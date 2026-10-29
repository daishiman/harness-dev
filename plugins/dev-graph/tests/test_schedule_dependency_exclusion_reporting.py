"""schedule-graph.py は依存未充足で ready から外した node を理由つきで報告する。

ready 判定が node を外す理由は 3 つ (--scope の選択外・非 schedulable・依存未充足) あり、
依存未充足だけが黙って消えないよう条件を分けて扱う。外した node は `excluded[]` へ
reason="dependency_unsatisfied" と blocking_depends_on を付けて機械可読に残す
(references/schedule-graph-contract.md)。`unmapped[]` は ready payload と graph の対応失敗だけを持つ。
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


def test_schedule_reports_unsatisfied_dependencies_without_misclassifying_other_exclusions(
    tmp_path, monkeypatch, capsys,
):
    schedule = load("schedule-graph.py", "schedule_dependency_exclusion_report")
    graph = tmp_path / "graph.json"
    base = {
        "artifact_kind": "task",
        "status": "active",
        "confirmation_status": "confirmed",
        "evaluation_status": "pass",
        "implementation_readiness": {"status": "complete"},
        "tracker_binding": "none",
        "parent_feature": "selected-feature",
    }
    graph.write_text(json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": [
        {"artifact_kind": "feature", "graph_node_id": "selected-feature", "status": "draft", "depends_on": []},
        {"artifact_kind": "feature", "graph_node_id": "outside-feature", "status": "draft", "depends_on": []},
        {**base, "graph_node_id": "upstream-open", "depends_on": [], "resource_scope": ["src/upstream.py"]},
        {**base, "graph_node_id": "blocked", "depends_on": ["upstream-open"], "resource_scope": ["src/blocked.py"]},
        {
            **base,
            "graph_node_id": "not-schedulable",
            "evaluation_status": "pending",
            "depends_on": ["upstream-open"],
            "resource_scope": ["src/not-schedulable.py"],
        },
        {
            **base,
            "graph_node_id": "outside-selection",
            "parent_feature": "outside-feature",
            "depends_on": ["upstream-open"],
            "resource_scope": ["src/outside-selection.py"],
        },
        {**base, "graph_node_id": "ready", "depends_on": [], "resource_scope": ["src/ready.py"]},
    ]}), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys, "--graph", graph, "--scope", "selected-feature")

    assert code == 0
    assert plan["scope"] == "selected-feature"
    assert plan["ready_set"]["tasks"] == ["ready", "upstream-open"]
    # 選択外 (outside-selection) と非 schedulable (not-schedulable) は依存未充足として数えない。
    assert plan["excluded"] == [{
        "graph_node_id": "blocked",
        "reason": "dependency_unsatisfied",
        "blocking_depends_on": ["upstream-open"],
        "source": "schedule-graph",
    }]
    assert plan["unmapped"] == []


def test_dependency_report_names_the_open_node_behind_a_done_one(tmp_path, monkeypatch, capsys):
    """done の依存を通り抜けた先の未完了 node と、graph に無い依存を blocker として名指しする。"""
    schedule = load("schedule-graph.py", "schedule_dependency_exclusion_transitive")
    graph = tmp_path / "graph.json"
    ready = {
        "artifact_kind": "task",
        "status": "active",
        "confirmation_status": "confirmed",
        "evaluation_status": "pass",
        "implementation_readiness": {"status": "complete"},
        "resource_scope": [],
    }
    graph.write_text(json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": [
        {"graph_node_id": "open", "status": "active", "depends_on": []},
        {"graph_node_id": "done-on-open", "status": "done", "depends_on": ["open"]},
        {**ready, "graph_node_id": "leaf", "depends_on": ["done-on-open", "missing"]},
    ]}), encoding="utf-8")

    code, plan = call_main(schedule, monkeypatch, capsys, "--graph", graph)

    assert code == 0
    assert plan["ready_set"]["tasks"] == []
    assert plan["excluded"] == [{
        "graph_node_id": "leaf",
        "reason": "dependency_unsatisfied",
        "blocking_depends_on": ["missing", "open"],
        "source": "schedule-graph",
    }]


def test_unknown_scope_stops_instead_of_scheduling_everything(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "schedule_dependency_exclusion_scope")
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    with pytest.raises(schedule.ContractError, match="unknown --scope graph node: ghost"):
        call_main(schedule, monkeypatch, capsys, "--graph", graph, "--scope", "ghost")
