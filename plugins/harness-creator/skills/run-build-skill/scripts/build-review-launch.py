#!/usr/bin/env python3
# /// script
# name: build-review-launch
# purpose: durable gate planの配送leaseをatomic取得し、stale後は同一idempotency requestを再認可する。
# inputs: --gate-plan <json> --runtime <claude-code|codex>
# outputs: stdout / --out <json>
# contexts: [C]
# network: false
# write-scope: <gate state_ref>.launch.json + --out指定先
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Authorize one active delivery lease; recover stale delivery with one identity."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CLAIM_RE = re.compile(r"^IRC-[0-9a-f]{32}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{2,127}$")
SUPPORTED_RUNTIMES = {"claude-code", "codex"}
PROMPT_REF = "prompts/R5-initial-draft-evaluate.md"
SCHEMA_REF = "schemas/initial-draft-review.schema.json"
EVALUATOR_ID = "elegant-initial-draft-evaluator"
LAUNCH_LEASE_SECONDS = 300
PRE_DIAGNOSTIC_LEVELS = {"light", "standard", "detailed"}
PRESENTATION_RECEIPT_KEYS = {
    "schema_version", "event_id", "event_type", "source", "run_id", "subject",
    "artifact_path", "artifact_sha256", "target_manifest_sha256",
    "contract_binding_sha256", "usable_draft_proof_sha256", "artifact_created_at",
    "smoke", "occurred_at",
}
PRE_DIAGNOSTIC_CHOICE_KEYS = {
    "schema_version", "event_id", "event_type", "source", "run_id", "subject",
    "artifact_path", "artifact_sha256", "target_manifest_sha256",
    "contract_binding_sha256", "presentation_receipt_sha256", "selected_level",
    "occurred_at",
}


