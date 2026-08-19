# P05-x-25 裁定: C11 / C20 / C17 brief の未追随を解消する (受け皿消滅分の再割当)

- leaf: `P05-x-25` (write_scope: `plugin-plans/guide-doc-generator/briefs`)
- 経緯: 追随先の leaf (`P05-x-21` = C20 担当 / `P05-x-24` = C17/C22 担当 / `P05-x-20` = C11 担当) が
  いずれも done になり、brief 側の追随だけが受け皿を失って残っていた (PAT-4)。

## 0. 裁定の向き: 全件で「brief を実装へ寄せる」

5 件すべてで実装を正本とした。**ただし「実装が動いているから正しい」ではなく、
brief 自身が従属関係を宣言している / 実装側に理由がコメントとして残っている、という
根拠がある場合に限った。** 根拠が brief 側にも実装側にも無ければ「実装を直すべき」と
書いて残す方針だったが、今回は 5 件とも根拠が見つかったため該当が無かった。

| # | 対象 | 食い違い | 正本 | 根拠 |
| --- | --- | --- | --- | --- |
| 1 | C11 `html_attribute_contract` | 実装が出す `data-hb-*` のうち 6 件が未宣言 | 実装 | brief 自身が「ここが唯一の正本。属性を増減するときは本節を先に更新」と書いており、宣言が実装に遅れている状態は brief の自己規定違反 |
| 2 | C11 `algorithm` 手順 13 | `.date-pill` の置き場所が「header の中」で一意に決まらない | 実装 | 生成 HTML には `<header class="doc-head">` と `<header class="pop-header">` の 2 つがあり、brief の記述だけでは場所が決まらない (契約が実装より弱い) |
| 3 | C11 入力方言 | `normalized:true` / `nav[]` / `blocks[]` を入力必須として要求 | 実装 (= C12 の config_schema) | **同じ brief の手順 6/7 が「フィールド名と制約の正本は C12 の config_schema」と宣言している**。brief 自身が従属を宣言している以上、寄せる向きは一意 |
| 4 | C20 `heuristic_fallback.class_map` | 鍵が部品 id / IMG 行が裸 `<img>` を含むと書く | 実装 | 実装のコメント (`extract-handout-config.py` 冒頭) が「部品 id を鍵にすると第 2 の名簿へ退化する」「裸の `<img>` はアイコン・ロゴと区別できず拾うと構造を捏造する」と理由まで書いている |
| 5 | C17 `detections` A11Y-04 | 冒頭句が `data-hb-part="B05"` 配下の table に限定 | 実装 | **同じ rule の末尾が「data-hb-part を持たない場合も検査対象に含める」と既に書いており、rule が自己矛盾していた**。実装は全 `<table>` を無条件に走査 |

## 1. C11 属性契約の追随 (6 件)

散文で探さず、実装から `data-hb-[a-z0-9-]+` を全採取して brief の宣言集合との差集合を取った。

| 方向 | 着手前 | 着手後 |
| --- | --- | --- |
| 実装で出力・brief 未宣言 | **6 件** (`data-hb-detail-level` / `data-hb-evidence-depth` / `data-hb-notes-enabled` / `data-hb-tone` / `data-hb-live-demo` / `data-hb-action`) | **0 件** |
| brief 宣言・実装で未出力 | 0 件 | 0 件 |

`attributes` は 30 → 36 件。既存 30 件は 1 件も書き換えていない (追加のみ)。

`data-hb-notes-enabled` の記述には ROUNDTRIP-CONTRACT.md の裁定理由 (メモ UI は読み飛ばし対象の
chrome なので、UI の有無から C20 に推定させず宣言で持たせる) を併記した。属性名だけを足すと、
なぜ「UI から推定」でなく「宣言」なのかが消費側から見えなくなるため。

### 1.1 この差集合は再測できる

上記の差集合はワンライナーで再現でき、将来また実装が先行したときに同じ手順で検出できる。
**ただし検査として自動化はされていない** (§4 参照)。

## 2. C11 手順 13: `.date-pill` の置き場所

実装 (`build_doc_head`) は `<header class="doc-head">` の内側に `.date-pill` を 1 個だけ出す。
sticky ナビは別の `<header class="pop-header">` であり、印刷時に `position:static` へ落ちる帯である。

brief を「文書冒頭の `<header class="doc-head">` の内側に限る・`.pop-header` の内側には置かない」へ
改訂し、理由 (日付は資料の属性であってナビの属性ではない) を併記した。

`header` 要素が 2 つあるという事実こそが、旧記述が曖昧だった原因である。「header の中」で
一意に決まると書き手が思い込めたのは、書いた時点では `.pop-header` がまだ無かったからだろうが、
brief にはその履歴が残らない。したがって**場所の指定はクラス名まで含める**を規則として採った。

## 3. C11 入力方言の自己矛盾

brief の `block_to_component_map` と algorithm 各手順は `blocks[]` / `block.type` を使うが、
schema (C12 の config_schema) は `sections[].parts[]` である。この二重方言を
`parts_catalog_ssot.input_dialect` へ 1 箇所に集約して裁定した。

- 入力の正本は config_schema (`sections[].parts[]`) 一つだけ。
- brief 中の `blocks[]` / `block.type` は **`project_schema_config()` が写した先の描画モデルの語彙**であり、
  入力そのものの形ではない。翻訳点は `project_schema_config()` 一箇所、入口判別は `has_schema_dialect()`。
- `normalized:true` は schema に無いフラグなので要求しない。正規化済みの判定は
  `provenance.normalized_by` が schema 宣言の const と一致するか (const は schema から引き literal で書かない)。
