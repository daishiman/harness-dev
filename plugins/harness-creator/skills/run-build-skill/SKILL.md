---
name: run-build-skill
description: Capability 7 kind を新規作成・更新するとき、CapabilityManifest と plugin-composition.yaml を整備するときに使う。
triggers:
  [
    'skill作成',
    'skill更新',
    'agent作成',
    'hook配線',
    'slashcommand作成',
    'plugin-composition編集',
    'prompt生成',
    'workflow定義',
  ]
disable-model-invocation: false
user-invocable: true
argument-hint: '[skill-name] [kind?] [--mode create|update] [--stage draft|release] [--with-subagent] [--with-prompts] [--with-evaluator] [--with-hooks] [--with-knowledge index-search|router-registry] [--verification-profile incremental|exhaustive|build-only] [--model opus|sonnet]'
arguments:
  [
    skill_name,
    kind,
    mode,
    with_subagent,
    with_prompts,
    with_evaluator,
    with_hooks,
    with_knowledge,
    verification_profile,
    build_stage,
    model,
  ]
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Task
  - AskUserQuestion
  - Skill(assign-skill-design-evaluator *)
pair: assign-skill-design-evaluator
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-17
version: 0.3.0 # + with-goal-seek engine:task-graph 変種 (依存順駆動+self-reflect+cross-surface dependency graph knowledge)
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-scaffold.md
  - prompts/R2-responsibility-emit.md
  - prompts/R3-template-select.md
  - prompts/R4-trace-write.md
  - prompts/R5-initial-draft-evaluate.md
  - prompts/R6-bounded-improve.md
template_refs:
  - templates/agent-skeleton.md
  - templates/hook-skeleton.md
  - templates/command-skeleton.md
  - templates/plugin-composition-skeleton.yaml
  - templates/prompt-skeleton.md
  - templates/workflow-skeleton.md
  # ENG-Cxx = 生成 harness 同梱 engine 系 component id (凡例表: $PLUGIN_ROOT/references/pipeline-boundary-contract.md)
  - templates/task-graph-engine/scripts/ready-set-from-checklist.py       # engine:task-graph 同梱 (ENG-C01)
  - templates/task-graph-engine/scripts/self-reflect-append.py            # engine:task-graph 同梱 (ENG-C02)
  - templates/task-graph-engine/scripts/extract-capability-dependency-graph.py  # engine:task-graph 同梱 (ENG-C06)
  - templates/task-graph-engine/scripts/record-capability-graph-knowledge.py    # engine:task-graph 同梱 (ENG-C07)
schema_refs:
  - references/capability-manifest.schema.json
  - schemas/verification-contract.schema.json
  - schemas/verification-evidence.schema.json
  - schemas/review-launch-request.schema.json
  - schemas/initial-draft-review.schema.json
  - schemas/improvement-user-event.schema.json
  - schemas/improvement-decision.schema.json
  - schemas/improvement-result.schema.json
  - schemas/usable-draft-proof.schema.json
prompt_format: markdown # 既定: Markdown (.md)。YAML (.yaml) は legacy 許容、新規禁止
script_refs:
  - scripts/build-external-intelligence.py
  - scripts/auto-record-lesson.py
  - scripts/render-combinators.py
  - scripts/render-frontmatter.py
  - scripts/validate-naming.py
  - scripts/build-subagent.py
  - scripts/validate-build-trace.py
  - scripts/lint-goal-seek.py
  - scripts/lint-capability-graph-knowledge.py  # engine:task-graph の ENG-C06/ENG-C07 同梱・consult・source_ref 検査 (ENG-C08)
  - scripts/lint-ssot-duplication.py
  - scripts/derive-route-build-obligations.py
  - scripts/derive-verification-contract.py
  - scripts/plan-verification-obligations.py
  - scripts/record-verification-evidence.py
  - scripts/build-improvement-gate.py
  - scripts/build-usable-draft-proof.py
  - scripts/build-review-launch.py
  - scripts/validate-improvement-result.py
reference_refs:
  - ref-skill-glossary
  - ref-task-context-map
  - ref-output-routing
  - ref-knowledge-loop
  - references/reproducibility-trace-schema.md
  - references/goal-seek-paradigm.md
  - references/verification-obligation-protocol.md
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成 Capability が命名/構造/frontmatter/goal-seek/completeness/ssot lint と validate-build-trace を全て exit0 で通過する
      verify_by: lint
      derived_from: [CL-1, CL-2, CL-3, CL-4, CL-7, CL-9, CL-10, CL-11]
    - id: IN2
      loop_scope: inner
      text: skill-build-trace.json が source_docs/doc_coverage/layer_decisions/reproducibility_gates を空欄なく記録している
      verify_by: script
      derived_from: [CL-6]
    - id: IN3
      loop_scope: inner
      text: plugin 一括 build (handoff routes 消費) では route 完了ごとの実行レポートが validate-route-build-reports.py --route/--complete を exit0 で通過する (単発 build は N/A)
      verify_by: script
      derived_from: [CL-12]
    - id: OUT1
      loop_scope: outer
      text: machine proof後に残るsemantic obligationがcurrent fingerprintに束縛されたPASS証拠を持ち、confidence閾値以上かつhigh severity 0件
      verify_by: verification-obligation
      derived_from: [CL-5]
    - id: OUT2
      loop_scope: outer
      text: 全7 Capabilityのusable draftは共通launch requestの単一active leaseを使い、stale時は同一idempotency identityで再配送し、所見提示とユーザー選択後は選択findingだけを有界改善してC1-C4を再検証し、release/exhaustiveへ自動昇格しない
      verify_by: verification-obligation
      derived_from: [CL-8, CL-13]
# context-budget (CD-005): 章一括ロード禁止 / max-reference-chapters: 3
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-22
audit-trigger: quarterly
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

# run-build-skill

## Runtime root contract

`runtime_root_policy: host-skill-path` の製品別root解決・cwd推測禁止・prompt継承は [ref-cross-platform-runtime の共有正本](../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約) をそのまま適用する。

> Phase 2 移行後は `plugins/harness-creator/skills/` が正本、`.claude/skills/` は symlink/deploy target。plugin同梱資産は解決済みabsolute `$PLUGIN_ROOT` / `$SKILL_DIR` で参照する。生成対象repositoryのroot-level gateだけは、明示したproject rootを別入力として使う。

## Purpose & Output Contract
ユーザー要求から Claude Code Skill を 1 本構築するワークフロー。

