# 30思考法による配布経路・planner改善レビュー

対象は全22プラグインのClaude/Codex配布・導入経路、およびplugin-dev-plannerの作成・改善時の既定契約。進行中の別issueが扱う業務機能は対象外。Beads: harness-f11。

思考リセット → 3 SubAgentの独立並列分析（9＋9＋12、30種使用・省略0）→ 3実装担当の並列改善 → 別担当の独立再検証を実施。改善は2巡で収束。先行成果物の削除、commit/push、版の採番、実環境への再installは行っていない。

## 判定

対象実装の4条件はすべてPASS。これは現在のsourceと配布契約の判定であり、全業務機能の完全性や未実施の新版実導入を意味しない。

| 条件 | 根拠 |
|---|---|
| 矛盾なし | 公開配布・ローカル導入・開発用projectionを区別。runtime opt-outと両package保持を整合。 |
| 漏れなし | 8条件すべてで5つの導入義務が実行leafへ到達。40の義務欠落をすべて拒否。 |
| 整合性あり | install既定値と義務の生成・検査をspecfmへ集約。全22件のmanifest/catalog/parity/composition検査PASS。 |
| 依存関係整合 | fixed13とtask-graph-derived双方で既存producerが読む実行義務を検査。保存済graphの古い義務も拒否。release後段失敗は台帳確定せず再試行で修復。 |

## 実施した改善

- LOG-01: install宣言だけでなく、通常形式のP13 checklistとtask-graph-derivedのdirect-task受入条項を、既存derive()経由で突合。保存済graphも検査する。
- LOG-04 / META-002: default_install_contract()とinstall_release_obligations()を共通化し、生成器と検査器の値の重複を除去。
- LOG-02 / LOG-03 / META-001: 旧make sync指示、古い配布件数、分散した導入手順を整理。共通installerとnative surface ownerへ集約。
- META-003: Codex除外は実導入対象のみ。両manifest/catalogを維持し、--platformを生成コマンドへ伝搬。
- SYS-01: marketplace/config lock生成成功後にrelease台帳を保存。新規・更新・手動採番の各失敗後に、余分な採番なしで修復。
- SYS-02: handoff・.DS_Store・空directoryだけの差をruntime内容差から除外し、本体の変更検出を維持。単独plugin配布を壊すroot importは追加しない。
- SYS-03: Codexの既存marketplace sourceを変更前に検証し、異なるsourceの上書きを防ぐ。

## 検証

- planner全体: 911 passed、2 skipped。
- 配布・導入・既存文書テスト: 121 passed。追加文書修正後は関連40 passed、1 skipped（重複実行を含むため合算しない）。
- release関連: 17 passed、25 deselected。Gitを要する既存ケースはこのセッションのGit操作禁止に従い対象外。
- Claude CLI strict validate: 全22件PASS。platform同期・local marketplace・capability parity・compositionも全件PASS。
- 独立レビューは実装者とは別context。releaseの6故障ケース、metadata差と本体差、Codex source衝突を修正前後で比較。plannerは2形式×create/update×両製品/Claude-onlyの8正例と40欠落負例を検証。

## 未実施・残る運用上の確認

新版の採番・再installは未実施。初回の実環境読取ではCodex22件、Claude21件がverifiedで、system-spec-harnessのみuser/projectの同hook二重activationを検出した。利用者の設定とtrustは変更していない。次回リリース反映と重複activation整理はharness-y2lに記録。source変更後に既存cacheが更新済みとは主張しない。

## 30思考法の適用記録

以下は初回観察の要約。具体的な修正前証拠は各phase2 JSON、解消確認は独立レビューJSONに保持した。

