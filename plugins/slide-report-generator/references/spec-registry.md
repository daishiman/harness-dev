# Spec Registry (SSoT) — presentation-slide-generator

**目的**: 30以上の references / SKILL.md ベストプラクティス表 / agents / assets に散在する制約を**1ファイルに集約**し、LLMが暗記不要で参照可能な Single Source of Truth として機能させる。

**運用原則**:
- 各ルールに **SR-ID（SR-§番号-連番）** を付与。他ファイルからは ID で参照する（例: 「SR-6-02 に従う」）。
- 各ルールは **Why（理由）** と **実装値/コード** を併記する。
- 矛盾するルールは「現状」「将来形」を明示し、どちらを優先するかを SR-ID 単位で確定させる。
- 本ファイルが既存 references と矛盾する場合、**本ファイルが正**。既存 references は段階的に本ファイルへの参照リンク化する。

**索引**:
- §1 寸法・単位 / §2 カラー / §3 フォント / §4 レイアウト / §5 SVG設計 / §6 GSAP
- §7 印刷 / §8 ナビゲーション / §9 アクセシビリティ / §10 コードブロック
- §11 検証ID対応表 / §12 逆引き（agent/script → SR-ID） / §13 逐語コンテンツの非画像化

---

## §1 寸法・単位

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-1-01 | スライドアスペクト比は **16:9 厳守** | `.slider__container { aspect-ratio: 16 / 9; }`、`.slide-area` にも `aspect-ratio: 16/9` を設定 | プロジェクター/PDF/任意ウィンドウサイズで崩れない一貫表示を保証 |
| SR-1-02 | 設計基準解像度は **1920×1080**（半分の 960×540 を SVG viewBox 標準とする） | `viewBox="0 0 960 540"` | 16:9 と整数倍関係を維持、座標計算が容易 |
| SR-1-03 | A4横印刷時の物理サイズは **297mm × 210mm**（固定） | `.slider__item { width: 297mm; height: 210mm; min-height: 210mm; max-height: 210mm; }` | 1ページ1スライドを強制し、コンテンツ量に依存しない |
| SR-1-04 | 単位ホワイトリスト = **mm / rem / vw / vh / %**。**px は原則禁止** | CSS 全般で px 直書き禁止 | デバイス非依存・印刷とのスケール一致 |
| SR-1-05 | px 例外: **SVG 内部の座標・font-size**、および GSAP 計算で必要な数値 | `<text font-size="14">`、`gsap.from(el, { x: -30 })` 等 | SVG 仕様上 rem 解決が不安定なため px 必須。詳細は SR-3-04 / SR-5-04 |
| SR-1-06 | スペーシングスケールは **8px ベース**（rem換算）の 9 段階を使用 | `--space-1: 0.25rem` … `--space-9: 6rem` | 一貫した余白リズム |

---

