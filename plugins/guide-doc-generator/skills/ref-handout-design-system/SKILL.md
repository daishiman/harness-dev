---
name: ref-handout-design-system
description: 資料の部品カタログ・デザイントークンの値を確認したいとき、アイコン規約を引きたいときに読む。
owner: harness maintainers
source-tier: internal
disable-model-invocation: false
user-invocable: false
allowed-tools: [Read]
kind: ref
prefix: ref
hierarchy_level: L1
effect: none
output_language: ja
source: plugin-plans/guide-doc-generator/component-inventory.json#C04
since: 2026-08-17
version: 0.2.0
responsibility_refs:
  - references/answer-patterns.md
schema_refs:
  - ../../schemas/handout-config.schema.json
completeness_exempt:
  - "manifest: ref kind は問い合わせに応じて正本の所在を返す参照専用面で、phase 遷移や副作用を持たないため workflow manifest は作らない。"
---

# ref-handout-design-system

## Purpose & Output Contract

guide-doc-generator が生成する資料のデザイン言語について、問い合わせに対して規範を
引用で返す参照。返す面は 6 つに限る。

1. 部品カタログの構成データ表現
2. CSS 変数トークン一覧
3. アイコン規約
4. 文章設計の型
5. カードとナビの視覚設計 (R25)
6. 資料作成の大原則 (考え方層)

デザイン言語の出所は jp-web-design のモードB「Pop・親しみ」である。実行時に
plugin の外を読まないため、採用した規範は `assets/jp-web-design-mode-b.md` へ
vendoring した。同じ理由で、資料作成の大原則は上流正本から
`assets/deck-principles/principles.json` へ generated mirror として同梱する (面 6)。
回答の組み立て方は `references/answer-patterns.md` に置く。
ユーザーグローバル資産 (`~/.claude` 配下など) と絶対パスは参照しない。

## 責務境界 (Boundary)

- 入力 = 部品またはトークンについての問い合わせ。出力 = 規範の引用。
- HTML の生成とレンダリングはしない。単独 writer は C11 `render-handout.py` で
  あり、CSS・部品テンプレート・トークン展開・入場アニメーションを書くのはその
  1 本だけである。
- 生成物の検証もしない。自己完結とアイコン様式は C16、a11y と印刷は C17、言語
  規約は C18、物語構造は C22 が判定する。
- 語彙を自分の側へ複製しない。部品 id・用途語彙・セクション種別はいずれも別
  component が所有するデータファイルが正本で、この skill は毎回それを読む。
- 生成物は外部参照ゼロの単一 HTML である。CDN・web font・外部 URL・外部アイコン
  フォントを前提とする設計回答をしない。取得を発生させる参照が違反かどうかの判定
  規則の正本は C16 `verify-handout-selfcontained.py` の CR-EXT であり、この skill
  はその所在を示すだけで自分では判定しない。
- 規範と実装が食い違って見えるときは、描画の実装 (C11) が正本である。この skill
  は参照回答であって仕様の決定主体ではない。

## 参照の正本表

| 問い合わせ | 読むファイル | owner |
|---|---|---|
| 部品の id と属性 | `config/handout-parts.json` | C11 |
| 用途の語彙とプリセット | `config/handout-purposes.json` | C23 |
| セクション種別 | `config/handout-sections.json` | C12 (writer) |
| 冒頭カード・ナビの閾値と見出し語 | `config/handout-visual-policy.json` | C12 (閾値解決) |
| カードの CSS クラス名と DOM 構造 | C11 `render-handout.py` のブリーフ | C11 |
| 外部参照ゼロの判定規則 | C16 `verify-handout-selfcontained.py` の CR-EXT | C16 |
| テーマトークンの実値 | `assets/tokens/<theme>.json` | C11 (スキーマ owner は C11) |
| 採用したデザイン言語 | `assets/jp-web-design-mode-b.md` | C04 (vendoring 実体) |
| 資料作成の大原則の配布境界と共通契約 | `assets/deck-principles/README.md` | guide-doc-generator |
| 資料作成の大原則の本文と閾値 | `assets/deck-principles/principles.json` (`scripts/select-deck-principles.py` 経由) | slide-report-generator (上流正本) |
| guide consumer の対応 | `assets/deck-principles/binding.json` | guide-doc-generator (local overlay) |
| 回答の型 | `references/answer-patterns.md` | C04 |

