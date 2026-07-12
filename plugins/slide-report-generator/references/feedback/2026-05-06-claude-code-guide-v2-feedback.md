# 2026-05-06 Claude Code 概念ガイド v2 — UI/UX フィードバックと反映

## 案件
`05_Project/スライド/slide-2026-05-06-claude-code-guide-v2/` の図解スライド全47枚に
ついて、目視レビューでスキル側の致命的バグと図解品質の問題が発見された。

## 発見された問題と反映先

### 1. verify-slides.js の致命的バグ（最優先）
- **症状**: `captureScreenshots` が `container.style.transform = 'translateX(...)'`
  方式で全スライドを順送りしようとしていたが、現行スライドは
  `.slider__item { position: absolute; opacity: 0; visibility: hidden; }` 上で
  `.is-active` クラスで切り替える方式（GSAP 駆動）。translateX は無視され、
  毎回1枚目の slide_01 だけが映り、他は空白で保存される。03 フェーズで PASS と
  なっていた検証は事実上機能しておらず虚偽だった。
- **反映先**: `scripts/verify-slides.js` の captureScreenshots 内 Python ブロック
- **適用内容（v7.5.0）**: `.is-active` を1枚ずつ付け替え、`page.screenshot({ clip })`
  で実際に可視化されたスライドエリアのみを撮影する実装に置換。
  `transform / visibility` 操作は完全削除。

### 2. diagram-mindmap の文字切れ・重なり
- **症状**: `buildMindmap` は SIZE=540 正方形ビューで外円ノード半径 r=40 を
  使用、ラベルをノード円内部に置いていたため、日本語の長い枝
  （「プラグイン配布」「スラッシュコマンド」「サブエージェント」）が
  円外にはみ出す or 切れて読めない。
- **反映先**: `scripts/svg-builder.cjs` `buildMindmap`
- **適用内容（v7.5.0）**: viewBox を 1100x600 に拡大、外円ノード r=38 とし、
  ラベルはノード外側にリーダー線で配置。テキスト anchor は方位ベクトルに
  応じて `start`/`middle`/`end` を切替え、上下位置も微調整。

### 3. diagram-cycle の余白過多 + 補足不足
- **症状**: SIZE=540 正方形でビュー全体の30%程度しか使っておらず、左右が
  真っ白。各ノードに desc があっても表示されない。
- **反映先**: `scripts/svg-builder.cjs` `buildCycle` および
  `scripts/render-slide.cjs` の dispatch
- **適用内容（v7.5.0）**:
  - viewBox を 1200x600 に横長化、サイクルは右側、左側に
    `headline / subtext / description / caption` を表示するキャプションカード
    （白背景＋青の左バー）を追加。
  - render-slide で `c.headline / c.subtext / c.description / c.caption` を
    buildCycle に渡すよう修正。
  - 各ノード半径を rNode=78 に拡大、文字数あたりの maxChars を再計算。

### 4. diagram-vs が比較図でなく単なるフロー6箱になっていた
- **症状**: render-slide の dispatch が `buildHorizontalFlow(both)` を呼んでおり、
  Before/After の概念が消えて 6 個の箱が並ぶだけ。SR-4-04 の 48%/4%/48% 構造
  が完全に欠落。
- **反映先**: `scripts/svg-builder.cjs` 新規 `buildVs` を実装、
  `scripts/render-slide.cjs` を `buildVs` 呼び出しに切替
- **適用内容（v7.5.0）**:
  - 1200x620 の 2 カラム比較レイアウト（左 colW=540, 中央gap=60, 右 colW=540）。
  - 左 = sakura-pink（Before/悪い例）、右 = wave-aqua（After/良い例）。
  - 各カラムにヘッダーバー（カラー塗りつぶし + 白バッジ + タイトル白文字）。
  - 項目は白カード + 左 6px の色バー + ×/○ 記号 + 黒文字本文。
  - 中央に紫枠の "VS" バッジ。
  - render-slide は `c.left.label / c.left.title / c.right.label / c.right.title`
    を buildVs に渡し、デフォルトは `Before/After` および `悪い例/良い例`。

### 5. slide-flow の補足不足
- **症状**: `buildHorizontalFlow` は items の `desc` を無視、ステップカードに
  ラベルだけ表示。本文ゼロでスカスカ。
- **反映先**: `scripts/svg-builder.cjs` `buildHorizontalFlow`
- **適用内容（v7.5.0）**: viewBox を 1080x540 に拡大。各カード左上に番号バッジ
  （白丸 + 色文字）を追加。カード下に desc キャプションを最大 3 行で描画。

### 6. slide-list / slide-grid の視覚階層不足
- **症状**: アイコン色が単調、見出しと補足のサイズ差が小さく、強弱が不明瞭。
- **反映先**: `scripts/style-builder.cjs` の `.slide-list .list-item` および
  `.grid-cell` ブロック
