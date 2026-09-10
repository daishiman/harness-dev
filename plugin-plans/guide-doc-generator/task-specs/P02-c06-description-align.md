---
id: "P02-c06-description-align"
title: "C06 の description を inventory / brief / 出荷物の 3 者で一致させる"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/component-inventory.json"
acceptance_criterion: "inventory C06 / agent-brief-C06.json / handout-readability-reviewer.md の description が同一文字列で、lint-skill-description.py が exit0 になること"
objective: "inventory C06 の description が句点を欠き lint-skill-description.py:53 の ALLOWED_TAIL ('使う。'/'読む。'/'起動する。') を満たさないため、AC1 (inventory 一致 かつ lint exit0) が構造的に充足不能"
verify: "inventory C06 / agent-brief-C06.json / handout-readability-reviewer.md の description が同一文字列で、lint-skill-description.py が exit0 になること"
depends_on: ["P02-C06-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c06-description-align.md"]
consumes: []
---

# C06 の description を inventory / brief / 出荷物の 3 者で一致させる

## 由来

build 実行中に `P02-C06-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: inventory C06 の description が句点を欠き lint-skill-description.py:53 の ALLOWED_TAIL ('使う。'/'読む。'/'起動する。') を満たさないため、AC1 (inventory 一致 かつ lint exit0) が構造的に充足不能

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C06-01.json`

## 作業

`plugin-plans/guide-doc-generator/component-inventory.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c06-description-align.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

inventory C06 / agent-brief-C06.json / handout-readability-reviewer.md の description が同一文字列で、lint-skill-description.py が exit0 になること
