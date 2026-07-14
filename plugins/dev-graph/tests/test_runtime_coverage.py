from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
HOOKS = PLUGIN / "hooks"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def common():
    return load(SCRIPTS / "_common.py", "_common")


def call_main(module, monkeypatch, capsys, *args, stdin=None):
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, args)])
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stdin)))
    code = module.main()
    output = capsys.readouterr().out.strip()
    return code, json.loads(output) if output else None


def test_common_primitives(common, tmp_path, monkeypatch, capsys):
    cp = SimpleNamespace(returncode=0, stdout=" ok \n", stderr="")
    monkeypatch.setattr(common.subprocess, "run", lambda *a, **k: cp)
    assert common.run(["tool"]).stdout == " ok \n"
    assert common.git(["status"], tmp_path) == "ok"
    bad = SimpleNamespace(returncode=3, stdout="", stderr="boom")
    monkeypatch.setattr(common.subprocess, "run", lambda *a, **k: bad)
    with pytest.raises(common.ContractError, match="command failed"):
        common.run(["tool"])
    assert common.run(["tool"], check=False).returncode == 3

    def os_error(*a, **k):
        raise OSError("missing")

    monkeypatch.setattr(common.subprocess, "run", os_error)
    with pytest.raises(common.ContractError, match="cannot execute"):
        common.run(["missing"])

    target = tmp_path / "state.json"
    common.atomic_json(target, {"b": 2, "a": 1})
    assert common.load_json(target) == {"a": 1, "b": 2}
    target.write_text("{")
    with pytest.raises(common.ContractError, match="invalid JSON"):
        common.load_json(target)
    inside = tmp_path / "inside"; inside.mkdir()
    assert common.contained(inside, tmp_path) == inside
    with pytest.raises(common.ContractError, match="escapes"):
        common.contained(tmp_path.parent, tmp_path)
    assert common.stable_id("x_", "a") == common.stable_id("x_", "a")
    assert common.utc_now().endswith("Z")
    common.dump({"日本": True})
    assert json.loads(capsys.readouterr().out)["日本"] is True


