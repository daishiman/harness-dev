# テーマ・スタイルガイドライン

<!-- css-route: hand-slide -->
<!-- この文書は手書き経路の :root の実体を兼ねるので、自身も手書き経路として
     照合される (lint-contract-drift.py check G)。ここで未定義の変数を引いていれば、
     それは成果物の styles.css でも解決できないということ -->

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

色はここでカスタマイズしない。面の色は 3 色しかなく、そのうち 1 つを差し替えると
配色ではなく意匠が変わる。値は §4 の生成区間が持ち、変えるときは
`vendor/scripts/style-builder.cjs` の `SPEC.colors` を変えて再生成する。

### カスタマイズ例

```css
/* プロジェクトごとの設定を上書き */
:root {
  /* フォントを小さくする場合 */
  --font-scale: 1.1;

  /* ナビゲーション余白をタイトに */
  --nav-arrow-padding: 2rem;
  --nav-bottom-padding: 1.5rem;
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

## 2. カラーパレット

> **配色の正本は `vendor/scripts/style-builder.cjs` の `SPEC.colors`**。
> この文書は手書き経路の実装そのもの（LLM がここの `:root` を読んで成果物の
> `styles.css` へ書き出す）なので、色の実値は §4 の生成区間だけが持ち、
> そこは `python3 scripts/build-slide-skeleton-css.py` が正本から機械的に作る。
> この節の表は名前と用途だけを持ち、値は持たない。
> 値を変えるときは正本を変えて再生成し、`--check` で一致を確認する。

### 出荷されるパレットは 1 種類

以前この節は「Lotus White / ライト / ダーク の 3 テーマを提供」と書いていたが、
**テーマを切り替える機構は存在しない**。`buildRootVars()` が `SPEC.colors` を
そのまま `:root` へ流すだけで、切替の入力も分岐もない。3 つの `:root` ブロックが
どれも「デフォルト」と名乗り、しかもどれも実際の出力と違う値だったため、
読んだ側が誤った配色を正解として複製していた。ここでは実際に出る 1 種類だけを載せる。

| 変数名 | 用途 |
|--------|------|
| `--bg-dark` | 面の地 |
| `--fg` | テキスト（メイン） |
| `--fg-dim` | テキスト（サブ）・注記 |
| `--bg-dim` | 沈めた地 |
| `--bg-card` | カードの地 |
| `--sumi-ink` | 面の地の最下段。**名前はパレットのスロット名であり、暗いという意味ではない**（実値は §4 の生成区間が持つ） |

実値はこの表に書かない。書けば正本と写しの 2 か所になり、必ず片方が取り残される。
値は §4 の生成区間だけが持ち、そこは `SPEC.colors` から機械的に作られる。

アクセントは専用の色変数ではなく反転面（地色と文字色の入れ替え）で作る（[SR-2-04](spec-registry.md#sr-2-04)）。

### 色相名の 4 変数は一時定義であり、新しい面では使わない

`--sakura-pink` / `--wave-blue` / `--wave-aqua` / `--autumn-yellow` は
§4 の生成区間が一時的に定義している。値は `vendor/scripts/svg-kit.cjs` が
実際に出している fallback から生成していて、書き写していない。定義を入れる
前は、参照の多くがフォールバック無しで、未定義参照は宣言ごと無効になるため
その色指定は落ちていた。旧パレットの hex をフォールバックに持つ参照もあった。

一時定義なので、新しい面では使わない。理由はこれらが**名前の数だけの区別を
運んでいない**こと。紙の上で塗りとして見分けられるのは 3 値しかない。

| 名前 | 出る値 | 塗りとして |
|------|--------|-----------|
| `--sakura-pink` | インク | 成立 |
| `--wave-blue` | `--tone-3` | 成立 |
| `--wave-aqua` | `--tone-2` | 成立 |
| `--autumn-yellow` | `--tone-1` | 紙とコントラスト比 1.16・区別なし |

`--autumn-yellow` の区別は既に失われた状態で出荷されている。色を足して直すの
ではなく、区別を **(濃度 × 形) の系列**へ移す。1 名を 1 つの色値ではなく
`(fill, stroke, dash)` の組へ写す形で、印刷と白黒複写でも区別が残る。

当初この節は 6 名を扱っていた。`--spring-violet` は `--wave-blue` と、
`--fuji-gray` は `--fg-dim` と**同じ値を指す別名**で、名前が 2 つあること自体が
「区別がある」という誤った主張になっていたため、参照側を寄せたうえで名前ごと
落とした。**同値の別名を消したのであって、区別を 1 つ減らしたのではない。**

参照側が系列 API を呼ぶようになった時点でこの 4 名も消える。消し忘れは
`tests/test_legacy_hue_aliases.py` が落として知らせる。

### 暗色が要るとき

暗い面はテーマではなく用途で入る。コードブロック（`#1F1F28` / `#DCD7BA`、§10）と
`data-bg="dark"` のスライドだけが暗色で、これは配色の切替ではなく個別の指定。

