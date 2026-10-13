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
argument-hint: "[--repo-root PATH] [--feature-id ID] [--package-dir REL] [--receipt REL] [--system-planner-root PATH] [--handoff-target PATH]"
allowed-tools: [Read, Write, Bash, Skill, AskUserQuestion, Agent]
script_refs: [../../scripts/_common.py, ../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/gh-bridge.py, ../../scripts/register-package.py, ../../scripts/validate-readiness-binding.py, ../../scripts/guard-requirements-handoff.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/package-registration-receipt.schema.json]
reference_refs: [../../templates/template-contract.json, ../../references/feature-execution-package-contract.md, ../../references/prompt-common-layers.md]
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
  fork: subagent
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

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-dev-graph-requirements

## Purpose & Output Contract

- 入力: C24/C11 検証済み subgraph、C02 保存済み readiness/evaluation/source digest、system-dev-planner package。
- 出力: requirements document、readiness matrix、snapshot digest に固定した capability-build/task-graph handoff。
- 完了条件: C11/C02/validate-system-plan の三 gate が同一 digest で PASS し、missing section が0、本 skill による実装 code 生成が0である。

実装コードの生成は禁止。graph の5 artifact kind、C19 が取り込んだ system-spec lineage、external system-dev-planner の feature execution package を引用して requirements handoff を作る。

1. 対象 feature/subgraph と handoff target を確定する。
2. 三 gate の照合は `validate-readiness-binding.py --repo-root <root> --package-dir <published package> --receipt <C02 receipt> [--system-planner-root PATH]` だけが行う。script は C24 (`resolve-repo-context.py --mode read`) で root を固定し、system-dev-planner の `validate-system-plan.py` を起動して `validated_digest` を得る (P01..P13 exact set・13-node DAG・共通 `parent_feature/feature_package_id` の検証は外部 validator のまま。13 task の生成ロジックは複製しない)。
3. 同じ script が、C02 の registration manifest・promotion receipt・C02 receipt の `source_digest` と `validated_digest` の一致、C11 (`validate-graph-schema.py` の validate) を通した graph の package member の readiness view (`status/confirmation_status/evaluation_status/implementation_readiness/source_digest/evaluated_digest`) の digest と C02 が保存した同じ view の digest の一致、receipt の `graph_revision_after` と同じ revision なら graph 全体の digest と `graph_digest_after` の一致を確かめる。exit 1 なら `violations` (code と node) をそのまま返して止まる。LLM が digest や readiness を読み比べて代わりに判定しない。
4. handoff 対象の node は `guard-requirements-handoff.py --repo-root <root> --node <id> [--node <id>]... --expect-graph-digest <binding の graph.digest>` に渡す。script は参照 closure (`depends_on/related_nodes/architecture_refs/parent_feature` と package member) をたどり、incomplete/unknown/pending/fail/stale/draft/superseded/tombstoned・参照切れ・C11 violation が1件でもあれば exit 1 (`status: withheld`、`handoff_count: 0`) で、closure 全件の `missing_sections` と各 blocked node の `remediation.owner` を返す。一部の node だけを handoff しない。guard は自分が読んだ graph の `graph.digest` と `graph.graph_revision` を binding と同じ定義 (C02 の canonical digest) で返し、`--expect-graph-digest` と違えば (binding の後に graph が変わった) exit 2 (`status: snapshot_mismatch`、`handoff_count: 0`) で止まる。そのときは binding からやり直す。exit 2 には report の無いもの (usage・C24・IO の例外。stdout は空で、stderr に理由が出る) もある。これも handoff 0件で止め、stderr の例外の内容を止まった理由として返す (binding からやり直すのは `status: snapshot_mismatch` の report があるときだけ)。
5. `validate-readiness-binding.py` と `guard-requirements-handoff.py` がともに exit 0 で、binding の `graph.digest` と guard の `graph.digest` が一致する (guard の `graph.digest_match: true`) ときだけ、guard の `handoff` に並んだ node について requirements document、graph snapshot digest (binding の `graph.digest`)、package reference、capability-build handoff reference を atomic emit する。

出力は readiness matrix と handoff package。`run-system-dev-plan` の出力を消費するが dev-graph 自身は task spec を作らない。

