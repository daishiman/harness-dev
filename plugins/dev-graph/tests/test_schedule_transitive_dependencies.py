"""schedule-graph puts a node in the ready set only when every dependency it reaches is done, not only the direct ones.

run-dev-graph-schedule's SKILL.md requires every ``depends_on`` to be done. A done or closed node can still
depend on an open one (C02 accepts ``status`` and ``depends_on`` patches, and C11 does not reject the pair),
so a check of the direct dependencies alone let that node's dependents into the ready set. Two nodes with
the same id fail closed: building ``by_id`` would keep only the last one and hide the other.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


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
        "id": node_id,
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


def schedule_args(tmp_path, nodes, ready_set=None):
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    args = ["--graph", graph]
    if ready_set is not None:
        ready = tmp_path / "ready.json"
        ready.write_text(json.dumps({"ready_set": ready_set}), encoding="utf-8")
        args += ["--ready-source", "bd-bridge", "--ready-json", ready]
    return args


def schedule(tmp_path, monkeypatch, capsys, nodes, ready_set=None):
    module = load("schedule-graph.py", "schedule_graph_transitive_dependencies")
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, schedule_args(tmp_path, nodes, ready_set))])
    code = module.main()
    return code, json.loads(capsys.readouterr().out.strip())


@pytest.mark.parametrize(("done_status", "open_status"), [("done", "draft"), ("closed", "active")])
def test_a_done_dependency_that_depends_on_an_open_node_keeps_its_dependent_out(
    tmp_path, monkeypatch, capsys, done_status, open_status
):
    nodes = [
        ready_node("upstream", status=open_status, confirmation_status="draft"),
        ready_node("middle", status=done_status, depends_on=["upstream"]),
        ready_node("leaf", depends_on=["middle"]),
        ready_node("free"),
    ]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes)

    assert code == 0
    assert report["ready_set"]["tasks"] == ["free"]


def test_the_bd_bridge_ready_set_is_checked_through_the_same_transitive_rule(tmp_path, monkeypatch, capsys):
    nodes = [
        ready_node("upstream", status="draft", confirmation_status="draft"),
        ready_node("middle", status="done", depends_on=["upstream"]),
        ready_node("leaf", depends_on=["middle"]),
        ready_node("free"),
    ]
    ready_set = [{"external_ref": "leaf"}, {"external_ref": "free"}]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes, ready_set)

    assert code == 0
    assert report["ready_set"]["tasks"] == ["free"]
    assert report["unmapped"] == []


def test_a_chain_and_a_diamond_of_done_dependencies_still_schedule(tmp_path, monkeypatch, capsys):
    nodes = [
        ready_node("root", status="done"),
        ready_node("left", status="done", depends_on=["root"]),
        ready_node("right", status="closed", depends_on=["root"]),
        ready_node("leaf", depends_on=["left", "right"]),
    ]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes)

    assert code == 0
    assert report["ready_set"]["tasks"] == ["leaf"]


def test_a_dependency_missing_from_the_graph_keeps_its_dependent_out(tmp_path, monkeypatch, capsys):
    nodes = [
        ready_node("middle", status="done", depends_on=["ghost"]),
        ready_node("leaf", depends_on=["middle"]),
        ready_node("orphan", depends_on=["ghost"]),
    ]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes)

    assert code == 0
    assert report["ready_set"]["tasks"] == []


def test_cycles_end_and_keep_out_a_candidate_that_reaches_itself(tmp_path, monkeypatch, capsys):
    # C11 rejects cycles, but schedule must not loop forever when handed one; ``seen`` ends the walk.
    nodes = [
        ready_node("loop-a", depends_on=["loop-b"]),
        ready_node("loop-b", status="done", depends_on=["loop-a"]),
        ready_node("ring-x", status="done", depends_on=["ring-y"]),
        ready_node("ring-y", status="done", depends_on=["ring-x"]),
        ready_node("self-loop", status="done", depends_on=["self-loop"]),
        ready_node("after-ring", depends_on=["ring-x"]),
        ready_node("after-self", depends_on=["self-loop"]),
    ]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes)

    assert code == 0
    assert report["ready_set"]["tasks"] == ["after-ring", "after-self"]


def test_duplicate_node_ids_fail_closed(tmp_path, monkeypatch, capsys):
    # With by_id built by a dict comprehension, the ready twin listed last hid the blocked one.
    module = load("schedule-graph.py", "schedule_graph_transitive_dependencies")
    nodes = [
        ready_node("upstream", status="draft", confirmation_status="draft"),
        ready_node("twin", depends_on=["upstream"]),
        ready_node("twin"),
    ]
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, schedule_args(tmp_path, nodes))])

    with pytest.raises(module.ContractError, match=r"duplicate graph node ids: \['twin'\]"):
        module.main()
    assert capsys.readouterr().out == ""
