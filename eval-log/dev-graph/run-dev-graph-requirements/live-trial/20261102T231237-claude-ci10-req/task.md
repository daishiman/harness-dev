# タスク: dev-graph:run-dev-graph-requirements の実走 (scenario C04-OUT1-positive-ready-handoff-r2)

この run は scenario C04-OUT1-positive-ready-handoff-r2 の充足を確認するものです。
scenario required_observations（正本の逐語）:
1. a capability-build task-graph handoff is emitted for the exact-13 package
2. the handoff remains bound to the feature and source digest
3. the requirements skill generates no implementation source file

入力 fixture: /private/tmp/harness-claude-ci10-20261102/cases/requirements/fx。合成の architecture、confirmed/pass/readiness complete の FEATURE-1、および正規 promote・C02 register 済みの P01..P13 exact-13 package がある。入力の生成方法は /private/tmp/harness-claude-ci10-20261102/cases/requirements/control/input-provenance.json と preflight.json に明記した。上流評価の合成データは入力条件であり、あなたの新しい成果の評価として使わない。feature・package・graph の作り直しは禁止。C24 と C11 で実体を確認する。

この trial の cwd は harness の作業ツリーです。業務パスはすべて絶対パスを使ってください。plugin は boot が pin した harness 作業ツリーの plugin だけを使います。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "--repo-root /private/tmp/harness-claude-ci10-20261102/cases/requirements/fx --feature-id FEATURE-1 --package-dir /private/tmp/harness-claude-ci10-20261102/cases/requirements/fx/.dev-graph/plans/generations/feature-package-feat/9a04f52c11bdcf4c3f7fc55be0753a693de3ed698baa5d4a112cbb7792d0a379"})

SKILL 全文・全責務 prompt を Read し、必要な型の独立 Agent を実際に起動する。goal-spec/progress/intermediate は skill の定める `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-goal-spec.json`、`run-dev-graph-requirements-progress.json`、`run-dev-graph-requirements-intermediate.jsonl` に保存する。`DEV_GRAPH_ROOT` は fixture `/private/tmp/harness-claude-ci10-20261102/cases/requirements/fx` とし、harness 作業ツリーへは書かない。artifact_delivery の standard 記録も fixture 内に保存する。handoff の出力を確認し、実装ソースを作らない。必須契約を省略したら FAIL にする。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20261102T231237-claude-ci10-req/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容: {"status": "PASS|FAIL|ERROR", "scenario": "C04-OUT1-positive-ready-handoff-r2"}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は fixture 側へ)。

追加の試行境界: 書込先は上記の隔離 fixture と本 run の証跡 dir のみ。作業 repo の source/settings/plugin/install/release/Git/Beads を変更しない。実在 GitHub/Beads/外部サービスへの接続・mutation は禁止。boot が pin した plugin 以外を代用しない。

隔離 fixture の事前回答契約: artifact_delivery の選択は standard。fixture 内成果物を提示してから、この予め指定済みの standard を記録して正規の後続検証へ進める。これは本 repo や外部アカウントの承認ではない。Skill tool が Unknown skill になった場合、直ちに status.json を FAIL で終了し、Read で真似る、または直接 script へ代替しない。

実行の意味: Skill tool は手順を現在 context へロードする。ロード成功だけで writer が実行済みになったとは扱わず、ロードされた SKILL と各責務 prompt に従って canonical writer/validator/必須 Agent を実行し、実成果を作って検証する。

外部公開は禁止: Artifact tool / Claude.ai publish / 外部 artifact 作成は使わない。実成果物は fixture 内ローカル file と、上で指定した status.json のみ。
