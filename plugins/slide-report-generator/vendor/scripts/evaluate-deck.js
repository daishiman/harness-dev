#!/usr/bin/env node
/**
 * evaluate-deck.js — 生成後評価オーケストレータ（機械評価の正本）
 *
 * 生成済みプレゼンデッキ（index.html + styles.css + scripts.js + structure.*）を
 * 評価し、視覚崩れ・ナビ・仕様適合を機械的に判定して統合レポートを出力する。
 * 思考リセット後30種思考法のLLM評価（deck-evaluator.md）と対をなす「機械の目」。
 *
 * 設計原則:
 *  - 既存資産を再利用（重複実装しない）: sync-checker.js / validate-structure.js /
 *    check-consistency.js / verify-slides.js と同じ手法を集約する。
 *  - chromium 非依存の static 検証を常時動作の中核にし、dynamic(playwright) は
 *    存在すれば enhance・無ければ WARN でスキップ（graceful degradation）。
 *  - ナビ命名は3系統混在（.pg-* / .section-nav / .nav__*）。機能ベースの
 *    複数セレクタ union + aria/キーボードヒューリスティックで検出する。
 *
 * 評価次元:
 *  - Dx 動作可能性  : CSS/JSの実在・スライド表示切替の定義・ページ送り制御の実在（static・CRITICAL）
 *  - D1 視覚的崩れ  : 型崩れ・画像欠落（static）/ broken img・カードはみ出し・16:9（dynamic）
 *  - D2 文字サイズ  : SVGテキスト<13px・rem<1.4（static）/ computed px（dynamic）
 *  - D3 ナビ        : 左右送り・ページネーション・上部インデックス・カウンター・進捗（static）
 *  - D4 仕様適合    : sync-checker / validate-structure を集約（static）+
 *                    全面画像デッキ検出時は validate-print / validate-ai-image-assets を集約
 *  - D5 要望↔構成   : LLM限定（deck-evaluator が判定）。本scriptは "pending-llm" を記録のみ
 *
 * CHANGELOG:
 *  - v3 (2026-06-26, operability-gate Dx): styles.css / scripts.js 欠落により
 *    index.html を開いてもスライドが動かない事故（ページ送り不可・全スライド非切替）を
 *    CRITICAL で検出する Dx「動作可能性／自己完結性」を追加。chromium 非依存の static 解析で
 *    (1) 参照CSSの実在＋非空 or <style>インライン (2) 参照JSの実在＋非空 or <script>インライン
 *    (3) .slider__item の表示切替CSS(opacity/visibility/display × is-active/active)
 *    (4) ページ送り制御JS(querySelectorAll('.slider__item') + active付替 / arrow / 各種ナビID)
 *    を検査。いずれか欠落で Dx error→verdict FAIL。命名2系統(is-active/active・prevBtn系/arrow系)
 *    の双方を union 検出し誤検知を抑制。D1〜D5・既存出力・終了コードは不変（後方互換）。
 *  - v2 (2026-06-24, elegant-review D3): 全面画像デッキ(full-image-deck)検出時に
 *    validate-print.js と validate-ai-image-assets.js --full-image-deck
 *    --strict-style-genome を子プロセスで実行し、CRITICAL/exit非0を D4 error に昇格。
 *    これにより印刷cover端切れ・主キャンバスclass乖離・imageFit欠落・plan.json迂回が
 *    出荷ゲート(verdict)に接続される。通常HTMLデッキはこれらを spawn せず後方互換。
 *
 * 使用方法:
 *   node scripts/evaluate-deck.js <deck-dir | index.html> [options]
 *
 * オプション:
 *   --json            統合レポートをJSONで標準出力
 *   --static-only     dynamic(playwright)検証をスキップ（フック用・高速）
 *   --report <path>   レポートJSONの出力先（既定: <deck-dir>/evaluation-report.json）
 *   --no-write        レポートファイルを書き出さない
 *   --strict          WARN も失敗(exit 4)扱い
 *   --help, -h        ヘルプ
 *
 * 終了コード: 0=PASS / 4=FAIL(error あり、--strictならWARNでも) / 2=引数 / 3=不在
 */

import { existsSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from 'fs';
import { dirname, join, basename, resolve, isAbsolute } from 'path';
import { tmpdir } from 'os';
import { spawnSync } from 'child_process';
import { parseArgs, hasFlag, EXIT_CODES, getDirname, VIEWPORT } from './utils.js';
import {
  configurePluginLocalPlaywright,
  setupCommand,
} from './playwright-runtime.js';

const __dirname = getDirname(import.meta.url);
configurePluginLocalPlaywright();

// ==================================================
// 設定（閾値・セレクタ）— 視覚回帰テスト同様、ここを調整すれば基準を変えられる
// ==================================================
const CONFIG = {
  // dynamic computed font-size の最小値（px）。1080pxビューポートで body は概ね15px+
  bodyFontMinPx: 12,
  // SVG <text> の最小（S22 と一致）
  svgTextMinPx: 13,
  // static で rem 直書きが小さすぎると見なす閾値
  remMin: 1.4,
  // はみ出し許容誤差（px）
  overflowTolPx: 2,
  // カードとみなす要素のセレクタ（dynamic はみ出し検査対象）
  cardSelectors: [
    '.fo-card', '[class*="card"]', '.list-item', '[class*="stat"]',
    '.chip', '[class*="chip"]', '.point', '[class*="box"]'
  ],
  // ナビ機能の検出パターン（命名3系統 union + heuristic）
  nav: {
    prev: [/pg-controls__btn--prev/, /id=["']prevBtn["']/, /class=["'][^"']*\bprev[^"']*["']/, /aria-label=["'][^"']*前[^"']*["']/, /\bArrowLeft\b/],
    next: [/pg-controls__btn--next/, /id=["']nextBtn["']/, /class=["'][^"']*\bnext[^"']*["']/, /aria-label=["'][^"']*次[^"']*["']/, /\bArrowRight\b/],
    dots: [/pg-dots/, /nav__dots/, /id=["']dots["']/, /class=["'][^"']*\bdots\b[^"']*["']/, /buildDots|buildNavigation/],
    counter: [/pg-counter/, /nav__counter/, /id=["']counter["']/, /class=["'][^"']*counter[^"']*["']/],
    progress: [/pg-progress/, /progress__bar/, /class=["'][^"']*progress[^"']*["']/, /\bprogressBar\b/],
    topIndex: [/pg-section-nav/, /\bsection-nav\b/, /agenda-indicator/, /agenda-nav/, /class=["'][^"']*(agenda|index-nav|\btoc\b)[^"']*["']/]
  }
};

// 次元の人間可読名
const DIMENSIONS = {
  Dx: '動作可能性/自己完結性',
  D1: '視覚的崩れ',
  D2: '文字サイズ',
  D3: 'ナビ/ページネーション/インデックス',
  D4: '仕様適合',
  D5: '要望↔構成の整合(LLM)'
};

// ==================================================
// 引数
// ==================================================
const { flags, positional, options } = parseArgs();

if (hasFlag(flags, 'help', 'h')) {
  console.log(`
evaluate-deck.js — 生成後評価オーケストレータ

使用方法:
  node scripts/evaluate-deck.js <deck-dir | index.html> [options]

オプション:
  --json            統合レポートをJSONで標準出力
  --static-only     dynamic(playwright)検証をスキップ（フック用・高速）
  --report <path>   レポートJSONの出力先（既定: <deck-dir>/evaluation-report.json）
  --no-write        レポートファイルを書き出さない
  --strict          WARN も失敗(exit 4)扱い
  --help, -h        ヘルプ

終了コード: 0=PASS / 4=FAIL / 2=引数エラー / 3=ファイル不在
`);
  process.exit(EXIT_CODES.SUCCESS);
}

const target = positional[0];
if (!target) {
  console.error('❌ 評価対象（デッキディレクトリ または index.html）を指定してください');
  console.error('   例: node scripts/evaluate-deck.js ./05_Project/スライド/slide-xxx/');
  process.exit(EXIT_CODES.ARGS_ERROR);
}

const staticOnly = hasFlag(flags, 'static-only');
const jsonOut = hasFlag(flags, 'json');
const noWrite = hasFlag(flags, 'no-write');
const strict = hasFlag(flags, 'strict');

// ==================================================
// 入力解決
// ==================================================
const absTarget = isAbsolute(target) ? target : resolve(process.cwd(), target);
let deckDir, indexPath;
if (absTarget.endsWith('.html')) {
  indexPath = absTarget;
  deckDir = dirname(absTarget);
} else {
  deckDir = absTarget;
  indexPath = join(deckDir, 'index.html');
}

if (!existsSync(indexPath)) {
  console.error(`❌ index.html が見つかりません: ${indexPath}`);
  process.exit(EXIT_CODES.FILE_NOT_FOUND);
}

const cssPath = join(deckDir, 'styles.css');
const jsPath = join(deckDir, 'scripts.js');
const structureMd = join(deckDir, 'structure.md');
const structureJson = join(deckDir, 'structure.json');

const html = readFileSync(indexPath, 'utf-8');
const css = existsSync(cssPath) ? readFileSync(cssPath, 'utf-8') : '';
const js = existsSync(jsPath) ? readFileSync(jsPath, 'utf-8') : '';
const combined = `${html}\n${css}\n${js}`;

// ==================================================
// finding 収集
// ==================================================
const findings = [];
let fid = 0;
function add(dimension, severity, title, detail, extra = {}) {
  fid += 1;
  findings.push({
    id: `F${String(fid).padStart(3, '0')}`,
    dimension,
    severity, // 'error' | 'warn' | 'info'
    title,
    detail,
    ...extra
  });
}

// ==================================================
// Dx: 動作可能性／自己完結性（static・CRITICAL）
//   実運用事故対策: styles.css / scripts.js 欠落で index.html を開いても
//   スライドが動かない（ページ送り不可・全スライド非切替）状態を CRITICAL で検出する。
//   chromium 非依存。index.html が「実際に参照している」CSS/JS を相対解決して実体検査する。
// ==================================================

// index.html 内のローカル参照（http(s)/data/CDN を除く相対パス）を抽出する汎用ヘルパ。
// 外部参照は index.html と同じディレクトリからの相対パスとして deckDir 基準で解決する。
function resolveLocalRefs(urls) {
  const out = [];
  for (const raw of urls) {
    const url = (raw || '').trim();
    if (!url) continue;
    if (/^(https?:)?\/\//i.test(url)) continue; // 外部/CDN
    if (url.startsWith('data:')) continue;       // インライン data URI
    if (url.startsWith('#')) continue;           // アンカー
    if (/^[a-z]+:/i.test(url) && !isAbsolute(url)) continue; // mailto: 等のスキーム
    const clean = url.split('?')[0].split('#')[0];
    const abs = isAbsolute(clean) ? clean : resolve(deckDir, clean);
    out.push({ ref: clean, abs });
  }
  return out;
}

// 参照ファイル群の実体（存在＋非空）を読んで結合テキストを返す。
// {present: boolean, content: string, missing: string[], empty: string[]}
function readRefFiles(refs) {
  let content = '';
  const missing = [];
  const empty = [];
  let present = false;
  for (const { ref, abs } of refs) {
    if (!existsSync(abs)) { missing.push(ref); continue; }
    let body = '';
    try { body = readFileSync(abs, 'utf-8'); } catch { missing.push(ref); continue; }
    if (body.trim().length === 0) { empty.push(ref); continue; }
    present = true;
    content += `\n${body}`;
  }
  return { present, content, missing, empty };
}

// .slider__item の表示切替が定義されているか（opacity/visibility/display ×
// .is-active または .active）。命名2系統（is-active / active）の双方を許容する。
function hasSlideToggleCss(cssText) {
  if (!cssText) return false;
  // 例: .slider__item.is-active { opacity: 1; } / .slider__item.active { display: flex; }
  const activeRuleRe = /\.slider__item\.(?:is-active|active)\b[^{}]*\{[^{}]*(?:opacity|visibility|display)\s*:/i;
  if (activeRuleRe.test(cssText)) return true;
  // 基底 .slider__item に opacity/visibility/display があり、かつ別途 .is-active/.active 規則がある構成
  const baseRe = /\.slider__item\b[^.{][^{}]*\{[^{}]*(?:opacity|visibility|display)\s*:/i;
  const activeSelRe = /\.slider__item\.(?:is-active|active)\b/i;
  return baseRe.test(cssText) && activeSelRe.test(cssText);
}

// ページ送り制御の実体があるか（スライド集合の取得 + アクティブ付替、または
// 矢印キー/各種ナビID制御）。命名2系統（prevBtn系 / arrowLeft系）双方を union 検出。
function hasPagingControlJs(jsText) {
  if (!jsText) return false;
  const collectSlides = /querySelectorAll\(\s*['"]\.slider__item['"]\s*\)/.test(jsText);
  const toggleActive = /classList\.(?:add|remove|toggle)\(\s*['"](?:is-active|active)['"]/.test(jsText);
  // スライド集合を取得して active を付替える実装は「動く」中核条件
  if (collectSlides && toggleActive) return true;
  // ナビ制御識別子（prevBtn/nextBtn/dots/counter 系 or arrowLeft/arrowRight/slideCounter/pageNav 系）
  const navIdRe = /getElementById\(\s*['"](?:prevBtn|nextBtn|dots|counter|arrowLeft|arrowRight|slideCounter|pageNav)['"]\s*\)/;
  const arrowKeyRe = /\b(?:ArrowLeft|ArrowRight)\b/;
  // 矢印キーまたはナビIDの制御があり、かつスライド集合の取得があれば動作実体ありとみなす
  if (collectSlides && (navIdRe.test(jsText) || arrowKeyRe.test(jsText))) return true;
  return false;
}

function checkOperability() {
  // (1) CSS の実在: index.html が参照する <link rel="stylesheet" href="..."> 各CSSが
  //     実在し空でない。または <style>...</style> でインラインされている。
  const linkRe = /<link\b[^>]*\brel\s*=\s*["']?stylesheet["']?[^>]*>/gi;
  const cssUrls = [];
  let lm;
  while ((lm = linkRe.exec(html)) !== null) {
    const hrefM = lm[0].match(/\bhref\s*=\s*["']([^"']+)["']/i);
    if (hrefM) cssUrls.push(hrefM[1]);
  }
  const cssRefs = resolveLocalRefs(cssUrls);
  const cssFiles = readRefFiles(cssRefs);
  const hasInlineStyle = /<style\b[^>]*>[\s\S]*?\S[\s\S]*?<\/style>/i.test(html);
  // 検査用CSSテキスト: 実在した外部CSS + インライン<style> + 念のため固定パスのstyles.css
  let inlineStyleText = '';
  const styleBlockRe = /<style\b[^>]*>([\s\S]*?)<\/style>/gi;
  let sm;
  while ((sm = styleBlockRe.exec(html)) !== null) inlineStyleText += `\n${sm[1]}`;
  const cssForCheck = `${cssFiles.content}\n${inlineStyleText}\n${css}`;

  if (!cssFiles.present && !hasInlineStyle) {
    const why = cssRefs.length === 0
      ? 'index.html が CSS を一切参照しておらず（<link rel="stylesheet"> も <style> も無い）'
      : `参照CSSの実体が無い（欠落: ${cssFiles.missing.join(', ') || 'なし'} / 空: ${cssFiles.empty.join(', ') || 'なし'}）`;
    add('Dx', 'error', 'CSSが自己完結していない（スライドが正しく表示されない）',
      `${why}。styles.css 等の参照CSSが実在し非空であるか、<style> でインライン化されている必要がある。CSSが無いとレイアウトとスライド表示切替が機能しない。`,
      { check: 'operability.css', missing: cssFiles.missing });
  } else {
    add('Dx', 'info', 'CSSの自己完結を確認',
      `${cssFiles.present ? `外部CSS ${cssRefs.length - cssFiles.missing.length - cssFiles.empty.length}件実在` : ''}${cssFiles.present && hasInlineStyle ? ' / ' : ''}${hasInlineStyle ? 'インライン<style>あり' : ''}`.trim() || 'CSSあり',
      { check: 'operability.css' });
  }

  // (2) JS の実在: index.html が参照する <script src="..."> 各JSが実在し空でない。
  //     または <script>...</script> でインラインされている。
  const scriptRefs = [];
  const scriptTagRe = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let stm;
  let inlineScriptText = '';
  while ((stm = scriptTagRe.exec(html)) !== null) {
    const attrs = stm[1] || '';
    const body = stm[2] || '';
    const srcM = attrs.match(/\bsrc\s*=\s*["']([^"']+)["']/i);
    if (srcM) scriptRefs.push(srcM[1]);
    else if (body.trim().length > 0) inlineScriptText += `\n${body}`;
  }
  const jsRefs = resolveLocalRefs(scriptRefs);
  const jsFiles = readRefFiles(jsRefs);
  const hasInlineScript = inlineScriptText.trim().length > 0;
  // 検査用JSテキスト: 実在した外部JS + インライン<script> + 念のため固定パスのscripts.js
  const jsForCheck = `${jsFiles.content}\n${inlineScriptText}\n${js}`;

  if (!jsFiles.present && !hasInlineScript) {
    const why = jsRefs.length === 0
      ? 'index.html がローカルJSを参照しておらず（<script src> も インライン<script> も無い）'
      : `参照JSの実体が無い（欠落: ${jsFiles.missing.join(', ') || 'なし'} / 空: ${jsFiles.empty.join(', ') || 'なし'}）`;
    add('Dx', 'error', 'JSが自己完結していない（ページ送りができない）',
      `${why}。scripts.js 等の参照JSが実在し非空であるか、<script> でインライン化されている必要がある。JSが無いとページ送り・スライド切替が一切動かない。`,
      { check: 'operability.js', missing: jsFiles.missing });
  } else {
    add('Dx', 'info', 'JSの自己完結を確認',
      `${jsFiles.present ? `外部JS ${jsRefs.length - jsFiles.missing.length - jsFiles.empty.length}件実在` : ''}${jsFiles.present && hasInlineScript ? ' / ' : ''}${hasInlineScript ? 'インライン<script>あり' : ''}`.trim() || 'JSあり',
      { check: 'operability.js' });
  }

  // (3) スライド表示切替の定義（CSS）: .slider__item の表示切替（opacity/visibility/display
  //     × .is-active|.active）が定義されているか。無ければ全スライドが重なる/出ない。
  if (!hasSlideToggleCss(cssForCheck)) {
    add('Dx', 'error', 'スライド表示切替CSSが未定義（全スライドが重なる/表示されない）',
      '.slider__item の表示切替（opacity/visibility/display と .is-active または .active）がCSSに見当たらない。これが無いと全スライドが同時表示・重なり、1枚ずつの切替ができない。',
      { check: 'operability.slideToggleCss' });
  } else {
    add('Dx', 'info', 'スライド表示切替CSSを確認',
      '.slider__item のアクティブ時表示切替（opacity/visibility/display）を検出。', { check: 'operability.slideToggleCss' });
  }

  // (4) ページ送り制御の実在（JS）: スライド集合取得 + active 付替、または矢印キー/ナビID制御。
  //     無ければナビが動かない（ページ送り不能）。
  if (!hasPagingControlJs(jsForCheck)) {
    add('Dx', 'error', 'ページ送り制御JSが未実装（ナビが動かない）',
      "JSにスライド送りの実体が見当たらない（querySelectorAll('.slider__item') + active 付替、または ArrowLeft/ArrowRight・prevBtn/nextBtn/dots/counter（arrowLeft/arrowRight/slideCounter/pageNav）の制御）。これが無いとページ送り・スライド切替が動作しない。",
      { check: 'operability.pagingJs' });
  } else {
    add('Dx', 'info', 'ページ送り制御JSを確認',
      'スライド集合の取得とアクティブ切替（またはキーボード/ナビID制御）を検出。', { check: 'operability.pagingJs' });
  }
}

// ==================================================
// D3: ナビ/ページネーション/インデックス（static・機能ベース union 検出）
// ==================================================
function present(patterns) {
  return patterns.some((re) => re.test(combined));
}
function checkNavigation() {
  const hasPrev = present(CONFIG.nav.prev);
  const hasNext = present(CONFIG.nav.next);
  const hasDots = present(CONFIG.nav.dots);
  const hasCounter = present(CONFIG.nav.counter);
  const hasProgress = present(CONFIG.nav.progress);
  const hasTopIndex = present(CONFIG.nav.topIndex);

  if (!hasPrev || !hasNext) {
    add('D3', 'error', '左右ページ送りが検出できない',
      `前へ(${hasPrev ? 'あり' : 'なし'})/次へ(${hasNext ? 'あり' : 'なし'})。両サイドの左右送りナビ（prev/next ボタン または ←/→ キー）が必要。`,
      { check: 'nav.prevNext' });
  } else {
    add('D3', 'info', '左右ページ送りを検出',
      '前へ/次への送りを検出。ただし「両サイド配置」かは視覚判定（deck-evaluator）で確認すること。',
      { check: 'nav.prevNext' });
  }

  if (!hasDots) {
    add('D3', 'warn', 'ページネーション(ドット)が検出できない',
      'ページネーション（ドット/インジケータ）が見当たらない。配置の有無と位置を確認。',
      { check: 'nav.dots' });
  }
  if (!hasTopIndex) {
    add('D3', 'warn', '上部インデックス(目次ナビ)が検出できない',
      'セクション目次/アジェンダの上部インデックスが見当たらない。ユーザー要望項目のため deck-evaluator で要否を要望と照合すること。',
      { check: 'nav.topIndex' });
  }
  if (!hasCounter) {
    add('D3', 'info', 'スライドカウンターが検出できない',
      '現在/全数カウンターが見当たらない。', { check: 'nav.counter' });
  }
  if (!hasProgress) {
    add('D3', 'info', '進捗バーが検出できない',
      'プログレスバーが見当たらない（任意項目）。', { check: 'nav.progress' });
  }
}

// ==================================================
// D2: 文字サイズ（static 補助・本命は dynamic computed px）
// ==================================================
function checkFontStatic() {
  // rem 直書きで 1.4 未満
  const remRe = /font-size:\s*([\d.]+)rem/gi;
  let m;
  const haystack = `${css}\n${html}`;
  const smallRem = new Set();
  while ((m = remRe.exec(haystack)) !== null) {
    const v = parseFloat(m[1]);
    if (v > 0 && v < CONFIG.remMin) smallRem.add(m[1]);
  }
  if (smallRem.size > 0) {
    add('D2', 'warn', `最小フォント未満(rem)を検出: ${[...smallRem].join(', ')}rem`,
      `font-size が ${CONFIG.remMin}rem 未満の rem 直書きを検出。視認性が低下する可能性。`,
      { check: 'font.remMin' });
  }
  // SVG テキスト等の px が 13 未満
  const pxRe = /font-size:\s*([\d.]+)px/gi;
  const smallPx = new Set();
  while ((m = pxRe.exec(haystack)) !== null) {
    const v = parseFloat(m[1]);
    if (v > 0 && v < CONFIG.svgTextMinPx) smallPx.add(m[1]);
  }
  // SVG <text font-size="11"> 形式も拾う
  const attrRe = /<text[^>]*font-size=["']?([\d.]+)(px)?["']?/gi;
  while ((m = attrRe.exec(html)) !== null) {
    const v = parseFloat(m[1]);
    if (v > 0 && v < CONFIG.svgTextMinPx) smallPx.add(m[1]);
  }
  if (smallPx.size > 0) {
    add('D2', 'warn', `13px未満のフォント指定を検出: ${[...smallPx].join(', ')}px`,
      `SVGテキスト等で ${CONFIG.svgTextMinPx}px 未満を検出（対面大画面で視認不可の懸念・S22）。`,
      { check: 'font.svgMinPx' });
  }
}

// ==================================================
// D1: 視覚的崩れ（static: 型崩れ + ローカル画像欠落）
// ==================================================
function checkVisualStatic() {
  // テンプレート型崩れ（verify-slides.js と同基準）
  const corruption = ['[object Object]', '[render error:'];
  const hit = corruption.filter((p) => html.includes(p));
  if (hit.length > 0) {
    add('D1', 'error', '可視テキストの型崩れを検出',
      `テンプレート未解決の痕跡: ${hit.join(', ')}`, { check: 'visual.corruption' });
  }

  // ローカル画像参照の実体欠落（broken img を static で検出できる範囲）
  const refs = new Set();
  const imgRe = /(?:src|href|xlink:href)\s*=\s*["']([^"']+)["']/gi;
  let m;
  while ((m = imgRe.exec(html)) !== null) {
    const url = m[1].trim();
    if (!url) continue;
    if (/^(https?:)?\/\//i.test(url)) continue; // 外部
    if (url.startsWith('data:')) continue;       // インライン
    if (url.startsWith('#')) continue;           // アンカー/フラグメント
    if (!/\.(png|jpe?g|webp|gif|svg|avif)(\?|$)/i.test(url)) continue; // 画像のみ
    refs.add(url.split('?')[0].split('#')[0]);
  }
  const missing = [];
  for (const r of refs) {
    const p = isAbsolute(r) ? r : resolve(deckDir, r);
    if (!existsSync(p)) missing.push(r);
  }
  if (missing.length > 0) {
    add('D1', 'error', `参照画像の実体が存在しない: ${missing.length}件`,
      `index.html が参照するローカル画像が見つからない（画像崩れの原因）: ${missing.slice(0, 8).join(', ')}${missing.length > 8 ? ' ...' : ''}`,
      { check: 'visual.missingImage', missing });
  }
}

// ==================================================
// D4: 仕様適合（既存 sync-checker / validate-structure を集約）
// ==================================================
function runNode(scriptName, args) {
  const r = spawnSync('node', [join(__dirname, scriptName), ...args], {
    encoding: 'utf-8', timeout: 120000
  });
  return r;
}

// 全面画像デッキ検出（validate-print.js:150 / validate-ai-image-assets.js:412 と同一の
// 主キャンバス union。クラス名密結合を避け意味属性 + 許容クラスで判定）。
// 検出根拠（いずれか）:
//   1) HTML に主キャンバス class/marker（ai-slide-canvas / slide-fullbg / slide-bg / data-role=main-canvas）
//   2) image-deck-plan.json が deckDir 直下 or assets/generated に存在（決定論ビルドチェーンの計画）
//   3) structure.md に full-image-deck / 全面画像 / image-only 宣言
// 通常HTMLデッキ（主キャンバス無し・plan.json無し）はいずれにも該当せず spawn しない（後方互換）。
function detectFullImageDeck() {
  const mainCanvasRe = /(?:data-role\s*=\s*["']main-canvas["']|class\s*=\s*["'][^"']*\b(?:ai-slide-canvas|slide-fullbg|slide-bg)\b[^"']*["'])/;
  if (mainCanvasRe.test(html)) return true;
  const planCandidates = [
    join(deckDir, 'image-deck-plan.json'),
    join(deckDir, 'assets', 'generated', 'image-deck-plan.json')
  ];
  if (planCandidates.some((p) => existsSync(p))) return true;
  if (existsSync(structureMd)) {
    try {
      if (/full-image-deck|全面画像|image-only/i.test(readFileSync(structureMd, 'utf-8'))) return true;
    } catch { /* ignore */ }
  }
  return false;
}

// 印刷品質ゲート: validate-print.js を index.html に対し --full-image-deck --json で実行し、
// CRITICAL を D4 error、WARNING を D4 warn に接続する（exit 1=CRITICAL）。
function runPrintGate() {
  const r = runNode('validate-print.js', [indexPath, '--json', '--full-image-deck']);
  let parsed = false;
  if (r.stdout) {
    try {
      const data = JSON.parse(r.stdout);
      parsed = true;
      (data.results || []).filter((c) => !c.passed).forEach((c) => {
        add('D4', c.severity === 'CRITICAL' ? 'error' : 'warn',
          `印刷品質違反 ${c.id}`, c.name, { check: 'spec.print', source: 'validate-print' });
      });
      if ((data.criticalFails || 0) === 0 && (data.warningFails || 0) === 0) {
        add('D4', 'info', '印刷品質 PASS',
          `validate-print: ${data.passed}/${data.total} passed (full-image-deck)`,
          { check: 'spec.print', source: 'validate-print' });
      }
    } catch { /* parse失敗 → 下のフォールバック */ }
  }
  if (!parsed) {
    if (r.status !== 0) {
      add('D4', 'error', '印刷品質 検証失敗',
        `validate-print exit ${r.status}: ${(r.stderr || '').slice(0, 200)}`,
        { check: 'spec.print', source: 'validate-print' });
    } else if (r.error) {
      add('D4', 'info', 'validate-print 実行不可', `${r.error.message}`,
        { check: 'spec.print', source: 'validate-print' });
    }
  }
}

// AI画像アセットゲート: validate-ai-image-assets.js を deckDir に対し
// --full-image-deck --strict-style-genome で実行し、FAIL行を D4 error、WARN行を D4 warn に
// 接続する（--json 非対応のため行頭 FAIL:/WARN: を解析・exit 1=FAIL）。
function runAiImageGate() {
  const r = runNode('validate-ai-image-assets.js', [deckDir, '--full-image-deck', '--strict-style-genome']);
  if (r.error) {
    add('D4', 'info', 'validate-ai-image-assets 実行不可', `${r.error.message}`,
      { check: 'spec.aiImage', source: 'validate-ai-image-assets' });
    return;
  }
  const out = `${r.stdout || ''}\n${r.stderr || ''}`;
  const failLines = out.split('\n').filter((l) => /^\s*FAIL:/.test(l));
  const warnLines = out.split('\n').filter((l) => /^\s*WARN:/.test(l));
  failLines.forEach((l) => add('D4', 'error', 'AI画像アセット違反',
    l.replace(/^\s*FAIL:\s*/, '').slice(0, 240), { check: 'spec.aiImage', source: 'validate-ai-image-assets' }));
  warnLines.forEach((l) => add('D4', 'warn', 'AI画像アセット要確認',
    l.replace(/^\s*WARN:\s*/, '').slice(0, 240), { check: 'spec.aiImage', source: 'validate-ai-image-assets' }));
  if (r.status !== 0 && failLines.length === 0) {
    add('D4', 'error', 'AI画像アセット検証失敗',
      `validate-ai-image-assets exit ${r.status}`, { check: 'spec.aiImage', source: 'validate-ai-image-assets' });
  } else if (r.status === 0 && failLines.length === 0) {
    add('D4', 'info', 'AI画像アセット PASS',
      out.match(/PASS:[^\n]*/)?.[0] || 'validated', { check: 'spec.aiImage', source: 'validate-ai-image-assets' });
  }
}

function checkSpecConformance() {
  // 1) 同期検証: structure.md は sync-checker（md形式パーサ）、
  //    structure.json のみのデッキは sync-checker が誤って0枚と解釈するため直接スライド数照合する。
  const slideCountHtml = (html.match(/slider__item/g) || []).length;
  if (existsSync(structureMd)) {
    const r = runNode('sync-checker.js', [indexPath, structureMd, '--json']);
    if (r.stdout) {
      try {
        const data = JSON.parse(r.stdout);
        (data.issues || []).forEach((iss) => {
          add('D4', iss.severity === 'error' ? 'error' : 'warn',
            `同期: ${iss.type}`, iss.message, { check: 'spec.sync', source: 'sync-checker' });
        });
        (data.warnings || []).forEach((w) => {
          add('D4', 'info', `同期注意: ${w.type}`, w.message, { check: 'spec.sync', source: 'sync-checker' });
        });
        if ((data.issues || []).length === 0) {
          add('D4', 'info', '同期OK', `structure(${data.structure?.slideCount}枚) ⇔ HTML(${data.html?.slideCount}枚) の必須整合を確認`,
            { check: 'spec.sync', source: 'sync-checker' });
        }
      } catch (e) {
        add('D4', 'info', 'sync-checker 出力の解析に失敗', `${e.message}`, { check: 'spec.sync' });
      }
    } else if (r.error) {
      add('D4', 'info', 'sync-checker 実行不可', `${r.error.message}`, { check: 'spec.sync' });
    }
  } else if (existsSync(structureJson)) {
    try {
      const sj = JSON.parse(readFileSync(structureJson, 'utf-8'));
      const n = (sj.slides || []).length;
      if (n !== slideCountHtml) {
        add('D4', 'error', '同期: slide-count-mismatch',
          `structure.json=${n}枚, HTML=${slideCountHtml}枚`, { check: 'spec.sync', source: 'sync-checker' });
      } else {
        add('D4', 'info', '同期OK', `structure.json(${n}枚) ⇔ HTML(${slideCountHtml}枚) のスライド数一致`,
          { check: 'spec.sync', source: 'sync-checker' });
      }
    } catch (e) {
      add('D4', 'info', 'structure.json 解析失敗', `${e.message}`, { check: 'spec.sync' });
    }
  } else {
    add('D4', 'warn', 'structure.md/json が見つからない',
      'デッキに structure.md または structure.json が無いため仕様適合(同期/構成)を検証できない。', { check: 'spec.noStructure' });
  }

  // 2) validate-structure（構造仕様 V-001〜V-043）— structure.json がある時のみ。
  //    structure.md（長文/散文）は validate-structure の構造化(title/slides)前提に合致せず
  //    誤FAILを量産するため対象外（偽陽性回避）。.md は sync-checker のみで担保する。
  if (existsSync(structureJson)) {
    let tmpDir = null;
    try {
      tmpDir = mkdtempSync(join(tmpdir(), 'evaldeck-'));
      const reportPath = join(tmpDir, 'vs.json');
      runNode('validate-structure.js', [structureJson, '--schema', '--report', reportPath]);
      if (existsSync(reportPath)) {
        const vr = JSON.parse(readFileSync(reportPath, 'utf-8'));
        const failed = vr.failed || [];
        const warned = vr.warned || [];
        failed.forEach((c) => add('D4', 'error', `仕様違反 ${c.vid || ''}`,
          `${c.desc || ''}: ${c.detail || ''}`, { check: 'spec.validate', source: 'validate-structure' }));
        warned.forEach((c) => add('D4', 'warn', `仕様要確認 ${c.vid || ''}`,
          `${c.desc || ''}: ${c.detail || ''}`, { check: 'spec.validate', source: 'validate-structure' }));
        if (failed.length === 0 && warned.length === 0) {
          add('D4', 'info', '構造仕様 PASS',
            `validate-structure: FAIL/WARN なし（passed ${(vr.passed || []).length}件）`, { check: 'spec.validate' });
        }
      }
    } catch (e) {
      add('D4', 'info', 'validate-structure 実行/解析に失敗', `${e.message}`, { check: 'spec.validate' });
    } finally {
      if (tmpDir) { try { rmSync(tmpDir, { recursive: true, force: true }); } catch {} }
    }
  } else if (existsSync(structureMd)) {
    add('D4', 'info', 'structure.json 不在のため構造スキーマ検証(V-001〜)はスキップ',
      'structure.md のみのデッキは sync-checker による同期検証のみ実施（validate-structure は structure.json 専用）。', { check: 'spec.validate.skip' });
  }

  // 3) 全面画像デッキ専用ゲート（CHANGELOG v2 の実配線）: full-image-deck 検出時のみ
  //    validate-print / validate-ai-image-assets を子プロセスで実行し CRITICAL/FAIL を
  //    D4 error に昇格して出荷ゲート(verdict)に接続する。通常HTMLデッキでは spawn しない。
  if (detectFullImageDeck()) {
    add('D4', 'info', '全面画像デッキを検出',
      '主キャンバス class / image-deck-plan.json / structure.md 宣言のいずれかを検出。印刷品質・AI画像アセットゲートを集約する。',
      { check: 'spec.fullImageDeck' });
    runPrintGate();
    runAiImageGate();
  }
}

// ==================================================
// dynamic（playwright）: chromium があれば実行
// ==================================================
function chromiumAvailable() {
  const probe = `
import { chromium } from 'playwright';
import { existsSync } from 'fs';
const exe = chromium.executablePath();
process.exit(exe && existsSync(exe) ? 0 : 7);
`;
  const r = spawnSync('node', ['--input-type=module', '-e', probe], {
    cwd: resolve(__dirname, '..'), timeout: 30000
  });
  return r.status === 0;
}

function runDynamic() {
  const js = `
import { chromium } from 'playwright';

const htmlPath = ${JSON.stringify(indexPath)};
const W = ${VIEWPORT.WIDTH};
const H = ${VIEWPORT.HEIGHT};
const SVG_MIN = ${CONFIG.svgTextMinPx};
const BODY_MIN = ${CONFIG.bodyFontMinPx};
const TOL = ${CONFIG.overflowTolPx};
const CARD_SEL = ${JSON.stringify(CONFIG.cardSelectors.join(', '))};
const out = { findings: [], meta: {} };

try {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.goto('file://' + htmlPath);
  await page.waitForTimeout(1500);

  const total = await page.evaluate(() => document.querySelectorAll('.slider__item').length);
  out.meta.totalSlides = total;

  const ratio = await page.evaluate(() => {
    const a = document.querySelector('.slide-area');
    if (!a) return null;
    return a.offsetWidth / a.offsetHeight;
  });
  if (ratio !== null && Math.abs(ratio - (16 / 9)) > 0.01) {
    out.findings.push({ dimension: 'D1', severity: 'warn',
      title: '16:9アスペクト比のずれ', detail: \`slide-area 比率 \${ratio.toFixed(4)} (期待 1.7778)\`, check: 'visual.ratio' });
  }

  const bad = await page.evaluate(() => {
    const t = document.body.innerText || '';
    return ['[object Object]', '[render error:'].filter((p) => t.includes(p));
  });
  if (bad.length) {
    out.findings.push({ dimension: 'D1', severity: 'error',
      title: '可視テキストの型崩れ', detail: bad.join(', '), check: 'visual.corruption' });
  }

  for (let i = 0; i < total; i += 1) {
    await page.evaluate((active) => {
      const items = document.querySelectorAll('.slider__item');
      items.forEach((it, idx) => it.classList.toggle('is-active', idx === active));
    }, i);
    await page.waitForTimeout(120);

    const broken = await page.evaluate(() => {
      const a = document.querySelector('.slider__item.is-active') || document;
      const imgs = Array.from(a.querySelectorAll('img'));
      return imgs.filter((im) => im.complete && im.naturalWidth === 0)
        .map((im) => im.getAttribute('src') || '(no src)');
    });
    for (const src of broken) {
      out.findings.push({ dimension: 'D1', severity: 'error',
        title: '画像が読み込めない(broken img)', detail: \`slide \${i + 1}: \${src}\`, slide: i + 1, check: 'visual.brokenImg' });
    }

    const overflow = await page.evaluate(({ cardSel, tol }) => {
      const a = document.querySelector('.slider__item.is-active');
      if (!a) return [];
      const els = Array.from(a.querySelectorAll(cardSel));
      const res = [];
      for (const el of els) {
        const cs = getComputedStyle(el);
        if (cs.overflow === 'visible') continue;
        const ox = el.scrollWidth - el.clientWidth;
        const oy = el.scrollHeight - el.clientHeight;
        if (ox > tol || oy > tol) {
          res.push({ cls: el.className.toString().slice(0, 60), ox, oy, text: (el.innerText || '').slice(0, 30) });
        }
      }
      return res.slice(0, 6);
    }, { cardSel: CARD_SEL, tol: TOL });
    for (const o of overflow) {
      out.findings.push({ dimension: 'D1', severity: 'warn',
        title: 'カード内テキストのはみ出し',
        detail: \`slide \${i + 1}: .\${o.cls} がはみ出し(x:\${o.ox} y:\${o.oy}) text='\${o.text}'\`,
        slide: i + 1, check: 'visual.overflow' });
    }

    const oob = await page.evaluate((tol) => {
      const area = document.querySelector('.slide-area');
      const a = document.querySelector('.slider__item.is-active');
      if (!area || !a) return 0;
      const ar = area.getBoundingClientRect();
      const content = a.querySelector('.slider__content') || a;
      let cnt = 0;
      for (const el of content.querySelectorAll('*')) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (r.right > ar.right + tol || r.bottom > ar.bottom + tol || r.left < ar.left - tol || r.top < ar.top - tol) cnt += 1;
      }
      return cnt;
    }, TOL);
    if (oob > 0) {
      out.findings.push({ dimension: 'D1', severity: 'warn',
        title: 'スライド枠外への要素はみ出し',
        detail: \`slide \${i + 1}: \${oob}個の要素が slide-area 範囲外\`, slide: i + 1, check: 'visual.outOfBounds' });
    }

    const small = await page.evaluate(({ svgMin, bodyMin }) => {
      const a = document.querySelector('.slider__item.is-active');
      if (!a) return { body: 0, svg: 0 };
      let body = 0;
      let svg = 0;
      for (const el of a.querySelectorAll('*')) {
        const txt = (el.textContent || '').trim();
        if (!txt) continue;
        const fs = parseFloat(getComputedStyle(el).fontSize);
        const isSvg = el.ownerSVGElement || el.tagName.toLowerCase() === 'text';
        if (isSvg) { if (fs > 0 && fs < svgMin) svg += 1; }
        else if (fs > 0 && fs < bodyMin) body += 1;
      }
      return { body, svg };
    }, { svgMin: SVG_MIN, bodyMin: BODY_MIN });
    if (small.body > 0) {
      out.findings.push({ dimension: 'D2', severity: 'warn',
        title: '本文フォントが小さすぎる(computed)',
        detail: \`slide \${i + 1}: \${small.body}要素が \${BODY_MIN}px 未満\`, slide: i + 1, check: 'font.bodyComputed' });
    }
    if (small.svg > 0) {
      out.findings.push({ dimension: 'D2', severity: 'warn',
        title: 'SVGテキストが小さすぎる(computed)',
        detail: \`slide \${i + 1}: \${small.svg}要素が \${SVG_MIN}px 未満\`, slide: i + 1, check: 'font.svgComputed' });
    }
  }

  await browser.close();
  console.log(JSON.stringify(out));
} catch (e) {
  console.log(JSON.stringify({ error: e.message }));
  process.exit(9);
}
`;
  const r = spawnSync('node', ['--input-type=module', '-e', js], {
    cwd: resolve(__dirname, '..'), encoding: 'utf-8', timeout: 300000
  });
  if (r.status !== 0 || !r.stdout) {
    return { ok: false, error: (r.stderr || r.error?.message || 'unknown').toString().slice(0, 300) };
  }
  try {
    const data = JSON.parse(r.stdout.trim().split('\n').pop());
    if (data.error) return { ok: false, error: data.error };
    data.findings.forEach((f) => findings.push({ id: `F${String(++fid).padStart(3, '0')}`, ...f }));
    return { ok: true, meta: data.meta || {} };
  } catch (e) {
    return { ok: false, error: `parse: ${e.message}` };
  }
}

// ==================================================
// 実行
// ==================================================
checkOperability(); // 最重要: 動かないデッキ(CSS/JS欠落・切替/送り未実装)を CRITICAL で検出
checkNavigation();
checkFontStatic();
checkVisualStatic();
checkSpecConformance();

// D5 は LLM 限定。機械では判定不可であることを明示的に記録（漏れなし条件のため）。
add('D5', 'info', '要望↔構成の整合はLLM評価が必要',
  'ユーザー要望と structure/HTML の矛盾・仕組み反映の有無は deck-evaluator(30種思考法) で判定すること（機械評価対象外）。',
  { check: 'requirement.pendingLlm' });

let dynamicStatus = 'skipped';
let dynamicMeta = {};
if (staticOnly) {
  dynamicStatus = 'skipped(static-only)';
  add('D1', 'info', 'dynamic検証はstatic-onlyによりスキップ',
    'broken img/はみ出し/computedフォント等の動的検証は未実施。完全評価は --static-only 無しで再実行。', { check: 'dynamic.skip' });
} else if (!chromiumAvailable()) {
  dynamicStatus = 'skipped(no-chromium)';
  add('D1', 'warn', 'chromium未導入のためdynamic検証をスキップ',
    `broken img/カードはみ出し/computedフォントの動的検証ができない。plugin-local Chromium を \`${setupCommand()}\` で復元後に再実行する。`, { check: 'dynamic.noChromium' });
} else {
  const dyn = runDynamic();
  if (dyn.ok) { dynamicStatus = 'ran'; dynamicMeta = dyn.meta; }
  else {
    dynamicStatus = 'error';
    add('D1', 'warn', 'dynamic検証でエラー', `playwright実行に失敗: ${dyn.error}`, { check: 'dynamic.error' });
  }
}

// ==================================================
// 集計・レポート
// ==================================================
const counts = { error: 0, warn: 0, info: 0 };
findings.forEach((f) => { counts[f.severity] = (counts[f.severity] || 0) + 1; });

const byDimension = {};
Object.keys(DIMENSIONS).forEach((d) => {
  const fs = findings.filter((f) => f.dimension === d);
  byDimension[d] = {
    name: DIMENSIONS[d],
    error: fs.filter((f) => f.severity === 'error').length,
    warn: fs.filter((f) => f.severity === 'warn').length,
    info: fs.filter((f) => f.severity === 'info').length
  };
});

// Dx 動作可能性: 動かないデッキ（CSS/JS欠落・表示切替/送り未実装）の error が無い。
// CSS/JSの実体欠落は dependency_integrity の不成立としても扱う（依存資産の未解決）。
const operable = !findings.some((f) => f.dimension === 'Dx' && f.severity === 'error');

// 4条件（生成デッキに対する機械判定。矛盾/漏れ/整合/依存）
const conditions = {
  // 矛盾なし: 仕様間・実装間で相反がない（型崩れ・同期不一致・仕様違反 error が無い）
  contradiction_free: counts.error === 0,
  // 漏れなし: 必須ナビ/構成要素が揃う（D3 prevNext error が無い）＋デッキが動作可能(Dx error 無し)
  completeness: !findings.some((f) => f.check === 'nav.prevNext' && f.severity === 'error') && operable,
  // 整合性: 同期・仕様の error/warn が許容範囲（spec.sync/validate/print/ai-image の error が無い）
  consistency: !findings.some((f) => (f.source === 'sync-checker' || f.source === 'validate-structure' || f.source === 'validate-print' || f.source === 'validate-ai-image-assets') && f.severity === 'error'),
  // 依存関係整合: 参照画像・structure・CSS/JS 依存が解決（missingImage / CSS/JS欠落 error が無い）
  dependency_integrity: !findings.some((f) => (f.check === 'visual.missingImage' || f.check === 'operability.css' || f.check === 'operability.js') && f.severity === 'error'),
  // 動作可能性: index.html を開いてスライドが動くか（CSS/JS実在・表示切替・ページ送りが揃う）
  operable
};

const passed = counts.error === 0 && (!strict || counts.warn === 0);

const report = {
  schema: 'presentation-slide-generator/evaluation-report@1',
  generatedFor: deckDir,
  deck: { dir: deckDir, index: indexPath, hasCss: !!css, hasJs: !!js,
          hasStructure: existsSync(structureMd) || existsSync(structureJson) },
  dynamic: { status: dynamicStatus, ...dynamicMeta },
  verdict: passed ? 'PASS' : 'FAIL',
  conditions,
  summary: counts,
  byDimension,
  findings
};

// ファイル書き出し
let reportPath = options.report || join(deckDir, 'evaluation-report.json');
if (!isAbsolute(reportPath)) reportPath = resolve(process.cwd(), reportPath);
const mdPath = reportPath.replace(/\.json$/, '.md');

if (!noWrite) {
  try {
    writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');
    writeFileSync(mdPath, renderMarkdown(report), 'utf-8');
  } catch (e) {
    console.error(`⚠️ レポート書き出し失敗: ${e.message}`);
  }
}

// 出力
if (jsonOut) {
  console.log(JSON.stringify(report, null, 2));
} else {
  printHuman(report, noWrite ? null : { reportPath, mdPath });
}

process.exit(passed ? EXIT_CODES.SUCCESS : EXIT_CODES.VALIDATION_FAILED);

// ==================================================
// レンダリング
// ==================================================
function renderMarkdown(r) {
  const lines = [];
  lines.push(`# 生成後評価レポート`);
  lines.push('');
  lines.push(`- 対象: \`${basename(r.deck.dir)}\``);
  lines.push(`- 判定: **${r.verdict}**（error ${r.summary.error} / warn ${r.summary.warn} / info ${r.summary.info}）`);
  lines.push(`- dynamic検証: ${r.dynamic.status}`);
  lines.push('');
  lines.push(`## 4条件`);
  lines.push('');
  lines.push(`| 条件 | 判定 |`);
  lines.push(`|------|------|`);
  lines.push(`| 動作可能(スライドが動く) | ${r.conditions.operable ? 'PASS' : 'FAIL'} |`);
  lines.push(`| 矛盾なし | ${r.conditions.contradiction_free ? 'PASS' : 'FAIL'} |`);
  lines.push(`| 漏れなし | ${r.conditions.completeness ? 'PASS' : 'FAIL'} |`);
  lines.push(`| 整合性あり | ${r.conditions.consistency ? 'PASS' : 'FAIL'} |`);
  lines.push(`| 依存関係整合 | ${r.conditions.dependency_integrity ? 'PASS' : 'FAIL'} |`);
  lines.push('');
  lines.push(`## 次元別サマリー`);
  lines.push('');
  lines.push(`| 次元 | error | warn | info |`);
  lines.push(`|------|------|------|------|`);
  Object.entries(r.byDimension).forEach(([d, v]) => {
    lines.push(`| ${d} ${v.name} | ${v.error} | ${v.warn} | ${v.info} |`);
  });
  lines.push('');
  lines.push(`## 指摘一覧`);
  lines.push('');
  const order = { error: 0, warn: 1, info: 2 };
  [...r.findings].sort((a, b) => order[a.severity] - order[b.severity]).forEach((f) => {
    const mark = f.severity === 'error' ? '[ERROR]' : f.severity === 'warn' ? '[WARN]' : '[INFO]';
    lines.push(`- ${mark} (${f.dimension}) ${f.title} — ${f.detail}`);
  });
  lines.push('');
  lines.push(`## 次のアクション`);
  lines.push('');
  lines.push(`このレポートを入力に、deck-evaluator エージェント（思考リセット後30種思考法）で`);
  lines.push(`D5(要望↔構成の整合)を含む多角的・視覚的評価と4条件の最終判定を行うこと。`);
  lines.push('');
  return lines.join('\n');
}

function printHuman(r, paths) {
  const C = { error: '❌', warn: '⚠️ ', info: 'ℹ️ ' };
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`📊 生成後評価: ${basename(r.deck.dir)}`);
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`判定: ${r.verdict === 'PASS' ? '✅ PASS' : '❌ FAIL'}  (error ${r.summary.error} / warn ${r.summary.warn} / info ${r.summary.info})`);
  console.log(`dynamic: ${r.dynamic.status}`);
  console.log('');
  console.log('条件: ' + [
    `動作可能=${r.conditions.operable ? '○' : '×'}`,
    `矛盾なし=${r.conditions.contradiction_free ? '○' : '×'}`,
    `漏れなし=${r.conditions.completeness ? '○' : '×'}`,
    `整合性=${r.conditions.consistency ? '○' : '×'}`,
    `依存整合=${r.conditions.dependency_integrity ? '○' : '×'}`
  ].join(' / '));
  console.log('');
  const order = { error: 0, warn: 1, info: 2 };
  [...r.findings].sort((a, b) => order[a.severity] - order[b.severity]).forEach((f) => {
    if (f.severity === 'info') return; // 人間出力では info を省略
    console.log(`${C[f.severity]} (${f.dimension}) ${f.title}`);
    console.log(`     ${f.detail}`);
  });
  if (paths) {
    console.log('');
    console.log(`📝 レポート: ${paths.reportPath}`);
    console.log(`📝 Markdown: ${paths.mdPath}`);
  }
  console.log('');
  console.log('💡 次: deck-evaluator エージェント（30種思考法）でD5と最終4条件判定を実施');
}
