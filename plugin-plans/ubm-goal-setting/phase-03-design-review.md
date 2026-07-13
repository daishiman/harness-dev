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
P02 の設計 (inventory と envelope draft) を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。特に YouTube 3経路の単一 skill 統合が単一 skill 退化 (機能の水増し隠蔽) になっていないかを重点検査する。

## 背景
設計段階の欠陥を実装後に発見すると手戻りが大きい。本計画は既存 plugin への改善であるため、新設 component が既存 capability A/B の契約を壊していないか (非後退) も design-gate の審査対象に加える。審査は独立 context で行い、指摘は P02 へ差し戻す。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- elegant-review 4 条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みを参照できる。
- レビュアは提案者と別 context で評価する (構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4 を設計スコープ (inventory+envelope draft) に適用したもの。
- proposer≠approver: 設計した主体と承認する主体を context ごと分離する不変条件 (自己承認は無効)。
- 単一 skill 退化 = 複数責務が 1 skill に畳まれ分解価値が失われた状態 (本 plan では REQ1a/1b/1c の 3 経路を 1 skill のモード分岐に統合した判断が対象)。全量判定 (REQ1b) を独立 script (C03) へ分離したことが水増し回避の根拠として審査される。

## 成果物
- design-gate の判定記録 (C1-C4 全 PASS / 差し戻し理由)。

## スコープ外
- 指摘の修正そのもの (P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計 (P04)・実装 (P05)。
- 機械 lint の実行 (P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] REQ1a/1b/1c の単一 skill 統合が水増し回避 (機能ごとの独立検証は C03 で分離) として妥当と判定されている。
- [ ] 既存 capability A/B の契約への影響が無い (additive のみ) ことが確認済み。

### 受入例
独立approverが自動sync、厳格全量、edge producer、artifact producerを含む設計をC1-C4全PASSにする。

### 事前解決済み判断
shape PASSだけで承認せず、runnable/end-to-end契約も見る。

## 参照情報
- P02 成果物 (`component-inventory.json` / `envelope-draft/plugin.json`)。
- `assign-plugin-plan-evaluator` (評価ロジックの正本・proposer≠approver)。
- 後続 P04 (test-design)。
