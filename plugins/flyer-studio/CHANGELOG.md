# 変更履歴

## 1.3.0 — 2026-10-23

- **評価 skill の改名**: assign-flyer-review を assign-flyer-evaluator に、assign-flyer-analysis-review を assign-flyer-analysis-evaluator に改名し、frontmatter に `role_suffix: evaluator` を足した。名前の接尾辞と役割の宣言が一致することを harness の lint-skill-name が確かめる。登録簿・入口の地図・各 skill の参照も新しい名前へ付け替えた。旧名からの呼び出しは残さない。
- **実際に使える成果物を先に見せる 2 段構成**: run の 4 skill は、まず最小の実成果物（ヒアリング要約と様式案・診断と改善案の下書き・1 案の下書き紙面・集計の要約案）を親 context で作って見せ、現状で試す／軽微／標準／詳細（accept-as-is・light・standard・detailed）を利用者が選んでから、選んだ深さで評価と改善を進める（本文の「選ぶ前の実成果物の作成」と「選んだ深さでの改善の実行」）。frontmatter に artifact_delivery を、workflow-manifest.json に artifact_delivery_contract を置き、goal_seek と feedback_contract に `activation_state: semantic_evaluator_started` を書いた。下書きは納品物ではなく、別担当の評価を通っていない版は納品しない。選んだ深さでも評価の量・cycle の上限・個人情報の規則は緩めず、詳細 30 法は利用者が明示したときだけ加える。
- **ゴールシーク実行への書き換え**: 実行系の 6 skill のすべてが `## ゴールシーク実行` を持つようにした（intake と learn は新設、assign の 2 skill は「未達から次の行動を選ぶ」の見出しを改めた）。run の 4 skill はゴール・完了チェックリスト・ループを持つ。固定の `## 手順` を持っていた intake と learn は、元の手順を番号付きの `### 局面カタログ` として残す（番号は参照用で、実行の順番を固定しない）。周回の記録（goal-spec・progress・intermediate.jsonl）は案件フォルダの `<DIR>/goal-seek/`（learn は `${FLYER_STUDIO_HOME:-~/.flyer-studio}/goal-seek/run-learn-flyer/<開始時刻>/`）に置き、plugin の中へ書かない。この記録は cycle-ledger.json の entry にはせず、cycle の消費は評価記録からだけ数える。各周回の後に、ゴールの書き換えとハッシュの不一致を止める検査を実行する。
- **非FIX の戻り先のアンカー**: 登録簿（references/registry.json）の nonFixReturns の step と、stage-common.md・interview-guide.md の局面への参照を `#手順` から `#局面カタログ` へ付け替えた。tests/design.test.cjs は見出しの深さを読んで節を切り出し、戻り先の局面が局面カタログに実在することを確かめる。
- **登録簿と harness の部品宣言の分離**: 部品の登録簿を plugin-composition.yaml（中身は JSON）から references/registry.json へ移し、版と kind を外した（版は plugin manifest が正本）。plugin-composition.yaml は harness 書式の生成物にし、`scripts/build-local-package.py --write-composition` が登録簿と manifest から書く。写すのは、名前と版（manifest）・説明・owner・contract・eval_sinks・公開面（登録簿の skill・repo 専用の run-skill-feedback・plugin 直下の agent）・依存の DAG（revision を外し、skill 内の agent の辺はその skill へ寄せる）・外部依存で、FIX の戻り・非FIXの差し戻し・退役の記録・skill 内の agent は登録簿にだけ残る。`--check` は生成との一致を見て、手直しを止める。生成器は値を、YAML として読み戻すと元の文字列になる形で書く（数・日付・真偽・null に読まれる形と記号や制御文字を含む形は引用し、plugin の版は release が引用なしで書き換えるので引用しない。外部依存の版は常に引用する）。キットでは写した中身から作り直すので、run-skill-feedback と、それだけが要る harness-creator への外部依存が落ちる。harness の lint-plugin-composition と release の版の同期が、flyer だけの例外なしに読める。
- **入口の地図の置き場所**: plugin 直下の SKILL.md を references/kit-entry.md へ移した。harness では plugin 直下に SKILL.md を置かない規約のためで、ローカルキットでは scripts/build-local-package.py がリンクを plugin 直下からの相対に直して、キット直下の SKILL.md として書き出す。`--check` は kit-entry の name が plugin 名と一致すること・リンクがキット直下から解決すること・キット直下に SKILL.md があるときは書き出しと一致することを確かめ、package-contract.json の必要ファイルも references/kit-entry.md にした。
- **工程表の入口**: 6 つの stage skill の workflow-manifest.json の entrypoint を scripts/cli.cjs から scripts/build-flyer.py へ替えた。担当に使わせる入口は stage-common.md と runtime.md のとおり build-flyer.py（同じ引数を cli.cjs へ渡す）で、登録簿の implementation.entrypoint もこちらを指す。工程表だけが本体を指していた。cli.cjs は実装の本体として、登録簿の attached_resources に残る。
- **キットの入口の台帳**: キットへ写すとき、package-contract.json の entry_points.skills からも、キットに写さない skill（KIT_EXCLUDED_SKILLS の run-skill-feedback）を外す。以前は skill のフォルダだけを外して台帳に名前が残り、生成したキットの中で `--check` を実行すると入口の不一致で落ちていた。同じ台帳の runtime_dependencies からは外した skill の項目を、depends_on からは manifest と同じ KIT_EXCLUDED_DEPENDENCIES（skill-governance-adapters）と、キットの composition から落ちた外部依存（harness-creator）を外し、キットが解決できない依存を宣言しない。repo の台帳はそのまま残す。生成したキットが自分の `--check` を通ることを tests/package-contract.test.cjs で確かめる。
- **独立レビューの指摘の反映**: stage-common.md に「深さの選択と戻り」を足した。現状で試す（accept-as-is）を選んだ stage は後続が読む成果物を作らないので次へ進めないこと、評価の FIX や premise の戻しで入り直したときは前に記録した深さを引き継いで選び直しを求めないこと（深さは返却文へ書き、別の会話で前の返却文が読めないときだけ 1 回選び直す）を書き、run の 4 skill と workflow.md の premise の項目からこの節へつないだ。各 run には、深さが変える手間の範囲を 1 文で書いた。run-learn-flyer は、様式ラベルの傾向と参考候補が件数の下限（minCases）だけで選ばれ割合条件を使わないことを IN2・ゴール・チェックリストに書き、learn-suggest の文に件数と母数（例「切り絵（3/11 件）」）を添えた。返す labels はラベルのままにし、tests/learn.test.cjs で確かめる。run-intake-flyer の description は発火の場面を 2 つに絞った。run-create-flyer は、brief.policy の maxChars・axisGroups（intake で center がおまかせなら center も）を下書きの validate の前に決めることと、validate が全案の scene を検査することを書き、この 3 項目を flyer-producer の所有・production-contract・runtime.md の brief.json の行（feedback も制作が書く）にも書いた。description の頭には「確定した brief の」を入れた。run-analyze-flyer の workflow-manifest.json は completionRequiresIndependentReviewer を true にした。
- **非FIXの差し戻しの分離**: 様式が未確定のまま制作に入ったときのヒアリングへの差し戻しを、premise の revision 辺から登録簿（references/registry.json）の nonFixReturns へ分けた。revision 辺は評価の FIX だけを表し、nonFixReturns は fixClass を持たず cycle を消費しない（consumesCycle=false）。端の登録・参照・fixClass を持たないこと・consumesCycle=false・dependencies への非混入を scripts/build-local-package.py --check が、trigger と fixClass の区別と、戻り先の手順と見出しが skill の文書と一致することを tests/design.test.cjs が検査する。
- **skill の frontmatter を repo の規約へ揃えた**: run の 4 skill に feedback_contract（内側は tests で確かめる基準、外側は別 context の評価か利用者が確かめる基準）を置いた。max_iterations は goal_seek.max_loops を持つ skill だけに書き、どちらも design-contract.json の cycleBudget の写しであることを tests/design.test.cjs が検査する。6 skill の description は「〜したいとき、〜したいときに使う。」の型にそろえた。
- **漫画調・墨絵の見る観点**: references/designer-knowledge.md に「様式別の見る観点」を足し、漫画調（コマ割り・視線誘導・フキダシ・読む向き）と墨絵（濃淡・にじみとかすれ・余白と間・落款と印章）の問いと誤用しやすい点を出典付きで置いた。指針索引に DD13（漫画調）と DD14（墨絵）を足し、診断・提案評価・制作・完成評価に加えて、DD13 は構図・文字、DD14 は構図・色の専門レンズが、loadWhen の条件に当たる案のときだけ読む。呼び出す専門レンズは増やしていない。
- **知見の見出し**: designer-knowledge.md の H1 を「出典に基づくデザイン知見」にした。見出しに件数を書くと、観点を足したときに件数とずれるため。
- **制作担当の tools 継承の宣言**: skills/run-create-flyer/agents/flyer-producer.md に `tools-inherit: true` を足した。tools を書かずに全ツールを継承することを harness-creator の schema に宣言する欄で、tools 欄が無いのが書き忘れではなく意図だと機械で区別できる。制作開始時にホストの画像生成ツールを見つけて使う扱いは変わらない。
- **専門レンズの description と契約の検査**: 構図・文字・色の専門レンズ 3 体の description を「〜を、…から学んだ観点で、呼び出した担当とは別 context から実画像で確かめたいときに使う。」の型にそろえた。repo の agent で description の末尾規約を外れていたのは、この 3 体だけだった。tools が読み取りだけ（Read・Glob・Grep）であること、stage-common の専門レンズの共通規則と本文が互いを指すこと、name とファイル名が一致することを、harness の tests/test_flyer_studio_lens_agents.py で確かめる。
- **文字の任意回転**: scene の文字に rotation（単位は度、時計回りが正）を書けるようにした。宣言した箱の中心で回すので h が必須で、範囲は references/runtime.md と validate が正本。写真・ロゴ・QR・fields・保護領域の回転、縦組みとの併用、中心軸の意味群に属する文字の回転は、validate が明示エラーで止める。安全域と QR・ロゴ・保護領域への重なりは回転後の外接矩形で、はみ出しと不可視は回転前の行で検査する。
- **空の掲載文の検出**: 配置した掲載文が空か空白だけなら、validate が copy-empty で止め、必須情報を載せたことにしない。
- **見本の例外リストの廃止**: examples の scene は、許す指摘の一覧を持たずに全部の検査を通ることを tests/contract.test.cjs で確かめる。検査が増えれば、見本も自動でその対象になる。
- **重複画像の別名の向け先**: assets/catalog.json で同じ SHA の別名 NEW05〜07 は、正規側（REF04・REF02・REF01）のファイルを指す。元の出所パスは provenance の relativeSource に残す。登録簿の不変条件も「由来（元の出所パス）を保持する」に合わせた。scripts/build-local-package.py --check は、別名の記録が正規側と同じ SHA で同じ実ファイルを指すことを求め、同じ画像を別のパスで二重に同梱させない。
- **package 検査の黙った合格を止めた**: scripts/build-local-package.py --check は、次の場合をエラーにする。専門知見の本文（expertSourcesRef）が root（プラグインのフォルダ）内のファイルでないとき、または expertRoles だけを宣言して参照が無いとき。design-contract.json の knowledgeIndex が、登録簿の指針索引と別のファイルを指すとき。評価の出力先（eval_sinks）が root 内のファイルとして実在しないとき。退役（retired）の移行先が root 内のファイルでないとき。退役したパスにファイルが残っているとき。以前は、専門知見の本文が無ければ接続の照合を飛ばし、knowledgeIndex と評価の出力先は確かめず、退役の移行先は root の外でも通し、退役したパスに残ったファイルは登録済みとして扱っていた。
- **退役ファイルと重複画像の削除**: 退役スタブ 2 件（references/interview.md・agents/flyer-reviewer.md）と、正規側と同じ SHA の重複画像 assets/references/NEW05〜07.png を削除した。登録簿の退役の記録（retired）と assets/catalog.json の別名 NEW05〜07 は残すので、旧パスと旧 ID からも移行先を引ける。
- 6 skill の AI 判断を stage-common に一本化。資料・知識の選択、候補比較、制作、独立評価、集計の解釈を既存資産で分担し、intake/learn の判断と機械処理を分離した。
- 新規案件は doctor/init の後に prefill を保存する。制作への進行は依頼済みの範囲に従い、未指定のときだけ 1 回確認する。提案評価の台帳準備と mode 切替・履歴保全を呼出側責務へ揃えた。
- 提案評価の必須修正を text/serves に揃え、好みを別記録に分離。提案 FIX を画像用 premise と推定せず、知見の母集団を納品完了案件と明示した。旧文字列 FIX は再発行時に原文のまま退避し、新型で再評価する。

