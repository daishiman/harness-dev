"""run-intake-interview の procedure 軸拡張 (C01) を network/LLM 無しで検証する。

対象 (goal-spec C1 詳細抽出 / C2 フォールバック / C6 決定論分岐):
  - scripts/validate-answer-abstraction.py : procedure 軸の未回答検出と決定論判定
  - scripts/build-sheet-json.py            : sheet.md からの procedure ブロック抽出
  - scripts/validate-interview-json.py     : procedure を持つ完了 interview.json の schema PASS

tmp_path のみで完結し repo を汚染しない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IV = ROOT / "plugins" / "skill-intake" / "skills" / "run-intake-interview"
ABSTRACTION = IV / "scripts" / "validate-answer-abstraction.py"
BUILD_SHEET = IV / "scripts" / "build-sheet-json.py"
VALIDATE_IV = IV / "scripts" / "validate-interview-json.py"
PATTERNS = IV / "references" / "abstract-answer-patterns.md"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ABS = _load(ABSTRACTION, "validate_answer_abstraction_ut")
BSJ = _load(BUILD_SHEET, "build_sheet_json_ut")


# ---------------------------------------------------------------------------
# validate-answer-abstraction : procedure 軸 (C2 フォールバック / C6 決定論)
# ---------------------------------------------------------------------------

def _words():
    return ABS.DEFAULT_ACTION_ABSTRACT, ABS.DEFAULT_VAGUE_FILLER


def test_procedure_axis_concrete_is_not_abstract():
    aw, vw = _words()
    r = ABS.judge("freeeで請求書を作成する", aw, vw, axis="procedure")
    assert r["abstract"] is False and r["unanswered"] is False


def test_procedure_axis_empty_is_unanswered():
    aw, vw = _words()
    r = ABS.judge("", aw, vw, axis="procedure")
    assert r["abstract"] is True and r["unanswered"] is True


@pytest.mark.parametrize("ans", ["わからない", "特にない", "思いつかない", "答えられない", "なし", "ない"])
def test_procedure_axis_unanswered_phrases(ans):
    aw, vw = _words()
    r = ABS.judge(ans, aw, vw, axis="procedure")
    assert r["unanswered"] is True and r["abstract"] is True


def test_procedure_axis_unanswered_tolerates_trailing_punct():
    aw, vw = _words()
    r = ABS.judge("わからない。", aw, vw, axis="procedure")
    assert r["unanswered"] is True


def test_procedure_axis_abstract_answer_still_abstract():
    # 抽象語 (効率化・目的語なし) は procedure 軸でも abstract=True (unanswered ではない)
    aw, vw = _words()
    r = ABS.judge("効率化したい", aw, vw, axis="procedure")
    assert r["abstract"] is True and r["unanswered"] is False


def test_non_procedure_axis_empty_keeps_legacy_behavior():
    # procedure 以外の軸では空回答は従来通り (unanswered 検出しない)
    aw, vw = _words()
    r = ABS.judge("", aw, vw, axis="true-pain")
    assert r["unanswered"] is False


def test_procedure_axis_deterministic_same_input_same_result():
    # C6: 同一入力は常に同一判定 (LLM 定性判断を排除)
    aw, vw = _words()
    a = ABS.judge("特にない", aw, vw, axis="procedure")
    b = ABS.judge("特にない", aw, vw, axis="procedure")
    assert a == b


def test_abstraction_cli_procedure_unanswered_exit3():
    proc = subprocess.run(
        [sys.executable, str(ABSTRACTION), "--patterns", str(PATTERNS),
         "--answer", "", "--axis", "procedure"],
        capture_output=True, text=True)
    assert proc.returncode == 3
    assert json.loads(proc.stdout)["unanswered"] is True


def test_abstraction_cli_procedure_concrete_exit0():
    proc = subprocess.run(
        [sys.executable, str(ABSTRACTION), "--patterns", str(PATTERNS),
         "--answer", "freeeで請求書を作成する", "--axis", "procedure"],
        capture_output=True, text=True)
    assert proc.returncode == 0


# ---------------------------------------------------------------------------
# build-sheet-json : procedure 抽出 (C1 詳細抽出の runtime 生成)
# ---------------------------------------------------------------------------

_FIVE_AXES_MD = """## 出力先
Notion に業務報告を出す
## 情報源
Slack ログ
## 共有相手
経営チーム
## 真の課題
報告作成に時間がかかる
## ナレッジ資産
過去テンプレート
"""

_PROC_SECTION = """## 現状手順 (procedure)
```json
{"mode": "detailed", "steps": [{"action": "Slackログ収集", "input": "Slackチャンネル", "output": "生ログ", "tool": "Slack API", "frequency": "毎朝"}]}
```
"""


def test_extract_procedure_present():
    proc = BSJ.extract_procedure(_FIVE_AXES_MD + _PROC_SECTION)
    assert proc["mode"] == "detailed"
    assert proc["steps"][0]["tool"] == "Slack API"


def test_extract_procedure_absent_returns_none():
    assert BSJ.extract_procedure(_FIVE_AXES_MD) is None


def test_extract_procedure_section_without_fence_returns_none():
    md = _FIVE_AXES_MD + "## 現状手順\n手順はまだ言語化していない\n"
    assert BSJ.extract_procedure(md) is None


def test_extract_procedure_invalid_json_raises():
    md = _FIVE_AXES_MD + "## 現状手順\n```json\n{broken\n```\n"
    with pytest.raises(ValueError):
        BSJ.extract_procedure(md)


def test_build_includes_procedure_additively():
    payload = BSJ.build(_FIVE_AXES_MD + _PROC_SECTION, "standard")
    assert "procedure" in payload
    assert payload["procedure"]["mode"] == "detailed"
    # 5 軸は従来通り保持される
    assert len(payload["five_axes"]["rows"]) == 5


def test_build_without_procedure_omits_key():
    payload = BSJ.build(_FIVE_AXES_MD, "standard")
    assert "procedure" not in payload
    assert len(payload["five_axes"]["rows"]) == 5


# ---------------------------------------------------------------------------
# validate-interview-json : procedure を持つ完了 interview が schema PASS (C1)
# ---------------------------------------------------------------------------

def _complete_interview(with_procedure=True, procedure=None):
    iv = {
        "filled_ratio": 1,
        "five_axes_complete": True,
        "unresolved": [],
        "needs_excavation": False,
        "abstract_answers": [],
        "five_axes": {
            "rows": [
                {"name": "出力先", "content": "Notion", "depth": "standard"},
                {"name": "情報源", "content": "Slack / 議事録", "depth": "standard"},
                {"name": "共有相手", "content": "経営チーム", "depth": "standard"},
                {"name": "真の課題", "content": "報告作成に時間がかかる", "depth": "standard"},
                {"name": "ナレッジ資産", "content": "過去テンプレート", "depth": "standard", "must": True},
            ],
            "pipeline": {
                "ingest": "Slack", "analysis": "要約", "storage": "Notion",
                "retrieval": "検索", "update": "weekly",
            },
        },
        "intent_contract": {
            "input_spec": {"sources": ["Slack", "議事録"], "trigger": "毎朝",
                           "frequency": "daily", "raw_materials": ["ログ"]},
            "output_spec": {"sink": "Notion", "format": "document",
                            "granularity": "日次", "audience": "経営", "cadence": "daily"},
            "slot_status": {
                "input_spec.sources": {"filled": True, "source": "direct_answer"},
                "input_spec.trigger": {"filled": True, "source": "direct_answer"},
                "input_spec.frequency": {"filled": True, "source": "direct_answer"},
                "input_spec.raw_materials": {"filled": True, "source": "direct_answer"},
                "output_spec.sink": {"filled": True, "source": "direct_answer"},
                "output_spec.format": {"filled": True, "source": "direct_answer"},
                "output_spec.granularity": {"filled": True, "source": "direct_answer"},
                "output_spec.audience": {"filled": True, "source": "direct_answer"},
                "output_spec.cadence": {"filled": True, "source": "direct_answer"},
            },
        },
        "pending_probes": [],
        "qa_log": [
            {"qid": "Q03", "axis": "output", "question_text": "出力先は?",
             "selected_option": "", "raw_answer": "Notion", "normalized_answer": "Notion"},
        ],
    }
    if with_procedure:
        iv["procedure"] = procedure or {
            "mode": "detailed",
            "steps": [{"action": "収集", "input": "Slack", "output": "ログ",
                       "tool": "Slack API", "frequency": "毎朝"}],
        }
    return iv


def _run_validate_iv(tmp_path, data):
    p = tmp_path / "interview.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return subprocess.run([sys.executable, str(VALIDATE_IV), str(p)],
                          capture_output=True, text=True)


def test_validate_iv_complete_with_procedure_passes(tmp_path):
    proc = _run_validate_iv(tmp_path, _complete_interview(with_procedure=True))
    assert proc.returncode == 0, proc.stderr
    assert "PASS" in proc.stdout


def test_validate_iv_complete_without_procedure_still_passes(tmp_path):
    # 後方互換: procedure 未収集の完了 interview も従来通り PASS (procedure は additive optional)
    proc = _run_validate_iv(tmp_path, _complete_interview(with_procedure=False))
    assert proc.returncode == 0, proc.stderr


def test_validate_iv_procedure_overview_fallback_passes(tmp_path):
    proc = _run_validate_iv(tmp_path, _complete_interview(procedure={
        "mode": "overview_fallback", "difficulty_flag": True,
        "overview": {"step_count_estimate": "5工程", "participants": "自分", "frequency": "月次"},
    }))
    assert proc.returncode == 0, proc.stderr


def test_validate_iv_procedure_bad_step_fails_schema(tmp_path):
    # detailed なのに steps 要素が action 欠落 -> schema FAIL (returncode 1)
    proc = _run_validate_iv(tmp_path, _complete_interview(procedure={
        "mode": "detailed", "steps": [{"input": "x", "output": "y", "tool": "z", "frequency": "毎朝"}],
    }))
    assert proc.returncode == 1
    assert "FAIL" in proc.stderr


def test_validate_iv_procedure_detailed_missing_steps_fails(tmp_path):
    # detailed なのに steps 欠落 -> allOf if/then で FAIL
    proc = _run_validate_iv(tmp_path, _complete_interview(procedure={"mode": "detailed"}))
    assert proc.returncode == 1
