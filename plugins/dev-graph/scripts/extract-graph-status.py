#!/usr/bin/env python3
# /// script
# name: extract-graph-status
# purpose: Build the run-dev-graph-status search rows from the graph bytes that pass the same C11 validation, with every report key present (missing keys 0) and the graph/config/content bytes unchanged across the read.
# inputs: ["argv: --repo-root PATH [--config PATH] [--id ID]... [--kind KIND]... [--project ID]... [--domain NAME]... [--status STATUS]... [--feature ID]... [--tag TAG]... [--tag-mode any|all] [--keyword TEXT]"]
# outputs: ["stdout: JSON status report {query, graph{path, digest, graph_revision, node_count}, validation, missing_required_keys, rows[], count, result, read_only}", "exit: 0=rows (empty is a success) / 1=validation, missing key or changed bytes (no rows) / 2=usage, C24 or IO"]
# requires-python = ">=3.10"
# dependencies: [_common.py, resolve-repo-context.py, validate-graph-schema.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""C18 status extractor.

The repository is fixed by C24 (``resolve-repo-context.py --mode read``); its receipt names the graph. The graph bytes
are read once, and those same bytes go through C11 (``validate-graph-schema.validate`` with the C24 root). Rows are
built only when C11 reports no violation and every node carries every report key (``REPORT_KEYS``); otherwise the
report carries the diagnostics and no rows. Nothing is inferred: ``closed_at`` is the graph value (absent reads
null), ``dependents`` is the reverse of ``depends_on`` over the whole graph.

Filters are ANDed. Repeating one filter matches any of its values. ``--feature`` matches ``parent_feature`` or
``feature_package_id``. Two or more ``--tag`` need an explicit ``--tag-mode`` (any / all). ``--keyword`` is a
case-insensitive substring of graph_node_id, title or file_path. No match is an empty success.

The digest of the graph, the config and every node file is taken before and after the read; a difference fails the
run. The script calls no writer, gh or bd.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない (子の起動にも -B を渡す)。
sys.dont_write_bytecode = True

from _common import ContractError, contained, dump, run

SCRIPTS = Path(__file__).resolve().parent
RESOLVE = SCRIPTS / "resolve-repo-context.py"
REPORT_KEYS = ("graph_node_id", "artifact_kind", "title", "project_id", "domain", "tags", "file_path", "status",
               "depends_on", "parent_feature", "feature_package_id", "tracker_binding", "issue_linkage",
               "beads_linkage", "github_project_linkages")
FILTERS = ("id", "kind", "project", "domain", "status", "feature")


def _validator() -> Any:
    spec = importlib.util.spec_from_file_location("dev_graph_validate_graph_schema", SCRIPTS / "validate-graph-schema.py")
    if spec is None or spec.loader is None:
        raise ContractError("cannot load validate-graph-schema.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _context(repo_root: str, config: str) -> dict[str, Any]:
    cp = run([sys.executable, "-B", str(RESOLVE), "--repo-root", repo_root, "--config", config, "--mode", "read"], check=False)
    if cp.returncode:
        raise ContractError(f"resolve-repo-context failed: {(cp.stderr or cp.stdout).strip()}")
    receipt = json.loads(cp.stdout)
    root = Path(receipt["repo_root"]).resolve(strict=True)
    if Path(receipt["content_roots"]["repository"]).resolve(strict=True) != root:
        raise ContractError("resolve-repo-context repo_root differs from content_roots.repository")
    return receipt


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _snapshot(root: Path, paths: list[str]) -> dict[str, str | None]:
    """repo 相対 path → bytes の digest。読めないものは None (読んだ前後で同じかだけを見る)。"""
    digests: dict[str, str | None] = {}
    for rel in sorted(set(paths)):
        try:
            digests[rel] = _digest(contained(root / rel, root).read_bytes())
        except (OSError, ContractError):
            digests[rel] = None
    return digests


def missing_keys(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"graph_node_id": str(node.get("graph_node_id") or f"nodes[{index}]"), "key": key}
            for index, node in enumerate(nodes) for key in REPORT_KEYS if key not in node]


