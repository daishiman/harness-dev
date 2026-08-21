# 図解スタイルトークン（セマンティックロール索引）

<!-- css-route: diagram -->
<!-- この宣言より後ろの var() は diagram 経路の :root とだけ照合される (lint-contract-drift.py check G)。経路が違う例を載せるときは、その直前に別の css-route 宣言を置く -->

> **この文書は値の正本ではない。** 値の正本は
> `vendor/scripts/svg-kit.cjs` の `TOKENS` / `SERIES` / `STROKE` / `NODE_STYLES` と
> `vendor/scripts/style-builder.cjs` の `SPEC.colors` の 2 ファイルだけである。
> 本ファイルは「図解を描く人・agent が**役割の名前**で色を引く」ための索引であり、
> 値を複製しない。正確な値が必要な処理は必ず上記の正本を直接読む。

## 0. なぜロール名で引くのか

図解が「別の人が描いたように見える」原因はほぼ全て、線幅・色をその場の数値で
決めていることにある。色をリテラルで書いた図は、テーマ側の値が変わった日に 1 枚だけ
古いまま取り残される。**ロール名で引けば、値が動いても図が追随する。**

したがって図解を書くときの規約は 2 つだけ:

1. **色値を直接書かない。** 本ファイルの「正本キー」列から正本を参照する。
2. **ここに無い色を作らない。** 新しい色が要ると感じたら、それは色の問題ではなく
   情報構造の問題である（→ §3 focal rule / §5 使用制限）。

`scripts/validate-svg-diagram.py` の D10（パレット逸脱＋純黒）は
`svg-kit.cjs` の `TOKENS` / `SERIES` ブロックから許可色を実行時抽出するので、
**本ファイルに書いていない色は成果物側で warning になる。**

---

## 1. セマンティックロール表（C20 正本索引）

正本ファイル: `vendor/scripts/svg-kit.cjs` の `TOKENS`
（CSS 変数の実値は `vendor/scripts/style-builder.cjs` の `SPEC.colors` が定義し、
`buildRootVars()` が `:root` へ出力する）

| ロール | 正本キー | 用途 | 使用制限 |
|---|---|---|---|
| `paper` | `svg-kit.cjs TOKENS.paper` | カード地・不透明マスク | ラベルのマスク矩形は必ずこれ。図の背景を別色にしない |
| `paper-2` | `svg-kit.cjs TOKENS.paper2` | 副次的な面（比較表の項目行など） | 面の階層は 2 段まで。`paper` と `paper-2` の 3 段目を作らない |
| `ink` | `svg-kit.cjs TOKENS.ink` | 主テキスト・主ストローク | 純黒を代わりに使わない（D10 が常に指摘する） |
| `muted` | `svg-kit.cjs TOKENS.muted` | 副次テキスト・既定の矢印ストローク | 矢印の既定色。`link` と使い分ける（§2） |
| `soft` | `svg-kit.cjs TOKENS.soft` | 補助ラベル・境界ラベル | 最小文字サイズでは使わない（コントラストが落ちる） |
| `rule` | `svg-kit.cjs TOKENS.rule` | ヘアライン・カード枠 | 線幅は `STROKE.hairline` 以上（D9） |
| `rule-solid` | `svg-kit.cjs TOKENS.ruleSolid` | 強い罫・基準線・軸 | 軸は `STROKE.axis`。ヘアラインと同じ太さで引かない |
| `accent` | `svg-kit.cjs TOKENS.accent` | 焦点（**1 図 1-2 要素**） | §3 focal rule。矢印の既定色にしない |
| `accent-tint` | `svg-kit.cjs TOKENS.accentTint` | `accent` 枠のノードの塗り | `accent` 枠とセットでのみ使う。単独の面塗りにしない |
| `link` | `svg-kit.cjs TOKENS.link` | フロー・接続（外部呼び出し・API） | 系列色 `series-1` と同値なので、系列図では矢印に使わない（§2） |
| `white` | `svg-kit.cjs TOKENS.white` | 塗りつぶしカード上の文字 | `filledStyle()` 経由でのみ。地色が濃い面の文字専用 |

### 1.1 CSS 変数の解決先（style-builder.cjs SPEC.colors）

CSS 変数は slide/report の `:root` で
`vendor/scripts/style-builder.cjs` の `SPEC.colors` から生成される。

