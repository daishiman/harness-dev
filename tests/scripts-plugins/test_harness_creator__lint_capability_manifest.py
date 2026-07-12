"""run-build-skill/scripts/lint-capability-manifest.py の genuine 機能テスト。

PostToolUse:Edit|Write hook。stdin の {"tool_input": {"file_path": ...}} を読み、
対象ファイル(SKILL.md / plugin-composition.yaml / commands|agents の *.md)の
YAML frontmatter を CapabilityManifest schema で検証し、違反のみ stderr へ JSON 出力。
常に exit 0(非ブロック)。実通信・実 keychain なし。tmp_path で repo 非汚染。

純関数を実ファイルから importlib でロードして実入力で assert。main は
in-process(monkeypatch sys.stdin/io.StringIO + capsys)で全分岐を踏み、
さらに subprocess(sys.executable)で end-to-end の exit code/stderr も確認。

カバー分岐:
- _read_stdin_json: 正常 JSON / 空入力 → {} / 不正 JSON → {}(例外握り潰し)
- _is_target: SKILL.md / plugin-composition.yaml / commands・agents の .md /
  非対象 .md / 非 .md 拡張子
- _extract_frontmatter: frontmatter なし → None / 正常抽出 / quote 除去 /
  コメント・空行・ネスト/リスト行の無視 / 末尾空白除去
- _load_schema: 実在 schema ロード / 不在 → None / 例外 → None
- _fallback_check: name/description 欠落検出 / 充足 → []
- main:
  * file_path 空 → 早期 return 0(stderr 無)
  * 非対象/不存在ファイル → return 0(stderr 無)
  * frontmatter なし → "frontmatter not found" stderr / return 0
  * jsonschema 経路: 合格(stderr 無) / 違反(errors stderr, schema_used true)
  * validator 例外経路(schema 破損で validate が ValidationError 以外を投げる)
  * fallback 経路(HAS_JSONSCHEMA=False / schema=None): name 欠落検出
  * トップレベル例外握り潰し(read_text 失敗)→ return 0

network: false, keychain: なし, 実 repo 書換: なし。
"""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "lint-capability-manifest.py"
)

SPEC = importlib.util.spec_from_file_location("lint_capability_manifest_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


VALID_FM = (
    "---\n"
    "name: run-foo\n"
    "description: 十分に長い説明文(10文字以上)です\n"
    "kind: run\n"
    "version: 1.0.0\n"
    "owner: team-x\n"
    "---\n"
    "# 本文\n"
)


# ── _read_stdin_json ─────────────────────────────────────────────────────────
def test_read_stdin_json_valid(monkeypatch):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO('{"a": 1}'))
    assert MOD._read_stdin_json() == {"a": 1}


def test_read_stdin_json_empty_returns_empty(monkeypatch):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO("   \n"))
    assert MOD._read_stdin_json() == {}


def test_read_stdin_json_invalid_returns_empty(monkeypatch):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO("{ not json"))
    assert MOD._read_stdin_json() == {}


# ── _is_target ───────────────────────────────────────────────────────────────
def test_is_target_skill_md():
    assert MOD._is_target(Path("/x/skills/foo/SKILL.md")) is True


def test_is_target_plugin_composition_yaml():
    assert MOD._is_target(Path("/x/plugin-composition.yaml")) is True


def test_is_target_commands_md():
    assert MOD._is_target(Path("/p/commands/do.md")) is True


def test_is_target_agents_md():
    assert MOD._is_target(Path("/p/agents/eval.md")) is True


def test_is_target_plain_md_not_in_commands_or_agents():
    assert MOD._is_target(Path("/p/docs/readme.md")) is False


def test_is_target_non_md_extension():
    assert MOD._is_target(Path("/p/commands/do.txt")) is False


# ── _extract_frontmatter ─────────────────────────────────────────────────────
def test_extract_frontmatter_none_when_absent():
    assert MOD._extract_frontmatter("本文のみで frontmatter 無し") is None


def test_extract_frontmatter_basic():
    fm = MOD._extract_frontmatter("---\nname: foo\ndescription: bar\n---\nbody")
    assert fm == {"name": "foo", "description": "bar"}


