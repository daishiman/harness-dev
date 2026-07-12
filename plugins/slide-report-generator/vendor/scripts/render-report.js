/**
 * render-report.js — report-structure.json → report.html (決定論生成)
 *
 * 契約: report-structure.schema.json (正本) / BUILD CONTRACT §F・§E・§D。
 *   実行: node render-report.js <report-structure.json> <out.html>
 *
 * schema 語彙で読む (consumer は正本 schema に conform):
 *   - meta: title/reportType/audience/keyMessage/subtitle/length(brief|standard|deep)/author…
 *   - section: id(^section-)/heading/paragraphs[]/role/visual/readingOrder(視線方向 enum・任意)/callouts
 *   - visual: {kind, spec, caption, alt, rationale}  ← caption/alt は visual 直下 (spec 内でない)
 *       kind=svg         → svgSpec {variant, nodes[](^n-), edges?, groups?} を svg-builder.cjs へ dispatch
 *       kind=mermaid     → mermaidSpec {diagramType, definition} を mermaid-render.js へ
 *       kind=codex-image → aiVisualSpec {pattern, backgroundSource, asset?, slug, overlayText…} を <img>/composite へ
 *       kind=none        → spec 省略・テキストのみ
 *
 * 意匠トークン (Kanagawa Lotus 配色 / フォント / spacing / 最小サイズ) は
 * vendored `style-builder.cjs` の SPEC を **唯一のソース** として流用する
 * (slide と同一 SSOT・新規発明しない)。report は A4 縦向き・縦スクロールの読み物レイアウト。
 *
 * ESM (vendor/package.json type=module)。vendored .cjs は createRequire で require。
 * CLI と import (renderReport) の両対応。決定論・fail-soft (visual 失敗は fallback、render は落ちない)。
 */

import { readFileSync, writeFileSync } from 'fs';
import { createRequire } from 'module';
import { pathToFileURL } from 'url';
import { renderMermaidFragment, mermaidInitScript } from './mermaid-render.js';

// vendored CommonJS primitives を ESM から require する (共有意匠 SSOT の流用)
const require = createRequire(import.meta.url);
const { SPEC } = require('./style-builder.cjs');
const { escapeHtml } = require('./template-engine.cjs');
const svg = require('./svg-builder.cjs');

// reportType (§D の 4 enum) → アクセント色。読み物の視覚的アイデンティティ付与。
const REPORT_TYPE_ACCENT = {
  'internal-analysis': 'accent-blue-vivid',
  'client-proposal': 'accent-aqua-vivid',
  'tech-doc': 'accent-violet-vivid',
  learning: 'accent-yellow-vivid',
};

// svgSpec.variant (schema enum) → svg-builder.cjs のノードベース図解ビルダーへ写像。
// 単一配列引数 (items|events|circles|quadrants, opts) のビルダーはここで統一 dispatch。
// mindmap/comparison/network は多引数のため renderSvgVisual 内で個別処理。
const VARIANT_SINGLE_ARG = {
  flow: 'buildHorizontalFlow',
  stepper: 'buildVerticalFlow',
  'wave-step': 'buildSnake',
  snake: 'buildSnake',
  cycle: 'buildCycle',
  pyramid: 'buildPyramid',
  tree: 'buildHierarchy',
  org: 'buildHierarchy',
  matrix: 'buildMatrix',
  venn: 'buildVenn',
  timeline: 'buildVerticalTimeline',
  roadmap: 'buildVerticalTimeline',
  chevron: 'buildChevron',
  funnel: 'buildFunnel',
  concentric: 'buildConcentric',
  'value-stack': 'buildValueStack',
};

// ===== 1.2.0: footnote インライン係り先アンカー (文書レベル採番) =====
// renderReport 開始時に本文中 `[^id]` 参照 ↔ footnote 実体を突合するため、id を持つ脚注を
// 文書順に連番採番したレジストリを構築する。determinism: 入力配列順に一意採番するため決定論的。
// inlineMd は非再入で単一 renderReport 呼び出し中のみこの state を読む。
let _footnoteRegistry = Object.create(null); // id -> 連番 (1..)
let _emittedFnrefs = new Set();               // back-link アンカー id の重複防止 (最初の参照のみ id 付与)

/** 全 section の body footnote block を走査し、id を持つ脚注を文書順連番でレジストリ化 */
function buildFootnoteRegistry(sections) {
  const reg = Object.create(null);
  let n = 0;
  for (const sec of Array.isArray(sections) ? sections : []) {
    const body = Array.isArray(sec && sec.body) ? sec.body : [];
    for (const b of body) {
      if (b && b.type === 'footnote' && Array.isArray(b.footnotes)) {
        for (const fn of b.footnotes) {
          if (fn && fn.id && !(fn.id in reg)) {
            n += 1;
            reg[fn.id] = n;
          }
        }
      }
    }
  }
  return reg;
}

/** theme を string|object の両方許容し正規化 (schema: kanagawa-lotus 固定) */
function themeName(theme) {
  if (!theme) return 'kanagawa-lotus';
  if (typeof theme === 'string') return theme;
  return theme.name || 'kanagawa-lotus';
}

/**
 * 共有意匠 SSOT (SPEC) から report 用 :root と読み物レイアウト CSS を生成。
 * 色/フォント/spacing の値は SPEC が唯一のソース。単位は rem/mm (縦スクロール文書)。
 */
