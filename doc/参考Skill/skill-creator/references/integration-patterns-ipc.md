# Electron IPC 統合パターン

> **読み込み条件**: Electron IPC設計時
> **相対パス**: `references/integration-patterns-ipc.md`
> **親インデックス**: [integration-patterns.md](integration-patterns.md)

---

## 概要

Main Process（Node.js）とRenderer Process（Chromium）間の通信パターン。
セキュリティとパフォーマンスの両立が重要。

## 契約定義（TypeScript）

```typescript
// shared/types/ipc-contracts.ts

/**
 * IPCチャンネル定義（Single Source of Truth）
 */
export const IPC_CHANNELS = {
  // Agent関連
  AGENT_QUERY: "agent:query",
  AGENT_ABORT: "agent:abort",
  AGENT_STREAM: "agent:stream",

  // ファイル操作
  FILE_READ: "file:read",
  FILE_WRITE: "file:write",
  FILE_SELECT: "file:select-dialog",

  // システム
  SYSTEM_INFO: "system:info",
  SYSTEM_NOTIFICATION: "system:notification",
} as const;

export type IPCChannel = (typeof IPC_CHANNELS)[keyof typeof IPC_CHANNELS];

/**
 * リクエスト/レスポンス型定義
 */
export interface IPCRequest<T = unknown> {
  channel: IPCChannel;
  payload: T;
  requestId: string;
  timestamp: number;
}

export interface IPCResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: IPCError;
  requestId: string;
  duration: number;
}

export interface IPCError {
  code: string;
  message: string;
  stack?: string;
}

/**
 * チャンネル別ペイロード型マッピング
 */
export interface IPCPayloadMap {
  [IPC_CHANNELS.AGENT_QUERY]: {
    request: { prompt: string; options?: AgentOptions };
    response: { result: string; usage: TokenUsage };
  };
  [IPC_CHANNELS.FILE_READ]: {
    request: { path: string; encoding?: BufferEncoding };
    response: { content: string; stats: FileStats };
  };
  [IPC_CHANNELS.FILE_SELECT]: {
    request: { filters?: FileFilter[]; multiSelect?: boolean };
    response: { paths: string[] };
  };
}

/**
 * 型安全なIPCハンドラー型
 */
export type IPCHandler<C extends IPCChannel> = C extends keyof IPCPayloadMap
  ? (
      payload: IPCPayloadMap[C]["request"],
    ) => Promise<IPCPayloadMap[C]["response"]>
  : never;
```

## Main Process実装パターン

```typescript
// main/ipc/handlers.ts
import { ipcMain, BrowserWindow } from "electron";
import {
  IPC_CHANNELS,
  IPCPayloadMap,
  IPCResponse,
} from "@shared/types/ipc-contracts";

/**
 * 型安全なハンドラー登録
 */
function registerHandler<C extends keyof IPCPayloadMap>(
  channel: C,
  handler: (
    payload: IPCPayloadMap[C]["request"],
  ) => Promise<IPCPayloadMap[C]["response"]>,
): void {
  ipcMain.handle(
    channel,
    async (
      event,
      payload,
    ): Promise<IPCResponse<IPCPayloadMap[C]["response"]>> => {
      const startTime = Date.now();
      const requestId = payload.requestId || crypto.randomUUID();

      try {
        // 入力検証
        validatePayload(channel, payload);

        const data = await handler(payload);

        return {
          success: true,
          data,
          requestId,
          duration: Date.now() - startTime,
        };
      } catch (error) {
        return {
          success: false,
          error: {
            code: error.code || "UNKNOWN_ERROR",
            message: error.message,
            stack:
              process.env.NODE_ENV === "development" ? error.stack : undefined,
          },
          requestId,
          duration: Date.now() - startTime,
        };
      }
    },
  );
}

/**
 * ストリーミング用パターン（Agent応答など）
 */
function registerStreamHandler(
  channel: string,
  handler: (
    payload: unknown,
    send: (chunk: unknown) => void,
    signal: AbortSignal,
  ) => Promise<void>,
): void {
  const abortControllers = new Map<string, AbortController>();

  ipcMain.handle(channel, async (event, payload) => {
    const requestId = payload.requestId || crypto.randomUUID();
    const controller = new AbortController();
    abortControllers.set(requestId, controller);

    const sender = event.sender;
    const streamChannel = `${channel}:stream:${requestId}`;

    try {
      await handler(
        payload,
        (chunk) => {
          if (!sender.isDestroyed()) {
            sender.send(streamChannel, { type: "chunk", data: chunk });
          }
        },
        controller.signal,
      );

      if (!sender.isDestroyed()) {
        sender.send(streamChannel, { type: "end" });
      }
    } catch (error) {
      if (!sender.isDestroyed()) {
        sender.send(streamChannel, { type: "error", error: error.message });
      }
    } finally {
      abortControllers.delete(requestId);
    }
  });

  // 中断ハンドラー
  ipcMain.on(`${channel}:abort`, (event, { requestId }) => {
    const controller = abortControllers.get(requestId);
    if (controller) {
      controller.abort();
      abortControllers.delete(requestId);
    }
  });
}
```

