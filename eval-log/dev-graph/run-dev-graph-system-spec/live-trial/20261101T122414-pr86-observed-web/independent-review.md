# sysspec106 独立 goal 検証

判定: **FAIL**。点数は付けない。完走、C05 report の機械的 PASS、2 node の登録だけでは正規フローの達成証明にならない。

評価者 `/root/review_sysspec106` は完走通知前に106/過去実走のrawを読まず、指定source/scenarioだけを準備した。評価開始後は今回のfrozen原本を一次情報とした。W/source、入力、guard、設定、公開証跡は変更していない。出力は `/tmp/pr86-sysspec106-*` のみ。

## 確定したBlocker

B1: C19 R2-delegate 5.3第3項の毎Bash固定root契約が未達。main transcript line191/237/282/290/304（toolu_01XRu1weQJVPAzrGAh3XWrZS / 01XNqENHLW17qvvaeJAz1kJ9 / 01VNue35HGRcFovNe6Z6rF3X / 01HZuDUJFkKge4UWX1km2Yjc / 01QyesRcPfTrTvKEFpANgNyg）はelicit・doc-fetch・compileの提示/記録/検査を行うBashだが、各呼出しで固定receipt由来のCLAUDE_PROJECT_DIR exportがない。実compile等の取込元生成は正しい前置きで行われたため、root外生成が起きたという判定ではない。

B2: C05最終PASS前のdoc_verification全JSON再取得・一致確認が未達。C05 transcript line145 / toolu_011MRa3FtqZ3oaoYYkBfcxGF は初回のrepo_root・inputs各path/sha256・validator_path/sha256・argv・exit/stdout/stderrを持つ完全形を再構築せず、{refs,state,val,exit_code,stdout,stderr}へ縮約したDOC_SAME=Trueで代替した。C05 SMD99、R1/R2、doc-fetch R4 Layer3とtask132に反する。入力不変や機械exit0はこの実行義務を代替しない。

B3: 正式C02のpost-choice未達responsibilityのAgent forkが欠落。run-dev-graph-node SMD176/182は各周回の責務実行をforkへ出すが、main line623でstandardを記録し、line632で全checklist pendingを作成して同じmain Bashでcanonical addを実行している。C02担当の責務Agentは実際には0件。post-addのdev-graph-integrity-auditorとC19 R3 verifierは実行されたが、C02責務実行forkの代替ではない。

B1の範囲は、R2 checklistが「手順にあるBashの呼出しで毎回export」と明記した範囲である。絶対パスの補助ログを安全に書けたことと、この呼出しごとの契約を守ったことは別である。取込元を生成したcompile本体 `toolu_0148MRmwZzhLHs6NDCxgAr4o` は正しいexport/cd/pwd照合を行っている。scratch pytestはsession専用scratchを使い63件成功しているが、正規compileや独立監査の代替には数えていない。

B2では初回C13と最終C13の実argvは同じで、再取得した値の実差分を検出したわけではない。要求は完全形を再取得して全項目照合することなので、入力digestと一部結果の一致だけを根拠にPASSへ進めた実行上の欠落である。初回と同じ完全shapeを保持・再構築して比較する必要がある。C05は最終応答で「完全一致」と述べているが、実commandが示す範囲を優先した。

B3では正式C02の単一writerそのものは実行されている。欠落しているのはpost-choiceの責務実行を分離contextへ出す契約である。native Agent全8件はC19 R0/R1/R2/R3、C05内C07/C06/C08、C02 integrityの内訳で、C02未達responsibility用forkは含まれない。C02のintegrity verifierは型・実完了・graph digestを満たしているので、これを未実施とは報告しない。

## 提示に関する追加観測（証拠不足・適用範囲の疑義）

複数run Skillのartifact_presentedが実提示に接地していない。C19 main line125は開き方をartifact-delivery JSONへ書く一方stdoutはgoal hashのみ。elicit line191はpath/digestのみで開き方なし、doc-fetch line237は提示/choiceの同時記録後にokのみ、C02 line623もpath/digest/開き方を提示せず同一script内でartifact_presentedとstandardを記録する。各SMDのpre-choice契約「現物path・digest・開き方を提示してから」への独立した到達証拠は十分ではない。compileはline282の実path/digest/開き方出力後、別call line290でstandard記録があり、この不足には含めない。

