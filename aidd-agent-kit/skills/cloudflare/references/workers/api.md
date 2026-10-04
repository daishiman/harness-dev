# Workers API(索引)

API シグネチャは変わるため同梱しない。`cloudflare-docs` MCP で検索して最新を取得する。不通時は `https://developers.cloudflare.com/workers/runtime-apis/`。

| やりたいこと | docs MCP の検索語 |
|---|---|
| HTTP handler を書く | `workers fetch handler` |
| 応答後に処理を続ける | `ExecutionContext waitUntil`(`passThroughOnException` は `workers-best-practices` で禁止) |
| KV / R2 / D1 / Queues / secrets を `env` から使う | `workers bindings env` (各製品の `../<product>/README.md` も参照) |
| D1 の read-after-write 一貫性 | `D1 sessions API withSession` |
| Edge cache を使う | `workers cache API caches.default` |
| HTML を書き換える | `HTMLRewriter` |
| WebSocket / hibernation | `WebSocketPair` / `Durable Objects WebSocket hibernation` |
| Durable Objects RPC | `Durable Objects RPC methods`(実装は `durable-objects` Skill) |
| cron / queue / tail handler | `scheduled handler` / `queue handler` / `tail handler` |
| Worker 間呼び出し | `service bindings RPC` |

最小例:

```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    ctx.waitUntil(logAnalytics(request)); // 背景処理は await しない
    return Response.json({ ok: true });
  },
};
```

経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md) / [frameworks.md](./frameworks.md)。
