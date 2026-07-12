#!/usr/bin/env python3
"""Pick a Mermaid diagram type per section based on Japanese/English keywords."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RULES: list[dict[str, Any]] = [
    {'type': 'sequence', 'keywords': ['順番', 'やりとり', 'メッセージ', '対話', 'sequence', '会話']},
    {'type': 'flow', 'keywords': ['手順', '流れ', 'プロセス', 'process', '工程', 'workflow']},
    {'type': 'quadrant', 'keywords': ['比較', '優先', '位置付け', '象限', 'trade-off', '評価']},
    {'type': 'state', 'keywords': ['状態', 'ステート', 'ライフサイクル', '遷移']},
    {'type': 'pie', 'keywords': ['割合', 'シェア', '比率', '構成比']},
    {'type': 'mindmap', 'keywords': ['分類', '構造', '要素', '体系']},
    {'type': 'class', 'keywords': ['データ構造', '属性', '関係']},
    {'type': 'er', 'keywords': ['DB', 'テーブル', 'スキーマ', 'entity']},
    {'type': 'gantt', 'keywords': ['期間', 'スケジュール', 'タイムライン']},
    {'type': 'journey', 'keywords': ['体験', 'ユーザー体験', 'journey']},
    {'type': 'timeline', 'keywords': ['年表', '歴史', 'timeline']},
    {'type': 'graph', 'keywords': []},
]


def pick(text: Any) -> str:
    t = str(text or '')
    for r in RULES:
        if any(k in t for k in r['keywords']):
            return r['type']
    return 'flow'


def select_all(intake: dict[str, Any]) -> dict[str, str]:
    sections = intake.get('sections') or {}
    return {k: pick(v) for k, v in sections.items()}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: select_diagram_type.py <intake.json>\n')
        return 2
    try:
        data = json.loads(Path(argv[0]).resolve().read_text(encoding='utf-8'))
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = select_all(data)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
