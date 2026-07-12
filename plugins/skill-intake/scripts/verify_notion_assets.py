#!/usr/bin/env python3
"""manifest.items の各エントリの存在確認と sha256_16 ハッシュ照合。"""

import hashlib
import json
import os
import sys


def hash_file(file_path):
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()[:16]


def verify(manifest_path):
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except Exception as e:
        return {'ok': False, 'invalid_manifest': str(e), 'missing': [], 'corrupted': [], 'total': 0}
    if not isinstance(manifest, dict):
        return {'ok': False, 'invalid_manifest': 'manifest root must be an object', 'missing': [], 'corrupted': [], 'total': 0}
    base_dir = manifest.get('dest') or os.path.dirname(manifest_path)
    missing = []
    corrupted = []
    if 'items' not in manifest:
        return {'ok': False, 'invalid_manifest': 'manifest.items is required', 'missing': [], 'corrupted': [], 'total': 0}
    items = manifest.get('items')
    if not isinstance(items, list):
        return {'ok': False, 'invalid_manifest': 'manifest.items must be an array', 'missing': [], 'corrupted': [], 'total': 0}
    if len(items) == 0:
        return {'ok': False, 'invalid_manifest': 'manifest.items must not be empty', 'missing': [], 'corrupted': [], 'total': 0}
    for item in items:
        if not isinstance(item, dict):
            corrupted.append({'path': '', 'reason': 'manifest item must be an object'})
            continue
        rel_path = item.get('path') or item.get('absolute') or ''
        abs_path = item.get('absolute') or os.path.join(base_dir, item.get('path', ''))
        if not os.path.exists(abs_path):
            missing.append(rel_path)
            continue
        if item.get('sha256_16'):
            h = hash_file(abs_path)
            if h != item['sha256_16']:
                corrupted.append({'path': item.get('path'), 'expected': item['sha256_16'], 'actual': h})
    ok = len(missing) == 0 and len(corrupted) == 0
    return {'ok': ok, 'missing': missing, 'corrupted': corrupted, 'total': len(items)}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: verify_notion_assets.py <manifest.json>\n')
        return 2
    manifest_file = argv[1]
    if not os.path.exists(manifest_file):
        sys.stderr.write(f'manifest missing: {manifest_file}\n')
        return 2
    r = verify(os.path.abspath(manifest_file))
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    if r.get('invalid_manifest'):
        return 2
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