## Preload Script（contextBridge）

```typescript
// preload/index.ts
import { contextBridge, ipcRenderer } from "electron";
import { IPC_CHANNELS, IPCPayloadMap } from "@shared/types/ipc-contracts";

/**
 * 型安全なAPI公開
 */
const electronAPI = {
  /**
   * 単発リクエスト
   */
  invoke: async <C extends keyof IPCPayloadMap>(
    channel: C,
    payload: IPCPayloadMap[C]["request"],
  ): Promise<IPCPayloadMap[C]["response"]> => {
    const response = await ipcRenderer.invoke(channel, {
      ...payload,
      requestId: crypto.randomUUID(),
      timestamp: Date.now(),
    });

    if (!response.success) {
      throw new Error(response.error?.message || "IPC Error");
    }

    return response.data;
  },

  /**
   * ストリーミング購読
   */
  stream: <T>(
    channel: string,
    payload: unknown,
    callbacks: {
      onChunk: (chunk: T) => void;
      onEnd: () => void;
      onError: (error: Error) => void;
    },
  ): { abort: () => void } => {
    const requestId = crypto.randomUUID();
    const streamChannel = `${channel}:stream:${requestId}`;

    const handler = (
      _event: unknown,
      message: { type: string; data?: T; error?: string },
    ) => {
      switch (message.type) {
        case "chunk":
          callbacks.onChunk(message.data!);
          break;
        case "end":
          callbacks.onEnd();
          cleanup();
          break;
        case "error":
          callbacks.onError(new Error(message.error));
          cleanup();
          break;
      }
    };

    const cleanup = () => {
      ipcRenderer.removeListener(streamChannel, handler);
    };

    ipcRenderer.on(streamChannel, handler);
    ipcRenderer.invoke(channel, { ...payload, requestId });

    return {
      abort: () => {
        ipcRenderer.send(`${channel}:abort`, { requestId });
        cleanup();
      },
    };
  },
};

contextBridge.exposeInMainWorld("electronAPI", electronAPI);

// 型定義をRenderer側に公開
declare global {
  interface Window {
    electronAPI: typeof electronAPI;
  }
}
```

## ハンドラ登録の Graceful Degradation

### 問題

`registerAllIpcHandlers()` で複数のハンドラ登録関数を順次呼び出す際、1つが例外を投げると後続が全て未登録になる。

### 解決パターン

| パターン | 適用場面 | 実装 |
|---|---|---|
| `safeRegister(name, fn)` | 戻り値不要のハンドラ登録 | 個別 try-catch でラップ。失敗を `HandlerRegistrationFailure` として記録 |
| 個別 try-catch | 戻り値のキャプチャが必要な場合 | `setupThemeWatcher` のように unsubscribe 関数を保持する必要がある場合 |
| `track()` クロージャ | 成功/失敗カウントの自動管理 | `registerAllIpcHandlers` 内のクロージャで状態を閉じ込める |

### 型定義

```typescript
interface HandlerRegistrationFailure {
  handlerName: string;
  errorMessage: string;
  errorCode: number; // 4001 = Infrastructure Error
}

interface IpcHandlerRegistrationResult {
  successCount: number;
  failureCount: number;
  failures: HandlerRegistrationFailure[];
}
```

### エラーメッセージのサニタイズ

NFR-02（プライバシー保護）準拠。`os.homedir()` パスを `~` にマスクする。

```typescript
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function sanitizeRegistrationErrorMessage(message: string): string {
  const homeDir = os.homedir();
  const escaped = escapeRegExp(homeDir);
  return message.replace(new RegExp(escaped, "g"), "~");
}
```

### 設計時の判断基準

1. ハンドラ登録関数の戻り値が必要か？ → 必要: 個別 try-catch / 不要: safeRegister
2. 複数ハンドラの成功/失敗を集約する必要があるか？ → あり: track() クロージャ
3. エラーメッセージにファイルパスが含まれるか？ → あり: sanitize 必須

## 外部API統合パターン（TASK-SDK-SC-03）

SDK Session 内で外部HTTPAPIを呼び出す機能を統合する際のパターン。IPC + SDK custom tool + 秘匿化 + バリデーションの4層で構成される。

### 全体フロー

