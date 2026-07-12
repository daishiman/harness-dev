---
name: run-plugin-dev-plan
description: プラグイン構想から index+13 フェーズファイル+component-inventory.json とタスク粒度の型付き依存グラフ (task-graph) を第3の射影として生成したいとき、後段のrun-skill-createへ渡す前段の開発計画を立て build 中の discovered-task を --mode update の外ループで graph へ還流したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[plugin-concept?] [--mode create|update] [--out-dir <path>] [--intake-json <path>] [--next-action-json <path>] [--improvement-handoff <path>] [--discovered-inbox <dir>] [--approved]"
arguments: [plugin_concept, mode, out_dir, intake_json, next_action_json, improvement_handoff, discovered_inbox, approved]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3 *)
  - Skill
  - Agent
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-06-29
version: 0.2.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-06-29
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-elicit-goal.md
  - prompts/R2-decompose-components.md
  - prompts/R3-emit-specs.md
  - prompts/R4-verify-traceability.md
script_refs:
  - scripts/check-plugin-goal-spec.py
  - scripts/verify-index-topsort.py
  - scripts/detect-unassigned.py
  - scripts/check-spec-frontmatter.py
  - scripts/check-spec-gates.py
  - scripts/check-spec-matrix-coverage.py
  - scripts/check-surface-inventory.py
  - scripts/check-build-handoff.py
  - scripts/check-requirements-coverage.py
  - scripts/check-runtime-portability.py
  - scripts/check-plugin-surface-audit.py
  - scripts/check-intake-consumption.py
  - scripts/check-provenance-chain.py
  - scripts/check-upstream-pins.py
  - scripts/check-generative-fidelity.py
  - scripts/check-downstream-harness.py
  - scripts/check-harness-coverage-selfcheck.py
  - scripts/render-spec-skeleton.py
  - scripts/render-skill-brief.py
  - scripts/specfm.py
  - scripts/derive-task-graph.py
  - scripts/validate-task-graph.py
  - scripts/compute-ready-set.py
  - scripts/accept-discovered-task.py
  - scripts/apply-handoff-notes.py
  - scripts/check-plan-ledger.py
  - scripts/migrate-plan-layout.py
  - scripts/check-shape-non-regression.py
  - scripts/render-task-graph-mermaid.py
  - scripts/check-task-state-schema.py
  - scripts/render-task-execution-envelope.py
  - scripts/project-task-status.py
  - scripts/check-cycle-knowledge.py
reference_refs:
  - references/component-domain.md
  - references/phase-lifecycle.md
  - references/io-contract.md
  - references/plugin-creator-contract.md
  - references/purpose-driven-requirements.md
  - references/harness-creator-spec-reflection.md
  - references/task-graph-contract.md
  - ../../../harness-creator/references/pipeline-boundary-contract.md
  - ../../../harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md
agent_refs:
  - ../../agents/plugin-dev-plan-elicitor.md
  - ../../agents/plugin-dev-plan-architect.md
  - ../../agents/plugin-dev-plan-evaluator.md
command_refs:
  - ../../commands/plugin-dev-plan.md
hook_refs:
  - ../../hooks/hook-validate-plugin-plan.py
harness_refs:
  - ../../EVALS.json
  - ../../plugin-composition.yaml
schema_refs:
  - schemas/plugin-goal-spec.schema.json
  - schemas/phase-spec.schema.json
  - schemas/improvement-handoff.schema.json
  - schemas/task-graph.schema.json
  - schemas/discovered-task.schema.json
  - schemas/handoff-notes.schema.json
  - schemas/plan-ledger.schema.json
  - schemas/task-state.schema.json
  - schemas/task-execution-envelope.schema.json
  - schemas/knowledge-ref.schema.json
completeness_exempt:
  - "manifest: ゴールシークループで P1-P8 の手順を都度生成するため phase/gate 固定の workflow-manifest は適用外。フェーズ定義は references/phase-lifecycle.md を共有正本として参照する。"
goal_seek:
  engine: inline
  fork: subagent
  plan_dir: plugin-plans/<plugin-slug>
  spec: <PLAN_DIR>/goal-spec.json
  progress: <PLAN_DIR>/run-plugin-dev-plan-progress.json
  intermediate: <PLAN_DIR>/run-plugin-dev-plan-intermediate.jsonl
  max_loops: 5
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成した index.md が P01..P13 を phase_number 昇順で全列挙し inventory の component DAG が非循環で verify-index-topsort.py と detect-unassigned.py が未配置 0 件 (各 component が ≥1 phase の entities_covered に出現) で exit0 通過する
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 生成した 13 phase ファイルが frontmatter(PHASE_REQUIRED)+section 床を満たし各 inventory component が component_kind 別構造契約と core 規律 quality_gates(p0_lint/build_trace/elegant_review C1-C4/content_review/evaluator)+harness_coverage(block) を携帯し check-spec-frontmatter.py・check-spec-gates.py・check-spec-matrix-coverage.py が exit0 通過する
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 目的ドリブン要件定義(goal-spec)から導いた分解が UBM 固有物のみ除外し harness-creator ネイティブ規律を漏れなく伝播して run-elegant-review の C1-C4 を全 PASS する
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: 各 skill inventory component が skill-brief.schema.json 主要フィールドへ無加工で写せ後段 run-skill-create へそのまま投入できる粒度であると fork した evaluator が確認する
      verify_by: evaluator
---

# run-plugin-dev-plan

> **配布注記**: 本 skill の cross-skill `reference_refs` (`../../../harness-creator/...goal-seek-paradigm.md`) は repo-bundled 前提。plugin-dev-planner は `distributable:false` フラグで marketplace/bundles へ登録しない (`scripts/validate-plugin-completeness.py` が distributable:false プラグインの非登録を機械強制)。加えて plugin-dev-planner は `NEVER_DISTRIBUTE` denylist (`validate-plugin-completeness.py`) にも登録済みで、フラグが true へ漂流しても固有名検査が fail-closed で配布を阻止する二重ロック。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。また standalone 配布時は repo 側の schema parity テスト網 (upstream 突合) が skip され drift を検知しないため、repo-bundled 運用を既定とする。

## 目的と出力契約

プラグイン構想 1 件を、目的ドリブンで **2 軸直交** (ライフサイクル軸=13 フェーズ / 成果物実体軸=N 個の buildable component) に分解し、`run-skill-create` が段階実行できる **index(main) + 13 フェーズファイル + component-inventory.json** に変換する前段の計画スキル。フェーズファイルは上から順に読める宣言型タスク仕様 (8 節・人間向け primary deliverable)、`component-inventory.json` は buildable 実体の build routing・依存 DAG・評価基準を保持する唯一の機械 SSOT、index は plugin-creator の manifest / marketplace / cachebuster / validation 契約を `plugin_meta` で携帯する。両軸は build_target/depends_on を二重に持たず (正規化)、component は `entities_covered: [C01, ...]` の id 参照だけでフェーズに紐づく。

