# スキルチェーンパターン集

> **読み込み条件**: スキルチェーン設計時
> **相対パス**: `references/skill-chain-patterns.md`

---

## 基本パターン

### 1. シンプルパイプライン

```yaml
name: simple-pipeline
description: "入力→処理→出力の基本パターン"

steps:
  - id: input
    skill: file-reader
    args:
      path: "{{trigger.file_path}}"

  - id: process
    skill: data-transformer
    input_mapping:
      data: "{{input.output.content}}"

  - id: output
    skill: file-writer
    input_mapping:
      content: "{{process.output}}"
      path: "./output/result.json"
```

**ユースケース**: ETL、ファイル変換、データマイグレーション

---

### 2. フィルター＆マップ

```yaml
name: filter-map
description: "データをフィルタリングして変換"

steps:
  - id: fetch
    skill: api-client
    args:
      url: "https://api.example.com/items"

  - id: filter
    skill: data-filter
    input_mapping:
      items: "{{fetch.output.body.items}}"
    args:
      condition: "item.status == 'active'"

  - id: map
    skill: data-mapper
    input_mapping:
      items: "{{filter.output}}"
    args:
      transform: |
        {
          id: item.id,
          name: item.title.toUpperCase(),
          url: `https://example.com/${item.slug}`
        }
```

**ユースケース**: APIデータ加工、レポート前処理

---

### 3. 分岐後合流

```yaml
name: branch-merge
description: "条件で分岐し、最後に合流"

steps:
  - id: check
    skill: condition-checker
    args:
      input: "{{trigger.data}}"

  - id: path-a
    skill: processor-a
    condition:
      expression: "{{check.output.type}} == 'typeA'"
    input_mapping:
      data: "{{trigger.data}}"

  - id: path-b
    skill: processor-b
    condition:
      expression: "{{check.output.type}} == 'typeB'"
    input_mapping:
      data: "{{trigger.data}}"

  - id: merge
    skill: result-merger
    depends_on: [path-a, path-b]
    input_mapping:
      result_a: "{{path-a.output}}"
      result_b: "{{path-b.output}}"
```

**ユースケース**: マルチフォーマット処理、A/B処理

---

### 4. ファンアウト＆ファンイン

```yaml
name: fan-out-fan-in
description: "1対多に展開し、結果を集約"

steps:
  - id: split
    skill: data-splitter
    args:
      input: "{{trigger.items}}"
      chunk_size: 10

  - id: process
    skill: batch-processor
    input_mapping:
      chunks: "{{split.output.chunks}}"
    parallel: true
    max_concurrency: 5

  - id: aggregate
    skill: result-aggregator
    depends_on: [process]
    input_mapping:
      results: "{{process.output}}"
    args:
      strategy: "merge"
```

**ユースケース**: 大量データ並列処理、バッチジョブ

---

## 応用パターン

### 5. リトライ付きAPI呼び出し

```yaml
name: resilient-api-call
description: "エラー時にリトライする堅牢なAPI呼び出し"

steps:
  - id: call-api
    skill: api-client
    args:
      url: "{{context.api_url}}"
      method: "POST"
      body: "{{trigger.data}}"
    retry:
      count: 3
      delay: 5
      backoff: exponential
    on_failure: handle-error

  - id: handle-error
    skill: error-handler
    condition:
      expression: "{{call-api.status}} == 'failed'"
    args:
      error: "{{call-api.error}}"
      fallback_action: "queue"
```

**ユースケース**: 外部API連携、決済処理

---

### 6. 承認フロー

```yaml
name: approval-workflow
description: "人間の承認を待つワークフロー"

steps:
  - id: prepare
    skill: document-generator
    args:
      template: "approval-request"
      data: "{{trigger.request}}"

  - id: notify
    skill: notification-sender
    input_mapping:
      document: "{{prepare.output}}"
    args:
      channel: "slack"
      message: "承認をお願いします"

  - id: wait-approval
    skill: approval-waiter
    args:
      timeout: 86400  # 24時間
      approval_url: "{{prepare.output.approval_url}}"

  - id: on-approved
    skill: request-processor
    condition:
      expression: "{{wait-approval.output.status}} == 'approved'"
    input_mapping:
      request: "{{trigger.request}}"

  - id: on-rejected
    skill: rejection-handler
    condition:
      expression: "{{wait-approval.output.status}} == 'rejected'"
    args:
      reason: "{{wait-approval.output.reason}}"
```

**ユースケース**: 経費申請、デプロイ承認

---

### 7. サガパターン（補償トランザクション）

```yaml
name: saga-pattern
description: "分散トランザクションの補償処理"

steps:
  - id: create-order
    skill: order-service
    args:
      action: "create"
      data: "{{trigger.order}}"
    on_failure: compensate-order

  - id: reserve-inventory
    skill: inventory-service
    depends_on: [create-order]
    args:
      action: "reserve"
      items: "{{trigger.order.items}}"
    on_failure: compensate-inventory

  - id: process-payment
    skill: payment-service
    depends_on: [reserve-inventory]
    args:
      action: "charge"
      amount: "{{trigger.order.total}}"
    on_failure: compensate-payment

  # 補償アクション（逆順で実行）
  - id: compensate-payment
    skill: payment-service
    args:
      action: "refund"

  - id: compensate-inventory
    skill: inventory-service
    depends_on: [compensate-payment]
    args:
      action: "release"

  - id: compensate-order
    skill: order-service
    depends_on: [compensate-inventory]
    args:
      action: "cancel"
```

**ユースケース**: ECサイト注文、予約システム

---

### 8. イベントソーシング

```yaml
name: event-sourcing
description: "イベントを記録し、状態を再構築"

steps:
  - id: record-event
    skill: event-store
    args:
      stream: "{{trigger.aggregate_id}}"
      event_type: "{{trigger.event_type}}"
      payload: "{{trigger.data}}"

  - id: project
    skill: projection-builder
    depends_on: [record-event]
    args:
      aggregate_id: "{{trigger.aggregate_id}}"
      event: "{{record-event.output}}"

  - id: update-read-model
    skill: read-model-updater
    depends_on: [project]
    input_mapping:
      projection: "{{project.output}}"

  - id: publish
    skill: event-publisher
    depends_on: [record-event]
    args:
      event: "{{record-event.output}}"
      topics: ["notifications", "analytics"]
```

**ユースケース**: 監査ログ、CQRS

---

## パターン選択ガイド

| 要件 | 推奨パターン |
|------|-------------|
| シンプルなデータ変換 | シンプルパイプライン |
| データのフィルタ・加工 | フィルター＆マップ |
| 条件による処理分岐 | 分岐後合流 |
| 大量データの並列処理 | ファンアウト＆ファンイン |
| 外部API連携 | リトライ付きAPI呼び出し |
| 人間の介入が必要 | 承認フロー |
| 分散システム | サガパターン |
| 監査・履歴管理 | イベントソーシング |

---

## 関連リソース

- [orchestration-guide.md](orchestration-guide.md) - オーケストレーション全体ガイド
- [parallel-execution-guide.md](parallel-execution-guide.md) - 並列実行詳細
- [schemas/skill-chain.json](../schemas/skill-chain.json) - スキーマ定義
