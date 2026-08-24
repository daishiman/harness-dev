---
name: run-dev-graph-init
description: dev-graph を呼出し元 repository/worktree 内へ冪等初期化したいとき、検証済みrepo-local configの6 content rootとstate/templates/hook fallbackを安全に用意したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C01
kind: run
effect: local-artifact
runtime_root_policy: host-skill-path
prefix: run
hierarchy: L1
user-invocable: true
disable-model-invocation: false
argument-hint: "[--repo-root PATH] [--hook-source plugin|project-fallback] [--dry-run] [--rollback-project-hooks]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill]
script_refs: [scripts/build-dev-graph.py, ../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/repo-config.schema.json]
reference_refs: [../../schemas/repo-config.schema.json, ../../templates/template-contract.json, ../../references/claude-code-hooks-contract.md]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R3-init.md
  - prompts/R4-template.md
  - prompts/R5-hooks.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "C24でcaller repository rootとrepo-local configを解決し、検証済みeffective configを単一正本としてsymlink sourceとcontent authorityを分離する。保存先は質問しない"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "欠落時は6 content rootの既定値を組み立て、既存時は検証済みeffective configを保持し、routing/GitHub/worktree/hook policyと実行後readiness gateをdry-run receiptへ決定論的に出力する"
  - id: R3-init
    name: init
    prompt_required: true
    summary: "effective configから解決したrepo内pathだけにcontent/state/cache/locks/graph/receiptを生成し、GitHub設定はtoken/node IDを保存しない"
  - id: R4-template
    name: template
    prompt_required: true
    summary: "共通/5kind/architecture 5 subtype/API/system phase/system task overlay/template contractを`.dev-graph/templates/`へ冪等scaffoldし、利用者編集済み版は上書きしない"
  - id: R5-hooks
    name: hooks
    prompt_required: true
    summary: "C25のplugin hookを共有既定とする。project fallbackはplain-symlink導入時だけ許可し、effective plugin hookが見えれば拒否する。C24で検証した`.claude/dev-graph-plugin`からC10/C25全eventを既存settingsへpreview付きdeep-mergeし、override/二重登録を診断してrollback manifestを残す"
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
      text: "validate-graph-schema.py で初期グラフストアを送信前検証しスキーマの必須キー欠落が 0 件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "初期化後にeffective configの6 content rootとrouting policyとグラフストアが揃い、二回目initで構造が変化しないことを受入テストが確認する"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "初期化後に `.dev-graph/templates/` へ全kind templateがscaffoldされ、二回目initでも利用者編集を上書きしない"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "initは同一共有scriptをrepo A/Bで実行して各effective configが指すcontent/graph/receiptだけを読み書きし、cross-read/write 0件、absolute stored path 0件、project-root不一致とbroken content linkを診断付きfail-closedにする。起動前のharness link切断はinitの実行可能境界外とし、host正本`scripts/build-claude-symlinks.py --check`の証跡と分離する"
      verify_by: test
    - id: OUT4
      loop_scope: outer
      text: "GitHub設定雛形がenabled=falseで冪等生成され、owner/project number/field mappingを保持する一方、token/project/item/field node IDを正本configへ保存しない"
      verify_by: test
    - id: OUT5
      loop_scope: outer
      text: "plugin hookを既定にしproject fallback選択時だけ既存.claude/settings.jsonへ非破壊mergeされ、二重登録0件、既存key/hash変更0件、managed/disabled診断とrollbackが再現できる"
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


# run-dev-graph-init

## Purpose & Output Contract

- 入力: C24 の caller-repository context receipt、repo-local config、hook source policy。
- 出力: effective configが指す6 content root、config/state/cache/locks/templates、graph、およびgraphと同じstate directoryの init receipt。config欠落時だけ`issues/tasks/specs/architecture/features/docs`を既定値とする。
- 完了条件: repo config schema、C11 graph、template readiness、goal-seek anchorがすべてPASSし、2回目の init が`planned_changes=[]`、利用者編集済み成果物の上書0である。

呼出し元 repository を content authority、Runtime root contractで解決済みのabsolute `PLUGIN_ROOT`（Claude Codeでは`CLAUDE_PLUGIN_ROOT`由来）をread-only code/template authorityとして分離する。別 repository、root 外 realpath、broken content symlink、絶対 path の永続化は fail-closed。

## Input / output

- 入力: `--repo-root` または信頼済み project context、hook source。保存先や node ID は質問しない。
- 出力: effective configの`content_roots` / `local_state`から解決したdirectory/graph、`.dev-graph/{config.json,templates/}`、graphと同じstate directoryの初期化 receipt。
- GitHub は `enabled:false` で初期化し、owner/project number/field name のみ保存する。token と GitHub node ID は保存しない。

## Execution contract

config/scaffold/receiptや一時runnerをLLMが手書きしてはならない。選択したhook sourceで次の正本を1回実行し、同じcommandをもう1回実行する。1回目の`readiness.repo_config/graph/templates/goal_seek/claude_hooks`が全PASS、2回目の`planned_changes=[]`、`write_count=0`、`idempotent=true`になる場合だけ完了する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-dev-graph-init/scripts/build-dev-graph.py" \
  --repo-root "$DEV_GRAPH_ROOT" \
  --hook-source plugin  # plain-symlink fallbackだけ project-fallback を明示
