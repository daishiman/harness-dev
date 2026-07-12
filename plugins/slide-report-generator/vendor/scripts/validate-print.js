#!/usr/bin/env node
/**
 * validate-print.js
 *
 * 印刷品質の決定論的検証スクリプト。
 * HTMLファイルの @media print CSS ブロックを静的解析し、
 * 15項目（P01-P14）のチェックを実行する。
 *
 * Usage:
 *   node validate-print.js <html-file>
 *   node validate-print.js <html-file> --fix-hints
 *   node validate-print.js <html-file> --json
 *   node validate-print.js <html-file> --full-image-deck
 *
 * Exit codes:
 *   0 = All checks passed
 *   1 = Critical issues found
 *   2 = Argument error
 *
 * CHANGELOG:
 *   v2 (2026-06-24, elegant-review D4):
 *     - P06 を 297x210mm 固定前提から 16:9 letterbox(297mm幅 + height可変)
 *       も許容する判定へ拡張。通常HTMLデッキ(210mm full-bleed)は後方互換維持。
 *     - P13 新設: 全面画像デッキの主キャンバス img が @media print 内で
 *       object-fit:cover を持つと CRITICAL(D1 印刷端切れ違反の機械検出)。
 *     - P14 新設: 全スライドが印刷対象(page-break-after:always 等)で
 *       data-hidden 付き除外が意図的かを判定(WARNING)。
 *     - --full-image-deck フラグ追加。未指定でも structure.md/meta から
 *       全面画像デッキを自動検出し P13/P14 を有効化(後方互換)。
 *     - 既存 P01-P12 のロジックは不変。
 */

import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';

// ============================================================
// CLI引数パース
// ============================================================
const args = process.argv.slice(2);
const flags = {
  fixHints: args.includes('--fix-hints'),
  json: args.includes('--json'),
  fullImageDeck: args.includes('--full-image-deck'),
  help: args.includes('--help') || args.includes('-h'),
};
const filePath = args.find(a => !a.startsWith('-'));

if (flags.help) {
  console.log(`
Usage: node validate-print.js <html-file> [options]

Options:
  --fix-hints        Show remediation hints for failed checks
  --json             Output results as JSON
  --full-image-deck  Force full-image-deck print contract (letterbox + contain)
  --help             Show this help

Checks (P01-P14):
  P01  Chrome extension hiding (body>*:not(.slider))
  P02  Slide number dynamic (attr(data-total))
  P03  data-total attribute on .slider__item
  P04  print-color-adjust: exact
  P05  No font-size overrides inside @media print (vw-based unification)
  P06  A4 landscape viewport lock (297mm; 210mm full-bleed or 16:9 letterbox)
  P07  Pagination color specification
  P08  isolation: isolate
  P09  Gradient text print fallback
  P10  .question-badge print CSS
  P11  Print padding 8mm
  P12  Detailed extension hiding (visibility/width/overflow)
  P13  Full-image main canvas must NOT use object-fit:cover in @media print
  P14  All slides print-targeted (page-break) / data-hidden exclusion is intentional
`);
  process.exit(0);
}

if (!filePath) {
  console.error('Error: HTML file path is required');
  console.error('Usage: node validate-print.js <html-file> [--fix-hints] [--json]');
  process.exit(2);
}

const absPath = resolve(filePath);
if (!existsSync(absPath)) {
  console.error(`Error: File not found: ${absPath}`);
  process.exit(2);
}

// ============================================================
// HTML読み込み・@media print ブロック抽出
// ============================================================
const html = readFileSync(absPath, 'utf-8');

