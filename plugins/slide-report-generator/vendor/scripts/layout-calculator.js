#!/usr/bin/env node
/**
 * レイアウト計算スクリプト（必須化版）
 *
 * 【新モード（structure.json/structure.md 入力）】
 *   生成前に各スライドのレイアウトオーバーフローを事前検出する。
 *   - 入力: structure.json または structure.md（fence された JSON ブロック）
 *   - 各カードの有効幅・最大文字数/行・必要行数・必要高さを計算
 *   - スライド利用可能高さに対する使用率を算出
 *   - 判定: PASS（<85%） / WARN（85-95%） / FAIL（>95% またはカード単独 overflow）
 *   - 出力: text または json（CIフレンドリー）
 *   - 終了コード: 0=PASS, 1=FAIL, 2=WARN, 3=ARGS_ERROR
 *
 * 【旧モード（HTML 入力）】
 *   既存の HTML 解析・カード/フロー/フォントサイズ推奨機能は --html フラグで継続利用可能。
 *
 * 使用方法:
 *   node scripts/layout-calculator.js <structure-path> [--slide=<id>] [--format=json|text]
 *   node scripts/layout-calculator.js <html-file-path> --html [--json|--css]
 *
 * 計算式（unit-system.md / spec-registry.md SR-1, SR-3, SR-4 準拠）:
 *   カード有効幅 = カード幅(vw) - padding(vw) × 2
 *   1文字幅(JP) = font-size(vw) × 1.0     （全角）
 *   1文字幅(EN) = font-size(vw) × 0.5     （半角）
 *   最大文字数/行 = floor(有効幅 / 1文字幅)
 *   必要行数      = ceil(文字数 / 最大文字数)
 *   必要高さ      = 行数 × font-size × line-height(1.6)
 */

import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { parseArgs, hasFlag } from './utils.js';

// ==================================================
// 定数（spec-registry.md / unit-system.md 由来）
// ==================================================

// ビューポート（vw/vh 基準）
const VIEWPORT_VW = 100; // 1スライド = 100vw × 100vh
const VIEWPORT_VH = 100;

// フォントサイズ（vw）— unit-system.md §3.1
export const FS_VW = {
  title: 6.25,
  subtitle: 3.13,
  heading: 3.75,
  subheading: 2.50,
  'body-lg': 2.25,
  body: 1.88,
  small: 1.75,
};

// レイアウト定数（vw/vh）
const DEFAULT_LINE_HEIGHT = 1.6;
const DEFAULT_SLIDE_PADDING_VW = 5.05; // unit-system.md §3.4 外周 padding
const DEFAULT_SLIDE_PADDING_VH = 5.0;
const DEFAULT_TITLE_HEIGHT_VH = 12;    // タイトル領域（h2 + 余白）
const DEFAULT_FOOTER_HEIGHT_VH = 6;    // 補足/ナビ領域
const DEFAULT_CARD_PADDING_VW = 1.25;  // grid-card padding
const DEFAULT_CARD_GAP_VW = 1.25;      // grid-container gap

// 判定しきい値
const WARN_THRESHOLD = 0.85;
const FAIL_THRESHOLD = 0.95;

// 終了コード（独自）
const EXIT = {
  PASS: 0,
  FAIL: 1,
  WARN: 2,
  ARGS_ERROR: 3,
  FILE_NOT_FOUND: 3,
};

// ==================================================
// CLI（直接実行時のみ）
// ==================================================

// CLI コンテキスト用の遅延変数
let jsonOutput = false;
let cssOutput = false;
let targetSlide = null;

function runCli() {
  const { flags, positional, options } = parseArgs();
  const showHelp = hasFlag(flags, 'help', 'h');
  const htmlMode = hasFlag(flags, 'html');
  jsonOutput = hasFlag(flags, 'json') || options.format === 'json';
  cssOutput = hasFlag(flags, 'css');
  targetSlide = options.slide ?? options['slide-id'] ?? null;
  const inputPath = positional[0];

  if (showHelp) {
    printHelp();
    process.exit(EXIT.PASS);
  }
  if (!inputPath) {
    console.error('ERROR: 入力ファイルパスを指定してください');
    printHelp();
    process.exit(EXIT.ARGS_ERROR);
  }
  if (!existsSync(inputPath)) {
    console.error(`ERROR: ファイルが見つかりません: ${inputPath}`);
    process.exit(EXIT.FILE_NOT_FOUND);
  }
  if (htmlMode || inputPath.endsWith('.html')) {
    runHtmlMode(inputPath);
  } else {
    runStructureMode(inputPath);
  }
}

