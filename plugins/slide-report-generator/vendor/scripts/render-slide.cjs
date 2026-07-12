#!/usr/bin/env node
/**
 * render-slide.js — structure.json から決定論 HTML/CSS/JS を生成
 *
 * Usage:
 *   node scripts/render-slide.js <structure.json> --out <output-dir>
 *
 * 入力: structure.json (schemas/structure.schema.json で検証)
 * 出力:
 *   <out>/index.html  ... HTML scaffold + 全スライド断片
 *   <out>/styles.css  ... SR-ID 駆動 CSS + pagination.css
 *   <out>/scripts.js  ... GSAP 安全パターン (SR-6-01..04) 固定
 *   <out>/structure.json ... 入力の同期コピー (SR-12-07)
 *   <out>/structure.md ... sync-checker 用の同期 Markdown
 *
 * SR-12-08: HTML/CSS/JS は完全分離、インライン禁止。
 */
'use strict';

const fs = require('fs');
const path = require('path');

const { render, escapeHtml } = require('./template-engine.cjs');
const { buildStyles } = require('./style-builder.cjs');
const svg = require('./svg-builder.cjs');
const { renderD3BootstrapJs } = require('./d3-bootstrap.cjs');

const SKILL_ROOT = path.resolve(__dirname, '..');
const TEMPLATE_DIR = path.join(__dirname, 'templates');
const ASSETS = path.join(SKILL_ROOT, 'assets');
const SCHEMA_PATH = path.join(SKILL_ROOT, 'schemas', 'structure.schema.json');

// ---------- minimal JSON Schema validator (subset) ----------
function validateSchema(data, schema, p = 'root', errors = []) {
  if (!schema) return errors;
  if (schema.type) {
    const t = Array.isArray(data) ? 'array' : data === null ? 'null' : typeof data;
    const expect = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!expect.includes(t)) errors.push(`${p}: expected ${expect.join('|')}, got ${t}`);
  }
  if (schema.required && data && typeof data === 'object') {
    for (const k of schema.required) if (!(k in data)) errors.push(`${p}.${k}: required`);
  }
  if (schema.properties && data && typeof data === 'object') {
    for (const [k, sub] of Object.entries(schema.properties)) {
      if (k in data) validateSchema(data[k], sub, `${p}.${k}`, errors);
    }
  }
  if (schema.items && Array.isArray(data)) {
    data.forEach((it, i) => validateSchema(it, schema.items, `${p}[${i}]`, errors));
  }
  if (schema.enum && data !== undefined && !schema.enum.includes(data)) {
    errors.push(`${p}: must be one of ${JSON.stringify(schema.enum)}`);
  }
  return errors;
}

// ---------- args ----------
function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') args.out = argv[++i];
    else if (a === '--no-validate') args.noValidate = true;
    else if (a.startsWith('--')) args[a.slice(2)] = argv[++i];
    else args._.push(a);
  }
  return args;
}

// ---------- template loading ----------
const templateCache = {};
function loadTemplate(slideType) {
  if (templateCache[slideType]) return templateCache[slideType];
  // 直接マッチを試行 → schema 長名（slide-X）にフォールバック → message
  const candidates = [slideType];
  // alias 短縮名→長名
  const alias = TYPE_ALIASES && TYPE_ALIASES[slideType];
  if (alias) candidates.push(alias);
  candidates.push('slide-message', 'message');
  for (const cand of candidates) {
    const p = path.join(TEMPLATE_DIR, `${cand}.html.tpl`);
    if (fs.existsSync(p)) {
      const t = fs.readFileSync(p, 'utf8');
      templateCache[slideType] = t;
      return t;
    }
  }
  return '<section class="slider__item"><div class="slider__content"><h2>{{title}}</h2></div></section>';
}

