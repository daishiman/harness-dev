#!/usr/bin/env python3
# /// script
# name: consult-harness-artifact-graph
# version: 0.1.0
# purpose: run-ubm-goal-setting Phase1-2-collect から C06 knowledge-graph.json と C05
#          harness-artifact-graph.json を read-only に跨いで探索し、local/global/relationship
#          query で関連 knowledge/成果物を source refs/path/graph hash 付きで返す consult (C07)。
#          index (C05) が「これから作る計画」と「実成果物」を突合した後、本 script が
#          その正規化グラフと knowledge グラフを引くだけの純粋読取レイヤーを担う。
# inputs:
#   - argv: --topic TEXT --knowledge-graph FILE [--harness-artifact-graph FILE]
#           --query-type local|global|relationship --depth 1..5
#   - file: knowledge-graph.json (C06 出力・nodes/edges/associations・必須)
#   - file: harness-artifact-graph.json (C05 出力・nodes/edges/graph_hash・任意)
#           省略/未生成時は knowledge 単独 consult (sources.harness_artifact_graph.status=absent)
# outputs:
#   - stdout: JSON hits (nodes/edges を id/path/hash ポインタ形で・zero_hit フラグ・source graph hash・
#             warnings[]: knowledge graph の辺 0 本は "graph-edges-empty" を記録)
#   - stderr: usage error / broken index (スキーマ不正・dangling) 一覧
#   - exit: 0=正常 (zero-hit 含む) / 2=usage・入力不正・壊れた index
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""harness/knowledge デュアルグラフの read-only 探索 consult (C07)。

C05 (index-harness-artifact-graph.py) が計画 (task-graph/handoff) と実成果物
(task-state/route-report/build-trace/実在 build_target) を突合した
harness-artifact-graph.json と、C06 (validate-knowledge-graph.py) が検証再生成した
knowledge-graph.json を、書込まず・network なしで引く。

query-type:
  local        : topic に直接マッチする node + 隣接辺 (depth 上限まで無方向 BFS 展開)
  global       : topic に緩くマッチする node をカテゴリ (knowledge) / state (harness)
                 クラスタ単位に要約する
  relationship : topic を区切り ('->' '=>' '::' '|' ' to ') で 2 概念に分け、各グラフ内で
                 端点間の最短 path を探索する

正常性:
  - zero-hit (topic 不一致) は正常 (exit0・空 hits・zero_hit=true)
  - knowledge graph の辺 0 本 (退化グラフ) も zero-hit 同様に正常 (exit0) だが、consumer が
    consult_evidence へ転記できるよう出力 warnings[] に "graph-edges-empty" を記録する
  - 壊れた index (スキーマ不正・dangling edge) は zero-hit と区別し exit2 (エラー側)
  - --harness-artifact-graph 省略は正常 (exit0)。harness graph を空扱いで knowledge
    単独 consult に落とす (graceful degrade)。knowledge graph は必須のまま。

セキュリティ:
  - graph ファイル引数を正規化し '..' 親traversal を含む path を拒否する (exit2)
  - 出力の全 str 葉から secret 様 token を [REDACTED] へ置換し件数を記録する (C05 規約継承)
  - hit の evidence は id/path/hash まで。knowledge edge の逐語 evidence 本文は返さず
    evidence_count のみに落とす (secret/PII 本文非返却)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = "1.0.0"
GENERATOR = "consult-harness-artifact-graph.py"

QUERY_TYPES = ("local", "global", "relationship")
# relationship の端点区切り (優先順)。topic を A/B の 2 概念へ割る。
ENDPOINT_SEPARATORS = ("->", "=>", "::", "|", " to ")
# global の by_category / by_state で列挙する node id の上限 (要約なので打ち切る)。
CLUSTER_ID_CAP = 20

# secret/api key 様 token の prefix パターン (C05 と byte 一致)。sha256:<64hex> は誤爆しない。
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}"
    r"|ntn_[A-Za-z0-9]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[A-Za-z0-9_-]{20,})"
)
REDACTION_TOKEN = "[REDACTED]"


class UsageError(Exception):
    """exit2 に写像する引数/入力エラー。"""


class BrokenIndexError(Exception):
    """スキーマ不正・dangling 参照など『壊れた index』。zero-hit と区別し exit2 (エラー側)。"""


