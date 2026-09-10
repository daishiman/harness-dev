# 参照 HTML 解析: 配布用シングル HTML 資料 (handout) の型

対象: `/Users/dm/Downloads/guide (1) (1).html`
（base64 を除去した本文のみの写しを `reference-guide-stripped.html` に保存。原本は 5,364,417 chars）

## 0. 数量事実 (fact)

| 項目 | 値 |
|---|---|
| 原本サイズ | 5,364,417 chars (5.12 MiB) |
| data URI 数 | 3 (xlsx ×2 / zip ×1) |
| data URI 合計 | 5,319,184 chars (**全体の 99.16%**) |
| 本文（base64 除去後） | 45,447 chars |
| `<style>` ブロック | 1 (約 250 行・CSS 変数駆動) |
| `<script>` ブロック | 3 (UI 挙動 / data URI ダウンロード / アンカースクロール) |
| 外部依存 (CDN・font・img src) | **0**（完全自己完結） |
| `<section>` | 8 (hero 直下の「今日の流れ」+ 番号付き 7 セクション) |

**本質**: 「1 ファイルで完結し、そのままデプロイでき、Notion 埋め込みでも壊れない」を成立させている核心は、
外部参照を一切持たず、添付ファイルすら base64 data URI として本文に内包している点にある。

## 1. 全体構造 (骨格)

```
<header class="pop-header">   position: sticky; top:0  ← 常時表示インデックス
  .head-top   : タイトル + 日付ピル
  nav.navbar  : #s1..#s7 へのアンカーチップ (横スクロール可)
<main class="pop">            max-width: 860px の 1 カラム LP
  .pop-hero                   : h1 + リード文 + ゴールチップ群
  section.pop-card            : 「今日の流れ」(アジェンダ・所要時間つき)
  section.pop-card#s1 .. #s7  : 本体セクション (id がナビのアンカー)
<div class="pop-bottom">      : SVG wave + フッター
```

- 全セクションカードに `scroll-margin-top: 96px` が入っており、sticky header にタイトルが隠れない。
- さらに JS 側でも `header.getBoundingClientRect().height + 12` を実測してオフセットスクロールしており、**CSS と JS の二重防御**。

## 2. 部品カタログ (テンプレート化すべき型) — 12 種

| # | 部品 | クラス | 役割 | 主要な仕掛け |
|---|---|---|---|---|
| B01 | sticky ナビ | `.pop-header` / `.navbar a` | 常時表示インデックス | sticky + backdrop-filter + アンカー |
| B02 | ヒーロー | `.pop-hero` / `.goal-chip` | 主題1文 + 到達ゴールの明示 | `text-wrap: balance`, 波線下線 `.squiggle` |
| B03 | ステップ行 | `.step-row` / `.step-num` / `.s-time` | 手順・アジェンダ（所要時間つき） | 連番バッジ + 右端に時間ピル |
| B04 | トリオカード | `.trio` / `.trio-card.today\|rest` | 3 者の役割比較（今日触る/触らない） | 状態でトーン差 |
| B05 | 比較表 | `.table-wrap` / `table` | 軸 × 対象の網羅比較 | `overflow-x` + `scope` 属性 + `.hl-cell` 強調 |
| B06 | 二択グリッド | `.vs-grid` / `.vs-col.chat\|cowork` | 「A ならこっち / B ならこっち」 | 左右で色分け・箇条書き |
| B07 | 特徴カード | `.pop-features` / `.duo` / `.pop-feature` | 概念を 2〜3 枚で並置 | 破線ボーダー（軽い印象） |
| B08 | 選択マップ | `.map-grid .map-item` + `.map-detail` | 選択肢の一覧 → 押すと解説差替 | `aria-pressed` トグル + `data-title`/`data-detail` |
| B09 | チェック行 | `.pop-row input[type=checkbox]` | ハンズオン課題・宿題 | `appearance:none` の自作チェック + 進捗カウンタ |
| B10 | アコーディオン | `details.acc` / `summary` | 詳細を折りたたむ | `::before` の +/- 記号、ネイティブ `<details>` |
| B11 | プロンプト箱 | `.prompt-box` + `.copy-btn` + `<pre>` | コピーして使う文例 | `navigator.clipboard` + Range 選択フォールバック |
| B12 | DL ボタン | `.dl-btn[download][href="data:..."]` | 添付ファイル配布 | data URI → Blob 変換して保存 |
| B13 | タブ | `[role=tablist] .tab` + `.prompt-panel` | 出力形式別のプロンプト集 | `aria-selected` + `panel.hidden` |
| B14 | フロー | `.flow` / `.flow-step` / `.flow-arrow` | 2〜3 段の流れ | インライン SVG 矢印・モバイルは回転 |
| B15 | 選択チップ | `.pop-chips[data-single] .pop-chip` | その場で日程を決める | 単一選択トグル |

