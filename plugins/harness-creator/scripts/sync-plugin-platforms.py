#!/usr/bin/env python3
# /// script
# name: sync-plugin-platforms
# purpose: 新規/既存 Claude plugin から Codex manifest と repo marketplace を決定論生成する。
# inputs:
#   - argv: --repo-root PATH (--plugin PLUGIN_DIR|--all) [--apply|--check]
# outputs:
#   - stdout: plugin別upsert/check receipt JSON
#   - exit: 0=整合 / 1=drift・検証違反 / 2=引数不正 / 3=入力・契約を読めない
# contexts: [C, E]
# network: false
# write-scope: <plugin>/.codex-plugin, <plugin>/hooks/hooks.json (inline hooks の初回正規化),
#              <repo>/.agents/plugins/marketplace.json
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Project both newly-created and existing Claude plugins onto Codex."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses msvcrt below.
    fcntl = None


class PlatformSyncError(Exception):
    pass


PLUGIN_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
OVERRIDE_FILE = ".codex-plugin-overrides.json"
OVERRIDABLE_FIELDS = {"interface", "skills", "hooks", "mcpServers", "apps"}
CODEX_HOOK_EVENTS = {
    "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact",
    "PostCompact", "UserPromptSubmit", "SubagentStop", "Stop",
    "SessionStart", "SubagentStart", "SessionEnd",
}


