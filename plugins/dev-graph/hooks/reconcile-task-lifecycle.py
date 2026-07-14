#!/usr/bin/env python3
# /// script
# name: reconcile-task-lifecycle
# purpose: SessionStart/PostToolUse/TaskCompleted を lifecycle reconcile と worktree lease 操作へ安全に配線する薄い adapter。
# inputs: [stdin Claude hook JSON, argv --event --repo-root]
# outputs: [stdout JSON receipt, exit 0 noop/success, exit 2 identity-owner violation]
# contexts: [E]
# network: true
# write-scope: validated lifecycle projection and git-common-dir hook scheduling ledger only
# dependencies: [scripts/resolve-repo-context.py, scripts/reconcile-github-lifecycle.py, scripts/manage-worktree-lease.py, scripts/bd-bridge.py]
# requires-python: ">=3.11"
# ///
"""C25 lifecycle hook. TaskCompleted never marks a task done."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

DG_ID = re.compile(r"\[DG:([A-Za-z0-9._:-]+)\]")
RECONCILE_COMMAND = re.compile(r"^\s*(?:git\s+(?:pull|merge|push)\b|gh\s+pr\s+merge\b)", re.I)
MAX_COMMAND_LENGTH = 32_768
MAX_ID_LENGTH = 512
SCHEDULE_STATE = "lifecycle-schedule.json"
HOOK_EVENTS = "hook-events.json"


def read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def invoke(script: Path, *args: str) -> dict[str, Any]:
    if not script.is_file():
        return {"ok": False, "error": f"missing dependency: {script}"}
    proc = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, check=False)
    result: dict[str, Any] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    text = proc.stdout.strip()
    if text:
        try:
            result["result"] = json.loads(text)
        except json.JSONDecodeError:
            result["stdout"] = text
    if proc.stderr.strip():
        result["stderr"] = proc.stderr.strip()
    return result


def spawn(script: Path, *args: str) -> dict[str, Any]:
    """Detach C26 from the hook process; never inherit hook JSON or output pipes."""
    if not script.is_file():
        return {"ok": False, "spawned": False, "error": f"missing dependency: {script}"}
    try:
        proc = subprocess.Popen(
            [sys.executable, str(script), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError as exc:
        return {"ok": False, "spawned": False, "error": f"background spawn failed: {exc}"}
    return {"ok": True, "spawned": True, "pid": proc.pid}


def _value(payload: dict[str, Any], *names: str) -> str | None:
    lifecycle = payload.get("dev_graph") if isinstance(payload.get("dev_graph"), dict) else {}
    for name in names:
        value = payload.get(name)
        if value in (None, ""):
            value = lifecycle.get(name)
        if value not in (None, ""):
            return str(value)
    return None


def reconcile_args(args: argparse.Namespace, payload: dict[str, Any], root: Path, *, mode: str) -> tuple[list[str], list[str]]:
    graph = args.graph or _value(payload, "graph", "graph_path")
    node_id = args.graph_node_id or _value(payload, "graph_node_id")
    repo = args.github_repo or _value(payload, "github_repo", "repo")
    pr = str(args.pr) if args.pr else _value(payload, "pr", "pr_number")
    argv = ["--repo-root", str(root), "--mode", mode]
    missing: list[str] = []
    for flag, value, label in (("--graph", graph, "graph"), ("--graph-node-id", node_id, "graph_node_id"), ("--repo", repo, "repo"), ("--pr", pr, "pr")):
        if value:
            argv += [flag, value]
        elif mode != "drain-pending":
            missing.append(label)
    return argv, missing


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def coordination_context(context: dict[str, Any]) -> dict[str, str]:
    value = context.get("result")
    if not isinstance(value, dict):
        raise ValueError("resolver returned no context object")
    coordination = value.get("coordination_paths")
    required = ("repository_id", "head_sha")
    if not isinstance(coordination, dict) or not coordination.get("root") or any(not value.get(key) for key in required):
        raise ValueError("resolver context omits coordination identity")
    return {
        "root": str(Path(str(coordination["root"])).resolve()),
        "repository_id": str(value["repository_id"]),
        "head_sha": str(value["head_sha"]),
        "config": str(((value.get("local_state_paths") or {}).get("config") or "")),
    }


def schedule_policy(config_path: Path) -> dict[str, Any]:
    """Return the single configured scheduler owner, validating its runtime bounds."""
    if not config_path.is_file():
        return {"enabled": False, "owner": None, "reason": "config_missing"}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid repo config: {exc}") from exc
    policy = ((config.get("github") or {}).get("completion_policy") or {}) if isinstance(config, dict) else {}
    scheduled = policy.get("scheduled_reconciliation") if isinstance(policy, dict) else None
    if not isinstance(scheduled, dict):
        return {"enabled": False, "owner": None, "reason": "schedule_missing"}
    enabled = scheduled.get("enabled") is True
    owner = scheduled.get("owner")
    interval = scheduled.get("interval_minutes")
    entry_point = scheduled.get("entry_point")
    if owner not in ("claude_session_start", "host_scheduler"):
        raise ValueError("scheduled reconciliation owner is invalid")
    if not isinstance(interval, int) or isinstance(interval, bool) or not 5 <= interval <= 10_080:
        raise ValueError("scheduled reconciliation interval_minutes is invalid")
    if entry_point != "dev-graph sync --reconcile-lifecycle":
        raise ValueError("scheduled reconciliation entry_point is invalid")
    return {"enabled": enabled, "owner": owner, "interval_minutes": interval, "entry_point": entry_point}


def schedule_due(state_path: Path, interval_minutes: int, *, now: datetime | None = None) -> tuple[bool, dict[str, Any]]:
    state = _read_object(state_path)
    current = now or _utc_now()
    last = _parse_time(state.get("last_reconciled_at"))
    return last is None or current >= last + timedelta(minutes=interval_minutes), state


def claim_schedule_due(state_path: Path, interval_minutes: int, *, now: datetime | None = None) -> tuple[bool, dict[str, Any]]:
    """Reserve one due run under the scheduler lock so concurrent sessions cannot double-start it."""
    current = now or _utc_now()
    lock_path = state_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        due, state = schedule_due(state_path, interval_minutes, now=current)
        inflight = _parse_time(state.get("inflight_since"))
        if inflight is not None and current < inflight + timedelta(minutes=max(10, interval_minutes * 2)):
            return False, state
        if due:
            state.update({"schema_version": "1.0", "owner": "claude_session_start", "inflight_since": _iso(current)})
            _atomic_json(state_path, state)
        return due, state


def update_schedule_state(state_path: Path, *, owner: str, result: dict[str, Any], now: datetime | None = None) -> None:
    current = now or _utc_now()
    lock_path = state_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = _read_object(state_path)
        state.update({"schema_version": "1.0", "owner": owner, "last_attempted_at": _iso(current), "last_result_ok": bool(result.get("ok"))})
        state.pop("inflight_since", None)
        if result.get("ok"):
            state["last_reconciled_at"] = _iso(current)
        _atomic_json(state_path, state)


def validate_event_identity(event: str, payload: dict[str, Any], root: Path) -> tuple[bool, str]:
    expected = {"session-start": "SessionStart", "post-tool-use": "PostToolUse", "task-completed": "TaskCompleted"}[event]
    observed = payload.get("hook_event_name")
    if observed not in (None, "", expected):
        return False, f"hook event mismatch: expected {expected}"
    cwd = payload.get("cwd")
    if cwd not in (None, ""):
        try:
            Path(str(cwd)).resolve(strict=True).relative_to(root.resolve(strict=True))
        except (OSError, ValueError):
            return False, "hook cwd is outside caller repository"
    for key in ("session_id", "sessionId", "tool_use_id", "task_id"):
        value = payload.get(key)
        if value is not None and len(str(value)) > MAX_ID_LENGTH:
            return False, f"hook {key} exceeds length limit"
    return True, "validated"


def observed_bash(payload: dict[str, Any]) -> tuple[bool, str, dict[str, str]]:
    """Validate a successful official PostToolUse(Bash) observation without echoing input."""
    if payload.get("tool_name") != "Bash":
        return False, "tool is not Bash", {}
    session_id = _value(payload, "session_id", "sessionId")
    tool_use_id = _value(payload, "tool_use_id", "toolUseId")
    if not session_id or not tool_use_id:
        return False, "tool observation has no stable session/tool identity", {}
    tool_input = payload.get("tool_input")
    command = str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""
    if not command or len(command) > MAX_COMMAND_LENGTH or "\x00" in command:
        return False, "tool command is empty or exceeds validation bounds", {}
    outcome = payload.get("tool_response") or payload.get("tool_result")
    if not isinstance(outcome, dict):
        return False, "tool response is missing", {}
    exit_code = outcome.get("exit_code", 0)
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return False, "tool response exit_code is invalid", {}
    if outcome.get("is_error") is True or exit_code != 0:
        return False, "tool operation did not succeed", {}
    if not RECONCILE_COMMAND.search(command):
        return False, "successful Bash operation is outside the reconcile allowlist", {}
    return True, "validated", {"session_id": session_id, "tool_use_id": tool_use_id}


def dispatch_once(
    ledger_path: Path,
    event_key: str,
    script: Path,
    argv: list[str],
    *,
    spawn_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Atomically reserve an event key and spawn exactly one detached C26 process."""
    lock_path = ledger_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        ledger = _read_object(ledger_path) or {"schema_version": "1.0", "events": []}
        events = ledger.get("events")
        if not isinstance(events, list):
            events = []
            ledger["events"] = events
        if any(isinstance(row, dict) and row.get("event_key") == event_key and row.get("status") == "spawned" for row in events):
            return {"ok": True, "spawned": False, "deduplicated": True, "event_key": event_key}
        result = (spawn_fn or spawn)(script, *argv)
        receipt = {
            "event_key": event_key,
            "status": "spawned" if result.get("ok") else "spawn_failed",
            "recorded_at": _iso(_utc_now()),
        }
        if result.get("pid") is not None:
            receipt["pid"] = result["pid"]
        events[:] = [row for row in events if not (isinstance(row, dict) and row.get("event_key") == event_key)]
        events.append(receipt)
        ledger["events"] = events[-1000:]
        _atomic_json(ledger_path, ledger)
        return {**result, "deduplicated": False, "event_key": event_key}


