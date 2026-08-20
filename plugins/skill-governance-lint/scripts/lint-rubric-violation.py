#!/usr/bin/env python3
# /// script
# name: lint-rubric-violation
# version: 0.1.0
# purpose: eval-log/*.jsonl を読み、連続 N release × 違反率 M% 超を検出して trigger.json を出力する（27章§3.2 正本）
# inputs:
#   - --log-dir: eval-log ディレクトリのパス
#   - --n: 連続 release 数（既定 3）
#   - --threshold: 違反率閾値（既定 0.20）
#   - --out: 出力 trigger.json のパス
#   - --bootstrap-threshold: bootstrap 判定件数（既定 20、未満なら exit 0 + warning）
# outputs:
#   - file: trigger.json （breached / n / threshold / bootstrap）
#   - exit: 0=招集不要 / 2=招集必要 / 3=bootstrap中
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: output-dir
# ///
"""eval-log 違反率を時系列で集計し governance トリガーを判定する。"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load(log_dir: Path):
    for p in sorted(log_dir.rglob("*-score.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


def compute(records):
    bucket: dict = defaultdict(lambda: [0, 0])
    total = 0
    for r in records:
        total += 1
        for f in r.get("findings", []):
            k = (r.get("release", "unknown"), f.get("rubric_item_id") or f.get("id") or "?")
            bucket[k][0] += 1
            if not f.get("passed", True):
                bucket[k][1] += 1
    by_item: dict = defaultdict(list)
    for (rel, item), (t, v) in bucket.items():
        by_item[item].append((rel, v / t if t else 0.0))
    for item in by_item:
        by_item[item].sort()
    return by_item, total


def detect(by_item, n: int, th: float):
    out = []
    for item, s in by_item.items():
        if len(s) >= n and all(rate > th for _, rate in s[-n:]):
            out.append({
                "rubric_item_id": item,
                "recent_releases": [r for r, _ in s[-n:]],
                "recent_rates": [v for _, v in s[-n:]],
            })
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--log-dir", required=True)
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--threshold", type=float, default=0.20)
    p.add_argument("--out", required=True)
    p.add_argument("--bootstrap-threshold", type=int, default=20)
    a = p.parse_args()

    log_dir = Path(a.log_dir)
    if not log_dir.is_dir():
        result = {"breached": [], "n": a.n, "threshold": a.threshold, "bootstrap": True, "warning": "log dir missing"}
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 3

    by_item, total = compute(list(load(log_dir)))
    if total < a.bootstrap_threshold:
        result = {
            "breached": [],
            "n": a.n,
            "threshold": a.threshold,
            "bootstrap": True,
            "total_records": total,
            "bootstrap_threshold": a.bootstrap_threshold,
            "warning": f"bootstrap phase: {total}/{a.bootstrap_threshold} records",
        }
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 3

    breached = detect(by_item, a.n, a.threshold)
    result = {"breached": breached, "n": a.n, "threshold": a.threshold, "bootstrap": False, "total_records": total}
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not breached else 2


if __name__ == "__main__":
    sys.exit(main())
