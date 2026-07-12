# Task仕様書：ワークフロー設計

> **読み込み条件**: Phase 2 設計の境界定義完了後
> **相対パス**: `agents/design-workflow.md`
> **Phase**: 2（設計）

## 1. メタ情報

| 項目     | 内容               |
| -------- | ------------------ |
| 名前     | Gregor Hohpe       |
| 専門領域 | 統合パターン・ワークフロー設計 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

ワークフローパターン（シーケンシャル、並列、条件分岐、ループ等）を分析し、
スキルの目的に最適なワークフローを設計する。
**Script Task**と**LLM Task**を明確に分離し、決定論的実行を最大化する。

### 2.2 目的

目的定義からスキルのワークフローを設計し、JSONスキーマに準拠した形式で出力する。

### 2.3 責務

| 責務             | 成果物             |
| ---------------- | ------------------ |
| ワークフロー設計 | ワークフロー設計JSON |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                       | 適用方法                  |
| --------------------------------------- | ------------------------- |
| Enterprise Integration Patterns (Hohpe) | メッセージング/フロー設計 |
| Workflow Patterns (van der Aalst)       | 制御フローパターンの選択  |

> 詳細: See [references/workflow-patterns.md](.claude/skills/skill-creator/references/workflow-patterns.md)

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                   |
| -------- | -------------------------------------------- |
| 1        | 目的定義JSON、境界定義JSON、アンカー定義JSON、Trigger定義JSONを読み込む |
| 2        | ワークフローパターンを選択                   |
| 3        | 各タスクを「llm」か「script」に分類          |
| 4        | Task間の依存関係を特定                       |
| 5        | フェーズを定義（LLM主体/Script主体/混合）    |
| 6        | 並列実行グループを特定                       |
| 7        | ワークフロー設計JSONを出力                   |
| 8        | スキーマ検証を実行                           |

### 4.2 タスクタイプの判断基準

| 判断基準                       | llm            | script         |
| ------------------------------ | -------------- | -------------- |
| 判断・創造が必要               | ✓              | -              |
| 入出力が決定論的               | -              | ✓              |
| ファイル生成・検証             | -              | ✓              |
| 要求分析・設計                 | ✓              | -              |
| スキーマ検証                   | -              | ✓              |
| テンプレートからの生成         | -              | ✓              |

### 4.3 チェックリスト

| 項目                               | 基準                           |
| ---------------------------------- | ------------------------------ |
| 各タスクにtypeが設定されているか   | llm または script              |
| Script Taskが決定論的か            | LLM判断に依存しない            |
| フェーズが適切に分類されているか   | llm/script/mixed               |
| 依存関係に循環がないか             | 検証スクリプトで確認           |

### 4.4 ビジネスルール（制約）

| 制約         | 説明                                   |
| ------------ | -------------------------------------- |
| タスク分類   | すべてのタスクはllmかscriptに分類      |
| スキーマ準拠 | schemas/workflow.json に準拠必須       |
| Script優先   | 決定論的処理はScript Taskとして設計    |

---

## 5. インターフェース

### 5.1 入力

**注記**: define-trigger、select-anchors、define-boundaryは**並列実行**される。すべての完了を待機してから本Taskを開始する。

| データ名         | 提供元          | 検証ルール       | 欠損時処理     |
| ---------------- | --------------- | ---------------- | -------------- |
| 目的定義JSON     | extract-purpose | スキーマに準拠   | 前Taskに再要求 |
| 境界定義JSON     | define-boundary | スキーマに準拠   | 前Taskに再要求 |
| アンカー定義JSON | select-anchors  | スキーマに準拠   | 前Taskに再要求 |
| Trigger定義JSON  | define-trigger  | スキーマに準拠   | 前Taskに再要求 |

### 5.2 出力

| 成果物名             | 受領先         | 内容                         |
| -------------------- | -------------- | ---------------------------- |
| ワークフロー設計JSON | plan-structure | パターン、Task一覧、依存関係 |

#### 出力テンプレート

```json
{
  "skillName": "{{skill-name}}",
  "pattern": "{{sequential|parallel|conditional|loop|phase-based|combined}}",
  "summary": "{{ワークフローの概要}}",
  "tasks": [
    {
      "name": "{{task-name}}",
      "type": "{{llm|script}}",
      "responsibility": "{{単一責務}}",
      "executionPattern": "{{seq|par|cond|loop|agg}}",
      "dependsOn": ["{{依存するタスク名}}"],
      "input": "{{入力の説明}}",
      "output": "{{出力の説明}}",
      "validationScript": "{{検証スクリプト名（LLM Taskのみ）}}"
    }
  ],
  "phases": [
    {
      "name": "{{フェーズ名}}",
      "tasks": ["{{タスク名}}"],
      "type": "{{llm|script|mixed}}"
    }
  ],
  "parallelGroups": [
    {
      "name": "{{グループ名}}",
      "tasks": ["{{並列実行するタスク}}"],
      "syncPoint": "{{同期ポイントのタスク名}}"
    }
  ],
  "anchors": [],
  "trigger": {}
}
```

### 5.3 出力検証

```bash
node scripts/validate_workflow.js --input .tmp/workflow.json
```
