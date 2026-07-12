"""run-build-skill/scripts/lint-capability-manifest.py の genuine 機能テスト (scripts4)。

PostToolUse:Edit|Write hook。stdin {"tool_input": {"file_path": ...}} を読み、対象
(SKILL.md / plugin-composition.yaml / commands|agents の *.md)の YAML frontmatter を
CapabilityManifest schema(jsonschema 有り環境)または fallback で検証し、違反のみ
stderr へ JSON 出力。常に exit 0(非ブロック)。実通信・実 keychain なし。

純関数(_read_stdin_json / _is_target / _extract_frontmatter / _load_schema /
_fallback_check)を importlib でロードして実入力で assert。main は in-process
(monkeypatch sys.stdin = io.StringIO + capsys)で全分岐を踏み、subprocess でも
end-to-end の exit0/stderr を確認して `if __name__ == "__main__"` を踏む。

注: 別角度の同 script テストが tests/scripts3 にも在るため、本ファイルは名前衝突
回避で _r4 サフィックスを付し、scripts3 非依存で単独 >=80% 行カバレッジを満たす。

network: false, keychain: なし, 実 repo 書換: なし(tmp_path で隔離)。
"""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "lint-capability-manifest.py"
)

_SPEC = importlib.util.spec_from_file_location("lint_cap_manifest_uut_r4", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


VALID_SKILL_FM = (
    "---\n"
    "name: run-thing\n"
    "description: 発動条件を十分な長さで宣言する説明文\n"
    "kind: run\n"
    "version: 2.1.0\n"
    "owner: team-skills\n"
    "---\n"
    "# 本文\n"
)


def _run_main(monkeypatch, payload):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(json.dumps(payload)))
    return MOD.main()


def _stderr(capsys):
    return capsys.readouterr().err


def _write(tmp_path, content, name="SKILL.md"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ── _read_stdin_json ─────────────────────────────────────────────────────────
def test_read_stdin_json_object(monkeypatch):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO('{"tool_input": {"file_path": "x"}}'))
    assert MOD._read_stdin_json() == {"tool_input": {"file_path": "x"}}


def test_read_stdin_json_blank_to_empty(monkeypatch):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO("\n\t  "))
    assert MOD._read_stdin_json() == {}


def test_read_stdin_json_malformed_to_empty(monkeypatch):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO("not json at all"))
    assert MOD._read_stdin_json() == {}


# ── _is_target ───────────────────────────────────────────────────────────────
def test_is_target_skill_md_anywhere():
    assert MOD._is_target(Path("/a/b/skills/x/SKILL.md")) is True


def test_is_target_composition_yaml():
    assert MOD._is_target(Path("/a/plugin-composition.yaml")) is True


def test_is_target_command_md_case_insensitive_dir():
    assert MOD._is_target(Path("/p/Commands/run.md")) is True


def test_is_target_agent_md():
    assert MOD._is_target(Path("/p/agents/eval.md")) is True


def test_is_target_other_md_rejected():
    assert MOD._is_target(Path("/p/notes/x.md")) is False


def test_is_target_yaml_other_name_rejected():
    assert MOD._is_target(Path("/p/config.yaml")) is False


# ── _extract_frontmatter ─────────────────────────────────────────────────────
def test_extract_frontmatter_absent_returns_none():
    assert MOD._extract_frontmatter("# heading only") is None


def test_extract_frontmatter_parses_kv():
    fm = MOD._extract_frontmatter("---\nname: a\nkind: run\n---\nbody")
    assert fm == {"name": "a", "kind": "run"}


def test_extract_frontmatter_strips_double_and_single_quotes():
    fm = MOD._extract_frontmatter('---\nname: "x"\ndescription: \'y\'\n---\n')
    assert fm["name"] == "x" and fm["description"] == "y"


def test_extract_frontmatter_skips_comments_blank_nested_and_noColon():
    txt = (
        "---\n"
        "name: top\n"
        "# comment line\n"
        "\n"
        "tags:\n"
        "  - one\n"  # indented list -> skipped
        "barekey\n"  # no colon -> skipped
        "---\n"
    )
    fm = MOD._extract_frontmatter(txt)
    assert fm == {"name": "top", "tags": ""}


def test_extract_frontmatter_trailing_whitespace_trimmed():
    fm = MOD._extract_frontmatter("---\nname: val   \n---\n")
    assert fm["name"] == "val"


# ── _load_schema ─────────────────────────────────────────────────────────────
def test_load_schema_real_returns_capability_manifest():
    s = MOD._load_schema()
    assert isinstance(s, dict) and s["title"] == "CapabilityManifest"


def test_load_schema_absent_path_none(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "SCHEMA_PATH", tmp_path / "absent.json")
    assert MOD._load_schema() is None


def test_load_schema_corrupt_none(monkeypatch, tmp_path):
    bad = tmp_path / "s.json"
    bad.write_text("{bad", encoding="utf-8")
    monkeypatch.setattr(MOD, "SCHEMA_PATH", bad)
    assert MOD._load_schema() is None


# ── _fallback_check ──────────────────────────────────────────────────────────
def test_fallback_check_ok():
    assert MOD._fallback_check({"name": "n", "description": "d"}) == []


def test_fallback_check_flags_missing_description():
    assert MOD._fallback_check({"name": "n"}) == ["missing required key: description"]


def test_fallback_check_empty_string_is_missing():
    errs = MOD._fallback_check({"name": "", "description": ""})
    assert errs == [
        "missing required key: name",
        "missing required key: description",
    ]