// 直接実行時のみ CLI 起動（import 時は実行しない）
const __isMain = (() => {
  try {
    return process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
  } catch {
    return false;
  }
})();
if (__isMain) runCli();

// ==================================================
// 構造モード（新機能・必須化の中核）
// ==================================================

/**
 * structure.json/structure.md を読み込み、各スライドのレイアウト判定を行う
 */
export function runStructureMode(filePath) {
  const structure = loadStructure(filePath);
  const slides = Array.isArray(structure) ? structure : (structure.slides || []);

  if (!slides.length) {
    console.error('ERROR: スライド配列が見つかりません（slides[]）');
    process.exit(EXIT.ARGS_ERROR);
  }

  const targets = targetSlide
    ? slides.filter(s => String(s.id) === String(targetSlide) || String(s.num) === String(targetSlide))
    : slides;

  const reports = targets.map(evaluateSlide);
  const overall = aggregate(reports);

  if (jsonOutput) {
    console.log(JSON.stringify({ file: filePath, overall, reports }, null, 2));
  } else {
    printTextReport(filePath, overall, reports);
  }

  process.exit(overall.verdict === 'FAIL' ? EXIT.FAIL : overall.verdict === 'WARN' ? EXIT.WARN : EXIT.PASS);
}

/**
 * structure.md（コードフェンス内 JSON）または .json を読み込み
 */
export function loadStructure(filePath) {
  const raw = readFileSync(filePath, 'utf-8');
  if (filePath.endsWith('.json')) {
    return JSON.parse(raw);
  }
  // .md からの抽出: ```json ... ``` ブロックを優先
  const fence = raw.match(/```json\s*([\s\S]*?)```/);
  if (fence) return JSON.parse(fence[1]);
  // それでもない場合、生テキストで JSON.parse 試行
  try {
    return JSON.parse(raw);
  } catch {
    throw new Error(`structure ファイルから JSON を抽出できません: ${filePath}`);
  }
}

/**
 * 単一スライドのレイアウト判定
 * @param {Object} slide - { id, type, title, cards: [{ heading, body, fontSize? }], layout? }
 */
export function evaluateSlide(slide) {
  const id = slide.id ?? slide.num ?? '?';
  const type = slide.type ?? 'unknown';
  const cards = slide.cards ?? slide.items ?? [];
  const layout = slide.layout ?? {};

  // スライド全体の利用可能高さ（vh）
  const titleH = layout.titleHeightVh ?? DEFAULT_TITLE_HEIGHT_VH;
  const footerH = layout.footerHeightVh ?? DEFAULT_FOOTER_HEIGHT_VH;
  const slidePadVh = layout.slidePaddingVh ?? DEFAULT_SLIDE_PADDING_VH;
  const availableHeightVh = VIEWPORT_VH - titleH - footerH - slidePadVh * 2;

  // カード列数
  const columns = layout.columns ?? Math.min(cards.length || 1, 4);
  const rows = Math.ceil((cards.length || 1) / columns);
  const cardGapVw = layout.cardGapVw ?? DEFAULT_CARD_GAP_VW;
  const slidePadVw = layout.slidePaddingVw ?? DEFAULT_SLIDE_PADDING_VW;

  // カード幅（vw）
  const contentWidthVw = VIEWPORT_VW - slidePadVw * 2;
  const cardWidthVw = (contentWidthVw - cardGapVw * (columns - 1)) / columns;
  const cardPaddingVw = layout.cardPaddingVw ?? DEFAULT_CARD_PADDING_VW;
  const effectiveCardWidthVw = cardWidthVw - cardPaddingVw * 2;

  // 各カード判定
  const cardReports = cards.map((card, idx) => evaluateCard(card, {
    effectiveCardWidthVw,
    cardWidthVw,
    cardPaddingVw,
    columnIndex: idx % columns,
    rowIndex: Math.floor(idx / columns),
  }));

  // 行ごとの最大高さの合計
  const rowHeights = [];
  for (let r = 0; r < rows; r++) {
    const inRow = cardReports.filter(c => c._rowIndex === r);
    const max = inRow.reduce((m, c) => Math.max(m, c.requiredHeightVh), 0);
    rowHeights.push(max);
  }
  const totalRowHeightVh = rowHeights.reduce((a, b) => a + b, 0);
  const totalGapVh = (rows - 1) * (layout.rowGapVh ?? 2);
  const usedHeightVh = totalRowHeightVh + totalGapVh;
  const usageRatio = usedHeightVh / availableHeightVh;

  // 個別 overflow 判定
  const anyCardOverflow = cardReports.some(c => c.fits === false);

  // 総合判定
  let verdict = 'PASS';
  if (usageRatio > FAIL_THRESHOLD || anyCardOverflow) verdict = 'FAIL';
  else if (usageRatio > WARN_THRESHOLD) verdict = 'WARN';

  // 改善提案
  const recommendations = buildRecommendations({
    verdict, usageRatio, cardReports, columns, cards,
  });

  return {
    id,
    type,
    verdict,
    columns,
    rows,
    availableHeightVh: round(availableHeightVh),
    usedHeightVh: round(usedHeightVh),
    usageRatio: round(usageRatio, 4),
    cardWidthVw: round(cardWidthVw),
    effectiveCardWidthVw: round(effectiveCardWidthVw),
    cards: cardReports.map(stripInternal),
    recommendations,
  };
}

