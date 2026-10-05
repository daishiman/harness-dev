# タスク: dev-graph:run-dev-graph-schedule の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83m-schedule`
は、前回 run (20260907T0500-gm4b) が `dev-graph:run-dev-graph-init` と
`dev-graph:run-dev-graph-node` の正規経路で作った fixture の repo から切った git worktree (branch `p83m-schedule`) に、その fixture の未追跡の状態 (`.dev-graph/` と content) を写したものです。同じ repository の worktree なので repository_id は元の fixture と一致し、C24 を通ります。初期化済みで、次が混在する graph を持っています:

- 依存が全て解決済みで ready になるべき task (複数、resource_scope が重なるものと重ならないものの双方)
- 依存が未解決で blocked のままであるべき task
- draft / 未確認 (unconfirmed) / evaluation 非 pass / readiness 非 complete の task

前回の状態を使う理由: 現行の C02 単一 writer (`build-graph-node.py`) は新規 node を常に
`confirmation_status=draft` / `evaluation_status=pending` で書き、通常 task を
confirmed / pass へ遷移させる経路を持たないため、ready な task を今の正規経路では作れません。
この trial では graph / content を作り直さず、この fixture をそのまま schedule の入力にしてください。

### 本題

Skill({skill: "dev-graph:run-dev-graph-schedule", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83m-schedule --max-parallel 4"})

### 検証

- ready-set に全依存済み task だけが入ること
- blocked / draft / unconfirmed / evaluation 非 pass / readiness 非 complete が ready-set に 0 件であること
- batch 内の resource_scope 重複が 0 件であること
- suggested_branch と worktree claim command が一意であること


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20261005T1500-p83m/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"schedule-positive-ready-set"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **graph / content を書き換える必要が生じた場合は、必ず `Skill({skill: "dev-graph:run-dev-graph-node", ...})` を
  起動し、その SKILL.md / prompts が定める手順の中で行うこと。** skill を起動せずに
  自分で staging 生成 / lock 取得 / atomic replace / receipt 作成を書くのは経路違反であり、
  この trial を無効にする (skill を「読んで真似る」のではなく「起動して従う」こと)。
- `config.json` / `state/graph.json` / `state/init-receipt.json` を Write tool で直接書き換えないこと。
- SKILL.md が独立 verifier subagent の起動を要求している場合は Agent tool で実際に起動すること。自己判定で代替しないこと。
- 上記が実行不能と判断した場合は、代替実装で回避せず status.json に `FAIL` を書き、
  何がどう実行不能だったかを報告すること。
