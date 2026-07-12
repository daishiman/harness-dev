/**
 * D3.js Chart Components
 *
 * グラフ系: 棒グラフ、円グラフ、折れ線グラフ、レーダー、ゲージ、バブル、ヒートマップ
 * データバインディング、トランジション対応
 */

const D3Charts = {
  /**
   * 縦棒グラフ
   * @param {string} selector
   * @param {Array} data - [{ label, value, highlight? }]
   * @param {Object} options
   */
  createBarChart(selector, data, options = {}) {
    const {
      width = 700,
      height = 400,
      animate = true,
      showGrid = true,
      showValues = true,
      xLabel = '',
      yLabel = ''
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 30, right: 30, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart bar-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // スケール
    const xScale = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([0, innerWidth])
      .padding(0.3);

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.value) * 1.1])
      .range([innerHeight, 0]);

    // グリッド
    if (showGrid) {
      g.append('g')
        .attr('class', 'grid')
        .call(d3.axisLeft(yScale)
          .tickSize(-innerWidth)
          .tickFormat(''))
        .selectAll('line')
        .attr('stroke', theme.border)
        .attr('stroke-dasharray', '3,3');
    }

    // X軸
    g.append('g')
      .attr('class', 'axis x-axis')
      .attr('transform', `translate(0, ${innerHeight})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .attr('fill', theme.fg)
      .style('font-size', '12px');

    // Y軸
    g.append('g')
      .attr('class', 'axis y-axis')
      .call(d3.axisLeft(yScale).tickFormat(d => D3Base.formatNumber(d)))
      .selectAll('text')
      .attr('fill', theme.fg)
      .style('font-size', '12px');

    // 軸ラベル
    D3Base.addAxisLabels(g, { xLabel, yLabel, width: innerWidth, height: innerHeight, theme });

    // バー
    const bars = g.selectAll('.bar')
      .data(data)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', d => xScale(d.label))
      .attr('width', xScale.bandwidth())
      .attr('fill', (d, i) => d.highlight ? accentPalette[1] : accentPalette[i % accentPalette.length])
      .attr('rx', 4);

    if (animate) {
      bars.attr('y', innerHeight)
        .attr('height', 0)
        .transition()
        .duration(800)
        .delay((d, i) => i * 100)
        .attr('y', d => yScale(d.value))
        .attr('height', d => innerHeight - yScale(d.value));
    } else {
      bars.attr('y', d => yScale(d.value))
        .attr('height', d => innerHeight - yScale(d.value));
    }

    // 値ラベル
    if (showValues) {
      const valueLabels = g.selectAll('.value-label')
        .data(data)
        .enter()
        .append('text')
        .attr('class', 'value-label')
        .attr('x', d => xScale(d.label) + xScale.bandwidth() / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', theme.fg)
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .text(d => D3Base.formatNumber(d.value));

      if (animate) {
        valueLabels.attr('y', innerHeight)
          .attr('opacity', 0)
          .transition()
          .duration(800)
          .delay((d, i) => i * 100)
          .attr('y', d => yScale(d.value) - 8)
          .attr('opacity', 1);
      } else {
        valueLabels.attr('y', d => yScale(d.value) - 8);
      }
    }

    // ホバー＆ツールチップ
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
   * 円グラフ（ドーナツ対応）
   * @param {string} selector
   * @param {Array} data - [{ label, value }]
   * @param {Object} options
   */
  createPieChart(selector, data, options = {}) {
    const {
      width = 500,
      height = 500,
      innerRadius = 0, // 0 = 円グラフ、> 0 = ドーナツ
      animate = true,
      showLabels = true,
      showLegend = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const radius = Math.min(width, height) / 2 - 40;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart pie-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // パイレイアウト
    const pie = d3.pie()
      .value(d => d.value)
      .sort(null);

    // アークジェネレータ
    const arc = d3.arc()
      .innerRadius(innerRadius)
      .outerRadius(radius);

    const arcHover = d3.arc()
      .innerRadius(innerRadius)
      .outerRadius(radius + 10);

    // パス描画
    const paths = g.selectAll('.arc')
      .data(pie(data))
      .enter()
      .append('path')
      .attr('class', 'arc')
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2);

    if (animate) {
      paths.attr('d', d3.arc().innerRadius(innerRadius).outerRadius(0))
        .transition()
        .duration(800)
        .attrTween('d', function(d) {
          const interpolate = d3.interpolate({ startAngle: d.startAngle, endAngle: d.startAngle }, d);
          return t => arc(interpolate(t));
        });
    } else {
      paths.attr('d', arc);
    }

    // ラベル
    if (showLabels) {
      const labelArc = d3.arc()
        .innerRadius(radius * 0.6)
        .outerRadius(radius * 0.6);

      g.selectAll('.label')
        .data(pie(data))
        .enter()
        .append('text')
        .attr('class', 'label')
        .attr('transform', d => `translate(${labelArc.centroid(d)})`)
        .attr('text-anchor', 'middle')
        .attr('fill', '#fff')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .text(d => {
          const total = d3.sum(data, d => d.value);
          const percent = ((d.data.value / total) * 100).toFixed(0);
          return percent >= 5 ? `${percent}%` : '';
        })
        .attr('opacity', animate ? 0 : 1)
        .transition()
        .delay(animate ? 600 : 0)
        .duration(300)
        .attr('opacity', 1);
    }

    // 凡例
    if (showLegend) {
      const total = d3.sum(data, d => d.value);
      const legendItems = data.map((d, i) => ({
        label: `${d.label} (${((d.value / total) * 100).toFixed(1)}%)`,
        color: accentPalette[i % accentPalette.length]
      }));

      D3Base.createLegend(svg, legendItems, {
        x: 20,
        y: height - 30,
        direction: 'horizontal',
        itemWidth: 150
      });
    }

    // ホバー＆ツールチップ
    paths.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('d', arcHover);

        const total = d3.sum(data, d => d.value);
        const percent = ((d.data.value / total) * 100).toFixed(1);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.data.label}</strong><br>${D3Base.formatNumber(d.data.value)} (${percent}%)`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('d', arc);

        tooltip.style('opacity', 0);
      });

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * 折れ線グラフ
   * @param {string} selector
   * @param {Array} data - [{ label, value }] または複数系列 [{ name, values: [{label, value}] }]
   * @param {Object} options
   */
  createLineChart(selector, data, options = {}) {
    const {
      width = 700,
      height = 400,
      animate = true,
      showDots = true,
      showArea = false,
      showGrid = true,
      curved = true,
      xLabel = '',
      yLabel = ''
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 30, right: 30, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // データ形式の正規化（単一系列 → 複数系列形式）
    const series = Array.isArray(data[0]?.values)
      ? data
      : [{ name: 'データ', values: data }];

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart line-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // 全データポイント
    const allValues = series.flatMap(s => s.values);

    // スケール
    const xScale = d3.scalePoint()
      .domain(allValues.map(d => d.label))
      .range([0, innerWidth]);

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(allValues, d => d.value) * 1.1])
      .range([innerHeight, 0]);

    // グリッド
    if (showGrid) {
      g.append('g')
        .attr('class', 'grid')
        .call(d3.axisLeft(yScale)
          .tickSize(-innerWidth)
          .tickFormat(''))
        .selectAll('line')
        .attr('stroke', theme.border)
        .attr('stroke-dasharray', '3,3');
    }

    // X軸
    g.append('g')
      .attr('class', 'axis x-axis')
      .attr('transform', `translate(0, ${innerHeight})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .attr('fill', theme.fg)
      .style('font-size', '12px');

    // Y軸
    g.append('g')
      .attr('class', 'axis y-axis')
      .call(d3.axisLeft(yScale).tickFormat(d => D3Base.formatNumber(d)))
      .selectAll('text')
      .attr('fill', theme.fg)
      .style('font-size', '12px');

    // 軸ラベル
    D3Base.addAxisLabels(g, { xLabel, yLabel, width: innerWidth, height: innerHeight, theme });

    // ラインジェネレータ
    const lineGenerator = d3.line()
      .x(d => xScale(d.label))
      .y(d => yScale(d.value));

    if (curved) {
      lineGenerator.curve(d3.curveMonotoneX);
    }

    // エリアジェネレータ
    const areaGenerator = d3.area()
      .x(d => xScale(d.label))
      .y0(innerHeight)
      .y1(d => yScale(d.value));

    if (curved) {
      areaGenerator.curve(d3.curveMonotoneX);
    }

    // 各系列描画
    series.forEach((s, i) => {
      const color = accentPalette[i % accentPalette.length];

      // エリア
      if (showArea) {
        g.append('path')
          .datum(s.values)
          .attr('class', 'area')
          .attr('d', areaGenerator)
          .attr('fill', color)
          .attr('fill-opacity', 0.15);
      }

      // ライン
      const path = g.append('path')
        .datum(s.values)
        .attr('class', 'line')
        .attr('d', lineGenerator)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 3)
        .attr('stroke-linecap', 'round');

      if (animate) {
        D3Base.animateEntry(path, 'drawPath');
      }

      // ドット
      if (showDots) {
        const dots = g.selectAll(`.dot-${i}`)
          .data(s.values)
          .enter()
          .append('circle')
          .attr('class', `dot dot-${i}`)
          .attr('cx', d => xScale(d.label))
          .attr('cy', d => yScale(d.value))
          .attr('fill', color)
          .attr('stroke', theme.bg)
          .attr('stroke-width', 2);

        if (animate) {
          dots.attr('r', 0)
            .transition()
            .duration(400)
            .delay((d, j) => 600 + j * 50)
            .attr('r', 5);
        } else {
          dots.attr('r', 5);
        }

        // ホバー
        dots.style('cursor', 'pointer')
          .on('mouseenter', function(event, d) {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('r', 8);

            tooltip
              .style('opacity', 1)
              .html(`<strong>${d.label}</strong><br>${s.name}: ${D3Base.formatNumber(d.value)}`)
              .style('left', (event.pageX + 10) + 'px')
              .style('top', (event.pageY - 10) + 'px');
          })
          .on('mouseleave', function() {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('r', 5);

            tooltip.style('opacity', 0);
          });
      }
    });

    // 凡例（複数系列時）
    if (series.length > 1) {
      const legendItems = series.map((s, i) => ({
        label: s.name,
        color: accentPalette[i % accentPalette.length]
      }));

      D3Base.createLegend(svg, legendItems, {
        x: margin.left,
        y: 10,
        direction: 'horizontal'
      });
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * レーダーチャート
   * @param {string} selector
   * @param {Array} data - [{ axis, value }] または複数系列
   * @param {Object} options
   */
  createRadarChart(selector, data, options = {}) {
    const {
      width = 500,
      height = 500,
      levels = 5,
      animate = true
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const radius = Math.min(width, height) / 2 - 60;

    // データ正規化
    const series = Array.isArray(data[0]?.values)
      ? data
      : [{ name: 'データ', values: data }];

    const axes = series[0].values.map(d => d.axis);
    const maxValue = d3.max(series.flatMap(s => s.values), d => d.value);

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart radar-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // 角度計算
    const angleSlice = (2 * Math.PI) / axes.length;

    // レベル円
    for (let level = 1; level <= levels; level++) {
      const r = (radius / levels) * level;

      g.append('circle')
        .attr('r', r)
        .attr('fill', 'none')
        .attr('stroke', theme.border)
        .attr('stroke-opacity', 0.5);

      // レベルラベル
      g.append('text')
        .attr('x', 5)
        .attr('y', -r)
        .attr('fill', theme.fgDim)
        .style('font-size', '10px')
        .text(((maxValue / levels) * level).toFixed(0));
    }

    // 軸線と軸ラベル
    axes.forEach((axis, i) => {
      const angle = angleSlice * i - Math.PI / 2;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;

      g.append('line')
        .attr('x1', 0)
        .attr('y1', 0)
        .attr('x2', x)
        .attr('y2', y)
        .attr('stroke', theme.border)
        .attr('stroke-opacity', 0.5);

      g.append('text')
        .attr('x', Math.cos(angle) * (radius + 20))
        .attr('y', Math.sin(angle) * (radius + 20))
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .attr('fill', theme.fg)
        .style('font-size', '12px')
        .text(axis);
    });

    // データ系列描画
    series.forEach((s, seriesIndex) => {
      const color = accentPalette[seriesIndex % accentPalette.length];

      const points = s.values.map((d, i) => {
        const angle = angleSlice * i - Math.PI / 2;
        const r = (d.value / maxValue) * radius;
        return { x: Math.cos(angle) * r, y: Math.sin(angle) * r, data: d };
      });

      // エリア
      const area = g.append('polygon')
        .attr('points', points.map(p => `${p.x},${p.y}`).join(' '))
        .attr('fill', color)
        .attr('fill-opacity', 0.2)
        .attr('stroke', color)
        .attr('stroke-width', 2);

      if (animate) {
        area.attr('opacity', 0)
          .transition()
          .duration(600)
          .delay(seriesIndex * 200)
          .attr('opacity', 1);
      }

      // ドット
      const dots = g.selectAll(`.dot-${seriesIndex}`)
        .data(points)
        .enter()
        .append('circle')
        .attr('class', `dot dot-${seriesIndex}`)
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('fill', color)
        .attr('stroke', theme.bg)
        .attr('stroke-width', 2);

      if (animate) {
        dots.attr('r', 0)
          .transition()
          .duration(400)
          .delay(seriesIndex * 200 + 400)
          .attr('r', 4);
      } else {
        dots.attr('r', 4);
      }

      // ホバー
      dots.style('cursor', 'pointer')
        .on('mouseenter', function(event, d) {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', 7);

          tooltip
            .style('opacity', 1)
            .html(`<strong>${d.data.axis}</strong><br>${s.name}: ${d.data.value}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseleave', function() {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', 4);

          tooltip.style('opacity', 0);
        });
    });

    // 凡例
    if (series.length > 1) {
      const legendItems = series.map((s, i) => ({
        label: s.name,
        color: accentPalette[i % accentPalette.length]
      }));

      D3Base.createLegend(svg, legendItems, {
        x: 20,
        y: height - 30,
        direction: 'horizontal'
      });
    }

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * ゲージチャート
   * @param {string} selector
   * @param {number} value - 現在値
   * @param {Object} options
   */
  createGaugeChart(selector, value, options = {}) {
    const {
      width = 300,
      height = 200,
      min = 0,
      max = 100,
      label = '',
      unit = '',
      animate = true,
      thresholds = [] // [{ value, color }]
    } = options;

    const theme = D3Base.getTheme();

    const radius = Math.min(width, height * 2) / 2 - 20;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart gauge-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height - 20})`);

    // 背景弧
    const bgArc = d3.arc()
      .innerRadius(radius - 20)
      .outerRadius(radius)
      .startAngle(-Math.PI / 2)
      .endAngle(Math.PI / 2);

    g.append('path')
      .attr('d', bgArc())
      .attr('fill', theme.surface);

    // 値弧
    const valueAngle = ((value - min) / (max - min)) * Math.PI - Math.PI / 2;

    const valueArc = d3.arc()
      .innerRadius(radius - 20)
      .outerRadius(radius)
      .startAngle(-Math.PI / 2)
      .endAngle(valueAngle);

    // 色決定（閾値ベース）
    let color = accentPalette[0];
    if (thresholds.length > 0) {
      for (const t of thresholds.sort((a, b) => b.value - a.value)) {
        if (value >= t.value) {
          color = t.color;
          break;
        }
      }
    }

    const valuePath = g.append('path')
      .attr('fill', color);

    if (animate) {
      valuePath.attrTween('d', function() {
        const interpolate = d3.interpolate(-Math.PI / 2, valueAngle);
        return t => valueArc.endAngle(interpolate(t))();
      })
      .transition()
      .duration(1000)
      .ease(d3.easeQuadOut);
    } else {
      valuePath.attr('d', valueArc());
    }

    // 値テキスト
    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('y', -20)
      .attr('fill', theme.fg)
      .style('font-size', '32px')
      .style('font-weight', 'bold')
      .text(D3Base.formatNumber(value) + unit);

    // ラベル
    if (label) {
      g.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 10)
        .attr('fill', theme.fgDim)
        .style('font-size', '14px')
        .text(label);
    }

    // 最小・最大値
    g.append('text')
      .attr('x', -radius + 10)
      .attr('y', 5)
      .attr('fill', theme.fgDim)
      .style('font-size', '11px')
      .text(min);

    g.append('text')
      .attr('x', radius - 10)
      .attr('y', 5)
      .attr('text-anchor', 'end')
      .attr('fill', theme.fgDim)
      .style('font-size', '11px')
      .text(max);

    D3Base.makeResponsive(svg);
    return svg;
  },

  /**
   * バブルチャート
   * @param {string} selector
   * @param {Array} data - [{ x, y, size, label, group? }]
   * @param {Object} options
   */
  createBubbleChart(selector, data, options = {}) {
    const {
      width = 700,
      height = 500,
      animate = true,
      xLabel = '',
      yLabel = ''
    } = options;

    const theme = D3Base.getTheme();
    const tooltip = D3Base.createTooltip();

    const margin = { top: 30, right: 30, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(selector)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('class', 'd3-chart bubble-chart');

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left}, ${margin.top})`);

    // スケール
    const xScale = d3.scaleLinear()
      .domain(d3.extent(data, d => d.x))
      .range([0, innerWidth])
      .nice();

    const yScale = d3.scaleLinear()
      .domain(d3.extent(data, d => d.y))
      .range([innerHeight, 0])
      .nice();

    const sizeScale = d3.scaleSqrt()
      .domain([0, d3.max(data, d => d.size)])
      .range([5, 40]);

    // 軸
    g.append('g')
      .attr('class', 'axis x-axis')
      .attr('transform', `translate(0, ${innerHeight})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .attr('fill', theme.fg);

    g.append('g')
      .attr('class', 'axis y-axis')
      .call(d3.axisLeft(yScale))
      .selectAll('text')
      .attr('fill', theme.fg);

    // 軸ラベル
    D3Base.addAxisLabels(g, { xLabel, yLabel, width: innerWidth, height: innerHeight, theme });

    // バブル
    const bubbles = g.selectAll('.bubble')
      .data(data)
      .enter()
      .append('circle')
      .attr('class', 'bubble')
      .attr('cx', d => xScale(d.x))
      .attr('cy', d => yScale(d.y))
      .attr('fill', (d, i) => accentPalette[(d.group || i) % accentPalette.length])
      .attr('fill-opacity', 0.7)
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2);

    if (animate) {
      bubbles.attr('r', 0)
        .transition()
        .duration(800)
        .delay((d, i) => i * 50)
        .attr('r', d => sizeScale(d.size));
    } else {
      bubbles.attr('r', d => sizeScale(d.size));
    }

    // ホバー＆ツールチップ
    bubbles.style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill-opacity', 1);

        tooltip
          .style('opacity', 1)
          .html(`<strong>${d.label || ''}</strong><br>X: ${d.x}<br>Y: ${d.y}<br>Size: ${d.size}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseleave', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill-opacity', 0.7);

        tooltip.style('opacity', 0);
      });

    D3Base.makeResponsive(svg);
    return svg;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { D3Charts };
}
