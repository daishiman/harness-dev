#!/usr/bin/env python3
"""Validate that skill-intake completed Notion publish before run-skill-create builds.

This is intentionally small and file-based so Gate 1 can fail closed without
calling Notion. It verifies the local publish evidence produced by
plugins/skill-intake/scripts/intake_publish_pipeline.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def canonical_page_id(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).split("?")[0].split("#")[0].rstrip("/")
    parsed = urlparse(str(value))
    query = parse_qs(parsed.query)
    for key in ("p", "page_id"):
        for candidate in query.get(key, []):
            compact = re.sub(r"[^0-9a-fA-F]", "", str(candidate)).lower()
            if len(compact) == 32:
                return compact
    segment = (parsed.path or text).rstrip("/").split("/")[-1]
    uuid_match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        segment,
    )
    if uuid_match:
        return re.sub(r"[^0-9a-fA-F]", "", uuid_match.group(0)).lower()
    token = segment.split("-")[-1]
    if re.fullmatch(r"[0-9a-fA-F]{32}", token):
        return token.lower()
    compact = re.sub(r"[^0-9a-fA-F]", "", segment).lower()
    return compact if len(compact) == 32 else ""


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="output/<hint> directory from skill-intake")
    parser.add_argument("--page-id", default="", help="expected Notion page id or URL")
    parser.add_argument("--page-url", default="", help="expected Notion page URL")
    args = parser.parse_args()

    out_dir = Path(args.dir)
    result_path = out_dir / "notion-publish-result.json"
    log_path = out_dir / "notion-log.json"
    url_path = out_dir / "notion-url.txt"
    intake_path = out_dir / "intake.json"

    missing = [str(p) for p in (intake_path, result_path, log_path, url_path) if not p.exists()]
    if missing:
        print(f"[validate-intake-publish-ready] missing publish evidence: {missing}", file=sys.stderr)
        return 2

    try:
        result = read_json(result_path)
        log = read_json(log_path)
    except Exception as exc:
        print(f"[validate-intake-publish-ready] invalid publish evidence: {exc}", file=sys.stderr)
        return 2

    if log.get("status") != "published":
        print(f"[validate-intake-publish-ready] notion-log status is {log.get('status')!r}, expected 'published'", file=sys.stderr)
        return 2

    actual_page_id = canonical_page_id(result.get("page_id") or result.get("id") or log.get("page_id"))
    if not actual_page_id:
        print("[validate-intake-publish-ready] publish result has no page_id", file=sys.stderr)
        return 2

    actual_url = url_path.read_text(encoding="utf-8").strip()
    if not actual_url.startswith("https://www.notion.so/"):
        print(f"[validate-intake-publish-ready] invalid notion-url.txt: {actual_url!r}", file=sys.stderr)
        return 2

    expected_page_id = canonical_page_id(args.page_id) or canonical_page_id(args.page_url)
    if expected_page_id and expected_page_id != actual_page_id:
        print(
            "[validate-intake-publish-ready] page_id mismatch "
            f"(expected={expected_page_id}, actual={actual_page_id})",
            file=sys.stderr,
        )
        return 2

    try:
        intake = read_json(intake_path)
    except Exception as exc:
        print(f"[validate-intake-publish-ready] invalid intake.json: {exc}", file=sys.stderr)
        return 2

    target = intake.get("notion_target")
    if isinstance(target, dict) and target.get("mode") == "update":
        target_page_id = canonical_page_id(target.get("page_id") or target.get("page_url"))
        if not target_page_id:
            print("[validate-intake-publish-ready] intake.notion_target update mode lacks page_id", file=sys.stderr)
            return 2
        if target_page_id != actual_page_id:
            print(
                "[validate-intake-publish-ready] intake.notion_target does not match publish result "
                f"(target={target_page_id}, actual={actual_page_id})",
                file=sys.stderr,
            )
            return 2

    print(f"[validate-intake-publish-ready] PASS page_id={actual_page_id} url={actual_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