- **入力**: `skill_name` (kebab-case), `kind` (run|ref|assign|wrap|delegate), `mode` (create|update), `build_stage` (draft|release、既定=draft), 各種 `--with-*` フラグ, `model` (opus|sonnet)。フラグ仕様は `schemas/build-flags.schema.json`。
- **出力**: `$OUT_BASE/<name>/SKILL.md` (170 行を目安・本文 300 行以下が上限 (P0-2)、frontmatter 完備、本文は日本語) / `templates/` / `references/` / `scripts/` / `prompts/` / `eval-log/skill-build-trace.json` / verification contract・plan・evidence receipts (既存content-review verdictも互換投影として保持)。
- **draft proof 条件 (既定)**: 実際に試せる生成物があり、class別の最小guardが通り、`stage_gate.status=usable-draft`となること。現物のpath/試し方を先に提示し、その後に利用者が診断・改善深度を選ぶ。
- **release 完了条件 (明示時のみ)**: build/semantic/behavior obligation DAGがcurrent PASS proofで閉じ、rubric high severity 0 件、C1-C4 ゲート pass、`validate-build-trace.py` exit 0。`build-only` は未実施proofを明示し完了を偽装しない。

### usable-first stage
`draft` と `release` の2段階だけを使う。別の MVP mode は追加しない。無指定では draft の生成と class別最小guard (parse/open・secret・不可逆操作・破損) だけを解き、修復は1周までとする。7 Capabilityのいずれも `artifact_created → minimal_guard_passed → artifact_presented → user_choice_recorded → semantic_evaluator_started` の順を守る。現物と試し方の提示後に診断深度を聞き、`accept-as-is` はevaluator 0 / improver 0。選択された場合だけsemantic evaluator / 30思考法 / multi-agent / 有界改善を起動する。`release` / `exhaustive` は明示選択なしに自動昇格しない。

`build-review-launch.py` はgateのdurable claimを同一lock下でatomic consumeし、artifact+contract fingerprintあたりruntime-neutral requestを1件だけ作る。再生時は `authorized=false` でfail-closedにする。Claude Codeはそのpayloadで `elegant-initial-draft-evaluator` Task、Codexは同じpayloadとR5による単一subagentを起動する。両者ともRead/Glob/Grep限定のfresh contextで、他runtimeはfail-closed。親contextで同じ30思考法を繰り返さない。

## Key Rules
### 契約系 (contract)
1. 本文 300 行以下 (07章)。`description` は発動条件のみ、trigger 2-3 個 (08章)。
2. ディレクトリ名 == `frontmatter.name`、`name` に plugin 名を含めない (06/34章)。
3. Python 標準ライブラリ正本。`.sh` / `.js` 新規禁止、scripts 内 yaml import 禁止 (22/28章)。
4. `--mode update` は Edit 差分のみ。全書き換え禁止 (CD-002)。
5. 具体値直書き禁止。`{{PROJECT_ROOT}}` 等の変数で表現し source_trace に残す。
6. **marketplace install 配置非依存**: plugin 資産の読込は `runtime_root_policy: host-skill-path` に従う。Claude Codeでは `CLAUDE_PLUGIN_ROOT`、Codexではホストが提示したabsolute `SKILL.md` pathからmanifestを持つ祖先を解決し、各shell invocation内の論理 `PLUGIN_ROOT` とする。plugin rootをcwd・repo相対位置から推測せず、literal placeholderをshellへ渡さない。生成物の出力先だけを `$CLAUDE_PROJECT_DIR` / cwd / `$CLAUDE_SKILL_OUT_BASE` で解決する。

### 責務系 (responsibility)
7. R-id 単位の責務分離。生成 SubAgent は `references/agent-template.md` 9 セクション固定構造。
8. 評価分離: 生成本体は採点しない。machine proof後に未解決のsemantic obligationがある場合だけ、別contextの `assign-skill-design-evaluator` へ最小sliceを渡す (09章 Goodhart)。
9. 実行レイヤー (Skill/Subagent/Hook/MCP/CLI/script) の配置理由を trace に記録 (01a/05章)。
10. 横展開候補 (Harness Creator 基盤/hook/lint/adapter/rubric/reference) は plugin 登録判定へ戻す。
11. 量産情報 (`pattern_refs` / `variant_axes` / `reuse_targets` / `deterministic_checks` / `placement_candidates` / `hook_events`) を trace と本文へ反映 (29-35章)。

### lint 系 (lint)

12. **manual-preflight の lint 集合の正本は `$PLUGIN_ROOT/references/lint-matrix.json`** (context=build-preflight。Step 4 の bash ブロックはその射影で、乖離は `lint-matrix-sync.py` が CI で fail。28章: A/B 強制 gate と呼称分離)。`lint-ssot-duplication.py` は編集前に対象プラグイン全体を重複解析する事前ゲート (両方残し禁止・上書き一本化の判断材料)。検出は **DUP-SCHEMA-ID** (同一 `$id`=正本曖昧, **exit1 で fail**) / **REDIRECT-FAT-BODY** / **DUP-REQUIRED-SET** / **DUP-PASSAGE** (後 3 者は smell、build 時は warn・CI の `--strict` で fail 化) の 4 種。build Step4 は早期警告、強制は `governance-check.yml` の `--strict` 実行が担う。
13. `validate-build-trace.py` が `source_docs` / `build_flow_coverage` / `doc_coverage` / `layer_decisions` / `reproducibility_gates` の空欄・未読・N/A 理由なしを拒否。
14. context 予算 (CD-005): 同時 Read は 3 章まで。`references/resource-map.yaml` で task category → 章選択。
15. ch15/ch16 公式参照確認は必須 (Step 1 冒頭)。
16. 26/27/28 章 / 29-35 章ゲートは N/A 理由つきで省略可、未記入は不可。
17. **prompt 形式**: 新規 prompt は **Markdown (`.md`) を既定**とし、`prompts/<R-id>-<slug>.md` で生成する。骨格は `plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-markdown-template.md` を写経。YAML (`.yaml`) は既存資産のみ許容し、新規作成は禁止 (warn を発する)。
18. **Capability 7 kind 統一**: skill / agent / hook / command / plugin-composition / prompt / workflow の全 kind で `CapabilityManifest commonCore` を必須とする。**必須項目集合の正本は `references/capability-manifest.schema.json#/definitions/commonCore.required` 唯一**（本文に再掲しない＝SSOT。現行は `name` / `description` / `kind` / `version` / `owner` の5項目。`since` / `source-tier` 等は任意）。kind 別追加フィールドは同 schema の `definitions/<kind>` を参照。`commonCore` 欠落は `validate-frontmatter.py` が exit 1（同 lint は必須集合を schema から動的ロードし、`--self-test` で正本との drift を検出）。

