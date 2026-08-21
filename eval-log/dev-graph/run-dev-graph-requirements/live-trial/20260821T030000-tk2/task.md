# タスク: dev-graph:run-dev-graph-requirements の実走

fixture repo内のconfirmed/pass/readiness-completeのfeature、C19由来system-spec/architecture lineage、system-dev-planner由来P01..P13 exact 13 task packageを使用してください。共通parent_feature/feature_package_id、前方dependency、source digest、C11 readiness digestを一致させてから以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "handoff --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-requirements --feature-id LT-FEATURE-001 --package /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-requirements/system-plan/LT-FEATURE-001/package.json"})

handoffが実在してcapability-build/task-graph向け要件・13 task・lineage/digestを持ち、本skillが実装codeを1件も生成していないことを検証してください。system plan validatorとC11がexit0でなければPASSにしないでください。scenario IDは `C04-OUT1-positive-ready-handoff` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/orca/workspaces/harness/トークン削減対策/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20260821T030000-tk2/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"requirements-positive-handoff"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
