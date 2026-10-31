---
name: run-dev-graph-system-spec
description: system-spec-harness の正規フローで仕様を作りたいとき、確定した仕様・architecture を source lineage 付きで dev-graph に取り込みたいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C19
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--resume]"
allowed-tools: [Read, Bash, Skill, Agent, AskUserQuestion]
script_refs: [scripts/prepare-evaluation.py, ../../scripts/_common.py, ../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/validate-source-lineage.py]
schema_refs: [../../schemas/graph-node.schema.json]
reference_refs: [../../references/prompt-common-layers.md]
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
      text: "system-spec-harnessのcoverage/source citation gateとdev-graph schema gateがすべてexit0になる"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "仕様書/architecture要求がsystem-spec-harness成果物をsource lineage付きで引用し、同等ヒアリング/compileロジックがdev-graph内に複製されていないことを受入テストが確認する"
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

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-dev-graph-system-spec

## Purpose & Output Contract

- 入力: C24 で caller repo 内に固定した `system-spec/`、system-spec-harness manifest/entry points、任意の resume state。
- 出力: confirmed specification/architecture node、C02 import report、version/digest/imported_at を含む source lineage。
- 完了条件: system-spec-harness の required 4 entry points、coverage/source-citation/evaluator gate が PASS し、dev-graph 内の同等生成ロジック複製が0である。
- 選択前の最小成果物: caller root・入力のpath/digest・依存版/4 entry points・lineageの検査結果を示す実際のpreflight report。R0/R1がPASSのときだけ提示して深さを記録する。確定nodeは評価後の最終成果物であり、この時点では作らない。

本 skill は仕様生成ロジックを持たない。system-spec-harness を起動し、確定成果物の検証と C02 取込だけを担う。

1. C24 で caller repo の `system-spec/` を解決し、plugin source/別 repo の content を拒否する。
2. `plugins/system-spec-harness/.claude-plugin/plugin.json` の name が一致し、version が `plugin-composition.yaml` の `external_dependencies.system-spec-harness.version` の範囲に入り、かつ `references/package-contract.json#entry_points.skills` が `run-system-spec-elicit`, `run-system-spec-doc-fetch`, `run-system-spec-compile`, `assign-system-spec-completeness-evaluator` を持つことを確認する。公式manifestへharness専用キーを混在させず、不在/不一致は fallback を実装せず停止する。版の範囲の正本は composition で、frontmatter の R1 の summary にある `>=0.1.0` は計画時の値である。
3. Skill 呼出しで elicit → 必要時 doc-fetch → compile → completeness evaluator を順に委譲する。開始時の C24 receipt を JSON ファイルで保存して R2 へ渡す。委譲先の Bash は呼出しごとに receipt の `repo_root` を `CLAUDE_PROJECT_DIR` に export し、その固定 root へ移ってから書込む。evaluator には `scripts/prepare-evaluation.py` が receipt を再検証して出力した絶対パスの args を渡す。Skill の読込や fork で cwd が変わっても評価対象を変えない (R2)。
4. confirmed 章と evaluator PASS だけを C02 に渡し、`source_lineage={origin_kind,plugin,path,version,digest,imported_at}`, confirmation evidence, readiness を specification/architecture node に保存する。

出力は import report (`system-spec/index.md`, imported node ids, lineage, confirmation_status, readiness)。feature は `architecture_refs` で参照し、内容を複製しない。1 feature→13 task は system-dev-planner の責務であり本 skill は扱わない。

## Resume と lineage gate

`../../scripts/validate-source-lineage.py --repo-root <DEV_GRAPH_ROOT> [--graph <path>] [--node-id <id> ...]` を R0 (resume) と R3 (C02 import の後) の決定論 gate にする。`origin_kind=system-spec-harness` の node だけを対象に、`source_path` が repo 内の通常ファイルとして実在し、その生 bytes の sha256 が `source_digest` と一致するかを副作用なしで検査し、`{status, checked, checked_node_ids, violations[]}` を返す (exit 0=pass、1=violation、2=usage/入力エラー)。C02 (`build-graph-node.py add`) も同じ関数で登録前に検査し、解決しない lineage は `source_lineage_unverified` で拒否される。

