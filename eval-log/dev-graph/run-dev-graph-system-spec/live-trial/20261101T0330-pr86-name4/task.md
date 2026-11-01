# タスク: dev-graph:run-dev-graph-system-spec の実走 (C19・現行の出典で取り込む)

### 入力 (準備済み)

fixture repo-root (以下 `<FX>`) は
`/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec100/fx`
です。git init した repo で、空の commit ("isolated current-source input") が 1 つあるだけです。dev-graph は正規builderで初期化済み、graph.nodesは空です。入力は未追跡の `system-spec/` のstate・出典資料・compiled章です。

- `system-spec/spec-state.json`: 前回の C19 の試験 (2026-10-12) の準備役 (orchestrator) が、system-spec-harness の正規 writer で組み立てた state です。基礎の承認 (appr-foundation-v2)・全 coverage・basis・required-info の接地が済んでいます。targets は postgres・react・fastapi・typescript、decisions は D1・D2・D3 (confirmed)、knowledge_candidates に k8s-workload-observability (deepened) があります。qa_log の利用者発言は、どれも orchestrator がシナリオ上の利用者の発言として書いたもので、実利用者との対話ではありません (各 entry の provenance に書いてあります)。
- 上の state には、今回の準備で `qa-foundation-u1`〜`u9` の 9 件を正規 writer の `chunk` で追記してあります。前回の試験の後に、上位概念 U1〜U9 の根拠を `qa-foundation-u<N>` の索引で示す契約が足されたためです。各 entry の answer は、appr-foundation-v2 の対応表でその U の根拠とされたシナリオ上の利用者発言を、逐語のまま連結したものです (新しい内容は足していません。経緯は各 entry の provenance にあります。provenance の日付 2026-10-30 は、この追記の内容を最初に組み立てた日です)。追記の副作用として、`hearing_progress.loop_count` が数え直されています。
- `system-spec/fetched-references.json` と `retrieval-evidence/`: 前の実走で正規doc-fetchが取得し、公式hostとdigestへ接地した資料。その実走で正規writerが更新したspec-stateと共に、今回はそのまま再開入力にした。取得日時・採用版・方針は入力の記録を確認し、doc-fetchの要否は正規Skillで判断すること。compiled章は今回の再開入力として複製済みだが、評価report・監査台帳・graphのnode・resume receiptは種として置いていない。過去の実走の評価結果は、今回の行動や判定の証拠へ転用しない。fixture-provenance.json参照。

これらは試験の入力 (seed) で、取込の成果や evaluator の PASS の証拠ではありません。**fixture の入力を準備のために書き換えないこと。** 入力を変えるのは、skill の正規経路の writer だけです。

### 準備済みの再開入力

- このrepoはC01の正規builderで初期化済み（workdir/fixture-init-receipt.json）。graph.nodesは空で、取込結果は無い。C01のSkillを実行するタスクではない。
- system-spec/には前の正規writerが作ったcompiled章もある。これらは再開入力であり、今回のcompile実行・evaluator・登録の成果として代用しない。C19の正規経路で再compile・新規独立評価を行う。
- candidate-import.jsonは前の実走のC02入力を基にした草案。confirmation_evidenceとimported_atは削除済みで、承認/確定根拠ではない。必要ならschema/sectionsの入力草案として参照できるが、今回のsource bytes/version/digestと新しいevaluator証拠へ正規に接地させてから使う。
- fixture-provenanceは `/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec100/workdir/fixture-provenance.json`。fixture入力を探すために / 全体を走査する必要はない。

### 本題

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec100/fx --resume"})

system-spec-harness の pin された entrypoint の preflight を通し、elicit の resume、必要なときだけ doc-fetch、compile、completeness evaluator (実際の Agent) を、正規の Skill の経路で実行してください。公式文書の取得と照合は WebFetch で行い、次の 5 host への https の読み取り (GET) だけが許可されています: www.postgresql.org・react.dev・fastapi.tiangolo.com・www.typescriptlang.org・kubernetes.io。WebSearch・ほかの host・認証が要る先・Bash のネットワーク CLI は使えません。正規の flow がそれ以外の外部取得を必須とするなら、迂回せずに FAIL にしてください。
compile された章と新しい evaluator の evidence ができた後でだけ、C02 の Skill で specification と architecture を confirmed・pass・readiness complete として登録してください。

