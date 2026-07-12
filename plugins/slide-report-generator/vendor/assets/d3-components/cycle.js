/**
 * D3.js Cycle Components
 *
 * 循環系図解: サイクル、PDCA、三角サイクル、回転フロー
 * 回転アニメーション、ホバーエフェクト対応
 */

const D3Cycle = {
  /**
   * 基本サイクル図（4要素）
   * @param {string} selector - セレクタ
   * @param {Array} data - [{ label, description, icon? }]
   * @param {Object} options - 設定オプション
   */
  createCycle(selector, data, options = {}) {
    const {
      width = 600,
      height = 500,
      radius = 160,
      nodeRadius = 60,
      animate = true,
      showArrows = true,
      centerLabel = ''
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart cycle-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // 中心ラベル
    if (centerLabel) {
      g.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .attr('fill', theme.fgDim)
        .style('font-size', '16px')
        .text(centerLabel);
    }

    // ノード配置角度計算
    const angleStep = (2 * Math.PI) / data.length;
    const startAngle = -Math.PI / 2; // 12時方向から開始

    // 接続矢印（パスアニメーション）
    if (showArrows) {
      const arrowGroup = g.append('g').attr('class', 'arrows');

      data.forEach((_, i) => {
        const angle1 = startAngle + i * angleStep;
        const angle2 = startAngle + ((i + 1) % data.length) * angleStep;

        const x1 = Math.cos(angle1) * radius;
        const y1 = Math.sin(angle1) * radius;
        const x2 = Math.cos(angle2) * radius;
        const y2 = Math.sin(angle2) * radius;

        // 曲線パス
        const midAngle = (angle1 + angle2) / 2;
        const curveRadius = radius * 1.2;
        const mx = Math.cos(midAngle) * curveRadius;
        const my = Math.sin(midAngle) * curveRadius;

        const path = arrowGroup.append('path')
          .attr('d', `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`)
          .attr('fill', 'none')
          .attr('stroke', theme.border)
          .attr('stroke-width', 2)
          .attr('marker-end', 'url(#arrowhead)');

        if (animate) {
          D3Base.animateEntry(path, 'drawPath');
        }
      });

      // 矢印マーカー定義
      svg.append('defs')
        .append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 0 10 10')
        .attr('refX', 8)
        .attr('refY', 5)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M 0 0 L 10 5 L 0 10 z')
        .attr('fill', theme.border);
    }

    // ノード
    const nodes = g.selectAll('.node')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', (d, i) => {
        const angle = startAngle + i * angleStep;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        return `translate(${x}, ${y})`;
      });

    // ノード円
    nodes.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 3)
      .style('cursor', 'pointer');

    // ノードラベル
    nodes.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', '#fff')
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .text(d => d.label);

    // ホバー＆ツールチップ
    nodes.on('mouseenter', function(event, d) {
      d3.select(this).select('circle')
        .transition()
        .duration(200)
        .attr('r', nodeRadius * 1.1);

      if (d.description) {
        tooltip
          .style('opacity', 1)
          .html(d.description)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      }
    })
    .on('mouseleave', function() {
      d3.select(this).select('circle')
        .transition()
        .duration(200)
        .attr('r', nodeRadius);

      tooltip.style('opacity', 0);
    });

    // エントリーアニメーション
    if (animate) {
      nodes.style('opacity', 0)
        .transition()
        .duration(600)
        .delay((d, i) => i * 150)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * PDCAサイクル（4象限スタイル）
   * @param {string} selector
   * @param {Object} data - { plan, do, check, act } それぞれ { items: [], highlight? }
   * @param {Object} options
   */
  createPDCA(selector, data, options = {}) {
    const {
      width = 700,
      height = 600,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart pdca-chart');

    const centerX = width / 2;
    const centerY = height / 2;
    const quadrantSize = Math.min(width, height) * 0.4;

    // PDCAデータ配列化
    const pdcaData = [
      { key: 'plan', label: 'Plan', color: accentPalette[0], ...data.plan, x: -1, y: -1 },
      { key: 'do', label: 'Do', color: accentPalette[1], ...data.do, x: 1, y: -1 },
      { key: 'check', label: 'Check', color: accentPalette[2], ...data.check, x: 1, y: 1 },
      { key: 'act', label: 'Act', color: accentPalette[3], ...data.act, x: -1, y: 1 }
    ];

    const g = svg.append('g')
      .attr('transform', `translate(${centerX}, ${centerY})`);

    // 中心の回転矢印
    const arrowPath = g.append('path')
      .attr('d', `
        M -30 -60 A 60 60 0 1 1 60 -30
        L 50 -40 L 60 -30 L 50 -20
      `)
      .attr('fill', 'none')
      .attr('stroke', theme.fgDim)
      .attr('stroke-width', 2)
      .attr('stroke-linecap', 'round');

    if (animate) {
      D3Base.animateEntry(arrowPath, 'drawPath');
    }

    // 各象限
    const quadrants = g.selectAll('.quadrant')
      .data(pdcaData)
      .enter()
      .append('g')
      .attr('class', 'quadrant')
      .attr('transform', d => `translate(${d.x * quadrantSize / 2}, ${d.y * quadrantSize / 2})`);

    // 象限背景
    quadrants.append('rect')
      .attr('x', -quadrantSize / 2 + 10)
      .attr('y', -quadrantSize / 2 + 10)
      .attr('width', quadrantSize - 20)
      .attr('height', quadrantSize - 20)
      .attr('rx', 12)
      .attr('fill', d => d.color)
      .attr('opacity', 0.15);

    // 象限ヘッダー
    quadrants.append('text')
      .attr('x', 0)
      .attr('y', -quadrantSize / 2 + 40)
      .attr('text-anchor', 'middle')
      .attr('fill', d => d.color)
      .style('font-size', '24px')
      .style('font-weight', 'bold')
      .text(d => d.label);

    // 象限アイテム
    quadrants.each(function(d) {
      const items = d.items || [];
      const itemGroup = d3.select(this);

      items.forEach((item, i) => {
        itemGroup.append('text')
          .attr('x', 0)
          .attr('y', -quadrantSize / 2 + 70 + i * 24)
          .attr('text-anchor', 'middle')
          .attr('fill', theme.fg)
          .style('font-size', '14px')
          .text(`• ${item}`);
      });
    });

    // ホバーエフェクト
    quadrants.on('mouseenter', function(event, d) {
      d3.select(this).select('rect')
        .transition()
        .duration(200)
        .attr('opacity', 0.25);
    })
    .on('mouseleave', function() {
      d3.select(this).select('rect')
        .transition()
        .duration(200)
        .attr('opacity', 0.15);
    });

    // エントリーアニメーション
    if (animate) {
      quadrants.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => i * 200)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * 三角サイクル（3要素循環）
   * @param {string} selector
   * @param {Array} data - [{ label, description }] 3要素
   * @param {Object} options
   */
  createTriangleCycle(selector, data, options = {}) {
    const {
      width = 600,
      height = 520,
      radius = 180,
      nodeRadius = 55,
      animate = true,
      centerLabel = ''
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart triangle-cycle-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2 + 20})`);

    // 三角形の頂点位置
    const positions = [
      { x: 0, y: -radius },                           // 上
      { x: radius * Math.cos(Math.PI / 6), y: radius * Math.sin(Math.PI / 6) },   // 右下
      { x: -radius * Math.cos(Math.PI / 6), y: radius * Math.sin(Math.PI / 6) }   // 左下
    ];

    // 中心ラベル
    if (centerLabel) {
      g.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .attr('fill', theme.fgDim)
        .style('font-size', '14px')
        .text(centerLabel);
    }

    // 接続線（三角形の辺）
    const lineGroup = g.append('g').attr('class', 'connections');

    for (let i = 0; i < 3; i++) {
      const p1 = positions[i];
      const p2 = positions[(i + 1) % 3];

      // 矢印付き曲線
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const perpX = -dy * 0.15;
      const perpY = dx * 0.15;

      const path = lineGroup.append('path')
        .attr('d', `M ${p1.x} ${p1.y} Q ${midX + perpX} ${midY + perpY} ${p2.x} ${p2.y}`)
        .attr('fill', 'none')
        .attr('stroke', accentPalette[i])
        .attr('stroke-width', 3)
        .attr('stroke-linecap', 'round')
        .attr('marker-end', `url(#tri-arrow-${i})`);

      if (animate) {
        D3Base.animateEntry(path, 'drawPath');
      }

      // 矢印マーカー
      svg.append('defs')
        .append('marker')
        .attr('id', `tri-arrow-${i}`)
        .attr('viewBox', '0 0 10 10')
        .attr('refX', 8)
        .attr('refY', 5)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M 0 0 L 10 5 L 0 10 z')
        .attr('fill', accentPalette[i]);
    }

    // ノード
    const nodes = g.selectAll('.node')
      .data(data.slice(0, 3))
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', (d, i) => `translate(${positions[i].x}, ${positions[i].y})`);

    nodes.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', (d, i) => accentPalette[i])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 3);

    nodes.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', '#fff')
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .each(function(d) {
        const text = d3.select(this);
        const words = d.label.split(/\s+/);
        if (words.length > 1) {
          words.forEach((word, i) => {
            text.append('tspan')
              .attr('x', 0)
              .attr('dy', i === 0 ? '-0.3em' : '1.2em')
              .text(word);
          });
        } else {
          text.text(d.label);
        }
      });

    // ホバー＆ツールチップ
    nodes.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', nodeRadius * 1.15);

        if (d.description) {
          tooltip
            .style('opacity', 1)
            .html(d.description)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
        }
      })
      .on('mouseleave', function() {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', nodeRadius);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      nodes.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => 300 + i * 200)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * 回転フロー（N要素サイクル）
   * @param {string} selector
   * @param {Array} data - [{ label, icon?, description? }]
   * @param {Object} options
   */
  createRotatingFlow(selector, data, options = {}) {
    const {
      width = 650,
      height = 550,
      outerRadius = 200,
      innerRadius = 80,
      animate = true,
      autoRotate = false
    } = options;

    const theme = D3Base.getTheme();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart rotating-flow-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    const n = data.length;
    const angleStep = (2 * Math.PI) / n;

    // 外側の接続弧
    const arcGenerator = d3.arc()
      .innerRadius(outerRadius - 30)
      .outerRadius(outerRadius - 10)
      .cornerRadius(5);

    data.forEach((d, i) => {
      const startAngle = i * angleStep - Math.PI / 2 + 0.1;
      const endAngle = (i + 1) * angleStep - Math.PI / 2 - 0.1;

      const arc = g.append('path')
        .attr('d', arcGenerator({ startAngle, endAngle }))
        .attr('fill', accentPalette[i % accentPalette.length])
        .attr('opacity', 0.6);

      if (animate) {
        arc.attr('opacity', 0)
          .transition()
          .duration(400)
          .delay(i * 100)
          .attr('opacity', 0.6);
      }
    });

    // 中心円
    g.append('circle')
      .attr('r', innerRadius)
      .attr('fill', theme.surface)
      .attr('stroke', theme.border)
      .attr('stroke-width', 2);

    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', theme.fg)
      .style('font-size', '16px')
      .style('font-weight', 'bold')
      .text(`${n}ステップ`);

    // ノード
    const nodeGroup = g.append('g').attr('class', 'nodes');

    const nodes = nodeGroup.selectAll('.node')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', (d, i) => {
        const angle = i * angleStep - Math.PI / 2;
        const x = Math.cos(angle) * (outerRadius - 60);
        const y = Math.sin(angle) * (outerRadius - 60);
        return `translate(${x}, ${y})`;
      });

    nodes.append('circle')
      .attr('r', 35)
      .attr('fill', theme.bg)
      .attr('stroke', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke-width', 3);

    nodes.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '-0.2em')
      .attr('fill', theme.fg)
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .text((d, i) => i + 1);

    nodes.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '1.2em')
      .attr('fill', theme.fg)
      .style('font-size', '10px')
      .text(d => d.label.length > 6 ? d.label.slice(0, 6) + '…' : d.label);

    // 自動回転
    if (autoRotate) {
      let rotation = 0;
      d3.interval(() => {
        rotation += 0.5;
        nodeGroup.attr('transform', `rotate(${rotation})`);
      }, 50);
    }

    // エントリーアニメーション
    if (animate) {
      nodes.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => 400 + i * 100)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { D3Cycle };
}
