/**
 * D3 Extended Components - 拡張図解コンポーネント
 *
 * 追加図解タイプ:
 * - ウォーターフォール: 増減累積表示
 * - ドーナツチャート: 中央KPI付き円グラフ
 * - ブレットチャート: KPI進捗表示
 * - スロープチャート: 2時点比較
 * - バタフライチャート: 左右対称比較
 * - ロリポップチャート: 視認性向上棒グラフ
 * - カレンダーヒートマップ: 日別活動表示
 * - パラレルコーディネート: 多変量比較
 * - デンドログラム: クラスタリング表示
 * - アイソタイプ: アイコン数量表現
 *
 * 依存: D3Base (base.js)
 */

const D3Extended = {
  /**
   * ウォーターフォールチャート - 増減の累積表示
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{label, value, type: 'increase'|'decrease'|'total'}]
   * @param {Object} options - オプション
   */
  createWaterfall(container, data, options = {}) {
    const {
      width = 700,
      height = 400
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 40, right: 40, bottom: 60, left: 80 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);
    const tooltip = D3Base.createTooltip(container);

    // 累積値を計算
    let cumulative = 0;
    const processedData = data.map((d, i) => {
      const start = d.type === 'total' ? 0 : cumulative;
      const end = d.type === 'total' ? d.value : cumulative + d.value;
      cumulative = end;
      return { ...d, start, end };
    });

    const x = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([0, innerWidth])
      .padding(0.3);

    const maxVal = d3.max(processedData, d => Math.max(d.start, d.end));
    const minVal = d3.min(processedData, d => Math.min(d.start, d.end));

    const y = d3.scaleLinear()
      .domain([Math.min(0, minVal), maxVal * 1.1])
      .range([innerHeight, 0]);

    // 軸
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
      .attr('fill', theme.muted)
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'end');

    g.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
      .attr('fill', theme.muted);

    // ゼロライン
    g.append('line')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', y(0))
      .attr('y2', y(0))
      .attr('stroke', theme.border)
      .attr('stroke-dasharray', '4,4');

    // バー
    const bars = g.selectAll('.bar')
      .data(processedData)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', d => x(d.label))
      .attr('width', x.bandwidth())
      .attr('y', d => y(Math.max(d.start, d.end)))
      .attr('height', 0)
      .attr('fill', d => {
        if (d.type === 'total') return theme.accent1;
        return d.value >= 0 ? theme.accent3 : theme.accent2;
      });

    bars.transition()
      .delay((d, i) => i * 80)
      .duration(500)
      .attr('height', d => Math.abs(y(d.start) - y(d.end)));

    // コネクタライン
    g.selectAll('.connector')
      .data(processedData.slice(0, -1))
      .enter()
      .append('line')
      .attr('class', 'connector')
      .attr('x1', d => x(d.label) + x.bandwidth())
      .attr('x2', (d, i) => x(processedData[i + 1].label))
      .attr('y1', d => y(d.end))
      .attr('y2', d => y(d.end))
      .attr('stroke', theme.muted)
      .attr('stroke-dasharray', '2,2');

    // ツールチップ
    bars.on('mouseenter', function(event, d) {
      const sign = d.value >= 0 ? '+' : '';
      tooltip
        .html(`<strong>${d.label}</strong><br/>値: ${sign}${D3Base.formatNumber(d.value)}<br/>累計: ${D3Base.formatNumber(d.end)}`)
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 10) + 'px')
        .classed('visible', true);
    })
    .on('mouseleave', () => tooltip.classed('visible', false));

    return { svg };
  },

  /**
   * ドーナツチャート - 中央にKPI表示
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{label, value}]
   * @param {Object} options - {centerLabel, centerValue}
   */
  createDonutChart(container, data, options = {}) {
    const {
      width = 500,
      height = 400,
      innerRadiusRatio = 0.6,
      centerLabel = '',
      centerValue = ''
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 40, right: 40, bottom: 40, left: 40 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);
    const tooltip = D3Base.createTooltip(container);

    const radius = Math.min(innerWidth, innerHeight) / 2;
    const innerRadius = radius * innerRadiusRatio;

    const centerG = g.append('g')
      .attr('transform', `translate(${innerWidth/2},${innerHeight/2})`);

    const pie = d3.pie().value(d => d.value).sort(null);
    const arc = d3.arc().innerRadius(innerRadius).outerRadius(radius);

    const slices = centerG.selectAll('.slice')
      .data(pie(data))
      .enter()
      .append('path')
      .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
      .attr('stroke', theme.bg)
      .attr('stroke-width', 2);

    slices.transition()
      .duration(800)
      .attrTween('d', function(d) {
        const interpolate = d3.interpolate({ startAngle: 0, endAngle: 0 }, d);
        return t => arc(interpolate(t));
      });

    // 中央テキスト
    if (centerValue) {
      centerG.append('text')
        .attr('y', -10)
        .attr('text-anchor', 'middle')
        .attr('fill', theme.fg)
        .style('font-size', '32px')
        .style('font-weight', '700')
        .text(centerValue);
    }

    if (centerLabel) {
      centerG.append('text')
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .attr('fill', theme.muted)
        .style('font-size', '14px')
        .text(centerLabel);
    }

    // ツールチップ
    const total = d3.sum(data, d => d.value);
    slices.on('mouseenter', function(event, d) {
      const percent = ((d.data.value / total) * 100).toFixed(1);
      tooltip
        .html(`<strong>${d.data.label}</strong><br/>値: ${D3Base.formatNumber(d.data.value)}<br/>割合: ${percent}%`)
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 10) + 'px')
        .classed('visible', true);
    })
    .on('mouseleave', () => tooltip.classed('visible', false));

    return { svg };
  },

  /**
   * ブレットチャート - KPI進捗表示
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{label, value, target, ranges: [poor, ok, good]}]
   * @param {Object} options - オプション
   */
  createBulletChart(container, data, options = {}) {
    const {
      width = 600,
      height = 50 * data.length + 60
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 30, right: 40, bottom: 30, left: 120 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);

    const rowHeight = innerHeight / data.length;

    data.forEach((d, i) => {
      const rowG = g.append('g')
        .attr('transform', `translate(0,${i * rowHeight})`);

      const maxVal = Math.max(d.target, d.value, ...d.ranges);
      const x = d3.scaleLinear()
        .domain([0, maxVal])
        .range([0, innerWidth]);

      // 範囲バー（背景）
      const rangeColors = [theme.surface, theme.border, theme.muted];
      d.ranges.forEach((range, ri) => {
        rowG.append('rect')
          .attr('x', 0)
          .attr('y', rowHeight * 0.15)
          .attr('width', x(range))
          .attr('height', rowHeight * 0.7)
          .attr('fill', rangeColors[ri] || theme.surface)
          .attr('opacity', 0.5);
      });

      // 実績バー
      rowG.append('rect')
        .attr('x', 0)
        .attr('y', rowHeight * 0.35)
        .attr('width', 0)
        .attr('height', rowHeight * 0.3)
        .attr('fill', d.value >= d.target ? theme.accent3 : theme.accent1)
        .transition()
        .duration(600)
        .delay(i * 100)
        .attr('width', x(d.value));

      // 目標マーカー
      rowG.append('line')
        .attr('x1', x(d.target))
        .attr('x2', x(d.target))
        .attr('y1', rowHeight * 0.2)
        .attr('y2', rowHeight * 0.8)
        .attr('stroke', theme.accent2)
        .attr('stroke-width', 3);

      // ラベル
      rowG.append('text')
        .attr('x', -10)
        .attr('y', rowHeight / 2)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'middle')
        .attr('fill', theme.fg)
        .style('font-size', '12px')
        .text(d.label);
    });

    return { svg };
  },

  /**
   * スロープチャート - 2時点間の変化比較
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{label, start, end}]
   * @param {Object} options - {startLabel, endLabel}
   */
  createSlopeChart(container, data, options = {}) {
    const {
      width = 500,
      height = 400,
      startLabel = '開始',
      endLabel = '終了'
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 50, right: 100, bottom: 40, left: 100 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);

    const allValues = data.flatMap(d => [d.start, d.end]);
    const y = d3.scaleLinear()
      .domain([d3.min(allValues) * 0.9, d3.max(allValues) * 1.1])
      .range([innerHeight, 0]);

    // 軸ラベル
    g.append('text')
      .attr('x', 0)
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.fg)
      .style('font-size', '14px')
      .style('font-weight', '600')
      .text(startLabel);

    g.append('text')
      .attr('x', innerWidth)
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.fg)
      .style('font-size', '14px')
      .style('font-weight', '600')
      .text(endLabel);

    // スロープライン
    data.forEach((d, i) => {
      const color = accentPalette[i % accentPalette.length];
      const isIncrease = d.end > d.start;

      // ライン
      const line = g.append('line')
        .attr('x1', 0)
        .attr('y1', y(d.start))
        .attr('x2', 0)
        .attr('y2', y(d.start))
        .attr('stroke', color)
        .attr('stroke-width', 2);

      line.transition()
        .duration(800)
        .delay(i * 100)
        .attr('x2', innerWidth)
        .attr('y2', y(d.end));

      // 開始点
      g.append('circle')
        .attr('cx', 0)
        .attr('cy', y(d.start))
        .attr('r', 6)
        .attr('fill', color);

      // 終了点
      g.append('circle')
        .attr('cx', innerWidth)
        .attr('cy', y(d.end))
        .attr('r', 6)
        .attr('fill', color);

      // ラベル（左）
      g.append('text')
        .attr('x', -10)
        .attr('y', y(d.start))
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'middle')
        .attr('fill', theme.fg)
        .style('font-size', '11px')
        .text(`${d.label}: ${d.start}`);

      // ラベル（右）
      g.append('text')
        .attr('x', innerWidth + 10)
        .attr('y', y(d.end))
        .attr('dominant-baseline', 'middle')
        .attr('fill', theme.fg)
        .style('font-size', '11px')
        .text(`${d.end} ${isIncrease ? '↑' : '↓'}`);
    });

    return { svg };
  },

  /**
   * バタフライチャート - 左右対称比較（人口ピラミッド型）
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{label, left, right}]
   * @param {Object} options - {leftLabel, rightLabel}
   */
  createButterflyChart(container, data, options = {}) {
    const {
      width = 600,
      height = 400,
      leftLabel = '左',
      rightLabel = '右'
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 50, right: 40, bottom: 40, left: 40 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);

    const midPoint = innerWidth / 2;
    const maxVal = d3.max(data, d => Math.max(d.left, d.right));

    const xLeft = d3.scaleLinear()
      .domain([0, maxVal])
      .range([midPoint - 20, 0]);

    const xRight = d3.scaleLinear()
      .domain([0, maxVal])
      .range([midPoint + 20, innerWidth]);

    const y = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([0, innerHeight])
      .padding(0.2);

    // ラベル
    g.append('text')
      .attr('x', midPoint / 2)
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.accent1)
      .style('font-size', '14px')
      .style('font-weight', '600')
      .text(leftLabel);

    g.append('text')
      .attr('x', midPoint + (innerWidth - midPoint) / 2)
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('fill', theme.accent2)
      .style('font-size', '14px')
      .style('font-weight', '600')
      .text(rightLabel);

    // 中央ラベル
    g.selectAll('.center-label')
      .data(data)
      .enter()
      .append('text')
      .attr('x', midPoint)
      .attr('y', d => y(d.label) + y.bandwidth() / 2)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .attr('fill', theme.fg)
      .style('font-size', '11px')
      .text(d => d.label);

    // 左バー
    g.selectAll('.bar-left')
      .data(data)
      .enter()
      .append('rect')
      .attr('x', d => xLeft(d.left))
      .attr('y', d => y(d.label))
      .attr('width', 0)
      .attr('height', y.bandwidth())
      .attr('fill', theme.accent1)
      .transition()
      .delay((d, i) => i * 50)
      .duration(500)
      .attr('width', d => midPoint - 20 - xLeft(d.left));

    // 右バー
    g.selectAll('.bar-right')
      .data(data)
      .enter()
      .append('rect')
      .attr('x', midPoint + 20)
      .attr('y', d => y(d.label))
      .attr('width', 0)
      .attr('height', y.bandwidth())
      .attr('fill', theme.accent2)
      .transition()
      .delay((d, i) => i * 50)
      .duration(500)
      .attr('width', d => xRight(d.right) - midPoint - 20);

    return { svg };
  },

  /**
   * ロリポップチャート - 視認性向上棒グラフ
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{label, value}]
   * @param {Object} options - オプション
   */
  createLollipopChart(container, data, options = {}) {
    const {
      width = 600,
      height = 400,
      horizontal = true
    } = options;

    const theme = D3Base.getTheme();
    const margin = horizontal
      ? { top: 40, right: 40, bottom: 40, left: 120 }
      : { top: 40, right: 40, bottom: 80, left: 60 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);
    const tooltip = D3Base.createTooltip(container);

    if (horizontal) {
      const x = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.value) * 1.1])
        .range([0, innerWidth]);

      const y = d3.scaleBand()
        .domain(data.map(d => d.label))
        .range([0, innerHeight])
        .padding(0.5);

      // 軸
      g.append('g')
        .call(d3.axisLeft(y))
        .selectAll('text')
        .attr('fill', theme.muted);

      // ライン
      g.selectAll('.line')
        .data(data)
        .enter()
        .append('line')
        .attr('x1', 0)
        .attr('x2', 0)
        .attr('y1', d => y(d.label) + y.bandwidth() / 2)
        .attr('y2', d => y(d.label) + y.bandwidth() / 2)
        .attr('stroke', theme.border)
        .attr('stroke-width', 2)
        .transition()
        .delay((d, i) => i * 50)
        .duration(500)
        .attr('x2', d => x(d.value));

      // 円
      g.selectAll('.dot')
        .data(data)
        .enter()
        .append('circle')
        .attr('cx', 0)
        .attr('cy', d => y(d.label) + y.bandwidth() / 2)
        .attr('r', 8)
        .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
        .transition()
        .delay((d, i) => i * 50)
        .duration(500)
        .attr('cx', d => x(d.value));

    } else {
      const x = d3.scaleBand()
        .domain(data.map(d => d.label))
        .range([0, innerWidth])
        .padding(0.5);

      const y = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.value) * 1.1])
        .range([innerHeight, 0]);

      // 軸
      g.append('g')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(d3.axisBottom(x))
        .selectAll('text')
        .attr('fill', theme.muted)
        .attr('transform', 'rotate(-45)')
        .style('text-anchor', 'end');

      g.append('g')
        .call(d3.axisLeft(y))
        .selectAll('text')
        .attr('fill', theme.muted);

      // ライン
      g.selectAll('.line')
        .data(data)
        .enter()
        .append('line')
        .attr('x1', d => x(d.label) + x.bandwidth() / 2)
        .attr('x2', d => x(d.label) + x.bandwidth() / 2)
        .attr('y1', innerHeight)
        .attr('y2', innerHeight)
        .attr('stroke', theme.border)
        .attr('stroke-width', 2)
        .transition()
        .delay((d, i) => i * 50)
        .duration(500)
        .attr('y2', d => y(d.value));

      // 円
      g.selectAll('.dot')
        .data(data)
        .enter()
        .append('circle')
        .attr('cx', d => x(d.label) + x.bandwidth() / 2)
        .attr('cy', innerHeight)
        .attr('r', 8)
        .attr('fill', (d, i) => accentPalette[i % accentPalette.length])
        .transition()
        .delay((d, i) => i * 50)
        .duration(500)
        .attr('cy', d => y(d.value));
    }

    return { svg };
  },

  /**
   * カレンダーヒートマップ - 日別活動表示
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{date: 'YYYY-MM-DD', value}]
   * @param {Object} options - オプション
   */
  createCalendarHeatmap(container, data, options = {}) {
    const {
      width = 900,
      height = 200,
      cellSize = 15
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 40, right: 40, bottom: 20, left: 40 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);
    const tooltip = D3Base.createTooltip(container);

    const parseDate = d3.timeParse('%Y-%m-%d');
    const formatDate = d3.timeFormat('%Y-%m-%d');
    const formatMonth = d3.timeFormat('%b');

    const dates = data.map(d => parseDate(d.date));
    const minDate = d3.min(dates);
    const maxDate = d3.max(dates);

    const dataMap = new Map(data.map(d => [d.date, d.value]));
    const maxVal = d3.max(data, d => d.value);

    const colorScale = d3.scaleSequential()
      .domain([0, maxVal])
      .interpolator(d3.interpolateGreens);

    const weekday = ['日', '月', '火', '水', '木', '金', '土'];

    // 曜日ラベル
    weekday.forEach((day, i) => {
      g.append('text')
        .attr('x', -5)
        .attr('y', i * cellSize + cellSize / 2 + 20)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'middle')
        .attr('fill', theme.muted)
        .style('font-size', '10px')
        .text(day);
    });

    // セル
    const timeWeek = d3.timeMonday;
    const countDay = d => (d.getDay() + 6) % 7;

    let weekOffset = 0;
    let currentMonth = -1;

    const allDays = d3.timeDays(minDate, d3.timeDay.offset(maxDate, 1));

    allDays.forEach((date, i) => {
      const week = d3.timeMonday.count(minDate, date);
      const day = date.getDay();
      const dateStr = formatDate(date);
      const value = dataMap.get(dateStr) || 0;

      // 月ラベル
      if (date.getMonth() !== currentMonth) {
        currentMonth = date.getMonth();
        g.append('text')
          .attr('x', week * cellSize + cellSize / 2)
          .attr('y', 10)
          .attr('text-anchor', 'middle')
          .attr('fill', theme.muted)
          .style('font-size', '10px')
          .text(formatMonth(date));
      }

      const cell = g.append('rect')
        .attr('x', week * cellSize)
        .attr('y', day * cellSize + 20)
        .attr('width', cellSize - 2)
        .attr('height', cellSize - 2)
        .attr('rx', 2)
        .attr('fill', value > 0 ? colorScale(value) : theme.surface)
        .attr('stroke', theme.border)
        .attr('stroke-width', 0.5)
        .style('opacity', 0);

      cell.transition()
        .delay(i * 5)
        .duration(200)
        .style('opacity', 1);

      cell.on('mouseenter', function(event) {
        tooltip
          .html(`<strong>${dateStr}</strong><br/>値: ${value}`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px')
          .classed('visible', true);
      })
      .on('mouseleave', () => tooltip.classed('visible', false));
    });

    return { svg };
  },

  /**
   * パラレルコーディネート - 多変量データ比較
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{name, values: {axis1: val, axis2: val, ...}}]
   * @param {Object} options - {axes: ['axis1', 'axis2', ...]}
   */
  createParallelCoordinates(container, data, options = {}) {
    const {
      width = 700,
      height = 400,
      axes = Object.keys(data[0].values)
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 50, right: 40, bottom: 40, left: 40 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);
    const tooltip = D3Base.createTooltip(container);

    const x = d3.scalePoint()
      .domain(axes)
      .range([0, innerWidth]);

    const yScales = {};
    axes.forEach(axis => {
      const extent = d3.extent(data, d => d.values[axis]);
      yScales[axis] = d3.scaleLinear()
        .domain(extent)
        .range([innerHeight, 0]);
    });

    // 軸
    axes.forEach(axis => {
      const axisG = g.append('g')
        .attr('transform', `translate(${x(axis)},0)`);

      axisG.call(d3.axisLeft(yScales[axis]).ticks(5))
        .selectAll('text')
        .attr('fill', theme.muted)
        .style('font-size', '10px');

      axisG.append('text')
        .attr('y', -20)
        .attr('text-anchor', 'middle')
        .attr('fill', theme.fg)
        .style('font-size', '12px')
        .style('font-weight', '600')
        .text(axis);
    });

    // ライン生成
    const line = d3.line()
      .defined(d => !isNaN(d[1]))
      .x(d => d[0])
      .y(d => d[1]);

    // データライン
    data.forEach((d, i) => {
      const points = axes.map(axis => [x(axis), yScales[axis](d.values[axis])]);
      const color = accentPalette[i % accentPalette.length];

      const path = g.append('path')
        .datum(points)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 2)
        .attr('stroke-opacity', 0.7)
        .attr('d', line);

      const totalLength = path.node().getTotalLength();
      path
        .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
        .attr('stroke-dashoffset', totalLength)
        .transition()
        .delay(i * 100)
        .duration(800)
        .attr('stroke-dashoffset', 0);

      // ホバー
      path.on('mouseenter', function(event) {
        d3.select(this)
          .attr('stroke-width', 4)
          .attr('stroke-opacity', 1);
        tooltip
          .html(`<strong>${d.name}</strong>`)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px')
          .classed('visible', true);
      })
      .on('mouseleave', function() {
        d3.select(this)
          .attr('stroke-width', 2)
          .attr('stroke-opacity', 0.7);
        tooltip.classed('visible', false);
      });
    });

    return { svg };
  },

  /**
   * デンドログラム - クラスタリング表示
   * @param {HTMLElement} container - コンテナ要素
   * @param {Object} data - 階層構造 {name, children: [...]}
   * @param {Object} options - オプション
   */
  createDendrogram(container, data, options = {}) {
    const {
      width = 600,
      height = 400,
      horizontal = true
    } = options;

    const theme = D3Base.getTheme();
    const margin = horizontal
      ? { top: 20, right: 120, bottom: 20, left: 40 }
      : { top: 40, right: 20, bottom: 80, left: 20 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);

    const root = d3.hierarchy(data);

    const cluster = horizontal
      ? d3.cluster().size([innerHeight, innerWidth])
      : d3.cluster().size([innerWidth, innerHeight]);

    cluster(root);

    // リンク
    const linkGenerator = horizontal
      ? d3.linkHorizontal().x(d => d.y).y(d => d.x)
      : d3.linkVertical().x(d => d.x).y(d => d.y);

    g.selectAll('.link')
      .data(root.links())
      .enter()
      .append('path')
      .attr('class', 'link')
      .attr('fill', 'none')
      .attr('stroke', theme.border)
      .attr('stroke-width', 1.5)
      .attr('d', linkGenerator)
      .style('opacity', 0)
      .transition()
      .duration(600)
      .style('opacity', 1);

    // ノード
    const nodes = g.selectAll('.node')
      .data(root.descendants())
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => horizontal
        ? `translate(${d.y},${d.x})`
        : `translate(${d.x},${d.y})`);

    nodes.append('circle')
      .attr('r', d => d.children ? 4 : 6)
      .attr('fill', d => d.children ? theme.muted : accentPalette[d.depth % accentPalette.length])
      .style('opacity', 0)
      .transition()
      .delay((d, i) => i * 30)
      .duration(300)
      .style('opacity', 1);

    // ラベル（末端のみ）
    nodes.filter(d => !d.children)
      .append('text')
      .attr('x', horizontal ? 10 : 0)
      .attr('y', horizontal ? 0 : 15)
      .attr('text-anchor', horizontal ? 'start' : 'middle')
      .attr('dominant-baseline', 'middle')
      .attr('fill', theme.fg)
      .style('font-size', '11px')
      .text(d => d.data.name);

    return { svg };
  },

  /**
   * アイソタイプ（ピクトグラム） - アイコンで数量表現
   * @param {HTMLElement} container - コンテナ要素
   * @param {Array} data - [{label, value, icon}]
   * @param {Object} options - {unitValue, maxPerRow}
   */
  createIsotype(container, data, options = {}) {
    const {
      width = 600,
      height = 400,
      unitValue = 1,
      maxPerRow = 10,
      iconSize = 24
    } = options;

    const theme = D3Base.getTheme();
    const margin = { top: 40, right: 40, bottom: 40, left: 120 };
    const { svg, g, innerWidth, innerHeight } = D3Base.createSVG(container, width, height, margin);

    const rowHeight = Math.min(60, innerHeight / data.length);

    data.forEach((d, i) => {
      const rowG = g.append('g')
        .attr('transform', `translate(0,${i * rowHeight})`);

      // ラベル
      rowG.append('text')
        .attr('x', -10)
        .attr('y', rowHeight / 2)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'middle')
        .attr('fill', theme.fg)
        .style('font-size', '12px')
        .text(d.label);

      // アイコン（FontAwesome使用前提）
      const iconCount = Math.ceil(d.value / unitValue);
      const color = accentPalette[i % accentPalette.length];

      for (let j = 0; j < iconCount; j++) {
        const x = (j % maxPerRow) * (iconSize + 4);
        const y = Math.floor(j / maxPerRow) * (iconSize + 4);

        // 四角形で代替（実際はFontAwesomeアイコンを使用）
        rowG.append('rect')
          .attr('x', x)
          .attr('y', y + (rowHeight - iconSize) / 2)
          .attr('width', iconSize - 4)
          .attr('height', iconSize - 4)
          .attr('rx', 4)
          .attr('fill', color)
          .style('opacity', 0)
          .transition()
          .delay(j * 30 + i * 100)
          .duration(200)
          .style('opacity', 1);
      }

      // 値ラベル
      const totalWidth = Math.min(iconCount, maxPerRow) * (iconSize + 4);
      rowG.append('text')
        .attr('x', totalWidth + 10)
        .attr('y', rowHeight / 2)
        .attr('dominant-baseline', 'middle')
        .attr('fill', theme.muted)
        .style('font-size', '11px')
        .text(d.value);
    });

    return { svg };
  }
};
