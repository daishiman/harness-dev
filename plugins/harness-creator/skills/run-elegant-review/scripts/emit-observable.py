#!/usr/bin/env python3
"""emit-observable: 35 章 meta-harness 連動。

elegant-review v2 の Phase 3 完了後、4 条件のいずれかが FAIL なら
`.claude/logs/meta-harness.jsonl` に `elegant_review_4condition_failed` event を 1 行 append する。

入力 verdict JSON は schemas/verdict.schema.json 準拠。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _git_repo_root() -> Path | None:
    """git rev-parse --show-toplevel で repo ルートを返す。失敗時は None。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return Path(result.stdout.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _default_log_path() -> Path:
    root = _git_repo_root()
    if root is not None:
        return root / ".claude" / "logs" / "meta-harness.jsonl"
    return Path(".claude/logs/meta-harness.jsonl")


EVENT = "elegant_review_4condition_failed"
SCHEMA_VERSION = "1.0"


def load_verdict(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def derive_failed_conditions(verdict: dict) -> list[str]:
    return [k for k, v in verdict.get("verdict", {}).items() if v == "FAIL"]


def build_event(verdict: dict, failed: list[str]) -> dict:
    return {
        "event": EVENT,
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugin": verdict.get("plugin"),
        "skill": verdict.get("skill"),
        "scope_mode": verdict.get("scope_mode"),
        "run_id": verdict.get("run_id"),
        "failed_conditions": failed,
        "fail_counts": {
            k: verdict.get("fail_counts", {}).get(k, 0)
            for k in ("contradiction", "omission", "inconsistency", "dependency_break")
        },
        "iteration_count": verdict.get("iteration_count"),
        "status": verdict.get("status"),
        "safety_valve_fired": verdict.get("safety_valve_fired", False),
    }


def append_jsonl(log_path: Path, event: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verdict", required=True, type=Path)
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="default: <git_repo_root>/.claude/logs/meta-harness.jsonl (cwd フォールバック)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.log is None:
        args.log = _default_log_path()

    verdict = load_verdict(args.verdict)
    failed = derive_failed_conditions(verdict)

    if not failed and not verdict.get("safety_valve_fired"):
        print(json.dumps({"emitted": False, "reason": "all_pass"}))
        return 0

    event = build_event(verdict, failed)
    if args.dry_run:
        print(json.dumps({"emitted": False, "dry_run": True, "event": event}, ensure_ascii=False))
        return 0

    append_jsonl(args.log, event)
    print(json.dumps({"emitted": True, "log": str(args.log), "event": event}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