### 検証

この scenario (C19-OUT1-positive-system-spec-lineage-r2) で確かめる観測です。すべてを実測で満たさなければ PASS にしないでください:

1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

追加で確かめること:
- source_lineage が実在する source の bytes を指し、その digest が一致すること
- 登録した node の confirmation evidence の evaluated_digest が、評価した成果物と一致すること
- 現行の plugin version・C11 と C19 の決定論の gate・C02 の receipt
- 新しい取込の成果が無く、fail-closed で止まっただけなら FAIL にすること
- skill の checklist が PARTIAL・not_achieved を残すなら PASS にしないこと

経路と役割ごとの保護条件:
- 仕様state・出典記録・章はsystem-spec-harnessの正規writerだけで生成し、graphと登録contentはC02単一writerで作る。dev-graph親がこれらを生成する独自driver/renderer/evaluatorを作り、正規Skillを代替することは禁止。正規writerへ渡す入力JSON、呼出しログ、実行結果の構造化はwriterそのものの代替とは区別する。
- C05は正規Skillの本物のforkで評価し、C07/C06/C08は実Agentを1件ずつ起動して完了を待ち、実completionのreceipt/digestへ判定を結ぶ。親の自己判定や手製のPASSで代替しない。
- 正規C05自身が、実際に行った意味評価・canonical gate stdout・実auditor結果をJSONへ整形することは、親による偽evaluatorではない。C05のread-only Pythonのstdoutや許可scratchでの一時的serializerは、それが文書/state/graphを生成/変更せず、独立評価を代替せず、最終JSONがC05の実判断とreceiptを忠実に保持し、指定されたreport pathだけを最終出力とする場合に区別して扱う。単に「自作script」という語が出たことだけで未達とせず、実際の書込先・処理・帰属を確認する。各roleのallowed-toolsは尊重し、C05へWrite等を追加しない。
- このhostのAgentは、run_in_background/nameを指定しなくてもruntimeがAsync launchを返す。C05が明示的にbackground/nameを要求しないこと、1message1forkで実completion確定後に次を起動すること、起動受理payloadを判定にしないこと、台帳の全必須行がresolvedであることを確認する。runtimeのAsyncという表示だけを、明示的なasync/canary選択や並列監査と同一視しない。実際に並列起動・起動受理の判定流用・receipt不一致があればFAIL。
- 責務promptをその出力前に読み、必須Verifier/Agentを省略しない。 sourceのchecklist/feedback契約、C24固定root、各周回3CLI実測とIN1/6キー/hash記録、C05の独立性/全gate、C02単一writer/lineage/evaluated_digestはすべて必須。
- 正規SkillがUnknown/必須gateが未達なら別実装へ逃げずFAIL。出力JSONの保存先不明による拒否はsource R1-score4.3のliteral保存先への正規再試行を認める。sourceが明示する回復まで一律禁止しない。仕様書の直接改変・偽評価・外部effectの拒否を別toolで迂回することは認めない。

foundation と各セルの承認内容は、fixture の qa_log と approval_log に明示済みです。ほかに意思決定が要るなら、承認を勝手に作らず FAIL にしてください。

配置の注記: この session は fixture の root (`/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec100/fx`) を cwd として起動しています。plugin は同じ root の `plugins/` にある写しを `--plugin-dir` で読み込んでいます (`plugins/` と `.claude/` は fixture の `.git/info/exclude` で git の追跡外にしてあります)。

ネットワークの注記: 後半の「隔離環境の注記」にある「外部ネットワークは遮断」には、この run に限り例外が 1 つあります。WebFetch による上の 5 host への https の読み取り (GET) だけは許可されています。それ以外 (ほかの host・WebSearch・Bash のネットワーク CLI) は遮断のままです。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec100/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage-r2"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec100` の内側だけが許可され、外部ネットワークは遮断、gh と既定の bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。

