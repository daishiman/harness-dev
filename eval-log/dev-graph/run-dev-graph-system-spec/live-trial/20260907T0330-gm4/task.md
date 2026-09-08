# タスク: dev-graph:run-dev-graph-system-spec の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-spec`
は素の git repo であり dev-graph 未初期化です。まず正規経路で初期化してください。

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-spec --hook-source plugin"})

その後、以下を行ってください。

lineage が **切れている** 状態を正規経路で作ってください。すなわち、被験 skill が
lineage 不整合を検出して fail-closed すべき状況を用意します。
C02 単一 writer (`dev-graph:run-dev-graph-node`) 経由で specification / architecture を
登録したうえで、参照先が解決できない lineage を含む状態にしてください。
どの状態が「lineage 断絶」に当たるかは被験 skill の SKILL.md / prompts / schemas から導くこと。

### 本題

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-spec"})

### 検証

これは **fail-closed が正しい挙動** のシナリオです。

- 被験 skill が lineage 断絶を検出し、診断付きで fail-closed すること
- 断絶を黙って無視したり、欠けた lineage を勝手に捏造して先へ進めないこと
- 部分的な成功を成功扱いしないこと
- graph が壊れた状態で残らないこと

skill が正しく fail-closed したなら status は `PASS` です (skill が落ちたこと自体は FAIL ではない)。
逆に skill が断絶を見逃して正常終了したなら `FAIL` です。


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20260907T0330-gm4/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-failclosed-system-spec-lineage"}`
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
