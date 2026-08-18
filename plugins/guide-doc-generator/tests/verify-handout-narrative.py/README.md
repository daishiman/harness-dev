# C22 `verify-handout-narrative.py` 受入テスト (P04-C22-01 / 赤で固定)

本ディレクトリは **実装より先に** 判定基準を確定させるための受入テストである。
実装本体 (`plugins/guide-doc-generator/scripts/verify-handout-narrative.py`) は
**まだ存在しない**。したがって現時点で全 186 件が赤であることが正しい状態であり、
P05 の実装がこのテストを通すことをもって受入とする。

契約の正本は `plugin-plans/guide-doc-generator/briefs/script-brief-C22.json`。
本テストは推測で契約を発明していない (足りない箇所は末尾の「未確定事項」に記す)。

## 実行

```bash
python3 -m unittest discover -s plugins/guide-doc-generator/tests/verify-handout-narrative.py -p 'test_*.py'
```

Python 3.10+ の標準ライブラリのみ。テストは script を `subprocess` で起動し、
exit code / stdout / stderr / `--json-report` の 4 面だけを観測する
(実装の内部関数へは一切依存しない = 実装の書き方を縛らずに判定だけを固定する)。

## ファイル構成

| ファイル | 固定した面 | 件数 |
|---|---|---|
| `_support.py` | fixture 生成と実行ヘルパ (判定基準は持たない) | — |
| `test_cli_contract.py` | argv / exit code / stdout 書式 / OUT-OF-SCOPE / json-report / write_scope | 39 |
| `test_nar01_nar02_hero.py` | NAR-01 (冒頭 3 要素) / NAR-02 (文言一致と正規化) / アンカー不在 | 30 |
| `test_nar03_nar04_section_goal.py` | NAR-03 (セクション冒頭のゴール) / NAR-04 (常時表示) | 32 |
| `test_nar05_nar06_nav_chain.py` | NAR-05 (nav のゴール参照) / NAR-06 (連鎖表) / nav 不在 | 25 |
| `test_nar07_demo_first.py` | NAR-07 = CR-DEMO1 (実画面先行の**禁止**) と SKIP 開示 | 25 |
| `test_nar08_appendix_order.py` | NAR-08 (付録の描画順隔離 / logistics の混入) | 14 |
| `test_scope_and_determinism.py` | R11・R18・C16 面の**担当外**であることの回帰 / 再現性 | 21 |

## 契約 id とテストの対応表

### detection (NAR-*)

| 契約 id | 何を赤で固定したか | 代表テスト |
|---|---|---|
| NAR-01 | purpose / background / goal が hero 内にちょうど 1 個ずつ非空で、最初の `<section id>` より前、文書順 purpose → background → goal | `TestNar01Presence.*`, `TestNar01Position.*` |
| NAR-02 | 冒頭 3 要素の文言が config と正規化後に完全一致。NFKC + 空白圧縮 + トリムだけを吸収し、句読点除去はしない | `TestNar02TextMatch.*`, `TestNar02Normalization.*` |
| NAR-03 | 全 section が `section_goal` をちょうど 1 個、`lead_line` と具体部品より前に持ち、文言が config と一致。config 側 goal 空も本ゲートが独立に FAIL | `TestNar03Presence.*`, `TestNar03Position.*`, `TestNar03ConfigSideEmptyGoal.*` |
| NAR-04 | hidden / aria-hidden / インライン display:none / 祖先 `<details>` / 通常 CSS 規則での非表示は違反。**メディアクエリ内は対象外** | `TestNar04AlwaysVisible.*` |
| NAR-05 | nav の全 `a[href^="#"]` が `data-hb-nav-goal` または `title` を持ち、両方あるときは**両方**が section.goal と一致。nav 不在は checked=0 PASS ではなく exit 1 | `TestNar05NavGoalReference.*`, `TestNar05NavAbsent.*` |
| NAR-06 | config と HTML の section id 集合が完全一致、goal 空 0 件、対応表を json-report へ必ず出力。`<section>` かつ id を持つものだけが対象 | `TestNar06Chain.*` |
| NAR-07 / **CR-DEMO1** | demo_first のとき、最初の main セクションの最初の提示物が screenshot / live_demo B17 でなければ違反。DIAGRAM・B14・B07・120 字超段落の先行を**禁止**として判定 | `TestNar07Prohibition.*`, `TestNar07Allowed.*`, `TestNar07Skip.*`, `TestNar07SourceOfTruth.*` |
| NAR-08 | appendix が全 main より後、`data-hb-section-role="appendix"` を持ち、nav 順も同様。`section_kind=logistics` が role=main なら違反 | `TestNar08*` |

### acceptance_checks (AC-*)

