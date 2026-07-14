#!/usr/bin/env python3
# /// script
# name: reconcile-github-lifecycle
# purpose: Converge C12-verified default-branch PR facts through a C02 consumer into idempotent completion and C27 release events.
# inputs: ["argv: --repo-root PATH --graph FILE --graph-node-id ID --mode reconcile|check|drain-pending"]
# outputs: ["stdout: JSON remote facts, linkage decision, C02 request/receipt, step ledger and completion event"]
# requires-python = ">=3.10"
# dependencies: ["gh-bridge.py", "manage-worktree-lease.py", "bd-bridge.py"]
# contexts: [A, B, C, E]
# network: true
# write-scope: git-common-dir completion request/transaction/event ledgers only; graph and Markdown writes belong to C02
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from _common import ContractError, atomic_json, dump, load_json, run, utc_now

PHASES = [f"P{i:02d}" for i in range(1, 14)]
EVIDENCE_PHASES = {"P07", "P10", "P11"}
MARKER = re.compile(r"(?mi)^\s*dev-graph:\s*([^\s#]+)\s*$")
PLACEHOLDER = re.compile(r"<[^>]+>|\b(?:TODO|TBD)\b", re.IGNORECASE)


def _nodes(value: Any) -> list[dict[str, Any]]:
    rows = value.get("nodes", []) if isinstance(value, dict) else value
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ContractError("graph nodes must be an array of objects")
    return rows


def _node_id(node: dict[str, Any]) -> str | None:
    return node.get("graph_node_id") or node.get("id")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _invoke_json(argv: list[str], root: Path, label: str) -> dict[str, Any]:
    cp = run(argv, cwd=root, check=False)
    if cp.returncode:
        raise ContractError(f"{label} failed ({cp.returncode}): {(cp.stderr or cp.stdout).strip()}")
    try:
        value = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{label} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} receipt must be an object")
    return value


def c12_lifecycle_facts(root: Path, bridge: Path, repo: str, number: int) -> dict[str, Any]:
    """Read remote facts exclusively through the C12 anti-corruption boundary."""
    fixture = os.environ.get("DEV_GRAPH_GH_FIXTURE")
    if fixture:
        try:
            value = json.loads(fixture)
        except json.JSONDecodeError as exc:
            raise ContractError("DEV_GRAPH_GH_FIXTURE is invalid JSON") from exc
        if not isinstance(value, dict):
            raise ContractError("DEV_GRAPH_GH_FIXTURE must be an object")
        return value
    receipt = _invoke_json(
        [sys.executable, str(bridge), "--op", "lifecycle-facts", "--repo", repo, "--number", str(number)],
        root,
        "C12 lifecycle-facts",
    )
    if receipt.get("op") != "lifecycle-facts" or not isinstance(receipt.get("result"), dict):
        raise ContractError("C12 lifecycle-facts receipt identity mismatch")
    return receipt["result"]


def c24_context(root: Path, resolver: Path) -> dict[str, Any]:
    """Resolve repository/worktree identity through the declared C24 boundary."""
    receipt = _invoke_json(
        [sys.executable, str(resolver), "--repo-root", str(root), "--mode", "read"],
        root,
        "C24 repository context",
    )
    required = ("repo_root", "repository_id", "git_common_dir", "branch", "head_sha")
    if any(not receipt.get(key) for key in required):
        raise ContractError("C24 repository context omits required identity")
    if Path(str(receipt["repo_root"])).resolve() != root:
        raise ContractError("C24 repository context root mismatch")
    repository_id = str(receipt["repository_id"])
    if not (repository_id.startswith("github:") or repository_id.startswith("local:sha256:")):
        raise ContractError("C24 repository context returned a non-canonical repository_id")
    common = Path(str(receipt["git_common_dir"])).resolve()
    coordination = (receipt.get("coordination_paths") or {}).get("root")
    if not coordination or Path(str(coordination)).resolve() != common / "dev-graph":
        raise ContractError("C24 repository context coordination root mismatch")
    return receipt


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ContractError("task Markdown has no frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ContractError("task Markdown frontmatter is not terminated")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if match:
            values[match.group(1)] = match.group(2).strip("\"'")
    return values, text[end + 5:]


def _section(body: str, headings: tuple[str, ...]) -> str | None:
    alternatives = "|".join(re.escape(item) for item in headings)
    match = re.search(rf"(?ms)^##\s+(?:{alternatives})\s*$\n(?P<body>.*?)(?=^##\s|\Z)", body)
    return match.group("body").strip() if match else None


def _artifact_path(root: Path, node: dict[str, Any]) -> Path:
    raw = node.get("file_path")
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or ".." in Path(raw).parts:
        raise ContractError(f"{_node_id(node)} has invalid task Markdown file_path")
    candidate = (root / raw).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"{_node_id(node)} task Markdown escapes repository authority") from exc
    if not candidate.is_file():
        raise ContractError(f"{_node_id(node)} task Markdown is not a regular file")
    return candidate


