# cloudflare/references 索引

同梱するのはキット既定スタック(Workers / D1 / R2 / KV / Bindings)と要件フラグ経由の製品(Queues / Workflows / Vectorize)だけ。それ以外の製品は `cloudflare-docs` MCP で `docs:<name>` を検索する(製品名と `https://developers.cloudflare.com/<name>/` の slug は一致する)。

「MCP で取れるものは同梱しない」原則により、各製品の `api.md` / `configuration.md` は **docs MCP への問い方(検索語)と最小例だけの薄い索引**に縮めてある。`gotchas.md` / `patterns.md`(workers は `frameworks.md` も)は公式 docs に散在するか載っていない**経験知**なので温存している。wrangler CLI のコマンドは [`../../wrangler/references/`](../../wrangler/references/README.md) が正本で、ここでは複製しない。

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| `<product>/README.md` | 製品の概要・既定スタックでの位置・検索語・同梱ファイルの案内 | 可(索引のみ同梱) |
| `<product>/api.md` | API の検索語表と最小呼び出し例 1 つ | 可(索引のみ同梱) |
| `<product>/configuration.md` | `wrangler.jsonc` の最小 binding 例と設定項目の検索語表 | 可(索引のみ同梱) |
| `<product>/gotchas.md` | 落とし穴・制限の読み方・anti-pattern。末尾に旧 api/configuration から移設した注意点 | 不可(経験知。温存) |
| `<product>/patterns.md` | 設計パターン・使い分け | 不可(経験知。温存) |
| `workers/frameworks.md` | Hono / ルーティング / バリデーションの組み合わせ方 | 不可(経験知。温存) |
| `account-context.md` | Account 文脈の自動検出(本Skill独自) | 不可(公式 docs に存在しない) |

| 製品 | ディレクトリ | wrangler コマンド側 |
|---|---|---|
| Workers | `workers/` | `deploy.md` / `dev-local.md` / `config.md` |
| Bindings | `bindings/` | `config.md` |
| D1 | `d1/` | `d1.md` |
| KV | `kv/` | `kv-r2.md` |
| R2 | `r2/` | `kv-r2.md` |
| Queues | `queues/` | `queues-workflows-pipelines.md` |
| Workflows | `workflows/` | `queues-workflows-pipelines.md` |
| Vectorize | `vectorize/` | `ai-vectorize-hyperdrive.md` |

docs MCP が不通のとき(410 等)は `../../wrangler/references/mcp-vs-cli-routing.md` の復旧手順に従い、復旧できない場合だけ Web の `https://developers.cloudflare.com/<name>/` を直接取得する。
