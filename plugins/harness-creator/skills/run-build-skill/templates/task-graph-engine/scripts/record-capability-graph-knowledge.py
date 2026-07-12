#!/usr/bin/env python3
# /// script
# name: record-capability-graph-knowledge
# purpose: C06 の capability 依存グラフと self-reflect で発見された未網羅タスクを、生成 harness 側 knowledge (Loop A) と harness-creator 側 knowledge (Loop B) へ source_ref 付き要約として記録する。生ログ全文や task-graph.json 相当の別状態を複製せず、依存詰まり・dangling 参照・再利用すべき順序判断だけを knowledge entry 化する (H6 の実装物)。
# inputs:
#   - argv: <dependency_graph_json> --target-knowledge-dir <knowledge/> [--harness-knowledge-dir <plugins/harness-creator/knowledge>] [--discovered-json <tasks.json>] [--dry-run]
# outputs:
#   - stdout: {"entries":[...],"loop_a_status":...,"loop_b_status":...} JSON (entry は knowledge-loop schema 準拠 + 明示 source_ref)
#   - stderr: 診断
#   - exit: 0=OK / 1=記録失敗 / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: <knowledge-dir>/knowledge-capability-graph.json (append/merge・既存 entry 不変) + <knowledge-dir>/knowledge-index.json (category 登録・冪等)。Loop A/B の各 knowledge-dir が対象
# dependencies: []
# requires-python: ">=3.10"
# ///
"""capability 依存グラフ + discovered task を Loop A/B knowledge へ記録する (C07)。

with-goal-seek の engine:task-graph 変種が、C06 が抽出した cross-surface 依存グラフと
self-reflect (C02) で checklist へ追記された未網羅タスクを、「どの surface がどの前提知識・
成果物に依存するか」「どの dangling を先に解消すべきか」という**実行前判断で参照する派生
knowledge** として記録する。生ログ全文や task-graph.json 相当の別状態は複製しない (H6)。

記録先は 2 系統 (既存 record-task-graph-knowledge.py の Loop A/Loop B 設計を生成 harness 側へ
縮小適用):
  - Loop A = --target-knowledge-dir (生成 harness 自身の knowledge/)。
  - Loop B = --harness-knowledge-dir (harness-creator 側 knowledge/・任意)。
いずれも category ファイル knowledge-capability-graph.json の items[] へ **append/merge のみ**
(id 既存の entry は上書きせず skip)。各 entry は必須6フィールド + 明示 source_ref を持つ。

Exit 0 = OK, 1 = 記録失敗, 2 = usage/IO error。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CATEGORY_FILE = "knowledge-capability-graph.json"
CATEGORY_ID = "capability-graph"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


def build_entries(graph: dict, source_ref: str, discovered: list[dict]) -> list[dict]:
    """graph + discovered task から knowledge entry 群を決定論生成する (id 昇順)。"""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    gaps = graph.get("gaps", [])
    entries: list[dict] = []

    # 1. 依存順序サマリ (再利用すべき順序判断)。
    chains = "; ".join(f"{e['from']}->{e['to']}" for e in edges[:8]) or "(edge なし)"
    entries.append({
        "id": "cdg-summary",
        "title": "capability dependency graph summary",
        "intent": "実行前に surface 間依存を参照し、依存先が未完成の surface を先に着手しない",
        "background": (
            f"抽出 surface {len(nodes)} 件 / 依存辺 {len(edges)} 件 / 未解決 {len(gaps)} 件。"
            f"主要依存: {chains}。checklist(progress.json) の実行順とは別レイヤの派生 knowledge。"
        ),
        "keywords": ["dependency-graph", "surface", "ready-order", "task-graph", "consult"],
        "source": {"file": source_ref},
        "source_ref": source_ref,
    })

    # 2. dangling 参照ごとの解消 knowledge (依存詰まり)。
    for g in gaps:
        gid = f"cdg-gap-{_slug(g.get('from', '') + '-' + g.get('ref', ''))}"
        entries.append({
            "id": gid,
            "title": f"dangling 参照: {g.get('from')} -> {g.get('ref')}",
            "intent": "当該 surface 利用前に dangling 参照 (未発見の依存先) を解消する",
            "background": (
                f"{g.get('from')} が {g.get('ref')} ({g.get('type')}) を参照するが surface が未発見。"
                f"source: {g.get('source_ref')}"
            ),
            "keywords": ["dangling", "dependency-gap", "consult", "fail-closed"],
            "source": {"file": g.get("source_ref", source_ref)},
            "source_ref": g.get("source_ref", source_ref),
        })

    # 3. self-reflect discovered task (未網羅タスク・任意)。
    for t in discovered:
        tid = t.get("id")
        if not tid:
            continue
        entries.append({
            "id": f"cdg-task-{_slug(tid)}",
            "title": f"discovered task {tid}",
            "intent": "self-reflect で発見した未網羅タスクを完了 gate へ載せる",
            "background": t.get("text", "(text なし)"),
            "keywords": ["self-reflect", "discovered-task", "completion-gate"],
            "source": {"file": source_ref},
            "source_ref": source_ref,
        })

    entries.sort(key=lambda e: e["id"])
    return entries


def register_in_index(knowledge_dir: Path, dry_run: bool) -> bool:
    """knowledge-index.json の categories[] へ本 category を登録する (index-search consult で発見可能にする)。

    index-search 型 consult は knowledge-index.json の categories[] を辿るため、category ファイルを
    書くだけでは記録済みでも発見されない (add_entry.py の register_category_in_index と同型の効果を、
    テンプレ自己完結のため stdlib のみで内蔵する)。既登録なら no-op (冪等)。登録した場合 True。
    """
    index_path = knowledge_dir / "knowledge-index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            index = {"version": "1.0.0", "consult_at": ["runtime"], "categories": []}
    else:
        index = {"version": "1.0.0", "consult_at": ["runtime"], "categories": []}
    categories = index.setdefault("categories", [])
    if any(c.get("id") == CATEGORY_ID or c.get("file") == CATEGORY_FILE for c in categories):
        return False
    categories.append({
        "id": CATEGORY_ID,
        "label": "capability dependency graph",
        "file": CATEGORY_FILE,
        "keywords": ["dependency-graph", "surface", "consult", "task-graph"],
    })
    if not dry_run:
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def merge_into_store(knowledge_dir: Path, entries: list[dict], dry_run: bool) -> dict:
    """category ファイルへ append/merge (id 既存は skip・既存 entry 不変) + index 登録。結果 status を返す。"""
    store_path = knowledge_dir / CATEGORY_FILE
    if store_path.exists():
        data = json.loads(store_path.read_text(encoding="utf-8"))
        if not isinstance(data.get("items"), list):
            data["items"] = []
    else:
        data = {"category": CATEGORY_ID, "label": "capability dependency graph",
                "version": "1.0.0", "consult_at": ["runtime"], "items": []}

    existing_ids = {it.get("id") for it in data["items"] if isinstance(it, dict)}
    added, skipped = [], []
    for e in entries:
        if e["id"] in existing_ids:
            skipped.append(e["id"])
        else:
            data["items"].append(e)
            existing_ids.add(e["id"])
            added.append(e["id"])

    if not dry_run:
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 記録済み knowledge を index-search consult から発見可能にする (category 登録・冪等)。
    registered = register_in_index(knowledge_dir, dry_run)

    return {"store": str(store_path), "added": added, "skipped": skipped,
            "category_registered": registered, "dry_run": dry_run}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dependency_graph_json", help="C06 の出力 (dependency graph JSON) パス")
    p.add_argument("--target-knowledge-dir", required=True, help="Loop A: 生成 harness の knowledge/")
    p.add_argument("--harness-knowledge-dir", default=None, help="Loop B: harness-creator の knowledge/ (任意)")
    p.add_argument("--discovered-json", default=None, help="self-reflect discovered task の JSON list [{id,text}] (任意)")
    p.add_argument("--dry-run", action="store_true", help="書込せず結果のみ返す")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        graph = json.loads(Path(args.dependency_graph_json).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"dependency graph 読込失敗: {exc}\n")
        return 2

    discovered: list[dict] = []
    if args.discovered_json:
        try:
            discovered = json.loads(Path(args.discovered_json).read_text(encoding="utf-8"))
            if not isinstance(discovered, list):
                raise ValueError("discovered-json は list である必要がある")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            sys.stderr.write(f"discovered-json 読込失敗: {exc}\n")
            return 2

    entries = build_entries(graph, args.dependency_graph_json, discovered)

    try:
        loop_a = merge_into_store(Path(args.target_knowledge_dir), entries, args.dry_run)
        loop_b = None
        if args.harness_knowledge_dir:
            loop_b = merge_into_store(Path(args.harness_knowledge_dir), entries, args.dry_run)
    except OSError as exc:
        sys.stderr.write(f"knowledge 記録失敗: {exc}\n")
        return 1

    sys.stdout.write(json.dumps({
        "entries": entries,
        "loop_a_status": loop_a,
        "loop_b_status": loop_b,
    }, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
