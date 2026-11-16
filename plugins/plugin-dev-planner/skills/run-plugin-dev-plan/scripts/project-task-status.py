#!/usr/bin/env python3
# /// script
# name: project-task-status
# purpose: 三層状態モデル (task-graph.json 構造 SSOT / task-state.json consumer 単一 writer / status projection) の parity を fail-closed 検証する検査専用 script (C18)。graph node 集合=state node 集合・graph_hash pin 一致を検査する。投影ファイル (task-graph-status.json + task-progress.md) の書込は行わない — projection writer は consumer (harness-creator TG-C09 project-task-status.py) が単一 writer (二重 writer 禁止)。
# inputs:
#   - argv: --task-graph <task-graph.json> --task-state <task-state.json>
#           --status-json <task-graph-status.json> [--check-only]
#   - backward-compatible argv: <PLAN_DIR> (3 ファイルが同居する旧配置)
# outputs:
#   - stdout: parity violations 列挙 もしくは OK summary
#   - stderr: IO/引数エラー
#   - exit: 0=OK / 1=parity violation / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none (検査専用・投影は書かない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-graph/task-state/status projection の三層 parity 検査器 (C18・検査専用)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C18) +
phase-04-test-design.md の C18 受入例。canonical graph は同一 revision 内で構造 SSOT として不変、
consumer 単一 writer が task-state を更新する。**投影 (task-graph-status.json + task-progress.md) の
writer は consumer (harness-creator TG-C09 project-task-status.py) 唯一**であり、本 script は書かない
(producer/consumer の二重 writer は出力 schema drift と「どちらが正か」の曖昧化を招くため、
elegant-review 20260711 A2 で producer 側を parity 検査専用へ縮退した)。parity 検査は
graph node 集合=state node 集合=projection node 集合、projection の各 state、summary counts、
graph_hash pin 一致 (revision 内 graph 不変) を実ファイル間で強制する。projection は純導出という
設計だけを根拠に一致を仮定しない。--check-only は後方互換で受理する no-op (常に検査のみ)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_derive_task_graph():
    """同梱 derive-task-graph.py を file-path import する (graph_hash 再計算用)。"""
    path = Path(__file__).resolve().parent / "derive-task-graph.py"
    spec = importlib.util.spec_from_file_location("derive_task_graph", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _graph_node_ids(graph: dict) -> set[str]:
    return {
        n["id"]
        for n in graph.get("nodes", [])
        if isinstance(n, dict) and isinstance(n.get("id"), str)
    }


def _node_state_map(document: dict) -> dict[str, object]:
    """state/projection document の id -> state マップ。"""
    out: dict[str, str] = {}
    for n in document.get("nodes", []):
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            out[n["id"]] = n.get("state")
    return out


def _duplicate_ids(document: dict) -> list[str]:
    ids = [n.get("id") for n in document.get("nodes", []) if isinstance(n, dict)]
    return sorted({nid for nid in ids if isinstance(nid, str) and ids.count(nid) > 1})


def _expected_counts(node_states: dict[str, object]) -> dict[str, int]:
    counts = {key: 0 for key in ("pending", "running", "done", "blocked")}
    for value in node_states.values():
        if value in counts:
            counts[value] += 1
    return counts


def check_parity(graph: dict, state: dict, projection: dict) -> list[str]:
    """三層 parity を実比較する (C18)。"""
    errs: list[str] = []
    g_ids = _graph_node_ids(graph)
    state_map = _node_state_map(state)
    projection_map = _node_state_map(projection)
    s_ids = set(state_map)
    p_ids = set(projection_map)

    for label, document in (("graph", graph), ("state", state), ("projection", projection)):
        duplicates = _duplicate_ids(document)
        if duplicates:
            errs.append(f"parity: {label} の node id が重複: {duplicates}")

    only_graph = sorted(g_ids - s_ids)
    only_state = sorted(s_ids - g_ids)
    if only_graph:
        errs.append(f"parity: graph にあり state に無い node: {only_graph}")
    if only_state:
        errs.append(f"parity: state にあり graph に無い node: {only_state}")

    only_state_projection = sorted(s_ids - p_ids)
    only_projection_state = sorted(p_ids - s_ids)
    if only_state_projection:
        errs.append(f"parity: state にあり projection に無い node: {only_state_projection}")
    if only_projection_state:
        errs.append(f"parity: projection にあり state に無い node: {only_projection_state}")

    for node_id in sorted(s_ids & p_ids):
        if state_map[node_id] != projection_map[node_id]:
            errs.append(
                f"parity: projection state 不一致 node={node_id!r}: "
                f"state={state_map[node_id]!r} != projection={projection_map[node_id]!r}"
            )

    pinned = state.get("graph_hash") if isinstance(state, dict) else None
    dtg = _load_derive_task_graph()
    try:
        actual = dtg.graph_hash(graph)
    except (TypeError, AttributeError, KeyError) as exc:
        errs.append(f"parity: graph_hash 算出不能 (graph 不正): {exc}")
        return errs
    if pinned != actual:
        errs.append(
            f"parity: graph_hash pin 不一致 state={pinned!r} != 実算出={actual!r} "
            "(graph 直接書換/revision 内 graph 変更・状態更新は task-state だけを触ること)"
        )

    projected_hash = projection.get("graph_hash") if isinstance(projection, dict) else None
    if projected_hash != actual:
        errs.append(
            f"parity: projection graph_hash 不一致 projection={projected_hash!r} "
            f"!= 実算出={actual!r}"
        )

    summary = projection.get("summary") if isinstance(projection, dict) else None
    if not isinstance(summary, dict):
        errs.append("parity: projection summary が object でない")
    else:
        expected_total = len(state_map)
        if summary.get("total") != expected_total:
            errs.append(
                f"parity: projection summary.total 不一致 "
                f"summary={summary.get('total')!r} != state nodes={expected_total}"
            )
        expected_by_state = _expected_counts(state_map)
        if summary.get("by_state") != expected_by_state:
            errs.append(
                f"parity: projection summary.by_state 不一致 "
                f"summary={summary.get('by_state')!r} != state 集計={expected_by_state!r}"
            )
    return errs


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="task-graph/state/status の三層 parity 検査 (C18・検査専用。"
                    "投影の書込は consumer harness-creator TG-C09 project-task-status.py が単一 writer)")
    ap.add_argument("plan_dir", nargs="?", help="後方互換: 3 ファイルが同居する旧 PLAN_DIR")
    ap.add_argument("--task-graph", help="構造 SSOT task-graph.json")
    ap.add_argument("--task-state", help="状態 SSOT eval-log/<slug>/build/task-state.json")
    ap.add_argument("--status-json", help="派生投影 task-graph-status.json")
    ap.add_argument("--check-only", action="store_true",
                    help="後方互換 no-op (本 script は常に検査のみで投影を書かない)")
    return ap


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    explicit = (args.task_graph, args.task_state, args.status_json)
    if all(explicit) and args.plan_dir is None:
        return tuple(Path(value) for value in explicit)  # type: ignore[return-value]
    if args.plan_dir is not None and not any(explicit):
        plan_dir = Path(args.plan_dir)
        return (
            plan_dir / "task-graph.json",
            plan_dir / "task-state.json",
            plan_dir / "task-graph-status.json",
        )
    raise ValueError(
        "--task-graph/--task-state/--status-json を全て指定するか、後方互換 PLAN_DIR だけを指定してください"
    )


def main(argv: list[str] | None = None) -> int:
    ap = _build_parser()
    try:
        args = ap.parse_args(argv)
        graph_path, state_path, status_path = _resolve_paths(args)
    except (SystemExit, ValueError) as exc:
        if isinstance(exc, ValueError):
            sys.stderr.write(f"引数エラー: {exc}\n")
        return 2

    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        projection = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"task-graph/task-state 読込/parse 失敗: {exc}\n")
        return 2

    violations = check_parity(graph, state, projection)
    if violations:
        for v in violations:
            print(v)
        return 1

    print("OK: 三層 parity 妥当 (node 集合・各 state・summary counts・graph_hash 一致)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
