#!/usr/bin/env python3
# /// script
# name: render-task-graph-mermaid
# purpose: task-graph.json を canonical 順序のまま mermaid (graph TD) へ決定論 render する (byte一致/graph外要素非描画)。4 edge 型を線種で描き分け、depends_on 最長鎖 (critical path) を linkStyle で強調する。
# inputs:
#   - argv: <PLAN_DIR> [--task-state <task-state.json path>]
# outputs:
#   - stdout: 書込パス (<PLAN_DIR>/task-graph.mmd)
#   - stderr: IO/引数エラー
#   - exit: 0=OK / 1=violation (未使用) / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: <PLAN_DIR>/task-graph.mmd
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-graph.json → mermaid renderer (C15)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C15) +
phase-04-test-design.md の C15 受入例。derive-task-graph.py の canonicalize() と同一
canonical 順序で nodes/edges を走査し byte 一致を保証、graph 外要素は描画しない。
critical_path() は depends_on エッジのみを辺とする最長依存鎖 (tie は辞書順最小)。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))


def _load_derive():
    """derive-task-graph.py (ハイフン名) を importlib でロードし canonicalize を再利用する。"""
    path = _SCRIPTS / "derive-task-graph.py"
    spec = importlib.util.spec_from_file_location("derive_task_graph", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


derive_task_graph = _load_derive()

# (state, fill色) この順・この色で classDef を出力する。
_STATE_CLASSDEFS = (
    ("pending", "#eee"),
    ("running", "#bbf"),
    ("done", "#bfb"),
    ("blocked", "#fbb"),
)
# edge 型 → mermaid 線種。
_EDGE_STYLE = {
    "parent_of": "-->",
    "depends_on": "==>",
    "produces": "-.->",
    "consumes": "--o",
}
_CRITICAL_LINKSTYLE = "stroke:#f66,stroke-width:3px"


def _state_map(task_state: dict | None) -> dict:
    """task-state.json ({"nodes":[{"id","state"}]}) から id→state マップを構築する。"""
    out: dict = {}
    if not isinstance(task_state, dict):
        return out
    for n in task_state.get("nodes", []) or []:
        if isinstance(n, dict) and isinstance(n.get("id"), str) and isinstance(n.get("state"), str):
            out[n["id"]] = n["state"]
    return out


def _seq_better(a: list[str], b: list[str]) -> bool:
    """a が b より良い経路か (より長い / 同長なら辞書順で小さい)。"""
    if not b:
        return True
    if len(a) != len(b):
        return len(a) > len(b)
    return a < b


def _longest_dep_chain(graph: dict) -> list[str]:
    """depends_on エッジのみを辺とする最長鎖を depends_on 順 (dependent→dependency) で返す。

    tie は経路先頭 node id の辞書順最小 (先頭が同じなら経路全体の辞書順最小) で決定論化する。
    """
    g = derive_task_graph.canonicalize(graph)
    adj: dict = {}
    vertices: set = set()
    for e in g["edges"]:
        if e.get("type") == "depends_on":
            f, t = e.get("from"), e.get("to")
            adj.setdefault(f, []).append(t)
            vertices.add(f)
            vertices.add(t)
    if not vertices:
        return []

    memo: dict = {}
    visiting: set = set()

    def best_from(u):
        if u in memo:
            return memo[u]
        if u in visiting:  # depends_on は非循環前提だが安全側で cycle をガード
            return [u]
        visiting.add(u)
        best = [u]
        for w in sorted(adj.get(u, []), key=str):
            cand = [u] + best_from(w)
            if _seq_better(cand, best):
                best = cand
        visiting.discard(u)
        memo[u] = best
        return best

    overall: list[str] = []
    for u in sorted(vertices, key=str):
        cand = best_from(u)
        if _seq_better(cand, overall):
            overall = cand
    return overall


def critical_path(graph: dict) -> list[str]:
    """depends_on 最長依存鎖を実行順 (dependency→dependent) の node id list で返す。

    最長路が複数ある tie は経路の辞書順最小で固定 (決定論)。空 graph では []。
    """
    chain = _longest_dep_chain(graph)
    return list(reversed(chain))


def _critical_edge_pairs(graph: dict) -> set:
    """critical path 上の depends_on エッジ (from,to) ペア集合を返す (linkStyle 強調用)。"""
    chain = _longest_dep_chain(graph)
    return set(zip(chain, chain[1:]))


def render_mermaid(graph: dict, task_state: dict | None = None) -> str:
    """canonical 順序で mermaid (graph TD) を決定論生成する。同一 (graph, state) で byte 一致。"""
    g = derive_task_graph.canonicalize(graph)
    smap = _state_map(task_state)

    lines: list[str] = ["graph TD"]
    for state, color in _STATE_CLASSDEFS:
        lines.append(f"    classDef {state} fill:{color}")
    for n in g["nodes"]:
        nid = n.get("id")
        title = n.get("title", "")
        state = smap.get(nid, n.get("state"))
        lines.append(f'    {nid}["{title}"]:::{state}')
    for e in g["edges"]:
        style = _EDGE_STYLE.get(e.get("type"), "-->")
        lines.append(f"    {e.get('from')} {style} {e.get('to')}")

    # critical path 強調: 該当 depends_on エッジの link 番号 (g["edges"] 上の index) を linkStyle で上書き。
    cp_pairs = _critical_edge_pairs(g)
    if cp_pairs:
        for idx, e in enumerate(g["edges"]):
            if e.get("type") == "depends_on" and (e.get("from"), e.get("to")) in cp_pairs:
                lines.append(f"    linkStyle {idx} {_CRITICAL_LINKSTYLE}")

    return "\n".join(lines) + "\n"


def _usage() -> int:
    print("usage: render-task-graph-mermaid.py <PLAN_DIR> [--task-state <path>]", file=sys.stderr)
    return 2


def _parse_argv(argv: list[str]) -> tuple[list[str], str | None] | None:
    positional: list[str] = []
    task_state_path: str | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--task-state":
            if i + 1 >= len(argv):
                return None
            task_state_path = argv[i + 1]
            i += 2
        else:
            positional.append(argv[i])
            i += 1
    if len(positional) != 1:
        return None
    return positional, task_state_path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parsed = _parse_argv(argv)
    if parsed is None:
        return _usage()
    positional, task_state_path = parsed

    plan_dir = Path(positional[0])
    if not plan_dir.is_dir():
        print(f"not a directory: {plan_dir}", file=sys.stderr)
        return 2

    graph_path = plan_dir / "task-graph.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {graph_path}: {exc}", file=sys.stderr)
        return 2

    task_state: dict | None = None
    if task_state_path:
        try:
            task_state = json.loads(Path(task_state_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"read/parse error: {task_state_path}: {exc}", file=sys.stderr)
            return 2

    out = render_mermaid(graph, task_state)
    out_path = plan_dir / "task-graph.mmd"
    out_path.write_text(out, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
