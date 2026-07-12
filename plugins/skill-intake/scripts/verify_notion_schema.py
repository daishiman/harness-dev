#!/usr/bin/env python3
"""期待スキーマと現状 DB の properties を突き合わせ conflicts を eval-log に出力。"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCRIPT_DIR.parent / 'references' / 'notion-db-schema.json'


def normalize_type(t):
    return t


def classify_conflict(expected, actual):
    spec = expected['spec']
    if actual is None:
        if spec.get('required'):
            return {'kind': 'missing', 'detail': f"required property absent (expected type={spec.get('type')})"}
        return {'kind': 'missing_optional', 'detail': f"optional property absent (expected type={spec.get('type')})"}
    exp_type = normalize_type(spec.get('type'))
    act_type = normalize_type(actual.get('type'))
    if exp_type != act_type:
        return {'kind': 'type_mismatch', 'detail': f'expected={exp_type}, actual={act_type}'}
    if exp_type in ('select', 'multi_select') and isinstance(spec.get('options'), list):
        actual_options = [o.get('name') for o in (actual.get(exp_type, {}).get('options') or [])]
        expected_set = set(spec['options'])
        actual_set = set(actual_options)
        missing = [o for o in spec['options'] if o not in actual_set]
        extra = [o for o in actual_options if o not in expected_set]
        if missing or extra:
            parts = []
            if missing:
                parts.append(f"missing options: [{', '.join(missing)}]")
            if extra:
                parts.append(f"extra options: [{', '.join(extra)}]")
            return {'kind': 'options_drift', 'detail': '; '.join(parts)}
    return {'kind': 'ok', 'detail': 'match'}


def classify_extras(expected_names, actual_props):
    out = []
    for name, val in actual_props.items():
        if name not in expected_names:
            out.append({'name': name, 'kind': 'extra', 'detail': f"unexpected property: {val.get('type')}"})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-id', dest='database_id')
    parser.add_argument('--on-conflict', dest='mode', default='skip-warn')
    parser.add_argument('--out', dest='out_path')
    args = parser.parse_args()

    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    # DB ID 解決は notion_config を SSOT とする。明示 NOTION_CONFIG_PATH が壊れている場合は
    # 別 config / schema default へフォールバックせず fail-closed。
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import notion_config as _nc
        repo_cfg_db_id = _nc.get_db_id('hearing-sheet')
    except Exception as e:
        print(f'[verify_notion_schema] notion_config failed: {e}', file=sys.stderr)
        return 2
    if args.database_id:
        database_id, db_id_source = args.database_id, 'arg'
    elif repo_cfg_db_id:
        database_id, db_id_source = repo_cfg_db_id, 'notion_config'
    else:
        database_id, db_id_source = None, None
    if not database_id:
        print('database_id is required (--database-id, or INTAKE_NOTION_DATABASE_ID / '
              '.notion-config.json#databases.hearing-sheet via notion_config). '
              'See references/notion-per-repo-setup.md', file=sys.stderr)
        return 2
    try:
        eval_log_dir = Path('eval-log')
        eval_log_dir.mkdir(parents=True, exist_ok=True)
        with open(eval_log_dir / 'db-id-resolution.json', 'w', encoding='utf-8') as f:
            json.dump({'tool': 'verify_notion_schema', 'source': db_id_source, 'database_id': database_id}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    if args.mode not in ('skip-warn', 'overwrite', 'fail-stop'):
        print(f'invalid --on-conflict: {args.mode}', file=sys.stderr)
        return 2

    from notion_http import get_database, NotionHttpError
    try:
        db = get_database(database_id)
    except NotionHttpError as e:
        print(f'[verify_notion_schema] {e}', file=sys.stderr)
        return 44 if e.status == 401 else 1

    expected_names = set(schema['properties'].keys())
    conflicts = []
    for name, spec in schema['properties'].items():
        actual = db.get('properties', {}).get(name)
        r = classify_conflict({'name': name, 'spec': spec}, actual)
        if r['kind'] != 'ok':
            conflicts.append({'name': name, **r})
    conflicts.extend(classify_extras(expected_names, db.get('properties', {})))

    out_path = args.out_path or os.path.abspath('eval-log/notion-conflicts.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    by_kind = {}
    for c in conflicts:
        by_kind[c['kind']] = by_kind.get(c['kind'], 0) + 1
    report = {
        'database_id': database_id,
        'database_title': ''.join(t.get('plain_text', '') for t in db.get('title', [])),
        'mode': args.mode,
        'checked_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'summary': {'total': len(conflicts), 'by_kind': by_kind},
        'conflicts': conflicts,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'wrote {out_path} ({len(conflicts)} entries, mode={args.mode})')

    blocking = [c for c in conflicts if c['kind'] not in ('missing_optional', 'extra')]
    if args.mode == 'fail-stop' and len(blocking) > 0:
        print(f'fail-stop: {len(blocking)} blocking conflicts', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
