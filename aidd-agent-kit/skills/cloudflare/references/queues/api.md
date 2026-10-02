# Queues API(索引)

API シグネチャ・型定義は変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/queues/` を直接取得する。

| やりたいこと | docs MCP の検索語 |
|---|---|
| producer から送信(`send` / `sendBatch`、`delaySeconds`、`contentType`) | `Queues JavaScript APIs producer` |
| push consumer(`queue()` handler、`MessageBatch`、`Message`) | `Queues JavaScript APIs consumer` |
| ack / retry(個別、`ackAll` / `retryAll`、`retry({ delaySeconds })`) | `Queues message acknowledgement retries` |
| 指数バックオフ・retry 遅延 | `Queues retry delay` |
| 1 consumer で複数 queue を捌く(`batch.queue`) | `Queues consumer multiple queues` |
| pull consumer(HTTP、`lease_id`、`visibility_timeout_ms`) | `Queues pull consumers` |
| 型定義(`Queue<Body>` / `MessageBatch` / `QueueSendOptions`) | `Queues TypeScript types` |

最小例(message ごとに try/catch し、必ず ack か retry を呼ぶ):

```typescript
export default {
  async queue(batch: MessageBatch, env: Env): Promise<void> {
    for (const msg of batch.messages) {
      try { await process(msg.body); msg.ack(); }
      catch { msg.retry({ delaySeconds: 60 }); }
    }
  }
};
```

queue 作成・consumer 追加の CLI は `../../../wrangler/references/queues-workflows-pipelines.md` が正本。経験知(batch 全体 retry、無限 retry、ack/retry の優先順位、contentType)は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。
