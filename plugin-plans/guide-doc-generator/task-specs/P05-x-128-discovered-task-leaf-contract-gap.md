---
id: "P05-x-128-discovered-task-leaf-contract-gap"
title: "discovered-task の実行可能 leaf 契約 (task_spec_ref/produces) を埋める owner を定め外ループを閉じる"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/harness-creator/scripts/emit-discovered-task.py"
acceptance_criterion: "task_spec_ref/produces を埋める owner を emit 側・planner E4 側のいずれかに確定し実装したうえで、discovered-task を 2 件以上含む inbox に対して --approved ドレインを実行し accepted>0 かつ graph_hash が変化することを実測する。あわせて accept-discovered-task.py の inbox summary へ validation_failed を含め、拒否時に理由が stdout から失われないことを、意図的に不備のある form 1 件で確認する。"
objective: "外ループ (spec-improvement loop) が構造的に閉じない。本 cycle の discovered-task 135 件を --approved 付きでドレインした実測: accepted=0 / needs_approval=135 / graph_hash 不変 / node_count 138 不変。原因は validate-task-graph 規則 (k) の実行可能 leaf 契約で、task_spec_ref=task-specs/*.md と produces エッジを必須とするが、135 件中 task_spec_ref 欠落 135 件・produces 欠落 135 件・execution_kind 欠落 18 件で、3 条件を満たす form は 0 件。しかも accept は最終 graph に対する all-or-nothing 検証なので、1 件でも不備があれば全件が unapplied になり部分前進が原理的に不可能。責務の空白が 3 層で連鎖している: (1) emit-discovered-task.py は --node-task-spec-ref / --node-produces を任意扱いにする、(2) planner の E4 は SKILL.md:181 のとおり accept-discovered-task.py --inbox --approved へ転送するだけで欠落を補完しない、(3) accept は検証して拒否するだけ。accept-discovered-task.py:69-83 の docstring は『task_spec_ref/produces を欠く discovered node を受理させないため』に marker を選ぶと明記しており、拒否側の意図は正しい。欠けているのは埋める側で、誰も owner になっていない。発覚が最大限に遅れる構造でもある: emit 時は緑、蓄積中も緑、drain の瞬間に初めて 135 件が同時に赤くなる。加えて accept-discovered-task.py:372-382 の summary は 7 キーをハードコードし、:313 で設定される validation_failed (今回 343 件) を stdout から落とすため、exit 0 かつ理由ゼロで返る。運用者から見ると『承認したのに何も起きず、なぜかも分からない』。本 form 自身も同じ欠落を持つため受理不能であり、欠陥が自己を実証している。"
verify: "task_spec_ref/produces を埋める owner を emit 側・planner E4 側のいずれかに確定し実装したうえで、discovered-task を 2 件以上含む inbox に対して --approved ドレインを実行し accepted>0 かつ graph_hash が変化することを実測する。あわせて accept-discovered-task.py の inbox summary へ validation_failed を含め、拒否時に理由が stdout から失われないことを、意図的に不備のある form 1 件で確認する。"
depends_on: ["P05-C10-01"]
produces: ["plugin-plans/guide-doc-generator/task-graph.json"]
consumes: []
---

# discovered-task の実行可能 leaf 契約 (task_spec_ref/produces) を埋める owner を定め外ループを閉じる

## 由来

build 実行中に `P05-C10-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 外ループ (spec-improvement loop) が構造的に閉じない。本 cycle の discovered-task 135 件を --approved 付きでドレインした実測: accepted=0 / needs_approval=135 / graph_hash 不変 / node_count 138 不変。原因は validate-task-graph 規則 (k) の実行可能 leaf 契約で、task_spec_ref=task-specs/*.md と produces エッジを必須とするが、135 件中 task_spec_ref 欠落 135 件・produces 欠落 135 件・execution_kind 欠落 18 件で、3 条件を満たす form は 0 件。しかも accept は最終 graph に対する all-or-nothing 検証なので、1 件でも不備があれば全件が unapplied になり部分前進が原理的に不可能。責務の空白が 3 層で連鎖している: (1) emit-discovered-task.py は --node-task-spec-ref / --node-produces を任意扱いにする、(2) planner の E4 は SKILL.md:181 のとおり accept-discovered-task.py --inbox --approved へ転送するだけで欠落を補完しない、(3) accept は検証して拒否するだけ。accept-discovered-task.py:69-83 の docstring は『task_spec_ref/produces を欠く discovered node を受理させないため』に marker を選ぶと明記しており、拒否側の意図は正しい。欠けているのは埋める側で、誰も owner になっていない。発覚が最大限に遅れる構造でもある: emit 時は緑、蓄積中も緑、drain の瞬間に初めて 135 件が同時に赤くなる。加えて accept-discovered-task.py:372-382 の summary は 7 キーをハードコードし、:313 で設定される validation_failed (今回 343 件) を stdout から落とすため、exit 0 かつ理由ゼロで返る。運用者から見ると『承認したのに何も起きず、なぜかも分からない』。本 form 自身も同じ欠落を持つため受理不能であり、欠陥が自己を実証している。

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/build-summary.json`

## 作業

`plugins/harness-creator/scripts/emit-discovered-task.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/task-graph.json` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

task_spec_ref/produces を埋める owner を emit 側・planner E4 側のいずれかに確定し実装したうえで、discovered-task を 2 件以上含む inbox に対して --approved ドレインを実行し accepted>0 かつ graph_hash が変化することを実測する。あわせて accept-discovered-task.py の inbox summary へ validation_failed を含め、拒否時に理由が stdout から失われないことを、意図的に不備のある form 1 件で確認する。
