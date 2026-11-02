# タスク: dev-graph:run-dev-graph-render の実走

## 必須の実行順序（Skill内部の監査にも適用）
standardはこの隔離試行について事前指定済み。追加質問は不要だが、順序は省略しない。
まずmain contextだけで最小成果物/previewを作成する→実在するpathとbytes digestをassistantメッセージで提示する→canonical artifact-deliveryへstandardを記録する→その後でsemantic evaluator/auditor/Agentを起動する。
Agent前に提示と選択記録が揃わなければ、最終状態が合っていてもFAILとして止める。責務の依存順・fixture境界を守る。

この run は scenario render-feature-progress-receipt-positive-fixture-standard-v3 の充足を確認するものです。
1. the generated HTML has zero external resource references and draws features, tasks, and edges as inline SVG
2. LT-FEATURE-001 progress X/Y matches the graph, Y equals the registration receipt expected_count, and the child task set equals the receipt node_ids
3. the render is invoked with the registration receipt and its target corresponds to the receipt source_digest
4. two consecutive renders produce identical output digests

LT-FEATURE-001と一部doneのexact-13子taskを持つ入力fixtureです。registration receiptは/Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/render/fixture/.dev-graph/state/package-registration-receipt-LT-FEATURE-001.json。render-graph-html.pyには必ず--receiptで渡してください。子task集合/node_ids、Y=expected_count、source_digestへの対応を実際に照合し、2回描画のdigest一致と外部resource参照0を確認してください。過去のrender出力はseedから除外済みです。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/render/fixture --output /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/render/fixture/.dev-graph/render/index.html"})

処理が終了 (成功/失敗/中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20261102T010423-ci-full/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-receipt-positive-fixture-standard-v3"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・goal-seek証跡はfixture内eval-log等へ保存する。
- 書込は新fixtureと本run証跡dirだけ。source/plugin/settings/trust/PATH/permissions、旧fixture/過去証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、plugin installを行わない。fixture内fake adapterだけを明示する。
- private sandbox/guardを維持する。PATH/ZDOTDIRは継承のまま。未知gate/拒否を回避しない。未登録SkillをReadやscriptで代替しない。
- artifact_deliveryはstandard事前指定だが、必ず実成果物のpath+digest提示→canonical standard記録→独立評価/Agentの順に実行する。
- scenario予算はwall 900秒/tokens 3000000。poll/verdict両方で強制し延長しない。
