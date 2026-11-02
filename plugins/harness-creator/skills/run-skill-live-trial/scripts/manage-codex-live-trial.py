#!/usr/bin/env python3
# /// script
# name: manage-codex-live-trial
# purpose: Codex native exec の fresh/resume、原本採取、予算、所有process回収を管理する。
# inputs: [argv: action --config PATH]
# outputs: [private state/raw, workdir evidence, shared live-trial verdict]
# contexts: [C, E]
# network: false
# write-scope: config.private_dir and config.workdir
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Codex native 実走の制御。Claude の tool/transcript を合成しない。

fixture/provider/task/scenario は呼出し元が準備する。run は実作業だけを行い、
collect 後に別個体が評価した goal JSON を finalize へ渡す。自己 PASS は生成しない。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path


ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
SECRET_NAMES = {".guard-key", "credentials.json", "auth.json", ".env"}
TOKEN_RE = re.compile(r"\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")
SUPERVISOR_MODE = "--supervise-owned-turn"
_METADATA_CACHE: OrderedDict = OrderedDict()
_METADATA_CACHE_LIMIT = 2048
_ROLLOUT_TIME = re.compile(r"^rollout-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-")


def secret_file(path: Path) -> bool:
    name = path.name.lower()
    return name in SECRET_NAMES or name.startswith(".env.") or path.suffix.lower() in {".pem", ".key"}


