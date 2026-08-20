#!/usr/bin/env python3
# /// script
# name: lint-plugin-composition
# purpose: plugin-composition.yaml の capability 実在・hook配線・skill/command dispatch dependency parityを検査する。
# inputs:
#   - argv: plugin-composition.yaml path(s) or --self-test
# outputs:
#   - stdout: OK status
#   - stderr: violation findings (FAIL) / warnings (WARN)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Lint plugin-composition.yaml (CapabilityBundle 宣言) の構造整合を検査する。

検査項目:
  (a) capabilities[] の ref 重複            → FAIL
  (b) capabilities[] の ref 実在
      - kind=skill:   <plugin>/<ref>/SKILL.md   → FAIL
      - kind=agent:   <plugin>/<ref>.md         → FAIL
      - kind=command: <plugin>/<ref>.md         → FAIL
      - kind=hook:    "hook:<Event>[-<hint>]/<name>" 形式           → FAIL
  (c) hooks 宣言 ↔ .claude-plugin/plugin.json の hook 配線対応       → FAIL
      論理名(例: elegant-review-trigger)と script 実体名は 1:1 でないため
      イベント単位の件数一致で照合する (宣言数 == 配線 command 数)。
  (d) contract.interface.outputs のパス実在                          → WARN
      proposals/*.md 等は governance 発火まで空が正当なため FAIL にしない
      (オオカミ少年回避)。パス形でない概念名 (CapabilityManifest 等) は skip。
  (e) skill frontmatter script_refs ↔ dependencies(type=calls)      → FAIL
  (f) command 本文の同 bundle Skill/script dispatch ↔ dependencies      → FAIL

YAML パーサ非依存 (stdlib only): CI は pip install を行わないため、
flow-mapping 行 `- { kind: x, ref: y, tier: z }` と block 形
`- kind: x` + 字下げ `ref:/path:` の両形式を行ベースで読む。

Usage:
  lint-plugin-composition.py plugins/harness-creator/plugin-composition.yaml
  lint-plugin-composition.py --self-test

Exit 0 = ok (WARN は許容), 1 = violation, 2 = usage/parse error.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

FLOW_ENTRY_RE = re.compile(r"^\s*-\s*\{(.*)\}\s*(?:#.*)?$")
BLOCK_ENTRY_RE = re.compile(r"^(\s*)-\s+([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*(?:#.*)?$")
KV_RE = re.compile(r"""([A-Za-z_][\w-]*)\s*:\s*("(?:[^"\\]|\\.)*"|'[^']*'|[^,}]+)""")
TOP_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(?:#.*)?")
OUTPUTS_RE = re.compile(r"^\s*outputs:\s*\[(.*)\]\s*(?:#.*)?$")
HOOK_REF_RE = re.compile(r"^hook:([A-Za-z]+)(?:-[\w-]+)?/[\w.-]+$")
GLOB_CHARS = ("*", "?", "[")
FRONTMATTER_BOUNDARY_RE = re.compile(r"^---\s*$", re.MULTILINE)
BACKTICK_SCRIPT_RE = re.compile(r"`(scripts/[A-Za-z0-9_.\-/]+\.py)`")
SKILL_DISPATCH_RE = re.compile(r"\bSkill\s+`([A-Za-z0-9_.\-/]+)`", re.IGNORECASE)


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def parse_composition(text: str) -> tuple[list[dict], list[str], list[str]]:
    """Returns (capabilities, outputs, parse_errors).

    capabilities: [{"kind": ..., "ref": ...}, ...] (ref は ref/path キーの値)
    outputs: contract.interface.outputs の要素リスト
    """
    caps: list[dict] = []
    outputs: list[str] = []
    errors: list[str] = []
    section = None
    current_block: dict | None = None

    def flush_block() -> None:
        nonlocal current_block
        if current_block is not None:
            caps.append(current_block)
            current_block = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        top = TOP_KEY_RE.match(raw)
        if top:
            flush_block()
            section = top.group(1)
            continue
        m = OUTPUTS_RE.match(raw)
        if m and section == "contract":
            outputs = [_unquote(x) for x in m.group(1).split(",") if x.strip()]
            continue
        if section != "capabilities":
            continue
        m = FLOW_ENTRY_RE.match(raw)
        if m:
            flush_block()
            entry = {k: _unquote(v) for k, v in KV_RE.findall(m.group(1))}
            if "ref" not in entry and "path" not in entry:
                errors.append(f"line {lineno}: capability entry has no ref/path: {stripped}")
            else:
                caps.append(entry)
            continue
        m = BLOCK_ENTRY_RE.match(raw)
        if m:
            flush_block()
            current_block = {m.group(2): _unquote(m.group(3))}
            continue
        if current_block is not None:
            kv = re.match(r"^\s+([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*(?:#.*)?$", raw)
            if kv:
                current_block[kv.group(1)] = _unquote(kv.group(2))
    flush_block()
    return caps, outputs, errors


def parse_dependencies(text: str) -> tuple[list[dict], list[str]]:
    """dependencies[] のflow/block mappingをstdlibだけで読み取る。"""
    entries: list[dict] = []
    errors: list[str] = []
    section = None
    current_block: dict | None = None

    def flush_block(lineno: int) -> None:
        nonlocal current_block
        if current_block is None:
            return
        missing = [key for key in ("from", "to", "type") if not current_block.get(key)]
        if missing:
            errors.append(
                f"line {lineno}: dependency entry missing {','.join(missing)}: {current_block}"
            )
        else:
            entries.append(current_block)
        current_block = None

    lines = text.splitlines()
    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        top = TOP_KEY_RE.match(raw)
        if top:
            flush_block(lineno)
            section = top.group(1)
            continue
        if section != "dependencies":
            continue
        flow = FLOW_ENTRY_RE.match(raw)
        if flow:
            flush_block(lineno)
            entry = {k: _unquote(v) for k, v in KV_RE.findall(flow.group(1))}
            missing = [key for key in ("from", "to", "type") if not entry.get(key)]
            if missing:
                errors.append(
                    f"line {lineno}: dependency entry missing {','.join(missing)}: {stripped}"
                )
            else:
                entries.append(entry)
            continue
        block = BLOCK_ENTRY_RE.match(raw)
        if block:
            flush_block(lineno)
            current_block = {block.group(2): _unquote(block.group(3))}
            continue
        if current_block is not None:
            kv = re.match(r"^\s+([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*(?:#.*)?$", raw)
            if kv:
                current_block[kv.group(1)] = _unquote(kv.group(2))
                continue
        errors.append(f"line {lineno}: dependency entry is not a supported mapping: {stripped}")
    flush_block(len(lines) + 1)
    return entries, errors


def parse_external_dependencies(text: str) -> tuple[dict[str, dict], list[str]]:
    """Parse the supported external_dependencies owner/required-entrypoint subset."""

    result: dict[str, dict] = {}
    errors: list[str] = []
    section = False
    current: str | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        if re.match(r"^external_dependencies:\s*(?:#.*)?$", raw):
            section = True
            current = None
            continue
        if section and re.match(r"^[A-Za-z_][\w-]*:", raw):
            break
        if not section or not raw.strip() or raw.lstrip().startswith("#"):
            continue
        owner = re.match(r"^\s{2}([a-z][a-z0-9-]*):\s*(?:#.*)?$", raw)
        if owner:
            current = owner.group(1)
            result[current] = {}
            continue
        required = re.match(r"^\s{4}required_entry_points:\s*\[(.*)\]\s*(?:#.*)?$", raw)
        if required and current:
            entries = [_unquote(item) for item in required.group(1).split(",") if item.strip()]
            if not entries or len(entries) != len(set(entries)):
                errors.append(
                    f"line {lineno}: external dependency {current} requires a unique non-empty required_entry_points list"
                )
            result[current]["required_entry_points"] = entries
            continue
    for owner, spec in result.items():
        if "required_entry_points" not in spec:
            errors.append(
                f"external dependency {owner} must declare required_entry_points"
            )
    return result, errors


def _cap_ref(cap: dict) -> str | None:
    return cap.get("ref") or cap.get("path")


def check_duplicate_refs(caps: list[dict]) -> list[str]:
    seen: dict[str, int] = {}
    for cap in caps:
        ref = _cap_ref(cap)
        if ref:
            seen[ref] = seen.get(ref, 0) + 1
    return [
        f"duplicate capability ref: {ref} (declared {n} times)"
        for ref, n in seen.items()
        if n > 1
    ]


def _actual_public_surfaces(plugin_dir: Path) -> dict[str, set[str]]:
    return {
        "skill": {
            f"skills/{path.parent.name}"
            for path in plugin_dir.glob("skills/*/SKILL.md")
        },
        "agent": {
            f"agents/{path.stem}" for path in plugin_dir.glob("agents/*.md")
        },
        "command": {
            f"commands/{path.stem}" for path in plugin_dir.glob("commands/*.md")
        },
        "hook": {
            f"hooks/{path.name}"
            for path in plugin_dir.glob("hooks/*")
            if path.is_file() and path.suffix in {".py", ".sh"}
        },
    }


