#!/usr/bin/env python3
# /// script
# name: build-usable-draft-proof
# purpose: kind別生成/lint receiptとdraft verification planから共通usable-draft proofを生成する。
# inputs:
#   - argv: --verification-plan <json> --capability-kind <kind>
#           --capability-artifact <repo-relative path>
#           --upstream-receipt <json> [--upstream-receipt <json>]
#           --repo-root <dir> --out <json>
# outputs:
#   - stdout / --out: usable-draft-proof.schema.json 準拠JSON
# contexts: [C, E]
# network: false
# write-scope: --out のみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Produce a fail-closed usable-draft proof for every Capability kind."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CAPABILITY_KINDS = {
    "skill", "agent", "hook", "command", "plugin-composition", "prompt", "workflow"
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_KEYS = {
    "schema_version", "capability_kind", "producer_phase", "receipt_type",
    "status", "verification_plan_sha256", "evidence_refs",
}
EVIDENCE_KEYS = {"path", "sha256"}
VALIDATOR_ID = "validate-build-trace"
VALIDATOR_REF = "scripts/validate-build-trace.py"
VALIDATOR_PATH = Path(__file__).resolve().with_name("validate-build-trace.py")
VALIDATOR_TIMEOUT_SECONDS = 30
VALIDATOR_RESULT_KEYS = {"valid", "kind", "findings"}


