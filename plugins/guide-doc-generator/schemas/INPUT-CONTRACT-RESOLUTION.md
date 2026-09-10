# INPUT-CONTRACT-RESOLUTION — C11 (renderer) と C12 (schema) の入力契約の裁定

`P05-x-20` の裁定記録。`schemas/handout-config.schema.json` に適合する構成データを
`scripts/render-handout.py` へ渡すと部品が 1 件も描画されなかった構造的乖離
(`ROUNDTRIP-CONTRACT.md#blocking_contract_divergences` の
`c11-c12-input-shape-divergence`) を解消し、どちらを正本とするかを確定する。

## 1. 乖離の実体 (着手時に再実測した)

| # | renderer が期待するもの | schema が宣言するもの |
|---|---|---|
| (a) | `config["normalized"] is True` を必須とする | top-level `properties` に `normalized` が無く `additionalProperties:false` |
| (b) | `config["nav"]` (目次データ) を必須とし section id と 1:1 を課す | top-level `properties` に `nav` が無い |
| (c) | `sections[].blocks[]` を走査し `block.type`(= `steps` / `table` …) で分岐する | `sections[].parts[]` を `required` で宣言し、要素は `{part: <catalog id>, id, data}` |

(c) は「キー名が違う」だけではない。schema の `$defs.part_data` は各部品の `data` の形を
`part` ごとに定義しており、フィールド名も renderer の描画モデルと異なる
(例: B03 は `rows[].text` / renderer は `items[].label`)。さらに schema は画像・添付・図解を
`asset_id` / `attachment_id` / `diagram_id` の **参照**で持つのに対し、renderer の描画モデルは
実体を部品の中へ**展開**して持つ。つまり乖離は「別名」ではなく**正規化の段が 1 段違う**。

## 2. 裁定

### 2.1 正本は schema (`handout-config.schema.json`) とする

`plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` 自身が
`algorithm[5]`「フィールド名と制約の正本は C12 の config_schema であり、本 script は再定義せず
存在と非空だけを確認する」・`algorithm[6]`「セクションレベルのフィールド名も C12 の
config_schema.section_fields が正本」と書いている。C11 の brief に出てくる
`normalized` / `nav` / `blocks` は、その C11 自身が宣言した従属関係に反して C11 側が持って
しまった第 2 の名簿である。**正本を持たない側が持つ側に合わせる**のが唯一整合する向きなので、
schema を正本とする (取りうる解のうち (A))。

- **(B) 正規化後の形を別 schema として schema へ足す案は退けた。** `normalized` は
  「C12 --normalize を通ったか」の真偽であり、schema には既に同じ事実を運ぶ
  `provenance.normalized_by` (`const: "validate-handout-config.py"`、
  `x_required_after_normalize` に含まれる) がある。同じ事実の 2 本目のフィールドを増やす案で
  あり、二名簿を作らないという本 plugin の原則に反する。
- **(C) C12 の出力を renderer の期待形へ寄せる中間層を独立 component として置く案も退けた。**
  変換規則の正本が schema でも renderer でもない第 3 の場所に生まれ、部品を足すたびに
  3 箇所を同時に更新することになる。

`additionalProperties` を `true` へ緩める / `required` を外す案は最初から採らない
(`P05-x-11` の判断と `ROUNDTRIP-CONTRACT.md` §4 に整合)。**schema は 1 バイトも変更していない。**

### 2.2 3 点それぞれの決着

| # | 決着 | 実装 |
|---|---|---|
| (a) `normalized` | **schema へ足さない。** 正規化済みであることは `provenance.normalized_by` が schema 由来の `const` と一致することで判定する。期待値は schema から実行時に読み、renderer へ焼き込まない | `normalized_by_const()` / `project_schema_config()` |
| (b) `nav` | **schema へ足さない。導出する。** 目次は `sections[].id` と `sections[].heading` から一意に決まる派生物であり、構成データへ持たせると目次と本文の二名簿になって同期ずれを表現できてしまう (PAT-1)。導出した目次は section と定義上 1:1 なので、`nav` 不整合という失敗モード自体が消える | `project_schema_config()` の `projected["nav"]` |
| (c) `parts` | **schema が正本。** renderer の入力境界に `sections[].parts` → 描画モデルの投影を 1 段置く。参照 (`asset_id` / `attachment_id` / `diagram_id`) はここで解決し、解決できなければ `exit 1` | `project_part()` / `PART_DATA_PROJECTIONS` |

投影表の鍵は部品カタログの `data_block_type` であり、`Renderer.RENDERERS` と同じ語彙を使う。
part id を renderer へ列挙しない (Y-05) という既存の規律を崩さないため、
part id → `data_block_type` の対応は `config/handout-parts.json` から実行時に引く。

`normalized` の検査は**弱めていない**。証拠が無い schema 方言の構成データは
`exit 1` (`test_missing_provenance_is_exit1` / `test_wrong_normalized_by_is_exit1`)。

### 2.3 旧方言 (`normalized` / `nav` / `sections[].blocks`) の位置づけ

renderer は「section が `parts` を持つか」で方言を判定し、旧方言の入力は従来どおり
`normalized:true` と `nav` の 1:1 を課したまま処理する。これは**互換のための猶予であって
正本ではない**。残している理由は 1 つだけで、C11 の受入テスト
(`tests/render-handout.py/_harness.py` の fixture と `test_input_violations.py` の
AC-C11-16 / AC-C11-8) が旧方言を固定しており、その移行は本タスクの受入基準の外にあるためである
(テストの assert を弱めない制約下では fixture 側の全面移行が必要で、別 leaf の仕事になる)。

