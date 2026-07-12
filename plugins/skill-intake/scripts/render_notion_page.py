#!/usr/bin/env python3
"""intake-final-context.json から Notion ページペイロード（properties + children）を生成する v2 レンダラ。

責務:
  - DB プロパティは context.notion_db_properties をそのまま Notion 型に projection する
  - 本文 children は intake-final-template.md.tmpl の §0〜§11 構造を context から直接組み立てる
    （Markdown 経由ではなく context オブジェクトを正本として参照）

正本:
  - 構造: references/intake-final-schema.json
  - テンプレ: references/intake-final-template.md.tmpl
  - DB スキーマ: references/notion-db-schema.json (v2)

v1 ブリッジ (section-templates.json / SECTION_DATA_PATHS) は廃止済み。
render_v2_adapter.py は v2 経路の section_canonical_map iterator として継続使用 (dry_render_notion.py から import)。
"""

import json
import os
import sys
from pathlib import Path

import _jsonschema_compat as jsonschema

SCRIPT_DIR = Path(__file__).resolve().parent
with open(SCRIPT_DIR / 'notion_limits.json', 'r', encoding='utf-8') as f:
    _LIMITS = json.load(f)
MAX_RT = _LIMITS['MAX_RT']

SCHEMA_PATH = (
    SCRIPT_DIR.parent
    / 'references'
    / 'intake-final-schema.json'
)


def _load_schema():
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


# ===== Notion block primitives =====

def rt(text):
    s = '' if text is None else str(text)
    return [{'type': 'text', 'text': {'content': s[:MAX_RT]}}]


def heading(level, text):
    lv = max(1, min(level, 3))
    key = f'heading_{lv}'
    return {'object': 'block', 'type': key, key: {'rich_text': rt(text)}}


def paragraph(text):
    return {'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': rt(text)}}


def bullet(text):
    return {'object': 'block', 'type': 'bulleted_list_item', 'bulleted_list_item': {'rich_text': rt(text)}}


def numbered(text):
    return {'object': 'block', 'type': 'numbered_list_item', 'numbered_list_item': {'rich_text': rt(text)}}


def code(text, language=None):
    return {'object': 'block', 'type': 'code', 'code': {'rich_text': rt(text), 'language': language or 'plain text'}}


def divider():
    return {'object': 'block', 'type': 'divider', 'divider': {}}


def callout(text, emoji=None):
    block = {'rich_text': rt(text)}
    if emoji:
        block['icon'] = {'type': 'emoji', 'emoji': emoji}
    return {'object': 'block', 'type': 'callout', 'callout': block}


def quote(text):
    return {'object': 'block', 'type': 'quote', 'quote': {'rich_text': rt(text)}}


# ===== DB properties projection =====

def _select(value):
    return {'select': {'name': str(value)}} if value is not None else {'select': None}


# canonical status 語彙 (intake-final-schema ステータス enum) → Notion 標準 status option。
# status 型は select と違い未知 option を自動作成しないため、実 DB の標準 3 態へ写像する。
_STATUS_CANON_TO_STD = {
    '下書き': '未着手',
    'レビュー中': '進行中',
    'Gate A承認済み': '進行中',
    '引き渡し済み': '進行中',
    '構築済み': '完了',
    'アーカイブ': '完了',
}


def _status(value):
    if value is None:
        return {'status': None}
    name = _STATUS_CANON_TO_STD.get(str(value), str(value))
    return {'status': {'name': name}}


def _multi(values):
    return {'multi_select': [{'name': str(v)} for v in (values or [])]}


def _rich(text):
    return {'rich_text': rt(text)}


def _title(text):
    return {'title': rt(text)}


def _date(value):
    return {'date': {'start': value}} if value else {'date': None}


def _url(value):
    return {'url': value or None}


