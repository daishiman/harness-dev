#!/usr/bin/env python3
# /// script
# name: manage-worktree-lease
# purpose: Atomically coordinate per-node worktree reservations, Beads claim sagas and completion-event releases.
# inputs: ["argv: --op context|claim|heartbeat|park|release|system-release|list|reclaim"]
# outputs: ["stdout: JSON lease/event/writer receipt"]
# requires-python = ">=3.10"
# dependencies: ["bd-bridge.py", "register-package.py"]
# contexts: [A, B, C, E]
# network: true
# write-scope: verified git-common-dir/dev-graph ephemeral coordination only
# ///
from __future__ import annotations

import argparse
import fcntl
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _common import ContractError, atomic_json, dump, git, load_json, run, utc_now

ACTIVE = {"reserving", "claimed", "in_progress", "pending_review", "pending_merge", "claim_pending_local_repair"}


def context(root: Path, resolver: Path | None = None) -> dict[str, str]:
    """Consume C24's canonical repository/worktree identity instead of re-deriving it."""
    boundary = resolver or Path(__file__).with_name("resolve-repo-context.py")
    if not boundary.is_file():
        raise ContractError(f"missing C24 context resolver: {boundary}")
    cp = run(
        [sys.executable, str(boundary), "--repo-root", str(root), "--mode", "read"],
        cwd=root,
        check=False,
    )
    if cp.returncode:
        raise ContractError(f"C24 context resolver failed ({cp.returncode}): {(cp.stderr or cp.stdout).strip()}")
    try:
        receipt = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("C24 context resolver returned invalid JSON") from exc
    required = ("repo_root", "git_common_dir", "repository_id", "worktree_id", "branch", "default_branch", "head_sha")
    if not isinstance(receipt, dict) or any(not receipt.get(key) for key in required):
        raise ContractError("C24 context resolver omitted required identity")
    top = Path(str(receipt["repo_root"])).resolve()
    if top != root.resolve():
        raise ContractError("C24 context resolver root mismatch")
    repository_id = str(receipt["repository_id"])
    if not (repository_id.startswith("github:") or repository_id.startswith("local:sha256:")):
        raise ContractError("C24 context resolver returned a non-canonical repository_id")
    return {
        "repo_root": str(top),
        "git_common_dir": str(Path(str(receipt["git_common_dir"])).resolve()),
        "repository_id": repository_id,
        "worktree_id": str(receipt["worktree_id"]),
        "branch": str(receipt["branch"]),
        "base_branch": str(receipt["default_branch"]),
        "head_sha": str(receipt["head_sha"]),
    }


def invoke_bd_bridge(root: Path, bridge: Path, argv: list[str]) -> dict[str, Any]:
    if not bridge.is_file(): raise ContractError(f"missing C28 bridge: {bridge}")
    cp = run([sys.executable, str(bridge), "--repo-root", str(root), *argv], cwd=root, check=False)
    if cp.returncode:
        raise ContractError(f"C28 bridge failed ({cp.returncode}): {(cp.stderr or cp.stdout).strip()}")
    try:
        value = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("C28 bridge returned invalid JSON") from exc
    if not isinstance(value, dict): raise ContractError("C28 bridge receipt must be an object")
    return value


def _ensure_claim_branch(root: Path, graph_node_id: str, requested: str | None, current: dict[str, str]) -> dict[str, str]:
    canonical = f"devgraph/{graph_node_id}"
    if requested and requested != canonical:
        raise ContractError(f"claim branch must be canonical {canonical}")
    if run(["git", "check-ref-format", "--branch", canonical], cwd=root, check=False).returncode:
        raise ContractError("graph node id cannot form a canonical devgraph branch")
    if current["branch"] == canonical:
        return current
    if git(["status", "--porcelain"], root):
        raise ContractError("canonical claim branch creation requires a clean worktree")
    if git(["show-ref", "--verify", f"refs/heads/{canonical}"], root, check=False):
        raise ContractError("canonical claim branch already exists in another context")
    cp = run(["git", "switch", "-c", canonical], cwd=root, check=False)
    if cp.returncode:
        raise ContractError(f"cannot create canonical claim branch: {(cp.stderr or cp.stdout).strip()}")
    refreshed = context(root)
    if refreshed["branch"] != canonical:
        raise ContractError("canonical claim branch creation did not converge")
    return refreshed


