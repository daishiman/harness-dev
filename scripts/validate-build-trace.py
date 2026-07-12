#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""validate-build-trace.py: ビルドトレース JSON の doc_coverage を検証する。

Usage:
  validate-build-trace.py build-trace.json

build-trace JSON の期待構造:
  {
    "doc_coverage": {
      "ch11_templates": true,
      "ch13_checklists": true,
      "ch14_dynamic_injection": true,
      "ch15_official_spec_checked": true,
      "ch16_frontmatter_spec": true,
      ...
    },
    ...
  }

B-3: doc_coverage に以下の必須キーがすべて存在し、かつ値が true / "true" であること:
  - ch11_templates
  - ch13_checklists
  - ch14_dynamic_injection
  - ch15_official_spec_checked
  - ch16_frontmatter_spec

いずれかが欠落または false の場合 exit 1。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_DOC_COVERAGE_KEYS: list[str] = [
    "ch11_templates",
    "ch13_checklists",
    "ch14_dynamic_injection",
    "ch15_official_spec_checked",
    "ch16_frontmatter_spec",
]


def _is_true(v: object) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() == "true"


def validate(trace: dict) -> list[str]:
    errs: list[str] = []

    doc_cov = trace.get("doc_coverage")
    if doc_cov is None:
        errs.append("missing top-level key: doc_coverage")
        return errs

    if not isinstance(doc_cov, dict):
        errs.append("doc_coverage must be an object/dict")
        return errs

    for key in REQUIRED_DOC_COVERAGE_KEYS:
        if key not in doc_cov:
            errs.append(f"doc_coverage missing required key: {key}")
        elif not _is_true(doc_cov[key]):
            errs.append(
                f"doc_coverage.{key} = {doc_cov[key]!r} (expected true)"
            )

    return errs


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: validate-build-trace.py build-trace.json", file=sys.stderr)
        return 2

    p = Path(sys.argv[1])
    if not p.exists():
        print(f"not found: {p}", file=sys.stderr)
        return 2

    try:
        trace = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return 1

    errs = validate(trace)
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1

    skill_name = trace.get("skill") or trace.get("name") or p.stem
    print(f"ok: {skill_name} doc_coverage PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
