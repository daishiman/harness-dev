"""Executable external-mutation guard contract and hook integration tests."""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor


ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "plugins"
    / "skill-governance-adapters"
    / "scripts"
    / "build-external-mutation-guard.py"
)
MANIFEST = ROOT / "plugins/skill-governance-adapters/.claude-plugin/plugin.json"
SCHEMA = (
    ROOT
    / "plugins"
    / "skill-governance-adapters"
    / "schemas"
    / "external-mutation-guard.schema.json"
)
CONTRACT = (
    ROOT
    / "plugins"
    / "skill-governance-adapters"
    / "references"
    / "external-mutation-guard-contract.md"
)


def _run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def _preview(project: pathlib.Path, command: list[str], *, target: str = "remote:fixture") -> dict:
    result = _run(
        "preview",
        "--project-root",
        str(project),
        "--entrypoint-ref",
        "plugin:fixture/skills/run-fixture/SKILL.md",
        "--target-scope",
        target,
        "--diff-summary",
        "Create or update exactly one fixture record.",
        "--side-effect-summary",
        "Writes to the declared remote fixture target; no other target is changed.",
        "--command-json",
        json.dumps(command),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _confirm(project: pathlib.Path, challenge: str) -> dict:
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "cwd": str(project),
        "session_id": "session-fixture",
        "prompt": f"CONFIRM EXTERNAL MUTATION {challenge}",
    }
    result = _run("hook-confirm", input_text=json.dumps(payload))
    assert result.returncode == 0, result.stderr
    hook_output = json.loads(result.stdout)
    context = hook_output["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("[external-mutation-confirmation]\n")
    return json.loads(context.split("\n", 1)[1])


def test_public_guard_cli_executes_only_the_confirmed_preview(tmp_path):
    assert RUNNER.is_file()
    assert SCHEMA.is_file()
    assert CONTRACT.is_file()
    output = tmp_path / "executed.txt"
    command = [sys.executable, "-c", f"from pathlib import Path; Path({str(output)!r}).write_text('ok')"]

    preview_result = _run(
        "preview",
        "--project-root",
        str(tmp_path),
        "--entrypoint-ref",
        "plugin:fixture/skills/run-fixture/SKILL.md",
        "--target-scope",
        "remote:fixture",
        "--diff-summary",
        "Create or update exactly one fixture record.",
        "--side-effect-summary",
        "Writes to the declared remote fixture target; no other target is changed.",
        "--command-json",
        json.dumps(command),
    )
    assert preview_result.returncode == 0, preview_result.stderr
    positions = [
        preview_result.stdout.index(f'"{field}"')
        for field in (
            "target_scope",
            "command_argv",
            "diff_summary",
            "side_effect_summary",
            "challenge",
        )
    ]
    assert positions == sorted(positions)
    preview = json.loads(preview_result.stdout)
    assert preview["target_scope"] == "remote:fixture"
    assert preview["command_argv"] == command
    assert preview["diff_summary"] == "Create or update exactly one fixture record."
    assert preview["side_effect_summary"].startswith("Writes to the declared remote fixture")
    assert not output.exists()
    confirmation = _confirm(tmp_path, preview["challenge"])
    authorization = _run(
        "authorize",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        preview["receipt_path"],
        "--confirmation-receipt",
        confirmation["receipt_path"],
    )
    assert authorization.returncode == 0, authorization.stderr
    authorized = json.loads(authorization.stdout)
    assert not output.exists()

    execute = _run(
        "execute",
        "--project-root",
        str(tmp_path),
        "--authorization-receipt",
        authorized["receipt_path"],
        "--command-json",
        json.dumps(command),
    )
    assert execute.returncode == 0, execute.stderr
    assert output.read_text() == "ok"
    after_completion = _run(
        "pretool",
        input_text=json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "cwd": str(tmp_path),
                "tool_input": {"command": "python3 unknown_read_only_helper.py"},
            }
        ),
    )
    assert after_completion.returncode == 0
    assert after_completion.stdout == ""


