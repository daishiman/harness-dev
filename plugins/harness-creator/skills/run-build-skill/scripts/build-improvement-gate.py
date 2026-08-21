#!/usr/bin/env python3
# /// script
# name: build-improvement-gate
# purpose: usable draft の初回30思考法結果をartifact単位でdurable reuseし、
#          所見提示後のユーザー選択だけが改善範囲を認可する。
# inputs:
#   - argv: --verification-plan <json> --usable-draft-proof <json>
#           --target-path <path> --state-dir <dir>
#           [--review <json> --claim-id <id>]
#           [--selected-level <level> --user-choice-event <json>]
# outputs:
#   - stdout / --out: improvement gate plan JSON
#   - --decision-out: user choice receipt JSON
# contexts: [C, E]
# network: false
# write-scope: --state-dir / --out / --decision-out 指定先のみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Durable gate for one initial diagnosis and user-bounded improvement."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METHODS_PATH = SKILL_ROOT.parent / "run-elegant-review" / "references" / "thought-methods.yaml"
DEFAULT_LEVELS_PATH = SKILL_ROOT / "references" / "improvement-levels.json"
DEFAULT_PROMPT_PATH = SKILL_ROOT / "prompts" / "R5-initial-draft-evaluate.md"
DEFAULT_REVIEW_SCHEMA_PATH = SKILL_ROOT / "schemas" / "initial-draft-review.schema.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
METHOD_ID_RE = re.compile(r"^\s+- id:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$")
METHOD_VERSION_RE = re.compile(r'^version:\s*["\']?([^"\'\s]+)')
FINDING_ID_RE = re.compile(r"^IDR-[0-9]{3}$")
EVIDENCE_ID_RE = re.compile(r"^EVD-[0-9]{3}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{2,127}$")
LAUNCH_REQUEST_ID_RE = re.compile(r"^IRL-[0-9a-f]{64}$")
SEVERITIES = {"critical", "high", "medium", "low"}
CONDITION_KEYS = {"C1", "C2", "C3", "C4"}
LEVEL_IDS = {"accept-draft", "light", "standard", "detailed", "release", "exhaustive"}
GLOB_META_RE = re.compile(r"[*?\[\]{}!]")
CAPABILITY_KINDS = {"skill", "agent", "hook", "command", "plugin-composition", "prompt", "workflow"}
USABLE_DRAFT_PROOF_KEYS = {"schema_version", "status", "capability_kind", "upstream_phase", "run_id", "subject", "verification_plan_ref", "verification_plan_sha256", "capability_artifact", "artifact_validation", "stage_gate", "upstream_receipts", "generated_at"}
UPSTREAM_RECEIPT_KEYS = {"schema_version", "capability_kind", "producer_phase", "receipt_type", "status", "verification_plan_sha256", "evidence_refs"}
BUILD_TRACE_VALIDATOR_ID = "validate-build-trace"
BUILD_TRACE_VALIDATOR_REF = "scripts/validate-build-trace.py"
BUILD_TRACE_VALIDATOR_PATH = Path(__file__).resolve().with_name("validate-build-trace.py")
BUILD_TRACE_VALIDATOR_TIMEOUT_SECONDS = 30
BUILD_TRACE_RESULT_KEYS = {"valid", "kind", "findings"}
PRE_DIAGNOSTIC_LEVELS = {"accept-as-is", "light", "standard", "detailed"}
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


class GateError(ValueError):
    """The gate cannot safely authorize the requested action."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise GateError(f"cannot hash file {path}: {exc}") from exc
    return digest.hexdigest()


def _parse_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise GateError(f"{label} must be a non-empty date-time")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise GateError(f"{label} must be RFC3339 date-time") from exc
    if parsed.tzinfo is None:
        raise GateError(f"{label} must include a timezone")
    return parsed


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_exact_keys(value: Any, *, required: set[str], optional: set[str] | None = None, label: str) -> dict:
    if not isinstance(value, dict):
        raise GateError(f"{label} must be an object")
    optional = optional or set()
    missing = required - set(value)
    unknown = set(value) - required - optional
    if missing:
        raise GateError(f"{label} missing required properties: {sorted(missing)}")
    if unknown:
        raise GateError(f"{label} has additional properties: {sorted(unknown)}")
    return value


def load_method_ids(path: Path = DEFAULT_METHODS_PATH) -> list[str]:
    """Load the 30 method IDs from the existing elegant-review SSOT."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GateError(f"cannot read thought-methods SSOT: {exc}") from exc
    ids = [match.group(1) for line in text.splitlines() if (match := METHOD_ID_RE.match(line))]
    if len(ids) != 30 or len(set(ids)) != 30:
        raise GateError(f"thought-methods SSOT must contain 30 unique method ids; got {len(ids)}")
    return ids


