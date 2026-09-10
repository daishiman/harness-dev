#!/usr/bin/env python3
# /// script
# name: build-external-intelligence-runtime
# purpose: Claude Code / Codex 共通の通常runtime requestを、中央external-intelligence engineの有界検索・選択・再利用・終了時観測へ変換する。
# inputs:
#   - argv: --request <request JSON path> | --request-json <inline request JSON>
# outputs:
#   - stdout: external-intelligence-runtime.schema.json#/definitions/output 準拠JSON
#   - exit: 0=artifact継続（memory warningを含む） / 2=request contract不正
# contexts: [A, C, E]
# network: false
# write-scope: 中央engineが解決するproject-scope stateのみ
# dependencies: [build-external-intelligence.py]
# requires-python: ">=3.10"
# ///
"""Bounded, provider-neutral normal-runtime adapter for external intelligence."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


CONTRACT_ID = "external-intelligence-runtime-v1"
SCHEMA_VERSION = 1
ENGINE_PATH = Path(__file__).resolve().with_name("build-external-intelligence.py")
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ENGINE_TIMEOUT_SECONDS = 5
SEARCH_LIMIT_MAX = 5
SCORE_THRESHOLD = 1.0
SUMMARY_MAX_BYTES = 512
SEARCH_RESULTS_MAX_BYTES = 4_096
DETAIL_MAX_BYTES = 4_096
DETAILS_TOTAL_MAX_BYTES = 16_384
ENTRY_ID_RE = re.compile(r"^ei-[0-9a-f]{12}(?:-(?:[2-9]|[1-9][0-9]+))?$")
RUNTIMES = {"codex": "codex", "claude-code": "claude"}
OUTCOMES = {"helpful", "neutral", "unhelpful"}
ENTRY_STATUSES = {"observation", "candidate", "verified", "promoted", "superseded"}
ENTRY_REQUIRED_KEYS = {
    "schema_version",
    "id",
    "status",
    "title",
    "summary",
    "rule",
    "tags",
    "countercondition",
    "fingerprint",
    "identity_text",
    "created_at",
    "last_seen_at",
    "observations",
    "reuses",
    "variants",
    "observation_count",
    "context_count",
    "evidence_count",
    "helpful_reuse_count",
}
ENTRY_OPTIONAL_KEYS = {
    "resolution_status",
    "duplicate_candidates",
    "distinct_reason",
    "promotion",
    "supersession",
}
THIN_ENTRY_KEYS = {
    "id",
    "status",
    "title",
    "summary",
    "rule",
    "tags",
    "resolution_status",
    "observation_count",
    "context_count",
    "evidence_count",
    "helpful_reuse_count",
    "last_seen_at",
    "score",
}
USER_SCOPE_ENV = {
    "HARNESS_INTELLIGENCE_HOME",
    "PLUGIN_DATA",
    "CLAUDE_PLUGIN_DATA",
    "XDG_STATE_HOME",
    "LOCALAPPDATA",
}


class RequestError(ValueError):
    """The canonical runtime request is invalid."""


class MemorySidecarError(RuntimeError):
    """Memory is unavailable, but artifact generation remains authorized."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _json_bytes(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _truncate_utf8(value: Any, limit: int) -> str:
    raw = str(value or "").encode("utf-8")
    if len(raw) <= limit:
        return raw.decode("utf-8")
    return raw[:limit].decode("utf-8", errors="ignore")


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RequestError(f"{label} must be an object")
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise RequestError(f"{label} keys mismatch: missing={missing}, extra={extra}")
    return value