- **適用内容（v7.5.0）**:
  - 各アイテムに `nth-child(5n+x)` で 5 色のビビッドアクセントを
    左ボーダー（list-item は 0.5vw, grid-cell は 0.45vw）で循環。
  - `list-label / grid-cell-title` を fs-subheading + 800 weight。
  - `list-desc / grid-cell-desc` を fs-body + 500 weight + fg-muted。
  - hover で box-shadow を `--shadow-prominent` に強化、translateY で浮上。
  - SVG コンテナに `width: 100%; max-height: 70vh; flex: 1;` を追加して
    画面全体を活用。

## 副次的修正
- structure.json の `slide-010` / `slide-042`（diagram-cycle 2件）に
  `headline` / `subtext` を補強。原稿『10_ClaudeCode概念ガイド.md』の対応
  セクションから要点を抽出。

## CHANGELOG（references/changelog.md / SKILL.md 参照用）
- v7.5.0: verify-slides.js を is-active 方式に書き換え（翻訳されない translateX
  バグ修正）。svg-builder に buildVs を新規追加し、buildMindmap/buildCycle/
  buildHorizontalFlow を改善。style-builder で slide-list/slide-grid に
  色別アクセント＋ホバー＋視覚階層を追加。

## v7.5.1 追加修正（カード暗色背景フィックス / 2026-05-06）

### 7. diagram-vs カード下半分が暗色（黒〜濃グレー）に塗られる
- **症状**: slide 21 / 29 / 33 で Before/After カードの項目下にある余白が
  濃グレーで露出。`fill="var(--card-bg, #f6f5ed)" opacity="0.6"` で描画
  していたが、`--card-bg` がどこにも定義されておらず、`var()` の解決失敗時に
  ブラウザが `currentColor`（親要素から継承された `--fg: #43436c`）に
  フォールバックしたためと推定。
- **反映先**: `scripts/svg-builder.cjs` `buildVs`
- **適用内容（v7.5.1）**:
  - カード背景を `fill="#FFFFFF" stroke="#DCD7BA" stroke-width="1.5"` に
    ハードコード（var() 排除）。
  - カード高さを `H - 90` 固定 → `headerH + 22 + maxItems*itemH +
    (maxItems-1)*itemGap + 28` で動的算出。下半分の空白ゼロ。
  - SVG 全体の H もカード高さに連動して縮小。
  - 中央 VS マークの Y 座標もカード中央に動的配置。
  - 項目カードを `fill="#fff" opacity=0.95` → `fill="#F8F7F0" stroke="#DCD7BA"`
    に変更してコントラスト確保。
  - ラベル text fill も `var(--fg, #43436c)` → `#43436c` ハードコード。

### 8. diagram-cycle 左キャプションカードの下半分が暗色
- **症状**: slide 10 / 42 で左の headline+subtext カードがテキスト領域の
  下半分から濃色に塗られる。`height="${H-120}"` 固定でテキスト行数より
  カードが大きすぎ、`fill="#fff" opacity=0.95` の半透明部が背景と相互作用。
- **反映先**: `scripts/svg-builder.cjs` `buildCycle`
- **適用内容（v7.5.1）**:
  - キャプションカード高さを `cardPadTop + headBlockH + bodyBlockH +
    cardPadBottom` で動的算出。テキスト行数に合わせて短縮。
  - `fill="#fff" opacity=0.95` → `fill="#FFFFFF"`（opacity 削除）。
  - 左の青ボーダー（6px 幅）も同じ動的高さに揃える。

## CHANGELOG 追記
- v7.5.1: buildVs / buildCycle のカード背景 `var(--card-bg)` 変数解決失敗で
  暗色露出する問題を修正。カード高さを内容に合わせて動的算出に変更し、
  下半分の余白を排除。SVG fill を `#FFFFFF` ハードコードに統一。

## v7.5.1 追加修正（slide-* class 名整合）

### 修正サマリ
- **slide-table 罫線/ヘッダ消失**: テンプレが付与する `slide-slide-{type}` と
  style-builder.cjs の `.slide-{type}` セレクタが mismatch。
  `render-slide.cjs:normalizeRenderedSlideHtml` で `slide-slide-*` → `slide-*` に
  正規化する後処理を追加し、全 slide-* スタイルがテンプレ class に到達するよう
  にした。
- **slide-table CSS 強化**: border-collapse separate + border-radius + zebra +
  Kanagawa Lotus 調 (`rgba(255,250,240,0.5)` 背景) を導入。最終行 border 抑制と
  最終列 border-right 抑制で視覚ノイズ削減。
- **直書き `.slide-slide-flow` 修正**: style-builder.cjs L290 付近の slide-flow /
  slide-circle SVG 全画面化セレクタを `.slide-flow` 単体に統一。

### 残課題
- なし（slide_45「用語ミニ索引」の縮小見えは Read tool プレビュー側の問題で、
  実画像 1920×1080 では正常占有を確認）。

### 影響範囲
- スキル全体に効く修正のため、`slide-table` を含む既存全プレゼンが再レンダで
  自動修正される。後方互換: 入力契約 (structure.json schema) 変更なし。
