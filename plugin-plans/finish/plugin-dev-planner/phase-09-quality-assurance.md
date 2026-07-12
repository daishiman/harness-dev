---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的
C01/C02 の quality_gates (p0_lint / build_trace / elegant_review C1-C4 / content_review / evaluator≥80,high0) と harness_coverage (min≥80/kind_pass) を build 後に実行し、plugin-dev-planner の 6 surface × mechanical/llm_eval 12 軸カバレッジが goal-spec C3 の意味で自己適用されていること、および C6/C7/C10/C11 (機械層)・C8/C12 (意味層) の追加による quality_gates 契約の非破壊を確認する。

## 背景
本 plan の環境ポリシーは全 buildable component が quality_gates + harness_coverage を携帯することを要求する。C01/C02 の 2 件が plugin-dev-planner 全体の harness-coverage 自己適用状態を代表する (dogfooding F1 の解消証跡)。C02 は skill_kind=assign のため harness_coverage.kind_pass が "assign=evaluator-verdict" と C01 とは異なる合否様式を持つ点に注意する。P09 は判定行為中心の gate 系 phase であり縮小要件 (受入例/事前解決済み判断は簡略形) を適用する。

## 前提条件
- P08 のリファクタリングが完了している (または不要と判定されている)。

## ドメイン知識
- **p0_lint (kind別=skill)**: lint-skill-name / lint-skill-description / lint-skill-tree / validate-frontmatter / lint-dependency-direction / lint-skill-dep-step7 / lint-forbidden-deps / lint-manifest-contents の 8 本全 exit0 (C01/C02 双方)。
- **elegant_review**: C1 (Layer 整合) / C2 (依存方向) / C3 (再現性) / C4 (Self-Eval) の 4 条件 all_pass (C01/C02 双方)。
- **content_review**: verdict=PASS かつ skill_md_sha256 一致 (stale 検出無し、C01/C02 双方)。
- **evaluator**: threshold>=80 かつ high findings 0 件 (C01/C02 双方)。
- **harness_coverage**: `check-harness-coverage-selfcheck.py` (C3 で新設) が 6 種別×mechanical/llm_eval=12 軸の構造的宣言状態を exit0 で検証し、EVALS.json.threshold_note (現状値非焼込みの哲学) と矛盾しないことを確認する。C02 の harness_coverage.kind_pass="assign=evaluator-verdict" は R1-evaluate.md の C8/C12 判定ステップ追加後もこの合否様式で判定可能であることを確認する。

## 成果物
- p0_lint 8 本の実行結果 (C01/C02 それぞれ)。
- elegant_review 4 条件の判定結果 (C01/C02 それぞれ)。
- content_review verdict (C01/C02 それぞれ)。
- evaluator スコアと high findings 件数 (C01/C02 それぞれ)。
- harness_coverage self-check の実行結果。

## スコープ外
- 品質基準そのものの変更 (component-inventory.json の quality_gates/harness_coverage が正本・本 phase は実行のみ)。

## 完了チェックリスト
- [ ] p0_lint 8 本が C01/C02 双方で全 exit0。
- [ ] elegant_review C1-C4 が C01/C02 双方で all_pass。
- [ ] content_review が C01/C02 双方で verdict=PASS かつ sha_match。
- [ ] evaluator が C01/C02 双方で threshold>=80 かつ high_max=0。
- [ ] harness_coverage self-check が exit0 で 12 軸の構造的宣言状態を確認 (C02 の assign=evaluator-verdict 様式含む)。

### 受入例 (満たす例 / 満たさない例・判定行為ゲート簡略形)
- 満たす例: C01/C02 双方の quality_gates 全項目と harness_coverage の判定結果が記録され、C02 特有の evaluator-verdict 様式が別途明示される。
- 満たさない例: C01 のみ判定し C02 (assign kind) を quality_gates 対象外と誤認して省略する。

### 事前解決済み判断
- 分岐点: C02 (skill_kind=assign) の quality_gates を C01 と同一基準で適用するか → 判断: p0_lint/elegant_review/content_review/evaluator は skill 種別共通のため同一基準を適用し、harness_coverage.kind_pass のみ assign 固有の evaluator-verdict 様式に置き換える (io-contract.md §11 の kind 別合否様式に準拠)。

## 参照情報
- `component-inventory.json` (C01/C02.quality_gates / harness_coverage)。
- `plugins/plugin-dev-planner/EVALS.json` (threshold_note)。
- 後続 P10 (final-review)。
