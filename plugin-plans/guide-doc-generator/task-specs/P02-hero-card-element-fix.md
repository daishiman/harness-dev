---
id: "P02-hero-card-element-fix"
title: "hero-card の要素名を決定ファイルへ昇格させる"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/improvement/hero-card-decision.json"
acceptance_criterion: "improvement/hero-card-decision.json が hero カードの DOM を .hero-card-grid > .hero-card として明示し、script-brief-C11.json:352 と一致すること"
objective: "決定ファイルは『section-card と同系の hero-card 要素』としか書いておらず要素名を固定していない。build が <section id=...> を選ぶと C18 の LANG-04 が hero へ lead_line を要求する誤検出になる (C18 側は先回りで塞いだが、決定ファイルが緩いままだと再発する)"
verify: "improvement/hero-card-decision.json が hero カードの DOM を .hero-card-grid > .hero-card として明示し、script-brief-C11.json:352 と一致すること"
depends_on: ["P02-C18-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-hero-card-element-fix.md"]
consumes: []
---

# hero-card の要素名を決定ファイルへ昇格させる

## 由来

build 実行中に `P02-C18-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 決定ファイルは『section-card と同系の hero-card 要素』としか書いておらず要素名を固定していない。build が <section id=...> を選ぶと C18 の LANG-04 が hero へ lead_line を要求する誤検出になる (C18 側は先回りで塞いだが、決定ファイルが緩いままだと再発する)

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C18-01.json`

## 作業

`plugin-plans/guide-doc-generator/improvement/hero-card-decision.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-hero-card-element-fix.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

improvement/hero-card-decision.json が hero カードの DOM を .hero-card-grid > .hero-card として明示し、script-brief-C11.json:352 と一致すること
