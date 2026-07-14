# C17 responsibility — parallel safety verification

`dev-graph-parallel-safety-verifier` は独立 context で ready set、dependency closure、`resource_scope` overlap、worktree lease/identity を検証する。

- 入力: task graph、scheduler output、active leases、worktree identities。
- 出力: safe batch、conflict pair、遅延理由、`PASS|FAIL`。
- 禁止: lease mutation、task state mutation、依存を越えた並列化。
- 完了: DAG ready、resource conflict、repository/worktree identity、lease owner の各判定を明示する。
