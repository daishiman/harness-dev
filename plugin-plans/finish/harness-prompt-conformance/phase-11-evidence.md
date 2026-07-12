---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 完了
gate_type: evidence
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09]
applicability:
  applicable: true
  reason:
---

# P11 — evidence (検証)

## 目的
11 script / 12 invocations の決定論ゲート全ての実行結果 (exit code) をエビデンスとして記録し、goal-seek loop の intermediate anchor へ反映する。

## 背景
run-plugin-dev-plan-intermediate.jsonl は各周回末に original_goal/current_goal_snapshot/delta_from_original/merged_directive_for_next/drift_signal を不変追記する規約を持つ。

## 前提条件
P06 (test-run) と P09 (quality-assurance) で各ゲートが実行済みであること。

## ドメイン知識
run-plugin-dev-plan-progress.json の更新規約 (進捗の機械可読な記録)。plan-findings.json は plan-scoped 10 invocations (G1-G10) を保持し、input-gate / dogfood は progress 側の別枠証跡として保持する。

## 成果物
run-plugin-dev-plan-intermediate.jsonl (追記)、run-plugin-dev-plan-progress.json (更新)。

## スコープ外
なし。

## 完了チェックリスト
- [ ] 11 script / 12 invocations 全ての最終 exit code が記録されている
- [ ] goal-seek anchor が最低1件 intermediate.jsonl に追記されている

## 参照情報
run-plugin-dev-plan-intermediate.jsonl、run-plugin-dev-plan-progress.json