def test_preview_and_confirmation_can_authorize_only_once(tmp_path):
    command = [sys.executable, "-c", "print('once')"]
    preview = _preview(tmp_path, command)
    confirmation = _confirm(tmp_path, preview["challenge"])
    args = (
        "authorize",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        preview["receipt_path"],
        "--confirmation-receipt",
        confirmation["receipt_path"],
    )
    first = _run(*args)
    second = _run(*args)
    assert first.returncode == 0, first.stderr
    assert second.returncode != 0
    assert "already consumed" in second.stderr


def test_concurrent_authorize_has_exactly_one_winner(tmp_path):
    command = [sys.executable, "-c", "print('once')"]
    preview = _preview(tmp_path, command)
    confirmation = _confirm(tmp_path, preview["challenge"])
    args = (
        "authorize",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        preview["receipt_path"],
        "--confirmation-receipt",
        confirmation["receipt_path"],
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _run(*args), range(2)))
    assert sorted(result.returncode for result in results) == [0, 2]
    assert sum("already consumed" in result.stderr for result in results) == 1


def test_confirmation_cannot_authorize_a_different_preview(tmp_path):
    first = _preview(tmp_path, [sys.executable, "-c", "print('one')"], target="remote:one")
    second = _preview(tmp_path, [sys.executable, "-c", "print('two')"], target="remote:two")
    confirmation = _confirm(tmp_path, first["challenge"])
    result = _run(
        "authorize",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        second["receipt_path"],
        "--confirmation-receipt",
        confirmation["receipt_path"],
    )
    assert result.returncode != 0
    assert "not bound" in result.stderr


def test_tampered_preview_and_changed_execute_argv_fail_closed(tmp_path):
    command = [sys.executable, "-c", "print('safe')"]
    preview = _preview(tmp_path, command)
    receipt_path = pathlib.Path(preview["receipt_path"])
    receipt = json.loads(receipt_path.read_text())
    receipt["target_scope"] = "remote:tampered"
    receipt_path.write_text(json.dumps(receipt))
    tampered_confirmation = _run(
        "hook-confirm",
        input_text=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "cwd": str(tmp_path),
                "session_id": "session-fixture",
                "prompt": f"CONFIRM EXTERNAL MUTATION {preview['challenge']}",
            }
        ),
    )
    assert tampered_confirmation.returncode != 0
    assert "challenge" in tampered_confirmation.stderr

    preview = _preview(tmp_path, command)
    confirmation = _confirm(tmp_path, preview["challenge"])
    authorization = _run(
        "authorize",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        preview["receipt_path"],
        "--confirmation-receipt",
        confirmation["receipt_path"],
    )
    authorized = json.loads(authorization.stdout)
    changed = _run(
        "execute",
        "--project-root",
        str(tmp_path),
        "--authorization-receipt",
        authorized["receipt_path"],
        "--command-json",
        json.dumps([sys.executable, "-c", "print('changed')"]),
    )
    assert changed.returncode != 0
    assert "command digest" in changed.stderr


