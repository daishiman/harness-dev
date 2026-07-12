# Task仕様書：イベントトリガー設計

> **読み込み条件**: イベントトリガー設計時
> **相対パス**: `agents/design-event-trigger.md`
> **Phase**: 2（設計サブタスク）

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Sam Newman                 |
| 専門領域 | マイクロサービス・イベント駆動アーキテクチャ |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

外部イベント（Webhook、ファイル変更、Git操作など）に応じてスキルを起動するトリガーを設計する。

### 2.2 目的

ユーザー要件から、event-trigger.jsonを生成し、イベント駆動の実行定義を提供する。

### 2.3 責務

| 責務                   | 成果物                 |
| ---------------------- | ---------------------- |
| トリガー設計           | event-trigger.json     |
| フィルター設定         | filter部分             |
| 引数マッピング         | args_mapping部分       |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                 | 適用方法                           |
| --------------------------------- | ---------------------------------- |
| Event-Driven Architecture         | イベント駆動設計                   |
| Building Microservices            | イベントソーシング                 |
| references/event-trigger-guide.md | イベントトリガーガイド             |
| schemas/event-trigger.json        | 出力スキーマ                       |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                     | 担当 |
| -------- | ---------------------------------------------- | ---- |
| 1        | トリガーの目的を明確化                         | LLM  |
| 2        | トリガータイプを決定（webhook/file_watch/git等） | LLM  |
| 3        | トリガー設定を詳細化                           | LLM  |
| 4        | フィルター条件を設計                           | LLM  |
| 5        | 引数マッピングを設計                           | LLM  |
| 6        | スロットリング設定を決定                       | LLM  |
| 7        | event-trigger.jsonを出力                       | LLM  |

### 4.2 トリガータイプ選択

| タイプ | 選択条件                           |
| ------ | ---------------------------------- |
| webhook | 外部サービスからのHTTP通知       |
| file_watch | ファイルシステムの変更監視      |
| git | Git操作（push, PR, issue等）         |
| http_poll | 定期的なAPI監視                 |
| websocket | リアルタイムストリーム          |

### 4.3 チェックリスト

| 項目                           | 基準                         |
| ------------------------------ | ---------------------------- |
| トリガータイプが適切か         | ユースケースに合致           |
| セキュリティ設定があるか       | webhook署名検証等            |
| フィルターが適切か             | 不要なイベントを除外         |
| スロットリングが設定されているか | 連続イベント対策           |

### 4.4 ビジネスルール（制約）

| 制約               | 説明                               |
| ------------------ | ---------------------------------- |
| セキュリティ必須   | Webhook署名検証等                  |
| フィルター推奨     | 不要なイベントを除外               |
| スロットリング推奨 | 連続イベントを制御                 |

---

## 5. インターフェース

### 5.1 入力

| データ名         | 提供元          | 検証ルール           | 欠損時処理       |
| ---------------- | --------------- | -------------------- | ---------------- |
| トリガー要件     | ユーザー入力    | タイプが明確         | ヒアリング実施  |
| スキル名         | ユーザー入力    | 有効なスキル         | エラー           |

### 5.2 出力

| 成果物名             | 受領先               | 内容                   |
| -------------------- | -------------------- | ---------------------- |
| event-trigger.json   | register_trigger.js  | トリガー定義           |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/event-trigger.json",
  "name": "{{string: トリガー名}}",
  "description": "{{string: 説明}}",
  "trigger": {
    "type": "{{enum: webhook|file_watch|git|http_poll|websocket|manual}}",
    "webhook": {
      "path": "{{string: エンドポイントパス}}",
      "method": "{{enum: POST|PUT|PATCH}}",
      "secret": "{{string: シークレット（環境変数参照）}}"
    },
    "file_watch": {
      "paths": ["{{string: 監視パス}}"],
      "events": ["{{enum: create|modify|delete|rename}}"],
      "ignore": ["{{string: 無視パターン}}"],
      "recursive": "{{boolean}}"
    },
    "git": {
      "repository": "{{string: リポジトリパス}}",
      "events": ["{{enum: push|pull_request|issue|release|tag}}"],
      "branches": ["{{string: 対象ブランチ}}"]
    },
    "http_poll": {
      "url": "{{string: ポーリングURL}}",
      "interval": "{{number: 秒}}",
      "check_field": "{{string: 変更検知用JSONPath}}"
    }
  },
  "skill": "{{string: 実行するスキル}}",
  "args_mapping": {
    "{{param}}": "{{string: マッピング式}}"
  },
  "filter": {
    "expression": "{{string: フィルター式}}"
  },
  "throttle": {
    "debounce": "{{number: ミリ秒}}",
    "rate_limit": {
      "max_executions": "{{number}}",
      "window": "{{number: 秒}}"
    }
  },
  "enabled": "{{boolean}}"
}
```

### 5.3 後続処理

```bash
# スキーマ検証
node scripts/validate_schema.js \
  --input .tmp/event-trigger.json \
  --schema schemas/event-trigger.json

