---
id: "P02-root-resolution-align"
title: "C17 / C09 の実体解決を C15 と同じ 4 段へ揃える"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/"
acceptance_criterion: "script-brief-C17.json と command-brief-C09.json の root 解決が plugin.json の name 照合を含む 4 段になり、C15 と同じく全段外れた場合の挙動が明記されていること"
objective: "実体解決が C17 (HB_ROOT→CLAUDE_PLUGIN_ROOT→2階層上) と C09 ($CLAUDE_PLUGIN_ROOT のみ) で manifest name 照合を欠く 3 段へ縮退。.claude/ 平置き projection では CLAUDE_PLUGIN_ROOT が 1 値しか持てず他 plugin の root を掴みうる"
verify: "script-brief-C17.json と command-brief-C09.json の root 解決が plugin.json の name 照合を含む 4 段になり、C15 と同じく全段外れた場合の挙動が明記されていること"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-root-resolution-align.md"]
consumes: []
---

# C17 / C09 の実体解決を C15 と同じ 4 段へ揃える

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実体解決が C17 (HB_ROOT→CLAUDE_PLUGIN_ROOT→2階層上) と C09 ($CLAUDE_PLUGIN_ROOT のみ) で manifest name 照合を欠く 3 段へ縮退。.claude/ 平置き projection では CLAUDE_PLUGIN_ROOT が 1 値しか持てず他 plugin の root を掴みうる

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-x-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-root-resolution-align.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C17.json と command-brief-C09.json の root 解決が plugin.json の name 照合を含む 4 段になり、C15 と同じく全段外れた場合の挙動が明記されていること
