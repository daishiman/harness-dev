#!/usr/bin/env python3
# /// script
# name: build-github-projection
# purpose: Project eligible tracker_binding=github tasks onto one marker-identified Issue and their Projects v2 items, leaving failed operations in pending_retry.
# inputs: ["argv: --repo-root PATH [--config PATH] [--graph PATH] [--report PATH] [--retry-from REPORT] [--dry-run]"]
# outputs: ["stdout: JSON publication report with linkage proposals and pending_retry", "file: optional --report copy"]
# requires-python = ">=3.10"
# dependencies: [_common.py, gh-bridge.py]
# contexts: [A, B, C, E]
# network: true
# write-scope: gh mutations through gh-bridge and the explicitly selected report; never the dev graph
# ///
"""C14 binding=github publication.

Every gh call goes through gh-bridge. The Issue identity is the remote body marker
``<!-- dev-graph:<graph_node_id> -->`` and the Project item identity is the Issue content id, so a
rerun finds instead of creating. All reads run before the first mutation: a config or remote
inconsistency stops with no external write. A failed mutation leaves the local task as it is (this
script never writes the graph; C02 is its single writer) and is recorded per node/operation in
pending_retry; ``--retry-from`` repeats only those operations.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, atomic_json, contained, dump, load_json, run, utc_now

BRIDGE = Path(__file__).resolve().parent / "gh-bridge.py"
_SPEC = importlib.util.spec_from_file_location("dev_graph_gh_bridge", BRIDGE)
assert _SPEC and _SPEC.loader
GH = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(GH)

MARKER = re.compile(r"<!-- dev-graph:(\S+) -->")
PUBLISHING = {"issue", "issue_and_projects"}
ISSUE_LIST_LIMIT = 5000
EXIT_PENDING = 3


class BridgeFailure(Exception):
    def __init__(self, op: str, returncode: int, detail: str) -> None:
        super().__init__(f"{op} failed ({returncode}): {detail}")
        self.code = f"gh_bridge_exit_{returncode}"
        self.detail = detail.splitlines()[-1] if detail else ""


def bridge(op: str, **fields: Any) -> Any:
    argv = [sys.executable, str(BRIDGE), "--op", op]
    for key, value in fields.items():
        if value is not None:
            argv += [f"--{key.replace('_', '-')}", str(value)]
    cp = run(argv, check=False)
    if cp.returncode:
        raise BridgeFailure(op, cp.returncode, (cp.stderr or cp.stdout).strip())
    return json.loads(cp.stdout)["result"]


def _path(root: Path, value: str, *, must_exist: bool = True) -> Path:
    candidate = Path(value)
    return contained(candidate if candidate.is_absolute() else root / candidate, root, must_exist=must_exist)


def plan(nodes: list[dict[str, Any]], github: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose github-bound tasks and their Project aliases; a publication authority conflict stops everything."""
    projects = {project["alias"]: project for project in github.get("projects", [])}
    targets: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for node in nodes:
        node_id, binding = node.get("graph_node_id"), node.get("tracker_binding")
        publication = node.get("github_publication") or {}
        mode = publication.get("mode")
        if (binding == "github") != (mode in PUBLISHING):
            raise ContractError(f"{node_id}: binding {binding} with github_publication.mode {mode} "
                                "is a publication authority conflict")
        if binding != "github":
            continue
        gate = (node.get("confirmation_status"), node.get("evaluation_status"),
                (node.get("implementation_readiness") or {}).get("status"))
        if gate != ("confirmed", "pass", "complete"):
            skipped.append({"graph_node_id": node_id, "reason": "not confirmed/pass/readiness complete"})
            continue
        aliases: list[str] = []
        if mode == "issue_and_projects":
            aliases = list(publication.get("project_aliases") or []) or sorted(
                alias for alias, project in projects.items()
                if project.get("default") or node.get("artifact_kind") in project["auto_add"]["artifact_kinds"])
            unknown = [alias for alias in aliases if alias not in projects]
            if unknown:
                raise ContractError(f"{node_id}: project aliases {unknown} are not configured in github.projects")
        targets.append({"node": node, "aliases": aliases})
    return targets, skipped


def initial_fields(config: dict[str, Any], project: dict[str, Any], node: dict[str, Any]) -> list[dict[str, str]]:
    """Resolve the local_to_project single-select values (Status) a new item is initialized with."""
    fields = {str(field.get("name", "")).casefold(): field for field in project.get("fields", {}).get("nodes", [])}
    resolved = []
    for mapping in config.get("field_mappings", []):
        if mapping["direction"] != "local_to_project" or mapping["value_type"] != "single_select":
            continue  # gh-bridge edits single-select values only; the rest stays with C03 sync.
        option_name = mapping["option_map"].get(str(node.get(mapping["local_field"])))
        if option_name is None:
            continue
        field = fields.get(mapping["project_field_name"].casefold()) or {}
        option = next((o for o in field.get("options", []) if o.get("name") == option_name), None)
        if not option:
            raise ContractError(f"project {config['alias']} has no {mapping['project_field_name']} option {option_name}")
        resolved.append({"local_field": mapping["local_field"], "field_id": field["id"],
                         "option_id": option["id"], "option_name": option_name})
    return resolved


