# 資料生成プラグインの仕様反映

今回の変更は、図の選定・描画・検査・表示操作・再現用証跡に影響する。既存プラグインの仕様差分として、C02単一writerで次の文書を登録した。

| 役割 | 正本 |
|---|---|
| 要件・互換性 | [仕様](../../specs/guide-doc-visual.md) |
| 描画と検査の責務 | [設計](../../architecture/guide-doc-visual.md) |
| 機能と受入 | [機能](../../features/guide-doc-visual.md) |
| 利用・再生成 | [案内](../../docs/guide-doc-visual.md) |
| 最終レビューの手順 | [タスク](../../tasks/gdg-review.md) |
| 適用証拠 | [受領書](spec-impact-receipt.json) |
| 実行結果・制限 | [品質ゲート](../../docs/guide-doc-generator-review/quality-gates.json) |

この索引は既存MVPの影響記録であり、新規システム全体のsystem-spec-harness編纂を実施したという宣言ではない。実行契約は既存のcomponent-inventory・brief・schema・設定を該当箇所で更新した。HTTP API・認証・DB・クラウド構成・他プラグインへの仕様変更はない。

C02生成の文書とsnapshotは当該時点の記録として保持し、完了報告は受領書・品質ゲート・Beadsに記録する。draft featureを自動的に実装13フェーズへ昇格させない。
