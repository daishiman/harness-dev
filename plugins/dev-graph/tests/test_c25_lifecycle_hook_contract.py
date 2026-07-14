from __future__ import annotations

import importlib.util
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "reconcile-task-lifecycle.py"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HOOK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, root: Path, event: str, payload: dict, *argv: str):
    monkeypatch.setattr(sys, "argv", [str(HOOK), "--event", event, "--repo-root", str(root), *argv])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = module.main()
    return code, json.loads(capsys.readouterr().out)


def context_result(root: Path, config: Path) -> dict:
    return {
        "ok": True,
        "exit_code": 0,
        "result": {
            "repository_id": "repo_1",
            "head_sha": "HEAD1",
            "coordination_paths": {"root": str(root / ".git" / "dev-graph")},
            "local_state_paths": {"config": str(config)},
        },
    }


def write_config(path: Path, *, owner: str = "claude_session_start", enabled: bool = True, interval: int = 5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "github": {"completion_policy": {"scheduled_reconciliation": {
            "enabled": enabled,
            "interval_minutes": interval,
            "owner": owner,
            "entry_point": "dev-graph sync --reconcile-lifecycle",
        }}},
    }))


def official(event: str, root: Path, **extra) -> dict:
    value = {"hook_event_name": event, "cwd": str(root), "session_id": "session-1"}
    value.update(extra)
    return value


def test_session_start_owns_interval_and_persists_last_success(tmp_path, monkeypatch, capsys):
    module = load("c25_schedule")
    config = tmp_path / ".dev-graph" / "config.json"
    write_config(config)
    fixed = datetime(2026, 7, 13, 1, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(module, "_utc_now", lambda: fixed)
    calls = []

    def fake_invoke(path, *args):
        calls.append((path.name, args))
        if path.name == "resolve-repo-context.py":
            return context_result(tmp_path, config)
        return {"ok": True, "exit_code": 0, "result": {}}

    monkeypatch.setattr(module, "invoke", fake_invoke)
    payload = official("SessionStart", tmp_path)
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "session-start", payload, "--tracker-binding", "none")
    assert code == 0 and receipt["actions"][-1]["mode"] == "drain-pending"
    state_path = tmp_path / ".git" / "dev-graph" / module.SCHEDULE_STATE
    state = json.loads(state_path.read_text())
    assert state["owner"] == "claude_session_start"
    assert state["last_reconciled_at"] == "2026-07-13T01:00:00Z"
    assert sum(name == "reconcile-github-lifecycle.py" for name, _ in calls) == 1

    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "session-start", payload, "--tracker-binding", "none")
    assert code == 0 and receipt["actions"][-1]["scheduler"] == "not_due"
    assert sum(name == "reconcile-github-lifecycle.py" for name, _ in calls) == 1

    monkeypatch.setattr(module, "_utc_now", lambda: fixed + timedelta(minutes=5))
    code, _ = call_main(module, monkeypatch, capsys, tmp_path, "session-start", payload, "--tracker-binding", "none")
    assert code == 0
    assert sum(name == "reconcile-github-lifecycle.py" for name, _ in calls) == 2


def test_session_start_respects_host_owner_and_does_not_advance_failed_run(tmp_path, monkeypatch, capsys):
    module = load("c25_owner")
    config = tmp_path / ".dev-graph" / "config.json"
    write_config(config, owner="host_scheduler")
    calls = []

    def fake_invoke(path, *args):
        calls.append(path.name)
        return context_result(tmp_path, config) if path.name == "resolve-repo-context.py" else {"ok": False, "exit_code": 1}

    monkeypatch.setattr(module, "invoke", fake_invoke)
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "session-start", official("SessionStart", tmp_path), "--tracker-binding", "none")
    assert code == 0 and receipt["actions"][-1]["scheduler"] == "owned_by_host_scheduler"
    assert "reconcile-github-lifecycle.py" not in calls

    write_config(config, owner="claude_session_start")
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "session-start", official("SessionStart", tmp_path), "--tracker-binding", "none")
    assert code == 0 and receipt["actions"][-1]["scheduled_reconcile"]["ok"] is False
    state = json.loads((tmp_path / ".git" / "dev-graph" / module.SCHEDULE_STATE).read_text())
    assert state["last_result_ok"] is False and "last_reconciled_at" not in state


def test_scheduler_claim_suppresses_reentry_and_retries_after_failure(tmp_path):
    module = load("c25_schedule_claim")
    state_path = tmp_path / "coord" / module.SCHEDULE_STATE
    now = datetime(2026, 7, 13, 2, 0, tzinfo=timezone.utc)
    due, _ = module.claim_schedule_due(state_path, 5, now=now)
    assert due is True
    due, state = module.claim_schedule_due(state_path, 5, now=now)
    assert due is False and state["inflight_since"] == "2026-07-13T02:00:00Z"
    module.update_schedule_state(state_path, owner="claude_session_start", result={"ok": False}, now=now)
    due, _ = module.claim_schedule_due(state_path, 5, now=now)
    assert due is True, "a failed run must not advance last_reconciled_at"


@pytest.mark.parametrize(
    ("change", "expected", "exit_code"),
    [
        ({"owner": "both"}, "owner", 2),
        ({"interval_minutes": 1}, "interval_minutes", 0),
        ({"entry_point": "python unsafe.py"}, "entry_point", 0),
    ],
)
def test_invalid_scheduler_contract_only_blocks_for_owner_violation(tmp_path, monkeypatch, capsys, change, expected, exit_code):
    module = load(f"c25_bad_{expected}")
    config = tmp_path / ".dev-graph" / "config.json"
    write_config(config)
    value = json.loads(config.read_text())
    value["github"]["completion_policy"]["scheduled_reconciliation"].update(change)
    config.write_text(json.dumps(value))
    monkeypatch.setattr(module, "invoke", lambda path, *a: context_result(tmp_path, config))
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "session-start", official("SessionStart", tmp_path))
    assert code == exit_code and expected in receipt["actions"][-1]["scheduler_error"]


