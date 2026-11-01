"""schedule-graph does not recommend system-dev-planner for a feature whose exact-13 package is registered.

A feature that its package members name as ``parent_feature`` was already planned. Its tasks are the execution
candidates; putting the feature in the feature ready set too would launch the planner for it a second time.
The feature is reported in ``planned_features`` instead, for both ready sources.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(script: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def ready_node(node_id: str, **overrides):
    node = {
        "graph_node_id": node_id,
        "artifact_kind": "task",
        "status": "active",
        "confirmation_status": "confirmed",
        "evaluation_status": "pass",
        "implementation_readiness": {"status": "complete"},
        "depends_on": [],
        "resource_scope": [],
    }
    node.update(overrides)
    return node


def schedule(tmp_path, monkeypatch, capsys, nodes, ready_set=None):
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    argv = ["--graph", graph]
    if ready_set is not None:
        ready = tmp_path / "ready.json"
        ready.write_text(json.dumps({"ready_set": ready_set}), encoding="utf-8")
        argv += ["--ready-source", "bd-bridge", "--ready-json", ready]
    module = load("schedule-graph.py", "schedule_graph_planned_features")
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, argv)])
    code = module.main()
    return code, json.loads(capsys.readouterr().out.strip())


def package_graph():
    return [
        ready_node("feature-planned", artifact_kind="feature"),
        ready_node("feature-new", artifact_kind="feature"),
        ready_node("task-p01", parent_feature="feature-planned", feature_package_id="pkg", phase_ref="P01"),
        ready_node("task-p02", parent_feature="feature-planned", feature_package_id="pkg", phase_ref="P02",
                   depends_on=["task-p01"]),
    ]


def test_a_feature_with_a_registered_package_is_planned_not_a_planner_candidate(tmp_path, monkeypatch, capsys):
    code, report = schedule(tmp_path, monkeypatch, capsys, package_graph())

    assert code == 0
    assert report["ready_set"] == {"features": ["feature-new"], "tasks": ["task-p01"]}
    assert report["batches"]["features"] == [["feature-new"]]
    assert report["planned_features"] == ["feature-planned"]
    assert [hint["graph_node_id"] for hint in report["assignment_hints"]] == ["task-p01"]


def test_the_bd_bridge_epic_of_a_planned_feature_is_also_kept_out(tmp_path, monkeypatch, capsys):
    ready_set = [{"external_ref": "feature-planned"}, {"external_ref": "task-p01"}]

    code, report = schedule(tmp_path, monkeypatch, capsys, package_graph(), ready_set)

    assert code == 0
    assert report["ready_set"] == {"features": [], "tasks": ["task-p01"]}
    assert report["planned_features"] == ["feature-planned"] and report["unmapped"] == []


def test_a_planned_feature_that_is_not_ready_is_not_reported(tmp_path, monkeypatch, capsys):
    nodes = package_graph()
    nodes[0]["confirmation_status"] = "draft"

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes)

    assert code == 0
    assert report["ready_set"]["features"] == ["feature-new"] and report["planned_features"] == []
