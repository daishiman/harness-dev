# レイアウト最適化規約（layout-optimizer 手続き知識 SSOT）

> **正本**: このファイルは layout-optimizer から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/layout-optimizer.md）の双方がこれを参照する。規則の上位正本 (SR-ID) は spec-registry.md を辿る。

**責務**: スライド内レイアウト最適化のドメイン定義（用語集・評価基準・制約カタログ CONST_001-011）とレイアウト計算規約（横方向のレイアウト計算式・縦方向の残余配分・読み取り用画像の寸法・浮遊UIの置き方・意図的改行の仕様・印刷時の最適化換算表・全コード例）の逐語正本。横方向（文字数→幅→フォントサイズ）と縦方向（面の高さ→ブロック配分）は別系統として両方を規定する。layout-optimizer（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。5.4 実行方式が参照する決定論的計算規約であり、感覚値による直接指定を禁じ（CONST_001）、数式・係数・換算値を SSOT として保持する。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| 最長タイトル文字数 | 同一スライド内のタイトル群を countChars で計測した最大値 | フォントサイズ決定 |
| 全角/半角字幅係数 | 文字数→必要幅換算の係数。全角=0.9・半角=0.5 | カード必要幅計算式 |
| font-scale | CSS変数 `--font-scale`（既定1.3）。全フォントの一括スケール | CONST_004 |
| 意図的改行 | `<br>` を意味境界に挿入する手動改行。自動折り返しに委ねない | CONST_005 |
| 図解エリア比率 | 図解40%:テキスト50%:gap10% のバランス | 図解サイズ計算 |
| 二系統最適化 | 画面用 rem 指定と印刷用 pt 指定を別個に整備すること | CONST_006 / 換算表 |
| 残余高さ | 面の高さから全ブロックの内容高と gap を引いた余り。ブロックの伸長でなく群の外側余白として残す | CONST_008 |
| 内容高ブロック | カード・帯・ステップを内容の高さで作り、面いっぱいへ引き伸ばさない状態 (`grid-auto-rows: auto` / `flex: 0 0 auto`) | CONST_008 |
| 近接 gap | 群が一塊に見える項目間隔。基準値は `assets/slide-templates/frame-contract.json` の `spacing.gap` から導出し、面ごとに新しい間隔値を発明しない。`space-between`/`space-evenly` は使わない | CONST_008 / `vertical_margin_policy.note_gap` |
| 面の余白率・充填率の正本 | 面の余白と充填の量的基準は `assets/slide-templates/frame-contract.json` の `fill_policy`（面積比）と `vertical_margin_policy`（高さ比）のみが持つ。本ファイルを含む散文へ数値を写さない | CONST_008 / CONST_012 相当の量的正本 |
| 適用系統 | 生成経路の別。**エンジン経路** = `slider-*` を出す render-slide.cjs 経路（`style-builder.cjs` の既定 CSS が効く）/ **ひな形経路** = `data-slide-skeleton` を持つ 22 ひな形（`slide-skeleton.css` が効く）。本ファイルの CSS セレクタはエンジン経路にしか効かない | CONST_008-011 |
| 高さ牽引 | 同一グリッド内の背の高いカード (QR等) に行高が引かれ、内容の少ないカードに空洞ができる現象 | CONST_009 |
| 内部順序の統一 | 同一群の全カードを icon → title → media → desc の同じ並びに揃えること | CONST_009 |
| 読み取り用画像 | QR 等、読者が端末で読み取る前提の画像。図解面積規約 (L4) の対象外 | CONST_010 |
| 浮遊UI | ページ送り等、面の内容と重ならず外周へ固定する操作要素 | CONST_011 |