```
1. SDK Session が外部API設定を必要と判断
2. RequestExternalApiConfig custom tool を発行
3. IPC 経由で Renderer に設定フォーム表示を要求（external-api-config-required）
4. ユーザーが URL / Method / Auth / Credential を入力
5. Renderer が configure-api IPC で設定を送信
6. Main Process が設定を受領し、sanitize してから SDK に返却
7. SDK が sanitize 済み設定をコンテキストとして利用
8. 実際のHTTP呼び出しは HttpExternalApiAdapter が生の credential で実行
```

### IPC チャネル設計

| チャネル | 方向 | 用途 |
|---|---|---|
| `skill-creator:configure-api` | Renderer → Main | 外部API設定を送信 |
| `skill-creator:api-configured` | Main → Renderer | API設定確認応答 |
| `skill-creator:api-test-result` | Main → Renderer | API接続テスト結果 |
| `skill-creator:external-api-config-required` | Main → Renderer | 設定要求通知 |

### 型定義（shared パッケージ）

```typescript
// packages/shared/src/types/skillCreatorExternalApi.ts
interface ExternalApiConnectionConfig {
  name: string;
  url: string;
  method: "GET" | "POST";
  authType: ExternalApiAuthType; // "none" | "api-key" | "bearer" | "basic"
  credential?: string;
  headers?: Record<string, string>;
  description?: string;
}
```

### 秘匿化パターン

```typescript
// SDKプロンプトに含める際は credential をマスクする
sanitizeExternalApiConfigForPrompt(config) {
  return { ...config, credential: config.credential ? "***REDACTED***" : undefined };
}
```

### エラーハンドリング

```typescript
// 30秒タイムアウト
class ExternalApiTimeoutError extends Error { url: string; }
// HTTP 4xx/5xx
class ExternalApiHttpError extends Error { statusCode: number; url: string; }
```

### 設計時の判断基準

1. 認証情報はどのレイヤーで保持するか → Main Process のみ。Renderer / SDK プロンプトには渡さない
2. 並行フロー（質問待機 vs API設定要求）は相互排他にする必要があるか → ある。同時に2つの pending Promise を持たない
3. タイムアウトはどこで制御するか → HttpExternalApiAdapter の fetch レベルで 30 秒固定

---

## 検証チェックリスト

```markdown
## Electron IPC 検証チェックリスト

### 契約定義

- [ ] 全チャンネル名が `IPC_CHANNELS` に集約されている
- [ ] リクエスト/レスポンス型が `IPCPayloadMap` で定義されている
- [ ] 型定義がMain/Preload/Rendererで共有されている

### セキュリティ

- [ ] `nodeIntegration: false` が設定されている
- [ ] `contextIsolation: true` が設定されている
- [ ] `sandbox: true` が設定されている（推奨）
- [ ] contextBridge経由でのみAPIを公開している
- [ ] 入力バリデーションがMain側で実装されている
- [ ] ファイルパスのサニタイズが実装されている

### エラーハンドリング

- [ ] 統一されたエラー形式（IPCError）を使用している
- [ ] 開発環境でのみスタックトレースを返している
- [ ] タイムアウト処理が実装されている
- [ ] 中断（abort）処理が実装されている

### パフォーマンス

- [ ] 大きなデータはストリーミングで送信している
- [ ] 不要なシリアライズを避けている
- [ ] リスナーのクリーンアップが実装されている
```

---

## Verify Engine 統合パターン（TASK-P0-01）

### 依存注入による Graceful Degradation

```typescript
// RuntimeSkillCreatorFacade.ts
class RuntimeSkillCreatorFacade {
  private verificationEngine?: SkillCreatorVerificationEngine;

  async verifySkill(skillDir: string): Promise<RuntimeSkillCreatorVerifyCheck[]> {
    if (!this.verificationEngine) return []; // graceful degradation
    return this.verificationEngine.verify(skillDir);
  }
}
```

### Severity Routing パターン

`verifyAndImproveLoop()` は verify 結果の severity に基づいて処理を分岐する:
- `info` → pass（改善不要）
- `warning` / `error` → improve 対象として LLM に渡す

### Verify IPC チャネル

| チャネル | 方向 | 用途 |
| --- | --- | --- |
| `skill-creator:get-verify-detail` | Renderer → Main | チェック詳細取得 |
| `skill-creator:request-reverify` | Renderer → Main | 再 verify 要求 |
| `skill-creator:reverify-workflow` | Renderer → Main | verify→improve→re-verify 閉ループ |

---

## 関連リソース

- **パターン選択**: See [integration-patterns.md](integration-patterns.md)
- **API実装詳細**: See [api-integration-patterns.md](api-integration-patterns.md)
