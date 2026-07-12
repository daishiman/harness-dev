# 拡張スライドタイプ

**責務**: 拡張8種のスライドタイプ（ピラミッド、サークル、グリッド、ハイライト、アイコングリッド、プロセス、引用、ヒーロー）のCSS・HTMLテンプレート

---


## 3. 拡張スライド詳細

### 3.1 ピラミッドスライド

階層構造を視覚的に表現。上から下へ重要度/範囲が広がる。

```css
.slide-pyramid .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-pyramid .pyramid-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-pyramid .pyramid-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  max-width: 800px;
}

.slide-pyramid .pyramid-level {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 2rem;
  border-radius: 8px;
  text-align: center;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-pyramid .pyramid-level:hover {
  transform: scale(1.05);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

/* レベル別スタイル */
.slide-pyramid .pyramid-level-1 { width: 30%; background: var(--sakura-pink); color: var(--bg-dark); font-weight: 700; }
.slide-pyramid .pyramid-level-2 { width: 50%; background: var(--autumn-yellow); color: var(--bg-dark); }
.slide-pyramid .pyramid-level-3 { width: 70%; background: var(--wave-aqua); color: var(--bg-dark); }
.slide-pyramid .pyramid-level-4 { width: 90%; background: var(--wave-blue); color: var(--bg-dark); }
```

```html
<div class="slider__item slide-pyramid">
  <div class="slider__content">
    <h2 class="pyramid-title"><i class="fas {{アイコン}}"></i> {{タイトル}}</h2>
    <div class="pyramid-container">
      <div class="pyramid-level pyramid-level-1 has-tooltip" data-tooltip="{{説明1}}">
        <i class="fas {{アイコン1}}"></i>
        <span>{{テキスト1}}</span>
      </div>
      <!-- レベル2-4繰り返し -->
    </div>
  </div>
</div>
```

### 3.2 サークルスライド

中心から放射状に広がる構成。中心概念と周辺要素の関係を表現。

```css
.slide-circle .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-circle .circle-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-circle .circle-container {
  position: relative;
  width: 500px;
  height: 500px;
}

.slide-circle .circle-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 150px;
  height: 150px;
  background: var(--sakura-pink);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--bg-dark);
  font-weight: 700;
  z-index: 10;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-circle .circle-center:hover {
  transform: translate(-50%, -50%) scale(1.1);
  box-shadow: 0 0 40px rgba(210, 126, 153, 0.5);
}

.slide-circle .circle-item {
  position: absolute;
  width: 120px;
  height: 120px;
  background: var(--bg-dim);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  border: 3px solid var(--wave-blue);
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}

.slide-circle .circle-item:hover {
  transform: scale(1.15);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  border-color: var(--sakura-pink);
}

/* 位置（6要素の場合） */
.slide-circle .circle-item:nth-child(2) { top: 0; left: 50%; transform: translateX(-50%); }
.slide-circle .circle-item:nth-child(3) { top: 25%; right: 5%; }
.slide-circle .circle-item:nth-child(4) { bottom: 25%; right: 5%; }
.slide-circle .circle-item:nth-child(5) { bottom: 0; left: 50%; transform: translateX(-50%); }
.slide-circle .circle-item:nth-child(6) { bottom: 25%; left: 5%; }
.slide-circle .circle-item:nth-child(7) { top: 25%; left: 5%; }
```

```html
<div class="slider__item slide-circle">
  <div class="slider__content">
    <h2 class="circle-title"><i class="fas {{アイコン}}"></i> {{タイトル}}</h2>
    <div class="circle-container">
      <div class="circle-center has-tooltip" data-tooltip="{{中心説明}}">
        <i class="fas {{中心アイコン}}"></i>
        <span>{{中心テキスト}}</span>
      </div>
      <div class="circle-item has-tooltip" data-tooltip="{{説明1}}">
        <i class="fas {{アイコン1}}"></i>
        <span>{{テキスト1}}</span>
      </div>
      <!-- 周辺要素繰り返し -->
    </div>
  </div>
</div>
```

### 3.3 グリッドスライド

均等なグリッドレイアウトでカードを配置。