// ---------- slideType エイリアス（既存 24 短縮名 -> schema enum 名） ----------
const TYPE_ALIASES = {
  // 既存テンプレファイル名（短縮名）が schema 上の長い名にマップされる
  title: 'slide-title', hero: 'slide-hero', quote: 'slide-quote',
  message: 'slide-message', list: 'slide-list', 'icon-grid': 'slide-icon-grid',
  grid: 'slide-grid', pyramid: 'slide-pyramid', circle: 'slide-circle',
  compare: 'slide-compare', 'code-compare': 'slide-code-compare',
  flow: 'slide-flow', process: 'slide-process', timeline: 'slide-timeline',
  table: 'slide-table', code: 'slide-code', highlight: 'slide-highlight',
};
function normalizeSlideType(t) {
  return TYPE_ALIASES[t] || t;
}

function mdCell(value) {
  return String(value ?? '').replace(/\|/g, '\\|').replace(/\s+/g, ' ').trim();
}

function slideTitle(slide) {
  const c = slide.content || {};
  return c.title || slide.title || c.main || c.subtitle || slide.id || '';
}

function itemLabel(item) {
  if (item === null || item === undefined) return '';
  if (typeof item === 'string' || typeof item === 'number') return String(item);
  return item.label || item.title || item.name || item.text || item.value || '';
}

function normalizeTextList(items) {
  return (items || []).map(itemLabel).filter(Boolean);
}

function normalizeCell(cell) {
  if (cell === null || cell === undefined) return '';
  if (typeof cell === 'string' || typeof cell === 'number') return String(cell);
  return cell.text || cell.label || cell.title || cell.value || '';
}

function buildStructureMd(data) {
  const meta = data.meta || {};
  const sections = Object.fromEntries((data.sections || []).map((s) => [s.id, s.title || s.label || s.id]));
  const rows = (data.slides || []).map((slide, i) => {
    const type = normalizeSlideType(slide.slideType || '');
    const section = sections[slide.section] || slide.section || '';
    return `| ${i + 1} | ${mdCell(type)} | ${mdCell(slideTitle(slide))} | ${mdCell(section)} |`;
  });
  return `# ${mdCell(meta.title || 'Presentation')}

## Slides

| # | Type | Title | Section |
|---|---|---|---|
${rows.join('\n')}
`;
}

// ---------- D3 component map (slideType -> d3-components/* component name) ----------
const D3_COMPONENTS = {
  'd3-cycle': 'cycle', 'd3-pdca': 'pdca', 'd3-triangle-cycle': 'triangle-cycle',
  'd3-rotating-flow': 'rotating-flow',
  'd3-tree': 'tree', 'd3-org-chart': 'org-chart', 'd3-sunburst': 'sunburst',
  'd3-treemap': 'treemap', 'd3-packed-circles': 'packed', 'd3-dendrogram': 'dendrogram',
  'd3-force': 'force', 'd3-chord': 'chord', 'd3-arc': 'arc', 'd3-sankey': 'sankey',
  'd3-roadmap': 'roadmap', 'd3-vertical-timeline': 'vertical-timeline',
  'd3-pyramid': 'pyramid', 'd3-funnel': 'funnel', 'd3-waterfall': 'waterfall',
  'd3-bar': 'bar', 'd3-line': 'line', 'd3-pie': 'pie', 'd3-donut': 'donut',
  'd3-radar': 'radar', 'd3-gauge': 'gauge', 'd3-bubble': 'bubble',
  'd3-heatmap': 'heatmap', 'd3-radial-bar': 'radial-bar', 'd3-bullet': 'bullet',
  'd3-lollipop': 'lollipop', 'd3-calendar': 'calendar', 'd3-isotype': 'isotype',
  'd3-wordcloud': 'wordcloud',
};

