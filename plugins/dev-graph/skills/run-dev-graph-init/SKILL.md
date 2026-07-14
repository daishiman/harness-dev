---
name: run-dev-graph-init
description: dev-graph を呼出し元 repository/worktree 内へ冪等初期化したいとき、6 content root と repo-local config/state/templates/hook fallback を安全に用意したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C01
kind: run
prefix: run
hierarchy: L1
user-invocable: true
disable-model-invocation: false
argument-hint: "[--repo-root PATH] [--hook-source plugin|project-fallback] [--dry-run]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill, Agent]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py]
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
    summary: "C24でcaller repository rootとrepo-local configを解決し、symlink sourceとcontent authorityを分離する。保存先は質問しない"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "6 content root (issues/tasks/specs/architecture/features/docs)、frontmatter、routing policyに加え、GitHub enabled=false既定のissue repository/複数Project/field mapping/auto-add設定雛形を組み立てる。保存先やnode IDをユーザーへ求めない"
  - id: R3-init
    name: init
    prompt_required: true
    summary: "resolved repo内へrepository_idを埋めたconfig/content/state/cache/locksを生成し、GitHub設定はowner/project number/field nameだけをrepo-local保存、token/node IDは保存しない"
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
      text: "validate-graph-schema.py で初期グラフストアを送信前検証しスキーマの必須キー欠落が 0 件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "初期化後にissues/tasks/specs/architecture/features/docsの6 rootとrouting policyとグラフストアが揃い、二回目initで構造が変化しないことを受入テストが確認する"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "初期化後に `.dev-graph/templates/` へ全kind templateがscaffoldされ、二回目initでも利用者編集を上書きしない"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "同一symlink harnessをrepo A/Bから実行して各repo固有config/docs/stateだけを読み書きし、cross-read/write 0件、absolute stored path 0件、project-root不一致とbroken content linkは診断付きfail-closedになり、harness link切断はhost launcher preflightが起動前検出する"
      verify_by: test
    - id: OUT4
      loop_scope: outer
      text: "GitHub設定雛形がenabled=falseで冪等生成され、owner/project number/field mappingを保持する一方、token/project/item/field node IDを正本configへ保存しない"
      verify_by: test
    - id: OUT5
      loop_scope: outer
      text: "plugin hookを既定にしproject fallback選択時だけ既存.claude/settings.jsonへ非破壊mergeされ、二重登録0件、既存key/hash変更0件、managed/disabled診断とrollbackが再現できる"
      verify_by: test
---

# run-dev-graph-init

## Purpose & Output Contract

- 入力: C24 の caller-repository context receipt、repo-local config、hook source policy。
- 出力: `issues/tasks/specs/architecture/features/docs` の6 content root、`.dev-graph/` 配下の config/state/cache/locks/templates、および init receipt。
- 完了条件: 全 path が resolved repo 内で C11 gate が PASS し、2回目の init が変更0、利用者編集済み成果物の上書0である。

呼出し元 repository を content authority、`$CLAUDE_PLUGIN_ROOT` を read-only code/template authority として分離する。別 repository、root 外 realpath、broken content symlink、絶対 path の永続化は fail-closed。

## Input / output

- 入力: `--repo-root` または信頼済み project context、hook source。保存先や node ID は質問しない。
- 出力: `issues/ tasks/ specs/ architecture/ features/ docs/`、`.dev-graph/{config.json,graph.json,state/,cache/,locks/,templates/}` と初期化 receipt。
- GitHub は `enabled:false` で初期化し、owner/project number/field name のみ保存する。token と GitHub node ID は保存しない。

## Execution contract

1. `resolve-repo-context.py --mode write` を実行し、resolved root と host project root の realpath 一致を確認する。
2. 既存ファイルを列挙して preview。6 root と repo-local directory は欠落時だけ作る。
3. plugin の `templates/` 全件を `.dev-graph/templates/` へ欠落時だけコピーする。利用者編集済みファイルは上書きせず `migration_preview` へ記録する。
4. plugin hook を既定とする。`project-fallback` は plain-symlink 導入かつ effective plugin hook 不在時だけ許可し、既存 `.claude/settings.json` を deep-merge preview 後に更新して rollback manifest を残す。二重登録は拒否する。
5. `validate-graph-schema.py` で config/graph/template readiness を検証する。二回目実行の planned changes が 0 でなければ完了しない。

Receipt は `repository_id`, repo-relative roots, created/preserved/migration_preview, hook_source, schema_result を含む。検証失敗時は部分成功を成功扱いしない。

## ゴールシーク実行

### ゴール (Goal)

symlinkで配布された任意の呼出し元repository/worktreeを解決し、そのrepo内だけに6 content root (issues/tasks/specs/architecture/features/docs)、repo-local config/template/stateと選択式Claude hook配線を冪等初期化できる状態になっている

### 目的・背景 (Why)

成果物種別を混在させず一元管理するには、単一グラフストアと正規ディレクトリ構造の双方が必要なため。物理配置はartifact_kind、横断分類はmetadataとし、小規模時はflat、大規模時だけ段階分割するhybrid policyを初期化時に敷く。初期化レポートにはgh CLI認証状態も含める。加えて、artifact kind別テンプレート正本 (`templates/template-contract.json` + kind別/subtype別Markdown雛形) はplugin同梱の静的資産であり、init実行時に導入先 `.dev-graph/templates/` へ冪等コピーする (要件C18のscaffold責務)

### 完了チェックリスト

- [ ] `resolve-repo-context.py` receipt の repository_id/common-dir/content root が caller repo と一致する
- [ ] `issues/tasks/specs/architecture/features/docs` と `.dev-graph/{config.json,graph.json,state,cache,locks}` が実在する
- [ ] `template-contract.json` 列挙資産が欠落0で、利用者編集済み template の digest が不変である
- [ ] effective hook は plugin または許可済み fallback の一経路だけで、既存 settings key/hash の変更が0件である
- [ ] `validate-graph-schema.py` が exit0 で、同じ入力の二回目 init の planned changes が0件である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-init-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-init-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
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
- `criteria:OUT1`: `issues/tasks/specs/architecture/features/docs` と graph store が揃い、二回目initの変更が0件である。
- `criteria:OUT2`: 全 kind template を `.dev-graph/templates/` へ配置し、二回目initでも利用者編集を上書きしない。
- `criteria:OUT3`: repo A/B の cross-read/write 0件、absolute stored path 0件を確認し、project-root不一致、broken content symlink、harness link切断をfail-closedにする。
- `criteria:OUT4`: GitHub template は `enabled:false` で生成し、tokenまたはproject/item/field node IDを保存しない。
- `criteria:OUT5`: `project-fallback` の非破壊mergeは二重登録0件、既存key/hash変更0件で、managed/disabled診断とrollbackを再現できる。

## Gotchas

- symlink 元の plugin directory を content authority にせず、C24 receipt の caller repo だけを書込み先にする。
- token、GitHub node ID、環境固有の絶対 path を repo config へ永続化しない。
- 利用者が編集した template は上書きせず、migration preview に差分を残す。
- effective plugin hook がある状態で project fallback を追加しない。
