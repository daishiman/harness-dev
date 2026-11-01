# sysspec104 独立 goal 評価

**FAIL**。必須 R2-delegate 独立検証が2回とも FAIL で、C19 checklist 3 は `not_achieved` のまま終了した。今回の task は未達の残る run を PASS にすることを明示禁止している。2 node の成果が成立したことから、この native FAIL を反転しない。

評価者は `/root/review_sysspec104`。開始前は正本と scenario のみを準備し、完走収集の指示後に今回の frozen raw を初めて読んだ。過去 live raw は読んでいない。source/W は変更していない。

対象 D: `/Users/dm/orca/workspaces/harness/pr86-ci-fix/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261101T105704-pr86-freshness`

公開 `transcript.jsonl` SHA-256: `5b19158c84dbbea7a2fb2308f752f26bde820921429c0236e2aa4cbad2e53226`。原本 SHA-256: `ec0124997e9788d2b36586fc89798922c3137d1369fbdd12b4d92b20fea5c942`。

## blocker と R2 根因

blocker は必須独立検証への証拠受渡し不足である。初回 verifier が拒否された3項目について、外側の fresh evaluator は以下の先行一次入力・出力を照合できた。

| R2 の未達項目 | 今回の先行一次観測 | 分類 |
|---|---|---|
| 63: 本処理ごとの固定 root 移動・照合と scratch 隔離 | 親 transcript L151/L188/L207/L229/L259/L265/L270 等の実 Bash に receipt の root の literal export、cd、pwd -P 照合がある。L265→266 の正規 compile は exit0 で10 file生成。L281→282 は許可絶対 scratch を cwd/basetemp にした63 passed、末尾 diff の拒否は L286→288 の cmp で caller unchanged を再確認した | 本処理の実施を裏付ける一次証拠あり。verifier への handoff が無い |
| 64: 毎回 CLAUDE_PROJECT_DIR export | 上記本処理 Bash の tool input に実在し、開始 C24 receipt の repo_root と一致する | 不実施という検出ではない |
| 67: 委譲先 SKILL/prompt 全文取得 | Skill の host 注入に各本文がある。C19 R0-R3 は L60→66 の全出力、elicit R0-R2 は L158 の persisted output を L170→171 で全文 Read、R3/R4/R5 は L172/174/176。doc-fetch R1-R3 は L212→218、compile R1-R3 は L247→248 の完全な出力。各全文を被験 source と直接照合して一致した | 実際の全文取得はあるが verifier が参照できない |

初回 R2 verifier (`transcript/subagents/agent-a33aac9c0aad61499.jsonl` L79→80) は global `.claude/projects` の当該 session transcript を探索し、隔離 guard に拒否された。その時点で手順違反を発見したのではなく、receipt に root-prefix/全文取得の機械記録がなく独立に確かめられないため FAIL とした。

親の `process-attestation.json` はその後 L674→675 で作られた。内容は `self-report ... not machine-recorded` と明示されており、それ自体を先行動作の観測証拠にできない。再検証者 (`agent-a5daec78203d87c4d.jsonl`) はファイル実在・hash・scratch・配置を確認したうえで、過程を証明しないとして3項目の未達を維持した。これは source の「親の自己申告だけで閉じない」に沿う。

補足ログの内容は、固定 root・Skill 呼出し・prompt 内容の取得・scratch・ハングについて実際の先行呼出しと整合する。ただし `prompts_read_in_full_with_Read_tool` という名称は不正確で、doc-fetch/compile は native Read ではなく Bash cat の全出力で取得している。親にはその Bash が許可されているので、取得内容の全文性と道具名の誤記を区別する。自己申告に tool という名称を付けても機械証拠にはならない。

## 重点契約の一次照合

