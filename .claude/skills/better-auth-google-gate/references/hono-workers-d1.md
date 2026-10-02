# Hono／素のCloudflare Worker + D1

## 基本方針

- D1 bindingからリクエストごとにDrizzle clientとBetter Auth instanceを作る。
- `better-auth/minimal`と`@better-auth/drizzle-adapter`を優先する。
- Google provider、`hd`、`emailVerified`、DB-backed rate limit、`cf-connecting-ip`はNext.js版と同じ。
- schema生成はruntime設定と分離したCLI設定から行う。

## Hono

```ts
import { Hono } from "hono";
import { betterAuth } from "better-auth/minimal";
import { drizzleAdapter } from "@better-auth/drizzle-adapter";
import { drizzle } from "drizzle-orm/d1";
import * as schema from "./auth-schema";

type Env = {
  Bindings: {
    DB: D1Database;
    BETTER_AUTH_SECRET: string;
    BETTER_AUTH_URL: string;
    GOOGLE_CLIENT_ID: string;
    GOOGLE_CLIENT_SECRET: string;
  };
};

const app = new Hono<Env>();

function createAuth(env: Env["Bindings"]) {
  return betterAuth({
    baseURL: env.BETTER_AUTH_URL,
    secret: env.BETTER_AUTH_SECRET,
    trustedOrigins: [env.BETTER_AUTH_URL],
    database: drizzleAdapter(drizzle(env.DB, { schema }), {
      provider: "sqlite",
      schema,
      transaction: false,
    }),
    socialProviders: {
      google: {
        clientId: env.GOOGLE_CLIENT_ID,
        clientSecret: env.GOOGLE_CLIENT_SECRET,
        hd: "example.co.jp",
        prompt: "select_account",
      },
    },
    rateLimit: {
      enabled: true,
      storage: "database",
      customRules: { "/sign-in/social": { window: 60, max: 10 } },
    },
    advanced: {
      ipAddress: { ipAddressHeaders: ["cf-connecting-ip"] },
    },
  });
}

app.on(["GET", "POST", "PATCH", "PUT", "DELETE"], "/api/auth/*", (c) =>
  createAuth(c.env).handler(c.req.raw),
);
```

保護routeでは同じrequest headersを渡してsessionを取得する。

```ts
const session = await createAuth(c.env).api.getSession({
  headers: c.req.raw.headers,
});
if (!session) return c.json({ error: "Unauthorized" }, 401);
```

## 素のWorker

```ts
export default {
  async fetch(request, env) {
    const auth = createAuth(env);
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/auth/")) {
      return auth.handler(request);
    }

    const session = await auth.api.getSession({ headers: request.headers });
    if (!session) return new Response("Unauthorized", { status: 401 });
    return new Response("OK");
  },
} satisfies ExportedHandler<Bindings>;
```

## CLI、D1、Secret

Next.js版と同じ順序で行う。

1. CLI専用auth configを用意する。
2. `pnpm dlx auth@latest generate`でDrizzle schemaを生成する。
3. `pnpm drizzle-kit generate`でD1 migrationを作る。
4. `pnpm wrangler d1 migrations apply <db> --local`。
5. test/build後に`--remote`。
6. `setup-cloudflare-secrets.sh`で本番Secretを登録する。
7. `pnpm wrangler deploy`。

`wrangler.jsonc`に`compatibility_flags: ["nodejs_compat"]`を設定し、Secret値は書かない。

## 静的SPAアセットと同居するとき（必読・OAuthコールバックの罠）

Vite等でビルドしたSPAを Worker と同居させ、`assets.not_found_handling: "single-page-application"` を
使う構成では、**そのままだと Google のOAuthコールバックが動かない**。

理由: SPAフォールバックは、静的アセットに一致しない**ブラウザのトップレベル遷移**（`Accept: text/html`）
を `index.html` として返し、**Worker を実行しない**。`fetch`（`Accept: application/json`）は Worker に
届くため、`/api/me` 等の確認では正常に見えて気づけない。しかし `/api/auth/callback/google` は
Googleからの**トップレベル遷移**なので横取りされ、Better Auth がコードを受け取れず、
セッションが張れないまま毎回ログイン画面へ戻る。

対策: `/api/*` を必ず Worker 先行にルートする。

```jsonc
// wrangler.jsonc
"assets": {
  "not_found_handling": "single-page-application",
  // これが無いと OAuth コールバックの遷移が index.html に化ける。/api/* は必ず Worker へ。
  "run_worker_first": ["/api/*"]
}
```

`run_worker_first` は配列（負ルールは `"!..."`）または `true`。`true` は全リクエストを Worker 先行に
するが、その場合アセット配信も自前で `env.ASSETS.fetch()` する必要があるため、SPA配信を活かすなら
`["/api/*"]` のように**認証・APIパスだけ**を対象にする。

必ず検証する（`fetch`ではなく**遷移**を模す。これが今回のバグの再発防止線）:

```bash
# 遷移リクエストで Worker の応答（JSON/リダイレクト）が返れば正しい。
# <title> や <!doctype html>（＝index.html）が返るなら run_worker_first が効いていない。
curl -s -H "Accept: text/html" -H "Sec-Fetch-Mode: navigate" \
  "$PRODUCTION_ORIGIN/api/me" | head -c 200
```

Next.js + OpenNext 構成では Next 側がルーティングを持ち `/api/auth/*` も Worker が処理するため、
この罠は通常起きない。**Hono／素のWorker + 別ビルドのSPA配信**のときだけ必須のチェック。
