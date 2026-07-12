#!/usr/bin/env python3
"""Render diagram sources to PNG.

- 入力 .mmd: 外部 `mmdc` CLI で Mermaid → PNG (mmdc 必須; 不在は exit 3)。
- 入力 .svg: 同梱済み事前レンダリング PNG (入力と同ディレクトリの <stem>.png、
  例 assets/cvis-*.png) を出力先へコピー (外部依存ゼロ)。同梱 PNG 不在時のみ
  cairosvg fallback で変換し、どちらも不可なら exit 3 (DEPENDENCY_ERROR)。
"""
from __future__ import annotations

import argparse
import json
import re
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

SVG_DEPENDENCY_GUIDE = (
    'SVG → PNG の変換手段がありません (同梱 PNG 不在 + cairosvg 未導入)。\n'
    '復旧手順 (いずれか):\n'
    '  1. 同梱 PNG を再取得: 配布物 assets/ の <入力SVG名>.png を入力 SVG と同じディレクトリへ戻す\n'
    '  2. pip install cairosvg で変換ライブラリを導入する\n'
)


def has_mmdc() -> bool:
    if shutil.which('mmdc') is None:
        return False
    try:
        r = subprocess.run(['mmdc', '--version'], capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def load_cairosvg() -> Any:
    """cairosvg module を返す。未導入なら None (テストで monkeypatch 可能な単一 seam)。"""
    try:
        import cairosvg  # type: ignore
        return cairosvg
    except ImportError:
        return None


def placeholder_png(output_path: Path, note: str = '') -> None:
    txt = (
        f"# mmdc not installed\n"
        f"# placeholder for {output_path.name}\n"
        f"# note: {note}\n"
    )
    (output_path.parent / (output_path.name + '.placeholder.txt')).write_text(txt, encoding='utf-8')


def svg_bytes_for_cairosvg(input_path: Path) -> bytes:
    """cairosvg 向けに SVG を前処理して bytes を返す。

    cairosvg は CSS システムフォントキーワード `-apple-system` を実フォントとして
    解決できず、font-family リスト先頭にあると CJK グリフを持たない代替が選ばれ
    日本語が豆腐化する。リストから除去して後続 (Hiragino Sans 等) を解決させる。
    """
    text = input_path.read_text(encoding='utf-8')
    text = re.sub(r'-apple-system\s*,\s*', '', text)
    return text.encode('utf-8')


def render_svg(input_path: Path, output_path: Path, opts: dict[str, Any]) -> dict[str, Any]:
    """静的 SVG → PNG。同梱 PNG コピー (外部依存ゼロ) → cairosvg fallback → exit 3。"""
    bundled = input_path.with_suffix('.png')
    if bundled.exists() and bundled.stat().st_size > 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled, output_path)
        return {'ok': True, 'mode': 'bundled-copy', 'source': str(bundled),
                'output': str(output_path)}
    cairosvg = load_cairosvg()
    if cairosvg is None:
        return {'ok': False, 'mode': 'svg', 'reason': 'DEPENDENCY_ERROR',
                'error': 'no bundled PNG and cairosvg not installed'}
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(bytestring=svg_bytes_for_cairosvg(input_path),
                         write_to=str(output_path),
                         output_width=opts.get('width') or 1200)
    except Exception as e:
        return {'ok': False, 'mode': 'cairosvg', 'error': str(e)}
    return {'ok': True, 'mode': 'cairosvg', 'output': str(output_path)}


def render(input_path: Path, output_path: Path, opts: dict[str, Any] | None = None) -> dict[str, Any]:
    opts = opts or {}
    if input_path.suffix.lower() == '.svg':
        # 静的 SVG は mmdc 非対象 (mmdc は Mermaid 専用)。同梱 PNG / cairosvg 経路へ。
        return render_svg(input_path, output_path, opts)
    fmt = opts.get('format') or ('svg' if str(output_path).endswith('.svg') else 'png')
    if not has_mmdc():
        # fail-open 禁止: placeholder は明示 --allow-placeholder (CI/テスト専用) のみ。
        if opts.get('allow_placeholder'):
            placeholder_png(output_path, f'format={fmt}')
            return {'ok': True, 'mode': 'placeholder', 'output': str(output_path)}
        return {'ok': False, 'mode': 'mmdc', 'reason': 'DEPENDENCY_ERROR',
                'error': 'mmdc not installed'}
    args = ['mmdc', '-i', str(input_path), '-o', str(output_path), '-b', 'white']
    if opts.get('width'):
        args += ['-w', str(opts['width'])]
    if opts.get('height'):
        args += ['-H', str(opts['height'])]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return {'ok': False, 'mode': 'mmdc', 'stderr': r.stderr}
    return {'ok': True, 'mode': 'mmdc', 'output': str(output_path), 'format': fmt}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog='render_to_image.py',
        description='Mermaid(.mmd) → PNG (mmdc 必須; 不在は exit 3) / '
                    '静的 SVG(.svg) → 同梱 PNG コピー (不在時 cairosvg fallback; 両不可は exit 3)')
    parser.add_argument('input', help='input .mmd (Mermaid) または .svg (カタログ静的 SVG)')
    parser.add_argument('output', help='output .png')
    parser.add_argument('--allow-placeholder', dest='allow_placeholder', action='store_true',
                        help='mmdc 不在時に placeholder を生成して続行する (CI/テスト専用。通常運用では使わない)')
    args = parser.parse_args(argv)
    inp = Path(args.input)
    out = Path(args.output)
    if not inp.exists():
        sys.stderr.write(f'input missing: {inp}\n')
        return 2
    r = render(inp.resolve(), out.resolve(),
               {'width': 1200, 'allow_placeholder': args.allow_placeholder})
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    if r.get('reason') == 'DEPENDENCY_ERROR':
        guide = SVG_DEPENDENCY_GUIDE if r.get('mode') == 'svg' else MMDC_INSTALL_GUIDE
        sys.stderr.write(f'[render_to_image] {guide}')
    return 0 if r.get('ok') else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
