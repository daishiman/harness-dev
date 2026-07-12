# ワークフローパターン

> **読み込み条件**: ワークフロー設計時、タスク構成決定時
> **相対パス**: `references/workflow-patterns.md`

---

## パターン一覧

| パターン       | 用途                       | 記号      |
| -------------- | -------------------------- | --------- |
| シーケンシャル | 依存関係のある順次処理     | `→`       |
| 並列実行       | 独立した同時処理           | `∥`       |
| 条件分岐       | 状況に応じた処理選択       | `◇`       |
| ループ         | 繰り返し処理               | `↺`       |
| Fan-out/Fan-in | 展開と集約                 | `⊂ ⊃`     |
| パイプライン   | ストリーム処理             | `⟹`       |
| Phase ベース   | フェーズ区切りの大規模処理 | `Phase N` |

---

## 1. シーケンシャル（Sequential）

依存関係のあるタスクを順次実行する基本パターン。

```
A → B → C → D
```

**使用場面**:
- データベースマイグレーション
- ビルド＆デプロイパイプライン
- 依存関係のあるAPI呼び出し

**JSON定義**:
```json
{
  "pattern": "sequential",
  "tasks": [
    { "name": "task-a", "dependsOn": [] },
    { "name": "task-b", "dependsOn": ["task-a"] },
    { "name": "task-c", "dependsOn": ["task-b"] }
  ]
}
```

---

## 2. 並列実行（Parallel）

独立したタスクを同時に実行し、効率を最大化するパターン。

```
      ┌─ Task A ─┐
Start ├─ Task B ─┼─ Sync
      └─ Task C ─┘
```

**使用場面**:
- 複数の独立した分析
- 並列データ取得
- テストの並列実行

**JSON定義**:
```json
{
  "pattern": "parallel",
  "parallelGroups": [{
    "name": "analysis-group",
    "tasks": ["task-a", "task-b", "task-c"],
    "syncPoint": "aggregate-task"
  }]
}
```

---

## 3. 条件分岐（Conditional）

入力や状態に応じて異なるワークフローを選択するパターン。

```
         ┌─ Task B (条件A)
Task A ──┤
         └─ Task C (条件B)
```

**使用場面**:
- タイプ別処理
- エラーハンドリング
- モード別実行

**JSON定義**:
```json
{
  "pattern": "conditional",
  "tasks": [
    { "name": "task-b", "condition": "type === 'api-client'", "dependsOn": ["task-a"] },
    { "name": "task-c", "condition": "type === 'git-ops'", "dependsOn": ["task-a"] }
  ]
}
```

---

## 4. ループ処理（Loop）

コレクションの各要素や条件を満たすまで繰り返し処理するパターン。

### For-Each ループ
```
items[] → ↺ process-item → results[]
```

### While ループ
```
init → ↺ [condition?] → process → update → done
```

**使用場面**:
- バッチ処理
- リトライ処理
- 品質改善ループ

**JSON定義**:
```json
{
  "pattern": "loop",
  "tasks": [{
    "name": "task-a",
    "loopCondition": "quality < 0.9",
    "maxIterations": 5
  }]
}
```

---

## 5. Fan-out / Fan-in（集約）

単一入力を複数に展開し、処理後に集約するパターン。

```
        ⊂ Fan-out ⊃
       /     |     \
      A      B      C
       \     |     /
        ⊂ Fan-in ⊃
```

**使用場面**:
- 大規模データの分割処理
- MapReduceパターン
- 並列結果の統合

**JSON定義**:
```json
{
  "tasks": [{
    "name": "aggregate-task",
    "dependsOn": ["task-a", "task-b", "task-c"],
    "aggregation": { "strategy": "merge" }
  }]
}
```

---

## 6. パイプライン（Pipeline）

データがステージを通過しながら変換されるパターン。

```
input ⟹ validate ⟹ transform ⟹ enrich ⟹ output
```

**使用場面**:
- ETL（Extract-Transform-Load）処理
- コンパイルパイプライン
- データ検証フロー

---

## 7. Phase ベースワークフロー

大規模タスクを明確なフェーズに分割するパターン。

```
Phase 1: 分析 → Phase 2: 設計 → Phase 3: 実装 → Phase 4: 検証
```

**使用場面**:
- スキル作成ワークフロー
- 機能開発サイクル
- 移行プロジェクト

**JSON定義**:
```json
{
  "pattern": "phase-based",
  "phases": [
    { "name": "Phase 1: 分析", "type": "llm", "tasks": ["analyze-request"] },
    { "name": "Phase 2: 設計", "type": "mixed", "tasks": ["design-workflow", "validate"] },
    { "name": "Phase 3: 生成", "type": "script", "tasks": ["generate-files"] }
  ]
}
```

---

## パターン選定ガイド

| タスクの特性                 | 推奨パターン       |
| ---------------------------- | ------------------ |
| 順序が重要、依存関係あり     | シーケンシャル     |
| 独立した複数タスク           | 並列実行           |
| 条件によって処理が変わる     | 条件分岐           |
| コレクションの各要素を処理   | ループ             |
| 大規模データの分散処理       | Fan-out/Fan-in     |
| データ変換の連鎖             | パイプライン       |
| 複数の独立したフェーズがある | Phase ベース       |

### 判断フローチャート

```
Q1: タスクは独立して実行可能か？
├─ Yes → 並列実行 or Fan-out/Fan-in
└─ No  → Q2: 条件による分岐があるか？
          ├─ Yes → 条件分岐
          └─ No  → Q3: 繰り返し処理があるか？
                    ├─ Yes → ループ
                    └─ No  → シーケンシャル or パイプライン
```

---

## タスクタイプ別推奨

### LLM Task 向き
| パターン | 適合度 | 理由 |
|----------|--------|------|
| Sequential | ◎ | 段階的な思考 |
| Parallel | ○ | 独立した分析 |
| Conditional | ○ | 判断による分岐 |
| Loop | △ | トークン消費大 |

### Script Task 向き
| パターン | 適合度 | 理由 |
|----------|--------|------|
| Sequential | ◎ | 依存関係明確 |
| Parallel | ◎ | 独立処理の並列化 |
| Loop | ◎ | バッチ処理に最適 |
| Pipeline | ◎ | 変換チェーン |

---

## Task分割の判断基準

### 分割すべき場合
- 思考ログが肥大する場合
- フェーズ間で責務が異なる場合
- 並列実行の恩恵を受ける場合

### 分割しない場合
- 単純なタスク（ステップが3未満）
- 入出力が曖昧
- コンテキスト共有が必須

---

## 記号凡例

| 記号    | 意味             |
| ------- | ---------------- |
| `→`     | シーケンシャル   |
| `∥`     | 並列実行         |
| `◇`     | 条件分岐         |
| `↺`     | ループ           |
| `⊂ ⊃`   | Fan-out/Fan-in   |
| `⟹`     | パイプライン     |