## 面 1: 部品カタログの構成データ表現

部品 id の語彙をこの skill は持たない。問い合わせのたびに正本
`config/handout-parts.json` (owner: C11) のカタログを読んで答える。カタログを
参照せずに記憶から id を答えることを禁じる。

- カタログの各エントリは id と表示名、`kind` (骨格 / セクション内の具体部品 /
  メディア)、`section_scope`、構成データ側のブロック型、初出、出所を持つ。
- 「セクション内の具体部品か」を判定する述語は `section_scope` であり、id の
  範囲指定で判定しない。カタログに部品が増えても述語は変わらない。
- 構成データは部品を直接名指しせず、ブロック型で表現する。ブロック型から部品への
  写像はカタログの `data_block_type` を引く。
- 用途の語彙は `config/handout-purposes.json` (owner: C23) を、セクション種別は
  `config/handout-sections.json` (writer: C12) を読む。どちらもこの本文へ値を
  書き写さない。

## 面 2: CSS 変数トークン一覧

アクセントは 1 色だけ置き、そこから明度の 4 段階を派生させる。派生した値は
`<style>` 冒頭の `:root` へ展開し、実値が現れるのはそのブロックだけにする。
以降の CSS 規則と SVG はすべて `var()` 参照で書く。こうしておくと、テーマを
差し替えるときに書き換える場所が 1 か所で済む。

値の正本は `assets/tokens/<theme>.json` であり、この skill にも生成コードにも
実値を焼かない。テーマを増やすときはトークンファイルを 1 枚足す。以下は形の
例示であって値の正本ではない。

```css
:root {
  --pop-primary: #43a4f5;
  --pop-primary-pastel: #8ecdf8;
  --pop-primary-soft: #d9edfe;
  --pop-primary-deep: #2273b8;
  --pop-bg: #eaf5fe;
  --ink: #1b2733;
  --ink-muted: #5b6b7a;
  --line: #dbe6ef;
  --subtle: #f4f8fc;
  --card-radius: 24px;
  --font-num: "Helvetica Neue", Arial, sans-serif;
}

body {
  background: var(--pop-bg);
  color: var(--ink);
  font-feature-settings: "palt";
}
.card { border: 1px solid var(--line); border-radius: var(--card-radius); }
.chip { background: var(--pop-primary-soft); color: var(--pop-primary-deep); }
.num { font-family: var(--font-num); font-variant-numeric: tabular-nums; letter-spacing: -0.015em; }

@keyframes rise-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: none; }
}
.section { animation: rise-in 480ms ease-out both; animation-delay: var(--stagger, 0ms); }

@media (prefers-reduced-motion: reduce) {
  .section { animation: none; }
  html { scroll-behavior: auto; }
  * { transition: none; }
}
```

- 4 段階の役割: ブライトは CTA とトグル ON、パステルは面、soft は選択状態と
  チップとリング、deep は文字とリンクと線画。deep を面に使わない。
- 和文は `font-feature-settings: "palt"` を body に置いて字間を詰める。
- 数値は tabular-nums で桁を揃える。桁が揃わない表は読み比べができない。
- 入場は rise-in のスタガー。段差はインライン変数 `--stagger` で各要素へ与え、
  JavaScript を使わない形で成立させる。段差の上限は C11 が決める。
- `prefers-reduced-motion: reduce` では animation と scroll-behavior と transition
  を無効化する。
- テーマトークンには `text_limits.block_body_max_chars` (既定 400) が入る。この
  スキーマの owner は C11 であり、上限を超えた本文の折り畳み規則は C12 の
  CR-TEXT-FOLD が正本である。この skill は既定値を引用するだけで、値も規則も
  決めない。

## 面 3: アイコン規約

様式は 4 点で固定する。`viewBox="0 0 24 24"` / `stroke="currentColor"` /
`fill="none"` / `stroke-linecap="round"`。塗りつぶしアイコンと 24 以外の
viewBox を混ぜない。

```html
<svg width="0" height="0" aria-hidden="true" style="position:absolute">
  <symbol id="hbic-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 12l5 5L20 6" />
  </symbol>
</svg>

<svg class="ic" aria-hidden="true"><use href="#hbic-check" /></svg>
```

