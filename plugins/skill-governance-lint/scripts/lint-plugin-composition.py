#!/usr/bin/env python3
# /// script
# name: lint-plugin-composition
# purpose: plugin-composition.yaml の capabilities 重複/実在と hooks↔plugin.json 配線対応を検査する。
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


def check_ref_exists(caps: list[dict], plugin_dir: Path) -> list[str]:
    findings: list[str] = []
    for cap in caps:
        kind = cap.get("kind", "")
        ref = _cap_ref(cap)
        if not ref:
            continue
        if kind == "hook" or ref.startswith("hook:"):
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


def _wired_hook_counts(plugin_json: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event, groups in (plugin_json.get("hooks") or {}).items():
        n = 0
        for group in groups or []:
            n += len(group.get("hooks") or [])
        counts[event] = n
    return counts


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
    if parse_errors:
        return [f"{path}: {e}" for e in parse_errors], [], 2
    if not caps:
        return [f"{path}: no capabilities entries parsed (capabilities: section missing or empty)"], [], 2

    plugin_json: dict | None = None
    pj_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if pj_path.is_file():
        try:
            plugin_json = json.loads(pj_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            return [f"{pj_path}: read/parse error: {e}"], [], 2

    findings: list[str] = []
    findings += check_duplicate_refs(caps)
    findings += check_ref_exists(caps, plugin_dir)
    findings += check_hook_wiring(caps, plugin_json)
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
    (root / "agents").mkdir()
    (root / "agents" / "beta-agent.md").write_text("# beta\n", encoding="utf-8")
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
    for path in targets:
        findings, warnings, err = lint_composition(path)
        if err is not None:
            for f in findings:
                sys.stderr.write(f + "\n")
            return err
        all_findings.extend(findings)
        all_warnings.extend(warnings)
    for w in all_warnings:
        sys.stderr.write(w + "\n")
    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 1
    sys.stdout.write(
        f"OK: {len(targets)} composition file(s) passed"
        f" ({len(all_warnings)} warning(s))\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