## 評価基準（ドメイン固有の判定基準）
| 基準 | 条件 |
|------|------|
| 1行収まり | 合格=全タイトルが nowrap で1行に収まる / 不合格=折り返しが残る |
| カード幅均等 | 合格=同一スライド内で同一 min/max-width / 不合格=要素ごとに幅が食い違う |
| フォント下限 | 合格=`1.1rem × var(--font-scale)` 以上 / 不合格=下限を割る縮小 |
| 改行品質 | 合格=`<br>` が句読点・助詞の後・15-20文字境界 / 不合格=単語途中で切れる |
| 非破壊性 | 合格=構造・既存CSS変数定義を保持し追記のみ / 不合格=DOM構造または変数定義を改変 |
| 内容高 | 合格=カード/帯の高さが内容で決まり、余りは群の外側余白 / 不合格=**縦方向の伸長指定**（`grid-auto-rows: 1fr`・`align-content: stretch`・`flex: 1 1 0`）で面いっぱいへ伸長。`grid-template-columns` の `1fr`（列幅指定）と横方向の `align-items: stretch`（カード外形の高さ揃え）は対象外 |
| 群の一体感 | 合格=項目間 gap がブロック高より小さく一塊に見える / 不合格=`space-between`/`space-evenly` で塊が割れる |
| 空洞なし | 合格=高さを牽引されたカードの中身が縦中央で余白が上下均等 / 不合格=中身が上端に張り付き下半分が空く |
| 内部順序 | 合格=同一群の全カードが icon → title → media → desc / 不合格=画像のあるカードだけ icon が欠ける |
| カード内無折り返し | 合格=カード見出し・説明が折り返さない字数 / 不合格=折り返しで隣接カードの media 位置がずれる |
| 横幅の使い切り | 合格=単列の帯が面の横幅を使う / 不合格=文字が左に寄り右半分が空く |
| 浮遊UIの非重畳 | 合格=ページ送りが面の内容・帯と重ならない / 不合格=見出し帯や本文に重なる |

## ビジネスルール
- **CONST_001 (計算式駆動)**: フォントサイズ・カード幅・図解サイズは Layer 5 の計算式で算出した値のみを採用し、感覚値で直接指定しない。
  - 目的: スライド間・カード間のレイアウトを再現可能かつ一貫させる。
  - 背景: 目視調整は同一タイトル長でも結果がばらつき、改行崩れと不統一を招くため決定論的算出に統一する。
- **CONST_002 (同一スライド統一)**: 同一スライド内のカード/ステップは最長タイトルを基準に全要素へ同一フォントサイズ・同一カード幅を適用する。
  - 目的: 並んだカードの高さ・幅・文字サイズを揃え視覚的統一感を出す。
  - 背景: 要素ごとに最適化すると隣接カードでフォントサイズが食い違い不揃いに見えるため。
- **CONST_003 (最小フォント下限)**: フォントサイズは `1.1rem × var(--font-scale)` を下限とし、これを下回る縮小はしない。
  - 目的: 可読性の下限を保証する。
  - 背景: 幅優先で際限なく縮小すると読めなくなるため calculateFontSize で Math.max により下限を担保する。
- **CONST_004 (CSS変数経由・直書き禁止)**: スタイルは `var(--font-scale)` 等の CSS 変数経由で指定し、ピクセル直書きを避ける。
  - 目的: スケール変更時に一括反映できる保守性を確保する。
  - 背景: 直書きはスケール変更時に全箇所修正が必要になり破綻しやすいため。
- **CONST_005 (意味境界改行)**: 説明文の改行は `<br>` を句読点・助詞の後・15-20文字単位の意味境界に入れ、自動折り返しに委ねない。
  - 目的: 単語途中での折り返しを防ぎ可読性を保つ。
  - 背景: 自動改行は「プロンプト」のような語を途中で切り読みにくくするため。
- **CONST_006 (画面・印刷の二系統最適化)**: 画面用 rem 指定と印刷用 pt 指定を Layer 5 換算表に基づき別個に整備する。
  - 目的: 画面と印刷で同等のレイアウトを維持する。
  - 背景: rem と pt は媒体で見え方が異なり、片方のみ最適化すると印刷で崩れるため。
