---
description: 既存 Capability に対し run-elegant-review を dry-run で起動する。多視点 agent 並列レビュー → 集約 → 4 条件ゲート判定までを analyse-only で実行する薄いラッパ (改善実行はしない)。
argument-hint: "<target-path> [scope_mode]  例: plugins/harness-creator/skills/run-build-skill skill / plugins/harness-creator plugin"
allowed-tools: Read, Bash
name: capability-review
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
entrypoint: run-elegant-review
---

# /capability-review

`$ARGUMENTS` の `<target-path>` を `run-elegant-review` Skill に `--dry-run` 付きで渡し、Phase 1 (思考リセット) → Phase 2 (並列多角的分析) → Phase 3 (改善実行) を起動する薄いラッパ。`--dry-run` のため Phase 3 は write を行わず、4 条件の verdict 判定のみを返す (analyse only)。

## 振る舞い

1. `$ARGUMENTS` を `<target-path> [scope_mode]` にパース。target が存在しなければ停止。
2. target_path を `run-elegant-review` の `target` 構造体 (plugin / skill / scope_mode) に正規化。target_type は skill/agent/hook/command/composition を自動判定。
3. `run-elegant-review` Skill を `--dry-run` 付きで起動。`scope_mode` 省略時は `skill`、`plugin` / `repo` で横断レビュー幅を拡張。
4. 集約後の C1〜C4 ゲート結果 (`verdict`) と residual_risks を報告。FAIL 時は改善実行を行う `/skill-improve <target-path>` を案内。

## 引数

| 引数 | 説明 |
|---|---|
| `target-path` | レビュー対象の絶対 or リポジトリ相対パス (必須) |
| `scope_mode` | `skill` / `plugin` / `repo` (レビュー幅、省略時 skill) |

## 失敗時

- target 不在: パス候補を表示
- target_type 判定不能: 明示指定 (`--type=skill` 等) を案内
- 収束未達 (max 3 iteration 超過): human_review に escalate

## 注意

- 改善実行は行わない (analyse only)。`run-elegant-review` を `--dry-run` で起動するため Phase 3 でも write/auto-commit されない。改善を適用したい場合は `/skill-improve` を使う。
