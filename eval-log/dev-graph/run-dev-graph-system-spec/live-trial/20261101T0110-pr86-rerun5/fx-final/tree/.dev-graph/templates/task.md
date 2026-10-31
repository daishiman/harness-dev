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

## status の意味論 (二重正本の禁止)

frontmatter の `status` は **文書ライフサイクル**のみを表す。取り得る値と意味 (graph-node.schema.json の enum に一致):

- `draft` 起案中 / `active` 有効 / `blocked` 依存で停止 / `done` 完了として確定 / `closed` 文書として役割終了 / `tombstoned` 論理削除 (物理削除しない)
- 「後継文書へ置換された」状態は `closed` (旧文書) + 新文書側の `related_nodes`/`source_lineage` で表す。`superseded` という値は enum に無いため使用しない。

**実行状態 (未着手・進行中・完了) の正本は md ではない。** 実行状態は graph node 側に一元化する:

- `completion_evidence` (実行完了の根拠・policy・status) / `execution_contexts` (実行中の worktree/branch) / `beads_linkage` (課題トラッカー上の状態)

md へ実行状態を書き写して二重正本を作らない。`status=closed` かつ `completion_evidence.status=in_progress` は矛盾ではなく「文書は役割終了・実行の reconcile は未了」を意味する。両者は `lint-open-residue.py` が別 rule で検査する。なお `completion_evidence.policy=linked_pr_merged_all` は `status=done` へ遷移する際 GitHub PR merge の証跡 (pull_request_linkages/source=github_pr_merge) を schema が強制するため、`github.enabled=false` の beads 運用で close-loop する場合は `policy=manual` + `source=manual` を用いる。

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