**旧方言は将来削除する。** 削除に必要な作業は §5 に列挙する。

## 3. 受入の実測

- schema 適合の判定は自分でせず C12 に委ねている。
  `tests/render-handout.py/test_schema_dialect_input.py` が
  `validate-handout-config.py --config` を exit 0 で通ることを検査し、
  同じ構成データで `render-handout.py` が exit 0、
  カタログの **in-section 部品 18 件すべて**が `data-hb-part` / `data-hb-part-id` として
  描画されること (`blocks_by_type` が空でないこと) を検査する。
- 部品 fixture の網羅はカタログから導出しているので、部品を足して fixture を足さなければ赤になる。
- 3 スイート (`render-handout.py` / `validate-handout-config.py` / `extract-handout-config.py`) の
  失敗テスト名の集合は着手前後で不変。

## 4. 投影で落ちる値 (既知の欠損)

schema にはあるが描画モデルに受け皿が無く、現状 HTML へ出ない値。いずれも
「schema を緩める」側の問題ではなく **renderer の描画実装の未対応**であり、後続の受け皿が要る。

| pointer | 値 | 現状 |
|---|---|---|
| B03 `rows[].num` | 明示連番 | renderer は常に `index+1` を描く |
| B09 `rows[].decided` / `show_counter` | 既決フラグ / 件数表示 | 描画に反映されない |
| B11 `copyable` | コピーボタンの有無 | 常に出る |
| B12 `label` | ボタン表示文言 | 添付の `filename` を表示する |
| IMG `lightbox` | lightbox の有無 | 常に付く |
| B15 `key` (部品単位の鍵) | 単一選択群の識別子 | 属性として出ない |

B05 は `cells` の件数が `columns` と同数で、行見出し列が `columns` 側に名前を持たない。
投影は列見出しの先頭に空セルを 1 つ補って桁を合わせている (`_project_table`)。
`rows[].highlight` の整数は `cells` 上の 0 始まり位置として読み、先頭セル 1 つ分ずらして
(行, 列) 座標へ写す。

## 5. 後続へ渡す作業

1. **旧方言の撤去** — `tests/render-handout.py/_harness.py` の `base_config` / `base_section` /
   `BLOCK_FIXTURES` を schema 方言へ移し、`test_input_violations.py` の AC-C11-16 / AC-C11-8 を
   `provenance` 側の証拠と導出目次に対する検査へ書き直したうえで、renderer から
   `normalized` / `nav` / `blocks` の経路を削る。
2. **§4 の欠損の解消** — 描画実装側の対応。
3. **round-trip の残差** — 本裁定の投影を通した schema 方言の構成データでは、
   `extract-handout-config.py` は 18 部品を `exact` で復元し `unrecoverable` は 0 になる
   (投影前は部品が 1 件も描かれず復元しようがなかった)。残る不一致は C20 側の読み取り粒度である。
   実測した残差は次のとおり。
   - section の `role` / `ties_to` / `attainment_step` / `glossary` が復元結果に現れない
     (マーカーは HTML 側に出ている)。
   - 部品内のテキストが兄弟要素ごとに分かれず連結される
     (例: B03 が `"1資料を開く手元で開く5分"`、B07 が `title` へ body と footnote を連結)。
   - B05 / B06 / B12 / B14 は形が別の部品の形で復元される (`columns` が行の配列になる 等)。
   - B13 の `panel_parts` が入れ子として復元されず、タブ配列が平坦化される。
   - DIAGRAM の `diagram_id` に部品 id が入り、`diagrams[]` の id を指していない。

## 6. 本タスクの範囲外で見つけた不整合 (手を出していない)

- **`script-brief-C11.json` が C12 の schema に無い入力形を要求している。**
  `argv[0].description` の「normalized:true とスキーマ版が無い構成データは受け付けない」、
  `algorithm[2]` (normalized:true)、`algorithm[7]` (nav と section id の 1:1)、
  `algorithm[16]` / `block_to_component_map` (`blocks[]` / `block.type`) が該当する。
  一方で同じ brief の `algorithm[5]` / `algorithm[6]` は「フィールド名の正本は C12」と書いており、
  brief 内部で矛盾している。本裁定は後者を採った。brief は write_scope 外につき未修正。
- **`ROUNDTRIP-CONTRACT.md` の `/assets/*/data_uri` の裁定は現行の C20 受入テストと両立しない。**
  裁定は「`data-hb-src` が非空ならその値を `src` に戻し data URI は捨てる」「C20 が `data_uri`
  キーを発明せず `src` へ格納する」とするが、
  `tests/extract-handout-config.py/test_marker_extraction.py` の AC-C20-06
  (`test_image_asset_is_restored_with_data_uri` / `test_attachment_is_restored_with_data_uri`) は
  同一エントリに**原本相対パス (`src`) と data URI 本体の両方**が保持されることを要求している。
  フィールド 1 本では両立しないため、`extract-handout-config.py` の `data_uri` キーを削ると
  当該 2 件が赤になる。裁定かテストのどちらを動かすかの決着が必要で、本タスクの受入基準
  (入力契約) の外にあるため手を触れていない。
