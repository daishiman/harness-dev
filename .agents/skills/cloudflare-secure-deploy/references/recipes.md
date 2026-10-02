# レシピ別 完全設定スニペット(実プロジェクト検証済み)

## レシピA: Next.js + OpenNext

出典: 不動産マッチングシステム / SHIPPING FLOW OPTIMIZATION

```jsonc
// wrangler.jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "app-name",
  "main": ".open-next/worker.js",
  "compatibility_date": "2026-07-16",
  "compatibility_flags": ["nodejs_compat"],
  "observability": { "enabled": true },
  "upload_source_maps": true,
  "assets": { "directory": ".open-next/assets", "binding": "ASSETS" },
  "d1_databases": [{ "binding": "DB", "database_name": "app-db", "database_id": "<uuid>", "migrations_dir": "migrations" }],
  "r2_buckets": [{ "binding": "DOCS", "bucket_name": "app-docs" }]
}
```

```ts
// open-next.config.ts(これだけで良い)
import { defineCloudflareConfig } from "@opennextjs/cloudflare";
export default defineCloudflareConfig();
```

```jsonc
// package.json scripts(正準形)
{
  "preview": "opennextjs-cloudflare build && opennextjs-cloudflare preview",
  "deploy": "opennextjs-cloudflare build && opennextjs-cloudflare deploy",
  "cf-typegen": "wrangler types --env-interface CloudflareEnv cloudflare-env.d.ts"
}
```

```ts
// バインディングへのアクセス(Server Action / Route Handler)
import { getCloudflareContext } from "@opennextjs/cloudflare";
const { env } = await getCloudflareContext({ async: true });
// env.DB, env.DOCS
```

注意:
- `@opennextjs/cloudflare` は **1.3.0 未満に絶対ピンしない**(SSRF 脆弱性修正が 1.3.0)
- D1 を読む page / route には `export const dynamic = "force-dynamic"`(ビルド時プリレンダの古いデータ焼き込み防止)
- `next dev` で開発してよいが、**デプロイ前検証は必ず `preview`(workerd 実機)**
- 自分のエンドポイントを fetch する場合は `compatibility_flags` に `"global_fetch_strictly_public"` を追加
- Next.js のメジャーが新しい場合は `node_modules/next/dist/docs/` を先に読む(訓練データと breaking changes がある)

## レシピB: Vite SPA + Worker API(@cloudflare/vite-plugin + Hono)

出典: AXアプリポータル / AIアプリポータル / keiyu系 / Naemane

```jsonc
// wrangler.jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "app-name",
  "main": "./worker/index.ts",
  "compatibility_date": "2026-07-16",
  "compatibility_flags": ["nodejs_compat"],
  "observability": { "enabled": true },
  "upload_source_maps": true,
  "assets": {
    "not_found_handling": "single-page-application",
    "run_worker_first": ["/api/*"]        // アセットは高速配信のまま、APIだけWorker先行
  },
  "d1_databases": [{ "binding": "DB", "database_name": "app-db", "database_id": "<uuid>", "migrations_dir": "migrations" }]
}
```

```ts
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { cloudflare } from "@cloudflare/vite-plugin";
export default defineConfig({ plugins: [react(), tailwindcss(), cloudflare()] });
```

```jsonc
// package.json scripts
{
  "dev": "vite",
  "build": "tsc -b && vite build",
  "deploy": "pnpm run build && wrangler deploy -c dist/<app_name>/wrangler.json"
  // ★ vite-plugin はビルド時に dist/<name>/wrangler.json を生成する。デプロイはそれを -c で指定。
  //   素の `wrangler deploy` はソースの wrangler.jsonc を使ってしまい assets 解決が壊れる
}
```

