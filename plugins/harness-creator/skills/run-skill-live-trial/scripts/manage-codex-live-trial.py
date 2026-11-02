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


def public_bytes(raw: bytes, secrets: list[str]) -> bytes:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    for secret in secrets:
        if len(secret) >= 8:
            text = text.replace(secret, "[REDACTED_FIXTURE_SECRET]")
    text = TOKEN_RE.sub("[REDACTED_API_TOKEN]", text)
    text = re.sub(r"\b(?:Bearer|Basic)[ \t]+[A-Za-z0-9._~+/-]{8,}=*", "[REDACTED_AUTHORIZATION]", text, flags=re.I)
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
                  "[REDACTED_PRIVATE_KEY]", text, flags=re.S)
    return text.encode("utf-8")


def collect(cfg: dict) -> dict:
    state = load_state(cfg)
    verify_pin(cfg, state)
    if state.get("active_process") or state.get("collected"):
        raise ValueError("only a stopped, uncollected trial can be frozen")
    work, private = Path(cfg["workdir"]), Path(cfg["private_dir"])
    if (work / "evidence-freeze.json").exists():
        raise ValueError("frozen evidence exists")
    rawdir = private / "raw-at-collection"
    rawdir.mkdir(exist_ok=False)
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
    copies = []
    def publish(source: Path, destination: Path):
        fixed = rawdir / destination.relative_to(work)
        copy_once(source, fixed)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = public_bytes(fixed.read_bytes(), secrets)
        with destination.open("xb") as stream:
            stream.write(data)
        copies.append({"path": str(destination.relative_to(work)),
                       "original_sha256": digest(fixed), "public_sha256": digest(destination)})
    if state.get("native_rollout"):
        verify_native_skill_paths(cfg, state)
        publish(Path(state["native_rollout"]), work / "transcript.jsonl")
        pending = [state["session_id"]]
        seen = set(pending)
        while pending:
            parent_id = pending.pop()
            for child in child_rollouts(session_root(), parent_id, parent_rollout=Path(state["native_rollout"]),
                                        started_at_unix=state["started_at_unix"], fresh=True):
                meta = _first_metadata(child)
                identity = meta["id"]
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
    snapshot = work / "fixture-final"
    def ignore(directory, names):
        return [name for name in names if name in {".git", ".agents", ".codex", "__pycache__"}
                or (Path(directory).resolve() == Path(cfg["repo_root"]).resolve() and name == ".native-tmp")
                or secret_file(Path(name)) or Path(name).suffix == ".pyc"]
    shutil.copytree(cfg["repo_root"], snapshot, symlinks=True, ignore=ignore)
    for path in snapshot.rglob("*"):
        if path.is_symlink():
            try:
                path.resolve(strict=True).relative_to(snapshot.resolve())
            except (ValueError, FileNotFoundError):
                raise ValueError("public fixture contains an escaping symlink")
        elif path.is_file():
            data = public_bytes(path.read_bytes(), secrets)
            if data != path.read_bytes():
                fixed = rawdir / path.relative_to(work)
                copy_once(path, fixed)
                path.write_bytes(data)
                copies.append({"path": str(path.relative_to(work)), "original_sha256": digest(fixed),
                               "public_sha256": digest(path)})
    state["collected"] = True
    dump(work / "native-run-state.json", state)
    dump(work / "poll-state.json", {"elapsed": math.ceil(state["elapsed"]),
          "started_at_unix": state["started_at_unix"], "observed_at_unix": time.time()})
    dump(work / "public-copy-receipt.json", {"runtime": "codex", "copies": copies,
          "excluded_fixture_files": excluded, "private_original_fixed_before_public_copy": True,
          "native_temporary_exclusion": {"path": ".native-tmp", "publicly_included": False,
                "reason": "native CLI communication/runtime temporary data; business artifacts belong outside this directory",
                "private_original_retained": native_temporary.exists()},
          "native_format_converted": False})
    dump(work / "evidence-freeze.json", {"files": {
          str(path.relative_to(work)): digest(path) for path in sorted(work.rglob("*"))
          if path.is_file() and not path.is_symlink()}, "behavior_sha256": state["behavior_sha256"]})
    dump(state_path(cfg), state)
    return state


def finalize(cfg: dict, goal: Path | None, observations: list[str], blocked: bool) -> int:
    state = load_state(cfg)
    if not state.get("collected"):
        raise ValueError("collect before independent evaluation/finalize")
    work = Path(cfg["workdir"])
    if (work / "verdict.json").exists():
        raise ValueError("existing verdict must never be overwritten")
    frozen = json.loads((work / "evidence-freeze.json").read_text())
    for rel, sha in frozen["files"].items():
        if digest(work / rel) != sha:
            raise ValueError(f"frozen evidence drift: {rel}")
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
    parser.add_argument("action", choices=("run", "continue", "collect", "finalize", "status"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--response-file", type=Path)
    parser.add_argument("--goal-evaluation", type=Path)
    parser.add_argument("--observation", action="append", default=[])
    parser.add_argument("--blocked", action="store_true")
    ns = parser.parse_args(argv)
    try:
        cfg = load_config(ns.config)
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
        else:
            state = load_state(cfg)
        print(json.dumps({"runtime": "codex", "run_id": cfg["run_id"], "status": state["status"],
                          "session_id": state.get("session_id"), "collected": state.get("collected")}, ensure_ascii=False))
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
