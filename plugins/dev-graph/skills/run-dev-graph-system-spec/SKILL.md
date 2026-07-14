---
name: run-dev-graph-system-spec
description: system-spec-harness の正規フローで仕様を作りたいとき、確定した仕様・architecture を source lineage 付きで dev-graph に取り込みたいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C19
kind: run
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--resume]"
allowed-tools: [Read, Bash, Skill, Agent, AskUserQuestion]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py]
schema_refs: [../../schemas/graph-node.schema.json]
responsibility_refs:
  - prompts/R0-context.md
  - prompts/R1-preflight.md
  - prompts/R2-delegate.md
  - prompts/R3-import.md
responsibilities:
  - id: R0-context
    name: context
    prompt_required: true
    summary: "C24で呼出しrepoのsystem_spec rootを解決し、symlink元や別repoのsystem-specを読まないcontainmentを検証する"
  - id: R1-preflight
    name: preflight
    prompt_required: true
    summary: "system-spec-harness versionが>=0.1.0 <1.0.0でrequired 4 entry pointsを持つことを確認し、不一致/未導入ならfallbackせず診断付きfail-closedにする"
  - id: R2-delegate
    name: delegate
    prompt_required: true
    summary: "run-system-spec-elicit→必要時run-system-spec-doc-fetch→run-system-spec-compile→assign-system-spec-completeness-evaluatorを引用実行する"
  - id: R3-import
    name: import
    prompt_required: true
    summary: "確定system-spec章をC02経由で登録しsource_lineage(origin_kind/plugin/path/version/digest/imported_at)、confirmation=confirmed、evaluator evidenceを保持する"
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
      text: "system-spec-harnessのcoverage/source citation gateとdev-graph schema gateがすべてexit0になる"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "仕様書/architecture要求がsystem-spec-harness成果物をsource lineage付きで引用し、同等ヒアリング/compileロジックがdev-graph内に複製されていないことを受入テストが確認する"
      verify_by: live-trial
---

# run-dev-graph-system-spec

## Purpose & Output Contract

- 入力: C24 で caller repo 内に固定した `system-spec/`、system-spec-harness manifest/entry points、任意の resume state。
- 出力: confirmed specification/architecture node、C02 import report、version/digest/imported_at を含む source lineage。
- 完了条件: system-spec-harness の required 4 entry points、coverage/source-citation/evaluator gate が PASS し、dev-graph 内の同等生成ロジック複製が0である。

本 skill は仕様生成ロジックを持たない。system-spec-harness を起動し、確定成果物の検証と C02 取込だけを担う。

1. C24 で caller repo の `system-spec/` を解決し、plugin source/別 repo の content を拒否する。
2. `plugins/system-spec-harness/.claude-plugin/plugin.json` の name/version が `>=0.1.0 <1.0.0`、かつ `references/package-contract.json#entry_points.skills` が `run-system-spec-elicit`, `run-system-spec-doc-fetch`, `run-system-spec-compile`, `assign-system-spec-completeness-evaluator` を持つことを確認する。公式manifestへharness専用キーを混在させず、不在/不一致は fallback を実装せず停止する。
3. Skill 呼出しで elicit → 必要時 doc-fetch → compile → completeness evaluator を順に委譲する。
4. confirmed 章と evaluator PASS だけを C02 に渡し、`source_lineage={origin_kind,plugin,path,version,digest,imported_at}`, confirmation evidence, readiness を specification/architecture node に保存する。

出力は import report (`system-spec/index.md`, imported node ids, lineage, confirmation_status, readiness)。feature は `architecture_refs` で参照し、内容を複製しない。1 feature→13 task は system-dev-planner の責務であり本 skill は扱わない。

## ゴールシーク実行

### ゴール (Goal)

仕様書・アーキテクチャをplugins/system-spec-harness/の正規フローで構築し、出典・確定状態・上位目的traceを保ったままdev-graphのspecification/architectureノードへ取り込んだ状態になっている

### 目的・背景 (Why)

system-spec-harnessが既に持つヒアリング、カテゴリ×platform matrix、公式出典、確定章保護、独立完成度評価を複製せず引用し、dev-graphはグラフ登録とlineage維持だけを担うため。本skillが取り込むarchitecture/specificationノードはfeature.architecture_refsから参照されfeatureのアーキテクチャ文脈を成す (複製せずlineage参照のみ・MM-12)

### 完了チェックリスト

- [ ] system_spec content root が caller repo 内で repository_id/common-dir と一致する
- [ ] system-spec-harness が version `>=0.1.0 <1.0.0` と required 4 entry points を満たす
- [ ] elicit/条件付き doc-fetch/compile/evaluator が system-spec-harness Skill 経由だけで実行される
- [ ] coverage/source-citation/evaluator gate が全て PASS である
- [ ] C02 登録 node の source_lineage/confirmation/evaluator evidence/readiness が欠落0である
- [ ] dev-graph 内に同等 elicitation/compile logic の複製が0件である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: system-spec-harnessのcoverage/source citation gateとdev-graph schema gateが全てexit0である。
- `criteria:OUT1`: 確定成果物をsource lineage付きで引用し、同等のelicitation/compileロジックは複製0件、登録はC02経由だけにする。

## Gotchas

- system-spec-harness 不在や version/entry-point 不一致時に、簡易 fallback を dev-graph 内へ実装しない。
- plugin source 側や別 repo の `system-spec/` を読まず、C24 receipt の caller repo だけを content authority にする。
- evaluator PASS と confirmed の両方が揃わない章を C02 へ登録しない。
- feature に仕様本文を複製せず、`architecture_refs` と source lineage で参照する。
