# System task overlay: <task title>

## 目的

<単一責務の実装完了時に成立するシステム状態。task.mdの全必須sectionも併用する>

## 背景

<system-spec/architecture/phase docの根拠ノードとユーザー価値>

## 前提条件

- Required spec/architecture/phase/task nodes: <graph_node_id>
- Entry gate: <machine-verifiable condition>

## Workstream applicability

- Frontend: <applicable + change | N/A: reason>
- Backend: <applicable + change | N/A: reason>
- API: <applicable + contract | N/A: reason>
- Data: <applicable + migration | N/A: reason>
- Infrastructure: <applicable + IaC/deploy | N/A: reason>
- Security: <applicable + control | N/A: reason>
- Quality: <applicable + tests/gates | N/A: reason>
- Documentation: <applicable + docs | N/A: reason>
- Operations: <applicable + runbook/monitoring | N/A: reason>

## Architecture and deploy unit

- Architecture decisions: <graph_node_id>
- Deploy unit/environment: <unit or N/A: reason>
- Compatibility/migration/backfill: <contract or N/A: reason>

## 成果物

- Produced artifacts: <paths and graph nodes>
- Consumed artifacts: <paths and graph nodes>
- Write scope/touches: <paths>

## スコープ外

- <explicit non-goal>

## Verification and evidence

- Automated commands: <commands>
- Required evidence: <paths>

## Rollout and rollback

- Rollout: <steps/flags>
- Rollback trigger and steps: <contract>

## Handoff

- Executor: <system build route>
- Ready when: <confirmed + evaluation pass + readiness complete>

## Tracker publication and completion intent

- Tracker binding intent: <auto|beads|github|none; mode=bothではauto禁止>
- Publication mode: <local_only|issue|issue_and_projects>
- Project aliases: <configured aliases; empty means default auto-add targets>
- Initial mapped fields: <status/priority/start_date/target_date/iteration>
- Linkage owner: <dev-graph C14 resolves intent; C28 beads or C12 GitHub publishes>
- Partial failure: <Project alias remains pending_retry without rolling back the promoted task>
- Completion trigger: <linked PR merged into default branch; closed-unmerged is not completion>
- Multiple PR policy: <all|required override>
- PR body contract: <GitHub binding=closing keyword + Issue; Beads binding=graph_node_id marker or gh:pr gate>

## 参照情報

- System specification: <system-spec-harness output node>
- Architecture: <system-spec-harness output node>
- Phase doc: <system-phase-spec node>
- Dependencies: <task graph node>
