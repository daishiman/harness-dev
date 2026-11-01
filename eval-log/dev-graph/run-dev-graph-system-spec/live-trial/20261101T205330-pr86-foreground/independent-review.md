# sysspec117 独立受入評価

**FAIL。blocker は B1（C02 の選択後責務実行 fork 欠落）1 件。** 点数は付けない。

公開 collector: `eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261101T205330-pr86-foreground/`。
評価者: `/root/review_sysspec117`。公開 main transcript SHA-256: `93fc43bb603fc631b7f98785d013b29336a946ae1b622df939581904deec0be7`。

run-skill-live-trial の絶対ルール1と goal verification に従い、description が約束する成果、C19 IN1/OUT1、scenario 3 観測、source が要求する実行境界を一次証拠で分けて確認した。過去の実走・verdict・独立review・input-review の結論を判断根拠にしていない。positive-input-v5 は合成 given であり、今回の評価や実利用者承認を種として扱っていない。

## B1: 正規 C02 フローの未達

- C02 SKILL.md の Purpose & Output Contract は「C02 単一 writer 経由で atomic 登録された typed node/package と revision/digest receipt」を最小の実成果とする。Pre-choice 節は、その実成果物を main context で作り、path/digest/開き方を提示してから深さを記録する契約である。
- 同じ source のゴールシーク配線は、standard 後の未達 responsibility を担当 prompt とともに Agent の分離 context へ出す。必須 integrity auditor は実行担当の代わりではない。
- task.md はこの既存境界を明示し、「dry-runだけでstandardを記録してmainで未達writerを直接実行しない」「standard後の未達responsibilityはAgentで実行」「必須integrity auditorだけで責務実行forkを代替しない」と定めた。preset standard は改善深度の事前回答であり、この実行境界の免除ではない。

最終 main raw の実時系列は次のとおり。公開 transcript でも同じ tool ID と内容を確認できる。

1. `toolu_015MoxNf6Xrf2Es3DDVejyDi`: 正規 C02 writer の add --dry-run。write_count=0。
2. `toolu_01CryZUNMy6diusiEeh2uYEQ`: `run-dev-graph-node-artifact-delivery.json` を Write。`pre_choice_artifact.kind="dry-run preview (write_count 0)"` のまま、`choice="standard"`、`state="semantic_evaluator_started"` を記録。
3. `toolu_01UvWXhcNQ79dhgvGR9pUXj3`: 未達 checklist、revision0 の graph_baseline を progress に記録。
4. `toolu_01UwW3yvxE6nL3t3dnY6AYrb`: 親 main 自身が add を直接実行し、revision0→1、2node を登録。
5. `toolu_01AMXCMUCEMX9pqdTgoBTdqD`: 後段の integrity auditor。
6. `toolu_01UMaucyTe9xvNdus3HyUrfZ`: C19 R3 の独立 verifier。

全10rawstreamの Agent 実call は計8件で、C19 R0/R1/R2/R3、C05 3監査、integrity auditor だけである。C02 の R3-write 等を実行した責務 Agent は存在しない。observer は Agent/Write を意図的に除外するため、この不存在は observer の absence でなく native raw 全件から確認した。

これは成果物が壊れているという finding ではない。実成果2nodeと canonical writer-only は成立している。一方で、今回タスクが必須とした正規 C02 の選択後経路を実行していないため、「正規フローを新たに実走して取込を受け入れる」という対象タスクの完了を確認できない。CLI exit0、receipt、後段 auditor の PASS だけでこの経路違反を緑化しない。よって最終 FAIL とする。

主証拠: `transcript.jsonl`、`fx-eval-log/run-dev-graph-node-artifact-delivery.json`、`fx-eval-log/run-dev-graph-node-progress.json`、`task.md`。source 正本は repository の `plugins/dev-graph/skills/run-dev-graph-node/SKILL.md`。

## 成立した成果と直接条件

- 観測1: declared system-spec-harness 0.1.24 の4entrypointを preflight。elicit resume、必要性判定後の doc-fetch 省略、canonical compile、独立 C05 を Skill 経由で実行。seed と同じ bytes でも、今回の compile 実call と新規評価は実在する。
- 観測2: specification と architecture の2node は confirmed/pass/readiness complete。lineage は 0.1.24 の index と要件定義書に解決し、source_digest=evaluated_digest=C05 artifact_snapshot=実 bytes。node 本文digestは immutable C02 receipt と一致する。
- 観測3の writer-only/非複製部分: 登録は C02 の build-graph-node.py のみ。payload・graph・content の直接書換えで writer を代用せず、同等 elicitation/compile logic を dev-graph に新設していない。source 閉包は起動時と現在で一致。
- IN1 正本全文: 「system-spec-harnessのcoverage/source citation gateとdev-graph schema gateがすべてexit0になる」。周回1/2とも実CLIの3gate全exit0を確認。各周回の progress は実測に接地し、後周回からの遡及はない。
- OUT1 正本全文: 「仕様書/architecture要求がsystem-spec-harness成果物をsource lineage付きで引用し、同等ヒアリング/compileロジックがdev-graph内に複製されていないことを受入テストが確認する」。引用/非複製の直接条件は成立。B1はこの成果を否定せず、正規flow全体の受入を妨げる別の必須境界である。

