# 初期化前ガード修復の仕様反映記録

dev-graph 初期化直後に通常操作まで止まる不具合を修復する。計画実行中は完全な設定と readiness を要求し、設定不正やロック探索先の変更を黙認しない。

- [仕様](../../specs/sdp-readiness-review.md)
- [設計](../../architecture/sdp-readiness-review.md)
- [機能](../../features/sdp-readiness-review.md)
- [利用者向け説明](../../docs/sdp-readiness-review.md)
- [最終レビュータスク](../../tasks/sdp-readiness-review.md)
- [仕様反映の受領書](spec-impact-receipt.json)
- [品質ゲート](quality-gates.json)
- [未提出証跡の保存台帳](../../docs/sdp-readiness-review/publication-manifest.json)

文書とグラフは C02 の preview → revision 指定 apply で登録した。受領書は `.dev-graph/state/receipts/node-r000018-add.json` と `node-r000019-update.json`、`node-r000020-update.json`。draft の登録であり、独立評価や confirmed への昇格ではない。

Beads は全残存公開を追跡する `harness-86kh`、今回のタスクノードは `task-sdp-readiness-review`。公開先は `devgraph/task-sdp-readiness-review` から `main` 向けの draft PR。過去の実走ログは当時の失敗も含めて保存し、新しい成功へ置き換えない。MVP のため新規 actor 実走・全体網羅・30思考法の再実行は行わない。

最小の機能回帰は成功した。既存dev-graph実走受領書の照合は6件成功・3件失敗で、C02/node・C04/requirements・C14/decomposeは今回変更後の実走証拠を取り直す必要がある。現時点はマージ可能なリリース完了として扱わず、この残課題を明示したdraft提出とする。
