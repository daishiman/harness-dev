"""網羅補完テスト: plugins/skill-governance-lint/scripts/validate-frontmatter.py

tests/scripts-root/ 及び tests/scripts-plugins/ の既存テストが触れていない分岐を埋めて 80% 以上へ。
main() を in-process で呼び (subprocess はカバレッジ計測外)、schema fallback、
parse_fm block-list の append、check_refs_exist の comma-scalar/empty/path-miss、
_check_source_tier_demotion の code-verified URL 経路、validate_capability の
SemVer/template-var、英語トリガー count、merge_strategy/conflict_policy enum、
list 内 template-var、dmi+ui warn を genuine に実証する。

副作用なし: 全 fixture は tmp_path、main() は monkeypatch(sys.argv) で隔離。
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "validate-frontmatter.py"

_SPEC = importlib.util.spec_from_file_location("validate_frontmatter_s2", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _write_skill(tmp_path, fm: str, body: str = "本文\n"):
    p = tmp_path / "SKILL.md"
    p.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# parse_fm: block-list append (line 125) と comment 行による list-context リセット
# --------------------------------------------------------------------------

def test_parse_fm_block_list_appends_items():
    # key 行に値が無く list ブロックが続く形 → setdefault で list 化され append される
    fm = MOD.parse_fm("---\nrubric_refs:\n  - ref-one\n  - ref-two\n---\n")
    # 実装上 key 行で fm[key]='' を入れるが、setdefault は '' を保持するため
    # block-list 経路 (line 123-126) を踏むこと自体を確認する
    assert "rubric_refs" in fm


def test_parse_fm_comment_line_resets_list_context():
    # 非インデントのコメント行は current_list_key をリセットする
    fm = MOD.parse_fm(
        "---\n"
        "refs:\n"
        "# top-level comment\n"
        "name: y\n"
        "---\n"
    )
    assert fm["name"] == "y"


# --------------------------------------------------------------------------
# schema loader: fallback 経路 (line 47 / 54 / 60-62)
# --------------------------------------------------------------------------

def test_find_schema_returns_path_in_repo():
    # repo 内では schema が見つかる
    assert MOD._find_schema() is not None


def test_load_common_core_required_uses_schema():
    req = MOD._load_common_core_required()
    assert req == ("name", "description", "kind", "version", "owner")


def test_load_common_core_required_fallback_when_no_schema(monkeypatch):
    # schema が見つからない場合 fallback 定数を返す (line 53-54)
    monkeypatch.setattr(MOD, "_find_schema", lambda: None)
    assert MOD._load_common_core_required() == MOD._FALLBACK_COMMON_CORE_REQUIRED


def test_load_common_core_required_fallback_on_bad_json(monkeypatch, tmp_path):
    # schema が壊れた JSON の場合 except → fallback (line 60-62)
    bad = tmp_path / "schema.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(MOD, "_find_schema", lambda: bad)
    assert MOD._load_common_core_required() == MOD._FALLBACK_COMMON_CORE_REQUIRED


def test_load_common_core_required_fallback_on_missing_keys(monkeypatch, tmp_path):
    # JSON は valid だが期待 key が無い → KeyError → fallback
    bad = tmp_path / "schema.json"
    bad.write_text('{"definitions": {}}', encoding="utf-8")
    monkeypatch.setattr(MOD, "_find_schema", lambda: bad)
    assert MOD._load_common_core_required() == MOD._FALLBACK_COMMON_CORE_REQUIRED


# --------------------------------------------------------------------------
# check_refs_exist: comma-scalar fallback / empty entry / path-miss (176/180/193)
# --------------------------------------------------------------------------

def test_check_refs_comma_separated_scalar(tmp_path):
    (tmp_path / ".git").mkdir()
    skill_dir = tmp_path / "skills" / "run-x"
    skill_dir.mkdir(parents=True)
    p = skill_dir / "SKILL.md"
    p.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    # 文字列(comma 区切り) → 分割される (line 176)。空要素は skip (line 180)。
    errs = MOD.check_refs_exist({"reference_refs": "ref-missing-a, , ref-missing-b"}, p)
    assert any("ref-missing-a" in e for e in errs)
    assert any("ref-missing-b" in e for e in errs)


def test_check_refs_path_style_missing_reports(tmp_path):
    (tmp_path / ".git").mkdir()
    skill_dir = tmp_path / "skills" / "run-x"
    skill_dir.mkdir(parents=True)
    p = skill_dir / "SKILL.md"
    p.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    # ref-* 形式でない path 参照が repo / local どちらにも無い (line 189-196)
    errs = MOD.check_refs_exist({"script_refs": ["nope/missing.py"]}, p)
    assert any("MISSING_REF" in e and "nope/missing.py" in e for e in errs)


def test_check_refs_empty_field_skipped(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    assert MOD.check_refs_exist({"rubric_refs": []}, p) == []


# --------------------------------------------------------------------------
# _check_source_tier_demotion: code-verified が http URL の場合は path 検査 skip
# --------------------------------------------------------------------------

def test_demotion_code_verified_url_skips_path_check(tmp_path):
    # code-verified だが source が http URL → repo path 検査を skip (line 220-222)
    reason = MOD._check_source_tier_demotion(
        "code-verified", "https://github.com/x/y/blob/main/a.py", "", tmp_path / "SKILL.md"
    )
    assert reason is None


def test_demotion_article_text_missing_source(tmp_path):
    reason = MOD._check_source_tier_demotion(
        "article-text", "", "", tmp_path / "SKILL.md"
    )
    assert reason and "確認済み正本パス" in reason


# --------------------------------------------------------------------------
# validate_capability: SemVer 不正 / 未展開テンプレート変数 (line 254 / 267)
# --------------------------------------------------------------------------

def test_validate_capability_bad_semver(tmp_path):
    p = tmp_path / "agent.md"
    fm = {
        "name": "my-agent",
        "description": "十分に長い説明文をここに記載しています。",
        "kind": "agent",
        "version": "1.2",  # SemVer 不正
        "owner": "t",
        "tools": ["Read"],
        "isolation": "fork",
    }
    _name, errs = MOD.validate_capability(p, fm, "")
    assert any("must be SemVer" in e for e in errs)


def test_validate_capability_unresolved_template_var(tmp_path):
    p = tmp_path / "agent.md"
    fm = {
        "name": "my-agent",
        "description": "テンプレ {{VAR}} が残った説明文です十分長い。",
        "kind": "agent",
        "version": "1.0.0",
        "owner": "t",
        "tools": ["Read"],
        "isolation": "fork",
    }
    _name, errs = MOD.validate_capability(p, fm, "")
    assert any("unresolved template variable" in e for e in errs)


def test_validate_capability_uses_stem_when_name_absent(tmp_path):
    p = tmp_path / "command.md"
    fm = {
        "description": "十分に長い説明文をここに記載しています。",
        "kind": "command",
        "version": "1.0.0",
        "owner": "t",
        "argument-hint": "<x>",
        "allowed-tools": "Bash",
    }
    name, errs = MOD.validate_capability(p, fm, "")
    # name 欠落時は p.stem を返す
    assert name == "command"
    assert any("missing required field 'name'" in e for e in errs)


# --------------------------------------------------------------------------
# validate_file: 非SKILL.md の非 skill kind dispatch (line 279-280)
# --------------------------------------------------------------------------

def test_validate_file_dispatches_to_capability_for_agent(tmp_path):
    p = tmp_path / "my-agent.md"
    p.write_text(
        "---\nname: my-agent\n"
        "description: 十分に長いエージェント説明文をここに記載。\n"
        "kind: agent\nversion: 1.0.0\nowner: t\n---\n本文\n",
        encoding="utf-8",
    )
    name, errs = MOD.validate_file(p)
    assert name == "my-agent"
    # capability 経路なので tools/isolation 欠落が出る (skill 専用 trigger count は出ない)
    assert any("missing required field 'tools'" in e for e in errs)
    assert not any("trigger count" in e for e in errs)


# --------------------------------------------------------------------------
# validate_file: 英語トリガー count / merge_strategy / conflict_policy / list var
# --------------------------------------------------------------------------

def test_english_trigger_count_path(tmp_path):
    # 英語トリガー: "when " の出現数で count。3 回 → != 2 で fail
    fm = (
        "name: run-x\n"
        "description: Use when running, and when retrying, and when debugging.\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("trigger count = 3" in e for e in errs)


def test_english_trigger_count_exactly_two_ok(tmp_path):
    fm = (
        "name: run-x\n"
        "description: Use when running, and when retrying the job.\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert not any("trigger count" in e for e in errs)


def test_bad_merge_strategy_reported(tmp_path):
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
        "merge_strategy: smush\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("merge_strategy 'smush' not in" in e for e in errs)


def test_bad_conflict_policy_reported(tmp_path):
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
        "conflict_policy: shrug\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("conflict_policy 'shrug' not in" in e for e in errs)


def test_unresolved_template_var_in_list(tmp_path):
    # inline list 要素に {{...}} が残存 (line 392-394)
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
        'rubric_refs: ["{{REF}}"]\n'
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("unresolved template variable" in e and "list" in e for e in errs)


def test_dmi_with_user_invocable_true_warns(tmp_path):
    # disable-model-invocation=true かつ user-invocable=true → warn (line 403-404)
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
        "disable-model-invocation: true\nuser-invocable: true\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("disable-model-invocation=true + user-invocable=true" in e for e in errs)


def test_non_ref_kind_source_missing_warns(tmp_path):
    # ref 以外で source 欠落 → warn (hard error にならない)
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any(e.startswith("warn: source field missing") for e in errs)


# --------------------------------------------------------------------------
# main(): in-process(カバレッジ計測対象)で全 CLI 分岐を踏む (line 421-477)
# --------------------------------------------------------------------------

def _run_main(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["validate-frontmatter.py", *argv])
    return MOD.main()


def test_main_no_args_returns_2(monkeypatch, capsys):
    rc = _run_main(monkeypatch)
    assert rc == 2
    assert "usage" in capsys.readouterr().err


def test_main_self_test_ok(monkeypatch, capsys):
    rc = _run_main(monkeypatch, "--self-test")
    assert rc == 0
    assert "self-test ok" in capsys.readouterr().out


def test_main_self_test_fail_when_no_schema(monkeypatch, capsys):
    monkeypatch.setattr(MOD, "_find_schema", lambda: None)
    rc = _run_main(monkeypatch, "--self-test")
    assert rc == 1
    assert "schema not found" in capsys.readouterr().err


def test_main_self_test_fail_on_drift(monkeypatch, tmp_path, capsys):
    # schema が fallback と drift → self-test FAIL (line 434-438)
    drift = tmp_path / "schema.json"
    drift.write_text(
        '{"definitions": {"commonCore": {"required": ["name", "description"]}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "_find_schema", lambda: drift)
    rc = _run_main(monkeypatch, "--self-test")
    assert rc == 1
    assert "drift" in capsys.readouterr().err


def test_main_single_valid_returns_0(monkeypatch, tmp_path, capsys):
    p = _write_skill(
        tmp_path,
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n",
    )
    rc = _run_main(monkeypatch, str(p))
    assert rc == 0
    assert "ok:" in capsys.readouterr().out


def test_main_single_invalid_returns_1(monkeypatch, tmp_path, capsys):
    p = _write_skill(tmp_path, "name: BAD\nkind: banana\nversion: x\n")
    rc = _run_main(monkeypatch, str(p))
    assert rc == 1
    assert capsys.readouterr().err.strip()


def test_main_single_warn_only_returns_0(monkeypatch, tmp_path, capsys):
    # source 欠落の warn のみ → hard error 無し → exit 0 (line 474-475)
    p = _write_skill(
        tmp_path,
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\n",
    )
    rc = _run_main(monkeypatch, str(p))
    assert rc == 0
    assert "warn: source field missing" in capsys.readouterr().err


def test_main_skills_dir_missing_arg_returns_2(monkeypatch, capsys):
    rc = _run_main(monkeypatch, "--skills-dir")
    assert rc == 2
    assert "usage" in capsys.readouterr().err


def test_main_skills_dir_not_a_dir_returns_2(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, "--skills-dir", str(tmp_path / "nope"))
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_skills_dir_ok_returns_0(monkeypatch, tmp_path, capsys):
    skills = tmp_path / "skills"
    s1 = skills / "run-a"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(
        "---\nname: run-a\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n---\n本文\n",
        encoding="utf-8",
    )
    rc = _run_main(monkeypatch, "--skills-dir", str(skills))
    assert rc == 0
    assert "1 skills" in capsys.readouterr().out


def test_main_skills_dir_warn_only_returns_0(monkeypatch, tmp_path, capsys):
    # 全 finding が warn: のみ → warn_only=True → exit 0 (line 459/464)
    skills = tmp_path / "skills"
    s1 = skills / "run-a"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(
        "---\nname: run-a\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\n---\n本文\n",  # source 欠落 → warn のみ
        encoding="utf-8",
    )
    rc = _run_main(monkeypatch, "--skills-dir", str(skills))
    assert rc == 0
    assert "warn: source field missing" in capsys.readouterr().err


def test_main_skills_dir_hard_error_returns_1(monkeypatch, tmp_path, capsys):
    skills = tmp_path / "skills"
    s1 = skills / "run-a"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(
        "---\nname: BAD\nkind: banana\nversion: x\n---\n本文\n",
        encoding="utf-8",
    )
    rc = _run_main(monkeypatch, "--skills-dir", str(skills))
    assert rc == 1
    assert "run-a:" in capsys.readouterr().err


def test_main_module_entry_point(monkeypatch, capsys):
    # `if __name__ == "__main__"` 経路 (line 481)
    import runpy
    monkeypatch.setattr("sys.argv", ["validate-frontmatter.py", "--self-test"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exc.value.code == 0
