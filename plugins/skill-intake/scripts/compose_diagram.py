#!/usr/bin/env python3
"""Compose a Mermaid diagram from a typed template and variable dict."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

TEMPLATES: dict[str, str] = {
    'flow': 'flowchart TD\n{{nodes}}\n{{edges}}',
    'sequence': 'sequenceDiagram\n{{participants}}\n{{messages}}',
    'quadrant': 'quadrantChart\n  title {{title}}\n  x-axis {{x_low}} --> {{x_high}}\n  y-axis {{y_low}} --> {{y_high}}\n{{items}}',
    'state': 'stateDiagram-v2\n{{transitions}}',
    'graph': 'graph LR\n{{nodes}}\n{{edges}}',
}

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def fill(template: str, vars: dict[str, Any]) -> str:
    def _sub(m: re.Match[str]) -> str:
        v = vars.get(m.group(1))
        return '' if v is None else str(v)
    return _PLACEHOLDER.sub(_sub, template)


def compose(type_: str, vars: dict[str, Any] | None) -> str:
    tpl = TEMPLATES.get(type_, TEMPLATES['flow'])
    return fill(tpl, vars or {})


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: compose_diagram.py <type> [vars.json]\n')
        return 2
    type_ = argv[0]
    vars_file = argv[1] if len(argv) > 1 else None
    vars: dict[str, Any] = {}
    if vars_file:
        try:
            vars = json.loads(Path(vars_file).resolve().read_text(encoding='utf-8'))
        except Exception as e:
            sys.stderr.write(f'input error: {e}\n')
            return 2
    sys.stdout.write(compose(type_, vars) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
