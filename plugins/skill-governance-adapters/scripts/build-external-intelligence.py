#!/usr/bin/env python3
# /// script
# name: external-intelligence
# purpose: Codex / Claude Code 共通の外部知能 state を plugin package 外に保存し、重複統合・独立証拠・再利用検証・明示承認による昇格を決定論的に管理する
# inputs:
#   - argv: --scope project|user / --project-root / --state-dir / --agent + init|capture|search|show|reuse|promote|supersede|verify
# outputs:
#   - stdout: 常に単一 JSON object
#   - write: project=.git/harness-creator/external-intelligence/v1 (non-git=.harness/...) / user=plugin data or XDG state
#   - exit: 0=success / 1=blocked|invalid|corrupt / 2=usage / 3=possible duplicate requiring explicit resolution
# contexts: [A, C, E]
# network: false
# write-scope: resolved external-intelligence state root only; plugin package is read-only
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Durable, provider-neutral external intelligence for capability runtimes.

The plugin ships code and curated seed knowledge. Runtime observations live in
a project or user state directory, never in the installed plugin copy.  The
event log is hash chained; materialized entry files and the thin index can be
reconstructed from it.
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64
AUTO_MERGE_THRESHOLD = 0.88
REVIEW_THRESHOLD = 0.62
MAX_TEXT = 8_000
STATUSES = ("observation", "candidate", "verified", "promoted", "superseded")
AGENTS = ("codex", "claude", "other")
ENTRY_ID_RE = re.compile(r"^ei-[0-9a-f]{12}(?:-(?:[2-9]|[1-9][0-9]+))?$")
LEGACY_EVIDENCE_SOURCE = "legacy-unclassified"


class StoreError(Exception):
    """Expected state or validation error."""


class StoreCorruption(StoreError):
    """Hash chain or materialized state is not trustworthy."""


class StateBusy(StoreError):
    """Another writer owns the state lock."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    """Japanese-compatible canonical form used for identity and comparison."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    chars = []
    for char in normalized:
        category = unicodedata.category(char)
        chars.append(" " if category.startswith(("P", "Z", "C")) else char)
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _identity_text(title: str, rule: str) -> str:
    return normalize_text(f"{title}\n{rule}")


def _fingerprint(title: str, rule: str) -> str:
    return _digest(_identity_text(title, rule))


def _ngrams(value: str, size: int = 3) -> set[str]:
    compact = value.replace(" ", "")
    if len(compact) <= size:
        return {compact} if compact else set()
    return {compact[i : i + size] for i in range(len(compact) - size + 1)}


def similarity(left: str, right: str) -> float:
    """Deterministic character similarity that also works without word spaces."""
    a, b = normalize_text(left), normalize_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    seq = difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()
    ag, bg = _ngrams(a), _ngrams(b)
    jac = len(ag & bg) / len(ag | bg) if ag and bg else 0.0
    return max(seq, jac)


def _validated_text(label: str, value: str, *, required: bool = True) -> str:
    text = value.strip()
    if required and not text:
        raise StoreError(f"{label} must be non-empty")
    if len(text) > MAX_TEXT:
        raise StoreError(f"{label} exceeds {MAX_TEXT} characters")
    return text


def _validated_entry_id(value: str, *, corruption: bool = False) -> str:
    error_type = StoreCorruption if corruption else StoreError
    if not isinstance(value, str) or not ENTRY_ID_RE.fullmatch(value):
        raise error_type("entry id has invalid format")
    return value


def resolve_state_dir(
    *,
    scope: str,
    state_dir: str | None,
    project_root: str | None,
    environ: dict[str, str] | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    if state_dir:
        return Path(state_dir).expanduser().resolve()
    override = env.get("HARNESS_INTELLIGENCE_HOME")
    if override:
        return Path(override).expanduser().resolve()

    if scope == "project":
        root = Path(project_root or env.get("CLAUDE_PROJECT_DIR") or os.getcwd()).expanduser().resolve()
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            proc = None
        if proc is not None and proc.returncode == 0 and proc.stdout.strip():
            common = Path(proc.stdout.strip())
            if not common.is_absolute():
                common = root / common
            return (common.resolve() / "harness-creator" / "external-intelligence" / "v1")
        return root / ".harness" / "external-intelligence" / "v1"

    plugin_data = env.get("PLUGIN_DATA") or env.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data).expanduser().resolve() / "external-intelligence" / "v1"
    if env.get("XDG_STATE_HOME"):
        base = Path(env["XDG_STATE_HOME"]).expanduser()
    elif os.name == "nt" and env.get("LOCALAPPDATA"):
        base = Path(env["LOCALAPPDATA"]).expanduser()
    else:
        base = Path.home() / ".local" / "state"
    return (base / "harness-creator" / "external-intelligence" / "v1").resolve()


