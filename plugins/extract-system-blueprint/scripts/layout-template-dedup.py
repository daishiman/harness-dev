#!/usr/bin/env python3
# /// script
# name: layout-template-dedup
# purpose: layout_template_hash が同じ画面群から key screen 優先・URL辞書順で代表画面を決定論選択し、代表 layout を重複排除する (browser/screenshot 不使用時は inert だが汎用 layout dedup ロジックとして保持)
# inputs:
#   - argv: [INPUT_JSON | --input INPUT_JSON] [--self-test]
#   - JSON: layout_template_dedup.pages / pages / pages配列
# outputs:
#   - stdout: JSON {before_count, after_count, selected, skipped}
#   - stderr: 入力・JSON・page契約違反
#   - exit: 0=OK / 1=input violation / 2=usage
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Select one deterministic representative page per layout template.

Originally chose one screenshot target per layout template; with the browser /
screenshot path dropped this dedup is inert at runtime, but the deterministic
representative-selection logic is retained as a general-purpose layout dedup
utility.  The first occurrence of a ``layout_template_hash`` fixes the output
order of template groups.  Within each group, ``key_screen=true`` wins; pages
with the same key-screen rank are ordered by their URL using Python's Unicode
lexical ordering.  The CLI emits URL lists so its result can be compared
directly with ``tests/fixtures/llm-lanes.json::expected_representative_urls``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"


class InputViolation(ValueError):
    """Raised when input JSON does not satisfy the pages contract."""


def _extract_pages(payload: Any) -> list[Any]:
    """Accept a fixture root, a ``pages`` object, or a bare pages array."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise InputViolation("JSON root must be an object or a pages array")

    lane = payload.get("layout_template_dedup")
    if isinstance(lane, dict) and "pages" in lane:
        pages = lane["pages"]
    elif "pages" in payload:
        pages = payload["pages"]
    else:
        raise InputViolation("pages not found (expected layout_template_dedup.pages or pages)")

    if not isinstance(pages, list):
        raise InputViolation("pages must be an array")
    return pages


def _normalize_page(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InputViolation(f"pages[{index}] must be an object")

    url = raw.get("url")
    template_hash = raw.get("layout_template_hash")
    key_screen = raw.get("key_screen", False)
    if not isinstance(url, str) or not url.strip():
        raise InputViolation(f"pages[{index}].url must be a non-empty string")
    if not isinstance(template_hash, str) or not template_hash.strip():
        raise InputViolation(
            f"pages[{index}].layout_template_hash must be a non-empty string"
        )
    if not isinstance(key_screen, bool):
        raise InputViolation(f"pages[{index}].key_screen must be a boolean")

    return {
        "url": url,
        "layout_template_hash": template_hash,
        "key_screen": key_screen,
        "input_index": index,
    }


def deduplicate_pages(pages: list[Any]) -> dict[str, Any]:
    """Return representative and skipped URL lists for ``pages``."""
    normalized = [_normalize_page(page, index) for index, page in enumerate(pages)]

    urls = [page["url"] for page in normalized]
    if len(urls) != len(set(urls)):
        raise InputViolation("pages[].url must be unique")

    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for page in normalized:
        groups.setdefault(page["layout_template_hash"], []).append(page)

    selected_pages: list[dict[str, Any]] = []
    selected_indexes: set[int] = set()
    for candidates in groups.values():
        representative = min(
            candidates,
            key=lambda page: (not page["key_screen"], page["url"]),
        )
        selected_pages.append(representative)
        selected_indexes.add(representative["input_index"])

    selected = [page["url"] for page in selected_pages]
    skipped = [
        page["url"] for page in normalized if page["input_index"] not in selected_indexes
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "before_count": len(normalized),
        "after_count": len(selected),
        "selected": selected,
        "skipped": skipped,
    }


def _read_json(path_text: str) -> Any:
    if path_text == "-":
        source = sys.stdin.read()
        label = "stdin"
    else:
        path = Path(path_text)
        label = str(path)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise InputViolation(f"cannot read {label}: {exc}") from exc
    try:
        return json.loads(source)
    except json.JSONDecodeError as exc:
        raise InputViolation(f"invalid JSON in {label}: {exc}") from exc


def _self_test() -> None:
    fixture = [
        {"url": "https://example.test/product/a", "layout_template_hash": "product"},
        {
            "url": "https://example.test/product/z",
            "layout_template_hash": "product",
            "key_screen": True,
        },
        {"url": "https://example.test/help/b", "layout_template_hash": "help"},
        {"url": "https://example.test/help/a", "layout_template_hash": "help"},
    ]
    actual = deduplicate_pages(fixture)
    expected = {
        "schema_version": SCHEMA_VERSION,
        "before_count": 4,
        "after_count": 2,
        "selected": [
            "https://example.test/product/z",
            "https://example.test/help/a",
        ],
        "skipped": [
            "https://example.test/product/a",
            "https://example.test/help/b",
        ],
    }
    if actual != expected:
        raise AssertionError(f"self-test mismatch: expected={expected!r}, actual={actual!r}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select one representative layout URL per layout_template_hash"
    )
    parser.add_argument("input_path", nargs="?", help="input JSON path, or - for stdin")
    parser.add_argument("--input", dest="input_option", help="input JSON path, or - for stdin")
    parser.add_argument("--self-test", action="store_true", help="run deterministic built-in tests")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.self_test:
        if args.input_path or args.input_option:
            parser.error("--self-test cannot be combined with an input")
        try:
            _self_test()
        except (AssertionError, InputViolation) as exc:
            sys.stderr.write(f"self-test failed: {exc}\n")
            return 1
        sys.stdout.write("OK: layout-template-dedup self-test passed\n")
        return 0

    if bool(args.input_path) == bool(args.input_option):
        parser.error("provide exactly one of INPUT_JSON or --input INPUT_JSON")

    try:
        payload = _read_json(args.input_option or args.input_path)
        result = deduplicate_pages(_extract_pages(payload))
    except InputViolation as exc:
        sys.stderr.write(f"input violation: {exc}\n")
        return 1

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
