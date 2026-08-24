#!/usr/bin/env python3
# /// script
# name: schedule-graph
# purpose: Compute deterministic feature/task ready sets and non-conflicting worktree batches.
# inputs: ["argv: --graph FILE --scope ID? --ready-source self|bd-bridge|both --ready-json FILE? --leases FILE? --max-parallel N"]
# outputs: ["stdout: JSON schedule", "optional --out/goal anchor artifacts"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: optional schedule and goal-anchor paths only
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import ContractError, atomic_json, dump, load_json, utc_now


GOAL = (
    "グラフの依存関係・完了状態・active worktree leaseから次に着手すべきready-setと、"
    "リソーススコープ/lease重複のない複数worktree向け並列バッチを算出・提示した状態になっている"
)


def sha256_file(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def schedule_digest(value: dict[str, Any]) -> str:
    """Bind the semantic schedule while excluding observational timestamps."""
    unsigned = json.loads(json.dumps(value))
    unsigned.pop("generated_at", None)
    digests = unsigned.get("input_digests")
    if isinstance(digests, dict):
        digests.pop("schedule", None)
    return "sha256:" + hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _validate_write_paths(
    *, read_paths: list[Path | None], write_paths: list[Path | None]
) -> None:
    reads = {path for path in read_paths if path is not None}
    writes = [path for path in write_paths if path is not None]
    if len(writes) != len(set(writes)):
        raise ContractError("schedule output and goal-anchor paths must be distinct")
    overlap = sorted(str(path) for path in set(writes) & reads)
    if overlap:
        raise ContractError(
            f"schedule writes must not overwrite graph/ready/lease inputs: {overlap}"
        )


def _atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def touches(node: dict[str, Any]) -> set[str]:
    """Return the canonical graph-node `resource_scope: string[]` value.

    Older prototypes used ``{"touches": [...]}``, but that shape contradicts
    graph-node.schema.json and silently erased every scope during scheduling.
    Reject the stale shape instead of producing an unsafe parallel batch.
    """
    values = node.get("resource_scope", [])
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value for value in values
    ):
        node_id = node.get("graph_node_id") or node.get("id") or "<unknown>"
        raise ContractError(f"{node_id}: resource_scope must be a non-empty string[]")
    return set(values)


def is_schedulable(node: dict[str, Any]) -> bool:
    readiness = node.get("implementation_readiness") or {}
    return (
        node.get("status") == "active"
        and node.get("confirmation_status") == "confirmed"
        and node.get("evaluation_status") == "pass"
        and isinstance(readiness, dict)
        and readiness.get("status") == "complete"
    )


def _node_id(node: dict[str, Any]) -> str | None:
    value = node.get("graph_node_id") or node.get("id")
    return value if isinstance(value, str) and value else None


def _scope_ids(
    nodes: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], scope: str | None
) -> set[str]:
    """Resolve the same fixed-point feature/dependency closure used by render.

    A task selector expands to its parent feature and siblings; a feature
    selector expands to its child tasks. Every selected node then pulls in its
    dependency targets. Dependencies are part of the scoped graph so a ready
    prerequisite can be recommended, while unrelated nodes remain excluded.
    """
    if scope is None:
        return set(by_id)
    if scope not in by_id:
        raise ContractError(f"scope node does not exist: {scope}")
    selected = {scope}
    while True:
        before = set(selected)
        for node_id in tuple(selected):
            node = by_id.get(node_id)
            if node is None:
                raise ContractError(f"scope closure contains missing node: {node_id}")
            dependencies = node.get("depends_on", [])
            if not isinstance(dependencies, list) or any(
                not isinstance(dep, str) or not dep for dep in dependencies
            ):
                raise ContractError(f"{node_id}: depends_on must be a string[]")
            selected.update(dependencies)
            parent = node.get("parent_feature")
            if isinstance(parent, str) and parent:
                selected.add(parent)
        selected.update(
            node_id
            for node in nodes
            if (node_id := _node_id(node)) is not None
            and node.get("parent_feature") in selected
        )
        missing = selected - set(by_id)
        if missing:
            raise ContractError(
                f"scope closure contains missing node(s): {sorted(missing)}"
            )
        if selected == before:
            return selected


def _confirmed_parity(item: dict[str, Any]) -> bool:
    parity = item.get("edge_parity")
    if not isinstance(parity, dict) or parity.get("confirmed") is not True:
        return False
    expected = parity.get("expected_depends_on")
    actual = parity.get("actual_depends_on")
    missing = parity.get("missing_edges")
    unexpected = parity.get("unexpected_edges")
    return (
        parity.get("expected_status") == parity.get("actual_status")
        and isinstance(expected, list)
        and isinstance(actual, list)
        and all(isinstance(value, str) for value in expected + actual)
        and sorted(expected) == sorted(actual)
        and missing == []
        and unexpected == []
    )


