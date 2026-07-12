/**
 * test-render-report.js — render-report.js の最小テスト (node 実行)。
 *
 * サンプル (sample-report-structure.json) は report-structure.schema.json に valid。
 * 検証:
 *   (a) 例外なく HTML を生成する
 *   (b) 出力に必須要素が含まれる:
 *       - <!DOCTYPE html> / </html>
 *       - 各 section の heading (schema: section.heading)
 *       - theme CSS var (--bg-dark 等 Kanagawa トークン)・theme-name=kanagawa-lotus
 *       - svg visual: <svg viewBox + variant 由来のノードラベル + visual.caption
 *       - mermaid visual: <pre class="mermaid"> + local bundle初期化 + spec.definition テキスト
 *       - codex-image visual: <img src=spec.asset>
 *       - none visual: fallback を誤爆しない
 *       - reportType バッジ
 *   (c) 決定論: 同一入力→byte 一致
 *
 * 失敗時 exit 1、成功時 exit 0。
 *   実行: node test-render-report.js
 */

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { runInNewContext } from 'vm';
import { renderReport } from '../scripts/render-report.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
let failed = 0;
function check(name, cond) {
  if (cond) {
    console.log(`  ok   - ${name}`);
  } else {
    console.error(`  FAIL - ${name}`);
    failed++;
  }
}

/** self-contained scrollspy を外部ブラウザ無しで実行する最小 DOM harness */
function runScrollspyHarness(renderedHtml) {
  const scriptMatch = renderedHtml.match(/<script>\n(\(function \(\) \{[\s\S]*?__slideReportScrollspy[\s\S]*?\}\)\(\);)\n<\/script>/);
  if (!scriptMatch) throw new Error('scrollspy script not found');

  const windowListeners = new Map();
  const rafQueue = [];
  let rafId = 0;
  let fontReady = null;
  const observerInstances = [];

  class FakeLink {
    constructor(id) {
      this.attrs = new Map([['href', `#${id}`]]);
      this.listeners = new Map();
      const classes = new Set();
      this.classList = {
        add: (name) => classes.add(name),
        remove: (name) => classes.delete(name),
        contains: (name) => classes.has(name),
      };
    }
    getAttribute(name) { return this.attrs.get(name) || null; }
    setAttribute(name, value) { this.attrs.set(name, value); }
    removeAttribute(name) { this.attrs.delete(name); }
    addEventListener(type, fn) { this.listeners.set(type, fn); }
    removeEventListener(type, fn) { if (this.listeners.get(type) === fn) this.listeners.delete(type); }
    click() { const fn = this.listeners.get('click'); if (fn) fn({ currentTarget: this }); }
  }

  class FakeTarget {
    constructor(id, top) { this.id = id; this.top = top; this.scrollCount = 0; }
    getBoundingClientRect() { return { top: this.top }; }
    scrollIntoView() { this.scrollCount += 1; }
  }

  class FakeIntersectionObserver {
    constructor(callback) {
      this.callback = callback;
      this.targets = [];
      this.disconnected = false;
      observerInstances.push(this);
    }
    observe(target) { this.targets.push(target); }
    disconnect() { this.disconnected = true; this.targets = []; }
    emit() { this.callback(this.targets.map((target) => ({ target, isIntersecting: true }))); }
  }

  const links = [new FakeLink('section-a'), new FakeLink('section-legacy')];
  const targets = [new FakeTarget('section-a', 500), new FakeTarget('section-legacy', 900)];
  const targetMap = Object.fromEntries(targets.map((target) => [target.id, target]));
  const nav = { querySelectorAll: () => links };
  const fakeWindow = {
    location: { hash: '#section-legacy' },
    innerHeight: 1000,
    matchMedia: () => ({ matches: false }),
    requestAnimationFrame(fn) { const id = ++rafId; rafQueue.push({ id, fn }); return id; },
    cancelAnimationFrame(id) {
      const index = rafQueue.findIndex((item) => item.id === id);
      if (index >= 0) rafQueue.splice(index, 1);
    },
    addEventListener(type, fn) {
      if (!windowListeners.has(type)) windowListeners.set(type, new Set());
      windowListeners.get(type).add(fn);
    },
    removeEventListener(type, fn) { if (windowListeners.has(type)) windowListeners.get(type).delete(fn); },
  };
  const fakeDocument = {
    querySelector: (selector) => selector === '.report-toc--sidebar' ? nav : null,
    getElementById: (id) => targetMap[id] || null,
    fonts: { ready: { then(fn) { fontReady = fn; } } },
  };
  const context = {
    window: fakeWindow,
    document: fakeDocument,
    IntersectionObserver: FakeIntersectionObserver,
    decodeURIComponent,
    String,
    Math,
  };
  fakeWindow.window = fakeWindow;

  function flushRaf() {
    while (rafQueue.length) rafQueue.shift().fn();
  }
  function dispatch(type) {
    for (const fn of Array.from(windowListeners.get(type) || [])) fn({ type });
  }
  function activeId() {
    const index = links.findIndex((link) => link.classList.contains('is-active'));
    return index < 0 ? null : targets[index].id;
  }
  function listenerCount(type) { return (windowListeners.get(type) || new Set()).size; }

  runInNewContext(scriptMatch[1], context);
  flushRaf();
  return {
    links, targets, observerInstances, fakeWindow, activeId, dispatch, flushRaf, listenerCount,
    click(id) { links[targets.findIndex((target) => target.id === id)].click(); },
    setTop(id, top) { targetMap[id].top = top; },
    fontReady() { if (fontReady) fontReady(); flushRaf(); },
    rerun() { runInNewContext(scriptMatch[1], context); flushRaf(); },
  };
}

