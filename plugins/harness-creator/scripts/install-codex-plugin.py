#!/usr/bin/env python3
# /// script
# name: install-codex-plugin
# purpose: 明示依頼された local/Git marketplace plugin を Codex CLI へ登録・install・検証する。
# network: conditional (Git source のみ)
# write-scope: ${CODEX_HOME:-~/.codex} (明示実行時のみ)
# dependencies: [codex]
# requires-python: ">=3.10"
# ///
"""Install one Codex plugin from a local or Git marketplace with a receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


class InstallError(Exception):
    pass


GIT_SHORTHAND_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TREE_IGNORES = {".git", ".build", ".pytest_cache", "__pycache__", "node_modules"}


def _run_json(command: list[str], *, env: dict[str, str]) -> dict:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError as exc:
        raise InstallError(f"cannot execute Codex CLI: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise InstallError(f"command failed ({result.returncode}): {' '.join(command)}: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise InstallError(f"Codex CLI did not return JSON: {' '.join(command)}") from exc
    if not isinstance(payload, dict):
        raise InstallError(f"Codex CLI JSON must be an object: {' '.join(command)}")
    return payload


def _run_text(command: list[str], *, env: dict[str, str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError as exc:
        raise InstallError(f"cannot execute Codex CLI: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise InstallError(f"command failed ({result.returncode}): {' '.join(command)}: {detail}")
    return result.stdout.strip()


def _cli_identity(env: dict[str, str]) -> dict[str, str]:
    executable = shutil.which("codex", path=env.get("PATH"))
    if not executable:
        raise InstallError("codex CLI is not available on PATH")
    # Preserve launcher symlinks such as Volta's `codex`; the resolved
    # `volta-shim` target is not a valid directly-invoked command.
    cli_path = os.path.abspath(os.path.expanduser(executable))
    version = _run_text([cli_path, "--version"], env=env)
    if not version:
        raise InstallError("codex CLI returned an empty version")
    return {"cli_path": cli_path, "cli_version": version.splitlines()[0]}


def _classify_source(source: str) -> tuple[str, str]:
    candidate = Path(source).expanduser()
    if candidate.is_dir():
        return "local", str(candidate.resolve())
    if source.startswith((".", "/", "~")):
        raise InstallError(f"local marketplace root does not exist: {source}")
    if source.startswith(("https://", "http://", "ssh://", "git@")) or GIT_SHORTHAND_RE.fullmatch(source):
        return "git", source
    raise InstallError("source must be an existing local marketplace root or a Git source")


def _read_json(path: Path, *, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InstallError(f"{label} must be a JSON object: {path}")
    return payload


def _manifest_version(root: Path, *, expected_name: str) -> str:
    path = root / ".codex-plugin" / "plugin.json"
    payload = _read_json(path, label="Codex manifest")
    if payload.get("name") != expected_name:
        raise InstallError(f"Codex manifest name mismatch: {path}")
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise InstallError(f"Codex manifest version is missing: {path}")
    return version


def _confined_plugin_root(marketplace_root: Path, value: str, *, name: str) -> Path:
    if not value.startswith("./"):
        raise InstallError(f"Codex plugin source must start with ./: {name}")
    root = (marketplace_root / value).resolve()
    try:
        root.relative_to(marketplace_root.resolve())
    except ValueError as exc:
        raise InstallError(f"Codex plugin source escapes marketplace root: {name}") from exc
    if not root.is_dir():
        raise InstallError(f"Codex plugin source does not exist: {name}")
    return root


def _load_catalog(marketplace_root: Path) -> tuple[str, dict[str, dict]]:
    marketplace_root = marketplace_root.expanduser().resolve()
    marketplace = marketplace_root / ".agents" / "plugins" / "marketplace.json"
    payload = _read_json(marketplace, label="Codex marketplace")
    marketplace_name = payload.get("name")
    if not isinstance(marketplace_name, str) or not marketplace_name:
        raise InstallError(f"Codex marketplace name is missing: {marketplace}")
    entries = payload.get("plugins")
    if not isinstance(entries, list):
        raise InstallError(f"Codex marketplace plugins must be an array: {marketplace}")
    plugins: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise InstallError(f"Codex marketplace plugin entry must be an object: {marketplace}")
        name = entry.get("name")
        source = entry.get("source")
        value = source.get("path") if isinstance(source, dict) and source.get("source") == "local" else None
        if not isinstance(name, str) or not name:
            raise InstallError(f"Codex marketplace plugin name is missing: {marketplace}")
        if name in plugins:
            raise InstallError(f"Codex marketplace contains duplicate plugin: {name}")
        if not isinstance(value, str):
            raise InstallError(f"Codex plugin source must be local within its marketplace: {name}")
        root = _confined_plugin_root(marketplace_root, value, name=name)
        version = _manifest_version(root, expected_name=name)
        contract = root / "references" / "package-contract.json"
        dependencies: tuple[str, ...] = ()
        if contract.is_file():
            contract_payload = _read_json(contract, label="package contract")
            if contract_payload.get("plugin_name") not in {None, name}:
                raise InstallError(f"package contract plugin_name mismatch: {contract}")
            depends_on = contract_payload.get("depends_on", [])
            if not isinstance(depends_on, list) or not all(
                isinstance(item, str) and item for item in depends_on
            ):
                raise InstallError(f"package contract depends_on must be an array: {contract}")
            if len(set(depends_on)) != len(depends_on):
                raise InstallError(f"package contract contains duplicate dependencies: {contract}")
            dependencies = tuple(depends_on)
        plugins[name] = {
            "root": root,
            "version": version,
            "dependencies": dependencies,
        }
    known = set(plugins)
    for name, metadata in plugins.items():
        unknown = sorted(set(metadata["dependencies"]) - known)
        if unknown:
            raise InstallError(
                f"dependencies are not exposed by the same marketplace/source for {name}: "
                + ", ".join(unknown)
            )
    return marketplace_name, plugins


def _resolve_dependency_order(
    plugins: dict[str, dict], requested: str
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, ...], ...]]:
    if requested not in plugins:
        raise InstallError(f"plugin is not exposed by marketplace: {requested}")
    reachable: set[str] = set()

    def collect(name: str) -> None:
        if name in reachable:
            return
        reachable.add(name)
        for dependency in plugins[name]["dependencies"]:
            collect(dependency)

    collect(requested)
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def strong_connect(name: str) -> None:
        nonlocal index
        indices[name] = index
        lowlinks[name] = index
        index += 1
        stack.append(name)
        on_stack.add(name)
        for dependency in sorted(plugins[name]["dependencies"]):
            if dependency not in indices:
                strong_connect(dependency)
                lowlinks[name] = min(lowlinks[name], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[name] = min(lowlinks[name], indices[dependency])
        if lowlinks[name] != indices[name]:
            return
        members = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            members.append(member)
            if member == name:
                break
        components.append(tuple(sorted(members)))

    for name in sorted(reachable):
        if name not in indices:
            strong_connect(name)

    component_for = {
        name: component_index
        for component_index, component in enumerate(components)
        for name in component
    }
    ordered_component_indexes: list[int] = []
    visited_components: set[int] = set()

    def visit_component(component_index: int) -> None:
        if component_index in visited_components:
            return
        visited_components.add(component_index)
        dependency_components = {
            component_for[dependency]
            for name in components[component_index]
            for dependency in plugins[name]["dependencies"]
            if component_for[dependency] != component_index
        }
        for dependency_index in sorted(
            dependency_components, key=lambda item: components[item]
        ):
            visit_component(dependency_index)
        ordered_component_indexes.append(component_index)

    visit_component(component_for[requested])
    ordered_components = tuple(components[item] for item in ordered_component_indexes)
    order = tuple(name for component in ordered_components for name in component)
    cycle_groups = tuple(
        component
        for component in ordered_components
        if len(component) > 1
        or component[0] in plugins[component[0]]["dependencies"]
    )
    return order, tuple(name for name in order if name != requested), cycle_groups


def _absolute_runtime_path(value, *, plugin_id: str) -> Path:
    if not isinstance(value, str) or not value:
        raise InstallError(f"runtime path is missing: {plugin_id}")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise InstallError(f"runtime path is not absolute: {plugin_id}: {value}")
    if not path.is_dir():
        raise InstallError(f"runtime path does not exist: {plugin_id}: {value}")
    return path.resolve()


def _marketplace_snapshot_root(payload: dict, *, marketplace_name: str) -> Path:
    entries = payload.get("marketplaces")
    if not isinstance(entries, list):
        raise InstallError("Codex marketplace list JSON requires marketplaces[]")
    match = next(
        (
            item
            for item in entries
            if isinstance(item, dict) and item.get("name") == marketplace_name
        ),
        None,
    )
    if not match:
        raise InstallError(f"Codex marketplace is not registered: {marketplace_name}")
    value = match.get("root") or match.get("path")
    if not isinstance(value, str):
        source = match.get("marketplaceSource")
        value = source.get("source") if isinstance(source, dict) else None
    return _absolute_runtime_path(value, plugin_id=f"marketplace {marketplace_name}")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if any(part in _TREE_IGNORES for part in relative.parts):
            continue
        encoded = relative.as_posix().encode("utf-8")
        if path.is_symlink():
            digest.update(b"L\0" + encoded + b"\0" + os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(b"F\0" + encoded + b"\0" + path.read_bytes())
        elif path.is_dir():
            digest.update(b"D\0" + encoded + b"\0")
    return digest.hexdigest()


def _git_snapshot(root: Path) -> dict:
    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args], check=False,
                capture_output=True, text=True,
            )
        except OSError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    repository = git("rev-parse", "--show-toplevel")
    commit = git("rev-parse", "HEAD") if repository else None
    dirty_output = git("status", "--porcelain", "--", str(root)) if repository else None
    return {
        "repository": repository,
        "commit": commit,
        "dirty": bool(dirty_output) if dirty_output is not None else None,
    }


def _hook_digest(runtime_path: Path) -> str | None:
    manifest = _read_json(
        runtime_path / ".codex-plugin" / "plugin.json", label="Codex manifest"
    )
    value = manifest.get("hooks")
    candidates = [value] if isinstance(value, str) else []
    if "./hooks/hooks.json" not in candidates:
        candidates.append("./hooks/hooks.json")
    for candidate in candidates:
        if not candidate.startswith("./"):
            continue
        path = (runtime_path / candidate).resolve()
        try:
            path.relative_to(runtime_path.resolve())
        except ValueError:
            continue
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def _plugin_id_parts(value: object) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value:
        return None, None
    name, separator, marketplace = value.partition("@")
    return name or None, marketplace if separator and marketplace else None


def _activation_observation(
    *, installed_entries: list, name: str, selected_id: str
) -> dict:
    candidates = []
    for entry in installed_entries:
        if not isinstance(entry, dict):
            continue
        entry_name, marketplace = _plugin_id_parts(entry.get("pluginId"))
        if entry_name != name:
            continue
        source = entry.get("source")
        raw_path = source.get("path") if isinstance(source, dict) else None
        runtime_path = None
        hook_digest = None
        if isinstance(raw_path, str) and raw_path:
            candidate_path = Path(raw_path).expanduser()
            if candidate_path.is_absolute() and candidate_path.is_dir():
                runtime_path = str(candidate_path.resolve())
                try:
                    hook_digest = _hook_digest(candidate_path.resolve())
                except InstallError:
                    hook_digest = None
        candidates.append({
            "plugin_id": entry.get("pluginId"),
            "scope": entry.get("scope") or "user-global",
            "marketplace": marketplace,
            "runtime_path": runtime_path,
            "hook_digest": hook_digest,
            "enabled": entry.get("enabled") is True,
            "selected": entry.get("pluginId") == selected_id,
        })
    enabled_digests = [
        item["hook_digest"] for item in candidates
        if item["enabled"] and item["hook_digest"] is not None
    ]
    same_hook = any(enabled_digests.count(value) > 1 for value in set(enabled_digests))
    return {
        "activation_collisions": candidates if len(candidates) > 1 else [],
        "same_hook_multiple_activation": same_hook,
    }


def _artifact_receipt(
    *,
    name: str,
    marketplace_name: str,
    metadata: dict,
    installed: dict,
    install_result: dict,
    source_type: str,
) -> dict:
    plugin_id = f"{name}@{marketplace_name}"
    if installed.get("installed") is not True:
        raise InstallError(f"post-install verification failed: {plugin_id}")
    if installed.get("enabled") is not True:
        raise InstallError(f"plugin is not enabled: {plugin_id}")
    source = installed.get("source")
    runtime_value = source.get("path") if isinstance(source, dict) else None
    runtime_path = _absolute_runtime_path(runtime_value, plugin_id=plugin_id)
    installed_path_value = install_result.get("installedPath")
    if installed_path_value is not None:
        installed_path = _absolute_runtime_path(installed_path_value, plugin_id=plugin_id)
        if installed_path != runtime_path:
            raise InstallError(
                f"runtime path mismatch: {plugin_id}: "
                f"install_result={installed_path}, installed={runtime_path}"
            )
    reported_version = installed.get("version")
    if not isinstance(reported_version, str) or not reported_version:
        raise InstallError(f"installed version is missing: {plugin_id}")
    result_version = install_result.get("version")
    if result_version is not None and result_version != reported_version:
        raise InstallError(
            f"version mismatch: {plugin_id}: "
            f"install_result={result_version}, installed={reported_version}"
        )
    source_path = Path(metadata["root"]).resolve()
    source_version = metadata["version"]
    runtime_version = _manifest_version(runtime_path, expected_name=name)
    if len({source_version, runtime_version, reported_version}) != 1:
        raise InstallError(
            f"version mismatch: {plugin_id}: source={source_version}, "
            f"runtime={runtime_version}, installed={reported_version}"
        )
    artifact_mode = (
        "git-snapshot"
        if source_type == "git"
        else "live-source" if runtime_path == source_path else "copy"
    )
    return {
        "plugin": name,
        "plugin_id": plugin_id,
        "version": source_version,
        "manifest_version": source_version,
        "source_path": str(source_path),
        "runtime_path": str(runtime_path),
        "installed_path": str(runtime_path),
        "artifact_mode": artifact_mode,
        "source_digest": _tree_digest(source_path),
        "runtime_digest": _tree_digest(runtime_path),
        "git_snapshot": _git_snapshot(source_path),
        "enabled": True,
        "verified": True,
        "verification_status": "verified",
        "activation_errors": [],
        "activation": {
            "installed": "verified",
            "enabled": "verified",
            "trust": "pending_user_gate",
            "new_session": "pending_user_gate",
            "runtime": "verified",
        },
    }


def install(
    *,
    source: str,
    ref: str | None,
    plugin: str,
    codex_home: Path | None,
) -> dict:
    source_type, resolved_source = _classify_source(source)
    if ref and source_type != "git":
        raise InstallError("--ref is valid only for Git marketplace sources")
    local_catalog: tuple[str, dict[str, dict]] | None = None
    if source_type == "local":
        local_catalog = _load_catalog(Path(resolved_source))
        _resolve_dependency_order(local_catalog[1], plugin)

    env = dict(os.environ)
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home.expanduser().resolve())
    cli_identity = _cli_identity(env)
    cli_path = cli_identity["cli_path"]

    add_command = [cli_path, "plugin", "marketplace", "add", resolved_source]
    if ref:
        add_command.extend(["--ref", ref])
    add_command.append("--json")
    marketplace_result = _run_json(add_command, env=env)
    marketplace_name = marketplace_result.get("marketplaceName")
    if not isinstance(marketplace_name, str) or not marketplace_name:
        raise InstallError("marketplace add did not return marketplaceName")

    if source_type == "git" and marketplace_result.get("alreadyAdded") is True:
        _run_json(
            [cli_path, "plugin", "marketplace", "upgrade", marketplace_name, "--json"],
            env=env,
        )

    if source_type == "local":
        assert local_catalog is not None
        catalog_name, plugins = local_catalog
        marketplace_root = Path(resolved_source).resolve()
    else:
        marketplace_list = _run_json(
            [cli_path, "plugin", "marketplace", "list", "--json"], env=env
        )
        marketplace_root = _marketplace_snapshot_root(
            marketplace_list, marketplace_name=marketplace_name
        )
        catalog_name, plugins = _load_catalog(marketplace_root)
    if catalog_name != marketplace_name:
        raise InstallError(
            "Codex registered an unexpected marketplace: "
            f"manifest={catalog_name}, registered={marketplace_name}"
        )
    install_order, dependency_closure, cycle_groups = _resolve_dependency_order(
        plugins, plugin
    )
    cycle_members = {
        name: list(group) for group in cycle_groups for name in group
    }
    install_results = {}
    for name in install_order:
        plugin_id = f"{name}@{marketplace_name}"
        result = _run_json(
            [cli_path, "plugin", "add", plugin_id, "--json"],
            env=env,
        )
        if result.get("pluginId") not in {None, plugin_id}:
            raise InstallError(
                f"plugin add returned an unexpected pluginId: {result.get('pluginId')}"
            )
        install_results[name] = result
    list_result = _run_json([cli_path, "plugin", "list", "--json"], env=env)
    installed_entries = list_result.get("installed")
    if not isinstance(installed_entries, list):
        raise InstallError("Codex plugin list JSON requires installed[]")
    artifacts = []
    for name in install_order:
        plugin_id = f"{name}@{marketplace_name}"
        installed = next(
            (
                item
                for item in installed_entries
                if isinstance(item, dict) and item.get("pluginId") == plugin_id
            ),
            None,
        )
        if not installed:
            raise InstallError(f"post-install verification failed: {plugin_id}")
        artifact = _artifact_receipt(
            name=name,
            marketplace_name=marketplace_name,
            metadata=plugins[name],
            installed=installed,
            install_result=install_results[name],
            source_type=source_type,
        )
        artifact.update(_activation_observation(
            installed_entries=installed_entries,
            name=name,
            selected_id=plugin_id,
        ))
        if artifact["same_hook_multiple_activation"]:
            artifact["verified"] = False
            artifact["verification_status"] = "not_verified"
        artifact["scc_members"] = cycle_members.get(name, [name])
        artifacts.append(artifact)
    selected = artifacts[-1]
    verified = all(item.get("verified") is True for item in artifacts)
    return {
        "status": "installed" if verified else "pending_user_gate",
        "verified": verified,
        "source_type": source_type,
        "source": resolved_source,
        "marketplace_root": str(marketplace_root),
        "ref": ref,
        "marketplace": marketplace_name,
        **cli_identity,
        **selected,
        "dependency_closure": list(dependency_closure),
        "install_order": list(install_order),
        "cycle_groups": [list(group) for group in cycle_groups],
        "artifacts": artifacts,
        "hook_trust": "user-review-required",
        "next_action": "Review and trust current hooks, then start a new thread.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Local repo root or Git marketplace source.")
    parser.add_argument("--ref", help="Git ref to install after it has been merged.")
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--codex-home", type=Path, help="Optional isolated Codex home.")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = install(
            source=args.source,
            ref=args.ref,
            plugin=args.plugin,
            codex_home=args.codex_home,
        )
        code = 0 if report.get("verified", True) is not False else 1
    except InstallError as exc:
        report, code = {"status": "invalid", "error": str(exc)}, 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