- **CONST_007 (非破壊上書き)**: 最適化はスライド固有 CSS の追記で行い、html-generator が生成した構造・既存 CSS 変数定義を破壊しない。
  - 目的: 後続レンダリングと他エージェント成果物との整合を保つ。
  - 背景: 構造改変は slide-renderer や ui-quality-reviewer の前提を崩すため最小差分で上書きする。
  - 書き先（エンジン経路）: 補正 CSS は出力先の **`custom.css`** へ書く。`render-slide.cjs` は `styles.css` と `index.html` を毎回全文再生成するので `styles.css` への追記は次の render で必ず消え、逃げ場が `index.html` の inline `<style>` になって `ui-quality-checklist.md` S1（index.html に `<style>` 0 件）を構造的に破る。`custom.css` が出力先に在るときだけ `render-slide.cjs` が `styles.css` の直後へ `<link>` を繋ぎ（後勝ち）、`custom.css` 自体は生成も上書きもしない。無ければ `<link>` も出ない。
> **CONST_008-011 を読む前に必ず行うこと（適用系統の判別）**: これらの規則の CSS は**エンジン経路（`slider-*`）にしか効かない**。対象の成果物が `data-slide-skeleton` 属性を持つ**ひな形経路**なら、本ファイルの CSS セレクタ（`.slide-grid` / `.slide-list` / `.slide-timeline` 等）は一切当たらないので、`slide-skeleton.css` 側で直す。どちらの系統かを最初に判別し、判別結果を最適化レポートへ記録する。

- **CONST_008 (内容高ブロック・残余は外側余白)**: カード・帯・ステップは内容の高さで作り、面いっぱいへ引き伸ばさない。残余高さは群の外側余白として残し、項目間は近接 gap に固定する。量的な基準値（充填率・外側余白率・gap）は `assets/slide-templates/frame-contract.json` の `fill_policy` / `vertical_margin_policy` を唯一の正本とし、本ファイルへ写さない。
  - やさしい要約: 中身が少ない箱を無理に引き伸ばして面を埋めない、という決まりです。余った高さは箱の中でなく、箱の集まりの外側（上下）へ残します。項目どうしの間隔は決まった値に固定して、ひとかたまりに見えるようにします。
  - 適用系統: エンジン経路（`slider-*`）。ひな形経路は別系統（下記背景 (a)）。
  - 目的: 面を埋めることでなく読ませることを優先し、ブロック高を内容量に対応させる。
  - 背景: 空白と伸長の症状は**経路ごとに逆向き**に出るため、分けて捉える。
    - (a) ひな形経路: `assets/slide-templates/slide-skeleton.css` の `.srg-slide__main { flex: 1 1 auto }`（コメント「空白過多の構造的な封じ手」）が main を面いっぱいへ伸長させる。伸長は既定として意図されたものなので、問題になるのは main の**中の**スロットまで連鎖して伸びる場合であり、中の項目側を内容高へ戻して直す。
    - (b) エンジン経路: `vendor/scripts/style-builder.cjs` の既定に**縦方向の伸長指定は無い**（`.flow-step { flex: 1 }` は `.flow-container` が row flex なので横方向の伸長）。かつて既定の `.slider__content` は `justify-content` 未指定＝`flex-start` で、残余が必ず下側へ偏り `vertical_margin_policy.max_symmetry_delta` を規約内の手段では満たせなかったため、2026-08-13 に `justify-content: center` を既定へ入れた（配置であって伸長ではなく、内容高も充填率も動かない）。ここへ `grid-auto-rows: 1fr` / `align-content: stretch` / `flex: 1 1 0` を足すと今度は短い内容まで引き伸ばされ「画面いっぱいで逆に見にくい」状態になる。残余を項目間へ配る `space-between` / `space-evenly` も、gap がブロック高を超えると群が割れて別々の要素に見えるため使わない（上限は `vertical_margin_policy.max_proximity_gap_ratio`）。
- **CONST_009 (高さ牽引時の縦中央寄せ・内部順序の統一)**: 同一群内に背の高いカード (読み取り用画像を含む等) がある面では、内容の少ないカードの中身を縦中央に置き、全カードを icon → title → media → desc の同一順序に揃える。
  - やさしい要約: 横に並ぶカードは一番背の高いものに高さが揃います。そのとき中身を上に寄せると下半分が空洞に見えるので、中身は縦の真ん中へ置きます。並び順も全カードで揃えます。
  - 適用系統: エンジン経路（`slider-*`）。
  - 目的: 高さが揃った群の中でも視線の当たる位置を揃え、空洞と欠落を作らない。
  - 背景: 高さは行で揃うため、中身を上端に寄せるとカード下半分が空洞になる。またレンダラは `image` があると `icon` を省略することがあり、画像付きカードだけ先頭要素が欠けて横並びの律動が崩れる。