19. **ゴールシーク必須 (固定手順禁止)**: ループ実行系 kind (run / wrap / delegate / orchestrator / agent / agent-team / hook-integrated) は達成手順を固定列挙せず、`## ゴールシーク実行` (**Goal + 目的/背景 + 完了チェックリスト + ゴールシークループ**) で構成する。手順は実行時に AI がチェックリストの未達項目から都度生成する。`assign-*` は評価系のため Goal/Checklist 形は使うが runtime loop は配線しない。`ref-*` (read-only) は対象外で `## 手順` は「参照用。手順なし。」のまま。正本定義は `references/goal-seek-paradigm.md`。lint は `lint-goal-seek.py` (固定 `### Step N:` の連番羅列を実行系本文で検出したら violation)。
    - **実行可能機構の配線 (with-goal-seek combinator)**: loop 実行系 (run / wrap / delegate) は `render-combinators.py` が `with-goal-seek.patch` を**default-ON で自動適用**し (`--no-goal-seek` で opt-out)、frontmatter `goal_seek:` と `### ゴールシーク配線` を注入する。周回状態は `schemas/goal-seek-loop.schema.json` 準拠の `eval-log/<skill>-progress.json` に記録し、重い周回は `Skill(run-goal-seek)` に fork 委譲する。`assign-*` は checklist のみ (ループ非配線)。`lint-goal-seek.py` は loop 実行系に対し二値チェックリスト項目の存在・曖昧語不在を violation、`### ゴールシーク配線` 不在を warning で検査する。フラグ仕様は `schemas/build-flags.schema.json#/properties/with_goal_seek`。
    - **engine 変種 (inline / run-goal-seek / task-graph)**: `goal_seek.engine` は独立 combinator flag ではなく with-goal-seek 内の選択値。loop kind (run/wrap/delegate) の**既定は `task-graph`** (量産ハーネスは既定で依存順駆動+self-reflect。Step 10.6・`with-goal-seek.patch` default 準拠)、opt-down で `inline`(自己完結)・`run-goal-seek`(重量オーケストレータへ任意 fork) を明示選択する。`task-graph` は checklist の `depends_on` を依存充足順に消費し (`ready-set-from-checklist.py` で ready 集合の最小 id を拘束選択=依存順が「助言」でなく「拘束」)、実行中の新規タスクを `self-reflect-append.py` で checklist 末尾へ自己反映し (別状態ファイル新設せず progress.json を唯一の truth に保つ)、cross-surface dependency graph knowledge を `extract-capability-dependency-graph.py`/`record-capability-graph-knowledge.py` で抽出・記録・consult する engine 変種。同梱は **Step 10.6** の決定論 materializer と build-plan required_deliverables で機械化し、欠落/byte drift/profile driftを `--check` で拒否する。現 profile は `engine_profile=checklist-graph` / `full_task_spec_graph=false` であり、plugin-dev-planner の task-specs→graph→envelope/state/projection→spec-improvement outer loop と同等とは扱わない。

`kind → templates/_base + combinator` 対応表は **`schemas/template-selection.schema.json#/selection_rules`** を正本とする (本文に再掲しない)。

## ゴールシーク実行

> 本 Skill は固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。下記「局面カタログ」は順序固定の手順ではなく、未達項目に応じてループが選ぶ局面メニュー。正本: `references/goal-seek-paradigm.md`。

### ゴール (Goal)

対象 Capability (7 kind) が `$OUT_BASE/<name>/` に生成・更新され、draft では試用可能な現物+決定論ゲート、release では加えて全obligationのPASS証拠に到達する。`eval-log/skill-build-trace.json` は、同一 brief→同一判断順序と繰越し範囲を証跡化する。

### 目的・背景 (Why)

量産対象は kind・ドメイン・出力先が多様で、固定手順は前提が崩れると破綻する。各stageの到達点とチェックリストを固定し、手順は未達項目から都度導出する。これにより、最初の現物を早く試しつつ、確認後の release でのみ網羅性を回収できる。

### 完了チェックリスト (Checklist)

- [ ] kind を 7 種から確定し、commonCore frontmatter (必須集合の正本 = `references/capability-manifest.schema.json#/definitions/commonCore.required`: `name`/`description`/`kind`/`version`/`owner`) を生成した <!-- CL-1 -->
- [ ] 本文 300 行以下・description は発動条件のみ・trigger 2-3 個 (08章) <!-- CL-2 -->
- [ ] kind 別必須サポート資産 (prompts/references/schemas/scripts) を実在・共有正本参照・`completeness_exempt` 理由付き宣言のいずれかで満たした (`lint-skill-completeness.py` exit0) <!-- CL-3 -->
- [ ] P0 lint 群 + `lint-goal-seek.py` + `lint-skill-completeness.py` + `lint-ssot-duplication.py` + `validate-build-trace.py` が exit 0 <!-- CL-4 -->
- [ ] (`build_stage=release` のみ) machine proof後に残るsemantic obligationを独立e evaluatorが判定し、score>=80 かつ high=0 (draft は `deferred_to_release` へ記録) <!-- CL-5 -->
- [ ] `eval-log/skill-build-trace.json` に `source_docs`/`doc_coverage`/`layer_decisions`/`reproducibility_gates` を空欄なく記録 (未使用は N/A 理由付き)。brief 経由 build は `requirement_coverage` (RTM) で brief 非空フィールドの被覆を宣言 <!-- CL-6 -->
- [ ] (loop 実行系 run/wrap/delegate のみ) `feedback_contract.criteria` を `brief.goal`/完了チェックリストから導出し inner/outer 各1件以上を trace に記録 (ref/assign は `feedback_contract.skip_reason` で N/A)。各 criterion は `derived_from: [CL-n]` で出所チェックリスト項目を宣言 (`lint-criteria-provenance.py` が被覆を検査) <!-- CL-7 -->
- [ ] **ハーネス・カバレッジ仕様 (`doc/harness-coverage-spec.md`) を kind 別に満たす** (draft は実体を起動できる決定論ゲートまで、意味・実走カバレッジはreleaseへ繰越し): <!-- CL-8 -->
  - 同梱 `scripts/` があれば `tests/` に機能テストを追加し当該スクリプト行カバレッジ ≥80% (network/secret 系は monkeypatch で副作用遮断し純関数・分岐・エラー経路を genuine に網羅)。純 re-export shim は import 経由の間接被覆+理由記録 (coverage record への明記) で代替可。LLM eval record は補完であり機能テストの代替にはならない
  - loop 実行系: criteria 検証テスト (inner=lint exit0 / outer=verdict PASS) で全 criterion を被覆 (`validate-llm-coverage.py --gate-new --since <today>` を ≥80% で通す)
  - **ref (辞書型/参照型): source-traceability を検証する** — `source`/`source-tier`/`last-audited`/`audit-trigger` が埋まり、参照内容が `source` と整合することを `eval-log/coverage/skills/<plugin>__<skill>.json` の ref-review verdict (verdict=PASS) で記録。ref は behavioral criteria を持たない代わりにこの source 検証が必須カバレッジ (除外でなく ref 専用パス)
  - assign: evaluator verdict、その他 kind: content-review verdict を `eval-log/coverage/` に記録
