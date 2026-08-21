---
name: run-intake-status
description: 進行中のskill intakeのphaseと5軸を確認したいとき、visualとNotion公開状態をread-onlyで確認したいときに使う。
allowed-tools: Read, Glob
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[hint?]"
effect: conversation-output
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-intake
source-tier: internal
responsibility_refs:
  - prompts/R1-status.md
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 対象outputごとにkickoff profile 5軸 visuals notionの実在証拠を再集計し必ず一行ずつ報告している
      verify_by: evaluator
    - id: OUT1
      loop_scope: outer
      text: ファイルを生成または修復せず欠落 parse不能 状態不明を成功記号へ推測変換しないread-only結果になっている
      verify_by: evaluator
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実回答をmain contextで作成する。secret・欠測・矛盾のminimal guardだけを実行し、根拠refつきの現物をそのまま提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはそのままhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。

# run-intake-status

## Purpose & Output Contract

`output/<hint>/`をread-onlyで走査し、kickoff/profile/5軸/visual/Notion公開状態をMarkdown表で返す。

## Key Rules

- 引数があれば`output/<hint>/`だけ、なければ`output/*/`を対象にする。
- 出力表の6列は次の実在証拠と1:1で対応させる (証拠の無い列を作らない) — `kickoff`=`output/<hint>/kickoff.json` (`run-intake-kickoff`が生成)、`profile`=`output/<hint>/profile.json` (Phase 3 の SubAgent `skill-intake-user-profiler` が出力。`run-intake-interview` は Phase 4 で読むだけ)、`5 axes`=`intake.json`の5軸、`visuals`=`visuals/*.{svg,png}`、`notion`=`notion-url.txt`と`notion-log.json.status`。
- 欠落は未完了として表示し、ファイルを生成・修復しない。
- JSON parse不能は対象名と原因を表示し、成功へ畳まない。
- 実行手順の正本は`prompts/R1-status.md` — 機密フィールドの読取り境界 (Layer 4)、hintの安定sortと下流skillを自動実行しない境界 (Layer 6)、`✓`表示規約 (Layer 7) はそこを参照する。

## ゴールシーク実行

対象を確定し、`prompts/R1-status.md`に従って各証拠を読み、`hint | kickoff | profile | 5 axes | visuals | notion`列の表を返す。全対象を1行ずつ報告できたら完了する。

## 検証

- 集計値を実ファイル数と再照合する。
- 状態不明を`✓`へ推測変換しない。