def test_extract_frontmatter_strips_quotes_and_skips_noise():
    txt = (
        "---\n"
        'name: "quoted-name"\n'
        "# これはコメント\n"
        "\n"
        "description: 'single'\n"
        "tags:\n"
        "  - a\n"  # リスト行(先頭空白)は無視
        "nested: top\n"
        "  indented: y\n"  # ネスト行(先頭空白)は無視
        "noColonLine\n"  # ':' 無し行は無視
        "---\n"
        "body\n"
    )
    fm = MOD._extract_frontmatter(txt)
    assert fm["name"] == "quoted-name"
    assert fm["description"] == "single"
    assert fm["nested"] == "top"
    assert fm["tags"] == ""  # 空値はそのまま空文字
    assert "indented" not in fm
    assert "noColonLine" not in fm


# ── _load_schema ─────────────────────────────────────────────────────────────
def test_load_schema_real_file_returns_dict():
    schema = MOD._load_schema()
    assert isinstance(schema, dict)
    assert schema.get("title") == "CapabilityManifest"


def test_load_schema_missing_path_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "SCHEMA_PATH", tmp_path / "nope.json")
    assert MOD._load_schema() is None


def test_load_schema_corrupt_returns_none(monkeypatch, tmp_path):
    bad = tmp_path / "schema.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(MOD, "SCHEMA_PATH", bad)
    assert MOD._load_schema() is None


# ── _fallback_check ──────────────────────────────────────────────────────────
def test_fallback_check_all_present():
    assert MOD._fallback_check({"name": "x", "description": "y"}) == []


def test_fallback_check_missing_name():
    errs = MOD._fallback_check({"description": "y"})
    assert errs == ["missing required key: name"]


def test_fallback_check_missing_both():
    errs = MOD._fallback_check({})
    assert "missing required key: name" in errs
    assert "missing required key: description" in errs


def test_fallback_check_empty_value_counts_as_missing():
    errs = MOD._fallback_check({"name": "", "description": "ok"})
    assert errs == ["missing required key: name"]


# ── main: in-process helpers ─────────────────────────────────────────────────
def _run_main(monkeypatch, payload):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(json.dumps(payload)))
    return MOD.main()


def _stderr(capsys):
    return capsys.readouterr().err


