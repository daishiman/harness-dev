#!/usr/bin/env python3
# /// script
# name: validate-schedule-receipt
# purpose: Independently recompute and fail-closed verify a schedule receipt for C17.
# inputs: ["argv: --graph FILE --schedule FILE --scope ID? --ready-source self|bd-bridge|both --leases FILE? --ready-json FILE? --max-parallel N"]
# outputs: ["stdout/--out: JSON C17 verdict"]
# requires-python = ">=3.10"
# dependencies: [schedule-graph.py]
# contexts: [C, E]
# network: false
# write-scope: optional verdict path only
# ///
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from _common import ContractError, atomic_json, dump, load_json, utc_now


def _load_scheduler() -> ModuleType:
    path = Path(__file__).with_name("schedule-graph.py")
    spec = importlib.util.spec_from_file_location("_dev_graph_schedule", path)
    if spec is None or spec.loader is None:
        raise ContractError(f"cannot load scheduler: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _unsafe_pairs(
    schedule: dict[str, Any], graph: Any, max_parallel: int
) -> list[dict[str, Any]]:
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else graph
    by_id = {
        (node.get("graph_node_id") or node.get("id")): node
        for node in nodes
        if isinstance(node, dict)
    }
    findings: list[dict[str, Any]] = []
    for kind in ("features", "tasks"):
        for index, batch in enumerate(schedule.get("batches", {}).get(kind, [])):
            if len(batch) > max_parallel:
                findings.append(
                    {"kind": "max_parallel", "batch": f"{kind}[{index}]", "size": len(batch)}
                )
            for left_index, left in enumerate(batch):
                for right in batch[left_index + 1 :]:
                    overlap = sorted(
                        set(by_id.get(left, {}).get("resource_scope", []))
                        & set(by_id.get(right, {}).get("resource_scope", []))
                    )
                    if overlap:
                        findings.append(
                            {
                                "kind": "resource_overlap",
                                "batch": f"{kind}[{index}]",
                                "nodes": [left, right],
                                "resources": overlap,
                            }
                        )
    return findings


def _c28_authority_findings(
    schedule: dict[str, Any], ready: Any, graph: Any, ready_source: str
) -> list[dict[str, Any]]:
    """Independently reject scheduled IDs lacking confirmed C28 authority."""
    if ready_source not in {"bd-bridge", "both"}:
        return []
    if not isinstance(ready, dict):
        return [{"kind": "invalid_c28_ready_evidence"}]
    ready_items = ready.get("ready_set")
    conflicts = ready.get("conflicts", [])
    if not isinstance(ready_items, list) or not isinstance(conflicts, list):
        return [{"kind": "invalid_c28_ready_evidence"}]

    confirmed: set[str] = set()
    invalid: set[str] = set()
    for item in ready_items:
        if not isinstance(item, dict):
            continue
        node_id = item.get("external_ref")
        if not isinstance(node_id, str) or not node_id:
            continue
        if _exact_parity_confirmed(item):
            confirmed.add(node_id)
        else:
            invalid.add(node_id)
    for item in conflicts:
        if isinstance(item, dict):
            node_id = item.get("graph_node_id") or item.get("external_ref")
            if isinstance(node_id, str) and node_id:
                invalid.add(node_id)

    scheduled = {
        node_id
        for kind in ("features", "tasks")
        for node_id in schedule.get("ready_set", {}).get(kind, [])
        if isinstance(node_id, str)
    }
    findings: list[dict[str, Any]] = []
    unsafe = sorted(scheduled & invalid)
    if unsafe:
        findings.append(
            {"kind": "unconfirmed_parity_scheduled", "graph_node_ids": unsafe}
        )

    nodes = graph.get("nodes", []) if isinstance(graph, dict) else graph
    by_id = {
        (node.get("graph_node_id") or node.get("id")): node
        for node in nodes
        if isinstance(node, dict) and (node.get("graph_node_id") or node.get("id"))
    }
    beads_scheduled = {
        node_id
        for node_id in scheduled
        if ready_source == "bd-bridge"
        or by_id.get(node_id, {}).get("tracker_binding") == "beads"
    }
    missing_authority = sorted(beads_scheduled - confirmed)
    if missing_authority:
        findings.append(
            {"kind": "missing_confirmed_c28_authority", "graph_node_ids": missing_authority}
        )
    if ready_source == "both":
        wrong_binding = sorted(
            node_id
            for node_id in scheduled
            if by_id.get(node_id, {}).get("tracker_binding")
            not in {"beads", "github", "none"}
        )
        if wrong_binding:
            findings.append(
                {"kind": "invalid_both_authority", "graph_node_ids": wrong_binding}
            )
    return findings