def _text(value: Any, label: str, *, maximum: int = 8_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestError(f"{label} must be a non-empty string")
    result = value.strip()
    if len(result) > maximum:
        raise RequestError(f"{label} exceeds {maximum} characters")
    return result


def _entry_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ENTRY_ID_RE.fullmatch(value):
        raise RequestError(f"{label} has invalid entry id")
    return value


def _project_root(value: Any) -> Path:
    raw = _text(value, "project_root")
    try:
        root = Path(raw).expanduser().resolve(strict=True)
    except OSError as exc:
        raise RequestError("project_root must be an existing directory") from exc
    if not root.is_dir():
        raise RequestError("project_root must be an existing directory")
    return root


def _validate_state(value: Any, *, run_id: str, project_root: Path) -> dict[str, Any]:
    state = _exact(
        value,
        {
            "schema_version",
            "contract_id",
            "run_id",
            "project_root",
            "query",
            "candidate_ids",
            "selected_ids",
            "phase",
            "memory_status",
        },
        "state",
    )
    if state["schema_version"] != SCHEMA_VERSION or state["contract_id"] != CONTRACT_ID:
        raise RequestError("state schema_version/contract_id mismatch")
    if state["run_id"] != run_id or state["project_root"] != str(project_root):
        raise RequestError("state does not belong to this run/project")
    if state["phase"] not in {"searched", "adopted", "finished"}:
        raise RequestError("state phase is invalid")
    if state["memory_status"] not in {"available", "unavailable"}:
        raise RequestError("state memory_status is invalid")
    _text(state["query"], "state.query")
    for key in ("candidate_ids", "selected_ids"):
        ids = state[key]
        if not isinstance(ids, list) or len(ids) > SEARCH_LIMIT_MAX:
            raise RequestError(f"state.{key} must be an array of at most 5 ids")
        checked = [_entry_id(item, f"state.{key}") for item in ids]
        if len(checked) != len(set(checked)):
            raise RequestError(f"state.{key} must be unique")
    if not set(state["selected_ids"]).issubset(state["candidate_ids"]):
        raise RequestError("state.selected_ids must be returned candidate ids")
    return json.loads(json.dumps(state))


def _validate_request(value: Any) -> tuple[dict[str, Any], Path]:
    if not isinstance(value, dict):
        raise RequestError("request must be an object")
    operation = value.get("operation")
    common = {
        "schema_version", "contract_id", "operation", "runtime", "run_id",
        "project_root", "context_id",
    }
    operation_keys = {
        "search": common | {"query", "limit"},
        "adopt": common | {"state", "selection", "evidence_ref", "evidence_source"},
        "finish": common | {"state", "capture"},
    }
    if operation not in operation_keys:
        raise RequestError("operation must be search, adopt, or finish")
    request = _exact(value, operation_keys[operation], "request")
    if request["schema_version"] != SCHEMA_VERSION or request["contract_id"] != CONTRACT_ID:
        raise RequestError("request schema_version/contract_id mismatch")
    if request["runtime"] not in RUNTIMES:
        raise RequestError("runtime must be codex or claude-code")
    _text(request["run_id"], "run_id")
    _text(request["context_id"], "context_id")
    root = _project_root(request["project_root"])
    if operation == "search":
        _text(request["query"], "query")
        if isinstance(request["limit"], bool) or not isinstance(request["limit"], int):
            raise RequestError("limit must be an integer")
        if request["limit"] < 1 or request["limit"] > SEARCH_LIMIT_MAX:
            raise RequestError("limit must be between 1 and 5")
    else:
        state = _validate_state(request["state"], run_id=request["run_id"], project_root=root)
        if state["phase"] == "finished":
            raise RequestError("finished state is terminal")
        if operation == "adopt":
            _text(request["evidence_ref"], "evidence_ref")
            _text(request["evidence_source"], "evidence_source")
            selection = request["selection"]
            if not isinstance(selection, list) or not selection or len(selection) > SEARCH_LIMIT_MAX:
                raise RequestError("selection must contain 1 to 5 items")
            ids: list[str] = []
            for index, raw in enumerate(selection):
                item = _exact(raw, {"id", "outcome"}, f"selection[{index}]")
                ids.append(_entry_id(item["id"], f"selection[{index}].id"))
                if item["outcome"] not in OUTCOMES:
                    raise RequestError(f"selection[{index}].outcome is invalid")
            if len(ids) != len(set(ids)):
                raise RequestError("selection ids must be unique")
            if not set(ids).issubset(state["candidate_ids"]):
                raise RequestError("selection id was not returned as a candidate")
        else:
            capture = request["capture"]
            if capture is not None:
                capture = _exact(
                    capture,
                    {
                        "title", "summary", "rule", "evidence_ref", "evidence_source",
                        "tags", "countercondition",
                    },
                    "capture",
                )
                for key in ("title", "summary", "rule", "evidence_ref", "evidence_source"):
                    _text(capture[key], f"capture.{key}")
                _text(capture["countercondition"], "capture.countercondition", maximum=8_000)
                if not isinstance(capture["tags"], list) or len(capture["tags"]) > 20:
                    raise RequestError("capture.tags must be an array of at most 20 strings")
                for tag in capture["tags"]:
                    _text(tag, "capture.tags[]", maximum=100)
    return request, root


def _engine_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in USER_SCOPE_ENV:
        env.pop(key, None)
    return env


def _engine_exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label} payload shape drift: {actual}",
        )
    return value


