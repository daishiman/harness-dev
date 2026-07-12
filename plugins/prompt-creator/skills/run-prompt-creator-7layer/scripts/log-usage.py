#!/usr/bin/env python3
# /// script
# name: log-usage
# purpose: prompt-creator の利用結果（result/phase/format/error）をプラグインルートの LOGS.md に追記する
# inputs:
#   - argv: --result success|failure [--phase "Phase N"] [--format yaml|markdown|json|xml] [--error "ErrorMessage"]
# outputs:
#   - file: LOGS.md に Markdown テーブル行を追記（無ければヘッダ付きで新規作成）
#   - stdout: Logged サマリ
# contexts: [C]
# network: false
# write-scope: plugins/prompt-creator/LOGS.md
# dependencies: []
# ///
# log-usage.py — prompt-creator usage logger
# Usage: python3 log-usage.py --result success|failure [--phase "Phase N"] [--format yaml|markdown|json|xml] [--error "ErrorMessage"]
"""log_usage.js の python 移植。元の追記ロジックを維持する。"""
import argparse
import os
from datetime import datetime, timezone

# 旧 plugin-level scripts/ から skills/run-prompt-creator-7layer/scripts/ へ移動したため、
# LOGS.md のプラグインルートは 3 階層上。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--result", default="unknown")
    parser.add_argument("--phase", default="unknown")
    parser.add_argument("--format", default="not_specified")
    parser.add_argument("--error", default="")
    # A4-10: parse_known_args の黙殺を廃止 (failfast)。未知引数は argparse が exit 2。
    return parser.parse_args()


def main():
    args = parse_args()
    result = args.result or "unknown"
    phase = args.phase or "unknown"
    fmt = args.format or "not_specified"
    error = args.error or ""

    log_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
    log_file = os.path.join(log_dir, "LOGS.md")

    # JS の new Date().toISOString() と同じ Z 付き UTC ISO8601 (ミリ秒) 形式。
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    entry = f"| {timestamp} | {result} | {phase} | {fmt} | {error} |"

    if not os.path.exists(log_file):
        header = (
            "# Prompt Creator Usage Logs\n\n"
            "| Timestamp | Result | Phase | Format | Error |\n"
            "|-----------|--------|-------|--------|-------|\n"
        )
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(header + entry + "\n")
    else:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

    print(f"[prompt-creator] Logged: {result} at {phase} (format: {fmt})")


if __name__ == "__main__":
    main()
