#!/usr/bin/env python3
"""Offline `gh` stand-in for the r5-sync live-trial fixture.

All reads and writes are closed inside the fixture directory: remote state lives in
`github-adapter.json` and every call is appended to `github-adapter-calls.jsonl`.
No network access exists in this process by construction.

pr85 sync2 additions (orchestrator, before the trial session): the Projects item field-value read
(`node(id:$id){... on ProjectV2Item{id fieldValues(first:100){...}}}`, the ITEM_QUERY of
diff-github-project-fields.py) and the `clearProjectV2ItemFieldValue` mutation, both answered from the
adapter state like the existing ops.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent.parent
ADAPTER = FIXTURE_ROOT / "github-adapter.json"
CALL_LOG = FIXTURE_ROOT / "github-adapter-calls.jsonl"


def fail(message: str) -> None:
    print(f"fake-gh: {message}", file=sys.stderr)
    raise SystemExit(1)


def load() -> dict:
    return json.loads(ADAPTER.read_text(encoding="utf-8"))


def save(state: dict) -> None:
    ADAPTER.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def log_call(op: str, detail: dict, mutation: bool) -> None:
    with CALL_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"op": op, "mutation": mutation, "detail": detail},
                                ensure_ascii=False, sort_keys=True) + "\n")


def option_value(state: dict, alias: str, field_id: str, option_id: str) -> tuple[str, str]:
    for field in state["projects"][alias]["fields"]:
        if field["id"] == field_id:
            for option in field.get("options", []):
                if option["id"] == option_id:
                    return field["name"], option["name"]
            fail(f"unknown option {option_id} for field {field_id}")
    fail(f"unknown field {field_id}")
    raise AssertionError


def field_value(field: dict, name: str, value) -> dict:
    """One fieldValues node in the GraphQL shape: the value key follows the field kind of the adapter."""
    if "options" in field:
        key = "name"  # ProjectV2ItemFieldSingleSelectValue
    elif "configuration" in field:
        key = "title"  # ProjectV2ItemFieldIterationValue
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        key = "number"
    elif isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        key = "date"  # the adapter has no dataType; a YYYY-MM-DD value is a date field (Target date)
    else:
        key = "text"
    return {key: value, "field": {"name": name}}


def flag(argv: list[str], name: str) -> str | None:
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    return None


def issue_by_number(state: dict, ref: str) -> dict:
    number = ref.rsplit("/", 1)[-1]
    issue = state["issues"].get(str(number))
    if issue is None:
        fail(f"issue not found in fixture: {ref}")
    return issue


def handle_issue(state: dict, argv: list[str]) -> None:
    action = argv[1]
    repo = flag(argv, "--repo")
    if repo != state["repo"]:
        fail(f"refusing to touch a repository outside the fixture: {repo}")
    if action == "view":
        issue = issue_by_number(state, argv[2])
        log_call("issue-view", {"number": issue["number"]}, False)
        print(json.dumps({key: issue[key] for key in ("id", "number", "title", "state", "url", "updatedAt")},
                         ensure_ascii=False))
        return
    if action == "edit":
        issue = issue_by_number(state, argv[2])
        title, body = flag(argv, "--title"), flag(argv, "--body")
        changed = {}
        if title is not None and title != issue["title"]:
            changed["title"] = {"from": issue["title"], "to": title}
            issue["title"] = title
        if body is not None and body != issue["body"]:
            changed["body"] = {"changed": True}
            issue["body"] = body
        if changed:
            issue["updatedAt"] = state["clock"]["issue_update_updated_at"]
            state["mutation_log"].append({"op": "issue-edit", "number": issue["number"], "changed": changed,
                                          "updatedAt": issue["updatedAt"]})
            save(state)
        log_call("issue-edit", {"number": issue["number"], "changed": bool(changed)}, True)
        print(issue["url"])
        return
    if action == "close":
        issue = issue_by_number(state, argv[2])
        if issue["state"] != "CLOSED":
            issue["state"] = "CLOSED"
            issue["updatedAt"] = state["clock"]["issue_update_updated_at"]
            state["mutation_log"].append({"op": "issue-close", "number": issue["number"],
                                          "updatedAt": issue["updatedAt"]})
            save(state)
        log_call("issue-close", {"number": issue["number"]}, True)
        print(issue["url"])
        return
    fail(f"unsupported issue action: {action}")


def handle_graphql(state: dict, argv: list[str]) -> None:
    query = ""
    variables: dict[str, str] = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "-f" and index + 1 < len(argv):
            raw = argv[index + 1]
            if raw.startswith("query="):
                query = raw[len("query="):]
            index += 2
            continue
        if token == "-F" and index + 1 < len(argv):
            key, _, value = argv[index + 1].partition("=")
            variables[key] = value
            index += 2
            continue
        index += 1
    projects = state["projects"]

    if "projectV2(number:$number)" in query:
        login, number = variables.get("login"), variables.get("number")
        alias = next((key for key, value in projects.items()
                      if value["owner_login"] == login and str(value["project_number"]) == str(number)), None)
        if alias is None:
            fail(f"project not found in fixture: {login}/{number}")
        project = projects[alias]
        log_call("project-resolve", {"alias": alias}, False)
        payload = {"id": project["id"], "title": project["title"],
                   "fields": {"nodes": [{"id": field["id"], "name": field["name"],
                                         **({"options": field["options"]} if "options" in field else {})}
                                        for field in project["fields"]]}}
        owner_key = "user" if project["owner_type"] == "user" else "organization"
        other = "organization" if owner_key == "user" else "user"
        print(json.dumps({"data": {owner_key: {"projectV2": payload}, other: None}}, ensure_ascii=False))
        return

    alias_of = {value["id"]: key for key, value in projects.items()}

    if "... on ProjectV2Item{" in query and "fieldValues(" in query:
        item_id = variables.get("id")
        found = next(((key, item) for key, value in projects.items() for item in value["items"]
                      if item["id"] == item_id), None)
        if found is None:  # an item gone from the project: the planner reports it as missing
            log_call("project-item-fields", {"item_id": item_id, "found": False}, False)
            print(json.dumps({"data": {"node": None}}, ensure_ascii=False))
            return
        alias, item = found
        fields = {field["name"]: field for field in projects[alias]["fields"]}
        nodes = [field_value(fields.get(name, {}), name, value)
                 for name, value in sorted(item["fields"].items()) if value is not None]
        log_call("project-item-fields", {"alias": alias, "item_id": item_id, "fields": len(nodes)}, False)
        print(json.dumps({"data": {"node": {"id": item_id, "fieldValues": {"nodes": nodes}}}}, ensure_ascii=False))
        return

    if "clearProjectV2ItemFieldValue" in query:
        project_id, item_id, field_id = variables.get("project"), variables.get("item"), variables.get("field", "")
        alias = alias_of.get(project_id)
        if alias is None:
            fail(f"project id not found in fixture: {project_id}")
        item = next((row for row in projects[alias]["items"] if row["id"] == item_id), None)
        if item is None:
            fail(f"project item not found in fixture: {item_id}")
        name = next((field["name"] for field in projects[alias]["fields"] if field["id"] == field_id), None)
        if name is None:
            fail(f"unknown field {field_id}")
        if item["fields"].get(name) is not None:
            item["fields"].pop(name)
            item["field_updated_at"][name] = state["clock"]["issue_update_updated_at"]
            state["mutation_log"].append({"op": "project-item-clear", "alias": alias, "item_id": item_id,
                                          "field": name})
            save(state)
        log_call("project-item-clear", {"alias": alias, "item_id": item_id, "field": name}, True)
        print(json.dumps({"data": {"clearProjectV2ItemFieldValue": {"projectV2Item": {"id": item_id}}}},
                         ensure_ascii=False))
        return

    if "items(first:100,after:$cursor)" in query:
        project_id = variables.get("id")
        alias = alias_of.get(project_id)
        if alias is None:
            fail(f"project id not found in fixture: {project_id}")
        nodes = [{"id": item["id"], "content": {"id": item["content_id"], "number": item["content_number"],
                                                "url": f"https://github.invalid/{state['repo']}/issues/{item['content_number']}"}}
                 for item in projects[alias]["items"]]
        log_call("project-item-find", {"alias": alias, "items": len(nodes)}, False)
        print(json.dumps({"data": {"node": {"items": {"nodes": nodes,
                                                      "pageInfo": {"hasNextPage": False, "endCursor": None}}}}},
                         ensure_ascii=False))
        return

    if "addProjectV2ItemById" in query:
        project_id, content_id = variables.get("project"), variables.get("content")
        alias = alias_of.get(project_id)
        if alias is None:
            fail(f"project id not found in fixture: {project_id}")
        existing = next((item for item in projects[alias]["items"] if item["content_id"] == content_id), None)
        if existing is None:
            existing = {"id": f"PVTI_lADOFIXTURE0001zgA{len(projects[alias]['items']) + 1:04d}",
                        "content_id": content_id, "content_number": None, "fields": {}, "field_updated_at": {}}
            projects[alias]["items"].append(existing)
            state["mutation_log"].append({"op": "project-item-add", "alias": alias, "item_id": existing["id"],
                                          "content_id": content_id})
            save(state)
        log_call("project-item-add", {"alias": alias, "item_id": existing["id"]}, True)
        print(json.dumps({"data": {"addProjectV2ItemById": {"item": {"id": existing["id"]}}}}, ensure_ascii=False))
        return

    if "updateProjectV2ItemFieldValue" in query:
        project_id, item_id = variables.get("project"), variables.get("item")
        alias = alias_of.get(project_id)
        if alias is None:
            fail(f"project id not found in fixture: {project_id}")
        item = next((row for row in projects[alias]["items"] if row["id"] == item_id), None)
        if item is None:
            fail(f"project item not found in fixture: {item_id}")
        name, value = option_value(state, alias, variables.get("field", ""), variables.get("option", ""))
        if item["fields"].get(name) != value:
            item["fields"][name] = value
            item["field_updated_at"][name] = state["clock"]["issue_update_updated_at"]
            state["mutation_log"].append({"op": "project-item-edit", "alias": alias, "item_id": item_id,
                                          "field": name, "value": value})
            save(state)
        log_call("project-item-edit", {"alias": alias, "item_id": item_id, "field": name}, True)
        print(json.dumps({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": item_id}}}},
                         ensure_ascii=False))
        return

    fail("unsupported graphql query for this fixture")


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        fail("no arguments")
    state = load()
    if argv[0] == "issue":
        handle_issue(state, argv)
        return 0
    if argv[0] == "api" and len(argv) > 1 and argv[1] == "graphql":
        handle_graphql(state, argv[2:])
        return 0
    fail(f"unsupported gh invocation: {' '.join(argv)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
