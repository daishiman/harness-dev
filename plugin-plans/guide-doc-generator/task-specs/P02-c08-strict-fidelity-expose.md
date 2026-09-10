---
id: "P02-c08-strict-fidelity-expose"
title: "C08 へ --strict-fidelity を露出するか裁定し inventory の argument-hint を揃える"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/component-inventory.json"
acceptance_criterion: "inventory C08 の argument-hint と command-brief-C08.json の arguments が同一のフラグ集合を持ち、--strict-fidelity の採否理由が 1 箇所に記録されていること"
objective: "C20 の --strict-fidelity が C08 から利用者へ露出しておらず、逆抽出の忠実度を厳しく見る選択肢が無い。argument-hint は inventory と一致必須のため inventory 変更を伴う"
verify: "inventory C08 の argument-hint と command-brief-C08.json の arguments が同一のフラグ集合を持ち、--strict-fidelity の採否理由が 1 箇所に記録されていること"
depends_on: ["P02-C08-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c08-strict-fidelity-expose.md"]
consumes: []
---

# C08 へ --strict-fidelity を露出するか裁定し inventory の argument-hint を揃える

## 由来

build 実行中に `P02-C08-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C20 の --strict-fidelity が C08 から利用者へ露出しておらず、逆抽出の忠実度を厳しく見る選択肢が無い。argument-hint は inventory と一致必須のため inventory 変更を伴う

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C08-01.json`

## 作業

`plugin-plans/guide-doc-generator/component-inventory.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c08-strict-fidelity-expose.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

inventory C08 の argument-hint と command-brief-C08.json の arguments が同一のフラグ集合を持ち、--strict-fidelity の採否理由が 1 箇所に記録されていること
