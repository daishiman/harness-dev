"""run-prompt-creator-7layer/scripts/validate-sheet.py の genuine 機能テスト。

Prompt作成シート JSON の必須/推奨/オプション各フィールド充足度と達成ゴール記述を
検証する純関数を実ファイルから importlib でロードして実入力で assert し、main は
in-process(argv monkeypatch + SystemExit)で全終了経路(0/1/2/3/4)と stdout/stderr を
踏む(subprocess は `--cov` 単体実行では main 本体の行カバレッジに計上されないため)。

カバー分岐:
- validate_goals: 非 list(配列でない) / str ゴール / dict(description 有無) / その他型 /
  空文字・空白のみ → issue / 全充足 → issue なし
- validate: 必須欠落(None/"") → missing / オプション欠落 → warnings /
  isArray 不足(非 list / len < minLength)→ missing(現在件数メッセージ) /
  isArray 充足 → filled / goals 詳細検証配線(list のみ)
- main: -h/--help(exit0) / 引数なし(exit2) / file not found(exit3) /
  不正 JSON(exit1) / 全充足(exit0) / 必須欠落(exit4) / goalIssues あり(exit4) /
  警告・未充足・ゴール詳細問題の各サマリ出力 / JSON結果ブロック出力

network: false, keychain: なし, 実 repo 書換: なし (tmp_path / stdout のみ)。
"""
import importlib.util
import json
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

