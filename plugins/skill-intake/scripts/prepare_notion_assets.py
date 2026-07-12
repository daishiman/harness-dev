#!/usr/bin/env python3
"""Copy visual assets into a Notion-upload staging dir and emit a manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ALLOWED = {'.png', '.svg', '.jpg', '.jpeg', '.gif'}


def walk(dir_: Path) -> list[Path]:
    if not dir_.exists():
        return []
    out: list[Path] = []
    for p in dir_.rglob('*'):
        if p.is_file():
            out.append(p)
    return out


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def prepare(src_dir: Path, dest_dir: Path) -> dict[str, Any]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for file in walk(src_dir):
        ext = file.suffix.lower()
        if ext not in ALLOWED:
            skipped.append({'path': str(file), 'reason': 'ext'})
            continue
        rel = file.relative_to(src_dir)
        dest = dest_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, dest)
        size = dest.stat().st_size
        items.append({
            'path': str(rel),
            'absolute': str(dest),
            'size': size,
            'sha256_16': file_hash(dest),
            'ext': ext,
        })
    by_ext: dict[str, int] = {}
    for it in items:
        by_ext[it['ext']] = by_ext.get(it['ext'], 0) + 1
    return {
        'items': items,
        'skipped': skipped,
        'summary': {'total': len(items), 'by_ext': by_ext},
        'src': str(src_dir),
        'dest': str(dest_dir),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write('usage: prepare_notion_assets.py <src> <dest> [manifest.json]\n')
        return 2
    src = Path(argv[0]).resolve()
    dest = Path(argv[1]).resolve()
    out = argv[2] if len(argv) > 2 else None
    manifest = prepare(src, dest)
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    manifest_path = Path(out).resolve() if out else dest / 'manifest.json'
    manifest_path.write_text(text + '\n', encoding='utf-8')
    sys.stdout.write(json.dumps({'ok': True, 'manifest': str(manifest_path), 'total': manifest['summary']['total']}, ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