- 独立再分析で見つかった工程間の抜けを修正。premise の戻り先と cycle 台帳を合わせ、資料由来の明示様式を引き継ぐ。保持点を持つ元案の改名を黙って受理せず、本質基準のない描画・納品は停止する。

工程を intake → analyze → analysis-review → create → review → finalize → learn の 6 skill に分け、部品の登録簿（どの部品があり、何が何を呼ぶかの一覧）を references/registry.json に集めた（harness 書式の plugin-composition.yaml はそこからの生成物）。

- **一括ヒアリング**: run-intake-flyer を新設。全質問を 1 枚で出して一括で答えてもらい、不足・矛盾・様式提案の要否だけを 1 ラウンドで追加確認する。旧 references/interview.md は退役（retired＝使わなくなった部品）。
- **本質アンカー（判断の錨）**: 判断と必須修正を references/essence.json の E1〜E5 に結ぶ。開始時の purpose と must-fact を essence-baseline.json に固定し、利用者が承認した変更だけを essence-revisions.json に残す。差は essence-check が検出する。
- **analysisRequired の廃止**: brief の分析要否は `analysisMode`（source-artifact / new-from-brief）で決める。旧 brief は analysisMode を書くまで制作へ進めない。
- **FIX の分類**: 評価の FIX（修正指示）を fixClass（deterministic / within-plan / premise / preference）で分類し、戻り先を workflow の表に一本化した。preference（好み）は記録だけで cycle を消費しない。
- **cycle 台帳と予算超過の INCOMPLETE**: FIX を返した評価を案件全体で 1 つの cycle-ledger.json へ 1 回だけ記録し（cycle-status で確認）、予算を超えると finalize は INCOMPLETE（未完）を返して納品物を残さない。上限の正本は design-contract.json の cycleBudget とし、登録簿と skill の値は package 検査で一致を確かめる写しとし、各 workflow-manifest の maxImprovementCycles は削除した。
- **評価の作り直し時の退避**: 評価台帳を作り直すとき、前の評価を cycle 台帳へ記録してから reviews/<時刻>/ へ退避し、書き換えない。
- **様式の開放と提案**: 様式を固定の選択肢から選ばせず、記述軸で受ける。言葉にならなければ 2〜3 案を style-proposals.json で提案し、例に無い様式も同じ判断点で設計・評価する。
- **依頼主の中立化と preset 範囲の素材**: 依頼主・案件固有の値と採点は references/presets/<名前>/ と案件フォルダにだけ置く。preset の付いた素材は、その preset を init で選んだ案件だけが一覧・import・照合に使う。素材一覧の案内文も汎用にした。
- **知見の還元**: run-learn-flyer を新設。finalize 済みの案件を、個人情報・事実値を除いて知見台帳へ 1 回だけ追記し、件数の揃った傾向を次の intake の参考値（要確認）にする。質問票と preset は自動で書き換えない。
- **flyer-reviewer の廃止**: 完成画像の評価は visual-review-coordinator と review-contract へ統合した。構図・文字・色の専門 3 役は、昇格条件に当たるときだけ使うレンズにした。指針 DD09 の参照先も review-contract へ付け替えた。
- **登録簿の正本化**: `build-local-package.py --check` は stage 名・指針 ID・必要ファイルを持たず、登録簿と package-contract から読んで実ファイルと両方向に照合する（未登録の部品、登録だけで実在しない部品、参照切れ、版の不一致を拒否）。入口は user-invocable（利用者が直接呼べる）の 4 skill。EVALS を新しい工程へ更新した。
- 案件方針を一般化。中心軸は`policy.center`（whole-page/none）と`axisGroups`、必須配色は`requiredTones`で案件ごとに決める。案件固有の既定値は持たないため、方針を持たない旧briefは軸の意味群と配色を書いてから検査する。
- 表現様式ごとの判断基準（DD11 [style-profiles](references/style-profiles.md)）を追加。写真・イラスト/生成画像・漫画・墨絵/水墨/書・手書き・文字主体・混合の伝わるもの、背景生成、起きやすい失敗、レビューの重点、権利を設計・背景・評価のpromptへ接続。
- 評価の物差し（DD12 [review-rubric](references/review-rubric.md)）を追加。縮小での初見→全体→拡大→意図照合→5観点→保持点の順序と、観点別のPASS/FIX記述を評価前に固定する。
- 完成レビューに`viewedThumbnail`・`readingTest`（紙面に見えた語・意味群・迷い・誰向けの手掛かり）・`preservationChecks`を追加。掲載文に無い語、意図と食い違う読み順、抽象的な手掛かりを機械検査で拒否する。
- 設計意図に案ごとの`rejectedAlternatives`（比較して採らなかった候補と理由）を必須化。分析に任意の`executionPlan`（既存案の一部に限る先行試作と展開方法）を追加。

