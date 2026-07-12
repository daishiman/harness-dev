---
description: プラグイン構想から index+13 フェーズファイル+component-inventory.json の plan を生成したいとき、skill/sub-agent/command/hook/script/harness/manifest を漏れなく分解したいときに使う。
argument-hint: "<plugin-concept> [--mode create|update] [--out-dir <path>] [--intake-json <path>] [--next-action-json <path>] [--improvement-handoff <path>]"
allowed-tools: Read, Write, Edit, Bash(python3 *), Skill, Agent
entrypoint: run-plugin-dev-plan
name: plugin-dev-plan
kind: command
version: 0.1.0
owner: team-platform
since: 2026-06-30
---

# /plugin-dev-plan

`$ARGUMENTS` を `run-plugin-dev-plan` に渡す薄い入口。単一 skill の作成ではなく、plugin 全体 (skill / sub-agent / slash-command / hook / script / harness-eval / manifest) の **計画 (index + 13 フェーズファイル + component-inventory.json)** を作る。実プラグイン/実コードは作らず、後段 build 先は handoff route として記録する。

## 前提条件 (再現性のための実行環境)

| 条件 | 要件 | 確認方法 |
|---|---|---|
| cwd | repo ルート (`harness/`) で起動する | lint・同梱スクリプトは repo-root 相対で動く |
| python | `python3 >= 3.10` (標準ライブラリのみ。`yaml`/`.sh`/`.js` 不使用) | `python3 --version` |
| 依存 plugin | `plugins/harness-creator/` が同梱されている (repo-bundled) | `run-skill-create` / `run-build-skill` / `run-elegant-review` / `run-goal-elicit` / `goal-seek-paradigm.md` を参照するため |
| symlink | 更新後は `make sync` で `.claude/` へ展開済み | `.claude/skills/run-plugin-dev-plan` は symlink 派生 (未同期だと旧版が動く) |
| 配布 | `distributable:false` (marketplace/bundles 非登録) | 計画専用・本 plugin は配布対象でない |

## 引数

| 引数 | 必須 | 既定 | 説明 |
|---|---|---|---|
| `plugin-concept` | yes | — | プラグイン構想 1 件 (自然文 + 任意でコンポーネント希望)。曖昧な場合も停止せず仮 slug + `open_questions` で進める |
| `--mode create\|update` | no | `create` | `update` は既存 plan への Edit 差分のみ (全書き換え禁止) |
| `--out-dir <path>` | no | `plugin-plans/<plugin-slug>/` | 計画成果物の出力先を明示上書きする (既定は可視・永続の tracked deliverable)。相対パスは repo root 基準。指定値も `goal-spec.plan_dir` に固定する |
| `--intake-json <path>` | no | — | skill-intake の `intake.json` を R1 (`intake_json`) へ渡し E1 消費させる (§0/§3 を反映し `source_intake` を記録)。未指定なら構想文のみで生成 |
| `--next-action-json <path>` | no | — | skill-intake の `next-action.json` を R1 (`next_action_json`) へ渡し、mode P の `split_candidates[]` を初期分解候補として消費させる。`--intake-json` と併用時のみ有効 |
| `--improvement-handoff <path>` | no | — | E3 改善成果物 (`improvement-handoff.json`) を R1 (`improvement_handoff`) へ渡す。`--mode update` 時のみ有効で `source_improvement` を記録 |

> ライフサイクル軸は **13 フェーズ固定** (`phase-01-requirements.md` … `phase-13-release.md`)。buildable 実体数 N は `component-inventory.json` の `components[]` 件数として現れ 13 とは独立。ユーザーが具体的本数を求めた場合は `goal-spec.requested_count` に任意記録するが gate 強制しない。

## 入力契約

- 入力 = プラグイン構想 1 件のみ。外部システム連携・secret は入力にしない。
- 分析材料 (例: UBM-Hyogo 配下) は read-only 抽出のみ。fork/複製しない。

## 実行手順 (決定論的・再現可能)

ゴールシークループ本体は `Agent` ツールで SubAgent に fork し、R 責務を 3 agent へ 1:1 dispatch する (自己完結型 7 層 SubAgent。source を authoring 正本とする)。