- **入力**: プラグイン構想 1 件 (自然文 + 任意でコンポーネント希望)、`--mode create|update`、任意 `--out-dir <path>`、任意 `--intake-json <path>` (E1)、任意 `--next-action-json <path>` (E1 の split_candidates)、任意 `--improvement-handoff <path>` (E3、`--mode update` 時のみ)、任意 `--discovered-inbox <dir>` (E4=外ループ帰路、`--mode update` 時のみ・consumer が build 中 emit した discovered-task inbox を一括受理し task-graph を改善する)、任意 `--approved` (E4 の structural 二段受理を承認するフラグ・`--discovered-inbox` と併用し内部の `accept-discovered-task.py --inbox … --approved` へ転送する)。
- **出力**: **決定論的に解決される可視・永続の plan ディレクトリ** (既定 `plugin-plans/<plugin-slug>/`・`--out-dir` で上書き・正本 `references/io-contract.md` §9) へ (1) `goal-spec.json` (2) **13 フェーズファイル `phase-01-requirements.md` … `phase-13-release.md`** (フェーズ 1 段階=1 ファイル・§2 frontmatter + §5 本文) (3) `index.md`(main) = P01..P13 を phase_number 昇順で列挙した目次 + 全体完了条件 + 受入確認 (4) **`component-inventory.json`** (buildable 実体の唯一の SSOT・品質機構を component エントリへ焼く) (5) **`task-graph.json`** (13 phase §5 + inventory `depends_on` を単一 writer 射影した依存グラフ駆動のデフォルト成果物・`derive-task-graph.py` が生成) (6) `handoff-run-plugin-dev-plan.json` (`task_graph_ref` 常時付与) / `plan-findings.json`。同一構想は常に同一出力先 (再現性)。deliverable は tracked、goal-seek transient (progress/intermediate) のみ gitignore。
- **完了条件**: 同梱 core 5 scripts / 6 invocations が全 exit0 (index が P01..P13 全列挙 + inventory DAG 非循環 / unassigned 0 件=各 component が ≥1 phase に出現 / 13 phase frontmatter+section 床 + inventory component の criteria・harness≥80% 携帯 / plugin_meta 値域 / 46 行反映 self-test + PLAN) に加え、拡張ゲート 7 本 — `check-plugin-goal-spec.py` (R1 goal-spec + plugin 固有アンカー)、`check-requirements-coverage.py` (SDD 要件トレーサビリティ=goal-spec checklist の各 id が index 完了チェックリスト/受入確認へ被覆)、`check-surface-inventory.py` (5種検討証跡 + plugin-level surface 採否)、`check-build-handoff.py` (`handoff-run-plugin-dev-plan.json` の build routing (inventory 由来) / `build_kind` / `build_args` / manifest draft / **`task_graph_ref` 必須**)、`validate-task-graph.py` (**デフォルト成果物 `task-graph.json` の DAG 非循環/orphan 0/inventory 矛盾 0/非正準拒否 の 10 検査**)、`check-runtime-portability.py` (共有 script hoist + build_target 自己完結の install 携帯性)、`check-plugin-surface-audit.py` (`plugins/` 配下の現物 surface 棚卸し) — が exit0 検証する (呼称 2 層=core 5+拡張ゲート・総数と一覧の単一正本は `references/io-contract.md` §11 表)。harness-creator 仕様 46 行と plugin-creator 物理契約が反映され、elegant-review C1-C4 全 PASS の設計が記述されている。

## 13 フェーズ写像 (ライフサイクル軸・成果物 primary deliverable)

ファイル軸は**13 フェーズ固定**。従来の機能開発 Phase 1-13 をプラグイン開発ドメインへ 1:1 写像し (UBM 固有物は DROP/REPLACE)、各フェーズ = 1 Markdown `phase-NN-<kebab>.md` を上から順に読める宣言型タスク仕様 (8 節・本文床の正本=`specfm.PHASE_BODY_SECTIONS`、人間可読表=`references/io-contract.md` §5) として出力する。正本は `references/phase-lifecycle.md` §8、id/kebab/category/gate_type の実行可能正本は `scripts/specfm.py` の `PHASE_*` dict + `schemas/phase-spec.schema.json`。

| # | id | phase_name | 日本語 | category | gate_type |
|---|---|---|---|---|---|
| 1 | P01 | requirements | 要件定義 | 要件 | none |
| 2 | P02 | design | 設計 | 設計 | none |
| 3 | P03 | design-review | 設計レビューゲート | レビュー | design-gate |
| 4 | P04 | test-design | テスト設計 | テスト | tdd-red |
| 5 | P05 | implementation | 実装 | 実装 | tdd-green |
| 6 | P06 | test-run | テスト実行 | テスト | none |
| 7 | P07 | acceptance-criteria | 受入基準判定 | 判定 | none |
| 8 | P08 | refactoring | リファクタリング | 改善 | tdd-refactor |
| 9 | P09 | quality-assurance | 品質保証 | 品質 | qa |
| 10 | P10 | final-review | 最終レビューゲート | レビュー | final-gate |
| 11 | P11 | evidence | 手動テスト検証 | 検証 | evidence |
| 12 | P12 | documentation | ドキュメント | 文書 | none |
| 13 | P13 | release | 完了(PR/リリース) | 完了 | none |

- **本数は 13 固定** (フェーズ数)。旧来の「buildable 実体の数だけ本を作る」本数論争機構は per-phase 転換で廃止した (13 はフェーズ数として固定・出力本数の設計判断ではない)。**buildable 実体数 N は `component-inventory.json` の `components[]` 件数**として現れ、13 とは独立に決まる (同一 kind 複数実体を含む・input でなく output)。
- ユーザーが「13 個」「Phase 1-13」等の具体的な本数/段数を口にした場合も、13 フェーズはフェーズ数として保つ。要求本数は `goal-spec` に任意記録できる (`requested_count`) が **gate 強制しない**。旧 Phase 1-13 の読み物ビューが要る構想では、この 13 phase ファイルがそのビューを兼ねる。
- `applicability.applicable == false` のフェーズ (典型は P08) は `{applicable: false, reason: <非空>}` で明示 N/A にでき、本文 section 床を免除される。

## 境界

入力=プラグイン構想 1 件。出力=計画 (index + 13 phase ファイル + component-inventory.json) のみ。**実プラグイン/実コードは生成せず、各 inventory component を `run-skill-create` へ委譲する**。分析材料 (UBM-Hyogo 配下) は read-only 抽出のみで fork/複製しない。配布登録動作は一切しない。4 層分離 (L0 構想 / L1 run-skill-create / L2 本スキル / L3 13 phase files+index+inventory / L4 実 build) の正本は `references/component-domain.md`。