class LaunchError(ValueError):
    """The gate plan cannot authorize a safe single evaluator launch."""


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_dict(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise LaunchError(f"{label} must be an object")
    return value


def _require_sha(value: Any, label: str) -> str:
    rendered = str(value)
    if not SHA256_RE.fullmatch(rendered):
        raise LaunchError(f"{label} must be a lowercase SHA-256")
    return rendered


def _parse_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise LaunchError(f"{label} must be a non-empty date-time")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise LaunchError(f"{label} must be an RFC3339 date-time") from exc
    if parsed.tzinfo is None:
        raise LaunchError(f"{label} must include a timezone")
    return parsed


def _validate_binding(value: Any) -> dict:
    binding = _require_dict(value, "contract_binding")
    required = {
        "target_manifest_sha256",
        "method_catalog_sha256",
        "method_catalog_version",
        "prompt_sha256",
        "review_schema_sha256",
        "review_schema_version",
    }
    if set(binding) != required:
        raise LaunchError("contract_binding has an invalid key set")
    for field in (
        "target_manifest_sha256",
        "method_catalog_sha256",
        "prompt_sha256",
        "review_schema_sha256",
    ):
        _require_sha(binding[field], f"contract_binding.{field}")
    if not str(binding["method_catalog_version"]).strip():
        raise LaunchError("method catalog version is required")
    if binding["review_schema_version"] != 1:
        raise LaunchError("review schema version must be 1")
    return binding


def _validate_manifest(value: Any) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise LaunchError("target manifest must be a non-empty array")
    paths: set[str] = set()
    for index, item in enumerate(value):
        item = _require_dict(item, f"target_manifest[{index}]")
        if set(item) != {"path", "sha256", "size"}:
            raise LaunchError(f"target_manifest[{index}] has an invalid key set")
        path = str(item["path"])
        if not path or path.startswith("/") or "\\" in path or ".." in Path(path).parts:
            raise LaunchError(f"target_manifest[{index}].path must be repository-relative")
        if path in paths:
            raise LaunchError(f"duplicate target manifest path: {path}")
        paths.add(path)
        _require_sha(item["sha256"], f"target_manifest[{index}].sha256")
        if type(item["size"]) is not int or item["size"] < 0:
            raise LaunchError(f"target_manifest[{index}].size must be non-negative")
    return value


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LaunchError(f"cannot hash presented artifact: {exc}") from exc
    return digest.hexdigest()


def _validate_pre_diagnostic_authorization(gate: dict, initial: dict) -> dict:
    """Reject any evaluator launch not bound to presentation then user choice."""
    presentation = _require_dict(
        gate.get("artifact_presentation_receipt"), "artifact presentation receipt"
    )
    if set(presentation) != PRESENTATION_RECEIPT_KEYS:
        raise LaunchError("artifact presentation receipt has an invalid key set")
    if (
        presentation.get("schema_version") != 1
        or presentation.get("event_type") != "artifact-presented"
        or presentation.get("source") != "host"
        or not EVENT_ID_RE.fullmatch(str(presentation.get("event_id", "")))
    ):
        raise LaunchError("artifact presentation receipt event identity is invalid")

    choice = _require_dict(
        gate.get("pre_diagnostic_choice_event"), "pre-diagnostic choice event"
    )
    if set(choice) != PRE_DIAGNOSTIC_CHOICE_KEYS:
        raise LaunchError("pre-diagnostic choice event has an invalid key set")
    if (
        choice.get("schema_version") != 1
        or choice.get("event_type") != "pre-diagnostic-choice"
        or choice.get("source") != "user"
        or not EVENT_ID_RE.fullmatch(str(choice.get("event_id", "")))
        or choice.get("selected_level") not in PRE_DIAGNOSTIC_LEVELS
    ):
        raise LaunchError("pre-diagnostic choice does not authorize an evaluator")

    manifest = initial["target_manifest"]
    manifest_by_path = {item["path"]: item for item in manifest}
    artifact_path = presentation.get("artifact_path")
    artifact_sha = _require_sha(presentation.get("artifact_sha256"), "presented artifact sha256")
    manifest_item = manifest_by_path.get(artifact_path)
    if not isinstance(manifest_item, dict) or manifest_item.get("sha256") != artifact_sha:
        raise LaunchError("artifact presentation is not bound to the target manifest")

    binding = initial["contract_binding"]
    expected_common = {
        "run_id": gate["run_id"],
        "subject": gate["subject"],
        "artifact_path": artifact_path,
        "artifact_sha256": artifact_sha,
        "target_manifest_sha256": binding["target_manifest_sha256"],
        "contract_binding_sha256": _canonical_sha(binding),
    }
    for key, expected in expected_common.items():
        if presentation.get(key) != expected or choice.get(key) != expected:
            raise LaunchError(f"presentation/pre-diagnostic choice {key} binding mismatch")
    _require_sha(presentation.get("usable_draft_proof_sha256"), "usable-draft proof sha256")
    if choice.get("presentation_receipt_sha256") != _canonical_sha(presentation):
        raise LaunchError("pre-diagnostic choice presentation receipt digest mismatch")
    if presentation.get("smoke") != {"status": "PASS", "mode": "parse-or-open", "exit_code": 0}:
        raise LaunchError("artifact presentation smoke must PASS parse-or-open")

    created_at = _parse_datetime(presentation.get("artifact_created_at"), "artifact created_at")
    presented_at = _parse_datetime(presentation.get("occurred_at"), "artifact presented_at")
    choice_at = _parse_datetime(choice.get("occurred_at"), "pre-diagnostic choice occurred_at")
    if created_at > presented_at or presented_at >= choice_at:
        raise LaunchError("required event order is artifact_created <= artifact_presented < pre-diagnostic choice")

    raw_root = gate.get("target_root")
    if not isinstance(raw_root, str):
        raise LaunchError("gate plan target_root is required for presented artifact validation")
    try:
        root = Path(raw_root).resolve(strict=True)
        raw_artifact = root / str(artifact_path)
        if raw_artifact.is_symlink():
            raise LaunchError("presented artifact must not be a symlink")
        resolved_artifact = raw_artifact.resolve(strict=True)
        resolved_artifact.relative_to(root)
    except (OSError, ValueError) as exc:
        raise LaunchError("presented artifact is outside the authoritative target root") from exc
    if not resolved_artifact.is_file() or _file_sha(resolved_artifact) != artifact_sha:
        raise LaunchError("presented artifact no longer matches its digest")

    presentation_sha = _canonical_sha(presentation)
    choice_sha = _canonical_sha(choice)
    expected_initial = {
        "artifact_presentation_receipt_sha256": presentation_sha,
        "pre_diagnostic_choice_event_sha256": choice_sha,
        "pre_diagnostic_level": choice["selected_level"],
    }
    if any(initial.get(key) != value for key, value in expected_initial.items()):
        raise LaunchError("initial review is not bound to the presentation/pre-diagnostic choice")
    return {
        "selected_level": choice["selected_level"],
        "presentation_receipt_sha256": presentation_sha,
        "choice_event_sha256": choice_sha,
        "presentation_event_id": presentation["event_id"],
        "choice_event_id": choice["event_id"],
        "choice_occurred_at": choice["occurred_at"],
    }


def _validate_gate_plan(gate_plan: Any) -> tuple[dict, dict]:
    gate = _require_dict(gate_plan, "gate plan")
    if gate.get("schema_version") != 1:
        raise LaunchError("gate plan schema_version must be 1")
    if gate.get("status") != "initial-review-required":
        raise LaunchError("gate plan status must be initial-review-required")
    if not str(gate.get("run_id", "")).strip() or not str(gate.get("subject", "")).strip():
        raise LaunchError("gate plan run_id and subject are required")
    baseline = _require_sha(
        gate.get("baseline_fingerprint_sha256"), "baseline_fingerprint_sha256"
    )
    if gate.get("artifact_fingerprint_sha256") != baseline:
        raise LaunchError("artifact fingerprint must equal the reviewed baseline")
    if not isinstance(gate.get("target_root"), str) or not isinstance(gate.get("target_roots"), list) or not isinstance(gate.get("target_exclusions"), list):
        raise LaunchError("gate plan target scope is required")
    if gate.get("auto_promote_release") is not False or gate.get(
        "auto_promote_exhaustive"
    ) is not False:
        raise LaunchError("gate plan must disable release/exhaustive auto promotion")

    initial = _require_dict(gate.get("initial_review"), "initial_review")
    if initial.get("authorized") is not True or initial.get("action") != "run-once":
        raise LaunchError("initial review is not authorized for a single launch")
    if initial.get("evaluator_id") != EVALUATOR_ID:
        raise LaunchError("initial review evaluator is invalid")
    if initial.get("evaluator_context_limit") != 1:
        raise LaunchError("initial review must authorize exactly one evaluator context")
    if initial.get("review_mode") != "diagnostic-only" or initial.get(
        "target_edits_allowed"
    ) is not False:
        raise LaunchError("initial review must remain read-only diagnostic work")
    if initial.get("thought_reset_required") is not True:
        raise LaunchError("initial review must require a fresh-context thought reset")
    claim_id = str(initial.get("claim_id", ""))
    if not CLAIM_RE.fullmatch(claim_id) or initial.get("claimed_run_id") != gate["run_id"]:
        raise LaunchError("initial review durable claim is invalid")

    methods = initial.get("required_method_ids")
    if (
        initial.get("required_method_count") != 30
        or not isinstance(methods, list)
        or len(methods) != 30
        or len(set(methods)) != 30
        or any(not isinstance(item, str) or not item for item in methods)
    ):
        raise LaunchError("initial review requires 30 unique method IDs")
    if initial.get("prompt_ref") != PROMPT_REF or initial.get("schema_ref") != SCHEMA_REF:
        raise LaunchError("initial review prompt/schema refs are not canonical")
    manifest = _validate_manifest(initial.get("target_manifest"))
    binding = _validate_binding(initial.get("contract_binding"))
    if binding != _validate_binding(gate.get("contract_binding")):
        raise LaunchError("initial review and gate contract bindings differ")
    if _canonical_sha(manifest) != binding["target_manifest_sha256"]:
        raise LaunchError("target manifest digest does not match the contract binding")
    _validate_pre_diagnostic_authorization(gate, initial)
    return gate, initial


def _prepare_launch_request(gate_plan: dict, *, runtime: str) -> tuple[dict, dict, dict]:
    """Validate input and prepare one envelope without consuming its claim."""
    if runtime not in SUPPORTED_RUNTIMES:
        raise LaunchError(f"unsupported runtime: {runtime}")
    gate, initial = _validate_gate_plan(gate_plan)
    pre_diagnostic = _validate_pre_diagnostic_authorization(gate, initial)
    common = {
        "run_id": gate["run_id"],
        "subject": gate["subject"],
        "artifact_fingerprint_sha256": gate["artifact_fingerprint_sha256"],
        "review_claim_id": initial["claim_id"],
        "evaluator_id": EVALUATOR_ID,
        "prompt_ref": PROMPT_REF,
        "output_schema_ref": SCHEMA_REF,
        "contract_binding": initial["contract_binding"],
        "target_manifest": initial["target_manifest"],
        "required_method_ids": initial["required_method_ids"],
        "pre_diagnostic_authorization": pre_diagnostic,
        "context_policy": {
            "context_count": 1,
            "fresh_context": True,
            "parent_history_used": False,
        },
        "tool_policy": {
            "mode": "read-only",
            "allowed_tools": ["Read", "Glob", "Grep"],
            "forbidden_capabilities": ["write", "edit", "shell", "agent-spawn"],
        },
        "thought_reset": {
            "required": True,
            "physical_deletion_allowed": False,
            "fresh_target_read_required": True,
        },
    }
    adapter = (
        {
            "runtime": "claude-code",
            "invocation_kind": "task",
            "entrypoint": EVALUATOR_ID,
        }
        if runtime == "claude-code"
        else {
            "runtime": "codex",
            "invocation_kind": "subagent",
            "entrypoint": PROMPT_REF,
        }
    )
    request_id = "IRL-" + _canonical_sha(common)
    common["launch_request_id"] = request_id
    common["idempotency_key"] = request_id
    return gate, initial, {
        "schema_version": 1,
        "authorized": True,
        "request_id": request_id,
        "idempotency_key": request_id,
        "launch_count": 1,
        "runtime_neutral_request": common,
        "runtime_adapter": adapter,
    }


def launch_state_path(state_path: Path) -> Path:
    """Return the launch-consumption receipt path shared with the gate validator."""
    return Path(f"{state_path}.launch.json")


@contextmanager
def _locked_gate_state(path: Path) -> Iterator[None]:
    """Use the exact lock namespace used by build-improvement-gate.py."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise LaunchError(f"cannot lock durable review state: {exc}") from exc
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _read_durable_state(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise LaunchError("durable review state must be an existing regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LaunchError(f"cannot read durable review state: {exc}") from exc
    return _require_dict(value, "durable review state")


def _validate_durable_state(state: dict, gate: dict, initial: dict) -> None:
    required = {
        "schema_version",
        "artifact_fingerprint_sha256",
        "subject",
        "contract_binding",
        "target_root",
        "target_roots",
        "target_exclusions",
        "target_manifest",
        "status",
        "claim_id",
        "claimed_run_id",
        "created_at",
        "review",
        "review_sha256",
        "review_content_sha256",
        "decisions",
    }
    if set(state) != required or state.get("schema_version") != 2:
        raise LaunchError("durable review state has an invalid key set")
    if state.get("status") != "claimed" or state.get("review") is not None:
        raise LaunchError("durable review state no longer authorizes a launch")
    expected = {
        "artifact_fingerprint_sha256": gate["artifact_fingerprint_sha256"],
        "subject": gate["subject"],
        "contract_binding": gate["contract_binding"],
        "target_root": gate["target_root"],
        "target_roots": gate["target_roots"],
        "target_exclusions": gate["target_exclusions"],
        "target_manifest": initial["target_manifest"],
        "claim_id": initial["claim_id"],
        "claimed_run_id": gate["run_id"],
    }
    if any(state.get(key) != value for key, value in expected.items()):
        raise LaunchError("durable review state does not match the authorized gate plan")
    if state.get("review_sha256") is not None or state.get("review_content_sha256") is not None:
        raise LaunchError("durable review state already contains review evidence")
    if not isinstance(state.get("decisions"), dict):
        raise LaunchError("durable review state decisions must be an object")
    pre_diagnostic = _validate_pre_diagnostic_authorization(gate, initial)
    expected_pre_diagnostic = dict(pre_diagnostic)
    expected_pre_diagnostic.pop("choice_occurred_at")
    if state["decisions"].get("pre_diagnostic") != expected_pre_diagnostic:
        raise LaunchError("durable review state does not match presentation/pre-diagnostic authorization")


def _atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _validate_launch_consumption(value: Any, *, gate: dict, initial: dict, runtime: str, request_id: str) -> dict:
    receipt = _require_dict(value, "launch consumption receipt")
    required = {
        "claim_id", "artifact_fingerprint_sha256", "run_id", "runtime",
        "request_id", "consumed_at", "lease_expires_at", "delivery_attempts",
    }
    if set(receipt) != required:
        raise LaunchError("launch consumption receipt has an invalid key set")
    expected = {
        "claim_id": initial["claim_id"],
        "artifact_fingerprint_sha256": gate["artifact_fingerprint_sha256"],
        "run_id": gate["run_id"],
        "runtime": runtime,
        "request_id": request_id,
    }
    if any(receipt.get(key) != expected_value for key, expected_value in expected.items()):
        raise LaunchError("launch consumption receipt does not match the same idempotency identity")
    _parse_datetime(receipt["consumed_at"], "launch consumed_at")
    _parse_datetime(receipt["lease_expires_at"], "launch lease_expires_at")
    if type(receipt["delivery_attempts"]) is not int or receipt["delivery_attempts"] < 1:
        raise LaunchError("launch delivery_attempts must be a positive integer")
    return receipt


def build_launch_request(gate_plan: dict, *, runtime: str) -> dict:
    """Authorize one active lease, or redeliver its same identity after expiry."""
    gate, initial, request = _prepare_launch_request(gate_plan, runtime=runtime)
    raw_state_ref = gate.get("state_ref")
    if not isinstance(raw_state_ref, str) or not raw_state_ref.strip():
        raise LaunchError("gate plan state_ref is required")
    state_path = Path(raw_state_ref)
    expected_name = f"initial-draft-review-{gate['artifact_fingerprint_sha256']}.json"
    if state_path.name != expected_name:
        raise LaunchError("gate plan state_ref does not match the artifact fingerprint")
    consumed_path = launch_state_path(state_path)
    with _locked_gate_state(state_path):
        _validate_durable_state(_read_durable_state(state_path), gate, initial)
        now = datetime.now(timezone.utc)
        choice_at = _parse_datetime(
            gate["pre_diagnostic_choice_event"]["occurred_at"],
            "pre-diagnostic choice occurred_at",
        )
        if now <= choice_at:
            raise LaunchError("semantic evaluator must start strictly after the pre-diagnostic choice")
        if consumed_path.exists():
            try:
                existing_value = json.loads(consumed_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise LaunchError(f"cannot read launch consumption receipt: {exc}") from exc
            existing = _validate_launch_consumption(
                existing_value,
                gate=gate,
                initial=initial,
                runtime=runtime,
                request_id=request["request_id"],
            )
            if now < _parse_datetime(existing["lease_expires_at"], "launch lease_expires_at"):
                raise LaunchError("initial review launch was already consumed; lease is active")
            consumption = dict(existing)
            consumption["lease_expires_at"] = (now + timedelta(seconds=LAUNCH_LEASE_SECONDS)).isoformat().replace("+00:00", "Z")
            consumption["delivery_attempts"] += 1
        else:
            consumption = {
                "claim_id": initial["claim_id"],
                "artifact_fingerprint_sha256": gate["artifact_fingerprint_sha256"],
                "run_id": gate["run_id"],
                "runtime": runtime,
                "request_id": request["request_id"],
                "consumed_at": now.isoformat().replace("+00:00", "Z"),
                "lease_expires_at": (now + timedelta(seconds=LAUNCH_LEASE_SECONDS)).isoformat().replace("+00:00", "Z"),
                "delivery_attempts": 1,
            }
        try:
            _atomic_write_json(consumed_path, consumption)
        except OSError as exc:
            raise LaunchError(f"cannot persist launch consumption receipt: {exc}") from exc
    return request


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LaunchError(f"cannot read gate plan: {exc}") from exc
    return _require_dict(value, "gate plan")


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gate-plan", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        result = build_launch_request(
            _read_json(Path(args.gate_plan)), runtime=args.runtime
        )
        if args.out:
            _write_json(Path(args.out), result)
    except LaunchError as exc:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "authorized": False,
                    "launch_count": 0,
                    "error": str(exc),
                },
                ensure_ascii=False,
            )
        )
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
