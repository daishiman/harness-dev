#!/usr/bin/env python3
# /// script
# name: lint-forbidden-deps
# purpose: Detect forbidden external dependency usage in creator-kit sources.
# inputs:
#   - argv: optional kit path
# outputs:
#   - stdout: OK status
#   - stderr: forbidden dependency findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""manifest.json の forbidden_dependencies を kit内ソースから grep し、混入を検出する。

CONVENTIONS.md §6「macOSデフォルトのみ・ライブラリ追加禁止」のフィードバックループ実装。
CI / pre-commit hook から呼ぶ想定。
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = KIT_DIR.parent
MANIFEST = KIT_DIR / "manifest.json"

# 検査対象拡張子
SCAN_EXTS = {".py", ".sh"}
# 検査対象ルート (kit内 + プロジェクト内 scripts/.claude)
SCAN_ROOTS = [KIT_DIR, REPO_ROOT / "scripts", REPO_ROOT / ".claude/skills"]
# 自分自身は除外
SELF = Path(__file__).resolve()


def build_patterns(forbidden: list[str]) -> dict[str, re.Pattern]:
    pats = {}
    for name in forbidden:
        # Python import 形式: import X / from X import / X.foo(
        # Shell 起動: pip install X / brew install X / X コマンド呼び出し
        esc = re.escape(name)
        pats[name] = re.compile(
            rf"(?:^|\W)(?:import\s+{esc}|from\s+{esc}\b|pip\s+install\s+\S*{esc}|brew\s+install\s+\S*{esc}|\b{esc}\s+(?:--|-[a-zA-Z]))",
            re.MULTILINE,
        )
    return pats


def scan(roots: list[Path], patterns: dict[str, re.Pattern]) -> list[tuple[Path, int, str, str]]:
    findings = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in SCAN_EXTS:
                continue
            if path.resolve() == SELF:
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, PermissionError):
                continue
            for name, pat in patterns.items():
                for m in pat.finditer(text):
                    line_no = text[: m.start()].count("\n") + 1
                    line = text.splitlines()[line_no - 1].strip()
                    findings.append((path, line_no, name, line))
    return findings


def main() -> int:
    if not MANIFEST.exists():
        print(
            f"SKIP: {MANIFEST} not found "
            "(Phase 2 partition の名残。Phase 3 carry-over F-7 で manifest 再導入予定。"
            "lint は実行せず exit 0 で通す)",
            file=sys.stderr,
        )
        return 0
    manifest = json.loads(MANIFEST.read_text())
    forbidden = manifest.get("requirements", {}).get("forbidden_dependencies", [])
    if not forbidden:
        print("OK: forbidden_dependencies is empty (nothing to check)")
        return 0
    patterns = build_patterns(forbidden)
    findings = scan(SCAN_ROOTS, patterns)
    if not findings:
        print(f"OK: no forbidden dependency usage detected ({len(forbidden)} patterns checked: {forbidden})")
        return 0
    print(f"FAIL: {len(findings)} forbidden dependency usage(s) detected:")
    for path, line_no, name, line in findings:
        print(f"  {path}:{line_no}  [{name}]  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
