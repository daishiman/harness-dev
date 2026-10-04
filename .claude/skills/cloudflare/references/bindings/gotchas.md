# Binding Gotchas and Troubleshooting

## Critical: Global Scope Mutation

### ❌ THE #1 GOTCHA: Caching env in Global Scope

```typescript
// ❌ DANGEROUS - env cached at deploy time
const apiKey = env.API_KEY;  // ERROR: env not available in global scope

export default {
  async fetch(request: Request, env: Env) {
    // Uses undefined or stale value!
  }
}
```

**Why it breaks:**
- `env` not available in global scope
- If using workarounds, secrets may not update without redeployment
- Leads to "Cannot read property 'X' of undefined" errors

**✅ Always access env per-request:**
```typescript
export default {
  async fetch(request: Request, env: Env) {
    const apiKey = env.API_KEY;  // Fresh every request
  }
}
```

## Common Errors

### "env.MY_KV is undefined"

**Cause:** Name mismatch or not configured  
**Solution:** Check wrangler.jsonc (case-sensitive), run `pnpm wrangler types`, verify `pnpm wrangler kv namespace list`

### "Property 'MY_KV' does not exist on type 'Env'"

**Cause:** Types not generated  
**Solution:** `pnpm wrangler types`

### "preview_id is required for --remote"

**Cause:** Missing preview binding  
**Solution:** Add `"preview_id": "dev-id"` or use `pnpm wrangler dev` (local mode)

### "Secret updated but Worker still uses old value"

**Cause:** Cached in global scope or not redeployed  
**Solution:** Avoid global caching, redeploy after secret change

### "KV get() returns null for existing key"

**Cause:** Eventual consistency (60s), wrong namespace, wrong environment  
**Solution:**
```bash
# Check key exists
pnpm wrangler kv key get --binding=MY_KV "your-key"

# Verify namespace ID
pnpm wrangler kv namespace list

# Check environment
pnpm wrangler deployments list
```

### "D1 database not found"

**Solution:** `pnpm wrangler d1 list`, verify ID in wrangler.jsonc

### "Service binding returns 'No such service'"

**Cause:** Target Worker not deployed, name mismatch, environment mismatch  
**Solution:**
```bash
# List deployed Workers
pnpm wrangler deployments list --name=target-worker

# Check service binding config
cat wrangler.jsonc | grep -A2 services

# Deploy target first
cd ../target-worker && pnpm wrangler deploy
```

### "Rate limit exceeded" on KV writes

**Cause:** >1 write/second per key  
**Solution:** Use different keys, Durable Objects, or Queues

## Type Safety Gotchas

### Missing @cloudflare/workers-types

**Error:** `Cannot find name 'Request'`  
**Solution:** `pnpm add -D @cloudflare/workers-types`, add to tsconfig.json `"types"`

### Binding Type Mismatches

```typescript
// ❌ Wrong - KV returns string | null
const value: string = await env.MY_KV.get('key');

// ✅ Handle null
const value = await env.MY_KV.get('key');
if (!value) return new Response('Not found', { status: 404 });
```

## Environment Gotchas

### Wrong Environment Deployed

**Solution:** Check `pnpm wrangler deployments list`, use `--env` flag

### Secrets Not Per-Environment

**Solution:** Set per environment: `pnpm wrangler secret put API_KEY --env staging`

## Development Gotchas

**wrangler dev vs deploy:**
- dev: Uses `preview_id` or local bindings, secrets not available
- deploy: Uses production `id`, secrets available

**Access secrets in dev:** `pnpm wrangler dev --remote`  
**Persist local data:** `pnpm wrangler dev --persist`

## Performance Gotchas

### Sequential Binding Calls

```typescript
// ❌ Slow
const user = await env.DB.prepare('...').first();
const config = await env.MY_KV.get('config');

// ✅ Parallel
const [user, config] = await Promise.all([
  env.DB.prepare('...').first(),
  env.MY_KV.get('config')
]);
```

## Security Gotchas

**❌ Secrets in logs:** `console.log('Key:', env.API_KEY)` - visible in dashboard  
**✅** `console.log('Key:', env.API_KEY ? '***' : 'missing')`

**❌ Exposing env:** `return Response.json(env)` - exposes all bindings  
**✅** Never return env object in responses

## Limits Reference

| Resource | Limit | Impact | Plan |
|----------|-------|--------|------|
| **Bindings per Worker** | 64 total | All binding types combined | All |
| **Environment variables** | 64 max, 5KB each | Per Worker | All |
| **Secret size** | 1KB | Per secret | All |
| **KV key size** | 512 bytes | UTF-8 encoded | All |
| **KV value size** | 25 MB | Per value | All |
| **KV writes per key** | 1/second | Per key; exceeding = 429 error | All |
| **KV list() results** | 1000 keys | Per call; use cursor for more | All |
| **KV operations** | 1000 reads/day | Free tier only | Free |
| **R2 object size** | 5 TB | Per object | All |
| **R2 operations** | 1M Class A/month free | Writes | All |
| **D1 database size** | 10 GB | Per database | All |
| **D1 rows per query** | 100,000 | Result set limit | All |
| **D1 databases** | 10 | Free tier | Free |
| **Queue batch size** | 100 messages | Per consumer batch | All |
| **Queue message size** | 128 KB | Per message | All |
| **Service binding calls** | Unlimited | Counts toward CPU time | All |
| **Durable Objects** | 1M requests/month free | First 1M | Free |

## Debugging Tips

```bash
# Check configuration
pnpm wrangler deploy --dry-run       # Validate config without deploying
pnpm wrangler kv namespace list      # List KV namespaces
pnpm wrangler secret list            # List secrets (not values)
pnpm wrangler deployments list       # Recent deployments

# Inspect bindings
pnpm wrangler kv key list --binding=MY_KV
pnpm wrangler kv key get --binding=MY_KV "key-name"
pnpm wrangler r2 object get my-bucket/file.txt
pnpm wrangler d1 execute my-db --command="SELECT * FROM sqlite_master"

# Test locally
pnpm wrangler dev                  # Local mode
pnpm wrangler dev --remote         # Production bindings
pnpm wrangler dev --persist        # Persist data across restarts

# Verify types
pnpm wrangler types
cat .wrangler/types/runtime.d.ts | grep "interface Env"

# Debug specific binding issues
pnpm wrangler tail                 # Stream logs in real-time
pnpm wrangler tail --format=pretty # Formatted logs
```

## See Also

- [Workers Limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Wrangler Commands](https://developers.cloudflare.com/workers/wrangler/commands/)

## api.md / configuration.md から移設した注意点

- **`addEventListener('fetch', …)` の旧形式では `env` が届かない**: bindings は Module Worker の `fetch(request, env, ctx)` handler(または Hono の `c.env`)で受け取る。旧形式は使わない。
- **`env: any` にしない**: `wrangler types` が生成する `Env` を使う。`any` は binding 名の typo や型不一致を隠す。
- **`id` を使う binding と `name` を使う binding が混在する**: KV / D1 / Hyperdrive は `id`、R2 は `bucket_name`、Queues / Workflows は `queue` / `name`。取り違えると deploy 時に「resource not found」になる。
- **`wrangler types` の出力先と検出**: `.wrangler/types/runtime.d.ts` へ出る。`tsconfig.json` の `types` に `@cloudflare/workers-types` があり `include` に `.wrangler/types/**/*.ts` があれば自動で拾われる。binding を変えたら再実行する。
- **別 Worker の Durable Object / Service を参照する**: DO は `script_name`、Service binding は `environment` で対象 Worker / env を指定できる。参照先を先に deploy しないと `No such service` になる。
