#!/usr/bin/env python3
# /// script
# name: build-parity-manifest
# purpose: Materialize the C28 parity manifest as a provenance-bearing snapshot of the canonical dev-graph.
# inputs: ["argv: --repo-root PATH [--graph FILE] [--out FILE]"]
# outputs: ["stdout: JSON receipt", "file: parity manifest under repository eval-log"]
# requires-python = ">=3.10"
# dependencies: ["_common.py"]
# contexts: [A, B, C, E]
# network: false
# write-scope: parity manifest under repository eval-log only
# ///
"""parity manifest (C28 `--parity-manifest` の入力) を canonical graph から生成する単一 writer。

manifest は「graph 側の事実」を tracker 突合用に切り出した snapshot であり、tracker
(Beads) を一切読まない。読むと「graph と tracker が一致しているか」を検査するはずの
C28 が、自分で作った答え合わせ用紙を採点することになり、parity 検査が空虚になる。
したがって本 script は read-only な graph 投影に徹し、突合は C28、鮮度判定は C16 が担う。

契約の正本は references/execution-tracker-contract.md (parity manifest の由来必須化)。
必須フィールドは `generated_at` / `source_graph_digest` / `nodes[]` / `graph_node_ids[]` で、
`source_graph_digest` は C16 schedule-graph.py `_canonical_digest` と同一式でなければ
ならない (不一致は恒久 stale)。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない (子の起動にも -B を渡す)。
sys.dont_write_bytecode = True

from _common import ContractError, atomic_json, contained, dump, load_json, repository_eval_root  # noqa: E402

SCHEMA_VERSION = "1.1"
# 既定出力先。eval-log/ 直下ではなく skill 名のサブディレクトリ配下に置く。
# 実体は毎回作り直す揮発 snapshot で git 追跡しない。
DEFAULT_OUT = "eval-log/dev-graph/run-dev-graph-schedule/parity-manifest.json"

# C28 bd-bridge.py `_ready_with_parity` の status_map が受理する graph status の exact-set。
# ここに無い値を manifest へ書いた node は ready_set ではなく conflicts へ落ちる。
# bd-bridge.py 側と一致必須 (test_build_parity_manifest.py が両者の一致を固定する)。
BRIDGE_STATUS_MAP: dict[str, str] = {
    "draft": "open",
    "active": "open",
    "blocked": "blocked",
    "done": "closed",
    "closed": "closed",
    "tombstoned": "closed",
}


def _node_id(node: dict[str, Any]) -> str:
    value = node.get("graph_node_id") or node.get("id")
    if not isinstance(value, str) or not value:
        raise ContractError("graph node is missing graph_node_id")
    return value


def _canonical_digest(value: Any) -> str:
    """graph の意味的 digest。C16 schedule-graph.py `_canonical_digest` と同一式。

    整形差 (空白・key 順) で stale 判定が揺れないよう、バイト列 digest ではなく
    canonical JSON の digest を使う。式がずれると C16 が常に stale と判定し、
    schedule が恒久停止するため、回帰テストで両者の一致を固定している。
    """
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _generated_at() -> str:
    """契約の `YYYY-MM-DDThh:mm:ssZ` 形式で生成時刻を返す。

    _common.utc_now() は小数秒を含む。C28 の正規表現は小数秒を許容するが、契約表が
    示す表記へ寄せておくほうが人間の目視突合と将来の厳格化に耐える。
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mvp_fit(node: dict[str, Any]) -> str | None:
    """mvp_alignment.mvp_fit を fail-closed で読む (表示順整合用)。

    fallback はキー欠落 / null のみ。enum 外の非 null を黙って未設定へ丸めると、
    C28 側の per-candidate fail-closed 検査 (bd-bridge.py) が空振りする。
    """
    alignment = node.get("mvp_alignment")
    if alignment is None:
        return None
    if not isinstance(alignment, dict):
        raise ContractError(f"{_node_id(node)}: mvp_alignment must be an object or null")
    fit = alignment.get("mvp_fit")
    if fit is None:
        return None
    if fit not in {"direct", "enabling", "deferred"}:
        raise ContractError(f"{_node_id(node)}: unsupported mvp_fit {fit!r}")
    return fit