def _local_evidence(root: Path, reference: str) -> Path | None:
    parsed = urlparse(reference)
    if parsed.scheme in {"http", "https"}:
        return None
    raw = Path(reference.split("#", 1)[0])
    if raw.is_absolute() or ".." in raw.parts:
        raise ContractError(f"evidence reference escapes repository authority: {reference}")
    path = (root / raw).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"evidence reference escapes repository authority: {reference}") from exc
    if not path.is_file():
        raise ContractError(f"evidence reference is not a file: {reference}")
    return path


def _validate_task_artifact(
    root: Path,
    node: dict[str, Any],
    *,
    require_completion_evidence: bool = False,
    allow_pending_status: bool = False,
    feature_acceptance: list[Any] | None = None,
) -> dict[str, Any]:
    path = _artifact_path(root, node)
    frontmatter, body = _frontmatter(path.read_text(encoding="utf-8"))
    node_id = _node_id(node)
    for key, expected in (("graph_node_id", node_id), ("phase_ref", node.get("phase_ref"))):
        if expected is not None and frontmatter.get(key) != str(expected):
            raise ContractError(f"{node_id} task Markdown {key} does not match graph")
    if require_completion_evidence and not allow_pending_status and frontmatter.get("status") != "done":
        raise ContractError(f"{node_id} task Markdown status is not done")
    verification = _section(body, ("Verification and evidence", "\u691c\u8a3c\u65b9\u6cd5"))
    if not verification or PLACEHOLDER.search(verification):
        raise ContractError(f"{node_id} task Markdown has incomplete verification/evidence section")
    result: dict[str, Any] = {"file_path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
    if not require_completion_evidence:
        return result
    completion = node.get("completion_evidence") or {}
    references = completion.get("evidence_refs") or []
    if completion.get("status") != "done" or not isinstance(references, list) or not references:
        raise ContractError(f"{node_id} completion evidence is incomplete")
    verified: list[dict[str, Any]] = []
    for reference in references:
        if not isinstance(reference, str) or not reference:
            raise ContractError(f"{node_id} has an invalid evidence reference")
        path_ref = _local_evidence(root, reference)
        if path_ref is None:
            continue
        receipt = load_json(path_ref)
        verdict = receipt.get("result", receipt.get("verdict")) if isinstance(receipt, dict) else None
        covered = receipt.get("covered_task_ids", []) if isinstance(receipt, dict) else []
        if verdict != "PASS" or node_id not in covered:
            raise ContractError(f"{node_id} evidence receipt does not prove PASS coverage: {reference}")
        if receipt.get("phase_ref") not in (None, node.get("phase_ref")):
            raise ContractError(f"{node_id} evidence receipt phase_ref mismatch: {reference}")
        if feature_acceptance is not None and receipt.get("feature_acceptance") != feature_acceptance:
            raise ContractError(f"{node_id} evidence receipt does not cover feature acceptance exactly: {reference}")
        if reference not in verification:
            raise ContractError(f"{node_id} task Markdown does not cite completion evidence: {reference}")
        verified.append({"reference": reference, "sha256": _sha256(path_ref)})
    if not verified:
        raise ContractError(f"{node_id} requires at least one local PASS evidence receipt")
    result["evidence_receipts"] = verified
    return result


def _load_registration(path: str | None, node: dict[str, Any], children: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    if not node.get("parent_feature"):
        return None, []
    blockers: list[str] = []
    if not path:
        return None, ["feature rollup requires immutable registration receipt"]
    receipt = load_json(Path(path).resolve(strict=True))
    expected_ids = {_node_id(child) for child in children}
    if not isinstance(receipt, dict) or receipt.get("status") != "registered":
        blockers.append("registration receipt status is not registered")
    if receipt.get("expected_count") != 13 or receipt.get("applied_count") != 13:
        blockers.append("registration receipt does not prove exact 13")
    if receipt.get("phase_refs") != PHASES:
        blockers.append("registration receipt phase_refs are not P01..P13 exact-set")
    if set(receipt.get("node_ids") or []) != expected_ids:
        blockers.append("registration receipt node_ids differ from feature children")
    if receipt.get("feature_package_id") != node.get("feature_package_id") or receipt.get("parent_feature") != node.get("parent_feature"):
        blockers.append("registration receipt feature identity mismatch")
    return receipt, blockers


def feature_rollup(
    root: Path,
    nodes: list[dict[str, Any]],
    node: dict[str, Any],
    registration_path: str | None,
    prospective_completion: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    parent = node.get("parent_feature")
    if not parent:
        return None
    package = node.get("feature_package_id")
    children = [child for child in nodes if child.get("parent_feature") == parent and child.get("feature_package_id") == package]
    phases = [child.get("phase_ref") for child in children]
    blockers: list[str] = []
    artifacts: dict[str, Any] = {}
    feature = next((candidate for candidate in nodes if _node_id(candidate) == parent), None)
    if not feature or feature.get("artifact_kind") not in (None, "feature"):
        blockers.append("parent feature node is missing or invalid")
    acceptance = feature.get("acceptance") if feature else None
    if not isinstance(acceptance, list) or not acceptance:
        blockers.append("parent feature acceptance is empty")
    if len(children) != 13 or set(phases) != set(PHASES) or len(set(phases)) != 13:
        blockers.append("feature children are not exact P01..P13")
    _, receipt_blockers = _load_registration(registration_path, node, children)
    blockers += receipt_blockers
    for child in children:
        effective_done = child.get("status") == "done" or _node_id(child) == _node_id(node)
        if not effective_done:
            blockers.append(f"child not done: {_node_id(child)}")
        if child.get("phase_ref") in EVIDENCE_PHASES:
            try:
                evidence_node = child
                is_current = _node_id(child) == _node_id(node)
                if is_current and prospective_completion is not None:
                    evidence_node = {**child, "status": "done", "completion_evidence": prospective_completion}
                artifacts[str(child.get("phase_ref"))] = _validate_task_artifact(
                    root,
                    evidence_node,
                    require_completion_evidence=True,
                    allow_pending_status=is_current,
                    feature_acceptance=acceptance if isinstance(acceptance, list) else None,
                )
            except (ContractError, OSError) as exc:
                blockers.append(f"{child.get('phase_ref')} acceptance evidence is incomplete: {exc}")
    return {
        "parent_feature": parent,
        "feature_package_id": package,
        "eligible": not blockers,
        "checked_phases": PHASES,
        "required_evidence_phases": sorted(EVIDENCE_PHASES),
        "evidence_artifacts": artifacts,
        "blockers": blockers,
        "writer_patch": {"graph_node_id": parent, "file_path": feature.get("file_path") if feature else None, "set": {"status": "done", "updated_at": utc_now()}} if not blockers else None,
    }


def _linkage_decision(node: dict[str, Any], repo: str, pr: dict[str, Any]) -> dict[str, Any]:
    node_id = _node_id(node)
    markers = MARKER.findall(pr.get("body") or "")
    marker_verified = markers == [node_id]
    closing = pr.get("closingIssuesReferences") or []
    closing_verified = False
    if node.get("tracker_binding") == "github":
        issue = node.get("issue_linkage") or {}
        expected_repo = issue.get("repo") or repo
        expected_number = issue.get("issue_number") or issue.get("number")
        closing_verified = bool(expected_number) and any(
            isinstance(item, dict)
            and item.get("number") == expected_number
            and (item.get("repository") or repo).casefold() == str(expected_repo).casefold()
            for item in closing
        )
    else:
        closing_verified = True
    return {
        "marker_verified": marker_verified,
        "closing_reference_verified": closing_verified,
        "expected_marker": f"dev-graph: {node_id}",
        "observed_markers": markers,
        "eligible": marker_verified and closing_verified,
    }


def _updated_linkages(node: dict[str, Any], repo: str, pr: dict[str, Any], closing_verified: bool, now: str) -> list[dict[str, Any]]:
    number = pr.get("number")
    current = [item for item in (node.get("pull_request_linkages") or []) if item.get("pr_number") != number or item.get("repo", "").casefold() != repo.casefold()]
    merge = pr.get("mergeCommit") or {}
    current.append({
        "repo": repo,
        "pr_number": number,
        "url": pr.get("url"),
        "base_branch": pr.get("baseRefName"),
        "head_branch": pr.get("headRefName") or "unknown",
        "state": "merged",
        "merged_at": pr.get("mergedAt"),
        "merge_commit_sha": merge.get("oid") if isinstance(merge, dict) else merge,
        "linked_at": now,
        "closing_reference_verified": closing_verified,
    })
    return sorted(current, key=lambda item: (item.get("repo", "").casefold(), item.get("pr_number", 0)))


def _writer_request(
    event_key: str,
    graph_path: Path,
    graph_revision: int,
    node: dict[str, Any],
    repo: str,
    pr: dict[str, Any],
    linkage: dict[str, Any],
    task_artifact: dict[str, Any],
    rollup: dict[str, Any] | None,
    completion: dict[str, Any],
) -> dict[str, Any]:
    now = utc_now()
    request = {
        "schema_version": "1.1",
        "owner": "C02/run-dev-graph-node",
        "operation": "apply-lifecycle-request",
        "event_key": event_key,
        "status": "pending",
        "graph_path": graph_path.name,
        "graph_revision_before": graph_revision,
        "graph_sha256_before": _sha256(graph_path),
        "task_patch": {
            "graph_node_id": _node_id(node),
            "file_path": node.get("file_path"),
            "artifact_sha256_before": task_artifact["sha256"],
            "set": {
                "status": "done", "updated_at": now, "completion_evidence": completion,
                "pull_request_linkages": _updated_linkages(node, repo, pr, linkage["closing_reference_verified"], now),
            },
        },
        "feature_patch": rollup.get("writer_patch") if rollup and rollup.get("eligible") else None,
    }
    request["request_digest"] = _json_digest(request)
    return request


def _completion(node: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any]:
    current = node.get("completion_evidence") or {}
    references = [item for item in current.get("evidence_refs", []) if isinstance(item, str) and item]
    if pr.get("url") not in references:
        references.append(pr.get("url"))
    return {
        "status": "done",
        "policy": current.get("policy") or "linked_pr_merged_all",
        "source": "github_pr_merge",
        "completed_at": pr["mergedAt"],
        "reconciled_at": utc_now(),
        "evidence_refs": references,
    }


def _feature_artifact(root: Path, node: dict[str, Any]) -> dict[str, Any]:
    path = _artifact_path(root, node)
    frontmatter, _ = _frontmatter(path.read_text(encoding="utf-8"))
    if frontmatter.get("graph_node_id") != str(_node_id(node)) or frontmatter.get("status") != "done":
        raise ContractError(f"{_node_id(node)} feature Markdown identity/status does not match graph")
    return {"file_path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}


def _writer_applied(path: str | Path | None, request: dict[str, Any], graph_path: Path, root: Path) -> dict[str, Any] | None:
    if not path:
        return None
    receipt = load_json(Path(path).resolve(strict=True))
    node_id = request["task_patch"]["graph_node_id"]
    if not isinstance(receipt, dict) or receipt.get("owner") != "C02/run-dev-graph-node" or receipt.get("status") != "applied":
        raise ContractError("C02 writer receipt is not applied")
    if receipt.get("operation") != "apply-lifecycle-request" or receipt.get("event_key") != request["event_key"] or receipt.get("graph_node_id") != node_id:
        raise ContractError("C02 writer receipt identity mismatch")
    if receipt.get("request_digest") != request["request_digest"]:
        raise ContractError("C02 writer receipt request digest mismatch")
    if receipt.get("graph_sha256_after") != _sha256(graph_path):
        raise ContractError("C02 writer receipt graph digest is stale")
    graph = load_json(graph_path)
    expected_revision = request["graph_revision_before"] + 1
    if graph.get("graph_revision") != expected_revision or receipt.get("graph_revision_after") != expected_revision:
        raise ContractError("C02 writer receipt graph revision mismatch")
    current = next((row for row in _nodes(graph) if _node_id(row) == node_id), None)
    if not current or current.get("status") != "done" or current.get("completion_evidence") != request["task_patch"]["set"]["completion_evidence"]:
        raise ContractError("C02 writer receipt does not match durable task completion")
    if current.get("pull_request_linkages") != request["task_patch"]["set"]["pull_request_linkages"]:
        raise ContractError("C02 writer receipt does not match durable PR linkage")
    artifact = _validate_task_artifact(root, current)
    if artifact["sha256"] != receipt.get("task_artifact_sha256_after"):
        raise ContractError("C02 writer receipt task Markdown digest is stale")
    if _frontmatter(_artifact_path(root, current).read_text(encoding="utf-8"))[0].get("status") != "done":
        raise ContractError("C02 writer receipt did not update task Markdown status")
    return receipt


def _consume_writer(root: Path, consumer: Path, request_path: Path, receipt_path: Path) -> None:
    if not consumer.is_file():
        raise ContractError(f"C02 writer consumer is missing: {consumer}")
    argv = ([sys.executable, str(consumer)] if consumer.suffix == ".py" else [str(consumer)]) + [
        "--operation", "apply-lifecycle-request", "--request", str(request_path), "--receipt", str(receipt_path)
    ]
    _invoke_json(argv, root, "C02 writer consumer")
    if not receipt_path.is_file():
        raise ContractError("C02 writer consumer did not create its receipt")


def _invoke_bd_close(root: Path, bridge: Path, issue_id: str, workspace_id: str | None, event_key: str) -> dict[str, Any]:
    argv = [sys.executable, str(bridge), "--repo-root", str(root), "--op", "close", "--bd-issue-id", issue_id, "--reason", f"dev-graph completion {event_key}"]
    if workspace_id:
        argv += ["--expected-workspace-id", workspace_id]
    return _invoke_json(argv, root, "C28 close")


def _invoke_system_release(root: Path, manager: Path, node_id: str, event_key: str) -> dict[str, Any]:
    receipt = _invoke_json(
        [sys.executable, str(manager), "--repo-root", str(root), "--op", "system-release", "--graph-node-id", node_id, "--completion-event-key", event_key],
        root,
        "C27 system-release",
    )
    if (receipt.get("lease") or {}).get("state") != "released" or (receipt.get("lease") or {}).get("completion_event_key") != event_key:
        raise ContractError("C27 system-release receipt does not match completion event")
    return receipt


def _needs_system_release(node: dict[str, Any]) -> bool:
    return any(item.get("state") in {"pending_review", "pending_merge"} for item in (node.get("execution_contexts") or []) if isinstance(item, dict))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--graph")
    p.add_argument("--graph-node-id")
    p.add_argument("--mode", choices=("reconcile", "check", "drain-pending"), default="reconcile")
    p.add_argument("--repo")
    p.add_argument("--pr", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--writer-receipt")
    p.add_argument("--writer-consumer")
    p.add_argument("--registration-receipt")
    p.add_argument("--gh-bridge")
    p.add_argument("--context-resolver")
    p.add_argument("--bd-bridge")
    p.add_argument("--lease-manager")
    p.add_argument("--expected-workspace-id")
    a = p.parse_args()
    root = Path(a.repo_root).resolve(strict=True)
    resolver = Path(a.context_resolver).resolve() if a.context_resolver else Path(__file__).with_name("resolve-repo-context.py")
    context = c24_context(root, resolver)
    common = Path(str(context["git_common_dir"])).resolve()
    branch = str(context["branch"])
    head_oid = str(context["head_sha"])
    clean = not run(["git", "-C", str(root), "status", "--porcelain"], check=False).stdout.strip()
    coord = common / "dev-graph"
    events_path = coord / "events.json"
    events = load_json(events_path) if events_path.exists() else {"schema_version": "1.0", "events": []}
    transactions = sorted((coord / "completion-receipts").glob("*.json")) if (coord / "completion-receipts").is_dir() else []
    if a.mode == "drain-pending":
        dump({"pending_events": [item for item in events["events"] if not item.get("consumed_at")], "pending_transactions": [load_json(path) for path in transactions if load_json(path).get("status") != "complete"]})
        return 0
    if not all((a.graph, a.graph_node_id, a.repo, a.pr)):
        raise ContractError("check/reconcile require graph, graph-node-id, repo and pr")
    if a.writer_receipt and a.writer_consumer:
        raise ContractError("use either --writer-receipt or --writer-consumer, not both")
    graph_path = Path(a.graph).resolve(strict=True)
    try:
        graph_relative = graph_path.relative_to(root)
    except ValueError as exc:
        raise ContractError("graph path escapes repository content authority") from exc
    data = load_json(graph_path)
    graph_revision = data.get("graph_revision")
    if not isinstance(graph_revision, int) or graph_revision < 0:
        raise ContractError("graph_revision must be a non-negative integer")
    nodes = _nodes(data)
    node = next((item for item in nodes if _node_id(item) == a.graph_node_id), None)
    if not node:
        raise ContractError("graph node not found")
    task_artifact = _validate_task_artifact(root, node)
    gh_bridge = Path(a.gh_bridge).resolve() if a.gh_bridge else Path(__file__).with_name("gh-bridge.py")
    facts = c12_lifecycle_facts(root, gh_bridge, a.repo, a.pr)
    default = facts.get("default_branch") or {}
    pr = facts.get("pull_request") or {}
    if facts.get("repository", "").casefold() != a.repo.casefold() or pr.get("number") != a.pr:
        raise ContractError("C12 lifecycle facts do not match requested repository/PR")
    default_branch, remote_oid = default.get("name"), default.get("oid")
    merge = pr.get("mergeCommit") or {}
    merge_sha = merge.get("oid") if isinstance(merge, dict) else merge
    merged = pr.get("state") == "MERGED" and pr.get("merged") is True and bool(pr.get("mergedAt")) and bool(merge_sha)
    ancestor = bool(merge_sha) and run(["git", "-C", str(root), "merge-base", "--is-ancestor", merge_sha, "HEAD"], check=False).returncode == 0
    linkage = _linkage_decision(node, a.repo, pr)
    synced_default = bool(remote_oid) and head_oid == remote_oid
    decision = merged and pr.get("baseRefName") == default_branch and branch == default_branch and clean and synced_default and ancestor and linkage["eligible"]
    policy_digest = hashlib.sha256(f"{a.graph_node_id}\0{a.pr}\0{default_branch}\0linked_pr_merged\0{linkage['eligible']}".encode()).hexdigest()
    event_key = f"{a.repo}#pr:{a.pr}#{merge_sha or 'unmerged'}"
    needs_release = _needs_system_release(node)
    ledger = {
        "event_key": event_key,
        "c02_writer": "pending",
        "completion_event": "pending",
        "system_release": "pending" if needs_release else "not_applicable",
        "beads_close": "not_applicable" if node.get("tracker_binding") != "beads" else "pending",
    }
    completion = _completion(node, pr) if merged else None
    rollup = feature_rollup(root, nodes, node, a.registration_receipt, completion)
    writer_request = _writer_request(event_key, graph_path, graph_revision, node, a.repo, pr, linkage, task_artifact, rollup, completion) if decision and completion else None
    if writer_request is not None:
        writer_request["graph_path"] = graph_relative.as_posix()
        writer_request["request_digest"] = _json_digest({key: value for key, value in writer_request.items() if key != "request_digest"})
    worktree = {"branch": branch, "clean": clean, "head_oid": head_oid, "remote_default_oid": remote_oid, "synced_default": synced_default}
    conflicts = []
    if not decision:
        if not merged: conflicts.append("PR is not merged")
        if pr.get("baseRefName") != default_branch: conflicts.append("PR does not target remote default branch")
        if branch != default_branch or not clean or not synced_default: conflicts.append("worktree is not clean and synchronized on the remote default branch")
        if not ancestor: conflicts.append("merge commit is not an ancestor of HEAD")
        if not linkage["marker_verified"]: conflicts.append("PR has no exact unique dev-graph marker")
        if not linkage["closing_reference_verified"]: conflicts.append("PR closing reference does not match the bound GitHub Issue")
    common_output = {
        "remote_default_oid": remote_oid,
        "ancestor_verified": ancestor,
        "remote_facts": facts,
        "linkage_decision": linkage,
        "worktree_decision": worktree,
        "feature_rollup": rollup,
    }
    if a.mode == "check" or a.dry_run or not decision:
        dump({**common_output, "policy_decision": "complete" if decision else "pending", "completion_step_ledger": ledger,
              "writer_request": writer_request, "local_patch": None, "completion_event": None, "system_release": "not_run",
              "beads_reflux": "not_run", "pending_events": events["events"], "conflicts": conflicts})
        return 0 if decision else 1
    transaction_dir = coord / "completion-receipts"
    digest = hashlib.sha256(event_key.encode()).hexdigest()
    transaction_path = transaction_dir / f"{digest}.json"
    request_path = transaction_dir / f"{digest}.writer-request.json"
    generated_receipt_path = transaction_dir / f"{digest}.writer-receipt.json"
    if transaction_path.exists():
        transaction = load_json(transaction_path)
        if transaction.get("event_key") != event_key or transaction.get("graph_node_id") != a.graph_node_id:
            raise ContractError("completion transaction identity mismatch")
        pinned_request = transaction.get("writer_request")
        if not isinstance(pinned_request, dict):
            raise ContractError("completion transaction has no pinned C02 request")
        writer_request = pinned_request
        if transaction.get("status") == "complete":
            completed_event = next((item for item in events["events"] if item.get("event_key") == event_key), None)
            dump({**common_output, "policy_decision": "complete", "completion_step_ledger": transaction["steps"],
                  "writer_request": writer_request, "local_patch": transaction.get("writer_receipt"),
                  "completion_event": completed_event, "system_release": transaction.get("system_release_receipt", "not_applicable"),
                  "beads_reflux": transaction.get("beads_reflux", "not_applicable"), "pending_events": [], "conflicts": []})
            return 0
    else:
        transaction = {
            "schema_version": "1.1", "event_key": event_key, "graph_node_id": a.graph_node_id, "status": "pending_writer",
            "writer_request": writer_request, "steps": ledger, "created_at": utc_now(),
        }
    atomic_json(request_path, writer_request)
    atomic_json(transaction_path, transaction)
    writer_path: str | Path | None = a.writer_receipt or transaction.get("writer_receipt_path")
    if not writer_path and a.writer_consumer:
        _consume_writer(root, Path(a.writer_consumer).resolve(), request_path, generated_receipt_path)
        writer_path = generated_receipt_path
    writer_receipt = _writer_applied(writer_path, writer_request, graph_path, root)
    if writer_receipt is None:
        dump({**common_output, "policy_decision": "writer_pending", "completion_step_ledger": transaction["steps"],
              "writer_request": writer_request, "writer_request_path": str(request_path), "local_patch": None,
              "completion_event": None, "system_release": "not_run", "beads_reflux": "not_run",
              "pending_events": events["events"], "conflicts": []})
        return 0
    if rollup and rollup.get("eligible"):
        durable_feature = next((row for row in _nodes(load_json(graph_path)) if _node_id(row) == rollup["parent_feature"]), None)
        if not durable_feature or durable_feature.get("status") != "done":
            raise ContractError("C02 writer receipt omitted eligible feature rollup")
        feature_artifact = _feature_artifact(root, durable_feature)
        if feature_artifact["sha256"] != writer_receipt.get("feature_artifact_sha256_after"):
            raise ContractError("C02 writer receipt feature Markdown digest is stale")
    transaction["steps"]["c02_writer"] = "applied"
    transaction["writer_receipt_path"] = str(Path(writer_path).resolve())
    transaction["writer_receipt"] = {key: writer_receipt.get(key) for key in (
        "owner", "operation", "status", "event_key", "graph_node_id", "request_digest", "graph_sha256_after",
        "graph_revision_after", "task_artifact_sha256_after", "feature_graph_node_id", "feature_artifact_sha256_after",
    )}
    transaction["status"] = "local_applied"
    atomic_json(transaction_path, transaction)
    event = next((item for item in events["events"] if item.get("event_key") == event_key), None)
    if not event:
        event = {
            "type": "completion", "event_key": event_key,
            "repository_id": context["repository_id"],
            "graph_node_id": a.graph_node_id, "merge_commit_sha": merge_sha, "policy_digest": policy_digest,
            "default_branch": default_branch, "remote_default_oid": remote_oid, "created_at": utc_now(),
        }
        events["events"].append(event)
        atomic_json(events_path, events)
    transaction["steps"]["completion_event"] = "applied"
    transaction["status"] = "event_applied"
    atomic_json(transaction_path, transaction)
    system_release: Any = "not_applicable"
    if needs_release:
        if transaction["steps"].get("system_release") == "applied":
            system_release = transaction.get("system_release_receipt")
        else:
            manager = Path(a.lease_manager).resolve() if a.lease_manager else Path(__file__).with_name("manage-worktree-lease.py")
            try:
                system_release = _invoke_system_release(root, manager, a.graph_node_id, event_key)
            except ContractError as exc:
                transaction["steps"]["system_release"] = "pending_retry"
                transaction["status"] = "pending_retry"
                atomic_json(transaction_path, transaction)
                dump({**common_output, "policy_decision": "pending_retry", "completion_step_ledger": transaction["steps"],
                      "writer_request": writer_request, "local_patch": writer_receipt, "completion_event": event,
                      "system_release": None, "beads_reflux": "not_run", "conflicts": [str(exc)]})
                return 1
            transaction["steps"]["system_release"] = "applied"
            transaction["system_release_receipt"] = system_release
            transaction["status"] = "lease_released"
            atomic_json(transaction_path, transaction)
        events = load_json(events_path)
        event = next(item for item in events["events"] if item.get("event_key") == event_key)
    beads_reflux: Any = "not_applicable"
    if node.get("tracker_binding") == "beads":
        linkage_data = node.get("beads_linkage") or {}
        issue_id = linkage_data.get("bd_issue_id")
        if not issue_id:
            transaction["steps"]["beads_close"] = "pending_retry"
            transaction["status"] = "pending_retry"
            atomic_json(transaction_path, transaction)
            dump({**common_output, "policy_decision": "pending_retry", "completion_step_ledger": transaction["steps"],
                  "writer_request": writer_request, "local_patch": writer_receipt, "completion_event": event,
                  "system_release": system_release, "beads_reflux": None, "conflicts": ["beads task has no bd_issue_id"]})
            return 1
        bridge = Path(a.bd_bridge).resolve() if a.bd_bridge else Path(__file__).with_name("bd-bridge.py")
        try:
            beads_reflux = _invoke_bd_close(root, bridge, issue_id, a.expected_workspace_id, event_key)
        except ContractError as exc:
            transaction["steps"]["beads_close"] = "pending_retry"
            transaction["status"] = "pending_retry"
            atomic_json(transaction_path, transaction)
            dump({**common_output, "policy_decision": "pending_retry", "completion_step_ledger": transaction["steps"],
                  "writer_request": writer_request, "local_patch": writer_receipt, "completion_event": event,
                  "system_release": system_release, "beads_reflux": None, "conflicts": [str(exc)]})
            return 1
        transaction["steps"]["beads_close"] = "applied"
        transaction["beads_reflux"] = beads_reflux
    transaction["status"] = "complete"
    transaction["completed_at"] = utc_now()
    atomic_json(transaction_path, transaction)
    dump({**common_output, "policy_decision": "complete", "completion_step_ledger": transaction["steps"],
          "writer_request": writer_request, "local_patch": writer_receipt, "completion_event": event,
          "system_release": system_release, "beads_reflux": beads_reflux, "pending_events": [], "conflicts": []})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
