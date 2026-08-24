---
name: run-dev-graph-node
description: dev-graph artifact を正規 path へ atomic 追加・差分更新したいとき、C14 macro intentのpreview/applyまたはsystem-dev-planner exact 13 packageのall-or-none登録が必要なときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C02
kind: run
effect: local-artifact
runtime_root_policy: host-skill-path
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "<add|update|preview-macro|apply-macro|register-package> [--repo-root PATH] [--input PATH] [--dry-run]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/register-package.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/macro-intent.schema.json, ../../schemas/macro-registration-receipt.schema.json, ../../schemas/package-registration-receipt.schema.json, ../../schemas/package-registration-evidence.schema.json]
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
    summary: "成果物内容からartifact_kind/domain/project_id候補、confidence、reason、正規root候補を推定する。物理pathを決めず保存先を質問しない"
  - id: R2-preview
    name: preview
    prompt_required: true
    summary: "分類previewを提示し、閾値未達時だけsemantic decisionを確認する。物理pathはC02 CLI receiptでのみ確定する"
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
    - id: OUT4
      loop_scope: outer
      text: "新規normal/macroの正規path占有とdurable normal/macroのsymlinkをstaging前に拒否し、dry-run/applyはgraph/content/receiptを変更せず、正常な再実行はwrite_count=0の冪等no-opになる"
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


# run-dev-graph-node

## Purpose & Output Contract

- 入力: C24 で containment 検証済みの artifact candidate、C14 macro intent、既存 graph snapshot、または exact-13 package。
- 出力: C02 単一 writer 経由で atomic 登録された typed node/macro/package と revision/digest receipt。
- 完了条件: kind/path/frontmatter/dependency が schema と一致し、macroはpreview digestとapply digestが一致し、package は P01..P13 exact-set のときだけ applied count 13 となる。

全 graph/content write の単一 writer。通常 artifact は issue/task/specification/architecture/document、macro feature は C14 由来のみを `features/` に登録する。

## Classification and write

1. C24 resolver で全 read/write realpath の containment を検証する。
2. 内容から `artifact_kind/domain/project_id`、正規 root 候補、confidence/reason/second candidate を preview する。confidence>=0.80 かつ margin>=0.15 は自動確定し、それ以外だけユーザー確認する。物理 path は決めず、保存先は質問しない。
3. `template-contract.json` から kind template を選ぶ。architecture は subtype 全件、specification は API 変更時だけ api-contract overlay を合成する。
4. R1/R2/R4 の意味判定だけを contained JSON plan に記録する。plan は `schema_version/observed_at/decisions[]` のみで、各 decision は `input_index/artifact_kind/artifact_subtypes/project_id/domain/owners/tags/priority/resource_scope/classification_confidence/classification_reason/classification_candidates/decision_source/tracker_binding/depends_on_titles/related_node_titles/architecture_ref_titles/rendered_body` を持つ。node ID、path、frontmatter、graphは plan に書かない。
5. 以下のメンテナンスされた C02 CLI を必ず dry-run → apply の順で呼ぶ。`$PLAN` は `$DEV_GRAPH_ROOT` 内、`$INPUT` は C24 検証済みとする。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/register-package.py" artifacts \
  --repo-root "$DEV_GRAPH_ROOT" --input "$INPUT" --plan "$PLAN" --dry-run
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/register-package.py" artifacts \
  --repo-root "$DEV_GRAPH_ROOT" --input "$INPUT" --plan "$PLAN"
```

C02 CLI が classification threshold、C14 feature 拒否、正規 root/ID/path/frontmatter、template section、semantic title reference、tracker binding、staging C11、lock、atomic replace を一括所有する。executor は `c02-write.py` 等の一時 driver を作らず、graph/content を直接 Write/Edit/copy しない。

新規通常artifactの正規pathは未占有であることをstaging前に検査する。graph未登録の通常file、directory、broken/in-repository/root外向きsymlinkはすべてdry-run/apply共にfail-closedとし、既存durable nodeの更新は正規pathの通常fileだけを許可する。

既存 artifact の入力 digest が変わった場合は、全文置換ではなく contained patch plan を渡す。patch plan は `{"patches":[{"input_index":0,"append_sections":[{"heading":"## ...","body":"..."}]}]}` の形だけを許し、`--patches "$PATCHES"` を dry-run/apply の両方に付ける。C02 は既存 ID/path/body を保持して section を追記し、同一 digest の再実行を no-op にする。

履歴から取り込むローカル専用 artifact を初回から closed として記録する場合だけ、contained initial-state plan `{"schema_version":"1.0.0","states":[{"input_index":1,"status":"closed","closed_at":"<RFC3339>"}]}` を作り、dry-run/apply の両方に `--initial-state "$INITIAL_STATE"` を付ける。これは新規 artifact、`status=closed`、`tracker_binding=none` に限定する。通常作成は従来どおり draft 固定とし、既存 node の lifecycle 更新や外部 tracker close には流用しない。

## Macro graph gate

C14が作るのは `../../schemas/macro-intent.schema.json` 準拠のintentだけである。featureは `graph_node_id/title/domain/purpose/goal/scope_in/scope_out/acceptance/depends_on/resource_scope` を持ち、`architecture_refs` は渡さない。C02がtop-level `architecture.graph_node_id` から全featureへ一意に導出する。

同じintentを次の順で実行する。applyは直前previewの `candidate_graph_digest` を必須照合し、graphが変化したstale previewを拒否する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/register-package.py" preview-macro \
  --repo-root "$DEV_GRAPH_ROOT" --graph .dev-graph/state/graph.json \
  --request-json "$MACRO_INTENT_JSON" --dry-run
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/register-package.py" apply-macro \
  --repo-root "$DEV_GRAPH_ROOT" --graph .dev-graph/state/graph.json \
  --request-json "$MACRO_INTENT_JSON" \
  --expected-candidate-digest "$PREVIEW_DIGEST" --receipt "$MACRO_RECEIPT"
```

