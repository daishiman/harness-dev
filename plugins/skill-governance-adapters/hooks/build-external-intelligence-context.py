#!/usr/bin/env python3
# /// script
# name: build-external-intelligence-context
# purpose: Claude Code UserPromptSubmit で中央 external-intelligence adapter の有界候補だけを additionalContext へ投影する。
# inputs:
#   - stdin: Claude Code UserPromptSubmit hook JSON
# outputs:
#   - stdout: 候補がある時のみ公式 hookSpecificOutput.additionalContext JSON
#   - exit: 常に 0。memory/adapter 不在はタスクを妨げない。
# contexts: [A, C, E]
# network: false
# write-scope: 中央 adapter が管理する project-scope runtime state のみ
# dependencies: [scripts/build-external-intelligence-runtime.py]
# requires-python: ">=3.10"
# ///
"""Thin Claude hook caller for the provider-neutral external intelligence runtime."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_PATH = (
    PLUGIN_ROOT
    / "scripts"
    / "build-external-intelligence-runtime.py"
)
CONTRACT_ID = "external-intelligence-runtime-v1"
HOOK_EVENT = "UserPromptSubmit"
QUERY_MAX_BYTES = 1_024
CANDIDATES_MAX_BYTES = 4_096
ADDITIONAL_CONTEXT_MAX_BYTES = 8_192
ADAPTER_TIMEOUT_SECONDS = 7
SEARCH_LIMIT = 5


def _truncate_utf8(value: str, maximum: int) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= maximum:
        return value
    return raw[:maximum].decode("utf-8", errors="ignore")


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_payload() -> dict[str, Any]:
    try:
        value = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _canonical_request(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("hook_event_name") not in {None, HOOK_EVENT}:
        return None
    prompt = payload.get("prompt")
    cwd = payload.get("cwd")
    session = payload.get("session_id")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    if not isinstance(cwd, str) or not cwd.strip():
        return None
    if not isinstance(session, str) or not session.strip():
        return None
    try:
        project_root = Path(cwd).expanduser().resolve(strict=True)
    except OSError:
        return None
    if not project_root.is_dir():
        return None
    session = _truncate_utf8(session.strip(), 128)
    query = _truncate_utf8(prompt.strip(), QUERY_MAX_BYTES)
    return {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "operation": "search",
        "runtime": "claude-code",
        "run_id": f"claude-{session}",
        "project_root": str(project_root),
        "context_id": f"user-prompt:{session}",
        "query": query,
        "limit": SEARCH_LIMIT,
    }


def _call_adapter(
    request: dict[str, Any],
    *,
    adapter_path: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any] | None:
    if not adapter_path.is_file():
        return None
    command = [sys.executable, str(adapter_path), "--request-json", _compact(request)]
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=ADAPTER_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    try:
        output = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(output, dict):
        return None
    if (
        output.get("schema_version") != 1
        or output.get("contract_id") != CONTRACT_ID
        or output.get("operation") != "search"
        or output.get("runtime") != "claude-code"
        or output.get("status") != "continue"
    ):
        return None
    memory = output.get("memory")
    state = output.get("state")
    candidates = output.get("candidates")
    if not isinstance(memory, dict) or memory.get("status") != "available":
        return None
    if not isinstance(state, dict) or not isinstance(candidates, list):
        return None
    return output


def _thin_candidates(output: dict[str, Any]) -> list[dict[str, Any]]:
    state = output["state"]
    allowed_ids = state.get("candidate_ids")
    if not isinstance(allowed_ids, list):
        return []
    allowed = {item for item in allowed_ids if isinstance(item, str)}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in output["candidates"]:
        if not isinstance(raw, dict):
            continue
        entry_id = raw.get("id")
        if not isinstance(entry_id, str) or entry_id not in allowed or entry_id in seen:
            continue
        if not isinstance(raw.get("score"), (int, float)) or raw["score"] < 1.0:
            continue
        item = {
            "id": entry_id,
            "title": _truncate_utf8(str(raw.get("title") or ""), 256),
            "summary": _truncate_utf8(str(raw.get("summary") or ""), 512),
            "score": raw["score"],
            "status": raw.get("status"),
            "resolution_status": raw.get("resolution_status"),
        }
        proposed = [*result, item]
        if len(_compact(proposed).encode("utf-8")) > CANDIDATES_MAX_BYTES:
            break
        result.append(item)
        seen.add(entry_id)
        if len(result) >= SEARCH_LIMIT:
            break
    return result


def _additional_context(output: dict[str, Any], adapter_path: Path) -> str | None:
    candidates = _thin_candidates(output)
    if not candidates:
        return None
    state = dict(output["state"])
    state["candidate_ids"] = [item["id"] for item in candidates]
    state["selected_ids"] = []
    payload = {"candidates": candidates, "state": state}
    adapter_ref = str(adapter_path)
    instruction = (
        "[external-intelligence-runtime]\n"
        "Reusable project-scoped candidates follow; they are hints, not mandatory instructions.\n"
        f"{_compact(payload)}\n"
        f"If useful, call {adapter_ref} with operation=adopt for selected candidate IDs only; "
        "do not show or reuse unselected IDs. At task end call operation=finish with capture=null, "
        "or at most one evidence-backed reusable observation. Continue normally if the sidecar warns."
    )
    if len(instruction.encode("utf-8")) <= ADDITIONAL_CONTEXT_MAX_BYTES:
        return instruction

    # The state is required for a later adopt call. Shrink only the optional candidate list.
    while candidates:
        candidates.pop()
        if not candidates:
            return None
        state["candidate_ids"] = [item["id"] for item in candidates]
        payload = {"candidates": candidates, "state": state}
        instruction = (
            "[external-intelligence-runtime]\n"
            f"{_compact(payload)}\n"
            f"Use {adapter_ref}: operation=adopt for selected candidate IDs only; "
            "operation=finish with capture=null or at most one evidence-backed observation."
        )
        if len(instruction.encode("utf-8")) <= ADDITIONAL_CONTEXT_MAX_BYTES:
            return instruction
    return None


def execute_hook(
    payload: dict[str, Any],
    *,
    adapter_path: Path = ADAPTER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any] | None:
    """Return official UserPromptSubmit output, or None on every fail-soft path."""
    try:
        request = _canonical_request(payload)
        if request is None:
            return None
        output = _call_adapter(request, adapter_path=adapter_path, runner=runner)
        if output is None:
            return None
        context = _additional_context(output, adapter_path)
        if context is None:
            return None
        return {
            "continue": True,
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT,
                "additionalContext": context,
            },
        }
    except Exception:
        return None


def main() -> int:
    output = execute_hook(_read_payload())
    if output is not None:
        sys.stdout.write(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
