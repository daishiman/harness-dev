#!/usr/bin/env python3
# /// script
# name: install-codex-plugin
# purpose: 明示依頼された local/Git marketplace plugin を Codex CLI へ登録・install・検証する。
# inputs:
#   - argv: --source SOURCE --plugin NAME [--ref REF] [--approved-plugin NAME ...] [--codex-home PATH]
#     (--source・--plugin・--ref・--codex-home は 1 回だけ。--approved-plugin を渡すと、plugin add の前に
#      対象plugin集合をこの集合と照合する。Git source では --ref に 40 桁の commit SHA も要る)
# outputs:
#   - stdout: install/verification receipt JSON (exit 3 でも phase・added_plugins を載せる)
#   - exit: 0=verified / 1=verification未達 (pending_user_gate・stale_runtime) /
#           2=argparse が拒む引数 (必須の欠け・1 回だけの引数の重複・空の --codex-home) /
#           3=引数の組み合わせ・source・CLI・artifact の契約違反
# contexts: [C, E]
# network: conditional (Git source のみ。Codex CLI が取得する)
# write-scope: ${CODEX_HOME:-~/.codex} (明示実行時のみ。git は --no-optional-locks で読むだけ)
# dependencies: [codex, git]
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
COMMIT_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
_INSTALL_METADATA = ".codex-marketplace-install.json"
_TREE_IGNORES = {".git", ".build", ".pytest_cache", "__pycache__", "node_modules"}
# install-local-plugins.py の _tree_digest と同じ除外にそろえる (配布される helper は単体で動かす)
_TREE_IGNORED_FILES = {".DS_Store"}
_TREE_IGNORED_PREFIXES = (".claude/handoff",)
_RUNTIME_MARKERS = {".in_use", ".orphaned_at"}
_JSON_ERRORS = (ValueError, RecursionError)  # JSONDecodeError と UnicodeDecodeError は ValueError
_PATH_ERRORS = (OSError, RuntimeError, ValueError)  # 権限・symlink の循環・NUL を含む path


def _resolve(path: Path, *, label: str) -> Path:
    try:
        return path.expanduser().resolve()
    except _PATH_ERRORS as exc:
        raise InstallError(f"cannot resolve {label}: {path!s}: {exc}") from exc