## §2 カラー（Kanagawa テーマ）

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-2-01 | デフォルトテーマは **Lotus White**（ライトモード） | `--bg-dark: #fafafa; --fg: #43436c;` | 印刷配布・明るい環境で最大の可読性 |
| SR-2-02 | 基本カラー変数は CSS 変数で定義し、**カラーコード直書き禁止** | `var(--wave-blue)` 等を使用 | テーマ切替・量産時の一括変更を可能に |
| SR-2-03 | 主要アクセント変数 6種 | `--wave-blue`, `--spring-violet`, `--sakura-pink`, `--wave-aqua`, `--autumn-yellow`, `--fuji-gray` | Kanagawa Lotus 公式パレット準拠 |
| SR-2-04 | ビビッドアクセント変数 5種を別途定義 | `--accent-blue-vivid: #3B7DD8`, `--accent-pink-vivid: #D94B6E`, `--accent-aqua-vivid: #2EA88F`, `--accent-violet-vivid: #7B4FBA`, `--accent-yellow-vivid: #F5A623` | Lotus 原色だけでは彩度不足。フォーカルポイントに使用 |
| SR-2-04-alt | **Apple トーン代替セット（議論中・SR-07 提案）**: より落ち着いた配色を指定したい場合の代替 | `--accent-blue-apple: #007AFF`, `--accent-pink-apple: #FF3B30`, `--accent-green-apple: #34C759`, `--accent-orange-apple: #FF9500`, `--accent-purple-apple: #AF52DE` を `theme.accentSet: "apple"` で切替可能化（**未実装**: validator V-018' で「同一スライド内で vivid と apple セットを混在禁止」を検査することを将来検討） | クライアント案件で Apple 製品トーンが要求された場合の選択肢確保。デフォルトは vivid のまま |
| SR-2-05 | **各スライドにビビッドアクセントを 1 色以上**使用 | スライドごとに `--accent-*-vivid` のいずれか1つ以上 | 視覚階層の確立、Apple品質感 |
| SR-2-06 | **1 スライドあたりビビッドアクセントは最大 2 色まで**（10% 以内の面積） | 60-30-10 配色ルール | 焦点散漫の防止・WCAG コントラスト維持 |
| SR-2-07 | 意味と色の対応 | 重要=`--wave-blue` / 課題・Before=`--sakura-pink` / 解決・After=`--wave-aqua` / 強調=`--autumn-yellow` / 補足=`--spring-violet` | 全スライドで色の意味を統一 |
| SR-2-08 | SVG の `fill` / `stroke` も **CSS 変数を使用** | `<rect fill="var(--wave-blue, #7E9CD8)" />` | SVG 属性にカラーコード直書き禁止。CSS 変数フォールバック付き |
| SR-2-09 | シャドウは 4 段階＋グロウ 3 種で統一 | `--shadow-subtle/medium/prominent/elevated`, `--glow-blue/pink/aqua` | 視覚階層の段階表現 |

---

## §3 フォント

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-3-01 | 本文フォントは **Noto Sans JP**、コードは **SF Mono / Fira Code** | `font-family: 'Noto Sans JP', sans-serif;` / `font-family: 'SF Mono', 'Fira Code', monospace;` | 日本語可読性とコード等幅性の両立 |
| SR-3-02 | フォントスケールは `--font-scale` で一括制御（既定 1.3） | `--fs-body: calc(1.5rem * var(--font-scale))` | 量産時にスライドごとサイズ調整可能 |
| SR-3-03 | フォントサイズ変数 7 種 | `--fs-title` (5rem×scale) / `--fs-subtitle` (2.5rem) / `--fs-heading` (3rem) / `--fs-subheading` (2rem) / `--fs-body` (1.5rem) / `--fs-body-lg` (1.8rem) / `--fs-small` (1.4rem) | 視覚階層の機械的担保 |
| SR-3-04 | **画面表示の最小フォントは 1.4rem**（`--fs-small`）。それ以下は禁止 | UI テキスト・補足・キャプション含む | 50名規模プレゼン・スマホ視聴で可読性確保 |
| SR-3-05 | **SVG `<text>` の最小 font-size は 13px** | `<text font-size="14px">` 以上を原則。12px は小バッジ・軸ラベルのみ許容、11px 以下は禁止 | 50名対面×プロジェクタで判読不能（約2-3mm相当）になるため |
| SR-3-06 | SVG `<text>` 内で **Font Awesome unicode（`&#xf...;`）使用禁止** | アイコンが必要なら `<foreignObject>` 内に `<i class="fa-solid ..."></i>` を置き、その div に `class="fo-card"` を付与（SR-6-04参照）。または Unicode emoji を直書き | CDN 未ロード時に PUA コードが全スライドで消失するリスク |
| SR-3-07 | 質問スライドの本文は **`--fs-subheading`** を使用（`--fs-heading` は大きすぎる） | `.question-badge ~ .main-message { font-size: var(--fs-subheading); }` | 質問の威圧感を抑え、思考誘導に適切 |
| SR-3-08 | **全スライドタイプの `h2` に CSS 定義必須**（特に `.slide-quote`, `.slide-message`, `.slide-list`, `.slide-cycle`, `.slide-flow`） | `.slide-TYPE h2 { font-size: var(--fs-heading); }` | 定義漏れがあると見出しが極小表示になる |

---