SPEC = importlib.util.spec_from_file_location("validate_sheet_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── fixtures ─────────────────────────────────────────────────────────────────
def _full_data():
    """全必須/推奨/オプションを充足する合格 fixture。"""
    return {
        "prompt_name": "テストプロンプト",
        "target_user": "想定利用者",
        "purpose": "目的の説明",
        "background": "背景の説明",
        "success_criteria": "完了条件の説明",
        "goals": ["完成状態A", {"description": "完成状態B"}],
        "checklist": ["チェック項目1"],
        "challenges": ["課題1"],
        "required_info": ["必要情報1"],
        "constraints": ["制約1"],
        "prompt_issues": "既存プロンプトの課題",
        "test_cases": [{"input": "入力例"}],
    }


# ── validate_goals ───────────────────────────────────────────────────────────
def test_validate_goals_not_a_list():
    issues = MOD.validate_goals("not a list")
    assert len(issues) == 1
    assert issues[0]["field"] == "goals"
    assert "配列ではありません" in issues[0]["message"]


def test_validate_goals_str_filled_no_issue():
    assert MOD.validate_goals(["完成状態A", "完成状態B"]) == []


def test_validate_goals_dict_with_description_no_issue():
    assert MOD.validate_goals([{"description": "完成状態"}]) == []


def test_validate_goals_dict_without_description_flagged():
    issues = MOD.validate_goals([{"description": ""}])
    assert len(issues) == 1
    assert issues[0]["field"] == "goals[0]"
    assert "ゴール1の記述が空" in issues[0]["message"]


def test_validate_goals_empty_string_flagged():
    issues = MOD.validate_goals([""])
    assert len(issues) == 1
    assert issues[0]["field"] == "goals[0]"


def test_validate_goals_whitespace_only_flagged():
    issues = MOD.validate_goals(["   "])
    assert len(issues) == 1
    assert issues[0]["field"] == "goals[0]"


def test_validate_goals_other_type_flagged():
    # int 等は desc="" 経路 → 空とみなされ issue
    issues = MOD.validate_goals([123, None])
    assert len(issues) == 2
    assert issues[0]["field"] == "goals[0]"
    assert issues[1]["field"] == "goals[1]"


def test_validate_goals_mixed_some_valid_some_invalid():
    issues = MOD.validate_goals(["有効", "", {"description": "有効2"}, {"description": ""}])
    fields = [i["field"] for i in issues]
    assert fields == ["goals[1]", "goals[3]"]


# ── validate ─────────────────────────────────────────────────────────────────
def test_validate_full_data_all_filled():
    r = MOD.validate(_full_data())
    assert r["missing"] == []
    assert r["warnings"] == []
    assert r["goalIssues"] == []
    # 12 フィールド全充足
    assert len(r["filled"]) == len(MOD.REQUIRED_FIELDS)


def test_validate_required_missing_none_and_empty_string():
    data = _full_data()
    data["prompt_name"] = None  # None 欠落
    data["purpose"] = ""  # 空文字欠落
    r = MOD.validate(data)
    missing_keys = {m["field"] for m in r["missing"]}
    assert "prompt_name" in missing_keys
    assert "purpose" in missing_keys
    for m in r["missing"]:
        if m["field"] in ("prompt_name", "purpose"):
            assert m["priority"] == "必須"


def test_validate_optional_missing_goes_to_warnings():
    data = _full_data()
    del data["test_cases"]  # オプション欠落
    r = MOD.validate(data)
    warn_keys = {w["field"] for w in r["warnings"]}
    assert "test_cases" in warn_keys
    assert all(w["label"] for w in r["warnings"])
    # オプション欠落は missing に入らない
    assert "test_cases" not in {m["field"] for m in r["missing"]}


def test_validate_array_too_short_reports_current_count():
    data = _full_data()
    data["challenges"] = []  # isArray minLength=1 不足(空 list)
    r = MOD.validate(data)
    # 空 list は value=="" でなく None でもないので isArray 分岐に到達
    chal = [m for m in r["missing"] if m["field"] == "challenges"]
    assert len(chal) == 1
    assert "最低1件必要" in chal[0]["message"]
    assert "現在: 0件" in chal[0]["message"]


def test_validate_array_field_not_a_list():
    data = _full_data()
    data["goals"] = "文字列(配列でない)"
    r = MOD.validate(data)
    g = [m for m in r["missing"] if m["field"] == "goals"]
    assert len(g) == 1
    assert "現在: 0件" in g[0]["message"]
    # goals が list でないので goalIssues 詳細検証は走らない
    assert r["goalIssues"] == []


def test_validate_array_field_partially_filled_passes_minlength():
    data = _full_data()
    data["required_info"] = ["1件のみ"]  # minLength=1 を満たす
    r = MOD.validate(data)
    assert "required_info" in {f["field"] for f in r["filled"]}


def test_validate_goal_issues_wired_when_goals_is_list():
    data = _full_data()
    data["goals"] = ["有効", ""]  # 2件目が空 → goalIssue
    r = MOD.validate(data)
    assert len(r["goalIssues"]) == 1
    assert r["goalIssues"][0]["field"] == "goals[1]"


def test_validate_empty_dict_all_required_missing():
    r = MOD.validate({})
    # 必須は missing、オプションは warnings
    required_labels = {
        f["key"] for f in MOD.REQUIRED_FIELDS if f["priority"] != "オプション"
    }
    missing_keys = {m["field"] for m in r["missing"]}
    assert required_labels.issubset(missing_keys)
    opt_keys = {f["key"] for f in MOD.REQUIRED_FIELDS if f["priority"] == "オプション"}
    assert opt_keys.issubset({w["field"] for w in r["warnings"]})
    assert r["filled"] == []


# ── main: in-process (argv monkeypatch + SystemExit) ─────────────────────────
def _call_main(monkeypatch, argv):
    monkeypatch.setattr(MOD.sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        MOD.main()
    code = exc.value.code
    return 0 if code is None else code


def _write(tmp_path, data, name="sheet.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_main_help_short_exit0(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["validate-sheet.py", "-h"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Usage:" in out


def test_main_help_long_exit0(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["validate-sheet.py", "--help"])
    assert code == 0
    assert "Usage:" in capsys.readouterr().out


def test_main_no_args_exit2(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["validate-sheet.py"])
    out = capsys.readouterr().out
    assert code == 2
    assert "Usage:" in out


def test_main_file_not_found_exit3(monkeypatch, capsys, tmp_path):
    missing = str(tmp_path / "nope.json")
    code = _call_main(monkeypatch, ["validate-sheet.py", missing])
    err = capsys.readouterr().err
    assert code == 3
    assert "File not found" in err


def test_main_invalid_json_exit1(monkeypatch, capsys, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json", encoding="utf-8")
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    err = capsys.readouterr().err
    assert code == 1
    assert "Invalid JSON" in err


def test_main_full_data_exit0(monkeypatch, capsys, tmp_path):
    p = _write(tmp_path, _full_data())
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 0
    assert "充足: 12/12" in out
    assert "未充足: 0" in out
    assert "ゴール問題: 0" in out
    # JSON結果ブロックが出力される
    assert "--- JSON結果 ---" in out
    json_part = out.split("--- JSON結果 ---", 1)[1]
    parsed = json.loads(json_part)
    assert parsed["missing"] == []


def test_main_required_missing_exit4_and_section(monkeypatch, capsys, tmp_path):
    data = _full_data()
    del data["prompt_name"]  # 必須欠落
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 4
    assert "--- 未充足フィールド ---" in out
    assert "プロンプト名" in out
    assert "(prompt_name)" in out


def test_main_array_short_message_in_missing_section(monkeypatch, capsys, tmp_path):
    data = _full_data()
    data["goals"] = []  # 必須 isArray 不足
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 4
    assert "最低1件必要" in out  # message 付き missing 行


def test_main_warnings_section_emitted(monkeypatch, capsys, tmp_path):
    data = _full_data()
    del data["test_cases"]  # オプション欠落 → warnings
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    # 必須は揃っているので exit0 だが warnings セクションは出る
    assert code == 0
    assert "--- 警告 ---" in out
    assert "テストケース" in out


def test_main_goal_issues_section_and_exit4(monkeypatch, capsys, tmp_path):
    data = _full_data()
    data["goals"] = ["有効", ""]  # 2件目空 → goalIssue
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 4
    assert "--- ゴール詳細問題 ---" in out
    assert "goals[1]" in out


def test_main_goal_issues_alone_trigger_exit4(monkeypatch, capsys, tmp_path):
    # 必須はすべて充足だが goalIssues のみで exit4 になることを確認
    data = _full_data()
    data["goals"] = ["有効", "   "]  # 空白のみ → goalIssue, 件数自体は >=1
    p = _write(tmp_path, data)
    code = _call_main(monkeypatch, ["validate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 4
    assert "未充足: 0" in out  # missing は無いのに
    assert "ゴール問題: 1" in out
