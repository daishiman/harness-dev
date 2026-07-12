#!/usr/bin/env python3
# /// script
# name: validate-task-graph
# purpose: task-graph.json を fail-soft 検査する (DAG非循環/orphan0/producer一意/inventory矛盾0/consumes producer実在/dangling edge端点0/非正準拒否/bootstrap→target移行gate)。単一 writer=derive-task-graph.py の canonicalize() を再適用して手書き編集を拒否する読み取り側検証器。
# inputs:
#   - argv: <PLAN_DIR> (task-graph.json + component-inventory.json を含むディレクトリ)
# outputs:
#   - stdout: violations 一覧 (空なら無出力)
#   - stderr: IO/引数エラー
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-graph.json の検証器 (C2/C3/C11)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C2/C3/C11) +
phase-04-test-design.md の C2 受入例。canonicalize() の再適用で非正準 (手書き編集)
を拒否し、DAG 非循環・orphan・producer 一意・inventory 依存整合・consumes producer 実在・
dangling edge 端点・phase 非逆走・couples_with 直列化実現・node.state pending seed 固定の 10 検査に、
bootstrap→target shape 移行 gate (l・GAP-BOOTSTRAP-TARGET-SHAPE-001) を additive で加えた検査群を
fail-soft (violations list) で返す。単一 writer=derive-task-graph.py。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))


