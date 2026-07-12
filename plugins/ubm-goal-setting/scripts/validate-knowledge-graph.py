#!/usr/bin/env python3
# /// script
# name: validate-knowledge-graph
# version: 0.1.0
# purpose: C08 (knowledge-relation-extractor) が返した根拠付き有方向辺の候補と knowledge entry から
#          knowledge/knowledge-graph.json を決定論再生成し検証する共有ゲート (C06)。C08 は read-only
#          (辺候補 JSON を返すのみ) ゆえ永続化 owner が不在だったため、本 script が --merge-relations で
#          候補を canonical key (source_id,target_id,relation_type) により knowledge-relations.json へ
#          冪等 merge (既存辺は保持=first-write-wins)、検証 PASS 時のみ relations と graph を atomic 書込する。
#          self-loop 禁止・depends_on の DAG 非循環・edge evidence≥1・confidence 0..1・
#          review_status 必須を検査する。related は無方向連想として cycle 対象外・dangling は非致命 drop。
#          endpoint 不在 (dangling) の辺は hard-fail にせず knowledge-relations-quarantine.json へ
#          冪等退避 (WARN) し、残辺で graph 生成を継続する縮退を持つ (entry 削除で辺が恒久ブロックに
#          ならないため)。quarantine された辺は knowledge-relations.json から除去される。
# inputs:
#   - argv: --knowledge-dir DIR [--graph-out FILE] [--merge-relations CANDIDATE_FILE]
#   - file: <knowledge-dir>/knowledge-relations.json (辺の永続ストア・不在は空辺として扱う)
#   - file: CANDIDATE_FILE (--merge-relations 時・C08 が返し呼び出し側が materialize した辺候補 JSON)
#   - file: <knowledge-dir>/*.json のうち entries[] を持つ category ファイル群
# outputs:
#   - stdout: OK + node/edge/association 件数・relations 状態 (absent/loaded/merged)・graph-out パス
#   - stderr: violation 一覧 (self-loop/evidence欠落/confidence範囲外/review_status欠落/cycle 等) と
#             WARN (dangling 辺の quarantine 退避・edges=0 の退化グラフ)
#   - file: graph-out (既定 <knowledge-dir>/knowledge-graph.json) ※検証 PASS 時のみ書込
#   - file: <knowledge-dir>/knowledge-relations.json ※(--merge-relations または quarantine 発生) かつ検証 PASS 時のみ atomic 書込
#   - file: <knowledge-dir>/knowledge-relations-quarantine.json ※dangling 辺検出かつ検証 PASS 時のみ冪等追記
#   - exit: 0=OK / 1=violation / 2=usage
# contexts: [E, C]
# network: false
# write-scope: graph-out / knowledge-relations.json / knowledge-relations-quarantine.json のみ
# dependencies: []
# requires-python: ">=3.9"
# ///
"""knowledge 依存グラフの決定論再生成 + 検証ゲート (C06)。

C08 handover の辺 schema:
  {source_id, target_id, relation_type ∈ {depends_on|supports|contradicts|derived_from},
   evidence:[逐語 ≥1], source_ref, confidence:0..1, review_status}

entry の `related` は無方向連想 (探索ヒント) であり有方向辺ではない。cycle 判定は depends_on 辺のみ。
同一入力に対し byte-identical な knowledge-graph.json を生成する (タイムスタンプ非焼込・全リストを
canonical 文字列でソートし入力順に非依存)。

永続化 owner: C08 (knowledge-relation-extractor) は幻覚防止のため read-only で辺候補 JSON を返すのみ。
呼び出し側 (skill) がその候補を eval-log 等へ materialize し、本 script を `--merge-relations CANDIDATE`
で起動する。merge は canonical key (source_id, target_id, relation_type) で冪等: 既存辺は evidence/
confidence/review_status を含め保持し (human review 済み status を候補で上書きしない=first-write-wins)、
未知 key の候補のみ append する。同じ候補を二度 merge しても knowledge-relations.json は byte-identical で
不変。merge は atomic で、検証 PASS 時のみ relations と graph の双方を書き、FAIL 時は双方とも書かない
(壊れた辺・循環を永続化しない)。

dangling (endpoint の entry 不在) だけは violation でなく縮退: entry 削除で dangling 化した辺が
graph 再生成を恒久ブロックしないよう、該当辺を knowledge-relations-quarantine.json へ canonical key で
冪等退避 (first-write-wins) し WARN を出し、残辺で検証・生成を続行する。quarantine 後の残グラフに対する
fail-closed 性 (violation 時は一切書かない・cycle 検査等) は従来通り維持する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
GENERATOR = "validate-knowledge-graph.py"
RELATIONS_FILENAME = "knowledge-relations.json"
QUARANTINE_FILENAME = "knowledge-relations-quarantine.json"
DEFAULT_GRAPH_FILENAME = "knowledge-graph.json"

ALLOWED_RELATIONS = ("depends_on", "supports", "contradicts", "derived_from")
DAG_RELATION = "depends_on"
EDGE_FIELDS = ("source_id", "target_id", "relation_type", "evidence", "source_ref", "confidence", "review_status")

# entry ファイル走査から除外する派生/管理ファイル。加えて entries[] 述語でも弾かれるが二重に閉じる。
DERIVED_FILENAMES = {RELATIONS_FILENAME, QUARANTINE_FILENAME, DEFAULT_GRAPH_FILENAME, "harness-artifact-graph.json"}


def _canonical(obj) -> str:
    """入力順非依存ソート用の正準シリアライズ。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def load_entries(knowledge_dir: Path) -> tuple[list[dict], list[str]]:
    """knowledge-dir 内の entry ファイル (dict かつ entries[] を持つ) を読み node と violation を返す。

    戻り値 nodes は id 昇順・各 node は {id, category, subcategory, title}。
    """
    nodes: list[dict] = []
    violations: list[str] = []
    seen: dict[str, str] = {}  # id -> file (重複検出)

    for path in sorted(knowledge_dir.glob("*.json")):
        if path.name in DERIVED_FILENAMES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            violations.append(f"entry file unreadable: {path.name}: {exc}")
            continue
        if not (isinstance(data, dict) and isinstance(data.get("entries"), list)):
            continue  # category ファイルでない (registry/router/schema 等) → skip
        category = data.get("category", "")
        subcategory = data.get("subcategory", "")
        for entry in data["entries"]:
            if not isinstance(entry, dict):
                violations.append(f"non-object entry in {path.name}")
                continue
            eid = entry.get("id")
            if not isinstance(eid, str) or not eid:
                violations.append(f"entry without valid id in {path.name}")
                continue
            if eid in seen:
                violations.append(f"duplicate node id {eid} ({seen[eid]} と {path.name})")
                continue
            seen[eid] = path.name
            nodes.append(
                {
                    "id": eid,
                    "category": category if isinstance(category, str) else "",
                    "subcategory": subcategory if isinstance(subcategory, str) else "",
                    "title": entry.get("title", "") if isinstance(entry.get("title", ""), str) else "",
                }
            )

    nodes.sort(key=lambda n: n["id"])
    return nodes, violations


