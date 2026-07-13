---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 完了
gate_type: tdd-red
entities_covered: [C01, C02, C09]
applicability:
  applicable: true
  reason:
---

# P04 — test-design (テスト)

## 目的
feedback_contract.criteria (C01/C09 の inner/outer loop) と C02 の tests_min しきい値など、各 component の検証観点を実装に先立って確定する (RED 先行)。

## 背景
FEEDBACK_LOOP_SKILL_KINDS (run/wrap/delegate) の skill のみ criteria が構造的に必須。C01 (run-prompt-creator-7layer) と C09 (run-build-skill) はいずれも skill_kind="run" のため必須。C02 は script kind であり tests_min>=80 のみが必須。

## 前提条件
P02/P03 で component 分解と design-review が完了していること。

## ドメイン知識
criteria の各 item は id (IN/OUT/C 接頭辞・一意)・loop_scope (inner/outer)・text・verify_by (lint/test/script/evaluator/elegant-review/live-trial/human のいずれか) を持つ。text は同一 component 自身の goal/checklist と語彙的traceabilityを持つ必要がある (goal-spec 全体ではなく component 内部の traceability)。

## 成果物
C01 の criteria (IN1=内側lint検証/OUT1=外側test検証)、C09 の criteria (IN1/OUT1、prompt-creator 経由 provenance とバイパス不能性)、C02 の tests_min=80 の確定宣言。

## スコープ外
実装 (GREEN 化) 自体は P05 の責務。

## 完了チェックリスト
- [ ] C01・C09 それぞれに inner ≥1件・outer ≥1件の criteria が存在する
- [ ] 各 criteria.text が同一 component の goal/checklist と語彙を共有している (traceability)
- [ ] C02 の tests_min が80以上で宣言されている
- [ ] C09 の OUT1 が provenance 欠落または prompt_creator_invocation=false の生成物を exit1 とするバイパス不能性テストを要求している

## 参照情報
component-inventory.json、references/io-contract.md (条件付き規制表)
