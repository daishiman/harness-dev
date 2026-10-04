# Bindings Configuration(索引)

binding ごとの key 名は変わるため同梱しない。`cloudflare-docs` MCP で検索するか `node_modules/wrangler/config-schema.json` を読む。不通時は `https://developers.cloudflare.com/workers/wrangler/configuration/`。

最小 `wrangler.jsonc`(既定スタック分):

```jsonc
{
  "vars": { "API_URL": "https://api.example.com" },
  "kv_namespaces": [{ "binding": "CACHE", "id": "abc123", "preview_id": "dev-id" }],
  "r2_buckets": [{ "binding": "ASSETS", "bucket_name": "my-assets" }],
  "d1_databases": [{ "binding": "DB", "database_name": "my-db", "database_id": "xyz789" }],
  "services": [{ "binding": "AUTH", "service": "auth-worker" }],
  "queues": {
    "producers": [{ "binding": "MY_QUEUE", "queue": "my-queue" }],
    "consumers": [{ "queue": "my-queue", "max_batch_size": 10 }]
  }
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| storage bindings(KV / R2 / D1 / DO / Vectorize / Queues) | `wrangler configuration kv_namespaces` など製品名 + `binding` |
| compute bindings(services / ai / browser / workflows) | `service bindings configuration` / `workers ai binding` |
| platform bindings(analytics engine / mtls / hyperdrive / rate limiting) | `analytics_engine_datasets` / `mtls_certificates` / `hyperdrive binding` / `rate limiting binding` |
| vars / secrets / text_blobs / data_blobs / wasm_modules | `wrangler configuration vars` / `wrangler secret put` |
| `env` ごとの上書きと `preview_id` | `wrangler configuration environments` / `preview_id` |

resource の作成・一覧・型生成の CLI は `../../../wrangler/references/config.md` と各製品ファイル(`d1.md` / `kv-r2.md` / `queues-workflows-pipelines.md`)が正本。経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。
