# REST API 統合パターン

> **読み込み条件**: REST API設計時
> **相対パス**: `references/integration-patterns-rest.md`
> **親インデックス**: [integration-patterns.md](integration-patterns.md)

---

## 契約定義（OpenAPI互換）

```typescript
// shared/types/api-contracts.ts

/**
 * APIエンドポイント定義
 */
export const API_ENDPOINTS = {
  USERS: "/api/v1/users",
  USER_BY_ID: "/api/v1/users/:id",
  SKILLS: "/api/v1/skills",
  SKILL_EXECUTE: "/api/v1/skills/:id/execute",
} as const;

/**
 * HTTPメソッド型
 */
export type HTTPMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/**
 * APIルート定義
 */
export interface APIRoute<
  TParams = void,
  TQuery = void,
  TBody = void,
  TResponse = void,
> {
  method: HTTPMethod;
  path: string;
  params?: TParams;
  query?: TQuery;
  body?: TBody;
  response: TResponse;
}

/**
 * エンドポイント別契約定義
 */
export interface APIContracts {
  // GET /api/v1/users
  listUsers: APIRoute<
    void,
    { page?: number; limit?: number; search?: string },
    void,
    { users: User[]; total: number; page: number }
  >;

  // GET /api/v1/users/:id
  getUser: APIRoute<{ id: string }, void, void, User>;

  // POST /api/v1/users
  createUser: APIRoute<
    void,
    void,
    { name: string; email: string; role: UserRole },
    User
  >;

  // POST /api/v1/skills/:id/execute
  executeSkill: APIRoute<
    { id: string },
    void,
    { input: Record<string, unknown>; options?: ExecuteOptions },
    { output: unknown; duration: number }
  >;
}

/**
 * 統一レスポンス形式
 */
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, string[]>;
  };
  meta?: {
    requestId: string;
    timestamp: string;
    duration: number;
  };
}

/**
 * バリデーションスキーマ（Zod互換）
 */
export const UserCreateSchema = {
  name: { type: "string", minLength: 1, maxLength: 100 },
  email: { type: "string", format: "email" },
  role: { type: "enum", values: ["admin", "user", "guest"] },
} as const;
```

## 型安全なAPIクライアント

```typescript
// lib/api-client.ts

type ExtractParams<T extends APIRoute<any, any, any, any>> =
  T extends APIRoute<infer P, any, any, any> ? P : never;

type ExtractQuery<T extends APIRoute<any, any, any, any>> =
  T extends APIRoute<any, infer Q, any, any> ? Q : never;

type ExtractBody<T extends APIRoute<any, any, any, any>> =
  T extends APIRoute<any, any, infer B, any> ? B : never;

type ExtractResponse<T extends APIRoute<any, any, any, any>> =
  T extends APIRoute<any, any, any, infer R> ? R : never;

/**
 * 型安全なAPIクライアント
 */
export class TypedAPIClient {
  constructor(
    private baseUrl: string,
    private defaultHeaders: HeadersInit = {},
  ) {}

  async request<K extends keyof APIContracts>(
    key: K,
    options: {
      params?: ExtractParams<APIContracts[K]>;
      query?: ExtractQuery<APIContracts[K]>;
      body?: ExtractBody<APIContracts[K]>;
    } = {},
  ): Promise<APIResponse<ExtractResponse<APIContracts[K]>>> {
    const contract = this.getContract(key);
    let url = `${this.baseUrl}${contract.path}`;

    // パスパラメータ置換
    if (options.params) {
      for (const [k, v] of Object.entries(options.params)) {
        url = url.replace(`:${k}`, encodeURIComponent(String(v)));
      }
    }

    // クエリパラメータ追加
    if (options.query) {
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(options.query)) {
        if (v !== undefined) params.append(k, String(v));
      }
      if (params.toString()) url += `?${params}`;
    }

    const response = await fetch(url, {
      method: contract.method,
      headers: {
        "Content-Type": "application/json",
        ...this.defaultHeaders,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    return response.json();
  }

  private getContract(key: keyof APIContracts): {
    method: HTTPMethod;
    path: string;
  } {
    const contracts: Record<
      keyof APIContracts,
      { method: HTTPMethod; path: string }
    > = {
      listUsers: { method: "GET", path: API_ENDPOINTS.USERS },
      getUser: { method: "GET", path: API_ENDPOINTS.USER_BY_ID },
      createUser: { method: "POST", path: API_ENDPOINTS.USERS },
      executeSkill: { method: "POST", path: API_ENDPOINTS.SKILL_EXECUTE },
    };
    return contracts[key];
  }
}

// 使用例
const client = new TypedAPIClient("https://api.example.com", {
  Authorization: `Bearer ${token}`,
});

// 型安全な呼び出し（型エラーで誤りを検出）
const users = await client.request("listUsers", {
  query: { page: 1, limit: 20 },
});

const user = await client.request("getUser", {
  params: { id: "123" },
});
```

## 検証チェックリスト

```markdown
## REST API 検証チェックリスト

### 契約定義

- [ ] 全エンドポイントが `API_ENDPOINTS` に集約されている
- [ ] リクエスト/レスポンス型が `APIContracts` で定義されている
- [ ] バリデーションスキーマが定義されている
- [ ] エラーコードが文書化されている

### RESTful設計

- [ ] リソース指向のURL設計になっている
- [ ] HTTPメソッドが適切に使い分けられている
- [ ] ステータスコードが適切に返されている
- [ ] べき等性が保証されている（GET/PUT/DELETE）

### バージョニング

- [ ] APIバージョンがURLに含まれている（/api/v1/）
- [ ] 後方互換性が考慮されている
- [ ] 非推奨APIの告知方法が決まっている

### セキュリティ

- [ ] 認証ヘッダー（Bearer Token等）が必須になっている
- [ ] CORS設定が適切に行われている
- [ ] Rate Limitingが実装されている
- [ ] 入力サニタイズが実装されている
```

---

## 関連リソース

- **パターン選択**: See [integration-patterns.md](integration-patterns.md)
- **API実装詳細**: See [api-integration-patterns.md](api-integration-patterns.md)
