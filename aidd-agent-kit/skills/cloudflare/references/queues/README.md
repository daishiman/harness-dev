# Queues(索引)

at-least-once 配信のメッセージキュー。push(Worker)/ pull(HTTP)consumer、batch、retry、DLQ、最大 12 時間の遅延配信。要件フラグ「上記以外の Cloudflare 機能」で `cloudflare` Skill から明示ルーティングされる製品。limits / pricing は陳腐化するため同梱せず、docs MCP で `queues limits` / `queues pricing` を検索する。

**先に読む 2 点**: 未捕捉エラーは **batch 全体**が retry される。ack も retry も呼ばない message は `max_retries` まで自動 retry される。詳細は [gotchas.md](./gotchas.md)。

## 最新仕様の取得(第一手段)

`cloudflare-docs` MCP で `queues` / `Queues JavaScript APIs` / `Queues consumer configuration` を検索。不通時は `https://developers.cloudflare.com/queues/`。

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| `configuration.md` | 最小 binding 例(producer + consumer)と設定項目の検索語 | 可(索引のみ同梱) |
| `api.md` | send / consumer / ack・retry の検索語と最小例 | 可(索引のみ同梱) |
| `patterns.md` | 非同期処理、buffering、rate limiting、DLQ、fan-out、冪等性、D1/Workflows/DO 連携 | 不可(経験知。温存) |
| `gotchas.md` | batch 全体 retry、無限 retry、ack/retry 優先順位、contentType、エラー分類 | 不可(経験知。温存) |

## wrangler コマンド
作成・一覧・consumer 追加削除・pause / purge は `../../../wrangler/references/queues-workflows-pipelines.md` が正本。

## 関連

[workers](../workers/)(producer / consumer の runtime)/ [r2](../r2/)(event notifications を queue で処理)/ [d1](../d1/)(consumer からの batch 書き込み)