def sibling(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def copy_once(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst)


def records(path: Path):
    if not path.is_file():
        return
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                yield obj


def _codex_user_config() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"


def native_hook_trust_argv(config: dict) -> list[str]:
    """Reapply only exact, persisted user trust while ignoring other user config.

    This reads native hooks/list hashes and the real user config; it neither
    computes trusted hashes nor writes trust. The native engine checks them too.
    """
    declaration = config.get("native_hook_trust")
    external = config.get("external_confirmation_fixture")
    if declaration is None:
        if external is not None:
            raise ValueError("external confirmation requires persisted native hook trust")
        return []
    if external is None or not isinstance(declaration, dict):
        raise ValueError("native hook trust is limited to an external confirmation fixture")
    try:
        import tomllib
    except ImportError as exc:
        raise ValueError("native hook trust verification requires Python 3.11+") from exc
    root = Path(config["repo_root"]).resolve()
    hooks_path = root / ".codex/hooks.json"
    if (str(hooks_path) != declaration.get("hooks_file") or hooks_path.is_symlink()
            or digest(hooks_path) != declaration.get("hooks_sha256")):
        raise ValueError("native hook definition drift")
    inspection = Path(declaration.get("native_list_file", ""))
    writable = [root, (Path(config["workdir"]) / "out").resolve()]
    if (not inspection.is_absolute() or any(inspection.resolve().is_relative_to(p) for p in writable)
            or digest(inspection) != declaration.get("native_list_sha256")):
        raise ValueError("native hook inspection is missing, mutable, or changed")
    if any((part.parent.resolve() / part.name).is_relative_to(p)
           for part in (inspection, *inspection.parents) for p in writable):
        raise ValueError("native hook inspection alias is actor writable")
    native = json.loads(inspection.read_text(encoding="utf-8"))
    listing = native.get("hooks_list", native)
    rows = [row for group in listing.get("data", [])
            if group.get("cwd") == str(root) for row in group.get("hooks", [])
            if row.get("sourcePath") == str(hooks_path)]
    definitions = json.loads(hooks_path.read_text(encoding="utf-8"))
    if set(definitions.get("hooks", {})) != {"UserPromptSubmit", "PreToolUse"}:
        raise ValueError("native hook trust requires exactly two declared events")
    expected = {}
    for event, suffix in (("UserPromptSubmit", "user_prompt_submit"), ("PreToolUse", "pre_tool_use")):
        groups = definitions["hooks"][event]
        if not isinstance(groups, list) or len(groups) != 1 or len(groups[0].get("hooks", [])) != 1:
            raise ValueError("native hook trust requires exactly two handlers")
        handler = groups[0]["hooks"][0]
        if handler.get("type") != "command" or handler.get("async", False):
            raise ValueError("native confirmation hooks must be synchronous commands")
        expected[f"{hooks_path}:{suffix}:0:0"] = handler["command"]
    if len(rows) != 2 or {row.get("key") for row in rows} != set(expected):
        raise ValueError("native hook inspection has different handlers")
    user = tomllib.loads(_codex_user_config().read_text(encoding="utf-8"))
    if user.get("projects", {}).get(str(root), {}).get("trust_level") != "trusted":
        raise ValueError("native fixture project trust is not persisted")
    state = user.get("hooks", {}).get("state", {})
    argv = ["-c", "features.hooks=true", "-c", f"projects.{json.dumps(str(root))}.trust_level=\"trusted\""]
    for row in sorted(rows, key=lambda item: item["key"]):
        key, current = row["key"], row.get("currentHash")
        if (row.get("command") != expected[key] or row.get("handlerType") != "command"
                or row.get("async") is True or row.get("enabled") is not True
                or row.get("trustStatus") != "trusted"
                or not isinstance(current, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", current)
                or state.get(key, {}).get("trusted_hash") != current):
            raise ValueError("native hook trust is not the exact persisted native hash")
        argv += ["-c", f"hooks.state.{json.dumps(key)}.trusted_hash={json.dumps(current)}"]
    return argv


def native_skill_exclusion_argv(config: dict) -> list[str]:
    """Disable only explicitly pinned, unrelated catalog entries for this CLI call."""
    entries = config.get("native_skill_exclusions", [])
    if not isinstance(entries, list):
        raise ValueError("native skill exclusions must be a list")
    if not entries:
        return []
    writable = [Path(config["repo_root"]).resolve(), (Path(config["workdir"]) / "out").resolve()]
    roots = [Path(value).resolve() for value in config.get("loaded_provider_roots", [config["skill_dir"]])]
    roots += [Path(item["skill_dir"]).resolve() for item in config.get("native_operations", [])]
    allowed = set()
    if config.get("projection_receipt_file"):
        projection = json.loads(Path(config["projection_receipt_file"]).read_text())
        if not isinstance(projection, dict) or not isinstance(projection.get("skills"), list):
            raise ValueError("native exclusion projection mapping is invalid")
        for row in projection["skills"]:
            for key in ("project_path", "source_path"):
                value = row.get(key)
                if not isinstance(value, str) or not Path(value).is_absolute():
                    raise ValueError("native exclusion projection source is invalid")
                allowed.add(Path(value).resolve())
    disabled, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"} or not isinstance(entry["path"], str):
            raise ValueError("native exclusion requires exact path and sha256")
        path = Path(entry["path"])
        if not path.is_absolute() or path.name != "SKILL.md" or not path.is_file():
            raise ValueError("native exclusion must name an existing absolute SKILL.md")
        resolved = path.resolve(strict=True)
        if resolved in seen:
            raise ValueError("native exclusion duplicate source")
        seen.add(resolved)
        if (resolved in allowed or any(resolved.is_relative_to(root) for root in roots)
                or any(resolved.is_relative_to(root) for root in writable)
                or any((part.parent.resolve() / part.name).is_relative_to(root)
                       for part in (path, *path.parents) for root in writable)):
            raise ValueError("native exclusion may not disable an actor/project/provider source")
        if not isinstance(entry["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]) or digest(path) != entry["sha256"]:
            raise ValueError("native exclusion source digest changed")
        disabled.append("{path=" + json.dumps(str(path), ensure_ascii=False) + ",enabled=false}")
    return ["-c", "skills.config=[" + ",".join(disabled) + "]"]


def codex_argv(config: dict, session_id: str | None = None) -> list[str]:
    if session_id is not None and (not ID_RE.fullmatch(session_id) or ".." in session_id):
        raise ValueError("invalid exact session identity")
    cli = Path(config["codex_executable"])
    if not cli.is_absolute() or not cli.is_file() or not os.access(cli, os.X_OK):
        raise ValueError("codex_executable must be an executable absolute path")
    argv = [str(cli), "--no-daemon", "exec", "--ignore-user-config", "--json",
            "--sandbox", "workspace-write", "--skip-git-repo-check", "-C",
            str(Path(config["repo_root"]).resolve()), "--add-dir",
            str((Path(config["workdir"]) / "out").resolve()),
            "-c", "sandbox_workspace_write.exclude_tmpdir_env_var=true",
            "-c", "sandbox_workspace_write.exclude_slash_tmp=true"]
    argv += native_hook_trust_argv(config)
    argv += native_skill_exclusion_argv(config)
    model = config.get("requested_model", "")
    if model:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
            raise ValueError("invalid model")
        argv += ["--model", model]
    if session_id:
        argv += ["resume", session_id]
    return argv + ["-"]


def actor_environment(config: dict) -> dict[str, str]:
    fixture = Path(config["repo_root"]).resolve(strict=True)
    temporary = fixture / ".native-tmp"
    temporary.mkdir(exist_ok=True)
    if temporary.is_symlink() or not temporary.resolve(strict=True).is_relative_to(fixture):
        raise ValueError("native temporary directory must remain inside fixture")
    environment = os.environ.copy()
    environment["TMPDIR"] = str(temporary)
    environment["TMPPREFIX"] = str(temporary / "zsh")
    if config.get("external_confirmation_fixture") is not None:
        environment["DEV_GRAPH_GH"] = config["external_confirmation_fixture"]["fake_adapter"]
    if config.get("codex_audit_fixture") is not None:
        environment.update(sibling("record-codex-audit").environment(config))
    return environment


def _rollout_time(path: Path) -> datetime.datetime | None:
    match = _ROLLOUT_TIME.match(path.name)
    if not match:
        return None
    try:
        return datetime.datetime.strptime(match[1], "%Y-%m-%dT%H-%M-%S")
    except ValueError:
        return None


def _session_candidates(root: Path, *, started_at_unix=None, parent_rollout=None, session_id=None):
    anchor = _rollout_time(Path(parent_rollout)) if parent_rollout else None
    if anchor is None and started_at_unix is not None:
        anchor = datetime.datetime.fromtimestamp(started_at_unix).replace(microsecond=0)
    pattern = f"rollout-*{session_id}.jsonl" if session_id else "rollout-*.jsonl"
    if anchor is None:
        # Flat deterministic fixtures remain usable; never fall back to rglob.
        yield from sorted(root.glob(pattern))
        return
    for offset in (0, 1):
        day = anchor.date() + datetime.timedelta(days=offset)
        directory = root / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}"
        for path in sorted(directory.glob(pattern)):
            stamp = _rollout_time(path)
            if stamp is None:
                raise ValueError("unknown native rollout filename in active dates")
            if stamp >= anchor:
                yield path


def _typed_parent(meta: dict) -> str | None:
    source = meta.get("source", {})
    subagent = source.get("subagent", {}) if isinstance(source, dict) else {}
    spawn = subagent.get("thread_spawn", {}) if isinstance(subagent, dict) else {}
    values = [meta.get("parent_thread_id")]
    if isinstance(spawn, dict):
        values.append(spawn.get("parent_thread_id"))
    known = [value for value in values if value is not None]
    if any(not isinstance(value, str) or not value for value in known) or len(set(known)) > 1:
        raise ValueError("native parent metadata is invalid or contradictory")
    return known[0] if known else None


def _first_metadata(path: Path, *, fresh=False) -> dict | None:
    stat = path.stat()
    key = (stat.st_dev, stat.st_ino)
    identity = str(path.resolve())
    cached = _METADATA_CACHE.get(key)
    if not fresh and cached is not None and cached[0] == identity:
        _METADATA_CACHE.move_to_end(key)
        return cached[1]
    with path.open(encoding="utf-8", errors="replace") as stream:
        line = stream.readline()
    try:
        first = json.loads(line)
    except ValueError:
        if fresh:
            raise ValueError("native first metadata is missing or incomplete")
        return None  # an in-progress first append is retried, never cached
    meta = first.get("payload") if isinstance(first, dict) and first.get("type") == "session_meta" else None
    if not isinstance(meta, dict) or not isinstance(meta.get("id"), str) or not meta["id"]:
        raise ValueError("native first metadata identity is invalid")
    _typed_parent(meta)
    if not path.name.endswith(f"-{meta['id']}.jsonl"):
        raise ValueError("native rollout filename and metadata identity differ")
    _METADATA_CACHE[key] = (identity, meta)
    _METADATA_CACHE.move_to_end(key)
    while len(_METADATA_CACHE) > _METADATA_CACHE_LIMIT:
        _METADATA_CACHE.popitem(last=False)
    return meta


def child_rollouts(session_root: Path, parent_id: str, *, parent_rollout=None,
                   started_at_unix=None, fresh=False) -> list[Path]:
    found = []
    for path in _session_candidates(session_root, started_at_unix=started_at_unix, parent_rollout=parent_rollout):
        meta = _first_metadata(path, fresh=fresh)
        if meta is not None and _typed_parent(meta) == parent_id:
            found.append(path)
    return found


def find_rollout(session_root: Path, session_id: str, *, started_at_unix=None, parent_rollout=None) -> Path | None:
    valid = []
    for path in _session_candidates(session_root, started_at_unix=started_at_unix,
                                    parent_rollout=parent_rollout, session_id=session_id):
        meta = _first_metadata(path)
        if meta is not None and meta["id"] == session_id:
            valid.append(path)
    if len(valid) > 1:
        raise ValueError("native session rollout is not unique")
    return valid[0] if valid else None


def native_skill_name_matches(actual: str, expected: str) -> bool:
    return actual == expected or (":" not in actual and actual == expected.split(":")[-1])


def native_operation_prompt(operation: dict) -> str:
    return "$" + operation["target_skill"] + " " + operation["args"] + "\n"


def validate_choice_request(request: dict, *, fixture: Path, assistant_text: str,
                            permitted_skills: set[str], seen_ids: set[str]) -> dict:
    if request.get("kind") != "artifact-delivery-choice" or request.get("state") != "waiting_user_choice":
        raise ValueError("unknown contractual gate")
    if request.get("target_skill") not in permitted_skills:
        raise ValueError("choice request belongs to an unpinned skill")
    identity = request.get("invocation_id")
    if not isinstance(identity, str) or not ID_RE.fullmatch(identity):
        raise ValueError("choice invocation identity missing")
    if identity in seen_ids:
        raise ValueError("choice request already answered")
    artifacts = request.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("choice has no real artifacts")
    checked = []
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("choice artifact path missing")
        path = Path(item["path"])
        if not path.is_absolute():
            raise ValueError("choice artifact must have an absolute fixture path")
        try:
            path.resolve(strict=True).relative_to(fixture.resolve(strict=True))
        except (ValueError, FileNotFoundError):
            raise ValueError("choice artifact is outside fixture")
        if not path.is_file():
            raise ValueError("choice artifact is not a file")
        sha = item.get("sha256")
        if not isinstance(sha, str) or digest(path) != sha:
            raise ValueError("choice artifact digest changed")
        if str(path) not in assistant_text or sha not in assistant_text:
            raise ValueError("current assistant did not present actual path and digest")
        checked.append({"path": str(path), "sha256": sha})
    if not all(choice in assistant_text for choice in ("accept-as-is", "light", "standard", "detailed")):
        raise ValueError("current assistant did not ask the declared depth choice")
    if not re.search(r"open|cat |開[きくけ]|確認", assistant_text, re.I):
        raise ValueError("current assistant omitted how to open artifacts")
    return {"invocation_id": identity, "target_skill": request["target_skill"], "artifacts": checked}


def external_fixture(cfg: dict) -> dict | None:
    value = cfg.get("external_confirmation_fixture")
    if value is None:
        return None
    required = {"guard_script", "hook_wrapper", "hook_event_log", "fake_adapter", "allowed_commands", "target_scopes"}
    if not isinstance(value, dict) or not required.issubset(value):
        raise ValueError("external confirmation fixture declaration incomplete")
    if "frontmatter.external_mutation_guard" not in sibling("live-trial-verdict").contract_gate_evidence(Path(cfg["skill_dir"]) / "SKILL.md"):
        raise ValueError("external confirmation requires the target's declared mutation guard")
    for key in ("guard_script", "hook_wrapper", "hook_event_log", "fake_adapter"):
        if not isinstance(value[key], str) or not Path(value[key]).is_absolute():
            raise ValueError(f"external fixture {key} must be absolute")
    adapter = Path(cfg["repo_root"]) / "tools/fake-gh.py"
    if (Path(value["fake_adapter"]) != adapter or adapter.is_symlink() or not adapter.is_file()
            or not adapter.resolve(strict=True).is_relative_to(Path(cfg["repo_root"]).resolve(strict=True))):
        raise ValueError("external confirmation requires the literal fixture fake-gh")
    commands = value["allowed_commands"]
    if not isinstance(commands, list) or not commands or any(not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv) for argv in commands):
        raise ValueError("external confirmation requires exact predeclared argv")
    scopes = value["target_scopes"]
    if not isinstance(scopes, list) or not scopes or not all(isinstance(x, str) and x for x in scopes):
        raise ValueError("external confirmation requires exact target scopes")
    relative = Path(value.get("request_relative", "external-confirmation-request.json"))
    if relative.is_absolute() or ".." in relative.parts or str(relative) in {"", "."}:
        raise ValueError("external confirmation request must remain in fixture")
    return value


def external_source_pin(cfg: dict) -> dict | None:
    fixture = external_fixture(cfg)
    if fixture is None:
        return None
    return {key + "_sha256": digest(Path(fixture[key])) for key in ("guard_script", "hook_wrapper", "fake_adapter")}


def external_guard(cfg: dict, state: dict):
    fixture = external_fixture(cfg)
    if fixture is None or external_source_pin(cfg) != state.get("external_fixture_pin"):
        raise ValueError("external fixture source/adapter pin drift")
    path = Path(fixture["guard_script"]).resolve(strict=True)
    if path.name != "build-external-mutation-guard.py" or path.parent.name != "scripts" or path.parents[1].name != "skill-governance-adapters":
        raise ValueError("external confirmation guard is not the canonical provider")
    if not any(path.is_relative_to(Path(root).resolve()) for root in cfg["loaded_provider_roots"]):
        raise ValueError("external confirmation guard is outside pinned providers")
    spec = importlib.util.spec_from_file_location("native_external_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def external_hook_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("external hook log contains a non-object record")
        rows.append(value)
    return rows


def validate_external_request(cfg: dict, state: dict, request: dict, *, assistant_text: str, inspected: dict) -> dict:
    fixture, guard = external_fixture(cfg), external_guard(cfg, state)
    if request.get("kind") != "external-mutation-confirmation" or request.get("state") != "waiting_user_confirmation":
        raise ValueError("unknown external confirmation checkpoint")
    identity, challenge = request.get("invocation_id"), request.get("challenge")
    if not isinstance(identity, str) or not ID_RE.fullmatch(identity) or any(r.get("invocation_id") == identity for r in state["responses"]):
        raise ValueError("external confirmation identity invalid/already answered")
    if not isinstance(challenge, str) or not re.fullmatch(r"[0-9A-F]{24}", challenge):
        raise ValueError("external confirmation challenge invalid")
    challenge_sha = hashlib.sha256(challenge.encode()).hexdigest()
    if any(r.get("challenge_sha256") == challenge_sha for r in state["responses"]):
        raise ValueError("external confirmation challenge already answered")
    fx = Path(cfg["repo_root"]).resolve(strict=True)
    if request.get("project_root") != str(fx):
        raise ValueError("external confirmation project root mismatch")
    if inspected.get("pending_tools") or not inspected.get("completed") or inspected.get("session_id") != state["session_id"]:
        raise ValueError("external confirmation requires a completed native turn")
    contexts = [row.get("payload", {}) for row in records(Path(state["native_rollout"])) if row.get("type") in {"session_meta", "turn_context"}]
    if not contexts or contexts[-1].get("cwd") != str(fx):
        raise ValueError("external confirmation native cwd mismatch")
    preview_id = request.get("preview_receipt_id")
    if not isinstance(preview_id, str) or not re.fullmatch(r"[0-9a-f]{32}", preview_id):
        raise ValueError("external confirmation preview identity invalid")
    directory = guard._state_dir(fx, create=False)
    path, preview = guard._receipt(directory, str(directory / f"preview-{preview_id}.json"), "preview", guard._key(directory, create=False))
    sha = digest(path)
    entrypoint = "plugin:" + cfg["target_skill"].replace(":", "/skills/", 1) + "/SKILL.md"
    if preview.get("entrypoint_ref") != entrypoint or preview.get("challenge_sha256") != challenge_sha or request.get("preview_sha256") != sha:
        raise ValueError("external confirmation signed preview binding mismatch")
    if preview.get("command_argv") not in fixture["allowed_commands"] or preview.get("target_scope") not in fixture["target_scopes"]:
        raise ValueError("external confirmation argv/target is not the predeclared fixture")
    if preview.get("command_sha256") != guard._command_sha256(preview["command_argv"]):
        raise ValueError("external confirmation command digest mismatch")
    if (f"GATE-CHALLENGE: {challenge}" not in assistant_text or str(path) not in assistant_text or sha not in assistant_text
            or preview["target_scope"] not in assistant_text or not all(arg in assistant_text for arg in preview["command_argv"])):
        raise ValueError("current assistant did not present the exact external preview")
    return {"kind": "external-mutation-confirmation", "invocation_id": identity, "target_skill": cfg["target_skill"],
            "challenge_sha256": challenge_sha, "preview_receipt_id": preview_id, "preview_sha256": sha,
            "preview_path": str(path), "command_sha256": preview["command_sha256"], "project_root": str(fx),
            "presentation_sha256": hashlib.sha256(assistant_text.encode()).hexdigest(),
            "hook_records_before": len(external_hook_rows(Path(fixture["hook_event_log"]))),
            "confirmation_receipt_created_by_controller": False}


def verify_external_confirmation(cfg: dict, state: dict, response: dict, turn: dict) -> None:
    fixture, guard = external_fixture(cfg), external_guard(cfg, state)
    rows = external_hook_rows(Path(fixture["hook_event_log"]))
    matching = []
    for index, row in enumerate(rows):
        if index < response["hook_records_before"]:
            continue
        if not isinstance(row.get("input_raw"), str) or not isinstance(row.get("output_raw"), str):
            raise ValueError("external hook log lacks original UTF-8 input/output")
        payload = json.loads(row["input_raw"])
        if payload.get("hook_event_name") == "UserPromptSubmit" and payload.get("session_id") == state["session_id"] and payload.get("prompt", "").strip().startswith("CONFIRM EXTERNAL MUTATION "):
            matching.append((index, row, payload))
    if len(matching) != 1:
        raise ValueError("exactly one actual native confirmation hook event is required")
    index, row, payload = matching[0]
    actual_prompt = payload.get("prompt")
    if (payload.get("cwd") != cfg["repo_root"] or not isinstance(actual_prompt, str)
            or not re.fullmatch(r"CONFIRM EXTERNAL MUTATION [0-9A-F]{24}\s*", actual_prompt)
            or hashlib.sha256(actual_prompt.strip().split()[-1].encode()).hexdigest() != response["challenge_sha256"]
            or row.get("runtime") != "codex" or row.get("returncode") != 0
            or row.get("guard_script_sha256") != state["external_fixture_pin"]["guard_script_sha256"]):
        raise ValueError("native confirmation hook identity/source mismatch")
    output = json.loads(row["output_raw"])
    context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
    if not context.startswith("[external-mutation-confirmation]\n"):
        raise ValueError("native confirmation hook did not emit canonical context")
    result = json.loads(context.split("\n", 1)[1])
    if result.get("status") != "confirmation-created":
        raise ValueError("native confirmation hook did not create a receipt")
    directory = guard._state_dir(Path(cfg["repo_root"]), create=False)
    path = Path(result["receipt_path"])
    if path.parent.resolve() != directory or not re.fullmatch(r"confirmation-[0-9a-f]{32}\.json", path.name):
        raise ValueError("native confirmation receipt path is not canonical")
    confirmation = json.loads(path.read_text())
    key = guard._key(directory, create=False)
    if not guard.hmac.compare_digest(confirmation.get("seal", ""), guard._seal(confirmation, key)):
        raise ValueError("native confirmation receipt seal invalid")
    if (digest(path) != result.get("receipt_sha256") or confirmation.get("kind") != "confirmation"
            or confirmation.get("producer") != "codex-user-prompt-submit"
            or confirmation.get("preview_receipt_id") != response["preview_receipt_id"]
            or confirmation.get("preview_receipt_sha256") != response["preview_sha256"]
            or confirmation.get("user_event_id") != guard._user_event_id(state["session_id"], actual_prompt.strip())):
        raise ValueError("native confirmation receipt binding/producer mismatch")
    preview_path = Path(response["preview_path"])
    if digest(preview_path) != response["preview_sha256"]:
        raise ValueError("external preview changed after confirmation")
    preview = json.loads(preview_path.read_text())
    if not preview["issued_at"] <= confirmation["issued_at"] <= preview["expires_at"]:
        raise ValueError("native confirmation was outside preview validity")
    proof = {"runtime": "codex", "native_hook_record_index": index, "native_hook_record": row,
             "preview": preview, "confirmation": confirmation, "confirmation_sha256": digest(path),
             "fixture_pin": state["external_fixture_pin"], "project_root": cfg["repo_root"],
             "entrypoint_ref": preview["entrypoint_ref"], "allowed_commands": fixture["allowed_commands"],
             "target_scopes": fixture["target_scopes"], "private_seal_verified": True,
             "public_hmac_recheck": "not_available: guard key remains private; public checks bind original event/output, receipt bytes, source and native user turn"}
    proof_path = Path(cfg["workdir"]) / "external-confirmations" / f"{response['invocation_id']}.json"
    if proof_path.exists():
        raise ValueError("external confirmation proof must not be overwritten")
    dump(proof_path, proof)
    response.update({"proof_ref": str(proof_path.relative_to(cfg["workdir"])), "proof_sha256": digest(proof_path),
                     "hook_event_index": index, "confirmation_receipt_sha256": digest(path),
                     "hook_verified": True})


def stop_owned_process_group(process, *, expected_pid: int) -> None:
    if process is None or process.pid != expected_pid or expected_pid <= 1:
        raise ValueError("process cleanup ownership mismatch")
    # The non-exiting supervisor reserves its PGID until our SIGKILL. Never kill
    # an exited leader's numeric group, which could have been reused meanwhile.
    if process.poll() is not None:
        raise RuntimeError("owned supervisor exited before scoped cleanup; group ownership unavailable")
    if os.getpgid(process.pid) != process.pid:
        raise ValueError("process group ownership mismatch")
    if getattr(process, "_harness_supervisor_ready", False):
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        else:
            raise RuntimeError("owned supervisor unexpectedly exited during cleanup grace")
    if process.poll() is not None or os.getpgid(process.pid) != process.pid:
        raise RuntimeError("supervisor ownership was lost before final group cleanup")
    os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=2)


def supervise_owned_turn(status_file: Path, argv: list[str]) -> None:
    """Remain group leader after the real CLI exits, until the owner reaps us."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    status = {"supervisor_pid": os.getpid(), "process_group": os.getpgrp(),
              "supervisor_ready": True, "child_pid": None, "child_returncode": None,
              "status": "supervisor_ready"}
    try:
        dump(status_file, status)
        # An ignored SIGTERM would survive exec. Give the actual CLI its normal
        # signal behavior while only this single-thread supervisor ignores TERM.
        def child_signals():
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        child = subprocess.Popen(argv, preexec_fn=child_signals)
        status.update({"child_pid": child.pid, "status": "child_running"})
        dump(status_file, status)
        status.update({"child_returncode": child.wait(), "status": "child_exited"})
        dump(status_file, status)
    except BaseException as exc:
        status.update({"status": "supervisor_error", "error": f"{type(exc).__name__}: {exc}"})
        try:
            dump(status_file, status)
        except OSError:
            pass  # owner wall cap still reaps the live, reserved group
    finally:
        while True:
            signal.pause()


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    required = {"run_id", "target_skill", "skill_dir", "repo_root", "private_dir", "workdir",
                "task_file", "scenario_file", "scenario_id", "codex_executable"}
    if not isinstance(cfg, dict) or not required.issubset(cfg):
        raise ValueError("runner config required fields missing")
    if not ID_RE.fullmatch(cfg["run_id"]):
        raise ValueError("invalid run_id")
    backend = sibling("live-trial-backend")
    if any(backend.deny_target_skill(target) for target in
           [cfg["target_skill"], *[item["target_skill"] for item in cfg.get("native_operations", [])]]):
        raise ValueError("recursive live trial target is denied")
    protected = [(key, Path(cfg[key])) for key in
                 ("private_dir", "skill_dir", "task_file", "scenario_file", "codex_executable")]
    protected.append(("config file", path.absolute()))
    if cfg.get("projection_receipt_file"):
        protected.append(("projection receipt", Path(cfg["projection_receipt_file"])))
    if cfg.get("codex_audit_fixture") is not None:
        protected.append(("Codex audit provider", Path(cfg["codex_audit_fixture"]["plugin_root"])))
    external = external_fixture(cfg)
    if external is not None:
        protected.extend(("external " + name, Path(external[name])) for name in ("guard_script", "hook_wrapper", "hook_event_log"))
    effective_provider_roots = cfg.get("loaded_provider_roots", [cfg["skill_dir"]])
    protected.extend(("loaded provider", Path(value)) for value in effective_provider_roots)
    protected.extend(("operation provider", Path(item["skill_dir"])) for item in cfg.get("native_operations", []))
    for key in ("skill_dir", "repo_root", "private_dir", "workdir", "task_file", "scenario_file"):
        value = Path(cfg[key])
        if not value.is_absolute():
            raise ValueError(f"{key} must be absolute")
        cfg[key] = str(value.resolve())
    for key in ("skill_dir", "repo_root"):
        if not Path(cfg[key]).is_dir():
            raise ValueError(f"{key} missing")
    # Secrets/control/providers are not writable additions to the Codex sandbox.
    if Path(cfg["private_dir"]).is_relative_to(Path(cfg["repo_root"])):
        raise ValueError("private_dir must be outside the actor workspace")
    if Path(cfg["workdir"]).is_relative_to(Path(cfg["repo_root"])):
        raise ValueError("workdir must be outside the actor workspace")
    if Path(cfg["skill_dir"]).is_relative_to(Path(cfg["repo_root"])):
        raise ValueError("loaded provider must be outside the writable actor workspace")
    writable = [Path(cfg["repo_root"]), (Path(cfg["workdir"]) / "out").resolve()]
    for label, original in protected:
        if not original.is_absolute():
            raise ValueError(f"{label} must be absolute")
        resolved = original.resolve()
        if any(resolved.is_relative_to(root) or root.is_relative_to(resolved) for root in writable):
            raise ValueError(f"{label} overlaps an actor writable root")
        # A mutable symlink entry/prefix inside a writable root is unsafe even
        # when its current target is outside. Preserve the ordinary CLI path
        # (Volta shims can depend on argv[0]) without accepting mutable aliases.
        for component in (original, *original.parents):
            entry = component.parent.resolve() / component.name
            if any(entry.is_relative_to(root) for root in writable):
                raise ValueError(f"{label} alias overlaps an actor writable root")
    cfg["loaded_provider_roots"] = [str(Path(value).resolve()) for value in effective_provider_roots]
    for operation in cfg.get("native_operations", []):
        operation["skill_dir"] = str(Path(operation["skill_dir"]).resolve())
    if cfg.get("projection_receipt_file"):
        cfg["projection_receipt_file"] = str(Path(cfg["projection_receipt_file"]).resolve())
    relative = Path(cfg.get("goal_seek_eval_root_relative", "eval-log"))
    if relative.is_absolute() or ".." in relative.parts or str(relative) in {"", "."}:
        raise ValueError("goal_seek_eval_root_relative must be a contained fixture-relative directory")
    cfg["goal_seek_eval_root_relative"] = str(relative)
    cfg["_config_file"] = str(path.resolve())
    codex_argv(cfg)
    return cfg


def state_path(cfg: dict) -> Path:
    return Path(cfg["private_dir"]) / "runner-state.json"


def load_state(cfg: dict) -> dict:
    return json.loads(state_path(cfg).read_text(encoding="utf-8"))


def closure(cfg: dict) -> str:
    return sibling("live-trial-verdict").skill_dir_tree_sha(Path(cfg["skill_dir"]), runtime="codex")


def verify_pin(cfg: dict, state: dict) -> None:
    if digest(Path(cfg["_config_file"])) != state["config_sha256"]:
        raise ValueError("controller config/operation plan drift")
    if closure(cfg) != state["behavior_sha256"]:
        raise ValueError("loaded provider behavior closure drift")
    if digest(Path(cfg["task_file"])) != state["task_sha256"]:
        raise ValueError("task input drift")
    if digest(Path(cfg["scenario_file"])) != state["scenario_file_sha256"]:
        raise ValueError("scenario contract drift")
    if state.get("projection_receipt_ref"):
        expected = state["projection_receipt_sha256"]
        if (digest(Path(cfg["projection_receipt_file"])) != expected
                or digest(Path(cfg["workdir"]) / state["projection_receipt_ref"]) != expected):
            raise ValueError("controller projection receipt drift")
    for operation in cfg.get("native_operations", []):
        expected = state.get("operation_source_sha256", {}).get(operation["id"])
        if expected != digest(Path(operation["skill_dir"]) / "SKILL.md"):
            raise ValueError("native operation source drift")
    if cfg.get("external_confirmation_fixture") is not None and external_source_pin(cfg) != state.get("external_fixture_pin"):
        raise ValueError("external fixture source/adapter pin drift")


def verify_native_skill_paths(cfg: dict, state: dict) -> dict:
    raw = state.get("native_rollout")
    if not raw:
        raise ValueError("native rollout unavailable for contractual response")
    live_usage(cfg, state)
    cached = Path(cfg["private_dir"]) / "live-usage-cache/transcript.jsonl"
    inspected = sibling("extract-codex-transcript").inspect_transcript(cached)
    roots = [Path(p).resolve() for p in cfg.get("loaded_provider_roots", [cfg["skill_dir"]])]
    for injection in inspected.get("injected_skills", []):
        path = Path(injection["path"]).resolve(strict=True)
        if not any(path.is_relative_to(root) for root in roots):
            raise ValueError("native skill activation outside pinned provider roots")
    return inspected


def pre_choice_agent_started(cfg: dict, state: dict, request: dict, inspected: dict) -> bool:
    target = request["target_skill"]
    sources = ([Path(cfg["skill_dir"])] if target == cfg["target_skill"] else [])
    sources += [Path(item["skill_dir"]) for item in cfg.get("native_operations", []) if item["target_skill"] == target]
    expected = {(path / "SKILL.md").resolve() for path in sources}
    starts = [item["index"] for item in inspected.get("injected_skills", [])
              if native_skill_name_matches(item["name"], target) and Path(item["path"]).resolve() in expected]
    if not starts:
        raise ValueError("native skill injection missing for declared choice")
    start = max(starts)
    for index, row in enumerate(records(Path(state["native_rollout"]))):
        payload = row.get("payload", {})
        if index <= start or row.get("type") != "response_item":
            continue
        if payload.get("type") in {"function_call", "custom_tool_call"} and payload.get("name", "").split(".")[-1] == "spawn_agent":
            return True
    return False


def bind_projection_receipt(cfg: dict, state: dict) -> None:
    if not cfg.get("projection_receipt_file"):
        return
    original = Path(cfg["projection_receipt_file"])
    raw = original.read_bytes()
    receipt = json.loads(raw)
    entries = receipt.get("skills") if isinstance(receipt, dict) else None
    if (not isinstance(entries, list) or not entries or receipt.get("source_body_modified") is not False
            or receipt.get("provider_inside_workspace") is not False):
        raise ValueError("invalid controller projection receipt")
    roots = [Path(value).resolve() for value in cfg.get("loaded_provider_roots", [cfg["skill_dir"]])]
    project_root = Path(cfg["repo_root"]).resolve() / ".agents/skills"
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"qualified_skill", "project_path", "source_path", "sha256"}:
            raise ValueError("invalid controller projection entry")
        qualified = entry["qualified_skill"]
        if not isinstance(qualified, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*:[A-Za-z0-9][A-Za-z0-9._-]*", qualified) or qualified in seen:
            raise ValueError("invalid or duplicate qualified projection name")
        seen.add(qualified)
        project, source = Path(entry["project_path"]), Path(entry["source_path"])
        if (not project.is_absolute() or not source.is_absolute() or project.name != "SKILL.md"
                or not project.absolute().is_relative_to(project_root)
                or project.resolve(strict=True) != source.resolve(strict=True)
                or not any(source.resolve().is_relative_to(root) for root in roots)
                or digest(source) != entry["sha256"]):
            raise ValueError("controller projection source/path/bytes mismatch")
    destination = Path(cfg["workdir"]) / "project-projection.json"
    if destination.exists():
        if destination.read_bytes() != raw:
            raise ValueError("existing public projection differs from controller original")
    else:
        with destination.open("xb") as stream:
            stream.write(raw)
    sha = hashlib.sha256(raw).hexdigest()
    if digest(original) != sha:
        raise ValueError("controller projection changed while binding")
    state.update({"projection_receipt_ref": "project-projection.json", "projection_receipt_sha256": sha})


def init_state(cfg: dict) -> dict:
    private, work = Path(cfg["private_dir"]), Path(cfg["workdir"])
    private.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    (work / "out").mkdir(exist_ok=True)
    environment = actor_environment(cfg)
    if (work / "verdict.json").exists() or (work / "evidence-freeze.json").exists():
        raise ValueError("prior evidence must never be overwritten")
    scenario = sibling("validate-live-trial-scenario-contract").load_scenario(
        Path(cfg["scenario_file"]), cfg["scenario_id"])
    budget = sibling("validate-live-trial-resource-budget").resource_budget(scenario)
    state = {"run_id": cfg["run_id"], "runtime": "codex", "session_id": None,
             "started_at_unix": time.time(), "elapsed": 0, "turns": [], "responses": [],
             "status": "prepared", "budget": budget, "behavior_sha256": closure(cfg),
             "task_sha256": digest(Path(cfg["task_file"])),
             "scenario_file_sha256": digest(Path(cfg["scenario_file"])),
             "config_sha256": digest(Path(cfg["_config_file"])),
             "goal_seek_eval_root_relative": cfg.get("goal_seek_eval_root_relative", "eval-log"),
             "writable_roots": [str(Path(cfg["repo_root"]).resolve()), str((work / "out").resolve())],
             "actor_environment_override": {key: environment[key] for key in ("TMPDIR", "TMPPREFIX")},
             "owner_pid": os.getpid(), "collected": False}
    operations = cfg.get("native_operations", [])
    identities = [item["id"] for item in operations]
    if len(identities) != len(set(identities)):
        raise ValueError("native operation identities must be unique")
    state["native_operation_turns"] = []
    state["operation_source_sha256"] = {item["id"]: digest(Path(item["skill_dir"]) / "SKILL.md")
                                        for item in operations}
    if cfg.get("external_confirmation_fixture") is not None:
        state["external_fixture_pin"] = external_source_pin(cfg)
        ext = external_fixture(cfg)
        state["external_fixture_policy"] = {"allowed_commands": ext["allowed_commands"], "target_scopes": ext["target_scopes"],
             "guard_source_ref": "external-confirmations/guard-source.py", "hook_wrapper_ref": "external-confirmations/hook-wrapper.py",
             "hook_events_ref": "external-confirmations/hook-events.jsonl", "fake_adapter_ref": "fixture-final/tools/fake-gh.py"}
        state["actor_environment_override"]["DEV_GRAPH_GH"] = environment["DEV_GRAPH_GH"]
    if cfg.get("codex_audit_fixture") is not None:
        sibling("record-codex-audit").initialize(cfg, state)
        state["actor_environment_override"].update(sibling("record-codex-audit").environment(cfg))
    bind_projection_receipt(cfg, state)
    # Creation is exclusive; a second controller cannot reset the clock.
    with state_path(cfg).open("x", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
    task_copy = work / "task.md"
    if task_copy.exists():
        if digest(task_copy) != state["task_sha256"]:
            raise ValueError("public task differs from actual stdin")
    else:
        copy_once(Path(cfg["task_file"]), task_copy)
    return state


def session_root() -> Path:
    # Read the ordinary CLI's session storage; never repurpose HOME/CODEX_HOME.
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"


def latest_agent_text(events: Path) -> str:
    text = ""
    for obj in records(events):
        item = obj.get("item", {})
        if obj.get("type") == "item.completed" and item.get("type") == "agent_message":
            text = item.get("text", "")
    return text


def native_turn_complete(events: Path) -> bool:
    kinds = [obj.get("type") for obj in records(events)]
    return bool(kinds) and kinds[-1] == "turn.completed"


def live_usage(cfg: dict, state: dict) -> dict:
    """Include strictly parent-bound descendants without mutating native originals."""
    raw = Path(state["native_rollout"])
    cache = Path(cfg["private_dir"]) / "live-usage-cache"
    cache.mkdir(exist_ok=True)
    main = cache / "transcript.jsonl"
    shutil.copyfile(raw, main)
    children = cache / "transcript/subagents"
    children.mkdir(parents=True, exist_ok=True)
    queue, seen = [state["session_id"]], {state["session_id"]}
    for path in children.glob("*.jsonl"):
        path.unlink()  # disposable measurement cache only, never frozen evidence
    while queue:
        parent = queue.pop()
        for child in child_rollouts(session_root(), parent, parent_rollout=raw,
                                    started_at_unix=state["started_at_unix"]):
            identity = _first_metadata(child)["id"]
            if identity in seen:
                continue
            seen.add(identity)
            queue.append(identity)
            shutil.copyfile(child, children / f"{identity}.jsonl")
    return sibling("extract-codex-transcript").transcript_token_usage(main)


def _elapsed(state: dict) -> float:
    return max(float(state.get("elapsed", 0)), time.time() - state["started_at_unix"])


def observe_native_audit(cfg: dict, state: dict) -> None:
    if cfg.get("codex_audit_fixture") is None:
        return
    root = Path(state["native_rollout"])
    paths, pending, seen = [root], [root], {state["session_id"]}
    while pending:
        current = pending.pop()
        meta = _first_metadata(current)
        for child in child_rollouts(session_root(), meta["id"], parent_rollout=root, started_at_unix=state["started_at_unix"]):
            identity = _first_metadata(child)["id"]
            if identity not in seen:
                seen.add(identity)
                paths.append(child)
                pending.append(child)
    sibling("record-codex-audit").observe(cfg, state, paths)


def execute_turn(cfg: dict, state: dict, prompt: Path) -> dict:
    verify_pin(cfg, state)
    if state.get("collected"):
        raise ValueError("collected session may not be resumed")
    elapsed = _elapsed(state)
    if elapsed >= state["budget"]["max_wall_clock_s"]:
        raise ValueError("scenario wall clock exhausted before resume")
    turn_no = len(state["turns"]) + 1
    private = Path(cfg["private_dir"])
    stdout, stderr = private / f"turn-{turn_no:03d}.jsonl", private / f"turn-{turn_no:03d}.stderr.log"
    argv = codex_argv(cfg, state["session_id"])
    child_status_file = private / f"turn-{turn_no:03d}.child-status.json"
    if child_status_file.exists():
        raise ValueError("prior supervisor status must not be reused")
    supervisor_argv = [sys.executable, "-B", str(Path(__file__).resolve()), SUPERVISOR_MODE,
                       str(child_status_file), "--", *argv]
    prior_raw = Path(state["native_rollout"]) if state.get("native_rollout") else None
    raw_count_before = len(list(records(prior_raw))) if prior_raw is not None else 0
    raw_sha_before = digest(prior_raw) if prior_raw is not None else None
    raw_bytes_before = prior_raw.stat().st_size if prior_raw is not None else 0
    process = None
    terminated = None
    execution_error = None
    child_status = {}
    with prompt.open("rb") as inp, stdout.open("xb") as out, stderr.open("xb") as err:
        process = subprocess.Popen(supervisor_argv, stdin=inp, stdout=out, stderr=err,
                                   cwd=cfg["repo_root"], env=actor_environment(cfg), start_new_session=True)
        state["active_process"] = {"pid": process.pid, "process_group": process.pid,
                                    "run_id": cfg["run_id"], "owner_pid": os.getpid(),
                                    "role": "owned-python-supervisor"}
        dump(state_path(cfg), state)
        try:
            while process.poll() is None:
                if child_status_file.is_file():
                    child_status = json.loads(child_status_file.read_text())
                    if (child_status.get("supervisor_pid") != process.pid
                            or child_status.get("process_group") != process.pid):
                        raise ValueError("supervisor status ownership mismatch")
                    process._harness_supervisor_ready = child_status.get("supervisor_ready") is True
                    if child_status.get("status") in {"child_exited", "supervisor_error"}:
                        break
                state["elapsed"] = _elapsed(state)
                if state["elapsed"] >= state["budget"]["max_wall_clock_s"]:
                    terminated = "HARD_CAP"
                    break
                if not state["session_id"]:
                    ids = {obj.get("thread_id") for obj in records(stdout)
                           if obj.get("type") == "thread.started"}
                    ids.discard(None)
                    if len(ids) > 1:
                        raise ValueError("multiple native parent sessions in one turn")
                    if ids:
                        state["session_id"] = ids.pop()
                if state["session_id"]:
                    raw = find_rollout(session_root(), state["session_id"],
                                       started_at_unix=state["started_at_unix"],
                                       parent_rollout=state.get("native_rollout"))
                    if raw:
                        state["native_rollout"] = str(raw)
                        usage = live_usage(cfg, state)
                        observe_native_audit(cfg, state)
                        if usage.get("measured") and usage["total_tokens"] > state["budget"]["max_total_tokens"]:
                            terminated = "HARD_CAP"
                            break
                time.sleep(0.5)
        except Exception as exc:
            execution_error = f"{type(exc).__name__}: {exc}"
            terminated = "RUNNER_ERROR"
        finally:
            try:
                stop_owned_process_group(process, expected_pid=process.pid)
            except Exception as exc:
                state["status"] = "CLEANUP_FAILED"
                state["cleanup_error"] = f"{type(exc).__name__}: {exc}"
                dump(state_path(cfg), state)
                raise
            else:
                state.pop("active_process", None)
                dump(state_path(cfg), state)
    if child_status_file.is_file():
        child_status = json.loads(child_status_file.read_text())
    actual_returncode = child_status.get("child_returncode")
    if not state["session_id"]:
        ids = {obj.get("thread_id") for obj in records(stdout) if obj.get("type") == "thread.started"}
        ids.discard(None)
        if len(ids) == 1:
            state["session_id"] = ids.pop()
    if state["session_id"]:
        raw = find_rollout(session_root(), state["session_id"],
                           started_at_unix=state["started_at_unix"], parent_rollout=state.get("native_rollout"))
        if raw:
            state["native_rollout"] = str(raw)
            observe_native_audit(cfg, state)
    state["elapsed"] = _elapsed(state)
    turn = {"number": turn_no, "argv": argv, "stdin_sha256": digest(prompt),
            "stdout": str(stdout), "stderr": str(stderr), "returncode": actual_returncode,
            "cli_pid": child_status.get("child_pid"), "supervisor_pid": process.pid,
            "supervisor_returncode": process.returncode, "supervisor_argv": supervisor_argv,
            "supervisor_status_file": str(child_status_file), "scoped_group_reaped": True,
            "native_turn_complete": native_turn_complete(stdout), "terminated": terminated,
            "native_records_before": raw_count_before, "native_bytes_before": raw_bytes_before,
            "native_prefix_sha256_before": raw_sha_before, "runner_error": execution_error}
    if prior_raw is not None:
        prefix = prior_raw.read_bytes()[:raw_bytes_before]
        if hashlib.sha256(prefix).hexdigest() != raw_sha_before:
            state["status"] = "NATIVE_HISTORY_DRIFT"
            state["turns"].append(turn)
            dump(state_path(cfg), state)
            raise ValueError("native resume rewrote prior transcript bytes")
    state["turns"].append(turn)
    state["status"] = terminated or ("turn_complete" if actual_returncode == 0 and turn["native_turn_complete"] else "BLOCKED")
    dump(state_path(cfg), state)
    return turn


def validate_operation_request(cfg: dict, state: dict, request: dict) -> dict:
    if request.get("kind") != "native-operation" or request.get("state") != "waiting_operation":
        raise ValueError("unknown native operation checkpoint")
    completed = state.get("native_operation_turns", [])
    operations = cfg.get("native_operations", [])
    if len(completed) >= len(operations):
        raise ValueError("no further declared native operation")
    expected = operations[len(completed)]
    if (request.get("operation_id") != expected["id"]
            or request.get("target_skill") != expected["target_skill"]
            or request.get("args") != expected["args"]):
        raise ValueError("native operation order/skill/args differ from declared task")
    if expected["target_skill"] not in set(cfg.get("permitted_skills", [cfg["target_skill"]])):
        raise ValueError("native operation skill is not pinned")
    return expected


def _marker(cfg: dict, state: dict) -> bool:
    marker = Path(cfg["workdir"]) / "out/status.json"
    if not marker.is_file():
        return False
    value = json.loads(marker.read_text())
    if value.get("status") not in {"PASS", "FAIL", "ERROR", "BLOCKED"}:
        raise ValueError("invalid terminal status marker")
    if value.get("status") == "PASS" and sum(bool(r.get("submitted")) for r in state.get("native_operation_turns", [])) != len(cfg.get("native_operations", [])):
        raise ValueError("terminal PASS before declared native operations completed")
    return True


def verify_operation_activation(cfg: dict, state: dict, operation: dict, turn: dict) -> None:
    live_usage(cfg, state)
    cached = Path(cfg["private_dir"]) / "live-usage-cache/transcript.jsonl"
    inspected = sibling("extract-codex-transcript").inspect_transcript(
        cached, skill_dir=Path(operation["skill_dir"]), target_skill=operation["target_skill"])
    injections = [item["index"] for item in inspected.get("injected_skills", [])
                  if native_skill_name_matches(item["name"], operation["target_skill"]) and item["index"] >= turn["native_records_before"]
                  and Path(item["path"]).resolve() == (Path(operation["skill_dir"]) / "SKILL.md").resolve()]
    if not injections:
        raise ValueError("new native operation skill injection missing")
    call_indexes = {row.get("payload", {}).get("call_id"): index
                    for index, row in enumerate(records(cached))
                    if row.get("type") == "response_item"
                    and row.get("payload", {}).get("type") in {"function_call", "custom_tool_call"}}
    expected_path = (Path(operation["skill_dir"]) / "SKILL.md").resolve()
    expected_sha = digest(expected_path)
    if not any(item.get("skill") == operation["target_skill"]
               and Path(item.get("path", "")).resolve() == expected_path
               and item.get("source_sha256") == expected_sha
               and call_indexes.get(item["read_call_id"], -1) >= max(injections)
               for item in inspected.get("activations", [])):
        raise ValueError("new native operation did not Read its pinned skill bytes")


def drive(cfg: dict, state: dict, prompt: Path, response_pending=None) -> dict:
    while True:
        turn = execute_turn(cfg, state, prompt)
        if response_pending is not None:
            if response_pending["kind"] == "native-operation" and state["status"] == "turn_complete":
                expected = next(item for item in cfg["native_operations"] if item["id"] == response_pending["operation_id"])
                try:
                    verify_operation_activation(cfg, state, expected, turn)
                except ValueError as exc:
                    response_pending["native_validation_error"] = str(exc)
                    state["status"] = "NATIVE_OPERATION_ACTIVATION_FAIL"
            if response_pending["kind"] == "external-mutation-confirmation" and state["status"] == "turn_complete":
                try:
                    verify_external_confirmation(cfg, state, response_pending, turn)
                except (ValueError, OSError, KeyError) as exc:
                    response_pending["native_validation_error"] = str(exc)
                    state["status"] = "EXTERNAL_CONFIRMATION_FAIL"
            response_pending["submitted"] = state["status"] == "turn_complete"
            response_pending["native_turn"] = turn["number"]
            dump(state_path(cfg), state)
            response_pending = None
        if state["status"] != "turn_complete":
            return state
        if _marker(cfg, state):
            state["status"] = "DONE"
            dump(state_path(cfg), state)
            return state
        external = external_fixture(cfg)
        if external is not None:
            external_path = Path(cfg["repo_root"]) / external.get("request_relative", "external-confirmation-request.json")
            if not external_path.resolve().is_relative_to(Path(cfg["repo_root"]).resolve()):
                raise ValueError("external confirmation request escapes fixture")
            request = json.loads(external_path.read_text()) if external_path.is_file() else None
            previous_external = next((r for r in state["responses"] if request and r.get("kind") == "external-mutation-confirmation" and r["invocation_id"] == request.get("invocation_id")), None)
            if previous_external and digest(external_path) != previous_external["request_sha256"]:
                raise ValueError("answered external confirmation checkpoint was rewritten")
            if request is not None and previous_external is None:
                checked = validate_external_request(cfg, state, request,
                          assistant_text=latest_agent_text(Path(turn["stdout"])), inspected=verify_native_skill_paths(cfg, state))
                prompt = Path(cfg["private_dir"]) / f"external-confirmation-{len(state['responses']) + 1:03d}.txt"
                with prompt.open("x", encoding="utf-8") as stream:
                    stream.write(f"CONFIRM EXTERNAL MUTATION {request['challenge']}\n")
                response = {**checked, "request_sha256": digest(external_path), "sent_after_turn": turn["number"],
                            "prompt_sha256": digest(prompt), "submitted": False}
                state["responses"].append(response)
                dump(state_path(cfg), state)
                response_pending = response
                continue
        request_path = Path(cfg.get("choice_request", str(Path(cfg["repo_root"]) / "artifact-choice-request.json")))
        request = json.loads(request_path.read_text()) if request_path.is_file() else None
        previous = next((r for r in state["responses"] if request and r["invocation_id"] == request.get("invocation_id")), None)
        if previous and digest(request_path) != previous["request_sha256"]:
            raise ValueError("answered choice checkpoint was rewritten")
        if request is not None and previous is None:
            inspected = verify_native_skill_paths(cfg, state)
            if pre_choice_agent_started(cfg, state, request, inspected):
                raise ValueError("pre-choice agent already started; do not repair ordering by replying")
            checked = validate_choice_request(request, fixture=Path(cfg["repo_root"]),
                      assistant_text=latest_agent_text(Path(turn["stdout"])),
                      permitted_skills=set(cfg.get("permitted_skills", [cfg["target_skill"]])),
                      seen_ids={r["invocation_id"] for r in state["responses"]})
            prompt = Path(cfg["private_dir"]) / f"choice-{len(state['responses']) + 1:03d}.txt"
            with prompt.open("x", encoding="utf-8") as stream:
                stream.write("standard\n")
            response = {**checked, "kind": "artifact-delivery-choice", "choice": "standard",
                        "request_sha256": digest(request_path), "sent_after_turn": turn["number"],
                        "prompt_sha256": digest(prompt), "submitted": False}
            state["responses"].append(response)
            dump(state_path(cfg), state)
            response_pending = response
            continue
        operation_path = Path(cfg.get("operation_request", str(Path(cfg["repo_root"]) / "native-operation-request.json")))
        operation = json.loads(operation_path.read_text()) if operation_path.is_file() else None
        old = next((r for r in state["native_operation_turns"] if operation and r["operation_id"] == operation.get("operation_id")), None)
        if old and digest(operation_path) != old["request_sha256"]:
            raise ValueError("consumed native operation checkpoint was rewritten")
        if operation is not None and old is None:
            inspected = verify_native_skill_paths(cfg, state)
            if inspected.get("pending_tools") or not inspected.get("completed"):
                raise ValueError("native operation handoff before current invocation completed")
            expected = validate_operation_request(cfg, state, operation)
            prompt = Path(cfg["private_dir"]) / f"operation-{len(state['native_operation_turns']) + 1:03d}.txt"
            with prompt.open("x", encoding="utf-8") as stream:
                stream.write(native_operation_prompt(expected))
            response = {"kind": "native-operation", "operation_id": expected["id"],
                        "target_skill": expected["target_skill"], "args": expected["args"],
                        "source_sha256": state["operation_source_sha256"][expected["id"]],
                        "request_sha256": digest(operation_path), "sent_after_turn": turn["number"],
                        "prompt_sha256": digest(prompt), "submitted": False}
            state["native_operation_turns"].append(response)
            dump(state_path(cfg), state)
            response_pending = response
            continue
        state["status"] = "WAITING_DECLARED_RESPONSE"
        dump(state_path(cfg), state)
        return state


def run(cfg: dict) -> dict:
    state = load_state(cfg) if state_path(cfg).exists() else init_state(cfg)
    if state["turns"]:
        raise ValueError("existing run requires explicit continue; fresh clock must not reset")
    return drive(cfg, state, Path(cfg["task_file"]))


def continue_run(cfg: dict, response_file: Path) -> dict:
    state = load_state(cfg)
    if state["status"] != "WAITING_DECLARED_RESPONSE":
        raise ValueError("no pending declared response")
    # This is explicit controller input, not automatic approval of an unknown UI.
    # Caller must provide the already-authorized fixture response through a file.
    turn_no = len(state["turns"]) + 1
    state.setdefault("manual_response_turns", []).append({"turn": turn_no,
                         "stdin_sha256": digest(response_file), "classified_as": "rescue"})
    dump(state_path(cfg), state)
    return drive(cfg, state, response_file)


def public_bytes(raw: bytes, secrets: list[str], aliases: dict[str, str] | None = None) -> bytes:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    for original, alias in (aliases or {}).items():
        text = text.replace(original, alias)
        text = text.replace(json.dumps(original)[1:-1], json.dumps(alias)[1:-1])
    for secret in secrets:
        if len(secret) >= 8:
            text = text.replace(secret, "[REDACTED_FIXTURE_SECRET]")
    text = TOKEN_RE.sub("[REDACTED_API_TOKEN]", text)
    text = re.sub(r"\b(?:Bearer|Basic)[ \t]+[A-Za-z0-9._~+/-]{8,}=*", "[REDACTED_AUTHORIZATION]", text, flags=re.I)
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
                  "[REDACTED_PRIVATE_KEY]", text, flags=re.S)
    return text.encode("utf-8")


def fixture_ignored(root: Path, parent: Path, name: str) -> bool:
    return (name in {".git", ".agents", ".codex", "__pycache__"}
            or (parent == root and name == ".native-tmp") or secret_file(Path(name)) or Path(name).suffix == ".pyc")


def tree_inventory(root: Path, *, fixture: bool = False) -> dict:
    """Record links as links, never read their external targets."""
    result = {}
    def scan_error(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=scan_error):
        parent = Path(directory)
        dirs[:] = sorted(name for name in dirs if not fixture or not fixture_ignored(root, parent, name))
        for name in sorted([*dirs, *files]):
            if fixture and fixture_ignored(root, parent, name):
                continue
            path = parent / name
            metadata = path.lstat()
            item = {"mode": stat.S_IMODE(metadata.st_mode), "mtime_ns": metadata.st_mtime_ns}
            if path.is_symlink():
                target = os.readlink(path)
                item.update(kind="symlink", target=target, target_sha256=hashlib.sha256(os.fsencode(target)).hexdigest())
            elif path.is_dir():
                item["kind"] = "directory"
            elif path.is_file():
                item.update(kind="file", sha256=digest(path), bytes=metadata.st_size)
            else:
                raise ValueError("unsupported collection entry: " + str(path))
            result[str(path.relative_to(root))] = item
    return result


def snapshot_fixture(source: Path, destination: Path) -> dict:
    """Publish internal pointers relative to the snapshot, preserving originals."""
    source = source.resolve(strict=True)
    before = tree_inventory(source, fixture=True)
    links = []
    for relative, item in before.items():
        if item["kind"] != "symlink":
            continue
        original = source / relative
        try:
            target = original.resolve(strict=True)
            target_relative = target.relative_to(source)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("fixture symlink escapes or has no resolvable target: " + relative) from exc
        if str(target_relative) not in before and target_relative != Path("."):
            raise ValueError("fixture symlink points to an excluded target: " + relative)
        public_target = os.path.relpath(destination / target_relative, (destination / relative).parent)
        links.append({"path": relative, "original_target": item["target"], "original_target_sha256": item["target_sha256"],
                      "original_metadata": {k:item[k] for k in ("mode", "mtime_ns")},
                      "resolved_fixture_target": str(target_relative), "public_target": public_target,
                      "target_evidence": before.get(str(target_relative), {"kind":"fixture-root"})})
    shutil.copytree(source, destination, symlinks=True,
                    ignore=lambda directory, names: [name for name in names if fixture_ignored(source, Path(directory), name)])
    copied = tree_inventory(destination)
    if copied != before or tree_inventory(source, fixture=True) != before:
        raise ValueError("fixture bytes/metadata changed during snapshot")
    for link in links:
        path = destination / link["path"]
        path.unlink()  # Only this new publication's copied link; the original is untouched.
        path.symlink_to(link["public_target"])
    for link in links:
        target = (destination / link["path"]).resolve(strict=True)
        target.relative_to(destination.resolve(strict=True))
        if target != (destination / link["resolved_fixture_target"]).resolve(strict=True):
            raise ValueError("published symlink target mismatch")
    if tree_inventory(source, fixture=True) != before:
        raise ValueError("original fixture changed during publication")
    return {"source_inventory": before, "links": links, "original_fixture_modified": False,
            "rule": "resolve-in-original-fixture-then-publish-snapshot-relative; external/secret targets rejected"}


def publication_paths(cfg: dict, ordinal: int) -> tuple[Path, Path]:
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
        raise ValueError("collection publication ordinal must be a positive integer")
    suffix = "" if ordinal == 1 else f"-{ordinal}"
    original = Path(cfg["workdir"])
    return (original.with_name(original.name + "-publication-recovery" + suffix),
            Path(cfg["private_dir"]) / ("raw-at-recollection" + suffix))


def fixed_child_metadata(path: Path) -> dict:
    """A fixed collection uses exact UUID aliases, never live rollout discovery."""
    with path.open(encoding="utf-8") as stream:
        first = json.loads(stream.readline())
    meta = first.get("payload") if isinstance(first, dict) and first.get("type") == "session_meta" else None
    if (not isinstance(meta, dict) or not isinstance(meta.get("id"), str)
            or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", meta["id"])
            or path.name != meta["id"] + ".jsonl"):
        raise ValueError("fixed child snapshot filename and metadata identity differ")
    _typed_parent(meta)
    return meta


def fixed_native_preflight(raw: Path, session_id: str) -> dict:
    main = raw / "transcript.jsonl"
    with main.open(encoding="utf-8") as stream:
        first = json.loads(stream.readline())
    if first.get("type") != "session_meta" or first.get("payload", {}).get("id") != session_id:
        raise ValueError("fixed original main session identity mismatch")
    for child in sorted((raw / "transcript/subagents").glob("*.jsonl")):
        fixed_child_metadata(child)
    info = sibling("extract-codex-transcript").inspect_transcript(main)
    if info.get("format_errors"):
        raise ValueError("fixed native evidence invalid before recollection: " + ",".join(info["format_errors"]))
    return {"session_id": info["session_id"], "agent_sessions": info["agent_sessions"],
            "format_errors": info["format_errors"], "completed": info["completed"]}


def previous_collection_attempts(cfg: dict, state: dict, ordinal: int, logs: list[Path], secrets: list[str], aliases: dict) -> list[dict]:
    if len(logs) != ordinal - 1:
        raise ValueError("each previous publication ordinal requires its original failure log")
    records = []
    original_raw = Path(cfg["private_dir"]) / "raw-at-collection"
    original_work = Path(cfg["workdir"])
    writable = [Path(cfg["repo_root"]).resolve(), (original_work / "out").resolve()]
    for number, error_log in enumerate(logs, 1):
        work, raw = publication_paths(cfg, number)
        if (not work.is_dir() or not raw.is_dir() or (work / "evidence-freeze.json").exists()
                or (work / "verdict.json").exists()):
            raise ValueError("prior collection ordinal missing or already frozen/finalized")
        if not error_log.is_absolute() or not error_log.is_file() or any(error_log.resolve().is_relative_to(root) for root in writable):
            raise ValueError("previous failure log must be a controller-owned absolute file")
        if not error_log.read_text().strip().startswith("[ERROR]"):
            raise ValueError("previous publication failure log has no native collector error")
        for relative, item in tree_inventory(raw).items():
            if item["kind"] == "directory":
                continue
            if item["kind"] != "file":
                raise ValueError("prior fixed raw cannot contain links")
            path = raw / relative
            if relative == "runner-state-before.json":
                expected = state_path(cfg)
            elif re.fullmatch(r"previous-failure-[0-9]{3}\.log", relative):
                index = int(relative.removeprefix("previous-failure-").removesuffix(".log")) - 1
                if index >= len(logs):
                    raise ValueError("unknown prior failure log copy")
                expected = logs[index]
            else:
                expected = original_raw / relative
                if not expected.is_file() and relative.startswith("fixture-final/"):
                    expected = Path(cfg["repo_root"]) / relative.removeprefix("fixture-final/")
            if not expected.is_file() or path.read_bytes() != expected.read_bytes():
                raise ValueError("previous collection raw differs from fixed original: " + relative)
        # Previously published native copies must still be the exact declared
        # publication transform of the fixed raw; no new interpretation is used.
        for path in sorted(raw.rglob("*")):
            relative = str(path.relative_to(raw))
            if path.is_file() and relative != "runner-state-before.json" and not relative.startswith("previous-failure-"):
                published = work / relative
                if published.is_file() and published.read_bytes() != public_bytes(path.read_bytes(), secrets, aliases):
                    raise ValueError("previous partial publication differs from fixed raw: " + relative)
        records.append({"ordinal": number, "workdir": str(work), "raw_root": str(raw),
                        "public_inventory": tree_inventory(work), "raw_inventory": tree_inventory(raw),
                        "failure_log_path": str(error_log), "failure_log_sha256": digest(error_log),
                        "inventory_time": "recollection preflight observation, not a retrospective freeze"})
    return records


def recovery_preflight(cfg: dict, state: dict, secrets: list[str], aliases: dict[str, str] | None = None,
                       *, ordinal: int = 1, failure_logs: list[Path] | None = None) -> dict:
    work, private = Path(cfg["workdir"]), Path(cfg["private_dir"])
    observation = private / "collection-failure-observation.json"
    failure = json.loads(observation.read_text())
    original_raw = private / "raw-at-collection"
    if (failure.get("state") != "failed_collection_preserved_no_retry" or failure.get("actor_collected") is not False
            or failure.get("evidence_freeze_exists") is not False or state.get("collected")
            or (work / "verdict.json").exists() or (work / "evidence-freeze.json").exists()
            or Path(failure.get("original_fixed_raw_main", "")).resolve() != (original_raw / "transcript.jsonl").resolve()
            or digest(original_raw / "transcript.jsonl") != failure.get("original_fixed_raw_sha256")
            or digest(work / "transcript.jsonl") != failure.get("partial_public_main_sha256")):
        raise ValueError("recollection requires the unchanged observed partial failure and fixed original raw")
    source, partial = Path(cfg["repo_root"]), work / "fixture-final"
    expected, prior = tree_inventory(source, fixture=True), tree_inventory(partial)
    if set(expected) != set(prior):
        raise ValueError("partial fixture and original fixture entries differ")
    for relative, item in expected.items():
        old = prior[relative]
        if item["kind"] != old["kind"] or item["mode"] != old["mode"]:
            raise ValueError("partial fixture type/mode differs from original: " + relative)
        if item["kind"] == "symlink" and item != old:
            raise ValueError("partial fixture original link metadata differs: " + relative)
        if item["kind"] == "file":
            raw, published = (source / relative).read_bytes(), (partial / relative).read_bytes()
            if published not in (raw, public_bytes(raw, secrets, aliases)):
                raise ValueError("partial fixture bytes differ from original: " + relative)
            fixed = original_raw / "fixture-final" / relative
            if fixed.exists() and fixed.read_bytes() != raw:
                raise ValueError("fixed fixture raw differs from original: " + relative)
    native = fixed_native_preflight(original_raw, state["session_id"])
    previous = previous_collection_attempts(cfg, state, ordinal, failure_logs or [], secrets, aliases or {})
    return {"failure_observation_sha256": digest(observation), "original_state_sha256": digest(state_path(cfg)),
            "original_workdir": str(work), "original_raw_root": str(original_raw),
            "original_raw_inventory": tree_inventory(original_raw), "partial_public_inventory": tree_inventory(work),
            "source_fixture_inventory": expected,
            "fixed_native_validation": native, "publication_ordinal": ordinal, "previous_failed_attempts": previous,
            "inventory_time": "official recollection preflight; original partial was not retrospectively frozen"}


def collection_workdir(cfg: dict, state: dict) -> Path:
    original = Path(cfg["workdir"])
    binding = state.get("collection_publication")
    if binding is None:
        return original
    expected, _raw = publication_paths(cfg, binding.get("ordinal", 1) if isinstance(binding, dict) else 1)
    if not isinstance(binding, dict) or binding.get("original_workdir") != str(original) or binding.get("workdir") != str(expected):
        raise ValueError("invalid collection publication binding")
    receipt = expected / "collection-recovery-receipt.json"
    if digest(receipt) != binding.get("receipt_sha256"):
        raise ValueError("collection recovery receipt drift")
    return expected


def collect(cfg: dict, *, recollect: bool = False, publication_ordinal: int = 1,
            previous_failure_logs: list[Path] | None = None) -> dict:
    state = load_state(cfg)
    verify_pin(cfg, state)
    if state.get("active_process") or state.get("collected"):
        raise ValueError("only a stopped, uncollected trial can be frozen")
    work, private = Path(cfg["workdir"]), Path(cfg["private_dir"])
    if (work / "evidence-freeze.json").exists():
        raise ValueError("frozen evidence exists")
    secrets, excluded = [], []
    native_temporary = Path(cfg["repo_root"]) / ".native-tmp"
    if native_temporary.exists():
        excluded.append(".native-tmp")
    for path in Path(cfg["repo_root"]).rglob("*"):
        if ".native-tmp" == path.relative_to(cfg["repo_root"]).parts[0]:
            continue
        if path.is_file() and secret_file(path):
            excluded.append(str(path.relative_to(cfg["repo_root"])))
            if path.stat().st_size <= 65536:
                try:
                    secrets.append(path.read_text().strip())
                except UnicodeDecodeError:
                    pass
    aliases = {entry["path"]: "catalog-exclusion-" + hashlib.sha256(entry["path"].encode()).hexdigest()[:24] + "/SKILL.md"
               for entry in cfg.get("native_skill_exclusions", [])}
    recovery = recovery_preflight(cfg, state, secrets, aliases, ordinal=publication_ordinal,
                                  failure_logs=previous_failure_logs) if recollect else None
    fixed_prior = private / "raw-at-collection" if recollect else None
    if recollect:
        work, recovery_raw = publication_paths(cfg, publication_ordinal)
        if work.exists() or recovery_raw.exists():
            raise ValueError("recollection publication/attempt already exists; never overwrite or retry")
        work.mkdir()
    rawdir = recovery_raw if recollect else private / "raw-at-collection"
    rawdir.mkdir(exist_ok=False)
    if recollect:
        copy_once(state_path(cfg), rawdir / "runner-state-before.json")
        for number, error_log in enumerate(previous_failure_logs or [], 1):
            copy_once(error_log, rawdir / f"previous-failure-{number:03d}.log")
        original_work = Path(cfg["workdir"])
        for name in ("task.md", state.get("projection_receipt_ref")):
            if name:
                copy_once(original_work / name, work / name)
        if (original_work / "out").is_dir():
            if any(item["kind"] == "symlink" for item in tree_inventory(original_work / "out").values()):
                raise ValueError("recollection output markers may not contain symlinks")
            shutil.copytree(original_work / "out", work / "out", symlinks=True)
        for response in state.get("responses", []):
            if response.get("proof_ref"):
                path = original_work / response["proof_ref"]
                if digest(path) != response["proof_sha256"]:
                    raise ValueError("original external proof drift")
                copy_once(path, work / response["proof_ref"])
    copies = []
    def publish(source: Path, destination: Path):
        if fixed_prior is not None:
            source = fixed_prior / destination.relative_to(work)
            if not source.is_file() or source.is_symlink():
                raise ValueError("recollection cannot replace an unavailable fixed original: " + str(source))
        fixed = rawdir / destination.relative_to(work)
        copy_once(source, fixed)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = public_bytes(fixed.read_bytes(), secrets, aliases)
        with destination.open("xb") as stream:
            stream.write(data)
        copies.append({"path": str(destination.relative_to(work)),
                       "original_sha256": digest(fixed), "public_sha256": digest(destination)})
    if state.get("native_rollout"):
        if not recollect:
            verify_native_skill_paths(cfg, state)
        publish(Path(state["native_rollout"]), work / "transcript.jsonl")
        pending = [state["session_id"]]
        seen = set(pending)
        while pending:
            parent_id = pending.pop()
            candidates = (list((fixed_prior / "transcript/subagents").glob("*.jsonl")) if recollect else
                          child_rollouts(session_root(), parent_id, parent_rollout=Path(state["native_rollout"]),
                                         started_at_unix=state["started_at_unix"], fresh=True))
            for child in candidates:
                meta = fixed_child_metadata(child) if recollect else _first_metadata(child)
                identity = meta["id"]
                if recollect and _typed_parent(meta) != parent_id:
                    continue
                if identity in seen:
                    continue
                seen.add(identity)
                pending.append(identity)
                publish(child, work / "transcript/subagents" / f"{identity}.jsonl")
        native_validation = sibling("extract-codex-transcript").inspect_transcript(rawdir / "transcript.jsonl")
        dump(work / "native-collection-validation.json", {
            "full_frozen_raw_revalidated": True,
            "format_errors": native_validation.get("format_errors", []),
            "pending_tools": native_validation.get("pending_tools", []),
            "agent_sessions": native_validation.get("agent_sessions", []),
            "completed": native_validation.get("completed", False),
            "note": "Missing spawned children and malformed native records remain acceptance failures; this report never grants PASS."})
    for turn in state["turns"]:
        for key in ("stdout", "stderr", "supervisor_status_file"):
            if key not in turn:
                continue
            path = Path(turn[key])
            publish(path, work / "native-exec" / path.name)
    if cfg.get("external_confirmation_fixture") is not None:
        ext = external_fixture(cfg)
        for key, name in (("guard_script", "guard-source.py"), ("hook_wrapper", "hook-wrapper.py"), ("hook_event_log", "hook-events.jsonl")):
            path = Path(ext[key])
            if path.is_file():
                publish(path, work / "external-confirmations" / name)
    if cfg.get("codex_audit_fixture") is not None:
        audit = private / "codex-audit"
        if not audit.is_dir():
            raise ValueError("Codex audit host evidence is missing")
        for path in sorted(audit.rglob("*")):
            if path.is_symlink():
                raise ValueError("Codex audit evidence must not contain symlinks")
            if path.is_file() and not secret_file(path):
                publish(path, work / "codex-audit" / path.relative_to(audit))
    snapshot = work / "fixture-final"
    publication = snapshot_fixture(Path(cfg["repo_root"]), snapshot)
    for path in snapshot.rglob("*"):
        if path.is_symlink():
            try:
                path.resolve(strict=True).relative_to(snapshot.resolve())
            except (ValueError, FileNotFoundError):
                raise ValueError("public fixture contains an escaping symlink")
        elif path.is_file():
            data = public_bytes(path.read_bytes(), secrets, aliases)
            if data != path.read_bytes():
                fixed = rawdir / path.relative_to(work)
                copy_once(path, fixed)
                path.write_bytes(data)
                copies.append({"path": str(path.relative_to(work)), "original_sha256": digest(fixed),
                               "public_sha256": digest(path)})
    dump(work / "fixture-publication-receipt.json", publication)
    if recollect:
        if (tree_inventory(Path(cfg["workdir"])) != recovery["partial_public_inventory"]
                or tree_inventory(fixed_prior) != recovery["original_raw_inventory"]
                or tree_inventory(Path(cfg["repo_root"]), fixture=True) != recovery["source_fixture_inventory"]):
            raise ValueError("original partial/raw/fixture changed during recollection")
        for previous in recovery["previous_failed_attempts"]:
            if (tree_inventory(Path(previous["workdir"])) != previous["public_inventory"]
                    or tree_inventory(Path(previous["raw_root"])) != previous["raw_inventory"]
                    or digest(Path(previous["failure_log_path"])) != previous["failure_log_sha256"]):
                raise ValueError("previous failed collection changed during recollection")
        recovery.update({"new_workdir": str(work), "new_raw_root": str(rawdir),
                         "config_sha256": state["config_sha256"], "run_id": state["run_id"],
                         "execution_binding_changed": False, "original_raw_or_partial_modified": False})
        recovery["collected_at_unix"] = time.time()
        recovery["execution_observed_at_unix"] = state["started_at_unix"] + state["elapsed"]
        dump(work / "collection-recovery-receipt.json", recovery)
        state["collection_publication"] = {"original_workdir": cfg["workdir"], "workdir": str(work), "ordinal": publication_ordinal,
                                          "receipt_sha256": digest(work / "collection-recovery-receipt.json")}
    state["collected"] = True
    dump(work / "native-run-state.json", state)
    if aliases:
        public_state = work / "native-run-state.json"
        public_state.write_bytes(public_bytes(public_state.read_bytes(), secrets, aliases))
    dump(work / "poll-state.json", {"elapsed": math.ceil(state["elapsed"]),
          "started_at_unix": state["started_at_unix"],
          "observed_at_unix": state["started_at_unix"] + state["elapsed"]})
    dump(work / "public-copy-receipt.json", {"runtime": "codex", "copies": copies,
          "collected_at_unix": time.time(), "execution_observed_at_unix": state["started_at_unix"] + state["elapsed"],
          "excluded_fixture_files": excluded, "private_original_fixed_before_public_copy": True,
          "native_temporary_exclusion": {"path": ".native-tmp", "publicly_included": False,
                "reason": "native CLI communication/runtime temporary data; business artifacts belong outside this directory",
                "private_original_retained": native_temporary.exists()},
          "native_format_converted": False})
    if aliases:
        dump(work / "catalog-exclusion-publication.json", {"paths_anonymized": len(aliases),
             "aliases": [{"alias": alias, "original_path_sha256": hashlib.sha256(path.encode()).hexdigest()}
                         for path, alias in aliases.items()],
             "note": "Only excluded external catalog paths are anonymized in publication copies; private argv/raw and execution config remain unchanged. Catalog isolation is not established by this receipt."})
    dump(work / "evidence-freeze.json", {"files": {
          str(path.relative_to(work)): digest(path) for path in sorted(work.rglob("*"))
          if path.is_file() and not path.is_symlink()}, "symlinks": {
          str(path.relative_to(work)): os.readlink(path) for path in sorted(work.rglob("*")) if path.is_symlink()},
          "behavior_sha256": state["behavior_sha256"]})
    dump(state_path(cfg), state)
    return state


def finalize(cfg: dict, goal: Path | None, observations: list[str], blocked: bool) -> int:
    state = load_state(cfg)
    if not state.get("collected"):
        raise ValueError("collect before independent evaluation/finalize")
    work = collection_workdir(cfg, state)
    if (work / "verdict.json").exists():
        raise ValueError("existing verdict must never be overwritten")
    frozen = json.loads((work / "evidence-freeze.json").read_text())
    for rel, sha in frozen["files"].items():
        if digest(work / rel) != sha:
            raise ValueError(f"frozen evidence drift: {rel}")
    for rel, target in frozen.get("symlinks", {}).items():
        path = work / rel
        if not path.is_symlink() or os.readlink(path) != target:
            raise ValueError(f"frozen publication link drift: {rel}")
        path.resolve(strict=True).relative_to(work.resolve(strict=True))
    verify_pin(cfg, state)
    fixture = (work / "fixture-final").resolve(strict=True)
    eval_root = (fixture / cfg.get("goal_seek_eval_root_relative", "eval-log")).resolve()
    if not eval_root.is_relative_to(fixture):
        raise ValueError("goal-seek evidence root escapes collected fixture")
    args = ["--runtime", "codex", "--workdir", str(work), "--target-skill", cfg["target_skill"],
            "--skill-dir", cfg["skill_dir"], "--args=" + cfg.get("args", ""),
            "--session-id", state.get("session_id") or "", "--transcript", str(work / "transcript.jsonl"),
            "--requested-model", cfg.get("requested_model", ""),
            "--launch", "PASS" if state.get("session_id") else "FAIL",
            "--completion", "PASS" if state["status"] == "DONE" else "FAIL",
            "--poll-exit", "DONE" if state["status"] == "DONE" else "HARD_CAP" if state["status"] == "HARD_CAP" else "STALL",
            "--poll-state", str(work / "poll-state.json"), "--permissions-mode", "workspace-write",
            "--scenario-file", cfg["scenario_file"], "--scenario-id", cfg["scenario_id"],
            "--goal-seek-eval-root", str(eval_root),
            "--native-run-state", str(work / "native-run-state.json"),
            "--nudge-count", str(len(state.get("manual_response_turns", []))),
            "--gate-response-count", str(sum(bool(r["submitted"]) for r in state["responses"])),
            "--gate-kind", "contractual" if state["responses"] else "rescue"]
    if blocked:
        args += ["--blocked", "--blocker", f"native Codex run stopped: {state['status']}"]
    elif goal is None:
        raise ValueError("fresh independent goal-evaluation required")
    else:
        args += ["--goal-evaluation", str(goal)]
    for observation in observations:
        args += ["--observation", observation]
    return int(sibling("live-trial-verdict").main(args))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "continue", "collect", "recollect", "finalize", "status"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--response-file", type=Path)
    parser.add_argument("--goal-evaluation", type=Path)
    parser.add_argument("--observation", action="append", default=[])
    parser.add_argument("--blocked", action="store_true")
    parser.add_argument("--publication-ordinal", type=int, default=1)
    parser.add_argument("--previous-failure-log", type=Path, action="append", default=[])
    ns = parser.parse_args(argv)
    try:
        cfg = load_config(ns.config)
        if ns.action != "recollect" and (ns.publication_ordinal != 1 or ns.previous_failure_log):
            raise ValueError("publication ordinal/failure logs are only valid for recollect")
        if ns.action == "finalize":
            return finalize(cfg, ns.goal_evaluation, ns.observation, ns.blocked)
        if ns.action == "run":
            state = run(cfg)
        elif ns.action == "continue":
            if ns.response_file is None:
                raise ValueError("continue requires explicit response file")
            state = continue_run(cfg, ns.response_file)
        elif ns.action == "collect":
            state = collect(cfg)
        elif ns.action == "recollect":
            state = collect(cfg, recollect=True, publication_ordinal=ns.publication_ordinal,
                            previous_failure_logs=ns.previous_failure_log)
        else:
            state = load_state(cfg)
        print(json.dumps({"runtime": "codex", "run_id": cfg["run_id"], "status": state["status"],
                          "session_id": state.get("session_id"), "collected": state.get("collected"),
                          "publication_workdir": str(collection_workdir(cfg, state))}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if sys.argv[1:2] == [SUPERVISOR_MODE]:
        if len(sys.argv) < 5 or sys.argv[3] != "--":
            raise SystemExit("invalid internal supervisor invocation")
        supervise_owned_turn(Path(sys.argv[2]), sys.argv[4:])
    raise SystemExit(main())
