#!/usr/bin/env python3
# /// script
# name: schedule-graph
# purpose: Compute deterministic feature/task ready sets and non-conflicting worktree batches.
# inputs: ["argv: --graph FILE --ready-source self|bd-bridge --ready-json FILE? --leases FILE? --scope ID? --max-parallel N?"]
# outputs: ["stdout: JSON schedule (ready_set, batches, conflicts, conflict_pairs, excluded, unmapped, selection_receipt, input sha256 before/after)"]
# requires-python = ">=3.10"
# dependencies: ["../lib/schedule_graph_nodes.py", "../lib/bd_bridge_contracts.py"]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない (子の起動にも -B を渡す)。
sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from _common import ContractError, dump

# lib を毎回 exec し直す。test が本 script と ``_common`` を別インスタンスとして読み直したとき、キャッシュ済み
# lib の ContractError だけが旧世代のクラスに残り、呼出側の ``except``/``pytest.raises`` が取り逃がす。
sys.modules.pop("schedule_graph_nodes", None)
from schedule_graph_nodes import (
    ScopePath, blocking_dependencies, is_schedulable, node_id_of, overlaps, scope_paths, shared_paths, touches,
)
# MVP-first の rank は C28 が ready_set を見せる順と同じでなければならないので、定義を複製せず共有する。
# 未設定 (None) を deferred より前に置くのは、mvp_alignment を持たない既存 node を品質系の明示 task より
# 先に出し、metadata を一括で書き足さなくても従来の並びから劣化させないため。
from bd_bridge_contracts import MVP_FIT_RANK

# manage-worktree-lease.py が claim 時に expires_at 超過で expired へ倒す state と同じ集合。
# park 済み (pending_review) などは expires_at を持たないか、期限で解放されない。
EXPIRING_LEASE_STATES = {"reserving", "claimed", "in_progress", "claim_pending_local_repair"}


def lease_touches(lease: dict[str, Any], by_id: dict[Any, dict[str, Any]]) -> set[ScopePath]:
    """Return what an active lease holds: its recorded scope plus its graph node's ``resource_scope``.

    The public claim path (``/dev-graph worktree claim <id> --branch ... --session-id ...``) does not
    pass ``--resource``, so C27 records ``resource_scope: []``. Reading only the lease record let a
    candidate that touches the leased node's files into the ready set. A lease whose scope can be
    derived from neither the record nor the graph fails closed instead of conflicting with nothing.
    """
    node_id = lease.get("graph_node_id")
    held = scope_paths(lease.get("resource_scope", []), f"lease {node_id}")
    if node_id in by_id:
        held |= touches(by_id[node_id])
    if not held:
        raise ContractError(f"lease {node_id}: resource_scope is empty and the node is not in the graph")
    return held


def lease_is_active(lease: dict[str, Any], now: datetime) -> bool:
    """released/expired 以外は保持中。ただし期限で解放される state は expires_at を過ぎたら保持しない。

    C27 は期限切れを次の claim まで ``expired`` へ書き換えないため、snapshot に残る古い
    ``claimed`` が誰も作業していない scope を塞ぎ続けないよう、ここでも同じ期限を読む。
    """
    if lease.get("state") in {"released", "expired"}:
        return False
    expires = lease.get("expires_at")
    if lease.get("state") not in EXPIRING_LEASE_STATES or expires is None:
        return True
    try:
        expiry = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"lease {lease.get('graph_node_id')}: invalid expires_at {expires!r}") from exc
    if expiry.tzinfo is None:
        raise ContractError(f"lease {lease.get('graph_node_id')}: expires_at must be timezone-aware")
    return expiry > now


