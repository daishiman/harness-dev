---
id: "P02-c03-axis-vocab-removal"
title: "C03 の key_constraints から軸名の列挙を除き C06 参照へ寄せる"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/skill-brief-C03.json"
acceptance_criterion: "skill-brief-C03.json に軸名 (lead-line / decision-line / glossary / goal-chain / sentence-flow / concreteness / opening-order / visual-fit / card-granularity / nav-scannability) が 1 件も現れず、軸の正本として agent-brief-C06.json#output_contract.returns の axis を参照する記述だけが残ること"
objective: "P02-c06-r25-axes の AC は『C03 側は軸を持たないまま (正本が C06 1 箇所)』を求めるが、skill-brief-C03.json の key_constraints が軸名 6 種 (lead-line / decision-line / glossary / goal-chain / sentence-flow / concreteness) をそのまま列挙している。同 brief の open_questions[0] は『本 brief は軸名を 1 つも書かない』と宣言しており、同一ブリーフ内で宣言と実体が食い違う。C06 側は 10 種へ増えているため、C03 の列挙は旧 6 種のまま古びた状態でもある。write_scope が C06 のため本ノードでは直せない"
verify: "skill-brief-C03.json に軸名 (lead-line / decision-line / glossary / goal-chain / sentence-flow / concreteness / opening-order / visual-fit / card-granularity / nav-scannability) が 1 件も現れず、軸の正本として agent-brief-C06.json#output_contract.returns の axis を参照する記述だけが残ること"
depends_on: ["P02-c06-r25-axes"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c03-axis-vocab-removal.md"]
consumes: []
---

# C03 の key_constraints から軸名の列挙を除き C06 参照へ寄せる

## 由来

build 実行中に `P02-c06-r25-axes` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P02-c06-r25-axes の AC は『C03 側は軸を持たないまま (正本が C06 1 箇所)』を求めるが、skill-brief-C03.json の key_constraints が軸名 6 種 (lead-line / decision-line / glossary / goal-chain / sentence-flow / concreteness) をそのまま列挙している。同 brief の open_questions[0] は『本 brief は軸名を 1 つも書かない』と宣言しており、同一ブリーフ内で宣言と実体が食い違う。C06 側は 10 種へ増えているため、C03 の列挙は旧 6 種のまま古びた状態でもある。write_scope が C06 のため本ノードでは直せない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-c06-r25-axes.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/skill-brief-C03.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c03-axis-vocab-removal.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

skill-brief-C03.json に軸名 (lead-line / decision-line / glossary / goal-chain / sentence-flow / concreteness / opening-order / visual-fit / card-granularity / nav-scannability) が 1 件も現れず、軸の正本として agent-brief-C06.json#output_contract.returns の axis を参照する記述だけが残ること
