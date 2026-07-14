#!/usr/bin/env python3
"""Bind a verifier artifact to one planned obligation fingerprint."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path


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
        record = next(item for item in plan["obligations"] if item["id"] == args.obligation_id)
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
    except (OSError, json.JSONDecodeError, KeyError, StopIteration, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    receipt = {
        "schema_version": 1,
        "subject": plan["subject"],
        "obligation_id": args.obligation_id,
        "fingerprint_sha256": record["fingerprint_sha256"],
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
    if any(value < 0 for value in usage.values()):
        print("[ERROR] usage values must be non-negative", file=sys.stderr)
        return 2
    if usage:
        receipt["usage"] = usage
    effective_run_id = args.run_id or plan.get("run_id")
    if effective_run_id:
        receipt["run_id"] = str(effective_run_id)
    if args.model_action_id:
        receipt["model_action_id"] = args.model_action_id
    out_dir = Path(args.evidence_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", args.obligation_id).strip("-")
    out = out_dir / f"{safe_id}-{record['fingerprint_sha256'][:12]}.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(out), "status": args.status}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
