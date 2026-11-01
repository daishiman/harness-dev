# タスク: dev-graph:run-dev-graph-requirements の実走

入力fixture: /private/tmp/claude-501/pr86-ci-live/lt/runs/requirements87/fx。合成のarchitecture-system、confirmed/pass/readiness completeのFEATURE-1、および正規promote・C02 register済みのP01..P13 exact-13 packageがある。入力の生成方法はworkdir/fixture-provenance.jsonに明記した。上流評価の合成データは入力条件であり、あなたの新しい成果の評価として使わない。feature・package・graphの作り直しは禁止。C24とC11で実体を確認する。

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "--repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/requirements87/fx --feature-id FEATURE-1 --package-dir .dev-graph/plans/generations/feature-package-feat/5255c0949b56ca95e8e2e0e5282a0016566e2830b8c826990efb1d2180638bc6"})

SKILL全文・全責務promptをReadし、必要な型の独立Agentを実際に起動する。goal-spec/progress/intermediateとartifact_deliveryのstandard記録をfixture/eval-logに保存する。handoffの出力を確認し、実装ソースを作らない。必須契約を省略したらFAILにする。

scenario required_observations（正本の逐語）:
1. a capability-build task-graph handoff is emitted for the exact-13 package
2. the handoff remains bound to the feature and source digest
3. the requirements skill generates no implementation source file

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/pr86-ci-live/lt/runs/requirements87/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C04-OUT1-positive-ready-handoff-r2"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/pr86-ci-live/lt/runs/requirements87` の内側だけが許可され、外部ネットワークは遮断、gh と既定の bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。
