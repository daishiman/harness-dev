# 図解骨格テンプレート（成果物埋め込み用）

> **単体ページ用ではない。** ここに置いてあるのは HTML **断片**で、
> スライド面（`.slider__item` の zones）またはレポート本文の中へ
> `<figure>` ごと差し込むためのものである。

## 0. 何のためにあるか

図解の生成経路は 3 つあり（`references/diagram-type-crosswalk.md` §10）、
そのうち **LLM 手書き経路だけが防具を 4 つ失う**。

| 防具 | 決定論ビルダー | slide tpl | 手書き |
|---|---|---|---|
| 件数上限（`CAPACITY`） | あり | 一部 | **なし** |
| 座標計算（`LAYOUTS`） | あり | 一部 | **なし** |
| コネクタ入射（`safeElbow`） | あり | なし | **なし** |
| 色トークン（`TOKENS` 参照） | あり | あり | **なし** |

決定論ビルダーが存在しない型を描くとき、agent は白紙から SVG を書き始めることになり、
そこで色を発明し、座標を思いつきで置き、影を付ける。
本テンプレートは**その白紙をなくす**ためにある。

## 1. ファイル

| ファイル | 用途 | 埋め込み先 |
|---|---|---|
| `diagram-skeleton-slide.html` | 16:9 スライド面内の図解ブロック | `.slider__item` の zones の 1 つ |
| `diagram-skeleton-report.html` | レポート読書フロー内の図版ブロック | 本文 `<section>` の段落間 |

両方とも:

- **JS を持たない。** `<script>` は D12（error）で失格する。
- **外部依存を持たない。** 外部フォント・CDN・`@import` も D12 で失格する。
- **色は `var(--x, fallback)` で書く。** `:root` は `vendor/scripts/style-builder.cjs` の
  `buildRootVars()` が出力する。CSS が効く場所では `:root` が勝ち、
  効かない場所（SVG 単体プレビュー）ではフォールバックが使われる。
- **矢印マーカー 3 種を同梱する。** 形状は `svg-kit.cjs` の `MARKER` と同一
  （`w=8 / h=6 / refX=7 / refY=3`）。

## 2. 使い方

1. **型と経路を決める。** `references/diagram-type-crosswalk.md` の
   「何を見せたいか」列から引く。**決定論ビルダーか slide tpl があるなら
   そちらを使う。** 本テンプレートは両方とも無いときの最後の手段である。
2. **骨格をコピーする。** 成果物へ `<figure>` ごと貼る。
3. **`data-diagram-id` を一意な値へ変える。** マーカー id の接頭辞も同じ値へ揃える
   （`d1-arrow` → `d3-arrow` のように）。ここを揃え忘れると、
   同一ページの 2 枚目以降の図が 1 枚目のマーカーを参照して**矢印の色が混ざる**。
   D3 は「参照先が同じ SVG 内にあるか」しか見ないので、この事故は検査を素通りする。
4. **`<!-- EDIT: 図解本体 -->` の中だけを書く。** 描く順序は
   下地 → コネクタ → ノード → ラベル。
5. **`<figcaption>` を書く。** 40-120 字。図のラベルを繰り返さない。
6. **検査を通す。**
   ```bash
   python3 scripts/validate-svg-diagram.py <出力file>
   python3 scripts/validate-report-visual.py <出力file>   # report のみ
   ```

## 3. 埋め込み契約（書き換えてよい範囲）

| 箇所 | 書き換え |
|---|---|
| `data-diagram-id` | **必須**（一意にする） |
| `data-figure-width`（report のみ） | `"text"` または `"bleed"` の 2 択 |
| `<marker>` の id 接頭辞 | `data-diagram-id` と揃える |
| `<!-- EDIT: 図解本体 -->` の中 | **ここが本体** |
| `<figcaption>` の中 | **必須** |
| `<figure>` の class | 書き換えない（成果物側 CSS が引く） |
| `<marker>` の `markerWidth` / `markerHeight` / `refX` / `refY` | 書き換えない（`MARKER` が正本。変えると端点補正が全経路でずれる） |
| `role` / `aria-labelledby` | 書き換えない |

## 4. 禁止事項（R9 溶け込み契約）

> **単体で豪華な図がページ内で浮く単純移植を禁じる。**

移植元の参考実装（diagram-design）は「図解単体の HTML ページ」を作るスキルで、
そのテンプレートは `<body>` に `display:flex; align-items:center` を持ち、
図を画面中央に据え、`min-width: 900px` で図に最低幅を要求し、
自前の `:root` で 4 色 3 書体を宣言していた。
**それは単体ページとしては正しいが、本プラグインの成果物へ持ち込むと壊れる。**

以下は本テンプレートで意図的に落としてある。復活させない。

| 落としたもの | 復活させてはいけない理由 |
|---|---|
| `<html>` / `<head>` / `<body>` | 断片なので、書くと成果物の DOM が入れ子になって壊れる |
| 自前の `:root` 変数宣言 | 成果物の `:root`（`style-builder.cjs` 生成）と二重定義になり、どちらが勝つか読めなくなる |
| 外部フォント `<link>` | D12（error）。CDN が落ちた瞬間にその図の書体が消えて読者に届く |
| `svg { min-width: 900px }` | 本文幅を超えて図だけが横スクロールを発生させる |
| `body { display:flex; align-items:center }` | 図が画面中央へ据わり、本文の読書フローから切り離される |
| 背景の全面塗り（`<rect width="100%" fill="paper">`） | 図だけが白い矩形として紙面／スライド面に浮き出る |
| ドットパターン背景 | 周囲の本文が持たない質感。図だけが装飾的になる |
| 影（`drop-shadow` / `box-shadow`） | R9-14。周囲の本文が影を持たないため、図だけが浮く |
| 独自配色（`#eb6c36` 等） | 本プラグインは Kanagawa トークンを維持する。移植するのは**作図文法であって配色ではない** |
| `<script>` | D12（error） |

## 5. 溶け込みの数値契約（要点）

全文は `references/diagram-layout-contract.md` の
「第 4 次 update: 作図文法の数値契約」§D-4 にある。骨格を使うときに特に効くもの:

| # | 規約 |
|---|---|
| R9-1 | スライド面内の図解ブロック面積比は 40-70% |
| R9-2 | 1 スライド 1 図解 |
| R9-3 | レポート図版の高さは読書 viewport 高の 60% 以下 |
| R9-5 | レポート図版幅は本文幅 100% か全幅 bleed の 2 択 |
| R9-6 | 図解内の実効フォントは周囲本文の 0.7-1.0 倍 |
| R9-7 | 図のラベルが直近本文に完全一致で現れるのは 1 件以下 |
| R9-9 | キャプションは 40-120 字 |
| R9-10 | キャプションは図のラベルを含めない |
| R9-11 | 図解内の有彩色は「周囲の有彩色種類数 + 1」以下 |
| R9-14 | 影は常に 0 |

## 6. 関連

- 色ロールの索引 → `references/diagram-style-tokens.md`
- 図解 1 枚の契約（幾何・素材・数値） → `references/diagram-layout-contract.md`
- 型と経路の対応 → `references/diagram-type-crosswalk.md`
- 型ごとの選ぶ条件 → `skills/ref-diagram-system/references/diagram-type-catalog.md`
- 手続き知識の索引 → `skills/ref-diagram-system/SKILL.md`
