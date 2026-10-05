#!/usr/bin/env python3
# /// script
# name: validate-source-lineage
# purpose: origin_kind=system-spec-harness の node について source_path の実在 (repo 内) と source_digest (生 bytes の sha256 hex) の一致を副作用なしで fail-closed 検査する。
# inputs: ["argv: --repo-root PATH [--graph PATH] [--node-id ID ...]"]
# outputs: ["stdout: JSON {status, checked, checked_node_ids, violations[]}"]
# requires-python = ">=3.10"
# dependencies: [_common.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""C19 の R0 (resume) と R3 (import 後) の lineage gate。C02 add も lineage_findings を読み込んで登録前に使う。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from _common import ContractError, contained, dump, load_json

ORIGIN = "system-spec-harness"
DIGEST = re.compile(r"^[a-f0-9]{64}$")
DEFAULT_GRAPH = ".dev-graph/state/graph.json"


def imported(node: dict[str, Any]) -> bool:
    lineage = node.get("source_lineage")
    return isinstance(lineage, dict) and lineage.get("origin_kind") == ORIGIN


def lineage_findings(nodes: list[dict[str, Any]], root: Path) -> list[dict[str, str]]:
    """system-spec-harness 由来の node だけを検査する。finding は validate-graph-schema と同じ {node, code, detail}。"""
    authority = root.resolve(strict=True)
    findings: list[dict[str, str]] = []
    for index, node in enumerate(nodes):
        if not imported(node):
            continue
        node_id = str(node.get("graph_node_id") or f"nodes[{index}]")
        lineage = node["source_lineage"]
        raw, digest = lineage.get("source_path"), lineage.get("source_digest")
        pure = PurePosixPath(raw) if isinstance(raw, str) else None
        if pure is None or not raw or "\\" in raw or pure.is_absolute() or ".." in pure.parts:
            findings.append({"node": node_id, "code": "lineage_source_path_invalid",
                             "detail": f"source_path {raw!r} は repo 相対の path でなければならない"})
            continue
        try:
            target = contained(authority / raw, authority, must_exist=True)
        except ContractError:
            findings.append({"node": node_id, "code": "lineage_source_outside_repository",
                             "detail": f"{raw} は symlink などで repo の外を指している"})
            continue
        except (OSError, RuntimeError):
            findings.append({"node": node_id, "code": "lineage_source_missing", "detail": f"{raw} が存在しない"})
            continue
        if not target.is_file():
            findings.append({"node": node_id, "code": "lineage_source_missing", "detail": f"{raw} は通常ファイルではない"})
            continue
        if not isinstance(digest, str) or not DIGEST.match(digest):
            findings.append({"node": node_id, "code": "lineage_digest_invalid",
                             "detail": f"source_digest {digest!r} は sha256 の 64 桁 hex でなければならない"})
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            findings.append({"node": node_id, "code": "lineage_digest_mismatch",
                             "detail": f"{raw}: source_digest {digest} と現物の sha256 {actual} が一致しない"})
    return findings


def _graph_path(root: Path, raw: str | None) -> Path:
    path = Path(raw or DEFAULT_GRAPH).expanduser()
    return contained(path if path.is_absolute() else root / path, root, must_exist=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="system-spec-harness 由来の source_lineage を検査する (読取りのみ)")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--graph", help=f"repo 相対または絶対 path (既定: {DEFAULT_GRAPH})")
    parser.add_argument("--node-id", action="append", default=[], help="検査対象を絞る graph_node_id (複数可)")
    args = parser.parse_args(argv)
    try:
        root = Path(args.repo_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ContractError(f"--repo-root {root} is not a directory")
        graph = _graph_path(root, args.graph)
        data = load_json(graph)
        values = data.get("nodes") if isinstance(data, dict) else None
        if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
            raise ContractError("graph must be an object with nodes[]")
        nodes = values
        if args.node_id:
            known = {node.get("graph_node_id") for node in nodes}
            unknown = sorted(set(args.node_id) - known)
            if unknown:
                raise ContractError(f"--node-id {unknown} is not in the graph")
            nodes = [node for node in nodes if node.get("graph_node_id") in set(args.node_id)]
    except (ContractError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        dump({"status": "error", "error": str(exc), "checked": 0, "checked_node_ids": [], "violations": []})
        return 2
    checked = [str(node.get("graph_node_id")) for node in nodes if imported(node)]
    violations = lineage_findings(nodes, root)
    dump({"status": "fail" if violations else "pass", "checked": len(checked), "checked_node_ids": checked,
          "graph": graph.relative_to(root).as_posix(), "violations": violations})
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
