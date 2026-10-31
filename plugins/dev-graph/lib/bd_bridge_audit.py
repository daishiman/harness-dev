"""bd 起点の read-only 監査 — dangling external_ref の棚卸しと node 削除の事前 gate (import 専用 module)。

``scripts/bd-bridge.py`` の書込 op (create / update / dep-add など) が「graph → Beads へ書く」
側なのに対し、この module は **1 度も書かずに数える**側を担う。どちらの op も自動
close / detach を持たないのは、件数を揃えるために未解決課題を暗黙終了する経路を
構造的に作らないため。

  orphan_audit      全 bd issue を canonical graph と突合し、参照先の無い issue に
                    対処 owner の分かる `disposition` を付けて全件返す。
  removal_preflight graph node の物理削除が非クローズ orphan を増やさないことを、
                    人が選んだ処分が既に Beads へ反映済みかで確認する。

bd / git の実行関数は ``bd=`` ``git=`` で受け取る (scripts/bd-bridge.py 側の module
変数を呼び出し時に解決させ、test の monkeypatch を効かせるため)。

正本契約: references/execution-tracker-contract.md §10
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from pathlib import Path
from typing import Any, Callable

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _common import ContractError

from bd_bridge_contracts import (
    ORPHAN_DISPOSITIONS,
    REMOVAL_DISPOSITIONS,
    external_ref,
    rows,
)
from bd_bridge_graph import (
    graph_ids_from_source,
    graph_node_ids,
    refs_with_node,
    spec_index,
)


def orphan_disposition(spec_files: list[str], refs: list[str]) -> str:
    """orphan 1 件に付ける仕分け札を決める。

    入力:
      spec_files - 作業ツリーの content_roots で当該 graph_node_id を宣言する markdown[]
      refs       - 当該 node が graph に実在する他 ref[] (--scan-refs 未指定なら常に空)

    返り値は ORPHAN_DISPOSITIONS のいずれか。

    優先順位は「その札を見た人が次に **書き込む** か否か」で決める。

      refs あり → merge_pending
        参照先は実在する。ここで C02 build-graph-node.py を走らせると、マージで運ばれてくる同じ
        node を先回りで書くことになり graph.json が衝突する。spec 実体がローカルにも
        在る場合 (ブランチとローカル両方に居る) も同じ理由で merge_pending が勝つ。
        「待て」は取り消せるが「書いた」は取り消しに手間がかかる。

      refs 無し + spec あり → restore_node
        復元先が一意に決まる。C02 build-graph-node.py 一択で、人の判断は要らない。

      refs 無し + spec 無し → repoint_or_close
        機械には決められない。張り替えか失効かを中身から人が決める。

    refs が常に空 (--scan-refs 未指定) のときは後ろ 2 分岐だけが働き、走査を足す前の
    挙動と一致する。既定実行の意味を変えずに札を 1 つ増やすための形。
    """
    if refs:
        return "merge_pending"
    return "restore_node" if spec_files else "repoint_or_close"


def orphan_audit(
    root: Path,
    *,
    bd: Callable[..., Any],
    git: Callable[..., str],
    scan_refs: bool = False,
) -> dict[str, Any]:
    """dev-graph external_ref を持つ bd issue を canonical graph と全数突合する。

    C28 `--op ready` の `parity_manifest_missing` は「external_ref を持つのに manifest に
    対応 node が無い」だけを見るため、(1) 参照先 node が graph に実在しない dangling
    reference と (2) node は実在するのに manifest から落ちた真の取りこぼし が同じ札に
    混ざる。前者が常駐すると札が恒常的に立ち続け、後者を検出できなくなる。

    本 op は ready 候補に限らず **全 issue** を対象に (1) を切り出して数え、対処 owner が
    分かる `disposition` を付ける。ready と違って silent drop の余地を作らないため、
    closed も含め全件を返し、集計だけを status 別に分ける。
    """
    known = graph_node_ids(root)
    specs = spec_index(root)
    listed = rows(bd(["list", "--status", "all", "--limit", "10000", "--json"], cwd=root))
    referenced: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []
    for row in listed:
        raw = row.get("external_ref") or row.get("externalRef")
        # dev-graph 管轄の参照だけを対象にする。prefix の無い external_ref は
        # 契約 §10 の `external_ref_absent` (graph 管理外・対処不要) 側の事象。
        if not (isinstance(raw, str) and raw.startswith("dev-graph:")):
            continue
        node_id = external_ref(row)
        if not node_id:
            continue
        referenced.append(row)
        if node_id in known:
            continue
        orphans.append({
            "bd_issue_id": str(row.get("id") or ""),
            "graph_node_id": node_id,
            "status": str(row.get("status") or ""),
            "spec_files": specs.get(node_id, []),
        })
    # 札付けは全 orphan を集めてから一括で行う。ref 走査は ref 単位で graph を 1 回読む
    # 設計なので、行ごとに呼ぶと同じ ref を orphan の数だけ読み直すことになる。
    refs_by_node = (
        refs_with_node(root, {row["graph_node_id"] for row in orphans}, git=git) if scan_refs else {}
    )
    for row in orphans:
        row["node_in_refs"] = refs_by_node.get(row["graph_node_id"], [])
        row["disposition"] = orphan_disposition(row["spec_files"], row["node_in_refs"])
    orphans.sort(key=lambda row: (row["graph_node_id"], row["bd_issue_id"]))
    non_closed = [row for row in orphans if row["status"] != "closed"]
    by_status: dict[str, int] = {}
    for row in orphans:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {
        "graph_node_count": len(known),
        "issue_count": len(listed),
        "dev_graph_reference_count": len(referenced),
        # 走査したかを receipt に残す。未走査を「他 ref に無いことを確認済み」と読まれると、
        # merge_pending が 0 件なのは調べていないからなのか本当に無いのかが区別できない。
        "scanned_refs": scan_refs,
        "orphans": orphans,
        "orphan_summary": {
            "total": len(orphans),
            "non_closed": len(non_closed),
            "by_status": dict(sorted(by_status.items())),
            "by_disposition": {
                disposition: sum(1 for row in non_closed if row["disposition"] == disposition)
                for disposition in ORPHAN_DISPOSITIONS
            },
        },
    }


def removal_disposition_rows(manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """処分 manifest を node ID で索引化し、exact-set と重複を検証する。"""
    if manifest is None:
        return {}
    if manifest.get("schema_version") != "1.0.0":
        raise ContractError("removal disposition manifest schema_version must be 1.0.0")
    raw = manifest.get("dispositions")
    if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
        raise ContractError("removal disposition manifest requires dispositions[] objects")
    indexed: dict[str, dict[str, Any]] = {}
    for row in raw:
        node_id = row.get("graph_node_id")
        disposition = row.get("disposition")
        reason = row.get("reason")
        issue_ids = row.get("bd_issue_ids")
        if not isinstance(node_id, str) or not node_id:
            raise ContractError("removal disposition requires graph_node_id")
        if node_id in indexed:
            raise ContractError(f"duplicate removal disposition: {node_id}")
        if disposition not in REMOVAL_DISPOSITIONS:
            raise ContractError(
                "removal disposition must be one of: "
                + ", ".join(REMOVAL_DISPOSITIONS)
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ContractError(f"removal disposition requires a reason: {node_id}")
        if not isinstance(issue_ids, list) or not all(
            isinstance(issue_id, str) and issue_id for issue_id in issue_ids
        ):
            raise ContractError(f"removal disposition requires bd_issue_ids[]: {node_id}")
        if len(issue_ids) != len(set(issue_ids)):
            raise ContractError(f"duplicate bd_issue_ids in removal disposition: {node_id}")
        indexed[node_id] = row
    return indexed


def removal_preflight(
    root: Path,
    *,
    bd: Callable[..., Any],
    git: Callable[..., str],
    before_graph: str | None,
    before_ref: str | None,
    after_graph: str | None,
    after_ref: str | None,
    disposition_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    """graph 物理削除で非クローズ orphan を増やさない read-only gate。

    自動 close/detach は行わない。選択した処分が Beads の現在状態に既に反映済みかを
    確認するだけなので、未解決課題を件数のために暗黙終了する経路を持たない。
    """
    before = graph_ids_from_source(
        root, git=git, path=before_graph, ref=before_ref, label="before"
    )
    after = graph_ids_from_source(
        root,
        git=git,
        path=after_graph,
        ref=after_ref,
        label="after",
        default_current=True,
    )
    removed = sorted(before - after)
    dispositions = removal_disposition_rows(disposition_manifest)
    cancelled = sorted(
        node_id
        for node_id, row in dispositions.items()
        if row["disposition"] == "cancel_deletion"
        and node_id in before
        and node_id in after
    )
    invalid_extra = sorted(set(dispositions) - set(removed) - set(cancelled))
    if invalid_extra:
        raise ContractError(
            "removal disposition names nodes that are not removed or validly cancelled: "
            + ", ".join(invalid_extra)
        )

    listed = rows(
        bd(["list", "--status", "all", "--limit", "10000", "--json"], cwd=root)
    )
    references: dict[str, list[dict[str, str]]] = {}
    live_refs: list[tuple[str, str]] = []
    for row in listed:
        raw = row.get("external_ref") or row.get("externalRef")
        if not (isinstance(raw, str) and raw.startswith("dev-graph:")):
            continue
        node_id = external_ref(row)
        issue_id = str(row.get("id") or "")
        status = str(row.get("status") or "")
        if not node_id or not issue_id:
            continue
        references.setdefault(node_id, []).append(
            {"bd_issue_id": issue_id, "status": status}
        )
        if status != "closed":
            live_refs.append((issue_id, node_id))

    before_orphans = sorted(
        issue_id for issue_id, node_id in live_refs if node_id not in before
    )
    after_orphans = sorted(
        issue_id for issue_id, node_id in live_refs if node_id not in after
    )
    decisions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for node_id in sorted(set(removed) | set(cancelled)):
        was_removed = node_id in removed
        refs = sorted(
            references.get(node_id, []),
            key=lambda row: (row["bd_issue_id"], row["status"]),
        )
        actual_issue_ids = sorted(row["bd_issue_id"] for row in refs)
        non_closed = [row for row in refs if row["status"] != "closed"]
        requested = dispositions.get(node_id)
        disposition = requested.get("disposition") if requested else None
        declared_issue_ids = (
            sorted(requested.get("bd_issue_ids", [])) if requested else []
        )
        errors: list[str] = []
        if requested is None:
            errors.append("disposition_missing")
        elif declared_issue_ids != actual_issue_ids:
            errors.append("bd_issue_ids_mismatch")
        elif disposition == "cancel_deletion":
            if was_removed:
                errors.append("deletion_not_cancelled")
        elif disposition == "close_issue_first":
            if not refs:
                errors.append("referenced_issue_missing")
            if non_closed:
                errors.append("non_closed_reference")
        elif disposition == "detach_external_ref_first" and refs:
            errors.append("external_ref_not_detached")
        decision = {
            "graph_node_id": node_id,
            "removed": was_removed,
            "disposition": disposition,
            "reason": requested.get("reason") if requested else None,
            "references": refs,
            "non_closed_references": non_closed,
            "verified": not errors,
            "errors": errors,
        }
        decisions.append(decision)
        if errors:
            blockers.append(
                {"graph_node_id": node_id, "errors": errors}
            )

    new_orphans = sorted(set(after_orphans) - set(before_orphans))
    if new_orphans:
        blockers.append(
            {"graph_node_id": None, "errors": ["non_closed_orphan_increase"], "bd_issue_ids": new_orphans}
        )
    return {
        "allowed": not blockers,
        "write_count": 0,
        "before_node_count": len(before),
        "after_node_count": len(after),
        "removed_node_count": len(removed),
        "removed_nodes": removed,
        "disposition_exact_set": list(REMOVAL_DISPOSITIONS),
        "decisions": decisions,
        "blockers": blockers,
        "orphan_audit": {
            "before_non_closed": len(before_orphans),
            "after_non_closed": len(after_orphans),
            "new_non_closed_bd_issue_ids": new_orphans,
        },
    }
