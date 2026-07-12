# スクリプトタイプカタログ

> **読み込み条件**: スクリプト設計時、タイプ選定時
> **相対パス**: `references/script-types-catalog.md`

---

## 概要

スクリプトタイプを複数カテゴリに分類。目的に応じて最適なタイプを選択する。

---

## カテゴリ一覧

| カテゴリ | 主要用途 |
|----------|----------|
| API/通信 | 外部サービス連携 |
| データ処理 | データ変換・加工 |
| データベース | 永続化・キャッシュ |
| 開発ツール | 開発ワークフロー |
| インフラ | 環境・運用 |
| AI/自動化 | AI連携・MCP |
| ユーティリティ | 汎用・通知 |

---

## 1. API/通信カテゴリ

### 1.1 api-client

| 項目 | 内容 |
|------|------|
| 用途 | REST/GraphQL API呼び出し |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | axios, node-fetch (Node) / requests, httpx (Python) |
| 必須環境変数 | API_URL, API_KEY (optional) |

**ユースケース**:
- 外部サービスからのデータ取得
- Webhook送信
- OAuth認証フロー

**テンプレート**: `assets/type-api-client.md` + `assets/base-node.js` / `assets/base-python.py`

### 1.2 webhook

| 項目 | 内容 |
|------|------|
| 用途 | Webhook受信・送信処理 |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | express (Node) / flask, fastapi (Python) |
| 必須環境変数 | WEBHOOK_SECRET, WEBHOOK_URL |

**ユースケース**:
- GitHub/GitLab Webhook受信
- Slack/Discord通知
- CI/CDトリガー

**テンプレート**: `assets/type-webhook.md` + `assets/base-node.js` / `assets/base-python.py`

### 1.3 scraper

| 項目 | 内容 |
|------|------|
| 用途 | Webスクレイピング |
| 推奨ランタイム | Python, Node.js |
| 主要依存 | beautifulsoup4, selenium (Python) / cheerio, puppeteer (Node) |
| 必須環境変数 | TARGET_URL |

**ユースケース**:
- Webページからのデータ抽出
- 定期的な情報収集
- コンテンツ監視

**テンプレート**: `assets/type-scraper.md` + `assets/base-python.py` / `assets/base-node.js`

---

## 2. データ処理カテゴリ

### 2.1 parser

| 項目 | 内容 |
|------|------|
| 用途 | JSON/YAML/XML/CSV変換 |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | yaml, xml2js, csv-parse (Node) / pyyaml, xmltodict, pandas (Python) |

**ユースケース**:
- 設定ファイル変換
- データフォーマット統一
- ログパース

**テンプレート**: `assets/type-parser.md` + `assets/base-node.js` / `assets/base-python.py`

### 2.2 transformer

| 項目 | 内容 |
|------|------|
| 用途 | データ形式変換・マッピング |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | lodash (Node) / pandas (Python) |

**ユースケース**:
- スキーマ変換
- データマイグレーション
- ETL処理

**テンプレート**: `assets/type-transformer.md` + `assets/base-node.js` / `assets/base-python.py`

### 2.3 aggregator

| 項目 | 内容 |
|------|------|
| 用途 | データ集約・統計処理 |
| 推奨ランタイム | Python, Node.js |
| 主要依存 | pandas, numpy (Python) / lodash (Node) |

**ユースケース**:
- レポート生成
- メトリクス集計
- 分析データ準備

**テンプレート**: `assets/type-aggregator.md` + `assets/base-python.py` / `assets/base-node.js`

### 2.4 file-processor

| 項目 | 内容 |
|------|------|
| 用途 | ファイル操作（圧縮/解凍/変換） |
| 推奨ランタイム | Bash, Node.js |
| 主要依存 | tar, gzip, zip (system) / archiver, unzipper (Node) |

**ユースケース**:
- アーカイブ作成・展開
- ファイル一括処理
- バックアップ

**テンプレート**: `assets/type-file-processor.md` + `assets/base-bash.sh` / `assets/base-node.js`

---

## 3. データベースカテゴリ

### 3.1 database

| 項目 | 内容 |
|------|------|
| 用途 | SQL実行・マイグレーション |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | pg, mysql2, better-sqlite3 (Node) / psycopg2, sqlalchemy (Python) |
| 必須環境変数 | DATABASE_URL |

**ユースケース**:
- データベースクエリ
- スキーママイグレーション
- データシーディング

**テンプレート**: `assets/type-database.md` + `assets/base-node.js` / `assets/base-python.py`

