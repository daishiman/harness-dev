#!/usr/bin/env python3
# /// script
# name: gh-bridge
# purpose: Provide a deterministic, dry-run-safe bridge to approved gh Issue, Projects v2 and lifecycle fact operations.
# inputs: ["argv: --op OP --repo OWNER/REPO and operation fields; optional offline --adapter-fixture for project-item-fields"]
# outputs: ["stdout: normalized issue/project/item/field snapshot JSON or mutation preview"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: true
# write-scope: approved gh CLI mutations only
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, dump, run

MUTATIONS = {"issue-create", "issue-update", "issue-close", "project-item-add", "project-item-edit"}
ISSUE_FIELDS = "id,number,title,state,url,updatedAt"


def retry_classification(op: str) -> str:
    """Describe how a caller may repeat an operation after an uncertain result."""
    if op in {"issue-fetch", "lifecycle-facts", "project-resolve", "project-item-find", "project-item-fields"}:
        return "safe_read"
    if op in {"issue-create", "project-item-add"}:
        return "verify_before_retry"
    return "idempotent_with_same_arguments"


def normalize_issue(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("gh issue result must be an object")
    missing = [key for key in ("id", "number", "url") if value.get(key) is None]
    if missing:
        raise ContractError(f"gh issue result missing fields: {', '.join(missing)}")
    return {
        "id": value["id"],
        "number": value["number"],
        "title": value.get("title", ""),
        "state": str(value.get("state", "")).lower(),
        "url": value["url"],
        "updated_at": value.get("updatedAt"),
    }


def gh_json(argv: list[str]) -> Any:
    cp = run([os.environ.get("DEV_GRAPH_GH", "gh"), *argv])
    try: return json.loads(cp.stdout)
    except json.JSONDecodeError as exc: raise ContractError(f"gh returned invalid JSON: {exc}") from exc


def gh_text(argv: list[str]) -> str:
    return run([os.environ.get("DEV_GRAPH_GH", "gh"), *argv]).stdout.strip()


def graphql(query: str, variables: dict[str, Any]) -> Any:
    argv = ["api", "graphql", "-f", f"query={query}"]
    for key, value in sorted(variables.items()):
        # gh -F coerces numeric-looking text; GraphQL String/Date/ID variables
        # must stay verbatim while Python numeric values intentionally use -F.
        argv += ["-f" if isinstance(value, str) else "-F", f"{key}={value}"]
    return gh_json(argv)


def _project_field_mutation(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    """Build one typed Projects v2 field mutation after fail-closed validation."""
    if not all((args.project_id, args.item_id, args.field_id)):
        raise ContractError("project/item/field ids required")
    supplied_values = [args.option_id is not None, args.value is not None, args.iteration_id is not None]
    if args.clear:
        if args.value_type is not None or any(supplied_values):
            raise ContractError("--clear cannot be combined with a field value")
        return (
            "mutation($project:ID!,$item:ID!,$field:ID!){"
            "clearProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field})"
            "{projectV2Item{id}}}",
            {"project": args.project_id, "item": args.item_id, "field": args.field_id},
        )

    value_type = args.value_type or ("single_select" if args.option_id is not None else None)
    if value_type is None:
        raise ContractError("project item edit requires --value-type or --clear")
    required_by_type = {
        "single_select": (args.option_id, "--option-id", "String", "singleSelectOptionId"),
        "text": (args.value, "--value", "String", "text"),
        "number": (args.value, "--value", "Float", "number"),
        "date": (args.value, "--value", "Date", "date"),
        "iteration": (args.iteration_id, "--iteration-id", "String", "iterationId"),
    }
    raw_value, required_flag, graphql_type, input_key = required_by_type[value_type]
    if raw_value is None or raw_value == "":
        raise ContractError(f"{required_flag} required for --value-type {value_type}")
    expected_supplied = {
        "single_select": [True, False, False],
        "text": [False, True, False],
        "number": [False, True, False],
        "date": [False, True, False],
        "iteration": [False, False, True],
    }[value_type]
    if supplied_values != expected_supplied:
        raise ContractError(f"only {required_flag} is allowed for --value-type {value_type}")
    value: Any = raw_value
    if value_type == "number":
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ContractError("--value must be a finite number") from exc
        if not math.isfinite(value):
            raise ContractError("--value must be a finite number")
    elif value_type == "date":
        try:
            from datetime import date

            date.fromisoformat(str(raw_value))
        except ValueError as exc:
            raise ContractError("--value must be an ISO date (YYYY-MM-DD)") from exc
    query = (
        f"mutation($project:ID!,$item:ID!,$field:ID!,$value:{graphql_type}!){{"
        "updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,"
        f"value:{{{input_key}:$value}}}}){{projectV2Item{{id}}}}}}"
    )
    return query, {"project": args.project_id, "item": args.item_id, "field": args.field_id, "value": value}


def _validate_mutation_args(op: str, args: argparse.Namespace) -> None:
    """Validate the same mutation contract for preview and execution."""
    if op == "issue-create" and not args.title:
        raise ContractError("--title required")
    if op in {"issue-update", "issue-close"} and not args.number:
        raise ContractError("--number required")
    if op == "project-item-add" and not all((args.project_id, args.content_id)):
        raise ContractError("--project-id and --content-id required")
    if op == "project-item-edit":
        _project_field_mutation(args)


def _snapshot_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _field_value(
    *,
    field_id: str,
    field_name: str,
    value: Any,
    updated_at: Any,
    options: Any = None,
) -> dict[str, Any]:
    if not field_id or not field_name or not isinstance(updated_at, str) or not updated_at:
        raise ContractError("project field value requires field id, name, and updatedAt")
    normalized: dict[str, Any] = {
        "field_id": field_id,
        "field_name": field_name,
        "updated_at": updated_at,
        "value": value,
        "value_type": "date" if isinstance(value, str) and len(value) == 10 and value[4:5] == "-" else "text",
    }
    if options is not None:
        if not isinstance(options, list):
            raise ContractError(f"project field options are malformed: {field_name}")
        matched = [option for option in options if isinstance(option, dict) and option.get("name") == value]
        if len(matched) != 1 or not matched[0].get("id"):
            raise ContractError(f"project single-select value does not resolve exactly once: {field_name}={value}")
        normalized.update({"value_type": "single_select", "option_id": matched[0]["id"]})
    return normalized


def _project_item_content(value: Any, *, repo: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("GitHub project item content is not an Issue")
    repository = value.get("repository")
    repository_name = repository.get("nameWithOwner") if isinstance(repository, dict) else None
    if not isinstance(repository_name, str) or repository_name.casefold() != repo.casefold():
        raise ContractError("GitHub project item content does not belong to --repo")
    missing = [key for key in ("id", "number", "url") if value.get(key) is None]
    if missing:
        raise ContractError(f"GitHub project item content missing fields: {', '.join(missing)}")
    return {key: value[key] for key in ("id", "number", "url")}


def _project_item_fields_from_fixture(
    fixture_path: str,
    *,
    repo: str,
    project_id: str,
    item_id: str,
) -> dict[str, Any]:
    try:
        path = Path(fixture_path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ContractError("--adapter-fixture must resolve to a file")
        fixture = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"adapter fixture is unreadable or invalid JSON: {exc}") from exc
    if not isinstance(fixture, dict) or fixture.get("network") != "disabled":
        raise ContractError("adapter fixture must declare network=disabled")
    if fixture.get("repo") != repo:
        raise ContractError("adapter fixture repo does not match --repo")
    projects = fixture.get("projects")
    if not isinstance(projects, dict):
        raise ContractError("adapter fixture projects must be an object")
    matches = [project for project in projects.values() if isinstance(project, dict) and project.get("id") == project_id]
    if len(matches) != 1:
        raise ContractError(f"adapter fixture project id must resolve exactly once, got {len(matches)}")
    project = matches[0]
    items = project.get("items")
    if not isinstance(items, list):
        raise ContractError("adapter fixture project items must be an array")
    item_matches = [item for item in items if isinstance(item, dict) and item.get("id") == item_id]
    if len(item_matches) != 1:
        raise ContractError(f"adapter fixture item id must resolve exactly once, got {len(item_matches)}")
    item = item_matches[0]
    issues = fixture.get("issues")
    if not isinstance(issues, dict):
        raise ContractError("adapter fixture issues must be an object")
    issue_matches = [issue for issue in issues.values()
                     if isinstance(issue, dict) and issue.get("id") == item.get("content_id")]
    if len(issue_matches) != 1:
        raise ContractError(f"adapter fixture item content must resolve exactly once, got {len(issue_matches)}")
    issue = issue_matches[0]
    definitions = project.get("fields")
    values = item.get("fields")
    timestamps = item.get("field_updated_at")
    if not isinstance(definitions, list) or not isinstance(values, dict) or not isinstance(timestamps, dict):
        raise ContractError("adapter fixture project field state is malformed")
    by_name: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        if not isinstance(definition, dict) or not definition.get("id") or not definition.get("name"):
            raise ContractError("adapter fixture field definition is malformed")
        key = str(definition["name"]).casefold()
        if key in by_name:
            raise ContractError("adapter fixture project field names are not unique")
        by_name[key] = definition
    fields: list[dict[str, Any]] = []
    for name, value in values.items():
        definition = by_name.get(str(name).casefold())
        if definition is None:
            raise ContractError(f"adapter fixture item references unknown field: {name}")
        fields.append(_field_value(
            field_id=str(definition["id"]),
            field_name=str(definition["name"]),
            value=value,
            updated_at=timestamps.get(name),
            options=definition.get("options") if "options" in definition else None,
        ))
    content = _project_item_content(
        {**issue, "repository": {"nameWithOwner": repo}},
        repo=repo,
    )
    snapshot = {
        "project_id": project_id,
        "item_id": item_id,
        "content": content,
        "fields": sorted(fields, key=lambda row: (row["field_name"].casefold(), row["field_id"])),
    }
    return {
        **snapshot,
        "pages": 1,
        "snapshot_sha256": _snapshot_digest(snapshot),
        "source": {"kind": "adapter_fixture", "fixture_id": fixture.get("fixture_id"), "network": "disabled"},
    }


def _normalize_graphql_field(node: Any) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ContractError("GitHub project field value is malformed")
    field = node.get("field")
    if not isinstance(field, dict) or not field.get("id") or not field.get("name"):
        raise ContractError("GitHub project field identity is unavailable")
    kind = node.get("__typename")
    common = {
        "field_id": field["id"],
        "field_name": field["name"],
        "updated_at": node.get("updatedAt"),
    }
    value_by_kind = {
        "ProjectV2ItemFieldSingleSelectValue": ("single_select", node.get("name")),
        "ProjectV2ItemFieldDateValue": ("date", node.get("date")),
        "ProjectV2ItemFieldTextValue": ("text", node.get("text")),
        "ProjectV2ItemFieldNumberValue": ("number", node.get("number")),
        "ProjectV2ItemFieldIterationValue": ("iteration", node.get("title")),
    }
    if kind not in value_by_kind:
        raise ContractError(f"unsupported GitHub project field value type: {kind}")
    value_type, value = value_by_kind[kind]
    normalized = {**common, "value_type": value_type, "value": value}
    if kind == "ProjectV2ItemFieldSingleSelectValue":
        normalized["option_id"] = node.get("optionId")
    elif kind == "ProjectV2ItemFieldIterationValue":
        normalized["iteration_id"] = node.get("iterationId")
    if not normalized["updated_at"]:
        raise ContractError(f"GitHub project field updatedAt is unavailable: {field['name']}")
    return normalized


def project_item_fields(
    *,
    repo: str,
    project_id: str,
    item_id: str,
    adapter_fixture: str | None = None,
) -> dict[str, Any]:
    """Read one Project item and normalize values for a deterministic 3-way base."""
    if adapter_fixture:
        return _project_item_fields_from_fixture(
            adapter_fixture,
            repo=repo,
            project_id=project_id,
            item_id=item_id,
        )
    query = (
        "query($item:ID!,$cursor:String){node(id:$item){... on ProjectV2Item{id project{id} "
        "content{... on Issue{id number url repository{nameWithOwner}}} "
        "fieldValues(first:100,after:$cursor){nodes{__typename "
        "... on ProjectV2ItemFieldSingleSelectValue{updatedAt name optionId field{... on ProjectV2FieldCommon{id name}}} "
        "... on ProjectV2ItemFieldDateValue{updatedAt date field{... on ProjectV2FieldCommon{id name}}} "
        "... on ProjectV2ItemFieldTextValue{updatedAt text field{... on ProjectV2FieldCommon{id name}}} "
        "... on ProjectV2ItemFieldNumberValue{updatedAt number field{... on ProjectV2FieldCommon{id name}}} "
        "... on ProjectV2ItemFieldIterationValue{updatedAt title iterationId field{... on ProjectV2FieldCommon{id name}}}"
        "} pageInfo{hasNextPage endCursor}}}}}"
    )
    cursor = ""
    pages = 0
    content: dict[str, Any] | None = None
    normalized_fields: list[dict[str, Any]] = []
    while True:
        payload = graphql(query, {"item": item_id, "cursor": cursor})
        item = (payload.get("data") or {}).get("node") if isinstance(payload, dict) else None
        if not isinstance(item, dict) or item.get("id") != item_id:
            raise ContractError("GitHub project item was not found")
        project = item.get("project")
        if not isinstance(project, dict) or project.get("id") != project_id:
            raise ContractError("GitHub project item does not belong to --project-id")
        page_content = _project_item_content(item.get("content"), repo=repo)
        if content is None:
            content = page_content
        elif content != page_content:
            raise ContractError("GitHub project item content changed during pagination")
        field_values = item.get("fieldValues")
        if not isinstance(field_values, dict) or not isinstance(field_values.get("nodes"), list):
            raise ContractError("GitHub project fieldValues are malformed")
        normalized_fields.extend(_normalize_graphql_field(node) for node in field_values["nodes"])
        pages += 1
        page_info = field_values.get("pageInfo")
        if not isinstance(page_info, dict):
            raise ContractError("GitHub project fieldValues pageInfo is malformed")
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            raise ContractError("GitHub project fieldValues pagination cursor is unavailable")
    ids = [row["field_id"] for row in normalized_fields]
    names = [row["field_name"].casefold() for row in normalized_fields]
    if len(ids) != len(set(ids)) or len(names) != len(set(names)):
        raise ContractError("GitHub project item returned duplicate field values")
    snapshot = {
        "project_id": project_id,
        "item_id": item_id,
        "content": content,
        "fields": sorted(normalized_fields, key=lambda row: (row["field_name"].casefold(), row["field_id"])),
    }
    return {
        **snapshot,
        "pages": pages,
        "snapshot_sha256": _snapshot_digest(snapshot),
        "source": {"kind": "github", "repository": repo},
    }


def lifecycle_facts(repo: str, number: int) -> dict[str, Any]:
    """Return the remote default branch and one PR from the same GraphQL snapshot."""
    try:
        owner, name = repo.split("/", 1)
    except ValueError as exc:
        raise ContractError("--repo must be OWNER/REPO") from exc
    if not owner or not name or number < 1:
        raise ContractError("lifecycle facts require OWNER/REPO and a positive PR number")
    query = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){nameWithOwner "
        "defaultBranchRef{name target{oid}} "
        "pullRequest(number:$number){number state merged mergedAt baseRefName headRefName url body "
        "mergeCommit{oid} closingIssuesReferences(first:100){nodes{number repository{nameWithOwner}}}}}}"
    )
    payload = graphql(query, {"owner": owner, "name": name, "number": number})
    repository = (payload.get("data") or {}).get("repository") if isinstance(payload, dict) else None
    if not isinstance(repository, dict):
        raise ContractError("GitHub repository was not found")
    default = repository.get("defaultBranchRef")
    pr = repository.get("pullRequest")
    if not isinstance(default, dict) or not isinstance(default.get("target"), dict):
        raise ContractError("remote defaultBranchRef is unavailable")
    if not isinstance(pr, dict):
        raise ContractError("GitHub pull request was not found")
    closing = (pr.get("closingIssuesReferences") or {}).get("nodes", [])
    if not isinstance(closing, list):
        raise ContractError("closingIssuesReferences is malformed")
    return {
        "repository": repository.get("nameWithOwner"),
        "default_branch": {"name": default.get("name"), "oid": default["target"].get("oid")},
        "pull_request": {
            "number": pr.get("number"),
            "state": str(pr.get("state") or "").upper(),
            "merged": pr.get("merged") is True,
            "mergedAt": pr.get("mergedAt"),
            "mergeCommit": pr.get("mergeCommit"),
            "baseRefName": pr.get("baseRefName"),
            "headRefName": pr.get("headRefName"),
            "url": pr.get("url"),
            "body": pr.get("body") or "",
            "closingIssuesReferences": [
                {
                    "number": item.get("number"),
                    "repository": (item.get("repository") or {}).get("nameWithOwner"),
                }
                for item in closing
                if isinstance(item, dict)
            ],
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--op", required=True, choices=("issue-fetch", "issue-create", "issue-update", "issue-close", "lifecycle-facts", "project-resolve", "project-item-find", "project-item-fields", "project-item-add", "project-item-edit"))
    p.add_argument("--repo"); p.add_argument("--number", type=int); p.add_argument("--title"); p.add_argument("--body")
    p.add_argument("--owner"); p.add_argument("--project-number", type=int); p.add_argument("--content-id"); p.add_argument("--project-id"); p.add_argument("--item-id"); p.add_argument("--field-id"); p.add_argument("--option-id"); p.add_argument("--iteration-id"); p.add_argument("--value-type", choices=("single_select", "text", "number", "date", "iteration")); p.add_argument("--value"); p.add_argument("--clear", action="store_true"); p.add_argument("--adapter-fixture"); p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(); op = a.op
    if a.adapter_fixture and op != "project-item-fields":
        raise ContractError("--adapter-fixture is supported only by read-only project-item-fields")
    if (op.startswith("issue-") or op == "lifecycle-facts") and not a.repo: raise ContractError("--repo required")
    if a.dry_run and op in MUTATIONS:
        _validate_mutation_args(op, a)
        dump({"op": op, "dry_run": True, "mutation_suppressed": True,
              "preview": {k: v for k, v in vars(a).items() if v is not None and k != "dry_run"}}); return 0
    if op == "issue-fetch":
        if not a.number: raise ContractError("--number required")
        result = normalize_issue(gh_json(["issue", "view", str(a.number), "--repo", a.repo, "--json", ISSUE_FIELDS]))
    elif op == "lifecycle-facts":
        if not a.number: raise ContractError("--number required")
        result = lifecycle_facts(a.repo, a.number)
    elif op == "issue-create":
        if not a.title: raise ContractError("--title required")
        created_ref = gh_text(["issue", "create", "--repo", a.repo, "--title", a.title, "--body", a.body or ""])
        created_url = next((line.strip() for line in reversed(created_ref.splitlines()) if "/issues/" in line), "")
        if not created_url:
            raise ContractError("gh issue create did not return a created issue URL")
        result = normalize_issue(gh_json(["issue", "view", created_url, "--repo", a.repo, "--json", ISSUE_FIELDS]))
    elif op in {"issue-update", "issue-close"}:
        if not a.number: raise ContractError("--number required")
        argv = ["issue", "edit" if op == "issue-update" else "close", str(a.number), "--repo", a.repo]
        if op == "issue-update":
            if a.title: argv += ["--title", a.title]
            if a.body is not None: argv += ["--body", a.body]
        run([os.environ.get("DEV_GRAPH_GH", "gh"), *argv]); result = {"number": a.number, "state": "closed" if op == "issue-close" else "updated"}
    elif op == "project-resolve":
        if not a.owner or not a.project_number: raise ContractError("--owner and --project-number required")
        field_selection = (
            "id name fields(first:100){nodes{"
            "... on ProjectV2FieldCommon{id name} "
            "... on ProjectV2SingleSelectField{id name options{id name}} "
            "... on ProjectV2IterationField{id name configuration{"
            "iterations{id title} completedIterations{id title}}}"
            "}}"
        )
        query = (
            "query($login:String!,$number:Int!){"
            f"user(login:$login){{projectV2(number:$number){{{field_selection}}}}} "
            f"organization(login:$login){{projectV2(number:$number){{{field_selection}}}}}"
            "}"
        )
        data = graphql(query, {"login": a.owner, "number": a.project_number}).get("data", {})
        candidates = [x.get("projectV2") for x in (data.get("user") or {}, data.get("organization") or {}) if x.get("projectV2")]
        if len(candidates) != 1: raise ContractError(f"default project must resolve exactly once, got {len(candidates)}")
        project = candidates[0]; names = [x.get("name", "").casefold() for x in project.get("fields", {}).get("nodes", [])]
        if len(names) != len(set(names)): raise ContractError("project field aliases are not unique")
        result = project
    elif op == "project-item-find":
        if not a.project_id or not a.content_id: raise ContractError("--project-id and --content-id required")
        query = "query($id:ID!,$cursor:String){node(id:$id){... on ProjectV2{items(first:100,after:$cursor){nodes{id content{... on Issue{id number url}}} pageInfo{hasNextPage endCursor}}}}}"
        cursor = ""; found = []; pages = 0
        while True:
            page = graphql(query, {"id": a.project_id, "cursor": cursor}); pages += 1
            items = page["data"]["node"]["items"]
            found += [x for x in items["nodes"] if (x.get("content") or {}).get("id") == a.content_id]
            if not items["pageInfo"]["hasNextPage"]: break
            cursor = items["pageInfo"]["endCursor"]
        result = {"items": found, "pages": pages}
    elif op == "project-item-fields":
        if not a.repo or not a.project_id or not a.item_id:
            raise ContractError("--repo, --project-id and --item-id required")
        result = project_item_fields(
            repo=a.repo,
            project_id=a.project_id,
            item_id=a.item_id,
            adapter_fixture=a.adapter_fixture,
        )
    elif op == "project-item-add":
        if not a.project_id or not a.content_id: raise ContractError("--project-id and --content-id required")
        q = "mutation($project:ID!,$content:ID!){addProjectV2ItemById(input:{projectId:$project,contentId:$content}){item{id}}}"
        result = graphql(q, {"project": a.project_id, "content": a.content_id})
    else:
        query, variables = _project_field_mutation(a)
        result = graphql(query, variables)
    dump({"op": op, "dry_run": False, "result": result, "retry_classification": retry_classification(op)})
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ContractError as exc: print(str(exc), file=sys.stderr); raise SystemExit(1)
