開始時にrepo rootのCLAUDE.local.mdをReadし、各独立Agent/Skillが同じ既存契約を受信することを守る。今回は通常project指示で既存契約を伝達する。source/入力v7/判定/予算/権限はboot後不変。
実走前の既存R2境界（入力と判定基準はそのまま）: 委譲出力を一つも作る前に、親自身が plugins/system-spec-harness/skills/run-system-spec-elicit/SKILL.md、run-system-spec-doc-fetch/SKILL.md、run-system-spec-compile/SKILL.md、assign-system-spec-completeness-evaluator/SKILL.md をそれぞれRead toolで1行目から最終行まで取得する。Skillツールの本文注入にはYAML frontmatterが含まれない場合があるため、Skill起動だけを全文Read済みと数えない。Readのoffsetを本文以降に設定せず、frontmatterも含め、tool応答が切れたら不足範囲を追加Readする。担当prompt/SSOTの必読も通常どおり守る。
今回の合成入力v7はtrace-correction-provenance.jsonの正規再開/書面source-indexで再接地した入力。Kubernetes含む5targetsとD1-D4を保持し、現在の評価/PASS/監査台帳/graphはseedしていない。
失敗で停止した場合も、最後にout/status.jsonへ実際のFAILとblockersだけを完了マーカーとして保存し、DONE: FAILと報告する。これは失敗を成功へ変える指示ではない。

# タスク: dev-graph:run-dev-graph-system-spec の実走 (C19・現行の出典で取り込む)

### 入力 (準備済み)

fixture repo-root (以下 `<FX>`) は
`/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec122/fx`
です。git init した repo で、空の commit ("isolated current-source input") が 1 つあるだけです。dev-graph は正規builderで初期化済み、graph.nodesは空です。入力は未追跡の `system-spec/` のstate・出典資料・compiled章です。

- `system-spec/spec-state.json`: 正規writerで構成した新規合成given v7。旧50QAの本文/basis/source/answered_atは保持し、qa-037/038へは正規supersession metadataだけを追加。auth/webとsecurity/webをreopenし、提供書面の新4QAへconfirmして根拠を再接地した。foundation/appr-foundation-v2、D1-D4の採択・値、5targetsは保持する。旧basis変更を正当な利用者入力と主張しない。
- 上の state には、今回の準備で `qa-foundation-u1`〜`u9` の 9 件を正規 writer の `chunk` で追記してあります。前回の試験の後に、上位概念 U1〜U9 の根拠を `qa-foundation-u<N>` の索引で示す契約が足されたためです。各 entry の answer は、appr-foundation-v2 の対応表でその U の根拠とされたシナリオ上の利用者発言を、逐語のまま連結したものです (新しい内容は足していません。経緯は各 entry の provenance にあります。provenance の日付 2026-10-30 は、この追記の内容を最初に組み立てた日です)。追記の副作用として、`hearing_progress.loop_count` が数え直されています。
- `system-spec/fetched-references.json` と `retrieval-evidence/`: 前の実走で正規doc-fetchが取得し、公式hostとdigestへ接地した資料。その実走で正規writerが更新したspec-stateと共に、今回はそのまま再開入力にした。取得日時・採用版・方針は入力の記録を確認し、doc-fetchの要否は正規Skillで判断すること。compiled章は今回の再開入力として複製済みだが、評価report・監査台帳・graphのnode・resume receiptは種として置いていない。前の実走はFAILであり、その評価結果を今回の証拠に転用しない。fixture-provenance.json参照。

これらは試験の入力 (seed) で、取込の成果や evaluator の PASS の証拠ではありません。**fixture の入力を準備のために書き換えないこと。** 入力を変えるのは、skill の正規経路の writer だけです。

### 準備済みの再開入力

- このrepoはC01の正規builderで初期化済み（workdir/fixture-init-receipt.json）。graph.nodesは空で、取込結果は無い。C01のSkillを実行するタスクではない。
- system-spec/には前の正規writerが作ったcompiled章もある。これらは再開入力であり、今回のcompile実行・evaluator・登録の成果として代用しない。C19の正規経路で再compile・新規独立評価を行う。
- candidate-import.jsonは前の実走のC02入力を基にした草案。confirmation_evidenceとimported_atは削除済みで、承認/確定根拠ではない。必要ならschema/sectionsの入力草案として参照できるが、今回のsource bytes/version/digestと新しいevaluator証拠へ正規に接地させてから使う。
- fixture-provenanceは `/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec122/workdir/fixture-provenance.json`。fixture入力を探すために / 全体を走査する必要はない。

### 本題

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec122/fx --resume"})

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

配置の注記: この session は fixture の root (`/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec122/fx`) を cwd として起動しています。plugin は同じ root の `plugins/` にある写しを `--plugin-dir` で読み込んでいます (`plugins/` と `.claude/` は fixture の `.git/info/exclude` で git の追跡外にしてあります)。

ネットワークの注記: 後半の「隔離環境の注記」にある「外部ネットワークは遮断」には、この run に限り例外が 1 つあります。WebFetch による上の 5 host への https の読み取り (GET) だけは許可されています。それ以外 (ほかの host・WebSearch・Bash のネットワーク CLI) は遮断のままです。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec122/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage-r2"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec122` の内側だけが許可され、外部ネットワークは遮断、gh と既定の bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。

契約履行の確認: 責務prompt全文を成果作成前にReadし、必須の型のAgentを実際に起動する。goal_seekのgoal-spec/progress/intermediateとartifact_deliveryのstandard選択記録をfixture内eval-logへ保存する。契約を省略したらFAILとする。
scenario required_observations（正本の逐語）:
1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph


追加のrunner契約はCLAUDE.local.mdに集約した。正本sourceの必読/意味評価/3観測/各周回IN1/6キー/hash/独立性/単一writer/lineageは変更しない。書面Read前の検査はtrusted hookで同actorに強制する。sourceで必須でない一般再監査や全validator実装の一律Readを増やさず、同じ3300秒/23Mtoken内で担当scopeを実行する。