## §4 レイアウト

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-4-01 | 3層構造を厳守: `.slider` > `.slide-area` > `.slider__container` > `.slider__item` | HTML 構造の必須形 | 16:9 強制とアニメーション制御の前提 |
| SR-4-02 | スライド本体パディングは CSS 変数で制御 | `padding: var(--nav-top-padding) var(--nav-arrow-padding) var(--nav-bottom-padding);` | ナビ余白の一括カスタマイズ |
| SR-4-03 | **Before/After（比較）レイアウトは 48% / 4% / 48%** | `.compare-container { display: flex; gap: 4%; } .compare-panel { width: 48%; }` | 視覚的バランス、比率変更禁止 |
| SR-4-04 | Before=ピンク／After=アクア の色対応 | 左パネル: `--accent-pink-vivid`、右パネル: `--accent-aqua-vivid` | 直感的な意味付け（SR-2-07 と整合） |
| SR-4-05 | カードリスト（`.list-item`, `.ig-item`）は **`width: 100%; box-sizing: border-box;`** を必ず指定 | コンテナにも `width: 100%` | 指定漏れで左寄り半幅表示になるバグの防止 |
| SR-4-06 | 補足テキストは **最大 3 行 / `--fs-small` / opacity 0.7** | `.text-note { font-size: var(--fs-small); opacity: 0.7; -webkit-line-clamp: 3; }` | 主情報を阻害しない補助情報の規律 |
| SR-4-07 | 質問スライドは「**背景情報 → 質問**」の順で配置 | structure.md でこの順序を強制 | 文脈なしの質問は思考が起動しない |
| SR-4-08 | 図解はインライン SVG2 で描画。`position: absolute` で配置するレイアウト図解は禁止 | `<svg viewBox="...">` を使用 | SVG 座標系の精密制御・印刷品質 |
| SR-4-09 | **スライド ID 命名規約**: 物理順 ID は `slide-NNN`（schema 準拠）、論理順別名は `N` 接頭辞（NarrativeOrder）または `S` 接頭辞（SectionOrder）で別名指定可。`data-slide-id="N06"` のように HTML 属性へ二重持ちすることで、構成案の差し替えで物理順が変わっても論理参照が壊れない | `id="slide-006" data-narrative-id="N06"` 等。`N` = 全体ナラティブ通し、`S` = セクション内通し | 章再分割やスライド追加で物理順 ID 採番が再配布された際、references / structure.md / レビュー文書の相互リンクが破綻するのを防ぐ。SR-12-07 同期検証はこの両 ID を区別する |

---

## §5 SVG 設計

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-5-01 | viewBox は **16:9 系（960×540 等）**または図解形状に応じた専用値（円形=正方形）を使用 | `viewBox="0 0 960 540"` 等 | 解像度独立・座標計算容易 |
| SR-5-02 | viewBox 算出式: `幅 = カード幅×N + gap×(N-1) + 左右マージン×2` | structure.md の SVG 設計メモに必須記載 | 100人中100人が同じ図解を再現できる精度 |
| SR-5-03 | **テキスト 1 行最大文字数 = floor(カード有効幅 / font-size px) × 0.75**（安全マージン） | 例: 有効幅 200px / 14px → 14文字 × 0.75 ≒ 10文字 | 自動折返し不可な SVG `<text>` での溢れ防止 |
| SR-5-04 | SVG `<text>` の改行は `<tspan>` で明示。`dy = font-size × 1.5` | `<tspan x="100" dy="20">…</tspan>` | SVG は自動改行しないため |
| SR-5-05 | 矢印マーカーは `<defs>` に色別 5種（blue/pink/yellow/green/aqua）を定義 | `<marker id="arrow-blue" ...>` | 一貫性のあるフロー表現 |
| SR-5-06 | グラデーション・フィルターは `<defs>` 内で定義し ID 参照 | `<linearGradient id="grad-blue-pink">` 等 | 再利用性とパフォーマンス |
| SR-5-07 | SVG 設計メモには 12 項目（viewBox / 各座標 / カードサイズ / フォント / 最大文字数 / 最大行数 / 改行位置 / padding / gap / 接続線 / アクセント / 文字数検証）を **すべて** 明記 | structure.md テンプレ準拠 | 実装ブレを排除 |

---

