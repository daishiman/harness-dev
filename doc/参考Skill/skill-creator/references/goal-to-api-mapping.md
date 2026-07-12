# 目的→API/ツール マッピングガイド

> **読み込み条件**: Phase 0-3（外部連携ヒアリング）時、ユーザーの目的からAPI/ツールを推薦する際に参照
> **相対パス**: `references/goal-to-api-mapping.md`

---

## 1. 概要

ユーザーは「やりたいこと」は知っているが、それを実現するために必要なAPI/ツールを知らないことが多い。
このドキュメントは、ユーザーの目的・ドメインから適切なAPI/サービスを推薦するためのマッピング知識ベース。

---

## 2. ドメイン別API推薦マップ

### 2.1 コミュニケーション・通知

| ユーザーの目的キーワード         | 推薦API/サービス    | 用途                             | 認証方式          |
| -------------------------------- | ------------------- | -------------------------------- | ----------------- |
| 日報、レポート、通知、メッセージ | Slack API           | メッセージ送受信、チャンネル管理 | OAuth/Bot Token   |
| 日報、レポート、通知、メッセージ | Discord API         | メッセージ送受信、Webhook        | Bot Token/Webhook |
| メール、通知、レポート送信       | Gmail API           | メール送受信                     | OAuth2            |
| メール、通知                     | SendGrid API        | メール送信（大量配信向け）       | API Key           |
| チーム通知、アラート             | Microsoft Teams API | メッセージ送信                   | OAuth2            |
| SMS通知、電話                    | Twilio API          | SMS/音声通話                     | API Key           |

### 2.2 開発・Git操作

| ユーザーの目的キーワード       | 推薦API/サービス   | 用途                          | 認証方式    |
| ------------------------------ | ------------------ | ----------------------------- | ----------- |
| PR、プルリクエスト、コード管理 | GitHub API         | PR作成、Issue管理、コード取得 | Token/OAuth |
| PR、マージリクエスト           | GitLab API         | MR作成、パイプライン管理      | Token       |
| コードレビュー、差分           | Bitbucket API      | PR管理、リポジトリ操作        | OAuth2      |
| CI/CD、ビルド、デプロイ        | GitHub Actions API | ワークフロー実行              | Token       |
| CI/CD、パイプライン            | CircleCI API       | ビルド管理                    | API Key     |
| CI/CD、Jenkins                 | Jenkins API        | ビルド・ジョブ管理            | Token       |

### 2.3 プロジェクト管理・タスク

| ユーザーの目的キーワード | 推薦API/サービス    | 用途                  | 認証方式          |
| ------------------------ | ------------------- | --------------------- | ----------------- |
| タスク管理、進捗         | Jira API            | Issue作成・更新・検索 | API Token         |
| タスク、プロジェクト管理 | Asana API           | タスク管理            | OAuth2            |
| タスク、カンバン         | Trello API          | カード・ボード管理    | API Key           |
| ドキュメント、Wiki       | Notion API          | ページ作成・更新      | Integration Token |
| ドキュメント、共有       | Google Docs API     | ドキュメント編集      | OAuth2            |
| スプレッドシート、データ | Google Sheets API   | シート操作            | OAuth2            |
| 会議、スケジュール       | Google Calendar API | 予定管理              | OAuth2            |

### 2.4 データ・ストレージ

| ユーザーの目的キーワード | 推薦API/サービス | 用途                   | 認証方式        |
| ------------------------ | ---------------- | ---------------------- | --------------- |
| ファイル保存、共有       | Google Drive API | ファイル管理           | OAuth2          |
| ファイル保存、同期       | Dropbox API      | ファイル操作           | OAuth2          |
| クラウドストレージ       | AWS S3 API       | オブジェクトストレージ | AWS Credentials |
| データベース、クラウド   | Firebase API     | Realtime DB/Firestore  | Service Account |
| データベース             | Supabase API     | PostgreSQL + Auth      | API Key         |

### 2.5 AI・自動化

| ユーザーの目的キーワード | 推薦API/サービス | 用途          | 認証方式 |
| ------------------------ | ---------------- | ------------- | -------- |
| AI、文章生成、要約       | OpenAI API       | GPT利用       | API Key  |
| AI、Claude               | Anthropic API    | Claude利用    | API Key  |
| 画像生成、AI             | Stability API    | 画像生成      | API Key  |
| 翻訳                     | DeepL API        | 翻訳          | API Key  |
| 音声認識                 | Whisper API      | 音声→テキスト | API Key  |

### 2.6 外部データ取得

| ユーザーの目的キーワード | 推薦API/サービス   | 用途                   | 認証方式 |
| ------------------------ | ------------------ | ---------------------- | -------- |
| 天気、気象               | OpenWeatherMap API | 天気情報取得           | API Key  |
| ニュース、記事           | News API           | ニュース取得           | API Key  |
| 株価、金融               | Alpha Vantage API  | 株価データ             | API Key  |
| 地図、位置情報           | Google Maps API    | 地図・ジオコーディング | API Key  |
| SNS、Twitter             | X (Twitter) API    | ツイート取得・投稿     | OAuth2   |

### 2.7 EC・決済

