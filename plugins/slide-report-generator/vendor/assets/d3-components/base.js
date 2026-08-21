/**
 * D3.js Base Components for Presentation Slide Generator
 *
 * 配色はこのファイルに持たない。CSS カスタムプロパティを実行時に解決して使う。
 * 色の正本は vendor/assets/style-genome-*.json の palette と、
 * それを写した CSS 変数（--paper / --ink / --hairline / --tint-*）。
 * CDN: https://cdn.jsdelivr.net/npm/d3@7
 */

// ============================================================
// Color Tokens（CSS 変数名のみ。色値は持たない）
// ============================================================

// 各役割について、先に見つかった CSS 変数を採用する解決順。
// 変数名は vendor/scripts/style-builder.cjs が発行するものに合わせる
// (--paper / --ink / --fg-muted / --hairline / --tone-1..3)。末尾は旧名の保険。
const TOKEN_CHAINS = {
  bg:      ['--paper', '--bg'],
  fg:      ['--ink', '--fg'],
  fgDim:   ['--fg-muted', '--fg-dim'],
  border:  ['--hairline', '--border'],
  surface: ['--paper', '--surface', '--bg'],
  // アクセントは色相ではなく「地の反転」と単一色相の濃度3段で作る。
  accent1: ['--ink', '--fg'],
  accent2: ['--tone-3', '--ink', '--fg'],
  accent3: ['--tone-2', '--ink', '--fg'],
  accent4: ['--tone-1', '--hairline', '--border'],
  accent5: ['--tone-3', '--ink', '--fg'],
  accent6: ['--tone-2', '--ink', '--fg']
};

// 系列色の並び（濃い順）。色数ではなく濃度段で系列を分ける。
const ACCENT_RAMP = ['accent1', 'accent2', 'accent3', 'accent4'];

function readCssVar(name) {
  if (typeof document === 'undefined' || !document.documentElement) return '';
  try {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  } catch (e) {
    return '';
  }
}

// CSS 変数が解決できない環境では var() 式をそのまま返す（色値を埋め込まない）。
function resolveToken(key) {
  const chain = TOKEN_CHAINS[key] || [];
  for (let i = 0; i < chain.length; i++) {
    const value = readCssVar(chain[i]);
    if (value) return value;
  }
  return chain.length ? 'var(' + chain[0] + ')' : 'currentColor';
}

function buildTheme() {
  const theme = {};
  Object.keys(TOKEN_CHAINS).forEach(key => { theme[key] = resolveToken(key); });
  return theme;
}

// 既存 API 互換。値は参照時に CSS 変数から解決する。
const KanagawaColors = {
  get light() { return buildTheme(); },
  get dark() { return buildTheme(); }
};

// アクセントカラー配列（グラフ用）。参照時に解決する読み取り専用ビュー。
const accentPalette = new Proxy(ACCENT_RAMP.slice(), {
  get(target, prop, receiver) {
    if (typeof prop === 'string' && /^\d+$/.test(prop)) {
      const idx = Number(prop) % ACCENT_RAMP.length;
      return resolveToken(ACCENT_RAMP[idx]);
    }
    return Reflect.get(target, prop, receiver);
  }
});