def test_resolve_discover_and_main(common, tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "resolve-repo-context.py", "resolve_repo_context_cov")
    root = tmp_path / "repo"; root.mkdir(); (root / ".git").mkdir()
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(mod.Path, "cwd", classmethod(lambda cls: root))
    monkeypatch.setattr(mod, "git", lambda args, r, check=True: str(root) if args[-1] == "--show-toplevel" else "")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    assert mod.discover(str(root)) == (root, "explicit --repo-root")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    with pytest.raises(common.ContractError, match="disagree"):
        mod.discover(str(root))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    common_dir = root / ".git"; (common_dir / "HEAD").write_text("ref: refs/heads/main\n")
    (common_dir / "objects").mkdir()
    (common_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
    config = root / ".dev-graph" / "config.json"; config.parent.mkdir()
    config.write_text(json.dumps({"worktrees": {"default_branch": "trunk"}}))
    values = {
        ("rev-parse", "--git-common-dir"): ".git",
        ("rev-parse", "--git-dir"): ".git",
        ("rev-parse", "--git-path", "objects"): ".git/objects",
        ("rev-parse", "--git-path", "config"): ".git/config",
        ("remote", "get-url", "origin"): "git@example/repo.git",
        ("--git-dir", str(common_dir), "remote", "get-url", "origin"): "git@example/repo.git",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "feature/x",
        ("rev-parse", "HEAD"): "abc123",
        ("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"): "",
    }
    monkeypatch.setattr(mod, "discover", lambda explicit: (root, "test"))
    monkeypatch.setattr(mod, "git", lambda args, r, check=True: values.get(tuple(args), ""))
    code, result = call_main(mod, monkeypatch, capsys, "--repo-root", root)
    assert code == 0 and result["default_branch"] == "trunk"
    assert result["branch"] == "feature/x" and result["repository_id"].startswith("local:sha256:")

    config.unlink()
    code, result = call_main(mod, monkeypatch, capsys, "--repo-root", root)
    assert code == 0 and "config_missing" in result["diagnostics"]
    assert "default_branch_fallback_main" in result["diagnostics"]


def test_bd_helpers_and_all_operations(common, tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "bd-bridge.py", "bd_bridge_cov")
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout='{"id":"x"}', returncode=0))
    assert mod.bd(["show"], cwd=tmp_path)["id"] == "x"
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout="plain", returncode=4))
    assert mod.bd(["show"], cwd=tmp_path, check=False)["text"] == "plain"
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout="", returncode=0))
    assert mod.bd(["show"], cwd=tmp_path) == {"ok": True}
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout="bd version 1.4.2", returncode=0))
    monkeypatch.setattr(mod, "bd", lambda *a, **k: {"workspace": "w"})
    assert mod.preflight(tmp_path)["version"] == "1.4.2"
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout="bd 2.0.0", returncode=0))
    with pytest.raises(common.ContractError, match="unsupported"):
        mod.preflight(tmp_path)

    monkeypatch.setattr(mod, "preflight", lambda root: {"version": "1.4.2", "workspace_identity": {"id": "w"}})
    calls = []
    gates = []

    def fake_bd(args, cwd, check=True):
        calls.append(args)
        if args[0] == "search": return []
        if args[:2] == ["create", "--title"]: return {"id": "new"}
        if args[0] == "show": return {"id": args[1], "status": "open", "dependencies": []}
        if args[:3] == ["gate", "list", "--all"]: return gates
        if args[:2] == ["gate", "create"]:
            gate = {"id": "gate-1", "type": "gh:pr", "blocks": args[args.index("--blocks") + 1], "await_id": args[args.index("--await-id") + 1]}
            gates.append(gate); return gate
        return {"ok": True, "args": args}

    monkeypatch.setattr(mod, "bd", fake_bd)
    code, out = call_main(mod, monkeypatch, capsys, "--op", "create", "--repo-root", tmp_path, "--graph-node-id", "G1", "--title", "T")
    assert code == 0 and out["result"]["id"] == "new"
    for argv in (
        ("--op", "update", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--status", "in_progress", "--title", "T2"),
        ("--op", "close", "--repo-root", tmp_path, "--bd-issue-id", "B1"),
        ("--op", "claim", "--repo-root", tmp_path, "--bd-issue-id", "B1"),
        ("--op", "show", "--repo-root", tmp_path, "--bd-issue-id", "B1"),
        ("--op", "dep-add", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--depends-on", "B0"),
        ("--op", "ready", "--repo-root", tmp_path),
        ("--op", "github-push", "--repo-root", tmp_path),
        ("--op", "gate-add", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--pr", "7"),
        ("--op", "gate-check", "--repo-root", tmp_path, "--bd-issue-id", "B1", "--pr", "7"),
    ):
        assert call_main(mod, monkeypatch, capsys, *argv)[0] == 0
    code, out = call_main(mod, monkeypatch, capsys, "--op", "create", "--repo-root", tmp_path, "--dry-run")
    assert code == 0 and out["dry_run_preview"]["op"] == "create"

    monkeypatch.setattr(mod, "bd", lambda args, cwd, check=True: [{"id": "B9", "description": "external_ref:G9"}] if args[0] == "search" else {})
    _, out = call_main(mod, monkeypatch, capsys, "--op", "create", "--repo-root", tmp_path, "--graph-node-id", "G9", "--title", "T")
    assert out["result"]["idempotent"] is True


def test_validate_graph_schema_and_main(common, tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "validate-graph-schema.py", "validate_graph_cov")
    with pytest.raises(common.ContractError): mod.nodes_of({})
    assert mod.nodes_of([]) == []
    bad = [
        {"id": "dup", "status": "active", "depends_on": ["missing"], "artifact_kind": "bad", "tracker_binding": "beads", "github_publication": {"mode": "issue"}},
        {"id": "dup", "status": "weird", "depends_on": "bad", "tracker_binding": "github", "beads_linkage": {}},
        {"status": "draft", "depends_on": []},
    ]
    codes = {x["code"] for x in mod.validate(bad)}
    assert {"duplicate_id", "dangling_dependency", "invalid_kind", "invalid_status", "invalid_dependencies", "active_not_ready", "beads_publication", "binding_collision", "missing_id"} <= codes
    cycle = [{"id": "a", "status": "draft", "depends_on": ["b"]}, {"id": "b", "status": "draft", "depends_on": ["a"]}]
    assert any(x["code"] == "dependency_cycle" for x in mod.validate(cycle))
    package = [{"id": "feature", "artifact_kind": "feature", "status": "done", "depends_on": []}]
    for number in range(1, 14):
        package.append({
            "id": f"p{number}", "artifact_kind": "task", "status": "active",
            "depends_on": ["p13"] if number == 2 else [], "parent_feature": "feature",
            "feature_package_id": "pkg", "phase_ref": f"P{number:02d}",
            "confirmation_status": "confirmed", "evaluation_status": "pass",
            "implementation_readiness": {"status": "complete"},
        })
    package_codes = {x["code"] for x in mod.validate(package)}
    assert {"non_forward_phase_dependency", "premature_feature_done", "feature_evidence_missing"} <= package_codes

    graph = tmp_path / "graph.json"; graph.write_text(json.dumps({"nodes": [{"id": "x", "status": "draft", "depends_on": []}]}))
    code, out = call_main(mod, monkeypatch, capsys, "--graph", graph, "--repo-root", tmp_path)
    assert code == 1 and out["valid"] is False
    graph.write_text(json.dumps({"nodes": [{"id": "x", "status": "bad", "depends_on": []}]}))
    code, out = call_main(mod, monkeypatch, capsys, "--graph", graph, "--repo-root", tmp_path)
    assert code == 1 and out["valid"] is False


def test_gh_bridge_helpers_and_operations(common, tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "gh-bridge.py", "gh_bridge_cov")
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout='{"ok":true}'))
    assert mod.gh_json(["api"])["ok"] is True
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout="not-json"))
    with pytest.raises(common.ContractError, match="invalid JSON"): mod.gh_json(["api"])
    seen = []
    monkeypatch.setattr(mod, "gh_json", lambda argv: seen.append(argv) or {"data": {}})
    mod.graphql("Q", {"z": "2", "a": "1"})
    assert seen[0][-4:] == ["-F", "a=1", "-F", "z=2"]

    monkeypatch.setattr(mod, "gh_json", lambda argv: {"id": "I", "number": 1, "title": "T", "state": "OPEN", "url": "https://github.test/o/r/issues/1", "updatedAt": "2026-07-13T00:00:00Z"})
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(stdout="https://github.test/o/r/issues/1\n", returncode=0))
    for argv in (
        ("--op", "issue-fetch", "--repo", "o/r", "--number", "1"),
        ("--op", "issue-create", "--repo", "o/r", "--title", "T"),
        ("--op", "issue-update", "--repo", "o/r", "--number", "1", "--title", "N", "--body", "B"),
        ("--op", "issue-close", "--repo", "o/r", "--number", "1"),
        ("--op", "project-item-add", "--project-id", "P", "--content-id", "C"),
        ("--op", "project-item-edit", "--project-id", "P", "--item-id", "I", "--field-id", "F", "--option-id", "O"),
    ):
        assert call_main(mod, monkeypatch, capsys, *argv)[0] == 0
    _, out = call_main(mod, monkeypatch, capsys, "--op", "issue-create", "--repo", "o/r", "--dry-run")
    assert out["mutation_suppressed"] is True

    monkeypatch.setattr(mod, "graphql", lambda q, v: {"data": {"user": {"projectV2": {"id": "P", "fields": {"nodes": [{"name": "Status"}]}}}, "organization": {"projectV2": None}}})
    _, out = call_main(mod, monkeypatch, capsys, "--op", "project-resolve", "--owner", "o", "--project-number", "1")
    assert out["result"]["id"] == "P"
    pages = iter([
        {"data": {"node": {"items": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}}},
        {"data": {"node": {"items": {"nodes": [{"id": "X", "content": {"id": "C"}}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}},
    ])
    monkeypatch.setattr(mod, "graphql", lambda q, v: next(pages))
    _, out = call_main(mod, monkeypatch, capsys, "--op", "project-item-find", "--project-id", "P", "--content-id", "C")
    assert out["result"]["pages"] == 2 and len(out["result"]["items"]) == 1


def test_render_and_schedule(common, tmp_path, monkeypatch, capsys):
    render = load(SCRIPTS / "render-graph-html.py", "render_graph_cov")
    graph = tmp_path / "graph.json"; out = tmp_path / "out.html"
    graph.write_text(json.dumps({"nodes": [
        {"id": "feature", "title": "<Feature>", "artifact_kind": "feature", "status": "active", "depends_on": []},
        {"id": "a", "title": "<A>", "status": "done", "parent_feature": "feature", "depends_on": []},
        {"id": "b", "status": "active", "parent_feature": "feature", "depends_on": ["a"]},
    ]}))
    code, receipt = call_main(render, monkeypatch, capsys, "--graph", graph, "--out", out)
    assert code == 0
    assert {key: receipt[key] for key in ("edges", "nodes", "ok", "out")} == {
        "edges": 1, "nodes": 3, "ok": True, "out": str(out),
    }
    assert receipt["input_sha256"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    assert receipt["output_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert receipt["feature_progress"] == {
        "aggregate": {"done": 1, "total": 2},
        "by_feature": {"feature": {"done": 1, "total": 2}},
    }
    text = out.read_text()
    assert "&lt;A&gt;" in text and "<script type=\"application/json\"" in text
    assert "active · feature · 1/2" in text
    assert "https://" not in text and "http://" not in text
    with pytest.raises(common.ContractError, match="overwrite"):
        call_main(render, monkeypatch, capsys, "--graph", graph, "--out", graph)
    graph.write_text(json.dumps({"nodes": [{"id": "a", "depends_on": ["x"]}]}))
    with pytest.raises(common.ContractError, match="dangling"):
        call_main(render, monkeypatch, capsys, "--graph", graph, "--out", out)
    graph.write_text(json.dumps({"nodes": [{"id": "a", "parent_feature": "missing", "depends_on": []}]}))
    with pytest.raises(common.ContractError, match="dangling parent_feature"):
        call_main(render, monkeypatch, capsys, "--graph", graph, "--out", out)

    sched = load(SCRIPTS / "schedule-graph.py", "schedule_graph_cov")
    graph.write_text(json.dumps({"nodes": [
        {"id": "done", "status": "done", "depends_on": []},
        {"id": "f", "artifact_kind": "feature", "status": "active", "confirmation_status": "confirmed", "evaluation_status": "pass", "implementation_readiness": {"status": "complete"}, "depends_on": ["done"], "resource_scope": ["api"]},
        {"id": "t1", "artifact_kind": "task", "status": "active", "confirmation_status": "confirmed", "evaluation_status": "pass", "implementation_readiness": {"status": "complete"}, "depends_on": ["done"], "resource_scope": ["web"]},
        {"id": "t2", "artifact_kind": "task", "status": "active", "confirmation_status": "confirmed", "evaluation_status": "pass", "implementation_readiness": {"status": "complete"}, "depends_on": [], "resource_scope": ["web"]},
    ]}))
    code, plan = call_main(sched, monkeypatch, capsys, "--graph", graph)
    assert code == 0 and plan["ready_set"]["features"] == ["f"]
    assert plan["batches"]["tasks"] == [["t1"], ["t2"]]
    leases = tmp_path / "leases.json"; leases.write_text(json.dumps({"leases": [{"graph_node_id": "t1", "state": "claimed", "resource_scope": ["web"]}]}))
    _, plan = call_main(sched, monkeypatch, capsys, "--graph", graph, "--leases", leases)
    assert "t1" in plan["conflicts"] and "t2" in plan["conflicts"]
    ready = tmp_path / "ready.json"; ready.write_text(json.dumps({"ready_set": [{"external_ref": "t2"}, {"external_ref": "unknown"}]}))
    _, plan = call_main(sched, monkeypatch, capsys, "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready)
    assert plan["ready_source"] == "bd-bridge" and plan["unmapped"]

    graph.write_text(json.dumps({"nodes": [
        {"id": "legacy", "artifact_kind": "task", "status": "active", "confirmation_status": "confirmed", "evaluation_status": "pass", "implementation_readiness": {"status": "complete"}, "depends_on": [], "resource_scope": {"touches": ["unsafe"]}},
    ]}))
    with pytest.raises(common.ContractError, match="resource_scope must be"):
        call_main(sched, monkeypatch, capsys, "--graph", graph)


def test_render_receipt_hashes_progress_and_rejects_invalid_input(
    common, tmp_path, monkeypatch, capsys,
):
    render = load(SCRIPTS / "render-graph-html.py", "render_graph_receipt_contract")
    graph = tmp_path / "graph.json"
    out = tmp_path / "index.html"
    graph.write_bytes(json.dumps({"nodes": [
        {"id": "feature", "artifact_kind": "feature", "status": "active", "depends_on": []},
        {"id": "done", "status": "done", "parent_feature": "feature", "depends_on": []},
        {"id": "open", "status": "active", "parent_feature": "feature", "depends_on": ["done"]},
    ]}, sort_keys=True).encode("utf-8"))

    code, receipt = call_main(render, monkeypatch, capsys, "--graph", graph, "--out", out)

    assert code == 0
    assert receipt["input_sha256"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    assert receipt["output_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert receipt["feature_progress"]["by_feature"]["feature"] == {"done": 1, "total": 2}
    assert receipt["feature_progress"]["aggregate"] == {"done": 1, "total": 2}

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    rejected_out = tmp_path / "rejected.html"
    with pytest.raises(common.ContractError, match="invalid JSON"):
        call_main(render, monkeypatch, capsys, "--graph", invalid, "--out", rejected_out)
    assert not rejected_out.exists()


def test_worktree_lease_lifecycle(common, tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "manage-worktree-lease.py", "lease_cov")
    common_dir = tmp_path / "common"; common_dir.mkdir()
    resolved = {
        "repo_root": str(tmp_path), "git_common_dir": str(common_dir),
        "repository_id": "github:example/repo", "worktree_id": "wt_" + "1" * 16,
        "branch": "task/x", "default_branch": "main", "head_sha": "H",
    }
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(resolved), stderr=""))
    assert mod.context(tmp_path)["branch"] == "task/x"
    ctx = {"repo_root": str(tmp_path), "git_common_dir": str(common_dir), "repository_id": "R", "worktree_id": "wt_" + "1" * 16, "branch": "task/x", "base_branch": "main", "head_sha": "1" * 40}
    monkeypatch.setattr(mod, "context", lambda root, resolver=None: dict(ctx))
    monkeypatch.setattr(mod, "_ensure_claim_branch", lambda root, node_id, requested, current: {**current, "branch": f"devgraph/{node_id}"})
    monkeypatch.setattr(mod, "invoke_execution_context_consumer", lambda root, consumer, graph, lease, current: {"owner": "C02/run-dev-graph-node", "status": "applied", "graph_node_id": lease["graph_node_id"], "worktree_id": lease["worktree_id"]})
    graph = tmp_path / "graph.json"; graph.write_text('{"nodes": []}')
    assert call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "context")[0] == 0
    claim = ("--repo-root", tmp_path, "--op", "claim", "--graph", graph, "--graph-node-id", "G", "--session-id", "S", "--branch", "devgraph/G", "--resource", "web")
    _, result = call_main(mod, monkeypatch, capsys, *claim)
    assert result["lease"]["state"] == "claimed"
    _, result = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "heartbeat", "--graph-node-id", "G", "--session-id", "S")
    assert result["lease"]["state"] == "in_progress"
    _, result = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "park", "--graph-node-id", "G", "--session-id", "S")
    assert result["lease"]["state"] == "pending_review"
    events = common_dir / "dev-graph" / "events.json"
    event_data = json.loads(events.read_text()); event_data["events"].append({"type": "completion", "event_key": "E", "graph_node_id": "G", "repository_id": "R", "merge_commit_sha": "2" * 40, "policy_digest": "3" * 64}); events.write_text(json.dumps(event_data))
    _, result = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "system-release", "--graph-node-id", "G", "--completion-event-key", "E")
    assert result["lease"]["state"] == "released"
    _, listed = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "list")
    assert listed["leases"] and listed["events"]
    _, result = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "claim", "--graph", graph, "--graph-node-id", "G2", "--session-id", "S")
    _, result = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "release", "--graph-node-id", "G2", "--session-id", "S")
    assert result["lease"]["state"] == "released"
    with pytest.raises(common.ContractError, match="ttl"):
        call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--op", "context", "--ttl", "1")