def _exact_parity_confirmed(item: dict[str, Any]) -> bool:
    parity = item.get("edge_parity")
    if not isinstance(parity, dict) or parity.get("confirmed") is not True:
        return False
    expected = parity.get("expected_depends_on")
    actual = parity.get("actual_depends_on")
    return (
        parity.get("expected_status") == parity.get("actual_status")
        and isinstance(expected, list)
        and isinstance(actual, list)
        and all(isinstance(value, str) for value in expected + actual)
        and sorted(expected) == sorted(actual)
        and parity.get("missing_edges") == []
        and parity.get("unexpected_edges") == []
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--scope")
    parser.add_argument("--ready-source", choices=("self", "bd-bridge", "both"), default="self")
    parser.add_argument("--ready-json")
    parser.add_argument("--leases")
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--out")
    args = parser.parse_args()

    graph_path = Path(args.graph).resolve()
    schedule_path = Path(args.schedule).resolve()
    ready_path = Path(args.ready_json).resolve() if args.ready_json else None
    lease_path = Path(args.leases).resolve() if args.leases else None
    out_path = Path(args.out).resolve() if args.out else None
    if out_path is not None and out_path in {
        graph_path,
        schedule_path,
        ready_path,
        lease_path,
    }:
        raise ContractError(
            "C17 verdict must not overwrite graph/schedule/ready/lease inputs"
        )
    if lease_path is not None and not lease_path.is_file():
        raise ContractError(f"lease snapshot does not exist: {lease_path}")
    graph = load_json(graph_path)
    actual = load_json(schedule_path)
    ready = load_json(ready_path) if ready_path else None
    leases = load_json(lease_path) if lease_path else None
    scheduler = _load_scheduler()
    expected = scheduler.compute_schedule(
        graph,
        ready_source=args.ready_source,
        ready_data=ready,
        lease_data=leases,
        max_parallel=args.max_parallel,
        scope=args.scope,
    )

    findings: list[dict[str, Any]] = []
    for key in (
        "ready_set",
        "batches",
        "conflicts",
        "conflict_pairs",
        "assignment_hints",
        "unmapped",
        "out_of_scope",
        "source_conflicts",
        "binding_ready_set",
        "ready_source",
        "scope",
        "scope_node_ids",
        "max_parallel",
    ):
        if actual.get(key) != expected.get(key):
            findings.append({"kind": "schedule_mismatch", "field": key})
    expected_digests = {
        "graph": _sha(graph_path),
        "ready": _sha(ready_path),
        "leases": _sha(lease_path),
    }
    recorded = actual.get("input_digests")
    if not isinstance(recorded, dict):
        findings.append({"kind": "missing_input_digests"})
    else:
        for key, value in expected_digests.items():
            if recorded.get(key) != value:
                findings.append(
                    {"kind": "stale_input_digest", "input": key, "expected": value, "actual": recorded.get(key)}
                )
        actual_schedule_digest = recorded.get("schedule")
        if not isinstance(actual_schedule_digest, str) or not actual_schedule_digest.startswith("sha256:"):
            findings.append({"kind": "missing_schedule_digest"})
        else:
            expected_schedule_digest = scheduler.schedule_digest(actual)
            if actual_schedule_digest != expected_schedule_digest:
                findings.append(
                    {
                        "kind": "schedule_digest_mismatch",
                        "expected": expected_schedule_digest,
                        "actual": actual_schedule_digest,
                    }
                )
    findings.extend(_unsafe_pairs(actual, graph, args.max_parallel))
    findings.extend(_c28_authority_findings(actual, ready, graph, args.ready_source))
    verdict = {
        "schema_version": "1.0.0",
        "verifier": "dev-graph-parallel-safety-verifier",
        "component": "C17",
        "verified_at": utc_now(),
        "schedule_ref": os.path.relpath(
            schedule_path,
            start=out_path.parent if out_path is not None else Path.cwd(),
        ),
        "schedule_digest": (recorded or {}).get("schedule") if isinstance(recorded, dict) else None,
        "input_digests": expected_digests,
        "unsafe_pairs": [item for item in findings if item["kind"] == "resource_overlap"],
        "findings": findings,
        "verdict": "PASS" if not findings else "FAIL",
    }
    if out_path:
        atomic_json(out_path, verdict)
    dump(verdict)
    return 0 if not findings else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
