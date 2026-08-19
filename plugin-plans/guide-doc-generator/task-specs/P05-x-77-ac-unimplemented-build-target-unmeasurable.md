---
id: "P05-x-77-ac-unimplemented-build-target-unmeasurable"
title: "P04 全ノードの AC 後半 (build_target 未実装時に失敗する) を測定可能な文へ改める"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/task-graph.json"
acceptance_criterion: "P04 の component ノードの acceptance_criterion 後半が、実装を消さずに測定できる文へ改められていること (例: build_target 不在時に全テストが fail する仕掛けを持つこと)。または測定手段が用意されていること"
objective: "P04 の全 component ノードが build_target が未実装の時点で実行すると失敗する という AC 後半を持つが、実装が既に存在する以上どのノードでも再現不能で、実装を消して測ることは禁止されている。結果として全ノードで同じ 再現不能 が繰り返し報告される。仕掛け自体は実在し名指しできる (各 tests/ の _harness.py / hb_c16.py / _support.py の require_script() が SCRIPT.exists() を見て fail する) が、これは必要条件であって十分条件ではない (空ファイルや別物が置かれた場合の挙動は測っていない)。cyan と orange が独立に同じ結論へ到達"
verify: "P04 の component ノードの acceptance_criterion 後半が、実装を消さずに測定できる文へ改められていること (例: build_target 不在時に全テストが fail する仕掛けを持つこと)。または測定手段が用意されていること"
depends_on: ["P04-C23-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-77-ac-unimplemented-build-target-unmeasurable.md"]
consumes: []
---

# P04 全ノードの AC 後半 (build_target 未実装時に失敗する) を測定可能な文へ改める

## 由来

build 実行中に `P04-C23-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P04 の全 component ノードが build_target が未実装の時点で実行すると失敗する という AC 後半を持つが、実装が既に存在する以上どのノードでも再現不能で、実装を消して測ることは禁止されている。結果として全ノードで同じ 再現不能 が繰り返し報告される。仕掛け自体は実在し名指しできる (各 tests/ の _harness.py / hb_c16.py / _support.py の require_script() が SCRIPT.exists() を見て fail する) が、これは必要条件であって十分条件ではない (空ファイルや別物が置かれた場合の挙動は測っていない)。cyan と orange が独立に同じ結論へ到達

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugin-plans/guide-doc-generator/task-graph.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-77-ac-unimplemented-build-target-unmeasurable.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

P04 の component ノードの acceptance_criterion 後半が、実装を消さずに測定できる文へ改められていること (例: build_target 不在時に全テストが fail する仕掛けを持つこと)。または測定手段が用意されていること
