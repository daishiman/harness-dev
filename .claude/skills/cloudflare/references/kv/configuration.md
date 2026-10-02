# KV Configuration(索引)

設定項目の正本は docs と `node_modules/wrangler/config-schema.json`。`cloudflare-docs` MCP で検索して最新を取得する。不通時は `https://developers.cloudflare.com/kv/` を直接取得する。

`wrangler.jsonc` の最小 binding:

```jsonc
{
  "kv_namespaces": [
    { "binding": "MY_KV", "id": "<NAMESPACE_ID>" },          // wrangler kv namespace create の出力
    { "binding": "MY_KV", "preview_id": "<PREVIEW_ID>" }     // 任意: preview / dev 用
  ]
}
```

| 設定項目・作業 | docs MCP の検索語 |
|---|---|
| namespace 作成・binding・`preview_id`・`remote` | `kv wrangler configuration kv_namespaces` |
| `Env` 型(`KVNamespace`)と型付き JSON 取得 | `kv typescript KVNamespace types` |
| CLI の key / bulk 操作 | `wrangler kv key put get list bulk` |
| ローカル開発と `--remote` の違い | `kv local development wrangler dev remote` |
| REST API(SDK `cloudflare` パッケージ) | `kv rest api namespaces values bulk` |
| 上限・料金 | `kv limits` / `kv pricing` |

namespace 作成・key 操作・bulk などの CLI は `../../../wrangler/references/kv-r2.md` が正本。落とし穴は [gotchas.md](./gotchas.md)、設計パターンは [patterns.md](./patterns.md)。