def _events_path(state: Path) -> Path:
    return state / "events.jsonl"


def _index_path(state: Path) -> Path:
    return state / "index.json"


def _entries_dir(state: Path) -> Path:
    return state / "entries"


def _entry_path(state: Path, entry_id: str, *, corruption: bool = False) -> Path:
    validated = _validated_entry_id(entry_id, corruption=corruption)
    state_root = state.resolve()
    root = _entries_dir(state).resolve()
    if root != state_root / "entries":
        error_type = StoreCorruption if corruption else StoreError
        raise error_type("entries directory escapes the state root")
    path = (root / f"{validated}.json").resolve()
    if path.parent != root:
        error_type = StoreCorruption if corruption else StoreError
        raise error_type("entry path escapes the entries directory")
    return path


def _ensure_layout(state: Path) -> None:
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    _entries_dir(state).mkdir(parents=True, exist_ok=True, mode=0o700)
    events = _events_path(state)
    if not events.exists():
        events.touch(mode=0o600)


@contextlib.contextmanager
def _write_lock(state: Path) -> Iterator[None]:
    _ensure_layout(state)
    lock = state / ".write.lock"
    fd: int | None = None
    for attempt in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError as exc:
            if attempt or not _reclaim_dead_owner_lock(lock):
                raise StateBusy(f"state is busy: {lock}") from exc
    if fd is None:  # defensive: the loop either opens the lock or raises
        raise StateBusy(f"state is busy: {lock}")
    owned = os.fstat(fd)
    try:
        try:
            owner = {"pid": os.getpid(), "acquired_at": _now()}
            os.write(fd, (_canonical(owner) + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        yield
    finally:
        try:
            current = lock.stat()
            if (owned.st_dev, owned.st_ino) == (current.st_dev, current.st_ino):
                lock.unlink()
        except FileNotFoundError:
            pass


def _reclaim_dead_owner_lock(lock: Path) -> bool:
    """Reclaim only a well-formed lock whose recorded PID cannot exist."""
    try:
        before = lock.stat()
        owner = json.loads(lock.read_text(encoding="utf-8"))
        pid = owner.get("pid") if isinstance(owner, dict) else None
        acquired_at = owner.get("acquired_at") if isinstance(owner, dict) else None
        if not isinstance(pid, int) or pid <= 0 or not isinstance(acquired_at, str):
            return False
        datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            after = lock.stat()
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                return False
            lock.unlink()
            return True
        except (PermissionError, OSError):
            return False
        return False
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _event_hash(event_without_hash: dict[str, Any]) -> str:
    return _digest(_canonical(event_without_hash))


def load_events(state: Path) -> list[dict[str, Any]]:
    path = _events_path(state)
    if not path.exists():
        return []
    result: list[dict[str, Any]] = []
    previous = GENESIS_HASH
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StoreCorruption(f"event line {line_no} is invalid JSON") from exc
        if not isinstance(event, dict):
            raise StoreCorruption(f"event line {line_no} is not an object")
        expected_seq = len(result) + 1
        if event.get("seq") != expected_seq:
            raise StoreCorruption(f"event sequence mismatch at line {line_no}")
        if event.get("previous_hash") != previous:
            raise StoreCorruption(f"previous hash mismatch at line {line_no}")
        claimed = event.get("hash")
        body = {key: value for key, value in event.items() if key != "hash"}
        actual = _event_hash(body)
        if claimed != actual:
            raise StoreCorruption(f"event hash mismatch at line {line_no}")
        if not isinstance(event.get("entry"), dict) or not event["entry"].get("id"):
            raise StoreCorruption(f"event entry missing at line {line_no}")
        _validated_entry_id(event["entry"]["id"], corruption=True)
        result.append(event)
        previous = actual
    return result


def reconstruct(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for event in events:
        entry = json.loads(json.dumps(event["entry"], ensure_ascii=False))
        entries[entry["id"]] = entry
    return entries


def _thin_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        key: entry.get(key)
        for key in (
            "id",
            "status",
            "title",
            "summary",
            "rule",
            "tags",
            "resolution_status",
            "observation_count",
            "context_count",
            "evidence_count",
            "helpful_reuse_count",
            "last_seen_at",
        )
    }


def _index_for(entries: dict[str, dict[str, Any]], head: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "chain_head": head,
        "entry_count": len(entries),
        "entries": [_thin_entry(entries[key]) for key in sorted(entries)],
    }


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass
        raise


def materialize(state: Path, events: list[dict[str, Any]], entries: dict[str, dict[str, Any]]) -> None:
    _ensure_layout(state)
    expected_names = {f"{entry_id}.json" for entry_id in entries}
    for path in _entries_dir(state).glob("*.json"):
        if path.name not in expected_names:
            path.unlink()
    for entry_id in sorted(entries):
        _atomic_json(_entry_path(state, entry_id, corruption=True), entries[entry_id])
    head = events[-1]["hash"] if events else GENESIS_HASH
    _atomic_json(_index_path(state), _index_for(entries, head))


def init_store(state: Path) -> dict[str, Any]:
    with _write_lock(state):
        events = load_events(state)
        entries = reconstruct(events)
        materialize(state, events, entries)
    return {"status": "ok", "state_dir": str(state), "entry_count": len(entries)}


def _append_event(
    state: Path,
    events: list[dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    *,
    kind: str,
    agent: str,
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    body = {
        "seq": len(events) + 1,
        "previous_hash": events[-1]["hash"] if events else GENESIS_HASH,
        "recorded_at": _now(),
        "kind": kind,
        "agent": agent,
        "entry_id": entry["id"],
        "entry": entry,
    }
    event = dict(body)
    event["hash"] = _event_hash(body)
    with _events_path(state).open("a", encoding="utf-8") as stream:
        stream.write(_canonical(event) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    updated_events = events + [event]
    entries[entry["id"]] = entry
    materialize(state, updated_events, entries)
    return updated_events


def _observation_key(context_id: str, evidence_ref: str, evidence_source: str) -> str:
    return _digest(
        f"{normalize_text(context_id)}\n{normalize_text(evidence_ref)}\n{normalize_text(evidence_source)}"
    )


def _evidence_source(item: dict[str, Any]) -> str:
    return normalize_text(str(item.get("evidence_source") or LEGACY_EVIDENCE_SOURCE))


def _refresh_counts(entry: dict[str, Any]) -> None:
    observations = entry.get("observations", [])
    entry["observation_count"] = len(observations)
    entry["context_count"] = len({item["context_id"] for item in observations})
    entry["evidence_count"] = len({_evidence_source(item) for item in observations})
    entry["helpful_reuse_count"] = sum(
        1 for item in entry.get("reuses", []) if item.get("outcome") == "helpful"
    )


def _candidate_ready(entry: dict[str, Any]) -> bool:
    if entry.get("resolution_status") == "pending_duplicate":
        return False
    return entry.get("context_count", 0) >= 2 and entry.get("evidence_count", 0) >= 2


def _verified_ready(entry: dict[str, Any]) -> bool:
    if not _candidate_ready(entry):
        return False
    observed_contexts = {item["context_id"] for item in entry.get("observations", [])}
    observed_sources = {_evidence_source(item) for item in entry.get("observations", [])}
    return any(
        item.get("outcome") == "helpful"
        and item.get("context_id") not in observed_contexts
        and _evidence_source(item) not in observed_sources
        for item in entry.get("reuses", [])
    )


def _derive_status(entry: dict[str, Any]) -> str:
    if entry.get("status") in {"promoted", "superseded"}:
        return entry["status"]
    if entry.get("resolution_status") == "pending_duplicate":
        return "observation"
    if _verified_ready(entry):
        return "verified"
    if _candidate_ready(entry):
        return "candidate"
    return "observation"


def capture_entry(state: Path, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    title = _validated_text("title", args.title)
    summary = _validated_text("summary", args.summary)
    rule = _validated_text("rule", args.rule)
    context_id = _validated_text("context-id", args.context_id)
    evidence_ref = _validated_text("evidence-ref", args.evidence_ref)
    evidence_source = _validated_text("evidence-source", args.evidence_source)
    countercondition = _validated_text("countercondition", args.countercondition or "", required=False)
    fingerprint = _fingerprint(title, rule)
    identity = _identity_text(title, rule)
    tags = sorted({normalize_text(tag) for tag in (args.tags or "").split(",") if normalize_text(tag)})
    observed_at = _now()
    observation = {
        "key": _observation_key(context_id, evidence_ref, evidence_source),
        "agent": args.agent,
        "context_id": context_id,
        "evidence_ref": evidence_ref,
        "evidence_source": evidence_source,
        "observed_at": observed_at,
        "summary": summary,
        "rule": rule,
    }

    with _write_lock(state):
        events = load_events(state)
        entries = reconstruct(events)
        materialize(state, events, entries)
        target: dict[str, Any] | None = None
        score = 0.0
        duplicate_candidates: list[dict[str, Any]] = []
        if args.merge_with:
            merge_id = _validated_entry_id(args.merge_with)
            target = entries.get(merge_id)
            if target is None:
                raise StoreError(f"merge target not found: {merge_id}")
            if target.get("status") == "superseded":
                raise StoreError("cannot merge into a superseded entry")
        else:
            for entry in entries.values():
                if entry.get("fingerprint") == fingerprint and entry.get("status") != "superseded":
                    target = entry
                    score = 1.0
                    break
            if target is None and entries:
                ranked = sorted(
                    (
                        (similarity(identity, entry.get("identity_text", "")), entry)
                        for entry in entries.values()
                        if entry.get("status") != "superseded"
                    ),
                    key=lambda item: (-item[0], item[1]["id"]),
                )
                if ranked:
                    score, closest = ranked[0]
                    if score >= AUTO_MERGE_THRESHOLD:
                        target = closest
                    elif score >= REVIEW_THRESHOLD and not args.force_new:
                        duplicate_candidates = [
                            {
                                "id": item[1]["id"],
                                "title": item[1]["title"],
                                "similarity": round(item[0], 4),
                            }
                            for item in ranked[:3]
                            if item[0] >= REVIEW_THRESHOLD
                        ]
                        if args.ambiguous_action == "reject":
                            return {
                                "status": "possible_duplicate",
                                "state_dir": str(state),
                                "candidates": duplicate_candidates,
                                "resolution": "rerun with --merge-with <id>, or --force-new --distinct-reason <why>",
                            }, 3
        if args.force_new and not args.distinct_reason:
            raise StoreError("--force-new requires --distinct-reason")

        if target is not None:
            if any(item.get("key") == observation["key"] for item in target.get("observations", [])):
                return {
                    "status": "ok",
                    "action": "duplicate_observation",
                    "state_dir": str(state),
                    "similarity": round(score, 4),
                    "entry": target,
                }, 0
            target.setdefault("observations", []).append(observation)
            target["tags"] = sorted(set(target.get("tags", [])) | set(tags))
            if fingerprint != target.get("fingerprint"):
                variant = {"title": title, "summary": summary, "rule": rule, "fingerprint": fingerprint}
                if variant not in target.setdefault("variants", []):
                    target["variants"].append(variant)
            if countercondition and not target.get("countercondition"):
                target["countercondition"] = countercondition
            target["last_seen_at"] = observed_at
            _refresh_counts(target)
            target["status"] = _derive_status(target)
            _append_event(
                state, events, entries, kind="OBSERVATION_MERGED", agent=args.agent, entry=target
            )
            return {
                "status": "ok",
                "action": "merged",
                "state_dir": str(state),
                "similarity": round(score, 4),
                "entry": target,
            }, 0

        entry_id = f"ei-{fingerprint[:12]}"
        suffix = 1
        while entry_id in entries:
            suffix += 1
            entry_id = f"ei-{fingerprint[:12]}-{suffix}"
        entry = {
            "schema_version": SCHEMA_VERSION,
            "id": entry_id,
            "status": "observation",
            "title": title,
            "summary": summary,
            "rule": rule,
            "tags": tags,
            "countercondition": countercondition,
            "fingerprint": fingerprint,
            "identity_text": identity,
            "created_at": observed_at,
            "last_seen_at": observed_at,
            "observations": [observation],
            "reuses": [],
            "variants": [],
        }
        if duplicate_candidates and args.ambiguous_action == "quarantine":
            entry["resolution_status"] = "pending_duplicate"
            entry["duplicate_candidates"] = duplicate_candidates
        if args.force_new:
            entry["distinct_reason"] = args.distinct_reason.strip()
        _refresh_counts(entry)
        _append_event(state, events, entries, kind="OBSERVATION_CREATED", agent=args.agent, entry=entry)
        return {"status": "ok", "action": "created", "state_dir": str(state), "entry": entry}, 0


def reuse_entry(state: Path, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    entry_id = _validated_entry_id(args.id)
    context_id = _validated_text("context-id", args.context_id)
    evidence_ref = _validated_text("evidence-ref", args.evidence_ref)
    evidence_source = _validated_text("evidence-source", args.evidence_source)
    key = _observation_key(context_id, evidence_ref, evidence_source)
    with _write_lock(state):
        events = load_events(state)
        entries = reconstruct(events)
        materialize(state, events, entries)
        entry = entries.get(entry_id)
        if entry is None:
            raise StoreError(f"entry not found: {entry_id}")
        if entry.get("status") == "superseded":
            raise StoreError("cannot reuse a superseded entry")
        if any(item.get("key") == key for item in entry.get("reuses", [])):
            return {"status": "ok", "action": "duplicate_reuse", "state_dir": str(state), "entry": entry}, 0
        entry.setdefault("reuses", []).append(
            {
                "key": key,
                "agent": args.agent,
                "context_id": context_id,
                "evidence_ref": evidence_ref,
                "evidence_source": evidence_source,
                "outcome": args.outcome,
                "recorded_at": _now(),
            }
        )
        entry["last_seen_at"] = _now()
        _refresh_counts(entry)
        entry["status"] = _derive_status(entry)
        _append_event(state, events, entries, kind="REUSE_RECORDED", agent=args.agent, entry=entry)
        return {"status": "ok", "action": "reuse_recorded", "state_dir": str(state), "entry": entry}, 0


def promote_entry(state: Path, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    entry_id = _validated_entry_id(args.id)
    approved_by = _validated_text("approved-by", args.approved_by)
    approval_evidence_ref = _validated_text(
        "approval-evidence-ref", args.approval_evidence_ref
    )
    with _write_lock(state):
        events = load_events(state)
        entries = reconstruct(events)
        materialize(state, events, entries)
        entry = entries.get(entry_id)
        if entry is None:
            raise StoreError(f"entry not found: {entry_id}")
        if entry.get("status") == "promoted":
            return {
                "status": "ok",
                "action": "already_promoted",
                "state_dir": str(state),
                "entry": entry,
            }, 0
        if entry.get("status") != "verified":
            return {
                "status": "blocked",
                "reason": "promotion requires current status verified",
                "entry": entry,
            }, 1
        entry["status"] = "promoted"
        entry["promotion"] = {
            "target": _validated_text("target", args.target),
            "falsifier": _validated_text("falsifier", args.falsifier),
            "rollback": _validated_text("rollback", args.rollback),
            "owner_approved": bool(args.owner_approved),
            "approved_by": approved_by,
            "approval_evidence_ref": approval_evidence_ref,
            "promoted_at": _now(),
        }
        _append_event(state, events, entries, kind="PROMOTED", agent=args.agent, entry=entry)
        return {"status": "ok", "action": "promoted", "state_dir": str(state), "entry": entry}, 0


def supersede_entry(state: Path, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Logically remove an invalid/obsolete entry without erasing audit history."""
    reason = _validated_text("reason", args.reason)
    entry_id = _validated_entry_id(args.id)
    with _write_lock(state):
        events = load_events(state)
        entries = reconstruct(events)
        materialize(state, events, entries)
        entry = entries.get(entry_id)
        if entry is None:
            raise StoreError(f"entry not found: {entry_id}")
        if entry.get("status") == "superseded":
            return {
                "status": "ok",
                "action": "already_superseded",
                "state_dir": str(state),
                "entry": entry,
            }, 0
        entry["status"] = "superseded"
        entry["supersession"] = {"reason": reason, "superseded_at": _now()}
        entry["last_seen_at"] = _now()
        _append_event(state, events, entries, kind="SUPERSEDED", agent=args.agent, entry=entry)
        return {"status": "ok", "action": "superseded", "state_dir": str(state), "entry": entry}, 0


def _load_trusted_snapshot(state: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    events = load_events(state)
    entries = reconstruct(events)
    head = events[-1]["hash"] if events else GENESIS_HASH
    expected = _index_for(entries, head)
    path = _index_path(state)
    if not path.exists() and not events:
        return expected, entries
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreCorruption(
            f"cannot trust materialized index; run verify --repair: {exc}"
        ) from exc
    if data != expected:
        raise StoreCorruption("materialized index drift; run verify --repair")
    return data, entries


def search_entries(state: Path, query: str, limit: int) -> dict[str, Any]:
    query_norm = normalize_text(_validated_text("query", query))
    tokens = [token for token in query_norm.split() if token]
    index, _ = _load_trusted_snapshot(state)
    ranked = []
    for entry in index["entries"]:
        if entry.get("status") == "superseded":
            continue
        haystack = normalize_text(
            " ".join(str(entry.get(key) or "") for key in ("title", "summary", "rule", "tags"))
        )
        score = 2.0 * similarity(query_norm, haystack)
        if query_norm in haystack:
            score += 3.0
        score += sum(1.0 for token in tokens if token in haystack)
        if score > 0:
            ranked.append((score, entry))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    results = []
    for score, thin in ranked[:limit]:
        result = dict(thin)
        result["score"] = round(score, 4)
        results.append(result)
    return {"status": "ok", "state_dir": str(state), "query": query, "results": results}


def show_entry(state: Path, entry_id: str) -> tuple[dict[str, Any], int]:
    entry_id = _validated_entry_id(entry_id)
    _, authoritative = _load_trusted_snapshot(state)
    expected = authoritative.get(entry_id)
    path = _entry_path(state, entry_id)
    if expected is None:
        if path.exists():
            raise StoreCorruption("orphaned entry projection; run verify --repair")
        return {"status": "not_found", "id": entry_id, "state_dir": str(state)}, 1
    if not path.exists():
        raise StoreCorruption("missing entry projection; run verify --repair")
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreCorruption(f"cannot read entry {entry_id}: {exc}") from exc
    if entry != expected:
        raise StoreCorruption("entry projection drift; run verify --repair")
    return {"status": "ok", "state_dir": str(state), "entry": entry}, 0


def store_metrics(state: Path) -> dict[str, Any]:
    """Derive compact operating KPIs from the authoritative event log only."""
    events = load_events(state)
    entries = reconstruct(events)
    observation_events = sum(
        event.get("kind") in {"OBSERVATION_CREATED", "OBSERVATION_MERGED"}
        for event in events
    )
    merged_events = sum(event.get("kind") == "OBSERVATION_MERGED" for event in events)
    return {
        "status": "ok",
        "state_dir": str(state),
        "event_count": len(events),
        "events_bytes": _events_path(state).stat().st_size if _events_path(state).exists() else 0,
        "entry_count": len(entries),
        "observation_count": sum(len(entry.get("observations", [])) for entry in entries.values()),
        "merged_observation_ratio": (
            round(merged_events / observation_events, 6) if observation_events else 0.0
        ),
        "helpful_reuse_count": sum(
            item.get("outcome") == "helpful"
            for entry in entries.values()
            for item in entry.get("reuses", [])
        ),
        "promoted_count": sum(entry.get("status") == "promoted" for entry in entries.values()),
        "promotion_event_count": sum(event.get("kind") == "PROMOTED" for event in events),
    }


def verify_store(state: Path, repair: bool) -> tuple[dict[str, Any], int]:
    try:
        events = load_events(state)
    except StoreCorruption as exc:
        return {"status": "corrupt", "state_dir": str(state), "error": str(exc)}, 1
    entries = reconstruct(events)
    head = events[-1]["hash"] if events else GENESIS_HASH
    expected_index = _index_for(entries, head)
    drift: list[str] = []
    try:
        actual_index = json.loads(_index_path(state).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        actual_index = None
    if actual_index != expected_index:
        drift.append("index.json")
    actual_names = {path.name for path in _entries_dir(state).glob("*.json")} if _entries_dir(state).exists() else set()
    expected_names = {f"{entry_id}.json" for entry_id in entries}
    if actual_names != expected_names:
        drift.append("entries/")
    else:
        for entry_id, expected in entries.items():
            try:
                actual = json.loads((_entries_dir(state) / f"{entry_id}.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                actual = None
            if actual != expected:
                drift.append(f"entries/{entry_id}.json")
    if drift and repair:
        with _write_lock(state):
            materialize(state, events, entries)
        return {"status": "repaired", "state_dir": str(state), "drift": sorted(set(drift))}, 0
    if drift:
        return {"status": "drift", "state_dir": str(state), "drift": sorted(set(drift))}, 1
    return {
        "status": "ok",
        "state_dir": str(state),
        "event_count": len(events),
        "entry_count": len(entries),
        "chain_head": head,
    }, 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--project-root")
    parser.add_argument("--state-dir")
    parser.add_argument("--agent", choices=AGENTS, default="other")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init")

    capture = commands.add_parser("capture")
    capture.add_argument("--title", required=True)
    capture.add_argument("--summary", required=True)
    capture.add_argument("--rule", required=True)
    capture.add_argument("--context-id", required=True)
    capture.add_argument("--evidence-ref", required=True)
    capture.add_argument("--evidence-source", default="")
    capture.add_argument("--tags", default="")
    capture.add_argument("--countercondition", default="")
    capture.add_argument("--merge-with")
    capture.add_argument("--force-new", action="store_true")
    capture.add_argument("--distinct-reason")
    capture.add_argument(
        "--ambiguous-action", choices=("reject", "quarantine"), default="reject"
    )

    search = commands.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=5)

    show = commands.add_parser("show")
    show.add_argument("--id", required=True)

    reuse = commands.add_parser("reuse")
    reuse.add_argument("--id", required=True)
    reuse.add_argument("--context-id", required=True)
    reuse.add_argument("--evidence-ref", required=True)
    reuse.add_argument("--evidence-source", default="")
    reuse.add_argument("--outcome", choices=("helpful", "neutral", "unhelpful"), required=True)

    promote = commands.add_parser("promote")
    promote.add_argument("--id", required=True)
    promote.add_argument("--target", required=True)
    promote.add_argument("--owner-approved", action="store_true", required=True)
    promote.add_argument("--approved-by", default="")
    promote.add_argument("--approval-evidence-ref", default="")
    promote.add_argument("--falsifier", required=True)
    promote.add_argument("--rollback", required=True)

    supersede = commands.add_parser("supersede")
    supersede.add_argument("--id", required=True)
    supersede.add_argument("--reason", required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--repair", action="store_true")
    commands.add_parser("metrics")
    return parser


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    state = resolve_state_dir(
        scope=args.scope,
        state_dir=args.state_dir,
        project_root=args.project_root,
    )
    try:
        if args.command == "init":
            payload, code = init_store(state), 0
        elif args.command == "capture":
            payload, code = capture_entry(state, args)
        elif args.command == "search":
            if args.limit < 1 or args.limit > 50:
                raise StoreError("limit must be between 1 and 50")
            payload, code = search_entries(state, args.query, args.limit), 0
        elif args.command == "show":
            payload, code = show_entry(state, args.id)
        elif args.command == "reuse":
            payload, code = reuse_entry(state, args)
        elif args.command == "promote":
            payload, code = promote_entry(state, args)
        elif args.command == "supersede":
            payload, code = supersede_entry(state, args)
        elif args.command == "metrics":
            payload, code = store_metrics(state), 0
        else:
            payload, code = verify_store(state, args.repair)
    except (StoreError, OSError) as exc:
        payload, code = {"status": "error", "state_dir": str(state), "error": str(exc)}, 1
    _emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