- **CONST_010 (読み取り用画像の寸法と図解面積の除外)**: QR 等の読み取り用画像は面高に対する比で上限寸法を決め（基準は `frame-contract.json` の `stage.height`。`vh` は使わない）、図解面積規約 (`validate-slide-layout.js` の L4) の対象外として扱う。下限値そのものは L4 が持つので、ここには書き写さない。
  - やさしい要約: QR コードは大きすぎても小さすぎても困るので、面の高さに対する割合で上限を決めます。読み取り用なので「図解の面積が足りない」という指摘の対象からは外します。
  - 適用系統: エンジン経路（`slider-*`）。
  - 目的: 端末で読み取れる下限を満たしつつ、面を占有する過大な QR を避ける。
  - 背景: QR は読ませる図解ではなく読み取り対象であり、L4 の下限を満たすには面を支配する寸法が必要になる。L4 warning は本規約に従う限り受容し、逸脱理由を評価レポートへ明示する。`vh` を上限に使うと `@media print` で基準が用紙高へ変わり、画面と印刷で寸法が食い違う（CONST_006 違反）。
- **CONST_011 (浮遊UIの配置はエンジン既定に従う・動かすなら予約帯を先に広げる)**: ページ送り等の浮遊UIは**エンジンが既に `position: fixed` で右下へ集約している**（`vendor/assets/pagination.css`）。この配置は変更しない。配置変更が必要な場合に限り、先に `style-builder.cjs` の `--pg-reserve-side` / `--pg-reserve-bottom` を移動先の辺（左へ出すなら左右両側）へ拡張し、予約帯を確保してから動かす。
  - やさしい要約: ページ送りボタンの位置は、すでにエンジン側で本文と重ならないよう右下に決まっています。勝手に動かすと本文に重なる事故が起きます。どうしても動かすときは、先に「ここは空けておく」という余白の予約を広げてから動かします。
  - 適用系統: エンジン経路（`slider-*`）。予約帯変数は `style-builder.cjs` が出力する。
  - 目的: 操作要素が本文・見出し帯を覆う事故（1440x900 で送りボタンと図解が重なった実測）を再発させない。
  - 背景: `pagination.css` のボタンは既に `position: fixed` で右下に集約されており、`style-builder.cjs` の `--pg-reserve-side` / `--pg-reserve-bottom` はその**集約を前提に**本文側の予約帯を算出している。ここでボタンを左右へ分離すると、**左側には予約帯が無いため prev ボタンが本文へ重なり**、L1（帯×コンテンツ重なり = error）を新たに踏む。過去に置かれていた `left` / `right` へ分離する CSS 例は誤りとして削除した。

## レイアウト計算式（核心仕様・保持必須）

### 文字数カウント計算式

全角=1・半角=0.5 で各タイトル・説明文の文字数を算出する（混在テキストでも実幅に近い文字数を得る）。

```javascript
// 文字数カウント（全角=1、半角=0.5として計算）
function countChars(text) {
  let count = 0;
  for (const char of text) {
    count += /[^\x00-\x7F]/.test(char) ? 1 : 0.5;
  }
  return Math.ceil(count);
}
```

### カードサイズ計算式

```
カード必要幅 = (最長タイトル文字数 × 平均文字幅係数 × フォントサイズ) + (左右パディング × 2)
```

計算パラメータ:

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| 全角文字幅係数 | 0.9 | フォントサイズの90% |
| 半角文字幅係数 | 0.5 | フォントサイズの50% |
| 左右パディング | 1.2rem | カード内の余白 |
| カード間gap | 1.0-1.5rem | カード間の間隔 |
| font-scale | 1.3 | CSS変数で定義 |

