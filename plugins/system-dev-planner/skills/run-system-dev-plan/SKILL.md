---
name: run-system-dev-plan
description: dev-graph の1 featureを exact 13 task specsへ分解したいとき、独立評価後に13-entry inventory・13-node DAGを atomic promotionしたいときに使う。
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
version: 0.1.0
owner: team-platform
source: plugin-plans/system-dev-planner/component-inventory.json#C01
user-invocable: true
disable-model-invocation: false
argument-hint: "--feature-id <graph-node-id> --feature-context <repo-relative-json> [--repo-root DIR] [--config .dev-graph/config.json]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Skill, Task]
context: inherit
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-decompose.md
  - prompts/R3-emit.md
  - ../../agents/system-dev-plan-elicitor.md
  - ../../agents/system-dev-plan-architect.md
  - ../../agents/system-dev-plan-evaluator.md
schema_refs:
  - ../../schemas/feature-context.schema.json
  - ../../schemas/feature-execution-package.schema.json
  - ../../schemas/workstream-inventory.schema.json
  - ../../schemas/system-build-handoff.schema.json
reference_refs:
  - ../../references/repo-local-runtime-contract.md
  - ../../references/feature-execution-package-contract.md
  - ../../references/atomic-promotion-contract.md
script_refs:
  - ../../scripts/resolve-project-context.py
  - ../../scripts/check-implementation-readiness.py
  - ../../scripts/init-project-layout.py
  - ../../scripts/manage-system-plan-lock.py
  - ../../scripts/build-system-handoff.py
  - ../../scripts/validate-system-plan.py
  - ../../scripts/promote-system-plan.py
  - ../../scripts/validate-inline-goal-seek-anchor.py
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
  spec: eval-log/run-system-dev-plan-goal-spec.json
  progress: eval-log/run-system-dev-plan-progress.json
  max_loops: 5
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "1 feature の分解が exact 13 task specs と 13-entry inventory・13-node の intra-feature DAG を生成し validate-system-plan.py が DAG 非循環/orphan 0/inventory 矛盾 0/13 件厳密一致で exit0 通過する"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "各 task spec が system-task-spec 構造契約と workstream-inventory.schema.json の語彙(workstream_kind/build_target_kind)を満たし build-system-handoff.py が system-build-handoff.schema.json 準拠の handoff を exit0 生成する"
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: "確定 system-spec 起点の分解が feature 境界と repository boundary を保ち UBM 固有物を混入せず run-elegant-review の C1-C4 を全 PASS する"
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: "13 task specs が atomic promotion 前提の readiness(check-implementation-readiness.py)を満たし各 spec が実装者へそのまま渡せる粒度であると fork した system-dev-plan-evaluator が確認する"
      verify_by: evaluator
    - id: OUT3
      loop_scope: outer
      text: "実 feature-context を入力に end-to-end で R1-elicit→R2-decompose→R3-emit を走らせ、生成された 13 task specs が staging へ atomic promotion され二回目実行で構造が変化しないことを受入テストが確認する"
      verify_by: live-trial
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
runtime_root_policy: host-skill-path
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# System development planning

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

- **入力**: caller repository 内の `--feature-id` と repo-relative `--feature-context`、confirmed system-spec/readiness。C09 が realpath containment・feature id・digest を固定する。
- **出力**: exact 13 task specs、13-entry inventory、13-node DAG、`system-build-handoff.json`、staging/promotion/registration receipts。すべて同一 feature digest に接地する。
- **完了条件**: C12 決定論 gate と独立 evaluator C1-C4 が同一 digest を PASS し、C11 が atomic promotion して lock を解放した状態。
- **非目標**: 実装codeの生成、複数featureの同時分解、exact-13 外タスクの混入、dev-graph registration receipt の自己発行は行わない。

## Invariants

