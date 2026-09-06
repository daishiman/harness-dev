# タスク: dev-graph:run-dev-graph-decompose の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-decompose", args: "認証付きTODO APIをarchitecture、認証feature、TODO featureへマクロ分解する。TODOは認証に依存。全nodeはtracker_binding=none。 --repo-root /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-decompose --dry-run"})

feature+architecture DAGが循環なし、task粒度混入なし、全node draft preview、外部write 0、原graph digest不変であることを検証してください。featureを通常C02 addとして直登録していないことも確認してください。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/run-dev-graph-decompose/live-trial/20260904T0500-gm1/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"decompose-macro-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **成果物を生成する自作スクリプトを書かないこと。** driver / build / guard の類を自分で
  実装して成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- graph / content の生成と適用は必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`、preview は `--dry-run`) を通すこと。
  直接の file write や手書き JSON 組み立てで代替しないこと。
- SKILL.md の Macro flow が要求する独立 auditor は Agent tool で実際に起動すること
  (`dev-graph-integrity-auditor`)。自分で書いた検査コードによる自己判定で代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
  読まずに出力 shape を発明しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。
