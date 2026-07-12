# Notification スクリプトテンプレート指示

> **読み込み条件**: type === "notification" の場合
> **対応ランタイム**: Node.js, Python

---

## 目的

通知（Slack, Discord, Email等）を送信するスクリプトを生成する。

---

## AIへの実装指示

### 必須機能

1. **メッセージ送信**
   - プレーンテキスト
   - リッチフォーマット（Markdown等）
   - 添付ファイル（対応サービスの場合）

2. **サービス対応**
   - Slack（Webhook, API）
   - Discord（Webhook）
   - Email（SMTP）
   - その他（要件に応じて）

3. **エラーハンドリング**
   - 送信失敗時のリトライ
   - 認証エラーの処理

### 環境変数

- `{{SLACK_WEBHOOK_URL}}`: Slack Webhook
- `{{DISCORD_WEBHOOK_URL}}`: Discord Webhook
- `{{SMTP_HOST}}`, `{{SMTP_USER}}`, `{{SMTP_PASSWORD}}`: Email設定

### 引数仕様

| 引数 | 必須 | 説明 |
|------|------|------|
| --message | △ | 送信メッセージ |
| --file | △ | メッセージファイル |
| --channel | × | 送信先チャンネル |
| --service | × | 使用サービス |

---

## 品質基準

- [ ] Webhook URLの検証
- [ ] メッセージ長制限への対応
- [ ] 送信成功/失敗の明確なフィードバック
- [ ] 機密情報のログ出力防止
