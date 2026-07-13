"""sync-task-state.py (TG-C02) の機能テスト — task-state.json 単一 writer の状態機械。

conftest 非依存で module-level に importlib ロードする (共有 fixture に依存しない
自己完結テスト)。正常系 + 異常系 (不正遷移/done route_report 欠落/blocked reason 欠落/
covered_task_ids 照合失敗/--require-covered 不在 violation/graph 指定時の未知 task-id 拒否/
lease 期限前 reap 拒否/再 pin 異値/propagate↔reactivate 往復/
resolve_build_dir cycle_id 有無/resolve_planner_root/canonical id 昇順) を網羅する。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sts = _load("sync-task-state")


T0 = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _state(*nodes) -> dict:
    return {"schema_version": "1.0", "graph_hash": None, "nodes": [dict(n) for n in nodes]}


def _node(nid, state="pending", **extra) -> dict:
    base = {"id": nid, "state": state, "started_at": None, "lease_expires_at": None}
    base.update(extra)
    return base


def _route_report(tmp_path, name="route-r1.json", covered=None) -> str:
    payload = {"route_id": "r1"}
    if covered is not None:
        payload["covered_task_ids"] = covered
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return str(p)


def _graph() -> dict:
    # T1 -> T2 -> T3 の直列 depends_on 鎖 + T2 produces A2, A2 -> T4 consumes。
    return {
        "schema_version": "1.0",
        "nodes": [{"id": f"T{i}"} for i in (1, 2, 3, 4)],
        "edges": [
            {"type": "depends_on", "from": "T2", "to": "T1"},
            {"type": "depends_on", "from": "T3", "to": "T2"},
            {"type": "produces", "from": "T2", "to": "A2"},
            {"type": "consumes", "from": "A2", "to": "T4"},
        ],
    }


def test_dependency_truth_table_resolves_consumes_via_produces():
    producers, issues = sts.resolve_dependency_producers(_graph())
    assert issues == []
    assert producers["T2"] == {"T1"}
    assert producers["T3"] == {"T2"}
    assert producers["T4"] == {"T2"}


def test_dependency_truth_table_missing_artifact_producer_is_issue():
    graph = _graph()
    graph["edges"] = [
        edge for edge in graph["edges"]
        if not (edge["type"] == "produces" and edge["to"] == "A2")
    ]
    _, issues = sts.resolve_dependency_producers(graph)
    assert issues == [{
        "kind": "missing-artifact-producer",
        "artifact_id": "A2",
        "consumer_task_id": "T4",
    }]


def test_propagate_blocked_rejects_missing_consumes_producer():
    graph = {"nodes": [{"id": "T1"}], "edges": [
        {"type": "consumes", "from": "A404", "to": "T1"},
    ]}
    with pytest.raises(ValueError, match="has no producer"):
        sts.propagate_blocked(_state(_node("T1")), graph, "T1", T0)


# ─────────────────────────── resolve_build_dir ───────────────────────────
def test_resolve_build_dir_flat_when_cycle_none():
    assert sts.resolve_build_dir("acme", None) == "eval-log/acme/build"


def test_resolve_build_dir_scoped_when_cycle_set():
    assert sts.resolve_build_dir("acme", "20260706-x") == "eval-log/acme/build/20260706-x"


# ─────────────────────────── resolve_planner_root ───────────────────────────
def test_resolve_planner_root_points_to_producer_plugin():
    root = sts.resolve_planner_root()
    assert root.name == "plugin-dev-planner"
    assert root == SCRIPTS.resolve().parents[1] / "plugin-dev-planner"
    assert root.is_dir()  # producer 実在 (C01/C03/C07 の import 前提)


# ─────────────────────────── transition: running ───────────────────────────
def test_transition_pending_to_running_sets_started_and_lease():
    out = sts.transition(_state(_node("T1")), "T1", "running", now=T0, lease_seconds=3600)
    n = out["nodes"][0]
    assert n["state"] == "running"
    assert n["started_at"] == "2026-07-06T12:00:00Z"
    assert n["lease_expires_at"] == "2026-07-06T13:00:00Z"


def test_transition_unregistered_task_defaults_pending():
    out = sts.transition(_state(), "TX", "running", now=T0)
    assert out["nodes"][0]["id"] == "TX" and out["nodes"][0]["state"] == "running"


def test_transition_invalid_pending_to_done_raises():
    with pytest.raises(ValueError):
        sts.transition(_state(_node("T1")), "T1", "done", now=T0)


def test_transition_done_terminal_no_further(tmp_path):
    rr = _route_report(tmp_path)
    done = sts.transition(_state(_node("T1", "running")), "T1", "done", route_report=rr, now=T0)
    with pytest.raises(ValueError):
        sts.transition(done, "T1", "running", now=T0)


# ─────────────────────────── transition: done ───────────────────────────
def test_transition_done_requires_existing_route_report():
    with pytest.raises(ValueError):
        sts.transition(_state(_node("T1", "running")), "T1", "done",
                       route_report="/no/such/report.json", now=T0)


def test_transition_done_missing_route_report_arg_raises():
    with pytest.raises(ValueError):
        sts.transition(_state(_node("T1", "running")), "T1", "done", now=T0)


def test_transition_done_backward_compat_without_covered(tmp_path):
    rr = _route_report(tmp_path)  # covered_task_ids 不在 = 単一 task 後方互換
    out = sts.transition(_state(_node("T1", "running")), "T1", "done", route_report=rr, now=T0)
    n = out["nodes"][0]
    assert n["state"] == "done" and n["route_report"] == rr


def test_transition_done_with_covered_includes_task(tmp_path):
    rr = _route_report(tmp_path, covered=["T1", "T2"])
    out = sts.transition(_state(_node("T1", "running")), "T1", "done", route_report=rr, now=T0)
    assert out["nodes"][0]["state"] == "done"


def test_transition_done_covered_mismatch_raises(tmp_path):
    rr = _route_report(tmp_path, covered=["T2", "T3"])
    with pytest.raises(ValueError):
        sts.transition(_state(_node("T1", "running")), "T1", "done", route_report=rr, now=T0)


# ─────────────────────────── transition: require_covered ───────────────────────────
def test_transition_require_covered_absent_raises(tmp_path):
    rr = _route_report(tmp_path)  # covered_task_ids 不在 → 暗黙互換を無効化して violation
    with pytest.raises(ValueError):
        sts.transition(_state(_node("T1", "running")), "T1", "done",
                       route_report=rr, require_covered=True, now=T0)


def test_transition_require_covered_present_passes(tmp_path):
    rr = _route_report(tmp_path, covered=["T1"])
    out = sts.transition(_state(_node("T1", "running")), "T1", "done",
                         route_report=rr, require_covered=True, now=T0)
    assert out["nodes"][0]["state"] == "done"


def test_main_require_covered_flag_exit1_when_absent(tmp_path):
    rr = _route_report(tmp_path)
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(_node("T1", "running"))), encoding="utf-8")
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(tmp_path / "e.jsonl"),
        "--task-id", "T1", "--to-state", "done", "--route-report", rr, "--require-covered",
    ])
    assert rc == 1
    # violation 時は書き込まない (running のまま)。
    assert json.loads(state_path.read_text(encoding="utf-8"))["nodes"][0]["state"] == "running"


# ─────────────────────────── 未知 task-id 拒否 (graph 指定時) ───────────────────────────
def test_assert_task_in_graph_accepts_known():
    sts.assert_task_in_graph(_graph(), "T1")  # 例外にならない


def test_assert_task_in_graph_rejects_unknown():
    with pytest.raises(ValueError):
        sts.assert_task_in_graph(_graph(), "TX")


def test_main_transition_unknown_task_with_graph_exit1(tmp_path):
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(_graph()), encoding="utf-8")
    state_path = tmp_path / "task-state.json"
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(tmp_path / "e.jsonl"),
        "--task-id", "TX", "--to-state", "running", "--task-graph", str(graph_path),
    ])
    assert rc == 1
    assert not state_path.exists()  # fail-closed: 暗黙 pending node を書き込まない


def test_main_transition_known_task_with_graph_exit0(tmp_path):
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(_graph()), encoding="utf-8")
    state_path = tmp_path / "task-state.json"
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(tmp_path / "e.jsonl"),
        "--task-id", "T1", "--to-state", "running", "--task-graph", str(graph_path),
    ])
    assert rc == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["nodes"][0]["state"] == "running"


# ────────── initialize_from_graph (sparse state → complete node set) ──────────
def test_initialize_from_graph_adds_missing_pending_and_preserves_existing():
    state = _state(
        _node("T1", "done", route_report="route-T1.json"),
        _node("T2", "running", started_at="2026-07-06T10:00:00Z",
              lease_expires_at="2026-07-06T11:00:00Z"),
    )
    graph = {"nodes": [{"id": "T1"}, {"id": "T2"}, {"id": "T3"}], "edges": []}
    out = sts.initialize_from_graph(state, graph)
    by_id = {node["id"]: node for node in out["nodes"]}
    assert by_id["T1"] == state["nodes"][0]
    assert by_id["T2"] == state["nodes"][1]
    assert by_id["T3"] == _node("T3")
    assert len(state["nodes"]) == 2  # 入力不変


@pytest.mark.parametrize("owner", ["task-state", "task-graph"])
def test_initialize_from_graph_rejects_duplicate_ids(owner):
    state = _state(_node("T1"))
    graph = {"nodes": [{"id": "T1"}], "edges": []}
    if owner == "task-state":
        state["nodes"].append(_node("T1"))
    else:
        graph["nodes"].append({"id": "T1"})
    with pytest.raises(ValueError, match=rf"{owner} node id 重複"):
        sts.initialize_from_graph(state, graph)


def test_initialize_from_graph_rejects_unknown_state_node():
    with pytest.raises(ValueError, match="未知 node"):
        sts.initialize_from_graph(
            _state(_node("T1"), _node("GHOST")),
            {"nodes": [{"id": "T1"}], "edges": []},
        )


def test_cli_initialize_from_graph_materializes_all_nodes(tmp_path):
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps({
        "nodes": [{"id": f"T{i}"} for i in range(135)], "edges": [],
    }), encoding="utf-8")
    state_path = tmp_path / "task-state.json"
    existing = [_node(f"T{i}", "done", route_report=f"route-{i}.json") for i in range(110)]
    state_path.write_text(json.dumps(_state(*existing)), encoding="utf-8")
    events_path = tmp_path / "task-events.jsonl"
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(events_path),
        "--task-graph", str(graph_path), "--initialize-from-graph",
    ])
    assert rc == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(state["nodes"]) == 135
    assert sum(node["state"] == "done" for node in state["nodes"]) == 110
    assert sum(node["state"] == "pending" for node in state["nodes"]) == 25
    event = json.loads(events_path.read_text(encoding="utf-8"))
    assert event["type"] == "task_state_initialized" and event["added_count"] == 25


def test_cli_initialize_rejection_does_not_write(tmp_path):
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps({"nodes": [{"id": "T1"}]}), encoding="utf-8")
    state_path = tmp_path / "task-state.json"
    original = _state(_node("T1"), _node("GHOST"))
    state_path.write_text(json.dumps(original), encoding="utf-8")
    rc = sts.main([
        "--task-state", str(state_path), "--task-graph", str(graph_path),
        "--initialize-from-graph",
    ])
    assert rc == 1
    assert json.loads(state_path.read_text(encoding="utf-8")) == original


# ─────────────────────────── transition: blocked ───────────────────────────
def test_transition_blocked_requires_reason():
    with pytest.raises(ValueError):
        sts.transition(_state(_node("T1")), "T1", "blocked", now=T0)


def test_transition_blocked_invalid_reason_raises():
    with pytest.raises(ValueError):
        sts.transition(_state(_node("T1")), "T1", "blocked", reason="whatever", now=T0)


def test_transition_blocked_sets_first_class_reason():
    out = sts.transition(_state(_node("T1")), "T1", "blocked", reason="origin-failure", now=T0)
    n = out["nodes"][0]
    assert n["state"] == "blocked" and n["blocked_reason"] == "origin-failure"


def test_transition_out_of_blocked_clears_reason():
    blocked = sts.transition(_state(_node("T1")), "T1", "blocked", reason="propagated", now=T0)
    reopened = sts.transition(blocked, "T1", "pending", now=T0)
    assert reopened["nodes"][0]["state"] == "pending"
    assert "blocked_reason" not in reopened["nodes"][0]


# ─────────────────────────── reap_expired_lease ───────────────────────────
def test_reap_expired_lease_running_past_expiry():
    expired = "2026-07-06T11:00:00Z"
    st = _state(_node("T1", "running", started_at="2026-07-06T10:00:00Z", lease_expires_at=expired))
    out = sts.reap_expired_lease(st, "T1", T0)
    assert out["nodes"][0]["state"] == "pending"
    assert out["nodes"][0]["lease_expires_at"] is None


def test_reap_rejects_when_lease_not_expired():
    future = "2026-07-06T13:00:00Z"
    st = _state(_node("T1", "running", lease_expires_at=future))
    with pytest.raises(ValueError):
        sts.reap_expired_lease(st, "T1", T0)


def test_reap_rejects_non_running():
    st = _state(_node("T1", "pending", lease_expires_at="2026-07-06T11:00:00Z"))
    with pytest.raises(ValueError):
        sts.reap_expired_lease(st, "T1", T0)


# ─────────────────────────── renew_lease ───────────────────────────
def test_renew_lease_extends_and_keeps_running():
    st = _state(_node("T1", "running", lease_expires_at="2026-07-06T12:30:00Z"))
    out = sts.renew_lease(st, "T1", T0, 3600)
    n = out["nodes"][0]
    assert n["state"] == "running" and n["lease_expires_at"] == "2026-07-06T13:00:00Z"


def test_renew_lease_rejects_non_running():
    with pytest.raises(ValueError):
        sts.renew_lease(_state(_node("T1", "pending")), "T1", T0, 3600)


# ─────────────────────────── pin_graph_hash ───────────────────────────
def test_pin_graph_hash_sets_when_unset():
    h = "sha256:" + "a" * 64
    out = sts.pin_graph_hash(_state(), h)
    assert out["graph_hash"] == h


def test_pin_graph_hash_idempotent_same_value():
    h = "sha256:" + "b" * 64
    st = _state()
    st["graph_hash"] = h
    assert sts.pin_graph_hash(st, h)["graph_hash"] == h


def test_pin_graph_hash_rejects_different_value():
    st = _state()
    st["graph_hash"] = "sha256:" + "c" * 64
    with pytest.raises(ValueError):
        sts.pin_graph_hash(st, "sha256:" + "d" * 64)


# ─────────────────────────── propagate / reactivate ───────────────────────────
def test_propagate_blocked_marks_downstream_closure():
    st = _state(_node("T1"), _node("T2"), _node("T3"), _node("T4"))
    out = sts.propagate_blocked(st, _graph(), "T1", T0)
    by = {n["id"]: n for n in out["nodes"]}
    # T2/T3/T4 は T1 の推移的下流 → propagated blocked。T1 自身は変えない。
    for tid in ("T2", "T3", "T4"):
        assert by[tid]["state"] == "blocked" and by[tid]["blocked_reason"] == "propagated"
    assert by["T1"]["state"] == "pending"


def test_propagate_reactivate_round_trip():
    st = _state(_node("T1"), _node("T2"), _node("T3"), _node("T4"))
    blocked = sts.propagate_blocked(st, _graph(), "T1", T0)
    back = sts.reactivate_cascade(blocked, _graph(), "T1")
    by = {n["id"]: n for n in back["nodes"]}
    for tid in ("T2", "T3", "T4"):
        assert by[tid]["state"] == "pending" and "blocked_reason" not in by[tid]


def test_reactivate_origin_only_with_include_origin():
    st = _state(
        _node("T1", "blocked", blocked_reason="origin-failure"),
        _node("T2", "blocked", blocked_reason="propagated"),
    )
    without = sts.reactivate_cascade(st, _graph(), "T1", include_origin=False)
    assert {n["id"]: n["state"] for n in without["nodes"]}["T1"] == "blocked"
    with_origin = sts.reactivate_cascade(st, _graph(), "T1", include_origin=True)
    by = {n["id"]: n for n in with_origin["nodes"]}
    assert by["T1"]["state"] == "pending" and "blocked_reason" not in by["T1"]


# ─────────────────────────── append_event ───────────────────────────
def test_append_event_writes_line_with_ts(tmp_path):
    ev_path = tmp_path / "task-events.jsonl"
    sts.append_event(ev_path, {"type": "state_transition", "task_id": "T1"})
    sts.append_event(ev_path, {"type": "lease_renewed", "task_id": "T1"})
    lines = ev_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert "ts" in first and first["type"] == "state_transition" and first["task_id"] == "T1"


# ─────────────────────────── canonical_state_json ───────────────────────────
def test_canonical_state_json_sorts_nodes_by_id():
    st = _state(_node("T3"), _node("T1"), _node("T10"), _node("T2"))
    parsed = json.loads(sts.canonical_state_json(st))
    assert [n["id"] for n in parsed["nodes"]] == ["T1", "T10", "T2", "T3"]


def test_canonical_state_json_is_indented_utf8():
    st = _state(_node("あ"))
    text = sts.canonical_state_json(st)
    assert "\n  " in text and "あ" in text  # indent=2 かつ ensure_ascii=False


# ─────────────────────────── purity ───────────────────────────
def test_transition_does_not_mutate_input():
    st = _state(_node("T1"))
    sts.transition(st, "T1", "running", now=T0)
    assert st["nodes"][0]["state"] == "pending" and st["nodes"][0]["started_at"] is None


# ─────────────────────────── main() CLI ───────────────────────────
def test_main_transition_writes_state_and_event(tmp_path):
    state_path = tmp_path / "task-state.json"
    events_path = tmp_path / "task-events.jsonl"
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(events_path),
        "--task-id", "T1", "--to-state", "running",
    ])
    assert rc == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["nodes"][0]["state"] == "running"
    assert state_path.read_text(encoding="utf-8").endswith("\n")
    assert len(events_path.read_text(encoding="utf-8").splitlines()) == 1


def test_main_invalid_transition_exit1(tmp_path):
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(_node("T1", "done"))), encoding="utf-8")
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(tmp_path / "e.jsonl"),
        "--task-id", "T1", "--to-state", "running",
    ])
    assert rc == 1


def test_main_no_operation_exit2(tmp_path):
    rc = sts.main(["--task-state", str(tmp_path / "s.json"), "--events", str(tmp_path / "e.jsonl")])
    assert rc == 2


def test_main_default_path_from_resolve_build_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = sts.main([
        "--target-plugin-slug", "acme", "--cycle-id", "20260706-x",
        "--task-id", "T1", "--pin-graph-hash", "sha256:" + "e" * 64,
    ])
    assert rc == 0
    expected = tmp_path / "eval-log/acme/build/20260706-x/task-state.json"
    assert expected.exists()
    assert json.loads(expected.read_text(encoding="utf-8"))["graph_hash"] == "sha256:" + "e" * 64


def test_main_propagate_blocked_end_to_end(tmp_path):
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(
        _state(_node("T1", "running"), _node("T2"), _node("T3"), _node("T4"))), encoding="utf-8")
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(_graph()), encoding="utf-8")
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(tmp_path / "e.jsonl"),
        "--task-id", "T1", "--to-state", "blocked", "--reason", "origin-failure",
        "--propagate-blocked", "--task-graph", str(graph_path),
    ])
    assert rc == 0
    by = {n["id"]: n for n in json.loads(state_path.read_text(encoding="utf-8"))["nodes"]}
    assert by["T1"]["blocked_reason"] == "origin-failure"
    for tid in ("T2", "T3", "T4"):
        assert by[tid]["state"] == "blocked" and by[tid]["blocked_reason"] == "propagated"


def test_main_reactivate_cascade_end_to_end(tmp_path):
    """--reactivate-cascade CLI: propagated 下流閉包を pending へ復帰し reactivated イベントを記録。"""
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(
        _node("T1", "blocked", blocked_reason="origin-failure"),
        _node("T2", "blocked", blocked_reason="propagated"),
        _node("T3", "blocked", blocked_reason="propagated"),
        _node("T4", "blocked", blocked_reason="propagated"))), encoding="utf-8")
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(_graph()), encoding="utf-8")
    events_path = tmp_path / "e.jsonl"
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(events_path),
        "--reactivate-cascade", "T1", "--task-graph", str(graph_path),
    ])
    assert rc == 0
    by = {n["id"]: n for n in json.loads(state_path.read_text(encoding="utf-8"))["nodes"]}
    assert by["T1"]["state"] == "blocked"  # origin は --include-origin なしでは据置
    for tid in ("T2", "T3", "T4"):
        assert by[tid]["state"] == "pending" and "blocked_reason" not in by[tid]
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    reactivated = [e for e in events if e.get("reason") == "reactivated"]
    assert sorted(e["task_id"] for e in reactivated) == ["T2", "T3", "T4"]


def test_main_reactivate_cascade_include_origin(tmp_path):
    """--include-origin で origin 自身も pending へ復帰する。"""
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(
        _node("T1", "blocked", blocked_reason="origin-failure"),
        _node("T2", "blocked", blocked_reason="propagated"))), encoding="utf-8")
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(_graph()), encoding="utf-8")
    rc = sts.main([
        "--task-state", str(state_path), "--events", str(tmp_path / "e.jsonl"),
        "--reactivate-cascade", "T1", "--include-origin", "--task-graph", str(graph_path),
    ])
    assert rc == 0
    by = {n["id"]: n for n in json.loads(state_path.read_text(encoding="utf-8"))["nodes"]}
    assert by["T1"]["state"] == "pending" and "blocked_reason" not in by["T1"]


def test_main_reactivate_cascade_requires_graph(tmp_path):
    """--reactivate-cascade は --task-graph 必須 (欠落は exit2)。"""
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(_node("T1", "blocked", blocked_reason="origin-failure"))),
                          encoding="utf-8")
    rc = sts.main(["--task-state", str(state_path), "--reactivate-cascade", "T1"])
    assert rc == 2


# ─────────────── repin_graph_hash (外ループ再入・provenance-gated) ───────────────
def test_repin_authorized_updates_pin():
    """新 hash が authorized 集合にあれば再 pin する (drain 由来の正当な再入)。"""
    st = {"schema_version": "1.0", "graph_hash": "sha256:" + "a" * 64, "nodes": []}
    out = sts.repin_graph_hash(st, "sha256:" + "b" * 64, {"sha256:" + "b" * 64})
    assert out["graph_hash"] == "sha256:" + "b" * 64
    # 入力不変 (純関数)
    assert st["graph_hash"] == "sha256:" + "a" * 64


def test_repin_unauthorized_raises():
    """authorized 集合に無い hash への再 pin は fail-closed で ValueError (不正混入拒否)。"""
    st = {"schema_version": "1.0", "graph_hash": "sha256:" + "a" * 64, "nodes": []}
    with pytest.raises(ValueError):
        sts.repin_graph_hash(st, "sha256:" + "c" * 64, {"sha256:" + "b" * 64})


def test_repin_same_hash_is_noop():
    """既に新 hash で pin 済みなら冪等 no-op (authorized 不問)。"""
    h = "sha256:" + "a" * 64
    st = {"schema_version": "1.0", "graph_hash": h, "nodes": []}
    out = sts.repin_graph_hash(st, h, set())
    assert out["graph_hash"] == h


def test_cli_repin_authorized_exit0(tmp_path):
    """--repin-graph-hash + --authorized-hash 一致で exit0・pin 更新。"""
    old, new = "sha256:" + "a" * 64, "sha256:" + "d" * 64
    sp = tmp_path / "task-state.json"
    sp.write_text(json.dumps({"schema_version": "1.0", "graph_hash": old, "nodes": []}), encoding="utf-8")
    rc = sts.main(["--task-state", str(sp), "--repin-graph-hash", new, "--authorized-hash", new])
    assert rc == 0
    assert json.loads(sp.read_text(encoding="utf-8"))["graph_hash"] == new


def test_cli_repin_unauthorized_exit1(tmp_path):
    """authorized 不在の --repin-graph-hash は exit1 (state violation)。"""
    old, new = "sha256:" + "a" * 64, "sha256:" + "e" * 64
    sp = tmp_path / "task-state.json"
    sp.write_text(json.dumps({"schema_version": "1.0", "graph_hash": old, "nodes": []}), encoding="utf-8")
    rc = sts.main(["--task-state", str(sp), "--repin-graph-hash", new])  # authorized 未指定
    assert rc == 1
    assert json.loads(sp.read_text(encoding="utf-8"))["graph_hash"] == old  # 変更されない
