# harness-creator パイプライン境界契約 — build evidence / implementation-guide

本 plan (量産パイプライン 3 境界断線 E1/E2/E3 の producer/consumer 機械契約・検証ゲート・provenance 整備) を
実プラグイン (harness-creator + plugin-dev-planner) へ build した記録。全 11 component を実体化し、
決定論ゲート (validate-plan-coverage) を緑化した。**ただし現時点で実体は git 未追跡であり、
build_status は `planned` を維持する** (下記「build_status ライフサイクルと finalization」参照)。

## 実装区分の判断

plan の `constraints` は「成果物はタスク仕様書 (13 phase plan) のみ・実 build はスコープ外 (後段 builder へ委譲)」
と記す (plugin-dev-planner の既定境界)。本サイクルの指示は 2 plan の「漏れなく全て次のプラグインに反映」確認で
あり、目的達成には実コード実体が必要と判断し、plan を実プラグインへ build 済 (cross-plugin routing)。

## build した component (11 / cross-plugin)

| id | kind | build_target | 所有 plugin |
|---|---|---|---|
| C01 | skill 更新 | `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/` (R1-elicit-goal.md へ intake_json/--mode update 配線) | plugin-dev-planner |
| C02 | slash-command 更新 | `plugins/plugin-dev-planner/commands/plugin-dev-plan.md` (intake-json/mode 引数) | plugin-dev-planner |
| C03 | script 新設 | `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-plugin-goal-spec.py` (+schemas/plugin-goal-spec.schema.json へ source_intake/source_improvement 追加) | plugin-dev-planner |
| C04 | script 新設 | `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-intake-consumption.py` (tests 同梱) | plugin-dev-planner |
| C05 | script 新設 | `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-provenance-chain.py` (tests 同梱) | plugin-dev-planner |
| C06 | skill 更新 | `plugins/harness-creator/skills/run-skill-create/` (R1-elicit.md CONST_014/015 brief_path/handoff + SKILL.md 入口露出) | harness-creator |
| C07 | slash-command 更新 | `plugins/harness-creator/commands/capability-build.md` (routes[] 直接消費 --handoff/--route-id) | harness-creator |
| C08 | script 新設 | `plugins/harness-creator/scripts/check-route-component-parity.py` | harness-creator |
| C09 | script 新設 | `plugins/harness-creator/scripts/emit-improvement-handoff.py` | harness-creator |
| C10 | sub-agent 新設 | `plugins/plugin-dev-planner/agents/plugin-dev-plan-improvement-reviewer.md` | plugin-dev-planner |
| C11 | hook 新設 | `plugins/plugin-dev-planner/hooks/enforce-provenance-chain.py` (tests 同梱) | plugin-dev-planner |

付随: `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/schemas/improvement-handoff.schema.json` (C09 出力の
形状契約・**consumer 共置**)、`plugins/harness-creator/references/pipeline-boundary-contract.md` (E1/E2/E3 対応表)。

## schema 配置の正本 (elegant-review run-20260705-reflection での確定事項)

当初 inventory/handoff は phantom パス `plugins/harness-creator/schemas/improvement-handoff.schema.json` を
literal で 3 箇所 (inventory C09 side_effect_targets / inventory schemas.targets / handoff L22) 宣言し、加えて
inventory schemas.note と index.md L63 が「harness-creator 所有」と prose で誤記していた。実体・全 consumer 参照
(C01/C05/C10/C11 + emit script) は例外なく consumer skill `run-plugin-dev-plan` の `schemas/` に共置されていた
(plugin-goal-spec/phase-spec と凝集)。**実装が正・宣言が stale** と判定し、計画側 5 箇所 (上記 literal 3 + prose 2)
を実配置へ追随修正した。producer C09 は schema を import せず stdlib 自己検証ゆえ共置コスト 0 で、単一 SSOT 化により
P09 の schema-parity 二重化リスクは消失した (配置原則: cross-plugin schema は検証者近接=consumer skill 凝集配置)。

