#!/usr/bin/env python3
# /// script
# name: validate-codex-audit
# purpose: Codex原rolloutの独立監査帰属をhost bindingと再照合する。
# inputs: [Python API: binding, native parent/child rollout]
# outputs: [Python API: verified schema 2.0 audit records]
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Codex専用の原証跡検証。Claudeのhookイベントへ変換しない。"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = "2.0"
PRODUCER = "codex-native-rollout-observer"
AUDITORS = frozenset({"system-spec-matrix-auditor", "system-spec-hearing-auditor", "system-spec-doc-freshness-auditor"})
TASK_AUDITORS = {name.replace("-", "_"): name for name in AUDITORS}
MARKER = re.compile(r"AUDIT_VERDICT: (PASS|FAIL|INDETERMINATE)")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(text(item) for item in value)
    if isinstance(value, dict):
        return value.get("text", "")
    return ""


def rows(raw: bytes):
    values = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if not values or values[0].get("type") != "session_meta":
        raise ValueError("native first session metadata missing")
    if any(not isinstance(row.get("payload"), dict) for row in values):
        raise ValueError("native payload invalid")
    if any(isinstance(row.get("ordinal"), bool) or not isinstance(row.get("ordinal"), int)
           or row["ordinal"] != i for i, row in enumerate(values)):
        raise ValueError("native ordinal gap/duplicate")
    return values


def outside(path: Path, writable: list[str]):
    resolved = path.resolve()
    if any(resolved.is_relative_to(Path(root).resolve()) for root in writable):
        raise ValueError("audit evidence lies inside actor writable roots")


def source_pins(plugin_root: Path):
    pins = {"verifier": sha(Path(__file__).read_bytes())}
    for name in AUDITORS:
        definition = plugin_root / "agents" / (name + ".md")
        pins[name] = sha(definition.read_bytes())
        match = re.search(r"^prompt_ssot:\s*(.+)$", definition.read_text(), re.M)
        if match is None:
            raise ValueError("native auditor prompt SSOT missing")
        prompt = (definition.parent / match.group(1).strip()).resolve(strict=True)
        prompt.relative_to(plugin_root.resolve())
        pins[name + ":prompt"] = sha(prompt.read_bytes())
    return pins


def verify_binding(binding: dict, directory: Path, plugin_root: Path):
    if binding.get("schema_version") != "codex-audit-host-binding/v1" or binding.get("producer") != PRODUCER:
        raise ValueError("native audit host binding invalid")
    config_path = Path(binding["config_path"])
    cfg = json.loads(config_path.read_bytes())
    if sha(config_path.read_bytes()) != binding["config_sha256"]:
        raise ValueError("native audit execution config changed")
    fixture = cfg.get("codex_audit_fixture")
    if not isinstance(fixture, dict) or Path(fixture["plugin_root"]).resolve() != plugin_root.resolve():
        raise ValueError("native audit provider config mismatch")
    expected_directory = Path(cfg["private_dir"]).resolve() / "codex-audit"
    expected_writable = [str(Path(cfg["repo_root"]).resolve()), str((Path(cfg["workdir"]) / "out").resolve())]
    if directory.resolve() != expected_directory or binding["writable_roots"] != expected_writable:
        raise ValueError("native audit protected directory/config mismatch")
    if binding["run_id"] != cfg["run_id"]:
        raise ValueError("native audit run identity mismatch")
    if binding["native_session_root"] != str((Path.home() / ".codex/sessions").resolve()):
        raise ValueError("native audit session source must be ordinary native storage")
    for path in (directory, config_path, plugin_root):
        outside(path, expected_writable)
    expected_sources = source_pins(plugin_root)
    if binding["sources"] != expected_sources or fixture["verifier_sha256"] != expected_sources["verifier"]:
        raise ValueError("native audit source pin changed")
    if str(plugin_root.resolve()) not in [str(Path(p).resolve()) for p in cfg["loaded_provider_roots"]]:
        raise ValueError("native audit provider not loaded")
    return cfg