# notion-db-schema.json (v2) 準拠の固定プロパティ projection 仕様。
# (name, canonical_type, notion_db_properties からの取り出し key)。
_DB_PROP_SPEC = [
    ('名前', 'title', '名前'),
    ('ステータス', 'select', 'ステータス'),
    ('パターン', 'select', 'パターン'),
    ('ワークフロー', 'select', 'ワークフロー'),
    ('深度', 'select', '深度'),
    ('熟練度', 'select', '熟練度'),
    ('テーマ抽出', 'select', 'テーマ抽出'),
    ('責務境界', 'select', '責務境界'),
    ('配信タイミング', 'select', '配信タイミング'),
    ('出力先', 'multi_select', '出力先'),
    ('共有相手', 'multi_select', '共有相手'),
    ('引き渡しモード', 'select', '引き渡しモード'),
    ('真の課題', 'rich_text', '真の課題'),
    ('ナレッジ資産タグ', 'multi_select', 'ナレッジ資産タグ'),
    ('実行環境', 'select', '実行環境'),
]
# 送信不可 (read-only) の Notion プロパティ型。
_READONLY_TYPES = {'created_time', 'last_edited_time', 'formula', 'rollup',
                   'created_by', 'last_edited_by', 'unique_id'}


def _project_value(ntype, value):
    if ntype == 'title':
        return _title(value if value is not None else '')
    if ntype == 'rich_text':
        return _rich(value if value is not None else '')
    if ntype == 'status':
        return _status(value)
    if ntype == 'multi_select':
        return _multi(value)
    if ntype == 'date':
        return _date(value)
    # select 既定 (未知型も select へ寄せる: 従来挙動を保つ)
    return _select(value)


def project_db_properties(ctx, db_schema=None):
    """context.notion_db_properties → Notion DB properties payload。

    db_schema (name -> notion_type の実 DB スキーマ) が渡された場合、実 DB に存在する
    プロパティのみを、その実型に合わせて projection する。これにより canonical
    notion-db-schema.json と実際の公開先 DB とのドリフト (例: ステータス が status 型 /
    ナレッジ資産タグ・実行環境 が非存在) を publish 時に非破壊で吸収する。
    db_schema=None のときは notion-db-schema.json (v2) 準拠の固定集合を返す
    (render / quality_gate の後方互換: キー・型・順序を従来と完全一致で維持)。
    """
    p = ctx.get('notion_db_properties') or {}
    out = {}
    for name, canonical_type, src_key in _DB_PROP_SPEC:
        default = '' if canonical_type in ('title', 'rich_text') else None
        value = p.get(src_key, default)
        if db_schema is None:
            out[name] = _project_value(canonical_type, value)
            continue
        # 実 DB スキーマ適応: 非存在列は送らない / read-only 型は送らない / 実型へ coerce。
        if name not in db_schema:
            continue
        actual_type = db_schema[name] or canonical_type
        if actual_type in _READONLY_TYPES:
            continue
        out[name] = _project_value(actual_type, value)
    return out


# ===== Section diagram helper =====

def _render_section_diagrams(ctx, blocks, section_key):
    """section_diagrams[section_key] を mermaid または image ブロックとして描画。
    存在しない章 (§0, §5) はスキップ。§5 は _render_figures が別経路で処理。"""
    sd = ctx.get('section_diagrams', {})
    diagrams = sd.get(section_key, [])
    if not diagrams:
        return
    for d in diagrams:
        blocks.append(heading(3, f"【{d.get('kind', 'diagram')}】 {d.get('title', '')}"))
        if d.get('one_liner'):
            blocks.append(paragraph(f"言いたい一言: {d['one_liner']}"))
        if d.get('mermaid_source'):
            blocks.append(code(d['mermaid_source'], 'mermaid'))
        elif d.get('image_url'):
            blocks.append({'object': 'block', 'type': 'image',
                           'image': {'type': 'external', 'external': {'url': d['image_url']}}})
        if d.get('legend'):
            blocks.append(paragraph(f"凡例: {d['legend']}"))


# ===== Section renderers (§0〜§11) =====

