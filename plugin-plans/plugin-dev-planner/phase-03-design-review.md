---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02 で確定した component 分解 (C01/C02) と依存 DAG・plugin_level_surfaces 採否を、proposer (plugin-dev-plan-architect) とは別 context の approver (plugin-dev-plan-evaluator, fork) が elegant-review C1-C4 (design) 観点で審査する。

## 背景
5 種検討の結果が「単一 skill 偏重の既定選択」ではなく「検討済み帰結」であることを、proposer と異なる文脈のレビューアが独立に確認する必要がある。P02 の derivation フィールドはこの審査に耐える具体性を持つ前提で書かれている。

## 前提条件
- P02 の component-inventory.json が確定している。
- proposer (P02 の実行 agent) と approver (本 phase の審査 agent) が異なる context (fork) である。

## ドメイン知識
- elegant-review C1-C4: C1=矛盾なし、C2=漏れなし (checklist C1-C19)、C3=整合性あり、C4=依存関係整合。C17のtask_spec_ref join、C18のgraph/state/projection parity、C19のlineageとactive DAG分離も対象に含む。

## 成果物
- design レビュー verdict (C1-C4 各 PASS/FAIL + 指摘事項)。

## スコープ外
- 実装設計の詳細化 (P05 の責務)。

## 完了チェックリスト
- [ ] C1-C4 が全て PASS している。

### 受入例
（本 phase は縮小要件対象 (REDUCED_REQUIREMENT_PHASES) のため、見出し直下の本文は簡略形で足りる。）

### 事前解決済み判断
（本 phase は縮小要件対象のため、見出し直下の本文は簡略形で足りる。）

## 参照情報
- P02 (design)。
- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/`。
