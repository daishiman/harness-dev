# Task仕様書：条件分岐設計

> **読み込み条件**: 条件分岐フロー設計時
> **相対パス**: `agents/design-conditional-flow.md`
> **Phase**: 2（設計サブタスク）

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Michael Feathers           |
| 専門領域 | レガシーコード改善・条件分岐設計 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

実行結果に基づいて処理を分岐させる条件フローを設計する。
複雑な条件式、複数パスの管理、デフォルト処理を考慮。

### 2.2 目的

ユーザー要件から、conditional-flow.jsonを生成し、条件分岐ロジックの定義を提供する。

### 2.3 責務

| 責務                   | 成果物                 |
| ---------------------- | ---------------------- |
| 条件分岐設計           | conditional-flow.json  |
| 条件式定義             | conditions部分         |
| アクション定義         | action部分             |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                 | 適用方法                           |
| --------------------------------- | ---------------------------------- |
| Working Effectively with Legacy Code | 条件分岐の整理                  |
| Strategy Pattern                  | 条件に応じた処理の切り替え         |
| schemas/conditional-flow.json     | 出力スキーマ                       |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                     | 担当 |
| -------- | ---------------------------------------------- | ---- |
| 1        | 分岐の目的を明確化                             | LLM  |
| 2        | 判定に使用するデータを特定                     | LLM  |
| 3        | 分岐条件を列挙                                 | LLM  |
| 4        | 各条件に対するアクションを定義                 | LLM  |
| 5        | デフォルトアクションを決定                     | LLM  |
| 6        | 条件の評価順序を最適化                         | LLM  |
| 7        | conditional-flow.jsonを出力                    | LLM  |

### 4.2 条件式パターン

| パターン   | 構文                               | 例                           |
| ---------- | ---------------------------------- | ---------------------------- |
| 等価比較   | `{{var}} == 'value'`               | `{{status}} == 'success'`    |
| 不等比較   | `{{var}} != 'value'`               | `{{status}} != 'error'`      |
| 数値比較   | `{{var}} > 100`                    | `{{count}} >= 10`            |
| 含有       | `{{var}} contains 'text'`          | `{{message}} contains 'error'` |
| 存在       | `{{var}} in ['a', 'b']`            | `{{type}} in ['csv', 'json']` |
| AND条件    | `{{a}} == 1 && {{b}} == 2`         | 複数条件のAND               |
| OR条件     | `{{a}} == 1 || {{b}} == 2`         | 複数条件のOR                |

### 4.3 チェックリスト

| 項目                           | 基準                         |
| ------------------------------ | ---------------------------- |
| 条件が網羅的か                 | 全パターンをカバー           |
| 条件が排他的か                 | 重複がない                   |
| デフォルトがあるか             | 想定外ケースへの対応         |
| 評価順序が正しいか             | 優先度の高い条件が先         |

### 4.4 ビジネスルール（制約）

| 制約               | 説明                               |
| ------------------ | ---------------------------------- |
| 網羅性             | 全ケースをカバーする               |
| 排他性             | 1つの入力に対し1つのパスのみ       |
| デフォルト必須     | 想定外ケースへの対応               |

---

## 5. インターフェース

### 5.1 入力

| データ名         | 提供元          | 検証ルール           | 欠損時処理       |
| ---------------- | --------------- | -------------------- | ---------------- |
| 分岐条件         | ユーザー入力    | 条件式が有効         | ヒアリング実施  |
| アクション       | ユーザー入力    | 有効なアクション     | エラー           |

### 5.2 出力

