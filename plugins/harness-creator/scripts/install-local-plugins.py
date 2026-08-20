#!/usr/bin/env python3
# /// script
# name: install-local-plugins
# purpose: harness の全 plugin を Claude Code/Codex の user 領域へ cwd 非依存で導入・検証する。
# network: false
# write-scope: ${CLAUDE_CONFIG_DIR:-~/.claude}, ${CODEX_HOME:-~/.codex} (明示実行時のみ)
# dependencies: [claude, codex]
# requires-python: ">=3.10"
# ///
"""Install repository-local plugins for Claude Code and Codex from any cwd."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple


class InstallError(Exception):
    pass


class Catalog(NamedTuple):
    repo_root: Path
    claude_root: Path
    codex_root: Path
    claude_marketplace: str
    codex_marketplace: str
    plugin_names: tuple[str, ...]


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]
_TREE_IGNORES = {".git", ".build", ".pytest_cache", "__pycache__", "node_modules"}


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"cannot read marketplace JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InstallError(f"marketplace JSON root must be an object: {path}")
    return payload


def _plugin_names(payload: dict, *, source: str) -> tuple[str, ...]:
    entries = payload.get("plugins")
    if not isinstance(entries, list):
        raise InstallError(f"{source} marketplace plugins must be an array")
    names = tuple(
        item.get("name") for item in entries if isinstance(item, dict)
    )
    if len(names) != len(entries) or not all(isinstance(name, str) and name for name in names):
        raise InstallError(f"{source} marketplace requires a name for every plugin")
    if len(set(names)) != len(names):
        raise InstallError(f"{source} marketplace contains duplicate plugin names")
    return names


def _manifest_identity(root: Path, *, platform: str, expected_name: str) -> tuple[Path, str]:
    directory = ".claude-plugin" if platform == "claude" else ".codex-plugin"
    path = root / directory / "plugin.json"
    payload = _read_json(path)
    if payload.get("name") != expected_name:
        raise InstallError(f"{platform} manifest name mismatch: {path}")
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise InstallError(f"{platform} manifest version is missing: {path}")
    return path, version


def _confined_plugin(repo_root: Path, value: str, *, base: Path, source: str) -> Path:
    if not value.startswith("./"):
        raise InstallError(f"{source} plugin source must start with ./: {value}")
    resolved = (base / value).resolve()
    try:
        resolved.relative_to((repo_root / "plugins").resolve())
    except ValueError as exc:
        raise InstallError(f"{source} plugin source escapes repo plugins/: {value}") from exc
    if not resolved.is_dir():
        raise InstallError(f"{source} plugin source does not exist: {value}")
    return resolved


def load_catalog(repo_root: Path) -> Catalog:
    repo_root = repo_root.expanduser().resolve()
    claude_root = (repo_root / "marketplaces" / "local").resolve()
    codex_root = repo_root
    claude = _read_json(claude_root / ".claude-plugin" / "marketplace.json")
    codex = _read_json(codex_root / ".agents" / "plugins" / "marketplace.json")
    claude_name, codex_name = claude.get("name"), codex.get("name")
    if not isinstance(claude_name, str) or not claude_name:
        raise InstallError("Claude marketplace name is missing")
    if not isinstance(codex_name, str) or not codex_name:
        raise InstallError("Codex marketplace name is missing")
    claude_names = _plugin_names(claude, source="Claude")
    codex_names = _plugin_names(codex, source="Codex")
    if set(claude_names) != set(codex_names):
        raise InstallError(
            "Claude and Codex catalogs disagree: "
            f"claude_only={sorted(set(claude_names) - set(codex_names))}, "
            f"codex_only={sorted(set(codex_names) - set(claude_names))}"
        )
    for entry in claude["plugins"]:
        source = entry.get("source")
        if not isinstance(source, str):
            raise InstallError(f"Claude plugin source must be a path: {entry.get('name')}")
        root = _confined_plugin(repo_root, source, base=claude_root, source="Claude")
        manifest_path = root / ".claude-plugin" / "plugin.json"
        if not manifest_path.is_file():
            raise InstallError(f"Claude manifest is missing: {root}")
        manifest = _read_json(manifest_path)
        _manifest_identity(root, platform="claude", expected_name=entry["name"])
        if "bundles" in manifest:
            raise InstallError(
                f"Claude manifest bundles belongs in marketplace metadata: {root}"
            )
    for entry in codex["plugins"]:
        source = entry.get("source")
        value = source.get("path") if isinstance(source, dict) and source.get("source") == "local" else None
        if not isinstance(value, str):
            raise InstallError(f"Codex plugin source must be local: {entry.get('name')}")
        root = _confined_plugin(repo_root, value, base=codex_root, source="Codex")
        manifest_path = root / ".codex-plugin" / "plugin.json"
        if not manifest_path.is_file():
            raise InstallError(f"Codex manifest is missing: {root}")
        _manifest_identity(root, platform="codex", expected_name=entry["name"])
    return Catalog(
        repo_root=repo_root,
        claude_root=claude_root,
        codex_root=codex_root,
        claude_marketplace=claude_name,
        codex_marketplace=codex_name,
        plugin_names=claude_names,
    )


def _source_root(catalog: Catalog, name: str) -> Path:
    root = (catalog.repo_root / "plugins" / name).resolve()
    try:
        root.relative_to((catalog.repo_root / "plugins").resolve())
    except ValueError as exc:
        raise InstallError(f"plugin source escapes repo plugins/: {name}") from exc
    if not root.is_dir():
        raise InstallError(f"plugin source does not exist: {name}")
    return root


def _plugin_dependencies(catalog: Catalog, name: str) -> tuple[str, ...]:
    contract = _source_root(catalog, name) / "references" / "package-contract.json"
    if not contract.is_file():
        return ()
    payload = _read_json(contract)
    if payload.get("plugin_name") not in {None, name}:
        raise InstallError(f"package contract plugin_name mismatch: {contract}")
    dependencies = payload.get("depends_on", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) and item for item in dependencies
    ):
        raise InstallError(f"package contract depends_on must be an array of plugin names: {contract}")
    if len(set(dependencies)) != len(dependencies):
        raise InstallError(f"package contract contains duplicate dependencies: {contract}")
    unknown = sorted(set(dependencies) - set(catalog.plugin_names))
    if unknown:
        raise InstallError(
            f"dependencies are not exposed by the same marketplace/source for {name}: "
            + ", ".join(unknown)
        )
    return tuple(dependencies)


def resolve_dependency_order(
    catalog: Catalog, requested: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Return dependency-first order, implicit closure, and cyclic SCCs."""
    graph: dict[str, tuple[str, ...]] = {}

    def collect(name: str) -> None:
        if name in graph:
            return
        dependencies = _plugin_dependencies(catalog, name)
        graph[name] = dependencies
        for dependency in dependencies:
            collect(dependency)

    for name in requested:
        collect(name)

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
        for dependency in sorted(graph[name]):
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

    for name in sorted(graph):
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
            for dependency in graph[name]
            if component_for[dependency] != component_index
        }
        for dependency_index in sorted(
            dependency_components, key=lambda item: components[item]
        ):
            visit_component(dependency_index)
        ordered_component_indexes.append(component_index)

    for name in requested:
        visit_component(component_for[name])
    ordered_components = tuple(components[item] for item in ordered_component_indexes)
    order = tuple(name for component in ordered_components for name in component)
    requested_set = set(requested)
    closure = tuple(name for name in order if name not in requested_set)
    cycle_groups = tuple(
        component
        for component in ordered_components
        if len(component) > 1 or component[0] in graph[component[0]]
    )
    return order, closure, cycle_groups