preview/applyは同じnormalize・schema/DAG・candidate digest関数を共有する。C02だけがprivate temporary stagingでcanonical artifactとcandidate graphを組み立て、`validation.authority=C11/validate-graph-schema.py` としてvalidatorを実行する。callerはcandidateをscratch/cacheへcopyしない。applyはsingle-writer lock内でarchitecture/feature本文、graph、immutable receiptを一括反映し、どのwriteが失敗してもgraphと本文を復元する。graph未登録の同名artifact pathはpreviewでfail-closedとし上書きしない。既登録macroの冪等再実行もdurable pathがsymlinkでない通常fileであることを再検証する。同じintent由来nodeが欠落・改ざんされていなければ、後続graph追加後も既存receiptを `idempotent=true/write_count=0` として認識する。

## Exact-13 package gate

`register-package` verb はこの gate の実装本体 `../../scripts/register-package.py` に委譲する (`register-package --package <path> --graph <path> --output <path> --receipt <path>`、事前検査は `preflight`)。単一 writer は `register-package.py` が fcntl ロックと receipt の `os.link` 一回性で保証し、skill 側は入力整形と結果提示に留める。

system-dev-planner の package は P01..P13 exact set、13 node、共通 `parent_feature`/`feature_package_id`、同一 package 内だけの DAG、source digest、tracker binding を commit 前に検証する。12/14件、phase 重複/欠落、mixed parent/package、cross-feature edge は `applied_count=0` で拒否する。成功 receipt は `status/source_digest/expected_count=13/applied_count=13/graph_revision/registered_node_ids/committed_at` を持ち immutable に保存する (schema: `../../schemas/package-registration-receipt.schema.json`)。

旧immutable receiptに`c11_readiness_digest`が無い既登録packageを同じ`register` commandで再実行した場合だけ、graph/receiptを変更せずcurrent feature-scoped C11とimplementation-readiness sourceを再検証する。PASS時はreceipt SHA・current graph SHA/revision・C11/source/package/node digestを束縛したcontent-addressed supplemental evidenceをatomic発行する (schema: `../../schemas/package-registration-evidence.schema.json`)。`--dry-run`は証拠も書かず、missing/mismatch/partialは発行0件でFAILする。現行receiptはreceipt内digestを正本として継続する。

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
- [ ] 通常 artifact の frontmatter/body/path/template metadata が schema と一致し、未登録path占有とdurable pathのsymlinkをwrite前に拒否する
- [ ] 通常 artifact の dry-run/apply が正規 `register-package.py artifacts` のreceiptを持ち、一時 writer driver が0件である
- [ ] C14 macro intentのpreview/applyが同じcandidate digestとC11 PASSを持ち、失敗時partial node/artifactが0件である
- [ ] package は P01..P13 exact 13、共通 parent/package、内部 DAG を満たし、違反時 applied_count が0である
- [ ] 成功 receipt の graph_revision と registered_node_ids が commit 後 graph と一致する

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: inline` / `max_loops: 5` を実行契約とする。固定手順は使わず、main context で未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、main context でその周回の処理を実行する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
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
- `criteria:OUT4`: normal/macroの新規path占有とdurable symlinkはwrite 0で拒否し、正規fileの再実行だけがwrite_count=0の冪等no-opになる。

## Gotchas

- graph/content を直接書かず、preview と apply のどちらも C02 単一 writer を通す。
- 意味判定 plan をスクリプトに変換しない。必ずプラグイン内の `register-package.py artifacts` を呼び、`owner=C02/run-dev-graph-node` / `operation=write_artifacts` / `temporary_driver=false` をreceiptで確認する。
- feature は C14 の macro contract から受け取り、通常 artifact routing で新規生成しない。
- P01..P13 の欠落、重複、混在、cross-feature edge のいずれかがあれば部分登録しない。
- execution context の repository/worktree identity 不一致を上書きで吸収しない。