## 3. デザイントークン (CSS 変数)

```css
--pop-primary:#43a4f5  --pop-primary-pastel:#8ecdf8  --pop-primary-soft:#d9edfe
--pop-primary-deep:#2273b8  --pop-bg:#eaf5fe
--ink:#16191d  --ink-muted:#545e6b  --line:#e3e6ea  --subtle:#f5f6f8
--card-radius:24px  --font-num: Helvetica Neue 系（tabular-nums）
```

- **アクセント 1 色 + 4 段階の明度**のみで全体を構成。色数を絞ることが「初心者にうるさく見えない」効果を出している。
- `font-feature-settings:"palt"` で日本語の字詰めを詰めている。
- 数値は `.num` クラスで `tabular-nums` + `letter-spacing:-0.015em`（桁ズレ防止）。

## 4. アクセシビリティ / 堅牢性の作法（引き継ぐ価値が高い）

- `aria-pressed` / `aria-selected` / `aria-label` / `scope="col|row"` / `aria-hidden="true"`（装飾 SVG）
- `:focus-visible` に統一 outline
- `@media (prefers-reduced-motion: reduce)` で `scroll-behavior` と transition を無効化（2 箇所以上）
- clipboard API 失敗時に Range 選択へフォールバック
- data URI ダウンロードが効かない場合の代替手段を `.dl-hint` で明記
- JS は `'use strict'` + 素の DOM API のみ（フレームワーク・CDN ゼロ）

## 5. 文章設計の型（抽象 → 具体の往復）

観測される順序パターン:

1. **ヒーローで一文の主題**（「今日は、Claude に触って慣れる日。」）＋ 到達ゴールをチップで列挙
2. **アジェンダで全体像と所要時間**（読み手が残量を把握できる）
3. 各セクションは `section-label`（番号 + 見出し + 所要時間）→ `lead-line`（1 行の抽象）→ 具体部品
4. **抽象の提示 → 具体例 → 判断軸の一文**（例: セクション3 で出力形式を並べた直後に「形をえらぶ質問はひとつ。『誰が見て、次に何につながる？』」）
5. 専門用語は必ず言い換えを併記（「コネクタ ＝ 外とつながる」「スキル ＝ やり方を覚える」）
6. 一文が短い。`f-sub` / `s-sub` は概ね 20〜45 字。

## 6. 現行版に無く、今回追加が要るもの (gap)

| gap | 内容 |
|---|---|
| G1 | 図解 SVG が装飾用（波・矢印）のみ。**概念図解が存在しない** |
| G2 | 画像（スクリーンショット / イラスト）が 1 枚も無い。埋め込み機構も無い |
| G3 | 画像クリックでの拡大（lightbox）が無い |
| G4 | **会議中メモ機構が無い**（チェックボックス状態も含め、リロードで消える） |
| G5 | 状態の永続化（localStorage）が無い |
| G6 | 印刷レイアウトの考慮が無い |
| G7 | テンプレート化されておらず、内容がハードコード（使い回し不可） |

## 7. 継承する設計原則（結論）

