# タスク: dev-graph:run-dev-graph-system-spec の実走

## 必須の実行順序（Skill内部の監査にも適用）
standardはこの隔離試行について事前指定済み。追加質問は不要だが、順序は省略しない。
まずmain contextだけで最小成果物/previewを作成する→実在するpathとbytes digestをassistantメッセージで提示する→canonical artifact-deliveryへstandardを記録する→その後でsemantic evaluator/auditor/Agentを起動する。
Agent前に提示と選択記録が揃わなければ、最終状態が合っていてもFAILとして止める。責務の依存順・fixture境界を守る。

この run は scenario C19-OUT1-positive-system-spec-lineage-r2 の充足を確認するものです。
1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

system-spec/は確定問答・出典・compiled章だけの正規再開入力です。graphは空で、評価report・PASS結果・登録結果・取込payloadをseedに置いていません。compiled章を今回の行動証拠へ代用せず、--resumeから現行正規flow、新しい独立評価、C02登録を実行してください。取込payloadはC19 R3に従い新しいevaluator PASSの後に作成してください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/system-spec/fixture --resume"})

処理が終了 (成功/失敗/中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261102T010423-ci-full/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage-r2"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・goal-seek証跡はfixture内eval-log等へ保存する。
- 書込は新fixtureと本run証跡dirだけ。source/plugin/settings/trust/PATH/permissions、旧fixture/過去証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、plugin installを行わない。fixture内fake adapterだけを明示する。
- private sandbox/guardを維持する。PATH/ZDOTDIRは継承のまま。未知gate/拒否を回避しない。未登録SkillをReadやscriptで代替しない。
- artifact_deliveryはstandard事前指定だが、必ず実成果物のpath+digest提示→canonical standard記録→独立評価/Agentの順に実行する。
- scenario予算はwall 3300秒/tokens 23000000。poll/verdict両方で強制し延長しない。
