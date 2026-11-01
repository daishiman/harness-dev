# 実走fixtureの共通実行契約

これは公開system-spec-harness 0.1.24とC19の既存契約を各独立contextへ届けるプロジェクト指示であり、判定基準・権限・予算・資料を変更しない。過去の評価結果は今回の判断に使わない。出力は日本語とする。

各Skill/Agentは担当の出力を作る前に、このCLAUDE.local.mdをReadし、自分のSKILL.md・起動adapter・責務prompt・必読SSOTをfrontmatterも含め全文取得する。親のReadや親の会話を、自分が読んだ証拠と数えない。内容がツール上限で欠けたら残りを取得し、見出し/先頭/grep/存在確認で意味評価を代用しない。sourceが許すtool/CLIと読取専用境界を守り、sourceやguard/この指示を編集しない。

C05 completeness evaluatorでは、R1-scoreとR2-delegate、scoring-rubric.json、aspect-criteria.md、resource-map.yamlと指定schemaを全文取得し、spec_dir内の全Markdownとstate/refsを意味評価する。設計知識はC04 mapと各章の確定要件への具体適用を照合する。3監査の実completion/台帳が揃うまで合格にしない。

C05のprompt_qualityは、plugins/system-spec-harness/skills/*/prompts/*.mdの全18件が対象。全件のC1-C4（Layer役割、L7からL1への整合、再現性、Self-Evaluation）を、この独立contextで内容を読んで意味評価し、既存schemaが認めるsummary/findings等にprompt別の実根拠を残す。R1/R2だけの標本評価・機械validatorの形状PASS・既存レビューの存在確認で残りをPASSにしない。外部prompt-creator未導入時のstandalone例外は機械gateだけで、意味評価の免除ではない。未実施/根拠不足なら通常どおりINDETERMINATE/FAILを返す。期待する判定や点数は指定しない。

C05の保存境界はR1-score 4.3/R2-delegate 2.4どおり。書けるのは許可されたhearing-audit.jsonの無改変保存と引数outputの評価レポートだけ。Write/Edit、catリダイレクト、heredocでのPython script生成、scratch/tmpへの自作report builder保存・実行はしない。レポートはpython3 -cでliteralのpathlib.Pathへsys.stdin.read()を無改変保存し、引用JSON heredocに妥当なJSONだけを渡す。正規検証CLIを使い、レポートやreceiptの自己緑化をしない。既存sourceの正常なliteral保存先修正は可能。

C06/C07/C08は起動adapterだけで責務が完結したとみなさず、adapterが指す責務SSOTと必読資料を全文取得する。C08は出力前にskills/run-system-spec-doc-fetch/prompts/R4-audit-doc-freshness.mdを必ず読み、R4 Layer3が指定する公式source catalog等を読み、公式サイトの実再照合を行う。未読SSOTがある状態で監査PASSにしない。sourceにない新しい許可・検査免除は設けない。

C19親は固定C24 root、各周回3CLI実測後のIN1、6キー/hash、親が所有する集約ログ、責務Verifierの実完了を守る。C02は評価済み内容のみを正規single writerで登録し、pre-choiceの実成果提示と選択/baseline、source lineage/evaluated_digest/readiness、独立整合性監査を守る。途中で人に追加判断を求めず、実際の失敗は失敗として完了markerに記す。

## C05 の明示ツール境界と索引
C05自身はfilesystem本文・索引・promptをReadで取得する。C05がBashを使えるのはpython3で正規の検査CLIを実行する場合と、R1-score4.3のliteral保存だけである。C05でcat/ls/find/grep/sed/head/tail/wc/awk等のshell調査を行わず、python3 -cの自作探索/reader/報告builderにも置換しない。CLIと入力/出力は絶対パスで渡し、Readで必要な本文を揃える。検査のstdoutやsnapshotをtmpへredirect保存せず、artifact_snapshot/gate_resultsには正規CLI応答をそのまま使い、保存先は許可2JSONだけとする。standaloneで外部PCが無ければsourceの機械gate例外だけを正確に記し、root全体/別repoの探索をしない。
C05が必ず全文ReadするC04索引は plugins/system-spec-harness/skills/ref-system-design-knowledge/references/resource-map.yaml である。C05自身の references/resource-map.yaml とは別物であり、両方を読む。各章の原則採否とC04 mapの対応・新要件への具体適用を自前で検証する。
次はsourceから列挙した18promptの入力inventoryだけであり、評価済み/合格を意味しない。各fileは自分で全文ReadしC1-C4を意味評価する。
- plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/prompts/R1-score.md sha256=ef674d2766f992048676482ad8d671440966a21df20898014c4e19ad8e488c43
- plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/prompts/R2-delegate.md sha256=030f8c2da816b0fd46a835e1f8d05c7d9e1d09c4624cd97f02c37a9b94b90309
- plugins/system-spec-harness/skills/ref-system-design-knowledge/prompts/R1-system-design-knowledge.md sha256=a2953c59442019e0174a6bdbbe4b1efd7ea14fe3286c4b3e4c4565f76470f538
- plugins/system-spec-harness/skills/run-system-spec-compile/prompts/R1-assemble.md sha256=e826d94dafcbddb9296a22c08132f8cb44d5a02bce06e022673222ee51eb1eb6
- plugins/system-spec-harness/skills/run-system-spec-compile/prompts/R2-render.md sha256=f111f404b3df1f684571efa90b9ca3406c943be1fa5aa49326ab4f9444f038b5
- plugins/system-spec-harness/skills/run-system-spec-compile/prompts/R3-crosslink.md sha256=894783fe8485bf5d382230fc6817661507b2ddc5cc29315117d8b99453c6b664
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R1-identify.md sha256=f5b6ef403f0ffca13adaf78a80a6d990cb6529d408eb1a5cb436502712d8404d
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R2-fetch.md sha256=c74acafdc2abed1141cdc26f7f4a42b7d0062556e5168588f72e46da4b7587d5
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R3-record.md sha256=df225877a020e1fada8e98b0566373267bdb58614de96bca72cd7339e5e09e28
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R4-audit-doc-freshness.md sha256=3fb7ee09926bff77cba880f07bd929242012fea0d08af2a6a0a1b94ebb742501
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R0-foundation.md sha256=6504ed986790f356c898a296e1c819631305d7e663f44168c4aa9b428597cd83
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R1-init.md sha256=0c680368e000645b74dab2c62852adbdb78458bf68e348597ada3875ee83bf6f
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R2-interview.md sha256=6dbe8048720b950e17daac8425a44a295c9c2255e0293ec315e04323facac084
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R3-reask.md sha256=16ad7f236badf040ffbc9ac790871b17dc7b7cc4c69523c1f606b2a6e2bed9b8
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R4-reopen.md sha256=113078305c2284c6b7e61867534b78da3a30272f5c8800b5a5760872b0cb4fca
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R5-decision-guide.md sha256=e53d1dff697e2a5cb034e6487f32f4b10121867032fd47c3d20746f143db37d9
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R6-audit-hearing.md sha256=9521a9048ef144a307ee50508dc16895b86c105a1891a6d805669b3fa82f2e83
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R7-audit-matrix.md sha256=ab3562ed3d238504886b95c17942cda95c92d8e4900755994860ad47cff8cdac
