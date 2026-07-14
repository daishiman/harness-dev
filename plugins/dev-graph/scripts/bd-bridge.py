#!/usr/bin/env python3
# /// script
# name: bd-bridge
# purpose: Be the single deterministic CLI choke point for allowed Beads task, edge, mirror and gate operations.
# inputs: ["argv: --op OP and operation fields"]
# outputs: ["stdout: normalized JSON receipt"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: true
# write-scope: approved bd CLI only; never direct .beads I/O
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, dump, run

MUTATIONS = {"create", "update", "dep-add", "close", "claim", "github-push", "gate-add"}
PHASES = [f"P{i:02d}" for i in range(1, 14)]


def bd(args: list[str], *, cwd: Path, check: bool = True) -> Any:
    cp = run([os.environ.get("DEV_GRAPH_BD", "bd"), *args], cwd=cwd, check=check)
    raw = cp.stdout.strip()
    if not raw: return {"ok": cp.returncode == 0}
    try:
        value = json.loads(raw)
        if isinstance(value, dict) and "data" in value and "schema_version" in value:
            return value["data"]
        return value
    except json.JSONDecodeError: return {"text": raw, "returncode": cp.returncode}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list): return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        for key in ("issues", "results", "data"):
            rows = value.get(key)
            if isinstance(rows, list): return [row for row in rows if isinstance(row, dict)]
        return [value]
    return []


def _workspace_identity(value: Any) -> dict[str, Any]:
    rows = _rows(value)
    if len(rows) != 1: raise ContractError("bd where must identify exactly one workspace")
    row = rows[0]
    identity_keys = ("database_path", "prefix", "schema_version") if row.get("database_path") else ("path", "prefix", "schema_version", "workspace", "id")
    stable = {key: str(row[key]) for key in identity_keys if row.get(key) is not None}
    if not stable: raise ContractError("bd where did not expose a stable workspace identity")
    fingerprint = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"workspace_id": f"bdw_{fingerprint[:24]}", "attributes": stable}


def preflight(root: Path, expected_workspace_id: str | None = None) -> dict[str, Any]:
    version_raw = run([os.environ.get("DEV_GRAPH_BD", "bd"), "version"], cwd=root).stdout
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_raw)
    if not match or not ((1, 1, 0) <= tuple(map(int, match.groups())) < (2, 0, 0)):
        raise ContractError(f"unsupported bd version: {version_raw.strip()}")
    where = bd(["where", "--json"], cwd=root, check=False)
    if isinstance(where, dict) and where.get("returncode", 0) not in (0, None): raise ContractError("bd workspace unavailable")
    identity = _workspace_identity(where)
    if expected_workspace_id and identity["workspace_id"] != expected_workspace_id:
        raise ContractError("linked worktree resolves a different Beads workspace")
    return {"version": match.group(0), "workspace_identity": identity}


def _issue(value: Any, issue_id: str) -> dict[str, Any]:
    rows = [row for row in _rows(value) if str(row.get("id")) == issue_id]
    if len(rows) != 1: raise ContractError(f"bd show did not return exactly one issue: {issue_id}")
    return rows[0]


def _dependency_ids(issue: dict[str, Any]) -> set[str]:
    raw = issue.get("dependencies", [])
    if not isinstance(raw, list): raise ContractError("bd show dependencies must be an array")
    result: set[str] = set()
    for item in raw:
        relation = (item.get("dependency_type") or item.get("type")) if isinstance(item, dict) else None
        if relation not in (None, "blocks"):
            continue
        dep = item.get("id") if isinstance(item, dict) else item
        if not isinstance(dep, str) or not dep: raise ContractError("bd dependency is missing its id")
        result.add(dep)
    return result


