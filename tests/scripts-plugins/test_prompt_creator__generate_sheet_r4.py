"""run-prompt-creator-7layer/scripts/generate-sheet.py の genuine 機能テスト (scripts4)。

ヒアリング結果 JSON から Prompt作成シート(ゴール・完了チェックリスト等)Markdown を
生成する CLI スクリプト。純関数 (generate_sheet / get_arg) を実ファイルから importlib で
ロードして実入力で assert し、main は in-process(argv monkeypatch + SystemExit +
tmp_path 出力 / stdout)で全終了コード(0/1/2/3)と各ブランチを踏み、さらに
subprocess(sys.executable)で end-to-end と `if __name__ == "__main__"` ガード行を踏む。

名前衝突回避のため _r4 サフィックスを付し、scripts/scripts2/scripts3 に同名ファイルは
作らない。各テストは単独で script 行カバレッジ >=80% を達成する自己完結セット。

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
    / "generate-sheet.py"
)

_SPEC = importlib.util.spec_from_file_location("generate_sheet_uut_r4", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _full():
    """全フィールドを充足する fixture(全分岐の充足側を踏む)。"""
    return {
        "prompt_name": "請求書チェッカー",
        "target_user": "経理担当",
        "purpose": "発行漏れ検知",
        "background": "手作業が煩雑",
        "success_criteria": "差分0で完了",
        "goals": [
            "成果状態A",  # str 形式
            {"description": "成果状態B", "output_format": "JSON配列"},  # dict + output_format
            {"description": "成果状態C"},  # output_format 無し → fmt_idx 進まない
        ],
        "checklist": [
            "単純項目",  # str 形式
            {"item": "判定付き", "judgement": "YES/NO"},  # dict + judgement
            {"item": "判定無し"},  # dict, judgement 無し
        ],
        "challenges": ["課題1", "課題2"],
        "required_info": ["前月台帳", "今月台帳"],
        "constraints": ["標準ライブラリのみ"],
        "prompt_issues": "誤検知が残る",
        "test_cases": [
            {"input": "in1", "expected_output": "out1"},
            {"input": "in2"},  # expected_output 欠落 → fallback "未定義"
        ],
    }


def _write(tmp_path, data, name="hearing.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _call_main(monkeypatch, argv):
    monkeypatch.setattr(MOD.sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        MOD.main()
    code = exc.value.code
    return 0 if code is None else code


# ── get_arg 純関数 ──────────────────────────────────────────────────────────
def test_get_arg_returns_value_after_flag(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["g.py", "h.json", "--output", "out.md"])
    assert MOD.get_arg("output") == "out.md"


def test_get_arg_absent_flag_returns_none(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["g.py", "h.json"])
    assert MOD.get_arg("output") is None


def test_get_arg_flag_at_end_without_value_returns_none(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["g.py", "h.json", "--output"])
    assert MOD.get_arg("output") is None  # idx+1 が範囲外


def test_get_arg_flag_with_empty_value_returns_none(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["g.py", "h.json", "--output", ""])
    assert MOD.get_arg("output") is None  # 空文字は falsy で None


# ── generate_sheet 純関数: 充足側の全要素 ───────────────────────────────────
def test_generate_sheet_full_renders_all_sections():
    md = MOD.generate_sheet(_full())
    assert md.startswith("# Prompt作成シート")
    # ヘッダーフィールド
    assert "- 請求書チェッカー" in md
    assert "- 経理担当" in md
    assert "- 発行漏れ検知" in md
    assert "- 手作業が煩雑" in md
    assert "- 差分0で完了" in md
    assert "- 誤検知が残る" in md


def test_generate_sheet_goals_string_and_dict_numbered():
    md = MOD.generate_sheet(_full())
    assert "1. 成果状態A" in md  # str 形式
    assert "2. 成果状態B" in md  # dict.description
    assert "3. 成果状態C" in md


def test_generate_sheet_checklist_str_and_judgement():
    md = MOD.generate_sheet(_full())
    assert "- [ ] 単純項目" in md
    assert "- [ ] 判定付き — 判定: YES/NO" in md  # judgement 付与経路
    assert "- [ ] 判定無し" in md  # dict だが judgement 無し


def test_generate_sheet_output_format_only_for_dict_goals_with_format():
    md = MOD.generate_sheet(_full())
    # output_format を持つのは goals[1] のみ → ゴール1の成果物として 1 ブロック
    assert "## ゴール1の成果物" in md
    assert "JSON配列" in md
    assert "## ゴール2の成果物" not in md  # fmt_idx は format 保有ゴールのみ加算


def test_generate_sheet_challenges_required_info_constraints():
    md = MOD.generate_sheet(_full())
    assert "- 課題1" in md and "- 課題2" in md
    assert "- 前月台帳" in md and "- 今月台帳" in md
    # constraints は固定先頭行 + ユーザー定義
    assert "- 各周回末に中間成果物アンカーを記録し、完了チェックリストで充足を確認する" in md
    assert "- 標準ライブラリのみ" in md


def test_generate_sheet_test_cases_numbered_with_fallback():
    md = MOD.generate_sheet(_full())
    assert "# 想定するユーザー入力1" in md and "in1" in md
    assert "# 期待される出力1" in md and "out1" in md
    assert "# 想定するユーザー入力2" in md and "in2" in md
    # test_cases[1] は expected_output 欠落 → "未定義" fallback
    assert "# 期待される出力2" in md


# ── generate_sheet 純関数: 空入力 fallback ──────────────────────────────────
def test_generate_sheet_empty_uses_all_fallbacks():
    md = MOD.generate_sheet({})
    assert "1. 未定義" in md  # goals_block fallback
    assert "- [ ] 未定義" in md  # checklist_block fallback
    assert "```\n未定義\n```" in md  # output_formats_block fallback
    # challenges / required_info の "- 未定義" fallback
    assert "- 未定義" in md
    # test_cases_fallback ブロック
    assert "# 想定するユーザー入力1" in md and "# 期待される出力1" in md
    # ヘッダーフィールド未定義
    assert md.count("未定義") >= 8


def test_generate_sheet_constraints_only_fixed_line_when_empty():
    md = MOD.generate_sheet({})
    # 制約セクションは空でも固定先頭行が常に出る
    assert "- 各周回末に中間成果物アンカーを記録し、完了チェックリストで充足を確認する" in md


def test_generate_sheet_goal_dict_description_none_falls_back():
    md = MOD.generate_sheet({"goals": [{"description": None}]})
    assert "1. 未定義" in md  # description が falsy → "未定義"


def test_generate_sheet_checklist_dict_item_none_falls_back():
    md = MOD.generate_sheet({"checklist": [{"item": None}]})
    assert "- [ ] 未定義" in md


def test_generate_sheet_test_case_both_fields_missing():
    md = MOD.generate_sheet({"test_cases": [{}]})
    # input / expected_output 両方欠落 → 両方 "未定義"
    assert "# 想定するユーザー入力1" in md
    assert md.count("未定義") >= 2


# ── main in-process: stdout / output / 終了コード ───────────────────────────
def test_main_stdout_exit0(monkeypatch, capsys, tmp_path):
    p = _write(tmp_path, _full())
    code = _call_main(monkeypatch, ["generate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 0
    assert "# Prompt作成シート" in out
    assert "- 請求書チェッカー" in out


def test_main_output_file_exit0(monkeypatch, capsys, tmp_path):
    p = _write(tmp_path, _full())
    out = tmp_path / "sheet.md"
    code = _call_main(monkeypatch, ["generate-sheet.py", str(p), "--output", str(out)])
    assert code == 0
    assert out.read_text(encoding="utf-8").startswith("# Prompt作成シート")
    assert "[OK] Prompt作成シートを出力" in capsys.readouterr().out


def test_main_no_args_exit2(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["generate-sheet.py"])
    assert code == 2
    assert "Usage:" in capsys.readouterr().out


def test_main_help_exit0(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["generate-sheet.py", "--help"])
    assert code == 0
    assert "Usage:" in capsys.readouterr().out


def test_main_dash_h_exit0(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["generate-sheet.py", "-h"])
    assert code == 0
    assert "Exit codes" in capsys.readouterr().out


def test_main_missing_file_exit3(monkeypatch, capsys, tmp_path):
    code = _call_main(monkeypatch, ["generate-sheet.py", str(tmp_path / "nope.json")])
    assert code == 3
    assert "File not found" in capsys.readouterr().err


def test_main_bad_json_exit1(monkeypatch, capsys, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("}{not json", encoding="utf-8")
    code = _call_main(monkeypatch, ["generate-sheet.py", str(p)])
    assert code == 1
    assert "Invalid JSON" in capsys.readouterr().err


def test_main_empty_object_json_exit0_with_fallbacks(monkeypatch, capsys, tmp_path):
    p = _write(tmp_path, {})
    code = _call_main(monkeypatch, ["generate-sheet.py", str(p)])
    out = capsys.readouterr().out
    assert code == 0
    assert "1. 未定義" in out


# ── subprocess end-to-end: __main__ ガード行/終了コードを実プロセスで踏む ────
def _run_cli(args, **kw):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True, **kw
    )


def test_subprocess_stdout_exit0(tmp_path):
    p = _write(tmp_path, _full())
    res = _run_cli([str(p)])
    assert res.returncode == 0
    assert "# Prompt作成シート" in res.stdout


def test_subprocess_output_file_exit0(tmp_path):
    p = _write(tmp_path, _full())
    out = tmp_path / "s.md"
    res = _run_cli([str(p), "--output", str(out)])
    assert res.returncode == 0 and out.exists()


def test_subprocess_no_args_exit2():
    assert _run_cli([]).returncode == 2


def test_subprocess_missing_file_exit3(tmp_path):
    res = _run_cli([str(tmp_path / "x.json")])
    assert res.returncode == 3
    assert "File not found" in res.stderr


def test_subprocess_bad_json_exit1(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("{,}", encoding="utf-8")
    res = _run_cli([str(p)])
    assert res.returncode == 1
