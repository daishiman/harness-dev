---
name: run-dev-graph-requirements
description: 確定 system spec と feature package から実装要件を導出したいとき、readiness 完了時だけ capability-build/task-graph build へ handoff したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C04
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--feature-id ID] [--handoff-target PATH]"
allowed-tools: [Read, Write, Bash, Skill, AskUserQuestion]
runtime_root_policy: host-skill-path
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/build-requirements-handoff.py, ../../scripts/validate-goal-seek-runtime.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/package-registration-receipt.schema.json, ../../schemas/package-registration-evidence.schema.json]
reference_refs: [../../templates/template-contract.json, ../../../system-dev-planner/references/feature-execution-package-contract.md]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R2b-readiness.md
  - prompts/R3-handoff.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "要件定義導出対象のグラフノード範囲と capability-build handoff 先をヒアリングして確定する"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "5 artifact kindを横断し、C19が取り込んだsystem-spec-harness成果物とexternal plugin system-dev-planner (run-system-dev-plan) 由来のsystem task planを引用する要件抽出計画を組み立てる"
  - id: R2b-readiness
    name: readiness
    prompt_required: true
    summary: "C11の純粋validation reportとC02が保存したimplementation_readiness/evaluation_statusを照合し、不一致またはincomplete/pending/fail/staleならmissing sectionsをsurfaceしてhandoffを保留する"
  - id: R3-handoff
    name: handoff
    prompt_required: true
    summary: "C11のreadiness検証とsystem-dev-planner所有のsystem-plan検証 (validate-system-plan.py) の完了時だけ要件定義書をcapability-build/task-graph buildへhandoffする。不足時はmissing_sectionsを返して停止し、実装コードは生成しない"
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
  max_loops: 5
completeness_exempt:
  - "manifest: goal_seek.engine=inline が未達 checklist から実行局面を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行を正本とする。"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "C11のreadiness validation digestとC02保存済みimplementation_readiness/evaluation_status/source_digestが一致し、system-dev-plannerのvalidate-system-plan.pyがP01..P13 exact 13・共通parent_feature/feature_package_id・機能内前方dependencyを検証して必須キー欠落とstale digestが0件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "導出した要件定義書が capability-build/task-graph build へ handoff され、本 skill 自身が実装コードを生成しないことを受入テストが確認する"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "implementation_readiness=incompleteの参照ノードが混在するとき、missing_sectionsが漏れなくレポートへsurfaceされ、当該ノードのhandoffが保留されることを受入テストが確認する (要件C20)"
      verify_by: test
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

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-dev-graph-requirements

## Purpose & Output Contract

- 入力: C24/C11 検証済み subgraph、C02 registration receipt の `c11_readiness_digest`（legacy receiptではC02発行のversioned supplemental evidence）、readiness/evaluation/source digest、system-dev-planner package。
- 出力: requirements document、readiness matrix、snapshot digest に固定した capability-build/task-graph handoff。
- 完了条件: C11/C02/validate-system-plan の三 gate が同一 digest で PASS し、missing section が0、本 skill による実装 code 生成が0である。

実装コードは生成しない。graph の5 artifact kind、C19 が取り込んだ system-spec lineage、external system-dev-planner の feature execution package を引用して requirements handoff を作る。

`build-requirements-handoff.py` を唯一の実行 entry point とする。この command がC24 receiptの`local_state_paths.graph`とその親state directoryをauthorityとし、C11、C02保存state、system-dev-planner の `validate-system-plan.py` / readiness gate、P01..P13 exact set、lineage/digest、前方 dependency を一括して fail-closed 検証する。C02 receiptは新旧ともschema/status/package/parent/count/phase/node/revision/digest/outputをexact照合し、legacyの差分は`c11_readiness_digest`の有無だけとする。C11 はfeature-scoped `readiness_digest`を返し、現行C02 receiptの同名digestとexact matchした場合だけ進む。digestを持たないlegacy immutable receiptでは、maintained C02のidempotent `register`が発行した`package-registration-revalidation/v1`だけを許可し、receipt SHA・current graph SHA/revision・C11 digest・live readiness source・package/node/sourceをexact照合する。実行時reportを後からaggregate hash化して代用せず、ad hoc Python driver で handoff を組み立てない。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-requirements-handoff.py" \
  --repo-root "$DEV_GRAPH_ROOT" \
  --feature-id "<FEATURE_ID>" \
  --package "$DEV_GRAPH_ROOT/<SYSTEM_PLAN_PACKAGE_JSON>"
