#!/usr/bin/env python3
# /// script
# name: lint-template-variables
# purpose: Detect unregistered template variables and concrete values in reusable creator-kit artifacts.
# inputs:
#   - argv: paths to scan
# outputs:
#   - stdout: PASS summary
#   - stderr: findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""再利用成果物の具体値直書きと未登録 `{{...}}` を検出する。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
# registry の正本は兄弟プラグイン skill-governance-config/config/ (プラグイン分割で移動)。
REGISTRY = KIT_ROOT.parent / "skill-governance-config" / "config" / "template-variable-registry.json"
VAR_RE = re.compile(r"\{\{[A-Z0-9_]+}}")
ABS_PATH_RE = re.compile(r"(?<![`<])/(Users|home|var|tmp)/[A-Za-z0-9._/\-]+")
URL_RE = re.compile(r"https?://(?!\{\{)[^\s\"')]+")
SECRET_SERVICE_RE = re.compile(r"keychain:(?!\{\{SECRET_NAMESPACE}})[A-Za-z0-9_.-]+/")
ALLOWED_URL_PREFIXES = (
    "https://json-schema.org/",
    "http://json-schema.org/",
    "https://docs.claude.com/",
    "https://github.com/openai/codex",
)


def registered_vars() -> set[str]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {item["name"] for item in data.get("variables", [])}


def should_scan(path: Path) -> bool:
    if path.name.startswith("."):
        return False
    if "__pycache__" in path.parts:
        return False
    return path.suffix in {".md", ".json", ".example", ".yaml", ".yml"}


def scan(path: Path, known: set[str]) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    findings: list[str] = []
    for var in sorted(set(VAR_RE.findall(text)) - known):
        findings.append(f"{path}: unregistered template variable {var}")
    for regex, label in (
        (ABS_PATH_RE, "fixed absolute path"),
        (URL_RE, "fixed URL"),
        (SECRET_SERVICE_RE, "fixed keychain service namespace"),
    ):
        for match in regex.finditer(text):
            if label == "fixed URL" and match.group(0).startswith(ALLOWED_URL_PREFIXES):
                continue
            findings.append(f"{path}: {label}: {match.group(0)}")
    return findings


def main() -> int:
    roots = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else [KIT_ROOT / "skills", KIT_ROOT / "agents", KIT_ROOT / "config"]
    known = registered_vars()
    findings: list[str] = []
    for root in roots:
        if root.is_file() and should_scan(root):
            findings.extend(scan(root, known))
        elif root.is_dir():
            for path in root.rglob("*"):
                if path.is_file() and should_scan(path):
                    findings.extend(scan(path, known))
    if findings:
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("PASS: template variables are registered and no concrete value leaks were found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
