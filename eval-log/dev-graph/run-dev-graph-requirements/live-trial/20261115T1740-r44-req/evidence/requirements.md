# Requirements: FEATURE-1

- feature_package_id: `feature-package/feat`
- graph snapshot digest: `sha256:e375a59b087b0c13ea95dca1de47a95f0868120b8475320124cbf9ddc904b1fc` (revision 2)
- validated_digest (validate-system-plan.py): `sha256:c08646a47b6ceecd81f4ec2af7601e977208e5805533a5260388d5900d2caa23`
- readiness digest (C11 = C02): `sha256:374543454d483129c591e7591a27f065401ed6515dbdb7892fbb594032111bb3`
- lineage: system-spec/index.md → features/FEATURE-1.md → architecture/system.md → P01..P13 package

## Scope

FEATURE-1 の exact-13 package member SYS-P01..SYS-P13 (closure: FEATURE-1, ready)。

## Requirement trace

| requirement | node | phase | depends_on | document | package task spec | build target | readiness |
|---|---|---|---|---|---|---|---|
| REQ-P01 | SYS-P01 | P01 | - | `tasks/FEATURE-1/SYS-P01.md` | `task-specs/phase-01-requirements.md` | application-code | ready |
| REQ-P02 | SYS-P02 | P02 | SYS-P01 | `tasks/FEATURE-1/SYS-P02.md` | `task-specs/phase-02-architecture.md` | application-code | ready |
| REQ-P03 | SYS-P03 | P03 | SYS-P02 | `tasks/FEATURE-1/SYS-P03.md` | `task-specs/phase-03-design-review.md` | application-code | ready |
| REQ-P04 | SYS-P04 | P04 | SYS-P03 | `tasks/FEATURE-1/SYS-P04.md` | `task-specs/phase-04-test-design.md` | application-code | ready |
| REQ-P05 | SYS-P05 | P05 | SYS-P04 | `tasks/FEATURE-1/SYS-P05.md` | `task-specs/phase-05-implementation.md` | application-code | ready |
| REQ-P06 | SYS-P06 | P06 | SYS-P05 | `tasks/FEATURE-1/SYS-P06.md` | `task-specs/phase-06-test-run.md` | application-code | ready |
| REQ-P07 | SYS-P07 | P07 | SYS-P06 | `tasks/FEATURE-1/SYS-P07.md` | `task-specs/phase-07-acceptance.md` | application-code | ready |
| REQ-P08 | SYS-P08 | P08 | SYS-P07 | `tasks/FEATURE-1/SYS-P08.md` | `task-specs/phase-08-refactoring-migration.md` | application-code | ready |
| REQ-P09 | SYS-P09 | P09 | SYS-P08 | `tasks/FEATURE-1/SYS-P09.md` | `task-specs/phase-09-quality-assurance.md` | application-code | ready |
| REQ-P10 | SYS-P10 | P10 | SYS-P09 | `tasks/FEATURE-1/SYS-P10.md` | `task-specs/phase-10-final-review.md` | application-code | ready |
| REQ-P11 | SYS-P11 | P11 | SYS-P10 | `tasks/FEATURE-1/SYS-P11.md` | `task-specs/phase-11-evidence.md` | application-code | ready |
| REQ-P12 | SYS-P12 | P12 | SYS-P11 | `tasks/FEATURE-1/SYS-P12.md` | `task-specs/phase-12-documentation-operations.md` | application-code | ready |
| REQ-P13 | SYS-P13 | P13 | SYS-P12 | `tasks/FEATURE-1/SYS-P13.md` | `task-specs/phase-13-release-deploy.md` | application-code | ready |

## Boundary

本書は要件と handoff 参照だけを持つ。実装 code はこの skill では生成せず、capability-build/task-graph build が package の task spec から実装する。
