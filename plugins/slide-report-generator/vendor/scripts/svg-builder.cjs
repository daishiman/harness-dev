/**
 * svg-builder.js — 決定論 SVG 生成
 *
 * SR-1-02: viewBox は 960×540 系（または図解形状用の正方形）
 * SR-3-05: SVG <text> 最小 13px
 * SR-2-08: fill/stroke は CSS 変数 + フォールバック
 * SR-3-06: SVG <text> 内に Font Awesome unicode 禁止
 *
 * v7.5.0:
 *   - buildMindmap: ラベルを外円の外側にリーダー線で配置、文字切れ解消
 *   - buildCycle: viewBox を横長化、左に description 用キャプション領域、
 *                 各ノード半径を文字数に応じて拡大
 *   - buildVs: 真の Before/After 2カラム比較ビルダーを新規追加
 *              （diagram-vs / diagram-comparison-1 用）
 */
'use strict';

const MIN_FONT = 14; // SR-3-05 実用最小
const VAR_BLUE = 'var(--wave-blue, #7E9CD8)';
const VAR_PINK = 'var(--sakura-pink, #D27E99)';
const VAR_AQUA = 'var(--wave-aqua, #7FB4CA)';
const VAR_YELLOW = 'var(--autumn-yellow, #DCA561)';
const VAR_VIOLET = 'var(--spring-violet, #957FB8)';
const COLOR_PALETTE = [VAR_BLUE, VAR_AQUA, VAR_PINK, VAR_YELLOW, VAR_VIOLET];

/** 入力配列の正規化: null/undefined を除去し、最低1件のプレースホルダを保証 */
function normItems(items, minCount) {
  const arr = Array.isArray(items) ? items.filter((x) => x != null) : [];
  while (arr.length < (minCount || 0)) arr.push({ label: '' });
  return arr;
}
/** ラベル抽出（string|object 両対応） */
function getLabel(it) {
  if (it == null) return '';
  if (typeof it === 'string') return it;
  return it.label || it.text || it.name || '';
}

function escapeXml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** 矢印マーカー定義 (SR-5-05) */
function defs() {
  const colors = { blue: VAR_BLUE, pink: VAR_PINK, aqua: VAR_AQUA, yellow: VAR_YELLOW, violet: VAR_VIOLET };
  const markers = Object.entries(colors)
    .map(
      ([n, c]) => `<marker id="arrow-${n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="${c}"/></marker>`
    )
    .join('\n    ');
  return `<defs>\n    ${markers}\n  </defs>`;
}

