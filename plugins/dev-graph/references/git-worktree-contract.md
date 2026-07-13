# Git worktree / branch coordination contract

## authority separation

- content authority: 現在の`git rev-parse --show-toplevel`で得たworktree root。tasks/specs/architecture/docs/graphはここだけでread/writeする。
- repository identity: canonical remoteと`git rev-parse --git-common-dir`を正規化してC24が照合する。
- coordination authority: 検証済みgit common dir配下の`dev-graph/`。lease/event ledger/cacheだけを置き、仕様本文、graph、secret、絶対worktree pathは置かない。
- `worktree_id`はrepository_idとworktree root realpathのhashから`wt_<16hex>`として導出し、durable graphにはhash、branch、HEAD、stateだけを投影する。

## lease state machine

`unclaimed → claimed → in_progress → pending_review → pending_merge → released`を基本経路とする。Claude `TaskCompleted`は`pending_review`へparkするだけでGitHub taskをdoneにしない。open PRのlinkage確認で`pending_merge`へ進む。`pending_review`/`pending_merge`は通常TTLによる自動reclaim対象外とし、staleとしてC15へsurfaceする。明示reclaimはopen branch/PRなしをC26で確認し、利用者確認と監査eventを必須とする。通常のclaim/heartbeat/park/releaseはowner session一致、TTL自動expiryは`claimed|in_progress`だけに適用する。

PR merge後はowner sessionが消滅していても解放できるよう、C26だけがcompletion event (`repository_id + graph_node_id + merge_commit_sha + policy_digest + event_key`) をcommon ledgerへatomic appendする。C27の`system-release`は未消費のcompletion event、現在のpending lease identity、default-branch completion decisionを一致検証して一度だけconsumeし、owner非依存で`released`へ遷移して監査recordを残す。任意入力や通常releaseからsystem-releaseへ昇格できない。

config schemaは`lease_ttl_seconds>=300`かつ`15<=heartbeat_seconds<=60`を強制し、heartbeatがTTLより短いことを構造保証する。runtimeでも値を再検証し、不正configはclaim前にfail-closedとする。

Beads bindingではtask ownershipのauthorityはC28のatomic `bd update --claim`であり、C27 leaseはworktree/resource reservation projectionである。claim transactionは`preflight → C27 reservation → C28 claim → C02 execution_context`の順で、C28失敗時はreservationを解放し、C02失敗時は`pending_reconcile`として同じtransactionを再開する。linked worktreeが同じBeads workspace/database identityを解決できない場合はclaim前に停止する。

同じrepository_id内で同一`graph_node_id`のactive leaseは最大1件。別taskであっても`resource_scope.touches`が重なるleaseはC15/C16が同じparallel batchへ入れない。detached HEAD、branch重複checkout、rebase/cherry-pick中、dirty indexは診断対象とする。

## completion convergence

feature branch/worktreeでPR mergeを観測してもtask specを`done`へ直接書かず、共通event ledgerへpending merge factだけを記録する。durableなtask/graph projectionは次の条件を全て満たすworktreeでC26が更新する。

1. configured default branchである。
2. index/worktreeがcleanで、merge/rebase/cherry-pick中でない。
3. linked PRがdefault branchへ`merged=true`で、completion policyを満たす。
4. C12が返したremote default branch名と一致し、local HEADがmerge_commit_shaをancestorとして包含する。
5. graph schema検証とatomic writeが成功する。

条件未達はデータを上書きせずpending/conflictを残す。manual/scheduled reconciliationで再実行できるため、Claude Code hookは唯一の完了検知経路ではない。

