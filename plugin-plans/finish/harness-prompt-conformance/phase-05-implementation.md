---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 完了
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09]
applicability:
  applicable: true
  reason:
---

# P05 — implementation (実装)

## 目的
9 component を handoff-run-plugin-dev-plan.json の routes[] として builder 経路へ払い出し、後続 build 工程が実体を生成できる契約状態にする (routing GREEN 化)。

## 背景
builder マッピング (skill→run-skill-create、sub-agent→run-build-skill、script かつ plugin-root→plugin-scaffold) に従い routing する。C09 は skill component として run-skill-create に払い出される executor-backed 経路であり、C02 は builder_status="contract-only" (plugin-scaffold 経由・gap_ref 必須) となる。

## 前提条件
P04 で criteria/tests_min が確定していること。

## ドメイン知識
contract-only builder (parent-skill-build/plugin-scaffold) は open_issues[] の gap_ref を必須とする。placement_scope="skill" の script が親 skill の build_target 配下に nest する場合は requires_parent_scaffold が必須だが、本 plan の C02 は placement_scope="plugin-root" のため該当しない。

## 成果物
handoff-run-plugin-dev-plan.json (mode="update"、9 routes、envelope、open_issues)。

## スコープ外
初期 plan 生成時点では、実際の build 実行 (ファイル生成そのもの) は run-plugin-dev-plan の責務範囲外 (本 skill はタスク仕様書生成のみ)。
ただし 2026-07-05 の capability-build 指示により本 plan は実体化済みで、`component-inventory.json` / handoff の `build_status` / `status` は realized / built として plan↔実体 completeness gate の対象である。

## 完了チェックリスト
- [ ] routes[] の id が component-inventory.json の components[].id と過不足なく一致している
- [ ] C02 の builder_status="contract-only" かつ gap_ref が open_issues[] の実在 id を指している

## 参照情報
handoff-run-plugin-dev-plan.json、scripts/check-build-handoff.py
