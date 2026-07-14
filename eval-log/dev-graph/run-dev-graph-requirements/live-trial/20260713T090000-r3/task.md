# タスク: dev-graph:run-dev-graph-requirements 正経路の実走

fixture repo内に、confirmed/pass/readiness-completeのfeature、C19由来system-spec/architecture lineage、system-dev-planner由来P01..P13 exact 13 task packageを正本schemaとvalidatorで準備してください。共通parent_feature/feature_package_id、前方dependency、source digest、C11 readiness digestを一致させてから以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "handoff --repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-requirements --feature-id LT-FEATURE-001 --package /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-requirements/system-plan/LT-FEATURE-001/package.json"})

handoffが実在してcapability-build/task-graph向け要件・13 task・lineage/digestを持ち、本skillが実装codeを1件も生成していないことを検証してください。system plan validatorとC11がexit0でなければPASSにしないでください。scenario IDは `C04-OUT1-positive-ready-handoff` です。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20260713T090000-r3/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"requirements-positive-handoff"}` をWriteする。
2. `DONE: <status>` と1行だけ報告する。

途中で人間に質問せず最後まで自走し、skillの手順を省略しないこと。out/に中間成果物を書かないこと。