> **この表の対応は、現在の生成器とほぼ一致していない。**
> 下表の「正本キー」列が指す `SPEC.colors` のキーは、**`--fg-muted` の行を除き、どれも現在の
> `SPEC.colors` に存在しない**（件数は書かない。行を増減させたときに数だけ古くなるため、
> 数えたい場合は `SPEC.colors` を直接読む）。
> したがって残りの変数は `:root` へ出力されず、`svg-kit.cjs` の `var(--名前, #hex)` は
> 常に第 2 引数の hex へ落ちる。**色は出るが、変数経由では制御できない状態にある。**
> 意匠刷新にともなう対応表（ロール → 現行トークン）は設計中で、確定するまでこの表の値は書き換えない。
> 値を先に書き換えると、対応が決まったときに 2 度目の書き換えが要るうえ、
> 途中の版が「一致している表」に見えてしまう。
> 現在の実値は `SPEC.colors`（正本）を直接読む。

| CSS 変数 | 正本キー | 図解側で参照しているロール |
|---|---|---|
| `--fg` | `style-builder.cjs SPEC.colors.fg` | `ink` |
| `--fg-muted` | `style-builder.cjs SPEC.colors.inkMuted` | `muted` |
| `--sakura-pink` | `style-builder.cjs SPEC.colors.sakuraPink` | `accent` / `series-3` |
| `--wave-blue` | `style-builder.cjs SPEC.colors.waveBlue` | `link` / `series-1` |
| `--wave-aqua` | `style-builder.cjs SPEC.colors.waveAqua` | `series-2` |
| `--autumn-yellow` | `style-builder.cjs SPEC.colors.autumnYellow` | `series-4` |

> `--fuji-gray` の行は 2026-08-14 に落とした。第 3 列の 2 語がどちらも偽だったうえ、
> **綴りを直しても行として成立しない**ことが分かったため。`soft` は `TOKENS` の 9 キー
> （`paper` `paper2` `tone2` `ink` `muted` `rule` `accent` `link` `white`）に無く、当たっていたのは
> 「`arrow-soft` は…**置いていない**」というコメント 1 行だった（**同じ 1 行が別々の担当を 2 回
> 引っかけている**。不在の記録が存在の証拠として読まれる形）。`rule-solid` は
> `style-builder.cjs:222` の `--rule-solid: 1px` で**線幅**であり、色ではない（使用箇所 6 件は
> すべて `border-top: var(--rule-solid) solid var(--hairline)` の形で、色は `--hairline` が担う）。
> そして主語の `--fuji-gray` は**どの経路の生成器も定義していない**（実在は経路外の
> `vendor/assets/src/styles/variables.css` と `vendor/assets/slide-template-single.html` の 2 件で、
> これは drift の `orphan-var-definer` に出ている 2 件そのもの）。
> 綴りだけ直すと「**どの経路にも属していない変数について、経路を書いていない行**」が延命する。
> 色ロールの一覧はこの表に持てない（経路ごとに名前も数も違う）。SR-5-05 と同じ扱いにした。
>
> `--fg-dim` の行は 2026-08-14 に `--fg-muted` へ寄せた。旧行は正本キーを
> `SPEC.colors.fgDim` としていたが、**その綴りは `style-builder.cjs` に 1 か所も無い**。
> 値を代入しているのは `--fg-muted: <inkMuted>` の行だけで、`--fg-dim: var(--fg-muted)` は
> そこから派生した別名である。別名のほうを表が例示していると、そこから写した記述が
> 別名を増やし続ける（実際に文書側の参照は別名が多数派だった）。`svg-kit.cjs` の
> `muted` トークンも `--fg-muted` を指しているので、寄せ先はこちらで一致する。
>
> `--spring-violet` の行は 2026-08-14 に落とした。`SERIES` が 5 枠から 4 枠になり
> `series-5` が消えたので、この変数を参照している図解ロールが 1 つも無くなったため。
> 名前だけは `VAR_VIOLET` として互換で残っているが、指す先は `SERIES[0]` で、
> **増える区別は 1 つも無い**（復活させると同じ色に 2 つ目の名前が付く）。

---

## 2. 系列色（SERIES・4 色）

正本: `vendor/scripts/svg-kit.cjs` の `SERIES`（順序も正本。並べ替えると既存成果物の色が変わる）

> **枠は 2026-08-14 に 5 から 4 へ減った。**それ以前は 5 要素あったが、いずれも §1.1 の
> 「存在しないキー」に紐づく変数を参照して第 2 引数の hex へ落ちるため、
> **`series-1` と `series-5` が同一の値**になっていた。5 枠目は一度も別の見た目を
> 出していない（builder golden 11 本の再生成が全件 SAME）ので、枠ごと落とした。
> 見出しの数を戻す前に、`SERIES` が実際に何要素あるかを読むこと。
>
> **`series-3` は `accent` と同一の値である**（どちらも `var(--sakura-pink, #141412)`）。
> 下表の使用制限が言うとおりだが、現在は「同じ役割の色だから」ではなく
> 「両方が同じ値へ落ちているから」同値になっている。
> 何段の符号系が要るかは対応表の設計事項なので、ここでは食い違いの記録に留める。