| 契約 | 実観測 |
|---|---|
| C24 と root 固定 | L84→85 で write receipt を保存。repo_root/content_roots.repository 一致、caller 内 system_spec。開始 lineage checked0、空 graph の新規取込。helper L433→434 exit0 の skill_args と C05 L508 の args は完全一致。評価先 spec_dir/report も同じ root |
| 選択前境界 | preflight を提示し standard を記録してから後続へ進行。compile も path/digest/開き方を L265→266 に提示し、別 L270 呼出しで standard を記録した後に tests/C05 |
| 正規4 Skill | elicit L138、doc-fetch L194、compile L234、C05 L508。elicit は完成 state の resume、doc-fetch は既存4 record充足・discovered0の not_required、compile は正規 compiler を実行。state/ref の preflight digest と原本最終 bytes が一致し、追加 QA/承認は作っていない |
| C05 真 fork・道具 | forked-skill sidecar と `agent-a9ee0b801353eefd7.jsonl` に別 context の実行。実作業は Read、Python Bash、Agent。cat/grep/find/ls/tee/Write/Edit/TaskStop/TaskOutput の実使用なし。R1/R2 を最初に全文 Read。Python は正規 gate、読取検査、許可 JSON 保存であり、自作 writer/evaluator による正規 Skill 置換ではない |
| C07 | `agent-a0eacacc983d0377d.jsonl` の実 tool は Read のみ。R7/C12/taxonomy と state 全1801行を分割して Read。48 cell を5軸で意味監査。初回 C12 loop/require-complete の exit/stdout/stderr、state/validator path/SHA を C05 L52→53 で実測し、L59 の prompt 内 JSON は無改変一致 |
| C06 | `agent-acd3c051063eeca8e.jsonl` は Read のみ。R6/中立基準/state全文/aspect-criteria を Read。正規 hearing-sources の全 JSON を L107 prompt に無改変転記、snapshot state SHA と一致。written QA0なので安全性確認後の書面section読取は N/A。5軸・supersession・active consumer の意味監査を実施し、その JSON を hearing-audit.json に改変なく保存 |
| C08 | `agent-a332e23105a14aa36.jsonl` は Read と WebFetch のみ、Bash/WebSearchなし。R4/catalog/references/targetsを Read。C05 L52 の C13 実 argv・全 inputs/validator path/SHA・exit/stdout/stderr と L163 prompt の doc_verification は全 JSON 一致。4 target を許可公式4 hostで独立再照合。FastAPI冒頭10万字という範囲は明示され、最新番号の確認結果と到達不能を混同していない |
| 入力安定性 | L52 の全入力/validatorの取得前後 hash は STABLE True。snapshot state SHA=9c14364c...。C05 L235→236 は監査後に snapshot 全一致、C12両mode、C13/HS exit/stdout/stderr、C12/C13 validator SHA を再取得し L241 で初回比較後stableとした。今回 stdout は300/400字の上限未満で実内容は切れておらず、初回の全構成値と一致する |
| 3監査の直列実 completion | C07 dispatch 02:10:09→completion02:10:43、C06 02:11:17→02:12:16、C08 02:13:09→02:13:41。各 Agent input は description/subagent_type/prompt だけで明示 name/backgroundなし。自動 Async 受理後、実 completionと台帳を待って次を起動。3 receiptの session/ID/token/verdict は対応し、response digest は schema1.3 completion に一致 |
| C02 親の必読と唯一 writer | 親 L552/554/556/558/560 が R0-R4 の全行を native Read。全出力を source と照合した。C02 Skill L688 はその後。L744 dry-run と L777 add は同一 payload SHA。receipt owner=C02/run-dev-graph-node、revision0→1。追加の graph writer や feature本文複製は検出されない |
| 2 node の lineage/評価証拠 | 原本 graph は specification/architecture 各1。confirmed/pass/readiness complete。source_version0.1.25、index.md f7f64767... と要件定義書1cc7fe6b...の実 SHA=source_digest=evaluated_digest。新規 report b39c2d94... の artifact_snapshot 12件も原本 bytes と全一致。lineage gate checked2、strict schema0、R3/必須 integrity verifier は実完了PASS |
| C19 各周回 | 周回1 L365→366 の3CLI exit0後に L381→382 で IN1、6キー、goal/hashを記録・検査。周回2 L851→857 も同順序で cov0/cit0/schema0/hash_exit0。元goal原文/hashは2行とも一致。OUT1 は自己採点せず external_pending。親集約と子責務dirは分離される |