const structure = JSON.parse(readFileSync(join(__dirname, 'sample-report-structure.json'), 'utf-8'));

let html = '';
let threw = null;
try {
  html = renderReport(structure);
} catch (e) {
  threw = e;
}

check('(a) 例外なく HTML を生成', threw === null && typeof html === 'string' && html.length > 0);
if (threw) console.error('     ', threw.stack);

// (b) 文書骨格
check('(b) <!DOCTYPE html> を含む', html.startsWith('<!DOCTYPE html>'));
check('(b) 終端 </html> を含む', html.trimEnd().endsWith('</html>'));

// (b) 各 section heading (schema: section.heading)
for (const sec of structure.sections) {
  check(`(b) section heading "${sec.heading}" を含む`, html.includes(`>${sec.heading}</h2>`));
}
// (b) 各 section id (schema: ^section-)
for (const sec of structure.sections) {
  check(`(b) section id "${sec.id}" を含む`, html.includes(`id="${sec.id}"`));
}

// (b) theme CSS var (Kanagawa トークン)
check('(b) theme CSS var --bg-dark を含む', html.includes('--bg-dark:'));
check('(b) theme CSS var --accent-blue-vivid を含む', html.includes('--accent-blue-vivid:'));
check('(b) theme-name meta が kanagawa-lotus', html.includes('content="kanagawa-lotus"'));

// --- visual: schema 語彙で各サンプル section を検証 ---
const bySection = Object.fromEntries(structure.sections.map((s) => [s.id, s]));

// svg (variant=flow, nodes[].label / visual.caption)
const svgFlow = bySection['section-background'];
check('(b) svg <svg viewBox を含む', html.includes('<svg viewBox='));
check('(b) svg visual.caption を含む', html.includes(svgFlow.visual.caption));
check('(b) svg ノードラベルを含む', html.includes(svgFlow.visual.spec.nodes[0].label));

// svg (variant=cycle) も描画される
const svgCycle = bySection['section-next-action'];
check('(b) svg cycle caption を含む', html.includes(svgCycle.visual.caption));

