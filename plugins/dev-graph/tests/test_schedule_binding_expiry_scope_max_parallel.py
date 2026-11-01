"""schedule-graph.py の binding 別 ready 判定・lease 期限・--scope・--max-parallel・入力不変の検証。

bd-bridge mode では tracker_binding ごとに ready の根拠が違う。beads は C28 の ready entry と
確認済み edge parity、github/none は graph だけで決める。lease は manage-worktree-lease.py と
同じ state で expires_at を読み、期限で解放される claim が scope を塞ぎ続けないようにする。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(script: str, name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    code = module.main()
    output = capsys.readouterr().out.strip()
    return code, json.loads(output) if output else None


BASE = {
    "artifact_kind": "task", "status": "active", "confirmation_status": "confirmed",
    "evaluation_status": "pass", "implementation_readiness": {"status": "complete"},
    "depends_on": [],
}


def write_graph(path: Path, nodes: list[dict]) -> None:
    path.write_text(json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": nodes}), encoding="utf-8")


def test_schedule_mixed_binding_parity_expiry_and_max_parallel(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_v2_contract")
    graph = tmp_path / "graph.json"
    write_graph(graph, [
        {**BASE, "graph_node_id": "beads", "tracker_binding": "beads", "resource_scope": ["a"]},
        {**BASE, "graph_node_id": "github", "tracker_binding": "github", "resource_scope": ["b"]},
        {**BASE, "graph_node_id": "none", "tracker_binding": "none", "resource_scope": ["c"]},
    ])
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({"ready_set": [{
        "bd_issue_id": "bd-1", "external_ref": "beads", "edge_parity": {"confirmed": True},
        "graph_status": "active", "graph_depends_on": [],
    }]}), encoding="utf-8")
    leases = tmp_path / "leases.json"
    leases.write_text(json.dumps({"leases": [{
        "graph_node_id": "github", "state": "claimed", "resource_scope": ["b"],
        "expires_at": "2020-01-01T00:00:00Z",
    }]}), encoding="utf-8")
    argv = ("--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready, "--leases", leases)

    code, plan = call_main(schedule, monkeypatch, capsys, *argv, "--max-parallel", "1")

    assert code == 0
    # github/none は Beads の ready entry を持たなくても graph だけで ready になる。
    # 2020 年に期限の切れた claimed lease は github を塞がない。
    assert plan["ready_set"]["tasks"] == ["beads", "github", "none"]
    assert plan["conflicts"] == [] and plan["excluded"] == []
    assert plan["batches"]["tasks"] == [["beads"], ["github"], ["none"]]
    assert plan["max_parallel"] == 1 and plan["read_only"] is True
    assert plan["graph_sha256_before"] == plan["graph_sha256_after"]
    assert plan["tracker_sha256_before"] == plan["tracker_sha256_after"] is not None
    assert plan["lease_sha256_before"] == plan["lease_sha256_after"] is not None

    _, unbounded = call_main(schedule, monkeypatch, capsys, *argv)
    assert unbounded["batches"]["tasks"] == [["beads", "github", "none"]]

    ready.write_text(json.dumps({"ready_set": [{
        "bd_issue_id": "bd-1", "external_ref": "beads", "edge_parity": {"confirmed": True},
        "graph_status": "active", "graph_depends_on": ["stale-dependency"],
    }]}), encoding="utf-8")
    _, stale = call_main(schedule, monkeypatch, capsys, *argv)
    assert stale["ready_set"]["tasks"] == ["github", "none"]
    assert [row["reason"] for row in stale["excluded"]] == ["beads_parity_stale_or_unconfirmed"]


def test_lease_expiry_follows_the_lease_manager_states(tmp_path, monkeypatch, capsys):
    """期限で解放される state だけが expires_at で非 active になる。park 後の pending_review は残る。"""
    schedule = load("schedule-graph.py", "schedule_v2_lease_expiry")
    graph = tmp_path / "graph.json"
    write_graph(graph, [
        {**BASE, "graph_node_id": "parked", "resource_scope": ["parked"]},
        {**BASE, "graph_node_id": "running", "resource_scope": ["running"]},
        {**BASE, "graph_node_id": "stale", "resource_scope": ["stale"]},
    ])
    leases = tmp_path / "leases.json"
    leases.write_text(json.dumps({"leases": [
        {"graph_node_id": "parked", "state": "pending_review", "resource_scope": [], "expires_at": "2020-01-01T00:00:00Z"},
        {"graph_node_id": "running", "state": "in_progress", "resource_scope": [], "expires_at": "2099-01-01T00:00:00Z"},
        {"graph_node_id": "stale", "state": "in_progress", "resource_scope": [], "expires_at": "2020-01-01T00:00:00Z"},
    ]}), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys, "--graph", graph, "--leases", leases)

    assert code == 0
    assert plan["ready_set"]["tasks"] == ["stale"]
    assert plan["conflicts"] == ["parked", "running"]

    for expires, message in (("not-a-time", "invalid expires_at"), ("2099-01-01T00:00:00", "timezone-aware")):
        leases.write_text(json.dumps({"leases": [
            {"graph_node_id": "running", "state": "claimed", "resource_scope": [], "expires_at": expires},
        ]}), encoding="utf-8")
        with pytest.raises(schedule.ContractError, match=message):
            call_main(schedule, monkeypatch, capsys, "--graph", graph, "--leases", leases)


def test_scope_selects_the_feature_subtree_and_max_parallel_must_be_positive(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_v2_scope")
    graph = tmp_path / "graph.json"
    write_graph(graph, [
        {**BASE, "graph_node_id": "feature-a", "artifact_kind": "feature", "resource_scope": ["a"]},
        {**BASE, "graph_node_id": "a-task", "parent_feature": "feature-a", "resource_scope": ["a/task"]},
        {**BASE, "graph_node_id": "b-task", "parent_feature": "feature-b", "resource_scope": ["b/task"]},
        {**BASE, "graph_node_id": "feature-b", "artifact_kind": "feature", "resource_scope": ["b"]},
    ])

    _, scoped = call_main(schedule, monkeypatch, capsys, "--graph", graph, "--scope", "feature-a")
    assert scoped["ready_set"] == {"features": ["feature-a"], "tasks": ["a-task"]}
    # feature と配下 task は同じ path を触るので、並列に出せない組として報告する。
    assert scoped["conflict_pairs"] == [
        {"left": "a-task", "right": "feature-a", "kind": "ready_pair", "resources": ["a/task"]},
    ]

    with pytest.raises(schedule.ContractError, match="--max-parallel must be at least 1"):
        call_main(schedule, monkeypatch, capsys, "--graph", graph, "--max-parallel", "0")
