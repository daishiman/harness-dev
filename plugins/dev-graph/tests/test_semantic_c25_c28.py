from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
HOOKS = PLUGIN / "hooks"
sys.path.insert(0, str(SCRIPTS))
from _common import ContractError  # noqa: E402


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *argv, stdin=None):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stdin or {})))
    code = module.main()
    text = capsys.readouterr().out
    return code, json.loads(text) if text else None


def git_context(monkeypatch, module, root: Path, common: Path) -> None:
    values = {
        ("rev-parse", "--git-common-dir"): str(common),
        ("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"): "refs/remotes/origin/main",
        ("rev-parse", "origin/main"): "REMOTE",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "main",
        ("status", "--porcelain"): "",
        ("remote", "get-url", "origin"): "git@example/repo.git",
    }
    monkeypatch.setattr(module, "git", lambda args, cwd, check=True: values.get(tuple(args), ""))


def test_c25_passes_complete_context_to_async_dispatch_without_blocking(tmp_path, monkeypatch, capsys):
    module = load(HOOKS / "reconcile-task-lifecycle.py", "semantic_c25")
    calls = []

    def invoke(path, *args):
        calls.append((path.name, args))
        if path.name == "resolve-repo-context.py":
            return {"ok": True, "exit_code": 0, "result": {
                "repository_id": "R", "head_sha": "H",
                "coordination_paths": {"root": str(tmp_path / "coord")},
                "local_state_paths": {"config": str(tmp_path / "missing.json")},
            }}
        return {"ok": True, "exit_code": 0, "result": {}}

    monkeypatch.setattr(module, "invoke", invoke)
    dispatched = []
    monkeypatch.setattr(module, "dispatch_once", lambda ledger, key, script, argv: dispatched.append((ledger, key, script, argv)) or {"ok": False, "spawned": False})
    code, _ = call_main(
        module, monkeypatch, capsys, "--event", "post-tool-use", "--repo-root", tmp_path,
        "--graph", "graph.json", "--graph-node-id", "G1", "--github-repo", "o/r", "--pr", "7",
        stdin={"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
               "session_id": "S", "tool_use_id": "T", "tool_input": {"command": "git push"}, "tool_response": {"exit_code": 0}},
    )
    assert code == 0
    assert len(dispatched) == 1
    argv = dispatched[0][3]
    for expected in ("--graph", "graph.json", "--graph-node-id", "G1", "--repo", "o/r", "--pr", "7"):
        assert expected in argv

    dispatched.clear()
    code, receipt = call_main(
        module, monkeypatch, capsys, "--event", "post-tool-use", "--repo-root", tmp_path,
        stdin={"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
               "session_id": "S", "tool_use_id": "T2", "tool_input": {"command": "gh pr merge 7"}, "tool_response": {"exit_code": 0}},
    )
    assert code == 0 and "reconcile context missing" in receipt["actions"][-1]["noop"]
    assert dispatched == []