def test_reconcile_lifecycle_modes(common, tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "reconcile-github-lifecycle.py", "reconcile_cov")
    common_dir = tmp_path / ".git"; common_dir.mkdir(); (common_dir / "dev-graph").mkdir()
    events = common_dir / "dev-graph" / "events.json"; events.write_text(json.dumps({"schema_version": "1.0", "events": [{"event_key": "old"}]}))
    values = {
        ("rev-parse", "--git-common-dir"): ".git",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "main",
        ("rev-parse", "HEAD"): "H",
        ("status", "--porcelain"): "",
        ("remote", "get-url", "origin"): "git@example/repo.git",
    }
    monkeypatch.setattr(mod, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(mod, "c24_context", lambda root, resolver: {
        "repo_root": str(root), "repository_id": "github:o/r", "git_common_dir": str(common_dir),
        "branch": "main", "head_sha": "H", "coordination_paths": {"root": str(common_dir / "dev-graph")},
    })
    code, out = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, "--mode", "drain-pending")
    assert code == 0 and out["pending_events"]
    tasks = tmp_path / "tasks"; tasks.mkdir(); (tasks / "G.md").write_text('---\ngraph_node_id: "G"\nstatus: "active"\n---\n## Verification and evidence\n\n- Automated commands: `pytest`\n- Required evidence: evidence/run.json\n')
    graph = tmp_path / "graph.json"; graph.write_text(json.dumps({"graph_revision": 0, "nodes": [{"id": "G", "status": "active", "tracker_binding": "none", "file_path": "tasks/G.md", "completion_evidence": {"policy": "linked_pr_merged_all", "evidence_refs": []}}]}))
    remote = {"repository": "o/r", "default_branch": {"name": "main", "oid": "H"}, "pull_request": {"number": 1, "state": "MERGED", "merged": True, "mergedAt": "2026-01-01T00:00:00Z", "mergeCommit": {"oid": "M"}, "baseRefName": "main", "headRefName": "task/G", "url": "https://pr", "body": "dev-graph: G", "closingIssuesReferences": []}}
    monkeypatch.setattr(mod, "c12_lifecycle_facts", lambda *args: remote)
    args = ("--repo-root", tmp_path, "--graph", graph, "--graph-node-id", "G", "--repo", "o/r", "--pr", "1")
    code, out = call_main(mod, monkeypatch, capsys, *args, "--mode", "check")
    assert code == 0 and out["policy_decision"] == "complete"
    code, out = call_main(mod, monkeypatch, capsys, *args)
    assert code == 0 and out["policy_decision"] == "writer_pending"
    assert json.loads(graph.read_text())["nodes"][0]["status"] == "active"
    bad = {**remote, "pull_request": {**remote["pull_request"], "state": "CLOSED", "merged": False, "mergedAt": None}}
    monkeypatch.setattr(mod, "c12_lifecycle_facts", lambda *args: bad)
    code, out = call_main(mod, monkeypatch, capsys, *args, "--mode", "check")
    assert code == 1 and out["policy_decision"] == "pending"


