---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P03 — design-review (レビュー)

## 目的

P02 の設計が要件を過不足なく満たすかを design-gate で判定し、分界線違反・責務重複・依存循環・単一 skill 退化の 4 種の設計欠陥がないことを確認した状態にする。

## 背景

設計欠陥は実装後に発見すると全 component の作り直しになる。特に「レンダラに LLM を挟む」設計は再現性要件を原理的に壊すため、実装着手前に潰す必要がある。

## 前提条件

- `component-inventory.json` と `envelope-draft/plugin.json` が揃っている
- 依存 DAG が導出可能である

## ドメイン知識

- **design-gate**: 設計成果物に対する二値判定。FAIL 時は P02 へ差し戻す
- **単一 skill 退化**: 責務を 1 skill へ押し込み、hook / command / script の保証面が欠落する状態。plugin-level surface の採否根拠が空欄なら退化を疑う
- **責務重複**: 2 つ以上の component が同一の検証面を持つ状態。差し戻し先が特定できなくなる

## 成果物

- design-gate の判定記録 (PASS/FAIL と指摘)
- 指摘に対する設計修正の反映
- 設計上の未決事項の `plan-design-notes.json` への転記

## スコープ外

- テストの記述 (P04)
- 実装 (P05)

## 完了チェックリスト

- [ ] 分界線違反 (決定論レンダリング経路への LLM 介在) が 0 件である
- [ ] 責務重複が 0 件である
- [ ] 依存 DAG に循環がない
- [ ] plugin-level surface の不採用に全て理由が付いている
- [ ] design-gate が PASS である

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 構成データ→HTML の経路上に LLM 呼び出しの余地が 1 箇所も無いことを設計文面で追跡でき、不採用の plugin-level surface 全てに理由が付いている。
- 満たさない例: レンダラの一部 (図解の配置など) を LLM に委ねる余地が残っており、バイト一致再現性の根拠が崩れている。

### 事前解決済み判断

- 設計レビューは分界線 (決定論経路への LLM 介在) と責務重複と DAG 循環の 3 点を優先して見る。判定は独立 context で行い、設計者自身が承認しない。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`