契約履行の確認: 責務prompt全文を成果作成前にReadし、必須の型のAgentを実際に起動する。goal_seekのgoal-spec/progress/intermediateとartifact_deliveryのstandard選択記録をfixture内eval-logへ保存する。契約を省略したらFAILとする。
scenario required_observations（正本の逐語）:
1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

今回の入力の補足（試行開始前の準備）:
- 基礎の承認・質問/回答・採択は既存の合成入力どおり。利用者の新たな承認を作らない。前の実走の正規writerでqa単位の設計解釈とD1の採用PostgreSQL16の出典整合まで済んだstateを再開入力とし、元のfixture問答と採用判断は変えていない。
- 全責務promptとC19のgoal-seek配線を読み、親と責務Agentのログ所有権・6必須キー検査を含む契約を実行する。条件を満たさなければFAILで、手順を省略してPASSにしない。










実行前の契約確認:
- 現行C19と4 SkillのSKILL/責務promptを全文読み、そのゴールと停止条件を実行する。C24 receipt/rootを固定し、各生成Bashでexport/cd/pwdを確認する。親はC19集約ログ、子は各責務dirを所有する。
- 毎周回coverage/source-citation/schemaの3CLIを実行してからIN1を記録する。空graphもschema実行、全exit0後のみPASS、未実施/待ちはnot_achieved。その後intermediate6キーと元goal/hashを検査。直前の次指示を新周回より先に入力する。
- 各run Skillの最小成果物を提示してから事前回答standardを記録する。compile CLI末尾にpath/digestと「開き方: less <絶対repo-root>/system-spec/index.md」を表示し、その後の別呼出しでcompile-standard.jsonへ記録する。OUT1 tests/意味評価Agentはその後。
- C05の直前にhelperの成功出力そのままのargsを渡す。C05へrole毎の保護条件とこのhostのAsync応答の実態を共有する。reportのspec_dir/outputは引数どおり、指定pathへliteral保存し、原文JSON/receiptを忠実に保持。R1/R2の安全な保存例と同じ境界を満たす一時的なJSON整形と、正規evaluatorを置換する生成器を混同しない。sourceが禁止する仕様state/章/graphの書換はしない。
- hostはzsh/TMPPREFIXを許可run内へ固定、引用heredoc使用可。隔離guardのJSONデータ識別はprovenanceどおりで書込root/外部effect制約は維持。被験側はguard/settings/sandbox/plugin sourceを変えない。
- scratch単体検証は許可絶対pathだけ、caller取込元はreadonly、scratch成果をC05/C02証拠へ代用しない。コード全体回帰は外側で914PASS済みだが今回のflow行動証拠へ代用しない。
- qa008は原初schema1.0から正規backfillした同一問答の入力で、未確認RTO/RPO文は除去済み。既存問答/承認/採択を変えず、今回の再compile・新しい独立評価・正規C02登録を行う。

保存方法の確認: C05/R1-score 4.3 の allowed-tools を守る。Write/Edit は使わない。評価JSONはread-only Pythonのstdoutで組み立てられるが、ファイル保存は literal pathlib.Path("指定絶対output").write_text(sys.stdin.read(), encoding="utf-8") と引用JSON heredocを使う。補助scriptのファイル保存も行わない。この既存契約をC05へ起動前に明示共有する。

既存sourceの問答履歴の区別をC05直前に共有する: R6-audit-hearingのactive consumerは確定cell.qa_refとrequirements_foundation.effective_source_refsのqa_refである。apply-spec-transition.py::_supersede_qaは補助qa_refsの旧問参照を履歴として残すことを明示許可し、compileは旧版の印と現行根拠ではない旨を描く。qa_refsの存在だけをactive consumerと数えず、主根拠/bindingと置き換え(a)(b)(c)を個別確認する。履歴を削除せず、無効な置き換え・実active consumer・他欠陥があれば通常どおりFAIL。この定義と保存契約を共有後、helper argsを無変更でC05へ渡し、C06にも担当source全体を読ませる。

