"""Validate scenario-bound live-trial budgets and transcript token accounting.

The budget is part of the scenario contract, not an operator-tunable hint.  A
caller may choose a stricter poll limit, but cannot raise the scenario limit.
Token accounting de-duplicates the repeated transcript records emitted for one
assistant message and includes main-session and subagent JSONL files.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


def resource_budget(scenario: dict[str, Any]) -> dict[str, int]:
    """Return the required, closed resource budget for one scenario."""
    raw = scenario.get("resource_budget")
    if not isinstance(raw, dict):
        raise ValueError("scenario resource_budget must be an object")
    expected = {"max_wall_clock_s", "max_total_tokens"}
    if set(raw) != expected:
        raise ValueError(
            "scenario resource_budget must contain exactly "
            "max_wall_clock_s and max_total_tokens"
        )
    budget: dict[str, int] = {}
    for key in sorted(expected):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"scenario resource_budget.{key} must be a positive integer")
        budget[key] = value
    return budget


def transcript_paths(main: Path) -> list[Path]:
    """List the main transcript plus Claude subagent transcripts deterministically."""
    paths = [main]
    subagents = main.with_suffix("") / "subagents"
    if subagents.is_dir():
        paths.extend(sorted(subagents.glob("*.jsonl")))
    return [path for path in paths if path.is_file()]


def transcript_token_usage(main: Path | None) -> dict[str, Any]:
    """Sum unique assistant-message usage records from transcript JSONL files."""
    totals = {key: 0 for key in USAGE_FIELDS}
    # Claude assistant message id は session/subagent transcript を横断して一意。path を
    # identity に含めると同一 record の main/subagent 複写を二重計上するため id だけで束縛する。
    seen: set[str] = set()
    assistant_identities: set[str] = set()
    invalid_usage_identities: set[str] = set()
    idless_assistant_records = 0
    paths = transcript_paths(main) if main is not None else []
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "assistant":
                continue
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            message_id = message.get("id")
            usage = message.get("usage")
            if not isinstance(message_id, str) or not message_id:
                idless_assistant_records += 1
                continue
            identity = message_id
            assistant_identities.add(identity)
            if identity in seen:
                continue
            if not isinstance(usage, dict):
                invalid_usage_identities.add(identity)
                continue
            required = ("input_tokens", "output_tokens")
            if any(
                isinstance(usage.get(key), bool)
                or not isinstance(usage.get(key), int)
                or usage[key] < 0
                for key in required
            ):
                invalid_usage_identities.add(identity)
                continue
            if any(
                key in usage
                and (
                    isinstance(usage[key], bool)
                    or not isinstance(usage[key], int)
                    or usage[key] < 0
                )
                for key in USAGE_FIELDS
            ):
                invalid_usage_identities.add(identity)
                continue
            seen.add(identity)
            invalid_usage_identities.discard(identity)
            for key in USAGE_FIELDS:
                value = usage.get(key, 0)
                totals[key] += value
    missing_usage = assistant_identities - seen
    return {
        **totals,
        "total_tokens": sum(totals.values()),
        "assistant_messages": len(seen),
        "assistant_message_ids": len(assistant_identities),
        "invalid_or_missing_usage_messages": len(missing_usage),
        "idless_assistant_records": idless_assistant_records,
        "transcript_files": len(paths),
        "measured": (
            bool(paths) and bool(seen) and not missing_usage
            and idless_assistant_records == 0
        ),
    }


def poll_wall_usage(workdir: Path, state_path: Path | None) -> dict[str, Any]:
    """Derive wall time from a contained, persisted poll state; never caller claims."""
    if state_path is None:
        raise ValueError("scenario verdict requires --poll-state")
    try:
        resolved = state_path.resolve(strict=True)
        resolved.relative_to(workdir.resolve())
        raw_bytes = resolved.read_bytes()
        state = json.loads(raw_bytes)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"poll state unreadable or outside workdir: {exc}") from exc
    if not isinstance(state, dict):
        raise ValueError("poll state must be a JSON object")
    elapsed = state.get("elapsed")
    started = state.get("started_at_unix")
    observed = state.get("observed_at_unix")
    if isinstance(elapsed, bool) or not isinstance(elapsed, int) or elapsed < 0:
        raise ValueError("poll state.elapsed must be a non-negative integer")
    for key, value in (("started_at_unix", started), ("observed_at_unix", observed)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"poll state.{key} must be positive")
    if observed < started:
        raise ValueError("poll state observed_at_unix precedes started_at_unix")
    measured = max(float(elapsed), float(observed) - float(started))
    return {
        "wall_clock_s": measured,
        "poll_state_ref": str(resolved.relative_to(workdir.resolve())),
        "poll_state_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }


def budget_violations(
    budget: dict[str, int], *, wall_clock_s: float | None, token_usage: dict[str, Any]
) -> list[str]:
    """Return fail-closed resource-budget violations."""
    violations: list[str] = []
    if wall_clock_s is None:
        violations.append("wall-clock-unmeasured")
    elif wall_clock_s > budget["max_wall_clock_s"]:
        violations.append(
            f"wall-clock-exceeded:{wall_clock_s:g}>{budget['max_wall_clock_s']}"
        )
    if not token_usage.get("measured"):
        violations.append("tokens-unmeasured")
    elif token_usage.get("total_tokens", 0) > budget["max_total_tokens"]:
        violations.append(
            "token-budget-exceeded:"
            f"{token_usage['total_tokens']}>{budget['max_total_tokens']}"
        )
    return violations
