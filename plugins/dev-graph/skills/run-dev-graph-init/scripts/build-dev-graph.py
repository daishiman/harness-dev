#!/usr/bin/env python3
# /// script
# name: build-dev-graph
# purpose: Canonically scaffold and verify one repository-local dev-graph installation and its inline goal anchor.
# inputs: ["argv: --repo-root PATH --hook-source plugin|project-fallback [--dry-run] [--rollback-project-hooks]"]
# outputs: ["stdout: JSON plan/receipt with config, graph, template, hook, auth, idempotence, and goal-seek readiness"]
# requires-python = ">=3.10"
# dependencies: [../../../scripts/resolve-repo-context.py, ../../../scripts/validate-graph-schema.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: selected repository content roots, .dev-graph/, .claude/settings.json, .claude/dev-graph-plugin, and eval-log/run-dev-graph-init-*
# ///
"""C01 deterministic repository initializer; no model-authored config or receipt."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_SCRIPTS = PLUGIN_ROOT / "scripts"
TEMPLATES = PLUGIN_ROOT / "templates"
SCHEMA = PLUGIN_ROOT / "schemas" / "repo-config.schema.json"
RESOLVER = PLUGIN_SCRIPTS / "resolve-repo-context.py"
GRAPH_VALIDATOR = PLUGIN_SCRIPTS / "validate-graph-schema.py"
GRAPH_SCHEMA = PLUGIN_ROOT / "schemas" / "graph-node.schema.json"
PLUGIN_HOOKS = PLUGIN_ROOT / "hooks" / "hooks.json"
PROJECT_HOOKS = TEMPLATES / "claude-settings.example.json"
PROJECT_SETTINGS = Path(".claude/settings.json")
PROJECT_SETTINGS_LOCAL = Path(".claude/settings.local.json")
PROJECT_PLUGIN_LINK = Path(".claude/dev-graph-plugin")
PROJECT_HOOK_MANIFEST = Path(".dev-graph/state/project-hook-rollback.json")
DEFAULT_GOAL = (
    "symlinkで配布された任意の呼出し元repository/worktreeを解決し、そのrepo内だけに6 content root "
    "(issues/tasks/specs/architecture/features/docs)、repo-local config/template/stateと選択式Claude hook配線を"
    "冪等初期化できる状態になっている"
)
GOAL_FILES = {
    "goal": "eval-log/run-dev-graph-init-goal-spec.json",
    "progress": "eval-log/run-dev-graph-init-progress.json",
    "intermediate": "eval-log/run-dev-graph-init-intermediate.jsonl",
}


class ContractError(RuntimeError):
    """Fail-closed input/readiness error."""


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON object required: {path}")
    return value


def _absolute_stored_paths(value: Any, location: str = "$") -> list[str]:
    if isinstance(value, dict):
        return [
            finding
            for key, child in value.items()
            for finding in _absolute_stored_paths(child, f"{location}.{key}")
        ]
    if isinstance(value, list):
        return [
            finding
            for index, child in enumerate(value)
            for finding in _absolute_stored_paths(child, f"{location}[{index}]")
        ]
    if isinstance(value, str) and (Path(value).is_absolute() or PureWindowsPath(value).is_absolute()):
        return [location]
    return []


def _context(repo_root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(RESOLVER), "--repo-root", str(repo_root), "--mode", "write"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContractError(f"C24 repository context failed: {completed.stderr.strip() or completed.stdout.strip()}")
    try:
        receipt = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("C24 repository context returned invalid JSON") from exc
    if not isinstance(receipt, dict) or Path(str(receipt.get("repo_root", ""))).resolve() != repo_root:
        raise ContractError("C24 repository context identity mismatch")
    if Path(str((receipt.get("content_roots") or {}).get("repository", ""))).resolve() != repo_root:
        raise ContractError("C24 content authority differs from repository root")
    if (receipt.get("root_trust_evidence") or {}).get("claude_project_dir_verified") is not True:
        raise ContractError("C24 CLAUDE_PROJECT_DIR differs from the selected repository root")
    if Path(str(receipt.get("plugin_source", ""))).resolve() != PLUGIN_ROOT:
        raise ContractError("C24 plugin source differs from the canonical initializer source")
    return receipt


def _safe_slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not slug or not slug[0].isalpha():
        slug = fallback
    return slug


def _desired_config(context: dict[str, Any], hook_source: str) -> dict[str, Any]:
    template = _load_object(TEMPLATES / "repo-config.example.json")
    repository_id = str(context["repository_id"])
    if repository_id.startswith("github:"):
        issue_repository = repository_id.removeprefix("github:")
        owner, repository = issue_repository.split("/", 1)
    else:
        repository = _safe_slug(Path(str(context["repo_root"])).name, "repository")
        owner = "local"
        issue_repository = f"{owner}/{repository}"
    template["repository_id"] = repository_id
    template["github"]["enabled"] = False
    template["github"]["issue_repository"] = issue_repository
    template["github"]["projects"][0]["owner_login"] = owner
    template["execution_tracker"]["beads"]["issue_prefix"] = _safe_slug(repository, "devgraph")
    template["claude_hooks"]["source"] = "project" if hook_source == "project-fallback" else "plugin"
    return template


def _repo_relative(raw: Any, label: str) -> Path:
    """Return one unambiguous POSIX repository-relative path."""
    if not isinstance(raw, str) or not raw or "\x00" in raw or "\\" in raw:
        raise ContractError(f"{label} must be a non-empty POSIX repository-relative path")
    windows = PureWindowsPath(raw)
    relative = Path(raw)
    if (
        relative.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or raw.startswith("/")
        or raw.endswith("/")
        or "//" in raw
        or raw.startswith("./")
        or "/./" in raw
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ContractError(f"{label} is ambiguous or escapes repository authority: {raw}")
    return relative


def _contained_target(root: Path, raw: Any, label: str) -> Path:
    """Preflight every existing segment and reject symlink-mediated init targets."""
    relative = _repo_relative(raw, label)
    candidate = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            try:
                current.resolve(strict=True)
            except OSError as exc:
                raise ContractError(f"broken content symlink for {label}: {current}: {exc}") from exc
            raise ContractError(f"init target must not traverse a symlink: {label}={current}")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except (OSError, ValueError) as exc:
        raise ContractError(f"{label} escapes repository authority: {raw}") from exc
    return candidate


def _effective_config(
    root: Path, context: dict[str, Any], hook_source: str,
) -> tuple[dict[str, Any], str]:
    """Select the validated repository config, never a parallel default copy."""
    config_path = root / ".dev-graph/config.json"
    desired = _desired_config(context, hook_source)
    if config_path.exists() or config_path.is_symlink():
        if config_path.is_symlink() or not config_path.is_file():
            raise ContractError("existing repo config must be a non-symlink regular file")
        config = _load_object(config_path)
        source = "repository"
    else:
        config = desired
        source = "generated-default"
    findings = _schema_findings(config)
    if findings:
        prefix = "existing" if source == "repository" else "generated"
        raise ContractError(f"{prefix} repo config violates canonical schema: {findings}")
    if config.get("repository_id") != context.get("repository_id"):
        raise ContractError("repo config repository_id does not match the C24 repository identity")
    expected_source = "project" if hook_source == "project-fallback" else "plugin"
    if (config.get("claude_hooks") or {}).get("source") != expected_source:
        raise ContractError(f"existing repo config hook source conflicts with --hook-source {hook_source}")
    return config, source


def _layout(root: Path, config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Resolve and preflight every path used by planning, writes, and readiness."""
    content = {
        key: _contained_target(root, value, f"content_roots.{key}")
        for key, value in config["content_roots"].items()
    }
    if len(set(content.values())) != len(content):
        raise ContractError("content_roots must resolve to distinct repository paths")
    for key, path in content.items():
        for other_key, other in content.items():
            if key != other_key and path.is_relative_to(other):
                raise ContractError(f"content_roots overlap ambiguously: {key} within {other_key}")
    local = {
        key: _contained_target(root, value, f"local_state.{key}")
        for key, value in config["local_state"].items()
    }
    if len(set(local.values())) != len(local):
        raise ContractError("local_state paths must resolve to distinct repository paths")
    for key, path in content.items():
        reported = Path(str((context.get("content_roots") or {}).get(key, "")))
        if reported.resolve(strict=False) != path.resolve(strict=False):
            raise ContractError(f"C24 content path differs from effective_config: {key}")
    for key, path in local.items():
        reported = Path(str((context.get("local_state_paths") or {}).get(key, "")))
        if reported.resolve(strict=False) != path.resolve(strict=False):
            raise ContractError(f"C24 local-state path differs from effective_config: {key}")
    graph = local["graph"]
    directories = [*content.values(), local["cache"], local["locks"], graph.parent, root / ".dev-graph/templates"]
    fixed_files = [root / ".dev-graph/config.json", *[root / relative for relative in GOAL_FILES.values()]]
    receipt = graph.parent / "init-receipt.json"
    fixed_files.append(receipt)
    file_targets = [graph, *fixed_files]
    if len(set(file_targets)) != len(file_targets):
        raise ContractError("effective_config maps graph onto a reserved init file")
    if any(path in directories for path in file_targets):
        raise ContractError("effective_config maps an init file onto a required directory")
    for directory in directories:
        relative = directory.relative_to(root).as_posix()
        _contained_target(root, relative, f"init directory {relative}")
        if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
            raise ContractError(f"init target directory is invalid: {relative}")
    for path in file_targets:
        relative = path.relative_to(root).as_posix()
        _contained_target(root, relative, f"init file {relative}")
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file():
                raise ContractError(f"init target file is invalid: {relative}")
    for source in sorted(path for path in TEMPLATES.iterdir() if path.is_file()):
        destination = root / ".dev-graph/templates" / source.name
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file():
                raise ContractError(f"template target is invalid: {destination.relative_to(root).as_posix()}")
    return {"content": content, "local": local, "graph": graph, "receipt": receipt, "directories": directories}


