"""schedule-graph compares resource_scope as repository-relative paths, not as raw strings.

graph-node.schema.json defines resource_scope as the files/directories a node touches. Spellings of the
same directory (``./packages/api``, ``packages/api/``) and a file under it must not share a parallel
batch, a sibling whose name only shares a string prefix (``packages/apix``) must, an ancestor held by a
lease must keep its descendants out of the ready set, and a path outside the repository fails closed.
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


def call_main(module, monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, args)])
    code = module.main()
    output = capsys.readouterr().out.strip()
    return code, json.loads(output)


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


def schedule(tmp_path, monkeypatch, capsys, nodes, leases=None):
    module = load("schedule-graph.py", "schedule_graph_scope_paths")
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    args = ["--graph", graph]
    if leases is not None:
        lease_file = tmp_path / "leases.json"
        lease_file.write_text(json.dumps({"leases": leases}), encoding="utf-8")
        args += ["--leases", lease_file]
    return call_main(module, monkeypatch, capsys, *args)


def test_spellings_of_one_directory_and_a_file_under_it_never_share_a_batch(tmp_path, monkeypatch, capsys):
    nodes = [
        ready_node("a1", resource_scope=["packages/api"]),
        ready_node("a2", resource_scope=["packages/api/users.py"]),
        ready_node("a3", resource_scope=["./packages/api"]),
        ready_node("a4", resource_scope=["packages/api/"]),
    ]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes)

    assert code == 0
    assert report["ready_set"]["tasks"] == ["a1", "a2", "a3", "a4"]
    assert report["batches"]["tasks"] == [["a1"], ["a2"], ["a3"], ["a4"]]


def test_sibling_sharing_only_a_string_prefix_is_not_a_conflict(tmp_path, monkeypatch, capsys):
    nodes = [
        ready_node("api", resource_scope=["packages/api"]),
        ready_node("apix", resource_scope=["packages/apix"]),
    ]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes)

    assert code == 0
    assert report["batches"]["tasks"] == [["api", "apix"]]


@pytest.mark.parametrize("leased_scope", ["packages", "./packages/"])
def test_leased_ancestor_removes_descendant_task_from_candidates(tmp_path, monkeypatch, capsys, leased_scope):
    nodes = [
        ready_node("child", resource_scope=["packages/api/users.py"]),
        ready_node("web", resource_scope=["web"]),
    ]
    leases = [{"graph_node_id": "holder", "state": "claimed", "resource_scope": [leased_scope]}]

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes, leases)

    assert code == 0
    assert report["ready_set"]["tasks"] == ["web"]
    assert report["batches"]["tasks"] == [["web"]]
    assert report["conflicts"] == ["child"]


@pytest.mark.parametrize("scope", ["/etc/passwd", "..", "../outside", "packages/../../x"])
def test_node_scope_outside_the_repository_fails_closed(tmp_path, monkeypatch, capsys, scope):
    module = load("schedule-graph.py", "schedule_graph_scope_paths")
    nodes = [ready_node("escape", resource_scope=[scope])]
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [module.__file__, "--graph", str(graph)])

    with pytest.raises(module.ContractError, match="resource_scope"):
        module.main()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("scope", ["/srv/repo", "../outside"])
def test_lease_scope_outside_the_repository_fails_closed(tmp_path, monkeypatch, capsys, scope):
    module = load("schedule-graph.py", "schedule_graph_scope_paths")
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": [ready_node("web", resource_scope=["web"])]}), encoding="utf-8")
    leases = tmp_path / "leases.json"
    leases.write_text(json.dumps({"leases": [{"graph_node_id": "holder", "state": "claimed",
                                              "resource_scope": [scope]}]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [module.__file__, "--graph", str(graph), "--leases", str(leases)])

    with pytest.raises(module.ContractError, match="lease holder: resource_scope"):
        module.main()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("recorded", [None, []])
def test_lease_from_the_public_claim_path_holds_its_graph_node_scope(tmp_path, monkeypatch, capsys, recorded):
    # `/dev-graph worktree claim <id> --branch ... --session-id ...` passes no --resource, so C27
    # records resource_scope [] (or none). The leased node's graph scope must still keep overlapping
    # candidates out of the ready set and batches.
    nodes = [
        ready_node("holder", status="in_progress", resource_scope=["src/db"]),
        ready_node("migrations", resource_scope=["src/db/migrations"]),
        ready_node("web", resource_scope=["web"]),
    ]
    lease = {"graph_node_id": "holder", "state": "claimed"}
    if recorded is not None:
        lease["resource_scope"] = recorded

    code, report = schedule(tmp_path, monkeypatch, capsys, nodes, [lease])

    assert code == 0
    assert report["ready_set"]["tasks"] == ["web"]
    assert report["batches"]["tasks"] == [["web"]]
    assert report["conflicts"] == ["migrations"]


def test_lease_with_no_recorded_scope_and_no_graph_node_fails_closed(tmp_path, monkeypatch, capsys):
    module = load("schedule-graph.py", "schedule_graph_scope_paths")
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": [ready_node("web", resource_scope=["web"])]}), encoding="utf-8")
    leases = tmp_path / "leases.json"
    leases.write_text(json.dumps({"leases": [{"graph_node_id": "ghost", "state": "claimed",
                                              "resource_scope": []}]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [module.__file__, "--graph", str(graph), "--leases", str(leases)])

    with pytest.raises(module.ContractError, match="lease ghost: resource_scope is empty"):
        module.main()
    assert capsys.readouterr().out == ""