## §6 GSAP アニメーション

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-6-01 | **`scale: 0` および `scale: 0.5` 禁止**。最小 `scale: 0.8` | `gsap.from(el, { scale: 0.8, ... })` または `x: -30 / y: 30` で代替 | 残留 transform で要素消失するバグの防止 |
| SR-6-02 | **`clearProps: 'all'` は `content.children` のみに適用**。`content.querySelectorAll('*')` は禁止 | `gsap.set(content.children, { clearProps: 'all' })` | `*` 適用は SVG fill/stroke 属性と foreignObject レイアウトを破壊する |
| SR-6-03 | `clearProps` は updateSlide() と leaveAnimation() の onComplete の両方で適用 | 両ライフサイクルでリセット | 残留スタイルを完全除去 |
| SR-6-04 | **foreignObject 内 div には `class="fo-card"`（または `fo-card--row`）を付与**。インライン style のみのレイアウトは禁止 | CSS 側で `.fo-card { ... }` を定義 | clearProps に消されないクラスベース防御 |
| SR-6-05 | イージングは **3 種以上** 使い分け | `power2.out` / `back.out(1.7)` / `power1.inOut` / `elastic.out(1, 0.3)` / `power3.inOut` から組合せ | 単調 ease の繰り返しを防ぎ表現に階調 |
| SR-6-06 | スライド遷移は `duration: 0.25, ease: 'power3.inOut'`、enter は `'-=0.15'` で並行開始 | scripts.js 標準値 | 高速・スムーズの体感 |
| SR-6-07 | leave アニメーションは enter より短く（duration 0.15-0.2、stagger 0.03-0.05） | 退場は素早く | 切替の俊敏感 |
| SR-6-08 | `prefers-reduced-motion` 検出時は duration/stagger を 0 倍率にするグローバル変数を scripts.js 冒頭で定義 | `const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;` | アクセシビリティ必須対応 |

---

## §7 印刷

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-7-01 | `@page { size: A4 landscape; margin: 0; }` | 余白なし・A4 横 | 配布資料としての一貫サイズ |
| SR-7-02 | `.slider__item` は **width/height/min-height/max-height すべて 297mm × 210mm 固定** | SR-1-03 と同一 | コンテンツ量に関係なく1ページ1スライド |
| SR-7-03 | 枠線・margin 禁止（`border: none; margin: 0;`） | A4 フルサイズ印刷 | 見た目のロスを排除 |
| SR-7-04 | **印刷時 GSAP インラインスタイルを必ずリセット** | `@media print { .slider__content, .slider__content > *, .slider__content * { visibility: visible !important; opacity: 1 !important; transform: none !important; } }` | リセット忘れでスライドが空白になる事故防止 |
| SR-7-05 | 印刷時はナビ系を非表示 | `.progress-bar, .navigation, .slide-counter, .dot-pagination, .agenda-indicator { display: none !important; }` | 配布資料に不要 |
| SR-7-06 | 色再現を強制 | `* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }` | 背景色・アクセント色の保持 |
| SR-7-07 | `data-hidden="true"` のスライドは印刷から除外（display:none + height:0） | スキップスライド対応 | 完成版/ドラフト併存時の柔軟性 |
| SR-7-08 | **印刷=画面の同一比率を保つ**（padding/font-size/gap/border-radius は画面と同比率） | 印刷専用に padding/font 等を極端縮小しない | 視覚的整合性。SR-7-09 の矛盾を参照 |
| SR-7-09 | **【既知の矛盾】** 現実装の `print-layout.md` は印刷時にフォントサイズ縮小を多用している（例: `.slide-title .title-main { font-size: 3rem; }`）。一方 SKILL.md ベストプラクティスは「印刷=画面同じレイアウト」を要求 | **現状**: 縮小許容（`@media print` 内のフォント縮小は既存実装互換のため許容）。**将来形**: vw/`--font-scale` 統一で印刷時も画面と同じレイアウトに収束させる（縮小ゼロ化）。新規生成では SR-7-08 を優先しつつ、レガシー互換のため fallback として縮小ルールを残してよい | A4 物理サイズ（297mm）と画面 vw 換算の差を吸収する暫定策。新規スライドは vw + `--font-scale` で印刷でも崩れない設計を目指す |
| SR-7-10 | shadow は印刷で除去（`box-shadow: none !important`） | カード系のみ | インクコスト削減・視認性 |