// ---------- per-slideType: SVG / config 拡張 ----------
function enrichSlideContext(slide, idx) {
  const slideType = normalizeSlideType(slide.slideType);
  // schema 形式 (slide.content.*) を flatten すると共に、後方互換の短縮形 (slide.title 等) も維持
  const c = slide.content || {};
  const ctx = {
    ...slide,
    ...c,
    slideType,
    index: idx,
    section: slide.section || 'main',
    title: c.title != null ? c.title : slide.title,
  };
  const aria = ctx.title || slideType;

  // ---- SVG dispatch ----
  if (slideType === 'slide-flow' || slideType === 'flow' ||
      slideType === 'diagram-fabe-horizontal' ||
      slideType === 'diagram-flowchart' || slideType === 'diagram-roadmap') {
    const items = c.steps || c.items || slide.items || slide.steps || [];
    ctx.svg = svg.buildHorizontalFlow(items, { ariaLabel: aria });
  } else if (slideType === 'slide-circle' || slideType === 'circle' ||
             slideType === 'diagram-cycle' || slideType === 'diagram-cycle-flow-1' ||
             slideType === 'diagram-pdca' || slideType === 'diagram-triangle-cycle' ||
             slideType === 'diagram-fabe-circular') {
    // v7.5.0: buildCycle に subtext/headline を渡してキャプション表示
    const items = c.steps || c.satellites || c.items || slide.items || slide.steps || [];
    ctx.svg = svg.buildCycle(items, {
      ariaLabel: aria,
      headline: c.headline || c.lead || c.subtitle || '',
      subtext: c.subtext || c.description || c.caption || c.summary || '',
    });
  } else if (slideType === 'slide-pyramid' || slideType === 'pyramid' ||
             slideType === 'diagram-value-stack') {
    ctx.svg = svg.buildPyramid(c.levels || c.items || slide.layers || slide.items || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-business-prep' || slideType === 'diagram-prep' ||
             slideType === 'diagram-org' || slideType === 'diagram-fabe-vertical') {
    let layers = c.layers || slide.layers;
    if (!layers) {
      // PREP 構造から自動生成
      layers = [c.point, c.reason, c.example, c.point_again].filter(Boolean);
      if (!layers.length) layers = c.items || slide.items || [];
    }
    ctx.svg = svg.buildHierarchy(layers, { ariaLabel: aria });
  } else if (slideType === 'diagram-comparison-1' || slideType === 'diagram-vs') {
    // v7.5.0: 真の Before/After 2カラム比較（buildVs）に切替
    const lItems = (c.left && c.left.items) || (slide.before && slide.before.items) || [];
    const rItems = (c.right && c.right.items) || (slide.after && slide.after.items) || [];
    ctx.svg = svg.buildVs(lItems, rItems, {
      ariaLabel: aria,
      leftLabel: (c.left && c.left.label) || (slide.before && slide.before.label) || 'Before',
      rightLabel: (c.right && c.right.label) || (slide.after && slide.after.label) || 'After',
      leftTitle: (c.left && (c.left.title || c.left.heading)) || (slide.before && slide.before.title) || '悪い例',
      rightTitle: (c.right && (c.right.title || c.right.heading)) || (slide.after && slide.after.title) || '良い例',
    });
  } else if (slideType === 'diagram-butterfly') {
    ctx.svg = svg.buildButterfly((c.left && c.left.items) || [], (c.right && c.right.items) || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-slope') {
    ctx.svg = svg.buildSlope((c.left && c.left.items) || [], (c.right && c.right.items) || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-mindmap') {
    ctx.svg = svg.buildMindmap(c.center || '中心', c.branches || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-concentric') {
    ctx.svg = svg.buildConcentric(c.rings || c.items || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-venn-2' || slideType === 'diagram-venn-3') {
    ctx.svg = svg.buildVenn(c.circles || c.items || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-matrix' || slideType === 'diagram-table-advanced') {
    ctx.svg = svg.buildMatrix(c.quadrants || c.items || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-funnel' || slideType === 'diagram-aidma') {
    ctx.svg = svg.buildFunnel(c.items || c.stages || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-chevron') {
    ctx.svg = svg.buildChevron(c.items || c.steps || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-snake' || slideType === 'diagram-wave-step' ||
             slideType === 'diagram-parallel' || slideType === 'diagram-point-cards' ||
             slideType === 'diagram-icon-grid' || slideType === 'diagram-persona' ||
             slideType === 'diagram-problem-solution' || slideType === 'diagram-value-prop' ||
             slideType === 'diagram-fabe-grid') {
    ctx.svg = svg.buildSnake(c.items || c.steps || c.cards || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-vertical-timeline' || slideType === 'diagram-fabe-timeline') {
    ctx.svg = svg.buildVerticalTimeline(c.events || c.items || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-gantt' || slideType === 'diagram-growth') {
    ctx.svg = svg.buildGantt(c.tasks || c.items || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-star') {
    ctx.svg = svg.buildStar(c.items || c.points || [], { ariaLabel: aria });
  } else if (slideType === 'diagram-person-network') {
    const branches = c.people || c.nodes || c.items || c.branches || [];
    ctx.svg = svg.buildMindmap(c.center || '関係者', normalizeTextList(branches), { ariaLabel: aria });
  } else if (slideType === 'chart-bar' || slideType === 'chart-bar-vertical' ||
             slideType === 'chart-bar-horizontal' || slideType === 'chart-bar-stacked') {
    ctx.svg = svg.buildBarChart(c.data || slide.data || [], { ariaLabel: aria });
  } else if (slideType === 'chart-pie' || slideType === 'chart-clock-pie') {
    ctx.svg = svg.buildPieChart(c.data || slide.data || [], { ariaLabel: aria });
  } else if (slideType === 'chart-line') {
    ctx.svg = svg.buildLineChart(c.data || slide.data || [], { ariaLabel: aria });
  } else if (slideType === 'chart-radar') {
    ctx.svg = svg.buildRadarChart(c.axes || [], c.series || [], { ariaLabel: aria });
  } else if (slideType === 'chart-scatter') {
    ctx.svg = svg.buildScatterChart(c.data || slide.data || [], { ariaLabel: aria });
  } else if (slideType === 'chart-gauge') {
    const v = typeof c.value === 'number' ? c.value : (typeof c.data === 'number' ? c.data : 0);
    ctx.svg = svg.buildGauge(v, { ariaLabel: aria });
  }

  // ---- D3 dispatch ----
  if (D3_COMPONENTS[slideType]) {
    const config = {
      title: ctx.title,
      data: c.data || slide.data || slide.items || [],
      axes: c.axes,
      series: c.series,
      options: c.options || slide.options || {},
    };
    ctx.configJson = JSON.stringify(config);
    ctx.d3Component = D3_COMPONENTS[slideType];
  }

  // ---- HTML helper context ----
  if (slideType === 'slide-icon-grid') {
    ctx.columns = c.columns || 3;
    ctx.items = (c.items || []).map((it) => ({ ...it, selected: !!it.selected }));
  }
  if (slideType === 'slide-compare') {
    ctx.left = {
      ...(c.left || {}),
      items: normalizeTextList((c.left && c.left.items) || []),
    };
    ctx.right = {
      ...(c.right || {}),
      items: normalizeTextList((c.right && c.right.items) || []),
    };
  }
  if (slideType === 'slide-grid') ctx.cols = c.cols || 3;
  if (slideType === 'grid' || slideType === 'icon-grid') ctx.cols = slide.cols || c.cols || 3;
  if (slideType === 'process') {
    ctx.steps = (slide.steps || slide.items || []).map((s, i) => ({
      num: i + 1,
      label: typeof s === 'string' ? s : s.label,
      desc: typeof s === 'object' ? s.desc : undefined,
    }));
  }
  if (slideType === 'slide-process') {
    ctx.steps = (c.steps || []).map((s) => ({
      number: s.number, label: s.label, desc: s.desc,
    }));
  }
  if (slideType === 'slide-table') {
    ctx.headers = (c.headers || []).map(normalizeCell);
    ctx.rows = (c.rows || []).map((r) => ({ cells: (Array.isArray(r) ? r : r.cells || []).map(normalizeCell) }));
  }
  if (slideType === 'table') {
    ctx.headers = slide.headers || (slide.rows && slide.rows[0] ? slide.rows[0] : []);
    ctx.rows = (slide.rows || []).map((r) => ({ cells: Array.isArray(r) ? r : r.cells || [] }));
  }

  return ctx;
}

function normalizeRenderedSlideHtml(html, slide, idx, v8ctx) {
  const slideType = normalizeSlideType(slide.slideType || '');
  let out = String(html || '').trim();
  out = out.replace(/^<section\b/i, '<div').replace(/<\/section>\s*$/i, '</div>');
  out = out.replace(/\sdata-slide-type="[^"]*"/i, '');
  if (!/\sdata-type="/i.test(out)) {
    out = out.replace(/^<div\b/i, `<div data-type="${escapeHtml(slideType)}"`);
  }
  if (!/\sdata-slide="/i.test(out)) {
    out = out.replace(/^<div\b/i, `<div data-slide="${idx + 1}"`);
  }
  out = out.replace(/\bdata-index="[^"]*"/i, `data-index="${idx}"`);
  out = out.replace(/var\((--[a-z0-9-]+),\s*#[0-9a-f]{3,8}\)/gi, 'var($1)');
  out = out.replace(/fill="#fff"/gi, 'fill="var(--bg-dark)"');
  // v7.5.1: テンプレが付与する `slide-slide-*` を `slide-*` に正規化し、
  // style-builder.cjs の `.slide-table` `.slide-grid` 等のセレクタと整合させる。
  out = out.replace(/\bslide-slide-([a-z0-9-]+)/gi, 'slide-$1');

  // v8: schemaVersion=8.0.0 のときだけ追加の data-* / inline-style を付与
  if (v8ctx && v8ctx.enabled) {
    const attrs = computeV8SlideAttrs(slide, v8ctx);
    if (attrs.length > 0) {
      out = out.replace(/^<div\b/i, `<div ${attrs.join(' ')}`);
    }
  }
  return out;
}

// v8: 色名 (enum値) → 既存 CSS 変数名へのマッピング
// SR-V8-COLOR: schema accentColorEnum の値を style-builder.cjs が出力する CSS 変数に解決
const V8_COLOR_VAR = {
  blue: '--accent-blue-vivid',
  pink: '--accent-pink-vivid',
  aqua: '--accent-aqua-vivid',
  violet: '--accent-violet-vivid',
  yellow: '--accent-yellow-vivid',
  green: '--accent-aqua-vivid',
  'wave-blue': '--accent-blue-vivid',
  'spring-violet': '--accent-violet-vivid',
  'sakura-pink': '--accent-pink-vivid',
  'wave-aqua': '--accent-aqua-vivid',
  'autumn-yellow': '--accent-yellow-vivid',
  'fuji-gray': '--fg',
  'accent-blue-vivid': '--accent-blue-vivid',
  'accent-pink-vivid': '--accent-pink-vivid',
  'accent-aqua-vivid': '--accent-aqua-vivid',
  'accent-violet-vivid': '--accent-violet-vivid',
  'accent-yellow-vivid': '--accent-yellow-vivid',
};
function v8ColorVar(name) {
  if (!name) return null;
  return V8_COLOR_VAR[name] || '--accent-blue-vivid';
}

// v8: section.theme と pageOverride を data-attr / inline style に変換
function computeV8SlideAttrs(slide, v8ctx) {
  const attrs = [];
  const styleParts = [];
  const sec = slide.section ? v8ctx.sectionMap.get(slide.section) : null;
  const sectionTheme = sec && sec.theme ? sec.theme : null;
  const po = slide.pageOverride || null;

  if (slide.section) attrs.push(`data-section="${escapeHtml(slide.section)}"`);

  const primary = (po && po.primaryAccent) || (sectionTheme && sectionTheme.primaryAccent) || (sec && sec.color);
  const secondary = (po && po.secondaryAccent) || (sectionTheme && sectionTheme.secondaryAccent);
  const bg = (po && po.background) || (sectionTheme && sectionTheme.background);
  const bgImage = po && po.backgroundImage;
  const pgColor = (po && po.pagination && po.pagination.color) || (sectionTheme && sectionTheme.paginationColor);

  if (primary) styleParts.push(`--accent-primary: var(${v8ColorVar(primary)})`);
  if (secondary) styleParts.push(`--accent-secondary: var(${v8ColorVar(secondary)})`);
  if (pgColor) styleParts.push(`--accent-pagination: var(${v8ColorVar(pgColor)})`);
  if (bg) attrs.push(`data-bg="${escapeHtml(bg)}"`);
  if (bgImage) styleParts.push(`--bg-image: url(${escapeHtml(bgImage)})`);

  if (po && po.pagination && po.pagination.show === false) {
    attrs.push('data-pg-hide="true"');
  }

  if (styleParts.length > 0) {
    attrs.push(`style="${styleParts.join('; ')}"`);
  }

  // cover/index/diagram があるスライドはマーカーを付与（CSS フックや E2E 検証用）
  if (slide.cover) attrs.push(`data-v8-cover="${escapeHtml(slide.cover.variant || 'minimal')}"`);
  if (slide.index) attrs.push(`data-v8-index="${escapeHtml(slide.index.style || 'list')}"`);
  if (slide.diagram) attrs.push(`data-v8-diagram="${escapeHtml(slide.diagram.variant || 'custom')}"`);

  return attrs;
}

// ---------- HTML scaffold ----------
function buildScaffold({ meta, slidesHtml, paginationHtml, theme }) {
  const title = escapeHtml(meta.title || 'Presentation');
  const lang = meta.lang || 'ja';
  const author = meta.author ? `<meta name="author" content="${escapeHtml(meta.author)}"/>` : '';
  const v8 = (meta.schemaVersion === '8.0.0');
  const headerHtml = v8 ? buildHeaderFragment(theme && theme.header, meta) : '';
  const footerHtml = v8 ? buildFooterFragment(theme && theme.footer, meta) : '';
  const sliderAttrs = [
    `class="slider"`,
    `data-pg-total="${meta.nSlides}"`,
  ];
  if (v8 && theme && theme.pagination && theme.pagination.style) {
    sliderAttrs.push(`data-pg-style="${escapeHtml(theme.pagination.style)}"`);
  }
  return `<!DOCTYPE html>
<html lang="${lang}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>${title}</title>
  ${author}
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;600;700;800;900&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"/>
  <link rel="stylesheet" href="styles.css"/>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js" defer></script>
</head>
<body>
  <div ${sliderAttrs.join(' ')}>
${headerHtml}    <div class="slide-area">
      <div class="slider__container">
${slidesHtml}
      </div>
    </div>
${paginationHtml}
${footerHtml}  </div>
  <script src="scripts.js" defer></script>
</body>
</html>
`;
}

function buildHeaderFragment(header, meta) {
  if (!header || !header.show) return '';
  const logo = header.logoIcon ? `<i class="fas ${escapeHtml(header.logoIcon)}" aria-hidden="true"></i>` : '';
  const event = header.showEventName && meta.event && meta.event.name ? `<span class="slider-header__event">${escapeHtml(meta.event.name)}</span>` : '';
  const sec = header.showSection ? `<span class="slider-header__section" data-pg-current-section></span>` : '';
  return `    <header class="slider-header" role="banner">
      <span class="slider-header__logo">${logo}</span>
      ${sec}
      ${event}
    </header>
`;
}

function buildFooterFragment(footer, meta) {
  if (!footer || !footer.show) return '';
  const left = footer.left ? `<span class="slider-footer__left">${escapeHtml(footer.left)}</span>` : '<span></span>';
  const center = footer.center ? `<span class="slider-footer__center">${escapeHtml(footer.center)}</span>` : '<span></span>';
  const right = footer.right ? `<span class="slider-footer__right" data-pg-page-counter="${escapeHtml(footer.right)}">${escapeHtml(footer.right)}</span>` : '<span></span>';
  return `    <footer class="slider-footer" role="contentinfo">
      ${left}
      ${center}
      ${right}
    </footer>
`;
}

// ---------- pagination インクルード ----------
function buildPaginationFragment(nSlides, sections) {
  const tpl = fs.readFileSync(path.join(ASSETS, 'pagination.html'), 'utf8');
  // strip the long header comment block for the body inclusion
  const stripped = tpl.replace(/<!--[\s\S]*?-->/g, '').trim();
  let sectionButtons = '';
  if (Array.isArray(sections) && sections.length > 0) {
    sectionButtons = sections
      .map(
        (s) => `<button type="button" class="pg-section-nav__item"
        data-section="${escapeHtml(s.id || '')}" data-first-slide="${Number.isInteger(s.firstSlide) ? s.firstSlide : Math.max(0, ((s.slides || [1])[0] || 1) - 1)}">
        <span class="pg-section-nav__dot" style="background: var(--accent-blue-vivid);"></span>
        <span class="pg-section-nav__label">${escapeHtml(s.label || s.title || s.id || '')}</span>
        <span class="pg-section-nav__bar"></span>
      </button>`
      )
      .join('\n      ');
  }
  return stripped
    .replace(/\{\{N_SLIDES\}\}/g, String(nSlides))
    .replace(/\{\{SECTIONS\}\}/g, sectionButtons);
}

// ---------- scripts.js (GSAP 安全パターン固定) ----------
function buildScriptsJs() {
  const paginationJs = fs.readFileSync(path.join(ASSETS, 'pagination.js'), 'utf8');
  return `/* scripts.js — render-slide.js 自動生成 (GSAP 安全パターン)
 * SR-6-01: scale 最小 0.8。0 / 0.5 禁止
 * SR-6-02: clearProps は content.children のみ
 * SR-6-03: updateSlide / leaveAnimation の onComplete 両方で適用
 * SR-6-08: prefers-reduced-motion 検出
 */
(function () {
  'use strict';
  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var D = prefersReducedMotion ? 0 : 1; // duration multiplier
  var S = prefersReducedMotion ? 0 : 1; // stagger multiplier

  var slides = Array.prototype.slice.call(document.querySelectorAll('.slider__item'));
  var current = 0;
  if (slides.length === 0) return;
  slides[0].classList.add('is-active');

  function getContent(slide) { return slide.querySelector('.slider__content'); }

  function enterAnimation(slide) {
    if (typeof gsap === 'undefined') return;
    var content = getContent(slide);
    if (!content) return;
    gsap.set(content.children, { opacity: 0, y: 30 });
    gsap.to(content.children, {
      opacity: 1, y: 0,
      duration: 0.5 * D,
      stagger: 0.06 * S,
      ease: 'power2.out',
      onComplete: function () {
        // SR-6-02 / SR-6-03
        gsap.set(content.children, { clearProps: 'all' });
      }
    });
  }

  function leaveAnimation(slide, cb) {
    if (typeof gsap === 'undefined') { if (cb) cb(); return; }
    var content = getContent(slide);
    if (!content) { if (cb) cb(); return; }
    gsap.to(content.children, {
      opacity: 0, y: -20,
      duration: 0.18 * D,
      stagger: 0.03 * S,
      ease: 'power3.inOut',
      onComplete: function () {
        gsap.set(content.children, { clearProps: 'all' });
        if (cb) cb();
      }
    });
  }

  function updateSlide(next) {
    if (next < 0 || next >= slides.length || next === current) return;
    var prev = slides[current];
    var nextEl = slides[next];
    leaveAnimation(prev, function () {
      prev.classList.remove('is-active');
      nextEl.classList.add('is-active');
      enterAnimation(nextEl);
      current = next;
      window.dispatchEvent(new CustomEvent('slidechange', { detail: { index: current, total: slides.length } }));
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') updateSlide(current + 1);
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') updateSlide(current - 1);
    else if (e.key === 'Home') updateSlide(0);
    else if (e.key === 'End') updateSlide(slides.length - 1);
  });

  // Pagination wiring
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-pg-component], .pg-controls__btn, .pg-dots__item, .pg-section-nav__item');
    if (!t) return;
    if (t.classList.contains('pg-controls__btn--prev')) updateSlide(current - 1);
    else if (t.classList.contains('pg-controls__btn--next')) updateSlide(current + 1);
    else if (t.classList.contains('pg-dots__item')) {
      var i = parseInt(t.getAttribute('data-index') || '0', 10);
      updateSlide(i);
    } else if (t.classList.contains('pg-section-nav__item')) {
      var f = parseInt(t.getAttribute('data-first-slide') || '0', 10);
      updateSlide(f);
    }
  });

  // initial enter
  if (typeof gsap !== 'undefined') enterAnimation(slides[0]);
  window.__renderSlide = { goTo: updateSlide, total: slides.length, get current(){ return current; } };
})();

/* ===== pagination.js (asset 結合) ===== */
${paginationJs}

/* ===== d3-bootstrap.js (asset 結合・SR-12-05) ===== */
${renderD3BootstrapJs()}
`;
}

// ---------- main ----------
function main() {
  const args = parseArgs(process.argv);
  if (!args._[0] || !args.out) {
    console.error('Usage: render-slide.js <structure.json> --out <dir>');
    process.exit(1);
  }
  const inputPath = path.resolve(args._[0]);
  const outDir = path.resolve(args.out);
  const data = JSON.parse(fs.readFileSync(inputPath, 'utf8'));

  // schema validation
  if (!args.noValidate && fs.existsSync(SCHEMA_PATH)) {
    const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, 'utf8'));
    const errs = validateSchema(data, schema);
    if (errs.length > 0) {
      console.error('Schema validation failed:\n  ' + errs.join('\n  '));
      process.exit(2);
    }
  }

  fs.mkdirSync(outDir, { recursive: true });

  const meta = data.meta || {};
  const slides = data.slides || [];
  meta.nSlides = slides.length;
  if (data.meta && data.meta.event) meta.event = data.meta.event;

  // v8 ctx: schemaVersion=8.0.0 のみ各種拡張を有効化
  const v8ctx = {
    enabled: meta.schemaVersion === '8.0.0',
    sectionMap: new Map(),
  };
  (data.sections || []).forEach(sec => v8ctx.sectionMap.set(sec.id, sec));

  // generate slide HTML fragments
  const slidesHtml = slides
    .map((s, i) => {
      try {
        const tpl = loadTemplate(s.slideType);
        const ctx = enrichSlideContext(s, i);
        if (v8ctx.enabled) {
          if (s.cover) ctx.cover = s.cover;
          if (s.index) ctx.index = s.index;
          if (s.diagram) ctx.diagram = s.diagram;
          if (s.pageOverride) ctx.pageOverride = s.pageOverride;
        }
        return normalizeRenderedSlideHtml(render(tpl, ctx, {}), s, i, v8ctx);
      } catch (err) {
        console.warn(`[render-slide] slide ${i} (${s.slideType}) failed:`, err.message);
        return normalizeRenderedSlideHtml(`<section class="slider__item slide-error" data-index="${i}"><div class="slider__content"><h2>${escapeHtml(s.slideType || '')}</h2><p class="text-note">[render error: ${escapeHtml(err.message)}]</p></div></section>`, s, i, v8ctx);
      }
    })
    .join('\n');

  const paginationHtml = buildPaginationFragment(slides.length, data.sections || meta.sections || []);
  const html = buildScaffold({ meta, slidesHtml, paginationHtml, theme: data.theme });

  const css = buildStyles({
    paginationCssPath: path.join(ASSETS, 'pagination.css'),
  });

  const js = buildScriptsJs();

  fs.writeFileSync(path.join(outDir, 'index.html'), html);
  fs.writeFileSync(path.join(outDir, 'styles.css'), css);
  fs.writeFileSync(path.join(outDir, 'scripts.js'), js);
  fs.writeFileSync(path.join(outDir, 'structure.json'), JSON.stringify(data, null, 2));
  fs.writeFileSync(path.join(outDir, 'structure.md'), buildStructureMd(data));

  console.log(`[render-slide] OK
  in:  ${inputPath}
  out: ${outDir}
  slides: ${slides.length}
  files: index.html (${fs.statSync(path.join(outDir, 'index.html')).size}B), styles.css, scripts.js, structure.json, structure.md`);
}

if (require.main === module) main();

module.exports = { main, validateSchema, enrichSlideContext, normalizeRenderedSlideHtml, buildStructureMd };
