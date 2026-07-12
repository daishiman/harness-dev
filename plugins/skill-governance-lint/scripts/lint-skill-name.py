#!/usr/bin/env python3
# /// script
# name: lint-skill-name
# purpose: Lint skill names against naming convention articles.
# inputs:
#   - argv: SKILL.md path or --skills-dir
# outputs:
#   - stdout: OK status
#   - stderr: naming findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Lint Skill name against articles 第1〜5,7条.

Usage:
  lint-skill-name.py /path/to/SKILL.md
  lint-skill-name.py --skills-dir plugins/harness-creator/skills

Exit 0 = ok, 1 = violation, 2 = usage error.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

PREFIXES = ("run-", "ref-", "assign-", "wrap-", "delegate-")
ASSIGN_ROLE_SUFFIXES = ("evaluator", "generator", "contributor", "delegate")
RESERVED = {"skill", "claude", "anthropic"}
FORBIDDEN_PREFIX = ("test-", "tmp-", "wip-", "experimental-")
KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out: dict[str, str] = {}
    for line in parts[1].splitlines():
        m = re.match(r"^([a-zA-Z_-]+):\s*(.+?)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def lint_file(p: Path) -> list[str]:
    if not p.exists():
        return [f"not found: {p}"]

    text = p.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    name = fm.get("name")
    if not name:
        return ["frontmatter.name not found"]
    dir_name = p.parent.name

    errs: list[str] = []

    # 第1条 kebab-case
    if not KEBAB_RE.fullmatch(name):
        errs.append(f"第1条違反: '{name}' is not kebab-case")

    # 第2条 prefix
    if not any(name.startswith(pp) for pp in PREFIXES):
        errs.append(f"第2条違反: name must start with one of {PREFIXES}")

    # 第5条 role-suffix
    if name.startswith("assign-"):
        suffixes = [suffix for suffix in ASSIGN_ROLE_SUFFIXES if name.endswith(f"-{suffix}")]
        if len(suffixes) != 1:
            errs.append(
                "第5条違反: assign-* must end with one role suffix "
                f"{ASSIGN_ROLE_SUFFIXES}"
            )
        role_suffix = fm.get("role_suffix")
        if role_suffix and suffixes and role_suffix != suffixes[0]:
            errs.append(f"第5条違反: role_suffix '{role_suffix}' != name suffix '{suffixes[0]}'")

    user_invocable = fm.get("user-invocable", "false").lower() == "true"
    if user_invocable and name.startswith(("ref-", "assign-")):
        errs.append("第4条違反: ref-* / assign-* must not be user-invocable")
    if (not user_invocable) and name.startswith(("run-", "wrap-", "delegate-")):
        errs.append("第4条違反: run-* / wrap-* / delegate-* must be user-invocable")

    # 第4条 動詞/名詞（heuristic、強制しない）
    # skip

    # 第5条 長さ
    if len(name) > 60:
        errs.append(f"第5条違反: len(name)={len(name)} > 60")

    # 予約語（第6条 補助）
    parts = name.split("-")[1:]  # drop prefix
    if len(parts) == 1 and parts[0] in RESERVED:
        errs.append(f"第6条違反: '{parts[0]}' は予約語の単独使用")

    # 禁則 prefix（第16条 補助）
    if any(name.startswith(fp) for fp in FORBIDDEN_PREFIX):
        errs.append(f"第16条違反: forbidden prefix in '{name}'")

    # 第7条 ディレクトリ名一致
    if dir_name != name:
        errs.append(f"第7条違反: dir '{dir_name}' != name '{name}'")

    return errs


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: lint-skill-name.py /path/to/SKILL.md | --skills-dir /path/to/skills", file=sys.stderr)
        return 2

    if "--skills-dir" in args:
        idx = args.index("--skills-dir")
        if idx + 1 >= len(args):
            print("usage: lint-skill-name.py --skills-dir /path/to/skills", file=sys.stderr)
            return 2
        skills_dir = Path(args[idx + 1])
        if not skills_dir.is_dir():
            print(f"not a directory: {skills_dir}", file=sys.stderr)
            return 2
        total_errs: list[str] = []
        scanned = 0
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            scanned += 1
            for e in lint_file(skill_md):
                total_errs.append(f"{skill_md.parent.name}: {e}")
        if total_errs:
            for e in total_errs:
                print(e, file=sys.stderr)
            return 1
        print(f"ok: {skills_dir} ({scanned} skills)")
        return 0

    p = Path(args[0])
    errs = lint_file(p)

    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1
    print(f"ok: {parse_frontmatter(p.read_text(encoding='utf-8')).get('name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
