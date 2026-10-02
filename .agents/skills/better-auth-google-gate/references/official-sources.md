# 一次情報リンク

最終確認: 2026-07-18。実装時には必ず再度開き、導入されているBetter Auth、Wrangler、OpenNextのバージョンに合わせる。

## Better Auth

- [Google provider](https://better-auth.com/docs/authentication/google): Client設定、`baseURL`、Redirect URI、`hd`、`prompt`
- [CLI](https://better-auth.com/docs/concepts/cli): `auth generate`、`migrate`、`secret`、`info`
- [Database](https://better-auth.com/docs/concepts/database): schema、migration、database hooks
- [Drizzle adapter](https://better-auth.com/docs/adapters/drizzle): Drizzle schema生成とadapter設定
- [Next.js integration](https://better-auth.com/docs/integrations/next): route handler、client、Next.js 16 proxy、サーバー側session検証
- [Rate limit](https://better-auth.com/docs/concepts/rate-limit): DB storage、Cloudflareの`cf-connecting-ip`
- [Options](https://better-auth.com/docs/reference/options): `baseURL`、`trustedOrigins`、session設定
- [Changelog](https://better-auth.com/changelog): 最新リリースと既知修正

## Google

- [OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect): `hd`リクエストはヒントであり、返却ID tokenのclaim検証が必要
- [Google ID token claims](https://developers.google.com/identity/openid-connect/reference): Workspace判定はメール末尾でなく`hd`、恒久IDはemailでなく`sub`
- [OAuth consent screen setup](https://support.google.com/cloud/answer/13461325): Internal/External、同意画面
- [Google Auth Platform - Branding](https://console.cloud.google.com/auth/branding)
- [Google Auth Platform - Audience](https://console.cloud.google.com/auth/audience)
- [Google Auth Platform - Clients](https://console.cloud.google.com/auth/clients)

## Cloudflare / OpenNext

- [Cloudflare Secrets](https://developers.cloudflare.com/workers/configuration/secrets/): `.dev.vars`、`wrangler secret put/list`、Secretの可視性
- [Cloudflare Pages commands](https://developers.cloudflare.com/workers/wrangler/commands/pages/): `wrangler pages secret put/list`、`--project-name`
- [Wrangler commands](https://developers.cloudflare.com/workers/wrangler/commands/): 現行CLI構文
- [D1 migrations](https://developers.cloudflare.com/d1/reference/migrations/): migration作成、ローカル／本番適用
- [Workers security best practices](https://developers.cloudflare.com/workers/best-practices/workers-best-practices/): Secret、環境分離、`compatibility_date`
- [OpenNext bindings](https://opennext.js.org/cloudflare/bindings): `getCloudflareContext`、型生成、ローカルbinding
- [OpenNext database patterns](https://opennext.js.org/cloudflare/howtos/db): リクエスト単位のDB clientとReact `cache`

検索結果やブログを根拠にAPIを推測しない。上記一次情報とインストール済みpackageの型定義を優先する。
