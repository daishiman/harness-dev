#!/usr/bin/env python3
# /// script
# name: lint-script-frontmatter
# version: 0.1.0
# purpose: 28章§7 規格に従い scripts/*.py の PEP 723 frontmatter 必須キーを検証する meta-lint
# inputs:
#   - argv: 検査対象ディレクトリ（既定 plugins）
# outputs:
#   - stdout: 違反一覧（path: missing_key1, missing_key2 ...）
#   - exit: 0=OK / 1=違反あり / 2=usage error
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: none
# ///
"""scripts/*.py の PEP 723 inline frontmatter を機械検証する。"""
from __future__ import annotations
import sys
from pathlib import Path

REQUIRED_KEYS = ("name", "purpose", "inputs", "outputs", "contexts", "network", "write-scope", "dependencies")
EXEMPT_NAMES = {"__init__.py"}
# PENDING_FRONTMATTER: doc/migration/phase3/pending-frontmatter.md の移行計画に沿って段階補完中。
# このセットに含まれるファイルは frontmatter 不備でも警告にダウングレードする（EXCEPTION 扱い）。
PENDING_FILES = {
    "render-findings-score.py",
    "resolve-brief-to-category.py",
    "diff-rubric-impact.py",
    "lint-rubric-violation.py",
    "pre-commit-secret-scan.py",
    "guard-change-category.py",
}


def extract_frontmatter(text: str) -> dict | None:
    lines = text.splitlines()
    in_block = False
    keys: dict = {}
    last_key = None
    for ln in lines:
        s = ln.strip()
        if s == "# /// script":
            in_block = True
            continue
        if in_block and s == "# ///":
            return keys
        if in_block:
            body = ln[1:].lstrip() if ln.startswith("#") else ""
            if not body:
                continue
            if ":" in body and not body.lstrip().startswith("-"):
                k, _, v = body.partition(":")
                k = k.strip()
                keys[k] = v.strip()
                last_key = k
            elif body.lstrip().startswith("-") and last_key:
                keys[last_key] = keys.get(last_key, "") + " " + body.strip()
    return None


def main() -> int:
    if len(sys.argv) > 1:
        target_dirs = [Path(p) for p in sys.argv[1:]]
    else:
        target_dirs = [Path("plugins")]

    violations = []
    pending = []
    checked = 0
    for d in target_dirs:
        if not d.is_dir():
            print(f"warning: not a directory: {d}", file=sys.stderr)
            continue
        for p in sorted(d.rglob("*.py")):
            if p.name in EXEMPT_NAMES or "__pycache__" in p.parts:
                continue
            checked += 1
            fm = extract_frontmatter(p.read_text(encoding="utf-8"))
            if fm is None:
                msg = f"{p}: missing # /// script ... # /// block"
            else:
                missing = [k for k in REQUIRED_KEYS if k not in fm]
                if not missing:
                    continue
                msg = f"{p}: missing keys: {', '.join(missing)}"
            if p.name in PENDING_FILES:
                pending.append("PENDING " + msg)
            else:
                violations.append(msg)

    for w in pending:
        print(w, file=sys.stderr)
    if violations:
        for v in violations:
            print(v)
        print(f"\nchecked={checked} violations={len(violations)} pending={len(pending)}", file=sys.stderr)
        return 1
    print(f"OK (checked={checked} pending={len(pending)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