---

## 3. カラー使用ガイド

### 意味に応じた色選択

意味は色相ではなく濃度と反転で作る。使えるのは生成区間が定義している変数だけ。

| 意味 | 手段 | CSS変数 |
|------|------|---------|
| 重要・メイン | 本文と同じインク＋太さ | `--fg` |
| 最重要（面に 1 つ） | 反転面（地と字を入れ替える） | 地 `--fg` / 字 `--bg-dark` |
| 補足・サブ | 濃度を落とす | `--fg-dim` |
| 区切り・囲い | 罫 1 本 | `--hairline` |
| 図版の段 | 淡→濃の 3 段 | `--tone-1` / `--tone-2` / `--tone-3` |

### 比較スライドの色

Before / After は色相で塗り分けない。**位置（左右）とラベルが既に区別を担っている**ので、
色を足すと同じ情報を二重に持つことになる。差を見せたい側だけを反転面にする。

```css
/* Before側（左）: 地は紙のまま、罫だけ */
.compare-item.left {
  border-top: 1px solid var(--hairline);
}

/* After側（右）: 面に 1 つだけの反転で「こちらへ動く」を示す */
.compare-item.right {
  background: var(--fg);
  color: var(--bg-dark);
}
```

---

## 4. CSS変数定義（完全版）

### 全変数リスト

色は下の生成区間が唯一の定義場所で、この節の残りは幾何と書体だけを持つ。

<!-- BEGIN GENERATED: palette (scripts/build-slide-skeleton-css.py) -->
```css
/* 生成物。手で編集しない。編集しても再生成で消える。
 * 値の正本: vendor/scripts/style-builder.cjs の SPEC.colors
 * 再生成:   python3 scripts/build-slide-skeleton-css.py
 * 検証:     python3 scripts/build-slide-skeleton-css.py --check
 *
 * 手書き経路はこのブロックを成果物の styles.css へそのまま貼る。
 * 外部 CSS への link にはしない (出荷 deck の styles.css は index.html へ
 * インライン展開された写しで、外部 CSS はブラウザに読まれていない)。
 */
:root {
  /* ---- パレット (色数 3: 紙・インク・反転面) ---- */
  --paper: #F7F6F3;  /* 紙 */
  --ink: #141412;  /* インク */
  --fg-muted: #6A6A68;  /* 注記 (インク 62%) */
  --hairline: #D5D4D1;  /* 罫 (インク 15%) */
  --tone-1: #E1E6EA;  /* 図版の淡い段 */
  --tone-2: #9BADBF;  /* 図版の中間段 */
  --tone-3: #4B6681;  /* 図版の濃い段 */

  /* ---- 手書き経路の名前。値はパレットを指すだけで実体を持たない ---- */
  --bg-dark: var(--paper);  /* 面の地 */
  --fg: var(--ink);  /* 本文 */
  --fg-dim: var(--fg-muted);  /* 注記・補助 */
  --bg-dim: var(--paper);  /* 沈めた地。面の色数は 3 なので地は紙のまま */
  --bg-card: var(--paper);  /* カードの地。囲いは罫だけで作るので地は紙のまま */
  --sumi-ink: var(--paper);  /* 面の地の最下段。名前は本家パレットのスロット名で、暗いという意味ではない */

  /* ---- 色相名 (一時定義)。値の出所は vendor/scripts/svg-kit.cjs の fallback ----
   * 定義が無いせいで 265 箇所が宣言ごと無効になっていたので、今出ているのと
   * 同じ値で名前だけを与える。見た目は 1 ドットも変わらない。
   * 色相を戻したのではない。区別は色でなく (濃度 x 形) の系列へ移す設計で、
   * 参照側が seriesStyle() を呼ぶようになった時点でこの節ごと消える。
   * 消し忘れは tests/test_legacy_hue_aliases.py が落として知らせる。
   */
  --sakura-pink: var(--ink);  /* #141412 */
  --wave-blue: var(--tone-3);  /* #4B6681 */
  --wave-aqua: var(--tone-2);  /* #9BADBF */
  --autumn-yellow: var(--tone-1);  /* #E1E6EA */
}
```
<!-- END GENERATED: palette -->

