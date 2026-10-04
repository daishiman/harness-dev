# R2(索引)

S3 互換のオブジェクトストレージ。egress 無料、書き込み・削除は強整合。キット既定のファイルストレージ(`mvp-first-development` §3)。用途はメディア・ユーザーアップロード・バックアップ・静的アセット。limits / pricing は陳腐化するため同梱せず、docs MCP で `r2 limits` / `r2 pricing` を検索する。

## 最新仕様の取得(第一手段)

- `cloudflare-docs` MCP で検索: `r2` / `R2 Workers API` / `R2 S3 API`
- MCP 不通時: `https://developers.cloudflare.com/r2/`

## 同梱ファイル

| ファイル | 用途 | docs MCP で代替可か |
|---|---|---|
| `configuration.md` | 最小 binding 例と設定項目の検索語 | 可(索引のみ同梱) |
| `api.md` | Workers API の検索語と最小例 | 可(索引のみ同梱) |
| `patterns.md` | streaming、条件付き GET、presigned URL、公開バケット、Cache API | 不可(経験知。温存) |
| `gotchas.md` | list truncated、httpEtag、stream 長、S3 SDK region、CORS、token 分離 | 不可(経験知。温存) |

## wrangler コマンド

バケット・オブジェクト操作、公開状態の確認は `../../../wrangler/references/kv-r2.md` が正本。

## 関連

[workers](../workers/)(runtime と fetch handler)/ [kv](../kv/)(オブジェクトのメタデータ)/ [d1](../d1/)(R2 URL の管理)/ [queues](../queues/)(event notifications の非同期処理)
