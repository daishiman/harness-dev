# 目的と成功状態

<ユーザー価値と成功時に観測できる状態>

## スコープ

- In: <対象>
- Out: <非対象>

## 用語と主体

| Term/Actor | Definition/Responsibility |
|---|---|
| <term> | <definition> |

## ユースケースとユーザーフロー

1. <actor/action/result>

## 機能要件

- `FR-001`: <testable requirement>

## 非機能要件

- Performance: <metric/target/load>
- Availability/Reliability: <SLO/failure behavior>
- Accessibility/Usability: <standard/target>
- Security/Privacy: <control/data classification>
- Maintainability/Operability: <requirement>

## UI・状態遷移

- 画面/CLI/API状態: <states>
- 遷移条件: <event, guard, resulting state>
- Loading/Empty/Error: <behavior>

## ビジネスルールと検証

- `BR-001`: <rule, boundary, validation message>

## API契約

APIを公開・変更する場合は `api-contract.md` を endpoint ごとに合成する。API非該当時は `N/A: <理由>` を記載する。

## データモデル

- Entity/Value: <name and purpose>
- Fields/Types/Nullability: <contract>
- Relations/Constraints/Indexes: <contract>
- Ownership/Retention/Migration: <contract>

## 認証・認可

- Authentication: <method>
- Authorization: <role/scope/resource rule>
- Tenant/data boundary: <rule>

## エラー・例外・回復

- Error taxonomy: <code/status/message>
- Retry/Timeout/Fallback: <policy>
- Idempotency/Concurrency: <policy>

## イベント・非同期処理

- Producer/Consumer: <contract-or-N/A: reason>
- Delivery/Ordering/Deduplication/DLQ: <policy>

## 可観測性

- Logs/Metrics/Traces/Audit: <signal and redaction>
- Alert/SLO dashboard: <condition>

## 互換性・移行・リリース

- Compatibility/versioning: <policy>
- Migration/backfill: <steps>
- Rollout/rollback: <steps and trigger>

## テストと受入条件

- [ ] `AC-001`: <Given/When/Then>
- Contract/integration/e2e/security/performance: <coverage>

## 未決事項

- <owner, due date, decision needed>