// mermaid (spec.definition / diagramType / self-contained local bundle 初期化)
const mm = bySection['section-analysis'];
check('(b) mermaid <pre class="mermaid"> を含む', html.includes('<pre class="mermaid">'));
check('(b) mermaid local bundle 初期化 script を含む', html.includes('mermaid.initialize') && !html.includes('cdn.jsdelivr.net'));
check('(b) 自己完結HTMLとして外部script/link参照を含まない', !/<(?:script|link)[^>]+(?:src|href)=["']https?:/i.test(html));
check('(b) mermaid 定義テキスト(系統判定)が埋込まれている', html.includes('系統判定'));
check('(b) mermaid visual.caption を含む', html.includes(mm.visual.caption));

// codex-image (spec.asset → <img>)
const codex = bySection['section-findings'];
check('(b) codex-image <img src=asset> を含む', html.includes(`<img src="${codex.visual.spec.asset}"`));
check('(b) codex-image alt を含む', html.includes(codex.visual.alt));

// none (fallback を誤爆しない)
check('(b) none section で fallback を出さない', !html.includes('report-visual--fallback'));

// reportType バッジ / meta
check('(b) reportType バッジ(社内報告分析)を含む', html.includes('社内報告分析'));
check('(b) meta.audience を含む', html.includes(structure.meta.audience));
check('(b) meta.keyMessage を含む', html.includes(structure.meta.keyMessage));

// section 要素数
const sectionCount = (html.match(/class="report-section"/g) || []).length;
check(`(b) section 要素数 = ${structure.sections.length}`, sectionCount === structure.sections.length);

// (c) 決定論
const html2 = renderReport(structure);
check('(c) 決定論: 2回の生成が byte 一致', html === html2);

// ===== 1.1.0: 構造化本文ブロック / narrative / highlight / placement / TOC =====
const s110 = {
  meta: { title: 'v1.1.0', reportType: 'tech-doc', audience: 'dev', keyMessage: 'k', toc: true, schemaVersion: '1.1.0' },
  theme: { name: 'kanagawa-lotus', accentColors: ['accent-violet-vivid'] },
  sections: [
    { id: 'section-a', heading: 'A', narrative: { essence: '本質', approach: '解決', leverage: '活用' },
      body: [
        { type: 'paragraph', text: '段落 **太字** と ==要点== と `code`。' },
        { type: 'subheading', text: '小見出し', level: 3 },
        { type: 'ordered-list', items: ['手順1', '手順2'] },
        { type: 'table', headers: ['h1', 'h2'], rows: [['a', 'b']], caption: '比較' },
        { type: 'code', language: 'bash', code: 'echo hi', caption: '例' },
        { type: 'key-point', title: 'P', text: '要点ボックス', tone: 'accent' },
        { type: 'stat-tile', stats: [{ label: 'x', value: '2.4x', trend: 'up' }] },
        { type: 'callout', variant: 'warning', text: '注意' },
        { type: 'blockquote', text: '引用' },
      ],
      visual: { kind: 'svg', layout: { grid: '2x1' }, caption: '図', spec: { variant: 'flow', nodes: [{ id: 'n-x', label: 'X' }] } } },
    { id: 'section-legacy', heading: 'L', paragraphs: ['旧 paragraphs のみ。'] },
  ],
};
const h110 = renderReport(s110);
check('(1.1.0) narrative リード帯を描画', h110.includes('report-narrative') && h110.includes('本質'));
check('(1.1.0) ==要点== → mark.report-hl', h110.includes('<mark class="report-hl">要点</mark>'));
check('(1.1.0) 小見出し → h3.report-subheading', h110.includes('<h3 class="report-subheading">'));
check('(1.1.0) 番号リスト → ol', h110.includes('report-list--ol'));
check('(1.1.0) 表 → table (br で潰さない)', h110.includes('<table class="report-table"'));
check('(1.1.0) 表の図表番号 表1.', h110.includes('表1. 比較'));
check('(1.1.0) コード → pre.report-code', h110.includes('<pre class="report-code">'));
check('(1.1.0) コードの図表番号 コード1.', h110.includes('コード1. 例'));
check('(1.1.0) key-point ボックス', h110.includes('report-keypoint'));
check('(1.1.0) stat-tile', h110.includes('report-stat__value') && h110.includes('2.4x'));
check('(1.1.0) callout warning', h110.includes('report-callout--warning'));
check('(1.1.0) blockquote', h110.includes('report-quote'));
check('(1.1.0) 図の図表番号 図1.', h110.includes('図1. 図'));
check('(1.1.0) 意味的配置 2カラム grid', h110.includes('report-grid--2col'));
check('(1.1.0) 目次 TOC', h110.includes('report-toc') && h110.includes('目次'));
check('(1.3.0 UI) screen layout の SSOT token (72ch/15rem/1240px)',
  h110.includes('--report-measure: 72ch') &&
  h110.includes('--report-sidebar-w: 15rem') &&
  h110.includes('--report-page-max: 1240px'));
check('(1.3.0 UI) sticky sidebar + 900px graceful degrade + print guard',
  h110.includes('.report-toc--sidebar') &&
  h110.includes('@media (max-width: 900px)') &&
  h110.includes("matchMedia('print')"));
check('(1.3.0 UI) printではsidebar TOCを非表示',
  h110.includes('.report-sidebar { display: none !important; }'));
check('(1.3.0 UI) scrollspy controller は再評価時に destroy して idempotent',
  h110.includes("var CONTROLLER_KEY = '__slideReportScrollspy'") &&
  h110.includes('window[CONTROLLER_KEY].destroy()') &&
  h110.includes('var controller = { start: start, stop: stop, destroy: destroy'));
check('(1.3.0 UI) 初期 hash / TOC click / manual scroll を単一 activate 経路へ統合',
  h110.includes('syncFromLocation(true); /* 初期 hash') &&
  h110.includes("addEventListener('click', onTocClick)") &&
  h110.includes("addEventListener('scroll', scheduleScrollSync") &&
  h110.includes("setAttribute('aria-current', 'location')"));
check('(1.3.0 UI) hashchange / popstate / fonts.ready 後に再着地',
  h110.includes("addEventListener('hashchange', onHistoryNavigation)") &&
  h110.includes("addEventListener('popstate', onHistoryNavigation)") &&
  h110.includes('document.fonts.ready.then') &&
  h110.includes("scrollIntoView({ block: 'start' })"));
check('(1.3.0 UI) beforeprint stop / afterprint restart+active復元',
  h110.includes("addEventListener('beforeprint', onBeforePrint)") &&
  h110.includes("addEventListener('afterprint', onAfterPrint)") &&
  /function onBeforePrint\(\)\s*\{[^}]*printing = true;[^}]*stop\(\)/s.test(h110) &&
  /function onAfterPrint\(\)\s*\{[^}]*printing = false;[^}]*start\(\)/s.test(h110) &&
  h110.includes('restoreAfterPrint'));
