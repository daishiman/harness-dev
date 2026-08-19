# P04-x-06-ALIGNMENT — 裁定 / ハーネス欠陥 とテスト実体の対応

leaf: `P04-x-06` / 日付: 2026-08-17
上流正本: `plugin-plans/guide-doc-generator/briefs/RESOLUTION-P04-x-05.md`
write_scope: `plugins/guide-doc-generator/tests/` のみ

本 leaf が行ったのは「古い正本の写しを新しい正本の写しへ差し替える」ことに限る。
assert の削除・許容範囲の拡大・skip の追加は 1 件も無い。
各行の「固定している性質」列が、差し替え前後で変わっていないことを示す。

---

## 1. 裁定への追従

### G-03 — 絵文字判定は C16 の `CR-EMOJI` へ委譲する

| 変更先 | 変更内容 | 固定している性質 (前 → 後) |
| --- | --- | --- |
| `build-icon-sprite.py/_harness.py` | `C16_SCRIPT` / `C16_MODULE_FUNCTION` / `EMOJI_CODEPOINT_TOKENS` を追加。`make_plugin_tree(..., with_c16=True)` が C16 の script も複製する | 変更なし (定数と fixture の追加のみ)。stub は置かない — 置けば第 2 の正本になる |
| `build-icon-sprite.py/test_emoji_policy_sc05.py` | `test_layer2_violation_reports_sc05_and_codepoints` を追加 (AC-C15-3c の stderr 面) | 追加。層 2 + VS16 が exit 1 という既存の性質は `test_layer2_with_vs16_is_exit1` がそのまま保持 |
| 同上 | `EmojiDelegationTest` を新設: AC-C15-11 (コードポイント列挙 0 件 / `U+` 表記 0 件)、`scan_emoji` への委譲形 (`spec_from_file_location`)、C16 未解決時の **exit 2 fail-closed** | 追加。委譲先が解決できないときに独自判定へ退避しないことを固定 |

**denylist 前提の期待値は元から無かった。** `_harness.find_emoji` は P04-C15-01 の時点で
既に `CR-EMOJI` の二層規則 (層 1 の明示レンジ + 層 2 は VS16 を伴うときのみ) で書かれており、
`NonEmojiSymbolsPassTest` が `✔ U+2714` (VS16 なし) / `★` / `→` / `©` の **exit 0** を固定していた。
したがって AC-C15-3b / AC-C15-3c は既に固定済みで、本 leaf が足したのは
「同じ規則を書く」ではなく「同じ実装を呼ぶ」ことの検査 (AC-C15-11 と fail-closed) である。

### A — preset の鍵面は「個数」ではなく「閉じた allowlist」

| 変更先 | 変更内容 | 固定している性質 (前 → 後) |
| --- | --- | --- |
| `resolve-handout-preset.py/_harness.py` | `ALLOWED_PRESET_KEYS` へ `granularity_defaults` を追加 (6 キー)。`GRANULARITY_DEFAULT_KEYS` / `REQUIRED_PRESET_KEYS` を新設 | 「preset から不変項へ到達する経路が無い」— 集合が閉じていることは維持。個数は導出値として扱う |
| `resolve-handout-preset.py/test_r20_invariants.py` | `test_preset_keys_are_within_allowed_five` → `test_preset_keys_are_within_the_allowlist` へ改名。診断文から「5」を除き allowlist を出す | 同上。allowlist 外のキーは依然として不合格 |
| 同上 | `test_every_preset_has_the_required_keys` を追加 | 追加 (必須キーの欠落も同じ検査面で落ちる) |
| 同上 | `test_cli_output_exposes_only_variant_fields_per_preset` の許可 top-level へ `granularity_defaults` を追加 | 「用途固有の出力キーが増えない」— 集合は依然として閉じている |
| `resolve-handout-preset.py/test_catalog_integrity.py` | `test_preset_forbidden_key` の docstring から「5」を除去。`test_preset_orphan` の ghost preset へ `granularity_defaults` を付与し 4(f) の orphan 判定だけを切り出す | `E-PRESET-FORBIDDEN-KEY` / `E-PRESET-ORPHAN` の要求は不変 |

緩和でないことの根拠: allowlist へキーを足す条件は「そのキーの値空間が不変項へ到達しないこと」で、
`granularity_defaults` が表現できるのは 2 軸の既定値のみ (値域を狭めることも、
利用者の明示指定を拒むことも、セクションの追加・削除も書けない)。`INVARIANT_KEY_FRAGMENTS`
による不変項キー名の検査も無変更のまま全 preset に掛かり続ける。

### B — 固定順は `detections` の定義順 (NAR-01..NAR-10)

| 変更先 | 変更内容 | 固定している性質 (前 → 後) |
| --- | --- | --- |
| `verify-handout-narrative.py/_support.py` | `DETECTION_ORDER` へ `NAR-09` / `NAR-10` を追加 (件数は `len()` から導く旨を明記)。`DETECTION_LINE_RE` と `detection_ids()` を追加 | 「stdout が detections 定義順ちょうどで出る」— 8 の写しを 10 の写しへ差し替え。NAR-01..08 の判定内容は 1 件も変更していない |
| `verify-handout-narrative.py/test_cli_contract.py` | `test_ac01_all_eight_detection_lines_present` → `test_ac01_all_detection_lines_present` (集合一致は維持)。`test_ac01_detection_line_count_matches_detections` (AC-C22-01 の行数) と `test_ac15_detection_id_column_matches_detections_exactly` (AC-C22-15) を追加 | 行数と順序の固定は維持し、**数値リテラルではなく `DETECTION_ORDER` から導く形**へ。未知 id の混入と欠落も検出するので検査は強くなっている |
| `verify-handout-narrative.py/test_r22_nar09_nar10.py` | `R22GateTestCase` の docstring を裁定後の状態へ更新 (assert は無変更) | 変更なし |
| `verify-handout-narrative.py/README.md` | 「8 行」表記を `detections` 件数由来の表記へ。AC-C22-15 の行を追加 | 変更なし (記述のみ) |

