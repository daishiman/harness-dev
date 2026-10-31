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
bootstrap→target shape 移行 gate (l・GAP-BOOTSTRAP-TARGET-SHAPE-001) と
task node/component ID 一意性 (m) を additive で加えた検査群を fail-soft
(violations list) で返す。単一 writer=derive-task-graph.py。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))


def _load_shape_checks():
    """命名規約に従うハイフン区切りの補助スクリプトをロードする。"""
    path = _SCRIPTS / "validate-task-graph-shapes.py"
    spec = importlib.util.spec_from_file_location("task_graph_shape_checks", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load task graph shape checks: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shape_checks = _load_shape_checks()


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


def _duplicate_ids(entries: list[dict]) -> list[str]:
    """集合・辞書へ変換する前に、文字列 ID の重複を決定論的に列挙する。"""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for entry in entries:
        value = entry.get("id")
        if not isinstance(value, str):
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _check_id_uniqueness(nodes: list[dict], inventory: dict) -> list[str]:
    """(m) downstream の set/dict 化で別要素が同じ ID へ畳み込まれる前に拒否する。"""
    components = (
        [c for c in inventory.get("components", []) if isinstance(c, dict)]
        if isinstance(inventory, dict)
        else []
    )
    out: list[str] = []
    for label, entries in (("task node", nodes), ("component", components)):
        duplicates = _duplicate_ids(entries)
        if duplicates:
            out.append(f"(m) duplicate {label} id(s): {', '.join(duplicates)}")
    return out


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


def _check_migration_gate(nodes: list[dict], marker: str) -> list[str]:
    """(l) shape 固有検査は support module へ委譲する。"""
    return shape_checks.check_migration_gate(nodes, marker)


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
    """(j) couples_with 検査は shape support module へ委譲する。"""
    return shape_checks.check_couples(nodes, edges, inventory, derive_task_graph)


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
    """(k) target shape 検査は shape support module へ委譲する。"""
    return shape_checks.check_target_shape(graph, plan_dir, derive_task_graph)


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
    violations += _check_id_uniqueness(nodes, inventory)
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