def _engine_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label} must be a non-empty string",
        )
    return value


def _engine_count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label} must be a non-negative integer",
        )
    return value


def _validate_entry_common(raw: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MemorySidecarError(
            "memory_unavailable", f"external intelligence {label} must be an object"
        )
    keys = set(raw)
    if not ENTRY_REQUIRED_KEYS.issubset(keys) or not keys.issubset(
        ENTRY_REQUIRED_KEYS | ENTRY_OPTIONAL_KEYS
    ):
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label} entry shape drift: {sorted(keys)}",
        )
    entry_id = raw.get("id")
    if not isinstance(entry_id, str) or not ENTRY_ID_RE.fullmatch(entry_id):
        raise MemorySidecarError(
            "memory_unavailable", f"external intelligence {label}.id is invalid"
        )
    if raw.get("schema_version") != 1:
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label}.schema_version is invalid",
        )
    for key in (
        "title",
        "summary",
        "rule",
        "fingerprint",
        "identity_text",
        "created_at",
        "last_seen_at",
    ):
        _engine_text(raw.get(key), f"{label}.{key}")
    if raw.get("status") not in ENTRY_STATUSES:
        raise MemorySidecarError(
            "memory_unavailable", f"external intelligence {label}.status is invalid"
        )
    if not isinstance(raw.get("countercondition"), str):
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label}.countercondition must be a string",
        )
    tags = raw.get("tags")
    if not isinstance(tags, list) or any(not isinstance(item, str) for item in tags):
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label}.tags must be an array of strings",
        )
    for key in ("observations", "reuses", "variants"):
        if not isinstance(raw.get(key), list):
            raise MemorySidecarError(
                "memory_unavailable",
                f"external intelligence {label}.{key} must be an array",
            )
    for key in (
        "observation_count",
        "context_count",
        "evidence_count",
        "helpful_reuse_count",
    ):
        _engine_count(raw.get(key), f"{label}.{key}")
    resolution = raw.get("resolution_status")
    if resolution not in {None, "pending_duplicate"}:
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence {label}.resolution_status is invalid",
        )
    return raw


def _validate_search_result(raw: Any, index: int) -> dict[str, Any]:
    item = _engine_exact(raw, THIN_ENTRY_KEYS, f"search.results[{index}]")
    entry_id = item.get("id")
    if not isinstance(entry_id, str) or not ENTRY_ID_RE.fullmatch(entry_id):
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence search.results[{index}].id is invalid",
        )
    for key in ("title", "summary", "rule", "last_seen_at"):
        _engine_text(item.get(key), f"search.results[{index}].{key}")
    if item.get("status") not in ENTRY_STATUSES:
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence search.results[{index}].status is invalid",
        )
    tags = item.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence search.results[{index}].tags is invalid",
        )
    resolution = item.get("resolution_status")
    if resolution not in {None, "pending_duplicate"}:
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence search.results[{index}].resolution_status is invalid",
        )
    for key in (
        "observation_count",
        "context_count",
        "evidence_count",
        "helpful_reuse_count",
    ):
        _engine_count(item.get(key), f"search.results[{index}].{key}")
    score = item.get("score")
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
    ):
        raise MemorySidecarError(
            "memory_unavailable",
            f"external intelligence search.results[{index}].score is invalid",
        )
    return item


def _argument(arguments: list[str], flag: str) -> str:
    try:
        return arguments[arguments.index(flag) + 1]
    except (ValueError, IndexError) as exc:
        raise MemorySidecarError(
            "memory_unavailable", f"external intelligence adapter omitted {flag}"
        ) from exc


