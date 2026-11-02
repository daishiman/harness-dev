#!/usr/bin/env python3
# /// script
# name: extract-codex-transcript
# purpose: Codex native rolloutを変換せずに読み、実skill適用・終了・モデル・資源使用を検証する。
# inputs:
#   - argv: なし（live-trial-verdict/runtime runnerからimport）
# outputs:
#   - stdout: なし
#   - exit: 呼出側へ検査結果を返す
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Read native Codex rollout JSONL; never synthesize Claude tool events.

Native skill activation means the host-injected ``<skill>`` contains the current
source and a subsequent real read tool succeeds with those same source bytes.
User mentions, shell-script execution and a caller's PASS are not activation.
Token counts are cumulative per native thread, so only the final monotonic total
is counted. Cached/reasoning tokens are subsets, not additions to that total.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any


FORMAT = "codex-rollout-jsonl"
_SKILL = re.compile(r"<skill>\s*<name>([^<]+)</name>\s*<path>([^<]+)</path>\s*(.*?)\s*</skill>", re.S)
_SKILL_NAME = re.compile(r"(?:(?P<plugin>[a-z0-9][a-z0-9-]{0,127}):)?(?P<skill>[a-z0-9][a-z0-9-]{0,127})")


def _declared_source_roots(skill_dir: Path) -> dict[str, Path] | None:
    """Use the canonical closure resolver, rather than a second dependency map."""
    if skill_dir.parent.name != "skills" or skill_dir.parent.parent.parent.name != "plugins":
        return None
    source = Path(__file__).with_name("live-trial-verdict.py")
    spec = importlib.util.spec_from_file_location("codex_declared_behavior", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module.behavior_closure_files(skill_dir, runtime="codex")
    return {path.parent.parent.name: path.parent.parent for _label, path in files
            if path.parent.name == ".codex-plugin" and path.name == "plugin.json"}


def _projection_entries(path: Path, session_id: str | None) -> list[dict]:
    state_path = path.parent / "native-run-state.json"
    if not state_path.is_file():
        return []
    state = json.loads(state_path.read_text(encoding="utf-8"))
    reference = state.get("projection_receipt_ref") if isinstance(state, dict) else None
    if reference is None or state.get("collected") is not True:
        return []
    if state.get("runtime") != "codex" or state.get("session_id") != session_id or not isinstance(reference, str):
        raise ValueError("projection state identity mismatch")
    receipt = (path.parent / reference).resolve(strict=True)
    receipt.relative_to(path.parent.resolve())
    raw = receipt.read_bytes()
    if hashlib.sha256(raw).hexdigest() != state.get("projection_receipt_sha256"):
        raise ValueError("projection receipt digest mismatch")
    document = json.loads(raw)
    entries = document.get("skills") if isinstance(document, dict) else None
    if not isinstance(entries, list) or document.get("source_body_modified") is not False:
        raise ValueError("projection receipt shape invalid")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"qualified_skill", "project_path", "source_path", "sha256"}:
            raise ValueError("projection entry shape invalid")
        name = _SKILL_NAME.fullmatch(entry["qualified_skill"]) if isinstance(entry["qualified_skill"], str) else None
        if name is None or name.group("plugin") is None or not re.fullmatch(r"[a-f0-9]{64}", str(entry["sha256"])):
            raise ValueError("projection entry identity invalid")
        if any(not isinstance(entry[key], str) or not Path(entry[key]).is_absolute() for key in ("project_path", "source_path")):
            raise ValueError("projection paths must be absolute")
        identity = (entry["qualified_skill"], entry["project_path"])
        if identity in seen:
            raise ValueError("projection entry duplicated")
        seen.add(identity)
    return entries


