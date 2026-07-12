#!/usr/bin/env python3
# /// script
# name: backfill-source-tier
# purpose: Backfill doc/21 source traceability fields into existing SKILL.md files.
# inputs:
#   - argv: --skills-dir and optional --dry-run
# outputs:
#   - stdout: changed or skipped files
#   - file: updated SKILL.md files unless --dry-run
# contexts: [A, B]
# network: false
# write-scope: output-dir
# dependencies: []
# requires-python: ">=3.9"
# ///
"""既存 SKILL.md 群に doc/21 出典追跡フィールドを一括追記する。

すでに source: / source-tier: / last-audited: / audit-trigger: のいずれかが
存在する場合はスキップ（idempotent）。

usage:
  python3 backfill-source-tier.py --skills-dir plugins/harness-creator/skills [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "source": "doc/ClaudeCodeスキルの設計書/",
    "source-tier": "internal",
    "last-audited": "",  # 実行時に補完
    "audit-trigger": "quarterly",
}


def has_field(fm_block: str, field: str) -> bool:
    return re.search(rf"^{re.escape(field)}:", fm_block, re.MULTILINE) is not None


def insert_into_frontmatter(text: str, today: str) -> tuple[str, list[str]]:
    """frontmatter (---..---) を見つけて必須フィールドを補完。"""
    parts = text.split("---", 2)
    if len(parts) < 3 or not text.startswith("---"):
        return text, ["no-frontmatter"]

    fm = parts[1]
    inserted: list[str] = []
    new_lines: list[str] = []
    for field, default in REQUIRED_FIELDS.items():
        if has_field(fm, field):
            continue
        val = default or today
        if field == "last-audited":
            val = today
        new_lines.append(f"{field}: {val}")
        inserted.append(field)

    if not new_lines:
        return text, []

    # frontmatter 末尾（最後の改行直前）に挿入
    fm_stripped = fm.rstrip("\n")
    fm_new = fm_stripped + "\n# auto-backfilled by backfill-source-tier.py (doc/21)\n" \
             + "\n".join(new_lines) + "\n"
    new_text = "---" + fm_new + "---" + parts[2]
    return new_text, inserted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--today", default=None,
                    help="ISO date (YYYY-MM-DD) を明示。省略時は system 日付")
    args = ap.parse_args()

    today = args.today
    if not today:
        from datetime import date
        today = date.today().isoformat()

    skills_dir = Path(args.skills_dir)
    if not skills_dir.is_dir():
        print(f"not a directory: {skills_dir}", file=sys.stderr)
        return 2

    modified = 0
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        new_text, inserted = insert_into_frontmatter(text, today)
        if inserted:
            modified += 1
            print(f"[{skill_md.parent.name}] backfilled: {', '.join(inserted)}")
            if not args.dry_run:
                skill_md.write_text(new_text, encoding="utf-8")
        else:
            print(f"[{skill_md.parent.name}] up-to-date")

    print(f"\n{'(dry-run) ' if args.dry_run else ''}modified: {modified}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
