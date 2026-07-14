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
本L3 planの完了を宣言し、後続buildへのhandoff一式が揃うことを確認する。これはGitHub Issue #17の実修正・close完了宣言ではない。

## 背景
goal-spec の constraints で「実プラグイン/実コード生成は禁止・L3 plan までに留める」「PR 作成やリリース対応は本 plugin の責務外」と明示されている通り、本 phase は実際のリリース作業 (PR 作成・marketplace 登録・実 plugins/ への配置) を行わない。あくまで plan 成果物一式が build 開始可能な状態にあることの最終宣言に留まる (sample-plan と同様の「soft note」扱い)。

## 前提条件
- P12 の文書化が完了している。
- `handoff-run-plugin-dev-plan.json` / `task-graph.json` が生成済みである。

## ドメイン知識
- リリース (PR 作成・marketplace 登録・実 `plugins/` への配置) は本 plan の責務外であり、下流の build フェーズまたは人手が担う (DROP 読替: 本 plan では扱わない)。
- GitHub Issue #17は実plugin build、対象rubric/schema/templateの検証済み反映、人間によるC10証跡確認後にのみcloseする。本phaseはIssueをcloseしない。
- envelope generator (manifest/marketplace の自動生成 builder) が現状存在しないという gap は handoff の open_issues に記録済みであり、本 phase での解消は行わない。

## 成果物
- plan完了宣言 (13 phase + inventory + index + handoff + task-graph + 30思考法証跡が揃うことの確認)。
- 未解決 gap の一覧 (envelope generator gap 等、open_issues への参照)。

## スコープ外
- PR 作成・実プラグインのリリース対応 (本 plan の責務外)。
- marketplace への実登録 (build フェーズ以降の責務)。

## 完了チェックリスト
- [ ] 13 phase ファイル + `component-inventory.json` + `index.md` + `handoff-run-plugin-dev-plan.json` + `task-graph.json` が全て `plugin-plans/spec-drift-guardian/` に存在する。
- [ ] `handoff-run-plugin-dev-plan.json` の open_issues に未解決 gap (envelope generator 不在等) が漏れなく記録されている。
- [ ] 本 plan が build フェーズ (`plugin-dev-plan-evaluator` 等) へそのまま引き渡し可能であることが確認されている。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build フェーズへの引き渡し内容)。
- `task-graph.json` (derive-task-graph.py による単一書き手投影)。
- 本 plan の外側 (build フェーズ・evaluator) が後続の責務を持つ。