def graph_status_for_manifest(node: dict[str, Any]) -> str:
    """manifest へ記録する `graph_status` を返す。status による選別は行わない。

    呼び出し側の前提: この関数へ来るのは `tracker_binding == "beads"` かつ
    `beads_linkage.bd_issue_id` を持つ node だけ。戻り値はそのまま manifest の
    `graph_status` になり、C28 が `BRIDGE_STATUS_MAP` 経由で「Beads 側の期待 status」へ
    写して `verify_parity` に渡す。

    **status で間引かない理由 (この関数の設計判断)**:

    1. 間引きは依存側を巻き添えにする。C28 は manifest entry の `depends_on` に
       manifest 内に居ない graph_node_id が 1 つでもあれば、その候補を
       `parity manifest dependency lacks a Beads linkage` で conflicts へ落とす
       (bd-bridge.py `_ready_with_parity`)。`done`/`closed` を「終わったから不要」と
       省くと、それを依存に持つ `active` node が道連れで ready-set から消える。
    2. 間引きは下流の理由コードを嘘にする。manifest に無い bd 候補は
       `parity_manifest_missing` (= graph 管理下の取りこぼし・C03 sync 案件) として
       報告される。意図的に外した node がこの札を付けられると、owner を誤らせる。
    3. 間引く実利が無い。schedule 対象の絞り込みは C16 `is_schedulable`
       (`status == "active"` 等) が graph 側の事実として独立に行う。manifest は
       「突合台帳」であって「作業候補リスト」ではない。

    したがって選別せず、`BRIDGE_STATUS_MAP` が写せない status だけを fail-closed で弾く。
    schema の status enum が拡張されたのに C28 が追随していない場合、ここで停止するのが
    正しい (黙って除外すると 2. の誤った札が付くだけで、停止より発見が遅れる)。
    """
    status = node.get("status")
    if not isinstance(status, str) or not status:
        raise ContractError(f"{_node_id(node)}: graph node is missing status")
    if status not in BRIDGE_STATUS_MAP:
        raise ContractError(
            f"{_node_id(node)}: graph status {status!r} is not accepted by the C28 status map "
            f"({sorted(BRIDGE_STATUS_MAP)}); extend bd-bridge.py status_map and "
            "BRIDGE_STATUS_MAP together before landing the new status"
        )
    return status