def _execute(command: list[str], *, env: dict[str, str], expect_json: bool):
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError as exc:
        raise InstallError(f"cannot execute {command[0]} CLI: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise InstallError(
            f"command failed ({result.returncode}): {' '.join(command)}: {detail}"
        )
    if not expect_json:
        return result.stdout.strip()
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise InstallError(f"CLI did not return JSON: {' '.join(command)}") from exc


def _cli_identity(name: str, env: dict[str, str]) -> dict[str, str]:
    executable = shutil.which(name, path=env.get("PATH"))
    if not executable:
        raise InstallError(f"{name} CLI is not available on PATH")
    # Keep the executable shim path: resolving Volta's `codex` symlink to the
    # internal `volta-shim` binary makes an otherwise valid CLI unexecutable.
    cli_path = os.path.abspath(os.path.expanduser(executable))
    version = _execute([cli_path, "--version"], env=env, expect_json=False).strip()
    if not version:
        raise InstallError(f"{name} CLI returned an empty version")
    return {"cli_path": cli_path, "cli_version": version.splitlines()[0]}


def _environment(*, claude_config_dir: Path | None, codex_home: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = _preferred_cli_path(Path.home(), env.get("PATH", ""))
    if claude_config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = str(claude_config_dir.expanduser().resolve())
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home.expanduser().resolve())
    return env


