#!/usr/bin/env python3
"""5 軸 + user_profile の必須キー存在を検証。"""

import json
import sys

REQUIRED_AXES = ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets']
AXIS_FALLBACK = {'output_target': 'output_destination'}

# v2 構造 (render_notion_page context / convert_v1_to_v2_context の出力) では
# five_axes.rows[] が日本語 name + content を持つ。v1 の flat dict (5_axes.output_target)
# と相互変換するための JA name → 内部 key マッピング (convert_v1_to_v2_context と一致)。
AXIS_JA_TO_KEY = {
    '出力先': 'output_target',
    '情報源': 'info_source',
    '共有相手': 'share_target',
    '真の課題': 'true_problem',
    'ナレッジ資産': 'knowledge_assets',
}


def axis_value_text(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and isinstance(v.get('answer'), str):
        return v['answer']
    if isinstance(v, dict) and isinstance(v.get('content'), str):
        return v['content']
    return None


def normalize_axes(intake):
    """v1 flat (5_axes.output_target=...) と v2 (five_axes.rows[]) を共通の
    {key: text} dict に正規化する。後方互換: v1 構造はそのまま通す。"""
    raw = intake.get('5_axes') or intake.get('five_axes')
    if not isinstance(raw, dict):
        return None
    # v2: rows[] を持つ場合は JA name → key へ畳み込む
    rows = raw.get('rows')
    if isinstance(rows, list):
        flat = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = AXIS_JA_TO_KEY.get(str(row.get('name', '')).strip())
            if key:
                flat[key] = axis_value_text(row)
        return flat
    # v1: そのまま (output_target などのキーを持つ flat dict)
    return raw


def has_user_profile(intake):
    """v1 user_profile / v2 profile(.dimensions) のどちらかが存在すれば真。"""
    if 'user_profile' in intake:
        return True
    prof = intake.get('profile')
    return isinstance(prof, dict) and bool(prof.get('dimensions') or prof)


def validate(intake):
    errors = []
    if not isinstance(intake, dict):
        return {'ok': False, 'errors': ['intake is not an object']}
    if '5_axes' not in intake and 'five_axes' not in intake:
        errors.append('missing top-level key: 5_axes (or five_axes)')
    if not has_user_profile(intake):
        errors.append('missing top-level key: user_profile (or profile)')
    axes = normalize_axes(intake)
    if axes is None:
        errors.append('5_axes/five_axes missing or not an object')
    else:
        for k in REQUIRED_AXES:
            fb = AXIS_FALLBACK.get(k)
            present = (k in axes) or (fb and fb in axes)
            if not present:
                errors.append(f'5_axes.{k} missing')
                continue
            raw = axes[k] if k in axes else axes[fb]
            text = axis_value_text(raw)
            if text is None or text.strip() == '':
                errors.append(f'5_axes.{k} empty')
    up = intake.get('user_profile')
    if up is not None and not isinstance(up, (dict, str)):
        errors.append('user_profile invalid type')
    return {'ok': len(errors) == 0, 'errors': errors}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: validate_intake.py <intake.json>\n')
        return 2
    try:
        with open(argv[1], 'r', encoding='utf-8') as f:
            intake = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = validate(intake)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