check('(1.3.0 UI) toc=false では scrollspy controller を出力しない', (() => {
  const h = renderReport({ ...s110, meta: { ...s110.meta, toc: false } });
  return !h.includes('__slideReportScrollspy') && !h.includes('report-toc--sidebar" aria-label="目次');
})());
const scrollspy = runScrollspyHarness(h110);
check('(1.3.0 runtime) 初期 hash target を active + aria-current + 再着地',
  scrollspy.activeId() === 'section-legacy' &&
  scrollspy.links[1].getAttribute('aria-current') === 'location' &&
  scrollspy.targets[1].scrollCount === 1);
scrollspy.click('section-a');
check('(1.3.0 runtime) TOC click は active/aria-current を即時同期',
  scrollspy.activeId() === 'section-a' &&
  scrollspy.links[0].getAttribute('aria-current') === 'location' &&
  scrollspy.links[1].getAttribute('aria-current') === null);
scrollspy.setTop('section-a', -100);
scrollspy.setTop('section-legacy', 500);
scrollspy.dispatch('scroll');
scrollspy.flushRaf();
check('(1.3.0 runtime) manual scroll は viewport marker 直前の section を選択', scrollspy.activeId() === 'section-a');
scrollspy.fakeWindow.location.hash = '#section-legacy';
scrollspy.dispatch('hashchange');
scrollspy.flushRaf();
check('(1.3.0 runtime) hashchange は target を active + 再着地',
  scrollspy.activeId() === 'section-legacy' && scrollspy.targets[1].scrollCount === 2);
