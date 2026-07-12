# 生成側 13 phase 名称確定表 (sdp 確定版)

> system-dev-planner が生成する typed task spec の `phase_ref` (P01..P13) が指す生成側 13 phase の呼称を、`plugin-plans/dev-graph/templates/system-plan-contract.json` の先行 draft から **sdp 確定版として本表に固定**する。以後、生成物側 schema/文書は draft へ依存せず本表を正本として参照する (`schemas-draft/workstream-inventory.schema.json` の `phase_ref` description が参照元)。本 plan 自身のライフサイクル 13 phase (index「フェーズ一覧」) とは別軸であり混同しない。

| phase_ref | phase id (確定呼称) | 責務 | applicability |
|---|---|---|---|
| P01 | requirements | requirements baseline | required |
| P02 | architecture | frontend/backend/API/data/infrastructure/security workstream design | required |
| P03 | design-review | independent design gate | required |
| P04 | test-design | test-first acceptance contract | required |
| P05 | implementation | dependency-ordered implementation tasks | required |
| P06 | test-run | unit/contract/integration/e2e/security/performance tests | required |
| P07 | acceptance | purpose-derived acceptance | required |
| P08 | refactoring-migration | refactor, data migration and compatibility | conditional-with-reason |
| P09 | quality-assurance | quality, security and operational readiness | required |
| P10 | final-review | independent final gate | required |
| P11 | evidence | reproducible evidence | required |
| P12 | documentation-operations | docs, runbooks and handover | required |
| P13 | release-deploy | rollout, rollback and post-release verification | conditional-with-reason |
