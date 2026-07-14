---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的
全 14 component の `quality_gates` (p0_lint / build_trace / elegant_review C1-C4 / content_review / evaluator) の値域規律を確認する。

## 背景
「現状値非焼込」原則により、`quality_gates` は要件化された契約であり、現時点の実測未達数値を component エントリへ焼かない (Goodhart 回避)。本フェーズはその契約の値域 (enum/閾値) が全 component (C09-C14 の repo-local deterministic script を含む) で構造的に満たされていることを確認する。

## 前提条件
- P08 の SSOT dedup が完了している。

## ドメイン知識
- quality_gates 必須 5 項目の値域: `p0_lint` (kind別・網羅)、`build_trace: required`、`elegant_review.all_pass: true` (C1-C4)、`content_review.verdict: PASS` + `sha_match: true`、`evaluator.threshold >= 80` かつ `high_max: 0`。

## 成果物
- 全 14 component の quality_gates 充足記録。

## スコープ外
- 最終レビュー (P10)。

## 完了チェックリスト
- [ ] 全 14 component が p0_lint (kind 別) を網羅している。
- [ ] `build_trace: required` / `elegant_review.all_pass: true` / `content_review.verdict: PASS, sha_match: true` / `evaluator.threshold >= 80, high_max: 0` を全 component が携帯する。
- [ ] filesystem permissionはplugin source code/assetsとcaller repo local rootsに限定され、network/secrets不要、absolute path保存禁止である。

## 参照情報
- `io-contract.md` (core 規律・quality_gates 値域表)。
- 対象 component C01-C14。
- 後続 P10 (final-review)。
