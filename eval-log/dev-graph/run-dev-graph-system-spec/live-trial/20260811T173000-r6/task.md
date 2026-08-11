# タスク: dev-graph:run-dev-graph-system-spec の実走

対象 repo は初期化済み dev-graph repo で、要求 brief が `requirements-brief.md` に置いてあります
(ローカル専用 TODO REST API。認証、TODO CRUD、SQLite 永続化、外部 network なし)。
brief を要求入力として、宣言済み依存 `system-spec-harness` の正規 4 entry point を
**qualified Skill 呼び出しで実際に引用実行**し、仕様書と architecture を生成してください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r6-spec-lineage"})

次の 4 つの qualified Skill 呼び出しがそれぞれ実際にロード・実行されることが必須で、
`Unknown skill` や直接スクリプト呼び出しへの fallback は即 FAIL とします:

1. `system-spec-harness:run-system-spec-elicit`
2. `system-spec-harness:run-system-spec-doc-fetch` (必要時)
3. `system-spec-harness:run-system-spec-compile`
4. `system-spec-harness:assign-system-spec-completeness-evaluator`

そのうえで coverage / source-citation gate と C11 gate を exit 0 にし、C02 経由で登録された
specification / architecture ノードが `source_lineage.{origin_kind,source_plugin,source_path,source_version,source_digest,imported_at}`
と confirmation evidence・evaluator evidence・readiness を持つことを検証してください。
dev-graph 内に同等の elicit/compile 実装を複製しないこと。
scenario ID は `C19-OUT1-positive-system-spec-lineage` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20260811T173000-r6/out/status.json`
   に完了マーカーを 1 ファイルだけ Write する。内容:
   `{"status": "PASS|FAIL|ERROR", "scenario": "system-spec-positive-lineage"}`
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は skill 側の出力先へ)。
