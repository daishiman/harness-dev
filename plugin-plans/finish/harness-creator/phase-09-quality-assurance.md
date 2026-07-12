---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的
全 11 component に対し P0 lint + build-trace + schema parity + content-review を実行する qa gate。各 component の quality_gates ブロックが機械的に強制され、content-review verdict が現 SHA で genuine に PASS していることを保証する。

## 背景
各 component が携帯する quality_gates ブロックを実際に機械実行して qa gate とする。content-review verdict は現 SHA で genuine に生成されていなければ偽装 (SHA 書換だけの見せかけ) になりうるため、独立 SubAgent で現 SHA から再生成する。これが「保証要件は機械層で担保する」原則の適用点。E1/E2/E3 の provenance フィールド (source_intake/source_improvement/derived_from_artifact) は schema parity の対象として C03 が新設する `plugin-goal-spec.schema.json` 差分と `improvement-handoff.schema.json` (C09) の両方で frontmatter/schema 双方向一致を確認する。

## 前提条件
- P08 で SSOT 重複が 0 件。
- 各 component が quality_gates (p0_lint/build_trace/elegant_review/content_review/evaluator) を携帯している。
- content-review を独立 context (SubAgent) で実行できる。

## ドメイン知識
- genuine verdict: content-review verdict は現 SHA から独立 SubAgent が再生成したもののみ有効 (SHA 手書換は偽装として無効)。
- P0 lint は component_kind 別に集合が異なる (正本は `specfm.P0_LINT_BY_KIND`・全 kind 同一集合を仮定しない。script 系 5 件は `lint-script-frontmatter`、skill 系 2 件は skill 標準 8 種、command 系 2 件は `validate-frontmatter`、sub-agent/hook は agent/script 系の複合)。
- schema parity (2 軸): (1) frontmatter↔schema の required 双方向一致 (片側追加は drift)。C03 (goal-spec schema 更新) と C09 (improvement-handoff schema 新設) が対象。(2) cross-plugin producer↔consumer parity: improvement-handoff.schema.json は producer C09 (harness-creator 所有) が正本で、consumer C01/C05/C10/C11 (plugin-dev-planner 側) が期待するフィールド集合と正本 schema の required が一致することを確認する。別 plugin に跨る partial drift (schema_version は一致するが required 集合が片側追加) を検出する安全弁で、cross-plugin runtime 参照 (index「cross-plugin routing」節) の健全性を担保する。

## 成果物
- 全 11 component の P0 lint / build-trace / schema parity / content-review verdict の結果一式。

## スコープ外
- プラグイン全域の最終審査 (P10 final-gate・本 gate は component 単位)。
- evidence の集約記録 (P11)。
- lint ルール自体の改変 (lint 正本は harness-creator 側・plan からは引用のみ)。

## 完了チェックリスト
- [ ] 全 11 component で P0 lint が component_kind 別に exit0。
- [ ] build-trace coverage が全 component で PASS し、schema parity が (1) frontmatter↔schema required と (2) improvement-handoff.schema.json の cross-plugin producer(C09)↔consumer(C01/C05/C10/C11) required の双方で一致。
- [ ] content-review verdict=PASS・sha_match=true を独立 SubAgent の現 SHA 再生成で得ている。

## 参照情報
- component_kind 別 p0_lint 集合 (`specfm.P0_LINT_BY_KIND`)。
- content-review verdict 契約 (現 SHA genuine 再生成)。
- 対象 component C01-C11、後続 P10 (final-review)。
