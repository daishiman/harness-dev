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
