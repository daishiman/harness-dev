#!/usr/bin/env python3
# /// script
# name: validate-knowledge-graph
# version: 0.1.0
# purpose: 知識依存グラフ (goal-spec C13/C14)・必須情報カタログ (C16)・doctrine anchor 写像 (C15) を検証する決定論ゲート。4 profile: knowledge=depends_on precedence DAG (A depends_on B なら B before A)+循環/dangling/root到達性/孤立node と refines(有向精緻化)/conflicts_with(対称非順序)型則、required-info=item最低形状/domain被覆/収集順序/coverage certificate/missing_effect、doctrine=concern_id 一意性+各 concern の authority 非空 (authority は concern 間で共有可・種類数は不問)+全category→concern写像全射+orphan concern+未帰属pending例外、cross=taxonomy/doctrine/required-info の語彙横断整合 (category 集合一致・concern 部分集合・domain 被覆)。本 gate は well-formedness と順序決定論のみを保証し、辺やカタログ内容の意味妥当性は content-review/human の責務。
# inputs:
#   - argv: --profile knowledge|required-info|doctrine --input FILE [--order]  |  --profile cross --taxonomy FILE --doctrine FILE --required-info FILE
# outputs:
#   - stdout: profile 別 JSON (knowledge={status,topo_order} / required-info={status,collection_order,coverage_certificate} / doctrine={status,category_concern_mapping,concern_authorities,pending_exceptions} / cross={status,shared_categories,extra_domains})。--order 指定時は順序配列のみ。
#   - stderr: violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""知識グラフ / 必須情報カタログ / doctrine anchor registry の 3 profile を機械検証する。

profile は相互排他 (1 起動 1 profile)。C01 (run-system-spec-elicit) の R5-decision-guide と
C03 (run-system-spec-compile) の R2-render が同一 JSON 位相順を消費するための決定論ゲートで、
形状・辺型則・写像全射のみを検証し、意味 (知識内容が正しいか) の判定は content-review/human が担う。

辺の意味論 (knowledge / required-info 共通の depends_on):
  A depends_on B  ==>  B が前提。位相順で B を A より先に出す (precedence DAG)。同順位は id 昇順。
  refines          ==>  有向の精緻化 (A refines B = A は B の詳細化)。非循環。位相には参加しない。
  conflicts_with   ==>  対称な非順序制約 (A conflicts_with B なら B conflicts_with A も必須)。位相不参加。
"""
from __future__ import annotations

import argparse
import heapq
import json
import sys
from pathlib import Path

PROFILES = ("knowledge", "required-info", "doctrine", "cross")

# required-info item の最低形状 (goal-spec C16)
REQUIRED_INFO_FIELDS = (
    "item_id",
    "domain",
    "concern",
    "question",
    "required_reason",
    "evidence_required",
    "depends_on",
    "required_when",
    "completion_rule",
    "missing_effect",
    "serves_goals",
)
MISSING_EFFECTS = ("block", "degrade", "warn")
APPROVAL_STATES = ("approved", "pending", "rejected")


# ── 共通グラフユーティリティ ─────────────────────────────────────────────────
def _detect_cycle(nodes: list[str], adj: dict[str, list[str]]) -> list[str]:
    """adj (node -> 依存先/精緻化先) の有向グラフから循環路を 1 本返す (無ければ [])。

    反復 DFS (明示スタック) で実装し、再帰上限に依存しない (深い連鎖 600+ でも
    RecursionError で門番が沈黙せず正しく VIOLATION/PASS を返す・A3 if思考の破壊試験対策)。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    for root in sorted(nodes):
        if color[root] != WHITE:
            continue
        path: list[str] = [root]           # 現在たどっている GRAY パス
        stack = [(root, iter(adj.get(root, [])))]
        color[root] = GRAY
        while stack:
            u, it = stack[-1]
            advanced = False
            for v in it:
                if v not in color:
                    continue               # dangling は別途検出済み
                if color[v] == GRAY:
                    i = path.index(v)
                    return path[i:] + [v]
                if color[v] == WHITE:
                    color[v] = GRAY
                    path.append(v)
                    stack.append((v, iter(adj.get(v, []))))
                    advanced = True
                    break
            if not advanced:
                color[u] = BLACK
                path.pop()
                stack.pop()
    return []


