# 並列実行ガイド

> **読み込み条件**: 並列実行設計時
> **相対パス**: `references/parallel-execution-guide.md`

---

## 概要

並列実行は、複数のスキルを同時に実行して効率を上げる機能。

### ユースケース

- 複数APIからのデータ取得
- バッチ処理の並列化
- マルチソースの集約
- 独立したタスクの同時実行

---

## 基本構文

```yaml
parallel:
  - id: parallel-group-1
    skills:
      - skill: api-client-a
        args:
          url: "https://api-a.example.com"
      - skill: api-client-b
        args:
          url: "https://api-b.example.com"
      - skill: api-client-c
        args:
          url: "https://api-c.example.com"
    aggregate: merge
    max_concurrency: 3
    fail_fast: false
```

---

## 設定オプション

### max_concurrency

同時実行数の上限。リソース制限やAPI制限がある場合に使用。

```yaml
# 10個のタスクを最大3つずつ実行
max_concurrency: 3
# 実行順: [task1,2,3] → [task4,5,6] → [task7,8,9] → [task10]
```

### fail_fast

1つでも失敗したら全体を停止するか。

```yaml
fail_fast: true   # 1つ失敗で全停止（デフォルト: false）
fail_fast: false  # 失敗しても他は続行
```

### aggregate

結果の集約方法。

| 値 | 説明 | 出力形式 |
|---|------|---------|
| `all` | 全結果を配列で返す | `[result1, result2, ...]` |
| `merge` | 結果をマージ | `{...result1, ...result2}` |
| `first` | 最初に完了した結果 | `result` |
| `any` | 成功した最初の結果 | `result` |

---

## 集約戦略詳細

### all（デフォルト）

```yaml
aggregate: all

# 入力
skills:
  - skill: task-a  # 出力: { data: "A" }
  - skill: task-b  # 出力: { data: "B" }

# 結果
output: [
  { id: "task-a", status: "success", output: { data: "A" } },
  { id: "task-b", status: "success", output: { data: "B" } }
]
```

### merge

```yaml
aggregate: merge
merge_strategy: shallow  # shallow | deep | array

# shallow（デフォルト）
# task-a: { users: [1,2] }
# task-b: { posts: [3,4] }
# 結果: { users: [1,2], posts: [3,4] }

# deep
# task-a: { data: { users: [1,2] } }
# task-b: { data: { posts: [3,4] } }
# 結果: { data: { users: [1,2], posts: [3,4] } }

# array
# task-a: { items: [1,2] }
# task-b: { items: [3,4] }
# 結果: { items: [1,2,3,4] }
```

### first

```yaml
aggregate: first
# 最初に完了したタスクの結果を返す
# 他のタスクはキャンセル（オプション）

cancel_on_first: true  # 最初の完了で他をキャンセル
```

### any

```yaml
aggregate: any
# 最初に成功したタスクの結果を返す
# 失敗は無視して次を待つ
```

---

## 高度なパターン

### 1. 依存関係のある並列実行

```yaml
flow:
  - id: prepare
    skill: data-preparer

  - id: parallel-process
    parallel:
      skills:
        - skill: processor-a
          args:
            data: "{{prepare.output.chunk_a}}"
        - skill: processor-b
          args:
            data: "{{prepare.output.chunk_b}}"
    depends_on: [prepare]

  - id: finalize
    skill: result-finalizer
    depends_on: [parallel-process]
    args:
      results: "{{parallel-process.output}}"
```

### 2. 動的並列実行

```yaml
flow:
  - id: get-items
    skill: item-fetcher
    # 出力: { items: ["item1", "item2", "item3", ...] }

  - id: process-each
    skill: item-processor
    parallel:
      for_each: "{{get-items.output.items}}"
      item_var: "item"
      args:
        target: "{{item}}"
    max_concurrency: 5
```

### 3. 条件付き並列実行

```yaml
parallel:
  skills:
    - skill: fast-source
      args: { ... }
      timeout: 5

    - skill: slow-source
      args: { ... }
      timeout: 30
      required: false  # オプショナル

    - skill: backup-source
      args: { ... }
      condition: "{{fast-source.status}} == 'failed'"
```

---

## エラーハンドリング

### 部分的失敗の処理

```yaml
parallel:
  skills:
    - skill: task-a
      required: true   # 必須（失敗で全体失敗）
    - skill: task-b
      required: false  # オプション（失敗しても続行）
    - skill: task-c
      required: false

  on_partial_failure:
    action: continue   # continue | abort
    include_failed: true  # 失敗結果も出力に含める
```

### リトライ設定

```yaml
parallel:
  skills:
    - skill: flaky-api
      retry:
        enabled: true
        max_attempts: 3
        delay: 1000  # ms
        backoff: exponential
```

---

## パフォーマンス考慮事項

### 1. 適切な同時実行数

```yaml
# API制限がある場合
max_concurrency: 5  # レート制限に合わせる

# CPU集約的な処理
max_concurrency: 4  # CPUコア数に合わせる

# I/O集約的な処理
max_concurrency: 20  # より多く設定可能
```

### 2. タイムアウト設定

```yaml
parallel:
  timeout: 60  # 全体のタイムアウト
  skills:
    - skill: fast-task
      timeout: 5
    - skill: slow-task
      timeout: 30
```

### 3. メモリ考慮

```yaml
# 大量データの並列処理
parallel:
  max_concurrency: 3  # メモリ使用量を制限
  skills:
    # 各タスクが大量メモリを使う場合
```

---

## ベストプラクティス

| すべきこと | 避けるべきこと |
|-----------|---------------|
| 独立したタスクのみ並列化 | 依存関係のあるタスクを並列化 |
| 適切なmax_concurrencyを設定 | 無制限の並列実行 |
| タイムアウトを設定 | タイムアウトなしの外部呼び出し |
| 失敗時の動作を明示 | デフォルト動作に依存 |
| required: falseでオプション化 | 全タスク必須での脆弱な設計 |

---

## 関連リソース

- [orchestration-guide.md](orchestration-guide.md) - オーケストレーション全体ガイド
- [skill-chain-patterns.md](skill-chain-patterns.md) - チェーンパターン集
- [schemas/parallel-execution.json](../schemas/parallel-execution.json) - スキーマ定義
