---
name: run-dev-graph-decompose
description: 大きな自然文構想を feature・architecture・機能間依存へマクロ分解したいとき、ready feature の system-dev-planner package を atomic 登録・binding 別投影したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C14
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "<want|--package PATH> [--repo-root PATH] [--manual-plan] [--dry-run]"
allowed-tools: [Read, Write, Bash, Skill, AskUserQuestion, Agent]
script_refs: [../../scripts/_common.py, ../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/gh-bridge.py, ../../scripts/bd-bridge.py, ../../scripts/build-github-projection.py, ../../scripts/build-graph-node.py, ../../scripts/register-package.py]
schema_refs: [../../schemas/graph-node.schema.json]
reference_refs: [../../references/feature-execution-package-contract.md, ../../references/execution-tracker-contract.md, ../../references/prompt-common-layers.md, ../../agents/dev-graph-integrity-auditor.md]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R2b-feature-planning.md
  - prompts/R3-decompose.md
  - prompts/R4-project.md
  - prompts/R6-dryrun.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "自然文の「やりたいこと(大)」とマクロ分解の粒度基準 (feature単位)・機能間依存推定方針、および --dry-run 指定の有無をヒアリングして確定する"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "自然文のwantからfeatureノード群+architectureノード+機能間depends_onへのマクロ分解案を組み立てる (1機能=13タスク仕様書への細分解はsystem-dev-plannerへ委譲しここでは行わない)"
  - id: R2b-feature-planning
    name: feature-planning
    prompt_required: true
    summary: "ready featureごとにsystem-dev-plannerを起動し、返却packageがP01..P13 exact 13 task/13-node DAG、共通parent_feature/feature_package_idを満たす場合だけC02へ渡す。手動/system-dev-planも同じ検査経路を通す"
  - id: R3-decompose
    name: decompose
    prompt_required: true
    summary: "C02で全feature/task (system-dev-planner/`/system-dev-plan`が返すpromoted task含む) のbinding/path/dependency/parent_featureを事前検証してall-or-none登録する。eligible taskをbinding=beadsならC28 create/dep-add、githubならC12 Issue、noneなら外部writeなしへ振り分け、既存linkageは再起票しない"
  - id: R4-project
    name: project
    prompt_required: true
    summary: "tracker_binding=githubかつissue_and_projectsのtaskだけをconfigured Projectsへ冪等追加し、Statusはlocal_to_projectで初期化する。beads mirrorとnoneはProject mutationしない"
  - id: R5-retry
    name: retry
    prompt_required: false
    summary: "Issue成功後のProject mutation失敗はローカルtask/Issue linkageを維持し、alias単位のsync_state=pending_retryとして次回C03 syncへ渡す"
  - id: R6-dryrun
    name: dryrun
    prompt_required: true
    summary: "--dry-run時はIssue/Project mutationを一切実行せず、Issue body、Project targets、field valuesのpreviewだけを返す"
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
      text: "validate-graph-schema.py で分解生成ノードを送信前検証しスキーマの必須キー欠落が 0 件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "マクロ分解結果 (feature+architecture+機能間depends_on) のDAGが循環なし・粒度閾値内で、評価前draftはIssue起票0件、confirmed/pass/readiness completeへの昇格後だけ起票対象になる"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "同一入力を二回実行してもbinding=beadsはbd issue/blocks edge、binding=githubはIssue/Project item、binding=noneはlocal nodeだけを各1組維持する"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "--dry-run時にlocal graph/Beads/GitHub/Projects writeが0件のままbinding解決と投影差分だけがpreviewされる"
      verify_by: test
    - id: OUT4
      loop_scope: outer
      text: "mode=both+auto、github+local_only、beads+Issue publicationを各fixtureでfail-closedし、外部write 0件となる"
      verify_by: test
    - id: OUT5
      loop_scope: outer
      text: "local batch成功後の外部mutation失敗でlocal taskを維持し、失敗node/operationだけpending_retryから冪等再実行できる"
      verify_by: test
    - id: OUT6
      loop_scope: outer
      text: "同一ready featureへの自動起動を二回実行してもP01..P13 exact 13 taskが一組だけ維持され、全taskのparent_feature/feature_package_idが一致する"
      verify_by: test
    - id: OUT7
      loop_scope: outer
      text: "同一featureに対する自動起動結果と手動`/system-dev-plan`実行結果は同じparent_featureで登録され、経路の違いによる二重登録が生じない"
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


