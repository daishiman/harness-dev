"""run-skill-live-trial harness の機械検証 (tmux 非依存)。

- live-trial-status: transcript JSONL の 4 状態分類 + interrupt 例外 + subagents bytes 合算
- live-trial-poll: 終端 4 分岐 (DONE/STALL/GATE/HARD_CAP) + state-file JSON 永続化 +
  scenario 予算 (wall/token cap) + 壊れた state・usage 欠落の fail-closed
- build-live-trial-verdict: verdict 成否に関係なく自 run だけを reap する finalizer
- live-trial-verdict: schema 自己検証 / skill_dir_tree_sha 決定論 / proof 機械 gate /
  nudge 降格 / denylist 拒否 / 被験 skill 起動 gate / goal_seek 配線 gate
- live-trial-backend/boot/send: オフライン検査 (tmux 呼出は BLOCKED/fallback 側のみ) +
  run-id・owner-pid で範囲を絞った reap

合成 fixture は references/transcript-jsonl.md の実測スキーマに従う。
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial" / "scripts"
SCHEMA = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial"
    / "schemas" / "live-trial-verdict.schema.json"
)


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), SCRIPTS / f"{stem}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


status_mod = _load("live-trial-status")
poll_mod = _load("live-trial-poll")
verdict_mod = _load("live-trial-verdict")
planner_mod = _load("plan-live-trials")
backend_mod = _load("live-trial-backend")
boot_mod = _load("live-trial-boot")
send_mod = _load("live-trial-send")
finalize_mod = _load("build-live-trial-verdict")


def _codex_rollout(tmp_path, *, read_ok=True, inject=True, complete=True):
    skill = tmp_path / "skills" / "run-native"
    skill.mkdir(parents=True, exist_ok=True)
    source = "---\nname: run-native\ndescription: native test\n---\n\n# Native\nRead this source.\n"
    (skill / "SKILL.md").write_text(source)
    rows = [
        {"type": "session_meta", "payload": {"id": "native-root", "cwd": str(tmp_path), "cli_version": "0.165.0", "source": "exec"}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn-1"}},
        {"type": "turn_context", "payload": {"model": "gpt-native", "approval_policy": "never",
         "sandbox_policy": {"type": "workspace-write", "network_access": False, "exclude_tmpdir_env_var": True, "exclude_slash_tmp": True},
         "permission_profile": {"file_system": {"type": "restricted", "entries": [{"path": {"type": "path", "path": str(tmp_path)}, "access": "write"}]}}}},
        {"type": "response_item", "payload": {"type": "message", "id": "user-1", "role": "user", "content": [{"type": "input_text", "text": "$run-native"}], "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1", "content_item_kinds": ["user.text"]}}},
    ]
    if inject:
        rows.append({"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": f"<skill>\n<name>run-native</name>\n<path>{skill / 'SKILL.md'}</path>\n{source}\n</skill>"}], "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1", "content_item_kinds": ["skills.selected_skill_instructions"]}}})
    else:
        rows.append({"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "$run-native"}]}})
    rows.extend([
        {"type": "response_item", "payload": {"type": "custom_tool_call", "call_id": "read-1", "name": "exec", "input": f'text(await tools.exec_command({{cmd:"cat {skill / "SKILL.md"}"}}));'}},
        {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "read-1", "output": [{"type": "input_text", "text": json.dumps({"exit_code": 0 if read_ok else 1, "output": source})}]}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 20, "reasoning_output_tokens": 5, "total_tokens": 120}}}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 150, "cached_input_tokens": 100, "output_tokens": 30, "reasoning_output_tokens": 10, "total_tokens": 180}}}},
    ])
    if complete:
        rows.append({"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "turn-1"}})
    path = _write_jsonl(tmp_path / "native.jsonl", rows)
    return path, skill


def test_codex_native_activation_binds_injected_source_and_successful_read(tmp_path):
    native = _load("extract-codex-transcript")
    path, skill = _codex_rollout(tmp_path)
    result = native.inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["models"] == ["gpt-native"]
    assert result["cli_version"] == "0.165.0"
    assert result["invoked_skills"] == ["demo:run-native"]
    assert result["completed"] is True
    assert result["usage"]["total_tokens"] == 180
    assert result["usage"]["input_tokens"] == 150
    assert result["usage"]["cache_read_input_tokens"] == 0
    assert result["format_errors"] == []


def _rename_native_injection(path, name):
    rows = list(map(json.loads, path.read_text().splitlines()))
    for row in rows:
        payload = row.get("payload", {})
        for content in payload.get("content", []):
            if isinstance(content, dict) and "<skill>" in content.get("text", ""):
                content["text"] = content["text"].replace("<name>run-native</name>", f"<name>{name}</name>")
    _write_jsonl(path, rows)


def test_codex_qualified_native_skill_activates_exact_namespace(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    _rename_native_injection(path, "demo:run-native")
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["invoked_skills"] == ["demo:run-native"]
    assert result["activation_errors"] == []


@pytest.mark.parametrize("name", ["other:run-native", "demo:run-native:extra", "demo::run-native", ":run-native", "demo:", "../demo:run-native", "demo:../run-native", "demo*:run-native"])
def test_codex_wrong_namespace_or_invalid_qualified_name_is_rejected(tmp_path, name):
    path, skill = _codex_rollout(tmp_path)
    _rename_native_injection(path, name)
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert "demo:run-native" not in result["invoked_skills"]
    assert result["activation_errors"]


@pytest.mark.parametrize("namespace", ["provider", "outside"])
def test_codex_qualified_nested_skill_requires_declared_provider(tmp_path, namespace):
    target = _write_trial_plugin(tmp_path, "demo", "demo", "run-native")
    provider = _write_trial_plugin(tmp_path, "provider", "provider", "run-delegate")
    outside = _write_trial_plugin(tmp_path, "outside", "outside", "run-delegate")
    _write_package_contract(target, ["provider"], skills=["run-native"])
    for root in (provider, outside):
        _write_package_contract(root, [], skills=["run-delegate"])
    for root in (target, provider, outside):
        (root / ".codex-plugin").mkdir()
        (root / ".codex-plugin/plugin.json").write_text(json.dumps({"name": root.name}))
    path, skill = _codex_rollout(target)
    nested = (provider if namespace == "provider" else outside) / "skills/run-delegate/SKILL.md"
    body = nested.read_text()
    rows = list(map(json.loads, path.read_text().splitlines()))
    rows[-1:-1] = [
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": f"<skill>\n<name>{namespace}:run-delegate</name>\n<path>{nested}</path>\n{body}\n</skill>"}], "internal_chat_message_metadata_passthrough": {"content_item_kinds": ["skills.selected_skill_instructions"]}}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "call_id": "nested-read", "name": "exec", "input": f'text(await tools.exec_command({{cmd:"cat {nested}"}}));'}},
        {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "nested-read", "output": [{"type": "input_text", "text": json.dumps({"exit_code": 0, "output": body})}]}},
    ]
    _write_jsonl(path, rows)
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert "demo:run-native" in result["invoked_skills"]
    assert (f"{namespace}:run-delegate" in result["invoked_skills"]) is (namespace == "provider")
    assert bool(result["activation_errors"]) is (namespace == "outside")


def test_codex_archived_projection_requires_exact_controller_mapping(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    _rename_native_injection(path, "demo:run-native")
    original = str(skill / "SKILL.md")
    archived = "/gone/fixture/.agents/skills/run-native/SKILL.md"
    rows = list(map(json.loads, path.read_text().splitlines()))
    _write_jsonl(path, [json.loads(json.dumps(row).replace(original, archived)) for row in rows])
    native = _load("extract-codex-transcript")
    assert native.inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")["invoked_skills"] == []
    receipt = {"skills": [{"qualified_skill": "demo:run-native", "project_path": archived,
                           "source_path": "/gone/providers/plugins/demo/skills/run-native/SKILL.md",
                           "sha256": hashlib.sha256((skill / "SKILL.md").read_bytes()).hexdigest()}],
               "source_body_modified": False}
    receipt_path = path.parent / "project-projection.json"
    receipt_path.write_text(json.dumps(receipt))
    state = {"runtime": "codex", "session_id": "native-root", "collected": True,
             "projection_receipt_ref": receipt_path.name,
             "projection_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    state_path = path.parent / "native-run-state.json"
    state_path.write_text(json.dumps(state))
    assert native.inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")["invoked_skills"] == ["demo:run-native"]
    receipt["skills"][0]["source_path"] = "/gone/providers/plugins/other/skills/run-native/SKILL.md"
    receipt_path.write_text(json.dumps(receipt))
    state["projection_receipt_sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    state_path.write_text(json.dumps(state))
    assert native.inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")["invoked_skills"] == []


def _codex_relocated_source(tmp_path, *, alias=False, remove_private=False):
    path, skill = _codex_rollout(tmp_path / "checkout")
    _rename_native_injection(path, "demo:run-native")
    source = tmp_path / "private/providers/plugins/demo/skills/run-native/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_bytes((skill / "SKILL.md").read_bytes())
    project = tmp_path / "private/fixture/.agents/skills/run-native/SKILL.md"
    project.parent.mkdir(parents=True)
    project.symlink_to(source)
    injected = project if alias else source
    original = str(skill / "SKILL.md")
    rows = [json.loads(json.dumps(row).replace(original, str(injected)))
            for row in map(json.loads, path.read_text().splitlines())]
    _write_jsonl(path, rows)
    receipt = {"skills":[{"qualified_skill":"demo:run-native", "project_path":str(project),
                           "source_path":str(source), "sha256":hashlib.sha256(source.read_bytes()).hexdigest()}],
               "source_body_modified":False}
    receipt_path = path.parent / "project-projection.json"
    receipt_path.write_text(json.dumps(receipt))
    state = {"runtime":"codex", "session_id":"native-root", "collected":True,
             "projection_receipt_ref":receipt_path.name,
             "projection_receipt_sha256":hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    (path.parent / "native-run-state.json").write_text(json.dumps(state))
    if remove_private:
        source.unlink()
        project.unlink()
    return path, skill, source, project, receipt, state


@pytest.mark.parametrize("alias,remove_private", [(False,False),(True,False),(False,True),(True,True)])
def test_codex_relocated_checkout_requires_exact_alias_or_source_and_identical_bytes(tmp_path,alias,remove_private):
    path, skill, _source, _project, _receipt, _state = _codex_relocated_source(tmp_path,alias=alias,remove_private=remove_private)
    before = path.read_bytes()
    result = _load("extract-codex-transcript").inspect_transcript(path,skill_dir=skill,target_skill="demo:run-native")
    assert result["invoked_skills"] == ["demo:run-native"]
    assert result["activation_errors"] == []
    assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["namespace","receipt_body","current_body","private_body","read_output",
                                     "user_xml","unmapped_suffix","mapping_sha"])
def test_codex_relocation_never_accepts_namespace_body_read_or_mapping_shortcuts(tmp_path,mutation):
    path, skill, source, _project, receipt, state = _codex_relocated_source(tmp_path)
    rows = list(map(json.loads,path.read_text().splitlines()))
    if mutation == "namespace": receipt["skills"][0]["qualified_skill"] = "other:run-native"
    elif mutation == "receipt_body": receipt["skills"][0]["sha256"] = "0"*64
    elif mutation == "current_body": (skill/"SKILL.md").write_text("changed current source")
    elif mutation == "private_body": source.write_text("changed original provider source")
    elif mutation == "read_output":
        for row in rows:
            if row.get("payload",{}).get("type")=="custom_tool_call_output":
                row["payload"]["output"]=[{"type":"input_text","text":json.dumps({"exit_code":0,"output":"different read body"})}]
    elif mutation == "user_xml":
        for row in rows:
            if "skills.selected_skill_instructions" in row.get("payload",{}).get("internal_chat_message_metadata_passthrough",{}).get("content_item_kinds",[]):
                row["payload"]["internal_chat_message_metadata_passthrough"]["content_item_kinds"]=["user.text"]
    elif mutation == "unmapped_suffix":
        rows=[json.loads(json.dumps(row).replace(str(source),"/unmapped/providers/plugins/demo/skills/run-native/SKILL.md"))for row in rows]
    _write_jsonl(path,rows)
    receipt_path=path.parent/"project-projection.json"
    receipt_path.write_text(json.dumps(receipt))
    state["projection_receipt_sha256"]="0"*64 if mutation=="mapping_sha" else hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    (path.parent/"native-run-state.json").write_text(json.dumps(state))
    result=_load("extract-codex-transcript").inspect_transcript(path,skill_dir=skill,target_skill="demo:run-native")
    assert result["invoked_skills"]==[]


def test_codex_symlink_spelling_of_the_same_skill_file_counts_as_read(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    alias = tmp_path / "alias" / "skills" / "run-native"
    alias.parent.mkdir(parents=True)
    alias.symlink_to(skill, target_is_directory=True)
    real = str(skill / "SKILL.md")
    spelled = str(alias / "SKILL.md")
    assert Path(spelled).resolve() == Path(real).resolve()
    rows = list(map(json.loads, path.read_text().splitlines()))
    for row in rows:
        payload = row.get("payload", {})
        if payload.get("call_id") == "read-1" and payload.get("type") == "custom_tool_call":
            payload["input"] = payload["input"].replace(real, spelled)
    _write_jsonl(path, rows)
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["invoked_skills"] == ["demo:run-native"]
    assert result["activation_errors"] == []
    assert result["activations"][0]["path"] == real
    assert result["activations"][0]["source_sha256"] == hashlib.sha256((skill / "SKILL.md").read_text().encode()).hexdigest()


def test_codex_identical_copy_at_another_path_is_not_the_pinned_read(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    copy = tmp_path / "other" / "skills" / "run-native" / "SKILL.md"
    copy.parent.mkdir(parents=True)
    copy.write_bytes((skill / "SKILL.md").read_bytes())
    real = str(skill / "SKILL.md")
    rows = list(map(json.loads, path.read_text().splitlines()))
    for row in rows:
        payload = row.get("payload", {})
        if payload.get("call_id") == "read-1" and payload.get("type") == "custom_tool_call":
            payload["input"] = payload["input"].replace(real, str(copy))
    _write_jsonl(path, rows)
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["invoked_skills"] == []
    assert any(item.startswith("native-skill-read-unproven:") for item in result["activation_errors"])


def test_codex_skill_md_filename_suffix_is_not_a_resolved_read(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    decoy = skill / "SKILL.md.backup"
    decoy.write_bytes((skill / "SKILL.md").read_bytes())
    real = str(skill / "SKILL.md")
    rows = list(map(json.loads, path.read_text().splitlines()))
    for row in rows:
        payload = row.get("payload", {})
        if payload.get("call_id") == "read-1" and payload.get("type") == "custom_tool_call":
            payload["input"] = payload["input"].replace(real, str(decoy))
    _write_jsonl(path, rows)
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["invoked_skills"] == []


@pytest.mark.parametrize("read_ok,inject", [(False, True), (True, False)])
def test_codex_mention_or_failed_read_is_not_native_activation(tmp_path, read_ok, inject):
    path, skill = _codex_rollout(tmp_path, read_ok=read_ok, inject=inject)
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["invoked_skills"] == []


def test_codex_modified_source_is_not_accepted_as_current_activation(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    (skill / "SKILL.md").write_text("changed source\n")
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["invoked_skills"] == []


def test_codex_missing_completion_is_not_overridden_by_caller(tmp_path):
    path, skill = _codex_rollout(tmp_path, complete=False)
    result = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert result["completed"] is False


def test_codex_claude_transcript_cannot_be_relabelled_native(tmp_path):
    path = _write_jsonl(tmp_path / "claude.jsonl", [_tool_use("s1", "Skill", {"skill": "demo:run-native"})])
    result = _load("extract-codex-transcript").inspect_transcript(path)
    assert result["format_errors"]
    assert result["models"] == []
    assert result["usage"]["measured"] is False


def test_codex_missing_usage_is_unmeasured(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    rows = [row for row in map(json.loads, path.read_text().splitlines()) if row.get("payload", {}).get("type") != "token_count"]
    _write_jsonl(path, rows)
    assert _load("extract-codex-transcript").inspect_transcript(path)["usage"]["measured"] is False


def test_codex_model_and_runtime_identity_are_not_caller_claims(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    document = {"target_skill": "demo:run-native", "actual_model": ["gpt-native"],
                "environment": {"runtime": "codex", "claude_version": None, "codex_version": "0.165.0",
                                "native_transcript_format": "codex-rollout-jsonl", "tmux": False},
                "overall": {"verdict": "PASS", "completion": "PASS"}}
    document["environment"].update({"permissions_mode": "workspace-write", "native_sandbox_contexts": _load("extract-codex-transcript").inspect_transcript(path)["sandbox_contexts"]})
    assert verdict_mod.validate_runtime_evidence(document, path, skill) == []
    document["actual_model"] = ["invented"]
    assert "native-actual-model-mismatch" in verdict_mod.validate_runtime_evidence(document, path, skill)
    document["environment"]["runtime"] = "claude"
    assert any("runtime-mismatch" in error for error in verdict_mod.validate_runtime_evidence(document, path, skill))


def test_codex_missing_model_is_not_accepted(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    rows = [row for row in map(json.loads, path.read_text().splitlines()) if row.get("type") != "turn_context"]
    _write_jsonl(path, rows)
    document = {"target_skill": "demo:run-native", "actual_model": [],
                "environment": {"runtime": "codex", "claude_version": None, "codex_version": "0.165.0",
                                "native_transcript_format": "codex-rollout-jsonl", "tmux": False},
                "overall": {"verdict": "PASS", "completion": "PASS"}}
    assert "native-actual-model-unmeasured" in verdict_mod.validate_runtime_evidence(document, path, skill)


def test_codex_native_surface_changes_only_codex_closure(tmp_path):
    plugin, skill = _behavior_closure_fixture(tmp_path)
    # fixture declares provider as its dependency; materialize a native manifest
    # for exactly the same roots, without changing their Claude surfaces.
    for root in plugin.parent.iterdir():
        manifest = root / ".claude-plugin/plugin.json"
        if not manifest.is_file():
            continue
        native = root / ".codex-plugin"
        native.mkdir()
        name = json.loads(manifest.read_text())["name"]
        (native / "plugin.json").write_text(json.dumps({"name": name, "version": "1", "hooks": "./codex/hooks.json"}))
        (root / "codex").mkdir()
        (root / "codex/hooks.json").write_text('{"hooks":{}}')
    claude = verdict_mod.skill_dir_tree_sha(skill)
    native = verdict_mod.skill_dir_tree_sha(skill, runtime="codex")
    assert native != claude
    (plugin / "codex/hooks.json").write_text('{"hooks":{"SessionStart":[]}}')
    assert verdict_mod.skill_dir_tree_sha(skill) == claude
    assert verdict_mod.skill_dir_tree_sha(skill, runtime="codex") != native


def test_codex_children_are_parent_bound_and_cumulative_usage_is_counted_once(tmp_path):
    path, _skill = _codex_rollout(tmp_path)
    rows = list(map(json.loads, path.read_text().splitlines()))
    rows[-1:-1] = [
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "spawn-1", "name": "spawn_agent", "arguments": "{}"}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "spawn-1", "output": json.dumps({"task_name": "/root/child"})}},
    ]
    _write_jsonl(path, rows)
    native = _load("extract-codex-transcript")
    assert "native-spawned-child-transcript-missing" in native.inspect_transcript(path)["format_errors"]
    child_dir = path.with_suffix("") / "subagents"
    child_dir.mkdir(parents=True)
    child = child_dir / "child.jsonl"
    child_rows = [json.loads(json.dumps(row)) for row in rows if row.get("payload", {}).get("call_id") != "spawn-1"]
    child_rows[0]["payload"].update({"id": "native-child", "parent_thread_id": "native-root", "agent_path": "/root/child"})
    _write_jsonl(child, child_rows)
    result = native.inspect_transcript(path)
    assert result["format_errors"] == []
    assert result["completed"] is True
    assert result["usage"]["total_tokens"] == 360
    assert result["usage"]["transcript_files"] == 2
    child_rows[0]["payload"]["parent_thread_id"] = "unrelated"
    _write_jsonl(child, child_rows)
    result = native.inspect_transcript(path)
    assert result["completed"] is False
    assert result["usage"]["measured"] is False


def test_codex_duplicate_usage_record_does_not_double_count(tmp_path):
    path, _skill = _codex_rollout(tmp_path)
    rows = list(map(json.loads, path.read_text().splitlines()))
    rows.insert(-1, {"type": "token_usage_record", "payload": {"thread_id": "native-root", "thread_token_usage": {"input_tokens": 150, "output_tokens": 30, "total_tokens": 180}}})
    _write_jsonl(path, rows)
    usage = _load("extract-codex-transcript").transcript_token_usage(path)
    assert usage["measured"] is True
    assert usage["total_tokens"] == 180


def _codex_inherited_child(tmp_path):
    """Native v2 paginated physical layout, not a rewritten acceptance log."""
    path, skill = _codex_rollout(tmp_path)
    parent = list(map(json.loads, path.read_text().splitlines()))
    meta = {"id": "native-child", "session_id": "native-root", "parent_thread_id": "native-root",
            "agent_path": "/root/child", "multi_agent_version": "v2", "history_mode": "paginated",
            "cwd": str(tmp_path), "cli_version": "0.165.0", "subagent_history_start_ordinal": len(parent) + 1}
    owned = [
        {"type":"event_msg", "payload":{"type":"thread_settings_applied", "thread_id":"native-child"}},
        {"type":"event_msg", "payload":{"type":"task_started", "turn_id":"child-turn"}},
        {"type":"turn_context", "payload":{"model":"gpt-child", "cwd":str(tmp_path)}},
        {"type":"token_usage_record", "payload":{"thread_id":"native-child", "thread_token_usage":{"input_tokens":20,"output_tokens":5,"total_tokens":25}}},
        {"type":"event_msg", "payload":{"type":"task_complete", "turn_id":"child-turn"}},
    ]
    rows = [{"type":"session_meta", "payload":meta}, *parent, *owned]
    for index, row in enumerate(rows): row["ordinal"] = index
    child = path.with_suffix("") / "subagents/child.jsonl"
    child.parent.mkdir(parents=True)
    _write_jsonl(child, rows)
    return path, skill, child, rows


def test_codex_v2_inherited_prefix_is_not_child_work_or_usage(tmp_path):
    path, skill, child, rows = _codex_inherited_child(tmp_path)
    raw = child.read_bytes()
    native = _load("extract-codex-transcript")
    one = native._inspect_one(child, skill_dir=skill, target_skill="demo:run-native")
    assert one["session_id"] == "native-child"
    assert one["models"] == ["gpt-child"]
    assert one["invoked_skills"] == []  # the parent's injection and Read are context only
    assert one["user_turns"] == []
    assert one["usage"]["total_tokens"] == 25
    assert one["history_projection"]["boundary_ordinal"] == rows[0]["payload"]["subagent_history_start_ordinal"]
    result = native.inspect_transcript(path)
    assert result["format_errors"] == []
    assert result["completed"] is True
    assert result["usage"]["measured"] is True
    assert result["usage"]["total_tokens"] == 205  # parent180 + owned child25, no inherited180 again
    assert child.read_bytes() == raw


@pytest.mark.parametrize("mutation", ["missing_boundary", "bool_boundary", "out_of_range", "wrong_version", "wrong_parent",
                                    "duplicate_ordinal", "missing_ordinal", "ordinal_gap", "wrong_boundary_thread",
                                    "own_meta", "history_base", "malformed_inherited_record"])
def test_codex_v2_ambiguous_or_invalid_history_never_selects_arbitrary_meta(tmp_path, mutation):
    path, _skill, child, rows = _codex_inherited_child(tmp_path)
    meta = rows[0]["payload"]; boundary = meta["subagent_history_start_ordinal"]
    if mutation == "missing_boundary": del meta["subagent_history_start_ordinal"]
    elif mutation == "bool_boundary": meta["subagent_history_start_ordinal"] = True
    elif mutation == "out_of_range": meta["subagent_history_start_ordinal"] = len(rows)
    elif mutation == "wrong_version": meta["multi_agent_version"] = "unknown"
    elif mutation == "wrong_parent": rows[1]["payload"]["id"] = "unrelated"
    elif mutation == "duplicate_ordinal": rows[3]["ordinal"] = 2
    elif mutation == "missing_ordinal": del rows[3]["ordinal"]
    elif mutation == "ordinal_gap": rows[3]["ordinal"] = 4
    elif mutation == "wrong_boundary_thread": rows[boundary]["payload"]["thread_id"] = "native-root"
    elif mutation == "own_meta": rows[-1] = {"ordinal":len(rows)-1, "type":"session_meta", "payload":{"id":"stray"}}
    elif mutation == "history_base": meta["history_base"] = {"end_ordinal_exclusive":7}
    elif mutation == "malformed_inherited_record": rows[3]["type"] = "unknown-native-record"
    _write_jsonl(child, rows)
    result = _load("extract-codex-transcript").inspect_transcript(path)
    assert result["format_errors"]
    assert result["completed"] is False
    assert result["usage"]["measured"] is False


@pytest.mark.parametrize("mutation", ["no_own_usage", "no_own_completion", "own_usage_wrong_thread"])
def test_codex_inherited_completion_and_usage_cannot_prove_child_success(tmp_path, mutation):
    path, _skill, child, rows = _codex_inherited_child(tmp_path)
    boundary = rows[0]["payload"]["subagent_history_start_ordinal"]
    if mutation == "no_own_usage":
        rows[boundary+3] = {"ordinal":boundary+3, "type":"event_msg", "payload":{"type":"agent_message", "message":"no usage"}}
    elif mutation == "no_own_completion": rows.pop()
    else: rows[boundary+3]["payload"]["thread_id"] = "native-root"
    _write_jsonl(child, rows)
    result = _load("extract-codex-transcript").inspect_transcript(path)
    if mutation == "no_own_completion": assert result["completed"] is False
    else: assert result["usage"]["measured"] is False


@pytest.mark.parametrize("complete,read_ok,expected", [(True, True, "PASS"), (False, True, "FAIL"), (True, False, "FAIL")])
def test_codex_verdict_uses_native_runtime_gates(tmp_path, complete, read_ok, expected):
    path, skill = _codex_rollout(tmp_path, complete=complete, read_ok=read_ok)
    work = tmp_path / "work"
    work.mkdir()
    shutil.copyfile(path, work / "transcript.jsonl")
    goal = {"result": "PASS", "blockers": [], "evaluator": {"mode": "fresh-independent-context", "id": "synthetic-independent-test"},
            "transcript_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "evidence_refs": ["transcript.jsonl"]}
    (work / "goal.json").write_text(json.dumps(goal))
    assert verdict_mod.main(["--workdir", str(work), "--target-skill", "demo:run-native", "--skill-dir", str(skill),
                             "--runtime", "codex", "--transcript", str(work / "transcript.jsonl"),
                             "--launch", "PASS", "--completion", "PASS", "--goal-evaluation", str(work / "goal.json")]) == 0
    document = json.loads((work / "verdict.json").read_text())
    assert document["overall"]["verdict"] == expected
    assert document["environment"]["runtime"] == "codex"
    assert document["environment"]["claude_version"] is None
    assert document["environment"]["tmux"] is False
    assert document["environment"]["codex_version"] == "0.165.0"


def test_codex_run_state_is_bound_to_actual_user_turns(tmp_path):
    path, _skill = _codex_rollout(tmp_path)
    info = _load("extract-codex-transcript").inspect_transcript(path)
    state = {"runtime": "codex", "session_id": "native-root", "collected": True,
             "writable_roots": [str(tmp_path)],
             "native_operation_turns": [], "responses": [],
             "turns": [{"number": 1, "stdin_sha256": info["user_turns"][0]["text_sha256"]}]}
    ledger = tmp_path / "native-run-state.json"
    ledger.write_text(json.dumps(state))
    metadata, errors = verdict_mod.native_run_metadata(tmp_path, ledger, info, nudge=0, gate=0)
    assert errors == []
    assert metadata["native_operation_turns"] == 0
    assert metadata["single_input_autonomous"] is True
    state["turns"][0]["stdin_sha256"] = "f" * 64
    ledger.write_text(json.dumps(state))
    metadata, errors = verdict_mod.native_run_metadata(tmp_path, ledger, info, nudge=0, gate=0)
    assert "native-run-state-execution-prompt-mismatch" in errors
    assert metadata["single_input_autonomous"] is False


def _native_info(tmp_path, turns):
    return {
        "session_id": "native-root",
        "completed": False,
        "sandbox_contexts": [{"writable_roots": [str(tmp_path)]}],
        "user_turns": turns,
    }


def test_terminated_unsubmitted_turn_is_classified_and_not_counted(tmp_path):
    """HARD_CAP / TOKEN_CAP で submitted にならなかった turn を未分類入力にしない。"""
    first, second = "a" * 64, "c" * 64
    info = _native_info(tmp_path, [
        {"text_sha256": first, "normalized_text_sha256": "b" * 64},
        {"text_sha256": second, "normalized_text_sha256": "d" * 64},
    ])
    state = {
        "runtime": "codex", "session_id": "native-root", "collected": True,
        "writable_roots": [str(tmp_path)], "responses": [],
        "turns": [
            {"number": 1, "stdin_sha256": first, "terminated": None, "native_turn_complete": True},
            {"number": 2, "stdin_sha256": second, "terminated": "TOKEN_CAP", "native_turn_complete": False},
        ],
        "native_operation_turns": [{
            "kind": "native-operation", "submitted": False, "native_turn": 2,
            "prompt_sha256": second, "target_skill": "demo:run-native", "args": "add",
        }],
    }
    ledger = tmp_path / "native-run-state.json"
    ledger.write_text(json.dumps(state))
    metadata, errors = verdict_mod.native_run_metadata(tmp_path, ledger, info, nudge=0, gate=0)
    assert "native-run-state-unclassified-user-turns" not in errors
    assert metadata["native_operation_turns"] == 0
    state["turns"][1]["terminated"] = None
    ledger.write_text(json.dumps(state))
    _, errors = verdict_mod.native_run_metadata(tmp_path, ledger, info, nudge=0, gate=0)
    assert "native-run-state-unclassified-user-turns" in errors


def test_blocked_reason_names_token_cap_separately_from_tmux(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--blocked", "--poll-exit", "TOKEN_CAP"])
    doc = json.loads(out.read_text())
    assert rc == 0
    assert doc["overall"]["verdict"] == "BLOCKED"
    assert doc["timeline"]["poll_exit"] == "TOKEN_CAP"
    assert "TOKEN_CAP" in doc["downgrade_reason"]
    assert "tmux" not in doc["downgrade_reason"]
    rc, out = _run_verdict(tmp_path, transcript, ["--blocked"])
    assert "tmux 不在" in json.loads(out.read_text())["downgrade_reason"]


def test_codex_pasted_skill_xml_without_native_provenance_is_not_activation(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    rows = list(map(json.loads, path.read_text().splitlines()))
    for row in rows:
        payload = row.get("payload", {})
        metadata = payload.get("internal_chat_message_metadata_passthrough", {})
        if "skills.selected_skill_instructions" in metadata.get("content_item_kinds", []):
            metadata["content_item_kinds"] = ["user.text"]
    _write_jsonl(path, rows)
    info = _load("extract-codex-transcript").inspect_transcript(path, skill_dir=skill, target_skill="demo:run-native")
    assert info["invoked_skills"] == []


def test_codex_sandbox_cannot_be_claimed_independently_of_raw_context(tmp_path):
    path, skill = _codex_rollout(tmp_path)
    info = _load("extract-codex-transcript").inspect_transcript(path)
    doc = {"target_skill": "demo:run-native", "actual_model": ["gpt-native"],
           "environment": {"runtime": "codex", "claude_version": None, "codex_version": "0.165.0", "tmux": False,
                           "native_transcript_format": "codex-rollout-jsonl", "permissions_mode": "danger-full-access",
                           "native_sandbox_contexts": info["sandbox_contexts"]},
           "overall": {"completion": "PASS", "verdict": "PASS"}}
    assert "native-sandbox-mode-unproven" in verdict_mod.validate_runtime_evidence(doc, path, skill)


# ---- 合成 transcript fixture -------------------------------------------------

def _write_jsonl(path: Path, entries: list[dict]) -> Path:
    for i, e in enumerate(entries):
        e.setdefault("timestamp", f"2026-07-02T00:00:{i:02d}Z")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return path


def _prompt(text="run the task"):
    return {"type": "user", "message": {"content": text}}


def _turn_end():
    return {"type": "system", "subtype": "turn_duration"}


def _tool_use(tid, name, tool_input=None):
    block = {"type": "tool_use", "id": tid, "name": name}
    if tool_input is not None:
        block["input"] = tool_input
    return {"type": "assistant", "message": {
        "model": "claude-opus-4-8",
        "content": [block]}}


def _tool_result(tid):
    return {"type": "user", "message": {
        "content": [{"type": "tool_result", "tool_use_id": tid}]}}


FIXTURES = {
    "waiting": [_prompt(), _tool_use("t1", "AskUserQuestion")],
    "busy_tool": [_prompt(), _tool_use("t2", "Bash")],
    "busy_gen": [_prompt()],
    "idle": [_prompt(), _tool_use("t3", "Bash"), _tool_result("t3"), _turn_end()],
}


# ---- live-trial-status: 4 状態分類 -------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("waiting", "WAITING_USER_INPUT"),
    ("busy_tool", "BUSY_TOOL_RUNNING"),
    ("busy_gen", "BUSY_GENERATING"),
    ("idle", "IDLE_TURN_COMPLETE"),
])
def test_status_four_states(tmp_path, name, expected):
    p = _write_jsonl(tmp_path / f"{name}.jsonl", [dict(e) for e in FIXTURES[name]])
    result = status_mod.classify(p)
    assert result["state"] == expected


def test_status_interrupt_is_turn_end(tmp_path):
    entries = [_prompt(), {"type": "user",
                           "message": {"content": "[Request interrupted by user]"}}]
    p = _write_jsonl(tmp_path / "int.jsonl", entries)
    assert status_mod.classify(p)["state"] == "IDLE_TURN_COMPLETE"


def test_status_missing_or_empty_returns_none(tmp_path):
    assert status_mod.classify(tmp_path / "nope.jsonl") is None
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert status_mod.classify(empty) is None
    # 全行 parse 不能も None (TUI fallback へ)
    garbage = tmp_path / "garbage.jsonl"
    garbage.write_text("not json at all\n", encoding="utf-8")
    assert status_mod.classify(garbage) is None


def test_status_subagent_bytes_aggregated(tmp_path):
    """fork 内長時間実行の STALL 誤報対策: subagents/*.jsonl bytes を合算する。"""
    p = _write_jsonl(tmp_path / "s.jsonl", [_prompt()])
    base = status_mod.transcript_bytes(p)
    sub = tmp_path / "s" / "subagents"
    sub.mkdir(parents=True)
    (sub / "a.jsonl").write_text("x" * 100, encoding="utf-8")
    assert status_mod.transcript_bytes(p) == base + 100


def test_status_cli_exit3_on_missing(tmp_path, capsys):
    assert status_mod.main([str(tmp_path / "none.jsonl")]) == 3
    p = _write_jsonl(tmp_path / "idle.jsonl", [dict(e) for e in FIXTURES["idle"]])
    assert status_mod.main([str(p)]) == 0
    out = capsys.readouterr().out
    assert "STATE:IDLE_TURN_COMPLETE" in out and "BYTES:" in out


# ---- live-trial-poll: 終端 4 分岐 + state-file --------------------------------

def _poll_env(monkeypatch, tmp_path, session_id="u-1", **env):
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setenv("SESSION_ID", session_id)
    defaults = {"INTERVAL": "0", "STABLE_TICKS": "2",
                "STALL_LIMIT": "600", "HARD_CAP": "7200"}
    defaults.update({k: str(v) for k, v in env.items()})
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)
    return projects


def test_poll_done(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text('{"status":"PASS"}', encoding="utf-8")
    rc = poll_mod.main([str(marker), "lt-test"])
    assert rc == poll_mod.EXIT_DONE
    assert "via jsonl" in capsys.readouterr().out


def test_poll_gate_after_two_ticks_and_resets(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["waiting"]])
    state_file = tmp_path / "state.json"
    rc = poll_mod.main(["--state-file", str(state_file),
                        str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_GATE
    assert "AskUserQuestion" in capsys.readouterr().out
    # 応答後の再 poll が即 GATE 再発しないよう gate_ticks=0 で永続化される
    assert json.loads(state_file.read_text())["gate_ticks"] == 0


def test_poll_stall_no_artifact(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1", STALL_LIMIT="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    rc = poll_mod.main([str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_STALL
    assert "成果物なし" in capsys.readouterr().out


def test_poll_hard_cap(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1", HARD_CAP="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["busy_gen"]])
    rc = poll_mod.main([str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_HARD_CAP
    out = capsys.readouterr().out
    assert "HARD_CAP" in out


def _scenario_file(tmp_path, *, wall=60, tokens=1000):
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps({
        "scenarios": [{
            "scenario_id": "bounded",
            "required_observations": ["bounded run completes"],
            "resource_budget": {
                "max_wall_clock_s": wall,
                "max_total_tokens": tokens,
            },
        }],
    }), encoding="utf-8")
    return path


def test_poll_scenario_wall_cap_cannot_be_raised_by_environment(
    monkeypatch, tmp_path, capsys
):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1", HARD_CAP="7200")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["busy_gen"]])
    rc = poll_mod.main([
        "--state-file", str(tmp_path / "poll-state.json"),
        "--scenario-file", str(_scenario_file(tmp_path, wall=1)),
        "--scenario-id", "bounded",
        str(tmp_path / "out" / "status.json"), "lt-test",
    ])
    assert rc == poll_mod.EXIT_HARD_CAP
    assert "1s 到達" in capsys.readouterr().out


def test_poll_scenario_token_cap_stops_immediately(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    transcript = projects / "u-1.jsonl"
    _write_jsonl(transcript, [{
        "type": "assistant",
        "message": {
            "id": "msg-1",
            "model": "claude-test",
            "content": [],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    }])
    rc = poll_mod.main([
        "--state-file", str(tmp_path / "poll-state.json"),
        "--scenario-file", str(_scenario_file(tmp_path, tokens=2)),
        "--scenario-id", "bounded",
        str(tmp_path / "out" / "status.json"), "lt-test",
    ])
    assert rc == poll_mod.EXIT_TOKEN_CAP
    assert "TOKEN_CAP (2 >= 2)" in capsys.readouterr().out


def test_poll_state_file_persists_counters(monkeypatch, tmp_path):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["busy_gen"]])
    state_file = tmp_path / "state.json"
    rc = poll_mod.main(["--state-file", str(state_file), "--max-ticks", "2",
                        str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_TICK_BUDGET
    st = json.loads(state_file.read_text())
    assert st["elapsed"] == 1  # 呼び越しで 0 に戻らない (STALL/HARD_CAP 実効の前提)
    assert st["prev"].startswith("jsonl:")
    # 同一 state-file の再呼びで elapsed が引き継がれ DONE に到達する
    # (trial 完了を模して jsonl を idle へ更新 — busy のままだと DONE 条件を満たさない)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text('{"status":"PASS"}', encoding="utf-8")
    monkeypatch.setenv("INTERVAL", "0")
    monkeypatch.setenv("STABLE_TICKS", "1")
    rc2 = poll_mod.main(["--state-file", str(state_file),
                         str(marker), "lt-test"])
    assert rc2 == poll_mod.EXIT_DONE
    assert json.loads(state_file.read_text())["elapsed"] >= 1


def test_poll_corrupt_state_file_fails_closed_without_reset(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    state_file = tmp_path / "state.json"
    state_file.write_text("{broken", encoding="utf-8")
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text("{}", encoding="utf-8")
    assert poll_mod.main(["--state-file", str(state_file),
                          str(marker), "lt-test"]) == poll_mod.EXIT_BLOCKED
    assert "STATE_CORRUPT" in capsys.readouterr().out


def test_poll_missing_usage_fails_closed(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [{
        "type": "assistant",
        "message": {"id": "msg-no-usage", "model": "claude-test", "content": []},
    }])
    rc = poll_mod.main([
        "--state-file", str(tmp_path / "poll-state.json"),
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--scenario-id", "bounded",
        str(tmp_path / "out" / "status.json"), "lt-test",
    ])
    assert rc == poll_mod.EXIT_BLOCKED
    assert "TOKEN_UNMEASURED" in capsys.readouterr().out


def test_scenario_poll_requires_persisted_state_file(monkeypatch, tmp_path):
    _poll_env(monkeypatch, tmp_path)
    with pytest.raises(SystemExit):
        poll_mod.main([
            "--scenario-file", str(_scenario_file(tmp_path)),
            "--scenario-id", "bounded",
            str(tmp_path / "out" / "status.json"), "lt-test",
        ])


def test_finalizer_reaps_even_when_verdict_fails():
    calls = []

    class Backend:
        @staticmethod
        def valid_session_name(value): return True
        @staticmethod
        def valid_run_id(value): return True
        @staticmethod
        def session_belongs_to_run(session, run_id): return True
        @staticmethod
        def reap(run_id, owner_pid): calls.append(("reap", run_id, owner_pid)); return []
        @staticmethod
        def has_session(session): return False

    class Verdict:
        @staticmethod
        def main(_args): raise SystemExit(2)

    rc = finalize_mod.finalize(
        session="lt-run-1", run_id="run-1", owner_pid=123,
        verdict_args=["--bad"], backend=Backend, verdict=Verdict,
    )
    assert rc == 2
    assert calls == [("reap", "run-1", 123)]


def test_finalizer_never_kills_session_when_tmux_ownership_mismatches():
    calls = []

    class Backend:
        valid_session_name = staticmethod(lambda _value: True)
        valid_run_id = staticmethod(lambda _value: True)
        session_belongs_to_run = staticmethod(lambda _session, _run_id: True)
        reap = staticmethod(lambda run_id, owner_pid: calls.append(("reap", run_id, owner_pid)) or [])
        has_session = staticmethod(lambda _session: True)

    class Verdict:
        main = staticmethod(lambda _args: 0)

    rc = finalize_mod.finalize(
        session="lt-run-1", run_id="run-1", owner_pid=123,
        verdict_args=["--ok"], backend=Backend, verdict=Verdict,
    )
    assert rc == 1
    assert calls == [("reap", "run-1", 123)]


# ---- live-trial-verdict: schema / tree sha / gate ----------------------------

def _fake_skill_dir(tmp_path: Path, *, gate_declared: bool = False) -> Path:
    d = tmp_path / "fake-skill"
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    # gate_declared=True は「契約上の確認 gate を持つ skill」を表す。contractual 免除は
    # この宣言に接地していなければ受理されない (自己申告での降格回避の遮断)。
    gate = "allowed-tools: [Read, AskUserQuestion]\n" if gate_declared else ""
    (d / "SKILL.md").write_text(f"---\nname: fake\n{gate}---\nbody\n", encoding="utf-8")
    (d / "scripts" / "a.py").write_text("print('a')\n", encoding="utf-8")
    return d


def _goal_evaluation_args(workdir: Path, transcript: Path, extra: list[str]) -> list[str]:
    """肯定 trial に要る、transcript へ束縛された独立 evaluator の証跡を作る。"""
    if "--goal-result" not in extra:
        return []
    workdir.mkdir(parents=True, exist_ok=True)
    goal_result = extra[extra.index("--goal-result") + 1]
    goal_blockers = [
        extra[index + 1]
        for index, value in enumerate(extra[:-1])
        if value == "--blocker"
    ]
    evidence = workdir / "evaluator-evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    goal_evaluation = workdir / "goal-evaluation.json"
    goal_evaluation.write_text(json.dumps({
        "result": goal_result,
        "blockers": goal_blockers,
        "evaluator": {
            "mode": "fresh-independent-context",
            "id": "pytest-live-trial-goal-evaluator",
        },
        "transcript_sha256": verdict_mod.sha256_file(transcript),
        "evidence_refs": ["evaluator-evidence.json"],
    }), encoding="utf-8")
    return ["--goal-evaluation", str(goal_evaluation)]


def _run_verdict(tmp_path, transcript: Path, extra: list[str],
                 *, gate_declared: bool = False) -> tuple[int, Path]:
    workdir = tmp_path / "workdir"
    goal_eval_args = _goal_evaluation_args(workdir, transcript, extra)
    skill_dir = _fake_skill_dir(tmp_path, gate_declared=gate_declared)
    argv = [
        "--workdir", str(workdir),
        "--target-skill", "some-plugin:run-something",
        "--skill-dir", str(skill_dir),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS",
        "--poll-exit", "DONE",
    ] + goal_eval_args + extra
    rc = verdict_mod.main(argv)
    return rc, workdir / "verdict.json"


@pytest.fixture()
def transcript(tmp_path):
    entries = [
        dict(_prompt()),
        dict(_tool_use("t8", "Skill", {"skill": "some-plugin:run-something"})),
        dict(_tool_result("t8")),
        dict(_tool_use("t9", "Bash")),
        dict(_tool_result("t9")),
        dict(_turn_end()),
    ]
    entries[1]["version"] = "2.1.173"
    return _write_jsonl(tmp_path / "src" / "u-9.jsonl", entries)


def test_verdict_pass_and_schema_valid(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--goal-result", "PASS"])
    assert rc == 0
    doc = json.loads(out.read_text())
    schema = json.loads(SCHEMA.read_text())
    assert verdict_mod.validate_schema(doc, schema) == []
    assert doc["overall"]["verdict"] == "PASS"
    assert doc["actual_model"] == ["claude-opus-4-8"]
    assert doc["environment"]["claude_version"] == "2.1.173"
    assert doc["environment"]["transcript_layer"] == "jsonl"
    assert doc["transcript_sha256"] and len(doc["transcript_sha256"]) == 64
    assert (tmp_path / "workdir" / "transcript.jsonl").is_file()


def test_verdict_goal_fail_degrades(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "FAIL", "--blocker", "成果物が目的を満たさない"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "goal-proxy" in doc["downgrade_reason"]


def test_verdict_nudge_degrades(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--nudge-count", "1"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "自走未達" in doc["downgrade_reason"]


def test_verdict_gate_rescue_degrades_by_default(tmp_path, transcript):
    """--gate-kind 未指定は rescue (fail-closed) — 既存の呼び出しが黙って緩まないこと。"""
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--gate-response-count", "1"])
    doc = json.loads(out.read_text())
    assert doc["gate_kind"] == "rescue"
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "自走未達" in doc["downgrade_reason"]


def test_verdict_gate_contractual_does_not_degrade(tmp_path, transcript):
    """契約上 gate を要求する skill は gate 応答があっても PASS を取れること。"""
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--gate-response-count", "1",
                            "--gate-kind", "contractual"], gate_declared=True)
    doc = json.loads(out.read_text())
    assert doc["gate_kind"] == "contractual"
    assert doc["gate_response_count"] == 1  # 免除しても回数は消えない
    assert doc["gate_contract_evidence"] == ["frontmatter.allowed-tools:AskUserQuestion"]
    assert doc["overall"]["verdict"] == "PASS"
    assert doc["downgrade_reason"] is None


def test_verdict_contractual_without_declaration_is_rejected(tmp_path, transcript):
    """gate 宣言の無い skill の contractual 申告は fail-closed で拒否されること。

    無検証で受理すると、stall 救済を contractual と言い換えるだけで
    DEGRADED を PASS へ反転できる (受け入れ基準の自己申告による緩和)。
    """
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--gate-response-count", "1",
                            "--gate-kind", "contractual"])
    assert rc == 2
    assert not out.exists()  # 拒否した実行は verdict を残さない


def test_verdict_contractual_grounds_on_external_mutation_guard(tmp_path, transcript):
    """external_mutation_guard 宣言も契約 gate の接地根拠として認めること。"""
    skill_dir = tmp_path / "fake-skill"
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        '---\nname: fake\nexternal_mutation_guard: {flow: "preview-confirm-authorize-execute-v1"}\n---\nbody\n',
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "a.py").write_text("print('a')\n", encoding="utf-8")
    extra = ["--goal-result", "PASS", "--gate-response-count", "1",
             "--gate-kind", "contractual"]
    rc = verdict_mod.main([
        "--workdir", str(tmp_path / "workdir"),
        "--target-skill", "some-plugin:run-something",
        "--skill-dir", str(skill_dir),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS", "--poll-exit", "DONE",
    ] + _goal_evaluation_args(tmp_path / "workdir", transcript, extra) + extra)
    assert rc == 0
    doc = json.loads((tmp_path / "workdir" / "verdict.json").read_text())
    assert doc["gate_contract_evidence"] == ["frontmatter.external_mutation_guard"]
    assert doc["overall"]["verdict"] == "PASS"


def test_verdict_gate_kind_normalized_to_rescue_without_gate_response(tmp_path, transcript):
    """gate 応答 0 のとき kind は意味を持たないので rescue へ正規化されること。"""
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--gate-kind", "contractual"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["gate_kind"] == "rescue"
    assert "gate_contract_evidence" not in doc


def test_verdict_proof_rejects_contractual_gate(tmp_path, transcript):
    """proof trial の受け入れ条件は「人手介入なし」— 契約 gate も介入として FAIL。"""
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--gate-response-count", "1",
                            "--gate-kind", "contractual", "--proof",
                            "--requested-model", "claude-opus-4-8"], gate_declared=True)
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "FAIL"
    assert "proof trial" in doc["downgrade_reason"]


def test_verdict_nudge_degrades_even_with_contractual_gate(tmp_path, transcript):
    """契約 gate の免除は gate 応答だけに効き、nudge (救済介入) は免除しないこと。"""
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--nudge-count", "1",
                            "--gate-kind", "contractual"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "nudge=1" in doc["downgrade_reason"]


def test_verdict_proof_model_gate(tmp_path, transcript):
    # transcript の actual は claude-opus-4-8 — requested と不一致なら proof は FAIL
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--proof",
                            "--requested-model", "claude-sonnet-5"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "FAIL"
    assert "proof" in doc["downgrade_reason"]
    # 一致すれば PASS
    rc2, out2 = _run_verdict(tmp_path, transcript,
                             ["--goal-result", "PASS", "--proof",
                              "--requested-model", "claude-opus-4-8"])
    assert json.loads(out2.read_text())["overall"]["verdict"] == "PASS"


def test_verdict_blocked_fail_closed(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--blocked"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "BLOCKED"
    assert doc["overall"]["goal_fit"] == "NOT_EVALUATED"
    assert doc["goal_verdict"]["blockers"]  # 未実施の blocker が自動記録される


def test_verdict_denylist_rejected(tmp_path, transcript, capsys):
    workdir = tmp_path / "wd"
    rc = verdict_mod.main([
        "--workdir", str(workdir),
        "--target-skill", "harness-creator:run-skill-live-trial",
        "--skill-dir", str(_fake_skill_dir(tmp_path)),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS",
    ])
    assert rc == 2
    assert "DENYLIST" in capsys.readouterr().err


# ---- live-trial-verdict: 被験 skill 起動 gate と goal_seek 配線 gate ----------

def test_verdict_fails_when_the_target_skill_was_never_invoked(tmp_path):
    """被験 skill を起動せず script を直接叩いた実走は launch=FAIL になる。

    2026-07-21 live-trial r14 の C05 (render) は Skill 呼出しが transcript に0件のまま
    render-graph-html.py を Bash から直接実行し、成果物が出たため PASS を自己申告した。
    起動の有無を orchestrator の --launch ではなく transcript の機械判定へ移す。
    """
    entries = [dict(_prompt()), dict(_tool_use("t1", "Bash")),
               dict(_tool_result("t1")), dict(_turn_end())]
    src = _write_jsonl(tmp_path / "src" / "no-skill.jsonl", entries)

    rc, out = _run_verdict(tmp_path, src, ["--goal-result", "PASS"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert verdict_mod.validate_schema(doc, json.loads(SCHEMA.read_text())) == []
    assert doc["invoked_skills"] == []
    assert doc["overall"]["launch"] == "FAIL"
    assert doc["overall"]["verdict"] == "FAIL"
    assert any("Skill 呼出しが transcript に0件" in b for b in doc["goal_verdict"]["blockers"])


def test_verdict_accepts_a_trial_that_invoked_the_target_skill(tmp_path):
    """target skill を起動した実走は従来どおり通り、invoked_skills に記録される。"""
    entries = [dict(_prompt()),
               dict(_tool_use("t1", "Skill", {"skill": "some-plugin:run-something"})),
               dict(_tool_result("t1")),
               dict(_tool_use("t2", "Skill", {"skill": "other-plugin:run-helper"})),
               dict(_tool_result("t2")), dict(_turn_end())]
    src = _write_jsonl(tmp_path / "src" / "with-skill.jsonl", entries)

    rc, out = _run_verdict(tmp_path, src, ["--goal-result", "PASS"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["invoked_skills"] == ["other-plugin:run-helper", "some-plugin:run-something"]
    assert doc["overall"]["launch"] == "PASS"
    assert doc["overall"]["verdict"] == "PASS"


def _goal_seek_skill_dir(tmp_path: Path) -> Path:
    """goal_seek を宣言した被験 skill (実行契約として配線成果物を要求する)。"""
    d = tmp_path / "run-something"
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: run-something\ncombinators:\n  - with-goal-seek\n"
        "goal_seek:\n  engine: inline\n  fork: subagent\n  max_loops: 5\n---\nbody\n",
        encoding="utf-8",
    )
    (d / "scripts" / "a.py").write_text("print('a')\n", encoding="utf-8")
    return d


def _run_verdict_with_skill_dir(
    tmp_path, transcript: Path, skill_dir: Path, extra: list[str], eval_root: Path | None = None
):
    workdir = tmp_path / "workdir"
    goal_eval_args = _goal_evaluation_args(workdir, transcript, extra)
    argv = [
        "--workdir", str(workdir),
        "--target-skill", "some-plugin:run-something",
        "--skill-dir", str(skill_dir),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS",
        "--poll-exit", "DONE",
    ]
    if eval_root is not None:
        argv.extend(["--goal-seek-eval-root", str(eval_root)])
    argv.extend(goal_eval_args)
    argv.extend(extra)
    return verdict_mod.main(argv), workdir / "verdict.json"


def _skill_invocation_entries():
    return [dict(_prompt()),
            dict(_tool_use("s1", "Skill", {"skill": "some-plugin:run-something"})),
            dict(_tool_result("s1"))]


def test_verdict_flags_missing_goal_seek_wiring(tmp_path):
    """goal_seek を宣言した skill が配線成果物を残さない実走を機械検出する。

    2026-07-21 の live-trial r13/r14 では 7 skill で goal-spec.json / progress.json /
    intermediate.jsonl が一つも生成されず、SKILL.md の実行契約が一律に省略されていた。
    fresh evaluator の目視ではなく transcript の書込み記録で判定する。
    """
    entries = _skill_invocation_entries() + [dict(_tool_use("t1", "Bash")),
                                             dict(_tool_result("t1")), dict(_turn_end())]
    src = _write_jsonl(tmp_path / "src" / "no-wiring.jsonl", entries)
    eval_root = tmp_path / "eval-log"
    eval_root.mkdir()

    rc, out = _run_verdict_with_skill_dir(
        tmp_path,
        src,
        _goal_seek_skill_dir(tmp_path),
        ["--goal-result", "PASS"],
        eval_root,
    )
    assert rc == 0
    doc = json.loads(out.read_text())
    assert verdict_mod.validate_schema(doc, json.loads(SCHEMA.read_text())) == []
    assert set(doc["missing_goal_seek_artifacts"]) == {
        "goal-spec.json", "progress.json", "intermediate.jsonl"}
    # evaluator が PASS を返しても機械 gate が勝つ (fail-closed)
    assert doc["overall"]["goal_fit"] == "FAIL"
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert any("ゴールシーク配線" in b for b in doc["goal_verdict"]["blockers"])


def test_verdict_accepts_complete_goal_seek_wiring(tmp_path):
    """3 種の配線成果物が実在し、内容も整合する実走は gate を通る。"""
    entries = _skill_invocation_entries() + [dict(_turn_end())]
    src = _write_jsonl(tmp_path / "src" / "wired.jsonl", entries)
    eval_root = tmp_path / "eval-log"
    eval_root.mkdir()
    goal = "target skill の目的を最後まで達成する"
    goal_hash = hashlib.sha256(goal.encode("utf-8")).hexdigest()
    (eval_root / "run-something-goal-spec.json").write_text(
        json.dumps({"original_goal": goal}), encoding="utf-8"
    )
    (eval_root / "run-something-progress.json").write_text(
        json.dumps({"checklist": ["done"]}), encoding="utf-8"
    )
    (eval_root / "run-something-intermediate.jsonl").write_text(
        json.dumps(
            {
                "original_goal": goal,
                "original_goal_hash": goal_hash,
                "current_goal_snapshot": goal,
                "delta_from_original": "none",
                "merged_directive_for_next": "continue",
                "drift_signal": "none",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rc, out = _run_verdict_with_skill_dir(
        tmp_path,
        src,
        _goal_seek_skill_dir(tmp_path),
        ["--goal-result", "PASS"],
        eval_root,
    )
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["missing_goal_seek_artifacts"] == []
    assert doc["goal_seek_evidence_violations"] == []
    assert doc["overall"]["verdict"] == "PASS"


def test_verdict_rejects_goal_seek_files_with_invalid_content(tmp_path):
    """ファイル名だけ揃えたダミー成果物は goal_seek 履行の証拠にしない。"""
    entries = _skill_invocation_entries() + [dict(_turn_end())]
    src = _write_jsonl(tmp_path / "src" / "invalid-wiring.jsonl", entries)
    eval_root = tmp_path / "eval-log"
    eval_root.mkdir()
    (eval_root / "run-something-goal-spec.json").write_text(
        json.dumps({"original_goal": "goal"}), encoding="utf-8"
    )
    (eval_root / "run-something-progress.json").write_text("{}", encoding="utf-8")
    (eval_root / "run-something-intermediate.jsonl").write_text("{}\n", encoding="utf-8")

    rc, out = _run_verdict_with_skill_dir(
        tmp_path,
        src,
        _goal_seek_skill_dir(tmp_path),
        ["--goal-result", "PASS"],
        eval_root,
    )
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["goal_seek_evidence_violations"]
    assert doc["overall"]["goal_fit"] == "FAIL"


def test_verdict_skips_wiring_gate_when_skill_does_not_declare_goal_seek(tmp_path, transcript):
    """goal_seek 非宣言の skill には配線 gate を適用しない (過剰適用の防止)。"""
    rc, out = _run_verdict(tmp_path, transcript, ["--goal-result", "PASS"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["missing_goal_seek_artifacts"] == []
    assert doc["overall"]["verdict"] == "PASS"


def test_tree_sha_deterministic_and_content_sensitive(tmp_path):
    d1 = _fake_skill_dir(tmp_path / "a")
    d2 = _fake_skill_dir(tmp_path / "b")
    sha1 = verdict_mod.skill_dir_tree_sha(d1)
    assert sha1 == verdict_mod.skill_dir_tree_sha(d1)  # 決定論
    assert sha1 == verdict_mod.skill_dir_tree_sha(d2)  # 同内容 → 同 sha
    (d2 / "scripts" / "a.py").write_text("print('b')\n", encoding="utf-8")
    assert sha1 != verdict_mod.skill_dir_tree_sha(d2)  # 内容変更で変わる


def _write_package_contract(
    plugin_dir: Path, depends_on: list[str], *, skills: list[str] | None = None,
    skill_dependencies: dict[str, list[str]] | None = None,
) -> Path:
    path = plugin_dir / "references" / "package-contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "plugin_name": plugin_dir.name,
        "depends_on": depends_on,
        "entry_points": {
            "skills": skills or [],
            "agents": [],
            "commands": [],
            "hooks": [],
        },
    }
    if skill_dependencies is not None:
        document["skill_dependencies"] = skill_dependencies
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _behavior_closure_fixture(tmp_path: Path) -> tuple[Path, Path]:
    plugin_dir = _write_trial_plugin(
        tmp_path, "dev-graph", "dev-graph", skill_name="run-behavior"
    )
    dependency = _write_trial_plugin(
        tmp_path, "system-spec-harness", "system-spec-harness", skill_name="run-delegate"
    )
    _write_package_contract(plugin_dir, ["system-spec-harness"])
    _write_package_contract(dependency, [], skills=["run-delegate"])
    skill_dir = plugin_dir / "skills" / "run-behavior"
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "local.py").write_text("print('local')\n", encoding="utf-8")
    (skill_dir / "prompts").mkdir()
    (skill_dir / "prompts" / "R0.md").write_text("prompt-v1\n", encoding="utf-8")
    (plugin_dir / "scripts").mkdir()
    (plugin_dir / "scripts" / "shared.py").write_text("print('shared')\n", encoding="utf-8")
    (plugin_dir / "references" / "contract.md").write_text("contract-v1\n", encoding="utf-8")
    (plugin_dir / "hooks").mkdir()
    (plugin_dir / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
    (dependency / "hooks").mkdir()
    (dependency / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: run-behavior\n"
        "script_refs: [../../scripts/shared.py]\n"
        "reference_refs:\n"
        "  - ../../references/contract.md\n"
        "responsibility_refs: [prompts/R0.md]\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    return plugin_dir, skill_dir


@pytest.mark.parametrize("relative_path", [
    "prompts/R0.md",
    "../../scripts/shared.py",
    "../../references/contract.md",
    "../../hooks/hooks.json",
    "../../.claude-plugin/plugin.json",
])
def test_tree_sha_binds_declared_behavior_closure(tmp_path, relative_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    path = (skill_dir / relative_path).resolve()
    if path.name == "plugin.json":
        # manifest が closure に入っていることの確認は、release メタではなく挙動に
        # 効くキーで行う。version で確かめると、下の
        # test_tree_sha_ignores_manifest_release_metadata が守る性質
        # (bump では stale にしない) と要求が正面衝突する。
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["hooks"] = "./hooks/hooks.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        path.write_text(path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_ignores_manifest_release_metadata(tmp_path):
    """version bump だけでは verdict を stale にしない。

    build-plugin-release は plugin に内容変更があれば必ず version を上げる。生の
    manifest を digest に入れていると「どんな変更でも version が動く」→「その
    plugin の全 skill の verdict が一斉に stale」になり、再 trial の要求が挙動変更
    の signal ではなく release 作業の副作用として出る。巻き添えの stale は本物の
    stale と区別がつかないので、検査そのものが痩せる。
    """
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    path = (skill_dir / "../../.claude-plugin/plugin.json").resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = "9.9.9"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before


def _commit_tree(repo: Path) -> None:
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo, check=True, env=env)


def test_closure_drift_names_behavior_files_and_skips_version(tmp_path):
    """stale の説明は挙動ファイルだけを名指しする。version bump は digest と同じく無視する。"""
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    _commit_tree(tmp_path)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True,
    ).strip()
    manifest_path = (skill_dir / "../../.claude-plugin/plugin.json").resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "9.9.9"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    labels = verdict_mod.closure_drift_labels(tmp_path, skill_dir, commit)
    assert labels == ["plugins/dev-graph/skills/run-behavior/SKILL.md"]
    assert "plugin.json" not in verdict_mod.format_closure_drift(labels)
    assert "SKILL.md" in verdict_mod.format_stale_sha("a" * 64, "b" * 64, labels)


def test_tree_sha_ignores_dependency_manifest_release_metadata(tmp_path):
    """依存 plugin 側の bump も同じ。巻き添えの範囲は依存を辿って更に広い。"""
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    path = tmp_path / "plugins" / "system-spec-harness" / ".claude-plugin" / "plugin.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = "9.9.9"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before


def test_tree_sha_keeps_unknown_manifest_keys_in_the_closure(tmp_path):
    """未知のキーは digest に残す (fail-closed)。

    除外を allowlist で書くと、manifest に新しいキーが増えたとき digest に出ず、
    挙動が変わったのに verdict が緑のまま通る。除外は「挙動でないと言い切れる
    キー」の denylist に限る。
    """
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    path = (skill_dir / "../../.claude-plugin/plugin.json").resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["someFutureBehaviorKey"] = {"loads": "extra"}
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_binds_declared_dependency_manifest_and_hooks(tmp_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    dependency = tmp_path / "plugins" / "system-spec-harness"
    (dependency / "hooks" / "hooks.json").write_text('{"changed":true}\n', encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_binds_declared_dependency_skill_behavior(tmp_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    dependency_skill = (
        tmp_path / "plugins" / "system-spec-harness" / "skills"
        / "run-delegate" / "SKILL.md"
    )
    dependency_skill.write_text("---\nname: run-delegate\n---\nchanged\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_ignores_ephemeral_tool_caches(tmp_path):
    """ツールが残す一時 cache で digest が動くと stale 判定が実行履歴に依存する。

    CI は clone 直後なので cache が無く、ローカルで pytest を回した後だけ落ちる
    という非対称を生むため、closure は出荷バイト列だけを見る。
    """
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    dependency = tmp_path / "plugins" / "system-spec-harness" / "skills" / "run-delegate"
    for relative in (
        ".pytest_cache/v/cache/nodeids",
        ".ruff_cache/content",
        "__pycache__/mod.cpython-313.pyc",
    ):
        noise = dependency / relative
        noise.parent.mkdir(parents=True, exist_ok=True)
        noise.write_text("noise\n", encoding="utf-8")
    (dependency / ".DS_Store").write_text("noise\n", encoding="utf-8")
    (skill_dir / "scripts" / "local.pyc").write_text("noise\n", encoding="utf-8")

    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before


def test_tree_sha_resolves_declared_repo_root_relative_ref(tmp_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    repo_ref = tmp_path / "doc" / "notion-schema" / "contract.md"
    repo_ref.parent.mkdir(parents=True)
    repo_ref.write_text("repo-contract-v1\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: run-behavior\n"
        "reference_refs: [doc/notion-schema/contract.md]\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    repo_ref.write_text("repo-contract-v2\n", encoding="utf-8")

    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_prefers_skill_relative_ref_over_repo_root_ref(tmp_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    relative = Path("doc/notion-schema/contract.md")
    repo_ref = tmp_path / relative
    skill_ref = skill_dir / relative
    repo_ref.parent.mkdir(parents=True)
    skill_ref.parent.mkdir(parents=True)
    repo_ref.write_text("repo-contract-v1\n", encoding="utf-8")
    skill_ref.write_text("skill-contract-v1\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: run-behavior\n"
        "reference_refs: [doc/notion-schema/contract.md]\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    repo_ref.write_text("repo-contract-v2\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before

    skill_ref.write_text("skill-contract-v2\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_ignores_dependency_outside_skill_scope(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-behavior"],
        skill_dependencies={},
    )
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    dependency_skill = (
        tmp_path / "plugins" / "system-spec-harness" / "skills"
        / "run-delegate" / "SKILL.md"
    )
    dependency_skill.write_text("---\nname: run-delegate\n---\nchanged\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before


def test_tree_sha_ignores_other_skills_package_contract_projection(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-behavior", "run-other"],
        skill_dependencies={"run-behavior": []},
    )
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-behavior", "run-other"],
        skill_dependencies={
            "run-behavior": [],
            "run-other": ["system-spec-harness"],
        },
    )
    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before


def test_tree_sha_rejects_missing_and_symlink_escape_refs(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\nscript_refs: [scripts/missing.py]\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing"):
        verdict_mod.skill_dir_tree_sha(skill_dir)

    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("unsafe\n", encoding="utf-8")
    (plugin_dir / "scripts" / "escape.py").symlink_to(outside)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\nscript_refs: [../../scripts/escape.py]\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="escapes repository"):
        verdict_mod.skill_dir_tree_sha(skill_dir)

    (plugin_dir / "scripts" / "escape.py").unlink()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\nscript_refs: [../../scripts/shared.py]\n---\n",
        encoding="utf-8",
    )
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-dir"
    outside_dir.mkdir()
    (plugin_dir / "hooks" / "escape-dir").symlink_to(
        outside_dir, target_is_directory=True
    )
    with pytest.raises(ValueError, match="escapes repository"):
        verdict_mod.skill_dir_tree_sha(skill_dir)


def test_tree_sha_rejects_undeclared_cross_plugin_ref(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    extra = _write_trial_plugin(tmp_path, "undeclared", "undeclared", skill_name="run-x")
    (extra / "references").mkdir()
    (extra / "references" / "behavior.md").write_text("external\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\n"
        "reference_refs: [../../../undeclared/references/behavior.md]\n"
        "---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not declared"):
        verdict_mod.skill_dir_tree_sha(skill_dir)
    _write_package_contract(extra, [], skills=["run-x"])
    _write_package_contract(plugin_dir, ["system-spec-harness", "undeclared"])
    assert len(verdict_mod.skill_dir_tree_sha(skill_dir)) == 64


def test_schema_rejects_additional_properties(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--goal-result", "PASS"])
    doc = json.loads(out.read_text())
    schema = json.loads(SCHEMA.read_text())
    doc["extra_key"] = 1
    errs = verdict_mod.validate_schema(doc, schema)
    assert any("additionalProperties" in e for e in errs)
    del doc["extra_key"]
    del doc["timeline"]
    errs = verdict_mod.validate_schema(doc, schema)
    assert any("timeline" in e for e in errs)


# ---- plan-live-trials: incremental evidence reuse / bounded dispatch ---------

def _planner_plugin(tmp_path: Path, skills: list[str]) -> Path:
    plugin_dir = tmp_path / "plugins" / "sample-plugin"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "sample-plugin"}), encoding="utf-8"
    )
    (plugin_dir / ".codex-plugin").mkdir()
    (plugin_dir / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "sample-plugin"}), encoding="utf-8"
    )
    for skill in skills:
        skill_dir = plugin_dir / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill}\nkind: run\nallowed-tools: [Read, Skill]\n---\nbody\n",
            encoding="utf-8",
        )
    _write_package_contract(plugin_dir, [], skills=skills, skill_dependencies={})
    return plugin_dir


def _write_reusable_verdict(eval_root: Path, plugin_dir: Path, skill: str) -> Path:
    run_dir = eval_root / plugin_dir.name / skill / "live-trial" / "20260713T000000"
    run_dir.mkdir(parents=True)
    transcript = run_dir / "transcript.jsonl"
    transcript.write_text('{"type":"system","subtype":"turn_duration"}\n', encoding="utf-8")
    transcript_sha = planner_mod._sha256(transcript)
    behavior_sha = verdict_mod.skill_dir_tree_sha(plugin_dir / "skills" / skill)
    verdict = {
        "target_skill": f"{plugin_dir.name}:{skill}",
        "args": "",
        "requested_model": "",
        "actual_model": ["claude-test"],
        "nudge_count": 0,
        "gate_response_count": 0,
        "gate_kind": "rescue",
        "goal_verdict": {"result": "PASS", "blockers": []},
        "overall": {
            "launch": "PASS", "completion": "PASS", "goal_fit": "PASS",
            "verdict": "PASS",
        },
        "skill_dir_tree_sha": behavior_sha,
        "transcript_sha256": transcript_sha,
        "scenario_origin": "synthetic",
        "scenario_id": f"{skill}-positive",
        "environment": {
            "claude_version": "test", "tmux": True,
            "transcript_layer": "jsonl", "permissions_mode": "test",
        },
        "tier": "live",
        "downgrade_reason": None,
        "timeline": {"boot_s": 1, "poll_exit": "DONE", "wall_clock_s": 2},
    }
    path = run_dir / "verdict.json"
    path.write_text(json.dumps(verdict), encoding="utf-8")
    return path


def test_incremental_plan_reuses_current_pass_and_bounds_new_runs(tmp_path):
    skills = ["run-a", "run-b", "run-c"]
    plugin_dir = _planner_plugin(tmp_path, skills)
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental",
        max_live_trials=1, max_concurrency=2,
    )
    actions = {record["skill"]: record["action"] for record in plan["skills"]}
    assert actions == {"run-a": "reuse", "run-b": "run", "run-c": "defer"}
    assert plan["live_batches"] == [["run-b"]]
    assert plan["counts"] == {"static": 0, "fork": 0, "reuse": 1, "run": 1, "defer": 1}
    assert plan["skills"][0]["reused_evidence"] == str(evidence)


def test_incremental_plan_invalidates_evidence_on_behavior_change(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    with (plugin_dir / "skills" / "run-a" / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("changed\n")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental",
        max_live_trials=1, max_concurrency=1,
    )
    assert [record["action"] for record in plan["skills"]] == ["run", "defer"]
    assert plan["skills"][0]["reason"] == "behavior-changed"


def _receipt(eval_root: Path, plugin: str, skill: str, ref: str, body: str | None = None) -> None:
    path = eval_root / plugin / skill / "criteria-test" / "scenario-verdict.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if body is not None else json.dumps({
        "criteria_results": {
            "OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": ref},
        },
    }), encoding="utf-8")


def test_receipt_pass_is_reused_ahead_of_newer_blocked(tmp_path):
    """新しい BLOCKED は、receipt が指す current PASS を再利用対象から外さない。"""
    plugin_dir = _planner_plugin(tmp_path, ["run-a"])
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    newer = evidence.parent.parent / "20260714T000000"
    newer.mkdir()
    blocked = json.loads(evidence.read_text(encoding="utf-8"))
    blocked["overall"]["verdict"] = "BLOCKED"
    blocked["downgrade_reason"] = "TOKEN_CAP: scenario の token 予算到達 (fail-closed)"
    blocked["timeline"]["poll_exit"] = "TOKEN_CAP"
    (newer / "verdict.json").write_text(json.dumps(blocked), encoding="utf-8")
    ref = "eval-log/sample-plugin/run-a/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-a", ref)

    plan = planner_mod.build_plan(plugin_dir, eval_root, profile="incremental", max_live_trials=1)
    record = plan["skills"][0]
    assert record["action"] == "reuse"
    assert record["reused_evidence"] == str(evidence)


def test_stale_receipt_reports_behavior_change_not_newer_pass(tmp_path):
    """receipt の PASS が古いとき、より新しい current PASS へ黙って乗り換えない。"""
    plugin_dir = _planner_plugin(tmp_path, ["run-a"])
    eval_root = tmp_path / "eval-log"
    accepted = _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    stale_doc = json.loads(accepted.read_text(encoding="utf-8"))
    stale_doc["skill_dir_tree_sha"] = "0" * 64
    accepted.write_text(json.dumps(stale_doc), encoding="utf-8")
    fresh = accepted.parent.parent / "20260714T000000"
    fresh.mkdir()
    current = json.loads(accepted.read_text(encoding="utf-8"))
    current["skill_dir_tree_sha"] = verdict_mod.skill_dir_tree_sha(plugin_dir / "skills" / "run-a")
    (fresh / "verdict.json").write_text(json.dumps(current), encoding="utf-8")
    (fresh / "transcript.jsonl").write_text(
        accepted.parent.joinpath("transcript.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    ref = "eval-log/sample-plugin/run-a/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-a", ref)

    plan = planner_mod.build_plan(plugin_dir, eval_root, profile="incremental", max_live_trials=1)
    record = plan["skills"][0]
    assert record["action"] == "run"
    assert record["reason"] == "behavior-changed"
    assert record["reused_evidence"] is None


def test_corrupt_receipt_is_not_replaced_by_another_pass(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    _receipt(eval_root, "sample-plugin", "run-a", "unused", body="{")

    plan = planner_mod.build_plan(plugin_dir, eval_root, profile="refresh")
    record = plan["skills"][0]
    assert record["action"] == "defer"
    assert record["reason"].startswith("criteria-receipt-invalid-json")
    assert plan["live_batches"] == []


def test_behavior_changed_is_scheduled_before_missing_evidence(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-b")
    with (plugin_dir / "skills" / "run-b" / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("changed\n")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental", max_live_trials=1,
    )
    by_skill = {record["skill"]: record for record in plan["skills"]}
    assert by_skill["run-b"]["action"] == "run"
    assert by_skill["run-b"]["reason"] == "behavior-changed"
    assert by_skill["run-a"]["action"] == "defer"
    assert by_skill["run-a"]["evidence_reason"] == "missing-evidence"
    assert by_skill["run-a"]["reason"] == "live-budget-exhausted:1"
    assert plan["live_batches"] == [["run-b"]]


def test_refresh_runs_every_nonreusable_skill_and_keeps_current_pass(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b", "run-c"])
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    _write_reusable_verdict(eval_root, plugin_dir, "run-b")
    with (plugin_dir / "skills" / "run-b" / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("changed\n")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="refresh", max_live_trials=0,
    )
    actions = {record["skill"]: record["action"] for record in plan["skills"]}
    assert actions == {"run-a": "reuse", "run-b": "run", "run-c": "run"}
    assert plan["skills"][0]["reused_evidence"] == str(evidence)
    assert plan["policy"]["max_live_trials"] is None
    assert plan["live_batches"] == [["run-b", "run-c"]]


def test_behavior_drift_names_files_for_stale_receipt(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a"])
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    ref = "eval-log/sample-plugin/run-a/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-a", ref)
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=tmp_path, check=True, env=env)
    skill_md = plugin_dir / "skills" / "run-a" / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    plan = planner_mod.build_plan(plugin_dir, eval_root, profile="refresh")
    record = plan["skills"][0]
    assert record["reason"] == "behavior-changed"
    assert record["behavior_drift"] == ["plugins/sample-plugin/skills/run-a/SKILL.md"]
    assert evidence.name == "verdict.json"


def test_refresh_reuses_claude_receipt_when_plan_runtime_is_codex(tmp_path):
    """受領が Claude で current なら、Codex の refresh は再実走しない。"""
    plugin_dir = _planner_plugin(tmp_path, ["run-a"])
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    ref = "eval-log/sample-plugin/run-a/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-a", ref)

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="refresh", runtime="codex",
    )
    record = plan["skills"][0]
    assert record["action"] == "reuse"
    assert record["runtime"] == "claude"
    assert record["reused_evidence"] == str(evidence)


def test_incremental_does_not_reuse_current_pass_across_runtime(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    ref = "eval-log/sample-plugin/run-a/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-a", ref)

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental", runtime="codex",
    )
    record = plan["skills"][0]
    assert record["action"] == "run"
    assert record["reason"] == "runtime-mismatch"
    assert record["runtime"] == "codex"
    assert record["acceptance_runtime"] == "claude"
    assert "behavior_drift" not in record


def test_cross_runtime_stale_keeps_behavior_priority(tmp_path):
    """runtime が違っても、受領閉包の stale は欠測より先に実走する。"""
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    accepted = _write_reusable_verdict(eval_root, plugin_dir, "run-b")
    stale = json.loads(accepted.read_text(encoding="utf-8"))
    stale["skill_dir_tree_sha"] = "0" * 64
    accepted.write_text(json.dumps(stale), encoding="utf-8")
    ref = "eval-log/sample-plugin/run-b/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-b", ref)

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental", runtime="codex", max_live_trials=1,
    )
    by_skill = {record["skill"]: record for record in plan["skills"]}
    assert by_skill["run-b"]["action"] == "run"
    assert by_skill["run-b"]["reason"] == "behavior-changed"
    assert by_skill["run-b"]["runtime"] == "codex"
    assert by_skill["run-b"]["acceptance_runtime"] == "claude"
    assert by_skill["run-a"]["action"] == "defer"
    assert by_skill["run-a"]["evidence_reason"] == "missing-evidence"


def test_refresh_reruns_stale_receipt_on_its_own_runtime(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    ref = "eval-log/sample-plugin/run-a/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-a", ref)
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=tmp_path, check=True, env=env)
    skill_md = plugin_dir / "skills" / "run-a" / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="refresh", runtime="codex", max_concurrency=2,
    )
    by_skill = {record["skill"]: record for record in plan["skills"]}
    assert by_skill["run-a"]["action"] == "run"
    assert by_skill["run-a"]["reason"] == "behavior-changed"
    assert by_skill["run-a"]["runtime"] == "claude"
    assert by_skill["run-a"]["behavior_drift"] == [
        "plugins/sample-plugin/skills/run-a/SKILL.md",
    ]
    assert by_skill["run-b"]["action"] == "run"
    assert by_skill["run-b"]["runtime"] == "codex"
    assert by_skill["run-b"]["reason"] == "missing-evidence"
    assert plan["live_batches"] == [["run-a"], ["run-b"]]
    assert evidence.name == "verdict.json"


def test_refresh_reuses_codex_receipt_when_plan_runtime_is_claude(tmp_path, monkeypatch):
    """native 検査は別テストの責務。ここでは受領 runtime の採用だけを見る。"""
    plugin_dir = _planner_plugin(tmp_path, ["run-a"])
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    document = json.loads(evidence.read_text(encoding="utf-8"))
    document["environment"] = {
        "claude_version": None,
        "tmux": False,
        "transcript_layer": "jsonl",
        "permissions_mode": "test",
        "runtime": "codex",
        "codex_version": "0.0.0-test",
        "native_transcript_format": "codex-rollout-jsonl",
    }
    document["skill_dir_tree_sha"] = verdict_mod.skill_dir_tree_sha(
        plugin_dir / "skills" / "run-a", runtime="codex",
    )
    evidence.write_text(json.dumps(document), encoding="utf-8")
    ref = "eval-log/sample-plugin/run-a/live-trial/20260713T000000/verdict.json"
    _receipt(eval_root, "sample-plugin", "run-a", ref)
    real_load = planner_mod._load_sibling

    def wrapped(name):
        module = real_load(name)
        if name == "live-trial-verdict":
            module.validate_runtime_evidence = lambda *_args, **_kwargs: []
        return module

    monkeypatch.setattr(planner_mod, "_load_sibling", wrapped)
    refreshed = planner_mod.build_plan(
        plugin_dir, eval_root, profile="refresh", runtime="claude",
    )
    record = refreshed["skills"][0]
    assert record["action"] == "reuse"
    assert record["runtime"] == "codex"
    assert record["reused_evidence"] == str(evidence)

    incremental = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental", runtime="claude",
    )
    blocked = incremental["skills"][0]
    assert blocked["action"] == "run"
    assert blocked["reason"] == "runtime-mismatch"
    assert blocked["runtime"] == "claude"
    assert blocked["acceptance_runtime"] == "codex"


def test_exhaustive_plan_explicitly_reruns_current_evidence(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="exhaustive",
        max_live_trials=0, max_concurrency=1,
    )
    assert [record["action"] for record in plan["skills"]] == ["run", "run"]
    assert plan["policy"]["max_live_trials"] is None
    assert plan["live_batches"] == [["run-a"], ["run-b"]]


def test_build_only_plan_never_schedules_live_session(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="build-only",
        max_live_trials=9, max_concurrency=9,
    )
    assert [record["action"] for record in plan["skills"]] == ["defer", "defer"]
    assert {record["reason"] for record in plan["skills"]} == {
        "not-run(profile=build-only)"
    }
    assert plan["live_batches"] == []
    assert plan["policy"]["max_live_trials"] == 0


# ---- backend / boot / send: オフライン検査 ------------------------------------

@pytest.fixture(autouse=True)
def boot_test_cli(monkeypatch, tmp_path, request):
    """boot のoffline検査は実際のClaude install/PATHに依存させない。"""
    if not request.node.name.startswith("test_boot_"):
        return None
    executable = tmp_path / "claude"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    original_which = shutil.which
    monkeypatch.setattr(
        boot_mod.shutil, "which",
        lambda command: str(executable) if command == "claude" else original_which(command),
    )
    return executable.resolve()


def test_boot_executable_is_fixed_before_tmux(monkeypatch, boot_test_cli, tmp_path):
    explicit = tmp_path / "native CLI"
    explicit.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    explicit.chmod(0o700)
    argv = boot_mod.build_claude_argv("u-1", "model-1")
    pinned = boot_mod.build_claude_argv("u-1", "model-1", claude_executable=str(explicit))
    assert argv[0] == str(boot_test_cli)
    assert pinned[0] == str(explicit.resolve())
    assert pinned[1:] == argv[1:]
    assert backend_mod.shlex.split(boot_mod.build_claude_command(
        "u-1", "model-1", claude_executable=str(explicit),
    )) == list(pinned)
    monkeypatch.setattr(boot_mod.shutil, "which", lambda _command: "/wrong/tmux/claude")
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["❯ "], ["claude"])
    assert boot_mod.boot(
        fb, "lt-x", "x", str(tmp_path), "model-1", "u-1", 1, 0,
        claude_executable=str(explicit),
    ) == 0
    assert fb.argv == pinned


@pytest.mark.parametrize("kind", ["relative", "missing", "directory", "not-executable", "newline", "nul"])
def test_boot_rejects_invalid_cli_before_session(tmp_path, monkeypatch, kind):
    candidate = tmp_path / "invalid-cli"
    if kind == "relative":
        value = "claude"
    elif kind in {"newline", "nul"}:
        value = str(candidate) + ("\n--dangerously-skip-permissions" if kind == "newline" else "\x00")
    else:
        value = str(candidate)
        if kind == "directory":
            candidate.mkdir()
        elif kind == "not-executable":
            candidate.write_text("text", encoding="utf-8")
            candidate.chmod(0o600)
    fb = FakeBootBackend([], [])
    with pytest.raises(ValueError):
        boot_mod.boot(fb, "lt-x", "x", str(tmp_path), "", "u-1", 1, 0,
                      claude_executable=value)
    assert fb.argv is None
    assert fb.killed == []
    assert boot_mod.main([
        "lt-x", str(tmp_path), "--run-id", "x", "--claude-executable", value,
    ]) == 2


def test_boot_missing_caller_cli_is_rejected(monkeypatch):
    monkeypatch.setattr(boot_mod.shutil, "which", lambda _command: None)
    with pytest.raises(ValueError, match="caller PATH"):
        boot_mod.build_claude_argv("u-1", "")


def test_boot_main_forwards_validated_explicit_cli(monkeypatch, tmp_path, boot_test_cli):
    calls = []
    monkeypatch.setattr(boot_mod, "_load_sibling", lambda _name: backend_mod)
    monkeypatch.setattr(backend_mod, "require_tmux", lambda: None)
    monkeypatch.setattr(boot_mod, "boot", lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
    assert boot_mod.main([
        "lt-x", str(tmp_path), "--run-id", "x", "--model", "model-1",
        "--session-id", "u-1", "--claude-executable", str(boot_test_cli),
    ]) == 0
    assert len(calls) == 1
    assert calls[0][1]["claude_executable"] == str(boot_test_cli)
    assert calls[0][1]["plugin_dir"] == ()
    assert calls[0][0][4:6] == ("model-1", "u-1")


def test_boot_explicit_cli_symlink_pins_resolved_file(tmp_path):
    link = tmp_path / "selected-cli"
    link.symlink_to(sys.executable)
    assert boot_mod.resolve_claude_executable(str(link)) == str(Path(sys.executable).resolve())
    link.unlink()
    link.symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError):
        boot_mod.resolve_claude_executable(str(link))

def test_backend_denylist_and_session_names():
    assert backend_mod.deny_target_skill("run-skill-live-trial")
    assert backend_mod.deny_target_skill("harness-creator:run-skill-iter-improve")
    assert not backend_mod.deny_target_skill("harness-creator:run-goal-seek")
    assert backend_mod.valid_session_name("lt-20260702T000000-x")
    assert not backend_mod.valid_session_name("../evil")
    assert not backend_mod.valid_session_name("a/b")


def test_backend_blocked_without_tmux(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    with pytest.raises(SystemExit) as exc:
        backend_mod.require_tmux()
    assert exc.value.code == 3


def test_backend_self_test_cli():
    assert backend_mod.main(["--self-test"]) == 0
    assert backend_mod.main(["deny-check", "harness-creator:run-goal-seek"]) == 0
    assert backend_mod.main(["deny-check", "run-skill-live-trial"]) == 2


def test_boot_denylist_and_validation(tmp_path, capsys):
    assert boot_mod.main(["--self-test"]) == 0
    rc = boot_mod.main(["lt-x", str(tmp_path),
                        "--run-id", "x",
                        "--target-skill", "run-skill-iter-improve"])
    assert rc == 2
    assert "DENYLIST" in capsys.readouterr().err
    assert boot_mod.main(["../evil", str(tmp_path), "--run-id", "x"]) == 2
    assert boot_mod.main([
        "lt-x", str(tmp_path / "missing"), "--run-id", "x"
    ]) == 2
    assert boot_mod.main([
        "lt-x", str(tmp_path), "--run-id", "x", "--model", "bad model;rm"
    ]) == 2
    assert boot_mod.main([
        "lt-x", str(tmp_path), "--run-id", "x",
        "--session-id", "bad; touch /tmp/injected"
    ]) == 2
    assert boot_mod.main(["lt-x", str(tmp_path)]) == 2
    assert "missing run-id" in capsys.readouterr().err
    assert boot_mod.main([
        "lt-other", str(tmp_path), "--run-id", "x"
    ]) == 2


def test_boot_audit_ledger_stays_inside_trial_repo(tmp_path):
    ledger = tmp_path / "eval-log" / "system-spec-harness" / "audit-fork-ledger.jsonl"
    assert boot_mod.resolve_audit_fork_ledger(str(ledger), str(tmp_path)) == str(ledger)
    assert boot_mod.resolve_audit_fork_ledger(
        "eval-log/system-spec-harness/audit-fork-ledger.jsonl", str(tmp_path)
    ) == str(ledger)
    with pytest.raises(ValueError, match="escapes trial repo"):
        boot_mod.resolve_audit_fork_ledger("/tmp/audit-fork-ledger.jsonl", str(tmp_path))
    with pytest.raises(ValueError, match="filename"):
        boot_mod.resolve_audit_fork_ledger("eval-log/other.jsonl", str(tmp_path))


def _write_trial_plugin(
    root: Path, directory_name: str, manifest_name: str,
    skill_name: str = "run-dev-graph-init",
) -> Path:
    plugin_dir = root / "plugins" / directory_name
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": manifest_name}), encoding="utf-8"
    )
    skill_dir = plugin_dir / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\ndescription: fixture\n---\n", encoding="utf-8")
    return plugin_dir


def test_boot_qualified_target_pins_cwd_plugin_dir(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    resolved = boot_mod.resolve_target_plugin_dir(
        str(tmp_path), "dev-graph:run-dev-graph-init"
    )
    assert resolved == plugin_dir.resolve()
    argv = boot_mod.build_claude_argv("u-1", "", resolved)
    assert argv[-2:] == ("--plugin-dir", str(plugin_dir.resolve()))
    assert argv[argv.index("--setting-sources") + 1] == "local"
    assert boot_mod.resolve_target_plugin_dir(str(tmp_path), "plain-skill") is None
    assert "--plugin-dir" not in boot_mod.build_claude_argv("u-1", "")


def test_boot_qualified_target_loads_only_declared_dependencies(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    dep_b = _write_trial_plugin(tmp_path, "system-spec-harness", "system-spec-harness")
    dep_a = _write_trial_plugin(tmp_path, "system-dev-planner", "system-dev-planner")
    undeclared = _write_trial_plugin(tmp_path, "other-plugin", "other-plugin")
    _write_package_contract(plugin_dir, ["system-spec-harness", "system-dev-planner"])

    resolved = boot_mod.resolve_target_plugin_dirs(
        str(tmp_path), "dev-graph:run-dev-graph-init"
    )
    assert resolved == (plugin_dir.resolve(), dep_a.resolve(), dep_b.resolve())
    assert undeclared.resolve() not in resolved
    argv = boot_mod.build_claude_argv("u-1", "", resolved)
    loaded = [argv[index + 1] for index, value in enumerate(argv) if value == "--plugin-dir"]
    assert loaded == [str(path) for path in resolved]


def test_boot_qualified_target_honors_per_skill_dependency_scope(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    second = plugin_dir / "skills" / "run-dev-graph-system-spec"
    second.mkdir(parents=True)
    (second / "SKILL.md").write_text("---\ndescription: fixture\n---\n", encoding="utf-8")
    dependency = _write_trial_plugin(
        tmp_path, "system-spec-harness", "system-spec-harness"
    )
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-dev-graph-init", "run-dev-graph-system-spec"],
        skill_dependencies={
            "run-dev-graph-system-spec": ["system-spec-harness"],
        },
    )

    init_dirs = boot_mod.resolve_target_plugin_dirs(
        str(tmp_path), "dev-graph:run-dev-graph-init"
    )
    system_spec_dirs = boot_mod.resolve_target_plugin_dirs(
        str(tmp_path), "dev-graph:run-dev-graph-system-spec"
    )
    assert init_dirs == (plugin_dir.resolve(),)
    assert system_spec_dirs == (plugin_dir.resolve(), dependency.resolve())


def test_boot_rejects_skill_dependency_outside_package_allow_list(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    _write_package_contract(
        plugin_dir,
        [],
        skills=["run-dev-graph-init"],
        skill_dependencies={"run-dev-graph-init": ["undeclared-plugin"]},
    )
    with pytest.raises(ValueError, match="subset of depends_on"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


def test_boot_declared_dependency_fails_closed_on_missing_or_manifest_mismatch(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    _write_package_contract(plugin_dir, ["system-spec-harness"])
    with pytest.raises(ValueError, match="directory not found"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )
    _write_trial_plugin(tmp_path, "system-spec-harness", "wrong-name")
    with pytest.raises(ValueError, match="manifest name mismatch"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


def test_boot_declared_dependency_rejects_symlink_escape(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    _write_package_contract(plugin_dir, ["system-spec-harness"])
    outside = _write_trial_plugin(
        tmp_path / "outside-root", "system-spec-harness", "system-spec-harness"
    )
    (tmp_path / "plugins" / "system-spec-harness").symlink_to(
        outside, target_is_directory=True
    )
    with pytest.raises(ValueError, match="escapes cwd/plugins"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


@pytest.mark.parametrize("target", [
    "../evil:run-safe",
    "Dev_Graph:run-safe",
    "dev-graph:../run-safe",
    "dev-graph:run-safe:extra",
])
def test_boot_qualified_target_rejects_invalid_slug_or_path(tmp_path, target):
    with pytest.raises(ValueError):
        boot_mod.resolve_target_plugin_dir(str(tmp_path), target)


def test_boot_qualified_target_rejects_symlink_escape(tmp_path):
    outside = _write_trial_plugin(tmp_path / "outside-root", "outside", "escape")
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes cwd/plugins"):
        boot_mod.resolve_target_plugin_dir(str(tmp_path), "escape:run-safe")


def test_boot_qualified_target_rejects_manifest_name_mismatch(tmp_path):
    _write_trial_plugin(tmp_path, "dev-graph", "different-plugin")
    with pytest.raises(ValueError, match="manifest name mismatch"):
        boot_mod.resolve_target_plugin_dir(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


def test_boot_qualified_target_rejects_missing_plugin(tmp_path):
    with pytest.raises(ValueError, match="directory not found"):
        boot_mod.resolve_target_plugin_dir(
            str(tmp_path), "missing-plugin:run-safe"
        )


def test_boot_qualified_target_rejects_missing_skill_in_pinned_plugin(tmp_path):
    _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    with pytest.raises(ValueError, match="target skill not found"):
        boot_mod.resolve_target_plugin_dir(
            str(tmp_path), "dev-graph:run-missing"
        )


def test_send_usage_errors(tmp_path, capsys):
    assert send_mod.main(["../evil", str(tmp_path / "task.md")]) == 2
    assert send_mod.main(["lt-x", str(tmp_path / "missing.md")]) == 2


def test_send_jsonl_accept_detection(tmp_path):
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True)
    task = tmp_path / "task.md"
    task.write_text("do it", encoding="utf-8")
    line = json.dumps({"type": "user", "message": {"content": f"読んで実行: {task}"}})
    (projects / "u-2.jsonl").write_text(line + "\n", encoding="utf-8")
    assert send_mod.jsonl_accepted(str(tmp_path / "projects"), "u-2", str(task))
    assert not send_mod.jsonl_accepted(str(tmp_path / "projects"), "u-404", str(task))


# ---- fake backend による tmux 経路の網羅 (実 tmux 非依存) ----------------------

class FakeSendBackend:
    """live-trial-send.main が触る backend 面だけを実装する fake。"""

    def __init__(self, cap=""):
        self.cap = cap
        self.enters = 0
        self.pasted = ""

    def valid_session_name(self, s):
        return backend_mod.valid_session_name(s)

    def require_tmux(self):
        pass

    def paste_file(self, _session, path):
        self.pasted = Path(path).read_text(encoding="utf-8")

    def send_keys(self, _session, *_keys):
        self.enters += 1

    def capture_pane(self, _session, scrollback=False):
        return self.cap


def test_send_started_via_tui_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    monkeypatch.delenv("SESSION_ID", raising=False)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    fb = FakeSendBackend(cap="✻ … (5s · 120 tokens)")
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 0
    # 指示行はファイル経由 (paste) で送られ、taskfile の絶対パスを含む
    assert str(task.resolve()) in fb.pasted


def test_send_unconfirmed_retries_then_warn(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    monkeypatch.delenv("SESSION_ID", raising=False)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    fb = FakeSendBackend(cap="")  # 着手マーカーなし
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 1
    assert fb.enters == 3  # Enter 再送は 3 回で打ち切り
    assert "WARN" in capsys.readouterr().out


def test_send_jsonl_primary_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True)
    line = json.dumps({"type": "user",
                       "message": {"content": f"読んで実行: {task.resolve()}"}})
    (projects / "u-3.jsonl").write_text(line + "\n", encoding="utf-8")
    monkeypatch.setenv("SESSION_ID", "u-3")
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(tmp_path / "projects"))
    fb = FakeSendBackend(cap="")  # TUI は無反応でも jsonl 一次判定で確定する
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 0


class FakeBootBackend:
    """live-trial-boot.boot が触る backend 面だけを実装する fake。"""

    def __init__(self, captures, cmds):
        self.captures = captures
        self.cmds = cmds
        self.tick = 0
        self.killed = []
        self.sent = ""
        self.argv = None
        self.run_id = None
        self.environment_overrides = None
        self.send_calls = 0
        self.key_sends = []

    def new_session(
        self, _s, _c, command_argv=None, *, run_id, owner_pid,
        environment_overrides=None,
    ):
        self.argv = command_argv
        self.run_id = run_id
        self.owner_pid = owner_pid
        self.environment_overrides = environment_overrides
        if command_argv:
            self.sent = " ".join(command_argv)

    def send_line(self, _s, text):
        self.send_calls += 1
        self.sent = text

    def send_keys(self, _s, *keys):
        self.key_sends.append(tuple(keys))

    def capture_pane(self, _s, scrollback=False):
        return self.captures[min(self.tick, len(self.captures) - 1)]

    def pane_current_command(self, _s):
        v = self.cmds[min(self.tick, len(self.cmds) - 1)]
        self.tick += 1
        return v

    def kill_session(self, s):
        self.killed.append(s)


def test_boot_ready_line_contract(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    monkeypatch.setenv(
        "SYSTEM_SPEC_AUDIT_FORK_LEDGER", "/tmp/current-session-ledger.jsonl"
    )
    fb = FakeBootBackend(["Type /help for shortcuts\n❯ "], ["2.1.173"])
    explicit_ledger = "/tmp/fixture/eval-log/system-spec-harness/audit-fork-ledger.jsonl"
    rc = boot_mod.boot(fb, "lt-x", "x", "/tmp", "claude-opus-4-8", "u-1",
                       timeout=5, grace=1, audit_fork_ledger=explicit_ledger)
    assert rc == 0
    out = capsys.readouterr().out
    # SESSION_ID: は行末固定 (parse 互換) / MODEL: は requested の echo
    assert "READY: lt-x" in out
    assert out.strip().endswith("SESSION_ID:u-1")
    assert "MODEL:claude-opus-4-8" in out
    assert "--model claude-opus-4-8" in fb.sent
    assert "--setting-sources local" in fb.sent
    assert fb.argv == boot_mod.build_claude_argv("u-1", "claude-opus-4-8")
    assert fb.environment_overrides["SYSTEM_SPEC_AUDIT_FORK_LEDGER"] == explicit_ledger
    assert fb.run_id == "x"
    assert f"OWNER_PID:{fb.owner_pid}" in out
    assert fb.send_calls == 0  # 対話 shell への send-line を経由しない
    assert fb.key_sends == []


def _bypass_gate(*, native=False, selected="no"):
    no = "No, exit" if native else "1. No, exit"
    yes = "Yes, I accept" if native else "2. Yes, I accept"
    return "\n".join([
        boot_mod._BYPASS_CONFIRM_MARKERS[0],
        ("❯ " if selected == "no" else "  ") + no,
        ("❯ " if selected == "yes" else "  ") + yes,
        "Enter to confirm · Esc to cancel",
    ])


@pytest.mark.parametrize("native", [False, True])
def test_boot_accepts_exact_bypass_gate_once_then_waits_for_prompt(monkeypatch, capsys, native):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    gate = _bypass_gate(native=native)
    fb = FakeBootBackend(
        [gate, _bypass_gate(native=native, selected="yes"),
         "Welcome to Claude Code\nType /help for shortcuts\n❯ "],
        ["claude", "claude", "claude"],
    )
    rc = boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", timeout=4, grace=1)
    assert rc == 0
    assert fb.key_sends == [("Down",), ("Enter",)]
    assert "READY: lt-x (2s)" in capsys.readouterr().out


def test_boot_accepts_native_warning_with_real_wrapped_body(monkeypatch):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    gate = _bypass_gate(native=True).replace(
        "\n❯ No, exit",
        "\n\n  In Bypass Permissions mode, Claude Code will not ask for your approval before running potentially dangerous commands.\n"
        "  This mode should only be used in a sandboxed container/VM that has restricted internet access and can easily be restored if damaged.\n\n"
        "  By proceeding, you accept all responsibility for actions taken while running in Bypass Permissions mode.\n\n"
        "  https://code.claude.com/docs/en/security\n\n  ❯ No, exit",
    )
    selected = gate.replace("❯ No, exit", "  No, exit").replace("  Yes, I accept", "❯ Yes, I accept")
    fb = FakeBootBackend([gate, selected, "❯\u00a0Try something"], ["claude"])
    assert boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", 2, 0) == 0
    assert fb.key_sends == [("Down",), ("Enter",)]


def test_boot_ready_regex_matches_real_nbsp_try_prompt_not_numbered_gate():
    real_prompt = '❯\u00a0Try "how do I log an error?"'
    assert boot_mod._READY_RE.search(real_prompt)
    assert boot_mod._READY_RE.search("❯   ")
    assert not boot_mod._READY_RE.search("❯ 1. Yes, I trust this folder")
    assert not boot_mod._READY_RE.search("❯\u00a01. No, exit")


@pytest.mark.parametrize("native", [False, True])
def test_boot_never_repeats_bypass_gate_acceptance(monkeypatch, capsys, native):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend([
        _bypass_gate(native=native), _bypass_gate(native=native, selected="yes"),
        _bypass_gate(native=native),
    ], ["claude"])
    rc = boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", timeout=3, grace=1)
    assert rc == 1
    assert fb.key_sends == [("Down",), ("Enter",)]
    assert "TIMEOUT" in capsys.readouterr().out


@pytest.mark.parametrize("replacement", [
    "unchanged", "unknown", "mixed-format", "shell", "ready-without-selection",
])
def test_boot_never_confirms_without_matching_selection(monkeypatch, replacement):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    selected = _bypass_gate(selected="yes")
    command = "claude"
    if replacement == "unchanged":
        selected = _bypass_gate()
    elif replacement == "unknown":
        selected = selected.replace("Yes, I accept", "Continue")
    elif replacement == "mixed-format":
        selected = _bypass_gate(native=True, selected="yes")
    elif replacement == "shell":
        command = "zsh"
    else:
        selected = "❯ "
    fb = FakeBootBackend([_bypass_gate(), selected], ["claude", command])
    assert boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", timeout=2, grace=0) == 1
    assert fb.key_sends == [("Down",)]
    assert fb.killed == ["lt-x"]


@pytest.mark.parametrize("gate", [
    _bypass_gate().replace("2. Yes, I accept", "Yes, I accept"),
    _bypass_gate().replace("❯ 1. No, exit", "1. No, exit"),
    _bypass_gate().replace("2. Yes, I accept", "❯ 2. Yes, I accept"),
    _bypass_gate(selected="yes"),
    _bypass_gate().replace("Yes, I accept", "Yes, continue"),
    _bypass_gate().replace("Enter to confirm", "Press Enter"),
    _bypass_gate().replace("  2. Yes, I accept", "  2. Yes, I accept\n  3. Other"),
    _bypass_gate().replace("❯ 1. No, exit", "❯ 2. Yes, I accept").replace("  2. Yes, I accept", "  1. No, exit"),
    _bypass_gate().replace(boot_mod._BYPASS_CONFIRM_MARKERS[0], "Do you trust this folder?"),
])
def test_boot_never_answers_nearby_or_ambiguous_gate(monkeypatch, gate):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend([gate], ["claude"])
    assert boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", 1, 0) == 1
    assert fb.key_sends == []
    assert fb.killed == ["lt-x"]


@pytest.mark.parametrize("command", sorted(boot_mod._SHELL_BLACKLIST))
def test_boot_never_answers_gate_from_shell(monkeypatch, command):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend([_bypass_gate()], [command])
    assert boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", 1, 0) == 1
    assert fb.key_sends == []
    assert fb.killed == ["lt-x"]


def test_boot_does_not_report_ready_while_bypass_warning_remains(monkeypatch):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend([_bypass_gate(selected="yes") + "\nfor shortcuts"], ["claude"])
    assert boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", 1, 0) == 1
    assert fb.key_sends == []


def test_boot_does_not_answer_non_exact_gate(monkeypatch):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    partial = (
        "WARNING: Claude Code running in Bypass Permissions mode\n"
        "1. No, exit\n2. Continue\nEnter to confirm"
    )
    fb = FakeBootBackend([partial], ["claude"])
    assert boot_mod.boot(
        fb, "lt-x", "x", "/tmp", "", "u-1", timeout=1, grace=1
    ) == 1
    assert fb.key_sends == []


def test_boot_fail_when_claude_dies(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["zsh: command not found: claude"], ["zsh"])
    rc = boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", timeout=5, grace=0)
    assert rc == 1
    assert "BOOT_FAIL" in capsys.readouterr().out
    assert fb.killed == ["lt-x"]  # 失敗経路でも session を掃除する


def test_boot_timeout_no_ready(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["still starting"], ["2.1.173"])
    rc = boot_mod.boot(fb, "lt-x", "x", "/tmp", "", "u-1", timeout=2, grace=1)
    assert rc == 1
    assert "TIMEOUT" in capsys.readouterr().out
    assert fb.killed == ["lt-x"]


def test_backend_tmux_wrappers_with_fake_subprocess(monkeypatch, tmp_path):
    calls = []

    class CP:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, capture_output=True, text=True, check=False):
        calls.append(list(args))
        cp = CP()
        if args[1] == "list-sessions" and "\t" in args[-1]:
            cp.stdout = (
                "lt-run-a-one\trun-a\t111\n"
                "lt-run-a-sibling\trun-a\t222\n"
                "lt-run-a-spoof\trun-b\t222\n"
                "lt-run-a-unowned\t\t\n"
                "lt-run-b-one\trun-b\t222\n"
                "other\t\t\n"
            )
        elif args[1] == "list-sessions":
            cp.stdout = (
                "lt-run-a-one\n"
                "lt-run-a-sibling\n"
                "lt-run-a-spoof\n"
                "lt-run-a-unowned\n"
                "lt-run-b-one\n"
                "other\n"
            )
        elif args[1] == "list-panes":
            cp.stdout = "claude\n"
        elif args[1] == "capture-pane":
            cp.stdout = "pane output\n"
        return cp

    monkeypatch.setattr(backend_mod.shutil, "which", lambda _c: "/usr/bin/tmux")
    monkeypatch.setattr(backend_mod.subprocess, "run", fake_run)

    backend_mod.new_session("lt-x", str(tmp_path), run_id="x", owner_pid=111)
    backend_mod.new_session(
        "lt-direct", str(tmp_path), run_id="direct", owner_pid=111,
        command_argv=("printf", "%s", "safe; touch /tmp/not-created"),
        environment_overrides={
            "SYSTEM_SPEC_AUDIT_FORK_LEDGER": "/tmp/current ledger.jsonl",
        },
    )
    backend_mod.send_line("lt-x", "hello")
    backend_mod.paste_text("lt-x", "task body\nwith newline")
    assert backend_mod.capture_pane("lt-x", scrollback=True) == "pane output\n"
    assert backend_mod.has_session("lt-x")
    assert backend_mod.pane_current_command("lt-x") == "claude"
    assert backend_mod.reap("run-a", 111) == ["lt-run-a-one"]
    with pytest.raises(ValueError, match="run_id"):
        backend_mod.reap()
    with pytest.raises(ValueError, match="owner_pid"):
        backend_mod.reap("run-a")
    assert backend_mod.reap(all_sessions=True) == [
        "lt-run-a-one",
        "lt-run-a-sibling",
        "lt-run-a-spoof",
        "lt-run-a-unowned",
        "lt-run-b-one",
    ]
    kill_calls = [c for c in calls if c[:2] == ["tmux", "kill-session"]]
    assert len(kill_calls) >= 8  # new_session 前掃除 2 + scoped 1 + explicit all 5
    option_calls = [c for c in calls if c[:2] == ["tmux", "set-option"]]
    assert ["tmux", "set-option", "-t", "lt-x", "@lt_run_id", "x"] in option_calls
    assert [
        "tmux", "set-option", "-t", "lt-x", "@lt_owner_pid", "111"
    ] in option_calls
    # paste は session/file 固有 named buffer を load → paste → delete する。
    flat = [c[1] for c in calls]
    assert {"load-buffer", "paste-buffer", "delete-buffer"} <= set(flat)
    load_call = next(c for c in calls if c[1] == "load-buffer")
    paste_call = next(c for c in calls if c[1] == "paste-buffer")
    delete_call = next(c for c in calls if c[1] == "delete-buffer")
    assert load_call[2] == "-b"
    assert paste_call[2:4] == ["-b", load_call[3]]
    assert delete_call[2:4] == ["-b", load_call[3]]
    assert backend_mod.valid_buffer_name(load_call[3])
    assert len(load_call[3]) <= backend_mod._BUFFER_NAME_MAX
    direct = next(c for c in calls if c[1:5] == ["new-session", "-d", "-s", "lt-direct"])
    env_index = direct.index("-e")
    assert direct[env_index + 1] == (
        "SYSTEM_SPEC_AUDIT_FORK_LEDGER=/tmp/current ledger.jsonl"
    )
    assert direct[-1] == "printf %s 'safe; touch /tmp/not-created'"
    # CLI dispatch も同じ境界を通る
    assert backend_mod.main([
        "new-session", "lt-y", str(tmp_path), "--run-id", "y"
    ]) == 0
    assert backend_mod.main(["send-line", "lt-y", "hi"]) == 0
    assert backend_mod.main(["capture-pane", "lt-y", "--scrollback"]) == 0
    assert backend_mod.main(["has-session", "lt-y"]) == 0
    assert backend_mod.main(["kill-session", "lt-y"]) == 0
    assert backend_mod.main([
        "reap", "--run-id", "run-a", "--owner-pid", "111"
    ]) == 0
    assert backend_mod.main(["require"]) == 0
    assert backend_mod.main(["kill-session", "../evil"]) == 2  # session 名検証は CLI 層でも効く


def test_backend_reap_cli_requires_an_explicit_scope():
    """引数なし reap が従来の lt-* 全 kill へ戻らないことを固定する。"""
    with pytest.raises(SystemExit) as exc:
        backend_mod.main(["reap"])
    assert exc.value.code == 2
    assert backend_mod.main(["reap", "--run-id", "../unsafe"]) == 2
    assert backend_mod.main(["reap", "--run-id", "safe"]) == 2
    assert backend_mod.main(["reap", "--all", "--owner-pid", "123"]) == 2


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"BAD-NAME": "value"}, "invalid environment override name"),
        ({"SAFE_NAME": "line1\nline2"}, "invalid environment override value"),
    ],
)
def test_backend_rejects_unsafe_environment_overrides(
    monkeypatch, tmp_path, overrides, message
):
    monkeypatch.setattr(backend_mod, "require_tmux", lambda: None)
    monkeypatch.setattr(backend_mod, "kill_session", lambda _session: True)
    with pytest.raises(ValueError, match=message):
        backend_mod.new_session(
            "lt-env-guard", str(tmp_path), run_id="env-guard",
            environment_overrides=overrides,
        )


def test_backend_cli_does_not_expose_arbitrary_direct_command(tmp_path):
    """new-session CLI は command 余剰引数を受けず argparse で拒否する。"""
    with pytest.raises(SystemExit) as exc:
        backend_mod.main([
            "new-session", "lt-x", str(tmp_path), "; touch /tmp/injected"
        ])
    assert exc.value.code == 2


def test_backend_paste_buffer_name_is_deterministic_isolated_and_injection_safe(tmp_path):
    path = tmp_path / "task; display-message.md"
    same_a = backend_mod.paste_buffer_name("lt-route-a", path)
    same_b = backend_mod.paste_buffer_name("lt-route-a", path)
    other_session = backend_mod.paste_buffer_name("lt-route-b", path)
    other_path = backend_mod.paste_buffer_name("lt-route-a", tmp_path / "other.md")

    assert same_a == same_b
    assert len({same_a, other_session, other_path}) == 3
    assert backend_mod.valid_buffer_name(same_a)
    assert ";" not in same_a and "/" not in same_a
    assert not backend_mod.valid_buffer_name("x; display-message")
    assert not backend_mod.valid_buffer_name(
        "x" * (backend_mod._BUFFER_NAME_MAX + 1)
    )
    with pytest.raises(ValueError, match="invalid session"):
        backend_mod.paste_buffer_name("lt-safe; display-message", path)
    with pytest.raises(ValueError, match="invalid session"):
        backend_mod.paste_buffer_name("lt-safe\n", path)


def test_backend_paste_buffer_cleanup_runs_when_paste_fails(monkeypatch, tmp_path):
    calls = []

    def fake_tmux(*args, check=False):
        calls.append((args, check))
        if args[0] == "paste-buffer":
            raise RuntimeError("simulated paste failure")
        return None

    task = tmp_path / "task.md"
    task.write_text("payload\n", encoding="utf-8")
    monkeypatch.setattr(backend_mod, "require_tmux", lambda: None)
    monkeypatch.setattr(backend_mod, "_tmux", fake_tmux)

    with pytest.raises(RuntimeError, match="simulated paste failure"):
        backend_mod.paste_file("lt-cleanup", str(task))

    load = next(args for args, _check in calls if args[0] == "load-buffer")
    delete = next(args for args, _check in calls if args[0] == "delete-buffer")
    assert delete == ("delete-buffer", "-b", load[2])


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux unavailable")
def test_backend_real_tmux_eight_parallel_pastes_are_session_isolated(
    monkeypatch, tmp_path
):
    """全 load を先に完了させ、default-buffer 実装なら確実に誤配信する race。"""
    count = 8
    sessions = [f"lt-buffer-race-{i}" for i in range(count)]
    files = []
    receiver = (
        "import sys,time; "
        "line=sys.stdin.readline().rstrip('\\n'); "
        "print('RECEIVED:'+line,flush=True); time.sleep(5)"
    )
    original_tmux = backend_mod._tmux
    barrier = threading.Barrier(count, timeout=10)

    try:
        for i, session in enumerate(sessions):
            task = tmp_path / f"task-{i}.md"
            task.write_text(f"PAYLOAD_{i}\n", encoding="utf-8")
            files.append(task)
            backend_mod.new_session(
                session,
                str(tmp_path),
                command_argv=(sys.executable, "-u", "-c", receiver),
                run_id="buffer-race",
            )

        def synchronized_tmux(*args, check=False):
            result = original_tmux(*args, check=check)
            if args[0] == "load-buffer":
                barrier.wait()
            return result

        monkeypatch.setattr(backend_mod, "_tmux", synchronized_tmux)
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [
                pool.submit(backend_mod.paste_file, session, str(path))
                for session, path in zip(sessions, files)
            ]
            for future in futures:
                future.result(timeout=15)

        for i, session in enumerate(sessions):
            expected = f"RECEIVED:PAYLOAD_{i}"
            captured = ""
            for _ in range(40):
                captured = backend_mod.capture_pane(session)
                if expected in captured:
                    break
                time.sleep(0.05)
            assert expected in captured, captured
            assert all(
                f"RECEIVED:PAYLOAD_{other}" not in captured
                for other in range(count)
                if other != i
            )

        listed = original_tmux("list-buffers", "-F", "#{buffer_name}")
        remaining = set(listed.stdout.splitlines()) if listed.returncode == 0 else set()
        expected_names = {
            backend_mod.paste_buffer_name(session, str(path))
            for session, path in zip(sessions, files)
        }
        assert remaining.isdisjoint(expected_names)
    finally:
        monkeypatch.setattr(backend_mod, "_tmux", original_tmux)
        for session in sessions:
            backend_mod.kill_session(session)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux unavailable")
def test_backend_real_tmux_direct_process_avoids_interactive_shell(tmp_path):
    """tmux pane が対話 shell readiness 無しで指定processを実行する。"""
    session = "lt-direct-process-fixture"
    marker = "DIRECT_PROCESS_READY"
    argv = (
        sys.executable,
        "-u",
        "-c",
        f"import time; print('{marker}', flush=True); time.sleep(5)",
    )
    try:
        backend_mod.new_session(
            session, str(tmp_path), command_argv=argv, run_id="direct-process"
        )
        captured = ""
        for _ in range(40):
            captured = backend_mod.capture_pane(session)
            if marker in captured:
                break
            time.sleep(0.05)
        assert marker in captured
        assert backend_mod.has_session(session)
        assert backend_mod.pane_current_command(session) not in {"", "zsh", "bash", "sh"}
        ownership = {
            name: (run_id, owner_pid)
            for name, run_id, owner_pid in backend_mod.list_session_ownership()
        }
        assert ownership[session][0] == "direct-process"
        assert ownership[session][1].isdecimal()
        assert int(ownership[session][1]) > 0
    finally:
        backend_mod.kill_session(session)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux unavailable")
def test_backend_real_tmux_session_environment_overrides_stale_global_value(
    monkeypatch, tmp_path
):
    """session 固有値が隔離 tmux server の stale global 値を上書きする。"""
    # macOS の Unix socket path 上限に収めつつ、通常利用中の tmux server と隔離する。
    socket_root = tempfile.mkdtemp(prefix="lt-env-")
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setenv("TMUX_TMPDIR", socket_root)

    env_name = "SYSTEM_SPEC_AUDIT_FORK_LEDGER"
    stale_value = "/tmp/stale-global-ledger.jsonl"
    current_value = "current value; 'quoted' $(not-executed)"
    token = f"env-override-{os.getpid()}"
    anchor = f"lt-{token}-anchor"
    current_session = f"lt-{token}-current"
    empty_session = f"lt-{token}-empty"
    sleeper = (sys.executable, "-u", "-c", "import time; time.sleep(30)")

    def env_reporter():
        return (
            sys.executable,
            "-u",
            "-c",
            (
                "import os,time; "
                f"print('ENV='+repr(os.environ.get('{env_name}')), flush=True); "
                "time.sleep(30)"
            ),
        )

    try:
        backend_mod.new_session(
            anchor, str(tmp_path), command_argv=sleeper, run_id=token
        )
        socket_path = backend_mod._tmux(
            "display-message", "-p", "#{socket_path}", check=True
        ).stdout.strip()
        assert os.path.commonpath(
            (os.path.realpath(socket_root), os.path.realpath(socket_path))
        ) == os.path.realpath(socket_root)
        backend_mod._tmux(
            "set-environment", "-g", env_name, stale_value, check=True
        )
        backend_mod.new_session(
            current_session,
            str(tmp_path),
            command_argv=env_reporter(),
            run_id=token,
            environment_overrides={env_name: current_value},
        )
        backend_mod.new_session(
            empty_session,
            str(tmp_path),
            command_argv=env_reporter(),
            run_id=token,
            environment_overrides={env_name: ""},
        )

        captures = {}
        for session in (current_session, empty_session):
            for _ in range(40):
                captures[session] = backend_mod.capture_pane(session)
                if "ENV=" in captures[session]:
                    break
                time.sleep(0.05)

        assert f"ENV={current_value!r}" in captures[current_session]
        assert "ENV=''" in captures[empty_session]
        assert stale_value not in captures[current_session]
        assert stale_value not in captures[empty_session]
    finally:
        backend_mod._tmux("set-environment", "-gu", env_name)
        for session in (current_session, empty_session, anchor):
            backend_mod.kill_session(session)
        backend_mod._tmux("kill-server")
        shutil.rmtree(socket_root, ignore_errors=True)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux unavailable")
def test_backend_real_tmux_reap_is_limited_to_its_owned_run(tmp_path):
    """実 tmux でも別 run と metadata 無し session を巻き添えにしない。"""
    token = f"reap-scope-{os.getpid()}"
    owned_run = f"{token}-owned"
    owned_session = f"lt-{owned_run}-worker"
    other_session = f"lt-{owned_run}-sibling"
    unowned_session = f"lt-{owned_run}-legacy"
    argv = (
        sys.executable,
        "-u",
        "-c",
        "import time; time.sleep(30)",
    )
    try:
        backend_mod.new_session(
            owned_session,
            str(tmp_path),
            command_argv=argv,
            run_id=owned_run,
            owner_pid=111,
        )
        backend_mod.new_session(
            other_session,
            str(tmp_path),
            command_argv=argv,
            run_id=owned_run,
            owner_pid=222,
        )
        backend_mod._tmux(
            "new-session",
            "-d",
            "-s",
            unowned_session,
            "-c",
            str(tmp_path),
            backend_mod._direct_process_command(argv),
            check=True,
        )

        assert backend_mod.reap(owned_run, 111) == [owned_session]
        assert not backend_mod.has_session(owned_session)
        assert backend_mod.has_session(other_session)
        assert backend_mod.has_session(unowned_session)
    finally:
        for session in (owned_session, other_session, unowned_session):
            backend_mod.kill_session(session)
