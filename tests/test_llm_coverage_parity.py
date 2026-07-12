"""eval-log/llm-coverage.json が最新であることを保証する parity テスト。

llm-coverage.json は validate-llm-coverage.py が毎回無条件 write する派生
レポートで、roster (tests/criteria/criteria_roster.py) のような git-stale
検出が無かった。そのため skill 変更/改名で checklist_items 等が変わっても
台帳の更新漏れが CI の exit code に現れず、長期間潜伏しうる
(2026-07-02 harness-creator 改名で 15→16 の stale が顕在化)。

生成器の --check モードは書き込まず生成結果と既存ファイルを突き合わせ、
乖離を fail-closed に検出する。本テストはそれを pytest 経由でも保証し、
再生成 (make llm-coverage) 忘れを機械遮断する。criteria roster 側の
tests/criteria/test_roster_matches_discovery.py と対称。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_llm_coverage_json_up_to_date():
    """validate-llm-coverage --all --check が exit0 (台帳が生成結果と一致)。

    乖離時は `make llm-coverage` (= python3 scripts/validate-llm-coverage.py
    --all) での再生成を促す。--check は書き込まないため副作用なし。
    """
    r = subprocess.run(
        [sys.executable, "scripts/validate-llm-coverage.py", "--all", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        "eval-log/llm-coverage.json が生成結果と乖離 (stale)。"
        "再生成: make llm-coverage\n"
        f"stdout={r.stdout}\nstderr={r.stderr}"
    )