## 反映完全性の追随修正 (elegant-review run-20260705-reflection / Phase 3 write-back)

30 思考法 × 4 条件レビューで検出した「実装↔計画」乖離を双方向に整合:

- **実装→修正 (計画が正・実装が欠陥)**:
  - C07 capability-build.md: `allowed-tools` に委譲先 `Skill` が欠落し起動不能だった機能バグを `Read, Skill, Bash(python3 *)` へ修正 (Write/Edit 削除・Bash scope 化)。
  - C06 run-skill-create SKILL.md: R1-elicit.md §2.3 に反映済の `brief_path`/`handoff` が orchestrator 層 (argument-hint/arguments/入力/起動モード) に未露出で E2 パラメータが skill 引数から到達不能だった穴を露出。
- **計画→修正 (実装が正・宣言が stale)**:
  - schema 配置 5 箇所 (上記)。
  - C09 inputs/outputs: 旧語彙 (`--source/--source-path/changed_paths/residual_risks`) を実 argv/schema (`--source-kind/--source-ref/--target-plugin-slug/--plan-dir/--findings` / `source{kind,ref}/findings[]/provenance{source_intake,prev_goal_spec}`) へ追随。
  - C08 inputs: `--routes <handoff>` を実装の positional `<handoff> [--inventory]` へ追随。
  - C01 output_contract: `changed_paths/validation_commands/residual_risks` を `findings[]` へ追随。
  - C07 argument-hint: `--from-handoff/--route` を実装の `--handoff/--route-id` へ追随。

## ゲート結果

- `python3 plugins/harness-creator/scripts/validate-plan-coverage.py --all` → exit 0 (JSON 妥当・plan↔実体 completeness)。
- realized-flip シミュレーション: build_status を realized に一時 flip した状態でも `--all` が exit 0 (全 build_target /
  side_effect / required surface が実在)。schema-path 修正前に存在した phantom path (`harness-creator/schemas/`) による
  FAIL トラップは解消済。

## build_status ライフサイクルと finalization (残タスク)

現状 `build_status: planned`。全 11 実体はディスク実在だが **git 未追跡**のため、realized へ上げると clean checkout の
CI で未追跡 build_target を欠落と誤検出し FAIL する (gitignored-source-leak 型)。したがって realized 化は次を
**同一操作**で行う (proposer≠approver: 独立レビュー後、ユーザー承認で実行):

1. 両 plugin の新規/更新実体を実 plugins パスで `git add` (`.claude/` symlink 経由不可)。
2. `component-inventory.json` の `build_status` を `realized` へ、`build_status_reason` を実体化済へ更新。
3. index.md フェーズ一覧の状態を実施済へ更新。
4. commit → CI (`validate-plan-coverage --all` が realized 化で Plan B を gate 対象化)。

## スコープ外 / 先送り — 優先度付き backlog (elegant-review run-20260705-reflection 起票)

- **[high] build 終端 write-back プロトコル**: build 完了時に build_status→realized 遷移 + inventory write-back +
  git add を強制する終端 gate/hook。全 drift (schema stale / status 未 flip) の共通根 = 終端 write-back 機構の不在。
- **[medium] planned-materialized reconcile-WARN**: validate-plan-coverage に「build_status∈{planned,draft} かつ
  全 build_target 実在」を検出する reconcile 警告を追加 (skip でなく「build 済・flip 忘れ疑い」を可視化・exit0 維持)。
- **[medium] inventory↔schema field-parity lint**: 存在照合 gate が拾えない意味層 drift (inventory outputs 契約 ↔
  実 schema field 形状) を vendor byte-parity の類推で照合する専用 lint。
- **[low] index に build_target plugin 別分布表**: 単一 plugin (harness-creator) 視点では過半 (plugin-dev-planner 側
  6 component + schema) が不可視である旨を冒頭で明示。
