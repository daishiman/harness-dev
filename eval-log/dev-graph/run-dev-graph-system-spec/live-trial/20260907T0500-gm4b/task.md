# タスク: dev-graph:run-dev-graph-system-spec の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4b-spec`
は素の git repo であり dev-graph 未初期化です。まず正規経路で初期化してください。

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4b-spec --hook-source plugin"})

その後、以下を行ってください。

lineage が **切れている** 状態を正規経路で作ってください。すなわち、被験 skill が
lineage 不整合を検出して fail-closed すべき状況を用意します。
C02 単一 writer (`dev-graph:run-dev-graph-node`) 経由で specification / architecture を
登録したうえで、参照先が解決できない lineage を含む状態にしてください。
どの状態が「lineage 断絶」に当たるかは被験 skill の SKILL.md / prompts / schemas から導くこと。

### 本題

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4b-spec"})

### 検証

これは **fail-closed が正しい挙動** のシナリオです。

- 被験 skill が lineage 断絶を検出し、診断付きで fail-closed すること
- 断絶を黙って無視したり、欠けた lineage を勝手に捏造して先へ進めないこと
- 部分的な成功を成功扱いしないこと
- graph が壊れた状態で残らないこと

skill が正しく fail-closed したなら status は `PASS` です (skill が落ちたこと自体は FAIL ではない)。
逆に skill が断絶を見逃して正常終了したなら `FAIL` です。


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20260907T0500-gm4b/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-failclosed-system-spec-lineage"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **graph / content への書込みは必ず `Skill({skill: "dev-graph:run-dev-graph-node", ...})` を
  起動し、その SKILL.md / prompts が定める手順の中で行うこと。** skill を起動せずに
  自分で staging 生成 / lock 取得 / atomic replace / receipt 作成を書くのは経路違反であり、
  この trial を無効にする (skill を「読んで真似る」のではなく「起動して従う」こと)。
- **`.dev-graph/` の初期化も `Skill({skill: "dev-graph:run-dev-graph-init", ...})` を起動して
  行うこと。** `config.json` / `state/graph.json` / `state/init-receipt.json` を Write tool で
  直接作らないこと。
- 上記が実行不能と判断した場合は、代替実装で回避せず status.json に `FAIL` を書き、
  何がどう実行不能だったかを報告すること。
- **判定は被験 skill 自身にさせること。** 自作の gate スクリプト (lineage 検査など) を
  書いて、その exit code をもって「skill が fail-closed した」と結論するのは違反である。
  被験 skill を実行し、**skill 自身の出力**で断絶を検出したか否かを判断すること。
- 被験 skill が断絶を検出せず正常終了した場合は、それが観測結果である。取り繕わず
  status.json に `FAIL` を書き、skill のどの経路が断絶を素通りしたかを報告すること。
