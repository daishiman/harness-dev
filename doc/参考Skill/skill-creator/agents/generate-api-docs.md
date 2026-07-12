# Task仕様書：APIドキュメント生成

> **読み込み条件**: API連携ドキュメント生成時
> **相対パス**: `agents/generate-api-docs.md`
> **Phase**: 4（生成サブタスク）

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Daniele Procida            |
| 専門領域 | 技術ドキュメンテーション（Diátaxis Framework） |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

API連携に必要なセットアップドキュメントを生成する。
**公式ドキュメントを参照し、そのドキュメントだけでタスクが完了できる**レベルの詳細さを持つドキュメントを作成。

### 2.2 目的

ユーザー要件から、api-documentation.jsonと実際のマークダウンドキュメントを生成する。

### 2.3 責務

| 責務                   | 成果物                       |
| ---------------------- | ---------------------------- |
| 公式ドキュメント参照   | 最新情報の取得               |
| ドキュメント構造設計   | api-documentation.json       |
| ドキュメント生成       | setup-guide.md               |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                     | 適用方法                           |
| ------------------------------------- | ---------------------------------- |
| Diátaxis Documentation Framework      | ドキュメント構造                   |
| references/api-docs-standards.md      | 品質基準                           |
| references/official-docs-registry.md  | 公式ドキュメントURL                |
| schemas/api-documentation.json        | 出力スキーマ                       |
| schemas/setup-guide.json              | セットアップガイドスキーマ         |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                     | 担当 |
| -------- | ---------------------------------------------- | ---- |
| 1        | 対象APIを特定                                  | LLM  |
| 2        | 公式ドキュメントURLを取得（レジストリ参照）    | LLM  |
| 3        | **WebSearchで最新の公式ドキュメントを確認**    | LLM  |
| 4        | 認証方法を特定（APIキー/OAuth/サービスアカウント） | LLM  |
| 5        | 必要なステップを列挙                           | LLM  |
| 6        | 各ステップの詳細を設計（場所、操作、確認方法） | LLM  |
| 7        | トラブルシューティングを追加                   | LLM  |
| 8        | 動作確認方法を設計                             | LLM  |
| 9        | api-documentation.jsonを出力                   | LLM  |
| 10       | マークダウンドキュメントを生成                 | LLM  |

### 4.2 ドキュメント必須要素

| 要素 | 説明 | 必須 |
|------|------|------|
| 目的 | 完了後に何ができるか | ✅ |
| 前提条件 | 必要なアカウント、ツール、権限 | ✅ |
| 場所 | 各ステップのURL、ナビゲーションパス | ✅ |
| 操作手順 | 具体的なクリック、入力、選択 | ✅ |
| 期待結果 | 操作後の状態 | ✅ |
| 確認方法 | 成功の確認方法 | ✅ |
| 設定値サマリー | 取得した値の一覧 | ✅ |
| 動作確認 | コマンドと期待出力 | ✅ |
| トラブルシューティング | よくある問題と解決方法 | ✅ |
| 参照ドキュメント | 公式ドキュメントへのリンク | ✅ |

### 4.3 チェックリスト

| 項目                           | 基準                         |
| ------------------------------ | ---------------------------- |
| 公式ドキュメントを参照したか   | WebSearchで最新情報を確認    |
| 全ステップに場所が明記されているか | URL、ナビゲーションパス    |
| 全ステップに目的が明記されているか | 「なぜ」が説明されている   |
| 曖昧な表現がないか             | 「適切な」等を具体化         |
| 動作確認方法があるか           | 実行コマンドと期待出力       |

### 4.4 ビジネスルール（制約）

| 制約               | 説明                               |
| ------------------ | ---------------------------------- |
| 自己完結           | 外部参照なしで作業完了可能         |
| 最新性             | 公式ドキュメントを必ず参照         |
| 具体性             | 曖昧な表現を排除                   |
| 検証可能           | 動作確認方法を必ず含める           |

---

## 5. インターフェース

### 5.1 入力

| データ名         | 提供元          | 検証ルール           | 欠損時処理       |
| ---------------- | --------------- | -------------------- | ---------------- |
| APIプロバイダー  | ユーザー入力    | 有効なプロバイダー   | ヒアリング実施  |
| API名            | ユーザー入力    | 有効なAPI名          | ヒアリング実施  |
| 使用目的         | ユーザー入力    | 目的が明確           | ヒアリング実施  |

### 5.2 出力

| 成果物名                 | 受領先          | 内容                           |
| ------------------------ | --------------- | ------------------------------ |
| api-documentation.json   | validate_docs.js | ドキュメント構造               |
| setup-guide.md           | ユーザー        | 実際のセットアップガイド       |

