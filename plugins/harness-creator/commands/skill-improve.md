---
description: 既存 Skill/Capability を読み、run-elegant-review → 改善実行 (elegant-improvement-executor) を自動チェインする。レビューと修正を 1 コマンドで完結させる入口。
argument-hint: "<capability-path>  例: plugins/harness-creator/skills/run-build-skill / agents/elegant-reset-observer.md"
allowed-tools: Read, Write, Edit, Bash
name: skill-improve
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
entrypoint: run-elegant-review
---

# /skill-improve

`$ARGUMENTS` の `<capability-path>` を対象に、レビュー → 改善 → 再レビューのループを最大 3 周回まで自動実行する。

## 振る舞い

1. target を読み、`run-elegant-review` を起動 (Phase 1-3)。
2. 集約 findings の severity `critical` / `high` を `elegant-improvement-executor` agent に渡し、最小パッチを適用。
3. 適用後に validation script (`validate-build-trace.py` 等) を実行。
4. C1〜C4 ゲートが PASS するか `iteration_count >= 3` まで 1-3 をループ。
5. 完了時に `changed_paths / validation_commands / residual_risks` を報告。

## 引数

| 引数 | 説明 |
|---|---|
| `capability-path` | 改善対象の skill/agent/hook/command パス (必須) |

## 失敗時

- target 不在: パス候補を表示し停止
- max iteration 超過: human_review に escalate し、未解決 finding を一覧出力
- validation script 不在: skip 理由を明示し、手動検証コマンドを提示

## 注意

- 本 command は破壊的変更を行う。事前に git commit clean を推奨。
- review のみを行いたい場合は `/capability-review` を使う。