既存sourceの問答履歴の区別をC05直前に共有する: R6-audit-hearingのactive consumerは確定cell.qa_refとrequirements_foundation.effective_source_refsのqa_refである。apply-spec-transition.py::_supersede_qaは補助qa_refsの旧問参照を履歴として残すことを明示許可し、compileは旧版の印と現行根拠ではない旨を描く。qa_refsの存在だけをactive consumerと数えず、主根拠/bindingと置き換え(a)(b)(c)を個別確認する。履歴を削除せず、無効な置き換え・実active consumer・他欠陥があれば通常どおりFAIL。この定義と保存契約を共有後、helper argsを無変更でC05へ渡し、C06にも担当source全体を読ませる。

今回とくに実行前に確認する、既存sourceの責務/ツール契約（判定基準の変更ではない）:
1. C05起動直前に、次のC05/C06/C07/C08の制約を会話へ明示し、helperの引数は無変更で渡す。C05は各auditorへのAgent promptにもそのroleの制約と必読SSOTの絶対pathを明示する。必読を担当者がReadした証跡か、同じSSOT全文を起動promptへinlineした証跡が必要。自分が読んだだけで子も読んだとみなさない。
2. C05の道具はRead/Bash(python3 *)/Agent/Taskだけ。Bash cat/grep/rg/find/ls/head/tail/tee、TaskStop/TaskOutput、Write/Editを使わない。ファイルの参照や検索はRead、JSON/正規gate結果の読取はReadまたはsourceが認めるPython処理。gate stdoutの取得は正規CLIかPython subprocess.run(capture_output=True)で行い、teeを使わない。ファイル保存は指定先をliteralにしたPath.write_text(sys.stdin.read())と引用JSON heredoc。独立監査の起動は明示background/nameなし、runtimeが自動Asyncを返した場合は完了通知とReadで読める正規台帳を待ち、TaskStop等で完了を代替しない。
3. C07は必読R7-audit-matrix.md全文と必要stateをReadし、Bashは正規validate-coverage-matrix.pyの2モードだけ。集計/qa_refs解析/カテゴリJSON抽出のための自作Python・grep等は使わずRead結果から意味評価する。R7のツール制約とagent定義の差分に気づいても広い側へ拡張しない。
4. C06は必読R6-audit-hearing.md/neutral-question-criteria.mdをReadし、Bash Pythonはsourceが許すpath containment/SHAの確認だけ。grep/head/JSON集計Python等で監査本文の参照を代替しない。qa_refsの履歴とactive consumerの定義は前述のsourceに従い、全QA/全bindingをReadして意味評価する。
5. C08は監査開始前にR4-audit-doc-freshness.md全文をRead（またはそのSSOT全文のinline起動promptを読む）し、official-source-catalog.md、stateのtargetsとfetched-referencesもRead。専門agent定義だけを読んで別正本を読んだことにしない。正規C13と実WebFetch/WebSearchによる2層監査を実施する。
6. C05 PASS後、C02のSkillを呼ぶ前に、親自身がrun-dev-graph-node/promptsのR0-context.md/R1-classify.md/R2-preview.md/R3-write.md/R4-apply-template.mdを全文Readする。一部Layerだけのsed出力では全文読込にならない。子R3-writeが全文を読んでも親のR0/R1/R2/R4を代替しない。全責務を読んだ後にC02へ渡して、その規定のpre-choice/正規writer/独立監査を維持する。
7. C19の完了記録も指定eval-log/workdirのファイルだけ。system-spec章/state/graphの直接書換はしない。保護hookがPythonの出力先変数を解決できない場合、出力先をliteral Pathへ固定しJSONを引用heredocで渡す。Bash Write先にsystem-specの文字列がデータとして現れたことと実際の書込先は区別するが、sourceを変えて回避しない。
これらはsourceに元からある条件を具体化したもの。役割制約に合わないコマンドを『readonlyだから』と実行せず、正規Read/CLIへ切り替える。出典/問答/確定/approvalを削除したり、判定や原本を改変したり、過去のPASS/実走を今回の観測へ流用しない。
