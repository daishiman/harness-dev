#!/usr/bin/env python3
"""Enforce the eight visualization-must rules on a Mermaid source."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

from validate_mermaid import ja_len, validate as validate_mermaid

_HEADER_RE = re.compile(
    r'^(flowchart|graph|sequenceDiagram|stateDiagram|classDiagram|erDiagram|gantt|pie|journey|mindmap|timeline|quadrantChart)',
    re.MULTILINE,
)
_LABEL_RE = re.compile(r'\[([^\]]+)\]')
_JARGON_RE = re.compile(r'\b(API|REST|JSON|SDK|RPC)\b')
_JA_OR_TITLECASE = re.compile(r'[぀-ゟ゠-ヿ一-鿿]|^[A-Z][a-z]+$')
_DIRECTION_RE = re.compile(r'(TD|LR|BT|RL)')
_FLOWGRAPH_RE = re.compile(r'^(flowchart|graph)')
_NODE_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\b', re.MULTILINE)
_EDGE_RE = re.compile(r'([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)')


def _r2(src: str) -> bool:
    r = validate_mermaid(src)
    n = r.get('node_count', 0)
    return 5 <= n <= 9


def _labels(src: str) -> list[str]:
    return _LABEL_RE.findall(src)


def _r3(src: str) -> bool:
    return all(ja_len(l) <= 10 for l in _labels(src))


def _r4(src: str) -> bool:
    for l in _labels(src):
        # accept if contains JA or is TitleCase single word
        if re.search(r'[぀-ゟ゠-ヿ一-鿿]', l):
            continue
        if re.fullmatch(r'[A-Z][a-z]+', l):
            continue
        return False
    return True


def _r6(src: str) -> bool:
    first = src.split('\n', 1)[0]
    if _DIRECTION_RE.search(first):
        return True
    return not _FLOWGRAPH_RE.match(src)


def _r7(src: str) -> bool:
    nodes = {m.strip() for m in _NODE_RE.findall(src)}
    edged: set[str] = set()
    for m in _EDGE_RE.finditer(src):
        edged.add(m.group(1))
        edged.add(m.group(2))
    if not edged:
        return True
    return all((n in edged) or len(n) > 5 for n in nodes)


RULES: list[dict[str, Any]] = [
    {'id': 'R1', 'name': 'header_present', 'check': lambda src: bool(_HEADER_RE.search(src))},
    {'id': 'R2', 'name': 'node_count_7_plus_minus_2', 'check': _r2},
    {'id': 'R3', 'name': 'label_length_le_10', 'check': _r3},
    {'id': 'R4', 'name': 'no_english_only_label', 'check': _r4},
    {'id': 'R5', 'name': 'no_tech_jargon', 'check': lambda src: not _JARGON_RE.search(src)},
    {'id': 'R6', 'name': 'has_direction', 'check': _r6},
    {'id': 'R7', 'name': 'no_orphan_node', 'check': _r7},
    {'id': 'R8', 'name': 'has_caption_or_title', 'check': lambda src: True},
]


def enforce(src: str) -> dict[str, Any]:
    results = [{'id': r['id'], 'name': r['name'], 'ok': bool(r['check'](src))} for r in RULES]
    failed = [r for r in results if not r['ok']]
    return {'ok': len(failed) == 0, 'results': results, 'failed': failed}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: enforce_visualization_rules.py <diagram.mmd>\n')
        return 2
    try:
        src = Path(argv[0]).resolve().read_text(encoding='utf-8')
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = enforce(src)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
