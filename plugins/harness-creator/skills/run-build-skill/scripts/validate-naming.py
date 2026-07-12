#!/usr/bin/env python3
# /// script
# name: validate-naming
# purpose: Validate skill name kebab-case and allowed prefix before rendering.
# inputs:
#   - argv: skill-name
# outputs:
#   - stdout: ok
#   - stderr: validation errors
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Quick naming validator (subset of lint-skill-name.py for pre-flight checks)."""
from __future__ import annotations
import re
import sys

PREFIXES = ("run-", "ref-", "assign-", "wrap-", "delegate-")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: validate-naming.py <skill-name>", file=sys.stderr)
        return 2
    name = sys.argv[1]
    errors = []
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        errors.append("第1条: kebab-case違反")
    if not any(name.startswith(p) for p in PREFIXES):
        errors.append(f"第2条: prefix({'|'.join(PREFIXES)})なし")
    if len(name) > 60:
        errors.append("第5条: 60文字超過")
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
