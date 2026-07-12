#!/usr/bin/env python3
"""Build deterministic sheet.json five_axes from the Phase 4 sheet.md."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


AXES = ["出力先", "情報源", "共有相手", "真の課題", "ナレッジ資産"]
DEPTH_TO_ROW_DEPTH = {
    "light": "shallow",
    "quick": "shallow",
    "standard": "standard",
    "detailed": "deep",
    "deep": "deep",
}


def _pick_axis(text: str, axis: str) -> str:
    match = re.search(rf"#+\s*{re.escape(axis)}\s*\n(.+?)(?=\n#+\s|\Z)", text, re.S)
    if not match:
        return ""
    lines = [line.strip(" \t-") for line in match.group(1).splitlines()]
    value = " / ".join(line for line in lines if line.strip())
    return value.strip()


def extract_procedure(sheet_text: str):
    """sheet.md の『現状手順』セクション内の ```json フェンスから procedure ブロックを抽出する。
    節が無ければ None (procedure 未収集の後方互換)。JSON パース不能なら ValueError。
    procedure ブロックの完全性判定は plugin-root scripts/validate-procedure-completeness.py が担う
    (本スクリプトは構造抽出のみで完全性は重複検証しない)。"""
    section = re.search(r"#+\s*現状手順[^\n]*\n(.*?)(?=\n#+\s|\Z)", sheet_text, re.S)
    if not section:
        return None
    block = re.search(r"```json\s*\n(.+?)\n```", section.group(1), re.S)
    if not block:
        return None
    try:
        return json.loads(block.group(1))
    except Exception as exc:
        raise ValueError(f"procedure JSON パース失敗: {exc}")


def build(sheet_text: str, depth: str) -> dict:
    row_depth = DEPTH_TO_ROW_DEPTH.get(depth, "standard")
    rows = []
    for axis in AXES:
        content = _pick_axis(sheet_text, axis)
        if not content or "[?]" in content:
            raise ValueError(f"axis incomplete: {axis}")
        row = {"name": axis, "content": content, "depth": row_depth}
        if axis == "ナレッジ資産":
            row["must"] = True
        rows.append(row)

    knowledge = next(r["content"] for r in rows if r["name"] == "ナレッジ資産")
    source = next(r["content"] for r in rows if r["name"] == "情報源")
    output = next(r["content"] for r in rows if r["name"] == "出力先")
    payload = {
        "five_axes": {
            "rows": rows,
            "pipeline": {
                "ingest": source,
                "analysis": "Phase 5 purpose-excavator で抽象回答を深掘り",
                "storage": knowledge,
                "retrieval": output,
                "update": "on-demand",
            },
        }
    }
    procedure = extract_procedure(sheet_text)
    if procedure is not None:
        payload["procedure"] = procedure
    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet")
    parser.add_argument("--depth", default="standard")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    try:
        payload = build(Path(args.sheet).read_text(encoding="utf-8"), args.depth)
    except Exception as exc:
        print(f"FAIL build-sheet-json: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
