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
plugin-dev-planner同型の流れをsystem developmentへ写像し、system-spec-harness引用、dev-graph登録、symlink配布先のrepo-local isolation、atomic promotionを含む`goal-spec.json`を確定する。

## 背景
dev-graph (plugin-plans/dev-graph/) は、システム開発タスク仕様書を生成する専用ハーネスが plugin-dev-planner と同型の 13 フェーズ lifecycle + workstream inventory + typed task DAG + handoff + 独立評価を持つことを既に要件化している。単語置換ではなく目的ドリブンで要件化しないと後続の workstream 分解が破綻するため、全 13 フェーズが参照する不変の goal-spec を最初に固定する必要がある。同一構想は常に同一 `PLAN_DIR` (`plugin-plans/system-dev-planner/`) へ解決され (再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- システム開発ハーネス構想 1 件 (dev-graph の goal-spec checklist C21-C23 由来) が入力として与えられている。
- 汎用の `run-goal-elicit` (harness-creator) が利用可能で、purpose/background/goal/checklist を `goal-spec.schema.json` で抽出できる (再実装しない)。
- `plugin-plans/dev-graph/templates/system-task-spec.md` / `system-plan-contract.json` (draft) が出力形状の先行参照として既に存在する。
- system-spec-harness の manifest version は `0.1.0`、引用 entrypoint は `run-system-spec-compile` と `assign-system-spec-completeness-evaluator`、手動commandは `/spec-compile` である。
- caller repository root は symlink物理元と独立し、repo-local `.dev-graph/config.json` をcontent authorityとする。
- このフェーズは特定 component へ紐づかない (責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- implementation-readiness = 実装着手に必要な内容 (前提条件/設計知識/成果物/依存/完了チェックリスト) の充足度。system-dev-planner の purpose 中核語。
- system-spec-harness が仕様書・アーキテクチャ内容の正本データで、system-dev-planner が生成する task-spec はその引用写像 (内容ロジックを複製しない)。
- goal-spec は全 goal-seek 周回で不変のアンカー (target_plugin_slug/plan_dir を含め以降のフェーズが書き換えない)。
- その他の plan 全体用語 (workstream_kind/build_target_kind 等) は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist C1-C13/constraints/handoff_targets/open_questions)。
- `system-spec-source-pin.json` と `intake.json` / `improvement-handoff.json`。
- target_plugin_slug と plan_dir の確定値。

## スコープ外
- workstream 分解・component 分解 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点が purpose 語彙から導出されている。
- [ ] target_plugin_slug が ASCII kebab (`system-dev-planner`) で確定し以降のフェーズがそれを参照できる。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。
- [ ] source pin、repo-root precedence、path containment、idempotent init、atomic promotionがC9/C10へ二値要件化されている。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 呼び出し元 `plugin-plans/dev-graph/goal-spec.json` (checklist C21-C23)。
- 後続 P02 (この goal-spec を workstream/component 分解の入力とする)。