scrollspy.fakeWindow.location.hash = '#section-a';
scrollspy.dispatch('popstate');
scrollspy.flushRaf();
check('(1.3.0 runtime) popstate は履歴 target を復元',
  scrollspy.activeId() === 'section-a' && scrollspy.targets[0].scrollCount === 1);
scrollspy.fakeWindow.location.hash = '#section-legacy';
scrollspy.fontReady();
check('(1.3.0 runtime) document.fonts.ready は hash target へ再着地',
  scrollspy.activeId() === 'section-legacy' && scrollspy.targets[1].scrollCount === 3);
scrollspy.fakeWindow.location.hash = '';
const observerBeforePrint = scrollspy.observerInstances.at(-1);
scrollspy.dispatch('beforeprint');
check('(1.3.0 runtime) beforeprint は observer/scroll監視を停止',
  observerBeforePrint.disconnected && scrollspy.listenerCount('scroll') === 0);
scrollspy.dispatch('afterprint');
check('(1.3.0 runtime) afterprint は controllerを再起動して直前activeを復元',
  scrollspy.activeId() === 'section-legacy' &&
  scrollspy.listenerCount('scroll') === 1 &&
  scrollspy.observerInstances.length === 2);
const controllerBeforeRerun = scrollspy.fakeWindow.__slideReportScrollspy;
scrollspy.rerun();
check('(1.3.0 runtime) script 再評価は旧controllerを破棄しlistenerを一重に維持',
  scrollspy.fakeWindow.__slideReportScrollspy !== controllerBeforeRerun &&
  scrollspy.listenerCount('scroll') === 1 &&
  scrollspy.listenerCount('hashchange') === 1 &&
  scrollspy.listenerCount('popstate') === 1 &&
  scrollspy.listenerCount('beforeprint') === 1 &&
  scrollspy.listenerCount('afterprint') === 1);
check('(1.1.0) section 番号 data-secnum (h2 本文は見出しのみ)', h110.includes('data-secnum="01"') && !h110.includes('report-section__num'));
check('(1.1.0) 後方互換: paragraphs[] のみの section も描画', h110.includes('旧 paragraphs のみ'));
check('(1.1.0) 決定論: 2回 byte 一致', h110 === renderReport(s110));

