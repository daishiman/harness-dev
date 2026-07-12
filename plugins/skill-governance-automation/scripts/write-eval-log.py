#!/usr/bin/env python3
# /// script
# name: write-eval-log
# purpose: Normalize evaluator JSON and append it to the 27章 score JSONL path.
# inputs:
#   - stdin: evaluator JSON
#   - argv: --input, --log-path, --dry-run
# outputs:
#   - stdout: written path or dry-run record
#   - stderr: validation errors
#   - exit: 0=OK / 1=validation failure
# contexts: [A, B, E]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""Append a single evaluation result to eval-log/<plugin>/<date>-score.jsonl.

self-progression loop (23章) の記録責務を担う唯一の書き込み経路。
assign-skill-design-evaluator が評価完了時にSTDOUTへ出すJSONを、本スクリプト経由で
27章の score JSONL schema に正規化して1行=1評価としてappendする。

Sink Contract v1.0 準拠:
  exit 0 success / 1 validation / 2 secret / 3 API / 4 fallback
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

REQUIRED_KEYS = ("rubric_id", "rubric_version", "rubric_hash", "target", "score", "passed")
SCHEMA_VERSION = "1.0"


def resolve_log_path(record: dict) -> Path:
    base = os.environ.get("EVAL_LOG_DIR")
    plugin = str(record.get("plugin") or "core")
    date = time.strftime("%Y-%m-%d")
    if base:
        return Path(base) / plugin / f"{date}-score.jsonl"
    project_root = os.environ.get("PROJECT_ROOT")
    if project_root:
        return Path(project_root) / "eval-log" / plugin / f"{date}-score.jsonl"
    return Path("eval-log") / plugin / f"{date}-score.jsonl"


def validate(record: dict) -> list[str]:
    errors = []
    for k in REQUIRED_KEYS:
        if k not in record:
            errors.append(f"missing key: {k}")
    if "score" in record and not isinstance(record["score"], (int, float)):
        errors.append("score must be numeric")
    if "passed" in record and not isinstance(record["passed"], bool):
        errors.append("passed must be bool")
    findings = record.get("findings", [])
    if not isinstance(findings, list):
        errors.append("findings must be list when present")
    else:
        for idx, finding in enumerate(findings):
            if not isinstance(finding, dict):
                errors.append(f"findings[{idx}] must be object")
                continue
            if not (finding.get("rubric_item_id") or finding.get("id")):
                errors.append(f"findings[{idx}].id or rubric_item_id is required")
    return errors


def normalize(record: dict) -> dict:
    target = record.get("target")
    if isinstance(target, dict):
        skill_name = target.get("skill_name") or target.get("name") or target.get("path") or "unknown"
    else:
        skill_name = str(target or "unknown")
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    record.setdefault("release", os.environ.get("RELEASE_VERSION", "local"))
    record.setdefault("plugin", os.environ.get("PLUGIN_NAME", "core"))
    record.setdefault("skill_name", skill_name)
    record.setdefault("threshold", 80)
    record.setdefault("schema_version", SCHEMA_VERSION)
    for finding in record.get("findings", []):
        if isinstance(finding, dict) and "rubric_item_id" not in finding and finding.get("id"):
            finding["rubric_item_id"] = finding["id"]
    record["rubric"] = {
        "rubric_id": record.pop("rubric_id"),
        "rubric_version": record.pop("rubric_version"),
        "rubric_hash": record.pop("rubric_hash"),
    }
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="path to JSON file (default: STDIN)")
    parser.add_argument("--log-path", help="override eval-log path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw = Path(args.input).read_text() if args.input else sys.stdin.read()
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[write-eval-log] invalid JSON: {e}", file=sys.stderr)
        return 1

    errors = validate(record)
    if errors:
        for e in errors:
            print(f"[write-eval-log] {e}", file=sys.stderr)
        return 1

    record = normalize(record)

    log_path = Path(args.log_path) if args.log_path else resolve_log_path(record)
    if args.dry_run:
        print(f"[write-eval-log] (dry-run) would append to {log_path}")
        print(json.dumps(record, ensure_ascii=False))
        return 0

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[write-eval-log] appended to {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
