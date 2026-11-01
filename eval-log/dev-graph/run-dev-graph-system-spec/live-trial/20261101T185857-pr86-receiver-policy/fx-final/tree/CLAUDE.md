# 実走fixtureの共通実行契約

これは公開system-spec-harness 0.1.24とC19の既存契約を各独立contextへ届けるプロジェクト指示であり、判定基準・権限・予算・資料を変更しない。過去の評価結果は今回の判断に使わない。出力は日本語とする。

各Skill/Agentは担当の出力を作る前に、このCLAUDE.mdをReadし、自分のSKILL.md・起動adapter・責務prompt・必読SSOTをfrontmatterも含め全文取得する。親のReadや親の会話を、自分が読んだ証拠と数えない。内容がツール上限で欠けたら残りを取得し、見出し/先頭/grep/存在確認で意味評価を代用しない。sourceが許すtool/CLIと読取専用境界を守り、sourceやguard/この指示を編集しない。

C05 completeness evaluatorでは、R1-scoreとR2-delegate、scoring-rubric.json、aspect-criteria.md、resource-map.yamlと指定schemaを全文取得し、spec_dir内の全Markdownとstate/refsを意味評価する。設計知識はC04 mapと各章の確定要件への具体適用を照合する。3監査の実completion/台帳が揃うまで合格にしない。

C05のprompt_qualityは、plugins/system-spec-harness/skills/*/prompts/*.mdの全18件が対象。全件のC1-C4（Layer役割、L7からL1への整合、再現性、Self-Evaluation）を、この独立contextで内容を読んで意味評価し、既存schemaが認めるsummary/findings等にprompt別の実根拠を残す。R1/R2だけの標本評価・機械validatorの形状PASS・既存レビューの存在確認で残りをPASSにしない。外部prompt-creator未導入時のstandalone例外は機械gateだけで、意味評価の免除ではない。未実施/根拠不足なら通常どおりINDETERMINATE/FAILを返す。期待する判定や点数は指定しない。

C05の保存境界はR1-score 4.3/R2-delegate 2.4どおり。書けるのは許可されたhearing-audit.jsonの無改変保存と引数outputの評価レポートだけ。Write/Edit、catリダイレクト、heredocでのPython script生成、scratch/tmpへの自作report builder保存・実行はしない。レポートはpython3 -cでliteralのpathlib.Pathへsys.stdin.read()を無改変保存し、引用JSON heredocに妥当なJSONだけを渡す。正規検証CLIを使い、レポートやreceiptの自己緑化をしない。既存sourceの正常なliteral保存先修正は可能。

C06/C07/C08は起動adapterだけで責務が完結したとみなさず、adapterが指す責務SSOTと必読資料を全文取得する。C08は出力前にskills/run-system-spec-doc-fetch/prompts/R4-audit-doc-freshness.mdを必ず読み、R4 Layer3が指定する公式source catalog等を読み、公式サイトの実再照合を行う。未読SSOTがある状態で監査PASSにしない。sourceにない新しい許可・検査免除は設けない。

C19親は固定C24 root、各周回3CLI実測後のIN1、6キー/hash、親が所有する集約ログ、責務Verifierの実完了を守る。C02は評価済み内容のみを正規single writerで登録し、pre-choiceの実成果提示と選択/baseline、source lineage/evaluated_digest/readiness、独立整合性監査を守る。途中で人に追加判断を求めず、実際の失敗は失敗として完了markerに記す。
