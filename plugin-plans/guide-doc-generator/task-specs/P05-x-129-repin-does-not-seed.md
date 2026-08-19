---
id: "P05-x-129-repin-does-not-seed"
title: "外ループ再入時に task-state へ新 node を seed する手順を機構化する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/harness-creator/scripts/sync-task-state.py"
acceptance_criterion: "node を 1 件以上増やした task-graph に対し外ループ再入の再 pin を 1 回行った後、追加呼出しなしで task-state.nodes 数が graph の node 数と一致することを実測する。一致しない実装のままなら、SKILL の外ループ手順へ seed 呼出しを明記し、欠落時に赤くなる検査を置く。"
objective: "sync-task-state.py の --repin-graph-hash と --initialize-from-graph が main の elif 排他になっており、外ループ再入の再 pin では graph に増えた node が task-state へ seed されない。実測: drain で node が 138→274 になった直後の再 pin 後も task-state.nodes は 138 のままで、TG-C05 が total=138 と報告した。新規 136 件が集計から丸ごと落ちる。--initialize-from-graph を別呼出しすれば解消するが、その順序は SKILL の外ループ手順に書かれておらず、忘れても誰も赤くならない (静かな過少報告)。"
verify: "node を 1 件以上増やした task-graph に対し外ループ再入の再 pin を 1 回行った後、追加呼出しなしで task-state.nodes 数が graph の node 数と一致することを実測する。一致しない実装のままなら、SKILL の外ループ手順へ seed 呼出しを明記し、欠落時に赤くなる検査を置く。"
depends_on: ["P05-x-128-discovered-task-leaf-contract-gap"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-129-repin-does-not-seed.md"]
consumes: []
---

# 外ループ再入時に task-state へ新 node を seed する手順を機構化する

## 由来

build 実行中に `P05-x-128-discovered-task-leaf-contract-gap` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: sync-task-state.py の --repin-graph-hash と --initialize-from-graph が main の elif 排他になっており、外ループ再入の再 pin では graph に増えた node が task-state へ seed されない。実測: drain で node が 138→274 になった直後の再 pin 後も task-state.nodes は 138 のままで、TG-C05 が total=138 と報告した。新規 136 件が集計から丸ごと落ちる。--initialize-from-graph を別呼出しすれば解消するが、その順序は SKILL の外ループ手順に書かれておらず、忘れても誰も赤くならない (静かな過少報告)。

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/task-events.jsonl`

## 作業

`plugins/harness-creator/scripts/sync-task-state.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-129-repin-does-not-seed.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

node を 1 件以上増やした task-graph に対し外ループ再入の再 pin を 1 回行った後、追加呼出しなしで task-state.nodes 数が graph の node 数と一致することを実測する。一致しない実装のままなら、SKILL の外ループ手順へ seed 呼出しを明記し、欠落時に赤くなる検査を置く。
