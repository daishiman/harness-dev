"""schedule-graph.py は bd ready payload に entry の無い beads node を黙って落とさない。

tracker_binding=beads の node に対応する entry が `--ready-json` に無いとき、その node は
ready にも入らないが、消えもしない。`excluded[]` へ reason="ready_payload_entry_absent" で残り、
schedulable な候補は必ず ready_set・excluded・conflicts のどれかに現れる
(references/schedule-graph-contract.md)。
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


def task(node_id: str, **overrides):
    node = {
        "graph_node_id": node_id,
        "artifact_kind": "task",
        "status": "active",
        "confirmation_status": "confirmed",
        "evaluation_status": "pass",
        "implementation_readiness": {"status": "complete"},
        "depends_on": [],
        "tracker_binding": "beads",
        "resource_scope": [f"src/{node_id}.py"],
    }
    node.update(overrides)
    return node


def write_graph(path: Path, nodes: list[dict]) -> None:
    path.write_text(json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": nodes}), encoding="utf-8")


def confirmed_entry(node_id: str, depends_on: list[str] | None = None, status: str = "active") -> dict:
    return {
        "bd_issue_id": f"bd-{node_id}",
        "external_ref": node_id,
        "edge_parity": {"confirmed": True},
        "graph_status": status,
        "graph_depends_on": depends_on or [],
    }


def covered(plan: dict) -> set[str]:
    return (
        set(plan["ready_set"]["features"]) | set(plan["ready_set"]["tasks"])
        | {row["graph_node_id"] for row in plan["excluded"]} | set(plan["conflicts"])
    )


def test_schedule_reports_beads_node_missing_from_ready_payload(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_beads_ready_entry_absent_report")
    graph = tmp_path / "graph.json"
    nodes = [task("beads-with-entry"), task("beads-missing-entry")]
    write_graph(graph, nodes)
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({
        "parity_provenance": {
            "generated_at": "2026-07-21T00:00:00Z",
            "source_graph_digest": schedule._canonical_digest(json.loads(graph.read_text())),
        },
        "ready_set": [confirmed_entry("beads-with-entry")],
    }), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys,
                           "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)

    assert code == 0
    assert plan["ready_set"]["tasks"] == ["beads-with-entry"]
    assert plan["excluded"] == [{
        "graph_node_id": "beads-missing-entry",
        "tracker_binding": "beads",
        "reason": "ready_payload_entry_absent",
        "source": "schedule-graph",
    }]
    assert plan["unmapped"] == []
    assert {node["graph_node_id"] for node in nodes} <= covered(plan)


def test_schedule_treats_parity_dependency_order_as_a_set(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_beads_dependency_order")
    graph = tmp_path / "graph.json"
    write_graph(graph, [
        {"graph_node_id": "upstream-a", "status": "done", "depends_on": []},
        {"graph_node_id": "upstream-b", "status": "closed", "depends_on": []},
        task("beads-order-independent", depends_on=["upstream-b", "upstream-a"]),
    ])
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({
        "ready_set": [confirmed_entry("beads-order-independent", ["upstream-a", "upstream-b"])],
    }), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys,
                           "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)

    assert code == 0
    assert plan["ready_set"]["tasks"] == ["beads-order-independent"]
    assert plan["excluded"] == [] and plan["unmapped"] == []


def test_unconfirmed_or_stale_parity_is_excluded_with_what_was_observed(tmp_path, monkeypatch, capsys):
    """entry はあっても parity 未確認・status 不一致・依存集合の不一致なら ready にしない。"""
    schedule = load("schedule-graph.py", "schedule_beads_parity_stale")
    graph = tmp_path / "graph.json"
    write_graph(graph, [
        {"graph_node_id": "upstream", "status": "done", "depends_on": []},
        task("unconfirmed"),
        task("status-drift"),
        task("edge-drift", depends_on=["upstream"]),
    ])
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({"ready_set": [
        {**confirmed_entry("unconfirmed"), "edge_parity": {"confirmed": False, "missing_edges": ["x"]}},
        confirmed_entry("status-drift", status="draft"),
        confirmed_entry("edge-drift", []),
    ]}), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys,
                           "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)

    assert code == 0
    assert plan["ready_set"]["tasks"] == []
    rows = {row["graph_node_id"]: row for row in plan["excluded"]}
    assert set(rows) == {"unconfirmed", "status-drift", "edge-drift"}
    assert {row["reason"] for row in rows.values()} == {"beads_parity_stale_or_unconfirmed"}
    assert rows["unconfirmed"]["observed_edge_parity"] == {"confirmed": False, "missing_edges": ["x"]}
    assert (rows["status-drift"]["expected_status"], rows["status-drift"]["observed_status"]) == ("active", "draft")
    assert (rows["edge-drift"]["expected_depends_on"], rows["edge-drift"]["observed_depends_on"]) == (["upstream"], [])
    assert rows["edge-drift"]["bd_issue_id"] == "bd-edge-drift"


def test_payload_rows_that_cannot_be_mapped_are_kept_with_a_reason(tmp_path, monkeypatch, capsys):
    """graph と対応しない payload 行と、C28 が自分で落とした行は unmapped に理由つきで残る。"""
    schedule = load("schedule-graph.py", "schedule_beads_unmapped_rows")
    graph = tmp_path / "graph.json"
    write_graph(graph, [task("known")])
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({
        "ready_set": ["not-an-object", {"bd_issue_id": "bd-x"}, confirmed_entry("known"), confirmed_entry("gone")],
        "unmapped": [{"bd_issue_id": "bd-u", "external_ref": "u", "reason": "parity_manifest_missing"}],
        "conflicts": [{"bd_issue_id": "bd-c", "graph_node_id": "c", "reason": "status_conflict"}],
    }), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys,
                           "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)

    assert code == 0
    assert plan["ready_set"]["tasks"] == ["known"]
    assert [(row["reason"], row["source"]) for row in plan["unmapped"]] == [
        ("parity_manifest_missing", "bd-bridge"),
        ("status_conflict", "bd-bridge"),
        ("not_an_object", "schedule-graph"),
        ("missing_external_ref", "schedule-graph"),
        ("graph_node_missing", "schedule-graph"),
    ]

    ready.write_text(json.dumps({"ready_set": [confirmed_entry("known"), confirmed_entry("known")]}), encoding="utf-8")
    with pytest.raises(schedule.ContractError, match="duplicate external_ref in Beads ready payload: known"):
        call_main(schedule, monkeypatch, capsys, "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)


def test_stale_parity_provenance_and_unresolved_binding_stop_the_schedule(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_beads_stale_provenance")
    graph = tmp_path / "graph.json"
    write_graph(graph, [task("known")])
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({
        "parity_provenance": {"source_graph_digest": "sha256:" + "0" * 64},
        "ready_set": [confirmed_entry("known")],
    }), encoding="utf-8")
    with pytest.raises(schedule.ContractError, match="beads parity snapshot is stale"):
        call_main(schedule, monkeypatch, capsys, "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)

    write_graph(graph, [task("known", tracker_binding="repo-config-default")])
    ready.write_text(json.dumps({"ready_set": [confirmed_entry("known")]}), encoding="utf-8")
    with pytest.raises(schedule.ContractError, match="unresolved tracker_binding 'repo-config-default'"):
        call_main(schedule, monkeypatch, capsys, "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)


def test_schedule_fails_closed_when_p01_parent_is_missing(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_missing_p01_parent")
    graph = tmp_path / "graph.json"
    write_graph(graph, [task(
        "orphan-p01", phase_ref="P01", parent_feature="missing-feature", tracker_binding="none",
    )])

    with pytest.raises(schedule.ContractError, match="P01 task requires a graph parent_feature"):
        call_main(schedule, monkeypatch, capsys, "--graph", graph)


def test_schedule_candidate_coverage_accounts_for_active_lease_conflicts(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_candidate_coverage_with_lease")
    graph = tmp_path / "graph.json"
    write_graph(graph, [task("leased-ready-node", tracker_binding="none", resource_scope=["src/leased.py"])])
    leases = tmp_path / "leases.json"
    leases.write_text(json.dumps({"leases": [{
        "graph_node_id": "leased-ready-node",
        "resource_scope": ["src/leased.py"],
        "state": "claimed",
        "expires_at": "2099-01-01T00:00:00+00:00",
    }]}), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys, "--graph", graph, "--leases", leases)

    assert code == 0
    assert plan["ready_set"]["tasks"] == [] and plan["excluded"] == []
    assert covered(plan) == {"leased-ready-node"}
    assert plan["conflict_pairs"] == [{
        "left": "leased-ready-node", "right": "active-lease", "kind": "lease", "resources": ["src/leased.py"],
    }]