## 主要ルール

1. **目的ドリブン (単語置換でない)**: UBM 機能開発固有物 (IPC/Cloudflare/スクショ/PR) のみ除外し、harness-creator ネイティブ規律 (TDD/評価/goal-seek/feedback-contract) は漏れなく後段へ伝播する。**DROP 列挙の正本は `references/phase-lifecycle.md` §7 読替表**、目的ドリブン精神の正本は `references/purpose-driven-requirements.md`。
2. **5 種の component_kind × N 実体を inventory へ分解 (skill 偏重を解消)**: 各 buildable 実体を skill/sub-agent/slash-command/hook/script の 5 種のいずれかへ写像し `component-inventory.json` の `components[]` に `component_kind` 宣言 + kind 別構造キーで載せる。**同一 kind の複数実体 (skill 複数・agent 複数 等) はそれぞれ独立 component** にする (1 実体 = 1 component = 1 build_target の shadow-tree 同型)。加えて plugin-level surface として harness/eval、plugin manifest、plugin-composition、references/config/assets の要否を index の `plugin_meta` と inventory の `plugin_level_surfaces` に記録する。buildable 実体数 N は対象プラグインが持つ実体の数に依存して変動し (13 フェーズ数とは独立)、実プラグインでは自然に 10 実体超になる。正本 `references/component-domain.md` / `references/io-contract.md`。
3. **2 軸を二重に持たない (正規化)**: ライフサイクル軸=13 phase ファイル (人間向け・上から順に読める)、成果物実体軸=`component-inventory.json` (機械 SSOT・build routing/DAG/品質機構)。build_target/depends_on は inventory のみが持ち、phase ファイルは再記述せず `entities_covered: [C01, ...]` の id 参照だけで component に紐づく。plugin 階層の横断規律は `index.md` の `plugin_meta` に集約する。
4. **plugin-creator 物理契約を index に集約**: `.claude-plugin/plugin.json`、manifest name と folder name の一致、TODO placeholder 禁止、personal marketplace default、policy.installation/authentication/category、update cachebuster、`validate-plugin-completeness.py` 実行を `plugin_meta` に焼く。正本 `references/plugin-creator-contract.md`。
5. **評価基準を inventory component エントリへ operationalize**: 全 buildable component が core 規律 `quality_gates`(p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + `harness_coverage`(block: min≥80/kind_pass) を携帯し `check-spec-gates.py` が inventory を走査して機械検証する。参照ポインタでなく具体キーへ焼く。条件付き規律 (feedback_contract criteria/goal_seek/prompt_layer/knowledge_loop/combinators) は kind/feature でゲート、plugin 階層規律 (manifest/marketplace/配布/bundles/PKG/governance/CI/SSOT) は index の `plugin_meta` へ焼く。焼き先正本は `references/harness-creator-spec-reflection.md` の 46 行マトリクス (operationalize 状況は `check-spec-matrix-coverage.py` が検査)。**品質ゲートだけでなく成果物評価 (purpose-acceptance) も焼く**: skill loop kind の `feedback_contract.criteria` は当該 component の goal/checklist 由来 (汎用ゲート言い換えへの退化を `check-spec-frontmatter.py` の purpose-traceability が機械検出)、index に「受入確認 (build 後の見方)」章を持たせ build 後に「組み上がった実プラグインが purpose を満たすか」を確認できる trace を通す (実行は L4・plan は契約として焼くのみ)。正本 `references/io-contract.md` §10「成果物評価の境界」。
6. **現状数値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
7. **schema parity**: skill component は `skill-brief.schema.json` 主要 14 フィールド相当へ無加工で写せる粒度にする (`references/io-contract.md`)。
8. **配置非依存・変数化・install 携帯性**: 具体値は直書きせず `{{PROJECT_ROOT}}`/`$CLAUDE_PLUGIN_ROOT`/self-relative で表現する。Python 標準ライブラリ正本 (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。共有 script は `placement_scope=plugin-root` で `plugins/<slug>/scripts/` へ hoist し (**≥2 skill consumer は plugin-root 必須**)、cross-plugin SSOT は vendoring/self-derive で携帯する (`check-runtime-portability.py` が強制・詳細は `references/io-contract.md`「配布・.claude 反映・install 携帯性」)。
9. **update は差分のみ**: `--mode update` は Edit 差分。全書き換え禁止。
10. **境界入力を契約として消費**: `--intake-json` は E1 (skill-intake→goal-spec) の producer artifact として `source_intake` に記録し、`--next-action-json` があれば `split_candidates[]` を初期分解候補として反映する。`--improvement-handoff` は E3 (改善→goal-spec) の producer artifact として `source_improvement` に記録する。境界の正本は `plugins/harness-creator/references/pipeline-boundary-contract.md`。
11. **外ループ帰路 (E4=spec-improvement loop の planner 側入口)**: `--discovered-inbox <dir>` 提供時は、consumer=harness-creator が build 中に emit した discovered-task inbox を `scripts/accept-discovered-task.py --inbox <dir> --graph <task-graph.json>` で一括ドレインし、additive を task-graph へ自動反映・structural は二段受理・不正 form は rejected 化する。**structural の受理は `--approved` フラグ提供時のみ**: 本 skill 起動時に `--approved` が渡されたら drain 呼出しへ `--approved` を転送し (`accept-discovered-task.py --inbox <dir> --graph <task-graph.json> --approved`)、未提供なら structural を pending 据置 (consumer C08 が block 継続=意図的安全弁)。この passthrough により consumer C08 の handback 主コマンド `run-plugin-dev-plan --mode update --discovered-inbox … --approved` 1 本で structural 承認まで閉じる (F1・低レベル script 直叩き不要)。ドレインが各 form へ `status`/`resulting_graph_hash` を書き戻すことで consumer C08 完了ゲートが処理済 form を素通しでき外ループが閉じる。graph が更新されると `graph_hash` が変わり、consumer は次回 build で新 pin を再消費する (再入)。E3 (build 完了後の全体改善還流) と E4 (build 中の単発タスク発見・in-flight) は別境界であり、両者は `--mode update` の同一周回で併走しうる (E3=goal-spec/checklist 再生成材料、E4=task-graph 直接反映)。改善→再実行の一巡: consumer emit(C04)→consumer block(C08)→**本 skill drain(E4)**→consumer 再消費。境界正本は `plugins/harness-creator/references/pipeline-boundary-contract.md`。

## ゴールシーク実行

> 本スキルは固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。正本: `../../../harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`。

> **形状と手順の直交 (中心原則・「ひな形」論の解)**: goal-seek paradigm が廃するのは**固定手順 (process)** であって**固定出力形状 (output shape)** ではない。両者は直交する。よって本スキルは (a) phase ファイルの **frontmatter 形状 (`PHASE_REQUIRED`) と inventory component の構造 (`STRUCTURAL_REQUIRED`) を `specfm` + lint + ゴールデン例で凍結**し (検査可能な骨格)、(b) phase 本文 prose は判断を要するため**形状を解放**しつつ、(c) 本文にも **§5 の床 (空セクションを弾く)** を敷く。手書きの穴埋め skeleton ファイルは置かない。必要な場合は `scripts/render-spec-skeleton.py` が `specfm` の正本から phase skeleton (`--phase N`) / inventory component skeleton を生成する (形状の正本は frontmatter=specfm、本文は床付きの自由記述)。つまり「ひな形が無い」のでなく「ひな形を実行可能 schema + lint + 生成 skeleton + 例として持つ」のが本方式。正本 `references/io-contract.md` §9/§10。

### ゴール (Goal)

プラグイン構想 1 件から、P01..P13 を phase_number 昇順で列挙した index と 13 フェーズファイル + `component-inventory.json` が生成され、各 skill component が skill-brief 主要フィールドと harness-creator 評価基準 (4 条件 / feedback_contract criteria / harness≥80% / content-review) を携帯し、各 component が ≥1 phase の `entities_covered` に出現 (unassigned 0 件) で完結している状態。

### 目的・背景 (Why)

既存の機能開発用 task-specification-creator は UBM 固有物に強結合で、単語置換では破綻する。固定手順は構想ごとに前提が崩れるため、ゴール (= 評価基準を携帯した計画一式) とチェックリストを到達点に固定し、手順は未達項目から都度導出する。これにより多様なプラグイン構想を同一基盤で再現性高く計画化し、harness-creator 規律を後段へ漏れなく伝播できる。

### 完了チェックリスト (Checklist)

- [ ] R1: 構想から目的駆動の plugin-goal-spec (purpose/background/goal/二値 checklist + target_plugin_slug/plan_dir。`requested_count` は任意) を確定し `check-plugin-goal-spec.py` が exit0
- [ ] E1: `--intake-json` 提供時は `source_intake` を goal-spec に記録し、`--next-action-json` 提供時は `split_candidates[]` も初期分解候補として反映し、`check-intake-consumption.py` が未反映 0 を報告した (未提供時は非適用)
- [ ] E3: `--mode update --improvement-handoff` 提供時は `findings[]` を goal-spec/checklist/plan 再生成材料へ反映し、`source_improvement` を記録した
- [ ] E4 (外ループ帰路): `--mode update --discovered-inbox` 提供時は `accept-discovered-task.py --inbox` で discovered-task inbox を一括ドレインし additive を task-graph へ反映・各 form へ status 書き戻し・structural は `--approved` 提供時のみ受理 (drain 呼出しへ `--approved` を転送)・未提供なら pending 据置 (consumer C08 が block 継続) を確認した (未提供時は非適用)
- [ ] R2: 各実体を 5 種の component_kind へ単一責務分解し `component-inventory.json` (N 実体・同一 kind 複数実体可) と依存 DAG (循環なし) + envelope(plugin.json)設計 (Phase02 owner) を導出した
- [ ] R3: 13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md`) + index(main) + `component-inventory.json` を生成した
- [ ] 各 inventory component が `component_kind` を宣言し kind 別構造契約を携帯している (skill 偏重なし)
- [ ] index が plugin-creator 物理契約 (`manifest` / `marketplace` / cachebuster / validate_plugin) を `plugin_meta` に携帯している
- [ ] 各 buildable component が core 規律 quality_gates + harness_coverage(block) を携帯している
- [ ] skill loop kind の component が feedback_contract criteria を inner+outer 各 1 件以上携帯している (現状値は焼かない)
- [ ] skill loop kind の criteria が当該 component の goal/checklist 由来 (purpose-acceptance) で汎用ゲート言い換えに退化していない + index に「受入確認 (build 後の見方)」章がある (成果物評価の operationalize)
- [ ] index が P01..P13 を phase_number 昇順で全列挙し plugin_meta (plugin 階層規律) を持つ
- [ ] 各 inventory component が ≥1 phase の `entities_covered` に出現 (orphan 0 件) し全 phase ファイルが frontmatter+section 床を満たす
- [ ] R4: 適用される harness-creator 仕様 46 行の焼き先が反映され、elegant-review C1-C4 全 PASS の設計が記述されている
- [ ] 同梱 core 5 scripts / 6 invocations (`verify-index-topsort` / `detect-unassigned` / `check-spec-frontmatter` / `check-spec-gates` / `check-spec-matrix-coverage --self-test` / `check-spec-matrix-coverage PLAN`) が全 exit0
- [ ] `check-surface-inventory.py <PLAN_DIR>/component-inventory.json` が exit0 で、5種検討証跡と plugin-level surface 採否が検証済み
- [ ] `check-build-handoff.py <PLAN_DIR>/handoff-run-plugin-dev-plan.json` が exit0 で、各 component の builder / build_kind / build_args / build_target / envelope draft/gap + **`task_graph_ref` 常時付与** が検証済み
- [ ] `derive-task-graph.py <PLAN_DIR>` でデフォルト成果物 `task-graph.json` を生成し、`validate-task-graph.py <PLAN_DIR>` が exit0 (DAG 非循環/orphan 0/inventory 矛盾 0/非正準拒否) で、build が task-graph mode で駆動される状態
- [ ] `check-runtime-portability.py <PLAN_DIR>` が exit0 で、共有 script の plugin-root hoist と build_target の plugin 内自己完結 (install 携帯性・F8) が検証済み
- [ ] plugin-dev-planner 自身の dogfood では `check-plugin-surface-audit.py --plugins-dir plugins --strict-manifest --expect-plan-ready plugin-dev-planner` が exit0 で、現物 plugin surface が横断棚卸し済み

### ゴールシークループ

正本 `goal-seek-paradigm.md` の 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し) に従う。本スキル固有の差分:

- 現状評価は上記チェックリストの未達項目を対象にし、それを埋める局面を下記「局面カタログ」から選ぶ (順序は都度判断)。
- 検証は決定論検査 (同梱 core 5 scripts / 6 invocations + 拡張ゲートの exit code・一覧の正本は `references/io-contract.md` §11 表) を優先する。
- ゲート未達は最大 3 周で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。
- ループ本体は親セッションで直接回さず `Agent` ツールで SubAgent に fork し、親へは最終成果物パスと handoff 要約のみ返す。R*.md は prompt authoring 正本 (SSOT) として維持し、plugin root の 3 agent (`agents/plugin-dev-plan-{elicitor,architect,evaluator}.md`) を **自己完結型 7 層 SubAgent**として使う (各 agent は 7 層本文を自身に保持し、frontmatter `source` + owner_skill / responsibility_id で authoring 正本 R*.md を指す。7 層準拠は `verify-completeness.py` で機械検査する)。R 責務と 1:1 対応: **elicitor=R1** (goal-spec 確定・`isolation:inherit` で会話履歴保持。R1 は推定に親 context を要するため fork しない)、**architect=R2/R3** (component 分解 + 13 phase ファイル + inventory 生成・`isolation:fork`)。**R4 (4条件と決定論ゲートの独立評価) は独立 skill `assign-plugin-plan-evaluator` (kind=assign) へ委譲し**、その R1(evaluate) を **evaluator agent** (`isolation:fork`/read-only) が fork 実行する (proposer≠approver を skill 分離で構造保証)。pipeline は elicitor→architect→(assign-plugin-plan-evaluator→)evaluator の単方向 handoff。Bash 依存検証は親が実行し結果を fork 先へ事実として渡す (背景 SubAgent は権限承認待ちで停止しうるため)。

### ゴールシーク配線

- **PLAN_DIR 解決**: R1 は `target_plugin_slug` (= `specfm.plan_slug(対象plugin名)`) と任意 `out_dir` を先に確定し、`PLAN_DIR` = `specfm.plan_output_dir(target_plugin_slug, out_dir)` で解決する。既定は `plugin-plans/<plugin-slug>/` (可視・永続)。以降の全成果物はこの plugin 別ディレクトリ配下へ置く。
- **goal-spec ロード**: `<PLAN_DIR>/goal-spec.json` をロード (無ければ R1 が会話履歴・構想文から推定生成)。R1 は `target_plugin_slug` / `out_dir` / `plan_dir` を goal-spec に書き、全 goal-seek 周回で不変にする (再現性アンカー=同一構想は常に同一 `PLAN_DIR`)。
- **周回 progress**: 各周回の checklist 状態を `<PLAN_DIR>/run-plugin-dev-plan-progress.json` に記録する。
- **中間成果物アンカー (必須)**: 各周回末に `<PLAN_DIR>/run-plugin-dev-plan-intermediate.jsonl` へ 5 要素 (`original_goal`=全周回不変・`current_goal_snapshot`・`delta_from_original`・`merged_directive_for_next`・`drift_signal`) を 1 行 append する。次周回 Step2 (手順生成) は直前の `merged_directive_for_next` と `original_goal` を必須入力として読み、AI が単独で再導出しない。初回は `progress.original_goal_hash` に SHA-256 を固定し以降全周回で照合 (改竄検知で停止)。

### ゴールシーク検証

```bash
# 中間成果物アンカーの機械検査 + plan 決定論検査 (PLAN_DIR / SKILL_DIR は cwd から解決)
python3 - "$PLAN_DIR/run-plugin-dev-plan-intermediate.jsonl" "$PLAN_DIR/run-plugin-dev-plan-progress.json" <<'PY'
import json, sys, os, hashlib
inter_path, prog_path = sys.argv[1], sys.argv[2]
required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}
if not os.path.exists(inter_path):
    assert prog.get("iteration", 0) == 0, "intermediate.jsonl 不在だが周回実行済 (anchor jsonl 必須)"
    print("intermediate.jsonl 未生成 (ループ未実行)")
else:
    lines = [l for l in open(inter_path, encoding="utf-8").read().splitlines() if l.strip()]
    first = None
    for i, line in enumerate(lines):
        e = json.loads(line)
        assert not (required_keys - e.keys()), f"intermediate[{i}] 必須キー不足"
        if i == 0:
            first = e["original_goal"]
            h = hashlib.sha256(first.encode()).hexdigest()
            assert prog.get("original_goal_hash") in (None, h), "original_goal_hash drift"
        assert e["original_goal"] == first, f"intermediate[{i}] anchor 不変性違反"
    print(f"intermediate 検査 OK: {len(lines)} 行 / anchor 不変")
PY
# plan 決定論ゲート (PLAN_DIR を計画出力先に設定して実行)
python3 "$SKILL_DIR/scripts/check-plugin-goal-spec.py" "$PLAN_DIR/goal-spec.json" # R1 goal-spec + plugin 固有アンカー
if [ -n "${INTAKE_JSON:-}" ]; then
  if [ -n "${NEXT_ACTION_JSON:-}" ]; then
    python3 "$SKILL_DIR/scripts/check-intake-consumption.py" --intake "$INTAKE_JSON" --next-action "$NEXT_ACTION_JSON" --goal-spec "$PLAN_DIR/goal-spec.json" --strict --marker-dir "$PLAN_DIR"
  else
    python3 "$SKILL_DIR/scripts/check-intake-consumption.py" --intake "$INTAKE_JSON" --goal-spec "$PLAN_DIR/goal-spec.json" --marker-dir "$PLAN_DIR"
  fi
fi
if [ -n "${IMPROVEMENT_HANDOFF:-}" ]; then
  python3 "$SKILL_DIR/scripts/check-provenance-chain.py" --goal-spec "$PLAN_DIR/goal-spec.json" --plan-dir "$PLAN_DIR" --require-improvement --marker-dir "$PLAN_DIR"
fi
python3 "$SKILL_DIR/scripts/derive-task-graph.py" "$PLAN_DIR"                      # デフォルト成果物 task-graph.json を単一 writer 射影 (§9・gate 前に生成)
python3 "$SKILL_DIR/scripts/verify-index-topsort.py" "$PLAN_DIR"
python3 "$SKILL_DIR/scripts/detect-unassigned.py" --inventory "$PLAN_DIR/component-inventory.json" --specs-dir "$PLAN_DIR"
python3 "$SKILL_DIR/scripts/check-spec-frontmatter.py" --specs-dir "$PLAN_DIR"   # component_kind 別構造 + core 規律
python3 "$SKILL_DIR/scripts/check-spec-gates.py" --specs-dir "$PLAN_DIR"          # quality_gates + harness 深掘り
python3 "$SKILL_DIR/scripts/check-spec-matrix-coverage.py" --self-test            # 46 行 table drift
python3 "$SKILL_DIR/scripts/check-spec-matrix-coverage.py" "$PLAN_DIR"            # 適用行の焼き先反映 + OP/conditional/N-A 内訳
python3 "$SKILL_DIR/scripts/check-surface-inventory.py" "$PLAN_DIR/component-inventory.json" # 5種検討証跡 + surface 採否
python3 "$SKILL_DIR/scripts/check-build-handoff.py" "$PLAN_DIR/handoff-run-plugin-dev-plan.json" # L3→L4 routing / build_kind / manifest draft / task_graph_ref 必須
python3 "$SKILL_DIR/scripts/validate-task-graph.py" "$PLAN_DIR"                    # デフォルト成果物 task-graph.json の 10 検査 (DAG/orphan/inventory 矛盾/couples(j)/非正準)
python3 "$SKILL_DIR/scripts/lint-sibling-coupling.py" "$PLAN_DIR" || true          # advisory (record-only・非ゲート): 未宣言の密結合な同一 phase 兄弟候補を提示 (couples_with 宣言忘れの安全網・exit0)
python3 "$SKILL_DIR/scripts/check-runtime-portability.py" "$PLAN_DIR"              # install 携帯性 (共有 script hoist + build_target 自己完結)
# plugin-dev-planner 自身の dogfood (現物 surface 横断棚卸し・PLAN_DIR でなく plugins/ を対象)
python3 "$SKILL_DIR/scripts/check-plugin-surface-audit.py" --plugins-dir plugins --strict-manifest --expect-plan-ready plugin-dev-planner
```

## 局面カタログ (順序は都度判断)

固定順序ではなく、ゴールシークループが未達チェックリスト項目に応じて選ぶ局面群。各局面の詳細プロンプトは `prompts/<R-id>.md` (7 層 Markdown 正本) へ委譲する。

### 局面: 目的ドリブン要件定義 (R1)

`prompts/R1-elicit-goal.md`。構想から purpose/background/goal/二値 checklist を `goal-spec.json` に固める。**purpose/background/goal/checklist の抽出は既存 `run-goal-elicit` (harness-creator・汎用 schema=goal-spec.schema.json) へ委譲し再実装しない** (DRY)。R1 は委譲結果へ plugin 固有アンカー (`target_plugin_slug` / `plan_dir`。ユーザー本数要求があれば `requested_count` を任意記録・gate 強制しない) を加え、専用 `schemas/plugin-goal-spec.schema.json` + `scripts/check-plugin-goal-spec.py` で検証する。追加質問せず仮定を constraints/open_questions に明示。正本 `references/purpose-driven-requirements.md`。

### 局面: コンポーネント分解 + envelope 設計 (R2)

`prompts/R2-decompose-components.md`。capability 列挙 + SRP 分割線 → 各実体を 5 種の component_kind のいずれかへ写像し `component_kind` 確定 (skill のみ `skill_kind` sub-field・同一 kind 複数実体可) → hierarchy/pattern → 依存 DAG を `component-inventory.json` の `components[]` に記録 (N 実体は 13 フェーズと独立の射影)。独立 builder を持つ kind は各実体 1 component、共有 script のみ独立昇格し専用 script は親へ畳む (P02)。加えて Phase02 owner として envelope(plugin.json)設計を確定し `<PLAN_DIR>/envelope-draft/plugin.json` の下地にする。plugin 階層横断規律は phase/component でなく index へ集約する。正本 `references/component-domain.md` / `references/phase-lifecycle.md`。

### 局面: 13 phase ファイル + index + inventory 生成 (R3)

`prompts/R3-emit-specs.md`。13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md`) を §2 frontmatter (`PHASE_REQUIRED`) + §5 本文 (宣言型 8 節・正本=`specfm.PHASE_BODY_SECTIONS`、人間可読表=`references/io-contract.md` §5) で生成し、各 inventory component へ core 規律 (quality_gates/harness block) + 条件付き規律 (feedback_contract/goal_seek/prompt_layer 等) を焼く。index(main) に P01..P13 phase_number 昇順の目次 + `plugin_meta` (plugin 階層規律) + 受入確認章を焼く。**phase/index/inventory 確定後に `derive-task-graph.py <PLAN_DIR>` を必ず実行してデフォルト成果物 `task-graph.json` を単一 writer 射影し、handoff へ `task_graph_ref` を常時付与する** (R3 prompt §2.5・成果物=タスクグラフ)。キー契約は `references/io-contract.md`、焼き先正本は `references/harness-creator-spec-reflection.md` の 46 行。

