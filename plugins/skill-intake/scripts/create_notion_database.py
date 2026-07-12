#!/usr/bin/env python3
"""Create a Notion DB under a parent page, or sync an existing DB to the expected schema.

Usage:
  python3 create_notion_database.py --mode=create [--parent-page <PAGE_ID>|--parent-page-url <URL>] [--title "skillインタビュー"] [--dry-run]
  python3 create_notion_database.py --mode=sync --database-id <DB_ID> [--dry-run]

Exit codes: 0=OK, 1=API error, 2=INPUT_ERROR, 44=KEYCHAIN_ERROR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import notion_config
from notion_http import NotionHttpError, notion_fetch

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / 'references/notion-db-schema.json'
)


def build_property_def(spec: dict[str, Any]) -> dict[str, Any]:
    t = spec['type']
    if t == 'title':
        return {'title': {}}
    if t == 'rich_text':
        return {'rich_text': {}}
    if t == 'number':
        return {'number': {'format': 'number'}}
    if t == 'checkbox':
        return {'checkbox': {}}
    if t == 'url':
        return {'url': {}}
    if t == 'people':
        return {'people': {}}
    if t == 'created_time':
        return {'created_time': {}}
    if t == 'last_edited_time':
        return {'last_edited_time': {}}
    if t == 'select':
        return {'select': {'options': [{'name': n} for n in spec.get('options', [])]}}
    if t == 'multi_select':
        return {'multi_select': {'options': [{'name': n} for n in spec.get('options', [])]}}
    raise ValueError(f'unsupported type: {t}')


def build_properties(schema: dict[str, Any]) -> dict[str, Any]:
    return {name: build_property_def(spec) for name, spec in schema['properties'].items()}


def parse_args(argv: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith('--mode='):
            out['mode'] = a[len('--mode='):]
        elif a == '--mode':
            i += 1
            out['mode'] = argv[i]
        elif a == '--parent-page':
            i += 1
            out['parentPage'] = argv[i]
        elif a == '--parent-page-url':
            i += 1
            out['parentPageUrl'] = argv[i]
        elif a == '--database-id':
            i += 1
            out['databaseId'] = argv[i]
        elif a == '--title':
            i += 1
            out['title'] = argv[i]
        elif a == '--dry-run':
            out['dryRun'] = True
        i += 1
    return out


def resolve_parent_page(args: dict[str, Any]) -> str | None:
    return (
        notion_config.canonical_notion_id(args.get('parentPage'))
        or notion_config.canonical_notion_id(args.get('parentPageUrl'))
        or notion_config.get_parent_page_id()
    )


def configured_db_ids() -> set[str]:
    """config の databases.*.db_id 集合 (canonical UUID)。親ページ誤設定ガード用。"""
    cfg = notion_config.load_config() or {}
    ids: set[str] = set()
    for entry in (cfg.get('databases') or {}).values():
        if not isinstance(entry, dict):
            continue
        canon = notion_config.canonical_notion_id(entry.get('db_id'))
        if canon:
            ids.add(canon)
    return ids


def create_db(parent_page: str | None, title: str | None, schema: dict[str, Any], dry_run: bool) -> dict[str, Any] | None:
    # fail-closed guard: 親ページ ID が空/未設定、または databases.*.db_id と同一
    # (親が DB を指す誤設定) の場合は DB を作成しない。
    if not parent_page or parent_page in configured_db_ids():
        sys.stderr.write(
            'DB新規作成には親“ページ”IDが必要です。.notion-config.json の '
            'parent_page.page_id にご自身の Notion ページ ID を設定してください '
            '(--parent-page / --parent-page-url / env INTAKE_NOTION_PARENT_PAGE_ID でも指定可。'
            'databases.*.db_id と同一の ID は DB を指すため親ページとして使えません)\n'
        )
        sys.exit(2)
    body = {
        'parent': {'type': 'page_id', 'page_id': parent_page},
        'title': [{'type': 'text', 'text': {'content': title or 'skillインタビュー'}}],
        'properties': build_properties(schema),
    }
    if dry_run:
        print(json.dumps({
            'tool': 'create_notion_database',
            'mode': 'create',
            'dry_run': True,
            'parent_page_id': parent_page,
            'title': title or 'skillインタビュー',
            'property_count': len(body['properties']),
            'body': body,
        }, ensure_ascii=False, indent=2))
        return None
    res = notion_fetch('/databases', method='POST', body=body)
    print(f"created database id={res.get('id')}")
    print(f"url={res.get('url')}")
    return res


def sync_db(database_id: str | None, schema: dict[str, Any], dry_run: bool) -> Any:
    if not database_id:
        sys.stderr.write('--database-id is required for --mode=sync\n')
        sys.exit(2)
    current = notion_fetch(f'/databases/{database_id}')
    desired = build_properties(schema)
    patch: dict[str, Any] = {}
    expected_title_name = next(
        (n for n, s in schema['properties'].items() if s['type'] == 'title'),
        None,
    )
    current_title_name = next(
        (n for n, p in current.get('properties', {}).items() if p.get('type') == 'title'),
        None,
    )
    if expected_title_name and current_title_name and expected_title_name != current_title_name:
        patch[current_title_name] = {'name': expected_title_name}
        print(f'title rename: "{current_title_name}" -> "{expected_title_name}"')
    for name, def_ in desired.items():
        if name == expected_title_name and current_title_name:
            continue
        cur = current.get('properties', {}).get(name)
        spec_type = schema['properties'][name]['type']
        if not cur or cur.get('type') != spec_type:
            patch[name] = def_
        elif spec_type in ('select', 'multi_select'):
            cur_opts = ','.join(sorted(o.get('name', '') for o in cur.get(cur['type'], {}).get('options', [])))
            exp_opts = ','.join(sorted(schema['properties'][name].get('options', [])))
            if cur_opts != exp_opts:
                patch[name] = def_
    if not patch:
        print('no drift; nothing to sync')
        return None
    print(f"sync plan: {', '.join(patch.keys())}")
    if dry_run:
        print('dry-run: no PATCH issued')
        return None
    res = notion_fetch(f'/databases/{database_id}', method='PATCH', body={'properties': patch})
    print(f'synced {len(patch)} properties')
    return res


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    try:
        if args.get('mode') == 'create':
            create_db(resolve_parent_page(args), args.get('title'), schema, bool(args.get('dryRun')))
        elif args.get('mode') == 'sync':
            sync_db(args.get('databaseId'), schema, bool(args.get('dryRun')))
        else:
            sys.stderr.write('--mode=create|sync required\n')
            return 2
        return 0
    except NotionHttpError as e:
        sys.stderr.write(f'[create_notion_database] {e}\n')
        return 44 if getattr(e, 'status', None) == 401 else 1
    except Exception as e:
        sys.stderr.write(f'[create_notion_database] {e}\n')
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