| AC id | テスト |
|---|---|
| AC-C22-01 | `TestHappyPathContract.*` (exit 0 / stderr 空 / detections 件数ちょうどの固定順 / OUT-OF-SCOPE) |
| AC-C22-02 | `test_ac02_goal_removed` |
| AC-C22-03 | `test_ac03_goal_text_altered`, `test_ac03_stderr_shows_both_values` |
| AC-C22-04 | `test_ac04_goal_at_section_tail`, `test_ac04_reason_mentions_not_at_top` |
| AC-C22-05 | `TestNar03ConfigSideEmptyGoal.*` |
| AC-C22-06 | `test_ac06_details_wrapper` |
| AC-C22-07 | `test_ac07_media_print_display_none_is_not_a_violation` (C17 PRINT-03 との責務衝突の回帰) |
| AC-C22-08 | `test_ac08_anchor_without_any_goal_attribute` |
| AC-C22-09 | `test_ac09_nav_goal_and_title_disagree`, `test_ac09_partial_match_is_not_pass` |
| AC-C22-10 | `test_ac10_section_missing_from_html`, `test_ac10_report_contains_chain_table` |
| AC-C22-R21-56a | `test_ac56a_diagram_first_is_violation` / `..._message_states_diagram_before_real_screen` / `..._message_carries_line_number` |
| AC-C22-R21-56b | `test_ac56b_screenshot_inserted_before_diagram_passes` |
| AC-C22-R21-56c | `test_figure_role_image_first_is_violation` + `TestNar07Skip.*` |
| AC-C22-R21-48 | `TestNar08Logistics.*` (描画段のゲート。構成データ段の `E-SECTION-ROLE-CONFLICT` は C12 側テストの担当) |
| AC-C22-11 | `TestR11IsOutOfScope.*` (goal-spec C40 の分界) |
| AC-C22-12 | `TestR18IsOutOfScope.*` |
| AC-C22-13 | `TestArgvAndExit2.*` |
| AC-C22-14 | `TestDeterminism.*` |
| AC-C22-15 | `test_ac15_detection_id_column_matches_detections_exactly`, `test_ac01_detection_line_count_matches_detections` (件数の数値リテラルを置かない / P04-x-05 裁定 B) |

### failure_modes と横断契約

| 契約 | テスト |
|---|---|
| 検査アンカーが 1 個も無い → exit 1 + 必要な field 名を列挙 | `TestNoAnchorsAtAll.*` |
| `sections` 0 件 → exit 2 | `test_config_sections_empty_is_exit2` |
| 整形差 (改行 / インデント) では FAIL にしない | `test_formatting_difference_does_not_fail` |
| nav 不在 → exit 1 | `TestNar05NavAbsent.*` |
| single_writer (`--json-report` 以外へ書かない) | `TestWriteScope.*` |
| 早期 return で後続 detection を落とさない | `test_all_detections_reported_even_when_first_fails` |
| 違反 1 件につき stderr 1 行 (サマリ合計と一致) | `test_stderr_row_count_matches_summary_total` |

## 実装側が「テストを自分に都合よく」できないよう固定した点

1. **未評価を PASS に化けさせない** — `explain_first` の NAR-07 は `SKIP` 行であり、
   `PASS` でも `checked=0` でもないことを直接 assert している。
2. **禁止形であること** — `test_diagram_then_screenshot_is_violation` が、
   「資料のどこかに実画面がある」では満たされないことを固定する。
3. **担当外を勝手に拾わない** — R11 / R18 / 外部参照の欠陥がある HTML を
   exit 0 で通すことを assert しており、C18 / C16 の面を C22 が取り込むと赤になる。
4. **担当を勝手に手放さない** — config 側 goal 空 (C12 の面) や nav 不在 (C16 SC-08 の面) を
   「他が見るから」と PASS へ畳むと赤になる。
5. **stdout 書式の固定** — 1 行目・`detections` 定義順ちょうどの固定順 (NAR-01..NAR-10)・`checked=` / `violations=` の存在・
   OUT-OF-SCOPE が最後、をすべて assert している。

## 未確定事項 (実装前に決着が要る / gaps)

- `--json-report` の**キー名スキーマ**がブリーフに書かれていない。本テストは
  「valid JSON であること」「NAR-01..NAR-10 と全 section id が現れること」
  「同一入力でバイト一致すること」までしか固定していない。
- NAR-05 の補助属性を `data-hb-nav-goal` 必須へ一本化するか `title` 単独も許すかが
  ブリーフの open_question のまま。本テストは
  「両方あるなら両方一致」「両方無いなら違反」だけを固定し、
  `title` 単独の可否には踏み込んでいない。
- NAR-04 の CSS 判定は近似 (祖先条件付き・詳細度・カスケード未解決)。
  実描画による検証を置くかは P06 の判断。本テストは
  「メディアクエリ内は対象外」「単純セレクタの display:none / visibility:hidden は違反」
  の 2 点だけを固定する。
- team-lead の指示にあった **R11 (抽象↔具体の往復・用語の初出言い換え) の検査を C22 に持たせる案**は、
  ブリーフ・`component-inventory.json` の C22/C18 purpose・phase-02「検証面の独立」・
  および AC-C22-11 / AC-C22-12 (R11・R18 欠落で exit 0 を要求) と正面から矛盾する。
  本テストは**正本であるブリーフに従い C22 を R19 専任として固定**した。
  R11 側を C22 に寄せる決定を下す場合、AC-C22-11 / AC-C22-12 と
  `TestR11IsOutOfScope` / `TestR18IsOutOfScope` を先に破棄する必要がある。
