"""scripts/lint-skill-description.py の main() を in-process で網羅する補完テスト。

既存 tests/scripts-root/test_root__lint_skill_description.py は check() /
parse_frontmatter() / _parse_skills_dir() を in-process で、main() を subprocess
で検証している。subprocess 経由の main() は --cov=scripts に計上されないため、
本ファイルは main(argv) を **直接呼び** stdout/stderr/exit code を assert し、
main() 内の各分岐 (--report / VIOLATION 表示 / OK 集計 / 既定 glob / readme スキップ /
クオート剥がし / override_dirs ループ) を行カバレッジ込みで網羅する。

R0-R5 の判定 (check) は既存テストが担うが、main 経由でも代表的な違反種別が
正しく集計・表示されることを end-to-end で確認する。すべて network/外部 I/O なし、
書き込みは tmp_path 配下のみ。
"""
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-skill-description.py"

SPEC = importlib.util.spec_from_file_location("lint_skill_description_s2", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

def _mk_skill(root: Path, name: str, desc: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n# body\n",
        encoding="utf-8",
    )


VALID = "コードを変更したとき確認のために使う。"
BANNED = "差分を採点するときに確認する。"  # R2 (採点する) + R5 (末尾不正)


# --- check(): main を経由しない純関数の各ルール分岐 (この補完ファイルを自己完結化) ---

def test_check_valid_returns_empty():
    assert MOD.check("x", VALID) == []


def test_check_missing_description_returns_r0():
    assert MOD.check("x", "") == ["R0: description missing"]


def test_check_too_long_triggers_r4():
    issues = MOD.check("x", "あ" * 290 + "とき使う。")  # 290+ 文字
    assert any(i.startswith("R4: length") and "> 280" in i for i in issues)


def test_check_wrong_tail_triggers_r5():
    issues = MOD.check("x", "コードを変更したときに確認する。")  # 末尾「確認する。」
    assert any(i.startswith("R5:") for i in issues)


def test_check_overflow_triggers_r1():
    # とき/場合/際 の 3 トリガー -> count 3 > 2
    issues = MOD.check("x", "変更したとき、リリースする場合、レビューの際に読む。")
    assert any("R1: trigger count 3 > 2" in i for i in issues)


def test_check_no_trigger_triggers_r1_missing():
    issues = MOD.check("x", "差分の正しさを確認するために読む。")
    assert any("R1: no trigger condition" in i for i in issues)


def test_check_use_when_satisfies_trigger():
    issues = MOD.check("x", "Use when reviewing diffs to verify. 読む。")
    assert not any("R1: no trigger" in i for i in issues)


def test_check_digit_paradigm_triggers_r2():
    issues = MOD.check("x", "3つの思考法を適用するときに使う。")
    assert any("R2: digit+paradigm" in i for i in issues)


def test_check_parenthetical_enumeration_triggers_r3():
    inner = "あ" * 16 + "/" + "い" * 16  # 各 15 字超 + / 区切り
    issues = MOD.check("x", f"何かをするとき（{inner}）に使う。")
    assert any(i.startswith("R3:") for i in issues)


# --- parse_frontmatter(): frontmatter 欠落/未終端のエッジ ---

def test_parse_frontmatter_no_marker_returns_empty(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("# heading only\nno frontmatter\n", encoding="utf-8")
    assert MOD.parse_frontmatter(p) == {}


def test_parse_frontmatter_unterminated_returns_empty(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: run-x\ndescription: 何かするとき使う。\n", encoding="utf-8")
    assert MOD.parse_frontmatter(p) == {}


# --- main(): --skills-dir 経由で OK / VIOLATION / report 集計を in-process 検証 ---

def test_main_ok_all_valid_returns_0(tmp_path, capsys):
    _mk_skill(tmp_path, "run-a", VALID)
    _mk_skill(tmp_path, "run-b", VALID)
    rc = MOD.main(["--skills-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK=2 VIOLATION=0" in out


def test_main_violation_returns_1_and_prints_issues(tmp_path, capsys):
    _mk_skill(tmp_path, "run-bad", BANNED)
    rc = MOD.main(["--skills-dir", str(tmp_path)])
    cap = capsys.readouterr()
    assert rc == 1
    # 違反は stderr に path + name + 各 issue で出る
    assert "VIOLATION" in cap.err
    assert "run-bad" in cap.err
    assert "R2: banned term '採点する'" in cap.err
    assert "R5:" in cap.err
    # stdout は集計のみ
    assert "OK=0 VIOLATION=1" in cap.out


def test_main_report_mode_emits_json_summary(tmp_path, capsys):
    _mk_skill(tmp_path, "run-bad", BANNED)
    _mk_skill(tmp_path, "run-good", VALID)
    rc = MOD.main(["--skills-dir", str(tmp_path), "--report"])
    out = capsys.readouterr().out
    assert rc == 1  # 違反があるので report でも 1
    data = json.loads(out)
    assert data["summary"]["OK"] == 1
    assert data["summary"]["VIOLATION"] == 1
    names = {v["name"] for v in data["violations"]}
    assert names == {"run-bad"}
    # 違反 entry は issues を含む
    assert any(i.startswith("R2:") for i in data["violations"][0]["issues"])


def test_main_report_mode_all_ok_returns_0(tmp_path, capsys):
    _mk_skill(tmp_path, "run-good", VALID)
    rc = MOD.main(["--skills-dir", str(tmp_path), "--report"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["summary"]["OK"] == 1
    assert data["summary"]["VIOLATION"] == 0
    assert data["violations"] == []


def test_main_strips_quoted_description_in_process(tmp_path, capsys):
    # description がダブルクオート付きでも中身で判定する (139-140 行)
    d = tmp_path / "run-q"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f'---\nname: run-q\ndescription: "{VALID}"\n---\n# body\n',
        encoding="utf-8",
    )
    rc = MOD.main(["--skills-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK=1 VIOLATION=0" in out


def test_main_uses_name_fallback_to_stem_when_no_name(tmp_path, capsys):
    # frontmatter に name が無いと p.stem が name に使われる (137 行)
    d = tmp_path / "run-stem"
    d.mkdir(parents=True)
    # SKILL.md の stem は "SKILL" になるが、違反時の表示で stem が出ることを確認
    (d / "SKILL.md").write_text(
        f"---\ndescription: {BANNED}\n---\n# body\n",
        encoding="utf-8",
    )
    rc = MOD.main(["--skills-dir", str(tmp_path), "--report"])
    out = capsys.readouterr().out
    assert rc == 1
    data = json.loads(out)
    assert data["violations"][0]["name"] == "SKILL"


def test_main_multiple_override_dirs_are_unioned(tmp_path, capsys):
    # --skills-dir を 2 回渡すと両方の SKILL.md が対象になる (125-128 行)
    a = tmp_path / "dirA"
    b = tmp_path / "dirB"
    _mk_skill(a, "run-a", VALID)
    _mk_skill(b, "run-b", BANNED)
    rc = MOD.main(["--skills-dir", str(a), "--skills-dir=" + str(b)])
    cap = capsys.readouterr()
    assert rc == 1
    assert "OK=1 VIOLATION=1" in cap.out
    assert "run-b" in cap.err


def test_main_default_globs_branch_empty_cwd(tmp_path, monkeypatch, capsys):
    # override_dirs 無し -> 既定 SKILL_GLOBS 分岐 (130-131 行)。
    # 空ディレクトリを cwd にして 0 件 OK を確認。
    monkeypatch.chdir(tmp_path)
    rc = MOD.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK=0 VIOLATION=0" in out


def test_main_default_globs_picks_up_plugin_skill(tmp_path, monkeypatch, capsys):
    # 既定 glob plugins/harness-creator/skills/*/SKILL.md に違反 skill を置くと拾う。
    skills = tmp_path / "plugins" / "harness-creator" / "skills"
    _mk_skill(skills, "run-bad", BANNED)
    monkeypatch.chdir(tmp_path)
    rc = MOD.main([])
    cap = capsys.readouterr()
    assert rc == 1
    assert "VIOLATION=1" in cap.out
    assert "run-bad" in cap.err


def test_main_skips_readme_md(tmp_path, monkeypatch, capsys):
    # .claude/agents/*.md glob は readme.md を拾うが main はスキップする (134 行)。
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "readme.md").write_text(
        f"---\nname: README\ndescription: {BANNED}\n---\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = MOD.main([])
    out = capsys.readouterr().out
    assert rc == 0  # readme はスキップ -> 違反 0
    assert "OK=0 VIOLATION=0" in out


def test_main_module_entrypoint_executes(tmp_path, monkeypatch):
    # __main__ ガード (158-159 行) を runpy で踏ませて exit code を確認する。
    import runpy
    import sys

    monkeypatch.chdir(tmp_path)  # 空 cwd -> exit 0
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert ei.value.code == 0
