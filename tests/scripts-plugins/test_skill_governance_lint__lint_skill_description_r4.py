"""lint-skill-description.py の description 設計規律 (R0-R5) を独立に網羅検証する (scripts4 系列)。

対象 script:
  plugins/skill-governance-lint/scripts/lint-skill-description.py

このスイートは tests/scripts3 の同名テストとは独立に、各純関数 (parse_frontmatter /
check / _parse_skills_dir / main) の分岐をゼロから genuine に被覆する。
  - check: R0 欠落 / R1 トリガー上限(>2)・不在(0)・境界(==2 許容) / R2 禁止語全種・
    数字+パラダイム / R3 括弧列挙(境界含む) / R4 長さ(境界含む) / R5 末尾全種・不正
  - parse_frontmatter: fence あり/無し/未終端 / `- ` 行無視 / コロン無し行無視
  - _parse_skills_dir: space 形式 / =形式 / 複数 / 末尾値欠落 / 非該当
  - main: in-process(monkeypatch.chdir)/ subprocess 双方で OK / VIOLATION / --report /
    --skills-dir override / readme.md スキップ / クォート除去 / 対象 0 件 / 既定 glob
純ローカル lint (network=false, write-scope=none) のため stub 不要。全 fixture は tmp_path。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-skill-description.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_skill_description_r4_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def _mk_skill_md(root: Path, name: str, description: str, *, quoted: bool = False) -> Path:
    d = root / ".claude" / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    val = f'"{description}"' if quoted else description
    p.write_text(f"---\nname: {name}\ndescription: {val}\n---\n\n# {name}\n", encoding="utf-8")
    return p


# 全 R0-R5 を通過する基準 description: トリガー 1 個 + 許可末尾 + 禁止語/列挙なし + 短い
GOOD = "コードレビューが必要なとき使う。"


# ---------------------------------------------------------------------------
# check (R0-R5)
# ---------------------------------------------------------------------------
def test_check_good_is_clean(MOD):
    assert MOD.check("n", GOOD) == []


def test_check_two_triggers_is_boundary_ok(MOD):
    # 「とき」「場合」の 2 トリガーは許容 (上限は 3 以上で違反)
    assert MOD.check("n", "実装したとき、レビューが必要な場合に使う。") == []


def test_check_r0_empty(MOD):
    assert MOD.check("n", "") == ["R0: description missing"]


def test_check_r1_overflow_reports_count(MOD):
    issues = MOD.check("n", "Aするとき、Bする場合、Cの際に使う。")
    assert any(i == "R1: trigger count 3 > 2 (overflow)" for i in issues)


def test_check_r1_no_trigger_without_use_when(MOD):
    # 日本語トリガー 0 かつ "Use when" 無し → R1 不在
    issues = MOD.check("n", "差分の正しさを確認するために読む。")
    assert "R1: no trigger condition found" in issues


def test_check_use_when_satisfies_trigger(MOD):
    # 「とき/場合/際/時に」が無くても "Use when" があれば R1 不在に当たらない
    issues = MOD.check("n", "Use when reviewing code changes. 読む。")
    assert not any("R1: no trigger" in i for i in issues)


def test_check_r2_all_banned_terms_individually(MOD):
    # BANNED_TERMS の各語が個別に検出される (語ごとに 1 ケースで genuine 被覆)
    for term in MOD.BANNED_TERMS:
        # 末尾とトリガーを満たしつつ禁止語を埋め込む
        desc = f"何か{term}が要るとき使う。"
        issues = MOD.check("n", desc)
        assert any(i == f"R2: banned term '{term}'" for i in issues), term


def test_check_r2_digit_paradigm(MOD):
    issues = MOD.check("n", "3つの思考法を使うとき読む。")
    assert "R2: digit+paradigm/思考法 enumeration not allowed" in issues


def test_check_r3_parenthetical_enumeration(MOD):
    long_a = "あ" * 16
    long_b = "い" * 16
    issues = MOD.check("n", f"何かするとき（{long_a}/{long_b}）に使う。")
    assert "R3: paradigm enumeration in parentheses not allowed" in issues


def test_check_r3_short_parenthetical_not_flagged(MOD):
    # 括弧内が短い (15 字未満) ときは R3 に当たらない
    issues = MOD.check("n", "何かするとき（短い/列挙）に使う。")
    assert not any("R3" in i for i in issues)


def test_check_r4_length_boundary(MOD):
    # MAX_LEN ちょうどは合格、超過で R4。末尾/トリガーは満たす
    tail = "が要るとき使う。"
    body_len = MOD.MAX_LEN - len(tail)
    exact = "x" * body_len + tail
    assert len(exact) == MOD.MAX_LEN
    assert not any(i.startswith("R4") for i in MOD.check("n", exact))
    over = "x" * (body_len + 1) + tail
    issues = MOD.check("n", over)
    assert any(i == f"R4: length {len(over)} > {MOD.MAX_LEN}" for i in issues)


def test_check_r5_each_allowed_tail(MOD):
    for tail in MOD.ALLOWED_TAIL:
        assert MOD.check("n", f"レビューが必要なとき{tail}") == []


def test_check_r5_wrong_tail(MOD):
    issues = MOD.check("n", "レビューが必要なとき確認する。")
    assert any(i.startswith("R5: must end with one of") for i in issues)


def test_check_r5_trailing_whitespace_is_rstripped(MOD):
    # 末尾の空白は rstrip されて判定される
    assert MOD.check("n", "レビューが必要なとき使う。   ") == []


def test_check_multiple_violations_accumulate(MOD):
    # R1 不在 + R2 禁止語 + R5 末尾不正 を同時に出す
    issues = MOD.check("n", "結果を採点する処理")
    kinds = {i.split(":")[0] for i in issues}
    assert {"R1", "R2", "R5"} <= kinds


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------
def test_parse_frontmatter_fields_and_listline_ignored(MOD, tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: foo\n"
        f"description: {GOOD}\n"
        "kind: workflow\n"
        "  - listitem\n"      # `- ` 始まり (インデント含む) は無視
        "noколон_line\n"       # コロン無し行は無視
        "---\n# body\n",
        encoding="utf-8",
    )
    fm = MOD.parse_frontmatter(p)
    assert fm["name"] == "foo"
    assert fm["description"] == GOOD
    assert fm["kind"] == "workflow"
    assert "listitem" not in fm


def test_parse_frontmatter_no_fence(MOD, tmp_path):
    p = tmp_path / "x.md"
    p.write_text("# heading\nbody\n", encoding="utf-8")
    assert MOD.parse_frontmatter(p) == {}


def test_parse_frontmatter_unterminated(MOD, tmp_path):
    # 開始 --- はあるが閉じ --- が無い → split で parts<3 → {}
    p = tmp_path / "y.md"
    p.write_text("---\nname: a\ndescription: b\n", encoding="utf-8")
    assert MOD.parse_frontmatter(p) == {}


# ---------------------------------------------------------------------------
# _parse_skills_dir
# ---------------------------------------------------------------------------
def test_parse_skills_dir_space_form(MOD):
    assert MOD._parse_skills_dir(["--skills-dir", "a/b"]) == ["a/b"]


def test_parse_skills_dir_equals_form(MOD):
    assert MOD._parse_skills_dir(["--skills-dir=c/d"]) == ["c/d"]


def test_parse_skills_dir_multiple_mixed(MOD):
    assert MOD._parse_skills_dir(
        ["--skills-dir", "x", "noise", "--skills-dir=y"]
    ) == ["x", "y"]


def test_parse_skills_dir_trailing_flag_without_value(MOD):
    assert MOD._parse_skills_dir(["--skills-dir"]) == []


def test_parse_skills_dir_none(MOD):
    assert MOD._parse_skills_dir(["--report"]) == []


# ---------------------------------------------------------------------------
# main (in-process)
# ---------------------------------------------------------------------------
def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["lint-skill-description.py", *args])


def test_main_inproc_default_glob_ok(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill_md(tmp_path, "ref-foo", GOOD)
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch)
    assert MOD.main(sys.argv[1:]) == 0
    out = capsys.readouterr().out
    assert "OK=1 VIOLATION=0" in out


def test_main_inproc_violation_exit1(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill_md(tmp_path, "bad-skill", "結果を採点する処理")
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch)
    assert MOD.main(sys.argv[1:]) == 1
    cap = capsys.readouterr()
    assert "VIOLATION" in cap.err
    assert "bad-skill" in cap.err
    assert "VIOLATION=1" in cap.out


def test_main_inproc_report_json(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill_md(tmp_path, "ok-skill", GOOD)
    _mk_skill_md(tmp_path, "bad-skill", "採点する処理")
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--report")
    assert MOD.main(sys.argv[1:]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["OK"] == 1
    assert data["summary"]["VIOLATION"] == 1
    assert data["violations"][0]["name"] == "bad-skill"


def test_main_inproc_skills_dir_override(MOD, tmp_path, monkeypatch, capsys):
    base = tmp_path / "custom" / "skills"
    d = base / "ref-x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: ref-x\ndescription: {GOOD}\n---\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--skills-dir", str(base))
    assert MOD.main(sys.argv[1:]) == 0
    assert "OK=1" in capsys.readouterr().out


def test_main_inproc_quote_stripping(MOD, tmp_path, monkeypatch, capsys):
    # description が "..." で囲まれても中身でルール判定される
    base = tmp_path / "skills"
    d = base / "ref-q"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f'---\nname: ref-q\ndescription: "{GOOD}"\n---\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--report", "--skills-dir", str(base))
    MOD.main(sys.argv[1:])
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["OK"] == 1


def test_main_inproc_skips_readme_via_agents_glob(MOD, tmp_path, monkeypatch, capsys):
    # 既定 SKILL_GLOBS は .claude/agents/*.md を走査。readme.md は明示スキップ。
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "README.md").write_text(
        "---\nname: README\ndescription: 採点する。\n---\n", encoding="utf-8"
    )
    (agents / "good-agent.md").write_text(
        f"---\nname: good-agent\ndescription: {GOOD}\n---\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch)
    assert MOD.main(sys.argv[1:]) == 0
    assert "OK=1 VIOLATION=0" in capsys.readouterr().out


def test_main_inproc_empty_dir_no_targets(MOD, tmp_path, monkeypatch, capsys):
    base = tmp_path / "empty"
    base.mkdir()
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--skills-dir", str(base))
    assert MOD.main(sys.argv[1:]) == 0
    assert "OK=0 VIOLATION=0" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main (subprocess) — __main__ ガード + exit code 契約
# ---------------------------------------------------------------------------
def test_main_subprocess_ok(MOD, tmp_path):
    _mk_skill_md(tmp_path, "ref-foo", GOOD)
    r = _run([], cwd=tmp_path)
    assert r.returncode == 0
    assert "VIOLATION=0" in r.stdout


def test_main_subprocess_violation(MOD, tmp_path):
    _mk_skill_md(tmp_path, "bad-skill", "採点する処理")
    r = _run([], cwd=tmp_path)
    assert r.returncode == 1
    assert "bad-skill" in r.stderr


def test_main_subprocess_report(MOD, tmp_path):
    _mk_skill_md(tmp_path, "bad-skill", "採点する処理")
    r = _run(["--report"], cwd=tmp_path)
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["summary"]["VIOLATION"] == 1
