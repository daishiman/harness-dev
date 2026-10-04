# Workers Configuration(索引)

設定項目と許容値は変わるため同梱しない。`cloudflare-docs` MCP で検索するか `node_modules/wrangler/config-schema.json` を読む。不通時は `https://developers.cloudflare.com/workers/wrangler/configuration/`。

最小 `wrangler.jsonc`:

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "my-worker",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01", // 新規 project は当日
  "compatibility_flags": ["nodejs_compat"],
  "observability": { "enabled": true, "head_sampling_rate": 0.1 },
  "vars": { "ENVIRONMENT": "production" },
  "d1_databases": [{ "binding": "DB", "database_name": "my-db", "database_id": "xyz789" }]
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| bindings 全種の書式 | `wrangler configuration bindings`(一覧は `../bindings/configuration.md`) |
| `env` による staging / production 分離と継承ルール | `wrangler configuration environments` |
| secrets | `wrangler secret put` |
| routes / cron triggers | `wrangler configuration routes` / `cron triggers` |
| TypeScript 型生成 | `wrangler types` |
| `nodejs_compat` / smart placement / observability | `nodejs_compat` / `smart placement` / `workers observability` |

作成・deploy・型生成・ローカル開発の CLI は `../../../wrangler/references/config.md` / `deploy.md` / `dev-local.md` が正本。経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。
