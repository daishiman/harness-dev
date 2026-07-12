---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P03 — design-review (レビュー)

## 目的
Phase02 で確定した設計(8 component 分解 + H1-H6 解消)が、後段の実 elegant-review C1-C4(component quality_gates が要求する 4 条件)を PASS する水準にあるかを、本 plan 独自の設計自己点検観点 LR1-LR4 でレビューする。

## 背景
goal-spec checklist C12 は「elegant-review C1-C4 全 PASS の設計意図(reasoning)」を機械判定(matrix coverage)とは別項目に分離して求める。L3 plan 段階では実際の subagent 評価は行わないため、本 phase は設計文書(Phase02)の自己点検チェックリストを、component-inventory の quality_gates.elegant_review.conditions(C1-C4)や goal-spec 自身の checklist(C1-C12)と混同しない独自ラベル **LR1-LR4**(Local Review、本 plan 内自己点検専用)で明示する。

## 前提条件
Phase02 完了(H1-H6 解消明記・8 component 確定)。

## ドメイン知識
LR1-LR4 の観点定義: LR1=単一 skill 退化がないか(必要最小の component 分解になっているか)、LR2=依存 DAG が非循環か、LR3=quality_gates/harness_coverage が全 component に携帯されているか、LR4=既存機構(build-pipeline task-graph)との非改変境界が明示されているか。用語集本体は index.md ## ドメイン知識 を引用する。

## 成果物
LR1-LR4 観点別の自己点検結果を本 phase 完了チェックリストとして記録する。

## スコープ外
実際の subagent 起動による elegant-review 実行(build 後段の別サイクルへ委譲。本 plan は L3 計画のみを扱う)。elegant-review C1-C4(component quality_gates 内の機械判定条件)自体の再定義(それは component-inventory.json の quality_gates.elegant_review が正本であり本 phase は上書きしない)。

## 完了チェックリスト
- [ ] LR1: 8 component が component_kind=skill(C05)/script(C01-C04/C06-C08)へ分解され、独立 combinator flag を新設せず、generated harness dependency graph knowledge を C06-C08 として必要最小に分離していることが Phase02 の H1/H5/H6 節で裏付けられている(単一 skill 退化なし)
- [ ] LR2: C01→(依存なし)、C02→C01、C06→C01/C02、C07→C02/C06、C03→C01/C02/C06/C07、C04→C03、C08→C03/C06/C07、C05→C03/C04/C06/C07/C08 の依存 DAG が非循環である
- [ ] LR3: 全 component が quality_gates(p0_lint/build_trace/elegant_review/content_review/evaluator)+ harness_coverage を携帯している
- [ ] LR4: 既存 build-pipeline task-graph(`plugin-plans/harness-creator/`)の非改変境界が index.md 受入確認に明記されている

### 受入例
- 満たす例: LR1-LR4 各観点について grep/目視の確認コマンドと結果が記録される(例: `grep -c "write_scope" component-inventory.json` の出力件数)。
- 満たさない例: 「問題なし」とだけ記載し、確認に使ったコマンドや対象箇所への参照がない。

### 事前解決済み判断
- 分岐点: design-review を人手レビューのみで済ませるか機械確認を伴わせるか → 判断: constraints の「独立 combinator flag を新設しない」「既存 build-pipeline task-graph を非改変とする」は否定命題であり目視のみでは見落としやすいため、grep 等の軽量機械確認を LR1/LR4 の完了条件に含める。

## 参照情報
- `component-inventory.json`
- `index.md` ## 受入確認
- `phase-02-design.md`
