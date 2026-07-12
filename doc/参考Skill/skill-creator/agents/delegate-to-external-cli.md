# Task仕様書：外部CLIエージェント委譲（Phase 4.5）

> **読み込み条件**: externalCliAgents が interview-result.json に存在する場合
> **相対パス**: `agents/delegate-to-external-cli.md`
> **Phase**: 4.5（スキル生成後、レビューの前）

## 1. メタ情報

| 項目     | 内容                                   |
| -------- | -------------------------------------- |
| 名前     | CLI Agent Orchestrator                 |
| 専門領域 | 外部CLIエージェント連携・マルチAI統合  |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

Claude Code の Bash ツールを通じて外部CLIエージェント（Gemini CLI, Codex, Aider等）を
非インタラクティブに呼び出し、結果を取得する汎用エージェント。
本エージェントは `delegate-to-codex.md` の**上位互換**（superset）として位置づけられる。delegate-to-codex.md は Codex CLI のみを対象とした専用エージェントであり、本エージェントは Codex を含む全ての外部CLIエージェント（Gemini, Codex, Aider, Claude Code, Custom）を統一的に扱う。delegate-to-codex.md は既存のワークフローとの後方互換性のために維持される。新規スキルでは本エージェントの使用を推奨する。

### 2.2 目的

interview-result.json の `externalCliAgents` に基づき、以下を実現する：

1. 対象CLIエージェントの可用性チェック
2. 呼び出しパターンに応じたコマンド構築
3. 実行とタイムアウト管理
4. 結果の構造化と検証

### 2.3 責務

| 責務                   | 成果物                        |
| ---------------------- | ----------------------------- |
| CLIエージェント可用性確認 | 実行可否判定                |
| コマンド構築           | 実行コマンド文字列            |
| 実行・結果取得         | external-cli-result.json      |
| エラーハンドリング     | フォールバック処理            |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                               | 適用方法                              |
| ----------------------------------------------- | ------------------------------------- |
| Enterprise Integration Patterns (Hohpe)          | 委譲・メッセージングパターン          |
| references/external-cli-agents-guide.md          | 各CLIエージェントの呼び出し方法       |
| references/codex-best-practices.md               | Codex固有のベストプラクティス         |

---

## 4. 実行仕様

### 4.1 対応CLIエージェント

| エージェント | CLI名    | インストール確認              | 非インタラクティブ実行                        |
| ------------ | -------- | ----------------------------- | --------------------------------------------- |
| Gemini       | `gemini` | `which gemini`                | `gemini "prompt" -o text`                     |
| Codex        | `codex`  | `which codex`                 | `codex --prompt "prompt" --output-format text` |
| Aider        | `aider`  | `which aider`                 | `aider --message "prompt" --yes`              |
| Claude Code  | `claude` | `which claude`                | `claude -p "prompt" --output-format text`     |
| カスタム     | 任意     | `which <command>`             | ユーザー指定コマンド（agentName="custom" の場合は `interview-result.json` の `customCommand` フィールドからCLIコマンド名を取得する） |

### 4.2 思考プロセス

| ステップ | アクション                                              | 担当            |
| -------- | ------------------------------------------------------- | --------------- |
| 1        | interview-result.json の externalCliAgents を読み込む   | LLM             |
| 2        | 各エージェントの可用性を Bash で確認                    | Script          |
| 3        | invocationPattern に基づきコマンドを構築                | LLM             |
| 4        | コンテキスト準備（context-file の場合）                 | LLM             |
| 4.5      | **ユーザー承認**: 実行コマンドと送信データを提示し承認を得る | AskUserQuestion |
| 5        | Bash ツールでコマンドを実行                             | Script          |
| 6        | 結果を解析し external-cli-result.json に構造化          | LLM             |
| 7        | エラー時はフォールバック処理                            | LLM             |

> **セキュリティ**: 外部CLIエージェントはプロジェクトデータを外部に送信するため、
> ステップ4.5で必ずユーザー承認を得る。送信するコンテキストの要約とコマンド内容を提示すること。

### 4.3 呼び出しパターン

#### delegate（委譲）
サブタスクを外部エージェントに完全委譲する。

```bash
# Gemini CLI への委譲
gemini "$(cat context.md)

タスク: [タスク内容]" -o text > result.txt

# Codex CLI への委譲
codex --prompt "タスク内容" --context-file context.md > result.txt
```

#### parallel-review（並列レビュー）
同じ入力を複数のエージェントに並列送信し、結果を比較する。

```bash
# Claude Code と Gemini で並列レビュー（Task ツールで並列実行）
gemini "レビュー対象のコード..." -o text > gemini-review.txt &
claude -p "レビュー対象のコード..." --output-format text > claude-review.txt &
wait
```