# run-dev-graph-decompose

## Purpose & Output Contract

- 入力: 大きな want、feature 粒度/依存方針、C24/C11 検証済み graph context、任意の system-dev-planner package。
- 出力: feature/architecture/機能間 DAG の macro report、ready feature ごとの exact-13 package receipt、binding 別 publication report。
- 完了条件: macro DAG に phase-task 混入0、ready package が P01..P13 exact-set、自動/手動経路の二重登録0、dry-run write 0 である。

## Hard boundary

dev-graph はマクロ層: purpose/goal/scope/acceptance を持つ feature、共有 architecture node、feature 間 `depends_on` を所有する。system-dev-planner はミクロ層: **1 feature から P01..P13 の13 task specs/DAG/package** を所有する。本 skill が phase task を独自生成してはならない。

## Macro flow

1. 大きな want、feature 粒度、依存推定方針、dry-run を確認する。
2. want を feature 候補と architecture context に分解し、各 feature に `purpose/goal/scope_in/scope_out/acceptance/architecture_refs` を付ける。循環と実装粒度の task 混入を独立 auditor で拒否する。
3. C02 preview/atomic writer で macro graph を登録する。draft/unconfirmed/readiness incomplete は tracker 投影しない。
4. feature 間依存が満たされた ready feature ごとに `run-system-dev-plan` を Skill 呼出しする。`--manual-plan`/`/system-dev-plan` 結果も同じ package gate へ入れる。`--dry-run` では起動しない (system-dev-planner は planner 側に staging を書くため)。`--package` で渡された package だけを下の「dry-run の preview」で検査する。
5. P01..P13 exact 13、共通 parent/package、13-node DAG、source digest を検証し、C02 `register-package` へ渡す。`graph_node_id+source_digest` で自動/手動の二重登録を防ぐ。
6. `beads` は C28 create/dep-add、`github` は `build-github-projection.py` (gh 操作はすべて C12 gh-bridge 経由) で本文 marker `dev-graph:<graph_node_id>` を同一性とする Issue 一つと任意 Projects item 一つ、`none` は local only。mode=both+auto、github+local_only、beads+GitHub Issue mutation は fail-closed。

binding をまたぐ依存 edge は、どの tracker にも張らない。とくに、binding=beads の node が Beads に投影されない node に依存するとき、依存先には Beads の issue がずっとできない。Beads に投影されない node とは、binding が github か none の node と、この規則で投影を保留にした beads の node である。規則は依存の鎖をたどって当てるので、保留にした beads の node に依存する beads の node も保留になる。C28 の parity の照合は、depends_on と bd の `blocks` の完全一致を求め、Beads に linkage の無い依存先を持つ node を conflict として ready 推薦から外す (`bd-bridge.py` の `parity manifest dependency lacks a Beads linkage`)。この edge の投影の規則は C14・C28 の契約にまだ無いので、保留にした beads の node は graph に登録するが、Beads には投影しない。publication report に、保留にした node ごとに理由 `cross_binding_dependency` と、鎖の元の edge (beads の node から github か none の node への edge) の両端の id・binding を書き、どちらかの binding をそろえるかを人に確かめる。依存する側が github か none の edge は、local graph だけに持つ (C12 は依存 edge を投影せず、none は外部 write をしない)。

local commit 後の外部失敗は rollback せず node/operation 単位 pending_retry とし、`build-github-projection.py --retry-from <report>` でその operation だけを再実行する。`--dry-run` は local/Beads/GitHub write 0。出力は macro report、per-feature package receipt、publication report。

