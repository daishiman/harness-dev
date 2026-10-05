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
# dependencies: [extract-plugin-root.py]
# ///
"""再利用成果物の具体値直書きと未登録 `{{...}}` を検出する。"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
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


def registry_path() -> Path:
    """registry の正本は兄弟 plugin skill-governance-config の config/ (plugin 分割で移動)。

    install 先は <cache>/<marketplace>/<plugin>/<version>/ なので親ディレクトリ経由では
    兄弟に届かない。同梱の scripts/extract-plugin-root.py で root を解決する。
    """
    resolver = KIT_ROOT / "scripts" / "extract-plugin-root.py"
    # spec_from_file_location は実在しない path にも spec を返すので、先に実在を確かめる。
    spec = importlib.util.spec_from_file_location("_extract_plugin_root", resolver) if resolver.is_file() else None
    if spec is None or spec.loader is None:
        raise SystemExit("extract-plugin-root.py is missing from skill-governance-lint/scripts")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    found = module.resolve("skill-governance-config", KIT_ROOT, Path.cwd())
    if found is None:
        raise SystemExit("skill-governance-config plugin not found; it holds template-variable-registry.json")
    return found / "config" / "template-variable-registry.json"


def registered_vars() -> set[str]:
    data = json.loads(registry_path().read_text(encoding="utf-8"))
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