def _config_evidence(config: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "source": source,
        "path": ".dev-graph/config.json",
        "sha256": hashlib.sha256(_json_bytes(config)).hexdigest(),
        "effective_config": config,
    }


def _schema_findings(config: dict[str, Any]) -> list[str]:
    schema = _load_object(SCHEMA)
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except ImportError:
        sys.path.insert(0, str(PLUGIN_SCRIPTS))
        spec = importlib.util.spec_from_file_location("dev_graph_schema_validator", GRAPH_VALIDATOR)
        if spec is None or spec.loader is None:
            raise ContractError("cannot load canonical schema validator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return [f"{path}: {detail}" for path, detail in module._schema_fallback(config, schema, schema)]
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ContractError(f"invalid repo-config schema: {exc}") from exc
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(
            Draft202012Validator(schema).iter_errors(config),
            key=lambda e: (tuple(str(part) for part in e.absolute_path), e.message),
        )
    ]


def _gh_cli_auth() -> dict[str, Any]:
    executable = shutil.which("gh")
    if executable is None:
        return {"available": False, "authenticated": False, "status": "unavailable", "exit_code": None}
    env = dict(os.environ)
    env["GH_PROMPT_DISABLED"] = "1"
    try:
        completed = subprocess.run(
            [executable, "auth", "status"], text=True, capture_output=True, check=False, timeout=10, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": True, "authenticated": False, "status": "unknown", "exit_code": None}
    authenticated = completed.returncode == 0
    return {
        "available": True,
        "authenticated": authenticated,
        "status": "authenticated" if authenticated else "unauthenticated",
        "exit_code": completed.returncode,
    }


def _canonical_project_hooks() -> dict[str, list[dict[str, Any]]]:
    plugin = _load_object(PLUGIN_HOOKS).get("hooks")
    project = _load_object(PROJECT_HOOKS).get("hooks")
    if not isinstance(plugin, dict) or not isinstance(project, dict):
        raise ContractError("C25 canonical hook assets must contain a hooks object")
    translated = json.loads(
        json.dumps(plugin).replace("${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PROJECT_DIR}/.claude/dev-graph-plugin")
    )
    if translated != project:
        raise ContractError("C25 plugin and project-fallback hook assets have drifted")
    if set(project) != {"SessionStart", "PreToolUse", "PostToolUse", "TaskCompleted"}:
        raise ContractError("C25 project-fallback does not cover every required event")
    if not all(isinstance(groups, list) and groups for groups in project.values()):
        raise ContractError("C25 project-fallback event groups must be non-empty arrays")
    return project


def _load_optional_object(path: Path) -> tuple[dict[str, Any], bool, bytes | None]:
    if not path.exists():
        return {}, False, None
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"C25 settings target must be a regular file: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"C25 settings JSON is invalid: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"C25 settings must be a JSON object: {path}")
    return value, True, raw


