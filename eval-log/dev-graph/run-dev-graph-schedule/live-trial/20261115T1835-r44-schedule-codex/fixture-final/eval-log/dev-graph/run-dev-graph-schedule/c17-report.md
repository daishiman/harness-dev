# C17 独立監査

判定: PASS。正規CLI再算出と独立した入力照合の双方が、推薦3件で一致した。

## 推薦batch

| 順序 | task | resource_scope | 全依存 | branch | claim command |
|---|---|---|---|---|---|
| 1 | task-api-orders | src/api/orders/ | task-base-schema | devgraph/task-api-orders | `/dev-graph worktree claim task-api-orders --branch devgraph/task-api-orders --session-id <session>` |
| 2 | task-cache-warmup | src/cache/ | task-base-auth | devgraph/task-cache-warmup | `/dev-graph worktree claim task-cache-warmup --branch devgraph/task-cache-warmup --session-id <session>` |
| 3 | task-docs-runbook | docs/runbook/ | なし | devgraph/task-docs-runbook | `/dev-graph worktree claim task-docs-runbook --branch devgraph/task-docs-runbook --session-id <session>` |

3件は同一batch。全3pairのscope intersectionは空。全推薦がactive/confirmed/pass/readiness complete、推移的依存は全件done。mvp_fit・purpose・background・rationaleはreceiptで全件null、並びはmvp-first/v1の同rank id順。

## 全入力nodeの判定

| node | resource_scope | 判定・理由 |
|---|---|---|
| task-base-schema | src/db/ | 除外: status=done |
| task-base-auth | src/auth/ | 除外: status=done |
| task-api-users | src/api/users/ | 除外: active_lease_conflict:task-api-users |
| task-api-orders | src/api/orders/ | 推薦 |
| task-api-users-cache | src/api/users/, src/cache/ | 除外: active_lease_conflict:task-api-users |
| task-cache-warmup | src/cache/ | 推薦 |
| task-docs-runbook | docs/runbook/ | 推薦 |
| task-api-users-e2e | tests/e2e/users/ | 除外: dependency_unsatisfied:task-api-users |
| task-release-gate | release/ | 除外: status=blocked; dependency_unsatisfied:task-api-orders |
| task-draft-idea | src/api/users/ | 除外: status=draft; confirmation_status=draft; evaluation_status=pending; readiness=incomplete; active_lease_conflict:task-api-users |
| task-unconfirmed-migration | src/db/migrations/ | 除外: status=draft; confirmation_status=draft; evaluation_status=pending |
| task-eval-failed-report | reports/ | 除外: status=draft; evaluation_status=fail |
| task-readiness-incomplete-ui | src/ui/ | 除外: status=draft; evaluation_status=pending; readiness=incomplete |

## Leaseと入力不変性

active leaseはtask-api-users、state=claimed、expires_at=2026-11-15T11:10:49.868810Z。node自身とsrc/api/users/に重なるtask-api-users-cacheを除外した。期限切れleaseは0件。

| 入力 | before = after SHA-256 |
|---|---|
| .dev-graph/state/graph.json | 2ca637a84eda9717b0d61bb684f77d4d83d8cd07d3c55217610b20382dd88a7c |
| .git/dev-graph/leases.json | a3aa498fade345624021598ccc803293e806e68c3510868a293bf1c70a7fe3c1 |
| .git/dev-graph/events.json | a1189e55d5ac4a541d4b430ece082ec9e24ce8d9b0e336d95bda6d410b4d5658 |
| eval-log/dev-graph/run-dev-graph-schedule/leases.json | 33e12890410aa4a7a8841f4c00862f33dbbf4626f4de8015b377650ff8de25a0 |
| eval-log/dev-graph/run-dev-graph-schedule/schedule.json | 45a9c297584782ec21f4d7e915c34ef110e10cc64b58ff662c53a6beae1e4405 |

正規再算出schedule SHA-256: `45a9c297584782ec21f4d7e915c34ef110e10cc64b58ff662c53a6beae1e4405`。元scheduleとbytes一致。graph/tracker/leaseのmutation、claim、lease cleanupは実行していない。

## 適用範囲と所見

feature ready/batchは空、task実行batchだけで混在0件。全nodeのbinding=noneなのでBeads parity receiptは不要。非空feature分離や外部parityの実証には一般化しない。C27二重claim抑止mutation試験はread-only監査の責務外。

低重要度 PRESENTATION-01: 正規scheduleのexcludedはschedulable以外の理由を仕様上列挙しない。本reportで全13nodeのscopeと除外理由を補完した。推薦の安全性に不一致はない。
