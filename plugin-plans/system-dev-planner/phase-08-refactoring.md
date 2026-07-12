---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
`plugin-plans/dev-graph/templates/system-task-spec.md` (draft) と system-dev-planner 自身のテンプレート資産との SSOT 重複を解消する。

## 背景
dev-graph 側の draft は本ハーネスの出力形状の先行参照として存在するが、system-dev-planner がタスク仕様書の**生成器**である以上、テンプレートの正本は生成器側 (system-dev-planner の `references/`) に置き、dev-graph 側は引用のみに留める (生成器と消費者の非対称を逆転させない)。

## 前提条件
- P07 で受入観点が確定している。

## ドメイン知識
- SSOT dedup の判断原則: 生成器 (system-dev-planner) がテンプレート正本を持ち、消費者 (dev-graph) は引用のみ。
- draft の形状 (目的/背景/前提条件/システム設計知識/成果物/スコープ外/完了チェックリスト+受入例+事前解決済み判断/参照情報) を正本へ昇格する際、フィールド名・節構成を変更しない (dev-graph 側の既存参照を壊さない非後退)。

## 成果物
- `references/system-task-spec-template.md` (正本化されたテンプレート。P12 で最終確定)。
- `references/system-phase-spec-template.md` (13 phase 文書テンプレートの正本。dev-graph `templates/system-phase-spec.md` (draft) と整合する骨子。P12 で最終確定)。
- dev-graph draft との収束記録 (draft は本正本への pointer に置き換え可能である旨)。

## スコープ外
- component 実装の差し戻し (実装自体は P05 で完了済み)。

## 完了チェックリスト
- [ ] テンプレート正本の所在が system-dev-planner 側の 1 箇所に確定している。
- [ ] dev-graph draft との重複が記録され、どちらが正本かが明示されている。

## 参照情報
- `plugin-plans/dev-graph/templates/system-task-spec.md` / `system-phase-spec.md` (draft)。
- `references/system-task-spec-template.md` / `references/system-phase-spec-template.md` (正本予定地)。
- 後続 P09 (quality-assurance)。
