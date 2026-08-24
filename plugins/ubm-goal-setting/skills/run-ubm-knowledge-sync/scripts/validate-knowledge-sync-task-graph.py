#!/usr/bin/env python3
# /// script
# name: validate-knowledge-sync-task-graph
# purpose: run-ubm-knowledge-sync の checklist と intermediate trace から各周回の ready 全集合を再計算し、C1→C6 の依存順消費を fail-closed 検証する。
# inputs:
#   - argv: <progress.json> <intermediate.jsonl>
# outputs:
#   - stdout: PASS 要約
#   - stderr: 契約違反
#   - exit: 0=PASS / 1=contract violation / 2=usage or IO/JSON error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""UBM knowledge sync 縮小 task graph の依存順消費を検証する。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REQUIRED_CHAIN = ("C1", "C2", "C3", "C4", "C5", "C6")
REQUIRED_KEYS = {"iteration", "ready_set", "selected_item"}
ID_RE = re.compile(r"^C([0-9]+)$")
STATUSES = {"pending", "done", "blocked"}


def _sort_key(item_id: str) -> tuple[int, int, str]:
    match = ID_RE.fullmatch(item_id)
    return (0, int(match.group(1)), item_id) if match else (1, 0, item_id)


def _cycle(deps_of: dict[str, list[str]]) -> str | None:
    white, grey, black = 0, 1, 2
    color = {item_id: white for item_id in deps_of}
    for start in deps_of:
        if color[start] != white:
            continue
        color[start] = grey
        stack: list[tuple[str, list[str]]] = [(start, list(deps_of[start]))]
        while stack:
            node, pending = stack[-1]
            if pending:
                dependency = pending.pop()
                if color[dependency] == grey:
                    return f"{node} -> {dependency}"
                if color[dependency] == white:
                    color[dependency] = grey
                    stack.append((dependency, list(deps_of[dependency])))
            else:
                color[node] = black
                stack.pop()
    return None