def _topo_order(nodes: list[str], depends_on: dict[str, list[str]]) -> list[str]:
    """Kahn 法 O(V+E) で位相順を返す。A depends_on B なら B before A。同順位は id 昇順 (決定論)。

    in-degree キュー (id 昇順 heap) で ready を取り出すため計算量は O((V+E) log V)。
    呼出し時点で dangling/循環は検出済み前提 (depends_on の参照先は全て nodes 内)。
    """
    indeg = {n: 0 for n in nodes}
    dependents: dict[str, list[str]] = {n: [] for n in nodes}
    for n in nodes:
        for b in depends_on.get(n, []):
            if b in indeg:
                indeg[n] += 1
                dependents[b].append(n)
    heap = sorted(n for n in nodes if indeg[n] == 0)
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        cur = heapq.heappop(heap)
        order.append(cur)
        for d in dependents[cur]:
            indeg[d] -= 1
            if indeg[d] == 0:
                heapq.heappush(heap, d)
    return order


# ── profile: knowledge ───────────────────────────────────────────────────────
def validate_knowledge(data: dict) -> tuple[list[str], dict]:
    findings: list[str] = []
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return (["knowledge: entries が空/非配列 (空カタログ拒否)"], {})

    ids: list[str] = []
    seen = set()
    depends_on: dict[str, list[str]] = {}
    refines: dict[str, list[str]] = {}
    conflicts: dict[str, list[str]] = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            findings.append(f"entries[{i}]: オブジェクトでない")
            continue
        kid = e.get("knowledge_id")
        if not kid:
            findings.append(f"entries[{i}]: knowledge_id 欠落")
            continue
        if kid in seen:
            findings.append(f"knowledge_id={kid!r} が重複")
            continue
        seen.add(kid)
        ids.append(kid)
        depends_on[kid] = list(e.get("depends_on", []) or [])
        refines[kid] = list(e.get("refines", []) or [])
        conflicts[kid] = list(e.get("conflicts_with", []) or [])

    if findings:
        return findings, {}

    idset = set(ids)
    # dangling + self 参照 (全辺型)
    for kid in ids:
        for rel, adj in (("depends_on", depends_on), ("refines", refines), ("conflicts_with", conflicts)):
            for tgt in adj[kid]:
                if tgt == kid:
                    findings.append(f"{kid}: {rel} が自己参照")
                elif tgt not in idset:
                    findings.append(f"{kid}: {rel} の参照先 {tgt!r} が存在しない (dangling)")

    # conflicts_with 対称性
    for kid in ids:
        for tgt in conflicts[kid]:
            if tgt in idset and kid not in conflicts.get(tgt, []):
                findings.append(
                    f"{kid} conflicts_with {tgt} だが {tgt} 側に対称な conflicts_with {kid} が無い (非対称)"
                )

    # depends_on 循環
    cyc = _detect_cycle(ids, depends_on)
    if cyc:
        findings.append(f"depends_on に循環: {' -> '.join(cyc)}")
    # refines 循環 (有向精緻化は非循環)
    rcyc = _detect_cycle(ids, refines)
    if rcyc:
        findings.append(f"refines に循環: {' -> '.join(rcyc)}")

    # 孤立 node: どの辺型にも in/out で参加しない完全に切り離された node
    referenced: set[str] = set()
    for kid in ids:
        for adj in (depends_on, refines, conflicts):
            referenced.update(adj[kid])
    for kid in ids:
        has_out = bool(depends_on[kid] or refines[kid] or conflicts[kid])
        if not has_out and kid not in referenced:
            findings.append(f"{kid}: 孤立 node (どの typed 辺にも参加していない)")

    if findings:
        return findings, {}

    # root 到達性: root = depends_on 空。root から dependent 方向 (逆 depends_on) BFS で全 node 到達必須。
    dependents: dict[str, list[str]] = {k: [] for k in ids}
    for kid in ids:
        for b in depends_on[kid]:
            dependents[b].append(kid)
    roots = sorted(k for k in ids if not depends_on[k])
    if not roots:
        findings.append("depends_on に root (依存なし node) が存在しない (全 node が依存を持つ = 循環の疑い)")
        return findings, {}
    reached = set(roots)
    queue = list(roots)
    while queue:
        cur = queue.pop(0)
        for nxt in dependents[cur]:
            if nxt not in reached:
                reached.add(nxt)
                queue.append(nxt)
    unreachable = sorted(set(ids) - reached)
    if unreachable:
        findings.append(f"root から到達できない node: {unreachable}")
        return findings, {}

    topo = _topo_order(ids, depends_on)
    return [], {"status": "ok", "topo_order": topo}


