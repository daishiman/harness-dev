# イベントトリガーガイド

> **読み込み条件**: イベントトリガー設計時
> **相対パス**: `references/event-trigger-guide.md`

---

## 概要

イベントトリガーは、外部イベント（Webhook、ファイル変更、Git操作など）に応じてスキルを自動実行する機能。

### ユースケース

- Webhookによるデプロイ起動
- ファイル変更の検知と処理
- Git push/PRでのCI/CD
- 外部APIのポーリング監視

---

## トリガータイプ

### 1. Webhook

```yaml
name: deploy-trigger
trigger:
  type: webhook
  webhook:
    path: "/api/webhooks/deploy"
    method: POST
    secret: "{{env.WEBHOOK_SECRET}}"
    headers:
      X-Custom-Header: "required-value"

skill: deploy-executor
args_mapping:
  branch: "{{trigger.body.ref}}"
  commit: "{{trigger.body.after}}"
```

#### Webhook署名検証

```yaml
webhook:
  secret: "{{env.GITHUB_WEBHOOK_SECRET}}"
  # GitHub: X-Hub-Signature-256
  # GitLab: X-Gitlab-Token
  # Slack: X-Slack-Signature
```

### 2. ファイル監視

```yaml
name: csv-processor
trigger:
  type: file_watch
  file_watch:
    paths:
      - "./data/*.csv"
      - "./input/**/*.json"
    events: [create, modify]
    ignore:
      - "**/.DS_Store"
      - "**/node_modules/**"
    recursive: true

skill: file-processor
args_mapping:
  file_path: "{{trigger.path}}"
  event_type: "{{trigger.event}}"
```

#### イベントタイプ

| イベント | 説明 |
|---------|------|
| `create` | ファイル作成 |
| `modify` | ファイル変更 |
| `delete` | ファイル削除 |
| `rename` | ファイル名変更 |
| `all` | 全イベント |

### 3. Git

```yaml
name: ci-trigger
trigger:
  type: git
  git:
    repository: "./"
    events: [push, pull_request]
    branches:
      - main
      - "feature/*"

skill: ci-runner
args_mapping:
  branch: "{{trigger.ref}}"
  commit: "{{trigger.sha}}"
  author: "{{trigger.author}}"
```

### 4. HTTPポーリング

```yaml
name: api-monitor
trigger:
  type: http_poll
  http_poll:
    url: "https://api.example.com/status"
    method: GET
    headers:
      Authorization: "Bearer {{env.API_TOKEN}}"
    interval: 60  # 秒
    check_field: "$.data.updated_at"  # 変更検知用フィールド

skill: data-syncer
args_mapping:
  new_data: "{{trigger.body}}"
```

### 5. WebSocket

```yaml
name: realtime-handler
trigger:
  type: websocket
  websocket:
    url: "wss://stream.example.com/events"
    message_filter: "$.type == 'notification'"
    reconnect: true

skill: notification-processor
args_mapping:
  event: "{{trigger.message}}"
```

---

## フィルタリング

### 条件式によるフィルター

```yaml
filter:
  expression: "{{trigger.body.action}} == 'opened' && {{trigger.body.pull_request.base.ref}} == 'main'"
```

### フィールド単位のフィルター

```yaml
filter:
  fields:
    action: ["opened", "synchronize"]
    "pull_request.base.ref": "main"
```

### 複合条件

```yaml
filter:
  expression: |
    ({{trigger.body.action}} == 'opened' || {{trigger.body.action}} == 'reopened')
    && {{trigger.body.pull_request.draft}} == false
```

---

## スロットリング

### デバウンス

連続したイベントを1つにまとめる。

```yaml
throttle:
  debounce: 5000  # 5秒間イベントがなければ実行
```

### レート制限

```yaml
throttle:
  rate_limit:
    max_executions: 10
    window: 60  # 60秒間に最大10回
```

---

## 完全な設定例

### GitHub Webhook

