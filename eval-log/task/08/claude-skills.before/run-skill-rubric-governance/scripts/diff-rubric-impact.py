#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assess impact of a proposed rubric change on past evaluations.

Usage:
  diff-rubric-impact.py --proposal <json> --logs <dir>

Heuristic: count what fraction of past evaluations would flip pass/fail
if the proposed rule were applied at proposed severity.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

SEVERITY_WEIGHTS = {"high": -20, "medium": -10, "low": -3}


def parse_proposal(p: Path) -> dict:
    data = json.loads(p.read_text(encoding="utf-8"))
    change = data.get("change", {})
    if "bump" in data and "bump" not in change:
        change["bump"] = data["bump"]
    return change


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposal", required=True)
    ap.add_argument("--logs", required=True)
    ap.add_argument("--threshold", type=int, default=80)
    args = ap.parse_args()

    pf = Path(args.proposal)
    if not pf.exists():
        print(f"proposal missing: {pf}", file=sys.stderr)
        return 2
    change = parse_proposal(pf)
    sev = change.get("severity", "medium")
    weight = SEVERITY_WEIGHTS.get(sev, -10)

    log_dir = Path(args.logs)
    if not log_dir.is_dir():
        print("no logs; cannot assess", file=sys.stderr)
        return 2

    total = 0
    would_flip = 0
    for f in sorted(log_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            old_score = rec.get("score", 100)
            # Worst case: rule would fire on this record
            new_score = max(0, old_score + weight)
            old_pass = old_score >= args.threshold
            new_pass = new_score >= args.threshold
            if old_pass and not new_pass:
                would_flip += 1

    flip_rate = (would_flip / total) if total else 0.0
    bump_required = "major" if flip_rate > 0.30 else change.get("bump", "minor")
    out = {
        "total": total,
        "would_flip": would_flip,
        "flip_rate": round(flip_rate, 4),
        "proposed_bump": change.get("bump", ""),
        "required_bump": bump_required,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
