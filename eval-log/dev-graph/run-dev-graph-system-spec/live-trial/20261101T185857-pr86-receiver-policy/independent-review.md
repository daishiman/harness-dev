# sysspec114 独立受入評価

判定: **FAIL（受入ゴール未達、設定伝達不成立で途中中断）**。点数は付けない。これはC05・C06・C08が最終FAILを返したとの判定ではない。

## 評価対象と証拠の範囲

C19 `run-dev-graph-system-spec` の正本SKILL SHA `10b54fd1e3070f57a8a02de2a31fb93a57940e15ab108e6df96947836812f049`、挙動閉包 `ebec0c4771f30cd2be8260f9871ad0e4d42112e7f03ebed8c04a0326bf13a5ef`、公開system-spec-harness 0.1.24、正本scenario `C19-OUT1-positive-system-spec-lineage-r2` を基準にした。準備時にsource契約を確認後、今回のfrozen raw・公開transcript・observer・fixture snapshotだけで評価した。過去trialのtranscript/verdict/independent reviewは参照していない。source/fixtureは変更していない。

元goalは「仕様書・アーキテクチャをplugins/system-spec-harness/の正規フローで構築し、出典・確定状態・上位目的traceを保ったままdev-graphのspecification/architectureノードへ取り込んだ状態になっている」。起動・compile完了だけをgoal達成へ読み替えない。

## 元の3観測とIN1/OUT1

| 対象 | 判定 | 一次記録から言えること |
|---|---|---|
| 1. the declared system-spec-harness plugin is loaded and its canonical flow completes | 未達 | C19、elicit resume、compile、C05を本物のSkillで起動。版0.1.24と4entrypoint、正規compiler実行は確認できる。C05は中断時点で未完了で、canonical flow全体は閉じていない。doc-fetch未起動は必要時のみという契約に沿う判断が記録され、全5targetの形式ゲートexit0。ただしC08による内容鮮度の再照合は未実施。 |
| 2. the imported specification and architecture retain source lineage and evaluator evidence | 未達 | 最終graphはrevision0・nodes=[]。新規取込node、confirmation/evaluator evidence、C02 receiptがない。seedのcompiled章・candidate-importを取込成果に数えない。 |
| 3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph | 未達（正の取込証拠なし） | C02 Skill/登録は未実行。直接graph writeやdev-graph内の代替compiler生成は観測されないが、登録0件の真空充足を正の受入PASSにしない。R1検証は複製0件を返しており、同等ロジックの新設も記録上ない。 |
| IN1 | 周回1の3機械ゲートのみPASS、最終判定は未完了 | `main-toolu_01TJTV5SHU4PuDzgY5TCmWz7.json`にcoverage(require-complete/basis/foundation)・source-citation(--state含む)・graph-schema(strict readiness)の各実出力とexit0。これらの後にprogressのIN1 PASSとintermediateを記録。C05内のmatrix/source/knowledge gatesも実行exit0だが、evaluator PASSの代用にはならない。周回2は途中で、R2/R3後の最終IN1を達成したことにはならない。 |
| OUT1 | 未達 | 正規Skill起動・正規compileの部分証拠はあるが、評価済み確定成果のC02取込まで到達していない。progressもOUT1=external_pending、残り4checklist=not_achievedのままであり、自己PASSは記録されていない。 |

## 実行の到達点

- R0/R1の独立verifierが実在し、担当prompt・共通層・project CLAUDE.mdを明示Readした。C24 receiptはcaller fixtureを指し、lineage gate checked=0から新規取込と判断した。
- 親は委譲先4SKILLのfrontmatter込みReadを実施し、elicit/compile責務promptを取得。elicitは未収集0の再開入力を正規validatorで検査し、状態を書き換えず完了と判断した。
- 正規compilerは10 Markdownを再生成してexit0。path/digest/開き方を実stdoutで提示した後、別呼出しでstandardを保存し、63受入テストのPASSを取得。compiled章がseedと同digestであることは、今回のwriter呼出しの実在を否定しないが、seedだけでは実行証拠にならない。
- helperは固定receiptを検証して絶対spec_dir/outputを返し、そのskill_argsがC05 Skill引数と一致する。C05はcontext:forkの別streamで実行された。
- C05 Step0のproduction snapshotは12入力を束縛し、最終snapshotとも一致する。R1/R2責務promptは大出力persisted fileを追加Readして取得している。aspect-criteriaは先頭150/165行、rubricは先頭5000文字の取得に留まり、resource-map/schema/全18prompt/全Markdownの完了した意味評価は確認できない。中断時点の未完了範囲として扱い、これだけを根拠に最終FAIL応答を創作しない。
- C07のdispatch(schema1.2 pending)とcompletion(schema1.3 resolved/PASS)が同tokenで揃う。C06はdispatch pendingのみ。C08は未起動。C05レポート・hearing-audit保存・aggregate --report・R2/R3 verifier・C02は未到達。

