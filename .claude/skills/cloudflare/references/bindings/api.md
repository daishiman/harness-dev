# Bindings API(索引)

binding 型と各 API の形は変わるため同梱しない。`cloudflare-docs` MCP で検索し、型は `pnpm wrangler types` の生成結果を正とする。不通時は `https://developers.cloudflare.com/workers/runtime-apis/bindings/`。

| やりたいこと | docs MCP の検索語 |
|---|---|
| `Env` interface を生成する | `wrangler types` |
| config key と TypeScript 型の対応(`kv_namespaces`→`KVNamespace` 等) | `workers-types bindings` |
| handler / Hono から binding を使う | `workers fetch handler env` / `hono bindings` |
| KV / R2 / D1 / Queues / DO / AI / Service の呼び出し | `KV binding api` / `R2 binding api` / `D1 client api` / `queues producer send` / `durable objects stub` / `workers ai run` / `service bindings` |
| `@cloudflare/workers-types` と `wrangler types` の役割の違い | `workers-types package` |

最小例:

```typescript
import type { Env } from './.wrangler/types/runtime';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const value = await env.MY_KV.get('key');
    return new Response(value ?? 'not found');
  },
};
```

経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。
