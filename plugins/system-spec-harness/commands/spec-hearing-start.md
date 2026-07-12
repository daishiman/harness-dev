---
description: システム仕様の往復ヒアリングを手動起動する。--status は進捗 (マトリクス充足状況) 表示のみを行う
argument-hint: "[--resume] [--status]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
name: spec-hearing-start
kind: command
version: 0.1.0
owner: team-platform
since: 2026-07-11
entrypoint: run-system-spec-elicit
---

# /spec-hearing-start

`$ARGUMENTS` を `run-system-spec-elicit` スキル (C01) にそのまま渡す薄いラッパ。カテゴリ×プラットフォーム収集マトリクス (`spec-state.json`) を単一 transition writer 経由で埋める往復ヒアリングの手動起動口であり、ヒアリング本体のロジック・状態遷移・確定判定はすべて C01 が所有する (本 command は引数の受け渡しと `--status` 分岐のみを担う)。

Marketplace から install した場合の呼び出し名は通常 `/system-spec-harness:spec-hearing-start`。

## 振る舞い

- **通常起動 (引数なし)**: `Skill(run-system-spec-elicit, args="$ARGUMENTS")` を呼び、往復ヒアリングを新規に開始する。C01 が `spec-state.json` の収集マトリクス (canonical platform: web/mobile/tablet/desktop-windows/desktop-linux/desktop-macos) を対話で埋め、確定セルには質疑ログ参照 (`qa_ref`) を、対象外セルには理由/承認参照を付与する。
- **`--resume`**: 前回中断した地点から再開する。`Skill(run-system-spec-elicit, args="$ARGUMENTS")` に `--resume` を渡し、C01 が保存済みの `hearing_progress` を読み込んで未収集セルの続きからヒアリングを再開する (`spec-state.json` の既存確定状態は保持し、直接巻き戻さない)。
- **`--status`**: **ヒアリングは起動しない**。進捗 (`spec-state.json` のマトリクス充足状況) の表示のみを行う。C01 スキルは呼ばず、下記「--status の実行コード」で `validate-coverage-matrix.py` により充足を機械確認し、その結果を要約表示する。

## --status の実行コード

`spec-state.json` に対して収集マトリクスの網羅性を決定論検証し、充足状況だけを要約する (書き込みは一切しない)。

```bash
SSH="${CLAUDE_PLUGIN_ROOT:-plugins/system-spec-harness}"
SPEC_DIR="${CLAUDE_PROJECT_DIR:-.}/system-spec"  # spec-state.json の正本位置 (SSOT・hook 保護対象と同一)
# 収集マトリクスの網羅性を機械確認 (loop 判定: 未収集セルは許容)
python3 "$SSH/scripts/validate-coverage-matrix.py" --matrix "$SPEC_DIR/spec-state.json"
```

- exit0 = 現時点の充足条件を満たす (loop モード)。`--require-complete` を付ければ「未収集セル 0」を最終条件として追加確認できる。
- exit1 = 充足違反あり (未定義カテゴリ・欠落 platform 行・確定 qa_ref 不整合・真理値表不一致など)。stderr の `VIOLATION:` 行を要約する。
- 実行後は `spec-state.json` を Read し、カテゴリ集約状態 (確定/収集中/未着手/対象外) と未収集セル数をカテゴリ別に要約表示する。ここでヒアリングは開始しない。

## 引数

| 引数 | 説明 |
|---|---|
| (なし) | 往復ヒアリングを新規起動 (C01 スキルへ委譲) |
| `--resume` | 保存済み `hearing_progress` からヒアリングを再開 (C01 スキルへ委譲) |
| `--status` | 進捗 (マトリクス充足状況) 表示のみ。ヒアリング非起動・`spec-state.json` 無変更 |

## 注意

- 本 command は入口 (起動 + `--status` 分岐) のみを担い、`spec-state.json` の確定状態の書換えは行わない。書換えの正本は C01 (および compile 側 C03) が所有する単一 transition writer に閉じており、確定セル/対象外理由の直接巻き戻しは C11 hook が fail-closed で遮断する。
- `--status` はどのモードでも副作用なし (read-only)。`spec-state.json` が未生成の場合は先に通常起動でヒアリングを開始する旨を案内する。