- caller repository の解決と全 path 検査は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/resolve-project-context.py` に一元化する。`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` は code/assets の位置決めだけに使い、caller の文書・状態の authority にはしない。
- 1 run は1 `parent_feature` のみを扱い、P01..P13 各1件の exact 13 executable tasks を生成する。別の13 phase 文書と14件目は生成しない。
- C08 readiness、C14 handoff producer、C12 deterministic validationが一致したactual exact-13 packageをusable draftとして書き出し、path/digest/開き方を先に提示する。fork evaluator C1..C4はlight/standard/detailed選択後だけ起動し、初回提示を待たせない。post-choiceのfinal promotion/publishは同じcanonical digestを再検証してから行う。
- staging lock は C13 `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/manage-system-plan-lock.py` だけが生成・更新・解放する。`repository_id/run_id/session_owner/feature_id/feature_digest/acquired_at/heartbeat_at/expires_at` を束縛し、開始時に `acquire`、各動的計画反復に `renew`、成否にかかわらず終了処理で `release` を実行する。他 component は lock JSON を直接作成・書換・削除しない。
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/guard-implementation-readiness.py` は run 識別 env に依存せず repository-local canonical lock を自己発見し、malformed same-repository lock を fail-closed 拒否し、`expires_at` 超過 lock は C13 と同じ audit receipt 規則で cleanup する。

## `init`

`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/init-project-layout.py" --repo-root "$CLAUDE_PROJECT_DIR"`

missing config keys/directories だけを作成し、既存値・docs/specs/tasks/issues を上書きしない。receipt と repository_id 導出元を保存する。

## `plan`

`--feature-id` と `--feature-context` は必須。feature context は caller repository 相対 JSON で、`graph_node_id`, `artifact_kind=feature`, `purpose`, `goal`, `scope_in`, `scope_out`, `acceptance`, `architecture_refs`, `updated_at` を持つ。C09 が realpath containment を検証し、JSON の `graph_node_id` と `--feature-id` が一致しなければ staging 作成前に停止する。absolute path、`..`、root 外 symlink、別 repository の context は拒否する。

pre-choiceではmain contextがexact-13 packageの最小usable draftを1回生成し、C12 deterministic validationを通してpath/digestを提示する。以下の動的計画・fork evaluator・反復・promotionは利用者がlight/standard/detailedを選んだ後だけ開始する。

- C09 repo context と feature identity/context digest が確定している。
- C08 が system-spec index/requirements/architecture graph を `complete` と判定している。
- C13 が repository_id/run_id/session_owner/expires_at と feature id/digest を束縛した staging lock を atomic acquire し、各反復で heartbeat renew している。
- elicitor の goal-spec と architect の exact-13 package が同じ feature digestを参照する。
- C14 が exact-13 source の個別 SHA-256 と registration request/receipt owner 境界を持つ `system-build-handoff.json` を生成し、その bytes が `staging-manifest.json` の canonical digest に含まれている。handoff は receipt を自己発行しない。
- pre-choiceのC12 deterministic validationが提示対象digestをPASSしている。post-choiceではfork evaluator C1..C4がその同一digestを診断し、改善後はC12を再実行する。
- C11 が same-filesystem atomic promotion、immutable receipt、registration manifest、current pointerを生成している。
- C11 が promotion receipt/registration request を所有し、dev-graph の all-or-none apply が発行する registration receipt と境界が一意である。C13 lock が解放され、published path/digest/receipt が dev-graphへ返されている。
- **計画構造レポート (plan-structure) が生成されている**: promotion 済み `task-graph.json` から「この feature で何をやるか + exact-13 タスク・ノード・依存の関係性」を 1 枚の自己完結 HTML (`plan-structure-report.html`) へ投影する。目的/本質的課題/できることの価値セクション (goal-spec / `value-narrative.json` 由来・非エンジニア/技術者の dual audience) と依存関係表を携帯し、build 前に計画の全体像を確認できるようにする。**plugin-dev-planner と共通の完了ステップ**として、両プランナーとも同一の共有 reporter を best-effort で呼ぶ (harness-creator 未配備環境では skip・非ゲート):
  `python3 plugins/harness-creator/scripts/project-task-status.py --task-graph <PLAN_DIR>/task-graph.json --goal-spec <PLAN_DIR>/goal-spec.json --out-html <PLAN_DIR>/plan-structure-report.html --out-md <PLAN_DIR>/plan-structure.md --out-json <PLAN_DIR>/plan-structure-status.json`
  `--goal-spec` を渡さないと reporter の価値セクション (目的/本質的課題/できること) は fail-soft で沈黙欠落する。非エンジニア向け平易層 (`plain_intro` 等) を出すには curated `value-narrative.json` を PLAN_DIR に用意する (未用意なら平易層のみ省略)。
