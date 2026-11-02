# タスク: dev-graph:run-dev-graph-system-spec の実走 (scenario C19-OUT1-positive-system-spec-lineage-r2)

この run は scenario C19-OUT1-positive-system-spec-lineage-r2 の充足を確認するものです。

1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

開始時に repo root の CLAUDE.local.md を Read し、各独立 Agent/Skill が同じ既存契約を受信することを守る。

fixture repo-root (以下 `<FX>`) は
`/private/tmp/harness-claude-ci10-20261102/cases/system-spec/fx`
です。git の commit は空の "fixture: canonical resume inputs" が 1 つあるだけです。dev-graph は正規 builder で初期化済みで、graph.nodes は空です。入力は未追跡の `system-spec/` の state・出典資料・compiled 章です。評価 report、PASS 結果、登録結果、取込 payload、監査台帳の行は種として置いていません。compiled 章は再開入力であり、今回の compile・evaluator・登録の証拠に代用しないでください。入力を準備のために書き換えず、変えるのは skill の正規 writer だけです。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /private/tmp/harness-claude-ci10-20261102/cases/system-spec/fx --resume"})

system-spec-harness の pin された entrypoint の preflight を通し、elicit の resume、必要なときだけ doc-fetch、compile、completeness evaluator (実際の Agent) を、正規の Skill の経路で実行してください。公式文書の取得と照合は WebFetch で行い、次の 5 host への https の読み取り (GET) だけが許可されています: www.postgresql.org・react.dev・fastapi.tiangolo.com・www.typescriptlang.org・kubernetes.io。WebSearch・ほかの host・認証が要る先・Bash のネットワーク CLI は使えません。正規の flow がそれ以外の外部取得を必須とするなら、迂回せずに FAIL にしてください。
compile された章と新しい evaluator の evidence ができた後でだけ、C02 の Skill で specification と architecture を confirmed・pass・readiness complete として登録してください。

この scenario (C19-OUT1-positive-system-spec-lineage-r2) で確かめる観測です。すべてを実測で満たさなければ PASS にしないでください:

1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

経路に関する絶対制約 (違反した時点でこの trial は無効):
- 成果物を生成する自作スクリプトを書かないこと。
- spec-state・fetched-references・compile の成果は system-spec-harness の正規 writer で、graph と content は C02 単一 writer (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) で作ること。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が要求する独立 Agent は Agent tool で実際に別 context として起動すること。手書きの evaluator PASS で代替しないこと。
- 実行できないと判断した場合は、代替実装で回避せず、status.json に FAIL を書き、何が実行不能だったかを報告すること。

foundation と各セルの承認内容は、fixture の qa_log と approval_log に明示済みです。ほかに意思決定が要るなら、承認を勝手に作らず FAIL にしてください。

配置の注記: この session は fixture の root (`/private/tmp/harness-claude-ci10-20261102/cases/system-spec/fx`) を cwd として起動しています。plugin は同じ root の `plugins/` にある写しを `--plugin-dir` で読み込んでいます。

ネットワークの注記: WebFetch による上の 5 host への https の読み取り (GET) だけは許可されています。それ以外は遮断のままです。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261103T065037-claude-ci12-sysspec/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容: {"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage-r2"}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

追加の試行境界: 書込先は上記の隔離 fixture と本 run の証跡 dir のみ。作業 repo の source/settings/plugin/install/release/Git/Beads を変更しない。実在 GitHub/Beads/外部サービスへの接続・mutation は禁止。予算は wall 3300 秒、tokens 23000000。延長しない。

隔離 fixture の事前回答契約: artifact_delivery の選択は standard。fixture 内成果物を提示してから、この予め指定済みの standard を記録して正規の後続検証へ進める。これは本 repo や外部アカウントの承認ではない。Skill tool が Unknown skill になった場合、直ちに status.json を FAIL で終了し、Read で真似る、または直接 script へ代替しない。