def _render_meta(ctx, blocks):
    m = ctx.get('meta', {})
    blocks.append(heading(1, f"{m.get('skill_name_hint', 'skill')} — ヒアリング正本（完全版）"))
    meta_lines = [
        f"生成日時: {m.get('generated_at', '')}",
        f"パターン: {m.get('pattern_code')}（{m.get('pattern_label', '')}）／Workflow: {m.get('workflow_pattern_code', '')}（{m.get('workflow_pattern_label', '')}）",
        f"深度: {m.get('depth')}（{m.get('depth_minutes', '?')}分相当）",
        f"語彙: {m.get('vocabulary_tier')}",
        f"状態: {m.get('status')}",
        f"value_realized_score: {m.get('value_realized_score')} / 100",
    ]
    for l in meta_lines:
        blocks.append(bullet(l))
    blocks.append(divider())


def _render_executive(ctx, blocks):
    blocks.append(heading(2, '0. エグゼクティブサマリ'))
    es = ctx.get('executive_summary', {})
    blocks.append(callout(f"真の目的: 「{es.get('true_purpose', '')}」", '🎯'))
    if es.get('purpose_narrative'):
        blocks.append(paragraph(es['purpose_narrative']))
    if es.get('design_choices'):
        blocks.append(paragraph(f"設計選択: {es['design_choices']}"))
    if es.get('handoff_mode'):
        blocks.append(paragraph(f"引き渡しモード: {es['handoff_mode']}（{es.get('handoff_note', '')}）"))
    blocks.append(divider())


def _render_assumption(ctx, blocks):
    a = ctx.get('assumption', {})
    blocks.append(heading(2, '1. Phase: assumption-challenger（前提逆転）'))
    blocks.append(heading(3, '1.1 表層リクエスト'))
    blocks.append(quote(a.get('surface_request', '')))
    blocks.append(heading(3, '1.2 深層候補'))
    for c in a.get('candidates', []):
        prefix = '✅ ' if c.get('adopted') else ''
        blocks.append(bullet(f"{prefix}{c.get('id')}: {c.get('label')}"))
    blocks.append(heading(3, '1.3 確定した深層課題'))
    blocks.append(paragraph(a.get('deep_problem', '')))
    if a.get('time_freed_intent'):
        blocks.append(heading(3, '1.4 浮いた時間の使い道'))
        blocks.append(paragraph(a['time_freed_intent']))
    if a.get('blind_spots'):
        blocks.append(heading(3, '1.5 ブラインドスポット'))
        for bs in a['blind_spots']:
            blocks.append(bullet(bs))
    _render_section_diagrams(ctx, blocks, '1_assumption_challenger')
    blocks.append(divider())


def _render_profile(ctx, blocks):
    p = ctx.get('profile', {})
    blocks.append(heading(2, '2. Phase: user-profiler（ユーザー像）'))
    for d in p.get('dimensions', []):
        blocks.append(bullet(f"{d.get('name')}: {d.get('value')} (confidence={d.get('confidence')}) — {d.get('evidence', '')}"))
    blocks.append(paragraph(f"vocabulary_tier: {p.get('vocabulary_tier', '')}"))
    if p.get('implications'):
        blocks.append(heading(3, '次フェーズへの含意'))
        for imp in p['implications']:
            blocks.append(bullet(imp))
    _render_section_diagrams(ctx, blocks, '2_user_profile')
    blocks.append(divider())


def _render_purpose(ctx, blocks):
    pu = ctx.get('purpose', {})
    blocks.append(heading(2, '3. Phase: purpose-excavator（真の目的の発掘）'))
    blocks.append(bullet(f"techniques_used: {pu.get('techniques_used_str', '')}"))
    blocks.append(bullet(f"rounds: {pu.get('rounds')} / agreement_loop_detected: {pu.get('agreement_loop_detected')}"))
    blocks.append(callout(f"真の目的: 「{pu.get('true_purpose', '')}」", '🎯'))
    if pu.get('underlying_motivation'):
        blocks.append(paragraph(f"underlying_motivation: {pu['underlying_motivation']}"))
    if pu.get('differentiation_title'):
        blocks.append(heading(3, pu['differentiation_title']))
        blocks.append(paragraph(pu.get('differentiation_text', '')))
    if pu.get('magic_wand_text'):
        blocks.append(heading(3, '浮いた時間の使い道 (Magic Wand)'))
        blocks.append(paragraph(pu['magic_wand_text']))
    if pu.get('output_priority'):
        blocks.append(heading(3, 'アウトプット優先順位'))
        for o in pu['output_priority']:
            text = f"**{o.get('text')}**" if o.get('is_top') else o.get('text', '')
            blocks.append(numbered(text))
    _render_section_diagrams(ctx, blocks, '3_purpose_excavator')
    blocks.append(divider())


