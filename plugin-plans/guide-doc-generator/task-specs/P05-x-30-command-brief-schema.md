---
id: "P05-x-30-command-brief-schema"
title: "command-brief 用 JSON Schema を harness-creator へ追加する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/harness-creator/skills/run-skill-create/schemas/"
acceptance_criterion: "command-brief.schema.json が存在し、command-brief-C07/C08/C09.json の 3 本を Draft202012Validator で検証して errors 0 になること"
objective: "command-brief 用 JSON Schema が harness-creator に存在せず (skill-brief / prompt-brief のみ)、C07/C08/C09 の 3 本が構造検証を受けずに積まれている"
verify: "command-brief.schema.json が存在し、command-brief-C07/C08/C09.json の 3 本を Draft202012Validator で検証して errors 0 になること"
depends_on: ["P02-C09-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-30-command-brief-schema.md"]
consumes: []
---

# command-brief 用 JSON Schema を harness-creator へ追加する

## 由来

build 実行中に `P02-C09-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: command-brief 用 JSON Schema が harness-creator に存在せず (skill-brief / prompt-brief のみ)、C07/C08/C09 の 3 本が構造検証を受けずに積まれている

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C09-01.json`

## 作業

`plugins/harness-creator/skills/run-skill-create/schemas/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-30-command-brief-schema.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

command-brief.schema.json が存在し、command-brief-C07/C08/C09.json の 3 本を Draft202012Validator で検証して errors 0 になること
