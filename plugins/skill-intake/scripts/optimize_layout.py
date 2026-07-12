#!/usr/bin/env python3
"""Suggest a topological order of nodes in a Mermaid flow diagram."""
from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

_EDGE_RE = re.compile(
    r'^\s*([A-Za-z0-9_]+)(?:\[[^\]]*\])?\s*-->\s*(?:\|[^|]*\|\s*)?([A-Za-z0-9_]+)',
    re.MULTILINE,
)


def parse_edges(src: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _EDGE_RE.finditer(src)]


def topo_order(edges: list[tuple[str, str]]) -> list[str]:
    nodes: set[str] = set()
    incoming: dict[str, int] = {}
    outgoing: dict[str, list[str]] = {}
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)
        incoming[b] = incoming.get(b, 0) + 1
        outgoing.setdefault(a, []).append(b)
    in_deg = {n: incoming.get(n, 0) for n in nodes}
    queue = deque(n for n in nodes if in_deg[n] == 0)
    order: list[str] = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for nxt in outgoing.get(n, []):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(nodes):
        return list(nodes)
    return order


def optimize(src: str) -> dict[str, Any]:
    edges = parse_edges(src)
    order = topo_order(edges)
    return {'order': order, 'edge_count': len(edges), 'suggestion': ' -> '.join(order)}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: optimize_layout.py <diagram.mmd>\n')
        return 2
    try:
        src = Path(argv[0]).resolve().read_text(encoding='utf-8')
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = optimize(src)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
