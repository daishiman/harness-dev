# C19 positive current-source live trial
入力repoは /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/sysspec3/fx の隔離Git fixture。system-spec/spec-state.json は現行elicitのexpected-final fixtureを基にした、基礎承認・全coverage・basis・required-info接地済みの入力。targetsはpostgres/react/fastapi/typescript (fastapi と typescript は、decisions D1/D2 の evidence_refs を targets に載せるため、trial の前に正規 writer の set-targets で足したもの)。fetched-references.jsonは現行compile fixtureからの postgres/react の公式citation inputで、fastapi/typescript の record は無い。これらは入力seedで、受入成果やevaluator PASS証拠ではない。準備はdev-graph:initを正規Skillで行いhook-sourceは /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/sysspec3/ws/plugins/dev-graph を指定する。

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/sysspec3/fx --resume"})

system-spec-harnessの現行pinされた4entrypointsのpreflightを通し、elicitのresume、必要時だけdoc-fetch、compile、実Agentのcompleteness evaluatorを正規Skill経路で実行する。公式文書の取得と照合は WebFetch で、次の 4 host への https の読み取り (GET) だけ許可する: www.postgresql.org・react.dev・fastapi.tiangolo.com・www.typescriptlang.org。WebSearch・ほかの host・認証が要る先・Bash のネットワーク CLI は使えない。正規flowがそれ以外の外部取得を必須とするなら迂回せずFAILとする。compiled章と新evaluator evidenceができた後だけC02 Skillで specification/architecture をconfirmed/pass/readiness-completeとして登録する。source_lineageの実source bytes、現行plugin version、confirmation evidenceのevaluated_digest、C11/C19 deterministic gates、C02 receiptを検証し、実際にgoalを満たした場合だけPASS。新しい取込成果がなくfailclosedになっただけならFAIL。

fixtureの事前回答契約: artifact_delivery choice=standard。foundationと各セルの入力承認内容はfixtureのqa_log/approval_logに明示済み。追加の意思決定が必要なら勝手に承認を生成せずFAIL。
書込はfixtureと /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/sysspec3/workdir のみ。作業repo source/settings/plugin/install/release/Git/Beads変更・実GitHub/Beads mutation・外部accounts操作は不可。graph/contentは正規writerのみ。被験skill責務の自作driverやhandwritten graph/evaluator PASSは不可。各promptを責務出力前に読む。必須Agentの独立verifier/evaluatorを実際に起動する。Unknown skillなら即FAIL、直接script代替は禁止。
途中で人間に質問せず最後まで自走すること。skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
処理完了時は /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/sysspec3/workdir/out/status.json に1ファイルのみ {"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage"} をWriteし、DONE: <status>を1行報告する。out/には他のfileを置かない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。ブラウザ検証が必要なら既存localPlaywright/Chromiumをisolatedprofileで使い、package/browserのinstallはしない。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/sysspec3` の内側だけが許可され、gh/bd は stub です。外部ネットワークは、WebFetch による www.postgresql.org・react.dev・fastapi.tiangolo.com・www.typescriptlang.org への https の読み取りを除いて遮断されています。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。
