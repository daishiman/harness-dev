#!/usr/bin/env python3
# /// script
# name: sink-notion
# purpose: Send payloads to Notion under Sink Contract v1.0.
# inputs:
#   - argv: --payload, --params, optional --dry-run
# outputs:
#   - stdout: Sink Contract JSON result
#   - stderr: sanitized adapter errors
# contexts: [E]
# network: true
# write-scope: none
# dependencies: []
# ///
"""Notion sink adapter. Sink Contract v1.0準拠。

実装方針:
- Notion公式API (api.notion.com) を直接呼ぶ。
- TokenはKeychainから取得しsubprocess内のみで使用。Claudeに渡さない。
- Claude Code環境ではNotion MCPが利用可能なら、本scriptを使わずworkflow側がMCP直呼びすることも可能。
  ただしroutingで一元管理したい場合は本scriptを使用する。
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "secrets"))
from keychain_helper import get_secret, sanitize_error, SecretError  # noqa: E402


NOTION_API = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def build_notion_page(payload: dict, database_id: str) -> dict:
    """payload → Notion API page object."""
    title = payload.get("title", "")
    body = payload.get("body", "")
    metadata = payload.get("metadata", {})
    tags = metadata.get("tags", [])

    return {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "Tags": {"multi_select": [{"name": t} for t in tags]} if tags else {"multi_select": []},
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": body[:2000]}}]
                },
            }
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    secret = ""
    try:
        payload = json.loads(Path(args.payload).read_text())
        params = json.loads(Path(args.params).read_text())

        database_id = params["database_id"]
        token_ref = params["token_ref"]

        try:
            secret = get_secret(token_ref)
        except SecretError as se:
            print(json.dumps({"status": "failure", "adapter": "notion", "errors": [str(se)]}))
            sys.exit(2)

        page = build_notion_page(payload, database_id)

        if args.dry_run:
            print(json.dumps({"status": "success", "adapter": "notion", "location": f"notion://db/{database_id}", "external_id": "", "dry_run": True}))
            return

        body = json.dumps(page).encode()
        req = urllib.request.Request(
            NOTION_API,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {secret}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = json.loads(resp.read())
                print(json.dumps({
                    "status": "success",
                    "adapter": "notion",
                    "location": resp_body.get("url", ""),
                    "external_id": resp_body.get("id", ""),
                    "errors": [],
                }))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="ignore")[:500]
            msg = sanitize_error(f"Notion HTTP {e.code}: {err_body}", [secret])
            print(json.dumps({"status": "failure", "adapter": "notion", "errors": [msg]}))
            sys.exit(3)

    except Exception as e:
        msg = sanitize_error(str(e), [secret])
        print(json.dumps({"status": "failure", "adapter": "notion", "errors": [msg]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
