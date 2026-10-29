---
name: run-system-dev-plan
description: dev-graph の1 featureを exact 13 task specsへ分解したいとき、独立評価後に13-entry inventory・13-node DAGを atomic promotionしたいときに使う。
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
version: 0.1.0
owner: team-platform
source: plugin-plans/system-dev-planner/component-inventory.json#C01
user-invocable: true
disable-model-invocation: false
argument-hint: "--feature-id <graph-node-id> --feature-context <repo-relative-json> [--repo-root DIR] [--config .dev-graph/config.json]"
allowed-tools: [Read, Write, Edit, Bash(python3 *), Glob, Grep, Skill, Task]
context: inherit
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-decompose.md
  - prompts/R3-emit.md
  - ../../agents/system-dev-plan-elicitor.md
  - ../../agents/system-dev-plan-architect.md
  - ../../agents/system-dev-plan-evaluator.md
schema_refs:
  - ../../schemas/feature-context.schema.json
  - ../../schemas/feature-execution-package.schema.json
  - ../../schemas/workstream-inventory.schema.json
  - ../../schemas/system-build-handoff.schema.json
reference_refs:
  - ../../references/repo-local-runtime-contract.md
  - ../../references/feature-execution-package-contract.md
  - ../../references/atomic-promotion-contract.md
script_refs:
  - ../../scripts/resolve-project-context.py
  - ../../scripts/check-implementation-readiness.py
  - ../../scripts/init-project-layout.py
  - ../../scripts/manage-system-plan-lock.py
  - ../../scripts/build-system-handoff.py
  - ../../scripts/validate-system-plan.py
  - ../../scripts/promote-system-plan.py
  - ../../scripts/extract-plugin-root.py
  - ../../scripts/validate-generation-lineage.py
  - ../../scripts/build-task-projection-rerun.py
combinators:
  - with-feedback-contract
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "1 feature の分解が exact 13 task specs と 13-entry inventory・13-node の intra-feature DAG を生成し validate-system-plan.py が DAG 非循環/orphan 0/inventory 矛盾 0/13 件厳密一致で exit0 通過する。promotion 後は対象 feature の generation lineage を書込なしモードで再検査し exit0 になる"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "各 task spec が system-task-spec 構造契約と workstream-inventory.schema.json の語彙(workstream_kind/build_target_kind)を満たし build-system-handoff.py が system-build-handoff.schema.json 準拠の handoff を exit0 生成する"
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: "確定 system-spec 起点の分解が feature 境界と repository boundary を保ち UBM 固有物を混入せず run-elegant-review の C1-C4 を全 PASS する"
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: "13 task specs が atomic promotion 前提の readiness(check-implementation-readiness.py)を満たし各 spec が実装者へそのまま渡せる粒度であると fork した system-dev-plan-evaluator が確認する"
      verify_by: evaluator
    - id: OUT3
      loop_scope: outer
      text: "実 feature-context を入力に end-to-end で R1-elicit→R2-decompose→R3-emit を走らせ、生成された 13 task specs が staging へ atomic promotion される。その後に対象 feature の generation lineage (現行世代の digest 再計算と supersede 済み世代の marker) をゲートし、二回目実行で構造が変化しないことを受入テストが確認する"
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
runtime_root_policy: host-skill-path
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# System development planning

## Purpose & Output Contract

dev-graph の1 feature を、確定 system-spec を起点に P01..P13 各1件の exact 13 executable task specs へ分解し、13-entry inventory と 13-node の intra-feature DAG を持つ package にまとめる。

- **入力**: `--feature-id <graph-node-id>` と `--feature-context <repo-relative-json>` (必須)、任意の `--repo-root` と `--config`。`init` は caller repository の layout だけを用意する。
- **出力 (pre-choice)**: staging の exact-13 package (`feature-package.json`・`task-specs/phase-01..13.md`・`workstream-inventory.json`・`task-graph.json`・`system-build-handoff.json`・`staging-manifest.json`)。C12 deterministic validation を通した path・digest・開き方を示す。
- **出力 (light/standard/detailed 選択後)**: 同じ canonical digest を再検証した atomic promotion の receipt・registration manifest・feature 別 current pointer と、best-effort の `plan-structure-report.html`・`task-specs.html`。
- **完了条件 (light/standard/detailed 選択後)**: C12 deterministic validation と fork evaluator C1..C4 が同一 canonical digest で PASS し、C11 の atomic promotion receipt が発行され、二回目実行で構造が変化しない。加えて対象 feature だけに scope した `validate-generation-lineage.py --repo-root <repo-root> --package <package-slug>` (書込なし) が exit 0 であること、すなわち現行世代の実バイトが pointer/receipt の digest と一致し、supersede 済み世代があればそれが byte-for-byte 不変で現行世代を指す marker を持つことまでを完了条件に含める。`<package-slug>` は C11 が書いた feature 別 current pointer (`<state>/current/<package-slug>.json`) のファイル名で、`feature_package_id` の英数字・`.`・`_`・`-` 以外を `-` に置換した値。marker 欠落は同じ scope の `--write-markers` (欠落時だけ作る create-only) で是正し、書込なしで再確認して完了とする。task projection (`tasks/<parent_feature>/<id>.md`) は本 run が発行した registration request を dev-graph が適用した後に初めて生成されるため、`build-task-projection-rerun.py` は本 run の完了条件に含めない。これは契約 1.3.0 未満で登録済みの projection を移行する別運用であり (`references/feature-execution-package-contract.md` §2.3)、repository 全件の移行・監査と同様に 1 feature run の完了スコープに混ぜない。
- **禁則**: 1 run で2つ以上の feature を扱わない。14件目の task と別の13 phase 文書を作らない。staging lock の JSON を C13 以外から作成・書換・削除しない。途中で失敗しても published/current の旧世代を壊さない。

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Invariants

