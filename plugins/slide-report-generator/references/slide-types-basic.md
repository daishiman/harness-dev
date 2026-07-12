# 基本スライドタイプ

**責務**: 基本9種のスライドタイプ（タイトル、メッセージ、リスト、比較、フロー、タイムライン、テーブル、コード、コード比較）のCSS・HTMLテンプレート

---


## 2. 基本スライド詳細

### 2.1 タイトルスライド

```css
.slide-title .slider__content {
  text-align: center;
}

.slide-title .main-title {
  font-size: 4rem;
  font-weight: 700;
  margin-bottom: 1rem;
  line-height: 1.2;
}

.slide-title .sub-title {
  font-size: 1.5rem;
  color: var(--fg-dim);
}

.slide-title .title-icon {
  font-size: 5rem;
  color: var(--wave-blue);
  margin-bottom: 2rem;
}
```

```html
<div class="slider__item slide-title">
  <div class="slider__content">
    <i class="title-icon fas {{アイコン}}"></i>
    <h1 class="main-title">{{タイトル}}</h1>
    <p class="sub-title">{{サブタイトル}}</p>
  </div>
</div>
```

### 2.2 メッセージスライド

```css
.slide-message .slider__content {
  text-align: center;
}

.slide-message .message-icon {
  margin: 0 auto 2rem;
}

.slide-message .main-message {
  font-size: 3rem;
  font-weight: 700;
  line-height: 1.3;
}

.slide-message .sub-message {
  font-size: 1.2rem;
  color: var(--fg-dim);
  margin-top: 1rem;
}
```

```html
<div class="slider__item slide-message">
  <div class="slider__content">
    <div class="icon-wrapper message-icon {{アクセントクラス}}">
      <i class="fas {{アイコン}}"></i>
    </div>
    <h2 class="main-message">{{メッセージ}}</h2>
    <p class="sub-message">{{補足}}</p>
  </div>
</div>
```

### 2.3 リストスライド

```css
.slide-list .slider__content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.slide-list .list-title {
  font-size: 2.5rem;
  font-weight: 700;
  text-align: center;
  margin-bottom: 1rem;
}

.slide-list .list-container {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  justify-content: center;
}

.slide-list .list-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: var(--bg-dim);
  padding: 1.5rem 2rem;
  border-radius: 12px;
  min-width: 280px;
  border-left: 4px solid var(--wave-blue);
}

.slide-list .list-item i {
  font-size: 1.5rem;
  color: var(--wave-blue);
}

.slide-list .list-item span {
  font-size: 1.2rem;
}
```

```html
<div class="slider__item slide-list">
  <div class="slider__content">
    <h2 class="list-title">{{タイトル}}</h2>
    <div class="list-container">
      <div class="list-item">
        <i class="fas {{アイコン}}"></i>
        <span>{{テキスト}}</span>
      </div>
      <!-- 繰り返し -->
    </div>
  </div>
</div>
```

### 2.4 比較スライド

```css
.slide-compare .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-compare .compare-title {
  font-size: 2.5rem;
  font-weight: 700;
  text-align: center;
}

.slide-compare .compare-container {
  display: flex;
  gap: 2rem;
  justify-content: center;
  align-items: stretch;
}

.slide-compare .compare-item {
  flex: 1;
  max-width: 400px;
  background: var(--bg-dim);
  padding: 2rem;
  border-radius: 16px;
  text-align: center;
}

.slide-compare .compare-item.left {
  border-top: 4px solid var(--sakura-pink);
}

.slide-compare .compare-item.right {
  border-top: 4px solid var(--wave-aqua);
}

.slide-compare .compare-item h3 {
  font-size: 1.5rem;
  margin-bottom: 1rem;
}

.slide-compare .compare-item .value {
  font-size: 3rem;
  font-weight: 700;
}

.slide-compare .compare-item.left .value {
  color: var(--sakura-pink);
}

.slide-compare .compare-item.right .value {
  color: var(--wave-aqua);
}

.slide-compare .compare-vs {
  display: flex;
  align-items: center;
  font-size: 2rem;
  font-weight: 700;
  color: var(--autumn-yellow);
}
```

