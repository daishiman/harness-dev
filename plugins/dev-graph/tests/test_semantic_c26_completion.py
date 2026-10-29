from __future__ import annotations

import hashlib
import importlib.util
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
sys.path.insert(0, str(SCRIPTS))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    code = module.main()
    output = capsys.readouterr().out.strip()
    return code, json.loads(output) if output else None


def markdown(node_id: str, *, status: str = "active", phase: str | None = None, evidence: str = "evidence/run.json") -> str:
    phase_line = f'phase_ref: "{phase}"\n' if phase else ""
    return (
        "---\n"
        f'graph_node_id: "{node_id}"\n'
        f'status: "{status}"\n'
        f"{phase_line}"
        "---\n"
        "# Task\n\n"
        "## Verification and evidence\n\n"
        "- Automated commands: `python3 -m pytest`\n"
        f"- Required evidence: {evidence}\n"
    )


def facts(node_id: str = "G", *, closing: list[dict] | None = None) -> dict:
    return {
        "repository": "o/r",
        "default_branch": {"name": "main", "oid": "1" * 40},
        "pull_request": {
            "number": 1,
            "state": "MERGED",
            "merged": True,
            "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "2" * 40},
            "baseRefName": "main",
            "headRefName": "devgraph/G",
            "url": "https://example.test/o/r/pull/1",
            "body": f"Implements task\n\ndev-graph: {node_id}\n",
            "closingIssuesReferences": closing or [],
        },
    }


def git_context(monkeypatch, module, common: Path) -> None:
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(module, "c24_context", lambda root, resolver: {
        "repo_root": str(root),
        "repository_id": "github:o/r",
        "git_common_dir": str(common),
        "branch": "main",
        "head_sha": "1" * 40,
        "coordination_paths": {"root": str(common / "dev-graph")},
    })


BUILD_NODE = SCRIPTS / "build-graph-node.py"
CONTRACT = json.loads((PLUGIN / "templates" / "template-contract.json").read_text(encoding="utf-8"))
ROOTS = {"issues": "issues", "tasks": "tasks", "specifications": "specs", "architecture": "architecture",
         "features": "features", "documents": "docs", "system_spec": "system-spec"}
VERIFICATION = "- Automated commands: `python3 -m pytest`\n- Required evidence: evidence/run.json"


