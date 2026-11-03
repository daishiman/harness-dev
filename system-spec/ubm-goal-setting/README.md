# 目標設定プラグイン 0.9.3 の仕様反映

今回の変更は、年・期・月・週の目標文書の書き方、対話の問いの数、検査スクリプトに影響する。新しいシステムの全体仕様の編纂ではなく、既存プラグインの差分を C02 の単一 writer で登録した。

| 役割 | 正本 |
|---|---|
| 要件 | [仕様](../../specs/ubm-goal-contract.md) |
| 責務 | [設計](../../architecture/ubm-goal-contract.md) |
| 機能と受入 | [機能](../../features/ubm-goal-contract.md) |
| 案内 | [案内](../../docs/ubm-goal-contract.md) |
| 最終レビュー | [タスク](../../tasks/ubm-goal-contract.md) |
| 適用証拠 | [受領書](spec-impact-receipt.json) |
| 検査結果 | [品質ゲート](quality-gates.json) |

HTTP API、認証、データベース、クラウド構成、他プラグインの仕様は変えていない。draft の feature を 13 フェーズの実装計画へ昇格していない。

実装の正本は `plugins/ubm-goal-setting` の版 0.9.3。既存の月報本文は変換していない。
