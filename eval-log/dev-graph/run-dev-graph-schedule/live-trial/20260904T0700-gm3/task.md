# タスク: dev-graph:run-dev-graph-schedule の実走

### 準備

schedule 対象の graph を **手作業ではなく skill の正規経路で** 用意してください。
C02 単一 writer (`dev-graph:run-dev-graph-node`) 経由で複数の task を登録し、
次が混在する状態にしてください:

- 依存が全て解決済みで ready になるべき task (複数、resource_scope が重なるものと重ならないものの双方)
- 依存が未解決で blocked のままであるべき task
- draft / 未確認 (unconfirmed) / evaluation 非 pass / readiness 非 complete の task

### 本題

Skill({skill: "dev-graph:run-dev-graph-schedule", args: "--repo-root /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-schedule --max-parallel 4"})

### 検証

- ready-set に全依存済み task だけが入ること
- blocked / draft / unconfirmed / evaluation 非 pass / readiness 非 complete が ready-set に 0 件であること
- batch 内の resource_scope 重複が 0 件であること
- suggested_branch と worktree claim command が一意であること


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20260904T0700-gm3/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"schedule-positive-ready-set"}`
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
