# タスク: dev-graph:run-dev-graph-status の実走

## 必須の実行順序（Skill内部の監査にも適用）
standardはこの隔離試行について事前指定済み。追加質問は不要だが、順序は省略しない。
まずmain contextだけで最小成果物/previewを作成する→実在するpathとbytes digestをassistantメッセージで提示する→canonical artifact-deliveryへstandardを記録する→その後でsemantic evaluator/auditor/Agentを起動する。
Agent前に提示と選択記録が揃わなければ、最終状態が合っていてもFAILとして止める。責務の依存順・fixture境界を守る。

この run は scenario C18-OUT1-positive-read-only-status-fixture-standard-v2 の充足を確認するものです。
1. the reported status, closed_at, and depends_on of task-lt-task-001 match the graph store values
2. C11 validate-graph-schema exits 0 on the queried graph
3. the graph digest is unchanged across the status run and GitHub/Beads writes are 0

fixtureはdev-graph未初期化の素Gitです。まずSkill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/status/fixture --hook-source plugin"})を正規経路で実行してください。次にdev-graph:run-dev-graph-nodeのC02単一writerでslug lt-task-001を含む複数taskを登録し、writerが割り当てるtask-lt-task-001にdepends_onと意味のあるclosed_atを持たせてください。準備のinit/nodeもSKILL/責務promptを省略せず実行します。graphを手作業で作成しないでください。その後status Skillを呼び、対象のstatus/closed_at/depends_onを含むreport本文をそのまま出力し、C11 exit0とstatus前後graph digest不変、外部writes0を確認してください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-status", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/status/fixture --id task-lt-task-001"})

処理が終了 (成功/失敗/中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-status/live-trial/20261102T010423-ci-full/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"C18-OUT1-positive-read-only-status-fixture-standard-v2"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・goal-seek証跡はfixture内eval-log等へ保存する。
- 書込は新fixtureと本run証跡dirだけ。source/plugin/settings/trust/PATH/permissions、旧fixture/過去証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、plugin installを行わない。fixture内fake adapterだけを明示する。
- private sandbox/guardを維持する。PATH/ZDOTDIRは継承のまま。未知gate/拒否を回避しない。未登録SkillをReadやscriptで代替しない。
- artifact_deliveryはstandard事前指定だが、必ず実成果物のpath+digest提示→canonical standard記録→独立評価/Agentの順に実行する。
- scenario予算はwall 1800秒/tokens 8000000。poll/verdict両方で強制し延長しない。
