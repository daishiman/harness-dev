# タスク: dev-graph:run-dev-graph-requirements の実走 (scenario C04-OUT1-positive-ready-handoff-r2)

この run は scenario C04-OUT1-positive-ready-handoff-r2 の充足を確認するものです。
scenario required_observations（正本の逐語）:
1. a capability-build task-graph handoff is emitted for the exact-13 package
2. the handoff remains bound to the feature and source digest
3. the requirements skill generates no implementation source file

入力 fixture: /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/requirements2/fx。合成の architecture、confirmed/pass/readiness complete の FEATURE-1、および正規 promote・C02 register 済みの P01..P13 exact-13 package がある。入力の生成方法は /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/requirements2/fx/../control/input-provenance.json と preflight.json に明記した。上流評価の合成データは入力条件であり、あなたの新しい成果の評価として使わない。feature・package・graph の作り直しは禁止。C24 と C11 で実体を確認する。

この session の cwd は信頼済みの harness worktree `/Users/dm/orca/workspaces/harness/harness-creatorの改善` です。業務の読み書きは fixture `/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/requirements2/fx` の絶対パスだけを使ってください。plugin は boot が harness worktree の plugins/ を --plugin-dir で pin します。harness 作業ツリー、settings、plugin 本文は編集しないでください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "--repo-root /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/requirements2/fx --feature-id FEATURE-1 --package-dir /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/requirements2/fx/.dev-graph/plans/generations/feature-package-feat/851f6700701209795092ce6bb141be5100af2099bd3f22a59ed26a00f03a71a4"})

SKILL 全文・全責務 prompt を Read し、必要な型の独立 Agent を実際に起動する。goal-spec/progress/intermediate は skill の定める `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-requirements-goal-spec.json`、`run-dev-graph-requirements-progress.json`、`run-dev-graph-requirements-intermediate.jsonl` に保存する。`DEV_GRAPH_ROOT` は fixture `/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/requirements2/fx` とし、harness 作業ツリーへは書かない。artifact_delivery の記録 (初回の選択 `diagnose`、診断の所見の後に改善の深さを聞かれたら `standard`) も fixture 内に保存する。handoff の出力を確認し、実装ソースを作らない。必須契約を省略したら FAIL にする。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20261115T1830-r44-req2/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容: {"status": "PASS|FAIL|ERROR", "scenario": "C04-OUT1-positive-ready-handoff-r2"}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は fixture 側へ)。
- hook に止められた操作は、別 file への移し替え・interpreter の変更・文字列の組み替えなど、形を変えて再試行しないこと。止められたら理由を読み、正規の道具 (Write / Edit の道具、または skill が定める script) で同じ記録を書けるかを考える。書けなければ、そこで止めて status.json を FAIL にし、止めた操作と理由を報告すること。

追加の試行境界: 書込先は上記の隔離 fixture と本 run の証跡 dir のみ。作業 repo の source/settings/plugin/install/release/Git/Beads を変更しない。実在 GitHub/Beads/Notion/外部サービスへの接続・mutation は禁止 (bd・gh などの外部書込コマンドを実行しない)。外部書込の確認用 preview も作らない・提示しない。boot が pin した plugin 以外を代用しない。

隔離 fixture の事前回答契約: artifact_delivery の初回の選択は `diagnose`。診断の所見の後に改善の深さを聞かれたら `standard`。fixture 内成果物を提示してから、この予め指定済みの選択を記録して正規の後続検証へ進める。これは本 repo や外部アカウントの承認ではない。Skill tool が Unknown skill になった場合、直ちに status.json を FAIL で終了し、Read で真似る、または直接 script へ代替しない。

実行の意味: Skill tool は手順を現在 context へロードする。ロード成功だけで writer が実行済みになったとは扱わず、ロードされた SKILL と各責務 prompt に従って canonical writer/validator/必須 Agent を実行し、実成果を作って検証する。

外部公開は禁止: Artifact tool / Claude.ai publish / 外部 artifact 作成は使わない。実成果物は fixture 内ローカル file と、上で指定した status.json のみ。

資源予算: wall 1500 秒、tokens 7000000。延長しない。
