#!/usr/bin/env python3
"""dry_render_notion.py — intake.json を v2 経路で Notion-like block JSON にドライ展開する。

目的 (T20):
  - render_v2_adapter.iter_sections() の canonical 順序で §0〜§11 を走査
  - 各 section を heading_2 + paragraph + figure placeholder の block 列に展開
  - 実 publish はせず stdout に JSON を出力 (人間/CI の視覚回帰用)

非目的:
  - rich_text の Notion API 完全準拠 (children 階層は1段で十分)
  - 値整形 (purpose_slots を完全文に整形するのは render_notion_page.py の責務)

Usage:
  python3 dry_render_notion.py <intake.json>
  python3 dry_render_notion.py <intake.json> --out eval-log/dry-notion-<id>.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from render_v2_adapter import assert_v2_strict, iter_sections, load_canonical_map  # noqa: E402


def _block_heading(title: str, level: int = 2) -> dict:
    return {
        "object": "block",
        "type": f"heading_{level}",
        f"heading_{level}": {"rich_text": [{"type": "text", "text": {"content": title}}]},
    }


def _block_paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _block_figure_placeholder(asset_id: str, role: str, mandatory: bool) -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": f"[figure:{asset_id}] role={role} mandatory={mandatory}"}}],
        },
    }


def _summarize_value(entry: dict, value: dict) -> str:
    if not value:
        return "(EMPTY: absence_behavior=" + entry.get("absence_behavior", "?") + ")"
    keys = [f["key"] for f in entry.get("required_fields", []) if f["key"] in value]
    missing = [f["key"] for f in entry.get("required_fields", []) if f.get("absence_behavior") == "block" and f["key"] not in value]
    parts = [f"present_required={len(keys)}/{sum(1 for f in entry.get('required_fields', []))}"]
    if missing:
        parts.append(f"BLOCK_MISSING={missing}")
    return " ".join(parts)


def render(intake: dict) -> dict:
    assert_v2_strict()
    cmap = load_canonical_map()
    blocks: list[dict] = []
    blocks.append(_block_heading(f"intake dry-render ({cmap['schema_version']})", level=1))
    for entry, value in iter_sections(intake):
        blocks.append(_block_heading(entry["title"], level=2))
        blocks.append(_block_paragraph(f"role: {entry.get('role_label', '')}"))
        blocks.append(_block_paragraph(_summarize_value(entry, value)))
        for slot in entry.get("viz_slots", []):
            blocks.append(_block_figure_placeholder(slot["asset_id"], slot.get("role", ""), slot.get("mandatory", False)))
    return {
        "schema_version_canonical": cmap["schema_version"],
        "schema_version_intake": intake.get("schema_version"),
        "block_count": len(blocks),
        "blocks": blocks,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: dry_render_notion.py <intake.json> [--out <path>]", file=sys.stderr)
        return 2
    path = Path(argv[1]).resolve()
    if not path.exists():
        print(f"ERROR: intake not found: {path}", file=sys.stderr)
        return 2
    out_path: Path | None = None
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 >= len(argv):
            print("ERROR: --out requires path", file=sys.stderr)
            return 2
        out_path = Path(argv[i + 1]).resolve()

    intake = json.loads(path.read_text(encoding="utf-8"))
    payload = render(intake)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"PASS: dry-render written to {out_path} (blocks={payload['block_count']})", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
