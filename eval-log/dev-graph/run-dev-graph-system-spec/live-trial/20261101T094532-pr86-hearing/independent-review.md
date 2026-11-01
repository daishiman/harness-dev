# sysspec102 独立 goal 評価

判定: **FAIL**。blocker は C07 の役割固有ツール契約違反1件。点数評価は行わない。

対象 D: `/Users/dm/orca/workspaces/harness/pr86-ci-fix/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261101T094532-pr86-hearing`。評価者 `/root/review_sysspec102`。公開親 transcript SHA-256: `f181f077c8563a368713e23779441449bbb1abc3017607ec747c3c13e885f545`。以下の行番号は公開 JSONL の物理行番号。重複表示された同一 tool_use_id は1回に正規化して実呼出しを照合した。

## 判定を決める一次証拠

C07 の役割固有ツール契約違反。transcript/subagents/agent-ab804216afad12a2d.jsonl の L32 で `grep -rl "missing_effect" . | head`、L36 で独自 Python による required-info-catalog.json 抽出と `ls`、L40 で独自 Python による item 集計を実行している。正規 C12 の loop/--require-complete だけに Bash を限定する C05 SKILL/R2-delegate、C07 R7 Layer 3.2/4.3、および実起動 prompt に反する。L14 の必読 R7 読込と L19 の正規二モード成功後に実行されており、道具宣言検索や単なる未遂ではない。したがって正規フロー完了を要する scenario 観測1と C19 OUT1 の受入を満たさない。

C07の実起動入力は C05 transcript `agent-a7c15c26886a8353a.jsonl:L53`。そこでも「Bashは正規二モードだけ」「独自PythonのJSON抽出・集計を足さない」と明示。C07は `agent-ab804216afad12a2d.jsonl:L14` で R7 を全文Readし、L19で両モードを成功させた後、L32/L36/L40で境界を越えた。呼出しはいずれも実行成功のtool_resultを持つ。広いnative tool poolやread-onlyという属性は責務の実行範囲を広げない。違反後のC07 PASS、C05 aggregate PASS、native status PASSは違反を消さない。

## feedback criteria の対応

### IN1

C19 feedback_contract.criteria IN1 正本「system-spec-harnessのcoverage/source citation gateとdev-graph schema gateがすべてexit0になる」に対応。親 transcript.jsonl L357 で初周回の coverage(--require-complete --require-basis --require-foundation)・source-citation(--targets/--references/--state/--repo-root)・graph-schema(--strict-artifact-readiness、空graph) を実行し cov=0/cit=0/sch=0、その後 L361 で loop1 IN1 PASS と6必須キー行を保存し hashcheck=0。第2周回は L631 の同3CLIおよび lineage gate が全0、L686/L688 の最終集約で3CLIを再実行し全0を assert してから loop2 IN1 PASS と6キーを記録、hashcheck=0。goal の原文/hash は全2行で一致し、progress の OUT1 は external_pending を維持した。IN1 の機械条件は実測で充足している。

### OUT1

C19 feedback_contract.criteria OUT1 正本「仕様書/architecture要求がsystem-spec-harness成果物をsource lineage付きで引用し、同等ヒアリング/compileロジックがdev-graph内に複製されていないことを受入テストが確認する」に対応。4正規Skill入口、今回の正規再compile、C05真fork・3監査の実completion/receipt・最終aggregate exit0、C02 build-graph-node.py add による唯一の登録、specification/architecture各1件の confirmed/pass/readiness complete と原本bytes=source_digest=evaluated_digest を確認した。dev-graph にヒアリング/compile生成器の代替実装・source改変は観測されず、scratch Python はpayload/評価ログの組立である。ただし独立C07が二モード専用Bash契約を実際に越境しており、その監査PASSを集約した正規フロー完了の主張を受理できない。成果物の成立だけでこの違反を解消しないため OUT1/goal の受入は FAIL。

## 実フロー・独立性