| # | 思考法 | 適用結果 |
|---|---|---|
| 1 | 批判的思考 | 「値域ゲートPASSならinstall既定が後段へ伝わる」を反証した。宣言と消費者実行義務は異なる。 |
| 2 | 演繹思考 | 全planは両platform install契約を持つ、consumerはtask graphを実行する、よって契約に対応したrelease義務の存在が必要。現行gateにはその含意の検査が無い。 |
| 3 | 帰納的思考 | R1 default指示、R3 default指示、index default、sample P13はいずれも両製品を記述する一方、installテスト群は値域単位に集中。複数artifactの整合は人手文面に依存する傾向を観測。 |
| 4 | アブダクション | 既定キーとsampleは更新済みでもconsumer到達gateが無い最良説明は、install追加がplugin_meta値域と散文生成指示までで閉じていること。既存task graph射影の仕組みを再利用する修正が最小。 |
| 5 | 垂直思考 | R1→R3→index/P13→derive→handoff.task_graph_ref→consumerの一本の経路を追跡。handoffはgraph pathとroute coverageを検査するがinstall obligationを検査しない。 |
| 6 | 要素分解 | installをplatform/manifest/registry/strict/release/isolated/liveの7要素へ分解。値域検査は揃うがtask実体化との接合が未検証。project projectionは別ownerでありmake sync推奨が逸脱。 |
| 7 | MECE | registryを公開Claude/local Claude/Codex repoの3集合に分解。非配布の除外条件は公開集合だけへ適用すべきだが文書はmarketplace全体へ適用している。 |
| 8 | 2軸思考 | create/update × Claude/Codexの4セルを確認。共通R1/R3 defaultsで全セルの宣言は存在する。ただしconsumer build-steps Phase Gの外側は新規plugin限定、内側step4は新規/既存両方とするためupdate登録手順の読み違い余地。中心問題は全セル共通のrelease義務検証欠落。 |
| 9 | プロセス思考 | ユーザー要求→default選択→index検証→P13射影→実install receiptの流れで、index→P13で消失可能と実験確認。新たな手書きルール列挙より共通factory/obligation射影でこの接合を閉じる。 |
| 10 | メタ思考 | 計画を作る責務と、package投影・user installを行う責務を区別し、入口docがどのexecutorへ導くかを観測。plannerは名前参照のみで再実装しない方針は適切だがcommandの旧経路が分岐を再導入する。 |
| 11 | 抽象化思考 | platform名/manifest path/registry/release orderを変数と、repo inventoryを事実とに分離。specfmの同ファイル内リテラル再保持は定数由来のfactoryへ畳める。 |
| 12 | ダブル・ループ思考 | install未達を手順追加で直す前に「公開不可=localでも導入不可」という前提を検証。local22/public18は意図的で、denylistを除去する必要はなく文書の公開範囲と導入範囲の混同を除くべき。 |
| 13 | ブレインストーミング | A:全docへ最新値をコピー、B:巨大cross-plugin共通schema、C:既存specfm内factory+共通installer入口に集約を比較。Aは次のdriftを残しBはinstall自己完結境界を拡大する。Cが最小変更で既存責務を守る。 |
| 14 | 水平思考 | 公開marketplaceの差分を直す代わりに、利用者が最初に見る入口commandを調べると既にREADMEにある全件helperがcommandへ反映されていなかった。機能追加より導線一本化を優先。 |
| 15 | 逆説思考 | 両製品対応の安全な既定と理由付き除外の柔軟性は単独では妥当だが、除外済み計画がdefault=bothのhelperを呼ぶと「除外が正しいほど実行に失敗」する。gateとexecution契約を同じ範囲へ戻す。 |
| 16 | 類推思考 | manifest正本→Codex投影のcompiler構造を、INSTALL_*→default contract→golden outputにも適用する。生成元と複製成果物の区別を揃えれば新しいSSOT形式は不要。 |
| 17 | if思考 | もし明示的にClaude-onlyを求めてcodex除外理由を記せばcheck_installは合格するが、helperはload_catalogでCodex manifestを依然要求する。gateを実メモリ入力で実行しerrors=[]を確認。 |
| 18 | 素人思考 | 「どこからでも全pluginを使う」利用者がmarketplace-registerの手順だけをコピペした場合、Codexはharness-creatorしか入り得ずClaudeの例はcwd依存project scope。READMEの絶対パスcommon helper例へ揃えれば前提知識を減らせる。 |
| 19 | システム思考 | Claude正本→Codex投影→catalog→version/fingerprint→CLI install→runtime receiptの鎖を確認。platform syncはtransaction/lockを持つがrelease台帳と下流生成に完了境界の不一致がある。 |
| 20 | 因果関係分析 | 後段marketplace生成を例外化すると台帳保存が先に終わるためsurveyがcleanとなる。再試行でno-pending分岐へ進み修復しないという因果を現物関数のメモリmockで再現した。 |
| 21 | 因果ループ | handoff更新→copy digest差→stale_runtime→release bump要求→releaseはhandoffを無視し変更なし、という回復不能ループを発見。実在handoffへの仮想本文変更で両検出器の違いを再現した。 |
| 22 | トレードオン思考 | 非配送内容だけを共通除外すれば本物の古い実装検出を維持しつつhandoff起因の誤検出を減らせる。symlink着地点の正規化とCLI marker除外は既存実装を維持し、粗いdigest無効化は不要。 |
| 23 | プラスサム思考 | Codex mutationにも既存source検証を共用すればClaude/checkとの重複分岐を減らし、通常の同source再実行と別source保護を同時に満たせる。既存_assert_marketplace_sourceが受け皿。 |
| 24 | 価値提案思考 | ユーザーの価値は『両方へ入れられた』こと。manifest22件一致から実環境receiptまで確認した結果、Codex22件verified、Claudeはsystem-spec-harnessの同hook複数有効化1件で未verified。構造検証PASSと導入・有効化PASSを混同しない。 |
| 25 | 戦略的思考 | 全pluginへ個別のinstall分岐を追加せず共通installer/releaseの2つの完了境界を優先修正する。fleet全件に効く3所見へ絞り、UBM等の業務機能には波及させない。 |
| 26 | why思考 | なぜ再試行成功なのに未生成か→pendingが0。なぜ0か→保存済みfingerprintと現物が一致。なぜ未生成前に保存済みか→saveが生成前。なぜ後段失敗をcheckが検出しないか→checkが台帳/内容だけ見る。なぜ修復されないか→clean経路が下流再生成を呼ばない。完了印を最後へ移しreleased経路でも随伴生成を回すのが根本処置。 |
| 27 | 改善思考 | 最小改善は台帳保存順序とconfig lock再生成条件、digest除外の整合、Codex source preflight。既存の関数・transaction・receipt・SCC依存順序を活用し、別のinstall frameworkは作らない。 |
| 28 | 仮説思考 | 『release除外とinstaller除外が等しい』を実在handoffのメモリ変更で棄却。『Codex installはcheckと同じsource preflightを通る』を呼出列mockで棄却。『CLI自体が同名別sourceを上書きする』は未検証として保留した。 |
| 29 | 論点思考 | 論点を導入可能性・再実行性・完了宣言の正確さに絞った。CLI読取ではCodex22件導入確認、Claudeの二重activationはソース欠陥と別の環境状態。global mutationを避け、既存有効化を勝手に解除しない。 |
| 30 | KJ法 | 観察を『完了境界』(台帳先行保存)、『内容境界』(handoff差)、『登録identity境界』(Codex source)、『環境状態』(Claude二重activation)に群化。前三者は共通コード修正、最後はユーザー環境の整理判断と分けた。 |

