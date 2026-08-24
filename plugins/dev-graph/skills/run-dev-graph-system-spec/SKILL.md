---
name: run-dev-graph-system-spec
description: system-spec-harness の正規フローで仕様を作りたいとき、確定した仕様・architecture を source lineage 付きで dev-graph に取り込みたいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C19
kind: run
effect: local-artifact
runtime_root_policy: host-skill-path
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--resume]"
allowed-tools: [Read, Bash, Skill, AskUserQuestion]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/validate-system-spec-delegation.py]
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
    summary: "run-system-spec-elicit→run-system-spec-doc-fetch(no-op可)→run-system-spec-compile→assign-system-spec-completeness-evaluatorを必ず順番どおり引用実行する"
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

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

**Key Rule:** R0〜R3は必ずmain contextで実行し、独立contextはqualified completeness evaluator内だけに限定する。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-dev-graph-system-spec

## Purpose & Output Contract

- 入力: C24 で caller repo 内に固定した `system-spec/`、system-spec-harness manifest/entry points、任意の resume state。
- 出力: confirmed specification/architecture node、C02 import report、version/digest/imported_at を含む source lineage。
- 完了条件: system-spec-harness の required 4 entry points、coverage/source-citation/evaluator gate が PASS し、dev-graph 内の同等生成ロジック複製が0である。

本 skill は仕様生成ロジックを持たない。system-spec-harness を起動し、確定成果物の検証と C02 取込だけを担う。

1. C24 で caller repo の `system-spec/` を解決し、plugin source/別 repo の content を拒否する。
2. `plugins/system-spec-harness/.claude-plugin/plugin.json` の name/version が `>=0.1.0 <1.0.0`、かつ `references/package-contract.json#entry_points.skills` が `run-system-spec-elicit`, `run-system-spec-doc-fetch`, `run-system-spec-compile`, `assign-system-spec-completeness-evaluator` を持つことを確認する。公式manifestへharness専用キーを混在させず、不在/不一致は fallback を実装せず停止する。
3. qualified Skill 呼出しで elicit → doc-fetch → compile → completeness evaluator を順に委譲する。既存 `fetched-references.json` が有効でも doc-fetch 自体を省略せず、正規 Skill に再検証を委ねて `no-op` または refresh の結果を得る。既存ファイルの独自検査を呼出しの代替にしない。全4呼出しの `result_status=PASS` と evidence SHA が validator に受理されるまで progress をPASS/4の取込可と扱わない。
4. validator PASS 後だけ、各章の repo-relative source path/SHA、system-spec-harness version、delegation receipt/progress path/SHA を `system-spec-import-attestation.json` にまとめる。qualified `dev-graph:run-dev-graph-node` Skill が正規 C02 writer の同一attestation付きdry-run→applyを実行し、staged C11 PASS 後にだけ `status=active`, `confirmation_status=confirmed`, `evaluation_status=pass`, `source_lineage={origin_kind,source_plugin,source_path,source_version,source_digest,imported_at}` と evaluator evidence を specification/architecture node へall-or-none保存する。

4 呼出しの戻りごとに `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-delegation.json` の `invocations[]` へ、順番、qualified entrypoint、`call_status` (`completed|no-op`)、`result_status` (`PASS|FAIL|INDETERMINATE`)、repo-relative `evidence_ref` とその SHA-256 を記録する。未来の呼出しを先に記録してはならない。進捗の `delegation` はこの receipt から導出し、次の validator が exit 0 になるまで `4/4` または PASS と扱わない。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-system-spec-delegation.py" \
  --repo-root "$DEV_GRAPH_ROOT" \
  --receipt "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-delegation.json" \
  --progress "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-progress.json"
```

`evidence_ref` は順に `spec-state.json`、`fetched-references.json`、compile 済み `index.md`、completeness evaluator report を指す。evaluator が FAIL/INDETERMINATE を返した場合も4番目の呼出し完了は記録するが、validator は非ゼロで停止する。C02 は呼ばず、開始時graph SHAの不変と追加artifact 0件をblocker証跡として返す。attestation/C11がFAILした場合も C02 writerのstaging/rollbackによりgraph/artifactをall-or-noneで不変に保つ。

出力は import report (`system-spec/index.md`, imported node ids, lineage, confirmation_status, readiness)。feature は `architecture_refs` で参照し、内容を複製しない。1 feature→13 task は system-dev-planner の責務であり本 skill は扱わない。

## ゴールシーク実行

### ゴール (Goal)

仕様書・アーキテクチャをplugins/system-spec-harness/の正規フローで構築し、出典・確定状態・上位目的traceを保ったままdev-graphのspecification/architectureノードへ取り込んだ状態になっている

### 目的・背景 (Why)

system-spec-harnessが既に持つヒアリング、カテゴリ×platform matrix、公式出典、確定章保護、独立完成度評価を複製せず引用し、dev-graphはグラフ登録とlineage維持だけを担うため。本skillが取り込むarchitecture/specificationノードはfeature.architecture_refsから参照されfeatureのアーキテクチャ文脈を成す (複製せずlineage参照のみ・MM-12)

### 完了チェックリスト

- [ ] system_spec content root が caller repo 内で repository_id/common-dir と一致する
- [ ] system-spec-harness が version `>=0.1.0 <1.0.0` と required 4 entry points を満たす
- [ ] elicit/doc-fetch/compile/evaluator が順番どおり system-spec-harness qualified Skill 経由だけで実行され、delegation validator が4件の実証跡を受理する
- [ ] coverage/source-citation/evaluator gate が全て PASS である
- [ ] C02 dry-run/apply receipt が同じsystem-spec attestationとstaged C11 PASSに束縛され、登録 node の active/confirmed/pass/source_lineage/evaluator evidence/readiness が欠落0である
- [ ] dev-graph 内に同等 elicitation/compile logic の複製が0件である

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: inline` / `max_loops: 5` を実行契約とする。固定手順は使わず、main context で未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、main context でその周回の処理を実行する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-system-spec-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- progress の `delegation.completed_count/status` は delegation receipt と validator stdout からだけ更新する。未呼出し・順序違反・PASS以外のresult・evidence digest 不一致では未達のまま停止する。
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
- 有効な `fetched-references.json` を見つけても doc-fetch の qualified Skill 呼出しを省略しない。再検証による `no-op` は許可するが、ファイル検査だけを呼出し済み証跡にしない。
- feature に仕様本文を複製せず、`architecture_refs` と source lineage で参照する。
