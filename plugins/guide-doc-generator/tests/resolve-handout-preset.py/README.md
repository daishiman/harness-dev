# C23 `resolve-handout-preset.py` 受入テスト (P04-C23-01 で赤に固定)

本ディレクトリは **実装より先に判定基準を固定する** ためのテスト群である。P05 の実装が
テストを自分に都合よく書き換えられないよう、契約は全て
`plugin-plans/guide-doc-generator/briefs/script-brief-C23.json` の `argv` / `stdout` /
`exit_codes` / `algorithm` / `acceptance_checks` / `failure_modes` から起こしてある。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/resolve-handout-preset.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。repo ルートから実行する。

**P04 時点では全件赤が正しい状態。** 赤の内容は import 例外ではなく
「実装が未存在」「依存データが未存在」という診断可能なアサーション失敗になっている
(`_harness.require_script` / `_harness.require_file`)。

## 検査の作り方 (2 つの原則)

1. **用途語彙をテストへ列挙しない。** 期待値は語彙正本
   `config/handout-purposes.json` を読んで機械的に導出し、CLI 出力とカタログの一致を検査する。
   例外は AC が名指しする `lecture` のみで、`_harness.LECTURE_SLUG` に 1 箇所だけ置いた。
   語彙の件数 8 だけは `EXPECTED_VOCABULARY_SIZE` として契約値で持つ (AC-C23-01)。
2. **実 plugin ツリーを一切変更しない。** カタログ違反系は実データを一時ディレクトリへ複製し、
   `HB_ROOT` を差し替えて実行する (`_harness.make_fixture_root`)。

## ファイルと契約 id の対応

| ファイル | 主な契約 id | 固定した内容 |
|---|---|---|
| `_harness.py` | (共通) | パス解決・fixture root 生成・正準 JSON 比較。テストではない |
| `test_cli_modes.py` | AC-C23-01 / AC-C23-10 | `--list` の text/json 出力と catalog 記載順・語彙 8 件・dir_token/alias の一意性・モード 0/2/3 個 → exit 2・`--format` enum 外 → exit 2・`--catalog` 読めない → exit 2・stdin 無視 |
| `test_purpose_resolution.py` | AC-C23-02 / 05 / 06 / 07 | 全語彙が exit 0 で section_order 1 件以上・出力キー契約・catalog との一致・`catalog_sha256` = ファイルバイト列の sha256・alias 完全一致・NFKC/前後空白/小文字化・前方一致は解決しない・E-VOCAB-UNKNOWN に全語彙一覧・`,` `+` `/` 空白 → E-VOCAB-COMPOSITE |
| `test_catalog_integrity.py` | AC-C23-03 / 04 / R21-50d | 全モード前段の自己整合検査 (E-PRESET-UNCOVERED は `--list` でも `--purpose` でも落ちる)・E-PRESET-ORPHAN・E-PRESET-FORBIDDEN-KEY (`sticky_nav` / `order_override`)・alias 重複と dir_token 重複と slug パターン違反 → E-CATALOG-MALFORMED・未知 section_kind・未知 part id・`section_scope=document` の部品・section id 重複・未知 schema_version・parse 不能 → exit 2・catalog 不在 → exit 2 と候補パス列挙 |
| `test_presentation_order.py` | AC-C23-R21-50a / 50b / 50c | 2 モードで section の multiset 一致・順序だけ変化・`recommended_parts` / `notes` / `required_document_fields` 同値 (C44)・並べ替え結果は catalog の variant 定義そのもの (C23 は導出しない)・variants なし preset は不変で `applied_variant=null`・`--presentation-order` 単独指定 → exit 2・enum 外 → exit 2・順列違反 (欠落 / 未知 id / 重複) → E-PRESET-ORDER-NOT-PERMUTATION・キー集合違反 → E-PRESET-ORDER-KEYS |
| `test_lecture_preset.py` | AC-C23-R21-53 / 57 | lecture が `flow-overview` / `capability-explainer` / `handson` / `anticipated-qa` / `dialogue` の 5 種別を必ず含み全て `required=true`・handson の推奨部品に B17・anticipated-qa に B10 (新部品を作らない)・`required_document_fields` に `must_remember` と `no_need_to_remember`・宣言フィールドが `schemas/handout-config.schema.json` の properties に実在 (E-PRESET-REQFIELD-UNKNOWN / 重複)・**対の強制は C12 の責務であり C23 は片方だけでも落とさない** |
| `test_determinism_and_readonly.py` | AC-C23-11 / 12 | 2 回実行の stdout バイト一致・`ensure_ascii=false` / `indent=2` / `sort_keys=true` / 末尾改行 1 個 / LF 固定・全モード実行後に catalog と `config/` 配下のバイト列と mtime が無変更 |
| `test_module_api.py` | AC-C23-13 | `importlib.util.spec_from_file_location` 経由で `CATALOG_RELPATH` / `resolve_catalog_path` / `load_catalog` / `vocabulary` / `resolve` / `preset` / `dir_token` / `catalog_sha256` / `CatalogError` / `UnknownPurposeError` が公開され、CLI と同値を返す。import 副作用なし |
| `test_dependency_boundary.py` | AC-C23-14 / P03 Y-08 | 外部パッケージ import 0 件 (`sys.stdlib_module_names` 照合)・**C12 を import しない** (`validate-handout-config` への参照 0 件)・`handout-sections.json` / `handout-parts.json` をデータファイルとして読む・subprocess 起動なし・書き込み系 API と書き込みモード `open` が 0 件 (write_scope 空)・script 本体が用途語彙 / section_kind を 3 種以上列挙しない |
| `test_audit_duplication.py` | AC-C23-08 / 09 (C42) | 実ツリーで `{"scanned":N,"violations":[]}` / exit 0・同一ファイル 3 種で E-VOCAB-DUPLICATED と `file:line`・2 種は違反にしない (閾値)・`tests/` と `references/` と allowlist の除外・`*.md` も走査対象・`--root` で走査起点差し替え |
| `test_r20_invariants.py` | R20 / C44 | 全 preset のキーが閉じた allowlist (`section_order` / `recommended_parts` / `notes` / `presentation_order_variants` / `required_document_fields` / `granularity_defaults`) に収まる (個数は導出値なので数えない / P04-x-05 裁定 A)・必須キーの欠落が落ちる・不変項を示唆するキー名 (nav / sticky / date / icon / theme / print / a11y ...) が preset に現れない・section エントリの形が固定・CLI 出力の top-level キーが用途ごとに増えない・全 preset の section_kind が C12 の中立データ語彙内・推奨部品が `section_scope=in-section` に限られる |
| `test_r22_granularity_defaults.py` | R22 C61 / C64 / P04-x-05 裁定 C | `granularity_defaults(catalog, purpose)` が全語彙で `{detail_level, evidence_depth}` を返す・既定値の正本は `preset_definitions[].granularity_defaults` 1 箇所で説明用の写し (`granularity_defaults.defaults`) とずれない・`proposal` = standard / sourced・欠落 → `E-PRESET-GRANULARITY-MISSING` / キー面違反 → `-KEYS` / 値域外 → `-VALUE` で exit 1・語彙だけ足しても通らない・実行時 fallback と None 返しが無い・script 本文に既定値と enum のリテラルが 0 件・`--purpose` 出力へ常に含まれる |

