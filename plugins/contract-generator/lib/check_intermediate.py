#!/usr/bin/env python3
# /// script
# name: check_intermediate
# purpose: ゴールシーク周回アンカー(intermediate.jsonl + progress.json)の整合性を SSOT で検査する。SKILL.md heredoc 重複を解消するための共通検査。
# inputs:
#   - argv: <skill-name> [--eval-log-dir DIR] [--required-keys k1,k2,...]
# outputs:
#   - 整合: stdout に "OK: <skill-name>"
#   - 不整合: stderr に違反列挙 + exit 2
# contexts: [C]
# network: none
# write-scope: eval-log/*
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: SKILL.md 内に重複していた Python heredoc を SSOT 化する。

検査項目:
  1. eval-log/{skill}-intermediate.jsonl の末尾行に original_goal が存在し、
     progress.json の original_goal_hash と sha256 一致すること(不変アンカー)。
  2. 末尾行に required_keys(既定: iteration / original_goal / current_goal_snapshot /
     delta_from_original / merged_directive_for_next / drift_signal) が全て揃うこと。
  3. progress.json の iteration / remaining と intermediate.jsonl 末尾行の整合。

不整合は stderr に列挙し exit 2、整合なら stdout に "OK: <skill>" を出して exit 0。
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

DEFAULT_REQUIRED_KEYS = [
    "iteration",
    "original_goal",
    "current_goal_snapshot",
    "delta_from_original",
    "merged_directive_for_next",
    "drift_signal",
]


def _read_last_jsonl(path: Path):
    last = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    if last is None:
        return None
    return json.loads(last)


def check(skill: str, eval_log_dir: Path, required_keys: list[str],
          allow_missing: bool = False) -> tuple[list[str], list[str]]:
    """整合検査。返り値は (violations, warnings)。

    allow_missing=True の場合、eval-log/{skill}-intermediate.jsonl /
    {skill}-progress.json の不在を violations ではなく warnings に降格する
    (CI dry-run / 初回起動向け)。デフォルト False は従来通り厳格。
    """
    violations: list[str] = []
    warnings: list[str] = []
    inter = eval_log_dir / f"{skill}-intermediate.jsonl"
    prog = eval_log_dir / f"{skill}-progress.json"

    missing: list[str] = []
    if not inter.exists():
        missing.append(f"intermediate.jsonl 不在: {inter}")
    if not prog.exists():
        missing.append(f"progress.json 不在: {prog}")
    if missing:
        if allow_missing:
            warnings.extend(missing)
            return violations, warnings
        violations.extend(missing)
        return violations, warnings

    last = _read_last_jsonl(inter)
    if last is None:
        violations.append(f"intermediate.jsonl が空: {inter}")
        return violations, warnings

    missing_keys = [k for k in required_keys if k not in last]
    if missing_keys:
        violations.append(f"末尾entry に required_keys 欠落: {missing_keys}")

    prog_data = json.loads(prog.read_text(encoding="utf-8"))

    og = last.get("original_goal")
    if og is None:
        violations.append("末尾entry に original_goal 欠落 → 不変アンカー検証不可")
    else:
        og_hash = hashlib.sha256(og.encode("utf-8")).hexdigest()
        recorded = prog_data.get("original_goal_hash")
        if recorded and recorded != og_hash:
            violations.append(
                f"original_goal_hash 不一致 (アンカー破損): progress={recorded[:12]}... "
                f"vs intermediate={og_hash[:12]}..."
            )

    if "iteration" in last and "iteration" in prog_data:
        if last["iteration"] != prog_data["iteration"]:
            violations.append(
                f"iteration 不整合: progress={prog_data['iteration']} "
                f"vs intermediate末尾={last['iteration']}"
            )

    signal = last.get("drift_signal")
    remaining = prog_data.get("remaining")
    if signal == "aligned" and remaining not in (0, None):
        violations.append(f"drift_signal=aligned だが remaining={remaining} (status と矛盾)")

    return violations, warnings


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("skill", help="検査対象 skill 名 (例: run-contract-generate)")
    p.add_argument("--eval-log-dir", default="eval-log",
                   help="intermediate.jsonl / progress.json の置場所 (既定: eval-log)")
    p.add_argument("--required-keys", default=",".join(DEFAULT_REQUIRED_KEYS),
                   help="末尾entryに必須のキー(カンマ区切り)")
    p.add_argument("--allow-missing", action="store_true",
                   help="eval-log 不在を violations ではなく warning に降格し exit 0 (CI smoke 用)")
    a = p.parse_args()

    keys = [k.strip() for k in a.required_keys.split(",") if k.strip()]
    violations, warnings = check(a.skill, Path(a.eval_log_dir), keys, a.allow_missing)
    for w in warnings:
        print(f"WARN: {a.skill}: {w}", file=sys.stderr)
    if violations:
        print(f"NG: {a.skill}", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 2
    print(f"OK: {a.skill}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