最終 graph canonical digest は `sha256:de7b1ff28a5d811277a410fbb58257a84958c73e43df2bc44295290a1b176a08`。specification の取込元digestは `f7f6476735e6ed5e07b2583a7d628b8cfd89227235c5745f3ae10681b8d545e2`、architecture は `6a5f58b008f16a4351a66e64ef7b1eb439908821565078c01d8115f53ac22bc8`。こちらの独立 read-only 再検証でも lineage、strict schema、C05 report/台帳帰属は全 exit0。

## C05 と3監査の一次検証

C05 の Read 実応答を行番号ごとに現物と照合し、全10Markdown、state/refs、全18prompt、R1/R2、rubric、aspect、schema、C05 own map と C04 map の全文取得を確認した。大きい state は追加Readで末尾まで補完されている。18promptは本文固有のevidenceと停止条件を使った意味評価があり、機械形状や既存reviewだけへの置換は観測されない。

C05 は実callとして Read50/Bash9/Agent3、Write/Editなし。Bashは正規CLIとliteral Pathによる許可2JSONの保存で、自作reader/builderの保存・実行なし。exit code の観測用 echo は併記されるが、新たな書込・探索経路を作っていない。C06 最終応答のJSON部分と保存JSONは文字単位一致。report heredocと保存実体、3gate stdout JSONとreport、開始/終了snapshotとartifact_snapshotも一致。

C07/C06/C08は別messageのforegroundで逐次実行。実final response→ledger Read→次のdispatchの順で、name/background指定なし。各token、最終AUDIT_VERDICT、6台帳行、3receiptを確認した。C06は全stateと5軸、C07は全stateと両モードCLI、C08はR4 SSOT/catalog全文・形式CLI・許可5hostへのWebFetch6件を実行。Kubernetesは末尾不足を追加取得。C08の全state読了は担当契約ではなく、targets全件を許可read-only JSON抽出で取得しているため未実施扱いにしない。

## blockerへ拡大しなかった差分

- C06/C08 adapter本文は native system へ厳密に全文投入されている。frontmatter全文は未取得で、model/toolsはnative metadataに反映済み。owner/version/phaseなど補助metadata差分単独に成果・安全性・意味評価の阻害因果は認められず、B1とは別のrunner指示差分として記録する。
- C19 preflightはstdoutにpath/digestを出し、開き方はstandard記録JSON内に初出。前段の提示順序の差分として残す。これ単独を主たるFAIL理由にしていない。C02のdry-runを最小実成果とした選択はB1の直接根拠である。
- C02 Skillの起動はR0-R4のReadより前だが、出力生成前にはprompt全文を取得。C02 frontmatterを含む独立Readは確認できない。source本文の実行境界はnative本文にも明示されており、B1は単なるfrontmatter未提示の推測から出したfindingではない。
- integrity auditorは依頼されたtext形式で判定/digest/根拠を返し、sourceが記すJSON形式ではないが、必要な内容は追跡可能。R3 verifierはPASSだがC02の選択時点/責務実行forkを監査せず、B1を覆さない。R3応答のpayloadとC02 Skillの相対順序説明にはrawとの違いがあるが、evaluator PASSより両方後というR3境界は成立。
- 初期親commentaryに英語が混在する。成果物と最終報告は日本語で、これは言語指定の差分として残し、引用付き取込の成否と混同しない。
- intermediateはWriteで既存1行を完全保持して2行目を追加しており、既存周回の改変はない。C19本文の6キー/hash/checklist契約に照合し、HC生成用schemaの未宣言enumへ自動拡張しない。

## 回収証跡・匿名化・予算

両固定prefixの全manifest SHAを照合し、最終private原本の正規prefixと厳密一致。post-import graph状態4fileは最終snapshotと同一。全10streamをsourceと同じ純粋extract関数で再構成し、observer 215/215eventが内容完全一致（missing/extra/different=0）。Read/Bash/Skill/WebFetchなどのobserverだけでなく、除外されたAgent/Write/自己I/Oもrawから検証。main Bashの固定root前置き違反は0。

公開10rawfileはprivate原本から1種類の匿名化置換44回だけで厳密再構成でき、行数を維持。公開main SHAは上記と一致。poll-stateの変更はelapsed 2131→2133のみで、ceil(observed_at_unix-start.epoch)と一致し、予算を緩和していない。途中のobserver-path修正も同じstate/startを保持し、subjectは変えていない。

正規resource計測はmeasured=true、10streams、161 unique assistant message IDs、13,872,426 tokens（上限23,000,000）。canonical poll DONE2131s、公開elapsed2133（上限3300s）。gate/nudgeで救済していない。source SMD SHA=`10b54fd1e3070f57a8a02de2a31fb93a57940e15ab108e6df96947836812f049`、behavior closure=`ebec0c4771f30cd2be8260f9871ad0e4d42112e7f03ebed8c04a0326bf13a5ef`を再確認した。

最終判定JSON: `/tmp/pr86-sysspec117-eval.json`。再構成の機械検証結果: `/tmp/pr86-sysspec117-observer-reconstruction.json`。
