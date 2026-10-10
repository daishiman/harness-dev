#!/usr/bin/env python3
# /// script
# name: diff-github-issues
# purpose: Plan the C03 reconciliation of linked GitHub Issue title/state by updated_at (newer side wins; the same instant keeps GitHub and flags a manual confirmation) without writing anything.
# inputs: ["argv: --repo-root PATH [--config PATH] [--graph PATH] [--remote FILE] [--decisions FILE] [--output PATH]"]
# outputs: ["stdout: JSON plan with exports (gh-bridge argv), imports (C02 update input), confirmations (manual confirmation flags) and conflicts"]
# requires-python = ">=3.10"
# dependencies: [_common.py, gh-bridge.py]
# contexts: [A, B, C, E]
# network: true
# write-scope: the explicitly selected --output report only; the graph belongs to C02 and remote writes to gh-bridge
# ///
"""C03 Issue planner.

For every node with tracker_binding=github and an issue_linkage it compares the local title and state (status
done / closed / tombstoned reads "closed", any other "open") with the Issue, and settles a difference by
updated_at (the node's updated_at against the Issue's updatedAt):

* the node is newer: export through gh-bridge (issue-update for the title, issue-close for the state);
* the Issue is newer: import through C02 update (the title, or status=closed);
* the same instant: nothing is written. GitHub's value is the one shown (``adopted: remote``) and the row stays a
  ``confirmations`` flag until a ``--decisions`` entry bound to the same local / remote / updated_at values chooses
  a side; a decision made against other values is reported stale and ignored. The flag is derived from what is
  observed, so it lasts exactly until the chosen side is applied: the next plan then sees both sides agree.

Any other C02 update moves the node's updated_at and would tip this comparison, so this plan goes first: apply it,
plan again, and pass that plan to diff-github-project-fields.py --issue-plan, which holds its imports into every node
still carrying a row here.

gh-bridge has no reopen and a closed node is not reopened from GitHub unasked, so a reopen either way stays a
conflict. exact-13 package members belong to system-dev-planner (C02 update refuses them), so their local side
always wins. A missing or unreadable timestamp is a conflict, never a guess. The remote is read with gh-bridge
issue-fetch (read-only) unless ``--remote`` supplies {issues: {"OWNER/REPO#N": {title, state, updated_at}}}.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, atomic_json, contained, dump, is_package_member, load_json, run

BRIDGE = Path(__file__).resolve().parent / "gh-bridge.py"
CLOSED = {"done", "closed", "tombstoned"}
BOUND_KEYS = ("local", "remote", "local_updated_at", "remote_updated_at")


def _path(root: Path, value: str, *, must_exist: bool = True) -> Path:
    candidate = Path(value)
    return contained(candidate if candidate.is_absolute() else root / candidate, root, must_exist=must_exist)


def _instant(value: Any) -> datetime.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def linked_issues(graph: dict[str, Any], github: dict[str, Any]) -> list[tuple[dict[str, Any], str, int]]:
    rows = []
    for node in sorted(graph.get("nodes") or [], key=lambda n: str(n.get("graph_node_id"))):
        linkage = node.get("issue_linkage")
        if node.get("tracker_binding") == "github" and isinstance(linkage, dict) and isinstance(linkage.get("issue_number"), int):
            rows.append((node, str(linkage.get("repo") or github.get("issue_repository") or ""), linkage["issue_number"]))
    return rows


def fetch_remote(targets: list[tuple[str, int]]) -> dict[str, Any]:
    """Read each linked Issue through gh-bridge issue-fetch (no mutation); a failed read is kept as its error."""
    issues: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for repo, number in sorted(set(targets)):
        cp = run([sys.executable, str(BRIDGE), "--op", "issue-fetch", "--repo", repo, "--number", str(number)], check=False)
        if cp.returncode:
            errors[f"{repo}#{number}"] = (cp.stderr or cp.stdout).strip()
        else:
            issues[f"{repo}#{number}"] = json.loads(cp.stdout)["result"]
    return {"issues": issues, "errors": errors}


def _decisions(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    rows = load_json(path).get("decisions")
    if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get("choose") in {"local", "remote"} for row in rows):
        raise ContractError("decisions must be {decisions:[{graph_node_id, field, choose: local|remote, local, remote, local_updated_at, remote_updated_at}]}")
    return {(row.get("graph_node_id"), row.get("field")): row for row in rows}


def plan(graph: dict[str, Any], github: dict[str, Any], remote: dict[str, Any],
         decisions: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    issues, errors = remote.get("issues") or {}, remote.get("errors") or {}
    exports: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    confirmations: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()
    for node, repo, number in linked_issues(graph, github):
        node_id = node.get("graph_node_id")
        issue = issues.get(f"{repo}#{number}")
        if issue is None:
            missing.append({"graph_node_id": node_id, "repo": repo, "issue_number": number, "error": errors.get(f"{repo}#{number}")})
            continue
        package_member = is_package_member(node)
        local_at, remote_at = _instant(node.get("updated_at")), _instant(issue.get("updated_at"))
        local_state = "closed" if node.get("status") in CLOSED else "open"
        for field, local, remote_value in (("title", node.get("title"), issue.get("title")),
                                           ("state", local_state, str(issue.get("state") or "").lower())):
            if local == remote_value:
                continue
            row = {"graph_node_id": node_id, "repo": repo, "issue_number": number, "field": field, "local": local,
                   "remote": remote_value, "local_updated_at": node.get("updated_at"), "remote_updated_at": issue.get("updated_at")}
            if package_member:
                side, kind = "local", "local-authority"
            elif local_at is None or remote_at is None:
                conflicts.append({**row, "kind": "no-updated-at"})
                continue
            elif local_at != remote_at:
                side, kind = ("local", "local-newer") if local_at > remote_at else ("remote", "remote-newer")
            else:
                decision = decisions.get((node_id, field))
                if decision is None or any(decision.get(key) != row[key] for key in BOUND_KEYS):
                    if decision is not None:
                        stale.append({**row, "decision": decision})
                    confirmations.append({**row, "kind": "same-time", "adopted": "remote", "display_value": remote_value})
                    continue
                used.add((node_id, field))
                side, kind = decision["choose"], "decided-same-time"
            if side == "local":
                if field == "title":
                    args = ["--op", "issue-update", "--repo", repo, "--number", str(number), f"--title={local}"]
                elif local == "closed":
                    args = ["--op", "issue-close", "--repo", repo, "--number", str(number)]
                else:
                    conflicts.append({**row, "kind": "unsupported-export", "cause": kind})  # gh-bridge cannot reopen
                    continue
                exports.append({**row, "kind": kind, "bridge_args": args})
            elif field == "title" or remote_value == "closed":
                imports.append({**row, "kind": kind, "node_patch": {"title": remote_value} if field == "title" else {"status": "closed"}})
            else:
                conflicts.append({**row, "kind": "remote-reopen", "cause": kind})  # a closed node is reopened by a human
    revision = graph.get("graph_revision")
    patches: dict[str, dict[str, Any]] = {}
    for entry in imports:
        patches.setdefault(entry["graph_node_id"], {}).update(entry["node_patch"])
    update_input = ({"expected_graph_revision": revision,
                     "updates": [{"graph_node_id": node_id, "node_patch": patch} for node_id, patch in sorted(patches.items())]}
                    if patches else None)
    unused = [{"graph_node_id": key[0], "field": key[1]} for key in sorted(set(decisions) - used)]
    changes = len(exports) + len(imports)
    unresolved = len(confirmations) + len(conflicts) + len(missing)
    return {"schema_version": "1.0.0", "graph_revision": revision, "exports": exports, "imports": imports,
            "confirmations": confirmations, "conflicts": conflicts, "stale_decisions": stale, "unused_decisions": unused,
            "missing_issues": missing, "update_input": update_input,
            "counts": {"exports": len(exports), "imports": len(imports), "confirmations": len(confirmations),
                       "conflicts": len(conflicts), "missing_issues": len(missing)},
            "changes": changes, "unresolved_count": unresolved, "converged": changes == 0 and unresolved == 0,
            "next": ("apply exports and imports, then plan again" if exports or imports
                     else "retry missing Issues, then plan again" if missing
                     else "resolve the reported conflicts (R6), then plan again" if conflicts
                     else "confirm each flagged row (R6), then plan again with --decisions" if confirmations else "converged")}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--graph", help="defaults to local_state.graph in --config")
    p.add_argument("--remote", help='JSON {issues:{"OWNER/REPO#N":{title, state, updated_at}}, errors?:{...}} instead of gh')
    p.add_argument("--decisions", help="JSON {decisions:[...]} bound to the local/remote/updated_at values of a flagged row")
    p.add_argument("--output", help="repo-relative path that also receives the plan (the flags R6 reads)")
    a = p.parse_args(argv)
    root = Path(a.repo_root).resolve(strict=True)
    config = load_json(_path(root, a.config))
    github = config.get("github") or {}
    graph_ref = a.graph or (config.get("local_state") or {}).get("graph")
    if not graph_ref:
        raise ContractError("repo config omits local_state.graph")
    graph = load_json(_path(root, graph_ref))
    if not isinstance(graph.get("nodes"), list):
        raise ContractError("graph nodes must be an array")
    if a.remote:
        remote = load_json(_path(root, a.remote))
    else:
        remote = fetch_remote([(repo, number) for _, repo, number in linked_issues(graph, github)])
    report = plan(graph, github, remote, _decisions(_path(root, a.decisions) if a.decisions else None))
    if a.output:
        atomic_json(_path(root, a.output, must_exist=False), report)
    dump(report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
