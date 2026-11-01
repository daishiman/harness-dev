"""C16 が graph node 単位で下す判定の部品 (import 専用 module)。

resource_scope の正規化と重なり、schedulable の判定、未完了依存の列挙を持つ。
ready payload・lease snapshot の読込と plan の組立ては `schedule-graph.py` 側に残し、
この module は入力 node と node 索引だけから決まる判定を返す。
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import posixpath
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _common import ContractError

ScopePath = tuple[str, ...]


def node_id_of(node: dict[str, Any]) -> Any:
    return node.get("graph_node_id") or node.get("id")


def scope_paths(values: Any, owner: str) -> set[ScopePath]:
    """Normalize a ``resource_scope: string[]`` into repository-relative path components.

    ``./packages/api``, ``packages/api/`` and ``packages/api`` are the same path
    (``posixpath.normpath``); ``.`` is the repository root (``()``). Absolute paths
    and paths that start with ``..`` after normalization point outside the
    repository, so they fail closed instead of escaping the conflict check.
    """
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise ContractError(f"{owner}: resource_scope must be a non-empty string[]")
    result: set[ScopePath] = set()
    for value in values:
        if value.startswith("/"):
            raise ContractError(f"{owner}: resource_scope must be repository-relative: {value}")
        path = posixpath.normpath(value)
        if path == ".." or path.startswith("../"):
            raise ContractError(f"{owner}: resource_scope escapes the repository: {value}")
        result.add(() if path == "." else tuple(path.split("/")))
    return result


def overlaps(left: set[ScopePath], right: set[ScopePath]) -> bool:
    """Two scopes conflict when a path equals, or is a component-wise ancestor of, a path in the other.

    ``packages/api`` covers ``packages/api/users.py`` but not ``packages/apix``
    (components are compared, not string prefixes).
    """
    return any(a[:len(b)] == b or b[:len(a)] == a for a in left for b in right)


def shared_paths(left: set[ScopePath], right: set[ScopePath]) -> list[str]:
    """List the region two scopes both touch, for conflict reports.

    祖先と子孫が重なるとき、両者が共に触るのは子孫側の path である。
    `overlaps()` と同じ成分比較で数え、表示用に `/` 区切り (root は ``.``) へ戻す。
    """
    shared = {
        a if len(a) >= len(b) else b
        for a in left for b in right
        if a[:len(b)] == b or b[:len(a)] == a
    }
    return sorted("/".join(path) or "." for path in shared)


def touches(node: dict[str, Any]) -> set[ScopePath]:
    """Return the canonical graph-node `resource_scope: string[]` value as normalized paths.

    Older prototypes used ``{"touches": [...]}``, but that shape contradicts
    graph-node.schema.json and silently erased every scope during scheduling.
    Reject the stale shape instead of producing an unsafe parallel batch.
    """
    return scope_paths(node.get("resource_scope", []), str(node_id_of(node) or "<unknown>"))


def is_schedulable(node: dict[str, Any]) -> bool:
    """Return whether C16 may consider a node for a ready recommendation."""
    readiness = node.get("implementation_readiness") or {}
    return (
        node.get("status") == "active"
        and node.get("confirmation_status") == "confirmed"
        and node.get("evaluation_status") == "pass"
        and isinstance(readiness, dict)
        and readiness.get("status") == "complete"
    )


def _dependency_list(node: dict[str, Any], owner: Any) -> list[Any]:
    dependencies = node.get("depends_on", [])
    if not isinstance(dependencies, list):
        raise ContractError(f"{owner}: depends_on must be a list")
    return dependencies


def blocking_dependencies(
    node: dict[str, Any], by_id: dict[Any, dict[str, Any]], done: set[Any]
) -> list[Any]:
    """Return the unfinished dependencies that keep ``node`` out of the ready set.

    SKILL.md requires every dependency to be done (完了条件・Gotchas). A done node can
    still depend on an open one: C02 accepts ``status`` and ``depends_on`` patches and
    C11 does not reject the pair, so the walk continues through done nodes and returns
    the first unfinished node on each path, not only the direct ones. An id missing
    from the graph is never done, so it blocks as well.

    P01 is a package entry point. Its own ``depends_on`` is an intra-feature list; its
    parent feature's macro dependencies are evaluated here as an entry gate instead
    of being copied onto the task. A P01 task without a graph parent stops schedule
    generation rather than silently skipping the gate.
    """
    owner = node_id_of(node)
    roots = list(_dependency_list(node, owner))
    if node.get("artifact_kind", node.get("kind")) == "task" and node.get("phase_ref") == "P01":
        parent_id = node.get("parent_feature")
        if not isinstance(parent_id, str) or parent_id not in by_id:
            raise ContractError(f"{owner}: P01 task requires a graph parent_feature")
        roots.extend(_dependency_list(by_id[parent_id], parent_id))
    blocking: set[Any] = set()
    seen: set[Any] = set()
    pending = roots
    while pending:
        dep = pending.pop()
        if dep in seen:
            continue
        seen.add(dep)
        if dep not in done:
            blocking.add(dep)
            continue
        pending.extend(_dependency_list(by_id[dep], dep))
    return sorted(blocking, key=str)
