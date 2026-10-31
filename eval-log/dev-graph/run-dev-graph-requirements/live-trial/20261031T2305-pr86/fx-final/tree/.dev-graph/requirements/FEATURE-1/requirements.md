# Requirements: FEATURE-1

- graph snapshot digest: `sha256:a84101d9109a6af449c88fc5cfeb05534a22f670e411ca727b59f160db6d7db6` (revision 2)
- source digest (validated_digest): `sha256:5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6`
- feature_package_id: `feature-package/feat` / parent_feature: `FEATURE-1`
- package: `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6`
- system-spec lineage (confirmed C19 / workstream-inventory.source_lineage): `system-spec/index.md` (system-spec-harness 0.1.0)
- architecture: `architecture/system.md` (architecture-system, closure verdict ready)

## Requirements (trace: requirement → source → system task → handoff field)

| REQ | source | system task | task spec | depends_on | handoff field |
|---|---|---|---|---|---|
| REQ-P01 | features/FEATURE-1.md + system-spec/index.md | SYS-P01 (P01) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-01-requirements.md` | - | execution_tasks[SYS-P01] |
| REQ-P02 | features/FEATURE-1.md + system-spec/index.md | SYS-P02 (P02) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-02-architecture.md` | SYS-P01 | execution_tasks[SYS-P02] |
| REQ-P03 | features/FEATURE-1.md + system-spec/index.md | SYS-P03 (P03) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-03-design-review.md` | SYS-P02 | execution_tasks[SYS-P03] |
| REQ-P04 | features/FEATURE-1.md + system-spec/index.md | SYS-P04 (P04) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-04-test-design.md` | SYS-P03 | execution_tasks[SYS-P04] |
| REQ-P05 | features/FEATURE-1.md + system-spec/index.md | SYS-P05 (P05) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-05-implementation.md` | SYS-P04 | execution_tasks[SYS-P05] |
| REQ-P06 | features/FEATURE-1.md + system-spec/index.md | SYS-P06 (P06) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-06-test-run.md` | SYS-P05 | execution_tasks[SYS-P06] |
| REQ-P07 | features/FEATURE-1.md + system-spec/index.md | SYS-P07 (P07) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-07-acceptance.md` | SYS-P06 | execution_tasks[SYS-P07] |
| REQ-P08 | features/FEATURE-1.md + system-spec/index.md | SYS-P08 (P08) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-08-refactoring-migration.md` | SYS-P07 | execution_tasks[SYS-P08] |
| REQ-P09 | features/FEATURE-1.md + system-spec/index.md | SYS-P09 (P09) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-09-quality-assurance.md` | SYS-P08 | execution_tasks[SYS-P09] |
| REQ-P10 | features/FEATURE-1.md + system-spec/index.md | SYS-P10 (P10) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-10-final-review.md` | SYS-P09 | execution_tasks[SYS-P10] |
| REQ-P11 | features/FEATURE-1.md + system-spec/index.md | SYS-P11 (P11) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-11-evidence.md` | SYS-P10 | execution_tasks[SYS-P11] |
| REQ-P12 | features/FEATURE-1.md + system-spec/index.md | SYS-P12 (P12) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-12-documentation-operations.md` | SYS-P11 | execution_tasks[SYS-P12] |
| REQ-P13 | features/FEATURE-1.md + system-spec/index.md | SYS-P13 (P13) | `.dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6/task-specs/phase-13-release-deploy.md` | SYS-P12 | execution_tasks[SYS-P13] |

## Readiness

C11 pass / C02 binding pass / validate-system-plan pass / guard handoff (14 nodes, node readiness missing_sections 0). 詳細は `readiness-matrix.json`。

### Advisory: artifact_readiness (C11, enforced=false)

C11 の本文見出し検査は status=incomplete、findings 49 件 (gate 非適用)。不足見出し: Architecture decisions, Architecture overview, Container and component view, Context and drivers, Cross-cutting contracts, Delivery, migration and rollback, Goals and non-goals, Risks and verification, Subtype architecture, System context and boundaries, 依存, 実行契約, 正本仕様書。
remediation owner: SYS-P01..P13 task-spec → system-dev-planner、architecture-system → architecture producer (system-spec-harness)。全件は `readiness-matrix.json#artifact_readiness_advisory`。

## Boundary

本文書は要件定義と handoff 参照のみ。実装コードは capability-build/task-graph が生成し、本 skill は生成しない。
