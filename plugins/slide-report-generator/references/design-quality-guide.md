# デザイン品質ガイド

<!-- css-route: hand-slide -->
<!-- この宣言より後ろの var() は hand-slide 経路の :root とだけ照合される (lint-contract-drift.py check G)。経路が違う例を載せるときは、その直前に別の css-route 宣言を置く -->

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは設計の文脈・例・適用ガイドのみ。規則の正本は SR-ID で参照すること

**責務**: Apple品質のビジュアルデザインを実現するための文脈・適用例・アンチパターン。
**規則の正本**: アクセントの作り方（色ではなく反転面） → [SR-2-04](spec-registry.md#sr-2-04)、強調は1面1箇所 → [SR-2-05](spec-registry.md#sr-2-05)、面積配分 60-30-10 → [SR-2-06](spec-registry.md#sr-2-06)、意味を色で区別しない → [SR-2-07](spec-registry.md#sr-2-07)、階層は罫で作る（影・グロウ不使用） → [SR-2-09](spec-registry.md#sr-2-09)、a11y全般 → §9（[SR-9-01](spec-registry.md#sr-9-01)〜[SR-9-06](spec-registry.md#sr-9-06)）、reduced-motion → [SR-6-08](spec-registry.md#sr-6-08)

---

## 1. アクセントの作り方

**規則の正本は [SR-2-04](spec-registry.md#sr-2-04)** で、本ファイルは hex を再掲しない（2 箇所に書くと片方だけ古くなる）。
本節が持つのは「なぜ色でなく反転で強調するか」＝手段と用途の対応だけ:

| 手段 | 作り方 | 用途 |
|------|--------|------|
| 反転面 | 地色と文字色を入れ替える | 面内で最も伝えたい 1 ブロック |
| 濃度段 | 図解の内部に限り、単一色相の濃度を変える | 図解内の系列・階層の区別 |
| 罫 | 1px の下罫を引く | 領域の区切り（囲み・影の代わり） |

段数・彩度・面積の上限は `skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_002 が正本。本ファイルへ値を写経しない。

### WCAG AA コントラスト比

反転面は地色と文字色の入れ替えなので、通常面と同じ組み合わせのコントラスト比がそのまま効く。地色・文字色の実測は [SR-9-01](spec-registry.md#sr-9-01) を参照。濃度段を使う場合は、その段が文字を載せる面かどうかで判定を分ける（文字を載せるなら 4.5:1 以上、図解の面塗りのみなら隣接段との差が判別できること）。

### 濃度と反転の使い分け

色相を増やすグラデーションは使わない。通常面は地色・パネル地・文字色の濃度差で整理し、
最重要ブロックだけを反転面にする。これにより、色覚や印刷条件が変わっても強調順位が
失われず、配色トークンを別名で重複定義せずに済む。

---

## 2. 階層システム（罫）

深度は影ではなく**罫**で作る（[SR-2-09](spec-registry.md#sr-2-09)）。角丸は 0px（写真・図のみ例外）。線の太さと hairline の値は `skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_003 / VGCONST_004 が正本で、本ファイルは値を再掲しない。

### 使い分け

| 手段 | 用途 | 適用例 |
|------|------|--------|
| 1px の下罫 | 区切りの既定 | カード、パネル、リスト項目の境界 |
| hairline（最も細い罫） | 従属的な区切り | 表の行間、図解内の補助線 |
| 2px の罫 | その面で 1 本だけの主線 | 図解の主フロー、セクションの区切り |
| 反転面 | 最前面・最重要 | モーダル、面内で最も伝えたい 1 ブロック |

`:root` に定義されている `--shadow-*` / `--glow-*` は、CSS トークン実体の差し替えが済むまで残る過渡的定義（定義本体は [theme-style.md](theme-style.md) §4）であり、新しい面では選ばない。

---

## 3. 深度レイヤー

**ぼかし（`backdrop-filter`）を意匠手段として使わない。** 深度は §2 と同じく罫と反転で作る（SR-2-09）。ぼかしは背面の絵柄を透かすことでしか階層を示せず、地が単色の面では何も見えないうえ、印刷では無効化されて階層が消える。

| レイヤー | z-index | 階層の示し方 | 用途 |
|---------|---------|-------------|------|
| 背景 (L0) | 0 | なし | スライド背景 |
| コンテンツ (L1) | 1 | 1px の下罫 | カード、パネル |
| フロート (L2) | 10 | 地色の塗り + 全周 1px の罫 | ツールチップ、ポップオーバー |
| ナビ (L3) | 100 | 地色の塗り + 境界側 1px の罫 | ナビゲーション、コントロール |

前面のレイヤーは背面を透かさず、地色で塗りつぶす。画面と紙で同じ階層が出る。

`.glass-card` / `.glass-card-strong`（定義本体は [theme-style.md](theme-style.md) §16）は CSS トークン実体の差し替えが済むまで残る過渡的定義であり、新しい面では選ばない。

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

### フォントウェイト

**ウェイトは 3 段のみ**（標準 / 中間 / 最も太い段）。段の値・段数・最も太い段の出現回数は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/references/visual-generation-rules.md` VGCONST_005 が正本で、ここに値を書かない（SR-3-10）。`:root` の `--fw-light` / `--fw-semibold` は CSS トークン実体の差し替えが済むまで残る過渡的定義（定義本体は [theme-style.md](theme-style.md) §4）であり、新しい面では選ばない。

### 使い分け

| 要素 | ウェイト段 | サイズ |
|------|-----------|--------|
| タイトル | 最も太い段（面に 1 箇所） | --fs-title |
| 見出し | 中間の段 | --fs-heading |
| 本文 | 標準の段 | --fs-body |
| 強調テキスト | 中間の段 | --fs-body |
| キャプション | 標準の段 | --fs-small |
| 数値ハイライト | 最も太い段（タイトルと排他） | --fs-heading 以上 |

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

#### lift（持ち上げ）

```css
.card-hover-lift {
  transition: transform 0.2s var(--ease-standard);
}
.card-hover-lift:hover {
  transform: translateY(-4px);
}
```

#### border-emphasis（罫の強調）

```css
.card-hover-border {
  transition: border-color 0.2s var(--ease-standard);
  border-bottom: 1px solid currentColor;
  opacity: 0.7;
}
.card-hover-border:hover {
  opacity: 1;
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
    background: var(--bg-card, #F0F0F0) !important;
    border: 1px solid var(--sumi-ink, #FAFAFA) !important;
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
    background: var(--bg-dim, #F5F5F5) !important;
  }
}
```

---

## 10. デザイン品質チェックリスト

HTML生成時の最終確認15項目。

### カラー・ビジュアル

- [ ] 面に置いた色が 地 / 文字 / 反転面 の 3 つ以内におさまっているか（[SR-2-01](spec-registry.md#sr-2-01)）
- [ ] 強調を色で作らず反転面 1 個で作っているか（[SR-2-04](spec-registry.md#sr-2-04) / [SR-2-05](spec-registry.md#sr-2-05)）
- [ ] 面積配分が 地 60 / 文字とパネル 30 / 反転面 10 におさまっているか（[SR-2-06](spec-registry.md#sr-2-06)）
- [ ] 対比・前後・可否を色相で区別せず 位置 / 順序 / ラベル / 罫 で示しているか（[SR-2-07](spec-registry.md#sr-2-07)）
- [ ] 影・グロウを使わず罫で階層を作り、角丸が 0px か（[SR-2-09](spec-registry.md#sr-2-09)）
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

- [ ] ウェイトが 3 段に収まり、最も太い段が 1 面 1 箇所か（SR-3-10）
- [ ] ぼかしで階層を作っていないか（罫と反転で作る・SR-2-09）
- [ ] スペーシング変数（--space-*）で余白を管理しているか
