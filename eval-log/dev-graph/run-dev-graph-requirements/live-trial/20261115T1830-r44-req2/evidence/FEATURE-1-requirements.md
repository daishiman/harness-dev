# FEATURE-1 要件定義書 (run-dev-graph-requirements)

- feature: `FEATURE-1` (`features/FEATURE-1.md`, confirmed / pass / implementation_readiness complete)
- feature_package_id: `feature-package/feat`
- package: `.dev-graph/plans/generations/feature-package-feat/851f6700701209795092ce6bb141be5100af2099bd3f22a59ed26a00f03a71a4`
- source_digest: `sha256:851f6700701209795092ce6bb141be5100af2099bd3f22a59ed26a00f03a71a4` (= `validate-system-plan.py` の `validated_digest`)
- graph snapshot digest: `sha256:63e2c21bb55aada5e6dab7813febe50839db6ca63f128a9443f09ed0ebf23ba5` (graph_revision 2, relation `registered_snapshot`)
- readiness view digest (C11 = C02): `sha256:27256fc4056eeef3904be2499615ab815baa70e40be805976982d38c376711cb`
- C02 receipt: `.dev-graph/state/registration-receipts/feat.json`
- handoff target: capability-build / task-graph build (実装は handoff 先が担う。本 skill は実装 code を生成しない)

## 1. Scope

guard (`guard-requirements-handoff.py`) の `handoff` に並んだ 14 node をそのまま scope とする。

| node | kind | phase | 定義文書 | 上流 (depends_on) |
|---|---|---|---|---|
| FEATURE-1 | feature | - | features/FEATURE-1.md | - |
| SYS-P01 | task | P01 | tasks/FEATURE-1/SYS-P01.md | - |
| SYS-P02 | task | P02 | tasks/FEATURE-1/SYS-P02.md | SYS-P01 |
| SYS-P03 | task | P03 | tasks/FEATURE-1/SYS-P03.md | SYS-P02 |
| SYS-P04 | task | P04 | tasks/FEATURE-1/SYS-P04.md | SYS-P03 |
| SYS-P05 | task | P05 | tasks/FEATURE-1/SYS-P05.md | SYS-P04 |
| SYS-P06 | task | P06 | tasks/FEATURE-1/SYS-P06.md | SYS-P05 |
| SYS-P07 | task | P07 | tasks/FEATURE-1/SYS-P07.md | SYS-P06 |
| SYS-P08 | task | P08 | tasks/FEATURE-1/SYS-P08.md | SYS-P07 |
| SYS-P09 | task | P09 | tasks/FEATURE-1/SYS-P09.md | SYS-P08 |
| SYS-P10 | task | P10 | tasks/FEATURE-1/SYS-P10.md | SYS-P09 |
| SYS-P11 | task | P11 | tasks/FEATURE-1/SYS-P11.md | SYS-P10 |
| SYS-P12 | task | P12 | tasks/FEATURE-1/SYS-P12.md | SYS-P11 |
| SYS-P13 | task | P13 | tasks/FEATURE-1/SYS-P13.md | SYS-P12 |

closure 外参照: `architecture-system` (`architecture/system.md`, verdict ready, in_scope false, FEATURE-1 から参照)。

## 2. 要件 → source → system task → handoff field の trace

各要件は external system-dev-planner の exact-13 package の task spec を正本とし、本書は引用だけを持つ (13 task の生成ロジックは複製しない)。

| req | 要件 (task spec の phase 責務) | source (package 内 task spec) | system task | handoff field |
|---|---|---|---|---|
| REQ-P01 | 要件定義 | task-specs/phase-01-requirements.md | SYS-P01 | execution_tasks[P01] |
| REQ-P02 | アーキテクチャ | task-specs/phase-02-architecture.md | SYS-P02 | execution_tasks[P02] |
| REQ-P03 | 設計レビュー | task-specs/phase-03-design-review.md | SYS-P03 | execution_tasks[P03] |
| REQ-P04 | テスト設計 | task-specs/phase-04-test-design.md | SYS-P04 | execution_tasks[P04] |
| REQ-P05 | 実装 | task-specs/phase-05-implementation.md | SYS-P05 | execution_tasks[P05] |
| REQ-P06 | テスト実行 | task-specs/phase-06-test-run.md | SYS-P06 | execution_tasks[P06] |
| REQ-P07 | 受入 | task-specs/phase-07-acceptance.md | SYS-P07 | execution_tasks[P07] |
| REQ-P08 | リファクタリング・移行 | task-specs/phase-08-refactoring-migration.md | SYS-P08 | execution_tasks[P08] |
| REQ-P09 | 品質保証 | task-specs/phase-09-quality-assurance.md | SYS-P09 | execution_tasks[P09] |
| REQ-P10 | 最終レビュー | task-specs/phase-10-final-review.md | SYS-P10 | execution_tasks[P10] |
| REQ-P11 | 証跡 | task-specs/phase-11-evidence.md | SYS-P11 | execution_tasks[P11] |
| REQ-P12 | 文書・運用 | task-specs/phase-12-documentation-operations.md | SYS-P12 | execution_tasks[P12] |
| REQ-P13 | リリース・デプロイ | task-specs/phase-13-release-deploy.md | SYS-P13 | execution_tasks[P13] |

各 task node の `source_lineage` は `origin_kind: system-dev-planner`、`source_digest: 851f6700…71a4` で、上の task spec を `source_path` に持つ。feature 文脈は `features/FEATURE-1.md`、system-spec lineage は `system-spec/index.md`・`system-spec/00-requirements-definition.md`、architecture は `architecture/system.md` を参照する。

## 3. Readiness (三 gate)

| gate | script | 結果 |
|---|---|---|
| system plan (P01..P13 exact 13・13-node DAG・共通 parent_feature/feature_package_id) | validate-system-plan.py (validate-readiness-binding.py 経由) | exit 0, status pass, violations 0 |
| C11 graph validation | validate-graph-schema.py | status pass, violations 0, node_readiness complete 15 / incomplete 0 |
| C02 binding (source_digest = validated_digest, readiness view digest c11 = c02) | validate-readiness-binding.py | exit 0, status pass, violations 0 |
| handoff guard | guard-requirements-handoff.py --expect-graph-digest | exit 0, status handoff, handoff_count 14, missing_sections [], blocked [], digest_match true |

missing section は 0 件。

## 4. 実装境界

- 本 skill は実装 code / task spec を生成しない。実装は `capability-build-handoff.json` を受けた capability-build / task-graph build が行う。
- 各 task の `resource_scope` (`src/p01` .. `src/p13`) は handoff 先の作業範囲であり、本 run はそこへ何も書かない。
