#!/usr/bin/env python3
# /// script
# name: doc-to-skill-adapter
# version: 0.1.0
# purpose: 設計書 doc/**/NN-*.md を 1 artifact として assign-skill-design-evaluator に渡せる brief JSON に変換（26章ドッグフード起動装置）
# inputs:
#   - --doc: 対象 .md ファイル（必須）
#   - --out: 出力 brief JSON のパス（必須）
# outputs:
#   - file: brief JSON（skill_name / description / trigger_conditions / artifact_path / source_tier=internal）
#   - exit: 0=OK / 1=入力エラー / 2=usage
# requires-python: ">=3.9"
# dependencies: []
# contexts: [B, E]
# network: false
# write-scope: output-dir
# ///
"""設計書 1 章を Skill candidate brief に変換する薄ラッパ。"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path


def derive_skill_name(path: Path) -> str:
    stem = path.stem
    m = re.match(r"^(\d+)[-_](.+)$", stem)
    base = m.group(2) if m else stem
    base = re.sub(r"[^a-zA-Z0-9-]+", "-", base.lower()).strip("-")
    return f"doc-{m.group(1)}-{base}" if m else f"doc-{base}"


def extract_first_h1(text: str) -> str:
    for ln in text.splitlines():
        if ln.startswith("# "):
            return ln[2:].strip()
    return ""


def extract_description(text: str) -> str:
    in_purpose = False
    chunks: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("## ") and ("目的" in s or "Purpose" in s):
            in_purpose = True
            continue
        if in_purpose:
            if s.startswith("## ") or s.startswith("---"):
                break
            if s and not s.startswith("#"):
                chunks.append(s)
                if sum(len(c) for c in chunks) > 200:
                    break
    desc = " ".join(chunks)
    return (desc[:197] + "...") if len(desc) > 200 else desc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    p = Path(args.doc)
    if not p.is_file():
        print(f"error: doc not found: {p}", file=sys.stderr)
        return 1
    text = p.read_text(encoding="utf-8")
    title = extract_first_h1(text)
    desc = extract_description(text) or title
    skill_name = derive_skill_name(p)

    brief = {
        "skill_name": skill_name,
        "kind": "ref",
        "description": desc,
        "trigger_conditions": [
            f"設計書 {p.stem} を評価対象として採点するとき",
            "メタSkillドッグフーディング（26章）を実行するとき",
        ],
        "artifact_path": str(p),
        "title": title,
        "source": str(p),
        "source_tier": "internal",
        "key_constraints": ["設計書本文行数 ≤ 300", "description は 200 文字以内"],
        "open_questions": [],
    }
    Path(args.out).write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