def _method_catalog_version(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if match := METHOD_VERSION_RE.match(line.strip()):
                return match.group(1)
    except OSError as exc:
        raise GateError(f"cannot read thought-methods SSOT: {exc}") from exc
    raise GateError("thought-methods SSOT version is required")


def load_levels(path: Path = DEFAULT_LEVELS_PATH) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read improvement level SSOT: {exc}") from exc
    _require_exact_keys(doc, required={"schema_version", "default", "offered_order", "levels"}, label="improvement level SSOT")
    if doc["schema_version"] != 1 or doc["default"] != "ask":
        raise GateError("improvement level SSOT requires schema_version=1 and default=ask")
    levels = doc["levels"]
    offered = doc["offered_order"]
    if not isinstance(levels, dict) or set(levels) != LEVEL_IDS:
        raise GateError("improvement level SSOT has an invalid closed level set")
    if not isinstance(offered, list) or len(offered) != 5 or len(set(offered)) != 5 or set(offered) != LEVEL_IDS - {"exhaustive"}:
        raise GateError("improvement level offered_order must contain five unique default levels")
    required = {"label", "description", "selection", "max_rounds", "next_stage", "next_profile", "offered_by_default"}
    for level, policy in levels.items():
        _require_exact_keys(policy, required=required, label=f"improvement level {level}")
        if not all(isinstance(policy[key], str) and policy[key].strip() for key in ("label", "description")):
            raise GateError(f"improvement level label/description is invalid: {level}")
        if policy["selection"] not in {"none", "high-or-critical", "goal-impact", "all"}:
            raise GateError(f"invalid finding selection policy: {level}")
        if type(policy["max_rounds"]) is not int or not 0 <= policy["max_rounds"] <= 3:
            raise GateError(f"invalid max_rounds: {level}")
        if policy["next_stage"] not in {"draft", "release"}:
            raise GateError(f"invalid next_stage: {level}")
        if policy["next_profile"] not in {"incremental", "exhaustive"}:
            raise GateError(f"invalid next_profile: {level}")
        if not isinstance(policy["offered_by_default"], bool):
            raise GateError(f"offered_by_default must be boolean: {level}")
    if levels["accept-draft"]["selection"] != "none" or levels["accept-draft"]["max_rounds"] != 0:
        raise GateError("accept-draft must remain a zero-edit policy")
    if any(not levels[level]["offered_by_default"] for level in offered):
        raise GateError("all offered levels must be marked offered_by_default")
    if levels["release"]["next_stage"] != "release" or levels["release"]["next_profile"] != "incremental":
        raise GateError("release level must explicitly select release/incremental")
    if levels["exhaustive"]["offered_by_default"] is not False or levels["exhaustive"]["next_stage"] != "release" or levels["exhaustive"]["next_profile"] != "exhaustive":
        raise GateError("exhaustive must remain a separate release/exhaustive opt-in")
    return doc


def _validate_verification_plan(plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise GateError("verification plan requires schema_version=1")
    if plan.get("stage") != "draft":
        raise GateError("initial improvement gate only accepts stage=draft")
    if not str(plan.get("subject", "")).strip():
        raise GateError("verification plan subject is required")
    if not str(plan.get("run_id", "")).strip():
        raise GateError("verification plan run_id is required for provenance")
    if not isinstance(plan.get("stage_gate"), dict):
        raise GateError("verification plan stage_gate is required")
    if plan["stage_gate"].get("auto_promote") is not False:
        raise GateError("verification plan must explicitly disable stage auto promotion")
    if not isinstance(plan.get("obligations"), list) or not plan["obligations"]:
        raise GateError("verification plan obligations must be a non-empty array")


def build_target_manifest(
    paths: list[Path],
    *,
    root: Path,
    exclude_paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Hash a stable, root-relative manifest of every target file."""
    if not paths:
        raise GateError("at least one target path is required")
    try:
        root_resolved = root.resolve(strict=True)
    except OSError as exc:
        raise GateError(f"cannot resolve repo root: {exc}") from exc
    excluded: list[Path] = []
    for raw in exclude_paths or []:
        candidate = raw if raw.is_absolute() else root_resolved / raw
        try:
            excluded.append(candidate.resolve(strict=False))
        except OSError as exc:
            raise GateError(f"cannot resolve excluded runtime path: {raw}") from exc

    def is_excluded(path: Path) -> bool:
        resolved_path = path.resolve(strict=False)
        return any(resolved_path == excluded_path or excluded_path in resolved_path.parents for excluded_path in excluded)

    files: dict[str, Path] = {}
    for raw in paths:
        candidate = raw if raw.is_absolute() else root_resolved / raw
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root_resolved)
        except (OSError, ValueError) as exc:
            raise GateError(f"target path must exist inside repo root: {raw}") from exc
        candidates = (
            []
            if is_excluded(resolved)
            else [resolved]
            if resolved.is_file()
            else sorted(
                (path for path in resolved.rglob("*") if path.is_file() and not is_excluded(path)),
                key=lambda path: path.as_posix(),
            )
        )
        if not candidates:
            raise GateError(f"target path contains no files: {raw}")
        for path in candidates:
            try:
                relative = path.resolve(strict=True).relative_to(root_resolved).as_posix()
            except (OSError, ValueError) as exc:
                raise GateError(f"target file escapes repo root: {path}") from exc
            files[relative] = path
    return [{"path": relative, "sha256": _file_sha(path), "size": path.stat().st_size} for relative, path in sorted(files.items())]


def build_target_scope(
    paths: list[Path],
    *,
    root: Path,
    state_dir: Path,
    runtime_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Build the closed target identity; only the dedicated state lineage is excludable."""
    if not paths:
        raise GateError("at least one target path is required")
    try:
        root_resolved = root.resolve(strict=True)
    except OSError as exc:
        raise GateError(f"cannot resolve repo root: {exc}") from exc
    if not root_resolved.is_dir():
        raise GateError("repo root must be a directory")

    roots: dict[str, dict[str, str]] = {}
    resolved_roots: list[tuple[Path, str]] = []
    for raw in paths:
        candidate = raw if raw.is_absolute() else root_resolved / raw
        try:
            resolved = candidate.resolve(strict=True)
            relative = resolved.relative_to(root_resolved).as_posix() or "."
        except (OSError, ValueError) as exc:
            raise GateError(f"target path must exist inside repo root: {raw}") from exc
        kind = "file" if resolved.is_file() else "directory" if resolved.is_dir() else ""
        if not kind:
            raise GateError(f"target root must be a regular file or directory: {raw}")
        roots[relative] = {"path": relative, "kind": kind}
        resolved_roots.append((resolved, kind))

    raw_state_dir = state_dir if state_dir.is_absolute() else root_resolved / state_dir
    state_resolved = raw_state_dir.resolve(strict=False)
    for target, _ in resolved_roots:
        if state_resolved == target or state_resolved in target.parents:
            raise GateError("state_dir must not be a target root or its parent")

    exclusions: list[str] = []
    try:
        state_relative = state_resolved.relative_to(root_resolved).as_posix()
    except ValueError:
        state_relative = ""
    if state_relative and any(kind == "directory" and (state_resolved == target or target in state_resolved.parents) for target, kind in resolved_roots):
        exclusions.append(state_relative)

    for raw in runtime_paths or []:
        candidate = raw if raw.is_absolute() else root_resolved / raw
        resolved = candidate.resolve(strict=False)
        overlaps_target = any(
            resolved == target if kind == "file" else resolved == target or target in resolved.parents
            for target, kind in resolved_roots
        )
        within_state = resolved == state_resolved or state_resolved in resolved.parents
        if overlaps_target and not within_state:
            raise GateError("runtime artifact path overlaps target content outside the dedicated state_dir")

    target_roots = [roots[key] for key in sorted(roots)]
    target_exclusions = sorted(set(exclusions))
    manifest = build_target_manifest(
        [root_resolved / item["path"] for item in target_roots],
        root=root_resolved,
        exclude_paths=[root_resolved / item for item in target_exclusions],
    )
    return {
        "target_root": str(root_resolved),
        "target_roots": target_roots,
        "target_exclusions": target_exclusions,
        "target_manifest": manifest,
    }


def _is_safe_relative_path(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not value.startswith("/") and "\\" not in value and ".." not in Path(value).parts


def _validate_target_scope(scope: Any, target_manifest: list[dict[str, Any]], *, state_dir: Path) -> dict:
    scope = _require_exact_keys(
        scope,
        required={"target_root", "target_roots", "target_exclusions", "target_manifest"},
        label="target scope",
    )
    try:
        root = Path(scope["target_root"]).resolve(strict=True)
    except (OSError, TypeError) as exc:
        raise GateError("target scope root must be an existing canonical path") from exc
    if str(root) != scope["target_root"] or not root.is_dir():
        raise GateError("target scope root must be a canonical absolute directory")
    roots = scope["target_roots"]
    exclusions = scope["target_exclusions"]
    if not isinstance(roots, list) or not roots or not isinstance(exclusions, list):
        raise GateError("target scope roots/exclusions are invalid")
    normalized_roots: list[dict[str, str]] = []
    for index, item in enumerate(roots):
        _require_exact_keys(item, required={"path", "kind"}, label=f"target_roots[{index}]")
        if item["kind"] not in {"file", "directory"} or not _is_safe_relative_path(item["path"]):
            raise GateError("target scope root entry is invalid")
        try:
            resolved = (root / item["path"]).resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise GateError("target scope root escapes the canonical root") from exc
        actual_kind = "file" if resolved.is_file() else "directory" if resolved.is_dir() else ""
        if actual_kind != item["kind"]:
            raise GateError("target scope root kind does not match the filesystem")
        normalized_roots.append({"path": item["path"], "kind": item["kind"]})
    if normalized_roots != sorted(normalized_roots, key=lambda item: item["path"]) or len({item["path"] for item in normalized_roots}) != len(normalized_roots):
        raise GateError("target scope roots must be sorted and unique")
    if exclusions != sorted(set(exclusions)) or any(not _is_safe_relative_path(item) for item in exclusions):
        raise GateError("target scope exclusions must be sorted unique paths")
    state_resolved = state_dir.resolve(strict=False)
    resolved_roots = [(root / item["path"]).resolve(strict=True) for item in normalized_roots]
    for target in resolved_roots:
        if state_resolved == target or state_resolved in target.parents:
            raise GateError("state_dir must not be a target root or its parent")
    expected_exclusions: list[str] = []
    try:
        state_relative = state_resolved.relative_to(root).as_posix()
    except ValueError:
        state_relative = ""
    if state_relative and any(item["kind"] == "directory" and (target == state_resolved or target in state_resolved.parents) for item, target in zip(normalized_roots, resolved_roots)):
        expected_exclusions.append(state_relative)
    if exclusions != expected_exclusions:
        raise GateError("target scope exclusions must equal the dedicated state_dir lineage")
    rebuilt = build_target_manifest(
        [root / item["path"] for item in normalized_roots],
        root=root,
        exclude_paths=[root / item for item in exclusions],
    )
    if scope["target_manifest"] != target_manifest or rebuilt != target_manifest:
        raise GateError("target manifest is not the complete current target scope closure")
    return scope


def _resolve_proof_path(value: Any, *, root: Path, label: str) -> Path:
    if not _is_safe_relative_path(value):
        raise GateError(f"{label} must be a safe repo-relative path")
    candidate = root / value
    current = root
    for part in Path(value).parts:
        current = current / part
        if current.is_symlink():
            raise GateError(f"{label} must not traverse a symlink")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise GateError(f"{label} must exist inside repo root") from exc
    if not resolved.is_file():
        raise GateError(f"{label} must be a regular file")
    return resolved


def _run_build_trace_validator(
    *, artifact_path: Path, capability_kind: str, root: Path
) -> tuple[subprocess.CompletedProcess[bytes], dict[str, Any]]:
    mode = "bundle" if capability_kind == "plugin-composition" else "manifest"
    flag = "--bundle" if mode == "bundle" else "--manifest"
    try:
        completed = subprocess.run(
            [sys.executable, str(BUILD_TRACE_VALIDATOR_PATH), flag, str(artifact_path)],
            cwd=root,
            capture_output=True,
            timeout=BUILD_TRACE_VALIDATOR_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError(f"usable-draft proof validator execution failed: {exc}") from exc
    try:
        report = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError("usable-draft proof validator did not emit valid JSON") from exc
    if not isinstance(report, dict) or set(report) != BUILD_TRACE_RESULT_KEYS:
        raise GateError("usable-draft proof validator emitted an invalid JSON contract")
    return completed, report


def _validate_usable_draft_proof(proof: Any, *, plan: dict, target_scope: dict) -> dict:
    proof = _require_exact_keys(proof, required=USABLE_DRAFT_PROOF_KEYS, label="usable-draft proof")
    if proof["schema_version"] != 2 or proof["status"] != "PASS":
        raise GateError("usable-draft proof must be schema_version=2 with status=PASS")
    capability_kind = proof["capability_kind"]
    if capability_kind not in CAPABILITY_KINDS:
        raise GateError("usable-draft proof capability_kind is unsupported")
    upstream_phase = "content-review" if capability_kind == "skill" else "non-skill-build-lint"
    required_types = {"content-review"} if capability_kind == "skill" else {"generation", "kind-lint"}
    if proof["upstream_phase"] != upstream_phase:
        raise GateError("usable-draft proof upstream_phase does not match capability_kind")
    if proof["run_id"] != plan["run_id"] or proof["subject"] != plan["subject"]:
        raise GateError("usable-draft proof run_id/subject does not match verification plan")
    gate = _require_exact_keys(proof["stage_gate"], required={"status", "handoff_ready", "auto_promote"}, label="usable-draft proof stage_gate")
    if gate != {"status": "usable-draft", "handoff_ready": True, "auto_promote": False}:
        raise GateError("usable-draft proof stage_gate must be a non-promoting usable draft")
    if any(plan["stage_gate"].get(key) != value for key, value in gate.items()):
        raise GateError("usable-draft proof stage_gate does not match verification plan")
    _parse_datetime(proof["generated_at"], "usable-draft proof generated_at")

    try:
        root = Path(target_scope["target_root"]).resolve(strict=True)
    except (OSError, TypeError) as exc:
        raise GateError("usable-draft proof requires a canonical target root") from exc
    plan_path = _resolve_proof_path(proof["verification_plan_ref"], root=root, label="verification_plan_ref")
    if not SHA256_RE.fullmatch(str(proof["verification_plan_sha256"])) or _file_sha(plan_path) != proof["verification_plan_sha256"]:
        raise GateError("usable-draft proof verification plan sha256 mismatch")
    try:
        persisted_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("usable-draft proof verification plan is unreadable") from exc
    if persisted_plan != plan:
        raise GateError("usable-draft proof verification plan content mismatch")

    artifact = _require_exact_keys(
        proof["capability_artifact"],
        required={"path", "sha256"},
        label="usable-draft proof capability_artifact",
    )
    artifact_path = _resolve_proof_path(
        artifact["path"], root=root, label="capability artifact path"
    )
    if not SHA256_RE.fullmatch(str(artifact["sha256"])) or _file_sha(artifact_path) != artifact["sha256"]:
        raise GateError("usable-draft proof capability artifact sha256 mismatch")
    manifest_by_path = {
        item.get("path"): item
        for item in target_scope.get("target_manifest", [])
        if isinstance(item, dict)
    }
    manifest_artifact = manifest_by_path.get(artifact["path"])
    if not isinstance(manifest_artifact, dict) or manifest_artifact.get("sha256") != artifact["sha256"]:
        raise GateError("capability artifact is not in the authoritative target manifest with the same sha256")

    validation = _require_exact_keys(
        proof["artifact_validation"],
        required={"validator_id", "validator_path", "validator_sha256", "mode", "exit_code", "stdout_sha256", "reported_kind", "valid"},
        label="usable-draft proof artifact_validation",
    )
    expected_mode = "bundle" if capability_kind == "plugin-composition" else "manifest"
    if validation["validator_id"] != BUILD_TRACE_VALIDATOR_ID or validation["validator_path"] != BUILD_TRACE_VALIDATOR_REF:
        raise GateError("usable-draft proof validator identity/path mismatch")
    if BUILD_TRACE_VALIDATOR_PATH.is_symlink() or not BUILD_TRACE_VALIDATOR_PATH.is_file():
        raise GateError("usable-draft proof canonical validator is unavailable")
    if not SHA256_RE.fullmatch(str(validation["validator_sha256"])) or _file_sha(BUILD_TRACE_VALIDATOR_PATH) != validation["validator_sha256"]:
        raise GateError("usable-draft proof validator sha256 mismatch")
    if validation["mode"] != expected_mode or validation["exit_code"] != 0 or validation["valid"] is not True or validation["reported_kind"] != capability_kind:
        raise GateError("usable-draft proof validator receipt does not match capability kind/mode")
    if not SHA256_RE.fullmatch(str(validation["stdout_sha256"])):
        raise GateError("usable-draft proof validator stdout sha256 is invalid")
    completed, report = _run_build_trace_validator(
        artifact_path=artifact_path,
        capability_kind=capability_kind,
        root=root,
    )
    if completed.returncode != 0 or report.get("valid") is not True or report.get("kind") != capability_kind or report.get("findings") != []:
        raise GateError("usable-draft proof public validator revalidation failed")
    if hashlib.sha256(completed.stdout).hexdigest() != validation["stdout_sha256"]:
        raise GateError("usable-draft proof validator stdout digest mismatch")

    summaries = proof["upstream_receipts"]
    if not isinstance(summaries, list) or len(summaries) != len(required_types):
        raise GateError("usable-draft proof has an incomplete upstream receipt set")
    receipt_types: set[str] = set()
    receipt_paths: set[str] = set()
    for index, summary in enumerate(summaries):
        _require_exact_keys(summary, required={"receipt_type", "path", "sha256"}, label=f"usable-draft proof upstream_receipts[{index}]")
        receipt_type = summary["receipt_type"]
        if receipt_type not in required_types or receipt_type in receipt_types or summary["path"] in receipt_paths:
            raise GateError("usable-draft proof upstream receipt types/paths are inconsistent")
        receipt_path = _resolve_proof_path(summary["path"], root=root, label="upstream receipt path")
        if not SHA256_RE.fullmatch(str(summary["sha256"])) or _file_sha(receipt_path) != summary["sha256"]:
            raise GateError("usable-draft proof upstream receipt sha256 mismatch")
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GateError("usable-draft proof upstream receipt is unreadable") from exc
        _require_exact_keys(receipt, required=UPSTREAM_RECEIPT_KEYS, label=f"upstream receipt {receipt_type}")
        if receipt["schema_version"] != 1 or receipt["status"] != "PASS" or receipt["capability_kind"] != capability_kind or receipt["producer_phase"] != upstream_phase or receipt["receipt_type"] != receipt_type or receipt["verification_plan_sha256"] != proof["verification_plan_sha256"]:
            raise GateError("usable-draft proof upstream receipt binding mismatch")
        evidence_refs = receipt["evidence_refs"]
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise GateError("usable-draft proof upstream receipt requires evidence")
        evidence_paths: set[str] = set()
        for evidence_index, evidence in enumerate(evidence_refs):
            _require_exact_keys(evidence, required={"path", "sha256"}, label=f"upstream receipt {receipt_type} evidence[{evidence_index}]")
            if evidence["path"] in evidence_paths:
                raise GateError("usable-draft proof upstream evidence paths must be unique")
            evidence_path = _resolve_proof_path(evidence["path"], root=root, label="upstream evidence path")
            if not SHA256_RE.fullmatch(str(evidence["sha256"])) or _file_sha(evidence_path) != evidence["sha256"]:
                raise GateError("usable-draft proof upstream evidence sha256 mismatch")
            evidence_paths.add(evidence["path"])
        receipt_types.add(receipt_type)
        receipt_paths.add(summary["path"])
    if receipt_types != required_types:
        raise GateError("usable-draft proof upstream receipt set does not match capability_kind")
    return proof


def contract_binding(target_manifest: list[dict[str, Any]], *, methods_path: Path = DEFAULT_METHODS_PATH, prompt_path: Path = DEFAULT_PROMPT_PATH, review_schema_path: Path = DEFAULT_REVIEW_SCHEMA_PATH) -> dict[str, Any]:
    if not target_manifest:
        raise GateError("target manifest must not be empty")
    return {
        "target_manifest_sha256": _canonical_sha(target_manifest),
        "method_catalog_sha256": _file_sha(methods_path),
        "method_catalog_version": _method_catalog_version(methods_path),
        "prompt_sha256": _file_sha(prompt_path),
        "review_schema_sha256": _file_sha(review_schema_path),
        "review_schema_version": 1,
    }


def _validate_artifact_presentation_receipt(
    receipt: Any,
    *,
    plan: dict,
    proof: dict,
    binding: dict,
    target_scope: dict,
) -> datetime:
    """Validate a host presentation receipt against the actual capability artifact."""
    receipt = _require_exact_keys(
        receipt,
        required=PRESENTATION_RECEIPT_KEYS,
        label="artifact presentation receipt",
    )
    if (
        receipt["schema_version"] != 1
        or receipt["event_type"] != "artifact-presented"
        or receipt["source"] != "host"
        or not EVENT_ID_RE.fullmatch(str(receipt["event_id"]))
    ):
        raise GateError("artifact presentation receipt schema/event/source/event_id is invalid")
    if receipt["run_id"] != plan["run_id"] or receipt["subject"] != plan["subject"]:
        raise GateError("artifact presentation receipt run_id/subject does not match current run")

    artifact = proof["capability_artifact"]
    if receipt["artifact_path"] != artifact["path"] or receipt["artifact_sha256"] != artifact["sha256"]:
        raise GateError("artifact presentation receipt is bound to another artifact")
    if receipt["target_manifest_sha256"] != binding["target_manifest_sha256"]:
        raise GateError("artifact presentation receipt target manifest digest mismatch")
    if receipt["contract_binding_sha256"] != _canonical_sha(binding):
        raise GateError("artifact presentation receipt contract binding digest mismatch")
    if receipt["usable_draft_proof_sha256"] != _canonical_sha(proof):
        raise GateError("artifact presentation receipt usable-draft proof digest mismatch")

    try:
        root = Path(target_scope["target_root"]).resolve(strict=True)
    except (OSError, TypeError) as exc:
        raise GateError("artifact presentation receipt requires a canonical target root") from exc
    artifact_path = _resolve_proof_path(
        artifact["path"], root=root, label="artifact presentation receipt path"
    )
    if not artifact_path.is_file() or _file_sha(artifact_path) != artifact["sha256"]:
        raise GateError("artifact presentation receipt does not identify the current regular artifact")

    smoke = _require_exact_keys(
        receipt["smoke"],
        required={"status", "mode", "exit_code"},
        label="artifact presentation smoke",
    )
    if smoke != {"status": "PASS", "mode": "parse-or-open", "exit_code": 0}:
        raise GateError("artifact presentation smoke must be a successful parse-or-open guard")

    created_at = _parse_datetime(receipt["artifact_created_at"], "artifact presentation artifact_created_at")
    proof_at = _parse_datetime(proof["generated_at"], "usable-draft proof generated_at")
    presented_at = _parse_datetime(receipt["occurred_at"], "artifact presentation occurred_at")
    if created_at > proof_at or proof_at > presented_at:
        raise GateError("artifact event order must be artifact_created <= usable proof <= artifact_presented")
    return presented_at


def _validate_pre_diagnostic_choice_event(
    event: Any,
    *,
    plan: dict,
    proof: dict,
    binding: dict,
    presentation_receipt: dict,
    presented_at: datetime,
) -> datetime:
    """Validate the user choice that may authorize a read-only semantic diagnosis."""
    event = _require_exact_keys(
        event,
        required=PRE_DIAGNOSTIC_CHOICE_KEYS,
        label="pre-diagnostic choice event",
    )
    if (
        event["schema_version"] != 1
        or event["event_type"] != "pre-diagnostic-choice"
        or event["source"] != "user"
        or not EVENT_ID_RE.fullmatch(str(event["event_id"]))
    ):
        raise GateError("pre-diagnostic choice event schema/event/source/event_id is invalid")
    if event["run_id"] != plan["run_id"] or event["subject"] != plan["subject"]:
        raise GateError("pre-diagnostic choice event run_id/subject does not match current run")
    artifact = proof["capability_artifact"]
    if event["artifact_path"] != artifact["path"] or event["artifact_sha256"] != artifact["sha256"]:
        raise GateError("pre-diagnostic choice event is bound to another artifact")
    if event["target_manifest_sha256"] != binding["target_manifest_sha256"]:
        raise GateError("pre-diagnostic choice event target manifest digest mismatch")
    if event["contract_binding_sha256"] != _canonical_sha(binding):
        raise GateError("pre-diagnostic choice event contract binding digest mismatch")
    if event["presentation_receipt_sha256"] != _canonical_sha(presentation_receipt):
        raise GateError("pre-diagnostic choice event presentation receipt digest mismatch")
    if event["selected_level"] not in PRE_DIAGNOSTIC_LEVELS:
        raise GateError("pre-diagnostic selected_level must be accept-as-is, light, standard, or detailed")
    choice_at = _parse_datetime(event["occurred_at"], "pre-diagnostic choice occurred_at")
    if choice_at <= presented_at:
        raise GateError("pre-diagnostic choice must occur strictly after artifact presentation")
    return choice_at


def _draft_proofs(plan: dict) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for item in plan["obligations"]:
        if not isinstance(item, dict):
            raise GateError("verification plan obligation must be an object")
        if item.get("stage") != "draft" or item.get("kind") not in {"generative", "deterministic"}:
            continue
        fingerprint = str(item.get("fingerprint_sha256", ""))
        if not SHA256_RE.fullmatch(fingerprint):
            raise GateError(f"invalid draft obligation fingerprint: {item.get('id')}")
        records.append({"id": str(item.get("id", "")), "kind": str(item.get("kind", "")), "fingerprint_sha256": fingerprint})
    if not records:
        raise GateError("verification plan has no draft generative/deterministic proof")
    return sorted(records, key=lambda item: item["id"])


def baseline_fingerprint(plan: dict, target_manifest: list[dict[str, Any]], *, methods_path: Path = DEFAULT_METHODS_PATH, prompt_path: Path = DEFAULT_PROMPT_PATH, review_schema_path: Path = DEFAULT_REVIEW_SCHEMA_PATH) -> str:
    """Bind a review to content and contracts; run_id is provenance, not identity."""
    _validate_verification_plan(plan)
    binding = contract_binding(target_manifest, methods_path=methods_path, prompt_path=prompt_path, review_schema_path=review_schema_path)
    return _canonical_sha({"subject": plan["subject"], "draft_proofs": _draft_proofs(plan), "contract_binding": binding})


def _validate_manifest(manifest: Any, expected: list[dict[str, Any]]) -> None:
    if not isinstance(manifest, list) or manifest != expected:
        raise GateError("review target_manifest is stale or does not match the current target")
    for index, item in enumerate(manifest):
        _require_exact_keys(item, required={"path", "sha256", "size"}, label=f"target_manifest[{index}]")
        if not isinstance(item["path"], str) or not item["path"] or not SHA256_RE.fullmatch(str(item["sha256"])):
            raise GateError("target manifest path/sha256 is invalid")
        if type(item["size"]) is not int or item["size"] < 0:
            raise GateError("target manifest size is invalid")


def _launch_receipt_path(state_path: Path) -> Path:
    return Path(f"{state_path}.launch.json")


def _validate_launch_receipt(value: Any, *, claim_id: str, artifact_fingerprint: str, run_id: str) -> dict:
    launch = _require_exact_keys(
        value,
        required={"claim_id", "artifact_fingerprint_sha256", "run_id", "runtime", "request_id", "consumed_at", "lease_expires_at", "delivery_attempts"},
        label="durable launch receipt",
    )
    if not LAUNCH_REQUEST_ID_RE.fullmatch(str(launch["request_id"])):
        raise GateError("durable launch request_id is invalid")
    if launch["runtime"] not in {"claude-code", "codex"}:
        raise GateError("durable launch runtime is invalid")
    if launch["claim_id"] != claim_id:
        raise GateError("durable launch receipt belongs to another claim")
    if launch["artifact_fingerprint_sha256"] != artifact_fingerprint:
        raise GateError("durable launch receipt belongs to another artifact")
    if launch["run_id"] != run_id:
        raise GateError("durable launch receipt belongs to another run")
    _parse_datetime(launch["consumed_at"], "durable launch consumed_at")
    if _parse_datetime(launch["lease_expires_at"], "durable launch lease_expires_at") <= _parse_datetime(launch["consumed_at"], "durable launch consumed_at"):
        raise GateError("durable launch lease must expire after initial consumption")
    if type(launch["delivery_attempts"]) is not int or launch["delivery_attempts"] < 1:
        raise GateError("durable launch delivery_attempts must be a positive integer")
    return launch


def _read_launch_receipt(path: Path, *, state: dict) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read durable launch receipt: {exc}") from exc
    return _validate_launch_receipt(
        value,
        claim_id=str(state["claim_id"]),
        artifact_fingerprint=str(state["artifact_fingerprint_sha256"]),
        run_id=str(state["claimed_run_id"]),
    )


def _normalize_semantic_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()

    def wordish(char: str) -> bool:
        return bool(char) and unicodedata.category(char)[0] in {"L", "N"}

    def meaningful_identifier_symbol(index: int, char: str) -> bool:
        previous = normalized[index - 1] if index else ""
        following = normalized[index + 1] if index + 1 < len(normalized) else ""
        if char in "._:/\\-" and wordish(previous) and wordish(following):
            return True
        if char == "@" and wordish(following):
            return True
        if char == "#" and wordish(previous):
            return True
        if char == "+" and (wordish(previous) or wordish(following) or previous == "+" or following == "+"):
            return True
        if char == "$" and wordish(following):
            return True
        return False

    characters: list[str] = []
    for index, char in enumerate(normalized):
        category = unicodedata.category(char)
        if category in {"Mn", "Me"} and ("VARIATION SELECTOR" in unicodedata.name(char, "") or ord(char) == 0x20E3):
            continue
        if category[0] in {"P", "S"}:
            characters.append(char if meaningful_identifier_symbol(index, char) else " ")
        elif category[0] == "C":
            characters.append(" ")
        else:
            characters.append(char)
    return " ".join("".join(characters).split())


def _finding_semantic_signature(finding: dict) -> str:
    location = finding["location"]
    return _canonical_sha({
        "title": _normalize_semantic_text(finding["title"]),
        "summary": _normalize_semantic_text(finding["description"]),
        "severity": finding["severity"],
        "affects_goal": finding["affects_goal"],
        "actionable": finding["actionable"],
        "recommendation": _normalize_semantic_text(finding["recommendation"]),
        "location": {
            "path": _normalize_semantic_text(location["path"]),
            "line": location["line"],
            "section": _normalize_semantic_text(location.get("section", "")),
        },
        "conditions": sorted(finding["condition_signals"]),
        "remediation_paths": sorted(_normalize_semantic_text(path) for path in finding["remediation_paths"]),
    })


def _manifest_location_file(manifest_item: dict, *, target_root: Path, location_kind: str, location_id: str) -> tuple[Path, int]:
    try:
        root = target_root.resolve(strict=True)
        candidate = root / manifest_item["path"]
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise GateError(f"{location_kind} path escapes target root or does not exist: {location_id}") from exc
    if not resolved.is_file():
        raise GateError(f"{location_kind} path is not a regular file: {location_id}")
    try:
        payload = resolved.read_bytes()
    except OSError as exc:
        raise GateError(f"cannot read {location_kind} file: {location_id}") from exc
    if len(payload) != manifest_item["size"] or hashlib.sha256(payload).hexdigest() != manifest_item["sha256"]:
        raise GateError(f"{location_kind} file no longer matches target manifest: {location_id}")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateError(f"{location_kind} file must be valid UTF-8: {location_id}") from exc
    return resolved, len(text.splitlines())


def _validate_remediation_paths(finding: dict, *, target_roots: list[dict[str, str]], finding_id: str) -> None:
    paths = finding["remediation_paths"]
    if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
        raise GateError(f"finding remediation_paths must be a non-empty unique array: {finding_id}")
    for path in paths:
        if not _is_safe_relative_path(path) or path == "." or Path(path).as_posix() != path:
            raise GateError(f"finding remediation path is invalid: {finding_id}")
        if GLOB_META_RE.search(path):
            raise GateError(f"finding remediation path must not contain glob syntax: {finding_id}")
    if finding["location"]["path"] not in paths:
        raise GateError(f"finding remediation_paths must include finding location: {finding_id}")

    def within_root(path: str) -> bool:
        for root in target_roots:
            root_path = root["path"]
            if root["kind"] == "file" and path == root_path:
                return True
            if root["kind"] == "directory" and (root_path == "." or path.startswith(root_path + "/")):
                return True
        return False

    if any(not within_root(path) for path in paths):
        raise GateError(f"finding remediation_paths must stay within authoritative target roots: {finding_id}")


def validate_review(review: dict, plan: dict, target_manifest: list[dict[str, Any]], *, claim_id: str, expected_run_id: str, launch_receipt: dict, target_scope: dict, methods_path: Path = DEFAULT_METHODS_PATH, prompt_path: Path = DEFAULT_PROMPT_PATH, review_schema_path: Path = DEFAULT_REVIEW_SCHEMA_PATH) -> None:
    """Strictly validate the diagnostic receipt without making it release proof."""
    required = {"schema_version", "run_id", "subject", "baseline_fingerprint_sha256", "review_claim_id", "launch_request_id", "contract_binding", "target_manifest", "evaluator", "review_mode", "edited_target", "thought_reset", "evidence", "method_observations", "findings", "four_conditions", "recommended_level", "summary", "produced_at"}
    _require_exact_keys(review, required=required, label="review")
    if review["schema_version"] != 1:
        raise GateError("review requires schema_version=1")
    if review["run_id"] != expected_run_id or review["subject"] != plan["subject"]:
        raise GateError("review run_id/subject does not match the review claim")
    if review["review_claim_id"] != claim_id:
        raise GateError("review claim id does not match the durable review claim")
    expected_binding = contract_binding(target_manifest, methods_path=methods_path, prompt_path=prompt_path, review_schema_path=review_schema_path)
    _require_exact_keys(review["contract_binding"], required=set(expected_binding), label="review contract_binding")
    if review["contract_binding"] != expected_binding:
        raise GateError("review contract binding is stale")
    baseline = baseline_fingerprint(plan, target_manifest, methods_path=methods_path, prompt_path=prompt_path, review_schema_path=review_schema_path)
    if review["baseline_fingerprint_sha256"] != baseline:
        raise GateError("review baseline_fingerprint is stale or belongs to another artifact")
    launch = _validate_launch_receipt(
        launch_receipt,
        claim_id=claim_id,
        artifact_fingerprint=baseline,
        run_id=expected_run_id,
    )
    if review["launch_request_id"] != launch["request_id"]:
        raise GateError("review launch_request_id does not match the durable launch")
    _validate_manifest(review["target_manifest"], target_manifest)
    if not isinstance(target_scope, dict) or not isinstance(target_scope.get("target_root"), str) or not isinstance(target_scope.get("target_roots"), list):
        raise GateError("review target scope is invalid")
    target_root = Path(target_scope["target_root"])
    target_roots = target_scope["target_roots"]

    evaluator = _require_exact_keys(review["evaluator"], required={"id", "context_count", "runtime"}, label="review evaluator")
    if evaluator["id"] != "elegant-initial-draft-evaluator" or evaluator["context_count"] != 1 or evaluator["runtime"] not in {"claude-code", "codex"}:
        raise GateError("review evaluator contract is invalid")
    if evaluator["runtime"] != launch["runtime"]:
        raise GateError("review evaluator runtime does not match the durable launch")
    if review["review_mode"] != "diagnostic-only" or review["edited_target"] is not False:
        raise GateError("review must be diagnostic-only with edited_target=false")

    reset = _require_exact_keys(review["thought_reset"], required={"performed", "physical_deletion_performed", "parent_history_used", "fresh_target_read", "attested_at"}, label="thought_reset")
    if reset["performed"] is not True or reset["physical_deletion_performed"] is not False or reset["parent_history_used"] is not False or reset["fresh_target_read"] is not True:
        raise GateError("thought reset must be fresh-context and must not delete artifacts")
    _parse_datetime(reset["attested_at"], "thought_reset.attested_at")

    evidence = review["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise GateError("review evidence must be a non-empty array")
    evidence_ids: set[str] = set()
    manifest_by_path = {item["path"]: item for item in target_manifest}
    target_paths = set(manifest_by_path)
    for index, item in enumerate(evidence):
        _require_exact_keys(item, required={"id", "path", "line"}, optional={"section"}, label=f"evidence[{index}]")
        evidence_id = str(item["id"])
        if not EVIDENCE_ID_RE.fullmatch(evidence_id) or evidence_id in evidence_ids:
            raise GateError(f"invalid or duplicate evidence id: {evidence_id!r}")
        if item["path"] not in target_paths or type(item["line"]) is not int or item["line"] < 1:
            raise GateError(f"evidence location is invalid: {evidence_id}")
        _, line_count = _manifest_location_file(manifest_by_path[item["path"]], target_root=target_root, location_kind="evidence", location_id=evidence_id)
        if item["line"] > line_count:
            raise GateError(f"evidence line exceeds actual line count: {evidence_id}")
        if "section" in item and not isinstance(item["section"], str):
            raise GateError(f"evidence section is invalid: {evidence_id}")
        evidence_ids.add(evidence_id)

    expected_methods = load_method_ids(methods_path)
    observations = review["method_observations"]
    if not isinstance(observations, list) or len(observations) != 30:
        raise GateError("review must contain exactly 30 method observations")
    actual_methods: list[str] = []
    rationales: set[str] = set()
    for index, item in enumerate(observations):
        _require_exact_keys(item, required={"method_id", "rationale", "observation", "evidence_refs", "finding_refs"}, label=f"method_observations[{index}]")
        method_id = str(item["method_id"])
        actual_methods.append(method_id)
        rationale = str(item["rationale"]).strip()
        if not rationale or rationale.casefold() in rationales:
            raise GateError(f"method rationale must be non-empty and method-specific: {method_id}")
        rationales.add(rationale.casefold())
        if not str(item["observation"]).strip():
            raise GateError(f"empty method observation: {method_id}")
        refs = item["evidence_refs"]
        if not isinstance(refs, list) or not refs or len(refs) != len(set(refs)) or set(refs) - evidence_ids:
            raise GateError(f"evidence_refs must be non-empty, unique, and known: {method_id}")
        if not isinstance(item["finding_refs"], list) or len(item["finding_refs"]) != len(set(item["finding_refs"])):
            raise GateError(f"finding_refs must be a unique array: {method_id}")
    if len(set(actual_methods)) != 30 or set(actual_methods) != set(expected_methods):
        raise GateError("review must cover all 30 canonical thought methods exactly once")

    findings = review["findings"]
    if not isinstance(findings, list):
        raise GateError("review findings must be an array")
    finding_ids: set[str] = set()
    finding_by_id: dict[str, dict] = {}
    semantic_findings: dict[str, str] = {}
    for index, finding in enumerate(findings):
        _require_exact_keys(finding, required={"id", "title", "description", "severity", "affects_goal", "actionable", "recommendation", "location", "remediation_paths", "condition_signals"}, label=f"findings[{index}]")
        finding_id = str(finding["id"])
        if not FINDING_ID_RE.fullmatch(finding_id) or finding_id in finding_ids:
            raise GateError(f"invalid or duplicate review finding id: {finding_id!r}")
        if finding["severity"] not in SEVERITIES or not isinstance(finding["affects_goal"], bool) or not isinstance(finding["actionable"], bool):
            raise GateError(f"finding severity/flags are invalid: {finding_id}")
        for field in ("title", "description", "recommendation"):
            if not isinstance(finding[field], str) or not finding[field].strip():
                raise GateError(f"finding {field} is empty: {finding_id}")
        location = _require_exact_keys(finding["location"], required={"path", "line"}, optional={"section"}, label=f"finding {finding_id} location")
        if location["path"] not in target_paths or type(location["line"]) is not int or location["line"] < 1:
            raise GateError(f"finding location is invalid: {finding_id}")
        _, finding_line_count = _manifest_location_file(manifest_by_path[location["path"]], target_root=target_root, location_kind="finding", location_id=finding_id)
        if location["line"] > finding_line_count:
            raise GateError(f"finding line exceeds actual line count: {finding_id}")
        _validate_remediation_paths(finding, target_roots=target_roots, finding_id=finding_id)
        signals = finding["condition_signals"]
        if not isinstance(signals, list) or not signals or len(signals) != len(set(signals)) or not set(signals) <= CONDITION_KEYS:
            raise GateError(f"finding condition_signals are invalid: {finding_id}")
        signature = _finding_semantic_signature(finding)
        if signature in semantic_findings:
            raise GateError(f"semantic duplicate findings are not allowed: {semantic_findings[signature]}, {finding_id}")
        semantic_findings[signature] = finding_id
        finding_ids.add(finding_id)
        finding_by_id[finding_id] = finding

    referenced_findings: set[str] = set()
    for item in observations:
        unknown = set(item["finding_refs"]) - finding_ids
        if unknown:
            raise GateError(f"method observation references unknown findings: {sorted(unknown)}")
        referenced_findings.update(item["finding_refs"])
    if referenced_findings != finding_ids:
        raise GateError(f"every finding must be referenced by a method observation: {sorted(finding_ids - referenced_findings)}")

    conditions = review["four_conditions"]
    if not isinstance(conditions, dict) or set(conditions) != CONDITION_KEYS:
        raise GateError("review four_conditions must contain exactly C1-C4")
    for key, value in conditions.items():
        _require_exact_keys(value, required={"verdict", "summary", "finding_refs"}, label=f"four_conditions.{key}")
        if value["verdict"] not in {"PASS", "FAIL", "PARTIAL"} or not str(value["summary"]).strip():
            raise GateError(f"invalid four_conditions verdict: {key}")
        expected_refs = {fid for fid, finding in finding_by_id.items() if key in finding["condition_signals"]}
        refs = value["finding_refs"]
        if not isinstance(refs, list) or len(refs) != len(set(refs)) or set(refs) != expected_refs:
            raise GateError(f"four_conditions.{key} finding linkage is inconsistent")
        severities = {finding_by_id[fid]["severity"] for fid in expected_refs}
        if "critical" in severities and value["verdict"] != "FAIL":
            raise GateError(f"four_conditions.{key} must FAIL for critical findings")
        if "high" in severities and value["verdict"] == "PASS":
            raise GateError(f"four_conditions.{key} cannot PASS for high findings")

    recommended = review["recommended_level"]
    if recommended not in LEVEL_IDS - {"exhaustive"}:
        raise GateError("review recommended_level cannot be exhaustive or unknown")
    actionable = [finding for finding in findings if finding["actionable"]]
    if any(f["severity"] in {"critical", "high"} for f in actionable) and recommended == "accept-draft":
        raise GateError("accept-draft cannot be recommended with actionable critical/high findings")
    if any(f["severity"] == "medium" and f["affects_goal"] for f in actionable) and recommended in {"accept-draft", "light"}:
        raise GateError("goal-affecting medium findings require at least standard recommendation")
    if not isinstance(review["summary"], str) or not review["summary"].strip():
        raise GateError("review summary is required")
    _parse_datetime(review["produced_at"], "review.produced_at")


def _select_findings(findings: list[dict], selection: str) -> list[str]:
    actionable = [finding for finding in findings if finding.get("actionable") is True]
    if selection == "none":
        return []
    if selection == "high-or-critical":
        return [f["id"] for f in actionable if f["severity"] in {"critical", "high"}]
    if selection == "goal-impact":
        return [f["id"] for f in actionable if f["severity"] in {"critical", "high"} or (f["severity"] == "medium" and f["affects_goal"])]
    if selection == "all":
        return [f["id"] for f in actionable]
    raise GateError(f"unknown finding selection policy: {selection}")


def _validate_user_event(event: Any, *, event_type: str, plan: dict, baseline: str, review_sha256: str, selected_level: str | None = None) -> datetime:
    required = {"schema_version", "event_id", "event_type", "source", "run_id", "subject", "artifact_fingerprint_sha256", "review_sha256", "occurred_at"}
    event = _require_exact_keys(event, required=required, optional={"selected_level"}, label="user event")
    if event["schema_version"] != 1 or event["source"] != "user" or not EVENT_ID_RE.fullmatch(str(event["event_id"])):
        raise GateError("user event schema/source/event_id is invalid")
    if event["event_type"] != event_type:
        raise GateError(f"user event_type must be {event_type}")
    if event["run_id"] != plan["run_id"] or event["subject"] != plan["subject"]:
        raise GateError("user event run_id/subject does not match current run")
    if event["artifact_fingerprint_sha256"] != baseline or event["review_sha256"] != review_sha256:
        raise GateError("user event is bound to another artifact or review")
    if event_type == "improvement-level-selected":
        if event.get("selected_level") != selected_level:
            raise GateError("user choice event selected_level does not match the request")
    elif "selected_level" in event:
        raise GateError(f"{event_type} event must not contain selected_level")
    return _parse_datetime(event["occurred_at"], "user event occurred_at")


def _state_path(state_dir: Path, baseline: str) -> Path:
    return state_dir / f"initial-draft-review-{baseline}.json"


@contextmanager
def _locked_state(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path.with_suffix(path.suffix + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


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


def _read_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read durable review state: {exc}") from exc
    required = {"schema_version", "artifact_fingerprint_sha256", "subject", "contract_binding", "target_root", "target_roots", "target_exclusions", "target_manifest", "status", "claim_id", "claimed_run_id", "created_at", "review", "review_sha256", "review_content_sha256", "decisions"}
    _require_exact_keys(value, required=required, label="durable review state")
    if value["schema_version"] != 2 or value["status"] not in {"claimed", "completed"} or not isinstance(value["decisions"], dict):
        raise GateError("durable review state is invalid")
    return value


def _base_result(plan: dict, baseline: str, binding: dict, state_path: Path, target_scope: dict) -> dict:
    return {"schema_version": 1, "subject": plan["subject"], "run_id": plan["run_id"], "baseline_fingerprint_sha256": baseline, "artifact_fingerprint_sha256": baseline, "contract_binding": binding, "target_root": target_scope["target_root"], "target_roots": target_scope["target_roots"], "target_exclusions": target_scope["target_exclusions"], "state_ref": str(state_path), "launch_receipt_ref": str(_launch_receipt_path(state_path)), "auto_promote_release": False, "auto_promote_exhaustive": False, "initial_review": {"authorized": False}, "improvement": {"authorized": False}}


def build_gate(plan: dict, *, target_manifest: list[dict[str, Any]], target_scope: dict, usable_draft_proof: dict, state_dir: Path, artifact_presentation_receipt: dict | None = None, pre_diagnostic_choice_event: dict | None = None, review: dict | None = None, review_source_sha256: str | None = None, claim_id: str | None = None, selected_level: str | None = None, choice_event: dict | None = None, exhaustive_confirmation_event: dict | None = None, risk_acknowledgement_event: dict | None = None, user_choice_ref: str | None = None, confirm_exhaustive: bool = False, methods_path: Path = DEFAULT_METHODS_PATH, levels_path: Path = DEFAULT_LEVELS_PATH, prompt_path: Path = DEFAULT_PROMPT_PATH, review_schema_path: Path = DEFAULT_REVIEW_SCHEMA_PATH) -> dict:
    """Return and durably record the only currently authorized action."""
    _validate_verification_plan(plan)
    _validate_manifest(target_manifest, target_manifest)
    target_scope = _validate_target_scope(target_scope, target_manifest, state_dir=Path(state_dir))
    _validate_usable_draft_proof(usable_draft_proof, plan=plan, target_scope=target_scope)
    binding = contract_binding(target_manifest, methods_path=methods_path, prompt_path=prompt_path, review_schema_path=review_schema_path)
    baseline = baseline_fingerprint(plan, target_manifest, methods_path=methods_path, prompt_path=prompt_path, review_schema_path=review_schema_path)
    method_ids = load_method_ids(methods_path)
    levels_doc = load_levels(levels_path)
    state_path = _state_path(Path(state_dir), baseline)
    result = _base_result(plan, baseline, binding, state_path, target_scope)
    if plan["stage_gate"].get("status") != "usable-draft" or plan["stage_gate"].get("handoff_ready") is not True:
        result.update(status="draft-not-ready", instruction="usable-draft proof が揃うまで初回診断も改善も開始しない。pending_draft だけを解決する。")
        return result

    if artifact_presentation_receipt is None:
        if pre_diagnostic_choice_event is not None:
            raise GateError("pre-diagnostic choice cannot exist before artifact presentation")
        if any(value is not None for value in (review, selected_level, choice_event)):
            raise GateError("review or improvement selection cannot start before artifact presentation")
        result.update(
            status="awaiting-artifact-presentation",
            instruction="実artifactのpath/digest/smokeをhost receiptへ記録し、利用者へ提示するまでdiagnostic claimを作らない。",
        )
        return result

    presented_at = _validate_artifact_presentation_receipt(
        artifact_presentation_receipt,
        plan=plan,
        proof=usable_draft_proof,
        binding=binding,
        target_scope=target_scope,
    )
    result["artifact_presentation_receipt"] = artifact_presentation_receipt
    if pre_diagnostic_choice_event is None:
        if any(value is not None for value in (review, selected_level, choice_event)):
            raise GateError("review or improvement selection cannot start before pre-diagnostic user choice")
        result.update(
            status="awaiting-pre-diagnostic-choice",
            instruction="提示済みartifactをそのまま受理するか、light/standard/detailed診断を行うか利用者eventを待つ。",
        )
        return result

    _validate_pre_diagnostic_choice_event(
        pre_diagnostic_choice_event,
        plan=plan,
        proof=usable_draft_proof,
        binding=binding,
        presentation_receipt=artifact_presentation_receipt,
        presented_at=presented_at,
    )
    result["pre_diagnostic_choice_event"] = pre_diagnostic_choice_event
    pre_diagnostic = {
        "selected_level": pre_diagnostic_choice_event["selected_level"],
        "presentation_receipt_sha256": _canonical_sha(artifact_presentation_receipt),
        "choice_event_sha256": _canonical_sha(pre_diagnostic_choice_event),
        "presentation_event_id": artifact_presentation_receipt["event_id"],
        "choice_event_id": pre_diagnostic_choice_event["event_id"],
    }

    with _locked_state(state_path):
        state = _read_state(state_path)
        if pre_diagnostic_choice_event["selected_level"] == "accept-as-is":
            if state is not None:
                raise GateError("pre-diagnostic choice is immutable after a diagnostic claim exists")
            if any(value is not None for value in (review, selected_level, choice_event)):
                raise GateError("accept-as-is cannot submit a review or improvement selection")
            result["status"] = "usable-draft"
            result["initial_review"] = {"authorized": False, "evaluator_contexts": 0}
            result["improvement"] = {"authorized": False, "improver_contexts": 0}
            result["handoff"] = {
                "artifact_presented": True,
                "selected_level": "accept-as-is",
                "presentation_receipt_sha256": pre_diagnostic["presentation_receipt_sha256"],
                "choice_event_sha256": pre_diagnostic["choice_event_sha256"],
            }
            result["instruction"] = "提示済みusable draftをそのままhandoffする。evaluator/improver contextは0。"
            return result
        if state is None:
            if review is not None or selected_level is not None:
                raise GateError("initial review must be durably claimed before review or selection")
            durable_claim_id = f"IRC-{uuid.uuid4().hex}"
            state = {"schema_version": 2, "artifact_fingerprint_sha256": baseline, "subject": plan["subject"], "contract_binding": binding, "target_root": target_scope["target_root"], "target_roots": target_scope["target_roots"], "target_exclusions": target_scope["target_exclusions"], "target_manifest": target_manifest, "status": "claimed", "claim_id": durable_claim_id, "claimed_run_id": plan["run_id"], "created_at": _now(), "review": None, "review_sha256": None, "review_content_sha256": None, "decisions": {"pre_diagnostic": pre_diagnostic}}
            _atomic_write_json(state_path, state)
            result["status"] = "initial-review-required"
            result["initial_review"] = {"authorized": True, "action": "run-once", "claim_id": durable_claim_id, "claimed_run_id": plan["run_id"], "evaluator_id": "elegant-initial-draft-evaluator", "evaluator_context_limit": 1, "review_mode": "diagnostic-only", "target_edits_allowed": False, "thought_reset_required": True, "required_method_count": 30, "required_method_ids": method_ids, "target_manifest": target_manifest, "contract_binding": binding, "artifact_presentation_receipt_sha256": pre_diagnostic["presentation_receipt_sha256"], "pre_diagnostic_choice_event_sha256": pre_diagnostic["choice_event_sha256"], "pre_diagnostic_level": pre_diagnostic["selected_level"], "schema_ref": "schemas/initial-draft-review.schema.json", "prompt_ref": "prompts/R5-initial-draft-evaluate.md"}
            result["instruction"] = "fresh contextの単一elegant-initial-draft-evaluatorへ、同一identityの有効配送leaseを1件だけ認可し、claim/target/contractをreceiptへ束縛する。"
            return result

        if state["artifact_fingerprint_sha256"] != baseline or state["contract_binding"] != binding or state["target_root"] != target_scope["target_root"] or state["target_roots"] != target_scope["target_roots"] or state["target_exclusions"] != target_scope["target_exclusions"] or state["target_manifest"] != target_manifest or state["subject"] != plan["subject"]:
            raise GateError("durable review state does not match the current artifact")
        if state["status"] == "claimed" and state["decisions"].get("pre_diagnostic") != pre_diagnostic:
            raise GateError("durable review state does not match the presentation/pre-diagnostic choice")
        launch_receipt = _read_launch_receipt(_launch_receipt_path(state_path), state=state)
        if launch_receipt is not None and state["status"] == "claimed":
            launch_started_at = _parse_datetime(launch_receipt["consumed_at"], "semantic evaluator started_at")
            pre_choice_at = _parse_datetime(pre_diagnostic_choice_event["occurred_at"], "pre-diagnostic choice occurred_at")
            if launch_started_at <= pre_choice_at:
                raise GateError("semantic evaluator must start strictly after the pre-diagnostic choice")
        if state["status"] == "claimed":
            if review is None:
                result["status"] = "initial-review-in-progress"
                result["initial_review"] = {"authorized": False, "status": "claimed", "claim_id": state["claim_id"], "claimed_run_id": state["claimed_run_id"], "launch": launch_receipt}
                result["instruction"] = "初回診断は別contextがclaim済み。追加Agentを起動しない。"
                return result
            if not claim_id or claim_id != state["claim_id"]:
                raise GateError("review submission requires the matching durable claim_id")
            if launch_receipt is None:
                raise GateError("review cannot be accepted before the claim is durably launched")
            validate_review(review, plan, target_manifest, claim_id=state["claim_id"], expected_run_id=state["claimed_run_id"], launch_receipt=launch_receipt, target_scope=target_scope, methods_path=methods_path, prompt_path=prompt_path, review_schema_path=review_schema_path)
            if _parse_datetime(review["produced_at"], "review.produced_at") <= launch_started_at:
                raise GateError("review must be produced strictly after the semantic evaluator started")
            state["status"] = "completed"
            state["review"] = review
            state["review_content_sha256"] = _canonical_sha(review)
            state["review_sha256"] = review_source_sha256 or state["review_content_sha256"]
            if not SHA256_RE.fullmatch(str(state["review_sha256"])):
                raise GateError("review source sha256 is invalid")
            _atomic_write_json(state_path, state)
        elif review is not None:
            if launch_receipt is None:
                raise GateError("completed review state is missing its durable launch")
            validate_review(review, plan, target_manifest, claim_id=state["claim_id"], expected_run_id=state["claimed_run_id"], launch_receipt=launch_receipt, target_scope=target_scope, methods_path=methods_path, prompt_path=prompt_path, review_schema_path=review_schema_path)
            if _parse_datetime(review["produced_at"], "review.produced_at") <= _parse_datetime(launch_receipt["consumed_at"], "semantic evaluator started_at"):
                raise GateError("review must be produced strictly after the semantic evaluator started")
            if _canonical_sha(review) != state["review_content_sha256"]:
                raise GateError("completed initial review is immutable")

        stored_review = state["review"]
        if not isinstance(stored_review, dict) or not SHA256_RE.fullmatch(str(state["review_sha256"])):
            raise GateError("completed durable state has no valid review receipt")
        review_sha256 = state["review_sha256"]
        result["initial_review"] = {"authorized": False, "status": "completed-once", "reused_from_run_id": state["claimed_run_id"], "review_sha256": review_sha256, "evaluator_id": "elegant-initial-draft-evaluator", "evaluator_context_count": 1, "release_proof": False, "exhaustive_audit_proof": False}
        result["findings"] = stored_review["findings"]
        result["four_conditions"] = stored_review["four_conditions"]
        result["summary"] = stored_review["summary"]

        def preview(level: str) -> dict:
            policy = levels_doc["levels"][level]
            ids = _select_findings(stored_review["findings"], policy["selection"])
            return {"id": level, "label": policy["label"], "description": policy["description"], "max_rounds": policy["max_rounds"], "selected_finding_count": len(ids), "selected_finding_ids": ids}

        result["question"] = {"prompt": "初回診断の所見を確認し、どの深さまで改善しますか？", "recommended_level": stored_review["recommended_level"], "levels": [preview(level) for level in levels_doc["offered_order"]], "exhaustive_is_separate_opt_in": True, "exhaustive_preview": preview("exhaustive")}
        if selected_level is None:
            result["status"] = "awaiting-improvement-choice"
            result["instruction"] = "所見を先に提示し、ユーザーevent receiptを得るまで編集しない。"
            return result

        if selected_level not in levels_doc["levels"]:
            raise GateError(f"unknown selected_level: {selected_level}")
        if choice_event is None:
            raise GateError("selected_level requires --user-choice-event receipt")
        choice_time = _validate_user_event(choice_event, event_type="improvement-level-selected", plan=plan, baseline=baseline, review_sha256=review_sha256, selected_level=selected_level)
        review_time = _parse_datetime(stored_review["produced_at"], "stored review produced_at")
        if choice_time <= review_time:
            raise GateError("user choice event must occur strictly after the review was produced")
        if user_choice_ref is not None and user_choice_ref != choice_event["event_id"]:
            raise GateError("legacy user_choice_ref must match the user choice event_id")

        confirmation_id: str | None = None
        if selected_level == "exhaustive":
            if exhaustive_confirmation_event is None:
                raise GateError("exhaustive requires a separate exhaustive confirmation event")
            confirmation_time = _validate_user_event(exhaustive_confirmation_event, event_type="exhaustive-confirmed", plan=plan, baseline=baseline, review_sha256=review_sha256)
            if exhaustive_confirmation_event["event_id"] == choice_event["event_id"] or confirmation_time <= choice_time:
                raise GateError("exhaustive confirmation must be a different, later user event")
            confirmation_id = exhaustive_confirmation_event["event_id"]
        elif exhaustive_confirmation_event is not None or confirm_exhaustive:
            raise GateError("exhaustive confirmation is only valid for exhaustive selection")

        critical_exists = any(f["severity"] == "critical" for f in stored_review["findings"])
        risk_ack_id: str | None = None
        if selected_level == "accept-draft" and critical_exists:
            if risk_acknowledgement_event is None:
                raise GateError("accept-draft with critical findings requires a risk acknowledgement event")
            risk_time = _validate_user_event(risk_acknowledgement_event, event_type="critical-risk-acknowledged", plan=plan, baseline=baseline, review_sha256=review_sha256)
            if risk_acknowledgement_event["event_id"] == choice_event["event_id"] or risk_time < choice_time:
                raise GateError("risk acknowledgement must be a different, non-earlier user event")
            risk_ack_id = risk_acknowledgement_event["event_id"]
        elif risk_acknowledgement_event is not None:
            raise GateError("risk acknowledgement is only valid for critical accept-draft")

        policy = levels_doc["levels"][selected_level]
        selected_ids = _select_findings(stored_review["findings"], policy["selection"])
        edits_authorized = bool(selected_ids)
        stage_transition_authorized = policy["next_stage"] == "release"
        decision = {"schema_version": 1, "run_id": plan["run_id"], "subject": plan["subject"], "artifact_fingerprint_sha256": baseline, "baseline_target_manifest_sha256": binding["target_manifest_sha256"], "review_sha256": review_sha256, "selected_level": selected_level, "selected_by": "user", "user_choice_event_id": choice_event["event_id"], "user_choice_ref": choice_event["event_id"], "explicit_exhaustive_confirmation": selected_level == "exhaustive", "exhaustive_confirmation_event_id": confirmation_id, "critical_risk_acknowledgement_event_id": risk_ack_id, "improvement_authorized": edits_authorized, "selected_finding_ids": selected_ids, "max_rounds": policy["max_rounds"], "next_stage": policy["next_stage"], "next_profile": policy["next_profile"], "auto_promote_release": False, "auto_promote_exhaustive": False, "created_at": _now()}
        existing = state["decisions"].get(plan["run_id"])
        if existing is not None:
            comparable = dict(existing); comparable.pop("created_at", None)
            proposed = dict(decision); proposed.pop("created_at", None)
            if comparable != proposed:
                raise GateError("a different improvement decision already exists for this run")
            decision = existing
        else:
            state["decisions"][plan["run_id"]] = decision
            _atomic_write_json(state_path, state)

        result["status"] = "improvement-authorized" if edits_authorized else "stage-transition-authorized" if stage_transition_authorized else "usable-draft"
        result["decision"] = decision
        result["improvement"] = {"authorized": edits_authorized, "stage_transition_authorized": stage_transition_authorized, "selected_level": selected_level, "selected_by": "user", "user_choice_ref": choice_event["event_id"], "selected_finding_ids": selected_ids, "selected_finding_count": len(selected_ids), "max_rounds": policy["max_rounds"], "next_stage": policy["next_stage"], "next_profile": policy["next_profile"], "explicit_release_opt_in": selected_level in {"release", "exhaustive"}, "explicit_exhaustive_opt_in": selected_level == "exhaustive"}
        result["instruction"] = "selected_finding_idsだけをmax_rounds以内で改善する。" if edits_authorized else "選択されたactionable findingは0件。改善編集はno-opとする。"
        return result


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{label} must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verification-plan", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--target-path", action="append", required=True)
    parser.add_argument("--usable-draft-proof", required=True)
    parser.add_argument("--artifact-presentation-receipt")
    parser.add_argument("--pre-diagnostic-choice-event")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--review")
    parser.add_argument("--claim-id")
    parser.add_argument("--selected-level", choices=["accept-draft", "light", "standard", "detailed", "release", "exhaustive"])
    parser.add_argument("--user-choice-event")
    parser.add_argument("--exhaustive-confirmation-event")
    parser.add_argument("--risk-acknowledgement-event")
    parser.add_argument("--user-choice-ref")
    parser.add_argument("--confirm-exhaustive", action="store_true")
    parser.add_argument("--methods", default=str(DEFAULT_METHODS_PATH))
    parser.add_argument("--levels", default=str(DEFAULT_LEVELS_PATH))
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT_PATH))
    parser.add_argument("--review-schema", default=str(DEFAULT_REVIEW_SCHEMA_PATH))
    parser.add_argument("--decision-out")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        plan = _read_json(Path(args.verification_plan), "verification plan")
        repo_root = Path(args.repo_root).resolve(strict=True)
        state_dir = Path(args.state_dir).resolve(strict=False)
        runtime_paths = [
            Path(path).resolve(strict=False)
            for path in (
                args.review,
                args.artifact_presentation_receipt,
                args.pre_diagnostic_choice_event,
                args.user_choice_event,
                args.exhaustive_confirmation_event,
                args.risk_acknowledgement_event,
                args.decision_out,
                args.out,
            )
            if path
        ]
        target_scope = build_target_scope(
            [Path(path) for path in args.target_path],
            root=repo_root,
            state_dir=state_dir,
            runtime_paths=runtime_paths,
        )
        target_manifest = target_scope["target_manifest"]
        review_path = Path(args.review) if args.review else None
        review = _read_json(review_path, "initial review") if review_path else None
        usable_draft_proof = _read_json(Path(args.usable_draft_proof), "usable-draft proof")
        artifact_presentation_receipt = _read_json(Path(args.artifact_presentation_receipt), "artifact presentation receipt") if args.artifact_presentation_receipt else None
        pre_diagnostic_choice_event = _read_json(Path(args.pre_diagnostic_choice_event), "pre-diagnostic choice event") if args.pre_diagnostic_choice_event else None
        review_source_sha256 = _file_sha(review_path) if review_path else None
        choice_event = _read_json(Path(args.user_choice_event), "user choice event") if args.user_choice_event else None
        exhaustive_event = _read_json(Path(args.exhaustive_confirmation_event), "exhaustive confirmation event") if args.exhaustive_confirmation_event else None
        risk_event = _read_json(Path(args.risk_acknowledgement_event), "risk acknowledgement event") if args.risk_acknowledgement_event else None
        result = build_gate(plan, target_manifest=target_manifest, target_scope=target_scope, usable_draft_proof=usable_draft_proof, state_dir=state_dir, artifact_presentation_receipt=artifact_presentation_receipt, pre_diagnostic_choice_event=pre_diagnostic_choice_event, review=review, review_source_sha256=review_source_sha256, claim_id=args.claim_id, selected_level=args.selected_level, choice_event=choice_event, exhaustive_confirmation_event=exhaustive_event, risk_acknowledgement_event=risk_event, user_choice_ref=args.user_choice_ref, confirm_exhaustive=args.confirm_exhaustive, methods_path=Path(args.methods), levels_path=Path(args.levels), prompt_path=Path(args.prompt), review_schema_path=Path(args.review_schema))
        if args.decision_out:
            if "decision" not in result:
                raise GateError("--decision-out requires a validated user decision")
            _atomic_write_json(Path(args.decision_out), result["decision"])
        if args.out:
            _atomic_write_json(Path(args.out), result)
    except GateError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