# ── main: 早期 return 経路(stderr 無出力)─────────────────────────────────────
def test_main_empty_path_returns0(monkeypatch, capsys):
    assert _run_main(monkeypatch, {"tool_input": {"file_path": ""}}) == 0
    assert _stderr(capsys) == ""


def test_main_missing_tool_input_returns0(monkeypatch, capsys):
    assert _run_main(monkeypatch, {"unrelated": 1}) == 0
    assert _stderr(capsys) == ""


def test_main_nontarget_file_returns0(monkeypatch, capsys, tmp_path):
    p = _write(tmp_path, VALID_SKILL_FM, name="README.md")
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    assert _stderr(capsys) == ""


def test_main_target_not_existing_returns0(monkeypatch, capsys, tmp_path):
    p = str(tmp_path / "SKILL.md")
    assert _run_main(monkeypatch, {"tool_input": {"file_path": p}}) == 0
    assert _stderr(capsys) == ""


# ── main: frontmatter 無し ───────────────────────────────────────────────────
def test_main_no_frontmatter_reports_error(monkeypatch, capsys, tmp_path):
    p = _write(tmp_path, "no frontmatter here\n")
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    err = json.loads(_stderr(capsys))
    assert err["error"] == "frontmatter not found"
    assert err["hook"] == "lint-capability-manifest"


# ── main: jsonschema 経路(合格/各違反/validator 例外)──────────────────────────
def test_main_valid_no_stderr(monkeypatch, capsys, tmp_path):
    assert MOD.HAS_JSONSCHEMA
    p = _write(tmp_path, VALID_SKILL_FM)
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    assert _stderr(capsys) == ""


def test_main_missing_owner_required_violation(monkeypatch, capsys, tmp_path):
    fm = (
        "---\n"
        "name: run-thing\n"
        "description: 発動条件を十分な長さで宣言する説明文\n"
        "kind: run\n"
        "version: 1.0.0\n"  # owner 欠落
        "---\n"
    )
    p = _write(tmp_path, fm)
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    err = json.loads(_stderr(capsys))
    assert err["schema_used"] is True
    assert any("owner" in e for e in err["errors"])


def test_main_description_too_short_violation(monkeypatch, capsys, tmp_path):
    fm = (
        "---\n"
        "name: run-thing\n"
        "description: 短い\n"  # minLength 10 未満
        "kind: run\n"
        "version: 1.0.0\n"
        "owner: team-x\n"
        "---\n"
    )
    p = _write(tmp_path, fm)
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    err = json.loads(_stderr(capsys))
    assert err["errors"]


def test_main_bad_name_pattern_violation(monkeypatch, capsys, tmp_path):
    fm = (
        "---\n"
        "name: Run_Thing\n"  # 大文字/アンダースコア → pattern 違反
        "description: 発動条件を十分な長さで宣言する説明文\n"
        "kind: run\n"
        "version: 1.0.0\n"
        "owner: team-x\n"
        "---\n"
    )
    p = _write(tmp_path, fm)
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    err = json.loads(_stderr(capsys))
    assert err["errors"]


def test_main_validator_unexpected_exception_path(monkeypatch, capsys, tmp_path):
    # validate が ValidationError 以外を投げる経路(不正な schema 型)
    monkeypatch.setattr(
        MOD, "_load_schema", lambda: {"type": "object", "properties": {"name": {"type": 99}}}
    )
    p = _write(tmp_path, VALID_SKILL_FM)
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    err = json.loads(_stderr(capsys))
    assert any("validator error" in e for e in err["errors"])


# ── main: fallback 経路(jsonschema 無し / schema None)─────────────────────────
def test_main_fallback_missing_name_detected(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(MOD, "HAS_JSONSCHEMA", False)
    p = _write(tmp_path, "---\ndescription: 説明だけ\nkind: run\n---\n")
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    err = json.loads(_stderr(capsys))
    assert "missing required key: name" in err["errors"]
    assert err["schema_used"] is False


def test_main_fallback_schema_none_passes_when_keys_present(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(MOD, "_load_schema", lambda: None)
    p = _write(tmp_path, "---\nname: x\ndescription: 説明テキスト\n---\n")
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    assert _stderr(capsys) == ""


# ── main: トップレベル例外握り潰し ──────────────────────────────────────────
def test_main_top_level_exception_swallowed(monkeypatch, capsys, tmp_path):
    def _boom(_):
        raise RuntimeError("boom")

    monkeypatch.setattr(MOD, "_extract_frontmatter", _boom)
    p = _write(tmp_path, VALID_SKILL_FM)
    assert _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}}) == 0
    assert _stderr(capsys) == ""


# ── subprocess end-to-end(__main__ ガードを踏む)────────────────────────────
def _run_cli(payload, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload) if stdin is None else stdin,
        text=True,
        capture_output=True,
    )


def test_subprocess_valid_exit0_clean(tmp_path):
    p = _write(tmp_path, VALID_SKILL_FM)
    res = _run_cli({"tool_input": {"file_path": str(p)}})
    assert res.returncode == 0 and res.stderr.strip() == ""


def test_subprocess_violation_exit0_with_errors(tmp_path):
    fm = (
        "---\n"
        "name: run-thing\n"
        "description: 発動条件を十分な長さで宣言する説明文\n"
        "version: 1.0.0\n"
        "owner: team-x\n"  # kind 欠落
        "---\n"
    )
    p = _write(tmp_path, fm)
    res = _run_cli({"tool_input": {"file_path": str(p)}})
    assert res.returncode == 0
    assert json.loads(res.stderr)["errors"]


def test_subprocess_empty_stdin_exit0(tmp_path):
    res = _run_cli({}, stdin="")
    assert res.returncode == 0 and res.stderr.strip() == ""
