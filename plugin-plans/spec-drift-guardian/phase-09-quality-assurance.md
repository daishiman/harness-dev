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

# P09 — quality-assurance (品質保証 / qa)

## 目的
全11 componentがinventoryのquality_gatesとharness_coverageを満たし、4 artifact schema/surface owner/DAG/Issue #17 fixture契約が閉じていることを確認する。

## 背景
P06/P07/P08に対し本phaseは全component横断QAを行う。特にscript4件(C11/C08/C09/C10)と独立verdict2件の配線を単一障害点として審査する。

## 前提条件
- P08 の改善が完了している (要改善項目が無い、または改善済み)。
- `check-spec-gates.py` / `check-spec-frontmatter.py` による機械検証を実行できる環境がある。

## ドメイン知識
- p0_lint は component_kind ごとに異なる (skill=8種、sub-agent=3種、slash-command=1種、hook=2種、script=1種)。
- evaluator.threshold=80 かつ high_max=0 は全 component 共通の契約値であり、個別に緩めない。
- harness-creatorへの書き込みは承認済みC02 applyだけで、対象外差分0件・hash/validator証跡があることを品質保証に含む。

## 成果物
- 全11 componentのquality_gates/harness_coverage充足確認結果。
- `check-spec-gates.py` / `check-spec-frontmatter.py` の実行結果 (exit code)。

## スコープ外
- 最終レビューでの承認判定そのもの (P10 の責務)。
- エビデンス集約 (P11 の責務)。

## 完了チェックリスト
- [ ] 全11 componentのp0_lintがcomponent_kind別必須リントを満たしている。
- [ ] 全11 componentのevaluator.threshold=80/high_max=0、harness_coverage.min=80がinventory上にliteralに焼き込まれている。
- [ ] `check-spec-gates.py` および `check-spec-frontmatter.py` が exit0。

## 参照情報
- `component-inventory.json` (quality_gates/harness_coverage の全定義)。
- `references/harness-creator-spec-reflection.md` (品質ゲートの正本)。
- 後続 P10 (この品質保証結果を final-review で最終承認する)。