---

## §8 ナビゲーション

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-8-01 | **ページネーションは 5 個区切りマイルストーン方式**（標準） | `.pagination .dot:nth-child(5n) { background: var(--accent-aqua-vivid); width: 0.7rem; height: 0.7rem; margin-right: 0.5rem; }` | 25 枚超でも現在位置が一目で分かる |
| SR-8-02 | 単色ドットのみは禁止（区切り必須） | `nth-child(5n)` 必須 | 多枚スライドでの位置感覚喪失防止 |
| SR-8-03 | **セクション目次ナビ（section-nav）を常時表示** | スライド左上 `.agenda-indicator` または上部 `.section-nav` | 構造把握を補助 |
| SR-8-04 | **`.section-nav__item.active[data-section="X"]` は HTML の全 data-section 値を網羅** | opening / lecture / demo / ws / summary / closing 等すべて 1対1 で CSS 定義 | 1つでも欠けるとナビ色が表示されない |
| SR-8-05 | セクション色分けは代替案（オプション）。基本は SR-8-01 とセクションナビの併用 | `.pagination .dot[data-section="X"]` は無くてよい | 役割分担の明確化 |
| SR-8-06 | 左右矢印は `var(--nav-arrow-padding)`（既定 3rem）で配置 | `position: fixed; padding: 0 var(--nav-arrow-padding)` | 量産時の余白一括調整 |

---

## §9 アクセシビリティ

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-9-01 | **WCAG 2.1 AA 準拠**（コントラスト比 4.5:1 以上） | `--accent-blue-vivid: #3B7DD8` on `#fafafa` = 4.5:1 等を確認 | 視覚障害含む全ユーザー可読性 |
| SR-9-02 | `:focus-visible` を全インタラクティブ要素に適用 | `:focus-visible { outline: 3px solid var(--accent-blue-vivid); outline-offset: 2px; }` | キーボード操作可視性 |
| SR-9-03 | `prefers-reduced-motion` 対応必須 | CSS: `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }` ＋ JS は SR-6-08 | 前庭障害・乗り物酔い配慮 |
| SR-9-04 | **UI テキスト（ナビ・ラベル・キャプション）の opacity は 0.6 以上** | `.text-note { opacity: 0.7; }` 等 | 0.3 等は読めない |
| SR-9-05 | `aria-label` を SVG 図解に必須 | `<svg role="img" aria-label="図解の説明">` | スクリーンリーダー対応 |
| SR-9-06 | `sr-only` クラスと `aria-live` を適切に使用 | スライド遷移通知等 | 動的コンテンツのアクセシビリティ |

---

## §10 コードブロック

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-10-01 | **コードブロック `max-height: 420px` で全回統一** | `.code-block { max-height: 420px; overflow-y: auto; }` | 視覚的一貫性。340px 等の不統一は禁止 |
| SR-10-02 | フォントは SF Mono / Fira Code（Noto Sans JP は禁止） | `font-family: 'SF Mono', 'Fira Code', monospace;` | 等幅表示 |
| SR-10-03 | 共通スタイル: `font-size: 1.4rem; line-height: 1.7; padding: 20px 24px; border-radius: 12px;` | structure.md コードブロック共通仕様 | 可読性 |
| SR-10-04 | ヘッダー行（`#`）はアクセントブルー太字、変数（`{変数}`）はアクセントイエローハイライト | 色は `--accent-blue-vivid` / `--accent-yellow-vivid` | 構文ハイライトの簡易版 |
| SR-10-05 | Before/After コードブロックは横並び 48% / 4% / 48%（SR-4-03 と整合） | `.code-compare { display: flex; gap: 4%; } .code-panel { width: 48%; max-height: 280px; }` | 比較しやすさ |
| SR-10-06 | Before ヘッダー = `--accent-pink-vivid` 背景、After ヘッダー = `--accent-aqua-vivid` 背景 | SR-4-04 と整合 | 意味の一貫 |

---

## §11 検証 ID 対応表（S1-S26 × SR-ID）

UI 品質レビュー（`agents/ui-quality-reviewer.md`）の検証項目 S1-S26 が、本 SSoT のどの SR-ID を根拠とするかを示す。

