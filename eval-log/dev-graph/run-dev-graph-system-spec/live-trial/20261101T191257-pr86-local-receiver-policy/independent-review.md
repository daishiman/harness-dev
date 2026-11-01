# sysspec115 独立評価

**FAIL**。起動・canonical処理・完了検出は確認できるが、C19の約束する確定仕様／architectureの取込成果が無い。C05 FAILを受けてC02を実行せずに停止したことはfail-closedとして適切だが、正のscenario受入の達成ではない。点数による判定は行っていない。

評価者: `/root/review_sysspec115`。対象は `20261101T191257-pr86-local-receiver-policy` の今回の一次資料のみ。過去trialのtranscript/verdict/独立レビューは未読。source/fixture無編集。Dは当該live-trialディレクトリ、以下のpathはD相対。

## 一次証拠の再構成と保存

凍結rawのmain＋6 subagent、合計7streamを独立パーサで走査し、UUID重複を除去、矛盾UUID／tool ID曖昧性・call/result順序・observer自己I/O除外・真正Skill注入metadataを照合した。178eventは全件同一、indexの全summary・source line・prefix byte数／SHAも一致、未列挙event0。7stream全体の観測SHAも一致した。Agent結果はobserverの対象外なので、native transcriptの子prompt・tool call/result・最終応答と台帳を別途照合した。thinking/api-request-blob/replayを実行証拠に数えていない。

公開main SHA: `3e6abfd67eb8223a9aac7f0f098505e98452abb5071b781ab4e909cbd351c0bd`。
原本main SHA: `398aec4eade906ed6c30b1d4b891cf2d6b7451e7f4685a54a8c44089e506bd22`。

匿名化manifestの7fileを原本と直接比較し、同一のメール値を `<redacted-email>` に置き換える31回だけで公開bytesへ一致し、行数不変を確認した。SequenceMatcherの93断片は１置換を３断片へ分けたもので31回と矛盾しない。pollはelapsedのみ1313→1314、`ceil(observed_at_unix-started_at_unix)=ceil(1313.681890964508)`。元／公開pollのSHAは記録と一致し、予算変更無し。project指示・at-collection・最終CLAUDE.local.mdの3つは同一SHA `133f322104bc3150cfd47cf0dc5184ef9360e8ccb0dbc7d2babe2a8811a4f9bd`。

計測tokenは11,001,380（assistant message ID127、全7file、usage欠損0）／上限23,000,000。wall-clock1314秒／3300秒。`poll DONE`とnative `DONE: FAIL`は両立する。transport smokeは今回のacceptance証拠に数えていない。tmux reaperは評価者が実施していない。

## 元３観測と正本criterion

| 観測 | 実観測 | 判定 |
|---|---|---|
| 1. the declared system-spec-harness plugin is loaded and its canonical flow completes | pin版0.1.24の4entrypoint検査。C19/elicit/compile/C05の本物のSkill呼出し。doc-fetchは正規出典gateと対象状態から不要判断。compile CLIは実行された。しかしC05はFAILで、canonical取込flowは完了しない。 | FAIL |
| 2. the imported specification and architecture retain source lineage and evaluator evidence | graph_revision=0/nodes=[]。C02 Skill／writer登録も新しい取込receiptも無い。保持すべき取込nodeが存在しない。 | FAIL |
| 3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph | 迂回登録・自作compiler・同等ヒアリング複製は観測しない。ただし登録自体0件なので、正のC02登録経路の実証にはならない。 | 未達 |

IN1正本: **system-spec-harnessのcoverage/source citation gateとdev-graph schema gateがすべてexit0になる**。周回1は `main-toolu_018qR1fyVckn3bukzXo17ydD` のG1/G2/G3が全0、周回2は `main-toolu_01HALkEvNMrWGMxDv4ZFHUJP` の&&連鎖がexit0。各後にIN1を記録。空graphのschemaも省略せず実測した。IN1はPASSで、成果取込やevaluator PASSへのproxyにはしない。

OUT1正本: **仕様書/architecture要求がsystem-spec-harness成果物をsource lineage付きで引用し、同等ヒアリング/compileロジックがdev-graph内に複製されていないことを受入テストが確認する**。引用node・lineage付き取込成果が無くFAIL。

