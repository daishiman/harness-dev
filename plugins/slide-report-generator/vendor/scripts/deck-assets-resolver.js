/**
 * deck-assets-resolver.js
 *
 * 「ブラウザが実際に読むもの」を 1 箇所で解決する SSOT。
 *
 * 背景 (この module が在る理由):
 *   出荷済みデッキには index.html へ CSS/JS をインライン化したもの (自己完結HTML) と、
 *   styles.css / scripts.js を <link> / <script src> で参照するものが混在する。
 *   さらに、インライン化した後もディスク上に古い styles.css が残っている例がある
 *   (実測: 出荷デッキの styles.css は実物より 9,653B 少ない旧版で、rem 数は
 *   ディスク 27 に対し実物 52 だった)。
 *   したがって `join(deckDir, 'styles.css')` を読む検査は、実物と違うものを見て
 *   合否を出す。偽緑 (実物が壊れているのに緑) と偽赤 (実物は正しいのに赤) の
 *   両方が実測で再現している。
 *
 * 契約:
 *   1. inline <style> / <script> と <link> / <script src> の両方を集めて 1 つとして返す。
 *      片方だけでは実物にならない (実測: 出荷デッキは inline が 2 ブロックで、
 *      2 番目のブロックはディスク上のどこにも存在しない)。
 *   2. 解決できないローカル参照は握り潰さず unresolved[] に積んで返す (fail-closed)。
 *      **この分岐を外すと、参照先が消えていても「CSS 0 件」のまま緑が出る。**
 *      呼び出し側は unresolved.length > 0 を必ず自分の重大度へ写像すること。
 *   3. 「styles.css というファイルが在ること」は要件ではない。
 *      要件は「CSS が解決できること」。自己完結 HTML は styles.css を持たないが正しい。
 *
 * 呼び出し側 (validate-print.js / validate-ai-image-assets.js /
 * cross-deck-consistency.js) は、必要な合成だけ自分で行う。
 */

import { readFileSync, existsSync } from 'fs';
import { resolve, dirname, join } from 'path';

/** <link rel="stylesheet" href="..."> */
const LINK_CSS_RE = /<link\s+[^>]*rel\s*=\s*["']stylesheet["'][^>]*href\s*=\s*["']([^"']+)["'][^>]*>/gi;
/** <style> ... </style> */
const INLINE_CSS_RE = /<style[^>]*>([\s\S]*?)<\/style>/gi;
/** <script src="..."> */
const LINK_JS_RE = /<script\s+[^>]*src\s*=\s*["']([^"']+)["'][^>]*>\s*<\/script>/gi;
/** <script> ... </script> (src 無しのみ) */
const INLINE_JS_RE = /<script(?![^>]*\bsrc\s*=)[^>]*>([\s\S]*?)<\/script>/gi;

/** CDN 等の絶対 URL はローカル解決の対象外 */
function isRemote(href) {
  return /^https?:/i.test(href) || /^\/\//.test(href) || /^data:/i.test(href);
}

/** href からクエリ・フラグメントを落として絶対パス化 */
function toLocalPath(baseDir, href) {
  return resolve(baseDir, href.split('#')[0].split('?')[0]);
}

/**
 * 1 種類 (CSS または JS) のローカル参照を解決する。
 * @returns {{ linked: string, hrefs: string[], unresolved: Array<{href: string, resolved: string, reason: string}> }}
 */
function resolveLinked(html, baseDir, regex) {
  let linked = '';
  const hrefs = [];
  const unresolved = [];
  regex.lastIndex = 0;
  let m;
  while ((m = regex.exec(html)) !== null) {
    const href = m[1];
    if (isRemote(href)) continue;
    const resolvedPath = toLocalPath(baseDir, href);
    hrefs.push(href);
    try {
      linked += '\n' + readFileSync(resolvedPath, 'utf-8');
    } catch (error) {
      // fail-closed。ここで握り潰すと参照先が消えていても素通りする。
      unresolved.push({ href, resolved: resolvedPath, reason: error.code || error.message });
    }
  }
  return { linked, hrefs, unresolved };
}

/** inline ブロックを配列で集める */
function collectInline(html, regex) {
  const blocks = [];
  regex.lastIndex = 0;
  let m;
  while ((m = regex.exec(html)) !== null) blocks.push(m[1]);
  return blocks;
}

/**
 * index.html が実際に読み込む CSS / JS を解決する。
 *
 * @param {string} indexHtmlPath index.html の絶対パス
 * @returns {{
 *   indexHtmlPath: string,
 *   exists: boolean,
 *   html: string,
 *   css: { inlineBlocks: string[], inline: string, linked: string, text: string, hrefs: string[], unresolved: object[] },
 *   js:  { inlineBlocks: string[], inline: string, linked: string, text: string, hrefs: string[], unresolved: object[] }
 * }}
 */
export function resolveDeckAssets(indexHtmlPath) {
  const absPath = resolve(indexHtmlPath);
  const empty = { inlineBlocks: [], inline: '', linked: '', text: '', hrefs: [], unresolved: [] };
  if (!existsSync(absPath)) {
    return { indexHtmlPath: absPath, exists: false, html: '', css: { ...empty }, js: { ...empty } };
  }

  const html = readFileSync(absPath, 'utf-8');
  const baseDir = dirname(absPath);

  const cssLinked = resolveLinked(html, baseDir, LINK_CSS_RE);
  const cssInlineBlocks = collectInline(html, INLINE_CSS_RE);
  const cssInline = cssInlineBlocks.join('\n');

  const jsLinked = resolveLinked(html, baseDir, LINK_JS_RE);
  const jsInlineBlocks = collectInline(html, INLINE_JS_RE);
  const jsInline = jsInlineBlocks.join('\n');

  return {
    indexHtmlPath: absPath,
    exists: true,
    html,
    css: {
      inlineBlocks: cssInlineBlocks,
      inline: cssInline,
      linked: cssLinked.linked,
      text: `${cssInline}\n${cssLinked.linked}`,
      hrefs: cssLinked.hrefs,
      unresolved: cssLinked.unresolved,
    },
    js: {
      inlineBlocks: jsInlineBlocks,
      inline: jsInline,
      linked: jsLinked.linked,
      text: `${jsInline}\n${jsLinked.linked}`,
      hrefs: jsLinked.hrefs,
      unresolved: jsLinked.unresolved,
    },
  };
}

/**
 * デッキディレクトリから解決する薄いラッパ。
 */
export function resolveDeckAssetsFromDir(deckDir) {
  return resolveDeckAssets(join(deckDir, 'index.html'));
}

/**
 * 解決できなかったローカル参照を人が読める 1 行へ。
 * 呼び出し側はこれを自分の重大度 (CRITICAL / error) へ写像する。
 */
export function describeUnresolved(unresolved) {
  return unresolved
    .map((u) => `${u.href} -> ${u.resolved} (${u.reason})`)
    .join(', ');
}

/**
 * 「CSS が解決できたか」の判定。**在るべきファイル名ではなく解決可否を見る。**
 * 自己完結 HTML (inline のみ・link 0 件) は resolvable かつ非空なので ok。
 */
export function cssIsUsable(assets) {
  return assets.exists
    && assets.css.unresolved.length === 0
    && assets.css.text.trim().length > 0;
}

/** JS 版。同じ理由で「scripts.js が在ること」ではなく解決可否を見る。 */
export function jsIsUsable(assets) {
  return assets.exists
    && assets.js.unresolved.length === 0
    && assets.js.text.trim().length > 0;
}
