# wrangler/references 索引

ここは **wrangler CLI のコマンドと設定ファイル(`wrangler.jsonc`)** に限定した参照。製品ごとの API・設計パターン・落とし穴は [`../../cloudflare/references/`](../../cloudflare/references/README.md) が正本で、ここでは扱わない。コマンドのフラグは変わるため、書く前に `cloudflare-docs` MCP で `wrangler <subcommand>` を検索して最新を取得する。

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| `mcp-vs-cli-routing.md` | MCP と CLI の経路判断の正本、MCP 未接続時の復旧手順 | 不可(キット独自の運用規則) |
| `config.md` | `wrangler.jsonc` の書き方、binding 追加、型生成 | 一部可(binding 形状は docs MCP。構成の勘所は温存) |
| `dev-local.md` | ローカル開発、remote binding、`.dev.vars`、Vitest / scheduled のテスト | 一部可(`--remote` 事故防止など運用注意は温存) |
| `deploy.md` | デプロイ、versions / rollback、Pages、認証 | 可(コマンド集)。手順の正本は `cloudflare-secure-deploy` §2・§8 |
| `secrets.md` | Worker secret と Secrets Store の操作 | 一部可(上書き禁止・ローテーション規律は温存) |
| `d1.md` | D1 の作成、SQL 実行、migration、export | 可(コマンド集)。`--local` / `--remote` の取り違え注意のみ温存 |
| `kv-r2.md` | KV namespace / key、R2 bucket / object の操作 | 可(コマンド集)。R2 公開状態の確認と Account 規律のみ温存 |
| `queues-workflows-pipelines.md` | Queues、Workflows とインスタンス、Pipelines の操作 | 可(コマンド集) |
| `ai-vectorize-hyperdrive.md` | Workers AI のモデル一覧、Vectorize の index、Hyperdrive の設定 | 可(コマンド集)。AI のローカル課金・Hyperdrive の平文禁止のみ温存 |
| `containers.md` | コンテナイメージのビルド / プッシュ、外部レジストリ | 可(コマンド集) |
| `observability-troubleshooting.md` | `wrangler tail`、observability 設定、エラーの切り分け | 一部可(切り分け手順は温存) |

製品別ファイル(`d1.md` / `kv-r2.md` / `queues-workflows-pipelines.md` / `ai-vectorize-hyperdrive.md`)は各コマンド集と `wrangler.jsonc` の binding 断片だけを持つ。その製品の API・patterns・gotchas は `../../cloudflare/references/<product>/` を読む。
