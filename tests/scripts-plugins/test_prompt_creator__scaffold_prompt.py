"""run-prompt-creator-7layer/scripts/scaffold-prompt.py の genuine 機能テスト。

ヒアリング結果 JSON から7層構造(Layer5 ゴールシーク型)プロンプト骨格を
yaml/markdown/json/xml で決定論生成する。純関数を実ファイルから importlib で
ロードして実入力で assert し、main は subprocess(sys.executable) で argv 依存の
分岐(format/agents/output/exit code)を確認する。

カバー分岐:
- _parse_int: 正常整数 / 符号付き / 前後空白 / 末尾文字無視(JS parseInt) / 解釈不能 None
- get_arg: フラグ有り値取得 / フラグ無し None / フラグ末尾で値欠落 None
- _slice: total==1 全返し / 複数分割
- goal_hints_for: goals(str/dict) / 旧 steps フォールバック / 空 []
- checklist_hints_for: checklist(str/dict) / 空 []
- scaffold_yaml: ヒント有り/無し両系統, 制約・課題行, test_cases/required_info 有無,
  単一/複数エージェント(input_provider/output_receiver/prereq/successor 分岐)
- scaffold_markdown / scaffold_json / scaffold_xml: 同様に主要分岐 + XML エスケープ
- main(CLI): help(-h, exit0) / 引数なし usage(exit2) / file not found(exit3) /
  format 欠落・不正(exit2) / agents 不正(exit2) / 不正 JSON(exit1) /
  正常 stdout 出力 / --output ファイル書き出し / LLM_FILL 統計 stderr

network: false, keychain: なし, 実 repo 書換: なし (tmp_path / stdout のみ)。
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
    / "scaffold-prompt.py"
)

SPEC = importlib.util.spec_from_file_location("scaffold_prompt_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── _parse_int ──────────────────────────────────────────────────────────────
def test_parse_int_plain():
    assert MOD._parse_int("3") == 3


def test_parse_int_signed_and_whitespace():
    assert MOD._parse_int("  -5") == -5
    assert MOD._parse_int("+7") == 7


def test_parse_int_trailing_text_ignored():
    # JS parseInt("3abc",10) == 3
    assert MOD._parse_int("3abc") == 3


def test_parse_int_unparseable_returns_none():
    assert MOD._parse_int("abc") is None
    assert MOD._parse_int("") is None


# ── get_arg ─────────────────────────────────────────────────────────────────
def test_get_arg_present(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["prog", "in.json", "--format", "yaml"])
    assert MOD.get_arg("format") == "yaml"


def test_get_arg_absent(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["prog", "in.json"])
    assert MOD.get_arg("format") is None


def test_get_arg_flag_at_end_no_value(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["prog", "in.json", "--output"])
    assert MOD.get_arg("output") is None


# ── _slice ──────────────────────────────────────────────────────────────────
def test_slice_total_one_returns_all():
    assert MOD._slice([1, 2, 3], 0, 1) == [1, 2, 3]


def test_slice_splits_across_agents():
    arr = ["a", "b", "c", "d"]
    assert MOD._slice(arr, 0, 2) == ["a", "b"]
    assert MOD._slice(arr, 1, 2) == ["c", "d"]


# ── goal_hints_for ──────────────────────────────────────────────────────────
def test_goal_hints_from_goals_str_and_dict():
    data = {"goals": ["完成形A", {"description": "完成形B"}]}
    assert MOD.goal_hints_for(data, 0, 1) == ["完成形A", "完成形B"]


def test_goal_hints_fallback_to_steps():
    data = {"steps": [{"description": "手順1"}, {"description": "手順2"}]}
    assert MOD.goal_hints_for(data, 0, 1) == ["手順1", "手順2"]


def test_goal_hints_empty():
    assert MOD.goal_hints_for({}, 0, 1) == []


def test_goal_hints_dict_without_description_filtered():
    data = {"goals": [{"description": ""}, "X"]}
    assert MOD.goal_hints_for(data, 0, 1) == ["X"]


# ── checklist_hints_for ─────────────────────────────────────────────────────
def test_checklist_hints_str_and_dict():
    data = {"checklist": ["条件A", {"item": "条件B"}]}
    assert MOD.checklist_hints_for(data, 0, 1) == ["条件A", "条件B"]


def test_checklist_hints_empty():
    assert MOD.checklist_hints_for({}, 0, 1) == []


# ── scaffold_yaml ───────────────────────────────────────────────────────────
def _rich_data():
    return {
        "prompt_name": "テストプロンプト",
        "target_user": "利用者",
        "purpose": "目的説明",
        "background": "背景説明",
        "success_criteria": "成功基準",
        "constraints": ["制約1", "制約2"],
        "challenges": ["課題1"],
        "goals": ["ゴールA", "ゴールB"],
        "checklist": ["チェック1"],
        "required_info": ["質問1"],
        "test_cases": [{"input": "入力例1"}],
    }


def test_scaffold_yaml_rich_contains_data():
    out = MOD.scaffold_yaml(_rich_data(), 1)
    assert "テストプロンプト" in out
    assert "制約1" in out and "制約2" in out
    assert "課題1" in out
    assert "ゴールA / ゴールB" in out  # 単一エージェントは全 goals を結合
    assert "チェック1" in out
    assert "質問1" in out
    assert "入力例1" in out
    assert "外部/ユーザー" in out  # i==0 input provider
    assert "ユーザー" in out  # last output receiver


def test_scaffold_yaml_empty_data_uses_llm_fill():
    out = MOD.scaffold_yaml({}, 1)
    assert "{{LLM_FILL" in out
    assert "CONST_001" in out  # 空 constraints のデフォルト行
    assert "CHAL_001" in out


def test_scaffold_yaml_multi_agent_splits_and_links():
    out = MOD.scaffold_yaml(_rich_data(), 2)
    # 2 エージェント: goals が分割される → 片方に A、もう片方に B
    assert "ゴールA" in out and "ゴールB" in out
    # 中間エージェントの後続/前提 LLM_FILL 経路
    assert "後続エージェント名" in out
    assert "前エージェント名" in out


def test_scaffold_yaml_purpose_truncated_to_60():
    long = "あ" * 100
    out = MOD.scaffold_yaml({"purpose": long}, 1)
    assert ("あ" * 60) in out
    # 61 文字目は出ない (切り詰め)
    assert ("あ" * 61) not in out.split("\n")[1]


# ── scaffold_markdown ───────────────────────────────────────────────────────
def test_scaffold_markdown_rich():
    out = MOD.scaffold_markdown(_rich_data(), 1)
    assert "# テストプロンプト" in out
    assert "CONST_001: 制約1" in out
    assert "CHAL_001: 課題1" in out
    assert "達成ゴール: ゴールA / ゴールB" in out
    assert "- [ ] チェック1" in out
    assert "- 質問1" in out


def test_scaffold_markdown_empty_uses_llm_fill():
    out = MOD.scaffold_markdown({}, 2)
    assert "{{LLM_FILL" in out
    assert "エージェント1" in out and "エージェント2" in out


# ── scaffold_json ───────────────────────────────────────────────────────────
def test_scaffold_json_rich_valid_and_populated():
    out = MOD.scaffold_json(_rich_data(), 1)
    obj = json.loads(out)
    assert obj["layer1_基本定義"]["メタ情報"]["プロジェクトID"] == "テストプロンプト"
    agents = obj["layer5_エージェント定義"]["エージェント"]
    assert agents[0]["ゴール定義"]["達成ゴール"] == "ゴールA / ゴールB"
    assert agents[0]["完了チェックリスト"][0]["項目"] == "チェック1"
    assert obj["layer2_ドメイン定義"]["ビジネスルール"][0]["内容"] == "制約1"
    assert obj["layer7_ユーザーインタラクション"]["初回質問"] == ["質問1"]


def test_scaffold_json_empty_defaults():
    obj = json.loads(MOD.scaffold_json({}, 1))
    assert obj["layer1_基本定義"]["メタ情報"]["プロジェクトID"] == "{{LLM_FILL}}"
    assert obj["layer7_ユーザーインタラクション"]["初回質問"] == ["{{LLM_FILL}}"]
    agents = obj["layer5_エージェント定義"]["エージェント"]
    assert agents[0]["ゴール定義"]["達成ゴール"] == "{{LLM_FILL: 成果状態で記述}}"


def test_scaffold_json_multi_agent_links():
    obj = json.loads(MOD.scaffold_json(_rich_data(), 2))
    agents = obj["layer5_エージェント定義"]["エージェント"]
    assert agents[0]["インターフェース"]["入力"][0]["提供元"] == "外部/ユーザー"
    assert agents[1]["インターフェース"]["出力"][0]["受領先"] == "ユーザー"
    # 中間/非末尾の LLM_FILL 経路
    assert agents[0]["インターフェース"]["出力"][0]["受領先"] == "{{LLM_FILL}}"
    assert agents[1]["インターフェース"]["入力"][0]["提供元"] == "{{LLM_FILL}}"


# ── scaffold_xml ────────────────────────────────────────────────────────────
def test_scaffold_xml_rich_and_escaping():
    data = _rich_data()
    data["challenges"] = ["a < b & c > d"]  # エスケープ対象
    out = MOD.scaffold_xml(data, 1)
    assert '<prompt name="テストプロンプト">' in out
    assert 'id="CONST_001"' in out
    assert "a &lt; b &amp; c &gt; d" in out  # esc() 適用
    assert "ゴールA / ゴールB" in out
    assert "<question><![CDATA[質問1]]></question>" in out


def test_scaffold_xml_empty_defaults():
    out = MOD.scaffold_xml({}, 1)
    assert 'id="CONST_001"' in out
    assert 'id="CHAL_001"' in out
    assert "{{LLM_FILL" in out


def test_scaffold_xml_esc_handles_none():
    # esc(None) → "" の経路 (内部 closure を直接は呼べないので空フィールド経由で)
    out = MOD.scaffold_xml({}, 1)
    assert "<target-user>" in out


# ── main CLI: subprocess ────────────────────────────────────────────────────
def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(cwd) if cwd else None,
    )


def _write_input(tmp_path, data):
    p = tmp_path / "hearing.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_cli_help_exit_zero():
    res = _run("-h")
    assert res.returncode == 0
    assert "Usage:" in res.stdout


def test_cli_no_args_usage_exit_2():
    res = _run()
    assert res.returncode == 2
    assert "Usage:" in res.stdout


def test_cli_file_not_found_exit_3(tmp_path):
    res = _run(str(tmp_path / "missing.json"), "--format", "yaml")
    assert res.returncode == 3
    assert "File not found" in res.stderr


def test_cli_format_missing_exit_2(tmp_path):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    res = _run(str(p))
    assert res.returncode == 2
    assert "--format required" in res.stderr


def test_cli_format_invalid_exit_2(tmp_path):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    res = _run(str(p), "--format", "toml")
    assert res.returncode == 2
    assert "--format required" in res.stderr


def test_cli_agents_invalid_exit_2(tmp_path):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    res = _run(str(p), "--format", "yaml", "--agents", "0")
    assert res.returncode == 2
    assert "--agents must be >= 1" in res.stderr


def test_cli_agents_nonnumeric_exit_2(tmp_path):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    res = _run(str(p), "--format", "yaml", "--agents", "abc")
    assert res.returncode == 2
    assert "--agents must be >= 1" in res.stderr


def test_cli_invalid_json_exit_1(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid", encoding="utf-8")
    res = _run(str(p), "--format", "yaml")
    assert res.returncode == 1
    assert "Invalid JSON" in res.stderr


def test_cli_yaml_to_stdout_with_stats(tmp_path):
    p = _write_input(tmp_path, _rich_data())
    res = _run(str(p), "--format", "yaml")
    assert res.returncode == 0, res.stderr
    assert "テストプロンプト" in res.stdout
    assert "[STATS]" in res.stderr
    assert "自動充填" in res.stderr


def test_cli_json_format_valid(tmp_path):
    p = _write_input(tmp_path, _rich_data())
    res = _run(str(p), "--format", "json")
    assert res.returncode == 0, res.stderr
    obj = json.loads(res.stdout)
    assert obj["layer1_基本定義"]["メタ情報"]["プロジェクトID"] == "テストプロンプト"


def test_cli_output_file_written(tmp_path):
    p = _write_input(tmp_path, _rich_data())
    out_file = tmp_path / "result.md"
    res = _run(str(p), "--format", "markdown", "--output", str(out_file))
    assert res.returncode == 0, res.stderr
    assert "[OK]" in res.stdout
    assert out_file.exists()
    assert "# テストプロンプト" in out_file.read_text(encoding="utf-8")


def test_cli_xml_format_and_agents_count(tmp_path):
    p = _write_input(tmp_path, _rich_data())
    res = _run(str(p), "--format", "xml", "--agents", "3")
    assert res.returncode == 0, res.stderr
    # 3 エージェント分の <agent ...> が出る
    assert res.stdout.count("<agent ") == 3


# ── main() in-process (argv monkeypatch + SystemExit) ────────────────────────
# subprocess 経由のテストは sitecustomize 連携が無い `--cov` 単体実行では main 本体の
# 行カバレッジが計上されないため、in-process でも全終了経路を踏む。
def _call_main(monkeypatch, argv):
    monkeypatch.setattr(MOD.sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        MOD.main()
    return exc.value.code


def test_main_help_exit_zero_in_process(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["scaffold-prompt.py", "-h"])
    assert code == 0
    assert "Usage:" in capsys.readouterr().out


def test_main_no_args_usage_exit_2_in_process(monkeypatch, capsys):
    # argv が1個 (プログラム名のみ) → len<2 で usage 表示 exit 2
    code = _call_main(monkeypatch, ["scaffold-prompt.py"])
    assert code == 2
    assert "Usage:" in capsys.readouterr().out


def test_main_file_not_found_exit_3_in_process(monkeypatch, tmp_path, capsys):
    missing = str(tmp_path / "missing.json")
    code = _call_main(monkeypatch, ["scaffold-prompt.py", missing, "--format", "yaml"])
    assert code == 3
    assert "File not found" in capsys.readouterr().err


def test_main_format_missing_exit_2_in_process(monkeypatch, tmp_path, capsys):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    code = _call_main(monkeypatch, ["scaffold-prompt.py", str(p)])
    assert code == 2
    assert "--format required" in capsys.readouterr().err


def test_main_format_invalid_exit_2_in_process(monkeypatch, tmp_path, capsys):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    code = _call_main(monkeypatch, ["scaffold-prompt.py", str(p), "--format", "toml"])
    assert code == 2
    assert "--format required" in capsys.readouterr().err


def test_main_agents_invalid_exit_2_in_process(monkeypatch, tmp_path, capsys):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    code = _call_main(monkeypatch, ["scaffold-prompt.py", str(p), "--format", "yaml", "--agents", "0"])
    assert code == 2
    assert "--agents must be >= 1" in capsys.readouterr().err


def test_main_agents_nonnumeric_exit_2_in_process(monkeypatch, tmp_path, capsys):
    p = _write_input(tmp_path, {"prompt_name": "x"})
    code = _call_main(monkeypatch, ["scaffold-prompt.py", str(p), "--format", "yaml", "--agents", "abc"])
    assert code == 2
    assert "--agents must be >= 1" in capsys.readouterr().err


def test_main_invalid_json_exit_1_in_process(monkeypatch, tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid", encoding="utf-8")
    code = _call_main(monkeypatch, ["scaffold-prompt.py", str(p), "--format", "yaml"])
    assert code == 1
    assert "Invalid JSON" in capsys.readouterr().err


def test_main_yaml_stdout_exit_0_in_process(monkeypatch, tmp_path, capsys):
    p = _write_input(tmp_path, _rich_data())
    code = _call_main(monkeypatch, ["scaffold-prompt.py", str(p), "--format", "yaml"])
    cap = capsys.readouterr()
    assert code == 0
    assert "テストプロンプト" in cap.out
    # LLM_FILL 統計が stderr に出る (filled_count / fill_count 経路)
    assert "[STATS]" in cap.err
    assert "自動充填" in cap.err


def test_main_output_file_written_exit_0_in_process(monkeypatch, tmp_path, capsys):
    p = _write_input(tmp_path, _rich_data())
    out_file = tmp_path / "result.json"
    code = _call_main(
        monkeypatch,
        ["scaffold-prompt.py", str(p), "--format", "json", "--output", str(out_file)],
    )
    cap = capsys.readouterr()
    assert code == 0
    assert "[OK]" in cap.out
    assert out_file.exists()
    obj = json.loads(out_file.read_text(encoding="utf-8"))
    assert obj["layer1_基本定義"]["メタ情報"]["プロジェクトID"] == "テストプロンプト"


def test_main_empty_data_stats_zero_filled(monkeypatch, tmp_path, capsys):
    # data に LAYER_MAPPING キーが無い → filled_count==0 経路 + 多数 LLM_FILL
    p = _write_input(tmp_path, {})
    code = _call_main(monkeypatch, ["scaffold-prompt.py", str(p), "--format", "markdown"])
    cap = capsys.readouterr()
    assert code == 0
    assert "自動充填: 0項目" in cap.err
