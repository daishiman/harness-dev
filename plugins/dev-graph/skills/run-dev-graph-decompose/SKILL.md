---
name: run-dev-graph-decompose
description: 大きな自然文構想を feature・architecture・機能間依存へマクロ分解したいとき、ready feature の system-dev-planner package を atomic 登録・binding 別投影したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C14
kind: run
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "<want|--package PATH> [--repo-root PATH] [--manual-plan] [--dry-run]"
allowed-tools: [Read, Write, Bash, Skill, AskUserQuestion, Agent]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/gh-bridge.py, ../../scripts/bd-bridge.py]
schema_refs: [../../schemas/graph-node.schema.json]
reference_refs: [../../../system-dev-planner/references/feature-execution-package-contract.md, ../../references/execution-tracker-contract.md]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R2b-feature-planning.md
  - prompts/R3-decompose.md
  - prompts/R4-project.md
  - prompts/R6-dryrun.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "自然文の「やりたいこと(大)」とマクロ分解の粒度基準 (feature単位)・機能間依存推定方針、および --dry-run 指定の有無をヒアリングして確定する"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "自然文のwantからfeatureノード群+architectureノード+機能間depends_onへのマクロ分解案を組み立てる (1機能=13タスク仕様書への細分解はsystem-dev-plannerへ委譲しここでは行わない)"
  - id: R2b-feature-planning
    name: feature-planning
    prompt_required: true
    summary: "ready featureごとにsystem-dev-plannerを起動し、返却packageがP01..P13 exact 13 task/13-node DAG、共通parent_feature/feature_package_idを満たす場合だけC02へ渡す。手動/system-dev-planも同じ検査経路を通す"
  - id: R3-decompose
    name: decompose
    prompt_required: true
    summary: "C02で全feature/task (system-dev-planner/`/system-dev-plan`が返すpromoted task含む) のbinding/path/dependency/parent_featureを事前検証してall-or-none登録する。eligible taskをbinding=beadsならC28 create/dep-add、githubならC12 Issue、noneなら外部writeなしへ振り分け、既存linkageは再起票しない"
  - id: R4-project
    name: project
    prompt_required: true
    summary: "tracker_binding=githubかつissue_and_projectsのtaskだけをconfigured Projectsへ冪等追加し、Statusはlocal_to_projectで初期化する。beads mirrorとnoneはProject mutationしない"
  - id: R5-retry
    name: retry
    prompt_required: false
    summary: "Issue成功後のProject mutation失敗はローカルtask/Issue linkageを維持し、alias単位のsync_state=pending_retryとして次回C03 syncへ渡す"
  - id: R6-dryrun
    name: dryrun
    prompt_required: true
    summary: "--dry-run時はIssue/Project mutationを一切実行せず、Issue body、Project targets、field valuesのpreviewだけを返す"
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: goal_seek.engine=inline が未達 checklist から実行局面を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行を正本とする。"
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "validate-graph-schema.py で分解生成ノードを送信前検証しスキーマの必須キー欠落が 0 件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "マクロ分解結果 (feature+architecture+機能間depends_on) のDAGが循環なし・粒度閾値内で、評価前draftはIssue起票0件、confirmed/pass/readiness completeへの昇格後だけ起票対象になる"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "同一入力を二回実行してもbinding=beadsはbd issue/blocks edge、binding=githubはIssue/Project item、binding=noneはlocal nodeだけを各1組維持する"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "--dry-run時にlocal graph/Beads/GitHub/Projects writeが0件のままbinding解決と投影差分だけがpreviewされる"
      verify_by: test
    - id: OUT4
      loop_scope: outer
      text: "mode=both+auto、github+local_only、beads+Issue publicationを各fixtureでfail-closedし、外部write 0件となる"
      verify_by: test
    - id: OUT5
      loop_scope: outer
      text: "local batch成功後の外部mutation失敗でlocal taskを維持し、失敗node/operationだけpending_retryから冪等再実行できる"
      verify_by: test
    - id: OUT6
      loop_scope: outer
      text: "同一ready featureへの自動起動を二回実行してもP01..P13 exact 13 taskが一組だけ維持され、全taskのparent_feature/feature_package_idが一致する"
      verify_by: test
    - id: OUT7
      loop_scope: outer
      text: "同一featureに対する自動起動結果と手動`/system-dev-plan`実行結果は同じparent_featureで登録され、経路の違いによる二重登録が生じない"
      verify_by: test
---

# run-dev-graph-decompose

## Purpose & Output Contract

- 入力: 大きな want、feature 粒度/依存方針、C24/C11 検証済み graph context、任意の system-dev-planner package。
- 出力: feature/architecture/機能間 DAG の macro report、ready feature ごとの exact-13 package receipt、binding 別 publication report。
- 完了条件: macro DAG に phase-task 混入0、ready package が P01..P13 exact-set、自動/手動経路の二重登録0、dry-run write 0 である。

## Hard boundary

dev-graph はマクロ層: purpose/goal/scope/acceptance を持つ feature、共有 architecture node、feature 間 `depends_on` を所有する。system-dev-planner はミクロ層: **1 feature から P01..P13 の13 task specs/DAG/package** を所有する。本 skill が phase task を独自生成してはならない。

## Macro flow

