#!/usr/bin/env python3
# /// script
# name: diff-github-project-fields
# purpose: Plan the C03 3-way reconciliation of Projects v2 field values against github_project_linkages[].field_snapshot without writing anything.
# inputs: ["argv: --repo-root PATH [--config PATH] [--graph PATH] [--remote FILE] [--decisions FILE] [--issue-plan FILE] [--output PATH]"]
# outputs: ["stdout: JSON plan with exports (gh-bridge argv), imports (C02 update input), held imports, manual conflicts and link_input (C02 link-github input)"]
# requires-python = ">=3.10"
# dependencies: [_common.py, gh-bridge.py]
# contexts: [A, B, C, E]
# network: true
# write-scope: the explicitly selected --output report only; the graph belongs to C02 and remote writes to gh-bridge
# ///
"""C03 Projects field planner.

For every linked item and every field_mappings entry it compares the local value L (projected through
option_map), the remote value R and the last-synced base B = field_snapshot[local_field]:

* L == R: unchanged; B is (re)recorded when it differs.
* local_to_project: L wins (export).
* bidirectional: only L changed -> export, only R changed -> import, both changed (or no base) -> manual
  conflict with no write at all. A ``--decisions`` entry bound to the same (B, L, R) turns one conflict
  into an export or import; a decision made against other values is reported stale and ignored.
* exact-13 package members (parent_feature / feature_package_id / phase_ref) belong to system-dev-planner,
  and C02 update refuses them, so every mapping is local_to_project for them: nothing is imported.

An export carries the gh-bridge ``project-item-edit`` flags in ``value_args``: the option or iteration id found by
name / title, the text, number or date itself, or ``--clear`` when the local value is empty. Only a value the field
cannot hold (a name missing from its options or iterations) stays an ``unsupported-export`` conflict whose
``cause`` keeps the classification that wanted the export. A manual cause (no-base / both-changed) resolves with a
decision choosing remote (an import); a local-only or local-authority cause has no decision to take, so it
resolves only when both sides are aligned by hand (L == R).

The snapshot only ever records values seen equal on both sides, so it is written (link_input) only in a
round that plans no export and no import: apply those, plan again, then link. The round after that has
changes = 0. The remote is read with gh-bridge (read-only) unless ``--remote`` supplies the same shape.

An import is a C02 update, which moves the node's updated_at, and the Issue planner (diff-github-issues.py) settles
title / state by that updated_at. So an import into a node linked to an Issue waits in ``held`` until the Issue side
is settled: ``--issue-plan`` takes the Issue plan made against this same graph_revision (apply it and plan the
Issues again first), and a node still carrying any row there (a difference, a confirmation flag, a conflict or an
unread Issue) keeps its imports held. Without ``--issue-plan`` every such import is held. Exports never touch the node.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, atomic_json, contained, dump, load_json, run, utc_now

BRIDGE = Path(__file__).resolve().parent / "gh-bridge.py"
UNLINKED_STATES = {"unlinked", "pending_retry", "detached"}
PACKAGE_KEYS = ("parent_feature", "feature_package_id", "phase_ref")  # same keys as build-graph-node.PACKAGE_KEYS
ITEM_QUERY = ("query($id:ID!){node(id:$id){... on ProjectV2Item{id fieldValues(first:100){nodes{"
              "... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}} "
              "... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}} "
              "... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{name}}} "
              "... on ProjectV2ItemFieldDateValue{date field{... on ProjectV2FieldCommon{name}}} "
              "... on ProjectV2ItemFieldIterationValue{title field{... on ProjectV2FieldCommon{name}}}}}}}}")
ABSENT = object()  # a field_snapshot key never observed, as opposed to an observed empty value (null)
ISSUE_ROWS = ("exports", "imports", "confirmations", "conflicts", "missing_issues")  # unsettled rows of an Issue plan


def _path(root: Path, value: str, *, must_exist: bool = True) -> Path:
    candidate = Path(value)
    return contained(candidate if candidate.is_absolute() else root / candidate, root, must_exist=must_exist)


def _same(left: Any, right: Any) -> bool:
    numbers = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (left, right))
    return float(left) == float(right) if numbers else left == right


def to_project(mapping: dict[str, Any], value: Any) -> tuple[Any, str | None]:
    """The local value in the project's representation (an option name for single_select)."""
    if value is None:
        return None, None
    if mapping["value_type"] == "single_select":
        name = mapping["option_map"].get(str(value))
        return (name, None) if name is not None else (None, "unmapped_local_value")
    if mapping["value_type"] == "number":
        try:
            return float(value), None
        except (TypeError, ValueError):
            return None, "unmapped_local_value"
    if mapping["value_type"] == "date":
        try:
            datetime.date.fromisoformat(str(value))
        except ValueError:
            return None, "unmapped_local_value"
    return value, None


