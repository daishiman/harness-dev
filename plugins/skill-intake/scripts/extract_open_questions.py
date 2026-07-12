#!/usr/bin/env python3
"""Walk intake.json and surface strings that look like open questions."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_MARKERS = [
    re.compile(r'\?$'),
    re.compile(r'要確認'),
    re.compile(r'未定'),
    re.compile(r'\bTBD\b', re.IGNORECASE),
    re.compile(r'わからない'),
    re.compile(r'検討中'),
    re.compile(r'後で'),
]


def walk(obj: Any, prefix: str = '', acc: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    if acc is None:
        acc = []
    if obj is None:
        return acc
    if isinstance(obj, str):
        if any(m.search(obj) for m in _MARKERS):
            acc.append({'path': prefix, 'text': obj.strip()})
        return acc
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f'{prefix}[{i}]', acc)
        return acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, f'{prefix}.{k}' if prefix else k, acc)
    return acc


def extract(intake: dict[str, Any]) -> dict[str, Any]:
    detected = walk(intake)
    existing = intake.get('open_questions') if isinstance(intake.get('open_questions'), list) else []
    existing = list(existing or [])
    merged: list[Any] = list(existing)
    for d in detected:
        text = d['text']
        already = any((m if isinstance(m, str) else m.get('text')) == text for m in merged)
        if not already:
            merged.append(d)
    return {'count': len(merged), 'open_questions': merged}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: extract_open_questions.py <intake.json>\n')
        return 2
    try:
        data = json.loads(Path(argv[0]).resolve().read_text(encoding='utf-8'))
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = extract(data)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
