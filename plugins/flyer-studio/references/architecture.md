# 責務と正本

入口の地図は root の [SKILL.md](../SKILL.md)、工程の順序と戻り先は [workflow](workflow.md)。この文書は、skill ごとの責務の境界と、どの情報をどこで一元管理するかを示す。6 skill が既存の agent・reference・知識・schema を使って、判断・制作・独立評価・学習を分担する。local agent がある段階はその担当が、無い intake・learn は呼び出された AI が実行する。共通の判断手順と資産の使い分けは [stage-common](stage-common.md#共通の判断手順) が正本。

## 6 skill の境界

| skill | 責務と成果 | 固有資産 |
|---|---|---|
| run-intake-flyer | AI が資料の意味と出典・不足・様式候補を判断し、一括質問と回答検査をコマンドへ渡す → brief.json・intake.json・style-proposals.json・essence-baseline.json | interview-guide、[intake-questions.json](intake-questions.json)、intake.cjs・essence.cjs |
| run-analyze-flyer | 元画像は read-only。現物診断・保持点・候補・採否理由と、別担当へ渡す未判定台帳の準備 → analysis.json・analysis-review.json の雛形 | artifact-analyst、analysis-contract |
| assign-flyer-analysis-review | 生成済み台帳へ評価を記入。提案の独立 PASS/FIX と本質条項に結ぶ根拠 → analysis-review.json | analysis-evaluator、evaluation-contract |
| run-create-flyer | 採用案の実装、意図・要求と実要素の対応、新 PDF/PNG・機械検査・finalize | flyer-producer、production-contract |
| assign-flyer-review | 評価のみ。新画像の 5 観点と要求ごとの充足 → visual-review.json | visual-review-coordinator、review-contract |
| run-learn-flyer | 機械が納品完了案件を記録・集計し、AI が根拠・反例・限界を解釈して改善仮説と次回の参考値を返す。規範は自動変更しない | learn.cjs、知見台帳 |

評価テンプレートの生成・再発行と履歴保全は呼出側の準備、評価者の直接編集は生成済み台帳の判定記入に限る。コマンドの付随更新は [stage-common の所有規則](stage-common.md#所有と機械による付随更新) に従い、自由な上流変更や履歴編集には広げない。

完成評価の統合担当は visual-review-coordinator。構図・文字・色の専門 3 役は既定では呼ばないレンズで、完成評価では [design-contract.json](design-contract.json) の expertEscalation（昇格条件。機械の正本）に当たった案だけで呼ぶ。他の stage で呼ぶ条件と呼ぶ側の責務は [stage-common の専門レンズの共通規則](stage-common.md#専門レンズの共通規則) が正本。呼ぶ条件はこの 2 点だけで決まり、review-rubric の評価コストの原則のうち専門レンズの行（R3）は同じ条件を指す参照なので読み飛ばしてよい。同節の評価対象の範囲（E5）と読む知識の絞り方はそこが正本。専門の本文は top-level の agents に 1 つだけ置き、stage ごとに複写しない。評価者は修正しない。

利用者の実行許可と、別担当による品質の判定を混同しない。案ごとに承認の質問を挟まない。新しい要求や事実の変更は、該当する上流 stage 以降の成果を失効させる。

## 一元管理の地図

| 正本 | 一元管理するもの |
|---|---|
| [essence.json](essence.json) | 本質（E1〜E5・R1〜R4・nonGoals） |
| [workflow.md](workflow.md) | 工程の順序・各 stage の入出力・FIX の戻り先・改善 cycle の意味 |
| [design-contract.json](design-contract.json) | initDefaults・cycleBudget・expertEscalation・reviewPolicyFiles・analysisPolicyFiles と、観点・担当・キー |
| [design-knowledge-index.json](design-knowledge-index.json) | 指針 ID（DD）の参照先・読み込み条件・usedBy（どの stage と観点が使うか） |
| [intake-questions.json](intake-questions.json) | ヒアリングの質問と must-fact |
| [plugin-composition.yaml](../plugin-composition.yaml) | 部品の登録と呼び出し関係 |
| [package-contract.json](package-contract.json) | 配布の検査条件 |
| [`references/presets/<name>/`](presets/) | 案件固有の値と知見。選択した preset.json の knowledgeFiles から読む |
| [examples](../examples) | 特定の案件に依らない架空の brief・scene の形の見本（init は読まない）。preset 固有の見本は各 preset.json の briefExample（preset 付き init の下書き）と sceneExample が指し、汎用の見本と置き場を分ける |
| [stage-common.md](stage-common.md) | 6 skill の共通判断手順・所有とコマンド副作用・知識の選び方 |
| [runtime.md](runtime.md) | コマンドと案件 dir のファイル |
| [review-rubric.md](review-rubric.md) | 見る順序・5 観点の物差し・評価コストの原則 |
| [design-rules](design-rules.md)・[designer-knowledge](designer-knowledge.md)・[style-profiles](style-profiles.md) | 制作判断と明示制約・一次資料の知見と適用限界・様式の記述軸 |
| [schemas](../schemas)・[scripts](../scripts) | 入出力の型と実検査（分析承認・描画・測定・QR・鮮度・結合） |
| `${FLYER_STUDIO_HOME}/ledger` | 知見台帳（plugin の外に置く） |
| 案件 dir | 今回の目的・事実・権限・要求・採否理由・意図・座標・書体と、stage ごとの評価物 |

提案の PASS と完成画像の PASS は別の評価物で、互いに代わりにしない。

## 描画経路の区別

plugin の scene から描く経路と、plugin 外の描画経路は別物として扱う。成果には renderer・source・output の対応を明記し、plugin 外の経路の成功をこの plugin の実行証拠にしない。未承認の試作や development-plan・旧 verification の履歴を、今回の完成の根拠に転用しない。
