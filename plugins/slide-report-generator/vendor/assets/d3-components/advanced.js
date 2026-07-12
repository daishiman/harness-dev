/**
 * D3.js Advanced Components
 *
 * 高度な図解: Force-Directed Graph、Chord Diagram、Arc Diagram、
 * Word Cloud、Heatmap、Radial Bar Chart
 */

const D3Advanced = {
  /**
   * Force-Directed Graph（力学モデルネットワーク）
   * @param {string} selector
   * @param {Object} data - { nodes: [{id, group?, label?}], links: [{source, target, value?}] }
   * @param {Object} options
   */
  createForceGraph(selector, data, options = {}) {
    const {
      width = 700,
      height = 600,
      animate = true,
      draggable = true,
      nodeRadius = 20
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart force-graph');

    // ノードとリンクのコピー
    const nodes = data.nodes.map(d => ({ ...d }));
    const links = data.links.map(d => ({ ...d }));

    // シミュレーション
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(nodeRadius + 5));

    // リンク
    const link = svg.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', theme.border)
      .attr('stroke-width', d => Math.sqrt(d.value || 1) * 2)
      .attr('stroke-opacity', 0.6);

    // ノード
    const node = svg.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g');

    node.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', d => accentPalette[(d.group || 0) % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', '#fff')
      .style('font-size', '11px')
      .style('font-weight', 'bold')
      .text(d => d.label || d.id);

    // ドラッグ
    if (draggable) {
      node.call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));
    }

    // ホバー＆ツールチップ
    node.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', nodeRadius * 1.3);

        // 接続ハイライト
        link.attr('stroke-opacity', l =>
          l.source.id === d.id || l.target.id === d.id ? 1 : 0.2);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.label || d.id}</strong>`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', nodeRadius);

        link.attr('stroke-opacity', 0.6);
        tooltip.style('opacity', 0);
      });

    // シミュレーション更新
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x}, ${d.y})`);
    });

    // 初期アニメーション
    if (animate) {
      node.style('opacity', 0)
        .transition()
        .duration(500)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * Chord Diagram（弦図）
   * @param {string} selector
   * @param {Object} data - { names: [], matrix: [[]] }
   * @param {Object} options
   */
  createChordDiagram(selector, data, options = {}) {
    const {
      width = 600,
      height = 600,
      innerRadius = 200,
      outerRadius = 220,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart chord-diagram');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // Chord レイアウト
    const chord = d3.chord()
      .padAngle(0.05)
      .sortSubgroups(d3.descending);

    const chords = chord(data.matrix);

    // グループ（外側の弧）
    const arc = d3.arc()
      .innerRadius(innerRadius)
      .outerRadius(outerRadius);

    const groups = g.selectAll('.group')
      .data(chords.groups)
      .enter()
      .append('g')
      .attr('class', 'group');

    groups.append('path')
      .attr('d', arc)
      .attr('fill', d => accentPalette[d.index % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 1);

    // グループラベル
    groups.append('text')
      .each(d => { d.angle = (d.startAngle + d.endAngle) / 2; })
      .attr('dy', '0.35em')
      .attr('transform', d => `
        rotate(${(d.angle * 180 / Math.PI - 90)})
        translate(${outerRadius + 10})
        ${d.angle > Math.PI ? 'rotate(180)' : ''}
      `)
      .attr('text-anchor', d => d.angle > Math.PI ? 'end' : 'start')
      .attr('fill', theme.fg)
      .style('font-size', '12px')
      .text(d => data.names[d.index]);

    // リボン（弦）
    const ribbon = d3.ribbon()
      .radius(innerRadius);

    const ribbons = g.selectAll('.ribbon')
      .data(chords)
      .enter()
      .append('path')
      .attr('class', 'ribbon')
      .attr('d', ribbon)
      .attr('fill', d => accentPalette[d.source.index % accentPalette.length])
      .attr('fill-opacity', 0.5)
      .attr('stroke', theme.bg)
      .attr('stroke-width', 0.5);

    // ホバー
    ribbons.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill-opacity', 0.8);

        tooltip
          .style('opacity', 1)
          .html(`${data.names[d.source.index]} → ${data.names[d.target.index]}<br>値: ${d.source.value}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill-opacity', 0.5);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      groups.style('opacity', 0)
        .transition()
        .duration(600)
        .style('opacity', 1);

      ribbons.style('opacity', 0)
        .transition()
        .duration(600)
        .delay(300)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * Heatmap
   * @param {string} selector
   * @param {Object} data - { rows: [], cols: [], values: [[]] }
   * @param {Object} options
   */
  createHeatmap(selector, data, options = {}) {
    const {
      width = 700,
      height = 500,
      animate = true,
      colorScheme = 'sequential' // 'sequential' | 'diverging'
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 60, right: 30, bottom: 30, left: 100 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart heatmap');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // スケール
    const xScale = d3.scaleBand()
      .domain(data.cols)
      .range([0, innerWidth])
      .padding(0.05);

    const yScale = d3.scaleBand()
      .domain(data.rows)
      .range([0, innerHeight])
      .padding(0.05);

    // 値の範囲
    const flatValues = data.values.flat();
    const minVal = d3.min(flatValues);
    const maxVal = d3.max(flatValues);

    // カラースケール
    let colorScale;
    if (colorScheme === 'diverging') {
      colorScale = d3.scaleSequential()
        .domain([minVal, maxVal])
        .interpolator(d3.interpolateRdYlBu);
    } else {
      colorScale = d3.scaleSequential()
        .domain([minVal, maxVal])
        .interpolator(d3.interpolateBlues);
    }

    // セル
    data.rows.forEach((row, rowIndex) => {
      data.cols.forEach((col, colIndex) => {
        const value = data.values[rowIndex][colIndex];

        const cell = g.append('rect')
          .attr('x', xScale(col))
          .attr('y', yScale(row))
          .attr('width', xScale.bandwidth())
          .attr('height', yScale.bandwidth())
          .attr('fill', colorScale(value))
          .attr('rx', 2)
          .attr('stroke', theme.bg)
          .attr('stroke-width', 1);

        // ホバー
        cell.style('cursor', 'pointer')
          .on('mouseenter', function(event) {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('stroke', accentPalette[0])
              .attr('stroke-width', 2);

            tooltip
              .style('opacity', 1)
              .html(`<strong>${row} × ${col}</strong><br>値: ${value}`)
              .style('left', (event.pageX + 10) + 'px')
              .style('top', (event.pageY - 10) + 'px');
          })
          .on('mouseleave', function() {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('stroke', theme.bg)
              .attr('stroke-width', 1);

            tooltip.style('opacity', 0);
          });

        if (animate) {
          cell.attr('opacity', 0)
            .transition()
            .duration(400)
            .delay((rowIndex * data.cols.length + colIndex) * 10)
            .attr('opacity', 1);
        }
      });
    });

    // X軸ラベル
    g.selectAll('.x-label')
      .data(data.cols)
      .enter()
      .append('text')
      .attr('class', 'x-label')
      .attr('x', d => xScale(d) + xScale.bandwidth() / 2)
      .attr('y', -10)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.fg)
      .style('font-size', '11px')
      .text(d => d);

    // Y軸ラベル
    g.selectAll('.y-label')
      .data(data.rows)
      .enter()
      .append('text')
      .attr('class', 'y-label')
      .attr('x', -10)
      .attr('y', d => yScale(d) + yScale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('fill', theme.fg)
      .style('font-size', '11px')
      .text(d => d);

    // カラーレジェンド
    const legendWidth = 200;
    const legendHeight = 15;
    const legendX = innerWidth - legendWidth;
    const legendY = -45;

    const legendScale = d3.scaleLinear()
      .domain([minVal, maxVal])
      .range([0, legendWidth]);

    const legendAxis = d3.axisBottom(legendScale)
      .ticks(5)
      .tickFormat(d3.format('.2s'));

    const defs = svg.append('defs');
    const gradient = defs.append('linearGradient')
      .attr('id', 'heatmap-gradient');

    for (let i = 0; i <= 10; i++) {
      const value = minVal + (maxVal - minVal) * (i / 10);
      gradient.append('stop')
        .attr('offset', `${i * 10}%`)
        .attr('stop-color', colorScale(value));
    }

    const legend = g.append('g')
      .attr('transform', `translate(${legendX}, ${legendY})`);

    legend.append('rect')
      .attr('width', legendWidth)
      .attr('height', legendHeight)
      .attr('fill', 'url(#heatmap-gradient)')
      .attr('rx', 2);

    legend.append('g')
      .attr('transform', `translate(0, ${legendHeight})`)
      .call(legendAxis)
      .selectAll('text')
      .attr('fill', theme.fgDim)
      .style('font-size', '10px');

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * Radial Bar Chart（放射状棒グラフ）
   * @param {string} selector
   * @param {Array} data - [{ label, value }]
   * @param {Object} options
   */
  createRadialBarChart(selector, data, options = {}) {
    const {
      width = 500,
      height = 500,
      innerRadius = 60,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const outerRadius = Math.min(width, height) / 2 - 40;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart radial-bar-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // スケール
    const xScale = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([0, 2 * Math.PI])
      .padding(0.1);

    const yScale = d3.scaleRadial()
      .domain([0, d3.max(data, d => d.value)])
      .range([innerRadius, outerRadius]);

    // 背景リング
    g.append('circle')
      .attr('r', outerRadius)
      .attr('fill', 'none')
      .attr('stroke', theme.border)
      .attr('stroke-opacity', 0.3);

    g.append('circle')
      .attr('r', innerRadius)
      .attr('fill', theme.surface);

    // バー
    const arcGenerator = d3.arc()
      .innerRadius(innerRadius)
      .startAngle(d => xScale(d.label))
      .endAngle(d => xScale(d.label) + xScale.bandwidth())
      .padAngle(0.02)
      .padRadius(innerRadius);

    const bars = g.selectAll('.bar')
      .data(data)
      .enter()
      .append('path')
      .attr('class', 'bar')
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 1);

    if (animate) {
      bars.attr('d', d => arcGenerator.outerRadius(innerRadius)(d))
        .transition()
        .duration(800)
        .delay((d, i) => i * 100)
        .attr('d', d => arcGenerator.outerRadius(yScale(d.value))(d));
    } else {
      bars.attr('d', d => arcGenerator.outerRadius(yScale(d.value))(d));
    }

    // ラベル
    g.selectAll('.label')
      .data(data)
      .enter()
      .append('text')
      .attr('class', 'label')
      .attr('text-anchor', 'middle')
      .attr('transform', d => {
        const angle = xScale(d.label) + xScale.bandwidth() / 2;
        const r = outerRadius + 20;
        const x = Math.sin(angle) * r;
        const y = -Math.cos(angle) * r;
        return `translate(${x}, ${y})`;
      })
      .attr('fill', theme.fg)
      .style('font-size', '11px')
      .text(d => d.label);

    // ホバー
    bars.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('opacity', 0.8);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.label}</strong><br>${D3Base.formatNumber(d.value)}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('opacity', 1);

        tooltip.style('opacity', 0);
      });

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * Word Cloud（ワードクラウド）
   * @param {string} selector
   * @param {Array} data - [{ text, size }]
   * @param {Object} options
   */
  createWordCloud(selector, data, options = {}) {
    const {
      width = 600,
      height = 400,
      animate = true,
      fontFamily = '"Noto Sans JP", sans-serif',
      minFontSize = 12,
      maxFontSize = 60
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart word-cloud');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // サイズスケール
    const sizeExtent = d3.extent(data, d => d.size);
    const fontScale = d3.scaleLinear()
      .domain(sizeExtent)
      .range([minFontSize, maxFontSize]);

    // シンプルなスパイラル配置（d3-cloudの代替）
    const words = data.map((d, i) => {
      const fontSize = fontScale(d.size);
      const angle = i * 137.5 * Math.PI / 180; // 黄金角
      const radius = Math.sqrt(i) * 30;
      return {
        ...d,
        fontSize,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        rotate: (Math.random() - 0.5) * 30
      };
    });

    // 単語描画
    const wordElements = g.selectAll('.word')
      .data(words)
      .enter()
      .append('text')
      .attr('class', 'word')
      .attr('text-anchor', 'middle')
      .attr('transform', d => `translate(${d.x}, ${d.y}) rotate(${d.rotate})`)
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .style('font-size', d => `${d.fontSize}px`)
      .style('font-family', fontFamily)
      .style('font-weight', 'bold')
      .text(d => d.text);

    // ホバー
    wordElements.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .style('font-size', `${d.fontSize * 1.2}px`);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.text}</strong><br>スコア: ${d.size}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .style('font-size', `${d.fontSize}px`);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      wordElements
        .attr('opacity', 0)
        .transition()
        .duration(500)
        .delay((d, i) => i * 30)
        .attr('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * Arc Diagram（弧線図）
   * @param {string} selector
   * @param {Object} data - { nodes: [{id}], links: [{source, target, value?}] }
   * @param {Object} options
   */
  createArcDiagram(selector, data, options = {}) {
    const {
      width = 800,
      height = 400,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 60, right: 40, bottom: 60, left: 40 };
    const innerWidth = width - margin.left - margin.right;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart arc-diagram');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${height / 2})`);

    // ノード配置
    const xScale = d3.scalePoint()
      .domain(data.nodes.map(d => d.id))
      .range([0, innerWidth]);

    // ノード描画
    const nodes = g.selectAll('.node')
      .data(data.nodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${xScale(d.id)}, 0)`);

    nodes.append('circle')
      .attr('r', 8)
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2);

    nodes.append('text')
      .attr('y', 25)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.fg)
      .style('font-size', '11px')
      .text(d => d.id);

    // アーク（弧）描画
    const arcs = g.selectAll('.arc')
      .data(data.links)
      .enter()
      .append('path')
      .attr('class', 'arc')
      .attr('d', d => {
        const sourceX = xScale(d.source);
        const targetX = xScale(d.target);
        const midX = (sourceX + targetX) / 2;
        const arcHeight = Math.abs(targetX - sourceX) / 2;
        return `M ${sourceX} 0 Q ${midX} ${-arcHeight} ${targetX} 0`;
      })
      .attr('fill', 'none')
      .attr('stroke', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke-width', d => Math.sqrt(d.value || 1) * 2)
      .attr('stroke-opacity', 0.6);

    // ホバー
    arcs.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('stroke-opacity', 1)
          .attr('stroke-width', d => Math.sqrt(d.value || 1) * 3);

        tooltip
          .style('opacity', 1)
          .html(`${d.source} ↔ ${d.target}${d.value ? `<br>値: ${d.value}` : ''}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('stroke-opacity', 0.6)
          .attr('stroke-width', d => Math.sqrt(d.value || 1) * 2);

        tooltip.style('opacity', 0);
      });

    // エントリーアニメーション
    if (animate) {
      arcs.each(function() {
        D3Base.animateEntry(d3.select(this), 'drawPath');
      });

      nodes.style('opacity', 0)
        .transition()
        .duration(400)
        .delay((d, i) => i * 50)
        .style('opacity', 1);
    }

    D3Base.makeResponsive(svg);
    return svg;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { D3Advanced };
}
