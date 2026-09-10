---
id: "P05-x-45-root-resolution-shipped"
title: "C17 / C09 の 4 段実体解決を出荷物へ反映する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "両出荷物が 4 段解決を行い、全段外れで exit 2 となる"
objective: "P03-x-02 で C17 brief (3 段・manifest 照合 0 件) と C09 brief (1 段展開のみ) を 4 段の参照形へ揃えた。正本は plan レベル=inventory#envelope_design.env_resolution / 実装レベル=script-brief-C15.json:39。出荷側 verify-handout-a11y-print.py と commands/handout-verify.md は未追随。.claude 平置き projection では CLAUDE_PLUGIN_ROOT が 1 値しか持てず manifest 照合を欠くと他 plugin の root を掴みうる"
verify: "両出荷物が 4 段解決を行い、全段外れで exit 2 となる"
depends_on: ["P03-x-02"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-45-root-resolution-shipped.md"]
consumes: []
---

# C17 / C09 の 4 段実体解決を出荷物へ反映する

## 由来

build 実行中に `P03-x-02` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P03-x-02 で C17 brief (3 段・manifest 照合 0 件) と C09 brief (1 段展開のみ) を 4 段の参照形へ揃えた。正本は plan レベル=inventory#envelope_design.env_resolution / 実装レベル=script-brief-C15.json:39。出荷側 verify-handout-a11y-print.py と commands/handout-verify.md は未追随。.claude 平置き projection では CLAUDE_PLUGIN_ROOT が 1 値しか持てず manifest 照合を欠くと他 plugin の root を掴みうる

**発見時の証跡**: `plugin-plans/guide-doc-generator/briefs/`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-45-root-resolution-shipped.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

両出荷物が 4 段解決を行い、全段外れで exit 2 となる