計算例（14文字タイトル）:

```
タイトル: "プロンプトを作るプロンプト" (14文字)
フォントサイズ: 1.2rem × 1.3 (scale) = 1.56rem ≈ 25px
パディング: 1.2rem × 2 × 16 = 38.4px

必要テキスト幅 = 14文字 × 0.9 × 25px ≈ 315px
カード必要幅 = 315px + 38.4px ≈ 354px

→ min-width: 340px, max-width: 400px が適切
```

### フォントサイズ決定アルゴリズム

制約条件:
1. 利用可能幅 = (コンテナ幅 - gap × (カード数-1)) ÷ カード数
2. タイトルは1行に収める（white-space: nowrap）
3. フォントサイズは最小 1.1rem × scale 以上

```javascript
// 計算ロジック
function calculateFontSize(charCount, availableWidth, padding) {
  const textAreaWidth = availableWidth - (padding * 2);
  const charWidth = 0.9; // 全角係数
  const fontScale = 1.3;

  // 必要フォントサイズ（rem単位）
  const requiredFontPx = textAreaWidth / (charCount * charWidth);
  const requiredFontRem = requiredFontPx / 16 / fontScale;

  // 最小値チェック（1.1rem以上）
  return Math.max(requiredFontRem, 1.1);
}
```

逆算アプローチ（推奨）:

```
利用可能コンテナ幅: 1400px
3カラムの場合のカード幅: (1400 - 1.2rem×2 × 16) ÷ 3 ≈ 454px
テキスト領域: 454 - 38.4 ≈ 416px

14文字を収めるには:
フォントサイズ = 416 ÷ (14 × 0.9) = 33px ≈ 2.06rem
scale除算: 2.06 ÷ 1.3 ≈ 1.58rem

→ font-size: calc(1.5rem * var(--font-scale)) で余裕あり
```

### 図解サイズの計算

サイクル図などの図解はテキストとのバランスで決定する:

```
図解エリア比率 = 40%
テキストエリア比率 = 50%
gap比率 = 10%

例: 総幅 1000px の場合
- 図解: 400px
- gap: 100px
- テキスト: 500px
```

ノードサイズ計算:

```
ノード直径 = 図解幅 × 0.28
中心円直径 = 図解幅 × 0.33
ノード内フォント = ノード直径 ÷ 文字数 × 0.7（最小 0.7rem）
```

### 同一スライド内の統一計算

```javascript
// 計算ロジック
const titles = cards.map(c => c.title);
const maxLength = Math.max(...titles.map(t => countChars(t)));
const fontSize = calculateFontSize(maxLength, cardWidth, padding);
// 全カードに同じフォントサイズを適用
```

余白バランス:

```css
/* カード内余白の比率: 縦:横 = 1.2:1 */
padding: 1.5rem 1.2rem; /* 縦24px : 横19.2px */
```

### 縦方向の配分（面の高さの使い方・CONST_008）

やさしい要約: 縦方向は「箱は中身の高さで作る」「箱の集まりは面の縦の真ん中へ置く」「余った高さは集まりの外側（上下）へ均等に残す」の 3 段で決めます。以下の CSS は**参考実装**で、数値そのものは `frame-contract.json` が持ちます。

横方向（文字数→幅→フォントサイズ）とは別系統として、縦方向は**内容高で作り・群を中央へ・残余は外側余白**の 3 段で決める。`data-slide="N"` のような**面固有セレクタで書かない**（deck ごとに書き直しが要り再現性が落ちる）。タイプ共通のセレクタへ 1 度だけ書く。

適用系統: 以下のセレクタは**エンジン経路（`slider-*`）専用**。ひな形経路（`data-slide-skeleton`・22 ひな形）には効かないので、先に系統を判別する。

```
面の内容高 H = Σ(ブロック内容高) + gap × (ブロック数 - 1)
残余 R = 面の利用可能高 - H
配分規則: R はすべて群の外側余白（上下均等）へ回す。ブロックへ配らない。
gap     = frame-contract.json の spacing.gap から導出したトークン（--space-* / --srg-gap）
基準値  = frame-contract.json の vertical_margin_policy
          （外側余白率の下限・上限、上下対称の許容差、gap とブロック高の比の上限）
充填率  = frame-contract.json の fill_policy（面種別の例外を含む）
```