## P05 が満たすべき成果物 (このテストが要求するもの)

- `plugins/guide-doc-generator/scripts/resolve-handout-preset.py` (C23)
- `plugins/guide-doc-generator/config/handout-purposes.json` (C23。語彙 + プリセットの単一正本)
- `plugins/guide-doc-generator/config/handout-sections.json` (C12) / `handout-parts.json` (C11)
- `plugins/guide-doc-generator/schemas/handout-config.schema.json` (C12。`required_document_fields` の照合先)
- `plugins/guide-doc-generator/.claude-plugin/plugin.json` (実体解決 4 段目)

`test_audit_duplication.py::AuditOnRealTreeTest` と
`test_lecture_preset.py::LectureRequiredDocumentFieldsTest::test_declared_fields_exist_in_config_schema`
は他 component の成果物にも依存する。これは C42 ゲートと単一正本の性質上意図した結合であり、
C23 単体では緑にできない。

## テストを書く際に判断した点 (ブリーフに明示が無い箇所)

- **`--catalog` 指定時の隣接データファイルの解決元**がブリーフに書かれていない。本テストは
  カタログ差し替え系を `HB_ROOT` 経由で行い、`--catalog` は「読めないパス → exit 2」の
  検査にだけ使うことで、この曖昧さに依存しない形にした。
- **`schema_version` の既知値**が定義されていないため、既知値そのものは検査せず
  「明らかに未知の値 (99999) なら exit 1」だけを固定した。
- **語彙 8 語の同一性**はテストへ列挙しない方針のため、件数 (8) と catalog 記載順の一致、
  および slug / dir_token / alias の一意性で拘束している。`guide` = 一般配布資料 /
  `report` = 報告資料 という P03 の裁定そのものはカタログ側 (C23 の実装成果物) が正本である。
