---
name: jp-web-design
description: 日本語Web UIの素材集。既定配色は暫定標準カラー(ブルー基調・ライトのみ・色は役割トークンだけを参照し、主操作は action-primary-*、状態は status-* に固定)。明示指定時だけMode B Pop。タイポと数値表記・レスポンシブ4段・部品HTML/CSS・モーションとa11y・情報設計の工程と表示形式の導出・動く参照実装(assets/reference)・コントラスト検査/トークン生成/旧配色の自動移行スクリプトを持つ。設計判断と体験の規律は含めない(Skill ux-design から参照される後工程)。UIの実装・見た目のレビュー・配色の導入や移行で必ず参照する。
---

# 日本語Web UI デザインシステム

実プロジェクトの反復フィードバックから確立した規範。装飾を足して良く見せるのではなく、余白・面・文字の階層で秩序を作る。色は「意味」にしか使わない。

- 配色の既定は暫定標準カラー(版は正本CSSの見出し)。値の正本は `assets/standard/standard-color-system.css` の1つだけで、使い方の正本は `references/standard-color-system.md`。公式CI指定値ではない暫定案なので、正式値が来たら基本色 `--p-*` だけを差し替え、役割トークン名と役割の割り当ては変えない。差し替えに伴う生成物の再生成・コントラスト検査・テスト・下流への配布・記述の追随は `references/standard-color-system.md` §0「色の値・版を変えるときの手順」が正本(手順を記憶で省略しない)。
- **指定なしの可視Web UIは `assets/reference/catalog.html` を既定にする**。生成アプリへ適用する唯一の契約は `references/catalog-default-contract.md`、機械可読な正本は `assets/reference/catalog-default-profile.json`。build / improve とも、詳細を記憶で再実装せず `scripts/catalog-default.mjs` の plan → apply → verify を通す。
- 迷ったら「色を足す」ではなく「余白と階層で解く」。
- 本書は素材集。業務構造の診断・体験の規律(デフォルト・一括操作・エラー回復)・検収の判断は Skill `ux-design` が正本で、本書では再説明しない。設計の入口から順に読んで本書へ辿り着く前提で、逆方向には参照しない。
- 本書は中核ルールだけを載せる。詳細は §6 のリファレンス索引から必要なファイルを読む(作業前に該当ファイルを必ず開く)。

## 起動プロトコル — 質問より先に代表画面を作る

UIの新規設計・リニューアルでは、依頼文・既存画面・業務フロー・ブランド資産を調べ、次を内部で確定する。質問より先に、最頻業務を表す完成度の高い代表画面を1つ作る。複数の無難な案は並べず、最有力案を正本として実装する。

1. カラー: 標準カラー(ブルー基調・ライトのみ)を既定とし、`references/standard-color-system.md` を必ず読む。利用者が「Pop」「親しみ」「toC向け」などを明示した場合だけ Mode B(`references/mode-b-pop.md`)。
2. 既存アプリ: 改善・再構築では `references/catalog-default-contract.md`「既存アプリの一本化フロー」(verify → 移行plan → safeだけapply → plan/apply → verify → T2記録)に従う。色だけを移行し、画面構成・文言・余白は変えない(INV-15)。
3. ロゴ・アイコン素材: 既存のロゴ/アプリアイコンはあるか? あればヘッダー・faviconへ使用する。なければテキストロゴで開始(ロゴの自作はしない)。
4. テーマ: ライトのみ。Dark・OS追従・テーマ切替は作らない(INV-15、`references/standard-color-system.md` §2-10)。
5. catalog-default: 新規の可視UIは確認なしで `apply --app-state=new`、既存UIは手順2のフロー。適用判定(REPORT_ONLY / NON_VISUAL)は `references/catalog-default-contract.md` が正本。

未指定項目は上記既定で進め、判断と却下した主要候補をT2へ残す。ロゴ原本、法的ブランド制約、公開前承認など本人しか決められない境界があっても、テキストロゴやローカルpreviewで成果物を先に作り、差し替え箇所だけを依頼者へ示す。

## 0. 8秒でわかる原則

