#!/usr/bin/env python3
"""Append a per-session record to eval-log/skill-intake/<date>.jsonl."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args(argv: list[str]) -> dict[str, Any]:
    args: dict[str, Any] = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--hint':
            i += 1
            args['hint'] = argv[i]
        elif a == '--root':
            i += 1
            args['root'] = argv[i]
        elif a == '--out':
            i += 1
            args['out'] = argv[i]
        i += 1
    return args


def safe_read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def iso_date(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d')


def count_sections(intake: Any) -> int:
    if not intake:
        return 0
    if isinstance(intake, dict):
        secs = intake.get('sections')
        if isinstance(secs, list):
            return len(secs)
        axes = intake.get('5_axes') or intake.get('five_axes')
        if isinstance(axes, dict):
            return len(axes)
    return 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.get('hint'):
        sys.stderr.write('usage: append_eval_log.py --hint <hint> [--root <repo>] [--out <dir>]\n')
        return 2
    root = Path(args.get('root') or os.getcwd()).resolve()
    out_dir = Path(args.get('out') or (root / 'eval-log/skill-intake')).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    self_update = safe_read(root / 'output' / args['hint'] / 'self-update.json') or {}
    intake = safe_read(root / 'output' / args['hint'] / 'intake.json') or {}

    date = iso_date(datetime.now(timezone.utc))
    vrs = self_update.get('value_realized_score')
    candidates_applied = self_update.get('candidates_applied')
    added_questions = self_update.get('added_questions')
    if isinstance(candidates_applied, (int, float)):
        questions_added = int(candidates_applied)
    elif isinstance(added_questions, list):
        questions_added = len(added_questions)
    else:
        questions_added = 0
    record = {
        'date': date,
        'hint': args['hint'],
        'value_realized_score': vrs if isinstance(vrs, (int, float)) else None,
        'sections_count': count_sections(intake),
        'questions_added': questions_added,
        'status': self_update.get('session_status') or self_update.get('status') or 'completed',
    }

    file = out_dir / f'{date}.jsonl'
    with file.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
    sys.stdout.write(json.dumps({'ok': True, 'file': str(file), 'record': record}, ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