def _load_derive():
    """derive-task-graph.py (ハイフン名) を importlib でロードし canonicalize を再利用する。"""
    path = _SCRIPTS / "derive-task-graph.py"
    spec = importlib.util.spec_from_file_location("derive_task_graph", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


derive_task_graph = _load_derive()

_DAG_EDGE_TYPES = ("depends_on", "parent_of")
_ALL_EDGE_TYPES = ("parent_of", "depends_on", "produces", "consumes")
_CANONICAL_NODE_STATE = "pending"


def _nodes(graph: dict) -> list[dict]:
    return [n for n in (graph.get("nodes") or []) if isinstance(n, dict)]


def _edges(graph: dict) -> list[dict]:
    return [e for e in (graph.get("edges") or []) if isinstance(e, dict)]


def _check_dag(edges: list[dict]) -> list[str]:
    """(a) depends_on/parent_of エッジのみで DFS し閉路を検出する。"""
    adj: dict = {}
    vertices: set = set()
    for e in edges:
        if e.get("type") in _DAG_EDGE_TYPES:
            f, t = e.get("from"), e.get("to")
            adj.setdefault(f, []).append(t)
            vertices.add(f)
            vertices.add(t)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {v: WHITE for v in vertices}
    found: list = []

    def dfs(u, stack) -> bool:
        color[u] = GRAY
        for w in adj.get(u, []):
            c = color.get(w, WHITE)
            if c == GRAY:
                found.append(stack + [u, w])
                return True
            if c == WHITE and dfs(w, stack + [u]):
                return True
        color[u] = BLACK
        return False

    for v in sorted(vertices, key=str):
        if color.get(v, WHITE) == WHITE and dfs(v, []):
            break
    if found:
        chain = " -> ".join(str(x) for x in found[0])
        return [f"(a) cycle detected in depends_on/parent_of edges: {chain}"]
    return []


def _check_orphans(nodes: list[dict], edges: list[dict]) -> list[str]:
    """(b) 4 種いずれの edge にも from/to として現れない node を検出する。"""
    endpoints: set = set()
    for e in edges:
        if e.get("type") in _ALL_EDGE_TYPES:
            endpoints.add(e.get("from"))
            endpoints.add(e.get("to"))
    out = []
    for nid in sorted((n.get("id") for n in nodes if n.get("id") is not None), key=str):
        if nid not in endpoints:
            out.append(f"(b) orphan node (not referenced by any edge): {nid}")
    return out


def _check_producer_unique(edges: list[dict]) -> list[str]:
    """(c) produces エッジの to (artifact) が複数の異なる node から指されていないか。"""
    producers: dict = {}
    for e in edges:
        if e.get("type") == "produces":
            producers.setdefault(e.get("to"), set()).add(e.get("from"))
    out = []
    for art in sorted((a for a in producers if a is not None), key=str):
        froms = producers[art]
        if len(froms) > 1:
            listed = ", ".join(sorted(str(x) for x in froms))
            out.append(f"(c) artifact {art} has multiple producers: {listed}")
    return out


def _check_inventory(nodes: list[dict], edges: list[dict], inventory: dict) -> list[str]:
    """(d) inventory の component 粒度 depends_on が task depends_on エッジで実現されているか。

    inventory 上 B が A に依存 (B.depends_on に A) するとき、entity_ref=B の node から
    entity_ref=A の node への depends_on エッジが存在しない (=向き逆転/欠落) 場合を violation。
    """
    comp_depends: dict = {}
    if isinstance(inventory, dict):
        for c in inventory.get("components", []) or []:
            if isinstance(c, dict) and isinstance(c.get("id"), str):
                deps = c.get("depends_on", [])
                comp_depends[c["id"]] = [d for d in deps if isinstance(d, str)] if isinstance(deps, list) else []

    nodes_by_entity: dict = {}
    for n in nodes:
        ent = n.get("entity_ref")
        if isinstance(ent, str):
            nodes_by_entity.setdefault(ent, set()).add(n.get("id"))

    dep_pairs = {(e.get("from"), e.get("to")) for e in edges if e.get("type") == "depends_on"}

    out = []
    for b in sorted(comp_depends):
        for a in sorted(comp_depends[b]):
            if a == b:
                continue
            b_nodes = nodes_by_entity.get(b, set())
            a_nodes = nodes_by_entity.get(a, set())
            if not b_nodes or not a_nodes:
                continue
            realized = any(f in b_nodes and t in a_nodes for (f, t) in dep_pairs)
            if not realized:
                out.append(
                    f"(d) inventory dependency {b} depends_on {a} not realized by any task depends_on edge"
                )
    return out


def _check_consumes(nodes: list[dict], edges: list[dict]) -> list[str]:
    """(e) consumes artifact が produces artifact に存在するか。

    正本は consumes=(artifact -> consumer task)。from artifact が produces.to に存在し、
    to が実在 task node を指すことを検査する。逆向き task -> artifact は fail-closed。
    """
    produced = {e.get("to") for e in edges if e.get("type") == "produces"}
    node_ids = {n.get("id") for n in nodes}
    out: list[str] = []
    for edge in edges:
        if edge.get("type") != "consumes":
            continue
        artifact = edge.get("from")
        consumer = edge.get("to")
        if artifact not in produced:
            out.append(f"(e) consumes references artifact with no producer: {artifact}")
        if consumer not in node_ids:
            out.append(f"(e) consumes references missing consumer task: {consumer}")
    return sorted(set(out))


def _check_node_states(nodes: list[dict]) -> list[str]:
    """(g) canonical task-graph node.state は pending seed に固定する。"""
    out: list[str] = []
    for n in nodes:
        state = n.get("state")
        if state != _CANONICAL_NODE_STATE:
            out.append(
                f"(g) node {n.get('id')} has invalid state {state!r}; "
                "canonical task-graph requires pending seed; runtime states belong to task-state.json"
            )
    return out


def _target_shape_declared(nodes: list[dict]) -> bool:
    """graph 内に execution_kind を携帯する node が 1 つでもあれば target shape 採用宣言とみなす。"""
    return any(isinstance(n.get("execution_kind"), str) and n.get("execution_kind") for n in nodes)


def _check_migration_gate(nodes: list[dict], marker: str) -> list[str]:
    """(l) bootstrap→target shape 移行 gate (marker 非依存の additive 層・C17 風化防止)。

    GAP-BOOTSTRAP-TARGET-SHAPE-001: fixed-13-phase bootstrap は execution_kind を一切携帯せず、
    legacy join は entity_ref から route を暗黙推測する。C01 build 完了後の target shape は明示
    route_ref parity を必須化し、legacy join は shape marker でだけ後方互換許可する。本 gate は
    「一部 node だけ target shape へ移行した中途半端 (=最も危険) な graph」を fail-closed で拒否する。

    発火条件 (どちらか成立):
      - target shape 採用宣言 = execution_kind を携帯する node が 1 つでも存在する (marker 非依存)。
      - shape_marker=task-graph-derived (dispatchable node に execution_kind 必須という shape 宣言)。
    非発火 (後方互換): fixed-13-phase marker かつ execution_kind 全不在 (現行 bootstrap plan)。
    entity_ref を持つ legacy node が多数あっても execution_kind が皆無なら発火しない。

    要求 (発火時):
      (l1) 部分携帯 fail-closed: entity_ref 非 null の全 node が execution_kind を携帯すること。
           一部 component node だけ移行し他は legacy のまま残る中途半端 shape を拒否する。
      (l2) 明示 route_ref parity: execution_kind==component-build の全 node が非空 route_ref を
           携帯すること (entity_ref からの暗黙 route 推測を禁止)。direct-task/phase-gate の
           route_ref=null は schema 通りで (l2) の対象外 ((k) が shape 別の詳細を担う)。
    """
    if not (_target_shape_declared(nodes) or marker == "task-graph-derived"):
        return []
    out: list[str] = []
    for n in nodes:
        entity = n.get("entity_ref")
        kind = n.get("execution_kind")
        if isinstance(entity, str) and entity and not (isinstance(kind, str) and kind):
            out.append(
                f"(l) migration gate: dispatchable node {n.get('id')} (entity_ref={entity!r}) "
                "lacks execution_kind — partial bootstrap→target adoption is fail-closed "
                "(GAP-BOOTSTRAP-TARGET-SHAPE-001)"
            )
    for n in nodes:
        if n.get("execution_kind") == "component-build":
            route = n.get("route_ref")
            if not (isinstance(route, str) and route.strip()):
                out.append(
                    f"(l) migration gate: component-build node {n.get('id')} requires explicit "
                    "non-empty route_ref (implicit entity_ref->route inference is forbidden)"
                )
    return out


def _check_edge_endpoints(nodes: list[dict], edges: list[dict]) -> list[str]:
    """(h) depends_on/parent_of エッジの from/to が nodes.id に実在するか (dangling edge 検出)。

    produces/consumes は artifact 端点を持つため対象外 (node↔node の DAG エッジのみ検査)。
    dangling depends_on は runtime の compute-ready-set で対象ノードを永久非 ready 化し、
    spec-gap 停滞で初めて露見する (shift-left の穴)。plan-time で拒否して runtime へ滑らせない (F5)。
    """
    node_ids = {n.get("id") for n in nodes if n.get("id") is not None}
    out: list[str] = []
    seen: set = set()
    for e in edges:
        if e.get("type") not in _DAG_EDGE_TYPES:
            continue
        for role in ("from", "to"):
            endpoint = e.get(role)
            if endpoint is not None and endpoint not in node_ids and endpoint not in seen:
                seen.add(endpoint)
                out.append(f"(h) dangling {e.get('type')} edge endpoint (not a node id): {endpoint}")
    return out


def _phase_order(phase_ref: str) -> int | None:
    """P01..P13 を数値順へ写す。未知形式は本検査の対象外にする。"""
    m = re.match(r"^P(\d+)$", str(phase_ref))
    return int(m.group(1)) if m else None


def _check_phase_dependency_direction(nodes: list[dict], edges: list[dict]) -> list[str]:
    """(i) depends_on が phase 軸を逆走しないことを検査する。

    `from depends_on to` の `to` が `from` より未来 phase の場合、P02 が P10 を待つ形になり、
    13 phase ライフサイクルの実行順を壊す。DAG として非循環でも意味的には不正なので拒否する。
    """
    phase_by_id = {n.get("id"): _phase_order(n.get("phase_ref")) for n in nodes}
    out: list[str] = []
    for e in edges:
        if e.get("type") != "depends_on":
            continue
        f, t = e.get("from"), e.get("to")
        fp, tp = phase_by_id.get(f), phase_by_id.get(t)
        if fp is None or tp is None:
            continue
        if tp > fp:
            out.append(
                f"(i) future phase dependency: {f}({fp:02d}) depends_on {t}({tp:02d})"
            )
    return out


def _check_couples(nodes: list[dict], edges: list[dict], inventory: dict) -> list[str]:
    """(j) inventory の couples_with (接合が密な兄弟ペア) が直列化 depends_on で実現され、
    参照先が実在 component であることを検査する ((d) inventory depends_on 実現検査の鏡像)。

    couples_with は対称宣言。derive の直列化と整合させ、次を対象外にする:
      - **推移閉包**で既に component depends_on 順序付いたペア (直接 A→B だけでなく A→C→B も)。
        直列化済ゆえ derive は coupling を skip する (逆走 cycle 回避) — (j) も要求しない。
      - **共有 phase を持たない** cross-phase ペア。derive は同一 phase のみ直列化し、異 phase は
        phase 順序 edge が直列化するため coupling edge を焼かない — (j) が直接 edge を要求すると
        偽陽性になるので skip する。
    共有 phase を持ち未順序のペアは、その共有 phase の entity node 間 depends_on エッジ (どちらの
    向きでも) が無ければ「宣言したのに盲目並列へ逆戻り」する silent 穴ゆえ violation とする。
    """
    if not isinstance(inventory, dict):
        return []
    comp_ids = {c.get("id") for c in inventory.get("components", []) if isinstance(c, dict)}
    couples: set = set()
    comp_depends: dict[str, list[str]] = {}
    out: list[str] = []
    for c in inventory.get("components", []) or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        cw = c.get("couples_with", [])
        if isinstance(cid, str) and isinstance(cw, list):
            for other in cw:
                if not isinstance(other, str) or not other or other == cid:
                    continue
                if other not in comp_ids:
                    out.append(f"(j) couples_with references unknown component: {cid} -> {other}")
                    continue
                couples.add(frozenset((cid, other)))
        deps = c.get("depends_on", [])
        if isinstance(cid, str) and isinstance(deps, list):
            comp_depends[cid] = [d for d in deps if isinstance(d, str) and d != cid]

    # 推移閉包は derive の SSOT を import 再利用する (直接ペアでなく推移順序も skip 判定に使う)。
    reach = derive_task_graph._transitive_closure(comp_depends)

    nodes_by_entity: dict = {}
    entity_phases: dict = {}
    for n in nodes:
        ent = n.get("entity_ref")
        if isinstance(ent, str):
            nodes_by_entity.setdefault(ent, set()).add(n.get("id"))
            entity_phases.setdefault(ent, set()).add(n.get("phase_ref"))
    dep_pairs = {(e.get("from"), e.get("to")) for e in edges if e.get("type") == "depends_on"}

    for pair in sorted(couples, key=lambda p: sorted(p)):
        a, b = sorted(pair)
        if b in reach.get(a, set()) or a in reach.get(b, set()):
            continue  # 推移閉包で既に順序付き=(d) が担う (逆走 cycle を封じ derive も skip)
        a_nodes = nodes_by_entity.get(a, set())
        b_nodes = nodes_by_entity.get(b, set())
        if not a_nodes or not b_nodes:
            continue  # 片方に node が無いペアは直列化不能 (component orphan は detect-unassigned が担当)
        if not (entity_phases.get(a, set()) & entity_phases.get(b, set())):
            continue  # 共有 phase 無し=cross-phase (phase 順序が直列化・coupling は no-op)
        serialized = any(
            (f in a_nodes and t in b_nodes) or (f in b_nodes and t in a_nodes)
            for (f, t) in dep_pairs
        )
        if not serialized:
            out.append(
                f"(j) couples_with {a}<->{b} not realized by any serialization depends_on edge "
                "(densely-coupled siblings would be blindly parallelized)"
            )
    return out


def _check_canonical(graph: dict) -> list[str]:
    """(f) canonicalize() 再適用結果が入力と一致しない (手書き編集された) graph を拒否する。"""
    try:
        canon = derive_task_graph.canonicalize(graph)
    except (TypeError, AttributeError, KeyError) as exc:
        return [f"(f) canonicalize failed (malformed graph): {exc}"]
    if canon != graph:
        return ["(f) graph is not canonical (hand-edited task-graph.json is rejected)"]
    return []


def _check_target_shape(graph: dict, plan_dir: Path | None) -> list[str]:
    """(k) task-graph-derived の renderer 前提と phase-gate/leaf shape を fail-closed 検査する。"""
    nodes = _nodes(graph)
    edges = _edges(graph)
    out: list[str] = []
    node_ids = {n.get("id") for n in nodes}
    parent_pairs = {
        (e.get("from"), e.get("to")) for e in edges if e.get("type") == "parent_of"
    }
    producing_nodes = {
        e.get("from") for e in edges if e.get("type") == "produces"
    }
    roots_by_phase: dict[str, list[dict]] = {}
    leaves: list[dict] = []
    for node in nodes:
        nid = node.get("id")
        ek = node.get("execution_kind")
        if ek == "phase-gate":
            roots_by_phase.setdefault(node.get("phase_ref"), []).append(node)
            if nid != node.get("phase_ref"):
                out.append(f"(k) phase-gate id must equal phase_ref: {nid}")
            if node.get("route_ref") is not None or node.get("task_spec_ref") is not None:
                out.append(f"(k) phase-gate must have null route_ref/task_spec_ref: {nid}")
            continue
        leaves.append(node)
        if ek not in ("direct-task", "component-build"):
            out.append(f"(k) executable leaf {nid} has invalid/missing execution_kind: {ek!r}")
        task_spec_ref = node.get("task_spec_ref")
        if not (isinstance(task_spec_ref, str) and task_spec_ref.startswith("task-specs/") and task_spec_ref.endswith(".md")):
            out.append(f"(k) executable leaf {nid} requires task_spec_ref=task-specs/*.md")
        if ek == "component-build" and not (
            isinstance(node.get("route_ref"), str) and node.get("route_ref").strip()
        ):
            out.append(f"(k) component-build leaf {nid} requires explicit route_ref")
        if ek == "direct-task" and node.get("route_ref") is not None:
            out.append(f"(k) direct-task leaf {nid} must have null route_ref")
        if not (isinstance(node.get("acceptance_criterion"), str) and node.get("acceptance_criterion").strip()):
            out.append(f"(k) executable leaf {nid} requires non-empty acceptance_criterion")
        if not (isinstance(node.get("write_scope"), str) and node.get("write_scope").strip()):
            out.append(f"(k) executable leaf {nid} requires non-empty write_scope")
        if nid not in producing_nodes:
            out.append(f"(k) executable leaf {nid} requires at least one produces artifact")
        phase_ref = node.get("phase_ref")
        if (phase_ref, nid) not in parent_pairs:
            out.append(f"(k) executable leaf {nid} is not parented by phase root {phase_ref}")

        if plan_dir is not None and isinstance(task_spec_ref, str):
            spec_path = plan_dir / task_spec_ref
            if not spec_path.is_file():
                out.append(f"(k) task_spec_ref does not exist for {nid}: {task_spec_ref}")
            else:
                try:
                    fm = derive_task_graph.specfm.parse_frontmatter(spec_path.read_text(encoding="utf-8"))
                except OSError as exc:
                    out.append(f"(k) task spec unreadable for {nid}: {exc}")
                else:
                    if fm.get("id") != nid:
                        out.append(f"(k) task spec id mismatch for {nid}: {fm.get('id')!r}")
                    for field in ("objective", "verify"):
                        if not (isinstance(fm.get(field), str) and fm.get(field).strip()):
                            out.append(f"(k) task spec {task_spec_ref} requires non-empty {field}")

    for phase_ref in sorted({n.get("phase_ref") for n in leaves}, key=str):
        roots = roots_by_phase.get(phase_ref, [])
        if len(roots) != 1:
            out.append(f"(k) phase {phase_ref} requires exactly one phase-gate root (found {len(roots)})")
    for phase_ref, roots in roots_by_phase.items():
        if phase_ref not in {n.get("phase_ref") for n in leaves}:
            out.append(f"(k) phase-gate has no executable leaves: {phase_ref}")
        for root in roots:
            if root.get("id") not in node_ids:
                out.append(f"(k) phase-gate missing from node set: {root.get('id')}")
    return out


def validate(
    graph: dict,
    inventory: dict,
    *,
    marker: str = "fixed-13-phase",
    plan_dir: Path | None = None,
) -> list[str]:
    """task-graph の検査を fail-soft で実行する。target shape は (k) を加える。"""
    nodes = _nodes(graph)
    edges = _edges(graph)
    violations: list[str] = []
    violations += _check_dag(edges)
    violations += _check_orphans(nodes, edges)
    violations += _check_producer_unique(edges)
    violations += _check_inventory(nodes, edges, inventory)
    violations += _check_consumes(nodes, edges)
    violations += _check_edge_endpoints(nodes, edges)
    violations += _check_phase_dependency_direction(nodes, edges)
    violations += _check_couples(nodes, edges, inventory)
    violations += _check_canonical(graph)
    violations += _check_node_states(nodes)
    violations += _check_migration_gate(nodes, marker)
    if marker == "task-graph-derived":
        violations += _check_target_shape(graph, plan_dir)
    elif marker != "fixed-13-phase":
        violations.append(f"(k) unknown shape_marker={marker!r}")
    return violations


def _usage() -> int:
    print("usage: validate-task-graph.py <PLAN_DIR>", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        return _usage()
    plan_dir = Path(argv[0])
    if not plan_dir.is_dir():
        print(f"not a directory: {plan_dir}", file=sys.stderr)
        return 2

    try:
        marker = derive_task_graph.shape_marker(plan_dir)
    except ValueError as exc:
        print(f"(k) {exc}")
        return 1

    graph_path = plan_dir / "task-graph.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {graph_path}: {exc}", file=sys.stderr)
        return 2

    inventory: dict = {}
    inv_path = plan_dir / "component-inventory.json"
    if inv_path.exists():
        try:
            inventory = json.loads(inv_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"read/parse error: {inv_path}: {exc}", file=sys.stderr)
            return 2

    violations = validate(graph, inventory, marker=marker, plan_dir=plan_dir)
    if violations:
        for v in violations:
            print(v)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
