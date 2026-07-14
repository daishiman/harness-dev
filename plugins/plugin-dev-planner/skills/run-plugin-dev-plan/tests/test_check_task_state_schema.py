"""check-task-state-schema.py の機能テスト (C16)。

conftest 非依存でローカルロード。validate_task_state (schema 手書き制約) と
check_graph_hash_pin (derive-task-graph.graph_hash 再計算照合) + main() を網羅する。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CTS = _load("check-task-state-schema")
DTG = _load("derive-task-graph")

GOOD_HASH = "sha256:" + "a" * 64


def _base_state(nodes=None):
    return {
        "schema_version": "1.0",
        "graph_hash": GOOD_HASH,
        "nodes": nodes if nodes is not None else [{"id": "T1", "state": "done"}],
    }


# ─────────────────── validate_task_state: 満たす例 ───────────────────
def test_valid_state_no_violations():
    state = _base_state([
        {"id": "T1", "state": "done"},
        {
            "id": "T2",
            "state": "running",
            "started_at": "2026-07-05T10:00:00Z",
            "lease_expires_at": "2026-07-05T10:30:00Z",
        },
    ])
    assert CTS.validate_task_state(state) == []


def test_valid_blocked_and_pending():
    state = _base_state([
        {"id": "P", "state": "pending"},
        {"id": "B", "state": "blocked", "blocked_reason": "origin-failure"},
        {"id": "B2", "state": "blocked", "blocked_reason": "propagated"},
    ])
    assert CTS.validate_task_state(state) == []


# ─────────────────── validate_task_state: 満たさない例 ───────────────────
def test_running_missing_started_at():
    state = _base_state([
        {"id": "T2", "state": "running", "lease_expires_at": "2026-07-05T10:30:00Z"},
    ])
    errs = CTS.validate_task_state(state)
    assert any("started_at" in e for e in errs)


def test_running_missing_lease():
    state = _base_state([
        {"id": "T2", "state": "running", "started_at": "2026-07-05T10:00:00Z"},
    ])
    errs = CTS.validate_task_state(state)
    assert any("lease_expires_at" in e for e in errs)


def test_running_malformed_datetime():
    state = _base_state([
        {"id": "T2", "state": "running", "started_at": "not-a-time", "lease_expires_at": "2026/07/05"},
    ])
    errs = CTS.validate_task_state(state)
    assert any("started_at" in e and "date-time" in e for e in errs)
    assert any("lease_expires_at" in e and "date-time" in e for e in errs)


def test_ready_state_is_violation():
    state = _base_state([{"id": "T1", "state": "ready"}])
    errs = CTS.validate_task_state(state)
    assert any("永続 enum 外" in e for e in errs)


def test_blocked_missing_reason():
    state = _base_state([{"id": "B", "state": "blocked"}])
    errs = CTS.validate_task_state(state)
    assert any("blocked_reason が必須" in e for e in errs)


def test_blocked_reason_out_of_range():
    state = _base_state([{"id": "B", "state": "blocked", "blocked_reason": "whatever"}])
    errs = CTS.validate_task_state(state)
    assert any("enum 外" in e for e in errs)


def test_blocked_reason_on_non_blocked():
    state = _base_state([{"id": "P", "state": "pending", "blocked_reason": "propagated"}])
    errs = CTS.validate_task_state(state)
    assert any("非 blocked" in e for e in errs)


def test_bad_graph_hash_and_schema_version():
    state = {"schema_version": "", "graph_hash": "sha256:zzz", "nodes": []}
    errs = CTS.validate_task_state(state)
    assert any("schema_version" in e for e in errs)
    assert any("graph_hash" in e for e in errs)


def test_missing_nodes_list():
    errs = CTS.validate_task_state({"schema_version": "1.0", "graph_hash": GOOD_HASH})
    assert any("nodes" in e for e in errs)


def test_non_object_state_and_node():
    assert CTS.validate_task_state("nope") == ["task-state が object でない"]
    errs = CTS.validate_task_state(_base_state(["junk"]))
    assert any("object でない" in e for e in errs)


def test_node_missing_id():
    errs = CTS.validate_task_state(_base_state([{"state": "done"}]))
    assert any("id が空" in e for e in errs)


def test_duplicate_state_node_id_is_violation():
    errs = CTS.validate_task_state(_base_state([
        {"id": "T1", "state": "done"},
        {"id": "T1", "state": "pending"},
    ]))
    assert any("task-state node id 重複" in e and "T1" in e for e in errs)


# ─────────────────── check_graph_hash_pin ───────────────────
def _write_graph(tmp_path, graph):
    p = tmp_path / "task-graph.json"
    p.write_text(json.dumps(graph), encoding="utf-8")
    return p


def _graph(nodes):
    return {"schema_version": "1.0", "nodes": nodes, "edges": []}


def test_pin_match(tmp_path):
    graph = _graph([
        {"id": "T1", "title": "t", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/1"},
    ])
    gp = _write_graph(tmp_path, graph)
    state = _base_state()
    state["graph_hash"] = DTG.graph_hash(graph)
    assert CTS.check_graph_hash_pin(state, gp) == []


def test_pin_match_but_missing_state_node_fails_closed(tmp_path):
    graph = _graph([
        {"id": "T1", "title": "t", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/1"},
        {"id": "T2", "title": "t2", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/2"},
    ])
    gp = _write_graph(tmp_path, graph)
    state = _base_state([{"id": "T1", "state": "done"}])
    state["graph_hash"] = DTG.graph_hash(graph)
    errs = CTS.check_graph_hash_pin(state, gp)
    assert any("task-state node 欠落" in e and "T2" in e for e in errs)


def test_pin_match_but_unknown_state_node_fails_closed(tmp_path):
    graph = _graph([
        {"id": "T1", "title": "t", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/1"},
    ])
    gp = _write_graph(tmp_path, graph)
    state = _base_state([
        {"id": "T1", "state": "done"}, {"id": "GHOST", "state": "done"},
    ])
    state["graph_hash"] = DTG.graph_hash(graph)
    errs = CTS.check_graph_hash_pin(state, gp)
    assert any("task-state 未知 node" in e and "GHOST" in e for e in errs)


def test_duplicate_graph_node_id_fails_closed(tmp_path):
    graph = _graph([
        {"id": "T1", "title": "t", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/1"},
        {"id": "T1", "title": "dup", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/dup"},
    ])
    gp = _write_graph(tmp_path, graph)
    state = _base_state([{"id": "T1", "state": "done"}])
    state["graph_hash"] = DTG.graph_hash(graph)
    errs = CTS.check_graph_hash_pin(state, gp)
    assert any("task-graph node id 重複" in e for e in errs)


def test_pin_mismatch_after_node_added(tmp_path):
    graph = _graph([
        {"id": "T1", "title": "t", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/1"},
    ])
    state = _base_state()
    state["graph_hash"] = DTG.graph_hash(graph)  # 旧 hash を pin
    graph["nodes"].append(
        {"id": "T2", "title": "t2", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/2"}
    )
    gp = _write_graph(tmp_path, graph)  # graph 変化後も state.graph_hash は旧値
    errs = CTS.check_graph_hash_pin(state, gp)
    assert any("pin 不一致" in e for e in errs)


def test_pin_graph_read_error(tmp_path):
    errs = CTS.check_graph_hash_pin(_base_state(), tmp_path / "missing.json")
    assert any("読込/parse 失敗" in e for e in errs)


# ─────────────────── main() ───────────────────
def _write_state(tmp_path, state):
    p = tmp_path / "task-state.json"
    p.write_text(json.dumps(state), encoding="utf-8")
    return p


def test_main_clean_exit0(tmp_path):
    sp = _write_state(tmp_path, _base_state())
    assert CTS.main(["--task-state", str(sp)]) == 0


def test_main_violation_exit1(tmp_path, capsys):
    sp = _write_state(tmp_path, _base_state([{"id": "B", "state": "blocked"}]))
    rc = CTS.main(["--task-state", str(sp)])
    assert rc == 1
    assert "blocked_reason" in capsys.readouterr().out


def test_main_with_pin_ok(tmp_path):
    graph = _graph([
        {"id": "T1", "title": "t", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/1"},
    ])
    gp = _write_graph(tmp_path, graph)
    state = _base_state()
    state["graph_hash"] = DTG.graph_hash(graph)
    sp = _write_state(tmp_path, state)
    assert CTS.main(["--task-state", str(sp), "--task-graph", str(gp)]) == 0


def test_main_with_pin_mismatch_exit1(tmp_path):
    graph = _graph([
        {"id": "T1", "title": "t", "phase_ref": "P05", "entity_ref": None,
         "state": "pending", "write_scope": "ws/1"},
    ])
    gp = _write_graph(tmp_path, graph)
    sp = _write_state(tmp_path, _base_state())  # graph_hash=GOOD_HASH は実 hash と不一致
    assert CTS.main(["--task-state", str(sp), "--task-graph", str(gp)]) == 1


def test_main_usage_error_missing_arg():
    assert CTS.main([]) == 2


def test_main_state_read_error(tmp_path):
    assert CTS.main(["--task-state", str(tmp_path / "missing.json")]) == 2
