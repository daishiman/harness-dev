"""Thin hook-adapter tests for the shared external-intelligence engine."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "auto-record-lesson.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("auto_record_lesson", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


def test_failure_detection_supports_both_hook_payloads(mod):
    claude = {
        "hook_event_name": "PostToolUseFailure",
        "tool_error": "permission denied",
    }
    codex = {
        "hook_event_name": "PostToolUse",
        "tool_response": {"exit_code": 2, "output": "command stopped"},
    }
    success = {
        "hook_event_name": "PostToolUse",
        "tool_response": {"exit_code": 0, "output": "ok"},
    }
    successful_edit_with_error_text = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_response": {"success": True, "output": "wrote example: ERROR is handled"},
    }
    semantic_skill_failure = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "tool_response": {"content": "ERROR validator rejected output"},
    }

    assert mod._failure_text(claude) == "permission denied"
    assert "exit code 2" in mod._failure_text(codex)
    assert mod._failure_text(success) == ""
    assert mod._failure_text(successful_edit_with_error_text) == ""
    assert "validator rejected" in mod._failure_text(semantic_skill_failure)


def test_redaction_removes_credentials_and_home(mod, monkeypatch):
    monkeypatch.setattr(mod.Path, "home", lambda: Path("/Users/alice"))
    text = "token=abc password:xyz Bearer secret /Users/alice/project"

    redacted = mod._redact(text)

    assert "abc" not in redacted
    assert "xyz" not in redacted
    assert "Bearer secret" not in redacted
    assert "/Users/alice" not in redacted
    assert redacted.endswith("~/project")


@pytest.mark.parametrize(
    "text,secrets",
    [
        ('{"api_key": "json-secret", "message": "keep me"}', ["json-secret"]),
        ("Authorization: Bearer header-secret\nmessage: keep me", ["header-secret"]),
        ("authorization: Basic YmFzZWM2NA==", ["YmFzZWM2NA"]),
        ("failed with Bearer bare-secret", ["bare-secret"]),
        ("cmd --api-key cli-secret --mode safe", ["cli-secret"]),
        ("cmd --token=equals-secret --mode safe", ["equals-secret"]),
        ("password='quoted-secret' detail=keep", ["quoted-secret"]),
    ],
)
def test_redaction_covers_structured_headers_and_cli_forms(mod, text, secrets):
    redacted = mod._redact(text)

    assert all(secret not in redacted for secret in secrets)
    assert "<redacted>" in redacted
    if "keep" in text:
        assert "keep" in redacted


def test_agent_detection_prefers_explicit_then_runtime_env(mod, monkeypatch):
    monkeypatch.setenv("HARNESS_AGENT", "other")
    assert mod._agent() == "other"

    monkeypatch.delenv("HARNESS_AGENT")
    monkeypatch.setenv("PLUGIN_DATA", "/tmp/codex-data")
    assert mod._agent() == "codex"

    monkeypatch.delenv("PLUGIN_DATA")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", "/tmp/claude-data")
    assert mod._agent() == "claude"


def test_build_command_is_argument_safe_and_uses_shared_engine(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("HARNESS_AGENT", "codex")
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest -q"},
        "cwd": str(tmp_path),
        "session_id": "s-1",
        "turn_id": "t-2",
        "tool_use_id": "u-3",
    }

    command = mod.build_command(payload, "ERROR token=super-secret")

    assert command[0] == sys.executable
    assert Path(command[1]).name == "build-external-intelligence.py"
    assert command[2:4] == ["--agent", "codex"]
    assert command[command.index("--project-root") + 1] == str(tmp_path)
    assert command[command.index("--context-id") + 1] == "session:s-1"
    assert command[command.index("--evidence-ref") + 1] == "hook:t-2:u-3"
    assert command[command.index("--evidence-source") + 1].startswith("hook-failure:bash:")
    assert command[command.index("--ambiguous-action") + 1] == "quarantine"
    assert "super-secret" not in command[command.index("--summary") + 1]


def test_identity_uses_normalized_failure_signature_not_instance_hint(mod):
    first = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/first.py"},
        "turn_id": "turn-1",
        "tool_use_id": "tool-1",
    }
    second = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/second.py"},
        "turn_id": "turn-2",
        "tool_use_id": "tool-2",
    }
    failure_a = "ERROR /tmp/run-a/test_widget.py:17 AssertionError request_id=abc-123 expected 3 got 4"
    failure_b = "ERROR /var/tmp/run-b/test_widget.py:991 AssertionError request_id=xyz-789 expected 8 got 9"

    command_a = mod.build_command(first, failure_a)
    command_b = mod.build_command(second, failure_b)

    assert command_a[command_a.index("--title") + 1] == command_b[command_b.index("--title") + 1]
    assert command_a[command_a.index("--rule") + 1] == command_b[command_b.index("--rule") + 1]
    assert command_a[command_a.index("--evidence-source") + 1] == command_b[command_b.index("--evidence-source") + 1]
    assert command_a[command_a.index("--summary") + 1] != command_b[command_b.index("--summary") + 1]


def test_different_failure_classes_keep_distinct_identity(mod):
    payload = {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}}

    permission = mod.build_command(payload, "ERROR PermissionError: access denied")
    timeout = mod.build_command(payload, "ERROR TimeoutError: operation expired")

    assert permission[permission.index("--title") + 1] != timeout[timeout.index("--title") + 1]
    assert permission[permission.index("--rule") + 1] != timeout[timeout.index("--rule") + 1]

    exit_one = mod.build_command(payload, "ERROR process ended with exit code 1")
    exit_two = mod.build_command(payload, "ERROR process ended with exit code 2")
    assert exit_one[exit_one.index("--title") + 1] != exit_two[exit_two.index("--title") + 1]


def test_no_secret_reaches_any_engine_argument(mod):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "deploy --api-key command-secret"},
    }
    failure = (
        'ERROR {"token": "json-secret"} Authorization: Basic header-secret '
        "Bearer bare-secret --password cli-secret"
    )

    command = mod.build_command(payload, failure)
    joined = "\n".join(command)

    for secret in ("command-secret", "json-secret", "header-secret", "bare-secret", "cli-secret"):
        assert secret not in joined


def test_main_ignores_invalid_or_successful_payload(mod, monkeypatch):
    calls = []
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO("not-json"))
    assert mod.main() == 0

    monkeypatch.setattr(
        mod.sys,
        "stdin",
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_response": "ok"})),
    )
    assert mod.main() == 0
    assert calls == []


def test_main_invokes_engine_without_blocking_parent(mod, monkeypatch, capsys, tmp_path):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_response": {"exit_code": 1, "output": "FAIL test_widget"},
        "cwd": str(tmp_path),
    }
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"action": "created", "state_dir": str(tmp_path / ".harness")}),
            stderr="",
        )

    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    assert mod.main() == 0
    assert seen["kwargs"]["timeout"] == 8
    assert seen["kwargs"]["check"] is False
    assert "created" in capsys.readouterr().err


def test_main_fails_soft_when_engine_is_unavailable(mod, monkeypatch, capsys):
    payload = {
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Write",
        "tool_error": "permission denied",
    }
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("missing engine")),
    )

    assert mod.main() == 0
    assert "skipped" in capsys.readouterr().err
