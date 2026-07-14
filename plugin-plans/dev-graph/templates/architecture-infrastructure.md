# Infrastructure architecture

## Environments and topology

- Local/test/staging/production parity: <matrix>
- Regions/zones/network/trust boundaries: <topology>
- DNS/TLS/edge/ingress/egress: <contract>

## Compute and storage

- Runtime/compute/scaling: <resources and limits>
- Database/object/cache/queue: <managed resources>
- Capacity and cost budgets: <targets>

## IaC and delivery

- IaC tool/state/locking: <contract>
- CI/CD stages, approvals, provenance: <pipeline>
- Immutable artifacts/config promotion: <policy>

## Secrets and access

- Secret authority/rotation/injection: <contract>
- Human/service access and least privilege: <roles>

## Reliability and recovery

- SLO/alerts/on-call: <contract>
- Backup/restore/RPO/RTO/DR: <targets and tests>
- Failure domains/failover: <behavior>

## Infrastructure verification

- Plan/policy/security/drift/smoke/restore tests: <coverage>

