# D3.js 統合リファレンス

## 概要

このドキュメントは、プレゼンテーションスライドにD3.jsを統合するための包括的なリファレンスです。

## CDN設定

```html
<!-- D3.js v7 (必須) -->
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>

<!-- GSAP (アニメーション拡張用) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
```

---

## コンポーネント一覧

### base.js - 基盤コンポーネント

| 関数 | 説明 | 戻り値 |
|------|------|--------|
| `D3Base.getTheme()` | 現在のKanagawaテーマ色を取得 | Object |
| `D3Base.createSVG(container, width, height, margin)` | SVG要素を生成 | {svg, g, innerWidth, innerHeight} |
| `D3Base.createTooltip(container)` | ツールチップ要素を生成 | D3 Selection |
| `D3Base.defaultTransition()` | 標準トランジションを生成 | D3 Transition |
| `D3Base.animateEntry(selection, type)` | 登場アニメーション適用 | void |
| `D3Base.addHoverEffect(selection, scaleFactor)` | ホバーエフェクト追加 | void |
| `D3Base.formatNumber(num)` | 数値をK/M形式でフォーマット | String |
| `D3Base.formatPercent(num)` | パーセント形式でフォーマット | String |

### cycle.js - 循環系コンポーネント

| 関数 | 用途 | データ形式 |
|------|------|-----------|
| `D3Cycle.createCycle(container, data, options)` | 汎用サイクル図 | `[{label, desc}]` |
| `D3Cycle.createPDCA(container, data, options)` | PDCAサイクル | `[{label, desc}]` |
| `D3Cycle.createTriangleCycle(container, data, options)` | 三角サイクル | `[{label, desc}]` |
| `D3Cycle.createRotatingFlow(container, data, options)` | 回転フロー | `[{label, desc}]` |

**オプション例:**
```javascript
{
  width: 600,
  height: 500,
  innerRadius: 80,
  outerRadius: 150,
  showArrows: true
}
```

### hierarchy.js - 階層系コンポーネント

| 関数 | 用途 | データ形式 |
|------|------|-----------|
| `D3Hierarchy.createTree(container, data, options)` | ツリー図 | `{name, children: []}` |
| `D3Hierarchy.createOrgChart(container, data, options)` | 組織図 | `{name, title, children: []}` |
| `D3Hierarchy.createPyramid(container, data, options)` | ピラミッド図 | `[{label, value}]` |
| `D3Hierarchy.createSunburst(container, data, options)` | サンバースト図 | `{name, children: []}` |
| `D3Hierarchy.createTreemap(container, data, options)` | ツリーマップ | `{name, children: [{value}]}` |
| `D3Hierarchy.createPackedCircles(container, data, options)` | パックドサークル | `{name, children: [{value}]}` |

**オプション例:**
```javascript
{
  width: 800,
  height: 500,
  nodeRadius: 25,
  horizontal: true
}
```

### flow.js - フロー系コンポーネント

| 関数 | 用途 | データ形式 |
|------|------|-----------|
| `D3Flow.createSankey(container, data, options)` | サンキー図 | `{nodes: [], links: []}` |
| `D3Flow.createChevron(container, data, options)` | シェブロン | `[{label}]` |
| `D3Flow.createRoadmap(container, data, options)` | ロードマップ | `[{label, items: []}]` |
| `D3Flow.createFunnel(container, data, options)` | ファネル図 | `[{label, value}]` |
| `D3Flow.createVerticalTimeline(container, data, options)` | 縦タイムライン | `[{date, title, desc}]` |

### charts.js - グラフ系コンポーネント

| 関数 | 用途 | データ形式 |
|------|------|-----------|
| `D3Charts.createBarChart(container, data, options)` | 棒グラフ | `[{label, value}]` |
| `D3Charts.createPieChart(container, data, options)` | 円グラフ | `[{label, value}]` |
| `D3Charts.createLineChart(container, data, options)` | 折れ線グラフ | `[{label, value}]` |
| `D3Charts.createRadarChart(container, data, options)` | レーダーチャート | `[{label, value}]` |
| `D3Charts.createGaugeChart(container, value, options)` | ゲージチャート | `number` |
| `D3Charts.createBubbleChart(container, data, options)` | バブルチャート | `[{label, x, y, r}]` |

**オプション例:**
```javascript
{
  width: 600,
  height: 400,
  horizontal: false,
  showValues: true,
  showDots: true
}
```

### advanced.js - 高度な可視化コンポーネント

