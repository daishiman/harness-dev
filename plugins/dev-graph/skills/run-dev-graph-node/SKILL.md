---
name: run-dev-graph-node
description: dev-graph artifact を正規 path へ atomic 追加・差分更新したいとき、system-dev-planner の exact 13 phase task package を all-or-none 登録したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C02
kind: run
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "<add|update|register-package> [--repo-root PATH] [--input PATH] [--dry-run]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill, Agent]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/register-package.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/package-registration-receipt.schema.json]
reference_refs: [../../schemas/graph-node.schema.json, ../../templates/template-contract.json, ../../../system-dev-planner/references/feature-execution-package-contract.md]
responsibility_refs:
  - prompts/R0-context.md
  - prompts/R1-classify.md
  - prompts/R2-preview.md
  - prompts/R3-write.md
  - prompts/R4-apply-template.md
responsibilities:
  - id: R0-context
    name: context
    prompt_required: true
    summary: "C24でcaller repo/config/content rootsを解決し、全read/write realpathがroot内であることをpreflightする"
  - id: R1-classify
    name: classify
    prompt_required: true
    summary: "成果物内容からartifact_kind/domain/project_id候補、confidence、reason、候補pathを推定する。保存先を質問しない"
  - id: R2-preview
    name: preview
    prompt_required: true
    summary: "分類previewを提示し、閾値未達時だけ確認して正規pathを確定する"
  - id: R3-write
    name: write
    prompt_required: true
    summary: "artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する"
  - id: R4-apply-template
    name: apply-template
    prompt_required: true
    summary: "確定したartifact_kind (architectureはsubtype複数選択、specificationはAPI変更有無) からtemplates/template-contract.jsonが示す本文骨格を適用し、template_id/template_version/artifact_subtypesをfrontmatterへ書き込む。既存文書は全書換せず不足セクションのみ差分追記する (要件C18/C19)"
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
      text: "validate-graph-schema.py でノード書込み前検証しスキーマの必須キー欠落が 0 件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "通常5 artifact混在入力は自動routingされ、featureはC14 macro contractだけからfeatures/へ入り、連続更新後もfrontmatter/path整合性が維持される"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "新規ノード作成時にartifact_kind (architectureは選択したsubtype全て、specificationはAPI変更有無に応じたapi-contract合成) に対応する本文必須セクション見出しが欠落0件で適用されることを受入テストが確認する (要件C18/C19)"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "12/14 task、phase欠落/重複、mixed parent/package、cross-feature edgeを注入するとapplied_count=0。正常時はexpected_count=applied_count=13、P01..P13/node exact-set、graph_revision付きreceiptとなる"
      verify_by: test
---

# run-dev-graph-node

## Purpose & Output Contract

- 入力: C24 で containment 検証済みの artifact candidate、既存 graph snapshot、または exact-13 package。
- 出力: C02 単一 writer 経由で atomic 登録された typed node/package と revision/digest receipt。
- 完了条件: kind/path/frontmatter/dependency が schema と一致し、package は P01..P13 exact-set のときだけ applied count 13 となる。

全 graph/content write の単一 writer。通常 artifact は issue/task/specification/architecture/document、macro feature は C14 由来のみを `features/` に登録する。

## Classification and write

1. C24 resolver で全 read/write realpath の containment を検証する。
2. 内容から `artifact_kind/domain/project_id`、候補 path、confidence/reason/second candidate を preview する。confidence>=0.80 かつ margin>=0.15 は自動確定し、それ以外だけユーザー確認する。保存先は質問しない。
3. `template-contract.json` から kind template を選ぶ。architecture は subtype 全件、specification は API 変更時だけ api-contract overlay を合成する。
4. frontmatter/body/path と graph node を一時領域で構成し `validate-graph-schema.py` を通してから atomic replace する。更新は既存本文を全置換せず不足 section/変更 field だけを更新する。物理削除は禁止。

## Exact-13 package gate

`register-package` verb はこの gate の実装本体 `../../scripts/register-package.py` に委譲する (`register-package --package <path> --graph <path> --output <path> --receipt <path>`、事前検査は `preflight`)。単一 writer は `register-package.py` が fcntl ロックと receipt の `os.link` 一回性で保証し、skill 側は入力整形と結果提示に留める。

system-dev-planner の package は P01..P13 exact set、13 node、共通 `parent_feature`/`feature_package_id`、同一 package 内だけの DAG、source digest、tracker binding を commit 前に検証する。12/14件、phase 重複/欠落、mixed parent/package、cross-feature edge は `applied_count=0` で拒否する。成功 receipt は `status/source_digest/expected_count=13/applied_count=13/graph_revision/registered_node_ids/committed_at` を持ち immutable に保存する (schema: `../../schemas/package-registration-receipt.schema.json`)。

`--dry-run` は local/external write 0。失敗時に一部 node を残さない。

## Execution-context consumer

C27 の claim saga は `register-package.py execution-context --graph <path> --graph-node-id <id> --context-json <json>` を内部 consumer として必ず実行する。この入口も C02 単一 writer の lock・graph-node schema 検証・atomic replace を共有し、同一 `worktree_id` の context を冪等置換する。C27 が receipt を自作・持込みせず、consumer が返す `owner=C02/run-dev-graph-node`、`operation=project_execution_context`、`status=applied`、node/worktree identity 一致を確認してから claim を確定する。

## ゴールシーク実行

### ゴール (Goal)

通常5 artifactを自動分類し、C14由来featureとsystem-dev-planner由来exact 13 phase tasksをそれぞれの専用契約で正規pathへatomic追加・更新し、graph/frontmatter/body/path/package整合を保つ

### 目的・背景 (Why)

成果物を単一graphで保持する専用writer。feature由来task batchはsystem-dev-plannerのfeature package契約に従い、P01..P13 exact 13 node、共通parent_feature/feature_package_id、同一package内dependencyを事前検証してall-or-none commitする。tracker bindingも同じtransactionで解決する

### 完了チェックリスト

- [ ] 全 read/write realpath が resolved repo root 内で repository_id が一致する
- [ ] classification decision が閾値による自動確定または明示 user confirmation の証跡を持つ
- [ ] 通常 artifact の frontmatter/body/path/template metadata が schema と一致する
- [ ] package は P01..P13 exact 13、共通 parent/package、内部 DAG を満たし、違反時 applied_count が0である
- [ ] 成功 receipt の graph_revision と registered_node_ids が commit 後 graph と一致する

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: `validate-graph-schema.py` の書込み前検証で必須キー欠落が0件である。
- `criteria:OUT1`: 通常5 artifactをroutingし、featureはC14 macro contractからのみ登録し、連続更新後もfrontmatter/path整合を保つ。
- `criteria:OUT2`: architecture subtypeとspecificationの`api-contract`条件を含むkind別必須セクションを欠落0件で適用する。
- `criteria:OUT3`: 12/14 task、phase欠落/重複、mixed package、cross-feature edgeは`applied_count=0`、正常時は`expected_count=applied_count=13`、P01..P13/node exact-set、`graph_revision`付きreceiptになる。

## Gotchas

- graph/content を直接書かず、preview と apply のどちらも C02 単一 writer を通す。
- feature は C14 の macro contract から受け取り、通常 artifact routing で新規生成しない。
- P01..P13 の欠落、重複、混在、cross-feature edge のいずれかがあれば部分登録しない。
- execution context の repository/worktree identity 不一致を上書きで吸収しない。