## C19／C02の境界

C24固定receiptを保存し、親の各Bashは固定root前置きで本処理を行った。R0/R1の独立Verifierは別contextでsource／receipt／現物を読み、実完了のPASSを返している。各周回の親集約ログ、6必須キー、original_goal/hash不変、append-onlyの2行、周回2前の直前指示読込を確認。共有goal evidence validatorも違反0。OUT1はexternal_pendingを保ち、R2/R3を未検証のままachievedにしていない。

compileは入力3gate→正規compiler→現物path/digest/lessによる提示→別callでstandard記録→scratch隔離の63test→helper成功args無改変でC05という順序。scratch成果を取込元にしていない。C05 FAIL後はC02を起動せずpayloadを書かず、givenのcandidate-importもbyte不変。C02のpre-choice登録／baseline／integrity監査／lineage/evaluated_digestは未到達であり、成功済みとは扱わない。入力state・refs・Markdown全体はgivenと同じbyteで、追加利用者承認・仕様差替えは観測しない。

## C05の実態と追加の不足

C05は本物のfork。自身のSKILL、R1/R2、rubric/criteria、評価器resource-map、schemaを全文取得した。全10Markdownとstate/refsも、途中のRead切れを追加取得して全行揃えた。Step0 snapshotは12artifact／全10Markdownの最終SHAと全件一致し、旧評価へ新入力を混ぜていない。

ただし、C05 Step3/R1-scoreが直接の設計知識照合元に指定する **C04 `ref-system-design-knowledge/references/resource-map.yaml` は当該contextで取得していない**。全Read/Bash/Skillの実記録にも全文が無く、C05自身のresource-mapやcompiler内部での機械読込、章に注入された参照をC04索引の直接読込に数えない。設計知識反映をsourceどおり評価し切ったとは認められない。

保存はC06 `hearing-audit.json` と引数outputのreportの２件だけ。両方ともliteralのPath＋stdin.read＋引用heredoc、本文は妥当JSON。C06 JSON部は最終応答の部分文字列と逐語完全一致。自作report builder/scriptの保存実行、仕様書／台帳の手書き、report PASSへの書換え、resume receipt自作は無い。正規aggregateのexit0を独立再検証したが、これはFAIL reportの形状／整合／帰属の受理である。

一方、C05のsourceは `Bash(python3 *)` と、R1-score 4.3の検証script／許可出力への限定を明記するが、実際のC05は `cat/ls/find/grep/wc/tail/cut` をBashで使った。例は `subagent_agent-adc371c3e200ef423-toolu_01KS9KUpt9RzMqZj3w3f7snX`、`…-toolu_01GqM8JaN7ifHwJ8VYi57qkT`（`find /`）、`…-toolu_019MbRePwrSr2oEkZbAfFC97`（監査outputのtail）。許可JSON保存が正しくても、明示CLI境界との差分は残る。

設計知識の意味層では、新O1/D4要件の問答自体は章へ逐語で載るが、章固有の適用・doctrine・原則採否は従前QA中心で、outboxの原子性・claim/lease/fencing・失敗job／30分超未処理の運用要求へ十分に接続していない。少なくともC05 PASSを得ておらず、この不足は解消していない。**同じ原則を二QAへ使ったこと／schema1.0でprovenance nullという事実だけは違反としない**。また「通知表示」はWeb画面への表示とも読め、外部メール等追加との矛盾をその語だけで断定しない。C05が提案するqa_refs描画拡張は、現行C03の主qa_ref中心の生成契約に対する改善提案として区別し、未宣言の必須要件にしない。

## ３監査の実完了と帰属

C07→C06→C08は、各前件completion後に次件dispatchする直列。モデルは明示background/nameを指定しておらず、ホスト自動async受理を最終結果とみなしていない。task.mdがこのhost挙動を明示的に扱っているため、自動async自体を追加失格理由にしない。