def _resolve_graph(root: Path, explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit)
        candidate = candidate if candidate.is_absolute() else root / candidate
    else:
        config_path = root / ".dev-graph" / "config.json"
        if not config_path.is_file():
            raise ContractError("claim requires --graph or .dev-graph/config.json")
        config = load_json(config_path)
        graph = (config.get("local_state") or {}).get("graph") if isinstance(config, dict) else None
        if not isinstance(graph, str) or not graph:
            raise ContractError("repo config omits local_state.graph")
        candidate = root / graph
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ContractError("execution-context graph escapes repository content authority") from exc
    return resolved


def invoke_execution_context_consumer(
    root: Path,
    consumer: Path,
    graph: Path,
    lease: dict[str, Any],
    ctx: dict[str, str],
) -> dict[str, Any]:
    if not consumer.is_file():
        raise ContractError(f"missing C02 execution-context consumer: {consumer}")
    acquired = lease.get("created_at")
    context_value = {
        "worktree_id": lease["worktree_id"],
        "branch": lease["branch"],
        "base_branch": ctx["base_branch"],
        "head_sha": lease["head_sha"],
        "state": "claimed",
        "lease_acquired_at": acquired,
        "last_seen_at": lease["updated_at"],
        "released_at": None,
    }
    cp = run([
        sys.executable, str(consumer), "execution-context", "--repo-root", str(root),
        "--graph", str(graph), "--graph-node-id", lease["graph_node_id"],
        "--context-json", json.dumps(context_value, ensure_ascii=False, sort_keys=True),
    ], cwd=root, check=False)
    if cp.returncode:
        raise ContractError(f"C02 execution-context consumer failed ({cp.returncode}): {(cp.stderr or cp.stdout).strip()}")
    try:
        receipt = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("C02 execution-context consumer returned invalid JSON") from exc
    if not isinstance(receipt, dict) or receipt.get("owner") != "C02/run-dev-graph-node" or receipt.get("status") != "applied":
        raise ContractError("C02 execution-context consumer did not return an applied receipt")
    if receipt.get("graph_node_id") != lease["graph_node_id"] or receipt.get("worktree_id") != lease["worktree_id"]:
        raise ContractError("C02 execution-context receipt identity mismatch")
    return receipt