def test_post_tool_use_is_detached_deduplicated_and_redacted(tmp_path, monkeypatch, capsys):
    module = load("c25_async")
    config = tmp_path / "missing.json"
    monkeypatch.setattr(module, "invoke", lambda path, *a: context_result(tmp_path, config))
    spawns = []
    monkeypatch.setattr(module, "spawn", lambda script, *args: spawns.append((script, args)) or {"ok": True, "spawned": True, "pid": 42})
    payload = official(
        "PostToolUse", tmp_path, tool_name="Bash", tool_use_id="tool-1",
        tool_input={"command": "git push https://do-not-log@example.invalid/repo main"},
        tool_response={"exit_code": 0},
        dev_graph={"graph": "graph.json", "graph_node_id": "G1", "repo": "o/r", "pr": 8},
    )
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "post-tool-use", payload)
    assert code == 0 and receipt["actions"][-1]["async_reconcile"]["spawned"] is True
    assert len(spawns) == 1
    assert "do-not-log" not in json.dumps(receipt)
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "post-tool-use", payload)
    assert code == 0 and receipt["actions"][-1]["async_reconcile"]["deduplicated"] is True
    assert len(spawns) == 1
    ledger = json.loads((tmp_path / ".git" / "dev-graph" / module.HOOK_EVENTS).read_text())
    assert len(ledger["events"]) == 1 and ledger["events"][0]["status"] == "spawned"


def test_spawn_uses_real_background_process_boundaries(tmp_path, monkeypatch):
    module = load("c25_spawn")
    script = tmp_path / "worker.py"
    script.write_text("pass\n")
    captured = {}

    def fake_popen(argv, **kwargs):
        captured.update({"argv": argv, **kwargs})
        return SimpleNamespace(pid=99)

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    result = module.spawn(script, "--mode", "reconcile")
    assert result == {"ok": True, "spawned": True, "pid": 99}
    assert captured["start_new_session"] is True and captured["close_fds"] is True
    assert captured["stdin"] is module.subprocess.DEVNULL
    assert captured["stdout"] is module.subprocess.DEVNULL
    assert captured["stderr"] is module.subprocess.DEVNULL


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Write", "tool_use_id": "T", "tool_input": {"command": "git push"}, "tool_response": {"exit_code": 0}},
        {"tool_name": "Bash", "tool_use_id": "T", "tool_input": {"command": "git push"}, "tool_response": {"exit_code": 1}},
        {"tool_name": "Bash", "tool_use_id": "T", "tool_input": {"command": "echo safe"}, "tool_response": {"exit_code": 0}},
        {"tool_name": "Bash", "tool_input": {"command": "git push"}, "tool_response": {"exit_code": 0}},
    ],
)
def test_post_tool_observation_rejects_nonmatching_events_as_noop(tmp_path, monkeypatch, capsys, payload):
    module = load("c25_observe")
    monkeypatch.setattr(module, "invoke", lambda path, *a: context_result(tmp_path, tmp_path / "missing.json"))
    monkeypatch.setattr(module, "spawn", lambda *a: pytest.fail("invalid observation must not spawn"))
    payload = official("PostToolUse", tmp_path, **payload)
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "post-tool-use", payload)
    assert code == 0 and "noop" in receipt["actions"][-1]


def test_identity_boundary_and_task_owner_fail_closed_only_for_target(tmp_path, monkeypatch, capsys):
    module = load("c25_identity")
    missing = tmp_path / "config.json"
    parks = []

    def fake_invoke(path, *args):
        if path.name == "resolve-repo-context.py":
            return context_result(tmp_path, missing)
        parks.append(args)
        return {"ok": False, "exit_code": 1, "stderr": "owner mismatch"}

    monkeypatch.setattr(module, "invoke", fake_invoke)
    outside = tmp_path.parent
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "post-tool-use", official("PostToolUse", outside))
    assert code == 2 and "outside caller repository" in receipt["actions"][-1]["error"]

    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "task-completed", official("TaskCompleted", tmp_path, task_subject="ordinary task"))
    assert code == 0 and parks == [] and "noop" in receipt["actions"][-1]
    code, receipt = call_main(module, monkeypatch, capsys, tmp_path, "task-completed", official("TaskCompleted", tmp_path, task_subject="done [DG:G1]"))
    assert code == 2 and parks and receipt["actions"][-2]["park"]["ok"] is False


def test_task_completed_non_owner_operational_failure_is_reported_without_blocking(tmp_path, monkeypatch, capsys):
    module = load("c25_task_non_owner_failure")

    def fake_invoke(path, *args):
        if path.name == "resolve-repo-context.py":
            return context_result(tmp_path, tmp_path / "missing.json")
        return {"ok": False, "exit_code": 1, "stderr": "temporary dependency unavailable"}

    monkeypatch.setattr(module, "invoke", fake_invoke)
    code, receipt = call_main(
        module, monkeypatch, capsys, tmp_path, "task-completed",
        official("TaskCompleted", tmp_path, task_subject="done [DG:G1]"),
    )
    assert code == 0
    assert receipt["actions"][-2]["park"] == {"ok": False, "exit_code": 1}