```css
.slide-grid .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-grid .grid-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-grid .grid-container {
  display: grid;
  gap: 1.5rem;
  justify-content: center;
}

/* グリッド列数バリエーション */
.slide-grid .grid-container.grid-2 { grid-template-columns: repeat(2, 280px); }
.slide-grid .grid-container.grid-3 { grid-template-columns: repeat(3, 250px); }
.slide-grid .grid-container.grid-4 { grid-template-columns: repeat(4, 200px); }

.slide-grid .grid-card {
  background: var(--bg-dim);
  padding: 2rem;
  border-radius: 16px;
  text-align: center;
  border: 2px solid transparent;
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}

.slide-grid .grid-card:hover {
  transform: translateY(-10px) scale(1.03);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
  border-color: var(--wave-blue);
}

/* カラーバリエーション */
.slide-grid .grid-card.card-pink { border-top: 4px solid var(--sakura-pink); }
.slide-grid .grid-card.card-pink i { color: var(--sakura-pink); }
.slide-grid .grid-card.card-aqua { border-top: 4px solid var(--wave-aqua); }
.slide-grid .grid-card.card-aqua i { color: var(--wave-aqua); }
.slide-grid .grid-card.card-yellow { border-top: 4px solid var(--autumn-yellow); }
.slide-grid .grid-card.card-yellow i { color: var(--autumn-yellow); }
```

```html
<div class="slider__item slide-grid">
  <div class="slider__content">
    <h2 class="grid-title"><i class="fas {{アイコン}}"></i> {{タイトル}}</h2>
    <div class="grid-container grid-3">
      <div class="grid-card card-pink has-tooltip" data-tooltip="{{説明1}}">
        <i class="fas {{アイコン1}}"></i>
        <h3>{{見出し1}}</h3>
        <p>{{テキスト1}}</p>
      </div>
      <!-- 繰り返し -->
    </div>
  </div>
</div>
```

### 3.4 ハイライトスライド

1つの重要な情報を大きく強調表示。

```css
.slide-highlight .slider__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  text-align: center;
}

.slide-highlight .highlight-icon {
  width: 150px;
  height: 150px;
  background: linear-gradient(135deg, var(--wave-blue), var(--sakura-pink));
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-highlight .highlight-icon:hover {
  transform: scale(1.1) rotate(5deg);
  box-shadow: 0 0 50px rgba(126, 156, 216, 0.5);
}

.slide-highlight .highlight-icon i {
  font-size: 4rem;
  color: var(--bg-dark);
}

.slide-highlight .highlight-value {
  font-size: calc(var(--fs-title) * 1.5);
  font-weight: 700;
  background: linear-gradient(135deg, var(--wave-blue), var(--sakura-pink));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.slide-highlight .highlight-label {
  font-size: var(--fs-subtitle);
  color: var(--fg-dim);
}

.slide-highlight .highlight-description {
  font-size: var(--fs-body);
  max-width: 600px;
  line-height: 1.6;
}
```

```html
<div class="slider__item slide-highlight">
  <div class="slider__content">
    <div class="highlight-icon has-tooltip" data-tooltip="{{アイコン説明}}">
      <i class="fas {{アイコン}}"></i>
    </div>
    <div class="highlight-value">{{大きな値}}</div>
    <div class="highlight-label">{{ラベル}}</div>
    <p class="highlight-description">{{説明文}}</p>
  </div>
</div>
```

### 3.5 アイコングリッドスライド

アイコンを主体にしたシンプルなグリッド表示。

```css
.slide-icon-grid .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-icon-grid .icon-grid-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-icon-grid .icon-grid-container {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2rem;
  max-width: 900px;
  margin: 0 auto;
}

.slide-icon-grid .icon-grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1.5rem;
  background: var(--bg-dim);
  border-radius: 12px;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-icon-grid .icon-grid-item:hover {
  transform: translateY(-10px) scale(1.05);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
}

.slide-icon-grid .icon-grid-item i {
  font-size: 2.5rem;
  color: var(--wave-blue);
  transition: transform 0.3s ease, color 0.3s ease;
}

.slide-icon-grid .icon-grid-item:hover i {
  transform: scale(1.2);
  color: var(--sakura-pink);
}
```

```html
<div class="slider__item slide-icon-grid">
  <div class="slider__content">
    <h2 class="icon-grid-title"><i class="fas {{アイコン}}"></i> {{タイトル}}</h2>
    <div class="icon-grid-container">
      <div class="icon-grid-item has-tooltip" data-tooltip="{{説明1}}">
        <i class="fas {{アイコン1}}"></i>
        <span>{{テキスト1}}</span>
      </div>
      <!-- 繰り返し -->
    </div>
  </div>
</div>
```

### 3.6 プロセススライド（縦）

縦方向のプロセス/ステップ表示。

