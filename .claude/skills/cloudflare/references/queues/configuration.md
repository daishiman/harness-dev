# Queues Configuration(索引)

設定項目は変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/queues/` を直接取得する。

最小 binding(`wrangler.jsonc`、producer + push consumer):

```jsonc
{
  "queues": {
    "producers": [{ "queue": "my-queue", "binding": "MY_QUEUE" }],
    "consumers": [
      { "queue": "my-queue", "max_batch_size": 10, "max_retries": 3, "dead_letter_queue": "my-dlq" }
    ]
  }
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| queue 作成(retention、delivery delay) | `wrangler queues create` |
| producer binding(`delivery_delay`) | `Queues configuration producers` |
| push consumer(`max_batch_size` / `max_batch_timeout` / `max_retries` / `retry_delay` / DLQ) | `Queues consumer configuration` |
| pull consumer(`type: "http_pull"`、`visibility_timeout_ms`) | `Queues pull consumer configuration` |
| `Env` 型と `satisfies ExportedHandler` | `Queues TypeScript types` |
| contentType(`json` / `v8` / `text` / `bytes`)の選び方 | `Queues message content type` |

作成・一覧・consumer 追加削除・pause / purge の CLI は `../../../wrangler/references/queues-workflows-pipelines.md` が正本。経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。
