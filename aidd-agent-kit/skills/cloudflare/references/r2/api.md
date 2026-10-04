# R2 API(索引)

API シグネチャ・型定義は変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/r2/` を直接取得する。

| やりたいこと | docs MCP の検索語 |
|---|---|
| アップロード(httpMetadata / customMetadata / storageClass / sha256 / ssecKey) | `R2 Workers API put` |
| ダウンロード・range 読み・条件付き GET(`onlyIf`) | `R2 Workers API get R2GetOptions` |
| メタデータだけ取得 | `R2 head` |
| 単体・一括削除 | `R2 delete` |
| 一覧・ページング(`cursor` / `truncated` / `delimiter`) | `R2 list R2ListOptions` |
| Multipart upload(create / uploadPart / complete / abort / resume) | `R2 multipart upload Workers API` |
| Presigned URL(S3 SDK) | `R2 presigned URLs` |
| 型定義(`R2Bucket` / `R2Object` / `R2ObjectBody` / `R2Checksums`) | `R2 Workers API types` |

最小例:

```typescript
await env.MY_BUCKET.put(key, data, { httpMetadata: { contentType: 'image/jpeg' } });
const object = await env.MY_BUCKET.get(key);
if (!object) return new Response('Not found', { status: 404 });
return new Response(object.body);
```

CLI でのオブジェクト操作は `../../../wrangler/references/kv-r2.md` が正本。経験知(list の truncated、httpEtag、stream 長、S3 SDK の region など)は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。
