#!/usr/bin/env python3
# /// script
# name: notify-if-governance-trigger
# version: 0.2.0
# purpose: trigger.json を読み breached が空でなければ Stop Hook 経由で招集メッセージを stdout 出力する（27章§3.4）
# inputs:
#   - --trigger: trigger.json のパス（既定 eval-log/trigger.json）
# outputs:
#   - stdout: 招集メッセージ（breached があるとき）/ 空（no-op）
#   - stderr: trigger.json を読めない・形が違うときの警告（黙って捨てない）
#   - exit: 0（trigger.json の中身によらず 0、Hook 自体は通す）。未知の引数だけは argparse が usage を出して 2
# requires-python: ">=3.9"
# dependencies: []
# contexts: [D]
# network: false
# write-scope: none
# ///
"""governance トリガーを Stop Hook で通知する。

trigger.json が無いのは、まだ発火していない通常の状態なので何も出さない。
あるのに読めない・JSON が壊れている・形が違う（object でない、breached が配列でない）
ときは、発火を見落とさないよう stderr に警告を出す。どちらも Hook は止めず exit 0。

bootstrap と breached は、書き手の lint-rubric-violation.py が bool と配列で書く。型が違う値
(文字列の "false"、""・0・false の breached など) を真偽で読むと、発火を黙って捨てたり誤って
止めたりするので、型で判定する。bootstrap の型が違うときは警告し、breached の判定に進む
(発火を見落とさない側に倒す)。breached が無い・null のときは、発火していない状態として扱う。

未知の引数は argparse が exit 2 で止める。Claude Code の Stop hook では exit 2 が停止の阻止に
なるので、hook に登録するときは --trigger 以外の引数を渡さない。この script は 2026-10-10 時点で
どの hooks.json にも登録されておらず、run-skill-rubric-governance などから手で呼ぶ。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def warn(message: str) -> None:
    print(f"[governance] warning: {message}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", default="eval-log/trigger.json")
    args = ap.parse_args()

    p = Path(args.trigger)
    if not p.is_file():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        warn(f"{p} を読めない ({type(exc).__name__}: {exc})。発火の有無を判定できない")
        return 0
    if not isinstance(data, dict):
        warn(f"{p} が object でない。発火の有無を判定できない")
        return 0

    bootstrap = data.get("bootstrap", False)
    if bootstrap is True:
        return 0
    if bootstrap is not False and bootstrap is not None:
        warn(f"{p} の bootstrap が真偽値でない ({bootstrap!r})。bootstrap 中でないとみなして breached を確かめる")
    breached = data.get("breached")
    if breached is None:
        breached = []
    if not isinstance(breached, list):
        warn(f"{p} の breached が配列でない。発火の有無を判定できない")
        return 0
    if not breached:
        return 0

    items = ", ".join(
        str(b.get("rubric_item_id", "?")) if isinstance(b, dict) else "?" for b in breached
    )
    print("[governance] rubric 改正招集トリガーが発火しました。")
    print(f"  違反継続項目: {items}")
    print(f"  連続 release 数 n={data.get('n')}、閾値 threshold={data.get('threshold')}")
    print("  次手順: /run-skill-rubric-governance を起動して提案 YAML を作成してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