def _validate_engine_success(
    arguments: list[str], payload: dict[str, Any]
) -> dict[str, Any]:
    command = arguments[0] if arguments else ""
    if command == "search":
        value = _engine_exact(
            payload, {"status", "state_dir", "query", "results"}, "search"
        )
        if value["status"] != "ok":
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence search status is not ok"
            )
        _engine_text(value["state_dir"], "search.state_dir")
        if value["query"] != _argument(arguments, "--query"):
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence search query drift"
            )
        if not isinstance(value["results"], list):
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence search.results must be an array"
            )
        for index, raw in enumerate(value["results"]):
            _validate_search_result(raw, index)
        return value

    if command == "show":
        value = _engine_exact(payload, {"status", "state_dir", "entry"}, "show")
        if value["status"] != "ok":
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence show status is not ok"
            )
        _engine_text(value["state_dir"], "show.state_dir")
        entry = _validate_entry_common(value["entry"], "show.entry")
        if entry["id"] != _argument(arguments, "--id"):
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence show entry id drift"
            )
        return value

    if command == "reuse":
        value = _engine_exact(
            payload, {"status", "action", "state_dir", "entry"}, "reuse"
        )
        if value["status"] != "ok" or value["action"] not in {
            "reuse_recorded",
            "duplicate_reuse",
        }:
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence reuse status/action drift"
            )
        _engine_text(value["state_dir"], "reuse.state_dir")
        entry = _validate_entry_common(value["entry"], "reuse.entry")
        if entry["id"] != _argument(arguments, "--id"):
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence reuse entry id drift"
            )
        return value

    if command == "capture":
        action = payload.get("action")
        keys = {"status", "action", "state_dir", "entry"}
        if action in {"merged", "duplicate_observation"}:
            keys.add("similarity")
        value = _engine_exact(payload, keys, "capture")
        if value["status"] != "ok" or action not in {
            "created",
            "merged",
            "duplicate_observation",
        }:
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence capture status/action drift"
            )
        _engine_text(value["state_dir"], "capture.state_dir")
        _validate_entry_common(value["entry"], "capture.entry")
        similarity = value.get("similarity")
        if "similarity" in value and (
            isinstance(similarity, bool)
            or not isinstance(similarity, (int, float))
            or not math.isfinite(similarity)
        ):
            raise MemorySidecarError(
                "memory_unavailable", "external intelligence capture.similarity is invalid"
            )
        return value

    raise MemorySidecarError(
        "memory_unavailable", f"unsupported external intelligence engine command: {command}"
    )


def _call_engine(
    arguments: list[str],
    *,
    project_root: Path,
    runtime: str,
    engine_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    if not engine_path.is_file():
        raise MemorySidecarError(
            "memory_unavailable",
            "central skill-governance-adapters external-intelligence engine is not installed",
        )
    command = [
        sys.executable,
        str(engine_path),
        "--scope",
        "project",
        "--project-root",
        str(project_root),
        "--agent",
        RUNTIMES[runtime],
        *arguments,
    ]
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=ENGINE_TIMEOUT_SECONDS,
            check=False,
            env=_engine_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        raise MemorySidecarError("memory_timeout", "external intelligence timed out") from exc
    except OSError as exc:
        raise MemorySidecarError("memory_unavailable", f"external intelligence unavailable: {exc}") from exc
    try:
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise MemorySidecarError("memory_unavailable", "external intelligence emitted invalid JSON") from exc
    if completed.returncode != 0 or not isinstance(payload, dict):
        payload_text = (
            " ".join(str(payload.get(key) or "") for key in ("status", "error"))
            if isinstance(payload, dict)
            else str(payload)
        )
        text = " ".join(
            str(part) for part in (payload_text, completed.stderr)
            if part
        ).lower()
        code = "memory_corrupt" if any(
            marker in text for marker in ("corrupt", "hash", "drift", "materialized", "invalid json")
        ) else "memory_unavailable"
        raise MemorySidecarError(code, text or "external intelligence operation failed")
    return _validate_engine_success(arguments, payload)


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": _truncate_utf8(message, 512)}


def _base_output(operation: str, runtime: str, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "operation": operation,
        "runtime": runtime,
        "status": "continue",
        "warnings": [],
        "policy": {
            "search_limit_max": SEARCH_LIMIT_MAX,
            "score_threshold": SCORE_THRESHOLD,
            "summary_max_bytes": SUMMARY_MAX_BYTES,
            "search_results_max_bytes": SEARCH_RESULTS_MAX_BYTES,
            "detail_max_bytes": DETAIL_MAX_BYTES,
            "details_total_max_bytes": DETAILS_TOTAL_MAX_BYTES,
        },
        "memory": {
            "scope": "project",
            "user_scope_used": False,
            "status": state["memory_status"],
            "engine": "central:skill-governance-adapters/build-external-intelligence.py",
        },
        "token_telemetry": {
            "status": "unavailable",
            "estimated": False,
            "input_tokens": None,
            "reused_input_tokens": None,
        },
        "state": state,
        "candidates": [],
        "details": [],
        "reuses": [],
        "capture": None,
    }


def _candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "status": raw.get("status"),
        "title": _truncate_utf8(raw.get("title"), 256),
        "summary": _truncate_utf8(raw.get("summary"), SUMMARY_MAX_BYTES),
        "score": raw.get("score"),
        "resolution_status": raw.get("resolution_status"),
        "observation_count": raw.get("observation_count", 0),
        "context_count": raw.get("context_count", 0),
        "evidence_count": raw.get("evidence_count", 0),
        "helpful_reuse_count": raw.get("helpful_reuse_count", 0),
    }


