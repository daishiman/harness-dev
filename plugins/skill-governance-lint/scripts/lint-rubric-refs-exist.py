#!/usr/bin/env python3
# /// script
# name: lint-rubric-refs-exist
# version: 0.1.0
# purpose: SKILL.md frontmatter の rubric_refs と rubric-registry.json の rubrics[].rubric が物理存在することを検証する
# inputs:
#   - argv[1..]: 検査対象 SKILL.md パス (省略時は plugins/harness-creator/skills/**/SKILL.md を走査)
# outputs:
#   - stdout: 検査結果サマリ
#   - exit code: 0=PASS / 1=FAIL (未解決 rubric_refs を検出)
# requires-python: ">=3.9"
# dependencies: []
# contexts: [C, E]
# network: false
# write-scope: none
# ///
"""rubric_refs の参照先が物理存在するかを CI / pre-commit で検証する。設計書29 §6.3 fail-fast を機械実装。"""
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", os.getcwd())).resolve()


def find_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    current_key = None
    def strip_comment(s: str) -> str:
        idx = s.find(" #")
        return s if idx < 0 else s[:idx].rstrip()

    for line in m.group(1).splitlines():
        if line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_key:
            fm[current_key].append(strip_comment(line[4:].strip()))
        elif ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            v = strip_comment(v.strip())
            if v == "":
                fm[k] = []
                current_key = k
            else:
                fm[k] = v
                current_key = None
    return fm


def resolve_rubric_ref(ref: str, skill_dir: Path) -> Path:
    if ref.startswith("ref-"):
        # 正規パスは <skill>/references/rubric.json (lint-skill-tree が直下配置を禁止)
        candidates = sorted(PROJECT_ROOT.glob(f"plugins/*/skills/{ref}/references/rubric.json"))
        candidates.append(PROJECT_ROOT / ".claude" / "skills" / ref / "references" / "rubric.json")
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]
    return (skill_dir / ref).resolve()


def check_skill_md(skill_md: Path) -> list:
    failures = []
    fm = find_frontmatter(skill_md)
    refs = fm.get("rubric_refs", [])
    if not isinstance(refs, list):
        return failures
    for ref in refs:
        resolved = resolve_rubric_ref(ref, skill_md.parent)
        if not resolved.exists():
            failures.append(f"  {skill_md}: rubric_refs={ref!r} -> {resolved} (NOT FOUND)")
    return failures


def check_registry() -> list:
    failures = []
    registry = PROJECT_ROOT / "plugins" / "skill-governance-config" / "config" / "rubric-registry.json"
    if not registry.exists():
        return failures
    data = json.loads(registry.read_text(encoding="utf-8"))
    for r in data.get("rubrics", []):
        p = PROJECT_ROOT / r["rubric"]
        if not p.exists():
            failures.append(f"  rubric-registry.json: domain={r['domain']} rubric={r['rubric']} (NOT FOUND)")
        for up in r.get("upstream", []):
            up_path = PROJECT_ROOT / up
            if not up_path.exists():
                failures.append(f"  rubric-registry.json: upstream={up} (NOT FOUND)")
    return failures


def main() -> int:
    targets = []
    if len(sys.argv) > 1:
        targets = [Path(p) for p in sys.argv[1:]]
    else:
        targets.extend(PROJECT_ROOT.glob("plugins/harness-creator/skills/*/SKILL.md"))
        base = PROJECT_ROOT / ".claude" / "skills"
        if base.exists():
            targets.extend(base.glob("*/SKILL.md"))

    all_failures = []
    for t in targets:
        if t.exists():
            all_failures.extend(check_skill_md(t))
    all_failures.extend(check_registry())

    if all_failures:
        print("FAIL: rubric_refs 未解決:", file=sys.stderr)
        for f in all_failures:
            print(f, file=sys.stderr)
        return 1

    print(f"PASS: rubric_refs 全件解決 ({len(targets)} SKILL.md checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