/** テキスト wrapping for SVG (SR-5-03..04) */
function svgText({ x, y, text, fontSize = MIN_FONT, anchor = 'middle', fill = 'var(--fg, #43436c)', weight = 600, maxChars = 0 }) {
  if (!text) return '';
  let lines = [String(text)];
  if (maxChars > 0 && text.length > maxChars) {
    lines = [];
    let s = String(text);
    while (s.length > 0) {
      lines.push(s.slice(0, maxChars));
      s = s.slice(maxChars);
    }
  }
  const dy = Math.round(fontSize * 1.5);
  const tspans = lines.map((ln, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : dy}">${escapeXml(ln)}</tspan>`).join('');
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" fill="${fill}" font-size="${fontSize}" font-weight="${weight}" font-family="'Noto Sans JP', sans-serif">${tspans}</text>`;
}

/**
 * 横フロー: 要素 3-7
 */
function buildHorizontalFlow(items, opts = {}) {
  // v7.5.0: H を 540 に拡大、ステップカード下に desc キャプションを描画
  const n = Math.max(3, Math.min(7, items.length));
  const W = 1080, H = 540;
  const margin = 40;
  const gap = 20;
  const cardW = Math.floor((W - margin * 2 - gap * (n - 1)) / n);
  const cardH = 130;
  const cy = 130;
  const fontSize = Math.max(MIN_FONT, Math.min(20, Math.floor(cardW / 11)));
  const maxChars = Math.max(4, Math.floor((cardW / fontSize) * 0.75));
  const itemList = items.slice(0, n);
  const hasDesc = itemList.some((it) => it && typeof it === 'object' && (it.desc || it.description));
  const cards = itemList.map((it, i) => {
    const x = margin + i * (cardW + gap);
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const isObj = it && typeof it === 'object';
    const label = typeof it === 'string' ? it : (isObj ? (it.label || it.text || '') : '');
    const num = isObj && it.number ? it.number : (i + 1);
    return `<g>
      <rect x="${x}" y="${cy - cardH / 2}" width="${cardW}" height="${cardH}" rx="14" ry="14" fill="${color}" opacity="0.92"/>
      <circle cx="${x + 28}" cy="${cy - cardH / 2 + 28}" r="18" fill="#fff" opacity="0.95"/>
      ${svgText({ x: x + 28, y: cy - cardH / 2 + 34, text: String(num), fontSize: 18, fill: color, weight: 800 })}
      ${svgText({ x: x + cardW / 2, y: cy + 8, text: label, fontSize, fill: '#fff', weight: 700, maxChars })}
    </g>`;
  });
  // 説明キャプション
  const captions = hasDesc ? itemList.map((it, i) => {
    const x = margin + i * (cardW + gap);
    const desc = (it && typeof it === 'object') ? (it.desc || it.description || '') : '';
    if (!desc) return '';
    const maxC = Math.max(8, Math.floor(cardW / 14));
    // 最大3行
    const lines = [];
    let s = String(desc);
    for (let li = 0; li < 4 && s.length > 0; li++) {
      lines.push(s.slice(0, maxC));
      s = s.slice(maxC);
    }
    if (s.length > 0 && lines.length) lines[lines.length - 1] = lines[lines.length - 1].slice(0, -1) + '…';
    const tspans = lines.map((ln, li) => `<tspan x="${x + cardW / 2}" dy="${li === 0 ? 0 : 22}">${escapeXml(ln)}</tspan>`).join('');
    return `<text x="${x + cardW / 2}" y="240" text-anchor="middle" fill="var(--fg-muted, #54546d)" font-size="15" font-weight="500" font-family="'Noto Sans JP', sans-serif">${tspans}</text>`;
  }).join('\n  ') : '';
  const arrows = [];
  for (let i = 0; i < n - 1; i++) {
    const ax = margin + (i + 1) * cardW + i * gap;
    const ax2 = ax + gap;
    arrows.push(`<line x1="${ax}" y1="${cy}" x2="${ax2}" y2="${cy}" stroke="${VAR_BLUE}" stroke-width="3" marker-end="url(#arrow-blue)"/>`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '横フロー図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${arrows.join('\n  ')}
  ${cards.join('\n  ')}
  ${captions}
</svg>`;
}

/**
 * サイクル: 3-8 要素を円周配置
 */
function buildCycle(items, opts = {}) {
  // v7.5.0: viewBox を横長化(1200x600)、右にサイクル、左にキャプションカード
  const n = Math.max(3, Math.min(8, items.length));
  const W = 1200, H = 600;
  const cx = W - 320, cy = H / 2;
  const R = 220;
  const rNode = 78;
  const fontSize = Math.max(MIN_FONT, Math.min(18, Math.floor(rNode / 3.5)));
  const maxChars = Math.max(5, Math.floor((rNode * 2) / fontSize * 0.7));
  const nodes = [];
  const arrows = [];
  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    const x = cx + R * Math.cos(a);
    const y = cy + R * Math.sin(a);
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const it = items[i] || {};
    const label = getLabel(it);
    nodes.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rNode}" fill="${color}" opacity="0.92"/>
      ${svgText({ x, y: y + 5, text: label, fontSize, fill: '#fff', weight: 700, maxChars })}`);
    const a2 = -Math.PI / 2 + (2 * Math.PI * ((i + 1) % n)) / n;
    const sx = cx + (R - rNode - 6) * Math.cos(a + 0.22);
    const sy = cy + (R - rNode - 6) * Math.sin(a + 0.22);
    const ex = cx + (R - rNode - 6) * Math.cos(a2 - 0.22);
    const ey = cy + (R - rNode - 6) * Math.sin(a2 - 0.22);
    arrows.push(`<path d="M${sx.toFixed(1)},${sy.toFixed(1)} A ${R} ${R} 0 0 1 ${ex.toFixed(1)},${ey.toFixed(1)}" fill="none" stroke="${VAR_BLUE}" stroke-width="3" marker-end="url(#arrow-blue)"/>`);
  }
  // 左キャプション（subtext / description / caption から拾う）
  const caption = opts.subtext || opts.description || opts.caption || '';
  const heading = opts.headline || opts.lead || '';
  const captionX = 40, captionW = 540;
  let captionBlock = '';
  if (heading || caption) {
    const headFs = 26;
    const bodyFs = 18;
    // 簡易折返し
    const wrap = (text, max) => {
      if (!text) return [];
      const out = []; let s = String(text);
      while (s.length > max) { out.push(s.slice(0, max)); s = s.slice(max); }
      if (s) out.push(s);
      return out;
    };
    const hLines = wrap(heading, 18);
    const bLines = wrap(caption, 26);
    const lineH = 30;
    let y = 100;
    const headTspans = hLines.map((ln, i) => `<tspan x="${captionX}" dy="${i === 0 ? 0 : headFs * 1.4}">${escapeXml(ln)}</tspan>`).join('');
    const bodyStartY = y + (hLines.length ? hLines.length * (headFs * 1.4) + 18 : 0);
    const bodyTspans = bLines.map((ln, i) => `<tspan x="${captionX}" dy="${i === 0 ? 0 : bodyFs * 1.5}">${escapeXml(ln)}</tspan>`).join('');
    // 動的カード高さ: 内容に合わせて短く
    const headBlockH = hLines.length ? hLines.length * (headFs * 1.4) + 18 : 0;
    const bodyBlockH = bLines.length ? (bLines.length - 1) * (bodyFs * 1.5) + bodyFs : 0;
    const cardTop = 60;
    const cardPadTop = 40; // y(=100) - cardTop
    const cardPadBottom = 28;
    const cardH = cardPadTop + headBlockH + bodyBlockH + cardPadBottom;
    captionBlock = `<g>
      <rect x="${captionX - 16}" y="${cardTop}" width="${captionW}" height="${cardH}" rx="14" fill="#FFFFFF" stroke="${VAR_BLUE}" stroke-width="1.5"/>
      <rect x="${captionX - 16}" y="${cardTop}" width="6" height="${cardH}" fill="${VAR_BLUE}"/>
      ${heading ? `<text x="${captionX}" y="${y}" fill="#43436c" font-size="${headFs}" font-weight="800" font-family="'Noto Sans JP', sans-serif">${headTspans}</text>` : ''}
      ${caption ? `<text x="${captionX}" y="${bodyStartY}" fill="#54546d" font-size="${bodyFs}" font-weight="500" font-family="'Noto Sans JP', sans-serif">${bodyTspans}</text>` : ''}
    </g>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}" class="cycle-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'サイクル図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${captionBlock}
  ${arrows.join('\n  ')}
  ${nodes.join('\n  ')}
</svg>`;
}

/**
 * ピラミッド: 3-5 層
 */
function buildPyramid(items, opts = {}) {
  const n = Math.max(3, Math.min(5, items.length));
  const W = 960, H = 540;
  const top = 40, bottom = H - 40;
  const layerH = (bottom - top) / n;
  const widthAt = (i) => 200 + ((i + 1) / n) * 600;
  const layers = items.slice(0, n).map((it, i) => {
    const y = top + i * layerH;
    const w = widthAt(i);
    const x = (W - w) / 2;
    const color = COLOR_PALETTE[(n - 1 - i) % COLOR_PALETTE.length];
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    const fontSize = Math.max(MIN_FONT, Math.min(22, Math.floor(layerH / 3)));
    return `<g>
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${(layerH - 6).toFixed(1)}" rx="6" fill="${color}" opacity="0.92"/>
      ${svgText({ x: W / 2, y: y + layerH / 2 + 6, text: label, fontSize, fill: '#fff', weight: 700 })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" class="pyramid-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ピラミッド図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${layers.join('\n  ')}
</svg>`;
}

/**
 * 階層: 3-4 階層（縦ツリー風）
 */
function buildHierarchy(items, opts = {}) {
  const n = Math.max(3, Math.min(4, items.length));
  const W = 960, H = 540;
  const layerH = H / n;
  const layers = items.slice(0, n).map((it, i) => {
    const y = i * layerH + 20;
    const w = 800 - i * 80;
    const x = (W - w) / 2;
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    const fontSize = Math.max(MIN_FONT, 20);
    return `<g>
      <rect x="${x}" y="${y}" width="${w}" height="${layerH - 30}" rx="10" fill="${color}" opacity="0.9"/>
      ${svgText({ x: W / 2, y: y + (layerH - 30) / 2 + 8, text: label, fontSize, fill: '#fff', weight: 700 })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '階層図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${layers.join('\n  ')}
</svg>`;
}

/** 棒グラフ */
function buildBarChart(data, opts = {}) {
  const W = 960, H = 480;
  const padL = 80, padB = 60, padT = 30, padR = 30;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const max = Math.max(...data.map((d) => d.value)) || 1;
  const bw = innerW / data.length * 0.6;
  const gap = innerW / data.length;
  const bars = data.map((d, i) => {
    const h = (d.value / max) * innerH;
    const x = padL + i * gap + (gap - bw) / 2;
    const y = padT + innerH - h;
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    return `<g>
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="4" fill="${color}"/>
      ${svgText({ x: x + bw / 2, y: y - 8, text: String(d.value), fontSize: MIN_FONT, fill: 'var(--fg, #43436c)', weight: 700 })}
      ${svgText({ x: x + bw / 2, y: padT + innerH + 24, text: d.label, fontSize: MIN_FONT, fill: 'var(--fg, #43436c)' })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '棒グラフ')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  <line x1="${padL}" y1="${padT + innerH}" x2="${padL + innerW}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  ${bars.join('\n  ')}
</svg>`;
}

/** 円グラフ */
function buildPieChart(data, opts = {}) {
  const SIZE = 540;
  const cx = SIZE / 2, cy = SIZE / 2, r = 200;
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  let acc = -Math.PI / 2;
  const slices = data.map((d, i) => {
    const a1 = acc;
    const a2 = acc + (d.value / total) * Math.PI * 2;
    acc = a2;
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
    const large = a2 - a1 > Math.PI ? 1 : 0;
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const am = (a1 + a2) / 2;
    const lx = cx + (r + 30) * Math.cos(am);
    const ly = cy + (r + 30) * Math.sin(am);
    const pct = Math.round((d.value / total) * 100);
    return `<g>
      <path d="M${cx},${cy} L${x1.toFixed(1)},${y1.toFixed(1)} A${r},${r} 0 ${large} 1 ${x2.toFixed(1)},${y2.toFixed(1)} z" fill="${color}" opacity="0.92"/>
      ${svgText({ x: lx, y: ly + 5, text: `${d.label} ${pct}%`, fontSize: MIN_FONT, fill: 'var(--fg, #43436c)', weight: 700 })}
    </g>`;
  });
  return `<svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${escapeXml(opts.ariaLabel || '円グラフ')}" xmlns="http://www.w3.org/2000/svg">
  ${slices.join('\n  ')}
</svg>`;
}

/* ============================================================
 * 追加ビルダー（v7.1: 73 slideType 拡張用）
 * すべて決定論・vw/CSS変数準拠・SR-3-05 (min 13px) 厳守。
 * ============================================================ */

/** 縦フロー（ステップ縦並び） */
function buildVerticalFlow(items, opts = {}) {
  const n = Math.max(2, Math.min(8, items.length));
  const W = 720, H = Math.max(360, n * 90);
  const cardH = 64, gap = 18, marginX = 60, marginY = 30;
  const cardW = W - marginX * 2;
  const cards = items.slice(0, n).map((it, i) => {
    const y = marginY + i * (cardH + gap);
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    return `<g><rect x="${marginX}" y="${y}" width="${cardW}" height="${cardH}" rx="12" fill="${c}" opacity="0.92"/>
      ${svgText({ x: W / 2, y: y + cardH / 2 + 5, text: label, fontSize: 18, fill: '#fff', weight: 700 })}</g>`;
  });
  const arrows = [];
  for (let i = 0; i < n - 1; i++) {
    const y1 = marginY + (i + 1) * cardH + i * gap;
    const y2 = y1 + gap;
    arrows.push(`<line x1="${W / 2}" y1="${y1}" x2="${W / 2}" y2="${y2}" stroke="${VAR_BLUE}" stroke-width="3" marker-end="url(#arrow-blue)"/>`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '縦フロー図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${arrows.join('\n  ')}
  ${cards.join('\n  ')}
</svg>`;
}

/** 同心円（concentric） */
function buildConcentric(rings, opts = {}) {
  const n = Math.max(2, Math.min(5, rings.length));
  const SIZE = 540, cx = SIZE / 2, cy = SIZE / 2;
  const maxR = 240;
  const items = rings.slice(0, n).map((r, i) => {
    const radius = maxR * (1 - i / n);
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const label = typeof r === 'string' ? r : r.label || r.text || '';
    const ly = cy - radius + 22;
    return `<circle cx="${cx}" cy="${cy}" r="${radius.toFixed(1)}" fill="${c}" opacity="${(0.25 + 0.15 * i).toFixed(2)}" stroke="${c}" stroke-width="2"/>
      ${svgText({ x: cx, y: ly, text: label, fontSize: 16, fill: 'var(--fg, #43436c)', weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${escapeXml(opts.ariaLabel || '同心円図')}" xmlns="http://www.w3.org/2000/svg">
  ${items.join('\n  ')}
</svg>`;
}

/** Venn図 (2 or 3 circles) */
function buildVenn(circles, opts = {}) {
  const n = Math.min(3, Math.max(2, circles.length));
  const SIZE = 540, cx = SIZE / 2, cy = SIZE / 2, r = 130;
  let positions;
  if (n === 2) positions = [{ x: cx - 80, y: cy }, { x: cx + 80, y: cy }];
  else positions = [{ x: cx, y: cy - 70 }, { x: cx - 80, y: cy + 60 }, { x: cx + 80, y: cy + 60 }];
  const parts = positions.slice(0, n).map((p, i) => {
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const it = circles[i];
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    return `<circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${c}" opacity="0.45"/>
      ${svgText({ x: p.x, y: p.y - r - 8, text: label, fontSize: 16, fill: 'var(--fg, #43436c)', weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ベン図')}" xmlns="http://www.w3.org/2000/svg">
  ${parts.join('\n  ')}
</svg>`;
}

/** マトリクス 2x2 */
function buildMatrix(quadrants, opts = {}) {
  const W = 720, H = 540;
  const cells = [];
  const cw = W / 2, ch = H / 2;
  const labels = quadrants.slice(0, 4);
  for (let i = 0; i < 4; i++) {
    const x = (i % 2) * cw, y = Math.floor(i / 2) * ch;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const it = labels[i] || '';
    const label = typeof it === 'string' ? it : it.label || it.text || '';
    cells.push(`<rect x="${x + 4}" y="${y + 4}" width="${cw - 8}" height="${ch - 8}" rx="10" fill="${c}" opacity="0.85"/>
      ${svgText({ x: x + cw / 2, y: y + ch / 2 + 6, text: label, fontSize: 18, fill: '#fff', weight: 700 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'マトリクス図')}" xmlns="http://www.w3.org/2000/svg">
  ${cells.join('\n  ')}
</svg>`;
}

/** ファネル */
function buildFunnel(items, opts = {}) {
  const n = Math.max(3, Math.min(6, items.length));
  const W = 720, H = 540;
  const top = 30, bot = H - 30;
  const lh = (bot - top) / n;
  const wTop = 600, wBot = 200;
  const layers = [];
  for (let i = 0; i < n; i++) {
    const t = i / n, t2 = (i + 1) / n;
    const w1 = wTop - (wTop - wBot) * t;
    const w2 = wTop - (wTop - wBot) * t2;
    const y1 = top + i * lh, y2 = y1 + lh - 4;
    const x1 = (W - w1) / 2, x2 = (W - w2) / 2;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const it = items[i];
    const label = getLabel(it);
    layers.push(`<polygon points="${x1.toFixed(1)},${y1.toFixed(1)} ${(x1 + w1).toFixed(1)},${y1.toFixed(1)} ${(x2 + w2).toFixed(1)},${y2.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}" fill="${c}" opacity="0.9"/>
      ${svgText({ x: W / 2, y: y1 + lh / 2 + 6, text: label, fontSize: 16, fill: '#fff', weight: 700 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ファネル図')}" xmlns="http://www.w3.org/2000/svg">
  ${layers.join('\n  ')}
</svg>`;
}

/** シェブロン (右向き矢印連結) */
function buildChevron(items, opts = {}) {
  const n = Math.max(3, Math.min(7, items.length));
  const W = 960, H = 220, M = 20;
  const segW = (W - M * 2) / n;
  const arrow = 30;
  const segs = [];
  for (let i = 0; i < n; i++) {
    const x = M + i * segW;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const it = items[i];
    const label = getLabel(it);
    const x2 = x + segW - 4;
    const points = [
      `${x},${30}`,
      `${x2 - arrow},${30}`,
      `${x2},${H / 2}`,
      `${x2 - arrow},${H - 30}`,
      `${x},${H - 30}`,
      `${x + arrow},${H / 2}`,
    ].join(' ');
    segs.push(`<polygon points="${points}" fill="${c}" opacity="0.92"/>
      ${svgText({ x: x + segW / 2, y: H / 2 + 5, text: label, fontSize: 16, fill: '#fff', weight: 700 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'シェブロン図')}" xmlns="http://www.w3.org/2000/svg">
  ${segs.join('\n  ')}
</svg>`;
}

/** スネーク（折り返しフロー） */
function buildSnake(items, opts = {}) {
  items = normItems(items, 3);
  const n = Math.max(3, Math.min(8, items.length));
  const W = 960, H = 360;
  const cols = Math.min(4, Math.ceil(n / 2));
  const rows = Math.ceil(n / cols);
  const cw = (W - 60) / cols, ch = (H - 40) / rows;
  const boxW = cw - 30, boxH = ch - 20;
  const boxes = [];
  for (let i = 0; i < n; i++) {
    const r = Math.floor(i / cols);
    const c0 = i % cols;
    const col = r % 2 === 0 ? c0 : cols - 1 - c0;
    const x = 30 + col * cw + 15;
    const y = 20 + r * ch + 10;
    const color = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const it = items[i];
    const label = getLabel(it);
    boxes.push(`<rect x="${x}" y="${y}" width="${boxW}" height="${boxH}" rx="10" fill="${color}" opacity="0.9"/>
      ${svgText({ x: x + boxW / 2, y: y + boxH / 2 + 5, text: label, fontSize: 16, fill: '#fff', weight: 700 })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'スネークフロー図')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${boxes.join('\n  ')}
</svg>`;
}

/** スロープグラフ (左右2点比較) */
function buildSlope(left, right, opts = {}) {
  const W = 720, H = 480, padX = 100, padY = 50;
  const items = (left || []).map((l, i) => ({
    label: l.label || (typeof l === 'string' ? l : ''),
    leftV: typeof l === 'object' ? l.value : l,
    rightV: right && right[i] ? (typeof right[i] === 'object' ? right[i].value : right[i]) : 0,
  }));
  const all = items.flatMap((d) => [Number(d.leftV) || 0, Number(d.rightV) || 0]);
  const max = Math.max(...all, 1);
  const lines = items.map((d, i) => {
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const y1 = padY + (1 - (Number(d.leftV) || 0) / max) * (H - padY * 2);
    const y2 = padY + (1 - (Number(d.rightV) || 0) / max) * (H - padY * 2);
    return `<line x1="${padX}" y1="${y1.toFixed(1)}" x2="${W - padX}" y2="${y2.toFixed(1)}" stroke="${c}" stroke-width="3"/>
      <circle cx="${padX}" cy="${y1.toFixed(1)}" r="6" fill="${c}"/>
      <circle cx="${W - padX}" cy="${y2.toFixed(1)}" r="6" fill="${c}"/>
      ${svgText({ x: padX - 10, y: y1 + 5, text: d.label, fontSize: 14, anchor: 'end', fill: 'var(--fg, #43436c)' })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'スロープグラフ')}" xmlns="http://www.w3.org/2000/svg">
  ${lines.join('\n  ')}
</svg>`;
}

/** バタフライチャート (左右ミラー水平棒) */
function buildButterfly(left, right, opts = {}) {
  const items = (left || []).map((l, i) => ({
    label: l.label || (typeof l === 'string' ? l : ''),
    l: Number(typeof l === 'object' ? l.value : l) || 0,
    r: Number((right && right[i]) ? (typeof right[i] === 'object' ? right[i].value : right[i]) : 0) || 0,
  }));
  const W = 720, H = Math.max(300, items.length * 60 + 40);
  const cx = W / 2, max = Math.max(...items.flatMap((d) => [d.l, d.r]), 1);
  const bh = 28, gap = 28;
  const bars = items.map((d, i) => {
    const y = 30 + i * (bh + gap);
    const lw = (d.l / max) * (cx - 80);
    const rw = (d.r / max) * (cx - 80);
    return `<rect x="${cx - lw}" y="${y}" width="${lw}" height="${bh}" rx="4" fill="${VAR_BLUE}" opacity="0.9"/>
      <rect x="${cx}" y="${y}" width="${rw}" height="${bh}" rx="4" fill="${VAR_PINK}" opacity="0.9"/>
      ${svgText({ x: cx, y: y - 6, text: d.label, fontSize: 14, fill: 'var(--fg, #43436c)', weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'バタフライチャート')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${cx}" y1="20" x2="${cx}" y2="${H - 20}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  ${bars.join('\n  ')}
</svg>`;
}

/** マインドマップ（中心ノード + 放射枝）
 *  v7.5.0: 横長 viewBox、ラベルは外円の外側にリーダー線で配置し、文字切れを解消
 */
function buildMindmap(center, branches, opts = {}) {
  const W = 1100, H = 600, cx = W / 2, cy = H / 2;
  const branchList = (branches || []).filter(Boolean);
  const n = Math.min(8, Math.max(3, branchList.length));
  const R = 200;       // 中心 → ノード中心の半径
  const rNode = 38;    // ノード円半径（ラベルは外置）
  const rCenter = 78;  // 中心円半径
  const parts = [];
  // 中心円
  parts.push(`<circle cx="${cx}" cy="${cy}" r="${rCenter}" fill="${VAR_BLUE}"/>
    ${svgText({ x: cx, y: cy + 6, text: center || '', fontSize: 18, fill: '#fff', weight: 800 })}`);
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    const cosA = Math.cos(a), sinA = Math.sin(a);
    const x = cx + R * cosA, y = cy + R * sinA;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const it = branchList[i];
    const label = typeof it === 'string' ? it : (it && (it.label || it.text || it.name)) || '';
    // 中心からノードへの線（中心円・ノード円ぶんを差し引く）
    const lx1 = cx + rCenter * cosA, ly1 = cy + rCenter * sinA;
    const lx2 = x - rNode * cosA, ly2 = y - rNode * sinA;
    // ラベル位置（ノードの外側）
    const labelDist = rNode + 14;
    const lx = x + labelDist * cosA, ly = y + labelDist * sinA;
    // テキストアンカー: 右半分は start、左半分は end、上下は middle
    let anchor = 'middle';
    if (cosA > 0.3) anchor = 'start';
    else if (cosA < -0.3) anchor = 'end';
    const textY = ly + 5 + (sinA > 0.5 ? 8 : sinA < -0.5 ? -2 : 0);
    parts.push(`<line x1="${lx1.toFixed(1)}" y1="${ly1.toFixed(1)}" x2="${lx2.toFixed(1)}" y2="${ly2.toFixed(1)}" stroke="${c}" stroke-width="2.5"/>
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rNode}" fill="${c}" opacity="0.95"/>
      ${svgText({ x: lx, y: textY, text: label, fontSize: 16, fill: 'var(--fg, #43436c)', weight: 700, anchor })}`);
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'マインドマップ')}" xmlns="http://www.w3.org/2000/svg">
  ${parts.join('\n  ')}
</svg>`;
}

/** v7.5.0: Before/After 2カラム比較ビルダー
 *  diagram-vs / diagram-comparison-1 用。左=Before(赤系)、右=After(緑/青系)。
 *  入力: leftItems, rightItems, opts: { leftLabel, rightLabel, leftTitle, rightTitle }
 */
function buildVs(leftItems, rightItems, opts = {}) {
  const colW = 540;
  const gap = 60;
  const leftX = 40;
  const rightX = leftX + colW + gap;
  const headerH = 70;
  const itemH = 56;
  const padX = 24;
  const itemGap = 12;
  const topY = 60;
  const bottomPad = 28;
  const lItems = (leftItems || []).slice(0, 6);
  const rItems = (rightItems || []).slice(0, 6);
  const leftLabel = opts.leftLabel || 'Before';
  const rightLabel = opts.rightLabel || 'After';
  const leftTitle = opts.leftTitle || opts.leftHeading || '悪い例';
  const rightTitle = opts.rightTitle || opts.rightHeading || '良い例';
  const leftColor = VAR_PINK;
  const rightColor = VAR_AQUA;
  // 動的カード高さ: ヘッダー + 上部余白22 + 項目数*itemH + (項目数-1)*itemGap + 下部余白
  const maxItems = Math.max(lItems.length, rItems.length, 1);
  const cardH = headerH + 22 + maxItems * itemH + Math.max(0, maxItems - 1) * itemGap + bottomPad;
  const W = 1200;
  const H = topY + cardH + 40;

  function column(x, items, color, label, title, isLeft) {
    const blocks = [];
    // カード背景: 純白 + 薄ボーダー（var() を使わずハードコード）
    blocks.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${cardH}" rx="16" fill="#FFFFFF" stroke="#DCD7BA" stroke-width="1.5"/>`);
    // ヘッダー（カラー）
    blocks.push(`<rect x="${x}" y="${topY}" width="${colW}" height="${headerH}" rx="16" fill="${color}" opacity="0.92"/>`);
    blocks.push(`<rect x="${x}" y="${topY + headerH - 16}" width="${colW}" height="16" fill="${color}" opacity="0.92"/>`);
    // バッジ
    blocks.push(`<rect x="${x + 20}" y="${topY + 14}" width="86" height="32" rx="16" fill="#FFFFFF" opacity="0.95"/>`);
    blocks.push(svgText({ x: x + 63, y: topY + 36, text: label, fontSize: 16, fill: color, weight: 800 }));
    // タイトル
    blocks.push(svgText({ x: x + 124, y: topY + 36, text: title, fontSize: 22, fill: '#FFFFFF', weight: 800, anchor: 'start' }));
    // 項目
    items.forEach((it, i) => {
      const y = topY + headerH + 22 + i * (itemH + itemGap);
      const label = typeof it === 'string' ? it : (it && (it.label || it.text)) || '';
      blocks.push(`<rect x="${x + padX}" y="${y}" width="${colW - padX * 2}" height="${itemH}" rx="10" fill="#F8F7F0" stroke="#DCD7BA" stroke-width="1"/>`);
      blocks.push(`<rect x="${x + padX}" y="${y}" width="6" height="${itemH}" fill="${color}"/>`);
      // アイコン円
      blocks.push(`<circle cx="${x + padX + 32}" cy="${y + itemH / 2}" r="14" fill="${color}" opacity="0.18"/>`);
      blocks.push(svgText({ x: x + padX + 32, y: y + itemH / 2 + 5, text: isLeft ? '×' : '○', fontSize: 18, fill: color, weight: 800 }));
      // ラベル（折返しなし簡易、長文は ... で省略）
      const maxChars = 22;
      const text = label.length > maxChars ? label.slice(0, maxChars) + '…' : label;
      blocks.push(svgText({ x: x + padX + 56, y: y + itemH / 2 + 6, text, fontSize: 17, fill: '#43436c', weight: 600, anchor: 'start' }));
    });
    return blocks.join('\n  ');
  }

  // 中央 VS マーク
  const vsX = leftX + colW + gap / 2;
  const vsCy = topY + cardH / 2;
  const vsBlock = `<circle cx="${vsX}" cy="${vsCy}" r="34" fill="#FFFFFF" stroke="${VAR_VIOLET}" stroke-width="3"/>
    ${svgText({ x: vsX, y: vsCy + 8, text: 'VS', fontSize: 22, fill: VAR_VIOLET, weight: 900 })}`;

  return `<svg viewBox="0 0 ${W} ${H}" class="vs-svg" role="img" aria-label="${escapeXml(opts.ariaLabel || 'Before/After 比較')}" xmlns="http://www.w3.org/2000/svg">
  ${defs()}
  ${column(leftX, lItems, leftColor, leftLabel, leftTitle, true)}
  ${column(rightX, rItems, rightColor, rightLabel, rightTitle, false)}
  ${vsBlock}
</svg>`;
}

/** 折れ線グラフ */
function buildLineChart(data, opts = {}) {
  const W = 960, H = 480, padL = 60, padR = 30, padT = 30, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const max = Math.max(...data.map((d) => d.value), 1);
  const stepX = data.length > 1 ? innerW / (data.length - 1) : innerW;
  const pts = data.map((d, i) => `${(padL + i * stepX).toFixed(1)},${(padT + innerH - (d.value / max) * innerH).toFixed(1)}`);
  const dots = data.map((d, i) => {
    const x = padL + i * stepX;
    const y = padT + innerH - (d.value / max) * innerH;
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" fill="${VAR_BLUE}"/>
      ${svgText({ x, y: padT + innerH + 22, text: d.label, fontSize: MIN_FONT, fill: 'var(--fg, #43436c)' })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '折れ線グラフ')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${padL}" y1="${padT + innerH}" x2="${padL + innerW}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  <polyline points="${pts.join(' ')}" fill="none" stroke="${VAR_BLUE}" stroke-width="3"/>
  ${dots.join('\n  ')}
</svg>`;
}

/** レーダー（多角形グラフ） */
function buildRadarChart(axes, series, opts = {}) {
  const SIZE = 540, cx = SIZE / 2, cy = SIZE / 2;
  const R = 200;
  const n = axes.length;
  const polyAxes = axes.map((a, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / n;
    const x = cx + R * Math.cos(ang), y = cy + R * Math.sin(ang);
    const lx = cx + (R + 30) * Math.cos(ang), ly = cy + (R + 30) * Math.sin(ang);
    return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${VAR_AQUA}" stroke-width="1"/>
      ${svgText({ x: lx, y: ly + 5, text: a, fontSize: 14, fill: 'var(--fg, #43436c)', weight: 700 })}`;
  }).join('\n  ');
  const polys = (series || []).map((s, si) => {
    const c = COLOR_PALETTE[si % COLOR_PALETTE.length];
    const pts = (s.values || []).map((v, i) => {
      const ang = -Math.PI / 2 + (2 * Math.PI * i) / n;
      const r = (Math.max(0, Math.min(100, v)) / 100) * R;
      return `${(cx + r * Math.cos(ang)).toFixed(1)},${(cy + r * Math.sin(ang)).toFixed(1)}`;
    }).join(' ');
    return `<polygon points="${pts}" fill="${c}" opacity="0.4" stroke="${c}" stroke-width="2"/>`;
  }).join('\n  ');
  return `<svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'レーダーチャート')}" xmlns="http://www.w3.org/2000/svg">
  ${polyAxes}
  ${polys}
</svg>`;
}

/** ゲージ（半円） */
function buildGauge(value, opts = {}) {
  const W = 540, H = 320, cx = W / 2, cy = H - 30, r = 200;
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const ang = Math.PI * (1 - v / 100);
  const x = cx + r * Math.cos(ang), y = cy - r * Math.sin(ang);
  const large = v > 50 ? 1 : 0;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ゲージ')}" xmlns="http://www.w3.org/2000/svg">
  <path d="M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}" fill="none" stroke="${VAR_AQUA}" stroke-width="24" opacity="0.3"/>
  <path d="M${cx - r},${cy} A${r},${r} 0 ${large} 1 ${x.toFixed(1)},${y.toFixed(1)}" fill="none" stroke="${VAR_BLUE}" stroke-width="24"/>
  ${svgText({ x: cx, y: cy - 30, text: `${v}%`, fontSize: 36, fill: 'var(--fg, #43436c)', weight: 800 })}
</svg>`;
}

/** スキャッター */
function buildScatterChart(data, opts = {}) {
  const W = 720, H = 480, padL = 60, padR = 30, padT = 30, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const xs = data.map((d) => d.x || 0), ys = data.map((d) => d.y || 0);
  const xMax = Math.max(...xs, 1), yMax = Math.max(...ys, 1);
  const dots = data.map((d, i) => {
    const x = padL + ((d.x || 0) / xMax) * innerW;
    const y = padT + innerH - ((d.y || 0) / yMax) * innerH;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="${c}" opacity="0.85"/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '散布図')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${padL}" y1="${padT + innerH}" x2="${padL + innerW}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + innerH}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  ${dots.join('\n  ')}
</svg>`;
}

/** 単純垂直タイムライン (1列) */
function buildVerticalTimeline(events, opts = {}) {
  const n = Math.max(2, Math.min(8, events.length));
  const W = 540, H = Math.max(360, n * 90);
  const cx = 100;
  const items = events.slice(0, n).map((e, i) => {
    const y = 40 + i * 80;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const date = e.date || '';
    const label = e.label || (typeof e === 'string' ? e : '');
    return `<circle cx="${cx}" cy="${y}" r="14" fill="${c}"/>
      ${svgText({ x: cx + 30, y: y + 5, text: `${date}  ${label}`, fontSize: 16, anchor: 'start', fill: 'var(--fg, #43436c)', weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || '縦タイムライン')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${cx}" y1="20" x2="${cx}" y2="${H - 20}" stroke="${VAR_BLUE}" stroke-width="3"/>
  ${items.join('\n  ')}
</svg>`;
}

/** ガント（バー期間） */
function buildGantt(tasks, opts = {}) {
  const n = Math.max(2, Math.min(8, tasks.length));
  const W = 960, H = Math.max(300, n * 50 + 60), padL = 200, padR = 30, padT = 40;
  const innerW = W - padL - padR;
  const allEnds = tasks.map((t) => Number(t.end) || 0);
  const max = Math.max(...allEnds, 1);
  const bars = tasks.slice(0, n).map((t, i) => {
    const y = padT + i * 50;
    const x = padL + (Number(t.start) || 0) / max * innerW;
    const w = ((Number(t.end) || 0) - (Number(t.start) || 0)) / max * innerW;
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    return `<rect x="${x.toFixed(1)}" y="${y}" width="${Math.max(20, w).toFixed(1)}" height="32" rx="6" fill="${c}" opacity="0.92"/>
      ${svgText({ x: padL - 10, y: y + 22, text: t.label || '', fontSize: 14, anchor: 'end', fill: 'var(--fg, #43436c)', weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'ガントチャート')}" xmlns="http://www.w3.org/2000/svg">
  <line x1="${padL}" y1="${padT - 10}" x2="${padL}" y2="${H - 10}" stroke="${VAR_BLUE}" stroke-width="1.5"/>
  ${bars.join('\n  ')}
</svg>`;
}

/** スター（5角形ノード強調） */
function buildStar(items, opts = {}) {
  const SIZE = 540, cx = SIZE / 2, cy = SIZE / 2;
  const n = Math.max(3, Math.min(7, items.length));
  const R = 200;
  const nodes = items.slice(0, n).map((it, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    const c = COLOR_PALETTE[i % COLOR_PALETTE.length];
    const label = typeof it === 'string' ? it : it.label || '';
    return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${c}" stroke-width="2"/>
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="50" fill="${c}" opacity="0.9"/>
      ${svgText({ x, y: y + 5, text: label, fontSize: 14, fill: '#fff', weight: 700 })}`;
  });
  return `<svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${escapeXml(opts.ariaLabel || 'スター図')}" xmlns="http://www.w3.org/2000/svg">
  <circle cx="${cx}" cy="${cy}" r="40" fill="${VAR_YELLOW}"/>
  ${nodes.join('\n  ')}
</svg>`;
}

/** 価値スタック（積層四角） */
function buildValueStack(items, opts = {}) {
  return buildPyramid(items.slice().reverse(), opts);
}

/** AIDMA / FABE 縦カラム */
function buildVerticalColumns(items, opts = {}) {
  return buildVerticalFlow(items, opts);
}

/** クロックパイ（時計風円グラフ） */
function buildClockPie(data, opts = {}) {
  return buildPieChart(data, opts);
}

module.exports = {
  buildHorizontalFlow,
  buildVerticalFlow,
  buildCycle,
  buildPyramid,
  buildHierarchy,
  buildBarChart,
  buildPieChart,
  buildLineChart,
  buildRadarChart,
  buildGauge,
  buildScatterChart,
  buildConcentric,
  buildVenn,
  buildMatrix,
  buildFunnel,
  buildChevron,
  buildSnake,
  buildSlope,
  buildButterfly,
  buildMindmap,
  buildVs,
  buildVerticalTimeline,
  buildGantt,
  buildStar,
  buildValueStack,
  buildVerticalColumns,
  buildClockPie,
  defs,
};
