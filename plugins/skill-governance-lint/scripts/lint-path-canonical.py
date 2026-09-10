#!/usr/bin/env python3
# /// script
# name: lint-path-canonical
# purpose: Validate canonical path and hardcoded value rules for skill artifacts.
# inputs:
#   - argv: --skills-dir or --skill-md
# outputs:
#   - stdout: OK status
#   - stderr: path canonicalization findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""パス正本ルール (CONVENTIONS.md §8) の自動検証スクリプト。

検証:
  1. ディレクトリ名 == SKILL.md frontmatter の name
  2. SKILL.md 内の python3 呼び出しパスが想定領域 (plugins/*/scripts/ または
     skill 自身の scripts/) を指している
  3. ref-* スキルの frontmatter に source: フィールドが存在する (doc/21)
  4. 具体プロジェクト名・組織名のハードコード検出 (横展開阻害)
  5. LS-215: governance lint scripts 内の削除済み root 'creator-kit/' への
     残存参照検出 (fail-closed)。自分自身 (本スクリプト) の検査ルール定義行は除外。

usage:
  python3 lint-path-canonical.py --skills-dir plugins/harness-creator/skills
  python3 lint-path-canonical.py --skill-md /path/to/SKILL.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 検出対象: 具体プロジェクト名 / 組織名 / 固定 owner
HARDCODE_PATTERNS = [
    (
        re.compile(r"\bxl" r"-skills\b"),
        "specific project name 'xl" + "-skills' (use {{PROJECT_ROOT}})",
    ),
    (re.compile(r"^owner:\s*team-skills\s*$", re.MULTILINE), "hardcoded owner 'team-skills' (use {{owner}})"),
    (re.compile(r"^owner:\s*solo_operator\s*$", re.MULTILINE), "hardcoded owner 'solo_operator' (use {{owner}})"),
]

# python3 呼び出し検出
PY3_CALL = re.compile(r"python3\s+([A-Za-z0-9_./\\-]+\.py)")

# LS-215: 削除済み root への参照パターン (パス文字列 'creator-kit/' / quoted path 部品)
STALE_ROOT_RE = re.compile(r"creator-kit/|['\"]creator-kit['\"]")


def parse_name(text: str) -> str | None:
    m = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def parse_kind(text: str) -> str | None:
    m = re.search(r"^kind:\s*(\S+)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def parse_source(text: str) -> str | None:
    m = re.search(r"^source:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip().strip('"').strip("'") if m else None


def check_skill_md(skill_md: Path) -> list[str]:
    errs: list[str] = []
    if not skill_md.exists():
        return [f"not found: {skill_md}"]
    text = skill_md.read_text(encoding="utf-8")

    # 1. ディレクトリ名 == name
    name = parse_name(text)
    dir_name = skill_md.parent.name
    if name and name != dir_name:
        errs.append(f"name '{name}' != directory '{dir_name}' (§8 violation)")

    # 2. python3 呼び出しパス検証
    for m in PY3_CALL.finditer(text):
        script_path = m.group(1)
        if script_path.startswith(("plugins/", "./scripts/", "scripts/")) \
           or "skills/" in script_path:
            continue
        # 許可外パス（.claude/skills/.../scripts/ など）はエラー
        if ".claude/skills/" in script_path:
            errs.append(f"non-canonical python3 path: {script_path} "
                        f"(use plugins/<name>/scripts/... or scripts/... not .claude/skills/...)")

    # 3. ref-* は source 必須
    kind = parse_kind(text)
    src = parse_source(text)
    if kind == "ref" and not src:
        errs.append("ref-* skill missing 'source:' field (doc/21)")

    # 4. ハードコード検出
    for pat, msg in HARDCODE_PATTERNS:
        if pat.search(text):
            errs.append(f"hardcoded value detected: {msg}")

    return errs


def check_stale_root_refs(scripts_dir: Path) -> list[tuple[str, list[str]]]:
    """LS-215: scripts_dir/*.py 内の削除済み 'creator-kit/' 参照を検出する (fail-closed)。

    自分自身 (本スクリプト) はこの検査ルール定義行を含むため除外する。
    """
    results: list[tuple[str, list[str]]] = []
    self_path = Path(__file__).resolve()
    if not scripts_dir.is_dir():
        return results
    for py in sorted(scripts_dir.glob("*.py")):
        if py.resolve() == self_path:
            continue  # 自分自身の検査ルール定義行は除外
        errs: list[str] = []
        try:
            lines = py.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if STALE_ROOT_RE.search(line):
                errs.append(
                    f"L{i}: 削除済み root 'creator-kit' への残存参照: {line.strip()[:100]}"
                )
        if errs:
            results.append((str(py), errs))
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir")
    ap.add_argument("--skill-md")
    ap.add_argument(
        "--scripts-dir",
        default=str(Path(__file__).resolve().parent),
        help="LS-215 creator-kit 残存参照検査の対象 scripts dir (既定: 本スクリプトと同階層)",
    )
    args = ap.parse_args()

    targets: list[Path] = []
    if args.skill_md:
        targets.append(Path(args.skill_md))
    if args.skills_dir:
        targets.extend(sorted(Path(args.skills_dir).glob("*/SKILL.md")))

    total_errs: list[tuple[str, list[str]]] = []
    for t in targets:
        errs = check_skill_md(t)
        if errs:
            total_errs.append((str(t), errs))

    # LS-215: governance lint scripts の削除済み root 参照検査 (fail-closed)。
    # skill targets 未指定でも必ず実行する (--scripts-dir 単独呼出を CI で使うため。
    # 旧実装は targets 空で help+return 2 となり本検査に到達しない fail-open だった)。
    total_errs.extend(check_stale_root_refs(Path(args.scripts_dir)))

    if total_errs:
        for path, errs in total_errs:
            print(f"\n[{path}]", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
        return 1

    print(
        f"ok: {len(targets)} skill(s) + stale-root scan ({args.scripts_dir}) pass path-canonical lint"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
