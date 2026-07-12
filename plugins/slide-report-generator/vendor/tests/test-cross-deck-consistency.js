/**
 * test-cross-deck-consistency.js — cross-deck-consistency.js の OUT1 受入テスト (node 実行)。
 *
 * run-cross-deck-review の feedback_contract OUT1 (verify_by=test) を backing する:
 *   既知の機械検出可能な不整合を cross-deck-consistency.js が全件検出し、
 *   クリーンseriesをPASSとすることを検証する。
 *
 * 方式: tmp に slide-* デッキ 2 件のシリーズを生成し --check all --json を実走。
 *   (a) 既知不整合を注入したシリーズ → 注入した各カテゴリを全件検出:
 *       - shared-spec 差分 (structure.md の GSAP 共通設定セクションを 2 デッキで相違)
 *       - rem-units    (styles.css に rem 単位を混入)
 *       - urls         (index.html に非許可ドメインの外部 URL を混入)
 *   (b) 同一構成のクリーンなシリーズ → 上記カテゴリを 1 件も誤検出しない
 *   (c) 4つの必須入力を欠くシリーズ → inputs error と欠落ファイル名を検出する
 *
 * cross-deck-consistency.js は checks map = {inputs, shared-spec, urls, css-vars, gsap, print, rem-units}
 * (px-rule/slide-types は非実装 = reference/prompt からも除外済み) を一次根拠とする。
 * 失敗時 exit 1、成功時 exit 0。実行: node test-cross-deck-consistency.js
 */

import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'fs';
import { execFileSync, spawnSync } from 'child_process';
import { tmpdir } from 'os';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPT = join(__dirname, '..', 'scripts', 'cross-deck-consistency.js');

let failed = 0;
function check(name, cond) {
  if (cond) {
    console.log(`  ok   - ${name}`);
  } else {
    console.error(`  FAIL - ${name}`);
    failed++;
  }
}

// --- shared-spec セクションを含む structure.md を組み立てる (gsap 部だけ差替可能) ---
function structureMd(gsapBody) {
  return [
    '## 共通仕様セクション',
    '',
    '### A4横配置・印刷品質保証仕様',
    'A4 landscape 297mm x 210mm、余白 0。',
    '',
    '### コードブロック共通仕様',
    'monospace、行番号なし。',
    '',
    '### GSAPアニメーション共通設定',
    gsapBody,
    '',
    '### フォント仕様',
    'Noto Sans JP、本文 vw ベース。',
    '',
  ].join('\n');
}

// クリーン styles.css: rem 非使用・@page margin:0・print 297mm・非許可 URL なし
const CLEAN_CSS = '@page { margin: 0; }\n.slide { padding: 2vw; }\n@media print { .slider__item { width: 297mm; height: 210mm; } }\n';
// 汚染 styles.css: rem 単位を混入 (checkRemUnits がフラグ)
const DIRTY_CSS = '@page { margin: 0; }\n.slide { padding: 2rem; }\n@media print { .slider__item { width: 297mm; height: 210mm; } }\n';
const CLEAN_HTML = '<!DOCTYPE html><html><head><link href="https://fonts.googleapis.com/x" rel="stylesheet"></head><body></body></html>\n';
// 汚染 index.html: 非許可ドメインの外部 URL を混入 (checkUrls がフラグ)
const DIRTY_HTML = '<!DOCTYPE html><html><head><script src="https://tracker.example.com/x.js"></script></head><body></body></html>\n';

function writeDeck(seriesDir, name, { gsap, css, html }) {
  const d = join(seriesDir, name);
  mkdirSync(d, { recursive: true });
  writeFileSync(join(d, 'structure.md'), structureMd(gsap), 'utf8');
  writeFileSync(join(d, 'styles.css'), css, 'utf8');
  writeFileSync(join(d, 'scripts.js'), "gsap.to('.a', {ease:'power1.out'}); gsap.to('.b', {ease:'power2.out'}); gsap.to('.c', {ease:'power3.out'});\n", 'utf8');
  writeFileSync(join(d, 'index.html'), html, 'utf8');
}

function runJson(seriesDir) {
  // FAIL=2 / WARN=1 で非0終了するため stdout を例外経由でも回収する。
  let out;
  try {
    out = execFileSync('node', [SCRIPT, seriesDir, '--check', 'all', '--json'], { encoding: 'utf8' });
  } catch (e) {
    out = e.stdout || '';
  }
  // --json モードでも先頭に「検出されたデッキ」ヘッダが出力されるため、最初の '{' 以降を抽出する。
  const start = out.indexOf('{');
  return JSON.parse(start >= 0 ? out.slice(start) : out);
}

