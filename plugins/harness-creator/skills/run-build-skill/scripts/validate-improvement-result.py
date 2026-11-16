#!/usr/bin/env python3
# /// script
# name: validate-improvement-result
# purpose: user-authorized finding setだけを扱ったbounded improvement receiptを検証する。
# inputs:
#   - argv: --review --decision --before-manifest --after-manifest --result --gate-state --target-root
# outputs:
#   - stdout / --out: validation verdict JSON
# contexts: [C, E]
# network: false
# write-scope: --out 指定先のみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Validate a post-improvement receipt against its immutable authorization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FINDING_ID_RE = re.compile(r"^IDR-[0-9]{3}$")
GLOB_META_RE = re.compile(r"[*?\[\]{}!]")
CONDITION_KEYS = {"C1", "C2", "C3", "C4"}
LEVELS = {"light", "standard", "detailed", "release", "exhaustive"}
STAGES = {"draft", "release"}
PROFILES = {"incremental", "exhaustive"}
SEVERITIES = {"critical", "high", "medium", "low"}


class ValidationError(ValueError):
    """The receipt cannot authorize a completion claim."""


def _read_json_value(path: Path, label: str) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read {label}: {exc}") from exc
    return value


def _read_json(path: Path, label: str) -> dict:
    value = _read_json_value(path, label)
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return value


def _file_sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValidationError(f"cannot hash {path}: {exc}") from exc


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty RFC3339 date-time")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"{label} must be an RFC3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{label} must be an RFC3339 date-time with timezone")
    return parsed