def _detail(raw: dict[str, Any]) -> dict[str, Any]:
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    detail = {
        "id": raw.get("id"),
        "status": raw.get("status"),
        "title": _truncate_utf8(raw.get("title"), 256),
        "summary": _truncate_utf8(raw.get("summary"), 512),
        "rule": _truncate_utf8(raw.get("rule"), 2_048),
        "countercondition": _truncate_utf8(raw.get("countercondition"), 512),
        "tags": [_truncate_utf8(tag, 64) for tag in tags[:10]],
        "resolution_status": raw.get("resolution_status"),
        "observation_count": raw.get("observation_count", 0),
        "context_count": raw.get("context_count", 0),
        "evidence_count": raw.get("evidence_count", 0),
        "helpful_reuse_count": raw.get("helpful_reuse_count", 0),
    }
    if _json_bytes(detail) > DETAIL_MAX_BYTES:
        detail["rule"] = _truncate_utf8(detail["rule"], 1_024)
        detail["summary"] = _truncate_utf8(detail["summary"], 256)
        detail["countercondition"] = _truncate_utf8(detail["countercondition"], 256)
    return detail


def _state_for_search(request: dict[str, Any], project_root: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "run_id": request["run_id"],
        "project_root": str(project_root),
        "query": request["query"],
        "candidate_ids": [],
        "selected_ids": [],
        "phase": "searched",
        "memory_status": "available",
    }


