---
name: run-dev-graph-node
description: dev-graph artifact を正規 path へ atomic 追加・差分更新したいとき、system-dev-planner の exact 13 phase task package を all-or-none 登録したいときに使う。
version: 0.2.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C02
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "<add|update|register-package> [--repo-root PATH] [--input PATH] [--dry-run]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill, Agent]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/build-graph-node.py, ../../scripts/register-package.py]
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


# run-dev-graph-node

## Purpose & Output Contract

- 入力: C24 で containment 検証済みの artifact candidate、既存 graph snapshot、または exact-13 package。
- 出力: C02 単一 writer 経由で atomic 登録された typed node/package と revision/digest receipt。
- 完了条件: kind/path/frontmatter/dependency が schema と一致し、package は P01..P13 exact-set のときだけ applied count 13 となる。

全 graph/content write の単一 writer。通常 artifact は issue/task/specification/architecture/document、macro feature は C14 (`run-dev-graph-decompose`) が宣言した macro contract だけを `add` の `artifact_kind=feature` で `features/` に登録する。

## Classification and write

1. C24 resolver で全 read/write realpath の containment を検証する。
2. 内容から `artifact_kind/domain/project_id`、候補 path、confidence/reason/second candidate を preview する。confidence>=0.80 かつ margin>=0.15 は自動確定し、それ以外だけユーザー確認する。保存先は質問しない。
3. `template-contract.json` から kind template を選ぶ。architecture は subtype 全件、specification は API 変更時だけ api-contract overlay を合成する。
4. frontmatter/body/path と graph node を一時領域で構成し `validate-graph-schema.py` を通してから atomic replace する。更新は既存本文を全置換せず、変更 field だけを更新する。不足 section は writer が返す `readiness_fill[]` (`{item, via, key}`) の `via` と `key` をそのまま使って埋める (placeholder のままの見出しは `set_sections`、見出しが無い section は `append_sections`、API block が無ければ `add_api_contracts`、feature の projection は `macro_patch` の field (`key=purpose` など) か `node_patch.depends_on`)。placeholder のままとは、section の全行が template の雛形行か placeholder (`placeholder_tokens`。`<` は `<...>` の範囲を指す) だけの行であることを指し、`p95 < 300ms`・`Bearer <token>`・`未定だが 30 日を上限にする` のような本文は埋まっている扱いになる。`via=null` (手で消された subtype block や leaf) は writer に埋める経路が無いので停止して報告する。readiness の項目名 (`api-contract`・`<subtype>:<leaf>`・`api:<op>:<leaf>`) を見出しキーに渡すと `readiness_item_is_not_a_heading` で拒否される。物理削除は禁止。

`add`/`update` verb は手順 1-4 の実装本体 `../../scripts/build-graph-node.py` に委譲する (`add|update --repo-root <path> --input <repo 内 JSON> [--dry-run]`)。skill は R1/R2 の分類結果と section 本文を入力 JSON に整形するだけで、graph・content・receipt を Write/Edit や自作 script で直接書かない。writer は C24 解決、入力の repo 内 containment (相対 `--input` は repo root 基準)、`expected_graph_revision` の CAS、register-package と共有する fcntl lock、staging 上の `validate-graph-schema.py` 再検証、content→graph→immutable receipt の順の atomic commit と失敗時 rollback を一体で持つ。apply では R2 preview の `graph_revision_before` を `expected_graph_revision` (整数) に必ず渡す。省略は `missing_expected_graph_revision`、整数以外は `invalid_input`、preview 後の変更は `graph_revision_conflict` で止め、省略できるのは `--dry-run` だけである。書込み前検証は baseline 差分で判定し、変更した node は finding 0 を要求し、変更していない node の既存 finding は持ち越す。