// 色文字列の相対輝度。解決できない場合は null。
function relativeLuminance(color) {
  if (typeof color !== 'string') return null;
  const value = color.trim();
  let r, g, b;
  const hex = value.match(/^#([0-9a-f]{3,8})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3 || h.length === 4) h = h.slice(0, 3).split('').map(c => c + c).join('');
    if (h.length < 6) return null;
    r = parseInt(h.slice(0, 2), 16);
    g = parseInt(h.slice(2, 4), 16);
    b = parseInt(h.slice(4, 6), 16);
  } else {
    const rgb = value.match(/^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i);
    if (!rgb) return null;
    r = parseFloat(rgb[1]);
    g = parseFloat(rgb[2]);
    b = parseFloat(rgb[3]);
  }
  const lin = c => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

// ============================================================
// D3 Base Utilities
// ============================================================
const D3Base = {
  /**
   * テーマ取得
   */
  getTheme() {
    return buildTheme();
  },

  /**
   * 単一トークンの解決（bg / fg / fgDim / border / surface / accent1-6）
   */
  token(key) {
    return resolveToken(key);
  },

  /**
   * 塗りの上に置く文字色。地が暗ければ紙色、明るければインク色を返す。
   * @param {string} fill - 下地の塗り
   */
  onFill(fill) {
    const theme = this.getTheme();
    const luminance = relativeLuminance(fill);
    if (luminance === null) return theme.bg;
    return luminance < 0.5 ? theme.bg : theme.fg;
  },

  /**
   * SVGコンテナ作成
   * @param {string} selector - セレクタ
   * @param {Object} options - { width, height, margin }
   */
  createSVG(selector, options = {}) {
    const {
      width = 800,
      height = 500,
      margin = { top: 40, right: 40, bottom: 40, left: 40 }
    } = options;

    const theme = this.getTheme();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('font-family', '"Noto Sans JP", "Hiragino Kaku Gothic ProN", sans-serif');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    return {
      svg,
      g,
      width: width - margin.left - margin.right,
      height: height - margin.top - margin.bottom,
      theme
    };
  },

  /**
   * ツールチップ作成
   */
  createTooltip() {
    let tooltip = d3.select('body').select('.d3-tooltip');
    if (tooltip.empty()) {
      const theme = this.getTheme();
      tooltip = d3.select('body')
        .append('div')
        .attr('class', 'd3-tooltip')
        .style('position', 'absolute')
        .style('padding', '8px 12px')
        .style('background', theme.fg)
        .style('color', theme.bg)
        .style('border-radius', '0')
        .style('font-size', '14px')
        .style('pointer-events', 'none')
        .style('opacity', 0)
        .style('z-index', 9999)
        .style('transition', 'opacity 0.2s');
    }
    return tooltip;
  },

  /**
   * 共通トランジション設定
   */
  defaultTransition(selection) {
    return selection.transition()
      .duration(750)
      .ease(d3.easeCubicInOut);
  },

  /**
   * エントリーアニメーション
   */
  animateEntry(selection, type = 'fadeIn') {
    const animations = {
      fadeIn: () => selection
        .style('opacity', 0)
        .transition()
        .duration(600)
        .style('opacity', 1),

      scaleIn: () => selection
        .attr('transform', 'scale(0)')
        .transition()
        .duration(600)
        .ease(d3.easeBackOut)
        .attr('transform', 'scale(1)'),

      slideUp: () => selection
        .attr('transform', 'translate(0, 50)')
        .style('opacity', 0)
        .transition()
        .duration(600)
        .attr('transform', 'translate(0, 0)')
        .style('opacity', 1),

      drawPath: () => {
        const totalLength = selection.node().getTotalLength();
        return selection
          .attr('stroke-dasharray', totalLength)
          .attr('stroke-dashoffset', totalLength)
          .transition()
          .duration(1000)
          .ease(d3.easeLinear)
          .attr('stroke-dashoffset', 0);
      }
    };

    return animations[type] ? animations[type]() : animations.fadeIn();
  },

  /**
   * ホバーエフェクト追加
   */
  addHoverEffect(selection, options = {}) {
    // 影は使わない。強調軸は拡大の1つだけ。
    const {
      scale = 1.05,
      cursor = 'pointer'
    } = options;

    selection
      .style('cursor', cursor)
      .style('transition', 'transform 0.2s')
      .on('mouseenter', function() {
        d3.select(this).style('transform', `scale(${scale})`);
      })
      .on('mouseleave', function() {
        d3.select(this).style('transform', 'scale(1)');
      });
  },

  /**
   * レスポンシブ対応
   */
  makeResponsive(svg) {
    svg.attr('preserveAspectRatio', 'xMidYMid meet')
       .style('max-width', '100%')
       .style('height', 'auto');
  },

  /**
   * 凡例作成
   */
  createLegend(g, items, options = {}) {
    const {
      x = 0,
      y = 0,
      direction = 'horizontal',
      itemWidth = 120,
      itemHeight = 24
    } = options;

    const theme = this.getTheme();
    const legend = g.append('g')
      .attr('class', 'legend')
      .attr('transform', `translate(${x}, ${y})`);

    items.forEach((item, i) => {
      const isHorizontal = direction === 'horizontal';
      const itemG = legend.append('g')
        .attr('transform', isHorizontal
          ? `translate(${i * itemWidth}, 0)`
          : `translate(0, ${i * itemHeight})`);

      itemG.append('rect')
        .attr('width', 16)
        .attr('height', 16)
        .attr('fill', item.color || accentPalette[i % accentPalette.length]);

      itemG.append('text')
        .attr('x', 22)
        .attr('y', 12)
        .attr('fill', theme.fg)
        .style('font-size', '14px')
        .text(item.label);
    });

    return legend;
  },

  /**
   * 軸ラベル追加
   */
  addAxisLabels(g, options = {}) {
    const { xLabel, yLabel, width, height, theme } = options;

    if (xLabel) {
      g.append('text')
        .attr('class', 'x-axis-label')
        .attr('x', width / 2)
        .attr('y', height + 35)
        .attr('text-anchor', 'middle')
        .attr('fill', theme.fgDim)
        .style('font-size', '14px')
        .text(xLabel);
    }

    if (yLabel) {
      g.append('text')
        .attr('class', 'y-axis-label')
        .attr('x', -height / 2)
        .attr('y', -35)
        .attr('transform', 'rotate(-90)')
        .attr('text-anchor', 'middle')
        .attr('fill', theme.fgDim)
        .style('font-size', '14px')
        .text(yLabel);
    }
  },

  /**
   * 数値フォーマット
   */
  formatNumber(value, format = 'auto') {
    if (format === 'auto') {
      if (Math.abs(value) >= 1e9) return d3.format('.2s')(value);
      if (Math.abs(value) >= 1e6) return d3.format('.2s')(value);
      if (Math.abs(value) >= 1e3) return d3.format(',.0f')(value);
      if (value % 1 !== 0) return d3.format('.1f')(value);
      return d3.format(',')(value);
    }
    return d3.format(format)(value);
  },

  /**
   * パーセントフォーマット
   */
  formatPercent(value) {
    return d3.format('.1%')(value);
  }
};

// ============================================================
// CSS Styles (インライン用)
// ============================================================
const D3Styles = `
.d3-tooltip {
  font-family: "Noto Sans JP", sans-serif;
  max-width: 200px;
  line-height: 1.4;
}

.d3-chart text {
  user-select: none;
}

.d3-chart .axis path,
.d3-chart .axis line {
  stroke: var(--fg-muted, var(--fg-dim));
  stroke-width: 1;
}

.d3-chart .axis text {
  fill: var(--fg-muted, var(--fg-dim));
  font-size: 12px;
}

.d3-chart .grid line {
  stroke: var(--hairline, var(--border));
  stroke-dasharray: 3,3;
}

.d3-chart .grid path {
  stroke-width: 0;
}

@keyframes d3-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes d3-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
`;

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { KanagawaColors, accentPalette, D3Base, D3Styles };
}