```css
.slide-process .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-process .process-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-process .process-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  max-width: 600px;
  margin: 0 auto;
}

.slide-process .process-step {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  width: 100%;
  padding: 1.5rem;
  background: var(--bg-dim);
  border-radius: 12px;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-process .process-step:hover {
  transform: scale(1.03) translateX(10px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

.slide-process .process-number {
  width: 50px;
  height: 50px;
  background: var(--wave-blue);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.5rem;
  flex-shrink: 0;
}

.slide-process .process-arrow {
  display: flex;
  justify-content: center;
  padding: 0.5rem;
  color: var(--autumn-yellow);
  font-size: 1.5rem;
}
```

```html
<div class="slider__item slide-process">
  <div class="slider__content">
    <h2 class="process-title"><i class="fas {{アイコン}}"></i> {{タイトル}}</h2>
    <div class="process-container">
      <div class="process-step has-tooltip" data-tooltip="{{説明1}}">
        <div class="process-number">1</div>
        <div class="process-content">
          <h4><i class="fas {{アイコン1}}"></i> {{見出し1}}</h4>
          <p>{{テキスト1}}</p>
        </div>
      </div>
      <div class="process-arrow"><i class="fas fa-arrow-down"></i></div>
      <!-- 繰り返し -->
    </div>
  </div>
</div>
```

### 3.7 引用スライド

印象的な引用文を大きく表示。

```css
.slide-quote .slider__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 2rem;
}

.slide-quote .quote-mark {
  font-size: 6rem;
  color: var(--wave-blue);
  opacity: 0.3;
  line-height: 1;
}

.slide-quote .quote-text {
  font-size: var(--fs-subtitle);
  font-style: italic;
  max-width: 800px;
  line-height: 1.6;
}

.slide-quote .quote-author {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
}

.slide-quote .quote-author-avatar {
  width: 60px;
  height: 60px;
  background: var(--bg-dim);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.slide-quote .quote-author-avatar i {
  font-size: 1.5rem;
  color: var(--wave-aqua);
}

.slide-quote .quote-author-name {
  font-size: var(--fs-body-lg);
  font-weight: 700;
}

.slide-quote .quote-author-title {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}
```

```html
<div class="slider__item slide-quote">
  <div class="slider__content">
    <div class="quote-mark">"</div>
    <p class="quote-text">{{引用文}}</p>
    <div class="quote-author">
      <div class="quote-author-avatar">
        <i class="fas {{著者アイコン}}"></i>
      </div>
      <div class="quote-author-info">
        <div class="quote-author-name">{{著者名}}</div>
        <div class="quote-author-title">{{著者肩書}}</div>
      </div>
    </div>
  </div>
</div>
```

### 3.8 ヒーロースライド

大きな背景/グラデーションと重ねてテキストを表示。

```css
.slide-hero {
  position: relative;
}

.slide-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(31, 31, 40, 0.9), rgba(42, 42, 55, 0.8));
  z-index: 1;
}

.slide-hero .slider__content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 2rem;
}

.slide-hero .hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--wave-blue);
  color: var(--bg-dark);
  padding: 0.5rem 1.5rem;
  border-radius: 50px;
  font-weight: 700;
  font-size: var(--fs-small);
}

.slide-hero .hero-title {
  font-size: calc(var(--fs-title) * 1.2);
  font-weight: 700;
  background: linear-gradient(135deg, var(--fg), var(--wave-blue));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.slide-hero .hero-subtitle {
  font-size: var(--fs-subtitle);
  color: var(--fg-dim);
  max-width: 600px;
}

.slide-hero .hero-cta {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.slide-hero .hero-button {
  padding: 1rem 2rem;
  border-radius: 8px;
  font-weight: 700;
  font-size: var(--fs-body);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  border: none;
  cursor: pointer;
}

.slide-hero .hero-button:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

.slide-hero .hero-button-primary {
  background: var(--sakura-pink);
  color: var(--bg-dark);
}

.slide-hero .hero-button-secondary {
  background: transparent;
  border: 2px solid var(--fg);
  color: var(--fg);
}
```

```html
<div class="slider__item slide-hero">
  <div class="slider__content">
    <div class="hero-badge">
      <i class="fas {{バッジアイコン}}"></i>
      <span>{{バッジテキスト}}</span>
    </div>
    <h1 class="hero-title">{{タイトル}}</h1>
    <p class="hero-subtitle">{{サブタイトル}}</p>
    <div class="hero-cta">
      <button class="hero-button hero-button-primary">{{ボタン1}}</button>
      <button class="hero-button hero-button-secondary">{{ボタン2}}</button>
    </div>
  </div>
</div>
```

---

