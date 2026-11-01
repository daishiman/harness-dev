# タスク: dev-graph:run-dev-graph-system-spec の実走 (C19・現行の出典で取り込む)

### 入力 (準備済み)

fixture repo-root (以下 `<FX>`) は
`/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec96/fx`
です。git init した repo で、空の commit ("isolated current-source input") が 1 つあるだけです。dev-graph は正規builderで初期化済み、graph.nodesは空です。入力は未追跡の `system-spec/` のstate・出典資料・compiled章です。

- `system-spec/spec-state.json`: 前回の C19 の試験 (2026-10-12) の準備役 (orchestrator) が、system-spec-harness の正規 writer で組み立てた state です。基礎の承認 (appr-foundation-v2)・全 coverage・basis・required-info の接地が済んでいます。targets は postgres・react・fastapi・typescript、decisions は D1・D2・D3 (confirmed)、knowledge_candidates に k8s-workload-observability (deepened) があります。qa_log の利用者発言は、どれも orchestrator がシナリオ上の利用者の発言として書いたもので、実利用者との対話ではありません (各 entry の provenance に書いてあります)。
- 上の state には、今回の準備で `qa-foundation-u1`〜`u9` の 9 件を正規 writer の `chunk` で追記してあります。前回の試験の後に、上位概念 U1〜U9 の根拠を `qa-foundation-u<N>` の索引で示す契約が足されたためです。各 entry の answer は、appr-foundation-v2 の対応表でその U の根拠とされたシナリオ上の利用者発言を、逐語のまま連結したものです (新しい内容は足していません。経緯は各 entry の provenance にあります。provenance の日付 2026-10-30 は、この追記の内容を最初に組み立てた日です)。追記の副作用として、`hearing_progress.loop_count` が数え直されています。
- `system-spec/fetched-references.json` と `retrieval-evidence/`: 前の実走で正規doc-fetchが取得し、公式hostとdigestへ接地した資料。その実走で正規writerが更新したspec-stateと共に、今回はそのまま再開入力にした。取得日時・採用版・方針は入力の記録を確認し、doc-fetchの要否は正規Skillで判断すること。compiled章は今回の再開入力として複製済みだが、評価report・監査台帳・graphのnode・resume receiptは種として置いていない。前の実走はFAILであり、その評価結果を今回の証拠に転用しない。fixture-provenance.json参照。

これらは試験の入力 (seed) で、取込の成果や evaluator の PASS の証拠ではありません。**fixture の入力を準備のために書き換えないこと。** 入力を変えるのは、skill の正規経路の writer だけです。

### 準備済みの再開入力

- このrepoはC01の正規builderで初期化済み（workdir/fixture-init-receipt.json）。graph.nodesは空で、取込結果は無い。C01のSkillを実行するタスクではない。
- system-spec/には前の正規writerが作ったcompiled章もある。これらは再開入力であり、今回のcompile実行・evaluator・登録の成果として代用しない。C19の正規経路で再compile・新規独立評価を行う。
- candidate-import.jsonは前の実走のC02入力を基にした草案。confirmation_evidenceとimported_atは削除済みで、承認/確定根拠ではない。必要ならschema/sectionsの入力草案として参照できるが、今回のsource bytes/version/digestと新しいevaluator証拠へ正規に接地させてから使う。
- fixture-provenanceは `/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec96/workdir/fixture-provenance.json`。fixture入力を探すために / 全体を走査する必要はない。

### 本題

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec96/fx --resume"})

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

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **成果物を生成する自作スクリプトを書かないこと。** driver / build / guard の類を自分で実装して成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- spec-state・fetched-references・compile の成果は system-spec-harness の正規 writer で、graph と content は C02 単一 writer (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) で作ること。直接の file write や手書き JSON の組み立てで代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。読まずに出力 shape を発明しないこと。
- SKILL.md が要求する独立 Agent (verifier・evaluator・auditor) は Agent tool で実際に別 context として起動すること。自分で書いた検査コードによる自己判定や、手書きの evaluator PASS で代替しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。

foundation と各セルの承認内容は、fixture の qa_log と approval_log に明示済みです。ほかに意思決定が要るなら、承認を勝手に作らず FAIL にしてください。

配置の注記: この session は fixture の root (`/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec96/fx`) を cwd として起動しています。plugin は同じ root の `plugins/` にある写しを `--plugin-dir` で読み込んでいます (`plugins/` と `.claude/` は fixture の `.git/info/exclude` で git の追跡外にしてあります)。

ネットワークの注記: 後半の「隔離環境の注記」にある「外部ネットワークは遮断」には、この run に限り例外が 1 つあります。WebFetch による上の 5 host への https の読み取り (GET) だけは許可されています。それ以外 (ほかの host・WebSearch・Bash のネットワーク CLI) は遮断のままです。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec96/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage-r2"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec96` の内側だけが許可され、外部ネットワークは遮断、gh と既定の bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。