```html
<div class="slider__item slide-compare">
  <div class="slider__content">
    <h2 class="compare-title">{{タイトル}}</h2>
    <div class="compare-container">
      <div class="compare-item left">
        <i class="fas {{左アイコン}}"></i>
        <h3>{{左ラベル}}</h3>
        <div class="value">{{左値}}</div>
        <p>{{左説明}}</p>
      </div>
      <div class="compare-vs">VS</div>
      <div class="compare-item right">
        <i class="fas {{右アイコン}}"></i>
        <h3>{{右ラベル}}</h3>
        <div class="value">{{右値}}</div>
        <p>{{右説明}}</p>
      </div>
    </div>
  </div>
</div>
```

### 2.5 フロースライド

```css
.slide-flow .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-flow .flow-title {
  font-size: 2.5rem;
  font-weight: 700;
  text-align: center;
}

.slide-flow .flow-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.slide-flow .flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-dim);
  padding: 1.5rem;
  border-radius: 12px;
  min-width: 140px;
}

.slide-flow .flow-step .step-number {
  width: 40px;
  height: 40px;
  background: var(--wave-blue);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.2rem;
}

.slide-flow .flow-step i {
  font-size: 2rem;
  color: var(--wave-aqua);
  margin: 0.5rem 0;
}

.slide-flow .flow-step span {
  font-size: 1rem;
  text-align: center;
}

.slide-flow .flow-arrow {
  font-size: 1.5rem;
  color: var(--autumn-yellow);
}
```

```html
<div class="slider__item slide-flow">
  <div class="slider__content">
    <h2 class="flow-title">{{タイトル}}</h2>
    <div class="flow-container">
      <div class="flow-step">
        <div class="step-number">{{番号}}</div>
        <i class="fas {{アイコン}}"></i>
        <span>{{テキスト}}</span>
      </div>
      <div class="flow-arrow"><i class="fas fa-arrow-right"></i></div>
      <!-- 繰り返し -->
    </div>
  </div>
</div>
```

### 2.6 タイムラインスライド

```css
.slide-timeline .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-timeline .timeline-title {
  font-size: 2.5rem;
  font-weight: 700;
  text-align: center;
}

.slide-timeline .timeline-container {
  position: relative;
  padding-left: 3rem;
}

.slide-timeline .timeline-line {
  position: absolute;
  left: 1rem;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--wave-blue);
  border-radius: 2px;
}

.slide-timeline .timeline-item {
  position: relative;
  padding: 1rem 0 1rem 2rem;
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.slide-timeline .timeline-dot {
  position: absolute;
  left: -2.5rem;
  width: 20px;
  height: 20px;
  background: var(--wave-blue);
  border-radius: 50%;
  border: 4px solid var(--bg-dark);
}

.slide-timeline .timeline-content {
  background: var(--bg-dim);
  padding: 1rem 1.5rem;
  border-radius: 8px;
  flex: 1;
}

.slide-timeline .timeline-content h4 {
  font-size: 1.2rem;
  color: var(--wave-blue);
  margin-bottom: 0.5rem;
}
```

```html
<div class="slider__item slide-timeline">
  <div class="slider__content">
    <h2 class="timeline-title">{{タイトル}}</h2>
    <div class="timeline-container">
      <div class="timeline-line"></div>
      <div class="timeline-item">
        <div class="timeline-dot"></div>
        <div class="timeline-content">
          <h4>{{時期}}</h4>
          <p>{{内容}}</p>
        </div>
      </div>
      <!-- 繰り返し -->
    </div>
  </div>
</div>
```

### 2.7 テーブルスライド

```css
.slide-table .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-table .table-title {
  font-size: 2.5rem;
  font-weight: 700;
  text-align: center;
}

.slide-table table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-dim);
  border-radius: 12px;
  overflow: hidden;
}

.slide-table th {
  background: var(--sumi-ink);
  padding: 1rem;
  text-align: left;
  font-weight: 700;
  color: var(--wave-blue);
  border-bottom: 2px solid var(--fuji-gray);
}

.slide-table td {
  padding: 1rem;
  border-bottom: 1px solid var(--fuji-gray);
}

.slide-table tr:last-child td {
  border-bottom: none;
}

.slide-table .table-icon {
  color: var(--wave-aqua);
  margin-right: 0.5rem;
}
```

```html
<div class="slider__item slide-table">
  <div class="slider__content">
    <h2 class="table-title">{{タイトル}}</h2>
    <table>
      <thead>
        <tr>
          <th>{{ヘッダー}}</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>{{セル}}</td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
```

### 2.8 コードブロックスライド