C05 の再検証は、同形の最終 matrix_verification/doc_verification を再生成して `old == new` を機械検査する形式ではない。固定 path/実 CLI flags、snapshot の state/ref digest、validator digest、各 exit/stdout/stderr を再取得し文脈上で初回と比較している。今回は全部の構成値が一次ログから照合できるため、同形 JSON を書かなかったという形式だけを新しい確定 blocker にしない。ただし次走で全 JSON の厳密比較を明示すれば、出力の slice や手動比較を巡る曖昧さを減らせる。変化や不明を PASS にする緩和は不要である。

C05 は index/要件定義書を native Read、全8技術章を Path.rglob/read_text し、見出しと doctrine/To-Be/具体適用/原則採否を表示して自前評価した。全 Markdown の raw 全文を一括表示したわけではない。これは「全章を対象にした」という観測と区別して記録する。C08 は k8s/OIDC/GitHub Actions への言及を認識し、targets範囲の記載も残した。targets側の取りこぼしを別担当とした表現は R4 の責務境界と誤解され得るため、次走では state/candidate の既存公式証拠と target集合の網羅性照合を明示するとよい。これらの記述だけで新たな確定違反とは判定していない。

## 誤帰属と公開コピー

親 L294 の `cat > /dev/null` が stdin 待ちになり、親 L360 で TaskStop した。C05 の開始は L508 である。これは C05 の TaskStop 禁止に帰属しない。停止後は L365 で正規3CLIを再実行してから周回1を閉じており、停止した呼出しの未実行 gate を実行済みと扱っていない。

匿名化 manifest の11 fileすべてで frozen原本 SHA/公開 SHA/原本bytesを照合した。置換対象の substring を決定論的に44回置換すると公開コピーを全件完全再現でき、行数も変わらない。それ以外の frozen file は公開コピーと bytes同一で、唯一の非匿名化差分は poll-state elapsed 1862→1863。記載式 ceil(observed_at_unix - start.epoch) と1862.6210000514984秒が一致し、budget変更なし。source/state/graph/lineage/receipt digestの接地には frozen原本 bytesを使用した。草案は source_version .25、非canonical version alias・confirmation_evidence・imported_atなし、開始graph0で今回のPASSseedではないことも確認した。

## 次の正規修復への最小提案

R2 checker に global transcript への権限を追加したり、自己申告を achieved の根拠へ格上げしたりせず、**当該 run の必要な機械 tool 記録だけを fixture 内へ受け渡す**。

- trusted harness/hook が、その run/session の root固定Bashの元 tool input/output、Skill本文注入、prompt全文Read/cat出力、scratch検査を、許可された R2 evidence pathへ append-only で保存する。実 tool_use_id、session、stdout/stderr、exit、入力source digest/全文範囲を保持する。
- R2 dispatch は固定 C24 receipt と evidence path/digest を渡す。checker は同じ sandbox 内のその記録を Readして63/64/67を照合し、receipt/成果物の独立再検証と併せる。親が後から作文した process-attestation に替えない。
- 完全な global transcript のコピー、guard解除、不要な account情報の転送は要らない。被験者が上書きできる自己申告ログを機械一次証拠とみなさないことが要点。fixture許可pathと真正な tool eventへの帰属を小さく固定する。
- 同時に C05 の監査前/後 receipt を同じ関数で再取得し全 JSON 等値を明示すると検証しやすい。sourceの意味監査・公式裏取り・独立性を代替しない。

これは次の実走への修復案であり、104の結果を書換える案ではない。rootが修理を担当し、本 evaluator は sourceを編集していない。
