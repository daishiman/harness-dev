# Vectorize(索引)

セマンティック検索・レコメンド・RAG・分類向けのグローバル分散ベクトル DB。Workers AI の embedding と組み合わせて使う。キットでは要件フラグ経由で明示ルーティングされる製品(既定スタック外)。limits / pricing は陳腐化するため同梱せず、docs MCP で `vectorize limits` / `vectorize pricing` を検索する。

## 最新仕様の取得(第一手段)

- `cloudflare-docs` MCP で検索: `vectorize` / `vectorize query` / `vectorize metadata filtering` / `vectorize limits`
- MCP 不通時: `https://developers.cloudflare.com/vectorize/`(embedding モデル一覧は `/workers-ai/models/#text-embeddings`)

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| [configuration.md](./configuration.md) | wrangler.jsonc の最小 binding 例と設定項目の検索語 | 可(索引のみ同梱) |
| [api.md](./api.md) | query / insert / upsert / filter API の検索語と最小例 | 可(索引のみ同梱) |
| [patterns.md](./patterns.md) | 経験知: metric 選定・RAG・Workers AI 連携・マルチテナント | 不可(経験知。温存) |
| [gotchas.md](./gotchas.md) | 経験知: 非同期反映・batch 切り捨て・metadata 切り詰め・topK 上限 | 不可(経験知。温存) |

## wrangler コマンド

[`../../../wrangler/references/ai-vectorize-hyperdrive.md`](../../../wrangler/references/ai-vectorize-hyperdrive.md)(create / list / insert / query の CLI は wrangler 側が正本)

## 関連

- [workers](../workers/) - Vectorize を呼ぶ実行環境
- `docs:workers-ai` - embedding 生成(同梱 reference なし)
