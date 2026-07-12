/**
 * test-mermaid-render.js — mermaid-render.js の最小テスト (node 実行)。
 *
 * 検証:
 *   - renderMermaidFragment: <pre class="mermaid"> 片・定義埋込・エスケープ
 *   - mermaidInitScript: package-lock固定ローカルbundleの自己完結初期化 script
 *   - renderMermaidSvg: valid な <svg> ルート・定義テキスト内包
 *   - renderMermaidForFile: .html は <!DOCTYPE html>、.svg は <svg
 *   - 決定論: 同一入力→同一出力
 *
 * 失敗時 exit 1、成功時 exit 0。
 *   実行: node test-mermaid-render.js
 */

import {
  renderMermaidFragment,
  mermaidInitScript,
  renderMermaidSvg,
  renderMermaidForFile,
} from '../scripts/mermaid-render.js';

let failed = 0;
function check(name, cond) {
  if (cond) {
    console.log(`  ok   - ${name}`);
  } else {
    console.error(`  FAIL - ${name}`);
    failed++;
  }
}

const def = 'graph TD; A[開始] --> B{判定}; B -->|yes| C[実行]; B -->|no| D[終了]';

// fragment
const frag = renderMermaidFragment(def, { caption: '処理フロー', ariaLabel: '判定フロー' });
check('fragment: <pre class="mermaid"> を含む', frag.includes('<pre class="mermaid">'));
check('fragment: 定義が埋込まれている (開始)', frag.includes('開始'));
check('fragment: caption を含む', frag.includes('処理フロー'));
check('fragment: aria-label を含む', frag.includes('判定フロー'));

// エスケープ (< > が実体参照化されること = 注入防止)
const injected = renderMermaidFragment('graph TD; A["<script>alert(1)</script>"] --> B');
check('fragment: HTML エスケープされる (<script 生埋込なし)', !injected.includes('<script>alert(1)'));
check('fragment: エスケープ後 &lt;script&gt; を含む', injected.includes('&lt;script&gt;'));

// init script
const init = mermaidInitScript();
check('init: inline <script> を含む', init.includes('<script>'));
check('init: mermaid.initialize を含む', init.includes('mermaid.initialize'));
check('init: 外部 CDN URL を含まない', !init.includes('cdn.jsdelivr.net'));
check('init: local bundle を inline 携行', init.length > 1_000_000);

// svg
const svg = renderMermaidSvg(def);
check('svg: <svg viewBox で始まる要素を含む', svg.includes('<svg viewBox='));
check('svg: </svg> で閉じる', svg.trim().endsWith('</svg>'));
check('svg: 定義テキストを内包 (判定)', svg.includes('判定'));

// forFile
const asHtml = renderMermaidForFile(def, 'out.html');
check('forFile(.html): <!DOCTYPE html> で始まる', asHtml.startsWith('<!DOCTYPE html>'));
check('forFile(.html): mermaid init を含む', asHtml.includes('mermaid.initialize'));
const asSvg = renderMermaidForFile(def, 'out.svg');
check('forFile(.svg): <svg を含む', asSvg.includes('<svg'));
check('forFile(.svg): DOCTYPE を含まない', !asSvg.includes('<!DOCTYPE'));

// 決定論
check('決定論: fragment 2回が一致', renderMermaidFragment(def) === renderMermaidFragment(def));
check('決定論: svg 2回が一致', renderMermaidSvg(def) === renderMermaidSvg(def));

console.log('');
if (failed > 0) {
  console.error(`test-mermaid-render: ${failed} 件 FAIL`);
  process.exit(1);
}
console.log('test-mermaid-render: 全 PASS');
process.exit(0);
