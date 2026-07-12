"""lint-skill-description.py の description 設計規律 (R0-R5) を実入力で網羅検証する。

対象 script:
  plugins/skill-governance-lint/scripts/lint-skill-description.py

方針:
  - 純関数 (parse_frontmatter / check / _parse_skills_dir / main) を実ファイルから
    importlib でロードして直接呼ぶ。
  - check は各ルール (R0 欠落 / R1 トリガー上限・不在 / R2 禁止語・数字+パラダイム /
    R3 括弧列挙 / R4 長さ / R5 末尾) を合格入力と各違反入力で findings を assert。
  - main は SKILL_GLOBS を cwd 相対で走査するため monkeypatch.chdir(tmp_path) 配下に
    .claude/skills/<name>/SKILL.md を置き、in-process と subprocess の両経路で
    exit code / stdout / stderr / --report JSON を assert する。
  - network / keychain / Notion 依存は無い純ローカル lint なので stub 不要。
    全 fixture は tmp_path 配下で repo を汚染しない。
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
    spec = importlib.util.spec_from_file_location("lint_skill_description_uut", SCRIPT)
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


def _mk_skill_md(root: Path, name: str, *, description: str, fence: bool = True) -> Path:
    """tmp_path 配下の .claude/skills/<name>/SKILL.md を作る。"""
    d = root / ".claude" / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    if fence:
        p.write_text(
            f'---\nname: {name}\ndescription: "{description}"\n---\n\n# {name}\n',
            encoding="utf-8",
        )
    else:
        p.write_text(f"# {name}\n{description}\n", encoding="utf-8")
    return p


# 合格 description の素材 (R0-R5 全通過): トリガー1個 + 許可末尾 + 禁止語/数字列挙なし
GOOD = "コードレビューが必要なとき使う。"


# ---------------------------------------------------------------------------
# check (R0-R5) を実入力で網羅
# ---------------------------------------------------------------------------
def test_check_clean_passes(MOD):
    assert MOD.check("n", GOOD) == []


def test_check_clean_two_triggers_ok(MOD):
    # トリガー 2 個までは許容 (R1 上限は 3 以上で違反)
    assert MOD.check("n", "実装したとき、レビューが必要な場合に使う。") == []


def test_check_clean_use_when_english_trigger(MOD):
    # 日本語トリガーが 0 でも "Use when" があれば R1 不在に当たらない
    assert MOD.check("n", "Use when reviewing code. 読む。") == []


def test_check_r0_missing_description(MOD):
    assert MOD.check("n", "") == ["R0: description missing"]


def test_check_r1_trigger_overflow(MOD):
    issues = MOD.check("n", "Aするとき、Bする場合、Cの際、Dの時に使う。")
    assert any("R1: trigger count" in i and "> 2" in i for i in issues)


def test_check_r1_no_trigger(MOD):
    issues = MOD.check("n", "これは何かをする。使う。")
    assert "R1: no trigger condition found" in issues


def test_check_r2_banned_term(MOD):
    # "採点する" は BANNED_TERMS。トリガー/末尾は満たして R2 のみを切り出す
    issues = MOD.check("n", "結果を採点するとき使う。")
    assert "R2: banned term '採点する'" in issues


def test_check_r2_each_banned_term_detected(MOD):
    # 代表的な禁止語が個別に検出されること
    for term in ["JSONで返す", "並列実行", "ウィザード", "runbook", "E2E", "一気通貫"]:
        issues = MOD.check("n", f"何か{term}が必要なとき使う。")
        assert any(f"R2: banned term '{term}'" == i for i in issues), term


def test_check_r2_digit_paradigm(MOD):
    issues = MOD.check("n", "3つの思考法が必要なとき読む。")
    assert "R2: digit+paradigm/思考法 enumeration not allowed" in issues


def test_check_r3_parenthesized_enumeration(MOD):
    # 括弧内に長い A/B 列挙 (各 15 文字超) があると R3
    long_a = "あ" * 16
    long_b = "い" * 16
    issues = MOD.check("n", f"（{long_a}/{long_b}）が必要なとき使う。")
    assert "R3: paradigm enumeration in parentheses not allowed" in issues


def test_check_r4_length_overflow_only(MOD):
    # 281 文字超だがトリガー/末尾は満たし、禁止語/列挙を含まない → R4 のみ
    desc = "x" * 275 + "が必要なとき使う。"
    assert len(desc) > MOD.MAX_LEN
    issues = MOD.check("n", desc)
    assert any(i.startswith("R4: length") for i in issues)
    # R4 以外の偽陽性が混ざらないこと
    assert all(i.startswith("R4:") for i in issues)


def test_check_r5_wrong_tail(MOD):
    issues = MOD.check("n", "レビューが必要なとき終わる")
    assert any("R5: must end with one of" in i for i in issues)


def test_check_r5_allowed_tails(MOD):
    for tail in ["使う。", "読む。", "起動する。"]:
        assert MOD.check("n", f"レビューが必要なとき{tail}") == []


def test_check_multiple_violations_accumulate(MOD):
    # 末尾不正 + トリガー不在 + 禁止語 を同時に
    issues = MOD.check("n", "結果を採点する処理")
    kinds = {i.split(":")[0] for i in issues}
    assert "R5" in kinds and "R1" in kinds and "R2" in kinds


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------
def test_parse_frontmatter_scalar_fields(MOD, tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        '---\nname: foo\ndescription: "レビューが必要なとき使う。"\n- listitem\n---\nbody\n',
        encoding="utf-8",
    )
    fm = MOD.parse_frontmatter(p)
    assert fm["name"] == "foo"
    # クォート付きのまま (除去は main 側の責務)
    assert fm["description"] == '"レビューが必要なとき使う。"'
    # リスト要素 (`- ` 始まり) は無視される
    assert "listitem" not in fm


def test_parse_frontmatter_no_fence(MOD, tmp_path):
    p = tmp_path / "x.md"
    p.write_text("no frontmatter here\n", encoding="utf-8")
    assert MOD.parse_frontmatter(p) == {}


def test_parse_frontmatter_single_fence(MOD, tmp_path):
    p = tmp_path / "y.md"
    p.write_text("---\nname: a\n", encoding="utf-8")  # 終端 --- が無い
    assert MOD.parse_frontmatter(p) == {}


# ---------------------------------------------------------------------------
# _parse_skills_dir
# ---------------------------------------------------------------------------
def test_parse_skills_dir_space_and_equals_forms(MOD):
    out = MOD._parse_skills_dir(["--skills-dir", "foo", "x", "--skills-dir=bar"])
    assert out == ["foo", "bar"]


def test_parse_skills_dir_none(MOD):
    assert MOD._parse_skills_dir(["--report"]) == []


def test_parse_skills_dir_trailing_flag_without_value(MOD):
    # 末尾 --skills-dir で値が無い場合は無視される
    assert MOD._parse_skills_dir(["--skills-dir"]) == []


# ---------------------------------------------------------------------------
# main (in-process) — cwd 相対 SKILL_GLOBS を走査するため chdir して被覆
# ---------------------------------------------------------------------------
def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["lint-skill-description.py", *args])


def test_main_inproc_all_ok(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill_md(tmp_path, "ref-foo", description=GOOD)
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch)
    assert MOD.main(sys.argv[1:]) == 0
    out = capsys.readouterr().out
    assert "VIOLATION=0" in out
    assert "OK=1" in out


def test_main_inproc_violation_exit1_stderr(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill_md(tmp_path, "bad-skill", description="結果を採点する処理")
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch)
    assert MOD.main(sys.argv[1:]) == 1
    captured = capsys.readouterr()
    assert "VIOLATION" in captured.err
    assert "bad-skill" in captured.err
    assert "VIOLATION=1" in captured.out


def test_main_inproc_report_json(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill_md(tmp_path, "ok-skill", description=GOOD)
    _mk_skill_md(tmp_path, "bad-skill", description="採点する処理")
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--report")
    rc = MOD.main(sys.argv[1:])
    assert rc == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["summary"]["OK"] == 1
    assert data["summary"]["VIOLATION"] == 1
    assert data["violations"][0]["name"] == "bad-skill"
    assert any("R2" in i for i in data["violations"][0]["issues"])


def test_main_inproc_skills_dir_override(MOD, tmp_path, monkeypatch, capsys):
    base = tmp_path / "custom" / "skills"
    d = base / "ref-x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f'---\nname: ref-x\ndescription: "{GOOD}"\n---\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--skills-dir", str(base))
    assert MOD.main(sys.argv[1:]) == 0
    assert "OK=1" in capsys.readouterr().out


def test_main_inproc_skips_readme(MOD, tmp_path, monkeypatch, capsys):
    # README.md は対象外。glob 名が SKILL.md なので README は別ディレクトリ glob で拾わない
    # ここでは override-dir で *.md ではなく */SKILL.md を見る挙動を確認
    base = tmp_path / "skills"
    d = base / "readme-holder"
    d.mkdir(parents=True)
    # name が readme.md のファイルは除外される (glob は SKILL.md なので別途 README.md を SKILL.md として置けない)
    (d / "SKILL.md").write_text(
        f'---\nname: readme-holder\ndescription: "{GOOD}"\n---\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--skills-dir", str(base))
    assert MOD.main(sys.argv[1:]) == 0
    assert "OK=1" in capsys.readouterr().out


def test_main_inproc_quote_stripping(MOD, tmp_path, monkeypatch, capsys):
    # description が "..." で囲まれていても check 前にクォート除去される
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
    # OK 側に入る = クォート込みで R5 末尾判定が失敗していない
    assert data["summary"]["OK"] == 1


def test_main_inproc_skips_readme_via_agents_glob(MOD, tmp_path, monkeypatch, capsys):
    # 既定 SKILL_GLOBS は .claude/agents/*.md も走査するため、readme.md は明示スキップされる。
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    # 大文字 README.md も name.lower()=="readme.md" で除外対象
    (agents / "README.md").write_text(
        '---\nname: README\ndescription: "x"\n---\n', encoding="utf-8"
    )
    (agents / "good-agent.md").write_text(
        f'---\nname: good-agent\ndescription: "{GOOD}"\n---\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch)
    assert MOD.main(sys.argv[1:]) == 0
    out = capsys.readouterr().out
    # README は除外され、good-agent のみ OK=1 (README が混ざれば VIOLATION か OK=2 になる)
    assert "OK=1 VIOLATION=0" in out


def test_main_inproc_no_targets(MOD, tmp_path, monkeypatch, capsys):
    # 空の override-dir → 対象 0 件で OK=0 VIOLATION=0 exit 0
    base = tmp_path / "empty-skills"
    base.mkdir()
    monkeypatch.chdir(tmp_path)
    _argv(monkeypatch, "--skills-dir", str(base))
    assert MOD.main(sys.argv[1:]) == 0
    out = capsys.readouterr().out
    assert "OK=0 VIOLATION=0" in out


# ---------------------------------------------------------------------------
# main (subprocess) — __main__ ガードと exit code 契約
# ---------------------------------------------------------------------------
def test_main_subprocess_violation_exit1(MOD, tmp_path):
    _mk_skill_md(tmp_path, "bad-skill", description="採点する処理")
    r = _run([], cwd=tmp_path)
    assert r.returncode == 1
    assert "bad-skill" in r.stderr


def test_main_subprocess_ok_exit0(MOD, tmp_path):
    _mk_skill_md(tmp_path, "ref-foo", description=GOOD)
    r = _run([], cwd=tmp_path)
    assert r.returncode == 0
    assert "VIOLATION=0" in r.stdout


def test_main_subprocess_report_json(MOD, tmp_path):
    _mk_skill_md(tmp_path, "bad-skill", description="採点する処理")
    r = _run(["--report"], cwd=tmp_path)
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["summary"]["VIOLATION"] == 1