def load_relations(relations_path: Path) -> tuple[list, str, list[str]]:
    """knowledge-relations.json を読み (edges, status, violations) を返す。

    status: "absent" | "loaded"。不在は空辺 (violation なし)。存在時のみ形状を検証する。
    """
    if not relations_path.exists():
        return [], "absent", []
    try:
        data = json.loads(relations_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [], "malformed", [f"relations file unreadable: {relations_path.name}: {exc}"]

    if isinstance(data, list):
        return data, "loaded", []
    if isinstance(data, dict):
        edges = data.get("edges", data.get("relations", []))
        if isinstance(edges, list):
            return edges, "loaded", []
    return [], "malformed", [f"relations file shape invalid (list か edges[]/relations[] を持つ dict が必要): {relations_path.name}"]


def load_candidate_edges(candidate_path: Path) -> tuple[list, list[str]]:
    """--merge-relations CANDIDATE を読み (edges, violations) を返す。

    list か edges[]/relations[] を持つ dict を受ける (knowledge-relations.json と同形状)。
    解析不能・形状不正は violation とし、呼び出し側が exit1 で差し戻す (壊れた候補を merge しない)。
    ファイル不在は main が exit2 (usage) で先に弾く前提。
    """
    try:
        data = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [], [f"merge 候補ファイル解析不能: {candidate_path.name}: {exc}"]
    if isinstance(data, list):
        return data, []
    if isinstance(data, dict):
        edges = data.get("edges", data.get("relations", []))
        if isinstance(edges, list):
            return edges, []
    return [], [f"merge 候補ファイル形状不正 (list か edges[]/relations[] を持つ dict が必要): {candidate_path.name}"]


def _relation_key(edge: dict) -> tuple[str, str, str]:
    """merge/dedup の canonical key。同一 (source_id, target_id, relation_type) を同一辺とみなす。"""
    return (str(edge.get("source_id")), str(edge.get("target_id")), str(edge.get("relation_type")))


def merge_relations(existing: list, candidate: list) -> tuple[list[dict], int, int]:
    """existing へ candidate を canonical key で冪等 merge する (first-write-wins)。

    既存辺 (同一 key) は evidence/confidence/review_status を含め一切上書きしない (human review 済み
    review_status を候補で潰さないため)。未知 key の候補のみ append する。戻り値 (merged, added, kept)
    の merged は canonical key 昇順で決定論。同じ候補の再 merge は added=0 で不変 (冪等)。
    """
    merged: dict[tuple[str, str, str], dict] = {}
    for e in existing:
        if isinstance(e, dict):
            merged.setdefault(_relation_key(e), e)
    kept = len(merged)
    added = 0
    for e in candidate:
        if not isinstance(e, dict):
            continue
        key = _relation_key(e)
        if key not in merged:
            merged[key] = e
            added += 1
    ordered = [merged[key] for key in sorted(merged)]
    return ordered, added, kept


def partition_dangling(edges: list, node_ids: set[str]) -> tuple[list, list[dict]]:
    """endpoint 不在 (dangling) の辺を quarantine 対象として分離する。

    quarantine 対象 = 構造的には辺の体裁 (非空 str の source_id/target_id・許可 relation_type・
    非 self-loop) を満たすが、endpoint のどちらかが entry 不在の辺。entry 削除で dangling 化した
    正常辺を hard-fail (恒久ブロック) にせず退避するための縮退であり、構造不正な辺はここで
    分離せず validate_edges の violation (fail-closed) に残す。戻り値 (kept, quarantined)。
    """
    kept: list = []
    quarantined: list[dict] = []
    for edge in edges:
        if (
            isinstance(edge, dict)
            and isinstance(edge.get("source_id"), str) and edge["source_id"]
            and isinstance(edge.get("target_id"), str) and edge["target_id"]
            and edge.get("relation_type") in ALLOWED_RELATIONS
            and edge["source_id"] != edge["target_id"]
            and (edge["source_id"] not in node_ids or edge["target_id"] not in node_ids)
        ):
            quarantined.append(edge)
        else:
            kept.append(edge)
    quarantined.sort(key=_relation_key)
    return kept, quarantined


def load_quarantine(quarantine_path: Path) -> list:
    """既存 quarantine ストアを読む。不在・解析不能は空扱い (quarantine は復旧用の退避先であり
    本体検証を巻き込まない)。"""
    if not quarantine_path.exists():
        return []
    try:
        data = json.loads(quarantine_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("edges"), list):
        return data["edges"]
    return []


def validate_edges(edges: list, node_ids: set[str]) -> tuple[list[dict], list[str]]:
    """C08 辺を検証し正準化した edge 群と violation 一覧を返す。

    正準 edge は EDGE_FIELDS のみ・structural に有効かつ非 dangling・非 self-loop のものだけ。
    cycle 判定は本関数を通過した depends_on 辺のみを対象にする。
    """
    canonical_edges: list[dict] = []
    violations: list[str] = []

    for idx, edge in enumerate(edges):
        tag = f"edge[{idx}]"
        if not isinstance(edge, dict):
            violations.append(f"{tag}: 辺が object でない")
            continue

        src = edge.get("source_id")
        tgt = edge.get("target_id")
        rel = edge.get("relation_type")
        ref = f"{tag} ({src} -{rel}-> {tgt})"

        structural_ok = True
        if not isinstance(src, str) or not src:
            violations.append(f"{tag}: source_id 欠落/不正")
            structural_ok = False
        if not isinstance(tgt, str) or not tgt:
            violations.append(f"{tag}: target_id 欠落/不正")
            structural_ok = False
        if rel not in ALLOWED_RELATIONS:
            violations.append(f"{tag}: relation_type 不正 ({rel!r} ∉ {ALLOWED_RELATIONS})")
            structural_ok = False

        # (b) self-loop 禁止
        if isinstance(src, str) and isinstance(tgt, str) and src and tgt and src == tgt:
            violations.append(f"{ref}: self-loop 禁止")
            structural_ok = False

        # (a) 参照整合 = source_id/target_id が entry 実在
        if isinstance(src, str) and src and src not in node_ids:
            violations.append(f"{ref}: dangling source_id (entry 不在)")
            structural_ok = False
        if isinstance(tgt, str) and tgt and tgt not in node_ids:
            violations.append(f"{ref}: dangling target_id (entry 不在)")
            structural_ok = False

        # (d) evidence≥1 (各要素が非空 str)
        evidence = edge.get("evidence")
        if not (isinstance(evidence, list) and evidence and all(isinstance(x, str) and x.strip() for x in evidence)):
            violations.append(f"{ref}: evidence は非空 str を1件以上必要")

        # (e) confidence 0..1 (bool 除外)
        conf = edge.get("confidence")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
            violations.append(f"{ref}: confidence は 0..1 の数値が必要 (got {conf!r})")

        # (f) review_status 必須
        status = edge.get("review_status")
        if not (isinstance(status, str) and status.strip()):
            violations.append(f"{ref}: review_status 必須")

        # source_ref (C08 schema の必須項目)
        source_ref = edge.get("source_ref")
        if not (isinstance(source_ref, str) and source_ref.strip()):
            violations.append(f"{ref}: source_ref 必須")

        if structural_ok:
            canonical_edges.append(
                {
                    "source_id": src,
                    "target_id": tgt,
                    "relation_type": rel,
                    "evidence": evidence if isinstance(evidence, list) else [],
                    "source_ref": source_ref if isinstance(source_ref, str) else "",
                    "confidence": float(conf) if isinstance(conf, (int, float)) and not isinstance(conf, bool) else None,
                    "review_status": status if isinstance(status, str) else "",
                }
            )

    canonical_edges.sort(key=_canonical)
    return canonical_edges, violations


def detect_cycle(canonical_edges: list[dict]) -> list[str] | None:
    """depends_on 辺のみで有向循環を検出する。循環があれば経路 (node id 列) を返す。

    supports/contradicts/derived_from と related は cycle 対象外。
    """
    adj: dict[str, list[str]] = {}
    for e in canonical_edges:
        if e["relation_type"] != DAG_RELATION:
            continue
        adj.setdefault(e["source_id"], []).append(e["target_id"])
    for k in adj:
        adj[k].sort()  # 決定論的な探索順

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []

    def dfs(u: str) -> list[str] | None:
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, ()):
            c = color.get(v, WHITE)
            if c == GRAY:
                # v から現在ノードまでが循環
                start = stack.index(v)
                return stack[start:] + [v]
            if c == WHITE:
                found = dfs(v)
                if found is not None:
                    return found
        stack.pop()
        color[u] = BLACK
        return None

    for node in sorted(adj.keys()):
        if color.get(node, WHITE) == WHITE:
            cycle = dfs(node)
            if cycle is not None:
                return cycle
    return None