def verify_native_roots(values: list, binding: dict):
    metadata = values[0]["payload"]
    if sorted(metadata.get("runtime_workspace_roots", [])) != sorted(binding["writable_roots"]):
        raise ValueError("native workspace roots differ from host binding")
    contexts = [row["payload"] for row in values if row["type"] == "turn_context"]
    if not contexts:
        raise ValueError("native sandbox context missing")
    for context in contexts:
        policy = context.get("sandbox_policy", {})
        profile = context.get("permission_profile", {}).get("file_system", {})
        writes = []
        for entry in profile.get("entries", []):
            if entry.get("access") == "write":
                value = entry.get("path", {})
                if value.get("type") != "path":
                    raise ValueError("native special write root forbidden")
                writes.append(value["path"])
        if (policy.get("type") != "workspace-write" or policy.get("network_access") is not False
                or policy.get("exclude_tmpdir_env_var") is not True or policy.get("exclude_slash_tmp") is not True
                or profile.get("type") != "restricted" or sorted(writes) != sorted(binding["writable_roots"])):
            raise ValueError("native audit storage is not protected by actual sandbox")


def read_input(value):
    if isinstance(value, str):
        try:
            return str(json.loads(value))
        except ValueError:
            return value
    return str(value)


def successful_read(output, source: str) -> bool:
    if isinstance(output, list):
        return any(successful_read(item, source) for item in output)
    if isinstance(output, dict):
        if output.get("exit_code") == 0 and output.get("output") == source:
            return True
        return any(successful_read(output[key], source) for key in ("text", "output") if key in output)
    if isinstance(output, str):
        try:
            decoded = json.loads(output)
        except ValueError:
            return bool(re.search(r"Process exited with code 0\s+Final output:\s*", output)) and output.endswith(source)
        return decoded != output and successful_read(decoded, source)
    return False


