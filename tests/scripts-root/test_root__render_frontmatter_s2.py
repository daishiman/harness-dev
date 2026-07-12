"""scripts/render-frontmatter.py の main() を in-process で網羅する補完テスト。

既存 tests/scripts-root/test_root__render_frontmatter.py は render() /
needs_os_preamble() を in-process で、main() を subprocess で検証している。
subprocess 経由の main() は --cov=scripts に計上されないため、本ファイルは
sys.argv を monkeypatch して main() を **直接呼び**、各 CLI 分岐
(引数なし / ファイル欠落 / --output 引数欠落 / JSON 破損 / stdout 出力 /
--output 書き込み) の return code と副作用 (stdout / 生成ファイル) を assert する。

render() のフィールド網羅 (list 展開 / key remap / OS preamble) も main 経由で
end-to-end に確認する。すべて network/外部 I/O なし、書き込みは tmp_path 配下のみ。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "render-frontmatter.py"

SPEC = importlib.util.spec_from_file_location("render_frontmatter_s2", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- needs_os_preamble(): 純関数の true/false 全分岐 (この補完ファイルを自己完結化) ---

def test_needs_os_preamble_bool_true():
    assert MOD.needs_os_preamble({"cross_platform": True}) is True


def test_needs_os_preamble_string_true_either_flag():
    assert MOD.needs_os_preamble({"os_preamble_required": "true"}) is True
    assert MOD.needs_os_preamble({"cross_platform": "True"}) is True


def test_needs_os_preamble_false_for_non_true_string_and_absent():
    # str "no" / 既定欠落 -> _is_true の False 分岐 (line 69) を踏む
    assert MOD.needs_os_preamble({}) is False
    assert MOD.needs_os_preamble({"cross_platform": "no"}) is False
    assert MOD.needs_os_preamble({"cross_platform": False}) is False


def _write_brief(tmp_path: Path, data) -> Path:
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _run_main(monkeypatch, *args) -> int:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *args])
    return MOD.main()


# --- main(): error 経路 (in-process) -----------------------------------------

def test_main_no_args_returns_2(monkeypatch, capsys):
    rc = _run_main(monkeypatch)
    err = capsys.readouterr().err
    assert rc == 2
    assert "usage:" in err


def test_main_brief_not_found_returns_2(monkeypatch, capsys):
    rc = _run_main(monkeypatch, "/no/such/brief.json")
    err = capsys.readouterr().err
    assert rc == 2
    assert "not found" in err


def test_main_output_flag_without_path_returns_2(monkeypatch, capsys, tmp_path):
    brief = _write_brief(tmp_path, {"name": "n", "body": "B"})
    rc = _run_main(monkeypatch, str(brief), "--output")
    err = capsys.readouterr().err
    assert rc == 2
    assert "--output requires a path" in err


def test_main_invalid_json_returns_1(monkeypatch, capsys, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    rc = _run_main(monkeypatch, str(bad))
    err = capsys.readouterr().err
    assert rc == 1
    assert "JSON parse error" in err


# --- main(): success 経路 (in-process) ---------------------------------------

def test_main_renders_to_stdout(monkeypatch, capsys, tmp_path):
    brief = _write_brief(
        tmp_path, {"name": "run-x", "description": "d", "body": "BODY"}
    )
    rc = _run_main(monkeypatch, str(brief))
    out = capsys.readouterr().out
    assert rc == 0
    assert out == "---\nname: run-x\ndescription: d\n---\n\nBODY\n"


def test_main_writes_output_file_with_preamble(monkeypatch, capsys, tmp_path):
    brief = _write_brief(
        tmp_path,
        {
            "name": "run-x",
            "description": "d",
            "body": "B",
            "cross_platform": True,
            "allowed_tools": ["Read", "Bash"],
            "argument_hint": "<file>",
        },
    )
    out_file = tmp_path / "SKILL.md"
    rc = _run_main(monkeypatch, str(brief), "--output", str(out_file))
    stdout = capsys.readouterr().out
    assert rc == 0
    assert "ok: wrote" in stdout
    text = out_file.read_text(encoding="utf-8")
    # frontmatter 順序 + list 展開 + key remap + OS preamble を一括確認
    assert text.startswith("---\nname: run-x\ndescription: d\n")
    assert "allowed-tools:\n  - Read\n  - Bash\n" in text
    assert "argument-hint: <file>\n" in text
    assert MOD.OS_PREAMBLE in text
    # preamble は frontmatter 終端と body の間
    assert text.index("---\n\n") < text.index(MOD.OS_PREAMBLE) < text.index("B\n")


def test_main_output_eq_form_is_not_special(monkeypatch, capsys, tmp_path):
    # main は "--output" を index() で探すので "--output=foo" 形式は対象外。
    # その結果 output_path は None のまま stdout 出力になることを確認する
    # (手書き parse の実挙動を固定するための回帰テスト)。
    brief = _write_brief(tmp_path, {"name": "n", "body": "B"})
    rc = _run_main(monkeypatch, str(brief), "--output=" + str(tmp_path / "x.md"))
    out = capsys.readouterr().out
    assert rc == 0
    # "--output=..." は --output と一致しないので stdout に出る
    assert out.startswith("---\nname: n\n")
    assert not (tmp_path / "x.md").exists()


def test_main_empty_body_renders_frontmatter_only(monkeypatch, capsys, tmp_path):
    brief = _write_brief(tmp_path, {"name": "n", "description": "d"})
    rc = _run_main(monkeypatch, str(brief))
    out = capsys.readouterr().out
    assert rc == 0
    # body 無し -> 末尾 newline 追記分岐 (103-104) は body が空なので踏まない
    assert out == "---\nname: n\ndescription: d\n---\n\n"


def test_main_module_entrypoint_via_runpy(monkeypatch, tmp_path):
    # __main__ ガード (145-146 行) を runpy で踏ませる。引数なし -> exit 2。
    import runpy

    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert ei.value.code == 2