契約履行の確認: 責務prompt全文を成果作成前にReadし、必須の型のAgentを実際に起動する。goal_seekのgoal-spec/progress/intermediateとartifact_deliveryのstandard選択記録をfixture内eval-logへ保存する。契約を省略したらFAILとする。
scenario required_observations（正本の逐語）:
1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

今回の入力の補足（試行開始前の準備）:
- 基礎の承認・質問/回答・採択は既存の合成入力どおり。利用者の新たな承認を作らない。前の実走の正規writerでqa単位の設計解釈とD1の採用PostgreSQL16の出典整合まで済んだstateを再開入力とし、元のfixture問答と採用判断は変えていない。
- 全責務promptとC19のgoal-seek配線を読み、親と責務Agentのログ所有権・6必須キー検査を含む契約を実行する。条件を満たさなければFAILで、手順を省略してPASSにしない。








実行前の契約確認:
- 現行C19のPurpose/Output/R0-R3/goal-seek配線と呼ぶ4 Skill/責務promptを全文読む。固定C24 root、親/責務Agentのログ所有権、goal周回と責務切替、本処理と隔離unitの境界に従う。
- 毎周回、coverage/source-citation/schemaの3 CLIを実測してからIN1を記録する。空graphでもschemaを省略しない。全exit0の後だけPASS、未実施/待ちはnot_achieved。その後にintermediate6キーと元goal/hashを検査。後周回成功の遡及は禁止。
- compile CLIのBash末尾で現物path/digestと「開き方: less <絶対repo-root>/system-spec/index.md」をstdoutへ出す。この呼出しにchoice/test/Agentを混ぜない。提示より後の別呼出しでcompile-standard.jsonへchoice=standard/path/digest/open_withを記録してからOUT1 63 tests/評価Agentを実行する。
- 各run Skillで最小成果物を提示した直後に事前回答standardを記録する。新周回の操作より前に直前のmerged_directive_for_nextを入力し、責務Agentへ固定receipt/元goal/hash/担当prompt/周回指示を渡す。
- C05の起動直前に、次の環境と保存契約を会話で共有してからhelper出力そのままのSkill argsで呼ぶ。C05/R2-delegate 2.4とR1-score 4.3のとおり、評価/監査JSONの保存は「python3 -c 'import pathlib,sys; pathlib.Path("<保存先の絶対パスをリテラルで直接記す>").write_text(sys.stdin.read(), encoding="utf-8")' <<'JSON'」の形を使い、引用heredocの本文には妥当なJSONだけを渡す。出力先をp等の変数へ入れてp.write_textする形はconfirmed-chapter guardが静的に解決できないので使わない。C05のallowed-toolsにないWriteやcatリダイレクトを要求しない。必要なJSON組立はread-only Pythonのstdoutで行い、正規C05自身の判断と実fork結果を無改変で保存する。C06出力も正規writerが同じliteral保存形で扱う。
- このrunはSHELL=/bin/zsh、TMPPREFIXを許可run/tmp内へ固定した環境で、長い引用heredocの保存を検証済み。sourceの保存方式をprintf等へ変える必要はない。外側の隔離guardは「許可eval-logのliteral Pathへstdinを無改変で保存するPython」かつ「引用heredocがJSON」のデータ本文だけをmacOS CLI文字列探索から除外する版で、実コマンド・外部接続・書込rootの制約は維持される。guard/settings/sandbox/ソースを被験側で変更しない。
- sourceが明示する正常な回復を禁止しない。confirmed-chapter guardが保存先不明のreport書込を拒否した場合は、R1-score 4.3が指示するとおりspec_dir/outputを変えず保存先をliteralへして再試行できる。保護仕様章やspec-stateの書換・外部サービス接続・別repoへの逃避を実行してはならない。隔離guardが拒否した外部effectを別tool経由で実行しない。任意のreadonly診断が拒否されたら同じraw pathの探索をやめ、正規Agent応答/監査台帳/TaskOutput等の提供済み証拠で確認する。
- 検証用scratchは事前許可の絶対pathだけ。caller取込元はread-only、scratch成果をC05 snapshot/C02取込元へ流用しない。各Skillが明示する個別test以外の大規模unit回帰は外側914PASSで確認済みだが、これを今回flow実行の証拠へ代用しない。
- qa-008入力は前runで原初schema1.0 fixtureから正規writerにより補完し直したもの。元問答/承認/採択は不変、未確認RTO/RPOへの言及はない。今回も再compile・新しい独立評価・正規C02登録を実証し、seedのcompiled章や過去PASSを行動証拠へ代用しない。
