#!/usr/bin/env python3
# /// script
# name: migrate-to-brief
# purpose: Convert migrate audit JSON into run-build-skill brief JSON.
# inputs:
#   - argv: audit JSON path and owner options
# outputs:
#   - stdout: brief JSON
#   - stderr: validation errors
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""audit.py の出力 JSON から run-build-skill 起動用 brief を生成する。

doc/21 source-tier の語彙を audit.origin から自動派生し、
doc/21 の単一の真実の場所 (single source of truth) をスクリプト側に集約する。
owner は --owner 引数で受け取り、未指定時は明示プレースホルダ
"TODO_SET_OWNER" を埋める。validate-frontmatter.py の未展開変数検出
({{...}}) と協調して、未解決値が成果物に流れることを防ぐ。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# doc/21 source-tier 語彙の唯一の真実の場所（origin → tier マッピング）
ORIGIN_TO_TIER = {
    "article": "article-text",       # 元記事 Markdown 由来
    "internal-doc": "internal",      # 内製設計書 (doc/) 由来
    "external-spec": "external-spec",  # 外部公式仕様 (claude.com docs 等)
    "unknown": "internal",           # 判定不能時は保守的に internal
}


def to_brief(audit: dict, owner: str) -> list[dict]:
    origin = audit.get("origin", "unknown")
    source_tier = ORIGIN_TO_TIER.get(origin, "internal")
    briefs = []
    for sec in audit["sections"]:
        if sec["suggested_skill_name"] is None:
            continue
        briefs.append({
            "skill_name": sec["suggested_skill_name"],
            "kind": sec["classification"],
            "origin_heading": sec["heading"],
            "source": audit["input_file"],
            "source-tier": source_tier,
            "origin": origin,
            "rationale": sec["rationale"],
            "owner": owner,
        })
    return briefs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-json", required=True)
    ap.add_argument("--output", default="-")
    ap.add_argument(
        "--owner",
        default="TODO_SET_OWNER",
        help="Skill の owner フィールド値。未指定時は明示プレースホルダ "
             "'TODO_SET_OWNER' が入り、validate-frontmatter.py で検出される。"
             " 量産時は team-platform 等の実体値を渡すこと。",
    )
    args = ap.parse_args()

    audit = json.loads(Path(args.audit_json).read_text(encoding="utf-8"))
    briefs = to_brief(audit, owner=args.owner)

    payload = json.dumps({"briefs": briefs, "count": len(briefs)}, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(payload)
    else:
        Path(args.output).write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