ここはB1–B3と区別する。提示eventの宣言だけを独立した提示の証明にはできない一方、現物とopen_withを含む永続ログ自体を「提示」として認めるかについて、sourceは別の独立したnative提示primitiveを要求していない。したがってこの提示方法を追加の確定違反としてJSONのblockerには数えない。提示の十分性は未証明として残し、次回はpath/digest/開き方の実出力と別callの選択記録で曖昧さをなくす。C02でdry-runを最小成果物として扱ったこと自体の是非も追加のblockerにはしていない。

## 報告済みcatの適用範囲

main line644、`toolu_01GQoKoMr5B5WMtawNMPzEYf` は `cat <実在するR3-import.md> > /dev/null; echo ok` である。task133の禁則は「対話待ちを作る `cat > /dev/null` 等」であり、実コマンドは入力ファイルが指定されていてstdin待ちにならない。R3 promptも先に全文取得されている。このコマンドを独立した不合格理由にはしない。C05のshell調査禁止を親C19へ誤って広げることもしない。無用な捨て読みなので次回は省くのがよいが、今回のFAILは上記blockerへ接地する。

## 実施を確認できた契約

- C19、elicit、doc-fetch、compile、C05、C02の正規Skill呼出し6件をnative成功結果で確認。C05は実際にforkされ、forked-skill markerと子streamが存在する。sourceの4 SMD SHAは準備指定と一致し、closure-at-launchは指定50b5e3b8…である。
- C24 write receiptはcaller root、repository_id/common-dir、content rootを固定している。resume lineage gateのchecked=0から新規取込へ進んだ。評価helper成功結果のskill_argsとC05の実argsは完全一致する。reportのspec_dirもその絶対pathである。
- C19は2周で各周回のcoverage/source-citation/strict graph-schemaを実際に実行した。空graphの第1周もschema gateがexit0。第2周は3 CLIのstdoutを破棄しているが各実exit0を回収している。後周回の結果を第1周へ流用していない。IN1記録後に6キー/goal原文SHA検査が行われ、2行とも一致した。OUT1はexternal_pendingを維持している。
- C19 R0/R1/R2/R3は別Agentで検証され、全責務promptの逐語全文と固定receipt/goal/hash/observer pathが各promptにある。各verifierはobserverの実eventをread-only Pythonで開いて実command/結果を根拠にした。自己申告だけを採用したわけではない。ただし各責務のverdictは契約全体のPASSを保証しない。
- C05はR1/R2を全文Readし、C07はR7/C12/taxonomy、C06はR6/中立基準、C08はR4/catalogを全文Readした。stateは最初の822行に加え823–1802行を追加Readしており、欠けた後半を未読のまま監査していない。
- C07/C06はReadのみ。C08はReadと許可4 official hostへのWebFetch4件のみ。Bash/WebSearch/書込はない。C05の実作業はRead・正規gate/読取専用Python・Agentと許可2JSONのliteral保存で、cat/grep/find/ls/head/tail/tee、Write/Edit、TaskStop/TaskOutputを使っていない。parent mainのWriteはC02 progressへのものなので、C05違反へ付け替えない。道具宣言ToolSearchはmainのMonitor宣言検索1件で、追加監査実行の証拠にも権限付与にも数えない。
- C05の3監査は明示background/nameを付けず1件ずつ呼び、runtimeが自動Asyncを返した。C07完了03:32:16→C06起動03:32:40、C06完了03:33:36→C08起動03:34:07、C08完了03:34:33の順である。台帳3dispatch/3completion、session/tool_use_id/token、native prompt SHA、実最終応答SHA、receipt SHA、生verdictが全一致。pending launchを最終判定に使っていない。
- 初回source_verification/matrix_verification/doc_verificationは正規CLIの実exit/stdout/stderrと前後hashへ接地し、各auditorへ渡したJSONは初回結果と完全一致。state SHAはsnapshotと一致する。C06は書面QA0件であり、書面sectionの逐語監査の実例は今回ない。C06最終再実行のstdout JSON全体は初回と一致。C07は最終二モードの全shapeを再構築して一致確認した。C08側の初回機械証拠受領と独立4軸Web監査は実施されたが、caller側最終全JSON確認はB2のため未達。
- C06は5軸とsupersession/active consumerの定義を用い、C07は8カテゴリ×6 platform全48セルの意味監査を行った。C08は全4 targetの公式性/現行性を実WebFetch応答と照合し、機械exit0だけで意味監査を置換していない。これは今回実行の証拠であり、Web応答内の指示や事実を無条件に正しいと認定するものではない。
- C05のsnapshot12ファイルは初回/final/report/凍結実bytesですべて一致。C06の保存JSONは応答JSON部分と同じで、markerはJSON外へ分けられている。C05はfoundation/decision/knowledge/prompt品質も評価し、G-matrix/G-source-citation/G-knowledge-graph4profileとhearing再導出、report形状/帰属gateが実exit0となった。ただしB2があるのでこのreportを契約完了したPASSの証明として採用できない。
- C05 reportの書込/検証後にC02 Skillとpayload作成が始まった。親はC02 R0–R4をSkill前に全文Readしている。payload SHAはdry-run/add/immutable receiptで同じ60a7b609…であり、確認根拠も含む。直接graph/content writerを実行した痕跡はなく、canonical addが2nodeを作った。
- 2nodeはいずれもconfirmed/pass/readiness complete。lineage全6fieldがあり、source実bytesのdigest=source_digest=evaluated_digest=report snapshot。graphのcanonical digestはreceiptと一致し、import後lineage/strict schemaは実exit0。feature本文や生成ロジックを新設していない。これは成果物の物理的整合の確認で、B2/B3を相殺しない。
- guardは混在したJSON保存commandを一部拒否したが、拒否時点でauthoritativeファイルへ書かれた証拠はない。後続は読み取りと許可eval-log保存を分離しており、source/settings/guardを変えて迂回していない。global homeの探索試行もguardに拒否され、ローカルrepo探索へ戻っている。

