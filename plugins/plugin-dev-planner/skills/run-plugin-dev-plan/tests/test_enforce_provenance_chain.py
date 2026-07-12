"""enforce-provenance-chain.py (C11 hook) の機能テスト。

--mode update の PreToolUse で C04/C05 pass marker (goal-spec digest pin) を検証し、
欠落/stale を exit2 block、markers 揃いを exit0、非 update / plan_dir 特定不能を
非関与 (exit0) にすることを固定する。hook は scripts/ 外なので独立ローダで import する。
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType

import pytest

# tests -> run-plugin-dev-plan -> skills -> plugin-dev-planner -> hooks/
_HOOK = Path(__file__).resolve().parents[3] / "hooks" / "enforce-provenance-chain.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("enforce_provenance_chain", _HOOK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook() -> ModuleType:
    return _load()


def _plan_with_goal_spec(tmp_path) -> Path:
    plan = tmp_path / "plugin-plans" / "sample"
    plan.mkdir(parents=True)
    (plan / "goal-spec.json").write_text(json.dumps({"purpose": "x"}), encoding="utf-8")
    return plan


def _write_markers(plan: Path, gates, digest=None):
    gate_dir = plan / ".gate"
    gate_dir.mkdir(exist_ok=True)
    if digest is None:
        digest = hashlib.sha256((plan / "goal-spec.json").read_bytes()).hexdigest()
    for g in gates:
        (gate_dir / f"{g}.pass").write_text(digest + "\n", encoding="utf-8")


# ─────────────────── detection helpers (単体) ───────────────────
def test_is_update_invocation_true(hook):
    assert hook._is_update_invocation("run-plugin-dev-plan --mode update")
    assert hook._is_update_invocation('{"mode": "update"} plugin-dev-plan')


def test_is_update_invocation_false(hook):
    assert not hook._is_update_invocation("run-plugin-dev-plan --mode create")
    assert not hook._is_update_invocation("some unrelated bash --mode update")  # no trigger token


def test_resolve_plan_dir_prefers_out_dir(hook):
    assert hook._resolve_plan_dir("... --out-dir custom/x/y ...") == Path("custom/x/y")


def test_resolve_plan_dir_from_plugin_plans_token(hook):
    assert hook._resolve_plan_dir("... plugin-plans/sample/goal-spec.json ...") == Path("plugin-plans/sample")


def test_resolve_plan_dir_from_improvement_handoff(tmp_path, hook):
    handoff = tmp_path / "improvement-handoff.json"
    handoff.write_text(json.dumps({"plan_dir": "plugin-plans/from-handoff"}), encoding="utf-8")
    assert hook._resolve_plan_dir(f"... --improvement-handoff {handoff} ...") == Path("plugin-plans/from-handoff")


def test_resolve_plan_dir_none(hook):
    assert hook._resolve_plan_dir("no path here") is None


# ─────────────────── check_markers (単体) ───────────────────
def test_check_markers_missing(tmp_path, hook):
    plan = _plan_with_goal_spec(tmp_path)
    problems = hook.check_markers(plan)
    assert len(problems) == 2 and all("pass marker が無い" in p for p in problems)


def test_check_markers_stale(tmp_path, hook):
    plan = _plan_with_goal_spec(tmp_path)
    _write_markers(plan, hook.REQUIRED_GATES, digest="deadbeef")
    problems = hook.check_markers(plan)
    assert len(problems) == 2 and all("stale" in p for p in problems)


def test_check_markers_clean(tmp_path, hook):
    plan = _plan_with_goal_spec(tmp_path)
    _write_markers(plan, hook.REQUIRED_GATES)
    assert hook.check_markers(plan) == []


def test_check_markers_no_goal_spec_is_noop(tmp_path, hook):
    plan = tmp_path / "plugin-plans" / "empty"
    plan.mkdir(parents=True)
    assert hook.check_markers(plan) == []


# ─────────────────── main (stdin payload → exit code) ───────────────────
def _run(hook, monkeypatch, payload) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


def test_main_non_update_is_allowed(hook, monkeypatch):
    assert _run(hook, monkeypatch, {"tool_input": {"command": "run-plugin-dev-plan --mode create"}}) == 0


def test_main_unresolvable_plan_dir_is_allowed(hook, monkeypatch):
    # update だが plan_dir を特定できない → 過剰 block を避け非関与。
    assert _run(hook, monkeypatch, {"tool_input": {"command": "run-plugin-dev-plan --mode update"}}) == 0


def test_main_missing_markers_blocks(tmp_path, hook, monkeypatch):
    plan = _plan_with_goal_spec(tmp_path)
    cmd = f"run-plugin-dev-plan --mode update --out-dir {plan}"
    assert _run(hook, monkeypatch, {"tool_input": {"command": cmd}}) == 2


def test_main_clean_markers_allows(tmp_path, hook, monkeypatch):
    plan = _plan_with_goal_spec(tmp_path)
    _write_markers(plan, hook.REQUIRED_GATES)
    cmd = f"run-plugin-dev-plan --mode update --out-dir {plan}"
    assert _run(hook, monkeypatch, {"tool_input": {"command": cmd}}) == 0


def test_main_improvement_handoff_plan_dir_blocks_without_markers(tmp_path, hook, monkeypatch):
    plan = _plan_with_goal_spec(tmp_path)
    handoff = tmp_path / "improvement-handoff.json"
    handoff.write_text(json.dumps({"plan_dir": str(plan)}), encoding="utf-8")
    cmd = f"run-plugin-dev-plan --mode update --improvement-handoff {handoff}"
    assert _run(hook, monkeypatch, {"tool_input": {"command": cmd}}) == 2


def test_main_stale_markers_block(tmp_path, hook, monkeypatch):
    plan = _plan_with_goal_spec(tmp_path)
    _write_markers(plan, hook.REQUIRED_GATES)
    # goal-spec を marker 後に改変 → digest 不一致 (stale)。
    (plan / "goal-spec.json").write_text(json.dumps({"purpose": "changed"}), encoding="utf-8")
    cmd = f"run-plugin-dev-plan --mode update --out-dir {plan}"
    assert _run(hook, monkeypatch, {"tool_input": {"command": cmd}}) == 2


def test_main_bad_json_is_allowed(hook, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("{ broken"))
    assert hook.main() == 0
