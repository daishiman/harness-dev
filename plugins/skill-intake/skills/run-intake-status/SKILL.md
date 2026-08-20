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
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 対象outputごとにkickoff profile 5軸 visuals notionの実在証拠を再集計し必ず一行ずつ報告している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: ファイルを生成または修復せず欠落 parse不能 状態不明を成功記号へ推測変換しないread-only結果になっている
      verify_by: evaluator
---

# run-intake-status

## Purpose & Output Contract

`output/<hint>/`をread-onlyで走査し、kickoff/profile/5軸/visual/Notion公開状態をMarkdown表で返す。

## Key Rules

- 引数があれば`output/<hint>/`だけ、なければ`output/*/`を対象にする。
- `intake.json`の5軸、`visuals/*.{svg,png}`、`notion-url.txt`、`notion-log.json.status`を観測する。
- 欠落は未完了として表示し、ファイルを生成・修復しない。
- JSON parse不能は対象名と原因を表示し、成功へ畳まない。

## ゴールシーク実行

対象を確定し、各証拠を読み、`hint | kickoff | profile | 5 axes | visuals | notion`列の表を返す。全対象を1行ずつ報告できたら完了する。

## 検証

- 集計値を実ファイル数と再照合する。
- 状態不明を`✓`へ推測変換しない。