def _declared_public_surfaces(caps: list[dict], plugin_dir: Path) -> dict[str, set[str]]:
    actual_hooks = _actual_public_surfaces(plugin_dir)["hook"]
    hook_by_stem = {Path(ref).stem: ref for ref in actual_hooks}
    declared = {kind: set() for kind in ("skill", "agent", "command", "hook")}
    for cap in caps:
        kind = str(cap.get("kind", ""))
        if kind not in declared:
            continue
        ref = _canonical_cap_ref(cap)
        if kind == "skill":
            declared[kind].add(f"skills/{Path(ref).name}")
        elif kind in {"agent", "command"}:
            declared[kind].add(f"{kind}s/{Path(ref).stem}")
        elif ref.startswith("hook:"):
            stem = Path(ref.split("/", 1)[-1]).stem
            declared[kind].add(hook_by_stem.get(stem, f"hooks/{stem}"))
        else:
            declared[kind].add(f"hooks/{Path(ref).name}")
    return declared


def check_public_surface_parity(caps: list[dict], plugin_dir: Path) -> list[str]:
    """Composition is the exact public S/A/C/H inventory, not a sample."""

    findings: list[str] = []
    actual = _actual_public_surfaces(plugin_dir)
    declared = _declared_public_surfaces(caps, plugin_dir)
    for kind in ("skill", "agent", "command", "hook"):
        for ref in sorted(actual[kind] - declared[kind]):
            findings.append(f"composition omits {kind} surface: {ref}")
        for ref in sorted(declared[kind] - actual[kind]):
            findings.append(f"composition declares non-public {kind} surface: {ref}")
    return findings


