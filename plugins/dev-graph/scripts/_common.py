#!/usr/bin/env python3
# /// script
# name: dev-graph-common
# purpose: Share stdlib-only fail-closed process, JSON, containment, atomic-write and identity primitives.
# inputs: ["Python imports only"]
# outputs: ["Reusable helper functions"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: caller-defined atomic JSON target only
# ///
"""Shared stdlib-only safety primitives for dev-graph scripts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence


class ContractError(RuntimeError):
    """A fail-closed contract violation (exit 1)."""


def run(argv: Sequence[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        cp = subprocess.run(list(argv), cwd=cwd, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise ContractError(f"cannot execute {argv[0]}: {exc}") from exc
    if check and cp.returncode:
        detail = (cp.stderr or cp.stdout).strip()
        raise ContractError(f"command failed ({cp.returncode}): {' '.join(argv)}: {detail}")
    return cp


def git(args: Sequence[str], root: Path, *, check: bool = True) -> str:
    return run(["git", "-C", str(root), *args], check=check).stdout.strip()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON {path}: {exc}") from exc


def dump(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def contained(path: Path, root: Path, *, must_exist: bool = True) -> Path:
    candidate = path.resolve(strict=must_exist)
    authority = root.resolve(strict=True)
    try:
        candidate.relative_to(authority)
    except ValueError as exc:
        raise ContractError(f"path escapes authority root: {candidate} not within {authority}") from exc
    return candidate


def stable_id(prefix: str, *parts: str, size: int = 16) -> str:
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:size]
    return f"{prefix}{digest}"


def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
