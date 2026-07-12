#!/usr/bin/env python3
# /// script
# name: lint-plugin-manifest
# purpose: plugin.json 宣言と実体ディレクトリ(skills/agents/hooks)の差分を機械検査し governance drift を防ぐ。
# inputs:
#   - .claude-plugin/plugin.json + skills/*/SKILL.md + agents/*.md + hooks/*
# outputs:
#   - stdout: 違反一覧 / exit: 0=OK / 2=FAIL
# contexts: [CI, pre-commit, manual]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
# WHY: plugin.json の宣言と実体の乖離が scripts/lib/agents の固定値拡散の真因。
# 宣言↔ファイルシステム↔SKILL.md frontmatter の三者整合を機械検査することで
# governance を取り戻す (rubric_refs 空など内容統治の欠落も同時に検出)。
import argparse
import json
import re
import sys
from pathlib import Path

DESC_LIMIT = 120


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_frontmatter(skill_md: Path) -> dict:
    # WHY: PyYAML を避け標準ライブラリのみで最低限の frontmatter (key: value / list) を取得
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    fm: dict = {}
    current_key = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        # WHY: YAML list 継続行は "  - value" のようにインデント込みで来るため lstrip 必須
        stripped = line.lstrip()
        if stripped.startswith("- ") and current_key is not None:
            val = stripped[2:].strip().strip("\"'")
            existing = fm.get(current_key)
            if existing is None:
                fm[current_key] = [val]
            elif isinstance(existing, list):
                existing.append(val)
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if v == "" or v == "[]":
                fm[k] = [] if v == "[]" else None
                current_key = k
            elif v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                fm[k] = [s.strip().strip("\"'") for s in inner.split(",")] if inner else []
                current_key = None
            else:
                fm[k] = v.strip("\"'")
                current_key = None
    return fm


def lint(plugin_root: Path) -> list[str]:
    violations: list[str] = []
    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        return [f"FAIL: plugin.json not found at {manifest_path}"]
    manifest = load_json(manifest_path)

    desc = manifest.get("description", "")
    if len(desc) > DESC_LIMIT:
        violations.append(f"WARN: description {len(desc)} chars exceeds {DESC_LIMIT}")

    skill_names: set[str] = set()
    for s in manifest.get("skills", []):
        name = s.get("name", "")
        skill_names.add(name)
        sp = plugin_root / s.get("path", "")
        if not sp.is_dir():
            violations.append(f"FAIL: skill path missing: {sp}")
            continue
        skill_md = sp / "SKILL.md"
        if not skill_md.exists():
            violations.append(f"FAIL: SKILL.md missing under {sp}")
            continue
        fm = parse_frontmatter(skill_md)
        rr = fm.get("rubric_refs")
        if rr is None or (isinstance(rr, list) and len(rr) == 0):
            violations.append(f"FAIL: rubric_refs empty/missing in {skill_md}")

    for a in manifest.get("agents", []):
        ap = plugin_root / a.get("path", "")
        if not ap.exists():
            violations.append(f"FAIL: agent file missing: {ap}")
        skill_link = a.get("skill")
        if skill_link and skill_link not in skill_names:
            violations.append(f"FAIL: agent {a.get('name')} references unknown skill '{skill_link}'")

    hooks = manifest.get("hooks", {})
    for event, entries in hooks.items():
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                m = re.search(r"\$CLAUDE_PLUGIN_ROOT/(\S+)", cmd)
                if m:
                    target = plugin_root / m.group(1)
                    if not target.exists():
                        violations.append(f"FAIL: hook command target missing: {target} (event={event})")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plugin-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    args = parser.parse_args()
    violations = lint(args.plugin_root)
    if not violations:
        print(f"OK: {args.plugin_root.name} manifest passes")
        return 0
    has_fail = any(v.startswith("FAIL") for v in violations)
    for v in violations:
        print(v)
    return 2 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
