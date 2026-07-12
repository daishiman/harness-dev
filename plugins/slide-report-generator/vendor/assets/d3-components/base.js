/**
 * D3.js Base Components for Presentation Slide Generator
 *
 * Kanagawa Theme統合、共通ユーティリティ、アニメーション定義
 * CDN: https://cdn.jsdelivr.net/npm/d3@7
 */

// ============================================================
// Kanagawa Theme Colors（CSS変数と同期）
// ============================================================
const KanagawaColors = {
  // Light Theme (default)
  light: {
    bg: '#FFFFFF',
    fg: '#2D2D2D',
    fgDim: '#717171',
    accent1: '#7E9CD8',   // wave-blue
    accent2: '#E46876',   // sakura-pink
    accent3: '#98BB6C',   // spring-green
    accent4: '#DCA561',   // autumn-yellow
    accent5: '#7AA89F',   // wave-aqua
    accent6: '#957FB8',   // oni-violet
    border: '#E0E0E0',
    surface: '#F5F5F5'
  },
  // Dark Theme
  dark: {
    bg: '#1F1F28',
    fg: '#DCD7BA',
    fgDim: '#727169',
    accent1: '#7E9CD8',
    accent2: '#E46876',
    accent3: '#98BB6C',
    accent4: '#DCA561',
    accent5: '#7AA89F',
    accent6: '#957FB8',
    border: '#363646',
    surface: '#2A2A37'
  }
};

// アクセントカラー配列（グラフ用）
const accentPalette = [
  '#7E9CD8', '#E46876', '#98BB6C', '#DCA561', '#7AA89F', '#957FB8',
  '#D27E99', '#C0A36E', '#6A9589', '#9CABCA'
];

// ============================================================
// D3 Base Utilities
// ============================================================
const D3Base = {
  /**
   * テーマ取得
   */
  getTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return isDark ? KanagawaColors.dark : KanagawaColors.light;
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
      tooltip = d3.select('body')
        .append('div')
        .attr('class', 'd3-tooltip')
        .style('position', 'absolute')
        .style('padding', '8px 12px')
        .style('background', 'rgba(0,0,0,0.8)')
        .style('color', '#fff')
        .style('border-radius', '4px')
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
    const {
      scale = 1.05,
      shadow = true,
      cursor = 'pointer'
    } = options;

    selection
      .style('cursor', cursor)
      .style('transition', 'transform 0.2s, filter 0.2s')
      .on('mouseenter', function() {
        d3.select(this)
          .style('transform', `scale(${scale})`)
          .style('filter', shadow ? 'drop-shadow(0 4px 8px rgba(0,0,0,0.15))' : null);
      })
      .on('mouseleave', function() {
        d3.select(this)
          .style('transform', 'scale(1)')
          .style('filter', null);
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
        .attr('fill', item.color || accentPalette[i % accentPalette.length])
        .attr('rx', 2);

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
  stroke: var(--fg-dim, #717171);
  stroke-width: 1;
}

.d3-chart .axis text {
  fill: var(--fg-dim, #717171);
  font-size: 12px;
}

.d3-chart .grid line {
  stroke: var(--border, #E0E0E0);
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