| 系列 | 正本キー | 使用制限 |
|---|---|---|
| `series-1` | `SERIES[0]` / `VAR_BLUE` | `link` と同値。系列図では矢印に `link` を使わない |
| `series-2` | `SERIES[1]` / `VAR_AQUA` | — |
| `series-3` | `SERIES[2]` / `VAR_PINK` | `accent` と同値。焦点表現と競合するので系列図では `accent` を別途使わない |
| `series-4` | `SERIES[3]` / `VAR_YELLOW` | — |

### 系列色の使用制限（4 条）

1. **色でしか区別できない図に限る。** レーダー・折れ線・円/ドーナツ・積上棒・散布図など、
   重なり合う複数実体を判別する必要がある型だけ。アーキテクチャ図・スイムレーン・
   フローチャートへ後付けしてはならない（そこでは形と配置が既に区別を担っている）。
2. **5 系列目を作らない。** 4 色で足りないなら、それは系列が多すぎる（→ 複雑度予算）。
   統合するか、図を分割する。塗りで区別する図では、この 4 は
   `SERIES_SUPPLY_NO_DASH`（D27 / SR-15-24）が言う供給の 4 段と同じ限界を指している。
3. **`series-3` は `accent` と同じ色である。** 系列図で焦点を作りたいときは、
   `accent` を重ねるのではなく **`resolvePalette({ paletteMode: 'focal' })`**
   （焦点のみ `accent`・他は全て `muted`）へ切り替える。系列色と焦点色を同一図で混ぜない。
4. **矢印には系列色を適用しない。** 矢印の色は `muted`（既定）か `link`（外部呼び出し）の
   2 択で、系列の意味を運ばせない。運ばせると凡例が矢印にも必要になり凡例が膨らむ。

---

## 3. focal rule（強調は 1 図 1-2 要素）

> `accent` は編集上の強調であって、状態フラグではない。

- **`accent` の面塗りは 1 図あたり 1-2 件まで。** 検査は
  `scripts/validate-svg-diagram.py` の **D7**（warning）。
  決定論経路では `kit.resolvePalette()` が明示 focal を先頭 2 件だけ採る。
- 3 件以上置くと視線の着地点が定まらず、「どこから読むか」が読者任せになる。
  強調したい要素が 3 つあるなら、それは 3 つの主張があるということで、
  スライドなら 1 スライド 1 メッセージ違反、レポートなら節の分割対象である。
- **焦点は「重要」ではなく「本文がこれから語る対象」を指す。**
  図の中で本文と接続する 1 点を `accent` にする。これが R9 溶け込み契約
  （`diagram-layout-contract.md` 第 4 次 update 章 §D-4）の入口になる。
- `accent-tint` は `accent` 枠のノードの塗りとしてのみ使う。
  `accent-tint` だけを塗って枠を `ink` にすると、焦点なのか副次面なのか読めない。

---

## 4. ノード種別 → 塗り / 枠 / 破線（NODE_STYLES）

正本: `vendor/scripts/svg-kit.cjs` の `NODE_STYLES`

意味の違うノードを同じ箱で描くと階層が消える。逆に、意味が同じノードを
別の見た目で描くと読者が存在しない区別を探す。この 7 種以外を作らない。

| ノード種別 | 正本キー | 意味 |
|---|---|---|
| `focal` | `NODE_STYLES.focal` | 焦点（1 図 1-2 件） |
| `plain` | `NODE_STYLES.plain` | 通常ノード（既定） |
| `store` | `NODE_STYLES.store` | 状態・保管（DB・キャッシュ） |
| `external` | `NODE_STYLES.external` | 外部システム（自分の管理外） |
| `input` | `NODE_STYLES.input` | 入力・利用者 |
| `optional` | `NODE_STYLES.optional` | 任意・非同期 |
| `boundary` | `NODE_STYLES.boundary` | 境界・セキュリティ領域 |

補足:

- 塗り・枠・破線の値は `NODE_STYLES` だけが持つ。この索引へ転記しない。
- 塗りつぶしカード（従来グラマー）は `kit.filledStyle(color)` を通す。
  塗りの上の文字は `white` で、この経路だけが `white` を文字色に使ってよい。
