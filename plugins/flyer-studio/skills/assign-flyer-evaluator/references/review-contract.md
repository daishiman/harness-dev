# 完成画像の独立評価契約

目的は、実際の最終画像（PDF 由来 PNG）から品質と最新要求の成立を確かめること。提案評価の PASS を完成画像の PASS に転用しない。共通規則は [stage-common](../../../references/stage-common.md)、型は [visual-review schema](../../../schemas/visual-review.schema.json)、見る順序と 5 観点の物差しは [review-rubric](../../../references/review-rubric.md)（DD12）が正本で、評価を始める前に固定する。

## 入力と所有

- 入力: project の絶対パス、brief・concepts・assets・scene、out/checks.json、評価対象の案（[評価コストの原則](../../../references/review-rubric.md#評価コストの原則)）の print.png・render.json、選んだ参照画像（参照画像も実画像で確かめる）、run-create-flyer が生成した評価テンプレート。
- 所有: visual-review.json（先行試作では pilot 案だけを同じ型で pilot-review.json）への記入と所見の返却だけ。文言・配置・素材・画像・テンプレートの生成元を変えず、未公開素材を外部へ送らない。pilot の合格を全案の PASS に転用しない。

## 評価の量

- どの案を見直し、いつ専門レンズを呼ぶかは [review-rubric の評価コストの原則](../../../references/review-rubric.md#評価コストの原則) に従う。5 観点は統合担当（visual-review-coordinator）が自分で判定する。
- mode（評価体制）の既定は independent-reviewer-lenses（制作と別の 1 担当が判定し、必要なレンズを自分で当てる）。レンズを別担当として起動した案があれば independent-agents。独立した担当自体がいなければ self-review の未完として返し、人の独立レビューへ渡す。値の正本は schema。

## 実見と記録

- [評価コストの原則](../../../references/review-rubric.md#評価コストの原則) が定める評価対象の案を、review-rubric の見る順序で 1 案ずつ開く。一覧だけ・機械検査だけ・他担当の所見だけで完了にしない。最終 PDF 由来の画像を正とし、意図した配置から描画で変わった箇所も見る。顔・端末画面の公開範囲、軸、同格、書体、親子関係、自然な接続は [design-rules](../../../references/design-rules.md) に照らす。
- 縮小の初見（readingTest）を記録してから brief.purpose の読者・価値・主要行動と designIntent を読み、目的への適合を hierarchy の根拠に含める。
- 評価対象の各案の criteria へ 5 観点を 1 件ずつ必ず書く。各件は verdict・region（紙面 mm の x/y/w/h）・observation・intentRef（その案の designIntent 内の参照先）を持つ。同じ文の使い回しや観点名の列挙を所見にしない。紙面全体を領域にするときは理由を書く。
- 最新要求の充足は feedbackChecks へ、分析の保持点は preservationChecks へ結び、失われた保持点はその案の FIX にする。様式で崩れやすい観点は [style-profiles](../../../references/style-profiles.md)（DD11）の「レビューの重点」で重く見る。

## 統合

統合は coordinator だけが行う。レンズは stage-common の「専門レンズの共通規則」どおりに同じ snapshot で呼び、全結果が揃ってから統合する。担当は 構図 → balance・spacing、文字 → hierarchy、色 → color・integration。criteria 本文は一度だけ保存し、expertReviews には reviewer・verdict・criteria（担当観点 ID の配列）だけを書く。観察全文を複写せず、実際に見ていない担当の所見を代筆しない。

## 返却と再確認

- 最新 fingerprint・reviewPolicyFingerprint・reviewer・reviewedAt・mode、案ごとの pngSha256 と実見フラグ（viewedFull・viewedThumbnail・viewedDetails）、readingTest・preservationChecks・criteria・expertReviews・observations・mandatoryFixes・preferenceNotes・decision を返す。制作担当と名前を変えただけで独立を装わない。
- mandatoryFixes の各件は text（案 ID・画像領域・理由・元要求 ID を含む修正内容）・fixClass・serves（E1〜E5 から 1 つ以上）・returnTo を持ち、fixClass と returnTo の組は [workflow の表](../../../references/workflow.md#改善と納品) と一致させる。本質条項に結べない所見は preferenceNotes へ残し、必須修正にも cycle にも数えない。
- 再実見の範囲と引き継ぎ済み item の扱いは [評価コストの原則](../../../references/review-rubric.md#評価コストの原則) に従う。制作者の修正説明だけで PASS へ変えず、古いレビューを手で転記しない。前の評価は reviews/<時刻>/ に退避済みで、新しい台帳には再利用が認められた item が入る。それ以外の案は未判定から始まる。
- 台帳に残るのは所見の SHA と評価が見た画像の指紋まで。どの担当がどの入力で起動されたかは実行環境側にしか記録が無く、plugin の検査では独立性を証明できない。独立は起動した側が担保し、reviewer に制作担当と別の識別子を書く。

## 合否と戻り

- 案ごと・全体の合否は review-rubric の「合否の決め方」に従う。加えて、入力・PNG・規範の hash が一致し、制作と独立していること。機械 PASS・幾何中心・担当名・点数だけでは美観を保証しない。
- 案件固有の採点表との対応は選択した preset の preset.json の knowledgeFiles が指す案件知見に置き、平均で未達を相殺しない。
- FIX は fixClass で決まる戻り先へ、PASS は呼出元の run-create-flyer へ返す（finalize は制作側）。cycle の数え方は stage-common の「戻り先と改善上限」に従い、評価者は修正しない。
