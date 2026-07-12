#!/usr/bin/env python3
"""render_v2_adapter.py

M2 部分実装: render_notion_page.py から v2 経路を呼び出す軽量 adapter。
section_canonical_map.json を読み、intake.json を section_key 順で iterate し、
section ごとに (canonical_entry, value_dict) を yield する。

利用方針 (render_path_resolution=v2-strict):
  - 環境変数 SKILL_INTAKE_RENDER_VERSION=v2 のとき本 adapter 経由で render
  - v1 経路 (section-templates.json 直読み) は legacy_warning を stderr に emit して reject
  - render_notion_page.py の段階移行用エントリポイント

設計判断:
  - 本 adapter は intake → block iteration のみを担う。Notion block への
    展開は render_notion_page.py 側の責務 (関心分離)。
  - canonical_map と intake のキー整合は intake.schema.json で別途検証済 (重複検査しない)。

Usage:
  from render_v2_adapter import iter_sections, load_canonical_map
  for entry, value in iter_sections(intake):
      ...

CLI:
  python3 render_v2_adapter.py <intake.json>   # section_key 順で要約を stdout 出力
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterator

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MAP_PATH = PLUGIN_ROOT / "references" / "section_canonical_map.json"
RUNTIME_CONFIG_PATH = PLUGIN_ROOT / "references" / "runtime-config.json"


def load_canonical_map() -> dict:
    return json.loads(CANONICAL_MAP_PATH.read_text(encoding="utf-8"))


def load_runtime_config() -> dict:
    return json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))


def assert_v2_strict() -> None:
    """render_path_resolution=v2-strict 以外を reject。"""
    cfg = load_runtime_config()
    resolution = cfg.get("render_path_resolution", {})
    if resolution.get("policy") != "v2-strict":
        raise RuntimeError(
            f"render_path_resolution.policy must be 'v2-strict' (got {resolution.get('policy')!r}). "
            "v1 fallback は M1 共存期間でも禁止。"
        )


def iter_sections(intake: dict) -> Iterator[tuple[dict, dict]]:
    """canonical_map.sections の宣言順で (entry, value) を yield。

    value は intake.sections[section_key] (欠落時は空 dict)。
    """
    cmap = load_canonical_map()
    sections_in_intake = intake.get("sections", {})
    for entry in cmap.get("sections", []):
        section_key = entry["section_key"]
        value = sections_in_intake.get(section_key, {})
        yield entry, value


def summarize(intake_path: Path) -> int:
    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    cmap = load_canonical_map()
    print(f"canonical_map schema_version: {cmap['schema_version']}")
    print(f"intake schema_version: {intake.get('schema_version', '<missing>')}")
    print(f"--- sections ({len(cmap.get('sections', []))}) ---")
    for entry, value in iter_sections(intake):
        present = "present" if value else "EMPTY"
        print(
            f"  [{entry['section_key']}] {entry['user_canonical_section']} "
            f"→ subagent={entry['responsible_subagent']} status={present}"
        )
    return 0


def main(argv: list[str]) -> int:
    assert_v2_strict()
    if len(argv) < 2:
        print("Usage: render_v2_adapter.py <intake.json>", file=sys.stderr)
        return 2
    path = Path(argv[1]).resolve()
    if not path.exists():
        print(f"ERROR: intake not found: {path}", file=sys.stderr)
        return 2
    return summarize(path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
