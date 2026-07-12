#!/usr/bin/env python3
# /// script
# name: apply-handoff-notes
# purpose: task 間で有界伝播する handoff-notes を task_id の直接先行 task へのみ限定伝播し (推移閉包は注入しない)、各 note を actionable/advisory へ分類し件数(≤3)/文字数(≤200)上限違反を検出する (C12)。
# inputs:
#   - argv: --notes <handoff-notes.json> --graph <task-graph.json> --task-id <id>
# outputs:
#   - stdout: {task_id, predecessors, injected_notes} JSON
#   - stderr: 有界性違反 (maxItems 3 / maxLength 200)
#   - exit: 0=OK / 1=有界性違反 / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""handoff-notes の有界伝播器 + advisory/actionable 分類器 (C12)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C12)。
伝播範囲は task_id へ直接 depends_on/consumes している先行 task のみに限定し、推移的な
全履歴注入は行わない。classify() は「〜する」等の動詞句で終わる次アクション記述を
actionable (accept-discovered-task 起票候補)、状態/所感に留まる記述を advisory と分類する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402,F401  (frontmatter 規約の共有ローダ; 兄弟 script と同一 boilerplate)

CATEGORIES = ("went_well", "friction_points", "downstream_watchouts")
MAX_ITEMS = 3
MAX_LEN = 200
PREDECESSOR_EDGE_TYPES = ("depends_on", "consumes")

# actionable 判定ヒューリスティック: 動詞語幹 (行為) を含み、次アクションの語尾で終わる文。
_ACTION_STEMS = (
    "追加", "修正", "実装", "検討", "対応", "変更", "削除", "作成",
    "更新", "確認", "分離", "統合", "整理", "導入", "移行", "改善",
)
_ACTION_ENDINGS = ("する", "すべき", "したい", "せよ", "しよう", "する必要がある")


def classify(note_text: str) -> str:
    """note 1 行を actionable / advisory に分類する簡易ヒューリスティック。

    行為語幹 (追加/修正/…) を含み、かつ次アクションの語尾 (する/すべき/…) で終わる文を
    actionable とする。状態/所感 (「〜していた」「〜だった」等) に留まる文は advisory。
    """
    text = note_text.strip().rstrip("。.！!？? ")
    ends_action = any(text.endswith(e) for e in _ACTION_ENDINGS)
    has_stem = any(stem in text for stem in _ACTION_STEMS)
    if ends_action and has_stem:
        return "actionable"
    return "advisory"


def validate_notes_bounds(notes: dict) -> list[str]:
    """handoff-notes の有界性 (各カテゴリ maxItems 3 / 各要素 maxLength 200) を検査し violations を返す。"""
    violations: list[str] = []
    for cat in CATEGORIES:
        items = notes.get(cat, [])
        if not isinstance(items, list):
            violations.append(f"{cat}: 配列でない ({type(items).__name__})")
            continue
        if len(items) > MAX_ITEMS:
            violations.append(f"{cat}: maxItems {MAX_ITEMS} 超過 ({len(items)} 件)")
        for i, item in enumerate(items):
            if isinstance(item, str) and len(item) > MAX_LEN:
                violations.append(f"{cat}[{i}]: maxLength {MAX_LEN} 超過 ({len(item)} 文字)")
    return violations


def _direct_predecessors(graph: dict, task_id: str) -> set[str]:
    """task_id から直接 depends_on/consumes で指される先行 (推移閉包は含めない)。"""
    preds: set[str] = set()
    for edge in graph.get("edges", []):
        if edge.get("from") == task_id and edge.get("type") in PREDECESSOR_EDGE_TYPES:
            to = edge.get("to")
            if to is not None:
                preds.add(to)
    return preds


def propagate(notes: dict, graph: dict, task_id: str) -> dict:
    """handoff-notes を task_id の直接先行 task へのみ限定伝播する (推移的全履歴は注入しない)。

    返り値: {task_id, predecessors (直接先行の id 昇順), injected_notes (分類済み note 群)}。
    """
    preds = _direct_predecessors(graph, task_id)
    injected: list[dict] = []
    for cat in CATEGORIES:
        for text in notes.get(cat, []):
            if isinstance(text, str):
                injected.append(
                    {"category": cat, "text": text, "class": classify(text)}
                )
    return {
        "task_id": task_id,
        "predecessors": sorted(preds),
        "injected_notes": injected,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apply-handoff-notes.py",
        description="handoff-notes を task_id の直接先行 task へ限定伝播し分類する。",
    )
    parser.add_argument("--notes", required=True, help="handoff-notes.json のパス")
    parser.add_argument("--graph", required=True, help="task-graph.json のパス")
    parser.add_argument("--task-id", required=True, help="伝播起点 task の id")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse usage error / --help
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        notes = json.loads(Path(args.notes).read_text(encoding="utf-8"))
        graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"read/parse error: {exc}", file=sys.stderr)
        return 2

    violations = validate_notes_bounds(notes)
    if violations:
        for v in violations:
            print(v, file=sys.stderr)
        return 1

    result = propagate(notes, graph, args.task_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