注記: image-only / 全面AI画像化デッキでも、コードページは画像に焼き込まず本セクションの実HTMLコードブロックで描画する（コード専用ページ）。

```css
.slide-code .slider__content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.slide-code .code-title {
  font-size: var(--fs-heading, 2.5rem);
  font-weight: 700;
  text-align: center;
}

.slide-code .code-block {
  max-height: 420px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: var(--fs-small, 1.4rem);
  line-height: 1.7;
  background: var(--bg-dim);
  border-radius: 12px;
  padding: 20px 24px;
  white-space: pre-wrap;
  word-wrap: break-word;
}

@media print {
  .slide-code .code-block {
    max-height: none;
    overflow: visible;
  }
}

.slide-code .code-block .code-header {
  color: var(--wave-blue);
  font-weight: 700;
}

.slide-code .code-block .code-variable {
  background: rgba(var(--autumn-yellow-rgb), 0.15);
  padding: 2px 6px;
  border-radius: 4px;
}

.slide-code .code-note {
  font-size: var(--fs-small, 1.4rem);
  opacity: 0.7;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

```html
<div class="slider__item slide-code">
  <div class="slider__content">
    <h2 class="code-title">{{タイトル}}</h2>
    <div class="code-block">
<span class="code-header"># {{セクション見出し}}</span>
{{コード本文}}
あなたは<span class="code-variable">{変数名}</span>の専門家です。
    </div>
    <p class="code-note">{{補足テキスト（最大3行）}}</p>
  </div>
</div>
```

### 2.9 コード比較スライド（Before/After）

注記: image-only / 全面AI画像化デッキでも、コードページは画像に焼き込まず本セクションの実HTMLコードブロックで描画する（コード専用ページ）。

```css
.slide-code-compare .slider__content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.slide-code-compare .code-compare-title {
  font-size: var(--fs-heading, 2.5rem);
  font-weight: 700;
  text-align: center;
}

.slide-code-compare .code-compare-container {
  display: flex;
  gap: 4%;
  justify-content: center;
}

.slide-code-compare .code-compare-column {
  width: 48%;
  display: flex;
  flex-direction: column;
}

.slide-code-compare .code-compare-header {
  padding: 0.6rem 1.2rem;
  color: white;
  font-weight: 700;
  font-size: var(--fs-small, 1.4rem);
  border-radius: 12px 12px 0 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.slide-code-compare .code-compare-column.before .code-compare-header {
  background: var(--sakura-pink);
}

.slide-code-compare .code-compare-column.after .code-compare-header {
  background: var(--wave-aqua);
}

.slide-code-compare .code-compare-body {
  max-height: 280px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: var(--fs-small, 1.4rem);
  line-height: 1.7;
  background: var(--bg-dim);
  border-radius: 0 0 12px 12px;
  padding: 20px 24px;
  white-space: pre-wrap;
  word-wrap: break-word;
  flex: 1;
}

@media print {
  .slide-code-compare .code-compare-body {
    max-height: none;
    overflow: visible;
  }
}

.slide-code-compare .code-compare-body .code-header {
  color: var(--wave-blue);
  font-weight: 700;
}

.slide-code-compare .code-compare-body .code-variable {
  background: rgba(var(--autumn-yellow-rgb), 0.15);
  padding: 2px 6px;
  border-radius: 4px;
}

.slide-code-compare .code-compare-diff {
  font-size: var(--fs-small, 1.4rem);
  opacity: 0.7;
  text-align: center;
}
```

```html
<div class="slider__item slide-code-compare">
  <div class="slider__content">
    <h2 class="code-compare-title">{{タイトル}}</h2>
    <div class="code-compare-container">
      <div class="code-compare-column before">
        <div class="code-compare-header">
          <i class="fas fa-times-circle"></i>
          <span>Before</span>
        </div>
        <div class="code-compare-body">
<span class="code-header"># {{セクション見出し}}</span>
{{Beforeコード}}
        </div>
      </div>
      <div class="code-compare-column after">
        <div class="code-compare-header">
          <i class="fas fa-check-circle"></i>
          <span>After</span>
        </div>
        <div class="code-compare-body">
<span class="code-header"># {{セクション見出し}}</span>
{{Afterコード}}
<span class="code-variable">{変数名}</span>を活用
        </div>
      </div>
    </div>
    <p class="code-compare-diff">{{差分ポイント：何が変わったかの説明}}</p>
  </div>
</div>
```

---
