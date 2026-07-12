# Webhook 統合パターン

> **読み込み条件**: Webhook設計時
> **相対パス**: `references/integration-patterns-webhook.md`
> **親インデックス**: [integration-patterns.md](integration-patterns.md)

---

## 契約定義

```typescript
// shared/types/webhook-contracts.ts

/**
 * Webhookイベント型定義
 */
export const WEBHOOK_EVENTS = {
  // スキル関連
  SKILL_CREATED: "skill.created",
  SKILL_UPDATED: "skill.updated",
  SKILL_DELETED: "skill.deleted",
  SKILL_EXECUTED: "skill.executed",

  // エージェント関連
  AGENT_STARTED: "agent.started",
  AGENT_COMPLETED: "agent.completed",
  AGENT_FAILED: "agent.failed",
} as const;

export type WebhookEventType =
  (typeof WEBHOOK_EVENTS)[keyof typeof WEBHOOK_EVENTS];

/**
 * Webhookペイロード基本構造
 */
export interface WebhookPayload<T = unknown> {
  /** イベントID（冪等性キー） */
  id: string;

  /** イベントタイプ */
  event: WebhookEventType;

  /** APIバージョン */
  apiVersion: string;

  /** 発生日時（ISO 8601） */
  createdAt: string;

  /** イベント固有データ */
  data: T;
}

/**
 * イベント別データ型マッピング
 */
export interface WebhookDataMap {
  [WEBHOOK_EVENTS.SKILL_CREATED]: {
    skill: { id: string; name: string; version: string };
    createdBy: string;
  };

  [WEBHOOK_EVENTS.SKILL_EXECUTED]: {
    skillId: string;
    executionId: string;
    status: "success" | "failure";
    duration: number;
    input: Record<string, unknown>;
    output?: unknown;
    error?: { code: string; message: string };
  };

  [WEBHOOK_EVENTS.AGENT_COMPLETED]: {
    agentId: string;
    sessionId: string;
    result: unknown;
    tokenUsage: { input: number; output: number };
  };
}

/**
 * 型安全なWebhookペイロード取得
 */
export type TypedWebhookPayload<E extends WebhookEventType> =
  E extends keyof WebhookDataMap
    ? WebhookPayload<WebhookDataMap[E]>
    : WebhookPayload<unknown>;

/**
 * Webhook署名検証用
 */
export interface WebhookSignatureConfig {
  /** ヘッダー名 */
  header: string;

  /** アルゴリズム */
  algorithm: "sha256" | "sha512";

  /** プレフィックス（例: "sha256="） */
  prefix: string;

  /** タイムスタンプヘッダー（リプレイ攻撃防止） */
  timestampHeader?: string;

  /** 許容時間差（秒） */
  tolerance?: number;
}
```

## Webhook送信実装

```typescript
// lib/webhook-sender.ts
import crypto from "crypto";
import {
  WebhookPayload,
  WebhookEventType,
  TypedWebhookPayload,
} from "@shared/types/webhook-contracts";

interface WebhookEndpoint {
  url: string;
  secret: string;
  events: WebhookEventType[];
  active: boolean;
}

export class WebhookSender {
  private endpoints: WebhookEndpoint[] = [];
  private retryConfig = {
    maxRetries: 3,
    initialDelay: 1000,
    maxDelay: 30000,
  };

  async send<E extends WebhookEventType>(
    event: E,
    data: TypedWebhookPayload<E>["data"],
  ): Promise<void> {
    const payload: WebhookPayload = {
      id: crypto.randomUUID(),
      event,
      apiVersion: "2024-01",
      createdAt: new Date().toISOString(),
      data,
    };

    const targets = this.endpoints.filter(
      (ep) => ep.active && ep.events.includes(event),
    );

    await Promise.allSettled(
      targets.map((endpoint) => this.sendToEndpoint(endpoint, payload)),
    );
  }

  private async sendToEndpoint(
    endpoint: WebhookEndpoint,
    payload: WebhookPayload,
  ): Promise<void> {
    const body = JSON.stringify(payload);
    const timestamp = Math.floor(Date.now() / 1000);
    const signature = this.sign(body, timestamp, endpoint.secret);

    for (let attempt = 0; attempt < this.retryConfig.maxRetries; attempt++) {
      try {
        const response = await fetch(endpoint.url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Webhook-ID": payload.id,
            "X-Webhook-Timestamp": timestamp.toString(),
            "X-Webhook-Signature": signature,
          },
          body,
        });

        if (response.ok || response.status < 500) {
          return; // 成功 or クライアントエラー（リトライ不要）
        }
      } catch (error) {
        // ネットワークエラー
      }

      // 指数バックオフ
      const delay = Math.min(
        this.retryConfig.initialDelay * Math.pow(2, attempt),
        this.retryConfig.maxDelay,
      );
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  private sign(body: string, timestamp: number, secret: string): string {
    const signedPayload = `${timestamp}.${body}`;
    const signature = crypto
      .createHmac("sha256", secret)
      .update(signedPayload)
      .digest("hex");
    return `t=${timestamp},v1=${signature}`;
  }
}
```

