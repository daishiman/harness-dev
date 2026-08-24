---
name: run-dev-graph-schedule
description: feature ready と task ready を分離したいとき、依存・tracker parity・resource scope・active lease を満たす conflict-free batch を算出したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C15
kind: run
effect: conversation-output
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--scope ID] [--max-parallel N]"
allowed-tools: [Read, Bash, AskUserQuestion, Task, Skill, Agent]
runtime_root_policy: host-skill-path
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/schedule-graph.py, ../../scripts/validate-schedule-receipt.py, ../../scripts/validate-goal-seek-runtime.py, ../../scripts/manage-worktree-lease.py, ../../scripts/bd-bridge.py]
schema_refs: [../../schemas/graph-node.schema.json]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R3-schedule.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "算出対象範囲 (グラフ全体/サブツリー) と並列バッチの上限件数方針をヒアリングして確定する"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "schedule-graph.py 呼び出しと結果整形の計画を組み立てる"
  - id: R3-schedule
    name: schedule
    prompt_required: true
    summary: "binding=beadsはC28のbd ready --jsonかつstatus/depends_on edge parity=confirmedの候補だけ、github/noneはstatus=activeかつconfirmed/pass/readiness completeだけをschedule-graph.pyへ渡し、resource_scope非重複batchへ整形する"
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
      text: "schedule-graph.py のready-setがblocked/draft/unconfirmed/evaluation非pass/readiness非completeを0件で含む"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "推薦タスクが全依存 (depends_on) 充足済み (ready) であることを受入テストが確認する"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "提示した並列バッチ内で resource_scope (touches) が重複するノードペアが 0 件 (conflict-free) であることを受入テストが確認する"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "ready taskごとに一意なsuggested_branchとC09 worktree claim commandが返り、同一graph_node_idの二重claimはC27が0件に抑える"
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


# run-dev-graph-schedule

## Purpose & Output Contract

- 入力: C24/C11 検証済み graph、任意scope node、binding parity、C27 lease snapshot、max parallel。
- 出力: strict ready sets、resource-safe parallel batches、conflict pairs、`devgraph/<graph_node_id>` branch/claim command。
- 完了条件: 全推薦がscope closure内で confirmed/pass/readiness complete、全 dependency done、binding authority/lease/resource conflict 0 を同時に満たす。

1. 対象scopeとmax parallelを確定する。`--scope` はscope node→parent feature/子task/依存先の固定点closureとし、unrelated nodeを候補に入れない。
2. C27 lease snapshotを`<LEASES_JSON>`へ保存する。明示したsnapshotが欠落した場合は「leases 0件」と見なさずfail-closed停止する。repo configの`execution_tracker.mode` が`beads|both`なら、C28の正規`ready`を同じparity manifestから`<C28_READY_JSON>`へ保存する。`edge_parity.confirmed=true`だけでなく、status一致・`expected_depends_on=actual_depends_on`・`missing_edges=[]`・`unexpected_edges=[]`がすべて成立する候補だけを採用し、`conflicts[]`の候補は必ず除外する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/manage-worktree-lease.py" \
  --repo-root "$DEV_GRAPH_ROOT" --op list > "<LEASES_JSON>"

if [ "$EXECUTION_TRACKER_MODE" = "beads" ] || [ "$EXECUTION_TRACKER_MODE" = "both" ]; then
  python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/bd-bridge.py" \
    --repo-root "$DEV_GRAPH_ROOT" --op ready \
    --parity-manifest "<C28_PARITY_MANIFEST>" > "<C28_READY_JSON>"
fi
```

3. 正規ready sourceを一意に選ぶ。`beads`=`bd-bridge`+C28 evidence、`github|none`=`self`、`both`=`both`+C28 evidenceとする。`both`は`tracker_binding=beads`だけをC28から、`github|none`だけをlocal graphから取り、統合後にresource batchを再構成する。

```bash
SCOPE_ARGS=(); if [ -n "${SCOPE:-}" ]; then SCOPE_ARGS=(--scope "$SCOPE"); fi
READY_JSON_ARGS=()
case "$EXECUTION_TRACKER_MODE" in
  beads) READY_SOURCE=bd-bridge; READY_JSON_ARGS=(--ready-json "<C28_READY_JSON>") ;;
  both) READY_SOURCE=both; READY_JSON_ARGS=(--ready-json "<C28_READY_JSON>") ;;
  github|none) READY_SOURCE=self ;;
  *) echo "unsupported execution_tracker.mode" >&2; exit 2 ;;
esac

python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/schedule-graph.py" \
  --graph "$DEV_GRAPH_ROOT/.dev-graph/state/graph.json" \
  "${SCOPE_ARGS[@]}" --ready-source "$READY_SOURCE" "${READY_JSON_ARGS[@]}" \
  --leases "<LEASES_JSON>" --max-parallel "<N>" \
  --out "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-receipt.json" \
  --goal-spec "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-goal-spec.json" \
  --goal-progress "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-progress.json" \
  --goal-intermediate "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-intermediate.jsonl"