- 親 L40 に C19 Skill、L131 に elicit、L214 に doc-fetch、L253 に compile、L391 に C05 Skill がある。nativeの再掲行を別起動に数えていない。doc-fetchは4/4既存参照、missing/discovered=0を判定して取得を省略し、C08が今回の現行性を再照合した。
- L278はcanonical compile-spec-doc.py compileを実行しexit0、10 Markdown生成。seedとbyte同一なのは同一入力による決定論再生成であり、今回実行の代わりに過去compileを使ったとは扱わない。L286のstandard記録前に同CLI末尾でpath/digest/開き方を表示し、その後に63件のcompile受入testを隔離scratchで実行した。最初のtest path誤りは次呼出しで修正されている。scratch試験をC05/C02の本処理へ代用していない。
- C19はpreflight実体とdigestを示した後L104でstandard記録、以後にR0/R1独立検証を起動。elicitはresume gateのみで入力不変、doc-fetchは不要判定、compileは上記提示後に評価へ進む。C02もdry-run提示後にstandardを記録して実writerへ進む。
- C05はnative fork markerと別JSONLがあり、R1/R2を最初にRead。最初のsnapshot CLIでshell変数展開の失敗があるがL37で絶対pathに修正してexit0、監査前に固定した。
- C07 dispatch 00:53:48→completion 00:54:33、C06 00:55:04→00:55:57、C08 00:56:30→00:56:56。3件は実completionを待った直列呼出し。ledger schema1.2/1.3の接合後resolved、response digest/verdict/session/tool_use_idとreport receiptが一致。台帳の手書きは観測されない。
- C05 L247はliteral Path.write_text(sys.stdin.read())と引用heredocによる指定report保存、その同じBashでcanonical aggregate --report/--spec-dir/--sessionを実行しexit0。R2 verifierも再実行してexit0。最終集約欠落ではない。

## C06 / C08 / C05 の役割固有検証

C06 は5回の実Readのみ。R6・中立基準を全文読込し、独立5軸意味監査を返した。書面QAは0件だがC05 L43で正規validate-hearing-sources.pyを実行し、無改変JSONをL124の起動promptへ渡した。state_sha256はsnapshotと一致。L182再実行JSONは全体一致し、source_verificationのokを意味判定に置換していない。

C05のToolSearch(select:Monitor)は宣言検索1件でMonitor実作業は無い。C05にcat/grep/find/tee/Write/Edit/TaskStop/TaskOutputの実呼出しは無く、readonly Pythonや評価JSONのliteral/stdin保存を一律違反扱いしていない。C08はR4と公式catalogをReadし、正規C13と4公式hostへの実WebFetchで二層監査を行った。

C06の応答は48セル、48QA、canonical U1〜U9と承認、supersession(a)(b)(c)とactive consumerを独立に意味照合し、medium/注記/閉じた検出を返す。C05はhearing-audit.jsonへJSON部分を無改変保存し、canonical --hearingで補助判定を再導出。単なる「CLI ok」からの意味PASSではない。

C08は `agent-a18670fda0d67cd81.jsonl:L14/L16` でR4とcatalogを各全文Read、L23で正規C13 exit0、L33〜36でPostgreSQL/React/FastAPI/TypeScript公式URLをWebFetchした。実WebSearchはなく、taskの許可host内で裏取りした。FastAPI本文取得範囲の制限は注記に残っている。

C05のread-only Pythonは、正規gate結果取得、snapshot/hash照合、章の意味判断に使う入力抽出、schema/ledger検査として実行される。C05が意味監査を自作evaluatorへ置換した証拠は無い。明確な拒否対象C07の3コマンドを、C05の許可されたPython全体へ一般化しない。

## C24 / C02 / graph

親はC02 Skill前のL449/451/453/455/457でR0〜R4を各全文Read。C05 PASS前のC02 payload/Skillは無く、dry-run/addのinput_sha256は同一。C02唯一writerのreceiptはrevision0→1、2node。R0/R1/R2/R3の独立VerifierとC02 integrity auditorは実起動・完了している。

