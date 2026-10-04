# Workflows(索引)

自動 retry と状態永続化を備えた複数 step の長時間ジョブ基盤。step 単位で再試行し、数分〜数週間の sleep や外部イベント待ちを資源を消費せず行える。キットでは要件フラグ経由で明示ルーティングされる製品(既定スタック外)。limits / pricing は陳腐化するため同梱せず、docs MCP で `workflows limits` / `workflows pricing` を検索する。

## 最新仕様の取得(第一手段)

- `cloudflare-docs` MCP で検索: `workflows` / `workflows step.do` / `workflows waitForEvent` / `workflows limits`
- MCP 不通時: `https://developers.cloudflare.com/workflows/`

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| [configuration.md](./configuration.md) | wrangler.jsonc の最小 binding 例と設定項目の検索語 | 可(索引のみ同梱) |
| [api.md](./api.md) | step / instance / trigger API の検索語と最小例 | 可(索引のみ同梱) |
| [patterns.md](./patterns.md) | 経験知: pipeline・承認待ち・fan-out・テスト | 不可(経験知。温存) |
| [gotchas.md](./gotchas.md) | 経験知: timeout・非決定性・retention・移設した注意点 | 不可(経験知。温存) |

## wrangler コマンド

[`../../../wrangler/references/queues-workflows-pipelines.md`](../../../wrangler/references/queues-workflows-pipelines.md)(list / trigger / instances の CLI は wrangler 側が正本)

## 関連

- `durable-objects` Skill - 状態を持つ別アプローチ
- [queues](../queues/) - メッセージ駆動の起動元
- [workers](../workers/) - instance を起動する entry point