- **仕様書ブラウザ (task-specs.html) が生成されている**: 13 フェーズ仕様書 (phase-01..13) と `task-specs/*.md` の本文を、サイドバー index → 各仕様書へページ遷移 → ブラウザ back で戻れる自己完結 HTML にする (中身閲覧ビュー)。構造/依存/価値の `plan-structure-report.html` と対になり、相互リンクで往復できる。**plugin-dev-planner と共通の完了ステップ** (best-effort・非ゲート):
  `python3 plugins/harness-creator/scripts/render-spec-browser.py --plan-dir <PLAN_DIR>`

## ゴールシーク実行

### ゴール (Goal)

1 feature が exact 13 task specs、13-entry inventory、13-node DAG、handoff に分解され、決定論 gate と独立 evaluator が同一 digest を PASS した状態。

### 目的・背景 (Why)

動的な分解を許しつつ、feature 境界・exact-13・atomic promotion を周回中に変質させないため。

### 完了チェックリスト

- [ ] C09/C08/C13 の context・readiness・lock が同一 feature digest に接地した
- [ ] exact 13 package と handoff が C12 の全決定論 gate を exit0 で通過した
- [ ] `system-dev-plan-evaluator` が C1-C4 を PASS し、同一 digest を C11 が atomic promotion した

### ゴールシークループ

post-choice のみ、main context が package と lock を所有したまま未達項目を1つ改善する。改善後に C12 を再実行し、独立判定だけを `Task` で `system-dev-plan-evaluator` へ委譲する。親へは verdict・blocker・対象 digest だけを返し、5周で停止する。

### ゴールシーク配線

`goal-spec.json` の `original_goal` と feature digest を progress に固定する。各周回は intermediate JSONL へ `original_goal/current_goal_snapshot/delta_from_original/merged_directive_for_next/drift_signal`、C12 receipt digest、evaluator verdict を append し、次周回は直前の `merged_directive_for_next` を必須入力とする。

### ゴールシーク検証

post-choice 周回の各回末に共通 validator を実行し、intermediate.jsonl の `required_keys`、非空 `original_goal`、全行不変性、`original_goal_hash == hashlib.sha256(original_goal)` を fail-closed 検証する。その後に feature/C12/evaluator digest 一致を検査する。

```bash
CONTEXT_JSON="$(python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/resolve-project-context.py" --repo-root "${CLAUDE_PROJECT_DIR:?caller project root is required}" --json)" || exit $?
PROJECT_ROOT="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["repo_root"])' <<<"$CONTEXT_JSON")" || exit $?
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "$PROJECT_ROOT/eval-log/run-system-dev-plan-progress.json" \
  "$PROJECT_ROOT/eval-log/run-system-dev-plan-intermediate.jsonl"
```

## Gotchas

- best-effort の HTML reporter を cwd 相対で呼び、別repositoryの `task-graph.json` を読まない。C09 receipt の repo root と出力 containment を先に固定する。
- lock 取得前の staging write、lock 解放前の完了報告、C12/evaluator PASS 前の promotion は禁止。失敗時は旧 current を保つ。
- P01..P13 以外の14件目や別phase文書を「詳細化」として追加しない。発見作業は follow-up feature candidate へ分離する。

## Failure handling

light/standard/detailed選択後だけ frontmatter の `goal_seek`（engine=inline / fork=inline / max_loops=5）を有効化する。main context が package を所有し、独立評価だけを `Task` で system-dev-plan-evaluator へ分離する。5周で未達なら自動続行せず findings と staging path を報告する。accept-as-isではこの周回を0回のまま終了する。途中失敗時も published/current は旧世代を維持する。発見した独立作業は package に追加せず follow-up feature candidate として返す。
