/**
 * d3-bootstrap.cjs — D3 マウント共通スクリプトを生成
 *
 * 出力されるスクリプトは index.html の末尾に挿入され、
 *   window.__d3Mounts = [{ id, component, config }, ...]
 * を順次走査して、対応する d3-components/*.js のレンダラを呼び出す。
 *
 * 各 component は assets/d3-components/ に存在する想定（base/cycle/hierarchy/flow/charts/advanced/extended.js）。
 * 実環境では D3 v7 を CDN ロードし、コンポーネントスクリプトを <script> タグで併せ読みする。
 *
 * SR-12-05: HTML/CSS/JS 完全分離。決定論。
 */
'use strict';

const fs = require('fs');
const path = require('path');

const D3_VERSION = '7.9.0';
const D3_CDN = `https://cdnjs.cloudflare.com/ajax/libs/d3/${D3_VERSION}/d3.min.js`;
const D3_SANKEY_CDN = `https://cdnjs.cloudflare.com/ajax/libs/d3-sankey/0.12.3/d3-sankey.min.js`;

/**
 * 73 スライドタイプで使用される D3 コンポーネントのフォールバック実装。
 * 実装の詳細は assets/d3-components/*.js に委譲するが、
 * CDN ロード失敗時/開発時用に最低限の placeholder レンダラを提供する。
 */