```ts
// worker/index.ts — Hono ミドルウェアチェーンの型
import { Hono } from "hono";
type Bindings = { DB: D1Database; ASSETS: Fetcher };
const app = new Hono<{ Bindings: Bindings }>();

app.use("/api/*", async (c, next) => {          // 1. ボディサイズ上限
  const len = Number(c.req.header("content-length") ?? 0);
  if (len > 64_000) return c.json({ error: "payload too large" }, 413);
  await next();
});
app.use("/api/*", async (c, next) => {          // 2. CSRF: 非GETはOrigin一致必須
  if (c.req.method !== "GET") {
    const origin = c.req.header("origin");
    if (!origin || new URL(origin).host !== new URL(c.req.url).host) {
      return c.json({ error: "origin mismatch" }, 403);
    }
  }
  await next();
});
// 3. 認証(Access JWT検証 等) → 4. ルート定義
app.notFound((c) => c.json({ error: "not found" }, 404));
export default app;
```

## レシピC/D: 素の Worker + 静的アセット + Durable Objects

出典: DiGiTEC Quiz Bingo / tokumeichat-realtime

```jsonc
// wrangler.jsonc(vite-plugin を使わない構成)
{
  "name": "app-name",
  "main": "worker/index.ts",
  "compatibility_date": "2026-07-16",
  "observability": { "enabled": true },
  "assets": { "directory": "./dist", "binding": "ASSETS", "run_worker_first": true },
  "durable_objects": { "bindings": [{ "name": "ROOM", "class_name": "RoomObject" }] },
  "migrations": [{ "tag": "v1", "new_sqlite_classes": ["RoomObject"] }]
  // ★ new_classes ではなく new_sqlite_classes(SQLiteバックエンド)。無料プランはこれが必須
}
```

```ts
// SPA フォールバック(Worker が前段にいる場合は自前で書く)
async function serveSpa(request: Request, env: Env): Promise<Response> {
  const res = await env.ASSETS.fetch(request);
  if (res.status !== 404) return res;
  // ★ /index.html を直接 fetch すると 307 → 空白ページになる。origin ルート "/" を叩く
  return env.ASSETS.fetch(new URL("/", request.url));
}
```

```ts
// Durable Object — WebSocket Hibernation(必須形)
export class RoomObject extends DurableObject {
  async fetch(request: Request) {
    const pair = new WebSocketPair();
    this.ctx.acceptWebSocket(pair[1]);            // ws.accept() + addEventListener は課金され続けるので禁止
    return new Response(null, { status: 101, webSocket: pair[0] });
  }
  async webSocketMessage(ws: WebSocket, msg: string) { /* ... */ }
  async webSocketClose(ws: WebSocket) { /* ... */ }
}
```

OpenNext(レシピA)と DO を組み合わせる場合は **リアルタイム専用 Worker を分離**し、フロントにはビルド時に `NEXT_PUBLIC_REALTIME_URL` を注入する(tokumeichat 方式)。

## 共通: 環境分離テンプレート

```jsonc
{
  "env": {
    "staging": {
      "name": "app-name-staging",
      "d1_databases": [{ "binding": "DB", "database_name": "app-db-staging", "database_id": "<staging-uuid>" }]
    },
    "production": {
      "name": "app-name",
      "workers_dev": false,           // 本番はカスタムドメインのみ
      "d1_databases": [{ "binding": "DB", "database_name": "app-db", "database_id": "<prod-uuid>" }]
    }
  }
}
```
デプロイ: `wrangler deploy -e staging` / `wrangler deploy -e production`。ローカル開発で本番リソースに触りたいときは binding に `"remote": true`(stable)を付け、`wrangler dev --remote` は使わない(Legacy)。

## 共通: レート制限 binding

```jsonc
"ratelimits": [{ "name": "API_LIMIT", "namespace_id": "1001", "simple": { "limit": 100, "period": 60 } }]
```
```ts
const { success } = await c.env.API_LIMIT.limit({ key: userId });  // キーはユーザーID(IPは共有オフィスで全滅する)
if (!success) return c.json({ error: "rate limited" }, 429);
```

## 共通: セキュリティヘッダー(public/_headers)

```
/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Content-Security-Policy: default-src 'self'; script-src 'self'; img-src https: data:; object-src 'none'; frame-ancestors 'none'; form-action 'self'
```
