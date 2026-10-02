# Workers Gotchas

## Common Errors

### "Too much CPU time used"

**Cause:** Worker exceeded CPU time limit (10ms on Free plan, 30s default / 5min max on Paid)  
**Solution:** Use `ctx.waitUntil()` for background work, offload heavy compute to Durable Objects, or consider Workers AI for ML workloads

### "Module-Level State Lost"

**Cause:** Workers are stateless between requests; module-level variables reset unpredictably  
**Solution:** Use KV, D1, or Durable Objects for persistent state; don't rely on module-level variables

### "Body has already been used"

**Cause:** Attempting to read response body twice (bodies are streams)  
**Solution:** Clone response before reading: `response.clone()` or read once and create new Response with the text

### "Node.js module not found"

**Cause:** Node.js built-ins not available by default  
**Solution:** Use Workers APIs (e.g., R2 for file storage) or enable Node.js compat with `"compatibility_flags": ["nodejs_compat"]`

### "Cannot fetch in global scope"

**Cause:** Attempting to use fetch during module initialization  
**Solution:** Move fetch calls inside handler functions (fetch, scheduled, etc.) where they're allowed

### "Subrequest depth limit exceeded"

**Cause:** Too many nested subrequests creating deep call chain  
**Solution:** Flatten request chain or use service bindings for direct Worker-to-Worker communication

### "D1 read-after-write inconsistency"

**Cause:** D1 is eventually consistent; reads may not reflect recent writes  
**Solution:** Use D1 Sessions (2024+) to guarantee read-after-write consistency within a session:

```typescript
const session = env.DB.withSession();
await session.prepare('INSERT INTO users (name) VALUES (?)').bind('Alice').run();
const user = await session.prepare('SELECT * FROM users WHERE name = ?').bind('Alice').first(); // Guaranteed to see Alice
```

**When to use sessions:** Write → Read patterns, transactions requiring consistency

### "wrangler types not generating TypeScript definitions"

**Cause:** Type generation not configured or outdated  
**Solution:** Run `pnpm wrangler types` after changing bindings in wrangler.jsonc:

```bash
pnpm wrangler types  # Generates .wrangler/types/runtime.d.ts
```

Add to `tsconfig.json`: `"include": [".wrangler/types/**/*.ts"]`

Then import: `import type { Env } from './.wrangler/types/runtime';`

### "Durable Object RPC errors with deprecated fetch pattern"

**Cause:** Using old `stub.fetch()` pattern instead of RPC (2024+)  
**Solution:** Export methods directly, call via RPC:

```typescript
// ❌ Old fetch pattern
export class MyDO {
  async fetch(request: Request) {
    const { method } = await request.json();
    if (method === 'increment') return new Response(String(await this.increment()));
  }
  async increment() { return ++this.value; }
}
const stub = env.DO.get(id);
const res = await stub.fetch('http://x', { method: 'POST', body: JSON.stringify({ method: 'increment' }) });

// ✅ RPC pattern (type-safe, no serialization overhead)
export class MyDO {
  async increment() { return ++this.value; }
}
const stub = env.DO.get(id);
const count = await stub.increment(); // Direct method call
```

### "WebSocket connection closes unexpectedly"

**Cause:** Worker reaches CPU limit while maintaining WebSocket connection  
**Solution:** Use WebSocket hibernation (2024+) to offload idle connections:

```typescript
export class WebSocketDO {
  async webSocketMessage(ws: WebSocket, message: string) {
    // Handle message
  }
  async webSocketClose(ws: WebSocket, code: number) {
    // Cleanup
  }
}
```

Hibernation automatically suspends inactive connections, wakes on events

### "Framework middleware not working with Workers"

**Cause:** Framework expects Node.js primitives (e.g., Express uses Node streams)  
**Solution:** Use Workers-native frameworks (Hono, itty-router, Worktop) or adapt middleware:

```typescript
// ✅ Hono (Workers-native)
import { Hono } from 'hono';
const app = new Hono();
app.use('*', async (c, next) => { /* middleware */ await next(); });
```

See [frameworks.md](./frameworks.md) for full patterns

## Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Request size | 100 MB | Maximum incoming request size |
| Response size | Unlimited | Supports streaming |
| CPU time (Free) | 10ms | Free plan |
| CPU time (Paid) | 30s default / 5min max | Configurable via `limits.cpu_ms` |
| Subrequests (Free) | 50 | Per invocation |
| Subrequests (Paid) | 10,000 | Per invocation |
| Subrequest operations (KV, R2, Cache API) | 1,000 | Shared across KV reads, R2 ops, Cache API calls per request |
| KV value size | 25 MiB | Maximum per key |
| Environment variable size | 5 KB | Per variable |

## See Also

- [Patterns](./patterns.md) - Best practices
- [API](./api.md) - Runtime APIs
- [Configuration](./configuration.md) - Setup
- [Frameworks](./frameworks.md) - Hono, routing, validation

## api.md / configuration.md から移設した注意点

- **背景処理は `await` しない**: レスポンス後に続ける処理(ログ送信、cache 書き込み)は `ctx.waitUntil()` に渡す。`await` すると応答が遅れる。
- **Cache API へ入れる Response は `clone()`**: body は 1 回しか読めないため、`ctx.waitUntil(cache.put(request, response.clone()))` のように複製を渡し、元をクライアントへ返す。
- **`env` ごとの継承ルール**: `name` / `main` / `compatibility_date` / `routes` / `workers_dev` は `env.<name>` へ継承されるが、**bindings(`vars`, `kv_namespaces`, `r2_buckets`, `d1_databases` など)は継承されない**。staging 用 env には binding を再宣言する。`migrations` / `keep_vars` / `send_metrics` は top-level のみ。
- **新規 project の `compatibility_date` は当日**: 古い日付を写すと新しい runtime 挙動が有効にならない。
- **Secrets は config に書かない**: `pnpm wrangler secret put <NAME>` で登録し、`env.<NAME>` で読む。
- **Automatic provisioning(beta)**: `id` を書かない `kv_namespaces` 等は deploy 時に自動作成される。意図しない resource 作成を避けるため、既存 resource を使うときは必ず `id` を明記する。
- **`nodejs_compat` の代償**: `Buffer` / `process.env` / `node:` import が使えるが、cold start が約 1〜2ms 増える。Workers API(R2 / KV)で足りる場面では有効化しない。
