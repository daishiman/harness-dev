---
id: "P05-x-03-acceptance-hardening"
title: "P05-x-03 の acceptance_criterion を節単位の視覚部品充足へ強化する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/task-specs/P05-x-03.md"
acceptance_criterion: "P05-x-03.md の acceptance_criterion が、config/handout-purposes.json の全 preset の全 main セクションについて (1) recommended_parts に DIAGRAM が 1 件以上 (2) 同じく IMG が 1 件以上 (3) section_order[] の各要素が image_role を screenshot|illustration のいずれかで宣言、の 3 点を明示要求すること。キー名の存在のみを問う表現を残さないこと"
objective: "P05-x-03 の acceptance_criterion がキー名の存在列挙に留まり、値が空でも通過する。実測: config/handout-purposes.json は 8 preset 全ての全節で DIAGRAM 0 件、IMG は lecture.demo の 1 件のみ、section_order[].image_role は未定義。R25 で W-DIAGRAM-FEW / E-IMAGE-ABSENT を error 水準へ確定した一方でプリセット側の供給が空のままであり、第1稿が fail-closed で止まる確率が最大化している。プリセットは充足を LLM 判断に依存させない唯一の決定論的供給源なので、受入条件を『節ごとに DIAGRAM>=1 かつ IMG>=1 かつ image_role が enum 値で宣言済み』へ強化する必要がある"
verify: "P05-x-03.md の acceptance_criterion が、config/handout-purposes.json の全 preset の全 main セクションについて (1) recommended_parts に DIAGRAM が 1 件以上 (2) 同じく IMG が 1 件以上 (3) section_order[] の各要素が image_role を screenshot|illustration のいずれかで宣言、の 3 点を明示要求すること。キー名の存在のみを問う表現を残さないこと"
depends_on: ["P02-C23-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-03-acceptance-hardening.md"]
consumes: []
---

# P05-x-03 の acceptance_criterion を節単位の視覚部品充足へ強化する

## 由来

build 実行中に `P02-C23-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P05-x-03 の acceptance_criterion がキー名の存在列挙に留まり、値が空でも通過する。実測: config/handout-purposes.json は 8 preset 全ての全節で DIAGRAM 0 件、IMG は lecture.demo の 1 件のみ、section_order[].image_role は未定義。R25 で W-DIAGRAM-FEW / E-IMAGE-ABSENT を error 水準へ確定した一方でプリセット側の供給が空のままであり、第1稿が fail-closed で止まる確率が最大化している。プリセットは充足を LLM 判断に依存させない唯一の決定論的供給源なので、受入条件を『節ごとに DIAGRAM>=1 かつ IMG>=1 かつ image_role が enum 値で宣言済み』へ強化する必要がある

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C23-01.json`

## 作業

`plugin-plans/guide-doc-generator/task-specs/P05-x-03.md` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-03-acceptance-hardening.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

P05-x-03.md の acceptance_criterion が、config/handout-purposes.json の全 preset の全 main セクションについて (1) recommended_parts に DIAGRAM が 1 件以上 (2) 同じく IMG が 1 件以上 (3) section_order[] の各要素が image_role を screenshot|illustration のいずれかで宣言、の 3 点を明示要求すること。キー名の存在のみを問う表現を残さないこと
