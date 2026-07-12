#!/usr/bin/env python3
# /// script
# name: evaluate-create-gates
# purpose: Evaluate fast-mode and elegant-review gates for run-skill-create.
# inputs:
#   - argv: --skill-name, --kind, --brief, --fast
# outputs:
#   - stdout: gate decision JSON
#   - stderr: git or JSON errors
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: [git]
# requires-python: ">=3.10"
# ///
"""Evaluate run-skill-create gates with Python stdlib only."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], check=False, stdout=subprocess.PIPE, text=True)
    return proc.stdout


def diff_lines(path: str) -> int:
    stat = git(["diff", "--shortstat", "--", path])
    return sum(int(match) for match in re.findall(r"(\d+) insertion|(\d+) deletion", stat) for match in match if match)


def changed_files(path: str) -> int:
    return len([line for line in git(["diff", "--name-only", "--", path]).splitlines() if line.strip()])


def is_new_skill(path: str) -> bool:
    tracked = git(["ls-files", path]).strip()
    untracked = git(["ls-files", "--others", "--exclude-standard", path]).strip()
    return bool(untracked) and not bool(tracked)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-name", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--brief", default="eval-log/skill-brief.json")
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    target = f"plugins/harness-creator/skills/{args.skill_name}/"
    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    lines = diff_lines(target)
    files = changed_files(target)
    pair_required = bool(brief.get("generate_pair_evaluator") or brief.get("needs_independent_context"))
    fast_allowed = (
        args.fast
        and files == 1
        and lines <= 30
        and args.kind in {"ref", "wrap"}
        and not pair_required
    )
    result = {
        "target": target,
        "changed_files": files,
        "diff_lines": lines,
        "new_skill": is_new_skill(target),
        "pair_required": pair_required,
        "fast_allowed": fast_allowed,
        "elegant_review_required": is_new_skill(target) or lines > 30,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