def validate(progress_path: Path, trace_path: Path) -> tuple[int, str]:
    if not progress_path.is_file() or not trace_path.is_file():
        return 1, "progress/intermediate が不在（task-graph trace の absence-as-violation）"
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        rows = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        return 2, f"JSON を読めない: {exc}"
    if not isinstance(progress, dict) or not rows or not all(isinstance(row, dict) for row in rows):
        return 1, "progress は object、intermediate は非空 object JSONL が必要"
    if progress.get("engine") != "task-graph":
        return 1, "progress.engine が task-graph でない"

    checklist = progress.get("checklist")
    if not isinstance(checklist, list) or not checklist:
        return 1, "checklist が非空配列でない"
    deps_of: dict[str, list[str]] = {}
    status_of: dict[str, str] = {}
    available_from: dict[str, int] = {}
    for index, item in enumerate(checklist):
        if not isinstance(item, dict):
            return 1, f"checklist[{index}] が object でない"
        item_id = item.get("id")
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            return 1, f"checklist[{index}].id が ^C[0-9]+$ に非準拠"
        if item_id in deps_of:
            return 1, f"checklist id 重複: {item_id}"
        dependencies = item.get("depends_on", []) or []
        if not isinstance(dependencies, list) or not all(isinstance(dep, str) for dep in dependencies):
            return 1, f"{item_id}: depends_on が string[] でない"
        status = item.get("status")
        if status not in STATUSES:
            return 1, f"{item_id}: status 不正: {status!r}"
        created = item.get("created_iteration", 0)
        available = item.get("available_from_iteration", created)
        if isinstance(created, bool) or not isinstance(created, int) or created < 0:
            return 1, f"{item_id}: created_iteration が非負整数でない"
        if isinstance(available, bool) or not isinstance(available, int) or available < created:
            return 1, f"{item_id}: available_from_iteration が created_iteration 以上でない"
        deps_of[item_id] = dependencies
        status_of[item_id] = status
        available_from[item_id] = available

    known = set(deps_of)
    for item_id, dependencies in deps_of.items():
        dangling = sorted(set(dependencies) - known, key=_sort_key)
        if dangling:
            return 1, f"{item_id}: dangling depends_on: {dangling}"
    cycle = _cycle(deps_of)
    if cycle:
        return 1, f"depends_on cycle: {cycle}"
    for index, item_id in enumerate(REQUIRED_CHAIN):
        expected = [] if index == 0 else [REQUIRED_CHAIN[index - 1]]
        if deps_of.get(item_id) != expected:
            return 1, f"required chain drift: {item_id} depends_on={deps_of.get(item_id)!r} expected={expected!r}"

    iteration = progress.get("iteration")
    max_loops = progress.get("max_loops")
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 0:
        return 1, "progress.iteration が非負整数でない"
    if isinstance(max_loops, bool) or not isinstance(max_loops, int) or max_loops < 1:
        return 1, "progress.max_loops が正整数でない"
    if progress.get("status") not in {"in_progress", "completed", "handed_off"}:
        return 1, f"progress.status 不正: {progress.get('status')!r}"
    if len(checklist) > max_loops:
        return 1, f"bound 不足: checklist={len(checklist)} > max_loops={max_loops}"
    if len(rows) > max_loops:
        return 1, f"bound 超過: trace rows={len(rows)} > max_loops={max_loops}"
    if iteration != len(rows) - 1:
        return 1, f"progress.iteration={iteration} != trace 最終周回={len(rows) - 1}"

    selected_sequence: list[str] = []
    for index, row in enumerate(rows):
        missing = sorted(REQUIRED_KEYS - row.keys())
        if missing:
            return 1, f"intermediate[{index}] required keys 不足: {missing}"
        if row.get("iteration") != index:
            return 1, f"intermediate[{index}].iteration が {index} でない"
        declared_ready = row.get("ready_set")
        selected = row.get("selected_item")
        if not isinstance(declared_ready, list) or not all(isinstance(item_id, str) for item_id in declared_ready):
            return 1, f"intermediate[{index}].ready_set が string[] でない"
        if len(set(declared_ready)) != len(declared_ready):
            return 1, f"intermediate[{index}].ready_set が重複"

        consumed = set(selected_sequence)
        computed_ready = sorted(
            (
                item_id
                for item_id, dependencies in deps_of.items()
                if item_id not in consumed
                and index >= available_from[item_id]
                and status_of[item_id] != "blocked"
                and all(dependency in consumed for dependency in dependencies)
            ),
            key=_sort_key,
        )
        # C6 is the final completion gate.  A reflected C7+ item can become
        # available in the same or a later iteration after C5.  If C6 were
        # selected by ordinary numeric order, that reflected work would be
        # validated before it ran.  Defer C6 until every other item has been
        # consumed; a future-available item therefore produces an empty
        # effective ready set rather than allowing the gate to jump ahead.
        if any(item_id != "C6" and item_id not in consumed for item_id in deps_of):
            computed_ready = [item_id for item_id in computed_ready if item_id != "C6"]
        if declared_ready != computed_ready:
            return 1, f"intermediate[{index}].ready_set 不整合: declared={declared_ready}, computed={computed_ready}"
        if computed_ready:
            if not isinstance(selected, str) or not selected:
                return 1, f"intermediate[{index}] ready 非空だが selected_item 不在"
            if selected != computed_ready[0]:
                return 1, f"intermediate[{index}].selected_item={selected} != ready 最小 id {computed_ready[0]}"
            if selected in consumed:
                return 1, f"intermediate[{index}].selected_item 重複: {selected}"
            if status_of[selected] != "done":
                return 1, f"intermediate[{index}].selected_item={selected} がdoneでない"
            for dependency in deps_of[selected]:
                if dependency not in consumed or status_of[dependency] != "done":
                    return 1, f"intermediate[{index}] {selected} の依存 {dependency} が過去周回で done でない"
            selected_sequence.append(selected)
        elif selected not in (None, ""):
            return 1, f"intermediate[{index}] ready 空だが selected_item={selected!r}"

    selected_set = set(selected_sequence)
    missing_done = sorted(
        (item_id for item_id, status in status_of.items() if status == "done" and item_id not in selected_set),
        key=_sort_key,
    )
    if missing_done:
        return 1, f"done だが selected_item 証跡なし: {missing_done}"
    if "C6" in selected_set and selected_sequence[-1] != "C6":
        return 1, "completion gate C6 が最後の selected_item でない"
    if progress.get("status") == "completed":
        unfinished = sorted(
            (item_id for item_id, status in status_of.items() if status != "done"),
            key=_sort_key,
        )
        if unfinished:
            return 1, f"completed だが pending/blocked 残: {unfinished}"
    return 0, f"knowledge-sync task-graph PASS: iterations={len(rows)} checklist={len(checklist)}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: validate-knowledge-sync-task-graph.py <progress.json> <intermediate.jsonl>\n")
        return 2
    code, message = validate(Path(argv[0]), Path(argv[1]))
    (sys.stdout if code == 0 else sys.stderr).write(message + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
