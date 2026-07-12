# Security architecture

## Assets, actors and threat model

- Protected assets/data classification: <assets>
- Actors/adversaries/abuse cases: <model>
- Trust boundaries/data flows: <diagram-or-contract>

## Identity and authorization

- Authentication/session/federation: <design>
- Authorization model and deny-by-default rules: <design>
- Tenant/resource ownership enforcement: <controls>

## Data and secret protection

- Encryption in transit/at rest/key ownership: <contract>
- Secret source/rotation/redaction: <contract>
- Retention/deletion/privacy requests: <policy>

## Application and supply-chain controls

- Input/output validation and injection defenses: <controls>
- Dependency/artifact provenance/signing/SBOM: <controls>
- CI/CD branch/review/environment protections: <controls>

## Detection and response

- Audit events/security telemetry/alerts: <signals>
- Incident response/revocation/recovery: <runbook>
- Vulnerability handling and SLA: <policy>

## Security verification

- SAST/SCA/secret scan/authz/abuse/penetration tests: <coverage>