0. 順序が結果を決める — 表から書き始めない。場面の1文 → ラベル剥がし → 伝わらないものだけ最小限に補う → グループ化 → 優先順位 → 表示用加工 → 表示形式の導出 → 機能と意味づけの装飾。設計とデザインを分けず、この8工程で作る(`references/information-design.md`)。装飾を後から足しても画面は良くならない。
1. 色は役割で固定する — ブランドの軸(`--p-brand-indigo`)=ナビ・見出し・リンク、アクセント(`--p-brand-accent`)=`action-primary-*` と `focus-ring` だけ、意味色(`status-*`)=状態だけ。部品は `--p-*` を直接使わず役割トークンを使う。
2. 1画面に `action-primary-bg` のボタンは1つ — 保存・送信・次へなど主操作だけ。キャンセル・戻る・削除に使わない。濃色のナビ地にアクセント色の小文字やフォーカス線を置かない(`focus-ring-inverse` を使う)。
3. メリハリ: 1画面に視覚的主役を1つ — 全部同じサイズ・太さの画面は視線の行き場がない。「まずここ」を大きく、それ以外は静かに。
4. マニュアル不要 — 押せるものは押せる見た目、押せないものに押せる見た目を与えない。初見で最頻タスクが完了できるか。
5. 折返しを設計する — 単語・数字・チップの「途中折返し」「1文字/1個だけ折返し」を全ブレークポイントで禁止。
6. 数字はExcel基準でシャープに — 単位は列ヘッダー、セルは生数値+カンマ。数字は欧文フォントで描画する。
7. 動きは因果の説明だけ — 装飾のためのアニメーションを足さない。`reduced-motion` で全部止まる。
8. 数字はすべて本物 — 演出のための偽の数字・煽り・偽の緊急性を使わない。
9. AIを通常機能として描く — 紫・ネオン・専用グラデーションを割り当てず、他画面と同じ情報階層・ボタン・状態表現を使う。

## 1. 標準カラーの導入

1. 正本CSSの配置先(`src/styles/aidd/`)・読み込み順・生成物は `references/catalog-default-contract.md` に従い、`scripts/catalog-default.mjs apply` で配置する(手でコピー・値の書き換え・JS定数への複製をしない)。
2. 部品は役割トークン(`--app-background` `--surface` `--text-primary` `--action-primary-bg` `--input-border` `--status-*-text` など)だけを参照する。直書きHEX・Tailwind既定色(`bg-slate-*` など)は使わない。
3. 足りない役割は部品側で色を作らず、CSSの役割トークン層へ追加して `node scripts/check-standard-contrast.mjs` と `node scripts/export-standard-tokens.mjs` を実行する。
4. フォント・寸法は色と独立に `:root` へ置く:

```css
:root {
  --font-ui: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Hiragino Sans", "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
  --font-display: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
  --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  --font-num: "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Yu Gothic UI", sans-serif;
  --font-size-body: 16px;
  --font-size-control: 16px;
  --font-size-label: 16px;
  --font-size-section: 18px;
  --font-size-page: clamp(22px, 2vw, 24px);
  --font-size-app: 20px;
  --font-size-display: clamp(40px, 7vw, 56px);
  --tap: 44px;
}
body { background: var(--app-background); color: var(--text-primary); font-family: var(--font-ui); }
```

Tailwind v4 の読み込み順は contract、`@theme inline` の役割トークン橋渡しは `references/standard-color-system.md` §3。`[hidden] { display: none !important; }` を必ず入れる(`display: flex/grid` のユーティリティが `hidden` 属性を上書きする事故を防ぐ)。

## 2. カラー規律 — 標準カラー(最重要)

| 層 | 役割 | 使うトークン |
|---|---|---|
| 地と面 | 背景・カード | `app-background` / `surface` / `surface-alt` |
| 骨格 | 文字・罫線・ナビ | `text-primary` / `text-secondary` / `border-subtle` / `nav-background` |
| 操作と状態 | 操作と状態だけ | `action-primary-*`(主操作だけ) + `status-*`(状態だけ) |

面積の出発点(3層の比率)は本書に数値を持たず `references/standard-color-system.md` §1 が正本。

