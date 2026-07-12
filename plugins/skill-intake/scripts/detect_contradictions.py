#!/usr/bin/env python3
"""NEG/POS 対立 + shared_terms 共有による矛盾検出。"""

import json
import re
import sys

NEG = ['ない', '不要', '無し', 'なし', '使わない', '使用しない', '対象外']
POS = ['必要', '使う', '対象', '欲しい', 'する', '実施']

_SPLIT_RE = re.compile(r'[、。\s,.;]+')
_NUM_RE = re.compile(r'^[0-9０-９]+$')
_UPPER_INITIAL_RE = re.compile(r'^[A-Z][A-Za-z0-9_-]*$')
_ALL_UPPER_RE = re.compile(r'^[A-Z0-9_-]+$')
STOP_TERMS = {'ラベル', 'Pro', 'Con', 'Weight', 'ID', '---', '✅'}


def flatten(obj, prefix='', acc=None):
    if acc is None:
        acc = []
    if obj is None:
        return acc
    if isinstance(obj, str):
        acc.append({'path': prefix, 'value': obj})
        return acc
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten(v, f'{prefix}[{i}]', acc)
        return acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(v, f'{prefix}.{k}' if prefix else k, acc)
    return acc


def tokenize(s):
    return [t.strip() for t in _SPLIT_RE.split(s) if t.strip()]


def is_informative_shared_term(t):
    cleaned = re.sub(r'[*`|✅\[\]()（）]+', '', t).strip()
    if not cleaned or len(cleaned) < 2:
        return False
    if cleaned in STOP_TERMS:
        return False
    if _NUM_RE.match(cleaned):
        return False
    if _UPPER_INITIAL_RE.match(cleaned):
        return False
    if _ALL_UPPER_RE.match(cleaned):
        return False
    if not re.search(r'[ぁ-んァ-ヶ一-龠]', cleaned):
        return False
    return True


def detect(intake):
    statements = flatten(intake)
    contradictions = []
    n = len(statements)
    for i in range(n):
        for j in range(i + 1, n):
            a = statements[i]['value']
            b = statements[j]['value']
            a_neg = any(x in a for x in NEG)
            b_pos = any(x in b for x in POS)
            b_neg = any(x in b for x in NEG)
            a_pos = any(x in a for x in POS)
            if not ((a_neg and b_pos) or (a_pos and b_neg)):
                continue
            a_toks = set(tokenize(a))
            b_toks = set(tokenize(b))
            shared = [t for t in a_toks if t in b_toks and len(t) >= 2 and is_informative_shared_term(t)]
            if len(shared) >= 2:
                contradictions.append({
                    'a_path': statements[i]['path'],
                    'b_path': statements[j]['path'],
                    'shared_terms': shared,
                    'a_excerpt': a[:80],
                    'b_excerpt': b[:80],
                })
    return {'ok': len(contradictions) == 0, 'count': len(contradictions), 'contradictions': contradictions}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: detect_contradictions.py <intake.json>\n')
        return 2
    try:
        with open(argv[1], 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = detect(data)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
