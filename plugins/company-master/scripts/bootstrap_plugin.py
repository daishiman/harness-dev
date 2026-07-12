#!/usr/bin/env python3
"""company-master plugin runtime bootstrap.

二役を担う:
  1. vendor 同梱依存の sys.path 解決: 将来 `vendor/` に外部ライブラリを置いた際、
     ユーザー手動 pip install を不要にするため `vendor/` を sys.path へ追加する。
  2. 共有モジュールの sys.path 解決: plugin-root `scripts/`
     (notion_config / resolve_company / enrich_company 等) を import 可能にする。
     resolve/enrich/upsert/backfill は build・backfill 両 skill で共有するため、
     実装の正本は plugin-root scripts/ に集約している。

**外部依存ゼロの現状では (2) が主機能**。`vendor/` は空のため (1) は no-op
(空ディレクトリでも sys.path には追加されるが解決対象が無い)。空 vendor の正当性は
`scripts/lint-company-master-vendored-deps.py` (B1) が機械強制する。
"""
from __future__ import annotations

import sys
from pathlib import Path


def plugin_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".claude-plugin").exists() or (parent / ".codex-plugin").exists():
            return parent
    return here.parents[1]


def bootstrap() -> Path:
    root = plugin_root()
    vendor = root / "vendor"
    shared_scripts = root / "scripts"
    for path in (vendor, shared_scripts):
        if path.exists():
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)
    return root


if __name__ == "__main__":
    print(bootstrap())