/**
 * 単一カードの判定
 */
export function evaluateCard(card, ctx) {
  const heading = card.heading ?? card.title ?? '';
  const body = card.body ?? card.text ?? card.description ?? '';
  const headingFsKey = card.headingFs ?? 'subheading';
  const bodyFsKey = card.bodyFs ?? 'body';
  const headingFsVw = typeof headingFsKey === 'number' ? headingFsKey : (FS_VW[headingFsKey] ?? FS_VW.subheading);
  const bodyFsVw = typeof bodyFsKey === 'number' ? bodyFsKey : (FS_VW[bodyFsKey] ?? FS_VW.body);

  const headingMetrics = textMetrics(heading, headingFsVw, ctx.effectiveCardWidthVw);
  const bodyMetrics = textMetrics(body, bodyFsVw, ctx.effectiveCardWidthVw);

  const requiredHeightVh = vwToVh(headingMetrics.heightVw + bodyMetrics.heightVw)
    + (ctx.cardPaddingVw * 2) * (VIEWPORT_VH / VIEWPORT_VW); // 上下 padding を vh 換算

  // カード単独の物理上限（カード幅の 0.6 倍を vh 換算した高さを「縦長すぎ警戒」として目安）
  const cardMaxHeightVh = vwToVh(ctx.cardWidthVw * 0.9);
  const fits = requiredHeightVh <= cardMaxHeightVh;

  return {
    heading: clip(heading),
    body: clip(body),
    headingChars: countChars(heading),
    bodyChars: countChars(body),
    headingMaxCharsPerLine: headingMetrics.maxCharsPerLine,
    bodyMaxCharsPerLine: bodyMetrics.maxCharsPerLine,
    headingLines: headingMetrics.lines,
    bodyLines: bodyMetrics.lines,
    requiredHeightVh: round(requiredHeightVh),
    cardMaxHeightVh: round(cardMaxHeightVh),
    fits,
    _rowIndex: ctx.rowIndex,
  };
}

/**
 * テキストメトリクス計算（日本語/英数字混在対応）
 */
export function textMetrics(text, fontSizeVw, effectiveWidthVw) {
  if (!text) return { lines: 0, maxCharsPerLine: 0, heightVw: 0 };

  // 全角/半角を加味した実効文字数（half-width=0.5, full-width=1.0）
  const effectiveCharCount = effectiveWidth(text);

  // 1文字の平均幅（vw）— 全角ベース基準で fontSize 相当
  const avgCharWidthVw = fontSizeVw; // 全角=1.0換算で取得済みのため
  const maxCharsPerLine = Math.max(1, Math.floor(effectiveWidthVw / avgCharWidthVw));

  // 改行（\n）も尊重
  const explicitLines = text.split(/\r?\n/);
  let totalLines = 0;
  for (const ln of explicitLines) {
    const w = effectiveWidth(ln);
    totalLines += Math.max(1, Math.ceil(w / maxCharsPerLine));
  }

  const heightVw = totalLines * fontSizeVw * DEFAULT_LINE_HEIGHT;
  return { lines: totalLines, maxCharsPerLine, heightVw, effectiveCharCount };
}

