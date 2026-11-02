# 1.2.0 検証記録

現行1.2.0の実装・画像・fresh実行検証は完了しました。配布kit自身の復元検査は別の外部receiptで確認します。旧版の結果は [1.0〜1.1履歴](history-1.0-1.1.md) として保持し、1.2.0の承認に転用しません。

[現在の状態](stage-1.2.0/status.json) ／ [コピー元と全SHA](stage-1.2.0/evidence-manifest.json)

## 完了した範囲

- native実行経路の2案：現物分析→独立提案評価→制作→別担当の完成画像評価を実施。既存素材と既存背景を明示再利用した2案です。[分析](stage-1.2.0/native/analysis.json)・[提案評価](stage-1.2.0/native/analysis-review.json)・[独立画像評価](stage-1.2.0/native/visual-review.json)・[独立所見](stage-1.2.0/native/independent-visual-observations-final.json)・[描画検査](stage-1.2.0/native/out/checks.json)・[まとめPDF厳密画素検査](stage-1.2.0/native/out/combined-checks.json)。最終PDFと350dpi PNGを各案に同梱しています。
- v13既存13案の改善：個人文の同サイズ/同太さと色のみ4%微差を実recordで照合。350dpi旧画像との比較で全13案とも個人文1行外の画素差分0。[個人文実装記録](stage-1.2.0/v13/personal-parity-implementation.json)・[実record](stage-1.2.0/v13/personal-parity-check.json)・[限定差分](stage-1.2.0/v13/personal-parity-pixel-check.json)。
- v13の全11機械検査は失敗0、まとめPDF16ページ（全13＋白3）を150dpi・文字/図形AA無効で元PDFとデコード済み画素の完全一致比較。[11検査](stage-1.2.0/v13/feedback-all-checks.json)・[16ページ厳密画素照合](stage-1.2.0/v13/combined-pixel-check.json)・[26ページQR照合（全13＋10＋白3）](stage-1.2.0/v13/combined-qr-check.json)。
- runtimeの179ファイルをfresh pathへ同一バイトで複製し、fresh環境の実native受入は95件PASS、失敗0・skip0。[正本実行ログ](stage-1.2.0/runtime/real-suite-final.log)・[root実行結果](stage-1.2.0/runtime/real-suite-final-results.json)・[結果と実施者の区別](stage-1.2.0/runtime/fresh-acceptance-summary.json)・[native2 delivery](stage-1.2.0/native/out/delivery.json)。検証README整理後の差分はREADMEのみで、旧バイトは履歴へ保持し、他178ファイルは一致。[証跡追加前runtime freeze](stage-1.2.0/runtime/source-freeze-before-evidence.json)。別の[復元preflight](stage-1.2.0/runtime/restore-preflight.json)は実施時点の履歴で、最終95件の代用にしません。

- v13の最新13画像を別担当が全体・縮小・詳細で実見し、R01〜R19と5観点各3/4以上、mandatoryFix0で独立PASS。[最終独立画像判定](stage-1.2.0/v13/independent-review.json)・[rubric](stage-1.2.0/v13/review-rubric.json)・[v13 delivery complete](stage-1.2.0/v13/delivery.json)。native実行経路の検証と混同しません。

## 最終独立監査と配布検査

[正式最終独立監査](stage-1.2.0/runtime/independent-plugin-audit-final.json)はC1〜C4すべてPASS、元36指摘を閉鎖し未解消0。新しいnative2案の実ログ・receipt・画像・SHA・分析と参照規範、およびv13の別経路を区別して照合しました。

新kitは `flyer-studio-kit-1.2.0-final-20261022`。既存1.1/既存1.2 kitは保持し、今回の承認へ転用しません。kit作成後のmanifest全SHA・ZIP復元同一性・新pathのnpm ci/自己完結検査/doctor/Claude validateは、kit外の `kit-final-restore.json` に記録します。検査前のPASSをこのkit内へ後付けしません。

## 実績の区別

native2案と、v13専用制作ツールによる既存13案の改善を区別します。nativeで新しい13案を生成した実績ではありません。3専門レンズは一人の独立担当が適用しており、3人が別々にレビューした実績にはしません。

新背景生成、漫画/手書きの全形式、両ホストの新規会話から通した制作、実機印刷、参加意欲や集客効果は未検証です。機械検査だけで読取所見の真実性や美観を保証するものではありません。

収録記録は元ファイルと同一バイトで、原プロジェクトの絶対パスも来歴として保持します。独立したv13プロジェクト全体をkit内へコピーしたものではありません。個人素材を含むローカル私用の検証・導入kitで、外部公開しません。
