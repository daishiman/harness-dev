FAIL

主原因の分類: C08 の Web 裏取り未実施ではなく、observer v2 の収集範囲を実行全体とみなした R2 と親の誤認。両回とも原本では許可された4公式hostへの WebFetch が4件ずつ成功している。C08の4軸評価も実結果に対応している。

- C19 の最終成果が未達。正規 C02 Skill は起動されず、最終 graph は graph_revision=0 / nodes=[]。必要な specification と architecture の2ノード、source_lineage、confirmed/pass、readiness、原本 source_digest=evaluated_digest は成立していない。native status も FAIL で、poll DONE は目標達成を示さない。
- R2 と親の再検証は observer v2 の対象外を未実施と誤認した。初回 R2 は a76d4d17a5548d7d3 を8 Readのみとし、親は再評価後の a9f5829f0bbc29081 を6 Readのみとして停止したが、frozen 原本には両者それぞれ4件の成功 WebFetch（code=200、is_error=false）がある。独立検証が証拠範囲を判別できず、実際のC08監査へ反する blocker を確定した。
- loop3 の IN1 は正本違反。main toolu_01XrvZJ8d1jxUamYEKmVRj14（原本656行）は coverage/source-citation/schema の3CLIをその周回で実測せず、gates unchanged since loop2 として PASS を追加した。C05内のC12/C13再実行は graph schema を含むC19の3CLI実測を代替しない。
- 再評価後の R2 について、独立 Agent を再起動していない。main の3 Agent はR0/R1/初回R2のみで、loop3は親がobserver indexを集計し reevaluation-grounding-check.json を書いた。直前の次指示が求めた独立再検証も満たしていない。
- C05の機械証拠再取得契約を全ては満たさない。初回 toolu_01QejuR151SfhcLHXqstdtyv はMVをpathのない部分形、DVをexit/stdout/stderrと一部digestで比較しており、初回の全JSONを再構成して比較していない。2回目 toolu_01V5hL9WGRYA8Tt377mfAuKT は stdout/stderr を strip/先頭長に加工して列挙し、MV/DV/source_verification の初回全JSONとの一致を検査していない。2回目C13取得も全input/validatorの取得中前後hash一致が揃わない。実ファイルsnapshotは一致していたが、その事実で省略された取得・一致検査を履行扱いにはしない。
- C05のレポート保存がR1 4.3/task107の指定形に従っていない。初回 toolu_01VQWWaGgASLqLwD3VpQ2yDY はPythonで組立てたJSONをpipe、2回目 toolu_016Z6ezaZ3fgiu5yVEfcuUpG は write_text(json.dumps(rep,...)) で保存し、指定されたliteral Path.write_text(sys.stdin.read())と引用JSON heredocではない。保存先は許可されたreportであり、仕様書への書込みを主張するものではない。
- 最終C05 reportのmatrix_coverage summaryが「確定7・対象外41」と誤記している。同reportに束縛されたstateおよび独立C07/C06の実結果は「確定8・対象外40・未収集0」。帰属gate exit0だけでは、報告内容の忠実さまで証明できない。

確認済みの範囲:

