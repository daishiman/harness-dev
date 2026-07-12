---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason:
---

# P01 — requirements (要件)

## 目的
goal-spec.json (確定済み・変更禁止) が定義する目標を本 plan のスコープ内で要件として固定し、C1-C8 の8チェック項目を後続フェーズが参照可能な状態にする。

## 背景
harness-creator の6 SubAgent (elegant-improvement-executor / elegant-logical-structural-analyst / elegant-meta-divergent-analyst / elegant-reset-observer / elegant-system-strategic-analyst / run-build-skill-subagent) は、prompt-creator の l5-contract v2.0.0 に本文準拠していない。skill 配下 prompts/*.md は7層見出しを持つものの、既存の lint-prompt-placement.py は『配置』規律のみを担い、本文内容の7層準拠を機械検証する機構が無い。ユーザーは SubAgent の frontmatter をプラグイン YAML 形式のまま維持し本文のみ7層構造に従うハイブリッド形式を確定済み。

## 前提条件
goal-spec.json が check-plugin-goal-spec.py を通過済みで凍結されていること。plugin-plans/harness-creator/ (別件 E1/E2/E3 パイプライン境界契約 plan)・plugin-plans/plugin-dev-planner/・plugin-plans/skill-intake/ には一切触れないこと (C8) が契約として確定していること。

## ドメイン知識
本 plan は2つの ID 名前空間を持つ: goal-spec.json の checklist id (C1-C8) と component-inventory.json の component id (C01-C09)。両者は無関係であり混同しない。用語集の詳細は index.md ## ドメイン知識 を正本とし、本 phase 固有の追加事項は無い。

## 成果物
本 phase ファイル自体が要件確定の記録である (entities_covered=[]、この時点では component は未分解)。

## スコープ外
component への分解自体は P02 の責務。契約文書 (SubAgent ハイブリッド契約) の具体的な配置先確定も P02 で行う。

## 完了チェックリスト
- [ ] goal-spec.json の8チェック項目 (C1-C8) が本 plan のスコープとして受理されている
- [ ] C8 が除外対象とする3つの plan_dir (plugin-plans/plugin-dev-planner/・plugin-plans/skill-intake/・plugin-plans/harness-creator/) が明示されている

## 参照情報
plugin-plans/harness-prompt-conformance/goal-spec.json、plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/io-contract.md、references/component-domain.md、references/phase-lifecycle.md
