# sysspec116 独立 goal 評価

判定: **FAIL**。登録成果・機械ゲート・証跡接地は成立したが、必須実行制約に2件の違反が残る。点数は付けない。

## Blockers

1. C05 の C08 監査を明示 background で起動した。transcript/subagents/agent-a1df14947e05f7107.jsonl:236 の Agent toolu_01XiXiegUZqPvXDgrkVat993 に run_in_background:"true" がある。task.md は C05 の明示 background/name を禁止し、SS0.1.24 R2-delegate Layer 1.1/6.2 も正式 evaluator の foreground 実行を要求する。3監査の実 completion と digest 接地は成立しているが、この実行制約違反は解消しない。

2. C19 親の全 Bash に要求された固定 C24 root の前置きが1件欠ける。transcript.jsonl:152 の toolu_01EZYH9me3ecZqVyCY3EwwVE は observer の ls/head/python 診断を直接実行し、export CLAUDE_PROJECT_DIR / cd / pwd-P 照合がない。task.md の全Bash呼出し契約には observer 診断の例外はない。observer 自己I/O は projection 対象外なので、投影内の45件が適合するだけでは親の全46件の適合を証明できない。

## 独立に成立を確認した事項

- source: C19本文 SHA `10b54fd1e3070f57a8a02de2a31fb93a57940e15ab108e6df96947836812f049`、正規closure `ebec0c4771f30cd2be8260f9871ad0e4d42112e7f03ebed8c04a0326bf13a5ef`、SS0.1.24。原sourceとpin済みcopyを照合し未変更。
- observer: main＋10subagentの11streamから247eventを再抽出し、全object/index順序/UUID/prefix bytes・SHA/call→result順序/stream SHAが一致。自己I/OとAgent結果はprojectionの意図的対象外なのでnative原本も確認した。
- publication: 差分は11transcriptの匿名化とpoll.elapsedのceil補正のみ。公開transcript SHAは `766681e38d94d65b4b35066ce6a21e11be8346424d6f410dcdec7c0952cc844c`。policy/at-collection/actual CLAUDE.local.mdは指定hashで一致。
- C05: 独立contextで全10Markdown、全18prompt、両map、rubric/aspect/R1/R2/schemaの全行取得を確認。prompt別意味評価根拠がreportにある。3監査の実final response、token、tool-use ID、prompt SHA、completion SHA、receipt一致を別途計算した。C06 JSONは応答のJSON部分と逐語一致。snapshot12件・gate_results・report集約も整合。保存は許可された2JSONのみで自作保存scriptはない。C08の6回の実WebFetchは許可host上で行われ、必読R4/catalogを先に読んでいる。
- C19: 各roundの3CLI→IN1記録→6キー/hash検査を確認。固定receiptはsha `8bf107d8cc2ed039bc513645fdb1f7c2eb060d5a646f57eeda5a44a1bc6c6205`。helper成功argsとevaluator実引数は一致。R0/R1/R2/R3各Verifierが実完了し、元goal/hash/直前directiveを受けている。集約ログは親が所有。
- C02: evaluator PASS後だけpayloadを作り、同じSHA `93e158a9bf90fd9360d35f26161f07e29dee67a8d50d3fda18d189fe53d6990b` をdry-run/addへ渡した。pre-choiceで実成果提示→standard→baselineの順。2nodeはconfirmed/pass/complete。lineage/evaluated_digestと現物bytesが一致し、唯一のwriter receiptと現graph canonical digest `sha256:a5b8ebd04adb86e665df9f774c1bd9c52f27c4299e4a9fb7f89d00e61d919e47` が一致。post-choice commitなし・baseline rev1とpre-choice receiptが整合し、独立整合性auditorも同digestを実返却した。
- 独立CLI: coverage/citation/design-ref/graph/lineage/report/hearing/knowledgeすべてexit0。compile固有受入63件の成功がnative stdoutにある。pytest後もcaller state/章digest不変。
- 予算: 公開elapsed1816秒、usage20457937tokens、11stream/216unique message、欠測0で正本3300秒/23000000tokens内。

## 判定の境界

C07/C06の明示background無し呼出しがホストでAsync受理されたことは、それだけで違反扱いしていない。C08は実引数でbackgroundを明示しており、taskの明文禁止とsource正式運用契約に反する。completion/schema gate成功でこの違反を免除しない。

C19の `drift_signal: none` やround形状は、生成用schemaのenumだけでは裁いていない。本文6キー/hash/checklistの意味的履行を確認した。

C05 report中の「cloud原則の採否矛盾」は、qa-005の原子性/冪等性と追加QAの分散資産/Blob非適用の対象差を考えると根拠不足である。またlegacy_backfill自体は正規sourceが許す。これらをfixture不足や新しいFAIL条件へ転用しない。

過去trialのraw/verdict/reviewと今回input-review結論は未参照。source/fixture無編集。今回の評価はtarget goalに限り、親がこれから行うcanonical finalizer/reapの未実施はblockerに含めない。