def test_guard_hook_branches(tmp_path, monkeypatch, capsys):
    mod = load(HOOKS / "guard-graph-schema.py", "guard_hook_cov")
    original_context_ok = mod.context_ok
    monkeypatch.setattr(mod, "context_ok", lambda root: (True, "ok"))
    for command, expected in (
        ("echo ok", 0),
        ("bd close X", 2),
        ("gh issue create --title x", 2),
        ("rm -rf .dev-graph", 2),
        ("python scripts/bd-bridge.py --op close", 0),
    ):
        code, _ = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, stdin={"tool_input": {"command": command}})
        assert code == expected
    code, _ = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, stdin={})
    assert code == 0
    monkeypatch.setattr(mod, "context_ok", lambda root: (False, "bad"))
    code, _ = call_main(mod, monkeypatch, capsys, "--repo-root", tmp_path, stdin={"tool_input": {"command": "echo x"}})
    assert code == 2
    monkeypatch.setattr(sys, "stdin", io.StringIO("bad")); assert mod.payload() == {}
    assert mod.command_of({"tool_input": "bad"}) == ""
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr=""))
    assert original_context_ok(tmp_path)[0] is True
    missing = tmp_path / "missing"
    monkeypatch.setattr(mod.Path, "is_file", lambda self: False)
    assert mod.context_ok(missing)[0] is False


