# 使い方ガイド

Meta Skill Creatorの詳細な使い方を説明します。

---

## 基本的な使い方

### 方法1: 自然言語で話しかける

Claude Codeに直接話しかけるだけでスキル作成を開始できます：

```
「新しいスキルを作成したい」
「〇〇を自動化するスキルを作って」
「毎日のレポート作成を自動化したい」
「このスキルのプロンプトを改善して」
```

### 方法2: コマンドで呼び出す

```
/skill-creator
```

---

## モード

Meta Skill Creatorには2つの主要なモードがあります。

### Collaborative Mode（推奨）

インタビュー形式でユーザーと対話しながらスキルを共創するモードです。

**特徴:**
- 段階的な質問でスキルの要件を明確化
- ユーザーの意図を正確に理解
- 抽象的なアイデアから具体的な実装へ

**使用例:**
```
「新しいスキルを作成したい」
→ インタビューが開始され、目的・入力・出力・制約などを質問されます
```

### Orchestrate Mode

Claude Code / Codex を使い分けて最適な実行エンジンを選択するモードです。

**特徴:**
- タスクの性質に応じた最適なエンジン選択
- 複雑なタスクの自動分割
- 効率的な処理の実現

---

## 高度な機能

### オーケストレーション

複数のスキルを組み合わせて複雑なワークフローを実現します。

**使用例:**
```
「データ取得→変換→レポート生成を連携させたい」
```

**設定ファイル例:**
```yaml
orchestration:
  name: daily-report-workflow
  steps:
    - skill: data-fetcher
      output: raw_data
    - skill: data-transformer
      input: raw_data
      output: transformed_data
    - skill: report-generator
      input: transformed_data
```

### イベントトリガー

ファイル変更、時刻、外部イベントでスキルを自動実行します。

**トリガータイプ:**
| タイプ | 説明 | 例 |
|--------|------|-----|
| file | ファイル変更を監視 | `*.md`ファイルの変更 |
| time | 時刻ベース | 毎日9:00 |
| webhook | 外部イベント | GitHub webhook |

**使用例:**
```
「READMEが更新されたら自動でドキュメントを生成したい」
```

### 並列実行

複数のタスクを同時実行して処理を高速化します。

**使用例:**
```
「複数のAPIから同時にデータを取得したい」
```

**設定ファイル例:**
```yaml
parallel:
  tasks:
    - name: fetch-users
      skill: api-fetcher
      params:
        endpoint: /users
    - name: fetch-orders
      skill: api-fetcher
      params:
        endpoint: /orders
  merge_strategy: combine
```

### スキルチェーン

スキルを連鎖させて段階的な処理フローを構築します。

**使用例:**
```
「入力検証→処理→出力フォーマットを順番に実行したい」
```

**設定ファイル例:**
```yaml
chain:
  name: data-pipeline
  steps:
    - skill: validator
      on_error: abort
    - skill: processor
      on_error: retry
    - skill: formatter
      on_error: skip
```

### スケジューラ

Cron形式で定期実行タスクを設定します。

**使用例:**
```
「毎朝9時にSlackに日報を送信したい」
```

**Cron形式:**
```
# 毎日9:00
0 9 * * *

# 毎週月曜9:00
0 9 * * 1

# 毎月1日0:00
0 0 1 * *
```

### 条件分岐フロー

実行結果に応じて処理を分岐します。

**使用例:**
```
「エラーが発生したらSlack通知、成功したらログ記録」
```

**設定ファイル例:**
```yaml
conditional:
  check: result.status
  branches:
    - condition: success
      skill: log-recorder
    - condition: error
      skill: slack-notifier
    - condition: default
      skill: fallback-handler
```

---

## ドキュメント生成機能

### API ドキュメント生成

スキルのAPI仕様書を自動生成します。

**使用例:**
```
「このスキルのAPIドキュメントを生成して」
```

**生成される内容:**
- エンドポイント一覧
- 入力パラメータ
- 出力フォーマット
- エラーコード
- 使用例

### セットアップガイド生成

インストールから使用開始までのガイドを自動生成します。

**使用例:**
```
「このスキルのセットアップガイドを作成して」
```

---

## 統合支援機能

### 公式ドキュメント取得

外部ライブラリの最新ドキュメントを自動取得します。

**使用例:**
```
「React Hooksの公式ドキュメントを参照して」
```

### 統合推奨

スキルに適したツール・ライブラリを提案します。

**使用例:**
```
「このスキルに適したテストフレームワークは？」
```

---

## スクリプトタイプ

Meta Skill Creatorは24種類のスクリプトタイプに対応しています：

| カテゴリ | タイプ |
|----------|--------|
| API | REST, GraphQL, WebSocket |
| データ処理 | ETL, Parser, Transformer |
| 開発ツール | Linter, Formatter, Generator |
| テスト | Unit, Integration, E2E |
| 通知 | Slack, Email, Webhook |
| ファイル | Reader, Writer, Watcher |

---

## ベストプラクティス

### 1. 明確な目的を伝える

```
❌ 「便利なスキルを作って」
✅ 「GitHubのIssueを自動でSlackに通知するスキルを作って」
```

### 2. 入出力を具体的に

```
❌ 「データを処理するスキル」
✅ 「CSVファイルを読み込んでJSON形式に変換するスキル」
```

### 3. 制約を事前に伝える

```
✅ 「外部APIは使わずにローカルで完結させたい」
✅ 「Node.js 18以上で動作させたい」
```

---

## トラブルシューティング

問題が発生した場合は、[TROUBLESHOOTING.md](TROUBLESHOOTING.md)を参照してください。

---

## 関連ドキュメント

- [インストールガイド](INSTALLATION.md)
- [変更履歴](CHANGELOG.md)
