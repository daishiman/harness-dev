# Task仕様書：公式ドキュメント取得

> **読み込み条件**: 公式ドキュメントから最新情報を取得する時
> **相対パス**: `agents/fetch-official-docs.md`

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Tom Preston-Werner         |
| 専門領域 | 開発者体験・ドキュメント設計 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

API連携ドキュメント作成のため、公式ドキュメントから最新情報を取得・解析する。
WebSearch/WebFetch等のツールを使用して情報を収集。

### 2.2 目的

指定されたAPIの公式ドキュメントから、セットアップに必要な最新情報を構造化して出力する。

### 2.3 責務

| 責務                   | 成果物                       |
| ---------------------- | ---------------------------- |
| 公式ドキュメント検索   | URLリスト                    |
| 情報抽出               | extracted-docs.json          |
| 構造化                 | 使用可能な形式への変換       |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                     | 適用方法                           |
| ------------------------------------- | ---------------------------------- |
| references/official-docs-registry.md  | 公式ドキュメントURLレジストリ      |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                     | 担当 |
| -------- | ---------------------------------------------- | ---- |
| 1        | 対象APIを特定                                  | LLM  |
| 2        | レジストリから公式URLを取得                    | LLM  |
| 3        | WebSearchで最新ドキュメントを検索              | LLM  |
| 4        | 関連ページを特定（クイックスタート、認証等）   | LLM  |
| 5        | 各ページから必要情報を抽出                     | LLM  |
| 6        | 情報を構造化して出力                           | LLM  |

### 4.2 検索クエリテンプレート

| 目的 | クエリ例 |
|------|---------|
| クイックスタート | `[API名] quickstart guide 2024` |
| 認証設定 | `[API名] authentication setup` |
| APIキー作成 | `[API名] API key create console` |
| OAuth設定 | `[API名] OAuth 2.0 setup` |
| SDK使用方法 | `[API名] SDK [言語] getting started` |
| エラー解決 | `[API名] [エラーメッセージ] solution` |

### 4.3 抽出対象情報

| カテゴリ | 抽出項目 |
|----------|---------|
| **認証** | 認証方法、必要な認証情報、取得手順 |
| **エンドポイント** | ベースURL、APIバージョン |
| **権限** | 必要なスコープ、IAM権限 |
| **コンソール** | 設定画面のURL、ナビゲーションパス |
| **SDK** | インストール方法、初期化コード |
| **サンプル** | 動作確認用コード |

### 4.4 ビジネスルール（制約）

| 制約               | 説明                               |
| ------------------ | ---------------------------------- |
| 公式ソースのみ     | 公式ドキュメント、公式ブログのみ使用 |
| 日付確認           | 情報の鮮度を確認                   |
| バージョン確認     | APIバージョンを明記                |

---

## 5. インターフェース

### 5.1 入力

| データ名         | 提供元          | 検証ルール           | 欠損時処理       |
| ---------------- | --------------- | -------------------- | ---------------- |
| APIプロバイダー  | ユーザー/前工程 | 有効なプロバイダー   | エラー           |
| API名            | ユーザー/前工程 | 有効なAPI名          | エラー           |
| 必要な情報タイプ | 前工程          | 有効なタイプ         | 全タイプ取得     |

### 5.2 出力

| 成果物名             | 受領先              | 内容                   |
| -------------------- | ------------------- | ---------------------- |
| extracted-docs.json  | generate-api-docs   | 抽出された情報         |

#### 出力形式

```json
{
  "api_provider": "Google",
  "api_name": "Gmail API",
  "fetched_at": "2024-XX-XX",
  "sources": [
    {
      "url": "https://...",
      "title": "...",
      "type": "quickstart",
      "verified": true
    }
  ],
  "authentication": {
    "type": "oauth2",
    "console_url": "https://console.cloud.google.com/apis/credentials",
    "steps": [
      {
        "action": "Create OAuth 2.0 Client ID",
        "url": "https://...",
        "details": "..."
      }
    ],
    "required_scopes": [
      "https://www.googleapis.com/auth/gmail.readonly"
    ]
  },
  "setup_steps": [
    {
      "order": 1,
      "title": "Enable API",
      "url": "https://console.cloud.google.com/apis/library/gmail.googleapis.com",
      "instructions": ["..."]
    }
  ],
  "sdk": {
    "node": {
      "install": "npm install googleapis",
      "init_code": "..."
    },
    "python": {
      "install": "pip install google-api-python-client",
      "init_code": "..."
    }
  },
  "verification": {
    "test_endpoint": "https://gmail.googleapis.com/gmail/v1/users/me/profile",
    "curl_example": "curl -H \"Authorization: Bearer $TOKEN\" ..."
  },
  "common_issues": [
    {
      "error": "403 Forbidden",
      "cause": "API not enabled",
      "solution": "Enable Gmail API in Cloud Console"
    }
  ]
}
```

### 5.3 後続処理

```bash
# 抽出情報を使用してドキュメント生成
# → agents/generate-api-docs.md を読み込み
```

---

## 6. 検索・抽出パターン

### Google Cloud / Google APIs

```
# 検索クエリ
WebSearch: "Google [API名] API quickstart 2024"
WebSearch: "Google Cloud Console [API名] enable"
WebSearch: "Google [API名] OAuth 2.0 credentials"

# 主要URL
- Console: https://console.cloud.google.com/
- API Library: https://console.cloud.google.com/apis/library
- Credentials: https://console.cloud.google.com/apis/credentials
```

### AWS

```
# 検索クエリ
WebSearch: "AWS [サービス名] getting started 2024"
WebSearch: "AWS IAM [サービス名] permissions"
WebSearch: "AWS CLI [サービス名] configure"

# 主要URL
- Console: https://console.aws.amazon.com/
- IAM: https://console.aws.amazon.com/iam/
```

### Stripe

```
# 検索クエリ
WebSearch: "Stripe API keys dashboard"
WebSearch: "Stripe [機能名] integration guide"

# 主要URL
- Dashboard: https://dashboard.stripe.com/
- API Keys: https://dashboard.stripe.com/apikeys
```

---

## 7. 品質チェック

### 情報の検証

| チェック項目 | 確認方法 |
|-------------|---------|
| URLが有効 | アクセス可能か |
| 情報が最新 | 更新日を確認 |
| バージョン一致 | 対象バージョンと一致 |
| ステップが完全 | 抜けがないか |

### 出力前確認

```
- [ ] 全ソースURLが有効
- [ ] 認証方法が正確
- [ ] 必要なスコープ/権限が網羅
- [ ] コンソールURLが正確
- [ ] サンプルコードが動作可能
```
