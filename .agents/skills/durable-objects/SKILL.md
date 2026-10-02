---
name: durable-objects
description: Cloudflare Durable Objects の実装とレビューに使用する。チャットルーム、マルチプレイ、予約システムなどの状態を持つ協調処理、RPC methods、SQLite storage、alarms、WebSockets、Workers統合、wrangler設定、Vitestでのテストを扱う。事前学習の知識より最新のCloudflare docsの取得を優先する。
---

> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# Durable Objects の実装・レビュー

Durable Objectsを使い、Cloudflare edge上に状態を持つ協調型アプリケーションを実装する。

## 最新情報の取得先

Durable Objects APIsや設定は更新されるため、**事前学習の知識より最新の公式情報を優先する**。API signature、設定項目、制限値を記憶だけで断定しない。

正本は [`cloudflare` Skill の「最新情報の取得先」](../cloudflare/SKILL.md#最新情報の取得先)(docs MCP 第一手段、不通時の復旧、workers-types / config-schema の取得方法)。ここには本Skill固有の取得先だけを書く。

| 取得先 | 取得方法 | 使う場面 |
|--------|----------|---------|
| **Cloudflare docs (MCP)** | `cloudflare-docs` MCPで `durable-objects` + API名(`sql.exec`、`setAlarm` 等)を検索 | **既定の第一手段**。API reference、制限値、compatibility date要件 |
| Durable Objects docs (Web) | `https://developers.cloudflare.com/durable-objects/`(`api/`、`best-practices/`、`examples/`) | MCP不通時 |

実装前に該当ページとプロジェクトのWrangler config schema / Workers typesを確認する。本Skillと最新の公式情報が食い違う場合は公式情報を優先し、不明なAPIや設定を推測で補わない。

## 使う場面

- 協調処理のために新しいDurable Object classを作る
- RPC methods、alarms、WebSocket handlersを実装する
- 既存のDOコードをBest Practicesに照らしてレビューする
- `wrangler.jsonc` / `wrangler.toml`にDO bindingsとmigrationsを設定する
- `@cloudflare/vitest-pool-workers`でテストする
- sharding戦略やparent-child関係を設計する

## 詳細リファレンス

- `./references/rules.md` - 中核ルール、storage、concurrency、RPC、alarms
- `./references/testing.md` - Vitest設定、unit/integration tests、alarm testing
- `./references/workers.md` - Workers handlers、types、wrangler config、observability

検索キーワード: `blockConcurrencyWhile`, `idFromName`, `getByName`, `setAlarm`, `sql.exec`

## 中核原則

### Durable Objectsが適する用途

| 必要な性質 | 例 |
|------|---------|
| 複数利用者の協調 | チャットルーム、マルチプレイ、共同編集 |
| Strong consistency | 在庫、予約システム、ターン制ゲーム |
| entity単位のstorage | Multi-tenant SaaS、利用者ごとのデータ |
| 持続接続 | WebSockets、real-time notifications |
| entity単位の予定処理 | 契約更新、ゲームのtimeout |

### 使わない用途

- statelessなrequest handling、plain Workersで十分な処理
- 最大限のglobal distributionが優先される処理
- 互いに独立したhigh fan-out requests

## 実装早見表

### Wrangler設定

```jsonc
// wrangler.jsonc
{
  "durable_objects": {
    "bindings": [{ "name": "MY_DO", "class_name": "MyDurableObject" }]
  },
  "migrations": [{ "tag": "v1", "new_sqlite_classes": ["MyDurableObject"] }]
}
```

### 基本パターン

```typescript
import { DurableObject } from "cloudflare:workers";

export interface Env {
  MY_DO: DurableObjectNamespace<MyDurableObject>;
}

export class MyDurableObject extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => {
      this.ctx.storage.sql.exec(`
        CREATE TABLE IF NOT EXISTS items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          data TEXT NOT NULL
        )
      `);
    });
  }

  async addItem(data: string): Promise<number> {
    const result = this.ctx.storage.sql.exec<{ id: number }>(
      "INSERT INTO items (data) VALUES (?) RETURNING id",
      data
    );
    return result.one().id;
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const stub = env.MY_DO.getByName("my-instance");
    const id = await stub.addItem("hello");
    return Response.json({ id });
  },
};
```

## 必須ルール

1. **coordination atomで分ける** - 1つのglobal DOに集約せず、chat room / game / userごとに1 DOとする
2. **deterministic routingに`getByName()`を使う** - 同じ入力は同じDO instanceへ導く
3. **SQLite storageを使う** - migrationsで`new_sqlite_classes`を設定する
4. **constructorで初期化する** - `blockConcurrencyWhile()`はschema setupだけに使う
5. **RPC methodsを使う** - `fetch()` handlerで代用しない。compatibility dateの要件は実装時に最新docsで確認する
6. **persistを先、cacheを後にする** - in-memory stateを更新する前にstorageへ書き込む
7. **alarmは1 DOに1つ** - `setAlarm()`は既存alarmを置き換える

## 禁止パターン

- 1つのglobal DOで全requestsを処理する。bottleneckになる
- 毎requestで`blockConcurrencyWhile()`を使いthroughputを落とす
- 重要なstateをmemoryだけに保持する。eviction / crashで失われる
- 関連するstorage writesの間に`await`を挟みatomicityを壊す
- `fetch()`や外部I/Oをまたいで`blockConcurrencyWhile()`を保持する

## Stubの作成

```typescript
// Deterministic - preferred for most cases
const stub = env.MY_DO.getByName("room-123");

// From existing ID string
const id = env.MY_DO.idFromString(storedIdString);
const stub = env.MY_DO.get(id);

// New unique ID - store mapping externally
const id = env.MY_DO.newUniqueId();
const stub = env.MY_DO.get(id);
```

## Storage操作

```typescript
// SQL (synchronous, recommended)
this.ctx.storage.sql.exec("INSERT INTO t (c) VALUES (?)", value);
const rows = this.ctx.storage.sql.exec<Row>("SELECT * FROM t").toArray();

// KV (async)
await this.ctx.storage.put("key", value);
const val = await this.ctx.storage.get<Type>("key");
```

## Alarmsの実装

```typescript
// Schedule (replaces existing)
await this.ctx.storage.setAlarm(Date.now() + 60_000);

// Handler
async alarm(): Promise<void> {
  // Process scheduled work
  // Optionally reschedule: await this.ctx.storage.setAlarm(...)
}

// Cancel
await this.ctx.storage.deleteAlarm();
```

## テストの最小例

```typescript
import { env } from "cloudflare:test";
import { describe, it, expect } from "vitest";

describe("MyDO", () => {
  it("should work", async () => {
    const stub = env.MY_DO.getByName("test");
    const result = await stub.addItem("test");
    expect(result).toBe(1);
  });
});
```

## 検証と報告

- プロジェクト既存のtypecheck / testコマンドと`@cloudflare/vitest-pool-workers`の対象テストを実行する。実行できない検証は未実施理由を明記する。
- bindings、migrations、class名、生成された`Env`型が一致することを確認する。新規のremote migrationや破壊的変更は、ユーザーの明示依頼がなければ実行しない。
- 最終報告は「選んだDO分割単位」「設定・実装の変更」「実行した検証と結果」「未検証項目・残るリスク」の順で簡潔に日本語で示す。