// 外部 stylesheet（<link rel="stylesheet" href="...">）を解決して取り込む
// 決定論レンダラ (render-slide.cjs) は CSS を styles.css に分離するため必須
const baseDir = dirname(absPath);
const linkRegex = /<link\s+[^>]*rel\s*=\s*["']stylesheet["'][^>]*href\s*=\s*["']([^"']+)["'][^>]*>/gi;
let linkedCss = '';
let linkMatch;
while ((linkMatch = linkRegex.exec(html)) !== null) {
  const href = linkMatch[1];
  if (/^https?:/i.test(href) || /^\/\//.test(href)) continue; // 外部 CDN は無視
  const cssPath = resolve(baseDir, href);
  try {
    linkedCss += '\n' + readFileSync(cssPath, 'utf-8');
  } catch (e) { /* missing stylesheet — 無視 */ }
}

/**
 * @media print ブロックをすべて抽出する
 * ネストされた波括弧に対応
 */
function extractPrintBlocks(source) {
  const blocks = [];
  const regex = /@media\s+print\s*\{/g;
  let match;

  while ((match = regex.exec(source)) !== null) {
    let depth = 1;
    let i = match.index + match[0].length;
    const start = match.index;

    while (i < source.length && depth > 0) {
      if (source[i] === '{') depth++;
      if (source[i] === '}') depth--;
      i++;
    }

    blocks.push(source.slice(start, i));
  }

  return blocks;
}

const printBlocks = extractPrintBlocks(html + '\n' + linkedCss);
const printCSS = printBlocks.join('\n');

// すべての CSS（@media print 外も含む）。全面画像デッキの主キャンバス検出に使う。
const allCss = html + '\n' + linkedCss;

// ============================================================
// 全面画像デッキ検出（後方互換: 自動検出 or --full-image-deck）
// 検出根拠（いずれか）:
//   1) --full-image-deck フラグ明示
//   2) HTML に主キャンバス class（.ai-slide-canvas / .slide-fullbg / .slide-bg）
//   3) structure.md に "full-image-deck" / "全面画像" 宣言、または image-only meta 群
// 通常HTMLデッキはこれらに該当しないため P13/P14 の厳格化は発火しない。
// ============================================================
// 主キャンバスを意味属性 + 許容クラスの union で検出（D2: クラス名密結合回避）
const MAIN_CANVAS_SELECTOR_RE = /(?:data-role\s*=\s*["']main-canvas["']|class\s*=\s*["'][^"']*\b(?:ai-slide-canvas|slide-fullbg|slide-bg)\b[^"']*["'])/;
const hasMainCanvasInHtml = MAIN_CANVAS_SELECTOR_RE.test(html);

function detectFullImageDeck() {
  if (flags.fullImageDeck) return true;
  if (hasMainCanvasInHtml) return true;
  // structure.md / meta 群からの間接検出
  try {
    const structurePath = resolve(baseDir, 'structure.md');
    if (existsSync(structurePath)) {
      const s = readFileSync(structurePath, 'utf-8');
      if (/full-image-deck|全面画像|image-only/i.test(s)) return true;
    }
  } catch (e) { /* ignore */ }
  return false;
}

const isFullImageDeck = detectFullImageDeck();

// ============================================================
// 12項目チェック定義
// ============================================================

const checks = [
  {
    id: 'P01',
    name: 'Chrome拡張非表示',
    severity: 'CRITICAL',
    test: () => /body\s*>\s*\*:not\(\s*\.slider\s*\)/.test(printCSS),
    hint: 'Add to @media print: body>*:not(.slider) { display: none !important; }',
  },
  {
    id: 'P02',
    name: 'スライド番号動的化',
    severity: 'CRITICAL',
    test: () => /attr\s*\(\s*data-total\s*\)/.test(printCSS),
    hint: 'Use content: counter(page) " / " attr(data-total) instead of hardcoded numbers',
  },
  {
    id: 'P03',
    name: 'data-total属性',
    severity: 'CRITICAL',
    test: () => /data-total\s*=/.test(html),
    hint: 'Add data-total="N" attribute to each .slider__item element',
  },
  {
    id: 'P04',
    name: 'print-color-adjust',
    severity: 'CRITICAL',
    test: () =>
      /print-color-adjust\s*:\s*exact/.test(printCSS) ||
      /-webkit-print-color-adjust\s*:\s*exact/.test(printCSS),
    hint: 'Add: print-color-adjust: exact; -webkit-print-color-adjust: exact;',
  },
  {
    id: 'P05',
    name: '@media print内 font-size上書き禁止',
    severity: 'WARNING',
    test: () => {
      // unit-system.md §6.1 R4: @media print 内の font-size 上書きは禁止
      // vw ベースで画面値がそのまま印刷値になるため、上書きは差分発生源となる
      const fontSizes = printCSS.match(/font-size\s*:\s*[^;]+/g) || [];
      return fontSizes.length === 0;
    },
    hint: 'Remove font-size overrides inside @media print (use vw-based values in :root instead)',
  },
  {
    id: 'P06',
    name: 'A4横viewport固定 (297mm; 210mm full-bleed または 16:9 letterbox)',
    severity: 'CRITICAL',
    test: () => {
      // 297mm 幅は両方式で共通の必須条件。
      if (!/297\s*mm/.test(printCSS)) return false;
      // 通常HTMLデッキ: unit-system.md §4.1 の 297mm × 210mm full-bleed。
      const fullBleed210 = /210\s*mm/.test(printCSS);
      if (fullBleed210) return true;
      // 全面画像デッキ: 16:9 を 297mm 幅でレターボックス(height ≈ 167mm)。
      // 210mm を持たない代わりに、height に mm 指定 + aspect-ratio または
      // 167mm 近傍(165-168mm)を許容する。full-image-deck 検出時のみ緩和。
      if (isFullImageDeck) {
        const letterboxHeight = /height\s*:\s*16[5-8](?:\.\d+)?\s*mm/.test(printCSS);
        const aspectRatio = /aspect-ratio\s*:\s*16\s*\/\s*9/.test(allCss);
        return letterboxHeight || aspectRatio;
      }
      // 全面画像デッキでない通常デッキで 210mm 欠落は従来どおり FAIL。
      return false;
    },
    hint: 'Lock html/body to 297mm width in @media print. Standard deck: + 210mm (full-bleed, unit-system.md §4.1). Full-image deck: 16:9 letterbox (height ~167mm or aspect-ratio:16/9).',
  },
  {
    id: 'P07',
    name: 'ページネーション色',
    severity: 'WARNING',
    test: () => {
      // .paginationがprint CSSに存在する場合、color指定があるか
      if (!/\.pagination/.test(printCSS)) return true; // pagination定義なし = スキップ
      // pagination関連でcolor指定があるか
      const paginationSection = printCSS.match(/\.pagination[^{]*\{[^}]*\}/g) || [];
      return paginationSection.some(sec => /\bcolor\s*:/.test(sec));
    },
    hint: 'Add explicit color to .pagination in @media print',
  },
  {
    id: 'P08',
    name: 'isolation',
    severity: 'WARNING',
    test: () => /isolation\s*:\s*isolate/.test(printCSS),
    hint: 'Add: isolation: isolate; to slide containers in @media print',
  },
  {
    id: 'P09',
    name: 'グラデーション代替',
    severity: 'WARNING',
    test: () => {
      // -webkit-background-clip: textがHTML内にある場合、print代替が必要
      if (!/-webkit-background-clip\s*:\s*text/.test(html)) return true;
      // print CSSでbackground: noneまたはcolor指定による代替があるか
      return /background\s*:\s*none/.test(printCSS) ||
             /-webkit-text-fill-color\s*:\s*[^t]/.test(printCSS) ||
             /\.gradient/.test(printCSS);
    },
    hint: 'Add print fallback for gradient text: background: none; color: <solid-color>;',
  },
  {
    id: 'P10',
    name: 'question-badge印刷',
    severity: 'WARNING',
    test: () => {
      // HTMLに.question-badgeがある場合、print CSSにも定義が必要
      if (!/question-badge/.test(html)) return true;
      return /question-badge/.test(printCSS);
    },
    hint: 'Add .question-badge styles to @media print block',
  },
  {
    id: 'P11',
    name: '印刷パディング',
    severity: 'WARNING',
    test: () => /padding\s*:\s*8\s*mm/.test(printCSS) || /padding.*8mm/.test(printCSS),
    hint: 'Add padding: 8mm to slide containers for printer margin safety',
  },
  {
    id: 'P12',
    name: '拡張非表示詳細',
    severity: 'WARNING',
    test: () => {
      // P01の補強: visibility, width, overflow, pseudo-elementの対策
      const hasVisibility = /visibility\s*:\s*hidden/.test(printCSS);
      const hasWidth = /width\s*:\s*0/.test(printCSS) || /max-width\s*:\s*0/.test(printCSS);
      const hasOverflow = /overflow\s*:\s*hidden/.test(printCSS);
      // 少なくとも1つの補強対策があるか
      return hasVisibility || hasWidth || hasOverflow;
    },
    hint: 'Strengthen extension hiding: add visibility:hidden, width:0, overflow:hidden',
  },
  {
    // P13: 全面画像デッキ専用。主キャンバス画像が @media print 内で
    // object-fit:cover を持つと焼込テキスト/被写体が端切れする(D1/D4違反)。
    // 通常HTMLデッキ(主キャンバス無し)はスキップ(test=true)で後方互換。
    id: 'P13',
    name: '全面画像 主キャンバスの印刷cover禁止 (object-fit:contain強制)',
    severity: 'CRITICAL',
    test: () => {
      // 全面画像デッキでない、または主キャンバスが無いならスキップ。
      if (!isFullImageDeck) return true;
      if (printBlocks.length === 0) return true; // 印刷CSSが無ければ判定対象外
      // 主キャンバス（ai-slide-canvas/slide-fullbg/slide-bg/data-role=main-canvas）の
      // img ルールが @media print 内で object-fit:cover を持つかを検出。
      // ルール塊単位で「主キャンバスセレクタ」かつ「object-fit:cover」を持つ宣言を探す。
      const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
      let mm;
      while ((mm = ruleRe.exec(printCSS)) !== null) {
        const selector = mm[1];
        const body = mm[2];
        const isMainCanvas = /(?:ai-slide-canvas|slide-fullbg|slide-bg|\[data-role\s*=\s*["']?main-canvas["']?\])/.test(selector);
        if (!isMainCanvas) continue;
        if (/object-fit\s*:\s*cover/.test(body)) return false; // cover 検出 = FAIL
      }
      return true;
    },
    hint: 'In @media print, main canvas img must be object-fit: contain !important (NOT cover). Cover crops baked text/subject on A4 landscape letterbox.',
  },
  {
    // P14: 全スライドが印刷対象か。page-break-after:always 等が無いと
    // 印刷時に1ページに重なる/欠落する。data-hidden 付きスライドが
    // 意図的除外か漏れかを WARNING で可視化する。
    id: 'P14',
    name: '全スライド印刷対象 (page-break) / data-hidden除外の意図確認',
    severity: 'WARNING',
    test: () => {
      // スライド要素が検出できないデッキはスキップ。
      const slideCount = (html.match(/slider__item/g) || []).length;
      if (slideCount === 0) return true;
      // 印刷でページ分割される仕組みがあるか（page-break-after / break-after / page-break-inside:avoid）。
      const hasPageBreak = /page-break-after\s*:\s*always/.test(printCSS)
        || /break-after\s*:\s*page/.test(printCSS)
        || /page-break-inside\s*:\s*avoid/.test(printCSS)
        || /break-inside\s*:\s*avoid/.test(printCSS);
      // data-hidden 付きスライドの存在（印刷から除外される可能性）。
      const hiddenSlides = (html.match(/data-hidden\s*=\s*["']?true["']?/g) || []).length;
      // ページ分割が無い、または非表示スライドがある場合は要確認(WARNING)。
      // ページ分割があり非表示も無ければ PASS。
      if (!hasPageBreak) return false;
      if (hiddenSlides > 0) return false;
      return true;
    },
    hint: 'Ensure @media print has page-break-after:always (or break-inside:avoid) so every slide prints on its own page. Verify any data-hidden slides are intentionally excluded.',
  },
];

// ============================================================
// チェック実行
// ============================================================
const results = checks.map(check => {
  const passed = check.test();
  return {
    id: check.id,
    name: check.name,
    severity: check.severity,
    passed,
    hint: !passed && flags.fixHints ? check.hint : undefined,
  };
});

// ============================================================
// 結果出力
// ============================================================
const criticalFails = results.filter(r => !r.passed && r.severity === 'CRITICAL');
const warningFails = results.filter(r => !r.passed && r.severity === 'WARNING');
const passCount = results.filter(r => r.passed).length;

if (flags.json) {
  console.log(JSON.stringify({
    file: absPath,
    printBlocksFound: printBlocks.length,
    fullImageDeck: isFullImageDeck,
    total: results.length,
    passed: passCount,
    criticalFails: criticalFails.length,
    warningFails: warningFails.length,
    results,
  }, null, 2));
} else {
  console.log(`\n[print] Print Quality Validation: ${absPath}`);
  console.log(`   @media print blocks found: ${printBlocks.length}`);
  console.log(`   full-image-deck: ${isFullImageDeck ? 'yes' : 'no'}`);
  console.log('─'.repeat(60));

  for (const r of results) {
    const icon = r.passed ? '✅' : (r.severity === 'CRITICAL' ? '❌' : '⚠️');
    const tag = r.passed ? 'PASS' : r.severity;
    console.log(`  ${icon} [${r.id}] ${r.name} — ${tag}`);
    if (r.hint) {
      console.log(`     💡 ${r.hint}`);
    }
  }

  console.log('─'.repeat(60));
  console.log(`  Result: ${passCount}/${results.length} passed`);
  if (criticalFails.length > 0) {
    console.log(`  ❌ ${criticalFails.length} CRITICAL issue(s) found`);
  }
  if (warningFails.length > 0) {
    console.log(`  ⚠️  ${warningFails.length} WARNING(s) found`);
  }
  if (criticalFails.length === 0 && warningFails.length === 0) {
    console.log('  🎉 All checks passed!');
  }
  console.log('');
}

// Exit code: 1 if critical issues, 0 otherwise
process.exit(criticalFails.length > 0 ? 1 : 0);