- [ ] `eval-log/build-plan.json` (`validate-build-plan.py --brief ... --out eval-log/build-plan.json` で brief から決定論導出) の `flags` が true の subagent/prompt/evaluator/hook/knowledge を全て生成し、`--check` が exit 0 (フラグの要否をモデル判断で省略しない) <!-- CL-9 -->
- [ ] (`--with-knowledge` or `brief.knowledge_loop` 指定時のみ) curated seed の knowledge/ 雛形展開 + 5スクリプト同梱 + plugin package 外の external-intelligence state + `## ナレッジループ`節注入 + `knowledge_loop`記述子(`contract_version: 1`, `consult_at: ["runtime"]`, `runtime_store: external-intelligence-v1`) + `lint-knowledge-loop.py` exit0 (KL-001..008) <!-- CL-10 -->
- [ ] (kind=plugin で外部依存(API/DB/秘密)の疎通確認手順が要る場合のみ) install位置を `__file__` 相対で自己解決する doctor 同梱 + 疎通確認はチャット委譲(`/<name>-doctor` or 自然文) + 生のplugin root変数非露出 (README **及び `references/*-setup.md` 等 setup 手順**の bash は**一次手順としては**doctor entry pointだけを案内し、生パス例は開発者補足へ降格したfallback形に限る(env/cwd/repo相対によるplugin root推測は不可)。番号付きリスト内の字下げフェンスも同様)。`scripts/lint-readme-plugin-root-portability.py` exit0。正本 `ref-cross-platform-runtime/references/runtime-portability.md` 層2 <!-- CL-11 -->
- [ ] (plugin 一括 build=handoff routes 消費時のみ) 実行済みrouteごとに `eval-log/<slug>/build/route-<id>.json` を記録し `validate-route-build-reports.py --route <id>` exit0。全 route 終端の `--complete` はreleaseのみ (契約正本 `references/route-build-report.md`) <!-- CL-12 -->
- [ ] (`build_stage=draft`) 実artifactの最小guard後にpath/試し方を提示し、その後に診断深度を質問する。accept-as-isはevaluator/improver 0、選択時だけ`elegant-initial-draft-evaluator`をread-only起動し、release/exhaustive自動昇格0件 <!-- CL-13 -->

### ゴールシークループ

正本 `references/goal-seek-paradigm.md` の 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し) に従う。本 Skill 固有の差分:

- 現状評価は上記チェックリストの未達項目を対象にし、それを埋める局面を下記「局面カタログ」から選ぶ (順序固定なし)。
- 検証は決定論検査 (lint/trace/score) を優先し、`### 局面: 命名・構造 Lint` / `### 局面: フォーク評価` のコマンド群で機械判定する。
- ゲート未達の再実行は draft で1周、release で最大3周。draft は超過時に完全化へ進まず、現物と最小修正を引き渡す。

## 局面カタログ (順序は都度判断)

詳細フローは `workflow-manifest.json` の phases、各責務プロンプトは `prompts/<R-id>.md` (Markdown 既定。legacy `.yaml` も読み取り可) に委譲する。下記は固定順序ではなく、ゴールシークループが未達チェックリスト項目に応じて選ぶ局面群。

### Step 0: kind 分岐ナビゲーション (phase: init-pre)

本 Skill は **Capability 7 kind** (skill / agent / hook / command / plugin-composition / prompt / workflow) を統一抽象として扱う。以下 4 段で分岐する。

1. **kind 確認**: 引数 `kind` または `brief.kind` を確定。既定は `skill`。未指定なら Step 1 のヒアリングで決める。7 kind 以外は exit 1。
2. **対応 skeleton 選択**: kind 語彙の正本は `schemas/build-flags.schema.json#/properties/capability_kind` (7値 enum)、kind → skeleton/出力先/kind別lint の対応表の正本は `references/build-steps.md` §I.1 (本文に再掲しない=SSOT)。kind=skill 配下のサブ種別 5 値の template 選択は `schemas/template-selection.schema.json#/selection_rules` に従う。
3. **Manifest 検証**: 全 kind で `CapabilityManifest commonCore` を `references/capability-manifest.schema.json` で検証。kind 別追加フィールド (`definitions/kindSkill`, `definitions/kindAgent` …) も同 schema で検証する。
4. **lint hook 連動**: kind に応じた lint を Step 4 で起動 (skill→既存 4 種、agent→`lint-agent-prompt-section.py` + **`lint-agent-prompt-content.py --mode agent`** (route C02 内容 lint)、hook→`lint-script-frontmatter.py`、plugin-composition→`lint-plugin-composition.py` (整備済・CI 配線済)、prompt→**`lint-agent-prompt-content.py --mode prompt`** (route C02))。command / prompt (構造面) / workflow の kind 専用 lint (`lint-command-md.py` / `lint-prompt-md.py` / `lint-workflow-md.py`) は**未実装 (script 実体なし・整備予定) のため起動しない** — それまで当該 3 kind は共通 lint (`validate-frontmatter.py` 等) のみで検査する。**agent/prompt 生成は本文7層 (l5-contract v2.0.0) を prompt-creator 経由で生成し route C02 を fail-closed ゲートとして通す** (契約: `../../../prompt-creator/skills/run-prompt-creator-7layer/references/subagent-hybrid-format.md`)。単独生成の抜け道は Step 3.5 の `prompt_provenance` で塞ぐ。

> 既存「Skill のみ作る」呼び出し (`kind=run|ref|assign|wrap|delegate`) は **kind=skill 配下のサブ種別** として後方互換維持。引数なしまたは `kind` が 5 択のいずれかなら従来通り Step 1 以降の skill 専用フローへ直行する。`kind_filter` はskill内部のサブ種別、`capability_kind_filter` はCapability 7 kindを指す。skillはskill専用phase、非skillは `non-skill-build-lint` のkind別生成/lintを経由し、どちらも共通 `usable-draft-proof` (Step 12.4) → `initial-draft-review` (Step 12.5) へ合流する。Step 12.6/12.7は利用者の選択とその結果に応じてだけ進む。phase依存とkind別upstream対応の正本は `workflow-manifest.json`。

### Step 1: 要求ヒアリング (phase: init)

> **[MANDATORY]** 冒頭で `Skill(ref-yaml-spec-fetcher)` を呼び `yaml-spec-cache.md` を Read。`validate-build-trace.py` が 15/16 章未実施を exit 1 で拒否する。