| 関数 | 用途 | データ形式 |
|------|------|-----------|
| `D3Advanced.createForceGraph(container, data, options)` | フォースグラフ | `{nodes: [], links: []}` |
| `D3Advanced.createChordDiagram(container, data, options)` | コード図 | `{names: [], matrix: [[]]}` |
| `D3Advanced.createHeatmap(container, data, options)` | ヒートマップ | `[{x, y, value}]` |
| `D3Advanced.createRadialBarChart(container, data, options)` | 放射状棒グラフ | `[{label, value}]` |
| `D3Advanced.createWordCloud(container, data, options)` | ワードクラウド | `[{text, value}]` |
| `D3Advanced.createArcDiagram(container, data, options)` | アーク図 | `{nodes: [], links: []}` |

### extended.js - 拡張図解コンポーネント

| 関数 | 用途 | データ形式 |
|------|------|-----------|
| `D3Extended.createWaterfall(container, data, options)` | ウォーターフォール | `[{label, value, type: 'increase'|'decrease'|'total'}]` |
| `D3Extended.createDonutChart(container, data, options)` | ドーナツチャート | `[{label, value}]` |
| `D3Extended.createBulletChart(container, data, options)` | ブレットチャート | `[{label, value, target, ranges: []}]` |
| `D3Extended.createSlopeChart(container, data, options)` | スロープチャート | `[{label, start, end}]` |
| `D3Extended.createButterflyChart(container, data, options)` | バタフライチャート | `[{label, left, right}]` |
| `D3Extended.createLollipopChart(container, data, options)` | ロリポップチャート | `[{label, value}]` |
| `D3Extended.createCalendarHeatmap(container, data, options)` | カレンダーヒートマップ | `[{date: 'YYYY-MM-DD', value}]` |
| `D3Extended.createParallelCoordinates(container, data, options)` | パラレルコーディネート | `[{name, values: {axis1: val, ...}}]` |
| `D3Extended.createDendrogram(container, data, options)` | デンドログラム | `{name, children: [...]}` |
| `D3Extended.createIsotype(container, data, options)` | アイソタイプ | `[{label, value}]` |

**オプション例:**
```javascript
// ドーナツチャート
{
  width: 500,
  height: 400,
  innerRadiusRatio: 0.6,
  centerLabel: '合計',
  centerValue: '100%'
}

// スロープチャート
{
  width: 500,
  height: 400,
  startLabel: '2023年',
  endLabel: '2024年'
}

// バタフライチャート
{
  width: 600,
  height: 400,
  leftLabel: '男性',
  rightLabel: '女性'
}
```

---

## Kanagawa テーマカラー

### CSS変数

```css
:root {
  /* Light Theme */
  --bg-light: #FFFFFF;
  --fg-light: #2D2D2D;
  --accent1-light: #7E9CD8;  /* Blue */
  --accent2-light: #E46876;  /* Pink */
  --accent3-light: #98BB6C;  /* Green */
  --accent4-light: #DCA561;  /* Yellow */
  --accent5-light: #7AA89F;  /* Aqua */
  --accent6-light: #957FB8;  /* Violet */

  /* Dark Theme */
  --bg-dark: #1F1F28;
  --fg-dark: #DCD7BA;
  --accent1-dark: #7E9CD8;
  --accent2-dark: #E46876;
  --accent3-dark: #98BB6C;
  --accent4-dark: #DCA561;
  --accent5-dark: #7AA89F;
  --accent6-dark: #957FB8;
}
```

### アクセントパレット（12色）

```javascript
const accentPalette = [
  '#7E9CD8', // Blue
  '#E46876', // Pink
  '#98BB6C', // Green
  '#DCA561', // Yellow
  '#7AA89F', // Aqua
  '#957FB8', // Violet
  '#FF9E3B', // Orange
  '#C34043', // Red
  '#76946A', // Dark Green
  '#938AA9', // Light Violet
  '#7FB4CA', // Light Blue
  '#E82424'  // Bright Red
];
```

---

## HTMLテンプレート使用方法

### data属性によるチャート定義

```html
<div class="d3-container"
     data-chart="bar"
     data-chart-data='[{"label":"A","value":100},{"label":"B","value":200}]'
     data-chart-options='{"horizontal":false}'>
</div>
```

### サポートされるチャートタイプ

