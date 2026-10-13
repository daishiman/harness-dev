---
name: run-dev-graph-status
description: dev-graph node を metadata で検索したいとき、依存・tombstone・completion 状態を副作用なしで確認したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C18
kind: run
effect: conversation-output
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--id ID] [--kind KIND] [--project ID] [--domain NAME] [--status STATUS] [--feature ID] [--tag TAG] [--tag-mode any|all] [--keyword TEXT]"
allowed-tools: [Read, Bash, AskUserQuestion, Skill, Agent]
script_refs: [../../scripts/_common.py, ../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/extract-graph-status.py]
schema_refs: [../../schemas/graph-node.schema.json]
reference_refs: [../../references/prompt-common-layers.md]
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
    summary: "extract-graph-status.py の rows だけから該当ノードの status/closed_at/依存関係を含む状態表示レポートを返す (書込みは行わない)"
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
      text: "extract-graph-status.py の rows に必須キー欠落が0件で、検索/状態表示がグラフ実状態と一致する"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "検索/状態表示の結果がグラフストアの実際の状態 (status/closed_at/依存関係) と一致することを受入テストが確認する"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "本 skill 実行後もグラフストアと GitHub Issue 側に一切の変更が生じない (read-only で副作用なし) ことを受入テストが確認する"
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


# run-dev-graph-status

## Purpose & Output Contract

- 入力: C24/C11 で read-only 検証済み graph store、scope/filter/tag match mode。
- 出力: node identity、classification、path、status/closed_at、依存関係、feature/tracker linkage を持つ検索 report。
- 完了条件: report が graph 実状態と一致し、実行前後の graph/config/content digest が不変で外部副作用0である。

検索と状態表示の行は `extract-graph-status.py --repo-root <root> [filter...]` だけが作る。script は C24 (`resolve-repo-context.py --mode read`) で caller root を固定し、一度だけ読んだ graph の bytes を C11 (`validate-graph-schema.py` の validate) に通し、violation と必須キー欠落が0件のときだけ行を返す。全 filter は AND、同じ filter の繰り返しは OR、`--feature` は parent_feature か feature_package_id、2つ以上の `--tag` は `--tag-mode any|all` を明示する (無ければ exit 2)。各行は `graph_node_id/artifact_kind/title/project_id/domain/tags/file_path/status/closed_at/depends_on/dependents/parent_feature/feature_package_id/tracker_binding/issue_linkage/beads_linkage/github_project_linkages` を持つ。closed_at は graph の値、dependents は graph 全体の depends_on の逆引きで、LLM が補わない。

script は検索前後の graph/config/content digest を比べ、変化があれば `read_only.changed` を付けて失敗する。GitHub/Beads command、writer、render、sync の呼び出しは禁止。該当なしは `result: empty` (exit 0)、schema 不正・root 外 file_path・dangling dependency・必須キー欠落は `result: rejected` (exit 1、rows 0件) で診断を返す。

## ゴールシーク実行

### ゴール (Goal)

特定のissue/task/specification/architecture/documentをgraph_node_id/artifact_kind/project_id/domain/status/tagsで検索し、依存関係・close/tombstone状態をread-onlyで確認できる状態になっている

### 目的・背景 (Why)

特定ノードの検索・状態確認 (要件C11) を独立の読取り専用経路として提供しないと、状態確認のたびに sync/render 相当の重い処理を経由せざるを得ず、副作用のない検索操作が書込みを伴う操作と混同されるリスクがあるため

### 完了チェックリスト

- [ ] query は許可 filter field と明示 tag match mode だけを持つ
- [ ] `extract-graph-status.py` が exit0 で `validation.status=pass`、`missing_required_keys` と root 外 file_path と dangling dependency が0件である
- [ ] report の status/closed_at/depends_on/dependents/linkage が `extract-graph-status.py` の rows そのもので、graph snapshot と一致する
- [ ] 該当なしが空 result の成功として返る
- [ ] 実行前後の graph/config/content digest が同一で外部 write が0件である
- [ ] 分離 context の評価役が、report と graph 実状態の一致と実行前後の digest の不変を独立に照合して PASS を返した

通らない経路の checklist 項目 (例: 該当ありの検索での「該当なしが空 result の成功として返る」) は、`not_applicable` と理由を progress に記録し、完了の判定から外す。

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。内ループは各周回で完了チェックリストと inner criterion (`IN1`) を検証する。outer criterion (`OUT1` の live-trial、`OUT2` の受入テスト) と content-review は内ループの完了判定に含めず、内ループが完了した後の外ループで最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- `semantic_evaluator_started` に入ったら、未達の有無にかかわらず、少なくとも1回 `Agent` で分離 context の評価役を起動する。評価役には report、graph の path、実行前の graph/config/content digest を渡す。評価役は `extract-graph-status.py` の rows と graph snapshot から report の status/closed_at/depends_on/dependents/linkage が graph の実状態と一致するかを、また実行後の digest を測り直して実行前と同じかを、独立に照合して verdict と根拠を返す。評価役も read-only で、graph/config/content を書かない。main context の自己照合では代えない。verdict は progress に記録する。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-status-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。内ループは、`not_applicable` を除く全 checklist と inner criterion (`IN1`) が PASS のときだけ完了する。skill の完了は、そのうえで外ループの outer criterion (`OUT1`・`OUT2`) と content-review も PASS になったときとする。

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

- `criteria:IN1`: `extract-graph-status.py`の`rows`に必須キー欠落が0件(`missing_required_keys`が空)で、検索/状態表示がgraphの実状態と一致する。scriptは`validate-graph-schema.py`(C11)と同じ検証を中で通し、`validation.status=pass`のときだけ行を返す。
- `criteria:OUT1`: reportの`status/closed_at/依存関係`はgraphの実状態と一致する。
- `criteria:OUT2`: 実行前後のdigestを比較し、graph/content/GitHubの副作用0件を保証する。

## Gotchas

- filter 間は OR に緩めず、全て AND で適用する。複数 tag は指定された match mode に従う。
- node 本文から status を推測せず、`extract-graph-status.py` の rows にある `status/closed_at` をそのまま報告する。
- 該当なしは空 result の成功とし、schema 不正や dangling dependency と混同しない。
- writer、sync、render、GitHub/Beads command を呼び出さない。