- `add`: `artifacts[]` に `artifact_kind/slug/title/project_id/domain/tracker_binding/classification` と、kind に応じた `artifact_subtypes` (architecture は 1 件以上、specification は `api_contracts` があれば `api` を自動補完) と任意の `sections`・`subtype_sections`・`api_contracts`・`depends_on` を渡す。形は `classification={reason, candidates:[{artifact_kind, confidence}], decision: auto|user_confirmed}`、`api_contracts=[{operation, sections:{leaf 見出し: 本文}}]`、`subtype_sections={subtype: {leaf 見出し: 本文}}`。id は `<kind prefix>-<slug>`、path は kind の正規 root 固定で、保存先は入力に含めない。分類は閾値未達なら `decision=user_confirmed` が無い限り拒否する。C14 が宣言した architecture だけは `classification={reason, decision: c14_macro_contract}` (candidates 無し) で登録でき、同じ batch の feature の `architecture_refs` が参照していなければ `invalid_classification` になる。`sections` の追加キーは単一行・先頭 `#` 無し・` > ` 無し・120 字以内・secret 無しの見出しだけを受け付ける (`invalid_section_key`)。
- `update`: `updates[]` に `graph_node_id` と `set_sections` (見出し直下の本文だけ置換、`祖先 > 見出し` で曖昧さを解消。H1 より下のパスを全部書いたキーは完全一致を優先するので、修飾しない名前は同名の H2 を指す)・`append_sections` (末尾に H2 で追記、同名の H2 があれば `duplicate_section`)・`add_subtypes` (block は subtype の正規順の位置へ挿入)・`add_api_contracts`・`node_patch`・`macro_patch` (feature のみ) を渡す。id/path/kind/template と外部 authority の field は変更できず、非管理 section のバイト列と contract 外の frontmatter キーは保持する (`unmanaged_frontmatter_kept`)。writer が生成した section (`Subtype architecture`・`API契約`) は、本文が旧状態の生成文と一致するときだけ新状態で再生成し (`sections_regenerated`)、人手で編集済みなら `set_sections` の同時指定が無い限り `generated_section_diverged` で拒否する。feature の projection は update のたびに frontmatter から再投影するので、手で編集した本文も手で消した見出しも次の update で戻る (`sections_regenerated`。消えた見出しは required 順の位置へ挿入する)。`status`/`closed_at` 以外の内容変更は `evaluation_status=pass` を `stale` に戻す。
- `feature` は `add` に `macro={purpose, goal, scope_in[], scope_out[], acceptance[], architecture_refs[]}` を渡したときだけ登録し、classification は受け付けない (decision は `c14_macro_contract` 固定)。`architecture_refs` の先は architecture、`depends_on` の先は feature でなければ `invalid_macro_reference`。目的・到達状態・スコープ・受入・アーキテクチャ参照・機能間依存は macro の projection なので `sections`/`set_sections`/`append_sections` では書けず (`macro_section_is_projection`)、変更は `macro_patch`/`node_patch.depends_on` で行う。macro が無い feature は `feature_requires_c14_macro_contract`、`parent_feature/feature_package_id/phase_ref` は `register-package` へ回す。拒否時は `applied_count=0`・`write_count=0` を返す。
- `tracker_binding` は register-package と同じ規則で repo の tracker mode と照合する。`none` は常に可、`beads`/`github` は mode が同じか `both` のときだけ可 (`tracker_binding_not_allowed`)、`repo-config-default` は mode が beads/github/none ならその値に解決し、`both` では `tracker_binding_unresolved`。github に解決された binding は draft node では schema を満たせないため `github_binding_requires_confirmed_node` で拒否するので、github mode の repo では `none` で登録する。登録済み node を github binding へ切り替える writer は現時点で無い。

## Exact-13 package gate

`register-package` verb はこの gate の実装本体 `../../scripts/register-package.py` に委譲する (`register-package.py register --package <path> --graph <path> --output <path> --receipt <path> [--tracker-mode <mode>] [--config <path>]`、事前検査は `register-package.py preflight`)。tracker mode は `--config` (既定 `.dev-graph/config.json`、`--repo-root` 基準) の `execution_tracker.mode` を読み、build-graph-node と同じ値で binding を解決する。`--tracker-mode` は同じ値の明示だけを受け付け、config と食い違う値や、config にも flag にも mode が無い場合は exit 2 で拒否する。単一 writer は `register-package.py` が fcntl ロックと receipt の `os.link` 一回性で保証し、skill 側は入力整形と結果提示に留める。

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
- `rollback_incomplete` (exit 2、`write_count=null`) は一部 path が書かれたまま残った状態である。`findings[]` の各 path を `detail` (`restore sha256 …` または `remove created file`) どおり手で戻し、`validate-graph-schema.py` が通ってから再実行する。
- content commit 後・graph commit 前の crash で本文だけが残ると、再実行は `artifact_path_exists` で止まる。graph に node が無い孤児本文であることを確かめて退避してから再実行する。graph を過去 revision へ戻したときの `immutable_receipt_exists` は、既存 receipt を消さず graph を最新 revision へ進めてから書く。