def _write_target(tmp_path, content, name="SKILL.md"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ── main: 早期 return 経路 ───────────────────────────────────────────────────
def test_main_empty_file_path_returns_0_no_output(monkeypatch, capsys):
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": ""}})
    assert rc == 0
    assert _stderr(capsys) == ""


def test_main_no_tool_input_returns_0(monkeypatch, capsys):
    rc = _run_main(monkeypatch, {})
    assert rc == 0
    assert _stderr(capsys) == ""


def test_main_non_target_file_returns_0(monkeypatch, capsys, tmp_path):
    p = _write_target(tmp_path, VALID_FM, name="README.md")  # 非対象
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    assert _stderr(capsys) == ""


def test_main_nonexistent_target_returns_0(monkeypatch, capsys, tmp_path):
    p = str(tmp_path / "SKILL.md")  # 対象名だが存在しない
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": p}})
    assert rc == 0
    assert _stderr(capsys) == ""


# ── main: frontmatter 無し ───────────────────────────────────────────────────
def test_main_no_frontmatter_emits_error(monkeypatch, capsys, tmp_path):
    p = _write_target(tmp_path, "frontmatter 無しの本文\n")
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    err = json.loads(_stderr(capsys))
    assert err["hook"] == "lint-capability-manifest"
    assert err["error"] == "frontmatter not found"
    assert err["file"] == str(p)


# ── main: jsonschema 合格/違反 ───────────────────────────────────────────────
def test_main_valid_frontmatter_no_errors(monkeypatch, capsys, tmp_path):
    assert MOD.HAS_JSONSCHEMA, "このテストは jsonschema 有り環境を前提"
    p = _write_target(tmp_path, VALID_FM)
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    assert _stderr(capsys) == ""  # 合格時は無出力


def test_main_schema_violation_missing_kind(monkeypatch, capsys, tmp_path):
    assert MOD.HAS_JSONSCHEMA
    fm = (
        "---\n"
        "name: run-foo\n"
        "description: 十分に長い説明文です(10文字以上)\n"
        "version: 1.0.0\n"
        "owner: team-x\n"  # kind 欠落 → required 違反
        "---\n"
    )
    p = _write_target(tmp_path, fm)
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    err = json.loads(_stderr(capsys))
    assert err["hook"] == "lint-capability-manifest"
    assert err["schema_used"] is True
    assert any("kind" in e for e in err["errors"])


def test_main_schema_violation_bad_version_pattern(monkeypatch, capsys, tmp_path):
    fm = (
        "---\n"
        "name: run-foo\n"
        "description: 十分に長い説明文です(10文字以上)\n"
        "kind: run\n"
        "version: 1.0\n"  # SemVer パターン違反
        "owner: team-x\n"
        "---\n"
    )
    p = _write_target(tmp_path, fm)
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    err = json.loads(_stderr(capsys))
    assert err["errors"]
    assert any("1.0" in e or "match" in e for e in err["errors"])


def test_main_validator_unexpected_error_path(monkeypatch, capsys, tmp_path):
    # jsonschema.validate が ValidationError 以外を投げる経路を踏む。
    # _load_schema を不正スキーマ(参照不能 $ref)に差し替え、validate 内部で
    # ValidationError 以外の例外を誘発する。
    def _broken_schema():
        return {"type": "object", "properties": {"name": {"type": 12345}}}

    monkeypatch.setattr(MOD, "_load_schema", _broken_schema)
    p = _write_target(tmp_path, VALID_FM)
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    err = json.loads(_stderr(capsys))
    assert any("validator error" in e for e in err["errors"])


# ── main: fallback 経路(jsonschema 無し / schema None) ───────────────────────
def test_main_fallback_when_no_jsonschema_detects_missing_name(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(MOD, "HAS_JSONSCHEMA", False)
    fm = "---\ndescription: 説明あり\nkind: run\n---\n"  # name 欠落
    p = _write_target(tmp_path, fm)
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    err = json.loads(_stderr(capsys))
    assert "missing required key: name" in err["errors"]
    assert err["schema_used"] is False


def test_main_fallback_when_schema_none_passes_with_required_keys(
    monkeypatch, capsys, tmp_path
):
    # schema=None でも fallback で name/description 充足なら無出力
    monkeypatch.setattr(MOD, "_load_schema", lambda: None)
    fm = "---\nname: run-foo\ndescription: 説明あり\nkind: run\n---\n"
    p = _write_target(tmp_path, fm)
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    assert _stderr(capsys) == ""


def test_main_top_level_exception_swallowed(monkeypatch, capsys, tmp_path):
    # _is_target が例外を投げてもトップレベル try/except で握り潰し return 0。
    def _boom(_path):
        raise RuntimeError("boom")

    monkeypatch.setattr(MOD, "_is_target", _boom)
    p = _write_target(tmp_path, VALID_FM)
    rc = _run_main(monkeypatch, {"tool_input": {"file_path": str(p)}})
    assert rc == 0
    assert _stderr(capsys) == ""


# ── main: subprocess end-to-end ──────────────────────────────────────────────
def _run_subprocess(payload):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )


def test_subprocess_valid_exit0_no_stderr(tmp_path):
    p = _write_target(tmp_path, VALID_FM)
    res = _run_subprocess({"tool_input": {"file_path": str(p)}})
    assert res.returncode == 0
    assert res.stderr.strip() == ""


def test_subprocess_violation_exit0_with_stderr(tmp_path):
    fm = (
        "---\n"
        "name: run-foo\n"
        "description: 十分に長い説明文です(10文字以上)\n"
        "version: 1.0.0\n"
        "owner: team-x\n"  # kind 欠落
        "---\n"
    )
    p = _write_target(tmp_path, fm)
    res = _run_subprocess({"tool_input": {"file_path": str(p)}})
    assert res.returncode == 0  # 非ブロック
    err = json.loads(res.stderr)
    assert any("kind" in e for e in err["errors"])


def test_subprocess_empty_stdin_exit0(tmp_path):
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="",
        text=True,
        capture_output=True,
    )
    assert res.returncode == 0
    assert res.stderr.strip() == ""