def execute_request(
    raw_request: dict[str, Any],
    *,
    engine_path: Path = ENGINE_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    request, root = _validate_request(raw_request)
    operation = request["operation"]
    state = (
        _state_for_search(request, root)
        if operation == "search"
        else json.loads(json.dumps(request["state"]))
    )
    output = _base_output(operation, request["runtime"], state)
    try:
        root.relative_to(PLUGIN_ROOT)
        package_target = True
    except ValueError:
        package_target = False
    if package_target:
        output["warnings"].append(
            _warning("memory_unavailable", "project root is inside the installed plugin package")
        )
        state["memory_status"] = "unavailable"
        output["memory"]["status"] = "unavailable"
        return output

    if operation == "search":
        try:
            payload = _call_engine(
                ["search", "--query", request["query"], "--limit", str(request["limit"])],
                project_root=root,
                runtime=request["runtime"],
                engine_path=engine_path,
                runner=runner,
            )
            memory_state_ref = payload.get("state_dir")
            if not isinstance(memory_state_ref, str) or not memory_state_ref or not Path(memory_state_ref).exists():
                output["warnings"].append(
                    _warning("memory_absent", "project external-intelligence state does not exist yet")
                )
                state["memory_status"] = "unavailable"
                output["memory"]["status"] = "unavailable"
                return output
            candidates: list[dict[str, Any]] = []
            for raw in payload.get("results", []):
                if not isinstance(raw, dict) or not isinstance(raw.get("score"), (int, float)):
                    continue
                if raw["score"] < SCORE_THRESHOLD:
                    continue
                item = _candidate(raw)
                proposed = [*candidates, item]
                if _json_bytes(proposed) > SEARCH_RESULTS_MAX_BYTES:
                    break
                candidates.append(item)
                if len(candidates) >= request["limit"]:
                    break
            output["candidates"] = candidates
            state["candidate_ids"] = [item["id"] for item in candidates]
        except MemorySidecarError as exc:
            output["warnings"].append(_warning(exc.code, str(exc)))
            state["memory_status"] = "unavailable"
            output["memory"]["status"] = "unavailable"
        return output

    if operation == "adopt":
        successful_ids: list[str] = []
        total_detail_bytes = 2
        for selection in request["selection"]:
            entry_id = selection["id"]
            try:
                shown = _call_engine(
                    ["show", "--id", entry_id],
                    project_root=root,
                    runtime=request["runtime"],
                    engine_path=engine_path,
                    runner=runner,
                )
                detail = _detail(shown.get("entry", {}))
                detail_bytes = _json_bytes(detail) + (1 if output["details"] else 0)
                if total_detail_bytes + detail_bytes > DETAILS_TOTAL_MAX_BYTES:
                    output["warnings"].append(
                        _warning("detail_budget_exhausted", "selected detail byte budget exhausted")
                    )
                    continue
                output["details"].append(detail)
                total_detail_bytes += detail_bytes
                reused = _call_engine(
                    [
                        "reuse", "--id", entry_id,
                        "--context-id", request["context_id"],
                        "--evidence-ref", request["evidence_ref"],
                        "--evidence-source", request["evidence_source"],
                        "--outcome", selection["outcome"],
                    ],
                    project_root=root,
                    runtime=request["runtime"],
                    engine_path=engine_path,
                    runner=runner,
                )
                output["reuses"].append(
                    {
                        "id": entry_id,
                        "outcome": selection["outcome"],
                        "recorded": reused.get("action") in {"reuse_recorded", "duplicate_reuse"},
                    }
                )
                successful_ids.append(entry_id)
            except MemorySidecarError as exc:
                output["warnings"].append(_warning(exc.code, str(exc)))
                state["memory_status"] = "unavailable"
                output["memory"]["status"] = "unavailable"
        state["selected_ids"] = successful_ids
        state["phase"] = "adopted"
        return output

    capture = request["capture"]
    if capture is not None:
        arguments = [
            "capture",
            "--title", capture["title"],
            "--summary", capture["summary"],
            "--rule", capture["rule"],
            "--context-id", request["context_id"],
            "--evidence-ref", capture["evidence_ref"],
            "--evidence-source", capture["evidence_source"],
            "--tags", ",".join(capture["tags"]),
            "--countercondition", capture["countercondition"],
            "--ambiguous-action", "quarantine",
        ]
        try:
            captured = _call_engine(
                arguments,
                project_root=root,
                runtime=request["runtime"],
                engine_path=engine_path,
                runner=runner,
            )
            entry = captured.get("entry") if isinstance(captured.get("entry"), dict) else {}
            output["capture"] = {
                "action": captured.get("action"),
                "id": entry.get("id"),
                "resolution_status": entry.get("resolution_status"),
            }
        except MemorySidecarError as exc:
            output["warnings"].append(_warning(exc.code, str(exc)))
            state["memory_status"] = "unavailable"
            output["memory"]["status"] = "unavailable"
    state["phase"] = "finished"
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    request_group = parser.add_mutually_exclusive_group(required=True)
    request_group.add_argument("--request", type=Path, help="path to request JSON")
    request_group.add_argument("--request-json", help="inline request JSON")
    args = parser.parse_args(argv)
    try:
        request_text = (
            args.request.read_text(encoding="utf-8")
            if args.request is not None
            else args.request_json
        )
        request = json.loads(request_text)
        output = execute_request(request)
    except (OSError, json.JSONDecodeError, RequestError) as exc:
        output = {
            "schema_version": SCHEMA_VERSION,
            "contract_id": CONTRACT_ID,
            "status": "invalid_request",
            "error": str(exc),
        }
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
