# テーマ・スタイルガイドライン

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは CSS 実装テンプレート・カスタマイズ例の参照集。規則の正本は SR-ID で参照すること

**責務**: カラーパレット・CSS変数・共通スタイル・アニメーション速度の**実装リファレンス**（CSS コード集）。
**規則の正本**:
- 16:9 アスペクト比 → [SR-1-01](spec-registry.md#sr-1-01)、解像度 → [SR-1-02](spec-registry.md#sr-1-02)、単位 → [SR-1-04](spec-registry.md#sr-1-04)
- カラー全般 → §2（[SR-2-01](spec-registry.md#sr-2-01)〜[SR-2-09](spec-registry.md#sr-2-09)）
- フォント全般 → §3（[SR-3-01](spec-registry.md#sr-3-01)〜[SR-3-08](spec-registry.md#sr-3-08)）
- レイアウト 3層 → [SR-4-01](spec-registry.md#sr-4-01)、Before/After → [SR-4-03](spec-registry.md#sr-4-03)
- コードブロック → §10
このファイル内の値が SR と矛盾した場合、SR を優先する。

---

## 0. 量産対応のためのCSS変数設計

### 設計原則

プレゼンテーションを量産する際、**現在のスライド内容を毎回反映できるテンプレート構造**が必要。
CSS変数を活用することで、カラー・フォント・余白を一箇所で管理し、迅速なカスタマイズを実現する。

### 主要なカスタマイズポイント

| カテゴリ | CSS変数 | 用途 | デフォルト値 |
|---------|---------|------|-------------|
| **フォントスケール** | `--font-scale` | 全体のフォントサイズ倍率 | 1.3 |
| **ナビゲーション余白** | `--nav-arrow-padding` | 左右矢印用のパディング | 3rem |
| **ナビゲーション余白** | `--nav-top-padding` | 上部プログレスバー用 | 1rem |
| **ナビゲーション余白** | `--nav-bottom-padding` | 下部ドット用 | 2rem |
| **アクセントカラー** | `--wave-blue` | メインアクセント色 | #7E9CD8 |
| **課題カラー** | `--sakura-pink` | Before/課題の色 | #D27E99 |
| **解決カラー** | `--wave-aqua` | After/解決の色 | #7AA89F |

### カスタマイズ例

```css
/* プロジェクトごとの設定を上書き */
:root {
  /* フォントを小さくする場合 */
  --font-scale: 1.1;

  /* ナビゲーション余白をタイトに */
  --nav-arrow-padding: 2rem;
  --nav-bottom-padding: 1.5rem;

  /* アクセントカラーを変更 */
  --wave-blue: #5E9CD8;
}
```

### 量産時のワークフロー

1. **テンプレートHTML** (`assets/slide-template.html`) をコピー
2. **CSS変数** (`:root`セクション) を調整
3. **スライド内容** (`slider__item`要素) を差し替え
4. **検証・デプロイ**

---

## 1. 16:9アスペクト比（必須制約）

### 重要原則

**すべてのスライドは16:9アスペクト比を厳守すること。**

これにより以下を保証する：
- プロジェクター/ディスプレイでの正しい表示
- PDF出力時の一貫したレイアウト
- 異なるウィンドウサイズでも崩れないデザイン

### CSS変数定義

```css
:root {
  /* 16:9アスペクト比 */
  --slide-aspect-ratio: 16 / 9;

  /* ビューポートに収まる最大サイズを計算 */
  --slide-max-width: min(100vw, calc(100vh * (16 / 9)));
  --slide-max-height: min(100vh, calc(100vw * (9 / 16)));

  /* 基準解像度（設計基準） */
  --slide-base-width: 1920;
  --slide-base-height: 1080;
}
```

### スライドコンテナCSS

```css
/* スライダー全体: ビューポート全体を使用しつつ16:9を維持 */
.slider {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--bg-dark);
}

/* スライドコンテナ: 16:9を強制 */
.slider__container {
  display: flex;
  width: var(--slide-max-width);
  height: var(--slide-max-height);
  aspect-ratio: 16 / 9;
}

/* 各スライド: 親コンテナに合わせて16:9を維持 */
.slider__item {
  min-width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--nav-top-padding) var(--nav-arrow-padding) var(--nav-bottom-padding);
  aspect-ratio: 16 / 9;
}

/* スライドコンテンツ: 16:9内に収まるよう制約 */
.slider__content {
  width: 100%;
  max-width: min(1600px, 90%);
  max-height: 90%;
  visibility: hidden;
  overflow: hidden;
}
```

### 実装チェックリスト

| 項目 | 確認方法 |
|------|----------|
| aspect-ratio: 16/9 が設定されているか | .slider__containerと.slider__itemを確認 |
| ビューポート変更時も崩れないか | ブラウザをリサイズして確認 |
| コンテンツがはみ出していないか | 各スライドで視覚確認 |
| 上下左右に均等な余白があるか | 黒帯（レターボックス）が表示されるか確認 |

### よくある問題と対処

| 問題 | 原因 | 解決策 |
|------|------|--------|
| 縦長ウィンドウでスライドが切れる | height: 100%のみで制約なし | aspect-ratio: 16/9 を追加 |
| 横長ウィンドウで間延びする | width: 100vwで固定 | max-width: calc(100vh * 16/9) を使用 |
| コンテンツが枠外に出る | overflow設定なし | overflow: hidden を追加 |
| PDF出力でずれる | 印刷時のサイズ計算問題 | @media print で固定サイズ指定 |

---

## 2. Kanagawaカラーパレット

### テーマ選択

**Lotus White**（デフォルト推奨）、**ライトテーマ**、**ダークテーマ**の3種類を提供。

| テーマ | 用途 | 背景色 | テキスト色 | 特徴 |
|--------|------|--------|-----------|------|
| **Lotus White** | **印刷配布、明るい環境、ビジネス資料（推奨）** | #fafafa | #43436c | 黄色みのない白、Lotus公式アクセント |
| ライト | 印刷配布、明るい環境 | #FFFFFF | #2D2D2D | 純白背景 |
| ダーク | プロジェクター投影、暗い環境 | #1F1F28 | #DCD7BA | 目に優しい暗色 |

### Lotus White（デフォルト推奨）

Kanagawa公式Lotusパレットのアクセントカラーを維持しつつ、背景を黄色みのないニュートラルな白に調整したカスタムバリエーション。

| 変数名 | カラーコード | 用途 |
|--------|-------------|------|
| `--bg-dark` | #fafafa | 背景（メイン・ニュートラル白） |
| `--bg-dim` | #f0f0f2 | 背景（サブ・青み灰） |
| `--bg-card` | #e8e8ec | カード背景（青み灰） |
| `--fg` | #43436c | テキスト（lotusInk2） |
| `--fg-dim` | #716e61 | テキスト（lotusGray2） |
| `--fg-muted` | #888888 | テキスト（ミュート・汎用） |
| `--wave-blue` | #4d699b | アクセント（lotusBlue4） |
| `--spring-violet` | #624c83 | アクセント（lotusViolet4） |
| `--sakura-pink` | #b35b79 | 警告・課題（lotusPink） |
| `--wave-aqua` | #597b75 | 成功・解決（lotusAqua） |
| `--autumn-yellow` | #de9800 | 強調（lotusYellow3） |

**Lotus White CSS変数（デフォルト推奨）**:
```css
:root {
  /* Kanagawa Lotus White - 白背景カスタム版（デフォルト推奨） */
  --bg-dark: #fafafa;      /* ニュートラル白 */
  --bg-dim: #f0f0f2;       /* 薄いグレー（青み） */
  --bg-card: #e8e8ec;      /* カード背景（青み） */
  --fg: #43436c;           /* lotusInk2 */
  --fg-dim: #716e61;       /* lotusGray2 */
  --wave-blue: #4d699b;    /* lotusBlue4 */
  --spring-violet: #624c83; /* lotusViolet4 */
  --sakura-pink: #b35b79;  /* lotusPink */
  --wave-aqua: #597b75;    /* lotusAqua */
  --autumn-yellow: #de9800; /* lotusYellow3 */
  --sumi-ink: #e0e0e4;     /* ニュートラルグレー */
  --fuji-gray: #8a8a90;    /* ニュートラルグレー */
}
```

### ライトテーマ

| 変数名 | カラーコード | 用途 |
|--------|-------------|------|
| `--bg-dark` | #FFFFFF | 背景（メイン） |
| `--bg-dim` | #F5F5F5 | 背景（サブ） |
| `--bg-highlight` | #EBEBEB | ハイライト背景 |
| `--bg-card` | #F0F0F0 | カード背景 |
| `--sumi-ink` | #FAFAFA | 背景（補助） |
| `--fg` | #2D2D2D | テキスト（メイン） |
| `--fg-dim` | #555555 | テキスト（サブ） |
| `--fg-muted` | #888888 | テキスト（薄い） |

**ライトテーマCSS変数（デフォルト）**:
```css
:root {
  /* Background Colors - Light Theme */
  --bg-dark: #FFFFFF;
  --bg-dim: #F5F5F5;
  --bg-highlight: #EBEBEB;
  --bg-card: #F0F0F0;
  --sumi-ink: #FAFAFA;

  /* Foreground Colors - Dark Text */
  --fg: #2D2D2D;
  --fg-dim: #555555;
  --fg-muted: #888888;
}
```

### ダークテーマ

| 変数名 | カラーコード | 用途 |
|--------|-------------|------|
| `--bg-dark` | #1F1F28 | 背景（メイン） |
| `--bg-dim` | #2A2A37 | 背景（サブ） |
| `--bg-highlight` | #363646 | ハイライト背景 |
| `--bg-card` | #363646 | カード背景 |
| `--sumi-ink` | #16161D | 背景（補助） |
| `--fg` | #DCD7BA | テキスト（メイン） |
| `--fg-dim` | #C8C093 | テキスト（サブ） |
| `--fg-muted` | #727169 | テキスト（薄い） |

**ダークテーマCSS変数**:
```css
:root {
  /* Background Colors - Dark Theme */
  --bg-dark: #1F1F28;
  --bg-dim: #2A2A37;
  --bg-highlight: #363646;
  --bg-card: #363646;
  --sumi-ink: #16161D;

  /* Foreground Colors - Light Text */
  --fg: #DCD7BA;
  --fg-dim: #C8C093;
  --fg-muted: #727169;
}
```

### アクセントカラー（共通）

| 変数名 | カラーコード | 用途 |
|--------|-------------|------|
| `--wave-blue` | #7E9CD8 | メインアクセント・リンク |
| `--spring-violet` | #9CABCA | アクセント（紫） |
| `--sakura-pink` | #D27E99 | 警告・課題・Before |
| `--wave-aqua` | #7AA89F | 成功・解決策・After |
| `--autumn-yellow` | #DCA561 | 強調・数字 |

### 補助カラー

| 変数名 | カラーコード | 用途 |
|--------|-------------|------|
| `--sumi-ink` | #363646 | ボーダー・区切り（ダーク） |
| `--fuji-gray` | #54546D | 補助色・ホバー |

---

## 3. カラー使用ガイド

### 意味に応じた色選択

| 意味 | 推奨カラー | CSS変数 |
|------|-----------|---------|
| 重要・メイン | 青 | `--wave-blue` |
| 課題・問題・Before | ピンク | `--sakura-pink` |
| 解決・成功・After | 青緑 | `--wave-aqua` |
| 強調・数字・警告 | 黄 | `--autumn-yellow` |
| 補足・サブ | 紫 | `--spring-violet` |
| 背景・カード | 暗灰 | `--bg-dim` |

### 比較スライドの色

```css
/* Before側（左） */
.compare-item.left {
  border-top: 4px solid var(--sakura-pink);
}
.compare-item.left .value {
  color: var(--sakura-pink);
}

/* After側（右） */
.compare-item.right {
  border-top: 4px solid var(--wave-aqua);
}
.compare-item.right .value {
  color: var(--wave-aqua);
}
```

---

## 4. CSS変数定義（完全版）

### 全変数リスト

```css
:root {
  /* ========================================
     カラーパレット（ライトテーマ - デフォルト）
     ======================================== */
  --bg-dark: #FFFFFF;
  --bg-dim: #F5F5F5;
  --bg-highlight: #EBEBEB;
  --bg-card: #F0F0F0;
  --sumi-ink: #FAFAFA;
  --fg: #2D2D2D;
  --fg-dim: #555555;
  --fg-muted: #888888;

  /* アクセントカラー（共通） */
  --wave-blue: #7E9CD8;
  --spring-violet: #9CABCA;
  --sakura-pink: #D27E99;
  --wave-aqua: #7AA89F;
  --autumn-yellow: #DCA561;
  --fuji-gray: #54546D;

  /* ========================================
     ビビッドアクセントカラー（彩度強化版）
     既存Lotus変数はそのまま維持
     ======================================== */
  --accent-blue-vivid: #3B7DD8;    /* 彩度 34%→60% */
  --accent-pink-vivid: #D94B6E;    /* 彩度 32%→60% */
  --accent-aqua-vivid: #2EA88F;    /* 彩度 16%→57% */
  --accent-violet-vivid: #7B4FBA;  /* 彩度深化 */
  --accent-yellow-vivid: #F5A623;  /* 高彩度維持 */

  /* ========================================
     シャドウシステム（4段階 + グロウ3種）
     ======================================== */
  --shadow-subtle:    0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-medium:    0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
  --shadow-prominent: 0 8px 24px rgba(0,0,0,0.12), 0 4px 8px rgba(0,0,0,0.06);
  --shadow-elevated:  0 16px 48px rgba(0,0,0,0.16), 0 8px 16px rgba(0,0,0,0.08);
  --glow-blue:  0 0 20px rgba(59,125,216,0.3);
  --glow-pink:  0 0 20px rgba(217,75,110,0.3);
  --glow-aqua:  0 0 20px rgba(46,168,143,0.3);

  /* ========================================
     グラデーション
     ======================================== */
  --gradient-blue-pink:   linear-gradient(135deg, var(--accent-blue-vivid), var(--accent-pink-vivid));
  --gradient-blue-aqua:   linear-gradient(135deg, var(--accent-blue-vivid), var(--accent-aqua-vivid));
  --gradient-violet-pink: linear-gradient(135deg, var(--accent-violet-vivid), var(--accent-pink-vivid));
  --gradient-subtle:      linear-gradient(135deg, var(--bg-dim), var(--bg-card));

  /* ========================================
     スペーシングスケール（8pxベース）
     ======================================== */
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.5rem;    /* 24px */
  --space-6: 2rem;      /* 32px */
  --space-7: 3rem;      /* 48px */
  --space-8: 4rem;      /* 64px */
  --space-9: 6rem;      /* 96px */

  /* ========================================
     フォントウェイト
     ======================================== */
  --fw-light: 300;
  --fw-regular: 400;
  --fw-medium: 500;
  --fw-semibold: 600;
  --fw-bold: 700;

  /* ========================================
     フォントサイズスケール
     ======================================== */
  --font-scale: 1.3;

  /* 計算されたフォントサイズ */
  --fs-title: calc(5rem * var(--font-scale));
  --fs-subtitle: calc(2.5rem * var(--font-scale));
  --fs-heading: calc(3rem * var(--font-scale));
  --fs-subheading: calc(2rem * var(--font-scale));
  --fs-body: calc(1.5rem * var(--font-scale));
  --fs-body-lg: calc(1.8rem * var(--font-scale));
  --fs-small: calc(1.4rem * var(--font-scale)); /* 最小1.4rem */
  --fs-icon-lg: calc(6rem * var(--font-scale));
  --fs-icon-md: calc(3rem * var(--font-scale));
  --fs-icon-sm: calc(2rem * var(--font-scale));

  /* ========================================
     ナビゲーション・余白設定
     ======================================== */
  --nav-arrow-padding: 3rem;        /* 左右矢印用のパディング */
  --nav-top-padding: 1rem;          /* 上部プログレスバー用 */
  --nav-bottom-padding: 2rem;       /* 下部ドットインジケーター用 */
}
```

**重要**: `--font-scale`の値を変更するだけで全体のサイズを調整できる。
**重要**: `--fs-small` は最小1.4remを維持する（視認性確保）。

---

## 5. フォントサイズ一覧

| 用途 | CSS変数 | 基準値 | 最小値 |
|------|---------|--------|--------|
| タイトル | `var(--fs-title)` | 5rem × scale | - |
| サブタイトル | `var(--fs-subtitle)` | 2.5rem × scale | - |
| 見出し | `var(--fs-heading)` | 3rem × scale | - |
| 小見出し | `var(--fs-subheading)` | 2rem × scale | - |
| 本文 | `var(--fs-body)` | 1.5rem × scale | - |
| 大きめ本文 | `var(--fs-body-lg)` | 1.8rem × scale | - |
| 小さめ文字 | `var(--fs-small)` | 1.4rem × scale | **1.4rem** |

---

## 6. 共通CSS

### リセット・基本設定

```css
*, *:after, *:before {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body, html {
  height: 100%;
  font-family: 'Noto Sans JP', sans-serif;
  background: var(--bg-dark);
  color: var(--fg);
  overflow: hidden;
}
```

### スライダー基本

```css
.slider {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.slider__container {
  display: flex;
  height: 100%;
  transition: none;
}

.slider__item {
  min-width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--nav-top-padding) var(--nav-arrow-padding) var(--nav-bottom-padding);
}

.slider__content {
  width: 100%;
  max-width: 1200px;
  visibility: hidden;
}
```

---

## 7. アイコンスタイル

### アイコンラッパー

```css
.icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--bg-dim);
  margin-bottom: 1rem;
}

.icon-wrapper i {
  font-size: 2.5rem;
  color: var(--wave-blue);
}

/* アクセントカラー */
.icon-wrapper.accent-pink i { color: var(--sakura-pink); }
.icon-wrapper.accent-aqua i { color: var(--wave-aqua); }
.icon-wrapper.accent-yellow i { color: var(--autumn-yellow); }
.icon-wrapper.accent-violet i { color: var(--spring-violet); }
```

---

## 8. 進捗バー

```css
.progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 4px;
  background: var(--sumi-ink);
  z-index: 100;
}

.progress {
  height: 100%;
  background: linear-gradient(90deg, var(--wave-blue), var(--sakura-pink));
  transition: width 0.5s ease;
}
```

---

## 9. ナビゲーション（ドットインジケーター）

### 9.1 基本構造

```css
/* ドットペジネーション（ライトテーマ対応） */
.pagination {
  position: fixed;
  bottom: var(--nav-bottom-padding);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  z-index: 100;
}

.pagination .dot {
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.3s ease;
}

.pagination .dot.active {
  transform: scale(1.4);
}

.pagination .dot:hover {
  transform: scale(1.3);
  filter: brightness(1.2);
}
```

### 9.2 5個区切りマイルストーン方式（標準）

5個目ごとにアクセント色で視覚的に区切り、現在位置の把握を容易にする。セクションナビ（§8）で構造を示し、ページネーションは位置インジケーターに徹する。

**HTML**: シンプルなドット（data-index のみ）
```html
<div class="pagination">
  <span class="dot active" data-index="0"></span>
  <span class="dot" data-index="1"></span>
  <span class="dot" data-index="2"></span>
  <!-- ... -->
</div>
```

**CSS**: 5個区切りマイルストーン
```css
/* デフォルトドット色 */
.pagination .dot {
  background: var(--fg);
  opacity: 0.25;
}

.pagination .dot.active {
  background: var(--fg);
  opacity: 1;
  transform: scale(1.4);
}

/* 5個区切りマイルストーン: 5番目ごとにアクセント色で視覚的に区切る */
.pagination .dot:nth-child(5n) {
  background: var(--accent-aqua-vivid);
  opacity: 0.5;
  width: 0.7rem;
  height: 0.7rem;
  margin-right: 0.5rem;
}

.pagination .dot:nth-child(5n).active {
  background: var(--accent-aqua-vivid);
  opacity: 1;
  transform: scale(1.3);
}
```

**設計意図**:
- セクションの構造はセクションナビ（常時表示）で把握できる
- ページネーションは「全体の中のどこか」を示す位置インジケーター
- 5個区切りで数えやすく、25枚超のスライドでも現在位置が明確

### 9.3 代替方式: セクション別色分け（オプション）

セクションナビがない場合や、ドットでもセクション構造を示したい場合に使用。

```css
/* セクション別ドット色: 非アクティブ = 30% opacity、アクティブ = フルカラー */
.pagination .dot[data-section="opening"] { background: rgba(59, 125, 216, 0.3); }
.pagination .dot[data-section="opening"].active { background: var(--accent-blue-vivid); }
/* ... 各セクション分定義 */
```

| セクション | data-section | 非アクティブ色（30%） | アクティブ色 |
|-----------|-------------|---------------------|------------|
| オープニング | opening | rgba(59,125,216,0.3) | --accent-blue-vivid |
| 講義 | lecture | rgba(46,168,143,0.3) | --accent-aqua-vivid |
| デモ | demo | rgba(245,166,35,0.3) | --accent-yellow-vivid |
| ワークショップ | ws | rgba(123,79,186,0.3) | --accent-violet-vivid |
| まとめ | summary | rgba(217,75,110,0.3) | --accent-pink-vivid |

---

## 10. コントロール（左右矢印）

```css
.slider-controls {
  position: fixed;
  top: 50%;
  width: 100%;
  transform: translateY(-50%);
  display: flex;
  justify-content: space-between;
  padding: 0 var(--nav-arrow-padding);
  z-index: 100;
  pointer-events: none;
}

.slider-controls button {
  width: 50px;
  height: 50px;
  background: rgba(126, 156, 216, 0.2);  /* ライトテーマ用: 青系半透明 */
  border: 2px solid var(--wave-blue);
  border-radius: 50%;
  color: var(--wave-blue);
  font-size: 1.2rem;
  cursor: pointer;
  transition: all 0.3s ease;
  pointer-events: auto;
}

.slider-controls button:hover {
  background: var(--wave-blue);
  border-color: var(--wave-blue);
  color: white;
  transform: scale(1.1);
}

.slider-controls button:active {
  transform: scale(0.95);
}
```

---

## 11. ページ番号表示

```css
.page-indicator {
  position: fixed;
  bottom: var(--nav-bottom-padding);
  right: var(--nav-arrow-padding);
  font-size: calc(var(--fs-small) * 1.3);  /* やや大きめ */
  color: #444;
  background: rgba(126, 156, 216, 0.15);
  border: 1px solid rgba(126, 156, 216, 0.3);
  padding: 0.5rem 1rem;
  border-radius: 20px;
  z-index: 100;
  font-weight: 600;
}

.page-indicator .current {
  color: var(--wave-blue);
  font-weight: 700;
}

.page-indicator .separator {
  margin: 0 0.3rem;
}
```

**HTML例**:
```html
<div class="page-indicator">
  <span class="current">1</span>
  <span class="separator">/</span>
  <span class="total">10</span>
</div>
```

**JavaScript更新ロジック**:
```javascript
updatePageIndicator() {
  const currentEl = document.querySelector('.page-indicator .current');
  const totalEl = document.querySelector('.page-indicator .total');
  currentEl.textContent = this.index + 1;
  totalEl.textContent = this.items.length;
}
```

---

## 12. アジェンダインジケーター（左上）

スライド左上に表示されるアジェンダインジケーター。現在のセクションを表示し、クリックで該当スライドにジャンプできる。

```css
/* アジェンダインジケーター */
.agenda-indicator {
  position: fixed;
  top: 1rem;
  left: 1rem;
  z-index: 100;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  max-width: 50vw;
}

.agenda-indicator-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.8rem 0.4rem 0.4rem;
  background: rgba(126, 156, 216, 0.2);
  border: 1px solid rgba(126, 156, 216, 0.4);
  border-radius: 16px;
  cursor: pointer;
  text-decoration: none;
  color: #333;
  transition: all 0.3s ease;
  font-size: 0.8rem;
}

.agenda-indicator-item:hover {
  background: rgba(126, 156, 216, 0.4);
  transform: translateY(-2px);
}

.agenda-indicator-item.active {
  background: var(--wave-blue);
  border-color: var(--wave-blue);
  color: white;
}

.agenda-num {
  width: 24px;
  height: 24px;
  min-width: 24px;
  background: #666;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
}

.agenda-indicator-item.active .agenda-num {
  background: white;
  color: var(--wave-blue);
}

.agenda-text {
  white-space: nowrap;
}
```

**HTML例**:
```html
<div class="agenda-indicator">
  <a href="#slide-3" class="agenda-indicator-item active">
    <span class="agenda-num">1</span>
    <span class="agenda-text">自己紹介</span>
  </a>
  <a href="#slide-7" class="agenda-indicator-item">
    <span class="agenda-num">2</span>
    <span class="agenda-text">課題</span>
  </a>
  <!-- 他のアジェンダアイテム -->
</div>
```

---

## 13. アニメーション速度ガイドライン

### 基本原則

GSAPアニメーションは**高速・スムーズ**を基本とする。

### スライド遷移

```javascript
// メインスライド遷移（左右移動）
duration: 0.25
ease: 'power3.inOut'

// enterアニメーション開始タイミング
'-=0.15'  // 遷移と並行して開始
```

### 要素アニメーション推奨値

| 要素タイプ | duration | stagger | 備考 |
|-----------|----------|---------|------|
| タイトル | 0.25-0.3s | - | アイコンは0.3-0.4s |
| リストアイテム | 0.2s | 0.05s | 要素が多い場合はstaggerを短く |
| カード・パネル | 0.3s | 0.08s | 同時出現は同一duration |
| フェードイン | 0.2s | 0.03-0.05s | leave時はさらに短く |

### leaveアニメーション

退場アニメーションは入場より**短く**設定：

```javascript
leave: {
  duration: 0.15-0.2s,
  stagger: 0.03-0.05s
}
```

### NG例

```javascript
// 遅すぎる（ユーザーがストレスを感じる）
duration: 0.6  // NG
stagger: 0.15  // NG（要素が多いと遅い）

// 推奨
duration: 0.25-0.3
stagger: 0.05-0.08
```

---

## 14. ユーティリティクラス

### テキスト関連

| クラス | 用途 |
|--------|------|
| `.text-note` | 注釈・補足テキスト（グレー） |
| `.text-emphasis` | 強調テキスト |
| `.highlight` | ハイライト（黄色） |

### 実装例

```css
.text-note {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

.text-emphasis {
  font-weight: 700;
  color: var(--wave-blue);
}

.highlight {
  background: var(--autumn-yellow);
  color: var(--bg-dark);
  padding: 0.2em 0.4em;
  border-radius: 4px;
}
```

---

## 15. 印刷用CSS

A4横向き印刷に最適化されたスタイル。ページ番号自動追加、ボックス背景色の視認性確保を含む。

```css
@media print {
  @page {
    size: A4 landscape;
    margin: 3mm;
  }

  /* SR-09 カード影は全要素で強制オフ（影がグレー塗りつぶしになる現象の恒久対策） */
  * {
    box-shadow: none !important;
  }

  /* 印刷不要な要素を非表示 */
  .nav-btn,
  .dot-pagination,
  .slide-counter,
  .agenda-indicator,
  .progress-bar {
    display: none !important;
  }

  /* スライド表示 */
  .slider__container {
    display: block !important;
    transform: none !important;
  }

  .slider__item {
    display: flex !important;
    page-break-after: always;
    page-break-inside: avoid;
    width: 291mm;
    height: 204mm;
    padding: 8mm 10mm;
    border: 1px solid #ccc;
    background: white !important;
    overflow: hidden;
  }

  /* 非表示スライドは印刷しない */
  .slider__item[data-hidden="true"] {
    display: none !important;
  }

  /* ページ番号 */
  body {
    counter-reset: page-counter;
  }

  .slider__item:not([data-hidden="true"]) {
    counter-increment: page-counter;
  }

  .slider__item:not([data-hidden="true"])::after {
    content: counter(page-counter);
    position: absolute;
    bottom: 8mm;
    right: 12mm;
    font-size: 14pt;
    color: #666;
    font-weight: 500;
  }

  /* ボックス類の背景色（印刷で見やすく） */
  .list-item,
  .stat-item,
  .grid-card,
  .compare-panel,
  .agenda-item,
  .icon-grid-item,
  .flow-step {
    background: #E3E9F0 !important;
    border: 1px solid #B8C4D0 !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
}
```

---

## 16. グラスモーフィズムユーティリティクラス

```css
/* 標準グラス */
.glass-card {
  background: rgba(250, 250, 250, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 16px;
  box-shadow: var(--shadow-medium);
}

/* 強調グラス */
.glass-card-strong {
  background: rgba(250, 250, 250, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  box-shadow: var(--shadow-prominent);
}
```

---

## 17. アクセシビリティスタイル

### focus-visible

```css
:focus-visible {
  outline: 3px solid var(--accent-blue-vivid);
  outline-offset: 2px;
  border-radius: 4px;
}

button:focus-visible,
a:focus-visible {
  outline: 3px solid var(--accent-blue-vivid);
  outline-offset: 2px;
}
```

### prefers-reduced-motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## 18. アニメーションイージングルール

GSAPアニメーションでは**3種類以上のイージング**を使用すること。単調な `ease: 'power2.out'` の繰り返しは禁止。

| GSAP ease | CSS相当 | 用途 |
|-----------|---------|------|
| `power2.out` | decelerate | タイトル入場 |
| `back.out(1.7)` | spring | カード・リスト入場 |
| `power1.inOut` | smooth | フェード・補足要素 |
| `elastic.out(1, 0.3)` | bounce | 数値ハイライト |
| `power3.inOut` | dramatic | スライド遷移 |

---

## 19. 完成チェックリスト

### テーマ・レイアウト基本

- [ ] カラーは意味に沿っているか
- [ ] フォントサイズはCSS変数を使用しているか
- [ ] **フォントサイズは最小1.4rem（--fs-small）を維持しているか**
- [ ] アニメーション速度は適切か（高速・スムーズ）
- [ ] leaveアニメーションはenterより短いか
- [ ] 進捗バー・ナビゲーション（ドット・矢印）は表示されているか
- [ ] ページ番号表示は実装されているか
- [ ] ナビゲーション用のCSS変数（--nav-arrow-padding等）を使用しているか
- [ ] 量産時のカスタマイズポイントが明確になっているか
- [ ] **ライトテーマがデフォルトになっているか**
- [ ] **印刷用CSSが適用されているか（A4横向き）**
- [ ] **UI要素（アジェンダ・ナビ・ページネーション）がライトテーマに対応しているか**

### デザイン品質（v5.1.0追加）

- [ ] **ビビッドアクセント（--accent-*-vivid）が各スライドに1つ以上使用されているか**
- [ ] **シャドウ変数（--shadow-*）が適切なレベルで使用されているか**
- [ ] **イージングが3種類以上使われているか（power2.out, back.out, power1.inOut等）**
- [ ] **prefers-reduced-motionが定義されているか**
- [ ] **focus-visibleがボタン・リンクに適用されているか**
- [ ] **UIテキスト要素のopacityが0.6以上か**
