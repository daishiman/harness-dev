---
id: "P05-x-14-ac-denylist-delegate"
title: "C14 の AC から絵文字/外部参照 denylist の複製を除去し C16 委譲へ寄せる"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C14.json"
acceptance_criterion: "script-brief-C14.json の AC-C14-3 / AC-C14-4 が U+1F300-1FAFF / U+2600-27BF / U+FE0F および http:// https:// // xlink:href を独自列挙せず、C16 の scan_emoji / scan_external_references の呼出し結果で判定していること"
objective: "G-03 が撤去したはずの Unicode ブロック denylist が C14 の test 側にだけ残存。C15 が過去に踏んだ『test だけが古い denylist を持つ』構図と同型。現時点の実害は 0 だが正本の二重化"
verify: "script-brief-C14.json の AC-C14-3 / AC-C14-4 が U+1F300-1FAFF / U+2600-27BF / U+FE0F および http:// https:// // xlink:href を独自列挙せず、C16 の scan_emoji / scan_external_references の呼出し結果で判定していること"
depends_on: ["P02-C16-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-14-ac-denylist-delegate.md"]
consumes: []
---

# C14 の AC から絵文字/外部参照 denylist の複製を除去し C16 委譲へ寄せる

## 由来

build 実行中に `P02-C16-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: G-03 が撤去したはずの Unicode ブロック denylist が C14 の test 側にだけ残存。C15 が過去に踏んだ『test だけが古い denylist を持つ』構図と同型。現時点の実害は 0 だが正本の二重化

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C16-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C14.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-14-ac-denylist-delegate.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C14.json の AC-C14-3 / AC-C14-4 が U+1F300-1FAFF / U+2600-27BF / U+FE0F および http:// https:// // xlink:href を独自列挙せず、C16 の scan_emoji / scan_external_references の呼出し結果で判定していること