def edit_value(mapping: dict[str, Any], field: dict[str, Any], value: Any) -> list[str] | None:
    """gh-bridge project-item-edit flags writing ``value`` (None clears); None when the field cannot hold it.

    Each value is one ``--flag=value`` token, so a text beginning with '-' is never read as another flag."""
    if value is None:
        return ["--clear"]
    kind = mapping["value_type"]
    if kind in {"single_select", "iteration"}:
        configuration = field.get("configuration") or {}
        choices, key, flag = ((field.get("options") or [], "name", "--option-id") if kind == "single_select" else
                              ([*(configuration.get("iterations") or []), *(configuration.get("completedIterations") or [])],
                               "title", "--iteration-id"))
        ids = [choice["id"] for choice in choices if choice.get(key) == value]
        return [f"{flag}={ids[0]}"] if len(ids) == 1 else None
    if kind == "number":
        return [f"--number-value={float(value)!r}"]
    return [f"--{kind}={value}"]  # text / date


def to_local(mapping: dict[str, Any], value: Any) -> tuple[Any, str | None]:
    if value is None:
        return None, None
    if mapping["value_type"] == "single_select":
        keys = [key for key, name in mapping["option_map"].items() if name == value]
        return (keys[0], None) if len(keys) == 1 else (None, "unmapped_remote_value")
    if mapping["value_type"] == "number":
        return (str(int(value)) if float(value).is_integer() else str(value)), None
    return value, None


def fetch_remote(targets: dict[str, tuple[dict[str, Any], set[str]]]) -> dict[str, Any]:
    """Read each project's fields and each linked item's field values through gh-bridge (no mutation)."""
    spec = importlib.util.spec_from_file_location("dev_graph_gh_bridge", BRIDGE)
    assert spec and spec.loader
    gh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gh)
    remote: dict[str, Any] = {}
    for alias, (config, item_ids) in sorted(targets.items()):
        cp = run([sys.executable, str(BRIDGE), "--op", "project-resolve", "--owner", config["owner_login"],
                  "--project-number", str(config["project_number"])], check=False)
        if cp.returncode:
            raise ContractError(f"project-resolve {alias} failed: {(cp.stderr or cp.stdout).strip()}")
        project = json.loads(cp.stdout)["result"]
        items = {}
        for item_id in sorted(item_ids):
            node = (gh.graphql(ITEM_QUERY, {"id": item_id}).get("data") or {}).get("node")
            if node is None:
                continue  # deleted from the project: reported as a missing item
            values = {}
            for value in node["fieldValues"]["nodes"]:
                name = (value.get("field") or {}).get("name")
                if name:
                    values[name] = next((value[k] for k in ("name", "text", "number", "date", "title") if k in value), None)
            items[item_id] = values
        remote[alias] = {"id": project.get("id"), "fields": project.get("fields") or {"nodes": []}, "items": items}
    return {"projects": remote}


def _decisions(path: Path | None) -> dict[tuple[str, str, str], dict[str, Any]]:
    if path is None:
        return {}
    rows = load_json(path).get("decisions")
    if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get("choose") in {"local", "remote"} for row in rows):
        raise ContractError("decisions must be {decisions:[{graph_node_id, project_alias, local_field, choose: local|remote, base?, local, remote}]}")
    return {(row.get("graph_node_id"), row.get("project_alias"), row.get("local_field")): row for row in rows}


def _bound(decision: dict[str, Any], base: Any, local: Any, remote: Any) -> bool:
    """A decision applies only to the very values the user saw; any later change makes it stale."""
    if ("base" in decision) != (base is not ABSENT):
        return False
    return (base is ABSENT or _same(decision["base"], base)) and _same(decision.get("local"), local) \
        and _same(decision.get("remote"), remote)