- アクセント(`--p-brand-accent`)の用途は `action-primary-*`・`focus-ring`(3px)・選択線・必須表示・進捗の強調に限る(§0-2)。リンクは色と下線を併用する。
- 意味色(`status-*`)はアクセントと別の色。成功・注意・エラー・情報は文言と記号を必ず併用し、ブランド色(`--p-brand-*`)を流用しない。
- 入力欄の枠は `--input-border`(3:1以上)。装飾罫線 `--border-subtle` を入力の境界に使わない。
- 無効状態は `--action-disabled-*` を使い、opacityで薄くしない。
- 表はヘッダー面(`--table-head-bg`)と交互行(`--table-stripe-bg`)を使ってよい。選択行は色+左線+`aria-selected`。
- カード左端の色帯(カテゴリ/ステータスのアクセントボーダー)は禁止(発注者フィードバックに基づく恒久ルール、2026-07)。分類・状態の色はチップ/ドット/進捗バーで示す。
- 注目させたい面だけ `--surface-accent`(アクセントの淡い面)を1画面1〜2か所使ってよい。
- 原色・蛍光色・専用グラデーションを追加しない。画面の地は白で、灰色や色付きの地を全面に敷かない。

> 12ルール・役割トークン表・73要素の適用表・部品の色契約は `references/standard-color-system.md`。ペアごとのコントラスト比は `node scripts/check-standard-contrast.mjs` の出力が正。ナビ骨格は `references/layout-responsive.md`。

## 3. 中核の寸法表(毎回参照する3つ)

### 3-1. タイポグラフィ階層(主役:本文 = 2.5倍以上)

| 用途 | サイズ | 太さ |
|---|---|---|
| ページ主数字(結果)= 主役 | `--font-size-display`(40〜56px) | bold・`--text-primary`・`--font-num` |
| ページタイトル | 22〜24px | bold |
| セクション見出し | 18px | 太字だが静かに |
| 本文・操作 | 16px | normal |
| ラベル | 15〜16px | normal |

> 見出しを「大きく・色付き」で目立たせない。主役は中身(数字・事実)。主役の作り方・説明文を視覚要素に置き換える手順は `references/typography-numerals.md`。

### 3-2. レスポンシブ4段(この4幅で実測してから完成とする)

| 呼称 | 幅 | コンテナ | 検証幅 |
|---|---|---|---|
| SP | 〜639px | 全幅・padding 16〜20px | 375px |
| タブレット | 640〜1023px | 全幅・padding 24px | 768px |
| PC | 1024〜1439px | `max-w-5xl`(1024px)中央 | 1280px |
| ワイド | 1440px〜 | `max-w-6xl`(1152px)中央・それ以上広げない | 1600px |

- ブレークポイントはTailwind既定(`sm:640 / md:768 / lg:1024 / xl:1280`)に合わせ、独自の中途半端な値を作らない。
- 部品の折返し・列切替・カード化は `@container`(コンテナクエリ)で書き、メディアクエリはページ骨格だけに使う。
- SPは「小さくする」のではなく「減らす」(テーブル→カード化・折りたたみ・上位N件)。詳細は `references/layout-responsive.md`。

### 3-3. 数値のCSS(数字は必ず欧文フォントで描く)

```css
.num { font-family: var(--font-num); font-variant-numeric: tabular-nums; letter-spacing: -0.02em; white-space: nowrap; }
.num-display { font-family: var(--font-num); font-variant-numeric: tabular-nums; letter-spacing: -0.015em; font-weight: 700; }
.num-sep  { font-size: 0.8em; font-weight: 400; }                                        /* 大型数字のカンマは脇役に */
.currency { font-size: 62%; font-weight: 600; margin-right: 0.15em; letter-spacing: 0; } /* 通貨記号は単位扱い */
```

表記規則(Excel基準・単位は列ヘッダー・KPIは正確な値)と「濃く太い数字=変わる値」の文法は `references/typography-numerals.md`。

## 4. 絶対ルール要約(モード共通・違反したら作り直す)