## 証拠と変更一覧

[verdict.json](/Users/dm/dev/dev/個人開発/harness/eval-log/plugin-dev-planner/run-plugin-dev-plan/elegant-review/20261004-f11/verdict.json) / [findings.json](/Users/dm/dev/dev/個人開発/harness/eval-log/plugin-dev-planner/run-plugin-dev-plan/elegant-review/20261004-f11/findings.json) / [initial-findings.json](/Users/dm/dev/dev/個人開発/harness/eval-log/plugin-dev-planner/run-plugin-dev-plan/elegant-review/20261004-f11/initial-findings.json) / [independent-planner-docs.json](/Users/dm/dev/dev/個人開発/harness/eval-log/plugin-dev-planner/run-plugin-dev-plan/elegant-review/20261004-f11/independent-planner-docs.json) / [independent-release-install.json](/Users/dm/dev/dev/個人開発/harness/eval-log/plugin-dev-planner/run-plugin-dev-plan/elegant-review/20261004-f11/independent-release-install.json) / [changed-files.json](/Users/dm/dev/dev/個人開発/harness/eval-log/plugin-dev-planner/run-plugin-dev-plan/elegant-review/20261004-f11/changed-files.json) / [implementation.patch](/Users/dm/dev/dev/個人開発/harness/eval-log/plugin-dev-planner/run-plugin-dev-plan/elegant-review/20261004-f11/implementation.patch)

implementation.patchは事前snapshotがある17ファイルを収録。marketplace-register.mdとその既存testの2ファイルはsnapshot対象外のため、現物・対応テスト・独立契約レビューで確認した。変更ファイルは合計19件、加えて本レビュー証拠を保存。
