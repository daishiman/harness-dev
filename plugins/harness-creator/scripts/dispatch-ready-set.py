#!/usr/bin/env python3
# /// script
# name: dispatch-ready-set
# purpose: task-graph 駆動 build の 1 周回 dispatch 配信 (TG-C01)。task-graph.json に task-state.json の runtime state を merge し、producer=plugin-dev-planner の compute-ready-set.py を一時ファイル経由の read-only cross-plugin subprocess で呼び出して着手可能 (ready) batch を得る。周回ごとに graph_hash pin を producer derive-task-graph.py --print-graph-hash で再検証 (F10) し、実行中の graph 変更混入を fail-closed 拒否する。本 script は read-only (task-state.json を書かない)。
# inputs:
#   - argv: --task-graph <task-graph.json> --task-state <task-state.json> [--planner-root <plugins/plugin-dev-planner>] [--repo-root <path>]
# outputs:
#   - stdout: {"ready_batch":[id,...],"conflicts":[[id,id],...],"blocked":[id,...],"graph_hash_pin":"verified"|"mismatch"|null,"source":"compute-ready-set.py"} JSON
#   - stderr: 読込/subprocess エラー
#   - exit: 0=OK (ready 空でも正常) / 1=graph_hash pin 不一致 | compute-ready-set 非0 | 出力 parse 不能 / 2=読込不能/usage error
# contexts: [C, E]
# network: false
# write-scope: none (read-only・compute-ready-set への受け渡し用 tempfile は非永続・subprocess 後に自動破棄)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""ready-set dispatch 配信器 (TG-C01)。

design: plugin-plans/harness-creator/phase-05-implementation.md (TG-C01 実装設計)。
producer=plugin-dev-planner の `compute-ready-set.py <plan_dir>` (単一位置引数・
`<plan_dir>/task-graph.json` を固定パスで読む) の実インターフェースへ、consumer 側で
task-state.json の runtime state を merge した graph を一時ディレクトリへ書き出して渡す。
ready_set 導出アルゴリズムは producer 側を再実装せず subprocess 呼出しのみで再利用する。

graph_hash 周回再検証 (F10): task-state.json の pin (graph_hash) が設定済みなら、
producer `derive-task-graph.py --print-graph-hash` (read-only・write-mode を起動しない) を
subprocess 呼出しして現 task-graph.json の canonical hash を pin と照合する。不一致なら
dispatch を fail-closed で拒否 (build 開始時 1 回の pin 検証を素通りした実行中の graph
変更混入を dispatch 周回ごとに拒む)。pin 未設定 (初回) は照合をスキップする。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


# ── 兄弟 script ローダ (ハイフン名 module の importlib ロード・TG-C02 SSOT 再利用) ──
def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# producer=plugin-dev-planner の既定 root。導出は TG-C02 (sync-task-state.resolve_planner_root)
# を SSOT として再利用しローカル再定義しない (--planner-root 明示指定は従来通り優先)。
_sts = _load_sibling("sync-task-state")
_PLANNER_ROOT_DEFAULT = str(_sts.resolve_planner_root())
_PLANNER_SCRIPTS_REL = ("skills", "run-plugin-dev-plan", "scripts")
# repo root の既定 (本 script 位置から導出・cwd 非依存)。compute-ready-set の consumes 成果物
# 実在検査 (M-02) に --repo-root として伝搬し、相対 write_scope 解決の cwd anchoring を避ける。
# parents[3] = scripts -> harness-creator -> plugins の 1 段上 = repo root。
_REPO_ROOT_DEFAULT = str(Path(__file__).resolve().parents[3])


# ── state マージ (純関数・入力を破壊しない浅コピー) ─────────────────────────────
def merge_state(graph: dict, state: dict) -> dict:
    """graph の各 node の state を state (node_id -> node-like dict のマッピング) で上書きする。

    上書き優先順: state[node_id]["state"] → graph 内 node の既存 state → "pending"。
    graph / 各 node を浅コピーし edges 参照は共有する (純関数・入力 graph を変更しない)。
    """
    nodes: list[dict] = []
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            nodes.append(node)
            continue
        merged = dict(node)
        nid = node.get("id")
        override = state.get(nid, {}) if isinstance(state, dict) else {}
        override = override if isinstance(override, dict) else {}
        merged["state"] = override.get("state", node.get("state", "pending"))
        nodes.append(merged)
    out = dict(graph)
    out["nodes"] = nodes
    return out