## ゴールシーク実行

### ゴール (Goal)

自然文の「やりたいこと(大)」からfeatureノード群+architectureノード+機能間depends_onを生成するマクロ分解を行い、ready featureごとにsystem-dev-planner(ミクロ層)を自動起動または手動`/system-dev-plan`実行結果を受理してpromoted typed task群をparent_feature付きでC02へatomic登録し、binding=beadsはC28へissue/依存edge、binding=githubはC12へIssue/任意Projects、binding=noneはローカルのみへ冪等投影した状態になっている

### 目的・背景 (Why)

マクロ (feature/architecture/機能間依存の保持+実行オーケストレーション) とミクロ (1 feature→13タスク仕様書) の責務混線を避けるため、C14は自然文のwantをfeature+architecture+機能間depends_onへ分解するところまでを担い、feature単位の細タスク仕様書生成はexternal plugin system-dev-planner (external_contract_ref: plugin-plans/system-dev-planner/handoff-run-plugin-dev-plan.json) へ委譲する。ready feature (機能間depends_on充足) ごとに [自動] run-system-dev-planをSkill呼出しでpurpose/goal/scope_in/scope_out/acceptance/architecture_refsを入力文脈として渡し、[手動] 人間の`/system-dev-plan`実行結果も同じ入口として受理する。両経路が返すpromoted typed taskはgraph_node_id+source_digestを冪等キーにC02単一writer経由でparent_feature=当該featureとしてatomic登録し、二重登録を防ぐ。既存の「自然文とpromoted system taskの入口一本化」責務は維持し、tracker_binding_intentはC02がrepo-configと照合して解決し、mode=bothのautoは拒否する。beadsはC28 create/dep-add、githubはC12 Issue/Projects、noneはlocal graphだけへ投影する。GitHub binding+local_onlyは未管理taskを生むため拒否する

### 完了チェックリスト

- [ ] macro result が feature/architecture/機能間 depends_on だけを持ち循環と phase-task 混入が0件である
- [ ] draft/unconfirmed/evaluation非pass/readiness非complete の tracker publication が0件である
- [ ] 各 ready feature package が P01..P13 exact 13、共通 parent/package、13-node DAG を満たす
- [ ] C02 local commit が all-or-none で、自動/手動経路の重複 node が0件である
- [ ] beads/github/none の各 task が単一 projection authority と linkage を持つ
- [ ] `--dry-run` の local/Beads/GitHub/Projects write count が0である

progress.json の各項目は `achieved`・`not_achieved`・`not_applicable` のどれかにする。`not_applicable` にしてよいのは次の場合だけで、evidence には代わりに確かめたものを書く。これ以外の未到達は `not_achieved` とし、overall は全項目が `achieved` か下の `not_applicable` のときだけ PASS にする。

- `--dry-run` の起動では、commit と投影をしないので「C02 local commit」と「単一 projection authority」の項目を `not_applicable` にする。代わりに、下の「dry-run の preview」が全 target の operation・判定・digest と write count 0 を示していることを evidence にする。「P01..P13 exact 13」の項目は、`--package` で渡された package があれば読むだけで検査できるので判定する。無ければ `not_applicable` にする (Macro flow 4 のとおり、dry-run では system-dev-planner を起動しない)。
- ready feature が0件のときは、「P01..P13 exact 13」の項目を `not_applicable` にする。feature ごとに、ready でない理由 (未完了の依存先など) を evidence に書く。
- `--dry-run` でない起動 (apply) では、「`--dry-run` の write count」の項目を `not_applicable` にする。preview と apply は別の起動なので、apply の起動ではこの項目を判定できない。evidence には、この起動が `--dry-run` でないことと、apply の前に取った preview の path (無ければ無いこと) を書く。

### dry-run の preview

`--dry-run` では graph・content・receipt と Beads/GitHub/Projects に書かない。C02 の入力と preview の JSON は、C24 receipt の `local_state_paths.cache` の下の `decompose-input/` に置き、write count には数えない。

