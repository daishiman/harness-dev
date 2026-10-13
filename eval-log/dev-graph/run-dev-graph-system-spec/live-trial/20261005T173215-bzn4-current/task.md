# C19 positive current-source live trial
入力repoは /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T173215-bzn4-current-system-spec の隔離Git fixture。system-spec/spec-state.json は現行elicitのexpected-final fixtureを基にした、基礎承認・全coverage・basis・required-info接地済みの入力。targetsはpostgres/react、fetched-references.jsonは現行compile fixtureからの同対象の公式citation input。これらは入力seedで、受入成果やevaluator PASS証拠ではない。準備はdev-graph:initを正規Skillで行いhook-sourceは /Users/dm/dev/dev/個人開発/harness/plugins/dev-graph を指定する。

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T173215-bzn4-current-system-spec --resume"})

system-spec-harnessの現行pinされた4entrypointsのpreflightを通し、elicitのresume、必要時だけdoc-fetch、compile、実Agentのcompleteness evaluatorを正規Skill経路で実行する。既にcitation入力が揃うため、実在外部サービスへ接続しない。正規flowが外部追加取得を必須とするなら迂回せずFAILとする。compiled章と新evaluator evidenceができた後だけC02 Skillで specification/architecture をconfirmed/pass/readiness-completeとして登録する。source_lineageの実source bytes、現行plugin version、confirmation evidenceのevaluated_digest、C11/C19 deterministic gates、C02 receiptを検証し、実際にgoalを満たした場合だけPASS。新しい取込成果がなくfailclosedになっただけならFAIL。

fixtureの事前回答契約: artifact_delivery choice=standard。foundationと各セルの入力承認内容はfixtureのqa_log/approval_logに明示済み。追加の意思決定が必要なら勝手に承認を生成せずFAIL。
書込はfixtureと /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261005T173215-bzn4-current のみ。作業repo source/settings/plugin/install/release/Git/Beads変更・実GitHub/Beads mutation・外部accounts操作は不可。graph/contentは正規writerのみ。被験skill責務の自作driverやhandwritten graph/evaluator PASSは不可。各promptを責務出力前に読む。必須Agentの独立verifier/evaluatorを実際に起動する。Unknown skillなら即FAIL、直接script代替は禁止。
途中で人間に質問せず最後まで自走すること。skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
処理完了時は /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261005T173215-bzn4-current/out/status.json に1ファイルのみ {"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage"} をWriteし、DONE: <status>を1行報告する。out/には他のfileを置かない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。ブラウザ検証が必要なら既存localPlaywright/Chromiumをisolatedprofileで使い、package/browserのinstallはしない。

機械隔離契約: Write/Edit/Artifact/ArtifactComments は CLI で禁止。全子プロセスも macOS sandbox により本 fixture と本 run dir 以外の file write を拒否する。run内 session-state/session-tmp は native CLI の認証・履歴・scratchpad・Agentの実行補助として許可するが、skillの成果物は fixture 内に作る。グローバルconfig/plugin/settingsを変更しない。必要なJSON入力も canonical手順からBashでfixture内へ出す。独立Agentにも同じ境界・prompt先読みを伝える。
必須順序: 起動した各SkillのSKILL.mdと、その出力に先行するprompts/R*.mdを実際にReadしてから writer を実行する。必須Agentを起動する。内部validatorが実行済みならその実結果も記録し、未実施checkをPASSにしない。
