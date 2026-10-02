# D1 Configuration(索引)

設定項目の正本は docs と `node_modules/wrangler/config-schema.json`。`cloudflare-docs` MCP で検索して最新を取得する。不通時は `https://developers.cloudflare.com/d1/` を直接取得する。

`wrangler.jsonc` の最小 binding:

```jsonc
{
  "d1_databases": [
    {
      "binding": "DB",                    // env.DB
      "database_name": "your-db-name",
      "database_id": "your-database-id",  // wrangler d1 create の出力
      "migrations_dir": "migrations"      // 省略時も "migrations"
    }
  ]
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| binding・複数 DB・read replica 用 binding | `d1 wrangler configuration d1_databases` |
| `Env` 型(`D1Database`)と `wrangler types` | `d1 typescript types` |
| migrations の作成・適用・追跡(`d1_migrations` テーブル) | `d1 migrations` |
| index 設計(複合・covering・partial) | `d1 indexes best practices` |
| Drizzle ORM(`driver: 'd1-http'`) | `d1 drizzle orm` |
| export / import / Time Travel | `d1 export import time travel` |
| ローカル開発(`--persist-to`)・上限・料金 | `d1 local development` / `d1 limits` / `d1 pricing` |

作成・一覧・migration 適用・export などの CLI は `../../../wrangler/references/d1.md` が正本。migration の運用ルール(`--local` → `--remote`、単発 `execute` 禁止)は `cloudflare-secure-deploy` Skill §4 に従う。落とし穴は [gotchas.md](./gotchas.md)、設計パターンは [patterns.md](./patterns.md)。