```yaml
name: github-pr-checker
description: "PRオープン時にコードチェックを実行"

trigger:
  type: webhook
  webhook:
    path: "/webhooks/github"
    method: POST
    secret: "{{env.GITHUB_WEBHOOK_SECRET}}"

filter:
  expression: |
    {{trigger.headers['x-github-event']}} == 'pull_request'
    && {{trigger.body.action}} in ['opened', 'synchronize']

skill: code-checker
args_mapping:
  repo: "{{trigger.body.repository.full_name}}"
  pr_number: "{{trigger.body.number}}"
  head_sha: "{{trigger.body.pull_request.head.sha}}"

throttle:
  debounce: 10000  # 同一PRの連続pushをまとめる

enabled: true
```

### ファイル監視＋処理

```yaml
name: auto-formatter
description: "保存されたファイルを自動フォーマット"

trigger:
  type: file_watch
  file_watch:
    paths:
      - "src/**/*.ts"
      - "src/**/*.tsx"
    events: [modify]
    ignore:
      - "**/node_modules/**"
      - "**/*.d.ts"

filter:
  expression: "!{{trigger.path}}.endsWith('.min.js')"

skill: code-formatter
args_mapping:
  file: "{{trigger.path}}"

throttle:
  debounce: 1000  # 保存の連打を防ぐ

enabled: true
```

---

## 引数マッピング

### 基本マッピング

```yaml
args_mapping:
  # トリガーデータから直接マッピング
  file_path: "{{trigger.path}}"

  # ネストしたデータ
  user_name: "{{trigger.body.user.name}}"

  # 配列アクセス
  first_item: "{{trigger.body.items[0]}}"
```

### 変換付きマッピング

```yaml
args_mapping:
  # 文字列操作
  filename: "{{trigger.path.split('/').pop()}}"

  # 条件付き
  priority: "{{trigger.body.urgent ? 'high' : 'normal'}}"

  # デフォルト値
  author: "{{trigger.body.author || 'unknown'}}"
```

### 静的値との組み合わせ

```yaml
args_mapping:
  dynamic_value: "{{trigger.body.data}}"

# スキルに渡される引数
args:
  static_value: "fixed"
  config:
    timeout: 30
```

---

## 管理コマンド

```bash
# トリガー一覧
node scripts/register_trigger.js --list

# トリガー登録
node scripts/register_trigger.js --register trigger.yaml

# トリガー更新
node scripts/register_trigger.js --update github-pr-checker trigger.yaml

# トリガー無効化
node scripts/register_trigger.js --disable github-pr-checker

# トリガー有効化
node scripts/register_trigger.js --enable github-pr-checker

# トリガー削除
node scripts/register_trigger.js --delete github-pr-checker

# テストイベント送信
node scripts/register_trigger.js --test github-pr-checker --data '{"action":"opened"}'

# ログ確認
node scripts/register_trigger.js --logs github-pr-checker --tail 100
```

---

## セキュリティ

### Webhook署名検証

```yaml
webhook:
  secret: "{{env.WEBHOOK_SECRET}}"
  # 署名ヘッダーは自動検証
  # GitHub: X-Hub-Signature-256
  # GitLab: X-Gitlab-Token
```

### IPホワイトリスト

```yaml
webhook:
  allowed_ips:
    - "192.168.1.0/24"
    - "10.0.0.0/8"
```

### 認証ヘッダー

```yaml
webhook:
  headers:
    Authorization: "Bearer {{env.AUTH_TOKEN}}"
```

---

## ベストプラクティス

| すべきこと | 避けるべきこと |
|-----------|---------------|
| 署名検証を必ず設定 | 未検証のWebhook |
| デバウンスで連続イベント対策 | 無制限のイベント処理 |
| フィルターで不要イベントを除外 | 全イベントを処理 |
| エラー時の通知設定 | サイレント失敗 |
| 冪等なスキル設計 | 副作用のある処理 |

---

## トラブルシューティング

| 問題 | 原因 | 解決策 |
|------|------|--------|
| Webhookが受信できない | URL/ポート設定 | ngrok等で公開 |
| 署名検証失敗 | シークレット不一致 | 環境変数確認 |
| ファイル監視が効かない | パス指定ミス | globパターン確認 |
| 重複実行される | デバウンス未設定 | throttle設定追加 |

---

## 関連リソース

- [orchestration-guide.md](orchestration-guide.md) - オーケストレーション全体ガイド
- [scheduler-guide.md](scheduler-guide.md) - スケジューラー
- [schemas/event-trigger.json](../schemas/event-trigger.json) - スキーマ定義