**移行**: design-contract.json の reviewPolicyFiles・analysisPolicyFiles に挙げた規範（design-contract・指針索引・評価の物差しなど）が変わったため、規範の fingerprint（内容から作る照合用の値）が変わり、既存の目視レビュー・提案評価は失効する。新しい画像と分析で再評価する。 また、designer-knowledge.md と design-knowledge-index.json は design-contract.json の reviewPolicyFiles と analysisPolicyFiles の両方に入っているため、規範の fingerprint が変わり、既存の目視レビュー・提案評価は失効する。新しい画像と分析で再評価する。描画処理（scripts）と scene schema も変わったため、回転を書かない案件でも既存の描画結果は stale-input になり、再描画が要る。回転を書かない文字が生む HTML は変わらない（tests/runtime-gates.test.cjs で検査）。

## 1.2.1 — 2026-10-22

- 最新支給 `HyogoAI_logo_text_gradation 2.svg` を既定ロゴに採用。原本・配置SVG・透過印刷PNGを同じ素材系として更新。
- 全13案の同梱完成例と素材一覧を新版ロゴへ更新。文字・写真・QRの構成は保持。
- 既存1.2.0の成果・試験記録は当時の履歴として保持。新版ロゴの検査と独立実見は別に記録。

## 1.2.0 — 2026-10-22