def _entries(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """beads 束縛 node を manifest entry へ投影し、落ちた node を理由つきで残す。"""
    included: dict[str, str] = {}
    seen_issues: set[str] = set()
    unlinked: list[dict[str, Any]] = []
    candidates: list[tuple[str, dict[str, Any], str]] = []

    for node in sorted(nodes, key=_node_id):
        node_id = _node_id(node)
        if node.get("tracker_binding") != "beads":
            continue
        issue_id = (node.get("beads_linkage") or {}).get("bd_issue_id")
        if not isinstance(issue_id, str) or not issue_id:
            # 起票前 (beads_linkage=null) の node。manifest へは載せられないが、
            # 黙って消すと「なぜ ready に出ないか」が下流から見えなくなる。
            unlinked.append({"graph_node_id": node_id, "reason": "beads_linkage_absent"})
            continue
        if issue_id in seen_issues:
            # C28 は重複 bd_issue_id を manifest 側の破損として拒否する。生成時点で
            # 同じ判定を先に下し、壊れた manifest を書き出さない。
            raise ContractError(f"duplicate bd_issue_id across graph nodes: {issue_id}")
        seen_issues.add(issue_id)
        included[node_id] = issue_id
        candidates.append((node_id, node, graph_status_for_manifest(node)))

    entries: list[dict[str, Any]] = []
    dependency_gaps: list[dict[str, Any]] = []
    for node_id, node, status in candidates:
        depends_on = node.get("depends_on", [])
        if not isinstance(depends_on, list) or any(not isinstance(dep, str) or not dep for dep in depends_on):
            raise ContractError(f"{node_id}: depends_on must be a string[]")
        escaped = sorted(dep for dep in depends_on if dep not in included)
        if escaped:
            # manifest へは事実どおり載せる。C28 が per-candidate conflict として落とし、
            # ここでも生成時点で可視化する。落として黙らせると parity_manifest_missing と
            # 区別できなくなり、対処 owner を誤らせる。
            dependency_gaps.append({
                "graph_node_id": node_id, "bd_issue_id": included[node_id],
                "dependencies_outside_manifest": escaped,
            })
        entries.append({
            "graph_node_id": node_id,
            "bd_issue_id": included[node_id],
            "graph_status": status,
            "depends_on": sorted(depends_on),
            "mvp_fit": _mvp_fit(node),
        })
    return {"nodes": entries, "unlinked": unlinked, "dependency_gaps": dependency_gaps}


def build(graph: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """canonical graph から (manifest, 診断) を作る。graph は読むだけで変更しない。"""
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if not isinstance(nodes, list) or not all(isinstance(node, dict) for node in nodes):
        raise ContractError("canonical graph must contain nodes[] objects")
    if len({_node_id(node) for node in nodes}) != len(nodes):
        raise ContractError("graph nodes require unique graph_node_id")
    projected = _entries(nodes)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _generated_at(),
        "source_graph_digest": _canonical_digest(graph),
        "nodes": projected["nodes"],
        # graph に実在する node id の全集合。`nodes[]` (= beads 束縛済みの投影) との差は
        # 「graph には居るが起票前 / linkage 欠落」であり、C28 が unmapped の理由を
        # `graph_node_missing` (graph から消えた = C02 案件) と `parity_manifest_missing`
        # (graph には居るのに投影から漏れた = C03 案件) へ切り分けるために要る。
        # これが無いと両者が同じ札になり、消えた node を指す orphan external_ref が
        # 「sync すれば直る」と誤認され、何度 sync しても消えない警告として常駐する。
        "graph_node_ids": sorted({_node_id(node) for node in nodes}),
    }
    diagnostics = {
        "node_count": len(projected["nodes"]),
        "graph_node_count": len(nodes),
        "unlinked": projected["unlinked"],
        "dependency_gaps": projected["dependency_gaps"],
    }
    return manifest, diagnostics


def _graph_path(root: Path, explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit)
        candidate = candidate if candidate.is_absolute() else root / candidate
        return contained(candidate, root, must_exist=True)
    config = load_json(root / ".dev-graph" / "config.json")
    raw = (config.get("local_state") or {}).get("graph") if isinstance(config, dict) else None
    if not isinstance(raw, str) or not raw:
        raise ContractError("build-parity-manifest requires --graph or config local_state.graph")
    return contained(root / raw, root, must_exist=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--graph")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    root = Path(args.repo_root).expanduser().resolve(strict=True)
    graph_path = _graph_path(root, args.graph)
    # 出力先は repository の eval-log 配下だけに限る。graph や tracker state を
    # 上書きできる path を受け取ると、read-only な投影 script が書込経路になる。
    eval_root = repository_eval_root(root)
    target = Path(args.out)
    target = target if target.is_absolute() else root / target
    target = contained(target, eval_root, must_exist=False)

    # C02 writer (build-graph-node.py / register-package.py) は graph を atomic replace で
    # 書くため、読み手は lock を取らなくても途中状態を見ない。残る競合は「読んでいる間に
    # 別 revision へ差し替わる」ことだけなので、前後のバイト列を比べて検出し、
    # 古い graph から作った manifest を書き出さない。
    before = graph_path.read_bytes()
    manifest, diagnostics = build(json.loads(before.decode("utf-8")))
    if graph_path.read_bytes() != before:
        raise ContractError("parity manifest generation observed a changing canonical graph")
    atomic_json(target, manifest)

    dump({
        "ok": True,
        "manifest_path": target.relative_to(root).as_posix(),
        "generated_at": manifest["generated_at"],
        "source_graph_digest": manifest["source_graph_digest"],
        "graph_sha256": hashlib.sha256(before).hexdigest(),
        "write_count": 1,
        **diagnostics,
    })
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
