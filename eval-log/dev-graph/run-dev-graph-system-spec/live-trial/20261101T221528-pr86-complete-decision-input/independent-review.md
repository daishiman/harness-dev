# sysspec119 fresh 独立 goal 評価

判定: **FAIL**。評価者 `/root/review_sysspec119_fresh`。点数は付けない。

D: `/Users/dm/orca/workspaces/harness/pr86-ci-fix/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261101T221528-pr86-complete-decision-input`

D/transcript.jsonl SHA-256: `c78548a27c6ce2da10e6525205627c6a44e3c404131bc3af98d956a8a17d9feb`

## 成果未達の決定的一次証拠

`fx-final/tree/.dev-graph/state/graph.json` は revision 0、nodes 0。`fx-eval-log/system-spec-completeness-report.json` は verdict FAIL、matrix_coverage FAIL。したがって確定 specification/architecture を lineage・評価証拠付きで取り込む description の成果がなく、positive scenario の観測1・2は未達。観測3は登録がないため正規登録の成功を実証していない。出力の DONE/FAIL や status の申告だけから判定していない。

## 入力根拠と C06 の導出

現物 `fx-final/tree/system-spec/spec-state.json` の qa-037/038 は basis=user-decision だが、provenance は orchestrator の既定値を agent-inference として追加した後、評価失敗を受けて team-lead 指示で user-decision に変更した経緯を明記する。auth/web の主たる qa_ref は qa-002、security/web は qa-004 で、ともに実在する。問題とされた参照は補助 qa_refs であり、主たる参照の欠落とは区別する。approval_log の foundation 承認等は、この2件を新たな利用者一次入力に結ぶ独立記録ではない。

raw C06 `transcript/subagents/agent-a749f5ed1b20ff93e.jsonl` L49、UUID `d46fcaff-100b-4464-9cd4-a9af328c60fe` はこの事情を medium traceability 3件として返した。本文中 JSON と `fx-eval-log/hearing-audit.json` は文字列として一致した。D と raw の最終 message も UUID で一致する。

正本 R6 は証跡のない正常判定を禁じ、裏付けだけの影響を証拠で示せるトレース欠陥は medium とする。aspect-criteria 1a は medium・軸2以外を FAIL とし、軸2の補助参照だけにある medium 誘導を注記へ緩和する。後者の緩和を traceability へ拡張しない。正規 `aggregate-completeness.py --hearing ... --state ...` を今回の保存現物へ read-only で再実行し、verdict FAIL、blocking 3、errors 0、exit 1 を独立確認した。これは C06 自身の verdict をそのまま信じた判定ではない。raw C05 L247/L249、call `toolu_01Nt13Qsai7kCyKJQDJYj3ZY` にも同じ実行・導出がある。

合成のシナリオ発言自体が全件不適切とは断定しない。今回確認した入力の後付け根拠と正規監査・導出の失敗を記録する。C06 による補助 qa_refs の意味評価の全域監査は行っていないが、たとえその意味判断に再検討の余地があっても、現実の report FAIL と graph 0 のため本 run の goal FAIL は変わらない。

## source の停止境界

C19 R3 は evaluator PASS 前の取込 payload 作成・C02 起動を禁止する。現物 progress は evaluator gate と取込を not_achieved、C02 未起動とし、raw main の Skill 呼出し走査に C02 起動はなく graph も空のまま。失敗時の停止はこの境界に整合する。ただし停止したという事実は positive acceptance の成功ではない。新規利用者承認を創作して進むことも今回 task の許可外である。

## C05 report の帰属整合エラーは別原因

C07 の raw 最終応答 L51、UUID `82921584-9cb0-46a2-81b3-3730b06b331e` と hook 台帳は PASS。C06 sub-input から matrix_coverage は FAIL になる。

C05 raw `agent-ad9854451a08928c6.jsonl` L287 は初版 primary receipt=FAIL/aspect=FAIL を書き、L290 UUID `8eed1c8f-c30b-425a-8404-9267ec9423f1` は hook 実判定との不一致で exit1。これは C07 の実判定を忠実に保存していない初版出力の違反で、C05 最終説明の「値を書き換えていない」という一般化は採用しない。

L299 は primary receipt=PASS/aspect=FAIL へ訂正し、L302 UUID `680c8790-c4cc-4547-91b5-6b35ffcb6b96` で primary receipt と観点 verdict の不一致により exit1。最終 report の値もこれと一致する。正本 `audit_fork_attribution.py` L584-L590 は primary receipt と aspect の一致を要求し、その直後に台帳一致も要求する。一方 aspect-criteria は C06 sub-input が観点を FAIL にでき、receipt verdict をその結果に書き換えないよう要求する。この C07 PASS / C06 FAIL の組合せで最終 report を通せないことは、C05 の説明だけでなく source の条件と両方の raw エラーから確認した。

この帰属整合エラーを、入力根拠の問題そのものや C19 の安全停止の欠陥と混同しない。解消しても C06 由来の評価 FAIL が残り、取込成果が自動的に生まれることはない。

## IN1 と証拠境界

IN1 の正本文と実観測、3観測の参照先は JSON に記載した。L373 の三CLI exit0 と、L445 の誤 path/schema=2、L465 の正規 graph path/schema=0 を確認。空 graph の schema PASS は内容の取込成功の代理にしない。C05 の他5観点の PASS は全面監査せず、その説明を無検証で追認していない。

private raw と D の transcript は bytes が異なる。C06/C05/C07 の最終応答は UUID/message 一致、hearing/state/graph/report は raw と D で bytes 一致を確認した。全 redaction 差分の独立再構成は未実施。今回の依頼に従い、全 raw tool I/O・全 observerv3・全 stream UUID/line/prefixSHA/fullSHA/順序・native Skill 本文注入の metadata/fullbody 接地の網羅再構成を先行していない。未確認を未履行と断定していない。

過去 trial・review・input-review・他 agent の状態や結論は未参照。現物入力に含まれる過去経緯は今回の provenance としてのみ参照した。source/fixture/raw/D は編集せず、出力は指定された `/tmp/pr86-sysspec119-fresh-*` の2ファイルだけ。