- 現物診断/提案評価/制作/完成画像評価の4境界を、各stageのlocal agent/referenceと実manifestで分担。必要指針IDから未達を診断し次行動を選ぶ。
- analysis/analysis-reviewと要求別feedbackを接続し、未承認/自己承認/古い元画像・規範・要求の提案を制作へ流さない。
- 描画中の入力/実装変化を失効させ、縦導入＋横回答の表現をschemaから実描画/測定へ接続。旧画像のレビューを再利用しない。
- Hyogo v13固有の主従/対象問い/料金1回/QR誘導/ロゴ比/構図保持を一般指針と分離。native PASS/FIXと案件0〜4採点を対応付ける。
- 新initはanalysisRequired。旧案件互換は独立評価済みへの自動移行ではない。実行/独立評価の実績は今回の検証記録で確認する。

- 一回掲載の任意ref契約、分析要求から制作/最終要望検査への対応付け、納品処理終了時の鮮度再検査を追加。文字数上限や善意の指示だけで代替しない。
- PDF結合は数値精度を保つ共通page-copyへ。Type3の高精度字形、実画素一致、逆順/元変更拒否を回帰検証する。
- 日本語年月日、個人向け文の同サイズ/同太さと微小な色差、余白/方向の意味と参加判断→QRを案件指針へ反映。

