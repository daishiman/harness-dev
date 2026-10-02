# Vectorize Configuration(索引)

設定項目と上限値は変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/vectorize/`。

最小 binding 例(`wrangler.jsonc`)。index の dimensions / metric は作成後に変更できない:

```jsonc
{
  "vectorize": [
    { "binding": "VECTORIZE", "index_name": "my-index" }
  ]
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| index 作成(dimensions / metric / preset) | `vectorize create index dimensions metric` |
| Worker binding と `Env` 型 | `vectorize wrangler binding` |
| metadata index の作成(データ投入前に必須) | `vectorize create-metadata-index` |
| NDJSON 一括投入とファイル上限 | `vectorize insert ndjson bulk upload` |
| metadata の型と高カーディナリティ対策 | `vectorize metadata index cardinality` |

index 作成・一覧・metadata index・ベクトル投入の CLI は [`../../../wrangler/references/ai-vectorize-hyperdrive.md`](../../../wrangler/references/ai-vectorize-hyperdrive.md) が正本。

経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。API は [api.md](./api.md)。