function renderD3BootstrapJs() {
  return `/* d3-bootstrap.js — render-slide.cjs 自動生成 (SR-12-05) */
(function () {
  'use strict';
  var mounts = window.__d3Mounts || [];
  // SR-12-05: data-only <script type="application/json" data-d3-mount> をスキャン（V-020 inline JS 違反回避）
  try {
    var nodes = document.querySelectorAll('script[type="application/json"][data-d3-mount]');
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var cfg;
      try { cfg = JSON.parse(n.textContent || '{}'); } catch (e) { continue; }
      mounts.push({
        id: n.getAttribute('data-d3-target'),
        component: n.getAttribute('data-d3-component'),
        config: cfg
      });
    }
  } catch (e) { /* ignore */ }
  if (!mounts.length) return;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  function fallbackRender(el, m) {
    // CDN 失敗時の最小プレースホルダ
    var div = document.createElement('div');
    div.className = 'd3-fallback';
    div.setAttribute('role', 'img');
    div.setAttribute('aria-label', m.component + ' chart');
    div.style.cssText = 'padding:1rem;border:2px dashed var(--wave-blue,#7E9CD8);color:var(--fg,#43436c);text-align:center;font-weight:700;';
    div.textContent = '[D3:' + m.component + ']';
    el.appendChild(div);
  }

  function render(d3, m) {
    var el = document.getElementById(m.id);
    if (!el) return;
    var cfg = m.config || {};
    var W = (cfg.options && cfg.options.width) || 720;
    var H = (cfg.options && cfg.options.height) || 480;

    var svg = d3.select(el).append('svg')
      .attr('viewBox', '0 0 ' + W + ' ' + H)
      .attr('role', 'img')
      .attr('aria-label', cfg.title || m.component);

    var palette = ['var(--wave-blue,#7E9CD8)', 'var(--wave-aqua,#7FB4CA)', 'var(--sakura-pink,#D27E99)', 'var(--autumn-yellow,#DCA561)', 'var(--spring-violet,#957FB8)'];

    try {
      switch (m.component) {
        case 'cycle':
        case 'pdca':
        case 'triangle-cycle':
        case 'rotating-flow': {
          var data = (cfg.data || []).slice(0, 7);
          var n = data.length || 4;
          var cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.35;
          for (var i = 0; i < n; i++) {
            var a = -Math.PI / 2 + 2 * Math.PI * i / n;
            var x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
            svg.append('circle').attr('cx', x).attr('cy', y).attr('r', 50).attr('fill', palette[i % palette.length]).attr('opacity', 0.92);
            svg.append('text').attr('x', x).attr('y', y + 5).attr('text-anchor', 'middle').attr('fill', '#fff').attr('font-weight', 700).attr('font-size', 14).text((data[i] && data[i].label) || ('Step ' + (i + 1)));
          }
          break;
        }
        case 'tree':
        case 'org-chart':
        case 'dendrogram': {
          var root = d3.hierarchy(cfg.data || { name: 'root', children: [] });
          var tree = d3.tree().size([W - 40, H - 40]);
          tree(root);
          var g = svg.append('g').attr('transform', 'translate(20,20)');
          g.selectAll('.link').data(root.links()).enter().append('path').attr('d', d3.linkVertical().x(function (d) { return d.x; }).y(function (d) { return d.y; })).attr('fill', 'none').attr('stroke', palette[0]).attr('stroke-width', 2);
          g.selectAll('.node').data(root.descendants()).enter().append('g').attr('transform', function (d) { return 'translate(' + d.x + ',' + d.y + ')'; })
            .each(function (d) {
              d3.select(this).append('circle').attr('r', 18).attr('fill', palette[d.depth % palette.length]);
              d3.select(this).append('text').attr('text-anchor', 'middle').attr('y', 5).attr('fill', '#fff').attr('font-weight', 700).attr('font-size', 12).text(d.data.name || '');
            });
          break;
        }
        case 'sunburst':
        case 'treemap':
        case 'packed': {
          var hr = d3.hierarchy(cfg.data || { name: 'root', children: [] }).sum(function (d) { return d.value || 1; });
          var rad = Math.min(W, H) / 2 - 20;
          if (m.component === 'sunburst') {
            d3.partition().size([2 * Math.PI, rad])(hr);
            var arc = d3.arc().startAngle(function (d) { return d.x0; }).endAngle(function (d) { return d.x1; }).innerRadius(function (d) { return d.y0; }).outerRadius(function (d) { return d.y1; });
            svg.append('g').attr('transform', 'translate(' + (W / 2) + ',' + (H / 2) + ')').selectAll('path').data(hr.descendants()).enter().append('path').attr('d', arc).attr('fill', function (d) { return palette[d.depth % palette.length]; }).attr('opacity', 0.85);
          } else if (m.component === 'treemap') {
            d3.treemap().size([W - 20, H - 20]).padding(2)(hr);
            svg.append('g').attr('transform', 'translate(10,10)').selectAll('rect').data(hr.leaves()).enter().append('rect').attr('x', function (d) { return d.x0; }).attr('y', function (d) { return d.y0; }).attr('width', function (d) { return d.x1 - d.x0; }).attr('height', function (d) { return d.y1 - d.y0; }).attr('fill', function (d, i) { return palette[i % palette.length]; }).attr('opacity', 0.9);
          } else {
            d3.pack().size([W, H]).padding(4)(hr);
            svg.selectAll('circle').data(hr.descendants()).enter().append('circle').attr('cx', function (d) { return d.x; }).attr('cy', function (d) { return d.y; }).attr('r', function (d) { return d.r; }).attr('fill', function (d) { return palette[d.depth % palette.length]; }).attr('opacity', 0.7);
          }
          break;
        }
        case 'sankey':
        case 'force':
        case 'chord':
        case 'arc': {
          var nodes = (cfg.data && cfg.data.nodes) || [];
          var links = (cfg.data && cfg.data.links) || [];
          if (m.component === 'force' && d3.forceSimulation) {
            var sim = d3.forceSimulation(nodes).force('charge', d3.forceManyBody().strength(-200)).force('link', d3.forceLink(links).id(function (d) { return d.id; }).distance(80)).force('center', d3.forceCenter(W / 2, H / 2)).stop();
            for (var k = 0; k < 100; k++) sim.tick();
            svg.selectAll('line').data(links).enter().append('line').attr('x1', function (d) { return d.source.x; }).attr('y1', function (d) { return d.source.y; }).attr('x2', function (d) { return d.target.x; }).attr('y2', function (d) { return d.target.y; }).attr('stroke', palette[0]).attr('stroke-width', 1.5);
            svg.selectAll('circle').data(nodes).enter().append('circle').attr('cx', function (d) { return d.x; }).attr('cy', function (d) { return d.y; }).attr('r', 18).attr('fill', function (d, i) { return palette[i % palette.length]; });
            svg.selectAll('.lbl').data(nodes).enter().append('text').attr('x', function (d) { return d.x; }).attr('y', function (d) { return d.y + 4; }).attr('text-anchor', 'middle').attr('fill', '#fff').attr('font-size', 12).attr('font-weight', 700).text(function (d) { return d.name || d.id; });
          } else {
            // チャート系：簡易ノード描画
            var step = W / Math.max(2, nodes.length + 1);
            nodes.forEach(function (n, i) {
              var x = step * (i + 1);
              svg.append('circle').attr('cx', x).attr('cy', H / 2).attr('r', 24).attr('fill', palette[i % palette.length]);
              svg.append('text').attr('x', x).attr('y', H / 2 + 5).attr('text-anchor', 'middle').attr('fill', '#fff').attr('font-weight', 700).attr('font-size', 12).text(n.name || n.id);
            });
          }
          break;
        }
        case 'bar':
        case 'lollipop':
        case 'bullet':
        case 'isotype': {
          var bdata = cfg.data || [];
          var bMax = d3.max(bdata, function (d) { return d.value; }) || 1;
          var bw = (W - 80) / bdata.length * 0.7;
          var bg = (W - 80) / bdata.length;
          bdata.forEach(function (d, i) {
            var h = (d.value / bMax) * (H - 80);
            var x = 40 + i * bg + (bg - bw) / 2;
            svg.append('rect').attr('x', x).attr('y', H - 40 - h).attr('width', bw).attr('height', h).attr('rx', 4).attr('fill', palette[i % palette.length]);
            svg.append('text').attr('x', x + bw / 2).attr('y', H - 18).attr('text-anchor', 'middle').attr('font-size', 13).attr('fill', 'var(--fg,#43436c)').text(d.label);
          });
          break;
        }
        case 'line':
        case 'slope': {
          var ldata = cfg.data || [];
          var lMax = d3.max(ldata, function (d) { return d.value; }) || 1;
          var stepX = ldata.length > 1 ? (W - 80) / (ldata.length - 1) : (W - 80);
          var pts = ldata.map(function (d, i) { return [40 + i * stepX, H - 40 - (d.value / lMax) * (H - 80)]; });
          svg.append('polyline').attr('points', pts.map(function (p) { return p.join(','); }).join(' ')).attr('fill', 'none').attr('stroke', palette[0]).attr('stroke-width', 3);
          pts.forEach(function (p) {
            svg.append('circle').attr('cx', p[0]).attr('cy', p[1]).attr('r', 5).attr('fill', palette[0]);
          });
          break;
        }
        case 'pie':
        case 'donut': {
          var pdata = cfg.data || [];
          var arc2 = d3.arc().innerRadius(m.component === 'donut' ? 60 : 0).outerRadius(Math.min(W, H) / 2 - 20);
          var pie = d3.pie().value(function (d) { return d.value; });
          svg.append('g').attr('transform', 'translate(' + (W / 2) + ',' + (H / 2) + ')').selectAll('path').data(pie(pdata)).enter().append('path').attr('d', arc2).attr('fill', function (d, i) { return palette[i % palette.length]; }).attr('opacity', 0.92);
          break;
        }
        case 'radar': {
          var raxes = cfg.axes || [];
          var rseries = (cfg.series && cfg.series[0] && cfg.series[0].values) || [];
          var rR = Math.min(W, H) / 2 - 40, rcx = W / 2, rcy = H / 2;
          var pts = raxes.map(function (a, i) {
            var ang = -Math.PI / 2 + 2 * Math.PI * i / raxes.length;
            var v = (rseries[i] || 0) / 100;
            return [rcx + rR * v * Math.cos(ang), rcy + rR * v * Math.sin(ang)];
          });
          svg.append('polygon').attr('points', pts.map(function (p) { return p.join(','); }).join(' ')).attr('fill', palette[0]).attr('opacity', 0.4).attr('stroke', palette[0]).attr('stroke-width', 2);
          break;
        }
        case 'gauge': {
          var v = Math.max(0, Math.min(100, Number(cfg.data) || 0));
          var gcx = W / 2, gcy = H - 40, gr = Math.min(W / 2 - 30, H - 60);
          var gang = Math.PI * (1 - v / 100);
          svg.append('path').attr('d', 'M' + (gcx - gr) + ',' + gcy + ' A' + gr + ',' + gr + ' 0 0 1 ' + (gcx + gr) + ',' + gcy).attr('fill', 'none').attr('stroke', palette[1]).attr('stroke-width', 24).attr('opacity', 0.3);
          var gx = gcx + gr * Math.cos(gang), gy = gcy - gr * Math.sin(gang);
          svg.append('path').attr('d', 'M' + (gcx - gr) + ',' + gcy + ' A' + gr + ',' + gr + ' 0 ' + (v > 50 ? 1 : 0) + ' 1 ' + gx + ',' + gy).attr('fill', 'none').attr('stroke', palette[0]).attr('stroke-width', 24);
          svg.append('text').attr('x', gcx).attr('y', gcy - 30).attr('text-anchor', 'middle').attr('font-size', 36).attr('font-weight', 800).attr('fill', 'var(--fg,#43436c)').text(v + '%');
          break;
        }
        case 'bubble': {
          var bdata2 = cfg.data || [];
          var bMaxV = d3.max(bdata2, function (d) { return d.value; }) || 1;
          bdata2.forEach(function (d, i) {
            var x = 60 + (i + 0.5) * ((W - 120) / bdata2.length);
            var r = 10 + (d.value / bMaxV) * 50;
            svg.append('circle').attr('cx', x).attr('cy', H / 2).attr('r', r).attr('fill', palette[i % palette.length]).attr('opacity', 0.7);
            svg.append('text').attr('x', x).attr('y', H / 2 + 4).attr('text-anchor', 'middle').attr('font-size', 13).attr('fill', '#fff').attr('font-weight', 700).text(d.label || '');
          });
          break;
        }
        case 'heatmap':
        case 'calendar': {
          var hd = cfg.data || [];
          var cols = 12, rowsN = Math.ceil(hd.length / cols);
          var cellW = (W - 40) / cols, cellH = (H - 40) / Math.max(1, rowsN);
          var hMax = d3.max(hd, function (d) { return d.value; }) || 1;
          hd.forEach(function (d, i) {
            var c = i % cols, r2 = Math.floor(i / cols);
            svg.append('rect').attr('x', 20 + c * cellW).attr('y', 20 + r2 * cellH).attr('width', cellW - 2).attr('height', cellH - 2).attr('fill', palette[0]).attr('opacity', Math.max(0.15, (d.value || 0) / hMax));
          });
          break;
        }
        case 'radial-bar':
        case 'pyramid':
        case 'funnel':
        case 'waterfall':
        case 'roadmap':
        case 'vertical-timeline':
        case 'wordcloud':
        case 'chevron':
        default: {
          // 汎用フォールバック描画
          fallbackRender(el, m);
          break;
        }
      }
    } catch (err) {
      console.warn('[d3-bootstrap]', m.component, err);
      fallbackRender(el, m);
    }
  }

  loadScript('${D3_CDN}').then(function () {
    return loadScript('${D3_SANKEY_CDN}').catch(function () { /* optional */ });
  }).then(function () {
    if (typeof d3 === 'undefined') {
      mounts.forEach(function (m) {
        var el = document.getElementById(m.id);
        if (el) fallbackRender(el, m);
      });
      return;
    }
    mounts.forEach(function (m) { render(d3, m); });
  }).catch(function () {
    mounts.forEach(function (m) {
      var el = document.getElementById(m.id);
      if (el) fallbackRender(el, m);
    });
  });
})();
`;
}

module.exports = { renderD3BootstrapJs, D3_CDN, D3_SANKEY_CDN };
