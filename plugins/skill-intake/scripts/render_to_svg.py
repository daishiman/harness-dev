#!/usr/bin/env python3
"""Render a Mermaid source to SVG via `mmdc` (mmdc 必須; 不在は exit 3)."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# execution-contract.md 終了コード規約: 3 = DEPENDENCY_ERROR (mmdc 等の外部ツール不在)。
MMDC_INSTALL_GUIDE = (
    'mmdc (Mermaid CLI) が見つかりません。図の描画に必須です。\n'
    '導入手順:\n'
    '  1. Node.js をインストール (https://nodejs.org)\n'
    '  2. ターミナルで: npm install -g @mermaid-js/mermaid-cli\n'
    '  3. mmdc --version が表示されれば導入完了\n'
    '(--allow-placeholder は CI/テスト専用。通常運用では使わない)\n'
)


def has_mmdc() -> bool:
    if shutil.which('mmdc') is None:
        return False
    try:
        r = subprocess.run(['mmdc', '--version'], capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def render(input_path: Path, output_path: Path,
           opts: dict[str, Any] | None = None) -> dict[str, Any]:
    opts = opts or {}
    if not has_mmdc():
        # fail-open 禁止: placeholder は明示 --allow-placeholder (CI/テスト専用) のみ。
        if opts.get('allow_placeholder'):
            placeholder = (
                '<?xml version="1.0"?>\n'
                f'<!-- mmdc not installed; placeholder for {input_path.name} -->\n'
                '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="80">'
                '<text x="10" y="40">mermaid placeholder</text></svg>\n'
            )
            output_path.write_text(placeholder, encoding='utf-8')
            return {'ok': True, 'mode': 'placeholder', 'output': str(output_path)}
        return {'ok': False, 'mode': 'mmdc', 'reason': 'DEPENDENCY_ERROR',
                'error': 'mmdc not installed'}
    r = subprocess.run(
        ['mmdc', '-i', str(input_path), '-o', str(output_path), '-b', 'transparent'],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return {'ok': False, 'mode': 'mmdc', 'stderr': r.stderr}
    return {'ok': True, 'mode': 'mmdc', 'output': str(output_path)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog='render_to_svg.py', description='Mermaid → SVG (mmdc 必須; 不在は exit 3)')
    parser.add_argument('input', help='input .mmd')
    parser.add_argument('output', help='output .svg')
    parser.add_argument('--allow-placeholder', dest='allow_placeholder', action='store_true',
                        help='mmdc 不在時に placeholder を生成して続行する (CI/テスト専用。通常運用では使わない)')
    args = parser.parse_args(argv)
    inp = Path(args.input)
    out = Path(args.output)
    if not inp.exists():
        sys.stderr.write(f'input missing: {inp}\n')
        return 2
    r = render(inp.resolve(), out.resolve(), {'allow_placeholder': args.allow_placeholder})
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    if r.get('reason') == 'DEPENDENCY_ERROR':
        sys.stderr.write(f'[render_to_svg] {MMDC_INSTALL_GUIDE}')
    return 0 if r.get('ok') else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
