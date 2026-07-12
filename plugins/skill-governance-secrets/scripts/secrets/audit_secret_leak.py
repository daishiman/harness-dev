#!/usr/bin/env python3
# /// script
# name: audit-secret-leak
# purpose: Detect plaintext secret patterns in routing, adapter, and skill files.
# inputs:
#   - argv: no required arguments
# outputs:
#   - stdout: OK status
#   - stderr: secret leak findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""output-routing.json / adapter-registry.json / adapter scriptsに平文secretが混入していないか検査。

検出パターン:
- Notion: secret_xxxxx (43+ chars)
- Bearer: 直書きトークン
- AWS: AKIA[0-9A-Z]{16}
- OpenAI: sk-[A-Za-z0-9]{40,}
- Slack webhook: https://hooks.slack.com/services/T.../B.../
- generic: 24+ chars base64-like
"""
from __future__ import annotations
import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent

PATTERNS = {
    "notion_secret": re.compile(r"secret_[A-Za-z0-9]{40,}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{40,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "slack_webhook": re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"),
    "bearer_literal": re.compile(r'Authorization["\s:]+Bearer\s+[A-Za-z0-9_\-]{20,}'),
    "long_token": re.compile(r"[A-Za-z0-9_\-]{40,}"),  # generic, last-resort
}

SCAN_PATHS = [
    REPO / ".claude/config",
    REPO / "scripts/adapters",
    REPO / "scripts/secrets",
    REPO / ".claude/skills",
]

ALLOW_KEYWORDS = ["REPLACE_WITH_", "example", "EXAMPLE", "placeholder", "[REDACTED]", "keychain:"]


def is_allowed(line: str) -> bool:
    return any(k in line for k in ALLOW_KEYWORDS)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    findings = []
    try:
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if is_allowed(line):
                continue
            for name, pat in PATTERNS.items():
                if name == "long_token":
                    # long_token は他パターンに引っかからなかった行のみ
                    if any(p.search(line) for k, p in PATTERNS.items() if k != "long_token"):
                        continue
                    # コメント/識別子/markdown罫線は除外
                    stripped = line.lstrip()
                    if stripped.startswith(("#", "//", "*", "|", "-", "=")):
                        continue
                    # 英字のみ(token候補は数字混在が多い)は除外
                    candidate = re.search(r"[A-Za-z0-9_\-]{40,}", line)
                    if candidate and candidate.group(0).isalpha():
                        continue
                m = pat.search(line)
                if m:
                    findings.append((i, name, line.strip()[:120]))
    except (UnicodeDecodeError, PermissionError):
        pass
    return findings


def main():
    total = 0
    for base in SCAN_PATHS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix in (".pyc",) or "__pycache__" in path.parts:
                continue
            findings = scan_file(path)
            if findings:
                for ln, pat, snippet in findings:
                    print(f"[{pat}] {path}:{ln}: {snippet}")
                    total += 1

    if total > 0:
        print(f"\nFAIL: {total} potential secret(s) detected", file=sys.stderr)
        sys.exit(2)
    print("OK: no plaintext secrets detected")


if __name__ == "__main__":
    main()
