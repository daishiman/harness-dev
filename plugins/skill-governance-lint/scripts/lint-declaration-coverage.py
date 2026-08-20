#!/usr/bin/env python3
# /// script
# name: lint-declaration-coverage
# purpose: plugin-composition.yaml の enforcement manual 残存数を ratchet 監視し宣言面の突合 lint 配線義務を強制する。
# inputs:
#   - argv: plugin-composition.yaml path or --self-test
# outputs:
#   - stdout: OK status / baseline 更新促し
#   - stderr: violation findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""plugin-composition.yaml の `enforcement: manual` 残存数を ratchet 方式で監視する。

背景 (finding LS-10): lint 集合分散・完了条件多系統・dangling 参照は全て
「宣言面を追加する際に対向突合 lint を同時に足す義務がどこにも宣言されていない」
に帰着する。突合が配線された宣言面 (feedback_contract / content-review) では
再発が止まっている実績があるため、manual 宣言の増加を機械遮断する。

ratchet 動作 (harness-creator-kit-ci.yml の coverage-gate ratchet と同思想):
  count >  baseline → FAIL (新しい宣言面には突合 lint を同時配線せよ)
  count == baseline → PASS
  count <  baseline → PASS + baseline 更新を促すメッセージ (締め上げ方向は歓迎)

baseline は本スクリプト内定数 MANUAL_BASELINE が正本。CI 配線対象は
plugins/harness-creator/plugin-composition.yaml であり、baseline はその実残存数
(意図的残置 2 項: rubric_refs 順序 / side_effect_scope。elegant-review Phase 順序は
validate-paradigm-coverage.py --phase-order 着地で機械化済) に一致させる。
意図的残置には invariant 行内に「manual 維持の理由」注記を要する。

Usage:
  lint-declaration-coverage.py plugins/harness-creator/plugin-composition.yaml
  lint-declaration-coverage.py --self-test

Exit 0 = ok, 1 = violation, 2 = usage error.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

# 意図的残置 manual の許容数。manual を減らしたら本定数も下げる (ratchet)。
MANUAL_BASELINE = 2

MANUAL_ENFORCEMENT_RE = re.compile(r"enforcement:\s*manual\b")


def count_manual(text: str) -> int:
    return len(MANUAL_ENFORCEMENT_RE.findall(text))


def evaluate(count: int, baseline: int) -> tuple[int, str]:
    """Returns (exit_code, message)."""
    if count > baseline:
        return 1, (
            f"FAIL: enforcement manual が {count} 件に増加 (baseline {baseline})。"
            "新しい宣言面には対向突合 lint を同時配線するか、意図的残置なら"
            "「manual 維持の理由」注記を付けたうえで MANUAL_BASELINE を更新して"
            "増加を明示的に承認すること。"
        )
    if count < baseline:
        return 0, (
            f"OK: enforcement manual {count} 件 (baseline {baseline} を下回る)。"
            f"ratchet を締めるため MANUAL_BASELINE を {count} へ更新推奨。"
        )
    return 0, f"OK: enforcement manual {count} 件 (baseline {baseline} と一致)"


def lint_file(path: Path, baseline: int = MANUAL_BASELINE) -> tuple[int, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return 2, f"{path}: read error: {e}"
    code, msg = evaluate(count_manual(text), baseline)
    return code, f"{path}: {msg}"


def self_test() -> int:
    failures: list[str] = []

    # count_manual: 検出 / 非検出 (enforcement 接頭辞なしの manual は数えない)
    cases = [
        ("", 0),
        ('- "x (enforcement: manual)"\n- "y (enforcement: manual。理由注記)"\n', 2),
        ('- "manual 宣言の残存数を ratchet 監視 (enforcement: lint-x.py)"\n', 0),
        ('- "z (enforcement:  manual)"\n', 1),
    ]
    for text, expected in cases:
        got = count_manual(text)
        if got != expected:
            failures.append(f"count_manual({text!r}) = {got}, expected {expected}")

    # evaluate: 増加 FAIL / 同数 PASS / 減少 PASS+更新促し
    code, msg = evaluate(4, 3)
    if code != 1 or "FAIL" not in msg:
        failures.append(f"evaluate(4,3) = ({code}, {msg!r}), expected FAIL exit 1")
    code, msg = evaluate(3, 3)
    if code != 0 or "一致" not in msg:
        failures.append(f"evaluate(3,3) = ({code}, {msg!r}), expected PASS")
    code, msg = evaluate(2, 3)
    if code != 0 or "更新推奨" not in msg:
        failures.append(f"evaluate(2,3) = ({code}, {msg!r}), expected PASS + 更新促し")

    # lint_file: 実ファイル入出力 (baseline 注入)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "plugin-composition.yaml"
        p.write_text('invariant:\n  - "a (enforcement: manual)"\n', encoding="utf-8")
        code, _ = lint_file(p, baseline=0)
        if code != 1:
            failures.append(f"lint_file over-baseline: exit {code}, expected 1")
        code, _ = lint_file(p, baseline=1)
        if code != 0:
            failures.append(f"lint_file at-baseline: exit {code}, expected 0")
        code, _ = lint_file(Path(td) / "missing.yaml", baseline=0)
        if code != 2:
            failures.append(f"lint_file missing file: exit {code}, expected 2")

    if failures:
        for f in failures:
            sys.stderr.write(f"self-test FAIL: {f}\n")
        return 1
    sys.stdout.write("self-test ok: count/evaluate/lint_file cases passed\n")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    targets = [Path(a) for a in argv if not a.startswith("--")]
    if not targets:
        sys.stderr.write(
            "usage: lint-declaration-coverage.py <plugin-composition.yaml> | --self-test\n"
        )
        return 2
    worst = 0
    for path in targets:
        code, msg = lint_file(path)
        if code == 2:
            sys.stderr.write(msg + "\n")
            return 2
        (sys.stderr if code else sys.stdout).write(msg + "\n")
        worst = max(worst, code)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
