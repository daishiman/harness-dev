#!/usr/bin/env python3
# /// script
# name: inject-task-inputs
# purpose: task-graph 駆動 build で 1 task を SubAgent へ渡す直前に、対象 task-id の graph nodes 実在と、depends_on (consumer task→producer task) および consumes (artifact→consumer task) を produces (producer task→artifact) で逆引きした producer が全て done であること、producer 成果物が実在すること (F5) を fail-closed 検査し、注入すべき成果物パスと有界 handoff notes を返す read-only な入力解決器 (TG-C03)。
# inputs:
#   - argv: --task-graph G --task-state S --task-id T [--notes-schema N] [--max-notes M] [--max-note-chars C]
# outputs:
#   - stdout: 正常 {"injected_inputs":[{producer_task_id,artifact_path}],"injected_notes":[...]} / 拒否 {"rejected":true,"reason":...}
#   - stderr: IO/usage エラー
#   - exit: 0=注入可 / 1=fail-closed 拒否 (task-id 不在 | producer 未 done | 成果物欠落 | notes 上限超過) / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none (read-only・task-state/task-graph/schema を読むのみで一切書き込まない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-graph 駆動 build の consumer 側入力解決器 (TG-C03・read-only)。

design: plugin-plans/harness-creator/phase-05-implementation.md (TG-C03 実装設計)。
producer=plugin-dev-planner の derive-task-graph.py は、depends_on=consumer task→producer task、
produces=producer task→artifact、consumes=artifact→consumer task の方向で edge を生成する。
成果物パスは producer node.write_scope を主経路とし、パス形状の produces 先も併用する。
対象 task-id 自体が graph nodes に
不在なら fail-closed 拒否する (typo/stale id の素通り防止・C04 discovering_task_id 検証と同型)。
対象 task の depends_on producer と、consumes artifact を produces で逆引きした producer が
全て done で、かつ write_scope 成果物が os.path.exists で実在する場合のみ注入入力を組む。
state==done は代理述語に過ぎず成果物存在の保証にはならないため F5 で実在を別途検査する。
F5 の対象はパス形状 ("/" を含む) の write_scope/produces 先のみ — 非パスの id トークン
(plan ノード参照) を持つ producer は成果物なし producer として artifact 検査を skip し
notes のみ注入する (実在しようのないトークンで偽拒否しない)。
notes は単一 writer=TG-C02 (sync-task-state.py) が producer state node へ書く handoff_notes
(dict: went_well/friction_points/downstream_watchouts の各 list) を主経路として平坦化集約し、
flat notes list は後方互換の副経路として併読する。件数/各要素長の上限は consumer 側で
数値を再定義せず producer 所有の handoff-notes.schema.json (maxItems/maxLength) から読み
(F8 SSOT)、件数上限は producer 単位で適用する (schema が制約するのは 1 node 分の
handoff_notes ゆえ、ダイヤモンド依存で複数 producer が各々満杯でも偽拒否しない。
全体は len(producers)×Σ maxItems で有界)。本 script は一切書き込まない
(dispatcher が結果を SubAgent へ渡す)。
"""
from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import os
import sys
from pathlib import Path

# producer 所有の notes 上限 SSOT (F8): consumer 側で 3/200 を再定義しない。
# scripts/ の 2 階層上 = plugins/ を起点に producer schema へ解決する。
DEFAULT_NOTES_SCHEMA = str(
    Path(__file__).resolve().parents[2]
    / "plugin-dev-planner"
    / "skills"
    / "run-plugin-dev-plan"
    / "schemas"
    / "handoff-notes.schema.json"
)


# ── 兄弟 script ローダ (ハイフン名 module の importlib ロード・TG-C02 SSOT 再利用) ──
def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# edge 方向の共通解決は TG-C02 の resolve_dependency_producers を再利用する。
_sts = _load_sibling("sync-task-state")
# produces = producer→artifact (from=producer task, to=artifact id/path)。
_PRODUCES_EDGE_TYPE = "produces"
# TG-C02 が producer state node へ書く handoff_notes (dict) の平坦化対象カテゴリ (固定順)。
_HANDOFF_CATEGORIES = ("went_well", "friction_points", "downstream_watchouts")


def read_notes_bounds(schema_path: str) -> tuple[int, int]:
    """handoff-notes.schema.json から (max_notes, max_note_chars) を読む (F8 の SSOT)。

    schema は went_well/friction_points/downstream_watchouts の 3 array プロパティを持ち
    各 array は maxItems、その items は maxLength を持つ。TG-C03 は handoff_notes を 3 カテゴリ
    横断で 1 本の list へ平坦化するため、件数上限 (max_notes) は各カテゴリ maxItems の総和
    (Σ maxItems) とする。schema が制約するのは producer 1 node 分の handoff_notes であって
    集約全体ではないから、この上限は producer 単位で適用する — 各カテゴリが最大まで埋まった
    producer が複数居るダイヤモンド依存でも各 producer は Σ maxItems 以内で正当であり、
    集約合計へ同じ数値を適用すると偽拒否する。全体は len(producers)×Σ maxItems で有界。
    要素長上限 (max_note_chars) は各要素へ個別適用ゆえ items.maxLength の最大を採る (現行 schema
    は一律 3/200 なので (9, 200))。
    """
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    props = schema.get("properties", {})
    item_bounds: list[int] = []
    len_bounds: list[int] = []
    for prop in props.values():
        if not isinstance(prop, dict):
            continue
        mi = prop.get("maxItems")
        if isinstance(mi, int):
            item_bounds.append(mi)
        items = prop.get("items")
        if isinstance(items, dict) and isinstance(items.get("maxLength"), int):
            len_bounds.append(items["maxLength"])
    if not item_bounds or not len_bounds:
        raise ValueError(f"notes schema に maxItems/maxLength が無い: {schema_path}")
    return sum(item_bounds), max(len_bounds)


@functools.lru_cache(maxsize=None)
def _bounds_from_schema(schema_path: str) -> tuple[int, int]:
    return read_notes_bounds(schema_path)


def _producers(graph: dict, task_id: str) -> list[str]:
    """task_id の producer task id を決定論順で返す。

    depends_on は task→task を直接読み、consumes は artifact→consumer task を
    produces (producer task→artifact) で逆引きする。
    """
    producers, _ = _sts.resolve_dependency_producers(graph)
    return sorted(producers.get(task_id, set()), key=str)


def _nodes_by_id(graph: dict) -> dict[str, dict]:
    """graph の nodes を {id: node} へ索引する (write_scope 解決用)。"""
    return {
        n.get("id"): n
        for n in graph.get("nodes", [])
        if isinstance(n, dict) and n.get("id") is not None
    }


def _is_path_shaped(value: str) -> bool:
    """F5 実在検査の対象となる成果物パス形状 ("/" を含む) かを判定する。

    非パス (plan ノードの id トークン) は filesystem 上に実在しようがなく、検査すると
    正当な producer を偽拒否するため「成果物なし producer」として扱う。
    """
    return "/" in value


def _producer_artifacts(node: dict | None, graph: dict, producer_id: str) -> list[str]:
    """producer のパス形状の成果物パスを順序保持・重複排除で返す。

    主経路=producer node の write_scope (実 producer graph の形状)。副経路=produces エッジ先
    (schema 上有効な forward-compat・存在時のみ併用)。write_scope を先頭に据える。
    非パス (id トークン) の write_scope/produces 先は F5 対象外として含めない。
    """
    out: list[str] = []
    seen: set[str] = set()
    if node is not None:
        ws = node.get("write_scope")
        if isinstance(ws, str) and _is_path_shaped(ws) and ws not in seen:
            seen.add(ws)
            out.append(ws)
    for e in graph.get("edges", []):
        if e.get("type") == _PRODUCES_EDGE_TYPE and e.get("from") == producer_id:
            art = e.get("to")
            if isinstance(art, str) and _is_path_shaped(art) and art not in seen:
                seen.add(art)
                out.append(art)
    return out


def _producer_notes(state_node: dict) -> list[str]:
    """producer の state node から引継 notes を平坦化集約する (順序保持)。

    主経路=TG-C02 が書く handoff_notes (dict: went_well/friction_points/downstream_watchouts の
    各 str list) を固定カテゴリ順で平坦化。副経路=flat notes list (後方互換)。str のみ採る。
    """
    out: list[str] = []
    handoff = state_node.get("handoff_notes")
    if isinstance(handoff, dict):
        for cat in _HANDOFF_CATEGORIES:
            vals = handoff.get(cat)
            if isinstance(vals, list):
                out.extend(v for v in vals if isinstance(v, str))
    flat = state_node.get("notes")
    if isinstance(flat, list):
        out.extend(v for v in flat if isinstance(v, str))
    return out


def resolve_inputs(
    graph: dict,
    state: dict,
    task_id: str,
    *,
    max_notes: int | None = None,
    max_note_chars: int | None = None,
    notes_schema: str = DEFAULT_NOTES_SCHEMA,
) -> dict:
    """task_id へ注入すべき producer 成果物と有界 notes を解決する (read-only 純関数)。

    state は producer task id を key とし各 value に "state"/"handoff_notes"(/"notes") を持つ dict。
    fail-closed:
      - task_id 自体が graph nodes に不在なら拒否 (C04 discovering_task_id 検証と同型)。
      - producer が 1 つでも done でなければ最初に見つかった producer で打ち切り拒否。
      - producer node のパス形状 write_scope 成果物 (副次的に produces エッジ先) が実在
        しなければ拒否 (F5・done の代理述語に依存しない。非パスの id トークンは検査対象外)。
      - いずれかの producer の平坦化 notes が件数上限を、いずれかの要素が文字数上限を
        超えれば拒否 (件数上限は producer 単位=schema は 1 node 分を制約・F8)。
    正常系は {"injected_inputs": [...], "injected_notes": [...]}。
    max_notes/max_note_chars 未指定時のみ notes_schema から上限を読む (明示指定が上書き)。
    """
    if max_notes is None or max_note_chars is None:
        schema_notes, schema_chars = _bounds_from_schema(notes_schema)
        if max_notes is None:
            max_notes = schema_notes
        if max_note_chars is None:
            max_note_chars = schema_chars

    graph_nodes = _nodes_by_id(graph)

    # (1) task-id 実在検査: nodes に不在の task-id は fail-closed 拒否
    #     (C04 emit-discovered-task の discovering_task_id 検証と同型・typo/stale id の素通り防止)。
    if task_id not in graph_nodes:
        return {
            "rejected": True,
            "reason": f"unknown-task-id {task_id!r} が task-graph の nodes に不在",
        }

    # consumes artifact の producer/consumer 解決不能は、依存なしと誤認せず fail-closed。
    _, dependency_issues = _sts.resolve_dependency_producers(graph)
    if dependency_issues:
        issue = dependency_issues[0]
        rejected = {
            "rejected": True,
            "reason": _sts.format_dependency_issue(issue),
            "missing_artifact": issue.get("artifact_id"),
        }
        if issue.get("producer_task_id") is not None:
            rejected["blocking_producer_task_id"] = issue["producer_task_id"]
        return rejected

    producers = _producers(graph, task_id)

    # (2) producer 完了検査: 最初の未完了 producer で fail-closed 打ち切り。
    for pid in producers:
        if state.get(pid, {}).get("state") != "done":
            return {
                "rejected": True,
                "reason": f"producer {pid} not done",
                "blocking_producer_task_id": pid,
            }

    # (3) 成果物実在検査 (F5): write_scope 主経路 (+ produces 副経路) を os.path.exists で確認。
    injected_inputs: list[dict] = []
    for pid in producers:
        for artifact_path in _producer_artifacts(graph_nodes.get(pid), graph, pid):
            if not os.path.exists(artifact_path):
                return {
                    "rejected": True,
                    "reason": "producer artifact missing",
                    "blocking_producer_task_id": pid,
                    "missing_artifact": artifact_path,
                }
            injected_inputs.append({"producer_task_id": pid, "artifact_path": artifact_path})

    # (4) notes 集約 (handoff_notes 主経路 + flat notes 副経路) + 有界性検査 (上限は F8 schema 由来)。
    # 件数上限は producer 単位で適用する (schema が制約するのは 1 node 分の handoff_notes ゆえ
    # ダイヤモンド依存で複数 producer が各々満杯でも偽拒否しない。全体は len(producers)×max_notes で有界)。
    injected_notes: list = []
    for pid in producers:
        producer_notes = _producer_notes(state.get(pid, {}))
        if len(producer_notes) > max_notes:
            return {"rejected": True, "reason": "notes bound exceeded"}
        injected_notes.extend(producer_notes)
    for note in injected_notes:
        if isinstance(note, str) and len(note) > max_note_chars:
            return {"rejected": True, "reason": "notes bound exceeded"}

    return {"injected_inputs": injected_inputs, "injected_notes": injected_notes}


def _keyed_state(task_state: dict) -> dict:
    """task-state を {task_id: node} へ正規化する。

    TG-C02 task-state.schema.json shape ({"nodes": [{"id", "state", ...}]}) は id で keying し、
    既に keyed dict 形式 (test/低レベル呼出) はそのまま使う。
    """
    if isinstance(task_state, dict) and isinstance(task_state.get("nodes"), list):
        return {
            n.get("id"): n
            for n in task_state["nodes"]
            if isinstance(n, dict) and n.get("id") is not None
        }
    if isinstance(task_state, dict):
        return task_state
    return {}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="inject-task-inputs.py",
        description="task の producer 完了/成果物実在/notes 有界を検査し注入入力を解決する (TG-C03・read-only)。",
    )
    p.add_argument("--task-graph", required=True, help="producer task-graph.json のパス")
    p.add_argument("--task-state", required=True, help="task-state.json のパス (nodes list or keyed)")
    p.add_argument("--task-id", required=True, help="注入対象 task id")
    p.add_argument("--notes-schema", default=DEFAULT_NOTES_SCHEMA,
                   help="notes 上限 SSOT (既定 producer handoff-notes.schema.json)")
    p.add_argument("--max-notes", type=int, default=None, help="件数上限の任意上書き (既定 schema maxItems)")
    p.add_argument("--max-note-chars", type=int, default=None, help="文字数上限の任意上書き (既定 schema maxLength)")
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
        print(f"task-graph read/parse error: {args.task_graph}: {exc}", file=sys.stderr)
        return 2
    try:
        task_state = json.loads(Path(args.task_state).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"task-state read/parse error: {args.task_state}: {exc}", file=sys.stderr)
        return 2

    try:
        result = resolve_inputs(
            graph,
            _keyed_state(task_state),
            args.task_id,
            max_notes=args.max_notes,
            max_note_chars=args.max_note_chars,
            notes_schema=args.notes_schema,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"resolve error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get("rejected") else 0


if __name__ == "__main__":
    sys.exit(main())