# ---- redaction (C05 規約継承) ----------------------------------------------

def _redact_str(value: str) -> "tuple[str, int]":
    count = 0

    def _sub(_m: "re.Match[str]") -> str:
        nonlocal count
        count += 1
        return REDACTION_TOKEN

    return _SECRET_RE.sub(_sub, value), count


def redact_tree(obj):
    """出力木を再帰走査し全 str 葉から secret 様 token を除去する。(redacted_obj, count)。"""
    if isinstance(obj, str):
        return _redact_str(obj)
    if isinstance(obj, list):
        total = 0
        out = []
        for item in obj:
            red, c = redact_tree(item)
            out.append(red)
            total += c
        return out, total
    if isinstance(obj, dict):
        total = 0
        out = {}
        for k, v in obj.items():
            red, c = redact_tree(v)
            out[k] = red
            total += c
        return out, total
    return obj, 0


# ---- path traversal guard + load -------------------------------------------

def _reject_traversal(raw: str) -> Path:
    """graph ファイル引数を正規化し '..' 親traversal を拒否する。"""
    # posix/os いずれの区切りでも '..' コンポーネントを検出する。
    parts = re.split(r"[\\/]+", raw)
    if any(p == ".." for p in parts):
        raise UsageError(f"path traversal 拒否 ('..' を含む graph 引数): {raw}")
    return Path(raw)


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_graph_json(raw: str) -> "tuple[Path, dict]":
    path = _reject_traversal(raw)
    if not path.is_file():
        raise UsageError(f"graph ファイルが存在しない: {raw}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise BrokenIndexError(f"broken index: JSON 解析不能 ({raw}): {exc}")
    if not isinstance(data, dict):
        raise BrokenIndexError(f"broken index: top-level が object でない: {raw}")
    return path, data


# ---- graph models -----------------------------------------------------------

class KnowledgeGraph:
    """C06 knowledge-graph.json を構造検証しつつ読む。dangling は broken index。"""

    def __init__(self, raw_path: str):
        self.path_arg = raw_path
        path, data = _load_graph_json(raw_path)
        self.sha256 = _sha256_file(path)

        nodes = data.get("nodes")
        edges = data.get("edges", [])
        associations = data.get("associations", [])
        if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(associations, list):
            raise BrokenIndexError(f"broken index: nodes/edges/associations が list でない: {raw_path}")

        self.nodes: dict[str, dict] = {}
        for n in nodes:
            if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not n["id"]:
                raise BrokenIndexError(f"broken index: knowledge node に有効な id が無い: {raw_path}")
            if n["id"] in self.nodes:
                raise BrokenIndexError(f"broken index: knowledge node id 重複: {n['id']}")
            self.nodes[n["id"]] = n

        self.edges: list[dict] = []
        for e in edges:
            if not isinstance(e, dict):
                raise BrokenIndexError(f"broken index: knowledge edge が object でない: {raw_path}")
            src, tgt = e.get("source_id"), e.get("target_id")
            if src not in self.nodes or tgt not in self.nodes:
                raise BrokenIndexError(
                    f"broken index: dangling knowledge edge ({src} -> {tgt}): {raw_path}"
                )
            self.edges.append(e)

        self.associations: list[dict] = []
        for a in associations:
            if not isinstance(a, dict):
                raise BrokenIndexError(f"broken index: association が object でない: {raw_path}")
            x, y = a.get("a"), a.get("b")
            if x not in self.nodes or y not in self.nodes:
                raise BrokenIndexError(f"broken index: dangling association ({x} ~ {y}): {raw_path}")
            self.associations.append(a)

        # 無方向隣接 (edge + association) と pair->関係ポインタ索引を構築する。
        self.adj: dict[str, set[str]] = {nid: set() for nid in self.nodes}
        self.pair_rel: dict[frozenset, dict] = {}
        for e in self.edges:
            s, t = e["source_id"], e["target_id"]
            self.adj[s].add(t)
            self.adj[t].add(s)
            self.pair_rel.setdefault(frozenset((s, t)), self._edge_ptr(e))
        for a in self.associations:
            x, y = a["a"], a["b"]
            self.adj[x].add(y)
            self.adj[y].add(x)
            self.pair_rel.setdefault(frozenset((x, y)), self._assoc_ptr(a))

    def searchable(self, nid: str) -> list:
        n = self.nodes[nid]
        return [nid, n.get("category"), n.get("subcategory"), n.get("title")]

    def node_ptr(self, nid: str) -> dict:
        n = self.nodes[nid]
        return {
            "id": nid,
            "category": n.get("category", ""),
            "subcategory": n.get("subcategory", ""),
            "title": n.get("title", ""),
            "source_ref": f"{self.path_arg}#nodes[id={nid}]",
        }

    def _edge_ptr(self, e: dict) -> dict:
        ev = e.get("evidence")
        # 逐語 evidence 本文は返さず件数だけ (id/path/hash まで)。
        return {
            "source_id": e.get("source_id"),
            "target_id": e.get("target_id"),
            "relation_type": e.get("relation_type"),
            "confidence": e.get("confidence"),
            "review_status": e.get("review_status"),
            "evidence_count": len(ev) if isinstance(ev, list) else 0,
            "source_ref": e.get("source_ref") if isinstance(e.get("source_ref"), str)
            else f"{self.path_arg}#edges[{e.get('source_id')}->{e.get('target_id')}]",
            "via": "edge",
        }

    def _assoc_ptr(self, a: dict) -> dict:
        return {
            "a": a.get("a"),
            "b": a.get("b"),
            "kind": a.get("kind", "related"),
            "source_ref": f"{self.path_arg}#associations[{a.get('a')}~{a.get('b')}]",
            "via": "association",
        }


class HarnessGraph:
    """C05 harness-artifact-graph.json を構造検証しつつ読む。dangling は broken index。"""

    def __init__(self, raw_path: str):
        self.path_arg = raw_path
        path, data = _load_graph_json(raw_path)
        self.sha256 = _sha256_file(path)
        gh = data.get("graph_hash")
        self.graph_hash = gh.get("recomputed") if isinstance(gh, dict) else None

        nodes = data.get("nodes")
        edges = data.get("edges", [])
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise BrokenIndexError(f"broken index: nodes/edges が list でない: {raw_path}")

        self.nodes: dict[str, dict] = {}
        for n in nodes:
            if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not n["id"]:
                raise BrokenIndexError(f"broken index: harness node に有効な id が無い: {raw_path}")
            if n["id"] in self.nodes:
                raise BrokenIndexError(f"broken index: harness node id 重複: {n['id']}")
            self.nodes[n["id"]] = n

        self.edges: list[dict] = []
        self.adj: dict[str, set[str]] = {nid: set() for nid in self.nodes}
        self.pair_rel: dict[frozenset, dict] = {}
        for e in edges:
            if not isinstance(e, dict):
                raise BrokenIndexError(f"broken index: harness edge が object でない: {raw_path}")
            f, t = e.get("from"), e.get("to")
            if f not in self.nodes or t not in self.nodes:
                raise BrokenIndexError(f"broken index: dangling harness edge ({f} -> {t}): {raw_path}")
            self.edges.append(e)
            self.adj[f].add(t)
            self.adj[t].add(f)
            self.pair_rel.setdefault(frozenset((f, t)), self._edge_ptr(e))

    def searchable(self, nid: str) -> list:
        n = self.nodes[nid]
        return [nid, n.get("name"), n.get("build_target"), n.get("component_kind"), n.get("state")]

    def node_ptr(self, nid: str) -> dict:
        n = self.nodes[nid]
        prov = n.get("provenance") if isinstance(n.get("provenance"), dict) else {}
        return {
            "id": nid,
            "component_kind": n.get("component_kind", ""),
            "name": n.get("name", ""),
            "build_target": n.get("build_target", ""),
            "state": n.get("state", ""),
            "refs": {
                "route_report": prov.get("route_report"),
                "build_trace": prov.get("build_trace"),
            },
            "source_ref": f"{self.path_arg}#nodes[id={nid}]",
        }

    def _edge_ptr(self, e: dict) -> dict:
        return {
            "from": e.get("from"),
            "to": e.get("to"),
            "type": e.get("type", "depends_on"),
            "source_ref": f"{self.path_arg}#edges[{e.get('from')}->{e.get('to')}]",
        }


class AbsentHarnessGraph:
    """--harness-artifact-graph 省略時の空グラフ。

    C05 index (harness-artifact-graph.json) は手動 build/レビュー後に再生成する
    運用生成物であり不在があり得る。その不在は「壊れた index」(exit2) と区別し、
    knowledge-graph 単独 consult を成立させる (graceful degrade)。空 nodes/adj を
    持つため matched_nodes/BFS/cluster/shortest_path は自然に空を返し、harness 側の
    hit は 0 に落ちる。出力 sources には status:"absent" を明示する。
    """

    def __init__(self):
        self.path_arg = None
        self.sha256 = None
        self.graph_hash = None
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.adj: dict[str, set[str]] = {}
        self.pair_rel: dict[frozenset, dict] = {}

    def searchable(self, nid: str) -> list:
        return []

    def node_ptr(self, nid: str) -> dict:
        return {}

    def _edge_ptr(self, e: dict) -> dict:
        return {}


# ---- matcher ----------------------------------------------------------------

def make_matcher(query: str):
    """topic を casefold 部分一致 (全体一致 or トークン一致) の述語へ変換する。"""
    q = query.strip().casefold()
    tokens = [t for t in q.split() if len(t) >= 2]
    if not tokens and q:
        tokens = [q]

    def matches(texts: list) -> bool:
        hay = "".join(t.casefold() for t in texts if isinstance(t, str) and t)
        if not hay or not q:
            return False
        if q in hay:
            return True
        return any(tok in hay for tok in tokens)

    return matches


def matched_nodes(graph, matcher) -> list:
    return sorted(nid for nid in graph.nodes if matcher(graph.searchable(nid)))


# ---- traversal --------------------------------------------------------------

def bfs_neighborhood(seeds: list, adj: dict, depth: int) -> set:
    """seeds から無方向 BFS で depth ホップまで到達する node 集合。"""
    visited = set(seeds)
    frontier = set(seeds)
    for _ in range(depth):
        nxt = set()
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in visited:
                    nxt.add(v)
        visited |= nxt
        frontier = nxt
        if not frontier:
            break
    return visited


def shortest_path(sources: list, targets: list, adj: dict, max_len: int) -> "list | None":
    """sources のいずれかから targets のいずれかへの無方向最短 path (node id 列)。

    max_len ホップ以内。決定論のため seed / 隣接を常にソート順で走査し、最初に到達した
    (= 最短かつ辞書順最小) path を返す。到達不能なら None。
    """
    src = set(sources)
    tgt = set(targets)
    if not src or not tgt:
        return None
    overlap = sorted(src & tgt)
    if overlap:
        return [overlap[0]]  # 同一概念 (長さ0 path)

    prev: dict[str, str] = {}
    dist: dict[str, int] = {s: 0 for s in src}
    visited = set(src)
    q = deque(sorted(src))
    while q:
        u = q.popleft()
        if dist[u] >= max_len:
            continue
        for v in sorted(adj.get(u, ())):
            if v in visited:
                continue
            visited.add(v)
            prev[v] = u
            dist[v] = dist[u] + 1
            if v in tgt:
                path = [v]
                while path[-1] in prev:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            q.append(v)
    return None


def path_edges(graph, node_path: list) -> list:
    """path の連続ノード間を pair->関係ポインタ索引で埋める。"""
    out = []
    for u, v in zip(node_path, node_path[1:]):
        rel = graph.pair_rel.get(frozenset((u, v)))
        if rel is not None:
            out.append(rel)
    return out


# ---- query executors --------------------------------------------------------

def incident_relations(graph, visited: set) -> "tuple[list, list]":
    """visited 内で両端が閉じている edge / association を返す (dangling を出力に載せない)。"""
    edges = [graph._edge_ptr(e) for e in getattr(graph, "edges", [])
             if e.get(_from_key(graph)) in visited and e.get(_to_key(graph)) in visited]
    assocs = []
    if isinstance(graph, KnowledgeGraph):
        assocs = [graph._assoc_ptr(a) for a in graph.associations
                  if a.get("a") in visited and a.get("b") in visited]
    return edges, assocs


def _from_key(graph) -> str:
    return "source_id" if isinstance(graph, KnowledgeGraph) else "from"


def _to_key(graph) -> str:
    return "target_id" if isinstance(graph, KnowledgeGraph) else "to"


def _sort_edges(edges: list, kf: str, kt: str) -> list:
    return sorted(edges, key=lambda e: (str(e.get(kf)), str(e.get(kt)), str(e.get("relation_type") or e.get("type"))))


def run_local(kg: KnowledgeGraph, hg: HarnessGraph, matcher, depth: int) -> dict:
    k_seeds = matched_nodes(kg, matcher)
    h_seeds = matched_nodes(hg, matcher)
    k_visited = bfs_neighborhood(k_seeds, kg.adj, depth)
    h_visited = bfs_neighborhood(h_seeds, hg.adj, depth)

    k_edges, k_assocs = incident_relations(kg, k_visited)
    h_edges, _ = incident_relations(hg, h_visited)

    hits = {
        "knowledge": {
            "nodes": [kg.node_ptr(n) for n in sorted(k_visited)],
            "edges": _sort_edges(k_edges, "source_id", "target_id"),
            "associations": sorted(k_assocs, key=lambda a: (str(a["a"]), str(a["b"]))),
        },
        "harness": {
            "nodes": [hg.node_ptr(n) for n in sorted(h_visited)],
            "edges": _sort_edges(h_edges, "from", "to"),
        },
        "global": None,
        "paths": None,
    }
    zero_hit = not k_seeds and not h_seeds
    return hits, zero_hit


def _cluster(graph, matched: list, key_field: str) -> list:
    buckets: dict[str, list] = {}
    for nid in matched:
        node = graph.nodes[nid]
        key = node.get(key_field) or ""
        buckets.setdefault(str(key), []).append(nid)
    out = []
    for key in sorted(buckets):
        ids = sorted(buckets[key])
        out.append({key_field: key, "count": len(ids), "node_ids": ids[:CLUSTER_ID_CAP]})
    return out


def run_global(kg: KnowledgeGraph, hg: HarnessGraph, matcher) -> dict:
    k_matched = matched_nodes(kg, matcher)
    h_matched = matched_nodes(hg, matcher)

    # matched node に接する edge の relation_type 分布 (要約)。
    rel_counts: dict[str, int] = {}
    mset = set(k_matched)
    for e in kg.edges:
        if e["source_id"] in mset or e["target_id"] in mset:
            rt = str(e.get("relation_type"))
            rel_counts[rt] = rel_counts.get(rt, 0) + 1

    hits = {
        "knowledge": None,
        "harness": None,
        "global": {
            "knowledge": {
                "matched_node_count": len(k_matched),
                "by_category": _cluster(kg, k_matched, "category"),
                "relation_types": [{"relation_type": rt, "count": rel_counts[rt]}
                                   for rt in sorted(rel_counts)],
            },
            "harness": {
                "matched_node_count": len(h_matched),
                "by_state": _cluster(hg, h_matched, "state"),
            },
        },
        "paths": None,
    }
    zero_hit = not k_matched and not h_matched
    return hits, zero_hit


def parse_endpoints(topic: str) -> "tuple[str, str]":
    for sep in ENDPOINT_SEPARATORS:
        if sep in topic:
            a, _, b = topic.partition(sep)
            return a.strip(), b.strip()
    raise UsageError(
        "relationship は 2 概念間の探索。topic を区切りで割ってください "
        f"(区切り: {' '.join(repr(s) for s in ENDPOINT_SEPARATORS)}) 例: 'A -> B'"
    )


def run_relationship(kg: KnowledgeGraph, hg: HarnessGraph, endpoints: "tuple[str, str]", depth: int) -> dict:
    a_matcher = make_matcher(endpoints[0])
    b_matcher = make_matcher(endpoints[1])

    paths = []
    for label, graph in (("knowledge", kg), ("harness", hg)):
        a_seeds = matched_nodes(graph, a_matcher)
        b_seeds = matched_nodes(graph, b_matcher)
        node_path = shortest_path(a_seeds, b_seeds, graph.adj, depth)
        if node_path is None:
            continue
        node_ptrs = [graph.node_ptr(n) for n in node_path]
        paths.append({
            "graph": label,
            "length": max(0, len(node_path) - 1),
            "nodes": [p["id"] for p in node_ptrs],
            "node_details": node_ptrs,
            "edges": path_edges(graph, node_path),
        })

    hits = {"knowledge": None, "harness": None, "global": None, "paths": paths}
    zero_hit = not paths
    return hits, zero_hit


# ---- assembly ---------------------------------------------------------------

def count_hits(hits: dict) -> dict:
    k = hits.get("knowledge") or {}
    h = hits.get("harness") or {}
    paths = hits.get("paths")
    return {
        "knowledge_nodes": len(k.get("nodes", [])) if k else 0,
        "knowledge_edges": len(k.get("edges", [])) if k else 0,
        "knowledge_associations": len(k.get("associations", [])) if k else 0,
        "harness_nodes": len(h.get("nodes", [])) if h else 0,
        "harness_edges": len(h.get("edges", [])) if h else 0,
        "paths": len(paths) if isinstance(paths, list) else 0,
        "redacted": 0,
    }


def parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="consult-harness-artifact-graph.py",
        description="harness/knowledge デュアルグラフの read-only 探索 consult (C07)",
    )
    parser.add_argument("--topic", required=True, help="探索トピック (relationship は 'A -> B')")
    parser.add_argument("--knowledge-graph", required=True, help="C06 knowledge-graph.json")
    parser.add_argument("--harness-artifact-graph", required=False, default=None,
                        help="C05 harness-artifact-graph.json (省略時は knowledge 単独 consult)")
    parser.add_argument("--query-type", required=True, choices=QUERY_TYPES)
    parser.add_argument("--depth", type=int, default=1, choices=range(1, 6),
                        help="探索深さ (local=BFS ホップ / relationship=最大 path 長, 1..5)")
    return parser.parse_args(argv)