1. **R1 (elicitor / `isolation:inherit`)**: 構想文 + 会話履歴から目的ドリブンに `plugin-plans/<plugin-slug>/goal-spec.json` (purpose/background/goal/二値 checklist + target_plugin_slug + plan_dir) を確定する。追加質問しない。goal-spec 生成本体は `run-goal-elicit` へ委譲。
2. **R2/R3 (architect / `isolation:fork`)**: capability の各実体を 5 種の component_kind へ単一責務分解 (同一 kind 複数実体可) → 依存 DAG + envelope(plugin.json)設計 (Phase02 owner) を `component-inventory.json` に記録 → 13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md`) を §2 frontmatter + §5 本文床で生成し、各 inventory component へ core 規律 (`quality_gates` + `harness_coverage`) を焼く → `index.md` に P01..P13 phase_number 昇順の目次 + `plugin_meta` (manifest/marketplace/cachebuster/validate_plugin) + 受入確認章を焼く。
3. **R4 (evaluator / `isolation:fork` / read-only)**: assign evaluator が決定論ゲートを実行し 4 条件へ写像。NG は R3 へ差し戻す (最大 3 周)。
4. 各周回末に `<PLAN_DIR>/run-plugin-dev-plan-intermediate.jsonl` へ不変アンカー (`original_goal` ほか 5 要素) を append し、次周回の必須入力にする (ドリフト圧縮)。

## 出力成果物

構想専用 plan ディレクトリ (既定 `plugin-plans/<plugin-slug>/`・可視/永続の tracked deliverable、`$CLAUDE_PROJECT_DIR`/cwd 基準で解決) へ:

- `component-inventory.json` — buildable component 目録 (5 種検討証跡 + 各 component の build_target/依存 DAG/品質機構) + `plugin_level_surfaces.<surface>.omitted_reason` (不要サーフェスの根拠)
- `phase-01-requirements.md` … `phase-13-release.md` — 13 フェーズファイル (フェーズ 1 段階=1 ファイル・§2 frontmatter + §5 本文床。frontmatter/本文契約は `references/io-contract.md`)
- `index.md` (main) — P01..P13 phase_number 昇順目次 + コンポーネント目録の所在 + `plugin_meta` + 全体完了条件 + 受入確認
- `goal-spec.json` / `run-plugin-dev-plan-progress.json` / `run-plugin-dev-plan-intermediate.jsonl` — plugin 別 goal-seek 作業ログ
- `handoff-run-plugin-dev-plan.json` / `plan-findings.json` — plan パス + component_kind 別 builder/build_target ルーティング + envelope gap/approval reason + 達成チェックリスト + 4条件評価

## 検証 (PASS 条件 = 全 exit0)

```bash
PLAN_DIR=<plan ディレクトリ>
SKILL_DIR=plugins/plugin-dev-planner/skills/run-plugin-dev-plan
python3 "$SKILL_DIR/scripts/verify-index-topsort.py" "$PLAN_DIR"                                   # top-sort 全列挙
python3 "$SKILL_DIR/scripts/check-plugin-goal-spec.py" "$PLAN_DIR/goal-spec.json"                  # R1 goal-spec + plugin anchors
python3 "$SKILL_DIR/scripts/detect-unassigned.py" --inventory "$PLAN_DIR/component-inventory.json" --specs-dir "$PLAN_DIR"  # unassigned 0
python3 "$SKILL_DIR/scripts/check-spec-frontmatter.py" --specs-dir "$PLAN_DIR"                     # kind 別構造 + core 規律
python3 "$SKILL_DIR/scripts/check-spec-gates.py" --specs-dir "$PLAN_DIR"                           # quality_gates + harness
python3 "$SKILL_DIR/scripts/check-spec-matrix-coverage.py" --self-test                             # マトリクス table drift 検出
python3 "$SKILL_DIR/scripts/check-spec-matrix-coverage.py" "$PLAN_DIR"                             # 焼き先反映
python3 "$SKILL_DIR/scripts/check-surface-inventory.py" "$PLAN_DIR/component-inventory.json"       # 5種検討証跡 + surface 採否
python3 "$SKILL_DIR/scripts/check-build-handoff.py" "$PLAN_DIR/handoff-run-plugin-dev-plan.json"   # L3→L4 routing
```

成功条件: 上記は代表サブセット。完全な PASS 条件 (検証 12 本 = core 5 + 拡張ゲート 7・`validate-task-graph` 含む) の総数と一覧の単一正本は `skills/run-plugin-dev-plan/references/io-contract.md` §11 表 (実行可能正本=`specfm.GATE_SCRIPTS`)。task-graph はデフォルト成果物ゆえ handoff に `task_graph_ref` が常時付与され build は task-graph mode で駆動する。加えて elegant-review C1-C4 全 PASS の設計が記述されていること。形状と handoff の生きた手本は `skills/run-plugin-dev-plan/examples/sample-plan/`。

## 失敗時

- **plugin 名が曖昧**: `constraints.open_questions` に残し、仮 slug で進める (停止しない)。
- **単一 skill だけになる**: sub-agent / slash-command / hook / script component を不要と判断した根拠を goal-spec constraints または index の受入確認に明記する。plugin-level surface の不要理由は `plugin_level_surfaces.<surface>.omitted_reason` に明記する。
- **検証スクリプト未実行 / NG**: `plugin-dev-plan-evaluator` に差し戻す。3 周超過は `open_issues` に残す。
- **goal-spec schema NG**: 最大 3 周で再生成、超過時 `open_issues` へ。

## 注意

- 実プラグイン/実コードを生成しない (成果物は計画のみ)。
- 具体値を直書きせず `{{PROJECT_ROOT}}` / `$CLAUDE_PLUGIN_ROOT` / self-relative で表現する。
- `--mode update` は Edit 差分のみ。capability の実 build は `/capability-build` 系へ委譲する（harness-creator は `distributable:false` の clone 専用基盤ゆえ呼称は project-local unprefixed が正本。`<plugin>:` 形式の namespaced prefix は付けない）。