gap に `vh` を使わない。`@media print` で `vh` の基準が用紙高へ変わり、画面と印刷で間隔が食い違う（CONST_006 違反）。印刷を伴う面では `spacing.gap` 由来のトークンを mm / rem / vw へ換算して用いる（換算率は `frame-contract.json` の `print.mm_per_px` / `print.zoom_factor`）。

参考実装（エンジン経路）:

```css
/* 共通: コンテナは面の残余を受け取るが、ブロックは内容高で作る */
.slide-grid .grid-container,
.slide-list .list,
.slide-timeline .timeline,
.slide-process .process-container,
.slide-icon-grid .ig-container { flex: 1 1 auto; min-height: 0; }

/* grid 系（grid-container / ig-container）: 行を内容高にし、群ごと縦中央へ置く */
.slide-grid .grid-container,
.slide-icon-grid .ig-container {
  grid-auto-rows: auto;          /* NG: 1fr（面いっぱいへ伸長する） */
  align-content: center;         /* NG: stretch / space-between / space-evenly */
  row-gap: var(--space-3);       /* spacing.gap 由来のトークン。vh を使わない */
}
/* grid 項目の中身を縦中央へ。既定が column flex の .grid-cell はそのまま指定でき、
   既定がブロックの .ig-item は先に column flex にしてから指定する */
.slide-grid .grid-cell { justify-content: center; }
.slide-icon-grid .ig-item { display: flex; flex-direction: column; justify-content: center; }

/* flex 系（list / timeline / process）: 項目は伸ばさず、群を縦中央へ */
.slide-list .list,
.slide-timeline .timeline,
.slide-process .process-container {
  display: flex; flex-direction: column;
  justify-content: center;
  gap: var(--space-3);           /* 同上 */
}
.slide-list .list-item,
.slide-timeline .timeline-item,
.slide-process .process-item { flex: 0 0 auto; }
/* 中身の縦中央寄せは、その項目が column flex のときだけ justify-content で効く
   （.list-item は既定で column flex）。NG: align-content —— これらは flex-wrap の
   無い単一行 column なので align-content は無視され、意図が出ない。
   .process-item は既定が row flex + align-items: center で既に縦中央のため追加指定は不要 */
.slide-list .list-item { justify-content: center; }

/* timeline は既定で .timeline-item { padding-bottom: var(--space-4) } を持つ。
   上の gap と加算されて実効間隔が規定から外れるため、縦方向指定と併せて 0 に戻す */
.slide-timeline .timeline-item { padding-bottom: 0; }
```

row 系（`.slide-compare .compare-container` / `.slide-flow .flow-container`）は横方向に項目を並べる系統であり、**本節（縦方向配分）の対象外**。`.flow-step { flex: 1 }` の伸長は横方向なので、縦方向の伸長禁止に抵触しない。

判定: ブロック高が内容量に比例していること・項目間 gap がブロック高より小さいこと（上限は `vertical_margin_policy.max_proximity_gap_ratio`）・面の上下に等しい余白が残っていること（許容差は `max_symmetry_delta`）。1 つでも崩れていれば**縦方向の伸長指定**（`grid-auto-rows: 1fr` / `align-content: stretch` / `flex: 1 1 0` / column flex 上の `justify-content: space-between|space-evenly`）の残存を疑う。`grid-template-columns` の `1fr`・`--space-*` 変数・横方向の `align-items: stretch` は正当なので誤検出しない。

#### 情報量と余白の 4 象限（どちらへ外れたときも「伸ばす・詰める」で解かない）

