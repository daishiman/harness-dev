#!/usr/bin/env python3
# /// script
# name: build-paradigm-scorecard
# purpose: Generate a paradigm x condition scorecard CSV from elegant-review findings.
# inputs:
#   - argv: findings.json and optional out.csv
# outputs:
#   - stdout: CSV when out path is omitted
#   - file: CSV when out path is provided
# contexts: [A, B, E]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""Generate paradigm x condition x score matrix as CSV.

Input : findings.json (path via argv[1])
Output: paradigm-scorecard.csv on stdout (or argv[2] if given)

stdlib only.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

EXPECTED_PARADIGMS = [
    # (id, name, category)
    (1, "critical", "A-logical"),
    (2, "deduction", "A-logical"),
    (3, "induction", "A-logical"),
    (4, "abduction", "A-logical"),
    (5, "vertical", "A-logical"),
    (6, "decomposition", "B-structural"),
    (7, "mece", "B-structural"),
    (8, "two-axis", "B-structural"),
    (9, "process", "B-structural"),
    (10, "meta", "C-meta"),
    (11, "abstraction", "C-meta"),
    (12, "double-loop", "C-meta"),
    (13, "brainstorming", "D-divergent"),
    (14, "lateral", "D-divergent"),
    (15, "paradox", "D-divergent"),
    (16, "analogy", "D-divergent"),
    (17, "if", "D-divergent"),
    (18, "naive", "D-divergent"),
    (19, "systems", "E-system"),
    (20, "causal", "E-system"),
    (21, "causal-loop", "E-system"),
    (22, "trade-on", "F-strategic"),
    (23, "plus-sum", "F-strategic"),
    (24, "value-proposition", "F-strategic"),
    (25, "strategic", "F-strategic"),
    (26, "why", "A-logical"),
    (27, "kaizen", "G-problem"),
    (28, "hypothesis", "G-problem"),
    (29, "issue", "G-problem"),
    (30, "kj", "G-problem"),
]

CONDITIONS = ["C1", "C2", "C3", "C4"]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: build-paradigm-scorecard.py <findings.json> [out.csv]", file=sys.stderr)
        return 2
    src = Path(argv[1])
    data = json.loads(src.read_text(encoding="utf-8"))
    findings = {f["paradigm_id"]: f for f in data.get("paradigm_findings", [])}
    coverage = data.get("thought_method_coverage", {})
    skipped = {
        item.get("method"): item.get("reason", "")
        for item in coverage.get("skipped_with_reason", [])
        if isinstance(item, dict)
    }
    missing = [
        pid
        for pid, name, _ in EXPECTED_PARADIGMS
        if pid not in findings and name not in skipped
    ]
    if missing:
        print(f"missing paradigm_findings ids: {missing}", file=sys.stderr)
        return 1

    out_stream = open(argv[2], "w", encoding="utf-8", newline="") if len(argv) >= 3 else sys.stdout
    writer = csv.writer(out_stream)
    writer.writerow(["paradigm_id", "paradigm_name", "category", *CONDITIONS, "score", "skip_reason"])
    for pid, name, cat in EXPECTED_PARADIGMS:
        if pid not in findings:
            writer.writerow([pid, name, cat, *("SKIP" for _ in CONDITIONS), "", skipped.get(name, "")])
            continue
        f = findings[pid]
        issues = f.get("issues", [])
        cond_flags = {c: "PASS" for c in CONDITIONS}
        for iss in issues:
            c = iss.get("condition")
            if c in cond_flags:
                cond_flags[c] = "FAIL"
        score = f.get("score", 0.0)
        writer.writerow([pid, name, cat, *(cond_flags[c] for c in CONDITIONS), score, ""])
    if out_stream is not sys.stdout:
        out_stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
