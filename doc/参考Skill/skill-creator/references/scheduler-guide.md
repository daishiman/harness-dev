# スケジューラーガイド

> **読み込み条件**: スケジューリング設計時
> **相対パス**: `references/scheduler-guide.md`

---

## 概要

スケジューラーは、スキルを定期的に自動実行する機能。

### ユースケース

- 日次/週次レポート生成
- 定期的なデータ同期
- バックアップジョブ
- ヘルスチェック
- キャッシュ更新

---

## スケジュールタイプ

### 1. cron式

```yaml
schedule:
  type: cron
  cron: "0 9 * * *"  # 毎日9:00
  timezone: "Asia/Tokyo"
```

#### cron式の構文

```
┌───────────── 分 (0-59)
│ ┌───────────── 時 (0-23)
│ │ ┌───────────── 日 (1-31)
│ │ │ ┌───────────── 月 (1-12)
│ │ │ │ ┌───────────── 曜日 (0-6, 0=日曜)
│ │ │ │ │
* * * * *
```

#### よく使うcron式

| 式 | 説明 |
|---|------|
| `0 * * * *` | 毎時0分 |
| `0 9 * * *` | 毎日9:00 |
| `0 9 * * 1-5` | 平日9:00 |
| `0 0 * * 0` | 毎週日曜0:00 |
| `0 0 1 * *` | 毎月1日0:00 |
| `*/15 * * * *` | 15分ごと |
| `0 9,18 * * *` | 9:00と18:00 |

### 2. インターバル

```yaml
schedule:
  type: interval
  interval:
    value: 30
    unit: minutes  # seconds | minutes | hours | days
```

### 3. 一度だけ

```yaml
schedule:
  type: once
  at: "2024-12-25T09:00:00+09:00"
```

---

## 完全な設定例

```yaml
name: daily-report
description: "日次レポートを生成してSlackに投稿"

skill: report-generator
args:
  report_type: "daily"
  format: "pdf"

schedule:
  type: cron
  cron: "0 9 * * 1-5"  # 平日9:00
  timezone: "Asia/Tokyo"
  start_date: "2024-01-01T00:00:00+09:00"
  end_date: "2024-12-31T23:59:59+09:00"

execution:
  timeout: 300  # 5分
  retry:
    enabled: true
    max_attempts: 3
    delay: 60
  concurrency: skip  # 前回実行中ならスキップ
  working_directory: "/app/reports"
  environment:
    REPORT_OUTPUT_DIR: "/tmp/reports"

notification:
  on_success: false
  on_failure: true
  on_start: false
  channels:
    - type: slack
      config:
        webhook_url: "{{env.SLACK_WEBHOOK_URL}}"
        channel: "#alerts"

enabled: true
```

---

## 実行制御

### concurrency（同時実行制御）

前回の実行が終わっていない場合の動作。

| 値 | 説明 |
|---|------|
| `allow` | 並行して実行 |
| `skip` | 今回の実行をスキップ |
| `queue` | キューに入れて待機 |

```yaml
execution:
  concurrency: skip  # 推奨
```

### タイムアウト

```yaml
execution:
  timeout: 3600  # 1時間（秒）
```

### リトライ

```yaml
execution:
  retry:
    enabled: true
    max_attempts: 3
    delay: 60  # 秒
```

---

## 環境変数とシークレット

### 環境変数の設定

```yaml
execution:
  environment:
    NODE_ENV: "production"
    LOG_LEVEL: "info"
    API_URL: "https://api.example.com"
```

### シークレットの参照

```yaml
args:
  api_key: "{{env.API_KEY}}"  # 環境変数から

execution:
  environment:
    API_KEY: "{{secret.api_key}}"  # シークレットストアから
```

---

## 通知設定

### Slack通知

```yaml
notification:
  on_failure: true
  channels:
    - type: slack
      config:
        webhook_url: "{{env.SLACK_WEBHOOK_URL}}"
        channel: "#alerts"
        username: "Scheduler Bot"
        icon_emoji: ":robot_face:"
```

### メール通知

```yaml
notification:
  channels:
    - type: email
      config:
        to: ["admin@example.com"]
        subject: "スケジュールジョブ失敗: {{job.name}}"
```

### Webhook通知

```yaml
notification:
  channels:
    - type: webhook
      config:
        url: "https://hooks.example.com/notify"
        method: "POST"
        headers:
          Authorization: "Bearer {{env.WEBHOOK_TOKEN}}"
```

---

## 管理コマンド

```bash
# スケジュール一覧
node scripts/schedule_skill.js --list

# スケジュール登録
node scripts/schedule_skill.js --register schedule.yaml

# スケジュール更新
node scripts/schedule_skill.js --update daily-report --cron "0 10 * * *"

# スケジュール無効化
node scripts/schedule_skill.js --disable daily-report

# スケジュール有効化
node scripts/schedule_skill.js --enable daily-report

# スケジュール削除
node scripts/schedule_skill.js --delete daily-report

# 即時実行（テスト用）
node scripts/schedule_skill.js --run-now daily-report

# 次回実行時刻確認
node scripts/schedule_skill.js --next daily-report
```

---

## ベストプラクティス

### 1. 適切な時刻設定

```yaml
# 良い例: 負荷分散
schedule:
  cron: "0 9 * * *"  # 9:00ちょうど

# より良い例: 負荷分散（ランダムオフセット）
schedule:
  cron: "7 9 * * *"  # 9:07（他と重ならない）
```

### 2. タイムゾーンを明示

```yaml
schedule:
  cron: "0 9 * * *"
  timezone: "Asia/Tokyo"  # 必ず指定
```

### 3. 開始/終了日を設定

```yaml
schedule:
  start_date: "2024-01-01T00:00:00+09:00"
  end_date: "2024-12-31T23:59:59+09:00"
  # 期間限定のジョブに有効
```

### 4. 冪等性を確保

```yaml
# スキル側で冪等性を確保
# 同じ日に2回実行しても問題ないように
args:
  date: "{{$date}}"  # 日付を引数に
  mode: "upsert"     # 上書きモード
```

### 5. ログと監視

```yaml
notification:
  on_failure: true   # 失敗は必ず通知
  on_success: false  # 成功は通知しない（ノイズ軽減）
```

---

## トラブルシューティング

| 問題 | 原因 | 解決策 |
|------|------|--------|
| 実行されない | enabledがfalse | `--enable`で有効化 |
| 時刻がずれる | タイムゾーン設定漏れ | timezoneを明示 |
| 重複実行 | concurrencyがallow | skipまたはqueueに変更 |
| タイムアウト | 処理時間超過 | timeoutを延長 |

---

## 関連リソース

- [orchestration-guide.md](orchestration-guide.md) - オーケストレーション全体ガイド
- [event-trigger-guide.md](event-trigger-guide.md) - イベントトリガー
- [schemas/schedule.json](../schemas/schedule.json) - スキーマ定義
