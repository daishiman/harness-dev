# Vectorize API(索引)

API シグネチャと上限値は変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/vectorize/`(Client API: `/vectorize/reference/client-api/`)。

| やりたいこと | docs MCP の検索語 |
|---|---|
| ベクトル型(`id` / `values` / `namespace` / `metadata`)の制約 | `vectorize VectorizeVector metadata size` |
| 類似検索(`query` / `topK` / `returnMetadata` / `returnValues`) | `vectorize query topK returnMetadata` |
| 既存ベクトルをクエリにする(`queryById`) | `vectorize queryById` |
| 追加・更新(`insert` / `upsert`)と batch 上限 | `vectorize insert upsert batch limit` |
| 取得・削除・index 情報(`getByIds` / `deleteByIds` / `describe`) | `vectorize getByIds deleteByIds describe` |
| metadata filter の演算子と制約 | `vectorize metadata filtering operators` |
| topK と返却オプションの性能トレードオフ | `vectorize query performance returnMetadata all` |

最小例:

```typescript
const emb = await env.AI.run("@cf/baai/bge-base-en-v1.5", { text: [query] });
const matches = await env.VECTORIZE.query(emb.data[0], {   // data[0] を渡す
  topK: 5,
  returnMetadata: "indexed",
  namespace: "tenant-123",
});
// matches.matches[0] = { id, score, metadata? }
```

経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。設定は [configuration.md](./configuration.md)。
