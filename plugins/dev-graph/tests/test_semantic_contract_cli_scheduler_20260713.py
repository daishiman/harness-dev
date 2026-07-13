from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace


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


def test_command_exposes_the_lease_parsers_canonical_list_operation():
    command = (PLUGIN / "commands" / "dev-graph.md").read_text(encoding="utf-8")
    lease = (SCRIPTS / "manage-worktree-lease.py").read_text(encoding="utf-8")
    assert "`claim|heartbeat|park|release|list`" in command
    assert "manage-worktree-lease.py --op list" in command
    assert "--op claim --graph-node-id <id> --branch <name> --session-id <session>" in command
    assert '"list"' in lease
    assert "|status`" not in command


def test_issue_create_uses_supported_create_flags_then_normalizes_view(monkeypatch, capsys):
    module = load("gh-bridge.py", "gh_bridge_semantic_contract")
    run_calls = []
    json_calls = []

    def fake_run(argv, **kwargs):
        run_calls.append(argv)
        return SimpleNamespace(stdout="https://github.test/acme/repo/issues/42\n", returncode=0)

    def fake_json(argv):
        json_calls.append(argv)
        return {
            "id": "I_kwDO42",
            "number": 42,
            "title": "Build it",
            "state": "OPEN",
            "url": "https://github.test/acme/repo/issues/42",
            "updatedAt": "2026-07-13T01:02:03Z",
        }

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "gh_json", fake_json)
    code, receipt = call_main(
        module, monkeypatch, capsys,
        "--op", "issue-create", "--repo", "acme/repo", "--title", "Build it",
    )

    assert code == 0
    create_argv = run_calls[0][1:]
    assert create_argv == ["issue", "create", "--repo", "acme/repo", "--title", "Build it", "--body", ""]
    assert "--json" not in create_argv
    assert json_calls == [["issue", "view", "https://github.test/acme/repo/issues/42", "--repo", "acme/repo", "--json", module.ISSUE_FIELDS]]
    assert receipt["result"] == {
        "id": "I_kwDO42",
        "number": 42,
        "title": "Build it",
        "state": "open",
        "url": "https://github.test/acme/repo/issues/42",
        "updated_at": "2026-07-13T01:02:03Z",
    }
    assert receipt["retry_classification"] == "verify_before_retry"
    assert module.retry_classification("issue-fetch") == "safe_read"
    assert module.retry_classification("issue-update") == "idempotent_with_same_arguments"


def test_scheduler_rejects_each_incomplete_gate_for_self_and_bd_ready(tmp_path, monkeypatch, capsys):
    module = load("schedule-graph.py", "schedule_graph_semantic_contract")
    nodes = [
        ready_node("eligible"),
        ready_node("eligible-2"),
        ready_node("waiting", depends_on=["not-done"]),
        ready_node("draft", status="draft"),
        ready_node("unconfirmed", confirmation_status="pending"),
        ready_node("failed", evaluation_status="fail"),
        ready_node("incomplete", implementation_readiness={"status": "incomplete"}),
    ]
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")

    code, self_plan = call_main(module, monkeypatch, capsys, "--graph", graph)
    assert code == 0
    assert self_plan["ready_set"]["tasks"] == ["eligible", "eligible-2"]
    assert {item["suggested_branch"] for item in self_plan["assignment_hints"]} == {
        "devgraph/eligible", "devgraph/eligible-2",
    }
    assert all(
        item["claim_command"].startswith(f"/dev-graph worktree claim {item['graph_node_id']} ")
        for item in self_plan["assignment_hints"]
    )

    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({"ready_set": [{"external_ref": node["id"]} for node in nodes]}), encoding="utf-8")
    code, bd_plan = call_main(
        module, monkeypatch, capsys,
        "--graph", graph, "--ready-source", "bd-bridge", "--ready-json", ready,
    )
    assert code == 0
    assert bd_plan["ready_set"]["tasks"] == ["eligible", "eligible-2"]
    assert "waiting" not in bd_plan["ready_set"]["tasks"]


def test_scheduler_uses_canonical_resource_scope_list_and_rejects_legacy_object(
    tmp_path, monkeypatch, capsys,
):
    module = load("schedule-graph.py", "schedule_graph_resource_scope_contract")
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": [
        ready_node("one", resource_scope=["packages/api"]),
        ready_node("two", resource_scope=["packages/api"]),
        ready_node("three", resource_scope=["packages/web"]),
    ]}), encoding="utf-8")

    code, plan = call_main(module, monkeypatch, capsys, "--graph", graph)
    assert code == 0
    assert plan["batches"]["tasks"] == [["one", "three"], ["two"]]

    graph.write_text(json.dumps({"nodes": [
        ready_node("legacy", resource_scope={"touches": ["packages/api"]}),
    ]}), encoding="utf-8")
    try:
        call_main(module, monkeypatch, capsys, "--graph", graph)
    except Exception as exc:
        assert "resource_scope must be" in str(exc)
    else:
        raise AssertionError("legacy resource_scope object must fail closed")
