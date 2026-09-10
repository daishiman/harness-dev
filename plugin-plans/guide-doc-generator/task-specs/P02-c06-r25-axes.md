---
id: "P02-c06-r25-axes"
title: "C06 の評価軸へ R25 の視覚・構造 4 面を追加する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/agent-brief-C06.json"
acceptance_criterion: "agent-brief-C06.json の axis 語彙に R25 の 4 面が REQ 番号つきで追加され、C03 側は軸を持たないまま (正本が C06 1 箇所) であること"
objective: "R25 の 9 要求 (冒頭のゴール→全体像→カード順・図解と本文の噛み合い・カード粒度・nav ラベルの拾いやすさ) に対応する評価軸が C06 の axis 6 種に無く、意味側の担当が不在"
verify: "agent-brief-C06.json の axis 語彙に R25 の 4 面が REQ 番号つきで追加され、C03 側は軸を持たないまま (正本が C06 1 箇所) であること"
depends_on: ["P02-C03-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c06-r25-axes.md"]
consumes: []
---

# C06 の評価軸へ R25 の視覚・構造 4 面を追加する

## 由来

build 実行中に `P02-C03-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: R25 の 9 要求 (冒頭のゴール→全体像→カード順・図解と本文の噛み合い・カード粒度・nav ラベルの拾いやすさ) に対応する評価軸が C06 の axis 6 種に無く、意味側の担当が不在

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C03-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/agent-brief-C06.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c06-r25-axes.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

agent-brief-C06.json の axis 語彙に R25 の 4 面が REQ 番号つきで追加され、C03 側は軸を持たないまま (正本が C06 1 箇所) であること