1. C02 `build-graph-node.py add --dry-run` に graph にまだ無い macro node だけを渡し、出力を `decompose-input/c02-preview.json` に保存する。`planned_nodes` に、各 node を登録するときの状態 (status・confirmation_status・evaluation_status・implementation_readiness・depends_on・tracker_binding) が入る。新しい macro node が無い起動 (同じ want の再実行や `--package` だけの起動) では 1 を飛ばす。C02 は空の入力を `invalid_input`、既にある node を `duplicate_node` で拒むためである。
2. binding=beads の target には、C28 `bd-bridge.py --op create --dry-run` を当てる。1 があれば `--planned-preview <1 の path>` を付け、feature の node には `--artifact-kind feature` を付ける (付けないと `issue_type` が epic でなく task になる)。予定の node は、C02 が登録する状態で昇格 gate に判定され、評価前の draft は `blocked` (`planned: true`) になる。昇格済みの node は `promotion_gate.status: pass` と `issue_type` を返す。preview を作ったあとに graph が進んでいれば、C28 は stale として止まるので、1 からやり直す。
3. macro の node の間の依存 edge を、両端の binding で分ける (package の中の edge は 4 で扱う)。先に、Macro flow の規則で投影を保留にする beads の node を決める。依存先が github か none の beads の node を保留にし、保留にした node に依存する beads の node も保留にする。新しい保留が出なくなるまで、依存の鎖をたどる。
   - 依存する側が beads で、依存先が github か none の node、または保留にした beads の node: Beads に張れない。edge の両端の id と binding を書き、依存する側の target の判定を、2 の結果が pass でも `blocked` (理由 `cross_binding_dependency`) にする。依存先が保留にした node なら、鎖の元の edge の両端の id も書く。dep-add は呼ばず、「create の後に張る edge」とも書かない (人が binding をそろえるまで、依存先の issue はできない)。
   - 依存する側が保留にした beads の node で、依存先が保留でない beads の node: 依存する側は Beads に投影しないので、dep-add は呼ばない。edge の両端の id と、依存する側の保留の理由 (`cross_binding_dependency` と鎖の元の edge の両端の id) を書き、「create の後に張る edge」とは書かない。
   - 両端が beads で、どちらも保留でない: 両端の issue がすでにあるときだけ `--op dep-add --dry-run` を当てる。本番と同じ引数の検査と `bd show` を通り、書く直前で止まって `planned_bd_args` を返す。すでに張ってある edge には `{"idempotent": true}` が返るので、operation を「なし (既存)」と書く。片方でも未起票なら dep-add を呼ばず、「create の後に張る edge」として両端の id を書く。
   - 依存する側が github か none: 「local graph だけの edge」と書く。
4. `--package PATH` があり、その package がまだ登録されていなければ、C02 `register-package.py --dry-run` を当てる。register-package は 13 task すべてに status `active`・confirmation_status `confirmed`・evaluation_status `pass`・implementation_readiness `complete` を求め、1 件でも欠ければ止まる。後ろの3つは C28 の昇格 gate の条件 (`bd-bridge.py` の `PROMOTED`) と同じなので、rc 0 の receipt (`dry_run: true`・`write_count: 0`) は、13 task がすべて gate を通る状態で登録されることを示す。package の task はまだ graph に無く、C28 の create --dry-run は `not in graph` で止まるので、C28 には当てない。receipt の `node_ids` ごとに、binding (registration の `binding_intents`。`auto` は repo config の tracker mode と同じ値)・operation (beads は feature の epic の下の task の create、github は Issue、none は外部 write なし)・判定 (`pass`。根拠は receipt) を書き、package の中の edge にも 3 の規則を当てる。親 feature が `cross_binding_dependency` で blocked なら、package の task も同じ理由で blocked と書く。register-package が止まったときは、その error を package の判定として書き、package の task の投影は preview しない。
   package の `feature_package_id` の task がすでに graph にある (登録済み) ときは、register-package を当てない。中身が同じなら登録時の receipt がそのまま返り (`idempotent: true`。`write_count` が無く、`graph_revision_before` は登録時の値)、task が進んでいれば `duplicate node ids exist with different content` で止まるので、どちらも今の graph の上の preview にならない。package の判定は「登録済み (登録の operation なし)」とする。task ごとに、`beads_linkage` があれば operation を「なし (起票済み)」と書き、binding=beads で `beads_linkage` が無ければ、task はすでに graph にあるので 2 と同じく C28 の create --dry-run を当てる。binding=github の task は 5 で扱い、binding=none の task は operation を「外部 write なし」と書く。package の中の edge に 3 の規則を当てることと、親 feature が `cross_binding_dependency` で blocked なら task も同じ理由で blocked と書くことは、未登録の package と同じである。
