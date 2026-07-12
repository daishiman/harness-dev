/**
 * mermaid-render.js — Mermaid 定義文字列 → SVG/HTML 片 (決定論)
 *
 * 契約: BUILD CONTRACT §F (C19 owner)。
 * package-lock で固定したローカル Mermaid browser bundle を HTML へ inline し、
 * `<pre class="mermaid">` をオフラインでも SVG 化できる自己完結片を決定論生成する。
 *
 * ESM (vendor/package.json type=module)。CLI と import の両対応。
 *   - CLI:    node mermaid-render.js <in.mmd> <out.svg|html>
 *   - import: import { renderMermaidFragment, mermaidInitScript, renderMermaidSvg } from './mermaid-render.js'
 */

import { readFileSync, writeFileSync } from 'fs';
import { pathToFileURL } from 'url';

const MERMAID_BUNDLE_URL = new URL('../node_modules/mermaid/dist/mermaid.min.js', import.meta.url);
let cachedMermaidBundle = null;

function localMermaidBundle() {
  if (cachedMermaidBundle === null) {
    cachedMermaidBundle = readFileSync(MERMAID_BUNDLE_URL, 'utf8').replace(/<\/script/gi, '<\\/script');
  }
  return cachedMermaidBundle;
}

/** HTML/XML エスケープ (template-engine.cjs / svg-builder.cjs と同一方針) */
function escape(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * package-lock固定のローカル mermaid bundle と初期化コードを埋め込むスクリプト片。
 * report HTML の <head> に「1回だけ」差し込む想定。theme は Kanagawa 調の
 * neutral を選び startOnLoad で `.mermaid` を自動レンダリングする。
 * @returns {string} <script type="module"> ... </script>
 */
export function mermaidInitScript() {
  return [
    '<script>',
    localMermaidBundle(),
    "  globalThis.mermaid.initialize({ startOnLoad: true, theme: 'neutral', securityLevel: 'strict' });",
    '</script>',
  ].join('\n');
}

/**
 * Mermaid 定義 → HTML 片 (<figure><pre class="mermaid">…</pre></figure>)。
 * 決定論: 入力が同じなら出力も同一 (乱数/時刻を含まない)。
 * @param {string} definition Mermaid 定義文字列 (例 "graph TD; A-->B")
 * @param {{ caption?: string, ariaLabel?: string }} [opts]
 * @returns {string} HTML 片
 */
export function renderMermaidFragment(definition, opts = {}) {
  const def = String(definition == null ? '' : definition).trim();
  const label = escape(opts.ariaLabel || 'Mermaid 図');
  const caption = opts.caption ? `\n  <figcaption>${escape(opts.caption)}</figcaption>` : '';
  return `<figure class="report-visual report-visual--mermaid" role="img" aria-label="${label}">
  <pre class="mermaid">${escape(def)}</pre>${caption}
</figure>`;
}

/**
 * Mermaid 定義 → 単体 SVG (決定論プレースホルダ)。
 * mermaid ライブラリ非導入環境向けに、定義テキストを内包した valid な SVG を返す。
 * CLI で出力先が .svg の場合に使用。
 * @param {string} definition
 * @param {{ width?: number, height?: number }} [opts]
 * @returns {string} SVG 文字列 (<?xml ... ?> は付けず <svg> ルート)
 */
export function renderMermaidSvg(definition, opts = {}) {
  const def = String(definition == null ? '' : definition).trim();
  const W = opts.width || 960;
  const H = opts.height || 480;
  const lines = def.split('\n');
  const lineH = 22;
  const startY = 70;
  const tspans = lines
    .map((ln, i) => `<tspan x="40" dy="${i === 0 ? 0 : lineH}">${escape(ln)}</tspan>`)
    .join('');
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mermaid 図 (静的プレースホルダ)" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="${W}" height="${H}" fill="var(--bg-dark, #fafafa)"/>
  <rect x="20" y="20" width="${W - 40}" height="${H - 40}" rx="12" fill="none" stroke="var(--wave-blue, #7E9CD8)" stroke-width="1.5"/>
  <text x="40" y="45" fill="var(--accent-blue-vivid, #3B7DD8)" font-size="18" font-weight="700" font-family="'Noto Sans JP', sans-serif">Mermaid</text>
  <text x="40" y="${startY}" fill="var(--fg, #43436c)" font-size="15" font-family="'SF Mono', 'Fira Code', monospace">${tspans}</text>
</svg>`;
}

/**
 * 出力先拡張子に応じて完結した成果物文字列を返す。
 * @param {string} definition
 * @param {string} outPath 出力ファイルパス (.svg or .html)
 * @returns {string}
 */
export function renderMermaidForFile(definition, outPath) {
  if (/\.svg$/i.test(outPath)) {
    return renderMermaidSvg(definition);
  }
  // .html: CDN 初期化つきの完結 HTML
  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mermaid</title>
${mermaidInitScript()}
</head>
<body>
${renderMermaidFragment(definition)}
</body>
</html>
`;
}

// ---- CLI ----
function isMain() {
  return process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (isMain()) {
  const [inPath, outPath] = process.argv.slice(2);
  if (!inPath || !outPath) {
    console.error('usage: node mermaid-render.js <in.mmd> <out.svg|html>');
    process.exit(2);
  }
  try {
    const def = readFileSync(inPath, 'utf-8');
    const out = renderMermaidForFile(def, outPath);
    writeFileSync(outPath, out, 'utf-8');
    console.log(`mermaid-render: wrote ${outPath} (${Buffer.byteLength(out)} bytes)`);
  } catch (e) {
    console.error(`mermaid-render error: ${e.message}`);
    process.exit(1);
  }
}
