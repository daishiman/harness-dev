#!/usr/bin/env python3
"""intake.json と blocks.json を入力に Notion DB へページを投稿する。"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
with open(SCRIPT_DIR / 'notion_limits.json', 'r', encoding='utf-8') as f:
    _LIMITS = json.load(f)
MAX_RT = _LIMITS['MAX_RT']


def rt(s):
    return [{'type': 'text', 'text': {'content': str(s or '')[:MAX_RT]}}]


def axis_text(v):
    if v is None:
        return ''
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and isinstance(v.get('answer'), str):
        return v['answer']
    return ''


MAX_TRUE_PROBLEM_LEN = 200
MAX_TITLE_JA_LEN = 30


def truncate(s, n):
    s = str(s or '')
    return s if len(s) <= n else s[: max(0, n - 1)] + '…'


def derive_ja_title(intake):
    """日本語タイトルを優先順位に従って導出。見つからなければ None。"""
    meta = intake.get('meta') or {}
    ndp = intake.get('notion_db_properties') or {}
    # 1) meta.skill_title_ja (新規正式フィールド)
    cand = meta.get('skill_title_ja')
    if cand and str(cand).strip():
        return str(cand).strip()[:MAX_TITLE_JA_LEN]
    # 2) notion_db_properties.名前 が既に日本語の場合
    name = ndp.get('名前')
    if name and isinstance(name, str) and any(ord(c) > 127 for c in name):
        return name.strip()[:MAX_TITLE_JA_LEN]
    # 3) top-level skill_title_ja
    cand = intake.get('skill_title_ja')
    if cand and str(cand).strip():
        return str(cand).strip()[:MAX_TITLE_JA_LEN]
    # 4) purpose.verb_object から自動生成 (末尾「する」「したい」「。」を削り 30 字)
    purpose = intake.get('purpose') or {}
    vo = purpose.get('verb_object') or purpose.get('true_purpose') or ''
    if vo:
        title = str(vo).strip().rstrip('。').rstrip('.')
        for suffix in ('したい', 'します', 'する'):
            if title.endswith(suffix):
                title = title[: -len(suffix)]
                break
        title = title.strip()
        if title:
            return title[:MAX_TITLE_JA_LEN]
    return None


def build_properties(intake, args):
    """Notion へ送る DB プロパティ集合。

    SSOT: render_notion_page.project_db_properties を唯一の projection 経路として再利用する。
    これにより「render が出すプロパティ集合 = publish が送る集合 = notion-db-schema.json の定義」
    が構造的に一致する (三系統分裂の封じ込め)。値の正本は intake (= context) の
    notion_db_properties (intake-final-schema.json#/properties/notion_db_properties)。

    render と同経路を通すため、ここでは context をそのまま渡す。derive_ja_title 等の
    旧フォールバックは notion_db_properties.名前 が未設定の場合のみ補完する。
    """
    from render_notion_page import project_db_properties

    ndp = intake.get('notion_db_properties')
    if not isinstance(ndp, dict):
        ndp = {}
    # 名前が空なら日本語タイトル導出 → skill_name_hint へフォールバック (空 title 禁止)。
    if not str(ndp.get('名前') or '').strip():
        ndp = dict(ndp)
        ndp['名前'] = (
            derive_ja_title(intake)
            or (intake.get('meta', {}) or {}).get('skill_name_hint')
            or intake.get('skill_name_hint')
            or 'untitled'
        )
        intake = dict(intake)
        intake['notion_db_properties'] = ndp
    # 公開先 DB の live スキーマを取得し、実 DB に存在する列のみ実型で projection する
    # (canonical notion-db-schema.json とのドリフトを非破壊で吸収)。取得不能 (offline /
    # test / token 不在) 時は None フォールバックで従来の固定集合を送る。
    db_schema = _fetch_db_schema(getattr(args, 'database_id', None))
    return project_db_properties(intake, db_schema)


def _fetch_db_schema(database_id):
    """公開先 DB の {property_name: notion_type} を返す。取得不能なら None。"""
    if not database_id:
        return None
    try:
        from notion_http import get_database
        info = get_database(database_id)
        props = info.get('properties') or {}
        return {name: (pr or {}).get('type') for name, pr in props.items()}
    except Exception as e:
        print(f'[publish_notion_page] live DB schema fetch skipped ({e}); '
              'falling back to static projection', file=sys.stderr)
        return None


def _rt_block(kind, text):
    return {'object': 'block', 'type': kind, kind: {'rich_text': rt(text)}}


def _heading2(text):
    return {'object': 'block', 'type': 'heading_2', 'heading_2': {'rich_text': rt(text)}}


def _toggle(label, child_texts):
    children = [_rt_block('paragraph', t) for t in child_texts if str(t or '').strip()]
    return {
        'object': 'block',
        'type': 'toggle',
        'toggle': {'rich_text': rt(label), 'children': children},
    }


def build_extra_body_blocks(intake, args):
    """DB から落とした 12 項目を本文 children として返す (publish 時に先頭付加)。"""
    axes = intake.get('five_axes') or intake.get('5_axes') or {}
    out = [_heading2('メタ情報 (DB プロパティ補完)')]

    def add_kv(label, value):
        s = value if isinstance(value, str) else (json.dumps(value, ensure_ascii=False) if value is not None else '')
        if s.strip():
            out.append(_rt_block('paragraph', f'{label}: {s}'))

    add_kv('出力先', axis_text(axes.get('output_target')) or axis_text(axes.get('output_destination')))
    add_kv('情報源', axis_text(axes.get('info_source')))
    add_kv('共有相手', axis_text(axes.get('share_target')))

    if isinstance(intake.get('viz_count'), (int, float)) and not isinstance(intake.get('viz_count'), bool):
        add_kv('図解枚数', str(intake['viz_count']))
    if isinstance(intake.get('value_score'), (int, float)) and not isinstance(intake.get('value_score'), bool):
        add_kv('価値実現スコア', str(intake['value_score']))
    owner = intake.get('owner')
    if owner:
        add_kv('担当者', owner if isinstance(owner, str) else json.dumps(owner, ensure_ascii=False))
    updated = intake.get('updated_at') or intake.get('updated')
    if updated:
        add_kv('更新日時', str(updated))

    up = intake.get('user_profile')
    if up:
        text = up if isinstance(up, str) else json.dumps(up, ensure_ascii=False)
        out.append(_toggle('ユーザープロファイル', [text]))
    oq = intake.get('open_questions')
    if isinstance(oq, list) and len(oq) > 0:
        out.append(_toggle('未解決事項', [f'- {q}' for q in oq]))
    integs = intake.get('integrations')
    if isinstance(integs, list) and len(integs) > 0:
        out.append(_toggle('外部連携', [', '.join(str(n) for n in integs)]))

    if len(out) <= 1:
        return []
    return out


def _read_existing_page_id(result_path):
    """notion-publish-result.json から既存 page_id を読む。無ければ None (= 新規作成)。"""
    if not result_path:
        return None
    p = Path(result_path)
    if not p.exists():
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pid = data.get('page_id') or data.get('id')
        return _extract_page_id_from_url(pid) if pid else None
    except Exception as e:
        raise ValueError(f'notion publish result is unreadable: {result_path}: {e}') from e


def _extract_page_id_from_url(url):
    """Notion ページ URL / 任意文字列から page_id を抽出し UUID 形式へ正規化。無ければ None。
    素人ユーザーが URL を貼った場合でも出力先を確定できるようにする入口。

    Notion URL は `…/Title-Words-{32hex}?query` 形式で、page_id は **最後のダッシュ以降の
    末尾トークン (32hex)**。ダッシュを全除去するとスラグ末尾の hex 文字 (例 'Pag*e*') が
    混入し境界がズレるため、クエリ除去 → 末尾パスセグメント → 末尾トークンの順で厳密抽出する。"""
    if not url:
        return None
    parsed = urlparse(str(url))
    query = parse_qs(parsed.query)
    # app.notion.com/p/<db_or_view>?...&p=<page_id>&... の共有 URL は query p が
    # 実ページ ID。path 側を先に読むと DB/view 側 ID を誤って target にしてしまう。
    for key in ("p", "page_id"):
        for candidate in query.get(key, []):
            compact = re.sub(r'[^0-9a-fA-F]', '', str(candidate)).lower()
            if len(compact) == 32:
                return f'{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:32]}'
    path = parsed.path or str(url).split('?')[0].split('#')[0]
    seg = path.rstrip('/').split('/')[-1]
    # 1) ダッシュ付き UUID 形式 (8-4-4-4-12) をそのまま受理
    m = re.search(
        r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', seg)
    if m:
        return m.group(0).lower()
    # 2) スラグ-id 形式: 最後のダッシュ以降の末尾トークンが 32hex なら採用
    last = seg.split('-')[-1]
    if re.fullmatch(r'[0-9a-fA-F]{32}', last):
        h = last.lower()
        return f'{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}'
    return None


def _canonical_id(value):
    s = re.sub(r'[^0-9a-fA-F]', '', str(value or '')).lower()
    return s if len(s) == 32 else ''


def resolve_target_page_id(args):
    """出力先 page_id を単一経路で解決し (page_id, source) を返す。
    優先順位 (SSOT): 明示 --page-id > --page-url 抽出 > --result-out ファイル > None(create)。
    「ユーザーが今指定した出力先」を最優先の真実とし、揮発的な result ファイル依存を上書きする。
    これが島1 (出力先指定インターフェース欠如) の封鎖点。"""
    explicit = getattr(args, 'page_id', None)
    if explicit and str(explicit).strip():
        pid = _extract_page_id_from_url(explicit)
        # 明示指定が有効な page_id に正規化できなければ invalid を返し main で fail-closed (exit 2)。
        # 生文字列を素通しすると不正 ID のまま Notion API に渡り「指定ページ 100% 出力」保証が壊れる。
        return (pid, 'arg') if pid else (None, 'arg_invalid')
    url = getattr(args, 'page_url', None)
    if url and str(url).strip():
        pid = _extract_page_id_from_url(url)
        return (pid, 'url') if pid else (None, 'url_invalid')
    try:
        pid = _read_existing_page_id(getattr(args, 'result_out', None))
    except ValueError:
        return None, 'result_invalid'
    if pid:
        return pid, 'result_file'
    return None, None


def _write_result(result_path, page_id, page_url, mode, database_id):
    """page_id を idempotency-key として永続化。後続 gate が参照する確定スキーマ。"""
    if not result_path:
        return
    import time
    payload = {
        'page_id': page_id,
        'url': page_url,
        'database_id': database_id,
        'mode': mode,
        'published_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }
    Path(result_path).parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write('\n')


def _list_child_ids(notion_fetch, page_id):
    """既存ページの直下 children ID をページング取得する。"""
    cursor = None
    block_ids = []
    while True:
        path = f'/blocks/{page_id}/children?page_size=100'
        if cursor:
            path += f'&start_cursor={cursor}'
        res = notion_fetch(path, method='GET')
        for b in res.get('results', []):
            if b.get('id'):
                block_ids.append(b['id'])
        if res.get('has_more') and res.get('next_cursor'):
            cursor = res['next_cursor']
        else:
            break
    return block_ids


def _archive_children(notion_fetch, block_ids):
    """指定済み children を archive する。"""
    for bid in block_ids:
        notion_fetch(f'/blocks/{bid}', method='DELETE')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intake', required=False)
    parser.add_argument('--blocks', required=False)
    parser.add_argument('--database-id', dest='database_id')
    parser.add_argument('--result-out', dest='result_out',
                        help='page_id を冪等に保存/参照する notion-publish-result.json のパス')
    parser.add_argument('--page-id', dest='page_id',
                        help='更新対象の Notion ページ ID を明示指定 (最優先。指定ページへの確実な出力)')
    parser.add_argument('--page-url', dest='page_url',
                        help='更新対象の Notion ページ URL (page_id を自動抽出。--page-id 未指定時の代替入口)')
    parser.add_argument('--require-update', dest='require_update', action='store_true',
                        help='revise 用: page_id 解決不能時に create せず exit 51 (同一ページ更新の保証)')
    parser.add_argument('--allow-create', dest='allow_create', action='store_true',
                        help='明示された初回作成だけ許可する。既定は create 禁止')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true')
    args = parser.parse_args()

    if not args.intake:
        print('--intake is required', file=sys.stderr)
        return 2
    if not args.blocks:
        print('--blocks is required (empty body publication is forbidden)', file=sys.stderr)
        return 2
    try:
        with open(args.blocks, 'r', encoding='utf-8') as f:
            blocks = json.load(f)
    except Exception as e:
        print(f'--blocks read error: {e}', file=sys.stderr)
        return 2
    block_children = blocks.get('children') if isinstance(blocks, dict) and 'children' in blocks else blocks
    if not isinstance(block_children, list) or len(block_children) == 0:
        print('--blocks must contain a non-empty children array', file=sys.stderr)
        return 2

    # ===== DB ID 解決の単一経路 (SSOT) =====
    # 解決順: --database-id (明示最優先) → notion_config.get_db_id('hearing-sheet')。
    # notion_config が env (INTAKE_NOTION_DATABASE_ID) と <repo-root>/.notion-config.json を
    # 一元解決する唯一の経路。import 失敗は silent にせず可視化して fail-closed (exit 2)。
    # 旧 4 段 fallback / schema.database_id_default は廃止 (分裂源だったため)。
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import notion_config as _nc
    except Exception as e:
        print(f'[publish_notion_page] notion_config import failed: {e}. '
              f'scripts/notion_config.py (本 plugin に同梱) が存在し import 可能か確認してください。',
              file=sys.stderr)
        return 2

    if args.database_id:
        database_id, db_id_source = args.database_id, 'arg'
    else:
        database_id = _nc.get_db_id('hearing-sheet')
        db_id_source = 'notion_config' if database_id else None
    if not database_id:
        print('database_id is required (--database-id, or INTAKE_NOTION_DATABASE_ID / '
              '<repo-root>/.notion-config.json#databases.hearing-sheet via notion_config). '
              'See references/notion-per-repo-setup.md', file=sys.stderr)
        return 2
    try:
        eval_log_dir = Path('eval-log')
        eval_log_dir.mkdir(parents=True, exist_ok=True)
        with open(eval_log_dir / 'db-id-resolution.json', 'w', encoding='utf-8') as f:
            json.dump({'tool': 'publish_notion_page', 'source': db_id_source, 'database_id': database_id}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # silent 禁止: 書込失敗は stderr へ (記録欠落を可視化)。
        print(f'[publish_notion_page] db-id-resolution.json write failed: {e}', file=sys.stderr)

    with open(args.intake, 'r', encoding='utf-8') as f:
        intake = json.load(f)
    extra_blocks = build_extra_body_blocks(intake, args)
    body = {
        'parent': {'database_id': database_id},
        'properties': build_properties(intake, args),
        'children': extra_blocks + block_children,
    }

    # 出力先 page_id を単一経路で解決 (冪等 upsert)。
    # 優先順位: 明示 --page-id > --page-url 抽出 > --result-out ファイル > None(create)。
    existing_page_id, page_id_source = resolve_target_page_id(args)
    # 明示 --page-id / --page-url が不正形式なら fail-closed (silent create を禁止し誤 ID を API に渡さない)。
    if page_id_source in ('arg_invalid', 'url_invalid', 'result_invalid'):
        print(f'指定された page 識別子が不正です (source={page_id_source})。'
              '有効な Notion page_id (32hex / ダッシュ付き UUID) または page URL を指定してください。'
              '既存 notion-publish-result.json が破損している場合は修復するか --page-id/--page-url を明示してください。',
              file=sys.stderr)
        return 2
    mode = 'update' if existing_page_id else 'create'

    # revise (--require-update): page_id を解決できないなら create せず停止 (同一ページ更新の保証)。
    # 文書契約「新規ページを作成しない」を実装で強制し、別ページ量産を構造的に封鎖する。
    if args.require_update and not existing_page_id:
        print('--require-update (revise) but no target page_id resolved '
              '(--page-id / --page-url / 既存 --result-out のいずれも無し)。'
              'create を禁止します (同一ページ更新の保証)。', file=sys.stderr)
        return 51
    if not existing_page_id and not args.allow_create:
        print('target page_id was not resolved and create is disabled by default. '
              'Specify --page-id/--page-url for update, or pass --allow-create for an explicit first create.',
              file=sys.stderr)
        return 51

    if args.dry_run:
        out = {
            'dry_run': True,
            'mode': mode,
            'page_id': existing_page_id,
            'page_id_source': page_id_source,
            'parent': body['parent'],
            'prop_count': len(body['properties']),
            'children_count': len(body['children']),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    # 実投稿: notion_http を遅延 import (dry-run 時は keychain アクセス回避)
    from notion_http import notion_fetch, NotionHttpError
    MAX_FIRST = _LIMITS.get('MAX_BLOCKS_PER_APPEND', 100)
    all_children = body['children']
    try:
        if existing_page_id:
            # ===== update mode: page_id 不変で PATCH (再公開で新規ページを増やさない) =====
            page_id = existing_page_id
            current = notion_fetch(f'/pages/{page_id}', method='GET')
            parent = current.get('parent') or {}
            current_db_id = parent.get('database_id') if parent.get('type') == 'database_id' else None
            if current_db_id and _canonical_id(current_db_id) != _canonical_id(database_id):
                print('[publish_notion_page] target page belongs to a different database '
                      f'(page.database_id={current_db_id}, expected={database_id}). '
                      '指定 DB と page_id の組み合わせを確認してください。',
                      file=sys.stderr)
                return 52
            old_child_ids = _list_child_ids(notion_fetch, page_id)
            # 1) プロパティ更新
            notion_fetch(f'/pages/{page_id}', method='PATCH', body={'properties': body['properties']})
            # 2) 新 children を全投入 → 旧 children を archive。
            #    先に削除すると API failure/rate limit 時に空ページを残すため、
            #    旧 children は新規投入が完了してから退避する。
            for i in range(0, len(all_children), MAX_FIRST):
                chunk = all_children[i:i + MAX_FIRST]
                notion_fetch(f'/blocks/{page_id}/children', method='PATCH', body={'children': chunk})
            _archive_children(notion_fetch, old_child_ids)
            res = notion_fetch(f'/pages/{page_id}', method='GET')
            page_url = res.get('url')
            out = {'id': page_id, 'url': page_url, 'mode': 'update',
                   'last_edited_time': res.get('last_edited_time')}
        else:
            # ===== create mode: POST /pages → page_id を result へ書き戻し永続化 =====
            body['children'] = all_children[:MAX_FIRST]
            remaining = all_children[MAX_FIRST:]
            res = notion_fetch('/pages', method='POST', body=body)
            page_id = res.get('id')
            page_url = res.get('url')
            # POST 成功直後に page_id を即時永続化 (partial-create 窓の封鎖):
            # 後続 children PATCH が失敗しても成功痕跡が残り、再実行は update mode で
            # 同一ページへ収束する (再 create によるページ重複を構造的に防ぐ)。
            try:
                _write_result(args.result_out, page_id, page_url, 'create', database_id)
            except Exception as e:
                print(f'[publish_notion_page] result write failed ({args.result_out}): {e}', file=sys.stderr)
                return 2
            for i in range(0, len(remaining), MAX_FIRST):
                chunk = remaining[i:i + MAX_FIRST]
                notion_fetch(f'/blocks/{page_id}/children', method='PATCH', body={'children': chunk})
            out = {'id': page_id, 'url': page_url, 'mode': 'create',
                   'created_time': res.get('created_time')}
        # page_id を idempotency-key として永続化 (次回 update mode の入力)。
        try:
            _write_result(args.result_out, page_id, page_url, out.get('mode'), database_id)
        except Exception as e:
            print(f'[publish_notion_page] result write failed ({args.result_out}): {e}', file=sys.stderr)
            return 2
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except NotionHttpError as e:
        print(f'[publish_notion_page] {e}', file=sys.stderr)
        return 44 if e.status == 401 else 1


if __name__ == '__main__':
    sys.exit(main())
