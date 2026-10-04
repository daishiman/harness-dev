# Workflows Configuration(索引)

設定項目の既定値・上限は変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/workflows/`。

最小 binding 例(`wrangler.jsonc`):

```jsonc
{
  "compatibility_date": "2025-01-01",   // Workflows binding は 2024-10-22 以上が必要
  "observability": { "enabled": true }, // Workflows dashboard と structured logs
  "workflows": [
    { "name": "my-workflow", "binding": "MY_WORKFLOW", "class_name": "MyWorkflow" }
  ]
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| binding・`limits.steps`・`limits.cpu_ms` | `workflows wrangler configuration limits` |
| step ごとの retry / timeout 設定 | `workflows WorkflowStepConfig retries backoff` |
| 並列・条件分岐・ループの step 構成 | `workflows parallel steps Promise.all deterministic` |
| 複数 Workflow の定義 | `workflows multiple workflows wrangler` |
| 別 Worker の Workflow を呼ぶ(`script_name`) | `workflows cross-script binding script_name` |
| Workflow から他 binding(KV / D1 / R2 / AI)を使う | `workflows this.env bindings` |
| Pages Functions から起動する | `workflows pages functions service binding` |

作成・一覧・trigger・instance 操作の CLI は [`../../../wrangler/references/queues-workflows-pipelines.md`](../../../wrangler/references/queues-workflows-pipelines.md) が正本。

経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。API は [api.md](./api.md)。