def lifecycle_workspace(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    """C02 add で登録した task を、C26 が完了へ進められる active/confirmed/pass へ上げた managed repo。"""
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    inputs = root / ".dev-graph" / "cache" / "inputs"
    inputs.mkdir(parents=True)
    (root / ".dev-graph" / "state").mkdir()
    (root / ".dev-graph" / "config.json").write_text(json.dumps({
        "schema_version": "1.0.0", "content_roots": ROOTS,
        "local_state": {"graph": ".dev-graph/state/graph.json", "cache": ".dev-graph/cache", "locks": ".dev-graph/locks"},
        "execution_tracker": {"mode": "beads"},
    }), encoding="utf-8")
    graph = root / ".dev-graph" / "state" / "graph.json"
    graph.write_text(json.dumps({"graph_revision": 0, "nodes": [], "schema_version": "1.0.0"}), encoding="utf-8")
    for directory in ROOTS.values():
        (root / directory).mkdir()
    sections = {name: f"{name} の確定内容。" for name in CONTRACT["artifacts"]["task"]["required_sections"]}
    sections["検証方法"] = VERIFICATION
    entry = {"artifact_kind": "task", "slug": "g", "title": "Lifecycle task", "project_id": "web", "domain": "auth",
             "tracker_binding": "none", "sections": sections,
             "classification": {"reason": "explicit task request", "decision": "auto",
                                "candidates": [{"artifact_kind": "task", "confidence": 0.95},
                                               {"artifact_kind": "document", "confidence": 0.05}]}}
    payload = inputs / "add.json"
    payload.write_text(json.dumps({"expected_graph_revision": 0, "artifacts": [entry]}, ensure_ascii=False), encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    added = subprocess.run([sys.executable, "-B", str(BUILD_NODE), "add", "--repo-root", str(root), "--input", str(payload)],
                           capture_output=True, text=True, env=env, cwd=root, check=False)
    assert added.returncode == 0, added.stdout + added.stderr
    saved = json.loads(graph.read_text(encoding="utf-8"))
    node = saved["nodes"][0]
    node.update({
        "status": "active", "confirmation_status": "confirmed", "evaluation_status": "pass",
        "confirmation_evidence": {"evaluator": "reviewer", "evidence_ref": "eval-log/x.json", "evaluated_digest": "a" * 64},
        "completion_evidence": {"policy": "linked_pr_merged_all", "status": "in_progress", "source": None,
                                "completed_at": None, "reconciled_at": None, "evidence_refs": []},
    })
    graph.write_text(json.dumps(saved), encoding="utf-8")
    artifact = root / node["file_path"]
    writer = load(BUILD_NODE, f"c26_seed_{tmp_path.name}")
    _, body = writer._split_frontmatter(artifact.read_text(encoding="utf-8"), node["file_path"])
    artifact.write_text(writer._frontmatter(node, list(CONTRACT["common_frontmatter"]["required"])) + "".join(body),
                        encoding="utf-8")
    return root, graph, artifact, node["graph_node_id"]


def lifecycle_request(root: Path, graph: Path, artifact: Path, node_id: str) -> dict:
    """reconcile `_writer_request` が C02 へ渡す形 (graph_path は repo 相対、digest は request_digest を除いた正規 JSON)。"""
    completion = {"policy": "linked_pr_merged_all", "status": "done", "source": "github_pr_merge",
                  "completed_at": "2026-01-01T00:00:00Z", "reconciled_at": "2026-01-01T00:00:01Z",
                  "evidence_refs": ["https://example.test/o/r/pull/1"]}
    linkage = {"repo": "o/r", "pr_number": 1, "url": "https://example.test/o/r/pull/1", "base_branch": "main",
               "head_branch": f"devgraph/{node_id}", "state": "merged", "merged_at": "2026-01-01T00:00:00Z",
               "merge_commit_sha": "2" * 40, "linked_at": "2026-01-01T00:00:01Z", "closing_reference_verified": True}
    request = {
        "schema_version": "1.1", "owner": "C02/run-dev-graph-node", "operation": "apply-lifecycle-request",
        "event_key": f"o/r#task:{node_id}#policy:test", "status": "pending",
        "graph_path": graph.relative_to(root).as_posix(),
        "graph_revision_before": json.loads(graph.read_text(encoding="utf-8"))["graph_revision"],
        "graph_sha256_before": hashlib.sha256(graph.read_bytes()).hexdigest(),
        "task_patch": {
            "graph_node_id": node_id, "file_path": artifact.relative_to(root).as_posix(),
            "artifact_sha256_before": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "set": {"status": "done", "updated_at": "2026-01-01T00:00:01Z", "completion_evidence": completion,
                    "pull_request_linkages": [linkage]},
        },
        "feature_patch": None,
    }
    request["request_digest"] = hashlib.sha256(
        json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return request


def consume(root: Path, request: Path, receipt: Path) -> tuple[int, dict]:
    """C26 `_consume_writer` と同じ起動: cwd = repo root、--repo-root なし。"""
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    cp = subprocess.run([sys.executable, "-B", str(BUILD_NODE), "--operation", "apply-lifecycle-request",
                         "--request", str(request), "--receipt", str(receipt)],
                        capture_output=True, text=True, env=env, cwd=root, check=False)
    return cp.returncode, json.loads(cp.stdout)


def test_c12_lifecycle_facts_returns_default_oid_and_exact_pr_snapshot(monkeypatch):
    module = load(SCRIPTS / "gh-bridge.py", "c12_lifecycle_facts")
    monkeypatch.setattr(module, "graphql", lambda query, variables: {"data": {"repository": {
        "nameWithOwner": "o/r",
        "defaultBranchRef": {"name": "main", "target": {"oid": "1" * 40}},
        "pullRequest": {
            "number": 7, "state": "MERGED", "merged": True, "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "2" * 40}, "baseRefName": "main", "headRefName": "devgraph/G",
            "url": "https://example.test/o/r/pull/7", "body": "dev-graph: G",
            "closingIssuesReferences": {"nodes": [{"number": 9, "repository": {"nameWithOwner": "o/r"}}]},
        },
    }}})
    result = module.lifecycle_facts("o/r", 7)
    assert result["default_branch"] == {"name": "main", "oid": "1" * 40}
    assert result["pull_request"]["closingIssuesReferences"] == [{"number": 9, "repository": "o/r"}]
    assert module.retry_classification("lifecycle-facts") == "safe_read"


def test_c26_consumes_c24_canonical_repository_context(tmp_path, monkeypatch):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_c24_context")
    common = tmp_path / ".git"
    receipt = {
        "repo_root": str(tmp_path),
        "repository_id": "github:o/r",
        "git_common_dir": str(common),
        "branch": "main",
        "head_sha": "1" * 40,
        "coordination_paths": {"root": str(common / "dev-graph")},
    }
    monkeypatch.setattr(module, "_invoke_json", lambda *args: dict(receipt))
    assert module.c24_context(tmp_path, SCRIPTS / "resolve-repo-context.py")["repository_id"] == "github:o/r"
    monkeypatch.setattr(module, "_invoke_json", lambda *args: {**receipt, "repository_id": "repo_legacy"})
    with pytest.raises(module.ContractError, match="non-canonical"):
        module.c24_context(tmp_path, SCRIPTS / "resolve-repo-context.py")
    # detached HEAD は branch=None として受け、key の欠落と空文字は identity 不備として落とす。
    monkeypatch.setattr(module, "_invoke_json", lambda *args: {**receipt, "branch": None})
    assert module.c24_context(tmp_path, SCRIPTS / "resolve-repo-context.py")["branch"] is None
    monkeypatch.setattr(module, "_invoke_json", lambda *args: {key: value for key, value in receipt.items() if key != "branch"})
    with pytest.raises(module.ContractError, match="omits required identity"):
        module.c24_context(tmp_path, SCRIPTS / "resolve-repo-context.py")
    monkeypatch.setattr(module, "_invoke_json", lambda *args: {**receipt, "branch": ""})
    with pytest.raises(module.ContractError, match="invalid branch state"):
        module.c24_context(tmp_path, SCRIPTS / "resolve-repo-context.py")


def test_c26_detached_check_reports_pending_without_identity_failure(tmp_path, monkeypatch, capsys):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_detached_check")
    common = tmp_path / "common"
    common.mkdir()
    git_context(monkeypatch, module, common)
    monkeypatch.setattr(module, "c24_context", lambda root, resolver: {
        "repo_root": str(root), "repository_id": "github:o/r", "git_common_dir": str(common), "branch": None,
        "head_sha": "1" * 40, "coordination_paths": {"root": str(common / "dev-graph")},
    })
    monkeypatch.setattr(module, "c12_lifecycle_facts", lambda *args: facts())
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "G.md").write_text(markdown("G"), encoding="utf-8")
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"graph_revision": 1, "nodes": [{
        "graph_node_id": "G", "artifact_kind": "task", "status": "active", "tracker_binding": "none",
        "file_path": "tasks/G.md", "pull_request_linkages": [],
        "completion_evidence": {"policy": "linked_pr_merged_all", "status": "in_progress", "evidence_refs": []},
    }]}), encoding="utf-8")
    code, result = call_main(module, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph, "--graph-node-id", "G",
                             "--repo", "o/r", "--pr", "1", "--mode", "check")
    assert code == 1 and result["policy_decision"] == "pending"
    assert result["worktree_decision"]["branch"] is None
    assert result["required_pr_decisions"][0]["linkage"]["marker_verified"] is True
    assert result["conflicts"] == ["worktree is not clean and synchronized on the remote default branch"]


