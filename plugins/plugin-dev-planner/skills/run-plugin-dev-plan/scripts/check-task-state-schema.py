#!/usr/bin/env python3
# /// script
# name: check-task-state-schema
# purpose: task-state.json を手書き検査する (永続 4 値 state / running→lease 条件付き必須 / blocked→blocked_reason / graph_hash pin 整合)。C16。
# inputs:
#   - argv: --task-state <path> (必須) [--task-graph <path> (任意・指定時のみ pin 検査)]
# outputs:
#   - stdout: violations 列挙 (空なら無出力)
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-state.json スキーマ + graph_hash pin 検査器 (C16)。

schema/pin 規約の所有=producer=plugin-dev-planner、実書込=consumer=harness-creator。本 script は
task-state.schema.json の条件付き必須 (running→started_at/lease_expires_at・blocked→blocked_reason)
と、computed-only の ready を永続 state へ焼く非正準を fail-closed で拒否する。graph_hash pin は
derive-task-graph.graph_hash() を task-graph へ再適用し state の pin と不一致 (graph 変化後の state 陳腐化)
を検出する (反映は次周回のみ・当該周回は fail-closed)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

_GRAPH_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# RFC3339 date-time の軽い形式検査 (末尾 Z / 小数秒 optional)。厳密な暦検査はしない (二層分離)。
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$")


def _load_derive_task_graph():
    """同梱 derive-task-graph.py を file-path import する (graph_hash 再計算用)。"""
    path = Path(__file__).resolve().parent / "derive-task-graph.py"
    spec = importlib.util.spec_from_file_location("derive_task_graph", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_task_state(state: dict) -> list[str]:
    """task-state (dict) を task-state.schema.json の手書き制約で検査し violation 群を返す。"""
    if not isinstance(state, dict):
        return ["task-state が object でない"]
    errs: list[str] = []

    sv = state.get("schema_version")
    if not isinstance(sv, str) or not sv.strip():
        errs.append("schema_version が無い/非文字列")
    gh = state.get("graph_hash")
    if not isinstance(gh, str) or not _GRAPH_HASH_RE.match(gh):
        errs.append(f"graph_hash={gh!r} が ^sha256:[0-9a-f]{{64}}$ に不一致")
    nodes = state.get("nodes")
    if not isinstance(nodes, list):
        errs.append("nodes が list でない (必須)")
        return errs

    state_ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    for nid, count in sorted(Counter(
            nid for nid in state_ids if isinstance(nid, str) and nid.strip()).items()):
        if count > 1:
            errs.append(f"task-state node id 重複: {nid!r} ({count}件)")

    for idx, n in enumerate(nodes):
        if not isinstance(n, dict):
            errs.append(f"nodes[{idx}] が object でない")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip():
            errs.append(f"nodes[{idx}].id が空/非文字列")
        label = nid if isinstance(nid, str) and nid.strip() else f"nodes[{idx}]"

        st = n.get("state")
        if st not in specfm.TASK_STATE_PERSISTED:
            errs.append(
                f"[{label}] state={st!r} が永続 enum 外 {list(specfm.TASK_STATE_PERSISTED)} "
                "(computed-only の ready を永続へ焼くのは非正準)"
            )

        if st == "running":
            sa = n.get("started_at")
            le = n.get("lease_expires_at")
            if sa is None:
                errs.append(f"[{label}] running は started_at が非 null 必須")
            elif not (isinstance(sa, str) and _DATETIME_RE.match(sa)):
                errs.append(f"[{label}] started_at={sa!r} が RFC3339 date-time 形式でない")
            if le is None:
                errs.append(f"[{label}] running は lease_expires_at が非 null 必須 (孤児 running 判別不能)")
            elif not (isinstance(le, str) and _DATETIME_RE.match(le)):
                errs.append(f"[{label}] lease_expires_at={le!r} が RFC3339 date-time 形式でない")

        br = n.get("blocked_reason")
        if st == "blocked":
            if br is None:
                errs.append(f"[{label}] blocked は blocked_reason が必須")
            elif br not in specfm.BLOCKED_REASONS:
                errs.append(f"[{label}] blocked_reason={br!r} が enum 外 {list(specfm.BLOCKED_REASONS)}")
        elif br is not None:
            errs.append(f"[{label}] 非 blocked state に blocked_reason={br!r} が付与 (violation)")

    return errs


def check_node_id_parity(state: dict, graph: dict) -> list[str]:
    """task-graph/state のnode id集合が完全一致することを検査する。

    hash pin 一致だけでは state から node が落ちた、または未知 node が混入した
    状態を検出できない。両側の重複も set 化前に fail-closed で拒否する。
    """
    errs: list[str] = []
    state_nodes = state.get("nodes") if isinstance(state, dict) else None
    graph_nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if not isinstance(state_nodes, list) or not isinstance(graph_nodes, list):
        return ["node id parity 検査不能: task-state/task-graph nodes が list でない"]

    def _ids(nodes: list, owner: str) -> list[str]:
        ids: list[str] = []
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                errs.append(f"{owner}.nodes[{idx}] が object でない (node id parity 検査不能)")
                continue
            nid = node.get("id")
            if not isinstance(nid, str) or not nid.strip():
                errs.append(f"{owner}.nodes[{idx}].id が空/非文字列 (node id parity 検査不能)")
                continue
            ids.append(nid)
        for nid, count in sorted(Counter(ids).items()):
            if count > 1:
                errs.append(f"{owner} node id 重複: {nid!r} ({count}件)")
        return ids

    state_ids = _ids(state_nodes, "task-state")
    graph_ids = _ids(graph_nodes, "task-graph")
    state_set, graph_set = set(state_ids), set(graph_ids)
    missing = sorted(graph_set - state_set)
    unknown = sorted(state_set - graph_set)
    if missing:
        errs.append(f"task-state node 欠落 (graph には存在): {missing}")
    if unknown:
        errs.append(f"task-state 未知 node (graph に不在): {unknown}")
    return errs


def check_graph_hash_pin(state: dict, graph_path: Path) -> list[str]:
    """state.graph_hash と graph hash、および両者の node id 完全一致を照合する。"""
    graph_path = Path(graph_path)
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"task-graph 読込/parse 失敗: {exc}"]
    dtg = _load_derive_task_graph()
    try:
        actual = dtg.graph_hash(graph)
    except (TypeError, AttributeError, KeyError) as exc:
        return [f"graph_hash 算出不能 (graph 不正): {exc}"]
    errs = check_node_id_parity(state, graph)
    pinned = state.get("graph_hash") if isinstance(state, dict) else None
    if pinned != actual:
        errs.append(
            f"graph_hash pin 不一致: state={pinned!r} != 実算出={actual!r} "
            "(discovered-task 受理等で graph 変化後 state が古い・反映は次周回のみ)"
        )
    return errs


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="check-task-state-schema.py",
        description="task-state.json のスキーマ + graph_hash pin 検査 (C16)。",
    )
    parser.add_argument("--task-state", required=True, help="検査対象 task-state.json パス")
    parser.add_argument("--task-graph", default=None, help="pin 照合用 task-graph.json (任意)")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    try:
        state = json.loads(Path(args.task_state).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"task-state 読込/parse 失敗: {exc}", file=sys.stderr)
        return 2

    violations = validate_task_state(state)
    if args.task_graph:
        violations = violations + check_graph_hash_pin(state, Path(args.task_graph))

    if violations:
        for v in violations:
            print(v)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