def remote_issues(repo: str) -> dict[str, list[dict[str, Any]]]:
    """List every Issue (not the lagging search index) and group them by dev-graph marker."""
    rows = GH.gh_json(["issue", "list", "--repo", repo, "--state", "all", "--limit", str(ISSUE_LIST_LIMIT),
                       "--json", f"{GH.ISSUE_FIELDS},body"])
    if not isinstance(rows, list):
        raise ContractError("gh issue list must return an array")
    if len(rows) >= ISSUE_LIST_LIMIT:
        raise ContractError(f"{repo} has {len(rows)}+ issues; the marker scan cannot prove absence")
    by_marker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for node_id in set(MARKER.findall(str(row.get("body") or ""))):
            by_marker.setdefault(node_id, []).append(GH.normalize_issue(row))
    return by_marker


def issue_body(node: dict[str, Any]) -> str:
    facts = [f"- {key}: `{node[key]}`" for key in ("graph_node_id", "parent_feature", "phase_ref", "file_path") if node.get(key)]
    return "\n".join([str(node.get("title") or node["graph_node_id"]), "", *facts, "", f"<!-- dev-graph:{node['graph_node_id']} -->"])


def linkage(config: dict[str, Any], project_id: str | None, item_id: str | None, state: str,
            snapshot: dict[str, Any], now: str, error: str | None = None) -> dict[str, Any]:
    return {"project_alias": config["alias"], "owner_type": config["owner_type"], "owner_login": config["owner_login"],
            "project_number": config["project_number"], "project_id": project_id, "item_id": item_id,
            "sync_state": state, "field_snapshot": snapshot, "linked_at": now if item_id else None,
            "last_synced_at": now if state == "linked" else None, "last_error_code": error}