1. **1 ファイル自己完結・外部依存ゼロ**（デプロイ・Notion 埋め込み・オフライン閲覧のすべてを同時に満たす唯一の条件）
2. **sticky インデックス + アンカー**（LP スクロールと目次ジャンプの両立）
3. **素の DOM API のみ**（ビルド工程を持たず、生成された HTML がそのまま最終成果物）
4. **アクセシビリティ属性を最初から焼く**
5. **アクセント 1 色 + 明度 4 段階**
6. **抽象 1 行 → 具体部品 → 判断軸 1 行**の反復
7. **専門用語には必ず括弧書きの言い換え**

---

# 参照 HTML v2 解析: デザイン言語の正本

対象: `/Users/dm/Downloads/Claude活用ガイド v2 (1).html`（写し: `reference-guide-v2.html`）

## 8. v2 の数量事実

| 項目 | 値 |
|---|---|
| 総サイズ | 30,586 chars（添付なし版） |
| data URI | **0**（v1 と違い添付を持たない） |
| 外部参照 (http/https) | **0** |
| **絵文字の使用数** | **0**（実測。装飾は全て inline SVG） |
| `<svg>` 要素 | 8（うち 1 つは `width=0 height=0` の定義専用） |
| `<symbol>` / `<use>` | 2 / 5（マスコットの定義 1 回・参照 3 回 + 内部 use 2） |
| `<section>` | 9 |

冒頭コメントに **`jp-web-design モードB「Pop・親しみ」準拠`** と明記。デザイン規範の出所が特定できる。
（`jp-web-design` は `~/.claude/skills/jp-web-design` にあるユーザーグローバル資産。**本リポジトリには同梱されていない**ため、
新プラグインは規範を参照しつつトークンとマスコットを自前 `assets/` へ vendoring して自己完結させる。）

## 9. v1 → v2 の差分（v2 で獲得された型）

| # | v2 の追加要素 | 実装 | 継承する理由 |
|---|---|---|---|
| D1 | **SVG マスコット** | `<svg width=0 height=0>` の `<defs>` に `<symbol id="mascot-bordered\|plain">` を 1 回定義し、`<use href="#...">` で header / hero / footer から参照 | 1 ファイル内で図版を使い回す正攻法。バイト数が参照回数に比例しない |
| D2 | **CSS 変数による SVG 再着色** | `--body-main` / `--border-mid` / `--pupil-dark` 等 11 個のトークンを `fill="var(--body-main)"` で参照 | テーマ差し替えだけでマスコットの色が追従する。テンプレート化の要 |
| D3 | **`rise-in` スタガー入場** | `@keyframes rise-in` + `animation-delay: var(--stagger, 0ms)` を各カードへ `style="--stagger: 120ms"` でインライン付与 | **JS 不要**でセクション順に遅延が付く。セクション追加＝属性 1 個追加で済む |
| D4 | **アイコンは全て inline SVG stroke** | `stroke="currentColor"` `stroke-width="2.2〜2.6"` `stroke-linecap="round"` `fill="none"` の統一様式 + `aria-hidden="true"` | 絵文字はフォント依存で機種差・トーン差が出る。SVG なら色・太さ・サイズが完全に制御でき、印刷でも崩れない |
| D5 | `.unit` クラス | 単位を `font-size:62%` で従属表示 | 数値の主役性を保つ |
| D6 | `data-mode="pop"` を `<html>` に付与 | モード切替の予約 | 将来のテーマ追加の受け皿 |
| D7 | `.hand-note` | 手書き風の矢印 SVG + 一言 | 「うまく話せなくても大丈夫」といった心理的ハードルを下げる語りかけ |

## 10. アイコン規約（確定事項・ユーザー明示要求）

**絵文字を使わない。アイコンは必ず inline SVG を使う。**

参照 v2 から抽出した統一様式:

```html
<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
     stroke="currentColor" stroke-width="2.2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="..."/>
</svg>
```