- 定義は `<symbol>` に 1 回だけ置き、使う側は `<use>` で参照する。同じ図形を
  複数回インライン展開しない。
- 色は `stroke="currentColor"` 経由で親の文字色に従う。アイコン側に実値を
  書かない。
- 構成データから実際に参照されたアイコンだけを sprite に入れる。
  未使用の symbol は 0 件にする。
- sprite の生成と symbol id の採番は C15 `build-icon-sprite.py` が行う。この
  skill は様式を答えるだけで生成しない。採番規則を自分で決めない。
- アイコンの代わりに絵文字を使わない。装飾でも見出しでも絵文字は使わない。
  意味を持つ記号が要るなら線画アイコンを sprite へ足す。

## 面 4: 文章設計の型

読み手は初心者・非エンジニアである。抽象と具体を往復させる型を守る。

1. 冒頭は一文の主題。到達ゴールはチップで並べ、読み終えた後の状態を示す。
2. 全体像を先に出し、読み手が残量を把握できるようにする。
3. 各セクションは「番号 + 見出し」から始め、次に絵、その後に 1 行の抽象
   (lead-line) と具体部品を置く。
4. 抽象を出したら具体例を続け、最後に判断軸を一文で締める。判断軸が無い節は
   読み手が自分の状況へ当てはめられない。
5. 専門用語には必ず括弧書きの言い換えを添える。初出で言い換えなかった語は以降も
   通じない。
6. 一文を短くする。補足文はおおむね 20 から 45 字に収める。
7. 断定できないことは「未確定」と書く。推測を事実の形で書かない。

判定は人手ではなく C18 と C22 と C06 が行う。この skill はその規範の出典を
示すだけで、個別の原稿を採点しない。

## 面 5: カードとナビの視覚設計 (R25)

冒頭は段落で埋めず、1 行の宣言とカードで見せる。ナビは読み手が残量を把握する
ための導線である。この面で返すのは「どこに正本があるか」であって、閾値の実値
でも DOM の写しでもない。値も構造もこの本文へ複製しない。

- 冒頭を hero-card 化する対象フィールドと、そこで用いる見出し語は
  `config/handout-visual-policy.json` の `#opening.hero_card_fields.layout` /
  `#opening.list_headings.headings` / `#opening.connector_card.heading` を
  読んで答える。
- nav 項目のラベル上限は同じファイルの `#micro_copy.roles` のうち
  `role="label"` のエントリ (`fields` に `nav_item` を含むもの) を読む。
  上限の数値をこの本文へ書き写さない。
- nav の置き場所 (左の柱か上の帯か)・柱の幅・帯へ戻す画面幅は同じファイルの
  `#nav.layout` / `#nav.sidebar_width_px` / `#nav.collapse_below_px` を読む。
  どちらの置き場所でも sticky は維持する (スクロールしても目次は消えない)。
  柱では札を縦に積み、行頭を左で揃える。値をこの本文へ書き写さない。
- CSS クラス名と DOM 構造の正本は C11 `render-handout.py` のブリーフにある
  `block_to_component_map` の冒頭ブロックのエントリである。`.hero-card-grid` /
  `.hero-card` / `.hero-card-label` / `.hero-card-body` / `.section-card` と
  いった名前はそこで決まる。この skill は所在を示すだけで複製しない。
- 冒頭の分量が上限を超えているかの判定 (W-HERO-LONG / W-HERO-HEAVY) は C12
  `validate-handout-config.py` の責務である。この skill は値を読まないし
  判定もしない。
- 参照先のキーが正本ファイルに存在しないときは、記憶や推測で埋めない。
  「未確定」と答え、正本の owner へ差し戻す。

## 面 6: 資料作成の大原則 (考え方層)

面 4 が扱うのは本 plugin の資料に固有の文章の型である。その手前にある「誰に何を
してほしいか」「骨格をどう組むか」「箇条書きをどこで切るか」「図解の型を何から
決めるか」は媒体をまたぐ原則である。所在・consumer marker・selection envelope・
上流 mirror と local overlay の境界は `assets/deck-principles/README.md` だけを読む。

面 4 と選択原則が競合するときは本 plugin 固有の面 4 を優先する。判定はこの skill が
行わず、読みやすさは C18 と C22、自己完結は C16、a11y と印刷は C17 が担う。
