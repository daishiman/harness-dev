#!/usr/bin/env python3
"""Lightweight Mermaid syntax sanity validator (no external CLI)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HEADERS = [
    'flowchart', 'graph', 'sequenceDiagram', 'classDiagram', 'stateDiagram', 'stateDiagram-v2',
    'erDiagram', 'gantt', 'pie', 'journey', 'mindmap', 'timeline', 'quadrantChart',
]

_BRACKET = re.compile(r'\[([^\]\n]+)\]')
_PAREN = re.compile(r'\(([^)\n]+)\)')


def ja_len(s: str) -> float:
    n = 0.0
    for ch in s:
        n += 1 if ord(ch) > 127 else 0.5
    return n


def extract_node_labels(src: str) -> list[str]:
    return _BRACKET.findall(src) + _PAREN.findall(src)


def validate(src: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    trimmed = src.strip()
    if not trimmed:
        return {'ok': False, 'errors': ['empty diagram'], 'warnings': warnings, 'node_count': 0}
    first_word = trimmed.split()[0]
    if not any(first_word.startswith(h) for h in HEADERS):
        errors.append(f'unknown diagram header: {first_word}')
    lines = [l for l in trimmed.split('\n') if l.strip() and not l.strip().startswith('%%')]
    body_lines = lines[1:]
    node_count = len(body_lines)
    if node_count < 5 or node_count > 9:
        warnings.append(f'node/line count {node_count} outside 7±2')
    labels = extract_node_labels(trimmed)
    for lbl in labels:
        if ja_len(lbl) > 10:
            warnings.append(f'label too long: "{lbl}"')
    return {
        'ok': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'node_count': node_count,
        'label_count': len(labels),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: validate_mermaid.py <diagram.mmd>\n')
        return 2
    try:
        src = Path(argv[0]).resolve().read_text(encoding='utf-8')
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = validate(src)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
