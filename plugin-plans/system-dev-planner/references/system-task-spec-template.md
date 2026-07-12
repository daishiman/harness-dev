<!--
正本: system-dev-planner (生成器) 側テンプレート。
template_version: 1.0.0
`plugin-plans/dev-graph/templates/system-task-spec.md` (draft) は現状独立ファイルであり、
P08/P12 で本正本への pointer 化予定。それまでフィールド名・節構成は非後退とし
draft の既存参照を壊さない。P08 で正本化・P12 で最終確定 (goal-spec C5)。
-->

# System task overlay: <task title>

## Machine-readable registration fields

- owners / tags / related_nodes: <values or empty arrays>
- parent_feature: <起動元 dev-graph feature ノードの graph_node_id。自動起動はfeature文脈から、手動起動は解決済みfeature参照から充填し、1 runが生む全task specで共有する>
- classification: <confidence + reason + task candidate paths>
- tracker_binding_intent: <auto|beads|github|none; execution_tracker.mode=both では auto 禁止>
- github_publication: <mode + project_aliases + labels + milestone>
- pr_completion_policy: <linked_pr_merged_all|linked_pr_merged_any>
- branch_policy: <one-task-one-branch + worktree lease required + default-branch reconciliation + assignment_owner=dev-graph-scheduler>

## 目的

<単一責務の実装完了時に成立するシステム状態。task.mdの全必須sectionも併用する>

## 背景

<system-spec/architecture/phase docの根拠ノードとユーザー価値>

## 前提条件

- Required spec/architecture/phase/task nodes: <graph_node_id>
- Entry gate: <machine-verifiable condition>
- Source pin: system-spec-harness v0.1.0 / run-system-spec-compile / assign-system-spec-completeness-evaluator
- Repository context: <repo_identity + root_resolution_source + .dev-graph/config.json; absolute path禁止>

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

## Tracker publication and completion

> 本specは`tracker_binding_intent`とGitHub公開intentだけを宣言し、永続bindingの解決・起票・完了収束はdev-graphが所有する。`auto`はrepo-configで解決するが、`execution_tracker.mode=both`では曖昧なため禁止する。Beads束縛時のGitHub viewer mirrorは`bd github sync --push-only`だけをauthorityとし、gh-bridgeによる二重起票とProjects custom-field同期を行わない。

- Tracker binding intent: <auto|beads|github|none>
- Publication mode: <local_only|issue|issue_and_projects>
- Project aliases / labels / milestone: <values or N/A: reason>
- PR completion policy: <linked_pr_merged_all|linked_pr_merged_any>
- PR body contract: <Closes #issue + dev-graph graph_node_id; default branch target>
- Ownership boundary: <system-dev-planner declares intent; dev-graph performs mutations/reconciliation>

## Branch and worktree execution

- Branch: <assigned after dev-graph registration by C15 as devgraph/<graph_node_id>; system-dev-planner does not preassign>
- Worktree lease: <claim graph_node_id before implementation; heartbeat/release>
- Parallel safety: <depends_on complete + resource_scope and active lease do not overlap>
- Completion projection: <feature branch records pending event only; clean default branch writes durable done>

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
- Ready when: <confirmed + evaluation pass + readiness complete + promoted digest + dev-graph registration complete>

## 参照情報

- System specification: <system-spec-harness output node>
- Architecture: <system-spec-harness output node>
- Feature: <起動元 dev-graph feature ノードの graph_node_id (parent_feature)。architecture_refs 先は system-spec-harness 引用のlineage参照であり本節のArchitectureと重複記載しない>
- Phase doc: <system-phase-spec node>
- Dependencies: <task graph node>

## implementation-readiness 判定 (正本追記)

- 上記全 section が placeholder (`<...>`) のまま残っていないこと。
- `Machine-readable registration fields`/`前提条件`/`成果物`/`Tracker publication and completion`/`Branch and worktree execution`/`Verification and evidence`/`Handoff` の 7 section は必須充足 (空・TODO 禁止)。空/TODO/未解決 `<...>` が 1 件でも残る場合、`check-implementation-readiness.py` (system-dev-planner C08) は `incomplete` を報告し、`missing_sections` に該当 section 名を列挙する。
- `Workstream applicability` は該当しない workstream を `N/A: reason` で明示し、空欄のまま省略しない (適用外の理由を機械可読に残す)。
- 全pathはcaller repository相対でC09 containment済みであること。`/absolute`、drive-letter、`..`、root外symlinkはincomplete。
- staging/evaluator/published digestが一致しC11 promotion receiptが存在するまでL4 handoffを出さない。