# ── profile: required-info ───────────────────────────────────────────────────
def validate_required_info(data: dict) -> tuple[list[str], dict]:
    findings: list[str] = []
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return (["required-info: items が空/非配列 (空カタログ拒否)"], {})

    in_scope = data.get("in_scope_domains")
    if not isinstance(in_scope, list) or not in_scope:
        findings.append("required-info: in_scope_domains が空/非配列 (domain 被覆床が定義されていない)")
        in_scope = []

    na_domains = data.get("na_domains", []) or []
    na_approved = {}
    for na in na_domains:
        if isinstance(na, dict) and na.get("domain"):
            na_approved[na["domain"]] = na.get("approval_state")
            if na.get("approval_state") not in APPROVAL_STATES:
                findings.append(f"na_domains[{na['domain']}]: approval_state 不正/欠落")
            if not na.get("reason"):
                findings.append(f"na_domains[{na['domain']}]: reason 欠落")

    ids: list[str] = []
    seen = set()
    depends_on: dict[str, list[str]] = {}
    domains_with_item: set[str] = set()
    blocking_items: list[str] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            findings.append(f"items[{i}]: オブジェクトでない")
            continue
        iid = it.get("item_id")
        if not isinstance(iid, str) or not iid.strip():
            # 非文字列 id は seen/sorted/heap で型混在 TypeError を招くため早期に拒否。
            findings.append(f"items[{i}]: item_id が空/欠落/非文字列")
            continue
        if iid in seen:
            findings.append(f"item_id={iid!r} が重複")
            continue
        seen.add(iid)
        ids.append(iid)
        # 最低形状: 全必須フィールド存在。型ごとに検査を分ける (boolean/list の
        # 正当な falsy 値=False/[] を「欠落」と誤検出しないため truthiness では判定しない)。
        for field in REQUIRED_INFO_FIELDS:
            missing = field not in it or it.get(field) is None
            val = it.get(field)
            if field == "depends_on":
                if missing or not isinstance(val, list):
                    findings.append(f"items[{iid}]: depends_on が配列でない/欠落")
            elif field == "serves_goals":
                if not isinstance(val, list) or not val:
                    findings.append(f"items[{iid}]: serves_goals が空 (goal trace 欠落)")
            elif field == "evidence_required":
                if missing or not isinstance(val, bool):
                    findings.append(f"items[{iid}]: evidence_required は boolean 必須 (false も正当値)")
            elif missing or not isinstance(val, str) or not val.strip():
                # 文字列必須フィールドは型も対称に検査する (非str値=最低形状違反。
                # depends_on/serves_goals/evidence_required の型検査と非対称にしない)。
                findings.append(f"items[{iid}]: 必須フィールド {field} が空/欠落/非文字列")
        depends_on[iid] = list(it.get("depends_on", []) or [])
        me = it.get("missing_effect")
        if me and me not in MISSING_EFFECTS:
            findings.append(f"items[{iid}]: missing_effect={me!r} が enum {MISSING_EFFECTS} 外")
        if me == "block":
            blocking_items.append(iid)
        dom = it.get("domain")
        if dom:
            domains_with_item.add(dom)

    if findings:
        return findings, {}

    # depends_on dangling + 循環
    idset = set(ids)
    for iid in ids:
        for tgt in depends_on[iid]:
            if tgt == iid:
                findings.append(f"{iid}: depends_on が自己参照")
            elif tgt not in idset:
                findings.append(f"{iid}: depends_on 参照先 {tgt!r} が存在しない (dangling)")
    if findings:
        return findings, {}
    cyc = _detect_cycle(ids, depends_on)
    if cyc:
        return [f"required-info depends_on に循環: {' -> '.join(cyc)}"], {}

    # domain 被覆床: 全 in_scope_domain に 1 件以上 or 承認済 N/A
    uncovered = []
    for dom in in_scope:
        if dom in domains_with_item:
            continue
        if na_approved.get(dom) == "approved":
            continue
        uncovered.append(dom)
    if uncovered:
        findings.append(f"in_scope_domain の被覆欠落 (item も承認済N/Aも無い): {sorted(uncovered)}")
        return findings, {}

    collection_order = _topo_order(ids, depends_on)
    certificate = {
        "in_scope_domains": sorted(in_scope),
        "domains_covered_by_item": sorted(domains_with_item),
        "na_approved_domains": sorted(d for d, s in na_approved.items() if s == "approved"),
        "total_items": len(ids),
        "blocking_items": sorted(blocking_items),
    }
    return [], {
        "status": "ok",
        "collection_order": collection_order,
        "coverage_certificate": certificate,
    }


