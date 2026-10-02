# KV API(索引)

API シグネチャと戻り値の形は変わるため同梱しない。`cloudflare-docs` MCP で検索して最新を取得する。不通時は `https://developers.cloudflare.com/kv/` を直接取得する。

| やりたいこと | docs MCP の検索語 |
|---|---|
| 読み取り(`get` の型指定 text/json/arrayBuffer/stream、`cacheTtl`) | `kv get cacheTtl type` |
| 複数 key の一括読み取り(≤100 key で 1 operation) | `kv bulk get` |
| 書き込み(`expiration` / `expirationTtl` / `metadata`) | `kv put expiration metadata` |
| metadata 付き取得 | `kv getWithMetadata` |
| 削除・一覧(`prefix`、`cursor` ページング) | `kv delete list prefix cursor` |
| エラー(429 write rate、413 value size) | `kv errors rate limit 429` |
| Worker 外からの REST / bulk 操作 | `kv rest api bulk` |

最小例:

```typescript
await env.MY_KV.put("session:abc", JSON.stringify(session), { expirationTtl: 3600 });
const value = await env.MY_KV.get("session:abc");                       // string | null
const config = await env.MY_KV.get<AppConfig>("config", "json");        // AppConfig | null
const many = await env.MY_KV.get(["user:1", "user:2"]);                  // Map<string, string | null>
```

経験知は [gotchas.md](./gotchas.md)(eventual consistency、負の cache、429)/ [patterns.md](./patterns.md)(多段 cache、session、prefix 設計)を読む。
