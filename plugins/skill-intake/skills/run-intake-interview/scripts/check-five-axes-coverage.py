#!/usr/bin/env python3
"""sheet.md に 5 軸見出しが揃い、各見出しの下に空行以外の内容があるか検証。"""
import re
import sys
from pathlib import Path

AXES = ["出力先", "情報源", "共有相手", "真の課題", "ナレッジ資産"]
USAGE = "usage: check-five-axes-coverage.py <sheet.md>"


def check(text: str) -> list[str]:
    """5 軸のうち未充足 (見出し欠落 / 内容空 / [?] 残存) の軸名リストを返す。"""
    missing = []
    for axis in AXES:
        m = re.search(rf"#+\s*{re.escape(axis)}\s*\n(.+?)(?=\n#+\s|\Z)", text, re.S)
        if not m or not m.group(1).strip() or "[?]" in m.group(1):
            missing.append(axis)
    return missing


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"FAIL: file not found: {path}", file=sys.stderr)
        return 2
    missing = check(path.read_text(encoding="utf-8"))
    if missing:
        print(f"FAIL axes incomplete: {missing}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
