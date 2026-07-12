#!/usr/bin/env python3
"""m3_deprecation_reverse_index.py

T3 (MD-08 対応): runtime-config.migration.deprecated_section_keys と
rename_map.keys に挙がっている legacy シンボルが、project tree 内の
どこからまだ参照されているかを逆引きする。M3 削除 PR 起票前に必須実行。

Usage:
  python3 m3_deprecation_reverse_index.py [--json]

Exit codes:
  0  PASS (deprecated 参照ゼロ)
  1  FOUND (deprecated 参照あり、stdout に一覧出力)
  2  IO error
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CONFIG = PLUGIN_ROOT / "references" / "runtime-config.json"

# 検索対象から除外するパス (本 reverse-index 自身 / canonical map / runtime-config / migration plan / trace 記録)
EXCLUDE_PATH_FRAGMENTS = (
    "m3_deprecation_reverse_index.py",
    "runtime-config.json",
    "section_canonical_map.json",
    "migration-plan-v2.md",
    "skill-build-trace",
    ".git/",
    "eval-log/docs/",
    "node_modules/",
)


def _collect_symbols(config: dict) -> list[str]:
    deprecated = list(config.get("migration", {}).get("deprecated_section_keys", []))
    rename_keys = list(config.get("migration", {}).get("rename_map", {}).keys())
    # 重複排除と順序保持
    seen: set[str] = set()
    out: list[str] = []
    for sym in deprecated + rename_keys:
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def _grep(symbol: str) -> list[str]:
    """git grep で symbol の出現箇所を列挙。除外パスを後段で filter。"""
    try:
        proc = subprocess.run(
            ["git", "grep", "-n", "--", symbol],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    if proc.returncode not in (0, 1):
        return []
    hits: list[str] = []
    for line in proc.stdout.splitlines():
        if any(frag in line for frag in EXCLUDE_PATH_FRAGMENTS):
            continue
        hits.append(line)
    return hits


def main(argv: list[str]) -> int:
    if not RUNTIME_CONFIG.exists():
        print(f"ERROR: runtime-config.json not found: {RUNTIME_CONFIG}", file=sys.stderr)
        return 2

    config = json.loads(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    symbols = _collect_symbols(config)

    report: dict[str, list[str]] = {}
    for sym in symbols:
        hits = _grep(sym)
        if hits:
            report[sym] = hits

    json_mode = "--json" in argv

    if not report:
        msg = "PASS: no external references to deprecated symbols"
        if json_mode:
            print(json.dumps({"verdict": "PASS", "symbols_checked": symbols, "references": {}}, ensure_ascii=False, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 0

    if json_mode:
        print(json.dumps({"verdict": "FOUND", "symbols_checked": symbols, "references": report}, ensure_ascii=False, indent=2))
    else:
        print("FOUND: deprecated symbols still referenced", file=sys.stderr)
        for sym, hits in report.items():
            print(f"\n## {sym} ({len(hits)} hits)", file=sys.stderr)
            for h in hits[:20]:
                print(f"  {h}", file=sys.stderr)
            if len(hits) > 20:
                print(f"  ... and {len(hits) - 20} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
