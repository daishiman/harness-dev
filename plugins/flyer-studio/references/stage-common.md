# stage 共通の規則

6 skill（intake・analyze・analysis-review・create・review・learn）と、その agent が共通で従う規則。AI が判断して実行する進め方はここだけに置き、各 SKILL・agent・契約には担当固有の判断と所有範囲を残す。

## 全体の流れ

[run-intake-flyer](../skills/run-intake-flyer/SKILL.md) →（既存紙面があるときは run-analyze-flyer → assign-flyer-analysis-evaluator）→ run-create-flyer → assign-flyer-evaluator → finalize → [run-learn-flyer](../skills/run-learn-flyer/SKILL.md)。段階の依存・分岐・実行許可の扱いは [workflow](workflow.md) が正本。

## 共通の判断手順

各担当は、未達を特定 → 必要な知識を選ぶ → 必要な候補だけを比較 → 根拠を持って判断 → 所有する成果物へ記録 → 検証して受け渡す、の順で進める。確認済みの処理は繰り返さず、不確実さが残る場所だけを再確認する。

- 未達は今回の目的・要求・保持点・公開条件と現物との差から選ぶ。観察事実と原因の仮説を分け、足りない事実は推測で埋めない。
- 候補比較が必要なときは、目的への効き方・保持リスク・実行可能性で必要最小限を比べ、採る理由と見送る理由を残す。固定の書体・pt・座標や担当数を正解にしない。
- 機械コマンドが担うのは型・依存・数値・鮮度の検査や記録・描画で、資料の意味・改善候補・合否根拠・集計の解釈は AI が担う。機械 PASS を意味や美観の PASS に置き換えない。
- 所有外の未達は、根拠と必要な修正を担当へ返す。評価者は対象を直さず、学習担当は仮説を返すまでとする。完了条件が満たされたら止める。

SKILL は担当の目標・入出力・受渡しを選ぶ入口。local agent がある stage はその agent が実行し、無い intake・learn は呼び出された AI が実行する。Ref（契約と判断の規則）・Knowledge（指針索引から選ぶ知識）で判断し、Schema（成果物の型）とコマンドで整合を確かめる。評価は別 context の既存評価担当へ渡し、役や管理台帳を追加して分離を装わない。

## 起点と実行形式

