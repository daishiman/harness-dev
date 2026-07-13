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

# P13 — release (完了・PR)

## 目的
feature→main の PR 作成条件 (xl-skills 運用: `make validate` + `tests/run-all.sh` 完了) を soft note として記録する (評価ゲート化はしない)。

## 背景
IPC/Cloudflare 由来の PR フローは DROP 済みであり、xl-skills の実運用は feature ブランチ→main への PR + CI 緑化である。本 phase はこの運用条件を記述するのみで、本 plan 自体の評価ゲートには含めない。

## 前提条件
- P12 のドキュメント設計が完了している。

## ドメイン知識
- xl-skills の PR 運用: feature ブランチで build 完了後、`make validate` + pytest 全件 green を確認し PR を作成する (`project_xlskills_pr_ci_workflow` 相当)。
- 本 plan (plugin-plans/plugin-dev-planner/) 自体は build 対象ではなくレビュー可能な deliverable であり、build 実行 (L4) は本 plan の handoff_targets (run-skill-create/run-build-skill/capability-build) に委譲される。

## 成果物
- release 条件の soft note (本 plan の完了条件には含めない)。

## スコープ外
- 実際の PR 作成・CI 実行 (build 完了後の運用作業・本 plan の対象外)。

## 完了チェックリスト
- [ ] release soft note が評価ゲートとして扱われないことが明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 「PR 作成は本 plan の完了条件に含めない soft note である」と明示され、C9 の完了条件 (elegant-review 4 条件 + 全ゲート exit0) と混同されていない。
- 満たさない例: release phase の完了チェックがそのまま C9 の完了条件として扱われ、両者が未分離のまま plan 全体の合否判定に混入する。

### 事前解決済み判断
- 分岐点: release phase を評価ゲート (gate_type=final-gate 相当) にするか soft note に留めるか → 判断: soft note (phase-lifecycle.md §8 の P13 定義通り「評価ゲートなし」であり、PR 言及は note 留めとする既定を踏襲する)。

## 参照情報
- P12 (documentation)。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/phase-lifecycle.md` §8 (P13 行)。