def _preferred_cli_path(home: Path, current: str) -> str:
    """Prefer user-managed current CLIs over cwd-dependent system shims."""
    candidates = [home / ".local" / "bin", home / ".volta" / "bin"]
    parts = [str(path.resolve()) for path in candidates if path.is_dir()]
    parts.extend(part for part in current.split(os.pathsep) if part and part not in parts)
    return os.pathsep.join(parts)


def _absolute_existing_path(value, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise InstallError(f"{label} did not report an install path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise InstallError(f"{label} install path is not absolute: {value}")
    if not path.is_dir():
        raise InstallError(f"{label} install path does not exist: {value}")
    return str(path.resolve())


def _tree_digest(root: Path) -> str:
    """Digest the delivered tree without following or hiding symlinks."""
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
    """Return commit provenance when the source lives in a Git snapshot."""
    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args],
                check=False,
                capture_output=True,
                text=True,
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


def _hook_digest(runtime_path: Path, *, platform: str) -> str | None:
    manifest_dir = ".claude-plugin" if platform == "claude" else ".codex-plugin"
    manifest = _read_json(runtime_path / manifest_dir / "plugin.json")
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


def _plugin_id_parts(plugin_id: object) -> tuple[str | None, str | None]:
    if not isinstance(plugin_id, str) or not plugin_id:
        return None, None
    name, separator, marketplace = plugin_id.partition("@")
    return name or None, marketplace if separator and marketplace else None


def _activation_observation(
    *,
    entries: list,
    platform: str,
    name: str,
    selected_id: str,
    id_key: str,
    path_getter,
) -> dict:
    candidates = []
    activation_errors = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_name, marketplace = _plugin_id_parts(entry.get(id_key))
        if entry_name != name:
            continue
        raw_path = path_getter(entry)
        runtime_path = None
        hook_digest = None
        if isinstance(raw_path, str) and raw_path:
            candidate_path = Path(raw_path).expanduser()
            if candidate_path.is_absolute() and candidate_path.is_dir():
                runtime_path = str(candidate_path.resolve())
                try:
                    hook_digest = _hook_digest(candidate_path.resolve(), platform=platform)
                except InstallError:
                    hook_digest = None
        errors = _activation_errors(entry) if platform == "claude" else []
        activation_errors.extend(errors)
        candidates.append({
            "plugin_id": entry.get(id_key),
            "scope": entry.get("scope") or ("user" if platform == "claude" else "user-global"),
            "marketplace": marketplace,
            "runtime_path": runtime_path,
            "hook_digest": hook_digest,
            "enabled": entry.get("enabled") is True,
            "selected": (
                entry.get(id_key) == selected_id
                and (platform != "claude" or entry.get("scope") == "user")
            ),
            "errors": errors,
        })
    enabled_digests = [
        item["hook_digest"] for item in candidates
        if item["enabled"] and item["hook_digest"] is not None
    ]
    same_hook = any(enabled_digests.count(value) > 1 for value in set(enabled_digests))
    return {
        "activation_collisions": candidates if len(candidates) > 1 else [],
        "same_hook_multiple_activation": same_hook,
        "activation_errors": activation_errors,
    }


def _activation_errors(entry: dict) -> list[str]:
    errors = entry.get("errors", [])
    if errors is None:
        return []
    if not isinstance(errors, list) or not all(isinstance(item, str) for item in errors):
        raise InstallError("Claude plugin list errors must be an array of strings")
    return [item for item in errors if item]


def _artifact_receipt(
    *,
    catalog: Catalog,
    platform: str,
    name: str,
    plugin_id: str,
    runtime_value,
    reported_version,
) -> dict:
    source_root = _source_root(catalog, name)
    _, source_version = _manifest_identity(
        source_root, platform=platform, expected_name=name
    )
    runtime_path = Path(
        _absolute_existing_path(runtime_value, label=plugin_id)
    ).resolve()
    _, runtime_version = _manifest_identity(
        runtime_path, platform=platform, expected_name=name
    )
    if not isinstance(reported_version, str) or not reported_version:
        raise InstallError(f"{plugin_id} did not report a version")
    versions = {source_version, runtime_version, reported_version}
    if len(versions) != 1:
        raise InstallError(
            f"{plugin_id} version mismatch: source={source_version}, "
            f"runtime={runtime_version}, reported={reported_version}"
        )
    artifact_mode = "live-source" if runtime_path == source_root else "copy"
    return {
        "platform": platform,
        "plugin": name,
        "plugin_id": plugin_id,
        "version": source_version,
        "manifest_version": source_version,
        "source_path": str(source_root),
        "runtime_path": str(runtime_path),
        # Backward-compatible alias; callers should prefer runtime_path.
        "installed_path": str(runtime_path),
        "artifact_mode": artifact_mode,
        "source_digest": _tree_digest(source_root),
        "runtime_digest": _tree_digest(runtime_path),
        "git_snapshot": _git_snapshot(source_root),
        "enabled": True,
        "verified": True,
        "verification_status": "verified",
        "activation": {
            "installed": "verified",
            "enabled": "verified",
            "trust": "pending_user_gate",
            "new_session": "pending_user_gate",
            "runtime": "verified",
        },
    }


def _marketplace_source(item: dict) -> Path | None:
    value = item.get("path")
    if not isinstance(value, str):
        source = item.get("marketplaceSource")
        value = source.get("source") if isinstance(source, dict) else None
    if not isinstance(value, str):
        return None
    return Path(value).expanduser().resolve()


def _assert_marketplace_source(
    entries: list,
    *,
    name: str,
    expected: Path,
) -> bool:
    matches = [item for item in entries if isinstance(item, dict) and item.get("name") == name]
    if not matches:
        return False
    actual = _marketplace_source(matches[0])
    if actual != expected.resolve():
        raise InstallError(
            f"marketplace {name} is already registered with a different source: "
            f"expected={expected.resolve()}, actual={actual}"
        )
    return True


def _verify_claude(
    *, catalog: Catalog, requested: tuple[str, ...], env: dict[str, str], cli_path: str
) -> list[dict]:
    payload = _execute(
        [cli_path, "plugin", "list", "--json"], env=env, expect_json=True
    )
    if not isinstance(payload, list):
        raise InstallError("Claude plugin list JSON must be an array")
    results = []
    for name in requested:
        plugin_id = f"{name}@{catalog.claude_marketplace}"
        installed = next(
            (
                item
                for item in payload
                if isinstance(item, dict)
                and item.get("id") == plugin_id
                and item.get("scope") == "user"
            ),
            None,
        )
        if not installed or installed.get("enabled") is not True:
            raise InstallError(f"Claude user-scope verification failed: {plugin_id}")
        results.append(
            _artifact_receipt(
                catalog=catalog,
                platform="claude",
                name=name,
                plugin_id=plugin_id,
                runtime_value=installed.get("installPath"),
                reported_version=installed.get("version"),
            )
        )
        artifact = results[-1]
        observation = _activation_observation(
            entries=payload,
            platform="claude",
            name=name,
            selected_id=plugin_id,
            id_key="id",
            path_getter=lambda item: item.get("installPath"),
        )
        artifact.update(observation)
        errors = observation["activation_errors"]
        if errors:
            artifact["verified"] = False
            artifact["verification_status"] = "not_verified"
            artifact["activation"]["runtime"] = "failed"
        if artifact["same_hook_multiple_activation"]:
            artifact["verified"] = False
            artifact["verification_status"] = "not_verified"
    return results


def _verify_codex(
    *, catalog: Catalog, requested: tuple[str, ...], env: dict[str, str], cli_path: str
) -> list[dict]:
    payload = _execute(
        [cli_path, "plugin", "list", "--json"], env=env, expect_json=True
    )
    installed_entries = payload.get("installed") if isinstance(payload, dict) else None
    if not isinstance(installed_entries, list):
        raise InstallError("Codex plugin list JSON requires installed[]")
    results = []
    for name in requested:
        plugin_id = f"{name}@{catalog.codex_marketplace}"
        installed = next(
            (
                item
                for item in installed_entries
                if isinstance(item, dict) and item.get("pluginId") == plugin_id
            ),
            None,
        )
        if (
            not installed
            or installed.get("installed") is not True
            or installed.get("enabled") is not True
        ):
            raise InstallError(f"Codex user-global verification failed: {plugin_id}")
        source = installed.get("source")
        source_path = source.get("path") if isinstance(source, dict) else None
        results.append(
            _artifact_receipt(
                catalog=catalog,
                platform="codex",
                name=name,
                plugin_id=plugin_id,
                runtime_value=source_path,
                reported_version=installed.get("version"),
            )
        )
        artifact = results[-1]
        artifact.update(_activation_observation(
            entries=installed_entries,
            platform="codex",
            name=name,
            selected_id=plugin_id,
            id_key="pluginId",
            path_getter=lambda item: (
                item.get("source", {}).get("path")
                if isinstance(item.get("source"), dict) else None
            ),
        ))
        if artifact["same_hook_multiple_activation"]:
            artifact["verified"] = False
            artifact["verification_status"] = "not_verified"
    return results


def _install_claude(
    *, catalog: Catalog, requested: tuple[str, ...], env: dict[str, str], check: bool
) -> tuple[dict, list[dict]]:
    cli_identity = _cli_identity("claude", env)
    cli_path = cli_identity["cli_path"]
    for name in requested:
        _execute(
            [
                cli_path, "plugin", "validate", "--strict",
                str(catalog.repo_root / "plugins" / name),
            ],
            env=env,
            expect_json=False,
        )
    marketplaces = _execute(
        [cli_path, "plugin", "marketplace", "list", "--json"],
        env=env,
        expect_json=True,
    )
    if not isinstance(marketplaces, list):
        raise InstallError("Claude marketplace list JSON must be an array")
    exists = _assert_marketplace_source(
        marketplaces,
        name=catalog.claude_marketplace,
        expected=catalog.claude_root,
    )
    if check and not exists:
        raise InstallError(f"Claude marketplace is not registered: {catalog.claude_marketplace}")
    if not check:
        if exists:
            _execute(
                [cli_path, "plugin", "marketplace", "update", catalog.claude_marketplace],
                env=env,
                expect_json=False,
            )
        else:
            _execute(
                [
                    cli_path, "plugin", "marketplace", "add",
                    str(catalog.claude_root), "--scope", "user",
                ],
                env=env,
                expect_json=False,
            )
        before = _execute(
            [cli_path, "plugin", "list", "--json"], env=env, expect_json=True
        )
        if not isinstance(before, list):
            raise InstallError("Claude plugin list JSON must be an array")
        for name in requested:
            plugin_id = f"{name}@{catalog.claude_marketplace}"
            already_user = any(
                isinstance(item, dict)
                and item.get("id") == plugin_id
                and item.get("scope") == "user"
                for item in before
            )
            verb = "update" if already_user else "install"
            _execute(
                [cli_path, "plugin", verb, "--scope", "user", plugin_id],
                env=env,
                expect_json=False,
            )
    plugins = _verify_claude(
        catalog=catalog, requested=requested, env=env, cli_path=cli_path
    )
    return {
        "scope": "user",
        "marketplace": catalog.claude_marketplace,
        "marketplace_source": str(catalog.claude_root),
        "plugin_count": len(plugins),
        **cli_identity,
    }, plugins


def _install_codex(
    *, catalog: Catalog, requested: tuple[str, ...], env: dict[str, str], check: bool
) -> tuple[dict, list[dict]]:
    cli_identity = _cli_identity("codex", env)
    cli_path = cli_identity["cli_path"]
    if check:
        payload = _execute(
            [cli_path, "plugin", "marketplace", "list", "--json"],
            env=env,
            expect_json=True,
        )
        entries = payload.get("marketplaces") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise InstallError("Codex marketplace list JSON requires marketplaces[]")
        if not _assert_marketplace_source(
            entries, name=catalog.codex_marketplace, expected=catalog.codex_root
        ):
            raise InstallError(f"Codex marketplace is not registered: {catalog.codex_marketplace}")
    else:
        added = _execute(
            [
                cli_path, "plugin", "marketplace", "add",
                str(catalog.codex_root), "--json",
            ],
            env=env,
            expect_json=True,
        )
        name = added.get("marketplaceName") if isinstance(added, dict) else None
        if name != catalog.codex_marketplace:
            raise InstallError(
                "Codex registered an unexpected marketplace: "
                f"expected={catalog.codex_marketplace}, actual={name}"
            )
        for plugin in requested:
            _execute(
                [cli_path, "plugin", "add", f"{plugin}@{catalog.codex_marketplace}", "--json"],
                env=env,
                expect_json=True,
            )
    plugins = _verify_codex(
        catalog=catalog, requested=requested, env=env, cli_path=cli_path
    )
    return {
        "scope": "user-global",
        "marketplace": catalog.codex_marketplace,
        "marketplace_source": str(catalog.codex_root),
        "plugin_count": len(plugins),
        **cli_identity,
    }, plugins


def install_local_plugins(
    *,
    repo_root: Path,
    platforms: tuple[str, ...],
    requested: tuple[str, ...],
    check: bool,
    claude_config_dir: Path | None,
    codex_home: Path | None,
) -> dict:
    catalog = load_catalog(repo_root)
    if not platforms or any(platform not in {"claude", "codex"} for platform in platforms):
        raise InstallError("platforms must contain claude and/or codex")
    unknown = sorted(set(requested) - set(catalog.plugin_names))
    if unknown:
        raise InstallError(f"unknown local plugins: {', '.join(unknown)}")
    if not requested:
        raise InstallError("at least one plugin must be selected")
    if len(set(requested)) != len(requested):
        raise InstallError("plugin selection contains duplicates")
    install_order, dependency_closure, cycle_groups = resolve_dependency_order(
        catalog, requested
    )
    env = _environment(
        claude_config_dir=claude_config_dir,
        codex_home=codex_home,
    )
    platform_reports = {}
    plugin_reports = []
    for platform in platforms:
        if platform == "claude":
            report, plugins = _install_claude(
                catalog=catalog, requested=install_order, env=env, check=check
            )
        else:
            report, plugins = _install_codex(
                catalog=catalog, requested=install_order, env=env, check=check
            )
        platform_reports[platform] = report
        plugin_reports.extend(plugins)
    cycle_members = {
        name: list(group) for group in cycle_groups for name in group
    }
    for plugin_report in plugin_reports:
        name = plugin_report["plugin"]
        plugin_report["scc_members"] = cycle_members.get(name, [name])
    verified = all(item.get("verified") is True for item in plugin_reports)
    return {
        "status": ("verified" if check else "installed") if verified else "pending_user_gate",
        "verified": verified,
        "repo_root": str(catalog.repo_root),
        "cwd_independent": True,
        "plugin_count": len(install_order),
        "requested_plugin_count": len(requested),
        "selected_plugins": list(requested),
        "dependency_closure": list(dependency_closure),
        "install_order": list(install_order),
        "cycle_groups": [list(group) for group in cycle_groups],
        "platforms": platform_reports,
        "plugins": plugin_reports,
        "hook_trust": "user-review-required",
        "next_action": "Review plugin hooks, then start a new Claude Code/Codex session.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
        help="Harness repository root (default: derived from this script, never cwd).",
    )
    parser.add_argument(
        "--platform", choices=("both", "claude", "codex"), default="both"
    )
    parser.add_argument(
        "--plugin", action="append", default=[], help="Install one named plugin; repeatable."
    )
    parser.add_argument(
        "--all", action="store_true", help="Install every plugin (also the default without --plugin)."
    )
    parser.add_argument("--check", action="store_true", help="Verify only; do not mutate CLI state.")
    parser.add_argument("--claude-config-dir", type=Path, help="Optional isolated Claude config dir.")
    parser.add_argument("--codex-home", type=Path, help="Optional isolated Codex home.")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.all and args.plugin:
            raise InstallError("--all and --plugin cannot be combined")
        if not args.all and not args.plugin:
            raise InstallError("explicit --all or --plugin selection is required")
        catalog = load_catalog(args.repo_root)
        requested = catalog.plugin_names if args.all else tuple(args.plugin)
        platforms = ("claude", "codex") if args.platform == "both" else (args.platform,)
        report = install_local_plugins(
            repo_root=args.repo_root,
            platforms=platforms,
            requested=requested,
            check=args.check,
            claude_config_dir=args.claude_config_dir,
            codex_home=args.codex_home,
        )
        code = 0 if report.get("verified", True) is not False else 1
    except InstallError as exc:
        report, code = {"status": "invalid", "error": str(exc)}, 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
