#!/usr/bin/env python3
# /// script
# name: post-publish-notify
# purpose: Verify one Notion publish success receipt and attempt one deduplicated Slack notification.
# inputs: [--receipt notion-log.json, --hint, optional macOS Keychain webhook]
# outputs: [stderr JSON status, .post-publish-notifications/<publish_event_id>.json]
# contexts: [E]
# network: true
# write-scope: <receipt-dir>/.post-publish-notifications/
# dependencies: [scripts/keychain_get_secret.py]
# requires-python: ">=3.10"
# ///
"""Deliver one optional Slack notification for one verified publish receipt.

This is deliberately not a generic PostToolUse hook.  The publish pipeline calls
it only after writing a successful ``notion-log.json`` receipt.  A per-event
O_EXCL claim makes concurrent/repeated calls at-most-once at the transport
boundary; claimed events are never automatically replayed because a timeout
after remote acceptance is ambiguous and replay could duplicate the message.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Callable


EVENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
STATE_DIR = ".post-publish-notifications"
KEYCHAIN_SCRIPT = Path(__file__).resolve().parent / "keychain_get_secret.py"


def _read_success_receipt(path: Path) -> dict | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    event_id = value.get("publish_event_id")
    url = value.get("url")
    if (
        value.get("status") != "published"
        or value.get("stage") != "publish"
        or value.get("exit_code") != 0
        or not isinstance(event_id, str)
        or not EVENT_ID_RE.fullmatch(event_id)
        or not isinstance(url, str)
        or not url.startswith("https://")
    ):
        return None
    return value


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _claim(path: Path, value: dict) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return True


def read_webhook() -> str | None:
    """Read the optional webhook through the single Keychain helper."""
    if not KEYCHAIN_SCRIPT.is_file():
        return None
    service = os.environ.get("INTAKE_SLACK_KEYCHAIN_SERVICE", "slack-incoming-webhook")
    account = os.environ.get("INTAKE_SLACK_KEYCHAIN_ACCOUNT", "harness")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(KEYCHAIN_SCRIPT),
                "--service",
                service,
                "--account",
                account,
                "--print-unsafe",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    secret = proc.stdout.strip() if proc.returncode == 0 else ""
    return secret if secret.startswith("https://") else None


def send_slack(webhook: str, text: str) -> int:
    payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310 - validated https webhook
        return int(response.status)


def notify(
    receipt_path: Path,
    *,
    hint: str | None = None,
    secret_reader: Callable[[], str | None] = read_webhook,
    sender: Callable[[str, str], int] = send_slack,
) -> dict:
    """Notify once for a valid successful receipt; never expose the webhook."""
    receipt_path = Path(receipt_path).resolve()
    receipt = _read_success_receipt(receipt_path)
    if receipt is None:
        return {"status": "skipped_invalid_receipt", "notified": False}

    event_id = receipt["publish_event_id"]
    marker = receipt_path.parent / STATE_DIR / f"{event_id}.json"
    if marker.exists():
        return {"status": "deduplicated", "notified": False, "event_id": event_id}

    webhook = secret_reader()
    if not isinstance(webhook, str) or not webhook.startswith("https://"):
        return {"status": "skipped_not_configured", "notified": False, "event_id": event_id}

    claimed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    claimed = {
        "schema_version": "1.0",
        "event_id": event_id,
        "status": "claimed",
        "claimed_at": claimed_at,
    }
    if not _claim(marker, claimed):
        return {"status": "deduplicated", "notified": False, "event_id": event_id}

    safe_hint = str(hint or receipt_path.parent.name).replace("\r", " ").replace("\n", " ")[:200]
    text = f"intake published: {safe_hint} -> {receipt['url']}"
    try:
        http_status = sender(webhook, text)
        delivered = http_status == 200
        state = {
            **claimed,
            "status": "notified" if delivered else "delivery_failed",
            "http_status": int(http_status),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    except Exception as exc:  # Transport adapters are optional; preserve the durable no-replay claim.
        delivered = False
        state = {
            **claimed,
            "status": "delivery_failed",
            "error_type": type(exc).__name__,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    _atomic_json(marker, state)
    return {
        "status": "notified" if delivered else "delivery_failed",
        "notified": delivered,
        "event_id": event_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--hint")
    args = parser.parse_args(argv)
    result = notify(Path(args.receipt), hint=args.hint)
    print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
