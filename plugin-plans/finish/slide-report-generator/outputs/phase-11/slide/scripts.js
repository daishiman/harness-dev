/* scripts.js — render-slide.js 自動生成 (GSAP 安全パターン)
 * SR-6-01: scale 最小 0.8。0 / 0.5 禁止
 * SR-6-02: clearProps は content.children のみ
 * SR-6-03: updateSlide / leaveAnimation の onComplete 両方で適用
 * SR-6-08: prefers-reduced-motion 検出
 */
(function () {
  'use strict';
  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var D = prefersReducedMotion ? 0 : 1; // duration multiplier
  var S = prefersReducedMotion ? 0 : 1; // stagger multiplier

  var slides = Array.prototype.slice.call(document.querySelectorAll('.slider__item'));
  var current = 0;
  if (slides.length === 0) return;
  slides[0].classList.add('is-active');

  function getContent(slide) { return slide.querySelector('.slider__content'); }

  function enterAnimation(slide) {
    if (typeof gsap === 'undefined') return;
    var content = getContent(slide);
    if (!content) return;
    gsap.set(content.children, { opacity: 0, y: 30 });
    gsap.to(content.children, {
      opacity: 1, y: 0,
      duration: 0.5 * D,
      stagger: 0.06 * S,
      ease: 'power2.out',
      onComplete: function () {
        // SR-6-02 / SR-6-03
        gsap.set(content.children, { clearProps: 'all' });
      }
    });
  }

  function leaveAnimation(slide, cb) {
    if (typeof gsap === 'undefined') { if (cb) cb(); return; }
    var content = getContent(slide);
    if (!content) { if (cb) cb(); return; }
    gsap.to(content.children, {
      opacity: 0, y: -20,
      duration: 0.18 * D,
      stagger: 0.03 * S,
      ease: 'power3.inOut',
      onComplete: function () {
        gsap.set(content.children, { clearProps: 'all' });
        if (cb) cb();
      }
    });
  }

  function updateSlide(next) {
    if (next < 0 || next >= slides.length || next === current) return;
    var prev = slides[current];
    var nextEl = slides[next];
    leaveAnimation(prev, function () {
      prev.classList.remove('is-active');
      nextEl.classList.add('is-active');
      enterAnimation(nextEl);
      current = next;
      window.dispatchEvent(new CustomEvent('slidechange', { detail: { index: current, total: slides.length } }));
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') updateSlide(current + 1);
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') updateSlide(current - 1);
    else if (e.key === 'Home') updateSlide(0);
    else if (e.key === 'End') updateSlide(slides.length - 1);
  });

  // Pagination wiring
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-pg-component], .pg-controls__btn, .pg-dots__item, .pg-section-nav__item');
    if (!t) return;
    if (t.classList.contains('pg-controls__btn--prev')) updateSlide(current - 1);
    else if (t.classList.contains('pg-controls__btn--next')) updateSlide(current + 1);
    else if (t.classList.contains('pg-dots__item')) {
      var i = parseInt(t.getAttribute('data-index') || '0', 10);
      updateSlide(i);
    } else if (t.classList.contains('pg-section-nav__item')) {
      var f = parseInt(t.getAttribute('data-first-slide') || '0', 10);
      updateSlide(f);
    }
  });

  // initial enter
  if (typeof gsap !== 'undefined') enterAnimation(slides[0]);
  window.__renderSlide = { goTo: updateSlide, total: slides.length, get current(){ return current; } };
})();

/* ===== pagination.js (asset 結合) ===== */
/* =================================================================
   pagination.js — 不変共通テンプレート

   責務:
     - スライド遷移ロジック（GSAP, scale 最小 0.8）
     - キーバインド: ← / → / Space / PageUp / PageDown / Home / End
     - ドット・前後ボタン・セクション目次クリック遷移
     - URL ハッシュ同期（#slide-3）
     - data-hidden="true" のスライドはスキップ
     - clearProps は content.children のみ（fo-card / SVG は除外）

   依存:
     - GSAP（必須）
     - スライド要素は `.slider .slider__item` を持つこと
     - 各スライドの中身は `.slider__content` でラップされていること

   公開:
     window.Pagination = { goTo, next, prev, current, total, instance }

   不変ルール: ロジック・キー割り当て・clearProps 範囲は変更禁止。
   ================================================================= */