def test_lifecycle_hook_helpers_and_events(tmp_path, monkeypatch, capsys):
    mod = load(HOOKS / "reconcile-task-lifecycle.py", "lifecycle_hook_cov")
    missing = tmp_path / "missing.py"
    assert mod.invoke(missing)["ok"] is False
    script = tmp_path / "script.py"; script.write_text("print('{\"x\":1}')")
    assert mod.invoke(script)["result"] == {"x": 1}
    script.write_text("print('plain')")
    assert mod.invoke(script)["stdout"] == "plain"
    script.write_text("import sys; print('bad', file=sys.stderr); raise SystemExit(1)")
    assert mod.invoke(script)["stderr"] == "bad"

    actions = []
    def fake_invoke(path, *args):
        actions.append((path.name, args))
        if path.name == "resolve-repo-context.py":
            return {"ok": True, "exit_code": 0, "result": {
                "repository_id": "R", "head_sha": "H",
                "coordination_paths": {"root": str(tmp_path / "coord")},
                "local_state_paths": {"config": str(tmp_path / "missing.json")},
            }}
        return {"ok": True, "exit_code": 0, "result": {}}
    monkeypatch.setattr(mod, "invoke", fake_invoke)
    monkeypatch.setattr(mod, "dispatch_once", lambda *a, **k: {"ok": True, "spawned": True, "pid": 1})
    for event, payload in (
        ("session-start", {"hook_event_name": "SessionStart", "cwd": str(tmp_path)}),
        ("post-tool-use", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(tmp_path), "session_id": "S", "tool_use_id": "T1", "tool_input": {"command": "git push"}, "tool_response": {"exit_code": 0}, "dev_graph": {"graph": "graph.json", "graph_node_id": "G1", "repo": "o/r", "pr": 1}}),
        ("post-tool-use", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(tmp_path), "session_id": "S", "tool_use_id": "T2", "tool_input": {"command": "echo ok"}, "tool_response": {"exit_code": 0}}),
        ("task-completed", {"task_subject": "no marker"}),
        ("task-completed", {"task_subject": "done [DG:G1]", "session_id": "S"}),
    ):
        code, out = call_main(mod, monkeypatch, capsys, "--event", event, "--repo-root", tmp_path, stdin=payload)
        assert code == 0 and out["event"] == event
    assert any(name == "manage-worktree-lease.py" for name, _ in actions)
    bd_ready_args = next(args for name, args in actions if name == "bd-bridge.py")
    assert "--json" not in bd_ready_args  # bd-bridge always emits JSON and has no --json flag.
    code, out = call_main(mod, monkeypatch, capsys, "--event", "task-completed", "--repo-root", tmp_path, stdin={"task_subject": "[DG:G2]"})
    assert code == 2 and out["actions"][-1]["error"] == "missing session identity"
    monkeypatch.setattr(mod, "invoke", lambda *a, **k: {"ok": False, "exit_code": 1})
    code, _ = call_main(mod, monkeypatch, capsys, "--event", "session-start", "--repo-root", tmp_path, stdin={})
    assert code == 2
    monkeypatch.setattr(sys, "stdin", io.StringIO("bad")); assert mod.read_payload() == {}
