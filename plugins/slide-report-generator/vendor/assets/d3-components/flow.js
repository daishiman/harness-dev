/**
 * D3.js Flow Components
 *
 * フロー系図解: Sankey図、シェブロン、ロードマップ、ファネル、タイムライン
 * パスアニメーション、ホバーエフェクト対応
 */

const D3Flow = {
  /**
   * Sankey図（フロー可視化）
   * @param {string} selector
   * @param {Object} data - { nodes: [{name}], links: [{source, target, value}] }
   * @param {Object} options
   */
  createSankey(selector, data, options = {}) {
    const {
      width = 800,
      height = 500,
      nodeWidth = 20,
      nodePadding = 20,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 20, right: 100, bottom: 20, left: 100 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart sankey-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // Sankeyレイアウト（d3-sankey使用想定、シンプル実装）
    // ノード配置計算
    const nodeMap = new Map(data.nodes.map((n, i) => [n.name, { ...n, index: i, x: 0, y: 0, sourceLinks: [], targetLinks: [] }]));

    // リンクにノード参照を追加
    const links = data.links.map(l => ({
      ...l,
      source: nodeMap.get(l.source) || nodeMap.get(data.nodes[l.source]?.name),
      target: nodeMap.get(l.target) || nodeMap.get(data.nodes[l.target]?.name)
    }));

    // ノードへのリンク関連付け
    links.forEach(link => {
      if (link.source) link.source.sourceLinks.push(link);
      if (link.target) link.target.targetLinks.push(link);
    });

    // ノードの階層（深さ）計算
    const nodes = Array.from(nodeMap.values());
    nodes.forEach(n => {
      n.depth = n.targetLinks.length === 0 ? 0 : Math.max(...n.targetLinks.map(l => l.source.depth + 1));
    });

    const maxDepth = Math.max(...nodes.map(n => n.depth));

    // X座標
    nodes.forEach(n => {
      n.x = (n.depth / maxDepth) * (innerWidth - nodeWidth);
    });

    // Y座標（各深さでグループ化）
    for (let d = 0; d <= maxDepth; d++) {
      const layerNodes = nodes.filter(n => n.depth === d);
      const totalValue = layerNodes.reduce((sum, n) => sum + Math.max(
        n.sourceLinks.reduce((s, l) => s + l.value, 0),
        n.targetLinks.reduce((s, l) => s + l.value, 0),
        1
      ), 0);

      let y = 0;
      layerNodes.forEach(n => {
        const nodeValue = Math.max(
          n.sourceLinks.reduce((s, l) => s + l.value, 0),
          n.targetLinks.reduce((s, l) => s + l.value, 0),
          1
        );
        n.height = (nodeValue / totalValue) * (innerHeight - (layerNodes.length - 1) * nodePadding);
        n.y = y;
        y += n.height + nodePadding;
      });
    }

    // リンク描画
    const linkGroup = g.append('g').attr('class', 'links');

    const linkPaths = linkGroup.selectAll('.link')
      .data(links)
      .enter()
      .append('path')
      .attr('class', 'link')
      .attr('d', d => {
        const sx = d.source.x + nodeWidth;
        const sy = d.source.y + d.source.height / 2;
        const tx = d.target.x;
        const ty = d.target.y + d.target.height / 2;
        const midX = (sx + tx) / 2;
        return `M ${sx} ${sy} C ${midX} ${sy}, ${midX} ${ty}, ${tx} ${ty}`;
      })
      .attr('fill', 'none')
      .attr('stroke', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', d => Math.max(d.value * 5, 2));

    // リンクホバー
    linkPaths.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('stroke-opacity', 0.8);

        tooltip
          .style('opacity', 1)
          .html(`${d.source.name} → ${d.target.name}<br>値: ${d.value}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('stroke-opacity', 0.4);

        tooltip.style('opacity', 0);
      });

    // ノード描画
    const nodeGroup = g.append('g').attr('class', 'nodes');

    const nodeRects = nodeGroup.selectAll('.node')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${d.x}, ${d.y})`);

    nodeRects.append('rect')
      .attr('width', nodeWidth)
      .attr('height', d => d.height)
      .attr('fill', (d, i) => accentPalette[d.depth % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 1);

    // ノードラベル
    nodeRects.append('text')
      .attr('x', d => d.depth < maxDepth / 2 ? nodeWidth + 6 : -6)
      .attr('y', d => d.height / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', d => d.depth < maxDepth / 2 ? 'start' : 'end')
      .attr('fill', theme.fg)
      .style('font-size', '12px')
      .text(d => d.name);

    // エントリーアニメーション
    if (animate) {
      linkPaths.attr('stroke-opacity', 0)
        .transition()
        .duration(800)
        .delay((d, i) => i * 50)
        .attr('stroke-opacity', 0.4);

      nodeRects.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => 300 + i * 50)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * シェブロン/矢印ステップ
   * @param {string} selector
   * @param {Array} data - [{ label, description?, highlight? }]
   * @param {Object} options
   */
  createChevron(selector, data, options = {}) {
    const {
      width = 800,
      height = 180,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 30, right: 20, bottom: 30, left: 20 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const n = data.length;
    const chevronWidth = innerWidth / n;
    const chevronDepth = 25; // 矢印の深さ
    const chevronHeight = innerHeight;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart chevron-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // シェブロン（矢印形状）描画
    const chevrons = g.selectAll('.chevron')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'chevron')
      .attr('transform', (d, i) => `translate(${i * chevronWidth}, 0)`);

    chevrons.append('path')
      .attr('d', (d, i) => {
        const x0 = i === 0 ? 0 : -chevronDepth;
        const x1 = chevronWidth - chevronDepth;
        const x2 = chevronWidth;
        const y0 = 0;
        const y1 = chevronHeight / 2;
        const y2 = chevronHeight;

        if (i === 0) {
          return `M 0 ${y0} L ${x1} ${y0} L ${x2} ${y1} L ${x1} ${y2} L 0 ${y2} Z`;
        }
        return `M ${x0} ${y0} L ${x1} ${y0} L ${x2} ${y1} L ${x1} ${y2} L ${x0} ${y2} L 0 ${y1} Z`;
      })
      .attr('fill', (d, i) => d.highlight ? accentPalette[1] : accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2)
      .attr('opacity', 0.9);

    // ステップ番号
    chevrons.append('text')
      .attr('x', (d, i) => i === 0 ? chevronWidth / 2 - chevronDepth / 2 : chevronWidth / 2 - chevronDepth)
      .attr('y', chevronHeight / 2 - 12)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .text((d, i) => `STEP ${i + 1}`);

    // ラベル
    chevrons.append('text')
      .attr('x', (d, i) => i === 0 ? chevronWidth / 2 - chevronDepth / 2 : chevronWidth / 2 - chevronDepth)
      .attr('y', chevronHeight / 2 + 8)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .text(d => d.label.length > 10 ? d.label.slice(0, 10) + '…' : d.label);

    // ホバー＆ツールチップ
    chevrons.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('path')
          .transition()
          .duration(200)
          .attr('opacity', 1)
          .attr('transform', 'scale(1.02) translate(-2, -1)');

        if (d.description) {
          tooltip
            .style('opacity', 1)
            .html(`<strong>${d.label}</strong><br>${d.description}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
        }
      })
      .on('mouseleave', function() {
        d3.select(this).select('path')
          .transition()
          .duration(200)
          .attr('opacity', 0.9)
          .attr('transform', 'scale(1) translate(0, 0)');

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      chevrons.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => i * 150)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * ロードマップ（水平タイムライン）
   * @param {string} selector
   * @param {Array} data - [{ label, date?, items: [], highlight? }]
   * @param {Object} options
   */
  createRoadmap(selector, data, options = {}) {
    const {
      width = 900,
      height = 300,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 50, right: 40, bottom: 60, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const n = data.length;
    const phaseWidth = innerWidth / n;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart roadmap-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // メインライン
    const line = g.append('line')
      .attr('x1', 0)
      .attr('y1', innerHeight / 2)
      .attr('x2', innerWidth)
      .attr('y2', innerHeight / 2)
      .attr('stroke', theme.border)
      .attr('stroke-width', 4)
      .attr('stroke-linecap', 'round');

    if (animate) {
      line.attr('x2', 0)
        .transition()
        .duration(800)
        .attr('x2', innerWidth);
    }

    // フェーズ
    const phases = g.selectAll('.phase')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'phase')
      .attr('transform', (d, i) => `translate(${i * phaseWidth + phaseWidth / 2}, ${innerHeight / 2})`);

    // マイルストーン円
    phases.append('circle')
      .attr('r', 16)
      .attr('fill', (d, i) => d.highlight ? accentPalette[1] : accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 3);

    // フェーズ番号
    phases.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', '#fff')
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .text((d, i) => i + 1);

    // ラベル（上部）
    phases.append('text')
      .attr('y', -35)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.fg)
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .text(d => d.label);

    // 日付（下部）
    phases.filter(d => d.date)
      .append('text')
      .attr('y', 35)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.fgDim)
      .style('font-size', '11px')
      .text(d => d.date);

    // アイテム（下部カード）
    phases.filter(d => d.items && d.items.length > 0)
      .each(function(d, phaseIndex) {
        const itemGroup = d3.select(this).append('g')
          .attr('transform', 'translate(0, 55)');

        const itemHeight = 20;
        const itemWidth = phaseWidth - 20;

        d.items.forEach((item, i) => {
          itemGroup.append('rect')
            .attr('x', -itemWidth / 2)
            .attr('y', i * (itemHeight + 4))
            .attr('width', itemWidth)
            .attr('height', itemHeight)
            .attr('rx', 4)
            .attr('fill', theme.surface)
            .attr('stroke', theme.border)
            .attr('stroke-width', 1);

          itemGroup.append('text')
            .attr('x', 0)
            .attr('y', i * (itemHeight + 4) + itemHeight / 2)
            .attr('dy', '0.35em')
            .attr('text-anchor', 'middle')
            .attr('fill', theme.fg)
            .style('font-size', '10px')
            .text(item.length > 12 ? item.slice(0, 12) + '…' : item);
        });
      });

    // ホバー
    phases.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', 20);
      })
      .on('mouseleave', function() {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', 16);
      });

    // エントリーアニメーション
    if (animate) {
      phases.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => 400 + i * 200)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * ファネル（逆三角形）
   * @param {string} selector
   * @param {Array} data - [{ label, value, percentage? }]
   * @param {Object} options
   */
  createFunnel(selector, data, options = {}) {
    const {
      width = 600,
      height = 500,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 30, right: 120, bottom: 30, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const n = data.length;
    const layerHeight = innerHeight / n;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart funnel-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // 最大値
    const maxValue = Math.max(...data.map(d => d.value));

    // 各層
    const layers = g.selectAll('.layer')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'layer');

    layers.append('path')
      .attr('d', (d, i) => {
        const topWidth = innerWidth * (1 - (i / n) * 0.7);
        const bottomWidth = innerWidth * (1 - ((i + 1) / n) * 0.7);
        const topY = i * layerHeight;
        const bottomY = (i + 1) * layerHeight;
        const centerX = innerWidth / 2;

        return `M ${centerX - topWidth / 2} ${topY}
                L ${centerX + topWidth / 2} ${topY}
                L ${centerX + bottomWidth / 2} ${bottomY}
                L ${centerX - bottomWidth / 2} ${bottomY}
                Z`;
      })
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2)
      .attr('opacity', 0.85);

    // ラベル（中央）
    layers.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', (d, i) => i * layerHeight + layerHeight / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .text(d => d.label);

    // 値・パーセンテージ（右側）
    layers.append('text')
      .attr('x', innerWidth + 15)
      .attr('y', (d, i) => i * layerHeight + layerHeight / 2 - 8)
      .attr('fill', theme.fg)
      .style('font-size', '16px')
      .style('font-weight', 'bold')
      .text(d => D3Base.formatNumber(d.value));

    layers.filter(d => d.percentage !== undefined)
      .append('text')
      .attr('x', innerWidth + 15)
      .attr('y', (d, i) => i * layerHeight + layerHeight / 2 + 10)
      .attr('fill', theme.fgDim)
      .style('font-size', '12px')
      .text(d => `${d.percentage}%`);

    // コンバージョン率矢印
    layers.filter((d, i) => i < n - 1)
      .append('text')
      .attr('x', innerWidth + 80)
      .attr('y', (d, i) => i * layerHeight + layerHeight)
      .attr('text-anchor', 'middle')
      .attr('fill', accentPalette[2])
      .style('font-size', '11px')
      .text((d, i) => {
        const current = d.value;
        const next = data[i + 1].value;
        const rate = ((next / current) * 100).toFixed(0);
        return `↓ ${rate}%`;
      });

    // ホバー
    layers.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('path')
          .transition()
          .duration(200)
          .attr('opacity', 1);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.label}</strong><br>値: ${D3Base.formatNumber(d.value)}${d.percentage !== undefined ? `<br>全体の${d.percentage}%` : ''}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this).select('path')
          .transition()
          .duration(200)
          .attr('opacity', 0.85);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      layers.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => i * 150)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * 縦タイムライン
   * @param {string} selector
   * @param {Array} data - [{ label, date?, description?, highlight? }]
   * @param {Object} options
   */
  createVerticalTimeline(selector, data, options = {}) {
    const {
      width = 500,
      height = 600,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 40, right: 40, bottom: 40, left: 100 };
    const innerHeight = height - margin.top - margin.bottom;

    const n = data.length;
    const stepHeight = innerHeight / (n - 1 || 1);

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart vertical-timeline-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // メインライン
    const line = g.append('line')
      .attr('x1', 0)
      .attr('y1', 0)
      .attr('x2', 0)
      .attr('y2', innerHeight)
      .attr('stroke', theme.border)
      .attr('stroke-width', 3)
      .attr('stroke-linecap', 'round');

    if (animate) {
      line.attr('y2', 0)
        .transition()
        .duration(800)
        .attr('y2', innerHeight);
    }

    // イベント
    const events = g.selectAll('.event')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'event')
      .attr('transform', (d, i) => `translate(0, ${i * stepHeight})`);

    // ドット
    events.append('circle')
      .attr('r', 10)
      .attr('fill', (d, i) => d.highlight ? accentPalette[1] : accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 3);

    // 日付（左側）
    events.filter(d => d.date)
      .append('text')
      .attr('x', -15)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('fill', theme.fgDim)
      .style('font-size', '11px')
      .text(d => d.date);

    // カード（右側）
    const cards = events.append('g')
      .attr('transform', 'translate(25, -25)');

    cards.append('rect')
      .attr('width', width - margin.left - margin.right - 50)
      .attr('height', 50)
      .attr('rx', 8)
      .attr('fill', theme.surface)
      .attr('stroke', (d, i) => d.highlight ? accentPalette[1] : theme.border)
      .attr('stroke-width', d => d.highlight ? 2 : 1);

    cards.append('text')
      .attr('x', 15)
      .attr('y', 20)
      .attr('fill', theme.fg)
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .text(d => d.label);

    cards.filter(d => d.description)
      .append('text')
      .attr('x', 15)
      .attr('y', 38)
      .attr('fill', theme.fgDim)
      .style('font-size', '11px')
      .text(d => d.description.length > 40 ? d.description.slice(0, 40) + '…' : d.description);

    // ホバー
    events.style('cursor', 'pointer')
      .on('mouseenter', function() {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', 14);
      })
      .on('mouseleave', function() {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', 10);
      });

    // エントリーアニメーション
    if (animate) {
      events.style('opacity', 0)
        .transition()
        .duration(400)
        .delay((d, i) => 300 + i * 150)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { D3Flow };
}
