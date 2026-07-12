# アジェンダナビゲーション

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは設計の文脈・例・適用ガイドのみ。規則の正本は SR-ID で参照すること

**責務**: セクション目次ナビゲーションの実装テンプレート（HTML/CSS/JS、GSAP連携、ホバー・クリック）。
**規則の正本**: ページネーション5個区切り → [SR-8-01](spec-registry.md#sr-8-01) / [SR-8-02](spec-registry.md#sr-8-02)、section-nav 常時表示 → [SR-8-03](spec-registry.md#sr-8-03)、data-section 全網羅 → [SR-8-04](spec-registry.md#sr-8-04)、矢印余白 → [SR-8-06](spec-registry.md#sr-8-06)

---

## 17-A. セクション目次ナビ（横並びタブ型 — Lotus White推奨）

画面上部に固定表示される横並びタブ。現在セクションをハイライトし、クリックでジャンプ可能。
Kanagawa Lotus White（ライトテーマ）用。

### 17-A.1 HTML構造

```html
<nav class="section-nav" aria-label="セクション目次">
  <button class="section-nav__item active" data-section="opening" data-first-slide="0">
    <span class="section-nav__dot" style="background: var(--accent-blue-vivid);"></span>
    <span class="section-nav__label">オープニング</span>
    <span class="section-nav__bar"></span>
  </button>
  <button class="section-nav__item" data-section="lecture" data-first-slide="3">
    <span class="section-nav__dot" style="background: var(--accent-aqua-vivid);"></span>
    <span class="section-nav__label">講義</span>
    <span class="section-nav__bar"></span>
  </button>
  <button class="section-nav__item" data-section="demo" data-first-slide="12">
    <span class="section-nav__dot" style="background: var(--accent-yellow-vivid);"></span>
    <span class="section-nav__label">デモ</span>
    <span class="section-nav__bar"></span>
  </button>
  <button class="section-nav__item" data-section="ws" data-first-slide="17">
    <span class="section-nav__dot" style="background: var(--accent-violet-vivid);"></span>
    <span class="section-nav__label">ワークショップ</span>
    <span class="section-nav__bar"></span>
  </button>
  <button class="section-nav__item" data-section="summary" data-first-slide="23">
    <span class="section-nav__dot" style="background: var(--accent-pink-vivid);"></span>
    <span class="section-nav__label">まとめ</span>
    <span class="section-nav__bar"></span>
  </button>
</nav>
```

**data-first-slide**: 各セクション先頭スライドの0始まりインデックス。structure.mdのスライド一覧から算出。

### 17-A.2 CSS

```css
.section-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 0;
  background: rgba(250, 250, 250, 0.92);
  backdrop-filter: blur(0.5rem);
  -webkit-backdrop-filter: blur(0.5rem);
  border-bottom: 1px solid var(--sumi-ink);
  padding: 0 var(--space-4);
}

.section-nav__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border: none;
  background: none;
  cursor: pointer;
  font-family: 'Noto Sans JP', sans-serif;
  font-size: var(--fs-small);
  font-weight: var(--fw-semibold);
  color: var(--fg);
  opacity: 0.5;
  transition: opacity 0.3s ease, background 0.3s ease;
  white-space: nowrap;
}

.section-nav__item:hover { opacity: 0.8; background: var(--bg-dim); }
.section-nav__item:focus-visible { outline: 2px solid var(--accent-blue-vivid); outline-offset: -2px; }
.section-nav__item.active { opacity: 1; }

.section-nav__dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; flex-shrink: 0; }
.section-nav__label { pointer-events: none; }

.section-nav__bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 3px;
  background: transparent;
  transition: background 0.3s ease;
}

/* セクション別アクティブバー色 */
.section-nav__item.active[data-section="opening"] .section-nav__bar { background: var(--accent-blue-vivid); }
.section-nav__item.active[data-section="lecture"] .section-nav__bar { background: var(--accent-aqua-vivid); }
.section-nav__item.active[data-section="demo"] .section-nav__bar { background: var(--accent-yellow-vivid); }
.section-nav__item.active[data-section="ws"] .section-nav__bar { background: var(--accent-violet-vivid); }
.section-nav__item.active[data-section="summary"] .section-nav__bar { background: var(--accent-pink-vivid); }
```

### 17-A.3 JavaScript（TweenSlider連携）

```javascript
// init() 内
this.bindSectionNav();
this.updateSectionNav();

// updateSlide() 内
this.updateSectionNav();

// メソッド
updateSectionNav() {
  const currentSlide = this.items[this.index];
  const section = currentSlide ? currentSlide.dataset.section : '';
  const navItems = document.querySelectorAll('.section-nav__item');
  navItems.forEach((item) => {
    item.classList.toggle('active', item.dataset.section === section);
  });
}

bindSectionNav() {
  const navItems = document.querySelectorAll('.section-nav__item');
  navItems.forEach((item) => {
    item.addEventListener('click', () => {
      const idx = parseInt(item.dataset.firstSlide, 10);
      if (!isNaN(idx)) this.goTo(idx);
    });
  });
}
```

### 17-A.4 印刷CSS

```css
@media print {
  .section-nav { display: none !important; }
}
```

---

## 17-B. アジェンダインジケーター（縦型サイドバー — ダークテーマ用）

左上のアジェンダインジケーターをクリックして、該当セクションのトップページに移動する機能。
Kanagawa Wave（ダークテーマ）用。

### 17.1 HTML構造

```html
<!-- アジェンダインジケーター（クリック可能） -->
<div class="agenda-indicator">
  <a href="#section-1" class="agenda-indicator-item active" data-section="1">
    <span class="agenda-number">1</span>
    <span class="agenda-label">{{セクション1}}</span>
  </a>
  <a href="#section-2" class="agenda-indicator-item" data-section="2">
    <span class="agenda-number">2</span>
    <span class="agenda-label">{{セクション2}}</span>
  </a>
  <a href="#section-3" class="agenda-indicator-item" data-section="3">
    <span class="agenda-number">3</span>
    <span class="agenda-label">{{セクション3}}</span>
  </a>
</div>

<!-- 各セクションのスライドにIDを付与 -->
<div id="section-1" class="slider__item slide-section" data-section="1">
  <!-- セクション1の開始スライド -->
</div>
```

### 17.2 CSS（ホバー・クリック状態）

```css
/* アジェンダインジケーター ベーススタイル */
.agenda-indicator {
  position: fixed;
  top: 1.5rem;
  left: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  z-index: 100;
  pointer-events: auto;
}

/* 各アジェンダ項目（リンク） */
.agenda-indicator-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  background: rgba(31, 31, 40, 0.8);
  border-radius: 8px;
  border-left: 3px solid transparent;
  cursor: pointer;
  text-decoration: none;
  color: var(--fg-dim);
  transition: all 0.3s ease;
}

/* ホバー状態 */
.agenda-indicator-item:hover {
  background: rgba(31, 31, 40, 0.95);
  color: var(--fg-light);
  border-left-color: var(--wave-aqua);
  transform: translateX(5px);
}

/* アクティブ状態（現在のセクション） */
.agenda-indicator-item.active {
  background: rgba(126, 156, 216, 0.2);
  color: var(--wave-blue);
  border-left-color: var(--wave-blue);
}

.agenda-indicator-item.active:hover {
  border-left-color: var(--sakura-pink);
}

/* 番号バッジ */
.agenda-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: var(--fuji-gray);
  border-radius: 50%;
  font-size: var(--fs-small);
  font-weight: 700;
}

.agenda-indicator-item.active .agenda-number {
  background: var(--wave-blue);
  color: var(--bg-dark);
}

.agenda-indicator-item:hover .agenda-number {
  background: var(--wave-aqua);
  color: var(--bg-dark);
}

/* ラベル */
.agenda-label {
  font-size: var(--fs-small);
  white-space: nowrap;
}
```

### 17.3 JavaScript（ナビゲーション機能）

```javascript
// アジェンダインジケーターのナビゲーション機能
document.addEventListener('DOMContentLoaded', function() {
  const agendaItems = document.querySelectorAll('.agenda-indicator-item');
  const slides = document.querySelectorAll('.slider__item');

  // 各セクションの開始スライドインデックスを取得
  const sectionStartIndices = {};
  slides.forEach((slide, index) => {
    const section = slide.getAttribute('data-section');
    if (section && !(section in sectionStartIndices)) {
      sectionStartIndices[section] = index;
    }
  });

  // アジェンダ項目クリック時のナビゲーション
  agendaItems.forEach(item => {
    item.addEventListener('click', function(e) {
      e.preventDefault();

      const targetSection = this.getAttribute('data-section');
      const targetIndex = sectionStartIndices[targetSection];

      if (targetIndex !== undefined) {
        // スライダーを該当スライドに移動
        goToSlide(targetIndex);

        // アクティブ状態を更新
        agendaItems.forEach(ai => ai.classList.remove('active'));
        this.classList.add('active');
      }
    });
  });

  // スライド変更時にアジェンダインジケーターを更新
  function updateAgendaIndicator(currentSlideIndex) {
    const currentSlide = slides[currentSlideIndex];
    const currentSection = currentSlide?.getAttribute('data-section');

    if (currentSection) {
      agendaItems.forEach(item => {
        const itemSection = item.getAttribute('data-section');
        item.classList.toggle('active', itemSection === currentSection);
      });
    }
  }

  // goToSlide関数（既存のスライダー機能と連携）
  function goToSlide(index) {
    // GSAPを使用している場合
    if (typeof gsap !== 'undefined' && window.slideTimeline) {
      // 既存のGSAPスライダーと連携
      window.currentSlide = index;
      updateSlider(index);
    } else {
      // 標準的なスライダーの場合
      const slider = document.querySelector('.slider');
      if (slider) {
        slider.style.transform = `translateX(-${index * 100}%)`;
      }
    }

    updateAgendaIndicator(index);
  }

  // スライダーの変更を監視してアジェンダを更新
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
        const activeSlide = document.querySelector('.slider__item.active');
        if (activeSlide) {
          const index = Array.from(slides).indexOf(activeSlide);
          updateAgendaIndicator(index);
        }
      }
    });
  });

  slides.forEach(slide => {
    observer.observe(slide, { attributes: true });
  });

  // キーボードナビゲーションとの連携
  document.addEventListener('keydown', function(e) {
    // 既存のキーボードナビゲーション後にアジェンダを更新
    setTimeout(() => {
      const activeSlide = document.querySelector('.slider__item.active');
      if (activeSlide) {
        const index = Array.from(slides).indexOf(activeSlide);
        updateAgendaIndicator(index);
      }
    }, 100);
  });
});
```

### 17.4 GSAP連携版JavaScript

```javascript
// GSAP使用時のアジェンダナビゲーション
const AgendaNavigation = {
  init: function(slideManager) {
    this.slideManager = slideManager;
    this.agendaItems = document.querySelectorAll('.agenda-indicator-item');
    this.slides = document.querySelectorAll('.slider__item');
    this.sectionMap = this.buildSectionMap();

    this.bindEvents();
    this.updateIndicator(0);
  },

  buildSectionMap: function() {
    const map = {};
    this.slides.forEach((slide, index) => {
      const section = slide.dataset.section;
      if (section && !map[section]) {
        map[section] = index;
      }
    });
    return map;
  },

  bindEvents: function() {
    const self = this;

    this.agendaItems.forEach(item => {
      item.addEventListener('click', function(e) {
        e.preventDefault();
        const section = this.dataset.section;
        const targetIndex = self.sectionMap[section];

        if (targetIndex !== undefined) {
          self.slideManager.goTo(targetIndex);
          self.updateIndicator(targetIndex);
        }
      });
    });
  },

  updateIndicator: function(currentIndex) {
    const currentSlide = this.slides[currentIndex];
    const currentSection = currentSlide?.dataset.section;

    this.agendaItems.forEach(item => {
      const isActive = item.dataset.section === currentSection;
      item.classList.toggle('active', isActive);

      // GSAPでアニメーション
      if (typeof gsap !== 'undefined') {
        gsap.to(item, {
          x: isActive ? 5 : 0,
          duration: 0.3,
          ease: 'power2.out'
        });
      }
    });
  },

  // 外部から呼び出し用
  onSlideChange: function(index) {
    this.updateIndicator(index);
  }
};

// 初期化
document.addEventListener('DOMContentLoaded', () => {
  // slideManagerは既存のスライダー管理オブジェクト
  if (window.slideManager) {
    AgendaNavigation.init(window.slideManager);

    // スライド変更時のコールバック登録
    window.slideManager.onSlideChange = (index) => {
      AgendaNavigation.onSlideChange(index);
    };
  }
});
```

### 17.5 使用例

```html
<!-- 完全な実装例 -->
<div class="slider-container">
  <!-- アジェンダインジケーター -->
  <div class="agenda-indicator">
    <a href="#section-intro" class="agenda-indicator-item active" data-section="intro">
      <span class="agenda-number">1</span>
      <span class="agenda-label">イントロ</span>
    </a>
    <a href="#section-problem" class="agenda-indicator-item" data-section="problem">
      <span class="agenda-number">2</span>
      <span class="agenda-label">課題</span>
    </a>
    <a href="#section-solution" class="agenda-indicator-item" data-section="solution">
      <span class="agenda-number">3</span>
      <span class="agenda-label">解決策</span>
    </a>
    <a href="#section-next" class="agenda-indicator-item" data-section="next">
      <span class="agenda-number">4</span>
      <span class="agenda-label">次のステップ</span>
    </a>
  </div>

  <!-- スライド -->
  <div class="slider">
    <div id="section-intro" class="slider__item slide-title-page" data-section="intro">
      <!-- タイトルスライド -->
    </div>
    <div class="slider__item slide-agenda" data-section="intro">
      <!-- アジェンダスライド -->
    </div>
    <div id="section-problem" class="slider__item slide-section" data-section="problem">
      <!-- 課題セクション開始 -->
    </div>
    <!-- ... -->
  </div>
</div>
```
