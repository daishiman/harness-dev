# 最終紙面を設計意図から独立して確認

[完成画像の独立評価契約](../skills/assign-flyer-review/references/review-contract.md)に従う。入力と書いてよい範囲は[入力と所有](../skills/assign-flyer-review/references/review-contract.md#入力と所有)、出力は[runtime](../references/runtime.md)のvisual-review.json（型は[schema](../schemas/visual-review.schema.json)）。

見直す案と専門レンズの量は[評価の量](../skills/assign-flyer-review/references/review-contract.md#評価の量)に従う。評価対象の範囲と reusedFrom 付き item の扱いは[評価コストの原則](../references/review-rubric.md#評価コストの原則)に従い、対象の案を、[評価の物差し(DD12)](../references/review-rubric.md)の「見る順序」で1案ずつ見る。designIntentを読む前に縮小で readingTest を記録し、文言は紙面に見えた語をそのまま書く。初見が意図と違っても、意図に合わせて所見を書き換えない。記録の項目は[実見と記録](../skills/assign-flyer-review/references/review-contract.md#実見と記録)。前の画像の観察文を新しい画像へ写さない（同じ案で画像だけが変わり文が同じなら機械検査で落ちる）。

5観点の criteria には confidence（high/low）を付ける。専門レンズの呼出条件と呼ぶ側の責務は[専門レンズの共通規則](../references/stage-common.md#専門レンズの共通規則)に従い、呼んだ担当の結果を expertReviews に記録する（統合の仕方は[統合](../skills/assign-flyer-review/references/review-contract.md#統合)）。呼ばない案では expertReviews は空でよい。

mandatoryFixes は text・fixClass・serves（E1〜E5）・returnTo の組で書き、本質条項に結べない好みは preferenceNotes（category は balance・color・hierarchy・spacing・integration のどれか）へ残す。書き方は[返却と再確認](../skills/assign-flyer-review/references/review-contract.md#返却と再確認)、合否と戻り先は[合否と戻り](../skills/assign-flyer-review/references/review-contract.md#合否と戻り)。機械検査の PASS を視覚品質に読み替えず、analysis-review の PASS を新 PNG の合格へ転用しない。評価者は制作を修正しない。
