---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 完了
gate_type: qa
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的

品質 gate、後方互換、security、freshness、native surface drift を機械検証する。

## 背景

coverage 数値だけでは trust bypass や stale review を防げないため、kind lint と意味 gate を併用する。

## 前提条件

- P08 refactor 完了。
- artifact digest generator が利用可能。

## ドメイン知識

- quality gate: p0_lint/build_trace/elegant-review/content-review/evaluator≥80/high0。
- compatibility: existing Claude INV、CLI args、task-graph single writer。
- security: global/beads/trust store/secret/PII write 0。

## 成果物

- component quality report。
- native surface parity/freshness/security/compatibility gate logs。

## スコープ外

- runtime trust approval。
- quality threshold を通すための test exclusion。

## 完了チェックリスト

- [ ] 全5 component の kind gate と coverage が PASS。
- [ ] existing Claude tests が green。
- [ ] C02 parity/freshness gate が PASS。
- [ ] forbidden write/secret scan が PASS。
- [ ] official source snapshot checked_at が stale policy 内。
- [ ] 別clone relocation、個人絶対path 0、duplicate runtime hook 0、exact marketplace identity、全active CIのC01単一ownerが PASS。
- [ ] runtime ledger の graph/artifact hash・時刻・user-gate node allowlist が schema validation PASS。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: quality report が digest と raw command を持つ。
- 満たさない例: plan-findings の古い component 数を引用する。

### 事前解決済み判断

- freshness FAIL は他 quality PASS より優先する。

## 参照情報

- `component-inventory.json` quality_gates
- `references/native-surface-contract.md` (planned)