`resolve-skill-dirs.py` で `$PLUGIN_ROOT` / `$SKILL_DIR` / `$OUT_BASE` を確定する。`$SKILL_DIR` は harness-creator plugin 内資産、`$OUT_BASE` は生成先であり、両者を同一パスと仮定しない。続けて `references/resource-map.yaml` で task category 選択 → 01章 5 要素 + 01a Step2 実行レイヤー判断表を埋める。詳細は `references/build-steps.md`。

**蓄積知見の参照 (Loop B / build-time)**: `brief.consult_build_knowledge` が true (既定) のとき、harness-creator 自身の蓄積知見を検索し、過去の設計判断・落とし穴回避を初期設計に反映する (`knowledge/knowledge-index.json` の consult 宣言と対。`run-skill-elicit` の同名節と同形):

```bash
# Runtime root contractで解決済みのabsolute self assetを使用する
python3 "$SKILL_DIR/templates/knowledge-skeleton/scripts/search_knowledge.py" \
  --dir "$PLUGIN_ROOT/knowledge/" --query "<brief.goal と kind の要約>" --limit 5

# 運用中に得た外部知能は薄い index だけを検索し、候補の詳細は必要時だけ show する
python3 "$SKILL_DIR/scripts/build-external-intelligence.py" --agent <codex|claude|other> \
  --project-root "${CLAUDE_PROJECT_DIR:-$PWD}" search --query "<brief.goal と kind の要約>" --limit 5
```

検索 0 件・スクリプト不在でも build を止めない。上位5件だけを見て、詳細は `show --id <id>` で選択取得する。実際に判断を変えた既存 entry は完了時に `reuse --outcome helpful|neutral|unhelpful` で記録し、採否を trace の `layer_decisions` に残す。loop 実行系 (run/wrap/delegate) はこの時点で `brief.goal` と完了チェックリストから per-skill 評価基準 (`feedback_contract.criteria`) を test-first で導出し、Step 3.5 で trace に固定する (criteria は goal-seek checklist と同源)。

**build-plan の決定論導出 (フラグはモデルが決めない)**: brief 確定直後に必須成果物集合を機械導出し、以降はこの plan を作業リストの正本とする。`--with-*` の要否・必須セクション・必須資産は brief の非空フィールドとテンプレート見出しから純関数で決まる (モデルの記憶・判断に依存しない):

```bash
python3 "$SKILL_DIR/scripts/validate-build-plan.py" --brief eval-log/skill-brief.json --out eval-log/build-plan.json
```

無指定は `flags.build_stage=draft`。Skill起動時に `--stage release` が明示された場合だけ、上記コマンドに同じ `--stage release` を付け、planへ決定論に固定する。充足検査は Step 4 の `--check` が行う (欠落は exit 1)。brief 無しのフラグ明示 build は NOTE 付き skip。

### Step 2: テンプレ展開 / 既存読込 (phase: scaffold)

kind → template 選択は `prompts/R3-template-select.md` (R3) と `schemas/template-selection.schema.json` に従う。骨格生成は `prompts/R1-scaffold.md` (R1)。`COMPOSER_MODE=atomic` の場合は combinator を kind → flag 順で適用。

### Step 3: 補助 references / 生成 (phase: references)

run 系は `templates/` / `scripts/` / `examples/`、ref 系は `references/articles-full.md`、assign 系は `references/rubric.json` / `scripts/render-findings-score.py`。本文 100 行超は `references/` へ追い出す。

**投入系 (外部システムへ書込む skill) の必須参照**: `brief.external_systems` に書込み先 (Notion/DB/API 等) がある場合、`Skill(ref-output-routing)` の Sink Contract (schema SSOT / 冪等 upsert / fail-closed) を Read し、その不変条件を `feedback_contract.criteria` と `deterministic_checks` へ反映する (build-plan の notes が要求。モデル知識での再発明は過去に品質ばらつきを生んだ既知の穴)。

### Step 3.5: 再現性トレース生成 (phase: trace-write)

`eval-log/skill-build-trace.json` を `schemas/skill-build-trace.schema.json` と `prompts/R4-trace-write.md` (R4) に従って章別記入。loop 実行系 (run/wrap/delegate) は Step 1 で導出した `feedback_contract` (inner/outer criteria を id/loop_scope/text/verify_by で記述) を **生成 SKILL.md frontmatter と trace の両方** に固定する。frontmatter は量産先が携帯する評価基準の正本、trace は再現性証跡。ref/assign は `feedback_contract.skip_reason` で N/A escape。`validate-build-trace.py` と `lint-feedback-contract.py` が kind-aware に gating する。

**要望カバレッジ (RTM)**: brief 経由 build は `requirement_coverage[]` を trace に記録する。brief の非空要求フィールド (例 `key_constraints[2]` / `boundary`) ごとに `disposition: mapped` (+`mapped_to`=反映先 criteria id/生成物) か `not_applicable` (+`reason`) を宣言する。被覆完全性と requirement_id 実在は `validate-build-trace.py` が機械検査し (段階導入: coverage 無しは WARN)、写像の意味的妥当性は Step 12 content-review (LLM 層) が判定する。