def _dev_graph_group(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return any(
        marker in encoded
        for marker in (
            ".claude/dev-graph-plugin",
            "/hooks/guard-graph-schema.py",
            "/hooks/reconcile-task-lifecycle.py",
        )
    )


def _plugin_enabled(value: Any) -> bool:
    if isinstance(value, dict):
        return any("dev-graph" in str(key).lower() and enabled is not False for key, enabled in value.items())
    if isinstance(value, list):
        return any("dev-graph" in str(item).lower() for item in value)
    return False


def _effective_plugin_evidence(root: Path, settings: dict[str, Any], local: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    configured_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if configured_root:
        try:
            if Path(configured_root).expanduser().resolve() == PLUGIN_ROOT:
                evidence.append("env:CLAUDE_PLUGIN_ROOT")
        except OSError:
            pass
    for relative, value in ((PROJECT_SETTINGS, settings), (PROJECT_SETTINGS_LOCAL, local)):
        if _plugin_enabled(value.get("enabledPlugins")):
            evidence.append(f"{relative.as_posix()}:enabledPlugins")
        hooks = value.get("hooks")
        if isinstance(hooks, dict):
            for groups in hooks.values():
                if isinstance(groups, list) and any(
                    _dev_graph_group(group) and "${CLAUDE_PLUGIN_ROOT}" in json.dumps(group)
                    for group in groups
                ):
                    evidence.append(f"{relative.as_posix()}:plugin-hook-command")
                    break
    return sorted(set(evidence))


def _policy_diagnostics(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    settings, _, _ = _load_optional_object(root / PROJECT_SETTINGS)
    local, _, _ = _load_optional_object(root / PROJECT_SETTINGS_LOCAL)
    for relative, value in ((PROJECT_SETTINGS, settings), (PROJECT_SETTINGS_LOCAL, local)):
        if value.get("disableAllHooks") is True:
            raise ContractError(f"C25 hooks are disabled by {relative.as_posix()}:disableAllHooks")
        if value.get("allowManagedHooksOnly") is True:
            raise ContractError(f"C25 project hooks are blocked by {relative.as_posix()}:allowManagedHooksOnly")
    return settings, local


def _project_hook_plan(root: Path) -> dict[str, Any]:
    settings, local = _policy_diagnostics(root)
    evidence = _effective_plugin_evidence(root, settings, local)
    if evidence:
        raise ContractError(f"C25 effective plugin hook detected; project-fallback refused: {evidence}")
    settings_path = root / PROJECT_SETTINGS
    _, settings_existed, settings_before = _load_optional_object(settings_path)
    canonical = _canonical_project_hooks()
    merged = json.loads(json.dumps(settings))
    hooks_existed = "hooks" in settings
    hooks = merged.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ContractError("C25 settings hooks must be an object")
    events_existed: dict[str, bool] = {}
    added: dict[str, list[dict[str, Any]]] = {}
    preserved = json.loads(json.dumps(settings))
    for event, desired_groups in canonical.items():
        events_existed[event] = event in hooks
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ContractError(f"C25 settings hooks.{event} must be an array")
        for group in groups:
            if _dev_graph_group(group) and group not in desired_groups:
                raise ContractError(f"C25 conflicting dev-graph hook override in hooks.{event}")
        for desired in desired_groups:
            count = sum(group == desired for group in groups)
            if count > 1:
                raise ContractError(f"C25 duplicate dev-graph hook in hooks.{event}")
            if count == 0:
                groups.append(desired)
                added.setdefault(event, []).append(desired)
    for key, value in preserved.items():
        if key != "hooks" and merged.get(key) != value:
            raise ContractError(f"C25 deep merge changed existing settings key: {key}")
    before_hooks = preserved.get("hooks", {})
    if isinstance(before_hooks, dict):
        for event, groups in before_hooks.items():
            if not isinstance(groups, list) or hooks.get(event, [])[: len(groups)] != groups:
                raise ContractError(f"C25 deep merge changed existing hook values: {event}")
    settings_after = _json_bytes(merged)
    settings_changed = merged != settings

    link = root / PROJECT_PLUGIN_LINK
    if link.exists() or link.is_symlink():
        if not link.is_symlink():
            raise ContractError("C25 project plugin link is occupied by a non-symlink")
        try:
            if link.resolve(strict=True) != PLUGIN_ROOT:
                raise ContractError("C25 project plugin link resolves to a different plugin source")
        except OSError as exc:
            raise ContractError(f"C25 project plugin link is broken: {exc}") from exc
        link_created = False
    else:
        link_created = True

    manifest_path = root / PROJECT_HOOK_MANIFEST
    manifest = {
        "schema_version": "1.0.0",
        "owner": "C25/run-dev-graph-init",
        "settings_path": PROJECT_SETTINGS.as_posix(),
        "settings_existed": settings_existed,
        "hooks_key_existed": hooks_existed,
        "events_existed": events_existed,
        "added_hooks": added,
        "project_plugin_link": PROJECT_PLUGIN_LINK.as_posix(),
        "plugin_link_created": link_created,
        "canonical_hooks_sha256": _digest(PLUGIN_HOOKS),
    }
    if manifest_path.exists():
        existing_manifest = _load_object(manifest_path)
        if existing_manifest.get("owner") != manifest["owner"]:
            raise ContractError("C25 rollback manifest owner mismatch")
        if existing_manifest.get("settings_path") != PROJECT_SETTINGS.as_posix():
            raise ContractError("C25 rollback manifest settings path mismatch")
        if existing_manifest.get("project_plugin_link") != PROJECT_PLUGIN_LINK.as_posix():
            raise ContractError("C25 rollback manifest plugin link mismatch")
        if existing_manifest.get("canonical_hooks_sha256") != _digest(PLUGIN_HOOKS):
            raise ContractError("C25 rollback manifest is stale for the canonical hooks")
        manifest_changed = False
        manifest = existing_manifest
    else:
        manifest_changed = True
    planned = []
    if settings_changed:
        planned.append(PROJECT_SETTINGS.as_posix())
    if link_created:
        planned.append(PROJECT_PLUGIN_LINK.as_posix())
    if manifest_changed:
        planned.append(PROJECT_HOOK_MANIFEST.as_posix())
    return {
        "settings_path": settings_path,
        "settings_before": settings_before,
        "settings_after": settings_after,
        "settings_changed": settings_changed,
        "link": link,
        "link_created": link_created,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "manifest_changed": manifest_changed,
        "planned_changes": planned,
        "receipt": {
            "mode": "project-fallback",
            "effective_plugin_evidence": [],
            "required_events": sorted(canonical),
            "added_hook_count": sum(len(groups) for groups in added.values()),
            "duplicate_count": 0,
            "existing_value_digest_changes": 0,
            "rollback_manifest": PROJECT_HOOK_MANIFEST.as_posix(),
            "project_plugin_link": PROJECT_PLUGIN_LINK.as_posix(),
        },
    }


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _apply_project_hook_plan(plan: dict[str, Any], changed: list[Path]) -> None:
    link = plan["link"]
    if plan["link_created"]:
        link.parent.mkdir(parents=True, exist_ok=True)
        relative_target = os.path.relpath(PLUGIN_ROOT, link.parent)
        link.symlink_to(relative_target, target_is_directory=True)
        changed.append(link)
    if plan["settings_changed"]:
        _atomic_write(plan["settings_path"], plan["settings_after"])
        changed.append(plan["settings_path"])
    if plan["manifest_changed"]:
        _create(plan["manifest_path"], _json_bytes(plan["manifest"]), changed)


def _restore_project_hook_plan(plan: dict[str, Any]) -> None:
    if plan["manifest_changed"]:
        try:
            plan["manifest_path"].unlink()
        except FileNotFoundError:
            pass
    if plan["settings_changed"]:
        if plan["settings_before"] is None:
            try:
                plan["settings_path"].unlink()
            except FileNotFoundError:
                pass
        else:
            _atomic_write(plan["settings_path"], plan["settings_before"])
    if plan["link_created"]:
        try:
            plan["link"].unlink()
        except FileNotFoundError:
            pass


def rollback_project_hooks(repo_root: Path, dry_run: bool) -> dict[str, Any]:
    root = repo_root.expanduser().resolve(strict=True)
    context = _context(root)
    manifest_path = root / PROJECT_HOOK_MANIFEST
    manifest = _load_object(manifest_path)
    if manifest.get("owner") != "C25/run-dev-graph-init":
        raise ContractError("C25 rollback manifest owner mismatch")
    settings_path = root / str(manifest.get("settings_path", ""))
    if settings_path != root / PROJECT_SETTINGS:
        raise ContractError("C25 rollback settings path mismatch")
    settings, _, before = _load_optional_object(settings_path)
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        raise ContractError("C25 rollback cannot find settings hooks")
    removed = 0
    for event, added_groups in (manifest.get("added_hooks") or {}).items():
        groups = hooks.get(event)
        if not isinstance(groups, list) or not isinstance(added_groups, list):
            raise ContractError(f"C25 rollback manifest/event is invalid: {event}")
        for added in added_groups:
            matches = [index for index, group in enumerate(groups) if group == added]
            if len(matches) != 1:
                raise ContractError(f"C25 rollback hook identity is stale or duplicated: {event}")
            groups.pop(matches[0])
            removed += 1
        if not manifest.get("events_existed", {}).get(event) and not groups:
            hooks.pop(event, None)
    if not manifest.get("hooks_key_existed") and not hooks:
        settings.pop("hooks", None)
    after = _json_bytes(settings)
    remove_settings = not manifest.get("settings_existed") and settings == {}
    link = root / str(manifest.get("project_plugin_link", ""))
    remove_link = bool(manifest.get("plugin_link_created"))
    if remove_link:
        if not link.is_symlink() or link.resolve(strict=True) != PLUGIN_ROOT:
            raise ContractError("C25 rollback project plugin link identity mismatch")
    planned = [PROJECT_HOOK_MANIFEST.as_posix()]
    if before != after or remove_settings:
        planned.append(PROJECT_SETTINGS.as_posix())
    if remove_link:
        planned.append(PROJECT_PLUGIN_LINK.as_posix())
    if not dry_run:
        if remove_settings:
            settings_path.unlink()
        elif before != after:
            _atomic_write(settings_path, after)
        if remove_link:
            link.unlink()
        manifest_path.unlink()
    return {
        "schema_version": "1.0.0",
        "owner": "C25/run-dev-graph-init",
        "status": "rollback-preview" if dry_run else "rolled-back",
        "repository_id": context["repository_id"],
        "planned_changes": sorted(planned),
        "write_count": 0 if dry_run else len(set(planned)),
        "removed_hook_count": removed,
    }


def _desired_goal_records(goal: str, evidence: list[str]) -> dict[str, bytes]:
    goal_hash = hashlib.sha256(goal.encode("utf-8")).hexdigest()
    goal_spec = {"schema_version": "1.0.0", "original_goal": goal}
    progress = {
        "schema_version": "1.0.0",
        "skill": "run-dev-graph-init",
        "original_goal": goal,
        "original_goal_hash": goal_hash,
        "checklist": {"status": "pass", "evidence": evidence, "blockers": []},
    }
    intermediate = {
        "original_goal": goal,
        "original_goal_hash": goal_hash,
        "current_goal_snapshot": goal,
        "delta_from_original": "none",
        "merged_directive_for_next": "all checklist items verified; stop",
        "drift_signal": False,
    }
    return {
        GOAL_FILES["goal"]: _json_bytes(goal_spec),
        GOAL_FILES["progress"]: _json_bytes(progress),
        GOAL_FILES["intermediate"]: (json.dumps(intermediate, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"),
    }


def _verify_goal_records(root: Path, expected_goal: str) -> dict[str, Any]:
    goal = _load_object(root / GOAL_FILES["goal"])
    progress = _load_object(root / GOAL_FILES["progress"])
    original = goal.get("original_goal")
    if not isinstance(original, str) or not original:
        raise ContractError("goal-spec original_goal must be non-empty")
    if original != expected_goal:
        raise ContractError("goal-spec original_goal conflicts with the requested goal")
    expected = hashlib.sha256(original.encode("utf-8")).hexdigest()
    try:
        rows = [
            json.loads(line)
            for line in (root / GOAL_FILES["intermediate"]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid goal-seek intermediate record: {exc}") from exc
    required = {
        "original_goal", "original_goal_hash", "current_goal_snapshot", "delta_from_original",
        "merged_directive_for_next", "drift_signal",
    }
    if not rows:
        raise ContractError("goal-seek intermediate record is empty")
    for row in rows:
        if not isinstance(row, dict) or not required.issubset(row):
            raise ContractError("goal-seek intermediate record omits required keys")
        if row["original_goal"] != original or row["original_goal_hash"] != expected:
            raise ContractError("goal-seek original goal/hash mismatch")
    if progress.get("original_goal") != original or progress.get("original_goal_hash") != expected:
        raise ContractError("goal-seek progress goal/hash mismatch")
    if (progress.get("checklist") or {}).get("status") != "pass":
        raise ContractError("goal-seek progress checklist is not pass")
    return {"valid": True, "original_goal_hash": expected, "iterations": len(rows)}


def _graph_readiness(root: Path, graph: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(GRAPH_VALIDATOR), "--graph", str(graph), "--repo-root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContractError(f"C11 graph validation failed: {completed.stdout.strip() or completed.stderr.strip()}")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("C11 graph validation returned invalid JSON") from exc
    if not isinstance(report, dict) or report.get("valid") is not True:
        raise ContractError("C11 graph validation did not return valid=true")
    reported_schema = report.get("schema")
    if not isinstance(reported_schema, str) or Path(reported_schema).resolve() != GRAPH_SCHEMA.resolve():
        raise ContractError("C11 graph validation used an unexpected schema")
    report["schema"] = GRAPH_SCHEMA.relative_to(PLUGIN_ROOT).as_posix()
    return report


def _create(path: Path, content: bytes, created: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        return
    created.append(path)


def _plan(
    root: Path, config: dict[str, Any], layout: dict[str, Any], goal: str,
) -> tuple[list[Path], dict[Path, bytes], list[str], list[str]]:
    directories = list(layout["directories"])
    evidence = [
        ".dev-graph/config.json",
        layout["graph"].relative_to(root).as_posix(),
        ".dev-graph/templates/template-contract.json",
    ]
    files: dict[Path, bytes] = {
        root / ".dev-graph/config.json": _json_bytes(config),
        layout["graph"]: _json_bytes({"schema_version": "1.0.0", "graph_revision": 0, "nodes": []}),
    }
    for source in sorted(path for path in TEMPLATES.iterdir() if path.is_file()):
        files[root / ".dev-graph/templates" / source.name] = source.read_bytes()
    files.update({root / relative: content for relative, content in _desired_goal_records(goal, evidence).items()})
    migration_preview: list[str] = []
    preserved: list[str] = []
    for path, content in files.items():
        if not path.exists():
            continue
        relative = path.relative_to(root).as_posix()
        preserved.append(relative)
        if path.parent == root / ".dev-graph/templates" and path.read_bytes() != content:
            migration_preview.append(relative)
    return directories, files, sorted(preserved), sorted(migration_preview)


def initialize(repo_root: Path, hook_source: str, goal: str, dry_run: bool) -> dict[str, Any]:
    root = repo_root.expanduser().resolve(strict=True)
    context = _context(root)
    config, config_source = _effective_config(root, context, hook_source)
    layout = _layout(root, config, context)
    config_evidence = _config_evidence(config, config_source)
    gh_cli_auth = _gh_cli_auth()
    directories, files, preserved, migration_preview = _plan(root, config, layout, goal)
    hook_plan = _project_hook_plan(root) if hook_source == "project-fallback" else None
    if hook_plan is not None:
        directories.append(root / ".claude")
        hook_report = hook_plan["receipt"]
    else:
        hook_report = {
            "mode": "plugin",
            "effective_source": "hooks/hooks.json",
            "required_events": sorted(_canonical_project_hooks()),
            "duplicate_count": 0,
        }
    missing_dirs = [path for path in directories if not path.is_dir()]
    missing_files = [path for path in files if not path.is_file()]
    receipt_path = layout["receipt"]
    receipt_missing = not receipt_path.is_file()
    planned = [path.relative_to(root).as_posix() for path in [*missing_dirs, *missing_files]]
    if hook_plan is not None:
        planned.extend(hook_plan["planned_changes"])
    if receipt_missing:
        planned.append(receipt_path.relative_to(root).as_posix())
    if dry_run:
        return {
            "schema_version": "1.0.0", "owner": "C01/run-dev-graph-init", "status": "preview",
            "repository_id": context["repository_id"], "hook_source": hook_source,
            "planned_changes": sorted(set(planned)), "write_count": 0,
            "migration_preview": migration_preview,
            "gh_cli_auth": gh_cli_auth,
            "hook_preview": hook_report,
            "config_result": config_evidence,
            "policy_preview": {
                "routing": {"content_roots": config["content_roots"], "path_policy": config["path_policy"]},
                "github": config["github"],
                "execution_tracker": config["execution_tracker"],
                "worktrees": config["worktrees"],
                "claude_hooks": config["claude_hooks"],
            },
            "readiness_plan": {
                "repo_config": {"status": "validated", "sha256": config_evidence["sha256"]},
                "graph": {
                    "status": "validate-after-apply",
                    "path": layout["graph"].relative_to(root).as_posix(),
                },
                "templates": {"status": "scaffold-missing-preserve-existing"},
                "goal_seek": {"status": "validate-after-apply"},
                "claude_hooks": {"status": "validate-after-apply", "mode": hook_report["mode"]},
                "completion_rule": "all actual readiness gates must pass after apply",
            },
        }

    created_files: list[Path] = []
    created_dirs: list[Path] = []
    hook_changed: list[Path] = []
    hook_applied = False
    try:
        for directory in sorted(set(directories), key=lambda path: len(path.parts)):
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created_dirs.append(directory)
            if not directory.is_dir() or directory.is_symlink():
                raise ContractError(f"init target directory is invalid: {directory}")
            directory.resolve(strict=True).relative_to(root)
        for path, content in files.items():
            if path.exists():
                continue
            _create(path, content, created_files)

        if hook_plan is not None:
            hook_applied = True
            _apply_project_hook_plan(hook_plan, hook_changed)
            if _project_hook_plan(root)["planned_changes"]:
                raise ContractError("C25 project-fallback readiness is incomplete after apply")

        config_report = {"valid": not _schema_findings(_load_object(root / ".dev-graph/config.json")), "schema": "schemas/repo-config.schema.json"}
        graph_report = _graph_readiness(root, layout["graph"])
        missing_templates = sorted(
            source.name for source in TEMPLATES.iterdir()
            if source.is_file() and not (root / ".dev-graph/templates" / source.name).is_file()
        )
        if missing_templates:
            raise ContractError(f"template readiness incomplete: {missing_templates}")
        goal_report = _verify_goal_records(root, goal)
        readiness = {
            "repo_config": config_report,
            "graph": graph_report,
            "templates": {"valid": True, "missing": [], "count": len([p for p in TEMPLATES.iterdir() if p.is_file()])},
            "goal_seek": goal_report,
            "claude_hooks": {"valid": True, **hook_report},
        }
        if receipt_missing:
            receipt = {
                "schema_version": "1.0.0", "owner": "C01/run-dev-graph-init", "status": "initialized",
                "repository_id": context["repository_id"],
                "content_roots": config["content_roots"], "local_state": config["local_state"],
                "config_result": config_evidence,
                "hook_source": hook_source,
                "created": sorted(path.relative_to(root).as_posix() for path in created_files),
                "preserved": preserved,
                "migration_preview": migration_preview,
                "gh_cli_auth": gh_cli_auth,
                "hook_result": hook_report,
                "schema_result": readiness,
            }
            absolute_paths = _absolute_stored_paths(receipt)
            if absolute_paths:
                raise ContractError(f"init receipt contains absolute stored paths: {absolute_paths}")
            _create(receipt_path, _json_bytes(receipt), created_files)
        else:
            receipt = _load_object(receipt_path)
            if (
                receipt.get("owner") != "C01/run-dev-graph-init"
                or receipt.get("repository_id") != context["repository_id"]
                or receipt.get("hook_source") != hook_source
            ):
                raise ContractError("existing init receipt identity mismatch")
            if receipt.get("content_roots") != config["content_roots"] or receipt.get("local_state") != config["local_state"]:
                raise ContractError("existing init receipt paths conflict with effective repo config")
            recorded_config = receipt.get("config_result")
            if isinstance(recorded_config, dict) and recorded_config.get("sha256") != config_evidence["sha256"]:
                raise ContractError("existing init receipt config digest conflicts with effective repo config")
            absolute_paths = _absolute_stored_paths(receipt)
            if absolute_paths:
                raise ContractError(f"existing init receipt contains absolute stored paths: {absolute_paths}")
        return {
            "schema_version": "1.0.0", "owner": "C01/run-dev-graph-init", "status": "initialized",
            "repository_id": context["repository_id"], "hook_source": hook_source,
            "config_result": config_evidence,
            "gh_cli_auth": gh_cli_auth,
            "planned_changes": sorted(set(planned)),
            "write_count": len(set(created_files + hook_changed)),
            "created": sorted(path.relative_to(root).as_posix() for path in created_files),
            "hook_changed": sorted(path.relative_to(root).as_posix() for path in hook_changed),
            "preserved": preserved,
            "migration_preview": migration_preview,
            "receipt": receipt_path.relative_to(root).as_posix(),
            "readiness": readiness,
            "idempotent": not planned,
        }
    except Exception:
        if hook_applied and hook_plan is not None:
            _restore_project_hook_plan(hook_plan)
        for path in reversed(created_files):
            try:
                path.unlink()
            except OSError:
                pass
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--hook-source", choices=("plugin", "project-fallback"), default="plugin")
    parser.add_argument("--goal", default=DEFAULT_GOAL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rollback-project-hooks", action="store_true")
    args = parser.parse_args()
    try:
        if args.rollback_project_hooks:
            if args.hook_source != "project-fallback":
                raise ContractError("--rollback-project-hooks requires --hook-source project-fallback")
            report = rollback_project_hooks(Path(args.repo_root), args.dry_run)
        else:
            report = initialize(Path(args.repo_root), args.hook_source, args.goal, args.dry_run)
    except (ContractError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
