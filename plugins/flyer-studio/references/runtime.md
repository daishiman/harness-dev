# 入出力と実コマンド

型の正本は [schemas](../schemas)、実検査は [scripts/cli.cjs](../scripts/cli.cjs) と各実装。ここではコマンドの用途・案件 dir のファイル・失敗時の扱いだけを書く。PLUGIN_ROOT（plugin の最上位フォルダ）の決め方と実行形式は [stage-common](stage-common.md)、工程の順序と FIX の戻り先は [workflow](workflow.md) が正本。

## コマンド一覧

すべて PLUGIN_ROOT で `python3 scripts/build-flyer.py <command> [引数]` と実行する（build-flyer.py は同じ引数を cli.cjs へ渡す入口）。パスは絶対パスで渡す。

| command | 引数 | 用途 |
|---|---|---|
| doctor | — | Node・Chromium・Poppler・依存の有無を確かめる |
| init | `--project DIR [--preset NAME]` | 新しい案件 dir を作る。既存 DIR を拒否するため、prefill などは init 成功後に保存する。preset は [presets](presets/) の値を下書きとして入れる。別名は各 preset.json の aliases を見る |
| catalog | `[--preset NAME]` | plugin 同梱素材の一覧。preset 専用の素材は、その preset を指定したときだけ出る |
| import | `--project DIR --id ID [--file PATH --kind KIND] [--privacy FILE] [--provenance FILE]` | 素材を案件へ取り込む（下記「追加素材と生成記録」） |
| intake-template | `[--preset NAME] [--prefill FILE] [--suggestions FILE] [--out FILE]` | 全質問を 1 枚で出す。learn-suggest の傾向は参考値として載せる |
| intake-apply | `--project DIR --answers FILE` | 一括回答を検査して brief.json と intake.json を書く |
| intake-residual | `--project DIR` | 不足・矛盾・様式提案の要否（styleProposalNeeded）だけを返す |
| essence-baseline | `--project DIR [--request TEXT]` | 開始時の purpose と must-fact の基準を全案件で固定する。intake.json のない旧案件は元の依頼文を --request に渡す |
| essence-check | `--project DIR` | 現在の brief と基準の差を、essence-revisions.json の承認記録と照合する |
| essence-revise | `--project DIR --field PTR --reason TEXT` | 利用者が会話で明示的に承認した purpose・事実の変更を 1 件記録する。brief を直してから呼ぶ |
| prompts | `--project DIR` | 背景用 prompt を保存する。生成はホストのツールで行う |
| analysis-template | `--project DIR --sources FILE` | run-analyze-flyer の準備として下書きを未確認・pending で出し、brief.analysisMode を source-artifact に切り替える |
| analysis-seal | `--project DIR` | 構造・要求網羅・元 SHA を検査し、要求 context と規範 hash を確定する |
| analysis-validate | `--project DIR` | 分析の型と整合を検査する |
| analysis-review-template | `--project DIR` | 呼出側の run-analyze-flyer が提案評価の台帳を用意する。前の評価があれば cycle 台帳へ記録してから reviews/<時刻>/ へ退避する |
| analysis-review-validate | `--project DIR` | 制作へ渡せる独立 PASS だけを通す |
| validate | `--project DIR` | brief・assets・concepts・scene を検査する |
| render | `--project DIR [--id 案ID]` | ヒアリングと本質基準を検査し、凍結した入力から描画する。基準欠落・未承認変更では描画しない |
| verify | `--project DIR` | 全案の機械検査を out/checks.json へ書く |
| pilot-review-template | `--project DIR` | pilot 案だけを検査し、評価台帳を出す。前の評価の扱いは review-template と同じ |
| review-template | `--project DIR` | 完成画像評価の台帳を出す。前の評価があれば cycle 台帳へ記録してから reviews/<時刻>/ へ退避し、変わっていない案は前の PASS を引き継いで埋める（引き継ぐ範囲は[評価コストの原則](review-rubric.md#評価コストの原則)） |
| cycle-status | `--project DIR` | cycle 台帳を更新し、消費した cycle 数・予算・残りを返す。予算を超えていれば fail |
| finalize | `--project DIR` | ヒアリングの未解決・必須の本質基準と差・cycle 予算を確かめてから、納品物を結合・照合して出す。予算超過なら INCOMPLETE を返し納品物を残さない |
| learn-record | `--project DIR` | finalize 後に知見台帳へ 1 行を追記する |
| learn-report | `[--min-cases N] [--preset NAME]` | 台帳を集計して改善提案を返す（提案の下限は下記「知見の記録」） |
| learn-suggest | `[--min-cases N] [--preset NAME]` | 次の intake に載せる参考値を返す |

## 案件 dir のファイル

案件 dir に生まれるファイルはこの表に集める。中身の型は各 schema を見る。

| ファイル | 作るもの | 中身 |
|---|---|---|
| brief.json | init → intake-apply（policy の maxChars・axisGroups と、intake でおまかせだった center、feedback は run-create-flyer が書く） | 目的・読者・価値・行動、確定事実と掲載文、形式・案数・印刷条件、policy、feedback（[brief schema](../schemas/brief.schema.json)） |
| intake.json | intake-apply | 回答ごとの値・出典（answer / document / preset-reconfirmed / placeholder / proposal）・ラウンド・未解決 |
| style-proposals.json | run-intake-flyer | 様式提案 2〜3 案・根拠・目的への効き方と、chosen・chosenBy（user / delegated） |
| essence-baseline.json | essence-baseline | 開始時の依頼文・purpose・must-fact と sha256 |
| essence-revisions.json | essence-revise（利用者が承認したときだけ） | purpose と事実の変更記録 `{at, field, from, to, approvedBy:"user", reason}` |
| assets.json・assets/ | init・import | 素材・SHA・公開条件・privacy・provenance |
| concepts.json・scene.json | 制作 | 案ごとの designIntent と、mm/pt の実レイヤー |
| SOURCES.json・analysis.json | 分析 | 元画像の一覧と、所見・保持点・候補と採否（[analysis schema](../schemas/analysis.schema.json)） |
| analysis-review.json | 分析が雛形を準備 → 提案評価が記入 | 照合の根拠・text/serves 付き必須修正・好みの別記録・PASS/FIX（[analysis-review schema](../schemas/analysis-review.schema.json)） |
| out/<案ID>/ | render | HTML・ブラウザ像・print.pdf・PDF 由来 PNG・測定値・SHA |
| out/checks.json・out/pilot-checks.json | verify・pilot-review-template | 全案と pilot 案の機械検査 |
| pilot-review.json・visual-review.json | 制作が雛形を準備 → 完成画像評価が記入 | 案ごとの観察・必須修正・PASS/FIX（[visual-review schema](../schemas/visual-review.schema.json)） |
| cycle-ledger.json | render・評価台帳の作成・finalize・cycle-status（どれから呼んでも同じ記録は 1 回だけ数える） | 改善 cycle の台帳 `{version, budget, entries[]}`。意味は [workflow](workflow.md#改善と納品) |
| reviews/<時刻>/ | 評価台帳の作り直し | 前の評価の退避先。書き換えない |
| out/all.pdf・white.pdf・index.html・delivery.json | finalize | white.pdf は白案があるときだけ作る。納品物と照合結果。delivery.json には analysisGate・intakeGate・essenceGate・cycles も残る |

## 案件と素材

brief の policy は、center と axisGroups で中心軸の有無と対象の意味群を、requiredTones で案の集合に必ず含める配色を持つ。様式は brief.stylePreferences に短い自由ラベル（閉じた選択肢ではない）で持つ。検査は、center=whole-page で axisGroups が空の案件と、center=none で axisGroups を指定した案件を止める。requiredTones の無い brief は必須の配色なしとして通るため、旧 brief は axisGroups と requiredTones を書いてから検査する。preset の値は下書きで、今回の値として確認し直す（E2）。未確認フラグを自動で true にしない。

qrUrl が無い案件は QR を作らず、copy.apply に電話・当日受付・来場などの具体的な行動を示す申込案内を保存し、requiredRefs に apply を含めて全案へ掲載する。URL がある案件は従来どおり最終 PDF 由来の QR 読取を必須にする。

### 追加素材と生成記録

- 新しい写真は `--privacy FILE` が必須。reviewed=true と、ownerFace・otherFaces・child・personalDeviceScreens・unrelatedEventMarks の各項目の確認記録（対象なしも明記）を持たせる。原写真を残し、公開用の派生物を使う。
- 背景は `--kind background --provenance FILE` で登録する。生成した背景は mode=generated と tool・prompt・generatedAt・outputSha256（取り込んだ画像の SHA と一致）を、既存背景の再利用は mode=reuse-approved と confirmed=true を持たせる。prompt だけでは生成済みにならない。
- 書体は `--kind font` で取り込み、brief.fontFiles と fonts で役割名へ割り当てる。

## 現物の分析・提案と独立評価

分析は元画像を持つ任意の案件 dir で使える。観察対象 ID は元成果物の ID で、新しい scene の案数と一致させる必要はない。SOURCES.json は元画像の `[{id,file}]`、または sources と今回の producer・purpose・constraints・requirements を持つ。file は実画像の絶対パスにし、再描画で変わる out 配下ではなく read-only の baseline snapshot を指す。

[run-analyze-flyer](../skills/run-analyze-flyer/SKILL.md) が全元画像を実見して下書きを埋める。特定案だけの要求は requirements.variantIds で対象を限り、全案へ強制しない。先行試作するなら executionPlan（pilotVariantIds・reason・propagation）を書き、pilot は既存案の一部に限る。seal は提案の承認ではない。分析の記述を変えれば analysisSha が、目的・制約・要求を変えれば context が変わる。

分析担当が analysis-review-template で用意した台帳を、[assign-flyer-analysis-evaluator](../skills/assign-flyer-analysis-evaluator/SKILL.md) が別 context で記入・照合し、analysis-review-validate が独立 PASS だけを通す。元画像・analysis・規範・要求 context が変われば旧承認は使えない。実施者の別名で自己承認を装わない。brief.analysisMode（分析の進め方）は init で new-from-brief（brief から新規に作る。分析の 2 段は飛ばす）になり、analysis-template を実行すると source-artifact（既存紙面を診断する）に切り替わる。source-artifact の案件は、有効な独立承認が無いと制作へ進めない。値が未決の案件は既定値で補わずに止める。コマンドの mode 切替・評価退避は呼出側に許された準備と履歴保全で、AI が brief や退避記録を自由に編集する許可ではない（[所有規則](stage-common.md#所有と機械による付随更新)）。

提案の mandatoryFixes は text と serves（E1〜E5）を持ち、好みは preferenceNotes の text へ分ける。FIX の判定条件は [提案評価契約](../skills/assign-flyer-analysis-evaluator/references/evaluation-contract.md) を正とする。提案 FIX は analysis-review の差戻しとして cycle を数え、画像用の premise と推定しない。旧形式の文字列 FIX は通常の検査・制作で停止する。移行は呼出側が analysis-review-template を再発行し、旧記録を serves を補わない未分類の履歴として予算へ記録・原文のまま退避してから、新型で独立評価を受け直す。

## 採否から制作へ

brief.feedback は案件内の実要素への適用台帳で、required / proposal と apply / preserve / decline / pending を区別する（実検査は design.cjs）。analysis の adopt / maintain は apply / preserve へ対応し、元画像 ID と出力 scene ID が違うときは対象を明示して対応させる。required の decline・未決・対象要素の不在・要求を避ける対象外扱いは完成にしない。最終評価の feedbackChecks は、適用要求 ID の全件を今回の実画像の所見と criteria へ結ぶ。

## 構図・書体と描画

concepts.designIntent は読む順序・意味群の目的と位置の理由・役割色・機能のある余白・光学的な均衡・画像と文字の関係を実レイヤーへ対応させる（[design-intent schema](../schemas/design-intent.schema.json)・[scene schema](../schemas/scene.schema.json)）。上部の意図的な非対称を中心軸と混同しない。rejectedAlternatives には、その案で比べて採らなかった候補と理由を書く。

書体は日本語グリフ・利用許諾・実際の字体・埋め込みを確かめる。system font の fallback（代替表示）はホストで変わるので、存在しない書体を使用済みにしない。縦組みは scene の writingMode・textOrientation と高さで、実 renderer が対応する範囲だけを指定する。文字の回転は、その案に必要なときだけ scene の文字へ rotation（度・正が時計回り・-90〜90・0 は書かない）と高さを書き、宣言した箱の中心で回す。縦組み・中心軸の意味群・文字以外の要素の回転は validate が未対応として止める。回転した文字の安全域と重なりは回転後の外接矩形で、はみ出しと不可視は回転前の行で検査する。止められる組合せや未対応 CSS を対応済みと報告しない。

render は背景と写真をラスタ化し、文字・ロゴ・QR を独立レイヤーで印刷する。開始時と終了時で入力・素材・実装が変われば成果を失効させる。verify は軸・衝突・公開 crop・QR・白外縁・サイズ・埋め込み・鮮度などを検査する。機械 PASS を美観 PASS にしない。

## 先行試作から全案への展開

承認済み analysis に executionPlan があれば、render は pilotVariantIds の案だけを描ける。他の案を含む描画は、pilot-review.json が現在の入力・pilot 画像 SHA・最新規範へ結びついた独立 PASS になるまで、ブラウザを開く前に拒否される。pilot-review-template は全案用の checks.json を上書きせず、visual-review と同じ schema の台帳を出す。出力案 ID は分析案 ID と揃え、改名した出力へ pilot の合格を推測で引き継がない。入力や処方を変えれば pilot の合格は失効する。

## 完成画像の独立評価

[assign-flyer-evaluator](../skills/assign-flyer-evaluator/SKILL.md) が [評価コストの原則](review-rubric.md#評価コストの原則)に従う評価対象の新しい PDF 由来 PNG を実見する。見る順序と物差しは [review-rubric](review-rubric.md) が正本。意図を読む前の初見は readingTest（紙面に見えた語のまま）、保持点の確認は preservationChecks へ残す。criteria の本文は 1 回だけ保存し、専門レンズの所見は担当 criterion を参照する（レンズと観点の対応は design-contract.json の expertDimensions）。

mode は、制作と別の 1 担当が判定し、必要なレンズを自分で当てるなら independent-reviewer-lenses、昇格して専門レンズを別担当で呼んだなら independent-agents。独立した担当が無ければ self-review で未完となり、finalize しない。全担当が同じ snapshot を評価し終わるまで編集を止める。

## 納品

finalize は入力と画像の fingerprint・reviewPolicyFingerprint・各 PNG の SHA・5 観点・適用要求・必須修正 0・独立性・cycle 予算を照合する。機械エラーは原因を直して再検査する。目視 FIX の戻り先と予算は [workflow](workflow.md#改善と納品) に従う。preset 固有の点数表と併用するときの規則は [review-rubric](review-rubric.md#案件ごとの点数表との併用) に従う。

結合は finalize の内部処理（merge-pdf.cjs）が行い、個別に承認済みの PDF のページを pdf-lib の page-copy で複製する。Type3 字体の FontMatrix などの数値精度を保つため、結合前後を同じ条件の全 RGBA 画素で照合し、差を許容率で隠さない。元 PDF は上書きせず、外部の既存 PDF も同じ検査を通す。一次資料は [PDFDocument.copyPages/save](https://pdf-lib.js.org/docs/api/classes/pdfdocument)。精度保持は実描画試験の結果として記録し、ライブラリ名だけで保証しない。plugin 外の描画経路の成果を、この plugin の render と verify を通したものと呼ばない。

納品は開始時と、結合・実描画照合の終了時の両方で、入力・分析承認・独立目視・個別成果の鮮度を検査する。処理中の変更を旧 fingerprint で complete にせず pending へ戻す。比較ファイルを足しただけの診断と、入力や承認対象の変更を区別する。

## 一回掲載と要求の引き継ぎ

`brief.singleUseRefs` は今回 1 回だけ掲載する意味群の ref を選ぶ任意の契約で、preset が対象を指定してよい。選んだ ref の配置回数と、解決済み掲載文の直接の再掲を、文字数上限とは別に検査する。意味の言い換えや写真内の文字までは自動で検出できないので、意味群の独立実見で判断する。

承認された analysis の要求は、制作の brief.feedback と完成評価の feedbackChecks へつなぐ。同じ元案・出力案・要求 ID なら自動で対応し、異なる場合は `brief.analysisBindings` で要求 ID・feedback ID・出力案を明示する。元案ごとに採否が違えば台帳と対応を分け、他案の採用で見送りを隠さない。全体要求を一部の案へ逃がさない。対応を変えたら分析 context も更新し、独立提案評価を受け直す。型と実検査の正本は schema と analysis.cjs。

保持点（preservedStrengths）は分析案の ID（analysis.variants[].id）から同じ ID の出力へ引き継ぐ。分析案 ID が出力から消える設定は停止し、要求の analysisBindings から保持点の対応を推測しない。出力を改名するときは分析案 ID を出力に合わせて更新し、再 seal と独立提案評価を受ける。元画像 ID は sourceId に保持するため、元画像と出力の ID・案数が異なること自体は許容する。

## 知見の記録

記録・集計の母集団は納品完了案件だけで、INCOMPLETE や分析のみの案件を含まない。AI の改善仮説はこの範囲の根拠・反例・欠けた入力から判断し、全実行の失敗率や因果へ一般化しない。提案差戻し trigger=analysis-review の cycle は premise の統計から除き、旧記録にある同 trigger の偽 premise も前提崩れとして数えない。

learn-record は `${FLYER_STUDIO_HOME:-~/.flyer-studio}/ledger/cases.jsonl` へ 1 案件 1 行を追記する（append-only＝追記だけで書き換えない）。同じ案件・同じ finalize SHA なら追記しない。保存するのは field path・出典・分類名・回数だけで、個人情報・事実値・参考画像は入れない（E3）。learn-report の改善提案と learn-suggest の質問候補は、件数の下限（--min-cases。省くと learn.cjs の既定）と、各集計対象に占める割合の下限（learn.cjs の minRate。CLI からは変えられない）を両方満たす傾向だけを返す。今回の値は learn-report の出力の minCases・minRate で確かめる。様式ラベルの参考候補は min-cases 以上の件数だけで選び、最低割合は適用しない。learn-suggest の値は再確認が必須の参考値で、preset と質問票は自動で書き換えない。型は [learn-record schema](../schemas/learn-record.schema.json)。