## ゴールシーク実行

### ゴール (Goal)

system-spec-harness確定成果物とsystem development task planを含むグラフ情報から実装要件を導出し、implementation-readiness完了時だけcapability-build/task-graph buildへ実装をhandoffした状態になっている

### 目的・背景 (Why)

実装コード生成は既存 capability-build/task-graph build へ責務分離するため、本ハーネスはグラフ情報から要件定義を導出するところまでを担う。要件定義が参照する各成果物がテンプレート必須セクションを充足していない (implementation-readiness不足) まま handoff すると後段 build が要件不足のまま着手してしまうため、本 skill が readiness を機械判定し不足セクションを事前に surface する (要件C20)。system development task planはexternal plugin system-dev-plannerのrun-system-dev-planをSkill呼出しで引用する (external_contract_ref: plugin-plans/system-dev-planner/handoff-run-plugin-dev-plan.json)。implementation_readiness/validator (validate-system-plan.py) も同pluginが所有する

### 完了チェックリスト

- [ ] scope 内 node の feature/package/system-spec lineage closure が欠落0である
- [ ] `validate-readiness-binding.py` が exit 0 で `violations` 0件、`readiness_digest.c11` と `readiness_digest.c02` が一致する
- [ ] `guard-requirements-handoff.py` の `missing_sections` と `blocked[].remediation` が全件表示され、exit 1 のとき handoff が0件である
- [ ] 全 gate PASS で、binding の `graph.digest` と guard の `graph.digest` が一致する場合だけ、requirements と capability-build handoff が同一 snapshot digest で生成される
- [ ] 本 skill が生成した実装 code file が0件である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-intermediate.jsonl" <<'PY'
import hashlib, json, sys
goal = json.load(open(sys.argv[1], encoding='utf-8'))
rows = [json.loads(line) for line in open(sys.argv[2], encoding='utf-8') if line.strip()]
required_keys = {'original_goal','original_goal_hash','current_goal_snapshot','delta_from_original','merged_directive_for_next','drift_signal'}
expected = hashlib.sha256(goal['original_goal'].encode('utf-8')).hexdigest()
assert rows, 'intermediate.jsonl is empty'
for row in rows:
    assert required_keys <= row.keys(), required_keys - row.keys()
    assert row['original_goal'] == goal['original_goal']
    assert row['original_goal_hash'] == expected
PY
```

## Criteria acceptance

- `criteria:IN1`: `validate-readiness-binding.py`が、C11のreadiness validation digestとC02保存済みimplementation_readiness/evaluation_status/source_digestの一致、system-dev-plannerの`validate-system-plan.py`の`validated_digest`(P01..P13 exact 13・共通`parent_feature/feature_package_id`・機能内前方dependencyの検証結果)との一致を照合し、exit 0で必須キー欠落が0件、stale digestが0件になる。`gh-bridge.py` 由来のissue contextは補助入力に留め、この三gateの代替にしない。
- `criteria:OUT1`: requirementsを`capability-build/task-graph`へhandoffし、本skill自身は実装コードを生成しない。
- `criteria:OUT2`: `guard-requirements-handoff.py`が、`implementation_readiness=incomplete`の参照ノードが1件でもあればclosure全件の`missing_sections`とremediation ownerを返し、`handoff_count: 0`で該当handoffを保留する。R3はこのscriptのexit 0のときだけhandoffする。

## Gotchas

- node 内の readiness 値だけを信頼せず、C11 report、C02 saved state、source digest の照合は `validate-readiness-binding.py` に任せる。sync などで graph の revision が登録より進んだ場合は graph 全体の digest ではなく readiness view の digest で照合される (`graph.relation: later_revision`)。登録より古い graph は拒否される。
- `validate-system-plan.py` の exact-13 検証を独自ロジックで代替しない。
- incomplete/pending/fail/stale を一部 handoff で回避せず、`guard-requirements-handoff.py` の `missing_sections` を全件返す。`schedule-graph.py` の ready set は依存の準備だけを見るので、handoff の可否には使わない。
- 実装は capability-build/task-graph に引き渡し、本 skill 内で code を生成しない。