# ── profile: doctrine ────────────────────────────────────────────────────────
def validate_doctrine(data: dict) -> tuple[list[str], dict]:
    findings: list[str] = []
    concerns = data.get("concerns")
    if not isinstance(concerns, list) or not concerns:
        return (["doctrine: concerns が空/非配列"], {})

    # concern authority 一意性: 各 concern_id は 1 回・authority 非空
    concern_authority: dict[str, str] = {}
    for i, c in enumerate(concerns):
        if not isinstance(c, dict):
            findings.append(f"concerns[{i}]: オブジェクトでない")
            continue
        cid = c.get("concern_id")
        auth = c.get("authority")
        if not cid:
            findings.append(f"concerns[{i}]: concern_id 欠落")
            continue
        if cid in concern_authority:
            findings.append(f"concern_id={cid!r} が重複 (1 concern 1 authority 違反)")
            continue
        if not auth:
            findings.append(f"concerns[{cid}]: authority 欠落 (1 concern 1 正本)")
        concern_authority[cid] = auth

    if findings:
        return findings, {}

    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        findings.append("doctrine: categories (in-scope 一覧) が空/非配列")
        return findings, {}

    mapping = data.get("category_concern_map", {})
    if not isinstance(mapping, dict):
        findings.append("doctrine: category_concern_map が object でない")
        return findings, {}

    pending_raw = data.get("pending_exceptions", []) or []
    pending_by_cat: dict[str, dict] = {}
    for i, p in enumerate(pending_raw):
        if not isinstance(p, dict) or not p.get("category"):
            findings.append(f"pending_exceptions[{i}]: category 欠落")
            continue
        cat = p["category"]
        pending_by_cat[cat] = p
        for f in ("owner", "reason", "approval_state"):
            if not p.get(f):
                findings.append(f"pending_exceptions[{cat}]: {f} 欠落")
        if p.get("approval_state") and p["approval_state"] not in APPROVAL_STATES:
            findings.append(f"pending_exceptions[{cat}]: approval_state 不正")

    # 写像全射: 全 category が concern へ写像 (>=1 existing concern) or well-formed pending 例外
    for cat in categories:
        mapped = mapping.get(cat)
        if mapped:
            if not isinstance(mapped, list) or not mapped:
                findings.append(f"category_concern_map[{cat}]: concern list が空/非配列")
                continue
            for cid in mapped:
                if cid not in concern_authority:
                    findings.append(f"category_concern_map[{cat}]: 未定義 concern {cid!r} を参照 (dangling)")
        elif cat in pending_by_cat:
            continue  # 例外形状は上で検査済
        else:
            findings.append(f"category {cat!r} が concern へ未写像かつ pending 例外にも無い (全射違反)")

    # mapping に categories 外の余剰キーがあれば dangling
    for cat in mapping:
        if cat not in categories:
            findings.append(f"category_concern_map に in-scope 外の category {cat!r} (categories と不整合)")

    # orphan concern: 定義済みだがどの category からも写像されない concern (knowledge の
    # 孤立 node 検出と対称・A3 抽象化 finding)。全 concern は最低 1 category に使われる必要がある。
    used_concerns: set[str] = set()
    for cat in categories:
        for cid in mapping.get(cat, []):
            used_concerns.add(cid)
    orphan_concerns = sorted(set(concern_authority) - used_concerns)
    if orphan_concerns:
        findings.append(f"orphan concern (どの category からも写像されない): {orphan_concerns}")

    if findings:
        return findings, {}

    # 未承認 pending は compile 保留シグナル (surface のみ・形状は valid)
    pending_out = [
        {
            "category": cat,
            "owner": p.get("owner"),
            "reason": p.get("reason"),
            "approval_state": p.get("approval_state"),
        }
        for cat, p in sorted(pending_by_cat.items())
    ]
    result = {
        "status": "ok",
        "category_concern_mapping": {cat: mapping.get(cat, []) for cat in sorted(categories)},
        "concern_authorities": dict(sorted(concern_authority.items())),
        "pending_exceptions": pending_out,
    }
    return [], result


