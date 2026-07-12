/**
 * D3.js Hierarchy Components
 *
 * 階層系図解: ツリー、組織図、ピラミッド、サンバースト、Treemap、Packed Circles
 * d3-hierarchy レイアウト活用
 */

const D3Hierarchy = {
  /**
   * ツリー図（横方向）
   * @param {string} selector
   * @param {Object} data - 階層データ { name, children: [...] }
   * @param {Object} options
   */
  createTree(selector, data, options = {}) {
    const {
      width = 800,
      height = 500,
      direction = 'horizontal', // horizontal | vertical
      animate = true,
      nodeRadius = 8
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 40, right: 120, bottom: 40, left: 120 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart tree-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // 階層データ作成
    const root = d3.hierarchy(data);

    // ツリーレイアウト
    const treeLayout = direction === 'horizontal'
      ? d3.tree().size([innerHeight, innerWidth])
      : d3.tree().size([innerWidth, innerHeight]);

    treeLayout(root);

    // リンク（接続線）
    const linkGenerator = direction === 'horizontal'
      ? d3.linkHorizontal().x(d => d.y).y(d => d.x)
      : d3.linkVertical().x(d => d.x).y(d => d.y);

    const links = g.selectAll('.link')
      .data(root.links())
      .enter()
      .append('path')
      .attr('class', 'link')
      .attr('d', linkGenerator)
      .attr('fill', 'none')
      .attr('stroke', theme.border)
      .attr('stroke-width', 2);

    if (animate) {
      links.each(function() {
        const path = d3.select(this);
        D3Base.animateEntry(path, 'drawPath');
      });
    }

    // ノード
    const nodes = g.selectAll('.node')
      .data(root.descendants())
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => direction === 'horizontal'
        ? `translate(${d.y}, ${d.x})`
        : `translate(${d.x}, ${d.y})`);

    // ノード円
    nodes.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', d => d.children ? accentPalette[d.depth % accentPalette.length] : theme.surface)
      .attr('stroke', d => accentPalette[d.depth % accentPalette.length])
      .attr('stroke-width', 2);

    // ノードラベル
    nodes.append('text')
      .attr('dy', '0.35em')
      .attr('x', d => direction === 'horizontal'
        ? (d.children ? -12 : 12)
        : 0)
      .attr('y', d => direction === 'vertical'
        ? (d.children ? -15 : 20)
        : 0)
      .attr('text-anchor', d => {
        if (direction === 'horizontal') return d.children ? 'end' : 'start';
        return 'middle';
      })
      .attr('fill', theme.fg)
      .style('font-size', '12px')
      .text(d => d.data.name);

    // ホバーエフェクト
    nodes.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', nodeRadius * 1.5);

        if (d.data.description) {
          tooltip
            .style('opacity', 1)
            .html(d.data.description)
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
        .delay((d, i) => i * 50)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * 組織図
   * @param {string} selector
   * @param {Object} data - { name, title?, children }
   * @param {Object} options
   */
  createOrgChart(selector, data, options = {}) {
    const {
      width = 900,
      height = 600,
      nodeWidth = 140,
      nodeHeight = 60,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 60, right: 40, bottom: 40, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart org-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // 階層データ
    const root = d3.hierarchy(data);
    const treeLayout = d3.tree().size([innerWidth, innerHeight]).nodeSize([nodeWidth + 20, nodeHeight + 40]);
    treeLayout(root);

    // 中央揃え調整
    let x0 = Infinity, x1 = -Infinity;
    root.each(d => {
      if (d.x > x1) x1 = d.x;
      if (d.x < x0) x0 = d.x;
    });
    const dx = (innerWidth - (x1 - x0)) / 2 - x0;

    // リンク
    const linkGroup = g.append('g').attr('class', 'links');

    linkGroup.selectAll('.link')
      .data(root.links())
      .enter()
      .append('path')
      .attr('class', 'link')
      .attr('d', d => {
        const sx = d.source.x + dx;
        const sy = d.source.y;
        const tx = d.target.x + dx;
        const ty = d.target.y;
        return `M ${sx} ${sy + nodeHeight / 2}
                V ${(sy + ty) / 2}
                H ${tx}
                V ${ty - nodeHeight / 2}`;
      })
      .attr('fill', 'none')
      .attr('stroke', theme.border)
      .attr('stroke-width', 2);

    // ノード
    const nodes = g.selectAll('.node')
      .data(root.descendants())
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${d.x + dx}, ${d.y})`);

    // ノードカード
    nodes.append('rect')
      .attr('x', -nodeWidth / 2)
      .attr('y', -nodeHeight / 2)
      .attr('width', nodeWidth)
      .attr('height', nodeHeight)
      .attr('rx', 8)
      .attr('fill', d => d.depth === 0 ? accentPalette[0] : theme.bg)
      .attr('stroke', d => accentPalette[d.depth % accentPalette.length])
      .attr('stroke-width', 2);

    // 名前
    nodes.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => d.data.title ? '-0.3em' : '0.35em')
      .attr('fill', d => d.depth === 0 ? '#fff' : theme.fg)
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .text(d => d.data.name);

    // 役職
    nodes.filter(d => d.data.title)
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '1em')
      .attr('fill', d => d.depth === 0 ? 'rgba(255,255,255,0.8)' : theme.fgDim)
      .style('font-size', '11px')
      .text(d => d.data.title);

    // ホバーエフェクト
    D3Base.addHoverEffect(nodes.select('rect'), { scale: 1.05 });

    // エントリーアニメーション
    if (animate) {
      nodes.style('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => d.depth * 200 + i * 30)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * ピラミッド図
   * @param {string} selector
   * @param {Array} data - [{ label, value?, description }] 上から下へ
   * @param {Object} options
   */
  createPyramid(selector, data, options = {}) {
    const {
      width = 600,
      height = 500,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 40, right: 60, bottom: 40, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart pyramid-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    const n = data.length;
    const layerHeight = innerHeight / n;
    const topWidth = innerWidth * 0.3;
    const bottomWidth = innerWidth;

    // 各レイヤー
    const layers = g.selectAll('.layer')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'layer');

    layers.append('path')
      .attr('d', (d, i) => {
        const topY = i * layerHeight;
        const bottomY = (i + 1) * layerHeight;
        const topW = topWidth + (bottomWidth - topWidth) * (i / n);
        const bottomW = topWidth + (bottomWidth - topWidth) * ((i + 1) / n);
        const centerX = innerWidth / 2;

        return `M ${centerX - topW / 2} ${topY}
                L ${centerX + topW / 2} ${topY}
                L ${centerX + bottomW / 2} ${bottomY}
                L ${centerX - bottomW / 2} ${bottomY}
                Z`;
      })
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2)
      .attr('opacity', 0.85);

    // ラベル
    layers.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', (d, i) => i * layerHeight + layerHeight / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .text(d => d.label);

    // 値（右側）
    layers.filter(d => d.value !== undefined)
      .append('text')
      .attr('x', innerWidth + 10)
      .attr('y', (d, i) => i * layerHeight + layerHeight / 2)
      .attr('dy', '0.35em')
      .attr('fill', theme.fgDim)
      .style('font-size', '12px')
      .text(d => d.value);

    // ホバー＆ツールチップ
    layers.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('path')
          .transition()
          .duration(200)
          .attr('opacity', 1);

        if (d.description) {
          tooltip
            .style('opacity', 1)
            .html(d.description)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
        }
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
   * サンバースト図（階層円形）
   * @param {string} selector
   * @param {Object} data - 階層データ { name, value?, children }
   * @param {Object} options
   */
  createSunburst(selector, data, options = {}) {
    const {
      width = 600,
      height = 600,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const radius = Math.min(width, height) / 2;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart sunburst-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // パーティションレイアウト
    const partition = d3.partition()
      .size([2 * Math.PI, radius]);

    const root = d3.hierarchy(data)
      .sum(d => d.value || 1)
      .sort((a, b) => b.value - a.value);

    partition(root);

    // 弧ジェネレータ
    const arc = d3.arc()
      .startAngle(d => d.x0)
      .endAngle(d => d.x1)
      .innerRadius(d => d.y0)
      .outerRadius(d => d.y1 - 1);

    // パス描画
    const paths = g.selectAll('path')
      .data(root.descendants().filter(d => d.depth))
      .enter()
      .append('path')
      .attr('d', arc)
      .attr('fill', d => {
        let current = d;
        while (current.depth > 1) current = current.parent;
        return accentPalette[current.parent.children.indexOf(current) % accentPalette.length];
      })
      .attr('fill-opacity', d => 1 - d.depth * 0.15)
      .attr('stroke', theme.bg)
      .attr('stroke-width', 1);

    // 中心ラベル
    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', theme.fg)
      .style('font-size', '16px')
      .style('font-weight', 'bold')
      .text(data.name);

    // ホバー＆ツールチップ
    paths.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill-opacity', 1);

        const ancestors = d.ancestors().reverse().map(a => a.data.name).join(' > ');
        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.data.name}</strong><br>${ancestors}${d.value ? `<br>値: ${d.value}` : ''}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill-opacity', 1 - d.depth * 0.15);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      paths.attr('opacity', 0)
        .transition()
        .duration(800)
        .delay((d, i) => i * 20)
        .attr('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * Treemap（矩形階層）
   * @param {string} selector
   * @param {Object} data - { name, children: [{ name, value }] }
   * @param {Object} options
   */
  createTreemap(selector, data, options = {}) {
    const {
      width = 800,
      height = 500,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart treemap-chart');

    // Treemapレイアウト
    const treemap = d3.treemap()
      .size([width, height])
      .padding(2)
      .round(true);

    const root = d3.hierarchy(data)
      .sum(d => d.value || 0)
      .sort((a, b) => b.value - a.value);

    treemap(root);

    // セル作成
    const cells = svg.selectAll('.cell')
      .data(root.leaves())
      .enter()
      .append('g')
      .attr('class', 'cell')
      .attr('transform', d => `translate(${d.x0}, ${d.y0})`);

    // 矩形
    cells.append('rect')
      .attr('width', d => d.x1 - d.x0)
      .attr('height', d => d.y1 - d.y0)
      .attr('fill', d => {
        let current = d;
        while (current.depth > 1) current = current.parent;
        const idx = current.parent ? current.parent.children.indexOf(current) : 0;
        return accentPalette[idx % accentPalette.length];
      })
      .attr('fill-opacity', 0.8)
      .attr('stroke', theme.bg)
      .attr('stroke-width', 1);

    // ラベル（サイズに応じて表示）
    cells.filter(d => (d.x1 - d.x0) > 50 && (d.y1 - d.y0) > 25)
      .append('text')
      .attr('x', 5)
      .attr('y', 15)
      .attr('fill', '#fff')
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .text(d => d.data.name.length > 10 ? d.data.name.slice(0, 10) + '…' : d.data.name);

    // 値（サイズに応じて表示）
    cells.filter(d => (d.x1 - d.x0) > 50 && (d.y1 - d.y0) > 40)
      .append('text')
      .attr('x', 5)
      .attr('y', 30)
      .attr('fill', 'rgba(255,255,255,0.8)')
      .style('font-size', '11px')
      .text(d => D3Base.formatNumber(d.value));

    // ホバー＆ツールチップ
    cells.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('rect')
          .transition()
          .duration(200)
          .attr('fill-opacity', 1);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.data.name}</strong><br>値: ${D3Base.formatNumber(d.value)}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this).select('rect')
          .transition()
          .duration(200)
          .attr('fill-opacity', 0.8);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      cells.style('opacity', 0)
        .transition()
        .duration(600)
        .delay((d, i) => i * 30)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * Packed Circles（円パッキング）
   * @param {string} selector
   * @param {Object} data - 階層データ
   * @param {Object} options
   */
  createPackedCircles(selector, data, options = {}) {
    const {
      width = 600,
      height = 600,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart packed-circles-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // パックレイアウト
    const pack = d3.pack()
      .size([width - 4, height - 4])
      .padding(3);

    const root = d3.hierarchy(data)
      .sum(d => d.value || 1)
      .sort((a, b) => b.value - a.value);

    pack(root);

    // ノード（円）
    const nodes = g.selectAll('.node')
      .data(root.descendants())
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${d.x - width / 2}, ${d.y - height / 2})`);

    nodes.append('circle')
      .attr('r', d => d.r)
      .attr('fill', d => d.children ? 'transparent' : accentPalette[d.depth % accentPalette.length])
      .attr('fill-opacity', d => d.children ? 0 : 0.8)
      .attr('stroke', d => accentPalette[d.depth % accentPalette.length])
      .attr('stroke-width', d => d.children ? 1 : 0)
      .attr('stroke-opacity', 0.5);

    // ラベル（葉のみ）
    nodes.filter(d => !d.children && d.r > 20)
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', '#fff')
      .style('font-size', d => Math.min(d.r / 3, 14) + 'px')
      .text(d => d.data.name.length > 8 ? d.data.name.slice(0, 8) + '…' : d.data.name);

    // ホバー＆ツールチップ
    nodes.filter(d => !d.children)
      .style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('fill-opacity', 1);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.data.name}</strong>${d.value ? `<br>値: ${d.value}` : ''}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('fill-opacity', 0.8);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      nodes.select('circle')
        .attr('r', 0)
        .transition()
        .duration(800)
        .delay((d, i) => i * 10)
        .attr('r', d => d.r);

      nodes.select('text')
        .style('opacity', 0)
        .transition()
        .duration(400)
        .delay((d, i) => 500 + i * 10)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { D3Hierarchy };
}
