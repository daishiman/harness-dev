#!/usr/bin/env python3
# /// script
# name: check-rubric-sync
# purpose: Detect version or hash drift between canonical and evaluator rubrics.
# inputs:
#   - argv: no required arguments
# outputs:
#   - stdout: OK status
#   - stderr: drift findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""check-rubric-sync.py — upstream rubric と evaluator 派生 rubric の版ずれ検出.

ref-skill-design-rubric/references/rubric.json (upstream 正本) の SHA-256 と rubric_version
を計算し、assign-skill-design-evaluator/references/rubric.json と照合する。

照合戦略:
  1. assign 側に `rubric_hash` フィールドがあれば、その値と upstream SHA-256 を
     直接比較する（厳密一致モード）。
  2. `rubric_hash` フィールドが無い場合は、`rubric_version` を比較する
     （バージョン同期モード）。
  3. どちらでも不一致なら exit 1 で `RUBRIC_DRIFT:` メッセージを stderr に出力。

stdlib only / Python 3.9+.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# __file__ = <repo>/plugins/skill-governance-lint/scripts/check-rubric-sync.py
REPO_ROOT = Path(__file__).resolve().parents[3]
UPSTREAM = (
    REPO_ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "ref-skill-design-rubric"
    / "references"
    / "rubric.json"
)
DERIVED = (
    REPO_ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "assign-skill-design-evaluator"
    / "references"
    / "rubric.json"
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    for p in (UPSTREAM, DERIVED):
        if not p.exists():
            print(f"RUBRIC_DRIFT: missing file {p}", file=sys.stderr)
            return 1

    upstream_hash = sha256_of(UPSTREAM)
    upstream_doc = load_json(UPSTREAM)
    derived_doc = load_json(DERIVED)

    upstream_version = upstream_doc.get("rubric_version")
    derived_version = derived_doc.get("rubric_version")
    derived_hash_field = derived_doc.get("rubric_hash")

    # Mode 1: hash field present -> strict compare
    if derived_hash_field is not None:
        if derived_hash_field != upstream_hash:
            print(
                "RUBRIC_DRIFT: hash mismatch\n"
                f"  upstream  ({UPSTREAM.relative_to(REPO_ROOT)}): {upstream_hash}\n"
                f"  derived   ({DERIVED.relative_to(REPO_ROOT)}) rubric_hash: {derived_hash_field}",
                file=sys.stderr,
            )
            return 1
        print(
            f"OK: rubric_hash matches ({upstream_hash[:12]}…) "
            f"version={upstream_version}"
        )
        return 0

    # Mode 2: version compare
    if upstream_version != derived_version:
        print(
            "RUBRIC_DRIFT: rubric_version mismatch\n"
            f"  upstream  ({UPSTREAM.relative_to(REPO_ROOT)}): {upstream_version}\n"
            f"  derived   ({DERIVED.relative_to(REPO_ROOT)}): {derived_version}\n"
            f"  upstream sha256: {upstream_hash}",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: rubric_version matches ({upstream_version}); "
        f"upstream sha256={upstream_hash[:12]}…  "
        "(consider adding `rubric_hash` to derived for strict checking)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
