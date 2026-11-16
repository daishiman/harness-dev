#!/usr/bin/env python3
# /// script
# name: validate-inline-goal-seek-anchor
# purpose: goal-seek progress と intermediate JSONL の不変ゴールアンカーを fail-closed 検証する。
# inputs:
#   - argv: <progress.json> <intermediate.jsonl>
# outputs:
#   - stdout: PASS 要約
#   - stderr: 契約違反
#   - exit: 0=PASS / 1=contract violation (progress・intermediate のどちらかが無い・ファイルでない場合を含む。
#     周回の証跡が無いことは違反として扱う) / 2=引数の誤り、または在るファイルを JSON として読めない
#     (非 UTF-8・壊れた JSON・深すぎる入れ子・読み取りの OS エラー)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""goal-seek の original_goal 不変性と SHA-256 固定を検証する。

progress に周回数 (iteration) があるときは、intermediate の最後の iteration と一致することも確かめる
(周回の記録漏れの検出)。original_goal と progress の hash を同時に書き換えた改ざんは、比べる外部の正本が
無いので検出できない。
"""

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
    except (OSError, ValueError, RecursionError) as exc:
        # ValueError は JSONDecodeError と UnicodeDecodeError（UTF-16 や 0xff 始まり）の両方を含む。
        # RecursionError は極端に深い入れ子の JSON。どれも宣言どおり exit 2 で返し、traceback を出さない。
        return 2, f"JSON を読めない: {type(exc).__name__}: {exc}"
    if not isinstance(progress, dict):
        return 1, "progress が object でない"
    if not rows:
        return 1, "intermediate.jsonl が空"
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return 1, f"intermediate[{index}] が object でない"
        missing = sorted(REQUIRED_KEYS - row.keys())
        if missing:
            return 1, f"intermediate[{index}] required_keys 不足: {missing}"
        iteration = row["iteration"]
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 0:
            return 1, f"intermediate[{index}] の iteration が 0 以上の整数でない: {iteration!r}"
        if index and iteration != rows[index - 1]["iteration"] + 1:
            return 1, f"intermediate[{index}] の iteration が連番でない: {rows[index - 1]['iteration']} の次が {iteration}"
    if "iteration" in progress:
        recorded = progress["iteration"]
        if isinstance(recorded, bool) or not isinstance(recorded, int):
            return 1, f"progress の iteration が整数でない: {recorded!r}"
        if recorded != rows[-1]["iteration"]:
            return 1, f"progress の iteration={recorded} が intermediate の最後の iteration={rows[-1]['iteration']} と一致しない"
    anchor = rows[0]["original_goal"]
    if not isinstance(anchor, str):
        return 1, f"original_goal が文字列でない: {type(anchor).__name__}"
    if not anchor.strip():
        return 1, "original_goal が空"
    if any(row["original_goal"] != anchor for row in rows):
        return 1, "original_goal が周回間で drift"
    try:
        encoded = anchor.encode("utf-8")
    except UnicodeEncodeError:
        # JSON の "\\ud800" のような対になっていない surrogate は、UTF-8 で表せず hash を固定できない
        return 1, "original_goal に UTF-8 で表せない文字 (対になっていない surrogate) がある"
    expected = hashlib.sha256(encoded).hexdigest()
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
