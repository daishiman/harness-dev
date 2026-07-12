---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的
全 6 component (C01〜C06) に対し P0 lint + build-trace + schema parity + content-review を実行する qa gate。各 component の quality_gates ブロックが機械的に強制され、content-review verdict が現 SHA で genuine に PASS していることを保証する。

## 背景
各 component が携帯する quality_gates ブロックを実際に機械実行して qa gate とする。content-review verdict は現 SHA で genuine に生成されていなければ偽装 (SHA 書換だけの見せかけ) になりうるため、独立 SubAgent で現 SHA から再生成する。これが「保証要件は機械層で担保する」原則の適用点であり、C04 hook の fail-closed 遮断がこの原則の実装例でもある。

## 前提条件
- P08 (N/A) を経て P07 の受入判定が全 PASS。
- 各 component が quality_gates (p0_lint/build_trace/elegant_review/content_review/evaluator) を携帯している。
- content-review を独立 context (SubAgent) で実行できる。

## ドメイン知識
genuine verdict・P0 lint の kind 別集合・schema parity の定義は index/io-contract §10 を参照。本 plan 固有の差分: C05・C06 (script) はいずれも `lint-script-frontmatter` のみ、C04 (hook) は `validate-frontmatter`+`lint-script-frontmatter`、C02 (sub-agent) は `validate-frontmatter`+`lint-skill-description`+`lint-agent-prompt-section`、C03 (slash-command) は `validate-frontmatter`、C01 (skill) は 8 本の P0 lint が対象 (`specfm.P0_LINT_BY_KIND` が正本)。C06 は `network:true`/`write_scope:notion:report-db-in-toggle` を持つため、build-trace で書込み先が指定見出し (`report_toggle_block`) に紐づく単一恒久 report DB の列 PATCH + 行 upsert に限定され、新規作成時のみ指定ページ『請求書発行チェック』(`report_parent_page`) 直下へ POST /databases すること(MF へ書かない)も本 gate の確認対象に含める。

## 成果物
- 全 6 component の P0 lint / build-trace / schema parity / content-review verdict の結果一式。

## スコープ外
- プラグイン全域の最終審査 (P10 final-gate・本 gate は component 単位)。
- evidence の集約記録 (P11)。
- lint ルール自体の改変 (lint 正本は harness-creator 側・plan からは引用のみ)。

## 完了チェックリスト
- [ ] 全 6 component (C01〜C06) で P0 lint が component_kind 別に exit0。
- [ ] build-trace coverage が全 component で PASS し、schema parity (frontmatter↔schema required) が一致。
- [ ] content-review verdict=PASS・sha_match=true を独立 SubAgent の現 SHA 再生成で得ている。

## 参照情報
- component_kind 別 p0_lint 集合 (`specfm.P0_LINT_BY_KIND`)。
- content-review verdict 契約 (現 SHA genuine 再生成)。
- 対象 component C01〜C06。後続 P10 (final-review)。