def plan(graph: dict[str, Any], github: dict[str, Any], remote: dict[str, Any],
         decisions: dict[tuple[str, str, str], dict[str, Any]], now: str,
         issue_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    projects = {project["alias"]: project for project in github.get("projects") or []}
    unsettled = None if issue_plan is None else {
        row.get("graph_node_id") for key in ISSUE_ROWS for row in issue_plan.get(key) or []}
    exports: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    missing_items: list[dict[str, Any]] = []
    used: set[tuple[str, str, str]] = set()
    stale: list[dict[str, Any]] = []
    candidates: list[tuple[str, dict[str, Any], dict[str, Any], bool]] = []
    for node in sorted(graph.get("nodes") or [], key=lambda n: str(n.get("graph_node_id"))):
        node_id = node.get("graph_node_id")
        if node.get("tracker_binding") != "github":
            continue
        package_member = any(node.get(key) is not None for key in PACKAGE_KEYS)
        issue_linked = isinstance((node.get("issue_linkage") or {}).get("issue_number"), int)
        hold = (None if not issue_linked else "issue-plan-missing" if unsettled is None
                else "issue-unsettled" if node_id in unsettled else None)
        for link in node.get("github_project_linkages") or []:
            alias, item_id = link.get("project_alias"), link.get("item_id")
            config = projects.get(alias)
            if config is None:
                skipped.append({"graph_node_id": node_id, "project_alias": alias, "reason": "alias not in github.projects"})
                continue
            if not item_id or link.get("sync_state") in UNLINKED_STATES:
                skipped.append({"graph_node_id": node_id, "project_alias": alias,
                                "reason": f"sync_state={link.get('sync_state')}: C14 retry owns it"})
                continue
            project = (remote.get("projects") or {}).get(alias) or {}
            item = (project.get("items") or {}).get(item_id)
            if item is None:
                missing_items.append({"graph_node_id": node_id, "project_alias": alias, "item_id": item_id})
                continue
            fields = {str(f.get("name", "")).casefold(): f for f in (project.get("fields") or {}).get("nodes", [])}
            values = {str(name).casefold(): value for name, value in item.items()}
            snapshot = link.get("field_snapshot") or {}
            observed: dict[str, Any] = {}
            in_conflict = waiting = False
            for mapping in config.get("field_mappings") or []:
                local_field, name = mapping["local_field"], mapping["project_field_name"]
                direction = "local_to_project" if package_member else mapping["direction"]
                row = {"graph_node_id": node_id, "project_alias": alias, "item_id": item_id,
                       "local_field": local_field, "project_field_name": name, "direction": direction}
                field = fields.get(name.casefold())
                if field is None:
                    conflicts.append({**row, "kind": "remote-field-missing"})
                    in_conflict = True
                    continue
                local, error = to_project(mapping, node.get(local_field))
                if error:
                    conflicts.append({**row, "kind": error, "local": node.get(local_field)})
                    in_conflict = True
                    continue
                remote_value = values.get(name.casefold())
                base = snapshot.get(local_field, ABSENT)
                if _same(local, remote_value):
                    if base is ABSENT or not _same(base, local):
                        observed[local_field] = local
                    continue
                if direction == "local_to_project":
                    action, kind = "export", "local-authority"
                elif base is ABSENT:
                    action, kind = "manual", "no-base"
                elif not _same(local, base) and _same(remote_value, base):
                    action, kind = "export", "local-only"
                elif _same(local, base) and not _same(remote_value, base):
                    action, kind = "import", "remote-only"
                else:
                    action, kind = "manual", "both-changed"
                seen = {"local": local, "remote": remote_value, **({} if base is ABSENT else {"base": base})}
                key = (node_id, alias, local_field)
                if action == "manual" and key in decisions:
                    if _bound(decisions[key], base, local, remote_value):
                        used.add(key)
                        action, kind = ("export" if decisions[key]["choose"] == "local" else "import"), f"decided-{kind}"
                    else:
                        stale.append({**row, **seen, "decision": decisions[key]})
                if action == "export":
                    value_args = edit_value(mapping, field, local)
                    if value_args is None:
                        # the field has no option / iteration of that name: adding one is a human's call
                        conflicts.append({**row, **seen, "kind": "unsupported-export", "cause": kind})
                        in_conflict = True
                        continue
                    exports.append({**row, **seen, "kind": kind, "field_id": field["id"], "value_args": value_args,
                                    "bridge_args": ["--op", "project-item-edit", "--project-id", str(project.get("id")),
                                                    "--item-id", item_id, "--field-id", field["id"], *value_args]})
                elif action == "import":
                    value, error = to_local(mapping, remote_value)
                    if error:
                        conflicts.append({**row, **seen, "kind": error})
                        in_conflict = True
                        continue
                    if hold:
                        held.append({**row, **seen, "kind": kind, "reason": hold})
                        waiting = True
                        continue
                    imports.append({**row, **seen, "kind": kind, "node_patch": {local_field: value}})
                else:
                    conflicts.append({**row, **seen, "kind": kind})
                    in_conflict = True
            if not waiting:  # a link with a held import is recorded only once that import has been applied
                candidates.append((node_id, link, observed, in_conflict))
    revision = graph.get("graph_revision")
    update_input = None
    if imports:
        patches: dict[str, dict[str, Any]] = {}
        for entry in imports:
            patches.setdefault(entry["graph_node_id"], {}).update(entry["node_patch"])
        update_input = {"expected_graph_revision": revision,
                        "updates": [{"graph_node_id": node_id, "node_patch": patch} for node_id, patch in sorted(patches.items())]}
    links: dict[str, list[dict[str, Any]]] = {}
    if not exports and not imports:
        for node_id, link, observed, in_conflict in candidates:
            state = "conflict" if in_conflict else "synced"
            if observed or state != link.get("sync_state"):
                links.setdefault(node_id, []).append({**link, "field_snapshot": observed, "sync_state": state,
                                                      "last_synced_at": now, "last_error_code": None})
    link_input = ({"expected_graph_revision": revision,
                   "links": [{"graph_node_id": node_id, "github_project_linkages": rows} for node_id, rows in sorted(links.items())]}
                  if links else None)
    link_count = sum(len(rows) for rows in links.values())
    unused = [{"graph_node_id": k[0], "project_alias": k[1], "local_field": k[2]} for k in sorted(set(decisions) - used)]
    return {"schema_version": "1.0.0", "graph_revision": revision, "exports": exports, "imports": imports, "held": held,
            "conflicts": conflicts, "stale_decisions": stale, "unused_decisions": unused, "missing_items": missing_items,
            "skipped": skipped, "update_input": update_input, "link_input": link_input,
            "counts": {"exports": len(exports), "imports": len(imports), "held": len(held), "conflicts": len(conflicts),
                       "links": link_count},
            "changes": len(exports) + len(imports) + link_count,
            "next": ("apply exports and imports, then plan again" if exports or imports
                     else "apply link_input" if link_input
                     else "settle the linked Issues (apply the Issue plan or confirm its flags), then plan again with the new --issue-plan"
                     if held else "converged")}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--graph", help="defaults to local_state.graph in --config")
    p.add_argument("--remote", help="JSON {projects:{alias:{id, fields:{nodes:[...]}, items:{item_id:{field name: value}}}}} instead of gh")
    p.add_argument("--decisions", help="JSON {decisions:[...]} bound to the base/local/remote values of a reported conflict")
    p.add_argument("--issue-plan", help="diff-github-issues.py plan made against the same graph_revision; imports wait until its rows settle")
    p.add_argument("--output", help="repo-relative path that also receives the plan")
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
        projects = {project["alias"]: project for project in github.get("projects") or []}
        targets: dict[str, tuple[dict[str, Any], set[str]]] = {}
        for node in graph["nodes"]:
            if node.get("tracker_binding") != "github":
                continue
            for link in node.get("github_project_linkages") or []:
                alias = link.get("project_alias")
                if alias in projects and link.get("item_id") and link.get("sync_state") not in UNLINKED_STATES:
                    targets.setdefault(alias, (projects[alias], set()))[1].add(link["item_id"])
        remote = fetch_remote(targets)
    issue_plan = None
    if a.issue_plan:
        issue_plan = load_json(_path(root, a.issue_plan))
        if issue_plan.get("graph_revision") != graph.get("graph_revision"):
            raise ContractError("--issue-plan was made against another graph_revision: apply it, plan the Issues again, then pass that plan")
    report = plan(graph, github, remote, _decisions(_path(root, a.decisions) if a.decisions else None), utc_now(), issue_plan)
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