### 3.2 cache

| 項目 | 内容 |
|------|------|
| 用途 | キャッシュ操作（Redis等） |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | ioredis (Node) / redis (Python) |
| 必須環境変数 | REDIS_URL |

**ユースケース**:
- キャッシュ読み書き
- セッション管理
- レート制限

**テンプレート**: `assets/type-cache.md` + `assets/base-node.js` / `assets/base-python.py`

### 3.3 queue

| 項目 | 内容 |
|------|------|
| 用途 | メッセージキュー操作 |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | bullmq, amqplib (Node) / celery, pika (Python) |
| 必須環境変数 | QUEUE_URL |

**ユースケース**:
- 非同期ジョブ投入
- イベント発行
- ワーカー処理

**テンプレート**: `assets/type-queue.md` + `assets/base-node.js` / `assets/base-python.py`

---

## 4. 開発ツールカテゴリ

### 4.1 git-ops

| 項目 | 内容 |
|------|------|
| 用途 | Git操作 |
| 推奨ランタイム | Bash, Node.js |
| 主要依存 | git (system) / simple-git (Node) |

**ユースケース**:
- ブランチ操作
- コミット・プッシュ
- PR作成

**テンプレート**: `assets/type-git-ops.md` + `assets/base-bash.sh` / `assets/base-node.js`

### 4.2 test-runner

| 項目 | 内容 |
|------|------|
| 用途 | テスト実行・結果解析 |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | vitest, jest (Node) / pytest (Python) |

**ユースケース**:
- ユニットテスト実行
- 統合テスト
- カバレッジ収集

**テンプレート**: `assets/type-test-runner.md` + `assets/base-node.js` / `assets/base-python.py`

### 4.3 linter

| 項目 | 内容 |
|------|------|
| 用途 | リンター実行・修正 |
| 推奨ランタイム | Node.js, Bash |
| 主要依存 | eslint, prettier (Node) / ruff, black (Python) |

**ユースケース**:
- コード品質チェック
- 自動修正
- CI統合

**テンプレート**: `assets/type-linter.md` + `assets/base-node.js` / `assets/base-bash.sh`

### 4.4 formatter

| 項目 | 内容 |
|------|------|
| 用途 | コードフォーマット |
| 推奨ランタイム | Node.js, Bash |
| 主要依存 | prettier (Node) / black, isort (Python) |

**ユースケース**:
- コード整形
- 一括フォーマット
- pre-commitフック

**テンプレート**: `assets/type-formatter.md` + `assets/base-node.js` / `assets/base-bash.sh`

### 4.5 builder

| 項目 | 内容 |
|------|------|
| 用途 | ビルドツール連携 |
| 推奨ランタイム | Node.js, Bash |
| 主要依存 | vite, esbuild, webpack (Node) / make (system) |

**ユースケース**:
- プロジェクトビルド
- バンドル作成
- アセット最適化

**テンプレート**: `assets/type-builder.md` + `assets/base-node.js` / `assets/base-bash.sh`

### 4.6 deployer

| 項目 | 内容 |
|------|------|
| 用途 | デプロイ操作 |
| 推奨ランタイム | Bash, Node.js |
| 主要依存 | ssh, rsync (system) |
| 必須環境変数 | DEPLOY_HOST, DEPLOY_KEY |

**ユースケース**:
- サーバーデプロイ
- CDN更新
- 環境切り替え

**テンプレート**: `assets/type-deployer.md` + `assets/base-bash.sh` / `assets/base-node.js`

---

## 5. インフラカテゴリ

### 5.1 docker

| 項目 | 内容 |
|------|------|
| 用途 | Docker操作 |
| 推奨ランタイム | Bash |
| 主要依存 | docker, docker-compose (system) |

**ユースケース**:
- コンテナ管理
- イメージビルド
- Compose操作

**テンプレート**: `assets/type-docker.md` + `assets/base-bash.sh`

### 5.2 cloud

| 項目 | 内容 |
|------|------|
| 用途 | クラウドCLI操作 |
| 推奨ランタイム | Bash, Python |
| 主要依存 | aws-cli, gcloud, az (system) / boto3 (Python) |
| 必須環境変数 | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 等 |

**ユースケース**:
- リソース管理
- S3操作
- Lambda/Cloud Functions

**テンプレート**: `assets/type-cloud.md` + `assets/base-bash.sh` / `assets/base-python.py`

### 5.3 monitor

| 項目 | 内容 |
|------|------|
| 用途 | ヘルスチェック・監視 |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | axios (Node) / requests (Python) |