def main(argv: list | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)  # query-type/depth の enum・欠落は argparse が exit2

    try:
        endpoints = None
        if args.query_type == "relationship":
            endpoints = list(parse_endpoints(args.topic))

        kg = KnowledgeGraph(args.knowledge_graph)
        # C05 harness graph は運用生成物ゆえ不在があり得る。不在時は空グラフで
        # knowledge 単独 consult に落とす (壊れた index=exit2 とは区別)。
        hg = HarnessGraph(args.harness_artifact_graph) if args.harness_artifact_graph else AbsentHarnessGraph()

        if args.query_type == "local":
            hits, zero_hit = run_local(kg, hg, make_matcher(args.topic), args.depth)
        elif args.query_type == "global":
            hits, zero_hit = run_global(kg, hg, make_matcher(args.topic))
        else:
            hits, zero_hit = run_relationship(kg, hg, tuple(endpoints), args.depth)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    except BrokenIndexError as exc:
        print(f"VIOLATION: {exc}", file=sys.stderr)
        return 2

    harness_absent = isinstance(hg, AbsentHarnessGraph)
    if harness_absent:
        harness_source = {"status": "absent",
                          "note": "harness-artifact-graph 未指定/未生成のため knowledge 単独 consult"}
    else:
        harness_source = {
            "status": "present",
            "path": hg.path_arg,
            "sha256": hg.sha256,
            "node_count": len(hg.nodes),
            "edge_count": len(hg.edges),
            "graph_hash": hg.graph_hash,
        }
    # 退化セルの可視化: 辺 0 本の knowledge graph は zero-hit 正常扱いのまま warnings で表面化する
    # (consumer は consult_evidence.warnings へ転記する。入力のみから決まる決定論値)。
    warnings: list = []
    if not kg.edges:
        warnings.append("graph-edges-empty")

    result = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "warnings": warnings,
        "query": {
            "topic": args.topic,
            "query_type": args.query_type,
            "depth": args.depth,
            "endpoints": endpoints,
        },
        "sources": {
            "knowledge_graph": {
                "path": kg.path_arg,
                "sha256": kg.sha256,
                "node_count": len(kg.nodes),
                "edge_count": len(kg.edges),
                "association_count": len(kg.associations),
            },
            "harness_artifact_graph": harness_source,
        },
        "zero_hit": zero_hit,
        "counts": count_hits(hits),
        "hits": hits,
    }

    # redaction: 出力前に全 str 葉から secret 様 token を除去し件数を記録。
    result, redacted = redact_tree(result)
    result["counts"]["redacted"] = redacted

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