def project_one(target: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    node = target["node"]
    node_id = node["graph_node_id"]
    repo, now, dry_run = ctx["repo"], ctx["now"], ctx["dry_run"]

    def mutate(op: str, alias: str | None, **fields: Any) -> Any:
        if dry_run:
            ctx["planned"].append({"operation": op, "graph_node_id": node_id, "project_alias": alias})
            return None
        result = bridge(op, **fields)
        ctx["mutations"].append({"operation": op, "graph_node_id": node_id, "project_alias": alias})
        return result

    def pending(op: str, alias: str | None, exc: BridgeFailure) -> None:
        ctx["pending_retry"].append({"graph_node_id": node_id, "project_alias": alias, "operation": op,
                                     "last_error_code": exc.code, "detail": exc.detail})

    entry: dict[str, Any] = {"graph_node_id": node_id, "issue": None, "projects": []}
    issue = ctx["issues"].get(node_id)
    if issue:
        entry["issue"] = {**issue, "action": "existing"}
    else:
        try:
            issue = mutate("issue-create", None, repo=repo, title=node.get("title") or node_id, body=issue_body(node))
        except BridgeFailure as exc:
            # gh may have created the Issue before failing; the retry finds it by marker instead of creating again.
            pending("issue-create", None, exc)
            entry["linkage_proposal"] = {"issue_linkage": None, "github_project_linkages": [
                linkage(ctx["projects"][a], None, None, "unlinked", {}, now) for a in target["aliases"]]}
            return entry
        entry["issue"] = {**issue, "action": "created"} if issue else {"action": "planned"}
    links = []
    for alias in target["aliases"]:
        config, project = ctx["projects"][alias], ctx["resolved"][alias]
        fields = initial_fields(config, project, node)
        item_id, op = None, "project-item-add"
        try:
            items = bridge("project-item-find", project_id=project["id"], content_id=issue["id"])["items"] if issue else []
            if len(items) > 1:
                raise ContractError(f"{node_id}: {len(items)} items hold one Issue in project {alias}")
            item_id = items[0]["id"] if items else None
            # A found item was initialized when it was added; only a pending edit is repeated on it.
            if item_id and (node_id, alias) not in ctx["force_edit"]:
                entry["projects"].append({"project_alias": alias, "item_id": item_id, "action": "existing"})
                links.append(linkage(config, project["id"], item_id, "linked", {}, now))
                continue
            if not item_id:
                added = mutate(op, alias, project_id=project["id"], content_id=issue["id"] if issue else None)
                item_id = added["data"]["addProjectV2ItemById"]["item"]["id"] if added else None
            op = "project-item-edit"
            for field in fields:
                mutate(op, alias, project_id=project["id"], item_id=item_id, field_id=field["field_id"], option_id=field["option_id"])
        except BridgeFailure as exc:
            pending(op, alias, exc)
            links.append(linkage(config, project["id"], item_id, "pending_retry", {}, now, exc.code))
            entry["projects"].append({"project_alias": alias, "item_id": item_id, "action": "pending_retry"})
            continue
        snapshot = {field["local_field"]: field["option_name"] for field in fields}
        entry["projects"].append({"project_alias": alias, "item_id": item_id, "action": "planned" if dry_run else "added"})
        links.append(linkage(config, project["id"], item_id, "linked", snapshot, now))
    if not dry_run:  # a preview has no ids to link yet.
        entry["linkage_proposal"] = {"issue_linkage": {"issue_number": issue["number"], "repo": repo, "linked_at": now},
                                     "github_project_linkages": links}
    return entry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--graph", help="defaults to local_state.graph in --config")
    p.add_argument("--report", help="repo-relative path that also receives the report (not written on --dry-run)")
    p.add_argument("--retry-from", help="a previous report; only its pending_retry operations run")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    root = Path(a.repo_root).resolve(strict=True)
    config = load_json(_path(root, a.config))
    github = config.get("github") or {}
    graph_ref = a.graph or (config.get("local_state") or {}).get("graph")
    if not graph_ref:
        raise ContractError("repo config omits local_state.graph")
    nodes = load_json(_path(root, graph_ref)).get("nodes")
    if not isinstance(nodes, list):
        raise ContractError("graph nodes must be an array")
    targets, skipped = plan(nodes, github)
    repo = github.get("issue_repository")
    force_edit: set[tuple[str, str]] = set()
    if a.retry_from:
        previous = load_json(_path(root, a.retry_from))
        if previous.get("issue_repository") != repo:
            raise ContractError("retry report belongs to a different issue_repository")
        scope: dict[str, set[str] | None] = {}
        for row in previous.get("pending_retry", []):
            node_id, alias = row["graph_node_id"], row["project_alias"]
            if alias is None:
                scope[node_id] = None  # the Issue itself failed: the whole node runs again.
            elif scope.get(node_id, set()) is not None:
                scope.setdefault(node_id, set()).add(alias)
            if row["operation"] == "project-item-edit":
                force_edit.add((node_id, alias))
        kept = {t["node"]["graph_node_id"] for t in targets} & scope.keys()
        skipped += [{"graph_node_id": n, "reason": "pending node is no longer an eligible github task"} for n in sorted(scope.keys() - kept)]
        targets = [{**t, "aliases": [x for x in t["aliases"] if scope[t["node"]["graph_node_id"]] is None
                                     or x in scope[t["node"]["graph_node_id"]]]}
                   for t in targets if t["node"]["graph_node_id"] in kept]
    ctx: dict[str, Any] = {"repo": repo, "now": utc_now(), "dry_run": a.dry_run, "force_edit": force_edit,
                           "projects": {x["alias"]: x for x in github.get("projects", [])},
                           "resolved": {}, "issues": {}, "mutations": [], "planned": [], "pending_retry": []}
    if targets:
        if github.get("enabled") is not True or not isinstance(repo, str) or "/" not in repo:
            raise ContractError("binding=github tasks need github.enabled=true and github.issue_repository OWNER/REPO")
        by_marker = remote_issues(repo)
        for target in targets:
            node = target["node"]
            found = by_marker.get(node["graph_node_id"], [])
            if len(found) > 1:
                raise ContractError(f"{node['graph_node_id']}: {len(found)} Issues carry the same dev-graph marker")
            linked = node.get("issue_linkage")
            if linked and (linked.get("repo") != repo or (found and found[0]["number"] != linked.get("issue_number"))):
                raise ContractError(f"{node['graph_node_id']}: issue_linkage disagrees with the marked Issue")
            if not found and linked:  # linked before markers existed: trust the linkage, never create a second Issue.
                found = [bridge("issue-fetch", repo=repo, number=linked["issue_number"])]
            if found:
                ctx["issues"][node["graph_node_id"]] = found[0]
        for alias in sorted({alias for target in targets for alias in target["aliases"]}):
            project = ctx["projects"][alias]
            ctx["resolved"][alias] = bridge("project-resolve", owner=project["owner_login"], project_number=project["project_number"])
        for target in targets:
            for alias in target["aliases"]:
                initial_fields(ctx["projects"][alias], ctx["resolved"][alias], target["node"])
    projected = [project_one(target, ctx) for target in targets]
    report = {"schema_version": "1.0.0", "dry_run": a.dry_run, "issue_repository": repo, "retry_from": a.retry_from,
              "projected": projected, "skipped": skipped, "mutations": ctx["mutations"],
              "planned_mutations": ctx["planned"], "pending_retry": ctx["pending_retry"],
              "mutation_count": len(ctx["mutations"]), "graph_written": False}
    if a.report and not a.dry_run:
        atomic_json(_path(root, a.report, must_exist=False), report)
    dump(report)
    return EXIT_PENDING if ctx["pending_retry"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, BridgeFailure) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