def verify_parity(issue: dict[str, Any], expected_status: str | None, expected_dependencies: list[str]) -> dict[str, Any]:
    if not expected_status: raise ContractError("parity verification requires --expected-status")
    expected = set(expected_dependencies)
    actual = _dependency_ids(issue)
    status_match = issue.get("status") == expected_status
    edges_match = actual == expected
    receipt = {
        "confirmed": status_match and edges_match,
        "expected_status": expected_status,
        "actual_status": issue.get("status"),
        "expected_depends_on": sorted(expected),
        "actual_depends_on": sorted(actual),
        "missing_edges": sorted(expected - actual),
        "unexpected_edges": sorted(actual - expected),
    }
    if not receipt["confirmed"]: raise ContractError(f"Beads parity conflict: {json.dumps(receipt, sort_keys=True)}")
    return receipt


def _load_manifest(path: str | None, root: Path, *, label: str) -> dict[str, Any] | None:
    if not path:
        return None
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else root / candidate
    try:
        candidate = candidate.resolve(strict=True)
        candidate.relative_to(root)
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid {label} manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} manifest must be an object")
    return value


def _external_ref(row: dict[str, Any]) -> str | None:
    direct = row.get("external_ref") or row.get("externalRef")
    if isinstance(direct, str) and direct:
        return direct.removeprefix("dev-graph:").removeprefix("external_ref:")
    match = re.search(r"(?:^|\s)external_ref:([^\s]+)", str(row.get("description", "")))
    return match.group(1) if match else None


def _find_external(root: Path, graph_node_id: str) -> dict[str, Any] | None:
    marker = f"dev-graph:{graph_node_id}"
    rows = _rows(bd(["search", "--external-contains", marker, "--status", "all", "--json"], cwd=root, check=False))
    exact = [row for row in rows if _external_ref(row) == graph_node_id]
    if len(exact) > 1:
        raise ContractError(f"duplicate beads external_ref for {graph_node_id}")
    return exact[0] if exact else None


def _create_one(
    root: Path,
    *,
    graph_node_id: str,
    title: str,
    description: str,
    issue_type: str,
    parent: str | None = None,
) -> dict[str, Any]:
    existing = _find_external(root, graph_node_id)
    if existing:
        actual_type = existing.get("issue_type") or existing.get("type")
        if actual_type and actual_type != issue_type:
            raise ContractError(f"existing {graph_node_id} has type {actual_type}, expected {issue_type}")
        actual_parent = existing.get("parent") or existing.get("parent_id")
        if parent and str(actual_parent) != parent:
            raise ContractError(f"existing {graph_node_id} belongs to a different epic")
        return {"id": existing.get("id"), "external_ref": graph_node_id, "idempotent": True}
    argv = [
        "create", "--title", title, "--description", description,
        "--external-ref", f"dev-graph:{graph_node_id}", "--type", issue_type,
    ]
    if parent:
        argv += ["--parent", parent]
    argv += ["--json"]
    created = bd(argv, cwd=root)
    rows = _rows(created)
    issue_id = (created.get("id") if isinstance(created, dict) else None) or (rows[0].get("id") if rows else None)
    if not issue_id:
        raise ContractError(f"bd create did not return an id for {graph_node_id}")
    return {"id": issue_id, "external_ref": graph_node_id, "created": created}


