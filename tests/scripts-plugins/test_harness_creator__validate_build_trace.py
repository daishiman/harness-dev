"""validate-build-trace.py の CapabilityManifest 検証経路を実入力で実証する。

既存 tests/test_validate_build_trace.py は _validate_feedback_contract と
--self-test を扱う。本ファイルはそれと重複しない以下の純関数 / CLI 経路を
genuine に検証する:

  - validate_manifest: kind 別 dispatch (skill/agent/hook/command/prompt/
    workflow/plugin-composition) の PASS/FAIL を実 dict で確認
  - _check_common_core: name/description/version/kind の形式検査
  - _has_cycle: DAG 循環検出の真偽
  - _load_frontmatter / _normalize_dates: frontmatter 抽出
  - main の CLI 契約: --manifest / --bundle / 後方互換 trace / 引数なし /
    不正 JSON / ファイル未存在 の returncode と stdout JSON

副作用なし (network/keychain 不使用)。tmp_path のみ書き込み。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "validate-build-trace.py"
)

_SPEC = importlib.util.spec_from_file_location("vbt_manifest_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# validate_manifest: kind 別 dispatch (純関数, 実 dict 入出力)
# --------------------------------------------------------------------------

def _common_core(**over):
    base = {
        "name": "run-sample",
        "description": "テスト用の発動条件宣言を含むサンプル manifest。",
        "kind": "skill",
        "version": "1.0.0",
        "owner": "team-test",
    }
    base.update(over)
    return base


def test_skill_manifest_valid_returns_no_findings():
    data = _common_core(triggers=["when sample runs"])
    valid, kind, findings = MOD.validate_manifest(data)
    assert valid is True
    assert kind == "skill"
    assert findings == []


def test_skill_manifest_missing_triggers_is_invalid():
    data = _common_core()  # triggers 欠落
    valid, kind, findings = MOD.validate_manifest(data)
    assert valid is False
    assert any("triggers" in f for f in findings)


def test_agent_manifest_missing_isolation_is_invalid():
    data = _common_core(kind="agent", tools=["Read"], phase="phase-1")
    valid, kind, findings = MOD.validate_manifest(data)
    assert valid is False
    assert any("isolation" in f for f in findings)


def test_agent_manifest_invalid_model_is_invalid():
    data = _common_core(
        kind="agent", tools=["Read"], phase="p1",
        isolation="fork", model="gpt4",
    )
    valid, _kind, findings = MOD.validate_manifest(data)
    assert valid is False
    assert any("model" in f and "gpt4" in f for f in findings)


def test_hook_manifest_bad_event_and_timeout():
    data = _common_core(kind="hook", event="NopeEvent", command="x", timeout_ms=99)
    valid, _kind, findings = MOD.validate_manifest(data)
    assert valid is False
    assert any("hook.event" in f for f in findings)
    assert any("timeout_ms" in f for f in findings)


def test_hook_manifest_valid():
    data = _common_core(kind="hook", event="PreToolUse", command="echo", timeout_ms=1000)
    valid, _kind, findings = MOD.validate_manifest(data)
    assert valid is True, findings


def test_prompt_manifest_requires_exactly_seven_layers():
    layers = [{"index": i, "title": f"L{i}"} for i in range(1, 7)]  # 6 のみ
    data = _common_core(kind="prompt", layers=layers)
    valid, _kind, findings = MOD.validate_manifest(data)
    assert valid is False
    assert any("exactly 7" in f for f in findings)


def test_prompt_manifest_seven_layers_valid():
    layers = [{"index": i, "title": f"L{i}"} for i in range(1, 8)]
    data = _common_core(kind="prompt", layers=layers)
    valid, _kind, findings = MOD.validate_manifest(data)
    assert valid is True, findings


def test_workflow_manifest_phase_without_agents_is_invalid():
    data = _common_core(kind="workflow", phases=[{"id": "p1"}])  # agents 欠落
    valid, _kind, findings = MOD.validate_manifest(data)
    assert valid is False
    assert any("agents" in f for f in findings)


def test_unknown_kind_is_reported():
    data = _common_core(kind="banana")
    valid, kind, findings = MOD.validate_manifest(data)
    # kind が enum 外なので commonCore でも検出される
    assert valid is False
    assert any("banana" in f for f in findings)


# --------------------------------------------------------------------------
# _check_common_core: 形式検査の単体実証
# --------------------------------------------------------------------------

def test_common_core_bad_name_and_version_and_desc():
    data = {
        "name": "Bad_Name",          # 大文字/アンダースコア不可
        "description": "short",       # 10 未満
        "kind": "skill",
        "version": "1.0",            # SemVer 非準拠
        "owner": "t",
    }
    findings = MOD._check_common_core(data)
    joined = " ".join(findings)
    assert "name=" in joined
    assert "version=" in joined
    assert "description length" in joined


def test_common_core_all_present_ok():
    assert MOD._check_common_core(_common_core()) == []


# --------------------------------------------------------------------------
# _has_cycle: DAG 循環検出
# --------------------------------------------------------------------------

def test_has_cycle_detects_back_edge():
    assert MOD._has_cycle({"a": ["b"], "b": ["a"]}) is True


def test_has_cycle_acyclic_is_false():
    assert MOD._has_cycle({"a": ["b"], "b": ["c"], "c": []}) is False


def test_plugin_composition_with_cycle_is_invalid():
    data = _common_core(
        kind="plugin-composition",
        capabilities=[{"kind": "skill", "ref": "skills/a"},
                      {"kind": "skill", "ref": "skills/b"}],
        dependencies=[{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    )
    valid, _kind, findings = MOD.validate_manifest(data)
    assert valid is False
    assert any("cycle" in f for f in findings)


# --------------------------------------------------------------------------
# _load_frontmatter / _normalize_dates
# --------------------------------------------------------------------------

def test_load_frontmatter_extracts_mapping():
    text = "---\nname: foo\nkind: skill\n---\nbody text\n"
    data, err = MOD._load_frontmatter(text)
    assert err == ""
    assert data["name"] == "foo"
    assert data["kind"] == "skill"


def test_load_frontmatter_missing_delimiter_errors():
    data, err = MOD._load_frontmatter("no frontmatter here")
    assert data is None
    assert "delimiter" in err


def test_normalize_dates_converts_date_to_iso():
    import datetime
    obj = {"d": datetime.date(2026, 6, 24), "nested": [datetime.date(2026, 1, 1)]}
    out = MOD._normalize_dates(obj)
    assert out["d"] == "2026-06-24"
    assert out["nested"][0] == "2026-01-01"


# --------------------------------------------------------------------------
# CLI 経路 (main): subprocess で returncode + stdout/stderr 契約
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


def test_cli_manifest_mode_valid_emits_json_exit0(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text(
        "---\nname: run-x\n"
        "description: 十分な長さの発動条件宣言を含むテスト manifest です。\n"
        "kind: skill\nversion: 1.0.0\nowner: team-test\n"
        "triggers:\n  - when x happens\n---\nbody\n",
        encoding="utf-8",
    )
    proc = _run("--manifest", str(md))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["valid"] is True
    assert out["kind"] == "skill"
    assert out["findings"] == []


def test_cli_manifest_mode_invalid_exit1(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text(
        "---\nname: BAD\nkind: skill\nversion: x\n---\nbody\n",
        encoding="utf-8",
    )
    proc = _run("--manifest", str(md))
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["valid"] is False
    assert out["findings"]


def test_cli_manifest_missing_file_exit1(tmp_path):
    proc = _run("--manifest", str(tmp_path / "nope.md"))
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["valid"] is False
    assert any("not found" in f for f in out["findings"])


def test_cli_manifest_wrong_argcount_exit2():
    proc = _run("--manifest")
    assert proc.returncode == 2


def test_cli_bundle_mode_reports_missing_ref(tmp_path):
    bundle = tmp_path / "plugin-composition.yaml"
    bundle.write_text(
        "name: bundle-x\n"
        "description: capabilities.ref の実在検査を行う bundle テストです。\n"
        "kind: plugin-composition\nversion: 0.0.1\nowner: team-test\n"
        "capabilities:\n"
        "  - kind: skill\n    ref: skills/does-not-exist\n",
        encoding="utf-8",
    )
    proc = _run("--bundle", str(bundle))
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert any("ref not found" in f for f in out["findings"])


def test_cli_backcompat_trace_missing_file_exit1(tmp_path):
    proc = _run(str(tmp_path / "skill-build-trace.json"))
    assert proc.returncode == 1
    assert "not found" in proc.stderr


def test_cli_backcompat_trace_empty_file_exit1(tmp_path):
    f = tmp_path / "trace.json"
    f.write_text("   \n", encoding="utf-8")
    proc = _run(str(f))
    assert proc.returncode == 1
    assert "empty" in proc.stderr


def test_cli_backcompat_trace_invalid_json_exit2(tmp_path):
    f = tmp_path / "trace.json"
    f.write_text("{not json", encoding="utf-8")
    proc = _run(str(f))
    assert proc.returncode == 2
    assert "invalid json" in proc.stderr


def test_cli_backcompat_trace_incomplete_is_validation_fail(tmp_path):
    # 有効 JSON だが必須 trace フィールドを欠くため exit 1 (validation failure)。
    f = tmp_path / "trace.json"
    f.write_text(json.dumps({"source_docs": []}), encoding="utf-8")
    proc = _run(str(f))
    assert proc.returncode == 1
    # source_docs 空 + 各種 missing が stderr に並ぶ
    assert "source_docs" in proc.stderr
    assert "missing design_model" in proc.stderr