| ユーザーの目的キーワード | 推薦API/サービス | 用途       | 認証方式 |
| ------------------------ | ---------------- | ---------- | -------- |
| 決済、支払い             | Stripe API       | 決済処理   | API Key  |
| 決済                     | PayPal API       | 決済処理   | OAuth2   |
| EC、商品管理             | Shopify API      | ストア管理 | API Key  |

### 2.8 インフラ・モニタリング

| ユーザーの目的キーワード | 推薦API/サービス       | 用途               | 認証方式        |
| ------------------------ | ---------------------- | ------------------ | --------------- |
| サーバー監視、アラート   | Datadog API            | メトリクス・ログ   | API Key         |
| エラー監視               | Sentry API             | エラートラッキング | API Key         |
| ログ管理                 | Logstash/Elasticsearch | ログ収集・検索     | Basic Auth      |
| クラウド管理             | AWS SDK                | インフラ操作       | AWS Credentials |
| クラウド管理             | GCP SDK                | インフラ操作       | Service Account |

---

## 3. 複合目的のAPI推薦パターン

### 3.1 日報自動化

```
目的: 「毎日の作業を日報にまとめて報告したい」

推薦API:
├─ [必須] Slack API or Gmail API（報告送信先）
├─ [推奨] GitHub API（コミット履歴取得）
├─ [推奨] Jira API / Asana API（タスク進捗取得）
├─ [推奨] Google Calendar API（会議情報取得）
└─ [オプション] OpenAI API（要約生成）
```

### 3.2 PR自動作成

```
目的: 「コード変更からPRを自動作成したい」

推薦API:
├─ [必須] GitHub API / GitLab API（PR作成）
├─ [推奨] OpenAI API（PR本文生成）
├─ [オプション] Slack API（PR通知）
└─ [オプション] Jira API（Issue連携）
```

### 3.3 デプロイ自動化

```
目的: 「コードをデプロイして通知したい」

推薦API:
├─ [必須] GitHub Actions API / CircleCI API（CI/CD）
├─ [必須] AWS SDK / Vercel API / Netlify API（デプロイ先）
├─ [推奨] Slack API（デプロイ通知）
└─ [オプション] Datadog API（デプロイ後監視）
```

### 3.4 ドキュメント同期

```
目的: 「コードとドキュメントを同期したい」

推薦API:
├─ [必須] GitHub API（コード取得）
├─ [必須] Notion API / Confluence API（ドキュメント更新）
├─ [オプション] OpenAI API（ドキュメント生成）
└─ [オプション] Slack API（更新通知）
```

### 3.5 顧客対応自動化

```
目的: 「問い合わせに自動応答したい」

推薦API:
├─ [必須] Slack API / Intercom API / Zendesk API（問い合わせ受信）
├─ [必須] OpenAI API / Anthropic API（回答生成）
├─ [オプション] Notion API（FAQ検索）
└─ [オプション] Gmail API（メール返信）
```

---

## 4. 推薦ロジック

### 4.1 キーワード抽出

ユーザーの `goal` と `domain` フィールドから以下を抽出:

1. 動詞（自動化、送信、取得、作成、通知、etc.）
2. 名詞（日報、PR、メール、タスク、etc.）
3. 固有名詞（Slack、GitHub、Google、etc.）

### 4.2 マッチングルール

1. **固有名詞が含まれる場合** → そのサービスのAPIを必須として推薦
2. **動詞+名詞の組み合わせ** → 2.x のマッピング表から候補を抽出
3. **複合目的の場合** → 3.x のパターンから最も近いものを選択

### 4.3 推薦出力形式

```json
{
  "recommendations": [
    {
      "service": "Slack API",
      "priority": "must",
      "reason": "『日報を通知』という目的に対してメッセージ送信が必要",
      "authType": "oauth",
      "officialDocsUrl": "https://api.slack.com/docs"
    },
    {
      "service": "GitHub API",
      "priority": "should",
      "reason": "作業内容としてコミット履歴取得が有効",
      "authType": "token",
      "officialDocsUrl": "https://docs.github.com/en/rest"
    }
  ]
}
```

---

## 5. 使用方法

### Phase 0-3 での適用

1. ユーザーの `goal` を受け取る
2. キーワードを抽出
3. このマッピングガイドを参照してAPI候補を生成
4. ユーザーに推薦リストを提示（AskUserQuestion）
5. ユーザーが選択・追加・削除
6. `integrations[]` に反映

### 例

```
ユーザー入力: 「毎日の作業を日報にまとめてSlackに送りたい」

キーワード抽出:
- 「日報」→ レポート系
- 「Slack」→ 固有名詞（必須）
- 「作業」→ 開発系？タスク系？

推薦生成:
1. Slack API [必須] ← 固有名詞
2. GitHub API [推奨] ← 開発作業の可能性
3. Jira API [推奨] ← タスク管理の可能性

AskUserQuestion:
  question: "以下のAPIを使用しますか？"
  header: "推薦API"
  multiSelect: true
  options:
    - label: "Slack API（必須）"
      description: "日報をSlackに送信"
    - label: "GitHub API"
      description: "コミット履歴を日報に含める"
    - label: "Jira API"
      description: "タスク進捗を日報に含める"
    - label: "その他"
      description: "別のサービスを使用"
```

---

## 6. 更新履歴

| Date       | Changes                                      |
| ---------- | -------------------------------------------- |
| 2026-01-24 | 初版作成：8ドメイン、50+サービスのマッピング |
