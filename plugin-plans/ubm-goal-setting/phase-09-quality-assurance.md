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
全11 componentのP0/build-trace/schema/content-reviewとend-to-end automation/fullness/graph/artifact provenanceを検証するqa gate。

## 背景
各 component が携帯する quality_gates ブロックを実際に機械実行して qa gate とする。content-review verdict は現 SHA で genuine に生成されていなければ偽装 (SHA 書換だけの見せかけ) になりうるため、独立 SubAgent で現 SHA から再生成する。これが「保証要件は機械層で担保する」原則の適用点。

## 前提条件
- P08 で SSOT 重複が 0 件。
- 各 component が quality_gates (p0_lint/build_trace/elegant_review/content_review/evaluator) を携帯している。
- content-review を独立 context (SubAgent) で実行できる。

## ドメイン知識
- genuine verdict: content-review verdict は現 SHA から独立 SubAgent が再生成したもののみ有効 (SHA 手書換は偽装として無効)。
- P0 lint は component_kind 別に集合が異なる (正本は `specfm.P0_LINT_BY_KIND`・全 kind 同一集合を仮定しない)。
- schema parityに加え、plugin.json/plugin-composition/package-contract/EVALSのentry point parityを検査する。
- REQ2 検証専用ステップ: `find plugins/ubm-goal-setting/skills -maxdepth 1 -type l` で run-skill-feedback が symlink のまま維持されていることを確認し、`scripts/lint-feedback-protocol.py --strict` で R1-R7 (R6=発火経路の周知/R7=実体配備の存在含む) が PASS することを確認する。これは buildable component の quality_gates とは別枠の検証専用チェックであり EVALS.json への新規エントリ追加は不要 (既存配備分のため)。

## 成果物
- 全 component の P0 lint / build-trace / schema parity / content-review verdict の結果一式。
- EVALS.jsonへの新設11 component分と無人sync/content coverage/non-zero edge/real artifact/redaction/相談スタンス・role provenance・command entrypointのend-to-end gate追加。
- REQ2 検証専用ステップ (run-skill-feedback symlink 維持確認 + lint-feedback-protocol.py --strict PASS) の実行結果。

## スコープ外
- プラグイン全域の最終審査 (P10 final-gate・本 gate は component 単位)。
- evidence の集約記録 (P11)。
- lint ルール自体の改変 (lint 正本は harness-creator 側・plan からは引用のみ)。

## 完了チェックリスト
- [ ] 全 component で P0 lint が component_kind 別に exit0。
- [ ] build-trace coverage が全 component で PASS し、schema parity (frontmatter↔schema required) が一致。
- [ ] content-review verdict=PASS・sha_match=true を独立 SubAgent の現 SHA 再生成で得ている。
- [ ] EVALS、manifest、composition、package-contractが11 componentと完全parityである。
- [ ] 全script routeのexecutor dry-runとdomain acceptanceがPASSする。
- [ ] (検証専用・非 buildable) REQ2: `plugins/ubm-goal-setting/skills/run-skill-feedback` が harness-creator SSOT への symlink のまま維持され、`scripts/lint-feedback-protocol.py --strict` が R1-R7 PASS する。

### 受入例
manifest/composition/package/EVALS parity、11 component gates、feedback symlink維持が全PASSする。

### 事前解決済み判断
content-review SHA手書換は無効。独立contextのgenuine verdictだけを受理する。

## 参照情報
- component_kind 別 p0_lint 集合 (`specfm.P0_LINT_BY_KIND`)。
- content-review verdict 契約 (現 SHA genuine 再生成)。
- `scripts/lint-feedback-protocol.py` (REQ2 検証専用ステップ)。
- 対象 component C01-C11、後続 P10。