def check_ref_exists(caps: list[dict], plugin_dir: Path) -> list[str]:
    findings: list[str] = []
    for cap in caps:
        kind = cap.get("kind", "")
        ref = _cap_ref(cap)
        if not ref:
            continue
        if ref.startswith("hook:"):
            if not HOOK_REF_RE.match(ref):
                findings.append(
                    f"malformed hook ref: {ref} (expected hook:<Event>[-<hint>]/<name>)"
                )
            continue
        target = plugin_dir / ref
        if target.is_file():
            continue
        if kind == "skill":
            if not (target / "SKILL.md").is_file():
                findings.append(f"capability ref not found: {ref} (expected {ref}/SKILL.md)")
        elif kind in ("agent", "command"):
            if not target.with_suffix(".md").is_file() and not target.is_dir():
                findings.append(f"capability ref not found: {ref} (expected {ref}.md)")
        else:
            if not target.exists():
                findings.append(f"capability ref not found: {ref}")
    return findings


def _canonical_cap_ref(cap: dict) -> str:
    ref = str(_cap_ref(cap) or "").strip().rstrip("/")
    kind = str(cap.get("kind", "")).strip()
    if kind == "skill" and ref.endswith("/SKILL.md"):
        return ref[: -len("/SKILL.md")]
    if kind in ("agent", "command") and ref.endswith(".md"):
        return ref[:-3]
    return ref