5. binding=github の target は `build-github-projection.py --dry-run` の preview を使う。graph にまだ無い予定の node は、その計画に入らない。
6. preview には、target ごとの binding・operation・判定と digest を並べる。digest は、1 の C02 preview と 4 の register-package の receipt の `graph_revision_before`・`graph_digest_after` を書く。どちらも今の graph の上で作るので、両方があるとき、apply の後の digest はどちらとも一致しない (apply では C02 の後に register-package が走る)。1 も 4 の register-package の receipt も無い起動 (登録済みの package だけの起動を含む) では、今の graph の `graph_revision` と、build-graph-node の receipt と同じ計算の digest (graph を `sort_keys`・区切り `,` `:`・`ensure_ascii=False` で直列化した UTF-8 の bytes の sha256 に `sha256:` を付けた値) を書く。

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist が `achieved` か上の規則の `not_applicable` で、inner criterion (IN1) が PASS のときだけ完了する。outer criterion (OUT1-OUT7) は、この run の後の live trial と content review が判定するので、run の中では PASS と書かず `external_pending` と書く。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-decompose-intermediate.jsonl" <<'PY'
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

- `criteria:IN1`: `validate-graph-schema.py`で生成nodeを検証し必須キー欠落が0件である。
- `criteria:OUT1`: `feature+architecture` DAGは循環なし・task粒度混入なしで、評価前draftのIssue起票は0件、tracker投影は`confirmed/pass/readiness complete`だけに限定する。
- `criteria:OUT2`: 同一入力を二回実行しても`binding=beads`はbd issue/blocks edge、`binding=github`はIssue/Project item、`binding=none`はlocal nodeを各一組だけ維持する。
- `criteria:OUT3`: `--dry-run`はlocal/Beads/GitHub/Projects write 0件である。
- `criteria:OUT4`: `mode=both+auto`、`github+local_only`、`beads+Issue publication`の各authority衝突をfail-closedにし、外部write 0件にする。
- `criteria:OUT5`: local batch成功後の外部失敗は対象operationだけを`pending_retry`から冪等再実行する。
- `criteria:OUT6`: 同一ready featureの自動起動を重ねても`P01..P13 exact 13`は一組だけで、全taskの`parent_feature`と`feature_package_id`が一致する。
- `criteria:OUT7`: 自動経路と手動/system-dev-plan経路は同一parent featureへ収束し二重登録0件である。

## Gotchas

- dev-graph は macro feature/DAG だけを作り、P01..P13 task spec 生成を再実装しない。
- draft/unconfirmed/readiness incomplete の feature/task を tracker へ投影しない。
- 自動と手動の planner 結果を別 gate にせず、同じ `graph_node_id+source_digest` の冪等キーへ収束させる。
- local commit 後の外部失敗で macro graph を rollback せず、失敗 operation だけを `pending_retry` に残す。
- `mode=both+auto`、`github+local_only`、`beads+Issue mutation` は authority 衝突として fail-closed にする。
- binding=beads の node が github か none の node、または同じ理由で保留にした beads の node に依存するときは (依存の鎖をたどって当てる)、Beads へ投影せず `cross_binding_dependency` で人に確かめる。投影すると C28 の parity が conflict にし、ready 推薦から外れ続ける。