## 設定伝達と既観測の契約逸脱

`project-instructions.md`とprovenanceは既存sourceの読込/保存/意味評価契約を各forkへ渡す意図のもので、期待PASSや新しい点数は含まない。しかしrunnerの`--setting-sources local`に対するCLI probeはLOCAL markerだけを返し、project markerを返していない。親/R0/R1の明示Readは原本で裏付く一方、C05の初期Skill本文注入にはproject policyが含まれず、CLAUDE.mdを取得するtoolもない。したがって「親が読んだ」ことを「各forkへ自動伝達できた」証拠に使わない。設定伝達不成立を理由に止めた判断は、abort-reasonと実際の未完了状態に整合する。

中断とは別に、次の実測済み逸脱がある。

1. **C05の保存・探索境界**: `toolu_01RLccNnPorfZiXSJz5Xanv8`でsnapshotを`$TMPDIR/snapshot.json`へ、`toolu_01EhJZJi1KrGT4T6q7uB1RBv`で3gateを`$TMPDIR/g-*.json`へshell redirect保存。公開R1-score 4.3が許すhearing-auditと引数outputのliteral保存以外の書込みである。`toolu_01Dwk5ZrVktVXk6SJPy36fZJ`は`find /`を実行し、fixture外の多数のpathを返した。後でTaskStopしたが、探索実行自体は記録に残る。別のglobal home探索はguardに拒否されている。外部pathの値はレビューへ転載しない。
2. **C07の必読SSOT**: 起動promptはR7への参照だけで本文ではない。C07 streamはcoverage両モード、stateのReadとPythonによる一部補足走査だけで終了し、R7の取得がないままPASSを返した。Agent実在・token joinの機械接地と、監査の意味契約を満たしたことは別であり、このPASSは契約履行済みの監査証拠に採用できない。
3. **C19のアンカーenum**: 周回1の親intermediateは6必須キーとoriginal_goal/hashを保持し、hash検査も成功。しかし`drift_signal=none`はgoal-seek正本enumにない。C19本文の6キー/hash検査だけではこの逸脱を拾っていない。

これらは実際に行われた操作への所見であり、未完了C05の最終verdictを推定したものではない。C06の未完了検査、C08未起動、最終レポート欠落は中断による未完了として分ける。

## 一次記録の完全性

独立parserでfrozen原本JSONLのUUIDを重複排除し、各実tool/resultとsource行・prefix bytes/SHA256を照合した。observer実装のextract関数は実行していない。

- observer108件=tool_call105（Bash60・Read41・Skill4）+正規metadataで束縛されたSkill本文注入3。全件が原本と一致、対象primitiveの欠落/余分0。observer自己I/Oは宣言どおり除外した。
- Agent/Write/ToolSearch/TaskStopはobserver対象外であり原本を直接確認した。C06の最後のBashには原本時点でtool_resultがなく、observerにないことは正しい。scope外のabsenceを未実施の根拠にしていない。
- raw→公開で内容が変わった共通ファイルは申告6transcriptとpoll-stateだけ。6transcriptはいずれもoriginal/redacted SHA・原本byte数・行数が宣言と一致し、JSON形状を保持。変更scalarはuserEmailと対応rendered/textの匿名化位置。その他の共通ファイルは同一。個人情報の原文は成果物へ転載しない。
- pollは原本elapsed672を`ceil(observed_at_unix-start.epoch)=673`へ変更しただけで、他field不変。正確な差は672.4345779418945秒。scenario上限3300秒/23000000tokensの変更や延長はない。これは最後のpoll観測時刻であり、reapまでの全経過秒と混同しない。原本main/subagentのassistant.message.idを横断重複排除し最初の有効usageを合算したtokenは7,688,583（96message、usage欠落0、ID欠落0）で、23,000,000未満。
- C05 production snapshotの12path/digestは最終treeの実bytesと全一致。最終manifest57件もpath/size/SHA256が全一致。最終graph nodes0、status markerなし、progress in_progressがpartialという収集説明に一致する。
- bootのrun-id sysspec114・owner85266と、既実施のscoped reap記録がある。評価者は追加kill/reapを実行していない。

再構成の明細は`pr86-sysspec114-observer-reconstruction.json`、機械読取の独立受入判定は`pr86-sysspec114-eval.json`。完走していないため、最終化ではcompletion FAIL/ABORTEDという観測事実を保持し、成功受入やC05の最終評価に読み替えない。
