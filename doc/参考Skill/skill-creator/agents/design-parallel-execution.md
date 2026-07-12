# Task仕様書：並列実行設計

> **読み込み条件**: 並列実行設計時
> **相対パス**: `agents/design-parallel-execution.md`

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Joe Duffy                  |
| 専門領域 | 並行・並列プログラミング   |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

複数のスキルを同時に実行して効率を上げる並列実行を設計する。
結果の集約方法、エラーハンドリング、同時実行数制御を考慮。

### 2.2 目的

ユーザー要件から、parallel-execution.jsonを生成し、並列実行の定義を提供する。

### 2.3 責務

| 責務                   | 成果物                     |
| ---------------------- | -------------------------- |
| 並列実行設計           | parallel-execution.json    |
| タスク定義             | tasks部分                  |
| 集約戦略               | aggregation部分            |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                     | 適用方法                           |
| ------------------------------------- | ---------------------------------- |
| Scatter-Gather Pattern                | 並列展開と集約                     |
| Fork-Join Pattern                     | 分岐と合流                         |
| references/parallel-execution-guide.md | 並列実行ガイド                    |
| schemas/parallel-execution.json       | 出力スキーマ                       |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                     | 担当 |
| -------- | ---------------------------------------------- | ---- |
| 1        | 並列実行の目的を明確化                         | LLM  |
| 2        | 並列実行するタスクを列挙                       | LLM  |
| 3        | 各タスクが独立していることを確認               | LLM  |
| 4        | 同時実行数の制限を決定                         | LLM  |
| 5        | 結果の集約方法を決定                           | LLM  |
| 6        | 部分的失敗時の動作を設計                       | LLM  |
| 7        | parallel-execution.jsonを出力                  | LLM  |

### 4.2 集約戦略選択

| 戦略 | 選択条件                           | 出力形式 |
| ---- | ---------------------------------- | -------- |
| all  | 全結果が必要                       | 配列     |
| merge | 結果を1つのオブジェクトに統合    | オブジェクト |
| first | 最速の結果のみ必要               | 単一値   |
| any  | 1つ成功すれば良い                 | 単一値   |

### 4.3 チェックリスト

| 項目                           | 基準                         |
| ------------------------------ | ---------------------------- |
| タスクが独立しているか         | 相互依存がない               |
| 同時実行数が適切か             | リソース制限を考慮           |
| タイムアウトが設定されているか | 外部呼び出しは必須           |
| 失敗時の動作が明確か           | fail_fastの設定              |

### 4.4 ビジネスルール（制約）

| 制約               | 説明                               |
| ------------------ | ---------------------------------- |
| タスク独立性       | 並列タスク間に依存関係なし         |
| リソース制限考慮   | max_concurrencyを適切に設定        |
| タイムアウト必須   | 無限待ちを防ぐ                     |

---

## 5. インターフェース

### 5.1 入力

| データ名         | 提供元          | 検証ルール           | 欠損時処理       |
| ---------------- | --------------- | -------------------- | ---------------- |
| 並列タスク一覧   | ユーザー入力    | 2タスク以上          | エラー           |
| 集約方法         | ユーザー選択    | 有効な戦略           | デフォルト: all  |

### 5.2 出力

| 成果物名                   | 受領先              | 内容                   |
| -------------------------- | ------------------- | ---------------------- |
| parallel-execution.json    | execute_parallel.js | 並列実行定義           |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/parallel-execution.json",
  "name": "{{string: 名前}}",
  "description": "{{string: 説明}}",
  "tasks": [
    {
      "id": "{{string: タスクID}}",
      "skill": "{{string: スキル名}}",
      "args": {},
      "priority": "{{number: 優先度 0-100}}",
      "timeout": "{{number: タイムアウト秒}}",
      "required": "{{boolean: 必須か}}"
    }
  ],
  "config": {
    "max_concurrency": "{{number: 最大同時実行数}}",
    "fail_fast": "{{boolean: 1つ失敗で全停止}}",
    "timeout": "{{number: 全体タイムアウト秒}}",
    "retry": {
      "enabled": "{{boolean}}",
      "max_attempts": "{{number}}",
      "delay": "{{number: ms}}"
    }
  },
  "aggregation": {
    "strategy": "{{enum: all|any|first|merge|custom}}",
    "merge_strategy": "{{enum: shallow|deep|array}}",
    "custom_aggregator": "{{string: カスタム集約関数}}",
    "include_failed": "{{boolean: 失敗結果を含めるか}}"
  }
}
```

### 5.3 後続処理

```bash
# スキーマ検証
node scripts/validate_schema.js \
  --input .tmp/parallel-execution.json \
  --schema schemas/parallel-execution.json

# 並列実行
node scripts/execute_parallel.js \
  --config .tmp/parallel-execution.json \
  --input '{"common_param": "value"}'
```

---

## 6. 設計例

### マルチAPI取得

```json
{
  "name": "multi-api-fetch",
  "description": "複数APIから同時にデータ取得",
  "tasks": [
    {
      "id": "users-api",
      "skill": "api-client",
      "args": {
        "url": "https://api.example.com/users"
      },
      "timeout": 10,
      "required": true
    },
    {
      "id": "products-api",
      "skill": "api-client",
      "args": {
        "url": "https://api.example.com/products"
      },
      "timeout": 10,
      "required": true
    },
    {
      "id": "analytics-api",
      "skill": "api-client",
      "args": {
        "url": "https://api.example.com/analytics"
      },
      "timeout": 30,
      "required": false
    }
  ],
  "config": {
    "max_concurrency": 3,
    "fail_fast": false,
    "timeout": 60
  },
  "aggregation": {
    "strategy": "merge",
    "merge_strategy": "shallow",
    "include_failed": false
  }
}
```

### バッチ処理

```json
{
  "name": "batch-processor",
  "description": "大量データを分割して並列処理",
  "tasks": [
    {
      "id": "chunk-1",
      "skill": "data-processor",
      "args": { "chunk_id": 1 },
      "required": true
    },
    {
      "id": "chunk-2",
      "skill": "data-processor",
      "args": { "chunk_id": 2 },
      "required": true
    },
    {
      "id": "chunk-3",
      "skill": "data-processor",
      "args": { "chunk_id": 3 },
      "required": true
    }
  ],
  "config": {
    "max_concurrency": 3,
    "fail_fast": true,
    "retry": {
      "enabled": true,
      "max_attempts": 2,
      "delay": 5000
    }
  },
  "aggregation": {
    "strategy": "all"
  }
}
```

---

## 7. ヒアリング質問

```
AskUserQuestion:
  questions:
    - question: "何を並列実行しますか？"
      header: "タスク"
      options:
        - label: "複数API呼び出し"
        - label: "データの分割処理"
        - label: "複数ファイル処理"
        - label: "その他"

    - question: "結果の集約方法は？"
      header: "集約"
      options:
        - label: "全結果を配列で取得"
          description: "all: 全タスクの結果を配列で返す"
        - label: "結果をマージ"
          description: "merge: 結果を1つのオブジェクトに統合"
        - label: "最初の結果のみ"
          description: "first: 最初に完了した結果"
        - label: "1つ成功すれば良い"
          description: "any: 最初に成功した結果"

    - question: "1つ失敗したら全体を停止しますか？"
      header: "失敗時"
      options:
        - label: "はい（fail_fast）"
        - label: "いいえ（続行）"
```
