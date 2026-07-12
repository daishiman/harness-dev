"""Genuine functional tests for plugins/skill-governance-lint/scripts/lint-skill-tree.py.

純関数 (_parse_fm_simple / _needs_os_preamble / _body_line_count /
check_prompts_listed / check_os_preamble / lint_one) を実 fixture で呼び
実出力を assert する。main は subprocess で単一ディレクトリ / --skills-dir /
不正引数 を与え returncode + stdout/stderr を assert する。

副作用なし: 全 fixture は tmp_path に構築し repo を汚さない。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-skill-tree.py"

_SPEC = importlib.util.spec_from_file_location("lint_skill_tree", SCRIPT)
LST = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LST)


def _make_skill(tmp_path, name="run-foo", body_lines=10, fm=None):
    d = tmp_path / name
    d.mkdir()
    fm = fm or "name: run-foo\nkind: run\n"
    body = "\n".join(f"line {i}" for i in range(body_lines))
    (d / "SKILL.md").write_text(f"---\n{fm}---\n{body}\n", encoding="utf-8")
    return d


# ---------- _parse_fm_simple ----------

def test_parse_fm_simple_scalar():
    text = "---\nname: foo\nkind: run\n---\nbody\n"
    fm = LST._parse_fm_simple(text)
    assert fm["name"] == "foo"
    assert fm["kind"] == "run"


def test_parse_fm_simple_list():
    text = "---\nname: foo\nresponsibility_refs:\n  - prompts/a.md\n  - prompts/b.md\n---\nbody\n"
    fm = LST._parse_fm_simple(text)
    assert fm["responsibility_refs"] == ["prompts/a.md", "prompts/b.md"]


def test_parse_fm_simple_no_frontmatter():
    assert LST._parse_fm_simple("just body, no fm") == {}


# ---------- _needs_os_preamble ----------

def test_needs_os_preamble_cross_platform_true():
    assert LST._needs_os_preamble({"cross_platform": "true"}) is True


def test_needs_os_preamble_bool_true():
    assert LST._needs_os_preamble({"os_preamble_required": True}) is True


def test_needs_os_preamble_via_allowed_tools_list():
    assert LST._needs_os_preamble({"allowed-tools": ["Bash(uname -s)"]}) is True


def test_needs_os_preamble_false_default():
    assert LST._needs_os_preamble({"name": "x"}) is False


# ---------- _body_line_count ----------

def test_body_line_count_excludes_frontmatter():
    fm = "---\n" + "\n".join(f"k{i}: v" for i in range(30)) + "\n---\n"
    body = "\n".join(f"b {i}" for i in range(7))
    assert LST._body_line_count(fm + body) == 7


def test_body_line_count_no_frontmatter():
    text = "\n".join(f"line {i}" for i in range(12))
    assert LST._body_line_count(text) == 12


# ---------- check_prompts_listed (warn) ----------

def test_check_prompts_listed_no_dir_returns_empty(tmp_path):
    d = _make_skill(tmp_path)
    assert LST.check_prompts_listed(d, d / "SKILL.md") == []


def test_check_prompts_listed_warns_unlisted(tmp_path):
    d = _make_skill(tmp_path, fm="name: foo\nkind: run\n")
    prompts = d / "prompts"
    prompts.mkdir()
    (prompts / "unlisted.md").write_text("x", encoding="utf-8")
    warns = LST.check_prompts_listed(d, d / "SKILL.md")
    assert len(warns) == 1
    assert "prompts/unlisted.md" in warns[0]
    assert warns[0].startswith("[Warn]")


def test_check_prompts_listed_no_warn_when_listed(tmp_path):
    fm = "name: foo\nkind: run\nresponsibility_refs:\n  - prompts/listed.md\n"
    d = _make_skill(tmp_path, fm=fm)
    prompts = d / "prompts"
    prompts.mkdir()
    (prompts / "listed.md").write_text("x", encoding="utf-8")
    assert LST.check_prompts_listed(d, d / "SKILL.md") == []


# ---------- check_os_preamble ----------

def test_check_os_preamble_missing_flagged(tmp_path):
    d = _make_skill(tmp_path, fm="name: foo\nkind: run\ncross_platform: true\n")
    errs = LST.check_os_preamble(d / "SKILL.md")
    assert len(errs) == 1
    assert "13章違反" in errs[0]


def test_check_os_preamble_present_no_error(tmp_path):
    d = tmp_path / "run-foo"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: foo\nkind: run\ncross_platform: true\n---\n"
        "!`uname -s 2>/dev/null || ver`\nbody\n",
        encoding="utf-8",
    )
    assert LST.check_os_preamble(d / "SKILL.md") == []


def test_check_os_preamble_not_required_no_error(tmp_path):
    d = _make_skill(tmp_path)
    assert LST.check_os_preamble(d / "SKILL.md") == []


# ---------- lint_one (end-to-end pure) ----------

def test_lint_one_clean_skill_no_errors(tmp_path):
    d = _make_skill(tmp_path)
    assert LST.lint_one(d) == []


def test_lint_one_missing_skill_md(tmp_path):
    d = tmp_path / "empty-skill"
    d.mkdir()
    errs = LST.lint_one(d)
    assert errs == ["missing SKILL.md"]


def test_lint_one_body_over_limit(tmp_path):
    d = _make_skill(tmp_path, body_lines=LST.MAX_SKILL_LINES + 5)
    errs = LST.lint_one(d)
    assert any("P0-2違反" in e for e in errs)


def test_lint_one_nested_dir_violation(tmp_path):
    d = _make_skill(tmp_path)
    (d / "references" / "deep").mkdir(parents=True)
    errs = LST.lint_one(d)
    assert any("第13条違反" in e and "deep" in e for e in errs)


def test_lint_one_scripts_bad_extension(tmp_path):
    d = _make_skill(tmp_path)
    scripts = d / "scripts"
    scripts.mkdir()
    (scripts / "tool.txt").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert any("第10条違反" in e for e in errs)


def test_lint_one_references_bad_extension(tmp_path):
    d = _make_skill(tmp_path)
    refs = d / "references"
    refs.mkdir()
    (refs / "doc.txt").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert any("第8〜11条違反" in e for e in errs)


def test_lint_one_references_three_files_need_resource_map(tmp_path):
    d = _make_skill(tmp_path)
    refs = d / "references"
    refs.mkdir()
    for n in ("a.md", "b.md", "c.md"):
        (refs / n).write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert any("P1-2違反" in e for e in errs)


def test_lint_one_references_with_resource_map_ok(tmp_path):
    d = _make_skill(tmp_path)
    refs = d / "references"
    refs.mkdir()
    for n in ("a.md", "b.md", "resource-map.yaml"):
        (refs / n).write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert not any("P1-2違反" in e for e in errs)


def test_lint_one_ref_skill_bad_rubric_placement(tmp_path):
    d = _make_skill(tmp_path, name="ref-thing")
    (d / "rubric.json").write_text("{}", encoding="utf-8")
    errs = LST.lint_one(d)
    assert any("rubric placement 違反" in e for e in errs)


def test_lint_one_templates_subtree_skipped(tmp_path):
    # templates/ 配下は skill 規約検査をスキップするので深さ違反にしない
    d = _make_skill(tmp_path)
    tdir = d / "templates" / "nested"
    tdir.mkdir(parents=True)
    (tdir / "x.txt").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert not any("第13条違反" in e for e in errs)


# ---------- main via subprocess ----------

def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_main_no_args_usage(tmp_path):
    r = _run()
    assert r.returncode == 2
    assert "usage" in r.stderr


def test_main_not_a_directory(tmp_path):
    r = _run(str(tmp_path / "nope"))
    assert r.returncode == 2
    assert "not a directory" in r.stderr


def test_main_single_dir_ok(tmp_path):
    d = _make_skill(tmp_path)
    r = _run(str(d))
    assert r.returncode == 0
    assert r.stdout.startswith("ok:")


def test_main_single_dir_fail(tmp_path):
    d = _make_skill(tmp_path, body_lines=LST.MAX_SKILL_LINES + 5)
    r = _run(str(d))
    assert r.returncode == 1
    assert "P0-2違反" in r.stderr


def test_main_skills_dir_mode_ok(tmp_path):
    base = tmp_path / "skills"
    base.mkdir()
    _make_skill(base, name="run-a")
    _make_skill(base, name="run-b")
    r = _run("--skills-dir", str(base))
    assert r.returncode == 0
    assert "2 skills" in r.stdout


def test_main_skills_dir_mode_reports_per_skill(tmp_path):
    base = tmp_path / "skills"
    base.mkdir()
    _make_skill(base, name="run-good")
    _make_skill(base, name="run-bad", body_lines=LST.MAX_SKILL_LINES + 5)
    r = _run("--skills-dir", str(base))
    assert r.returncode == 1
    assert "run-bad:" in r.stderr


def test_main_skills_dir_missing_arg(tmp_path):
    r = _run("--skills-dir")
    assert r.returncode == 2
    assert "usage" in r.stderr


def test_main_skills_dir_not_a_dir(tmp_path):
    r = _run("--skills-dir", str(tmp_path / "nope"))
    assert r.returncode == 2
    assert "not a directory" in r.stderr