def _identity_owner_failure(result: dict[str, Any]) -> bool:
    text = " ".join(str(result.get(key) or "") for key in ("error", "stderr", "stdout")).lower()
    nested = result.get("result")
    if isinstance(nested, dict):
        text += " " + " ".join(str(nested.get(key) or "") for key in ("error", "conflicts", "diagnostics")).lower()
    return any(token in text for token in ("owner", "identity", "session mismatch", "worktree mismatch", "repository mismatch"))


def _child_summary(result: dict[str, Any], *allowed: str) -> dict[str, Any]:
    """Keep hook stdout free of child stdout, remote bodies, command text and credentials."""
    summary: dict[str, Any] = {"ok": bool(result.get("ok"))}
    if result.get("exit_code") is not None:
        summary["exit_code"] = result["exit_code"]
    nested = result.get("result")
    if isinstance(nested, dict):
        for key in allowed:
            if key in nested:
                summary[key] = nested[key]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", choices=("session-start", "post-tool-use", "task-completed"), required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--graph")
    parser.add_argument("--graph-node-id")
    parser.add_argument("--github-repo")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--tracker-binding", choices=("beads", "github", "none"), default="beads")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    payload = read_payload()
    receipt: dict[str, Any] = {"event": args.event, "repo_root": str(root), "actions": []}

    context = invoke(scripts / "resolve-repo-context.py", "--repo-root", str(root), "--mode", "read")
    receipt["actions"].append({"context": _child_summary(context, "repository_id", "worktree_id", "branch", "head_sha", "default_branch", "diagnostics")})
    if not context.get("ok"):
        print(json.dumps(receipt, ensure_ascii=False))
        return 2
    try:
        coordination = coordination_context(context)
    except ValueError as exc:
        receipt["actions"].append({"error": str(exc)})
        print(json.dumps(receipt, ensure_ascii=False))
        return 2
    identity_ok, identity_reason = validate_event_identity(args.event, payload, root)
    if not identity_ok:
        receipt["actions"].append({"error": identity_reason})
        print(json.dumps(receipt, ensure_ascii=False))
        return 2

    coord_root = Path(coordination["root"])
    if args.event == "session-start":
        worktree_context = invoke(scripts / "manage-worktree-lease.py", "--repo-root", str(root), "--op", "context")
        receipt["actions"].append({"worktree_context": _child_summary(worktree_context, "repository_id", "worktree_id", "branch", "head_sha")})
        if not worktree_context.get("ok") and _identity_owner_failure(worktree_context):
            print(json.dumps(receipt, ensure_ascii=False))
            return 2
        try:
            policy = schedule_policy(Path(coordination["config"]))
        except ValueError as exc:
            receipt["actions"].append({"scheduler_error": str(exc)})
            print(json.dumps(receipt, ensure_ascii=False))
            return 2 if "owner" in str(exc) else 0
        state_path = coord_root / SCHEDULE_STATE
        due = False
        if policy.get("enabled") and policy.get("owner") == "claude_session_start":
            due, state = claim_schedule_due(state_path, int(policy["interval_minutes"]))
            if due:
                candidate_argv, missing = reconcile_args(args, payload, root, mode="reconcile")
                reconcile_argv = candidate_argv if not missing else reconcile_args(args, payload, root, mode="drain-pending")[0]
                reconciliation = invoke(scripts / "reconcile-github-lifecycle.py", *reconcile_argv)
                update_schedule_state(state_path, owner="claude_session_start", result=reconciliation)
                receipt["actions"].append({"scheduled_reconcile": _child_summary(reconciliation, "policy_decision"), "mode": "reconcile" if not missing else "drain-pending"})
            else:
                receipt["actions"].append({"scheduler": "not_due", "last_reconciled_at": state.get("last_reconciled_at")})
        elif policy.get("enabled"):
            receipt["actions"].append({"scheduler": "owned_by_host_scheduler"})
        else:
            receipt["actions"].append({"scheduler": policy.get("reason", "disabled")})
        if args.tracker_binding == "beads":
            beads_parity = invoke(scripts / "bd-bridge.py", "--op", "ready", "--repo-root", str(root))
            receipt["actions"].append({"beads_parity": _child_summary(beads_parity, "workspace_identity")})
            if not beads_parity.get("ok") and _identity_owner_failure(beads_parity):
                print(json.dumps(receipt, ensure_ascii=False))
                return 2
    elif args.event == "post-tool-use":
        observed, reason, identifiers = observed_bash(payload)
        if observed:
            reconcile_argv, missing = reconcile_args(args, payload, root, mode="reconcile")
            if missing:
                receipt["actions"].append({"noop": f"reconcile context missing: {', '.join(missing)}"})
            else:
                event_key = ":".join((coordination["repository_id"], "PostToolUse", identifiers["session_id"], identifiers["tool_use_id"], coordination["head_sha"]))
                dispatch = dispatch_once(coord_root / HOOK_EVENTS, event_key, scripts / "reconcile-github-lifecycle.py", reconcile_argv)
                receipt["actions"].append({"async_reconcile": dispatch})
        else:
            receipt["actions"].append({"noop": reason})
    else:
        subject = " ".join(str(payload.get(key) or "") for key in ("task_subject", "task_description", "prompt"))
        if len(subject) > MAX_COMMAND_LENGTH:
            receipt["actions"].append({"noop": "TaskCompleted subject exceeds validation bounds"})
        else:
            match = DG_ID.search(subject)
            if not match:
                receipt["actions"].append({"noop": "TaskCompleted has no [DG:<id>] marker"})
            else:
                session_id = str(payload.get("session_id") or payload.get("sessionId") or "")
                if not session_id:
                    receipt["actions"].append({"error": "missing session identity"})
                    print(json.dumps(receipt, ensure_ascii=False))
                    return 2
                park = invoke(
                    scripts / "manage-worktree-lease.py", "--repo-root", str(root), "--op", "park",
                    "--graph-node-id", match.group(1), "--session-id", session_id,
                )
                receipt["actions"].append({"park": _child_summary(park, "graph_node_id", "state", "worktree_id")})
                receipt["actions"].append({"note": "pending_review only; GitHub/local done is C26 evidence-gated"})
                if not park.get("ok") and _identity_owner_failure(park):
                    print(json.dumps(receipt, ensure_ascii=False))
                    return 2
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
