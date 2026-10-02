# D1 API(索引)

API シグネチャと戻り値の形は変わるため同梱しない。`cloudflare-docs` MCP で検索して最新を取得する。不通時は `https://developers.cloudflare.com/d1/` を直接取得する。

| やりたいこと | docs MCP の検索語 |
|---|---|
| prepared statement / `bind()` / `.all()` `.first()` `.run()` `.raw()` | `d1 workers binding api prepare bind` |
| 複数クエリを 1 往復・atomic に実行 | `d1 batch transaction` |
| 30 秒を超える長時間処理(Sessions API) | `d1 sessions api withSession` |
| 読み取りレプリカ / read-after-write の整合 | `d1 read replication` |
| エラー種別と `meta`(duration, rows_read, rows_written) | `d1 query error handling meta` |
| Worker 外(CI・管理スクリプト)からの HTTP アクセス | `d1 rest api query endpoint` |
| Vitest / ローカル検証 | `d1 testing vitest wrangler dev` |

最小例(prepared statement は SQL injection 対策として必須):

```typescript
// ❌ 文字列補間しない: env.DB.prepare(`... WHERE id = ${userId}`)
const { results, success, meta } = await env.DB
  .prepare('SELECT * FROM users WHERE email = ? AND active = ?')
  .bind(email, true)
  .all();
const user = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(userId).first();
```

経験知は [gotchas.md](./gotchas.md)(エラー・制限の読み方)/ [patterns.md](./patterns.md)(pagination、bulk、multi-tenant、replica、sessions)を読む。
