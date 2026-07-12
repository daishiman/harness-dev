#!/usr/bin/env python3
# /// script
# name: hook-verify-evaluator-json
# purpose: Check that assign-* subagents emit the evaluator JSON contract.
# inputs:
#   - stdin: Claude Code SubagentStop hook JSON
# outputs:
#   - stdout: violation list / exit 0=OK 2=violation
# contexts: [D]
# network: false
# write-scope: none
# dependencies: []
# ///
"""SubagentStop hook: when subagent name matches assign-*, verify last STDOUT
JSON contains score/findings/passed/threshold.
Exit 2 (block) when contract is violated — was warn-only (exit 0) before.
patch: PF-E2-001 — exit 2 化 (C3+C4)
"""
from __future__ import annotations
import json
import re
import sys


REQUIRED_KEYS = {
    "rubric_id",
    "rubric_version",
    "rubric_hash",
    "target",
    "score",
    "threshold",
    "passed",
    "findings",
    "required_fixes",
    "machine_checks",
}


def extract_json(text: str) -> dict | None:
    # try whole text first
    try:
        return json.loads(text)
    except Exception:
        pass
    # try last {...} block
    matches = re.findall(r"\{[\s\S]*\}", text or "")
    for m in reversed(matches):
        try:
            return json.loads(m)
        except Exception:
            continue
    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0
    name = (data.get("subagent_name") or data.get("agent") or
            data.get("subagent_type") or "")
    if not isinstance(name, str) or not name.startswith("assign-") or "evaluator" not in name:
        return 0
    output = (data.get("stdout") or data.get("output") or
              data.get("response") or "")
    parsed = extract_json(output)
    if not parsed:
        sys.stderr.write(
            f"hook-verify-evaluator-json: subagent {name} produced no parseable JSON\n"
        )
        # exit 2: block — contract violation (PF-E2-001)
        return 2
    missing = REQUIRED_KEYS - set(parsed.keys())
    if missing:
        sys.stderr.write(
            f"hook-verify-evaluator-json: {name} JSON missing keys {sorted(missing)}\n"
        )
        # exit 2: block — contract violation (PF-E2-001)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
