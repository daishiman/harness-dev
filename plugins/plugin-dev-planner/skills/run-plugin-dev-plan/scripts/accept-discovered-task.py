#!/usr/bin/env python3
# /// script
# name: accept-discovered-task
# purpose: build 進行中に発見された discovered-task form を producer 側で受理し、additive は即時 task-graph 反映・structural は --approved 二段受理 (fail-closed) で task-graph.json へ canonical 反映する (C5)。外ループ (spec-improvement loop) 入口として --inbox でディレクトリ一括ドレインし各 form へ status/resulting_graph_hash を書き戻す (FC-6 帰路)。
# inputs:
#   - argv (単一): --form <discovered-task.json> --graph <task-graph.json> [--approved] [-o OUT]
#   - argv (ドレイン): --inbox <discovered-tasks/ dir> --graph <task-graph.json> [--approved] [-o OUT]
# outputs:
#   - stdout: 受理サマリ JSON (単一: accepted 単発 / ドレイン: accepted[]/needs_approval[]/rejected[]/skipped[])
#   - stderr: 検証/受理エラー・structural 未承認拒否メッセージ
#   - exit: 0=OK (ドレインは needs_approval 残存でも 0=正常完了) / 1=単一 form の必須欠落|discovering_task_id 不在|structural 未承認 / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: <--out or --graph> task-graph.json (canonical 上書き) + --inbox 時は各 form の status/resulting_graph_hash 書き戻し
# dependencies: []
# requires-python: ">=3.10"
# ///
"""discovered-task form の producer 受理器 (C5・二段受理 + 外ループ inbox ドレイン)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C5)。
additive = proposed_node を即時 task-graph へ追加し derive-task-graph.canonicalize() を
再適用して単一 writer の正準形を維持する (id 重複は冪等に無視)。structural (既存エッジ
張替え/component 追加) は approved=True (CLI --approved) でない限り fail-closed 拒否する。

外ループ (spec-improvement loop) の planner 側入口: `--inbox <dir>` は consumer C04 が emit した
discovered-task inbox を決定論順 (filename 昇順) で一括ドレインし、additive を自動受理して
task-graph を累積更新、各 form へ `status`/`resulting_graph_hash` を書き戻す。書き戻しにより
consumer C08 の完了ゲート (scan_pending_discovered が status in {accepted,rejected,superseded}
を処理済とみなす) が処理済 form を素通しでき、外ループが閉じる。structural 未承認は status を
pending 据置で block 継続 (二段受理)。emit(C04)→block(C08)→drain(本 script)→再消費 の一巡。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402,F401  (frontmatter 規約の共有ローダ; 兄弟 script と同一 boilerplate)


def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む (canonicalize 共有 API)。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_dtg = _load_sibling("derive-task-graph")
_vtg = _load_sibling("validate-task-graph")

REQUIRED_FIELDS = (
    "discovering_task_id",
    "reason",
    "discovered_at_artifact",
    "proposed_node",
    "change_level",
)
CHANGE_LEVELS = ("additive", "structural")
# 外ループ完了ゲート (consumer C08) が「処理済」とみなす status 集合。
# これ以外 (pending/未設定) の form が inbox に 1 件でも残ると C08 は completed を block する。
PROCESSED_STATUSES = ("accepted", "rejected", "superseded")


def accept(form: dict, graph: dict, approved: bool = False) -> dict:
    """discovered-task form を受理し、更新後の canonical task-graph を返す。

    - 必須フィールド欠落は ValueError。
    - discovering_task_id が graph.nodes に実在しなければ ValueError。
    - change_level=="additive": proposed_node を追加し即時反映 (id 既存なら冪等に無追加)。
    - change_level=="structural": approved=True でなければ PermissionError (二段受理)。
    """
    missing = [k for k in REQUIRED_FIELDS if k not in form or form[k] is None]
    if missing:
        raise ValueError(f"discovered-task 必須フィールド欠落: {missing}")

    level = form["change_level"]
    if level not in CHANGE_LEVELS:
        raise ValueError(f"change_level は {CHANGE_LEVELS} のいずれか (received={level!r})")

    node_ids = {n.get("id") for n in graph.get("nodes", [])}
    if form["discovering_task_id"] not in node_ids:
        raise ValueError(
            f"discovering_task_id={form['discovering_task_id']!r} が task-graph の nodes に不在"
        )

    if level == "structural" and not approved:
        raise PermissionError(
            "structural change (既存エッジ張替え/component 追加) は --approved 二段受理が必須"
        )

    # graph の浅いコピー上で proposed_node を追加 (入力 graph を破壊しない)。
    updated = {
        "schema_version": graph.get("schema_version", "1.0"),
        "nodes": list(graph.get("nodes", [])),
        "edges": list(graph.get("edges", [])),
    }
    proposed = form["proposed_node"]
    proposed_id = proposed.get("id")
    existing_ids = {n.get("id") for n in updated["nodes"]}
    if proposed_id not in existing_ids:
        updated["nodes"].append(proposed)
        # 発見タスクを孤立ノードにしない (MD-2): 既定の連結辺として
        # 「発見された新タスクは、それを発見した discovering_task の後続 (depends_on)」を張る。
        # derive のエッジ方向 (from=下流/to=上流) に合わせ from=新ノード to=discovering_task。
        # これで producer validate-task-graph の orphan-0 不変条件を破らない
        # (新ノードは leaf dependent なので循環も生まない)。planner は structural 周回で張替え可。
        discovering = form["discovering_task_id"]
        # spec-gap 由来 (F4): proposed_id が discovering の *上流 producer* の場合
        # (= 既に {from=discovering, to=proposed_id} の depends_on/consumes エッジが存在し、
        # proposed_id 不在ゆえ dangling で spec-gap 停滞していた) は、逆向き
        # {from=proposed_id, to=discovering} を張ると 2-循環になり validate ゲートが rollback
        # → 自動受理不能で外ループが収束しない。この場合は既存の依存方向を尊重し auto-edge を
        # 張らない (追加した proposed_id により既存 dangling エッジがそのまま解決する)。
        proposed_is_upstream = any(
            e.get("type") in ("depends_on", "consumes")
            and e.get("from") == discovering and e.get("to") == proposed_id
            for e in updated["edges"]
        )
        if not proposed_is_upstream:
            dep_edge = {"type": "depends_on", "from": proposed_id, "to": discovering}
            if dep_edge not in updated["edges"]:
                updated["edges"].append(dep_edge)
        # 接合が密な既存兄弟との直列化 (proposed_node.couples_with・外ループ追記でも盲目並列を防ぐ)。
        # plan-time の derive は両兄弟未 build ゆえ id 昇順で対称に直列化するが、外ループの新タスクは
        # 既存兄弟が既に build 中/済ゆえ「新タスクは既存兄弟の *後*」(from=新ノード to=兄弟) が因果的に
        # 正しい (既存の統合面を観測してから新規を build)。新ノードは leaf dependent ゆえ cycle を作らず
        # additive のまま (既存ノードの依存は書き換えない)。同一 phase の兄弟のみ直列化する。
        couples = proposed.get("couples_with") or []
        proposed_phase = proposed.get("phase_ref")
        if isinstance(couples, list) and couples:
            existing_dep = {(e.get("from"), e.get("to")) for e in updated["edges"]
                            if e.get("type") == "depends_on"}
            for sib in updated["nodes"]:
                sid = sib.get("id")
                if sid == proposed_id:
                    continue
                if sib.get("entity_ref") in couples and sib.get("phase_ref") == proposed_phase:
                    if (sid, proposed_id) in existing_dep:
                        continue  # 逆向き (兄弟→新ノード) が既にあれば cycle 化するので張らない
                    if (proposed_id, sid) not in existing_dep:
                        updated["edges"].append({"type": "depends_on", "from": proposed_id, "to": sid})
                        existing_dep.add((proposed_id, sid))
    return _dtg.canonicalize(updated)


def diff_proposed_vs_existing(proposed: dict, graph: dict) -> list[str] | None:
    """proposed_node と graph 内の同 id 既存 node の field 差分を返す (既存不在なら None)。

    冪等 skip (id 既存で無追加) の際、再 emit された form の field 変更 (title/acceptance_criterion
    等) が黙って落ちるのを可視化する材料 (B1)。graph は不変のまま、両 node の key 和集合に対する
    値不一致フィールド名を昇順 list で返す (差分なしは [])。
    """
    pid = proposed.get("id")
    existing = next(
        (n for n in graph.get("nodes", []) if isinstance(n, dict) and n.get("id") == pid), None)
    if existing is None:
        return None
    keys = set(proposed) | set(existing)
    return sorted(k for k in keys if proposed.get(k) != existing.get(k))


def drain_inbox(inbox_dir: Path, graph: dict, approved: bool = False) -> tuple[dict, dict]:
    """discovered-task inbox を決定論順で一括ドレインし外ループ入口を閉じる (FC-6 帰路)。

    filename 昇順で各 *.json を走査し、status が処理済 (PROCESSED_STATUSES) の form は skip。
    未処理 form は accept() を試み:
      - 受理成功 (additive、または structural かつ approved) → graph を累積更新し form へ
        status=accepted + resulting_graph_hash を書き戻す。
      - PermissionError (structural 未承認) → status は pending 据置で書き戻さず needs_approval へ
        記録 (二段受理: 後続の --approved 周回で受理・それまで C08 が block し続ける)。
      - ValueError (必須欠落/discovering_task_id 不在等) → status=rejected + rejected_reason を
        書き戻し (恒久的に処理不能な form が block を永続化しないよう rejected 化)。

    graph は inbox 全体で 1 度だけ更新する累積更新 (form 間の id 依存は canonicalize が冪等吸収)。
    戻り値は (更新後 graph, 結果サマリ)。graph 自体の write は呼び出し側 (main) が担う。
    """
    results: dict = {"accepted": [], "needs_approval": [], "rejected": [], "skipped": []}
    original_graph = graph  # validate 失敗時に書き戻さない元 graph
    working = graph
    accepted_paths: list[tuple[Path, dict, str | None]] = []  # (path, form, node_id)
    for form_path in sorted(inbox_dir.glob("*.json")):
        try:
            form = json.loads(form_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            results["rejected"].append({"form": form_path.name, "reason": f"read/parse error: {exc}"})
            continue
        if form.get("status") in PROCESSED_STATUSES:
            results["skipped"].append({"form": form_path.name, "status": form.get("status")})
            continue
        node_id = form.get("proposed_node", {}).get("id")
        # 冪等 skip の field 差分検出 (B1): accept 前の working graph と比較する
        # (id 既存なら accept は無追加=graph 不変で、proposed の field 変更は反映されない)。
        proposed = form.get("proposed_node") if isinstance(form.get("proposed_node"), dict) else {}
        diff_fields = diff_proposed_vs_existing(proposed, working)
        try:
            working = accept(form, working, approved=approved)
        except PermissionError:
            # structural 未承認: pending 据置 (書き戻さない) → C08 が block を継続し二段受理を強制。
            results["needs_approval"].append({"form": form_path.name, "node": node_id})
            continue
        except ValueError as exc:
            form["status"] = "rejected"
            form["rejected_reason"] = str(exc)
            form_path.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results["rejected"].append({"form": form_path.name, "node": node_id, "reason": str(exc)})
            continue
        form["status"] = "accepted"
        entry = {"form": form_path.name, "node": node_id}
        if diff_fields:
            # 冪等 skip で proposed の field 変更が graph へ反映されていない (partial 反映)。
            # graph は不変のまま form へ差分一覧を書き戻し、次周回 planner の判断材料にする (B1)。
            form["reflected"] = "partial"
            form["reflected_diff_fields"] = diff_fields
            entry["reflected"] = "partial"
            entry["diff_fields"] = diff_fields
        accepted_paths.append((form_path, form, node_id))
        results["accepted"].append(entry)
    # fail-closed validate ゲート (MD-2): 受理を全て適用した *最終* graph が producer 不変条件
    # (DAG 非循環 / orphan 0 / producer 一意 / consumes 実在 / canonical) を破るなら、graph も
    # form status も一切コミットせず元 graph を返す。C08 完了ゲートが block を継続し外ループが
    # 不正 graph を書き戻せない (accept の depends_on 自動配線で additive は通常 valid・
    # structural 承認済で循環を招くケース等をここで捕捉)。
    violations = _vtg.validate(working, {}) if accepted_paths else []
    if violations:
        results["accepted"] = []
        results["validation_failed"] = violations
        for form_path, form, node_id in accepted_paths:
            results["needs_approval"].append(
                {"form": form_path.name, "node": node_id, "reason": "graph validation failed"}
            )
        return original_graph, results
    # 全 form 受理後の *最終* graph_hash を全 accepted form へ統一して焼き戻す (MD-8)。
    # form 逐次の中間 hash でなく最終 hash を焼くことで、consumer C07 の再 pin 認可述語
    # (task-state pin を新 graph_hash へ更新してよいのは、その hash が accepted form の
    # resulting_graph_hash と一致するときのみ) が最終 graph と突合できる (SS-4 provenance-gated re-pin)。
    final_hash = _dtg.graph_hash(working)
    for form_path, form, _ in accepted_paths:
        form["resulting_graph_hash"] = final_hash
        form_path.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return working, results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="accept-discovered-task.py",
        description="discovered-task form を producer 側で受理し task-graph へ canonical 反映する。",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--form", help="単一 discovered-task.json のパス")
    src.add_argument("--inbox", help="外ループ入口: discovered-tasks/ ディレクトリを一括ドレイン")
    parser.add_argument("--graph", required=True, help="task-graph.json のパス")
    parser.add_argument(
        "--approved",
        action="store_true",
        help="structural change を承認する (二段受理の第2段)",
    )
    parser.add_argument("-o", "--out", default=None, help="出力先 (既定は --graph を上書き)")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse usage error / --help
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else Path(args.graph)

    # 外ループ入口: inbox 一括ドレイン (needs_approval 残存でも exit0=ドレイン正常完了)。
    if args.inbox:
        inbox_dir = Path(args.inbox)
        if not inbox_dir.is_dir():
            print(f"inbox ディレクトリが存在しない: {inbox_dir}", file=sys.stderr)
            return 2
        updated, results = drain_inbox(inbox_dir, graph, approved=args.approved)
        out_path.write_text(_dtg.canonical_json(updated) + "\n", encoding="utf-8")
        summary = {
            "mode": "inbox",
            "accepted": results["accepted"],
            "needs_approval": results["needs_approval"],
            "rejected": results["rejected"],
            "skipped": results["skipped"],
            "graph_hash": _dtg.graph_hash(updated),
            "node_count": len(updated["nodes"]),
            "out": str(out_path),
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    # 単一 form モード (低レベルプリミティブ・従来互換: form へ status 書き戻さない)。
    try:
        form = json.loads(Path(args.form).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {exc}", file=sys.stderr)
        return 2

    try:
        updated = accept(form, graph, approved=args.approved)
    except PermissionError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"invalid discovered-task: {exc}", file=sys.stderr)
        return 1

    out_path.write_text(_dtg.canonical_json(updated) + "\n", encoding="utf-8")
    summary = {
        "accepted": True,
        "change_level": form["change_level"],
        "added_node": form["proposed_node"].get("id"),
        "node_count": len(updated["nodes"]),
        "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
