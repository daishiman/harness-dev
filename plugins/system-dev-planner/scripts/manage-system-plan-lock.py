#!/usr/bin/env python3
# /// script
# name: manage-system-plan-lock
# purpose: caller repository 内の system plan 実行を atomic acquire/renew/release と期限切れ監査 receipt で単一 owner に束縛する。
# inputs: argv --lock-action/--repo-root/--config/--run-id/--session-owner/--feature-id/--feature-digest/--ttl-seconds
# outputs: stdout JSON; repo-local .dev-graph/locks/system-dev-plan-lock.json and expired-lock-receipts/*.json
# contexts: [C, E]
# network: false
# write-scope: caller repository .dev-graph/locks only
# dependencies: [resolve-project-context.py]
# requires-python: ">=3.10"
# ///
"""C13 repository-local system plan lock lifecycle manager.

The authoritative lock has a fixed filename.  A fixed name plus ``O_EXCL`` is
what makes acquire exclusive across *different* run ids; using one filename per
run would allow two first-time acquisitions to race and both succeed.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
LOCK_ROOT_REL = ".dev-graph/locks"
LOCK_NAME = "system-dev-plan-lock.json"
GUARD_NAME = ".system-dev-plan.operation.guard"
RECEIPT_DIR_NAME = "expired-lock-receipts"
LOCK_FIELDS = {
    "repository_id", "run_id", "session_owner", "feature_id", "feature_digest",
    "acquired_at", "heartbeat_at", "expires_at",
}
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class DomainBlock(Exception):
    """Expected lifecycle refusal (exit 1): another owner, malformed lock, busy."""


class ContractError(Exception):
    """Caller/path/identity contract violation (exit 2)."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError(message)