### 局面: トレーサビリティ検証 (R4)

`prompts/R4-verify-traceability.md` (評価ロジックの正本は独立 skill `assign-plugin-plan-evaluator` の `prompts/R1-evaluate.md` へ昇格)。**R4 は `assign-plugin-plan-evaluator` (kind=assign・user-invocable:false・context:fork) へ委譲**し、同梱 core 5 scripts / 6 invocations + 拡張ゲート (io-contract §11 表) を実行して index の P01..P13 完全性 + inventory DAG・unassigned 0 件 (orphan 0)・component_kind 別構造・quality_gates/harness・46 行 operationalize 被覆 (OP/conditional/N-A 内訳)・5種検討証跡・L3→L4 routing/build_kind/build_args・manifest draft・install 携帯性を機械検証する (自然言語突合しない)。評価器は plan を書き換えず `<PLAN_DIR>/plan-findings.json` のみ返す (proposer≠approver)。NG は R3 へ差し戻す (最大 3 周)。

## ハンドオフ (component_kind でルーティング)

routes[] は `component-inventory.json` の `components[]` から導出する (phase からではない=build は component 単位)。

- **skill component** → `run-skill-create`(L1) へ 1 本ずつ投入し L4 実 build を委譲 (run-skill-create は skill 専用。投入 brief は `scripts/render-skill-brief.py` が inventory component から決定論射影し routes[].build_args の `brief_path` で渡す)。
- **sub-agent / slash-command / hook component** → `run-build-skill` の Capability kind dispatch で生成 (sub-agent→`kind=agent` または `--with-subagent` / slash-command→`kind=command` / hook→`kind=hook` または `--with-hooks`)。run-build-skill の 7 kind = skill/agent/hook/command/plugin-composition/prompt/workflow。単独 run-skill-create 投入はしない。本 plugin 自身にも `agents/`、`commands/`、`hooks/` の実体を持たせ、単一 skill だけの plan にならないことを dogfood する。
- **script component** → **run-build-skill に `script` kind は無い**。単一 skill 専用スクリプトは親 skill の build で `scripts/` + `tests/` として生成され (独立 Capability でなく skill 付随物)、計画上は依存元 skill に紐付ける。**ただし ≥2 skill が共有する script は `placement_scope=plugin-root` で `plugins/<slug>/scripts/` へ hoist する** (routing 上の builder 語彙=`plugin-scaffold`。単一 skill 配下固定は cross-skill/単独 install で dangling するため・`check-runtime-portability.py` が強制)。`plugin-scaffold` / `parent-skill-build` は planner 上の builder 語彙としては contract-only のまま扱うが、L4 実行時は `/capability-build --handoff ... --route-id ...` が `plugins/harness-creator/scripts/build-script-route.py` へ委譲して script route を実体化し、route-build-report を書く。builder→実行手段の解決表は `references/io-contract.md` の build handoff 契約に 1 表固定。
- **harness/eval 仕様** → `EVALS.json` と `plugin-composition.yaml` に集約し、mechanical と llm_eval の両方を持つ。個別 component_kind に無理に押し込まない。
- **plugin envelope (外殻) 仕様** → N 個の capability を 1 つの plugin に束ねる**外殻の生成 owner を明示する** (skill 偏重・component だけの plan にしないための要):
  - `plugin-composition.yaml` → `run-build-skill kind=plugin-composition` または `/plugin-compose` が生成・更新する（clone 専用基盤ゆえ project-local unprefixed が正本。`<plugin>:` 形式の namespaced prefix は付けない）。
  - `.claude-plugin/plugin.json` (manifest) と `.claude-plugin/marketplace.json` (配布登録) → **現状これを単独で自動生成する skill は無い** (`plugin-compose` は composition.yaml のみ、`run-build-skill` は capability 単位)。よって index の `plugin_meta.manifest` / `plugin_meta.marketplace` を**契約 spec として焼いた上で、生成手段が未整備な点を `open_issues` に gap として必ず記録する** (「envelope 生成器 未整備 → 手動 or 将来 scaffold skill」)。生成後の検証は `scripts/validate-plugin-completeness.py` (manifest name↔folder 一致 / TODO placeholder 禁止 / distributable 整合) が担う。さらに **layperson-complete のため R3 は `<PLAN_DIR>/envelope-draft/plugin.json` に具体値入りの「貼れる」 manifest ドラフト** (manifest name↔folder 一致・TODO placeholder 無し・`entry_points` 雛形・`distributable` 整合) を **manual-apply artifact** として emit する (実 `plugins/` には書かない = build 境界を侵さない)。これにより唯一 builder を持たない envelope について、利用者は契約(値域宣言)だけでなく貼れる実体ドラフトを得て、最後の手動ステップを専門知識なしに完了できる。
  - `.mcp.json` / `.app.json` (MCP / app connector) → **現状これを単独生成する skill は無い**。要否を `component-inventory.json` の `plugin_level_surfaces.mcp_app_connector` で判定し、必要時は index の `plugin_meta.manifest` に契約を焼いて生成器未整備を `open_issues` に gap 記録する (manifest/marketplace と同じ envelope owner 明示)。不要なら `omitted_reason` を残す。MCP server が**構想の中核**となる場合は buildable taxonomy の対象外 (5 buildable に MCP スロットは無い) ゆえ「形式 PASS だが中核が空」になりうる既知制約として R1 elicitor 段で早期開示する (正本 `references/component-domain.md` の境界節)。
  - **ボイラープレート/scaffold skill の要否と capability-gap の構造化起票**: 外殻生成が頻出なら別 skill (例 `run-plugin-scaffold`) へ昇格する価値があるが、本 plan の責務は「計画」であり scaffold skill の新設自体は本 plugin のスコープ外。**envelope/MCP 生成器の不在は per-plan の freetext `open_issues` で各 plan ごとに繰り返し記録するのでなく、`/run-skill-feedback plugin-dev-planner` 経由で harness-creator への 1 回限りの構造化 capability-gap として起票し**、以後の plan は当該既知チケットを参照する (同型 gap が全 plan へ線形増殖するのを止める)。個別 plan の `open_issues` / Phase02(設計)ファイルにも要否判断を残しユーザーへ可視化する。
