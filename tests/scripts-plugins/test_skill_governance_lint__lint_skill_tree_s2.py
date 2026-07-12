"""網羅補完テスト: plugins/skill-governance-lint/scripts/lint-skill-tree.py

tests/scripts-root/ 及び tests/scripts-plugins/ の既存テストが触れていない分岐を埋めて 80% 以上へ。
特に main() を in-process で呼び (subprocess はカバレッジ計測外)、
_parse_fm_simple / check_prompts_listed の欠落 frontmatter・suffix skip・
非ファイル skip、lint_one の __pycache__ skip / extra top-level dir(pass) /
MED-4 warn 出力 (stderr print 経路) を genuine に実証する。

副作用なし: 全 fixture は tmp_path、main() は monkeypatch(sys.argv) で隔離。
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-skill-tree.py"

_SPEC = importlib.util.spec_from_file_location("lint_skill_tree_s2", SCRIPT)
LST = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LST)


def _make_skill(tmp_path, name="run-foo", body_lines=10, fm=None):
    d = tmp_path / name
    d.mkdir()
    fm = fm or "name: run-foo\nkind: run\n"
    body = "\n".join(f"line {i}" for i in range(body_lines))
    (d / "SKILL.md").write_text(f"---\n{fm}---\n{body}\n", encoding="utf-8")
    return d


# --------------------------------------------------------------------------
# _parse_fm_simple: 閉じ --- 欠落 / 空行で list-context リセット
# --------------------------------------------------------------------------

def test_parse_fm_simple_unterminated_frontmatter_returns_empty():
    # 開始 --- はあるが閉じが無い → split('---',2) が len<3 → {}
    assert LST._parse_fm_simple("---\nname: x\nkind: run\n") == {}


def test_parse_fm_simple_blank_line_resets_list_context():
    # list 開始後に空行が来ると current_list_key がリセットされ、以降の
    # `- item` は list に積まれない。
    text = (
        "---\n"
        "refs:\n"
        "  - a\n"
        "\n"
        "  - b\n"
        "name: y\n"
        "---\nbody\n"
    )
    fm = LST._parse_fm_simple(text)
    assert fm["refs"] == ["a"]  # 空行後の b は積まれない
    assert fm["name"] == "y"


# --------------------------------------------------------------------------
# check_prompts_listed: frontmatter 欠落 / 閉じ欠落 / 非ファイル / 非対象 suffix
# --------------------------------------------------------------------------

def test_check_prompts_listed_skill_md_without_frontmatter_returns_empty(tmp_path):
    d = tmp_path / "run-foo"
    d.mkdir()
    (d / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
    (d / "prompts").mkdir()
    (d / "prompts" / "a.md").write_text("x", encoding="utf-8")
    assert LST.check_prompts_listed(d, d / "SKILL.md") == []


def test_check_prompts_listed_unterminated_frontmatter_returns_empty(tmp_path):
    d = tmp_path / "run-foo"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: x\n", encoding="utf-8")  # 閉じ無し
    (d / "prompts").mkdir()
    (d / "prompts" / "a.md").write_text("x", encoding="utf-8")
    assert LST.check_prompts_listed(d, d / "SKILL.md") == []


def test_check_prompts_listed_skips_subdir_and_nonmatching_suffix(tmp_path):
    d = _make_skill(tmp_path)
    prompts = d / "prompts"
    prompts.mkdir()
    # サブディレクトリ (非ファイル) は skip される
    (prompts / "nested").mkdir()
    # .txt は対象 suffix({.md,.yaml}) 外なので skip される
    (prompts / "note.txt").write_text("x", encoding="utf-8")
    # .yaml は対象 → 未列挙なので warn 1 件
    (prompts / "cfg.yaml").write_text("x", encoding="utf-8")
    warns = LST.check_prompts_listed(d, d / "SKILL.md")
    assert len(warns) == 1
    assert "prompts/cfg.yaml" in warns[0]


# --------------------------------------------------------------------------
# lint_one: __pycache__ skip / extra top-level dir(pass) / MED-4 stderr warn
# --------------------------------------------------------------------------

def test_lint_one_ignores_pycache_and_pyc(tmp_path):
    d = _make_skill(tmp_path)
    # __pycache__ ディレクトリ + .pyc は深さ/拡張子検査の対象外
    pc = d / "scripts" / "__pycache__"
    pc.mkdir(parents=True)
    (pc / "mod.cpython-311.pyc").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert errs == []


def test_lint_one_extra_top_level_dir_is_allowed(tmp_path):
    # ALLOWED_DIRS 外の top-level dir は warn 止まり(pass)で errs に出ない
    d = _make_skill(tmp_path)
    (d / "weird").mkdir()
    errs = LST.lint_one(d)
    assert errs == []


def test_lint_one_emits_med4_warn_to_stderr(tmp_path, capsys):
    d = _make_skill(tmp_path)
    prompts = d / "prompts"
    prompts.mkdir()
    (prompts / "unlisted.md").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    # MED-4 は exit 1 にしない(errs には積まれない)が stderr に warn が出る
    assert not any("MED-4" in e for e in errs)
    captured = capsys.readouterr()
    assert "MED-4" in captured.err
    assert "prompts/unlisted.md" in captured.err


def test_lint_one_examples_top_level_extension_checked(tmp_path):
    # examples/ 直下のファイルは template 系拡張子検査の対象 (top in
    # {templates,references,examples})。templates/ 配下は丸ごと skip されるため
    # 実際に検査が走るのは references/ と examples/。.txt は不正。
    d = _make_skill(tmp_path)
    t = d / "examples"
    t.mkdir()
    (t / "bad.txt").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert any("第8〜11条違反" in e for e in errs)


def test_lint_one_examples_allowed_extension_ok(tmp_path):
    d = _make_skill(tmp_path)
    t = d / "examples"
    t.mkdir()
    (t / "good.json").write_text("{}", encoding="utf-8")
    (t / "good.patch").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert not any("第8〜11条違反" in e for e in errs)


def test_lint_one_templates_subtree_files_fully_skipped(tmp_path):
    # templates/ 配下のファイル(深さ問わず)は skill 規約検査を skip するため
    # 不正拡張子でも違反にならない (line 202)。
    d = _make_skill(tmp_path)
    t = d / "templates"
    t.mkdir()
    (t / "anything.txt").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert not any("第8〜11条違反" in e for e in errs)


def test_lint_one_allowed_nested_combinators_dir_ok(tmp_path):
    # ALLOWED_NESTED_DIRS の templates/combinators は深さ違反にならない
    d = _make_skill(tmp_path)
    nested = d / "templates" / "combinators"
    nested.mkdir(parents=True)
    errs = LST.lint_one(d)
    assert not any("第13条違反" in e for e in errs)


def test_lint_one_examples_nested_dir_ok(tmp_path):
    # examples/ 配下の nested dir は生成出力見本 (完成例) のため構造検査 skip
    # (plugin-dev-planner examples/sample-plan/ の実例。2026-07-02)
    d = _make_skill(tmp_path)
    nested = d / "examples" / "sample-plan" / "envelope-draft"
    nested.mkdir(parents=True)
    (nested / "plugin.json").write_text("{}", encoding="utf-8")
    errs = LST.lint_one(d)
    assert not any("第13条違反" in e for e in errs)


def test_lint_one_examples_nested_bad_extension_still_flagged(tmp_path):
    # 構造は skip してもファイル拡張子検査 (第8-11条) は examples/ 配下で維持
    d = _make_skill(tmp_path)
    nested = d / "examples" / "sample-plan"
    nested.mkdir(parents=True)
    (nested / "binary.bin").write_text("x", encoding="utf-8")
    errs = LST.lint_one(d)
    assert any("第8〜11条違反" in e for e in errs)


def test_lint_one_assign_skill_bad_rubric_placement(tmp_path):
    d = _make_skill(tmp_path, name="assign-thing")
    (d / "rubric.json").write_text("{}", encoding="utf-8")
    errs = LST.lint_one(d)
    assert any("rubric placement 違反" in e for e in errs)


# --------------------------------------------------------------------------
# main(): in-process で argv を差し替えて全分岐を踏む(カバレッジ計測対象)
# --------------------------------------------------------------------------

def _run_main(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["lint-skill-tree.py", *argv])
    return LST.main()


def test_main_no_args_returns_2(monkeypatch, capsys):
    rc = _run_main(monkeypatch)
    assert rc == 2
    assert "usage" in capsys.readouterr().err


def test_main_not_a_directory_returns_2(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, str(tmp_path / "nope"))
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_single_dir_ok_returns_0(monkeypatch, tmp_path, capsys):
    d = _make_skill(tmp_path)
    rc = _run_main(monkeypatch, str(d))
    assert rc == 0
    assert capsys.readouterr().out.startswith("ok:")


def test_main_single_dir_fail_returns_1(monkeypatch, tmp_path, capsys):
    d = _make_skill(tmp_path, body_lines=LST.MAX_SKILL_LINES + 5)
    rc = _run_main(monkeypatch, str(d))
    assert rc == 1
    assert "P0-2違反" in capsys.readouterr().err


def test_main_skills_dir_missing_arg_returns_2(monkeypatch, capsys):
    rc = _run_main(monkeypatch, "--skills-dir")
    assert rc == 2
    assert "usage" in capsys.readouterr().err


def test_main_skills_dir_not_a_dir_returns_2(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, "--skills-dir", str(tmp_path / "nope"))
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_skills_dir_ok_returns_0(monkeypatch, tmp_path, capsys):
    base = tmp_path / "skills"
    base.mkdir()
    _make_skill(base, name="run-a")
    _make_skill(base, name="run-b")
    rc = _run_main(monkeypatch, "--skills-dir", str(base))
    assert rc == 0
    assert "2 skills" in capsys.readouterr().out


def test_main_skills_dir_reports_failures_returns_1(monkeypatch, tmp_path, capsys):
    base = tmp_path / "skills"
    base.mkdir()
    _make_skill(base, name="run-good")
    _make_skill(base, name="run-bad", body_lines=LST.MAX_SKILL_LINES + 5)
    rc = _run_main(monkeypatch, "--skills-dir", str(base))
    assert rc == 1
    err = capsys.readouterr().err
    assert "run-bad:" in err


def test_main_module_entry_point(monkeypatch, tmp_path):
    # `if __name__ == "__main__"` 経路を runpy で踏む (line 300)
    import runpy
    d = _make_skill(tmp_path)
    monkeypatch.setattr("sys.argv", ["lint-skill-tree.py", str(d)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exc.value.code == 0
