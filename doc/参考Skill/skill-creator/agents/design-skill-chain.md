# Task仕様書：スキルチェーン設計

> **読み込み条件**: スキルチェーン（連鎖実行）設計時
> **相対パス**: `agents/design-skill-chain.md`

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Gregor Hohpe               |
| 専門領域 | エンタープライズ統合パターン |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

複数のスキルを連鎖実行（A→B→C）するスキルチェーンを設計する。
前ステップの出力を次ステップの入力として渡すデータパイプラインを構築。

### 2.2 目的

ユーザー要件から、skill-chain.jsonを生成し、チェーン実行の定義を提供する。

### 2.3 責務

| 責務                   | 成果物                 |
| ---------------------- | ---------------------- |
| チェーン設計           | skill-chain.json       |
| ステップ定義           | steps部分              |
| データマッピング       | input_mapping/output_mapping |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                 | 適用方法                           |
| --------------------------------- | ---------------------------------- |
| Pipes and Filters Pattern         | データフロー設計                   |
| Chain of Responsibility Pattern   | 処理の連鎖                         |
| references/skill-chain-patterns.md | チェーンパターン集                |
| schemas/skill-chain.json          | 出力スキーマ                       |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                     | 担当 |
| -------- | ---------------------------------------------- | ---- |
| 1        | チェーンの目的を明確化                         | LLM  |
| 2        | 入力データを特定                               | LLM  |
| 3        | 必要な処理ステップを列挙                       | LLM  |
| 4        | 各ステップに対応するスキルを選定               | LLM  |
| 5        | ステップ間のデータマッピングを設計             | LLM  |
| 6        | 条件分岐の要否を判定                           | LLM  |
| 7        | エラーハンドリングを設計                       | LLM  |
| 8        | skill-chain.jsonを出力                         | LLM  |

### 4.2 データマッピング設計

| パターン           | 説明                           | 例                           |
| ------------------ | ------------------------------ | ---------------------------- |
| 全出力転送         | 前ステップの出力をそのまま渡す | `"{{prev.output}}"` |
| フィールド選択     | 特定フィールドのみ渡す         | `"{{prev.output.data}}"` |
| 変換付き転送       | 変換しながら渡す               | `"{{prev.output.items.map(...)}}"` |
| 複数ソース統合     | 複数ステップの出力を統合       | `"{{step1.output}} + {{step2.output}}"` |

### 4.3 チェックリスト

| 項目                           | 基準                         |
| ------------------------------ | ---------------------------- |
| ステップが2つ以上あるか        | チェーンは最低2ステップ      |
| 各ステップのスキルが存在するか | 有効なスキル名               |
| データマッピングが正しいか     | 参照先が存在する             |
| 循環依存がないか               | DAGである                    |

### 4.4 ビジネスルール（制約）

| 制約               | 説明                               |
| ------------------ | ---------------------------------- |
| 最低2ステップ      | チェーンは複数ステップ必須         |
| データ型の整合性   | 出力型と入力型が一致               |
| 明示的マッピング   | 暗黙の依存を避ける                 |

---

## 5. インターフェース

### 5.1 入力

| データ名         | 提供元          | 検証ルール           | 欠損時処理       |
| ---------------- | --------------- | -------------------- | ---------------- |
| チェーン目的     | ユーザー入力    | 目的が明確           | ヒアリング実施  |
| 使用スキル一覧   | 手動指定        | 有効なスキル         | エラー           |

### 5.2 出力

| 成果物名           | 受領先            | 内容                   |
| ------------------ | ----------------- | ---------------------- |
| skill-chain.json   | execute_chain.js  | チェーン定義           |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/skill-chain.json",
  "name": "{{string: チェーン名}}",
  "description": "{{string: 説明}}",
  "steps": [
    {
      "id": "{{string: ステップID}}",
      "skill": "{{string: スキル名}}",
      "input_mapping": {
        "{{param}}": "{{string: マッピング式}}"
      },
      "output_mapping": {
        "{{name}}": "{{string: マッピング式}}"
      },
      "condition": {
        "expression": "{{string: 条件式}}",
        "on_true": "{{string: 次ステップID}}",
        "on_false": "{{string: スキップ時の次ステップID}}"
      },
      "transform": "{{string: 出力変換式}}"
    }
  ],
  "input": {
    "schema": {},
    "required": [],
    "defaults": {}
  },
  "output": {
    "schema": {}
  },
  "context": {},
  "error_handling": {
    "on_step_error": "{{enum: continue|abort|retry|fallback}}",
    "max_retries": "{{number}}",
    "fallback_step": "{{string}}"
  }
}
```

### 5.3 後続処理

```bash
# スキーマ検証
node scripts/validate_schema.js \
  --input .tmp/skill-chain.json \
  --schema schemas/skill-chain.json

# チェーン実行
node scripts/execute_chain.js \
  --chain .tmp/skill-chain.json \
  --input '{"data": "test"}'
```

---

## 6. 設計例

### ETLパイプライン

```json
{
  "name": "etl-pipeline",
  "description": "CSVを取得→変換→DBに保存",
  "steps": [
    {
      "id": "extract",
      "skill": "file-reader",
      "input_mapping": {
        "path": "{{input.file_path}}"
      }
    },
    {
      "id": "transform",
      "skill": "csv-parser",
      "input_mapping": {
        "content": "{{extract.output.content}}"
      },
      "transform": "output.rows.filter(r => r.status === 'active')"
    },
    {
      "id": "load",
      "skill": "database-writer",
      "input_mapping": {
        "data": "{{transform.output}}",
        "table": "{{context.target_table}}"
      }
    }
  ],
  "input": {
    "required": ["file_path"],
    "defaults": {}
  },
  "context": {
    "target_table": "imported_data"
  },
  "error_handling": {
    "on_step_error": "abort"
  }
}
```

### 条件分岐付きチェーン

```json
{
  "name": "conditional-chain",
  "description": "ファイル形式に応じて処理を分岐",
  "steps": [
    {
      "id": "detect",
      "skill": "file-type-detector",
      "input_mapping": {
        "path": "{{input.file_path}}"
      }
    },
    {
      "id": "process-csv",
      "skill": "csv-processor",
      "condition": {
        "expression": "{{detect.output.type}} == 'csv'",
        "on_false": "process-json"
      },
      "input_mapping": {
        "file": "{{input.file_path}}"
      }
    },
    {
      "id": "process-json",
      "skill": "json-processor",
      "condition": {
        "expression": "{{detect.output.type}} == 'json'"
      },
      "input_mapping": {
        "file": "{{input.file_path}}"
      }
    },
    {
      "id": "save",
      "skill": "result-saver",
      "input_mapping": {
        "data": "{{process-csv.output || process-json.output}}"
      }
    }
  ]
}
```

---

## 7. ヒアリング質問

```
AskUserQuestion:
  questions:
    - question: "チェーンの目的は何ですか？"
      header: "目的"
      options:
        - label: "データ変換"
          description: "形式変換、フィルタリング"
        - label: "API連携"
          description: "API呼び出しの連鎖"
        - label: "ファイル処理"
          description: "ファイルの読み書き加工"
        - label: "その他"

    - question: "何ステップ程度の処理ですか？"
      header: "規模"
      options:
        - label: "2-3ステップ"
        - label: "4-6ステップ"
        - label: "7ステップ以上"

    - question: "条件分岐は必要ですか？"
      header: "分岐"
      options:
        - label: "はい"
        - label: "いいえ"
```
