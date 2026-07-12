#!/usr/bin/env python3
# /// script
# name: self-reflect-append
# purpose: self-reflect で実行中に発見した新規タスクを、別状態ファイル (task-graph.json 相当) を新設せず checklist (progress.json) の末尾へ新しい item として追記する決定論ゲート。追記のみ (既存 item は不変) で追記ノードは常に DAG 上の新規シンクになるが、id 重複・未知 depends_on 参照・追記後サイクルを fail-closed 検査する (単一truth設計=H3 解消の実装物)。
# inputs:
#   - argv: <progress_json_path> --id <新規id> --text <達成条件文> [--depends-on <id[,id...]>] [--verify-by reasoning|script|lint|test|human]
# outputs:
#   - stdout: 追記後の progress.json 全体 (checklist へ status=pending の新 item 追記済み)
#   - stderr: violation 理由 (id 重複 / 未知 depends_on / サイクル / schema 違反)
#   - exit: 0=OK / 1=violation (fail-closed) / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: <progress_json_path> のみ (別 state file を一切生成しない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""discovered task を checklist 末尾へ単一truth追記する決定論ゲート (C02)。

with-goal-seek の engine:task-graph 変種が、実行中に発見した新規タスクを**別状態ファイルを
新設せず** progress.json の checklist 配列末尾へ追記する。追記された item は追記された瞬間から
done-judge (周回終了判定) が毎回スキャンする**その同じ checklist 配列**の一部になるため、
「発見はしたが completion 判定に反映されない」非統合が構造的に発生しない (H3)。

安全性 (fail-closed・追記前に検査):
  1. id が schema pattern (^C[0-9]+$) に準拠し、既存 item と重複しない。
  2. depends_on の各先が既存 checklist に実在する (dangling 参照拒否)。
  3. 追記後の depends_on グラフが非循環である (新規シンクゆえ構造的に安全だが念のため検査)。
既存 item の id/text/status/depends_on は一切書き換えない (単一 self-writer 追記のみ)。

Exit 0 = OK, 1 = violation, 2 = usage/IO error。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ID_RE = re.compile(r"^C[0-9]+$")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("progress_path", help="progress.json のパス")
    p.add_argument("--id", required=True, help="新規 item の id (^C[0-9]+$)")
    p.add_argument("--text", required=True, help="二値判定可能な達成条件文")
    p.add_argument("--depends-on", default="", help="依存先 id のカンマ区切り (既定 空=依存なし)")
    p.add_argument(
        "--verify-by",
        choices=["reasoning", "script", "lint", "test", "human"],
        default=None,
        help="判定手段 (任意)",
    )
    return p.parse_args(argv)


def _parse_depends(raw: str) -> list[str]:
    return [d.strip() for d in raw.split(",") if d.strip()]


def _has_cycle(adjacency: dict[str, list[str]]) -> bool:
    """depends_on グラフ (item -> その依存先) の循環を反復 DFS で検出する。

    明示スタックの 3-color DFS で、数百 item の深い直鎖でも Python 再帰上限に触れない
    (再帰実装は深鎖で RecursionError=crash になり fail-closed でないため反復化する)。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in adjacency}

    for start in adjacency:
        if color[start] != WHITE:
            continue
        color[start] = GRAY
        stack: list[tuple[str, object]] = [(start, iter(adjacency.get(start, [])))]
        while stack:
            node, it = stack[-1]
            nxt = None
            for cand in it:  # type: ignore[assignment]
                if cand not in color or color[cand] == BLACK:  # dangling/処理済は無視
                    continue
                nxt = cand
                break
            if nxt is None:
                color[node] = BLACK
                stack.pop()
            elif color[nxt] == GRAY:
                return True
            else:  # WHITE
                color[nxt] = GRAY
                stack.append((nxt, iter(adjacency.get(nxt, []))))
    return False


def append_item(
    checklist: list[dict],
    new_id: str,
    text: str,
    depends_on: list[str],
    verify_by: str | None,
) -> dict:
    """fail-closed 検査を通したうえで新 item を組み立てて返す (checklist は破壊しない)。"""
    if not _ID_RE.match(new_id):
        raise ValueError(f"id が schema pattern (^C[0-9]+$) に非準拠: {new_id}")

    existing_ids = {it.get("id") for it in checklist if isinstance(it, dict)}
    if new_id in existing_ids:
        raise ValueError(f"id が既存 item と重複: {new_id}")

    unknown = [d for d in depends_on if d not in existing_ids]
    if unknown:
        raise ValueError(f"未知の depends_on 参照 (checklist に不在): {unknown}")

    new_item: dict = {"id": new_id, "text": text, "status": "pending"}
    if depends_on:
        new_item["depends_on"] = depends_on
    if verify_by:
        new_item["verify_by"] = verify_by

    # 追記後グラフのサイクル検査 (新規シンクゆえ理論上不要だが fail-closed の保険)。
    adjacency: dict[str, list[str]] = {}
    for it in checklist + [new_item]:
        if isinstance(it, dict) and it.get("id"):
            adjacency[it["id"]] = list(it.get("depends_on", []) or [])
    if _has_cycle(adjacency):
        raise ValueError(f"追記後の depends_on グラフにサイクルが生じる: {new_id}")

    return new_item


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    progress_path = Path(args.progress_path)
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"progress.json 読込/parse 失敗: {progress_path}: {exc}\n")
        return 2

    checklist = data.get("checklist")
    if not isinstance(checklist, list):
        sys.stderr.write("progress.json の checklist が配列でない\n")
        return 2

    try:
        new_item = append_item(
            checklist, args.id, args.text, _parse_depends(args.depends_on), args.verify_by
        )
    except ValueError as exc:
        sys.stderr.write(f"self-reflect append violation: {exc}\n")
        return 1

    # 既存 item を一切書き換えず末尾追記のみ (単一truth)。
    checklist.append(new_item)
    data["checklist"] = checklist
    progress_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