def _load_json(path: Path, *, missing=None) -> dict:
    if not path.is_file():
        if missing is not None:
            return missing
        raise PlatformSyncError(f"required JSON is missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlatformSyncError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PlatformSyncError(f"JSON root must be an object: {path}")
    return data


def _display_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-"))


def desired_codex_manifest(claude: dict, overrides: dict) -> dict:
    for field in ("name", "version", "description"):
        if not isinstance(claude.get(field), str) or not claude[field].strip():
            raise PlatformSyncError(f"Claude manifest requires non-empty {field}")
    if not PLUGIN_NAME_RE.fullmatch(claude["name"]):
        raise PlatformSyncError("Claude manifest name must be kebab-case")
    if not SEMVER_RE.fullmatch(claude["version"]):
        raise PlatformSyncError("Claude manifest version must be strict semver")
    if "author" in claude:
        author = claude["author"]
        if not isinstance(author, dict):
            raise PlatformSyncError("Claude manifest author must be an object")
        if not isinstance(author.get("name"), str) or not author["name"].strip():
            raise PlatformSyncError("Claude manifest author.name must be non-empty")
    unknown_overrides = sorted(set(overrides) - OVERRIDABLE_FIELDS)
    if unknown_overrides:
        raise PlatformSyncError(
            f"unsupported Codex override fields: {', '.join(unknown_overrides)}"
        )
    desired = {
        key: claude[key]
        for key in (
            "name", "version", "description", "author", "homepage", "repository",
            "license", "keywords", "skills", "hooks", "mcpServers", "apps",
        )
        if key in claude
    }
    author = claude.get("author") if isinstance(claude.get("author"), dict) else {}
    default_interface = {
        "displayName": _display_name(claude["name"]),
        "shortDescription": claude["description"][:120],
        "longDescription": claude["description"],
        "developerName": author.get("name", "Local developer"),
        "category": "Development Tools",
        "capabilities": ["Skills"],
        "defaultPrompt": [f"Help me use {_display_name(claude['name'])}."],
    }
    interface = dict(default_interface)
    if isinstance(claude.get("interface"), dict):
        interface.update(claude["interface"])
    override_interface = overrides.get("interface")
    if override_interface is not None and not isinstance(override_interface, dict):
        raise PlatformSyncError("Codex override interface must be an object")
    if isinstance(override_interface, dict):
        interface.update(override_interface)
    desired["interface"] = interface
    for field in OVERRIDABLE_FIELDS - {"interface"}:
        if field in overrides:
            if overrides[field] is None:
                desired.pop(field, None)
            else:
                desired[field] = overrides[field]
    return desired


def desired_claude_manifest(claude: dict) -> dict:
    """Use Claude's standard hooks/hooks.json auto-discovery exactly once.

    Codex still needs an explicit manifest pointer.  Inline Claude hooks are
    first materialized into the standard file by ``normalize_components`` and
    then removed from the Claude manifest to avoid double activation.
    """
    desired = json.loads(json.dumps(claude))
    hooks = desired.get("hooks")
    if isinstance(hooks, dict) or hooks == "./hooks/hooks.json":
        desired.pop("hooks", None)
    return desired


def _managed_marketplace_entry(*, name: str, source_path: str) -> dict:
    return {
        "name": name,
        "source": {"source": "local", "path": source_path},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Development Tools",
    }


def desired_marketplace(existing: dict, *, name: str, source_path: str, marketplace_name: str) -> dict:
    desired = json.loads(json.dumps(existing))
    plugins = desired.setdefault("plugins", [])
    if not isinstance(plugins, list) or not all(isinstance(item, dict) for item in plugins):
        raise PlatformSyncError("marketplace plugins must be an array of objects")
    desired["name"] = marketplace_name
    desired.setdefault("interface", {"displayName": _display_name(marketplace_name)})
    managed = _managed_marketplace_entry(name=name, source_path=source_path)
    next_plugins = []
    replaced = False
    for item in plugins:
        if item.get("name") != name:
            next_plugins.append(item)
        elif not replaced:
            next_plugins.append(managed)
            replaced = True
    if not replaced:
        next_plugins.append(managed)
    desired["plugins"] = next_plugins
    return desired


def desired_fleet_marketplace(
    existing: dict,
    *,
    plugin_names: list[str],
    marketplace_name: str,
) -> dict:
    """Reconcile every repo plugin while preserving unrelated marketplace entries."""
    desired = json.loads(json.dumps(existing))
    plugins = desired.setdefault("plugins", [])
    if not isinstance(plugins, list) or not all(isinstance(item, dict) for item in plugins):
        raise PlatformSyncError("marketplace plugins must be an array of objects")
    desired["name"] = marketplace_name
    desired.setdefault("interface", {"displayName": _display_name(marketplace_name)})
    managed_names = set(plugin_names)
    unmanaged = []
    for item in plugins:
        source = item.get("source")
        source_path = source.get("path") if isinstance(source, dict) else None
        is_repo_plugin = (
            isinstance(source, dict)
            and source.get("source") == "local"
            and isinstance(source_path, str)
            and re.fullmatch(r"\./plugins/[a-z][a-z0-9]*(?:-[a-z0-9]+)*", source_path)
        )
        if item.get("name") in managed_names or is_repo_plugin:
            continue
        unmanaged.append(item)
    desired["plugins"] = unmanaged + [
        _managed_marketplace_entry(
            name=name,
            source_path=f"./plugins/{name}",
        )
        for name in plugin_names
    ]
    return desired


def _text(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _component_path(plugin: Path, field: str, value: str) -> Path:
    if not value.startswith("./"):
        raise PlatformSyncError(f"{field} path must start with ./: {value}")
    target = (plugin / value).resolve()
    try:
        target.relative_to(plugin.resolve())
    except ValueError as exc:
        raise PlatformSyncError(f"{field} path escapes plugin root: {value}") from exc
    if not target.exists():
        raise PlatformSyncError(f"{field} path does not exist: {value}")
    return target


def _validate_codex_hook_document(document: dict, *, source: str) -> None:
    """Reject hook shapes Codex would skip or execute with unsafe semantics."""
    events = document.get("hooks", document)
    if not isinstance(events, dict):
        raise PlatformSyncError(f"{source}: hooks must be an object")
    for event, groups in events.items():
        if event not in CODEX_HOOK_EVENTS:
            raise PlatformSyncError(f"{source}: unsupported Codex hook event {event}")
        if not isinstance(groups, list):
            raise PlatformSyncError(f"{source}: {event} hook groups must be an array")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise PlatformSyncError(
                    f"{source}: {event} hook group must contain a hooks array"
                )
            matcher = group.get("matcher")
            if matcher is not None and not isinstance(matcher, str):
                raise PlatformSyncError(f"{source}: {event} matcher must be a string")
            for handler in group["hooks"]:
                if not isinstance(handler, dict):
                    raise PlatformSyncError(f"{source}: {event} hook handler must be an object")
                if handler.get("type") != "command":
                    raise PlatformSyncError(
                        f"{source}: only command hook handlers run in Codex"
                    )
                if not isinstance(handler.get("command"), str) or not handler["command"].strip():
                    raise PlatformSyncError(
                        f"{source}: {event} command hook requires a non-empty command"
                    )
                timeout = handler.get("timeout")
                if timeout is not None:
                    if (
                        isinstance(timeout, bool)
                        or not isinstance(timeout, (int, float))
                        or timeout <= 0
                    ):
                        raise PlatformSyncError(
                            f"{source}: {event} timeout must be positive seconds"
                        )
                    if event == "SessionEnd" and timeout > 3:
                        raise PlatformSyncError(
                            f"{source}: SessionEnd timeout cannot exceed Codex's 3 seconds; "
                            f"add {OVERRIDE_FILE} with a Codex-compatible hook definition"
                        )


def _normalize_hook_root_variables(document: dict) -> dict:
    """Prefer Codex's native root while retaining Claude Code compatibility."""
    normalized = json.loads(json.dumps(document))
    events = normalized.get("hooks", normalized)
    if not isinstance(events, dict):
        return normalized
    replacement = "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
    for groups in events.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                continue
            for handler in group["hooks"]:
                if not isinstance(handler, dict):
                    continue
                command = handler.get("command")
                if not isinstance(command, str):
                    continue
                if "${PLUGIN_ROOT" in command or "$PLUGIN_ROOT" in command:
                    continue
                handler["command"] = command.replace(
                    "${CLAUDE_PLUGIN_ROOT}", replacement
                ).replace("$CLAUDE_PLUGIN_ROOT", replacement)
    return normalized


def _validate_distribution_contract(plugin: Path) -> None:
    contract_path = plugin / "references" / "package-contract.json"
    if not contract_path.is_file():
        return
    contract = _load_json(contract_path)
    distribution = contract.get("codex_distribution")
    if distribution is None:
        return
    if not isinstance(distribution, dict):
        raise PlatformSyncError("codex_distribution must be an object")
    if distribution.get("distributable") is not True:
        raise PlatformSyncError("codex_distribution.distributable=true is required")
    if distribution.get("marketplace") != ".agents/plugins/marketplace.json":
        raise PlatformSyncError("codex_distribution.marketplace is unsupported")
    expected_source = f"./plugins/{plugin.name}"
    if distribution.get("source") != expected_source:
        raise PlatformSyncError(
            f"codex_distribution.source must be {expected_source}"
        )


def discover_codex_plugins(repo: Path) -> list[Path]:
    repo = repo.resolve()
    return [
        plugin.resolve()
        for plugin in sorted(
            (repo / "plugins").iterdir() if (repo / "plugins").is_dir() else []
        )
        if plugin.is_dir() and (plugin / ".claude-plugin" / "plugin.json").is_file()
    ]


def _assert_plugin_symlinks_confined(plugin: Path) -> None:
    root = plugin.resolve()
    for candidate in sorted(plugin.rglob("*")):
        if not candidate.is_symlink():
            continue
        try:
            candidate.resolve(strict=True).relative_to(root)
        except (OSError, ValueError) as exc:
            raise PlatformSyncError(
                f"symlink escapes plugin root: {candidate.relative_to(plugin)}"
            ) from exc


def _assert_output_path_confined(root: Path, path: Path) -> None:
    root = root.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise PlatformSyncError(f"output path escapes managed root: {path}") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if current.is_symlink():
                raise PlatformSyncError(f"output path uses symlink: {current}")


def normalize_components(
    plugin: Path,
    claude: dict,
    codex: dict,
    overrides: dict,
) -> tuple[dict, dict[Path, bytes]]:
    """Normalize product differences without inventing unsupported surfaces."""
    desired = dict(codex)
    extra_files: dict[Path, bytes] = {}
    if "skills" not in desired and (plugin / "skills").is_dir():
        desired["skills"] = "./skills/"
    hooks = claude.get("hooks")
    hooks_path = plugin / "hooks" / "hooks.json"
    if "hooks" in overrides:
        pass
    elif isinstance(hooks, dict):
        _validate_codex_hook_document(hooks, source="inline Claude hooks")
        desired["hooks"] = "./hooks/hooks.json"
        extra_files[hooks_path] = _text({
            "hooks": _normalize_hook_root_variables(hooks)
        }).encode()
    elif hooks == "./hooks/hooks.json":
        desired["hooks"] = "./hooks/hooks.json"
    elif hooks is None and hooks_path.is_file():
        desired["hooks"] = "./hooks/hooks.json"
    for field in ("skills", "apps"):
        value = desired.get(field)
        if value is not None and not isinstance(value, str):
            raise PlatformSyncError(f"{field} must be a plugin-relative path")
        if isinstance(value, str):
            _component_path(plugin, field, value)
    hook_value = desired.get("hooks")
    hook_paths = []
    inline_hook_documents = []
    if isinstance(hook_value, str):
        hook_paths = [hook_value]
    elif isinstance(hook_value, dict):
        inline_hook_documents = [hook_value]
    elif isinstance(hook_value, list):
        if all(isinstance(item, str) for item in hook_value):
            hook_paths = hook_value
        elif all(isinstance(item, dict) for item in hook_value):
            inline_hook_documents = hook_value
        else:
            raise PlatformSyncError("hooks array must contain only paths or only objects")
    elif hook_value is not None:
        raise PlatformSyncError("hooks must be paths or an inline hooks object")
    for document in inline_hook_documents:
        normalized = _normalize_hook_root_variables(document)
        _validate_codex_hook_document(normalized, source="Codex inline hooks")
        if isinstance(desired.get("hooks"), dict):
            desired["hooks"] = normalized
        elif isinstance(desired.get("hooks"), list):
            desired["hooks"] = [
                _normalize_hook_root_variables(item) for item in desired["hooks"]
            ]
    for value in hook_paths:
        if value == "./hooks/hooks.json" and hooks_path in extra_files:
            document = json.loads(extra_files[hooks_path])
        else:
            path = _component_path(plugin, "hooks", value)
            document = _load_json(path)
            normalized = _normalize_hook_root_variables(document)
            if normalized != document:
                _assert_output_path_confined(plugin, path)
                extra_files[path] = _text(normalized).encode()
                document = normalized
        _validate_codex_hook_document(document, source=f"Codex hooks {value}")
    mcp = desired.get("mcpServers")
    if isinstance(mcp, str):
        _component_path(plugin, "mcpServers", mcp)
    elif mcp is not None and not isinstance(mcp, dict):
        raise PlatformSyncError("mcpServers must be a plugin-relative path or object")
    interface = desired.get("interface", {})
    if isinstance(interface, dict):
        for field in ("composerIcon", "logo", "logoDark"):
            value = interface.get(field)
            if value is not None:
                if not isinstance(value, str):
                    raise PlatformSyncError(f"interface.{field} must be a path")
                _component_path(plugin, f"interface.{field}", value)
        screenshots = interface.get("screenshots")
        if screenshots is not None:
            if not isinstance(screenshots, list) or not all(isinstance(item, str) for item in screenshots):
                raise PlatformSyncError("interface.screenshots must be an array of paths")
            for value in screenshots:
                _component_path(plugin, "interface.screenshots", value)
    return desired, extra_files


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _apply_transaction(desired_files: dict[Path, bytes], drift: list[Path]) -> None:
    previous = {
        path: path.read_bytes() if path.is_file() else None
        for path in drift
    }
    applied: list[Path] = []
    try:
        for path in drift:
            _atomic_write(path, desired_files[path])
            applied.append(path)
    except BaseException:
        rollback_errors = []
        for path in reversed(applied):
            try:
                old_content = previous[path]
                if old_content is None:
                    path.unlink(missing_ok=True)
                else:
                    # Bypass a monkeypatched/failing writer during recovery.
                    fd, temporary = tempfile.mkstemp(prefix=path.name + ".rollback.", dir=path.parent)
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            stream.write(old_content)
                        os.replace(temporary, path)
                    except BaseException:
                        Path(temporary).unlink(missing_ok=True)
                        raise
            except BaseException as rollback_error:  # pragma: no cover - catastrophic filesystem failure.
                rollback_errors.append(f"{path}: {rollback_error}")
        if rollback_errors:
            raise PlatformSyncError(
                "platform sync failed and rollback was incomplete: " + "; ".join(rollback_errors)
            )
        raise


@contextmanager
def _repo_lock(repo: Path):
    digest = hashlib.sha256(str(repo.resolve()).encode()).hexdigest()[:20]
    lock_path = Path(tempfile.gettempdir()) / f"harness-plugin-sync-{digest}.lock"
    with lock_path.open("a+b") as stream:
        if fcntl is not None:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        elif os.name == "nt":  # pragma: no cover - exercised on Windows CI only.
            import msvcrt

            stream.seek(0)
            if stream.read(1) == b"":
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - unsupported platforms fail closed.
            raise PlatformSyncError("platform sync requires an inter-process file lock")
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            elif os.name == "nt":  # pragma: no cover
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _validate_plugin_location(repo: Path, plugin: Path) -> None:
    try:
        relative = plugin.relative_to(repo / "plugins")
    except ValueError as exc:
        raise PlatformSyncError(
            "plugin must be inside the repository plugins directory"
        ) from exc
    if len(relative.parts) != 1:
        raise PlatformSyncError(
            "plugin must be a direct child of the repository plugins directory"
        )


def _resolve_marketplace_name(
    *,
    repo: Path,
    existing_marketplace: dict,
    marketplace_name: str | None,
) -> str:
    fallback = re.sub(r"[^a-z0-9]+", "-", repo.name.lower()).strip("-")
    resolved = marketplace_name or existing_marketplace.get("name") or fallback
    if not isinstance(resolved, str) or not PLUGIN_NAME_RE.fullmatch(resolved):
        raise PlatformSyncError("marketplace name must be non-empty kebab-case")
    return resolved


def _desired_plugin_files(repo: Path, plugin: Path) -> dict[Path, bytes]:
    _validate_plugin_location(repo, plugin)
    claude_path = plugin / ".claude-plugin" / "plugin.json"
    codex_path = plugin / ".codex-plugin" / "plugin.json"
    _validate_distribution_contract(plugin)
    _assert_plugin_symlinks_confined(plugin)
    _assert_output_path_confined(plugin, claude_path)
    _assert_output_path_confined(plugin, codex_path)
    claude = _load_json(claude_path)
    if claude.get("name") != plugin.name:
        raise PlatformSyncError("Claude manifest name must match plugin directory")
    overrides = _load_json(plugin / OVERRIDE_FILE, missing={})
    claude_manifest = desired_claude_manifest(claude)
    codex_manifest, component_files = normalize_components(
        plugin,
        claude,
        desired_codex_manifest(claude_manifest, overrides),
        overrides,
    )
    desired_files = {
        claude_path: _text(claude_manifest).encode(),
        codex_path: _text(codex_manifest).encode(),
    }
    desired_files.update(component_files)
    return desired_files


def run(
    *,
    repo: Path,
    plugin: Path,
    intent: str | None,
    mode: str,
    marketplace_name: str | None,
) -> tuple[dict, int]:
    repo, plugin = repo.resolve(), plugin.resolve()
    if intent not in {None, "create", "update"}:
        raise PlatformSyncError("intent must be create or update")
    if mode not in {"apply", "check"}:
        raise PlatformSyncError("mode must be apply or check")
    _validate_plugin_location(repo, plugin)

    with _repo_lock(repo):
        marketplace_path = repo / ".agents" / "plugins" / "marketplace.json"
        _assert_output_path_confined(repo, marketplace_path)
        existing_marketplace = _load_json(marketplace_path, missing={})
        resolved_marketplace_name = _resolve_marketplace_name(
            repo=repo,
            existing_marketplace=existing_marketplace,
            marketplace_name=marketplace_name,
        )
        source_path = f"./plugins/{plugin.name}"

        desired_files = _desired_plugin_files(repo, plugin)
        desired_files[marketplace_path] = _text(desired_marketplace(
                existing_marketplace,
                name=plugin.name,
                source_path=source_path,
                marketplace_name=resolved_marketplace_name,
            )).encode()
        drift_paths = [
            path
            for path, content in desired_files.items()
            if not path.is_file() or path.read_bytes() != content or path.is_symlink()
        ]
        drift = [str(path.relative_to(repo)) for path in drift_paths]
        report = {
            "status": "drift" if drift else "noop",
            "operation": "upsert",
            "intent": intent or "auto",
            "paths": drift,
        }
        if mode == "apply":
            _apply_transaction(desired_files, drift_paths)
            report["status"] = "synced" if drift else "noop"
            return report, 0
        return report, 1 if drift else 0


def run_all(
    *,
    repo: Path,
    mode: str,
    marketplace_name: str | None,
) -> tuple[dict, int]:
    repo = repo.resolve()
    if mode not in {"apply", "check"}:
        raise PlatformSyncError("mode must be apply or check")
    with _repo_lock(repo):
        plugins = discover_codex_plugins(repo)
        marketplace_path = repo / ".agents" / "plugins" / "marketplace.json"
        _assert_output_path_confined(repo, marketplace_path)
        existing_marketplace = _load_json(marketplace_path, missing={})
        resolved_marketplace_name = _resolve_marketplace_name(
            repo=repo,
            existing_marketplace=existing_marketplace,
            marketplace_name=marketplace_name,
        )
        desired_files: dict[Path, bytes] = {}
        plugin_paths: dict[str, set[Path]] = {}
        for plugin in plugins:
            planned = _desired_plugin_files(repo, plugin)
            desired_files.update(planned)
            plugin_paths[plugin.name] = set(planned)
        desired_files[marketplace_path] = _text(desired_fleet_marketplace(
            existing_marketplace,
            plugin_names=[plugin.name for plugin in plugins],
            marketplace_name=resolved_marketplace_name,
        )).encode()
        drift_paths = [
            path
            for path, content in desired_files.items()
            if not path.is_file() or path.read_bytes() != content or path.is_symlink()
        ]
        drift_set = set(drift_paths)
        results = []
        for plugin in plugins:
            plugin_drift = sorted(plugin_paths[plugin.name] & drift_set)
            results.append({
                "plugin": plugin.name,
                "status": "drift" if plugin_drift else "noop",
                "operation": "upsert",
                "intent": "auto",
                "paths": [str(path.relative_to(repo)) for path in plugin_drift],
            })
        if mode == "apply":
            _apply_transaction(desired_files, drift_paths)
            for result in results:
                if result["status"] == "drift":
                    result["status"] = "synced"
            return {
                "status": "synced" if drift_paths else "noop",
                "operation": "fleet-reconcile",
                "paths": [str(path.relative_to(repo)) for path in drift_paths],
                "plugins": results,
            }, 0
        return {
            "status": "drift" if drift_paths else "ok",
            "operation": "fleet-reconcile",
            "paths": [str(path.relative_to(repo)) for path in drift_paths],
            "plugins": results,
        }, 1 if drift_paths else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument("--plugin", type=Path)
    targets.add_argument(
        "--all",
        action="store_true",
        help="Check/apply every direct plugins/* directory with a Claude plugin manifest.",
    )
    parser.add_argument(
        "--intent",
        choices=("create", "update"),
        help="Deprecated context label; projection is one idempotent upsert for both lifecycles.",
    )
    parser.add_argument(
        "--marketplace-name",
        help="Marketplace identity. Existing marketplace name or repository directory name is the default.",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_const", const="apply", dest="mode")
    modes.add_argument("--check", action="store_const", const="check", dest="mode")
    parser.set_defaults(mode="check")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.all:
            report, code = run_all(
                repo=args.repo_root,
                mode=args.mode,
                marketplace_name=args.marketplace_name,
            )
        else:
            report, code = run(
                repo=args.repo_root,
                plugin=args.plugin,
                intent=args.intent,
                mode=args.mode,
                marketplace_name=args.marketplace_name,
            )
    except PlatformSyncError as exc:
        report, code = {"status": "invalid", "error": str(exc)}, 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