- PLUGIN_ROOT（plugin の最上位フォルダ）は `skills/<stage>/SKILL.md` の 2 階層上。cwd（今いるフォルダ）や旧案件のパスから推測しない。
- コマンドは PLUGIN_ROOT で `python3 scripts/build-flyer.py <command> --project <DIR>` と実行する。build-flyer.py は同じ引数を scripts/cli.cjs へ渡す入口で、コマンド実行を許可された担当はこの Python 入口を使う。専門レンズはコマンドを実行せず、受け取った画像・資料の所見だけを返す。
- コマンドの意味と失敗時の扱いは [runtime のコマンド一覧](runtime.md#コマンド一覧)、データの型は schemas が正本。pending（未判定）の台帳を自動で承認しない。

## 所有と機械による付随更新

AI の直接編集は担当の所有物だけに限る。指定コマンドには次の付随更新があり、呼び出す stage の準備・履歴保全の責務として許可する。付随更新を理由に、brief や履歴を自由に編集してよいとは解釈しない。

| 呼び出す stage | 機械コマンドに許された付随更新 |
|---|---|
| run-analyze-flyer | analysis-template が brief.analysisMode を source-artifact に切り替える。analysis-review-template が評価用の空台帳を生成し、再発行時は旧評価を cycle-ledger へ記録して reviews へ退避する |
| run-create-flyer | render・評価テンプレート生成・finalize・cycle-status が検査物・cycle-ledger・評価退避を更新する。評価テンプレートへの合否記入は別担当に任せる |
| run-intake-flyer | init・intake-apply・essence 系コマンドが案件と回答・基準・承認記録を更新する。目的・確定事実の変更は R2 に従う |
| run-learn-flyer | learn-record が許可された分類・件数だけを知見台帳へ追記する。集計と参考値の取得は台帳を変更しない |

提案評価と完成評価は、呼出側が生成した同一版の台帳を記入する。提案評価の analysis-review-validate は読取検査だけを行う。評価者は台帳の再発行や履歴の直接編集をしない。

## 記録の残し方

未達・使った指針 ID・候補の採否理由・検証結果・受渡し先は、所有する成果物の既存欄へ短く残す。型に欄がない判断は返却文へ書き、新たな共通 JSON 状態や自由記述の知見台帳を作らない。不足は現物と既存回答で補い、既に答えのある質問を繰り返さない。目的・最新要求・公開条件・画像 hash（中身から計算した指紋の値）・必要な指針が不明なら、不明のまま合格にしない。

## 本質アンカー

各 stage は判断を本質条項 E1〜E5 に結び、mandatoryFixes（必須修正）には serves（満たす本質条項の ID）を付ける。結べない好みは preferenceNotes に記録するだけにし、必須修正や cycle へ混ぜない。条項と規則 R1〜R4 の要約は [workflow の判断の錨](workflow.md#判断の錨)、正本は [essence](essence.json)。

## 戻り先と改善上限

FIX の分類と戻り先、cycle（改善の 1 往復）の数え方と停止条件は [workflow の改善と納品](workflow.md#改善と納品) が正本。premise の戻し方は同節の表と[ヒアリングの局面 9](../skills/run-intake-flyer/SKILL.md#局面カタログ)を参照する。上限は [design-contract](design-contract.json) の cycleBudget。登録簿の maxCycles と skill の max_loops は機械検査で一致を確かめる写し。知識の選択・候補比較・資料解釈など AI が判断する回数と、評価 FIX に基づく納品改善 cycle の消費は別であり、考え直した回数を台帳へ足さない。

## 深さの選択と戻り

intake・analyze・create・learn は、選ぶ前の実成果物を見せてから、現状で試す／軽微／標準／詳細のどれにするかを利用者に選んでもらう。深さが変えるのは、各 SKILL が書いた手間の量だけである。独立性・停止条件・cycleBudget は変えない。選んだ深さは型に欄が無いので、[記録の残し方](#記録の残し方)どおり返却文へ書く。

- 現状で試す（`accept-as-is`）を選んだ stage は、その場で終わる。後続の stage が読む成果物（brief.json・essence-baseline.json・PASS した analysis-review・delivery.json）は作られないので、次の stage へは進めない。進めるには、その stage に入り直して軽微・標準・詳細のどれかを選ぶ。
- 評価の FIX や premise の戻し（[workflow の改善と納品](workflow.md#改善と納品)）で同じ案件の stage に入り直したときは、直す対象の現物（パスとハッシュ値）を示し、その stage で前に記録した深さをそのまま記録する。選び直しは求めない。前に記録した深さが無い stage と、別の会話で入り直して前の返却文が読めない stage だけ、1 回選んでもらう。

## 知識の読み込み

[指針 ID の索引](design-knowledge-index.json) の usedBy が自分の stage（評価では担当する観点）を含む DD だけを候補にし、loadWhen と今の未達に合うものを読む。「索引から読む」には、その DD の path・section と relatedSections が指す関連節を含む。全件を既定で読まず、読んだ知識は今回の現物への適用理由と限界を添えて使う。一次事例と適用の限界は [designer-knowledge](designer-knowledge.md) が正本で、デザイナー本人を演じたり、本人の承認や普遍的な美の法則を作り出したりしない。

## 独立性

- 提案者と提案評価者、制作者と完成評価者は、別 context（独立した作業単位）の別担当にする。評価者は評価対象（analysis・brief・scene・画像）を変えない。全担当の結果が揃うまで修正しない。
- 返却は画像領域・観察事実・要求との対応・理由・戻り先で書き、決まり文句の褒め言葉を根拠にしない。役名や別名だけで独立を装わず、実際の担当 ID を記録する。

## 専門レンズの共通規則

- 構図・文字・色の専門レンズ（[構図](../agents/flyer-composition-reviewer.md)・[文字](../agents/flyer-typography-reviewer.md)・[色](../agents/flyer-color-reviewer.md)）は既定では呼ばない。完成評価で呼ぶ条件は [review-rubric の評価コストの原則](review-rubric.md#評価コストの原則)。他の stage は同じ知見を自分で読み、呼ぶときは確かめたい本質条項を記録する（R3）。
- 呼ぶ側は stage・案 ID・同じ snapshot（固定した時点の入力と画像）・適用要求・担当 criterion・必要な指針 ID を渡し、レンズは受け取った内容を最初に確認する。
- stage=analysis では元画像の観察・保持点・候補の根拠を分析担当へ、stage=analysis-review では提案の妥当性・欠落・保持リスクを評価担当へ返す。この 2 stage では完成画像の visual-review を作らない。stage=create では候補の利点と保持リスクを制作担当へ返し、独立した完成合格を出さない。完成評価では review-contract の「統合」に従う。
- レンズからさらに SubAgent を起動せず、所見を返すだけにする。全用途に固定するフォント・pt・配色・回転を指示しない。
