# Architecture overview

## Context and drivers

- Business/technical context: <context>
- Quality attribute priorities: <security, reliability, latency, cost, delivery>
- Constraints: <platform, compliance, compatibility>

## Goals and non-goals

- Goals: <goal>
- Non-goals: <non-goal>

## System context and boundaries

- Users/external systems: <actors>
- Trust/deployment/data boundaries: <boundaries>
- Context diagram: <Mermaid/SVG/link>

## Container and component view

| Container/Component | Responsibility | Interface | Data owner | Deployment unit |
|---|---|---|---|---|
| <name> | <single responsibility> | <contract> | <data> | <unit> |

## Cross-cutting contracts

- Identity/access: <contract>
- Errors/resilience: <contract>
- Observability/audit: <contract>
- Configuration/secrets: <contract>
- Compatibility/versioning: <contract>

## Subtype architecture

合成対象を記録し、該当テンプレートを埋める。

- Frontend: <architecture-frontend.md or N/A: reason>
- Backend: <architecture-backend.md or N/A: reason>
- Infrastructure: <architecture-infrastructure.md or N/A: reason>
- Data: <architecture-data.md or N/A: reason>
- Security: <architecture-security.md or N/A: reason>

## Architecture decisions

| ADR | Decision | Alternatives | Trade-on rationale | Consequences |
|---|---|---|---|---|
| <id> | <decision> | <options> | <why> | <positive/negative> |

## Delivery, migration and rollback

- Build/deploy topology: <flow>
- Migration sequence: <steps>
- Rollback trigger/procedure: <contract>

## Risks and verification

- Risk/assumption: <risk>
- Architecture fitness test: <automated check>
- Load/failure/security validation: <evidence plan>


