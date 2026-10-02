# Next.js App Router + OpenNext + D1 標準実装

この経路を既定とする。資材は`assets/nextjs-opennext-d1/`にある。

## 構成

```text
Google OAuth
  → /api/auth/callback/google
  → Better Auth（hd / email_verified / rate limit）
  → Drizzle adapter
  → Cloudflare D1（user / account / session / verification / rate_limit）
  → HttpOnly session cookie
  → 保護ページ・APIでauth.api.getSession
```

## 1. 既存構成を尊重する

- `src/`有無、path alias、既存DB schema、既存routeを確認する。
- 既存authがある場合は置換せず差分監査する。
- D1 binding名は既存を優先し、なければ`DB`を使う。
- `package-lock.json`、`pnpm-lock.yaml`等からpackage managerを選ぶ。
- Next.jsのバージョン固有規約がある場合はプロジェクトの`AGENTS.md`とインストール済みdocsを読む。

## 2. 依存を導入する

新規構成の例:

```bash
pnpm add better-auth @better-auth/drizzle-adapter drizzle-orm
pnpm add -D drizzle-kit wrangler @cloudflare/workers-types @opennextjs/cloudflare
```

既存Better Authを更新する場合、core、adapter、CLI、schemaをまとめて確認する。lockfileを維持する。

## 3. D1を用意する

既存D1がなければ実行する。

```bash
pnpm wrangler whoami
pnpm wrangler d1 create <app-slug>-auth
```

返された`database_name`と`database_id`を`wrangler.jsonc`の`d1_databases`へ設定する。

```jsonc
{
  "compatibility_flags": ["nodejs_compat"],
  "d1_databases": [
    {
      "binding": "DB",
      "database_name": "<app-slug>-auth",
      "database_id": "<id>",
      "migrations_dir": "migrations"
    }
  ],
  "vars": {
    "BETTER_AUTH_URL": "https://app.example.com"
  }
}
```

`BETTER_AUTH_URL`はSecretではない。Client ID/SecretとBetter Auth secretはここへ書かない。

## 4. runtime envとauth factoryを作る

OpenNextのD1 bindingは`getCloudflareContext({ async: true })`から取得する。module load時にD1 clientを固定せず、リクエスト単位で生成し、React `cache`で同一リクエスト内だけ共有する。

主要設定:

```ts
return betterAuth({
  appName: APP_NAME,
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
      hd: WORKSPACE_DOMAIN,
      prompt: "select_account",
    },
  },
  databaseHooks: {
    user: {
      create: {
        before: async (user) => {
          if (!user.emailVerified) {
            throw new APIError("FORBIDDEN", { message: "ACCESS_DENIED" });
          }
          return { data: user };
        },
      },
    },
  },
  rateLimit: {
    enabled: true,
    storage: "database",
    window: 60,
    max: 100,
    customRules: { "/sign-in/social": { window: 60, max: 10 } },
  },
  advanced: {
    ipAddress: { ipAddressHeaders: ["cf-connecting-ip"] },
  },
});
```

`process.env`へ依存するだけのNode向けテンプレートをそのまま使わない。OpenNextのbinding取得をプロジェクトで一貫させる。

## 5. CLI用auth設定とschemaを生成する

runtime authはD1 bindingを必要とするため、CLIから読み込める副作用のない`src/auth.cli.ts`を分離する。ダミー値はschema生成専用で、実行時コードからimportしない。

```bash
pnpm dlx auth@latest info --config src/auth.cli.ts
pnpm dlx auth@latest generate \
  --config src/auth.cli.ts \
  --output src/lib/auth-schema.ts \
  --yes
pnpm drizzle-kit generate
```

`drizzle.config.ts`の例:

```ts
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  dialect: "sqlite",
  schema: "./src/lib/auth-schema.ts",
  out: "./migrations",
});
```

生成差分に`user`、`account`、`session`、`verification`があることを確認する。DB-backed rate limitを使う場合は`rate_limit`も必要。生成済みschemaを手で簡略化しない。

```bash
pnpm wrangler d1 migrations apply <database-name> --local
pnpm wrangler d1 migrations apply <database-name> --remote
```

本番適用はローカルtest/build成功後に行う。

## 6. Next.jsへマウントする

runtime envからauthを作る場合は、catch-all routeでRequestをそのまま渡す。

```ts
import { getAuth } from "@/lib/auth";

async function handler(request: Request) {
  return (await getAuth()).handler(request);
}

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const PUT = handler;
export const DELETE = handler;
```

静的なauth instanceを使える構成なら、公式の`toNextJsHandler(auth)`を使ってよい。

client:

```ts
import { createAuthClient } from "better-auth/react";
export const authClient = createAuthClient();
```

サインイン:

```ts
await authClient.signIn.social({
  provider: "google",
  callbackURL: "/",
  errorCallbackURL: "/sign-in?error=access_denied",
});
```

## 7. 保護する

すべての保護API、Server Action、データ取得関数でsessionを検証する。

```ts
const session = await (await getAuth()).api.getSession({
  headers: await headers(),
});
if (!session?.user?.id || !session.user.emailVerified) {
  throw new AuthenticationRequiredError();
}
```

停止／BANを実装する場合はapp profileを別テーブルへ置き、`session.create.before`とデータアクセス直前の両方で`status === "active"`を確認する。

Next.js 16の`proxy.ts`は早期redirectに使えるが、Cookie存在だけを見た場合は認可境界にしない。

## 8. 開発とデプロイ

`.dev.vars`にはローカル専用値を置く。

```dotenv
BETTER_AUTH_SECRET=<32文字以上。ローカル専用>
BETTER_AUTH_URL=http://localhost:3000
GOOGLE_CLIENT_ID=<Google Consoleから直接入力>
GOOGLE_CLIENT_SECRET=<Google Consoleから直接入力>
```

本番値は`setup-cloudflare-secrets.sh`で登録する。OpenNextの既存scriptsを使い、test、typecheck、build、migration、deployの順で実行する。

## このチャットから一般化した注意点

- Worker envはbuild時とruntimeで取得方法が違うため、`getCloudflareContext({ async: true })`を一貫して使う。
- D1はinteractive transaction非対応のため、Drizzle adapterに`transaction: false`を渡す構成を検証する。
- bundleが大きい場合は`better-auth/minimal`と抽出adapter packageを使う。
- `BETTER_AUTH_URL`をローカル値のままデプロイするとGoogle callbackがlocalhostになり、`redirect_uri_mismatch`になる。
- `hd`があるため、同じ文字列のメールドメインでも非Workspaceアカウントは通らない。