def _frontmatter_list(text: str, key: str) -> tuple[list[str], str | None]:
    """Read an inline or block string list from the first YAML frontmatter."""
    boundaries = list(FRONTMATTER_BOUNDARY_RE.finditer(text))
    if len(boundaries) < 2 or boundaries[0].start() != 0:
        return [], None
    body = text[boundaries[0].end() : boundaries[1].start()]
    lines = body.splitlines()
    for idx, raw in enumerate(lines):
        match = re.match(rf"^{re.escape(key)}\s*:\s*(.*?)\s*$", raw)
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            if not (value.startswith("[") and value.endswith("]")):
                return [], f"frontmatter {key} must be an inline list or block list"
            inner = value[1:-1].strip()
            if not inner:
                return [], None
            items = [_unquote(part) for part in inner.split(",")]
            if any(not item for item in items):
                return [], f"frontmatter {key} contains an empty item"
            return items, None
        items: list[str] = []
        for continuation in lines[idx + 1 :]:
            if not continuation.strip():
                continue
            item = re.match(r"^\s+-\s+(.+?)\s*$", continuation)
            if item:
                items.append(_unquote(item.group(1)))
                continue
            if re.match(r"^[A-Za-z_][\w-]*\s*:", continuation):
                break
            return [], f"frontmatter {key} block contains an unsupported line: {continuation.strip()}"
        return items, None
    return [], None


def _calls_set(dependencies: list[dict]) -> set[tuple[str, str]]:
    return {
        (str(dep.get("from", "")).strip(), str(dep.get("to", "")).strip())
        for dep in dependencies
        if str(dep.get("type", "")).strip() == "calls"
    }


def check_skill_script_dependencies(
    caps: list[dict], dependencies: list[dict], plugin_dir: Path
) -> list[str]:
    """Require every script_ref targeting a declared script capability to have a calls edge."""
    findings: list[str] = []
    calls = _calls_set(dependencies)
    plugin_root = plugin_dir.resolve()
    script_caps = {
        _canonical_cap_ref(cap) for cap in caps if cap.get("kind") == "script"
    }
    for cap in caps:
        if cap.get("kind") != "skill":
            continue
        source = _canonical_cap_ref(cap)
        skill_path = plugin_dir / source / "SKILL.md"
        if not skill_path.is_file():
            continue  # check_ref_exists owns the missing capability finding
        try:
            refs, parse_error = _frontmatter_list(
                skill_path.read_text(encoding="utf-8"), "script_refs"
            )
        except OSError as exc:
            findings.append(f"cannot read skill frontmatter for dependency parity: {source}: {exc}")
            continue
        if parse_error:
            findings.append(f"{source}/SKILL.md: {parse_error}")
            continue
        for declared in refs:
            target_path = (skill_path.parent / declared).resolve()
            try:
                target = target_path.relative_to(plugin_root).as_posix()
            except ValueError:
                continue  # cross-plugin refs are governed by external_dependencies
            if target not in script_caps:
                continue  # skill-private helper, not a bundle-level capability edge
            if (source, target) not in calls:
                findings.append(
                    f"missing calls dependency for skill script_ref: {source} -> {target}"
                )
    return findings