C24開始receipt SHAは `e1972b54f97b340976072c5d20d0b281f54919594de82344a862275c22cc6bc4`。repo_root=content_roots.repository、lineage checked0で新規取込と判定。生成Bashは固定rootをexport/cd/pwd照合し、C05直前のhelper成功outputのskill_argsをそのまま渡している。

source原本のindex digest `f7f6476735e6ed5e07b2583a7d628b8cfd89227235c5745f3ae10681b8d545e2`、requirements digest `1cc7fe6bd148679b1bb2450fbc61c8dfad42ae7edbcee6bd0463711c3ffa1402` は各nodeのsource_digest/evaluated_digest/report snapshotと一致。2nodeはconfirmed/pass/readiness complete。C02 receipt input digestは `fa7527976dbc00b555c5444698810bae70b68da32b2e731218731eb109d2ca96`、graph canonical digestは `sha256:df368b69396a4f2e3df8cdad5ef2473e8da05db850e5f5f774b9b3b85e015f8f`。最終graphとreceipt双方で一致し、writer後の別graph更新は無い。

R0/R1/R2/R3 verifierの実completion、C02 R3-writeのcanonical add、専門integrity auditorの実completionがある。R0/R1で「=====」をechoした箇所がzshのevalエラーになっているが、それ以前のprompt全文はstdoutへ出ており、後続で共通層/receiptの参照を回復している。未読や監査未完了へ短絡しない。

## guard拒否と回復

guard拒否は親L569の読取graphとeval-log payload保存を同居させたコマンド、R2 verifier L42の未知保存先を含むeval-log判定保存の2件。回復したscratchの実保存先はpayloadまたはverificationでありgraph/state/章を直接書かない。正規C02だけがgraphを更新した。source/settings/guardの被験側改変や外部effect拒否の迂回は観測していない。

親L569はgraphのrevisionを**読む**処理とeval-log payload保存を同じinline Pythonに含め、graph guardが書込として拒否した。L581のscratchでは期待revision=0を既観測値で固定し、payloadだけ保存、L583で実行した。その後のgraph変更はC02 canonical CLIのみ。R2 verifier L42の拒否も実際の保存対象は責務dirのverification.jsonで、L46/L53のscratchへ同じ検証JSON保存を移した。C05にはこのscratch保存回復を転用せず、正規literal/stdin契約で保存した。保護対象を実際に直接書く拒否を、別toolで実行した事例ではない。

## 証拠保全・入力不変・権限

evidence-redaction.jsonの11filesの原本SHA/公開SHA/原本size/行数を検証し、同一の24→19文字置換40回だけを確認した。fx-final manifest・seed・snapshot・lineage bytesは匿名化対象外で一致する。

公開poll-stateはrawのelapsed1374から1375へ収集時に切上げ。poll-normalization.jsonのraw/public SHA・唯一のfield差・ceil(1374.6130418777466)を照合した。上限変更は無く、この正規化を被験側改ざんに数えない。

validate-hearing-sources.pyの実走copyは0644、Wは0755、本文は同一。観測argvはpython3/親ではpython3 -Bで読み込むため実行bit差は今回のCLI呼出しを妨げていない。package検査上のmode問題と実走挙動を区別した。

原本fx-final/treeの全seed_sha256を再照合し差分0、C05 snapshot 12artifactも差分0。公開manifest掲載ファイルと原本のsource lineageを照合した。source/settingsの被験側Write/Editは無く、Writeの実宛先は許可scratchのpayload/ログ組立scriptだけ。隔離guard 171件はallowだが、これはplugin自身の拒否2件を否定しない。plugin拒否は上記tool_resultで確認した。

この評価で読むsourceはlaunch時固定copy（SS0.1.25/DG0.1.26、closure24bf8a09…）に限定し、その後の設計変更を102の契約へ遡及適用しない。