```

4. 候補 receipt を生成した親は、必ず `Task` で `subagent_type: dev-graph:dev-graph-parallel-safety-verifier` を1回起動する。C17にgraph、同一scope/lease/C28 evidence、ready source、候補 receipt、max parallelを渡し、分離contextで`<C17_RECEIPT>`を生成させる。一時verifier scriptは作らせない。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-schedule-receipt.py" \
  --graph "$DEV_GRAPH_ROOT/.dev-graph/state/graph.json" \
  --schedule "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-receipt.json" \
  "${SCOPE_ARGS[@]}" --ready-source "$READY_SOURCE" "${READY_JSON_ARGS[@]}" \
  --leases "<LEASES_JSON>" --max-parallel "<N>" \
  --out "<C17_RECEIPT>"
```

5. 親は C17 receipt の `verifier=dev-graph-parallel-safety-verifier`、`component=C17`、`verdict=PASS`、`findings=[]`、`unsafe_pairs=[]`、`schedule_digest`と候補 receipt の一致を統合確認する。scope/ready/lease digest、C28 exact parity、binding partitionの1項目でも不一致・receipt不在ならready-setを推薦しない。同じinputの再実行はschedule semantic digestが一致し、graph/C28 ready/leaseとoutput/goal anchor/C17 verdictのpath衝突は最初のwrite前に拒否する。

出力は ready sets、parallel batches、conflict pairs、各 task の `devgraph/<graph_node_id>` branch と `dev-graph worktree claim <id>` command。read-only で graph/tracker/lease を変更しない。

## ゴールシーク実行

### ゴール (Goal)

グラフの依存関係・完了状態・active worktree leaseから次に着手すべきready-setと、リソーススコープ/lease重複のない複数worktree向け並列バッチを算出・提示した状態になっている

### 目的・背景 (Why)

依存関係を都度人手で追跡せずに次の一手を判断できるようにする。binding=beadsはC28でstatusとdepends_on edge exact-set parityがconfirmedの場合だけbd ready候補を採用し、parity pending/conflictは推薦しない。その候補へdev-graph固有のresource_scope/lease重複回避を重ねる。github/noneはC16で自前算出し、mode=bothはbinding別結果を合成する。二層ready-set: feature ready (機能間depends_on充足) はper-feature planning起動候補、task ready (feature内depends_on充足+resource_scope非競合) は実行候補として区別し、feature単位の並列batchとtask単位の並列batchを混在させない (MM-10)

### 完了チェックリスト

- [ ] candidate は confirmed/pass/readiness complete、全 depends_on done、active lease なしを満たす
- [ ] scope指定時は固定点closure外のready candidateが0件である
- [ ] beads/bothは同一C28 evidenceだけを使い、status/depends_on exact parity不成立・conflict・authority不一致が推薦0件である
- [ ] feature ready と task ready が別々の ready-set/batch に出力される
- [ ] 同一 parallel batch の resource_scope.touches 重複 pair が0件である
- [ ] 各 task の suggested_branch が `devgraph/<graph_node_id>` で claim command が public CLI 形式である
- [ ] 実行前後の graph/tracker/lease digest が同一で、同一inputの再実行でschedule semantic digestが一致する

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- `schedule-graph.py` が元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、独立安全検証だけ上記 C17 `Task` へ分離する。親は候補生成・receipt統合・ユーザー提示を所有する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に共有 validator を実行し、goal-spec/progress/intermediate の欠落・goal drift・hash 不一致を fail-closed にする。`required_keys` と `hashlib.sha256` の判定実装はこの validator をSSOTとする。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-goal-seek-runtime.py" \
  --goal-spec "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-goal-spec.json" \
  --progress "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-progress.json" \
  --intermediate "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-intermediate.jsonl"
```

## Criteria acceptance

- `criteria:IN1`: `schedule-graph.py` の ready-set に blocked/draft/unconfirmed/evaluation非pass/readiness非complete の候補が 0件であることを script test で検証する。
- `criteria:OUT1`: 推薦 task は全 `depends_on` がdoneで、未充足依存を持つ候補が ready-set に0件であることを受入テストで検証する。
- `criteria:OUT2`: 同一parallel batch内の `resource_scope.touches` 重複ペアが0件で、active leaseと衝突する候補を推薦しないことを受入テストで検証する。
- `criteria:OUT3`: ready taskごとに一意な `suggested_branch=devgraph/<graph_node_id>` と `dev-graph worktree claim <id>` commandを返し、C27が同一graph_node_idの二重claimを0件に抑止することを受入テストで検証する。

## Gotchas

- `blocked/draft/unconfirmed/evaluation!=pass/readiness!=complete` のどれかを ready に混入させない。
- 直接依存だけでなく全 `depends_on` の done を確認する。
- 同一 batch の `resource_scope.touches` と active lease の両方を衝突判定に使う。
- feature planning 候補と task 実行候補を同一 batch に混ぜない。
- C17 を親 context の目視や一時 driver で代替しない。`Task` receipt がない候補は未検証である。
- beads/bothで`--ready-source`/`--ready-json`を省略しない。`both`でC28候補をgithub/none authorityとして混ぜない。
- `edge_parity.confirmed=true`の自己申告だけを信用せず、status・depends_on・missing/unexpected edgeのexact一致を照合する。
- 明示したlease snapshotの欠落や、output/goal anchor/C17 verdictがgraph/ready/lease/schedule inputを上書きするpath衝突を許容しない。