| 成果物名               | 受領先                | 内容                   |
| ---------------------- | --------------------- | ---------------------- |
| conditional-flow.json  | evaluate_condition.js | 条件分岐定義           |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/conditional-flow.json",
  "name": "{{string: 名前}}",
  "description": "{{string: 説明}}",
  "input": {},
  "conditions": [
    {
      "id": "{{string: 分岐ID}}",
      "condition": {
        "left": "{{string: 変数参照}}",
        "operator": "{{enum: ==|!=|>|<|>=|<=|contains|startsWith|endsWith|matches|in}}",
        "right": "{{any: 比較値}}"
      },
      "action": {
        "type": "{{enum: execute_skill|goto_step|return|abort|retry|notify}}",
        "skill": "{{string: スキル名}}",
        "args": {}
      }
    }
  ],
  "default": {
    "type": "{{enum: execute_skill|return|abort}}",
    "skill": "{{string: スキル名}}",
    "args": {}
  }
}
```

### 5.3 後続処理

```bash
# スキーマ検証
node scripts/validate_schema.js \
  --input .tmp/conditional-flow.json \
  --schema schemas/conditional-flow.json

# 条件評価
node scripts/evaluate_condition.js \
  --flow .tmp/conditional-flow.json \
  --input '{"status": "success"}'
```

---

## 6. 設計例

### ファイル形式による分岐

```json
{
  "name": "file-type-router",
  "description": "ファイル形式に応じて処理を分岐",
  "input": {
    "file_type": "string",
    "file_path": "string"
  },
  "conditions": [
    {
      "id": "csv-handler",
      "condition": {
        "left": "{{input.file_type}}",
        "operator": "==",
        "right": "csv"
      },
      "action": {
        "type": "execute_skill",
        "skill": "csv-processor",
        "args": {
          "path": "{{input.file_path}}"
        }
      }
    },
    {
      "id": "json-handler",
      "condition": {
        "left": "{{input.file_type}}",
        "operator": "==",
        "right": "json"
      },
      "action": {
        "type": "execute_skill",
        "skill": "json-processor",
        "args": {
          "path": "{{input.file_path}}"
        }
      }
    },
    {
      "id": "xml-handler",
      "condition": {
        "left": "{{input.file_type}}",
        "operator": "==",
        "right": "xml"
      },
      "action": {
        "type": "execute_skill",
        "skill": "xml-processor",
        "args": {
          "path": "{{input.file_path}}"
        }
      }
    }
  ],
  "default": {
    "type": "abort",
    "message": "Unsupported file type: {{input.file_type}}"
  }
}
```

### エラーレベルによる分岐

```json
{
  "name": "error-handler",
  "description": "エラーレベルに応じて処理を分岐",
  "conditions": [
    {
      "id": "critical",
      "condition": {
        "left": "{{input.error_level}}",
        "operator": "==",
        "right": "critical"
      },
      "action": {
        "type": "execute_skill",
        "skill": "alert-sender",
        "args": {
          "channel": "pagerduty",
          "message": "{{input.error_message}}"
        }
      }
    },
    {
      "id": "warning",
      "condition": {
        "left": "{{input.error_level}}",
        "operator": "==",
        "right": "warning"
      },
      "action": {
        "type": "execute_skill",
        "skill": "alert-sender",
        "args": {
          "channel": "slack",
          "message": "{{input.error_message}}"
        }
      }
    }
  ],
  "default": {
    "type": "execute_skill",
    "skill": "logger",
    "args": {
      "level": "info",
      "message": "{{input.error_message}}"
    }
  }
}
```

---

## 7. ヒアリング質問

```
AskUserQuestion:
  questions:
    - question: "何を条件として分岐しますか？"
      header: "条件"
      options:
        - label: "ステータス値"
          description: "success/failure/pending等"
        - label: "データ型"
          description: "CSV/JSON/XML等"
        - label: "数値範囲"
          description: "閾値による分岐"
        - label: "その他"

    - question: "分岐パターンは何種類ですか？"
      header: "パターン数"
      options:
        - label: "2パターン"
        - label: "3-4パターン"
        - label: "5パターン以上"

    - question: "デフォルトの動作は？"
      header: "デフォルト"
      options:
        - label: "エラーで停止"
        - label: "ログ出力のみ"
        - label: "特定の処理を実行"
```