function categories(report) {
  return new Set((report.issues || []).map(i => i.category));
}

const root = mkdtempSync(join(tmpdir(), 'cross-deck-test-'));
try {
  // (a) 既知不整合を注入したシリーズ
  const inconsistent = join(root, 'inconsistent');
  writeDeck(inconsistent, 'slide-2026-01-10-a', { gsap: 'duration 0.6s, ease power2.out', css: CLEAN_CSS, html: CLEAN_HTML });
  writeDeck(inconsistent, 'slide-2026-01-17-b', { gsap: 'duration 1.2s, ease power4.inOut', css: DIRTY_CSS, html: DIRTY_HTML });
  const badReport = runJson(inconsistent);
  const badCats = categories(badReport);
  check('(a) 2 デッキを検出', badReport.deckCount === 2);
  check('(a) shared-spec 差分 (GSAP 共通設定相違) を検出', badCats.has('shared-spec'));
  check('(a) rem-units (styles.css の rem 混入) を検出', badCats.has('rem-units'));
  check('(a) urls (非許可外部 URL 混入) を検出', badCats.has('urls'));
  check('(a) verdict が PASS でない (不整合検出)', badReport.verdict !== 'PASS');

  // (b) クリーン (同一構成) シリーズ
  const clean = join(root, 'clean');
  const gsapSame = 'duration 0.6s, ease power2.out';
  writeDeck(clean, 'slide-2026-01-10-a', { gsap: gsapSame, css: CLEAN_CSS, html: CLEAN_HTML });
  writeDeck(clean, 'slide-2026-01-17-b', { gsap: gsapSame, css: CLEAN_CSS, html: CLEAN_HTML });
  const okReport = runJson(clean);
  const okCats = categories(okReport);
  check('(b) 2 デッキを検出', okReport.deckCount === 2);
  check('(b) shared-spec を誤検出しない', !okCats.has('shared-spec'));
  check('(b) rem-units を誤検出しない', !okCats.has('rem-units'));
  check('(b) urls を誤検出しない', !okCats.has('urls'));
  check('(b) clean series 全体が PASS', okReport.verdict === 'PASS' && okReport.totalIssues === 0);

  // (c) 必須入力欠落 (IN1 fail-closed)
  const missing = join(root, 'missing-inputs');
  writeDeck(missing, 'slide-2026-01-10-a', { gsap: gsapSame, css: CLEAN_CSS, html: CLEAN_HTML });
  writeDeck(missing, 'slide-2026-01-17-b', { gsap: gsapSame, css: CLEAN_CSS, html: CLEAN_HTML });
  rmSync(join(missing, 'slide-2026-01-17-b', 'index.html'));
  rmSync(join(missing, 'slide-2026-01-17-b', 'styles.css'));
  rmSync(join(missing, 'slide-2026-01-17-b', 'scripts.js'));
  const missingReport = runJson(missing);
  const missingFiles = new Set(
    (missingReport.issues || []).filter(i => i.category === 'inputs').map(i => i.file),
  );
  check('(c) 必須入力欠落を inputs error として検出', missingReport.errors === 3);
  check('(c) index.html 欠落を検出', missingFiles.has('index.html'));
  check('(c) styles.css 欠落を検出', missingFiles.has('styles.css'));
  check('(c) scripts.js 欠落を検出', missingFiles.has('scripts.js'));

  // (d) 未実装カテゴリはfail-openでPASSを返さない
  const unknown = spawnSync('node', [SCRIPT, clean, '--check', 'px-rule', '--json'], { encoding: 'utf8' });
  check('(d) 不明カテゴリは exit 2', unknown.status === 2);
  check('(d) 不明カテゴリを stderr へ明示', (unknown.stderr || '').includes('不明なカテゴリ'));
} finally {
  rmSync(root, { recursive: true, force: true });
}

console.log('');
if (failed > 0) {
  console.error(`test-cross-deck-consistency: ${failed} 件 FAIL`);
  process.exit(1);
}
console.log('test-cross-deck-consistency: 全 PASS (OUT1: 注入不整合の全件検出 + clean series PASS)');
process.exit(0);
