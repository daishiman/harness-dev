#!/usr/bin/env python3
"""Compile handoff routes into incremental generative obligations.

The compiler extracts route-local slices from inventory and task-graph files, so
an unrelated component edit does not invalidate every build proof merely because
the routes share one JSON document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


# 第1稿 (stage=draft) に含める phase。
#
# 分類の基準は「使える実体が立ち上がるまでに要るか」の一点であり、重要度ではない。
# P01 は goal-spec、P02 は各 component の設計ブリーフ (build 入力そのもの)、
# P05 は実装。この 3 つが揃えば利用者は現物を起動できる。
#
# ここに入れていない phase は品質を捨てたのではなく、第1稿の後ろへ移しただけである。
# 特に P04 (受入テストを赤で固定する) は component 数と同じだけの direct-task を持ち、
# 厳格 TDD の下では「全 component 分の赤を書き終えるまで実装を 1 行も書かない」直列区間
# になる。実物が無い状態で払うこの待ち時間が、利用者の言う「使えるまで何もできない時間」
# の主因であり、stage を分ける動機そのものである。release で必ず回収する。
DRAFT_PHASES = frozenset({"P01", "P02", "P05"})
DRAFT_STAGE = "draft"
RELEASE_STAGE = "release"
# execution scheduler の phase 順。raw task-graph の 13-phase edge は claim provenance に保存する一方、
# draft は「使える実体」に必要な P01/P02/P05 を先に完了させる。release は全 draft
# proof 後に、現物があって初めて意味を持つ review/test/audit を phase 順で回収する。
EXECUTION_PHASE_ORDER = (
    "P01", "P02", "P05", "P03", "P04", "P06", "P07", "P08", "P09", "P10", "P11", "P12", "P13",
)


def _safe_id(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9:._-]+", "-", raw)


def _node_stage(node: dict) -> str:
    """direct-task node を第1稿と本番のどちらへ割り当てるか決める。

    phase_ref だけで決定論に引く。title の自然文や entity_ref の有無で判断しない
    (task-graph の意味論を 2 箇所で解釈すると、片方だけ直した状態が黙って成立する)。
    """
    return DRAFT_STAGE if str(node.get("phase_ref") or "") in DRAFT_PHASES else RELEASE_STAGE


def _folds_into_route(node: dict) -> bool:
    """entity_ref を持つ node を route obligation へ畳み込むか。

    `component-build` は route build そのものなので phase_ref を問わず畳む
    (phase_ref を持たない node もある)。それ以外の direct-task は stage で決める —
    同じ component の「受入テストを赤で固定する」(P04) まで畳むと、第1稿の
    route build 指示に赤いスイート作成が混ざり、stage を分けた意味が消える。
    """
    return node.get("execution_kind") == "component-build" or _node_stage(node) == DRAFT_STAGE


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


def normalize_fixed_execution_types(task_graph: object) -> object:
    """pre-migration fixed graph を構造だけから同値の gate/claim 型へ正規化する。

    全 node が未型付きの旧 fixed graph だけを対象とし、型付き/未型付き混在は
    fail-closed。derive-task-graph.py で再導出した正本と同じ分類にするための移行境界であり、
    claim の削除や title 解釈は行わない。
    """
    if not isinstance(task_graph, dict):
        return task_graph
    nodes = _graph_nodes(task_graph)
    if not nodes:
        return task_graph
    typed = ["execution_kind" in node for node in nodes]
    if any(typed) and not all(typed):
        raise ValueError("task-graph execution_kind が型付き/未型付き混在")
    if all(typed):
        return task_graph
    parent_roots = {
        str(edge.get("from")) for edge in _graph_edges(task_graph, "parent_of")
    }
    normalized = dict(task_graph)
    normalized_nodes: list[dict] = []
    for node in nodes:
        item = dict(node)
        task_id = str(item.get("id") or "")
        if task_id in parent_roots:
            item.update({"execution_kind": "phase-gate", "route_ref": None, "task_spec_ref": None})
        else:
            item.update({
                "acceptance_criterion": str(item.get("acceptance_criterion") or item.get("title") or task_id),
                "execution_kind": "verification-claim",
                "execution_stage": _node_stage(item),
                "route_ref": item.get("entity_ref"),
                "task_spec_ref": None,
            })
        normalized_nodes.append(item)
    normalized["nodes"] = normalized_nodes
    return normalized


def _ordered_claim_ids(claim_ids: set[str], dependency_edges: list[dict]) -> list[str]:
    """unit 内 claim の原 graph 依存順を保った決定論順を返す。"""
    prerequisites = {task_id: set() for task_id in claim_ids}
    for edge in dependency_edges:
        consumer, producer = str(edge.get("from")), str(edge.get("to"))
        if consumer in claim_ids and producer in claim_ids and consumer != producer:
            prerequisites[consumer].add(producer)
    ordered: list[str] = []
    remaining = set(claim_ids)
    while remaining:
        ready = sorted(task_id for task_id in remaining if not (prerequisites[task_id] & remaining))
        if not ready:
            raise ValueError(f"execution unit 内 claim dependency が循環: {sorted(remaining)}")
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def _route_inputs(route: dict, plan_dir: Path, repo_root: Path) -> list[dict]:
    selected = route.get("task_spec_ref") or route.get("spec")
    if not selected:
        return []
    candidate = (plan_dir / str(selected)).resolve()
    try:
        rel = candidate.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"route spec is outside repo: {candidate}") from exc
    return [{"path": rel, "required": True, "context": True}] if candidate.is_file() else []


def compile_execution_units(
    handoff: dict,
    task_graph: dict,
    inventory: object,
    *,
    plan_dir: Path,
    plan_dir_rel: str,
    repo_root: Path,
) -> dict:
    """verification-claim を phase 順序不変の execution unit へちょうど1回射影する。

    route×stage だけで P02/P05 を同一 unit にすると、間の global P03 と
    release P04 を跨いだ self/cyclic dependency になる。そのため execution_stage を
    保ちつつ、実行単位は依存順を弱めない最小の route×phase / global×phase とする。
    """
    routes = handoff.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("handoff.routes must be a non-empty array")
    routes_by_id = {
        str(route.get("id")): route for route in routes
        if isinstance(route, dict) and route.get("id")
    }
    if len(routes_by_id) != len(routes):
        raise ValueError("route ids must be non-empty and unique")

    nodes = _graph_nodes(task_graph)
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    if len(node_by_id) != len(nodes):
        raise ValueError("task-graph node ids must be non-empty and unique")
    claims = {
        task_id: node for task_id, node in node_by_id.items()
        if node.get("execution_kind") == "verification-claim"
    }
    gates = {
        task_id: node for task_id, node in node_by_id.items()
        if node.get("execution_kind") == "phase-gate"
    }
    other_typed = sorted(
        task_id for task_id, node in node_by_id.items()
        if node.get("execution_kind") not in {"verification-claim", "phase-gate"}
    )
    if not claims:
        raise ValueError("typed fixed graph has no verification-claim nodes")
    if other_typed:
        raise ValueError(f"verification-claim graph に未対応 execution kind が混在: {other_typed}")

    group_claims: dict[str, set[str]] = {}
    group_meta: dict[str, dict] = {}
    assignment: dict[str, str] = {}
    for task_id, node in sorted(claims.items()):
        phase_ref = str(node.get("phase_ref") or "")
        stage = node.get("execution_stage")
        route_ref = node.get("route_ref")
        if not phase_ref or stage not in {DRAFT_STAGE, RELEASE_STAGE}:
            raise ValueError(f"claim {task_id} は phase_ref/execution_stage を欠く")
        if route_ref is not None and str(route_ref) not in routes_by_id:
            raise ValueError(f"claim {task_id} が未知 route_ref={route_ref!r} を参照")
        if route_ref is None:
            unit_id = f"unit:global:{_safe_id(phase_ref)}"
            grouping = "global-phase"
        else:
            unit_id = f"unit:route:{_safe_id(str(route_ref))}:{_safe_id(phase_ref)}"
            grouping = "route-phase"
        if task_id in assignment:
            raise ValueError(f"claim 重複割当: {task_id}")
        assignment[task_id] = unit_id
        group_claims.setdefault(unit_id, set()).add(task_id)
        meta = {"grouping": grouping, "route_id": route_ref, "phase_ref": phase_ref, "stage": stage}
        prior = group_meta.setdefault(unit_id, meta)
        if prior != meta:
            raise ValueError(f"execution unit 内 metadata 不一致: {unit_id}")

    dependency_edges = _graph_edges(task_graph, "depends_on")
    gate_children: dict[str, set[str]] = {gate_id: set() for gate_id in gates}
    for edge in dependency_edges:
        src, dst = str(edge.get("from")), str(edge.get("to"))
        if src in gates:
            if dst not in claims:
                raise ValueError(f"phase-gate {src} が claim 以外 {dst} に依存")
            gate_children[src].add(dst)
    for gate_id, children in gate_children.items():
        if not children:
            raise ValueError(f"phase-gate {gate_id} に子 claim が無い")

    # claim の gate 依存は、gate が要求する全 child unit へ保守的に縮約する。
    raw_unit_dependencies: dict[str, set[str]] = {unit_id: set() for unit_id in group_claims}
    for edge in dependency_edges:
        consumer, producer = str(edge.get("from")), str(edge.get("to"))
        if consumer not in claims:
            continue
        if producer in claims:
            producers = {producer}
        elif producer in gates:
            producers = gate_children[producer]
        else:
            raise ValueError(f"claim {consumer} が未知 dependency {producer} を参照")
        source_unit = assignment[consumer]
        for producer_id in producers:
            target_unit = assignment[producer_id]
            if target_unit != source_unit:  # unit 内 edge は ordered_task_ids で保存。
                raw_unit_dependencies[source_unit].add(target_unit)

    unknown_phases = sorted({meta["phase_ref"] for meta in group_meta.values()} - set(EXECUTION_PHASE_ORDER))
    if unknown_phases:
        raise ValueError(f"execution scheduler が未知 phase を含む: {unknown_phases}")
    units_by_phase: dict[str, set[str]] = {}
    for unit_id, meta in group_meta.items():
        units_by_phase.setdefault(meta["phase_ref"], set()).add(unit_id)
    unit_dependencies: dict[str, set[str]] = {unit_id: set() for unit_id in group_claims}
    previous_phase_units: set[str] = set()
    for phase_ref in EXECUTION_PHASE_ORDER:
        phase_units = units_by_phase.get(phase_ref, set())
        if not phase_units:
            continue
        for unit_id in phase_units:
            # 同一 phase の route/coupling 依存は raw graph のまま保存。cross-phase は
            # explicit scheduler barrier に置換し、draft/release cut の意図をどちらも弱めない。
            unit_dependencies[unit_id].update(
                dependency for dependency in raw_unit_dependencies[unit_id]
                if group_meta[dependency]["phase_ref"] == phase_ref
            )
            unit_dependencies[unit_id].update(previous_phase_units)
        previous_phase_units = set(phase_units)

    # 縮約後も DAG であることを fail-closed に証明する。
    _ordered_claim_ids(set(group_claims), [
        {"from": unit_id, "to": dependency}
        for unit_id, dependencies in unit_dependencies.items()
        for dependency in dependencies
    ])

    slug = str(handoff.get("target_plugin_slug") or "plugin")
    build_dir = Path("eval-log") / slug / "build"
    if handoff.get("cycle_id") is not None:
        build_dir /= str(handoff["cycle_id"])
    produces_by_claim: dict[str, list[str]] = {}
    for edge in _graph_edges(task_graph, "produces"):
        produces_by_claim.setdefault(str(edge.get("from")), []).append(str(edge.get("to")))

    obligations: list[dict] = []
    for unit_id in sorted(group_claims):
        meta = group_meta[unit_id]
        covered = _ordered_claim_ids(group_claims[unit_id], dependency_edges)
        route = routes_by_id.get(str(meta["route_id"])) if meta["route_id"] is not None else None
        inputs = _route_inputs(route, plan_dir, repo_root) if route else []
        output_paths = sorted({
            path
            for task_id in covered
            for path in (
                produces_by_claim.get(task_id)
                or [str(claims[task_id].get("write_scope") or "")]
            )
            if path and "/" in path
        })
        if route:
            target = str(route.get("build_target") or "")
            if not target:
                raise ValueError(f"route {meta['route_id']} has no build_target")
            output_paths = sorted(set(output_paths) | {
                target, (build_dir / f"route-{meta['route_id']}.json").as_posix(),
            })
        execution_unit = {
            "id": unit_id,
            **meta,
            "covered_task_ids": covered,
            "ordered_task_ids": covered,
            "ordering_policy": "task-graph-dependency-topological",
            "scheduler_policy": "usable-draft-then-release-phase-barriers",
            "raw_dependency_unit_ids": sorted(raw_unit_dependencies[unit_id]),
        }
        obligations.append({
            "id": unit_id,
            "claim": (
                f"{meta['route_id']} route claims for {meta['phase_ref']} are all proven"
                if route else f"Global claims for {meta['phase_ref']} are all proven"
            ),
            "kind": "generative",
            "risk": "high" if meta["phase_ref"] in {"P03", "P09", "P10", "P13"} else "medium",
            "activation": "changed",
            "stage": meta["stage"],
            "depends_on": sorted(unit_dependencies[unit_id]),
            "inputs": inputs,
            "parameters": {
                "execution_unit": execution_unit,
                "covered_task_ids": covered,
                "task_nodes": [claims[task_id] for task_id in covered],
                "route": route,
                "inventory_component": (
                    _inventory_component(inventory, str(meta["route_id"])) if route else None
                ),
                "plan_dir": plan_dir_rel,
                "mode": handoff.get("mode"),
            },
            "expected_evidence_paths": output_paths,
            "model_required": True,
            "minimum_confidence": 0.9,
            "reuse": True,
        })

    assigned_ids = [task_id for obligation in obligations
                    for task_id in obligation["parameters"]["covered_task_ids"]]
    duplicates = sorted(task_id for task_id in set(assigned_ids) if assigned_ids.count(task_id) != 1)
    unassigned = sorted(set(claims) - set(assigned_ids))
    if duplicates or unassigned or len(assigned_ids) != len(claims):
        raise ValueError(f"claim coverage violation: unassigned={unassigned} duplicate={duplicates}")

    proof_projections = []
    for gate_id in sorted(gates):
        required_claim_ids = sorted(gate_children[gate_id])
        proof_projections.append({
            "task_id": gate_id,
            "dispatch": "none",
            "required_claim_ids": required_claim_ids,
            "required_unit_ids": sorted({assignment[task_id] for task_id in required_claim_ids}),
            "proof_policy": "all-claims-done-with-unique-evidence-report-ref",
        })
    coverage_digest = hashlib.sha256(
        json.dumps(assignment, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "subject": f"{slug}:route-build",
        "obligations": obligations,
        "claim_coverage": {
            "executable_claim_count": len(claims),
            "assigned_claim_count": len(assigned_ids),
            "execution_unit_count": len(obligations),
            "phase_gate_count": len(gates),
            "unassigned_task_ids": unassigned,
            "duplicate_task_ids": duplicates,
            "assignment_sha256": f"sha256:{coverage_digest}",
        },
        "proof_projections": proof_projections,
    }


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
    task_graph = normalize_fixed_execution_types(task_graph)

    graph_nodes = _graph_nodes(task_graph)
    if any(node.get("execution_kind") == "verification-claim" for node in graph_nodes):
        return compile_execution_units(
            handoff,
            task_graph,
            inventory,
            plan_dir=plan_dir,
            plan_dir_rel=plan_dir_rel,
            repo_root=repo_root,
        )

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
            # route obligation が背負うのは draft 段の node だけにする。
            # entity_ref を持つ node を無条件に畳み込むと、同じ component の
            # 「受入テストを赤で固定する」(P04) まで route build の指示に混ざり、
            # stage=draft でも赤いスイートを書かされる。畳み込みの単位は
            # component ではなく「component × stage」である。
            "task_nodes": [n for n in _task_nodes(task_graph, route_id) if _folds_into_route(n)],
            "mode": handoff.get("mode"),
        }
        obligations.append({
            "id": f"build:{_safe_id(route_id)}",
            "claim": f"Route {route_id} is materially built at {target} from its current route-local specification.",
            "kind": "generative",
            "risk": "high",
            "activation": "changed",
            # route build は成果物そのもの。第1稿から外すと「使える実体」が存在しない。
            "stage": DRAFT_STAGE,
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
        if entity_ref in route_ids and _folds_into_route(node):
            node_obligation[node_id] = f"build:{_safe_id(entity_ref)}"
        elif node.get("execution_kind") == "direct-task":
            # entity_ref を持つ release 段の node もここへ来る。route へ畳まず
            # 独立した obligation にすることで、第1稿から外して昇格時に回収できる。
            node_obligation[node_id] = f"task:{_safe_id(node_id)}"

    dependency_edges = _graph_edges(task_graph, "depends_on")
    produces_edges = _graph_edges(task_graph, "produces")
    for node_id, obligation_id in sorted(node_obligation.items()):
        node = node_by_id[node_id]
        if obligation_id.startswith("build:"):
            continue  # route obligation へ畳み込み済み
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
            "stage": _node_stage(node),
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