| data-chart | コンポーネント |
|------------|---------------|
| `cycle` | D3Cycle.createCycle |
| `pdca` | D3Cycle.createPDCA |
| `tree` | D3Hierarchy.createTree |
| `pyramid` | D3Hierarchy.createPyramid |
| `chevron` | D3Flow.createChevron |
| `funnel` | D3Flow.createFunnel |
| `bar` | D3Charts.createBarChart |
| `pie` | D3Charts.createPieChart |
| `line` | D3Charts.createLineChart |
| `radar` | D3Charts.createRadarChart |
| `gauge` | D3Charts.createGaugeChart |
| `force` | D3Advanced.createForceGraph |
| `heatmap` | D3Advanced.createHeatmap |
| `wordcloud` | D3Advanced.createWordCloud |
| `waterfall` | D3Extended.createWaterfall |
| `donut` | D3Extended.createDonutChart |
| `bullet` | D3Extended.createBulletChart |
| `slope` | D3Extended.createSlopeChart |
| `butterfly` | D3Extended.createButterflyChart |
| `lollipop` | D3Extended.createLollipopChart |
| `calendar` | D3Extended.createCalendarHeatmap |
| `parallel` | D3Extended.createParallelCoordinates |
| `dendrogram` | D3Extended.createDendrogram |
| `isotype` | D3Extended.createIsotype |

---

## アニメーション設定

### 標準トランジション

```javascript
// D3Baseのデフォルト
d3.transition()
  .duration(800)
  .ease(d3.easeCubicOut);
```

### 登場アニメーションタイプ

| タイプ | 効果 |
|--------|------|
| `fade` | 不透明度 0→1 |
| `scale` | スケール 0→1（バックアウト） |
| `slideUp` | Y移動 + フェード |

### 推奨アニメーション時間

| コンポーネント | 時間 |
|---------------|------|
| サイクル系 | 500ms × 要素数 |
| 階層系 | 600ms + 400ms |
| 棒グラフ | 600ms |
| 円グラフ | 800ms |
| 折れ線 | 1500ms |
| フォースグラフ | 自動（シミュレーション） |

---

## d3-config.json スキーマ

```json
{
  "version": "1.0",
  "theme": "dark",
  "slides": [
    {
      "slideNumber": 1,
      "chartType": "bar",
      "data": [
        { "label": "カテゴリA", "value": 100 },
        { "label": "カテゴリB", "value": 200 }
      ],
      "options": {
        "horizontal": false,
        "showValues": true
      }
    }
  ]
}
```

### 必須フィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `version` | string | スキーマバージョン |
| `theme` | string | "light" または "dark" |
| `slides` | array | スライド設定配列 |
| `slides[].slideNumber` | number | スライド番号 |
| `slides[].chartType` | string | チャートタイプ |
| `slides[].data` | object/array | チャートデータ |

---

## エラーハンドリング

### 一般的なエラーと対処

| エラー | 原因 | 対処 |
|--------|------|------|
| `d3 is not defined` | CDN読み込み失敗 | CDN URLを確認 |
| `Cannot read property of undefined` | データ形式不正 | データスキーマを確認 |
| `Maximum call stack exceeded` | 循環参照 | 階層データの構造を確認 |
| `Invalid transition` | トランジション重複 | 前のトランジションを待つ |

### デバッグ用コンソール出力

```javascript
// テーマ確認
console.log('Theme:', D3Base.getTheme());

// データ確認
console.log('Data:', JSON.stringify(data, null, 2));
```

---

## ベストプラクティス

### 1. レスポンシブ設計

```javascript
// viewBoxとpreserveAspectRatioを必ず設定
svg.attr('viewBox', `0 0 ${width} ${height}`)
   .attr('preserveAspectRatio', 'xMidYMid meet');
```

### 2. アクセシビリティ

```javascript
// ARIA属性の追加
svg.attr('role', 'img')
   .attr('aria-label', 'チャートの説明');
```

### 3. パフォーマンス

- 大量データは事前に集約
- 不要なアニメーションを避ける
- DOMの再描画を最小化

### 4. 一貫性

- Kanagawaカラーパレットを使用
- 標準トランジションを使用
- ツールチップスタイルを統一

---

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `assets/d3-components/base.js` | 基盤コンポーネント |
| `assets/d3-components/cycle.js` | 循環系コンポーネント |
| `assets/d3-components/hierarchy.js` | 階層系コンポーネント |
| `assets/d3-components/flow.js` | フロー系コンポーネント |
| `assets/d3-components/charts.js` | グラフ系コンポーネント |
| `assets/d3-components/advanced.js` | 高度な可視化コンポーネント |
| `assets/d3-components/extended.js` | 拡張図解コンポーネント（10種） |
| `assets/d3-slide-template.html` | D3対応HTMLテンプレート |
| `agents/d3-diagram-designer.md` | D3図解設計エージェント |
| `agents/data-visualizer.md` | データ可視化エージェント |
| `scripts/validate-d3.js` | D3検証スクリプト |