- 表から書き始めない。情報設計の工程(`references/information-design.md` §2)を通してからマークアップに入る。表示形式は6つの判断軸から導出する(同 §5)。結果として表を選ぶのは可だが、選定理由と却下候補を1行で言えること。
- 文章量と操作フローは `references/information-design.md` §3-1 を正本とする。文字を削るだけでなく、判断・遷移・例外分岐を減らし、次の操作を業務語で明示する。
- 前例のない要件を「対応不可」にしない。同 §9 の手順(原理に還元 → 軸で測る → 慣習を探す → 実データで検証 → 判断を記録)で導く。通常の表示形式・ラベル・加工・画像の判断は標準の `docs/product/T2-experience-spec.md`(プロジェクトに同等責務の既存正本がある場合はその正本)に残し、前例のない例外だけ `docs/product/design-decisions.md` に分離する。
- DBの生値(ISO日時・コード値・真偽値・内部ID)を画面にそのまま出さない(突合・出力・入力欄は例外で生値が正)。
- 画像は役割を判定してから置く。識別・証拠・説明の画像は目的に応じて強調し、装飾だけなら原則削除する。採用時は alt・キャプション・トリミング・4幅(375/768/1280/1600px)を設計と検収の対象にする(`references/information-design.md` §4-1)。
- 群の境界は余白で作る。罫線・背景色・囲みを足す前に余白を倍にする。分類ごとの色分けは使わない(表のヘッダー面と交互行は標準カラーのトークンで可)。
- 色は §0-1・§0-2・§2 と起動プロトコル4に従う。直書きHEX・Tailwind既定色・旧トークン(`--primary` `--accent` `--ink` など)を残さない。
- 1画面に視覚的主役を1つ。主役:本文のサイズ比2.5倍以上。同格要素のサイズは揃える。
- 常設の補足説明は作らない。可視DOMは見出し・ラベル・値・状態・エラーと次の操作・不可逆警告に限り、開発者注記と参照実装のサンプル文言は `references/information-design.md` §3-1 に従って非表示にする。
- 数字は `--font-num`(欧文)+ `tabular-nums`。テーブルは生数値+カンマ、単位は列ヘッダー、1列1単位。
- 「濃く太い数字=変わる値」の文法を全画面で統一する(値=太く濃い / ラベル・単位=小さくmuted)。
- 「1文字だけ改行」「1個だけ折返し」「途中折返し」を 375/768/1280/1600px の4幅すべてで出さない。ページ全体の横スクロール禁止。
- 語の途中で折り返さないことが既定。`word-break: break-all` をはみ出し対策として全体に当てない(はみ出す長い連続文字だけ `overflow-wrap: anywhere`)。短いラベル・ボタン文言・表ヘッダーは折り返さず、収まらないなら文言を短くするか省略表示にする。単位・記号を行頭行末に孤立させない。
- 頭文字アイコン(丸や四角に漢字1字)・多色アイコン・絵文字・自作SVGアイコンは禁止。迷ったらアイコンなし。
- 押せないものに押せる見た目(hover効果・`cursor: pointer`)を与えない。アイコン単独ボタンを作らない。
- すべてのアニメーションは `prefers-reduced-motion: reduce` で止まる。バウンス・オーバーシュートは使わない。
- フォーカスは必ず可視化(`:focus-visible` に `--focus-ring` の3pxアウトライン+白の隙間。紺地では `--focus-ring-inverse`)。タップ領域44px。状態を色だけで伝えない。
- 表示する数字はすべて本物の計算結果。偽の緊急性・煽り・confirmshaming 禁止。

## 5. リファレンス実装(`assets/reference/` — 構造・UX規律は検収済み / 標準配色は暫定・未検収)

本スキルの全規律を実装した「動く正解」がコードで保存されている。指定なしの可視UIは `references/catalog-default-contract.md` を入口に機械適用し、画面固有の構造・操作を実装するときだけ該当部品を開いて流用する(記憶で似せて書かない)。

