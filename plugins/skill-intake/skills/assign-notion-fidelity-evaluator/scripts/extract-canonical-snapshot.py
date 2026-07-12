#!/usr/bin/env python3
"""Extract canonical-page-snapshot.json from section_canonical_map.json (DRY).

references/section_canonical_map.json (v2) を派生元
として、本スキルが fidelity 比較に用いる snapshot を決定論的に生成する。

Usage:
    python3 extract-canonical-snapshot.py \
        --source <section_canonical_map.json> \
        --out    <canonical-page-snapshot.json> \
        [--canonical-page-id 35195d6503b781788e31f59b4e05e705]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

# plugin-root (= .../plugins/skill-intake) を __file__ 相対で解決し、marketplace install 後も
# cwd / repo レイアウトに依存せず canonical map を見つける (parents[3] = plugin root)。
PLUGIN_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = PLUGIN_ROOT / "references/section_canonical_map.json"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "references/canonical-page-snapshot.json"
DEFAULT_PAGE_ID = "35195d6503b781788e31f59b4e05e705"


def _now_jst() -> str:
    jst = _dt.timezone(_dt.timedelta(hours=9))
    return _dt.datetime.now(jst).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(source: Path, page_id: str) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8"))
    sections = []
    for s in raw["sections"]:
        sections.append(
            {
                "section_key": s["section_key"],
                "user_canonical_section": s["user_canonical_section"],
                "title": s["title"],
                "required_fields": [
                    {
                        "key": f["key"],
                        "type": f.get("type"),
                        "absence_behavior": f.get("absence_behavior", "block"),
                    }
                    for f in s.get("required_fields", [])
                ],
                "char_bounds": s.get("char_bounds", {"min": 0, "max": 9999}),
                "viz_slots": [
                    {
                        "role": v.get("role"),
                        "asset_id": v.get("asset_id"),
                        "mandatory": bool(v.get("mandatory", False)),
                    }
                    for v in s.get("viz_slots", [])
                ],
                "absence_behavior": s.get("absence_behavior", "block"),
            }
        )
    return {
        "schema_version": raw.get("schema_version", "2.0.0"),
        "generated_at": _now_jst(),
        "canonical_page_id": page_id,
        "derived_from": {
            "path": str(source),
            "sha256": _sha256(source),
        },
        "sections": sections,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--canonical-page-id", default=DEFAULT_PAGE_ID)
    args = p.parse_args(argv)

    if not args.source.is_file():
        print(f"[extract-canonical-snapshot] source not found: {args.source}", file=sys.stderr)
        return 64

    snapshot = extract(args.source, args.canonical_page_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[extract-canonical-snapshot] wrote {args.out} ({len(snapshot['sections'])} sections)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