- **PR / feature→main は本スキルの責務外 (下流の人手操作)**: 計画(L3)も `run-skill-create`(L1 build)も PR を作らない。Phase13 (release) が `phase-lifecycle.md` §7 P13 を言及する場合も「build 完了後に人手が feature→main する (`make validate` + `pytest` 緑が前提)」という soft note に留め、評価ゲート化しない (`references/io-contract.md` §10 と整合・ユーザー意図「PR/Cloudflare/IPC は今回スコープ外」)。
- `<PLAN_DIR>/handoff-run-plugin-dev-plan.json` に**解決済み `PLAN_DIR`** (= `specfm.plan_output_dir`)・**`task_graph_ref`** (`{path: "task-graph.json", schema_version: "1.0"}`・**常時付与**して build を task-graph mode で駆動)・**`component-inventory.json` の `components[]` から導出した** routes[] (component_kind 別ルーティング・各 component の **`builder` / `build_kind` / `build_args` / `build_target`**: skill→`run-skill-create`/`build_kind=skill`、sub-agent→`run-build-skill`/`build_kind=agent`、slash-command→`run-build-skill`/`build_kind=command`、hook→`run-build-skill`/`build_kind=hook`、script→`parent-skill-build`(skill 配下) または `plugin-scaffold`(placement_scope=plugin-root の共有 script)/`build_kind=script`)・envelope owner (Phase02)・draft_path・gap/approval reason・達成チェックリストを出力する。`routes[].spec` は当該 component が実装される Phase05 ファイル `phase-05-implementation.md` を参照 (トレース用・任意)。`scripts/check-build-handoff.py` が routes↔inventory の id/component_kind/name/depends_on/builder/build_kind/build_args/build_target 一致・spec (phase ファイル) 実在・top-sort・manifest draft 実在/JSON/name/TODO 禁止・envelope gap reason・**`task_graph_ref` 実在** を検証する。これにより計画(L3)と実体(L4)は分離しつつ「どの component がどこで実体になるか」を追跡できる。本スキルは投入も build もしない。

