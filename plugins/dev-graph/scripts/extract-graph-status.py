#!/usr/bin/env python3
# /// script
# name: extract-graph-status
# purpose: Validate and query canonical dev-graph status without mutating repository or external tracker state.
# inputs: ["argv: --repo-root PATH [--id ID] [--kind KIND] [--project ID] [--domain NAME] [--status STATUS] [--tag TAG] [--tag-match all|any] [--keyword TEXT]"]
# outputs: ["stdout: JSON read-only status report with C11 and before/after digest evidence"]
# requires-python = ">=3.10"
# dependencies: [_common.py, resolve-repo-context.py, validate-graph-schema.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""C18 deterministic read-only graph status query."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, contained, dump, load_json


HERE = Path(__file__).resolve().parent
RESOLVER = HERE / "resolve-repo-context.py"
C11 = HERE / "validate-graph-schema.py"
KINDS = {"issue", "task", "specification", "architecture", "feature", "document"}
STATUSES = {"draft", "active", "blocked", "done", "closed", "tombstoned"}


def _receipt(root: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    completed = subprocess.run(
        [sys.executable, str(RESOLVER), "--repo-root", str(root), "--mode", "read"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        raise ContractError(f"C24 repository context failed: {completed.stderr.strip() or completed.stdout.strip()}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("C24 returned invalid JSON") from exc
    if not isinstance(value, dict) or Path(str(value.get("repo_root", ""))).resolve() != root:
        raise ContractError("C24 repository identity mismatch")
    return value


def _graph(root: Path, receipt: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    local = receipt.get("local_state_paths")
    if not isinstance(local, dict):
        raise ContractError("C24 local_state_paths is missing")
    graph_path = contained(Path(str(local.get("graph", ""))), root, must_exist=True)
    config_path = contained(Path(str(local.get("config", ""))), root, must_exist=True)
    value = load_json(graph_path)
    if not isinstance(value, dict) or not isinstance(value.get("nodes"), list):
        raise ContractError("graph must contain nodes[]")
    if not all(isinstance(node, dict) for node in value["nodes"]):
        raise ContractError("graph nodes[] must contain objects")
    return graph_path, config_path, value


def _inventory(root: Path, graph_path: Path, config_path: Path, graph: dict[str, Any]) -> dict[str, str]:
    paths = {"graph": graph_path, "config": config_path}
    for index, node in enumerate(graph["nodes"]):
        raw = node.get("file_path")
        if not isinstance(raw, str) or not raw:
            raise ContractError(f"nodes[{index}].file_path is invalid")
        artifact = contained(root / raw, root, must_exist=True)
        paths[f"content:{artifact.relative_to(root).as_posix()}"] = artifact
    return {
        label: hashlib.sha256(path.read_bytes()).hexdigest()
        for label, path in sorted(paths.items())
    }


def _inventory_digest(inventory: dict[str, str]) -> str:
    payload = json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _validate_c11(root: Path, graph_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(C11), "--graph", str(graph_path), "--repo-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"C11 returned invalid JSON: {completed.stderr.strip()}") from exc
    if completed.returncode != 0 or not isinstance(report, dict) or report.get("valid") is not True:
        raise ContractError(f"C11 validation failed: {report}")
    return report


def _matches(node: dict[str, Any], args: argparse.Namespace) -> bool:
    exact = {
        "graph_node_id": args.id,
        "artifact_kind": args.kind,
        "project_id": args.project,
        "domain": args.domain,
        "status": args.status,
    }
    if any(value is not None and node.get(key) != value for key, value in exact.items()):
        return False
    tags = node.get("tags")
    if args.tag:
        if not isinstance(tags, list):
            return False
        checks = [tag in tags for tag in args.tag]
        if not (all(checks) if args.tag_match == "all" else any(checks)):
            return False
    if args.keyword:
        haystack = " ".join(str(node.get(key, "")) for key in ("graph_node_id", "title"))
        if args.keyword.casefold() not in haystack.casefold():
            return False
    return True


def query(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root or os.getcwd()).expanduser().resolve(strict=True)
    receipt = _receipt(root)
    graph_path, config_path, graph = _graph(root, receipt)
    before = _inventory(root, graph_path, config_path, graph)
    c11 = _validate_c11(root, graph_path)
    by_id = {node["graph_node_id"]: node for node in graph["nodes"]}
    results: list[dict[str, Any]] = []
    for node in graph["nodes"]:
        if not _matches(node, args):
            continue
        node_id = node["graph_node_id"]
        results.append({
            "graph_node_id": node_id,
            "artifact_kind": node["artifact_kind"],
            "project_id": node["project_id"],
            "domain": node["domain"],
            "tags": node["tags"],
            "file_path": node["file_path"],
            "status": node["status"],
            "closed_at": node.get("closed_at"),
            "depends_on": node["depends_on"],
            "dependents": sorted(
                other_id for other_id, other in by_id.items()
                if node_id in (other.get("depends_on") or [])
            ),
            "parent_feature": node["parent_feature"],
            "feature_package_id": node["feature_package_id"],
            "tracker_binding": node["tracker_binding"],
            "linkage": {
                "issue_linkage": node["issue_linkage"],
                "beads_linkage": node["beads_linkage"],
                "github_project_linkages": node["github_project_linkages"],
                "pull_request_linkages": node["pull_request_linkages"],
            },
        })
    after_graph = load_json(graph_path)
    if not isinstance(after_graph, dict) or not isinstance(after_graph.get("nodes"), list):
        raise ContractError("graph became invalid during read-only query")
    after = _inventory(root, graph_path, config_path, after_graph)
    if before != after:
        raise ContractError("read-only status query changed graph/config/content digests")
    before_digest = _inventory_digest(before)
    after_digest = _inventory_digest(after)
    return {
        "schema_version": "1.0.0",
        "owner": "C18/run-dev-graph-status",
        "operation": "status_search",
        "read_only": True,
        "filters": {
            "graph_node_id": args.id,
            "artifact_kind": args.kind,
            "project_id": args.project,
            "domain": args.domain,
            "status": args.status,
            "tags": args.tag,
            "tag_match_mode": args.tag_match,
            "keyword": args.keyword,
        },
        "result_count": len(results),
        "results": results,
        "c11": {"valid": True, "violations": c11.get("violations", [])},
        "digest_evidence": {
            "file_count": len(before),
            "sha256_before": before_digest,
            "sha256_after": after_digest,
        },
        "digests_unchanged": True,
        "write_count": 0,
        "external_writes": {"github": 0, "beads": 0},
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="C18 read-only dev-graph status query")
    parser.add_argument("--repo-root")
    parser.add_argument("--id")
    parser.add_argument("--kind", choices=sorted(KINDS))
    parser.add_argument("--project")
    parser.add_argument("--domain")
    parser.add_argument("--status", choices=sorted(STATUSES))
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--tag-match", choices=("all", "any"), default="all")
    parser.add_argument("--keyword")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        dump(query(_parser().parse_args(argv)))
        return 0
    except (ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        dump({"valid": False, "error": str(exc), "read_only": True, "write_count": 0})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
