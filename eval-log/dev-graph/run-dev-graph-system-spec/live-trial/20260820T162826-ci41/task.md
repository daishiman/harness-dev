# タスク: dev-graph:run-dev-graph-system-spec の実走

対象repoは初期化済みdev-graph repoで、要求briefが `requirements-brief.md` にあります。briefを要求入力とし、宣言済み依存 `system-spec-harness` の正規4 entry pointをqualified Skill呼出しで実際に実行してください。

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r7-spec-lineage"})

本シナリオはimport到達を必須とせず、上流の完全性評価がFAILなら不完全仕様をimportしなfail-closedを検証します。`run-system-spec-elicit`、必要時`run-system-spec-doc-fetch`、`run-system-spec-compile`、`assign-system-spec-completeness-evaluator` のqualified呼出し、C12/C13 exit0、PASSならlineage/evidence/readiness付きC02 importとC11 exit0、FAILならgraph不変・部分書込み0・blocker/owner報告・現graphのc11 exit0を確認してください。dev-graph内へ同等実装を複製しないでください。feedback_contractのmax_iterations=3を守り、FAILの場合は入力側で動かせる余地を1度は検討し根拠を報告してください。scenario IDは `C19-OUT1-failclosed-system-spec-lineage` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20260820T162826-ci41/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"system-spec-failclosed-lineage"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
