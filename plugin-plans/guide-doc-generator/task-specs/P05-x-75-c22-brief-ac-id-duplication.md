---
id: "P05-x-75-c22-brief-ac-id-duplication"
title: "script-brief-C22.json の AC id 重複と expected 破壊を復旧する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C22.json"
acceptance_criterion: "acceptance_checks[].id が一意であること。1 つ目の AC-C22-R21-56b の expected が HEAD 原文 (exit 0、NAR-07 PASS。概念図の存在自体は禁じておらず、実画面より前に置くことだけが禁止であることの回帰テスト) へ復元されていること。P03-x-04 で追加された方が AC-C22-R21-56d へ改番されていること"
objective: "P03-x-04 (orange) が AC-C22-R21-56b を新規 id のつもりで追加したが同 id が既存だった。結果 acceptance_checks に id 重複 2 件が生じ、既存 56b の expected が上書きで破壊されている。配列要素の id 重複なので json.load では検出できない。dispatcher が全 brief を横断確認したところ重複は C22 のみ。原意は tests/verify-handout-narrative.py/test_nar07_demo_first.py:108 test_ac56b_screenshot_inserted_before_diagram_passes が保持しており現在も緑。orange の自己申告"
verify: "acceptance_checks[].id が一意であること。1 つ目の AC-C22-R21-56b の expected が HEAD 原文 (exit 0、NAR-07 PASS。概念図の存在自体は禁じておらず、実画面より前に置くことだけが禁止であることの回帰テスト) へ復元されていること。P03-x-04 で追加された方が AC-C22-R21-56d へ改番されていること"
depends_on: ["P04-C22-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-75-c22-brief-ac-id-duplication.md"]
consumes: []
---

# script-brief-C22.json の AC id 重複と expected 破壊を復旧する

## 由来

build 実行中に `P04-C22-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P03-x-04 (orange) が AC-C22-R21-56b を新規 id のつもりで追加したが同 id が既存だった。結果 acceptance_checks に id 重複 2 件が生じ、既存 56b の expected が上書きで破壊されている。配列要素の id 重複なので json.load では検出できない。dispatcher が全 brief を横断確認したところ重複は C22 のみ。原意は tests/verify-handout-narrative.py/test_nar07_demo_first.py:108 test_ac56b_screenshot_inserted_before_diagram_passes が保持しており現在も緑。orange の自己申告

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C22.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-75-c22-brief-ac-id-duplication.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

acceptance_checks[].id が一意であること。1 つ目の AC-C22-R21-56b の expected が HEAD 原文 (exit 0、NAR-07 PASS。概念図の存在自体は禁じておらず、実画面より前に置くことだけが禁止であることの回帰テスト) へ復元されていること。P03-x-04 で追加された方が AC-C22-R21-56d へ改番されていること
