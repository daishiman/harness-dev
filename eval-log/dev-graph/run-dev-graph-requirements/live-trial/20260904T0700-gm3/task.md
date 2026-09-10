# タスク: dev-graph:run-dev-graph-requirements の実走

### 準備

handoff の入力となる feature と exact-13 package を **正規経路だけで** 用意してください。
`LT-FEATURE-001` を C02 単一 writer (`dev-graph:run-dev-graph-node`) 経由で登録し、
その配下の P01..P13 exact-13 task package を `/private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-requirements/system-plan/LT-FEATURE-001/package.json`
として用意してください。package の形状は
`plugins/dev-graph/schemas/package-registration-receipt.schema.json`、
`plugins/dev-graph/scripts/register-package.py`、および被験 skill の SKILL.md / prompts
から導くこと。

### 本題

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "handoff --repo-root /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-requirements --feature-id LT-FEATURE-001 --package /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-requirements/system-plan/LT-FEATURE-001/package.json"})

### 検証

- handoff が実在し、capability-build / task-graph 向けの要件・13 task・lineage / digest を持つこと
- 本 skill が実装 code を 1 件も生成していないこと
- system plan validator と C11 がともに exit 0 であること (どちらかが非 0 なら PASS にしない)


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20260904T0700-gm3/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C04-OUT1-positive-ready-handoff"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **被験 skill の責務を代行する自作スクリプトを書かないこと。** 自分で書いた実装で
  成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- graph / content への書込みは必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) を通すこと。
  直接の file write や手書き JSON の graph 組み立てで代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が独立 auditor / verifier subagent の起動を要求している場合は
  Agent tool で実際に起動すること。自己判定で代替しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。