- R0 の resume は「取込済み node の lineage が今の `system-spec/` に解決するか」の確認である。`checked=0` (system-spec 由来の node がまだ無い。`system-spec/` 未作成を含む) は再開する対象が無いので、新規作成として手順 3 へ進む。`checked>=1` で exit 0 なら、取込済み node を保持したまま続きから再開する。
- exit 1 (取込元の削除・移動・編集で lineage が解決しない) と exit 2 は fail-closed にする。取込元の付け替えや digest の書換えで辻褄を合わせず、診断 JSON (`violations[]` の node/code/detail) をそのまま提示して停止する。
- この fail-closed は最小成果物を作る前の停止なので、artifact_delivery は初期状態 `artifact_created` に留まり `minimum_guard_pass` を発火しない。`artifact_presented`/`user_choice_recorded` へ進まず、semantic evaluator・Agent fork も起動しない。利用者が取込元を戻すか再取込を選んだ後に R0 からやり直す。
- R3 の import 後に同じ gate が exit 0 にならなければ、import report を完成扱いにせず、同じく診断を提示して停止する。

## ゴールシーク実行

### ゴール (Goal)

仕様書・アーキテクチャをplugins/system-spec-harness/の正規フローで構築し、出典・確定状態・上位目的traceを保ったままdev-graphのspecification/architectureノードへ取り込んだ状態になっている

### 目的・背景 (Why)

system-spec-harnessが既に持つヒアリング、カテゴリ×platform matrix、公式出典、確定章保護、独立完成度評価を複製せず引用し、dev-graphはグラフ登録とlineage維持だけを担うため。本skillが取り込むarchitecture/specificationノードはfeature.architecture_refsから参照されfeatureのアーキテクチャ文脈を成す (複製せずlineage参照のみ・MM-12)

### 完了チェックリスト

