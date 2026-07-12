# 統合パターン集（契約定義中心）

> **読み込み条件**: システム間連携、IPC設計、API契約定義、型安全な通信設計時
> **相対パス**: `references/integration-patterns.md`

---

## 概要

システム間統合における**契約定義**を中心としたパターン集。
型安全性、検証可能性、保守性を重視した設計パターンを提供。

**既存リソースとの関係**:

- `api-integration-patterns.md`: 実装コード中心
- 本リソース: **契約定義**と**検証チェックリスト**中心

---

## パターン別詳細

| パターン     | 詳細参照                                                                                                   | 概要                                         |
| ------------ | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| Electron IPC | [integration-patterns-ipc.md](.claude/skills/skill-creator/references/integration-patterns-ipc.md)         | Main/Renderer間通信、セキュリティ・型安全    |
| REST API     | [integration-patterns-rest.md](.claude/skills/skill-creator/references/integration-patterns-rest.md)       | RESTful設計、OpenAPI契約、エラーハンドリング |
| GraphQL      | [integration-patterns-graphql.md](.claude/skills/skill-creator/references/integration-patterns-graphql.md) | SDL定義、Resolver設計、N+1対策               |
| Webhook      | [integration-patterns-webhook.md](.claude/skills/skill-creator/references/integration-patterns-webhook.md) | イベント駆動、署名検証、リトライ戦略         |

---

## パターン選択ガイド

### 比較表

| 観点        | Electron IPC         | REST API              | GraphQL               | Webhook        |
| ----------- | -------------------- | --------------------- | --------------------- | -------------- |
| 通信方向    | 双方向               | リクエスト/レスポンス | リクエスト/レスポンス | プッシュ       |
| 同期/非同期 | 両方                 | 同期                  | 同期                  | 非同期         |
| 型安全性    | 高（共有型）         | 中（OpenAPI）         | 高（SDL）             | 中（定義次第） |
| 適用場面    | デスクトップアプリ内 | マイクロサービス間    | 複雑なデータ取得      | イベント通知   |

### 選択フローチャート

```
[通信要件を特定]
    │
    ├─ デスクトップアプリ内部通信？
    │       └─ Yes → Electron IPC
    │
    ├─ リアルタイム双方向通信が必要？
    │       └─ Yes → WebSocket / SSE（別途検討）
    │
    ├─ イベント駆動の非同期通知？
    │       └─ Yes → Webhook
    │
    ├─ 複雑なネストデータ or 柔軟なクエリ？
    │       └─ Yes → GraphQL
    │
    └─ シンプルなCRUD操作？
            └─ Yes → REST API
```

---

## 関連リソース

- **API実装詳細**: See [api-integration-patterns.md](api-integration-patterns.md)
- **ランタイムガイド**: See [runtime-guide.md](runtime-guide.md)
- **スクリプト型カタログ**: See [script-types-catalog.md](script-types-catalog.md)
