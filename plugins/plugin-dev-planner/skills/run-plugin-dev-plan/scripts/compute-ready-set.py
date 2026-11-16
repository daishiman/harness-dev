#!/usr/bin/env python3
# /// script
# name: compute-ready-set
# purpose: task-graph.json から着手可能 (ready) task node 集合と write_scope 衝突ペアをステートレスに導出する (C4)。
# inputs:
#   - argv: <plan_dir> [--repo-root <path>] (<plan_dir>/task-graph.json を読む。--repo-root は
#     consumes 成果物実在検査の相対 write_scope 解決基点。未指定時は現状維持=cwd)
# outputs:
#   - stdout: {"ready_set":[id,...],"conflicts":[[id,id],...]} JSON (ready_set は sorted 決定論)
#   - exit: 0=OK (ready 空でも正常) / 1=読込不能 / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""ready-set 導出器 (C4)。

3 段のステートレスアルゴリズムで着手可能 node を求める:
  1. state==blocked の node を候補から除外 (depends_on 充足によらず ready に入れない強い除外)。
  2. state!=done かつ 全 depends_on 先が done かつ 全 consumes 先 artifact が実在する node を候補化。
     成果物実在は producer state==done を代理述語にせず、consumes 先 artifact を produces する
     producer node の write_scope を os.path.exists で独立検査する (done でもパス欠落なら除外)。
     相対 write_scope の解決基点は --repo-root (未指定時 cwd — cwd anchoring を避けたい consumer は
     --repo-root を明示指定する)。絶対パス write_scope は --repo-root の影響を受けない。
  3. 候補内で write_scope が重複するとき、決定論 tie-break (id 昇順) で先頭 1 件のみを ready とし、
     残りは deferred として次周回へ持ち越す (単一許可・直列化)。deferred は winner との衝突ペアを
     conflicts へ記録する。これにより同一 write_scope 衝突を理由に ready が 0 件化する fail-closed
     デッドロック (全除外) を構造的に排除する — pending が尽きるまで 1 周回 1 node ずつ必ず進行する。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402,F401  (語彙 SSOT の同梱確認・将来の値域参照用)


def ready_set(graph: dict, repo_root: str | None = None) -> tuple[set[str], list[tuple[str, str]]]:
    """graph から (ready node id 集合, write_scope 衝突ペア list) を返す。

    衝突ペアは (id_a, id_b) を id 昇順・ペア列も昇順で決定論的に並べる。
    repo_root 指定時は consumes 成果物実在検査の相対 write_scope を repo_root 基点で解決する
    (未指定は従来どおり cwd 基点・後方互換)。
    """
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = graph.get("edges", []) if isinstance(graph, dict) else []

    node_by_id: dict[str, dict] = {}
    for n in nodes:
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            node_by_id[n["id"]] = n

    depends: dict[str, list[str]] = {}          # node id -> depends_on 先 node id 群
    consumes: dict[str, list[str]] = {}         # consumer node id -> consumes 先 artifact id 群
    producers_of: dict[str, list[str]] = {}     # artifact id -> それを produces する producer node id 群
    for e in edges:
        if not isinstance(e, dict):
            continue
        et, frm, to = e.get("type"), e.get("from"), e.get("to")
        if et == "depends_on":
            depends.setdefault(frm, []).append(to)
        elif et == "consumes":
            # canonical direction: artifact -> consumer task
            consumes.setdefault(to, []).append(frm)
        elif et == "produces":
            producers_of.setdefault(to, []).append(frm)

    def _artifact_exists(artifact_id: str) -> bool:
        """artifact を produces する producer node の write_scope が os.path.exists か。

        相対 write_scope は repo_root 指定時のみ repo_root 基点で解決する (未指定は cwd 基点)。
        絶対パスは repo_root に依らずそのまま検査する。
        """
        for producer_id in producers_of.get(artifact_id, []):
            producer = node_by_id.get(producer_id)
            if producer is None:
                continue
            ws = producer.get("write_scope")
            if not (isinstance(ws, str) and ws):
                continue
            if repo_root and not os.path.isabs(ws):
                ws = os.path.join(repo_root, ws)
            if os.path.exists(ws):
                return True
        return False

    candidates: set[str] = set()
    for nid, n in node_by_id.items():
        state = n.get("state")
        if state == "blocked":            # 1. blocked は強い除外
            continue
        if state == "done":               # 2a. 未完了のみ候補
            continue
        if not all(node_by_id.get(y, {}).get("state") == "done" for y in depends.get(nid, [])):
            continue                       # 2b. 全 depends_on 先が done
        if not all(_artifact_exists(a) for a in consumes.get(nid, [])):
            continue                       # 2c. 全 consumes 先 artifact が実在 (os.path.exists 独立検査)
        candidates.add(nid)

    # 3. 候補内 write_scope 衝突を決定論 tie-break で直列化する (単一許可)。
    #    同一 write_scope グループは id 昇順先頭 1 件のみ ready・残りは deferred で次周回へ持ち越す。
    #    winner が done 化すると次周回で当該 scope が解放され deferred が新 winner になるため、
    #    fail-closed 全除外 (ready 0 件デッドロック) を構造的に排除する。write_scope=None は一意扱い。
    ordered = sorted(candidates)
    conflicts: list[tuple[str, str]] = []
    winner_by_scope: dict[str, str] = {}
    deferred: set[str] = set()
    for nid in ordered:
        ws = node_by_id.get(nid, {}).get("write_scope")
        if ws is None:                        # None は衝突しない (一意扱い・現行 semantics 維持)
            continue
        winner = winner_by_scope.get(ws)
        if winner is None:
            winner_by_scope[ws] = nid         # 先頭 (id 昇順) を許可
        else:
            conflicts.append((winner, nid))   # 後続は winner の背後へ直列化 (winner < nid)
            deferred.add(nid)
    ready = candidates - deferred
    return ready, conflicts


def _usage() -> int:
    print("usage: compute-ready-set.py <plan_dir> [--repo-root <path>]", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo_root: str | None = None
    if "--repo-root" in argv:              # optional flag (既定=cwd 基点の現状維持)
        i = argv.index("--repo-root")
        if i + 1 >= len(argv):
            return _usage()
        repo_root = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) != 1:
        return _usage()
    graph_path = Path(argv[0]) / "task-graph.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"読込不能: {exc}", file=sys.stderr)
        return 1
    ready, conflicts = ready_set(graph, repo_root=repo_root)
    out = {"ready_set": sorted(ready), "conflicts": [list(p) for p in conflicts]}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