def check_command_dispatch_dependencies(
    caps: list[dict], dependencies: list[dict], plugin_dir: Path
) -> list[str]:
    """Require calls edges for same-bundle targets explicitly dispatched by commands."""
    findings: list[str] = []
    calls = _calls_set(dependencies)
    skills = {
        Path(_canonical_cap_ref(cap)).name: _canonical_cap_ref(cap)
        for cap in caps
        if cap.get("kind") == "skill"
    }
    scripts = {
        _canonical_cap_ref(cap)
        for cap in caps
        if cap.get("kind") == "script"
    }
    for cap in caps:
        if cap.get("kind") != "command":
            continue
        canonical = _canonical_cap_ref(cap)
        command_path = plugin_dir / f"{canonical}.md"
        if not command_path.is_file():
            continue  # check_ref_exists owns the missing capability finding
        try:
            body = command_path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(f"cannot read command body for dependency parity: {canonical}: {exc}")
            continue
        source = f"{canonical}.md"
        targets: set[str] = set()
        for name in SKILL_DISPATCH_RE.findall(body):
            if name in skills:
                targets.add(skills[name])
        for target in BACKTICK_SCRIPT_RE.findall(body):
            if target in scripts:
                targets.add(target)
        for target in sorted(targets):
            if (source, target) not in calls:
                findings.append(
                    f"missing calls dependency for command dispatch: {source} -> {target}"
                )
    return findings


