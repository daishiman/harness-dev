# Workflows API(索引)

API シグネチャは変わるため同梱しない。`cloudflare-docs` MCP で下表の語を検索して最新を取得する。不通時は `https://developers.cloudflare.com/workflows/`(Workers API: `/workflows/build/workers-api/`)。

| やりたいこと | docs MCP の検索語 |
|---|---|
| step を定義する(`do` / retry / timeout) | `workflows step.do retries timeout` |
| 待機・スケジュール(`sleep` / `sleepUntil`) | `workflows step.sleep sleepUntil` |
| 外部イベント・承認を待つ | `workflows waitForEvent sendEvent` |
| retry 回数に応じた分岐(`WorkflowStepContext`) | `workflows WorkflowStepContext attempt` |
| instance の作成・状態・pause/resume/terminate | `workflows create createBatch status instance` |
| Worker / Queue / Cron / 別 Workflow から起動する | `workflows trigger workflow from worker queue cron` |
| retry を止めるエラー | `workflows NonRetryableError` |
| params / 戻り値の型制約 | `workflows Rpc.Serializable step return` |
| REST API で instance を作成・監視 | `workflows REST API instances` |

最小例:

```typescript
export class MyWorkflow extends WorkflowEntrypoint<Env, Params> {
  async run(event: WorkflowEvent<Params>, step: WorkflowStep) {
    const user = await step.do('fetch user', async () =>
      this.env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(event.payload.userId).first());
    await step.sleep('wait 7 days', '7 days');
    await step.do('send reminder', async () => sendEmail(user.email, 'Reminder!'));
  }
}
```

経験知は [gotchas.md](./gotchas.md) / [patterns.md](./patterns.md)。設定は [configuration.md](./configuration.md)。
