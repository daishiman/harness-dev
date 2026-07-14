# GitHub task lifecycle contract

## 結論

タスク完了の既定トリガーは「PRがcloseされた」ではなく、`default branch`向けのlinked PRが`merged=true`になった事実とする。PR close未mergeは完了ではない。GitHub IssueとProjectsのnative automationをremote fast pathとして使い、dev-graphのC03 reconciliationを最終的な整合・repair経路とする。

## Authorityと状態遷移

1. `task specification`がlocal content SSOT、`graph_node_id`が不変identity。
2. C14はtask batchをlocal atomic commit後、resolved tracker bindingに従ってGitHubならC12、BeadsならC28へ択一publicationする。noneは外部起票しない。
3. 実装PR本文は常に`dev-graph: <graph_node_id>`を持つ。GitHub bindingでは加えて`Closes #<issue>`またはcross-repo形式、Beads bindingではmirror Issueがある場合だけclosing keywordを持ち、remoteの現在default branchをtargetにする。
4. PR openでtaskは`in_progress`。PR close未mergeは`keep_active`または設定により`blocked`。自動doneは禁止。
5. linked PR mergeでGitHubがIssueをauto-closeし、Projects built-in workflowがStatusをDoneへ更新する。これはremote fast pathで、Projects Statusからtask doneへの逆流は禁止する。
6. C12はremote `defaultBranchRef{name,target.oid}` とPR factsを取得する。C26はremote default名一致、merged=true、policy、PR marker/closing reference、`merge-base --is-ancestor <merge_sha> HEAD`を検証し、event-key receiptでgraph patch→C02 task frontmatter→C28 bd closeの順に未適用stepだけを収束させる。feature branchではpending eventだけを記録する。

## 複数PR・reopen・revert

- 既定は`required_pull_requests=all`。linked PRが複数なら全required PR mergeまでdoneにしない。小規模taskだけ明示的に`any`を許可する。
- Issue reopenはtaskを`active`へ戻し、Project Statusもmappingに従って再同期する。
- direct Issue closeのreason=`not planned`はdoneではなく`closed`として扱う。reason=`completed`でもPR evidenceが必要なpolicyではmanual conflictへ送る。
- revert PRは元taskを自動未完了へ戻さず、Issueがreopenされた場合だけ同taskを再開する。それ以外はrevert/follow-up taskを新規作成して履歴を保存する。

## Remote fast pathとlocal reconciliation

- Remote: GitHub linked-issue auto-close + Projects built-in Done workflow。symlink先のlocal harnessをGitHub runnerから実行しない。
- Local primary repair: `dev-graph sync`。hookやCI実行有無に依存せず、GitHub remote factsから何度でも冪等再構築できる。
- Local acceleration: C25のClaude Code `PostToolUse(Bash)`が成功済み`git pull`/`git merge`/`gh pr merge`を観測してC26をasync起動する。plugin hookを共有既定、project settingsをfallbackとし、hookは唯一のauthorityにしない。
- Scheduled repair: 長期offlineやhook未設定に備え、次回status/requirements/decompose実行前または設定周期でC03を走らせる。
- scheduled ownerはrepo configで一意にする。`claude_session_start`はC25が最終実行時刻とintervalを見て期限到来時だけ起動し、`host_scheduler`はrepo rootで固定entry point `dev-graph sync --reconcile-lifecycle`を呼ぶ。両者の同時所有は禁止し、event ledgerで重複実行をno-opにする。
- local task spec更新はcleanなdefault-branch worktreeだけで行う。default worktree不在またはdirty/diverged/rebase中はpendingのまま停止し、自動push/PR作成は利用者の明示設定・承認なしに行わない。

## Idempotencyとevent ledger

- event key: `<repo>#pr:<number>#<merge_commit_sha>`、Issue eventは`<repo>#issue:<number>#<updated_at>`。
- 同じevent keyは一度だけ適用する。再実行は差分0件。
- Project field valueの`updatedAt`が取得できる場合は競合hintに使い、削除/欠落/option renameを含むcanonical baseはlast-synced snapshotとする。Status/doneはlocal→Project一方向、その他の許可fieldだけ3-way双方向にできる。
- external mutationの部分失敗はalias単位`pending_retry`。local completion evidenceの保存とProject field retryを分離する。

## 公式仕様参照

- GitHub Docs: Linking a pull request to an issue — https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
- GitHub Docs: Using the built-in automations — https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations
- GitHub Docs: Best practices for Projects — https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/best-practices-for-projects
- GitHub Docs: Managing the automatic closing of issues — https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-auto-closing-issues