- `nav` は schema に無い。sections から導出する (導出値を構成データへ書き下さない = PAT-1)。

追随して書き換えた箇所は 4 つ: `argv[0].description` / `algorithm` 手順 3 / 手順 8 /
`failure_modes[0].case` / `block_to_component_map[0].data`。
**`algorithm` の件数 (26) と `failure_modes` の件数と top-level キー集合は不変。**

`blocks[]` 表記そのものを全文置換しなかったのは、置換すると描画モデル側の記述まで
入力側の語彙へ倒れて逆向きの混乱を生むためである。方言が 2 つあること自体は正当で、
問題は**どちらがどちらかが書いていなかったこと**だった。

## 4. C20 `class_map` の鍵を `data_block_type` へ

`P05-x-23` の裁定 (`schemas/PART-CLASS-MAP-RESOLUTION.md`) に brief が追随していなかった。

| 観点 | 変更前 | 変更後 |
| --- | --- | --- |
| 行の鍵 | `"part": "B03"` (部品 id) | `"block_type": "steps"` (カタログの data_block_type) |
| 行数 | 18 | **18 (不変)** |
| 順序 | steps→…→text | **不変** (実装の `BLOCK_TYPE_CLASS_MAP` のキー順と完全一致することを機械照合した) |
| `selector_class` の記法 | CSS セレクタ風 (`.table-wrap > table`, `[role=tablist] + .prompt-panel`) | クラス名 (最終行のみタグ名) |
| IMG 行 | `figure.asset / img.asset-img (本文中の単独 <img> を含む)` | `asset / asset-img` + 括弧書き削除 |

追加した 3 つの説明キー:

- `class_map_key` — なぜ部品 id を鍵にしないか (第 2 の名簿への退化 / AC-C11-19 との衝突)。
- `selector_notation` — **値は CSS セレクタではなくクラス名**である。子孫・隣接・属性条件を書かない。
  実装は「クラス名の集合に当たるか」だけで判定するので、セレクタ記法で書くと**契約が実装より強い
  ことを暗示して読み手を誤らせる**。判定を強めたいなら記法を変えるのでなく、
  セレクタ照合機構を先に裁定して両方を同時に改める。
- `never_guessed_by_tag` — 裸の `<img>` を拾わない理由 (装飾と区別できず構造を捏造する)。
  最終行 (text) のタグ名照合だけは「どの型にも当たらない本文の受け皿」という別の根拠に立つ例外。

### 4.1 退けた案

- **`selector_class` に CSS セレクタを残し、実装側をセレクタ照合へ強化する。**
  隣接兄弟条件 (`[role=tablist] + .prompt-panel`) を実装できれば heuristic の精度は上がるが、
  stdlib のみの制約下でセレクタエンジンを自作することになり、しかも heuristic 経路の出力は
  `fidelity: "heuristic"` として既に「推定」と明示される。**本 leaf の write_scope は briefs だけで
  実装を触れないため、ここで決めると裁定と実装が別 leaf に割れて PAT-6 を作る。**
  §6-1 に追加タスク候補として残した。
- **class_map の行を実装のタプルへ 1:1 でコピーする。** 今回そうしたが、これは
  「クラス名は契約そのもの (導出値ではない)」という判断に基づく。**部品 id はカタログから導出できる
  ので書かない、クラス名は導出元が無いので書く** — この線引きが PAT-1 の適用境界である。

## 5. C17 A11Y-04 の冒頭句

rule が自己矛盾していた (冒頭で `data-hb-part="B05"` 配下に限定し、末尾で「data-hb-part を
持たない場合も含める」と書いていた)。実装は `[el for el in ctx.elements if el.tag == "table"]` で
全 `<table>` を無条件に走査する。

冒頭句を「**文書内のすべての `<table>` を対象とする** — data-hb-part の有無でも部品種別でも
絞り込まない」へ改訂し、部品 id literal (`B05`) を rule から削除した。
併せて「この非依存は意図的な例外であり、他の検査へ一般化しない」を明記した
(他の A11Y 検査は data-hb-part に依存してよいため、例外であることを書かないと次の書き手が
全検査を part 非依存へ倒しかねない)。

`detections` の id 集合と top-level キー集合は不変。stderr 診断コード集合にも触れていない
(rule は診断コードを持たない散文フィールドである)。

## 6. 未解決事項・追加タスク候補

1. **heuristic 経路の判定強度。** `[role=tablist] + .prompt-panel` の隣接条件が落ちているため、
   tablist を伴わない `.prompt-panel` も tabs と推定される。実害は heuristic 出力に限られ
   `fidelity: "heuristic"` で明示されるが、契約を弱めた側へ寄せた事実は残る (§4.1)。
2. **属性契約の追随は機械検査になっていない。** §1 の差集合はワンライナーで再測できるが、
   テストにはなっていない。実装が新しい `data-hb-*` を足しても brief は黙って古くなる。
   `tests/render-handout.py` 側に「実装が出す属性はすべて brief で宣言されている」を
   置ける (走査対象は `plugin-plans/` なので `GREP_SCOPE_DIRS` の拡張が要る点が
   `RESOLUTION-P05-x-29.md` §6-2 の未解決事項と同じ根に当たる)。
3. **本 leaf の成果は 1 件もテストで守られていない。** brief は plan 側の文書であり、
   どのスイートも読んでいない。したがって「テストが緑」は本 leaf の成立を何も証明しない
   (到達していない緑)。代わりに機械照合 (差集合 0 / 行数・順序の一致) を成立の根拠とした。