def _load_context():
    path = HERE / "resolve-project-context.py"
    spec = importlib.util.spec_from_file_location("sdp_lock_context", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise DomainBlock(f"malformed lock: {field} must be RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DomainBlock(f"malformed lock: {field} is not RFC3339") from exc
    if parsed.tzinfo is None:
        raise DomainBlock(f"malformed lock: {field} has no timezone")
    return parsed.astimezone(timezone.utc)


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ContractError(f"{field} must be a non-empty trimmed string")
    if len(value) > 256 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ContractError(f"{field} contains forbidden control/oversized content")
    return value


def _validate_cli(args: argparse.Namespace) -> None:
    if not SAFE_RUN_ID.fullmatch(args.run_id):
        raise ContractError("--run-id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    _identity(args.session_owner, "--session-owner")
    _identity(args.feature_id, "--feature-id")
    if not SHA256.fullmatch(args.feature_digest):
        raise ContractError("--feature-digest must be sha256:<64 lowercase hex>")
    if not 1 <= args.ttl_seconds <= 86400:
        raise ContractError("--ttl-seconds must be between 1 and 86400")


def _assert_no_symlinks(repo_root: Path, target: Path) -> None:
    """Reject every symlink segment, including in-root and broken symlinks."""
    try:
        relative = target.relative_to(repo_root)
    except ValueError as exc:
        raise ContractError(f"path escapes repository: {target}") from exc
    cursor = repo_root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ContractError(f"symlink path is forbidden for lock state: {cursor}")


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _exclusive_json(path: Path, value: dict) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise DomainBlock(f"exclusive state already exists: {path.name}") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)


def _atomic_replace_json(path: Path, value: dict) -> None:
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    _exclusive_json(temp, value)
    try:
        os.replace(temp, path)
        _fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def _read_lock(path: Path) -> tuple[dict, bytes]:
    if path.is_symlink():
        raise DomainBlock(f"lock path is a symlink: {path.name}")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise DomainBlock("system plan lock is absent") from exc
    try:
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read()
    except OSError as exc:
        raise DomainBlock(f"cannot read lock: {exc}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DomainBlock("malformed lock: invalid JSON") from exc
    if not isinstance(value, dict) or set(value) != LOCK_FIELDS:
        keys = set(value) if isinstance(value, dict) else set()
        raise DomainBlock(f"malformed lock: field exact-set mismatch {sorted(keys ^ LOCK_FIELDS)}")
    for field in ("repository_id", "run_id", "session_owner", "feature_id"):
        try:
            _identity(value[field], field)
        except ContractError as exc:
            raise DomainBlock(f"malformed lock: {exc}") from exc
    if not SAFE_RUN_ID.fullmatch(value["run_id"]):
        raise DomainBlock("malformed lock: unsafe run_id")
    if not SHA256.fullmatch(str(value["feature_digest"])):
        raise DomainBlock("malformed lock: invalid feature_digest")
    acquired = _parse_timestamp(value["acquired_at"], "acquired_at")
    heartbeat = _parse_timestamp(value["heartbeat_at"], "heartbeat_at")
    expires = _parse_timestamp(value["expires_at"], "expires_at")
    if acquired > heartbeat or heartbeat >= expires:
        raise DomainBlock("malformed lock: timestamps are not acquired<=heartbeat<expires")
    return value, raw


def _owner_fields(repository_id: str, args: argparse.Namespace) -> dict:
    return {
        "repository_id": repository_id,
        "run_id": args.run_id,
        "session_owner": args.session_owner,
        "feature_id": args.feature_id,
        "feature_digest": args.feature_digest,
    }


def _assert_owner(lock: dict, expected: dict) -> None:
    mismatched = [key for key, value in expected.items() if lock.get(key) != value]
    if mismatched:
        raise DomainBlock("lock owner identity mismatch: " + ", ".join(mismatched))


def validate_active_lock(
    *,
    repo_root: Path,
    locks: Path,
    repository_id: str,
    run_id: str,
    session_owner: str,
    feature_id: str,
    feature_digest: str,
    now: datetime | None = None,
) -> dict:
    """Read-only promotion gate for the canonical C13 lock.

    C11 uses this public boundary instead of duplicating lock parsing.  The
    lifecycle manager remains the sole writer; consumers can only prove that
    the exact repository/run/session/feature owner is still active.
    """
    root = repo_root.resolve()
    expected_locks = root / LOCK_ROOT_REL
    if locks != expected_locks:
        raise ContractError("lock root does not match the canonical repository-local path")
    _assert_no_symlinks(root, locks)
    lock_path = locks / LOCK_NAME
    _assert_no_symlinks(root, lock_path)
    lock, _raw = _read_lock(lock_path)
    expected = {
        "repository_id": repository_id,
        "run_id": _identity(run_id, "run_id"),
        "session_owner": _identity(session_owner, "session_owner"),
        "feature_id": _identity(feature_id, "feature_id"),
        "feature_digest": feature_digest,
    }
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise ContractError("run_id is unsafe")
    if not SHA256.fullmatch(feature_digest):
        raise ContractError("feature_digest must be sha256:<64 lowercase hex>")
    _assert_owner(lock, expected)
    observed = now or _utc_now()
    if observed.tzinfo is None:
        raise ContractError("active lock validation time must be timezone-aware")
    if _parse_timestamp(lock["expires_at"], "expires_at") <= observed.astimezone(timezone.utc):
        raise DomainBlock("system plan lock is expired")
    return lock


@contextlib.contextmanager
def _operation_guard(locks: Path) -> Iterator[None]:
    guard = locks / GUARD_NAME
    if guard.is_symlink():
        raise DomainBlock("operation guard is a symlink")
    try:
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(guard, flags, 0o600)
    except OSError as exc:
        raise DomainBlock(f"cannot open operation guard: {exc}") from exc
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DomainBlock("another lock lifecycle operation is in progress") from exc
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def cleanup_expired_lock(
    *,
    repo_root: Path,
    locks: Path,
    lock_path: Path,
    repository_id: str,
    now: datetime | None = None,
) -> Path:
    """Sole-writer cleanup boundary used by C07 for an observed stale lock."""
    root = repo_root.resolve()
    expected_locks = root / LOCK_ROOT_REL
    if locks != expected_locks or lock_path.parent != locks:
        raise ContractError("expired lock cleanup path is not canonical repository-local state")
    if re.fullmatch(r"system-dev-plan-[A-Za-z0-9._-]+\.json", lock_path.name) is None:
        raise ContractError("expired lock cleanup candidate name is invalid")
    _assert_no_symlinks(root, locks)
    _assert_no_symlinks(root, lock_path)
    observed = now or _utc_now()
    if observed.tzinfo is None:
        raise ContractError("expired lock cleanup time must be timezone-aware")
    with _operation_guard(locks):
        lock, raw = _read_lock(lock_path)
        if lock.get("repository_id") != repository_id:
            raise DomainBlock("expired lock repository identity mismatch")
        if _parse_timestamp(lock["expires_at"], "expires_at") > observed.astimezone(timezone.utc):
            raise DomainBlock("lock is not expired")
        return _expired_receipt(locks, lock_path, lock, raw, observed)


def _expired_receipt(locks: Path, lock_path: Path, lock: dict, raw: bytes, now: datetime) -> Path:
    receipts = locks / RECEIPT_DIR_NAME
    if receipts.is_symlink():
        raise DomainBlock("expired receipt directory is a symlink")
    receipts.mkdir(mode=0o700, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    receipt = receipts / f"expired-{lock['run_id']}-{digest[:16]}.json"
    value = {
        "schema_version": "1.0.0",
        "event": "expired-lock-cleanup",
        "cleaned_at": _timestamp(now),
        "lock_path": f"{LOCK_ROOT_REL}/{lock_path.name}",
        "expired_lock_sha256": f"sha256:{digest}",
        "expired_lock": lock,
    }
    if receipt.exists():
        if receipt.is_symlink():
            raise DomainBlock("expired receipt path is a symlink")
        try:
            existing = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DomainBlock("existing expired receipt is malformed") from exc
        if existing.get("expired_lock_sha256") != value["expired_lock_sha256"]:
            raise DomainBlock("expired receipt collision")
    else:
        _exclusive_json(receipt, value)
    # Do not remove a lock that changed after it was inspected.
    try:
        current = lock_path.read_bytes()
    except OSError as exc:
        raise DomainBlock(f"cannot re-read expired lock: {exc}") from exc
    if current != raw:
        raise DomainBlock("expired lock changed during cleanup")
    lock_path.unlink()
    _fsync_dir(locks)
    return receipt


def _lock_value(repository_id: str, args: argparse.Namespace, now: datetime) -> dict:
    timestamp = _timestamp(now)
    return {
        **_owner_fields(repository_id, args),
        "acquired_at": timestamp,
        "heartbeat_at": timestamp,
        "expires_at": _timestamp(now + timedelta(seconds=args.ttl_seconds)),
    }


def _acquire(locks: Path, repository_id: str, args: argparse.Namespace, now: datetime) -> dict:
    lock_path = locks / LOCK_NAME
    cleanup_receipts: list[str] = []
    # Legacy per-run names are inspected so an old active/malformed same-repo
    # lock cannot be bypassed by moving to the fixed-name manager.
    for candidate in sorted(locks.glob("system-dev-plan-*.json")):
        lock, raw = _read_lock(candidate)
        if lock["repository_id"] != repository_id:
            if candidate.name == LOCK_NAME:
                raise DomainBlock("fixed lock belongs to a different repository")
            continue
        expires = _parse_timestamp(lock["expires_at"], "expires_at")
        if expires > now:
            raise DomainBlock(f"active system plan lock exists: {candidate.name}")
        receipt = _expired_receipt(locks, candidate, lock, raw, now)
        cleanup_receipts.append(receipt.relative_to(Path(args._repo_root)).as_posix())
    value = _lock_value(repository_id, args, now)
    _exclusive_json(lock_path, value)
    return {
        "status": "acquired", "action": "acquire",
        "lock_path": f"{LOCK_ROOT_REL}/{LOCK_NAME}", "lock": value,
        "cleanup_receipts": cleanup_receipts,
    }


def _renew(locks: Path, repository_id: str, args: argparse.Namespace, now: datetime) -> dict:
    lock_path = locks / LOCK_NAME
    lock, raw = _read_lock(lock_path)
    _assert_owner(lock, _owner_fields(repository_id, args))
    expires = _parse_timestamp(lock["expires_at"], "expires_at")
    if expires <= now:
        receipt = _expired_receipt(locks, lock_path, lock, raw, now)
        raise DomainBlock(f"lock expired and was cleaned: {receipt.relative_to(Path(args._repo_root)).as_posix()}")
    previous_heartbeat = _parse_timestamp(lock["heartbeat_at"], "heartbeat_at")
    if now < previous_heartbeat:
        raise DomainBlock("clock regression would move heartbeat_at backwards")
    updated = dict(lock, heartbeat_at=_timestamp(now),
                   expires_at=_timestamp(now + timedelta(seconds=args.ttl_seconds)))
    _atomic_replace_json(lock_path, updated)
    return {
        "status": "renewed", "action": "renew",
        "lock_path": f"{LOCK_ROOT_REL}/{LOCK_NAME}", "lock": updated,
    }


def _release(locks: Path, repository_id: str, args: argparse.Namespace, now: datetime) -> dict:
    lock_path = locks / LOCK_NAME
    lock, raw = _read_lock(lock_path)
    _assert_owner(lock, _owner_fields(repository_id, args))
    expires = _parse_timestamp(lock["expires_at"], "expires_at")
    if expires <= now:
        receipt = _expired_receipt(locks, lock_path, lock, raw, now)
        return {
            "status": "released", "action": "release", "expired_cleanup": True,
            "lock_path": f"{LOCK_ROOT_REL}/{LOCK_NAME}",
            "cleanup_receipt": receipt.relative_to(Path(args._repo_root)).as_posix(),
        }
    lock_path.unlink()
    _fsync_dir(locks)
    return {
        "status": "released", "action": "release", "expired_cleanup": False,
        "lock_path": f"{LOCK_ROOT_REL}/{LOCK_NAME}",
    }


def _parser() -> Parser:
    parser = Parser(description="Manage the repository-local system plan lock")
    parser.add_argument("--lock-action", required=True, choices=("acquire", "renew", "release"))
    parser.add_argument("--repo-root")
    parser.add_argument("--config", default=".dev-graph/config.json")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-owner", required=True)
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--feature-digest", required=True)
    parser.add_argument("--ttl-seconds", type=int, default=900)
    return parser


def execute(argv: list[str] | None = None, env: dict | None = None) -> dict:
    args = _parser().parse_args(argv)
    _validate_cli(args)
    c09 = _load_context()
    cargv = ["--config", args.config]
    if args.repo_root:
        cargv[:0] = ["--repo-root", args.repo_root]
    try:
        context = c09.build_context(cargv, dict(os.environ if env is None else env))
    except (c09.PolicyError, c09.UsageError) as exc:
        raise ContractError(str(exc)) from exc
    repo_root = Path(context["repo_root"])
    configured = context["local_state"]["locks"]["relative"]
    if configured != LOCK_ROOT_REL:
        raise ContractError(f"config local_state.locks must be {LOCK_ROOT_REL!r}")
    locks = repo_root / LOCK_ROOT_REL
    _assert_no_symlinks(repo_root, locks)
    locks.mkdir(parents=True, mode=0o700, exist_ok=True)
    _assert_no_symlinks(repo_root, locks)
    if not locks.is_dir():
        raise ContractError("lock root is not a directory")
    args._repo_root = str(repo_root)
    now = _utc_now()
    with _operation_guard(locks):
        if args.lock_action == "acquire":
            return _acquire(locks, context["repository_id"], args, now)
        if args.lock_action == "renew":
            return _renew(locks, context["repository_id"], args, now)
        return _release(locks, context["repository_id"], args, now)


def main(argv: list[str] | None = None) -> int:
    try:
        result = execute(argv)
        code = 0
    except DomainBlock as exc:
        result = {"status": "blocked", "error_kind": "domain", "message": str(exc)}
        code = 1
    except (ContractError, OSError, ValueError) as exc:
        result = {"status": "error", "error_kind": "contract", "message": str(exc)}
        code = 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
