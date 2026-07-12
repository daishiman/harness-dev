# スライドインタラクション

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは GSAP 実装テンプレート・パターン集。規則の正本は SR-ID で参照すること

**責務**: ホバーエフェクト・アジェンダインジケーター・TweenSliderクラス・アニメーション定義の**実装**。
**規則の正本**: §6 GSAP（[SR-6-01](spec-registry.md#sr-6-01)〜[SR-6-08](spec-registry.md#sr-6-08)）。特に scale 下限 → [SR-6-01](spec-registry.md#sr-6-01)、clearProps → [SR-6-02](spec-registry.md#sr-6-02) / [SR-6-03](spec-registry.md#sr-6-03)、fo-card → [SR-6-04](spec-registry.md#sr-6-04)、イージング3種以上 → [SR-6-05](spec-registry.md#sr-6-05)、duration 標準値 → [SR-6-06](spec-registry.md#sr-6-06) / [SR-6-07](spec-registry.md#sr-6-07)、reduced-motion → [SR-6-08](spec-registry.md#sr-6-08)

---


## 4. ホバーエフェクト

### 4.0 ユニバーサルカードホバー（必須）

**すべてのカード・ボックス要素にホバーエフェクトを適用すること。**

ホバーなしのカードとありのカードが混在すると統一感がなくなる。以下のユニバーサルCSSをテンプレートに含め、全カード要素に一括適用する。

```css
/* ===== ユニバーサルカードホバー（必須適用） ===== */

/* 全カード要素の基本ホバー */
.list-item,
.compare-item,
.flow-step,
.timeline-content,
.stat-card,
.grid-card,
.icon-grid-item,
.process-step,
.pyramid-level,
.circle-item,
.circle-center,
.highlight-card,
.quote-box,
.hero-card,
.cycle-item,
.snake-item,
.venn-circle,
.mindmap-node,
.fc-node,
.growth-point,
.comparison-card,
.matrix-cell,
.gantt-bar,
.ps-list li,
.vp-card,
.pc-card,
.cc-layer,
.rm-card,
.vs-layer,
.aidma-cell,
.funnel-level,
.org-node,
.chevron-step,
.pn-node,
.vs-step-content,
.pdca-quadrant,
.tc-node,
.ws-card,
.ig-item {
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease;
  cursor: pointer;
}

/* 統一ホバーエフェクト */
.list-item:hover,
.compare-item:hover,
.flow-step:hover,
.timeline-content:hover,
.stat-card:hover,
.grid-card:hover,
.icon-grid-item:hover,
.process-step:hover,
.pyramid-level:hover,
.circle-item:hover,
.highlight-card:hover,
.quote-box:hover,
.hero-card:hover,
.cycle-item:hover,
.snake-item:hover,
.venn-circle:hover,
.mindmap-node:hover,
.fc-node:hover,
.growth-point:hover,
.comparison-card:hover,
.matrix-cell:hover,
.ps-list li:hover,
.vp-card:hover,
.pc-card:hover,
.cc-layer:hover,
.rm-card:hover,
.vs-layer:hover,
.aidma-cell:hover,
.funnel-level:hover,
.org-node:hover,
.pn-node:hover,
.vs-step-content:hover,
.pdca-quadrant:hover,
.tc-node:hover,
.ws-card:hover,
.ig-item:hover {
  transform: translateY(-5px) scale(1.02);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
}

/* 縦移動が不適切な要素（横移動に変更） */
.timeline-content:hover,
.vs-layer:hover,
.vs-step-content:hover,
.ps-list li:hover {
  transform: translateX(8px) scale(1.02);
}

/* 中心要素（拡大のみ） */
.circle-center:hover {
  transform: translate(-50%, -50%) scale(1.1);
}

/* ファネル・シェブロン（明るさ変化） */
.funnel-level:hover,
.chevron-step:hover,
.gantt-bar:hover {
  filter: brightness(1.15);
}
```

**統一ホバールール**:
- **transform**: `translateY(-5px) scale(1.02)` が基本
- **box-shadow**: `0 10px 30px rgba(0,0,0,0.25)` で浮遊感
- **transition**: 0.3s ease で滑らか
- **cursor**: pointer で操作可能を示す

### 4.1 基本ホバークラス

```css
/* 基本ホバー - 拡大 + 影 */
.hoverable {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  cursor: pointer;
}

.hoverable:hover {
  transform: scale(1.05);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

/* 控えめホバー - 小さめの拡大 */
.hoverable-subtle {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.hoverable-subtle:hover {
  transform: scale(1.02);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

/* 強調ホバー - ボーダーハイライト */
.hoverable-highlight {
  transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
  border: 2px solid transparent;
}

.hoverable-highlight:hover {
  transform: scale(1.03);
  border-color: var(--wave-blue);
  box-shadow: 0 0 20px rgba(126, 156, 216, 0.3);
}

/* グロー効果 */
.hoverable-glow {
  transition: transform 0.3s ease, filter 0.3s ease;
}

.hoverable-glow:hover {
  transform: scale(1.05);
  filter: drop-shadow(0 0 15px var(--wave-blue));
}
```

### 4.2 カードホバー（スライドタイプ別）

```css
/* リストアイテムカード */
.slide-list .list-item {
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-left-color 0.3s ease;
}

.slide-list .list-item:hover {
  transform: translateX(10px) scale(1.02);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
  border-left-color: var(--sakura-pink);
}

/* 比較カード */
.slide-compare .compare-item {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-compare .compare-item:hover {
  transform: translateY(-10px) scale(1.03);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
}

/* フローステップ */
.slide-flow .flow-step {
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.slide-flow .flow-step:hover {
  transform: scale(1.1);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  background: var(--bg-card);
}

/* タイムラインアイテム */
.slide-timeline .timeline-content {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-timeline .timeline-content:hover {
  transform: translateX(10px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}

/* 統計カード */
.slide-stats .stat-card {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-stats .stat-card:hover {
  transform: translateY(-15px) scale(1.05);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
}

/* グリッドカード */
.slide-grid .grid-card {
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}

.slide-grid .grid-card:hover {
  transform: scale(1.05);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
  border-color: var(--wave-blue);
}
```

### 4.3 アイコンホバー

```css
/* アイコンラッパー */
.icon-wrapper {
  transition: transform 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
}

.icon-wrapper:hover {
  transform: scale(1.15) rotate(5deg);
  background: var(--wave-blue);
  box-shadow: 0 10px 30px rgba(126, 156, 216, 0.4);
}

.icon-wrapper:hover i {
  color: var(--bg-dark);
}

/* アイコン単体 */
.hoverable-icon {
  transition: transform 0.3s ease, color 0.3s ease, filter 0.3s ease;
}

.hoverable-icon:hover {
  transform: scale(1.2);
  color: var(--sakura-pink);
  filter: drop-shadow(0 0 10px currentColor);
}

/* 回転アイコン */
.hoverable-icon-spin:hover {
  transform: rotate(360deg);
  transition: transform 0.6s ease;
}

/* パルスアイコン */
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.hoverable-icon-pulse:hover {
  animation: pulse 0.6s ease infinite;
}
```

### 4.4 統計値ホバー

```css
/* 大きな数値 */
.stat-value {
  transition: transform 0.3s ease, color 0.3s ease, text-shadow 0.3s ease;
}

.stat-card:hover .stat-value {
  transform: scale(1.1);
  text-shadow: 0 0 30px currentColor;
}

/* 進捗バー付き統計 */
.stat-progress {
  height: 6px;
  background: var(--bg-dim);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 0.5rem;
}

.stat-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--wave-blue), var(--sakura-pink));
  transition: width 0.8s ease;
}

.stat-card:hover .stat-progress-bar {
  filter: brightness(1.2);
}
```

### 4.5 テーブル行ホバー

```css
/* テーブル行 */
.slide-table tbody tr {
  transition: background 0.2s ease, transform 0.2s ease;
}

.slide-table tbody tr:hover {
  background: var(--bg-card);
  transform: scale(1.01);
}

/* セルホバー */
.slide-table td {
  transition: color 0.2s ease;
}

.slide-table tbody tr:hover td {
  color: var(--wave-blue);
}

/* 強調行 */
.slide-table tr.highlight {
  background: var(--bg-card);
  border-left: 4px solid var(--sakura-pink);
}

.slide-table tr.highlight:hover {
  background: var(--sumi-ink);
}
```

### 4.6 ツールチップ

```css
/* ツールチップコンテナ */
.has-tooltip {
  position: relative;
  cursor: help;
}

/* ツールチップ本体 */
.has-tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%) translateY(5px);
  background: var(--sumi-ink);
  color: var(--fg);
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.9rem;
  white-space: nowrap;
  max-width: 300px;
  white-space: normal;
  text-align: center;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, transform 0.3s ease;
  z-index: 1000;
  box-shadow: 0 5px 20px rgba(0, 0, 0, 0.4);
  border: 1px solid var(--fuji-gray);
  pointer-events: none;
}

/* ツールチップ矢印 */
.has-tooltip::before {
  content: '';
  position: absolute;
  bottom: calc(100% + 2px);
  left: 50%;
  transform: translateX(-50%);
  border: 8px solid transparent;
  border-top-color: var(--sumi-ink);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease;
  z-index: 1001;
}

/* ホバー時に表示 */
.has-tooltip:hover::after,
.has-tooltip:hover::before {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(0);
}

/* 下向きツールチップ */
.has-tooltip-bottom::after {
  bottom: auto;
  top: calc(100% + 10px);
  transform: translateX(-50%) translateY(-5px);
}

.has-tooltip-bottom::before {
  bottom: auto;
  top: calc(100% + 2px);
  border-top-color: transparent;
  border-bottom-color: var(--sumi-ink);
}

.has-tooltip-bottom:hover::after {
  transform: translateX(-50%) translateY(0);
}

/* カラーバリエーション */
.has-tooltip-blue::after {
  background: var(--wave-blue);
  border-color: var(--wave-blue);
}

.has-tooltip-pink::after {
  background: var(--sakura-pink);
  border-color: var(--sakura-pink);
}

.has-tooltip-yellow::after {
  background: var(--autumn-yellow);
  color: var(--bg-dark);
  border-color: var(--autumn-yellow);
}
```

### 4.7 使用ガイドライン

| 要素タイプ | 推奨クラス | 備考 |
|-----------|-----------|------|
| リストアイテム | `hoverable` | 左移動 + 拡大 |
| カード | `hoverable` + `has-tooltip` | 補足情報付き |
| フローステップ | `hoverable-highlight` | ボーダーハイライト |
| 統計カード | `hoverable` + `has-tooltip` | 詳細説明付き |
| アイコン | `hoverable-icon` | 拡大 + 色変化 |
| テーブル行 | 自動適用 | CSS定義済み |

**注意事項**:
1. 過度な使用を避ける - 全要素にホバーを付けると煩雑
2. 意味のある情報を - ツールチップには有用な補足情報を入れる
3. モバイル考慮 - タッチデバイスではホバーが機能しない
4. パフォーマンス - transform/opacityを使用し、レイアウト変更を避ける

---

## 5. アジェンダインジケーター

### 概要

各スライドで現在のセクション位置を表示するコンポーネント。左上に固定配置し、現在のセクションをハイライト表示する。

### CSS

```css
.agenda-indicator {
  position: fixed;
  top: var(--nav-top-padding);
  left: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  z-index: 100;
  background: rgba(31, 31, 40, 0.9);
  padding: 0.8rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--fuji-gray);
}

.agenda-indicator-item {
  font-size: 1rem;
  color: var(--fg-dim);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  transition: all 0.3s ease;
  white-space: nowrap;
  cursor: pointer;
  border-left: 3px solid transparent;
}

/* ホバー状態（クリック可能を示す） */
.agenda-indicator-item:hover {
  color: var(--fg);
  background: rgba(126, 156, 216, 0.1);
  border-left-color: var(--wave-blue);
  transform: translateX(3px);
}

.agenda-indicator-item.is-active {
  color: var(--autumn-yellow);
  background: rgba(220, 165, 97, 0.15);
  border-left: 3px solid var(--autumn-yellow);
  padding-left: 0.5rem;
  font-weight: bold;
}

.agenda-indicator-item.is-active:hover {
  border-left-color: var(--sakura-pink);
}

.agenda-indicator-item.is-passed {
  color: var(--wave-aqua);
}
```

### HTML

```html
<div class="agenda-indicator" id="agendaIndicator">
  <div class="agenda-indicator-item" data-section="0">イントロ</div>
  <div class="agenda-indicator-item" data-section="1">セクション名1</div>
  <div class="agenda-indicator-item" data-section="2">セクション名2</div>
</div>
```

### JavaScript

TweenSliderクラスに`updateAgenda`メソッドとクリックナビゲーション機能を追加する。

```javascript
// コンストラクタまたはinitで呼び出す
bindAgendaEvents() {
  const agendaItems = document.querySelectorAll('.agenda-indicator-item');
  agendaItems.forEach(item => {
    item.addEventListener('click', () => {
      const sectionIndex = parseInt(item.dataset.section);
      const targetSlide = this.getSectionStartSlide(sectionIndex);
      this.goToSlide(targetSlide);
    });
  });
}

// セクションの開始スライドインデックスを返す
getSectionStartSlide(sectionIndex) {
  // プロジェクトごとにカスタマイズ
  const sectionStarts = [0, 2, 6, 13, 22, 30]; // 例
  return sectionStarts[sectionIndex] || 0;
}

updateAgenda() {
  // セクションの範囲定義（プロジェクトごとにカスタマイズ）
  const sectionRanges = [
    { section: 0, start: 0, end: 1 },
    { section: 1, start: 2, end: 5 },
    { section: 2, start: 6, end: 12 },
    // ...以降のセクション
  ];

  const currentSection = sectionRanges.find(
    range => this.currentIndex >= range.start && this.currentIndex <= range.end
  );

  const agendaItems = document.querySelectorAll('.agenda-indicator-item');
  agendaItems.forEach((item, i) => {
    item.classList.remove('is-active', 'is-passed');
    if (currentSection && i === currentSection.section) {
      item.classList.add('is-active');
    } else if (currentSection && i < currentSection.section) {
      item.classList.add('is-passed');
    }
  });
}

// updateProgress メソッド内で呼び出す
updateProgress() {
  const progress = ((this.index + 1) / this.items.length) * 100;
  document.getElementById('progress').style.width = progress + '%';
  this.updateAgenda(); // アジェンダ更新を追加
}
```

### フォントサイズのグローバル管理

- **原則**: ブロックごとの個別設定は避け、CSS変数で統一管理
- **微調整**: 必要な場合のみ（収まらない場合のみ縮小）
- **CSS変数**: `--fs-small`, `--fs-body`, `--fs-heading` などを活用

```css
/* 推奨: CSS変数を使用 */
.agenda-indicator-item {
  font-size: var(--fs-small);
}

/* 非推奨: 固定値を直接指定 */
.agenda-indicator-item {
  font-size: 0.9rem;
}
```

---

## 6. TweenSliderクラス

```javascript
class TweenSlider {
  constructor(selector) {
    this.container = document.querySelector(selector + ' .slider__container');
    this.items = document.querySelectorAll(selector + ' .slider__item');
    this.index = 0;
    this.isAnimating = false;
    this.slideWidth = window.innerWidth;

    this.init();
  }

  init() {
    this.buildNavigation();
    this.bindEvents();
    this.makeActive(0);
    this.playEnterAnimation(0);
    this.updateProgress();
  }

  buildNavigation() {
    const nav = document.getElementById('navigation');
    this.items.forEach((_, i) => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = '#' + i;
      a.dataset.index = i;
      // 5個ごと・10個ごとにマーカークラスを追加（1始まりで計算）
      const slideNum = i + 1;
      if (slideNum % 10 === 0) {
        a.classList.add('nav-mark-10');  // 10, 20, 30...：大きく、オレンジ
      } else if (slideNum % 5 === 0) {
        a.classList.add('nav-mark-5');   // 5, 15, 25...：少し大きく、アクア
      }
      a.addEventListener('click', (e) => {
        e.preventDefault();
        this.move(i);
      });
      li.appendChild(a);
      nav.appendChild(li);
    });
  }

  bindEvents() {
    document.getElementById('next').addEventListener('click', () => this.moveToNext());
    document.getElementById('prev').addEventListener('click', () => this.moveToPrev());

    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault();
        this.moveToNext();
      }
      if (e.key === 'ArrowLeft') this.moveToPrev();
    });

    window.addEventListener('resize', () => {
      this.slideWidth = window.innerWidth;
      gsap.set(this.container, { x: -this.index * this.slideWidth });
    });

    // スワイプ対応（モバイル）
    this.bindSwipeEvents();
  }

  // 横スワイプ対応（デフォルト有効）
  bindSwipeEvents() {
    let touchStartX = 0;
    let touchStartY = 0;
    const minSwipeDistance = 50;
    const target = this.slideArea || this.slider;

    target.addEventListener('touchstart', (e) => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    target.addEventListener('touchend', (e) => {
      const touchEndX = e.changedTouches[0].screenX;
      const touchEndY = e.changedTouches[0].screenY;
      const diffX = touchStartX - touchEndX;
      const diffY = Math.abs(touchStartY - touchEndY);

      // 横方向のスワイプのみ反応（縦スクロールを妨げない）
      if (Math.abs(diffX) > minSwipeDistance && Math.abs(diffX) > diffY) {
        if (diffX > 0) {
          this.moveToNext();
        } else {
          this.moveToPrev();
        }
      }
    }, { passive: true });
  }

  makeActive(index) {
    const navItems = document.querySelectorAll('.slider-navigation a');
    this.items.forEach((item, i) => {
      item.classList.toggle('is-active', i === index);
      navItems[i]?.classList.toggle('is-active', i === index);
    });
  }

  getSlideType(slide) {
    const classes = slide.className.split(' ');
    for (const cls of classes) {
      if (cls.startsWith('slide-') && cls !== 'slider__item') {
        return cls;
      }
    }
    return 'slide-message';
  }

  playEnterAnimation(index) {
    const slide = this.items[index];
    const content = slide.querySelector('.slider__content');
    const type = this.getSlideType(slide);

    if (animations[type] && animations[type].enter) {
      return animations[type].enter(content);
    } else {
      gsap.set(content, { visibility: 'visible' });
      return gsap.timeline();
    }
  }

  playLeaveAnimation(index) {
    const slide = this.items[index];
    const content = slide.querySelector('.slider__content');
    const type = this.getSlideType(slide);

    if (animations[type] && animations[type].leave) {
      return animations[type].leave(content);
    } else {
      return gsap.timeline();
    }
  }

  async move(index) {
    if (this.isAnimating || index === this.index || index < 0 || index >= this.items.length) {
      return;
    }

    this.isAnimating = true;

    const masterTl = gsap.timeline({
      onComplete: () => {
        this.isAnimating = false;
      }
    });

    masterTl.add(this.playLeaveAnimation(this.index));

    masterTl.to(this.container, {
      x: -index * this.slideWidth,
      duration: 0.6,
      ease: 'power3.inOut'
    }, '-=0.2');

    masterTl.add(this.playEnterAnimation(index), '-=0.3');

    this.index = index;
    this.makeActive(index);
    this.updateProgress();
  }

  // ループナビゲーション（デフォルト有効）
  moveToNext() {
    // 最後のスライド → 最初へループ
    const nextIndex = (this.index + 1) % this.items.length;
    this.move(nextIndex);
  }

  moveToPrev() {
    // 最初のスライド → 最後へループ
    const prevIndex = (this.index - 1 + this.items.length) % this.items.length;
    this.move(prevIndex);
  }

  updateProgress() {
    const progress = ((this.index + 1) / this.items.length) * 100;
    document.getElementById('progress').style.width = progress + '%';
    this.updateAgenda();
  }

  updateAgenda() {
    const agendaItems = document.querySelectorAll('.agenda-indicator-item');
    const currentSlide = this.items[this.index];
    const currentSection = currentSlide.dataset.section;

    agendaItems.forEach(item => {
      const itemSection = item.dataset.section;

      if (itemSection === currentSection) {
        item.classList.add('is-active');
        item.classList.remove('is-passed');
      } else if (parseInt(itemSection) < parseInt(currentSection)) {
        item.classList.add('is-passed');
        item.classList.remove('is-active');
      } else {
        item.classList.remove('is-active', 'is-passed');
      }
    });
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  new TweenSlider('#slider');
});
```

---

## 6.5 GSAP安全パターン（必須）

### 6.5.1 scale: 0 禁止ルール

**GSAPの `from` アニメーションで `scale: 0` を使用してはならない。**

`scale: 0` はインラインの `transform: matrix(0, 0, 0, 0, ...)` スタイルを要素に残し、スライド遷移後に `clearProps` で完全にリセットされない場合がある。結果、要素が見えない・サイズが不正になるバグが発生する。

```javascript
// NG: scale: 0 は残留インラインスタイルの原因
tl.from(q('.ig-item'), {
  scale: 0, opacity: 0, duration: 0.35 * D,
  ease: 'back.out(1.7)', stagger: 0.08 * S
});

// OK: x または y 方向の移動で代替
tl.from(q('.ig-item'), {
  x: -30, opacity: 0, duration: 0.3 * D,
  ease: 'back.out(1.7)', stagger: 0.08 * S
});

// OK: scaleを使う場合は 0.8 以上から開始
tl.from(q('.slider__content > *'), {
  scale: 0.8, opacity: 0, duration: 0.4 * D,
  ease: 'power2.out', stagger: 0.06 * S
});
```

**許容される最小scale値**: `0.8`（`scale: 0` や `scale: 0.5` 等の極端な値は禁止）

### 6.5.2 clearProps 安全適用（必須）

スライド遷移時にGSAPが残すインラインスタイルを除去する。ただし **`content.querySelectorAll('*')` での包括クリアは禁止** — SVG要素の `fill`/`stroke` 属性やforeignObject内のレイアウトスタイルも破壊し、図解が黒塗りになるバグを引き起こす。

**安全なclearPropsルール**:
- `content.children`（直下の子要素のみ）に対して `clearProps: 'all'` を適用
- `content.querySelectorAll('*')` は **絶対に使わない**（SVG破壊の原因）
- foreignObject内のdivは `class="fo-card"` でCSSクラスベースのレイアウトを適用し、clearPropsでインラインスタイルが消えても表示を維持

**updateSlide() 内の clearProps**:
```javascript
updateSlide(index, animate = true) {
  this.items.forEach((item, i) => {
    const content = item.querySelector('.slider__content');
    if (content) {
      content.style.visibility = i === index ? 'visible' : 'hidden';
      if (i === index) {
        // 直下の子要素のみクリア（SVG内部には触れない）
        gsap.set(content.children, { clearProps: 'all' });
        // NG: gsap.set(content.querySelectorAll('*'), { clearProps: 'all' });
        // → SVGのfill/strokeがデフォルト黒になり、foreignObjectのflexレイアウトが崩壊する
      }
    }
  });
  if (animate) this.enterAnimation(this.items[index]);
}
```

**leaveAnimation() 内の clearProps（必須）**:
```javascript
leaveAnimation(slideEl) {
  return new Promise((resolve) => {
    const content = slideEl.querySelector('.slider__content');
    if (!content) { resolve(); return; }

    gsap.to(content.children, {
      opacity: 0, duration: 0.15 * D,
      ease: 'power1.inOut',
      stagger: 0,
      onComplete: () => {
        // 直下の子要素のみクリア（SVG内部には触れない）
        gsap.set(content.children, { clearProps: 'all' });
        resolve();
      }
    });
  });
}
```

### 6.5.2.1 foreignObject CSS保護パターン（必須）

SVG内のforeignObjectで使うdivレイアウトは、インラインstyleではなくCSSクラスで定義する。clearPropsはインラインスタイルのみ除去するため、CSSクラスのスタイルは保護される。

**styles.css に必須追加**:
```css
/* foreignObject card layout — CSS class protects against GSAP clearProps */
.fo-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px;
  text-align: center;
  font-family: 'Noto Sans JP', sans-serif;
  background: transparent;
}
.fo-card span { display: block; }
.fo-card i { display: inline-block; }

/* バリエーション: 横並び（アイコン+テキスト） */
.fo-card--row {
  flex-direction: row;
  gap: 6px;
}
```

**クラス選択ガイド**:

| レイアウト | クラス | 用途 |
|-----------|--------|------|
| 縦中央寄せ | `fo-card` | ラベル、タイトル、中央テキスト |
| 横並び | `fo-card fo-card--row` | アイコン+テキスト、バッジ+ラベル |

**装飾スタイルの扱い**:
- `color`, `font-size`, `font-weight`, `gap`（row時）等の装飾プロパティはstyle属性で追加OK
- `display`, `flex-direction`, `align-items`, `justify-content`, `width`, `height` 等のレイアウトプロパティはCSSクラス必須（style属性での単独定義禁止）

**HTML内のforeignObject div**:
```html
<!-- NG: インラインstyleのみ（clearPropsで破壊される） -->
<foreignObject x="8" y="8" width="144" height="64">
  <div xmlns="http://www.w3.org/1999/xhtml"
       style="display:flex;align-items:center;justify-content:center;height:100%;gap:8px;">
    <span>テキスト</span>
  </div>
</foreignObject>

<!-- OK: CSSクラスで保護（装飾プロパティはstyle属性で追加可） -->
<foreignObject x="8" y="8" width="144" height="64">
  <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card"
       style="font-size:1.4rem;font-weight:700;">
    <span>テキスト</span>
  </div>
</foreignObject>

<!-- OK: アイコン横並び -->
<foreignObject x="8" y="8" width="144" height="64">
  <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
       style="color:var(--fg-default,#DCD7BA);font-size:1.3rem;">
    <i class="fas fa-check" style="color:var(--spring-green,#98BB6C)"></i>
    <span>テキスト</span>
  </div>
</foreignObject>
```

### 6.5.3 prefers-reduced-motion 対応

GSAPアニメーションは `prefers-reduced-motion` を尊重する。scripts.js の冒頭で以下のグローバル変数を定義する:

```javascript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const D = prefersReducedMotion ? 0.01 : 1;  // duration倍率
const S = prefersReducedMotion ? 0 : 1;     // stagger倍率
```

全GSAPアニメーションで `duration: 0.3 * D`, `stagger: 0.05 * S` のように倍率を適用する。

---

## 7. アニメーション定義

すべてのスライドタイプのアニメーション定義は`animations`オブジェクトにまとめる。

各タイプに`enter`と`leave`関数を定義:

```javascript
const animations = {
  'slide-title': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-message': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-list': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-compare': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-flow': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-timeline': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-table': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-pyramid': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-circle': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-grid': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-highlight': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-icon-grid': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-process': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-quote': { enter: (content) => {...}, leave: (content) => {...} },
  'slide-hero': { enter: (content) => {...}, leave: (content) => {...} }
};
```

---

