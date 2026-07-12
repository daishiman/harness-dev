---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: 
---

# P09 — quality-assurance (品質)

## 目的
C01-C07 全 7 component が P0 lint + build-trace + schema parity + content-review の品質機構を携帯し、確定6要因根治 (C1〜C6) のコード変更が量産品質基準を満たす状態を確定する。

## 背景
旧「品質保証」を P0 lint 8 本 + `validate-build-trace.py` + schema parity + content-review へ replace する (phase-lifecycle.md §7 P9行)。C01-C05 は script、C06 は sub-agent、C07 は skill と component_kind が異なり、それぞれ必須 p0_lint 集合が異なる (`specfm.P0_LINT_BY_KIND`)。

## 前提条件
component-inventory.json の各 component の `quality_gates.p0_lint` が component_kind 別必須集合を網羅していること。`build_trace: required`・`elegant_review.conditions: [C1,C2,C3,C4], all_pass: true`・`content_review: {verdict: PASS, sha_match: true}`・`evaluator: {threshold: 80, high_max: 0}` が全 component に確定済みであること (P02-P05 由来、既に component-inventory.json に反映済み)。

## ドメイン知識
p0_lint は component_kind 別 (index の用語集の差分): C01-C05 (script) = `lint-script-frontmatter`。C06 (sub-agent) = `validate-frontmatter`/`lint-skill-description`/`lint-agent-prompt-section`。C07 (skill) = P0 8 本 (`lint-skill-name`/`lint-skill-description`/`lint-skill-tree`/`validate-frontmatter`/`lint-dependency-direction`/`lint-skill-dep-step7`/`lint-forbidden-deps`/`lint-manifest-contents`)。

## 成果物
C01-C07 全 component の `quality_gates` ブロック (p0_lint 網羅・build_trace required・elegant_review C1-C4・content_review PASS・evaluator 閾値) が確定した状態 (`check-spec-gates.py` で機械検査可能)。

## スコープ外
lint/content-review/evaluator の実走は L4 build 時に実行される。本フェーズは quality_gates 設計の確定に留まる。

## 完了チェックリスト
- [ ] C01-C05 の p0_lint が `lint-script-frontmatter` を含む
- [ ] C06 の p0_lint が `validate-frontmatter`/`lint-skill-description`/`lint-agent-prompt-section` を含む
- [ ] C07 の p0_lint が skill P0 8 本を含む
- [ ] 全 component の `build_trace=required`・`elegant_review.conditions=[C1,C2,C3,C4] all_pass:true`・`content_review={verdict:PASS,sha_match:true}`・`evaluator={threshold:80,high_max:0}` が確定している

## 参照情報
component-inventory.json / harness-creator-spec-reflection.md / io-contract.md §10 / `check-spec-gates.py`
