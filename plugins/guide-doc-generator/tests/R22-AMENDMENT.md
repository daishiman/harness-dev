# R22 追補 — 粒度 2 軸 (detail_level / evidence_depth) のテスト追加

対象タスク: `P04-x-04`
設計正本: `plugin-plans/guide-doc-generator/briefs/RESOLUTION-R22.md`,
`script-brief-C11.json` / `C12.json` / `C22.json` / `C23.json`, `skill-brief-C01.json`,
`goal-spec.json` の C61-C66。

R22 は既存の型に軸を足す追補である。**既存テストの受入基準を緩める書き換えは 1 件も行っていない**
(既存ファイルへの編集はゼロ。追加は新規ファイルのみ)。

## 追加したテストファイルとチェックリスト対応

| 追加ファイル | 対応 | 固定した内容 |
| --- | --- | --- |
| `validate-handout-config.py/test_r22_granularity_fields.py` | C61 / C62 | 2 フィールドの必須化と enum 外の棄却、プリセット既定の適用と `provenance.<field>_source` (`preset-default` / `explicit`)、3x3=9 の全組み合わせが有効 (禁止の対が無いこと)、既定表を C12 側に二重に持たないこと |
| `validate-handout-config.py/test_r22_detail_budget.py` | C63 (適用側) | 折り畳み上限を `text_limits.block_body_max_chars_by_detail_level` から水準別に引く、水準を跨ぐと同じ本文の折り畳み有無が変わる、detailed が生成する B10 のみ `open=true`、キー欠落テーマでの fail-soft、script に overview/detailed の数値リテラルが無いこと |
| `resolve-handout-preset.py/test_r22_granularity_defaults.py` | C61 (C23 側) | `granularity_defaults(catalog, purpose)` が doc_type ごとの既定を返す、値が C23 ブリーフと一致、全語彙 slug を被覆、別名も同一解決、未知 purpose は `UnknownPurposeError`、既定は制約ではない (診断コードを持たない・2 軸が独立に動く) |
| `render-handout.py/test_r22_detail_attributes.py` | C63 (数値の正本と描画側) | テーマトークンが 3 水準を宣言し値が確定値と一致、`block_body_max_chars` は standard と同値、root へ `data-hb-detail-level` / `data-hb-evidence-depth` を 2 属性として逐語で焼く、`data-hb-text-limit` が採用水準に追従、renderer は `open` を水準から推測しない、renderer に上限の数値リテラルが無いこと |
| `render-handout.py/test_r22_level_invariants.py` | C65 | 同一構成データから水準だけを変えた 3 生成物で、sticky 目次 / yyyy/mm/dd 日付 / 目的・背景・ゴール / 抽象↔具体の往復 / アイコン規約 / 単一ファイル自己完結 が保持され、差分が粒度属性と `open` 属性に限定されること (正規化後のバイト一致) |
| `run-handout-build/test_r22_hearing_granularity.py` | C64 | 2 フィールドを 1 問で提示、`required: false`、無回答で停止せず C23 の既定を採用し `preset-default` を記録、R21 の必須 5 項目ブロックを汚さない、既定表を skill 側に持たず実行時に C23 から引くこと |
| `verify-handout-narrative.py/test_r22_nar09_nar10.py` | C66 | NAR-09 (main セクション本文の 1 セクション平均で宣言↔実態を突合。detailed 宣言で overview 上限以下は違反、overview 宣言で detailed 上限超は違反、standard は帯、付録は対象外、境界値はテーマトークン由来)、NAR-10 (cited 以上で各 claim が根拠を内包、sourced でさらに出典表記が非空、none は許容、claim ゼロは空虚な PASS)、2 軸の違反が互いを巻き込まないこと |

## ディレクトリ別の件数 (追補前 → 追補後)

コマンド: `python3 -m unittest discover -s <dir> -p 'test_*.py'`

| ディレクトリ | tests 前 | tests 後 | failures 後 | errors 後 |
| --- | --- | --- | --- | --- |
| `tests/validate-handout-config.py/` | 240 | 278 | 359 | 0 |
| `tests/resolve-handout-preset.py/` | 103 | 113 | 113 | 0 |
| `tests/render-handout.py/` | 66 | 90 | 123 | 20 (追補前から同数) |
| `tests/run-handout-build/` | 34 | 48 | 42 | 0 |
| `tests/verify-handout-narrative.py/` | 186 | 215 | 224 | 0 |

