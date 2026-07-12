"""project-task-status.py の機能テスト (C18・parity 検査専用)。

conftest 非依存でローカルロード。check_parity (三層 parity) + main() を網羅する。
正本の受入例は phase-04-test-design.md の C18 節。投影 (task-graph-status.json + task-progress.md)
の writer は consumer (harness-creator TG-C09 project-task-status.py) 唯一であり、producer 側の
本 script は書かない (二重 writer 禁止・elegant-review 20260711 A2)。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PTS = _load("project-task-status")
DTG = _load("derive-task-graph")


def _node(nid, state="pending"):
    return {"id": nid, "title": nid, "phase_ref": "P05", "entity_ref": None,
            "state": state, "write_scope": f"ws/{nid}"}


def _graph(node_ids):
    nodes = [_node(nid) for nid in node_ids]
    return DTG.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": []})


def _state(graph, states):
    return {
        "schema_version": "1.0",
        "graph_hash": DTG.graph_hash(graph),
        "nodes": [{"id": nid, "state": st} for nid, st in states.items()],
    }


def _projection(graph, state):
    state_by_id = {n["id"]: n["state"] for n in state["nodes"]}
    nodes = [
        {"id": node["id"], "state": state_by_id[node["id"]]}
        for node in graph["nodes"]
    ]
    by_state = {key: 0 for key in ("pending", "running", "done", "blocked")}
    for node in nodes:
        by_state[node["state"]] += 1
    return {
        "graph_hash": state["graph_hash"],
        "summary": {"total": len(nodes), "by_state": by_state},
        "nodes": nodes,
    }


# ─────────────────── check_parity: 満たす例 ───────────────────
def test_parity_ok_on_state_transition():
    graph = _graph(["T1", "T2"])
    # pending→done の遷移は state だけを更新し graph bytes/hash は不変
    state = _state(graph, {"T1": "done", "T2": "pending"})
    assert PTS.check_parity(graph, state, _projection(graph, state)) == []


# ─────────────────── check_parity: 満たさない例 ───────────────────
def test_parity_graph_hash_mismatch_rejected():
    graph = _graph(["T1", "T2"])
    state = _state(graph, {"T1": "done", "T2": "pending"})
    # graph node.state を直接書き換える → hash 変化 → state.graph_hash pin と不一致
    graph["nodes"][0]["state"] = "done"
    errs = PTS.check_parity(graph, state, _projection(_graph(["T1", "T2"]), state))
    assert any("graph_hash pin 不一致" in e for e in errs)


def test_parity_node_set_mismatch_rejected():
    graph = _graph(["T1", "T2"])
    state = _state(graph, {"T1": "done"})  # T2 が state に無い
    projection = _projection(_graph(["T1"]), state)
    errs = PTS.check_parity(graph, state, projection)
    assert any("graph にあり state に無い node" in e for e in errs)


def test_parity_projection_state_and_summary_tamper_rejected():
    graph = _graph(["T1", "T2"])
    state = _state(graph, {"T1": "done", "T2": "pending"})
    projection = _projection(graph, state)
    projection["nodes"][0]["state"] = "blocked"
    projection["summary"]["by_state"]["done"] = 99
    errs = PTS.check_parity(graph, state, projection)
    assert any("projection state 不一致" in e for e in errs)
    assert any("summary.by_state 不一致" in e for e in errs)


def test_parity_projection_node_set_and_hash_tamper_rejected():
    graph = _graph(["T1", "T2"])
    state = _state(graph, {"T1": "done", "T2": "pending"})
    projection = _projection(graph, state)
    projection["nodes"].pop()
    projection["graph_hash"] = "sha256:" + "0" * 64
    errs = PTS.check_parity(graph, state, projection)
    assert any("state にあり projection に無い node" in e for e in errs)
    assert any("projection graph_hash 不一致" in e for e in errs)


# ─────────────────── main() ───────────────────
def _write(tmp_path, graph, state, projection=None):
    (tmp_path / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (tmp_path / "task-state.json").write_text(json.dumps(state), encoding="utf-8")
    projection = projection if projection is not None else _projection(graph, state)
    (tmp_path / "task-graph-status.json").write_text(json.dumps(projection), encoding="utf-8")


def test_main_explicit_paths_parity_ok_exit0_and_never_writes_projection(tmp_path):
    """実配置を表せる明示入力で exit0。入力 projection は一切変更しない。"""
    graph = _graph(["T1", "T2"])
    state = _state(graph, {"T1": "done", "T2": "pending"})
    _write(tmp_path, graph, state)
    status_path = tmp_path / "task-graph-status.json"
    before = status_path.read_bytes()
    assert PTS.main([
        "--task-graph", str(tmp_path / "task-graph.json"),
        "--task-state", str(tmp_path / "task-state.json"),
        "--status-json", str(status_path),
    ]) == 0
    assert status_path.read_bytes() == before
    assert not (tmp_path / "task-progress.md").exists()


def test_main_check_only_backward_compat_noop(tmp_path):
    """--check-only は後方互換で受理する no-op (常に検査のみ)。"""
    graph = _graph(["T1"])
    state = _state(graph, {"T1": "pending"})
    _write(tmp_path, graph, state)
    assert PTS.main([str(tmp_path), "--check-only"]) == 0


def test_main_parity_violation_exit1(tmp_path):
    graph = _graph(["T1", "T2"])
    state = _state(graph, {"T1": "done", "T2": "pending"})
    projection = _projection(graph, state)
    projection["nodes"][0]["state"] = "blocked"  # projection 改竄
    _write(tmp_path, graph, state, projection)
    assert PTS.main([
        "--task-graph", str(tmp_path / "task-graph.json"),
        "--task-state", str(tmp_path / "task-state.json"),
        "--status-json", str(tmp_path / "task-graph-status.json"),
    ]) == 1


def test_current_plan_graph_state_and_consumer_projection_exit0(tmp_path):
    """現行 plan の実配置 graph/state と consumer 生成 status の integration。"""
    graph_path = REPO_ROOT / "plugin-plans/plugin-dev-planner/task-graph.json"
    state_path = REPO_ROOT / "eval-log/plugin-dev-planner/build/task-state.json"
    if not state_path.exists():
        pytest.skip("gitignore 対象の現行 build task-state.json がない環境")
    status_path = tmp_path / "task-graph-status.json"
    progress_path = tmp_path / "task-progress.md"
    consumer = REPO_ROOT / "plugins/harness-creator/scripts/project-task-status.py"
    generated = subprocess.run(
        [
            sys.executable, str(consumer),
            "--task-graph", str(graph_path),
            "--task-state", str(state_path),
            "--out-json", str(status_path),
            "--out-md", str(progress_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    assert PTS.main([
        "--task-graph", str(graph_path),
        "--task-state", str(state_path),
        "--status-json", str(status_path),
    ]) == 0


def test_main_read_error_exit2(tmp_path):
    assert PTS.main([
        "--task-graph", str(tmp_path / "missing-graph.json"),
        "--task-state", str(tmp_path / "missing-state.json"),
        "--status-json", str(tmp_path / "missing-status.json"),
    ]) == 2


def test_main_rejects_partial_explicit_paths():
    assert PTS.main(["--task-graph", "task-graph.json"]) == 2


def test_producer_script_has_no_projection_write_code():
    """縮退の恒久確認: producer 側 source に投影ファイルへの書込コードが存在しない。"""
    src = (SCRIPTS / "project-task-status.py").read_text(encoding="utf-8")
    assert "write_text" not in src
    assert not hasattr(PTS, "project")
