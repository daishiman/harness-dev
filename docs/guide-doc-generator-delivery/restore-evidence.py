#!/usr/bin/env python3
"""収録した全ファイルをハッシュ検証し、指定先へ元の構成で復元する。"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='内容を検証するだけで書き込まない')
    parser.add_argument('--out', type=Path, help='空の復元先。harness/ と handout/ を作る')
    args = parser.parse_args()
    if not args.verify and args.out is None:
        parser.error('--verify または --out を指定してください')
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'manifest.json').read_text())
    target_root = args.out.resolve() if args.out else None
    if target_root and target_root.exists() and any(target_root.iterdir()):
        parser.error('復元先には空のディレクトリを指定してください')
    if target_root:
        target_root.mkdir(parents=True, exist_ok=True)
    groups = {}
    for entry in manifest['files']:
        path = PurePosixPath(entry['path'])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('不正な復元パス')
        groups.setdefault(entry['storage']['path'], []).append(entry)
    total = 0
    for stored, entries in sorted(groups.items()):
        source = (root / stored).resolve()
        source.relative_to(root)
        storage = entries[0]['storage']
        if storage['kind'] == 'zip':
            if hashlib.sha256(source.read_bytes()).hexdigest() != storage['sha256']:
                raise ValueError('アーカイブのハッシュ不一致: ' + stored)
            with zipfile.ZipFile(source) as archive:
                if archive.namelist() != ['payload']:
                    raise ValueError('アーカイブの構成が不正: ' + stored)
                data = archive.read('payload')
        elif storage['kind'] == 'file':
            data = source.read_bytes()
        else:
            raise ValueError('未知の保存形式')
        digest = hashlib.sha256(data).hexdigest()
        for entry in entries:
            if digest != entry['sha256'] or len(data) != entry['size_bytes']:
                raise ValueError('内容のハッシュ不一致: ' + entry['path'])
            if target_root:
                target = target_root / entry['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                os.chmod(target, int(entry['mode'], 8) & 0o777)
            total += 1
    print('全ファイルの検証成功: ' + str(total) + '件' + ('（復元済み）' if target_root else ''))


if __name__ == '__main__':
    main()