- 評価者は準備時にsource/scenarioだけを読み、完走通知前の105ログ・過去live rawを参照していない。点数を使用しない。
- 固定parser SHA=d80a0f69bf214af01485c04f7a6eabfc6df48b529ff7864765e95508aac6ddc0 のextractだけをfrozen各streamへ適用し、197 eventとindexの全JSONが一致。各source UUID/行/prefix bytes SHA・actual input/result、3件のmetadata-bound main Skill注入を同parser契約で照合。5件の実Skill呼出しのうち2件はnative status=forked/agentId付きC05で、fork本文冒頭・forked-skill metadataへ対応する。API再掲・thinking・親自己判定を一次イベントへ昇格していない。
- 公開匿名化は12ファイル・46箇所の<redacted-email>置換だけで原本から再構成でき、manifest SHA/bytes/行数が一致。それ以外の既存ファイル差はpoll-state.elapsed 1696→1697のみで、ceil(observed_at_unix-start.epoch)=1697、normalization SHA/式と一致、予算変更なし。公開transcript SHAは必須fieldに記録。
- C08初回: C05 aba42a4dfca29a6b8 → toolu_01LW7ay9kTo2Wki2DfQhuhQb → C08 a76d4d17a5548d7d3。R4/catalog/references/stateの実Read、許可された4公式hostの実WebFetch4件がすべて成功。targets全件対応・公式性・現行版・時刻/出典の4軸を個別に返している。FastAPIは先頭10万文字の制限を開示している。
- C08再評価: C05 a4035380fc29af7dc → toolu_01BMbDhtQcdsU5CdG5rPMTxi → C08 a9f5829f0bbc29081。同じ4公式hostへWebFetch4件すべて成功し、R4/catalogの実Readと4軸評価も存在する。2回目の実Fetch未実施という別blockerはない。FastAPI本文の一部とTypeScript betaの確認範囲は開示され、安定版の照合結果はactual結果に対応する。
- 両C05はnative Skillのfork実体に接地し、各3監査は明示name/run_in_backgroundなしで直列。各実prompt SHA、実completion本文SHA、session/tool_use_id/subagent/receiptを正規ledger読取関数で照合し6receipt全て一致。次監査のdispatchは前監査completionより後。自動Async launchを明示background指定と混同しない。2回目C07のtokenなし1対1fallbackは正規読取側でresolvedへ照合され、別のabsent completionはreceiptに消費されていない。
- C06/C07は実Readのみ、C08はReadと許可hostのWebFetchのみ。C05にcat/grep/find/ls/tee/Write/Edit/TaskStop/TaskOutputの実使用はない。ToolSearchは両回select:Monitorという宣言検索だけでMonitor実行なし。
- C06は5軸・C07は48全セル/6platform/集約/対象外承認と根拠を独立監査しており、機械gateの存在だけを意味監査へ置換していない。source_verificationは書面0件を含めstateSHAに束縛。初回MV/DVの全fieldと実CLIは存在し、両report snapshotの12digestは固定最終原本に一致。これらの確認済み項目は再取得手順の不足を免除しない。
- C19のC24固定receiptとhelper成功出力のskill_argsが2回のC05 Skill argsに一致。elicit resumeとcompileは実Skill、doc-fetchはmissing=0/discovered=0の条件付き非起動。compileは正規writerでbyte-stable。親はC02 R0-R4を全文Readしたが、取込は実行していない。未実行のR3/mandatory verifier/lineage/evaluated_digestはPASSにしない。
- 初回R2が指摘した2件のprefix欠落はいずれもread-onlyなplugin source調査。うちR3準備のコマンドをelicit/doc-fetch/compile生成Bashの契約へ一律に拡大して、主原因と断定しない。生成を行う本処理と親のread-only調査を区別した。
- W/source/D/rawは無変更。独立検査成果は/tmp/pr86-sysspec105-*のみ。v3修理案は105へ遡及していない。

対応表:

| 評価 | C05 fork | C08 fork | 実WebFetch | 最終監査/receipt |
|---|---|---|---|---|
| 初回 | aba42a4dfca29a6b8 | a76d4d17a5548d7d3 | 4件、全200 | PASS、completion SHA/receipt一致 |
| 再評価 | a4035380fc29af7dc | a9f5829f0bbc29081 | 4件、全200 | PASS、completion SHA/receipt一致 |

C08 actual I/O は公開コピーの `transcript/subagents/agent-a76d4d17a5548d7d3.jsonl` 29–36行、`agent-a9f5829f0bbc29081.jsonl` 29–36行へ接地（原本と行数同一）。報告・receiptは根拠の補助であり、WebFetch実在の一次根拠は各tool_use/tool_resultとnative code=200。

原本復元: 固定parser.extractから197event/index全JSON一致。匿名化12file/46置換とpoll唯一差のSHA/式を独立照合。詳細機械結果は `/tmp/pr86-sysspec105-primary-checks.json`、C08 actual I/O は `/tmp/pr86-sysspec105-c08-primary.json`、receipt照合は `/tmp/pr86-sysspec105-receipt-checks.json`。

公開transcript SHA-256: ed6b1e221f773ef7933d4a9848abe39213a5a92233d02974c308e8bf123cadc3