def _mvp_fit(node: dict[str, Any]) -> str | None:
    """mvp_alignment.mvp_fit を fail-closed で読む。fallback はキー欠落 / null のみ。

    enum 外の非 null 値を未設定 rank へ丸めると不正 metadata が黙って通る。
    validate-graph-schema.py を通った graph では到達しない防衛線として ContractError で落とす。
    """
    alignment = node.get("mvp_alignment")
    if alignment is None:
        return None
    if not isinstance(alignment, dict):
        raise ContractError(f"{node_id_of(node)}: mvp_alignment must be an object or null")
    fit = alignment.get("mvp_fit")
    if fit is None:
        return None
    if fit not in MVP_FIT_RANK:
        raise ContractError(f"{node_id_of(node)}: unsupported mvp_fit {fit!r} (expected direct|enabling|deferred)")
    return fit


def _mvp_established(by_id: dict[Any, dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, bool | None]:
    """selection_receipt に載る feature の MVP 成立状況を、``--scope`` ではなく graph 全体から決める。

    成立は feature の graph 上の事実で、閲覧範囲で真偽が変わると同一入力の plan が揺れる。
    direct task が 0 件の feature を空虚な真で true と読ませないため null にする。
    載せるのは candidates の parent_feature と candidates 中の feature 自身だけ。
    """
    feature_ids: set[str] = set()
    for node in candidates:
        parent = node.get("parent_feature")
        if isinstance(parent, str) and parent:
            feature_ids.add(parent)
        if node.get("artifact_kind", node.get("kind")) == "feature":
            feature_ids.add(str(node_id_of(node)))
    result: dict[str, bool | None] = {}
    for feature_id in sorted(feature_ids):
        direct = [n for n in by_id.values() if n.get("parent_feature") == feature_id and _mvp_fit(n) == "direct"]
        result[feature_id] = all(n.get("status") in {"done", "closed"} for n in direct) if direct else None
    return result


def _deferral_reason(node: dict[str, Any], established: dict[str, bool | None]) -> str | None:
    """deferred の node だけに、繰り延べた理由を状況別の固定文で返す。"""
    if _mvp_fit(node) != "deferred":
        return None
    parent = node.get("parent_feature")
    if not isinstance(parent, str) or not parent:
        return "quality-after-mvp: parent feature なしのため mvp_established 判定対象外、繰り延べ順序のみ適用"
    state = established.get(parent)
    if state is None:
        return "quality-after-mvp: MVP 未定義 (direct task 0 件) のため繰り延べ順序のみ適用"
    if state:
        return "quality-after-mvp: parent feature の MVP 成立済み。deferred rank による繰り延べ順序のみ適用"
    return "quality-after-mvp: parent feature の MVP (direct 全件 done) が未成立のため繰り延べ"


def _selection_receipt(by_id: dict[Any, dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """候補をその順に並べた理由。既存の plan キーには触れず、キーを 1 つ足すだけにする。

    order_index は features/tasks に分ける前の candidates の通し番号。mvp_alignment の無い node も
    null で必ず載せ、判断根拠が無いことを黙って落とさない。
    """
    established = _mvp_established(by_id, candidates)
    entries: list[dict[str, Any]] = []
    for index, node in enumerate(candidates):
        fit = _mvp_fit(node)
        alignment = node.get("mvp_alignment") if isinstance(node.get("mvp_alignment"), dict) else {}
        entries.append({"graph_node_id": node_id_of(node), "artifact_kind": node.get("artifact_kind", node.get("kind")),
                        "order_index": index, "mvp_fit": fit, "sort_rank": MVP_FIT_RANK[fit],
                        "purpose": alignment.get("purpose"), "background": alignment.get("background"),
                        "rationale": alignment.get("rationale"), "deferral_reason": _deferral_reason(node, established)})
    return {"policy": "mvp-first/v1", "mvp_established": established, "entries": entries}


def _canonical_digest(value: Any) -> str:
    """graph の意味的 digest。整形差 (空白・key 順) で鮮度判定が揺れないようにする。

    build-parity-manifest.py は同じ式で `source_graph_digest` を作る。比較を単純な文字列一致に
    落とすため、式を変えるときは両方を同時に変える (test_build_parity_manifest が一致を固定する)。
    """
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha(value: bytes | None) -> str | None:
    return hashlib.sha256(value).hexdigest() if value is not None else None


def _read_json(path: Path) -> tuple[bytes, Any]:
    """入力を一度だけ bytes で読み、その bytes を digest と parse の両方に使う。"""
    try:
        raw = path.read_bytes()
        return raw, json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON {path}: {exc}") from exc


def _scope_ids(scope: str | None, by_id: dict[Any, dict[str, Any]]) -> set[Any]:
    """``--scope`` の node と、``parent_feature`` を辿ってそこへ属する node を返す。"""
    if scope is None:
        return set(by_id)
    if scope not in by_id:
        raise ContractError(f"unknown --scope graph node: {scope}")
    selected = {scope}
    changed = True
    while changed:
        changed = False
        for node_id, node in by_id.items():
            if node_id not in selected and node.get("parent_feature") in selected:
                selected.add(node_id); changed = True
    return selected


def _tracker_side_unmapped(payload: Any) -> list[dict[str, Any]]:
    """C28 が ready から落とした課題 (unmapped/conflicts) を schedule の報告へ引き継ぐ。

    ここで捨てると「tracker では ready だが graph と対応しない課題」が最終報告に現れない。
    判断はしないが必ず見せる。
    """
    if not isinstance(payload, dict):
        return []
    carried: list[dict[str, Any]] = []
    for key in ("unmapped", "conflicts"):
        rows = payload.get(key)
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                carried.append({**row, "reason": row.get("reason") or f"tracker_{key}", "source": "bd-bridge"})
    return carried


def _ready_entries(payload: Any) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    raw = payload.get("ready_set", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw, list): raise ContractError("bd ready payload must contain ready_set[]")
    mapped: dict[str, dict[str, Any]] = {}
    unmapped = _tracker_side_unmapped(payload)
    for item in raw:
        if not isinstance(item, dict):
            unmapped.append({"value": item, "reason": "not_an_object", "source": "schedule-graph"}); continue
        external = item.get("external_ref")
        if not isinstance(external, str) or not external:
            unmapped.append({**item, "reason": "missing_external_ref", "source": "schedule-graph"}); continue
        if external in mapped:
            # 同じ node を指す entry が 2 つあると、どちらの parity を信じたかが入力順で変わる。
            raise ContractError(f"duplicate external_ref in Beads ready payload: {external}")
        mapped[external] = item
    return mapped, unmapped


def _payload_decision(node_id: Any, node: dict[str, Any], entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """bd-bridge mode で依存を満たした node を ready に入れない理由を返す (入れるなら None)。

    ``beads`` は C28 の ready entry があり、edge parity が確認済みで、その entry が見た status と
    ``depends_on`` が現 graph と一致するときだけ ready にする。``github``/``none`` は Beads の
    ready を持たないので graph だけで決める。binding の無い node は entry の有無だけを見る。
    """
    binding = node.get("tracker_binding")
    if binding in {"github", "none"}:
        return None
    if binding not in {None, "beads"}:
        # repo-config-default は永続 node に残らない前提の値で、解決前の binding で推薦しない。
        raise ContractError(f"{node_id}: unresolved tracker_binding {binding!r}")
    if entry is None:
        return {"graph_node_id": node_id, "tracker_binding": binding, "reason": "ready_payload_entry_absent",
                "source": "schedule-graph"}
    if binding is None:
        return None
    parity = entry.get("edge_parity")
    observed_depends_on = entry.get("graph_depends_on")
    if (isinstance(parity, dict) and parity.get("confirmed") is True
            and entry.get("graph_status") == node.get("status")
            and isinstance(observed_depends_on, list)
            and sorted(observed_depends_on, key=str) == sorted(node.get("depends_on", []), key=str)):
        return None
    return {"graph_node_id": node_id, "bd_issue_id": entry.get("bd_issue_id"), "tracker_binding": binding,
            "reason": "beads_parity_stale_or_unconfirmed",
            "expected_status": node.get("status"), "observed_status": entry.get("graph_status"),
            "expected_depends_on": node.get("depends_on", []), "observed_depends_on": observed_depends_on,
            "observed_edge_parity": parity, "source": "schedule-graph"}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--graph", required=True)
    parser.add_argument("--ready-source", choices=("self", "bd-bridge"), default="self")
    parser.add_argument("--ready-json"); parser.add_argument("--leases")
    parser.add_argument("--scope", help="feature (or node) id; schedule only it and the nodes under its parent_feature chain")
    parser.add_argument("--max-parallel", type=int, help="upper bound on the size of each batch")
    args = parser.parse_args()
    if args.max_parallel is not None and args.max_parallel < 1: raise ContractError("--max-parallel must be at least 1")
    if args.ready_source == "bd-bridge" and not args.ready_json: raise ContractError("--ready-source bd-bridge requires --ready-json")
    graph_path = Path(args.graph)
    ready_path = Path(args.ready_json) if args.ready_source == "bd-bridge" else None
    lease_path = Path(args.leases) if args.leases and Path(args.leases).exists() else None

    graph_before, data = _read_json(graph_path)
    nodes = data.get("nodes", []) if isinstance(data, dict) else data
    if not isinstance(nodes, list): raise ContractError("graph nodes must be an array")
    ids = Counter(node_id_of(n) for n in nodes if isinstance(n, dict))
    if duplicated := sorted(str(x) for x, count in ids.items() if count > 1):
        # by_id would keep only the last node per id, so a blocked twin could hide behind a ready one.
        raise ContractError(f"duplicate graph node ids: {duplicated}")
    by_id = {node_id_of(n): n for n in nodes if isinstance(n, dict)}
    done = {node_id for node_id, node in by_id.items() if node.get("status") in {"done", "closed"}}
    selected = _scope_ids(args.scope, by_id)
    graph_digest = _canonical_digest(data)

    tracker_before: bytes | None = None
    ready_by_id: dict[str, dict[str, Any]] = {}
    unmapped: list[dict[str, Any]] = []
    parity_provenance: Any = None
    if ready_path is not None:
        tracker_before, payload = _read_json(ready_path)
        ready_by_id, unmapped = _ready_entries(payload)
        parity_provenance = payload.get("parity_provenance") if isinstance(payload, dict) else None
        if parity_provenance is not None:
            # node 単位の parity は manifest に載った node しか見ない。manifest 生成後に足された/消された
            # node はそこでは捕まらないため、由来が付いているときは graph 全体の digest 一致を停止条件にする。
            observed = parity_provenance.get("source_graph_digest") if isinstance(parity_provenance, dict) else None
            if observed != graph_digest:
                raise ContractError(f"beads parity snapshot is stale: parity manifest source_graph_digest {observed} "
                                    f"!= current graph {graph_digest} (regenerate the parity manifest)")

    ready_ids: set[Any] = set()
    excluded: list[dict[str, Any]] = []
    for node_id in sorted(selected, key=str):
        node = by_id[node_id]
        if not is_schedulable(node): continue
        if blockers := blocking_dependencies(node, by_id, done):
            excluded.append({"graph_node_id": node_id, "reason": "dependency_unsatisfied",
                             "blocking_depends_on": blockers, "source": "schedule-graph"}); continue
        reason = _payload_decision(node_id, node, ready_by_id.get(node_id)) if ready_path is not None else None
        if reason: excluded.append(reason)
        else: ready_ids.add(node_id)
    for external, item in ready_by_id.items():
        if external not in by_id:
            unmapped.append({**item, "reason": "graph_node_missing", "source": "schedule-graph"})

    lease_before: bytes | None = None
    active_leases: list[dict[str, Any]] = []
    if lease_path is not None:
        lease_before, lease_data = _read_json(lease_path)
        raw_leases = lease_data.get("leases", []) if isinstance(lease_data, dict) else lease_data
        if not isinstance(raw_leases, list) or not all(isinstance(x, dict) for x in raw_leases):
            raise ContractError("lease snapshot must contain leases[] objects")
        now = datetime.now(timezone.utc)
        active_leases = [x for x in raw_leases if lease_is_active(x, now)]
    leased_ids = {x.get("graph_node_id") for x in active_leases}
    leased_touches: set[ScopePath] = set().union(*(lease_touches(x, by_id) for x in active_leases))
    lease_conflicts = {x for x in ready_ids if x in leased_ids or overlaps(touches(by_id[x]), leased_touches)}
    # 順序を決めるのはこの 1 行だけ。MVP 適合 rank が先で、同 rank は node_id の辞書順。
    # features/tasks の分割と batches() はこの順を引き継ぐ。
    candidates = [by_id[x] for x in sorted(ready_ids - lease_conflicts, key=lambda x: (MVP_FIT_RANK[_mvp_fit(by_id[x])], str(x)))]
    features = [n for n in candidates if n.get("artifact_kind", n.get("kind")) == "feature"]
    tasks = [n for n in candidates if n not in features]

    def batches(items: list[dict[str, Any]]) -> list[list[Any]]:
        result: list[list[Any]] = []
        for node in items:
            node_id = node_id_of(node); scope = touches(node)
            placed = False
            for batch in result:
                if args.max_parallel is not None and len(batch) >= args.max_parallel: continue
                occupied = set().union(*(touches(by_id[x]) for x in batch))
                if not overlaps(scope, occupied): batch.append(node_id); placed = True; break
            if not placed: result.append([node_id])
        return result
    feature_batches, task_batches = batches(features), batches(tasks)

    # batches は重なる ready node を別の batch へ分けるだけで、どれと重なったかは残らない。
    # 並列実行の判断材料として、重なりの組と共有する path を明示する。
    conflict_pairs: list[dict[str, Any]] = []
    ordered_ready = sorted(ready_ids, key=str)
    for index, left in enumerate(ordered_ready):
        for right in ordered_ready[index + 1:]:
            if overlaps(touches(by_id[left]), touches(by_id[right])):
                conflict_pairs.append({"left": left, "right": right, "kind": "ready_pair",
                                       "resources": shared_paths(touches(by_id[left]), touches(by_id[right]))})
    for node_id in sorted(lease_conflicts, key=str):
        conflict_pairs.append({"left": node_id, "right": "active-lease", "kind": "lease",
                               "resources": shared_paths(touches(by_id[node_id]), leased_touches)})

    hints = []
    for node in tasks:
        node_id = node_id_of(node)
        branch = f"devgraph/{node_id}"
        hints.append({"graph_node_id": node_id, "suggested_branch": branch,
                      "claim_command": f"/dev-graph worktree claim {node_id} --branch {branch} --session-id <session>"})

    # schedule は読取り専用の計算。計算中に入力が書き換わったなら、その推薦はどの版にも対応しない。
    graph_after = graph_path.read_bytes()
    tracker_after = ready_path.read_bytes() if ready_path is not None else None
    lease_after = lease_path.read_bytes() if lease_path is not None and lease_path.exists() else None
    if graph_after != graph_before: raise ContractError("graph changed while the schedule was computed")
    if tracker_after != tracker_before: raise ContractError("ready payload changed while the schedule was computed")
    if lease_after != lease_before: raise ContractError("lease snapshot changed while the schedule was computed")
    dump({"ready_set": {"features": [node_id_of(n) for n in features], "tasks": [node_id_of(n) for n in tasks]},
          "batches": {"features": feature_batches, "tasks": task_batches},
          "conflicts": sorted(lease_conflicts, key=str), "conflict_pairs": conflict_pairs,
          "excluded": excluded, "assignment_hints": hints, "unmapped": unmapped,
          "ready_source": args.ready_source, "scope": args.scope, "max_parallel": args.max_parallel,
          "graph_digest": graph_digest, "parity_provenance": parity_provenance, "read_only": True,
          "selection_receipt": _selection_receipt(by_id, candidates),
          "graph_sha256_before": _sha(graph_before), "graph_sha256_after": _sha(graph_after),
          "tracker_sha256_before": _sha(tracker_before), "tracker_sha256_after": _sha(tracker_after),
          "lease_sha256_before": _sha(lease_before), "lease_sha256_after": _sha(lease_after)})
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ContractError as exc: print(str(exc), file=sys.stderr); raise SystemExit(2)