| 監査 | dispatch | completion | native再接地 |
|---|---|---|---|
| C07 | 10:21:59 | 10:22:51 | prompt/child prompt/token/tool ID/session/最終本文SHA/verdict全一致 |
| C06 | 10:24:50 | 10:26:03 | 同上。保存JSON逐語一致。再導出PASS、blocking0/notes4/closed1 |
| C08 | 10:26:46 | 10:27:41 | 同上。SSOT R4とcatalog全文、5許可hostへ計6WebFetchを実施、Kubernetes末尾を追加取得 |

3件ともschema1.2 pending dispatch＋schema1.3 resolved completionの正しいjoinで、receiptはcompletion本文digest。別の内部completion1行はabsent／subagent_type=nullでreceiptへ流用されていない。C06はmatrix sub-input、C07/C08は各primary、C05自前4観点への虚偽primary receipt無し。C06が書面でなく合成対話sourceのcanonical U索引を使うschema1.0 fallbackも維持している。C08起動adapter本文はnative prompt_snapshotから載り、R4/catal​​ogは自身が実Readしている。新しいWeb照合は今回の実行I/Oとして扱い、現実世界の現行版をこのレビューが保証するものではない。

## 全18promptの意味評価

実Read応答の番号付き各行をsourceと照合し、18件全件で欠落0。C05 reportのprompt_quality.evidenceも18件が各C1-C4を具体的に扱う。外部prompt-creator不在のstandalone例外は機械gateだけに使われ、18件の意味評価を省いていない。次表は評価者がsource本文から確認した意味上の根拠である。

| prompt | 独立に確認した内容／限界 |
|---|---|
| C05 R1-score | 判定ルールと6観点・保存境界を分離。snapshot→実証拠→再導出とL7が一致。停止checklistあり。実走のC04索引未読はprompt本文の欠陥とは別。 |
| C05 R2-delegate | 監査ロジックをSSOTへ委譲、C06の判定再導出・token／台帳・逐語保存を規定。L7はL1と整合。 |
| C04 R1-system-design-knowledge | seed上限を設けず知識の目的・適用／非適用・trade-offを返す。再現性は固定入力と参照集合に依存し、外部探索を無条件な同一出力とは扱えない。 |
| compile R1-assemble | 真理値表・カテゴリ順・先頭要件章を決定論ヘルパへ接地し、7停止条件へ対応。 |
| compile R2-render | topo順・doctrine・章の具体適用と原則採否・unrecordedを明示。qa_refs全解釈の描画は現行契約で明示されず、追加提案と区別。 |
| compile R3-crosslink | index/全章/状態/goal参照の一貫性が達成状態と7checkに対応。 |
| doc-fetch R1-identify | spec-state由来の対象同定に限定、抽象方針混入／重複／ゼロ件根拠／候補追跡を検査。 |
| doc-fetch R2-fetch | 公式資料・実時刻・digest・未取得理由を分離。再現性は同じ公式snapshotという条件付きで適切。 |
| doc-fetch R3-record | canonical assembler・全件対応・時刻非捏造・散文版ドリフトを出力とchecklistへ接続。 |
| doc-fetch R4-audit | C13形式と公式再照合を二層化、未確認を可視化しread-onlyとmarkerの停止条件が一致。 |
| elicit R0-foundation | U1-U9／source-index／承認／canonical履歴とeffectiveを分離、writerとN1-N4がL7まで接続。 |
| elicit R1-init | taxonomy SSOT・6platform・初期状態・導出集約を4checkへ接地。 |
| elicit R2-interview | 未収集のみ、論点別逐語、required-info候補gate、qaの結付けと正規writerを明示。 |
| elicit R3-reask | chunk上限／未完了／next_question／依存順を分け、再開できる状態を客観停止条件化。 |
| elicit R4-reopen | 実測時刻・参照結直し・追記opとの区別・独立再確認を規定、状態保全とL7が一致。 |
| elicit R5-decision-guide | 比較／推奨／中立な選択／確認待ちを分離し5比較軸と20checkへ接続。writer CLI詳細は共有state契約を参照する余地があり、本文単体の補足提案は可能。 |
| elicit R6-audit-hearing | 5軸／重大度／active consumer／置換の意味判定と別途の合否導出を分離、構造化findingsとmarkerが対応。 |
| elicit R7-audit-matrix | loop/finalの機械＋意味の二層、理由／trace／集約／platformを網羅。l5-contract文字列の有無だけで意味構造の不合格にはしない。 |