def test_c26_requires_unique_marker_and_exact_bound_issue_closing_reference(tmp_path, monkeypatch):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_linkage")
    node = {"graph_node_id": "G", "tracker_binding": "github", "issue_linkage": {"repo": "o/r", "issue_number": 9}}
    pr = facts(closing=[{"number": 9, "repository": "o/r"}])["pull_request"]
    assert module._linkage_decision(node, "o/r", pr)["eligible"] is True
    assert module._linkage_decision(node, "o/r", {**pr, "body": "dev-graph: G\ndev-graph: G\n"})["marker_verified"] is False
    wrong = {**pr, "closingIssuesReferences": [{"number": 9, "repository": "someone/else"}]}
    assert module._linkage_decision(node, "o/r", wrong)["closing_reference_verified"] is False

    # gh:pr gate を持たない Beads task は「未検証」であって C28 の失敗ではない。
    beads_node = {"graph_node_id": "G", "tracker_binding": "beads", "beads_linkage": {"bd_issue_id": "B1"}}
    monkeypatch.setattr(module, "_invoke_json", lambda *args: (_ for _ in ()).throw(
        module.ContractError("C28 gh:pr gate check failed (1): gh:pr gate does not exist")))
    assert module._beads_gate_verified(tmp_path, tmp_path / "bridge.py", beads_node, 1) is False


