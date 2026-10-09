---
name: run-governance-automation
description: governanceの登録・rubric合成を実行したいとき、再評価・rollback automationを安全に選択したいときに使う。
kind: run
prefix: run
goal_seek:
  engine: inline
  fork: inline
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
effect: local-artifact
runtime_root_policy: host-skill-path
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-automation
source-tier: internal
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 選択したautomation entrypointのhelpとread-only preflightを実行し非0またはreceipt欠落を成功へ畳んでいない
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: apply rollback 通知の外部作用はユーザー承認後だけ実行されcommand exit changed pathsと残リスクが報告されている
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

Purpose & Output Contractの最小の実成果物をmain contextで作成する。parse/open・secret・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはそのままhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。

# run-governance-automation

## Purpose & Output Contract

`scripts/`のautomation entrypointを利用目的に対応付け、help/preflight後に実行結果を返す。

## Key Rules

- `runtime_root_policy: host-skill-path` を適用する。Claude Code は `CLAUDE_PLUGIN_ROOT`、Codex は host が提示したこの `SKILL.md` の絶対パスから plugin manifest のある祖先を探索して plugin root を解決する。各 Bash 呼出し内で実在する絶対パスを `PLUGIN_ROOT` に設定する。cwd 推測や未設定変数のまま実行することは禁止し、解決できなければ停止する。
- 最初に対象scriptの`--help`を実行する。
- `guard-change-category.py` は consumer の作業ディレクトリを保って実行する。`python3 "$PLUGIN_ROOT/scripts/extract-plugin-root.py" skill-governance-config` で依存pluginの実在する絶対rootを解決し、`--policy "<解決済config-plugin-root>/config/governance-policy.json"` を渡す。未検出・不正policyはexit2で停止し、repo配置を仮定しない。`--bypass-cooldown` も現物SHAに一致する承認済みincident以外には使わない。

- apply/rollback/通知は明示承認なしに実行しない。
- exit非0やreceipt欠落を成功へ畳まない。

## ゴールシーク実行

目的に合う実在scriptを選び、入力・write scope・rollbackを確認する。read-only checkがあれば先に実行し、許可された操作だけを続行する。

## 検証

実行command、exit code、changed paths、残リスクを報告する。

## Gotchas

- consumerのcwdはpolicyの置き場ではない。解決済みconfig-plugin-rootの実在policyを `--policy` で渡し、未検出や不正JSONを成功にしない。
- 同じファイルの過去変更はカテゴリーを変えてもcooldown対象になる。現在の承認は一致するSHAまたは明示したproposalに限定し、古い承認を新内容に流用しない。