**agent/prompt 生成の provenance (route C09)**: agents/*.md・skills/*/prompts/*.md を生成/更新した build は `prompt_provenance` を trace に記録する。`prompt_creator_invocation`=true (prompt-creator 経由で本文7層を生成)・`source_contract_ref` (準拠契約: agent=`subagent-hybrid-format.md` / prompt=`seven-layer-format.md`)・`content_lint`={mode, status:PASS} (route C02 `lint-agent-prompt-content.py` の結果) の3点を持つ。`run` / `assign` が **prompt を生成する** build (`per_responsibility` 非空) では `resolved_policy=optional/skip` を禁止し `required`+provenance を強制する (生成物があるのに optional へ降格する迂回=バイパスを封鎖)。本 build が prompt を生成しない場合 (共有 prompt を消費する等、`per_responsibility` 空) は `optional` で宣言してよい (`skip` は不可)。`required` の build ではこのブロックが必須で、`validate-build-trace.py` が invocation=false・契約参照欠落・content_lint≠PASS・ブロック欠落のいずれも exit1 で止める (バイパス不能性)。実際の本文7層準拠は route C02 の CI repo 全走査が trace 非依存で独立強制する。

**route 実行レポート (plugin 一括 build のみ)**: `handoff-run-plugin-dev-plan.json` の routes を消費する build では、route 1 本の完了ごとに `eval-log/<target_plugin_slug>/build/route-<id>.json` (`schemas/route-build-report.schema.json`) へ実行レポートを書き、後続 route は依存 route のレポート (`handover`/`deviations`) を読んでから着手する。契約正本は `references/route-build-report.md`、機械検証は `scripts/validate-route-build-reports.py` (route 毎 `--route <id>` / 終端 `--complete`)。単発 build (route 外) は対象外。

### Step 4: 命名・構造 Lint (phase: scripts)

> lint 集合の正本は `$PLUGIN_ROOT/references/lint-matrix.json` (context: build-preflight / p0-gate / ci)。下記 bash ブロックはその **build-preflight 射影**であり、集合の乖離は `plugins/skill-governance-lint/scripts/lint-matrix-sync.py` が CI で fail させる (lint の増減は matrix を先に更新)。`workflow-manifest.json` は宣言的リソース (schema/prompt/reference) の正本で、lint を manifest に resource 登録はしない (責務分離)。

```bash
GOV_LINT_DIR="$(dirname "$PLUGIN_ROOT")/skill-governance-lint"
python3 "$GOV_LINT_DIR/scripts/lint-skill-name.py" "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 "$GOV_LINT_DIR/scripts/lint-skill-description.py" "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 "$GOV_LINT_DIR/scripts/lint-skill-tree.py" "$OUT_BASE/$SKILL_NAME"
python3 "$GOV_LINT_DIR/scripts/validate-frontmatter.py" "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 "$GOV_LINT_DIR/scripts/lint-script-frontmatter.py" "$OUT_BASE/$SKILL_NAME"
python3 "$GOV_LINT_DIR/scripts/lint-skill-completeness.py" "$OUT_BASE/$SKILL_NAME"  # kind別必須サポート資産(prompts/references/schemas/scripts)を実在/共有正本参照/completeness_exempt理由付きのいずれかで充足。空欄(無宣言の欠落)は exit 1
python3 "$SKILL_DIR/scripts/lint-goal-seek.py" "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 ${HARNESS_ROOT:-.}/scripts/lint-feedback-contract.py --changed-only  # loop実行系(run/wrap/delegate)のSKILL.md frontmatterに feedback_contract.criteria(inner/outer) が無ければ fail
python3 "$SKILL_DIR/scripts/lint-ssot-duplication.py" --plugin-dir "$(dirname "$OUT_BASE")"  # SSOT 重複(正本曖昧/redirect 太り/required 二重定義/本文再掲)を検出。DUP-SCHEMA-ID は exit 1
python3 "$SKILL_DIR/scripts/lint-knowledge-loop.py" "$OUT_BASE/$SKILL_NAME"  # knowledge/ がある場合のみ KL-001..008 を検査(無ければ exit0 skip)。既定 warn、CI の --strict で fail 化
python3 "$SKILL_DIR/scripts/lint-capability-graph-knowledge.py" "$OUT_BASE/$SKILL_NAME"  # brief.goal_seek.engine=task-graph の生成 harness のみ ENG-C06/ENG-C07 同梱・consult token・source_ref を検査(非 task-graph は not-applicable exit0・ENG-C08)
python3 "$SKILL_DIR/scripts/validate-build-trace.py" eval-log/skill-build-trace.json
python3 "$SKILL_DIR/scripts/validate-build-plan.py" --brief eval-log/skill-brief.json --check --skill-dir "$OUT_BASE/$SKILL_NAME"  # brief から決定論導出した必須成果物 (flags/セクション/資産) のディスク実体を突合。brief 不在は NOTE skip
python3 ${HARNESS_ROOT:-.}/scripts/lint-readme-plugin-root-portability.py  # kind=plugin / README 更新時。裸のplugin root変数・repo相対直書き・os.environ添字を検出
```

全て exit 0 でなければ Step 2 / 3.5 へ戻る。

### Step 5: 出荷用フォーク評価 (phase: trace-write, release のみ)

draftで本出荷評価は起動せず Step 12 の `deferred_to_release` へ送る。Step 12.5は現物提示後の選択、Step 12.6は選択時だけの別診断であり、本semantic obligationのPASSに流用しない。release でmachine proof後にsemantic obligationが残った場合だけ、`Skill(assign-skill-design-evaluator) target=$OUT_BASE/$SKILL_NAME` を1 context起動する。

### Step 6: ゲート判定 (phase: trace-write)

draft は決定論ゲートが通ったら Step 12.4 で `usable-draft` proofを生成する。失敗は1周だけ修復する。proof後はStep 12.45の最小guard/提示までを必須とし、Step 12.5で利用者がaccept-as-isを選べばそこで完了。Step 12.6以降は選択時だけ。release は score >= 80 かつ high=0 で完了し、判定と差し戻し履歴は trace に記録する。

### Step 7: subagent 派生 (phase: prompts-emit, `--with-subagent`)

`build-subagent.py` で `.claude/agents/<skill-name>-subagent.md` を派生 → `lint-skill-description.py` で検証。9 セクション固定構造に準拠。

### Step 7.5: prompt-creator ループ (phase: prompts-emit, `--with-prompts` or `brief.use_prompt_creator`)

`brief.responsibilities[]` の **R-id 単位** でループ。詳細は `prompts/R2-responsibility-emit.md` (R2) と `references/prompt-placement-convention.md`。

### Step 8: evaluator ペア生成 (phase: evaluator-emit, `--with-evaluator` or `brief.generate_pair_evaluator`)

公式 CLI は `render-frontmatter.py --out --pair --rubric-refs`。詳細は `references/build-steps.md#h5-evaluator-ペア生成`。

### Step 9: Hook 配線生成 (phase: scripts, `--with-hooks` or `brief.hook_events` 非空)

`scripts/hook-<name>-<event>.py` スケルトンと `settings.json` マージ案を生成。自動 merge 禁止、人間承認後の手動 merge とする。

### Step 10: ナレッジループ注入 (phase: references, `--with-knowledge` or `brief.knowledge_loop`)

生成スキルに「知識を更新・蓄積し、検索して活用し、使うほど良くなる」ループを組み込む横断 combinator。正本仕様は `Skill(ref-knowledge-loop)`(構築編+運用編)、5 段の実行手順と Loop B (harness-creator 自己適用) の昇格条件は `references/build-steps.md#h7-ナレッジループ注入の詳細手順` (本文に再掲しない=SSOT)。

### Step 10.6: task-graph engine 同梱 (phase: references, engine 既定=task-graph)

**engine 既定は task-graph**: loop kind (run/wrap/delegate) で brief が `goal_seek.engine` を明示しない場合、`validate-build-plan.py` / `render-combinators.py` が同一規則で task-graph へ default し、本 Step を適用する (量産ハーネスは既定で依存順駆動+self-reflect のタスク実行になる)。opt-out は brief に `goal_seek.engine: inline` (または `run-goal-seek`) を明示するか `--no-goal-seek`。engine は brief 由来のテンプレート変数で、`--engine=task-graph` の独立 flag は追加しない。`validate-build-plan.py` が同梱資産と profile claim を決定論導出し、`render-combinators.py --brief <brief> --materialize-task-graph-engine <skill-dir>` が実体化する。手順:

1. 解決後 engine (明示値 > loop kind 既定 task-graph) が `task-graph` でなければ本 Step を skip (`inline`/`run-goal-seek` の明示 opt-out と非 loop kind は従来どおり)。
2. 上記 materializer を実行し、`templates/task-graph-engine/scripts/` の 4 スクリプト (`ready-set-from-checklist.py`=ENG-C01 / `self-reflect-append.py`=ENG-C02 / `extract-capability-dependency-graph.py`=ENG-C06 / `record-capability-graph-knowledge.py`=ENG-C07) を `$OUT_BASE/$SKILL_NAME/scripts/` へ byte 一致で冪等コピーし、frontmatter を `engine_profile: checklist-graph` / `full_task_spec_graph: false` へ収束させる。
3. `render-combinators.py` は default-ON の with-goal-seek 内へ既に `### ゴールシーク配線（task-graph 変種）` / `### ゴールシーク検証（task-graph 変種・機械検査）` / `### dependency graph knowledge consult` の 3 サブセクションを注入済み (engine 値 `task-graph` で有効化)。追加の combinator 適用は不要。
4. `validate-build-plan.py --check` と Step 4 の `lint-capability-graph-knowledge.py` を後段検査する。engine:task-graph でなければ not-applicable、指定時は4資産欠落・テンプレートとのbyte drift・profile claim driftを fail-closed にする。

> **単一truth**: 本 engine 変種は別状態ファイル (task-graph.json 相当) を生成せず、`eval-log/<skill>-progress.json` の checklist を唯一の truth とする。ready 算出 (ENG-C01)・self-reflect 追記 (ENG-C02) は同一 checklist 配列を読み書きし、cross-surface dependency graph knowledge (ENG-C06/ENG-C07) は実行前判断用の派生情報として分離レイヤに置く。route C05 (= 本 skill 更新 component) 自身の `goal_seek.engine` は inline を維持する (builder skill の更新タスクは依存が自明で並列 dispatch も self-reflect も要さないため self-適用の利得がない・dogfooding 非適用は意図的判断)。

### Step 11: Notion スキル一覧 DB へ upsert (phase: notion-register, `--notion-register`)

build 完了後、量産プラグインを Notion の SSOT (スキル一覧 DB) に冪等登録する。**プラグイン単位 1 行**で、配下の個別 Skill はページ本文に列挙される(`scripts/notion-upsert-plugin.py` が `plugins/<plugin>/skills/` を走査)。手順:

1. `--notion-register` または `brief.notion_register=true` 未指定なら phase skip。
2. `python3 ${HARNESS_ROOT:-.}/scripts/notion-upsert-plugin.py --plugin <plugin>` 実行 (TITLE 検索→PATCH/POST 冪等)。ヒアリングシート由来なら `--hearing-sheet-id <notion-page-id>` で 1:1 relation を埋める。
3. token は `.notion-config.json` の `keychain_service` / `keychain_account` (既定: `notion-api-key.<keychain-prefix>` / `harness`) から Keychain 経由で取得する。CI では `INTAKE_ALLOW_ENV_TOKEN=1` を明示した場合のみ `$NOTION_TOKEN` を許可する。不在なら警告のみで skip。
4. 整合性は `scripts/lint-notion-relations.py` が 1:1 / N:1 不変条件 (プラグイン名重複・ヒアリング多重紐付け・改善要望の対象未設定) を CI で検証。

正本スクリプト: `scripts/notion-upsert-plugin.py` / スキーマ SSOT: `doc/notion-schema/skill-list.schema.json` (含む `feedback_protocol` SSOT)。

### Step 11.5: feedback-loop 同梱と配備 (default-ON / 再現性の核)

量産プラグインに改善要望ループを **default-ON で機械的に保証** する。詳細は `references/feedback-loop-deployment.md`。要点:

- **配備**: phase `feedback-deploy` (workflow-manifest, `default_on: true`) が `<target-plugin>/skills/run-skill-feedback` を実体コピーで冪等配備。plugin 境界を越える symlink は marketplace install で dangling するため禁止。
- **SSOT**: 発火条件 / 対話項目は `doc/notion-schema/skill-list.schema.json#feedback_protocol`。プラグイン側で再定義しない。
- **周知**: 量産先の plugin.json / README / commands / agents いずれかに `run-skill-feedback` への発火経路を必ず記載。
- **lint**: `scripts/lint-feedback-protocol.py --strict` が R1-R7 (schema/SKILL.md/upsert 三者整合 + R6 周知 + R7 配備存在) を CI で検査。違反時 merge ブロック。
- **opt-out**: `brief.no_feedback_loop: true` または CLI `--no-feedback-loop` のみ。trace.layer_decisions に理由必須。harness-creator 自身は自動除外。

### Step 12: 証拠DAG解決 (verification obligations, profile 制御)

機械 lint・意味adequacy・実走acceptanceを別々の全件workflowとして起動しない。`derive-verification-contract.py` でgraph全体のclaimを `deterministic/semantic/observational/audit` obligationへcompileし、`plan-verification-obligations.py --stage <build-plan.flags.build_stage>` がcurrent receiptと依存fingerprintから次の最小work setを決める。draft は `generate/check` だけを解決し、`stage_gate.status=usable-draft` をStep 12.4の共通proofに渡す。release でのみ、machine proof後に残った `llm_batches[]` を独立 evaluatorへ、`observational_queue[]` をGate Dへ渡す。既存 `{elegance,rubric}-verdict.json` はCI互換projectionとして維持し、`record-verification-evidence.py` でsemantic fingerprintへ束縛する。3独立analystの30思考法完全監査は `exhaustive` 明示時のaudit obligationに限定する。**正本は `references/verification-obligation-protocol.md`、legacy verdict/hook projectionは `references/content-review-protocol.md`**。

### Step 12.4: 全7 Capability共通 usable-draft proof

`workflow-manifest.json` の `usable-draft-proof` が、current kindに適用されるupstreamを1つだけDAG provenanceとして検査する。skillは `content-review`、他の6 kindは `non-skill-build-lint` の生成/lint receiptを入力に、`stage_gate.status=usable-draft AND handoff_ready=true` を共通proofとして生成する。ただしreceiptのPASS自己申告はtruth sourceにしない。親は `build-usable-draft-proof.py --verification-plan <plan> --capability-kind <kind> --capability-artifact <repo-relative-artifact> --upstream-receipt <receipt> [--upstream-receipt <receipt>] --repo-root <root> --out <proof>` を実行する。producerは正本 `validate-build-trace.py` をplugin-compositionだけ `--bundle`、他は `--manifest` で実行し、exit 0・`valid=true`・reported kind一致を要求する。skillの `run/ref/assign/wrap/delegate` subtypeはreported kind `skill` へ正規化する。proofはartifact path/sha256とvalidator id/path/sha256/mode/exit/stdout digestを束縛する。Step 12.5のgateはartifactがauthoritative target manifestの同じsha256であることを確認し、同じpublic validatorを再実行する。不一致はすべてfail-closedとし、proofを作れないkindはStep 12.5へ進まない。JSON shapeは `schemas/usable-draft-proof.schema.json`、kind集合・upstream対応・依存関係はmanifestを正本とする。

### Step 12.45: actual artifactの最小guardと提示

`usable-draft-proof` が束縛した実artifactに、class別のparse/open、secret混入、不可逆操作、破損検査だけを掛ける。PASS後、利用者にpath・開き方・試し方を先に渡す。意味評価やリリース完全性はこのhandoffの完了条件にしない。

### Step 12.5: 提示後の診断深度選択 (draftのみ)

`artifact_presented` の後にだけ `accept-as-is / light / standard / detailed` を聞く。`accept-as-is` は evaluator 0 / improver 0 でdraft handoff完了。`release` / `exhaustive` はこの質問に混ぜず、別の明示eventでだけ受け付ける。今回のように30思考法監査が依頼本文で明示済みなら、現物提示後に現在turn限定の診断選択receiptとして消費できる。そのreceiptを「将来も毎draft自動診断」と解釈しない。

### Step 12.6: 選択時のsemantic診断とuser-bounded improvement

skill subtypeに限定せず、agent/hook/command/plugin-composition/prompt/workflowを含む全7 Capabilityを共通gateへ渡す。複数component harnessでは対象全体を1つのtarget manifestへ束ねる。`build-improvement-gate.py` がdurable claim付き `status=initial-review-required` を返した場合だけ `build-review-launch.py --gate-plan <gate-plan.json> --runtime <claude-code|codex>` を実行する。launcherは `state_ref` と同じlockで `<state_ref>.launch.json` の単一active delivery leaseをatomicに取得し、`authorized=true / launch_count=1`のschema準拠requestを返す。active lease中の重複配送は `authorized=false / launch_count=0` で拒否し、leaseがstaleになった場合は同一 `request_id / idempotency_key` で再配送する。同artifact+contractの完了receiptは別runでも再利用する。この配送leaseはexactly-once resultを保証せず、古いruntime実行が生存したまま再配送される可能性を受け入れる。unsupported runtime、durable state/identity不一致はfail-closedにする。

評価Agentはread-onlyで思考リセットを先に行い、target manifestをfresh readする。30 method observationは固有rationaleと実在evidenceを持ち、`launch_request_id` / durable claim / runtimeに束縛して返す。launcherは `artifact_created_at < artifact_presented_at < semantic_evaluator_started_at` を検査し、choice前の起動を拒否する。

**承認receiptの正本**: host/runtimeが現物提示後の質問に対して実際に受け取ったuser responseだけを直列化する。評価Agent・改善Agentによる捏造、代理選択、自己発行を禁止する。`exhaustive` 確認は同じ回答から推定せず別turn eventを必須とし、本診断はrelease/audit proofに流用しない。

validated `improvement-decision.json` の `improvement_authorized=true` かつ `selected_finding_ids` 非空の場合だけ `elegant-bounded-improvement-executor` を1 worker起動する。`R6-bounded-improve.md` に従い、selected ID、manifest内path、`max_rounds`だけを変更範囲とする。`accept-draft`または選択対象0件はexecutor 0 contextで停止する。新しいfindingを発見しても範囲を拡大せずresidualへ残す。

### Step 12.8: post-improvement verification

親は `validate-improvement-result.py --gate-state <state_ref> --target-root <target_root> ...` とし、authoritative gate stateと実際の対象rootを必ず束縛してreview/decision/before-after manifest/resultを検査する。selected setの閉集合、許可pathだけのdiff、round上限、source trace、C1-C4を満たさない結果は`incomplete|blocked`で停止し、追加Agentを起動しない。release/exhaustiveへの次stage/profileは明示user decisionからだけ投影し、validatorの完了判定やfinding数から自動昇格しない。

完了時、今回だけで閉じる事実は保存しない。別案件でも判断を変えうる新規構造が証拠付きで得られた場合だけ `build-external-intelligence.py capture` を最大1件実行し、`--evidence-source` に issue/テスト系/調査元など意味的な出典を指定する。同じ失敗の自動観測は `auto-record-lesson.py` が PostToolUse から捕捉するため重ねて登録しない。対話操作の `possible_duplicate` (exit 3) は、`--merge-with` または根拠付き `--force-new --distinct-reason` で解決する。`promote` は verified 前に実行せず、`--approved-by` と `--approval-evidence-ref` を必須とする。

## 配置先

| 用途               | 出力先                                          | 正本                            |
| ------------------ | ----------------------------------------------- | ------------------------------- |
| Harness Creator 基盤 | `plugins/harness-creator/skills/<skill>/SKILL.md` | `plugins/harness-creator/skills/` |
| 他 plugin 所属     | `plugins/<plugin>/skills/<skill>/SKILL.md`      | `plugins/<plugin>/`             |

`.claude/{skills,agents,commands}` と `.codex` projectionは派生面であり直接編集しない。build/更新後はC01だけを使い、repo rootで `(1) python3 plugins/harness-creator/scripts/sync-native-surfaces.py --repo-root . --apply`、`(2) python3 plugins/harness-creator/scripts/sync-native-surfaces.py --repo-root . --check` の順に実行する。child generator、legacy sync command、別parity commandを重ねて実行しない。applyだけを完了扱いせず、同じdesired-setのcheck exit 0を最終証拠にする。

## Gotchas

- frontmatter 順序事故 / description 長文化 / ref-\* body 肥大 / scripts 内 yaml import / fork 評価の自己採点 / update 全書き換え / 全章一括ロード / `.js` `.sh` 新規生成、いずれも禁止。詳細は `references/build-steps.md`。

## Additional Resources

- frontmatter (`manifest` / `responsibility_refs` / `template_refs` / `schema_refs` / `script_refs` / `reference_refs`) は**起動契約上の主要資産のみ**を列挙する (全資産の網羅索引ではない)。全資産の索引正本はディレクトリ実体 (`scripts/` / `schemas/` / `templates/` / `prompts/` / `references/`) そのもの。`references/resource-map.yaml` は task category → 設計書章選択の progressive disclosure 索引 (+`local_artifacts` に manifest/schemas/prompts の一部) であり、これも全資産列挙ではない。`examples/` = 完成例 (minimal-ref / workflow-with-evaluator)。
- references/ 主要補助: `design-docs-index.md` (設計書索引) / `build-steps.md` (詳細手順) / `capability-manifest.schema.json` (Capability 7 kind 統一 Manifest 正本)。他の references/ は本文各 Step から個別参照。
