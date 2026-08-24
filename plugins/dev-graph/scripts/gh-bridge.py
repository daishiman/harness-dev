#!/usr/bin/env python3
# /// script
# name: gh-bridge
# purpose: Provide a deterministic, dry-run-safe bridge to approved gh Issue, Projects v2 and lifecycle fact operations.
# inputs: ["argv: --op OP --repo OWNER/REPO and operation fields"]
# outputs: ["stdout: normalized JSON result or mutation preview"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: true
# write-scope: approved gh CLI mutations only
# ///
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from _common import ContractError, dump, run

MUTATIONS = {"issue-create", "issue-update", "issue-close", "project-item-add", "project-item-edit"}
ISSUE_FIELDS = "id,number,title,state,url,updatedAt"


def retry_classification(op: str) -> str:
    """Describe how a caller may repeat an operation after an uncertain result."""
    if op in {"issue-fetch", "lifecycle-facts", "project-resolve", "project-item-find"}:
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


def graphql(query: str, variables: dict[str, str]) -> Any:
    argv = ["api", "graphql", "-f", f"query={query}"]
    for key, value in sorted(variables.items()): argv += ["-F", f"{key}={value}"]
    return gh_json(argv)


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
    payload = graphql(query, {"owner": owner, "name": name, "number": str(number)})
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
    p = argparse.ArgumentParser(); p.add_argument("--op", required=True, choices=("issue-fetch", "issue-create", "issue-update", "issue-close", "lifecycle-facts", "project-resolve", "project-item-find", "project-item-add", "project-item-edit"))
    p.add_argument("--repo"); p.add_argument("--number", type=int); p.add_argument("--title"); p.add_argument("--body")
    p.add_argument("--owner"); p.add_argument("--project-number", type=int); p.add_argument("--content-id"); p.add_argument("--project-id"); p.add_argument("--item-id"); p.add_argument("--field-id"); p.add_argument("--option-id"); p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(); op = a.op
    if (op.startswith("issue-") or op == "lifecycle-facts") and not a.repo: raise ContractError("--repo required")
    if a.dry_run and op in MUTATIONS:
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
        query = "query($login:String!,$number:Int!){user(login:$login){projectV2(number:$number){id title fields(first:100){nodes{... on ProjectV2FieldCommon{id name} ... on ProjectV2SingleSelectField{id name options{id name}}}}}} organization(login:$login){projectV2(number:$number){id title fields(first:100){nodes{... on ProjectV2FieldCommon{id name} ... on ProjectV2SingleSelectField{id name options{id name}}}}}}}"
        data = graphql(query, {"login": a.owner, "number": str(a.project_number)}).get("data", {})
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
    elif op == "project-item-add":
        if not a.project_id or not a.content_id: raise ContractError("--project-id and --content-id required")
        q = "mutation($project:ID!,$content:ID!){addProjectV2ItemById(input:{projectId:$project,contentId:$content}){item{id}}}"
        result = graphql(q, {"project": a.project_id, "content": a.content_id})
    else:
        if not all((a.project_id, a.item_id, a.field_id, a.option_id)): raise ContractError("project/item/field/option ids required")
        q = "mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}"
        result = graphql(q, {"project": a.project_id, "item": a.item_id, "field": a.field_id, "option": a.option_id})
    dump({"op": op, "dry_run": False, "result": result, "retry_classification": retry_classification(op)})
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ContractError as exc: print(str(exc), file=sys.stderr); raise SystemExit(1)
