# v7 入力定義の独立レビュー: PASS

blockerはない。この判定は新しい合成入力の内容・履歴保全・再現性に限り、正式C06/C05の監査応答、live受入やC19 goal達成を示さない。

旧qa-037/038のquestion/answer/basis/provenanceはそのまま保存され、差はsupersession metadataの追記だけだった。過去のbasis変更を正当化したのではない。現行auth/securityセルを正規reopenで戻し、新しい提供書面の4source-indexへ再接地してconfirmした。全主/補助qa参照、foundation、decision、現行設計根拠の照合では旧37/38の現行consumerは0。残存言及は保存履歴と、旧根拠を使わない旨の説明だけ。compiled auth/securityにも旧37/38は出ていない。

## 書面の実質

書面はfixture作者が実走前に定義する合成givenと明記し、実利用者の新対話・本番承認とは主張しない。CSRF、セッション保存/ライフサイクル、認証モデル、セキュリティ基準は別々の節へ分ける。4QAは各一つの節を索引し、answerは節の逐語原文と完全一致、answerのUTF-8 SHAも一致する。pathは安全なrepo相対で全componentにsymlinkがなく、実体はroot内の通常ファイルだった。

新しいquestionは提供済みの単一書面節への索引であり、推奨を選ばせたり、複数の独立した新決定を一括承認させたりしない。設定契約に関連する複数条項があることを、N4の複数決定の強制と同一視しない。旧37→CSRF節、旧38→保存節は同じ要件値を覆い、後続の回答記録時刻もある。書面入力を認めるR6/source-index契約の範囲で、supersessionを有効と判断する。

この回復が成立するのは、**新しい合成書面を入力givenとして認める今回の条件に限る**。実案件でAIが作った文書を利用者一次入力へ格上げしたという意味ではない。旧履歴が過去に正しかったことにもならない。

## C06五軸の入力確認

54QAのquestion/answer/provenanceと全48セルを確認した。未収集0、進捗は4/4 loop・complete=trueで整合する。確定8セルの主qa_refはすべて実在・非retired、補助参照も実在する。foundationはschema1.0の正規fallback索引から元の合成回答とqa-033/appr-foundation-v2へ遡り、U1/U2/U3は値があり、今回の変更で値/承認を増やしていない。

qa-009とqa-038の多論点の旧問は、有効な置換として閉じた検出に残す。qa-o1-fixture-v3は定義・時点・表示先・測定を束ねたmediumのN4注記が残るが、現行主qa_refではなく補助だけなので、aspect-criteria1aではblockingにしない。旧37/38の不正basisの経緯も履歴のinfoとして残す。入力レビューで作成したfindingsを正規 `--hearing` 集約へ渡すとblocking=[]だった。これは正式C06 Agentの実応答ではない。

## 正規再現

別scratchへv6実データを複製し、全12canonical CLIを再実行した。全件exit0で、state・新書面・10章/index・出典を含む18ファイルがv7原本とバイト一致。元50QAは旧37/38のmetadata追記以外完全一致、新規4QAだけが増えた。セル差分はauth/webとsecurity/webの参照だけで、foundation・approval・targets・D1/D2/D4は不変。D3は注意書き1件の根拠参照だけが変わり、採択/比較/時刻は保持された。knowledge_refの21参照実在、required-info接地も正規gateで確認した。

証拠は `/tmp/pr86-positive-input-v7-review-replay.json`、構造化判定は `/tmp/pr86-positive-input-v7-review.json`。source/fixture原本は無編集。過去review結論や119証拠/進捗、他agent状態は未参照。

v7 state SHA-256: `09380939cfdf2a35afc32666445deb71785e6a82d781dbe7330b2a80ae747fb2`

書面 SHA-256: `8cb2050c84cf0d7936162752eef55b4880da2cea536d6d8a9ced983a5e876ee4`
