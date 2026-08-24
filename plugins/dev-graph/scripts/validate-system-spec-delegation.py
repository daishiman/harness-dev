#!/usr/bin/env python3
# /// script
# name: validate-system-spec-delegation
# purpose: Verify that the four canonical system-spec-harness entry points actually returned evidence before progress claims delegation complete.
# inputs: ["argv: --repo-root DIR --receipt FILE --progress FILE"]
# outputs: ["stdout: JSON PASS receipt"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [C, E]
# network: false
# write-scope: none
# ///
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, dump, load_json


REQUIRED_ENTRYPOINTS = (
    "system-spec-harness:run-system-spec-elicit",
    "system-spec-harness:run-system-spec-doc-fetch",
    "system-spec-harness:run-system-spec-compile",
    "system-spec-harness:assign-system-spec-completeness-evaluator",
)
COMPLETED_CALL_STATUSES = {"completed", "no-op"}
RESULT_STATUSES = {"PASS", "FAIL", "INDETERMINATE"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained_file(repo_root: Path, ref: object, *, field: str) -> Path:
    if not isinstance(ref, str) or not ref.strip():
        raise ContractError(f"{field} must be a non-empty repo-relative path")
    relative = Path(ref)
    if relative.is_absolute():
        raise ContractError(f"{field} must be repo-relative")
    resolved = (repo_root / relative).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ContractError(f"{field} escapes repo root") from exc
    if not resolved.is_file():
        raise ContractError(f"{field} is not a file: {ref}")
    return resolved


def contained_argument_file(repo_root: Path, path: Path, *, field: str) -> Path:
    """Resolve a CLI file argument without allowing a second authority root."""

    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ContractError(f"{field} escapes repo root") from exc
    if not resolved.is_file():
        raise ContractError(f"{field} is not a file: {path}")
    return resolved


def validate(repo_root: Path, receipt_path: Path, progress_path: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    if not root.is_dir():
        raise ContractError(f"repo root is not a directory: {root}")
    receipt_file = contained_argument_file(root, receipt_path, field="--receipt")
    progress_file = contained_argument_file(root, progress_path, field="--progress")
    receipt = load_json(receipt_file)
    progress = load_json(progress_file)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "1.0.0":
        raise ContractError("delegation receipt schema_version must be 1.0.0")
    invocations = receipt.get("invocations")
    if not isinstance(invocations, list):
        raise ContractError("delegation receipt invocations must be an array")
    if len(invocations) != len(REQUIRED_ENTRYPOINTS):
        raise ContractError(
            f"delegation receipt must contain exactly 4 invocations; got {len(invocations)}"
        )

    completed: list[str] = []
    evidence: list[dict[str, str]] = []
    for index, (row, expected) in enumerate(zip(invocations, REQUIRED_ENTRYPOINTS), 1):
        if not isinstance(row, dict):
            raise ContractError(f"invocations[{index - 1}] must be an object")
        if row.get("sequence") != index:
            raise ContractError(f"invocations[{index - 1}].sequence must be {index}")
        actual = row.get("qualified_entrypoint")
        if actual != expected:
            raise ContractError(
                f"invocations[{index - 1}] expected {expected}, got {actual!r}"
            )
        if row.get("call_status") not in COMPLETED_CALL_STATUSES:
            raise ContractError(
                f"invocations[{index - 1}].call_status must be completed or no-op"
            )
        if row.get("result_status") not in RESULT_STATUSES:
            raise ContractError(
                f"invocations[{index - 1}].result_status must be PASS, FAIL, or INDETERMINATE"
            )
        if row.get("result_status") != "PASS":
            raise ContractError(
                f"invocations[{index - 1}].result_status must be PASS before delegation progress can PASS"
            )
        evidence_file = contained_file(
            root, row.get("evidence_ref"), field=f"invocations[{index - 1}].evidence_ref"
        )
        expected_digest = row.get("evidence_sha256")
        if not isinstance(expected_digest, str) or len(expected_digest) != 64:
            raise ContractError(f"invocations[{index - 1}].evidence_sha256 must be 64 hex chars")
        try:
            int(expected_digest, 16)
        except ValueError as exc:
            raise ContractError(
                f"invocations[{index - 1}].evidence_sha256 must be lowercase hex"
            ) from exc
        if expected_digest != expected_digest.lower() or sha256(evidence_file) != expected_digest:
            raise ContractError(f"invocations[{index - 1}] evidence digest mismatch")
        completed.append(expected)
        evidence.append({"entrypoint": expected, "sha256": expected_digest})

    delegation = progress.get("delegation") if isinstance(progress, dict) else None
    if not isinstance(delegation, dict):
        raise ContractError("progress.delegation must be an object")
    if delegation.get("required_entrypoints") != list(REQUIRED_ENTRYPOINTS):
        raise ContractError("progress.delegation.required_entrypoints mismatch")
    if delegation.get("completed_entrypoints") != completed:
        raise ContractError("progress.delegation.completed_entrypoints mismatch")
    if delegation.get("completed_count") != len(completed):
        raise ContractError("progress.delegation.completed_count mismatch")
    if delegation.get("status") != "PASS":
        raise ContractError("progress.delegation.status must be PASS")

    receipt_ref = contained_file(
        root, delegation.get("receipt_ref"), field="progress.delegation.receipt_ref"
    )
    if receipt_ref != receipt_file:
        raise ContractError("progress.delegation.receipt_ref does not identify --receipt")
    receipt_digest = delegation.get("receipt_sha256")
    if receipt_digest != sha256(receipt_ref):
        raise ContractError("progress.delegation.receipt_sha256 mismatch")

    return {
        "valid": True,
        "required_entrypoints": list(REQUIRED_ENTRYPOINTS),
        "completed_count": len(completed),
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--progress", required=True)
    args = parser.parse_args()
    dump(validate(Path(args.repo_root), Path(args.receipt), Path(args.progress)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
