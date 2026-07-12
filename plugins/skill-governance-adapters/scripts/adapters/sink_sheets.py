#!/usr/bin/env python3
# /// script
# name: sink-sheets
# purpose: Append payload data to Google Sheets under Sink Contract v1.0.
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
"""Google Sheets sink adapter. Sink Contract v1.0準拠。

実装: Google Sheets API v4 (values:append) を直接呼ぶ。
OAuth tokenはKeychainから取得。
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


SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


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

        spreadsheet_id = params["spreadsheet_id"]
        sheet = params.get("sheet", "Sheet1")
        token_ref = params["token_ref"]

        try:
            secret = get_secret(token_ref)
        except SecretError as se:
            print(json.dumps({"status": "failure", "adapter": "sheets", "errors": [str(se)]}))
            sys.exit(2)

        # 行データ: [timestamp, kind, title, body, tags]
        metadata = payload.get("metadata", {})
        row = [
            metadata.get("timestamp", ""),
            payload.get("kind", ""),
            payload.get("title", ""),
            payload.get("body", "")[:5000],
            ",".join(metadata.get("tags", [])),
        ]

        url = f"{SHEETS_API}/{spreadsheet_id}/values/{sheet}:append?valueInputOption=USER_ENTERED"
        body = json.dumps({"values": [row]}).encode()

        if args.dry_run:
            print(json.dumps({"status": "success", "adapter": "sheets", "location": f"sheets://{spreadsheet_id}/{sheet}", "external_id": "", "dry_run": True}))
            return

        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = json.loads(resp.read())
                updated_range = resp_body.get("updates", {}).get("updatedRange", "")
                print(json.dumps({
                    "status": "success",
                    "adapter": "sheets",
                    "location": f"sheets://{spreadsheet_id}/{updated_range}",
                    "external_id": updated_range,
                    "errors": [],
                }))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="ignore")[:500]
            msg = sanitize_error(f"Sheets HTTP {e.code}: {err_body}", [secret])
            print(json.dumps({"status": "failure", "adapter": "sheets", "errors": [msg]}))
            sys.exit(3)

    except Exception as e:
        msg = sanitize_error(str(e), [secret])
        print(json.dumps({"status": "failure", "adapter": "sheets", "errors": [msg]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