function buildReportCss(spec = SPEC) {
  const c = spec.colors;
  const fs = spec.fontScale;
  const spacingVars = spec.spacing.map((v, i) => `  --space-${i + 1}: ${v};`).join('\n');
  return `:root {
  /* §2 Kanagawa Lotus パレット (style-builder SPEC を流用 = 共有意匠 SSOT) */
  --bg-dark: ${c.bgDark};
  --fg: ${c.fg};
  --fg-dim: ${c.fgDim};
  --fg-muted: #54546d;
  --wave-blue: ${c.waveBlue};
  --spring-violet: ${c.springViolet};
  --sakura-pink: ${c.sakuraPink};
  --wave-aqua: ${c.waveAqua};
  --autumn-yellow: ${c.autumnYellow};
  --fuji-gray: ${c.fujiGray};
  --accent-blue-vivid: ${c.accentBlueVivid};
  --accent-pink-vivid: ${c.accentPinkVivid};
  --accent-aqua-vivid: ${c.accentAquaVivid};
  --accent-violet-vivid: ${c.accentVioletVivid};
  --accent-yellow-vivid: ${c.accentYellowVivid};
  --shadow-subtle: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-medium: 0 3px 10px rgba(0,0,0,0.10);
  /* §3 フォント (SPEC 流用) */
  --font-scale: ${fs};
  --font-base: ${spec.fonts.base};
  --font-mono: ${spec.fonts.mono};
  /* report タイポは slide の --font-scale(1.3)から分離し、本文 16-18px の読み物レンジへ固定
     (title/body 比 <=2.2)。過大な見出しと窮屈感を根治する。 */
  --fs-title: 2.05rem;      /* ~33px */
  --fs-heading: 1.5rem;     /* ~24px */
  --fs-subheading: 1.2rem;  /* ~19px */
  --fs-body: 1.0625rem;     /* ~17px (16-18px 読書レンジ) */
  --fs-small: 0.92rem;      /* ~14.7px */
${spacingVars}
  /* report ページ幅 (A4 縦・print 層の正本) */
  --report-width: 190mm;
  /* screen 読書レイアウト。パワポ的に横空間を使い切る (空白>本文 の逆転を根治) */
  --report-measure: 72ch;      /* プレーン段落のみの可読幅。グラフィカル block は全幅で横を使う */
  --report-sidebar-w: 15rem;   /* sticky sidebar TOC 幅 */
  --report-page-max: 1240px;   /* sidebar + 本文の実効利用幅 (空白>本文 の逆転防止) */
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; }
body {
  background: var(--bg-dark);
  color: var(--fg);
  font-family: var(--font-base);
  font-size: var(--fs-body);
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
}
html { scroll-behavior: smooth; }

/* ===== 読み物レイアウト (screen: sidebar+可読幅 2 カラム / print: A4 縦 190mm 温存) ===== */
.report-layout {
  display: grid;
  grid-template-columns: var(--report-sidebar-w) minmax(0, 1fr);
  gap: var(--space-7, 3rem);
  max-width: var(--report-page-max);
  margin: 0 auto;
  padding: 0 var(--space-6, 2rem);
}
.report-layout--no-toc { grid-template-columns: 1fr; }
.report-layout--no-toc .report { margin: 0 auto; }
.report-sidebar { min-width: 0; }
.report {
  max-width: none;
  min-width: 0;
  margin: 0;
  padding: var(--space-7, 3rem) 0 var(--space-8, 4rem);
}
/* プレーン段落・リストのみ可読幅に制限。グラフィカル block (narrative/stats/visual/table/keypoint 等) は
   全幅でパワポ的に横空間を使う (窮屈=右側の空白過多を根治)。 */
.report-section > p,
.report-section > ul,
.report-section > ol { max-width: var(--report-measure); }
.report-section[id] { scroll-margin-top: var(--space-5, 1.5rem); }
.report-header { margin-bottom: var(--space-7, 3rem); border-bottom: 3px solid var(--report-accent, var(--accent-blue-vivid)); padding-bottom: var(--space-4, 1rem); }
.report-title { font-size: var(--fs-title); font-weight: 800; line-height: 1.25; color: var(--fg); }
.report-subtitle { margin-top: var(--space-2, 0.5rem); font-size: var(--fs-subheading); color: var(--fg-dim); font-weight: 500; }
.report-keymessage { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-body); color: var(--fg); font-weight: 500; border-left: 0.3rem solid var(--report-accent, var(--accent-blue-vivid)); padding-left: var(--space-3, 0.75rem); }
.report-meta { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-small); color: var(--fg-dim); display: flex; flex-wrap: wrap; gap: var(--space-4, 1rem); align-items: center; }
.report-meta .report-type-badge {
  display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px;
  background: var(--report-accent, var(--accent-blue-vivid)); color: #fff; font-weight: 700;
}

/* ===== section ===== */
.report-section { margin-bottom: var(--space-8, 4rem); }
.report-section > h2 {
  font-size: var(--fs-heading); font-weight: 700; line-height: 1.35;
  color: var(--fg);
  padding-left: var(--space-3, 0.75rem);
  border-left: 0.35rem solid var(--section-accent, var(--accent-blue-vivid));
  margin-bottom: var(--space-4, 1rem);
}
.report-section p { font-size: var(--fs-body); margin-bottom: var(--space-4, 1rem); }
.report-section strong { color: var(--section-accent, var(--accent-blue-vivid)); font-weight: 700; }
.report-section code { font-family: var(--font-mono); font-size: 0.92em; background: rgba(59,125,216,0.10); padding: 0.1em 0.35em; border-radius: 0.25rem; }
.report-section a { color: var(--accent-blue-vivid); }
.report-section ul { margin: 0 0 var(--space-4, 1rem) var(--space-5, 1.5rem); }
.report-section li { font-size: var(--fs-body); margin-bottom: var(--space-2, 0.5rem); }

/* ===== callouts (注記/警告/ヒント) ===== */
/* 吹き出し(左バー+ベタ塗り)を廃し、余白リッチのフラットカードへ。トーンは上端の細アクセント線で示す。 */
.report-callout { display: block; margin: var(--space-5, 1.5rem) 0; padding: var(--space-4, 1rem) var(--space-5, 1.5rem); border-radius: 0.85rem; font-size: var(--fs-small); background: #fff; border: 1px solid rgba(67,67,108,0.12); border-top: 3px solid var(--accent-blue-vivid); box-shadow: var(--shadow-subtle); }
.report-callout--warning, .report-callout--caution { border-top-color: var(--accent-pink-vivid); }
.report-callout--tip { border-top-color: var(--accent-yellow-vivid); }

/* ===== 本質図解 (essence diagram) — 各実質節の論理構造を一目化する主役ブロック ===== */
/* 1.3.0: 「小さく中央浮遊の装飾」→「本文幅いっぱいの枠付き figure (読解の主役)」へ。
   screen は本文可読幅を満たし、print は @media print 側で A4 幅 (--report-width) にキャップ。 */
.report-visual {
  margin: var(--space-7, 3rem) 0;
  padding: var(--space-6, 2rem);
  text-align: center;
  background: #fff;
  border: 1px solid rgba(67,67,108,0.10);
  border-radius: 0.9rem;
  box-shadow: var(--shadow-subtle);
}
.report-visual svg { width: 100%; max-width: 100%; height: auto; display: block; margin: 0 auto; }
.report-visual img { max-width: 100%; height: auto; border-radius: 0.5rem; box-shadow: var(--shadow-medium); object-position: var(--focal, 50% 50%); }
.report-visual figcaption { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-small); color: var(--fg-dim); text-align: center; }
.report-visual--mermaid pre.mermaid {
  display: block; text-align: left; font-family: var(--font-mono); font-size: var(--fs-small);
  background: rgba(59,125,216,0.06); border: 1px solid rgba(67,67,108,0.14);
  border-radius: 0.5rem; padding: var(--space-3, 0.75rem); overflow-x: auto; white-space: pre;
}
.report-visual--image .composite-overlay { list-style: none; margin: var(--space-2, 0.5rem) 0 0; padding: 0; font-size: var(--fs-small); color: var(--fg-dim); }

.report-footer { margin-top: var(--space-8, 4rem); padding-top: var(--space-3, 0.75rem); border-top: 1px solid rgba(67,67,108,0.15); font-size: var(--fs-small); color: var(--fg-dim); text-align: center; }

/* ===== 印刷 (A4 縦・読み物・screen 二層の print 側 = 従来 190mm 契約温存) ===== */
@page { size: A4 portrait; margin: 18mm; }
@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  body { background: #fff; }
  /* sidebar grid を解除し従来の一段組へ (sticky TOC 非適用・.report は A4 幅) */
  .report-layout { display: block; max-width: none; padding: 0; }
  .report-sidebar { display: none !important; }
  .report-toc a.is-active { color: inherit; font-weight: inherit; } /* scrollspy ハイライト無効 (print) */
  .report { max-width: 100%; margin: 0 auto; padding: 0; }
  .report-section { break-inside: avoid-page; }
  .report-visual { break-inside: avoid; }
}
/* ===== 狭画面 (max-width: 900px・タブレット縦含む): sidebar を解除しインライン TOC へ graceful degrade ===== */
@media (max-width: 900px) {
  .report-layout { display: block; max-width: 46rem; padding: 0 var(--space-4, 1rem); }
  .report-toc--sidebar { position: static; max-height: none; overflow: visible; margin: 0 0 var(--space-6, 2rem); }
  .report-toc--sidebar ol { columns: 2; }
  .report { max-width: none; margin: 0 auto; padding-top: var(--space-6, 2rem); }
}
/* ===== 1.1.0: 構造化本文ブロック ===== */
/* section 番号 (01, 02 …) — h2 の data-secnum を CSS ::before で前置 (h2 テキスト本体は見出しのみに保つ) */
.report-section > h2[data-secnum]::before {
  content: attr(data-secnum); display: inline-block; min-width: 2.2em; margin-right: 0.6rem;
  color: var(--section-accent, var(--accent-blue-vivid)); font-weight: 800;
  font-variant-numeric: tabular-nums; opacity: 0.85;
}
/* 節内論理展開リード帯 (本質課題→解決→活用) */
/* 節の論理アーク(本質課題→解決→活用): 外枠の吹き出しを廃し、余白の大きい独立 3 カードのパワポ図解へ。
   各カードは白地・上端アクセント・大きめ padding で「文字敷き詰め」から「余白のある図解」へ転換。 */
.report-narrative {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-5, 1.5rem); margin: var(--space-5,1.5rem) 0 var(--space-6, 2rem);
  padding: 0; background: none; border: 0;
}
.report-narrative__cell {
  display: flex; flex-direction: column; gap: 0.6rem;
  background: #fff; border: 1px solid rgba(67,67,108,0.12); border-radius: 0.85rem;
  border-top: 3px solid var(--section-accent, var(--accent-blue-vivid));
  padding: var(--space-5,1.5rem); box-shadow: var(--shadow-subtle);
}
.report-narrative__label {
  font-size: var(--fs-small); font-weight: 800; letter-spacing: 0.03em;
  color: var(--section-accent, var(--accent-blue-vivid));
}
.report-narrative__cell--approach .report-narrative__label { color: var(--accent-aqua-vivid); }
.report-narrative__cell--leverage .report-narrative__label { color: var(--accent-violet-vivid); }
.report-narrative__text { font-size: var(--fs-small); line-height: 1.7; color: var(--fg); }
/* 節内小見出し */
.report-subheading { font-size: var(--fs-subheading); font-weight: 700; margin: var(--space-5,1.5rem) 0 var(--space-3,0.75rem); color: var(--fg); }
h4.report-subheading { font-size: calc(1.12rem * var(--font-scale)); }
/* 番号/箇条書きリスト */
.report-list { margin: 0 0 var(--space-4,1rem) var(--space-5,1.5rem); }
.report-list--ol { list-style: decimal; }
.report-list--ul { list-style: disc; }
.report-list li { font-size: var(--fs-body); margin-bottom: var(--space-2,0.5rem); }
/* 要点の色付きハイライト (inline ==...==) — 1.2.0: 色に依存しない第2チャネル (font-weight + underline) を必須併存し色覚非依存 */
mark.report-hl {
  background: color-mix(in srgb, var(--accent-yellow-vivid) 34%, transparent);
  color: var(--fg); padding: 0.05em 0.28em; border-radius: 0.25rem; font-weight: 700;
  text-decoration: underline; text-decoration-thickness: 0.11em; text-underline-offset: 0.18em;
  text-decoration-color: var(--accent-yellow-vivid);
  box-decoration-break: clone; -webkit-box-decoration-break: clone;
}
/* markdown 表 (<br> で潰さない) */
.report-table-wrap { margin: var(--space-5,1.5rem) 0; overflow-x: auto; }
.report-table { width: 100%; border-collapse: collapse; font-size: var(--fs-small); background: rgba(255,255,255,0.5); border-radius: 0.5rem; overflow: hidden; box-shadow: var(--shadow-subtle); }
.report-table th, .report-table td { padding: 0.55rem 0.8rem; text-align: left; border-bottom: 1px solid rgba(67,67,108,0.14); vertical-align: top; }
.report-table thead th { background: color-mix(in srgb, var(--section-accent, var(--accent-blue-vivid)) 14%, transparent); color: var(--fg); font-weight: 700; }
.report-table tbody tr:nth-child(even) { background: rgba(67,67,108,0.035); }
.report-table-wrap figcaption, .report-code-wrap figcaption { margin-top: 0.4rem; font-size: var(--fs-small); color: var(--fg-dim); font-weight: 500; }
/* コードブロック (ダーク・ターミナル風) */
.report-code-wrap { position: relative; margin: var(--space-5,1.5rem) 0; }
.report-code__lang { position: absolute; top: 0.5rem; right: 0.7rem; font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; color: #c8c093; font-family: var(--font-mono); z-index: 1; }
pre.report-code { background: #1f1f28; color: #dcd7ba; font-family: var(--font-mono); font-size: 0.86rem; line-height: 1.6; padding: var(--space-4,1rem); border-radius: 0.55rem; overflow-x: auto; box-shadow: var(--shadow-medium); }
pre.report-code code { background: none; padding: 0; color: inherit; font-size: inherit; white-space: pre; }
/* キーポイント強調ボックス (色付き・トーン別) */
/* キーポイント: 吹き出しをやめ、余白の大きい白カード + 上端アクセント + タイトル前の色ドット。 */
.report-keypoint { margin: var(--space-5,1.5rem) 0; padding: var(--space-5,1.5rem); border-radius: 0.85rem; background: #fff; border: 1px solid rgba(67,67,108,0.12); border-top: 3px solid var(--accent-pink-vivid); box-shadow: var(--shadow-subtle); --kp-accent: var(--accent-pink-vivid); }
.report-keypoint--accent   { border-top-color: var(--accent-blue-vivid);   --kp-accent: var(--accent-blue-vivid); }
.report-keypoint--positive { border-top-color: var(--accent-aqua-vivid);   --kp-accent: var(--accent-aqua-vivid); }
.report-keypoint--caution  { border-top-color: var(--accent-yellow-vivid); --kp-accent: var(--accent-yellow-vivid); }
.report-keypoint--neutral  { border-top-color: var(--fuji-gray);           --kp-accent: var(--fuji-gray); }
.report-keypoint__title { font-weight: 800; margin-bottom: 0.5rem; color: var(--fg); display: flex; align-items: center; gap: 0.5rem; }
.report-keypoint__title::before { content: ""; width: 0.6rem; height: 0.6rem; border-radius: 0.2rem; background: var(--kp-accent, var(--accent-pink-vivid)); flex: none; }
.report-keypoint__body { font-size: var(--fs-body); line-height: 1.75; }
/* 統計タイル */
.report-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px,1fr)); gap: var(--space-3,0.75rem); margin: var(--space-5,1.5rem) 0; }
.report-stat { display: flex; flex-direction: column; gap: 0.2rem; padding: var(--space-3,0.75rem) var(--space-4,1rem); border-radius: 0.5rem; background: color-mix(in srgb, var(--section-accent, var(--accent-blue-vivid)) 7%, transparent); border: 1px solid color-mix(in srgb, var(--section-accent, var(--accent-blue-vivid)) 18%, transparent); }
.report-stat__label { font-size: var(--fs-small); color: var(--fg-dim); font-weight: 600; }
.report-stat__value { font-size: calc(1.9rem * var(--font-scale)); font-weight: 800; line-height: 1.1; color: var(--section-accent, var(--accent-blue-vivid)); font-variant-numeric: tabular-nums; }
.report-stat__note { font-size: 0.78rem; color: var(--fg-dim); }
.report-stat__trend { font-size: 0.9rem; margin-left: 0.2rem; }
.report-stat__trend--up { color: var(--accent-aqua-vivid); }
.report-stat__trend--down { color: var(--accent-pink-vivid); }
.report-stat__trend--flat { color: var(--fuji-gray); }
/* 引用ブロック */
.report-quote { margin: var(--space-4,1rem) 0; padding: var(--space-3,0.75rem) var(--space-5,1.5rem); border-left: 0.3rem solid var(--fuji-gray); color: var(--fg-dim); font-style: italic; background: rgba(103,103,108,0.05); border-radius: 0 0.4rem 0.4rem 0; }
/* callout に title を許容 */
.report-callout__title { color: var(--fg); }
/* 意味的配置: 本文と図の 2 カラム分割 */
.report-grid--2col { display: grid; grid-template-columns: 1.1fr 1fr; gap: var(--space-5,1.5rem); align-items: start; }
.report-grid__visual .report-visual { margin: 0; }
@media (max-width: 720px) { .report-grid--2col { grid-template-columns: 1fr; } }
/* section 強調度 (placement.emphasis) */
.report-section[data-emphasis="highlight"] { padding: var(--space-4,1rem) var(--space-4,1rem); border-radius: 0.6rem; background: color-mix(in srgb, var(--section-accent, var(--accent-blue-vivid)) 5%, transparent); }
.report-section[data-emphasis="muted"] { opacity: 0.82; }
/* 目次 (TOC) */
.report-toc { margin: 0 0 var(--space-7,3rem); padding: var(--space-4,1rem) var(--space-5,1.5rem); border-radius: 0.6rem; background: rgba(67,67,108,0.045); border: 1px solid rgba(67,67,108,0.12); }
.report-toc__title { font-weight: 800; font-size: var(--fs-small); letter-spacing: 0.08em; color: var(--fg-dim); margin-bottom: 0.5rem; }
.report-toc ol { list-style: none; margin: 0; padding: 0; columns: 2; column-gap: var(--space-6,2rem); }
.report-toc li { margin-bottom: 0.35rem; break-inside: avoid; }
.report-toc a { color: var(--fg); text-decoration: none; font-size: var(--fs-small); }
.report-toc a:hover { color: var(--report-accent, var(--accent-blue-vivid)); }
.report-toc__num { display: inline-block; min-width: 1.9em; color: var(--report-accent, var(--accent-blue-vivid)); font-weight: 700; font-variant-numeric: tabular-nums; }
/* 1.3.0: sticky sidebar TOC (スクロール追従・scrollspy 現在位置ハイライト) */
.report-toc--sidebar {
  position: sticky; top: var(--space-5, 1.5rem);
  max-height: calc(100vh - var(--space-6, 2rem) * 1.5);
  overflow-y: auto; margin: var(--space-7, 3rem) 0 0;
}
.report-toc--sidebar ol { columns: 1; }
.report-toc--sidebar li { margin-bottom: 0.45rem; }
.report-toc a.is-active { color: var(--report-accent, var(--accent-blue-vivid)); font-weight: 700; }
@media print { pre.report-code { box-shadow: none; } .report-toc ol { columns: 2; } }

/* ===== 1.2.0: 文書アーク / 節間接続 / 文書メタ / 新 block 型 ===== */
/* 文書全体の通し筋 (throughLine) — 導入部のアーク帯 */
.report-throughline {
  margin: var(--space-5,1.5rem) 0 var(--space-7, 3rem); padding: var(--space-5, 1.5rem) var(--space-6, 2rem);
  border-radius: 0.85rem; font-size: var(--fs-body); line-height: 1.8; color: var(--fg);
  background: #fff; border: 1px solid rgba(67,67,108,0.12);
  border-top: 3px solid var(--report-accent, var(--accent-blue-vivid));
  box-shadow: var(--shadow-subtle);
  display: flex; gap: var(--space-4,1rem); align-items: baseline; flex-wrap: wrap;
}
.report-throughline__label { font-size: var(--fs-small); font-weight: 800; letter-spacing: 0.05em; color: var(--report-accent, var(--accent-blue-vivid)); white-space: nowrap; }
/* part 単位 sub-arc (大規模文書の道標) */
.report-throughline-parts { list-style: none; margin: 0 0 var(--space-6, 2rem); padding: 0; display: grid; gap: 0.4rem; counter-reset: tlpart; }
.report-throughline__part { display: flex; gap: 0.7rem; align-items: baseline; padding: 0.4rem 0.7rem; border-left: 0.2rem solid color-mix(in srgb, var(--report-accent, var(--accent-blue-vivid)) 35%, transparent); background: color-mix(in srgb, var(--report-accent, var(--accent-blue-vivid)) 4%, transparent); border-radius: 0 0.4rem 0.4rem 0; }
.report-throughline__part-title { font-size: var(--fs-small); font-weight: 800; color: var(--report-accent, var(--accent-blue-vivid)); white-space: nowrap; }
.report-throughline__part-arc { font-size: var(--fs-small); line-height: 1.6; color: var(--fg); }
/* 文書メタ (version/updatedDate/readingTime) は report-meta の span を流用 */
/* 節末の次節への橋渡し (transition) */
.report-transition {
  margin: var(--space-4, 1rem) 0 0; padding: 0.5rem 0 0 var(--space-4, 1rem);
  font-size: var(--fs-small); color: var(--fg-dim); font-style: italic;
  border-left: 0.2rem solid color-mix(in srgb, var(--section-accent, var(--accent-blue-vivid)) 40%, transparent);
}
.report-transition::before { content: "→ "; font-weight: 700; font-style: normal; color: var(--section-accent, var(--accent-blue-vivid)); }
/* 定義リスト (term ↔ definition) */
.report-deflist { margin: var(--space-4,1rem) 0; display: grid; grid-template-columns: minmax(8rem, 14rem) 1fr; gap: 0.4rem var(--space-4,1rem); }
.report-deflist dt { font-weight: 800; color: var(--section-accent, var(--accent-blue-vivid)); }
.report-deflist dd { margin: 0; font-size: var(--fs-body); line-height: 1.75; }
@media (max-width: 720px) { .report-deflist { grid-template-columns: 1fr; } .report-deflist dd { margin-bottom: 0.5rem; } }
/* 脚注引用 (footnote + citation)。marker が採番を担うため ol の decimal は出さない (二重採番回避) */
.report-footnotes { margin: var(--space-5,1.5rem) 0 0; padding-top: var(--space-3,0.75rem); border-top: 1px solid rgba(67,67,108,0.18); font-size: var(--fs-small); color: var(--fg-dim); }
.report-footnotes ol { list-style: none; margin: 0; padding: 0; }
.report-footnotes li { margin-bottom: 0.35rem; line-height: 1.6; }
.report-footnotes li:target { background: color-mix(in srgb, var(--section-accent, var(--accent-blue-vivid)) 10%, transparent); border-radius: 0.3rem; }
.report-footnotes__marker { font-weight: 700; color: var(--section-accent, var(--accent-blue-vivid)); font-variant-numeric: tabular-nums; }
.report-footnotes__back { margin-left: 0.4rem; text-decoration: none; color: var(--section-accent, var(--accent-blue-vivid)); }
.report-footnotes cite { display: block; font-style: normal; font-size: 0.8rem; color: var(--fg-muted); margin-top: 0.1rem; }
/* 本文中の脚注参照 (上付き番号リンク) */
sup.report-fnref { font-size: 0.7em; line-height: 0; }
sup.report-fnref a { text-decoration: none; color: var(--section-accent, var(--accent-blue-vivid)); font-weight: 700; }
sup.report-fnref a:hover { text-decoration: underline; }
/* タスクリスト (次アクション・チェックボックス) */
.report-tasklist { list-style: none; margin: var(--space-4,1rem) 0; padding: 0; }
.report-tasklist li { display: flex; gap: 0.55rem; align-items: baseline; font-size: var(--fs-body); margin-bottom: 0.5rem; }
.report-tasklist__box { font-family: var(--font-mono); font-weight: 800; color: var(--section-accent, var(--accent-blue-vivid)); white-space: nowrap; }
.report-tasklist__box--done { color: var(--accent-aqua-vivid); }
.report-tasklist li.is-done .report-tasklist__text { color: var(--fg-dim); text-decoration: line-through; }
.report-tasklist__owner { font-size: var(--fs-small); color: var(--fg-muted); margin-left: 0.3rem; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}`;
}

