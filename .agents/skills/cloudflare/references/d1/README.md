# D1(索引)

Cloudflare のサーバーレス SQLite。**キット既定の DB**(`mvp-first-development` §3)。1 つの巨大 DB より per-tenant / per-user の複数 DB へ水平分割する設計を前提にする。Time Travel による point-in-time 復旧を持つ。

## 最新仕様の取得(第一手段)

- `cloudflare-docs` MCP で検索: `d1`、`d1 workers binding api`、`d1 migrations`、`d1 limits` / `d1 pricing`(制限値・料金は陳腐化するため同梱しない)
- MCP 不通時: `https://developers.cloudflare.com/d1/`

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| [configuration.md](./configuration.md) | `wrangler.jsonc` 最小 binding と設定項目の検索語 | 可(索引のみ同梱) |
| [api.md](./api.md) | 主要 API の検索語と prepared statement の最小例 | 可(索引のみ同梱) |
| [patterns.md](./patterns.md) | pagination、bulk insert、KV cache、multi-tenant、replica、sessions、backup | 不可(経験知。温存) |
| [gotchas.md](./gotchas.md) | SQL injection、型の罠、plan tier 制限の読み方、migration 事故 | 不可(経験知。温存) |

## wrangler コマンド

作成・SQL 実行・migration・export は `../../../wrangler/references/d1.md` が正本。

## 関連

- [workers](../workers/) - Worker runtime と fetch handler / Hyperdrive(既存 Postgres/MySQL): `docs:hyperdrive`
