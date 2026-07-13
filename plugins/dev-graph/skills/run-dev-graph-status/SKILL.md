---
name: run-dev-graph-status
description: dev-graph node を metadata で検索したいとき、依存・tombstone・completion 状態を副作用なしで確認したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C18
kind: run
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--id ID] [--kind KIND] [--project ID] [--domain NAME] [--status STATUS] [--tag TAG] [--keyword TEXT]"
allowed-tools: [Read, Bash, AskUserQuestion, Skill, Agent]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py]
schema_refs: [../../schemas/graph-node.schema.json]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R3-status.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "検索条件 (id/種別/キーワード) と表示したい状態範囲をヒアリングして確定する"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "グラフストア横断検索と状態表示の計画を組み立てる"
  - id: R3-status
    name: status
    prompt_required: true
    summary: "validate-graph-schema.py で読み取ったグラフストアから該当ノードを検索し、status/closed_at/依存関係を含む状態表示レポートを返す (書込みは行わない)"
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
      text: "validate-graph-schema.py で読み取ったグラフストアの検索結果に必須キー欠落が0件で、検索/状態表示がグラフ実状態と一致する"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "検索/状態表示の結果がグラフストアの実際の状態 (status/closed_at/依存関係) と一致することを受入テストが確認する"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "本 skill 実行後もグラフストアと GitHub Issue 側に一切の変更が生じない (read-only で副作用なし) ことを受入テストが確認する"
      verify_by: test
---

# run-dev-graph-status

## Purpose & Output Contract

- 入力: C24/C11 で read-only 検証済み graph store、scope/filter/tag match mode。
- 出力: node identity、classification、path、status/closed_at、依存関係、feature/tracker linkage を持つ検索 report。
- 完了条件: report が graph 実状態と一致し、実行前後の graph/config/content digest が不変で外部副作用0である。

C24 で caller root を固定し、C11 の read-only validation 後に graph store を検索する。全 filter は AND、複数 tag は明示された match mode に従う。結果は `graph_node_id/artifact_kind/project_id/domain/tags/file_path/status/closed_at/depends_on/dependents/parent_feature/feature_package_id/tracker_binding/linkage` を返す。

検索前後の graph/config/content digest を比較し、変化があれば失敗。GitHub/Beads command、writer、render、sync を呼ばない。該当なしは空 result の成功、schema 不正・root 外 file_path・dangling dependency は診断付き失敗。

## ゴールシーク実行

### ゴール (Goal)

特定のissue/task/specification/architecture/documentをgraph_node_id/artifact_kind/project_id/domain/status/tagsで検索し、依存関係・close/tombstone状態をread-onlyで確認できる状態になっている

### 目的・背景 (Why)

特定ノードの検索・状態確認 (要件C11) を独立の読取り専用経路として提供しないと、状態確認のたびに sync/render 相当の重い処理を経由せざるを得ず、副作用のない検索操作が書込みを伴う操作と混同されるリスクがあるため

### 完了チェックリスト

- [ ] query は許可 filter field と明示 tag match mode だけを持つ
- [ ] `validate-graph-schema.py` が exit0 で root 外 file_path と dangling dependency が0件である
- [ ] report の status/closed_at/depends_on/dependents/linkage が graph snapshot と一致する
- [ ] 該当なしが空 result の成功として返る
- [ ] 実行前後の graph/config/content digest が同一で外部 write が0件である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: `validate-graph-schema.py`後の結果は必須キー欠落が0件である。
- `criteria:OUT1`: reportの`status/closed_at/依存関係`はgraphの実状態と一致する。
- `criteria:OUT2`: 実行前後のdigestを比較し、graph/content/GitHubの副作用0件を保証する。

## Gotchas

- filter 間は OR に緩めず、全て AND で適用する。複数 tag は指定された match mode に従う。
- node 本文から status を推測せず、graph の `status/closed_at` をそのまま報告する。
- 該当なしは空 result の成功とし、schema 不正や dangling dependency と混同しない。
- writer、sync、render、GitHub/Beads command を呼び出さない。