### C — `granularity_defaults` は preset 内側の必須キー / fallback を置かない

| 変更先 | 変更内容 | 固定している性質 (前 → 後) |
| --- | --- | --- |
| `resolve-handout-preset.py/test_r22_granularity_defaults.py` | 冒頭 docstring の「格納場所は実装の裁量に委ねる」を削除し、裁定 A・C の確定形 (preset 内側 / 必須 / fallback 無し / catalog 検査で落とす) を明記 | 「既定値が doc_type から引ける」「既定値が制約でない」の 2 点は維持 |
| 同上 | `brief_defaults()` の読み出し元を `granularity_defaults.defaults` から **`preset_definitions[].granularity_defaults`** へ変更。写しの表は `brief_defaults_table()` として別に読む | 期待値の出所を正本 1 箇所へ寄せた。写しとのずれは新テストが別途検出する |
| 同上 | `GRANULARITY_KEYS` を `_harness.GRANULARITY_DEFAULT_KEYS` から導出 (二重列挙の解消) | 変更なし |
| 同上 | `GranularityDefaultsCoverageTest` を新設: 全 vocabulary slug 被覆 / 語彙 8 件 / 写しの忠実性 / catalog 実データ側の必須キーとキー面と値域 / `proposal` = `standard` + `sourced` | 「全語彙が既定を持つ」を、7 種の表の写しではなく vocabulary からの導出で固定 |
| 同上 | `GranularityCatalogGateTest` を新設: 欠落 → `E-PRESET-GRANULARITY-MISSING` (--list / --purpose 双方)、内側キー過不足 → `-KEYS`、値域外 → `-VALUE`、語彙だけ追加 → `-MISSING` (AC-C23-R22-61b / 61c) | 追加。停止する先が実行時ではなく catalog 検査時であることを固定 |
| 同上 | `NoRuntimeFallbackTest` を新設: script 本文に既定値 / enum のリテラル 0 件 (AC-C23-R22-61d)、API が `None` を返さない、`--purpose` 出力へ常に含まれる | 追加。退避経路が第 2 の正本にならないことを固定 |
| `resolve-handout-preset.py/README.md` | `test_r22_granularity_defaults.py` の行を追加 | 変更なし (記述のみ) |
| `R22-AMENDMENT.md` | 「設計正本の矛盾・未定義」1・2・3 が裁定済みである旨の追記 (本文は書き換えず) | 変更なし (記録のみ) |

---

## 2. テストハーネス欠陥 (H-01..H-03)

| ID | 変更先 | 修正 |
| --- | --- | --- |
| H-01 | `render-diagram-svg.py/_harness.py` | `_AttrDict(dict)` を新設し `Element.attrs` の照合を case-insensitive に (`__getitem__` / `__contains__` / `get`)。HTML の属性名は仕様上 case-insensitive で、`html.parser` は必ず小文字化する一方 SVG の `viewBox` はキャメルケース必須のため、素の dict では生成側の出力に関わらず `get("viewBox")` が必ず `None` になっていた |
| H-02 | `render-diagram-svg.py/test_argv_and_exit_codes.py` `test_stdin_is_not_used` | `path.read_text()` と `assertEqual` を `tempfile.TemporaryDirectory()` の `with` ブロック内へ移動 |
| H-03 | 同上 `test_width_float_is_exit2` | `assertEqual(res.returncode, 2, res, "...")` (位置引数 4 個 → `TypeError`) を `assertEqual(a, b, msg)` の 3 引数へ |

到達可能になったテスト: 7 本
(H-01 の 5 本 `test_default_width_is_860` / `test_explicit_width_is_reflected_in_viewbox` /
`test_viewbox_numbers_are_integers` / `test_cycle_is_symmetric_about_the_canvas_center` /
`test_height_grows_with_content`、H-02 の 1 本、H-03 の 1 本)。

`render-diagram-svg.py` は実装済みのため、修正後は **Ran 166 / failures 0 / errors 0**。
これは受入基準の消滅ではなく、ハーネスが初めて実装を判定できるようになったことを意味する
(task-spec の明示的な例外)。

---

## 3. 追従後の各テストディレクトリの状態

| ディレクトリ | Ran | failures | errors | 判定 |
| --- | --- | --- | --- | --- |
| `render-diagram-svg.py/` | 166 | 0 | 0 | 緑 (H-01..H-03 の例外。実装済み) |
| `build-icon-sprite.py/` | 128 | 128 | 0 | 赤 (`scripts/build-icon-sprite.py` 未実装) |
| `resolve-handout-preset.py/` | 128 | 126 | 0 | 赤 (`scripts/resolve-handout-preset.py` と `config/handout-purposes.json` 未実装) |
| `verify-handout-narrative.py/` | 217 | 226* | 0 | 赤 (`scripts/verify-handout-narrative.py` 未実装。* subTest 単位の計数) |

`resolve-handout-preset.py/` で緑の 2 本は
`test_the_defaults_table_is_a_faithful_copy` と `test_proposal_default_is_standard_and_sourced` で、
どちらも **ブリーフ (正本) だけを読む**検査であり実装に依存しない。正本が既に裁定済みなので
緑が正しい。受入基準の消滅ではない。

---

## 4. 未決着のまま残るもの

`R22-AMENDMENT.md` の 4 (C12 の enum 違反診断コード未定義) / 5 (NAR-09 の standard の帯) /
6 (claim ブロックの生成責務) は本裁定の対象外で、記録のまま残る。
