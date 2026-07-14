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
P02で確定した14 component分解、workstream、repo-local isolation、lock lifecycle、versioned handoff、atomic promotion設計を独立contextのapproverが承認する。

## 背景
proposer≠approver 原則により、設計の自己採点を防ぐ。system-dev-planner は「単一 skill (`run-system-dev-plan`) へ全責務を押し込む」誘惑が働きやすい構造 (ゴールシーク型ライフサイクルの中核が 1 skill に見えるため) であり、本ゲートはその単一 skill 退化 smell を明示的に検出する。

## 前提条件
- P02 の `component-inventory.json` が確定している。
- approver が P02 の editing context と分離した独立 context で起動できる。

## ドメイン知識
- design-gate は `gate_type: design-gate` で識別される (人間可読フェーズ・機械ゲートではなく合議的判定)。
- 単一 skill 退化 smell の具体例: hook (C07) の fail-closed 判定ロジックが skill (C01) 内部の if 分岐に埋没している、sub-agent (C03-C05) の R1/R2-R3/R4 責務が 1 つの sub-agent に統合されている、等。

## 成果物
- design-review 記録 (承認/差し戻しと理由)。

## スコープ外
- 実装 (P05)。
- test-design (P04)。

## 完了チェックリスト
- [ ] 14 component全てが単一責務原則を満たす。
- [ ] `C09→{C12,C08,C10,C03}→{C05,C04,C07}→C02→C11→C01→C06`の依存DAGに循環がなく、C08/C12がC09を迂回できず、C12 validationがC11/C01より先にbuildされ、C01から独立評価C02/C05とpromotion C11へproducer順に到達する。
- [ ] `workstream_kind`/`build_target_kind` 設計が本 inventory の `component_kind` と混同されていないことを approver が確認する。
- [ ] symlink sourceをcontent authorityへ誤用する経路とpartial publication経路がない。

## 参照情報
- `component-domain.md` (粒度原則・no-split threshold)。
- P02 の `component-inventory.json`。
- 後続 P04 (test-design)。
