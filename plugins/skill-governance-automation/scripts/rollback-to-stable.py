#!/usr/bin/env python3
# /// script
# name: rollback-to-stable
# version: 0.1.0
# purpose: rubric_version を 安定版凍結条件 (freeze.consecutive_runs × violation_rate_ceiling) を満たす過去版へ巻き戻す（27章§9 自動 rollback）
# inputs:
#   - --rubric: 現行 rubric.json のパス（必須）
#   - --versions-md: rubric-versions.md のパス（必須）
#   - --params: governance-params.json のパス（既定 references/governance-params.json）
#   - --dry-run: 候補表示のみ
# outputs:
#   - stdout: 選定版 / 復元計画
#   - exit: 0=OK / 1=候補なし / 2=usage
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: output-dir
# ///
"""安定版凍結条件を満たす最新の rubric_version へロールバック計画を出力する。"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path


def parse_versions_md(text: str) -> list[dict]:
    """## <ver> (date) ... violation_rate_avg: <float> 形式を抽出（簡易）。"""
    out = []
    current: dict | None = None
    for ln in text.splitlines():
        s = ln.strip()
        m = re.match(r"^##\s+(\S+)\s*\((\d{4}-\d{2}-\d{2})\)", s)
        if m:
            if current:
                out.append(current)
            current = {"version": m.group(1), "date": m.group(2), "violation_rate_avg": None}
            continue
        if current is None:
            continue
        m2 = re.search(r"violation[_-]?rate[_-]?avg[:\s]+([0-9.]+)", s)
        if m2:
            current["violation_rate_avg"] = float(m2.group(1))
    if current:
        out.append(current)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--versions-md", required=True)
    ap.add_argument("--params", default="references/governance-params.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    params_path = Path(args.params)
    if params_path.is_file():
        params = json.loads(params_path.read_text(encoding="utf-8"))
    else:
        params = {"freeze": {"violation_rate_ceiling": 0.05}}
    ceiling = params.get("freeze", {}).get("violation_rate_ceiling", 0.05)

    vm = Path(args.versions_md)
    if not vm.is_file():
        print(f"error: versions-md not found: {vm}", file=sys.stderr)
        return 1
    versions = parse_versions_md(vm.read_text(encoding="utf-8"))
    candidates = [v for v in versions if v["violation_rate_avg"] is not None and v["violation_rate_avg"] <= ceiling]
    if not candidates:
        print("no stable candidate found", file=sys.stderr)
        return 1

    target = candidates[-1]
    print(json.dumps({
        "target_version": target["version"],
        "target_date": target["date"],
        "violation_rate_avg": target["violation_rate_avg"],
        "ceiling": ceiling,
        "dry_run": args.dry_run,
        "plan": f"rubric.json の rubric_version を {target['version']} に書き戻し、compute-rubric-hash.py で hash を再計算する",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
