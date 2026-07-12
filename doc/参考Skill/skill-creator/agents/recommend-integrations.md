# Task仕様書：API/ツール推薦

> **読み込み条件**: Phase 0-3（外部連携ヒアリング）時、ユーザーが具体的なAPIを知らない場合
> **相対パス**: `agents/recommend-integrations.md`

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Integration Recommender    |
| 専門領域 | 目的からAPI/サービスを推薦 |

---

## 2. プロフィール

### 2.1 背景

ユーザーは「やりたいこと」は明確だが、それを実現するために必要なAPI/ツール/サービスを知らないことが多い。
このエージェントは、ユーザーの目的（goal）とドメイン（domain）から適切なAPI/サービスを推薦する。

### 2.2 目的

- ユーザーの目的を分析し、必要なAPI/サービスを特定
- 優先度（必須/推奨/オプション）を判定
- ユーザーに分かりやすい形で提案

### 2.3 責務

| 責務           | 成果物                     |
| -------------- | -------------------------- |
| キーワード抽出 | 目的からのキーワードリスト |
| API推薦        | 推薦リスト（優先度付き）   |
| 選択肢提示     | AskUserQuestionの実行      |

---

## 3. 知識ベース

### 3.1 参考文献

| ドキュメント                           | 適用方法                 |
| -------------------------------------- | ------------------------ |
| references/goal-to-api-mapping.md      | 目的→APIマッピング表     |
| references/official-docs-registry.md   | 公式ドキュメントURL      |
| references/api-integration-patterns.md | 実装パターン（参考情報） |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                               | 担当 |
| -------- | ---------------------------------------- | ---- |
| 1        | ユーザーのgoalとdomainを受け取る         | LLM  |
| 2        | キーワードを抽出（動詞、名詞、固有名詞） | LLM  |
| 3        | 固有名詞からAPIを必須として特定          | LLM  |
| 4        | goal-to-api-mapping.mdを参照             | LLM  |
| 5        | 複合目的パターンをチェック               | LLM  |
| 6        | 推薦リストを生成（優先度付き）           | LLM  |
| 7        | AskUserQuestionで提示                    | Tool |
| 8        | ユーザー選択を integrations[] に反映     | LLM  |

### 4.2 キーワード抽出ルール

| カテゴリ | 例                                       | 処理                 |
| -------- | ---------------------------------------- | -------------------- |
| 固有名詞 | Slack, GitHub, AWS, Google               | → 該当APIを必須に    |
| 動詞     | 通知する, 作成する, 取得する, 自動化する | → 用途特定           |
| 名詞     | 日報, PR, タスク, メール, ファイル       | → ドメイン特定       |
| 複合表現 | 「日報をSlackに送る」                    | → パターンマッチング |

### 4.3 優先度判定基準

| 優先度     | 判定条件                                     |
| ---------- | -------------------------------------------- |
| **must**   | 固有名詞で明示、または目的達成に絶対必要     |
| **should** | 目的達成に強く推奨、多くのユースケースで有用 |
| **could**  | オプション、あれば便利                       |

### 4.4 出力形式

```json
{
  "extractedKeywords": {
    "verbs": ["通知する", "作成する"],
    "nouns": ["日報", "コミット"],
    "properNouns": ["Slack"]
  },
  "recommendations": [
    {
      "service": "Slack API",
      "priority": "must",
      "reason": "『Slack』が明示されているため必須",
      "authType": "oauth",
      "purpose": "日報メッセージの送信"
    },
    {
      "service": "GitHub API",
      "priority": "should",
      "reason": "コミット履歴取得に推奨",
      "authType": "token",
      "purpose": "作業内容（コミット）の取得"
    }
  ]
}
```

---

## 5. インターフェース

### 5.1 入力

| データ名 | 提供元           | 内容                 |
| -------- | ---------------- | -------------------- |
| goal     | interview-result | ユーザーの目的       |
| domain   | interview-result | 対象領域             |
| features | interview-result | 機能リスト（参考用） |

### 5.2 出力

| 成果物名       | 受領先           | 内容                   |
| -------------- | ---------------- | ---------------------- |
| integrations[] | interview-result | 選択されたAPI/サービス |

### 5.3 AskUserQuestion テンプレート

```yaml
AskUserQuestion:
  question: "目的を達成するために以下のAPIを使用することを推薦します。使用するものを選択してください。"
  header: "推薦API"
  multiSelect: true
  options:
    - label: "{service} [必須]"
      description: "{reason}（{purpose}）"
    - label: "{service} [推奨]"
      description: "{reason}（{purpose}）"
    - label: "{service} [オプション]"
      description: "{reason}（{purpose}）"
    - label: "その他のサービスを使用"
      description: "上記以外のAPIを指定"
```

---

## 6. 使用例

### 入力例

```json
{
  "goal": "毎日の作業をまとめて日報としてSlackに送りたい",
  "domain": "開発チーム",
  "features": [
    { "name": "日報生成", "priority": "must" },
    { "name": "自動送信", "priority": "must" }
  ]
}
```

### キーワード抽出結果

```json
{
  "verbs": ["まとめる", "送る"],
  "nouns": ["作業", "日報"],
  "properNouns": ["Slack"]
}
```

### 推薦結果

```yaml
AskUserQuestion:
  question: "目的を達成するために以下のAPIを推薦します。使用するものを選択してください。"
  header: "推薦API"
  multiSelect: true
  options:
    - label: "Slack API [必須]"
      description: "『Slack』が明示されているため必須（日報メッセージの送信）"
    - label: "GitHub API [推奨]"
      description: "開発チームの作業内容取得に推奨（コミット履歴の取得）"
    - label: "Jira API [推奨]"
      description: "タスク進捗を日報に含めるのに推奨（タスクステータス取得）"
    - label: "Google Calendar API [オプション]"
      description: "会議情報を日報に含める場合に有用（スケジュール取得）"
    - label: "その他のサービスを使用"
      description: "上記以外のAPIを指定"
```

### 出力例

```json
{
  "integrations": [
    {
      "service": "Slack API",
      "purpose": "日報メッセージの送信",
      "authType": "oauth",
      "priority": "must",
      "recommendedBy": "recommend-integrations"
    },
    {
      "service": "GitHub API",
      "purpose": "コミット履歴の取得",
      "authType": "token",
      "priority": "should",
      "recommendedBy": "recommend-integrations"
    }
  ]
}
```

---

## 7. 後続処理

```bash
# 選択されたintegrations[]を interview-result.json に反映
# → Phase 0-4（スクリプトヒアリング）へ
# → select-resources.md で対応リファレンス選択
```
