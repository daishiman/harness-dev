#!/usr/bin/env python3
# /// script
# name: hook-validate-skill-md
# purpose: Validate SKILL.md frontmatter on FileChanged; warn-only.
# inputs:
#   - stdin: Claude Code FileChanged hook JSON
# outputs:
#   - stderr: warnings / exit 0
# contexts: [C]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""FileChanged hook: if the changed file is a SKILL.md, run validate-frontmatter.py.
Always returns 0; emits warnings on stderr only.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path


VALIDATOR = Path("scripts/validate-frontmatter.py")


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0
    fp = data.get("file_path") or (data.get("tool_input") or {}).get("file_path", "")
    if not fp.endswith("SKILL.md"):
        return 0
    if not Path(fp).exists() or not VALIDATOR.exists():
        return 0
    try:
        r = subprocess.run(
            ["python3", str(VALIDATOR), fp],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            sys.stderr.write(
                f"hook-validate-skill-md: warnings for {fp}\n{r.stderr}{r.stdout}\n"
            )
    except Exception as e:
        sys.stderr.write(f"hook-validate-skill-md: skipped ({e})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
