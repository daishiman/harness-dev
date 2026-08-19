---
id: "P02-c12-opens-prose-overview-codes"
title: "C12 brief に W-OPENS-PROSE と E-OVERVIEW-SECTION-MISSING の実体を定義する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C12.json"
acceptance_criterion: "script-brief-C12.json の detections 本体に W-OPENS-PROSE と E-OVERVIEW-SECTION-MISSING が定義され、それぞれ検査規則・違反例・exit code クラスへの割当を持つこと。AC 側の『または該当コード』という留保表現が残らないこと"
objective: "W-OPENS-PROSE の実体が script-brief-C12.json に 0 件 (dispatcher 実測)。handout-visual-policy.json:323 が『機械検査は W-OPENS-PROSE だけが持つ』と定め canon_authority を C12 とし、skill-brief-C01.json:64 と agent-brief-C05.json の AC-C05-R24-04 の両方が完了条件として当てにしているのに producer が空。加えて E-OVERVIEW-SECTION-MISSING は AC 内 1 件のみ (『または該当コード』の留保つき) で detections 本体に定義が無く、REQ-4 (利用者指定『全体像を先に』) が無検査で出荷される。P02-C12-01 は done 済みのため別ノードが要る"
verify: "script-brief-C12.json の detections 本体に W-OPENS-PROSE と E-OVERVIEW-SECTION-MISSING が定義され、それぞれ検査規則・違反例・exit code クラスへの割当を持つこと。AC 側の『または該当コード』という留保表現が残らないこと"
depends_on: ["P02-C22-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c12-opens-prose-overview-codes.md"]
consumes: []
---

# C12 brief に W-OPENS-PROSE と E-OVERVIEW-SECTION-MISSING の実体を定義する

## 由来

build 実行中に `P02-C22-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: W-OPENS-PROSE の実体が script-brief-C12.json に 0 件 (dispatcher 実測)。handout-visual-policy.json:323 が『機械検査は W-OPENS-PROSE だけが持つ』と定め canon_authority を C12 とし、skill-brief-C01.json:64 と agent-brief-C05.json の AC-C05-R24-04 の両方が完了条件として当てにしているのに producer が空。加えて E-OVERVIEW-SECTION-MISSING は AC 内 1 件のみ (『または該当コード』の留保つき) で detections 本体に定義が無く、REQ-4 (利用者指定『全体像を先に』) が無検査で出荷される。P02-C12-01 は done 済みのため別ノードが要る

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C22-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C12.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c12-opens-prose-overview-codes.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C12.json の detections 本体に W-OPENS-PROSE と E-OVERVIEW-SECTION-MISSING が定義され、それぞれ検査規則・違反例・exit code クラスへの割当を持つこと。AC 側の『または該当コード』という留保表現が残らないこと
