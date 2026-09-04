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
    # 改ざんされた preview は seal 検証で落ちるため候補にならず、confirmation は発行されない。
    # プロンプト自体は握り潰さない (拒否しても安全性は増えず、セッションだけが詰まるため)。
    assert tampered_confirmation.returncode == 0, tampered_confirmation.stderr
    context = json.loads(tampered_confirmation.stdout)["hookSpecificOutput"]["additionalContext"]
    assert json.loads(context.split("\n", 1)[1])["status"] == "confirmation-unmatched"
    assert not list(
        (tmp_path / ".artifact-delivery" / "external-mutation").glob("confirmation-*.json")
    )

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


def _intent(project: pathlib.Path, prompt: str) -> dict:
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "cwd": str(project),
        "session_id": "session-fixture",
        "prompt": prompt,
    }
    result = _run("hook-confirm", input_text=json.dumps(payload))
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    return json.loads(context.split("\n", 1)[1])


def _fake_gh(project: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """A stand-in whose basename is `gh`, so argv classifies without touching GitHub."""
    marker = project / "gh-ran.txt"
    binary = project / "bin" / "gh"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(f'#!/bin/sh\necho "$@" > {marker}\n')
    binary.chmod(0o755)
    return binary, marker


def test_natural_language_request_authorizes_a_pr_create_without_a_typed_challenge(tmp_path):
    grant = _intent(tmp_path, "この変更でプルリクを出しておいてください")
    assert grant["status"] == "intent-granted"
    assert grant["granted_classes"] == ["github-pr-write"]

    binary, marker = _fake_gh(tmp_path)
    command = [str(binary), "pr", "create", "--draft", "--title", "fixture"]
    preview = _preview(tmp_path, command)
    assert preview["action_class"] == "github-pr-write"
    assert preview["auto_grantable"] is True
    assert not marker.exists()

    authorization = _run(
        "authorize-intent",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        preview["receipt_path"],
        "--intent-receipt",
        grant["receipt_path"],
    )
    assert authorization.returncode == 0, authorization.stderr
    authorized = json.loads(authorization.stdout)
    assert authorized["confirmation_receipt_kind"] == "intent"
    assert not marker.exists()

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
    assert marker.read_text().strip() == "pr create --draft --title fixture"


def test_intent_grant_never_covers_irreversible_or_unclassified_argv(tmp_path):
    grant = _intent(tmp_path, "プルリクを作成して")
    binary, _ = _fake_gh(tmp_path)
    for command in (
        [str(binary), "pr", "merge", "--squash"],
        [str(binary), "api", "-X", "POST", "/repos/o/r/releases"],
        [sys.executable, "-c", "print('unclassified')"],
    ):
        preview = _preview(tmp_path, command)
        assert preview["action_class"] is None, command
        assert preview["auto_grantable"] is False, command
        result = _run(
            "authorize-intent",
            "--project-root",
            str(tmp_path),
            "--preview-receipt",
            preview["receipt_path"],
            "--intent-receipt",
            grant["receipt_path"],
        )
        assert result.returncode != 0, command
        assert "not auto-grantable" in result.stderr


def test_intent_grant_is_single_use_and_cannot_backdate_a_preview(tmp_path):
    binary, _ = _fake_gh(tmp_path)
    early = _preview(tmp_path, [str(binary), "pr", "create", "--title", "early"])
    grant = _intent(tmp_path, "プルリクを出して")
    backdated = _run(
        "authorize-intent",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        early["receipt_path"],
        "--intent-receipt",
        grant["receipt_path"],
    )
    assert backdated.returncode != 0
    assert "predates the intent grant" in backdated.stderr

    first_preview = _preview(tmp_path, [str(binary), "pr", "create", "--title", "one"])
    second_preview = _preview(tmp_path, [str(binary), "pr", "create", "--title", "two"])
    args = ("--project-root", str(tmp_path), "--intent-receipt", grant["receipt_path"])
    first = _run("authorize-intent", *args, "--preview-receipt", first_preview["receipt_path"])
    second = _run("authorize-intent", *args, "--preview-receipt", second_preview["receipt_path"])
    assert first.returncode == 0, first.stderr
    assert second.returncode != 0
    assert "already consumed" in second.stderr


def test_japanese_phrasings_without_spaces_are_recognized(tmp_path):
    """CJK が \\w に含まれるため \\bPR\\b は "PRを出して" で落ちる。実際の言い回しで固定する。"""
    for prompt in ("pr出して", "PRを出して", "PR出しておいて", "プルリクを出して", "pull request を作成して"):
        grant = _intent(tmp_path, prompt)
        assert grant["status"] == "intent-granted", prompt
        assert grant["granted_classes"] == ["github-pr-write"], prompt


def test_unrelated_prompt_grants_nothing(tmp_path):
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "cwd": str(tmp_path),
        "session_id": "session-fixture",
        "prompt": "このテストが落ちる原因を調べて",
    }
    result = _run("hook-confirm", input_text=json.dumps(payload))
    assert result.returncode == 0
    assert result.stdout == ""


def test_stale_challenge_does_not_block_the_prompt(tmp_path):
    _preview(tmp_path, [sys.executable, "-c", "print('live')"])
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "cwd": str(tmp_path),
        "session_id": "session-fixture",
        "prompt": "CONFIRM EXTERNAL MUTATION " + "0" * 24,
    }
    result = _run("hook-confirm", input_text=json.dumps(payload))
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert json.loads(context.split("\n", 1)[1])["status"] == "confirmation-unmatched"
    assert not list(
        (tmp_path / ".artifact-delivery" / "external-mutation").glob("confirmation-*.json")
    )


def test_cancel_releases_pending_guard_context(tmp_path):
    preview = _preview(tmp_path, [sys.executable, "-c", "print('abandoned')"])
    probe = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "cwd": str(tmp_path),
        "tool_input": {"command": "git status --short"},
    }
    blocked = _run("pretool", input_text=json.dumps(probe))
    assert json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    cancelled = _run(
        "cancel",
        "--project-root",
        str(tmp_path),
        "--preview-receipt",
        preview["receipt_path"],
    )
    assert cancelled.returncode == 0, cancelled.stderr
    released = _run("pretool", input_text=json.dumps(probe))
    assert released.returncode == 0
    assert released.stdout == ""


def test_pretool_allows_the_new_canonical_actions():
    commands = (
        "python3 $CLAUDE_PLUGIN_ROOT/scripts/build-external-mutation-guard.py authorize-intent "
        "--project-root /tmp --preview-receipt p.json --intent-receipt i.json",
        "python3 $CLAUDE_PLUGIN_ROOT/scripts/build-external-mutation-guard.py cancel "
        "--project-root /tmp --preview-receipt p.json",
    )
    for command in commands:
        result = _run(
            "pretool",
            input_text=json.dumps(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": command},
                }
            ),
        )
        assert result.returncode == 0
        assert result.stdout == "", command


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
    assert len(projections) == 21
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
    assert external == 34
