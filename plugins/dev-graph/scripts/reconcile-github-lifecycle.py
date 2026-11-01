#!/usr/bin/env python3
# /// script
# name: reconcile-github-lifecycle
# purpose: Converge C12-verified default-branch PR facts through a C02 consumer into idempotent completion and C27 release events.
# inputs: ["argv: --repo-root PATH --graph FILE --graph-node-id ID --mode reconcile|check|drain-pending|backfill-done [--writer-consumer PATH|--writer-receipt PATH|--writer-request-only]"]
# outputs: ["stdout: JSON remote facts, linkage decision, C02 request/receipt, step ledger and completion event"]
# requires-python = ">=3.10"
# dependencies: ["gh-bridge.py", "manage-worktree-lease.py", "bd-bridge.py", "build-graph-node.py", "resolve-repo-context.py"]
# contexts: [A, B, C, E]
# network: true
# write-scope: git-common-dir completion request/transaction/event ledgers only; graph and Markdown writes belong to C02
# ///
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない (子の起動にも -B を渡す)。
sys.dont_write_bytecode = True

from _common import ContractError, atomic_json, dump, load_json, run, utc_now

PHASES = [f"P{i:02d}" for i in range(1, 14)]
EVIDENCE_PHASES = {"P07", "P10", "P11"}
MARKER = re.compile(r"(?mi)^\s*dev-graph:\s*([^\s#]+)\s*$")
# 完了判定用なので、C02 (build-graph-node の readiness) より意図して厳しい: 検証節に `<…>` (autolink を含む) や
# TODO/TBD が 1 つでも残れば done にしない。C02 は section が埋まったかを見るだけなので基準をそろえない。
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
        [sys.executable, "-B", str(bridge), "--op", "lifecycle-facts", "--repo", repo, "--number", str(number)],
        root,
        "C12 lifecycle-facts",
    )
    if receipt.get("op") != "lifecycle-facts" or not isinstance(receipt.get("result"), dict):
        raise ContractError("C12 lifecycle-facts receipt identity mismatch")
    return receipt["result"]


def c24_context(root: Path, resolver: Path) -> dict[str, Any]:
    """Resolve repository/worktree identity through the declared C24 boundary."""
    receipt = _invoke_json(
        [sys.executable, "-B", str(resolver), "--repo-root", str(root), "--mode", "read"],
        root,
        "C24 repository context",
    )
    required_identity = ("repo_root", "repository_id", "git_common_dir", "head_sha")
    if any(not receipt.get(key) for key in required_identity) or "branch" not in receipt:
        raise ContractError("C24 repository context omits required identity")
    branch = receipt["branch"]
    if branch is not None and (not isinstance(branch, str) or not branch.strip()):
        raise ContractError("C24 repository context returned an invalid branch state")
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


def _published_task_verification(root: Path, node: dict[str, Any]) -> tuple[str | None, Path | None]:
    lineage = node.get("source_lineage") or {}
    raw = lineage.get("source_path") if isinstance(lineage, dict) else None
    if not isinstance(raw, str) or not raw:
        return None, None
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ContractError(f"{_node_id(node)} published task spec escapes repository authority")
    try:
        path = (root / relative).resolve(strict=True)
        path.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ContractError(f"{_node_id(node)} published task spec is not a repository file") from exc
    if not path.is_file():
        raise ContractError(f"{_node_id(node)} published task spec is not a regular file")
    source_digest = lineage.get("source_digest")
    if isinstance(source_digest, str) and re.fullmatch(r"[0-9a-f]{64}", source_digest):
        if source_digest not in path.parts:
            raise ContractError(f"{_node_id(node)} published task spec generation does not match source digest")
    body = path.read_text(encoding="utf-8")
    return _section(body, ("Verification and evidence", "\u691c\u8a3c\u65b9\u6cd5")), path


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
    verification_source: Path | None = None
    if not verification:
        verification, verification_source = _published_task_verification(root, node)
    if not verification or PLACEHOLDER.search(verification):
        raise ContractError(f"{node_id} task Markdown has incomplete verification/evidence section")
    result: dict[str, Any] = {"file_path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
    if verification_source is not None:
        result["verification_source"] = {
            "file_path": verification_source.relative_to(root).as_posix(),
            "sha256": _sha256(verification_source),
        }
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


def _linkage_decision(
    node: dict[str, Any], repo: str, pr: dict[str, Any], *, gate_verified: bool = False,
) -> dict[str, Any]:
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
    linkage_verified = marker_verified or (node.get("tracker_binding") == "beads" and gate_verified)
    return {
        "marker_verified": marker_verified,
        "gh_pr_gate_verified": gate_verified,
        "linkage_verified": linkage_verified,
        "closing_reference_verified": closing_verified,
        "expected_marker": f"dev-graph: {node_id}",
        "observed_markers": markers,
        "eligible": linkage_verified and closing_verified,
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
                "pull_request_linkages": copy.deepcopy(node.get("pull_request_linkages") or []),
            },
        },
        "feature_patch": rollup.get("writer_patch") if rollup and rollup.get("eligible") else None,
    }
    request["request_digest"] = _json_digest(request)
    return request