def test_c26_writer_consumer_cli_route_creates_receipt(tmp_path):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_consumer")
    request = tmp_path / "request.json"
    receipt = tmp_path / "receipt.json"
    request.write_text('{"request_digest":"abc"}', encoding="utf-8")
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        "import argparse,json\n"
        "p=argparse.ArgumentParser();p.add_argument('--operation');p.add_argument('--request');p.add_argument('--receipt');a=p.parse_args()\n"
        "open(a.receipt,'w').write(json.dumps({'owner':'C02/run-dev-graph-node','operation':a.operation,'status':'applied'}))\n"
        "print(json.dumps({'ok':True,'operation':a.operation}))\n",
        encoding="utf-8",
    )
    module._consume_writer(tmp_path, consumer, request, receipt)
    value = json.loads(receipt.read_text(encoding="utf-8"))
    assert value["owner"] == "C02/run-dev-graph-node"
    assert value["operation"] == "apply-lifecycle-request"


def test_c02_apply_lifecycle_request_is_typed_and_crash_retry_idempotent(tmp_path):
    root, graph, artifact, node_id = lifecycle_workspace(tmp_path)
    body_before = artifact.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    coordination = root / ".git" / "dev-graph" / "completion-receipts"
    coordination.mkdir(parents=True)
    request_path, receipt_path = coordination / "request.json", coordination / "receipt.json"
    request = lifecycle_request(root, graph, artifact, node_id)
    request_path.write_text(json.dumps(request), encoding="utf-8")

    code, receipt = consume(root, request_path, receipt_path)
    assert code == 0, receipt
    assert receipt == json.loads(receipt_path.read_text(encoding="utf-8"))
    assert (receipt["owner"], receipt["operation"], receipt["status"], receipt["idempotent"]) == (
        "C02/run-dev-graph-node", "apply-lifecycle-request", "applied", False)
    assert (receipt["request_digest"], receipt["graph_revision_after"]) == (request["request_digest"], 2)
    assert receipt["graph_sha256_after"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    assert receipt["task_artifact_sha256_after"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    saved = json.loads(graph.read_text(encoding="utf-8"))["nodes"][0]
    assert (saved["status"], saved["completion_evidence"]["status"], saved["evaluation_status"]) == ("done", "done", "pass")
    assert saved["pull_request_linkages"] == request["task_patch"]["set"]["pull_request_linkages"]
    text = artifact.read_text(encoding="utf-8")
    assert 'status: "done"' in text and text.split("\n---\n", 1)[1] == body_before, "completion must not touch the body"
    assert (root / receipt["node_receipt_path"]).is_file()
    validated = subprocess.run([sys.executable, "-B", str(SCRIPTS / "validate-graph-schema.py"), "--graph", str(graph),
                                "--repo-root", str(root)], capture_output=True, text=True, check=False)
    assert validated.returncode == 0, validated.stdout

    # receipt を書く前に落ちた retry: graph は既に revision+1 の完了状態なので、書き直さず idempotent な receipt だけ返す。
    receipt_path.unlink()
    graph_bytes = graph.read_bytes()
    code, repeated = consume(root, request_path, receipt_path)
    assert code == 0 and repeated["idempotent"] is True and repeated["node_receipt_path"] is None
    assert graph.read_bytes() == graph_bytes and repeated["graph_sha256_after"] == receipt["graph_sha256_after"]


def test_c02_apply_lifecycle_request_refuses_foreign_paths_tampering_and_moved_before_image(tmp_path):
    root, graph, artifact, node_id = lifecycle_workspace(tmp_path)
    coordination = root / ".git" / "dev-graph" / "completion-receipts"
    coordination.mkdir(parents=True)
    request = lifecycle_request(root, graph, artifact, node_id)
    outside = root / ".dev-graph" / "cache" / "request.json"
    outside.write_text(json.dumps(request), encoding="utf-8")
    code, report = consume(root, outside, coordination / "receipt.json")
    assert (code, report["code"]) == (1, "lifecycle_path_outside_authority")

    request_path, receipt_path = coordination / "request.json", coordination / "receipt.json"
    cases = {
        "lifecycle_request_invalid": {**request, "event_key": "o/r#task:other#policy:test"},  # digest no longer matches
        "feature_rollup_not_supported": {**request, "feature_patch": {"graph_node_id": "feature-x"}},
    }
    for expected, tampered in cases.items():
        if expected == "feature_rollup_not_supported":
            tampered["request_digest"] = hashlib.sha256(json.dumps(
                {key: value for key, value in tampered.items() if key != "request_digest"},
                ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        request_path.write_text(json.dumps(tampered), encoding="utf-8")
        code, report = consume(root, request_path, receipt_path)
        assert (code, report["code"]) == (1, expected), report

    request_path.write_text(json.dumps(request), encoding="utf-8")
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
    graph_bytes = graph.read_bytes()
    code, report = consume(root, request_path, receipt_path)
    assert (code, report["code"]) == (1, "lifecycle_before_image_mismatch")
    assert graph.read_bytes() == graph_bytes and not receipt_path.exists()


def test_c02_apply_lifecycle_request_keeps_package_member_frontmatter_owned_by_the_planner(tmp_path, monkeypatch):
    # exact-13 member の task Markdown は system-dev-planner の frontmatter で C02 の 46 key を持たない。完了は
    # その file を C02 の形へ作り直さず status 行だけを置き換え、宣言の無い key は増やさない。
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent))
    import test_register_package as package

    root, graph, _, _ = lifecycle_workspace(tmp_path)
    saved = json.loads(graph.read_text(encoding="utf-8"))
    saved["nodes"] += [package.feature_node(), *(package.task_node(index) for index in range(13))]
    graph.write_text(json.dumps(saved), encoding="utf-8")
    member = root / "tasks" / "feature-1" / "p01.md"
    member.parent.mkdir()
    front = 'graph_node_id: "task-P01"\nphase_ref: "P01"\nstatus: "active"\nplanner_note: "keep"\n'
    body = f"# P01\n\n## 検証方法\n\n{VERIFICATION}\n"
    member.write_text(f"---\n{front}---\n{body}", encoding="utf-8")
    coordination = root / ".git" / "dev-graph" / "completion-receipts"
    coordination.mkdir(parents=True)
    request_path, receipt_path = coordination / "request.json", coordination / "receipt.json"
    request_path.write_text(json.dumps(lifecycle_request(root, graph, member, "task-P01")), encoding="utf-8")

    code, receipt = consume(root, request_path, receipt_path)
    assert code == 0, receipt
    assert member.read_text(encoding="utf-8") == f"---\n{front.replace('active', 'done')}---\n{body}"
    assert receipt["task_artifact_sha256_after"] == hashlib.sha256(member.read_bytes()).hexdigest()
    durable = next(node for node in json.loads(graph.read_text(encoding="utf-8"))["nodes"] if node["graph_node_id"] == "task-P01")
    assert (durable["status"], durable["phase_ref"], durable["completion_evidence"]["status"]) == ("done", "P01", "done")


def test_c26_uses_default_c02_consumer_without_cli_injection(tmp_path, monkeypatch, capsys):
    root, graph, _, node_id = lifecycle_workspace(tmp_path)
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_default_consumer")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    actual_run = module.run
    git_context(monkeypatch, module, root / ".git")
    # git の照会は fixture で固定し、既定 consumer (build-graph-node.py) の起動だけを本物で通す。
    monkeypatch.setattr(module, "run", lambda argv, *args, **kwargs: (
        actual_run(argv, *args, **kwargs) if any(str(part).endswith("build-graph-node.py") for part in argv)
        else SimpleNamespace(returncode=0, stdout="", stderr="")))
    monkeypatch.setattr(module, "c12_lifecycle_facts", lambda *args: facts(node_id))
    args = ("--repo-root", root, "--graph", graph, "--graph-node-id", node_id, "--repo", "o/r", "--pr", "1")

    code, completed = call_main(module, monkeypatch, capsys, *args)
    assert code == 0, completed
    assert completed["policy_decision"] == "complete"
    assert completed["completion_step_ledger"]["c02_writer"] == "applied"
    assert completed["completion_step_ledger"]["completion_event"] == "applied"
    assert completed["local_patch"]["operation"] == "apply-lifecycle-request"
    assert completed["completion_event"]["graph_node_id"] == node_id
    saved = json.loads(graph.read_text(encoding="utf-8"))
    assert saved["nodes"][0]["status"] == "done"

    code, repeated = call_main(module, monkeypatch, capsys, *args)
    assert code == 0 and repeated["policy_decision"] == "complete"
    assert json.loads(graph.read_text(encoding="utf-8"))["graph_revision"] == saved["graph_revision"]


def test_c26_backfill_done_uses_stored_verified_merge_and_is_idempotent(tmp_path, monkeypatch, capsys):
    root, graph, artifact, node_id = lifecycle_workspace(tmp_path)
    coordination = root / ".git" / "dev-graph" / "completion-receipts"
    coordination.mkdir(parents=True)
    request_path = coordination / "request.json"
    request_path.write_text(json.dumps(lifecycle_request(root, graph, artifact, node_id)), encoding="utf-8")
    assert consume(root, request_path, coordination / "receipt.json")[0] == 0

    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_backfill_done")
    common = root / ".git"
    monkeypatch.setattr(module, "c24_context", lambda root_path, resolver: {
        "repo_root": str(root_path), "repository_id": "github:o/r", "git_common_dir": str(common), "branch": None,
        "head_sha": "3" * 40, "coordination_paths": {"root": str(common / "dev-graph")},
    })
    args = ("--repo-root", root, "--graph", graph, "--graph-node-id", node_id, "--mode", "backfill-done",
            "--repo", "o/r", "--pr", "1")

    def completion_events() -> list[dict]:
        ledger = json.loads((common / "dev-graph" / "events.json").read_text(encoding="utf-8"))
        return [event for event in ledger["events"] if event.get("graph_node_id") == node_id]

    code, result = call_main(module, monkeypatch, capsys, *args)
    assert code == 0, result
    assert result["backfill_mode"] == "verified_existing_done"
    assert result["completion_step_ledger"]["c02_writer"] == "verified_existing"
    assert result["completion_event"]["backfilled_from_durable_completion"] is True
    assert len(completion_events()) == 1
    code, repeated = call_main(module, monkeypatch, capsys, *args)
    assert code == 0 and repeated["completion_event"]["event_key"] == result["completion_event"]["event_key"]
    assert len(completion_events()) == 1

    (common / "dev-graph" / "leases.json").write_text(json.dumps(
        {"schema_version": "1.1", "leases": [{"graph_node_id": node_id, "state": "pending_merge"}]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, args)])
    with pytest.raises(module.ContractError, match="active common-dir lease"):
        module.main()


def test_c26_local_first_transaction_calls_c27_before_beads_and_is_idempotent(tmp_path, monkeypatch, capsys):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_transaction")
    common = tmp_path / "common"
    common.mkdir()
    git_context(monkeypatch, module, common)
    monkeypatch.setattr(module, "c12_lifecycle_facts", lambda *args: facts())
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    artifact = tasks / "G.md"
    artifact.write_text(markdown("G"), encoding="utf-8")
    node = {
        "graph_node_id": "G", "artifact_kind": "task", "status": "active", "tracker_binding": "beads",
        "file_path": "tasks/G.md", "completion_evidence": {"policy": "linked_pr_merged_all", "status": "in_progress", "evidence_refs": []},
        "beads_linkage": {"bd_issue_id": "B1"}, "execution_contexts": [{"state": "pending_review"}],
    }
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"graph_revision": 4, "nodes": [node]}), encoding="utf-8")
    original = graph.read_bytes()
    args = ("--repo-root", tmp_path, "--graph", graph, "--graph-node-id", "G", "--repo", "o/r", "--pr", "1")
    # --writer-request-only は既定の C02 consumer を起動せず、request を書いて止まる。
    code, pending = call_main(module, monkeypatch, capsys, *args, "--writer-request-only")
    assert code == 0 and pending["policy_decision"] == "writer_pending"
    assert graph.read_bytes() == original
    request = pending["writer_request"]
    assert Path(pending["writer_request_path"]).is_file(), "C02 request must have a concrete consumable path"

    updated = json.loads(graph.read_text(encoding="utf-8"))
    updated["graph_revision"] = 5
    updated["nodes"][0].update(request["task_patch"]["set"])
    graph.write_text(json.dumps(updated), encoding="utf-8")
    artifact.write_text(markdown("G", status="done"), encoding="utf-8")
    writer = tmp_path / "writer.json"
    writer.write_text(json.dumps({
        "owner": "C02/run-dev-graph-node", "operation": "apply-lifecycle-request", "status": "applied",
        "event_key": request["event_key"], "graph_node_id": "G", "request_digest": request["request_digest"],
        "graph_sha256_after": hashlib.sha256(graph.read_bytes()).hexdigest(), "graph_revision_after": 5,
        "task_artifact_sha256_after": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    order: list[str] = []
    def release_failure(*args):
        order.append("C27-fail")
        raise module.ContractError("lease unavailable")
    monkeypatch.setattr(module, "_invoke_system_release", release_failure)
    monkeypatch.setattr(module, "_invoke_bd_close", lambda *args: pytest.fail("Beads close must not run before C27 succeeds"))
    code, completed = call_main(module, monkeypatch, capsys, *args, "--writer-receipt", writer)
    assert code == 1 and completed["policy_decision"] == "pending_retry"
    assert completed["completion_step_ledger"]["system_release"] == "pending_retry"
    event_ledger = json.loads((common / "dev-graph" / "events.json").read_text(encoding="utf-8"))
    assert event_ledger["events"][0]["repository_id"] == "github:o/r"

    monkeypatch.setattr(module, "_invoke_system_release", lambda *args: order.append("C27") or {"lease": {"state": "released", "completion_event_key": request["event_key"]}})
    def beads_failure(*args):
        order.append("C28-fail")
        raise module.ContractError("beads unavailable")
    monkeypatch.setattr(module, "_invoke_bd_close", beads_failure)
    code, completed = call_main(module, monkeypatch, capsys, *args)
    assert code == 1 and completed["completion_step_ledger"]["system_release"] == "applied"
    assert completed["completion_step_ledger"]["beads_close"] == "pending_retry"

    monkeypatch.setattr(module, "_invoke_bd_close", lambda *args: order.append("C28") or {"op": "close", "result": {"status": "closed"}})
    code, completed = call_main(module, monkeypatch, capsys, *args)
    assert code == 0 and completed["policy_decision"] == "complete"
    assert completed["completion_step_ledger"] == {
        "event_key": request["event_key"], "c02_writer": "applied", "completion_event": "applied",
        "system_release": "applied", "beads_close": "applied",
    }
    assert order == ["C27-fail", "C27", "C28-fail", "C28"], "C27 local release must precede the final external Beads projection"
    code, repeated = call_main(module, monkeypatch, capsys, *args)
    assert code == 0 and repeated["policy_decision"] == "complete" and order == ["C27-fail", "C27", "C28-fail", "C28"]


def test_c26_feature_rollup_requires_deep_p07_p10_p11_markdown_and_receipts(tmp_path):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_rollup")
    acceptance = ["criterion-A", "criterion-B"]
    feature = {"graph_node_id": "F", "artifact_kind": "feature", "status": "active", "acceptance": acceptance}
    (tmp_path / "tasks").mkdir()
    (tmp_path / "evidence").mkdir()
    children = []
    for index, phase in enumerate(module.PHASES, 1):
        reference = f"evidence/{phase}.json"
        child = {
            "graph_node_id": f"T{index}", "artifact_kind": "task", "status": "done", "parent_feature": "F",
            "feature_package_id": "feature-package/F", "phase_ref": phase, "file_path": f"tasks/{phase}.md",
            "completion_evidence": {"status": "done", "evidence_refs": [reference]},
        }
        children.append(child)
        if phase in module.EVIDENCE_PHASES:
            (tmp_path / reference).write_text(json.dumps({
                "result": "PASS", "covered_task_ids": [child["graph_node_id"]], "phase_ref": phase,
                "feature_acceptance": acceptance,
            }), encoding="utf-8")
            (tmp_path / child["file_path"]).write_text(markdown(child["graph_node_id"], status="done", phase=phase, evidence=reference), encoding="utf-8")
    registration = tmp_path / "registration.json"
    registration.write_text(json.dumps({
        "status": "registered", "expected_count": 13, "applied_count": 13, "phase_refs": module.PHASES,
        "node_ids": [child["graph_node_id"] for child in children], "feature_package_id": "feature-package/F", "parent_feature": "F",
    }), encoding="utf-8")
    rollup = module.feature_rollup(tmp_path, [feature, *children], children[0], str(registration))
    assert rollup and rollup["eligible"] is True
    bad = tmp_path / "evidence" / "P10.json"
    value = json.loads(bad.read_text(encoding="utf-8"))
    value["feature_acceptance"] = ["criterion-A"]
    bad.write_text(json.dumps(value), encoding="utf-8")
    rollup = module.feature_rollup(tmp_path, [feature, *children], children[0], str(registration))
    assert rollup and rollup["eligible"] is False
    assert any("P10" in blocker and "exactly" in blocker for blocker in rollup["blockers"])


def test_c26_fails_closed_on_malformed_c12_fixture(tmp_path, monkeypatch):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_errors")
    monkeypatch.setenv("DEV_GRAPH_GH_FIXTURE", "{")
    with pytest.raises(module.ContractError, match="invalid JSON"):
        module.c12_lifecycle_facts(tmp_path, tmp_path / "gh-bridge.py", "o/r", 1)
    with pytest.raises(module.ContractError, match="graph nodes"):
        module._nodes({"nodes": "not-an-array"})


def test_c26_boundary_helpers_fail_closed_with_typed_receipts(tmp_path, monkeypatch):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_helper_errors")
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout="", stderr="denied"))
    with pytest.raises(module.ContractError, match="failed"):
        module._invoke_json(["tool"], tmp_path, "boundary")
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="{", stderr=""))
    with pytest.raises(module.ContractError, match="invalid JSON"):
        module._invoke_json(["tool"], tmp_path, "boundary")
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="[]", stderr=""))
    with pytest.raises(module.ContractError, match="must be an object"):
        module._invoke_json(["tool"], tmp_path, "boundary")

    monkeypatch.delenv("DEV_GRAPH_GH_FIXTURE", raising=False)
    monkeypatch.setattr(module, "_invoke_json", lambda *args: {"op": "wrong", "result": {}})
    with pytest.raises(module.ContractError, match="identity mismatch"):
        module.c12_lifecycle_facts(tmp_path, tmp_path / "bridge.py", "o/r", 1)
    expected = facts()
    monkeypatch.setattr(module, "_invoke_json", lambda *args: {"op": "lifecycle-facts", "result": expected})
    assert module.c12_lifecycle_facts(tmp_path, tmp_path / "bridge.py", "o/r", 1) == expected

    with pytest.raises(module.ContractError, match="no frontmatter"):
        module._frontmatter("plain")
    with pytest.raises(module.ContractError, match="not terminated"):
        module._frontmatter("---\nstatus: active")
    with pytest.raises(module.ContractError, match="invalid task Markdown"):
        module._artifact_path(tmp_path, {"graph_node_id": "G", "file_path": "../G.md"})
    assert module._local_evidence(tmp_path, "https://example.test/evidence") is None
    with pytest.raises(module.ContractError, match="escapes"):
        module._local_evidence(tmp_path, "/outside.json")

    tasks = tmp_path / "tasks"
    tasks.mkdir()
    task = tasks / "G.md"
    task.write_text(markdown("wrong"), encoding="utf-8")
    node = {"graph_node_id": "G", "file_path": "tasks/G.md"}
    with pytest.raises(module.ContractError, match="does not match graph"):
        module._validate_task_artifact(tmp_path, node)
    task.write_text(markdown("G").replace("`python3 -m pytest`", "TODO"), encoding="utf-8")
    with pytest.raises(module.ContractError, match="incomplete verification"):
        module._validate_task_artifact(tmp_path, node)

    monkeypatch.setattr(module, "_invoke_json", lambda *args: {"lease": {"state": "pending_review"}})
    with pytest.raises(module.ContractError, match="does not match"):
        module._invoke_system_release(tmp_path, tmp_path / "lease.py", "G", "E")
    assert module._needs_system_release({"execution_contexts": [{"state": "pending_merge"}]}) is True
    assert module._needs_system_release({"execution_contexts": [{"state": "released"}]}) is False