### 色以外の変数

```css
:root {
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
     使うのは 3 段のみ（SR-3-10）。--fw-light / --fw-semibold は
     CSS トークン実体の差し替えが済むまで残る過渡的定義
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
  background: var(--bg-dim, #f0f0f2);
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
.icon-wrapper.accent-violet i { color: var(--wave-blue); }
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
  background: var(--hairline);
  z-index: 100;
}

.progress {
  height: 100%;
  background: var(--fg);
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

/* 5個区切りマイルストーン: 5番目ごとに大きさと間隔で区切る。
   色を足さずに形で区別するので、面の色数 3 を消費しない。 */
.pagination .dot:nth-child(5n) {
  background: var(--fg);
  opacity: 0.5;
  width: 0.7rem;
  height: 0.7rem;
  margin-right: 0.5rem;
}

.pagination .dot:nth-child(5n).active {
  background: var(--fg);
  opacity: 1;
  transform: scale(1.3);
}
```

**設計意図**:
- セクションの構造はセクションナビ（常時表示）で把握できる
- ページネーションは「全体の中のどこか」を示す位置インジケーター
- 5個区切りで数えやすく、25枚超のスライドでも現在位置が明確

### 9.3 代替方式: セクション別の区切り（オプション）

セクションナビがない場合や、ドットでもセクション構造を示したい場合に使用。
セクションごとに色を割り当てない。5 セクションには色相が 5 本要るが、
区別の付く濃度段がそれだけ無いので、隣り合うセクションが同じ色に見える。
区切りは間隔で示す。

```css
/* セクションの先頭ドットの前だけ間隔を空ける。色は増やさない */
.pagination .dot[data-section-start="true"] { margin-left: 1.2rem; }
```

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

## 16. 階層の作り方

ぼかしも影も意匠手段として使わない（SR-2-09）。階層は 1px の下罫と反転面で作る。

```css
/* 面の中の区切り: 囲わず、下罫 1 本だけ引く */
.section-divider {
  border-bottom: 1px solid var(--hairline);
}

/* 手前に出したい塊: 面に 1 つだけ反転させる */
.section-emphasis {
  background: var(--fg);
  color: var(--bg-dark);
}
```

---

## 17. アクセシビリティスタイル

### focus-visible

```css
:focus-visible {
  outline: 3px solid var(--fg);
  outline-offset: 2px;
  border-radius: 4px;
}

button:focus-visible,
a:focus-visible {
  outline: 3px solid var(--fg);
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

- [ ] **各面の強調が反転面 1 個で作られ、色を足していないか（SR-2-04 / SR-2-05）**
- [ ] **影・グロウを使わず罫で階層を作り、角丸が 0px か（SR-2-09）**
- [ ] **イージングが3種類以上使われているか（power2.out, back.out, power1.inOut等）**
- [ ] **prefers-reduced-motionが定義されているか**
- [ ] **focus-visibleがボタン・リンクに適用されているか**
- [ ] **UIテキスト要素のopacityが0.6以上か**