```

正本scriptが次を一つのfail-closed transactionとして担う。

1. C24 `resolve-repo-context.py --mode write` でexplicit caller repositoryのgit/common-dir authorityを検証する。
2. 既存`.dev-graph/config.json`があればschema/repository identity/hook source/path containmentを書込み前に検証してeffective configとし、なければ6 rootを含む既定configを使う。directory/graph/C11/receipt/readinessはすべてこのeffective configから導出する。
3. plugin `templates/` 全件を欠落時だけコピーし、利用者編集済み版は上書きせず`migration_preview`へ分離する。
4. `repo-config.schema.json`でconfigを、`validate-graph-schema.py`でgraphを検証し、contract列挙templateの欠落を0にする。
5. goal-spec/progress/intermediateを同じoriginal goal/hashで作成・再読込検証し、C01 init receiptは全readiness PASS後だけ生成する。

`project-fallback` は同じ正本scriptのC25経路で`--dry-run` preview後にだけ適用する。effective plugin hook、`disableAllHooks`、`allowManagedHooksOnly`、競合/重複hookを検出したらFAILし、既存settings値を保持した識別子付きdeep merge、repo-relative symlink、rollback manifestを生成する。rollbackは同じ引数に`--rollback-project-hooks`を加えて実行する。

Receipt は `repository_id`, repo-relative roots, created/preserved/migration_preview, hook_source, `gh_cli_auth`, hook_result, schema_resultを含む。schema identifierはplugin-relativeで保存し、認証tokenや`gh auth status`のstdout/stderrは記録しない。新規だけでなく既存receiptも再帰走査し、POSIX/Windows絶対pathが1件でも残る場合や検証失敗時はfail-closedとし、部分成功を成功扱いしない。

Dry-run receiptは検証済み`config_result.effective_config`とそのdigest、routing/GitHub/execution tracker/worktree/hookの`policy_preview`、apply後に実測する`readiness_plan`を含む。未実行のgraph/template/goal/hookをPASSと予測しない。Apply receiptは同じeffective config snapshot/digestと実測済みschema/readinessを記録する。

## ゴールシーク実行

### ゴール (Goal)

symlinkで配布された任意の呼出し元repository/worktreeを解決し、そのrepo内だけに6 content root (issues/tasks/specs/architecture/features/docs)、repo-local config/template/stateと選択式Claude hook配線を冪等初期化できる状態になっている

### 目的・背景 (Why)

成果物種別を混在させず一元管理するには、単一グラフストアと正規ディレクトリ構造の双方が必要なため。物理配置はartifact_kind、横断分類はmetadataとし、小規模時はflat、大規模時だけ段階分割するhybrid policyを初期化時に敷く。初期化レポートにはgh CLI認証状態も含める。加えて、artifact kind別テンプレート正本 (`templates/template-contract.json` + kind別/subtype別Markdown雛形) はplugin同梱の静的資産であり、init実行時に導入先 `.dev-graph/templates/` へ冪等コピーする (要件C18のscaffold責務)

### 完了チェックリスト

- [ ] `resolve-repo-context.py` receipt の repository_id/common-dir/content root が caller repo と一致する
- [ ] effective configの`content_roots` / `local_state`が指すdirectory/graphと `.dev-graph/{config.json,templates}` が実在する
- [ ] `template-contract.json` 列挙資産が欠落0で、利用者編集済み template の digest が不変である
- [ ] effective hook は plugin または許可済み fallback の一経路だけで、既存 settings key/hash の変更が0件である
- [ ] repo config schemaと`validate-graph-schema.py`がexit0で、goal-spec/progress/intermediateのoriginal goal/hashが一致する
- [ ] 同じ正本commandの二回目が`planned_changes=[]`、`write_count=0`、`idempotent=true`である

### ゴールシークループ

frontmatterの `goal_seek.activation_state: semantic_evaluator_started` を先に確認する。main contextが最小init artifactを作成・guard・提示し、利用者がlight/standard/detailedを選んだ場合だけ `fork: inline` / `max_loops: 5` とfeedback反復を有効化する。accept-as-isではloopを0回のままhandoff完了する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-init-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-init-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、main context でその周回の処理を実行する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-init-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-init-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-init-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: `validate-graph-schema.py` の初期 graph 検証で必須キー欠落が0件である。
- `criteria:OUT1`: effective configの6 content rootと graph store が揃い、二回目initの変更が0件である。
- `criteria:OUT2`: 全 kind template を `.dev-graph/templates/` へ配置し、二回目initでも利用者編集を上書きしない。
- `criteria:OUT3`: initの受持範囲でrepo A/Bのcross-read/write 0件、absolute stored path 0件、project-root不一致/broken content symlink拒否を確認する。init自身を起動できないbroken harness linkはhost launcher責務であり、正本host evidenceは`scripts/build-claude-symlinks.py --check`とそのhost testに分離する。
- `criteria:OUT4`: GitHub template は `enabled:false` で生成し、tokenまたはproject/item/field node IDを保存しない。
- `criteria:OUT5`: `project-fallback` の非破壊mergeは二重登録0件、既存key/hash変更0件で、managed/disabled診断とrollbackを再現できる。

## Gotchas

- symlink 元の plugin directory を content authority にせず、C24 receipt の caller repo だけを書込み先にする。
- token、GitHub node ID、環境固有の絶対 path を repo config へ永続化しない。
- 利用者が編集した template は上書きせず、migration preview に差分を残す。
- effective plugin hook がある状態で project fallback を追加しない。
- scratch runnerや手書きconfig/receiptで正本initializerを置き換えず、graph-only PASSをfull init readinessと呼ばない。
