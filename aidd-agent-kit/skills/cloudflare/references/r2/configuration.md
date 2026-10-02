# R2 Configuration(索引)

設定項目は変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/r2/` を直接取得する。

最小 binding(`wrangler.jsonc`):

```jsonc
{
  "r2_buckets": [
    { "binding": "MY_BUCKET", "bucket_name": "my-bucket-name" }
  ]
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| Workers binding と `Env` 型 | `R2 bindings wrangler` |
| S3 SDK 接続(`region: 'auto'`、endpoint、access key) | `R2 S3 API tokens` |
| Location hint / jurisdiction | `R2 data location` |
| CORS(S3 SDK か Dashboard のみ) | `R2 CORS` |
| Object lifecycle(期限切れ・IA への移行) | `R2 object lifecycles` |
| API token の権限範囲 | `R2 API tokens permissions` |
| Event notifications(Queues 連携) | `R2 event notifications` |
| Storage class(Standard / InfrequentAccess) | `R2 storage classes` |

バケット作成・一覧・公開状態確認・オブジェクト操作の CLI は `../../../wrangler/references/kv-r2.md` が正本。経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。
