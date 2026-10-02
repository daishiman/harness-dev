# Queues・Workflows・Pipelines

## Queues

### キューの管理

```bash
# キューを作成
pnpm wrangler queues create my-queue

# 一覧
pnpm wrangler queues list

# 削除
pnpm wrangler queues delete my-queue

# キューにコンシューマーを追加
pnpm wrangler queues consumer add my-queue my-worker

# コンシューマーを削除
pnpm wrangler queues consumer remove my-queue my-worker
```

### 設定バインディング

```jsonc
{
  "queues": {
    "producers": [
      { "binding": "MY_QUEUE", "queue": "my-queue" }
    ],
    "consumers": [
      {
        "queue": "my-queue",
        "max_batch_size": 10,
        "max_batch_timeout": 30
      }
    ]
  }
}
```

---

## Workflows

### ワークフローの管理

```bash
# 一覧
pnpm wrangler workflows list

# 詳細を表示
pnpm wrangler workflows describe my-workflow

# インスタンスをトリガー
pnpm wrangler workflows trigger my-workflow

# パラメータ付きでトリガー
pnpm wrangler workflows trigger my-workflow --params '{"key": "value"}'

# 削除
pnpm wrangler workflows delete my-workflow
```

### インスタンスの管理

```bash
# インスタンス一覧
pnpm wrangler workflows instances list my-workflow

# インスタンスの詳細
pnpm wrangler workflows instances describe my-workflow <INSTANCE_ID>

# インスタンスを終了
pnpm wrangler workflows instances terminate my-workflow <INSTANCE_ID>
```

### 設定バインディング

```jsonc
{
  "workflows": [
    {
      "binding": "MY_WORKFLOW",
      "name": "my-workflow",
      "class_name": "MyWorkflow"
    }
  ]
}
```

---

## Pipelines

### パイプラインの管理

```bash
# 作成
pnpm wrangler pipelines create my-pipeline --r2 my-bucket

# 一覧
pnpm wrangler pipelines list

# 詳細を表示
pnpm wrangler pipelines show my-pipeline

# 更新
pnpm wrangler pipelines update my-pipeline --batch-max-mb 100

# 削除
pnpm wrangler pipelines delete my-pipeline
```

### 設定バインディング

```jsonc
{
  "pipelines": [
    { "binding": "MY_PIPELINE", "pipeline": "my-pipeline" }
  ]
}
```