def _render_options(ctx, blocks):
    o = ctx.get('options', {})
    blocks.append(heading(2, '4. Phase: option-presenter（選択肢提示と確定）'))
    for i, g in enumerate(o.get('groups', []), 1):
        blocks.append(heading(3, f"4.{i} {g.get('title', '')}"))
        for opt in g.get('options', []):
            prefix = '✅ ' if opt.get('adopted') else ''
            blocks.append(bullet(f"{prefix}{opt.get('id')} {opt.get('label')} — Pro: {opt.get('pro')} / Con: {opt.get('con')} / Weight: {opt.get('weight')}"))
    c = o.get('connectors', {})
    blocks.append(heading(3, 'コネクタ選択'))
    for k in ('input_sources', 'knowledge_assets', 'outputs', 'scheduler'):
        blocks.append(bullet(f"{k}: {c.get(k, '')}"))
    _render_section_diagrams(ctx, blocks, '4_option_presenter')
    blocks.append(divider())


def _render_figures(ctx, blocks):
    f = ctx.get('figures', {})
    blocks.append(heading(2, '5. Phase: visualizer（図解5枚）'))
    for i, fig in enumerate(f.get('entries', []), 1):
        blocks.append(heading(3, f"図{i}. {fig.get('title', '')}"))
        blocks.append(paragraph(f"言いたい一言: {fig.get('one_liner', '')}"))
        if fig.get('mermaid'):
            blocks.append(code(fig['mermaid'], 'mermaid'))
        if fig.get('legend'):
            blocks.append(paragraph(f"凡例: {fig['legend']}"))
    blocks.append(divider())


def _render_five_axes(ctx, blocks):
    fa = ctx.get('five_axes', {})
    blocks.append(heading(2, '6. 5軸サマリ（最終確定版）'))
    for row in fa.get('rows', []):
        must = '（MUST）' if row.get('must') else ''
        blocks.append(bullet(f"{row.get('name')}{must}: {row.get('content', '')} [{row.get('depth')}]"))
    pl = fa.get('pipeline', {})
    blocks.append(heading(3, 'ナレッジ抽出パイプライン'))
    for k in ('ingest', 'analysis', 'storage', 'retrieval', 'update'):
        blocks.append(bullet(f"{k}: {pl.get(k, '')}"))
    _render_section_diagrams(ctx, blocks, '6_five_axes_summary')
    blocks.append(divider())


def _render_design_decisions(ctx, blocks):
    dd = ctx.get('design_decisions', {})
    blocks.append(heading(2, '7. 設計選択サマリ'))
    for r in dd.get('rows', []):
        blocks.append(bullet(f"{r.get('axis')}: {r.get('adopted')} — {r.get('reason', '')}"))
    if dd.get('output_priority'):
        blocks.append(heading(3, 'アウトプット優先順位'))
        for o in dd['output_priority']:
            blocks.append(numbered(o))
    _render_section_diagrams(ctx, blocks, '7_design_decisions')
    blocks.append(divider())


def _render_open_questions(ctx, blocks):
    oq = ctx.get('open_questions', [])
    blocks.append(heading(2, '8. 未解決事項'))
    for q in oq:
        mark = '○' if q.get('blocking') else '×'
        blocks.append(bullet(f"[{mark}] {q.get('question')} → {q.get('defer_to', '')}"))
    _render_section_diagrams(ctx, blocks, '8_open_questions')
    blocks.append(divider())


