"""validate-frontmatter.py の frontmatter パーサと検証規則を実入力で実証する。

genuine な検証対象 (network 不使用, tmp_path のみ):
  - parse_fm: scalar / inline list / `- ` ブロックリスト / コメント除去
  - validate_file: commonCore 必須 / SemVer / トリガー句 / trigger count==2 /
    kind enum / effect enum / source-tier / assign-* 規則
  - validate_capability: 非 skill kind (agent/hook/...) の commonCore + kind 固有
  - _check_source_tier_demotion: external-spec URL / code-verified path / 監査経過
  - check_refs_exist: ref-* / path 参照の実在検査
  - main の CLI: --self-test / --skills-dir / 単一ファイル / 引数なし
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "validate-frontmatter.py"

_SPEC = importlib.util.spec_from_file_location("validate_frontmatter_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# parse_fm
# --------------------------------------------------------------------------

def test_parse_fm_scalars_and_comment_strip():
    fm = MOD.parse_fm("---\nname: foo\nkind: run  # trailing comment\n---\nbody\n")
    assert fm["name"] == "foo"
    assert fm["kind"] == "run"  # コメント部分は除去される


def test_parse_fm_inline_list():
    fm = MOD.parse_fm('---\nrubric_refs: ["a", "b"]\n---\n')
    assert fm["rubric_refs"] == ["a", "b"]


def test_parse_fm_block_list_quirk_yields_empty_scalar():
    # 実挙動の固定: key 行で fm[key]='' を先に設定するため、後続 `- item` の
    # setdefault が既存 '' と衝突し list 化されない (block list は空スカラに潰れる)。
    # inline list 形式のみが list を生む。この quirk を回帰として記録する。
    fm = MOD.parse_fm("---\nrubric_refs:\n  - ref-one\n  - ref-two\n---\n")
    assert fm["rubric_refs"] == ""


def test_parse_fm_no_frontmatter_returns_empty():
    assert MOD.parse_fm("just body, no fm") == {}
    assert MOD.parse_fm("---\nname: x\n") == {}  # closing --- 欠落


# --------------------------------------------------------------------------
# validate_file: SKILL.md 規則 (tmp_path に実ファイルを書いて検査)
# --------------------------------------------------------------------------

def _write_skill(tmp_path, body_fm: str, body: str = "本文\n"):
    p = tmp_path / "SKILL.md"
    p.write_text(f"---\n{body_fm}\n---\n{body}", encoding="utf-8")
    return p


def test_valid_run_skill_has_no_hard_errors(tmp_path):
    fm = (
        "name: run-sample\n"
        "description: サンプルを実行するとき、または再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: team-test\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    name, errs = MOD.validate_file(p)
    hard = [e for e in errs if not e.startswith("warn:")]
    assert name == "run-sample"
    assert hard == [], hard


def test_missing_common_core_reported(tmp_path):
    p = _write_skill(tmp_path, "name: run-x\nkind: run\n")
    _name, errs = MOD.validate_file(p)
    assert any("missing required field: description" in e for e in errs)
    assert any("missing required field: version" in e for e in errs)
    assert any("missing required field: owner" in e for e in errs)


def test_bad_semver_reported(tmp_path):
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.2\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("must be SemVer" in e for e in errs)


def test_trigger_count_must_be_two(tmp_path):
    # トリガー句が 1 つだけ → count != 2
    fm = (
        "name: run-x\n"
        "description: これは実行するときに使う説明です。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("trigger count = 1" in e for e in errs)


def test_missing_trigger_phrase_reported(tmp_path):
    fm = (
        "name: run-x\n"
        "description: トリガー句を一切含まない平易な説明文。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("trigger phrase" in e for e in errs)


def test_bad_kind_enum_reported(tmp_path):
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: banana\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("kind 'banana' not in" in e for e in errs)


def test_bad_effect_enum_reported(tmp_path):
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\neffect: explode\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("effect 'explode' not in" in e for e in errs)


def test_ref_kind_requires_source_and_tier(tmp_path):
    fm = (
        "name: ref-x\n"
        "description: 参照するとき、または読む場合に使う。\n"
        "kind: ref\nversion: 1.0.0\nowner: t\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("kind=ref: source" in e for e in errs)
    assert any("kind=ref: source-tier" in e for e in errs)


def test_bad_source_tier_value_reported(tmp_path):
    fm = (
        "name: ref-x\n"
        "description: 参照するとき、また読む場合に使う。\n"
        "kind: ref\nversion: 1.0.0\nowner: t\n"
        "source: https://example.com/spec\nsource-tier: bogus-tier\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("source-tier 'bogus-tier' not in" in e for e in errs)


def test_bad_last_audited_format(tmp_path):
    fm = (
        "name: ref-x\n"
        "description: 参照するとき、また読む場合に使う。\n"
        "kind: ref\nversion: 1.0.0\nowner: t\n"
        "source: https://example.com/spec\nsource-tier: external-spec\n"
        "last-audited: 2026/06/24\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("must be ISO date" in e for e in errs)


def test_assign_skill_requires_fork_context(tmp_path):
    # assign-* は context: fork と user-invocable: false が必須
    fm = (
        "name: assign-x\n"
        "description: 評価を割り当てるとき、また再評価する場合に使う。\n"
        "kind: assign\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("requires context: fork" in e for e in errs)
    assert any("requires user-invocable: false" in e for e in errs)


def test_unresolved_template_variable_reported(tmp_path):
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に {{PLACEHOLDER}} で使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
    )
    p = _write_skill(tmp_path, fm)
    _name, errs = MOD.validate_file(p)
    assert any("unresolved template variable" in e for e in errs)


def test_cross_platform_requires_os_branch(tmp_path):
    fm = (
        "name: run-x\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n"
        "cross_platform: true\n"
    )
    p = _write_skill(tmp_path, fm, body="OS 分岐タグの無い本文\n")
    _name, errs = MOD.validate_file(p)
    assert any("cross_platform=true requires" in e for e in errs)


def test_validate_file_not_found(tmp_path):
    name, errs = MOD.validate_file(tmp_path / "missing" / "SKILL.md")
    assert any("not found" in e for e in errs)


# --------------------------------------------------------------------------
# validate_capability: 非 skill kind
# --------------------------------------------------------------------------

def test_validate_capability_agent_missing_kind_specific(tmp_path):
    p = tmp_path / "agent.md"
    fm = {
        "name": "my-agent",
        "description": "テスト用エージェント定義です十分長い説明文。",
        "kind": "agent",
        "version": "1.0.0",
        "owner": "team-test",
        # tools / isolation 欠落
    }
    name, errs = MOD.validate_capability(p, fm, "")
    assert name == "my-agent"
    assert any("missing required field 'tools'" in e for e in errs)
    assert any("missing required field 'isolation'" in e for e in errs)


def test_validate_capability_hook_valid(tmp_path):
    p = tmp_path / "hook.md"
    fm = {
        "name": "my-hook",
        "description": "テスト用フック定義の十分に長い説明文です。",
        "kind": "hook",
        "version": "0.1.0",
        "owner": "team-test",
        "event": "PreToolUse",
        "command": "echo hi",
    }
    _name, errs = MOD.validate_capability(p, fm, "")
    assert errs == [], errs


def test_validate_capability_bad_name_kebab(tmp_path):
    p = tmp_path / "agent.md"
    fm = {
        "name": "Bad Name",
        "description": "十分に長い説明文をここに記載しています。",
        "kind": "agent",
        "version": "1.0.0",
        "owner": "t",
        "tools": ["Read"],
        "isolation": "fork",
    }
    _name, errs = MOD.validate_capability(p, fm, "")
    assert any("must be kebab-case" in e for e in errs)


# --------------------------------------------------------------------------
# _check_source_tier_demotion
# --------------------------------------------------------------------------

def test_demotion_external_spec_requires_url(tmp_path):
    reason = MOD._check_source_tier_demotion(
        "external-spec", "doc/local-path.md", "", tmp_path / "SKILL.md"
    )
    assert reason and "http(s) URL" in reason


def test_demotion_external_spec_url_ok(tmp_path):
    reason = MOD._check_source_tier_demotion(
        "external-spec", "https://claude.com/docs", "", tmp_path / "SKILL.md"
    )
    assert reason is None


def test_demotion_code_verified_missing_path(tmp_path):
    reason = MOD._check_source_tier_demotion(
        "code-verified", "nonexistent/path.py", "", tmp_path / "SKILL.md"
    )
    assert reason and "source path not found" in reason


def test_demotion_old_audit_flagged(tmp_path):
    reason = MOD._check_source_tier_demotion(
        "external-spec", "https://x.com", "2000-01-01", tmp_path / "SKILL.md"
    )
    assert reason and "days old" in reason


def test_demotion_none_for_empty_tier(tmp_path):
    assert MOD._check_source_tier_demotion("", "", "", tmp_path / "SKILL.md") is None


# --------------------------------------------------------------------------
# check_refs_exist
# --------------------------------------------------------------------------

def test_check_refs_missing_ref_style(tmp_path):
    # repo root に .git を作り、存在しない ref-* を参照
    (tmp_path / ".git").mkdir()
    skill_dir = tmp_path / "plugins" / "p" / "skills" / "run-x"
    skill_dir.mkdir(parents=True)
    p = skill_dir / "SKILL.md"
    p.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    errs = MOD.check_refs_exist({"reference_refs": ["ref-nonexistent"]}, p)
    assert any("MISSING_REF" in e and "ref-nonexistent" in e for e in errs)


def test_check_refs_existing_path_ok(tmp_path):
    (tmp_path / ".git").mkdir()
    skill_dir = tmp_path / "skills" / "run-x"
    skill_dir.mkdir(parents=True)
    p = skill_dir / "SKILL.md"
    p.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    target = tmp_path / "shared" / "thing.md"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    errs = MOD.check_refs_exist({"script_refs": ["shared/thing.md"]}, p)
    assert errs == []


# --------------------------------------------------------------------------
# CLI 経路 (subprocess)
# --------------------------------------------------------------------------

def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_no_args_usage_exit2():
    proc = _run()
    assert proc.returncode == 2
    assert "usage" in proc.stderr


def test_cli_self_test_passes():
    proc = _run("--self-test")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "self-test ok" in proc.stdout


def test_cli_single_valid_skill_exit0(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: run-sample\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n---\n本文\n",
        encoding="utf-8",
    )
    proc = _run(str(p))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok:" in proc.stdout


def test_cli_single_invalid_skill_exit1(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: BAD\nkind: banana\nversion: x\n---\n本文\n",
        encoding="utf-8",
    )
    proc = _run(str(p))
    assert proc.returncode == 1
    assert proc.stderr.strip()


def test_cli_skills_dir_scans_and_passes(tmp_path):
    skills = tmp_path / "skills"
    s1 = skills / "run-a"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(
        "---\nname: run-a\n"
        "description: 実行するとき、また再実行する場合に使う。\n"
        "kind: run\nversion: 1.0.0\nowner: t\nsource: doc/x.md\n---\n本文\n",
        encoding="utf-8",
    )
    proc = _run("--skills-dir", str(skills))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 skills" in proc.stdout


def test_cli_skills_dir_not_a_directory_exit2(tmp_path):
    proc = _run("--skills-dir", str(tmp_path / "nope"))
    assert proc.returncode == 2
    assert "not a directory" in proc.stderr
