#!/usr/bin/env python3
"""繰り返し違反検出 → rubric改正トリガー (設計書08章「繰り返し違反の昇格」+ 09章P3governance loop).

evaluator が出力した eval-log/evaluator-results/*.json を走査し、
同じ rubric_id × finding.area が 2 回連続で出ている skill を検出する。
検出されたら run-skill-rubric-governance フローを起動する。

Usage:
  python3 scripts/detect-repeated-rubric-violations.py [--threshold 2] [--out eval-log/governance-trigger.json]
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = ROOT / "eval-log" / "evaluator-results"


def load_eval_results(log_dir: Path) -> list[dict]:
    if not log_dir.exists():
        return []
    out = []
    for p in sorted(log_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            out.append({"file": p.name, "data": data})
        except Exception:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=2)
    ap.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    ap.add_argument("--out", default=str(ROOT / "eval-log" / "governance-trigger.json"))
    args = ap.parse_args()

    results = load_eval_results(Path(args.log_dir))
    # group: (skill, rubric_id, finding.area) → count
    counter: dict = defaultdict(int)
    for r in results:
        d = r["data"]
        skill = d.get("artifact") or d.get("skill_name") or r["file"]
        rid = (d.get("rubric") or {}).get("rubric_id", "unknown")
        for f in d.get("findings") or []:
            area = f.get("area") or f.get("rule_id") or "unknown"
            counter[(skill, rid, area)] += 1

    triggered = [
        {"skill": k[0], "rubric_id": k[1], "area": k[2], "count": v}
        for k, v in counter.items() if v >= args.threshold
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "threshold": args.threshold,
        "triggered": triggered,
        "next_action": "run-skill-rubric-governance" if triggered else "none",
    }, indent=2, ensure_ascii=False))

    if triggered:
        print(f"REPEATED VIOLATIONS DETECTED: {len(triggered)} pattern(s)")
        for t in triggered:
            print(f"  skill={t['skill']} rubric={t['rubric_id']} area={t['area']} count={t['count']}")
        print(f"→ Recommend: bash bin/run-skill-rubric-governance")
        return 1
    print("No repeated violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
