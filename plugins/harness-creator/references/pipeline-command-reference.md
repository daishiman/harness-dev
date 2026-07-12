# パイプライン コマンドリファレンス (表記 / 実態 / 用途)

skill-intake → plugin-dev-planner → harness-creator の3プラグイン量産パイプラインを回すために、
**あなたが打つ入口**と**内部で自動的に呼ばれるもの**を、表記・実態・用途で一覧化する。
(全エントリの実在は検証済み。分類の正本は各 `commands/*.md` frontmatter・`skills/*/SKILL.md` frontmatter・`agents/*.md`。)

## 読み方 (「実態」の凡例)

| 実態 | 意味 | あなたの操作 |
|---|---|---|
| **command** | `commands/*.md` に実体があるスラッシュコマンド | `/名前` で打つ |
| **skill (user-invocable)** | `commands/` にファイルは無いが `SKILL.md` が `user-invocable: true`。`disable-model-invocation: true` の場合 AI からは自動起動されない | `/名前` で打つ (あなた専用) |
| **subagent** | `agents/*.md`。command/skill が内部でファンアウトする | 打たない (自動) |
| **script / hook** | `scripts/*.py` / `hooks/*.py`。境界の検証・正規化 | 原則打たない (人間ブリッジの emit のみ手動) |

> **重要な共通挙動 (片方向依存)**: 各段は次段を**自動起動しない**。intake は `intake.json` を出して停止、planner は `handoff-run-plugin-dev-plan.json` を出して停止する。境界はファイルで受け渡し、次段はあなたが明示的に起動する。

---

## 1. あなたが打つ入口 (エントリ)

| 表記 | 実態 | どういうことで使うか |
|---|---|---|
| `/intake "[やりたいこと]" [--page-url <notion>]` | command → `run-skill-intake` skill (11 phase) | **ヒアリング**。非エンジニアの「やりたいこと」を5軸で聞き取り、`intake.json` を生成 (指定 Notion ページへ公開まで一気通貫)。plugin 規模と判定すると `mode P` で planner を推奨して停止 |
| `/plugin-dev-plan "<構想>" [--intake-json <p>] [--mode create\|update] [--out-dir <p>] [--improvement-handoff <p>]` | command → `run-plugin-dev-plan` skill | **タスク仕様書 (plan) 作成**。新規は `--intake-json <intake.json>`、改善は `--mode update --improvement-handoff <handoff>`。plan一式 + `handoff-run-plugin-dev-plan.json` を生成 |
| `/capability-build --handoff <handoff> [--route-id <Cxx>]` (または `<kind> <name>`) | command → `run-build-skill` skill (skill route は内部で `run-skill-create` へ dispatch) | **ハーネス構築**。既定 = `--handoff` のみで task-graph 全体を並列 dispatch + 2 ループ駆動 (planner handoff は `task_graph_ref` 常時携帯)。`--route-id <Cxx>` は単一 route だけ消費する段階 build / デバッグ用の escape hatch |
| `/capability-review <capability-path>` | command → `run-elegant-review` (dry-run) | **レビューのみ**。多視点 agent 並列レビュー→4条件ゲート判定を analyse-only で実行 (改善は実行しない) |
| `/skill-improve <capability-path>` | command → `run-elegant-review` → `elegant-improvement-executor` | **単発の直接改善 (近道)**。レビュー→その場修正を1コマンドで。※plan は再生成されないので、仕様書を正本に保ちたい改善は `/plugin-dev-plan --mode update` 経由を使う |
| `/run-skill-feedback` | **skill (user-invocable)** ※command ファイルは無い | **フィードバック収集**。利用者が「こう直してほしい」を Notion 改善要望 DB へ投入。`未対応要望数` rollup が優先度シグナルになる (改善着手は自動発火しない) |
| `python3 plugins/harness-creator/scripts/emit-improvement-handoff.py --source-kind manual --source-ref <url> --origin-request-ref <url> --target-plugin-slug <p> --plan-dir plugin-plans/<p> --findings <f.json> -o improvement-handoff.json` | **script** | **人間ブリッジ (手動)**。Notion 要望を `improvement-handoff.json` に正規化し planner の `--improvement-handoff` へ渡す。手順の正本は `feedback-to-improvement-runbook.md` |

補助コマンド (パイプライン外・必要時のみ): `/install-bundle` (bundle 一括 install) / `/plugin-compose` (plugin-composition.yaml 編集)。

---

## 2. 内部で自動的に呼ばれるもの (あなたは打たない)

