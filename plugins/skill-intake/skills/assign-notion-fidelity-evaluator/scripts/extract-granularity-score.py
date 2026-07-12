#!/usr/bin/env python3
"""Print overall granularity score (0-100) for intake-final-context.json.

CLI 用の軽量メトリクス取得スクリプト。verdict 判定や Markdown 生成は行わず、
validate-notion-fidelity.py の evaluate() を再利用して overall_score のみを stdout
に 1 行で出す。CI のメトリクス収集向け。

Usage:
    python3 extract-granularity-score.py <intake-final-context.json> \
        [--snapshot <canonical-page-snapshot.json>]
Exit: 0 (always; verdict 判定をしない)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHECK_PATH = SCRIPT_DIR / "validate-notion-fidelity.py"
DEFAULT_SNAPSHOT = SCRIPT_DIR.parent / "references/canonical-page-snapshot.json"


def _load_check_module():
    spec = importlib.util.spec_from_file_location("check_notion_fidelity", CHECK_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("context", type=Path)
    p.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    args = p.parse_args(argv)

    if not args.context.is_file() or not args.snapshot.is_file():
        print("0.0")
        return 0

    check = _load_check_module()
    context = json.loads(args.context.read_text(encoding="utf-8"))
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    report = check.evaluate(context, snapshot)
    print(report["overall_score"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
