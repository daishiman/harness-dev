# 元ブランチ全残存統合の仕様影響

元ブランチの全残存を最新mainへ統合する変更について、既存の責務契約と実装・保存先を結ぶ索引です。新規システム全体をsystem-spec-harnessで編纂したという宣言ではありません。

| 役割 | 文書・証拠 |
|---|---|
| 変更範囲・受入 | [仕様](../../specs/branch-publication.md) |
| CLI・描画・保存の責務 | [設計](../../architecture/branch-publication.md) |
| 整理用のmacro feature | [機能](../../features/branch-publication.md) |
| 利用者・レビュー向け案内 | [案内](../../docs/branch-publication.md) |
| 実行する作業の契約 | [draft task](../../tasks/branch-remaining-publication.md) |
| 全件の実装・保存先対応 | [manifest](../../docs/branch-publication/manifest.json) |
| 元版・素材・検証記録の復元 | [restore-source.py](../../docs/branch-publication/restore-source.py) |
| 独立したタスク契約評価 | [task-contract-review.json](../../docs/branch-publication/task-contract-review.json) |
| 仕様影響とC02適用証拠 | [spec-impact-receipt.json](spec-impact-receipt.json) |

4資料はC02単一writerのpreview/applyでgraph revision 4から5へ登録しました。文書骨格のreadinessはcompleteですが、statusとconfirmationはdraft、evaluationはpending、tracker bindingはnoneです。整理用featureを新しい13計画へ昇格せず、planner・外部投影・lifecycleは起動していません。

対象はdev-graphのmaterialize・confirm-feature・link-beads・planned_featuresとparityの単一builder、UBMの3チェックシートとCodex guard、JSON compositionのlint/release、SBBの番号クリックです。各実行契約は既存pluginの正本へ参照し、この索引では二重定義しません。公開HTTP API・DB・認証基盤を新設しません。

flyer-studioはmainの1.3.2を維持します。元1.3.1と素材42・検証85・計画25を含む元版362ファイルはsource snapshotとして保存し、現行pluginの上書きには使いません。台帳は元rootの1440 status entriesと元HEADの先行11変更を対応付けるための正本で、未反映0件の最終判定とPR #87のpush・CIは親の実行証跡で確認します。

新しい通常taskはpromotion writer不在によるC28の拒否を回避せずdraftを保持し、実行追跡は既存Beads harness-86khの拡張scopeで行います。scopeの明示指示と、未取得の承認receiptを区別します。[既存guide索引](../guide-doc-generator/README.md) とその文書は変更していません。
