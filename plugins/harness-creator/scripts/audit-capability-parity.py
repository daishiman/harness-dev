#!/usr/bin/env python3
# /// script
# name: audit-capability-parity
# purpose: Claude/Codex plugin capability parity を user-reachable surface 単位で監査する。
# inputs:
#   - argv: --repo-root PATH [--plugin SLUG ...|--all] [--json]
# outputs:
#   - stdout: plugin別のsurface inventory・violations・PASS/FAIL
#   - exit: 0=全PASS / 1=parity FAIL / 2=入力・layout不正
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Audit user-reachable capability parity across Claude Code and Codex plugins."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SHARED_MANIFEST_FIELDS = ("name", "version", "description", "author")
SURFACE_DIRS = {
    "skills": ("skills", "*/SKILL.md"),
    "agents": ("agents", "*.md"),
    "commands": ("commands", "*.md"),
    "hooks": ("hooks", "*"),
}
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml"}
EXECUTABLE_RE = re.compile(
    r"(?:^|[`|>\s])(?:python3?|bash|sh|node|uv\s+run)\s+|"
    r"(?:command|run|exec)\s*[:=].*CLAUDE_PLUGIN_ROOT|"
    r"CLAUDE_PLUGIN_ROOT/(?:scripts|skills|agents|hooks|lib|schemas|references)/"
)
DUAL_ROOT_RE = re.compile(
    r"\$\{PLUGIN_ROOT:-\$\{CLAUDE_PLUGIN_ROOT(?::-[^{}]+)?\}\}|"
    r"\$\{PLUGIN_ROOT:-\$CLAUDE_PLUGIN_ROOT\}"
)
LITERAL_ROOT_PLACEHOLDER_RE = re.compile(
    r"<(?:absolute-)?(?:plugin-root|skill-path)>", re.IGNORECASE
)
RUNTIME_ROOT_POLICY = "host-skill-path"
RUNTIME_ROOT_CONTRACT_TOKENS = (
    "## Runtime root contract",
    "Claude Code",
    "`CLAUDE_PLUGIN_ROOT`",
    "この `SKILL.md` のabsolute path",
    "plugin manifest",
    "`cwd`",
    "literal placeholder",
    "各shell invocation",
    "`prompts/` 配下はこのowner Skill契約を継承する",
)
SKILL_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:run|assign|ref|wrap|delegate)-[a-z0-9][a-z0-9-]*"
)
HOOK_PATH_RE = re.compile(
    r"/(?P<path>(?:hooks|scripts)/[A-Za-z0-9_./-]+\.(?:py|sh|js|mjs|cjs))"
)


class AuditError(RuntimeError):
    pass


def resolve_host_skill_plugin_root(
    skill_path: str | Path, *, expected_plugin: str | None = None
) -> Path:
    """Resolve a plugin root solely from a host-supplied absolute SKILL.md path."""

    raw = Path(skill_path)
    if not raw.is_absolute() or LITERAL_ROOT_PLACEHOLDER_RE.search(str(raw)):
        raise AuditError("host skill path must be an absolute, resolved path; placeholders are invalid")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise AuditError(f"host skill path cannot be resolved: {raw}") from exc
    if not resolved.is_file() or resolved.name != "SKILL.md":
        raise AuditError(f"host skill path must identify SKILL.md: {resolved}")

    for ancestor in (resolved.parent, *resolved.parents):
        for relative_manifest in (
            Path(".codex-plugin/plugin.json"),
            Path(".claude-plugin/plugin.json"),
        ):
            manifest_path = ancestor / relative_manifest
            if not manifest_path.is_file():
                continue
            manifest = _load_json(manifest_path)
            manifest_name = manifest.get("name")
            if expected_plugin is not None and manifest_name != expected_plugin:
                raise AuditError(
                    f"plugin manifest name {manifest_name!r} does not match {expected_plugin!r}"
                )
            return ancestor.resolve()
    raise AuditError(f"no ancestor plugin manifest found for host skill path: {resolved}")