| 検証ID | 検証内容 | 参照 SR-ID |
|--------|----------|------------|
| S1 | CSS/JS分離（インライン禁止） | SR-12-08（agents/html-generator） |
| S2 | 外部ファイル参照存在 | SR-12-08 |
| S3 | 質問スライド配置順序 | SR-4-07 |
| S4 | 質問スライドフォント = fs-subheading | SR-3-07 |
| S5 | slide-area 3層構造 | SR-4-01 |
| S6 | 16:9 アスペクト比 | SR-1-01 |
| S7 | 印刷カード比率（画面同等） | SR-7-08 |
| S8 | 印刷 A4 フルサイズ（margin 0・枠なし） | SR-7-01, SR-7-03 |
| S9 | ページネーション 5個区切り | SR-8-01 |
| S10 | ビビッドアクセント各スライド1色以上 | SR-2-05 |
| S11 | イージング3種以上 | SR-6-05 |
| S12 | アクセシビリティ基本（focus/reduced/sr-only/aria） | SR-9-02, SR-9-03, SR-9-05, SR-9-06 |
| S13 | UI テキスト opacity 0.6 以上 | SR-9-04 |
| S14 | 視覚階層（L1/L3 サイズ差 2倍以上） | SR-3-03（fs スケール） |
| S15 | CARP 原則（近接・対比） | SR-1-06, SR-2-05 |
| S16 | 60-30-10 配色 | SR-2-06 |
| S17 | clearProps 安全パターン | SR-6-02, SR-6-03 |
| S18 | foreignObject CSS 保護（fo-card） | SR-6-04 |
| S19 | A4 印刷仕様準拠（mm/rem/vw、px禁止） | SR-1-03, SR-1-04, SR-7-01〜03 |
| S20 | コンテンツ完全性（structure.md ⇔ HTML 一致） | SR-12-08 |
| S21 | ソース情報反映 | SR-12-08 |
| S22 | SVG テキスト最小 13px | SR-3-05 |
| S23 | SVG 内 FA unicode 禁止 | SR-3-06 |
| S24 | 全スライドタイプ h2 CSS 定義 | SR-3-08 |
| S25 | section-nav HTML/CSS 整合 | SR-8-04 |
| S26 | code-block max-height 420px 統一 | SR-10-01 |

---

## §12 逆引き（agent / script / asset → 参照すべき SR-ID）

| エージェント / スクリプト / アセット | 参照すべき主な SR-ID |
|------------------------------------|----------------------|
| `agents/structure-designer.md` | §1 全件、§2 全件、§3 全件、§4 全件、§5 全件、§7-08 |
| `agents/html-generator.md` | **全件**（特に SR-1-04, SR-2-08, SR-3-05/06/08, SR-4-03/05, SR-6-01〜04, SR-7-04, SR-8-04, SR-10-01） |
| `agents/ui-quality-reviewer.md` | §11 表で S1-S26 から各 SR-ID を逆引き |
| `agents/slide-modifier.md` | 改修対象セクションの SR-ID。最低限 SR-4-01, SR-6-02, SR-7-04 を保持 |
| `agents/d3-diagram-designer.md` | §5 全件、SR-3-05, SR-3-06, SR-9-05 |
| `agents/data-visualizer.md` | §2 全件、SR-3-05, SR-9-01 |
| `agents/cross-deck-reviewer.md` | SR-2-04, SR-3-03, SR-8-04, SR-10-01（横断統一の核） |
| `agents/layout-optimizer.md` | §4 全件、SR-1-04, SR-1-06 |
| `agents/hearing-facilitator.md` | （直接適用なし。Phase1 は要件収集のみ） |
| `assets/structure-template.md` | **全件**（structure.md は本 SSoT の値を埋め込む） |
| `assets/slide-template.html`, `assets/slide-template-single.html` | SR-1-01, SR-2-01, SR-4-01, SR-7-* |
| `assets/print-styles.css` | §7 全件 |
| `scripts/verify-slides.js` | SR-1-01, SR-7-02 |
| `scripts/check-consistency.js` | SR-2-04, SR-3-03, SR-10-01 |
| `scripts/validate-structure.js` | §5 全件、SR-4-01 |
| `scripts/validate-d3.js` | §5、SR-3-05 |
| `scripts/sync-checker.js` | structure.md ⇔ index.html の SR-ID 単位での同期確認 |
| `scripts/build-single-html.js` | SR-1-01, §7 全件（GAS デプロイ後も印刷可能性維持） |
| `scripts/cross-deck-consistency.js` | SR-2-04, SR-3-03, SR-8-04, SR-10-01 |

