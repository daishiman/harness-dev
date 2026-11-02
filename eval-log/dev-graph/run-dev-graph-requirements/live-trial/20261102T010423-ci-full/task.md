# タスク: dev-graph:run-dev-graph-requirements の実走

## 必須の実行順序（Skill内部の監査にも適用）
standardはこの隔離試行について事前指定済み。追加質問は不要だが、順序は省略しない。
まずmain contextだけで最小成果物/previewを作成する→実在するpathとbytes digestをassistantメッセージで提示する→canonical artifact-deliveryへstandardを記録する→その後でsemantic evaluator/auditor/Agentを起動する。
Agent前に提示と選択記録が揃わなければ、最終状態が合っていてもFAILとして止める。責務の依存順・fixture境界を守る。

この run は scenario C04-OUT1-positive-ready-handoff-r2 の充足を確認するものです。
1. a capability-build task-graph handoff is emitted for the exact-13 package
2. the handoff remains bound to the feature and source digest
3. the requirements skill generates no implementation source file

入力は現行PlanRepoで正規promote/C02 register済みのFEATURE-1・P01..P13 exact13 packageです。package directoryは/Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/requirements/fixture/.dev-graph/plans/generations/feature-package-feat/c6bf5fe659bc16e25675fda11e187b444f505c5faff5ed8bff84c1caa8a5580f。featureはconfirmed/evaluation pass/readiness completeです。上流findings/readinessの合成データは入力条件だけで、被験requirementsの独立評価結果ではありません。feature/package/graphを作り直さず、C24/C11で実体を確認して正規requirementsのhandoffを生成してください。登録済みtask文書も現行writerが生成済みです。実装ソースを生成しないでください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/requirements/fixture --feature-id FEATURE-1 --package-dir /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/requirements/fixture/.dev-graph/plans/generations/feature-package-feat/c6bf5fe659bc16e25675fda11e187b444f505c5faff5ed8bff84c1caa8a5580f"})

処理が終了 (成功/失敗/中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20261102T010423-ci-full/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"C04-OUT1-positive-ready-handoff-r2"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・goal-seek証跡はfixture内eval-log等へ保存する。
- 書込は新fixtureと本run証跡dirだけ。source/plugin/settings/trust/PATH/permissions、旧fixture/過去証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、plugin installを行わない。fixture内fake adapterだけを明示する。
- private sandbox/guardを維持する。PATH/ZDOTDIRは継承のまま。未知gate/拒否を回避しない。未登録SkillをReadやscriptで代替しない。
- artifact_deliveryはstandard事前指定だが、必ず実成果物のpath+digest提示→canonical standard記録→独立評価/Agentの順に実行する。
- scenario予算はwall 1500秒/tokens 7000000。poll/verdict両方で強制し延長しない。
