---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
GitHub issue #17 系の spec-drift 対応で人手依存になっている step2 (影響判定) と step3 (rubric/schema/template 更新) を構造化・半自動化する構想を目的ドリブンで要件化し、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`spec-drift-guardian` を固定し、既存責務 (検知) との非重複境界を制約として開示する。

## 背景
`.github/workflows/update-yaml-spec.yml` は `yaml-spec-cache.md` を更新する一方、`spec-diff-history.md` には unified diff の先頭80行しか残さない。Issue #17 に対応する実差分は base `da6d4e744e30c4ca5ac8aac9ab05127aa3471b41` / head `6ddd6453213155ca70dbed950176699fcd9e2752` の945行で、settings の `browserExternalPageTools` / `workflowSizeGuideline`、`/doctor`、plugin MCP matcher、hook transcript、sub-agent 挙動を含む。したがって履歴previewを正本扱いせず、イベント日時からcache更新commit pairを照合して全未triage完全diffを再構成し、name/type/required/enumの4軸とsemantics軸で影響判定する必要がある。step3は提案だけでなく、独立監査・ユーザー明示承認・許可パスへの実適用・post-image検証まで完了しない限りclose不可とする。

## 前提条件
- goal-spec 抽出は R1 (elicitor) により既に完了しており `goal-spec.json` (purpose/background/goal/checklist C1-C6/constraints/handoff_targets) が確定済みである。
- 検知 (fetch/diff/issue 起票) は既存 `.github/workflows/update-yaml-spec.yml` + `plugins/harness-creator/skills/ref-yaml-spec-fetcher` に委ね、本 plan では再実装しない前提を共有している。
- このフェーズは特定 component へ紐づかない (責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- spec-drift = SOURCES の変更が fetch→diff→issue 起票された後、完全diff再構成→4軸+semantics triage→独立verdict→提案→監査→明示承認→限定適用→post-image検証→close という後続対応を要する状態。
- 検知/対応の責務境界: 検知は既存 workflow、triage 以降 (影響判定・更新提案・close ゲート) が本 plugin `spec-drift-guardian` の責務。
- goal-spec は全 goal-seek 周回で不変のアンカー (target_plugin_slug=`spec-drift-guardian`/plan_dir を含め以降のフェーズが書き換えない)。
- checklist C1-C6 は本 plan 全体の受入観点であり、各 phase/component の完了判定はこの語彙から導出する (index `## ドメイン知識` も参照)。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist C1-C6/constraints/handoff_targets/max_loops/open_questions、確定済み)。
- target_plugin_slug=`spec-drift-guardian` と plan_dir=`plugin-plans/spec-drift-guardian` の確定値。

## スコープ外
- component 分解・依存 DAG 設計 (P02 へ委譲)。
- 検知機構 (fetch/diff/issue 起票) の再実装 (既存 workflow/`ref-yaml-spec-fetcher` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、checklist C1-C6 が purpose/background 語彙から導出されている。
- [ ] target_plugin_slug が ASCII kebab (`spec-drift-guardian`) で確定し以降のフェーズがそれを参照できる。
- [ ] 検知責務 (既存 workflow/`ref-yaml-spec-fetcher`) と本 plan の責務境界 (triage 以降) が constraints に明示されている。
- [ ] Issue #17の完全commit pairと、履歴previewが完全diffの正本ではないことがgoal-specに明示されている。

## 参照情報
- `goal-spec.json` (本 plan の唯一の入力・確定済み)。
- `.github/workflows/update-yaml-spec.yml` / `plugins/harness-creator/skills/ref-yaml-spec-fetcher` (検知責務の既存実体、read-only 参照)。
- 後続 P02 (この goal-spec を component 分解の入力とする)。