> **追加の SR-12-XX**: agent / script 固有の運用制約は将来ここに追記する余地として確保（例: SR-12-08 = 「CSS/JS は分離出力。インライン `<style>` / `<script>...</script>` 禁止。`<link rel="stylesheet">` と `<script src>` で外部参照」）。

### SR-12-XX（agent/script 由来の運用制約）

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-12-01 | バッチ並列生成時、`slider__item` の数 = structure.md のスライド数 | 一致しない場合は差し戻し | コンテンツ完全性（S20） |
| SR-12-02 | バッチ並列生成時、`nth-child(5n)` が styles.css に存在 | SR-8-01 の機械検証 | ページネーション標準化 |
| SR-12-03 | バッチ並列生成時、`.slider__content *` が `@media print` 内に存在 | SR-7-04 の機械検証 | GSAP リセット保証 |
| SR-12-04 | バッチ並列生成時、`scale: 0` が scripts.js に存在しない | SR-6-01 の機械検証 | 残留 transform 防止 |
| SR-12-05 | CDN は GSAP 3.12.2 / FontAwesome 6.5.1 / Noto Sans JP のみ使用可（任意で Bootstrap Icons / Material Symbols） | 他 CDN は許可しない | セキュリティと一貫性 |
| SR-12-06 | 写真・画像素材は **WebP 形式推奨**。PNG/JPG は変換してから使用 | `scripts/convert-to-webp.js` 利用 | ファイルサイズ削減 |
| SR-12-07 | index.html ⇔ structure.md は**常に同期**。HTML 修正時は必ず structure.md も更新 | `scripts/sync-checker.js` で検証 | 二重管理の破綻防止 |
| SR-12-08 | **CSS / JS はインライン禁止・外部ファイル分離**（`<link>` / `<script src>`） | GAS デプロイ用 1 ファイル化は `scripts/build-single-html.js` で生成 | 保守性・差分レビュー容易性 |

---

## §13 逐語コンテンツの非画像化（コード専用ページ）

| SR-ID | ルール | 値 / 実装 | Why |
|-------|--------|-----------|-----|
| SR-13-01 | **正確性必須・逐語コンテンツ（コード・数式・精密数値表）は画像化しない。コード系 slideType（`slide-code` / `slide-code-compare`）は aiVisual で image-only / baked-with-overlay 不可** | image-only デッキ・全面AI画像化デッキを含むどの場合でも、コードは実HTMLコードブロック（`.code-block` / `.code-compare-body`）で描画する「コード専用ページ」とする。`aiVisual` を持たない純HTMLコードページが正規デフォルト。世界観背景が必要な場合のみ `aiVisual` は `pattern: html-composite` / `backgroundSource: svg`（推奨）または `raster` / `textPolicy: overlay-only` に限定。機械検証は V-043（`scripts/validate-structure.js`）と `schemas/structure.schema.json` の slide allOf if/then。 | AI画像はコードを正確に再現できず（誤字・崩れ・コピー不可・印刷で判読不能）、逐語の正確性が損なわれる。実HTMLなら構文ハイライト・選択コピー・印刷品質を保てる |

---

## 改訂方針

- **本ファイルが正本**。既存 references / SKILL.md ベストプラクティス表との矛盾は本ファイルで明示し、`SR-7-09` のように現状/将来形を記録する。
- 新規ルール追加時は対応する §に SR-ID を採番し、`Why` と `実装値` を必ず併記する。
- ルール削除時は SR-ID を欠番化し（再利用しない）、`§11` の検証 ID 対応表も更新する。
- 既存 references の段階的移行: 各 reference の冒頭に「正本: spec-registry.md SR-X-XX 参照」を追記し、本ファイルの該当 SR-ID へ誘導する（後続タスク）。