## 1.1.0 — 2026-10-22

- 設計意図・5観点の画像証拠・3専門知見を共通契約へ集約。自己承認と汎用所見を納品条件から除外。
- 透明文字と構図差の水増しを拒否し、コントラスト・群間隔の診断と結合PDFの実検査を追加。
- 規範・30法・素材一覧の正本を整理し、専門役と共通モジュールを分担。
- 旧案件は設計意図/制作担当/新レビューの追記が必要。旧レビューを黙って合格へ移行しない。


## 1.0.1 — 2026-10-22

- JSON Schema検査のAjvを8.20.0へ更新し、依存監査の既知問題を解消。
- 詳細独立レビューで、白外縁・写真公開条件・QR/ロゴ/被写体の衝突と目視記録の型検査を修正。
- 中央揃えと白黒必須の説明を統一し、正式開発計画の引き渡し契約を整合。


## 1.0.0 — 2026-10-22

- 用途・表現形式・素材選択から新構図を制作する、両ホスト用プラグインを新設。
- F07/F11の紙面全体中央軸、白黒各1、自然な境界、白外縁を共通契約化。
- 本人写真・ロゴ・参考・完成13例と公開条件を同梱。
- 背景生成と文字・QR・印刷処理を分離し、最新画像に対する目視を完成条件に追加。