- caller repository の解決と全 path 検査は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/resolve-project-context.py` に一元化する。`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` は code/assets の位置決めだけに使い、caller の文書・状態の authority にはしない。
- 1 run は1 `parent_feature` のみを扱い、P01..P13 各1件の exact 13 executable tasks を生成する。別の13 phase 文書と14件目は生成しない。
- C08 readiness、C14 handoff producer、C12 deterministic validationが一致したactual exact-13 packageをusable draftとして書き出し、path/digest/開き方を先に提示する。fork evaluator C1..C4はlight/standard/detailed選択後だけ起動し、初回提示を待たせない。post-choiceのfinal promotion/publishは同じcanonical digestを再検証してから行う。
- staging lock は C13 `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/manage-system-plan-lock.py` だけが生成・更新・解放する。`repository_id/run_id/session_owner/feature_id/feature_digest/acquired_at/heartbeat_at/expires_at` を束縛し、開始時に `acquire`、各動的計画反復に `renew`、成否にかかわらず終了処理で `release` を実行する。他 component は lock JSON を直接作成・書換・削除しない。
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/guard-implementation-readiness.py` は run 識別 env に依存せず repository-local canonical lock を自己発見し、malformed same-repository lock を fail-closed 拒否し、`expires_at` 超過 lock は C13 と同じ audit receipt 規則で cleanup する。

## `init`

`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/init-project-layout.py" --repo-root "$CLAUDE_PROJECT_DIR"`

missing config keys/directories だけを作成し、既存値・docs/specs/tasks/issues を上書きしない。receipt と repository_id 導出元を保存する。

## `plan`

`--feature-id` と `--feature-context` は必須。feature context は caller repository 相対 JSON で、`graph_node_id`, `artifact_kind=feature`, `purpose`, `goal`, `scope_in`, `scope_out`, `acceptance`, `architecture_refs`, `updated_at` を持つ。C09 が realpath containment を検証し、JSON の `graph_node_id` と `--feature-id` が一致しなければ staging 作成前に停止する。absolute path、`..`、root 外 symlink、別 repository の context は拒否する。

pre-choiceではmain contextがexact-13 packageの最小usable draftを1回生成し、C12 deterministic validationを通してpath/digestを提示する。以下の動的計画・fork evaluator・反復・promotionは利用者がlight/standard/detailedを選んだ後だけ開始する。

実装を始める前に、外側ループの `purpose`（なぜ行うか）/`background`（どの経緯・制約か）/`goal`（何をもって完了か）を goal-spec に固定する。各 P01..P13 は portable 契約 `system-task-goal-seek/v1` の内側ループとして、汎用実行 prompt・task goal・rubric・前周の feedback を入力に実行し、独立評価の `rubric verdict=PASS` まで修正と再評価を反復する。反復上限で PASS に届かなければ fail-closed で停止する。P13 は実行結果・判断・改善点を確定 system spec と architecture へ書き戻し、次回の外側ループへ引き継ぐ。

