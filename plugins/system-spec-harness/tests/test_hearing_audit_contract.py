# /// script
# name: test-hearing-audit-contract
# purpose: 推奨の基準・監査の軸・重大度の対応が 1 か所に定義され、各文書がそこを参照していることを静的に検査する
# inputs:
#   - pytest 実行 (argv なし)
# outputs:
#   - pytest 結果
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""ヒアリング監査まわりの文書契約の静的テスト。

食い違いは次の 4 つだった。

1. R5 は「AI 推奨を提示する」、R6 と C06 は「片側の問は誘導」と定め、推奨を置く位置を誰も
   決めていなかった → 基準を ``neutral-question-criteria.md`` の 1 か所に置き、R5 と R6 と C06 が参照する。
2. C06 は「検出 3 軸 + トレース 1 軸」の 4 軸、SSOT の R6 は 5 軸 → C06 は R6 の 5 軸を参照する。
3. 重大度の閾値が無く low 1 件でも FAIL → 対応表を aspect-criteria.md の 1 か所に置く。
4. 置き換えの概念が無い → 契約文書に superseded_* と supersede-qa を定義する。

各文書に基準を書き写していないこと (参照していること) と、古い記述が残っていないことを確かめる。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELICIT = ROOT / "skills" / "run-system-spec-elicit"
EVAL = ROOT / "skills" / "assign-system-spec-completeness-evaluator"
COMPILE = ROOT / "skills" / "run-system-spec-compile"

NEUTRAL = ELICIT / "references" / "neutral-question-criteria.md"
R5 = ELICIT / "prompts" / "R5-decision-guide.md"
R6 = ELICIT / "prompts" / "R6-audit-hearing.md"
C06 = ROOT / "agents" / "system-spec-hearing-auditor.md"
CRITERIA = EVAL / "references" / "aspect-criteria.md"
RUBRIC = EVAL / "references" / "scoring-rubric.json"
R1 = EVAL / "prompts" / "R1-score.md"
R2 = EVAL / "prompts" / "R2-delegate.md"
CONTRACT = ELICIT / "references" / "spec-state-contract.md"

# C06 の監査を扱う文書。doc-freshness-auditor (C08) の「検出 4 軸」は別物なので含めない。
HEARING_DOCS = [C06, R1, R2, EVAL / "SKILL.md", RUBRIC, CRITERIA, R6]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_neutral_question_criteria_is_the_single_definition():
    text = _read(NEUTRAL)
    for nid in ("N1", "N2", "N3", "N4"):
        assert re.search(rf"^\| \*\*{nid}\*\* \|", text, re.M), f"{nid} の定義行が無い"
    assert "推奨の示し方" in text and "既に凍結された問に違反があったとき" in text
    # 作る側 (R5) と監査する側 (R6・C06) が同じ基準を参照する
    for path in (R5, R6, C06, ELICIT / "SKILL.md", ELICIT / "references" / "resource-map.yaml"):
        assert "neutral-question-criteria.md" in _read(path), f"{path.relative_to(ROOT)} が基準を参照していない"


def test_r5_keeps_the_recommendation_out_of_the_question():
    text = _read(R5)
    assert "推奨を問に入れない" in text
    assert "AI推奨 (参考)" in text
    assert "provenance" in text


def test_no_document_counts_the_hearing_audit_as_four_axes():
    for path in HEARING_DOCS:
        text = _read(path)
        for stale in ("4 軸", "4軸", "3 軸 + トレース 1 軸", "FAIL=1 軸以上"):
            assert stale not in text, f"{path.relative_to(ROOT)} に古い記述 {stale!r} が残っている"


def test_c06_refers_to_the_five_axes_of_r6_instead_of_restating_them():
    text = _read(C06)
    assert "R6-audit-hearing.md" in text and "監査 5 軸" in text
    assert "aspect-criteria.md" in text  # 重大度と判定の対応
    assert "supersession_valid" in text and "閉じた検出" in text
    assert "上位概念" in text  # 軸 5 が抜けていない


def test_severity_mapping_lives_only_in_aspect_criteria():
    text = _read(CRITERIA)
    assert "### 1a. ヒアリング監査 (C06) の重大度と判定の対応 (正本)" in text
    section = text.split("### 1a.", 1)[1].split("\n### ", 1)[0]
    for row in ("| high |", "| low / info |", "閉じた検出", "INDETERMINATE", "derive_hearing_verdict"):
        assert row in section, f"1a に {row!r} が無い"
    # 参照する側は表を持たず、1a を指す
    for path in (R1, R2, EVAL / "SKILL.md"):
        body = _read(path)
        assert "aspect-criteria.md" in body and "1a" in body, f"{path.relative_to(ROOT)} が 1a を参照していない"
    assert "aspect-criteria.md 1a" in _read(RUBRIC)


def test_r1_no_longer_turns_any_c06_fail_into_an_aspect_fail():
    text = _read(R1)
    assert "- 監査 verdict FAIL/INDETERMINATE → 該当観点 FAIL" not in text
    assert "--hearing" in text and "derive_hearing_verdict" in text


def test_rubric_is_still_valid_json_with_the_c06_sub_input():
    rubric = json.loads(_read(RUBRIC))
    criteria = rubric["aspects"]["matrix_coverage"]["pass_criteria"] if "aspects" in rubric else None
    blob = json.dumps(rubric, ensure_ascii=False)
    assert "R6-audit-hearing の監査 5 軸" in blob
    if criteria is not None:
        assert any("C06" in c for c in criteria)


def test_contract_defines_supersession():
    text = _read(CONTRACT)
    for key in ("`superseded_by`", "`superseded_at`", "`superseded_note`"):
        assert re.search(rf"^\| {re.escape(key)} \|", text, re.M), f"qa_log の項目表に {key} が無い"
    assert "**`supersede-qa` (追記専用)**" in text
    assert "置き換え済みの entry を主たる接地根拠にしない" in text


def test_compile_skill_states_the_verbatim_and_superseded_rules():
    text = _read(COMPILE / "SKILL.md")
    assert "逐語は章の構造を壊さない" in text
    assert "旧版（置き換え先: <qa_id>）" in text