def _completion(node: dict[str, Any], prs: list[dict[str, Any]], policy: str) -> dict[str, Any]:
    current = node.get("completion_evidence") or {}
    references = [item for item in current.get("evidence_refs", []) if isinstance(item, str) and item]
    for pr in prs:
        if pr.get("url") and pr.get("url") not in references:
            references.append(pr["url"])
    completed = sorted(str(pr["mergedAt"]) for pr in prs if pr.get("mergedAt"))
    return {
        "status": "done",
        "policy": f"linked_pr_merged_{policy}",
        "source": "github_pr_merge",
        "completed_at": completed[-1],
        "reconciled_at": utc_now(),
        "evidence_refs": references,
    }


def _completion_policy(root: Path) -> str:
    config_path = root / ".dev-graph" / "config.json"
    if not config_path.is_file():
        return "all"
    config = load_json(config_path)
    policy = (((config.get("github") or {}).get("completion_policy") or {}).get("required_pull_requests")) if isinstance(config, dict) else None
    if policy not in (None, "all", "any"):
        raise ContractError("github completion_policy.required_pull_requests must be all or any")
    return policy or "all"


def _beads_gate_verified(
    root: Path, bridge: Path, node: dict[str, Any], pr_number: int,
) -> bool:
    issue_id = (node.get("beads_linkage") or {}).get("bd_issue_id")
    if not issue_id:
        return False
    try:
        receipt = _invoke_json(
            [
                sys.executable, "-B", str(bridge), "--repo-root", str(root), "--op", "gate-check",
                "--bd-issue-id", str(issue_id), "--pr", str(pr_number),
            ],
            root,
            "C28 gh:pr gate check",
        )
    except ContractError as exc:
        if "gh:pr gate does not exist" in str(exc):
            return False
        raise
    return receipt.get("op") == "gate-check" and bool((receipt.get("result") or {}).get("gate"))


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
    argv = ([sys.executable, "-B", str(consumer)] if consumer.suffix == ".py" else [str(consumer)]) + [
        "--operation", "apply-lifecycle-request", "--request", str(request_path), "--receipt", str(receipt_path)
    ]
    _invoke_json(argv, root, "C02 writer consumer")
    if not receipt_path.is_file():
        raise ContractError("C02 writer consumer did not create its receipt")


def _invoke_bd_close(root: Path, bridge: Path, issue_id: str, workspace_id: str | None, event_key: str) -> dict[str, Any]:
    argv = [sys.executable, "-B", str(bridge), "--repo-root", str(root), "--op", "close", "--bd-issue-id", issue_id, "--reason", f"dev-graph completion {event_key}"]
    if workspace_id:
        argv += ["--expected-workspace-id", workspace_id]
    return _invoke_json(argv, root, "C28 close")


def _invoke_system_release(root: Path, manager: Path, node_id: str, event_key: str) -> dict[str, Any]:
    receipt = _invoke_json(
        [sys.executable, "-B", str(manager), "--repo-root", str(root), "--op", "system-release", "--graph-node-id", node_id, "--completion-event-key", event_key],
        root,
        "C27 system-release",
    )
    if (receipt.get("lease") or {}).get("state") != "released" or (receipt.get("lease") or {}).get("completion_event_key") != event_key:
        raise ContractError("C27 system-release receipt does not match completion event")
    return receipt


def _needs_system_release(node: dict[str, Any]) -> bool:
    return any(item.get("state") in {"pending_review", "pending_merge"} for item in (node.get("execution_contexts") or []) if isinstance(item, dict))