def _render_handoff(ctx, blocks):
    h = ctx.get('handoff', {})
    blocks.append(heading(2, '9. harness-creator への申し送り'))
    blocks.append(bullet(f"recommended_mode: {h.get('recommended_mode')}"))
    blocks.append(bullet(f"skip_to_phase: {h.get('skip_to_phase')}"))
    blocks.append(bullet(f"理由: {h.get('reason', '')}"))
    if h.get('starting_note'):
        blocks.append(paragraph(h['starting_note']))
    _render_section_diagrams(ctx, blocks, '9_handoff_contract')
    blocks.append(divider())


def _render_self_update(ctx, blocks):
    su = ctx.get('self_update', {})
    blocks.append(heading(2, '10. Phase: self-updater（自己進化結果）'))
    for k in ('candidates_detected', 'candidates_applied', 'skipped_duplicates', 'value_realized_score'):
        blocks.append(bullet(f"{k}: {su.get(k)}"))
    if su.get('score_rationale'):
        blocks.append(paragraph(f"スコア根拠: {su['score_rationale']}"))
    for d in su.get('deductions', []):
        blocks.append(bullet(f"控除 -{d.get('points')}: {d.get('reason')}"))
    _render_section_diagrams(ctx, blocks, '10_self_updater')
    blocks.append(divider())


def _render_artifacts(ctx, blocks):
    a = ctx.get('artifacts', {})
    blocks.append(heading(2, f"11. 出力ファイル一覧（{a.get('base_path', '')}）"))
    for f in a.get('files', []):
        blocks.append(bullet(f"`{f.get('path')}` — {f.get('description', '')}"))
    _render_section_diagrams(ctx, blocks, '11_artifact_index')


# ===== Top-level =====

def render(ctx):
    # render-intake-final.py と同じく intake-final-schema.json で context を厳密検証する。
    # 検証失敗は jsonschema.ValidationError として上位に伝播。
    jsonschema.validate(ctx, _load_schema())
    blocks = []
    _render_meta(ctx, blocks)
    _render_executive(ctx, blocks)
    _render_assumption(ctx, blocks)
    _render_profile(ctx, blocks)
    _render_purpose(ctx, blocks)
    _render_options(ctx, blocks)
    _render_figures(ctx, blocks)
    _render_five_axes(ctx, blocks)
    _render_design_decisions(ctx, blocks)
    _render_open_questions(ctx, blocks)
    _render_handoff(ctx, blocks)
    _render_self_update(ctx, blocks)
    _render_artifacts(ctx, blocks)
    return {'properties': project_db_properties(ctx), 'children': blocks}


def main(argv):
    """render エントリ。

    呼び出し規約 (argparse 化 / 位置引数も後方互換維持):
      render_notion_page.py <ctx.json> [out.json]
      render_notion_page.py --ctx <ctx.json> --out <blocks.json> [--manifest <manifest.json>]

    pipeline は `--ctx <intake> --out <blocks> [--manifest <manifest>]` を渡す。
    `--manifest` は描画の参考入力 (アセット情報) であり、レンダ結果 (blocks) の出力先は
    必ず `--out`。manifest を blocks で上書き破壊しないことが本シグネチャの不変条件。
    """
    import argparse
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('ctx_pos', nargs='?', help='intake-final-context.json (位置引数, 後方互換)')
    parser.add_argument('out_pos', nargs='?', help='out blocks.json (位置引数, 後方互換)')
    parser.add_argument('--ctx', dest='ctx_opt')
    parser.add_argument('--out', dest='out_opt')
    parser.add_argument('--manifest', dest='manifest')
    ns = parser.parse_args(argv[1:])

    ctx_file = ns.ctx_opt or ns.ctx_pos
    out_file = ns.out_opt or ns.out_pos
    if not ctx_file:
        sys.stderr.write('usage: render_notion_page.py <ctx.json> [out.json] | --ctx C --out O [--manifest M]\n')
        return 2
    if ns.manifest and not os.path.exists(ns.manifest):
        sys.stderr.write(f'--manifest not found: {ns.manifest}\n')
        return 2
    try:
        with open(ctx_file, 'r', encoding='utf-8') as f:
            ctx = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    out = render(ctx)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if out_file:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        sys.stdout.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