(function () {
  'use strict';

  const REDUCED_MOTION =
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const D = REDUCED_MOTION ? 0.01 : 1;
  const HASH_PREFIX = '#slide-';
  const MIN_SCALE = 0.8;

  class Pagination {
    constructor(rootSelector = '.slider') {
      this.root = document.querySelector(rootSelector);
      if (!this.root) return;

      this.container = this.root.querySelector('.slider__container') || this.root;
      this.allItems = Array.from(this.root.querySelectorAll('.slider__item'));
      // data-hidden="true" のスライドは遷移対象外（インデックス計算からも除外）
      this.items = this.allItems.filter((el) => el.dataset.hidden !== 'true');

      this.index = 0;
      this.isAnimating = false;

      this.dotsRoot = document.querySelector('[data-pg-component="dots"]');
      this.counterEl = document.querySelector('[data-pg-component="counter"]');
      this.controlsRoot = document.querySelector('[data-pg-component="controls"]');
      this.sectionNav = document.querySelector('[data-pg-component="section-nav"]');
      this.progressBar = document.querySelector('.pg-progress__bar');
      this.progressRoot = document.querySelector('.pg-progress');

      this.init();
    }

    init() {
      this.buildDots();
      this.bindControls();
      this.bindSectionNav();
      this.bindKeyboard();
      this.bindHashChange();

      const initial = this.indexFromHash();
      this.goTo(initial, false);
    }

    /* ---------------- DOM 構築 ---------------- */
    buildDots() {
      if (!this.dotsRoot) return;
      const total = this.items.length;
      this.dotsRoot.innerHTML = '';
      for (let i = 0; i < total; i++) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'pg-dots__item';
        btn.dataset.index = String(i);
        btn.setAttribute('aria-label', `スライド ${i + 1}`);
        btn.addEventListener('click', () => this.goTo(i));
        this.dotsRoot.appendChild(btn);
      }
    }

    /* ---------------- イベントバインド ---------------- */
    bindControls() {
      if (!this.controlsRoot) return;
      const prev = this.controlsRoot.querySelector('.pg-controls__btn--prev');
      const next = this.controlsRoot.querySelector('.pg-controls__btn--next');
      if (prev) prev.addEventListener('click', () => this.prev());
      if (next) next.addEventListener('click', () => this.next());
    }

    bindSectionNav() {
      if (!this.sectionNav) return;
      const items = this.sectionNav.querySelectorAll('.pg-section-nav__item');
      items.forEach((item) => {
        item.addEventListener('click', () => {
          const target = parseInt(item.dataset.firstSlide, 10);
          if (!Number.isNaN(target)) this.goTo(target);
        });
      });
    }

    bindKeyboard() {
      document.addEventListener('keydown', (e) => {
        // 入力中（input/textarea/contenteditable）は無視
        const t = e.target;
        if (
          t &&
          (t.tagName === 'INPUT' ||
            t.tagName === 'TEXTAREA' ||
            t.isContentEditable)
        ) {
          return;
        }

        switch (e.key) {
          case 'ArrowRight':
          case 'PageDown':
          case ' ':
            e.preventDefault();
            this.next();
            break;
          case 'ArrowLeft':
          case 'PageUp':
            e.preventDefault();
            this.prev();
            break;
          case 'Home':
            e.preventDefault();
            this.goTo(0);
            break;
          case 'End':
            e.preventDefault();
            this.goTo(this.items.length - 1);
            break;
        }
      });
    }

    bindHashChange() {
      window.addEventListener('hashchange', () => {
        const i = this.indexFromHash();
        if (i !== this.index) this.goTo(i, true, /*fromHash=*/ true);
      });
    }

    /* ---------------- 遷移コア ---------------- */
    indexFromHash() {
      const h = window.location.hash || '';
      if (!h.startsWith(HASH_PREFIX)) return 0;
      const n = parseInt(h.slice(HASH_PREFIX.length), 10);
      if (Number.isNaN(n)) return 0;
      // ハッシュは 1 始まり → 0 始まりに変換
      return Math.max(0, Math.min(this.items.length - 1, n - 1));
    }

    syncHash(index) {
      const newHash = HASH_PREFIX + (index + 1);
      if (window.location.hash !== newHash) {
        history.replaceState(null, '', newHash);
      }
    }

    next() {
      const n = (this.index + 1) % this.items.length;
      this.goTo(n);
    }

    prev() {
      const n = (this.index - 1 + this.items.length) % this.items.length;
      this.goTo(n);
    }

    goTo(index, animate = true, fromHash = false) {
      if (
        this.isAnimating ||
        index < 0 ||
        index >= this.items.length ||
        index === this.index
      ) {
        // 初回（hash経由）でも UI だけは同期する
        if (index === this.index) {
          this.updateUI(index);
          if (!fromHash) this.syncHash(index);
        }
        return;
      }

      const prevIndex = this.index;
      this.index = index;
      this.isAnimating = true;

      const prevSlide = this.items[prevIndex];
      const nextSlide = this.items[index];

      const tl = window.gsap ? window.gsap.timeline() : null;
      const finish = () => {
        this.items.forEach((el, i) => {
          el.classList.toggle('is-active', i === index);
        });
        this.applyClearProps(nextSlide);
        this.updateUI(index);
        if (!fromHash) this.syncHash(index);
        this.isAnimating = false;
      };

      if (!animate || !tl) {
        finish();
        return;
      }

      const prevContent = prevSlide && prevSlide.querySelector('.slider__content');
      const nextContent = nextSlide && nextSlide.querySelector('.slider__content');

      if (prevContent) {
        tl.to(prevContent.children, {
          opacity: 0,
          duration: 0.18 * D,
          ease: 'power1.in',
          stagger: 0,
          onComplete: () => this.applyClearProps(prevSlide)
        });
      }

      if (nextContent) {
        tl.fromTo(
          nextContent.children,
          { opacity: 0, scale: MIN_SCALE },
          {
            opacity: 1,
            scale: 1,
            duration: 0.35 * D,
            ease: 'power2.out',
            stagger: 0.04 * (REDUCED_MOTION ? 0 : 1),
            onComplete: finish
          },
          '>-0.05'
        );
      } else {
        finish();
      }
    }

    /* ---------------- clearProps（fo-card/SVG除外） ---------------- */
    applyClearProps(slideEl) {
      if (!slideEl || !window.gsap) return;
      const content = slideEl.querySelector('.slider__content');
      if (!content) return;
      // 直下の子要素のみクリア。さらに .fo-card は明示的に除外。
      const targets = Array.from(content.children).filter(
        (el) => !el.classList.contains('fo-card')
      );
      if (targets.length) {
        window.gsap.set(targets, { clearProps: 'all' });
      }
    }

    /* ---------------- UI 更新 ---------------- */
    updateUI(index) {
      // ドット
      if (this.dotsRoot) {
        const dots = this.dotsRoot.querySelectorAll('.pg-dots__item');
        dots.forEach((d, i) => d.classList.toggle('is-active', i === index));
        const active = dots[index];
        if (active && active.scrollIntoView) {
          active.scrollIntoView({ block: 'nearest', inline: 'center' });
        }
      }

      // カウンター
      if (this.counterEl) {
        const cur = this.counterEl.querySelector('.pg-counter__current');
        const tot = this.counterEl.querySelector('.pg-counter__total');
        if (cur) cur.textContent = String(index + 1);
        if (tot) tot.textContent = String(this.items.length);
      }

      // プログレス
      if (this.progressBar) {
        const pct = ((index + 1) / this.items.length) * 100;
        this.progressBar.style.width = pct + '%';
      }
      if (this.progressRoot) {
        this.progressRoot.setAttribute('aria-valuenow', String(index + 1));
      }

      // セクション目次
      if (this.sectionNav) {
        const current = this.items[index];
        const section = current ? current.dataset.section : '';
        this.sectionNav.querySelectorAll('.pg-section-nav__item').forEach((item) => {
          item.classList.toggle(
            'is-active',
            !!section && item.dataset.section === section
          );
        });
      }

      // 前後ボタンの活性（ループするので常に有効。aria-only）
      if (this.controlsRoot) {
        const prev = this.controlsRoot.querySelector('.pg-controls__btn--prev');
        const next = this.controlsRoot.querySelector('.pg-controls__btn--next');
        if (prev) prev.setAttribute('aria-disabled', 'false');
        if (next) next.setAttribute('aria-disabled', 'false');
      }
    }
  }

  /* ---------------- 起動 ---------------- */
  function boot() {
    const instance = new Pagination('.slider');
    window.Pagination = {
      instance,
      goTo: (i) => instance.goTo(i),
      next: () => instance.next(),
      prev: () => instance.prev(),
      get current() {
        return instance.index;
      },
      get total() {
        return instance.items.length;
      }
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();


/* ===== d3-bootstrap.js (asset 結合・SR-12-05) ===== */
/* d3-bootstrap.js — render-slide.cjs 自動生成 (SR-12-05) */
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

  loadScript('https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js').then(function () {
    return loadScript('https://cdnjs.cloudflare.com/ajax/libs/d3-sankey/0.12.3/d3-sankey.min.js').catch(function () { /* optional */ });
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