def _validate_projection(manifest: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    feature = manifest.get("feature")
    children = manifest.get("children")
    if not isinstance(feature, dict) or not isinstance(children, list) or not all(isinstance(row, dict) for row in children):
        raise ContractError("projection manifest requires feature object and children array")
    feature_id = feature.get("graph_node_id")
    if not isinstance(feature_id, str) or not feature_id:
        raise ContractError("projection feature requires graph_node_id")
    phases = [row.get("phase_ref") for row in children]
    child_ids = [row.get("graph_node_id") for row in children]
    if len(children) != 13 or phases != PHASES or len(set(child_ids)) != 13 or any(not isinstance(value, str) or not value for value in child_ids):
        raise ContractError("projection children must be the ordered P01..P13 exact-set with unique graph_node_id")
    if any(row.get("parent_feature") != feature_id for row in children):
        raise ContractError("projection children must share the feature parent")
    id_set = set(child_ids)
    for row in children:
        dependencies = row.get("depends_on", [])
        if not isinstance(dependencies, list) or any(dep not in id_set for dep in dependencies):
            raise ContractError("projection child dependency escapes the exact-13 package")
    return feature, children


def _package_projection(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    feature, children = _validate_projection(manifest)
    feature_id = feature["graph_node_id"]

    epic = _create_one(
        root,
        graph_node_id=feature_id,
        title=str(feature.get("title") or feature_id),
        description=str(feature.get("description") or "dev-graph feature projection"),
        issue_type="epic",
    )
    projected: list[dict[str, Any]] = []
    issue_ids: dict[str, str] = {}
    for row in children:
        projected_row = _create_one(
            root,
            graph_node_id=row["graph_node_id"],
            title=str(row.get("title") or f"{row['phase_ref']} {row['graph_node_id']}"),
            description=str(row.get("description") or f"dev-graph {row['phase_ref']} projection"),
            issue_type="task",
            parent=str(epic["id"]),
        )
        projected_row["phase_ref"] = row["phase_ref"]
        projected.append(projected_row)
        issue_ids[row["graph_node_id"]] = str(projected_row["id"])
    edges: list[dict[str, Any]] = []
    for row in children:
        issue_id = issue_ids[row["graph_node_id"]]
        for dependency in row.get("depends_on", []):
            dependency_id = issue_ids[dependency]
            current = _issue(bd(["show", issue_id, "--json"], cwd=root), issue_id)
            if dependency_id in _dependency_ids(current):
                edges.append({"issue_id": issue_id, "depends_on": dependency_id, "idempotent": True})
            else:
                result = bd(["dep", "add", issue_id, dependency_id, "--type", "blocks", "--json"], cwd=root)
                edges.append({"issue_id": issue_id, "depends_on": dependency_id, "result": result})
    parity: list[dict[str, Any]] = []
    for row in children:
        issue_id = issue_ids[row["graph_node_id"]]
        current = _issue(bd(["show", issue_id, "--json"], cwd=root), issue_id)
        expected_edges = [issue_ids[dependency] for dependency in row.get("depends_on", [])]
        parity.append({
            "graph_node_id": row["graph_node_id"],
            "bd_issue_id": issue_id,
            "edge_parity": verify_parity(current, current.get("status"), expected_edges),
        })
    return {
        "feature_epic": epic,
        "children": projected,
        "edges": edges,
        "parity": parity,
        "phase_refs": PHASES,
        "expected_count": 13,
        "applied_count": len(projected),
    }


def _ready_with_parity(root: Path, raw: Any, manifest: dict[str, Any] | None) -> dict[str, Any]:
    candidates = _rows(raw)
    entries = manifest.get("nodes", []) if manifest else []
    if not isinstance(entries, list) or not all(isinstance(row, dict) for row in entries):
        raise ContractError("parity manifest nodes must be an array of objects")
    by_issue = {str(row.get("bd_issue_id")): row for row in entries if row.get("bd_issue_id")}
    if len(by_issue) != len([row for row in entries if row.get("bd_issue_id")]):
        raise ContractError("parity manifest contains duplicate bd_issue_id")
    by_graph = {str(row.get("graph_node_id")): str(row.get("bd_issue_id")) for row in entries if row.get("graph_node_id") and row.get("bd_issue_id")}
    if len(by_graph) != len(entries):
        raise ContractError("parity manifest requires unique graph_node_id and bd_issue_id for every node")
    status_map = {"active": "open", "blocked": "blocked", "done": "closed", "closed": "closed", "tombstoned": "closed"}
    ready_set: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for candidate in candidates:
        issue_id = str(candidate.get("id") or "")
        expected = by_issue.get(issue_id)
        if not expected:
            unmapped.append({"bd_issue_id": issue_id or None, "external_ref": _external_ref(candidate), "reason": "parity_manifest_missing"})
            continue
        shown = _issue(bd(["show", issue_id, "--json"], cwd=root), issue_id)
        try:
            graph_status = expected.get("graph_status")
            if graph_status not in status_map:
                raise ContractError(f"unsupported graph status in parity manifest: {graph_status}")
            graph_dependencies = expected.get("depends_on", [])
            if not isinstance(graph_dependencies, list) or any(dep not in by_graph for dep in graph_dependencies):
                raise ContractError("parity manifest dependency lacks a Beads linkage")
            parity = verify_parity(shown, status_map[graph_status], [by_graph[dep] for dep in graph_dependencies])
        except ContractError as exc:
            conflicts.append({"bd_issue_id": issue_id, "graph_node_id": expected.get("graph_node_id"), "reason": str(exc)})
            continue
        ready_set.append({
            "bd_issue_id": issue_id,
            "external_ref": expected.get("graph_node_id") or _external_ref(candidate),
            "edge_parity": parity,
            "graph_status": graph_status,
            "graph_depends_on": graph_dependencies,
        })
    return {"ready_set": ready_set, "unmapped": unmapped, "conflicts": conflicts, "candidate_count": len(candidates)}


def _verify_feature_rollup(manifest: dict[str, Any], issue_id: str) -> dict[str, Any]:
    if str(manifest.get("epic_bd_issue_id")) != issue_id:
        raise ContractError("feature rollup epic identity mismatch")
    children = manifest.get("children")
    if not isinstance(children, list) or len(children) != 13 or not all(isinstance(row, dict) for row in children):
        raise ContractError("feature rollup requires exact 13 children")
    phases = [row.get("phase_ref") for row in children]
    if phases != PHASES or any(row.get("status") != "closed" for row in children):
        raise ContractError("feature rollup requires closed P01..P13 exact-set")
    return {"eligible": True, "phase_refs": phases, "closed_count": 13}


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--op", required=True, choices=("create", "update", "dep-add", "close", "ready", "show", "claim", "github-push", "gate-add", "gate-check"))
    p.add_argument("--repo-root", default="."); p.add_argument("--graph-node-id"); p.add_argument("--bd-issue-id"); p.add_argument("--depends-on"); p.add_argument("--expected-depends-on", action="append", default=[]); p.add_argument("--expected-status"); p.add_argument("--expected-workspace-id"); p.add_argument("--verify-parity", action="store_true"); p.add_argument("--title"); p.add_argument("--description"); p.add_argument("--status"); p.add_argument("--reason"); p.add_argument("--pr", type=int); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--parity-manifest"); p.add_argument("--projection-manifest"); p.add_argument("--feature-rollup-manifest"); p.add_argument("--artifact-kind", choices=("feature", "task"))
    a = p.parse_args(); root = Path(a.repo_root).resolve(strict=True)
    pf = preflight(root, a.expected_workspace_id) if a.expected_workspace_id else preflight(root)
    if a.dry_run and a.op in MUTATIONS:
        preview: dict[str, Any] = {k: v for k, v in vars(a).items() if v is not None and k != "dry_run"}
        if a.op == "create" and a.projection_manifest:
            feature, children = _validate_projection(_load_manifest(a.projection_manifest, root, label="projection") or {})
            preview["projection"] = {
                "feature": feature["graph_node_id"],
                "issue_type": "epic",
                "children": [{"graph_node_id": row["graph_node_id"], "phase_ref": row["phase_ref"], "issue_type": "task"} for row in children],
                "dependency_type": "blocks",
                "write_count": 0,
            }
        if a.op == "close" and a.artifact_kind == "feature":
            manifest = _load_manifest(a.feature_rollup_manifest, root, label="feature rollup")
            if not a.bd_issue_id or manifest is None: raise ContractError("feature close dry-run requires issue and rollup manifest")
            preview["feature_rollup"] = _verify_feature_rollup(manifest, a.bd_issue_id)
        dump({"op": a.op, "dry_run_preview": preview, **pf}); return 0
    issue = a.bd_issue_id
    if a.op == "create":
        projection = _load_manifest(a.projection_manifest, root, label="projection")
        if projection:
            result = _package_projection(root, projection)
        else:
            if not a.graph_node_id or not a.title: raise ContractError("create requires --graph-node-id and --title")
            result = _create_one(root, graph_node_id=a.graph_node_id, title=a.title, description=a.description or "", issue_type="epic" if a.artifact_kind == "feature" else "task")
    elif a.op in {"update", "close", "claim", "show"}:
        if not issue: raise ContractError(f"{a.op} requires --bd-issue-id")
        shown = bd(["show", issue, "--json"], cwd=root)
        current = _issue(shown, issue)
        edge_parity = verify_parity(current, a.expected_status, a.expected_depends_on) if a.verify_parity else None
        if a.op == "update":
            argv = ["update", issue];
            if a.status: argv += ["--status", a.status]
            if a.title: argv += ["--title", a.title]
            argv += ["--json"]; result = bd(argv, cwd=root)
        elif a.op == "close":
            rollup = None
            current_type = current.get("issue_type") or current.get("type")
            if a.artifact_kind == "feature" or current_type == "epic":
                manifest = _load_manifest(a.feature_rollup_manifest, root, label="feature rollup")
                if manifest is None: raise ContractError("feature close requires --feature-rollup-manifest")
                rollup = _verify_feature_rollup(manifest, issue)
            result = {"id": issue, "idempotent": True, "status": "closed"} if current.get("status") == "closed" else bd(["close", issue, "--reason", a.reason or "dev-graph completion", "--json"], cwd=root)
            if rollup is not None: result = {"epic": result, "feature_rollup": rollup}
        elif a.op == "claim":
            result = {"id": issue, "idempotent": True, "status": "in_progress"} if current.get("status") == "in_progress" else bd(["update", issue, "--claim", "--json"], cwd=root)
        else: result = current
        if edge_parity is not None: result = {"issue": result, "edge_parity": edge_parity}
    elif a.op == "dep-add":
        if not issue or not a.depends_on: raise ContractError("dep-add requires issue and depends-on")
        existing = _issue(bd(["show", issue, "--json"], cwd=root), issue)
        deps = existing.get("dependencies", [])
        if any((x.get("id") if isinstance(x, dict) else x) == a.depends_on for x in deps): result = {"idempotent": True}
        else: result = bd(["dep", "add", issue, a.depends_on, "--json"], cwd=root)
    elif a.op == "ready":
        manifest = _load_manifest(a.parity_manifest, root, label="parity")
        result = _ready_with_parity(root, bd(["ready", "--json"], cwd=root), manifest)
    elif a.op == "github-push": result = bd(["github", "sync", "--push-only", "--json"], cwd=root)
    elif a.op in {"gate-add", "gate-check"}:
        if not issue or not a.pr: raise ContractError("gate operation requires issue and --pr")
        gates = _rows(bd(["gate", "list", "--all", "--json"], cwd=root, check=False))
        matching = [gate for gate in gates if str(gate.get("await_id") or gate.get("awaitId")) == str(a.pr) and (gate.get("blocks") == issue or gate.get("blocked_issue_id") == issue) and (gate.get("gate_type") or gate.get("type")) == "gh:pr"]
        if len(matching) > 1: raise ContractError("duplicate gh:pr gates for issue and PR")
        if a.op == "gate-add":
            result = {"gate": matching[0], "idempotent": True} if matching else bd(["gate", "create", "--type", "gh:pr", "--blocks", issue, "--await-id", str(a.pr), "--reason", a.reason or f"PR #{a.pr} merge", "--json"], cwd=root)
        else:
            if not matching: raise ContractError("gh:pr gate does not exist")
            checked = bd(["gate", "check", "--type", "gh:pr", "--json"], cwd=root)
            result = {"gate": matching[0], "checked": checked}
    payload = {"op": a.op, "result": result, "workspace_identity": pf["workspace_identity"], "bd_version": pf["version"]}
    if a.op == "ready" and isinstance(result, dict):
        payload.update({key: result[key] for key in ("ready_set", "unmapped", "conflicts", "candidate_count")})
    dump(payload)
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ContractError as exc: print(str(exc), file=sys.stderr); raise SystemExit(1)
