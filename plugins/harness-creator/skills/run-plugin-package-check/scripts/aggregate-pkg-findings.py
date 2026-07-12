#!/usr/bin/env python3
"""PKG-001〜015 の個別ログを集約し run-report.json を生成。

入力: eval-log/<plugin>/pkg-*/<date>-*.json
出力: eval-log/<plugin>/pkg-summary/<date>-<run>.json
副作用: verdict.fail > 0 のとき .claude/logs/meta-harness.jsonl に
        pkg_check_failed event を 1 行 append（35章 observable）。
"""

from __future__ import annotations
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def aggregate(plugin: str) -> dict:
    eval_root = REPO_ROOT / "eval-log" / plugin
    summary = {
        "plugin": plugin,
        "aggregated_at": now_iso(),
        "pkg_checks": {},
        "verdict": {"pass": 0, "fail": 0, "skip": 0, "not_applicable": 0},
    }
    if not eval_root.exists():
        summary["verdict_note"] = "eval-log 未生成"
        return summary

    for pkg_dir in sorted(eval_root.glob("pkg-*")):
        if pkg_dir.name in {"pkg-summary", "pkg-batch"}:
            continue
        latest = max(pkg_dir.glob("*.json"), default=None, key=lambda p: p.stat().st_mtime)
        if latest is None:
            continue
        try:
            data = json.loads(latest.read_text())
        except json.JSONDecodeError:
            continue
        pkg_id = data.get("pkg_id") or pkg_dir.name.upper().replace("PKG-", "PKG-")
        status = data.get("status", "skip")
        summary["pkg_checks"][pkg_id] = {
            "status": status,
            "source_log": str(latest.relative_to(REPO_ROOT)),
            "findings_count": len(data.get("findings", [])) if isinstance(data.get("findings"), list) else 0,
        }
        summary["verdict"][status] = summary["verdict"].get(status, 0) + 1

    summary["verdict"]["total"] = sum(summary["verdict"][k] for k in ("pass", "fail", "skip", "not_applicable"))
    return summary


def emit_observable(summary: dict) -> None:
    if summary["verdict"].get("fail", 0) == 0:
        return
    log_dir = REPO_ROOT / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "pkg_check_failed",
        "schema_version": "1.0",
        "ts": now_iso(),
        "plugin": summary["plugin"],
        "fail_count": summary["verdict"]["fail"],
        "failed_pkg_ids": [k for k, v in summary["pkg_checks"].items() if v["status"] == "fail"],
    }
    with (log_dir / "meta-harness.jsonl").open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    summary = aggregate(args.plugin)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    emit_observable(summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["verdict"]["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
