# 対象121 early prefix 独立レビュー

判定: **FAIL（固定prefixで確定した既発生契約違反）**。全終了の最終goal判定ではない。

評価者: `/root/review_sysspec121_fresh`

main SHA-256: `db864be80d72ac91ced954eb07ea7d231930e98a3ae00c1aa3c0ec02fc5cee52`

## 証拠範囲

- `main.jsonl`: 1023026 bytes / `db864be80d72ac91ced954eb07ea7d231930e98a3ae00c1aa3c0ec02fc5cee52`（一致を実測）
- `subagent-agent-a3e9c29d13b2d7c5b.jsonl`: 821831 bytes / `24c7e972bb6cfca4c994f010d50ec587f15115ab3245a053812702bd7466ea53`（一致を実測）
- `subagent-agent-a61cb090a383592b5.jsonl`: 492590 bytes / `40e42461a04e7e5f01f86c01d9767963ae23ccd7964488753d47a0c07b885b35`（一致を実測）
- `subagent-agent-aeb112ba4103bb1f8.jsonl`: 457732 bytes / `2347ee642ef88f8cf37a97716b88fb8514e7dbce6dcbd327d7b86f6c68bcb930`（一致を実測）

## B1: C05を必須helperなし・手書き相対argsで起動

正本: `fx/plugins/dev-graph/skills/run-dev-graph-system-spec/prompts/R2-delegate.md:25-26`。
一次証拠: `main.jsonl:210 (toolu_01JPstQZSzYCusUVhwvdeY2k)`。

全prefixの実tool_useにbuild-evaluation-context.py呼出し0件。C05 argsは --spec-dir system-spec --output system-spec/completeness-report.json。

C24の固定receiptと評価対象/出力先の再照合を迂回し、正規Skill委譲で評価対象を固定する受入条件を満たさない。

## B2: compile責務promptを読む前に10ファイルを生成

正本: `fx/plugins/dev-graph/skills/run-dev-graph-system-spec/prompts/R2-delegate.md:32; fx/plugins/system-spec-harness/skills/run-system-spec-compile/SKILL.md:166-168,222`。
一次証拠: `main.jsonl:186,192 (toolu_01M3uUPBf6SREBtiJyDgG9mR)`。

compileのR1-assemble/R2-render/R3-crosslinkとown resource-mapの全文取得が生成前に0件。canonical compileはOK:10ファイル生成を返した。

正本が判断・章構成の意味付けを担わせた責務契約を未読のまま成果を生成した。後で読むことは出力前必読を回復しない。

## B3: 必須elicit resumeを実行せずcompileへ進行

正本: `fx/plugins/dev-graph/skills/run-dev-graph-system-spec/SKILL.md:101`。
一次証拠: `main.jsonl:88-210 (compile Skillは156、writerは186)`。

対象C19起動後、elicit Skill 0件のままcompile Skillとwriter、C05起動を実行。state/refsを自作診断で確認したのみ。doc-fetchは条件付きなので未起動自体を違反に数えない。

scenario観測1が求める正規flowのelicit→compile→evaluator順序が成立せず、seedの完成状態確認でelicit正規resumeを代替した。

## B4: 現物提示・standard記録前にsemantic evaluatorとsubagentを起動

正本: `fx/plugins/dev-graph/skills/run-dev-graph-system-spec/SKILL.md:73,81,95; fx/plugins/system-spec-harness/skills/run-system-spec-compile/SKILL.md:85,94`。
一次証拠: `main.jsonl:31-210; subagent-agent-a61cb090a383592b5.jsonl:60`。

mainの全assistant text/実toolを確認。preflight/compileの現物path・実digest・開き方提示、standard選択記録がないままC05が起動しC07 Agentが完了。事前回答standardはtaskにあるが、taskも現物提示後の記録を要求している。

sourceのartifact_deliveryで禁止されたpre-choice semantic-evaluator/subagentへ進んでおり、標準改善を有効化する正規遷移を経ていない。

## B5: C05が許可されたpython検査/保存以外のBashを実行

正本: `fx/plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/prompts/R1-score.md:88; 同SKILL.md allowed-tools`。
一次証拠: `subagent-agent-a61cb090a383592b5.jsonl:32-35 (toolu_01FQVhAmdT8VkCMGnEgSFPia)`。

C05本人が find system-spec -type f -name "*.json" -o -name "*.md" | head -20 を実行し、実ファイル一覧を得た。

read-onlyであるだけでは満たさないC05の明示Bash境界を外れた。runnerが新設した一般validator全読等ではなく、source自身の許可ツール範囲の逸脱。破壊/漏洩が起きたとの主張はしない。

## 判定境界

- これは固定early prefixの既発生契約違反の判定で、trial全終了の最終goal verdictではない。
- manifestに記載された全4streamのbytes/SHA-256一致を実測。全JSONLを構文解析しtool_use/text/tool_resultを確認、重複したreplay行は二重実行として数えていない。
- 未完了のC05全18prompt意味評価、C08、C19責務Verifier、3ゲート/6キー/hash、C02取込・lineage・3観測・予算は、このprefixで未了なだけでは追加FAILにしない。
- mainのactual_modelがhaikuでもmodeldefaultの通常trialなので単独の違反ではない。
- C06の書面前同actorBash成功→書面Read順はprefixで観測できる。runner補助guardの通過をgoal PASS根拠にはしない。
- source/入力/設定/原本は編集していない。過去trial/review/verdictを参照していない。
- C24 receipt保存のteeは /tmp/dev-graph-context.json への書込みをOSが拒否。これ自体を独立blockerとして水増しせず、B1の前提未成立を補強する証拠とした。
