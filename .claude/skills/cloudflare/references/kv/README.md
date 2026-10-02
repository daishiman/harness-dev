# KV(索引)

グローバル分散・結果整合(≤60 秒で伝播)の key-value ストア。**キット既定の session / cache 置き場**(`mvp-first-development` §3)。読み取り多・書き込み少に最適化され、key あたり 1 write/秒。強整合が要るなら `durable-objects` Skill、SQL なら [D1](../d1/)、ファイルなら [R2](../r2/)。

## 最新仕様の取得(第一手段)

- `cloudflare-docs` MCP で検索: `kv`、`kv get put api`、`kv wrangler configuration`、`kv limits` / `kv pricing`(制限値・料金は陳腐化するため同梱しない)
- MCP 不通時: `https://developers.cloudflare.com/kv/`

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| [configuration.md](./configuration.md) | `wrangler.jsonc` 最小 binding と設定項目の検索語 | 可(索引のみ同梱) |
| [api.md](./api.md) | 主要 API の検索語と get/put の最小例 | 可(索引のみ同梱) |
| [patterns.md](./patterns.md) | 多段 cache、API response cache、session、prefix 設計、metadata versioning | 不可(経験知。温存) |
| [gotchas.md](./gotchas.md) | 書き込み直後の stale read、負の cache、429、null 処理、上限の読み方 | 不可(経験知。温存) |

## wrangler コマンド

namespace 作成・key / bulk 操作は `../../../wrangler/references/kv-r2.md` が正本。

## 関連

- [workers](../workers/) - KV にアクセスする Worker runtime / [d1](../d1/) - 強整合・リレーショナルが要るとき
