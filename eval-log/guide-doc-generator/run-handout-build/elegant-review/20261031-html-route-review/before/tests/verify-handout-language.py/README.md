# C18 `verify-handout-language.py` 受入テスト (P04-C18-01 / 赤で固定)

本ディレクトリは **実装より先に** 判定基準を確定させるための受入テストである。
実装本体 (`plugins/guide-doc-generator/scripts/verify-handout-language.py`) は
**まだ存在しない**。したがって現時点で全 248 件が赤であることが正しい状態であり、
P05 の実装がこのテストを通すことをもって受入とする。

契約の正本は `plugin-plans/guide-doc-generator/briefs/script-brief-C18.json`。
本テストは推測で契約を発明していない (足りない箇所は末尾の「未確定事項 (gaps)」に記す)。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/verify-handout-language.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。テストは script を `subprocess` で起動し、
exit code / stdout / stderr / `--json-report` の 4 面だけを観測する
(実装の内部関数へは一切依存しない = 実装の書き方を縛らずに判定だけを固定する)。
未実装は import 例外ではなく `self.fail()` で表明しており、
discover 時に **errors ではなく failures** として赤になる。

## ファイル構成

| ファイル | 固定した面 | 件数 |
|---|---|---|
| `_support.py` | fixture 生成と実行ヘルパ (判定基準は持たない) | — |
| `test_cli_contract.py` | argv / exit code / stdout 書式 / OUT-OF-SCOPE / json-report / write_scope / stderr 行書式 | 53 |
| `test_lang01_glossary.py` | LANG-01 (宣言用語の初出言い換え) と宣言 0 件の可視化 | 31 |
| `test_lang04_lang05_leadline_axis.py` | LANG-04 (lead-line) / LANG-05 (判断軸の存在と形式) / 検査アンカー不在 | 29 |
| `test_lang06_order_and_parts.py` | LANG-06 (R11 の順序) と「具体部品」述語のカタログ駆動 | 23 |
| `test_lang07_capability.py` | LANG-07 = R21 C51 (機能名から始めない) の描画テキスト面 | 26 |
| `test_date01_date02_date04.py` | DATE-01 (yyyy/mm/dd) / DATE-02 (config 一致) / DATE-04 (文書内一貫性) | 31 |
| `test_date03_out_dir.py` | DATE-03 (ディレクトリ名日付) と `NOT-REQUESTED` の開示 | 23 |
| `test_scope_and_determinism.py` | 責務境界 (C06 / C12 / C16 / C17 / C19 / C22) の**担当外**回帰 / 日付単一ソース / 再現性 | 32 |

## 契約 id とテストの対応表

### detection

| 契約 id | 何を赤で固定したか | 代表テスト |
|---|---|---|
| LANG-01 | `config.glossary[]` の各 term が本文テキスト T の**初出**で括弧書きの plain を伴う。初出が無い (宣言の腐敗) も違反。全角/半角括弧・空白 (U+0020 / U+3000)・NFKC 差は吸収。2 回目以降の有無・重複は不問。英数 term は単語境界、日本語 term は境界条件なし。部分文字列関係は長い term 優先 | `TestLang01PassForms.*`, `TestLang01Violations.*`, `TestLang01LongestTermFirst.*` |
| LANG-01 (failure_mode) | `glossary` 空配列は checked=0 PASS だが、**stdout と json-report へ注記を必ず出す** (宣言を空にしてゲートを通す抜け道を可視化する) | `TestLang01EmptyGlossaryDisclosure.*` |
| LANG-04 | 各 section 配下に `data-hb-field="lead_line"` がちょうど 1 個、空白除去後に非空。0 個も 2 個以上も違反 | `TestLang04Presence.*` |
| LANG-05 | 各 section 配下に `data-hb-field="judgment_axis"` がちょうど 1 個で非空。形式条件は「句点 / `?` / `？` で終わる **または** 80 文字以内」。境界 80/81 を直接固定 | `TestLang05Presence.*`, `TestLang05SentenceForm.*` |
| LANG-06 | 文書位置で lead-line < 最初の具体部品 < 判断軸。具体部品 0 個も違反。goal-chip の位置は条件に含めない (C22 の面) | `TestLang06Order.*` |
| LANG-06 (述語) | 「具体部品」= `config/handout-parts.json` で `section_scope=="in-section"` の `data-hb-part`。document スコープ部品・構造マーカー (`section` / `memo` / `toolbar` 等)・未知 id は数えない。子孫要素まで数える | `TestLang06ConcretePartPredicate.*`, `TestLang06Nesting.*` |
| AC-C18-LANG06-CAT | 部品 id を script へ焼き込まない担保。旧記述 (B03..B15) の外にある **B16 / B17** と、`B\d\d` 形でない **IMG / DIAGRAM / TEXT** が無改修で認識されること + source がカタログを読んでいること | `TestLang06CatalogDriven.*` |
| LANG-07 | `data-hb-section-kind="capability-explainer"` の section のみ対象。lead_line の**先頭**が同 section の `data-hb-slot="feature"` 部品見出しと前方一致すれば違反 (NFKC + 空白 + 記号除去、2 文字以下の見出しは対象外)。加えて「〜機能/モード/ツール + は/を/の」で始まる場合も違反 | `TestLang07Scope.*`, `TestLang07PrefixMatch.*`, `TestLang07NounPhraseRule.*` |
| DATE-01 | `data-hb-field="date"` が `<header>` 内または hero より前に 1 個以上あり、trim 後に `^\d{4}/\d{2}/\d{2}$` へ完全一致し、暦として実在すること。不在は exit 1 (exit 2 ではない) | `TestDate01Format.*`, `TestDate01Position.*` |
| DATE-02 | date-pill と `config.date` の**無変換**文字列一致。書式変換を挟んで一致させることを禁止。現在日を取らないので過去日でも一致すれば PASS | `TestDate02Match.*` |
| DATE-03 | `--out-dir` の basename 先頭 10 文字が `^\d{4}-\d{2}-\d{2}$` かつ `config.date.replace('/','-')` と一致、11 文字目が `-`。種別語彙・slug は一切見ない (C19 の責務) | `TestDate03Match.*`, `TestDate03BoundaryWithC19.*`, `TestDate03PureConversion.*` |
| DATE-04 | date-pill が複数あるとき全て同値。本文中の別日付 (`\d{4}/\d{1,2}/\d{1,2}`) は違反にせず json-report へ info として列挙 | `TestDate04Consistency.*` |

