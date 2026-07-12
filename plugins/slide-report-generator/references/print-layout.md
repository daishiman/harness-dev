# 印刷用レイアウト仕様

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは印刷 CSS の実装テンプレート集。規則の正本は SR-ID で参照すること

**規則の正本**: §7 印刷（[SR-7-01](spec-registry.md#sr-7-01)〜[SR-7-10](spec-registry.md#sr-7-10)）。特に物理サイズ → [SR-7-02](spec-registry.md#sr-7-02)、GSAP リセット → [SR-7-04](spec-registry.md#sr-7-04)、ナビ非表示 → [SR-7-05](spec-registry.md#sr-7-05)、色再現 → [SR-7-06](spec-registry.md#sr-7-06)。

> **印刷ビューポート契約の一本化（DRY）**: 印刷の物理サイズ契約は**デッキ種別で2系統**ある。本ファイルは **(1) 通常 HTML デッキ＝full-bleed**（A4横 297mm/210mm・コンテンツ実体を 1 ページ 1 スライドで敷く）の実装テンプレート集を正本とする。**(2) 全面 AI 画像デッキ＝16:9 letterbox**（297mm→高さ167mm・上下 off-white 余白・主キャンバスを `object-fit:contain`）の契約は [full-image-deck-method.md §0.3](full-image-deck-method.md) を**唯一の正本**とし、本ファイルでは再定義しない（§全面画像デッキ印刷で参照のみ）。実装 CSS の正本は `assets/print-styles.css`、画面側 CSS・主キャンバス実体マークアップの正本は `assets/slide-template-single.html`。

> **既知の矛盾（SR-7-09）**: 本ファイルは `@media print` 内でフォントサイズ縮小を多用するレガシー互換実装を含む。SSoT としては「印刷=画面の同一比率」（[SR-7-08](spec-registry.md#sr-7-08)）が将来形。新規スライドは vw + `--font-scale` 統一を目指し、レガシー互換が必要な場合のみ本ファイルの縮小ルールを使用する。

## 概要

プレゼンテーションスライドを配布資料用PDFとして出力するための印刷レイアウト仕様。
**16:9アスペクト比を維持したA4横向き**（281mm × 158mm）方式を採用し、1ページ1スライドで印刷する。

### 重要: A4印刷前提の設計

スライド作成時から**A4横向き印刷を想定**したレイアウト設計を行うこと：
- 文字サイズ: 印刷時の可読性を考慮（最小14pt相当）
- 余白: コンテンツは中央80%以内に収める
- 図解: 印刷サイズでも視認可能なサイズ

---

## レイアウト構成

### ページレイアウト

```
┌─────────────────────────────────────────────────────────────┐
│                    A4 横向き (297mm × 210mm)                 │
├─────────────────────────────────────────────────────────────┤
│  padding: 15mm 20mm                                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │              スライドコンテンツ                       │    │
│  │                                                     │    │
│  │   ・ダーク背景維持 (var(--bg-dark))                   │    │
│  │   ・テキスト色維持 (Kanagawaテーマ)                   │    │
│  │   ・フォントサイズ縮小で1ページに収める               │    │
│  │   ・overflow: hidden で内容切り取り                  │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 寸法

| 項目 | 値 |
|------|-----|
| ページサイズ | A4横 (297mm × 210mm) |
| マージン | 0 (余白なし) |
| スライド領域 | 297mm × 210mm（固定） |
| パディング | 15mm (上下) / 20mm (左右) |
| overflow | hidden（はみ出しを切り取り） |

### 固定サイズ方式（推奨）

**従来の問題**:
- `transform: scale()` + `overflow: hidden` → コンテンツがクリッピングされて消失
- ライトモード変換 → デザインの一貫性が失われる
- height: auto → コンテンツ量で複数ページにまたがる

**解決策**: 固定サイズ + overflow: hidden + フォントサイズ縮小

```
従来方式（問題あり）:
┌────────────────────────────────┐
│  transform: scale(0.65)        │  ← overflow: hidden でクリッピング
│  height: auto                  │  ← 複数ページにまたがる
│  background: white             │  ← デザインの一貫性喪失
└────────────────────────────────┘

固定サイズ方式（推奨）:
┌────────────────────────────────┐
│  width: 297mm (固定)           │  ← A4横の幅
│  height: 210mm (固定)          │  ← A4横の高さ
│  min-height/max-height: 210mm  │  ← 高さを強制固定
│  overflow: hidden              │  ← はみ出しを切り取り
│  background: var(--bg-dark)    │  ← ダークモード維持
│  font-size: 縮小               │  ← 1ページに収める
└────────────────────────────────┘
```

---

## 印刷用CSS

### 基本設定

```css
@media print {
  /* ページ設定: A4横向き、余白なし */
  @page {
    size: A4 landscape;
    margin: 0;
  }

  /* 色の正確な再現＋カード影の全要素強制オフ（SR-09） */
  * {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
    color-adjust: exact !important;
    box-shadow: none !important;
  }

  html {
    height: auto;
    overflow: visible;
  }

  body {
    height: auto;
    overflow: visible;
    background: var(--bg-dark) !important;
    margin: 0;
    padding: 0;
  }

  /* ナビゲーション要素を非表示 */
  .progress-bar,
  .navigation,
  .slide-counter,
  .dot-pagination,
  .agenda-indicator {
    display: none !important;
  }
}
```

### スライダーコンテナ

```css
@media print {
  .slider {
    width: auto;
    height: auto;
    display: block;
    background: transparent;
  }

  .slide-area {
    width: auto;
    height: auto;
    max-width: none;
    max-height: none;
    overflow: visible;
    background: transparent;
  }

  .slider__container {
    position: static;
    width: auto;
    height: auto;
    display: block;
  }
}
```

### スライドアイテム（固定サイズ）

**重要**: `width`, `height`, `min-height`, `max-height` を全て固定値に設定することで、1ページ1スライドを強制する。

```css
@media print {
  .slider__item {
    position: relative !important;
    display: flex !important;
    opacity: 1 !important;
    visibility: visible !important;
    width: 297mm;              /* A4横の幅 */
    height: 210mm;             /* A4横の高さ */
    min-height: 210mm;         /* 最小高さ固定 */
    max-height: 210mm;         /* 最大高さ固定 */
    overflow: hidden;          /* はみ出しを切り取り */
    page-break-after: always;  /* 各スライド後に改ページ */
    page-break-inside: avoid;
    break-after: page;
    break-inside: avoid;
    background: var(--bg-dark) !important;
    color: var(--fg-default);
    padding: 15mm 20mm;        /* 内部余白 */
    box-sizing: border-box;
    margin: 0;
  }

  /* 最後のスライドはページブレークなし */
  .slider__item:last-of-type:not([data-hidden="true"]) {
    page-break-after: auto;
    break-after: auto;
  }
}
```

### 非表示スライドの処理

`data-hidden="true"` 属性を持つスライドは印刷から除外する。

```css
@media print {
  .slider__item[data-hidden="true"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    overflow: hidden !important;
    page-break-after: avoid !important;
    break-after: avoid !important;
  }
}
```

### コンテンツエリア

```css
@media print {
  .slider__content {
    width: 100%;
    height: 100%;
    max-width: 100%;
    padding: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    overflow: hidden;
  }
}
```

### フォントサイズ縮小（印刷用・レガシー互換のみ）

> **将来形は vw + `--font-scale` 統一（[SR-7-08](spec-registry.md#sr-7-08)）**。実装の正本 `assets/print-styles.css` は vw 統一で `@media print` 内のフォントサイズ上書きを**削除済み**（画面値がそのまま印刷値になり差分ゼロ）。本セクションは固定 rem の旧テンプレートを使うレガシー互換が必要な場合のみ参照する代表例である（全要素の網羅リストは再掲しない・DRY）。

```css
@media print {
  /* レガシー互換例: 1ページに収める固定 rem 縮小。
     新規スライドは使わず vw 統一（assets/print-styles.css）に従う。 */
  .slide-title .title-main {
    font-size: 3rem;
    background: none !important;
    -webkit-text-fill-color: var(--wave-blue) !important;
    color: var(--wave-blue) !important;
  }
  .slide-title .title-sub { font-size: 1.5rem; }
  .slide-section .section-title { font-size: 2.5rem; }
  .slide-stats .stat-value {
    font-size: 2rem;
    background: none !important;
    -webkit-text-fill-color: var(--wave-blue) !important;
    color: var(--wave-blue) !important;
  }
  .slide-message .message-main { font-size: 2rem; }
  /* カード/グリッド/テーブル/フロー等の gap・padding 縮小も同方針。
     完全な要素別リストは旧版実装に準ずるが、新規では vw 統一を優先する。 */
}
```

### GSAPインラインスタイルリセット（必須）

GSAPアニメーションは要素に `style="opacity: 0; transform: ..."` 等のインラインスタイルを残す。印刷時にこれらが残っているとスライドコンテンツが非表示になるため、`!important` で強制リセットする。

```css
@media print {
  /* GSAPが残すインラインスタイルを強制リセット */
  .slider__content {
    visibility: visible !important;
    opacity: 1 !important;
    max-width: 100% !important;
    width: 100% !important;
  }

  .slider__content > * {
    opacity: 1 !important;
    transform: none !important;
    visibility: visible !important;
  }

  /* 全ネスト要素のGSAPスタイルもリセット */
  .slider__content * {
    opacity: 1 !important;
    transform: none !important;
    visibility: visible !important;
  }

  /* カード・ボックス系の box-shadow を除去（印刷コスト削減） */
  .ig-item, .list-item, .flow-card, .icon-wrapper,
  .compare-item, .flow-step, .stat-card, .grid-card {
    box-shadow: none !important;
  }

  /* 全アニメーション・トランジションを無効化 */
  * {
    transition: none !important;
    animation: none !important;
  }
}
```

### インタラクティブ要素の無効化

```css
@media print {
  /* ホバー効果を無効化 */
  .list-item:hover,
  .stat-item:hover,
  .grid-card:hover,
  .compare-panel:hover,
  .agenda-item:hover,
  .icon-grid-item:hover {
    transform: none !important;
    box-shadow: none !important;
  }

  /* ツールチップ非表示 */
  .has-tooltip::after {
    display: none !important;
  }
}
```

---

## 完全な印刷CSS（コピー用）

通常 HTML デッキ（full-bleed）の完全な `@media print` ブロックは、上記「印刷用CSS」各セクション（基本設定 → スライダーコンテナ → スライドアイテム → 非表示スライド → コンテンツエリア → フォントサイズ縮小 → GSAP リセット → インタラクティブ無効化）の連結である。**コピー用の完全 CSS を二重掲載すると本ファイルと実装が乖離するため再掲しない（DRY）**。コピーして使う実体 CSS の正本は次のとおり。

| 用途 | 正本ファイル |
|------|-------------|
| 通常 HTML デッキ印刷 CSS（full-bleed・vw 統一版） | `assets/print-styles.css` |
| 画面 CSS・主キャンバス実体マークアップ | `assets/slide-template-single.html` |
| 決定論レンダラ出力の印刷 CSS | `scripts/style-builder.cjs` |

新規スライドは `assets/print-styles.css` を起点にし、本ファイルの各セクションは「なぜその指定が要るか」の根拠説明として参照する。

---

## 全面画像デッキの印刷（16:9 letterbox・参照のみ）

全面 AI 画像デッキ（`data-deck-mode="full-image"`）は、本ファイルの full-bleed（210mm 系）ではなく **16:9 letterbox（297mm→高さ167mm・上下 off-white 余白・主キャンバスを `object-fit:contain`）** で印刷する。この契約の正本は [full-image-deck-method.md §0.3](full-image-deck-method.md)（HTML表示サイズと生成画像サイズの契約）であり、本ファイルでは再定義しない。

要点（正本の要約・詳細は §0.3 参照）:

- 主キャンバスは規定クラス `.ai-slide-canvas`（後方互換エイリアス `.slide-fullbg` / `.slide-bg` / `[data-role="main-canvas"]`）を `:where()` で同一 `object-fit:contain` 契約に束ねる。
- 印刷は `@media print` で `object-fit: contain !important` を強制し `cover` を禁止（`scripts/validate-print.js` が `@media print` 内 `cover` を CRITICAL 検出）。
- `data-deck-mode="full-image"` 限定適用で、通常デッキの full-bleed（本ファイル）ルールには干渉しない（後方互換）。
- 実装 CSS の正本は `assets/print-styles.css`（全面画像デッキ印刷契約ブロック）と `assets/slide-template-single.html`（画面側）。
- 検証は `node scripts/validate-print.js <index.html>`（P06 を 167mm letterbox 許容に拡張）＋ `node scripts/evaluate-deck.js <slide-dir>`（full-image-deck 検出時に validate-print / validate-ai-image-assets を spawn し FAIL 連動）。

---

## 使用手順

### ブラウザでの印刷

1. HTMLファイルをブラウザで開く
2. `Ctrl+P` (Windows) / `Cmd+P` (Mac) で印刷ダイアログを開く
3. 印刷設定:
   - 送信先: 「PDFに保存」
   - レイアウト: 「横」
   - 余白: 「なし」
   - 背景のグラフィック: **有効にする**（重要）
4. 「保存」をクリック

### Chrome推奨設定

| 設定項目 | 値 |
|---------|-----|
| 送信先 | PDFに保存 |
| ページ | すべて |
| レイアウト | 横 |
| 用紙サイズ | A4 |
| ページあたりのページ数 | 1 |
| 余白 | なし |
| 倍率 | デフォルト（100%） |
| 背景のグラフィック | 有効 |

---

## トラブルシューティング

| 問題 | 原因 | 解決策 |
|------|------|--------|
| 1枚目しか印刷されない | `position: absolute` が残っている | `.slider__item` に `position: relative !important` を設定 |
| コンテンツがページをまたぐ | `height: auto` になっている | `height: 210mm`, `min-height: 210mm`, `max-height: 210mm` を全て設定 |
| 背景色が印刷されない | 背景グラフィック無効 | 印刷設定で「背景のグラフィック」を有効化 |
| 非表示スライドが印刷される | `[data-hidden="true"]` 未対応 | 非表示スライド用のCSS追加 |
| 改ページ位置がずれる | `break-after` 未設定 | `page-break-after: always` と `break-after: page` を両方設定 |
| グラデーション文字が消える | 印刷時にグラデーション未対応 | `background: none`, `-webkit-text-fill-color` で単色に変換 |
| ホバー効果が残る | CSSで無効化されていない | `:hover` セレクタに `transform: none !important` 追加 |

---

## 設計原則

### 固定サイズ方式を採用する理由

1. **1ページ1スライドの保証**: `height`, `min-height`, `max-height` を全て固定値にすることで、コンテンツ量に関わらず1ページに収まる
2. **デザインの一貫性**: ダークモードを維持することで、画面表示と印刷結果が一致
3. **予測可能な結果**: 固定サイズにより、印刷結果が常に同じレイアウトになる
4. **シンプルなデバッグ**: 問題発生時、サイズが固定されているため原因特定が容易

### 避けるべきパターン

```css
/* NG: コンテンツがページをまたぐ */
.slider__item {
  height: auto !important;      /* ← 可変高さはNG */
  min-height: 170mm !important; /* ← 最小値のみでは不十分 */
}

/* NG: ライトモード変換（デザインの一貫性喪失） */
.slider__item {
  background: white !important; /* ← ダークモードのデザインが崩れる */
}

/* OK: 固定サイズ方式 */
.slider__item {
  width: 297mm;
  height: 210mm;
  min-height: 210mm;
  max-height: 210mm;
  overflow: hidden;
  background: var(--bg-dark) !important;
}
```

---

---

## 必須事項チェックリスト（SR-08 / SR-09 反映 — 2026-05-09 追加）

新規スライド生成時、`@media print` ブロックに以下が**必ず**含まれていることを検証する。
欠落していれば配布資料の品質が著しく低下するため、テンプレート側で抜け漏れを防ぐ。

### 必須 1: print-color-adjust 強制（SR-7-06）

```css
@media print {
  * {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
    color-adjust: exact !important;
  }
}
```

- **理由**: ブラウザは印刷時に背景色・アクセント色をデフォルトで除去する。`exact !important` を全要素に適用しないと Kanagawa パレットが消失し、配布資料が白黒に近くなる。
- **必須化レベル**: 全スライド・全テンプレートで必須。`assets/print-styles.css` および `style-builder.cjs` 出力 CSS の両方に組み込むこと。
- **検証**: `scripts/validate-print.js` で `print-color-adjust:\s*exact` の存在を確認する。

### 必須 2: 印刷時 box-shadow 除去（SR-7-10 / 全要素強制）

```css
@media print {
  /* 全要素で box-shadow を強制オフ（新クラス追記漏れを構造的に防止） */
  * {
    box-shadow: none !important;
  }
}
```

- **理由**: box-shadow は印刷時に**インクコスト増大**＋**にじみ**を生む。さらに Chrome 印刷では `print-color-adjust: exact` と組み合わさると、影がカード周囲の**薄いグレーの色塗り（塗りつぶし）**として出てしまう。スクリーンでは奥行き表現として有効でも、紙では視認性を下げる。
- **必須化レベル**: 個別クラスを列挙する運用は廃止。`@media print` 内で `* { box-shadow: none !important; }` の**全要素一括強制**を必須とする。これによりカード・ボックス系クラスを新設しても追記不要・追記漏れゼロを構造的に担保する。`assets/print-styles.css` / `assets/slide-template-single.html` / `scripts/style-builder.cjs` の各 `@media print` 先頭に組み込み済み。
- **検証**: 新規 CSS ファイル生成時、`@media print` 内に `* { box-shadow: none !important; }` が存在することを必須。

### 必須 3: グラデ文字(background-clip:text)を印刷で通常色に戻す

```css
@media print {
  /* グラデ文字は印刷で塗りつぶし矩形になり読めなくなるため通常色に戻す */
  .gradient-text,
  [style*="-webkit-background-clip: text"], [style*="background-clip: text"] {
    background: none !important;
    -webkit-background-clip: border-box !important; background-clip: border-box !important;
    -webkit-text-fill-color: var(--accent-primary, #1F6FEB) !important; color: var(--accent-primary, #1F6FEB) !important;
  }
}
```

- **理由**: タイトル等で `background: <gradient>; -webkit-background-clip: text; -webkit-text-fill-color: transparent;` を使い、グラデを文字型に切り抜いて表示している場合、印刷では `background-clip: text` が効かず、背景グラデが矩形で塗られ＋`text-fill-color: transparent` で文字が透明になり、「青紫の塗りつぶし矩形」となって文字が読めなくなる。`@media print` で `background-clip` を `border-box` に戻し `-webkit-text-fill-color` / `color` を単色に戻すことで可読化する。
- **必須化レベル**: 全 `@media print` ブロックで必須。インライン `style` 属性で切り抜いた要素も `[style*="background-clip: text"]` 属性セレクタで捕捉する（クラス追記漏れを構造的に防止）。`stat-value` のような既存のクラス別グラデ→単色変換は温存する（別セレクタ・上書きしない）。`assets/print-styles.css` / `assets/slide-template-single.html` / `assets/src/styles/print.css` / `scripts/style-builder.cjs` の各 `@media print` 先頭に組み込み済み。
- **検証**: `@media print` 内に `background-clip: border-box` を含むグラデ復元ルールが存在することを確認する。

### 必須 4 (推奨): GSAP インラインスタイルリセット（SR-7-04）

`@media print` 内で `.slider__content *` に対し `opacity: 1 !important; transform: none !important; visibility: visible !important;` を必ず指定する。本ファイル「GSAPインラインスタイルリセット（必須）」セクションを参照。

---

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 3.4.0 | 2026-06-28 | 印刷時のグラデ文字を通常色へ戻す対策を追加（塗りつぶし矩形で読めなくなる現象の恒久対策） |
| 3.3.0 | 2026-06-28 | box-shadow:none を `* {}` 全要素強制に変更（新クラス追記漏れ防止）。`@media print` 内の影除去を個別クラス列挙から `* { box-shadow: none !important; }` の一括強制へ統一。Chrome 印刷＋`print-color-adjust: exact` で影がカード周囲のグレー塗りつぶしになる現象の恒久対策。実体 CSS（`print-styles.css` / `slide-template-single.html` / `style-builder.cjs`）と必須事項チェックリスト（必須2）を更新 |
| 3.2.0 | 2026-06-24 | 印刷ビューポート契約の一本化＋行数削減（elegant-review・D1/D10）。冒頭に「印刷=full-bleed（通常デッキ・本ファイル正本）／16:9 letterbox（全面画像デッキ・`full-image-deck-method.md §0.3` が正本）」の2系統を明記。「完全な印刷CSS（コピー用）」の全文再掲（前段セクションの完全重複・約290行）を削除し、実体 CSS の正本（`assets/print-styles.css` / `assets/slide-template-single.html` / `scripts/style-builder.cjs`）への参照表に置換（DRY）。「全面画像デッキの印刷（16:9 letterbox）」参照セクションを追加（`.ai-slide-canvas`＋エイリアス・contain強制・cover禁止・letterbox 167mm・検証ゲート接続は §0.3 を正本に参照のみ）。861行→約530行へ削減 |
| 3.1.0 | 2026-05-09 | SR-08 / SR-09 反映: 必須事項チェックリスト追加（print-color-adjust: exact 強制、box-shadow: none 強制）。新クラスにも box-shadow: none を追記する運用を明文化 |
| 3.0.0 | 2026-01-12 | 固定サイズ方式に全面変更：A4横(297mm×210mm)固定、ダークモード維持、overflow:hidden採用、非表示スライド対応 |
| 2.1.0 | 2026-01-04 | Flexbox/Grid維持方式に変更：`.slider__item`をflex表示に、コンテナごとの明示的display設定、全子要素のvisibility保証追加 |
| 2.0.0 | 2026-01-04 | シンプル方式に全面変更（transform: scale廃止、overflow: visible採用）、メモ欄削除 |
| 1.1.0 | 2026-01-03 | 比率維持スケーリング方式に変更（65%→70%/35%→30%）、レイアウト崩れ防止 |
| 1.0.0 | 2026-01-03 | 初版作成 |
