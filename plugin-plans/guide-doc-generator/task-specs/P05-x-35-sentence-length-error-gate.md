---
id: "P05-x-35-sentence-length-error-gate"
title: "文長判定を warning から error へ昇格し config#sentence を正本にする"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "handout-visual-policy.json#sentence が正本となり、閾値超過が E-TEXT-* として exit1 で build を止める。Python 定数の重複保持が 0 件"
objective: "handout-visual-policy.json に sentence キーが存在せず ('sentence' in policy が False)、C05/C06/C12/C18 の 4 brief が名指す正本が不在。出荷 validate-handout-config.py は LONG_SENTENCE_CHARS=45 / LONG_SENTENCE_COUNT=3 を Python 定数で持ち :1425 で W-SENTENCE-LONG (warning) としか出さないため build を止めない。利用者の最優先要件『文章が長ったらしく何行も書くのを絶対に防ぐ』が機構として効いていない"
verify: "handout-visual-policy.json#sentence が正本となり、閾値超過が E-TEXT-* として exit1 で build を止める。Python 定数の重複保持が 0 件"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-35-sentence-length-error-gate.md"]
consumes: []
---

# 文長判定を warning から error へ昇格し config#sentence を正本にする

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: handout-visual-policy.json に sentence キーが存在せず ('sentence' in policy が False)、C05/C06/C12/C18 の 4 brief が名指す正本が不在。出荷 validate-handout-config.py は LONG_SENTENCE_CHARS=45 / LONG_SENTENCE_COUNT=3 を Python 定数で持ち :1425 で W-SENTENCE-LONG (warning) としか出さないため build を止めない。利用者の最優先要件『文章が長ったらしく何行も書くのを絶対に防ぐ』が機構として効いていない

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-35-sentence-length-error-gate.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

handout-visual-policy.json#sentence が正本となり、閾値超過が E-TEXT-* として exit1 で build を止める。Python 定数の重複保持が 0 件
