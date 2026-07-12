#!/usr/bin/env python3
"""Append new questions to the shared question-bank.md with dedup, snapshot, and rollback."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_LINES = 3000
MAX_PER_SESSION = 5

_BULLET_RE = re.compile(r'^\s*-\s+(.+?)(?:<!--.*?-->)?\s*$', re.MULTILINE)


def load_bank(p: Path) -> str:
    if not p.exists():
        return ''
    return p.read_text(encoding='utf-8')


def count_lines(s: str) -> int:
    if not s:
        return 0
    return len(s.split('\n'))


def normalize(text: Any) -> str:
    return re.sub(r'\s+', ' ', str(text or '').lower()).strip()


def dedup(existing: str, candidates: list[Any]) -> list[Any]:
    seen: set[str] = set()
    for m in _BULLET_RE.finditer(existing):
        seen.add(normalize(m.group(1)))
    out: list[Any] = []
    for q in candidates:
        t = q if isinstance(q, str) else (q.get('text') if isinstance(q, dict) else '') or ''
        n = normalize(t)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(q)
    return out


def append(bank: str, session_id: str, questions: list[Any]) -> str:
    stamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    lines = [f'\n## Session {session_id} — {stamp}']
    for q in questions:
        if isinstance(q, str):
            text = q
            tags = ''
        elif isinstance(q, dict):
            text = q.get('text') or json.dumps(q, ensure_ascii=False)
            tag_list = q.get('tags')
            tags = f' <!-- {",".join(tag_list)} -->' if isinstance(tag_list, list) else ''
        else:
            text = json.dumps(q, ensure_ascii=False)
            tags = ''
        lines.append(f'- {text}{tags}')
    return re.sub(r'\s*$', '', bank) + '\n'.join(lines) + '\n'


def snapshot_path(hint: str) -> Path:
    return Path(f'output/{hint}/question-bank.snapshot.md').resolve()


def ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def save_snapshot(bank_file: Path, hint: str | None) -> Path | None:
    if not hint:
        return None
    snap = snapshot_path(hint)
    ensure_dir(snap)
    snap.write_text(load_bank(bank_file), encoding='utf-8')
    return snap


def rollback(bank_file: Path, hint: str) -> int:
    snap = snapshot_path(hint)
    if not snap.exists():
        sys.stderr.write(f'snapshot not found: {snap}\n')
        return 2
    data = snap.read_text(encoding='utf-8')
    bank_file.write_text(data, encoding='utf-8')
    sys.stdout.write(json.dumps({'ok': True, 'rolled_back': True, 'hint': hint, 'from': str(snap)}, ensure_ascii=False) + '\n')
    return 0


def parse_args(argv: list[str]) -> dict[str, Any]:
    args: dict[str, Any] = {'positional': []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--rollback':
            i += 1
            args['rollback'] = argv[i]
        elif a == '--hint':
            i += 1
            args['hint'] = argv[i]
        elif a == '--diff':
            i += 1
            args['diff'] = argv[i]
        elif a == '--bank':
            i += 1
            args['bank'] = argv[i]
        elif a == '--apply':
            args['apply'] = True
        else:
            args['positional'].append(a)
        i += 1
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    bank_file = Path(
        args.get('bank')
        or (args['positional'][0] if args['positional'] else None)
        or 'plugins/skill-intake/references/question-bank.md'
    ).resolve()

    if args.get('rollback'):
        return rollback(bank_file, args['rollback'])

    session_file = args.get('diff') or (args['positional'][1] if len(args['positional']) > 1 else None)
    if not session_file:
        sys.stderr.write('usage: update_question_bank.py [--bank <path>] [--diff <session.json>] [--apply] [--hint <hint>] | --rollback <hint>\n')
        return 2
    try:
        session = json.loads(Path(session_file).resolve().read_text(encoding='utf-8'))
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2

    session_id = session.get('session_id') or session.get('id') or f's-{int(datetime.now().timestamp()*1000)}'
    hint = args.get('hint') or session.get('hint') or session_id
    candidates = session.get('questions') or session.get('used_questions') or session.get('candidates') or []

    save_snapshot(bank_file, hint)

    bank = load_bank(bank_file)

    if count_lines(bank) > MAX_LINES:
        sys.stdout.write(json.dumps({'ok': False, 'status': 'halted_capacity', 'lines': count_lines(bank), 'max': MAX_LINES}, ensure_ascii=False) + '\n')
        return 3

    unique = dedup(bank, candidates)
    skipped = len(candidates) - len(unique)
    if len(unique) > MAX_PER_SESSION:
        unique = unique[:MAX_PER_SESSION]

    if not args.get('apply'):
        sys.stdout.write(json.dumps({'ok': True, 'dry_run': True, 'to_append': len(unique), 'skipped_duplicates': skipped}, ensure_ascii=False) + '\n')
        return 0

    nxt = append(bank, session_id, unique)
    if count_lines(nxt) > MAX_LINES:
        sys.stdout.write(json.dumps({'ok': False, 'status': 'halted_capacity', 'would_lines': count_lines(nxt), 'max': MAX_LINES}, ensure_ascii=False) + '\n')
        return 3
    bank_file.write_text(nxt, encoding='utf-8')
    sys.stdout.write(json.dumps({'ok': True, 'appended': len(unique), 'skipped_duplicates': skipped, 'session_id': session_id, 'hint': hint}, ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
