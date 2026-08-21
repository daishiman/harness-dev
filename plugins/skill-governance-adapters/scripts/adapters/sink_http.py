#!/usr/bin/env python3
# /// script
# name: sink-http
# purpose: Send payloads to an HTTP endpoint under Sink Contract v1.0.
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
"""Generic HTTP sink adapter. Sink Contract v1.0準拠。
Keychainからsecretを取得しsubprocess内でHTTP呼出し。secretはClaudeに渡らない。
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from secret_helper import get_secret, sanitize_error, SecretError  # noqa: E402


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

        url = params["url"]
        method = params.get("method", "POST").upper()
        headers = dict(params.get("headers", {}))

        auth = params.get("auth")
        scheme = auth.get("scheme", "bearer") if auth else None
        token_ref = auth.get("token_ref") if auth else None
        auth_header = (
            "Authorization" if scheme == "bearer"
            else auth.get("header", "X-API-Key") if scheme == "header"
            else None
        )

        # dry-run は credential を参照しない。secret を取得しないため keychain
        # provider 非配備でも成立し、同時にどの scheme でも実値が stdout へ出ない。
        if args.dry_run:
            safe = {**headers}
            if token_ref and auth_header:
                safe[auth_header] = "Bearer [REDACTED]" if scheme == "bearer" else "[REDACTED]"
            print(json.dumps({"status": "success", "adapter": "http", "location": url, "external_id": "", "dry_run": True, "headers": safe}))
            return

        if token_ref and auth_header:
            try:
                secret = get_secret(token_ref)
            except SecretError as se:
                print(json.dumps({"status": "failure", "adapter": "http", "errors": [str(se)]}))
                sys.exit(2)
            headers[auth_header] = f"Bearer {secret}" if scheme == "bearer" else secret

        body = json.dumps(payload).encode()
        headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                location = resp.headers.get("Location", url)
                ext_id = resp.headers.get("X-Resource-Id", "")
                print(json.dumps({"status": "success", "adapter": "http", "location": location, "external_id": ext_id, "errors": []}))
        except urllib.error.HTTPError as e:
            msg = sanitize_error(f"HTTP {e.code}: {e.reason}", [secret])
            print(json.dumps({"status": "failure", "adapter": "http", "errors": [msg]}))
            sys.exit(3)
        except urllib.error.URLError as e:
            msg = sanitize_error(f"URL error: {e.reason}", [secret])
            print(json.dumps({"status": "failure", "adapter": "http", "errors": [msg]}))
            sys.exit(3)

    except Exception as e:
        msg = sanitize_error(str(e), [secret])
        print(json.dumps({"status": "failure", "adapter": "http", "errors": [msg]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
