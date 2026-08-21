#!/usr/bin/env python3
# /// script
# name: notify-if-governance-trigger
# version: 0.1.0
# purpose: trigger.json を読み breached が空でなければ Stop Hook 経由で招集メッセージを stdout 出力する（27章§3.4）
# inputs:
#   - --trigger: trigger.json のパス（既定 eval-log/trigger.json）
# outputs:
#   - stdout: 招集メッセージ（breached があるとき）/ 空（no-op）
#   - exit: 0（常に 0、Hook 自体は通す）
# requires-python: ">=3.9"
# dependencies: []
# contexts: [D]
# network: false
# write-scope: none
# ///
"""governance トリガーを Stop Hook で通知する。"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", default="eval-log/trigger.json")
    args = ap.parse_args()

    p = Path(args.trigger)
    if not p.is_file():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0

    if data.get("bootstrap"):
        return 0
    breached = data.get("breached") or []
    if not breached:
        return 0

    items = ", ".join(b.get("rubric_item_id", "?") for b in breached)
    print("[governance] rubric 改正招集トリガーが発火しました。")
    print(f"  違反継続項目: {items}")
    print(f"  連続 release 数 n={data.get('n')}、閾値 threshold={data.get('threshold')}")
    print("  次手順: /run-skill-rubric-governance を起動して提案 YAML を作成してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
