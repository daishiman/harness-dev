---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 完了
gate_type: final-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P10 — final-review (最終レビューゲート)

## 目的

実装後の current artifact を独立 context で30思考法・4条件により最終審査する。

## 背景

design review 後にも実装 drift、source更新、route/build report不一致が起こり得るため final review を別 gate とする。

## 前提条件

- P09 quality PASS。
- goal/inventory/handoff/task-graph/build reports の digest が current。

## ドメイン知識

- 30思考法は finding または skip_reason を全件記録する。
- critical/high 0、4条件全PASS、unassigned 0 が final GO 条件。
- 最大3周で未達なら escalation。

## 成果物

- current digest 付き final verdict。
- finding→patch→retest trace。

## スコープ外

- stale evidence の再利用。
- runtime user gate の無断実行。

## 完了チェックリスト

- [ ] 30/30 method coverage。
- [ ] 4条件全PASS。
- [ ] critical/high 0。
- [ ] unassigned/orphan/unsupported silent skip 0。
- [ ] current digest parity PASS。
- [ ] generated hook command の relocation/existence、source-aware dedupe、exact marketplace identity、全CI desired-set owner を実体で検証する。
- [ ] P13 の user-gated node と local-required node が個判定され、ledger 一件で全 P13 を defer しない。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: review 対象 hash と実体 hash が一致し、全 method trace がある。
- 満たさない例: 過去の PASS JSON をコピーする。

### 事前解決済み判断

- design approver と final approver の verdict を流用しない。

## 参照情報

- `plan-findings.json`
- build route reports (planned)
