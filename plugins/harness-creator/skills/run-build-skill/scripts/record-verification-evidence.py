#!/usr/bin/env python3
# /// script
# name: record-verification-evidence
# purpose: verifier の成果物を、plan の obligation 1件の fingerprint に結び付けた receipt として記録する
# inputs:
#   - argv: --plan <json> --obligation-id <id> --status <PASS|FAIL|INCONCLUSIVE> --verifier-kind <kind> --verifier-id <id> --evidence-dir <dir>（必須） [--evidence-path ...] [--confidence] [--finding-code ...] [usage 系] [--repo-root]
# outputs:
#   - file: <evidence-dir>/<obligation-id>-<fingerprint 先頭12桁>.json
#   - stdout: {"receipt": <path>, "status": <status>}
#   - exit: 0=OK / 2=入力不正 (plan の形・fingerprint・usage の値)・証跡の欠落・receipt を書けない
# requires-python: ">=3.10"
# dependencies: [plan-verification-obligations.py]
# contexts: [A, C]
# network: false
# write-scope: --evidence-dir 配下の receipt 1件
# ///
"""Bind a verifier artifact to one planned obligation fingerprint."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

# receipt のファイル名に使う fingerprint。planner は sha256 の hexdigest を書く。
# 形を確かめずにファイル名へ入れると、'/../..' を含む値で --evidence-dir の外に書けてしまう。
FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")


def _load_planner():
    path = Path(__file__).with_name("plan-verification-obligations.py")
    spec = importlib.util.spec_from_file_location("verification_obligation_planner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load planner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--obligation-id", required=True)
    parser.add_argument("--status", choices=("PASS", "FAIL", "INCONCLUSIVE"), required=True)
    parser.add_argument("--confidence", type=float, default=1.0)
    parser.add_argument("--verifier-kind", choices=("deterministic", "llm", "live", "human"), required=True)
    parser.add_argument("--verifier-id", required=True)
    parser.add_argument("--evidence-path", action="append")
    parser.add_argument("--finding-code", action="append", default=[])
    parser.add_argument("--run-id")
    parser.add_argument("--model-action-id")
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--elapsed-ms", type=int)
    parser.add_argument("--estimated-cost-usd", type=float)
    parser.add_argument("--note", default="")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args(argv)
    if not 0 <= args.confidence <= 1:
        print("[ERROR] confidence must be between 0 and 1", file=sys.stderr)
        return 2
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        if not isinstance(plan, dict):
            raise ValueError(f"plan が object でない: {type(plan).__name__}")
        obligations = plan.get("obligations")
        if not isinstance(obligations, list):
            raise ValueError("plan.obligations が配列でない")
        record = next(
            (item for item in obligations if isinstance(item, dict) and item.get("id") == args.obligation_id),
            None,
        )
        if record is None:
            raise ValueError(f"obligation id が plan に無い: {args.obligation_id}")
        fingerprint = record.get("fingerprint_sha256")
        if not isinstance(fingerprint, str) or not FINGERPRINT_RE.fullmatch(fingerprint):
            raise ValueError(f"fingerprint_sha256 が64桁の小文字16進でない: {str(fingerprint)[:80]!r}")
        subject = plan.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("plan.subject が空、または文字列でない")
        planner = _load_planner()
        repo_root = Path(args.repo_root).resolve()
        evidence = []
        evidence_paths = args.evidence_path or record.get("expected_evidence_paths") or []
        if not evidence_paths:
            raise ValueError("provide --evidence-path or declare expected_evidence_paths")
        for raw in evidence_paths:
            snapshot = planner.snapshot_path(repo_root, raw)
            if snapshot["missing"]:
                raise ValueError(f"evidence path is missing: {raw}")
            evidence.append({"path": snapshot["path"], "sha256": snapshot["sha256"]})
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        # ValueError は JSONDecodeError と UnicodeDecodeError を含む
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    receipt = {
        "schema_version": 1,
        "subject": subject,
        "obligation_id": args.obligation_id,
        "fingerprint_sha256": fingerprint,
        "status": args.status,
        "confidence": args.confidence,
        "verifier": {"kind": args.verifier_kind, "id": args.verifier_id},
        "evidence": evidence,
        "finding_codes": sorted(set(args.finding_code)),
        "note": args.note,
        "produced_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    usage = {
        key: value
        for key, value in {
            "input_tokens": args.input_tokens,
            "output_tokens": args.output_tokens,
            "elapsed_ms": args.elapsed_ms,
            "estimated_cost_usd": args.estimated_cost_usd,
        }.items()
        if value is not None
    }
    if any(not math.isfinite(value) or value < 0 for value in usage.values()):
        # NaN と inf は receipt を strict JSON でなくし、集計も壊す
        print("[ERROR] usage values must be finite and non-negative", file=sys.stderr)
        return 2
    if usage:
        receipt["usage"] = usage
    effective_run_id = args.run_id or plan.get("run_id")
    if effective_run_id:
        receipt["run_id"] = str(effective_run_id)
    if args.model_action_id:
        receipt["model_action_id"] = args.model_action_id
    out_dir = Path(args.evidence_dir)
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", args.obligation_id).strip("-")
    out = out_dir / f"{safe_id}-{fingerprint[:12]}.json"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"[ERROR] receipt を書けない: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"receipt": str(out), "status": args.status}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