## Webhook受信・検証実装

```typescript
// lib/webhook-receiver.ts
import crypto from "crypto";
import {
  WebhookPayload,
  WebhookEventType,
  WebhookDataMap,
} from "@shared/types/webhook-contracts";

interface VerifyOptions {
  secret: string;
  tolerance?: number; // 秒（デフォルト: 300 = 5分）
}

export class WebhookReceiver {
  /**
   * 署名検証
   */
  verify(
    body: string,
    signatureHeader: string,
    options: VerifyOptions,
  ): boolean {
    const { secret, tolerance = 300 } = options;

    // ヘッダー解析（形式: t=timestamp,v1=signature）
    const parts = signatureHeader.split(",");
    const timestamp = parseInt(
      parts.find((p) => p.startsWith("t="))?.slice(2) || "0",
    );
    const signature = parts.find((p) => p.startsWith("v1="))?.slice(3);

    if (!timestamp || !signature) {
      throw new Error("Invalid signature format");
    }

    // タイムスタンプ検証（リプレイ攻撃防止）
    const now = Math.floor(Date.now() / 1000);
    if (Math.abs(now - timestamp) > tolerance) {
      throw new Error("Webhook timestamp too old");
    }

    // 署名検証
    const expectedSignature = crypto
      .createHmac("sha256", secret)
      .update(`${timestamp}.${body}`)
      .digest("hex");

    return crypto.timingSafeEqual(
      Buffer.from(signature),
      Buffer.from(expectedSignature),
    );
  }

  /**
   * 型安全なイベントハンドラー登録
   */
  on<E extends WebhookEventType>(
    event: E,
    handler: (data: WebhookDataMap[E]) => Promise<void>,
  ): void {
    this.handlers.set(event, handler as any);
  }

  private handlers = new Map<
    WebhookEventType,
    (data: unknown) => Promise<void>
  >();

  /**
   * ペイロード処理
   */
  async process(payload: WebhookPayload): Promise<void> {
    const handler = this.handlers.get(payload.event);
    if (!handler) {
      console.warn(`No handler for event: ${payload.event}`);
      return;
    }
    await handler(payload.data);
  }
}

// 使用例
const receiver = new WebhookReceiver();

receiver.on(WEBHOOK_EVENTS.SKILL_EXECUTED, async (data) => {
  // data は自動的に WebhookDataMap['skill.executed'] 型
  console.log(`Skill ${data.skillId} executed in ${data.duration}ms`);
  if (data.status === "failure") {
    await notifyFailure(data.error!);
  }
});
```

## 検証チェックリスト

```markdown
## Webhook 検証チェックリスト

### 契約定義

- [ ] 全イベントタイプが `WEBHOOK_EVENTS` に集約されている
- [ ] イベント別データ型が `WebhookDataMap` で定義されている
- [ ] ペイロード形式がドキュメント化されている
- [ ] APIバージョンがペイロードに含まれている

### セキュリティ

- [ ] HMAC署名検証が実装されている
- [ ] タイムスタンプ検証（リプレイ攻撃防止）が実装されている
- [ ] 秘密鍵がセキュアに管理されている
- [ ] HTTPSのみ許可されている

### 信頼性

- [ ] 冪等性キー（id）がペイロードに含まれている
- [ ] 受信側で重複処理防止が実装されている
- [ ] 送信側でリトライ（指数バックオフ）が実装されている
- [ ] Dead Letter Queue（DLQ）が検討されている

### 運用

- [ ] Webhook登録/解除APIが提供されている
- [ ] イベントフィルタリングが可能になっている
- [ ] 配信ログが記録されている
- [ ] 手動再送機能が提供されている
```

---

## 関連リソース

- **パターン選択**: See [integration-patterns.md](integration-patterns.md)
- **API実装詳細**: See [api-integration-patterns.md](api-integration-patterns.md)