def _persist(ledger_path: Path, events_path: Path, ledger: dict[str, Any], events: dict[str, Any]) -> None:
    atomic_json(ledger_path, ledger)
    atomic_json(events_path, events)


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--repo-root", default="."); p.add_argument("--op", required=True, choices=("context", "claim", "heartbeat", "park", "release", "system-release", "list", "reclaim"))
    p.add_argument("--graph-node-id"); p.add_argument("--session-id"); p.add_argument("--branch"); p.add_argument("--completion-event-key"); p.add_argument("--ttl", type=int, default=1800); p.add_argument("--resource", action="append", default=[])
    p.add_argument("--tracker-binding", choices=("beads", "github", "none"), default="github"); p.add_argument("--bd-issue-id"); p.add_argument("--bd-bridge"); p.add_argument("--workspace-id"); p.add_argument("--expected-bd-status", default="open"); p.add_argument("--expected-depends-on", action="append", default=[])
    p.add_argument("--graph"); p.add_argument("--execution-context-consumer"); p.add_argument("--context-resolver")
    a = p.parse_args(); root = Path(a.repo_root).resolve(strict=True)
    ctx = context(root, Path(a.context_resolver).resolve() if a.context_resolver else None)
    if a.ttl < 300: raise ContractError("ttl must be >=300")
    if a.op == "context": dump(ctx); return 0
    coord = Path(ctx["git_common_dir"]) / "dev-graph"; coord.mkdir(parents=True, exist_ok=True)
    ledger_path, events_path, lock_path = coord / "leases.json", coord / "events.json", coord / "leases.lock"
    bridge = Path(a.bd_bridge).resolve() if a.bd_bridge else Path(__file__).with_name("bd-bridge.py")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = load_json(ledger_path) if ledger_path.exists() else {"schema_version": "1.1", "workspace_identity": None, "leases": []}
        events = load_json(events_path) if events_path.exists() else {"schema_version": "1.0", "events": []}
        leases: list[dict[str, Any]] = ledger["leases"]
        now = datetime.now(timezone.utc)
        for lease in leases:
            expiry = lease.get("expires_at")
            if lease.get("state") in {"claimed", "in_progress"} and expiry:
                try:
                    if datetime.fromisoformat(expiry.replace("Z", "+00:00")) < now: lease["state"] = "expired"
                except ValueError: raise ContractError("invalid lease expiry")
        current = next((x for x in leases if x.get("graph_node_id") == a.graph_node_id and x.get("state") in ACTIVE), None)
        if a.op == "list": dump({**ctx, "workspace_identity": ledger.get("workspace_identity"), "leases": leases, "events": events["events"]}); return 0
        if not a.graph_node_id: raise ContractError("operation requires --graph-node-id")
        if a.op == "claim":
            if not a.session_id: raise ContractError("claim requires --session-id")
            if a.tracker_binding == "beads" and not a.bd_issue_id: raise ContractError("beads claim requires --bd-issue-id")
            if current and (current.get("session_id") != a.session_id or current.get("worktree_id") != ctx["worktree_id"]):
                raise ContractError("graph node already has an active lease")
            if not current:
                occupied = {r for x in leases if x.get("state") in ACTIVE for r in x.get("resource_scope", [])}
                if occupied & set(a.resource): raise ContractError("resource_scope conflicts with active lease")
            ctx = _ensure_claim_branch(root, a.graph_node_id, a.branch, ctx)
            if current and current.get("state") not in {"reserving", "claim_pending_local_repair"}:
                result = current
            else:
                if not current:
                    expiry = (now + timedelta(seconds=a.ttl)).isoformat().replace("+00:00", "Z")
                    current = {"graph_node_id": a.graph_node_id, "repository_id": ctx["repository_id"], "worktree_id": ctx["worktree_id"], "branch": ctx["branch"], "head_sha": ctx["head_sha"], "session_id": a.session_id, "state": "reserving", "tracker_binding": a.tracker_binding, "bd_issue_id": a.bd_issue_id, "resource_scope": sorted(set(a.resource)), "created_at": utc_now(), "updated_at": utc_now(), "expires_at": expiry}
                    leases.append(current); events["events"].append({"type": "lease.reserved", "at": utc_now(), "graph_node_id": a.graph_node_id, "worktree_id": ctx["worktree_id"]})
                    _persist(ledger_path, events_path, ledger, events)
                if a.tracker_binding == "beads":
                    expected_workspace = a.workspace_id or ledger.get("workspace_identity")
                    bridge_args = ["--op", "claim", "--bd-issue-id", a.bd_issue_id]
                    if expected_workspace: bridge_args += ["--expected-workspace-id", expected_workspace]
                    if current.get("state") != "claim_pending_local_repair":
                        bridge_args += ["--verify-parity", "--expected-status", a.expected_bd_status]
                        for dependency in a.expected_depends_on: bridge_args += ["--expected-depends-on", dependency]
                    try:
                        bd_receipt = invoke_bd_bridge(root, bridge, bridge_args)
                    except ContractError:
                        current["state"] = "released"; current["released_at"] = utc_now(); current["compensation"] = "reservation_released_after_bd_claim_failure"
                        events["events"].append({"type": "lease.claim_compensated", "at": utc_now(), "graph_node_id": a.graph_node_id})
                        _persist(ledger_path, events_path, ledger, events)
                        raise
                    actual_workspace = (bd_receipt.get("workspace_identity") or {}).get("workspace_id")
                    if not actual_workspace or ledger.get("workspace_identity") not in (None, actual_workspace):
                        current["state"] = "claim_pending_local_repair"; current["repair_reason"] = "bd_claim_succeeded_workspace_receipt_invalid"
                        _persist(ledger_path, events_path, ledger, events)
                        raise ContractError("C28 claim workspace identity is missing or changed")
                    ledger["workspace_identity"] = actual_workspace
                    current["bd_claim_receipt"] = {"workspace_id": actual_workspace, "op": bd_receipt.get("op"), "result": bd_receipt.get("result")}
                current["state"] = "claimed"; current["updated_at"] = utc_now()
                try:
                    _persist(ledger_path, events_path, ledger, events)
                except Exception:
                    if a.tracker_binding == "beads":
                        current["state"] = "claim_pending_local_repair"; current["repair_reason"] = "bd_claim_succeeded_local_finalize_failed"
                        try: _persist(ledger_path, events_path, ledger, events)
                        except Exception: pass
                    raise
                result = current
            graph_path = _resolve_graph(root, a.graph)
            consumer = Path(a.execution_context_consumer).resolve() if a.execution_context_consumer else Path(__file__).with_name("register-package.py")
            try:
                writer_receipt = invoke_execution_context_consumer(root, consumer, graph_path, result, ctx)
                result["execution_context_projection"] = "applied"
                result["execution_context_receipt"] = writer_receipt
            except ContractError:
                result["state"] = "claim_pending_local_repair"
                result["repair_reason"] = "c02_execution_context_projection_failed"
                result["updated_at"] = utc_now()
                _persist(ledger_path, events_path, ledger, events)
                raise
        elif not current: raise ContractError("no active lease for graph node")
        elif a.op in {"heartbeat", "park", "release"}:
            if current.get("session_id") != a.session_id: raise ContractError("lease owner session mismatch")
            if a.op == "heartbeat":
                current["state"] = "in_progress"; current["expires_at"] = (now + timedelta(seconds=a.ttl)).isoformat().replace("+00:00", "Z")
            elif a.op == "park": current["state"] = "pending_review"; current["expires_at"] = None
            else:
                if current.get("state") in {"pending_review", "pending_merge"}:
                    raise ContractError("pending lease requires C26 system-release")
                current["state"] = "released"; current["released_at"] = utc_now()
            current["updated_at"] = utc_now(); result = current; writer_receipt = None
        elif a.op == "system-release":
            if not a.completion_event_key: raise ContractError("system-release requires --completion-event-key")
            if current.get("state") not in {"pending_review", "pending_merge"}: raise ContractError("system-release requires pending lease")
            event = next((x for x in events["events"] if x.get("event_key") == a.completion_event_key and x.get("graph_node_id") == a.graph_node_id and not x.get("consumed_at")), None)
            if not event or event.get("type") != "completion" or event.get("repository_id") != ctx["repository_id"] or not event.get("merge_commit_sha") or not event.get("policy_digest"):
                raise ContractError("matching unconsumed C26 completion event required")
            event["consumed_at"] = utc_now(); current["state"] = "released"; current["released_at"] = utc_now(); current["completion_event_key"] = a.completion_event_key; result = current; writer_receipt = None
        else:
            if current.get("state") not in {"claimed", "in_progress", "expired"}: raise ContractError("pending review/merge cannot be reclaimed")
            current["state"] = "released"; current["released_at"] = utc_now(); current["reclaim_reason"] = "explicit"; result = current; writer_receipt = None
        if a.op != "claim" or result is current: _persist(ledger_path, events_path, ledger, events)
    dump({**ctx, "workspace_identity": ledger.get("workspace_identity"), "lease": result, "writer_receipt": writer_receipt, "conflicts": []}); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ContractError as exc: print(str(exc), file=sys.stderr); raise SystemExit(1)
