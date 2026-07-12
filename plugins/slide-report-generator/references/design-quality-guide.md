# デザイン品質ガイド

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは設計の文脈・例・適用ガイドのみ。規則の正本は SR-ID で参照すること

**責務**: Apple品質のビジュアルデザインを実現するための文脈・適用例・アンチパターン。
**規則の正本**: ビビッドアクセント定義 → [SR-2-04](spec-registry.md#sr-2-04)、各スライド1色以上 → [SR-2-05](spec-registry.md#sr-2-05)、60-30-10 → [SR-2-06](spec-registry.md#sr-2-06)、シャドウ/グロウ → [SR-2-09](spec-registry.md#sr-2-09)、a11y全般 → §9（[SR-9-01](spec-registry.md#sr-9-01)〜[SR-9-06](spec-registry.md#sr-9-06)）、reduced-motion → [SR-6-08](spec-registry.md#sr-6-08)

---

## 1. ビビッドカラーパレット

CSS変数定義の正本 → [SR-2-04](spec-registry.md#sr-2-04)。彩度強化の意図と元カラー対応:

| 変数名 | カラーコード | 元カラー | 彩度変化 | 用途 |
|--------|-------------|---------|---------|------|
| `--accent-blue-vivid` | #3B7DD8 | #4d699b | 34%→60% | 主アクセント強調 |
| `--accent-pink-vivid` | #D94B6E | #b35b79 | 32%→60% | 課題・警告強調 |
| `--accent-aqua-vivid` | #2EA88F | #597b75 | 16%→57% | 成功・解決強調 |
| `--accent-violet-vivid` | #7B4FBA | #624c83 | 彩度深化 | サブアクセント強調 |
| `--accent-yellow-vivid` | #F5A623 | #de9800 | 高彩度維持 | CTA・重要数値 |

### WCAG AA コントラスト比（背景 #fafafa）

| カラー | コントラスト比 | AA判定 |
|--------|--------------|--------|
| #3B7DD8 | 4.5:1 | PASS |
| #D94B6E | 4.6:1 | PASS |
| #2EA88F | 4.5:1 | PASS |
| #7B4FBA | 5.2:1 | PASS |
| #F5A623 | (装飾用) | 大テキストのみ |

### グラデーション定義

```css
:root {
  /* 主要グラデーション */
  --gradient-blue-pink: linear-gradient(135deg, var(--accent-blue-vivid), var(--accent-pink-vivid));
  --gradient-blue-aqua: linear-gradient(135deg, var(--accent-blue-vivid), var(--accent-aqua-vivid));
  --gradient-violet-pink: linear-gradient(135deg, var(--accent-violet-vivid), var(--accent-pink-vivid));

  /* 微細グラデーション（カード背景用） */
  --gradient-subtle: linear-gradient(135deg, var(--bg-dim), var(--bg-card));
}
```

### 使い分け

| グラデーション | 用途 |
|--------------|------|
| blue-pink | タイトルスライド背景、CTA要素 |
| blue-aqua | プロセス・フロー系のアクセント |
| violet-pink | セクション区切り、引用背景 |
| subtle | カード背景、パネル |

---

## 2. シャドウシステム

4段階のシャドウ + グロウ3種。カードやパネルの深度を表現する。

### シャドウ変数

```css
:root {
  /* 4段階シャドウ */
  --shadow-subtle:    0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-medium:    0 4px 12px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.04);
  --shadow-prominent: 0 8px 24px rgba(0, 0, 0, 0.12), 0 4px 8px rgba(0, 0, 0, 0.06);
  --shadow-elevated:  0 16px 48px rgba(0, 0, 0, 0.16), 0 8px 16px rgba(0, 0, 0, 0.08);

  /* グロウ（アクセント光彩） */
  --glow-blue:   0 0 20px rgba(59, 125, 216, 0.3);
  --glow-pink:   0 0 20px rgba(217, 75, 110, 0.3);
  --glow-aqua:   0 0 20px rgba(46, 168, 143, 0.3);
}
```

### 使い分け

| シャドウ | 用途 | 適用例 |
|---------|------|--------|
| subtle | 静的要素 | カード、パネルのデフォルト |
| medium | ホバー状態 | カードホバー、ボタン |
| prominent | 浮上要素 | モーダル、ツールチップ |
| elevated | 最前面 | ドロップダウン、オーバーレイ |
| glow-* | アクセント強調 | CTA、アクティブ状態 |

---

## 3. グラスモーフィズム・深度エフェクト

### グラスカードクラス

グラスカードの CSS 正本は [theme-style.md](theme-style.md) §16。ここでは品質判断だけを扱い、クラス定義は再掲しない。

### 深度レイヤー

| レイヤー | z-index | backdrop-filter | 用途 |
|---------|---------|----------------|------|
| 背景 (L0) | 0 | なし | スライド背景 |
| コンテンツ (L1) | 1 | blur(8px) | カード、パネル |
| フロート (L2) | 10 | blur(16px) | ツールチップ、ポップオーバー |
| ナビ (L3) | 100 | blur(20px) | ナビゲーション、コントロール |

### 印刷安全代替

`backdrop-filter` は印刷時に無効になるため、`@media print` では代替スタイルを適用する。

```css
@media print {
  .glass-card,
  .glass-card-strong {
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    background: var(--bg-card);
    border: 1px solid var(--sumi-ink);
  }
}
```

---

## 4. タイポグラフィモジュラースケール

Perfect Fourth (1.333) ベースのスケール。既存の `--fs-*` 変数を補完する。

### フォントサイズ変数

| 変数名 | 計算 | 用途 |
|--------|------|------|
| `--fs-display` | 6.4rem | ヒーロー数値 |
| `--fs-title` | 5rem × scale | スライドタイトル |
| `--fs-heading` | 3rem × scale | セクション見出し |
| `--fs-subheading` | 2rem × scale | サブ見出し |
| `--fs-body-lg` | 1.8rem × scale | 大きめ本文 |
| `--fs-body` | 1.5rem × scale | 本文 |
| `--fs-small` | 1.4rem (min) | キャプション |
| `--fs-caption` | 1.2rem (min) | 注釈 |

### フォントウェイト変数

```css
:root {
  --fw-light: 300;
  --fw-regular: 400;
  --fw-medium: 500;
  --fw-semibold: 600;
  --fw-bold: 700;
}
```

### 使い分け

| 要素 | ウェイト | サイズ |
|------|---------|--------|
| タイトル | bold | --fs-title |
| 見出し | semibold | --fs-heading |
| 本文 | regular | --fs-body |
| 強調テキスト | semibold | --fs-body |
| キャプション | regular | --fs-small |
| 数値ハイライト | bold | --fs-heading 以上 |

---

## 5. アニメーションパターンライブラリ

### イージング変数（7種）

```css
:root {
  --ease-standard:   cubic-bezier(0.4, 0.0, 0.2, 1);    /* Material標準 */
  --ease-decelerate: cubic-bezier(0.0, 0.0, 0.2, 1);    /* 入場向き */
  --ease-spring:     cubic-bezier(0.34, 1.56, 0.64, 1);  /* バウンス感 */
  --ease-bounce:     cubic-bezier(0.68, -0.55, 0.27, 1.55); /* 弾み */
  --ease-dramatic:   cubic-bezier(0.7, 0, 0.3, 1);       /* 劇的 */
  --ease-sharp:      cubic-bezier(0.4, 0, 0.6, 1);       /* シャープ */
  --ease-smooth:     cubic-bezier(0.25, 0.1, 0.25, 1);   /* 滑らか */
}
```

### デュレーション（6段階）

| 変数名 | 値 | 用途 |
|--------|-----|------|
| `--duration-instant` | 0.1s | マイクロ状態変化 |
| `--duration-fast` | 0.15s | leave、ホバー |
| `--duration-normal` | 0.25s | enter、標準遷移 |
| `--duration-moderate` | 0.35s | カード展開 |
| `--duration-slow` | 0.5s | ページ遷移 |
| `--duration-dramatic` | 0.8s | ヒーロー演出 |

### スタガーパターン（5種）

| パターン名 | stagger値 | 用途 |
|-----------|----------|------|
| rapid | 0.03s | 大量要素（10個以上） |
| standard | 0.05s | リスト、カード（3-8個） |
| relaxed | 0.08s | パネル、セクション |
| dramatic | 0.12s | ヒーロー要素、少数強調 |
| wave | 0.15s | 波状アニメーション |

### スライドタイプ別推奨マッピング

| スライドタイプ | enter ease | leave ease | stagger |
|--------------|-----------|-----------|---------|
| title | decelerate | sharp | - |
| list | spring | standard | standard |
| compare | decelerate | standard | relaxed |
| flow | spring | sharp | standard |
| stats | bounce | standard | dramatic |
| diagram | dramatic | standard | relaxed |
| quote | smooth | decelerate | - |
| table | standard | sharp | rapid |
| chart | decelerate | standard | standard |

### GSAPでの使用例

```javascript
// イージングの多様化（3種以上使う）
gsap.timeline()
  .from('.title', {
    y: 30, opacity: 0,
    duration: 0.35,
    ease: 'power2.out'          // decelerate相当
  })
  .from('.card', {
    y: 20, opacity: 0,
    duration: 0.25,
    stagger: 0.05,
    ease: 'back.out(1.7)'      // spring相当
  }, '-=0.15')
  .from('.footer', {
    opacity: 0,
    duration: 0.2,
    ease: 'power1.inOut'        // smooth相当
  }, '-=0.1');
```

---

## 6. マイクロインタラクション

### ホバーパターン

#### lift & glow（持ち上げ＋光彩）

```css
.card-hover-lift {
  transition: transform 0.2s var(--ease-standard),
              box-shadow 0.2s var(--ease-standard);
}
.card-hover-lift:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-prominent);
}
```

#### border-glow（ボーダー光彩）

```css
.card-hover-border {
  transition: border-color 0.2s var(--ease-standard),
              box-shadow 0.2s var(--ease-standard);
  border: 2px solid transparent;
}
.card-hover-border:hover {
  border-color: var(--accent-blue-vivid);
  box-shadow: var(--glow-blue);
}
```

#### gradient-reveal（グラデーション出現）

```css
.card-hover-gradient {
  position: relative;
  overflow: hidden;
}
.card-hover-gradient::after {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--gradient-blue-pink);
  opacity: 0;
  transition: opacity 0.3s var(--ease-standard);
  pointer-events: none;
  border-radius: inherit;
}
.card-hover-gradient:hover::after {
  opacity: 0.08;
}
```

---

## 7. アクセシビリティ（WCAG 2.1 AA）

### prefers-reduced-motion

具体 CSS は [theme-style.md](theme-style.md) §17 を正本とする。本書では「定義されていること」を品質チェック対象にする。

### focus-visible

具体 CSS は [theme-style.md](theme-style.md) §17 を正本とする。本書ではボタン・リンク・ナビゲーション要素に適用されているかだけを確認する。

### 最低 opacity

UIテキスト要素（ナビゲーション、ラベル、キャプション等）の opacity は最低 **0.6** とする。

```css
/* NG: 読めない */
.nav-label { opacity: 0.3; }

/* OK: 読める */
.nav-label { opacity: 0.7; }
```

### ARIA live region

動的に変化するコンテンツ（スライド番号、進捗等）には `aria-live` を適用。

```html
<div class="slide-number" aria-live="polite" aria-atomic="true">
  <span class="current">1</span> / <span class="total">10</span>
</div>
```

### sr-only（スクリーンリーダー専用）

```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

```html
<button id="prev">
  <i class="fas fa-chevron-left"></i>
  <span class="sr-only">前のスライド</span>
</button>
<button id="next">
  <i class="fas fa-chevron-right"></i>
  <span class="sr-only">次のスライド</span>
</button>
```

---

## 8. ホワイトスペースシステム

8px ベースの9段階スペーシングスケールを使う。具体変数の正本は [theme-style.md](theme-style.md) のスペーシングスケール。

### スペーシング変数

再掲しない。`--space-*` の値は theme-style 側を参照する。

### 使い分け

| スペース | 用途 |
|---------|------|
| 1-2 | テキスト間隔、アイコンとラベル |
| 3-4 | カード内padding、要素間gap |
| 5-6 | セクション間、カード間gap |
| 7-8 | スライド内ブロック間 |
| 9 | ヒーロー領域の余白 |

---

## 9. 印刷安全代替パターン

印刷時に非対応なプロパティの代替スタイル。

### backdrop-filter 代替

```css
@media print {
  /* グラスモーフィズム → ソリッド背景 + ボーダー */
  .glass-card,
  .glass-card-strong {
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    background: var(--bg-card) !important;
    border: 1px solid var(--sumi-ink) !important;
  }
}
```

### box-shadow 代替

```css
@media print {
  /* カード影は全要素で強制オフ（SR-09 / 影がグレー塗りつぶしになる現象の恒久対策） */
  * {
    box-shadow: none !important;
  }

  /* 必要に応じてボーダーで奥行きを補う（シャドウ → ボーダー） */
  [class*="shadow"],
  .card,
  .panel {
    border: 1px solid #ccc !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
}
```

### グラデーション代替

```css
@media print {
  /* グラデーション → ソリッドカラー */
  .gradient-bg {
    background: var(--bg-dim) !important;
  }
}
```

---

## 10. デザイン品質チェックリスト

HTML生成時の最終確認15項目。

### カラー・ビジュアル

- [ ] ビビッドアクセント（`--accent-*-vivid`）が各スライドに1つ以上使用されているか
- [ ] グラデーションがタイトルスライドまたはCTA要素に適用されているか
- [ ] シャドウが4段階のうち適切なレベルで使用されているか
- [ ] カラーコード直書きではなくCSS変数を使用しているか

### アニメーション

- [ ] イージングが3種類以上使われているか（power2.out, back.out, power1.inOut 等）
- [ ] staggerパターンがスライドタイプに合っているか
- [ ] leaveアニメーションがenterより短いか
- [ ] duration が 0.1s-0.5s の範囲内か（0.6s以上は禁止）

### アクセシビリティ

- [ ] `prefers-reduced-motion` が定義されているか
- [ ] `focus-visible` がボタン・リンクに適用されているか
- [ ] `sr-only` クラスがナビゲーションボタンに適用されているか
- [ ] `aria-live="polite"` がスライド番号に設定されているか
- [ ] UIテキスト要素の opacity が 0.6 以上か

### 品質

- [ ] フォントウェイト変数（--fw-*）を使用しているか
- [ ] スペーシング変数（--space-*）で余白を管理しているか
