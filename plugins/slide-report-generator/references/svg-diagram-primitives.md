# SVG2 図解プリミティブ・パターン集

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは設計の文脈・例・適用ガイドのみ。規則の正本は SR-ID で参照すること

**責務**: インラインSVG2の実装テンプレート・再利用可能なコンポーネント・defs パターン集。
**規則の正本**: viewBox基準 → [SR-1-02](spec-registry.md#sr-1-02) / [SR-5-01](spec-registry.md#sr-5-01)、SVG fill/stroke の CSS変数化 → [SR-2-08](spec-registry.md#sr-2-08)、矢印マーカー5種 → [SR-5-05](spec-registry.md#sr-5-05)、defs/グラデ → [SR-5-06](spec-registry.md#sr-5-06)、レイアウト図解は absolute 禁止 → [SR-4-08](spec-registry.md#sr-4-08)、foreignObject 内 fo-card → [SR-6-04](spec-registry.md#sr-6-04)

---

## 設計原則（運用ガイド）

| 原則 | 補足 |
|------|------|
| インラインSVG | HTML内に直接記述（外部ファイル不可） |
| CSS変数連携 | [SR-2-08](spec-registry.md#sr-2-08) |
| viewBox基準 | [SR-5-01](spec-registry.md#sr-5-01) |
| レスポンシブ | `width="100%" height="100%"` + `preserveAspectRatio` |
| foreignObject | FontAwesomeアイコン等のHTML要素は foreignObject 経由（[SR-3-06](spec-registry.md#sr-3-06)） |
| 配置 | `position: absolute` 禁止 → [SR-4-08](spec-registry.md#sr-4-08) |

---

## 1. SVG基本テンプレート

### 1.1 図解用SVGコンテナ

```html
<div class="slider__item slide-diagram">
  <div class="slider__content">
    <h2 class="diagram-title"><i class="fas fa-{{icon}}"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{図解の説明}}">
        <defs>
          <!-- 再利用可能な定義 -->
        </defs>
        <!-- 図解コンテンツ -->
      </svg>
    </div>
  </div>
</div>
```

### 1.2 SVGコンテナCSS

```css
.diagram-svg-container {
  width: 100%;
  max-width: 900px;
  aspect-ratio: 16 / 9;
  margin: 0 auto;
}

.diagram-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* SVG内テキスト共通 */
.diagram-svg text {
  font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', sans-serif;
  fill: var(--fg-default, #DCD7BA);
}

/* SVG内ホバー効果 */
.diagram-svg .interactive {
  cursor: pointer;
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.diagram-svg .interactive:hover {
  opacity: 0.85;
  filter: brightness(1.1);
}
```

---

## 2. `<defs>` 再利用パーツ

### 2.1 矢印マーカー

```html
<defs>
  <!-- 標準矢印（青） -->
  <marker id="arrow-blue" viewBox="0 0 10 10" refX="10" refY="5"
          markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--wave-blue, #7E9CD8)" />
  </marker>

  <!-- 矢印（ピンク） -->
  <marker id="arrow-pink" viewBox="0 0 10 10" refX="10" refY="5"
          markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--sakura-pink, #D27E99)" />
  </marker>

  <!-- 矢印（黄） -->
  <marker id="arrow-yellow" viewBox="0 0 10 10" refX="10" refY="5"
          markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--autumn-yellow, #DCA561)" />
  </marker>

  <!-- 矢印（緑） -->
  <marker id="arrow-green" viewBox="0 0 10 10" refX="10" refY="5"
          markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--spring-green, #98BB6C)" />
  </marker>

  <!-- 矢印（アクア） -->
  <marker id="arrow-aqua" viewBox="0 0 10 10" refX="10" refY="5"
          markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--wave-aqua, #7AA89F)" />
  </marker>

  <!-- 丸ドット -->
  <marker id="dot-blue" viewBox="0 0 10 10" refX="5" refY="5"
          markerWidth="6" markerHeight="6">
    <circle cx="5" cy="5" r="4" fill="var(--wave-blue, #7E9CD8)" />
  </marker>
</defs>
```

### 2.2 グラデーション

```html
<defs>
  <!-- 線形グラデーション（青→ピンク） -->
  <linearGradient id="grad-blue-pink" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="var(--wave-blue, #7E9CD8)" />
    <stop offset="100%" stop-color="var(--sakura-pink, #D27E99)" />
  </linearGradient>

  <!-- 放射グラデーション（中央ハイライト） -->
  <radialGradient id="grad-radial-blue" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="var(--wave-blue, #7E9CD8)" stop-opacity="0.8" />
    <stop offset="100%" stop-color="var(--wave-blue, #7E9CD8)" stop-opacity="0.3" />
  </radialGradient>

  <!-- ファネル用グラデーション -->
  <linearGradient id="grad-funnel" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="var(--wave-blue, #7E9CD8)" />
    <stop offset="25%" stop-color="var(--wave-aqua, #7AA89F)" />
    <stop offset="50%" stop-color="var(--spring-green, #98BB6C)" />
    <stop offset="75%" stop-color="var(--autumn-yellow, #DCA561)" />
    <stop offset="100%" stop-color="var(--sakura-pink, #D27E99)" />
  </linearGradient>
</defs>
```

### 2.3 フィルター

```html
<defs>
  <!-- ドロップシャドウ -->
  <filter id="shadow-sm" x="-5%" y="-5%" width="110%" height="110%">
    <feDropShadow dx="2" dy="4" stdDeviation="4" flood-color="#000" flood-opacity="0.25" />
  </filter>

  <filter id="shadow-lg" x="-10%" y="-10%" width="120%" height="130%">
    <feDropShadow dx="4" dy="8" stdDeviation="8" flood-color="#000" flood-opacity="0.35" />
  </filter>

  <!-- グロー効果 -->
  <filter id="glow-blue">
    <feGaussianBlur stdDeviation="4" result="blur" />
    <feFlood flood-color="var(--wave-blue, #7E9CD8)" flood-opacity="0.5" result="color" />
    <feComposite in="color" in2="blur" operator="in" result="glow" />
    <feMerge>
      <feMergeNode in="glow" />
      <feMergeNode in="SourceGraphic" />
    </feMerge>
  </filter>
</defs>
```

### 2.4 クリップパス・マスク

```html
<defs>
  <!-- ひし形クリップ（判断ノード用） -->
  <clipPath id="clip-diamond">
    <polygon points="50,0 100,50 50,100 0,50" />
  </clipPath>

  <!-- 角丸矩形クリップ -->
  <clipPath id="clip-rounded">
    <rect x="0" y="0" width="100" height="60" rx="12" ry="12" />
  </clipPath>
</defs>
```

---

## 3. 基本図形パターン

### 3.1 ノード（角丸矩形）

```html
<!-- 標準ノード -->
<g class="interactive" transform="translate(100, 100)">
  <rect width="160" height="80" rx="12" ry="12"
        fill="var(--bg-dim, #2A2A37)" stroke="var(--wave-blue, #7E9CD8)"
        stroke-width="2.5" filter="url(#shadow-sm)" />
  <foreignObject x="8" y="8" width="144" height="64">
    <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card">
      <i class="fas fa-cog" style="color:var(--wave-blue,#7E9CD8)"></i>
      <span>{{テキスト}}</span>
    </div>
  </foreignObject>
</g>
```

> **重要**: foreignObject内のdivは `class="fo-card"` を使用すること。インラインstyleでレイアウトを指定するとGSAPの `clearProps: 'all'` で破壊される。CSSクラスはclearPropsの影響を受けない。

### 3.2 円形ノード

```html
<!-- 円形ノード（サイクル要素用） -->
<g class="interactive" transform="translate(480, 270)">
  <circle r="55" fill="var(--bg-dim, #2A2A37)"
          stroke="var(--wave-blue, #7E9CD8)" stroke-width="3"
          filter="url(#shadow-sm)" />
  <foreignObject x="-45" y="-40" width="90" height="80">
    <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card">
      <i class="fas fa-star" style="font-size:1.4rem;color:var(--autumn-yellow,#DCA561)"></i>
      <span>{{ラベル}}</span>
    </div>
  </foreignObject>
</g>
```

### 3.3 ひし形ノード（判断用）

```html
<!-- ひし形（フローチャートの判断ノード） -->
<g class="interactive" transform="translate(480, 270)">
  <polygon points="0,-50 70,0 0,50 -70,0"
           fill="var(--autumn-yellow, #DCA561)"
           stroke="var(--autumn-yellow, #DCA561)" stroke-width="2"
           filter="url(#shadow-sm)" />
  <text text-anchor="middle" dominant-baseline="central"
        fill="var(--bg-dark, #1F1F28)" font-weight="700" font-size="16">
    {{条件?}}
  </text>
</g>
```

### 3.4 カプセル（開始・終了ノード）

```html
<!-- カプセル型（フローチャートの開始/終了） -->
<g class="interactive" transform="translate(480, 50)">
  <rect width="140" height="45" rx="22" ry="22" x="-70" y="-22"
        fill="var(--sakura-pink, #D27E99)" filter="url(#shadow-sm)" />
  <text text-anchor="middle" dominant-baseline="central"
        fill="var(--bg-dark, #1F1F28)" font-weight="700" font-size="16">
    開始
  </text>
</g>
```

---

## 4. 接続線パターン

### 4.1 直線接続

```html
<!-- 矢印付き直線 -->
<line x1="200" y1="140" x2="200" y2="200"
      stroke="var(--fuji-gray, #727169)" stroke-width="2.5"
      marker-end="url(#arrow-blue)" />
```

### 4.2 曲線接続（ベジェ）

```html
<!-- 2次ベジェ曲線 -->
<path d="M 200,140 Q 300,170 400,140"
      fill="none" stroke="var(--wave-blue, #7E9CD8)" stroke-width="2.5"
      marker-end="url(#arrow-blue)" />

<!-- 3次ベジェ曲線（S字） -->
<path d="M 200,140 C 250,200 350,80 400,140"
      fill="none" stroke="var(--wave-aqua, #7AA89F)" stroke-width="2.5"
      marker-end="url(#arrow-aqua)" />
```

### 4.3 円弧接続（サイクル用）

```html
<!-- 円弧（サイクル図の接続矢印） -->
<path d="M 560,200 A 180,180 0 0,1 400,380"
      fill="none" stroke="var(--autumn-yellow, #DCA561)" stroke-width="2.5"
      stroke-dasharray="none" marker-end="url(#arrow-yellow)" />
```

### 4.4 破線接続

```html
<!-- 破線（弱い関係、オプション） -->
<line x1="200" y1="270" x2="400" y2="270"
      stroke="var(--fuji-gray, #727169)" stroke-width="2"
      stroke-dasharray="8,4" marker-end="url(#arrow-blue)" />
```

---

## 5. テキスト配置パターン

### 5.1 SVGネイティブテキスト

```html
<!-- 中央揃えテキスト -->
<text x="480" y="270" text-anchor="middle" dominant-baseline="central"
      font-size="18" font-weight="700"
      fill="var(--fg-default, #DCD7BA)">
  {{テキスト}}
</text>

<!-- 折り返しテキスト（tspan使用） -->
<text x="480" y="250" text-anchor="middle" font-size="14"
      fill="var(--fg-default, #DCD7BA)">
  <tspan x="480" dy="0">{{1行目}}</tspan>
  <tspan x="480" dy="20">{{2行目}}</tspan>
</text>
```

### 5.2 foreignObject経由のHTML

```html
<!-- 複雑なHTML（アイコン+テキスト+ツールチップ） -->
<foreignObject x="380" y="230" width="200" height="80">
  <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card has-tooltip"
       data-tooltip="{{詳細テキスト}}">
    <i class="fas fa-lightbulb" style="color:var(--autumn-yellow,#DCA561)"></i>
    <span>{{ラベル}}</span>
  </div>
</foreignObject>
```

> **注意**: `fo-card` クラスが基本レイアウト（flex, column, center, padding）を提供する。横並びが必要な場合は `fo-card fo-card--row` を使用。装飾プロパティ（`color`, `font-size`, `font-weight`, `gap`）はstyle属性で追加OK。ただし **レイアウトプロパティ（`display`, `flex-direction`, `align-items`, `justify-content`）はstyle属性での単独定義禁止** — GSAPのclearPropsで消失する。

---

## 6. ツールチップ統合

SVG要素にも既存のツールチップシステムを適用可能。

```html
<!-- foreignObject内のツールチップ -->
<foreignObject x="100" y="100" width="160" height="80">
  <div xmlns="http://www.w3.org/1999/xhtml"
       class="has-tooltip" data-tooltip="{{詳細説明}}">
    <!-- コンテンツ -->
  </div>
</foreignObject>

<!-- SVG要素へのtitle（ブラウザネイティブツールチップ） -->
<g class="interactive">
  <title>{{ホバー時の説明}}</title>
  <rect ... />
</g>
```

---

## 7. アニメーション統合

### 7.1 GSAP連携

SVG要素もGSAPで制御可能。クラス名やdata属性でターゲット指定。

```javascript
// SVG要素のenter/leaveアニメーション
gsap.from('.diagram-svg .interactive', {
  opacity: 0,
  scale: 0.8,
  duration: 0.5,
  stagger: 0.1,
  ease: 'back.out(1.7)'
});

// 接続線のdraw-on効果
gsap.from('.diagram-svg line, .diagram-svg path.connector', {
  strokeDashoffset: function(i, el) {
    return el.getTotalLength ? el.getTotalLength() : 100;
  },
  strokeDasharray: function(i, el) {
    return el.getTotalLength ? el.getTotalLength() : 100;
  },
  duration: 1,
  stagger: 0.2
});
```

### 7.2 CSS Transition

```css
/* SVG要素のホバーアニメーション */
.diagram-svg .interactive rect,
.diagram-svg .interactive circle {
  transition: filter 0.3s ease, stroke-width 0.3s ease;
}

.diagram-svg .interactive:hover rect,
.diagram-svg .interactive:hover circle {
  filter: url(#shadow-lg);
  stroke-width: 3.5;
}
```

---

## 8. 座標計算ヘルパー

### 8.1 円形配置（サイクル図用）

N個の要素を円形に配置する座標計算:

```
要素i の位置:
  x = cx + r * cos(2π * i/N - π/2)
  y = cy + r * sin(2π * i/N - π/2)

例: 4要素サイクル（中心: 480,270、半径: 180）
  要素0: (480, 90)   — 上
  要素1: (660, 270)  — 右
  要素2: (480, 450)  — 下
  要素3: (300, 270)  — 左
```

### 8.2 接続弧の計算

要素A→Bを結ぶ円弧のSVGパス:

```
M {Ax},{Ay} A {r},{r} 0 0,{sweep} {Bx},{By}

sweep: 0=反時計回り, 1=時計回り
r: 弧の曲率半径（大きいほど緩やかな曲線）
```

### 8.3 ファネルの台形座標

ファネルのi番目レベル（N段）:

```
上辺幅: topW = maxW - (maxW - minW) * i / N
下辺幅: btmW = maxW - (maxW - minW) * (i+1) / N
Y位置: y = startY + levelH * i

左上: (cx - topW/2, y)
右上: (cx + topW/2, y)
右下: (cx + btmW/2, y + levelH)
左下: (cx - btmW/2, y + levelH)
```

---

## 9. CSS→SVG 移行ガイドライン

### 9.1 移行すべき図解

| 図解タイプ | CSS方式の問題 | SVG方式の利点 |
|-----------|-------------|-------------|
| サイクル図 | nth-child位置指定が脆弱 | 円弧パスで正確な接続線 |
| ベン図 | rgba半透明の重なり制御が困難 | SVG opacity + mix-blend-mode |
| フローチャート | clip-path ひし形が印刷で崩れる | polygon で正確な形状 |
| マインドマップ | CSSラインの角度計算が不正確 | SVG path で精密な接続 |
| ファネル | clip-path 台形の段差問題 | polygon で滑らかな台形 |
| 組織図 | border+positionの接続線が粗い | line/path で精密な罫線 |
| 上昇型 | border-left三角形の精度問題 | polygon + path で滑らかな曲線 |

### 9.2 CSSを維持すべき図解

| 図解タイプ | 理由 |
|-----------|------|
| 対比型（カード） | Flexboxレイアウトが最適 |
| FABE型（カード） | CSS Grid/Flexが適切 |
| ガントチャート | テーブル構造が適切 |
| ペルソナ型 | テキスト中心のカードレイアウト |
| ポイントカード型 | Gridレイアウトが最適 |

### 9.3 ハイブリッド方式

カード型レイアウト + SVG接続線の組み合わせ:

```html
<div class="slider__item slide-hybrid">
  <div class="slider__content" style="position:relative;">
    <!-- SVG接続線レイヤー（背面） -->
    <svg class="connector-layer" viewBox="0 0 960 540"
         style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5"
                markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--autumn-yellow,#DCA561)" />
        </marker>
      </defs>
      <path d="M 240,270 Q 480,200 720,270"
            fill="none" stroke="var(--autumn-yellow,#DCA561)"
            stroke-width="2.5" marker-end="url(#arrow)" />
    </svg>
    <!-- HTMLカードレイヤー（前面） -->
    <div class="card-container" style="position:relative;z-index:1;">
      <!-- カード要素 -->
    </div>
  </div>
</div>
```

---

## 10. 印刷互換性

### 10.1 印刷用SVGルール

```css
@media print {
  .diagram-svg {
    /* 印刷時はフィルター無効化（一部プリンタで問題） */
    --print-filter: none;
  }

  .diagram-svg [filter] {
    filter: none !important;
  }

  /* 線幅を太くして印刷での視認性を確保 */
  .diagram-svg line,
  .diagram-svg path {
    stroke-width: 3px;
  }

  /* テキストを黒に */
  .diagram-svg text {
    fill: #2D2D2D !important;
  }
}
```

---

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-15 | 初版作成: 矢印マーカー、グラデーション、フィルター、基本図形、接続線、テキスト配置、アニメーション統合、座標計算ヘルパー、CSS→SVG移行ガイド |