def _load_json(path: Path, *, required: bool = True) -> dict:
    if not path.is_file():
        if required:
            raise AuditError(f"required JSON missing: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditError(f"JSON root must be an object: {path}")
    return payload


def _violation(code: str, message: str, *, path: str | None = None) -> dict:
    item = {"code": code, "message": message}
    if path is not None:
        item["path"] = path
    return item


def _surface_names(plugin: Path, kind: str) -> list[str]:
    directory, pattern = SURFACE_DIRS[kind]
    root = plugin / directory
    if not root.is_dir():
        return []
    paths = sorted(root.glob(pattern))
    if kind == "skills":
        return [path.parent.name for path in paths]
    if kind == "hooks":
        return [path.name for path in paths if path.is_file() and path.suffix in {".py", ".sh"}]
    return [path.stem for path in paths]


def _composition_surfaces(plugin: Path, actual_hooks: list[str]) -> tuple[dict[str, list[str]], str | None]:
    """Read only public S/A/C/H refs from the stdlib-compatible composition subset."""

    path = plugin / "plugin-composition.yaml"
    empty = {kind: [] for kind in SURFACE_DIRS}
    if not path.is_file():
        return empty, "plugin-composition.yaml is required"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return empty, str(exc)
    identity = re.search(r"^(?:name|plugin):\s*([^\s#]+)", text, re.MULTILINE)
    if identity is None or identity.group(1).strip("\"'") != plugin.name:
        return empty, "composition name/plugin does not match plugin directory"
    section = None
    refs: list[tuple[str, str]] = []
    current: dict[str, str] | None = None

    def flush() -> None:
        nonlocal current
        if current and current.get("kind") and (current.get("ref") or current.get("path")):
            refs.append((current["kind"], current.get("ref") or current["path"]))
        current = None

    for raw in text.splitlines():
        top = re.match(r"^([A-Za-z_][\w-]*):", raw)
        if top:
            flush()
            section = top.group(1)
            continue
        if section != "capabilities":
            continue
        flow = re.match(r"^\s*-\s*\{(.*)\}\s*(?:#.*)?$", raw)
        if flow:
            flush()
            fields = {
                key: value.strip().strip("\"'")
                for key, value in re.findall(
                    r"([A-Za-z_][\w-]*)\s*:\s*(\"(?:[^\"\\]|\\.)*\"|'[^']*'|[^,}]+)",
                    flow.group(1),
                )
            }
            if fields.get("kind") and (fields.get("ref") or fields.get("path")):
                refs.append((fields["kind"], fields.get("ref") or fields["path"]))
            continue
        block = re.match(r"^\s*-\s+kind\s*:\s*(\S+)", raw)
        if block:
            flush()
            current = {"kind": block.group(1).strip("\"'")}
            continue
        if current is not None:
            field = re.match(r"^\s+(ref|path)\s*:\s*(.*?)\s*(?:#.*)?$", raw)
            if field:
                current[field.group(1)] = field.group(2).strip().strip("\"'")
    flush()

    surfaces = {kind: [] for kind in SURFACE_DIRS}
    hook_by_stem = {Path(name).stem: name for name in actual_hooks}
    singular = {"skill": "skills", "agent": "agents", "command": "commands", "hook": "hooks"}
    for kind, ref in refs:
        bucket = singular.get(kind)
        if bucket is None:
            continue
        if kind == "skill":
            value = Path(ref.removesuffix("/SKILL.md")).name
        elif kind in {"agent", "command"}:
            value = Path(ref).stem
        elif ref.startswith("hook:"):
            value = hook_by_stem.get(Path(ref.split("/", 1)[-1]).stem, Path(ref).name)
        else:
            value = Path(ref).name
        surfaces[bucket].append(value)
    return surfaces, None


def _resolve_component(plugin: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.startswith("./"):
        return None
    resolved = (plugin / value).resolve()
    try:
        resolved.relative_to(plugin.resolve())
    except ValueError:
        return None
    return resolved


def _hook_document(plugin: Path, manifest: dict) -> dict:
    value = manifest.get("hooks")
    if isinstance(value, dict):
        return {"hooks": value}
    if isinstance(value, str):
        path = _resolve_component(plugin, value)
        if path is None:
            raise AuditError(f"hook path escapes plugin root: {value}")
        return _load_json(path)
    default_path = plugin / "hooks" / "hooks.json"
    if default_path.is_file():
        return _load_json(default_path)
    return {"hooks": {}}


def _hook_events(document: dict) -> dict[str, list[dict]]:
    hooks = document.get("hooks", document)
    if not isinstance(hooks, dict):
        return {}
    return {
        event: groups
        for event, groups in hooks.items()
        if isinstance(event, str) and isinstance(groups, list)
    }


def _files_count(plugin: Path, directory: str) -> int:
    root = plugin / directory
    return (
        sum(
            1
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
        if root.is_dir()
        else 0
    )


def _frontmatter_value(path: Path, key: str) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(rf"^{re.escape(key)}\s*:\s*(.*?)\s*$", line)
        if match:
            return match.group(1).split("#", 1)[0].strip().strip("\"'")
    return None


def _owner_skill(path: Path, skills_root: Path) -> Path | None:
    for ancestor in (path.parent, *path.parents):
        if ancestor == skills_root.parent:
            break
        candidate = ancestor / "SKILL.md"
        if candidate.is_file() and candidate.parent.parent == skills_root:
            return candidate
    return None


def _portable_root_violations(plugin: Path) -> list[dict]:
    violations: list[dict] = []
    runtime_owners: set[Path] = set()
    candidates: list[Path] = []
    skills_root = plugin / "skills"
    for skill in skills_root.glob("*/SKILL.md") if skills_root.is_dir() else []:
        candidates.append(skill)
    for prompt in skills_root.glob("*/prompts/**/*") if skills_root.is_dir() else []:
        if prompt.is_file() and prompt.suffix in TEXT_SUFFIXES:
            candidates.append(prompt)
    for path in sorted(set(candidates)):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        fence = ""
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                marker = stripped[3:].strip().lower()
                fence = "" if fence else marker
                continue
            executable_fence = fence in {"bash", "sh", "shell", "zsh", "console"}
            executable_line = executable_fence or bool(EXECUTABLE_RE.search(line))
            if executable_line and LITERAL_ROOT_PLACEHOLDER_RE.search(line):
                rel = path.relative_to(plugin).as_posix()
                violations.append(
                    _violation(
                        "literal_runtime_root_placeholder",
                        "executable skill/prompt path must not pass a literal root placeholder to shell",
                        path=f"{rel}:{line_no}",
                    )
                )
            if not executable_line or not ({"PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"} & set(re.findall(r"(?:CLAUDE_)?PLUGIN_ROOT", line))):
                continue
            owner = _owner_skill(path, skills_root)
            if owner is not None:
                runtime_owners.add(owner)
            if "CLAUDE_PLUGIN_ROOT" in line and not DUAL_ROOT_RE.search(line):
                rel = path.relative_to(plugin).as_posix()
                violations.append(
                    _violation(
                        "bare_claude_plugin_root",
                        "executable skill/prompt path requires ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}} or self-resolution",
                        path=f"{rel}:{line_no}",
                    )
                )
    for owner in sorted(runtime_owners):
        rel = owner.relative_to(plugin).as_posix()
        if _frontmatter_value(owner, "runtime_root_policy") != RUNTIME_ROOT_POLICY:
            violations.append(
                _violation(
                    "runtime_root_policy_missing",
                    "owner skill of an executable plugin-root path requires runtime_root_policy: host-skill-path",
                    path=rel,
                )
            )
            continue
        try:
            body = owner.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            body = ""
        missing = [token for token in RUNTIME_ROOT_CONTRACT_TOKENS if token not in body]
        if missing:
            violations.append(
                _violation(
                    "runtime_root_contract_missing",
                    "owner skill runtime root body contract is incomplete: " + ", ".join(missing),
                    path=rel,
                )
            )
    return violations


def _marketplace_entry(repo: Path, slug: str) -> dict | None:
    marketplace = _load_json(repo / ".agents" / "plugins" / "marketplace.json")
    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        return None
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("name") == slug]
    return matches[0] if len(matches) == 1 else None


def _validate_alternatives(
    repo: Path,
    *,
    plugin: Path,
    actual: dict[str, list[str]],
    contract: dict,
    violations: list[dict],
) -> None:
    alternatives = contract.get("codex_alternatives")
    if not isinstance(alternatives, dict):
        violations.append(_violation("codex_alternatives_missing", "codex_alternatives object is required"))
        alternatives = {}
    skills = set(actual["skills"])
    for kind in ("commands", "agents"):
        mapping = alternatives.get(kind)
        if not isinstance(mapping, dict):
            mapping = {}
        for extra in sorted(set(mapping) - set(actual[kind])):
            violations.append(
                _violation(
                    "semantic_alternative_orphan",
                    f"{kind[:-1]} alternative has no matching Claude surface: {extra}",
                )
            )
        for name in actual[kind]:
            route = mapping.get(name)
            code = f"{kind[:-1]}_alternative_missing"
            if route is None:
                violations.append(_violation(code, f"{kind[:-1]} {name} has no explicit Codex skill alternative"))
                continue
            required = {"relation", "purpose", "arguments", "effect", "discovery", "owner_route"}
            if not isinstance(route, dict) or set(route) != required:
                violations.append(
                    _violation(
                        "semantic_alternative_invalid",
                        f"{kind[:-1]} {name} requires structured relation/purpose/arguments/effect/discovery/owner_route",
                    )
                )
                continue
            purpose = route.get("purpose")
            relation = route.get("relation")
            arguments = route.get("arguments")
            effect = route.get("effect")
            discovery = route.get("discovery")
            owner_route = route.get("owner_route")
            structural = (
                isinstance(relation, str)
                and bool(relation.strip())
                and isinstance(purpose, str)
                and bool(purpose.strip())
                and isinstance(arguments, dict)
                and set(arguments) == {"policy", "notes"}
                and all(isinstance(arguments.get(key), str) and arguments[key].strip() for key in arguments)
                and isinstance(effect, dict)
                and set(effect) == {"policy", "notes"}
                and all(isinstance(effect.get(key), str) and effect[key].strip() for key in effect)
                and isinstance(discovery, dict)
                and set(discovery) == {"kind", "entry_points"}
                and discovery.get("kind") == "skill"
                and isinstance(discovery.get("entry_points"), list)
                and bool(discovery["entry_points"])
                and all(isinstance(item, str) and item for item in discovery["entry_points"])
                and len(discovery["entry_points"]) == len(set(discovery["entry_points"]))
                and isinstance(owner_route, dict)
                and set(owner_route) == {"plugin", "entry_points"}
                and isinstance(owner_route.get("plugin"), str)
                and bool(owner_route["plugin"])
                and isinstance(owner_route.get("entry_points"), list)
                and bool(owner_route["entry_points"])
                and all(isinstance(item, str) and item for item in owner_route["entry_points"])
                and len(owner_route["entry_points"]) == len(set(owner_route["entry_points"]))
                and discovery["entry_points"] == owner_route["entry_points"]
            )
            if not structural:
                violations.append(
                    _violation(
                        "semantic_alternative_invalid",
                        f"{kind[:-1]} {name} semantic route fields are incomplete or inconsistent",
                    )
                )
                continue
            owner = owner_route["plugin"]
            targets = owner_route["entry_points"]
            if owner != plugin.name and owner not in contract.get("depends_on", []):
                violations.append(
                    _violation(
                        "semantic_owner_dependency_missing",
                        f"{kind[:-1]} {name} routes to {owner} without depends_on edge",
                    )
                )
            owner_plugin = repo / "plugins" / owner
            try:
                owner_contract = _load_json(
                    owner_plugin / "references" / "package-contract.json", required=False
                )
            except AuditError as exc:
                violations.append(
                    _violation("semantic_owner_entry_point_missing", str(exc))
                )
                continue
            declared = owner_contract.get("entry_points", {}).get("skills", [])
            owner_actual = set(_surface_names(owner_plugin, "skills"))
            missing = sorted(
                target
                for target in targets
                if target not in declared or target not in owner_actual
            )
            if missing:
                violations.append(
                    _violation(
                        "semantic_owner_entry_point_missing",
                        f"{kind[:-1]} {name} owner route is not a declared, reachable skill: {missing}",
                    )
                )
    library_files = sum(_files_count(plugin, name) for name in ("scripts", "config", "assets"))
    domain_skills = {name for name in skills if name != "run-skill-feedback"}
    if library_files and not domain_skills:
        target = alternatives.get("library_entry_skill")
        if not isinstance(target, str) or target not in skills:
            violations.append(
                _violation(
                    "library_entry_skill_missing",
                    "scripts/config/assets require a user-reachable domain skill",
                )
            )


def _codex_alternatives(repo: Path, slug: str, contract: dict) -> dict:
    inline = contract.get("codex_alternatives")
    return inline if isinstance(inline, dict) else {}


def _validate_hook_parity(
    *,
    plugin: Path,
    claude: dict,
    codex: dict,
    alternatives: dict,
    actual_skills: set[str],
    violations: list[dict],
) -> dict:
    try:
        claude_events = _hook_events(_hook_document(plugin, claude))
        codex_events = _hook_events(_hook_document(plugin, codex))
    except AuditError as exc:
        violations.append(_violation("hook_document_invalid", str(exc)))
        return {"claude_events": [], "codex_events": []}
    omissions = alternatives.get("hook_omissions", {})
    if not isinstance(omissions, dict):
        omissions = {}
    missing_events = set(claude_events) - set(codex_events)
    for event in sorted(set(omissions) - missing_events):
        violations.append(
            _violation(
                "hook_omission_orphan",
                f"hook omission is declared but Codex exposes the event: {event}",
            )
        )
    for event in sorted(missing_events):
        omission = omissions.get(event)
        valid = isinstance(omission, dict) and isinstance(omission.get("reason"), str) and bool(
            omission["reason"].strip()
        )
        if valid:
            replacement_events = omission.get("replacement_events", [])
            replacement_skill = omission.get("replacement_skill")
            event_valid = isinstance(replacement_events, list) and any(
                isinstance(item, str) and item in codex_events for item in replacement_events
            )
            skill_valid = isinstance(replacement_skill, str) and replacement_skill in actual_skills
            valid = event_valid or skill_valid
        if not valid:
            violations.append(
                _violation(
                    "hook_omission_missing",
                    f"Claude hook event {event} is absent from Codex without a usable omission contract",
                )
            )
    for event, groups in codex_events.items():
        for group in groups:
            hooks = group.get("hooks", []) if isinstance(group, dict) else []
            if not isinstance(hooks, list):
                violations.append(
                    _violation("hook_command_invalid", f"Codex hook {event} has a non-array hooks field")
                )
                continue
            for hook in hooks:
                if not isinstance(hook, dict) or hook.get("type") != "command":
                    continue
                command = hook.get("command")
                if not isinstance(command, str) or not command.strip():
                    violations.append(
                        _violation("hook_command_invalid", f"Codex hook {event} has no command")
                    )
                    continue
                if "CLAUDE_PLUGIN_ROOT" in command and "PLUGIN_ROOT" not in command:
                    violations.append(
                        _violation(
                            "hook_command_nonportable",
                            f"Codex hook {event} uses bare CLAUDE_PLUGIN_ROOT",
                        )
                    )
                matches = list(HOOK_PATH_RE.finditer(command))
                if "PLUGIN_ROOT" in command and not matches:
                    violations.append(
                        _violation(
                            "hook_command_unreachable",
                            f"Codex hook {event} plugin-root command has no resolvable script path",
                        )
                    )
                for match in matches:
                    target = (plugin / match.group("path")).resolve()
                    try:
                        target.relative_to(plugin.resolve())
                    except ValueError:
                        target = Path()
                    if not target.is_file():
                        violations.append(
                            _violation(
                                "hook_command_unreachable",
                                f"Codex hook {event} command target is missing: {match.group('path')}",
                            )
                        )
    return {
        "claude_events": sorted(claude_events),
        "codex_events": sorted(codex_events),
        "omitted_events": sorted(set(claude_events) - set(codex_events)),
    }


def _validate_component_parity(
    *,
    plugin: Path,
    claude: dict,
    codex: dict,
    alternatives: dict,
    actual_skills: set[str],
    violations: list[dict],
) -> dict:
    omissions = alternatives.get("component_omissions", {})
    if not isinstance(omissions, dict):
        omissions = {}
    report: dict[str, dict[str, bool]] = {}
    for field in ("mcpServers", "apps"):
        claude_present = claude.get(field) is not None
        codex_present = codex.get(field) is not None
        report[field] = {"claude": claude_present, "codex": codex_present}
        for platform, manifest in (("Claude", claude), ("Codex", codex)):
            value = manifest.get(field)
            if not isinstance(value, str):
                continue
            resolved = _resolve_component(plugin, value)
            if resolved is None or not resolved.exists():
                violations.append(
                    _violation(
                        "component_unreachable",
                        f"{platform} {field} path is missing or escapes: {value}",
                    )
                )
        if not claude_present or codex_present:
            continue
        omission = omissions.get(field)
        valid = isinstance(omission, dict) and isinstance(omission.get("reason"), str)
        valid = bool(valid and omission["reason"].strip())
        replacement_skill = omission.get("replacement_skill") if isinstance(omission, dict) else None
        valid = valid and isinstance(replacement_skill, str) and replacement_skill in actual_skills
        if not valid:
            violations.append(
                _violation(
                    "component_alternative_missing",
                    f"Claude {field} is absent from Codex without a reachable skill alternative",
                )
            )
    return report


def audit_plugin(repo_root: Path, plugin: Path) -> dict:
    repo = Path(repo_root).resolve()
    plugin = Path(plugin).resolve()
    slug = plugin.name
    violations: list[dict] = []
    actual = {kind: _surface_names(plugin, kind) for kind in SURFACE_DIRS}
    inventory = {
        **{kind: len(names) for kind, names in actual.items()},
        "scripts": _files_count(plugin, "scripts"),
        "mcp": 0,
        "apps": 0,
        "config_assets_references": sum(
            _files_count(plugin, name) for name in ("config", "assets", "references")
        ),
    }
    try:
        claude = _load_json(plugin / ".claude-plugin" / "plugin.json")
        codex = _load_json(plugin / ".codex-plugin" / "plugin.json")
    except AuditError as exc:
        violations.append(_violation("manifest_missing_or_invalid", str(exc)))
        return {"plugin": slug, "inventory": inventory, "violations": violations, "verdict": "FAIL"}
    for field in SHARED_MANIFEST_FIELDS:
        if claude.get(field) != codex.get(field):
            violations.append(_violation("manifest_metadata_drift", f"shared field differs: {field}"))
    skills_path = _resolve_component(plugin, codex.get("skills"))
    if skills_path != (plugin / "skills").resolve() or not skills_path.is_dir():
        violations.append(_violation("codex_skills_unreachable", "Codex manifest must reference existing ./skills/"))
    for field in ("hooks", "mcpServers", "apps"):
        value = codex.get(field)
        if isinstance(value, str):
            resolved = _resolve_component(plugin, value)
            if resolved is None or not resolved.exists():
                violations.append(_violation("codex_component_unreachable", f"{field} path is missing or escapes: {value}"))
        inventory["mcp"] += int(field == "mcpServers" and (value is not None or claude.get(field) is not None))
        inventory["apps"] += int(field == "apps" and (value is not None or claude.get(field) is not None))
    entry = _marketplace_entry(repo, slug)
    expected_source = {"source": "local", "path": f"./plugins/{slug}"}
    if entry is None or entry.get("source") != expected_source:
        violations.append(_violation("codex_marketplace_unreachable", "marketplace entry/source.path mismatch"))
    contract_path = plugin / "references" / "package-contract.json"
    try:
        contract = _load_json(contract_path)
    except AuditError as exc:
        violations.append(_violation("package_contract_missing", str(exc)))
        contract = {}
    if contract.get("plugin_name") != slug:
        violations.append(_violation("package_contract_plugin_mismatch", "package contract plugin_name mismatch"))
    entry_points = contract.get("entry_points")
    if not isinstance(entry_points, dict):
        violations.append(_violation("entry_points_missing", "package contract entry_points object is required"))
        entry_points = {}
    for kind in SURFACE_DIRS:
        declared = entry_points.get(kind)
        declared_set = set(declared) if isinstance(declared, list) else set()
        missing_declared = sorted(declared_set - set(actual[kind]))
        omitted_actual = sorted(set(actual[kind]) - declared_set)
        if not isinstance(declared, list) or missing_declared or omitted_actual:
            violations.append(
                _violation(
                    "entry_point_inventory_drift",
                    f"{kind} declared-not-actual={missing_declared} actual-not-declared={omitted_actual}",
                )
            )
        if isinstance(declared, list) and len(declared) != len(declared_set):
            violations.append(
                _violation("entry_point_duplicate", f"{kind} contains duplicate entry points")
            )
    composition, composition_error = _composition_surfaces(plugin, actual["hooks"])
    if composition_error:
        violations.append(_violation("composition_missing", composition_error))
    else:
        for kind in SURFACE_DIRS:
            declared = composition[kind]
            if set(declared) != set(actual[kind]):
                violations.append(
                    _violation(
                        "composition_surface_drift",
                        f"{kind} composition={sorted(set(declared))} actual={sorted(actual[kind])}",
                    )
                )
    dependencies = contract.get("depends_on")
    if not isinstance(dependencies, list):
        violations.append(_violation("dependency_contract_missing", "depends_on array is required"))
    else:
        marketplace = _load_json(repo / ".agents" / "plugins" / "marketplace.json")
        known = {
            item.get("name") for item in marketplace.get("plugins", []) if isinstance(item, dict)
        }
        for dependency in dependencies:
            if dependency not in known:
                violations.append(_violation("dependency_unreachable", f"dependency not in Codex marketplace: {dependency}"))
    runtime_dependencies = contract.get("runtime_dependencies")
    if not isinstance(runtime_dependencies, list):
        violations.append(
            _violation("runtime_dependency_contract_missing", "runtime_dependencies array is required")
        )
        runtime_dependencies = []
    seen_runtime: set[str] = set()
    for item in runtime_dependencies:
        if not isinstance(item, dict):
            violations.append(
                _violation("runtime_dependency_invalid", "runtime dependency must be an object")
            )
            continue
        required = {
            "capability", "owner", "classification", "local_path",
            "owner_route", "required_entry_point", "purpose",
        }
        if set(item) != required or item.get("classification") not in {"owned-vendored", "runtime"}:
            violations.append(
                _violation("runtime_dependency_invalid", "runtime dependency fields/classification are invalid")
            )
            continue
        capability = item.get("capability")
        owner = item.get("owner")
        local_path = item.get("local_path")
        owner_route = item.get("owner_route")
        required_entry = item.get("required_entry_point")
        if not all(isinstance(value, str) and value for value in (
            capability, owner, local_path, owner_route, required_entry, item.get("purpose")
        )):
            violations.append(
                _violation("runtime_dependency_invalid", "runtime dependency string field is empty")
            )
            continue
        if capability in seen_runtime:
            violations.append(
                _violation("runtime_dependency_invalid", f"duplicate runtime capability: {capability}")
            )
        seen_runtime.add(capability)
        if not (plugin / local_path).exists():
            violations.append(
                _violation("runtime_dependency_local_missing", f"local vendored route is missing: {local_path}")
            )
        owner_plugin = repo / "plugins" / owner
        try:
            owner_contract = _load_json(
                owner_plugin / "references" / "package-contract.json", required=False
            )
        except AuditError as exc:
            violations.append(
                _violation("runtime_dependency_owner_route_missing", str(exc))
            )
            continue
        owner_skills = owner_contract.get("entry_points", {}).get("skills", [])
        if (
            not (owner_plugin / owner_route / "SKILL.md").is_file()
            or required_entry not in owner_skills
            or Path(owner_route).name != required_entry
        ):
            violations.append(
                _violation(
                    "runtime_dependency_owner_route_missing",
                    f"owner route/required entry point is unresolved: {owner}/{owner_route}",
                )
            )
        if owner != slug and owner not in (dependencies if isinstance(dependencies, list) else []):
            violations.append(
                _violation(
                    "runtime_dependency_edge_missing",
                    f"runtime owner {owner} is absent from depends_on",
                )
            )
    if slug != "harness-creator" and "run-skill-feedback" in actual["skills"]:
        matches = [
            item for item in runtime_dependencies
            if isinstance(item, dict)
            and item.get("capability") == "run-skill-feedback"
            and item.get("owner") == "harness-creator"
            and item.get("classification") == "owned-vendored"
        ]
        if len(matches) != 1:
            violations.append(
                _violation(
                    "vendored_feedback_boundary_missing",
                    "run-skill-feedback requires one owned-vendored harness-creator runtime declaration",
                )
            )
    alternatives = _codex_alternatives(repo, slug, contract)
    parity_contract = dict(contract)
    parity_contract["codex_alternatives"] = alternatives
    _validate_alternatives(
        repo,
        plugin=plugin,
        actual=actual,
        contract=parity_contract,
        violations=violations,
    )
    hook_report = _validate_hook_parity(
        plugin=plugin,
        claude=claude,
        codex=codex,
        alternatives=alternatives,
        actual_skills=set(actual["skills"]),
        violations=violations,
    )
    component_report = _validate_component_parity(
        plugin=plugin,
        claude=claude,
        codex=codex,
        alternatives=alternatives,
        actual_skills=set(actual["skills"]),
        violations=violations,
    )
    violations.extend(_portable_root_violations(plugin))
    return {
        "plugin": slug,
        "inventory": inventory,
        "surfaces": actual,
        "hooks": hook_report,
        "components": component_report,
        "violations": violations,
        "verdict": "PASS" if not violations else "FAIL",
    }


def discover_plugins(repo_root: Path) -> list[Path]:
    root = Path(repo_root).resolve() / "plugins"
    return [
        path
        for path in sorted(root.iterdir() if root.is_dir() else [])
        if path.is_dir() and (path / ".claude-plugin" / "plugin.json").is_file()
    ]


def _dependency_graph(repo: Path, plugins: list[Path]) -> tuple[dict[str, list[str]], dict[str, list[dict]]]:
    """Load the explicit package graph and return per-plugin resolution failures."""
    slugs = {plugin.name for plugin in plugins}
    marketplace = _load_json(repo / ".agents" / "plugins" / "marketplace.json")
    entries = {
        item.get("name"): item
        for item in marketplace.get("plugins", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    graph: dict[str, list[str]] = {}
    failures: dict[str, list[dict]] = {slug: [] for slug in slugs}
    for plugin in plugins:
        slug = plugin.name
        try:
            contract = _load_json(
                plugin / "references" / "package-contract.json", required=False
            )
        except AuditError as exc:
            graph[slug] = []
            failures[slug].append(
                _violation("dependency_contract_invalid", str(exc))
            )
            continue
        dependencies = contract.get("depends_on", [])
        if not isinstance(dependencies, list):
            graph[slug] = []
            continue
        graph[slug] = sorted({item for item in dependencies if isinstance(item, str)})
        if len(graph[slug]) != len(dependencies):
            failures[slug].append(
                _violation("dependency_contract_invalid", "depends_on must contain unique plugin names")
            )
        for dependency in graph[slug]:
            entry = entries.get(dependency)
            expected_source = {"source": "local", "path": f"./plugins/{dependency}"}
            if dependency not in slugs or not isinstance(entry, dict) or entry.get("source") != expected_source:
                failures[slug].append(
                    _violation(
                        "dependency_unreachable",
                        f"dependency closure cannot resolve {dependency} from the Codex catalog",
                    )
                )
    return graph, failures


def _dependency_scc(graph: dict[str, list[str]]) -> list[dict]:
    """Return deterministic, fully declared dependency SCC co-install groups."""
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for dependency in graph.get(node, []):
            if dependency not in graph:
                continue
            if dependency not in indices:
                visit(dependency)
                lowlinks[node] = min(lowlinks[node], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[dependency])
        if lowlinks[node] != indices[node]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    result: list[dict] = []
    for members in sorted(components):
        member_set = set(members)
        has_cycle = len(members) > 1 or any(node in graph.get(node, []) for node in members)
        if not has_cycle:
            continue
        edges = [
            {"from": node, "to": dependency}
            for node in members
            for dependency in graph.get(node, [])
            if dependency in member_set
        ]
        result.append(
            {
                "members": members,
                "edges": edges,
                "catalog": ".agents/plugins/marketplace.json",
                "resolvable": True,
            }
        )
    return result


def audit_repo(repo_root: Path, slugs: list[str] | None = None) -> dict:
    repo = Path(repo_root).resolve()
    discovered = discover_plugins(repo)
    selected = discovered
    if slugs:
        wanted = {Path(item.rstrip("/")).name for item in slugs}
        selected = [path for path in selected if path.name in wanted]
        missing = sorted(wanted - {path.name for path in selected})
        if missing:
            raise AuditError(f"unknown plugin(s): {', '.join(missing)}")
    reports = [audit_plugin(repo, plugin) for plugin in selected]
    graph, dependency_failures = _dependency_graph(repo, discovered)
    for report in reports:
        report["dependencies"] = graph.get(report["plugin"], [])
        report["violations"].extend(dependency_failures.get(report["plugin"], []))
        report["verdict"] = "PASS" if not report["violations"] else "FAIL"
    return {
        "plugin_count": len(reports),
        "pass_count": sum(item["verdict"] == "PASS" for item in reports),
        "fail_count": sum(item["verdict"] != "PASS" for item in reports),
        "dependency_scc": _dependency_scc(graph),
        "plugins": reports,
        "verdict": "PASS" if reports and all(item["verdict"] == "PASS" for item in reports) else "FAIL",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--plugin", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.all and args.plugin:
        print("--all and --plugin cannot be combined", file=sys.stderr)
        return 2
    try:
        report = audit_repo(args.repo_root, None if args.all or not args.plugin else args.plugin)
    except AuditError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
