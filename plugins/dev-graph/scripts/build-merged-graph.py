#!/usr/bin/env python3
# /// script
# name: build-merged-graph
# purpose: git merge driver for .dev-graph/state/graph.json — structural 3-way merge by graph_node_id, plus an opt-in installer and a C02-locked resolver for an already conflicted index.
# inputs: ["argv: %O(base) %A(ours, overwritten with result) %B(theirs) [%P(path)]", "argv: --install [--repo-root PATH]", "argv: --resolve-conflict [--repo-root PATH] [--graph PATH] [--dry-run] [--accept-deletion ID]..."]
# outputs: ["exit 0: %A holds the merged graph; exit 1: %A holds __merge_conflict__ sentinels needing manual resolution", "stdout: JSON install/resolve receipt"]
# requires-python = ">=3.10"
# dependencies: ["_common.py", "../lib/graph_envelope.py"]
# contexts: [E]
# network: false
# write-scope: driver mode writes only the %A temp path git supplies; --install writes local git config only; --resolve-conflict is a C02 atomic writer for the conflicted graph under the shared register lock
# ///
"""graph.json 専用の git merge driver。

graph.json は多数の node が1つの配列に並ぶ単一ファイルのため、git 標準の行ベース
3-way マージは近接した追加/削除を衝突として誤検出しやすい。ここでは
``graph_node_id`` をキーにした集合演算でノード単位に構造的な3-wayマージを行い、
本当に同じノードの同じフィールドが両側で異なる値に変更されている場合だけ衝突とする。

ノードの物理削除はしない。schema の status enum は削除相当を tombstoned への遷移として
扱う規約であり (graph-node.schema.json)、どちらか一方の入力からノードが消えていても
それは C02 writer を経由した削除ではない (build-graph-node.py に削除操作はない) ため、
base に存在したノードは常に保持する。本当に消したい場合は、この merge driver とは
別に build-graph-node.py update で status を "tombstoned" に遷移させる。

git merge driver の契約: 呼び出し引数は base/ours/theirs の一時ファイルパス
(``%O %A %B``, 実行時 cwd はリポジトリ直下)。exit 0 なら git は %A の内容を
そのまま採用する。exit 非0 なら git はそのパスを未解決 (conflicted) のまま残す —
このとき %A には診断用の __merge_conflict__ sentinel を書き出し、通常の
schema validate で機械的に発見できるようにする。

driver の発火には managed repository 側の `.gitattributes` 宣言
(``.dev-graph/state/graph.json merge=devgraph-json``) と ``--install`` の git config の
両方が要る。``--install`` は tracked file を書かず、宣言の有無を receipt で報告するだけに
留める。plugin は repository の外 (plugin cache) に置かれるため、driver の command は
script の絶対パスを指す。plugin 更新でパスが変わったら ``--install`` を再実行する。

名前の verb は build とした。出力がマージ済み graph という成果物そのものだからである。
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない (子の起動にも -B を渡す)。
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from _common import ContractError, atomic_json, json_bytes  # noqa: E402
from graph_envelope import envelope_violations  # noqa: E402

DRIVER_NAME = "devgraph-json"
GRAPH_RELPATH = ".dev-graph/state/graph.json"


def _node_map(nodes: list[dict]) -> dict[str, dict]:
    return {node["graph_node_id"]: node for node in nodes}


def _merge_scalar(base: Any, ours: Any, theirs: Any) -> tuple[Any, bool]:
    """1フィールドを base/ours/theirs の3値で 3-way マージする。

    戻り値は (マージ後の値, 衝突したか)。
    - ours と theirs が同じ値 → その値を採用 (衝突ではない)。
    - 片方だけが base から変化している → 変化した側を採用 (もう片方は無変更)。
    - 両方が base から異なる値に変化していて、かつ両者が異なる → 真の衝突。
    """
    if ours == theirs:
        return ours, False
    if ours == base:
        return theirs, False
    if theirs == base:
        return ours, False
    return ours, True


def _merge_node(
    base_node: dict | None, ours_node: dict | None, theirs_node: dict | None
) -> tuple[dict, list[str]]:
    """1ノードをフィールド単位で 3-way マージする。戻り値は (マージ後dict, 衝突フィールド名のlist)。"""
    keys: set[str] = set()
    for candidate in (base_node, ours_node, theirs_node):
        if candidate:
            keys.update(candidate.keys())
    merged: dict[str, Any] = {}
    conflicts: list[str] = []
    for key in keys:
        b = base_node.get(key) if base_node else None
        o = ours_node.get(key) if ours_node else None
        t = theirs_node.get(key) if theirs_node else None
        value, conflicted = _merge_scalar(b, o, t)
        if conflicted:
            conflicts.append(key)
        merged[key] = value
    return merged, conflicts


def _merge_nodes(
    base_nodes: list[dict],
    ours_nodes: list[dict],
    theirs_nodes: list[dict],
    accept_deletions: frozenset[str] = frozenset(),
) -> tuple[list[dict], list[dict], list[str]]:
    """graph_node_id 単位で集合演算し、構造的に3-wayマージする。

    戻り値は (マージ後のノード配列, 衝突が残ったノードの一覧, 温存した片側削除の id 一覧)。
    出力順序は ours の既存順序を保持し、theirs にしかない新規ノードは末尾に追記する
    (無関係な並べ替えによる diff ノイズを避けるため)。

    片側からノードが消えている場合、既定では「温存」する。merge driver は git から自動的に
    呼ばれるため、ここで削除を確定させると事故で消えたノードを黙って葬ることになる。
    意図的な削除 (stale GC 等) と確認できた id だけを ``accept_deletions`` で明示承認する。
    """
    base_map = _node_map(base_nodes)
    ours_map = _node_map(ours_nodes)
    theirs_map = _node_map(theirs_nodes)
    preserved_deletions: list[str] = []

    order = [node["graph_node_id"] for node in ours_nodes]
    order += [
        node_id
        for node_id in (node["graph_node_id"] for node in theirs_nodes)
        if node_id not in ours_map
    ]
    # base にしかない (両側から消えた) ノードも、物理削除しない規約に従い末尾に温存する。
    order += [
        node_id
        for node_id in base_map
        if node_id not in ours_map and node_id not in theirs_map
    ]

    merged_nodes: list[dict] = []
    conflicted_nodes: list[dict] = []
    for node_id in order:
        b = base_map.get(node_id)
        o = ours_map.get(node_id)
        t = theirs_map.get(node_id)

        if o is None or t is None:
            # 片側 (または両側) からノードが消えている。base に居たなら削除、居ないなら片側追加。
            survivor = o if o is not None else (t if t is not None else b)
            assert survivor is not None
            if b is None:
                # base に無い = 片側だけが新規追加した。そのまま採用する (削除ではない)。
                merged_nodes.append(survivor)
                continue
            if node_id in accept_deletions:
                continue  # 明示承認された削除だけを実際に落とす
            preserved_deletions.append(node_id)
            merged_nodes.append(survivor)
            continue
        assert o is not None and t is not None
        if b is None:
            # 両側が同じ id を新規追加した。内容が同一なら無衝突、異なれば衝突。
            if o == t:
                merged_nodes.append(o)
            else:
                sentinel = {
                    "graph_node_id": node_id,
                    "__merge_conflict__": True,
                    "reason": "both sides independently added this graph_node_id with different content",
                    "base": None,
                    "ours": o,
                    "theirs": t,
                }
                merged_nodes.append(sentinel)
                conflicted_nodes.append(sentinel)
            continue

        merged, field_conflicts = _merge_node(b, o, t)
        if field_conflicts:
            sentinel = {
                "graph_node_id": node_id,
                "__merge_conflict__": True,
                "reason": f"conflicting fields: {', '.join(sorted(field_conflicts))}",
                "base": b,
                "ours": o,
                "theirs": t,
            }
            merged_nodes.append(sentinel)
            conflicted_nodes.append(sentinel)
        else:
            merged_nodes.append(merged)

    if preserved_deletions:
        sys.stderr.write(
            "[build-merged-graph] preserved "
            f"{len(preserved_deletions)} node(s) dropped by one side: {', '.join(preserved_deletions)}\n"
            "  意図的な削除なら --accept-deletion <id> を付けて --resolve-conflict を再実行する\n"
        )
    return merged_nodes, conflicted_nodes, preserved_deletions


def _merge_revision(ours_rev: int, theirs_rev: int, nodes_changed: bool) -> int:
    """graph_revision は「1回の書込みにつき+1」規約 (build-graph-node.py) に整合させる。

    このマージ自体を1回の論理的な書込み操作とみなし、より進んでいる側の revision に
    +1 する。ours と theirs のノード内容が完全に一致するなら (実質的に無変更マージ)
    revision を無駄に進めない。
    """
    if not nodes_changed:
        return max(ours_rev, theirs_rev)
    return max(ours_rev, theirs_rev) + 1


def merge_graph(
    base: dict, ours: dict, theirs: dict, accept_deletions: frozenset[str] = frozenset()
) -> tuple[dict, bool, list[str]]:
    """トップレベルを含めグラフ全体を3-wayマージする。

    戻り値は (マージ後graph, 衝突が残ったか, 温存した片側削除の id 一覧)。
    外枠は lib/graph_envelope.py の canonical key だけで組み直す。`repository_id` は任意 key
    なので、マージ後も値がある場合だけ残す (null を書くと envelope 違反になる)。
    """
    merged_nodes, conflicted, preserved_deletions = _merge_nodes(
        base.get("nodes", []), ours.get("nodes", []), theirs.get("nodes", []), accept_deletions
    )
    nodes_changed = ours.get("nodes") != theirs.get("nodes")

    schema_version, schema_conflict = _merge_scalar(
        base.get("schema_version"), ours.get("schema_version"), theirs.get("schema_version")
    )
    repository_id, repo_conflict = _merge_scalar(
        base.get("repository_id"), ours.get("repository_id"), theirs.get("repository_id")
    )

    merged: dict[str, Any] = {
        "schema_version": schema_version,
        "graph_revision": _merge_revision(ours["graph_revision"], theirs["graph_revision"], nodes_changed),
        "nodes": merged_nodes,
    }
    if repository_id is not None:
        merged["repository_id"] = repository_id
    has_conflict = bool(conflicted) or schema_conflict or repo_conflict
    return merged, has_conflict, preserved_deletions


def _git(root: Path, args: list[str], *, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    if check and proc.returncode:
        raise ContractError(f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def install_driver(root: Path) -> int:
    """`.gitattributes` の merge=devgraph-json を実際に動かすための git config を張る。

    driver 本体の指定は `.gitattributes` には書けない (任意コマンドの実行になるため git が
    禁じている)。clone/worktree ごとに一度だけこの `--install` を実行する必要がある。
    冪等 (何回実行しても同じ結果) なので、迷ったら再実行してよい。
    `.gitattributes` は tracked file なので書かず、宣言が効いているかを receipt で返す。
    """
    script = Path(__file__).resolve()
    try:
        command = f"python3 -B {script.relative_to(root.resolve())} %O %A %B %P"
    except ValueError:
        command = f"python3 -B {script} %O %A %B %P"
    _git(root, ["config", f"merge.{DRIVER_NAME}.name", "dev-graph graph.json structural 3-way merge"])
    _git(root, ["config", f"merge.{DRIVER_NAME}.driver", command])
    # recursive は「driver 未設定時に内部で使う仮想 merge 戦略」。text にしておくと
    # driver が居ない環境 (未 install の clone) でも従来通り行ベースで衝突表示になる。
    _git(root, ["config", f"merge.{DRIVER_NAME}.recursive", "text"])
    attribute = _git(root, ["check-attr", "merge", "--", GRAPH_RELPATH]).strip().rsplit(": ", 1)[-1]
    receipt: dict[str, Any] = {
        "installed": True,
        "driver": DRIVER_NAME,
        "command": command,
        "gitattributes_routed": attribute == DRIVER_NAME,
    }
    if attribute != DRIVER_NAME:
        receipt["next"] = f"add `{GRAPH_RELPATH} merge={DRIVER_NAME}` to the repository .gitattributes"
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


def _stage_blob(root: Path, stage: int, relpath: str) -> dict | None:
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f":{stage}:{relpath}"], capture_output=True, text=True, check=False
    )
    if proc.returncode or not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def _write_under_c02_lock(graph_path: Path, merged: dict) -> None:
    # build-graph-node.py / register-package.py と同じ lock file。C02 writer と直列化する。
    lock_path = graph_path.with_name(f".{graph_path.name}.register.lock")
    with lock_path.open("a+", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError(f"another C02 writer holds {lock_path.name}") from exc
        atomic_json(graph_path, merged)


def resolve_conflict(
    root: Path, relpath: str, *, dry_run: bool, accept_deletions: frozenset[str] = frozenset()
) -> int:
    """index に残っている未解決衝突を、構造マージした結果で解消する (C02 atomic write)。

    merge driver は「これから起きるマージ」にしか効かない。既に conflicted な状態
    (別プロセスの pull/stash pop などで作られたもの) を後から片付けるための経路。
    書く前に外枠を lib/graph_envelope.py で検査し、canonical でなければ書かない。
    """
    status = _git(root, ["status", "--porcelain=2", "--", relpath])
    if not any(line.startswith("u ") for line in status.splitlines()):
        sys.stderr.write(f"[build-merged-graph] {relpath} has no unresolved merge conflict\n")
        return 1

    base = _stage_blob(root, 1, relpath) or {"nodes": []}
    ours = _stage_blob(root, 2, relpath)
    theirs = _stage_blob(root, 3, relpath)
    if ours is None or theirs is None:
        sys.stderr.write("[build-merged-graph] add/add or delete/modify conflict needs manual resolution\n")
        return 1

    merged, has_conflict, preserved = merge_graph(base, ours, theirs, accept_deletions)
    summary = {
        "graph": relpath,
        "base": {"graph_revision": base.get("graph_revision"), "nodes": len(base.get("nodes", []))},
        "ours": {"graph_revision": ours.get("graph_revision"), "nodes": len(ours.get("nodes", []))},
        "theirs": {"graph_revision": theirs.get("graph_revision"), "nodes": len(theirs.get("nodes", []))},
        "merged": {"graph_revision": merged["graph_revision"], "nodes": len(merged["nodes"])},
        "conflicts": [n["graph_node_id"] for n in merged["nodes"] if n.get("__merge_conflict__")],
        "preserved_deletions": preserved,
        "accepted_deletions": sorted(accept_deletions),
        "written": False,
    }
    if has_conflict:
        summary["error"] = "unresolved node conflicts; graph left untouched"
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    violations = envelope_violations(merged)
    if violations:
        summary["error"] = "merged graph envelope is not canonical; graph left untouched"
        summary["envelope_violations"] = violations
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    if dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    _write_under_c02_lock((root / relpath).resolve(), merged)
    summary["written"] = True
    summary["next"] = f"git add {relpath}"
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1].startswith("--"):
        parser = argparse.ArgumentParser(description="dev-graph graph.json merge driver / conflict resolver")
        parser.add_argument("--install", action="store_true", help="register the merge driver in git config")
        parser.add_argument("--resolve-conflict", action="store_true", help="resolve an existing index conflict")
        parser.add_argument("--repo-root", default=".")
        parser.add_argument("--graph", default=GRAPH_RELPATH)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--accept-deletion",
            action="append",
            default=[],
            metavar="GRAPH_NODE_ID",
            help="片側で削除されたこの node を実際に落とす (意図的な削除を確認済みの場合のみ)",
        )
        args = parser.parse_args(argv[1:])
        root = Path(args.repo_root).resolve()
        try:
            if args.install:
                return install_driver(root)
            if args.resolve_conflict:
                return resolve_conflict(
                    root,
                    args.graph,
                    dry_run=args.dry_run,
                    accept_deletions=frozenset(args.accept_deletion),
                )
        except Exception as exc:  # fail-closed: 認識できない状態で graph は書かない
            sys.stderr.write(f"[build-merged-graph] {exc}\n")
            return 1
        parser.error("one of --install / --resolve-conflict is required")

    if len(argv) < 4:
        sys.stderr.write(
            "usage: build-merged-graph.py <base> <ours> <theirs> [path]\n"
            "       build-merged-graph.py --install [--repo-root DIR]\n"
            "       build-merged-graph.py --resolve-conflict [--repo-root DIR] [--graph PATH] [--dry-run]\n"
        )
        return 1
    base_path, ours_path, theirs_path = Path(argv[1]), Path(argv[2]), Path(argv[3])

    try:
        base = json.loads(base_path.read_text(encoding="utf-8")) if base_path.stat().st_size else {"nodes": []}
        ours = json.loads(ours_path.read_text(encoding="utf-8"))
        theirs = json.loads(theirs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[build-merged-graph] cannot parse input: {exc}\n")
        return 1

    merged, has_conflict, _preserved = merge_graph(base, ours, theirs)
    ours_path.write_bytes(json_bytes(merged))

    if has_conflict:
        sys.stderr.write(
            "[build-merged-graph] unresolved node conflicts remain "
            "(__merge_conflict__ sentinels written; resolve manually then re-stage)\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
