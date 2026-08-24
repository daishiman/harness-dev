#!/usr/bin/env python3
# /// script
# name: schedule-graph
# purpose: Compute deterministic feature/task ready sets and non-conflicting worktree batches.
# inputs: ["argv: --graph FILE --ready-source self|bd-bridge --ready-json FILE? --leases FILE?"]
# outputs: ["stdout: JSON schedule"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, dump, load_json


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


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--graph", required=True)
    parser.add_argument("--ready-source", choices=("self", "bd-bridge"), default="self")
    parser.add_argument("--ready-json"); parser.add_argument("--leases")
    args = parser.parse_args(); data = load_json(Path(args.graph)); nodes = data.get("nodes", []) if isinstance(data, dict) else data
    if not isinstance(nodes, list): raise ContractError("graph nodes must be an array")
    by_id = {(n.get("graph_node_id") or n.get("id")): n for n in nodes if isinstance(n, dict)}
    done = {node_id for node_id, node in by_id.items() if node.get("status") in {"done", "closed"}}
    ready_ids: set[str]
    unmapped: list[dict[str, Any]] = []
    if args.ready_source == "bd-bridge":
        if not args.ready_json: raise ContractError("--ready-source bd-bridge requires --ready-json")
        ready_data = load_json(Path(args.ready_json)); raw_ready = ready_data.get("ready_set", ready_data)
        if not isinstance(raw_ready, list): raise ContractError("bd ready payload must contain ready_set[]")
        ready_ids = set()
        for item in raw_ready:
            external = item.get("external_ref") if isinstance(item, dict) else None
            if external and external in by_id:
                if is_schedulable(by_id[external]) and all(
                    dep in done for dep in by_id[external].get("depends_on", [])
                ):
                    ready_ids.add(external)
            else: unmapped.append(item if isinstance(item, dict) else {"value": item})
    else:
        ready_ids = {node_id for node_id, node in by_id.items() if is_schedulable(node)
                     and all(dep in done for dep in node.get("depends_on", []))}
    active_leases: list[dict[str, Any]] = []
    if args.leases and Path(args.leases).exists():
        lease_data = load_json(Path(args.leases)); active_leases = lease_data.get("leases", lease_data if isinstance(lease_data, list) else [])
    leased_ids = {x.get("graph_node_id") for x in active_leases if x.get("state") not in {"released", "expired"}}
    leased_touches = {str(v) for x in active_leases if x.get("state") not in {"released", "expired"} for v in x.get("resource_scope", [])}
    candidates = [by_id[x] for x in sorted(ready_ids) if x in by_id and is_schedulable(by_id[x])
                  and x not in leased_ids and not (touches(by_id[x]) & leased_touches)]
    features = [n for n in candidates if n.get("artifact_kind", n.get("kind")) == "feature"]
    tasks = [n for n in candidates if n not in features]
    def batches(items: list[dict[str, Any]]) -> list[list[str]]:
        result: list[list[str]] = []
        for node in items:
            node_id = node.get("graph_node_id") or node.get("id"); scope = touches(node)
            placed = False
            for batch in result:
                occupied = set().union(*(touches(by_id[x]) for x in batch))
                if not scope & occupied: batch.append(node_id); placed = True; break
            if not placed: result.append([node_id])
        return result
    feature_batches, task_batches = batches(features), batches(tasks)
    conflicts = sorted((ready_ids & leased_ids) | {x for x in ready_ids if x in by_id and touches(by_id[x]) & leased_touches})
    hints = []
    for node in tasks:
        node_id = node.get("graph_node_id") or node.get("id")
        branch = f"devgraph/{node_id}"
        hints.append({"graph_node_id": node_id, "suggested_branch": branch,
                      "claim_command": f"/dev-graph worktree claim {node_id} --branch {branch} --session-id <session>"})
    dump({"ready_set": {"features": [n.get("graph_node_id") or n.get("id") for n in features],
                         "tasks": [n.get("graph_node_id") or n.get("id") for n in tasks]},
          "batches": {"features": feature_batches, "tasks": task_batches}, "conflicts": conflicts,
          "assignment_hints": hints, "unmapped": unmapped, "ready_source": args.ready_source})
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ContractError as exc: print(str(exc), file=sys.stderr); raise SystemExit(2)
