"""lint-skill-completeness.py の kind 別完全性ゲートを実入力で網羅検証する。

対象 script:
  plugins/skill-governance-lint/scripts/lint-skill-completeness.py

方針:
  - 純関数 (parse_frontmatter / _as_str / _is_true / resolve_kind / parse_exempt /
    category_satisfied / lint_one) を実ファイルから importlib でロードして直接呼ぶ。
  - lint_one は tmp_path に kind 別の「合格 fixture」と「各違反 fixture」を書いて
    実入力で findings を assert する。
  - main は subprocess(sys.executable) で単一 skill / --skills-dir / usage error の
    全経路を exit code と stdout/stderr で assert する。
  - network / keychain / Notion 依存は無い純ローカル lint なので stub 不要。
    全 fixture は tmp_path 配下で repo を汚染しない。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-lint"
    / "scripts"
    / "lint-skill-completeness.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("lint_skill_completeness_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _mk_skill(parent: Path, name: str, frontmatter: str, *, with_md: bool = True) -> Path:
    """tmp_path 配下に skill ディレクトリと SKILL.md を作る。"""
    d = parent / name
    d.mkdir(parents=True, exist_ok=True)
    if with_md:
        (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# {name}\n", encoding="utf-8")
    return d


def _add_file(d: Path, rel: str, content: str = "x") -> Path:
    p = d / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------
def test_parse_frontmatter_scalar_and_list(MOD):
    text = (
        "---\n"
        "prefix: ref\n"
        'name: "ref-foo"\n'
        "reference_refs:\n"
        "  - ../other/references/a.md\n"
        "  - ../other/references/b.md\n"
        "empty_list:\n"
        "scalar_after: bar\n"
        "---\n\nbody\n"
    )
    fm = MOD.parse_frontmatter(text)
    assert fm["prefix"] == "ref"
    assert fm["name"] == '"ref-foo"'  # クォートは parse 段では除去しない
    assert fm["reference_refs"] == ["../other/references/a.md", "../other/references/b.md"]
    assert fm["empty_list"] == []
    assert fm["scalar_after"] == "bar"


def test_parse_frontmatter_no_frontmatter(MOD):
    assert MOD.parse_frontmatter("just body, no fence") == {}


def test_parse_frontmatter_unterminated(MOD):
    # 開始 --- はあるが終端 --- が無い (split で 3 分割できない)
    assert MOD.parse_frontmatter("---\nprefix: ref\n") == {}


def test_parse_frontmatter_blank_line_resets_list(MOD):
    text = "---\nlist_a:\n  - x\n\n  - y\n---\n"
    fm = MOD.parse_frontmatter(text)
    # 空行で current_list_key がリセットされるので 2 個目の `- y` は list に入らない
    assert fm["list_a"] == ["x"]


# ---------------------------------------------------------------------------
# _as_str / _is_true
# ---------------------------------------------------------------------------
def test_as_str_strips_quotes_and_none(MOD):
    assert MOD._as_str('"hello"') == "hello"
    assert MOD._as_str("'world'") == "world"
    assert MOD._as_str(None) == ""
    assert MOD._as_str(123) == "123"


def test_is_true_variants(MOD):
    assert MOD._is_true(True) is True
    assert MOD._is_true(False) is False
    assert MOD._is_true("true") is True
    assert MOD._is_true("True") is True
    assert MOD._is_true("false") is False
    assert MOD._is_true(None) is False


# ---------------------------------------------------------------------------
# resolve_kind
# ---------------------------------------------------------------------------
def test_resolve_kind_assign_evaluator_by_role(MOD):
    assert MOD.resolve_kind({"prefix": "assign", "role_suffix": "evaluator"}, "assign-x") == "assign-evaluator"


def test_resolve_kind_assign_evaluator_by_name_suffix(MOD):
    assert MOD.resolve_kind({}, "assign-foo-evaluator") == "assign-evaluator"


def test_resolve_kind_assign_generator(MOD):
    assert MOD.resolve_kind({"prefix": "assign"}, "assign-foo-generator") == "assign-generator"


def test_resolve_kind_explicit_prefixes(MOD):
    for p in ("ref", "run", "wrap", "delegate"):
        assert MOD.resolve_kind({"prefix": p}, f"{p}-thing") == p


def test_resolve_kind_uses_kind_field_fallback(MOD):
    # prefix 不在で kind フィールドから読む
    assert MOD.resolve_kind({"kind": "run"}, "whatever") == "run"


def test_resolve_kind_inferred_from_name(MOD):
    assert MOD.resolve_kind({}, "wrap-git-commit") == "wrap"
    assert MOD.resolve_kind({}, "delegate-codex") == "delegate"


def test_resolve_kind_none_for_unknown(MOD):
    assert MOD.resolve_kind({}, "totally-unknown") is None


# ---------------------------------------------------------------------------
# parse_exempt
# ---------------------------------------------------------------------------
def test_parse_exempt_dict_from_list(MOD):
    fm = {"completeness_exempt": ["schemas: no schema needed", "prompts：日本語コロン理由"]}
    out = MOD.parse_exempt(fm)
    assert out["schemas"] == "no schema needed"
    assert out["prompts"] == "日本語コロン理由"


def test_parse_exempt_non_list_returns_empty(MOD):
    assert MOD.parse_exempt({"completeness_exempt": "scalar"}) == {}
    assert MOD.parse_exempt({}) == {}


def test_parse_exempt_skips_malformed_items(MOD):
    out = MOD.parse_exempt({"completeness_exempt": ["no-colon-here", "ok: reason"]})
    assert "ok" in out
    assert len(out) == 1


# ---------------------------------------------------------------------------
# category_satisfied
# ---------------------------------------------------------------------------
def test_category_satisfied_by_exempt(MOD, tmp_path):
    assert MOD.category_satisfied(tmp_path, {}, "schemas", {"schemas": "reason"}, None, []) is True


def test_category_satisfied_exempt_empty_reason_ignored(MOD, tmp_path):
    # 空理由は免除として無効 (それ以外の経路も無いので False)
    assert MOD.category_satisfied(tmp_path, {}, "scripts", {"scripts": ""}, None, []) is False


def test_category_satisfied_prompts_policy_skip(MOD, tmp_path):
    assert MOD.category_satisfied(tmp_path, {"prompt_creator_policy": "skip"}, "prompts", {}, None, []) is True


def test_category_satisfied_prompts_use_prompt_creator_false(MOD, tmp_path):
    assert MOD.category_satisfied(tmp_path, {"use_prompt_creator": "false"}, "prompts", {}, None, []) is True
    # true なら skip 経路は効かない (他経路も無いので False)
    assert MOD.category_satisfied(tmp_path, {"use_prompt_creator": "true"}, "prompts", {}, None, []) is False


def test_category_satisfied_by_refs(MOD, tmp_path):
    # MD-208: *_refs は参照先の実在まで検証されるので、skill dir 相対で
    # 解決可能な実ファイルを置いてから「ref により充足」を確認する。
    _add_file(tmp_path, "o/schemas/a.json", "{}")
    _add_file(tmp_path, "o/r.md", "doc")
    _add_file(tmp_path, "o/p.md", "prompt")
    _add_file(tmp_path, "o/s.py", "print(1)")
    _add_file(tmp_path, "o/references/rubric.json", "{}")
    assert MOD.category_satisfied(tmp_path, {"schema_refs": ["o/schemas/a.json"]}, "schemas", {}, None, []) is True
    assert MOD.category_satisfied(tmp_path, {"reference_refs": ["o/r.md"]}, "references", {}, None, []) is True
    assert MOD.category_satisfied(tmp_path, {"prompt_refs": ["o/p.md"]}, "prompts", {}, None, []) is True
    assert MOD.category_satisfied(tmp_path, {"responsibility_refs": ["o/p.md"]}, "prompts", {}, None, []) is True
    assert MOD.category_satisfied(tmp_path, {"script_refs": ["o/s.py"]}, "scripts", {}, None, []) is True
    assert MOD.category_satisfied(tmp_path, {"rubric_refs": ["o/references/rubric.json"]}, "rubric", {}, None, []) is True


def test_category_satisfied_dangling_ref_does_not_satisfy(MOD, tmp_path):
    # MD-208: 解決不可な ref は充足しない & findings に dangling を追記する。
    findings = []
    assert MOD.category_satisfied(tmp_path, {"schema_refs": ["../o/schemas/a.json"]}, "schemas", {}, None, findings) is False
    assert len(findings) == 1
    assert "解決不可" in findings[0]


def test_category_satisfied_empty_refs_does_not_satisfy(MOD, tmp_path):
    assert MOD.category_satisfied(tmp_path, {"schema_refs": []}, "schemas", {}, None, []) is False


def test_category_satisfied_local_rubric_file(MOD, tmp_path):
    assert MOD.category_satisfied(tmp_path, {}, "rubric", {}, None, []) is False
    _add_file(tmp_path, "references/rubric.json", "{}")
    assert MOD.category_satisfied(tmp_path, {}, "rubric", {}, None, []) is True


def test_category_satisfied_local_schemas_dir(MOD, tmp_path):
    # 空ディレクトリは不可
    (tmp_path / "schemas").mkdir()
    assert MOD.category_satisfied(tmp_path, {}, "schemas", {}, None, []) is False
    # 非 json ファイルだけでは不可
    _add_file(tmp_path, "schemas/note.txt", "x")
    assert MOD.category_satisfied(tmp_path, {}, "schemas", {}, None, []) is False
    # json があれば満たす
    _add_file(tmp_path, "schemas/s.json", "{}")
    assert MOD.category_satisfied(tmp_path, {}, "schemas", {}, None, []) is True


def test_category_satisfied_local_dir_categories(MOD, tmp_path):
    for cat in ("prompts", "references", "scripts"):
        d = tmp_path / cat
        assert MOD.category_satisfied(tmp_path, {}, cat, {}, None, []) is False  # 不在
        d.mkdir()
        assert MOD.category_satisfied(tmp_path, {}, cat, {}, None, []) is False  # 空
        _add_file(tmp_path, f"{cat}/file.txt", "content")
        assert MOD.category_satisfied(tmp_path, {}, cat, {}, None, []) is True


# ---------------------------------------------------------------------------
# lint_one
# ---------------------------------------------------------------------------
def test_lint_one_missing_skill_md(MOD, tmp_path):
    d = tmp_path / "ref-foo"
    d.mkdir()
    findings = MOD.lint_one(d)
    assert findings == ["ref-foo: missing SKILL.md"]


def test_lint_one_unresolvable_kind_is_ignored(MOD, tmp_path):
    d = _mk_skill(tmp_path, "random-name", "name: random-name")
    assert MOD.lint_one(d) == []


def test_lint_one_ref_clean(MOD, tmp_path):
    d = _mk_skill(tmp_path, "ref-foo", "prefix: ref")
    _add_file(d, "references/a.md", "doc")
    _add_file(d, "prompts/p.md", "prompt")
    assert MOD.lint_one(d) == []


def test_lint_one_ref_missing_both(MOD, tmp_path):
    d = _mk_skill(tmp_path, "ref-foo", "prefix: ref")
    findings = MOD.lint_one(d)
    cats = {f.split("'")[1] for f in findings}
    assert cats == {"references", "prompts"}
    # 解消ヒントが含まれること
    assert any("references/ に実体を置く" in f for f in findings)
    assert any("reference_refs" in f for f in findings)


def test_lint_one_run_clean_via_prompt_skip(MOD, tmp_path):
    d = _mk_skill(tmp_path, "run-foo", "prefix: run\nprompt_creator_policy: skip")
    assert MOD.lint_one(d) == []


def test_lint_one_run_missing_prompts(MOD, tmp_path):
    d = _mk_skill(tmp_path, "run-foo", "prefix: run")
    findings = MOD.lint_one(d)
    assert len(findings) == 1
    assert "'prompts'" in findings[0]


def test_lint_one_assign_evaluator_clean(MOD, tmp_path):
    d = _mk_skill(tmp_path, "assign-x-evaluator", "prefix: assign\nrole_suffix: evaluator")
    _add_file(d, "references/rubric.json", "{}")
    _add_file(d, "schemas/s.json", "{}")
    _add_file(d, "prompts/p.md", "p")
    assert MOD.lint_one(d) == []


def test_lint_one_assign_evaluator_missing_all(MOD, tmp_path):
    d = _mk_skill(tmp_path, "assign-x-evaluator", "prefix: assign\nrole_suffix: evaluator")
    findings = MOD.lint_one(d)
    cats = {f.split("'")[1] for f in findings}
    assert cats == {"rubric", "schemas", "prompts"}


def test_lint_one_assign_generator_clean_via_refs_and_exempt(MOD, tmp_path):
    fm = (
        "prefix: assign\n"
        "schema_refs:\n"
        "  - ../shared/schemas/s.json\n"
        "completeness_exempt:\n"
        "  - prompts: 生成は inline のため prompts ディレクトリ不要\n"
    )
    d = _mk_skill(tmp_path, "assign-foo-generator", fm)
    # MD-208: schema_refs は実在まで検証されるので参照先 (skill dir 相対) を実在させる
    _add_file(tmp_path, "shared/schemas/s.json", "{}")
    assert MOD.lint_one(d) == []


def test_lint_one_wrap_clean(MOD, tmp_path):
    d = _mk_skill(tmp_path, "wrap-foo", "prefix: wrap")
    _add_file(d, "scripts/run.py", "print(1)")
    _add_file(d, "schemas/s.json", "{}")
    assert MOD.lint_one(d) == []


def test_lint_one_delegate_missing(MOD, tmp_path):
    d = _mk_skill(tmp_path, "delegate-foo", "prefix: delegate")
    findings = MOD.lint_one(d)
    cats = {f.split("'")[1] for f in findings}
    assert cats == {"prompts", "schemas"}


# ---------------------------------------------------------------------------
# main (subprocess)  — exit code / 出力契約
# ---------------------------------------------------------------------------
def test_main_no_args_usage_error(MOD):
    r = _run([])
    assert r.returncode == 2
    assert "usage:" in r.stderr


def test_main_single_skill_ok(MOD, tmp_path):
    d = _mk_skill(tmp_path, "ref-foo", "prefix: ref")
    _add_file(d, "references/a.md", "doc")
    _add_file(d, "prompts/p.md", "prompt")
    r = _run([str(d)])
    assert r.returncode == 0
    assert "ok: ref-foo (completeness)" in r.stdout


def test_main_single_skill_findings(MOD, tmp_path):
    d = _mk_skill(tmp_path, "ref-foo", "prefix: ref")
    r = _run([str(d)])
    assert r.returncode == 1
    assert "ref-foo: [ref]" in r.stderr


def test_main_single_skill_not_a_directory(MOD, tmp_path):
    missing = tmp_path / "nope"
    r = _run([str(missing)])
    assert r.returncode == 2
    assert "not a directory" in r.stderr


def test_main_skills_dir_ok(MOD, tmp_path):
    base = tmp_path / "skills"
    base.mkdir()
    d1 = _mk_skill(base, "ref-a", "prefix: ref")
    _add_file(d1, "references/a.md", "doc")
    _add_file(d1, "prompts/p.md", "p")
    d2 = _mk_skill(base, "run-b", "prefix: run\nprompt_creator_policy: skip")
    # kind 判定不能ディレクトリも混ぜる (無視される)
    _mk_skill(base, "misc", "name: misc")
    r = _run(["--skills-dir", str(base)])
    assert r.returncode == 0
    assert "completeness" in r.stdout
    assert "3 skills" in r.stdout  # ディレクトリ数 (判定不能含む)


def test_main_skills_dir_findings(MOD, tmp_path):
    base = tmp_path / "skills"
    base.mkdir()
    _mk_skill(base, "ref-a", "prefix: ref")  # 欠落
    r = _run(["--skills-dir", str(base)])
    assert r.returncode == 1
    assert "ref-a: [ref]" in r.stderr


def test_main_skills_dir_missing_value(MOD):
    r = _run(["--skills-dir"])
    assert r.returncode == 2
    assert "usage:" in r.stderr


def test_main_skills_dir_not_a_directory(MOD, tmp_path):
    r = _run(["--skills-dir", str(tmp_path / "nope")])
    assert r.returncode == 2
    assert "not a directory" in r.stderr


def test_main_in_process_return_codes(MOD, tmp_path, monkeypatch, capsys):
    # main を in-process でも叩き return code を直接検証
    d = _mk_skill(tmp_path, "ref-foo", "prefix: ref")
    _add_file(d, "references/a.md", "doc")
    _add_file(d, "prompts/p.md", "p")
    monkeypatch.setattr(sys, "argv", ["lint-skill-completeness.py", str(d)])
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "ok: ref-foo" in out


# ---------------------------------------------------------------------------
# main (in-process) — 全分岐を直接実行して return code / 出力契約を網羅
#   (subprocess 経由ではカバレッジが回収されないため main 本体は in-process で被覆する)
# ---------------------------------------------------------------------------
def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["lint-skill-completeness.py", *args])


def test_main_inproc_no_args_usage(MOD, monkeypatch, capsys):
    _argv(monkeypatch)
    assert MOD.main() == 2
    err = capsys.readouterr().err
    assert "usage:" in err


def test_main_inproc_single_findings_exit1(MOD, tmp_path, monkeypatch, capsys):
    d = _mk_skill(tmp_path, "ref-foo", "prefix: ref")  # references/prompts 欠落
    _argv(monkeypatch, str(d))
    assert MOD.main() == 1
    err = capsys.readouterr().err
    assert "ref-foo: [ref]" in err
    # 2 カテゴリ分の findings が stderr に出ること
    assert err.count("ref-foo: [ref]") == 2


def test_main_inproc_single_not_a_directory(MOD, tmp_path, monkeypatch, capsys):
    _argv(monkeypatch, str(tmp_path / "missing"))
    assert MOD.main() == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_inproc_skills_dir_missing_value(MOD, monkeypatch, capsys):
    _argv(monkeypatch, "--skills-dir")
    assert MOD.main() == 2
    assert "usage:" in capsys.readouterr().err


def test_main_inproc_skills_dir_not_a_directory(MOD, tmp_path, monkeypatch, capsys):
    _argv(monkeypatch, "--skills-dir", str(tmp_path / "nope"))
    assert MOD.main() == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_inproc_skills_dir_ok_counts_dirs(MOD, tmp_path, monkeypatch, capsys):
    base = tmp_path / "skills"
    base.mkdir()
    d1 = _mk_skill(base, "ref-a", "prefix: ref")
    _add_file(d1, "references/a.md", "doc")
    _add_file(d1, "prompts/p.md", "p")
    _mk_skill(base, "run-b", "prefix: run\nprompt_creator_policy: skip")
    _mk_skill(base, "misc", "name: misc")  # kind 判定不能 (無視されるが count には入る)
    # ディレクトリでない混入物 (count されないこと)
    (base / "stray.txt").write_text("x", encoding="utf-8")
    _argv(monkeypatch, "--skills-dir", str(base))
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "3 skills" in out
    assert "completeness" in out


def test_main_inproc_skills_dir_findings_exit1(MOD, tmp_path, monkeypatch, capsys):
    base = tmp_path / "skills"
    base.mkdir()
    _mk_skill(base, "ref-a", "prefix: ref")  # 欠落
    _mk_skill(base, "wrap-b", "prefix: wrap")  # scripts/schemas 欠落
    _argv(monkeypatch, "--skills-dir", str(base))
    assert MOD.main() == 1
    err = capsys.readouterr().err
    assert "ref-a: [ref]" in err
    assert "wrap-b: [wrap]" in err


def test_module_executes_as_script_exit2(MOD, tmp_path):
    # __main__ ガード (raise SystemExit(main())) を subprocess で実行し非ゼロ終了を確認
    r = _run([])  # 引数無し => usage error exit 2
    assert r.returncode == 2