def matches(node: dict[str, Any], query: dict[str, Any]) -> bool:
    fields = {"id": [node["graph_node_id"]], "kind": [node["artifact_kind"]], "project": [node["project_id"]],
              "domain": [node["domain"]], "status": [node["status"]],
              "feature": [node["parent_feature"], node["feature_package_id"]]}
    for name in FILTERS:
        wanted = query[name]
        if wanted and not set(wanted) & {value for value in fields[name] if value is not None}:
            return False
    tags = set(node["tags"] or [])
    if query["tag"]:
        hit = (all if query["tag_mode"] == "all" else any)(tag in tags for tag in query["tag"])
        if not hit:
            return False
    keyword = query["keyword"]
    if keyword:
        haystack = " ".join(str(node.get(key) or "") for key in ("graph_node_id", "title", "file_path")).casefold()
        if keyword.casefold() not in haystack:
            return False
    return True


def rows_of(nodes: list[dict[str, Any]], query: dict[str, Any]) -> list[dict[str, Any]]:
    dependents: dict[str, list[str]] = {}
    for node in nodes:
        for dependency in node["depends_on"] or []:
            dependents.setdefault(dependency, []).append(node["graph_node_id"])
    return [{**{key: node[key] for key in REPORT_KEYS}, "closed_at": node.get("closed_at"),
             "dependents": sorted(dependents.get(node["graph_node_id"], []))}
            for node in sorted(nodes, key=lambda item: str(item["graph_node_id"])) if matches(node, query)]


def extract(receipt: dict[str, Any], query: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    root = Path(receipt["repo_root"]).resolve(strict=True)
    graph_path = contained(Path(receipt["local_state_paths"]["graph"]), root)
    config_path = Path(receipt["local_state_paths"]["config"])
    graph_bytes = graph_path.read_bytes()
    vgs = _validator()
    data = json.loads(graph_bytes.decode("utf-8"))
    nodes = vgs.nodes_of(data)
    graph_rel = graph_path.relative_to(root).as_posix()
    tracked = [graph_rel, *(str(node["file_path"]) for node in nodes if isinstance(node.get("file_path"), str))]
    if config_path.exists():
        tracked.append(contained(config_path, root).relative_to(root).as_posix())
    before = {**_snapshot(root, tracked), graph_rel: _digest(graph_bytes)}  # 検証するのは最初に読んだ bytes
    violations = vgs.validate(nodes, repo_root=vgs._repo_root_for(graph_path, str(root)))
    absent = missing_keys(nodes)
    rows = rows_of(nodes, query) if not violations and not absent else []
    after = _snapshot(root, tracked)
    changed = sorted(rel for rel in before if before[rel] != after.get(rel))
    failed = bool(violations or absent or changed)
    report = {
        "schema_version": "1.0.0",
        "query": query,
        "graph": {"path": graph_path.relative_to(root).as_posix(), "digest": _digest(graph_bytes),
                  "graph_revision": data.get("graph_revision") if isinstance(data, dict) else None, "node_count": len(nodes)},
        "validation": {"status": "fail" if violations else "pass", "violation_count": len(violations), "violations": violations},
        "missing_required_keys": absent,
        "read_only": {"tracked_files": len(before), "changed": changed},
        "rows": [] if failed else rows,
        "count": 0 if failed else len(rows),
        "result": "rejected" if failed else "matched" if rows else "empty",
    }
    return (1 if failed else 0), report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo-root", required=True)
    p.add_argument("--config", default=".dev-graph/config.json")
    for name in FILTERS:
        p.add_argument(f"--{name}", action="append", default=[])
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--tag-mode", choices=("any", "all"))
    p.add_argument("--keyword")
    a = p.parse_args(argv)
    if len(a.tag) > 1 and a.tag_mode is None:
        p.error("two or more --tag need an explicit --tag-mode any|all")
    query = {**{name: sorted(set(getattr(a, name))) for name in FILTERS}, "tag": sorted(set(a.tag)),
             "tag_mode": a.tag_mode or ("any" if a.tag else None), "keyword": a.keyword}
    code, report = extract(_context(a.repo_root, a.config), query)
    dump(report)
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
