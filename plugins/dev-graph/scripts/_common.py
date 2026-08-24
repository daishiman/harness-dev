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


def canonical_digest(value: Any) -> str:
    """Return the shared sha256 digest for canonical JSON values."""
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def c11_readiness_digest(nodes: Sequence[dict[str, Any]], feature_id: str) -> str:
    """Digest the C11/C02 eligibility evidence for one feature package.

    Volatile timestamps are intentionally excluded. The projection binds the
    feature, its related system-spec nodes, and its registered task package to
    confirmation/evaluation/readiness, lineage, and dependency evidence.
    """
    by_id = {
        node.get("graph_node_id") or node.get("id"): node
        for node in nodes
        if isinstance(node, dict)
        and isinstance(node.get("graph_node_id") or node.get("id"), str)
        and (node.get("graph_node_id") or node.get("id"))
    }
    feature = by_id.get(feature_id)
    if not isinstance(feature, dict) or feature.get("artifact_kind") != "feature":
        raise ContractError(f"C11 readiness feature not found: {feature_id}")
    related = feature.get("related_nodes")
    related_ids = sorted(value for value in related if isinstance(value, str)) if isinstance(related, list) else []
    child_ids = sorted(
        node_id
        for node_id, node in by_id.items()
        if node.get("parent_feature") == feature_id
    )
    scope_ids = [feature_id, *related_ids, *child_ids]
    projection: list[dict[str, Any]] = []
    for node_id in sorted(set(scope_ids)):
        node = by_id.get(node_id)
        if not isinstance(node, dict):
            projection.append({"graph_node_id": node_id, "missing": True})
            continue
        readiness = node.get("implementation_readiness")
        readiness = readiness if isinstance(readiness, dict) else {}
        missing = readiness.get("missing_sections")
        missing = sorted(value for value in missing if isinstance(value, str)) if isinstance(missing, list) else []
        lineage = node.get("source_lineage")
        lineage = lineage if isinstance(lineage, dict) else {}
        dependencies = node.get("depends_on")
        dependencies = sorted(value for value in dependencies if isinstance(value, str)) if isinstance(dependencies, list) else []
        node_related = node.get("related_nodes")
        node_related = sorted(value for value in node_related if isinstance(value, str)) if isinstance(node_related, list) else []
        projection.append(
            {
                "graph_node_id": node_id,
                "artifact_kind": node.get("artifact_kind"),
                "file_path": node.get("file_path"),
                "confirmation_status": node.get("confirmation_status"),
                "evaluation_status": node.get("evaluation_status"),
                "implementation_readiness": {
                    "status": readiness.get("status"),
                    "missing_sections": missing,
                },
                "source_digest": lineage.get("source_digest"),
                "parent_feature": node.get("parent_feature"),
                "feature_package_id": node.get("feature_package_id"),
                "phase_ref": node.get("phase_ref"),
                "depends_on": dependencies,
                "related_nodes": node_related,
            }
        )
    return canonical_digest(
        {
            "schema_version": "c11-readiness-digest-v1",
            "feature_id": feature_id,
            "nodes": projection,
        }
    )


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
