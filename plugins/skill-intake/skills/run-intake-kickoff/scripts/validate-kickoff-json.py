#!/usr/bin/env python3
"""kickoff.json の最小スキーマ検証。stdlib のみ使用。"""
import json
import sys
from pathlib import Path

REQUIRED = ["pattern", "depth", "skill_name_hint", "pain_ranking", "initial_utterance", "timestamp"]
PATTERNS = {"A", "B", "C", "D", "E"}
DEPTHS = {"quick", "standard", "detailed"}


def main(path: str) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        print(f"FAIL: missing keys: {missing}", file=sys.stderr)
        return 1
    if data["pattern"] not in PATTERNS:
        print(f"FAIL: pattern not in {PATTERNS}", file=sys.stderr)
        return 1
    if data["depth"] not in DEPTHS:
        print(f"FAIL: depth not in {DEPTHS}", file=sys.stderr)
        return 1
    if not isinstance(data["pain_ranking"], list) or not data["pain_ranking"]:
        print("FAIL: pain_ranking must be non-empty list", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
