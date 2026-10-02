# Workers(索引)

V8 isolate 上で動くエッジ実行環境。キット既定ランタイム(`mvp-first-development` §3)で、全アプリの入口になる。limits / pricing は docs MCP で `workers limits` / `workers pricing` を検索する。

## 最新仕様の取得(第一手段)

- `cloudflare-docs` MCP で検索: `workers` / `workers runtime apis` / `wrangler configuration`
- MCP 不通時: `https://developers.cloudflare.com/workers/`

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| [configuration.md](./configuration.md) | 最小 `wrangler.jsonc` と設定項目の検索語 | 可(索引のみ同梱) |
| [api.md](./api.md) | runtime API の検索語と最小 handler | 可(索引のみ同梱) |
| [patterns.md](./patterns.md) | error handling / CORS / streaming / testing / deploy の実践パターン | 不可(経験知。温存) |
| [frameworks.md](./frameworks.md) | Hono / itty-router / Worktop の使い分けと typed env | 不可(経験知。温存) |
| [gotchas.md](./gotchas.md) | CPU 制限・body 再読・env 継承などの落とし穴 | 不可(経験知。温存) |

## wrangler コマンド
dev / deploy / tail / secret は `../../../wrangler/references/deploy.md` / `dev-local.md` / `config.md` が正本。

## 関連

[KV](../kv/README.md) / [D1](../d1/README.md) / [R2](../r2/README.md) / [Queues](../queues/README.md) / [Bindings](../bindings/README.md) / Durable Objects(`durable-objects` Skill)/ コードレビュー規約(`workers-best-practices` Skill)