def _load_package_contract(plugin_dir: Path) -> tuple[dict, str | None]:
    path = plugin_dir / "references" / "package-contract.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"package contract cannot be read: {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"package contract must be an object: {path}"
    return payload, None


def _repo_and_slug(plugin_dir: Path) -> tuple[Path, str] | None:
    if plugin_dir.parent.name != "plugins":
        return None
    return plugin_dir.parent.parent, plugin_dir.name


def _cross_endpoint(endpoint: str, plugin_dir: Path) -> tuple[str, str, str] | None:
    """Return (owner, kind plural, entrypoint) for a structured plugin endpoint."""

    normalized = endpoint.strip().strip("\"'")
    match = re.match(
        r"^\.\./(?P<owner>[a-z][a-z0-9-]*)/(?P<kind>skills|agents|commands|hooks)/(?P<entry>[^/]+)",
        normalized,
    )
    if match is None:
        match = re.match(
            r"^plugins/(?P<owner>[a-z][a-z0-9-]*)/(?P<kind>skills|agents|commands|hooks)/(?P<entry>[^/]+)",
            normalized,
        )
    if match is None:
        return None
    kind = match.group("kind")
    entry = match.group("entry")
    if kind == "skills":
        entry = entry.removesuffix("/SKILL.md")
    elif kind in {"agents", "commands"}:
        entry = Path(entry).stem
    return match.group("owner"), kind, entry


def check_cross_plugin_dependencies(
    dependencies: list[dict], plugin_dir: Path
) -> list[str]:
    """Cross-plugin routes must resolve to a public entry point and package edge."""

    context = _repo_and_slug(plugin_dir)
    if context is None:
        return []
    repo, slug = context
    caller_contract, error = _load_package_contract(plugin_dir)
    findings = [error] if error else []
    package_edges = caller_contract.get("depends_on", [])
    if not isinstance(package_edges, list):
        package_edges = []
    for dep in dependencies:
        dep_type = str(dep.get("type", ""))
        for side in ("from", "to"):
            endpoint = str(dep.get(side, ""))
            cross = _cross_endpoint(endpoint, plugin_dir)
            if cross is None:
                if endpoint.startswith("../") or endpoint.startswith("plugins/"):
                    findings.append(
                        f"cross-plugin endpoint must name a public skills/agents/commands/hooks entry point: {endpoint}"
                    )
                continue
            owner, kind, entry = cross
            owner_dir = repo / "plugins" / owner
            owner_contract, owner_error = _load_package_contract(owner_dir)
            if owner_error:
                findings.append(owner_error)
                continue
            declared = owner_contract.get("entry_points", {}).get(kind, [])
            expected = entry
            if kind == "hooks":
                # Hook package identities retain their language suffix.
                expected = Path(endpoint).name
            if not isinstance(declared, list) or expected not in declared:
                findings.append(
                    f"cross-plugin required entry point is not declared by {owner}: {kind}.{expected}"
                )
            # called-by is descriptive incoming provenance.  All executable
            # outgoing relations require the package installation edge.
            outgoing = side == "to" and dep_type != "called-by"
            if outgoing and owner != slug and owner not in package_edges:
                findings.append(
                    f"cross-plugin dependency edge missing from package contract: {owner}"
                )
    return findings


def check_external_dependencies(
    external: dict[str, dict], plugin_dir: Path
) -> list[str]:
    context = _repo_and_slug(plugin_dir)
    if context is None:
        return []
    repo, _ = context
    caller_contract, error = _load_package_contract(plugin_dir)
    findings = [error] if error else []
    package_edges = caller_contract.get("depends_on", [])
    if not isinstance(package_edges, list):
        package_edges = []
    for owner, spec in sorted(external.items()):
        if owner not in package_edges:
            findings.append(
                f"external dependency edge missing from package contract: {owner}"
            )
        owner_dir = repo / "plugins" / owner
        owner_contract, owner_error = _load_package_contract(owner_dir)
        if owner_error:
            findings.append(owner_error)
            continue
        entry_points = owner_contract.get("entry_points", {})
        declared = {
            entry
            for values in entry_points.values()
            if isinstance(values, list)
            for entry in values
        }
        actual = {
            path.parent.name for path in owner_dir.glob("skills/*/SKILL.md")
        } | {
            path.stem for path in owner_dir.glob("agents/*.md")
        } | {
            path.stem for path in owner_dir.glob("commands/*.md")
        } | {
            path.name for path in owner_dir.glob("hooks/*")
            if path.is_file() and path.suffix in {".py", ".sh"}
        }
        for required in spec.get("required_entry_points", []):
            if required not in declared or required not in actual:
                findings.append(
                    f"external required entry point is unresolved: {owner}.{required}"
                )
    return findings


def _wired_hook_counts(plugin_json: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event, groups in (plugin_json.get("hooks") or {}).items():
        n = 0
        for group in groups or []:
            n += len(group.get("hooks") or [])
        counts[event] = n
    return counts


def _resolve_hook_manifest(plugin_json: dict, plugin_dir: Path) -> dict:
    """Normalize inline hooks and Claude's supported external hooks manifest form."""
    raw = plugin_json.get("hooks")
    if raw is None and (plugin_dir / "hooks" / "hooks.json").is_file():
        raw = "./hooks/hooks.json"
    if not isinstance(raw, str):
        return plugin_json
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"external hooks path must stay inside plugin: {raw}")
    plugin_root = plugin_dir.resolve()
    path = (plugin_dir / rel).resolve()
    if not path.is_relative_to(plugin_root):
        raise ValueError(f"external hooks path escapes plugin: {raw}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"external hooks manifest read/parse error: {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"external hooks manifest must be an object: {path}")
    hooks = manifest.get("hooks", manifest)
    if not isinstance(hooks, dict):
        raise ValueError(f"external hooks manifest hooks must be an object: {path}")
    normalized = dict(plugin_json)
    normalized["hooks"] = hooks
    return normalized


def check_hook_wiring(caps: list[dict], plugin_json: dict | None) -> list[str]:
    declared: dict[str, int] = {}
    for cap in caps:
        ref = _cap_ref(cap) or ""
        m = HOOK_REF_RE.match(ref)
        if m:
            declared[m.group(1)] = declared.get(m.group(1), 0) + 1
    if plugin_json is None:
        if declared:
            return [
                "hooks declared in composition but .claude-plugin/plugin.json not found: "
                + ", ".join(sorted(declared))
            ]
        return []
    wired = _wired_hook_counts(plugin_json)
    findings: list[str] = []
    for event in sorted(set(declared) | set(wired)):
        d, w = declared.get(event, 0), wired.get(event, 0)
        if d != w:
            findings.append(
                f"hook wiring mismatch for event {event}: "
                f"composition declares {d}, plugin.json wires {w}"
            )
    return findings


def _is_path_like(entry: str) -> bool:
    return "/" in entry or "." in entry


def check_outputs(outputs: list[str], plugin_dir: Path) -> list[str]:
    warnings: list[str] = []
    for entry in outputs:
        if not _is_path_like(entry):
            continue  # 概念名 (CapabilityManifest 等) は対象外
        if any(c in entry for c in GLOB_CHARS):
            if not any(plugin_dir.glob(entry)):
                warnings.append(f"output path has no match yet: {entry} (WARN のみ・生成前は正当)")
        elif not (plugin_dir / entry).exists():
            warnings.append(f"output path not found: {entry} (WARN のみ・生成前は正当)")
    return warnings


def lint_composition(path: Path) -> tuple[list[str], list[str], int | None]:
    """Returns (findings, warnings, error_exit). error_exit は parse/IO 不能時のみ非 None。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: read error: {e}"], [], 2
    plugin_dir = path.parent
    caps, outputs, parse_errors = parse_composition(text)
    dependencies, dependency_parse_errors = parse_dependencies(text)
    external_dependencies, external_parse_errors = parse_external_dependencies(text)
    parse_errors.extend(dependency_parse_errors)
    parse_errors.extend(external_parse_errors)
    if parse_errors:
        return [f"{path}: {e}" for e in parse_errors], [], 2
    if not caps:
        return [f"{path}: no capabilities entries parsed (capabilities: section missing or empty)"], [], 2

    plugin_json: dict | None = None
    pj_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if pj_path.is_file():
        try:
            plugin_json = json.loads(pj_path.read_text(encoding="utf-8"))
            plugin_json = _resolve_hook_manifest(plugin_json, plugin_dir)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            return [f"{pj_path}: read/parse error: {e}"], [], 2

    findings: list[str] = []
    findings += check_duplicate_refs(caps)
    findings += check_ref_exists(caps, plugin_dir)
    findings += check_public_surface_parity(caps, plugin_dir)
    findings += check_hook_wiring(caps, plugin_json)
    findings += check_skill_script_dependencies(caps, dependencies, plugin_dir)
    findings += check_command_dispatch_dependencies(caps, dependencies, plugin_dir)
    findings += check_cross_plugin_dependencies(dependencies, plugin_dir)
    findings += check_external_dependencies(external_dependencies, plugin_dir)
    warnings = check_outputs(outputs, plugin_dir)
    return (
        [f"{path}: {f}" for f in findings],
        [f"{path}: WARN: {w}" for w in warnings],
        None,
    )


# ── self-test fixtures ──────────────────────────────────────────────

_FIXTURE_PASS = """\
name: fixture-plugin
kind: plugin-composition

contract:
  interface:
    inputs: [user-request]
    outputs: [EVALS.json, proposals/*.md, CapabilityManifest]

capabilities:
  - { kind: skill, ref: skills/run-alpha, tier: core }
  - { kind: agent, ref: agents/beta-agent, tier: core }
  - { kind: hook, ref: "hook:Stop/gamma-trigger", tier: core }
"""

_FIXTURE_PLUGIN_JSON = {
    "name": "fixture-plugin",
    "hooks": {
        "Stop": [
            {"matcher": ".*", "hooks": [{"type": "command", "command": "python3 x.py"}]}
        ]
    },
}


def _build_fixture(root: Path, composition: str, plugin_json: dict | None) -> Path:
    (root / "skills" / "run-alpha").mkdir(parents=True)
    (root / "skills" / "run-alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
    if "agents/beta-agent" in composition:
        (root / "agents").mkdir()
        (root / "agents" / "beta-agent.md").write_text("# beta\n", encoding="utf-8")
    if "gamma-trigger" in composition:
        (root / "hooks").mkdir()
        (root / "hooks" / "gamma-trigger.py").write_text("# hook\n", encoding="utf-8")
    (root / "EVALS.json").write_text("{}\n", encoding="utf-8")
    if plugin_json is not None:
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(plugin_json), encoding="utf-8"
        )
    comp = root / "plugin-composition.yaml"
    comp.write_text(composition, encoding="utf-8")
    return comp


def self_test() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # 1. 合格 fixture: FAIL 0 / WARN 1 (proposals/*.md 未生成)
        comp = _build_fixture(base / "ok", _FIXTURE_PASS, _FIXTURE_PLUGIN_JSON)
        findings, warnings, err = lint_composition(comp)
        if err is not None or findings:
            failures.append(f"case1 pass fixture: unexpected findings={findings} err={err}")
        if not any("proposals/*.md" in w for w in warnings):
            failures.append(f"case1 pass fixture: expected proposals WARN, got {warnings}")

        # 2. ref 重複 → FAIL
        dup = _FIXTURE_PASS + "  - { kind: skill, ref: skills/run-alpha, tier: core }\n"
        comp = _build_fixture(base / "dup", dup, _FIXTURE_PLUGIN_JSON)
        findings, _, err = lint_composition(comp)
        if err is not None or not any("duplicate capability ref" in f for f in findings):
            failures.append(f"case2 duplicate: expected FAIL, got findings={findings} err={err}")

        # 3. ref 実体不在 → FAIL
        ghost = _FIXTURE_PASS + "  - { kind: skill, ref: skills/run-ghost, tier: core }\n"
        comp = _build_fixture(base / "ghost", ghost, _FIXTURE_PLUGIN_JSON)
        findings, _, err = lint_composition(comp)
        if err is not None or not any("run-ghost" in f for f in findings):
            failures.append(f"case3 missing ref: expected FAIL, got findings={findings} err={err}")

        # 4. hook 配線数不一致 → FAIL
        comp = _build_fixture(
            base / "hookless", _FIXTURE_PASS, {"name": "fixture-plugin", "hooks": {}}
        )
        findings, _, err = lint_composition(comp)
        if err is not None or not any("hook wiring mismatch" in f for f in findings):
            failures.append(f"case4 hook mismatch: expected FAIL, got findings={findings} err={err}")

        # 5. block 形 entry (path キー) も読める
        block = (
            "name: fixture-plugin\ncapabilities:\n"
            "  - kind: skill\n    path: skills/run-alpha/SKILL.md\n"
        )
        comp = _build_fixture(base / "block", block, None)
        findings, _, err = lint_composition(comp)
        if err is not None or findings:
            failures.append(f"case5 block style: unexpected findings={findings} err={err}")

    if failures:
        for f in failures:
            sys.stderr.write(f"self-test FAIL: {f}\n")
        return 1
    sys.stdout.write("self-test ok: 5 case(s) passed\n")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    targets = [Path(a) for a in argv if not a.startswith("--")]
    if not targets:
        sys.stderr.write(
            "usage: lint-plugin-composition.py <plugin-composition.yaml> [...] | --self-test\n"
        )
        return 2
    all_findings: list[str] = []
    all_warnings: list[str] = []
    parse_error_seen = False
    for path in targets:
        findings, warnings, err = lint_composition(path)
        if err is not None:
            parse_error_seen = True
            all_findings.extend(findings)
            all_warnings.extend(warnings)
            continue
        all_findings.extend(findings)
        all_warnings.extend(warnings)
    for w in all_warnings:
        sys.stderr.write(w + "\n")
    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 2 if parse_error_seen else 1
    sys.stdout.write(
        f"OK: {len(targets)} composition file(s) passed"
        f" ({len(all_warnings)} warning(s))\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