def _matches_source_path(injected: Path, source: Path, namespace: str | None,
                         qualified: str, projections: list[dict]) -> bool:
    if injected.exists():
        if injected.resolve() == source.resolve():
            return True
    # Archived/remote-CI verification cannot dereference the original private
    # root. A controller-owned, state-SHA-bound mapping preserves the exact alias,
    # namespace and source bytes; a coincidental path suffix is never enough.
    if namespace:
        expected = ("plugins", namespace, "skills", source.parent.name, "SKILL.md")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        for entry in projections:
            if entry["qualified_skill"] != qualified or entry["project_path"] != str(injected) or entry["sha256"] != digest:
                continue
            original = Path(entry["source_path"])
            if tuple(original.parts[-len(expected):]) != expected:
                continue
            if injected.exists() and original.exists() and injected.resolve() != original.resolve():
                continue
            return True
    return injected == source and injected.exists()


def _records(path: Path) -> tuple[list[dict], list[str]]:
    records, errors = [], []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"native-json-invalid:line-{index}")
            continue
        if not isinstance(value, dict) or not isinstance(value.get("payload"), dict):
            errors.append(f"native-record-invalid:line-{index}")
            continue
        if value.get("type") not in {"session_meta", "turn_context", "response_item", "event_msg", "compacted",
                                     "world_state", "token_usage_record", "inter_agent_communication_metadata"}:
            errors.append(f"native-record-type-invalid:line-{index}")
        records.append(value)
    return records, errors


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    if isinstance(value, dict):
        return str(value.get("text", ""))
    return ""


def _successful_read_output(output: Any, source: str) -> bool:
    """Recognize the actual exec wrapper output without executing its JS/input."""
    if isinstance(output, list):
        return any(_successful_read_output(item, source) for item in output)
    if isinstance(output, dict):
        if output.get("exit_code") == 0 and output.get("output") == source:
            return True
        return any(_successful_read_output(output[key], source) for key in ("text", "output") if key in output)
    if isinstance(output, str):
        try:
            decoded = json.loads(output)
        except (ValueError, TypeError):
            return bool(re.search(r"Process exited with code 0\s+Final output:\s*", output)) and output.endswith(source)
        if decoded != output:
            return _successful_read_output(decoded, source)
    return False


def _usage(payload: dict) -> dict[str, int] | None:
    info = payload.get("info")
    raw = info.get("total_token_usage") if isinstance(info, dict) else payload.get("thread_token_usage")
    if not isinstance(raw, dict):
        return None
    if any(isinstance(raw.get(key), bool) or not isinstance(raw.get(key), int) or raw[key] < 0
           for key in ("input_tokens", "output_tokens", "total_tokens")):
        return None
    if raw["total_tokens"] != raw["input_tokens"] + raw["output_tokens"]:
        return None
    for key, maximum in (("cached_input_tokens", raw["input_tokens"]),
                         ("cache_write_input_tokens", raw["input_tokens"]),
                         ("reasoning_output_tokens", raw["output_tokens"])):
        if key in raw and (isinstance(raw[key], bool) or not isinstance(raw[key], int) or not 0 <= raw[key] <= maximum):
            return None
    return {"input_tokens": raw["input_tokens"], "output_tokens": raw["output_tokens"], "total_tokens": raw["total_tokens"]}