### acceptance_checks (AC-*)

| AC id | テスト |
|---|---|
| AC-C18-01 | `TestHappyPathContract.*` (exit 0 / stderr 空 / 9 行固定順 / OUT-OF-SCOPE) |
| AC-C18-02 | `test_ac02_paraphrase_only_at_second_occurrence`, `test_ac02_evidence_shows_surrounding_text`, `test_ac02_violation_row_carries_line_and_column` |
| AC-C18-03 | `test_ac03_declared_but_absent_term_is_a_violation`, `test_ac03_absent_term_reason_differs_from_missing_paraphrase` |
| AC-C18-04 | `TestOutOfScopeDisclosure.*` |
| AC-C18-05 | `test_ac05_axis_before_lead_line_is_a_violation`, `test_ac05_violation_row_names_the_section` |
| AC-C18-06 | `test_ac06_section_without_any_part_is_a_violation`, `test_ac06_reason_mentions_missing_concrete_part` |
| AC-C18-R21-51a | `test_ac51a_lead_line_starts_with_feature_heading` ほか 2 件 |
| AC-C18-R21-51b | `test_ac51b_outcome_first_lead_line_passes`, `test_ac51b_no_capability_section_is_checked_zero_pass`, `test_ac51b_same_lead_line_passes_when_kind_is_standard` |
| AC-C18-07 | `test_ac07_missing_zero_padding_is_a_violation` ほか |
| AC-C18-08 | `test_ac08_nonexistent_calendar_date_is_a_violation`, `test_ac08_nonexistent_date_reason_is_distinguishable` |
| AC-C18-09 | `test_ac09_date_mismatch_is_a_violation`, `test_ac09_violation_row_shows_both_values` |
| AC-C18-10 | `TestDate03NotRequested.*` |
| AC-C18-11 | `test_ac11_config_date_missing_is_exit2`, `test_ac11_config_date_empty_is_exit2` |
| AC-C18-12 | `TestSingleDateSource.*` (`date.today` / `datetime.now` / `today(` / `utcnow` / `time.time(` が 0 件) |
| AC-C18-13 | `TestDeterminism.*` |
| AC-C18-LANG06-CAT | `TestLang06CatalogDriven.*` |

### failure_modes と横断契約

| 契約 | テスト |
|---|---|
| `data-hb-field` が 1 個も無い → LANG-04/05/06 と DATE-01 を FAIL (checked=0 PASS へ畳まない) | `TestAnchorAbsence.*` |
| date-pill 不在 → DATE-01 違反 + DATE-02 も未充足として計上 | `test_missing_date_pill_also_marks_date02_unsatisfied` |
| `--config` と `--html` が別資料 → 大量違反で exit 1 (exit 2 にしない) | `TestMismatchedPair.*` |
| `single_writer` (`--json-report` 以外へ書かない / `--out-dir` 配下を触らない) | `TestWriteScope.*` |
| 早期 return で後続 detection を落とさない | `test_all_detections_reported_even_when_first_fails` |
| 違反 1 件につき stderr 1 行 (サマリ合計と一致) | `test_stderr_row_count_matches_summary_total` |
| 整形差 (改行 / minify / CRLF) で判定が変わらない | `TestFormattingInsensitivity.*` |
| cwd 非依存 | `test_result_does_not_depend_on_cwd` |

## 実装側が「テストを自分に都合よく」できないよう固定した点

