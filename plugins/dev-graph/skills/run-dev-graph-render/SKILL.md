---
name: run-dev-graph-render
description: dev-graph を静的 HTML に可視化したいとき、外部 CDN/npm なしの自己完結 SVG + inline JS 成果物を生成したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C05
kind: run
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--scope ID] [--output PATH]"
allowed-tools: [Read, Bash, AskUserQuestion, Skill, Agent]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/render-graph-html.py]
schema_refs: [../../schemas/graph-node.schema.json]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R3-render.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "可視化対象範囲と静的HTML出力先パスをヒアリングして確定する"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "SVGノード配置とHTML/CSSレイアウトの生成計画を組み立てる"
  - id: R3-render
    name: render
    prompt_required: true
    summary: "render-graph-html.py で静的HTML/CSS + SVG + インラインJSを生成しコミットまたはCI生成可能な成果物を返す"
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
      text: "render-graph-html.py の出力HTMLに外部script/link参照が0件でゼロ依存であることをスクリプト検証する"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "生成したHTML/CSSをブラウザで開いた際に追加ランタイム依存なくSVGグラフが表示され、featureごとの子task進捗X/Yがregistration receiptのapplied_count/expected_countと一致し、表示対象がreceiptのsource_digestに対応することを受入テストが確認する"
      verify_by: live-trial
---

# run-dev-graph-render

## Purpose & Output Contract

- 入力: C24/C11 検証済み graph/scope、repo 内 output path。
- 出力: SVG/CSS/JS を inline 化した単一 HTML と node/edge/feature-progress counts、input/output digest を持つ renderer receipt。
- 完了条件: 外部 runtime 参照0、ブラウザ上で SVG と feature X/Y が表示され、receipt の counts/digests が実体に一致する。

1. C24/C11 で caller graph と scope を検証する。
2. 出力は repo 内の指定 path（既定 `.dev-graph/render/index.html`）に限定する。
3. `render-graph-html.py` を呼び、SVG、CSS、JS を単一 HTML に inline 化する。外部 `script/link`, CDN, npm dependency は禁止。
4. feature node は `parent_feature` の task を X/Y で集約し、feature 間 edge と task 内 edge を混同せず表示する。
5. renderer receipt の node/edge/progress counts と input digest を照合して返す。

graph は read-only。HTML 以外の graph/content を変更しない。

## ゴールシーク実行

### ゴール (Goal)

タスクグラフ情報から追加ランタイム依存なしでブラウザ表示可能な SVG + インライン JS 可視化済み静的 HTML/CSS が生成された状態になっている

### 目的・背景 (Why)

グラフ情報を人間が俯瞰するにはゼロ依存の静的可視化が必要で、コミットまたは CI 生成可能な成果物にすることで導入先リポジトリ内で完結させるため。feature ノードは配下task (parent_feature参照) の完了進捗 (X/Y) を集約表示し、機能単位のオーケストレーション状況を俯瞰できるようにする (§8.5・epic投影を持たないlocal_only profileでも実行状況を可視化)

### 完了チェックリスト

- [ ] input graph/scope が schema PASS で output realpath が caller repo 内にある
- [ ] render model の node/edge/feature progress counts が input graph と一致する
- [ ] 生成 HTML の外部 script/link/CDN/npm reference が0件で SVG と inline JS が実在する
- [ ] renderer receipt の input/output digest と実ファイル digest が一致する
- [ ] ブラウザ live trial で追加 runtime なしに SVG と feature X/Y progress が表示される

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-render-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-render-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-render-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-render-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-render-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: output HTMLの外部script/link参照が0件でゼロ依存である。
- `criteria:OUT1`: 生成HTML/CSSをブラウザで開き、追加ランタイム依存なくSVGグラフとfeatureごとの子task進捗X/Yが表示され、registration receiptの`applied_count/expected_count`と`source_digest`が表示内容に一致する。

## Gotchas

- CDN、npm bundle、外部 `script/link` を単一 HTML に混入させない。
- feature progress は `parent_feature` の task 実数から導出し、手入力値を表示しない。
- browser 表示だけで PASS にせず、receipt count と input/output digest も照合する。
- render は read-only graph から生成し、graph/content 本体を変更しない。
