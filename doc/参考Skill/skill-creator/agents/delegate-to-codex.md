# Task仕様書：Codex委譲

> **読み込み条件**: Codex実行モード選択時
> **相対パス**: `agents/delegate-to-codex.md`

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Gregor Hohpe               |
| 専門領域 | エンタープライズ統合・メッセージング |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

**スキル作成プロセス内**の特定サブタスクをCodex (GPT-5.2) に委譲し、実行結果を取得する。
必要に応じてClaude Codeが収集したコンテキストを共有し、Codexの処理能力を活用する。

**注意**: Codex実行後、結果はClaude Codeに戻り、スキル作成プロセスを継続する。
Codex専用スキルを作成するものではない。

### 2.2 目的

execution-mode.jsonに基づき、サブタスクをCodexに委譲し、結果をClaude Codeに返す。

### 2.3 責務

| 責務                   | 成果物              |
| ---------------------- | ------------------- |
| 事前条件チェック       | 実行可否判定        |
| コンテキスト準備       | context.md          |
| Codex実行              | codex-result.json   |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント              | 適用方法                   |
| ------------------------------ | -------------------------- |
| Enterprise Integration Patterns (Hohpe) | 委譲パターン              |
| references/codex-best-practices.md | Codex利用のベストプラクティス |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                   | 担当 |
| -------- | -------------------------------------------- | ---- |
| 1        | execution-mode.jsonを読み込む                | LLM  |
| 2        | 事前条件をチェック                           | Script |
| 3        | コンテキストを準備（claude-to-codexの場合）  | LLM  |
| 4        | assign_codex.jsを実行                        | Script |
| 5        | 結果を確認                                   | LLM  |
| 6        | codex-result.jsonを生成                      | LLM  |

### 4.2 事前条件チェック

| 条件 | コマンド | 期待値 |
| ---- | -------- | ------ |
| gitリポジトリ | `git rev-parse --is-inside-work-tree` | `true` |
| codex CLI | `which codex` | パスが返る |

### 4.3 チェックリスト

| 項目                     | 基準                         |
| ------------------------ | ---------------------------- |
| 事前条件を満たすか       | git + codex CLI              |
| タスクが明確か           | 実行内容が特定               |
| コンテキストが準備済みか | 必要な情報がファイル化       |
| 結果が取得できたか       | codex-response.md が存在     |

### 4.4 ビジネスルール（制約）

| 制約         | 説明                               |
| ------------ | ---------------------------------- |
| タイムアウト | 20分（1200秒）                     |
| 事前条件必須 | 未達の場合は実行しない             |
| 結果検証     | エラーの場合は明示的に報告         |

---

## 5. インターフェース

### 5.1 入力

| データ名             | 提供元                | 検証ルール           | 欠損時処理       |
| -------------------- | --------------------- | -------------------- | ---------------- |
| execution-mode.json  | interview-execution-mode | mode, taskが存在   | 前Taskに再要求   |
| context.md           | Claude Code（オプション）| ファイルが存在     | なしで実行       |

### 5.2 出力

| 成果物名             | 受領先          | 内容                           |
| -------------------- | --------------- | ------------------------------ |
| codex-result.json    | 呼び出し元ワークフロー | Codex実行結果                 |

#### 出力ディレクトリ構造

```
codex/assign-codex-{YYYYMMDD}-{task}/
├── task.md              # タスク内容
├── codex-response.md    # Codex実行結果
├── result.md            # 統合結果（Markdown）
└── result.json          # 統合結果（JSON）
```

### 5.3 前処理（Script Task - 100%精度）

```bash
# 事前条件チェック
node scripts/check_prerequisites.js

# コンテキストファイル準備（claude-to-codexの場合）
# Claude Codeが必要な情報を収集し、.tmp/context.mdに書き出す
```

### 5.4 実行

```bash
# 基本実行
node scripts/assign_codex.js \
  --task "タスク内容" \
  --output codex/output

# コンテキスト付き実行
node scripts/assign_codex.js \
  --task "タスク内容" \
  --context-file .tmp/context.md \
  --output codex/output
```

### 5.5 後続処理

```bash
# 結果確認
cat codex/output/result.json

# 結果を呼び出し元ワークフローに返却
# → codex-result.json を呼び出し元が受領
```

---

## 6. 補足：エラーハンドリング

| エラー | 原因 | 対応 |
| ------ | ---- | ---- |
| `git rev-parse failed` | gitリポジトリではない | `git init` を実行 |
| `codex: command not found` | Codex CLIがない | インストール案内 |
| `タイムアウト` | 処理に時間がかかりすぎ | タスクを分割して再実行 |
| `API error` | OpenAI APIエラー | リトライまたは報告 |

---

## 7. 補足：コンテキスト準備ガイドライン

### 含めるべき情報

```markdown
# コンテキスト

## プロジェクト概要
- プロジェクト名、目的、技術スタック

## 関連ファイル
- タスクに関連するファイルの内容（抜粋）

## 制約・要件
- コーディング規約、アーキテクチャルール

## 参考情報
- 既存の類似実装、ドキュメント
```

### 含めるべきでない情報

- 機密情報（APIキー、パスワード）
- 無関係なファイル内容
- 過度に大きなコードベース全体
