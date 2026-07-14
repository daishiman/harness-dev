# API: <operation-name>

## 識別と目的

- Operation ID: `<operation-id>`
- Method/Path: `<METHOD /path/{id}>`
- Purpose: <business purpose>
- Version/Lifecycle: <version, stability, deprecation>

## 認証・認可

- Authentication: <scheme>
- Required scopes/roles: <rules>
- Resource ownership check: <rule>

## Request

- Headers: <name/type/required/meaning>
- Path parameters: <name/type/constraints>
- Query parameters: <name/type/default/filter/sort/pagination>
- Body schema: <field/type/required/nullability/format/constraints>
- Example: <valid example>

## Response

| Status | Meaning | Schema |
|---|---|---|
| 200 | <success> | <schema> |

- Headers: <cache/location/request-id>
- Example: <response example>

## Validation・ビジネスルール

- <field/cross-field rule and failure code>

## Error contract

| HTTP | Code | Condition | Retryable | Client action |
|---|---|---|---|---|
| <status> | <stable-code> | <condition> | <yes/no> | <action> |

## 実行セマンティクス

- Idempotency key/replay: <policy>
- Concurrency/optimistic lock: <policy>
- Transaction boundary: <policy>
- Timeout/retry/rate limit: <policy>

## キャッシュ・ページング

- Cache/ETag: <policy>
- Cursor/limit/filter/sort: <contract>

## 可観測性と監査

- Request/correlation ID: <contract>
- Metrics/logs/audit/redaction: <contract>

## セキュリティ確認

- Input/output validation: <control>
- Sensitive data exposure: <control>
- Abuse/authorization tests: <cases>

## Contract tests

- Positive: <case>
- Boundary: <case>
- Negative/auth/error/idempotency: <cases>


