#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Aggregate rubric violations from eval-log/*.jsonl.

Usage:
  lint-rubric-violation.py --logs <dir> [--rule <id>]
Emits JSON: {"total": N, "by_rule": {"FM-003": 12, ...}}
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", required=True)
    ap.add_argument("--rule", default=None)
    args = ap.parse_args()

    log_dir = Path(args.logs)
    if not log_dir.is_dir():
        print(json.dumps({"total": 0, "by_rule": {}, "warning": "log dir missing"}))
        return 0

    counter: Counter[str] = Counter()
    total = 0
    for f in sorted(log_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                print(f"warning: invalid jsonl in {f}", file=sys.stderr)
                continue
            total += 1
            for finding in rec.get("findings", []):
                rid = finding.get("id", "?")
                if args.rule and rid != args.rule:
                    continue
                counter[rid] += 1

    out = {"total": total, "by_rule": dict(counter)}
    sys.stdout.write(json.dumps(out, ensure_ascii=False, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