def _bd_ready_ids(
    ready_data: Any,
    *,
    by_id: dict[str, dict[str, Any]],
    scoped_ids: set[str],
    done: set[str],
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize a C28 ready receipt and exclude every unconfirmed candidate."""
    if not isinstance(ready_data, dict):
        raise ContractError("C28 ready evidence must be a JSON object")
    raw_ready = ready_data.get("ready_set")
    raw_conflicts = ready_data.get("conflicts", [])
    if not isinstance(raw_ready, list):
        raise ContractError("C28 ready evidence must contain ready_set[]")
    if not isinstance(raw_conflicts, list) or any(
        not isinstance(item, dict) for item in raw_conflicts
    ):
        raise ContractError("C28 ready evidence conflicts must be an object[]")

    conflicts = [dict(item, source="c28-conflicts") for item in raw_conflicts]
    conflicted_ids = {
        str(item.get("graph_node_id") or item.get("external_ref"))
        for item in raw_conflicts
        if item.get("graph_node_id") or item.get("external_ref")
    }
    ready_ids: set[str] = set()
    unmapped: list[dict[str, Any]] = []
    out_of_scope: list[dict[str, Any]] = []
    for raw in raw_ready:
        if not isinstance(raw, dict):
            unmapped.append({"value": raw, "reason": "ready_item_not_object"})
            continue
        external = raw.get("external_ref")
        if not isinstance(external, str) or not external or external not in by_id:
            unmapped.append(dict(raw, reason="external_ref_unmapped"))
            continue
        if external not in scoped_ids:
            out_of_scope.append(dict(raw, reason="outside_scope"))
            continue
        if not _confirmed_parity(raw):
            conflicts.append(
                {
                    "graph_node_id": external,
                    "reason": "edge_parity_not_confirmed",
                    "edge_parity": raw.get("edge_parity"),
                    "source": "c28-ready-set",
                }
            )
            continue
        if external in conflicted_ids:
            conflicts.append(
                {
                    "graph_node_id": external,
                    "reason": "listed_in_c28_conflicts",
                    "source": "c28-ready-set",
                }
            )
            continue
        node = by_id[external]
        dependencies = node.get("depends_on", [])
        if is_schedulable(node) and all(dep in done for dep in dependencies):
            ready_ids.add(external)

    def sort_key(item: dict[str, Any]) -> str:
        return json.dumps(item, ensure_ascii=False, sort_keys=True)

    return (
        ready_ids,
        sorted(unmapped, key=sort_key),
        sorted(out_of_scope, key=sort_key),
        sorted(conflicts, key=sort_key),
    )


def compute_schedule(
    data: Any,
    *,
    ready_source: str = "self",
    ready_data: Any | None = None,
    lease_data: Any | None = None,
    max_parallel: int = 4,
    scope: str | None = None,
) -> dict[str, Any]:
    if max_parallel < 1:
        raise ContractError("--max-parallel must be >= 1")
    nodes = data.get("nodes", []) if isinstance(data, dict) else data
    if not isinstance(nodes, list):
        raise ContractError("graph nodes must be an array")
    object_nodes = [node for node in nodes if isinstance(node, dict)]
    by_id = {
        node_id: node
        for node in object_nodes
        if (node_id := _node_id(node)) is not None
    }
    scoped_ids = _scope_ids(object_nodes, by_id, scope)
    done = {
        node_id
        for node_id, node in by_id.items()
        if node.get("status") in {"done", "closed"}
    }
    local_ready_ids = {
        node_id
        for node_id in scoped_ids
        if is_schedulable(by_id[node_id])
        and all(dep in done for dep in by_id[node_id].get("depends_on", []))
    }
    unmapped: list[dict[str, Any]] = []
    out_of_scope: list[dict[str, Any]] = []
    source_conflicts: list[dict[str, Any]] = []
    bd_ready_ids: set[str] = set()
    if ready_source in {"bd-bridge", "both"}:
        bd_ready_ids, unmapped, out_of_scope, source_conflicts = _bd_ready_ids(
            ready_data, by_id=by_id, scoped_ids=scoped_ids, done=done
        )

    if ready_source == "self":
        ready_ids = local_ready_ids
    elif ready_source == "bd-bridge":
        ready_ids = bd_ready_ids
    elif ready_source == "both":
        valid_bindings = {"beads", "github", "none"}
        invalid = {
            node_id: by_id[node_id].get("tracker_binding")
            for node_id in scoped_ids
            if by_id[node_id].get("tracker_binding") not in valid_bindings
        }
        if invalid:
            raise ContractError(
                f"both mode requires an explicit durable tracker_binding: {invalid}"
            )
        wrong_authority = sorted(
            node_id
            for node_id in bd_ready_ids
            if by_id[node_id].get("tracker_binding") != "beads"
        )
        source_conflicts.extend(
            {
                "graph_node_id": node_id,
                "reason": "c28_candidate_binding_is_not_beads",
                "tracker_binding": by_id[node_id].get("tracker_binding"),
                "source": "authority-partition",
            }
            for node_id in wrong_authority
        )
        beads_ready = {
            node_id
            for node_id in bd_ready_ids
            if by_id[node_id].get("tracker_binding") == "beads"
        }
        local_ready = {
            node_id
            for node_id in local_ready_ids
            if by_id[node_id].get("tracker_binding") in {"github", "none"}
        }
        ready_ids = beads_ready | local_ready
    else:
        raise ContractError(f"unsupported ready source: {ready_source}")

    active_leases = []
    if isinstance(lease_data, dict):
        active_leases = lease_data.get("leases", [])
    elif isinstance(lease_data, list):
        active_leases = lease_data
    if not isinstance(active_leases, list):
        raise ContractError("lease payload must contain leases[]")
    leased_ids = {
        item.get("graph_node_id")
        for item in active_leases
        if isinstance(item, dict) and item.get("state") not in {"released", "expired"}
    }
    leased_touches = {
        str(value)
        for item in active_leases
        if isinstance(item, dict) and item.get("state") not in {"released", "expired"}
        for value in item.get("resource_scope", [])
    }
    candidates = [
        by_id[node_id]
        for node_id in sorted(ready_ids)
        if is_schedulable(by_id[node_id])
        and node_id not in leased_ids
        and not (touches(by_id[node_id]) & leased_touches)
    ]
    features = [
        node
        for node in candidates
        if node.get("artifact_kind", node.get("kind")) == "feature"
    ]
    tasks = [node for node in candidates if node not in features]

    def batches(items: list[dict[str, Any]]) -> list[list[str]]:
        result: list[list[str]] = []
        for node in items:
            node_id = node.get("graph_node_id") or node.get("id")
            scope = touches(node)
            placed = False
            for batch in result:
                occupied = set().union(*(touches(by_id[item]) for item in batch))
                if len(batch) < max_parallel and not scope & occupied:
                    batch.append(node_id)
                    placed = True
                    break
            if not placed:
                result.append([node_id])
        return result

    feature_batches, task_batches = batches(features), batches(tasks)
    conflict_pairs: list[dict[str, Any]] = []
    for kind, items in (("features", features), ("tasks", tasks)):
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                overlap = sorted(touches(left) & touches(right))
                if overlap:
                    conflict_pairs.append(
                        {
                            "kind": kind,
                            "nodes": [_node_id(left), _node_id(right)],
                            "resources": overlap,
                        }
                    )
    conflicts = sorted(
        (ready_ids & leased_ids)
        | {
            node_id
            for node_id in ready_ids
            if node_id in by_id and touches(by_id[node_id]) & leased_touches
        }
    )
    hints = []
    for node in tasks:
        node_id = node.get("graph_node_id") or node.get("id")
        branch = f"devgraph/{node_id}"
        hints.append(
            {
                "graph_node_id": node_id,
                "suggested_branch": branch,
                "claim_command": (
                    f"/dev-graph worktree claim {node_id} --branch {branch} "
                    "--session-id <session>"
                ),
                "tracker_binding": node.get("tracker_binding"),
            }
        )
    binding_ready_set: dict[str, dict[str, list[str]]] = {}
    if ready_source == "both":
        for binding in ("beads", "github", "none"):
            bound = [
                node
                for node in candidates
                if node.get("tracker_binding") == binding
            ]
            binding_ready_set[binding] = {
                "features": [
                    _node_id(node)
                    for node in bound
                    if node.get("artifact_kind", node.get("kind")) == "feature"
                ],
                "tasks": [
                    _node_id(node)
                    for node in bound
                    if node.get("artifact_kind", node.get("kind")) != "feature"
                ],
            }
    source_conflicts = sorted(
        source_conflicts,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
    )
    return {
        "ready_set": {
            "features": [node.get("graph_node_id") or node.get("id") for node in features],
            "tasks": [node.get("graph_node_id") or node.get("id") for node in tasks],
        },
        "batches": {"features": feature_batches, "tasks": task_batches},
        "conflicts": conflicts,
        "conflict_pairs": conflict_pairs,
        "assignment_hints": hints,
        "unmapped": unmapped,
        "out_of_scope": out_of_scope,
        "source_conflicts": source_conflicts,
        "binding_ready_set": binding_ready_set,
        "ready_source": ready_source,
        "scope": scope,
        "scope_node_ids": sorted(scoped_ids),
        "max_parallel": max_parallel,
    }


def write_goal_anchor(
    *,
    goal_spec: Path,
    progress: Path,
    intermediate: Path,
    schedule_path: Path,
    schedule: dict[str, Any],
) -> None:
    goal_hash = hashlib.sha256(GOAL.encode("utf-8")).hexdigest()
    now = utc_now()
    schedule_ref = os.path.relpath(schedule_path, start=progress.parent)
    atomic_json(goal_spec, {"original_goal": GOAL, "original_goal_hash": goal_hash})
    atomic_json(
        progress,
        {
            "original_goal_hash": goal_hash,
            "updated_at": now,
            "checklist": {
                "eligible_candidates_only": {"status": "PASS", "evidence": schedule_ref},
                "feature_task_separated": {"status": "PASS", "evidence": schedule_ref},
                "resource_conflicts_zero": {"status": "PASS", "evidence": schedule_ref},
                "branch_claim_hints": {"status": "PASS", "evidence": schedule_ref},
                "read_only": {"status": "PASS", "evidence": "schedule-graph.py write-scope"},
            },
        },
    )
    _atomic_jsonl(
        intermediate,
        [
            {
                "iteration": 1,
                "original_goal": GOAL,
                "original_goal_hash": goal_hash,
                "current_goal_snapshot": GOAL,
                "delta_from_original": "none",
                "merged_directive_for_next": "C17 verifier receipt を独立取得する",
                "drift_signal": False,
                "schedule_digest": schedule["input_digests"]["schedule"],
            }
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--scope")
    parser.add_argument("--ready-source", choices=("self", "bd-bridge", "both"), default="self")
    parser.add_argument("--ready-json")
    parser.add_argument("--leases")
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--out")
    parser.add_argument("--goal-spec")
    parser.add_argument("--goal-progress")
    parser.add_argument("--goal-intermediate")
    args = parser.parse_args()
    graph_path = Path(args.graph).resolve()
    ready_path = Path(args.ready_json).resolve() if args.ready_json else None
    lease_path = Path(args.leases).resolve() if args.leases else None
    out_path = Path(args.out).resolve() if args.out else None
    anchor_args = (args.goal_spec, args.goal_progress, args.goal_intermediate)
    if any(anchor_args) and not all(anchor_args):
        raise ContractError(
            "goal anchor requires --goal-spec, --goal-progress, and --goal-intermediate together"
        )
    if all(anchor_args) and out_path is None:
        raise ContractError("goal anchor materialization requires --out")
    anchor_paths = [Path(value).resolve() for value in anchor_args if value]
    _validate_write_paths(
        read_paths=[graph_path, ready_path, lease_path],
        write_paths=[out_path, *anchor_paths],
    )
    if args.ready_source in {"bd-bridge", "both"} and ready_path is None:
        raise ContractError(f"--ready-source {args.ready_source} requires --ready-json")
    if lease_path is not None and not lease_path.is_file():
        raise ContractError(f"lease snapshot does not exist: {lease_path}")
    data = load_json(graph_path)
    ready_data = load_json(ready_path) if ready_path else None
    lease_data = load_json(lease_path) if lease_path else None
    schedule = compute_schedule(
        data,
        ready_source=args.ready_source,
        ready_data=ready_data,
        lease_data=lease_data,
        max_parallel=args.max_parallel,
        scope=args.scope,
    )
    schedule["generated_at"] = utc_now()
    schedule["input_digests"] = {
        "graph": sha256_file(graph_path),
        "ready": sha256_file(ready_path),
        "leases": sha256_file(lease_path),
    }
    schedule["input_digests"]["schedule"] = schedule_digest(schedule)
    if out_path:
        atomic_json(out_path, schedule)
    if all(anchor_args):
        write_goal_anchor(
            goal_spec=anchor_paths[0],
            progress=anchor_paths[1],
            intermediate=anchor_paths[2],
            schedule_path=out_path,
            schedule=schedule,
        )
    dump(schedule)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
