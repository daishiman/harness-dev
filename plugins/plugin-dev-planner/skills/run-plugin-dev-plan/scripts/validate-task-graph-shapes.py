#!/usr/bin/env python3
# /// script
# name: validate-task-graph-shapes
# purpose: validate-task-graph.py の shape 固有検査 ((j) coupling・(k) target shape・(l) migration gate) を分離した単一正本 (import 専用モジュール)。
# inputs: []
# outputs: []
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Task graph の shape 移行・coupling・target shape 検査。

`validate-task-graph.py` の CLI と基礎整合性検査から、
shape 固有の検査だけを分離する。公開 CLI は引き続き
`validate-task-graph.py` が所有する。
"""
from __future__ import annotations

from pathlib import Path


def _target_shape_declared(nodes: list[dict]) -> bool:
    """execution_kind を持つ node が 1 つでもあれば target shape 採用宣言とみなす。"""
    return any(
        isinstance(node.get("execution_kind"), str) and node.get("execution_kind")
        for node in nodes
    )


def check_migration_gate(nodes: list[dict], marker: str) -> list[str]:
    """(l) bootstrap→target shape の部分移行を fail-closed で拒否する。

    fixed-13-phase の既存 graph は execution_kind が全件不在なら後方互換で
    受け入れる。一方、1 件でも target shape を採用した場合は、dispatchable
    node 全件の execution_kind と component-build の明示 route_ref を要求する。
    """
    if not (_target_shape_declared(nodes) or marker == "task-graph-derived"):
        return []
    out: list[str] = []
    for node in nodes:
        entity = node.get("entity_ref")
        kind = node.get("execution_kind")
        if isinstance(entity, str) and entity and not (
            isinstance(kind, str) and kind
        ):
            out.append(
                f"(l) migration gate: dispatchable node {node.get('id')} "
                f"(entity_ref={entity!r}) lacks execution_kind — partial "
                "bootstrap→target adoption is fail-closed "
                "(GAP-BOOTSTRAP-TARGET-SHAPE-001)"
            )
    for node in nodes:
        if node.get("execution_kind") == "component-build":
            route = node.get("route_ref")
            if not (isinstance(route, str) and route.strip()):
                out.append(
                    f"(l) migration gate: component-build node {node.get('id')} "
                    "requires explicit non-empty route_ref "
                    "(implicit entity_ref->route inference is forbidden)"
                )
    return out


def check_couples(
    nodes: list[dict],
    edges: list[dict],
    inventory: dict,
    derive_task_graph: object,
) -> list[str]:
    """(j) couples_with が depends_on で直列化されているか検査する。"""
    if not isinstance(inventory, dict):
        return []
    comp_ids = {
        component.get("id")
        for component in inventory.get("components", [])
        if isinstance(component, dict)
    }
    couples: set[frozenset[str]] = set()
    comp_depends: dict[str, list[str]] = {}
    out: list[str] = []
    for component in inventory.get("components", []) or []:
        if not isinstance(component, dict):
            continue
        component_id = component.get("id")
        coupled = component.get("couples_with", [])
        if isinstance(component_id, str) and isinstance(coupled, list):
            for other in coupled:
                if (
                    not isinstance(other, str)
                    or not other
                    or other == component_id
                ):
                    continue
                if other not in comp_ids:
                    out.append(
                        "(j) couples_with references unknown component: "
                        f"{component_id} -> {other}"
                    )
                    continue
                couples.add(frozenset((component_id, other)))
        dependencies = component.get("depends_on", [])
        if isinstance(component_id, str) and isinstance(dependencies, list):
            comp_depends[component_id] = [
                dependency
                for dependency in dependencies
                if isinstance(dependency, str) and dependency != component_id
            ]

    reach = derive_task_graph._transitive_closure(comp_depends)
    nodes_by_entity: dict[str, set] = {}
    entity_phases: dict[str, set] = {}
    for node in nodes:
        entity = node.get("entity_ref")
        if isinstance(entity, str):
            nodes_by_entity.setdefault(entity, set()).add(node.get("id"))
            entity_phases.setdefault(entity, set()).add(node.get("phase_ref"))
    dependency_pairs = {
        (edge.get("from"), edge.get("to"))
        for edge in edges
        if edge.get("type") == "depends_on"
    }

    for pair in sorted(couples, key=lambda value: sorted(value)):
        first, second = sorted(pair)
        if second in reach.get(first, set()) or first in reach.get(second, set()):
            continue
        first_nodes = nodes_by_entity.get(first, set())
        second_nodes = nodes_by_entity.get(second, set())
        if not first_nodes or not second_nodes:
            continue
        if not (
            entity_phases.get(first, set()) & entity_phases.get(second, set())
        ):
            continue
        serialized = any(
            (source in first_nodes and target in second_nodes)
            or (source in second_nodes and target in first_nodes)
            for source, target in dependency_pairs
        )
        if not serialized:
            out.append(
                f"(j) couples_with {first}<->{second} not realized by any "
                "serialization depends_on edge "
                "(densely-coupled siblings would be blindly parallelized)"
            )
    return out


def check_target_shape(
    graph: dict,
    plan_dir: Path | None,
    derive_task_graph: object,
) -> list[str]:
    """(k) renderer 前提と phase-gate/leaf shape を fail-closed 検査する。"""
    nodes = [
        node for node in (graph.get("nodes") or []) if isinstance(node, dict)
    ]
    edges = [
        edge for edge in (graph.get("edges") or []) if isinstance(edge, dict)
    ]
    out: list[str] = []
    node_ids = {node.get("id") for node in nodes}
    parent_pairs = {
        (edge.get("from"), edge.get("to"))
        for edge in edges
        if edge.get("type") == "parent_of"
    }
    producing_nodes = {
        edge.get("from")
        for edge in edges
        if edge.get("type") == "produces"
    }
    roots_by_phase: dict[str, list[dict]] = {}
    leaves: list[dict] = []
    for node in nodes:
        node_id = node.get("id")
        execution_kind = node.get("execution_kind")
        if execution_kind == "phase-gate":
            roots_by_phase.setdefault(node.get("phase_ref"), []).append(node)
            if node_id != node.get("phase_ref"):
                out.append(f"(k) phase-gate id must equal phase_ref: {node_id}")
            if (
                node.get("route_ref") is not None
                or node.get("task_spec_ref") is not None
            ):
                out.append(
                    f"(k) phase-gate must have null route_ref/task_spec_ref: {node_id}"
                )
            continue
        leaves.append(node)
        if execution_kind not in ("direct-task", "component-build"):
            out.append(
                f"(k) executable leaf {node_id} has invalid/missing "
                f"execution_kind: {execution_kind!r}"
            )
        task_spec_ref = node.get("task_spec_ref")
        if not (
            isinstance(task_spec_ref, str)
            and task_spec_ref.startswith("task-specs/")
            and task_spec_ref.endswith(".md")
        ):
            out.append(
                f"(k) executable leaf {node_id} requires task_spec_ref=task-specs/*.md"
            )
        if execution_kind == "component-build" and not (
            isinstance(node.get("route_ref"), str)
            and node.get("route_ref").strip()
        ):
            out.append(
                f"(k) component-build leaf {node_id} requires explicit route_ref"
            )
        if execution_kind == "direct-task" and node.get("route_ref") is not None:
            out.append(f"(k) direct-task leaf {node_id} must have null route_ref")
        if not (
            isinstance(node.get("acceptance_criterion"), str)
            and node.get("acceptance_criterion").strip()
        ):
            out.append(
                f"(k) executable leaf {node_id} requires non-empty acceptance_criterion"
            )
        if not (
            isinstance(node.get("write_scope"), str)
            and node.get("write_scope").strip()
        ):
            out.append(f"(k) executable leaf {node_id} requires non-empty write_scope")
        if node_id not in producing_nodes:
            out.append(
                f"(k) executable leaf {node_id} requires at least one produces artifact"
            )
        phase_ref = node.get("phase_ref")
        if (phase_ref, node_id) not in parent_pairs:
            out.append(
                f"(k) executable leaf {node_id} is not parented by phase root {phase_ref}"
            )

        if plan_dir is not None and isinstance(task_spec_ref, str):
            spec_path = plan_dir / task_spec_ref
            if not spec_path.is_file():
                out.append(
                    f"(k) task_spec_ref does not exist for {node_id}: {task_spec_ref}"
                )
            else:
                try:
                    frontmatter = derive_task_graph.specfm.parse_frontmatter(
                        spec_path.read_text(encoding="utf-8")
                    )
                except OSError as exc:
                    out.append(f"(k) task spec unreadable for {node_id}: {exc}")
                else:
                    if frontmatter.get("id") != node_id:
                        out.append(
                            f"(k) task spec id mismatch for {node_id}: "
                            f"{frontmatter.get('id')!r}"
                        )
                    for field in ("objective", "verify"):
                        if not (
                            isinstance(frontmatter.get(field), str)
                            and frontmatter.get(field).strip()
                        ):
                            out.append(
                                f"(k) task spec {task_spec_ref} requires non-empty {field}"
                            )

    leaf_phases = {node.get("phase_ref") for node in leaves}
    for phase_ref in sorted(leaf_phases, key=str):
        roots = roots_by_phase.get(phase_ref, [])
        if len(roots) != 1:
            out.append(
                f"(k) phase {phase_ref} requires exactly one phase-gate root "
                f"(found {len(roots)})"
            )
    for phase_ref, roots in roots_by_phase.items():
        if phase_ref not in leaf_phases:
            out.append(f"(k) phase-gate has no executable leaves: {phase_ref}")
        for root in roots:
            if root.get("id") not in node_ids:
                out.append(
                    f"(k) phase-gate missing from node set: {root.get('id')}"
                )
    return out