# ── profile: cross (語彙横断整合) ────────────────────────────────────────────
def validate_cross(taxonomy: dict, doctrine: dict, required_info: dict) -> tuple[list[str], dict]:
    """taxonomy / doctrine / required-info の語彙 SSOT を横断照合する (A3 メタ/ブレスト finding)。

    3 profile が相互排他 (1 起動 1 profile) だと語彙一致検査の置き場が消えるため、
    複数カタログを同時ロードする専用 profile として cross を設ける:
      1. taxonomy.categories と doctrine.categories の集合一致 (category SSOT の二重管理 drift 防止)。
      2. required-info の各 item.concern が doctrine.concerns に実在 (cross-catalog dangling 防止)。
      3. required-info.in_scope_domains を category 由来 (shared) と派生 (extra・例: api) に分類し報告。
    """
    findings: list[str] = []

    tax_raw = taxonomy.get("categories")
    if not isinstance(tax_raw, list) or not tax_raw:
        findings.append("cross: taxonomy.categories が空/非配列")
        return findings, {}
    tax_cats: set[str] = set()
    for c in tax_raw:
        if isinstance(c, dict) and c.get("id"):
            tax_cats.add(c["id"])
        elif isinstance(c, str):
            tax_cats.add(c)

    doc_cats = set(doctrine.get("categories") or [])
    doc_concerns = {
        c["concern_id"]
        for c in (doctrine.get("concerns") or [])
        if isinstance(c, dict) and c.get("concern_id")
    }
    ri_items = required_info.get("items") or []
    ri_domains = set(required_info.get("in_scope_domains") or [])

    # 1. category 集合一致
    if tax_cats != doc_cats:
        findings.append(
            f"category 集合が taxonomy と doctrine で不一致 "
            f"(taxonomy のみ={sorted(tax_cats - doc_cats)} / doctrine のみ={sorted(doc_cats - tax_cats)})"
        )
    # 2. required-info concern ⊆ doctrine concerns
    ri_concerns = {i["concern"] for i in ri_items if isinstance(i, dict) and i.get("concern")}
    dangling = sorted(ri_concerns - doc_concerns)
    if dangling:
        findings.append(f"required-info item.concern が doctrine concerns に不在 (cross dangling): {dangling}")

    if findings:
        return findings, {}

    return [], {
        "status": "ok",
        "shared_categories": sorted(ri_domains & tax_cats),
        "extra_domains": sorted(ri_domains - tax_cats),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def _load(path_str: str) -> tuple[dict | None, int]:
    path = Path(path_str)
    if not path.is_file():
        print(f"入力ファイルが存在しない: {path_str}", file=sys.stderr)
        return None, 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"JSON parse 失敗: {exc}", file=sys.stderr)
        return None, 2
    if not isinstance(data, dict):
        print("入力 root が object でない", file=sys.stderr)
        return None, 2
    return data, 0


def run(profile: str, data: dict) -> tuple[list[str], dict]:
    if profile == "knowledge":
        return validate_knowledge(data)
    if profile == "required-info":
        return validate_required_info(data)
    if profile == "doctrine":
        return validate_doctrine(data)
    return ([f"未知 profile: {profile}"], {})


def _order_field(profile: str) -> str | None:
    return {"knowledge": "topo_order", "required-info": "collection_order"}.get(profile)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="知識グラフ/必須情報カタログ/doctrine registry の 4 profile 決定論検証 (goal-spec C13-C16)"
    )
    ap.add_argument("--profile", required=True, choices=PROFILES)
    ap.add_argument("--input", help="knowledge/required-info/doctrine profile 対応 JSON のパス")
    ap.add_argument("--taxonomy", help="cross profile: system-category-taxonomy.json")
    ap.add_argument("--doctrine", help="cross profile: doctrine-anchor-registry.json")
    ap.add_argument("--required-info", dest="required_info", help="cross profile: required-info-catalog.json")
    ap.add_argument(
        "--order",
        action="store_true",
        help="knowledge/required-info で順序配列のみを stdout へ出す (消費側の位相順取得用)",
    )
    args = ap.parse_args(argv)

    if args.profile == "cross":
        if not (args.taxonomy and args.doctrine and args.required_info):
            print("--profile cross には --taxonomy/--doctrine/--required-info が必須", file=sys.stderr)
            return 2
        loaded = {}
        for key, path in (("t", args.taxonomy), ("d", args.doctrine), ("r", args.required_info)):
            d, rc = _load(path)
            if rc:
                return rc
            loaded[key] = d
        findings, result = validate_cross(loaded["t"], loaded["d"], loaded["r"])
    else:
        if not args.input:
            print(f"--profile {args.profile} には --input が必須", file=sys.stderr)
            return 2
        data, rc = _load(args.input)
        if rc:
            return rc
        findings, result = run(args.profile, data)
    if findings:
        for f in findings:
            print(f"VIOLATION: {f}", file=sys.stderr)
        print(f"FAIL: {len(findings)} 件の {args.profile} profile 違反", file=sys.stderr)
        return 1

    if args.order:
        field = _order_field(args.profile)
        if field is None:
            print(f"--order は {args.profile} profile では非対応 (順序を持たない)", file=sys.stderr)
            return 2
        print(json.dumps(result.get(field, []), ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