1. **未評価を PASS に化けさせない** — `--out-dir` 未指定時の DATE-03 は `NOT-REQUESTED` であり、
   `PASS` でも `SKIP` でもないことを 3 方向から assert している。
   `glossary` 空配列も、checked=0 PASS にする代わりに注記の出力を必須にした。
2. **担当外を勝手に拾わない** — 意味のない lead-line / 判断軸 (C06)、400 字超の本文 (C52 = C12)、
   slot の並び (C51 の正本 = C12)、外部参照 (C16)、alt 欠落 (C17)、hero 3 要素と section goal (C22)、
   ディレクトリの種別語彙と slug (C19) を持つ入力が **exit 0 で通ること**を assert している。
   C18 がこれらへはみ出すと赤になる。
3. **担当を勝手に手放さない** — 検査アンカー不在・date-pill 不在を「他が見るから」と
   checked=0 PASS へ畳むと赤になる。
4. **日付の単一ソース** — source に `today(` / `datetime.now` / `utcnow` / `time.time(` が
   1 件でもあれば赤。かつ `config.date` が 1999 年でも一致すれば PASS になることで、
   「今日の日付と比べる」実装を通さない。
5. **部品 id を焼き込ませない** — カタログにしか無い B16 / B17 / IMG / DIAGRAM / TEXT を
   具体部品として認識させ、source が `handout-parts.json` を読むことも assert している。
6. **stdout 書式の固定** — 1 行目・9 行の固定順 (`LANG-01, LANG-04..07, DATE-01..04`)・
   `checked=` / `violations=` の存在・OUT-OF-SCOPE が最後、をすべて assert している。
   存在しない `LANG-02` / `LANG-03` を出さないことも固定した。

## 未確定事項 (gaps / 実装前または P06 で決着が要る)

1. **`--json-report` のキー名スキーマがブリーフに無い。** 本テストは
   「valid JSON の object であること」「全 detection id が現れること」
   「`NOT-REQUESTED` と本文別日付の info が現れること」「バイト一致すること」までしか固定していない。
2. **`data-hb-glossary-first` に owner がいない。** LANG-01 の false_positive_risk 緩和策として
   ブリーフが挙げるアンカー属性 (`first_occurrence_anchor` / `data-hb-glossary-first`) は、
   C11 の `html_attribute_contract` に**存在しない** (contract 側は
   `data-hb-glossary-term` / `-plain` / `-scope` の 3 つのみ)。
   語彙の正本が無い属性をテストで固定すると第二正本を作ることになるため、本テストは
   アンカー経路を一切検査していない。採用するなら C11 の contract へ先に足す必要がある。
3. **section スコープ glossary の扱いが未定義。** C12 は `section[].glossary` を
   document 側へマージせず保持する。C18 LANG-01 は `config.glossary[]` としか書いておらず、
   section スコープ宣言を検査対象に含めるか・初出をその section 内に限るかが決まっていない。
   本テストは document スコープのみを固定した。
4. **`config.date` 自体が不正書式のときの挙動が未定義。** exit 2 (未正規化として弾く) か
   DATE-02 の違反かが書かれていない。本テストは衝突を避け、`config.date` は常に正規化済みの
   正しい値にし、壊すのは date-pill 側だけにしている。
5. **LANG-07 の「feature 見出し」の同定方法が未定義。** `data-hb-slot="feature"` 部品の
   「見出しテキスト」が `h1..h6` を指すのか最初の text node を指すのかが書かれていない。
   fixture は `<h3>` を使っており、実装が別の同定をするとこの前提が崩れる。
6. **DATE-01 の曜日・和暦併記** はブリーフの open_question のまま。現案 (完全一致 = 併記は一律違反) を
   そのまま赤で固定した。`data-hb-field="date-text"` の子要素へ切り替える案を採るなら、
   `test_weekday_suffix_is_a_violation` / `test_japanese_era_is_a_violation` を先に破棄する必要がある。
7. **LANG-01 の合格形**は括弧書きのみ (goal-spec C16 の文言に従う)。
   参照 §5 の「用語 ＝ 言い換え」形を許すなら `test_equals_form_is_a_violation` を破棄すること。
8. **R21 のうち C18 が owner でない項目** (C51 の判定正本 = C12、C52 の
   `text_limits.block_body_max_chars` と B10 畳み込み = C12 `--normalize`) は
   検査へ含めず、`TestR21NonOwnedItemsAreOutOfScope` で**含めないこと自体**を赤で固定した。
   C18 が持つのは C51 の描画テキスト面 (LANG-07) のみ。
9. **lead_line / judgment_axis の文言が config と一致するか**は、どの detection にも書かれていない
   (C22 NAR-02/NAR-03 が hero と section goal について持つ形の lead_line 版が無い)。
   本テストは HTML 側だけを書き換える fixture を多用しており、文言一致検査を前提にしていない。
   一致検査を C18 へ足すなら、その前に owner を決める必要がある。