def _sandbox(payload: dict) -> dict:
    policy, profile = payload.get("sandbox_policy"), payload.get("permission_profile")
    policy = policy if isinstance(policy, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    filesystem = profile.get("file_system", {})
    filesystem = filesystem if isinstance(filesystem, dict) else {}
    roots, special = [], []
    for entry in filesystem.get("entries", []):
        if not isinstance(entry, dict) or entry.get("access") != "write":
            continue
        path = entry.get("path", {})
        if isinstance(path, dict) and path.get("type") == "path" and isinstance(path.get("path"), str):
            roots.append(path["path"])
        if isinstance(path, dict) and path.get("type") == "special" and isinstance(path.get("value"), dict):
            special.append(path["value"].get("kind"))
    return {"mode": policy.get("type"), "approval_policy": payload.get("approval_policy"),
            "network_access": policy.get("network_access"), "writable_roots": sorted(set(roots)),
            "special_write_roots": sorted({value for value in special if isinstance(value, str)}),
            "exclude_tmpdir_env_var": policy.get("exclude_tmpdir_env_var"),
            "exclude_slash_tmp": policy.get("exclude_slash_tmp"),
            "profile_restricted": filesystem.get("type") == "restricted"}


def _inspect_one(path: Path, *, skill_dir: Path | None = None, target_skill: str | None = None) -> dict:
    records, errors = _records(path)
    metas = [r["payload"] for r in records if r.get("type") == "session_meta"]
    if len(metas) != 1 or not isinstance(metas[0].get("id"), str) or not metas[0].get("id"):
        errors.append("native-session-meta-missing-or-ambiguous")
    meta = metas[0] if len(metas) == 1 else {}
    source = (skill_dir / "SKILL.md").read_bytes().decode("utf-8") if skill_dir is not None else None
    models, injections, calls, successful, spawned, user_turns, sandboxes = set(), [], {}, {}, [], [], []
    latest_usage, invalid_usage, usage_checkpoints = None, False, set()
    last_started = last_complete = -1
    for index, row in enumerate(records):
        payload, kind = row["payload"], row.get("type")
        typ = payload.get("type")
        if kind == "turn_context" and isinstance(payload.get("model"), str) and payload["model"]:
            models.add(payload["model"])
            sandbox = _sandbox(payload)
            if sandbox not in sandboxes:
                sandboxes.append(sandbox)
        elif kind == "response_item" and typ == "message" and payload.get("role") == "user":
            text = _text(payload.get("content"))
            metadata = payload.get("internal_chat_message_metadata_passthrough")
            metadata = metadata if isinstance(metadata, dict) else {}
            kinds = metadata.get("content_item_kinds", [])
            if "user.text" in kinds:
                user_turns.append({"turn_id": metadata.get("turn_id"), "message_id": payload.get("id"),
                                   "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                                   "normalized_text_sha256": hashlib.sha256(text.strip().encode()).hexdigest()})
            if "skills.selected_skill_instructions" not in kinds:
                continue
            for match in _SKILL.finditer(text):
                name, raw_path, body = match.groups()
                injections.append({"name": name.strip(), "path": raw_path.strip(), "body": body, "index": index})
        elif kind == "response_item" and typ in {"function_call", "custom_tool_call"}:
            call_id = payload.get("call_id")
            if isinstance(call_id, str):
                calls[call_id] = {"name": payload.get("name", ""), "input": payload.get("arguments", payload.get("input", "")), "index": index}
        elif kind == "response_item" and typ in {"function_call_output", "custom_tool_call_output"}:
            call_id = payload.get("call_id")
            if isinstance(call_id, str) and call_id in calls:
                successful[call_id] = payload.get("output")
                if calls[call_id]["name"].split(".")[-1] == "spawn_agent":
                    try:
                        result = json.loads(_text(payload.get("output")))
                    except (ValueError, TypeError):
                        result = payload.get("output")
                    if isinstance(result, dict) and not result.get("error"):
                        spawned.append(result)
        elif kind == "event_msg" and typ == "task_started":
            last_started = index
        elif kind == "event_msg" and typ == "task_complete":
            last_complete = index
        elif (kind == "event_msg" and typ == "token_count" and payload.get("info") is not None) or kind == "token_usage_record":
            if kind == "token_usage_record" and payload.get("thread_id") != meta.get("id"):
                errors.append("native-usage-thread-mismatch")
            current = _usage(payload)
            if current is None or (latest_usage and any(current[k] < latest_usage[k] for k in current)):
                invalid_usage = True
            else:
                latest_usage = current
                usage_checkpoints.add(tuple(current[key] for key in ("input_tokens", "output_tokens", "total_tokens")))
    activations, activation_errors = [], []
    if source is not None:
        try:
            projections = _projection_entries(path, meta.get("id"))
        except (OSError, ValueError) as exc:
            projections = []
            errors.append(f"native-projection-receipt-invalid:{exc}")
        expected_name = target_skill.split(":")[-1] if target_skill else skill_dir.name
        target_namespace = target_skill.split(":")[0] if target_skill and ":" in target_skill else None
        try:
            source_roots = _declared_source_roots(skill_dir)
        except (OSError, ValueError) as exc:
            source_roots = {}
            errors.append(f"native-dependency-pin-invalid:{exc}")
        if source_roots is not None:
            actual_namespace = skill_dir.parent.parent.name
            if target_namespace is not None and target_namespace != actual_namespace:
                errors.append("native-target-namespace-source-mismatch")
            target_namespace = actual_namespace
        for entry in injections:
            parsed_name = _SKILL_NAME.fullmatch(entry["name"])
            if parsed_name is None:
                activation_errors.append("native-skill-name-invalid")
                continue
            namespace, local_name = parsed_name.group("plugin"), parsed_name.group("skill")
            possible = []
            if local_name == expected_name and namespace in {None, target_namespace}:
                qualified_target = f"{target_namespace}:{expected_name}" if target_namespace else expected_name
                possible.append((qualified_target, source, skill_dir / "SKILL.md", target_namespace))
            elif source_roots is not None:
                roots = {namespace: source_roots[namespace]} if namespace in source_roots else (source_roots if namespace is None else {})
                for slug, root in roots.items():
                    candidate = root / "skills" / local_name / "SKILL.md"
                    if not candidate.is_file():
                        continue
                    try:
                        candidate.resolve().relative_to(root.resolve())
                    except ValueError:
                        activation_errors.append("native-skill-source-escape")
                        continue
                    possible.append((f"{slug}:{local_name}", candidate.read_bytes().decode("utf-8"), candidate, slug))
            matching = [candidate for candidate in possible if entry["body"].strip() == candidate[1].strip()]
            if len(matching) != 1:
                activation_errors.append(f"native-skill-source-unproven:{entry['name']}")
                continue
            qualified, selected_source, source_path, selected_namespace = matching[0]
            injected = Path(entry["path"])
            if not injected.is_absolute() or injected.name != "SKILL.md":
                activation_errors.append(f"native-skill-path-invalid:{entry['name']}")
                continue
            if not _matches_source_path(injected, source_path, selected_namespace, qualified, projections):
                activation_errors.append(f"native-skill-path-source-mismatch:{entry['name']}")
                continue
            cwd = meta.get("cwd")
            relative = os.path.relpath(injected, cwd) if isinstance(cwd, str) and cwd else None
            for call_id, call in calls.items():
                if call["index"] <= entry["index"] or call_id not in successful:
                    continue
                raw_input = call["input"] if isinstance(call["input"], str) else json.dumps(call["input"])
                if call["name"].split(".")[-1] not in {"exec", "exec_command", "read_file"}:
                    continue
                if not re.search(r"\b(?:cat|sed|read_file)\b|\.read_(?:text|bytes)\s*\(", raw_input):
                    continue
                if not any(value and value in raw_input for value in (str(injected), relative)):
                    continue
                if _successful_read_output(successful[call_id], selected_source):
                    activations.append({"skill": qualified, "path": str(injected),
                                        "source_sha256": hashlib.sha256(selected_source.encode()).hexdigest(),
                                        "read_call_id": call_id})
                    break
            else:
                activation_errors.append(f"native-skill-read-unproven:{entry['name']}")
    parent = meta.get("parent_thread_id")
    if not parent and isinstance(meta.get("source"), dict):
        subagent = meta["source"].get("subagent")
        spawned_from = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
        parent = spawned_from.get("parent_thread_id") if isinstance(spawned_from, dict) else None
    measured = bool(latest_usage) and not invalid_usage and not errors
    return {"session_id": meta.get("id"), "cwd": meta.get("cwd"), "parent_thread_id": parent, "agent_path": meta.get("agent_path"),
            "models": sorted(models), "cli_version": meta.get("cli_version"), "format": FORMAT,
            "invoked_skills": sorted({entry["skill"] for entry in activations}), "activations": activations,
            "injected_skills": [{**{k: v for k, v in entry.items() if k != "body"},
                                 "body_sha256": hashlib.sha256(entry["body"].strip().encode()).hexdigest()} for entry in injections],
            "format_errors": errors, "activation_errors": activation_errors,
            "completed": last_complete > last_started >= 0 and not (set(calls) - set(successful)),
            "user_turns": user_turns, "sandbox_contexts": sandboxes,
            "pending_tools": sorted(set(calls) - set(successful)), "spawned_agents": spawned,
            "usage": {"input_tokens": latest_usage["input_tokens"] if latest_usage else 0,
                      "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                      "output_tokens": latest_usage["output_tokens"] if latest_usage else 0,
                      "total_tokens": latest_usage["total_tokens"] if latest_usage else 0,
                      "assistant_messages": len(usage_checkpoints), "transcript_files": 1,
                      "measured": measured}}


def inspect_transcript(path: Path, *, skill_dir: Path | None = None, target_skill: str | None = None) -> dict:
    """Inspect one root rollout and only its collected, parent-bound children."""
    path = Path(path)
    result = _inspect_one(path, skill_dir=Path(skill_dir).resolve() if skill_dir else None, target_skill=target_skill)
    children, seen = [], {result["session_id"]}
    subdir = path.with_suffix("") / "subagents"
    candidates = [_inspect_one(child) for child in sorted(subdir.glob("*.jsonl"))] if subdir.is_dir() else []
    pending = list(candidates)
    while pending:
        attached = [child for child in pending if child["parent_thread_id"] in seen]
        if not attached:
            result["format_errors"].append("native-unrelated-child-transcript")
            break
        for child in attached:
            pending.remove(child)
            if child["session_id"] in seen:
                result["format_errors"].append("native-duplicate-child-session")
                continue
            seen.add(child["session_id"])
            children.append(child)
    for parent in [result, *children]:
        direct = [child for child in children if child["parent_thread_id"] == parent["session_id"]]
        for spawned in parent["spawned_agents"]:
            identity = spawned.get("agent_id", spawned.get("task_name"))
            if not isinstance(identity, str) or not any(identity in {child["session_id"], child["agent_path"]} for child in direct):
                result["format_errors"].append("native-spawned-child-transcript-missing")
    for child in children:
        result["format_errors"].extend(child["format_errors"])
        result["models"] = sorted(set(result["models"]) | set(child["models"]))
        for key in ("input_tokens", "output_tokens", "total_tokens", "assistant_messages", "transcript_files"):
            result["usage"][key] += child["usage"][key]
        result["usage"]["measured"] = result["usage"]["measured"] and child["usage"]["measured"]
        result["completed"] = result["completed"] and child["completed"]
    result["agent_sessions"] = [{"session_id": child["session_id"], "parent_thread_id": child["parent_thread_id"],
                                 "agent_path": child["agent_path"], "completed": child["completed"]} for child in children]
    if result["format_errors"]:
        result["usage"]["measured"] = False
        result["completed"] = False
    return result


def extract_models(path: Path) -> list[str]:
    return inspect_transcript(path)["models"]


def extract_cli_version(path: Path) -> str | None:
    return inspect_transcript(path)["cli_version"]


def extract_skill_invocations(path: Path, *, skill_dir: Path | None = None, target_skill: str | None = None) -> list[str]:
    return inspect_transcript(path, skill_dir=skill_dir, target_skill=target_skill)["invoked_skills"]


def transcript_token_usage(path: Path | None) -> dict:
    if path is None:
        return {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                "output_tokens": 0, "total_tokens": 0, "assistant_messages": 0, "transcript_files": 0, "measured": False}
    return inspect_transcript(path)["usage"]
