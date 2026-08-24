#!/usr/bin/env python3
# /// script
# name: validate-goal-seek-runtime
# purpose: Validate goal-spec, progress, and intermediate JSONL as one fail-closed anchor.
# inputs: ["argv: --goal-spec FILE --progress FILE --intermediate FILE", "argv: --goal-spec-json JSON --progress-json JSON --intermediate-jsonl JSONL"]
# outputs: ["stdout: JSON PASS receipt"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [C, E]
# network: false
# write-scope: none
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, dump, load_json


REQUIRED_ROW_KEYS = {
    "iteration",
    "original_goal",
    "original_goal_hash",
    "current_goal_snapshot",
    "delta_from_original",
    "merged_directive_for_next",
    "drift_signal",
}


def _validate_values(goal_spec: Any, progress: Any, rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ContractError("intermediate rows must be an array")
    goal = goal_spec.get("original_goal") if isinstance(goal_spec, dict) else None
    if not isinstance(goal, str) or not goal.strip():
        raise ContractError("goal-spec original_goal must be non-empty")
    expected = hashlib.sha256(goal.encode("utf-8")).hexdigest()
    if goal_spec.get("original_goal_hash") != expected:
        raise ContractError("goal-spec original_goal_hash mismatch")
    if not isinstance(progress, dict) or progress.get("original_goal_hash") != expected:
        raise ContractError("progress original_goal_hash mismatch")
    checklist = progress.get("checklist")
    if not isinstance(checklist, dict) or not checklist:
        raise ContractError("progress checklist must be a non-empty object")
    if not rows:
        raise ContractError("intermediate JSONL is empty")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ContractError(f"intermediate[{index}] must be an object")
        missing = sorted(REQUIRED_ROW_KEYS - row.keys())
        if missing:
            raise ContractError(f"intermediate[{index}] missing keys: {missing}")
        if row["original_goal"] != goal or row["original_goal_hash"] != expected:
            raise ContractError(f"intermediate[{index}] goal anchor drift")
    return {
        "valid": True,
        "original_goal_hash": expected,
        "iterations": len(rows),
        "checklist_items": len(checklist),
    }


def validate(goal_spec_path: Path, progress_path: Path, intermediate_path: Path) -> dict[str, Any]:
    for path in (goal_spec_path, progress_path, intermediate_path):
        if not path.is_file():
            raise ContractError(f"goal anchor artifact missing: {path}")
    goal_spec = load_json(goal_spec_path)
    progress = load_json(progress_path)
    try:
        rows = [
            json.loads(line)
            for line in intermediate_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid intermediate JSONL: {exc}") from exc
    return _validate_values(goal_spec, progress, rows)


def validate_memory(goal_spec_json: str, progress_json: str, intermediate_jsonl: str) -> dict[str, Any]:
    try:
        goal_spec = json.loads(goal_spec_json)
        progress = json.loads(progress_json)
        rows = [json.loads(line) for line in intermediate_jsonl.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid in-memory goal anchor JSON: {exc}") from exc
    return _validate_values(goal_spec, progress, rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal-spec")
    parser.add_argument("--progress")
    parser.add_argument("--intermediate")
    parser.add_argument("--goal-spec-json")
    parser.add_argument("--progress-json")
    parser.add_argument("--intermediate-jsonl")
    args = parser.parse_args()
    file_values = (args.goal_spec, args.progress, args.intermediate)
    memory_values = (args.goal_spec_json, args.progress_json, args.intermediate_jsonl)
    if all(file_values) and not any(memory_values):
        report = validate(Path(args.goal_spec), Path(args.progress), Path(args.intermediate))
    elif all(value is not None for value in memory_values) and not any(file_values):
        report = validate_memory(args.goal_spec_json, args.progress_json, args.intermediate_jsonl)
    else:
        raise ContractError("provide exactly one complete goal anchor input mode: files or in-memory values")
    dump(report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