def _require_exact_keys(value: dict, required: set[str], label: str) -> None:
    missing = required - set(value)
    extra = set(value) - required
    if missing or extra:
        raise ValidationError(
            f"{label} fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _relative_path(value: Any, label: str) -> str:
    text = str(value or "")
    path = PurePosixPath(text)
    if (
        not text
        or "\\" in text
        or path.is_absolute()
        or text in {".", ".."}
        or ".." in path.parts
        or any(not part for part in path.parts)
    ):
        raise ValidationError(f"{label} must be a normalized relative path: {text!r}")
    normalized = path.as_posix()
    if normalized != text:
        raise ValidationError(f"{label} must be a normalized relative path: {text!r}")
    return normalized


def _unique_strings(value: Any, label: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValidationError(f"{label} must be an array of non-empty strings")
    if non_empty and not value:
        raise ValidationError(f"{label} must be non-empty")
    if len(value) != len(set(value)):
        raise ValidationError(f"{label} must contain unique values")
    return value


def _validate_manifest(value: Any, label: str) -> dict[str, tuple[str, int]]:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{label} must be a non-empty array")
    result: dict[str, tuple[str, int]] = {}
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValidationError(f"{label}[{index}] must be an object")
        _require_exact_keys(record, {"path", "sha256", "size"}, f"{label}[{index}]")
        path = _relative_path(record.get("path"), f"{label}[{index}].path")
        digest = record.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValidationError(f"{label}[{index}].sha256 is invalid")
        size = record.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValidationError(f"{label}[{index}].size is invalid")
        if path in result:
            raise ValidationError(f"{label} contains duplicate path: {path}")
        result[path] = (digest, size)
    return result


def _scope_path(value: Any, label: str, *, allow_dot: bool = False) -> str:
    if allow_dot and value == ".":
        return "."
    return _relative_path(value, label)


def _is_below(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_excluded(relative: str, exclusions: list[str]) -> bool:
    return any(relative == excluded or relative.startswith(excluded + "/") for excluded in exclusions)


def _reject_symlink_components(path: Path, root: Path, label: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes target_root") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValidationError(f"{label} contains symlink: {relative.as_posix()}")


def _resolve_target_root(target_root: Path, state_value: Any) -> Path:
    if target_root.is_symlink():
        raise ValidationError("target_root must not be a symlink")
    try:
        resolved = target_root.resolve(strict=True)
    except OSError as exc:
        raise ValidationError(f"target_root must be an existing directory: {exc}") from exc
    if not target_root.is_absolute() or str(target_root) != str(resolved):
        raise ValidationError("target_root must use its canonical absolute identity")
    if not resolved.is_dir() or not isinstance(state_value, str):
        raise ValidationError("authoritative gate state target_root is invalid")
    try:
        state_root = Path(state_value).resolve(strict=True)
    except OSError as exc:
        raise ValidationError("authoritative gate state target_root is invalid") from exc
    if state_value != str(state_root) or state_root != resolved:
        raise ValidationError("target_root does not match authoritative gate state")
    return resolved


def _validate_target_roots(value: Any, root: Path) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValidationError("authoritative gate state target_roots must be non-empty")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(f"target_roots[{index}] must be an object")
        _require_exact_keys(item, {"path", "kind"}, f"target_roots[{index}]")
        relative = _scope_path(item.get("path"), f"target_roots[{index}].path", allow_dot=True)
        kind = item.get("kind")
        if kind not in {"file", "directory"}:
            raise ValidationError(f"target_roots[{index}].kind is invalid")
        candidate = root if relative == "." else root / relative
        _reject_symlink_components(candidate, root, "target root")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ValidationError(f"target root does not exist: {relative}") from exc
        if not _is_below(resolved, root):
            raise ValidationError(f"target root escapes target_root: {relative}")
        actual_kind = "file" if resolved.is_file() else "directory" if resolved.is_dir() else None
        if actual_kind != kind:
            raise ValidationError(f"target_roots[{index}] kind does not match the actual target")
        normalized.append({"path": relative, "kind": kind})
    if normalized != sorted(normalized, key=lambda item: item["path"]):
        raise ValidationError("authoritative gate state target_roots must be sorted")
    if len({item["path"] for item in normalized}) != len(normalized):
        raise ValidationError("authoritative gate state target_roots must be unique")
    return normalized


def _expected_exclusions(gate_state_path: Path, root: Path, roots: list[dict[str, str]]) -> list[str]:
    if gate_state_path.is_symlink():
        raise ValidationError("authoritative gate state must not be a symlink")
    try:
        state_dir = gate_state_path.resolve(strict=True).parent
    except OSError as exc:
        raise ValidationError(f"cannot resolve authoritative gate state: {exc}") from exc
    if not _is_below(state_dir, root) or state_dir == root:
        return []
    relative = state_dir.relative_to(root).as_posix()
    for item in roots:
        if item["kind"] != "directory":
            continue
        target = root if item["path"] == "." else root / item["path"]
        if state_dir == target or _is_below(state_dir, target):
            return [relative]
    return []


def _validate_exclusions(
    value: Any,
    *,
    gate_state_path: Path,
    root: Path,
    roots: list[dict[str, str]],
    pre_files: dict[str, tuple[str, int]],
) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError("authoritative gate state exclusions must be an array")
    exclusions = [
        _scope_path(item, f"target_exclusions[{index}]")
        for index, item in enumerate(value)
    ]
    if exclusions != sorted(set(exclusions)):
        raise ValidationError("authoritative gate state exclusions must be sorted and unique")
    if exclusions != _expected_exclusions(gate_state_path, root, roots):
        raise ValidationError("authoritative gate state exclusions are not the closed runtime set")
    if any(_is_excluded(path, exclusions) for path in pre_files):
        raise ValidationError("authoritative gate state exclusions overlap the pre snapshot")
    return exclusions


def _actual_target_manifest(
    *, root: Path, roots: list[dict[str, str]], exclusions: list[str]
) -> list[dict[str, Any]]:
    files: dict[str, Path] = {}

    def visit(path: Path) -> None:
        relative = path.relative_to(root).as_posix()
        if _is_excluded(relative, exclusions):
            return
        if path.is_symlink():
            raise ValidationError(f"actual target closure contains symlink: {relative}")
        try:
            entries = sorted(os.scandir(path), key=lambda entry: entry.name)
        except OSError as exc:
            raise ValidationError(f"cannot enumerate actual target closure at {relative}: {exc}") from exc
        for entry in entries:
            candidate = Path(entry.path)
            child_relative = candidate.relative_to(root).as_posix()
            if _is_excluded(child_relative, exclusions):
                continue
            if entry.is_symlink():
                raise ValidationError(f"actual target closure contains symlink: {child_relative}")
            if entry.is_dir(follow_symlinks=False):
                visit(candidate)
            elif entry.is_file(follow_symlinks=False):
                files[child_relative] = candidate
            else:
                raise ValidationError(f"actual target closure contains a non-regular file: {child_relative}")

    for item in roots:
        candidate = root if item["path"] == "." else root / item["path"]
        relative = item["path"]
        if relative != "." and _is_excluded(relative, exclusions):
            raise ValidationError(f"target root is hidden by exclusions: {relative}")
        _reject_symlink_components(candidate, root, "actual target closure")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ValidationError(f"actual target closure is missing target root: {relative}") from exc
        if not _is_below(resolved, root):
            raise ValidationError(f"actual target closure escapes target_root: {relative}")
        if item["kind"] == "file":
            files[relative] = candidate
        else:
            visit(candidate)
    if not files:
        raise ValidationError("actual target closure contains no regular files")
    return [
        {"path": relative, "sha256": _file_sha(path), "size": path.stat().st_size}
        for relative, path in sorted(files.items())
    ]


def _validate_authoritative_state(
    *,
    state: dict,
    state_path: Path,
    target_root: Path,
    review: dict,
    review_path: Path,
    decision: dict,
    before: list[dict],
    before_files: dict[str, tuple[str, int]],
) -> tuple[Path, list[dict[str, str]], list[str]]:
    required = {
        "schema_version", "artifact_fingerprint_sha256", "subject", "contract_binding",
        "target_root", "target_roots", "target_exclusions", "target_manifest", "status",
        "claim_id", "claimed_run_id", "created_at", "review", "review_sha256",
        "review_content_sha256", "decisions",
    }
    _require_exact_keys(state, required, "authoritative gate state")
    if state.get("schema_version") != 2 or state.get("status") != "completed":
        raise ValidationError("authoritative gate state must be completed schema_version=2")
    root = _resolve_target_root(target_root, state.get("target_root"))
    roots = _validate_target_roots(state.get("target_roots"), root)
    exclusions = _validate_exclusions(
        state.get("target_exclusions"),
        gate_state_path=state_path,
        root=root,
        roots=roots,
        pre_files=before_files,
    )
    if state.get("target_manifest") != before:
        raise ValidationError("authoritative gate state pre snapshot does not match before manifest")
    if state.get("review") != review:
        raise ValidationError("authoritative gate state review does not match supplied review")
    if state.get("review_sha256") != _file_sha(review_path):
        raise ValidationError("authoritative gate state review digest does not match supplied review")
    if state.get("review_content_sha256") != _canonical_sha(review):
        raise ValidationError("authoritative gate state review content digest is invalid")
    if state.get("artifact_fingerprint_sha256") != review.get("baseline_fingerprint_sha256"):
        raise ValidationError("authoritative gate state artifact fingerprint does not match review")
    if state.get("subject") != review.get("subject") or state.get("claimed_run_id") != review.get("run_id"):
        raise ValidationError("authoritative gate state run_id/subject does not match review")
    decisions = state.get("decisions")
    if not isinstance(decisions, dict) or decisions.get(decision.get("run_id")) != decision:
        raise ValidationError("authoritative gate state decision does not match supplied decision")
    return root, roots, exclusions


def _finding_remediation_paths(finding: dict) -> set[str]:
    finding_id = finding.get("id")
    location = finding.get("location")
    if not isinstance(location, dict) or not location.get("path"):
        raise ValidationError(f"finding {finding_id} location.path is required")
    location_path = _relative_path(location["path"], f"finding {finding_id} location.path")
    raw_paths = _unique_strings(
        finding.get("remediation_paths"),
        f"finding {finding_id} remediation_paths",
        non_empty=True,
    )
    paths = {
        _relative_path(path, f"finding {finding_id} remediation_paths item")
        for path in raw_paths
    }
    if any(GLOB_META_RE.search(path) for path in paths):
        raise ValidationError(f"finding {finding_id} remediation_paths must be exact, not glob paths")
    if location_path not in paths:
        raise ValidationError(f"finding {finding_id} remediation_paths must include location.path")
    return paths


def _validate_review(review: dict) -> dict[str, dict]:
    if review.get("schema_version") != 1:
        raise ValidationError("review requires schema_version=1")
    for field in ("run_id", "subject"):
        if not str(review.get(field, "")).strip():
            raise ValidationError(f"review {field} is required")
    findings = review.get("findings")
    if not isinstance(findings, list):
        raise ValidationError("review findings must be an array")
    by_id: dict[str, dict] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValidationError("review finding must be an object")
        finding_id = str(finding.get("id", ""))
        if not FINDING_ID_RE.fullmatch(finding_id) or finding_id in by_id:
            raise ValidationError(f"invalid or duplicate review finding: {finding_id!r}")
        if finding.get("severity") not in SEVERITIES:
            raise ValidationError(f"invalid review finding severity: {finding_id}")
        normalized = dict(finding)
        normalized["_validated_remediation_paths"] = _finding_remediation_paths(finding)
        by_id[finding_id] = normalized
    return by_id


def _path_is_in_target_roots(path: str, roots: list[dict[str, str]]) -> bool:
    for item in roots:
        root_path = item["path"]
        if item["kind"] == "file" and path == root_path:
            return True
        if item["kind"] == "directory" and (
            root_path == "." or path.startswith(root_path + "/")
        ):
            return True
    return False


def _validate_decision(
    decision: dict, review: dict, review_path: Path, before_manifest: list[dict]
) -> list[str]:
    required = {
        "schema_version",
        "run_id",
        "subject",
        "artifact_fingerprint_sha256",
        "review_sha256",
        "selected_level",
        "selected_by",
        "user_choice_ref",
        "improvement_authorized",
        "selected_finding_ids",
        "max_rounds",
        "baseline_target_manifest_sha256",
        "next_stage",
        "next_profile",
        "auto_promote_release",
        "auto_promote_exhaustive",
        "explicit_exhaustive_confirmation",
        "user_choice_event_id",
        "exhaustive_confirmation_event_id",
        "critical_risk_acknowledgement_event_id",
        "created_at",
    }
    _require_exact_keys(decision, required, "decision")
    if decision.get("schema_version") != 1:
        raise ValidationError("decision requires schema_version=1")
    if decision.get("run_id") != review.get("run_id"):
        raise ValidationError("decision run_id does not match review")
    if decision.get("subject") != review.get("subject"):
        raise ValidationError("decision subject does not match review")
    if decision.get("artifact_fingerprint_sha256") != review.get("baseline_fingerprint_sha256"):
        raise ValidationError("decision artifact fingerprint does not match review")
    if decision.get("selected_by") != "user" or not str(decision.get("user_choice_ref", "")).strip():
        raise ValidationError("decision requires a user choice provenance")
    choice_event_id = decision.get("user_choice_event_id")
    if not isinstance(choice_event_id, str) or not choice_event_id or choice_event_id != decision.get("user_choice_ref"):
        raise ValidationError("decision user choice event is inconsistent")
    _parse_datetime(decision.get("created_at"), "decision created_at")
    if decision.get("selected_level") == "accept-draft":
        raise ValidationError("accept-draft must not start the improvement executor")
    if decision.get("selected_level") not in LEVELS:
        raise ValidationError("decision selected_level is invalid or unanswered")
    if decision.get("improvement_authorized") is not True:
        raise ValidationError("decision has not authorized improvement")
    selected = _unique_strings(
        decision.get("selected_finding_ids"),
        "decision selected_finding_ids",
        non_empty=True,
    )
    if any(not FINDING_ID_RE.fullmatch(item) for item in selected):
        raise ValidationError("decision selected_finding_ids contains an invalid ID")
    max_rounds = decision.get("max_rounds")
    if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or not 1 <= max_rounds <= 3:
        raise ValidationError("decision max_rounds must be an integer from 1 to 3")
    if decision.get("next_stage") not in STAGES:
        raise ValidationError("decision next_stage is invalid")
    if decision.get("next_profile") not in PROFILES:
        raise ValidationError("decision next_profile is invalid")
    if (
        decision.get("auto_promote_release") is not False
        or decision.get("auto_promote_exhaustive") is not False
    ):
        raise ValidationError("decision must disable auto promotion")
    level = decision["selected_level"]
    if decision["next_stage"] == "release" and level not in {"release", "exhaustive"}:
        raise ValidationError("next_stage=release requires an explicit release decision")
    if decision["next_profile"] == "exhaustive" and level != "exhaustive":
        raise ValidationError("next_profile=exhaustive requires an explicit exhaustive decision")
    if level == "release" and decision["next_stage"] != "release":
        raise ValidationError("release decision must set next_stage=release")
    if level == "exhaustive" and (
        decision["next_stage"] != "release"
        or decision["next_profile"] != "exhaustive"
        or decision.get("explicit_exhaustive_confirmation") is not True
        or not isinstance(decision.get("exhaustive_confirmation_event_id"), str)
        or decision.get("exhaustive_confirmation_event_id") == choice_event_id
    ):
        raise ValidationError("exhaustive decision requires its explicit confirmed stage/profile")
    if level != "exhaustive" and (
        decision.get("explicit_exhaustive_confirmation") is not False
        or decision.get("exhaustive_confirmation_event_id") is not None
    ):
        raise ValidationError("non-exhaustive decision cannot carry exhaustive confirmation")
    if decision.get("critical_risk_acknowledgement_event_id") is not None:
        raise ValidationError("an authorized improvement decision cannot carry accept-draft risk acknowledgement")
    if decision.get("review_sha256") != _file_sha(review_path):
        raise ValidationError("decision review digest does not match review")
    if decision.get("baseline_target_manifest_sha256") != _canonical_sha(before_manifest):
        raise ValidationError("decision baseline manifest digest does not match")
    return selected


def _validate_result_shape(result: dict) -> None:
    required = {
        "schema_version",
        "run_id",
        "subject",
        "review_sha256",
        "decision_sha256",
        "baseline_target_manifest_sha256",
        "post_target_manifest_sha256",
        "selected_level",
        "rounds_used",
        "changed_paths",
        "change_trace",
        "finding_outcomes",
        "four_conditions",
        "completion_status",
        "next_stage",
        "next_profile",
        "auto_promote_release",
        "auto_promote_exhaustive",
        "produced_at",
    }
    _require_exact_keys(result, required, "result")
    if result.get("schema_version") != 1:
        raise ValidationError("result requires schema_version=1")


def _validate_evidence_refs(
    value: Any,
    *,
    label: str,
    target_root: Path,
    actual_files: dict[str, tuple[str, int]],
) -> None:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{label} must be a non-empty array")
    seen: set[tuple[str, int, str]] = set()
    for index, reference in enumerate(value):
        if not isinstance(reference, dict):
            raise ValidationError(f"{label}[{index}] must be an evidence object")
        _require_exact_keys(reference, {"path", "line", "sha256"}, f"{label}[{index}]")
        path = _relative_path(reference.get("path"), f"{label}[{index}].path")
        if path not in actual_files:
            raise ValidationError(f"evidence path is not in the actual target closure: {path}")
        digest = reference.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValidationError(f"evidence digest is invalid for {path}")
        if digest != actual_files[path][0]:
            raise ValidationError(f"evidence digest does not match the actual file: {path}")
        line = reference.get("line")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            raise ValidationError(f"evidence line is invalid for {path}")
        evidence_path = target_root / path
        _reject_symlink_components(evidence_path, target_root, "evidence path")
        try:
            resolved = evidence_path.resolve(strict=True)
            resolved.relative_to(target_root)
            line_count = len(resolved.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValidationError(f"cannot read evidence path as target text: {path}") from exc
        if line > line_count:
            raise ValidationError(f"evidence line is outside the actual file: {path}:{line}")
        identity = (path, line, digest)
        if identity in seen:
            raise ValidationError(f"{label} contains duplicate evidence refs")
        seen.add(identity)


def validate_files(
    *,
    review_path: Path,
    decision_path: Path,
    before_manifest_path: Path,
    after_manifest_path: Path,
    result_path: Path,
    gate_state_path: Path,
    target_root: Path,
) -> dict:
    """Validate authoritative authorization, actual edits, outcomes, and completion."""
    review = _read_json(review_path, "review")
    decision = _read_json(decision_path, "decision")
    before = _read_json_value(before_manifest_path, "before manifest")
    after = _read_json_value(after_manifest_path, "after manifest")
    result = _read_json(result_path, "result")
    state = _read_json(gate_state_path, "authoritative gate state")

    before_files = _validate_manifest(before, "before manifest")
    after_files = _validate_manifest(after, "after manifest")
    findings = _validate_review(review)
    selected = _validate_decision(decision, review, review_path, before)
    unknown_selected = set(selected) - set(findings)
    if unknown_selected:
        raise ValidationError(f"decision references unknown review findings: {sorted(unknown_selected)}")

    _validate_result_shape(result)
    if result.get("run_id") != review.get("run_id") or result.get("subject") != review.get("subject"):
        raise ValidationError("result run_id/subject does not match review")
    if result.get("review_sha256") != _file_sha(review_path):
        raise ValidationError("result review digest does not match")
    if result.get("decision_sha256") != _file_sha(decision_path):
        raise ValidationError("result decision digest does not match")
    if result.get("baseline_target_manifest_sha256") != _canonical_sha(before):
        raise ValidationError("result baseline manifest digest does not match")
    if result.get("post_target_manifest_sha256") != _canonical_sha(after):
        raise ValidationError("result post manifest digest does not match")
    if result.get("selected_level") != decision.get("selected_level"):
        raise ValidationError("result selected_level does not match decision")

    actual_root, target_roots, target_exclusions = _validate_authoritative_state(
        state=state,
        state_path=gate_state_path,
        target_root=target_root,
        review=review,
        review_path=review_path,
        decision=decision,
        before=before,
        before_files=before_files,
    )
    actual_manifest = _actual_target_manifest(
        root=actual_root,
        roots=target_roots,
        exclusions=target_exclusions,
    )
    if actual_manifest != after:
        raise ValidationError("after manifest does not equal the actual target closure")
    actual_files = _validate_manifest(actual_manifest, "actual target closure")
    for finding_id, finding in findings.items():
        outside_scope = sorted(
            path
            for path in finding["_validated_remediation_paths"]
            if not _path_is_in_target_roots(path, target_roots)
        )
        if outside_scope:
            raise ValidationError(
                f"finding {finding_id} remediation scope escapes target_roots: {outside_scope}"
            )

    rounds_used = result.get("rounds_used")
    if (
        not isinstance(rounds_used, int)
        or isinstance(rounds_used, bool)
        or not 1 <= rounds_used <= decision["max_rounds"]
    ):
        raise ValidationError("result rounds_used exceeds decision max_rounds or is invalid")

    changed = _unique_strings(result.get("changed_paths"), "result changed_paths")
    normalized_changed = [_relative_path(path, "result changed_paths item") for path in changed]
    manifest_diff = sorted(
        path
        for path in set(before_files) | set(after_files)
        if before_files.get(path) != after_files.get(path)
    )
    if set(normalized_changed) != set(manifest_diff):
        raise ValidationError(
            f"result changed_paths does not equal manifest diff: expected={manifest_diff}"
        )

    traces = result.get("change_trace")
    if not isinstance(traces, list):
        raise ValidationError("result change_trace must be an array")
    trace_paths: set[str] = set()
    for index, trace in enumerate(traces):
        if not isinstance(trace, dict):
            raise ValidationError(f"change_trace[{index}] must be an object")
        _require_exact_keys(
            trace,
            {"path", "finding_ids", "summary", "validation_refs"},
            f"change_trace[{index}]",
        )
        path = _relative_path(trace.get("path"), f"change_trace[{index}].path")
        if path in trace_paths:
            raise ValidationError(f"change_trace has duplicate path: {path}")
        trace_paths.add(path)
        ids = _unique_strings(
            trace.get("finding_ids"), f"change_trace[{index}].finding_ids", non_empty=True
        )
        unselected = set(ids) - set(selected)
        if unselected:
            raise ValidationError(f"change_trace declares an unselected finding: {sorted(unselected)}")
        if not str(trace.get("summary", "")).strip():
            raise ValidationError(f"change_trace[{index}] summary is required")
        _unique_strings(
            trace.get("validation_refs"),
            f"change_trace[{index}].validation_refs",
            non_empty=True,
        )
        for finding_id in ids:
            if path not in findings[finding_id]["_validated_remediation_paths"]:
                raise ValidationError(
                    f"changed path {path!r} is not in finding {finding_id} remediation scope"
                )
    if trace_paths != set(manifest_diff):
        raise ValidationError("change_trace paths must exactly cover the manifest diff")

    outcomes = result.get("finding_outcomes")
    if not isinstance(outcomes, dict):
        raise ValidationError("finding_outcomes must be an object")
    _require_exact_keys(outcomes, {"resolved", "residual", "regressed"}, "finding_outcomes")
    outcome_sets = {
        key: set(_unique_strings(outcomes[key], f"finding_outcomes.{key}"))
        for key in ("resolved", "residual", "regressed")
    }
    if any(
        outcome_sets[left] & outcome_sets[right]
        for left, right in (("resolved", "residual"), ("resolved", "regressed"), ("residual", "regressed"))
    ):
        raise ValidationError("finding outcome sets must be disjoint")
    outcome_union = set().union(*outcome_sets.values())
    unselected_outcomes = outcome_union - set(selected)
    if unselected_outcomes:
        raise ValidationError(
            f"finding outcomes declare an unselected finding: {sorted(unselected_outcomes)}"
        )
    if outcome_union != set(selected):
        raise ValidationError("finding outcomes must form the closed set of selected findings")

    conditions = result.get("four_conditions")
    if not isinstance(conditions, dict) or set(conditions) != CONDITION_KEYS:
        raise ValidationError("result four_conditions must contain exactly C1-C4")
    for key, condition in conditions.items():
        if not isinstance(condition, dict):
            raise ValidationError(f"four_conditions.{key} must be an object")
        _require_exact_keys(condition, {"verdict", "summary", "evidence_refs"}, f"four_conditions.{key}")
        if condition.get("verdict") not in {"PASS", "FAIL", "PARTIAL"}:
            raise ValidationError(f"four_conditions.{key} verdict is invalid")
        if not str(condition.get("summary", "")).strip():
            raise ValidationError(f"four_conditions.{key} summary is required")
        _validate_evidence_refs(
            condition.get("evidence_refs"),
            label=f"four_conditions.{key}.evidence_refs",
            target_root=actual_root,
            actual_files=actual_files,
        )

    if result.get("completion_status") not in {"complete", "incomplete", "blocked"}:
        raise ValidationError("result completion_status is invalid")
    if result.get("next_stage") != decision.get("next_stage"):
        raise ValidationError("result next_stage differs from explicit decision")
    if result.get("next_profile") != decision.get("next_profile"):
        raise ValidationError("result next_profile differs from explicit decision")
    if (
        result.get("auto_promote_release") is not False
        or result.get("auto_promote_exhaustive") is not False
    ):
        raise ValidationError("result must disable auto promotion")
    _parse_datetime(result.get("produced_at"), "result produced_at")

    if result["completion_status"] == "complete":
        if outcome_sets["regressed"]:
            raise ValidationError("complete result cannot contain regressed findings")
        residual = sorted(outcome_sets["residual"])
        if residual:
            raise ValidationError(
                f"complete result cannot leave residual selected findings: {residual}"
            )
        nonpass = sorted(
            key for key, condition in conditions.items() if condition["verdict"] != "PASS"
        )
        if nonpass:
            raise ValidationError(
                f"complete result requires C1-C4 PASS; non-pass={nonpass}"
            )
        traced_findings = {
            finding_id
            for trace in traces
            if trace["path"] in manifest_diff
            for finding_id in trace["finding_ids"]
        }
        missing_resolved_trace = sorted(outcome_sets["resolved"] - traced_findings)
        if missing_resolved_trace:
            raise ValidationError(
                "resolved finding requires an actual changed source trace: "
                f"{missing_resolved_trace}"
            )

    return {
        "schema_version": 1,
        "status": "pass",
        "run_id": result["run_id"],
        "subject": result["subject"],
        "completion_status": result["completion_status"],
        "selected_finding_ids": selected,
        "changed_paths": sorted(normalized_changed),
        "rounds_used": rounds_used,
        "max_rounds": decision["max_rounds"],
        "next_stage": result["next_stage"],
        "next_profile": result["next_profile"],
        "auto_promote_release": False,
        "auto_promote_exhaustive": False,
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--review", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--before-manifest", required=True)
    parser.add_argument("--after-manifest", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--gate-state", required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        verdict = validate_files(
            review_path=Path(args.review),
            decision_path=Path(args.decision),
            before_manifest_path=Path(args.before_manifest),
            after_manifest_path=Path(args.after_manifest),
            result_path=Path(args.result),
            gate_state_path=Path(args.gate_state),
            target_root=Path(args.target_root),
        )
        if args.out:
            _write_json(Path(args.out), verdict)
    except ValidationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
