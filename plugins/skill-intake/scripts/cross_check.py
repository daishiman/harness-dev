#!/usr/bin/env python3
"""intake.md と intake.json の 5 軸 answer 一致を Jaccard 類似度で検査。"""

import json
import re
import sys

AXES = ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets']
AXIS_HEADINGS = {
    'output_target': ['出力先', 'Output Destination'],
    'info_source': ['情報源', 'Information Source'],
    'share_target': ['共有相手', 'Sharing Target'],
    'true_problem': ['真の課題', 'True Problem'],
    'knowledge_assets': ['ナレッジ資産', 'Knowledge Assets'],
}
AXIS_FALLBACK = {'output_target': 'output_destination'}
_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)
_HEADING_RE = re.compile(r'^#{1,4}\s+(.*?)\s*$')
_SPLIT_RE = re.compile(r'[\s、。,.]+')
_WS_RE = re.compile(r'\s+')


def parse_sections(md):
    sections = {}
    current = None
    buf = []
    for line in md.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if current is not None:
                sections[current] = '\n'.join(buf).strip()
            current = m.group(1)
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = '\n'.join(buf).strip()
    return sections


def pick_axis(sections, keys):
    for k, v in sections.items():
        if any(needle in k for needle in keys):
            return v
    return ''


def parse_five_axes_table(body):
    out = {}
    axis_by_label = {
        '出力先': 'output_target',
        '情報源': 'info_source',
        '共有相手': 'share_target',
        '真の課題': 'true_problem',
        'ナレッジ資産': 'knowledge_assets',
    }
    for line in body.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 3 or cells[0] in ('軸', '---'):
            continue
        label = re.sub(r'[*`]', '', cells[0]).replace('（MUST）', '').strip()
        key = axis_by_label.get(label)
        if key:
            out[key] = cells[1].strip()
    return out


def extract_frontmatter(md):
    m = _FRONTMATTER_RE.match(md)
    if not m:
        return {}, md
    meta = {}
    for line in m.group(1).split('\n'):
        kv = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)$', line)
        if kv:
            v = kv.group(2).strip()
            v = re.sub(r"^['\"]|['\"]$", '', v)
            meta[kv.group(1)] = v
    return meta, md[m.end():]


def convert_md(md):
    _, body = extract_frontmatter(md)
    sections = parse_sections(body)
    five_axes = parse_five_axes_table(body)
    if not five_axes:
        five_axes = {}
        for k, heads in AXIS_HEADINGS.items():
            five_axes[k] = pick_axis(sections, heads)
    return {'5_axes': five_axes}


def norm(s):
    return _WS_RE.sub(' ', str(s or '')).strip()


def similarity(a, b):
    na = norm(a)
    nb = norm(b)
    if not na and not nb:
        return 1
    if not na or not nb:
        return 0
    sa = set(t for t in _SPLIT_RE.split(na) if t)
    sb = set(t for t in _SPLIT_RE.split(nb) if t)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0


def cross(md, json_data):
    from_md = convert_md(md)
    md_axes = from_md.get('5_axes', {})
    json_axes = json_data.get('5_axes') or json_data.get('five_axes') or {}
    mismatches = []
    for k in AXES:
        json_value = json_axes.get(k)
        if json_value is None and k in AXIS_FALLBACK:
            json_value = json_axes.get(AXIS_FALLBACK[k])
        sim = similarity(md_axes.get(k), json_value)
        if sim < 0.4:
            mismatches.append({
                'axis': k,
                'similarity': round(sim, 2),
                'md_excerpt': norm(md_axes.get(k))[:60],
                'json_excerpt': norm(json_value)[:60],
            })
    return {'ok': len(mismatches) == 0, 'mismatches': mismatches}


def main(argv):
    if len(argv) < 3:
        sys.stderr.write('usage: cross_check.py <intake.md> <intake.json>\n')
        return 2
    try:
        with open(argv[1], 'r', encoding='utf-8') as f:
            md = f.read()
        with open(argv[2], 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = cross(md, json_data)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
