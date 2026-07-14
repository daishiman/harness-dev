#!/usr/bin/env python3
# /// script
# name: summarize-task-progress
# purpose: task-graph 駆動 build の進捗を task-state.json (producer component C16 shape) から集計する read-only consumer (TG-C05)。by_state 集計・completion_rate・blocked_tasks・route-build-report (PR#70 route-*.json) 件数を出し、実行時停滞 (plan component C12) を detect_stall で機械判定する。stall 出力は evaluated フラグ付き構造化 ({"evaluated":true,"stalled":...,"diagnosis":[...],"has_spec_gap":...} / 入力不足時は {"evaluated":false}) で「評価して非停滞」と「未評価」を区別する。各停滞診断を kind (spec-gap=仕様不備で外ループ合流 / build-failure=producer blocked 由来で人手救済 / origin-failure=自身が route 実失敗の起点) に分類し has_spec_gap (spec-gap のみ true) を返して TG-C06 (/capability-build dispatcher) の外ループ合流分岐へ渡す。resolve_build_dir は TG-C02 (sync-task-state) の SSOT を import 再利用する。
# inputs:
#   - argv: [--task-state P] [--build-dir D] [--target-plugin-slug S] [--cycle-id C]
#           [--ready-batch JSON] [--task-graph G]
# outputs:
#   - stdout: 進捗サマリ JSON (by_state/completion_rate/blocked_tasks/route_report_count + stall)
#   - stderr: usage/IO error メッセージ
#   - exit: 0=OK / 2=usage/IO error
#   - write-scope: なし (read-only。task-state/route-report/task-graph を読むのみ)
# contexts: [C, E]
# network: false
# write-scope: none (read-only)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-graph 駆動 build の進捗集計 + 実行時停滞検出 (TG-C05・read-only)。

