---
id: "P02-visual-policy-readers-c11"
title: "handout-visual-policy.json の _meta.readers へ C11 を追加する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/config/handout-visual-policy.json"
acceptance_criterion: "_meta.readers に C11 が含まれ、かつ列挙された全 reader が実際に本ファイルを読む component であること (逆方向の余剰も 0)"
objective: "config/handout-visual-policy.json の _meta.readers に C11 が列挙されていない。C11 は algorithm step 14/16 および B01/B02 で本ファイルを直接 json.load して読むため、readers 欠落は依存関係の宣言漏れであり、閾値変更時の影響範囲追跡が効かなくなる"
verify: "_meta.readers に C11 が含まれ、かつ列挙された全 reader が実際に本ファイルを読む component であること (逆方向の余剰も 0)"
depends_on: ["P02-C11-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-visual-policy-readers-c11.md"]
consumes: []
---

# handout-visual-policy.json の _meta.readers へ C11 を追加する

## 由来

build 実行中に `P02-C11-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: config/handout-visual-policy.json の _meta.readers に C11 が列挙されていない。C11 は algorithm step 14/16 および B01/B02 で本ファイルを直接 json.load して読むため、readers 欠落は依存関係の宣言漏れであり、閾値変更時の影響範囲追跡が効かなくなる

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C11-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/config/handout-visual-policy.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-visual-policy-readers-c11.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

_meta.readers に C11 が含まれ、かつ列挙された全 reader が実際に本ファイルを読む component であること (逆方向の余剰も 0)
