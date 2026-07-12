#!/usr/bin/env python3
# /// script
# name: sink-slack
# purpose: Send payloads to Slack webhook under Sink Contract v1.0.
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
"""Slack webhook sink adapter. Sink Contract v1.0準拠。"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "secrets"))
from keychain_helper import get_secret, sanitize_error, SecretError  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    webhook = ""
    try:
        payload = json.loads(Path(args.payload).read_text())
        params = json.loads(Path(args.params).read_text())
        webhook_ref = params["webhook_ref"]

        try:
            webhook = get_secret(webhook_ref)
        except SecretError as se:
            print(json.dumps({"status": "failure", "adapter": "slack", "errors": [str(se)]}))
            sys.exit(2)

        text = f"*{payload.get('title','')}*\n{payload.get('body','')[:2000]}"
        body_obj = {"text": text}
        if params.get("channel"):
            body_obj["channel"] = params["channel"]

        if args.dry_run:
            print(json.dumps({"status": "success", "adapter": "slack", "location": "slack://webhook", "external_id": "", "dry_run": True}))
            return

        req = urllib.request.Request(
            webhook,
            data=json.dumps(body_obj).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
                print(json.dumps({"status": "success", "adapter": "slack", "location": "slack://webhook", "external_id": "", "errors": []}))
        except urllib.error.HTTPError as e:
            msg = sanitize_error(f"Slack HTTP {e.code}: {e.reason}", [webhook])
            print(json.dumps({"status": "failure", "adapter": "slack", "errors": [msg]}))
            sys.exit(3)

    except Exception as e:
        msg = sanitize_error(str(e), [webhook])
        print(json.dumps({"status": "failure", "adapter": "slack", "errors": [msg]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
