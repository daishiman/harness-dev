# タスク: dev-graph:run-dev-graph-sync の実走 (scenario C03-OUT1-positive-second-sync-zero-r2)

この run は scenario C03-OUT1-positive-second-sync-zero-r2 の充足を確認するものです。
scenario required_observations（正本の逐語）:
1. the first sync applies the expected import and export
2. the second sync reports imports changes=0 and exports changes=0
3. stable IDs and snapshots are unchanged on the second run

fixture:
`/private/tmp/harness-claude-ci11-20261103/cases/sync/fx`

この session の cwd は fixture `/private/tmp/harness-claude-ci11-20261103/cases/sync/fx` です。業務パスは絶対パスを使ってください。plugin は同じ fixture の plugins/ にある trial 開始時点の写しを、boot が --plugin-dir で pin します。その写しも harness 作業ツリーも編集しないでください。

remote は `/private/tmp/harness-claude-ci11-20261103/cases/sync/fx/github-adapter.json` を読む `/private/tmp/harness-claude-ci11-20261103/cases/sync/fx/tools/fake-gh.py` だけです。DEV_GRAPH_GH は controller がこの session の環境へその fake-gh へ固定してあります。実 GitHub / bare gh へ接続しないでください。同じ args で Skill を 2 回呼んでください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-sync", args: "--repo-root /private/tmp/harness-claude-ci11-20261103/cases/sync/fx を同じ入力で 2 回続けて実行する (remote は DEV_GRAPH_GH=/private/tmp/harness-claude-ci11-20261103/cases/sync/fx/tools/fake-gh.py が読む fixture 内 github-adapter.json だけ)"})

1 回目の import/export 適用、2 回目の双方 changes=0、および Issue/Projects planner の converged=true / unresolved_count=0、stable IDs/snapshots 不変を実 report で確認してください。既存 canonical external mutation guard を preview → 実 UserPromptSubmit reply → authorize → execute の順で通し、receipt を自作しないでください。

### external mutation guard

この trial では canonical preview → UserPromptSubmit hook → authorize → execute を実際に通します。事前に指定する fixture 回答は、fixture だけを対象にした preview の challenge へ `CONFIRM EXTERNAL MUTATION <challenge>` と返信することです。この返信は orchestrator が本 Claude UI へ送る fixture 入力であり、実在人間の新規判断や本 repo / 実 GitHub の承認を証明するものではありません。confirmation receipt を自作したり hook-confirm stdin を偽造してはならない。

すべての guard 呼出しの --project-root は `/private/tmp/harness-claude-ci11-20261103/cases/sync/fx` に固定する。scope は fixture の local fake-gh だけ。実在 GitHub へ接続せず、現実の account を操作しない。

preview 後は challenge, preview_receipt_id, project_root を `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-sync/live-trial/20261103T004404-claude-ci11c-sync/gate-request.json` へ Write し、`GATE-CHALLENGE: <challenge>` を報告して返信を待つ。orchestrator の canonical send-line による返信を待つ。この実 UserPromptSubmit hook が発行した receipt だけを利用する。新 reply の hook 出力または同 workdir の gate-response.json に返された canonical confirmation_receipt_path を Read して authorize/execute に進む。Read 待機中に Bash polling や preview cancel を行わない。scope 不一致や receipt 不成立は迂回せず FAIL。

### 検証

- 1 回目が期待どおりの import / export を適用すること（export が実際に apply されるまで到達すること）
- 2 回目の imports / exports の changes がともに 0 件であること
- stable ID と snapshot が 2 回目で不変であること
- Issue planner と Projects planner の両方で converged=true、unresolved_count=0 を実 report で確認すること。changes=0 のみでは PASS とせず、missing/conflicts/held/skipped が残る場合は FAIL

status 判定の規則:
- 1 回目の export が実際に apply され、かつ 2 回目が changes 0 かつ両 planner が converged のときだけ PASS。
- gate 未成立で 1 回目が未適用のまま終わった場合は FAIL。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-sync/live-trial/20261103T004404-claude-ci11c-sync/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容: {"status": "PASS|FAIL|ERROR", "scenario": "C03-OUT1-positive-second-sync-zero-r2"}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- gate 待機以外では人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。中間成果物と goal-seek 証跡は fixture 内の eval-log へ保存する。DEV_GRAPH_ROOT は fixture とし、harness 作業ツリーへは書かない。
- 書込は隔離 fixture と本 run の証跡 dir だけ。source/plugin/settings、旧 fixture、過去証跡を変更しない。
- 実在 Beads/GitHub/Projects や外部サービスへの接続・mutation、外部公開、plugin install を行わない。
- artifact_delivery の選択は standard。実成果物の path と digest を提示してから、この予め指定済みの standard を記録して正規の後続検証へ進める。これは本 repo や外部アカウントの承認ではない。
- Skill tool が Unknown skill になった場合、直ちに status.json を FAIL で終了し、Read で真似る、または直接 script へ代替しない。
- 実行の意味: Skill tool は手順を現在 context へロードする。ロード成功だけで writer が実行済みになったとは扱わず、ロードされた SKILL と各責務 prompt に従って canonical writer/validator/必須 Agent を実行し、実成果を作って検証する。
- 必須の独立 verifier は Agent tool で起動する（dev-graph:dev-graph-sync-conflict-verifier）。自分の判定で代替しない。
- scenario 予算は wall 1200 秒 / tokens 7000000。延長しない。
- 外部公開は禁止。Artifact tool / Claude.ai publish は使わない。