def build_associations(entries_nodes: list[dict], knowledge_dir: Path, node_ids: set[str]) -> tuple[list[dict], int]:
    """entry の `related` から無方向連想を構築する。dangling は drop し件数を返す (非致命)。"""
    pairs: set[tuple[str, str]] = set()
    dropped = 0
    for path in sorted(knowledge_dir.glob("*.json")):
        if path.name in DERIVED_FILENAMES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not (isinstance(data, dict) and isinstance(data.get("entries"), list)):
            continue
        for entry in data["entries"]:
            if not isinstance(entry, dict):
                continue
            src = entry.get("id")
            related = entry.get("related")
            if not (isinstance(src, str) and src in node_ids and isinstance(related, list)):
                continue
            for tgt in related:
                if not isinstance(tgt, str):
                    dropped += 1
                    continue
                if tgt not in node_ids or tgt == src:
                    dropped += 1
                    continue
                pairs.add(tuple(sorted((src, tgt))))
    associations = [{"a": a, "b": b, "kind": "related"} for a, b in sorted(pairs)]
    return associations, dropped


def build_graph(nodes: list[dict], edges: list[dict], associations: list[dict]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "association_count": len(associations),
        "nodes": nodes,
        "edges": edges,
        "associations": associations,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate-knowledge-graph.py",
        description="knowledge 依存グラフの決定論再生成 + 検証ゲート (C06)",
    )
    parser.add_argument("--knowledge-dir", required=True, help="knowledge/ ディレクトリ")
    parser.add_argument("--graph-out", default=None, help="出力先 (既定 <knowledge-dir>/knowledge-graph.json)")
    parser.add_argument(
        "--merge-relations", default=None, metavar="CANDIDATE_FILE",
        help="C08 が返した辺候補 JSON を knowledge-relations.json へ冪等 merge してから検証する",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)  # 引数不正は argparse が exit2

    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.is_dir():
        print(f"usage error: --knowledge-dir が存在しない: {knowledge_dir}", file=sys.stderr)
        return 2

    graph_out = Path(args.graph_out) if args.graph_out else knowledge_dir / DEFAULT_GRAPH_FILENAME
    relations_path = knowledge_dir / RELATIONS_FILENAME
    quarantine_path = knowledge_dir / QUARANTINE_FILENAME

    violations: list[str] = []

    nodes, node_violations = load_entries(knowledge_dir)
    violations.extend(node_violations)
    node_ids = {n["id"] for n in nodes}

    if not nodes:
        print(f"no knowledge entries found in {knowledge_dir}", file=sys.stderr)
        return 1

    # --merge-relations: C08 候補を knowledge-relations.json へ冪等 merge してから検証する。
    # merge は atomic = 検証 PASS 時のみ relations を書く。merge 入力 (既存 relations か候補) が
    # 壊れていれば何も書かず exit1 で差し戻す。
    merged_relations: list[dict] | None = None
    merge_added = merge_kept = 0
    if args.merge_relations:
        candidate_path = Path(args.merge_relations)
        if not candidate_path.is_file():
            print(f"usage error: --merge-relations ファイルが存在しない: {candidate_path}", file=sys.stderr)
            return 2
        existing_edges, _existing_status, existing_violations = load_relations(relations_path)
        candidate_edges, candidate_violations = load_candidate_edges(candidate_path)
        merge_input_violations = existing_violations + candidate_violations
        if merge_input_violations:
            print(f"VIOLATION: merge 入力不正 ({len(merge_input_violations)} 件)", file=sys.stderr)
            for v in merge_input_violations:
                print(f"  - {v}", file=sys.stderr)
            return 1
        merged_relations, merge_added, merge_kept = merge_relations(existing_edges, candidate_edges)
        raw_edges = merged_relations
        rel_status = "merged"
    else:
        raw_edges, rel_status, rel_violations = load_relations(relations_path)
        violations.extend(rel_violations)

    # dangling (endpoint 不在) は violation でなく quarantine 縮退: entry 削除で辺が graph 再生成を
    # 恒久ブロックしないよう分離し、残辺で検証・生成を続行する。永続化 (退避先追記 + relations から
    # 除去) は fail-closed 維持のため検証 PASS 時のみ行う。
    raw_edges, quarantined = partition_dangling(raw_edges, node_ids)
    if merged_relations is not None:
        merged_relations = raw_edges
    if quarantined:
        print(
            f"WARN: dangling 辺 {len(quarantined)} 件を {QUARANTINE_FILENAME} へ退避する "
            "(endpoint の entry 不在・graph から除外)", file=sys.stderr,
        )
        for e in quarantined:
            print(f"  - {e['source_id']} -{e['relation_type']}-> {e['target_id']}", file=sys.stderr)

    canonical_edges, edge_violations = validate_edges(raw_edges, node_ids)
    violations.extend(edge_violations)

    # (c) depends_on DAG 非循環
    cycle = detect_cycle(canonical_edges)
    if cycle is not None:
        violations.append("depends_on 循環検出: " + " -> ".join(cycle))

    associations, dropped_related = build_associations(nodes, knowledge_dir, node_ids)

    if violations:
        print(f"VIOLATION: knowledge graph 検証失敗 ({len(violations)} 件)", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print(f"nodes={len(nodes)} edges(raw)={len(raw_edges)} relations={rel_status}", file=sys.stderr)
        return 1

    # 検証 PASS。quarantine 発生時は退避先へ canonical key で冪等追記する (first-write-wins・
    # 再実行で byte-identical)。fail-closed 維持のため FAIL 時はここへ到達せず何も書かない。
    if quarantined:
        merged_quarantine, _q_added, _q_kept = merge_relations(load_quarantine(quarantine_path), quarantined)
        quarantine_payload = json.dumps(
            {"schema_version": SCHEMA_VERSION, "edges": merged_quarantine},
            ensure_ascii=False, indent=2, sort_keys=True,
        ) + "\n"
        try:
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            quarantine_path.write_text(quarantine_payload, encoding="utf-8")
        except OSError as exc:
            print(f"usage error: {QUARANTINE_FILENAME} 書込失敗: {quarantine_path}: {exc}", file=sys.stderr)
            return 2

    # merge した場合、および quarantine で辺を除去した場合のみ辺ストアを canonical 書込する
    # (atomic: 検証を通った辺だけ永続化。quarantine 辺は knowledge-relations.json から除去される)。
    if merged_relations is not None or quarantined:
        store_edges = merged_relations if merged_relations is not None else sorted(raw_edges, key=_relation_key)
        relations_payload = json.dumps(
            {"schema_version": SCHEMA_VERSION, "edges": store_edges},
            ensure_ascii=False, indent=2, sort_keys=True,
        ) + "\n"
        try:
            relations_path.parent.mkdir(parents=True, exist_ok=True)
            relations_path.write_text(relations_payload, encoding="utf-8")
        except OSError as exc:
            print(f"usage error: knowledge-relations.json 書込失敗: {relations_path}: {exc}", file=sys.stderr)
            return 2

    graph = build_graph(nodes, canonical_edges, associations)
    payload = json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        graph_out.parent.mkdir(parents=True, exist_ok=True)
        graph_out.write_text(payload, encoding="utf-8")
    except OSError as exc:
        print(f"usage error: graph-out 書込失敗: {graph_out}: {exc}", file=sys.stderr)
        return 2

    # 退化セルの可視化: 辺 0 本の graph は zero-hit 正常だが consult 価値が出ないため WARN で表面化する
    # (exit0 維持・stderr のみ。既存 corpus への初回適用は RUNBOOK の初回 edge backfill 手順)。
    if graph["edge_count"] == 0:
        print(
            "WARN: knowledge graph の edges=0 (辺が1本も無い退化グラフ)。"
            "既存 corpus への初回適用は RUNBOOK の「初回 edge backfill」手順を参照",
            file=sys.stderr,
        )
    if rel_status == "absent":
        print(f"note: {relations_path.name} が無いため空辺として扱った (edges=0)")
    if rel_status == "merged":
        print(f"note: 辺候補を merge した (added={merge_added} kept={merge_kept}) -> {relations_path.name}")
    if dropped_related:
        print(f"note: 未解決の related 参照を {dropped_related} 件 drop した (無方向連想・非致命)")
    print(
        "OK: knowledge-graph validated "
        f"(nodes={graph['node_count']} edges={graph['edge_count']} "
        f"associations={graph['association_count']}) -> {graph_out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