design: plugin-plans/harness-creator/phase-05-implementation.md (TG-C05/plan component C12・F9)。
summarize() は task-state.json (producer component C16 shape) の nodes.state を by_state へ集計し
completion_rate/blocked_tasks を導出、build_dir 配下 route-*.json (PR#70 route-build-report)
の件数を read-only で数える (既存フィールドは一切読み書きしない)。
detect_stall() は dispatcher の ready_batch が空・running 0・未完了残存の停滞を機械判定し、
常に評価済み構造 {"evaluated": True, "stalled": bool, "diagnosis": [...], "has_spec_gap": bool}
を返す (非停滞は stalled=False・diagnosis=[])。ready_batch/task-graph 欠落で評価不能な場合は
main() が {"evaluated": False} を出し、「評価して非停滞」と「未評価」の三値曖昧を排する。
各 blocked/pending node の depends_on/consumes 先と自身の blocked_reason を検査して診断を
kind 分類する:
  - エッジ先 node が task-graph.nodes に不在 → spec-gap (仕様不備=外ループで task-graph 改善)
  - producer node が blocked (blocked_reason 由来) → build-failure (仕様は正・上流失敗の巻添え)
  - 自身が blocked_reason=origin-failure → origin-failure (route 実失敗の起点そのもの。
    producer が全て done でも診断対象にし、停滞の根を diagnosis から直接特定できるようにする)
has_spec_gap は spec-gap のみ true (外ループ合流トリガの意味を不変に保つ)。
起点特定 (F9): 各 blocked node の第一級 field blocked_reason (origin-failure|propagated) を
診断文へ併記し、propagated の連鎖を辿って origin-failure の route を特定できるようにする。
resolve_build_dir は TG-C02 (sync-task-state) の SSOT を import 再利用し独自導出しない。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_STATE_KEYS = ("pending", "running", "done", "blocked")


# ── 兄弟 script ローダ (ハイフン名 module の importlib ロード・TG-C02 SSOT 再利用) ──
def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# TG-C02 (sync-task-state) の resolve_build_dir を SSOT として import (独自 path 導出はしない)。
_sts = _load_sibling("sync-task-state")
resolve_build_dir = _sts.resolve_build_dir


# ── 進捗集計 ──────────────────────────────────────────────────────────────────
def summarize(task_state: dict, build_dir: Path) -> dict:
    """task-state.json の nodes.state を集計し進捗サマリ dict を返す (入力不変・read-only)。

    - by_state: pending/running/done/blocked の 4 値カウント (未知 state は無視)。
    - completion_rate: done / total (total=len(nodes)・total=0 は 0.0)。
    - blocked_tasks: state==blocked の node id 一覧。
    - route_report_count/route_reports: build_dir 配下 route-*.json (PR#70 route-build-report)
      の件数と filename 一覧 (存在確認・件数集計のみ・ファイル中身は読まない read-only)。
    """
    nodes = task_state.get("nodes", []) or []
    by_state = {k: 0 for k in _STATE_KEYS}
    for n in nodes:
        s = n.get("state")
        if s in by_state:
            by_state[s] += 1
    total = len(nodes)
    completion_rate = (by_state["done"] / total) if total else 0.0
    blocked_tasks = [n.get("id") for n in nodes if n.get("state") == "blocked"]

    build_dir = Path(build_dir)
    route_reports = sorted(p.name for p in build_dir.glob("route-*.json"))

    return {
        "total": total,
        "by_state": by_state,
        "completion_rate": completion_rate,
        "blocked_tasks": blocked_tasks,
        "route_report_count": len(route_reports),
        "route_reports": route_reports,
    }


# ── producer エッジ (depends_on/consumes) の逆引き ────────────────────────────
def _producers_of(task_graph: dict) -> dict[str, set[str]]:
    """consumer(下流) node id → producer(上流) node id 集合 を返す。

    depends_on は consumer task→producer task、consumes は artifact→consumer task を
    produces で producer task へ逆引きする。
    """
    prod, _ = _sts.resolve_dependency_producers(task_graph)
    return prod


# ── 実行時停滞検出 (plan component C12・外ループ合流の機械判定) ────────────────
def detect_stall(
    by_state: dict, ready_batch: list, task_graph: dict, task_state: dict
) -> dict:
    """ready_batch 空・running 0・未完了残存の停滞を判定し診断を kind 分類して返す。

    停滞条件: ready_batch == [] かつ (pending+running+blocked) > 0 かつ running == 0。
    戻り値は常に評価済み構造 {"evaluated": True, "stalled": bool, "diagnosis": [...],
    "has_spec_gap": bool} (非停滞は stalled=False・diagnosis=[]。未評価=入力不足は本関数を
    呼ばず main() が {"evaluated": False} を出す — 三値 None の曖昧さを排する)。
    停滞時は各 blocked/pending node の自身の blocked_reason と depends_on/consumes 先を検査:
      - 自身が blocked_reason=origin-failure → kind="origin-failure" (route 実失敗の起点そのもの。
        producer が全て done でも診断対象。state node の route_report があれば併記し人手救済導線に)。
      - エッジ先 node id が task_graph.nodes に不在 → kind="spec-gap" (仕様不備=外ループ合流)。
        spec-gap 診断は message 文字列に加え emit-discovered-task (TG-C04) 引数を機械導出できる
        構造化フィールド missing_dependency_id / stalled_task_phase_ref / stalled_task_write_scope
        を携帯する (TG-C06 が手 parse せず emit へ橋渡しできる=stall→emit seam 機械化)。
      - producer node が blocked (blocked_reason 由来) → kind="build-failure" (上流失敗の巻添え)。
        producer_id / producer_blocked_reason を構造化併記し失敗起点の特定を助ける。
    各 blocked node の第一級 field blocked_reason を診断文へ併記する (F9・伝播連鎖の起点特定)。
    has_spec_gap は spec-gap のみ true (外ループ合流トリガの意味は不変)。
    """
    not_stalled = {
        "evaluated": True, "stalled": False, "diagnosis": [], "has_spec_gap": False,
    }
    if ready_batch != []:
        return not_stalled
    stuck = (
        by_state.get("pending", 0)
        + by_state.get("running", 0)
        + by_state.get("blocked", 0)
    )
    if stuck <= 0 or by_state.get("running", 0) != 0:
        return not_stalled

    state_map = {n.get("id"): n.get("state") for n in task_state.get("nodes", []) or []}
    reason_map = {
        n.get("id"): n.get("blocked_reason") for n in task_state.get("nodes", []) or []
    }
    report_map = {
        n.get("id"): n.get("route_report") for n in task_state.get("nodes", []) or []
    }
    graph_node_ids = {n.get("id") for n in task_graph.get("nodes", []) or []}
    producers, dependency_issues = _sts.resolve_dependency_producers(task_graph)

    diagnosis: list[dict] = []
    # consumes artifact producer 不在等は「依存なし」ではなく、外ループへ返す
    # spec-gap として構造化診断する (fail-closed)。
    for issue in dependency_issues:
        consumer = issue.get("consumer_task_id")
        node = next(
            (n for n in task_graph.get("nodes", []) or [] if n.get("id") == consumer),
            {},
        )
        diagnosis.append({
            "task_id": consumer,
            "message": _sts.format_dependency_issue(issue),
            "kind": "spec-gap",
            "missing_dependency_id": issue.get("producer_task_id") or issue.get("artifact_id"),
            "missing_artifact_id": issue.get("artifact_id"),
            "stalled_task_phase_ref": node.get("phase_ref"),
            "stalled_task_write_scope": node.get("write_scope"),
        })
    for node in sorted(task_graph.get("nodes", []) or [], key=lambda x: str(x.get("id"))):
        nid = node.get("id")
        state = state_map.get(nid, node.get("state", "pending"))
        if state not in ("blocked", "pending"):
            continue
        self_reason = reason_map.get(nid) if state == "blocked" else None
        self_suffix = f" [self blocked_reason={self_reason}]" if self_reason else ""
        if self_reason == "origin-failure":
            # 第3分類: 自身が失敗起点。producer 全 done でも停滞の根を diagnosis から
            # 直接特定できるようにする (従来は巻添え側の build-failure しか出ず根が不可視)。
            entry: dict = {
                "task_id": nid,
                "message": f"{nid} 自身が blocked (blocked_reason=origin-failure) — route 実失敗の起点",
                "kind": "origin-failure",
            }
            route_report = report_map.get(nid)
            if route_report is not None:
                entry["route_report"] = route_report
            diagnosis.append(entry)
        for pid in sorted(producers.get(nid, set()), key=str):
            if pid not in graph_node_ids:
                diagnosis.append({
                    "task_id": nid,
                    "message": (
                        f"{nid} は依存先 {pid} が task-graph 上に不在のため実行不能"
                        f"{self_suffix}"
                    ),
                    "kind": "spec-gap",
                    # emit-discovered-task (TG-C04) の引数を TG-C06 が機械導出できるよう構造化する
                    # (message 文字列の手 parse を排し AI/機械の境界を確定・seam 機械化)。
                    # discovering_task_id=task_id / 欠落上流=missing_dependency_id /
                    # proposed_node の phase_ref・write_scope の既定値供給元 = 停滞 node の属性。
                    "missing_dependency_id": pid,
                    "stalled_task_phase_ref": node.get("phase_ref"),
                    "stalled_task_write_scope": node.get("write_scope"),
                })
            elif state_map.get(pid) == "blocked":
                p_reason = reason_map.get(pid)
                diagnosis.append({
                    "task_id": nid,
                    "message": (
                        f"{nid} は producer {pid} が blocked "
                        f"(blocked_reason={p_reason}) のため実行不能{self_suffix}"
                    ),
                    "kind": "build-failure",
                    # 人手救済導線: 失敗起点 producer とその blocked_reason を構造化併記 (F9)。
                    "producer_id": pid,
                    "producer_blocked_reason": p_reason,
                })
    return {
        "evaluated": True,
        "stalled": True,
        "diagnosis": diagnosis,
        "has_spec_gap": any(d["kind"] == "spec-gap" for d in diagnosis),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="summarize-task-progress.py",
        description="task-graph 駆動 build の進捗集計 + 実行時停滞検出 (read-only)。",
    )
    p.add_argument("--task-state", default=None, help="省略時 <build-dir>/task-state.json")
    p.add_argument("--build-dir", default=None, help="省略時 resolve_build_dir(...) 導出")
    p.add_argument("--target-plugin-slug", default=None)
    p.add_argument("--cycle-id", default=None)
    p.add_argument("--ready-batch", default=None, help="dispatcher が転送する TG-C01 直近 ready_batch (JSON)")
    p.add_argument("--task-graph", default=None, help="停滞診断用 task-graph.json")
    return p


def _resolve_paths(args) -> tuple[Path, Path] | None:
    """(build_dir, state_path) を解決する。解決不能なら None を返す。"""
    if args.build_dir:
        build_dir = Path(args.build_dir)
    elif args.target_plugin_slug:
        build_dir = Path(resolve_build_dir(args.target_plugin_slug, args.cycle_id))
    elif args.task_state:
        build_dir = Path(args.task_state).parent
    else:
        return None
    state_path = Path(args.task_state) if args.task_state else build_dir / "task-state.json"
    return build_dir, state_path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse usage error / --help
        return int(exc.code) if isinstance(exc.code, int) else 2

    resolved = _resolve_paths(args)
    if resolved is None:
        print(
            "--build-dir / --target-plugin-slug / --task-state のいずれかが必須",
            file=sys.stderr,
        )
        return 2
    build_dir, state_path = resolved

    if not state_path.exists():
        print(f"task-state が存在しない: {state_path}", file=sys.stderr)
        return 2
    try:
        task_state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"task-state 読込/parse 失敗: {state_path}: {exc}", file=sys.stderr)
        return 2

    ready_batch = None
    if args.ready_batch is not None:
        try:
            ready_batch = json.loads(args.ready_batch)
        except json.JSONDecodeError as exc:
            print(f"--ready-batch は JSON 文字列: {exc}", file=sys.stderr)
            return 2

    task_graph = None
    if args.task_graph is not None:
        try:
            task_graph = json.loads(Path(args.task_graph).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"task-graph 読込/parse 失敗: {args.task_graph}: {exc}", file=sys.stderr)
            return 2

    summary = summarize(task_state, build_dir)
    if ready_batch is not None and task_graph is not None:
        stall = detect_stall(summary["by_state"], ready_batch, task_graph, task_state)
    else:
        # 入力不足 (--ready-batch/--task-graph 欠落) は「評価して非停滞」と区別できる
        # 未評価マーカーを出す (null は両者を混同する三値曖昧ゆえ廃止)。
        stall = {"evaluated": False}
    summary["stall"] = stall

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
