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
import posixpath
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない (子の起動にも -B を渡す)。
sys.dont_write_bytecode = True

from _common import ContractError, dump, load_json

ScopePath = tuple[str, ...]


def scope_paths(values: Any, owner: str) -> set[ScopePath]:
    """Normalize a ``resource_scope: string[]`` into repository-relative path components.

    ``./packages/api``, ``packages/api/`` and ``packages/api`` are the same path
    (``posixpath.normpath``); ``.`` is the repository root (``()``). Absolute paths
    and paths that start with ``..`` after normalization point outside the
    repository, so they fail closed instead of escaping the conflict check.
    """
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise ContractError(f"{owner}: resource_scope must be a non-empty string[]")
    result: set[ScopePath] = set()
    for value in values:
        if value.startswith("/"):
            raise ContractError(f"{owner}: resource_scope must be repository-relative: {value}")
        path = posixpath.normpath(value)
        if path == ".." or path.startswith("../"):
            raise ContractError(f"{owner}: resource_scope escapes the repository: {value}")
        result.add(() if path == "." else tuple(path.split("/")))
    return result


def overlaps(left: set[ScopePath], right: set[ScopePath]) -> bool:
    """Two scopes conflict when a path equals, or is a component-wise ancestor of, a path in the other.

    ``packages/api`` covers ``packages/api/users.py`` but not ``packages/apix``
    (components are compared, not string prefixes).
    """
    return any(a[:len(b)] == b or b[:len(a)] == a for a in left for b in right)


def touches(node: dict[str, Any]) -> set[ScopePath]:
    """Return the canonical graph-node `resource_scope: string[]` value as normalized paths.

    Older prototypes used ``{"touches": [...]}``, but that shape contradicts
    graph-node.schema.json and silently erased every scope during scheduling.
    Reject the stale shape instead of producing an unsafe parallel batch.
    """
    node_id = node.get("graph_node_id") or node.get("id") or "<unknown>"
    return scope_paths(node.get("resource_scope", []), str(node_id))


def lease_touches(lease: dict[str, Any], by_id: dict[Any, dict[str, Any]]) -> set[ScopePath]:
    """Return what an active lease holds: its recorded scope plus its graph node's ``resource_scope``.

    The public claim path (``/dev-graph worktree claim <id> --branch ... --session-id ...``) does not
    pass ``--resource``, so C27 records ``resource_scope: []``. Reading only the lease record let a
    candidate that touches the leased node's files into the ready set. A lease whose scope can be
    derived from neither the record nor the graph fails closed instead of conflicting with nothing.
    """
    node_id = lease.get("graph_node_id")
    held = scope_paths(lease.get("resource_scope", []), f"lease {node_id}")
    if node_id in by_id:
        held |= touches(by_id[node_id])
    if not held:
        raise ContractError(f"lease {node_id}: resource_scope is empty and the node is not in the graph")
    return held


def is_schedulable(node: dict[str, Any]) -> bool:
    readiness = node.get("implementation_readiness") or {}
    return (
        node.get("status") == "active"
        and node.get("confirmation_status") == "confirmed"
        and node.get("evaluation_status") == "pass"
        and isinstance(readiness, dict)
        and readiness.get("status") == "complete"
    )


def dependencies_done(node_id: Any, by_id: dict[Any, dict[str, Any]], done: set[Any]) -> bool:
    """Return whether every node reachable through ``depends_on`` is done or closed, not only the direct ones.

    SKILL.md requires every dependency to be done (完了条件・Gotchas). A done node can still depend on an
    open one: C02 accepts ``status`` and ``depends_on`` patches and C11 does not reject the pair, so
    checking only direct dependencies let that node's dependents into the ready set.
    """
    seen: set[Any] = set()
    pending = list(by_id[node_id].get("depends_on", []))
    while pending:
        dep = pending.pop()
        if dep in seen:
            continue
        if dep not in done:
            return False
        seen.add(dep)
        pending.extend(by_id[dep].get("depends_on", []))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--graph", required=True)
    parser.add_argument("--ready-source", choices=("self", "bd-bridge"), default="self")
    parser.add_argument("--ready-json"); parser.add_argument("--leases")
    args = parser.parse_args(); data = load_json(Path(args.graph)); nodes = data.get("nodes", []) if isinstance(data, dict) else data
    if not isinstance(nodes, list): raise ContractError("graph nodes must be an array")
    ids = Counter(n.get("graph_node_id") or n.get("id") for n in nodes if isinstance(n, dict))
    if duplicated := sorted(str(x) for x, count in ids.items() if count > 1):
        # by_id would keep only the last node per id, so a blocked twin could hide behind a ready one.
        raise ContractError(f"duplicate graph node ids: {duplicated}")
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
                if is_schedulable(by_id[external]) and dependencies_done(external, by_id, done):
                    ready_ids.add(external)
            else: unmapped.append(item if isinstance(item, dict) else {"value": item})
    else:
        ready_ids = {node_id for node_id, node in by_id.items() if is_schedulable(node)
                     and dependencies_done(node_id, by_id, done)}
    active_leases: list[dict[str, Any]] = []
    if args.leases and Path(args.leases).exists():
        lease_data = load_json(Path(args.leases)); active_leases = lease_data.get("leases", lease_data if isinstance(lease_data, list) else [])
    leased_ids = {x.get("graph_node_id") for x in active_leases if x.get("state") not in {"released", "expired"}}
    leased_touches = set().union(*(lease_touches(x, by_id)
                                   for x in active_leases if x.get("state") not in {"released", "expired"}))
    candidates = [by_id[x] for x in sorted(ready_ids) if x in by_id and is_schedulable(by_id[x])
                  and x not in leased_ids and not overlaps(touches(by_id[x]), leased_touches)]
    features = [n for n in candidates if n.get("artifact_kind", n.get("kind")) == "feature"]
    tasks = [n for n in candidates if n not in features]
    def batches(items: list[dict[str, Any]]) -> list[list[str]]:
        result: list[list[str]] = []
        for node in items:
            node_id = node.get("graph_node_id") or node.get("id"); scope = touches(node)
            placed = False
            for batch in result:
                occupied = set().union(*(touches(by_id[x]) for x in batch))
                if not overlaps(scope, occupied): batch.append(node_id); placed = True; break
            if not placed: result.append([node_id])
        return result
    feature_batches, task_batches = batches(features), batches(tasks)
    conflicts = sorted((ready_ids & leased_ids) | {x for x in ready_ids if x in by_id and overlaps(touches(by_id[x]), leased_touches)})
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
