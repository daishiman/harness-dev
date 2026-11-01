# C12 validate-handout-config.py 受入テスト (P04-C12-01)

実装 (`plugins/guide-doc-generator/scripts/validate-handout-config.py`) より先に判定基準を固定するためのテスト群。
**この時点では全件が赤であることが正しい状態**であり、緑になったら契約を検査できていない証拠。

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/validate-handout-config.py -p 'test_*.py'
```

- テストメソッド数: **240** (subTest 展開で 264 件の失敗が出る)
- 依存: Python 3.10+ 標準ライブラリ (`unittest` / `subprocess` / `ast`) のみ。pytest / yaml / .sh / .js を使わない
- 判定基準の出所: `plugin-plans/guide-doc-generator/briefs/script-brief-C12.json` (argv / exit_codes / algorithm / normalize_algorithm / config_schema / r21_type_constraints / acceptance_checks / failure_modes)、`briefs/RESOLUTION-R21.md`、`briefs/config/handout-sections.json`

## 仕掛け

`_harness.py` が全テストの足場。

- **plugin root を temp へ複製して実行する。** `HB_ROOT` 環境変数 (ブリーフ A2 の実体解決 4 段の 1 段目) を複製先へ向け、複製した `scripts/validate-handout-config.py` を `subprocess` で起動する。これにより `config/handout-sections.json` の `max_items` / `min_duration_share` / `required_role` や `assets/tokens/<theme>.json` の `text_limits.block_body_max_chars` を書き換えて挙動が追従するかを検査できる — 「閾値を script へ書かない」という契約は、この書き換え回帰でしか測れない。
- **script が未存在なら returncode=127 の合成結果を返す。** import 例外で落ちるのではなく、各テストの `assert_exit` / `assert_diag` が「期待した exit code と診断コードが出ない」と報告して赤になる。実装が生えた瞬間に同じ assert がそのまま本番契約の判定器になる。
- **`H.valid_config()`** が全必須フィールドを満たす構成データ (AC-C12-01 の入力)。各テストはここから 1 点だけ壊して落ちることを確認する。

## 赤で固定した契約の対応表

### argv / exit code 契約 — `test_argv_contract.py` (20)

| テスト | 契約 id |
|---|---|
| `test_config_missing_flag_is_exit2` / `test_config_path_not_found_is_exit2` | exit_codes.2 |
| `test_normalize_without_out_is_exit2` | AC-C12-10 |
| `test_out_same_realpath_as_config_is_exit2` / `test_out_same_realpath_via_symlink_is_exit2` | AC-C12-09 |
| `test_out_parent_directory_missing_is_exit2` | exit_codes.2 |
| `test_today_bad_format_is_exit2` / `test_today_wellformed_is_accepted` | argv `--today` |
| `test_schema_path_unresolvable_is_exit2` / `test_catalog_path_unresolvable_is_exit2` | exit_codes.2 / A2 |
| `test_broken_json_is_exit1_not_exit2` / `test_broken_json_reports_line_and_column` | A3 / failure_modes |
| `test_valid_config_exit0_with_summary_and_empty_stderr` / `test_summary_reports_counts` | AC-C12-01 / stdout 契約 |
| `test_stdout_is_not_json` | stdout 契約 (JSON の行き先は `--out` 一箇所) |
| `test_stdin_is_ignored` | stdin 契約 |
| `test_config_is_never_modified` | N13 |
| `test_hb_root_env_resolves_plugin_root` | A2 |
| `test_diagnostic_line_shape` | stderr 契約 |
| `test_all_violations_are_listed_not_just_first` | failure_modes (全件列挙) |

### 文書 / セクション / 参照 — `test_document_fields.py` (47)

| テスト群 | 契約 id |
|---|---|
| `DocumentFields` 必須欠落・空・未知キー・長さ・enum・書式 | A5 / document_level_fields / AC-C12-19 |
| `test_use_scene_is_rejected_as_unknown_key` | failure_modes (同義の入口を作らない) |
| `test_title_long_is_warning_only` / `test_strict_turns_warning_into_failure` / `test_sections_many_is_warning` | AC-C12-20 / failure_modes |
| `DocTypeVocabulary` | A6 / N6 / AC-C12-12 / AC-C12-13 |
| `SectionFields` goal・lead_line・judgment_axis | AC-C12-02 / AC-C12-03 / AC-C12-04 (C38 / C15 / C40) |
| `test_lead_line_multiline` / `test_judgment_axis_multiline` | E-LEADLINE-MULTILINE / E-AXIS-MULTILINE |
| `test_section_id_*` / `test_unknown_section_kind` | A7 / section_kind_ssot |
| `test_document_scope_part_cannot_be_placed_in_section` / `test_unknown_part_id` / `test_part_shape_mismatch` / `test_nested_tabs_are_rejected` | A8 / part_data_schema / E-PART-SHAPE / E-PART-NESTED-TABS |
| `ReferencesAndGlossary` | A10 / A11 / AC-C12-17 / AC-C12-18 / E-ASSET-ROLE-MISSING / W-REF-UNUSED |

### 正規化と再現性 — `test_normalize_date_determinism.py` (29)

| テスト群 | 契約 id |
|---|---|
| `DateResolution` | N4 / AC-C12-05 / AC-C12-06 / AC-C12-07 / date_single_source_guarantee (C33-C35) |
| `NormalizeDefaults` | N3 / N7 / N7b / N11 / AC-C12-22 |
| `SubjectSlug` | N5 / AC-C12-21 |
| `FailClosed` | N1 / N12 / AC-C12-11 |
| `EncodingAndDeterminism` | AC-C12-08 / encoding_rules (sort_keys・末尾改行・LF・NFC・BOM・CRLF・配列順保持) |

### R21 — 各 checklist の owner としての契約

| ファイル | 件数 | checklist | 診断コード / 規則 | 受入検査 |
|---|---|---|---|---|
| `test_r21_document_fields.py` | 22 | C47 / C57 / C58 | `E-FOCUS-THEME` / `E-REMEMBER-PAIR` / `E-REMEMBER-MAX` / `E-TARGET-TASKS-EMPTY` | AC-C12-R21-47 / 57 / 58 |
| `test_r21_ties_and_role.py` | 16 | C48 / C58 | `E-SECTION-UNTIED-GOAL` / `E-SECTION-UNTIED-TASK` / `E-TIES-DANGLING` / `E-SECTION-ROLE-CONFLICT` / `E-APPENDIX-ORDER` | AC-C12-R21-48 / 58 |
| `test_r21_presentation_order.py` | 9 | C49 | `E-PRESENTATION-ORDER` + N4b (`CR-PRESENTATION-ORDER`) / `provenance.presentation_order_source` | AC-C12-R21-49 |
| `test_r21_flow_and_slots.py` | 16 | C46 / C51 | `E-SECTIONKIND-MAXITEMS` / `E-SECTIONKIND-ROWDETAIL` / `E-CAPABILITY-SLOT-MISSING` / `E-CAPABILITY-SLOT-ORDER` | AC-C12-R21-46 / 51 |
| `test_r21_text_fold.py` | 17 | C52 | `E-TEXT-OVERFLOW` (検証時) / `CR-TEXT-FOLD` = N10b (正規化時) / `provenance.text_fold_count` | AC-C12-R21-52 |
| `test_r21_attainment.py` | 11 | C54 | `E-ATTAINMENT-LEVEL` / `E-ATTAINMENT-OVERRUN` / `E-ATTAINMENT-UNREACHED` | AC-C12-R21-54 |
| `test_r21_duration.py` | 21 | C59 | `E-SECTION-DURATION-FORMAT` / `E-DURATION-INCOMPLETE` / `E-TIMEBOX-SUM` / `E-SECTIONKIND-DURATION-SHARE` | AC-C12-R21-59 |

R21 で特に強く固定した点:

- `presentation_order` は省略時に `prior_knowledge_level` から決定論導出され (`none`/`basic` → `demo_first`、`intermediate` → `explain_first`)、`provenance.presentation_order_source` が `explicit` と `derived-from-prior-knowledge` を区別する。明示値は導出に負けない。
- `must_remember` と `no_need_to_remember` は**対**。片方だけが非空なら `E-REMEMBER-PAIR` で落ちることを、どちらを先に書いたかに依らない対称な 2 テストで固定した。
- `role=main` のセクションは `ties_to` に (a) `goal`/`focus_theme:*` と (b) `target_task:*` の**両方**が要る。goal だけの資料が「紐づいているから合格」にならないことを別テストで固定 (AC-C12-R21-58 の回帰)。
- `section_kind="logistics"` は `required_role=appendix` により本編へ置けず、appendix は全 main より後ろ。
- `section.duration` が時間の唯一の正本。`dialogue` の `min_duration_share` (0.15) を下回れば FAIL し、割合の分母は `document.duration` ではなく `sections[].duration` の総和。

### section_kind 追加制約 — `test_section_kind_constraints.py` (21)

`action-items` (owner/due) は AC-C12-15、`known-unknown-next` (cards 3 件 + note_key) は AC-C12-16、
`decisions` / `sources` は part_data_schema の notes、`handson` (`E-SECTIONKIND-HANDSON` / B17 の operation-expected 対) と
`anticipated-qa` (items 2 件以上・全件 `open=false`) は R21 C53。

### ソース構造検査 — `test_source_hygiene.py` (11)

| テスト | 契約 id |
|---|---|
| `test_stdlib_only_imports` / `test_no_yaml` | AC-C12-23 (C27) |
| `test_no_purpose_vocabulary_literals` | AC-C12-14 (C42。語彙正本から動的に読んで突き合わせる) |
| `test_no_part_id_enumeration` | part_data_schema_note (id 語彙の正本は C11) |
| `test_no_section_kind_threshold_literals` / `test_no_min_duration_share_literal` / `test_section_kind_default_is_not_hardcoded` | section_kind_ssot / C46 / C59 |
| `test_does_not_import_c23_by_file_path_literal_only` | dependencies.invokes (importlib 経由) |
| `test_config_is_opened_read_only` | N13 |
| `test_single_date_resolution_point` | date_single_source_guarantee |
| `test_no_network_access` | component-inventory `network: false` |

## 実装側への注意

- テストは `--out` の**内容**まで見る。exit code だけを合わせても通らない。
- 閾値・語彙・既定値をデータファイルから読まずに script へ書くと `test_source_hygiene.py` と
  `test_threshold_comes_from_catalog_not_script` / `test_share_threshold_comes_from_catalog` /
  `test_required_role_comes_from_catalog` / `test_section_kind_default_comes_from_catalog` が落ちる。
- テストを書き換えて基準を緩めることは P05 の write_scope 外。基準の誤りを見つけた場合はブリーフ側の
  修正として上げること。