/**
 * 最小 Markdown → HTML (決定論・安全)。
 * 先に escapeHtml して注入を防いだ上で、安全なパターンのみ再装飾する。
 * ブロック配列の各要素を段落 or 箇条書きへ変換。
 */
function renderParagraphs(paragraphs) {
  const blocks = Array.isArray(paragraphs) ? paragraphs : paragraphs ? [String(paragraphs)] : [];
  return blocks
    .map((raw) => {
      const block = String(raw == null ? '' : raw);
      const lines = block.split('\n').map((l) => l.trimEnd());
      const isList = lines.length > 0 && lines.every((l) => l.trim() === '' || /^\s*[-*]\s+/.test(l));
      if (isList && lines.some((l) => l.trim() !== '')) {
        const items = lines
          .filter((l) => l.trim() !== '')
          .map((l) => `    <li>${inlineMd(l.replace(/^\s*[-*]\s+/, ''))}</li>`)
          .join('\n');
        return `  <ul>\n${items}\n  </ul>`;
      }
      const html = lines.map((l) => inlineMd(l)).join('<br>\n    ');
      return `  <p>${html}</p>`;
    })
    .join('\n');
}

/** インライン装飾 (escape 後の安全な文字列に対してのみ適用) */
function inlineMd(text) {
  let s = escapeHtml(text);
  // [^id] footnote 参照 → 上付き番号リンク (id がレジストリに在るときのみ・無ければ字面温存)。
  // link 記法 [label](url) より先に処理し、footnote ref を確実に消費する。
  s = s.replace(/\[\^([a-z0-9][a-z0-9-]*)\]/gi, (m, id) => {
    const key = id.toLowerCase();
    const num = _footnoteRegistry[key];
    if (!num) return m;
    let refId = '';
    if (!_emittedFnrefs.has(key)) {
      _emittedFnrefs.add(key);
      refId = ` id="fnref-${escapeHtml(key)}"`;
    }
    return `<sup class="report-fnref"${refId}><a href="#fn-${escapeHtml(key)}">[${num}]</a></sup>`;
  });
  // [label](url) → <a> (url は http/https/相対のみ許可)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]*|[^\s):]+)\)/g, '<a href="$2">$1</a>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // ==要点== → 色付きハイライト (1.1.0・要点の色付き強調)。** より先に処理し衝突を避ける
  s = s.replace(/==([^=\n]+)==/g, '<mark class="report-hl">$1</mark>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  return s;
}

/**
 * visual (schema §visual: {kind, spec, caption, alt, rationale}) → HTML 片。
 * caption/alt は visual 直下から読む (spec 内ではない)。例外は fallback へ (render は落ちない)。
 * @returns {{ html: string, usesMermaid: boolean }}
 */
function renderVisual(visual, counters) {
  if (!visual || !visual.kind || visual.kind === 'none') return { html: '', usesMermaid: false };
  const spec = visual.spec || {};
  let caption = visual.caption || '';
  // 図表番号を自動付与 (1.1.0・caption があるビジュアルに 図N. を前置)
  if (caption && counters) {
    counters.fig += 1;
    caption = `図${counters.fig}. ${caption}`;
  }
  const alt = visual.alt || '';
  try {
    if (visual.kind === 'mermaid') {
      const def = spec.definition || '';
      return { html: renderMermaidFragment(def, { caption, ariaLabel: alt || spec.diagramType }), usesMermaid: true };
    }
    if (visual.kind === 'codex-image') {
      return { html: renderCodexImage(spec, { caption, alt }), usesMermaid: false };
    }
    if (visual.kind === 'svg') {
      return { html: renderSvgVisual(spec, { caption, alt }), usesMermaid: false };
    }
  } catch (e) {
    return { html: fallbackVisual(`ビジュアル生成に失敗: ${e.message}`, caption), usesMermaid: false };
  }
  return { html: '', usesMermaid: false };
}

/** diagramNode[] → svg-builder が食う item 配列に射影 (label/subtext を保持) */
function nodesToItems(nodes) {
  const arr = Array.isArray(nodes) ? nodes : [];
  return arr.map((n, i) => {
    if (n == null) return { label: '', number: i + 1 };
    if (typeof n === 'string') return { label: n, number: i + 1 };
    return { label: n.label || '', desc: n.subtext || '', number: i + 1, date: n.subtext || '' };
  });
}

/** diagramNode[] → {label, value} 配列 (slope/butterfly 用。value は node.value か subtext 内の数値) */
function nodesToValued(nodes) {
  const arr = Array.isArray(nodes) ? nodes : [];
  return arr.map((n, i) => {
    if (n == null) return { label: '', value: 0 };
    if (typeof n === 'string') return { label: n, value: 0 };
    let v = n.value;
    if (v == null && typeof n.subtext === 'string') {
      const m = n.subtext.match(/-?\d+(?:\.\d+)?/);
      v = m ? Number(m[0]) : 0;
    }
    return { label: n.label || '', value: Number(v) || 0 };
  });
}

/**
 * 中立 A対B 対比図 (report engine 固有・決定論)。svg-builder.buildVs が Before/After(bad/good) を
 * 固定描画し vendor byte-parity で改変できないため、中立対比 (両列対等・group 名タイトル・bullet) を
 * ここで描く。列色は wave-blue / wave-aqua の対等な2色。逐語値は本文表に温存し、図は対比構造を一目化する。
 */
function buildNeutralComparison(leftItems, rightItems, opts = {}) {
  const colW = 540, gap = 64, leftX = 40;
  const rightX = leftX + colW + gap;
  const headerH = 60, itemH = 54, padX = 22, itemGap = 12, topY = 36, bottomPad = 26;
  const L = (Array.isArray(leftItems) ? leftItems : []).slice(0, 6);
  const R = (Array.isArray(rightItems) ? rightItems : []).slice(0, 6);
  const maxItems = Math.max(L.length, R.length, 1);
  const cardH = headerH + 18 + maxItems * itemH + Math.max(0, maxItems - 1) * itemGap + bottomPad;
  const W = 1200, H = topY + cardH + 28;
  const BLUE = "var(--wave-blue, #7E9CD8)";
  const AQUA = "var(--wave-aqua, #7FB4CA)";

  function column(x, items, color, title) {
    const b = [];
    b.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${cardH}" rx="16" fill="#FFFFFF" stroke="#DCD7BA" stroke-width="1.5"/>`);
    b.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${headerH}" rx="16" fill="${color}" opacity="0.92"/>`);
    b.push(`<rect x="${x}" y="${topY + headerH - 16}" width="${colW}" height="16" fill="${color}" opacity="0.92"/>`);
    b.push(`<text x="${x + 24}" y="${topY + 38}" text-anchor="start" fill="#FFFFFF" font-size="22" font-weight="800" font-family="'Noto Sans JP', sans-serif">${escapeHtml(title)}</text>`);
    items.forEach((it, i) => {
      const y = topY + headerH + 16 + i * (itemH + itemGap);
      const raw = typeof it === 'string' ? it : (it && (it.label || it.text)) || '';
      const text = raw.length > 26 ? raw.slice(0, 26) + '…' : raw;
      b.push(`<rect x="${x + padX}" y="${y}" width="${colW - padX * 2}" height="${itemH}" rx="10" fill="#F8F7F0" stroke="#DCD7BA" stroke-width="1"/>`);
      b.push(`<rect x="${x + padX}" y="${y}" width="6" height="${itemH}" fill="${color}"/>`);
      b.push(`<circle cx="${x + padX + 30}" cy="${y + itemH / 2}" r="6" fill="${color}"/>`);
      b.push(`<text x="${x + padX + 50}" y="${y + itemH / 2 + 6}" text-anchor="start" fill="#43436c" font-size="17" font-weight="600" font-family="'Noto Sans JP', sans-serif">${escapeHtml(text)}</text>`);
    });
    return b.join('\n  ');
  }

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHtml(opts.ariaLabel || `${opts.leftTitle} と ${opts.rightTitle} の対比`)}" xmlns="http://www.w3.org/2000/svg">
  ${column(leftX, L, BLUE, opts.leftTitle || 'A')}
  ${column(rightX, R, AQUA, opts.rightTitle || 'B')}
</svg>`;
}

/** svgSpec {variant, nodes[], groups?} → svg-builder への dispatch (決定論) */
function renderSvgVisual(spec, meta) {
  const variant = spec.variant || 'flow';
  const opts = {};
  const items = nodesToItems(spec.nodes);
  let inner = '';

  if (variant === 'mindmap' && typeof svg.buildMindmap === 'function') {
    const center = items.length ? items[0].label : '';
    inner = svg.buildMindmap(center, items.slice(1).map((it) => it.label), opts);
  } else if (variant === 'network' && typeof svg.buildMindmap === 'function') {
    const center = items.length ? items[0].label : '';
    inner = svg.buildMindmap(center, items.slice(1).map((it) => it.label), opts);
  } else if (variant === 'comparison') {
    // comparison = 中立の A対B 対比。svg-builder.buildVs は Before/After(×○/pink=bad/good) を固定描画し
    // かつ vendor byte-parity で不可侵ゆえ使えない。report engine 側の中立レンダラ (両列対等・group 名タイトル・
    // bullet マーカー) で描く。before→after / bad→good の対比は slope/butterfly が担当 (owner 分離)。
    const cmpNodes = spec.nodes || [];
    const { left, right } = splitForComparison(cmpNodes);
    const cmpGroups = [...new Set(cmpNodes.map((n) => (n && n.group) || '').filter(Boolean))];
    inner = buildNeutralComparison(
      nodesToItems(left).map((i) => i.label),
      nodesToItems(right).map((i) => i.label),
      { leftTitle: cmpGroups[0] || 'A', rightTitle: cmpGroups[1] || 'B', ariaLabel: meta.alt },
    );
  } else if ((variant === 'slope' || variant === 'butterfly') && typeof svg[variant === 'slope' ? 'buildSlope' : 'buildButterfly'] === 'function') {
    // 数値対比 (before→after / 左右量): group で二分、node.value か subtext 数値を採る
    const { left, right } = splitForComparison(spec.nodes || []);
    const fn = variant === 'slope' ? svg.buildSlope : svg.buildButterfly;
    inner = fn(nodesToValued(left), nodesToValued(right), opts);
  } else if (VARIANT_SINGLE_ARG[variant] && typeof svg[VARIANT_SINGLE_ARG[variant]] === 'function') {
    inner = svg[VARIANT_SINGLE_ARG[variant]](items, opts);
  } else {
    return fallbackVisual(`未対応の svg variant: ${variant}`, meta.caption);
  }
  const caption = meta.caption ? `\n  <figcaption>${escapeHtml(meta.caption)}</figcaption>` : '';
  const label = meta.alt ? ` aria-label="${escapeHtml(meta.alt)}"` : '';
  return `<figure class="report-visual report-visual--svg" role="img"${label}>\n  ${inner}${caption}\n</figure>`;
}

/** comparison 用に nodes を左右へ決定論分割 (group 優先、無ければ半々) */
function splitForComparison(nodes) {
  const groups = [...new Set(nodes.map((n) => (n && n.group) || '').filter(Boolean))];
  if (groups.length >= 2) {
    return {
      left: nodes.filter((n) => n && n.group === groups[0]),
      right: nodes.filter((n) => n && n.group !== groups[0]),
    };
  }
  const mid = Math.ceil(nodes.length / 2);
  return { left: nodes.slice(0, mid), right: nodes.slice(mid) };
}

/**
 * aiVisualSpec → <img> (asset/slug) or composite プレースホルダ。
 * asset (WebP/PNG) 明示 or slug から images/<slug>.png を導出し <img> 参照埋込。
 * 双方無い場合 (backgroundSource=none 等) は overlayText を並べた決定論プレースホルダ。
 */
function renderCodexImage(spec, meta) {
  const alt = escapeHtml(meta.alt || spec.alt || (Array.isArray(spec.overlayText) ? spec.overlayText[0] : '') || '図');
  const caption = meta.caption ? `\n  <figcaption>${escapeHtml(meta.caption)}</figcaption>` : '';
  const src = spec.asset || (spec.slug ? `images/${spec.slug}.png` : '');
  if (src) {
    return `<figure class="report-visual report-visual--image">\n  <img src="${escapeHtml(src)}" alt="${alt}">${caption}\n</figure>`;
  }
  const overlays = Array.isArray(spec.overlayText) ? spec.overlayText : [];
  const overlayHtml = overlays.map((t) => `    <li>${escapeHtml(t)}</li>`).join('\n');
  return `<figure class="report-visual report-visual--image" role="img" aria-label="${alt}">
  <svg viewBox="0 0 960 320" role="img" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="960" height="320" fill="rgba(46,168,143,0.08)" rx="10"/><text x="480" y="60" text-anchor="middle" fill="var(--accent-aqua-vivid, #2EA88F)" font-size="20" font-weight="700" font-family="'Noto Sans JP', sans-serif">Codex Image (${escapeHtml(spec.pattern || 'image')})</text><text x="480" y="170" text-anchor="middle" fill="var(--fg-dim, #727169)" font-size="16" font-family="'Noto Sans JP', sans-serif">${alt}</text></svg>
  <ul class="composite-overlay">
${overlayHtml}
  </ul>${caption}
</figure>`;
}

/** 決定論フォールバック (render を落とさない) */
function fallbackVisual(msg, caption) {
  const cap = caption ? `\n  <figcaption>${escapeHtml(caption)}</figcaption>` : '';
  return `<figure class="report-visual report-visual--fallback">\n  <svg viewBox="0 0 960 200" role="img" aria-label="placeholder" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="960" height="200" fill="rgba(59,125,216,0.06)" rx="8"/><text x="480" y="105" text-anchor="middle" fill="var(--fg-dim, #727169)" font-size="18" font-family="'Noto Sans JP', sans-serif">${escapeHtml(msg)}</text></svg>${cap}\n</figure>`;
}

/** callouts[] → HTML (任意) */
function renderCallouts(callouts) {
  if (!Array.isArray(callouts) || callouts.length === 0) return '';
  return callouts
    .map((c) => {
      const kind = (c && c.kind) || 'note';
      return `  <aside class="report-callout report-callout--${escapeHtml(kind)}">${inlineMd((c && c.text) || '')}</aside>`;
    })
    .join('\n');
}

// ===== 1.1.0: 節内論理展開 / 構造化本文ブロック / 目次 =====

/** section.narrative (本質課題→解決→活用 / logic[]) → heading 直下の論理リード帯 */
function renderNarrative(narrative) {
  if (!narrative || typeof narrative !== 'object') return '';
  const cells = [];
  if (narrative.essence) cells.push(['本質課題', narrative.essence, 'essence']);
  if (narrative.approach) cells.push(['解決アプローチ', narrative.approach, 'approach']);
  if (narrative.leverage) cells.push(['どう活かすか', narrative.leverage, 'leverage']);
  let inner = '';
  if (cells.length) {
    inner = cells
      .map(([label, text, cls]) => `    <div class="report-narrative__cell report-narrative__cell--${cls}"><span class="report-narrative__label">${escapeHtml(label)}</span><span class="report-narrative__text">${inlineMd(text)}</span></div>`)
      .join('\n');
  } else if (Array.isArray(narrative.logic) && narrative.logic.length) {
    const roleLabel = { claim: '主張', evidence: '根拠', implication: '含意', action: '行動' };
    inner = narrative.logic
      .map((x) => `    <div class="report-narrative__cell"><span class="report-narrative__label">${escapeHtml(roleLabel[x && x.role] || (x && x.role) || '')}</span><span class="report-narrative__text">${inlineMd((x && x.text) || '')}</span></div>`)
      .join('\n');
  }
  if (!inner) return '';
  return `  <div class="report-narrative" role="note">\n${inner}\n  </div>`;
}

/** body[] (構造化ブロック配列) → HTML。table/code は counters で図表番号を採番 */
function renderBody(body, counters) {
  const blocks = Array.isArray(body) ? body : [];
  return blocks
    .map((b) => renderBlock(b, counters))
    .filter(Boolean)
    .join('\n');
}

/** 単一 body block → HTML (type で分岐・決定論) */
function renderBlock(b, counters) {
  if (!b || !b.type) return '';
  switch (b.type) {
    case 'paragraph':
      return `  <p>${inlineMd(b.text || '')}</p>`;
    case 'subheading': {
      const lv = b.level === 4 ? 4 : 3;
      return `  <h${lv} class="report-subheading">${inlineMd(b.text || '')}</h${lv}>`;
    }
    case 'bullet-list':
      return renderListBlock(b.items, 'ul');
    case 'ordered-list':
      return renderListBlock(b.items, 'ol');
    case 'table':
      return renderTableBlock(b, counters);
    case 'code':
      return renderCodeBlock(b, counters);
    case 'key-point':
      return renderKeyPoint(b);
    case 'stat-tile':
      return renderStatTile(b);
    case 'callout': {
      const variant = ['note', 'warning', 'tip', 'caution'].includes(b.variant) ? b.variant : 'note';
      const title = b.title ? `<strong class="report-callout__title">${inlineMd(b.title)}</strong> ` : '';
      return `  <aside class="report-callout report-callout--${variant}">${title}${inlineMd(b.text || '')}</aside>`;
    }
    case 'blockquote':
      return `  <blockquote class="report-quote">${inlineMd(b.text || '')}</blockquote>`;
    case 'definition-list':
      return renderDefinitionList(b);
    case 'footnote':
      return renderFootnotes(b);
    case 'task-list':
      return renderTaskList(b);
    default:
      return '';
  }
}

/** definition-list → <dl> (用語定義対 term↔definition・1.2.0) */
function renderDefinitionList(b) {
  const terms = Array.isArray(b.terms) ? b.terms : [];
  if (!terms.length) return '';
  const rows = terms
    .filter((t) => t && t.term)
    .map((t) => `    <dt>${inlineMd(String(t.term))}</dt>\n    <dd>${inlineMd(String(t.definition == null ? '' : t.definition))}</dd>`)
    .join('\n');
  if (!rows) return '';
  return `  <dl class="report-deflist">\n${rows}\n  </dl>`;
}

/** footnote → 脚注引用帯 (marker 自動採番 + citation・1.2.0) */
function renderFootnotes(b) {
  const notes = Array.isArray(b.footnotes) ? b.footnotes : [];
  if (!notes.length) return '';
  const lis = notes
    .filter((n) => n && (n.text || n.citation))
    .map((n, i) => {
      const reg = n.id ? _footnoteRegistry[n.id] : 0;
      let anchorId = '';
      let marker;
      let backlink = '';
      if (reg) {
        // id 付き: 文書レベル連番 + 係り先アンカー + 本文へ戻るリンク。
        anchorId = ` id="fn-${escapeHtml(n.id)}"`;
        marker = `<span class="report-footnotes__marker">[${reg}]</span> `;
        backlink = ` <a class="report-footnotes__back" href="#fnref-${escapeHtml(n.id)}" aria-label="本文へ戻る">↩</a>`;
      } else {
        marker = n.marker ? `<span class="report-footnotes__marker">${escapeHtml(String(n.marker))}</span> ` : `<span class="report-footnotes__marker">[${i + 1}]</span> `;
      }
      const cite = n.citation ? `<cite>${inlineMd(String(n.citation))}</cite>` : '';
      return `    <li${anchorId}>${marker}${inlineMd(String(n.text == null ? '' : n.text))}${cite}${backlink}</li>`;
    })
    .join('\n');
  if (!lis) return '';
  return `  <aside class="report-footnotes" role="doc-endnotes">\n    <ol>\n${lis}\n    </ol>\n  </aside>`;
}

/** task-list → 次アクションのチェックリスト (done でチェック状態・1.2.0) */
function renderTaskList(b) {
  const tasks = Array.isArray(b.tasks) ? b.tasks : [];
  if (!tasks.length) return '';
  const lis = tasks
    .filter((t) => t && t.text)
    .map((t) => {
      const done = t.done === true;
      const box = done
        ? '<span class="report-tasklist__box report-tasklist__box--done" aria-hidden="true">[x]</span>'
        : '<span class="report-tasklist__box" aria-hidden="true">[ ]</span>';
      const owner = t.owner ? `<span class="report-tasklist__owner">(${escapeHtml(String(t.owner))})</span>` : '';
      const state = done ? ' 完了' : ' 未完了';
      return `    <li class="${done ? 'is-done' : ''}"><span class="visually-hidden">${state}</span>${box}<span class="report-tasklist__text">${inlineMd(String(t.text))}</span>${owner}</li>`;
    })
    .join('\n');
  if (!lis) return '';
  return `  <ul class="report-tasklist" role="list">\n${lis}\n  </ul>`;
}

/** bullet-list / ordered-list → <ul>/<ol> (番号リストの順序保持) */
function renderListBlock(items, tag) {
  const arr = Array.isArray(items) ? items : [];
  if (!arr.length) return '';
  const lis = arr.map((i) => `    <li>${inlineMd(String(i))}</li>`).join('\n');
  return `  <${tag} class="report-list report-list--${tag}">\n${lis}\n  </${tag}>`;
}

/** table block → <table> (markdown 表が <br> で潰れる問題を解消・図表番号採番) */
function renderTableBlock(b, counters) {
  const headers = Array.isArray(b.headers) ? b.headers : [];
  const rows = Array.isArray(b.rows) ? b.rows : [];
  if (!headers.length && !rows.length) return '';
  const thead = headers.length
    ? `    <thead><tr>${headers.map((h) => `<th>${inlineMd(String(h))}</th>`).join('')}</tr></thead>\n`
    : '';
  const tbody = `    <tbody>${rows
    .map((r) => `<tr>${(Array.isArray(r) ? r : []).map((c) => `<td>${inlineMd(String(c))}</td>`).join('')}</tr>`)
    .join('')}</tbody>`;
  let cap = '';
  if (b.caption) {
    counters.table += 1;
    cap = `\n    <figcaption>表${counters.table}. ${escapeHtml(b.caption)}</figcaption>`;
  }
  return `  <figure class="report-table-wrap">\n    <table class="report-table">\n${thead}${tbody}\n    </table>${cap}\n  </figure>`;
}

/** code block → <pre><code> (フェンスドコードブロックのパース・言語ラベル/図表番号) */
function renderCodeBlock(b, counters) {
  const code = String(b.code == null ? '' : b.code);
  const lang = b.language ? `<span class="report-code__lang">${escapeHtml(b.language)}</span>` : '';
  let cap = '';
  if (b.caption) {
    counters.code += 1;
    cap = `\n    <figcaption>コード${counters.code}. ${escapeHtml(b.caption)}</figcaption>`;
  }
  return `  <figure class="report-code-wrap">${lang}\n    <pre class="report-code"><code>${escapeHtml(code)}</code></pre>${cap}\n  </figure>`;
}

/** key-point → 色付きハイライトボックス (要点の色付き強調・意匠 accent トーン流用) */
function renderKeyPoint(b) {
  const tone = ['accent', 'positive', 'caution', 'neutral'].includes(b.tone) ? b.tone : 'accent';
  const title = b.title ? `<div class="report-keypoint__title">${inlineMd(b.title)}</div>` : '';
  return `  <div class="report-keypoint report-keypoint--${tone}">${title}<div class="report-keypoint__body">${inlineMd(b.text || '')}</div></div>`;
}

/** stat-tile → 統計タイル群 (label/value/trend) */
function renderStatTile(b) {
  const stats = Array.isArray(b.stats) ? b.stats : [];
  if (!stats.length) return '';
  const glyph = { up: '▲', down: '▼', flat: '—' };
  const tiles = stats
    .map((s) => {
      const label = s && s.label ? `<span class="report-stat__label">${escapeHtml(s.label)}</span>` : '';
      const trend = s && s.trend ? `<span class="report-stat__trend report-stat__trend--${escapeHtml(s.trend)}">${glyph[s.trend] || ''}</span>` : '';
      const note = s && s.note ? `<span class="report-stat__note">${escapeHtml(s.note)}</span>` : '';
      return `    <div class="report-stat">${label}<span class="report-stat__value">${escapeHtml((s && s.value) || '')} ${trend}</span>${note}</div>`;
    })
    .join('\n');
  return `  <div class="report-stats">\n${tiles}\n  </div>`;
}

/** meta.toc=true 時、section heading から決定論的に目次を生成 */
function renderToc(sections) {
  const items = sections
    .filter((s) => s && s.heading)
    .map((s, i) => {
      const num = String(i + 1).padStart(2, '0');
      const id = s.id ? escapeHtml(s.id) : `section-${i + 1}`;
      return `      <li><a href="#${id}"><span class="report-toc__num">${num}</span>${escapeHtml(s.heading)}</a></li>`;
    })
    .join('\n');
  if (!items) return '';
  return `  <nav class="report-toc report-toc--sidebar" aria-label="目次">\n    <div class="report-toc__title">目次</div>\n    <ol>\n${items}\n    </ol>\n  </nav>`;
}

/**
 * sticky sidebar TOC の scrollspy (1.3.0)。
 * 自己完結・再実行可能な controller として、初期 hash / TOC click / manual scroll /
 * hashchange / popstate / font-ready / print lifecycle を同じ activate 経路へ収束させる。
 * beforeprint で監視を停止し、afterprint で直前位置を復元して再起動する
 * (ハイライトは print CSS 側でも無効化する二重化)。
 */
function reportScrollspyScript() {
  return `<script>
(function () {
  'use strict';
  var CONTROLLER_KEY = '__slideReportScrollspy';
  if (window[CONTROLLER_KEY] && typeof window[CONTROLLER_KEY].destroy === 'function') {
    window[CONTROLLER_KEY].destroy(); /* script 再評価時も listener/observer を重複させない */
  }
  var nav = document.querySelector('.report-toc--sidebar');
  if (!nav) return;
  var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
  var map = {};
  var targets = [];
  function fragmentId(value) {
    try { return decodeURIComponent(String(value || '').replace(/^#/, '')); }
    catch (_) { return ''; }
  }
  links.forEach(function (a) {
    var id = fragmentId(a.getAttribute('href'));
    var el = document.getElementById(id);
    if (el) { map[id] = { link: a, target: el }; targets.push(el); }
  });
  if (!targets.length) return;
  var current = null;
  var restoreAfterPrint = null;
  var observer = null;
  var scrollFrame = null;
  var running = false;
  var printing = !!(window.matchMedia && window.matchMedia('print').matches);
  function activate(id) {
    if (current === id || !map[id]) return;
    current = id;
    links.forEach(function (a) { a.classList.remove('is-active'); a.removeAttribute('aria-current'); });
    map[id].link.classList.add('is-active');
    map[id].link.setAttribute('aria-current', 'location'); /* 現在位置を支援技術へ同期 (色非依存の第2チャネル) */
  }
  function syncFromScroll() {
    if (!running || printing) return;
    var marker = Math.max(1, window.innerHeight * 0.28);
    var candidate = targets[0];
    targets.forEach(function (target) {
      if (target.getBoundingClientRect().top <= marker) candidate = target;
    });
    activate(candidate.id);
  }
  function scheduleScrollSync() {
    if (scrollFrame !== null) return;
    scrollFrame = window.requestAnimationFrame(function () {
      scrollFrame = null;
      syncFromScroll();
    });
  }
  function syncFromLocation(reland) {
    var id = fragmentId(window.location.hash);
    if (!map[id]) return false;
    activate(id);
    if (reland) {
      window.requestAnimationFrame(function () {
        if (!printing && map[id]) {
          map[id].target.scrollIntoView({ block: 'start' });
          activate(id);
        }
      });
    }
    return true;
  }
  function start() {
    if (running || printing) return;
    running = true;
    window.addEventListener('scroll', scheduleScrollSync, { passive: true });
    if (typeof IntersectionObserver !== 'undefined') {
      observer = new IntersectionObserver(scheduleScrollSync, {
        rootMargin: '0px 0px -72% 0px', threshold: 0
      });
      targets.forEach(function (target) { observer.observe(target); });
    }
    if (!syncFromLocation(false)) syncFromScroll();
  }
  function stop() {
    if (!running) return;
    running = false;
    window.removeEventListener('scroll', scheduleScrollSync);
    if (observer) { observer.disconnect(); observer = null; }
    if (scrollFrame !== null) {
      window.cancelAnimationFrame(scrollFrame);
      scrollFrame = null;
    }
  }
  function onTocClick(event) {
    var id = fragmentId(event.currentTarget.getAttribute('href'));
    activate(id); /* default anchor navigation/hash update は維持し、active 状態だけ即時同期 */
  }
  function onHistoryNavigation() {
    if (!printing) window.requestAnimationFrame(function () { syncFromLocation(true); });
  }
  function onBeforePrint() {
    restoreAfterPrint = current;
    printing = true;
    stop();
  }
  function onAfterPrint() {
    printing = false;
    start();
    var id = fragmentId(window.location.hash);
    if (map[id]) activate(id);
    else if (restoreAfterPrint && map[restoreAfterPrint]) activate(restoreAfterPrint);
    else syncFromScroll();
    restoreAfterPrint = null;
  }
  function destroy() {
    stop();
    links.forEach(function (a) { a.removeEventListener('click', onTocClick); });
    window.removeEventListener('hashchange', onHistoryNavigation);
    window.removeEventListener('popstate', onHistoryNavigation);
    window.removeEventListener('beforeprint', onBeforePrint);
    window.removeEventListener('afterprint', onAfterPrint);
    if (window[CONTROLLER_KEY] === controller) delete window[CONTROLLER_KEY];
  }
  var controller = { start: start, stop: stop, destroy: destroy, sync: onHistoryNavigation };
  window[CONTROLLER_KEY] = controller;
  links.forEach(function (a) { a.addEventListener('click', onTocClick); });
  window.addEventListener('hashchange', onHistoryNavigation);
  window.addEventListener('popstate', onHistoryNavigation);
  window.addEventListener('beforeprint', onBeforePrint);
  window.addEventListener('afterprint', onAfterPrint);
  start();
  syncFromLocation(true); /* 初期 hash を observer の初回 callback より優先 */
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      if (!printing && !syncFromLocation(true)) scheduleScrollSync();
    });
  }
})();
</scr` + `ipt>`;
}

/** meta.throughLine (+ throughLineParts) → 導入部の文書アーク帯 (本質課題→解決→活用の通し筋・1.2.0) */
function renderThroughLine(throughLine, parts) {
  const hasTL = throughLine && typeof throughLine === 'string' && throughLine.trim();
  const partList = Array.isArray(parts) ? parts.filter((p) => p && p.arc) : [];
  if (!hasTL && !partList.length) return '';
  const mainBand = hasTL
    ? `  <div class="report-throughline" role="note"><span class="report-throughline__label">通し筋</span><span class="report-throughline__text">${inlineMd(throughLine)}</span></div>`
    : '';
  if (!partList.length) return mainBand;
  // part 単位 sub-arc (大規模文書の道標)。
  const items = partList
    .map((p, i) => {
      const title = p.title ? inlineMd(String(p.title)) : `第${i + 1}部`;
      return `    <li class="report-throughline__part"><span class="report-throughline__part-title">${title}</span><span class="report-throughline__part-arc">${inlineMd(String(p.arc))}</span></li>`;
    })
    .join('\n');
  const partsBand = `  <ol class="report-throughline-parts" aria-label="部構成">\n${items}\n  </ol>`;
  return mainBand ? mainBand + '\n' + partsBand : partsBand;
}

/** section.transition → 節末の次節への橋渡し1文 (節間接続・1.2.0) */
function renderTransition(transition) {
  if (!transition || typeof transition !== 'string' || !transition.trim()) return '';
  return `  <p class="report-transition">${inlineMd(transition)}</p>`;
}

/**
 * report-structure オブジェクト → report.html 全文 (決定論)。
 * section は配列順でレンダ (readingOrder は視線方向ヒントであり並び替えキーではない)。
 * @param {object} structure report-structure.schema.json 準拠オブジェクト
 * @returns {string} 完結した HTML 文書
 */
export function renderReport(structure) {
  const meta = (structure && structure.meta) || {};
  const reportType = meta.reportType || 'internal-analysis';
  const accent = REPORT_TYPE_ACCENT[reportType] || 'accent-blue-vivid';
  const title = escapeHtml(meta.title || 'レポート');
  const sections = Array.isArray(structure && structure.sections) ? structure.sections : [];

  // 1.2.0: footnote インライン係り先アンカーの文書レベルレジストリを本文レンダ前に構築する。
  _footnoteRegistry = buildFootnoteRegistry(sections);
  _emittedFnrefs = new Set();

  let usesMermaid = false;
  const counters = { fig: 0, table: 0, code: 0 }; // 図表番号の決定論採番 (1.1.0)
  const sectionHtml = sections
    .map((sec, idx) => {
      const heading = escapeHtml((sec && sec.heading) || '');
      const secNum = String(idx + 1).padStart(2, '0');
      const secAccent = REPORT_TYPE_ACCENT[(sec && sec.reportType) || reportType] || accent;
      const vis = renderVisual(sec && sec.visual, counters);
      if (vis.usesMermaid) usesMermaid = true;
      const narrative = renderNarrative(sec && sec.narrative);
      // body[] 優先・排他 (1.1.0)。存在すれば paragraphs[] を無視。無ければ paragraphs[] (1.0.0 後方互換)
      const bodyHtml = Array.isArray(sec && sec.body) && sec.body.length
        ? renderBody(sec.body, counters)
        : renderParagraphs(sec && sec.paragraphs);
      const callouts = renderCallouts(sec && sec.callouts);
      const idAttr = sec && sec.id ? ` id="${escapeHtml(sec.id)}"` : '';
      const roleAttr = sec && sec.role ? ` data-role="${escapeHtml(sec.role)}"` : '';
      const layout = (sec && sec.visual && sec.visual.layout) || {};
      // readingOrder: section 直下 (1.1.0) を優先し、無ければ placement へ移設された layout.readingOrder (1.2.0)
      const readingOrder = (sec && sec.readingOrder) || layout.readingOrder;
      const orderAttr = readingOrder ? ` data-reading-order="${escapeHtml(readingOrder)}"` : '';
      // emphasisZone (1.2.0) を優先し emphasis (1.1.0 deprecated alias) へ後方互換フォールバック
      const emphasis = (layout.emphasisZone && layout.emphasisZone !== 'normal' ? layout.emphasisZone : '') || (layout.emphasis && layout.emphasis !== 'normal' ? layout.emphasis : '');
      const emphAttr = emphasis ? ` data-emphasis="${escapeHtml(emphasis)}"` : '';
      // focalPoint (1.2.0): placement へ移設された focal を優先し section 直下へ後方互換フォールバック。
      // readingOrder と同じく視覚配置ヒントとして data 属性 + CSS var で live 露出する (dead field 化を防ぐ)。
      const focal = layout.focalPoint || (sec && sec.focalPoint);
      const hasFocal = focal && (typeof focal.x === 'number' || typeof focal.y === 'number');
      const fx = hasFocal && typeof focal.x === 'number' ? focal.x : 50;
      const fy = hasFocal && typeof focal.y === 'number' ? focal.y : 50;
      const focalAttr = hasFocal ? ` data-focal="${fx},${fy}"` : '';
      const focalVar = hasFocal ? ` --focal: ${fx}% ${fy}%;` : '';
      // 意味的配置 (1.1.0): grid が 2 列 (例 '2x1') かつ visual があれば本文と図を左右分割。無ければ従来の縦積み
      const twoCol = typeof layout.grid === 'string' && /^2x/.test(layout.grid) && vis.html;
      let inner;
      if (twoCol) {
        inner = `${narrative ? narrative + '\n' : ''}  <div class="report-grid report-grid--2col">
    <div class="report-grid__prose">
${bodyHtml}
${callouts ? callouts + '\n' : ''}    </div>
    <div class="report-grid__visual">${vis.html}</div>
  </div>`;
      } else {
        inner = `${narrative ? narrative + '\n' : ''}${bodyHtml}
${callouts ? callouts + '\n' : ''}  ${vis.html}`;
      }
      const transition = renderTransition(sec && sec.transition);
      return `<section class="report-section"${idAttr}${roleAttr}${orderAttr}${emphAttr}${focalAttr} style="--section-accent: var(--${secAccent});${focalVar}">
  <h2 data-secnum="${secNum}">${heading}</h2>
${inner}${transition ? '\n' + transition : ''}
</section>`;
    })
    .join('\n');

  const tocHtml = meta.toc ? renderToc(sections) : '';
  const throughLineHtml = renderThroughLine(meta.throughLine, meta.throughLineParts);

  // meta 行 (schema 準拠: audience/keyMessage/author/length。date/reader は無い)
  const metaBits = [];
  metaBits.push(`<span class="report-type-badge">${escapeHtml(reportTypeLabel(reportType))}</span>`);
  if (meta.audience) metaBits.push(`<span>読者: ${escapeHtml(meta.audience)}</span>`);
  if (meta.author) metaBits.push(`<span>著者: ${escapeHtml(meta.author)}</span>`);
  if (meta.length) metaBits.push(`<span>分量: ${escapeHtml(lengthLabel(meta.length))}</span>`);
  if (meta.createdAt) metaBits.push(`<span>作成: ${escapeHtml(meta.createdAt)}</span>`);
  // 文書メタ (1.2.0): version/updatedDate/readingTime
  if (meta.version) metaBits.push(`<span class="report-meta__doc">版: ${escapeHtml(meta.version)}</span>`);
  if (meta.updatedDate) metaBits.push(`<span class="report-meta__doc">更新: ${escapeHtml(meta.updatedDate)}</span>`);
  if (meta.readingTime) metaBits.push(`<span class="report-meta__doc">読了目安: ${escapeHtml(meta.readingTime)}</span>`);

  const subtitle = meta.subtitle ? `\n    <p class="report-subtitle">${escapeHtml(meta.subtitle)}</p>` : '';
  const keyMessage = meta.keyMessage ? `\n    <p class="report-keymessage">${escapeHtml(meta.keyMessage)}</p>` : '';

  const head = [
    '<!DOCTYPE html>',
    '<html lang="' + escapeHtml(meta.language || 'ja') + '">',
    '<head>',
    '<meta charset="UTF-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '<meta name="generator" content="slide-report-generator/render-report">',
    `<meta name="report-type" content="${escapeHtml(reportType)}">`,
    `<meta name="theme-name" content="${escapeHtml(themeName(structure && structure.theme))}">`,
    `<title>${title}</title>`,
    `<style>\n${buildReportCss(SPEC)}\n</style>`,
    usesMermaid ? mermaidInitScript() : '',
    '</head>',
  ]
    .filter(Boolean)
    .join('\n');

  // 1.3.0: screen は sidebar(TOC)+本文カラムの grid、print/狭画面は CSS 側で block へ degrade。
  // TOC が無ければ --no-toc で本文 1 カラム中央寄せ。
  const sidebarHtml = tocHtml ? `  <aside class="report-sidebar">\n${tocHtml}\n  </aside>\n` : '';
  const layoutClass = tocHtml ? 'report-layout' : 'report-layout report-layout--no-toc';
  const scrollspy = tocHtml ? reportScrollspyScript() : '';

  return `${head}
<body style="--report-accent: var(--${accent});">
<div class="${layoutClass}">
${sidebarHtml}  <main class="report">
  <header class="report-header">
    <h1 class="report-title">${title}</h1>${subtitle}${keyMessage}
    <div class="report-meta">
      ${metaBits.join('\n      ')}
    </div>
  </header>
${throughLineHtml ? throughLineHtml + '\n' : ''}${sectionHtml}
  <footer class="report-footer">slide-report-generator · report mode · theme: ${escapeHtml(themeName(structure && structure.theme))}</footer>
  </main>
</div>
${scrollspy}
</body>
</html>
`;
}

/** reportType enum → 日本語ラベル (§D) */
function reportTypeLabel(rt) {
  return (
    {
      'internal-analysis': '社内報告分析',
      'client-proposal': '顧客提案',
      'tech-doc': '技術ドキュメント',
      learning: '学習解説',
    }[rt] || rt
  );
}

/** length enum → 日本語ラベル */
function lengthLabel(len) {
  return { brief: '短報', standard: '標準', deep: '精読' }[len] || len;
}

// ---- CLI ----
function isMain() {
  return process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (isMain()) {
  const [inPath, outPath] = process.argv.slice(2);
  if (!inPath || !outPath) {
    console.error('usage: node render-report.js <report-structure.json> <out.html>');
    process.exit(2);
  }
  try {
    const structure = JSON.parse(readFileSync(inPath, 'utf-8'));
    const html = renderReport(structure);
    writeFileSync(outPath, html, 'utf-8');
    console.log(`render-report: wrote ${outPath} (${Buffer.byteLength(html)} bytes, ${(structure.sections || []).length} sections)`);
  } catch (e) {
    console.error(`render-report error: ${e.message}`);
    process.exit(1);
  }
}
