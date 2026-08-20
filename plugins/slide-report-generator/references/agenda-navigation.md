# アジェンダナビゲーション

<!-- css-route: hand-slide -->
<!-- この宣言より後ろの var() は hand-slide 経路の :root とだけ照合される (lint-contract-drift.py check G)。経路が違う例を載せるときは、その直前に別の css-route 宣言を置く -->

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは設計の文脈・例・適用ガイドのみ。規則の正本は SR-ID で参照すること

**責務**: セクション目次ナビゲーションの実装テンプレート（HTML/CSS/JS、GSAP連携、ホバー・クリック）。
**規則の正本**: ページネーション5個区切り → [SR-8-01](spec-registry.md#sr-8-01) / [SR-8-02](spec-registry.md#sr-8-02)、section-nav 常時表示 → [SR-8-03](spec-registry.md#sr-8-03)、data-section 全網羅 → [SR-8-04](spec-registry.md#sr-8-04)、矢印余白 → [SR-8-06](spec-registry.md#sr-8-06)

---

## 17-A. セクション目次ナビ（横並びタブ型 — Lotus White推奨）

画面上部に固定表示される横並びタブ。現在セクションをハイライトし、クリックでジャンプ可能。
ライトテーマ（既定）用。

### 17-A.1 HTML構造

```html
<nav class="section-nav" aria-label="セクション目次">
  <button class="section-nav__item active" data-section="opening" data-first-slide="0" aria-current="true">
    <span class="section-nav__label">オープニング</span>
  </button>
  <button class="section-nav__item" data-section="lecture" data-first-slide="3">
    <span class="section-nav__label">講義</span>
  </button>
  <button class="section-nav__item" data-section="demo" data-first-slide="12">
    <span class="section-nav__label">デモ</span>
  </button>
  <button class="section-nav__item" data-section="ws" data-first-slide="17">
    <span class="section-nav__label">ワークショップ</span>
  </button>
  <button class="section-nav__item" data-section="summary" data-first-slide="23">
    <span class="section-nav__label">まとめ</span>
  </button>
</nav>
```

**data-first-slide**: 各セクション先頭スライドの0始まりインデックス。structure.mdのスライド一覧から算出。

**セクションを色相で区別しない**（SR-2-07）。5 つを見分ける手がかりは既に 3 つある——**並び順**（ナビ内の位置がそのままセクションの順序）・**セクション名のテキスト**・**現在地の反転**（active だけ地と字を入れ替える）。色相は 4 つ目の手がかりとして乗っていただけで、無くても区別は落ちない。

逆に色相を使うと**畳まれた瞬間に区別が消える**。`--accent-*-vivid` は 5 つの名前として実在するが、report 経路（`vendor/scripts/render-report.js` の `:root`）では 5 つとも `--ink` へ倒してあり、hand-slide 経路の `:root` にはそもそも定義が無い（フォールバック無しの `var()` は宣言ごと無効になる）。**どちらの経路でも 5 色には成らない。**色が赤くなって気付ける類ではなく、静かに見分けが付かなくなる形なので、色相に分類を負わせないこと。

`.section-nav__dot` と `.section-nav__bar` は色相を載せるためだけの器だったので置かない。**空の器を残すと、次に色を戻す場所として使われる。**

### 17-A.2 CSS

以下は CSS トークン実体の差し替えが済むまで残る過渡的定義。`backdrop-filter` は使わず地色で塗る（SR-2-09）、ウェイトは 3 段のみ（SR-3-10）が確定方針で、**この 2 つはまだ下の定義に残っている**。色相で分類を示さない（SR-2-07）は上記のとおり解消済み。

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
  border-bottom: 1px solid var(--sumi-ink, #FAFAFA);
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
  font-weight: var(--fw-semibold, 600);
  color: var(--fg);
  opacity: 0.5;
  transition: opacity 0.3s ease, background 0.3s ease;
  white-space: nowrap;
}

.section-nav__item:hover { opacity: 0.8; background: var(--bg-dim, #F5F5F5); }
.section-nav__item:focus-visible { outline: 2px solid var(--fg); outline-offset: -2px; }
.section-nav__label { pointer-events: none; }

/* 現在地は反転（地と字を入れ替える）。濃度差だけに頼らないのは、
   opacity 0.5 → 1 の差が投影で潰れて「どれが現在地か」が消えるため */
.section-nav__item.active {
  opacity: 1;
  background: var(--fg);
  color: var(--bg-dark, var(--paper));
}
.section-nav__item.active:hover { background: var(--fg); }
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
    const isCurrent = item.dataset.section === section;
    item.classList.toggle('active', isCurrent);
    // 反転は見た目の手がかりなので、読み上げ側の現在地も同じ 1 箇所で切り替える
    if (isCurrent) { item.setAttribute('aria-current', 'true'); }
    else { item.removeAttribute('aria-current'); }
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
ダークテーマ用。

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

状態は **通常 / 現在地 / hover の 3 つに閉じる**。以前はここに 4 つ目（現在地に hover）が
独立した見た目で存在したが、現在地の手がかりを hover が上書きするので、指を置いた瞬間に
「どれが現在地か」が消えていた。現在地に hover したときは反転のままにする。

分類を色相で示さない（SR-2-07）。左端の帯で色を切り替える作りは、帯が細いので
**投影では色そのものが判別できず、状態の差が消える**。行全体の反転へ置き換えた。
帯やドットだけを反転させないのは、細い面の反転が投影で「汚れ」に見えるため。
反転が効くのは面積があるときだけ。

なお、ここにあった 3 つの旧値は `rgba()` の生値で書かれていたため、
**`css-var-fallback` の網に掛からなかった**（あの検査が見るのは `var()` の中身だけで、
生の色は素通りする）。同じ形の値は他にも残っている想定で扱うこと。

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

/* 各アジェンダ項目（リンク）。状態は 3 つに閉じる:
   通常 / 現在地（行全体の反転）/ hover（`--tone-2` の地）。
   反転は行全体に掛ける。帯やドットだけを反転させると、細い面の反転は
   投影で「汚れ」に見えて、状態ではなく印刷の事故として読まれる */
.agenda-indicator-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  background: var(--ink, #141412);
  border-radius: 8px;
  cursor: pointer;
  text-decoration: none;
  color: var(--fg-muted);
  transition: all 0.3s ease;
}

/* ホバー状態。現在地とは別の面（濃度段の中位）を当てる */
.agenda-indicator-item:hover {
  background: var(--tone-2, #9BADBF);
  color: var(--ink, #141412);
  transform: translateX(5px);
}

/* 現在地（現在のセクション）。地と字を入れ替える。
   §17-A と同じ反転の作りで、色相は使わない */
.agenda-indicator-item.active {
  background: var(--fg);
  color: var(--bg-dark, var(--paper));
}

/* 現在地に hover しても反転のまま。ここで hover 側の面へ移ると
   「現在地がどれか」が指の下で消える */
.agenda-indicator-item.active:hover {
  background: var(--fg);
  color: var(--bg-dark, var(--paper));
}

.agenda-indicator-item:focus-visible {
  outline: 2px solid var(--fg);
  outline-offset: -2px;
}

/* 番号バッジ。地を持たず輪郭だけにして `currentColor` に追随させる。
   こうすると行が反転したときバッジも一緒に反転し、状態ごとの指定が要らない。
   状態ごとの器を残すと、次に色を戻す場所として使われる */
.agenda-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: 1.25px solid currentColor;
  border-radius: 50%;
  font-size: var(--fs-small);
  font-weight: 700;
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
