"""run-prompt-creator-7layer/scripts/validate-sheet.py の genuine 機能テスト (scripts4)。

Prompt作成シート JSON のフィールド充足度・達成ゴール記述を検証する CLI スクリプト。
純関数 (validate / validate_goals / REQUIRED_FIELDS) を実ファイルから importlib で
ロードして実入力で assert し、main は in-process(argv monkeypatch + SystemExit)で
全終了コード(0/1/2/3/4)と stdout/stderr を踏み、さらに subprocess(sys.executable)で
end-to-end の exit code を確認して `if __name__ == "__main__"` ガード行まで踏む。

注: 同一 script の別角度テストが tests/scripts3 にも存在するため、本ファイルは
名前衝突回避のため _r4 サフィックスを付し、各テストが scripts3 に依存せず単独で
script 行カバレッジ >=80% を達成する自己完結セットとして構成する。

network: false, keychain: なし, 実 repo 書換: なし(tmp_path / stdout のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "prompt-creator"
    / "skills"
    / "run-prompt-creator-7layer"
    / "scripts"
    / "validate-sheet.py"
)

_SPEC = importlib.util.spec_from_file_location("validate_sheet_uut_r4", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _complete():
    """全 12 フィールド(必須/推奨/オプション)を充足する合格 fixture。"""
    return {
        "prompt_name": "P",
        "target_user": "U",
        "purpose": "目的",
        "background": "背景",
        "success_criteria": "完了条件",
        "goals": ["成果状態A", {"description": "成果状態B"}],
        "checklist": ["c1"],
        "challenges": ["課題1"],
        "required_info": ["info1"],
        "constraints": ["制約1"],
        "prompt_issues": "課題テキスト",
        "test_cases": [{"input": "x"}],
    }


def _write(tmp_path, data, name="sheet.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _call_main(monkeypatch, argv):
    monkeypatch.setattr(MOD.sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        MOD.main()
    code = exc.value.code
    return 0 if code is None else code


# ── REQUIRED_FIELDS スキーマ自体の不変条件 ──────────────────────────────────
def test_required_fields_priorities_are_known_values():
    prios = {f["priority"] for f in MOD.REQUIRED_FIELDS}
    assert prios == {"必須", "推奨", "オプション"}


def test_required_fields_array_specs_have_minlength():
    for f in MOD.REQUIRED_FIELDS:
        if f.get("isArray"):
            assert isinstance(f["minLength"], int) and f["minLength"] >= 1


def test_exactly_one_optional_field_is_test_cases():
    opt = [f["key"] for f in MOD.REQUIRED_FIELDS if f["priority"] == "オプション"]
    assert opt == ["test_cases"]


# ── validate_goals 純関数 ───────────────────────────────────────────────────
def test_validate_goals_string_form_accepted():
    assert MOD.validate_goals(["成果Aで終わる状態"]) == []


def test_validate_goals_dict_description_none_treated_empty():
    # description キーは在るが値 None → desc="" → issue
    issues = MOD.validate_goals([{"description": None}])
    assert len(issues) == 1
    assert issues[0]["field"] == "goals[0]"


def test_validate_goals_dict_missing_description_key():
    issues = MOD.validate_goals([{"other": "x"}])
    assert len(issues) == 1
    assert "ゴール1の記述が空" in issues[0]["message"]


def test_validate_goals_non_list_returns_single_issue():
    issues = MOD.validate_goals(42)
    assert issues == [{"field": "goals", "message": "配列ではありません"}]


def test_validate_goals_index_in_message_is_one_based():
    issues = MOD.validate_goals(["ok", "ok2", ""])
    assert issues[0]["field"] == "goals[2]"
    assert "ゴール3の記述が空" in issues[0]["message"]


def test_validate_goals_non_str_non_dict_element_flagged():
    # int/None/list 等は str でも dict でもない → desc="" 経路 → 空とみなし issue
    issues = MOD.validate_goals([123, None, ["x"]])
    assert [i["field"] for i in issues] == ["goals[0]", "goals[1]", "goals[2]"]


# ── validate 純関数: 各分岐 ─────────────────────────────────────────────────
def test_validate_complete_fixture_fully_filled():
    r = MOD.validate(_complete())
    assert r["missing"] == [] and r["warnings"] == [] and r["goalIssues"] == []
    assert len(r["filled"]) == len(MOD.REQUIRED_FIELDS)


def test_validate_none_value_for_recommended_goes_to_missing():
    data = _complete()
    data["checklist"] = None  # 推奨だが欠落は missing 行(オプションでないため)
    r = MOD.validate(data)
    m = [x for x in r["missing"] if x["field"] == "checklist"]
    assert m and m[0]["priority"] == "推奨"


def test_validate_array_non_list_value_reports_zero_current():
    data = _complete()
    data["challenges"] = "文字列"  # isArray 期待 だが非 list
    r = MOD.validate(data)
    m = [x for x in r["missing"] if x["field"] == "challenges"][0]
    assert "現在: 0件" in m["message"]


def test_validate_goals_list_wires_goal_issues():
    data = _complete()
    data["goals"] = ["ok", {"description": ""}]
    r = MOD.validate(data)
    assert [g["field"] for g in r["goalIssues"]] == ["goals[1]"]


def test_validate_goals_non_list_skips_goal_issue_detail():
    data = _complete()
    data["goals"] = "not-a-list"
    r = MOD.validate(data)
    # goals が list でない → 詳細 goalIssues 検証は配線されない
    assert r["goalIssues"] == []
    assert any(m["field"] == "goals" for m in r["missing"])


def test_validate_empty_input_required_in_missing_optional_in_warnings():
    r = MOD.validate({})
    missing = {m["field"] for m in r["missing"]}
    warns = {w["field"] for w in r["warnings"]}
    assert "prompt_name" in missing  # 必須
    assert "checklist" in missing  # 推奨も missing 扱い
    assert "test_cases" in warns  # オプションのみ warning


# ── main in-process: 終了コード/出力セクション ───────────────────────────────
def test_main_no_args_prints_usage_exit2(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["validate-sheet.py"])
    assert code == 2
    assert "Exit codes" in capsys.readouterr().out


def test_main_help_exit0(monkeypatch, capsys):
    assert _call_main(monkeypatch, ["validate-sheet.py", "--help"]) == 0
    assert "Usage" in capsys.readouterr().out


def test_main_missing_file_exit3(monkeypatch, capsys, tmp_path):
    code = _call_main(monkeypatch, ["validate-sheet.py", str(tmp_path / "x.json")])
    assert code == 3
    assert "File not found" in capsys.readouterr().err


def test_main_bad_json_exit1(monkeypatch, capsys, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("}{", encoding="utf-8")
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    assert code == 1
    assert "Invalid JSON" in capsys.readouterr().err


def test_main_complete_exit0_emits_json_block(monkeypatch, capsys, tmp_path):
    p = _write(tmp_path, _complete())
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 0
    assert "充足: 12/12" in out
    parsed = json.loads(out.split("--- JSON結果 ---", 1)[1])
    assert parsed["filled"] and parsed["missing"] == []


def test_main_required_missing_section_and_exit4(monkeypatch, capsys, tmp_path):
    data = _complete()
    del data["purpose"]
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 4
    assert "--- 未充足フィールド ---" in out
    assert "(purpose)" in out


def test_main_array_short_message_rendered(monkeypatch, capsys, tmp_path):
    data = _complete()
    data["challenges"] = []
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 4
    assert "最低1件必要" in out and "現在: 0件" in out


def test_main_warnings_section_when_optional_missing(monkeypatch, capsys, tmp_path):
    data = _complete()
    del data["test_cases"]
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 0  # 必須充足のため OK
    assert "--- 警告 ---" in out and "オプション" in out


def test_main_goal_issue_only_triggers_exit4(monkeypatch, capsys, tmp_path):
    data = _complete()
    data["goals"] = ["ok", "  "]  # 件数は足りるが空白のみ → goalIssue
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 4
    assert "--- ゴール詳細問題 ---" in out
    assert "未充足: 0" in out and "ゴール問題: 1" in out


# ── subprocess end-to-end: __main__ ガード行/終了コードを実プロセスで踏む ────
def _run_cli(args, **kw):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True, **kw
    )


def test_subprocess_complete_exit0(tmp_path):
    p = _write(tmp_path, _complete())
    res = _run_cli([str(p)])
    assert res.returncode == 0
    assert "充足: 12/12" in res.stdout


def test_subprocess_required_missing_exit4(tmp_path):
    data = _complete()
    del data["prompt_name"]
    p = _write(tmp_path, data)
    res = _run_cli([str(p)])
    assert res.returncode == 4


def test_subprocess_no_args_exit2():
    assert _run_cli([]).returncode == 2


def test_subprocess_missing_file_exit3(tmp_path):
    res = _run_cli([str(tmp_path / "nope.json")])
    assert res.returncode == 3
    assert "File not found" in res.stderr