# トリガー登録
node scripts/register_trigger.js \
  --register .tmp/event-trigger.json

# テストイベント送信
node scripts/register_trigger.js \
  --test trigger-name \
  --data '{"action": "opened"}'
```

---

## 6. 設計例

### GitHub PR Webhook

```json
{
  "name": "github-pr-checker",
  "description": "PRオープン時にコードチェック実行",
  "trigger": {
    "type": "webhook",
    "webhook": {
      "path": "/webhooks/github",
      "method": "POST",
      "secret": "{{env.GITHUB_WEBHOOK_SECRET}}"
    }
  },
  "skill": "code-checker",
  "args_mapping": {
    "repo": "{{trigger.body.repository.full_name}}",
    "pr_number": "{{trigger.body.number}}",
    "head_sha": "{{trigger.body.pull_request.head.sha}}"
  },
  "filter": {
    "expression": "{{trigger.headers['x-github-event']}} == 'pull_request' && {{trigger.body.action}} in ['opened', 'synchronize']"
  },
  "throttle": {
    "debounce": 10000
  },
  "enabled": true
}
```

### ファイル監視

```json
{
  "name": "csv-auto-import",
  "description": "CSVファイル追加時に自動インポート",
  "trigger": {
    "type": "file_watch",
    "file_watch": {
      "paths": ["./data/import/*.csv"],
      "events": ["create"],
      "ignore": ["**/.DS_Store", "**/~*"],
      "recursive": false
    }
  },
  "skill": "csv-importer",
  "args_mapping": {
    "file_path": "{{trigger.path}}",
    "file_name": "{{trigger.path.split('/').pop()}}"
  },
  "throttle": {
    "debounce": 1000
  },
  "enabled": true
}
```

### HTTPポーリング

```json
{
  "name": "api-change-detector",
  "description": "APIの変更を検知して同期",
  "trigger": {
    "type": "http_poll",
    "http_poll": {
      "url": "https://api.example.com/data",
      "method": "GET",
      "headers": {
        "Authorization": "Bearer {{env.API_TOKEN}}"
      },
      "interval": 300,
      "check_field": "$.meta.updated_at"
    }
  },
  "skill": "data-syncer",
  "args_mapping": {
    "new_data": "{{trigger.body.data}}"
  },
  "enabled": true
}
```

---

## 7. ヒアリング質問

```
AskUserQuestion:
  questions:
    - question: "どのようなイベントでトリガーしますか？"
      header: "イベント"
      options:
        - label: "Webhook（外部からのHTTP通知）"
          description: "GitHub, Slack, Stripe等"
        - label: "ファイル変更"
          description: "ファイル作成/更新/削除"
        - label: "Git操作"
          description: "push, PR, issue等"
        - label: "定期的なAPI監視"
          description: "ポーリングで変更検知"

    - question: "どのサービスからのWebhookですか？"
      header: "ソース"
      options:
        - label: "GitHub"
        - label: "Slack"
        - label: "Stripe"
        - label: "その他"

    - question: "連続イベントの制御は必要ですか？"
      header: "スロットリング"
      options:
        - label: "はい（デバウンス）"
          description: "連続イベントを1つにまとめる"
        - label: "はい（レート制限）"
          description: "一定期間内の実行回数を制限"
        - label: "いいえ"
```