class ProofError(ValueError):
    """The declared draft is not safely usable."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProofError(f"{label} must be a JSON object")
    return value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ProofError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _inside(path: Path, root: Path, *, must_exist: bool = True) -> tuple[Path, str]:
    candidate = path if path.is_absolute() else root / path
    try:
        resolved = candidate.resolve(strict=must_exist)
        relative = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise ProofError(f"path must remain inside repo root: {path}") from exc
    return resolved, relative


def _validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_version") != 1 or plan.get("stage") != "draft":
        raise ProofError("verification plan must be schema_version=1 and stage=draft")
    if not isinstance(plan.get("run_id"), str) or not plan["run_id"].strip():
        raise ProofError("verification plan run_id is required")
    if not isinstance(plan.get("subject"), str) or not plan["subject"].strip():
        raise ProofError("verification plan subject is required")
    if not isinstance(plan.get("obligations"), list) or not plan["obligations"]:
        raise ProofError("verification plan obligations must be non-empty")
    gate = plan.get("stage_gate")
    if not isinstance(gate, dict) or gate.get("status") != "usable-draft":
        raise ProofError("verification plan must have stage_gate.status=usable-draft")
    if gate.get("handoff_ready") is not True or gate.get("auto_promote") is not False:
        raise ProofError("usable-draft requires handoff_ready=true and auto_promote=false")


def _validate_receipt(
    receipt: dict[str, Any],
    *,
    receipt_path: Path,
    root: Path,
    capability_kind: str,
    upstream_phase: str,
    plan_sha: str,
) -> str:
    if set(receipt) != RECEIPT_KEYS:
        raise ProofError(f"upstream receipt has invalid keys: {receipt_path}")
    if receipt.get("schema_version") != 1 or receipt.get("status") != "PASS":
        raise ProofError(f"upstream receipt must be schema_version=1 and status=PASS: {receipt_path}")
    if receipt.get("capability_kind") != capability_kind:
        raise ProofError(f"upstream receipt capability_kind mismatch: {receipt_path}")
    if receipt.get("producer_phase") != upstream_phase:
        raise ProofError(f"upstream receipt producer_phase mismatch: {receipt_path}")
    if receipt.get("verification_plan_sha256") != plan_sha:
        raise ProofError(f"upstream receipt verification plan sha256 mismatch: {receipt_path}")
    receipt_type = receipt.get("receipt_type")
    if receipt_type not in {"content-review", "generation", "kind-lint"}:
        raise ProofError(f"upstream receipt_type is invalid: {receipt_path}")
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        raise ProofError(f"upstream receipt evidence_refs must be non-empty: {receipt_path}")
    for evidence in evidence_refs:
        if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_KEYS:
            raise ProofError(f"upstream receipt evidence_ref has invalid keys: {receipt_path}")
        relative = evidence.get("path")
        expected_sha = evidence.get("sha256")
        if not isinstance(relative, str) or not relative or not SHA256_RE.fullmatch(str(expected_sha)):
            raise ProofError(f"upstream receipt evidence_ref is invalid: {receipt_path}")
        evidence_path, _ = _inside(root / relative, root)
        if _sha(evidence_path) != expected_sha:
            raise ProofError(f"evidence sha256 mismatch: {relative}")
    return receipt_type


def _resolve_capability_artifact(path: Path, root: Path) -> tuple[Path, str]:
    text = path.as_posix()
    if (
        path.is_absolute()
        or not text
        or text in {".", ".."}
        or "\\" in text
        or ".." in path.parts
        or Path(text).as_posix() != text
    ):
        raise ProofError("capability artifact must be a normalized repo-relative path")
    resolved, relative = _inside(path, root)
    if relative != text or not resolved.is_file():
        raise ProofError("capability artifact must be an actual repo-relative regular file")
    return resolved, relative


def _run_capability_validator(
    *, artifact_path: Path, capability_kind: str, repo_root: Path
) -> dict[str, Any]:
    validator_path = VALIDATOR_PATH
    if validator_path.is_symlink() or not validator_path.is_file():
        raise ProofError("canonical capability artifact validator is unavailable")
    mode = "bundle" if capability_kind == "plugin-composition" else "manifest"
    flag = "--bundle" if mode == "bundle" else "--manifest"
    try:
        completed = subprocess.run(
            [sys.executable, str(validator_path), flag, str(artifact_path)],
            cwd=repo_root,
            capture_output=True,
            timeout=VALIDATOR_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProofError(f"capability artifact validator execution failed: {exc}") from exc
    stdout = completed.stdout
    try:
        report = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProofError("capability artifact validator did not emit valid JSON") from exc
    if not isinstance(report, dict) or set(report) != VALIDATOR_RESULT_KEYS:
        raise ProofError("capability artifact validator emitted an invalid JSON contract")
    if completed.returncode != 0 or report.get("valid") is not True:
        raise ProofError("capability artifact validator did not report valid=true with exit 0")
    if report.get("kind") != capability_kind:
        raise ProofError(
            "capability artifact validator reported kind mismatch: "
            f"expected={capability_kind}, actual={report.get('kind')}"
        )
    if report.get("findings") != []:
        raise ProofError("capability artifact validator valid result must have no findings")
    return {
        "validator_id": VALIDATOR_ID,
        "validator_path": VALIDATOR_REF,
        "validator_sha256": _sha(validator_path),
        "mode": mode,
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "reported_kind": report["kind"],
        "valid": True,
    }


def produce(
    *,
    verification_plan: Path,
    capability_kind: str,
    capability_artifact: Path,
    upstream_receipts: list[Path],
    repo_root: Path,
) -> dict[str, Any]:
    try:
        root = repo_root.resolve(strict=True)
    except OSError as exc:
        raise ProofError(f"cannot resolve repo root: {exc}") from exc
    if not root.is_dir():
        raise ProofError("repo root must be a directory")
    if capability_kind not in CAPABILITY_KINDS:
        raise ProofError(f"unsupported capability kind: {capability_kind}")
    artifact_path, artifact_ref = _resolve_capability_artifact(capability_artifact, root)
    plan_path, plan_ref = _inside(verification_plan, root)
    plan = _load_json(plan_path, "verification plan")
    _validate_plan(plan)
    plan_sha = _sha(plan_path)
    upstream_phase = "content-review" if capability_kind == "skill" else "non-skill-build-lint"
    summaries: list[dict[str, str]] = []
    receipt_types: list[str] = []
    for raw_receipt in upstream_receipts:
        receipt_path, receipt_ref = _inside(raw_receipt, root)
        receipt = _load_json(receipt_path, "upstream receipt")
        receipt_type = _validate_receipt(
            receipt,
            receipt_path=receipt_path,
            root=root,
            capability_kind=capability_kind,
            upstream_phase=upstream_phase,
            plan_sha=plan_sha,
        )
        receipt_types.append(receipt_type)
        summaries.append({
            "receipt_type": receipt_type,
            "path": receipt_ref,
            "sha256": _sha(receipt_path),
        })
    required_types = {"content-review"} if capability_kind == "skill" else {"generation", "kind-lint"}
    if len(receipt_types) != len(required_types) or set(receipt_types) != required_types:
        requirement = "one content-review receipt" if capability_kind == "skill" else "generation and kind-lint receipts"
        raise ProofError(f"{capability_kind} requires exactly {requirement}")
    summaries.sort(key=lambda item: item["receipt_type"])
    artifact_validation = _run_capability_validator(
        artifact_path=artifact_path,
        capability_kind=capability_kind,
        repo_root=root,
    )
    return {
        "schema_version": 2,
        "status": "PASS",
        "capability_kind": capability_kind,
        "upstream_phase": upstream_phase,
        "run_id": plan["run_id"],
        "subject": plan["subject"],
        "verification_plan_ref": plan_ref,
        "verification_plan_sha256": plan_sha,
        "capability_artifact": {
            "path": artifact_ref,
            "sha256": _sha(artifact_path),
        },
        "artifact_validation": artifact_validation,
        "stage_gate": {
            "status": "usable-draft",
            "handoff_ready": True,
            "auto_promote": False,
        },
        "upstream_receipts": summaries,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _write_atomic(path: Path, value: dict[str, Any], root: Path) -> None:
    resolved, _ = _inside(path, root, must_exist=False)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{resolved.name}.", dir=resolved.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, resolved)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification-plan", required=True, type=Path)
    parser.add_argument("--capability-kind", required=True, choices=sorted(CAPABILITY_KINDS))
    parser.add_argument("--capability-artifact", required=True, type=Path)
    parser.add_argument("--upstream-receipt", required=True, action="append", type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        proof = produce(
            verification_plan=args.verification_plan,
            capability_kind=args.capability_kind,
            capability_artifact=args.capability_artifact,
            upstream_receipts=args.upstream_receipt,
            repo_root=args.repo_root,
        )
        root = args.repo_root.resolve(strict=True)
        _write_atomic(args.out, proof, root)
    except (ProofError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