failures が tests を上回るのは `subTest` によるもの。全ディレクトリで failures > 0 であり、
実装が無いことによる赤として成立している。

`tests/render-handout.py/` の errors=20 は**追補前から存在する**既存テスト
(`test_html_attributes.py` / `test_html_structure.py` / `test_r21_rendering.py`) が
`setUpClass` 内で未実装を検出して例外を投げる構造に由来する。既存テストの書き換えは
禁止されているため解消していない。追加した 2 ファイルは `setUpClass` を一切使わず、
errors を 1 件も増やしていない (追補後の error 20 件はすべて既存クラス)。

## 設計正本の矛盾・未定義 (書き換えず記録)

> **追記 (P04-x-06 / 2026-08-17)**: 1・2・3 は `briefs/RESOLUTION-P04-x-05.md` の
> 裁定 A / B / C で正本側が決着し、テスト実体は `P04-x-06` が追従させた。
> 現状は 1 = `granularity_defaults` を 6 番目の許可キーとして正式化 (個数は導出値)、
> 2 = `_support.DETECTION_ORDER` を `detections` 定義順の NAR-01..NAR-10 へ、
> 3 = 全語彙明示列挙 + `proposal` = standard / sourced + fallback 廃止。
> 4・5・6 は未決着のまま残る。詳細は `P04-x-06-ALIGNMENT.md`。


1. **C23 のプリセット鍵数**: `script-brief-C23.json` の `structural_guarantee` は
   プリセットの鍵をちょうど 5 個に固定する一方、`variant_per_preset` は
   `granularity_defaults` を 6 個目として追加する。既存の
   `test_r20_invariants.PresetKeySurfaceTest.test_preset_keys_are_within_allowed_five` と
   両立しない。追加テストは格納形を問わずモジュール API
   (`granularity_defaults(catalog, purpose)`) 経由でのみ検査し、既存テストを
   達成不能にしない形に留めた。格納場所の裁定は P04-x-01 の集約側で必要。

2. **C22 の detection 件数**: `script-brief-C22.json` は R22 で 10 検出になったが、
   既存の `test_cli_contract.py` は stdout の detection 行が NAR-01..NAR-08 の
   8 件ちょうどであることを `assertEqual` で固定している
   (`_support.DETECTION_ORDER` も 8 件)。NAR-09 / NAR-10 を出力する実装は
   この既存テストを緑にできない。追加ファイルは `_support.summary()` を使わず
   ローカルの行パーサで R22 の 2 行だけを読む形にしてある。既存定数・既存テストは
   変更していないので、8 件固定を 10 件へ広げる裁定が別途必要。

3. **C23 の既定表の被覆漏れ**: `granularity_defaults.defaults` は doc_type 7 種のみで、
   語彙 slug の 8 番目 `proposal` に既定が無い。C64 の「無回答でも必ず既定が引ける」が
   `proposal` では成立しない。テストは全語彙 slug の被覆を要求する形で赤にしてある。

4. **enum 違反の診断コードが未定義**: `script-brief-C12.json` は
   `detail_level` / `evidence_depth` の enum 外値に対する診断コードを
   (`E-PRESENTATION-ORDER` のようには) 定めていない。追加テストは exit 1 と
   stderr に当該 JSON pointer を名指す行があることのみを要求し、コード名は固定していない。

5. **NAR-09 の standard の帯が未定義**: ブリーフは standard を「広い帯」とだけ述べ、
   上下限を定めていない。テストは両極端 (極小・detailed 上限の 2 倍) で PASS することのみを
   固定し、内部の閾値は実装の裁量に残した。

6. **claim ブロックの生成責務が未定義**: NAR-10 は `data-hb-block-role="claim"` /
   `data-hb-evidence` / `data-hb-evidence-source` を前提とするが、これらを
   どのブロック種別から C11 が生成するかは C11 のブリーフに無い。テストは
   属性を直接注入した HTML でゲート側の判定だけを固定している。