/**
 * 全角=1.0、半角=0.5 で「全角換算文字数」を返す
 */
export function effectiveWidth(s) {
  let w = 0;
  for (const ch of s) {
    // 半角: ASCII or Halfwidth Katakana
    if (/[\x20-\x7E｡-ﾟ]/.test(ch)) w += 0.5;
    else w += 1.0;
  }
  return w;
}

function countChars(s) {
  return [...(s || '')].length;
}

function vwToVh(vw) {
  // 16:9 viewport で 1vw = (100/56.25) vh → ただし unit-system では 100vh も使用するため
  // 単純比例で 1vw ≒ 1vh （基準解像度 1280×720 では実質同等）として扱う
  return vw;
}

function round(n, d = 2) {
  const p = Math.pow(10, d);
  return Math.round(n * p) / p;
}

function clip(s, max = 40) {
  s = String(s ?? '');
  return s.length > max ? s.slice(0, max) + '…' : s;
}

function stripInternal(o) {
  const { _rowIndex, ...rest } = o;
  return rest;
}

/**
 * 改善提案
 */
function buildRecommendations({ verdict, usageRatio, cardReports, columns, cards }) {
  const recs = [];
  if (verdict === 'PASS') {
    recs.push('レイアウトは余裕あり。生成可');
    return recs;
  }
  if (usageRatio > FAIL_THRESHOLD) {
    recs.push(`高さ使用率 ${(usageRatio * 100).toFixed(1)}% (>95%) — オーバーフロー確実`);
  } else if (usageRatio > WARN_THRESHOLD) {
    recs.push(`高さ使用率 ${(usageRatio * 100).toFixed(1)}% (85-95%) — 余裕薄い`);
  }
  const overflowCards = cardReports.filter(c => !c.fits);
  if (overflowCards.length) {
    recs.push(`${overflowCards.length}枚のカードが個別オーバーフロー`);
  }
  // 提案
  if (cards.length > columns * 2) {
    recs.push('要素数を減らす（カードを 2 行以内に収める）');
  }
  if (cardReports.some(c => c.bodyLines > 4)) {
    recs.push('本文を 4 行以内に短縮 / fs-small への縮小を検討');
  }
  if (cardReports.some(c => c.bodyMaxCharsPerLine < 10)) {
    recs.push('カード幅が狭すぎる — columns を減らすか slidePaddingVw を縮小');
  }
  if (verdict === 'FAIL') {
    recs.push('structure-designer に差し戻し（HTML生成しない）');
  }
  return recs;
}

/**
 * 全スライド集計
 */
function aggregate(reports) {
  const fail = reports.filter(r => r.verdict === 'FAIL').length;
  const warn = reports.filter(r => r.verdict === 'WARN').length;
  const pass = reports.filter(r => r.verdict === 'PASS').length;
  const verdict = fail > 0 ? 'FAIL' : warn > 0 ? 'WARN' : 'PASS';
  return { total: reports.length, pass, warn, fail, verdict };
}

/**
 * テキストレポート出力
 */
function printTextReport(filePath, overall, reports) {
  console.log('================================================================');
  console.log('  layout-calculator: 事前レイアウト判定');
  console.log('================================================================');
  console.log(`File: ${filePath}`);
  console.log(`Total: ${overall.total} slides | PASS=${overall.pass} WARN=${overall.warn} FAIL=${overall.fail}`);
  console.log(`Overall: ${overall.verdict}`);
  console.log('');

  for (const r of reports) {
    const mark = r.verdict === 'PASS' ? '[OK]' : r.verdict === 'WARN' ? '[WARN]' : '[FAIL]';
    console.log(`${mark} slide=${r.id} type=${r.type} usage=${(r.usageRatio * 100).toFixed(1)}% (used ${r.usedHeightVh}vh / avail ${r.availableHeightVh}vh)`);
    console.log(`     cards=${r.cards.length} cols=${r.columns} rows=${r.rows} cardWidth=${r.cardWidthVw}vw effW=${r.effectiveCardWidthVw}vw`);
    for (const c of r.cards) {
      const cf = c.fits ? 'fit' : 'OVERFLOW';
      console.log(`     - "${c.heading}" body=${c.bodyChars}chars lines=${c.bodyLines} req=${c.requiredHeightVh}vh max=${c.cardMaxHeightVh}vh [${cf}]`);
    }
    for (const rec of r.recommendations) {
      console.log(`     > ${rec}`);
    }
    console.log('');
  }
}

