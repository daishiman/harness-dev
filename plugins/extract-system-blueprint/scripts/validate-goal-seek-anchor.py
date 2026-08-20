#!/usr/bin/env python3
# /// script
# name: validate-goal-seek-anchor
# purpose: Goal-seek intermediate JSONL の必須キーと original_goal 不変性を共有検証する。
# inputs:
#   - argv: --intermediate <repo-root-relative JSONL path>
# outputs:
#   - stdout: validation summary
#   - exit: 0=valid, 1=invalid, 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Shared goal-seek anchor validator for extract-system-blueprint skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


REQUIRED_KEYS = {"original_goal", "merged_directive_for_next", "delta_from_original"}


def _repo_root() -> Path:
    try:
        return Path(
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], text=True
            ).strip()
        )
    except (OSError, subprocess.SubprocessError):
        return Path.cwd()


def validate(path: Path) -> int:
    if not path.exists():
        # 呼び出し側は必ず JSONL 追記後に本 validator を起動する配線のため、
        # パス不在は「検証対象なし」ではなく配線バグ。fail-closed で遮断する。
        print(f"goal-seek intermediate invalid: file not found: {path}")
        return 1
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        print(f"goal-seek intermediate invalid: {exc}")
        return 1
    if not rows:
        print("goal-seek intermediate OK: 0 rows")
        return 0
    base = hashlib.sha256(rows[0]["original_goal"].encode("utf-8")).hexdigest()
    if not all(REQUIRED_KEYS <= set(row) for row in rows):
        print("goal-seek intermediate invalid: missing required_keys")
        return 1
    if not all(
        hashlib.sha256(row["original_goal"].encode("utf-8")).hexdigest() == base
        for row in rows
    ):
        print("goal-seek intermediate invalid: original_goal_hash drift")
        return 1
    print(f"goal-seek intermediate OK: {len(rows)} rows")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intermediate", required=True)
    args = parser.parse_args()
    return validate(_repo_root() / args.intermediate)


if __name__ == "__main__":
    raise SystemExit(main())