# ── graph_hash pin 周回再検証 (F10・read-only) ────────────────────────────────
def verify_graph_hash_pin(task_graph_path: str, pinned: str, planner_root: str) -> bool:
    """producer derive-task-graph.py --print-graph-hash を read-only subprocess 呼出しし pin と照合。

    derive の write-mode main は起動せず (task-graph.json を上書きしない)、read-only
    サブコマンドの stdout (`sha256:<64hex>`) を pinned と比較する。derive が非0 終了
    (graph 不正/読込不能) の場合は照合不能ゆえ False (fail-closed) を返す。
    """
    script = Path(planner_root).joinpath(*_PLANNER_SCRIPTS_REL, "derive-task-graph.py")
    proc = subprocess.run(
        [sys.executable, str(script), "--print-graph-hash", str(task_graph_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return False
    return proc.stdout.strip() == pinned


# ── compute-ready-set 呼出し (cross-plugin subprocess・test で monkeypatch 可能) ──
def invoke_ready_set(planner_root: str, plan_dir: str, repo_root: str) -> subprocess.CompletedProcess:
    """producer compute-ready-set.py <plan_dir> --repo-root <repo_root> を subprocess 起動する。

    ready_set 導出は producer 側を再実装せず本呼出しに一元化する (cross-plugin subprocess)。
    --repo-root 伝搬 (M-02) で consumes 成果物実在検査の相対 write_scope を repo root 基点に固定し、
    dispatch 起動 cwd への依存 (cwd anchoring) を排除する。
    """
    script = Path(planner_root).joinpath(*_PLANNER_SCRIPTS_REL, "compute-ready-set.py")
    return subprocess.run(
        [sys.executable, str(script), str(plan_dir), "--repo-root", str(repo_root)],
        capture_output=True,
        text=True,
    )


def _blocked_ids(merged: dict) -> list[str]:
    """merged graph 上で state=="blocked" の node id を昇順で返す (単純フィルタ)。"""
    ids = [
        n.get("id")
        for n in merged.get("nodes", [])
        if isinstance(n, dict) and n.get("state") == "blocked" and n.get("id") is not None
    ]
    return sorted(ids)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dispatch-ready-set.py",
        description="task-graph + task-state を merge し compute-ready-set 経由で ready batch を配信する (TG-C01)。",
    )
    p.add_argument("--task-graph", required=True, help="task-graph.json のパス")
    p.add_argument("--task-state", required=True, help="task-state.json のパス (graph_hash pin/state 供給)")
    p.add_argument("--planner-root", default=_PLANNER_ROOT_DEFAULT,
                   help="producer=plugin-dev-planner の root (既定は TG-C02 resolve_planner_root() SSOT)")
    p.add_argument("--repo-root", default=_REPO_ROOT_DEFAULT,
                   help="compute-ready-set へ伝搬する相対 write_scope 解決基点 (既定は本 script 位置から導出した repo root)")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse usage error / --help
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        graph = json.loads(Path(args.task_graph).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"task-graph 読込/parse 失敗: {args.task_graph}: {exc}", file=sys.stderr)
        return 2
    try:
        task_state = json.loads(Path(args.task_state).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"task-state 読込/parse 失敗: {args.task_state}: {exc}", file=sys.stderr)
        return 2

    state_by_id = {
        n.get("id"): n for n in task_state.get("nodes", []) if isinstance(n, dict)
    }
    merged = merge_state(graph, state_by_id)

    # producer compute-ready-set 呼出前に同じ 3-edge truth table を検証する。
    # consumes artifact の producer 不在は ready=[] として沈黙させず fail-closed。
    _, dependency_issues = _sts.resolve_dependency_producers(merged)
    if dependency_issues:
        print(_sts.format_dependency_issue(dependency_issues[0]), file=sys.stderr)
        return 1

    # (F10) 周回 graph_hash 再検証: pin 設定済みなら不一致を fail-closed で拒否。
    pinned = task_state.get("graph_hash")
    if pinned:
        if not verify_graph_hash_pin(args.task_graph, pinned, args.planner_root):
            print(json.dumps({
                "ready_batch": [],
                "conflicts": [],
                "blocked": [],
                "graph_hash_pin": "mismatch",
                "source": "compute-ready-set.py",
            }, ensure_ascii=False, indent=2))
            return 1
        graph_hash_pin: str | None = "verified"
    else:
        graph_hash_pin = None

    blocked = _blocked_ids(merged)

    # merged graph を一時ディレクトリへ task-graph.json として書き出し compute-ready-set へ渡す。
    # この tempfile は入力受け渡し専用の非永続コピー (canonical serialization 契約 対象外)。
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "task-graph.json").write_text(  # writeguard: allow: TemporaryDirectory 内の非永続コピー (compute-ready-set 受け渡し用・plan は書かない)
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        proc = invoke_ready_set(args.planner_root, tmpdir, args.repo_root)

    if proc.returncode != 0:
        print(f"compute-ready-set.py 失敗 (rc={proc.returncode}): {proc.stderr}", file=sys.stderr)
        return 1
    try:
        rs = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(f"compute-ready-set.py 出力 parse 失敗: {exc}", file=sys.stderr)
        return 1

    out = {
        "ready_batch": rs.get("ready_set", []),
        "conflicts": rs.get("conflicts", []),
        "blocked": blocked,
        "graph_hash_pin": graph_hash_pin,
        "source": "compute-ready-set.py",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
