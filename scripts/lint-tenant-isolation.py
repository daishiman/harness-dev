#!/usr/bin/env python3
"""Reject enterprise-specific values in distributable core files."""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = ("plugins", "scripts", "installers", ".claude-plugin")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".git"}
TEXT_SUFFIXES = {
    ".json", ".jsonc", ".md", ".py", ".sh", ".ps1", ".yaml", ".yml",
    ".toml", ".txt", ".html", ".js", ".ts", ".tsx", ".xml", ".ini", "",
}
PATTERNS = (
    re.compile(r"xlocal", re.IGNORECASE),
    re.compile(r"xl-skills", re.IGNORECASE),
    re.compile(r"\.xl-skills", re.IGNORECASE),
    re.compile(r"\bXL_PARTY_A_JSON_PATH\b"),
    re.compile(r"\bXLSKILLS_SECRET_[A-Z0-9_]+\b"),
    re.compile(r"shonai\.inc", re.IGNORECASE),
    re.compile(r"(?:366|36b|37a|384|38a|38c|389|396)07a0c[-0-9a-f]{20,}", re.IGNORECASE),
)


def load_allowlist() -> list[dict]:
    path = ROOT / "scripts" / "tenant-isolation-allowlist.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    today = dt.date.today()
    entries = data.get("entries", [])
    for item in entries:
        if not item.get("reason"):
            raise ValueError(f"allowlist entry missing reason: {item}")
        if dt.date.fromisoformat(item["expires"]) < today:
            raise ValueError(f"expired tenant isolation allowlist entry: {item['path']}")
    return entries


def allowed(path: str, line: str, entries: list[dict]) -> bool:
    return any(
        item["path"] == path and re.search(item["pattern"], line)
        for item in entries
    )


def main() -> int:
    try:
        entries = load_allowlist()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[lint-tenant-isolation] FAIL: invalid allowlist: {exc}", file=sys.stderr)
        return 2
    violations: list[str] = []
    for root_name in SCAN_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            violations.append(f"missing scan root: {root_name}")
            continue
        for path in root.rglob("*"):
            if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in {
                "scripts/lint-tenant-isolation.py",
                "scripts/tenant-isolation-allowlist.json",
            }:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, 1):
                if any(pattern.search(line) for pattern in PATTERNS) and not allowed(rel, line, entries):
                    violations.append(f"{rel}:{number}: {line.strip()[:180]}")
    if violations:
        print(f"[lint-tenant-isolation] FAIL: {len(violations)} enterprise-specific line(s)", file=sys.stderr)
        for item in violations[:200]:
            print(f"  {item}", file=sys.stderr)
        if len(violations) > 200:
            print(f"  ... {len(violations) - 200} more", file=sys.stderr)
        return 1
    print("[lint-tenant-isolation] OK: distributable core is tenant-neutral")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