## observer v3の原本復元

frozen-raw/sysspec106のtool-observer-source.pyを、module main/scanを走らせずextract関数だけ復元し、固定session/元observer path/caller rootを渡した。parser SHAはd0ac1e4c…でprovenanceと一致した。

10 native streamのbytes/SHAとindexのobserved_streamsが完全一致。extractから復元した160 event（Bash96、Read49、Skill6、WebFetch4、genuine Skill本文注入5）はindex全event summary/orderと各payload JSONの双方で完全一致した。assistant/result UUID、source line/順序、全prefix bytes SHAも原本へ再照合した。不一致/余分eventは0件。Skill injectionはnative successful Skill pair・isMeta/turnCompanion/parentUuid/sourceToolUseID・宣言plugin pathへ接地している。

API再掲、思考、Agent応答、observer自己参照をeventとして混入させていない。native側で別途Agent/Write/ToolSearchの実呼出しを確認したため、observerの5primitive以外のabsenceを未実施の証明にはしていない。自己反射を除くread-only観測であり、observerの42境界probe結果は106のgoal証明として採用していない。

公開コピーとfrozen原本の匿名化manifest10件のoriginal/redacted SHA、原本bytes、行数維持を照合した。goal-evaluation JSONのtranscript_sha256は公開Dの0a2e3c77…へ束縛し、観測prefix再構成はraw原本dc809743…へ接地した。匿名化後のbytesへ原本prefix SHAを当てて不一致扱いにはしていない。

## 同sourceでの次回実行指示の明確化

1. elicit/doc-fetch/compileに属するBashは、読取検査・提示・補助ログ保存も含め、毎callで同じC24 rootのexport/cd/pwd照合を付ける。実生成だけに限定して解釈しない。
2. C05は初回の完全なdoc_verificationを保持し、最終も同じ全fieldを同じ実argvから再構築して全JSONを比較する。refs/state/val等の縮約形や一部tupleへ置き換えない。helper argsは変更しない。
3. C02はstandard後の未達responsibilityを正規prompt全文付きAgentへ委譲してから閉じる。writer所有者を1人に固定し、canonical writerを使い、終了後の必須integrity verifierも維持する。
4. 各run Skillは現物path/digest/開き方を実出力してから、別callで事前回答standardを記録する。event名を保存しただけで提示済みにしない。捨て読みcatは省く。

これらの実行上の不足を、source変更・制約緩和・input/承認書換え・過去PASS流用で埋めない。poll時刻正規化の検討は親担当で、本評価はそれを新たなblockerにしていない。
