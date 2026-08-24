---
name: run-governance-adapters
description: governance出力adapterの利用可能性を確認したいとき、入出力契約と代替経路を安全に特定したいときに使う。
kind: run
prefix: run
goal_seek:
  engine: inline
  fork: inline
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
effect: conversation-output
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-adapters
source-tier: internal
runtime_root_policy: host-skill-path
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 実在adapterだけを列挙しpath traversalを拒否したうえで選択adapterのhelpと入出力契約を実行前に確認している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: credentialや送信先を推測せず実行結果または未対応理由をexit codeとreceipt付きで報告している
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

# run-governance-adapters

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

`scripts/adapters/`のadapterを列挙し、選択したadapterのhelpと入出力契約を確認したうえで、**副作用を持たない範囲** (`--help` と `--dry-run`) だけを実行してSink Contract v1.0のJSON resultとexit codeを報告する。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- adapter名を実在一覧から選び、path traversalを許可しない。
- credentialや送信先を推測しない。
- **本skillは外部書込を実行しない** (`effect: conversation-output`の実体的根拠)。`sink_http.py` / `sink_notion.py` / `sink_sheets.py` / `sink_slack.py` は script header で`network: true`を宣言し、keychain由来のcredentialで実際にPOSTするため、本skillからは`--dry-run`付きでのみ起動する。`--dry-run`無しの実送信と`dispatch.py`の実配送は本skillの責務外であり、`external_mutation_guard` (preview→confirm→authorize→execute の受領証フロー) を持つ呼び出し元skillへ委譲する。委譲先が無い場合は実行せず未対応理由として停止する。
- 実行許可は「credentialを参照しない呼び出し」であり、`--dry-run`はその十分条件にすぎない。`--dry-run`を持たない`resolve_route.py`は`network: false` / `write-scope: none`の純読取なので`--registry`付きの通常起動も許可する。配送先の代替経路そのものを確認するときは`dispatch.py --dry-run`を使う。
- credentialは実送信経路でのみ解決される (`scripts/secret_helper.py`経由の遅延解決)。`--help`と`--dry-run`はkeychain provider (`skill-governance-secrets`の`secrets/keychain_helper.py`) が未配備でも成立し、実送信時のみ未配備が`status: failure` / exit 2として現れる。

## ゴールシーク実行

対象adapter、入力、期待出力を確定し、`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/adapters/<adapter>.py" --help`で契約を確認する。未解決入力がなくなった場合だけ`--dry-run`付きで起動する。

## 検証

exit codeと、adapterが返す**Sink Contract v1.0のJSON result** (`status` / `adapter` / `location` / `external_id` / `dry_run`) を報告する。これはexternal-mutation guardの受領証 (preview/confirmation/authorization/completion) とは別物であり、本skillはguard受領証を発行しない。未対応adapterと実送信要求は理由付きで停止する。
