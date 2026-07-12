"""genuine 機能テスト (scripts2): skill-governance-lint/scripts/lint-skill-name.py

tests/scripts-root/ 及び tests/scripts-plugins/ の既存テストとは別ディレクトリ・別観点で、行カバレッジ 80%+ を狙う。

方針:
- 純関数 parse_frontmatter / lint_file は import して実入力で assert。
- main() は in-process で sys.argv を monkeypatch + pytest.raises(SystemExit) で
  全 argv 分岐 (usage / 単一ファイル ok / 単一ファイル violation / --skills-dir
  missing value / not-a-dir / all-valid / violation) を網羅し、同一プロセスで
  coverage を計測する (subprocess だと別プロセスで計測漏れになるため)。
- 加えて __main__ 経路 (raise SystemExit(main())) の genuine 起動を subprocess で 1 本確認。

network / 外部 I/O は無い (network: false)。tmp_path のみ使用し repo を汚さない。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-skill-name.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("lint_skill_name_s2", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _write_skill(tmp_path: Path, dir_name: str, frontmatter: str) -> Path:
    d = tmp_path / dir_name
    d.mkdir()
    md = d / "SKILL.md"
    md.write_text(frontmatter, encoding="utf-8")
    return md


# =========================================================================
# parse_frontmatter — 各分岐
# =========================================================================
def test_parse_frontmatter_basic_pairs():
    fm = MOD.parse_frontmatter("---\nname: run-foo\nuser-invocable: true\n---\nbody text")
    assert fm == {"name": "run-foo", "user-invocable": "true"}


def test_parse_frontmatter_strips_double_quotes():
    assert MOD.parse_frontmatter('---\nname: "run-quoted"\n---\n')["name"] == "run-quoted"


def test_parse_frontmatter_returns_empty_without_leading_fence():
    # startswith("---") が False の早期 return 分岐
    assert MOD.parse_frontmatter("name: run-foo\n---\n") == {}


def test_parse_frontmatter_returns_empty_when_fence_not_closed():
    # split("---", 2) が 3 要素未満になる分岐
    assert MOD.parse_frontmatter("---\nname: run-foo\n") == {}


def test_parse_frontmatter_ignores_non_matching_lines():
    # 正規表現にマッチしない行 (コロン無し / 値空) は無視される
    text = "---\nname: run-foo\njust a sentence with no key\nempty:\n---\n"
    fm = MOD.parse_frontmatter(text)
    assert fm == {"name": "run-foo"}


def test_parse_frontmatter_underscore_and_hyphen_keys():
    text = "---\nrole_suffix: evaluator\nuser-invocable: false\n---\n"
    fm = MOD.parse_frontmatter(text)
    assert fm["role_suffix"] == "evaluator"
    assert fm["user-invocable"] == "false"


# =========================================================================
# lint_file — PASS ケース (全 prefix)
# =========================================================================
@pytest.mark.parametrize(
    "name,user_inv",
    [
        ("run-foo", "true"),
        ("ref-bar", "false"),
        ("wrap-git-commit-safe", "true"),
        ("delegate-codex-review", "true"),
        ("run-a", "true"),  # 最短に近い妥当名
    ],
)
def test_lint_file_pass_cases(tmp_path, name, user_inv):
    md = _write_skill(tmp_path, name, f"---\nname: {name}\nuser-invocable: {user_inv}\n---\n")
    assert MOD.lint_file(md) == []


def test_lint_file_pass_assign_evaluator_with_matching_role_suffix(tmp_path):
    md = _write_skill(
        tmp_path,
        "assign-plugin-package-evaluator",
        "---\nname: assign-plugin-package-evaluator\n"
        "user-invocable: false\nrole_suffix: evaluator\n---\n",
    )
    assert MOD.lint_file(md) == []


def test_lint_file_pass_assign_without_role_suffix_frontmatter(tmp_path):
    # role_suffix frontmatter が無くても name suffix が一致すれば OK
    md = _write_skill(
        tmp_path,
        "assign-prompt-design-evaluator",
        "---\nname: assign-prompt-design-evaluator\nuser-invocable: false\n---\n",
    )
    assert MOD.lint_file(md) == []


# =========================================================================
# lint_file — エッジ (欠落ファイル / name 欠落)
# =========================================================================
def test_lint_file_missing_file(tmp_path):
    errs = MOD.lint_file(tmp_path / "ghost" / "SKILL.md")
    assert len(errs) == 1
    assert "not found" in errs[0]


def test_lint_file_name_missing(tmp_path):
    md = _write_skill(tmp_path, "run-x", "---\nuser-invocable: true\n---\n")
    assert MOD.lint_file(md) == ["frontmatter.name not found"]


def test_lint_file_empty_file(tmp_path):
    # 完全に空 -> frontmatter 無し -> name 無し
    d = tmp_path / "run-empty"
    d.mkdir()
    md = d / "SKILL.md"
    md.write_text("", encoding="utf-8")
    assert MOD.lint_file(md) == ["frontmatter.name not found"]


# =========================================================================
# lint_file — 各条 (違反種別ごと) を個別に検証
# =========================================================================
def test_article1_not_kebab_uppercase(tmp_path):
    md = _write_skill(tmp_path, "run-FooBar", "---\nname: run-FooBar\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第1条違反" in e and "kebab-case" in e for e in errs)


def test_article1_not_kebab_double_hyphen(tmp_path):
    # 連続ハイフンは KEBAB_RE 不一致
    md = _write_skill(tmp_path, "run--foo", "---\nname: run--foo\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第1条違反" in e for e in errs)


def test_article2_unknown_prefix(tmp_path):
    md = _write_skill(tmp_path, "do-thing", "---\nname: do-thing\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第2条違反" in e for e in errs)


def test_article5_assign_missing_role_suffix(tmp_path):
    md = _write_skill(tmp_path, "assign-thing", "---\nname: assign-thing\nuser-invocable: false\n---\n")
    errs = MOD.lint_file(md)
    assert any("第5条違反" in e and "role suffix" in e for e in errs)


def test_article5_assign_two_role_suffixes_is_invalid(tmp_path):
    # name が 2 つの role suffix で終わる ... 実際には 1 つの -suffix のみ末尾一致だが
    # 末尾一致が 0 のケースを検証 (len(suffixes) != 1)
    md = _write_skill(
        tmp_path,
        "assign-foo-bar",
        "---\nname: assign-foo-bar\nuser-invocable: false\n---\n",
    )
    errs = MOD.lint_file(md)
    assert any("第5条違反" in e and "role suffix" in e for e in errs)


def test_article5_role_suffix_frontmatter_mismatch(tmp_path):
    md = _write_skill(
        tmp_path,
        "assign-design-evaluator",
        "---\nname: assign-design-evaluator\nuser-invocable: false\nrole_suffix: generator\n---\n",
    )
    errs = MOD.lint_file(md)
    assert any("role_suffix 'generator' != name suffix 'evaluator'" in e for e in errs)


def test_article4_ref_must_not_be_user_invocable(tmp_path):
    md = _write_skill(tmp_path, "ref-bad", "---\nname: ref-bad\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第4条違反" in e and "must not be user-invocable" in e for e in errs)


def test_article4_assign_must_not_be_user_invocable(tmp_path):
    md = _write_skill(
        tmp_path,
        "assign-skill-design-evaluator",
        "---\nname: assign-skill-design-evaluator\nuser-invocable: true\nrole_suffix: evaluator\n---\n",
    )
    errs = MOD.lint_file(md)
    assert any("第4条違反" in e and "must not be user-invocable" in e for e in errs)


def test_article4_run_must_be_user_invocable(tmp_path):
    md = _write_skill(tmp_path, "run-bad", "---\nname: run-bad\nuser-invocable: false\n---\n")
    errs = MOD.lint_file(md)
    assert any("第4条違反" in e and "must be user-invocable" in e for e in errs)


def test_article4_user_invocable_defaults_false(tmp_path):
    # user-invocable を frontmatter から省く -> default "false" -> run-* は違反
    md = _write_skill(tmp_path, "run-noflag", "---\nname: run-noflag\n---\n")
    errs = MOD.lint_file(md)
    assert any("第4条違反" in e and "must be user-invocable" in e for e in errs)


def test_article5_too_long(tmp_path):
    long_name = "run-" + "z" * 60  # > 60
    md = _write_skill(tmp_path, long_name, f"---\nname: {long_name}\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("len(name)=" in e and "> 60" in e for e in errs)


def test_article6_reserved_word_single(tmp_path):
    md = _write_skill(tmp_path, "run-skill", "---\nname: run-skill\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第6条違反" in e and "予約語" in e for e in errs)


def test_article6_reserved_word_not_flagged_when_multipart(tmp_path):
    # reserved 語でも複合語なら予約語単独使用ではない -> 第6条は出ない
    md = _write_skill(tmp_path, "run-skill-builder", "---\nname: run-skill-builder\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert not any("第6条違反" in e for e in errs)


def test_article16_forbidden_prefix_tmp(tmp_path):
    md = _write_skill(tmp_path, "tmp-thing", "---\nname: tmp-thing\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第16条違反" in e for e in errs)


def test_article16_forbidden_prefix_experimental(tmp_path):
    md = _write_skill(
        tmp_path, "experimental-x", "---\nname: experimental-x\nuser-invocable: true\n---\n"
    )
    errs = MOD.lint_file(md)
    assert any("第16条違反" in e for e in errs)


def test_article7_dir_name_mismatch(tmp_path):
    md = _write_skill(tmp_path, "run-actual-dir", "---\nname: run-foo\nuser-invocable: true\n---\n")
    errs = MOD.lint_file(md)
    assert any("第7条違反" in e and "run-actual-dir" in e and "run-foo" in e for e in errs)


def test_lint_file_accumulates_multiple_violations(tmp_path):
    # 大文字 (第1条) + 不正 prefix (第2条) + dir 不一致 (第7条) を同時に
    md = _write_skill(tmp_path, "Other_Dir", "---\nname: Bad_Name\nuser-invocable: false\n---\n")
    errs = MOD.lint_file(md)
    assert any("第1条違反" in e for e in errs)
    assert any("第2条違反" in e for e in errs)
    assert any("第7条違反" in e for e in errs)


# =========================================================================
# main() — in-process で全 argv 分岐を網羅 (coverage 計測のため同一プロセス)
# =========================================================================
def _run_main_in_process(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["lint-skill-name.py", *argv])
    return MOD.main()


def test_main_no_args_returns_2(monkeypatch, capsys):
    rc = _run_main_in_process(monkeypatch, [])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_single_valid_returns_0(monkeypatch, capsys, tmp_path):
    md = _write_skill(tmp_path, "run-foo", "---\nname: run-foo\nuser-invocable: true\n---\n")
    rc = _run_main_in_process(monkeypatch, [str(md)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ok: run-foo" in out


def test_main_single_violation_returns_1(monkeypatch, capsys, tmp_path):
    md = _write_skill(tmp_path, "do-thing", "---\nname: do-thing\nuser-invocable: true\n---\n")
    rc = _run_main_in_process(monkeypatch, [str(md)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "第2条違反" in err


def test_main_skills_dir_missing_value_returns_2(monkeypatch, capsys):
    rc = _run_main_in_process(monkeypatch, ["--skills-dir"])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_skills_dir_not_a_directory_returns_2(monkeypatch, capsys, tmp_path):
    rc = _run_main_in_process(monkeypatch, ["--skills-dir", str(tmp_path / "nope")])
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_skills_dir_all_valid_returns_0(monkeypatch, capsys, tmp_path):
    _write_skill(tmp_path, "run-a", "---\nname: run-a\nuser-invocable: true\n---\n")
    _write_skill(tmp_path, "ref-b", "---\nname: ref-b\nuser-invocable: false\n---\n")
    rc = _run_main_in_process(monkeypatch, ["--skills-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 skills" in out


def test_main_skills_dir_with_violation_returns_1(monkeypatch, capsys, tmp_path):
    _write_skill(tmp_path, "run-good", "---\nname: run-good\nuser-invocable: true\n---\n")
    _write_skill(tmp_path, "bad-name", "---\nname: bad-name\nuser-invocable: true\n---\n")
    rc = _run_main_in_process(monkeypatch, ["--skills-dir", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "bad-name:" in err


def test_main_skills_dir_empty_dir_returns_0(monkeypatch, capsys, tmp_path):
    # SKILL.md が 1 件も無い -> scanned=0 だが total_errs 空なので exit 0
    rc = _run_main_in_process(monkeypatch, ["--skills-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 skills" in out


# =========================================================================
# __main__ 経路 (raise SystemExit(main())) の genuine 起動を subprocess で確認
# =========================================================================
def test_dunder_main_entrypoint_via_subprocess(tmp_path):
    md = _write_skill(tmp_path, "run-foo", "---\nname: run-foo\nuser-invocable: true\n---\n")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(md)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "ok: run-foo" in proc.stdout