## 注意 (Gotchas)

- **実プラグインを作らない**: 成果物は計画 (index + 13 phase ファイル + component-inventory.json) のみ。実コード/実プラグイン生成と混同しない (build は `run-skill-create` へ委譲)。
- **cwd 前提**: lint・同梱スクリプト起動は repo-root cwd 前提。skill 資産は self-relative / `$CLAUDE_PLUGIN_ROOT` で参照し、具体値を直書きしない。
- **symlink 同期**: `.claude/skills/run-plugin-dev-plan` は symlink 派生。build/更新後に `make sync` を忘れると古い版が動く。
- **非配布フラグの漂流**: `distributable:false` に加え `validate-plugin-completeness.py` の `NEVER_DISTRIBUTE` denylist へ登録済み (二重ロック)。フラグが true へ漂流しても固有名検査が fail-closed で配布を阻止する。配布化する正当な決定時のみ両方を外す。
- **scripts 規約**: Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 `yaml` import 禁止)。
- **全書き換え禁止**: `--mode update` は Edit 差分のみ。
- **Goodhart 回避**: harness 現状未達の実数値を component エントリへ焼かない (「≥80% を満たす設計」を要件化する)。
- **criteria を品質ゲートの言い換えに退化させない (成果物評価の核)**: `feedback_contract.criteria` は当該 component の goal/checklist 由来の受入条件 (purpose-acceptance) にする。「P0 lint exit0」「elegant-review C1-C4 PASS」のみだと purpose を一度も検証せず**全ゲート PASS だが purpose 未達の空プラグイン**を許す (緑のパラドクス)。`check-spec-frontmatter.py` の purpose-traceability が「goal/checklist 語彙ゼロ参照」を fail-closed で弾く (意味の正否=criterion が purpose を正しく受入検証するかは evaluator の意味判定に残す二層分離)。skeleton 生成器 (`specfm.minimal_frontmatter` / `render-spec-skeleton.py`) も purpose 由来雛形を吐くので、実 component では domain purpose へ置換する。
- **上流 (harness-creator) ドリフトの検知方針 (DEF-1/DEF-1b)**: 46 行マトリクスが引用する harness-creator 規律の鮮度は、**実ドリフト検知**で担保する — skill 増減=`test_completeness_proof_enumerates_all_harness_creator_skills`・引用 rule-ID 実在=`test_matrix_rows_cite_real_rubric_rule_ids`・`plugins/` 引用パス存在=`test_matrix_rows_cite_existing_plugin_paths` の 3 機械辺が、上流の改名/移動/skill 増減を CI 時点で fail させる。**カレンダー (last-audited から N 日) ベースの freshness ゲートは敢えて設けない** (コード無変更で CI が時限崩壊する time-bomb・アンチパターンゆえ)。表示用に複製した数値は parity test で上流実体と突合し、意味ラベル (gloss) は `references/upstream-pins.json` の hash 不一致を発火点とする event-driven 再監査 (`check-upstream-pins.py`) + `audit-trigger: quarterly` の人手再監査 + 独立 SubAgent 二段確認に委ねる (意味の機械化は Goodhart)。三層の正本 `references/harness-creator-spec-reflection.md` §14.1「機械保証の射程」。
- **上流複製の二重保持台帳**: 上流値の表示用複製 (定数・閾値・lint 集合) を新設するときは、`scripts/specfm.py` 冒頭の二重保持台帳 (定数名/upstream パス/parity test 名) と値 parity test を必ず同時追加する (台帳外の複製は禁止)。
- **hook の責務境界**: `hooks/hook-validate-plugin-plan.py` は同梱 `examples/sample-plan` (生きた手本) の drift 検出器であり、`plugin-plans/` 配下に生成される**実 plan の製品ゲートではない**。実生成 plan の 4 条件検証は `assign-plugin-plan-evaluator` (context:fork) が担う (proposer≠approver)。hook へ製品検証を背負わせない。
- **自己検証の CI 配線 (dogfooding)**: 本 plugin の tests (`skills/run-plugin-dev-plan/tests`) は `harness-creator-kit-ci.yml` の per-plugin pytest で、conformance lint は `governance-check.yml` の plugin-dev-planner block で CI 実走する (`tests/test_ci_integration.py` が配線存在を機械固定)。**PR 前提条件**: 両 skill の content-review verdict (`eval-log/plugin-dev-planner/<skill>/content-review/{elegance,rubric}-verdict.json`) を `run-elegant-review` + `assign-skill-design-evaluator` で genuine 生成すること (`lint-content-review.py --all` が fail-closed・SHA 手書換は偽装ゆえ禁止)。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本スキル資産 | `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/` |
| 計画成果物 (index + 13 phase ファイル + inventory) | 既定 **`plugin-plans/<plugin-slug>/`** (repo-root/`$CLAUDE_PROJECT_DIR` 相対・可視/永続の tracked deliverable)。`<plugin-slug>` は R1 が `goal-spec.target_plugin_slug` に固定し全周回で不変。`--out-dir <path>` で上書き。解決の正本 = `specfm.plan_output_dir()` / 規約は `references/io-contract.md` §9。goal-seek transient (progress/intermediate) のみ gitignore |
| goal-seek 作業領域 | `<PLAN_DIR>/goal-spec.json` / `<PLAN_DIR>/run-plugin-dev-plan-{progress.json,intermediate.jsonl}` / `<PLAN_DIR>/handoff-run-plugin-dev-plan.json` / `<PLAN_DIR>/plan-findings.json`。plugin ごとに同一ディレクトリへ閉じ込め、global `eval-log/` 直下へ散らさない |

