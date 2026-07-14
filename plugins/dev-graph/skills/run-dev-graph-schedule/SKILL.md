---
name: run-dev-graph-schedule
description: feature ready と task ready を分離したいとき、依存・tracker parity・resource scope・active lease を満たす conflict-free batch を算出したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C15
kind: run
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--scope ID] [--max-parallel N]"
allowed-tools: [Read, Bash, AskUserQuestion, Task, Skill, Agent]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/schedule-graph.py, ../../scripts/manage-worktree-lease.py, ../../scripts/bd-bridge.py]
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
---

# run-dev-graph-schedule

## Purpose & Output Contract

- 入力: C24/C11 検証済み subgraph、binding parity、C27 lease snapshot、max parallel。
- 出力: strict ready sets、resource-safe parallel batches、conflict pairs、`devgraph/<graph_node_id>` branch/claim command。
- 完了条件: 全推薦が confirmed/pass/readiness complete、全 dependency done、lease/resource conflict 0 を同時に満たす。

1. 対象 subgraph と max parallel を確定する。
2. beads binding は C28 の `ready` と status/depends_on exact-set parity=confirmed の積集合だけを採用する。github/none は local graph から算出する。
3. confirmed/pass/readiness complete、全依存 done、active lease なしだけを候補にする。
4. feature ready は system-dev-planner 起動候補、task ready は実行候補として別 batch にする。両者を同じ batch に混ぜない。
5. `schedule-graph.py` の resource_scope conflict と C27 lease snapshot を重ね、同じ resource を触る組を分離する。C17 独立 verifier が不一致を出したら推薦しない。

出力は ready sets、parallel batches、conflict pairs、各 task の `devgraph/<graph_node_id>` branch と `dev-graph worktree claim <id>` command。read-only で graph/tracker/lease を変更しない。

## ゴールシーク実行

### ゴール (Goal)

グラフの依存関係・完了状態・active worktree leaseから次に着手すべきready-setと、リソーススコープ/lease重複のない複数worktree向け並列バッチを算出・提示した状態になっている

### 目的・背景 (Why)

依存関係を都度人手で追跡せずに次の一手を判断できるようにする。binding=beadsはC28でstatusとdepends_on edge exact-set parityがconfirmedの場合だけbd ready候補を採用し、parity pending/conflictは推薦しない。その候補へdev-graph固有のresource_scope/lease重複回避を重ねる。github/noneはC16で自前算出し、mode=bothはbinding別結果を合成する。二層ready-set: feature ready (機能間depends_on充足) はper-feature planning起動候補、task ready (feature内depends_on充足+resource_scope非競合) は実行候補として区別し、feature単位の並列batchとtask単位の並列batchを混在させない (MM-10)

### 完了チェックリスト

- [ ] candidate は confirmed/pass/readiness complete、全 depends_on done、active lease なしを満たす
- [ ] feature ready と task ready が別々の ready-set/batch に出力される
- [ ] 同一 parallel batch の resource_scope.touches 重複 pair が0件である
- [ ] 各 task の suggested_branch が `devgraph/<graph_node_id>` で claim command が public CLI 形式である
- [ ] 実行前後の graph/tracker/lease digest が同一である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-schedule-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: `schedule-graph.py` の ready-set に blocked/draft/unconfirmed/evaluation非pass/readiness非complete の候補が 0件であることを script test で検証する。
- `criteria:OUT1`: 推薦 task は全 `depends_on` がdoneで、未充足依存を持つ候補が ready-set に0件であることを受入テストで検証する。
- `criteria:OUT2`: 同一parallel batch内の `resource_scope.touches` 重複ペアが0件で、active leaseと衝突する候補を推薦しないことを受入テストで検証する。
- `criteria:OUT3`: ready taskごとに一意な `suggested_branch=devgraph/<graph_node_id>` と `dev-graph worktree claim <id>` commandを返し、C27が同一graph_node_idの二重claimを0件に抑止することを受入テストで検証する。

## Gotchas

- `blocked/draft/unconfirmed/evaluation!=pass/readiness!=complete` のどれかを ready に混入させない。
- 直接依存だけでなく全 `depends_on` の done を確認する。
- 同一 batch の `resource_scope.touches` と active lease の両方を衝突判定に使う。
- feature planning 候補と task 実行候補を同一 batch に混ぜない。
