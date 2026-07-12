#!/usr/bin/env python3
# /// script
# name: lint-external-refs
# purpose: Inventory SKILL.md references that point outside plugin boundaries.
# inputs:
#   - --skills-dir: directory containing skill subdirectories
#   - --json: emit machine-readable JSON
#   - --fail-on-external: exit 1 when external references are found
# outputs:
#   - stdout: inventory report
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""SKILL.md の外部参照を棚卸しする。

34章 Phase 0 の「全 SKILL.md 外部参照棚卸し」を機械化するための最小 lint。
plugin 移行前は report として使い、plugin 境界確定後は --fail-on-external で gate 化する。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


DEFAULT_ALLOWED_PREFIXES = (
    ".claude/",
    "eval-log/",
    "references/",
    "scripts/",
)

PATH_RE = re.compile(
    r"(?P<path>(?:\.claude|scripts|doc|references|eval-log|plugins)/"
    r"[A-Za-z0-9_\-./一-龠ぁ-んァ-ンー]+)"
)


def scan_skill(path: pathlib.Path, allowed_prefixes: tuple[str, ...]) -> dict:
    text = path.read_text(encoding="utf-8")
    refs = []
    for match in PATH_RE.finditer(text):
        ref = match.group("path").rstrip(").,`\"'")
        external = not ref.startswith(allowed_prefixes)
        refs.append(
            {
                "ref": ref,
                "line": text.count("\n", 0, match.start()) + 1,
                "external": external,
            }
        )
    return {
        "skill": path.parent.name,
        "path": str(path),
        "refs": refs,
        "external_refs": [r for r in refs if r["external"]],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-dir", default="plugins/harness-creator/skills")
    parser.add_argument("--allowed-prefix", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-external", action="store_true")
    args = parser.parse_args(argv[1:])

    skills_dir = pathlib.Path(args.skills_dir)
    allowed = tuple(args.allowed_prefix or DEFAULT_ALLOWED_PREFIXES)
    reports = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        reports.append(scan_skill(skill_md, allowed))

    external_total = sum(len(r["external_refs"]) for r in reports)
    payload = {
        "skills_dir": str(skills_dir),
        "allowed_prefixes": list(allowed),
        "skills_scanned": len(reports),
        "external_ref_count": external_total,
        "reports": reports,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"skills_scanned={payload['skills_scanned']} "
            f"external_ref_count={external_total}"
        )
        for report in reports:
            for ref in report["external_refs"]:
                print(f"EXTERNAL {report['skill']}:{ref['line']} {ref['ref']}")

    return 1 if args.fail_on_external and external_total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