`.claude/skills/run-plugin-dev-plan` は symlink 派生。build/更新後は `make sync` で `.claude/` へ展開する。

## 追加リソース

- `references/component-domain.md` — 2 軸直交 (ファイル軸=phase / build 軸=inventory) + 5 種 component_kind × N 実体定義 (script 畳み込み) + 用語集 + 4 層分離 (§4/§12)
- `references/phase-lifecycle.md` — 機能開発13フェーズ→プラグイン開発の読替表と 13 フェーズ (P01..P13) 定義 (§7/§8)
- `references/io-contract.md` — 入出力契約 (13 phase files + index + inventory sidecar) と検証接続 / evidence (§9/§10)
- `references/plugin-creator-contract.md` — `.claude-plugin/plugin.json` / marketplace / cachebuster / validation 契約
- `references/purpose-driven-requirements.md` — 目的ドリブン要件定義 (§13)
- `references/harness-creator-spec-reflection.md` — harness-creator 仕様 反映マトリクス全 46 行 (§14)
- `references/resource-map.yaml` — task category → 参照 references
- `examples/sample-plan/` — **ゴールデン出力の実例** (構想「notion-task-sync」を index.md + **13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md`)** + component-inventory.json (**11 の buildable component**: skill×3/sub-agent×3/slash-command×2/hook×1/共有 script×2) + handoff-run-plugin-dev-plan.json + envelope-draft/plugin.json で表現)。13 フェーズのライフサイクル軸と inventory の同一 kind 複数実体を実演し「kind ごと 1 本」への退化を防ぐ生きた手本。同梱の決定論ゲート (core 5 + 拡張ゲート・一覧は `references/io-contract.md` §11 表) を全 exit0 で通る。R3 生成時の形状参照・新規利用者の到達点確認に使う (`tests/test_examples_golden.py` が 13 phase + index=14 Markdown と inventory の 5-kind 網羅を回帰固定)
- `scripts/` — 検証 12 本 (呼称 2 層: core 5 + 拡張ゲート 7。一覧と総数の単一正本は `references/io-contract.md` §11 表 / `specfm.GATE_SCRIPTS`) + task-graph 導出/検証 (`derive-task-graph`/`validate-task-graph`/`compute-ready-set`) + skeleton renderer (`render-spec-skeleton`) + 共有 SSOT `specfm.py`。`tests/` に機能テスト (行カバレッジ ≥80%)