def test_c28_workspace_parity_and_supported_gate_contract(tmp_path, monkeypatch, capsys):
    module = load(SCRIPTS / "bd-bridge.py", "semantic_c28")
    monkeypatch.setattr(module, "run", lambda *a, **k: SimpleNamespace(stdout="bd version 1.1.0", returncode=0))
    monkeypatch.setattr(module, "bd", lambda *a, **k: {"database_path": "/db/a", "path": "/workspace", "prefix": "x", "schema_version": 1})
    identity = module.preflight(tmp_path)["workspace_identity"]
    assert identity["workspace_id"].startswith("bdw_")
    with pytest.raises(module.ContractError, match="different Beads workspace"):
        module.preflight(tmp_path, "bdw_wrong")

    issue = {"id": "B1", "status": "open", "dependencies": [{"id": "B0"}]}
    assert module.verify_parity(issue, "open", ["B0"])["confirmed"] is True
    with pytest.raises(module.ContractError, match="parity conflict"):
        module.verify_parity(issue, "open", [])

    calls = []
    monkeypatch.setattr(module, "preflight", lambda root: {"version": "1.1.0", "workspace_identity": identity})

    def fake_bd(args, cwd, check=True):
        calls.append(args)
        if args[:3] == ["gate", "list", "--all"]: return []
        if args[:2] == ["gate", "create"]: return {"id": "gate-1"}
        return issue

    monkeypatch.setattr(module, "bd", fake_bd)
    code, _ = call_main(module, monkeypatch, capsys, "--op", "gate-add", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--pr", "9")
    assert code == 0
    assert any(args[:2] == ["gate", "create"] and "--blocks" in args and "--await-id" in args for args in calls)
    assert not any(args[:2] == ["gate", "add"] for args in calls)


def test_c27_beads_claim_saga_and_compensation(tmp_path, monkeypatch, capsys):
    module = load(SCRIPTS / "manage-worktree-lease.py", "semantic_c27")
    common = tmp_path / "common"; common.mkdir()
    ctx = {"repo_root": str(tmp_path), "git_common_dir": str(common), "repository_id": "R", "worktree_id": "wt_" + "1" * 16, "branch": "devgraph/G1", "base_branch": "main", "head_sha": "1" * 40}
    monkeypatch.setattr(module, "context", lambda root, resolver=None: dict(ctx))
    monkeypatch.setattr(module, "_ensure_claim_branch", lambda root, node_id, requested, current: {**current, "branch": f"devgraph/{node_id}"})
    graph = tmp_path / "graph.json"; graph.write_text('{"nodes": []}')
    consumer_calls = []
    def consumer(root, path, graph_path, lease, actual_context):
        consumer_calls.append((path, graph_path, lease["graph_node_id"]))
        return {"owner": "C02/run-dev-graph-node", "status": "applied", "graph_node_id": lease["graph_node_id"], "worktree_id": lease["worktree_id"]}
    monkeypatch.setattr(module, "invoke_execution_context_consumer", consumer)
    bridge_calls = []

    def bridge(root, path, argv):
        bridge_calls.append(argv)
        return {"workspace_identity": {"workspace_id": "bdw_same"}, "result": {"status": "in_progress"}}

    monkeypatch.setattr(module, "invoke_bd_bridge", bridge)
    args = ("--repo-root", tmp_path, "--op", "claim", "--graph", graph, "--graph-node-id", "G1", "--session-id", "S1", "--branch", "devgraph/G1", "--tracker-binding", "beads", "--bd-issue-id", "B1", "--expected-depends-on", "B0")
    code, receipt = call_main(module, monkeypatch, capsys, *args)
    assert code == 0 and receipt["lease"]["state"] == "claimed"
    assert receipt["workspace_identity"] == "bdw_same"
    assert receipt["writer_receipt"]["owner"] == "C02/run-dev-graph-node"
    assert receipt["lease"]["execution_context_projection"] == "applied" and consumer_calls
    assert "--verify-parity" in bridge_calls[0] and "B0" in bridge_calls[0]
    call_main(module, monkeypatch, capsys, *args)
    assert len(bridge_calls) == 1, "same owner claim is idempotent"

    monkeypatch.setattr(module, "invoke_bd_bridge", lambda *a, **k: (_ for _ in ()).throw(module.ContractError("bd claim failed")))
    with pytest.raises(module.ContractError, match="bd claim failed"):
        call_main(module, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "claim", "--graph", graph, "--graph-node-id", "G2", "--session-id", "S2", "--tracker-binding", "beads", "--bd-issue-id", "B2")
    ledger = json.loads((common / "dev-graph" / "leases.json").read_text())
    failed = next(row for row in ledger["leases"] if row["graph_node_id"] == "G2")
    assert failed["state"] == "released"
    assert failed["compensation"] == "reservation_released_after_bd_claim_failure"


def test_c26_requires_c02_receipt_and_gates_exact13_rollup(tmp_path, monkeypatch):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "semantic_c26")
    children = []
    for i in range(1, 14):
        phase = f"P{i:02d}"
        reference = f"evidence/{phase}.json"
        children.append({"graph_node_id": f"T{i}", "status": "done", "parent_feature": "F", "feature_package_id": "feature-package/F", "phase_ref": phase, "file_path": f"tasks/{phase}.md", "completion_evidence": {"status": "done", "evidence_refs": [reference]}})
        if phase in module.EVIDENCE_PHASES:
            (tmp_path / "tasks").mkdir(exist_ok=True); (tmp_path / "evidence").mkdir(exist_ok=True)
            (tmp_path / reference).write_text(json.dumps({"result": "PASS", "covered_task_ids": [f"T{i}"], "feature_acceptance": ["A"]}))
            (tmp_path / f"tasks/{phase}.md").write_text(f'---\ngraph_node_id: "T{i}"\nstatus: "done"\nphase_ref: "{phase}"\n---\n## Verification and evidence\n\n- Required evidence: {reference}\n')
    registration = tmp_path / "registration.json"; registration.write_text(json.dumps({"status": "registered", "expected_count": 13, "applied_count": 13, "phase_refs": module.PHASES, "node_ids": [f"T{i}" for i in range(1, 14)], "feature_package_id": "feature-package/F", "parent_feature": "F"}))
    feature = {"graph_node_id": "F", "artifact_kind": "feature", "status": "active", "acceptance": ["A"]}
    rollup = module.feature_rollup(tmp_path, [feature, *children], children[0], str(registration))
    assert rollup and rollup["eligible"] is True
    children[9]["completion_evidence"]["evidence_refs"] = []
    rollup = module.feature_rollup(tmp_path, [feature, *children], children[0], str(registration))
    assert rollup and rollup["eligible"] is False and any("P10" in item for item in rollup["blockers"])
    assert "atomic_json(graph_path" not in (SCRIPTS / "reconcile-github-lifecycle.py").read_text()


def test_c26_fails_closed_on_malformed_remote_and_graph(tmp_path, monkeypatch):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "semantic_c26_errors")
    monkeypatch.setenv("DEV_GRAPH_GH_FIXTURE", "{")
    with pytest.raises(module.ContractError, match="is invalid JSON"):
        module.c12_lifecycle_facts(tmp_path, tmp_path / "gh-bridge.py", "o/r", 1)
    with pytest.raises(module.ContractError, match="graph nodes"):
        module._nodes({"nodes": "not-an-array"})
    monkeypatch.setattr(module, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"op":"close"}', stderr=""))
    assert module._invoke_bd_close(tmp_path, tmp_path / "bd-bridge.py", "B1", None, "event")["op"] == "close"
    graph = tmp_path / "graph.json"; graph.write_text('{"graph_revision":0,"nodes":[]}')
    bad_writer = tmp_path / "writer.json"; bad_writer.write_text("{}")
    with pytest.raises(module.ContractError, match="not applied"):
        module._writer_applied(str(bad_writer), {"task_patch": {"graph_node_id": "G"}}, graph, tmp_path)
