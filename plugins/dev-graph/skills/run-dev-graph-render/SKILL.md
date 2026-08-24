---
name: run-dev-graph-render
description: dev-graph を静的 HTML に可視化したいとき、外部 CDN/npm なしの自己完結 SVG + inline JS 成果物を生成したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C05
kind: run
effect: local-artifact
runtime_root_policy: host-skill-path
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--scope ID] [--registration-receipt PATH]... [--output PATH]"
allowed-tools: [Read, Bash, AskUserQuestion, Skill]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/render-graph-html.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/package-registration-receipt.schema.json]
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
      text: "render-graph-html.py の出力HTMLに外部script/link参照が0件でゼロ依存であることをスクリプト検証する"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "生成したHTMLをブラウザで開いた際に追加ランタイム依存なくSVGグラフとfeatureごとの子task実行進捗X/Y (done数/子task数) が表示され、YがC02 registration receiptのexpected_count=applied_countと一致し、子task exact node_ids/package/source lineageがreceiptのsource_digestに一致することを受入テストが確認する"
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


# run-dev-graph-render

## Purpose & Output Contract

- 入力: C24/C11 検証済み graph、任意のscope ID、scope内で子taskを持つfeatureごとのC02 registration receipt、repo内output path。
- 出力: SVG/CSS/JSをinline化した単一HTMLと、scope node set、node/edge-kind/feature-progress counts、C02 lineage照合、input/render-model/output digest、repo-relative path refsを持つrenderer receipt。
- 完了条件: 外部runtime参照0、ブラウザ上でSVG・edge種別・feature X/Yが表示され、receiptのcounts/digests/C02 lineageが実体に一致する。

1. C24/C11でcaller graphを検証し、`--scope` 指定時はscope node・そのfeature parent/子task・依存先の固定点closureだけを対象にする。
2. caller repo authorityを `--repo-root` でrendererへ渡し、graph/registration receipt/outputのrealpathをrepo内に限定する。repo外、symlinkを通るpath、fileが必要な位置のdirectoryは、HTMLへの最初の書込み前にfail-closed拒否する。
3. scope内で子taskを持つfeatureごとに、C02が保存した `package-registration-receipt.schema.json` 準拠receiptを1件ずつ `--registration-receipt` で渡す。rendererは`expected_count=applied_count=13`、exact `node_ids`/P01..P13/package、全子taskの `source_lineage.source_digest` をfail-closed照合する。
4. `render-graph-html.py` を呼び、SVG、CSS、JSを単一HTMLにinline化する。外部 `script/link`, CDN, npm dependencyは禁止。
5. featureのX/Yは`status=done`の子task数/子task総数から導出する。feature間・同一feature内task・その他edgeを別class/legend/countで表示する。
6. renderer receiptのscope/node/edge-kind/progress counts、C02 lineage、input/render-model/output digestを照合して返す。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/render-graph-html.py" \
  --repo-root "$DEV_GRAPH_ROOT" \
  --graph "$DEV_GRAPH_ROOT/.dev-graph/state/graph.json" \
  --out "$DEV_GRAPH_ROOT/.dev-graph/render/index.html" \
  --scope "$SCOPE" \
  --registration-receipt "$REGISTRATION_RECEIPT"
```

scopeを限定しない場合は `--scope "$SCOPE"` 行を外す。複数feature packageを含む場合は `--registration-receipt` をfeatureごとに繰り返す。子task 0件のfeatureにreceiptは渡さない。renderer receiptの`out`と`registration_evidence.*.receipt`はcaller repo相対pathで返し、環境固有の絶対pathを永続化しない。

graph は read-only。HTML 以外の graph/content を変更しない。

## ゴールシーク実行

### ゴール (Goal)

タスクグラフ情報から追加ランタイム依存なしでブラウザ表示可能な SVG + インライン JS 可視化済み静的 HTML/CSS が生成された状態になっている

### 目的・背景 (Why)

グラフ情報を人間が俯瞰するにはゼロ依存の静的可視化が必要で、コミットまたは CI 生成可能な成果物にすることで導入先リポジトリ内で完結させるため。feature ノードは配下task (parent_feature参照) の完了進捗 (X/Y) を集約表示し、機能単位のオーケストレーション状況を俯瞰できるようにする (§8.5・epic投影を持たないlocal_only profileでも実行状況を可視化)

### 完了チェックリスト

- [ ] input graph/scope/registration receipt/outputのrealpathがcaller repo内にあり、repo外・symlink通過・file位置のdirectoryがwrite 0で拒否される
- [ ] scope closure、render modelのnode/edge-kind/feature progress countsがinput graphと一致する
- [ ] 子taskを持つ各featureのC02 receiptが13-count/exact node set/P01..P13/package/source lineageで一致する
- [ ] 生成 HTML の外部 script/link/CDN/npm reference が0件で SVG と inline JS が実在する
- [ ] renderer receiptのinput/render-model/output digestと実ファイルdigestが一致し、path refsがすべてrepo-relativeである
- [ ] ブラウザ live trial で追加 runtime なしに SVG と feature X/Y progress が表示される

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: inline` / `max_loops: 5` を実行契約とする。固定手順は使わず、main context で未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode read` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-render-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-render-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、main context でその周回の処理を実行する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
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
- `criteria:OUT1`: 生成HTMLをブラウザで開き、追加ランタイム依存なくSVGグラフとfeatureごとのdone child/child countが表示され、Yがregistration receiptの`expected_count=applied_count`、child exact-set/package/lineageが`node_ids/source_digest`に一致する。

## Gotchas

- CDN、npm bundle、外部 `script/link` を単一 HTML に混入させない。
- feature progress は `parent_feature` の task 実数から導出し、手入力値を表示しない。
- C02 `applied_count` を実行完了数Xと解釈しない。これは登録件数であり、Xはgraph上のdone child数である。
- browser表示だけでPASSにせず、receipt count/node IDs/source lineageとinput/render-model/output digestも照合する。renderer receiptへ環境固有の絶対pathを保存しない。
- render は read-only graph から生成し、graph/content 本体を変更しない。
