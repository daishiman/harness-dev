#!/usr/bin/env python3
"""inventory-skill-references.py - 外部参照棚卸しスクリプト (P2-3)

各 Skill の外部参照 (scripts/, references/, 他 Skill, ハードコード path) を
eval-log/phase0-reference-inventory.json に書き出す。

設計書 06 第17条の Phase 0 必須要件に対応。

Usage:
  python3 scripts/inventory-skill-references.py
  python3 scripts/inventory-skill-references.py --skills-dir plugins/harness-creator/skills
  python3 scripts/inventory-skill-references.py --output eval-log/phase0-reference-inventory.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILL_REF_RE = re.compile(
    r'(?:Skill\(|pair:\s*|rubric_refs:\s*|reference_refs:\s*|script_refs:\s*)'
    r'([a-z][a-z0-9-]+)'
)
HARDCODE_RE = re.compile(r'(?:\.claude/skills/|plugins/harness-creator/skills/)([a-z][a-z0-9-]+)')
SCRIPT_REF_RE = re.compile(r'(?:python3|source)\s+([\w./\-]+\.(?:py|sh))')
REFS_FILE_RE = re.compile(r'references/([\w\-\.]+)')


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    current_list_key = None
    for raw in parts[1].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            if not line.startswith(" "):
                current_list_key = None
            continue
        m_item = re.match(r"^\s+-\s+(.+?)\s*$", line)
        if m_item and current_list_key is not None:
            fm.setdefault(current_list_key, [])
            if isinstance(fm[current_list_key], list):
                fm[current_list_key].append(m_item.group(1).strip())
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val == "":
                fm[key] = ""
                current_list_key = key
            else:
                fm[key] = val
                current_list_key = None
    return fm


def inventory_skill(skill_dir: Path) -> dict:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"name": skill_dir.name, "error": "SKILL.md not found"}

    text = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    # frontmatter から明示的参照を収集
    explicit_refs: list[str] = []
    for field in ("rubric_refs", "reference_refs", "script_refs"):
        items = fm.get(field)
        if isinstance(items, list):
            explicit_refs.extend(items)
        elif isinstance(items, str) and items:
            explicit_refs.append(items)

    # pair: フィールド
    pair = fm.get("pair", "")
    if pair:
        explicit_refs.append(f"pair:{pair}")

    # base: フィールド (wrap-* 用)
    base = fm.get("base", "")
    if base:
        explicit_refs.append(f"base:{base}")

    # 本文中のハードコードパス
    hardcode_paths = list(set(HARDCODE_RE.findall(text)))

    # 本文中のスクリプト参照
    script_refs = list(set(SCRIPT_REF_RE.findall(text)))

    # 本文中の references/ ファイル参照
    refs_files = list(set(REFS_FILE_RE.findall(text)))

    # references/ 実ファイル
    actual_refs: list[str] = []
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        actual_refs = [f.name for f in sorted(refs_dir.iterdir()) if f.is_file()]

    return {
        "name": fm.get("name", skill_dir.name),
        "kind": fm.get("kind", ""),
        "effect": fm.get("effect", ""),
        "frontmatter_refs": explicit_refs,
        "hardcode_paths": hardcode_paths,
        "script_refs_in_body": script_refs,
        "refs_files_mentioned": refs_files,
        "actual_references_files": actual_refs,
        "resource_map_exists": (refs_dir / "resource-map.yaml").exists() if refs_dir.is_dir() else False,
    }


def main() -> int:
    args = sys.argv[1:]

    skills_dir_override = None
    output_path = Path("eval-log/phase0-reference-inventory.json")

    i = 0
    while i < len(args):
        if args[i] == "--skills-dir" and i + 1 < len(args):
            skills_dir_override = Path(args[i + 1])
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        else:
            i += 1

    repo_root = Path(".").resolve()
    skills_base = skills_dir_override or (repo_root / "plugins" / "harness-creator" / "skills")
    if not skills_base.is_dir():
        print(f"ERROR: skills directory not found: {skills_base}", file=sys.stderr)
        return 2

    inventory = []
    for skill_dir in sorted(skills_base.iterdir()):
        if skill_dir.is_dir():
            inventory.append(inventory_skill(skill_dir))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-18",
                "skills_dir": str(skills_base),
                "skill_count": len(inventory),
                "inventory": inventory,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"written: {output_path} ({len(inventory)} skills)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