def test_c26_writer_receipt_rejects_digest_revision_and_durable_state_drift(tmp_path):
    module = load(SCRIPTS / "reconcile-github-lifecycle.py", "c26_writer_errors")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    artifact = tasks / "G.md"
    artifact.write_text(markdown("G", status="done"), encoding="utf-8")
    completion = {"policy": "linked_pr_merged_all", "status": "done", "source": "github_pr_merge", "completed_at": "2026-01-01T00:00:00Z", "reconciled_at": "2026-01-01T00:00:01Z", "evidence_refs": ["https://example.test/pr/1"]}
    linkages: list[dict] = []
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"graph_revision": 2, "nodes": [{"graph_node_id": "G", "status": "done", "file_path": "tasks/G.md", "completion_evidence": completion, "pull_request_linkages": linkages}]}), encoding="utf-8")
    request = {"event_key": "E", "request_digest": "D", "graph_revision_before": 1, "task_patch": {"graph_node_id": "G", "set": {"completion_evidence": completion, "pull_request_linkages": linkages}}}
    base = {"owner": "C02/run-dev-graph-node", "operation": "apply-lifecycle-request", "status": "applied", "event_key": "E", "graph_node_id": "G", "request_digest": "D", "graph_sha256_after": hashlib.sha256(graph.read_bytes()).hexdigest(), "graph_revision_after": 2, "task_artifact_sha256_after": hashlib.sha256(artifact.read_bytes()).hexdigest()}
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({**base, "request_digest": "wrong"}), encoding="utf-8")
    with pytest.raises(module.ContractError, match="request digest"):
        module._writer_applied(receipt, request, graph, tmp_path)
    receipt.write_text(json.dumps({**base, "graph_sha256_after": "stale"}), encoding="utf-8")
    with pytest.raises(module.ContractError, match="graph digest"):
        module._writer_applied(receipt, request, graph, tmp_path)
    receipt.write_text(json.dumps({**base, "graph_revision_after": 3}), encoding="utf-8")
    with pytest.raises(module.ContractError, match="graph revision"):
        module._writer_applied(receipt, request, graph, tmp_path)
    receipt.write_text(json.dumps(base), encoding="utf-8")
    assert module._writer_applied(receipt, request, graph, tmp_path)["status"] == "applied"
