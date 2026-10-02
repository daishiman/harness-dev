# Bindings(索引)

Workers が `env` 経由で Cloudflare resource(storage / compute / service / config)へ接続する仕組み。`wrangler.jsonc` で宣言し、`wrangler types` で型付けされ、実行時のネットワーク呼び出しはない。既定スタック(Workers + D1 + R2 + KV)を繋ぐ共通機構で全アプリが使う。limits / pricing は docs MCP で `workers limits bindings` を検索する。

## 最新仕様の取得(第一手段)

- `cloudflare-docs` MCP で検索: `workers bindings` / `wrangler configuration` / `wrangler types`
- MCP 不通時: `https://developers.cloudflare.com/workers/runtime-apis/bindings/`

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| [configuration.md](./configuration.md) | 既定スタック分の最小 `wrangler.jsonc` と検索語 | 可(索引のみ同梱) |
| [api.md](./api.md) | 型生成と `env` アクセスの検索語 | 可(索引のみ同梱) |
| [patterns.md](./patterns.md) | storage 選び方・Service RPC・secrets 運用・mock テスト | 不可(経験知。温存) |
| [gotchas.md](./gotchas.md) | global scope への env キャッシュ禁止・id/name 取り違え・limits | 不可(経験知。温存) |

## wrangler コマンド

resource 作成・型生成は `../../../wrangler/references/config.md`(製品別 CLI は同ディレクトリの `d1.md` / `kv-r2.md` / `queues-workflows-pipelines.md`)が正本。

## 関連

[Workers](../workers/README.md) / [KV](../kv/README.md) / [R2](../r2/README.md) / [D1](../d1/README.md) / [Queues](../queues/README.md)
