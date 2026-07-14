---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P13 — release (完了)

## 目的
P12 の文書化を最後に、本 plan の完了条件 (goal「dev-graph の 13 phase ファイル + index + component-inventory + handoff が決定論ゲートで検証可能な状態になっている」) を満たしたことを確認し、plan のライフサイクルを完了させる。

## 背景
constraints「実プラグインは生成せず L3 plan までに留める」に従い、本 plan は plugin の実 build・配布・タグ付けを含まない。distribution.distributable=false であるため、marketplace 公開や pkg_contract/governance は N/A のまま完了する。完了の中心は「決定論ゲートで検証可能な plan 一式が揃っていること」であり、build 実行や配布判断は plan スコープ外の後続工程 (capability-build/task-graph build 等) に委ねる。

## 前提条件
- P12 の文書化が完了している。
- P11 の evidence・P10 の final-gate 承認が揃っている。
- goal-spec のchecklist全件 (現行C1-C42) が充足判定可能な根拠を持つ。

## ドメイン知識
- L3 plan 止まり: 本 plan は「plan 一式が決定論ゲートで検証可能」であることが完了条件であり、plugin 実体の build・配布は行わない (constraints 由来)。
- `next_phase: 14` はP13が終端であることを表すschema上のsentinelであり、実在するP14や追加release工程を意味しない。
- distributable=false の帰結: marketplace 公開・pkg_contract/governance の適用は行わず `{applicable:false, reason}` のまま完了する。
- 最終評価ownerはP10だけ。P13はP10の同一plan digest承認を消費し、完了後はC04のcapability-build/task-graph build handoffだけへ進む。

## 成果物
- 完了した plan 一式 (13 phase ファイル + `component-inventory.json` + `index.md` + `handoff-run-plugin-dev-plan.json` + `task-graph.json` + `envelope-draft/plugin.json`)。
- goal-spec checklist全件 (現行C1-C42) の充足根拠。

## スコープ外
- plugin の実 build・配布・タグ付け (constraints により plan スコープ外)。
- capability-build/task-graph build 側の実装 (本 plan は要件定義までを担い、実装は handoff 先の責務)。
- marketplace 公開判断 (distributable=false のため N/A)。

## 完了チェックリスト
- [ ] goal-spec のchecklist全件 (現行C1-C42) が充足根拠付きで説明できる。
- [ ] 13 phase ファイル + component-inventory + index + handoff + task-graph が揃い決定論ゲートで検証可能である。
- [ ] plugin 実体の build・配布は行わず L3 plan で完了している (constraints 遵守)。

### 受入例
- 満たす例: goal-spec.jsonのchecklist 42件 (C1-C42)それぞれについてindex/phase/ACの対応箇所が特定でき、`check-requirements-coverage.py`がexit0になる。
- 満たす例: `check-plugin-goal-spec.py`/`derive-task-graph.py`/`verify-index-topsort.py`/`check-build-handoff.py` を含む全決定論ゲートが exit0 で揃った状態で本フェーズを完了とする。
- 満たさない例: checklist のいずれか 1 件でも index/phase のどこにも引用されない (silent drop) → `check-requirements-coverage.py` が未被覆要件として exit1 で検出し完了とみなさない。

### 事前解決済み判断
- 完了条件は「plan 一式が決定論ゲートで検証可能」であることに固定し、plugin の実 build・配布は本 plan のスコープに含めない (constraints 由来)。
- distributable=false のため marketplace 公開・pkg_contract/governance は `{applicable:false, reason}` のまま完了扱いとし、本フェーズで配布判断を行わない。
- evaluator再実行はP10差戻し時だけとし、P13後の引き継ぎ先はcapability-build/task-graph build (C04) に固定する。

## 参照情報
- `goal-spec.json` (goal / checklist全件 (現行C1-C42) / constraints / provenance)。
- P10-P12 成果物。
- P10承認記録 / 引き継ぎ先: capability-build (task-graph build)。