- `assets/reference/README.md` — ファイルマップとReact/TypeScriptへの移植ルール(クラス→コンポーネント対応表つき)。まずこれを読む。
- `catalog-default-profile.json` = 生成アプリ向け既定profile / `styles.css` = 全部品のCSS(部品CSSの正本。色の値は持たず標準カラーCSSを import)/ `term-ui.js` = 用語の段階開示UIの正本 / `reference-interactions.js` = catalog・Pop共通の操作helper / `index.html` + `app.js` = 標準カラーの画面構造とvanillaロジック / `pop.html` = モードBの全ディテール / `catalog.html` = 部品カタログ(本文は編集原本、CSS/JSの埋め込み範囲だけ生成物) / `assets/standard/` = 標準カラーCSS(色の値の正本)・生成JSON・配色プレビュー
- マスコット: `assets/pop-mascot-editable.svg`(原本)+ `reference/mascot-bordered.svg` / `mascot-borderless.svg`(再着色例)
- スクリプト(Node 18+、終了コード 0=成功 / 1=要対応 / 2=入力エラー):
  - `node scripts/check-standard-contrast.mjs` — 主要50ペア(本文4.5:1・非テキスト3:1)と避けるペアを検査。axe等の画面全体検査は置き換えない。
  - `node scripts/export-standard-tokens.mjs [--check]` — CSSの機械可読メタデータとトークンからJSON・standalone previewを一括生成。生成物は手書きしない。
  - `node scripts/inline-catalog-css.mjs [--check]` — `styles.css`・標準カラーCSS・`term-ui.js`・`reference-interactions.js` を `catalog.html` へ埋め込み、HTML 1ファイルで共有できるようにする。いずれかを変えたら再実行する。
  - `node scripts/migrate-legacy-colors.mjs <dir> [--plan|--apply] [--json]` — dry-run→計画→safeだけ適用。schema v1.0の報告へreview-only・対象外・未対応構文も残す。
  - `node scripts/catalog-default.mjs <plan|apply|verify> <app-root> ...` — 新規/既存の適用資格を判定し(既存は `--eligibility` 未指定時に移行スクリプトと同じ共有判定で自動算出)、正本CSS・provenance・v0/v1 conformance reportを生成する。参照画面の説明文やサンプルデータはコピーしない。
  - `node scripts/catalog-runtime-audit.mjs <app-root> [--base-url=<url>]` — 生成アプリをChromeの4幅と実pointer/keyboardで操作し、v1証拠を生成する。`catalog-default.mjs verify --stage=v1` からも必ず再実行される。
  - `scripts/lib/` — 上記スクリプトの共有lib(内部用。直接実行しない)。`tests/` — 参照実装とスクリプトの回帰テスト。
- どのフレームワークでも: 指定なしは `references/catalog-default-contract.md`、明示指定時だけ `references/mode-b-pop.md` または外部ブランド。正式版前は4幅実測+動的パス操作のv1検収を必ず通す。

## 6. リファレンス索引(`references/` — 作業内容に応じて読む)

| ファイル | 読むタイミング | 内容 |
|---|---|---|
| `references/information-design.md` | 画面を設計する前(必読)・既存画面の改善指示を受けたとき・「見づらい/ダサい」の指摘時・本書に前例がない要件のとき | 情報設計の工程8ステップ、「設計→装飾」の順で作った画面の6症状、ラベル剥がしの原則、表示用データ加工の原則、表示形式の導出(6判断軸→導出ルール→合成/分割/新規採用→検証)、配置の4原則、既存画面のリライト手順、前例がない要件への適用手順(自己拡張) |
| `references/standard-color-system.md` | UIを作る・直す・配色をレビューするとき(必読)・既存アプリの移行 | 標準カラーの色の役割と12ルール、役割トークン表とTailwind橋渡し、73要素の適用表、コントラストの検査方針、部品の色契約、a11y、トークン保守、旧配色移行の安全規則 |
| `references/typography-numerals.md` | 文字・数字を扱う全作業 | system-first書体、メリハリ(主役の作り方・サイズ表)、常設補足0件、Excel基準の数値表記CSS、値/ラベルの描き分け、アフォーダンス、折返しプロパティの使い分け表と禁則、UXライティング |
| `references/layout-responsive.md` | 画面骨格・レスポンシブ対応 | アプリシェル、余白・角丸、4段ブレークポイント表、モバイル情報削減、コンテナクエリ第一、結果/レポート画面の情報階層、固定ヘッダー・固定フッター |
| `references/components.md` | 部品を作る・レビューする | ボタン/フォーム/バッジ/テーブル/選択バー/モーダル/トースト/空状態のHTML、アイコン方針、スライダー座標系、バーチャートの3条件、専門用語の段階開示 |
| `references/motion-a11y.md` | アニメーション・hover・展開・a11y実装 | hover/pressed/入場/モーダル/展開/処理中/状態更新の時間表とCSS、操作感、reduced-motion、フォーカス・コントラスト・タップ領域 |
| `references/mode-b-pop.md` | 利用者がPopを明示指定したとき(必読) | パステル変換表、Pop用トークン、迷いゼロの構造、かわいらしさの作法、マスコット使用ルール |
| `references/acceptance-checklist.md` | 実装完了前の検収 | v0/v1適合、4幅実測、動的パス操作を含む検収チェックリスト |
| `references/catalog-default-contract.md` | build / improve で可視UIを作る・変えるとき(必読) | catalogを指定なし既定として生成アプリへ適用するplan/apply/verify、既存アプリの一本化フロー、CSSの配置先と読み込み順、provenance、v0/v1ゲート |
