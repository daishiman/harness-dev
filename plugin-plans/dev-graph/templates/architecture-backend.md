# Backend architecture

## Runtime and architecture pattern

- Runtime/framework/version: <stack>
- Pattern: <layered/hexagonal/CQRS/event-driven/etc.>
- Selection rationale and rejected alternatives: <decision>

## Domain and module boundaries

- Bounded contexts/modules: <ownership>
- Dependency direction: <rule>
- Public/internal interfaces: <contract>

## API and service contracts

- Protocol/style/versioning: <REST/GraphQL/gRPC/events/etc.>
- Request lifecycle: <middleware-to-storage flow>
- Error taxonomy: <stable contract>

## Data and transaction behavior

- Repository/data owner: <contract>
- Transaction/idempotency/concurrency: <boundaries>
- Cache consistency/invalidation: <policy>

## Async processing

- Queue/event/scheduler: <producer-consumer contract>
- Delivery/order/dedup/retry/DLQ: <policy>

## Security and resilience

- Authn/authz/input validation: <controls>
- Timeout/retry/circuit breaker/load shedding: <policy>

## Operations and verification

- Logs/metrics/traces/health/readiness: <signals>
- Unit/contract/integration/load/failure tests: <coverage>

