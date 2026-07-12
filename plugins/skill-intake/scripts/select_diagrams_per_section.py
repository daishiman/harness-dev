#!/usr/bin/env python3
"""Enforce min/max diagram count per section (1..3) and report violations."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MIN = 1
MAX = 3


def enforce(per_section: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, list[Any]] = {}
    violations: list[dict[str, Any]] = []
    for sec, val in per_section.items():
        arr = val if isinstance(val, list) else [val]
        if len(arr) < MIN:
            violations.append({'section': sec, 'count': len(arr), 'rule': f'min {MIN}'})
        if len(arr) > MAX:
            violations.append({'section': sec, 'count': len(arr), 'rule': f'max {MAX}'})
        out[sec] = arr[:MAX]
    return {'ok': len(violations) == 0, 'result': out, 'violations': violations}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: select_diagrams_per_section.py <map.json>\n')
        return 2
    try:
        data = json.loads(Path(argv[0]).resolve().read_text(encoding='utf-8'))
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = enforce(data)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
