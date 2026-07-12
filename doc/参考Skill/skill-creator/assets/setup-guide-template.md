# {{api_name}} セットアップガイド

> **最終更新**: {{last_updated}}
> **公式ドキュメント確認日**: {{docs_verified_date}}
> **対象バージョン**: {{api_version}}

---

## 概要

### 目的

このドキュメントを完了すると、**{{goal}}**が可能になります。

### 前提条件

以下を満たしていることを確認してください：

- [ ] {{prerequisite_account}}を持っている
- [ ] {{prerequisite_tool}}がインストールされている
  ```bash
  # 確認コマンド
  {{tool_check_command}}
  ```
- [ ] {{prerequisite_permission}}を持っている

### 所要時間

約**{{estimated_time}}**（手順通りに進めた場合）

---

## Step 1: {{step1_title}}

### 目的

{{step1_purpose}}

### 場所

| 項目 | 値 |
|------|-----|
| **URL** | {{step1_url}} |
| **ナビゲーション** | {{step1_navigation}} |

### 操作手順

1. **{{step1_action1}}**

   {{step1_action1_detail}}

2. **{{step1_action2}}**

   - 選択肢: `{{step1_action2_selection}}`
   - 入力値: `{{step1_action2_input}}`

### 期待される結果

{{step1_expected_result}}

### 確認方法

{{step1_verification}}

> **✅ 成功の指標**: {{step1_success_indicator}}

### トラブルシューティング

<details>
<summary>よくある問題</summary>

| 問題 | 原因 | 解決方法 |
|------|------|---------|
| {{step1_issue1}} | {{step1_issue1_cause}} | {{step1_issue1_solution}} |

</details>

---

## Step 2: {{step2_title}}

### 目的

{{step2_purpose}}

### 場所

| 項目 | 値 |
|------|-----|
| **URL** | {{step2_url}} |
| **ナビゲーション** | {{step2_navigation}} |

### 操作手順

{{step2_instructions}}

### 期待される結果

{{step2_expected_result}}

### 確認方法

{{step2_verification}}

---

<!-- 必要に応じてStep 3以降を追加 -->

---

## 設定値一覧

以下の値を取得・設定しました：

| 設定項目 | 値 | 取得ステップ | 用途 |
|----------|-----|-------------|------|
| `{{env_var1_name}}` | [Step {{env_var1_step}}で取得] | Step {{env_var1_step}} | {{env_var1_usage}} |
| `{{env_var2_name}}` | [Step {{env_var2_step}}で取得] | Step {{env_var2_step}} | {{env_var2_usage}} |

### 環境変数への設定

```bash
# .env ファイルに追加、または直接エクスポート
export {{env_var1_name}}="your-value-here"
export {{env_var2_name}}="your-value-here"
```

---

## 動作確認

### テストコマンド

```bash
{{verification_command}}
```

### 期待される出力

```{{verification_output_format}}
{{verification_expected_output}}
```

### 成功基準

- [ ] ステータスコード `{{expected_status_code}}` が返る
- [ ] レスポンスに `{{expected_response_field}}` が含まれる

---

## トラブルシューティング

### よくある問題

#### 問題1: {{common_issue1_symptom}}

**原因**: {{common_issue1_cause}}

**解決方法**:
1. {{common_issue1_solution_step1}}
2. {{common_issue1_solution_step2}}

#### 問題2: {{common_issue2_symptom}}

**原因**: {{common_issue2_cause}}

**解決方法**:
{{common_issue2_solution}}

---

## 次のステップ

- [ ] {{next_step1}}
- [ ] {{next_step2}}

---

## 参照ドキュメント

| ドキュメント | URL | 確認日 |
|-------------|-----|--------|
| {{ref1_title}} | {{ref1_url}} | {{ref1_date}} |
| {{ref2_title}} | {{ref2_url}} | {{ref2_date}} |

---

> このドキュメントは[公式ドキュメント]({{official_docs_url}})を参照して作成されました。
> 最新情報は公式ドキュメントをご確認ください。