## 最終blocker

1. C19の確定仕様／architectureのC02取込が無く、観測1・2とOUT1未達。
2. C05がFAILで、章の新O1/D4への具体的な設計適用不足が未解決。
3. C05自身のC04設計知識索引の直接読込・照合が未実証。
4. C05の明示CLI境界と実Bash操作に差分がある。

以下に、実値を見る前にsourceだけで決めたHC global schema／C19ローカル契約の適用根拠を全文保持する。

---

# C19 の goal-seek 契約適用範囲（source-only 独立確認）

対象 source root: `/Users/dm/orca/workspaces/harness/pr86-ci-fix`

本確認では今回の実走 raw、過去 trial の transcript・verdict・独立レビューを読んでいない。特定の実値や期待判定は入力されていない。source・fixture は編集していない。

## 結論

C19 の実走判定へ、harness-creator（HC）の全文 `goal-seek-loop.schema.json`・`drift_signal` の６値 enum が自動継承される参照経路は確認できなかった。C19 が本文・common・共有機械 gate に明示するローカル契約を必須として評価する。

## 一次 source 上の根拠

1. `plugins/dev-graph/skills/run-dev-graph-system-spec/SKILL.md:48` は停止条件と配線の正本を自身の `## ゴールシーク実行` と宣言する。frontmatter の `reference_refs` は `../../references/prompt-common-layers.md` であり、`schema_refs` は `../../schemas/graph-node.schema.json` である。本文144行目以降は、６必須キー（`original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal`）・hash一致・append-only・次周回の直前指示消費・各周回３ゲートを宣言する。common (`plugins/dev-graph/references/prompt-common-layers.md`) も HC schema・enum を参照しない。

2. `plugins/harness-creator/skills/run-skill-live-trial/scripts/validate-goal-seek-evidence.py:31` は、被験 SKILL の「ゴールシーク検証」節と同じ検査を外部強制する位置付けを明記する。実装が検査するのは３成果物の実在、非空 intermediate、６キー、goal-spec の非空 original_goal、各行の original_goal/hash 一致であり、enum・全文 schema 検証は実装されていない。

3. HC の `plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md:84` は生成スキルの周回状態を全文 schema 準拠とし、同105行目および `schemas/goal-seek-loop.schema.json:122` は drift_signal の６値 enum (`initial/aligned/compressing/stagnant/widening/oscillating`) を定義する。これは生成規約上の契約である。

4. `templates/combinators/with-goal-seek.patch` 冒頭と `scripts/render-combinators.py:984` 以降によれば、`with-goal-seek` は生成時の renderer が frontmatter・配線本文を注入する指定である。frontmatter の combinator 宣言だけで、実行時に HC 文書全体を読み込む機構ではない。C19 本文には HC 全文 schema 準拠・６値 enum の注入文がない。`behavior_closure_files()` による C19 宣言済み挙動閉包にも当該 HC 文書・schema は含まれない（閉包175ファイル、SHA-256 `ebec0c4771f30cd2be8260f9871ad0e4d42112e7f03ebed8c04a0326bf13a5ef`）。

5. 全文 HC schema をそのまま重ねると、C19 が明示する checklist の `achieved/not_achieved` と `evidence` に対し、HC schema は `pending/done/blocked` と checklist item の `additionalProperties:false` を課すため衝突する。両者を無条件に同一の実行契約として適用できない。

## 実走評価時の扱い

- C19 自身の明示契約・common・scenario・live-trial が定める必須 gate と、実際の意味的履行を必須とする。
- HC enum 外という理由だけで C19 の blocker にしない。
- 空・無意味な drift_signal、実際の goal drift、アンカー未消費、６キー/hash不一致、append-only違反、必須独立検証・各周回 gate 欠落等は C19 の局所契約に基づいて判定する。機械 gate の通過だけで意味的履行を代用しない。
- HC 生成規約との整合不足は、実走時の未宣言契約違反と分けて扱う。

本書は適用範囲の source-only 確認であり、sysspec115 の PASS/FAIL 判定ではない。
