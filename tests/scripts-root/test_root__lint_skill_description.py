"""lint-skill-description.py の description 規律 (R0-R5) を実入力で検証する。

このスクリプトは SKILL.md / agents/*.md の description を 5 ルールで機械強制する:
  R1 トリガー句は 2 個まで (3 個以上で違反、0 個で「trigger なし」)
  R2 禁止語 (「採点する」「JSONで返す」等) を含まない
  R3 括弧内のパラダイム列挙禁止
  R4 280 字以内
  R5 末尾は「使う。/読む。/起動する。」のいずれか
本テストは check() を多様な desc で呼び該当 issue が出る/出ないことを assert し、
parse_frontmatter / _parse_skills_dir を実入力で検証、main を subprocess で
--skills-dir 経由の OK/違反/--report 経路について exit code と出力を検証する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-skill-description.py"
SPEC = importlib.util.spec_from_file_location("lint_skill_description", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- check(): 各ルールの発火 ---

def test_check_valid_description_has_no_issues():
    desc = "コードを変更したとき、差分の正しさを確認するために使う。"
    assert MOD.check("x", desc) == []


def test_check_missing_description_returns_r0():
    assert MOD.check("x", "") == ["R0: description missing"]


def test_check_too_long_triggers_r4():
    # 末尾とトリガーは合わせて R4 のみが残るように作る
    long_desc = "あ" * 290 + "とき使う。"
    issues = MOD.check("x", long_desc)
    assert any(i.startswith("R4: length") for i in issues)


def test_check_wrong_tail_triggers_r5():
    desc = "コードを変更したときに確認する。"  # 末尾が「確認する。」
    issues = MOD.check("x", desc)
    assert any(i.startswith("R5:") for i in issues)


def test_check_too_many_triggers_r1_overflow():
    # 「とき」「場合」「際」の 3 トリガー -> R1 overflow
    desc = "変更したとき、リリースする場合、レビューの際に読む。"
    issues = MOD.check("x", desc)
    assert any("R1: trigger count 3" in i for i in issues)


def test_check_no_trigger_triggers_r1_missing():
    desc = "差分の正しさを確認するために読む。"  # トリガー句なし & "Use when" なし
    issues = MOD.check("x", desc)
    assert any("R1: no trigger condition" in i for i in issues)


def test_check_use_when_satisfies_trigger_requirement():
    desc = "Use when reviewing diffs to verify correctness. 読む。"
    issues = MOD.check("x", desc)
    # Use when があるので R1 missing は出ない
    assert not any("R1: no trigger" in i for i in issues)


def test_check_banned_term_triggers_r2():
    desc = "差分を採点するときに使う。"  # 「採点する」は禁止語
    issues = MOD.check("x", desc)
    assert any("R2: banned term '採点する'" in i for i in issues)


def test_check_digit_paradigm_triggers_r2():
    desc = "3つの思考法を適用するときに使う。"  # 数字+思考法
    issues = MOD.check("x", desc)
    assert any("R2: digit+paradigm" in i for i in issues)


def test_check_parenthetical_enumeration_triggers_r3():
    # 括弧内に 15 字以上 / 15 字以上 の列挙
    inner = "あ" * 16 + "/" + "い" * 16
    desc = f"何かをするとき（{inner}）に使う。"
    issues = MOD.check("x", desc)
    assert any("R3:" in i for i in issues)


# --- parse_frontmatter() ---

def test_parse_frontmatter_extracts_fields(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: run-x\n"
        "description: 何かするとき使う。\n"
        "kind: workflow\n"
        "- not_a_field: ignored\n"  # ハイフン始まりは無視される
        "---\n"
        "# body\n",
        encoding="utf-8",
    )
    fm = MOD.parse_frontmatter(p)
    assert fm["name"] == "run-x"
    assert fm["description"] == "何かするとき使う。"
    assert fm["kind"] == "workflow"
    assert "not_a_field" not in fm


def test_parse_frontmatter_no_frontmatter_returns_empty(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("# just a heading\nno frontmatter here\n", encoding="utf-8")
    assert MOD.parse_frontmatter(p) == {}


def test_parse_frontmatter_unterminated_returns_empty(tmp_path):
    # 開始 --- はあるが閉じ --- が無い -> parts < 3 -> {}
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: run-x\ndescription: 何かするとき使う。\n", encoding="utf-8")
    assert MOD.parse_frontmatter(p) == {}


# --- _parse_skills_dir() ---

def test_parse_skills_dir_space_form():
    assert MOD._parse_skills_dir(["--skills-dir", "a/b"]) == ["a/b"]


def test_parse_skills_dir_equals_form():
    assert MOD._parse_skills_dir(["--skills-dir=c/d"]) == ["c/d"]


def test_parse_skills_dir_multiple_and_empty():
    assert MOD._parse_skills_dir(["--skills-dir", "x", "--skills-dir=y"]) == ["x", "y"]
    assert MOD._parse_skills_dir(["--report"]) == []


# --- main(): subprocess で OK/違反/report 経路 ---

def _mk_skill(root: Path, name: str, desc: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n# body\n",
        encoding="utf-8",
    )


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_main_help_returns_0():
    # argparse を使わない手書き parse なので --help は通常引数扱い。
    # 代わりに存在しない skills-dir を渡すと OK (対象 0 件) になることを確認。
    proc = _run(["--skills-dir", "/no/such/dir"])
    assert proc.returncode == 0
    assert "VIOLATION=0" in proc.stdout


def test_main_ok_when_all_valid(tmp_path):
    _mk_skill(tmp_path, "run-good", "コードを変更したとき確認のために使う。")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 0
    assert "OK=1 VIOLATION=0" in proc.stdout


def test_main_violation_returns_1(tmp_path):
    _mk_skill(tmp_path, "run-bad", "差分を採点するときに確認する。")  # R2 + R5
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 1
    assert "VIOLATION" in proc.stderr
    assert "run-bad" in proc.stderr


def test_main_report_mode_emits_json(tmp_path):
    _mk_skill(tmp_path, "run-bad", "差分を採点するときに確認する。")
    _mk_skill(tmp_path, "run-good", "コードを変更したとき確認のために使う。")
    proc = _run(["--skills-dir", str(tmp_path), "--report"])
    # report モードでも違反があれば exit 1
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["summary"]["OK"] == 1
    assert data["summary"]["VIOLATION"] == 1
    assert data["violations"][0]["name"] == "run-bad"


def test_main_skips_readme_via_agents_glob(tmp_path):
    # 既定 glob `.claude/agents/*.md` は readme.md を拾うが、
    # main は p.name.lower()=="readme.md" をスキップする (135 行)。
    # 不正な description の readme.md を置いても VIOLATION にならないことで確認。
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "readme.md").write_text(
        "---\nname: README\ndescription: 差分を採点する。\n---\n",  # 本来 R2 違反
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    # readme.md はスキップされるので違反 0 件 -> exit 0
    assert proc.returncode == 0
    assert "OK=0 VIOLATION=0" in proc.stdout


def test_main_default_globs_in_empty_cwd(tmp_path):
    # --skills-dir 無指定 -> 既定 SKILL_GLOBS 分岐 (130-131)。
    # 空の tmp_path を cwd にして実行すると対象 0 件で OK 終了する。
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0
    assert "OK=0 VIOLATION=0" in proc.stdout


def test_main_strips_quoted_description(tmp_path):
    # description がクオート付きでも中身で判定する
    d = tmp_path / "run-q"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        '---\nname: run-q\ndescription: "コードを変更したとき確認のために使う。"\n---\n# body\n',
        encoding="utf-8",
    )
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 0
    assert "OK=1" in proc.stdout
