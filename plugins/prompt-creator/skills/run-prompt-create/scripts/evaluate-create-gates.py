#!/usr/bin/env python3
# /// script
# name: evaluate-create-gates
# purpose: run-prompt-create の elegant-review 起動可否 / fast_mode 適用可否をファイル状態のみで機械決定する
# inputs:
#   - argv: --prompt-name <name>, --brief <path>, --output <path>, --fast, --threshold <int>
#   - file: brief JSON (output_path 推定用), git diff --numstat HEAD
# outputs:
#   - stdout: 判定 JSON {"elegant_review_required": bool, "fast_mode": bool, "diff_lines": int, "reasons": [...]}
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""evaluate-create-gates.py

run-prompt-create の Step 4 (elegant-review) 起動可否 / fast_mode 適用可否を
機械決定する補助スクリプト。LLM 判断で揺れないようファイル状態のみで判定する。

判定基準:
- new prompt (target output file が存在しない) → elegant-review 必須
- diff_lines > 30 (target output に対する変更行数) → elegant-review 必須
- --fast 指定 かつ 上記いずれも該当しない → fast_mode 適用 (skip design-evaluate, elegant-review)
- それ以外 → 通常フロー (elegant-review skip 可)

出力: stdout に JSON {"elegant_review_required": bool, "fast_mode": bool, "reasons": [...]}, exit 0
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def diff_lines(path: Path) -> int:
    """git diff の追加削除行合計を返す。トラッキング外なら全行を追加扱い。"""
    if not path.exists():
        return 0
    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", "HEAD", "--", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return 0
    if result.returncode != 0 or not result.stdout.strip():
        # untracked
        try:
            return sum(1 for _ in path.open("r", encoding="utf-8"))
        except OSError:
            return 0
    added, deleted, _ = (result.stdout.strip().split("\t") + ["0", "0", ""])[:3]
    try:
        return int(added) + int(deleted)
    except ValueError:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-name", required=True)
    parser.add_argument("--brief", default="eval-log/prompt-brief.json")
    parser.add_argument("--output", default=None, help="判定対象の出力ファイル (省略時は brief から推定)")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--threshold", type=int, default=30)
    args = parser.parse_args()

    reasons: list[str] = []

    brief_path = Path(args.brief)
    output_path: Path | None = None
    if args.output:
        output_path = Path(args.output)
    elif brief_path.exists():
        try:
            data = json.loads(brief_path.read_text(encoding="utf-8"))
            if data.get("output_path"):
                output_path = Path(data["output_path"])
        except json.JSONDecodeError:
            pass

    new_prompt = output_path is None or not output_path.exists()
    lines = 0 if new_prompt or output_path is None else diff_lines(output_path)

    if new_prompt:
        reasons.append("new_prompt")
    if lines > args.threshold:
        reasons.append(f"diff_lines={lines}>{args.threshold}")

    elegant_required = bool(reasons)

    fast_mode = False
    if args.fast and not elegant_required:
        fast_mode = True
        reasons.append("fast_mode_applied")

    payload = {
        "prompt_name": args.prompt_name,
        "elegant_review_required": elegant_required,
        "fast_mode": fast_mode,
        "diff_lines": lines,
        "reasons": reasons,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
