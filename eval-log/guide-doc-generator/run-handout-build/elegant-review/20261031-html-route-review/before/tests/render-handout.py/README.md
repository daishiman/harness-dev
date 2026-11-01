# C11 `render-handout.py` 受入テスト (P04-C11-01 で赤に固定)

実装 (`plugins/guide-doc-generator/scripts/render-handout.py`) より先に判定基準をここで確定させた。
P05 の実装側がテストを自分に都合よく書き換えられないよう、**契約はすべて設計正本から起こしている**。

- 契約の正本: `plugin-plans/guide-doc-generator/briefs/script-brief-C11.json`
  (`argv` / `exit_codes` / `algorithm` / `html_attribute_contract` / `parts_catalog_ssot` / `failure_modes` / `acceptance_checks`)
- 追加確定: `briefs/RESOLUTION-P03.md` (Y-02 / Y-04 / Y-05 / Y-09) と `briefs/RESOLUTION-R21.md` (C47〜C58)
- 部品 id 語彙: `config/handout-parts.json` (owner = C11)。**テスト側も id を列挙しない** — 部品ごとのテストメソッドはカタログから動的生成する

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/render-handout.py -p 'test_*.py'
```

実装が無いあいだは全件が赤 (failure / setUpClass error) になるのが正しい状態。
`_harness.require_script()` が実体不在を `AssertionError` へ変換しているため、
「実装が無い」も「契約を満たさない」も同じ形の失敗として現れる。

## ファイル構成

| ファイル | 固定した内容 |
| --- | --- |
| `_harness.py` | 共通土台 (実体解決・subprocess 起動・構成データ fixture・HTML 走査)。テストは持たない |
| `test_argv_and_exit_codes.py` | argv と exit code の契約、テーマの二重指定・書き戻し |
| `test_input_violations.py` | 違反系入力で exit 1 になる系 |
| `test_determinism.py` | 同一入力の再現性、トークン間接化、標準ライブラリのみ |
| `test_html_attributes.py` | `data-hb-*` 属性語彙 (下流 5 本の検査アンカー) |
| `test_html_structure.py` | 骨格・CSS・JS 機構 (sticky ナビ / スタガー / print / a11y / メモ) |
| `test_parts_catalog.py` | 部品カタログ駆動のレンダリング網羅と module API |
| `test_r21_rendering.py` | R21 (C47-C58) の描画責務 |
| `test_cross_component.py` | 下流ゲートへの受け渡し (相手 script が未実装のあいだは skip) |

## 契約 id ↔ テストの対応表

| 契約 id | 出所 | テスト |
| --- | --- | --- |
| AC-C11-1 | 2 回生成のバイト一致 (checklist C29) | `test_determinism.ByteReproducibilityTest.test_two_runs_are_byte_identical` ほか 2 件 |
| AC-C11-2 | C16 selfcontained が exit 0 | `test_cross_component.GateHandoffTest.test_selfcontained_gate_passes` |
| AC-C11-3 | C17 a11y/print が exit 0 | `GateHandoffTest.test_a11y_print_gate_passes` |
| AC-C11-4 | C18 / C22 が exit 0 | `GateHandoffTest.test_language_gate_passes` / `test_narrative_gate_passes` |
| AC-C11-5 | カタログの全部品に独立したレンダリングテスト | `test_parts_catalog.PartRenderingTest.test_part_*` (動的生成) + `CatalogCoverageTest` 3 件 |
| AC-C11-6 | `.date-pill` が `^\d{4}/\d{2}/\d{2}$` かつ入力と同値 | `test_html_attributes.DatePillTest` 2 件 |
| AC-C11-7 | section goal 空で exit 1 + section id | `test_input_violations.SectionFieldTest.test_empty_section_goal_is_exit1_with_section_id` |
| AC-C11-8 | nav の未解決 fragment で exit 1 | `NavIntegrityTest` 2 件 (孤立 section 側も含む) |
| AC-C11-9 | `scroll-margin-top` と `getBoundingClientRect` の二重補正 | `test_html_structure.StickyNavAndOffsetTest.test_offset_correction_is_doubled` |
| AC-C11-10 | スタガーが CSS のみで成立 | `test_html_structure.StaggerTest` 3 件 |
| AC-C11-11 | アクセントトークン差し替えの diff が `:root` のみ | `test_determinism.TokenIndirectionTest.test_accent_token_change_only_diffs_root_block` + `TypographyAndTokenTest.test_design_tokens_are_declared_as_css_variables_in_root` |
| AC-C11-12 | theme 二重指定 exit 1 / `--config-out` 欠落 exit 2 | `test_argv_and_exit_codes.ThemeArgvContractTest` 2 件 |
| AC-C11-13 | `--config-out` へテーマ 1 欄だけ追記、出力先に `handout-config.json` を作らない | `ThemeArgvContractTest.test_theme_writeback_only_touches_theme_field` |
| AC-C11-14 | 用途プリセット横断で共有の型が保たれる (checklist C44) | `test_cross_component.PresetSharedShapeTest.test_every_purpose_keeps_the_shared_shape` |
| AC-C11-15 | C20 逆抽出との round-trip 等価 | `GateHandoffTest.test_round_trip_equivalence` |
| AC-C11-16 | 未正規化で exit 1 / 現在日時取得が 0 件 | `test_input_violations.UnnormalizedConfigTest` 4 件 |
| AC-C11-17 | 標準ライブラリのみ (checklist C27) | `test_determinism.StdlibOnlyTest.test_no_third_party_imports` |
| AC-C11-18 | 全属性が定義どおりの要素に付き、非 `data-hb-` の data 属性が 0 件 | `test_html_attributes.AttributeNamespaceTest` 2 件 + `PartAttributeTest` 4 件 + `AttributeContractCoverageTest` |
| AC-C11-19 | part id のリテラル列挙が catalog 以外に 0 件 | `test_parts_catalog.SingleVocabularyTest.test_part_ids_are_not_enumerated_outside_the_catalog` |
| AC-C11-20 | C11 の exit 1 と C16 の違反リストが一致 | `GateHandoffTest.test_external_reference_violations_match_c16_exactly` + `test_input_violations.ExternalReferenceTest` 3 件 |
| AC-C11-R21-a | R21 追加属性と描画必須フィールド、B17 の 3 つ組 | `test_r21_rendering.R21AttributeTest` 9 件 |
| AC-C11-R21-b | 片方だけを出す経路が存在しない (C57) | `test_r21_rendering.RememberPairTest` 2 件 |
| AC-C11-R21-c | 上限超過の本文を切り詰めずに exit 0 (C52) | `test_r21_rendering.TextLimitNoTruncationTest` 2 件 |

### 契約 id を持たないが正本に書かれている振る舞い

| 出所 | テスト |
| --- | --- |
| `argv` / `stdout` / `exit_codes` (--config 必須・不在・JSON 構文エラー・親ディレクトリ不在・結果 JSON の全キー・出力エンコーディング) | `test_argv_and_exit_codes.ArgvContractTest` 8 件 |
| `plugin_root_resolution` の 4 段フォールバック | `ArgvContractTest.test_plugin_root_resolution_falls_through_to_file_relative` |
| `algorithm` 5-8 (用途語彙照合・必須フィールド・セクション必須 3 種・nav 1:1) | `test_input_violations.DocumentFieldTest` / `SectionFieldTest` |
| `failure_modes` (未知 block type・tabs 2 段目・委譲先 exit 1 転記・肥大時 warnings) | `test_input_violations.BlockVocabularyTest` / `test_cross_component.DelegationTest` / `OversizeWarningTest` |
| `algorithm` 9-22 (sprite 参照・トークン :root 展開・タイポグラフィ・hero・セクション固定順序・print・a11y・メモ) | `test_html_structure.py` 全体 |
| `parts_catalog_ssot.consumer_contract` の module API | `test_parts_catalog.CatalogModuleApiTest` 3 件 |
| `invocation_style_rationale` (C14/C15 は module import・C13 は呼ばない) | `test_cross_component.DelegationTest` 2 件 |
| `theme_token_schema_ownership` (text_limits・config を 4 本目にしない) | `test_r21_rendering.ThemeTokenSchemaTest` 2 件 |

## 実装側が満たすべき前提 (テストが読むファイル)

テストは実装本体のほかに、C11 が owner / 同梱する次のファイルを読む。未生成のあいだは該当テストが赤のままになる。

- `plugins/guide-doc-generator/config/handout-parts.json` (部品 id 語彙の正本)
- `plugins/guide-doc-generator/config/handout-purposes.json` (owner C23・AC-C11-14 の用途一覧)
- `plugins/guide-doc-generator/assets/tokens/pop.json` (`text_limits` と `--pop-primary` 系トークン)