def _run_cli(command: list[str], *, env: dict[str, str]) -> str:
    """Codex CLI を走らせ、UTF-8 の stdout を返す。どの失敗も InstallError にする。"""
    try:
        result = subprocess.run(command, check=False, capture_output=True, env=env)
    except (OSError, ValueError) as exc:
        raise InstallError(f"cannot execute Codex CLI: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        raise InstallError(f"command failed ({result.returncode}): {' '.join(command)}: {detail}")
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InstallError(f"Codex CLI output is not UTF-8: {' '.join(command)}") from exc


def _run_json(command: list[str], *, env: dict[str, str]) -> dict:
    stdout = _run_cli(command, env=env)
    try:
        payload = json.loads(stdout)
    except _JSON_ERRORS as exc:
        raise InstallError(f"Codex CLI did not return JSON: {' '.join(command)}") from exc
    if not isinstance(payload, dict):
        raise InstallError(f"Codex CLI JSON must be an object: {' '.join(command)}")
    return payload


def _run_text(command: list[str], *, env: dict[str, str]) -> str:
    return _run_cli(command, env=env).strip()


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
    try:
        candidate = Path(source).expanduser()
    except RuntimeError as exc:
        raise InstallError(f"cannot expand source: {source}: {exc}") from exc
    if candidate.is_dir():
        return "local", str(_resolve(candidate, label="local marketplace root"))
    if source.startswith((".", "/", "~")):
        raise InstallError(f"local marketplace root does not exist: {source}")
    if source.startswith(("https://", "http://", "ssh://", "git@")) or GIT_SHORTHAND_RE.fullmatch(source):
        return "git", source
    raise InstallError("source must be an existing local marketplace root or a Git source")


def _read_json(path: Path, *, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, *_JSON_ERRORS) as exc:
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
    if "\0" in value:
        raise InstallError(f"Codex plugin source contains a NUL byte: {name}")
    root = _resolve(marketplace_root / value, label=f"Codex plugin source {name}")
    try:
        root.relative_to(_resolve(marketplace_root, label="Codex marketplace root"))
    except ValueError as exc:
        raise InstallError(f"Codex plugin source escapes marketplace root: {name}") from exc
    if not root.is_dir():
        raise InstallError(f"Codex plugin source does not exist: {name}")
    return root


def _load_catalog(marketplace_root: Path) -> tuple[str, dict[str, dict]]:
    marketplace_root = _resolve(marketplace_root, label="Codex marketplace root")
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
            contract_name = contract_payload.get("plugin_name")
            if contract_name is not None and contract_name != name:
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
    try:
        path = Path(value).expanduser()
    except RuntimeError as exc:
        raise InstallError(f"cannot expand runtime path: {plugin_id}: {value}") from exc
    if not path.is_absolute():
        raise InstallError(f"runtime path is not absolute: {plugin_id}: {value}")
    if not path.is_dir():
        raise InstallError(f"runtime path does not exist: {plugin_id}: {value}")
    return _resolve(path, label=f"runtime path {plugin_id}")


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
    """配布される tree の digest。symlink は辿らず、tree の中の着地点で記録する。"""
    digest = hashlib.sha256()
    try:
        resolved_root = root.resolve()
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            relative = path.relative_to(root)
            posix = relative.as_posix()
            if any(part in _TREE_IGNORES for part in relative.parts):
                continue
            if path.name in _TREE_IGNORED_FILES or any(
                posix == prefix or posix.startswith(prefix + "/")
                for prefix in _TREE_IGNORED_PREFIXES
            ):
                continue
            if relative.parts[0] in _RUNTIME_MARKERS:
                continue
            encoded = posix.encode("utf-8")
            if path.is_symlink():
                landing = Path(os.path.realpath(path))
                if landing.is_relative_to(resolved_root):
                    target = "@" + landing.relative_to(resolved_root).as_posix()
                else:
                    target = os.readlink(path)
                digest.update(b"L\0" + encoded + b"\0" + target.encode("utf-8"))
            elif path.is_file():
                digest.update(b"F\0" + encoded + b"\0" + path.read_bytes())
    except _PATH_ERRORS as exc:
        raise InstallError(f"cannot digest plugin tree: {root}: {exc}") from exc
    return digest.hexdigest()


def _git_snapshot(root: Path, *, exclude: tuple[str, ...] = ()) -> dict:
    """root の commit と、root の下の未 commit の変更 (untracked を含む) を読む。

    `--no-optional-locks` で、git status が利用者の .git/index を書き直さないようにする。
    """
    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(root), *args], check=False,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
        except (OSError, ValueError):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    repository = git("rev-parse", "--show-toplevel")
    commit = git("rev-parse", "HEAD") if repository else None
    pathspec = [".", *(f":(exclude){name}" for name in exclude)]
    dirty_output = (
        git("status", "--porcelain", "--untracked-files=all", "--", *pathspec)
        if repository else None
    )
    return {
        "repository": repository,
        "commit": commit,
        "dirty": bool(dirty_output) if dirty_output is not None else None,
    }


def _snapshot_revision(root: Path) -> dict:
    """Git marketplace の snapshot root が実際に指す commit を、実物から読む。

    出所は 2 つある。Codex が snapshot に書く install metadata の `revision` と、
    snapshot root そのものが checkout のときの `git rev-parse HEAD` である。
    receipt の `ref` は引数を写した値なので、ここでは使わない。2 つが食い違えば
    どちらを信じるか決められないので止める。`revision` が文字列でないなど、
    証拠そのものが壊れているときも、無いものとして捨てずに止める。
    checkout なら、作業ツリーの未 commit の変更 (`git_dirty`) も返す
    (Codex が書く install metadata は除く)。
    """
    recorded = None
    metadata_path = root / _INSTALL_METADATA
    if metadata_path.is_file():
        payload = _read_json(metadata_path, label="Codex marketplace install metadata")
        value = payload.get("revision")
        if value is not None:
            if not isinstance(value, str) or not value:
                raise InstallError(
                    f"{_INSTALL_METADATA} revision must be a non-empty string: {value!r}"
                )
            recorded = value.lower()
    head = None
    dirty = None
    snapshot = _git_snapshot(root, exclude=(_INSTALL_METADATA,))
    repository = snapshot.get("repository")
    # snapshot root より上の別の repository の HEAD を拾わない
    if repository and Path(repository).resolve() == root.resolve() and snapshot.get("commit"):
        head = snapshot["commit"].lower()
        dirty = snapshot.get("dirty")
    if recorded and head and recorded != head:
        raise InstallError(
            f"snapshot revision disagrees: {_INSTALL_METADATA} revision={recorded}, git HEAD={head}"
        )
    return {
        "revision": recorded or head,
        "install_metadata_revision": recorded,
        "git_head": head,
        "git_dirty": dirty,
    }


