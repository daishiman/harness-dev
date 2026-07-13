---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 完了
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09]
applicability:
  applicable: true
  reason:
---

# P02 — design (設計)

## 目的
goal-spec.json の C1-C8 を満たす buildable component 群へ分解し、各 component の build_target・builder・depends_on を確定する。

## 背景
独立 builder 種別 (skill / sub-agent / slash-command / hook) は実体1つにつき component 1つが原則 (component-domain.md)。既存6 SubAgent の是正を「1 component にまとめる」か「6 component に分ける」かは goal-spec.json の open_questions で未確定だったが、同一 kind 複数実体の原則に従い6 component (C03-C08) へ分解することを本 phase で確定した。

## 前提条件
P01 で C1-C8 が本 plan のスコープとして確定していること。

## ドメイン知識
5つの component_kind (skill/sub-agent/slash-command/hook/script)。script の no-split 閾値 (≥2 skill 共有・独立テスト対象・280行超のいずれか)。placement_scope (plugin-root / skill) の区別 — plugin-root スクリプトは build_target が "/scripts/" を含み "/skills/" を含まない。

## 成果物
component-inventory.json (9 components: C01=skill/run-prompt-creator-7layer 更新、C02=script/lint-agent-prompt-content.py 新設、C03-C08=sub-agent×6 是正、C09=skill/run-build-skill 更新)。

## スコープ外
quality_gates/harness_coverage の値域検証は P04・P09。実際の build 実行 (ファイル生成) は本 plan のスコープ外 (P05 は handoff routing の確定に留まる)。

## 完了チェックリスト
- [ ] 9 component の build_target が所有 plugin 別に正しく routing されている (C7): C01 は plugins/prompt-creator/、C02-C09 は plugins/harness-creator/ 配下の実体を指す
- [ ] plugin-plans/plugin-dev-planner/・plugin-plans/skill-intake/・plugin-plans/harness-creator/ 配下がいずれの build_target / routes[].build_target / side_effect_targets にも現れない (C8)
- [ ] considered_component_kinds が5種全てを網羅している

## 参照情報
component-inventory.json、references/component-domain.md
