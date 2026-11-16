# PKG007と共通feedback runtimeの仕様反映

今回の対象scope、配布依存、開発lintとruntimeの分離を、公開用worktreeで仕様へ反映した。HTTP API・DB schema・認証方式の変更はない。

- [仕様](../../specs/pkg007-runtime.md)
- [設計](../../architecture/pkg007-runtime.md)
- [機能](../../features/pkg007-runtime.md)
- [利用者・専門担当向け説明とPR用要約](../../docs/pkg007-runtime.md)
- [公開タスク](../../tasks/pkg007-runtime.md)
- [仕様影響受領書](spec-impact-receipt.json)
- [最小品質ゲート](quality-gates.json)

5文書とgraphは公開base版のC02 build-graph-node.pyでpreview→expected_graph_revision指定applyした。revision20→21で登録し、結果反映はr21→22、最終ログ表記調整はr22→23。実receiptは .dev-graph/state/receipts/node-r000021-add.json、node-r000022-update.json、node-r000023-update.json。全5nodeはdraft/pendingのまま、readinessはcompleteであり、独立評価・confirmed・doneへの昇格ではない。

Beadsはharness-zb7q、task nodeはtask-pkg007-runtime。branch devgraph/task-pkg007-runtimeからmainへdraft PRを作る。実Notion API投入・live再走・新しい全LLM評価・新exact13は行わない。既存全体coverageの未達は残し、今回MVPゲートの成功を全体coverage達成へ読み替えない。

最小ゲートは公開treeの521test、PKG007全23plugin、feedback strict、vendor330一致、対象23pluginのrelease整合、新規5nodeとSHA/秘密検査が成功した。対象23pluginをpatch採番・正規metadata生成し、installは行っていない。