- `viewBox="0 0 24 24"` に統一（サイズは width/height だけで変える）
- `stroke="currentColor"` — 親の文字色に追従させ、色指定を CSS 側へ一元化
- `stroke-width` 2.2〜2.6（Pop モードの「太く丸く」に合わせる）
- 装飾用途は `aria-hidden="true"`、意味を持つ場合のみ `<title>` を入れる
- **アイコンセットは `<symbol>` として一括定義し `<use>` 参照**（マスコットと同じ機構）
- 出力 HTML には**使用したアイコンだけ**を埋め込む（未使用シンボルを出さない）

## 11. v1 と v2 の統合方針

- **骨格・部品カタログ・添付埋め込み（B01〜B15, §2）は v1** を正本とする（v1 の方が部品が豊富: tabs / copy-btn / details / dl-btn / table を持つ）
- **デザイン言語・アイコン規約・マスコット・入場アニメ（D1〜D7, §9-10）は v2** を正本とする
- v1 の sticky navbar（常時表示インデックス）は v2 に無いが、ユーザー要求の中核なので **v1 を採用**
- 追加すべき gap（§6 G1〜G7: 概念図解 SVG / 画像埋め込み / lightbox / 会議メモ / localStorage 永続化 / 印刷 / テンプレート化）は両版とも未実装 = 新規構築範囲

## 12. 1 要素あたりの文字数の実測 (v2 別版・2026-08-18)

対象: `/Users/dm/Downloads/Claude活用ガイド v2 (2).html` (35,256 bytes)。
利用者の指摘「図解やカードの 1 つ 1 つの文章が長すぎて理解しづらい」「長い文章だけで
表現されると読みにくい」に対して、参照資料が実際に守っている長さを実測した。

### 12.1 全テキストノード

| 項目 | 値 |
|---|---|
| テキストノード数 | 134 |
| 中央値 | 11 文字 |
| 平均 | 15.3 文字 |
| 90 パーセンタイル | 32 文字 |
| 95 パーセンタイル | 42 文字 |
| 最大 | 77 文字 (定例日程の事実列挙 1 件) |

### 12.2 役割別

| 役割 | 該当 class | n | 中央値 | 最大 | 例 |
|---|---|---|---|---|---|
| 札 (label) | `m-cat` `t-tag` `fl-tag` `t-role` `p-label` `section-label` | 19 | 6 | 13 | 「いちばん手軽」「一目で伝える」 |
| 要点 (title) | `m-title` `f-title` `s-title` `pr-title` `t-name` `v-head` `fl-main` | 31 | 9 | 33 | 「フォルダごと任せられる」「操作を録画→覚える」 |
| 補足 (caption) | `f-sub` `s-sub` `pr-sub` `t-sub` `sched-note` | 21 | 30 | 77 | 「中のファイルを自分で探して読んで、整理・書き込みまでやる」 |
| lead-line | `lead-line` | 3 | 25 | 30 | 「同じアプリの中に、性格のちがう 3 人が住んでいます。」 |

40 文字を超える 5 件のうち 3 件は `prompt-box` の**指示文そのもの** (逐語の例示) であり、
要約すると例示にならない。残る 2 件は日程・接続先の事実列挙である。
つまり参照資料は「説明文としては 40 文字以内、それを超えるのは逐語引用と事実列挙だけ」
という運用になっている。

### 12.3 プラグインへの反映

| 反映先 | 内容 |
|---|---|
| `config/handout-visual-policy.json#micro_copy` | 役割別上限を label 14 / title 24 / caption 40 として正本化 |
| C12 `W-COPY-LONG` | `sections[].parts[].data` と `diagrams[].data` の文字列へ上限を当てる |
| 免除 | `TEXT` (文字数予算が別管轄) / `B10` (既定で閉じる折り畳み・TEXT 溢れの畳み先) / `B11` (逐語引用) |

参照資料には概念図解 SVG が無く、カード・行・チップで構造化している。利用者からは
「これに図解を足すのも可」との追認があるため、`W-DIAGRAM-FEW` による概念図解の下限は
維持したうえで、カード・表による構造化を図解と同格の視覚部品として数える。
