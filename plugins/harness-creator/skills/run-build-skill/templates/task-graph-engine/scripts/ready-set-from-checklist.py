#!/usr/bin/env python3
# /// script
# name: ready-set-from-checklist
# purpose: with-goal-seek の checklist (progress.json) へ additive 付与された depends_on から、依存充足順の ready 集合をステートレスに算出する決定論ゲート。逐次単一 self-writer 実行を前提とし write_scope 衝突/tie-break 機構は一切持たない (H1 解消の実装物)。
# inputs:
#   - argv: <progress_json_path> (schemas/goal-seek-loop.schema.json 準拠 checklist を持つ)
# outputs:
#   - stdout: {"ready":[id,...]} JSON (ready は id 昇順 sorted 決定論)
#   - stderr: 読込/parse 失敗の診断
#   - exit: 0=OK (ready 空でも正常) / 1=データ不整合 (id 欠落/status 不正) / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""checklist の depends_on から ready 集合を算出するステートレス決定論ゲート (C01)。

with-goal-seek の engine:task-graph 変種が、生成ハーネス内で「依存が全て done の pending
item だけを次の実行対象候補にする」ために使う。生成ハーネスは 1 プロセス内の**単一
self-writer** が checklist を逐次一つずつ処理するため、複数 writer が同一資源を奪い合う
状況が構造的に発生しない。よって既存 compute-ready-set.py (plugin-dev-planner) が持つ
write_scope tie-break / conflicts (並列 dispatch 前提の意図的機構・バグではない) は本
機構では死機構であり、複製しない (H1/H2)。本 script は read-only で状態を書かない。

ready の定義: status == "pending" かつ全 depends_on 先が status == "done" の item。
出力順序: id 昇順 (`C<n>` は数値昇順で自然順・C1<C2<C10)。

Exit 0 = OK (ready 空でも正常), 1 = データ不整合, 2 = usage/IO error。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_ID_NUM_RE = re.compile(r"^C(\d+)$")


def id_sort_key(item_id: str) -> tuple[int, int, str]:
    """id 昇順の決定論キー。`C<n>` は数値昇順 (C1<C2<C10)、非準拠 id は末尾へ辞書順。

    (bucket, numeric, raw) の三つ組で、準拠 id (bucket=0) を数値で、非準拠 id (bucket=1)
    を raw 文字列で安定ソートする。tie-break や write_scope には一切関与しない。
    """
    m = _ID_NUM_RE.match(item_id)
    if m:
        return (0, int(m.group(1)), item_id)
    return (1, 0, item_id)


def load_checklist(progress_path: Path) -> list[dict]:
    """progress.json を読み checklist 配列を返す。無ければ空配列。"""
    data = json.loads(progress_path.read_text(encoding="utf-8"))
    checklist = data.get("checklist", [])
    if not isinstance(checklist, list):
        raise ValueError("progress.json の checklist が配列でない")
    return checklist


def compute_ready(checklist: list[dict]) -> list[str]:
    """depends_on 全充足かつ status==pending の item id を昇順で返す (ステートレス)。

    - status が "done" の item id 集合を作る。
    - 各 pending item の depends_on が全て done 集合に含まれれば ready。
    - depends_on 先が checklist に存在しない (dangling) 場合、その先は永遠に done に
      ならないため当該 item は ready にならない (C01 は fail-closed 検査を C02 へ委ね、
      read-only 算出では単に not-ready として扱う)。
    """
    done_ids = {
        it["id"] for it in checklist
        if isinstance(it, dict) and it.get("status") == "done" and it.get("id")
    }
    ready: list[str] = []
    for it in checklist:
        if not isinstance(it, dict):
            raise ValueError("checklist item が object でない")
        item_id = it.get("id")
        if not item_id:
            raise ValueError("checklist item に id がない")
        if it.get("status") != "pending":
            continue
        deps = it.get("depends_on", []) or []
        if not isinstance(deps, list):
            raise ValueError(f"{item_id}: depends_on が配列でない")
        if all(dep in done_ids for dep in deps):
            ready.append(item_id)
    return sorted(ready, key=id_sort_key)


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        sys.stderr.write(
            "usage: ready-set-from-checklist.py <progress_json_path>\n"
            "  stdout: {\"ready\":[id,...]} (id 昇順・status==pending かつ depends_on 全 done)\n"
        )
        return 2 if argv[:1] not in (["-h"], ["--help"]) else 0
    progress_path = Path(argv[0])
    try:
        checklist = load_checklist(progress_path)
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"progress.json 読込/parse 失敗: {progress_path}: {exc}\n")
        return 2
    try:
        ready = compute_ready(checklist)
    except ValueError as exc:
        sys.stderr.write(f"checklist データ不整合: {exc}\n")
        return 1
    sys.stdout.write(json.dumps({"ready": ready}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
