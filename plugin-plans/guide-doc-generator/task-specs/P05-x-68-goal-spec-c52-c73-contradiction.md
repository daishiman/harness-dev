---
id: "P05-x-68-goal-spec-c52-c73-contradiction"
title: "goal-spec 内の C52 と C73(3) の矛盾を裁定する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/goal-spec.json"
acceptance_criterion: "C52 の criterion 文と C73 (REQ-7) の (3) が同一事項について逆を要求していない状態。どちらを採るかの根拠が goal-spec 内に記録されていること"
objective: "C52 は超過分を既定で畳んだアコーディオンへ格納することを要求し、C73(3) は fold_section による折り畳み退避の回数上限を 0 とし超過を E-TEXT-FOLDED で落とすことを要求する。設計側 (script-brief-C12) は C73 準拠へ倒れているが goal-spec が両方を要求したままなので P07 の受入で必ず割れる。cyan が検出"
verify: "C52 の criterion 文と C73 (REQ-7) の (3) が同一事項について逆を要求していない状態。どちらを採るかの根拠が goal-spec 内に記録されていること"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-68-goal-spec-c52-c73-contradiction.md"]
consumes: []
---

# goal-spec 内の C52 と C73(3) の矛盾を裁定する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C52 は超過分を既定で畳んだアコーディオンへ格納することを要求し、C73(3) は fold_section による折り畳み退避の回数上限を 0 とし超過を E-TEXT-FOLDED で落とすことを要求する。設計側 (script-brief-C12) は C73 準拠へ倒れているが goal-spec が両方を要求したままなので P07 の受入で必ず割れる。cyan が検出

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugin-plans/guide-doc-generator/goal-spec.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-68-goal-spec-c52-c73-contradiction.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C52 の criterion 文と C73 (REQ-7) の (3) が同一事項について逆を要求していない状態。どちらを採るかの根拠が goal-spec 内に記録されていること
