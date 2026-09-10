# C20 extract-handout-config.py 受入テスト (P04-C20-01)

実装 (`plugins/guide-doc-generator/scripts/extract-handout-config.py`) より先に判定基準を
赤で固定するためのテスト群。**P05 の実装側がここへ都合のよい基準を足して差し替えない**
ことを前提に読むこと。契約の出所は次の 3 つだけで、ここには契約を書かない。

- `plugin-plans/guide-doc-generator/briefs/script-brief-C20.json` (入出力契約・受入検査の正本)
- `plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md` の **Y-05** (部品 id 語彙の単一正本)
- `plugin-plans/guide-doc-generator/component-inventory.json` の C20 定義

## 実行

```
python3 -m unittest discover -s plugins/guide-doc-generator/tests/extract-handout-config.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。実装が無い間は `run()` が exit 127 の合成結果を返すので、
**import 例外ではなく failure として** 落ちる (2026-08-17 時点: 152 tests / 150 failures /
1 skipped / 1 passed。passed は plan 側カタログの存在確認、skipped は P05 で生成される
実装側カタログとの id 一致確認)。

## ファイルと固定した内容

| ファイル | 固定した判定基準 | 主な契約 id |
| --- | --- | --- |
| `_harness.py` | plugin root を temp へ複製して起動する足場、マーカー付き HTML fixture、参照 v1 相当の手書き HTML、診断コード定数、comparable projection | — |
| `test_argv_contract.py` | exit 2 は起動側の不正だけ (未指定/読めない/同一 realpath/親ディレクトリ不在/compare が JSON でない)、`--out` 省略時は検査のみ、構成データ JSON を stdout へ流さない、1 行サマリの形、`--html` の不可侵、write_scope が out-file 系のみ | AC-C20-11 / AC-C20-14 / argv / exit_codes |
| `test_marker_extraction.py` | `data-hb-*` を唯一の値の出所とする復元 (文書メタ・section・parts・key/owner/due/time)、DOM 順・文書順、空白畳み込みと `<pre>` 例外、data URI 本体の保持、図解構造は `data-hb-diagram-data` からのみ、C12 と同じ書式規約 | AC-C20-05 / AC-C20-06 / AC-C20-13 / A4-A12 |
| `test_chrome_skip.py` | `data-hb-generated="true"` の部分木を丸ごと読み飛ばす。マーカーが無い場合も `.pop-header` / `.pop-bottom` / `.memo-*` で二重防御。chrome が parts / assets / lead_line へ混入しない | AC-C20-07 / A3 |
| `test_heuristic_and_fidelity.py` | class_map による部品復元と `W-EXTRACT-HEURISTIC` (根拠クラス名つき)、never_guessed の 7 項目を推測せず null + `E-EXTRACT-UNRECOVERABLE`、穴つき成果物を `--out` へ残して exit 1、穴の一覧を構成データへ書かない、`--strict-fidelity` の境界 | AC-C20-08 / heuristic_fallback / fail_semantics |
| `test_roundtrip_compare.py` | comparable projection 上の深い等価、provenance を比較しない、キー順は差でない、未正規化 date は差でない、配列は順序込み、不一致は JSON Pointer + expected + actual を全件、diff 時は `--out` を書かない | AC-C20-01 (C20 側) / AC-C20-03 / roundtrip_granularity |
| `test_failure_modes.py` | 閉じない HTML は `E-HTML-MALFORMED` + 行番号で exit 1 かつ `--out` を書かない、void 要素で壊れない、section id 重複は黙って片方を選ばない、図解 JSON の破損は当該のみ穴にして他は続行 | AC-C20-10 / failure_modes |
| `test_determinism_and_report.py` | 同一入力から `--out` / stdout / `--report` がバイト一致、出力先パスを成果物へ書かない、中間ファイルを残さない、レポートの形 (fidelity 内訳・unrecoverable・roundtrip diffs) と stdout サマリとの一致 | AC-C20-12 / report_shape / A12・A14 |
| `test_parts_catalog_ssot.py` | **P03 Y-05**。下の節を参照 | Y-05 |
| `test_source_hygiene.py` | 標準ライブラリのみ / 外部 HTML ライブラリと yaml が 0 件、正規表現による DOM 解析の禁止、`convert_charrefs` を無効化しない、正規化を再実装せず C12 を importlib で読む、NFC、ソートしない、`os.replace`、構成データ blob を前提にしない | AC-C20-15 / C27 / parsing_strategy |

## P03 Y-05 (部品 id 語彙の単一正本) をどう赤で固定したか

Y-05 の確定は「**第二の正本を持たない**」ことなので、挙動だけでは落とせない。
`test_parts_catalog_ssot.py` はモジュール実体・ソース・挙動の 3 面から固定する。

1. **照合表の形** — モジュール内で「部品 id を鍵とする dict」を **名前ではなく形で** 探し、
   それが **ちょうど 1 つ** であることを要求する (複数あれば第二の正本の疑い)。値がクラス名
   (文字列またはその列) であることも確認し、照合表が「存在する id の名簿」に化けるのを防ぐ。
2. **双方向の自己整合検査** — 複製した plugin root のカタログを書き換えて起動する。
   - カタログに `B98` を足す → **カタログにあって鍵が無い部品**として stderr へ列挙される。
   - 照合表が鍵に持つ id をカタログから消す → **カタログに無い id を鍵に持つ行**として列挙される。
   - 報告行は stderr 契約と同じ「1 行 1 件・先頭に診断コード」の形。
   - 過不足が無いときは何も言わない (常時ノイズを出さない)。
3. **id 集合を自前に持たない証拠 (挙動)** — カタログへ部品を足すと script 無改修で認識され、
   消すと認識されなくなる。カタログに無い `data-hb-part` 値は黙って通さず exit 1。
   カタログが無いときに内蔵の名簿へ退避しない。
4. **ソース側** — 部品 id リテラルがすべてカタログ (と `non_part_structure_markers`) の内側に
   収まること、`config/handout-parts.json` を読んでいること、C12 のスキーマ (`part_data_schema` /
   `part_catalog`) を id 語彙の出所として参照していないこと、document スコープ部品 (B01 / B02) を
   id で名指ししていないこと。

## gaps (ブリーフに書かれておらず、テスト側で仮に固定した点)

実装 (P05) がここと違う結論を採るなら、**先にブリーフを直してからテストを直すこと**。

| # | 何が決まっていないか | テストで採った扱い |
| --- | --- | --- |
| G1 | 自己整合検査の**診断コード名**と、過不足があったときの**exit code**。C12 には `E-PARTS-CATALOG-MISMATCH` (exit 2) があるが C20 の `stderr` / `exit_codes` には対応する記述が無い | コード名は固定せず「先頭が `E-`/`W-` の診断行に当該 id が出る」ことだけを要求。exit code は問わない |
| G2 | 部品カタログが**読めないとき**の扱い | 起動側の不正として exit 2 (内蔵名簿へ退避しない、が Y-05 の趣旨) |
| G3 | カタログの**探索パス**。plugin root の解決方法がブリーフに無い | 姉妹テスト (C12) と同じ `HB_ROOT` 環境変数 + plugin root 相対 `config/handout-parts.json` |
| G4 | `assets[]` / `attachments[]` の **data URI 本体を入れるキー名** (`data_uri` 等) | キー名は固定せず「エントリのいずれかの値として原文の data URI が保持される」ことを要求 |
| G5 | `notes_enabled` の**復元マーカー**。preserved_exact に挙がっているが `required_markers` に対応する属性が無い | 値の当否は問わず「キーが消えない」ことだけを要求 |
| G6 | 部品ごとの `data` の**キー名**。C12 の `part_data_schema` が正本だが、そちらもまだ未実装 | B03/B09/B15/B16 の `rows` / `chips` と `key` / `time` / `owner` / `due`、TEXT の `body` のみ仮固定。他部品は件数と `part` / `id` だけを見る |
| G7 | `section.heading` を運ぶマーカー。`data-hb-field` の enum に `heading` が無い (`section_goal` はある) | fixture では `data-hb-field="heading"` を使用。C11 側 (P04-C11-01) と食い違ったらこちらを直す |
| G8 | 非 UTF-8 の HTML / 空ファイルの exit code | 1 か 2 のいずれか (診断コード行は必須) とだけ要求 |
| G9 | AC-C20-02 (再レンダリングのバイト一致) / AC-C20-04 (8 用途プリセット) は **C11 の実装が要る** | 本 leaf の write_scope 外。C20 側の等価判定 (AC-C20-01 相当) は手書き fixture + 自己比較 + 差分検出で代替。P06 の round-trip テストへ残す |
| G10 | AC-C20-09 (`--out` を C12 へ渡すと `E-FIELD-MISSING`) は **C12 のテスト側の責務** | 本ディレクトリでは扱わない (C20 は穴つき成果物を書くところまでを固定) |
| G11 | `component-inventory.json` の C20 `outputs` が「stdout(構成データ JSON)」と書いており、ブリーフの「構成データは常に `--out` へ書き stdout はサマリ」と食い違う | ブリーフ側を正として固定 (`test_config_json_is_not_written_to_stdout`)。inventory の記述は P05 前に直すべき |
