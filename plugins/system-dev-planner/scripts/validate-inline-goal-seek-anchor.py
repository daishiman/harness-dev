#!/usr/bin/env python3
# /// script
# name: validate-inline-goal-seek-anchor
# purpose: goal-seek progress と intermediate JSONL の不変ゴールアンカーを fail-closed 検証する。
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
"""goal-seek の original_goal 不変性と SHA-256 固定を検証する。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REQUIRED_KEYS = {
    "iteration",
    "original_goal",
    "current_goal_snapshot",
    "delta_from_original",
    "merged_directive_for_next",
    "drift_signal",
}


def validate(progress_path: Path, intermediate_path: Path) -> tuple[int, str]:
    if not progress_path.is_file() or not intermediate_path.is_file():
        return 1, "progress/intermediate が不在（周回証跡の absence-as-violation）"
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        rows = [
            json.loads(line)
            for line in intermediate_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        return 2, f"JSON を読めない: {exc}"
    if not rows:
        return 1, "intermediate.jsonl が空"
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return 1, f"intermediate[{index}] が object でない"
        missing = sorted(REQUIRED_KEYS - row.keys())
        if missing:
            return 1, f"intermediate[{index}] required_keys 不足: {missing}"
    anchor = rows[0]["original_goal"]
    if not isinstance(anchor, str) or not anchor.strip():
        return 1, "original_goal が空"
    if any(row["original_goal"] != anchor for row in rows):
        return 1, "original_goal が周回間で drift"
    expected = hashlib.sha256(anchor.encode("utf-8")).hexdigest()
    actual = progress.get("original_goal_hash")
    if actual != expected:
        return 1, f"original_goal_hash missing/drift: {actual!r} != {expected}"
    return 0, f"goal-seek anchor PASS: iterations={len(rows)} sha256={expected}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: validate-inline-goal-seek-anchor.py <progress.json> <intermediate.jsonl>\n")
        return 2
    code, message = validate(Path(argv[0]), Path(argv[1]))
    stream = sys.stdout if code == 0 else sys.stderr
    stream.write(message + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