def reconstruct(parent_raw: bytes, child_raw: bytes, binding: dict, plugin_root: Path) -> dict:
    parents, children = rows(parent_raw), rows(child_raw)
    verify_native_roots(parents, binding)
    verify_native_roots(children, binding)
    pm, cm = parents[0]["payload"], children[0]["payload"]
    if len([r for r in children if r["type"] == "session_meta"]) != 1 or cm.get("subagent_history_start_ordinal") is not None:
        raise ValueError("native auditor must have a fresh context")
    origin = cm.get("source", {}).get("subagent", {}).get("thread_spawn", {})
    if origin.get("parent_thread_id") != pm.get("id") or cm.get("id") == pm.get("id"):
        raise ValueError("native audit parent/child identity mismatch")
    calls, outputs = {}, {}
    for row in parents:
        value = row["payload"]
        if row["type"] == "response_item" and value.get("type") == "function_call" and value.get("name", "").split(".")[-1] == "spawn_agent":
            call_id = value.get("call_id")
            if call_id in calls:
                raise ValueError("native spawn call ID duplicated")
            calls[call_id] = json.loads(value["arguments"])
        if row["type"] == "response_item" and value.get("type") == "function_call_output":
            outputs[value.get("call_id")] = value.get("output")
    matches = []
    for call_id, args in calls.items():
        if args.get("task_name") not in TASK_AUDITORS or call_id not in outputs:
            continue
        result = json.loads(text(outputs[call_id]))
        if result.get("task_name") == origin.get("agent_path"):
            matches.append((call_id, args))
    if len(matches) != 1:
        raise ValueError("native audit spawn attribution absent or ambiguous")
    call_id, args = matches[0]
    auditor = TASK_AUDITORS[args["task_name"]]
    if args.get("fork_turns") != "none":
        raise ValueError("native audit dispatch did not request fresh context")
    definition = plugin_root / "agents" / (auditor + ".md")
    body = definition.read_text()
    prompt_match = re.search(r"^prompt_ssot:\s*(.+)$", body, re.M)
    if prompt_match is None:
        raise ValueError("native audit prompt SSOT missing")
    prompt_path = (definition.parent / prompt_match.group(1).strip()).resolve(strict=True)
    prompt_path.relative_to(plugin_root.resolve())
    reads, completed_calls, user_prompts, final_messages, starts, completions = {}, {}, [], [], [], []
    for index, row in enumerate(children):
        value = row["payload"]
        kind = value.get("type")
        if row["type"] == "response_item":
            if kind in {"function_call", "custom_tool_call"}:
                reads[value["call_id"]] = {"name": value.get("name", "").split(".")[-1],
                    "input": value.get("arguments", value.get("input", ""))}
            elif kind in {"function_call_output", "custom_tool_call_output"}:
                completed_calls[value["call_id"]] = value.get("output")
            elif kind == "message" and value.get("role") == "user":
                user_prompts.append(text(value.get("content")))
            elif kind == "message" and value.get("role") == "assistant" and value.get("channel") in (None, "final"):
                final_messages.append((index, text(value.get("content"))))
        elif row["type"] == "event_msg" and kind == "task_started":
            starts.append(index)
        elif row["type"] == "event_msg" and kind == "task_complete":
            completions.append((index, value.get("last_agent_message")))
    if set(reads) - set(completed_calls) or not starts or not completions or completions[-1][0] <= starts[-1]:
        raise ValueError("native auditor has not completed")
    if not final_messages or final_messages[-1][1] != completions[-1][1] or not user_prompts:
        raise ValueError("native audit final response/prompt not corroborated")
    response = final_messages[-1][1]
    marker = MARKER.fullmatch(response.rstrip().splitlines()[-1]) if response.strip() else None
    if marker is None:
        raise ValueError("native audit final AUDIT_VERDICT missing")
    for source_path in (definition, prompt_path):
        if not any(call["name"] in {"exec", "exec_command", "read_file"}
                   and re.search(r"\b(?:cat|sed|read_file)\b|\.read_(?:text|bytes)\s*\(", read_input(call["input"]))
                   and str(source_path) in read_input(call["input"])
                   and successful_read(completed_calls.get(cid), source_path.read_text())
                   for cid, call in reads.items()):
            raise ValueError("native audit agent definition/prompt was not fully read")
    return {"schema_version": SCHEMA, "producer": PRODUCER, "tool_name": "spawn_agent",
            "subagent_type": auditor, "session_id": pm["id"], "tool_use_id": call_id,
            "child_session_id": cm["id"], "agent_path": origin["agent_path"],
            "prompt_sha256": sha(user_prompts[0].encode()), "spawn_args_sha256": sha(json.dumps(args, sort_keys=True, ensure_ascii=False).encode()),
            "response_sha256": sha(response.encode()), "audit_verdict": marker.group(1), "verdict_state": "resolved",
            "agent_definition_sha256": sha(body.encode())}


def verify_record(record: dict, ledger: Path, plugin_root: Path) -> dict:
    directory = ledger.resolve().parent
    binding_raw = (directory / "host-binding.json").read_bytes()
    if sha(binding_raw) != record.get("host_binding_sha256"):
        raise ValueError("native audit host binding digest mismatch")
    binding = json.loads(binding_raw)
    verify_binding(binding, directory, plugin_root)
    native_root = Path(binding["native_session_root"])
    values = []
    for key in ("parent", "child"):
        evidence = record[key]
        snapshot = (directory / evidence["snapshot_ref"]).resolve(strict=True)
        snapshot.relative_to(directory)
        raw = snapshot.read_bytes()
        original = Path(evidence["native_source"]).resolve(strict=True)
        original.relative_to(native_root)
        outside(original, binding["writable_roots"])
        if sha(raw) != evidence["sha256"] or len(raw) != evidence["bytes"] or not raw.endswith(b"\n"):
            raise ValueError("native audit snapshot bytes mismatch")
        with original.open("rb") as stream:
            if stream.read(len(raw)) != raw:
                raise ValueError("native audit snapshot is not exact original native prefix")
        values.append(raw)
    result = reconstruct(*values, binding, plugin_root)
    expected = {key: value for key, value in record.items() if key not in {"parent", "child", "host_binding_sha256"}}
    if result != expected:
        raise ValueError("native audit record differs from original rollout reconstruction")
    current = os.environ.get("CODEX_THREAD_ID")
    if current and current != result["session_id"]:
        raise ValueError("native audit receipt belongs to another current thread")
    return result
