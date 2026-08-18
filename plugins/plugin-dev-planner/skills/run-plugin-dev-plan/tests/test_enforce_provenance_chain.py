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


def _plan_with_goal_spec(tmp_path, source_intake=None, raw: str | None = None) -> Path:
    """plan dir を作る。

    既定は greenfield (source_intake なし)。intake 由来 plan を作りたいときだけ
    source_intake を渡す。raw は JSON として壊れた goal-spec を置くための逃げ口。
    """
    plan = tmp_path / "plugin-plans" / "sample"
    plan.mkdir(parents=True)
    if raw is None:
        spec = {"purpose": "x"}
        if source_intake is not None:
            spec["source_intake"] = source_intake
        raw = json.dumps(spec)
    (plan / "goal-spec.json").write_text(raw, encoding="utf-8")
    return plan


def _gates_in(hook, problems, phrase: str) -> set[str]:
    """指定の診断語を出したゲート名の集合 (件数でなく名前で判定する)。

    ゲート名は hook.REQUIRED_GATES から引き、テスト側に第 2 の名簿を作らない。
    """
    return {
        g
        for g in hook.REQUIRED_GATES
        if any(p.startswith(f"{g} の pass marker が") and phrase in p for p in problems)
    }


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
def test_check_markers_missing_greenfield_requires_only_provenance_chain(tmp_path, hook):
    # greenfield (source_intake なし): C04 は --intake が無く原理的に PASS 不能なので
    # 要求しない。C05 は --allow-missing-intake で PASS 可能なので要求し続ける。
    plan = _plan_with_goal_spec(tmp_path)
    problems = hook.check_markers(plan)
    assert _gates_in(hook, problems, "無い") == {"provenance-chain"}


def test_check_markers_missing_intake_derived_requires_both(tmp_path, hook):
    # intake 由来: 従来どおり両ゲートを fail-closed で要求する (緩めていないことの固定)。
    plan = _plan_with_goal_spec(tmp_path, source_intake="analysis/x/intake.json")
    problems = hook.check_markers(plan)
    assert _gates_in(hook, problems, "無い") == {"intake-consumption", "provenance-chain"}


def test_check_markers_greenfield_passes_with_provenance_chain_only(tmp_path, hook):
    # 本 fix の主目的: greenfield plan が C05 の marker だけで --mode update へ進める。
    plan = _plan_with_goal_spec(tmp_path)
    _write_markers(plan, ("provenance-chain",))
    assert hook.check_markers(plan) == []


def test_check_markers_intake_derived_blocked_by_provenance_chain_only(tmp_path, hook):
    # 反例: 同じ marker 構成でも intake 由来なら通してはならない。
    plan = _plan_with_goal_spec(tmp_path, source_intake="analysis/x/intake.json")
    _write_markers(plan, ("provenance-chain",))
    assert _gates_in(hook, hook.check_markers(plan), "無い") == {"intake-consumption"}


@pytest.mark.parametrize("empty", [None, "", {}, [], 0, False])
def test_check_markers_empty_source_intake_is_greenfield(tmp_path, hook, empty):
    # planner は greenfield で source_intake に null を書く。空の器は出自の証拠にならない。
    plan = _plan_with_goal_spec(tmp_path, source_intake=empty)
    if empty is None:
        # source_intake: null を明示的に置く経路も同じ扱いになることを固定する。
        (plan / "goal-spec.json").write_text(
            json.dumps({"purpose": "x", "source_intake": None}), encoding="utf-8"
        )
    _write_markers(plan, ("provenance-chain",))
    assert hook.check_markers(plan) == []


def test_check_markers_unparsable_goal_spec_is_fail_closed(tmp_path, hook):
    # 壊れた goal-spec で C04 を回避できてはならない (緩める側の抜け道封鎖)。
    plan = _plan_with_goal_spec(tmp_path, raw="{ not json")
    _write_markers(plan, ("provenance-chain",))
    problems = hook.check_markers(plan)
    assert _gates_in(hook, problems, "無い") == {"intake-consumption"}
    # かつ「marker が無い」ではなく「壊れている」と分かる診断が出る (誤診の防止)。
    assert any("JSON として読めない" in p for p in problems)


def test_check_markers_non_object_goal_spec_is_fail_closed(tmp_path, hook):
    plan = _plan_with_goal_spec(tmp_path, raw=json.dumps(["not", "an", "object"]))
    _write_markers(plan, ("provenance-chain",))
    problems = hook.check_markers(plan)
    assert _gates_in(hook, problems, "無い") == {"intake-consumption"}
    assert any("object でない" in p for p in problems)


def test_check_markers_stale(tmp_path, hook):
    plan = _plan_with_goal_spec(tmp_path, source_intake="analysis/x/intake.json")
    _write_markers(plan, hook.REQUIRED_GATES, digest="deadbeef")
    problems = hook.check_markers(plan)
    assert _gates_in(hook, problems, "stale") == {"intake-consumption", "provenance-chain"}


def test_check_markers_stale_greenfield(tmp_path, hook):
    # greenfield でも C05 の stale 検出は生きている (要求集合を絞っただけで弱めていない)。
    plan = _plan_with_goal_spec(tmp_path)
    _write_markers(plan, ("provenance-chain",), digest="deadbeef")
    problems = hook.check_markers(plan)
    assert _gates_in(hook, problems, "stale") == {"provenance-chain"}


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


def test_main_greenfield_allows_with_provenance_chain_only(tmp_path, hook, monkeypatch):
    # exit code の水準でも greenfield が通ること (check_markers 単体だけでなく経路全体)。
    plan = _plan_with_goal_spec(tmp_path)
    _write_markers(plan, ("provenance-chain",))
    cmd = f"run-plugin-dev-plan --mode update --out-dir {plan}"
    assert _run(hook, monkeypatch, {"tool_input": {"command": cmd}}) == 0


def test_main_intake_derived_blocks_with_provenance_chain_only(tmp_path, hook, monkeypatch):
    # 同じ marker 構成で intake 由来は block されたままであること (fail-closed の保全)。
    plan = _plan_with_goal_spec(tmp_path, source_intake="analysis/x/intake.json")
    _write_markers(plan, ("provenance-chain",))
    cmd = f"run-plugin-dev-plan --mode update --out-dir {plan}"
    assert _run(hook, monkeypatch, {"tool_input": {"command": cmd}}) == 2


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