1. 大きな want、feature 粒度、依存推定方針、dry-run を確認する。
2. want を feature 候補と architecture context に分解し、各 feature に `purpose/goal/scope_in/scope_out/acceptance/architecture_refs` を付ける。循環と実装粒度の task 混入を独立 auditor で拒否する。
3. C02 preview/atomic writer で macro graph を登録する。draft/unconfirmed/readiness incomplete は tracker 投影しない。
4. feature 間依存が満たされた ready feature ごとに `run-system-dev-plan` を Skill 呼出しする。`--manual-plan`/`/system-dev-plan` 結果も同じ package gate へ入れる。
5. P01..P13 exact 13、共通 parent/package、13-node DAG、source digest を検証し、C02 `register-package` へ渡す。`graph_node_id+source_digest` で自動/手動の二重登録を防ぐ。
6. `beads` は C28 create/dep-add、`github` は C12 Issue/任意 Projects、`none` は local only。mode=both+auto、github+local_only、beads+GitHub Issue mutation は fail-closed。

local commit 後の外部失敗は rollback せず node/operation 単位 pending_retry。`--dry-run` は local/Beads/GitHub write 0。出力は macro report、per-feature package receipt、publication report。

## ゴールシーク実行

### ゴール (Goal)

自然文の「やりたいこと(大)」からfeatureノード群+architectureノード+機能間depends_onを生成するマクロ分解を行い、ready featureごとにsystem-dev-planner(ミクロ層)を自動起動または手動`/system-dev-plan`実行結果を受理してpromoted typed task群をparent_feature付きでC02へatomic登録し、binding=beadsはC28へissue/依存edge、binding=githubはC12へIssue/任意Projects、binding=noneはローカルのみへ冪等投影した状態になっている

### 目的・背景 (Why)

マクロ (feature/architecture/機能間依存の保持+実行オーケストレーション) とミクロ (1 feature→13タスク仕様書) の責務混線を避けるため、C14は自然文のwantをfeature+architecture+機能間depends_onへ分解するところまでを担い、feature単位の細タスク仕様書生成はexternal plugin system-dev-planner (external_contract_ref: plugin-plans/system-dev-planner/handoff-run-plugin-dev-plan.json) へ委譲する。ready feature (機能間depends_on充足) ごとに [自動] run-system-dev-planをSkill呼出しでpurpose/goal/scope_in/scope_out/acceptance/architecture_refsを入力文脈として渡し、[手動] 人間の`/system-dev-plan`実行結果も同じ入口として受理する。両経路が返すpromoted typed taskはgraph_node_id+source_digestを冪等キーにC02単一writer経由でparent_feature=当該featureとしてatomic登録し、二重登録を防ぐ。既存の「自然文とpromoted system taskの入口一本化」責務は維持し、tracker_binding_intentはC02がrepo-configと照合して解決し、mode=bothのautoは拒否する。beadsはC28 create/dep-add、githubはC12 Issue/Projects、noneはlocal graphだけへ投影する。GitHub binding+local_onlyは未管理taskを生むため拒否する

### 完了チェックリスト

- [ ] macro result が feature/architecture/機能間 depends_on だけを持ち循環と phase-task 混入が0件である
- [ ] draft/unconfirmed/evaluation非pass/readiness非complete の tracker publication が0件である
- [ ] 各 ready feature package が P01..P13 exact 13、共通 parent/package、13-node DAG を満たす
- [ ] C02 local commit が all-or-none で、自動/手動経路の重複 node が0件である
- [ ] beads/github/none の各 task が単一 projection authority と linkage を持つ
- [ ] `--dry-run` の local/Beads/GitHub/Projects write count が0である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: `validate-graph-schema.py`で生成nodeを検証し必須キー欠落が0件である。
- `criteria:OUT1`: `feature+architecture` DAGは循環なし・task粒度混入なしで、評価前draftのIssue起票は0件、tracker投影は`confirmed/pass/readiness complete`だけに限定する。
- `criteria:OUT2`: 同一入力を二回実行しても`binding=beads`はbd issue/blocks edge、`binding=github`はIssue/Project item、`binding=none`はlocal nodeを各一組だけ維持する。
- `criteria:OUT3`: `--dry-run`はlocal/Beads/GitHub/Projects write 0件である。
- `criteria:OUT4`: `mode=both+auto`、`github+local_only`、`beads+Issue publication`の各authority衝突をfail-closedにし、外部write 0件にする。
- `criteria:OUT5`: local batch成功後の外部失敗は対象operationだけを`pending_retry`から冪等再実行する。
- `criteria:OUT6`: 同一ready featureの自動起動を重ねても`P01..P13 exact 13`は一組だけで、全taskの`parent_feature`と`feature_package_id`が一致する。
- `criteria:OUT7`: 自動経路と手動/system-dev-plan経路は同一parent featureへ収束し二重登録0件である。

## Gotchas

- dev-graph は macro feature/DAG だけを作り、P01..P13 task spec 生成を再実装しない。
- draft/unconfirmed/readiness incomplete の feature/task を tracker へ投影しない。
- 自動と手動の planner 結果を別 gate にせず、同じ `graph_node_id+source_digest` の冪等キーへ収束させる。
- local commit 後の外部失敗で macro graph を rollback せず、失敗 operation だけを `pending_retry` に残す。
- `mode=both+auto`、`github+local_only`、`beads+Issue mutation` は authority 衝突として fail-closed にする。