#### 出力スキーマ（抜粋）

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/api-documentation.json",
  "name": "{{string: ドキュメント名}}",
  "api_provider": "{{string: プロバイダー名}}",
  "api_name": "{{string: API名}}",
  "official_docs_url": "{{string: 公式ドキュメントURL}}",
  "sections": [
    {
      "title": "{{string: セクションタイトル}}",
      "purpose": "{{string: 目的}}",
      "steps": [
        {
          "number": 1,
          "action": "{{string: アクション}}",
          "purpose": "{{string: なぜ必要か}}",
          "location": {
            "type": "url",
            "url": "{{string: URL}}",
            "navigation": ["{{string: ナビゲーションパス}}"]
          },
          "instructions": ["{{string: 詳細手順}}"],
          "expected_result": "{{string: 期待結果}}",
          "verification": "{{string: 確認方法}}"
        }
      ]
    }
  ],
  "credentials": {
    "auth_type": "{{enum: api_key|oauth2|service_account}}",
    "required_credentials": []
  },
  "environment_variables": [],
  "verification": {
    "methods": []
  },
  "troubleshooting": []
}
```

### 5.3 後続処理

```bash
# スキーマ検証
node scripts/validate_schema.js \
  --input .tmp/api-documentation.json \
  --schema schemas/api-documentation.json

# ドキュメント生成
node scripts/generate_api_docs.js \
  --config .tmp/api-documentation.json \
  --output docs/api-setup/

# ドキュメント検証
node scripts/validate_docs.js \
  --doc docs/api-setup/setup-guide.md
```

---

## 6. 生成テンプレート

### マークダウン出力形式

```markdown
# [API名] セットアップガイド

> 最終更新: YYYY-MM-DD
> 公式ドキュメント確認日: YYYY-MM-DD

## 概要

### 目的
このドキュメントを完了すると、[具体的にできること]が可能になります。

### 前提条件
- [ ] [必要なアカウント]を持っている
- [ ] [必要なツール]がインストールされている
- [ ] [必要な権限]を持っている

### 所要時間
約XX分

---

## Step 1: [アクション名]

### 目的
[なぜこのステップが必要か]

### 場所
- **URL**: [完全なURL]
- **ナビゲーション**: [メニュー] > [サブメニュー] > [項目]

### 操作手順
1. [具体的な操作]
   - [補足説明]
2. [次の操作]
   - 入力値: `[具体的な値]`

### 期待される結果
[操作後に表示されるべきもの]

### 確認方法
[成功したことをどう確認するか]

### トラブルシューティング
| 問題 | 原因 | 解決方法 |
|------|------|---------|
| [エラー] | [原因] | [解決策] |

---

## 設定値一覧

| 設定項目 | 値 | 取得場所 | 用途 |
|----------|-----|----------|------|
| [項目名] | [Step Xで取得] | [場所] | [用途] |

---

## 動作確認

### 確認コマンド
\`\`\`bash
[実行コマンド]
\`\`\`

### 期待される出力
\`\`\`json
[期待される出力]
\`\`\`

---

## 参照ドキュメント

| ドキュメント | URL | 確認日 |
|-------------|-----|--------|
| [名前] | [URL] | YYYY-MM-DD |
```

---

## 7. ヒアリング質問

```
AskUserQuestion:
  questions:
    - question: "どのAPIのセットアップガイドを作成しますか？"
      header: "API"
      options:
        - label: "Google系（Gmail, Sheets, Drive等）"
        - label: "AWS系（S3, Lambda, DynamoDB等）"
        - label: "Stripe（決済）"
        - label: "その他（指定してください）"

    - question: "認証方法は決まっていますか？"
      header: "認証"
      options:
        - label: "APIキー"
        - label: "OAuth 2.0"
        - label: "サービスアカウント"
        - label: "わからない（自動選択）"

    - question: "どの言語/SDKで使用しますか？"
      header: "言語"
      options:
        - label: "Node.js"
        - label: "Python"
        - label: "Bash/curl"
        - label: "複数対応"
```

---

## 8. 公式ドキュメント参照手順

### WebSearch使用例

```
WebSearch: "[API名] quickstart guide [年]"
WebSearch: "[API名] authentication setup"
WebSearch: "[API名] API key create"
```

### 情報抽出ポイント

1. **最新のコンソールURL**
   - UIが変更されている可能性があるため確認

2. **認証フロー**
   - 最新の認証方法を確認

3. **必要な権限/スコープ**
   - 変更がないか確認

4. **サンプルコード**
   - 動作確認用に使用