| 情報量 | 余白 | 症状 | 正しい直し方 | 禁止 |
|-------|-----|------|------------|------|
| 少 | 多 | 外側余白率が `vertical_margin_policy.max_outer_margin_ratio` を超える／充填率が `fill_policy.min_stage_fill_ratio` を割る | **面を統合する**か**項目を足す** | ブロックを伸ばして埋める（`flex: 1 1 0` / `grid-auto-rows: 1fr` / `align-content: stretch`）。面積比だけ稼いで中身は空のまま |
| 多 | 少 | 充填率が `fill_policy.max_stage_fill_ratio` を超える／外側余白率が `min_outer_margin_ratio` を割る | **面を割る**か**項目を減らす** | 書体を `typography.min` 未満へ下げて詰める（CONST_003 の下限とも衝突） |
| 少 | 適正 | — | 変更不要 | — |
| 多 | 適正 | — | 変更不要 | — |

面種別に例外レンジがある（表紙・章扉・引用・数値強調・表・コード・全面画像）。レンジの正本は `fill_policy.exceptions` で、面種別を宣言したうえで逸脱理由を評価レポートへ残す。

### 高さ牽引がある群の内部配置（CONST_009）

やさしい要約: 背の高いカードが 1 枚あると、横に並ぶ他のカードも同じ高さになります。そのままだと中身が少ないカードの下半分が空洞に見えるので、そのカードだけ中身を縦の真ん中へ置きます。

同一グリッドに背の高いカード（読み取り用画像・図・長文）が混ざると行高がそれに引かれる。引かれた側は**中身を縦中央**に置き、全カードの**内部順序を統一**する。適用系統はエンジン経路（`slider-*`）。

参考実装（`:has()` は「その要素を含むカードだけ」を選ぶための記法）:

```css
/* 背の高いカードを含む群: 行は内容高、カード内は上詰め（媒体の位置を揃える） */
.slide-grid .grid-container:has(.qr-img) { grid-auto-rows: auto; align-content: center; align-items: stretch; }
.slide-grid .grid-container:has(.qr-img) .grid-cell { justify-content: flex-start; gap: 0.8rem; }
/* 背の高い要素を持たないカードだけ縦中央にして空洞を作らない */
.slide-grid .grid-container:has(.qr-img) .grid-cell:not(:has(.qr-img)) { justify-content: center; }
```

内部順序は `icon → title → media → desc` に固定する。レンダラが `image` 指定時に `icon` を落とす場合は、生成後に icon 要素を補って先頭要素を揃える（構造は保つ・CONST_007）。カード見出しと説明は**折り返さない字数**へ収める（折り返すと媒体の縦位置が隣接カードとずれる）。収まらなければ文言を短くするか、当該群のみ `--fs-subheading × 0.94` まで下げる（下限は CONST_003）。

参考実装（CONST_010・上限は面高 `frame-contract.json` の `stage.height` に対する比で置く。`vh` は `@media print` で基準が用紙高へ変わるため使わない）:

```css
/* 画面用: 面高に対する比。--stage-h は stage.height を持つトークン */
.grid-cell .qr-img { width: min(100%, calc(var(--stage-h) * var(--qr-max-ratio))); margin: 0.2rem auto; }

@media print {
  /* 印刷用: 同じ比を mm へ換算して置く（換算率は print.mm_per_px / print.zoom_factor）*/
  .grid-cell .qr-img { width: min(100%, calc(var(--stage-h-mm) * var(--qr-max-ratio))); }
}
```

読み取り用画像を含む面は L4（図解面積の下限割れ）warning が残るが、CONST_010 に従う限り受容し、逸脱理由を評価レポートへ残す（面を支配する QR は不可）。

### 単列ブロックの横幅（帯化）

単列で並ぶ timeline / step は、文字だけ置くと左に寄って右半分が空く。**帯**にして横幅を使い切る。連番は擬似要素・カウンタで描くため、`<ol>` のマーカーは消す（二重表示になる）。

```css
.slide-timeline .timeline { list-style: none; }
.slide-timeline .timeline-item {
  background: rgba(59,125,216,0.06);
  border-radius: 0.6vw;
  box-shadow: var(--shadow-subtle);
  padding: var(--space-2) var(--space-4);
}
```

### 背景画像を敷く面の左右余白

`has-ai-bg` の生成画像は右端まで寄せると切れて見える。**左本文の余白と同幅の右余白**を残し、本文側の `padding-right` を画像幅＋余白に合わせる。