- [ ] system_spec content root が caller repo 内で repository_id/common-dir と一致する
- [ ] system-spec-harness が `plugin-composition.yaml` の version の範囲と required 4 entry points を満たす
- [ ] elicit/条件付き doc-fetch/compile/evaluator が system-spec-harness Skill 経由だけで実行される
- [ ] coverage/source-citation/evaluator gate が全て PASS である
- [ ] C02 登録 node の source_lineage/confirmation/evaluator evidence/readiness が欠落0である
- [ ] dev-graph 内に同等 elicitation/compile logic の複製が0件である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。shell 変数は Bash の呼出しをまたいで残らないので、後の呼出しでは、開始時の receipt の `repo_root` の値をそのまま書いて代入する (`pwd` や C24 の再実行から作らない)。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-progress.json` へ記録する。
- 親が正規Skillの呼出しとwriter操作を調整し、責務ごとのchecklistを閉じる前に `prompts/<R-id>.md` を全文渡した独立 `Agent` でreceipt・実成果・受入条件を検証する。R0/R1/R2/R3それぞれの検証結果を必要とし、親の自己申告だけで閉じない。Agentが本処理を担当する場合も同じ正規経路と境界を守る。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 上記3つの C19 集約ログは親 context が単独で更新する。責務 Agent には固定 C24 receipt・元の goal/hash・直前の次指示・担当 prompt を渡し、artifact/receipt と checklist の結果を返させる。Agent 自身の周回記録は `eval-log/run-dev-graph-system-spec/<R-id>/` に分け、集約 intermediate に別形状の行を混ぜない。親は各結果を6必須キーの周回記録へ統合して検証する。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 周回は親が未達checklistに対する操作と検証をまとめた区間で、責務名やSkill呼出しが変わるたびに増やすものではない。次周回の新規操作を開始する前に直前の `merged_directive_for_next` を入力する。同一周回内の既に開始した操作とread-only検証は並行できる。
- progress.json の `checklist` には、完了チェックリストの各項目を順に書き、status を `achieved` か `not_achieved` にして `evidence` を添える。`feedback_criteria` には IN1 と OUT1 を1回ずつ書き、IN1 には各周回の検証結果を status に書く。OUT1 は、この run の後の live trial が判定するので、run の中では PASS と書かず `status: external_pending` と書く。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist が `achieved` で、IN1 が PASS のときだけ完了する。

### ゴールシーク検証

各周回を閉じる前に、次の3ゲートを実行する。graphが未更新の周回もschema gateを省略しない。3つすべてexit 0のときだけ、その周回のIN1をPASSとしてprogressへ記録する。未実施・非0・実施待ちは `not_achieved` とし、残るゲートと次の操作を記録する。R3で後から通った結果を前の周回へ遡及しない。

```bash
DEV_GRAPH_ROOT='<開始時の receipt の repo_root>'
SYSTEM_SPEC_ROOT='<R1で検証した system-spec-harness plugin の絶対root>'
DEV_GRAPH_CODE_ROOT='<このSKILLを所有する dev-graph plugin の絶対root>'
SYSTEM_SPEC_DIR='<開始時receiptのcontent_roots.system_spec>'
GRAPH_PATH='<開始時receiptのlocal_state_paths.graph>'
python3 -B "$SYSTEM_SPEC_ROOT/scripts/validate-coverage-matrix.py" --matrix "$SYSTEM_SPEC_DIR/spec-state.json" --require-complete --require-basis --require-foundation &&
python3 -B "$SYSTEM_SPEC_ROOT/scripts/validate-source-citation.py" --targets "$SYSTEM_SPEC_DIR/spec-state.json" --references "$SYSTEM_SPEC_DIR/fetched-references.json" --state "$SYSTEM_SPEC_DIR/spec-state.json" --repo-root "$DEV_GRAPH_ROOT" &&
python3 -B "$DEV_GRAPH_CODE_ROOT/scripts/validate-graph-schema.py" --graph "$GRAPH_PATH" --repo-root "$DEV_GRAPH_ROOT" --strict-artifact-readiness
```

この実結果をprogressと6必須キーのintermediateへ記録した後、次の検査で中間成果物の欠落・goal drift・hash不一致をfail-closedにする。

```bash
DEV_GRAPH_ROOT='<開始時の receipt の repo_root>' && python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-intermediate.jsonl" <<'PY'
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
- evaluator PASS と confirmed の両方が揃わない章を C02 へ登録しない。evaluator の report が PASS になる前に、取込の入力を書いたり C02 の Skill を起動したりもしない (R3)。
- evaluator の起動前に `python3 -B "<skill root>/scripts/prepare-evaluation.py" --context-receipt "<開始時の C24 receipt の絶対パス>" --output eval-log/system-spec-completeness-report.json` を実行する。exit 0 の JSON の `skill_args` をそのまま Skill に渡す。helper は固定 receipt と現在の C24 identity/content root を照合し、repo 外・symlink 経由の書き先を拒否する。失敗時は `evaluation_context_invalid` で止め、手書き args で回避しない。
- evaluator の `--spec-dir`・`--output` と report の `spec_dir` は、helper が得た絶対パスに揃える。これは当該実走の評価先を固定するローカル証跡であり、移動して再利用しない。C02 の `evidence_ref` と source lineage は repo 相対のまま保つ。report の評価先が取込元と違えば手で書き換えず、R2 の検証を通した新しい評価を1回だけ行う。それでも違えば FAIL。dry-run にも確定と同じ payload (`confirmation_evidence` を含む) を渡す (R2・R3)。
- 委譲先の SKILL.md と責務 prompt は、出力を作る前に全文を読む。一部の Layer だけを読んで委譲先の出力を作らない (R2)。
- feature に仕様本文を複製せず、`architecture_refs` と source lineage で参照する。