// ==================================================
// HTML モード（旧機能の保持）
// ==================================================

function runHtmlMode(htmlPath) {
  const html = readFileSync(htmlPath, 'utf-8');
  const slides = extractSlidesFromHtml(html);
  const layouts = slides
    .filter(s => !targetSlide || String(s.num) === String(targetSlide))
    .map(calculateSlideLayoutFromHtml);

  const results = {
    file: htmlPath,
    mode: 'html',
    totalSlides: slides.length,
    layouts,
  };

  if (jsonOutput) {
    console.log(JSON.stringify(results, null, 2));
  } else if (cssOutput) {
    console.log(generateCssFromLayouts(layouts));
  } else {
    console.log(`HTML mode: ${slides.length} slides analyzed`);
    layouts.forEach(l => {
      console.log(`  slide ${l.slideNum} [${l.type}]: ${l.recommendations.join(', ') || 'no adjustments'}`);
    });
  }
  process.exit(EXIT.PASS);
}

function extractSlidesFromHtml(html) {
  const slides = [];
  const slideRegex = /<div[^>]*class="[^"]*slider__item[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*slider__item|<\/div>\s*<\/div>\s*<nav)/g;
  let match;
  let slideNum = 0;
  while ((match = slideRegex.exec(html)) !== null) {
    slideNum++;
    const content = match[1];
    const typeMatch = match[0].match(/slide-(\w+)/);
    const type = typeMatch ? typeMatch[1] : 'unknown';
    const cardCount = (content.match(/class="[^"]*(?:card|point-card|compare-item|grid-card)[^"]*"/g) || []).length;
    const flowSteps = (content.match(/class="[^"]*flow-step[^"]*"/g) || []).length;
    const listItems = (content.match(/<li[^>]*>/g) || []).length;
    const textContent = content.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    const textLength = textContent.length;
    const textLines = content.match(/<(?:h1|h2|h3|p|li|span)[^>]*>([^<]+)</g) || [];
    const maxLineLength = Math.max(...textLines.map(l => l.replace(/<[^>]+>/g, '').length), 0);
    slides.push({ num: slideNum, type, cardCount, flowSteps, listItems, textLength, maxLineLength });
  }
  return slides;
}

function calculateSlideLayoutFromHtml(slide) {
  const layout = { slideNum: slide.num, type: slide.type, recommendations: [] };
  if (slide.cardCount > 0) {
    layout.cards = { count: slide.cardCount };
    layout.recommendations.push(`cards: ${slide.cardCount}`);
  }
  if (slide.flowSteps > 0) {
    layout.flow = { steps: slide.flowSteps };
    layout.recommendations.push(`flow: ${slide.flowSteps} steps`);
  }
  if (slide.textLength > 200) {
    layout.recommendations.push(`text-heavy: ${slide.textLength} chars`);
  }
  return layout;
}

function generateCssFromLayouts(layouts) {
  return layouts.map(l => `/* slide ${l.slideNum} (${l.type}) */`).join('\n');
}

// ==================================================
// ヘルプ
// ==================================================

function printHelp() {
  console.log(`
layout-calculator — 事前レイアウト判定スクリプト

使用方法:
  node scripts/layout-calculator.js <structure-path> [--slide=<id>] [--format=json|text]
  node scripts/layout-calculator.js <html-path> --html [--json|--css]

structure モード（必須化の本機能）:
  入力: structure.json または structure.md（json コードフェンス内）
  出力: 各スライドの PASS/WARN/FAIL 判定 + 改善提案
  終了コード: 0=PASS, 1=FAIL, 2=WARN, 3=ARGS_ERROR

オプション:
  --slide=<id>      特定スライドのみ判定
  --format=json     JSON 形式で出力（デフォルト: text）
  --json            旧称、--format=json と同義
  --html            HTML モード（旧機能）
  --css             HTML モード時に CSS 変数として出力
  --help, -h        このヘルプを表示

structure JSON スキーマ（最低限）:
  {
    "slides": [
      {
        "id": "S1",
        "type": "grid",
        "title": "タイトル",
        "layout": { "columns": 3, "cardPaddingVw": 1.25 },
        "cards": [
          { "heading": "見出し", "body": "本文…", "headingFs": "subheading", "bodyFs": "body" }
        ]
      }
    ]
  }
`);
}
