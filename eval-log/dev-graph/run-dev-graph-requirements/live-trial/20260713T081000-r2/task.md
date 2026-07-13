# タスク: dev-graph:run-dev-graph-requirements の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r2-requirements --feature-id LT-TASK-001 --handoff-target /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r2-requirements/.dev-graph/handoff/requirements.json"})

これはcontract-negative試験です。指定IDがfeatureでないことを検出し、readiness不成立としてhandoffと実装codeを生成せず、修復可能な診断を返せばPASSです。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20260713T081000-r2/out/status.json` に完了マーカーを1ファイルだけWriteする。内容: `{"status":"PASS|FAIL|ERROR","scenario":"requirements-fail-closed"}`
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かないこと。中間成果物はfixture repo内またはtrial workdir直下へ置くこと。
