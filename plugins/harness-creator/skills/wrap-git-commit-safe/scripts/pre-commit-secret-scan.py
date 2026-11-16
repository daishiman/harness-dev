#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""wrap-git-commit-safe の決定論的事前スキャン。

doc/22 no-deps 原則 + 設計書04 二段防御の「動的検査」側を担う。
PyYAML / requests 不使用。stdlib のみ。

検査:
  1. ステージング済みファイル名に機密パターン
  2. ファイル内容に API トークン疑似パターン
  3. --no-verify / --no-gpg-sign のコマンドライン混入（呼び出し元から渡される）

exit code:
  0 = pass
  2 = BLOCK (機密検出 / hook bypass)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SECRET_NAME_PATTERNS = [
    r"\.env(\..*)?$",
    r"credentials\.json$",
    r".*\.pem$",
    r".*\.key$",
    r"id_rsa$",
    r".*_secret.*\.(json|yaml|yml|txt)$",
]

# 内容スキャン: github token / aws key / openai key 形式の最小例
SECRET_CONTENT_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]


def staged_files() -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, timeout=10
    )
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def scan_filenames(files: list[str]) -> list[str]:
    hits = []
    for f in files:
        for pat in SECRET_NAME_PATTERNS:
            if re.search(pat, f):
                hits.append(f"filename: {f} (pattern: {pat})")
                break
    return hits


def scan_content(files: list[str], repo_root: Path) -> list[str]:
    hits = []
    for f in files:
        p = repo_root / f
        if not p.exists() or p.is_dir():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_CONTENT_PATTERNS:
            if pat.search(text):
                hits.append(f"content: {f} matches {pat.pattern[:40]}")
                break
    return hits


def check_bypass_flags(argv: list[str]) -> list[str]:
    hits = []
    for a in argv:
        if a in {"--no-verify", "--no-gpg-sign"} or a.startswith("--no-verify=") :
            hits.append(f"forbidden flag: {a}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--commit-args", nargs="*", default=[],
                    help="呼び出し元から渡された git commit の引数列")
    args = ap.parse_args()

    files = staged_files()
    findings = []
    findings += scan_filenames(files)
    findings += scan_content(files, Path(args.repo_root).resolve())
    findings += check_bypass_flags(args.commit_args)

    if findings:
        print(json.dumps({
            "status": "block",
            "reason": "secret or hook-bypass detected",
            "findings": findings,
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    print(json.dumps({"status": "ok", "scanned_files": len(files)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