- C09 repo context と feature identity/context digest が確定している。
- C08 が system-spec index/requirements/architecture graph を `complete` と判定している。
- C13 が repository_id/run_id/session_owner/expires_at と feature id/digest を束縛した staging lock を atomic acquire し、各反復で heartbeat renew している。
- elicitor の goal-spec と architect の exact-13 package が同じ feature digestを参照する。
- C14 が exact-13 source の個別 SHA-256 と registration request/receipt owner 境界を持つ `system-build-handoff.json` を生成し、その bytes が `staging-manifest.json` の canonical digest に含まれている。handoff は receipt を自己発行しない。
- pre-choiceのC12 deterministic validationが提示対象digestをPASSしている。post-choiceではfork evaluator C1..C4がその同一digestを診断し、改善後はC12を再実行する。
- C11 が canonical digestごとのsame-filesystem atomic promotion、immutable receipt、registration manifest、feature別current pointerを生成している。source drift時は旧generation/receiptを保存し、新generationの`supersedes`から直前世代を追跡できる。
- C11 が promotion receipt/registration request を所有し、dev-graph の all-or-none apply/supersede が発行するgeneration別registration receipt と境界が一意である。C13 lock が解放され、published path/digest/receipt が dev-graphへ返されている。
- **計画構造レポート (plan-structure) が生成されている**: promotion 済み `task-graph.json` から「この feature で何をやるか + exact-13 タスク・ノード・依存の関係性」を 1 枚の自己完結 HTML (`plan-structure-report.html`) へ投影する。目的/本質的課題/できることの価値セクション (goal-spec / `value-narrative.json` 由来・非エンジニア/技術者の dual audience) と依存関係表を携帯し、build 前に計画の全体像を確認できるようにする。**plugin-dev-planner と共通の完了ステップ**として、両プランナーとも同一の共有 reporter を best-effort で呼ぶ (harness-creator 未配備環境では skip・非ゲート):
  共有 reporter は別 plugin (harness-creator) にあるので、`${PLUGIN_ROOT}/..` から推測せず、先に1回 `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/extract-plugin-root.py" harness-creator` で root を解決し、表示された absolute path を `<HARNESS_CREATOR_ROOT>` に使う。非0 で終わったら未配備としてこのステップと次の仕様書ブラウザを skip する。
  `python3 "<HARNESS_CREATOR_ROOT>/scripts/project-task-status.py" --task-graph <PLAN_DIR>/task-graph.json --goal-spec <PLAN_DIR>/goal-spec.json --out-html <PLAN_DIR>/plan-structure-report.html --out-md <PLAN_DIR>/plan-structure.md --out-json <PLAN_DIR>/plan-structure-status.json`
  `--goal-spec` を渡さないと reporter の価値セクション (目的/本質的課題/できること) は fail-soft で沈黙欠落する。非エンジニア向け平易層 (`plain_intro` 等) を出すには curated `value-narrative.json` を PLAN_DIR に用意する (未用意なら平易層のみ省略)。
- **仕様書ブラウザ (task-specs.html) が生成されている**: 13 フェーズ仕様書 (phase-01..13) と `task-specs/*.md` の本文を、サイドバー index → 各仕様書へページ遷移 → ブラウザ back で戻れる自己完結 HTML にする (中身閲覧ビュー)。構造/依存/価値の `plan-structure-report.html` と対になり、相互リンクで往復できる。**plugin-dev-planner と共通の完了ステップ** (best-effort・非ゲート):
  `python3 "<HARNESS_CREATOR_ROOT>/scripts/render-spec-browser.py" --plan-dir <PLAN_DIR>`

## Failure handling

light/standard/detailed選択後だけ `component-inventory.json` の `goal_seek.max_loops=5` を有効化する。5周で未達なら自動続行せず findings と staging path を報告する。accept-as-isではこの周回を0回のまま終了する。途中失敗時も published/current は旧世代を維持する。発見した独立作業は package に追加せず follow-up feature candidate として返す。

## Gotchas

- **`${PLUGIN_ROOT}` は caller の authority ではない**: plugin root は script と asset の位置決めにだけ使う。caller repository の文書・状態の解決と path 検査は `resolve-project-context.py` に任せる。
- **feature context の id 不一致は staging の前に止まる**: JSON の `graph_node_id` と `--feature-id` が違うと、C09 は staging を作らずに停止する。absolute path、`..`、root 外 symlink、別 repository の context も拒否される。
- **lock は C13 だけが触る**: 開始時の `acquire`、各反復の `renew`、成否にかかわらない終了時の `release` を `manage-system-plan-lock.py` で行う。lock JSON を手で書き換えて形が崩れると、guard hook が malformed lock として fail-closed で拒否する。
- **兄弟 plugin を `${PLUGIN_ROOT}/..` で探さない**: install 先では `..` の先が同じ plugin の別 version 群になる。harness-creator の reporter は `extract-plugin-root.py` で解決する。
- **reporter に `--goal-spec` を渡し忘れない**: 渡さないと `plan-structure-report.html` の価値セクションが警告なしに欠ける。
- **accept-as-is は周回を回さない**: `goal_seek.max_loops=5` が有効になるのは light/standard/detailed を選んだ後だけで、5周で未達なら自動続行せず findings と staging path を返す。