def _backfill_done(
    *,
    root: Path,
    context: dict[str, Any],
    coord: Path,
    events_path: Path,
    events: dict[str, Any],
    graph_path: Path,
    graph: dict[str, Any],
    node: dict[str, Any],
    task_artifact: dict[str, Any],
    requested_repo: str | None,
    requested_pr: int | None,
    bd_bridge: Path,
    expected_workspace_id: str | None,
) -> dict[str, Any]:
    node_id = str(_node_id(node))
    completion = node.get("completion_evidence") or {}
    if node.get("status") != "done" or completion.get("status") != "done":
        raise ContractError("backfill-done requires an already-done graph node")
    frontmatter, _ = _frontmatter(_artifact_path(root, node).read_text(encoding="utf-8"))
    if frontmatter.get("status") != "done":
        raise ContractError("backfill-done requires done task Markdown frontmatter")
    if _needs_system_release(node):
        raise ContractError("backfill-done refuses a node with an unreleased execution context")
    leases_path = coord / "leases.json"
    if leases_path.exists():
        lease_ledger = load_json(leases_path)
        active_leases = [
            item
            for item in lease_ledger.get("leases", [])
            if isinstance(item, dict)
            and item.get("graph_node_id") == node_id
            and item.get("state") != "released"
        ]
        if active_leases:
            raise ContractError(
                "backfill-done refuses a node with an active common-dir lease"
            )
    raw_policy = completion.get("policy")
    match = re.fullmatch(r"linked_pr_merged_(all|any)", str(raw_policy))
    if not match:
        raise ContractError(
            "backfill-done requires linked_pr_merged_all|any completion policy"
        )
    completion_policy = match.group(1)
    raw_linkages = node.get("pull_request_linkages") or []
    if not isinstance(raw_linkages, list) or not raw_linkages:
        raise ContractError("backfill-done requires stored pull_request_linkages")
    linkages: list[dict[str, Any]] = []
    for linkage in raw_linkages:
        if not isinstance(linkage, dict):
            raise ContractError("backfill-done pull request linkage must be an object")
        repo = linkage.get("repo")
        number = linkage.get("pr_number")
        merge_sha = linkage.get("merge_commit_sha")
        if (
            not isinstance(repo, str)
            or not repo
            or not isinstance(number, int)
            or number < 1
            or not isinstance(merge_sha, str)
            or not re.fullmatch(r"[0-9a-f]{40}", merge_sha)
            or str(linkage.get("state", "")).casefold() != "merged"
            or not linkage.get("merged_at")
            or linkage.get("closing_reference_verified") is not True
        ):
            raise ContractError(
                "backfill-done requires verified merged PR linkage facts"
            )
        linkages.append(linkage)
    linkages.sort(key=lambda item: (str(item["repo"]).casefold(), int(item["pr_number"])))
    if requested_repo is not None or requested_pr is not None:
        if not requested_repo or not requested_pr:
            raise ContractError("backfill-done accepts --repo and --pr only together")
        selected = next(
            (
                item
                for item in linkages
                if str(item["repo"]).casefold() == requested_repo.casefold()
                and item["pr_number"] == requested_pr
            ),
            None,
        )
        if selected is None:
            raise ContractError(
                "backfill-done requested PR does not match stored linkage"
            )
    else:
        selected = max(linkages, key=lambda item: str(item["merged_at"]))
    policy_material = [
        completion_policy,
        *[
            f"{item['repo']}#{item['pr_number']}#{item['merge_commit_sha']}#True"
            for item in linkages
        ],
    ]
    policy_digest = hashlib.sha256("\0".join(policy_material).encode()).hexdigest()
    event_key = (
        f"{selected['repo']}#task:{node_id}#policy:{policy_digest}"
    )
    existing_event = next(
        (
            item
            for item in events.get("events", [])
            if item.get("event_key") == event_key
        ),
        None,
    )
    if existing_event is not None and existing_event.get("graph_node_id") != node_id:
        raise ContractError("backfill-done event key is bound to another graph node")
    event = existing_event or {
        "type": "completion",
        "event_key": event_key,
        "repository_id": context["repository_id"],
        "graph_node_id": node_id,
        "merge_commit_sha": selected["merge_commit_sha"],
        "policy_digest": policy_digest,
        "default_branch": selected.get("base_branch"),
        "remote_default_oid": None,
        "created_at": utc_now(),
        "backfilled_from_durable_completion": True,
    }
    writer_receipt = {
        "schema_version": "1.0",
        "owner": "C02/run-dev-graph-node",
        "operation": "verify-existing-lifecycle-completion",
        "status": "applied",
        "event_key": event_key,
        "graph_node_id": node_id,
        "graph_sha256_after": _sha256(graph_path),
        "graph_revision_after": graph.get("graph_revision"),
        "task_artifact_sha256_after": task_artifact["sha256"],
        "completion_evidence": copy.deepcopy(completion),
        "verified_at": utc_now(),
    }
    beads_reflux: Any = "not_applicable"
    beads_step = "not_applicable"
    if node.get("tracker_binding") == "beads":
        issue_id = (node.get("beads_linkage") or {}).get("bd_issue_id")
        if not issue_id:
            raise ContractError("backfill-done beads node has no bd_issue_id")
        argv = [
            sys.executable,
            "-B",
            str(bd_bridge),
            "--repo-root",
            str(root),
            "--op",
            "show",
            "--bd-issue-id",
            str(issue_id),
        ]
        if expected_workspace_id:
            argv += ["--expected-workspace-id", expected_workspace_id]
        beads_reflux = _invoke_json(argv, root, "C28 show for completion backfill")
        result = beads_reflux.get("result") or {}
        if not isinstance(result, dict) or result.get("status") != "closed":
            raise ContractError("backfill-done requires the bound Beads task to be closed")
        beads_step = "verified_existing"
    steps = {
        "event_key": event_key,
        "c02_writer": "verified_existing",
        "completion_event": "applied",
        "system_release": "not_applicable",
        "beads_close": beads_step,
    }
    digest = hashlib.sha256(event_key.encode()).hexdigest()
    transaction_path = coord / "completion-receipts" / f"{digest}.json"
    transaction = {
        "schema_version": "1.1",
        "event_key": event_key,
        "graph_node_id": node_id,
        "status": "complete",
        "writer_request": None,
        "writer_receipt": writer_receipt,
        "steps": steps,
        "backfill_mode": "verified_existing_done",
        "beads_reflux": beads_reflux,
        "created_at": event["created_at"],
        "completed_at": utc_now(),
    }
    if transaction_path.exists():
        existing_transaction = load_json(transaction_path)
        if (
            existing_transaction.get("event_key") != event_key
            or existing_transaction.get("graph_node_id") != node_id
        ):
            raise ContractError("backfill-done transaction identity mismatch")
        if existing_transaction.get("status") != "complete":
            raise ContractError("backfill-done found an incomplete transaction")
        transaction = existing_transaction
    else:
        atomic_json(transaction_path, transaction)
    if existing_event is None:
        events.setdefault("events", []).append(event)
        atomic_json(events_path, events)
    return {
        "policy_decision": "complete",
        "backfill_mode": "verified_existing_done",
        "remote_default_oid": None,
        "ancestor_verified": True,
        "remote_facts": None,
        "required_pull_requests": completion_policy,
        "required_pr_decisions": [],
        "linkage_decision": {
            "stored_linkages_verified": True,
            "eligible": True,
        },
        "worktree_decision": {
            "branch": context["branch"],
            "head_oid": context["head_sha"],
            "durable_graph_write": False,
        },
        "feature_rollup": None,
        "completion_step_ledger": transaction["steps"],
        "writer_request": None,
        "local_patch": transaction["writer_receipt"],
        "completion_event": event,
        "system_release": "not_applicable",
        "beads_reflux": transaction.get("beads_reflux", beads_reflux),
        "pending_events": [],
        "conflicts": [],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--graph")
    p.add_argument("--graph-node-id")
    p.add_argument(
        "--mode",
        choices=("reconcile", "check", "drain-pending", "backfill-done"),
        default="reconcile",
    )
    p.add_argument("--repo")
    p.add_argument("--pr", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--writer-receipt")
    p.add_argument("--writer-consumer")
    p.add_argument("--writer-request-only", action="store_true")
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
    branch_value = context["branch"]
    branch = str(branch_value) if branch_value is not None else None
    head_oid = str(context["head_sha"])
    clean = not run(["git", "-C", str(root), "status", "--porcelain"], check=False).stdout.strip()
    coord = common / "dev-graph"
    events_path = coord / "events.json"
    events = load_json(events_path) if events_path.exists() else {"schema_version": "1.0", "events": []}
    transactions = sorted((coord / "completion-receipts").glob("*.json")) if (coord / "completion-receipts").is_dir() else []
    if a.mode == "drain-pending":
        dump({"pending_events": [item for item in events["events"] if not item.get("consumed_at")], "pending_transactions": [load_json(path) for path in transactions if load_json(path).get("status") != "complete"]})
        return 0
    if a.mode == "backfill-done":
        if not all((a.graph, a.graph_node_id)):
            raise ContractError("backfill-done requires graph and graph-node-id")
    elif not all((a.graph, a.graph_node_id, a.repo, a.pr)):
        raise ContractError("check/reconcile require graph, graph-node-id, repo and pr")
    if a.writer_receipt and a.writer_consumer:
        raise ContractError("use either --writer-receipt or --writer-consumer, not both")
    if a.writer_request_only and (a.writer_receipt or a.writer_consumer):
        raise ContractError(
            "--writer-request-only cannot be combined with a writer receipt/consumer"
        )
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
    if a.mode == "backfill-done":
        if a.dry_run or a.writer_receipt or a.writer_consumer or a.writer_request_only:
            raise ContractError(
                "backfill-done cannot be combined with writer or dry-run options"
            )
        bridge = Path(a.bd_bridge).resolve() if a.bd_bridge else Path(__file__).with_name("bd-bridge.py")
        dump(
            _backfill_done(
                root=root,
                context=context,
                coord=coord,
                events_path=events_path,
                events=events,
                graph_path=graph_path,
                graph=data,
                node=node,
                task_artifact=task_artifact,
                requested_repo=a.repo,
                requested_pr=a.pr,
                bd_bridge=bridge,
                expected_workspace_id=a.expected_workspace_id,
            )
        )
        return 0
    gh_bridge = Path(a.gh_bridge).resolve() if a.gh_bridge else Path(__file__).with_name("gh-bridge.py")
    requested_facts = c12_lifecycle_facts(root, gh_bridge, a.repo, a.pr)
    requested_pr = requested_facts.get("pull_request") or {}
    if requested_facts.get("repository", "").casefold() != a.repo.casefold() or requested_pr.get("number") != a.pr:
        raise ContractError("C12 lifecycle facts do not match requested repository/PR")
    required_keys = {
        (str(item.get("repo")), int(item.get("pr_number")))
        for item in (node.get("pull_request_linkages") or [])
        if isinstance(item, dict) and item.get("repo") and item.get("pr_number")
    }
    required_keys.add((a.repo, a.pr))
    fact_sets: dict[tuple[str, int], dict[str, Any]] = {(a.repo, a.pr): requested_facts}
    for linked_repo, linked_number in sorted(required_keys):
        if (linked_repo, linked_number) not in fact_sets:
            fact_sets[(linked_repo, linked_number)] = c12_lifecycle_facts(
                root, gh_bridge, linked_repo, linked_number
            )
    completion_policy = _completion_policy(root)
    bd_bridge = Path(a.bd_bridge).resolve() if a.bd_bridge else Path(__file__).with_name("bd-bridge.py")
    pr_decisions: list[dict[str, Any]] = []
    node_for_writer = dict(node)
    for (linked_repo, linked_number), remote in sorted(fact_sets.items()):
        remote_default = remote.get("default_branch") or {}
        linked_pr = remote.get("pull_request") or {}
        if remote.get("repository", "").casefold() != linked_repo.casefold() or linked_pr.get("number") != linked_number:
            raise ContractError("C12 lifecycle facts do not match a linked repository/PR")
        merge = linked_pr.get("mergeCommit") or {}
        linked_sha = merge.get("oid") if isinstance(merge, dict) else merge
        merged_ok = (
            linked_pr.get("state") == "MERGED"
            and linked_pr.get("merged") is True
            and bool(linked_pr.get("mergedAt"))
            and bool(linked_sha)
        )
        ancestor_ok = bool(linked_sha) and run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", linked_sha, "HEAD"],
            check=False,
        ).returncode == 0
        linkage = _linkage_decision(node, linked_repo, linked_pr)
        if node.get("tracker_binding") == "beads" and not linkage["marker_verified"]:
            gate_verified = _beads_gate_verified(root, bd_bridge, node, linked_number)
            linkage = _linkage_decision(node, linked_repo, linked_pr, gate_verified=gate_verified)
        target_ok = linked_pr.get("baseRefName") == remote_default.get("name")
        eligible = merged_ok and ancestor_ok and target_ok and linkage["eligible"]
        pr_decisions.append({
            "repo": linked_repo,
            "pr_number": linked_number,
            "facts": remote,
            "pull_request": linked_pr,
            "merge_commit_sha": linked_sha,
            "merged": merged_ok,
            "ancestor_verified": ancestor_ok,
            "target_default_verified": target_ok,
            "linkage": linkage,
            "eligible": eligible,
        })
        if merged_ok:
            node_for_writer["pull_request_linkages"] = _updated_linkages(
                node_for_writer, linked_repo, linked_pr, linkage["closing_reference_verified"], utc_now()
            )
    requested_decision = next(
        item for item in pr_decisions
        if item["repo"].casefold() == a.repo.casefold() and item["pr_number"] == a.pr
    )
    facts = requested_facts
    pr = requested_pr
    linkage = requested_decision["linkage"]
    default = facts.get("default_branch") or {}
    default_branch, remote_oid = default.get("name"), default.get("oid")
    merge_sha = requested_decision["merge_commit_sha"]
    merged = requested_decision["merged"]
    ancestor = requested_decision["ancestor_verified"]
    synced_default = bool(remote_oid) and head_oid == remote_oid
    remote_policy_satisfied = (
        all(item["eligible"] for item in pr_decisions)
        if completion_policy == "all"
        else any(item["eligible"] for item in pr_decisions)
    )
    decision = remote_policy_satisfied and branch == default_branch and clean and synced_default
    policy_material = [
        completion_policy,
        *[
            f"{item['repo']}#{item['pr_number']}#{item['merge_commit_sha'] or 'unmerged'}#{item['eligible']}"
            for item in pr_decisions
        ],
    ]
    policy_digest = hashlib.sha256("\0".join(policy_material).encode()).hexdigest()
    event_key = f"{a.repo}#task:{a.graph_node_id}#policy:{policy_digest}"
    needs_release = _needs_system_release(node)
    ledger = {
        "event_key": event_key,
        "c02_writer": "pending",
        "completion_event": "pending",
        "system_release": "pending" if needs_release else "not_applicable",
        "beads_close": "not_applicable" if node.get("tracker_binding") != "beads" else "pending",
    }
    eligible_prs = [item["pull_request"] for item in pr_decisions if item["eligible"]]
    completion = _completion(node, eligible_prs, completion_policy) if remote_policy_satisfied else None
    rollup = feature_rollup(root, nodes, node, a.registration_receipt, completion)
    writer_request = _writer_request(event_key, graph_path, graph_revision, node_for_writer, a.repo, pr, linkage, task_artifact, rollup, completion) if decision and completion else None
    if writer_request is not None:
        writer_request["graph_path"] = graph_relative.as_posix()
        writer_request["request_digest"] = _json_digest({key: value for key, value in writer_request.items() if key != "request_digest"})
    worktree = {"branch": branch, "clean": clean, "head_oid": head_oid, "remote_default_oid": remote_oid, "synced_default": synced_default}
    conflicts = []
    if not decision:
        for item in pr_decisions:
            if not item["merged"]: conflicts.append(f"PR {item['repo']}#{item['pr_number']} is not merged")
            if not item["target_default_verified"]: conflicts.append(f"PR {item['repo']}#{item['pr_number']} does not target remote default branch")
            if not item["ancestor_verified"]: conflicts.append(f"PR {item['repo']}#{item['pr_number']} merge commit is not an ancestor of HEAD")
            if not item["linkage"]["linkage_verified"]: conflicts.append(f"PR {item['repo']}#{item['pr_number']} has no exact marker or gh:pr gate")
            if not item["linkage"]["closing_reference_verified"]: conflicts.append(f"PR {item['repo']}#{item['pr_number']} closing reference does not match the bound GitHub Issue")
        if branch != default_branch or not clean or not synced_default: conflicts.append("worktree is not clean and synchronized on the remote default branch")
    common_output = {
        "remote_default_oid": remote_oid,
        "ancestor_verified": ancestor,
        "remote_facts": facts,
        "required_pull_requests": completion_policy,
        "required_pr_decisions": pr_decisions,
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
    if not writer_path and not a.writer_request_only:
        consumer = (
            Path(a.writer_consumer).resolve()
            if a.writer_consumer
            else Path(__file__).with_name("build-graph-node.py")
        )
        _consume_writer(root, consumer, request_path, generated_receipt_path)
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
