#!/usr/bin/env python3
"""ci_dogfooding_retest.py

Gate 2 rubric の auto_retest_policy 実装。
dogfooding_regression.py が exit==1 (回帰失敗) を返したとき、最大 1 回まで自動再検証し、
2 回連続失敗で BLOCK (exit 2) を返す。3 連続失敗は migration-plan-v2.md §6 のロールバック条件に該当する。

設計方針 (SS-02 / F3 対応):
  - close the feedback loop: 検出→再検証→escalation を一本の script に閉じる
  - 状態は eval-log/dogfooding-fail-counter.json に persist
  - CI / pre-merge hook から呼ぶことを想定

Usage:
  python3 ci_dogfooding_retest.py <generated-intake.json>

Exit codes:
  0  PASS (初回 or 再検証で合格)
  1  RETRY_FAIL (再検証も失敗、次回トリガーで escalation)
  2  ESCALATE (連続失敗 max を超過、Gate2 BLOCK)
  3  ENVIRONMENT_ERROR
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
COUNTER_PATH = PROJECT_ROOT / "eval-log" / "dogfooding-fail-counter.json"
DOGFOODING = PLUGIN_ROOT / "scripts" / "dogfooding_regression.py"
GATE2_RUBRIC = PROJECT_ROOT / "eval-log" / "gate2-rubric.json"


def _load_counter() -> dict:
    if not COUNTER_PATH.exists():
        return {"consecutive_fail": 0, "last_intake": None}
    return json.loads(COUNTER_PATH.read_text(encoding="utf-8"))


def _save_counter(state: dict) -> None:
    COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    COUNTER_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_policy() -> dict:
    if not GATE2_RUBRIC.exists():
        return {"max_retries": 1, "consecutive_fail_max": 2}
    rubric = json.loads(GATE2_RUBRIC.read_text(encoding="utf-8"))
    return {
        "max_retries": rubric.get("auto_retest_policy", {}).get("max_retries", 1),
        "consecutive_fail_max": rubric.get("regression_tolerance", {}).get("dogfooding_consecutive_fail_max", 2),
    }


def _run_dogfooding(intake: Path) -> int:
    return subprocess.call([sys.executable, str(DOGFOODING), str(intake)])


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: ci_dogfooding_retest.py <generated-intake.json>", file=sys.stderr)
        return 3

    intake = Path(argv[1]).resolve()
    if not intake.exists():
        print(f"ERROR: intake not found: {intake}", file=sys.stderr)
        return 3

    if not DOGFOODING.exists():
        print(f"ERROR: dogfooding_regression.py not found: {DOGFOODING}", file=sys.stderr)
        return 3

    policy = _load_policy()
    state = _load_counter()

    rc = _run_dogfooding(intake)
    if rc == 0:
        state["consecutive_fail"] = 0
        state["last_intake"] = str(intake)
        _save_counter(state)
        print("PASS: dogfooding PASS (counter reset)", file=sys.stderr)
        return 0

    # 1 回目の失敗 → 即座に再実行
    for attempt in range(1, policy["max_retries"] + 1):
        print(f"RETRY {attempt}/{policy['max_retries']}: dogfooding 再検証", file=sys.stderr)
        rc = _run_dogfooding(intake)
        if rc == 0:
            state["consecutive_fail"] = 0
            state["last_intake"] = str(intake)
            _save_counter(state)
            print(f"PASS on retry {attempt}", file=sys.stderr)
            return 0

    # max_retries 使い切って失敗 → counter インクリメント
    state["consecutive_fail"] = state.get("consecutive_fail", 0) + 1
    state["last_intake"] = str(intake)
    _save_counter(state)

    if state["consecutive_fail"] >= policy["consecutive_fail_max"] + 1:
        print(f"ESCALATE: 連続 {state['consecutive_fail']} 回失敗 → Gate2 BLOCK / migration §6 rollback 検討", file=sys.stderr)
        return 2

    print(f"RETRY_FAIL: 連続 {state['consecutive_fail']} 回失敗 (escalate閾値 {policy['consecutive_fail_max']+1})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
