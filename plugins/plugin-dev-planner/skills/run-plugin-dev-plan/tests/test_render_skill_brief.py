"""render-skill-brief.py の機能テスト (島B (iv): inventory→skill-brief の決定論射影器)。

golden 実データに対する round-trip (射影出力の実 schema 突合) は
test_minimal_omission_and_roundtrip.py が担う。本テストは射影ロジック単体
(planner キー除去 / skill_kind→kind 写像 / 非 skill 拒否 / schema 突合検査器) と
CLI 契約 (exit code・--self-test) を縛る。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import component_entry, write_inventory

_SKILL_DIR = Path(__file__).resolve().parents[1]
_SCRIPT = _SKILL_DIR / "scripts" / "render-skill-brief.py"
_GOLDEN_INVENTORY = _SKILL_DIR / "examples" / "sample-plan" / "component-inventory.json"


def _run(*args: str) -> subprocess.CompletedProcess:
    """CI と同じ skill dir cwd から subprocess 実行する。"""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        cwd=str(_SKILL_DIR),
        capture_output=True,
        text=True,
    )


def test_self_test_green():
    """--self-test (射影・kind 解決・非 skill 拒否・schema 突合の内部 fixture) が exit0。"""
    result = _run("--self-test")
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_main_projects_golden_c01_clean_json():
    """golden inventory の C01 射影が exit0 で、stdout が planner キーを含まない brief JSON。"""
    result = _run("--inventory", str(_GOLDEN_INVENTORY), "--component", "C01")
    assert result.returncode == 0, result.stderr
    brief = json.loads(result.stdout)
    assert brief["kind"] == "run" and brief["skill_name"]
    assert not set(brief) & set(json.loads('["id","component_kind","builder","quality_gates","skill_kind"]')), (
        "planner 固有キーが brief へ漏れている"
    )


def test_main_out_writes_brief_path(tmp_path):
    """--out が brief_path (handoff build_args の宣言先) へ書き出し、stdout/再実行が決定論。"""
    out = tmp_path / "briefs" / "skill-brief-C01.json"
    assert _run("--inventory", str(_GOLDEN_INVENTORY), "--component", "C01", "--out", str(out)).returncode == 0
    first = out.read_text(encoding="utf-8")
    assert _run("--inventory", str(_GOLDEN_INVENTORY), "--component", "C01", "--out", str(out)).returncode == 0
    assert out.read_text(encoding="utf-8") == first, "同一 inventory の射影が byte 同一でない (再現性違反)"


def test_main_usage_and_missing_component_exit2(tmp_path):
    """引数不足・inventory 不在・component 不在は usage error (exit 2)。"""
    assert _run().returncode == 2
    assert _run("--inventory", str(tmp_path / "ghost.json"), "--component", "C01").returncode == 2
    result = _run("--inventory", str(_GOLDEN_INVENTORY), "--component", "C99")
    assert result.returncode == 2
    assert "C99" in result.stderr


def test_main_non_skill_component_exit1(tmp_path):
    """非 skill component の射影指定は violation (exit 1) で明示拒否する。"""
    inventory = write_inventory(tmp_path, [component_entry("C04", "hook")])
    result = _run("--inventory", str(inventory), "--component", "C04")
    assert result.returncode == 1
    assert "skill のみ" in result.stderr


def test_project_brief_removes_planner_keys_and_renames_kind(skill_brief, specfm_mod):
    """射影が planner 固有キーを除去し skill_kind→kind へ写像、base required を保持する。"""
    comp = component_entry("C01", "skill", skill_kind="run")
    comp["couples_with"] = ["C02"]
    comp["goal_seek"] = {"engine": "inline", "fork": "subagent", "max_loops": 5}
    brief = skill_brief.project_brief(comp)
    assert brief["kind"] == "run"
    assert brief["goal_seek"] == comp["goal_seek"]
    assert "couples_with" not in brief
    assert not set(brief) & (skill_brief.PLANNER_ONLY_KEYS | {"skill_kind"})
    assert [f for f in specfm_mod.SKILL_BRIEF_FIELDS if f not in brief] == []
    # キー順は base required 14 が先頭 (byte 再現性の安定順)
    assert list(brief)[: len(specfm_mod.SKILL_BRIEF_FIELDS)] == list(specfm_mod.SKILL_BRIEF_FIELDS)


def test_validate_against_schema_detects_missing_and_extras(skill_brief):
    """schema 突合検査器が base/allOf required 欠落と余剰キーを検出する (負例)。"""
    schema = {
        "required": ["skill_name", "kind"],
        "properties": {"skill_name": {}, "kind": {}, "goal": {}},
        "allOf": [{
            "if": {"properties": {"kind": {"enum": ["run"]}}},
            "then": {"required": ["goal"]},
        }],
    }
    errs = skill_brief.validate_against_schema({"kind": "run", "planner_leak": 1}, schema)
    assert any("base required 欠落: skill_name" in e for e in errs)
    assert any("余剰キー" in e and "planner_leak" in e for e in errs)
    assert any("条件付き required 欠落: goal" in e for e in errs)
    # 正例: 充足 brief は違反 0
    assert skill_brief.validate_against_schema({"skill_name": "run-x", "kind": "run", "goal": "g"}, schema) == []