**ユースケース**:
- サービス死活監視
- メトリクス収集
- アラート発報

**テンプレート**: `assets/type-monitor.md` + `assets/base-node.js` / `assets/base-python.py`

---

## 6. AI/自動化カテゴリ

### 6.1 ai-tool

| 項目 | 内容 |
|------|------|
| 用途 | 外部AI連携 |
| 推奨ランタイム | Bash, Node.js |
| 主要依存 | claude (CLI) / openai, anthropic (packages) |
| 必須環境変数 | ANTHROPIC_API_KEY, OPENAI_API_KEY |

**ユースケース**:
- Claude CLI呼び出し
- AI API統合
- プロンプト実行

**テンプレート**: `assets/type-ai-tool.md` + `assets/base-bash.sh` / `assets/base-node.js`

### 6.2 mcp-bridge

| 項目 | 内容 |
|------|------|
| 用途 | MCPサーバー連携 |
| 推奨ランタイム | Node.js |
| 主要依存 | @modelcontextprotocol/sdk |

**ユースケース**:
- MCPツール呼び出し
- カスタムMCPサーバー構築
- ツール統合

**テンプレート**: `assets/type-mcp-bridge.md` + `assets/base-node.js`

---

## 7. ユーティリティカテゴリ

### 7.1 notification

| 項目 | 内容 |
|------|------|
| 用途 | 通知送信 |
| 推奨ランタイム | Node.js, Python |
| 主要依存 | @slack/web-api, nodemailer (Node) / slack_sdk, smtplib (Python) |
| 必須環境変数 | SLACK_TOKEN, SMTP_HOST 等 |

**ユースケース**:
- Slack通知
- メール送信
- Discord/Teamsメッセージ

**テンプレート**: `assets/type-notification.md` + `assets/base-node.js` / `assets/base-python.py`

### 7.2 shell

| 項目 | 内容 |
|------|------|
| 用途 | 汎用シェルスクリプト |
| 推奨ランタイム | Bash |
| 主要依存 | coreutils (system) |

**ユースケース**:
- システム操作
- 複合コマンド実行
- 環境セットアップ

**テンプレート**: `assets/type-shell.md` + `assets/base-bash.sh`

### 7.3 universal

| 項目 | 内容 |
|------|------|
| 用途 | 動的コード生成（任意目的） |
| 推奨ランタイム | Any |
| 主要依存 | 目的により異なる |

**ユースケース**:
- カスタムロジック
- 特殊要件対応
- プロトタイピング

**テンプレート**: `assets/type-universal.md` + `assets/base-node.js` / `assets/base-python.py` / `assets/base-bash.sh`

---

## タイプ選定フローチャート

```
要件分析
    │
    ├─ 外部サービス連携? → API/通信カテゴリ
    │   ├─ REST/GraphQL? → api-client
    │   ├─ Webhook? → webhook
    │   └─ スクレイピング? → scraper
    │
    ├─ データ加工? → データ処理カテゴリ
    │   ├─ フォーマット変換? → parser
    │   ├─ スキーマ変換? → transformer
    │   ├─ 集計? → aggregator
    │   └─ ファイル操作? → file-processor
    │
    ├─ 永続化? → データベースカテゴリ
    │   ├─ SQL? → database
    │   ├─ キャッシュ? → cache
    │   └─ キュー? → queue
    │
    ├─ 開発ワークフロー? → 開発ツールカテゴリ
    │   ├─ Git? → git-ops
    │   ├─ テスト? → test-runner
    │   ├─ 品質チェック? → linter/formatter
    │   ├─ ビルド? → builder
    │   └─ デプロイ? → deployer
    │
    ├─ インフラ操作? → インフラカテゴリ
    │   ├─ Docker? → docker
    │   ├─ クラウド? → cloud
    │   └─ 監視? → monitor
    │
    ├─ AI連携? → AI/自動化カテゴリ
    │   ├─ Claude/OpenAI? → ai-tool
    │   └─ MCP? → mcp-bridge
    │
    └─ その他 → ユーティリティカテゴリ
        ├─ 通知? → notification
        ├─ シェル? → shell
        └─ カスタム? → universal
```

---

## 関連リソース

- **ランタイムガイド**: See [runtime-guide.md](runtime-guide.md)
- **API連携パターン**: See [api-integration-patterns.md](api-integration-patterns.md)
- **変数・テンプレート**: See [variable-template-guide.md](variable-template-guide.md)
