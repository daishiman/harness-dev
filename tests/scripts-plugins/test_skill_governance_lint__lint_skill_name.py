"""lint-skill-name.py の genuine 機能テスト。

純関数 parse_frontmatter / lint_file を実入力 (tmp_path 上の SKILL.md) で呼び、
naming convention 各条 (第1/2/4/5/6/7/16条) の検出を実出力で assert する。
main() は subprocess (sys.executable) で --help 相当の usage / 単一ファイル /
--skills-dir / 不正入力を与え returncode と出力を検証する。
network/外部 I/O なし (network: false)。tmp_path のみ使用し repo を汚さない。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-skill-name.py"

SPEC = importlib.util.spec_from_file_location("lint_skill_name", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _write_skill(tmp_path: Path, dir_name: str, frontmatter: str) -> Path:
    """tmp_path/<dir_name>/SKILL.md を作り frontmatter を書く。"""
    d = tmp_path / dir_name
    d.mkdir()
    md = d / "SKILL.md"
    md.write_text(frontmatter, encoding="utf-8")
    return md


# --- parse_frontmatter ---

def test_parse_frontmatter_extracts_pairs():
    text = "---\nname: run-foo\nuser-invocable: true\n---\nbody"
    fm = MOD.parse_frontmatter(text)
    assert fm["name"] == "run-foo"
    assert fm["user-invocable"] == "true"


def test_parse_frontmatter_strips_quotes():
    text = '---\nname: "run-bar"\n---\n'
    assert MOD.parse_frontmatter(text)["name"] == "run-bar"


def test_parse_frontmatter_no_frontmatter_returns_empty():
    assert MOD.parse_frontmatter("no front matter here") == {}


def test_parse_frontmatter_incomplete_fence_returns_empty():
    # 終端 --- が無い
    assert MOD.parse_frontmatter("---\nname: x\n") == {}


# --- lint_file: 合格ケース ---

def test_lint_file_valid_run_skill_no_errors(tmp_path):
    md = _write_skill(tmp_path, "run-foo", "---\nname: run-foo\nuser-invocable: true\n---\n")
    assert MOD.lint_file(md) == []


def test_lint_file_valid_ref_skill_no_errors(tmp_path):
    md = _write_skill(tmp_path, "ref-bar", "---\nname: ref-bar\nuser-invocable: false\n---\n")
    assert MOD.lint_file(md) == []


def test_lint_file_valid_assign_evaluator_no_errors(tmp_path):
    md = _write_skill(
        tmp_path,
        "assign-skill-design-evaluator",
        "---\nname: assign-skill-design-evaluator\n"
        "user-invocable: false\nrole_suffix: evaluator\n---\n",
    )
    assert MOD.lint_file(md) == []


# --- lint_file: 各条違反の genuine 検出 ---

def test_lint_file_not_found(tmp_path):
    errs = MOD.lint_file(tmp_path / "absent" / "SKILL.md")
    assert len(errs) == 1 and "not found" in errs[0]


def test_lint_file_missing_name(tmp_path):
    md = _write_skill(tmp_path, "run-x", "---\nuser-invocable: true\n---\n")
    assert MOD.lint_file(md) == ["frontmatter.name not found"]


def test_lint_file_article1_not_kebab(tmp_path):
    # name に大文字/アンダースコア -> 第1条 + dir 名不一致(第7条)
    md = _write_skill(tmp_path, "run-Foo_Bar", "---\nname: run-Foo_Bar\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第1条違反" in e for e in errs)


def test_lint_file_article2_bad_prefix(tmp_path):
    md = _write_skill(tmp_path, "do-thing", "---\nname: do-thing\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第2条違反" in e for e in errs)


def test_lint_file_article5_assign_without_role_suffix(tmp_path):
    md = _write_skill(tmp_path, "assign-thing", "---\nname: assign-thing\nuser-invocable: false\n---\n")
    errs = MOD.lint_file(md)
    assert any("第5条違反" in e and "role suffix" in e for e in errs)


def test_lint_file_article5_role_suffix_mismatch(tmp_path):
    md = _write_skill(
        tmp_path,
        "assign-design-evaluator",
        "---\nname: assign-design-evaluator\nuser-invocable: false\nrole_suffix: generator\n---\n",
    )
    errs = MOD.lint_file(md)
    assert any("role_suffix 'generator'" in e for e in errs)


def test_lint_file_article4_ref_must_not_be_user_invocable(tmp_path):
    md = _write_skill(tmp_path, "ref-bad", "---\nname: ref-bad\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第4条違反" in e and "must not be user-invocable" in e for e in errs)


def test_lint_file_article4_run_must_be_user_invocable(tmp_path):
    md = _write_skill(tmp_path, "run-bad", "---\nname: run-bad\nuser-invocable: false\n---\n")
    errs = MOD.lint_file(md)
    assert any("第4条違反" in e and "must be user-invocable" in e for e in errs)


def test_lint_file_article5_too_long(tmp_path):
    long_name = "run-" + "a" * 60  # > 60 chars
    md = _write_skill(tmp_path, long_name, f"---\nname: {long_name}\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("> 60" in e for e in errs)


def test_lint_file_article6_reserved_word(tmp_path):
    md = _write_skill(tmp_path, "run-skill", "---\nname: run-skill\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第6条違反" in e and "予約語" in e for e in errs)


def test_lint_file_article16_forbidden_prefix(tmp_path):
    # forbidden prefix test- は第2条(許可prefixでない)にも違反する
    md = _write_skill(tmp_path, "test-thing", "---\nname: test-thing\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第16条違反" in e for e in errs)


def test_lint_file_article7_dir_name_mismatch(tmp_path):
    md = _write_skill(tmp_path, "run-other-dir", "---\nname: run-foo\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第7条違反" in e for e in errs)


# --- main(): subprocess ---

def _run(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else str(ROOT),
    )


def test_main_no_args_usage_exit_2():
    proc = _run([])
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_main_single_valid_file_exit_0(tmp_path):
    md = _write_skill(tmp_path, "run-foo", "---\nname: run-foo\nuser-invocable: true\n---\n")
    proc = _run([str(md)])
    assert proc.returncode == 0
    assert "ok: run-foo" in proc.stdout


def test_main_single_violating_file_exit_1(tmp_path):
    md = _write_skill(tmp_path, "do-thing", "---\nname: do-thing\nuser-invocable: true\n---\n")
    proc = _run([str(md)])
    assert proc.returncode == 1
    assert "第2条違反" in proc.stderr


def test_main_skills_dir_missing_value_exit_2():
    proc = _run(["--skills-dir"])
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_main_skills_dir_not_a_directory_exit_2(tmp_path):
    proc = _run(["--skills-dir", str(tmp_path / "nope")])
    assert proc.returncode == 2
    assert "not a directory" in proc.stderr


def test_main_skills_dir_all_valid_exit_0(tmp_path):
    _write_skill(tmp_path, "run-a", "---\nname: run-a\nuser-invocable: true\n---\n")
    _write_skill(tmp_path, "ref-b", "---\nname: ref-b\nuser-invocable: false\n---\n")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 0
    assert "2 skills" in proc.stdout


def test_main_skills_dir_with_violation_exit_1(tmp_path):
    _write_skill(tmp_path, "run-good", "---\nname: run-good\nuser-invocable: true\n---\n")
    _write_skill(tmp_path, "bad-name", "---\nname: bad-name\nuser-invocable: true\n---\n")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 1
    # 違反行は <dirname>: <error> の形式
    assert "bad-name:" in proc.stderr
