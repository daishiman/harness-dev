#!/usr/bin/env python3
# /// script
# name: build-project-hook-fallback
# purpose: C01 R5 の決定論本体。plain-symlink 導入の repo だけで plugin hooks.json の全 event を `.claude/settings.json` へ (event, matcher, command) 単位で追記 merge し、既存 key/hook group の hash 不変と二重登録 0 を自己検証して rollback manifest を残す。effective plugin hook・disableAllHooks・allowManagedHooksOnly・他 scope の dev-graph hook・link 不一致は書込み 0 で拒否する。
# inputs: ["argv: --repo-root PATH [--config PATH] [--mode preview|apply|rollback] [--manifest PATH] [--user-settings PATH] [--managed-settings PATH]"]
# outputs: ["stdout: JSON preview/noop/applied/rolled_back or rejection report"]
# requires-python = ">=3.10"
# dependencies: [_common.py, validate-graph-schema.py, resolve-repo-context.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: caller repository .claude/settings.json, .dev-graph/config.json (claude_hooks.source only) and .dev-graph/state/receipts/hook-fallback-*.json
# ///
"""run-dev-graph-init の R5 project fallback。dev-graph を Claude plugin として有効化していない導入先だけで使う。

hook の同一性は (event, matcher, command) とする。command は `${CLAUDE_PROJECT_DIR}/<link>/hooks/<script>` を
引用符付きで固定するので、同じ組があれば登録済みとして足さない。settings に独自の識別 key は足さない。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import ContractError, contained, dump, load_json, utc_now

HERE = Path(__file__).resolve().parent
OWNER = "C01/run-dev-graph-init/R5-hooks"
PLUGIN_TOKEN = "${CLAUDE_PLUGIN_ROOT}"
PROJECT_TOKEN = "${CLAUDE_PROJECT_DIR}"
SETTINGS = ".claude/settings.json"
LOCAL_SETTINGS = ".claude/settings.local.json"
# 公式の managed settings の既定位置。test と非標準の host は --managed-settings で差し替える。
MANAGED_DEFAULT = ("/Library/Application Support/ClaudeCode/managed-settings.json" if sys.platform == "darwin"
                   else "/etc/claude-code/managed-settings.json")
# settings の優先順位 (後ろほど強い)。enabledPlugins と disableAllHooks の実効値をこの順で畳む。
SCOPES = ("user", "project", "local", "managed")
CONFIG_SCHEMA = HERE.parent / "schemas" / "repo-config.schema.json"


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("dev_graph_validate_graph_schema", HERE / "validate-graph-schema.py")
    if spec is None or spec.loader is None:
        raise ContractError("cannot load validate-graph-schema.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VGS = _load_validator()


class FallbackError(ContractError):
    def __init__(self, code: str, detail: str, findings: list[dict[str, Any]] | None = None) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.findings = code, detail, findings or []


def _context(repo_root: str, config: str, mode: str) -> dict[str, Any]:
    argv = [sys.executable, str(HERE / "resolve-repo-context.py"), "--repo-root", repo_root, "--config", config,
            "--mode", mode]
    cp = subprocess.run(argv, text=True, capture_output=True, check=False)
    if cp.returncode:
        raise FallbackError("c24_context_failed", (cp.stderr or cp.stdout).strip())
    return json.loads(cp.stdout)


def _sha(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _canon(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _settings_bytes(value: dict[str, Any]) -> bytes:
    # 利用者の key 順を保つため sort しない。値は変えないので既存 key の hash は不変になる。
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _config_bytes(value: dict[str, Any]) -> bytes:
    # init と atomic_json と同じ直列化にして、source 以外の行を動かさない。
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _read_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _read_settings(path: Path, scope: str) -> dict[str, Any] | None:
    if not (path.exists() or path.is_symlink()):
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FallbackError("settings_invalid", f"{scope} settings is not valid JSON: {exc}") from exc
    hooks = value.get("hooks", {}) if isinstance(value, dict) else None
    valid = isinstance(hooks, dict) and all(
        isinstance(groups, list) and all(isinstance(group, dict) and isinstance(group.get("hooks"), list) for group in groups)
        for groups in hooks.values())
    if not valid:
        raise FallbackError("settings_invalid", f"{scope} settings must be an object whose hooks map events to [{{matcher?, hooks: [...]}}]")
    return value


def _identities(settings: dict[str, Any] | None) -> list[tuple[str, str | None, str]]:
    return [(event, group.get("matcher"), hook["command"])
            for event, groups in (settings or {}).get("hooks", {}).items() for group in groups
            for hook in group["hooks"] if isinstance(hook, dict) and isinstance(hook.get("command"), str)]


def _desired(plugin_source: Path, link_rel: str) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    """plugin hooks.json の全 event を、plugin root の代わりに repo-local link を指す command へ写す。"""
    source = load_json(plugin_source / "hooks" / "hooks.json")["hooks"]
    prefix = f"{PROJECT_TOKEN}/{link_rel}"
    desired = {event: [{**group, "hooks": [{**hook, "command": hook["command"].replace(PLUGIN_TOKEN, prefix)}
                                           for hook in group["hooks"]]} for group in groups]
               for event, groups in source.items()}
    commands = [command for _, _, command in _identities({"hooks": desired})]
    if any(PLUGIN_TOKEN in command for command in commands):
        raise FallbackError("plugin_hook_unmapped", "a fallback command still depends on ${CLAUDE_PLUGIN_ROOT}")
    scripts = {name for command in commands for name in re.findall(r"/hooks/([A-Za-z0-9_.-]+\.py)", command)}
    return desired, scripts


def _is_dev_graph(command: str, scripts: set[str]) -> bool:
    return any(f"/hooks/{name}" in command for name in scripts)


def _check_link(root: Path, link_rel: str, plugin_source: Path) -> None:
    link = root / link_rel
    contained(link.parent, root)
    if not link.is_symlink():
        raise FallbackError("plugin_link_not_symlink", f"{link_rel} must be a plain symlink to the dev-graph plugin source")
    try:
        target = link.resolve(strict=True)
    except OSError as exc:
        raise FallbackError("plugin_link_broken", f"{link_rel}: {exc}") from exc
    if target != plugin_source.resolve(strict=True):
        raise FallbackError("plugin_link_mismatch", f"{link_rel} does not resolve to the C24 plugin source")


def _diagnose(scopes: dict[str, dict[str, Any] | None], scripts: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """実効設定で project hook が効かない、または二重に効く条件を blocking として返す。"""
    enabled: dict[str, Any] = {}
    disabled = False
    for scope in SCOPES:
        settings = scopes[scope] or {}
        if isinstance(settings.get("enabledPlugins"), dict):
            enabled.update(settings["enabledPlugins"])
        if "disableAllHooks" in settings:
            disabled = settings["disableAllHooks"] is True
    blocking: list[dict[str, Any]] = []
    effective = sorted(key for key, value in enabled.items() if key.split("@", 1)[0] == "dev-graph" and value is True)
    if effective:
        blocking.append({"code": "plugin_hook_effective", "plugins": effective,
                         "detail": "dev-graph is enabled as a Claude plugin; its hooks.json already wires every event"})
    if disabled:
        blocking.append({"code": "hooks_disabled", "detail": "disableAllHooks is effective; project hooks would not run"})
    if (scopes["managed"] or {}).get("allowManagedHooksOnly") is True:
        blocking.append({"code": "managed_hooks_only", "detail": "managed policy allows managed hooks only"})
    for scope in ("user", "local", "managed"):
        for event, matcher, command in _identities(scopes[scope]):
            if _is_dev_graph(command, scripts):
                blocking.append({"code": "duplicate_registration", "scope": scope, "event": event, "matcher": matcher,
                                 "detail": "a dev-graph hook is already registered outside project settings"})
    notes = [f"{scope}_settings_absent" for scope in SCOPES if scopes[scope] is None]
    return blocking, notes


def _merge(project: dict[str, Any], desired: dict[str, list[dict[str, Any]]], scripts: set[str]) -> tuple[dict[str, Any], list, list]:
    wanted = set(_identities({"hooks": desired}))
    stray = [ident for ident in _identities(project) if _is_dev_graph(ident[2], scripts) and ident not in wanted]
    if stray:
        raise FallbackError("duplicate_registration", "project settings has a dev-graph hook other than the fallback wiring",
                            [{"code": "duplicate_registration", "scope": "project", "event": e, "matcher": m} for e, m, _ in stray])
    present = set(_identities(project))
    merged = json.loads(json.dumps(project))
    added: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for event, groups in desired.items():
        for group in groups:
            ids = [(event, group.get("matcher"), hook["command"]) for hook in group["hooks"]]
            row = {"event": event, "matcher": group.get("matcher"), "commands": [command for _, _, command in ids]}
            hits = sum(ident in present for ident in ids)
            if hits == len(ids):
                kept.append(row)
            elif hits:
                raise FallbackError("duplicate_registration", f"{event} has only part of a dev-graph hook group")
            else:
                merged.setdefault("hooks", {}).setdefault(event, []).append(json.loads(json.dumps(group)))
                added.append(row)
    return merged, added, kept


def _verify(before: dict[str, Any], after: dict[str, Any], desired: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """merge が追記だけだったことを、既存 key と既存 hook group の hash で確かめる。"""
    changed = [key for key, value in before.items() if key != "hooks" and (key not in after or _canon(after[key]) != _canon(value))]
    groups = 0
    for event, previous in before.get("hooks", {}).items():
        current = after["hooks"].get(event, [])
        groups += len(previous)
        changed += [f"hooks.{event}[{i}]" for i, group in enumerate(previous)
                    if i >= len(current) or _canon(current[i]) != _canon(group)]
    identities = _identities(after)
    duplicates = sum(max(0, identities.count(ident) - 1) for ident in set(_identities({"hooks": desired})))
    if changed or duplicates:
        raise FallbackError("merge_not_additive", f"changed={changed} duplicates={duplicates}")
    return {"top_level_keys": sum(key != "hooks" for key in before), "hook_groups": groups, "changed": 0,
            "duplicate_registrations": 0}


def _atomic_bytes(path: Path, data: bytes) -> None:
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _create_only(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        os.unlink(temp)


def _plain_file(path: Path, root: Path) -> Path:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise FallbackError("path_not_file", f"{path.relative_to(root).as_posix()} exists but is not a plain file")
    return contained(path, root, must_exist=False)


def apply(args: argparse.Namespace) -> dict[str, Any]:
    ctx = _context(args.repo_root, args.config, "read" if args.mode == "preview" else "write")
    root = Path(ctx["repo_root"]).resolve(strict=True)
    plugin_source = Path(ctx["plugin_source"])
    config_path = _plain_file(Path(ctx["local_state_paths"]["config"]), root)
    if not config_path.exists():
        raise FallbackError("config_missing", "run build-init-scaffold.py before wiring hooks")
    config = load_json(config_path)
    link_rel = config["claude_hooks"]["project_plugin_link"]
    _check_link(root, link_rel, plugin_source)
    desired, scripts = _desired(plugin_source, link_rel)
    settings_path = _plain_file(root / SETTINGS, root)
    scopes = {"user": _read_settings(Path(args.user_settings), "user"), "project": _read_settings(settings_path, "project"),
              "local": _read_settings(root / LOCAL_SETTINGS, "local"),
              "managed": _read_settings(Path(args.managed_settings), "managed")}
    blocking, notes = _diagnose(scopes, scripts)
    if blocking:
        raise FallbackError(blocking[0]["code"], f"{len(blocking)} blocking diagnostic(s)", blocking)
    before = scopes["project"] or {}
    merged, added, kept = _merge(before, desired, scripts)
    preserved = _verify(before, merged, desired)
    new_config = json.loads(json.dumps(config))
    new_config["claude_hooks"]["source"] = "project"
    findings = [{**item, "node": "repo-config"} for item in VGS.schema_findings(new_config, load_json(CONFIG_SCHEMA), 0)]
    if findings:
        raise FallbackError("config_invalid", f"{len(findings)} repo-config finding(s)", findings)

    def rel(path: Path) -> str:
        return path.relative_to(root).as_posix()

    files = []
    for path, after in ((settings_path, _settings_bytes(merged) if added else None),
                        (config_path, _config_bytes(new_config) if config["claude_hooks"]["source"] != "project" else None)):
        current = _read_bytes(path)
        if after is not None and after != current:
            files.append({"path": rel(path), "existed": current is not None, "before_sha256": _sha(current),
                          "before_text": None if current is None else current.decode("utf-8"),
                          "after_sha256": _sha(after), "_after": after, "_target": path})
    report = {"owner": OWNER, "repository_id": ctx["repository_id"], "plugin_link": link_rel, "source": "project",
              "added": added, "already_present": kept, "preserved": preserved, "diagnostics": notes,
              "planned_changes": len(files), "changed_files": [row["path"] for row in files]}
    if not files:
        return {**report, "status": "noop", "valid": True, "write_count": 0}
    if args.mode == "preview":
        return {**report, "status": "preview", "valid": True, "write_count": 0, "after_settings": merged}
    now = utc_now()
    manifest_path = Path(ctx["local_state_paths"]["graph"]).parent / "receipts" / f"hook-fallback-{re.sub(r'[^0-9TZ]', '', now)}.json"
    manifest_path = contained(manifest_path, root, must_exist=False)
    manifest = {**report, "schema_version": "1.0.0", "kind": "hook-fallback", "status": "applied", "recorded_at": now,
                "manifest_path": rel(manifest_path),
                "files": [{key: value for key, value in row.items() if not key.startswith("_")} for row in files]}
    # write-ahead: rollback に要る before bytes を、書き換えより先に create-only で残す。
    _create_only(manifest_path, _config_bytes(manifest))
    written: list[dict[str, Any]] = []
    try:
        for row in files:
            _atomic_bytes(row["_target"], row["_after"])
            written.append(row)
    except BaseException:
        for row in reversed(written):
            _restore(row["_target"], row)
        raise
    return {**manifest, "valid": True, "write_count": len(files) + 1}


def _restore(path: Path, row: dict[str, Any]) -> None:
    if row["existed"]:
        _atomic_bytes(path, row["before_text"].encode("utf-8"))
    else:
        path.unlink(missing_ok=True)


def rollback(args: argparse.Namespace) -> dict[str, Any]:
    if not args.manifest:
        raise FallbackError("manifest_required", "--mode rollback needs --manifest")
    ctx = _context(args.repo_root, args.config, "write")
    root = Path(ctx["repo_root"]).resolve(strict=True)
    path = Path(args.manifest)
    manifest = load_json(contained(path if path.is_absolute() else root / path, root))
    if manifest.get("kind") != "hook-fallback" or manifest.get("repository_id") != ctx["repository_id"]:
        raise FallbackError("manifest_mismatch", "manifest is not a hook-fallback receipt of this repository")
    restore, restored = [], []
    for row in manifest["files"]:
        target = _plain_file(root / row["path"], root)
        current = _sha(_read_bytes(target))
        if current == row["before_sha256"]:
            restored.append(row["path"])
        elif current == row["after_sha256"]:
            restore.append((target, row))
        else:
            # apply 後に誰かが書き換えた file を before で潰すと、その変更を黙って失う。
            raise FallbackError("rollback_drift", f"{row['path']} changed after the fallback was applied")
    base = {"owner": OWNER, "repository_id": ctx["repository_id"], "manifest_path": manifest["manifest_path"],
            "already_restored": restored, "restored": [row["path"] for _, row in restore]}
    if not restore:
        return {**base, "status": "noop", "valid": True, "write_count": 0}
    for target, row in restore:
        _restore(target, row)
    return {**base, "status": "rolled_back", "valid": True, "write_count": len(restore)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C01 R5 project hook fallback (追記 merge・二重登録 0・rollback manifest)")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--config", default=".dev-graph/config.json")
    parser.add_argument("--mode", choices=("preview", "apply", "rollback"), default="preview")
    parser.add_argument("--manifest", help="rollback する hook-fallback manifest (repo-relative 可)")
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    parser.add_argument("--user-settings", default=str(config_dir / "settings.json"))
    parser.add_argument("--managed-settings", default=MANAGED_DEFAULT)
    args = parser.parse_args(argv)
    try:
        dump(rollback(args) if args.mode == "rollback" else apply(args))
        return 0
    except FallbackError as exc:
        dump({"valid": False, "status": "rejected", "code": exc.code, "error": exc.detail, "findings": exc.findings,
              "write_count": 0})
        return 1
    except (ContractError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        dump({"valid": False, "status": "error", "code": type(exc).__name__, "error": str(exc), "write_count": 0})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