```

command が exit 0 で返した `requirements`、`readiness_matrix`、`handoff`、`task_count=13`、`implementation_code_files=0` の receipt だけを採用する。同じsnapshotの再実行は`write_count=0` / `idempotent=true`で、永続receipt/goal anchorにはrepo-relative pathだけを保存する。goal anchor/output/validator authorityを全て書込み前にpreflightし、exit 1/2、`missing_sections`、digest 不一致のどれかがあればhandoffを生成・更新せず停止する。validator差替えはtest-only契約外では拒否する。

出力は readiness matrix と handoff package。`run-system-dev-plan` の出力を消費するが dev-graph 自身は task spec を作らない。

## ゴールシーク実行

### ゴール (Goal)

system-spec-harness確定成果物とsystem development task planを含むグラフ情報から実装要件を導出し、implementation-readiness完了時だけcapability-build/task-graph buildへ実装をhandoffした状態になっている

### 目的・背景 (Why)

実装コード生成は既存 capability-build/task-graph build へ責務分離するため、本ハーネスはグラフ情報から要件定義を導出するところまでを担う。要件定義が参照する各成果物がテンプレート必須セクションを充足していない (implementation-readiness不足) まま handoff すると後段 build が要件不足のまま着手してしまうため、本 skill が readiness を機械判定し不足セクションを事前に surface する (要件C20)。system development task planはexternal plugin system-dev-plannerのrun-system-dev-planをSkill呼出しで引用する (external_contract_ref: plugin-plans/system-dev-planner/handoff-run-plugin-dev-plan.json)。implementation_readiness/validator (validate-system-plan.py) も同pluginが所有する

### 完了チェックリスト

- [ ] scope 内 node の feature/package/system-spec lineage closure が欠落0である
- [ ] C11 report と C02 保存済み readiness/evaluation/source digest が一致する
- [ ] incomplete/pending/fail/stale node の missing_sections と remediation owner が全件表示される
- [ ] 全 gate PASS の場合だけ requirements と capability-build handoff が同一 snapshot digest で生成される
- [ ] 同一 snapshot の再実行がwrite 0で、失敗時に新しいhandoff/goal anchorが0件である
- [ ] 本 skill が生成した実装 code file が0件である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: inline` / `max_loops: 5` を実行契約とする。固定手順は使わず、main context で未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 正規 command が元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-progress.json` へ materialize する。手作業で代替しない。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、main context でその周回の処理を実行する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に共有 validator を実行し、goal-spec/progress/intermediate の欠落・goal drift・hash 不一致を fail-closed にする。`required_keys` と `hashlib.sha256` の判定実装はこの validator をSSOTとする。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-goal-seek-runtime.py" \
  --goal-spec "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-goal-spec.json" \
  --progress "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-progress.json" \
  --intermediate "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-intermediate.jsonl"
```

## Criteria acceptance

- `criteria:IN1`: `validate-graph-schema.py --feature-id <FEATURE_ID>` の `readiness_digest` と現行C02 receiptの `c11_readiness_digest`、またはlegacy receiptに対するC02 supplemental evidenceの同digestがexact一致すること。legacy evidenceはreceipt/current graph/live readiness source/package exact 13を全て束縛し、missing/mismatchならhandoff 0件。system-dev-plannerの`validate-system-plan.py`もP01..P13 exact 13・共通`parent_feature/feature_package_id`・機能内前方dependencyを検証し、必須キー欠落が0件であることを要求する。`gh-bridge.py`由来issue contextは代替にしない。
- `criteria:OUT1`: requirementsを`capability-build/task-graph`へhandoffし、本skill自身は実装コードを生成しない。
- `criteria:OUT2`: `implementation_readiness=incomplete`では全`missing_sections`をsurfaceし、該当handoffを保留する。

## Gotchas

- node 内の readiness 値だけを信頼せず、C11 report、C02 saved state、source digest を同時に照合する。
- C02のlegacy registration receiptに`c11_readiness_digest`が無い場合、旧receiptを書換えない。正規`register-package.py register`を同じpackageでidempotent再実行してcontent-addressed supplemental evidenceを発行し、そのexact evidenceが揃うまでhandoffしない。
- `validate-system-plan.py` の exact-13 検証を独自ロジックで代替しない。
- 一時 driver や heredoc で正規 command の gate/handoff を再実装しない。
- incomplete/pending/fail/stale を一部 handoff で回避せず、対応する `missing_sections` を全件返す。
- 実装は capability-build/task-graph に引き渡し、本 skill 内で code を生成しない。