- 破線は `optional` と `boundary` の 2 種のみ。
  「点線にすれば区別がつく」で 3 種目を作らない。

---

## 5. 線幅・角丸・影（STROKE と禁止事項）

線幅の正本は `vendor/scripts/svg-kit.cjs` の `STROKE`。
値と用途の表は `references/diagram-layout-contract.md` §1.1 が持つので**ここでは繰り返さない**。
本ファイルが加えるのは「素材として何を禁じるか」だけ。

| 項目 | 規約 | 検査 owner |
|---|---|---|
| 最小線幅 | `STROKE.hairline` を下回らない（`0` は「引かない」の表明なので対象外） | D9（warning） |
| 角丸 | 4 / 6 / 8 のみ（小タグ / ノード / コンテナ）。`rounded-2xl` 相当の大きな丸めを使わない | 第 4 次 update 章 §D-1（4px グリッド） |
| 影 | **全面禁止。** `filter: drop-shadow` / `<feDropShadow>` / CSS `box-shadow` を図解要素に付けない。階層は枠線と面の濃度で作る | LLM チェックリスト（ui-quality-reviewer / report-quality-reviewer） |
| グラデーション | 図解の意味を運ぶ要素には使わない（ゲージの帯など、量を連続的に読ませる型のみ可） | LLM チェックリスト |
| 純黒 | 純黒リテラルを使わない（`ink` を使う） | D10（warning・許可集合内でも常に指摘） |
| 外部依存 | 外部フォント・`<script>`・外部 `http(s)` 参照を図解内に置かない | D12（**error**） |

> `:root` には `--shadow-subtle` 等が定義されているが、これは**スライド面の
> カード・UI 要素**のための変数であって、図解の中の図形へ適用してよいという意味ではない。
> 図解に影が付くと、周囲の本文組版（影を持たない）と質感が断絶し、
> 図だけが「貼り付けられた別物」に見える（R9 溶け込み契約違反）。

---

## 6. 書体の役割（fonts）

正本: `vendor/scripts/style-builder.cjs` の `SPEC.fonts` と
`vendor/scripts/svg-kit.cjs` の `textBlock` 既定スタック。
検査は D13（`font-family` ホワイトリスト・warning）。

| 役割 | 使う書体 | 使う対象 |
|---|---|---|
| 人が読む名前・見出し・説明 | `var(--font-base)`（`SPEC.fonts.base`） | ノード名・レーン名・キャプション・注釈 |
| 技術的リテラル | `var(--font-mono)`（`SPEC.fonts.mono`） | ポート番号・コマンド・URL・型名・ID |

**mono を「開発っぽさ」の演出に使わない。** 人間が読む名前を等幅で組むと
日本語との字幅比が崩れ、`kit.charWidth` 近似を前提にした `fitText` / `wrapText` の
収まり計算がそのまま外れる（D13 が可読性でなく計算前提の検査である理由）。

最小フォントサイズは `svg-kit.cjs` の `MIN_FONT` / `MIN_FONT_SMALL`（軸ラベル等の例外）。
検査は D4（error）。

---

## 7. 同期義務（この索引を書き換えるとき）

本ファイルは役割名と正本キーだけを持つ。
**値の変更では本ファイルを直さない。** 手順:

1. `vendor/scripts/svg-kit.cjs` または `vendor/scripts/style-builder.cjs` を変更する
   （vendor変更はmanifestのmanaged local overlay更新フローを通す）
2. `python3 scripts/lint-contract-drift.py` を通す
3. 新しい役割または正本キーを増やしたときだけ、本ファイルの索引を更新する
4. 新しく値の対を増やしたなら `_CONSTANT_PAIRS` へ登録する
   （`diagram-layout-contract.md` §5 の「登録できないなら書かない」に従う）

本ファイルは `scripts/lint-contract-drift.py` の `_PROSE_GLOBS` 対象に入る必要がある。
ファイル名が `references/diagram-style-tokens.md` なので、
`references/report-*.md` だけを見る既定 glob には**入らない**。
`_PROSE_GLOBS` へ `references/diagram-*.md` を追加すること（第 4 次 update の配線項目）。

---

## 8. 関連

- 図解 1 枚の契約の全文 → `references/diagram-layout-contract.md`
- 型の選択と経路 → `references/diagram-type-crosswalk.md`
- 埋め込み用の骨格 → `assets/diagram-templates/README.md`
- 手続き知識の索引 → `skills/ref-diagram-system/SKILL.md`