```css
.slider__item.has-ai-bg .ai-bg { background-position: right 5.5% center; background-size: 45% auto; }
.slider__item.has-ai-bg .slider__content { padding-right: 52%; }
```

### 浮遊UI（ページ送り）の置き方（CONST_011）

やさしい要約: ページ送りボタンの位置は**エンジン側で既に決まっている**ので、レイアウト最適化では触りません。触ると本文に重なる事故が起きます。

エンジン（`vendor/assets/pagination.css`）は既にボタンを `position: fixed` で**右下へ集約**しており、`vendor/scripts/style-builder.cjs` の `--pg-reserve-side` / `--pg-reserve-bottom` はその集約前提で本文側の予約帯（padding）を算出している。したがって **layout-optimizer は浮遊UIの配置を変更しない**。

配置変更が必要な場合に限り、次の順で行う。

1. `--pg-reserve-side` を移動先の辺へ拡張する（左へ出すなら左右両側に予約帯を確保する）。
2. 予約帯が本文へ効いていることを描画で確認する。
3. その後にボタンを動かす。

過去に置かれていた「ラッパを `display: contents` にし、子を `left` / `right` で左右端へ分離する」CSS 例は**誤りとして削除した**。左側には予約帯が無いため、prev ボタンが本文へ重なり L1（帯×コンテンツ重なり = error）を新たに踏む。

### 本文フォントの底上げ（縦に余裕が出た面）

内容高ブロック化で余白が増えた面は、本文が相対的に小さく見える。カード説明・リスト説明は**既存トークン `--fs-body-lg`**（`style-builder.cjs` の既定スケール）へ上げてよい（上げても 1 行に収まる範囲・CONST_002 の同一スライド統一を保つ）。新しい倍率を発明しない（`--fs-body` へ任意の係数を掛けると、根拠の無い値が deck ごとに散る）。

```css
.slide-grid .grid-cell-desc,
.slide-list .list-desc { font-size: var(--fs-body-lg); line-height: 1.5; }
```

## 意図的改行の仕様

自動改行は単語の途中で切れて読みにくくなるため、`<br>` で意味のまとまりで改行する。

```
【NG】講義ではなく、実際にAIを使いながらプ
ロンプト作成を体験

→「プロンプト」が途中で切れている
```

```html
<span>講義ではなく、<br>実際にAIを使いながら<br>プロンプト作成を体験</span>
```

改行位置の原則:
1. **句読点の後**: 「〜ではなく、」
2. **助詞の後**: 「AIを使いながら」
3. **15-20文字ごと**: 長い文の場合

適用対象:
- `.list-item span`: リストカードの説明文
- `.flow-step span`: フローステップの説明文
- `.compare-item li`: 比較リストの項目
- `.diagram-text li`: 図解スライドのリスト項目

スライドタイプ別の適用例:

```html
<!-- リストスライド -->
<span>講義ではなく、<br>実際にAIを使いながら<br>プロンプト作成を体験</span>
```

```html
<!-- フロースライド -->
<span>AI基礎と<br>初めてのプロンプト</span>
<span>プロンプト設計<br>パターンを学ぶ</span>
```

```html
<!-- 図解スライド -->
<li>AIと効果的に<br>対話する方法</li>
<li>目的に合わせた<br>プロンプト構造</li>
```

## 印刷時の最適化（画面用 → 印刷用 換算）

画面用 CSS と印刷用 CSS は別々に最適化する。

| 画面用(rem × scale) | 印刷用(pt) |
|--------------------|-----------|
| calc(1.6rem × 1.3) = 2.08rem ≈ 33px | 14pt |
| calc(1.4rem × 1.3) = 1.82rem ≈ 29px | 12pt |
| calc(1.2rem × 1.3) = 1.56rem ≈ 25px | 11pt |
| calc(1.1rem × 1.3) = 1.43rem ≈ 23px | 10pt |

印刷用 CSS 追加例:

```css
@media print {
  .slide-list .list-item h4 {
    font-size: 11pt !important; /* 長いタイトル対応 */
    white-space: nowrap !important;
  }
}
```
