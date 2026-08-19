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