def _check_approved_set(install_order: tuple[str, ...], approved: tuple[str, ...] | None) -> None:
    """plugin add の前に、入れる集合が承認した集合と同じかを確かめる。"""
    if approved is None:
        return
    unapproved = sorted(set(install_order) - set(approved))
    not_in_closure = sorted(set(approved) - set(install_order))
    if unapproved or not_in_closure:
        raise InstallError(
            "install set differs from the approved set; no plugin was added: "
            f"unapproved={unapproved}, approved_but_not_in_closure={not_in_closure}"
        )


def _hook_digest(runtime_path: Path) -> str | None:
    manifest = _read_json(
        runtime_path / ".codex-plugin" / "plugin.json", label="Codex manifest"
    )
    value = manifest.get("hooks")
    candidates = [value] if isinstance(value, str) else []
    if "./hooks/hooks.json" not in candidates:
        candidates.append("./hooks/hooks.json")
    for candidate in candidates:
        if not candidate.startswith("./") or "\0" in candidate:
            continue
        try:
            path = (runtime_path / candidate).resolve()
            path.relative_to(runtime_path.resolve())
            if path.is_file():
                return hashlib.sha256(path.read_bytes()).hexdigest()
        except _PATH_ERRORS:
            continue
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
        if isinstance(raw_path, str) and raw_path and "\0" not in raw_path:
            try:
                candidate_path = Path(raw_path).expanduser()
                if candidate_path.is_absolute() and candidate_path.is_dir():
                    runtime_path = str(candidate_path.resolve())
                    hook_digest = _hook_digest(candidate_path.resolve())
            except (InstallError, *_PATH_ERRORS):
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
    source_path = _resolve(Path(metadata["root"]), label=f"plugin source {name}")
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
    source_digest = _tree_digest(source_path)
    runtime_digest = _tree_digest(runtime_path)
    # version が同じまま中身が違えば、CLI が古い copy を残している。version を上げるまで写し直さない
    stale = runtime_path != source_path and source_digest != runtime_digest
    return {
        "plugin": name,
        "plugin_id": plugin_id,
        "version": source_version,
        "manifest_version": source_version,
        "source_path": str(source_path),
        "runtime_path": str(runtime_path),
        "installed_path": str(runtime_path),
        "artifact_mode": artifact_mode,
        "source_digest": source_digest,
        "runtime_digest": runtime_digest,
        "git_snapshot": _git_snapshot(source_path),
        "enabled": True,
        "verified": not stale,
        "verification_status": "stale_runtime" if stale else "verified",
        "activation_errors": [],
        "activation": {
            "installed": "verified",
            "enabled": "verified",
            "trust": "pending_user_gate",
            "new_session": "pending_user_gate",
            "runtime": "stale" if stale else "verified",
        },
    }


def _installed_entries(cli_path: str, *, env: dict[str, str]) -> tuple[list, set[str]]:
    payload = _run_json([cli_path, "plugin", "list", "--json"], env=env)
    entries = payload.get("installed")
    if not isinstance(entries, list):
        raise InstallError("Codex plugin list JSON requires installed[]")
    ids = {
        entry["pluginId"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("pluginId"), str)
    }
    return entries, ids