def test_pretool_blocks_direct_remote_mutation_outside_central_consumer():
    direct = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "curl -X POST https://example.invalid/items -d '{}'"},
    }
    blocked = _run("pretool", input_text=json.dumps(direct))
    assert blocked.returncode == 0
    output = json.loads(blocked.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    wrapped = {
        **direct,
        "tool_input": {
            "command": "python3 $CLAUDE_PLUGIN_ROOT/scripts/build-external-mutation-guard.py execute "
            "--project-root /tmp --authorization-receipt receipt.json "
            "--command-json '[\"curl\",\"-X\",\"POST\"]'"
        },
    }
    allowed = _run("pretool", input_text=json.dumps(wrapped))
    assert allowed.returncode == 0
    assert allowed.stdout == ""

    disguised = {
        **direct,
        "tool_input": {
            "command": "curl -X POST https://example.invalid/items -d '{}' # "
            "python3 $CLAUDE_PLUGIN_ROOT/scripts/build-external-mutation-guard.py execute"
        },
    }
    still_blocked = _run("pretool", input_text=json.dumps(disguised))
    assert still_blocked.returncode == 0
    output = json.loads(still_blocked.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    trailing = {
        **direct,
        "tool_input": {
            "command": "python3 $CLAUDE_PLUGIN_ROOT/scripts/build-external-mutation-guard.py execute "
            "--project-root /tmp --authorization-receipt receipt.json "
            "--command-json '[\"true\"]' ; curl -X POST https://example.invalid/items"
        },
    }
    trailing_blocked = _run("pretool", input_text=json.dumps(trailing))
    assert trailing_blocked.returncode == 0
    output = json.loads(trailing_blocked.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "full Bash command" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_pending_guard_context_blocks_unknown_binary(tmp_path):
    _preview(tmp_path, [sys.executable, "-c", "print('planned')"])
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "cwd": str(tmp_path),
        "tool_input": {"command": "python3 mutate_remote.py --really-write-remote"},
    }
    result = _run("pretool", input_text=json.dumps(payload))
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "pending guard context" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_pretool_blocks_known_entrypoint_mutation_clis_without_central_execute():
    commands = (
        'python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-send/scripts/send-campaign.py" '
        "--auto-approve",
        'python3 "$CLAUDE_PLUGIN_ROOT/scripts/gh-bridge.py" apply --plan sync.json',
        'python3 "$CLAUDE_PLUGIN_ROOT/scripts/intake_publish_pipeline.py" '
        '--intake output/x/intake.json --manifest output/x/notion-manifest.json',
    )
    for command in commands:
        result = _run(
            "pretool",
            input_text=json.dumps(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "cwd": "/tmp",
                    "tool_input": {"command": command},
                }
            ),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", command


def test_manifest_connects_confirmation_producer_and_pretool_enforcer():
    manifest = json.loads(MANIFEST.read_text())
    # 配線の実体は ./hooks/hooks.json にある。manifest が参照を書く形と、
    # 何も書かず loader の標準自動検出に任せる形の両方を辿って実体を読む。
    wiring = manifest.get("hooks")
    if wiring is None:
        wiring = json.loads((MANIFEST.parents[1] / "hooks" / "hooks.json").read_text())["hooks"]
    if isinstance(wiring, str):
        external = MANIFEST.parents[1] / wiring.lstrip("./")
        wiring = json.loads(external.read_text())["hooks"]
    hooks = wiring
    prompt_commands = [
        hook["command"]
        for group in hooks["UserPromptSubmit"]
        for hook in group["hooks"]
    ]
    pretool_commands = [
        hook["command"]
        for group in hooks["PreToolUse"]
        for hook in group["hooks"]
    ]
    assert any("build-external-mutation-guard.py\" hook-confirm" in item for item in prompt_commands)
    assert any("build-external-mutation-guard.py\" pretool" in item for item in pretool_commands)


def test_all_projections_pin_the_executable_guard_runtime():
    runner_sha = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    schema_sha = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    projections = sorted(ROOT.glob("plugins/*/artifact-delivery.json"))
    assert len(projections) == 20
    external = 0
    for path in projections:
        projection = json.loads(path.read_text())
        runtime = projection["external_mutation_runtime"]
        assert runtime["runner_sha256"] == runner_sha
        assert runtime["schema_sha256"] == schema_sha
        assert runtime["runner_ref"].endswith("/scripts/build-external-mutation-guard.py")
        for entrypoint in projection["entrypoints"]:
            if entrypoint["effect"] == "external-mutation":
                external += 1
                assert entrypoint["guard_contract"] == {
                    "runtime_ref": "#/external_mutation_runtime",
                    "flow": "preview-confirm-authorize-execute-v1",
                }
    assert external == 33