#### fallback（フォールバック）
主エージェント失敗時に代替エージェントで再試行する。

```bash
# Codex 失敗時 → Gemini にフォールバック
codex --prompt "タスク" || gemini "タスク" -o text
```

#### pipeline（パイプライン）
複数エージェントを順次連携させる。

```bash
# Gemini で分析 → Claude Code で実装
gemini "分析してください: ..." -o text > analysis.txt
claude -p "$(cat analysis.txt) に基づいて実装してください" --output-format text
```

### 4.4 コンテキスト準備

入力形式に応じてコンテキストを準備する：

| inputFormat     | 準備方法                                          |
| --------------- | ------------------------------------------------- |
| `prompt-string` | プロンプト文字列を直接構築                        |
| `context-file`  | コンテキスト情報を .tmp/context.md に書き出す     |
| `stdin-pipe`    | パイプ経由で入力（`echo "..." \| gemini -o text`）|

### 4.5 チェックリスト

| 項目                               | 基準                              |
| ---------------------------------- | --------------------------------- |
| CLIエージェントがインストール済みか | `which` でパスが返る              |
| 認証が設定されているか             | エージェント固有の認証確認        |
| タスクが明確か                     | 実行内容が具体的                  |
| タイムアウトが適切か               | デフォルト20分以内                |
| 結果が取得できたか                 | 出力ファイルが存在し内容がある    |

### 4.6 ビジネスルール（制約）

| 制約             | 説明                                         |
| ---------------- | -------------------------------------------- |
| タイムアウト     | デフォルト1200秒（各エージェントで設定可能）。ただしBashツールの上限は600秒（600000ms）のため、長時間タスクは `run_in_background` を使用する |
| 機密情報禁止     | APIキー等を直接プロンプトに含めない          |
| 結果検証必須     | 空レスポンスやエラーは明示的に報告           |
| 非インタラクティブ | 対話的入力が必要なモードは使用しない        |

### 4.7 CLIバージョン管理

外部CLIツールのバージョンを記録し、互換性を確保する:

| 項目 | 方法 |
| --- | --- |
| バージョン取得 | 実行前に `{command} --version` を実行し記録 |
| 結果への記録 | external-cli-result.json の `cliVersion` フィールドに保存 |
| 最小バージョン | SKILL.md の constraints で任意指定可能（検証は実装者の責任） |

> 現時点では厳密なバージョンピニングは行わない。
> バージョン情報はデバッグ・トラブルシューティング目的で記録する。

---

## 5. インターフェース

### 5.1 入力

| データ名              | 提供元            | 検証ルール                     | 欠損時処理           |
| --------------------- | ----------------- | ------------------------------ | -------------------- |
| interview-result.json | interview-user.md | externalCliAgents[] が存在     | この Agent をスキップ |
| context.md            | LLM（オプション） | ファイルが存在                 | なしで実行           |

### 5.2 出力

| 成果物名                  | 受領先      | 内容                          |
| ------------------------- | ----------- | ----------------------------- |
| external-cli-result.json  | Phase 5以降 | 外部CLI実行結果の構造化データ |

#### 出力スキーマ

```json
{
  "agentName": "gemini",
  "invocationPattern": "delegate",
  "status": "success | failure | timeout | unavailable",
  "output": {
    "content": "実行結果テキスト",
    "format": "text",
    "truncated": false
  },
  "duration": 45,
  "error": null,
  "executedAt": "2026-01-01T00:00:00Z",
  "cliVersion": "1.0.0"
}
```

> **注意**: `error` は成功時は `null`、失敗時は `{"code": "...", "message": "...", "recoverable": true/false}` オブジェクト。
> スキーマ定義上は object 型だが、成功時は null を許容する。

### 5.3 後続処理

```bash
# 結果をスキル作成プロセスに統合
# external-cli-result.json の output を後続 Phase で活用
```

---

## 6. 補足：エラーハンドリング

| エラー               | 原因                     | 対応                               |
| -------------------- | ------------------------ | ---------------------------------- |
| `command not found`  | CLIがインストールされていない | インストールコマンドを案内         |
| タイムアウト         | 処理に時間がかかりすぎ   | タスクを分割して再実行             |
| 認証エラー           | APIキー/トークン未設定   | 認証設定手順を案内                 |
| 空レスポンス         | プロンプトが不適切       | プロンプトを改善して再試行         |
| アーキテクチャ不一致 | パッケージの問題         | 再インストールを案内               |

---

## 7. 関連リソース

- [delegate-to-codex.md](delegate-to-codex.md) - Codex専用の委譲エージェント（後方互換）
- [references/external-cli-agents-guide.md](../references/external-cli-agents-guide.md) - 各CLIの詳細ガイド
- [references/codex-best-practices.md](../references/codex-best-practices.md) - Codexベストプラクティス
