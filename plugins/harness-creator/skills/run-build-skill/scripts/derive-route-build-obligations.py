#!/usr/bin/env python3
"""Compile handoff routes into incremental generative obligations.

The compiler extracts route-local slices from inventory and task-graph files, so
an unrelated component edit does not invalidate every build proof merely because
the routes share one JSON document.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _safe_id(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9:._-]+", "-", raw)


def _load_optional(path: Path) -> object:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory_component(inventory: object, route_id: str) -> object:
    if isinstance(inventory, dict):
        candidates = inventory.get("components") or inventory.get("inventory") or []
    else:
        candidates = inventory if isinstance(inventory, list) else []
    for item in candidates:
        if isinstance(item, dict) and str(item.get("id") or item.get("component_id")) == route_id:
            return item
    return None


def _task_nodes(task_graph: object, route_id: str) -> list[dict]:
    if not isinstance(task_graph, dict):
        return []
    nodes = task_graph.get("nodes") or task_graph.get("tasks") or []
    return [
        item for item in nodes
        if isinstance(item, dict)
        and str(item.get("entity_ref") or item.get("route_id") or "") == route_id
    ]


def _graph_nodes(task_graph: object) -> list[dict]:
    if not isinstance(task_graph, dict):
        return []
    nodes = task_graph.get("nodes") or task_graph.get("tasks") or []
    return [item for item in nodes if isinstance(item, dict)]


def _graph_edges(task_graph: object, edge_type: str) -> list[dict]:
    if not isinstance(task_graph, dict):
        return []
    edges = task_graph.get("edges") or []
    return [item for item in edges if isinstance(item, dict) and item.get("type") == edge_type]


def derive_contract(handoff: dict, repo_root: Path, handoff_path: Path) -> dict:
    routes = handoff.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("handoff.routes must be a non-empty array")
    plan_dir_raw = str(handoff.get("plan_dir") or handoff_path.parent)
    plan_dir = Path(plan_dir_raw)
    if not plan_dir.is_absolute():
        plan_dir = repo_root / plan_dir
    plan_dir = plan_dir.resolve()
    try:
        plan_dir_rel = plan_dir.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"plan_dir is outside repo: {plan_dir}") from exc

    inventory = _load_optional(plan_dir / "component-inventory.json")
    task_graph_ref = handoff.get("task_graph_ref")
    task_graph_path = None
    if isinstance(task_graph_ref, dict) and task_graph_ref.get("path"):
        task_graph_path = plan_dir / str(task_graph_ref["path"])
    elif isinstance(task_graph_ref, str):
        task_graph_path = plan_dir / task_graph_ref
    task_graph = _load_optional(task_graph_path) if task_graph_path else None

    route_ids = {str(route.get("id")) for route in routes if isinstance(route, dict)}
    if "" in route_ids or len(route_ids) != len(routes):
        raise ValueError("route ids must be non-empty and unique")
    slug = str(handoff.get("target_plugin_slug") or "plugin")
    build_dir = Path("eval-log") / slug / "build"
    if handoff.get("cycle_id") is not None:
        build_dir /= str(handoff["cycle_id"])
    obligations = []
    for route in routes:
        route_id = str(route["id"])
        target = str(route.get("build_target") or "")
        if not target:
            raise ValueError(f"route {route_id} has no build_target")
        unknown = set(route.get("depends_on") or []) - route_ids
        if unknown:
            raise ValueError(f"route {route_id} has unknown dependencies: {sorted(unknown)}")
        inputs: list[dict] = []
        task_spec = route.get("task_spec_ref")
        spec = route.get("spec")
        selected_spec = task_spec or spec
        if selected_spec:
            candidate = (plan_dir / str(selected_spec)).resolve()
            try:
                rel = candidate.relative_to(repo_root).as_posix()
            except ValueError as exc:
                raise ValueError(f"route spec is outside repo: {candidate}") from exc
            if candidate.is_file():
                inputs.append({"path": rel, "required": True, "context": True})
        parameters = {
            "route": {
                key: route.get(key)
                for key in (
                    "id", "component_kind", "name", "build_kind", "build_args",
                    "build_target", "placement_scope", "builder", "criteria_ref",
                    "task_spec_ref", "spec",
                )
                if key in route
            },
            "inventory_component": _inventory_component(inventory, route_id),
            "task_nodes": _task_nodes(task_graph, route_id),
            "mode": handoff.get("mode"),
        }
        obligations.append({
            "id": f"build:{_safe_id(route_id)}",
            "claim": f"Route {route_id} is materially built at {target} from its current route-local specification.",
            "kind": "generative",
            "risk": "high",
            "activation": "changed",
            "depends_on": [f"build:{_safe_id(dep)}" for dep in route.get("depends_on") or []],
            "inputs": inputs,
            "parameters": parameters,
            "expected_evidence_paths": [
                target,
                (build_dir / f"route-{route_id}.json").as_posix(),
            ],
            "model_required": True,
            "minimum_confidence": 0.9,
            "reuse": True,
        })

    # entity_ref=null direct tasks are real work too.  Compile them into the
    # same proof DAG so unchanged plan/review/evidence tasks do not launch a
    # fresh Agent.  phase-gate nodes are state projections over dependency
    # proof and intentionally do not become executable obligations.
    nodes = _graph_nodes(task_graph)
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    node_obligation: dict[str, str] = {}
    for node_id, node in node_by_id.items():
        entity_ref = str(node.get("entity_ref") or "")
        if entity_ref in route_ids:
            node_obligation[node_id] = f"build:{_safe_id(entity_ref)}"
        elif node.get("execution_kind") == "direct-task":
            node_obligation[node_id] = f"task:{_safe_id(node_id)}"

    dependency_edges = _graph_edges(task_graph, "depends_on")
    produces_edges = _graph_edges(task_graph, "produces")
    for node_id, obligation_id in sorted(node_obligation.items()):
        node = node_by_id[node_id]
        if str(node.get("entity_ref") or "") in route_ids:
            continue
        dependencies = sorted({
            node_obligation[str(edge.get("to"))]
            for edge in dependency_edges
            if str(edge.get("from")) == node_id and str(edge.get("to")) in node_obligation
        })
        task_spec = node.get("task_spec_ref")
        inputs = []
        if task_spec:
            candidate = (plan_dir / str(task_spec)).resolve()
            try:
                rel = candidate.relative_to(repo_root).as_posix()
            except ValueError as exc:
                raise ValueError(f"task spec is outside repo: {candidate}") from exc
            if candidate.is_file():
                inputs.append({"path": rel, "required": True, "context": True})
        outputs = [
            str(edge.get("to"))
            for edge in produces_edges
            if str(edge.get("from")) == node_id and str(edge.get("to") or "")
        ]
        if not outputs:
            scope = str(node.get("write_scope") or "")
            if scope and not re.fullmatch(r"P\d+", scope):
                outputs = [scope]
        obligations.append({
            "id": obligation_id,
            "claim": str(node.get("acceptance_criterion") or node.get("title") or f"Task {node_id} is complete"),
            "kind": "generative",
            "risk": "high" if node.get("phase_ref") in {"P03", "P09", "P10", "P13"} else "medium",
            "activation": "changed",
            "depends_on": dependencies,
            "inputs": inputs,
            "parameters": {"task_node": node, "plan_dir": plan_dir_rel},
            "expected_evidence_paths": outputs,
            "model_required": True,
            "minimum_confidence": 0.9,
            "reuse": True,
        })
    return {
        "schema_version": 1,
        "subject": f"{slug}:route-build",
        "obligations": obligations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve()
        handoff_path = Path(args.handoff).resolve()
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        contract = derive_contract(handoff, repo_root, handoff_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
