# 工程の正本（intake から learn まで）

この文書は、工程の順序・各 stage の入出力・FIX（修正指示）の戻り先・改善 cycle（改善の 1 周）の意味の正本。責務の境界と正本の地図は [architecture](architecture.md)、コマンドと案件ファイルは [runtime](runtime.md)、stage に共通の手順は [stage-common](stage-common.md)、必要知識は [指針索引](design-knowledge-index.json) を見る。

stage の順序と依存は守り、stage の中の具体的な行動は未達から AI が選ぶ（goal-seek＝目標との差から次の一手を選ぶ進め方）。固定の pt・書体・構図の手順を正解にしない。

## 全体の流れ

intake →（既存紙面があるときだけ analyze → analysis-review）→ create（pilot → 全案）→ review → finalize → learn

| stage | 担当 | 入力 | 出力 | 合否の記録先 |
|---|---|---|---|---|
| intake | [run-intake-flyer](../skills/run-intake-flyer/SKILL.md) | 依頼文・支給資料 | brief.json・intake.json・essence-baseline.json | intake-residual（不足と矛盾）。must-fact は finalize の assertResolved |
| ↳ 様式提案 | run-intake-flyer | 雰囲気の言葉・参考・避けたいもの | 様式が言葉にならなければ 2〜3 案の様式提案（`<project>/style-proposals.json`）→ 利用者が選ぶか、おまかせ | style-proposals.json の chosen |
| analyze | [run-analyze-flyer](../skills/run-analyze-flyer/SKILL.md) | 元紙面の画像（SOURCES.json）・brief | analysis.json・未判定の analysis-review.json | analysis-seal・analysis-validate。呼出側が評価台帳を準備 |
| analysis-review | [assign-flyer-analysis-review](../skills/assign-flyer-analysis-review/SKILL.md) | 元画像・analysis.json・生成済み評価台帳 | 記入した analysis-review.json | analysis-review-validate（PASS/FIX）・FIX は cycle-ledger.json |
| create | [run-create-flyer](../skills/run-create-flyer/SKILL.md) | brief・assets・concepts・scene・承認済み analysis | out/<案ID>/ の print.pdf・print.png | verify → out/checks.json |
| ↳ pilot | run-create-flyer → assign-flyer-review | analysis の executionPlan が指す案だけ | out/pilot-checks.json・pilot-review.json | 独立 PASS まで残りの案は描画できない |
| review | [assign-flyer-review](../skills/assign-flyer-review/SKILL.md) | [評価対象](review-rubric.md#評価コストの原則)の新 PDF 由来 PNG・checks | visual-review.json | 案ごとの PASS/FIX・cycle-ledger.json |
| finalize | run-create-flyer（制作側） | 全案 PASS の visual-review | out/all.pdf・index.html・delivery.json（白案があるときは white.pdf） | finalize（complete か INCOMPLETE） |
| learn | [run-learn-flyer](../skills/run-learn-flyer/SKILL.md) | finalize 済みの案件 | 知見台帳 `${FLYER_STUDIO_HOME:-~/.flyer-studio}/ledger/cases.jsonl` | learn-record（同じ案件・同じ finalize は再追記しない） |

## 判断の錨

本質の正本は [essence.json](essence.json)。ここには要約だけを置く。

- E1 目的適合・E2 事実の正確さ・E3 公開と権利の安全・E4 印刷品質・E5 独立した確認。判断と必須修正はこのどれかに結ぶ。
- R1 必須修正は serves に E を 1 つ以上持つ。結べない所見は preference として記録だけにする。
- R2 purpose と確定事実は、利用者の明示承認を `essence-revisions.json` に残したときだけ変える。差は essence-check が検出する。
- R3 評価観点や担当は、どの E の未達を見つけるかを説明できるときだけ増やす。R4 cycle は E の未達解消にだけ使う。

## stage ごとの要点

**intake**: 全質問を 1 枚で出して一括で答えてもらい、不足と矛盾だけを 1 ラウンドで追加確認する。既出の回答は聞き直さない。確定事実は回答か支給資料からだけ取り、preset の値も今回の値として再確認する（E2）。essence-baseline.json は全案件で必要。制作へ渡す前と finalize の前に essence-check を通し、欠落も未承認の差も停止理由にする。intake.json のない旧案件も、元の依頼文と確認済みの事実を確かめて essence-baseline --request で明示的に基準を作る。基準を自動で作り直して変更を正当化しない。様式は固定の選択肢から選ばせず、既知の例に無い様式も臨時のプロファイルとして同じ判断点で扱う（[style-profiles](style-profiles.md#様式の記述軸)）。

**analyze → analysis-review**: 元紙面は read-only（読むだけで変えない）。元画像の SHA と観察領域を伴う所見・保持点・要求ごとの候補と採否を analysis.json へ出し、初見を記録してから DD と専門知見を使う。元画像 ID の網羅と、これから作る案数を混同しない。提案評価は別 context で元画像と提案を照合し（観察一致・網羅・変更規律・実現性）、FIX は run-analyze-flyer へ戻す。PASS は「制作へ渡せる提案」の判定で、完成紙面の合格ではない。提案 PASS の後、制作まで許可済みならそのまま run-create-flyer へ進む。分析だけの依頼なら分析結果を返して終了する。制作の依頼が未指定のときだけ 1 回確認する。制作へ進む場合は run-create-flyer が制作と cycle-ledger.json を引き継ぎ、評価者は制作を起動しない。

**create（pilot → 全案）**: 採用理由を designIntent・brief.feedback と実要素へ結ぶ。写真・ロゴ・QR を先に仮置きし、衝突は構図・Y 位置・群の幅と間隔・トリミング・重複で直す。中心軸の回避・必須情報の削除・極小文字で通さない。素材は原本と公開用の派生物を分け、SHA と使用条件を残す（E3）。背景は選んだ様式と配色意図から必要性を判断し、新しく生成する場合は実行記録を残す。非生成案では支給背景や明示承認された再利用を選び、生成する方針なのに実行できなければ接続・支給背景・明示された再利用のどれで進めるかを確認する。prompt だけを生成済みにせず、本文・ロゴ・QR は背景へ焼き込まない。編集をまとめて凍結（freeze＝描画中は入力を変えない）し、validate → render → verify。描画中に入力・素材・実装が変われば成果は失効する。最終 PDF 由来の画像を正とし、機械検査が未達なら review へ進めない。pilot の PASS を全案の PASS にしない。

**review**: 見る順序・5 観点の物差し・評価コストの原則は [review-rubric](review-rubric.md)。統合担当は visual-review-coordinator で、専門 3 役は昇格時だけ使うレンズ（[architecture](architecture.md)）。評価者は修正せず、FIX を次節の表で分類して返す。

## 改善と納品

完成画像評価が返す FIX は次の表で分類して戻す。戻り先の正本はこの表と、後述の提案評価の規則。

| fixClass（修正の分類） | 意味 | 戻り先 | cycle 消費 |
|---|---|---|---|
| deterministic | 機械検査・型・素材差替など、方針を変えずに直る | run-create-flyer | する |
| within-plan | 採用済み提案の範囲内の見た目・配置の調整 | run-create-flyer | する |
| premise | 目的・事実・公開範囲・保持条件・提案の前提が崩れている | run-intake-flyer（前提の再確認）→ 既存紙面があれば分析・提案評価、無ければ制作 | する |
| preference | どの本質条項にも結べない好み | 記録のみ（知見台帳へ） | しない |

- visual-review と pilot-review の必須修正（mandatoryFixes）は fixClass・serves（E1〜E5）・returnTo を持ち、fixClass と returnTo は表と一致させる。preference は必須修正に入れず preferenceNotes へ残す。型は [visual-review schema](../schemas/visual-review.schema.json)。
- deterministic と within-plan は制作が直接直し、新描画・検査 → 別担当の再実見へ進む。premise は run-intake-flyer で原因となる前提と確定事実・公開条件を再確認する。purpose や確定事実を変えるときは利用者の明示承認を essence-revise で記録し、essence-check を通す（R2）。既存紙面がある案件は分析担当が保持点と修正提案を更新し、別担当の提案評価 → 制作へ戻す。元画像の無い新規案件は analysisMode=new-from-brief のまま制作へ戻し、架空の元画像を作らない。どちらも新描画・検査 → 別担当の再実見へ進み、cycle の予算は引き継ぐ。
- analysis-review の FIX は提案そのものへの指摘なので、常に run-analyze-flyer へ戻す。必須修正は text と serves を持ち、4 条件の判定と整合させる（[提案評価契約](../skills/assign-flyer-analysis-review/references/evaluation-contract.md)）。好みは preferenceNotes へ分ける。提案差戻しは trigger=analysis-review として cycle を消費するが、画像用 fixClass を推定せず fixClasses は空とし、前提崩れの premise 件数へ加算しない。
- FIX には案 ID・画像領域・理由・元要求 ID を添え、元要求の意味を勝手に変えない。要求に無い新しい改善仮説は候補として記録し、必須要求へ勝手に昇格しない。

**cycle の予算**: 上限の数値は [design-contract.json](design-contract.json) の cycleBudget を正とする。予算は案件全体で 1 つで、stage を戻っても提案を再評価してもリセットせず、提案 FIX だけの往復も同じ予算で数える。1 cycle は「FIX を返した評価 → 修正 → 新描画・検査 → 再評価」（提案評価だけの往復では修正提案の検査・再評価）で、FIX を返した評価は render・評価台帳の作り直し・finalize のときに評価記録から `cycle-ledger.json` へ 1 entry ずつ追記され（同じ評価記録は 1 回だけ）、消費した entry だけが cycle 番号を進める。

- **消費しない（consumed=false）**: 同じ所見の digest と同じ描画の digest の再提出（実物が変わっていない）、数えた評価と同じ画像への所見の追記（新しい描画が無い）、preference だけの所見（R1・R4）。重複は止め、未達と次に必要な修正を残す。
- **止める**: 全案・全必須条件が PASS になったらすぐ止める。予算を使い切っても未達なら INCOMPLETE（未完のまま返す）。finalize も予算超過を INCOMPLETE にする。
- 画像・要望・規範が変われば旧証拠を使わない。点数や署名だけで強制 PASS しない。

**納品（finalize）**: 全案の最新の機械検査・独立レビュー・必須修正 0・cycle 予算内・must-fact 解決を確かめて結合し、ページ数・順序・元 PDF の SHA・描画像を照合する。渡すのは編集元、個別 PDF/PNG、一覧・全案 PDF・白案がある場合の白案 PDF、事実・素材・生成・分析・評価・検査の記録と再実行方法。用紙と 100% 倍率で印刷する案内を添え、実機印刷・来場効果・別ホストでの再現は未実施として区別する。

## 知見の還元（learn）

finalize の後に run-learn-flyer が 1 回だけ記録し、AI が集計の根拠と反例から適用範囲を限った改善仮説を返す。母集団は納品完了案件だけで、未完了や分析のみの案件へ一般化しない。次の intake は learn-suggest の傾向を、再確認が必須の参考値として使う。台帳に入れてよいものと、提案を反映する手順は [runtime](runtime.md#知見の記録) を見る。

詳細 30 法は、明示されたときだけ [thirty-methods](thirty-methods.md) を追加する。
