# 対象121 fresh独立goal評価

**FAIL**。必須helperを省略したC05起動と、責務prompt未読のcompile成功が既発生であり、この2件だけでも受入不成立。

評価者: `/root/review_sysspec121_fresh`

公開workdir: `/Users/dm/orca/workspaces/harness/pr86-ci-fix/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261101T151641-pr86-bounded-context`

終了時公開transcript SHA-256: `5211d30e6631aeec7b8061125830514a540d300e2a998c7e2a24fe68e2eaebfd`

私用終了原本SHA-256: `786a17491588e0ddb5dd8669bc5cd60018f0a7ef9e0d037e6baa536af3b17daf`（公開匿名化対応表と照合）。

## Blocker

- B1: C19 R2-delegate:25-26の必須build-evaluation-context.pyを実行せず、transcript.jsonl:210でC05へ手書き相対args (--spec-dir system-spec --output system-spec/completeness-report.json) を渡した。全終了streamの実tool_useでhelper呼出し0件。固定C24 receiptに評価対象/出力先を束縛する正規境界を迂回した。
- B2: C19 R2-delegate:32が要求する委譲責務prompt全文読込の前に、transcript.jsonl:186でcompileを実行し:192/:194で10ファイル生成成功。先行するcompile R1-assemble/R2-render/R3-crosslinkおよびown resource-mapの取得0件。責務出力前必読は後読みで回復しない。
- B3: C19 SKILL.md:101の正規elicit→必要時doc-fetch→compile→C05順序に対し、elicit Skill 0件のままcompileとC05へ進行。stateの自作診断は必須elicit resumeの代替にならず、scenario観測1のcanonical flowを満たさない。条件付きdoc-fetch未起動自体は違反としない。
- B4: C19/compileのartifact_deliveryが要求する現物path・digest・開き方提示とstandard記録がないまま、transcript.jsonl:210でC05、同C05子stream:60でC07を実起動。事前回答standardは現物提示後の記録を省略する許可ではなく、pre-choice semantic-evaluator/subagent禁止を越えた。
- B5: C05 R1-score:88のBash(python3 *)境界に反し、transcript/subagents/agent-a61cb090a383592b5.jsonl:32-35でfind system-spec ... | head -20を本人が実行し一覧を取得した。source自身の明示ツール境界の逸脱であり、runnerの追加一般監査要件を拡張した判定ではない。

## 3観測

1. 正規flow: helper前置・責務必読・elicit順序が不成立。根拠 `transcript.jsonl`。
2. 取込とlineage: 最終graph.nodesは0。根拠 `fx-final/tree/.dev-graph/state/graph.json`。
3. C02のみの登録/複製なし: C02は未実行。肯定的な受入条件の完了認定はしていない。根拠 `transcript.jsonl`。

## 判定境界

- 最終FAILは既発生のB1/B2だけでも成立する。停止後の未完了を理由に必須違反を追加していない。残るB3-B5は同じ固定証拠で既に観測されたsource契約逸脱である。
- 判定用transcript_sha256は公開workdirの終了時transcript.jsonl実bytesのSHA。私用終了原本SHA-256は 786a17491588e0ddb5dd8669bc5cd60018f0a7ef9e0d037e6baa536af3b17daf。evidence-redaction.jsonのoriginal/redacted両SHAと実bytesが一致し行数維持を確認した。
- 公開main 217行、4子streamをJSONLとして解析して実tool_useを確認。全52個の一意tool_useを走査しhelper不在を確認。重複replay行は二重実行として数えていない。成功判定のための全stream完全再構成/全必読被覆/全意味評価は行っていない。
- 観測1: B1-B3によりcanonical flow不成立。観測2: 最終graph.nodes=0で取込成果なし。観測3: C02 Skillは全終了streamに0件、登録は未実施。登録経路の肯定・複製0の完了認定はしていない。
- C05全18prompt意味評価、3監査の最終全件帰属、C19 R0-R3独立Verifier、全周回3gate・6キー/hash、C02 pre-choice/必須Agent、lineage、予算の完全検証は未確認。未確認を追加blockerにしていない。
- actual_model=haikuはmodeldefault通常trialの背景でありblockerではない。input review/probe/guard通過をgoal PASSの代用にしていない。
- 同actor書面前Bash成功→Readの順序はearly C06 streamに観測。これはrunner補助であり、source要件と混同して全mustへ拡大していない。
- 正本SHA（fixture写しと作業source実bytes一致）: C19 SKILL.md=10b54fd1e3070f57a8a02de2a31fb93a57940e15ab108e6df96947836812f049; C19 R2-delegate.md=07ab201d7192adbbbd7722d0130a77b84eb143916998e47e519bfc1d5f286f2f; compile SKILL.md=d793d397edd7469061171069fb217ac1f537bbd05d95c9b26c4d614bc5e8cd82。挙動閉包の起動時digestはclosure-at-launch.txt。
- 独立評価者は過去trial/review/verdict・他評価者の結論を参照せず、source/入力/原本を編集していない。成果の書込みは/tmpのみ。
