# 目的

<完了時に成立する状態>

## 背景

<なぜ必要か。issue/spec/architectureへの参照を含める>

## 入力と前提条件

- 入力: <artifact-or-data>
- 前提: <precondition>

## 出力と成果物

- 生成物: <path-or-artifact>
- 更新対象: <path-or-node>

## 依存関係

- `depends_on`: <graph_node_id>
- ブロッカー: <condition>

## 実装対象

- Frontend: <change-or-N/A: reason>
- Backend/API: <change-or-N/A: reason>
- Database/Data: <change-or-N/A: reason>
- Infrastructure: <change-or-N/A: reason>
- Security/Privacy: <change-or-N/A: reason>
- Documentation: <change-or-N/A: reason>

## Write scope と競合制約

- `touches`: <file-or-directory-pattern>
- 排他資源: <resource-key>
- 並列実行条件: <condition>
- branch: <one task per feature branch>
- worktree lease: <claim graph_node_id before implementation; heartbeat/release policy>
- completion projection: <feature branch records pending event only; default branch reconciliation writes done>

## GitHub publication

- Mode: <local_only|issue|issue_and_projects>
- Project aliases: <repo-config alias list or N/A: default auto-add policy>
- Issue labels/milestone: <values or N/A: reason>
- Initial Project fields: <status/priority/date/iteration values or N/A: reason>
- Publication gate: `status=active && confirmation_status=confirmed && evaluation_status=pass && implementation_readiness.status=complete`
- Failure policy: <pending_retry; local promoted task is not rolled back>
- Completion policy: <linked_pr_merged_all|linked_pr_merged_any|manual; default is linked_pr_merged_all>
- PR linkage requirement: <PR body contains `Closes #<issue>` and `dev-graph: <graph_node_id>`, targets default branch>
- Closed without merge: <keep_active|mark_blocked; never auto-done>
- Local reconciliation: <manual sync + optional post-merge hook + scheduled repair>

## 実行手順

1. <single-responsibility-step>

## 受入条件

- [ ] <Given/When/Then または観測可能な結果>

## 検証方法

- 自動検証: `<command>`
- 手動検証: <procedure>
- 証跡: <path>

## リスクとロールバック

- リスク: <risk>
- ロールバック: <procedure>

## Handoff

- 実装 route: <capability-build|task-graph-build|human>
- 次に利用するノード: <graph_node_id>