// ===== 1.2.0: 文書アーク / 節間接続 / 文書メタ / 新 block 型 / emphasisZone / 色覚非依存 highlight =====
const s120 = {
  meta: {
    title: 'v1.2.0', reportType: 'tech-doc', audience: 'dev', keyMessage: 'k',
    schemaVersion: '1.2.0', throughLine: '本質課題→解決→活用の通し筋。',
    version: '1.2.0', updatedDate: '2026-07-06', readingTime: '約8分',
  },
  theme: { name: 'kanagawa-lotus', accentColors: ['accent-violet-vivid'] },
  sections: [
    { id: 'section-analysis', heading: '分析', role: 'analysis',
      narrative: { essence: '本質', approach: '解決', leverage: '活用' },
      transition: '次に手順へ移る。',
      body: [
        { type: 'paragraph', text: '==色覚非依存== の強調。' },
        { type: 'definition-list', terms: [{ term: 'DAG', definition: '有向非巡回グラフ' }, { term: 'SSOT', definition: '単一の真実源' }] },
        { type: 'footnote', footnotes: [{ text: '出典メモ', citation: 'https://example.com/doc' }] },
        { type: 'task-list', tasks: [{ text: '未完了タスク', done: false }, { text: '完了タスク', done: true, owner: '担当A' }] },
      ],
      visual: { kind: 'svg', layout: { grid: '2x1', emphasisZone: 'highlight', readingOrder: 'top-to-bottom', focalPoint: { x: 30, y: 70 } }, caption: '図', spec: { variant: 'flow', nodes: [{ id: 'n-x', label: 'X' }] } } },
    { id: 'section-reference', heading: '参照', role: 'reference',
      body: [{ type: 'paragraph', text: 'reference 節は narrative 不要。' }] },
  ],
};
const h120 = renderReport(s120);
check('(1.2.0) throughLine 文書アーク帯を描画', h120.includes('report-throughline') && h120.includes('通し筋') && h120.includes('本質課題→解決→活用'));
check('(1.2.0) section.transition 橋渡し帯を描画', h120.includes('report-transition') && h120.includes('次に手順へ移る'));
check('(1.2.0) 文書メタ version/updatedDate/readingTime を描画', h120.includes('版: 1.2.0') && h120.includes('更新: 2026-07-06') && h120.includes('読了目安: 約8分') && h120.includes('report-meta__doc'));
check('(1.2.0) definition-list → dl.report-deflist (term↔def)', h120.includes('report-deflist') && h120.includes('<dt>DAG</dt>') && h120.includes('有向非巡回グラフ'));
check('(1.2.0) footnote → aside.report-footnotes + citation', h120.includes('report-footnotes') && h120.includes('<cite>') && h120.includes('example.com/doc'));
check('(1.2.0) footnote marker 自動採番 [1]', h120.includes('report-footnotes__marker') && h120.includes('[1]'));
check('(1.2.0) task-list → ul.report-tasklist + done 状態', h120.includes('report-tasklist') && h120.includes('is-done') && h120.includes('[x]') && h120.includes('[ ]'));
check('(1.2.0) task-list owner', h120.includes('report-tasklist__owner') && h120.includes('担当A'));
check('(1.2.0) emphasisZone=highlight → data-emphasis', h120.includes('data-emphasis="highlight"'));
check('(1.2.0) placement.readingOrder → data-reading-order', h120.includes('data-reading-order="top-to-bottom"'));
check('(1.2.0) placement.focalPoint → data-focal + CSS --focal (live 化・dead field 解消)', h120.includes('data-focal="30,70"') && h120.includes('--focal: 30% 70%'));
check('(1.2.0) highlight 色覚非依存の第2チャネル (underline + weight700 が CSS に存在)', h120.includes('mark.report-hl') && /mark\.report-hl\s*\{[^}]*text-decoration:\s*underline/.test(h120) && /mark\.report-hl\s*\{[^}]*font-weight:\s*700/.test(h120));
check('(1.2.0) reference 節: narrative 不在でも描画される (category error 回避)', h120.includes('reference 節は narrative 不要') && (h120.match(/report-narrative"/g) || []).length === 1);
check('(1.2.0) 後方互換: emphasis(旧 alias) も data-emphasis へ', renderReport({ meta: { title: 't', reportType: 'tech-doc', audience: 'a', keyMessage: 'k' }, theme: { name: 'kanagawa-lotus', accentColors: ['blue'] }, sections: [{ id: 'section-x', heading: 'X', paragraphs: ['p'], visual: { kind: 'svg', layout: { emphasis: 'muted' }, spec: { variant: 'flow', nodes: [{ id: 'n-a', label: 'A' }] } } }] }).includes('data-emphasis="muted"'));
check('(1.2.0) 決定論: 2回 byte 一致', h120 === renderReport(s120));

// ===== 1.2.0: footnote インライン係り先アンカー ([^id] ↔ footnote) =====
const sFn = {
  meta: { title: 'fn', reportType: 'tech-doc', audience: 'a', keyMessage: 'k', schemaVersion: '1.2.0' },
  theme: { name: 'kanagawa-lotus', accentColors: ['blue'] },
  sections: [
    { id: 'section-a', heading: 'A', role: 'analysis', narrative: { essence: 'e' },
      body: [
        { type: 'paragraph', text: '根拠を示す[^src1]。別の出典[^src2]。再掲[^src1]。未登録[^nope]。' },
        { type: 'footnote', footnotes: [
          { id: 'src1', text: '一次資料', citation: 'https://example.com/a' },
          { id: 'src2', text: '二次資料' },
          { text: 'id 無し巻末注' },
        ] },
      ] },
  ],
};
const hFn = renderReport(sFn);
check('(1.2.0 fn) [^src1] → 上付き番号リンク[1] + fnref アンカー', /<sup class="report-fnref" id="fnref-src1"><a href="#fn-src1">\[1\]<\/a><\/sup>/.test(hFn));
check('(1.2.0 fn) [^src2] → [2]', hFn.includes('<a href="#fn-src2">[2]</a>'));
check('(1.2.0 fn) 同一 id 再掲は fnref アンカー重複しない', (hFn.match(/id="fnref-src1"/g) || []).length === 1);
check('(1.2.0 fn) footnote 実体に係り先アンカー id=fn-src1', hFn.includes('<li id="fn-src1">'));
check('(1.2.0 fn) 本文へ戻る back-link (↩ + #fnref-src1)', hFn.includes('href="#fnref-src1"') && hFn.includes('↩'));
check('(1.2.0 fn) id 無し脚注は従来の巻末注[3]', hFn.includes('[3]') && hFn.includes('id 無し巻末注'));
check('(1.2.0 fn) ol は list-style none (marker が採番・二重採番回避)', hFn.includes('list-style: none'));
check('(1.2.0 fn) 未登録 [^nope] は字面温存 (リンク化しない)', hFn.includes('[^nope]') && !hFn.includes('#fn-nope'));
check('(1.2.0 fn) 決定論: 2回 byte 一致', hFn === renderReport(sFn));

// ===== 1.2.0: throughLine の part 単位階層化 (throughLineParts) =====
const sParts = {
  meta: { title: 'p', reportType: 'tech-doc', audience: 'a', keyMessage: 'k', schemaVersion: '1.2.0',
    throughLine: '本質→解決→活用の全体アーク。',
    throughLineParts: [{ title: '第1部 現状', arc: '課題の所在' }, { arc: '採用した解決' }] },
  theme: { name: 'kanagawa-lotus', accentColors: ['blue'] },
  sections: [{ id: 'section-a', heading: 'A', role: 'summary', body: [{ type: 'paragraph', text: 'p' }] }],
};
const hParts = renderReport(sParts);
check('(1.2.0 parts) throughLine 主帯 + 通し筋', hParts.includes('class="report-throughline"') && hParts.includes('本質→解決→活用の全体アーク'));
check('(1.2.0 parts) part 帯 <ol class=report-throughline-parts>', hParts.includes('<ol class="report-throughline-parts"'));
check('(1.2.0 parts) 明示 title の part', hParts.includes('第1部 現状') && hParts.includes('課題の所在'));
check('(1.2.0 parts) title 未指定は 第N部 採番', hParts.includes('第2部') && hParts.includes('採用した解決'));
check('(1.2.0 parts) throughLine 無しでも parts のみ描画', (() => {
  const h = renderReport({ ...sParts, meta: { ...sParts.meta, throughLine: undefined } });
  return h.includes('<ol class="report-throughline-parts"') && !h.includes('<div class="report-throughline"');
})());
check('(1.2.0 parts) parts 無しは従来の主帯のみ (part 要素なし)', (() => {
  const h = renderReport({ ...sParts, meta: { ...sParts.meta, throughLineParts: undefined } });
  return h.includes('class="report-throughline"') && !h.includes('<ol class="report-throughline-parts"');
})());
check('(1.2.0 parts) 決定論: 2回 byte 一致', hParts === renderReport(sParts));

console.log('');
if (failed > 0) {
  console.error(`test-render-report: ${failed} 件 FAIL (${html.length} bytes)`);
  process.exit(1);
}
console.log(`test-render-report: 全 PASS (${Buffer.byteLength(html)} bytes, ${structure.sections.length} sections)`);
process.exit(0);
