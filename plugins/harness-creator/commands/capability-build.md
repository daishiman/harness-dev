---
description: Capability (Skill/Agent/Hook/Command/Plugin-Composition/Prompt/Workflow) を新規作成または更新する統一入口。通常 kind は run-build-skill Skill、script route は build-script-route.py に委譲する。
argument-hint: "<kind> <name> [options] | --handoff <path> [--route-id <Cxx>] [--stage draft|release] [--verification-profile incremental|exhaustive|build-only] [--max-workers N] [--max-model-actions N] [--max-live-trials N]  例: --handoff plugin-plans/x/handoff-run-plugin-dev-plan.json (既定=draft・incremental)"
allowed-tools: Read, Skill, Task, AskUserQuestion, Bash(python3 *)
name: capability-build
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
entrypoint: run-build-skill
---

# /capability-build

Capability の生成・更新を、入力形態に応じた 1 経路へ正規化する入口。常時判断するのは分岐・安全境界・完了条件だけとし、実コマンド列や task-graph 内外ループは分岐確定後に `references/capability-build-runtime-contract.md` の該当節だけを読む。

## 常時判断契約

1. `$ARGUMENTS` を解析し、下表の 1 経路だけを選ぶ。不正・曖昧・参照不在なら停止し、別経路へ推定フォールバックしない。
2. `--handoff` がある場合は JSON を Read し、route↔inventory parity を build 前に検査する。`--handoff` が無い場合だけ `<kind> <name>` を受理する。
3. 選択経路に対応する詳細節だけを遅延 Read して実行する。非選択経路、release、exhaustive の節を先読み・自動実行しない。
4. build と検証は verification obligation resolver を単一入口にし、current proof がない claim だけを実行する。決定論 proof 後に残る意味・live claim 以外で LLM/live session を起動しない。

## 分岐

| 条件 | 選択経路 | 委譲先 | 遅延 Read |
|---|---|---|---|
| `--handoff` なし | 明示モード | `skill\|agent\|hook\|command\|plugin-composition\|prompt\|workflow` は `run-build-skill`。`kind=skill` の端から端の作成は `/run-skill-create` を案内 | runtime contract の `## 振る舞い` と、選択した stage/profile 節 |
| `--handoff` あり、`--route-id` 明示、または `task_graph_ref` 不在 | 単一 route モード (E2 escape hatch / 後方互換) | skill route=`/run-skill-create`、script route=`build-script-route.py`、他7 kind=`run-build-skill` | runtime contract の `## 振る舞い` と `## 本質的なコストモデル` |
| `--handoff` あり、`task_graph_ref` あり、`--route-id` なし | task-graph route モード (既定) | TG-C01〜TG-C09 と route builder | runtime contract の `## task-graph route モード`。draft/release/profile は指定された節だけ |

受理 kind は上記7種だけで、`run/ref/assign/wrap/delegate` は skill sub-role であり capability kind として受理しない。script は route 専用で、明示モードの第8 kindにはしない。既定は `--stage draft --verification-profile incremental --max-workers 2 --max-model-actions 4 --max-live-trials 2 --live-concurrency 2`。

## 安全境界

- **fail-closed**: handoff/schema/parity、graph hash pin、lock/lease、route report、artifact/validator SHA、evidence freshness、budget gate のどれかが不正・欠落・stale なら起動または completed 宣言を止める。未実測を PASS と推定しない。
- **単一 writer**: `task-graph.json` は planner 所有で build 中に直接編集しない。runtime state は dispatcher が TG-C02 を直列呼出ししてだけ更新し、SubAgent は state を書かない。build lease の `owner_token` はメモリだけに保持し、所有者一致で renew/release する。
- **承認境界**: structural discovered-task の受理、初回診断後の改善、`release`、`exhaustive`、install/enable/hook trust/re-trust/uninstall は人間の明示承認なしに進めない。`pending_user_gate` を成功へ畳まない。
- **証拠鮮度**: proof/receipt は current target・route-local入力・checker契約・上流fingerprint・evidence SHA に束縛する。`completion-evidence.json.evidence[]` は注釈なしの実在パスだけを列挙し、実測不能は `blocked` にする。
- **実行量**: `generation_queue` / `llm_batches` / `observational_queue` に列挙された claim だけを起動する。`budget_gate=blocked` は開始前に停止し、上限を黙って緩めない。
- **native surface**: release 完了ゲートでは C01 `sync-native-surfaces.py` の apply→同一 desired-set の check だけを順に使う。legacy generator を連続実行せず、C01/TG-C08 がともに成功するまで completed にしない。

## 完了条件

- **明示 / 単一 route**: kind別の生成物と current proof が存在し、`validate-build-trace.py` または `validate-route-build-reports.py`、route モードの parity が exit 0。
- **task-graph draft**: 実体生成に必要な `generation_queue` と未解決 draft check が空、in-flight 0、`stage_gate.status=usable-draft`、`handoff_ready=true`、artifact SHA に束縛された `usable-draft-proof.json` が valid。release completion を偽装せず、利用者へ現物・試し方・未回収工程を提示する。
- **task-graph release**: task/state/report/evidence の全必須ゲート、C01 apply→check、TG-C08 `completion_gate:ok` が成立し、`build-summary.json` と TG-C09 の `task-execution-report.html` を保存してから自分の lock を release する。
- **全終了経路**: 完了・停滞・中断・異常のいずれでも、書込を伴う証跡保存と TG-C09 投影を lock release 前に行う。失敗/stall は completed にせず、構造化 blocker と TG-C08 の handback/next step をそのまま提示する。

## 遅延参照

正本: `${HC_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/capability-build-runtime-contract.md`。command ファイルからの解決先は `../references/capability-build-runtime-contract.md`。

- 入力正規化・route preflight・kind別 builder: `## 振る舞い`
- claim分類・resolver・proof reuse: `## 本質的なコストモデル (Verification-as-program)`
- draft/release と初回診断の承認境界: `## build stage (\`--stage draft|release\`)`
- profile と model/live 上限: `## 検証 profile とコスト上限`
- TG-C01〜TG-C09、内外ループ、stall/handback/native repair: `## task-graph route モード (並列 dispatch + 2 ループ)`
- E1〜E4、単一 writer、TTL/actor の不変条件: `../references/pipeline-boundary-contract.md`

## 引数

`kind name [--update] [--plugin=<name>]`、または `--handoff <path> [--route-id <Cxx>] [--stage draft|release] [--verification-profile incremental|build-only|exhaustive] [--max-workers N] [--max-model-actions N] [--max-live-trials N] [--live-concurrency N]`。`--route-id` は単一 route の段階 build / デバッグ専用 escape hatch。