| 表記 | 実態 | 呼び出し元 / 役割 |
|---|---|---|
| `skill-intake-user-profiler` / `-purpose-excavator` / `-assumption-challenger` / `-summarizer` | subagent | `/intake` が起動。プロファイル推定・目的発掘・前提挑戦・要約 |
| `run-intake-next-action` | skill | `/intake` 内で handoff 先 (A-D=harness / P=planner) を決定論的に判定 |
| `plugin-dev-plan-elicitor` / `-architect` / `-evaluator` / `-improvement-reviewer` | subagent | `/plugin-dev-plan` が起動。ゴール確定→分解→評価 (改善時は反映の意味検証) |
| `run-build-skill-subagent` | subagent | `/capability-build` が起動。brief から実体を生成 |
| `elegant-reset-observer` / `elegant-*-analyst` / `elegant-improvement-executor` | subagent | `run-elegant-review` (=`/skill-improve`・`/capability-review`) が起動 |
| `check-route-component-parity.py` | script | `/capability-build` が preflight (routes↔inventory 一致・exit0 で継続) |
| `build-script-route.py` | script | `/capability-build` の `build_kind=script` route 専用 executor (run-build-skill の 7 kind 外) |
| `render-skill-brief.py` (planner 側) | script | `/capability-build` が skill route dispatch 前の brief preflight で inventory から skill-brief を決定論射影 |
| `dispatch-ready-set.py` (TG-C01) / `sync-task-state.py` (TG-C02) / `inject-task-inputs.py` (TG-C03) / `emit-discovered-task.py` (TG-C04) / `summarize-task-progress.py` (TG-C05) / `manage-build-lease.py` (TG-C07) / `record-task-graph-knowledge.py` (TG-C08) | script | `/capability-build` の task-graph route モード (既定) が呼ぶ実行系。TG-Cxx の凡例と actor 対照表 (誰が判断し誰が機械実行するか) は `pipeline-boundary-contract.md` を正本とする |
| `check-provenance-chain.py` / `enforce-provenance-chain.py` | script / hook | `/plugin-dev-plan --mode update` の provenance 連続性を検証 (PB-C05 / PB-C11) |
| `notion-submit-improvement.py` | script | `/run-skill-feedback` が Notion 改善要望 DB へ投入 |

---

## 3. 用途 (シナリオ) ごとのコマンド列

### ① 新規作成 (ゼロから新しいプラグインを作る)

```
1. ヒアリング       /intake "<やりたいこと>" [--page-url <Notion>]        → intake.json
2. タスク仕様書作成  /plugin-dev-plan "<構想>" --intake-json <intake.json>  → handoff (task_graph_ref 常時付与) + task-graph.json
3. ハーネス構築     /capability-build --handoff <handoff>  (既定=task-graph route モード: 依存グラフ全体を自動 build+改善還流。単一 route だけは --route-id <Cxx> で明示)
```

### ② ハーネス構築だけ (仕様書が既にある状態で組む/組み直す)

```
/capability-build --handoff plugin-plans/<plugin>/handoff-run-plugin-dev-plan.json
```
ヒアリング・仕様書作成は不要 (既存 handoff を消費)。既定 = task-graph route モードで全体を build し、単一 route だけ組み直すデバッグ時のみ `--route-id <Cxx>` を付ける (escape hatch)。preflight で routes↔inventory 一致を自動検査。

### ③ 更新 (使ってみてハーネスを改善する = フィードバックサイクル)

```
1. ヒアリング(=収集)  /run-skill-feedback                                     → Notion 改善要望DB
2. 人間ブリッジ        emit-improvement-handoff.py --source-kind manual ...      → improvement-handoff.json
3. タスク仕様書作成    /plugin-dev-plan "<改善>" --mode update --improvement-handoff <handoff>
4. ハーネス構築        /capability-build --handoff <handoff>  (既定=task-graph route モード。単一 route のみは --route-id <Cxx>)
5. クローズ            Notion 対応ステータス→完了 (手動)
```
手順の正本: `feedback-to-improvement-runbook.md`。plan を介さない単発改善なら `/skill-improve <path>` 一発。

---

## 関連

- `command-usage-prompts/` — 各コマンドを30思考法エレガント検証つきで使う「用途プロンプト集」(コマンド入力→構造化プロンプト)
- `pr-creation-prompt.md` — 全変更を feature→main で PR 化する完全自律プロンプト(このrepo実コマンド版: make test / pytest / gh / git archive HEAD)
- `pipeline-boundary-contract.md` — E1/E2/E3/E4 境界契約の正本
- `feedback-to-improvement-runbook.md` — ③更新の人間ブリッジ手順の正本
- `plugins/harness-creator/skills/run-build-skill/references/feedback-loop-deployment.md` — フィードバック配備 (各量産先へ run-skill-feedback 同梱)