def install(
    *,
    source: str,
    ref: str | None,
    plugin: str,
    codex_home: Path | None,
    approved_plugins: list[str] | None = None,
    progress: dict | None = None,
) -> dict:
    """plugin を入れて receipt を返す。

    `progress` には、止まったときに呼び出し側が receipt に載せる途中の状態を書く。
    `phase` は今いる局面、`added_plugins` は `plugin add` が exit 0 を返した plugin id。
    """
    progress = progress if progress is not None else {}
    added: list[str] = []
    progress.update({"phase": "preflight", "added_plugins": added})
    source_type, resolved_source = _classify_source(source)
    if ref and source_type != "git":
        raise InstallError("--ref is valid only for Git marketplace sources")
    approved = tuple(approved_plugins) if approved_plugins else None
    if approved is not None and len(set(approved)) != len(approved):
        raise InstallError("--approved-plugin contains duplicate names")
    # 40 桁の SHA は小文字にそろえ、Codex への引数・照合・receipt で同じ綴りを使う
    pinned = ref.lower() if ref and COMMIT_SHA_RE.fullmatch(ref) else None
    if pinned is not None:
        ref = pinned
    if approved is not None and source_type == "git" and pinned is None:
        raise InstallError(
            "--approved-plugin with a Git source requires --ref pinned to a 40-hex commit SHA"
        )
    local_catalog: tuple[str, dict[str, dict]] | None = None
    if source_type == "local":
        local_catalog = _load_catalog(Path(resolved_source))
        local_order, _, _ = _resolve_dependency_order(local_catalog[1], plugin)
        # local の対象集合は CLI を変える前に決まるので、ここで照合する
        _check_approved_set(local_order, approved)

    env = dict(os.environ)
    if codex_home is not None:
        env["CODEX_HOME"] = str(_resolve(codex_home, label="--codex-home"))
    cli_identity = _cli_identity(env)
    cli_path = cli_identity["cli_path"]

    progress["phase"] = "marketplace"
    add_command = [cli_path, "plugin", "marketplace", "add", resolved_source]
    if ref:
        add_command.extend(["--ref", ref])
    add_command.append("--json")
    marketplace_result = _run_json(add_command, env=env)
    marketplace_name = marketplace_result.get("marketplaceName")
    if not isinstance(marketplace_name, str) or not marketplace_name:
        raise InstallError("marketplace add did not return marketplaceName")
    progress["marketplace"] = marketplace_name

    def snapshot_root() -> Path:
        marketplace_list = _run_json(
            [cli_path, "plugin", "marketplace", "list", "--json"], env=env
        )
        return _marketplace_snapshot_root(marketplace_list, marketplace_name=marketplace_name)

    if source_type == "git" and marketplace_result.get("alreadyAdded") is True:
        # 固定した SHA の snapshot がもうあるなら、upgrade で動かさない
        if pinned is None or _snapshot_revision(snapshot_root())["revision"] != pinned:
            _run_json(
                [cli_path, "plugin", "marketplace", "upgrade", marketplace_name, "--json"],
                env=env,
            )

    progress["phase"] = "snapshot-check"
    revision: dict | None = None
    if source_type == "local":
        assert local_catalog is not None
        catalog_name, plugins = local_catalog
        marketplace_root = Path(resolved_source)
    else:
        marketplace_root = snapshot_root()
        revision = _snapshot_revision(marketplace_root)
        progress["resolved_revision"] = revision["revision"]
        if pinned is not None and revision["revision"] != pinned:
            raise InstallError(
                "Git snapshot is not at the pinned commit; no plugin was added: "
                f"pinned={pinned}, snapshot={revision['revision']}"
            )
        if pinned is not None and revision["git_dirty"]:
            raise InstallError(
                "Git snapshot checkout has uncommitted changes; no plugin was added: "
                f"{marketplace_root}"
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
    _check_approved_set(install_order, approved)
    cycle_members = {
        name: list(group) for group in cycle_groups for name in group
    }
    target_ids = [f"{name}@{marketplace_name}" for name in install_order]
    _, ids_before = _installed_entries(cli_path, env=env)

    progress["phase"] = "plugin-add"
    install_results = {}
    for name, plugin_id in zip(install_order, target_ids):
        progress["failed_plugin"] = plugin_id
        result = _run_json(
            [cli_path, "plugin", "add", plugin_id, "--json"],
            env=env,
        )
        added.append(plugin_id)
        del progress["failed_plugin"]
        returned_id = result.get("pluginId")
        if returned_id is not None and returned_id != plugin_id:
            raise InstallError(
                f"plugin add returned an unexpected pluginId: {returned_id!r}"
            )
        install_results[name] = result

    progress["phase"] = "post-install-verify"
    if revision is not None:
        # add の間に snapshot が動いていないことを、add の後に実物で確かめ直す
        after = _snapshot_revision(snapshot_root())
        if after != revision:
            raise InstallError(
                f"Git snapshot changed while plugins were added: before={revision}, after={after}"
            )
        revision = {**after, "rechecked_after_plugin_add": True}
    installed_entries, ids_after = _installed_entries(cli_path, env=env)
    unexpected = sorted(ids_after - ids_before - set(target_ids))
    if unexpected:
        progress["unexpected_plugins"] = unexpected
        raise InstallError(
            "plugins outside the install set appeared in plugin list: " + ", ".join(unexpected)
        )
    artifacts = []
    for name, plugin_id in zip(install_order, target_ids):
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
    # 依存が循環すると要求した plugin が最後に来るとは限らないので、名前で選ぶ
    selected = next(item for item in artifacts if item["plugin"] == plugin)
    verified = all(item.get("verified") is True for item in artifacts)
    stale = sorted(
        item["plugin_id"] for item in artifacts
        if item.get("verification_status") == "stale_runtime"
    )
    if stale:
        status = "stale_runtime"
        next_action = (
            "Bump the version of " + ", ".join(stale)
            + " with scripts/build-plugin-release.py, then reinstall."
        )
    else:
        status = "installed" if verified else "pending_user_gate"
        next_action = "Review and trust current hooks, then start a new thread."
    progress["phase"] = "done"
    return {
        "status": status,
        "phase": "done",
        "added_plugins": list(added),
        "source_type": source_type,
        "source": resolved_source,
        "marketplace_root": str(marketplace_root),
        "ref": ref,
        "resolved_revision": revision["revision"] if revision else None,
        "revision_evidence": revision,
        "approved_plugins": list(approved) if approved is not None else None,
        "marketplace": marketplace_name,
        **cli_identity,
        **selected,
        # selected は要求した plugin 1 件の値。依存の側だけが stale や hook 重複でも
        # exit 0 にしないよう、全件で集計した値を展開の後に置いて上書きさせない
        "verified": verified,
        "verification_status": status if status == "stale_runtime"
        else "verified" if verified else "not_verified",
        "dependency_closure": list(dependency_closure),
        "install_order": list(install_order),
        "cycle_groups": [list(group) for group in cycle_groups],
        "artifacts": artifacts,
        "hook_trust": "user-review-required",
        "next_action": next_action,
    }


class _Once(argparse.Action):
    """同じ引数を 2 回渡されたら、後の値で黙って上書きせず argparse の誤り (exit 2) にする。"""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            raise argparse.ArgumentError(self, "may be given only once")
        setattr(namespace, self.dest, values)


def _non_empty_path(value: str) -> Path:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return Path(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", required=True, action=_Once, help="Local repo root or Git marketplace source."
    )
    parser.add_argument(
        "--ref", action=_Once,
        help="Git ref to install after it has been merged (a 40-hex SHA is lowercased).",
    )
    parser.add_argument("--plugin", required=True, action=_Once)
    parser.add_argument(
        "--approved-plugin",
        action="append",
        metavar="NAME",
        help=(
            "Approved target plugin (repeat for the whole closure). The install set must equal "
            "this set before any plugin add; a Git source then also requires a 40-hex --ref."
        ),
    )
    parser.add_argument(
        "--codex-home", type=_non_empty_path, action=_Once, help="Optional isolated Codex home."
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    progress: dict = {}
    try:
        report = install(
            source=args.source,
            ref=args.ref,
            plugin=args.plugin,
            codex_home=args.codex_home,
            approved_plugins=args.approved_plugin,
            progress=progress,
        )
        code = 0 if report.get("verified", True) is not False else 1
    except InstallError as exc:
        report, code = {"status": "invalid", "error": str(exc), **progress}, 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
