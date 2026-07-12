# 実行パターン集

> **読み込み条件**: スキル実行時、改善検討時
> **更新タイミング**: パターンを発見したら追記
> **構成**: 本ファイルはハブ。詳細は分割ファイルを参照。

---

## 分割ファイル一覧

| ファイル | 内容 |
| --- | --- |
| [patterns-success-ipc-auth.md](patterns-success-ipc-auth.md) | 成功パターン: IPC/Auth/Phase12基盤（前半） |
| [patterns-success-ipc-auth-b.md](patterns-success-ipc-auth-b.md) | 成功パターン: IPC/Auth/Testing・UI（後半） |
| [patterns-success-skill-phase12.md](patterns-success-skill-phase12.md) | 成功パターン: Skill/Phase12同期（前半） |
| [patterns-success-skill-phase12-b.md](patterns-success-skill-phase12-b.md) | 成功パターン: IPC/Testing/SDK/Security（後半） |
| [patterns-success-testing-security.md](patterns-success-testing-security.md) | 成功パターン: Testing/Security/IPC契約 |
| [patterns-success-phase12-advanced.md](patterns-success-phase12-advanced.md) | 成功パターン: Phase12上級・UI・ビルド |
| [patterns-failure-phase12.md](patterns-failure-phase12.md) | 失敗パターン: Phase12 |
| [patterns-failure-misc.md](patterns-failure-misc.md) | 失敗パターン: Skill/Build/SDK/IPC/Testing |
| [patterns-guideline-type.md](patterns-guideline-type.md) | ガイドライン・型定義リファクタリング |
| [patterns-pitfall-phase12.md](patterns-pitfall-phase12.md) | 新規Pitfall候補: Phase12 |
| [patterns-pitfall-testing-ui.md](patterns-pitfall-testing-ui.md) | 新規Pitfall候補: Testing/UI/状態管理 |

---

## クイックナビゲーション

| ドメイン                  | 成功パターン                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | 失敗パターン                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🔐 認証・セッション       | Supabase SDK競合防止, setTimeout方式選択, Callback DI, Zustandリスナー二重登録防止, IPC経由エラー伝達, OAuthコールバックエラー抽出, React Portal z-index, Supabase認証状態即時更新, **ブロッキングコンポーネント・タイムアウトパターン（AuthGuard bypass）**                                                                                                                                                                                                                                                                                                                                  | -                                                                                                                                                                                                                                                                                                                                                                                  |
| ⏱️ テスト                 | vi.useFakeTimers+flushPromises, ARIA属性ベースセレクタ, E2Eヘルパー関数分離, E2E安定性対策3層, mockReturnValueOnceテスト間リーク防止, 統合テスト依存サービスモック漏れ防止, DIテストモック大規模修正, Store Hook renderHookパターン, **テスト環境別イベント発火選択**, **モノレポテスト実行ディレクトリ**, **SDKテスト有効化モック2段階リセット**, **Vitest未処理Promise拒否の可視化運用**, **整合性テスト駆動の設定管理**, **grepベース仕様書TDD（spec-onlyタスク）**, **引数形式差異の共通化判断（YAGNI）**, **コンポーネント分割テスト戦略**, **P31回帰テスト（renderHook参照安定性）**, **Store統合テスト分離（UI/Store/セレクタ3層）**, **品質ゲート仕様先行（テストマトリクス事前定義）**, **証跡先行固定（SettingsView回帰）**, **サブエージェントテスト実行タイムアウト対策（exit code 144）**, **contextBridge mock capture テストパターン（Preload内部関数テスト）**                                                                                | テスト環境問題の実装問題誤認, モジュールモック下タイマーテスト失敗, dangerouslyIgnoreUnhandledErrors 常時有効化, **screenshot取得失敗を後追い修正で放置**, **サブエージェントでプロジェクト全体テスト実行（exit code 144）**                                                                                                                                                                                                   |
| 📋 Phase 12               | 成果物名厳密化, サブタスク完了チェックリスト, Step 1完了チェックリスト, Phase 12 Task 2クイックリファレンス, 横断的問題追加検証, 未タスク2段階判定（raw→精査）, **仕様書参照パス実在チェック**, 実装差分ベース文書化, **実装-仕様ドリフト再監査（数値・パス・文言）**, **仕様更新三点セット（quality/task-workflow/lessons-learned）**, **`spec_created` 状態判定**, **未実施タスク配置ドリフト是正（completed-tasks/unassigned-task → unassigned-task）**, **成果物ログとStep判定の同期（先送り禁止）**, **全体監査と対象差分の分離報告**, **仕様書修正タスクPhaseテンプレート（N/A記録）**, **spec-update-summary + artifacts二重台帳同期**, **仕様書修正タスク簡略Phase適用**, **実装ガイド2パート要件ギャップの即時是正**, **監査結果→次アクションブリッジ**, **Task 1〜5証跡突合レポート固定化**, **実装内容+苦戦箇所テンプレート適用**, **仕様書別SubAgent同期テンプレート**, **target監査 + 10見出し同時検証**, **未タスクメタ情報1セクション運用**, **phase-12仕様書ステータス同期（未実施→完了）**, **5仕様書同期 + IPC三点突合テンプレート**, **IPC追加時の登録配線突合（handler/register/preload）**, **待機API/停止API責務分離の仕様固定**, **仕様書単位SubAgent + N/A判定ログ固定**, **UI機能実装の未タスク6件分解（TASK-UI-05）**, **未タスクtarget監査 + diff監査の二段合否固定**, **UI機能6仕様書SubAgent同期テンプレート**, **UI基本6+ドメイン追加仕様同期（TASK-UI-02）**, **Phase 12依存成果物参照補完（warningドリフト防止）**, **UI再確認スクリーンショット再撮影固定（TASK-UI-05B）**, **UI6仕様書の1仕様書1SubAgent固定（TASK-UI-05B）**, **3workflow再監査 + 未タスク個別監査の二段固定（TASK-FIX-SKILL-IMPORT 3連続是正）**, **comparison baseline 正規化つき branch 再監査（TASK-10A-F）**, **並列エージェント台帳同期パターン（TASK-10A-F）**, **Store駆動移行の仕様書更新チェックリスト（TASK-10A-F）**, **fallback error の transport/UI localized 分離 + 画面起点未タスク formalization**, **UI再撮影前preview preflight + 失敗時未タスク化固定（SkillCenter）**, **UI再撮影前ポート競合preflight（5174）+ 分岐記録固定（workflow02）**, **UI再撮影のworkflow保存先固定 + strictPort preflight（5177）分岐記録**, **Light Mode white/black 基準 + compatibility bridge + shard再現 + screenshot再取得**, **同種課題の5分解決カード同期（TASK-055）**, **branch横断 Phase 12 一括監査（workflow複数同時検証）**, **P50パターン既実装→検証モード切替（TASK-FIX-SUPABASE-FALLBACK）**, **SubAgent完了後git diff --stat事後検証固定**, **画面検証で露出した副次不具合の即時未タスク化 + 3.5 節継承（TASK-FIX-SAFEINVOKE-TIMEOUT-001）**, **`verify-unassigned-links` を `missing=0` まで閉じ、exact counts を summary/task-workflow へ同値転記** | 成果物名暗黙解釈, サブタスク暗黙省略, Step 1-A更新漏れ, 未タスクraw検出の誤読, 実装ガイドへの誤ファイル名混入, **仕様書タスクのcompleted誤判定**, **未実施タスクの completed-tasks 配置混入**, **Step2「該当なし」誤判定/Phase 13先送り記載**, **全体ベースライン違反の今回起因誤判定**, **Phase4修正箇所数の事前ファイル検証不足**, **Phase 10/11サブエージェント出力の非永続化**, **spec-update-summary未作成/artifacts台帳非同期**, **仕様書修正タスクでのPhaseテンプレート誤適用**, **Part 1/Part 2必須要件の欠落**, **監査結果の棚卸し止まり（次アクション未定義）**, **成果物実体とphase-12実行記録の乖離放置**, **苦戦箇所が症状のみで再発条件が未記載**, **仕様書更新の単独進行による同期漏れ**, **未タスクメタ情報の二重定義**, **phase-12仕様書ステータス未更新**, **未タスクの存在確認止まり（10見出し未検証）**, **api-ipc仕様を同期対象から除外**, **IPCハンドラ実装のみで登録配線を未確認**, **timeout待機APIへの停止副作用混在**, **非対象仕様（N/A）の記録漏れ**, **task-workflow のみ更新で lessons-learned 同期漏れ**, **UIタスクに5仕様書テンプレートを誤適用**, **UI6仕様書だけ更新して domain UI spec を未同期**, **verify-all-specs warningドリフトの放置**, **UI再確認で既存スクショ存在確認のみで完了判定**, **UI6仕様書を束ねて責務境界が曖昧**, **preview成否確認なしで再撮影開始（ERR_CONNECTION_REFUSED）**, **Port 5174 競合ログ混在を未記録のまま完了判定**, **Port 5177 preflight未記録のまま再撮影を継続**, **5分解決カードをtask-workflowのみ更新して他仕様へ未同期**, **current workflow PASS だけで comparison baseline を放置**, **単一workflow PASSで branch 全体を完了判定する誤り**, **Phase 1で既実装チェックせず新規実装モードで進行（P50未検出）**, **テスト正規表現がエラーコード内/をパスと誤検出**, **画面検証で見つかった warning/contrast 問題を evidence のまま放置**, **global Light Mode を token 修正だけで閉じて renderer-wide drift を残す**, **CI shard fail を broad rerun だけで調査して根因を逃す**, **baseline 更新後も旧 screenshot を流用する**, **新規未タスクに親タスクの苦戦箇所を継承せず再利用性を落とす** |
| 🔌 IPC・アーキテクチャ    | IPCチャンネル統合, コンポーネント同階層ユーティリティ配置, 順次フィルタパイプライン, 横断的セキュリティバイパス検出, 入力バリデーション統一(whitespace対策), IPC/サービス層型変換, **IPC機能開発ワークフロー6段階**, **IPCハンドラライフサイクル管理（unregister→register）**, **IPC L3セキュリティハードニング**, **IPC契約ドリフト防止（3箇所同時更新）**, **Renderer層id→name契約変換**, **IPCチャネル名競合予防（仕様書段階分離）**, **P42準拠バリデーション一括移行（return→throw統一）**, **IPC Date→ISO 8601統一（仕様書段階）**, **positional→object引数統一（仕様書段階）**, **IPC契約ブリッジ（正式契約 + 後方互換）**, **IPC登録後のサービスバレル公開整合チェック**, **IPC Fallback DRYヘルパーパターン（createNotConfiguredResponse + registerFallbackHandlers）**, **safeInvoke timeout（Promise.race containment）**                                                                                               | ハードコード文字列発見, **IPC契約ドリフト（Handler/Preload不整合）**, **Renderer層での識別子混同（id/name）**, **正式契約切替時の後方互換欠落**, **サービス層バレル公開漏れ（直接import固定化）**                                                                                                                                                                                                                                                                      |
| ⏱️ テスト                 | vi.useFakeTimers+flushPromises, ARIA属性ベースセレクタ, E2Eヘルパー関数分離, E2E安定性対策3層, mockReturnValueOnceテスト間リーク防止, 統合テスト依存サービスモック漏れ防止, DIテストモック大規模修正, Store Hook renderHookパターン, **テスト環境別イベント発火選択**, **モノレポテスト実行ディレクトリ**, **SDKテスト有効化モック2段階リセット**, **Vitest未処理Promise拒否の可視化運用**, **整合性テスト駆動の設定管理**, **grepベース仕様書TDD（spec-onlyタスク）**, **引数形式差異の共通化判断（YAGNI）**, **contextBridge mock capture テストパターン（Preload内部関数テスト）**                                                                                | テスト環境問題の実装問題誤認, モジュールモック下タイマーテスト失敗, dangerouslyIgnoreUnhandledErrors 常時有効化                                                                                                                                                                                                                                                                    |
| 📋 Phase 12               | 成果物名厳密化, サブタスク完了チェックリスト, Step 1完了チェックリスト, Phase 12 Task 2クイックリファレンス, 横断的問題追加検証, 未タスク2段階判定（raw→精査）, **仕様書参照パス実在チェック**, 実装差分ベース文書化, **実装-仕様ドリフト再監査（数値・パス・文言）**, **仕様更新三点セット（quality/task-workflow/lessons-learned）**, **`spec_created` 状態判定**, **未実施タスク配置ドリフト是正（completed-tasks/unassigned-task → unassigned-task）**, **成果物ログとStep判定の同期（先送り禁止）**, **全体監査と対象差分の分離報告**, **仕様書修正タスクPhaseテンプレート（N/A記録）**, **spec-update-summary + artifacts二重台帳同期**, **仕様書修正タスク簡略Phase適用**, **実装ガイド2パート要件ギャップの即時是正**, **監査結果→次アクションブリッジ**, **Task 1〜5証跡突合レポート固定化**, **実装内容+苦戦箇所テンプレート適用**, **仕様書別SubAgent同期テンプレート**, **target監査 + 10見出し同時検証**, **未タスクメタ情報1セクション運用**, **phase-12仕様書ステータス同期（未実施→完了）**, **5仕様書同期 + IPC三点突合テンプレート**, **IPC追加時の登録配線突合（handler/register/preload）**, **待機API/停止API責務分離の仕様固定**, **仕様書単位SubAgent + N/A判定ログ固定**, **UI機能実装の未タスク6件分解（TASK-UI-05）**, **未タスクtarget監査 + diff監査の二段合否固定**, **UI機能6仕様書SubAgent同期テンプレート**, **UI基本6+ドメイン追加仕様同期（TASK-UI-02）**, **Phase 12依存成果物参照補完（warningドリフト防止）**, **UI再確認スクリーンショット再撮影固定（TASK-UI-05B）**, **UI6仕様書の1仕様書1SubAgent固定（TASK-UI-05B）**, **3workflow再監査 + 未タスク個別監査の二段固定（TASK-FIX-SKILL-IMPORT 3連続是正）**, **UI再撮影前preview preflight + 失敗時未タスク化固定（SkillCenter）**, **UI再撮影前ポート競合preflight（5174）+ 分岐記録固定（workflow02）**, **UI再撮影のworkflow保存先固定 + strictPort preflight（5177）分岐記録**, **同種課題の5分解決カード同期（TASK-055）** | 成果物名暗黙解釈, サブタスク暗黙省略, Step 1-A更新漏れ, 未タスクraw検出の誤読, 実装ガイドへの誤ファイル名混入, **仕様書タスクのcompleted誤判定**, **未実施タスクの completed-tasks 配置混入**, **Step2「該当なし」誤判定/Phase 13先送り記載**, **全体ベースライン違反の今回起因誤判定**, **Phase4修正箇所数の事前ファイル検証不足**, **Phase 10/11サブエージェント出力の非永続化**, **spec-update-summary未作成/artifacts台帳非同期**, **仕様書修正タスクでのPhaseテンプレート誤適用**, **Part 1/Part 2必須要件の欠落**, **監査結果の棚卸し止まり（次アクション未定義）**, **成果物実体とphase-12実行記録の乖離放置**, **苦戦箇所が症状のみで再発条件が未記載**, **仕様書更新の単独進行による同期漏れ**, **未タスクメタ情報の二重定義**, **phase-12仕様書ステータス未更新**, **未タスクの存在確認止まり（10見出し未検証）**, **api-ipc仕様を同期対象から除外**, **IPCハンドラ実装のみで登録配線を未確認**, **timeout待機APIへの停止副作用混在**, **非対象仕様（N/A）の記録漏れ**, **task-workflow のみ更新で lessons-learned 同期漏れ**, **UIタスクに5仕様書テンプレートを誤適用**, **UI6仕様書だけ更新して domain UI spec を未同期**, **verify-all-specs warningドリフトの放置**, **UI再確認で既存スクショ存在確認のみで完了判定**, **UI6仕様書を束ねて責務境界が曖昧**, **preview成否確認なしで再撮影開始（ERR_CONNECTION_REFUSED）**, **Port 5174 競合ログ混在を未記録のまま完了判定**, **Port 5177 preflight未記録のまま再撮影を継続**, **5分解決カードをtask-workflowのみ更新して他仕様へ未同期** |
| 🔌 IPC・アーキテクチャ    | IPCチャンネル統合, コンポーネント同階層ユーティリティ配置, 順次フィルタパイプライン, 横断的セキュリティバイパス検出, 入力バリデーション統一(whitespace対策), IPC/サービス層型変換, **IPC機能開発ワークフロー6段階**, **IPCハンドラライフサイクル管理（unregister→register）**, **IPC L3セキュリティハードニング**, **IPC契約ドリフト防止（3箇所同時更新）**, **Renderer層id→name契約変換**, **IPCチャネル名競合予防（仕様書段階分離）**, **P42準拠バリデーション一括移行（return→throw統一）**, **IPC Date→ISO 8601統一（仕様書段階）**, **positional→object引数統一（仕様書段階）**, **IPC契約ブリッジ（正式契約 + 後方互換）**, **IPC登録後のサービスバレル公開整合チェック**, **safeInvoke timeout（Promise.race containment）**                                                                                               | ハードコード文字列発見, **IPC契約ドリフト（Handler/Preload不整合）**, **Renderer層での識別子混同（id/name）**, **正式契約切替時の後方互換欠落**, **サービス層バレル公開漏れ（直接import固定化）**                                                                                                                                                                                                                                                                      |
| ⏱️ テスト                 | vi.useFakeTimers+flushPromises, ARIA属性ベースセレクタ, E2Eヘルパー関数分離, E2E安定性対策3層, mockReturnValueOnceテスト間リーク防止, 統合テスト依存サービスモック漏れ防止, DIテストモック大規模修正, Store Hook renderHookパターン, **テスト環境別イベント発火選択**, **モノレポテスト実行ディレクトリ**, **SDKテスト有効化モック2段階リセット**, **Vitest未処理Promise拒否の可視化運用**, **整合性テスト駆動の設定管理**, **grepベース仕様書TDD（spec-onlyタスク）**, **引数形式差異の共通化判断（YAGNI）**, **contextBridge mock capture テストパターン（Preload内部関数テスト）**                                                                                | テスト環境問題の実装問題誤認, モジュールモック下タイマーテスト失敗, dangerouslyIgnoreUnhandledErrors 常時有効化                                                                                                                                                                                                                                                                    |
| 📋 Phase 12               | 成果物名厳密化, サブタスク完了チェックリスト, Step 1完了チェックリスト, Phase 12 Task 2クイックリファレンス, 横断的問題追加検証, 未タスク2段階判定（raw→精査）, **仕様書参照パス実在チェック**, 実装差分ベース文書化, **実装-仕様ドリフト再監査（数値・パス・文言）**, **仕様更新三点セット（quality/task-workflow/lessons-learned）**, **`spec_created` 状態判定**, **未実施タスク配置ドリフト是正（completed-tasks/unassigned-task → unassigned-task）**, **成果物ログとStep判定の同期（先送り禁止）**, **全体監査と対象差分の分離報告**, **仕様書修正タスクPhaseテンプレート（N/A記録）**, **spec-update-summary + artifacts二重台帳同期**, **仕様書修正タスク簡略Phase適用**, **実装ガイド2パート要件ギャップの即時是正**, **監査結果→次アクションブリッジ**, **Task 1〜5証跡突合レポート固定化**, **実装内容+苦戦箇所テンプレート適用**, **仕様書別SubAgent同期テンプレート**, **target監査 + 10見出し同時検証**, **未タスクメタ情報1セクション運用**, **phase-12仕様書ステータス同期（未実施→完了）**, **5仕様書同期 + IPC三点突合テンプレート**, **IPC追加時の登録配線突合（handler/register/preload）**, **待機API/停止API責務分離の仕様固定**, **仕様書単位SubAgent + N/A判定ログ固定**, **UI機能実装の未タスク6件分解（TASK-UI-05）**, **未タスクtarget監査 + diff監査の二段合否固定**, **UI機能6仕様書SubAgent同期テンプレート**, **UI基本6+ドメイン追加仕様同期（TASK-UI-02）**, **Phase 12依存成果物参照補完（warningドリフト防止）**, **UI再確認スクリーンショット再撮影固定（TASK-UI-05B）**, **UI6仕様書の1仕様書1SubAgent固定（TASK-UI-05B）**, **3workflow再監査 + 未タスク個別監査の二段固定（TASK-FIX-SKILL-IMPORT 3連続是正）**, **UI再撮影前preview preflight + 失敗時未タスク化固定（SkillCenter）**, **UI再撮影前ポート競合preflight（5174）+ 分岐記録固定（workflow02）**, **UI再撮影のworkflow保存先固定 + strictPort preflight（5177）分岐記録**, **同種課題の5分解決カード同期（TASK-055）** | 成果物名暗黙解釈, サブタスク暗黙省略, Step 1-A更新漏れ, 未タスクraw検出の誤読, 実装ガイドへの誤ファイル名混入, **仕様書タスクのcompleted誤判定**, **未実施タスクの completed-tasks 配置混入**, **Step2「該当なし」誤判定/Phase 13先送り記載**, **全体ベースライン違反の今回起因誤判定**, **Phase4修正箇所数の事前ファイル検証不足**, **Phase 10/11サブエージェント出力の非永続化**, **spec-update-summary未作成/artifacts台帳非同期**, **仕様書修正タスクでのPhaseテンプレート誤適用**, **Part 1/Part 2必須要件の欠落**, **監査結果の棚卸し止まり（次アクション未定義）**, **成果物実体とphase-12実行記録の乖離放置**, **苦戦箇所が症状のみで再発条件が未記載**, **仕様書更新の単独進行による同期漏れ**, **未タスクメタ情報の二重定義**, **phase-12仕様書ステータス未更新**, **未タスクの存在確認止まり（10見出し未検証）**, **api-ipc仕様を同期対象から除外**, **IPCハンドラ実装のみで登録配線を未確認**, **timeout待機APIへの停止副作用混在**, **非対象仕様（N/A）の記録漏れ**, **task-workflow のみ更新で lessons-learned 同期漏れ**, **UIタスクに5仕様書テンプレートを誤適用**, **UI6仕様書だけ更新して domain UI spec を未同期**, **verify-all-specs warningドリフトの放置**, **UI再確認で既存スクショ存在確認のみで完了判定**, **UI6仕様書を束ねて責務境界が曖昧**, **preview成否確認なしで再撮影開始（ERR_CONNECTION_REFUSED）**, **Port 5174 競合ログ混在を未記録のまま完了判定**, **Port 5177 preflight未記録のまま再撮影を継続**, **5分解決カードをtask-workflowのみ更新して他仕様へ未同期** |
| 🔌 IPC・アーキテクチャ    | IPCチャンネル統合, コンポーネント同階層ユーティリティ配置, 順次フィルタパイプライン, 横断的セキュリティバイパス検出, 入力バリデーション統一(whitespace対策), IPC/サービス層型変換, **IPC機能開発ワークフロー6段階**, **IPCハンドラライフサイクル管理（unregister→register）**, **IPC L3セキュリティハードニング**, **IPC契約ドリフト防止（3箇所同時更新）**, **Renderer層id→name契約変換**, **IPCチャネル名競合予防（仕様書段階分離）**, **P42準拠バリデーション一括移行（return→throw統一）**, **IPC Date→ISO 8601統一（仕様書段階）**, **positional→object引数統一（仕様書段階）**, **IPC契約ブリッジ（正式契約 + 後方互換）**, **IPC登録後のサービスバレル公開整合チェック**, **IPC ハンドラ Graceful Degradation（safeRegister + track クロージャ）**, **safeInvoke timeout（Promise.race containment）**                                                                                               | ハードコード文字列発見, **IPC契約ドリフト（Handler/Preload不整合）**, **Renderer層での識別子混同（id/name）**, **正式契約切替時の後方互換欠落**, **サービス層バレル公開漏れ（直接import固定化）**                                                                                                                                                                                                                                                                      |
| 🏗️ DI・設計               | Setter Injection遅延初期化, **二重パイプライン設計（execute→SkillFileWriter persist統合 TASK-P0-05）**, **Optional Inject graceful degradation（SkillFileWriter未注入時warn+skip）**                                                                                                                                                                                                                                                                                                                                                                                                          | -                                                                                                                                                                                                                                                                                                                                                                                  |
| 💾 永続化・復旧            | **persist復旧の3段ガード（Set/Array二方向シリアライズ）**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | -                                                                                                                                                                                                                                                                                                                                                                                  |
| 🛡️ セキュリティ           | TDDセキュリティテスト分類体系, YAGNI共通化判断記録                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | 正規表現パターンPrettier干渉                                                                                                                                                                                                                                                                                                                                                       |
| 📦 スキル設計             | Collaborative First, Script Firstメトリクス, 詳細情報分離, 大規模DRYリファクタリング, **クロススキル・マルチスキル・外部CLI 3軸同時設計**                                                                                                                                                                                                                                                                                                                                                                                                                                                    | -                                                                                                                                                                                                                                                                                                                                                                                  |
| 🔗 SDK統合                | TypeScriptモジュール解決による型安全統合, **SDKテストTODO一括有効化**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | カスタムdeclare moduleとSDK実型共存, 未タスク配置ディレクトリ混同                                                                                                                                                                                                                                                                                                                  |
| 🔧 ビルド・環境           | **モノレポ三層モジュール解決整合**, **TypeScript paths定義順序制御**, **ソース構造二重性パスマッピング吸収**, **CIガードスクリプトによるモノレポ設定ファイル整合性自動検証**, **正規表現ベースTypeScript設定ファイルパーサー**, **Worktree環境初期化プロトコル**                                                                                                                                                                                                                                                                                                                               | ネイティブモジュールNODE_MODULE_VERSION不一致, **4ファイル同期漏れ**, **TypeScript設定ファイル完全AST解析の試行**                                                                                                                                                                                                                                                                  |
| 🔄 型定義リファクタリング | deprecatedプロパティ段階的移行                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | ドキュメント偏重による実装検証省略                                                                                                                                                                                                                                                                                                                                                 |
| 🎨 UI/フロントエンド      | **Props駆動Atoms設計**, **Record型バリアント定義**, **テーマ横断テスト（describe.each）**, **データ駆動UIパターン（定数配列+map+条件付きレンダリング）**, **Zustand個別セレクタ+happy-dom fireEventテスト統合**                                                                                                                                                                                                                                                                                                                                                                                    | **HTMLAttributes Props型衝突**, **Props命名の仕様-実装間ドリフト**                                                                                                                                                                                                                                                                                                                 |

## 成功パターン

成功した実行から学んだベストプラクティス。

### [IPC/Auth] APIキー連動3点セット同期（TASK-FIX-APIKEY-CHAT-TOOL-INTEGRATION-001）

- **状況**: Settings で APIキーを更新しても `ai.chat` の実行経路が旧状態を参照し、`saved` と `env-fallback` の表示も曖昧になる
- **アプローチ**:
  - `llm:set-selected-config` で Renderer 選択状態を Main へ同期する
  - `apiKey:save/delete` 成功後に `LLMAdapterFactory.clearInstance(provider)` を実行する
  - `auth-key:exists` を `{ exists, source }` へ拡張し、UI は `source` 優先表示に統一する
  - 仕様同期は `interfaces-auth` / `llm-ipc-types` / `api-ipc-system` / `security-electron-ipc` / `ui-ux-settings` / `task-workflow` / `lessons-learned` の7仕様書を同一ターンで実施する
- **結果**: 実行経路、鍵更新反映、状態表示のドリフトを同時に解消し、同種課題の初動を短縮
- **再確認運用**:
  - Phase 12 再監査では `verify-all-specs` / `validate-phase-output --phase 12` / `validate-phase12-implementation-guide` / `validate-phase11-screenshot-coverage` を同一セットで再実行する
  - 未タスク監査は `audit --diff-from HEAD` の `currentViolations` を合否判定に使い、`baselineViolations` は legacy 監視として分離記録する
- **適用条件**: APIキー保存とチャット実行が別経路で管理される IPC/UI タスク
- **失敗パターン**:
  - `apiKey:save` の永続化のみ更新して cache clear を実装しない
  - `auth-key:exists` を boolean のまま維持し、判定根拠を UI へ返さない
  - `task-workflow` のみ更新して domain spec（interfaces/api-ipc/security/ui）を未同期にする
- **発見日**: 2026-03-11
- **関連タスク**: TASK-FIX-APIKEY-CHAT-TOOL-INTEGRATION-001

### [Phase12] 証跡テーブル互換 + screenshot preflight 固定（TASK-FIX-SETTINGS-APIKEY-CONTRACT-GUARD-001）

- **状況**: `validate-phase11-screenshot-coverage` が `manual-test-result.md` から証跡列を抽出できず失敗し、さらに screenshot 再取得時に optional dependency 欠落で停止
- **アプローチ**:
  - Phase 11 成果物に validator互換ヘッダ（`テストケース` / `証跡`）を固定
  - screenshot 再取得前に `pnpm install` を preflight 実行
  - 取得後に `validate-phase11-screenshot-coverage` を再実行し、`expected=covered` を確認
- **結果**: screenshot 証跡監査を PASS 化し、Phase 12 の再確認を機械判定できる状態へ復帰
- **適用条件**: Phase 11で手動テスト証跡を運用する全 workflow
- **発見日**: 2026-03-08
- **関連タスク**: 06-TASK-FIX-SETTINGS-APIKEY-CONTRACT-GUARD-001

### [Phase12] 未タスク参照の canonical path 固定（TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001）

- **状況**: Phase 12 Task 4 で残課題を検出しても、`light-theme-*/` の workflow ディレクトリ参照だけで管理し、`docs/30-workflows/unassigned-task/` の正式指示書作成が抜ける
- **アプローチ**:
  - 残課題を `docs/30-workflows/unassigned-task/` へ 9見出しフォーマットで正式起票する
  - `task-workflow.md` / `ui-ux-design-system.md` の関連タスク参照を、workflow ディレクトリではなく未タスク指示書ファイルへ同期する
  - `audit-unassigned-tasks --json --diff-from HEAD --target-file <new-file>` を各新規ファイルに対して実行し、`currentViolations=0` を確認する
  - `unassigned-task-detection.md` に件数と監査値（current/baseline）を同値転記する
- **結果**: 「検出レポートはあるが正式未タスクがない」状態を防ぎ、Phase 12 の追跡性を維持できる
- **適用条件**: UI再監査や token 修正で follow-up 課題を検出したが、実装タスク本体で完了しない場合
- **発見日**: 2026-03-11
- **関連タスク**: TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001

### [Phase12] 画面検証で露出した副次不具合の即時未タスク化 + 3.5 節継承（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: 代表画面の screenshot 再取得中に、主タスクとは別の light theme contrast / React key warning / rollout 漏れが露出し、親 task だけ直しても再発防止にならない
- **アプローチ**:
  - screenshot 証跡から露出した副次不具合を、その場で `docs/30-workflows/unassigned-task/` に正式な未タスクとして起票する
  - 親タスクに苦戦箇所がある場合、新規未タスクへ `### 3.5 実装課題と解決策` を追加して再発条件と解決策を継承する
  - `verify-unassigned-links` を `missing=0` まで閉じ、`existing/missing/current/baseline` を `spec-update-summary.md` / `unassigned-task-detection.md` / `task-workflow.md` へ同値転記する
- **結果**: screenshot 由来の副次不具合が evidence のまま放置されず、未タスク台帳と system spec の両方に再利用可能な形で残る
- **適用条件**: ユーザーが画面検証を明示要求し、再撮影過程で本筋以外の不具合や warning を見つけた Phase 12 再監査
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [Phase12] 既存未タスク再参照時の target-file 監査固定（TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001）

- **状況**: `unassigned-task-detection.md` で「新規0件 / 既存再参照あり」と判定しても、再参照先の既存未タスク本文が10見出し要件を満たさず `currentViolations>0` になる場合がある
- **アプローチ**:
  - `audit-unassigned-tasks --json --diff-from HEAD` で全体合否（current/baseline）を確認した後、再参照した既存未タスクへ `--target-file` を個別実行する
  - 個別監査で current違反が出た場合は、同ターンで9/10見出し要件へ是正し、再監査で `currentViolations=0` を固定する
  - `verify-unassigned-links` の total は固定値を使わず同一ターン実測値を `unassigned-task-detection.md` / `documentation-changelog.md` / system spec に同値転記する
- **結果**: 「新規未タスクは0件だが、再参照先の品質が崩れている」取りこぼしを防げる
- **適用条件**: Phase 12 で既存未タスク再利用を選択した全タスク
- **失敗パターン**:
  - diff監査のみで完了判定し、再参照タスク本文の品質監査を省略する
  - `verify-unassigned-links` 件数を過去値のまま転記し、current実測と不一致になる
- **発見日**: 2026-03-14
- **関連タスク**: TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001

### [Phase12] 契約テストと回帰テストの責務分離（TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001）

- **状況**: design/spec_created タスクで Phase 4（契約テスト仕様）と Phase 6（回帰テスト仕様）を同時に書く際、同一ロジックを重複検証して保守コストが増える
- **アプローチ**:
  - Phase 4 は「単一関数の入出力契約（引数・戻り値・例外）」に限定する
  - Phase 6 は「イベント伝播・状態遷移・複数コンポーネント連携」の回帰に限定する
  - `phase-4-test-creation.md` / `phase-6-test-expansion.md` を grep 比較し、重複テスト ID（例: `TC-C*` と `MR-*`）を同一ターンで棚卸しする
  - 責務分離ができない場合は未タスクを即時起票し、`task-workflow` / `lessons-learned` / workflow spec を同一 wave で更新する
- **結果**: テスト種別の責務境界が明確になり、重複テストの管理負荷を先回りで抑制できる
- **適用条件**: 実装より先にテスト仕様を定義する design/spec_created タスク
- **失敗パターン**:
  - 契約テストと回帰テストで同一入力パターンをそのまま重複検証する
  - 重複を検出しても未タスク化せず、次タスクへ暗黙持ち越しにする
- **発見日**: 2026-03-14
- **関連タスク**: TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001

### [Skill] Collaborative First による要件明確化

- **状況**: ユーザーの要求が抽象的（L1/L2レベル）
- **アプローチ**: AskUserQuestion でインタビューを実施し、段階的に具体化
- **結果**: 要件の認識齟齬を防ぎ、手戻りを削減
- **適用条件**: 抽象度が高い要求、複数の解釈が可能な場合
- **発見日**: 2026-01-15

### [Skill] Script First によるメトリクス収集

- **状況**: フィードバック分析でデータ収集が必要
- **アプローチ**: collect_feedback.js でメトリクスを収集し、LLMは解釈のみ担当
- **結果**: 100%正確なデータに基づく改善提案が可能
- **適用条件**: 定量的なデータが必要な処理
- **発見日**: 2026-01-13

### [Skill] 詳細情報の分離によるSKILL.md最適化

- **状況**: SKILL.mdが500行制限を超過（521行）
- **アプローチ**:
  - Part 0.5: 詳細フローチャートをexecution-mode-guide.mdへ移動（86行→30行）
  - scripts/: 5テーブルを1テーブル+参照リンクへ統合（54行→14行）
- **結果**: 521行→420行に削減（101行削減、19.4%減）
- **適用条件**: Progressive Disclosure対象の詳細情報が肥大化した場合
- **発見日**: 2026-01-20

### [Skill] 大規模DRYリファクタリング

- **状況**: SKILL.md 481行、interview-user.md 398行と肥大化
- **アプローチ**:
  - SKILL.md: 詳細ワークフローをreferencesに委譲、エントリポイントと参照のみに
  - orchestration-guide.md: 実行モデル重複をworkflow-patterns.mdへの参照に
  - interview-user.md: 質問テンプレートをinterview-guide.mdへの参照に
- **結果**: SKILL.md 69%削減（481→149行）、interview-user.md 52%削減（398→191行）
- **適用条件**: 300行超のファイルで詳細とサマリーが混在している場合
- **発見日**: 2026-01-24

### [Skill] クロススキル・マルチスキル・外部CLI拡張の3軸同時設計

- **状況**: skill-creator v10.0.0で3つの大機能（クロススキル依存関係、外部CLIエージェント、マルチスキル同時設計）を同時追加
- **アプローチ**:
  - 各機能を独立したエージェント（resolve-skill-dependencies / delegate-to-external-cli / design-multi-skill）に分離
  - 共通のインターフェースをinterview-result.jsonスキーマの拡張フィールドとして定義
  - select-resources.mdの選択マトリクス（4.1.7 / 4.1.8）を追加して既存パイプラインに統合
  - 静的依存グラフ（skill-dependency-graph.json）とランタイム設定（externalCliAgents）を明確に分離
  - Meshパターンは単方向DAGとして表現（参照タイプ分離で双方向に見える関係を実現）
- **結果**: 既存のPhaseパイプラインを壊さず3つの大機能を統合。エージェント間の責務が明確で相互干渉なし
- **適用条件**: 既存スキルに複数の独立した大機能を同時追加する場合
- **教訓**:
  - スキーマを先に定義してからエージェントを実装すると整合性が高い
  - 新機能のインタビューPhaseにはスキップ条件を付けてユーザー負担を軽減する
  - セキュリティ面では `execFileSync` + 引数配列（シェルインジェクション防止）が必須
  - 4エージェント並列レビュー（16思考法）で設計矛盾を早期発見できた
- **発見日**: 2026-02-13
- **関連バージョン**: v10.0.0

### [Phase12] Phase仕様書の成果物名厳密化

- **状況**: Phase 12実行時に仕様書と異なるファイル名で成果物を生成
- **アプローチ**:
  - Phase仕様書の成果物セクションにファイル名パターンを明記
  - 実行前に成果物一覧を確認するチェックリストを追加
- **結果**: 仕様書どおりの成果物が生成され、検証が容易に
- **適用条件**: Phase実行時、特に複数成果物を持つPhase
- **発見日**: 2026-01-22
- **関連タスク**: SHARED-TYPE-EXPORT-01

### [Phase12] スキル間ドキュメント整合性の定期確認

- **状況**: task-specification-creatorのSKILL.mdとreferences/artifact-naming-conventions.mdでPhase 12成果物リストが不整合
- **アプローチ**:
  - SKILL.mdの成果物定義を正とし、references/を同期
  - 改善作業時に関連ドキュメントの整合性を確認
- **結果**: artifact-naming-conventions.mdにPhase 12の3成果物（implementation-guide.md, documentation-changelog.md, unassigned-task-report.md）を追加
- **適用条件**: スキル改善時、バージョンアップ時
- **発見日**: 2026-01-22
- **関連タスク**: SHARED-TYPE-EXPORT-01

### [Phase12] 成果物実体と `phase-12-documentation.md` 状態の二重突合

- **状況**: `outputs/phase-12` の必須成果物は全件存在するが、`phase-12-documentation.md` のステータスが `pending` のまま残るドリフトが発生
- **アプローチ**:
  - Task 12-1〜12-5 の成果物実在を先に機械確認
  - `verify-all-specs` と `validate-phase-output` を再実行し、PASS値を固定
  - 最後に `phase-12-documentation.md` の `ステータス` と完了チェックリスト2箇所を同期
- **結果**: 「成果物はあるが仕様書上は未完了」という誤判定を防止し、Phase 12の完了状態を一貫化
- **適用条件**: 再監査・追補で成果物追加後に仕様書状態が取り残される可能性がある場合
- **発見日**: 2026-03-05
- **関連タスク**: TASK-FIX-SKILL-EXECUTOR-AUTHKEY-DI-001

### [Phase12] workflow index / artifacts 二重同期（TASK-UI-02）

- **状況**: `phase-12-documentation.md` と `artifacts.json` は completed 側へ揃っていても、`outputs/artifacts.json` 未作成や `index.md` 未再生成で workflow 全体が「未実施」に見えることがある
- **アプローチ**:
  - `artifacts.json` 更新後に `outputs/artifacts.json` を同内容で同期する
  - `node .claude/skills/task-specification-creator/scripts/generate-index.js --workflow <workflow-path> --regenerate` を実行し、`index.md` の Phase 1-12 / 13 表示を再生成する
  - `phase-12-documentation.md` / `artifacts.json` / `outputs/artifacts.json` / `index.md` を四点セットで突合する
- **結果**: 「成果物はあるが workflow index 上は未実施」というドリフトを防止し、再監査の初手で迷わなくなる
- **適用条件**: Phase 12 完了後、または再監査で workflow 状態表示に違和感がある場合
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-02-GLOBAL-NAV-CORE

### [Phase12] `generate-index` schema 互換監査 + 壊れた index の即時未タスク化

- **状況**: `node .claude/skills/task-specification-creator/scripts/generate-index.js --workflow <workflow-path> --regenerate` 実行後、workflow ごとの `artifacts.json` schema 差異により `index.md` が `undefined` 表示や全 Phase 未実施へ壊れることがある
- **アプローチ**:
  - `generate-index` 実行後に `index.md` の Phase 12/13 表示だけでなく、`undefined` 混入や成果物件数の崩れを即時確認する
  - `phase-12-documentation.md` / `artifacts.json` / `outputs/artifacts.json` / `index.md` を四点突合し、generator 出力を盲信しない
  - generator 側修正が current task の責務外なら、workflow は手動で正本へ戻し、汎用改善は `docs/30-workflows/unassigned-task/` に未タスク化する
  - `task-workflow.md` と `lessons-learned.md` に、手動復旧した事実と generator/schema 互換改善が別課題であることを同一ターンで記録する
- **結果**: completed workflow を自動再生成で再破壊する連鎖を止め、局所修復と汎用改善の責務分離を維持できる
- **適用条件**: `generate-index` 実行後の `index.md` が `artifacts.json` と一致しない場合、または workflow 間で `artifacts.json` schema 差異が疑われる場合
- **発見日**: 2026-03-10
- **関連タスク**: UT-IMP-TASK-SPEC-GENERATE-INDEX-SCHEMA-COMPAT-001

### [Phase12] 完了済み未タスク指示書の配置整合（残置防止）

- **状況**: 機能実装完了後も、対応済みの未タスク指示書が `docs/30-workflows/unassigned-task/` に残り、運用上「未完了」と誤認される
- **アプローチ**:
  - Phase 12完了時に、完了済みの未タスク指示書を `docs/30-workflows/completed-tasks/unassigned-task/` へ移管
  - `task-workflow.md` / 関連interfaces仕様書 / workflow index の参照パスを同時更新
  - `artifacts.json` と phase-12成果物（監査レポート含む）を最終整合チェック
- **結果**: 未タスク台帳の状態と実ファイル配置が一致し、完了/未完了の判定ミスを抑制
- **適用条件**: 未タスクを起票した機能タスクが完了し、Phase 12の文書化を実施するタイミング
- **発見日**: 2026-02-12
- **関連タスク**: UT-9B-H-003

### [Phase12] 未実施タスク配置ドリフト是正（completed-tasks/unassigned-task → unassigned-task）

- **状況**: 未実施タスク指示書が `docs/30-workflows/completed-tasks/unassigned-task/` に残り、`task-workflow.md` / 関連仕様書リンクと不整合になる
- **アプローチ**:
  - `completed-tasks/unassigned-task/` 配下の指示書をステータスで分類し、`未着手|未実施|進行中` は `docs/30-workflows/unassigned-task/` に配置
  - `task-workflow.md` と関連仕様（例: `api-ipc-agent.md`）の参照を `docs/30-workflows/unassigned-task/` に統一
  - `node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js` 実行でリンク整合を検証
- **結果**: 未タスク台帳と物理配置が一致し、Phase 12監査時の誤判定を防止
- **適用条件**: 未タスク再監査、完了済み移管作業、参照修正を同時に行うPhase 12
- **発見日**: 2026-02-20
- **関連タスク**: UT-FIX-SKILL-REMOVE-INTERFACE-001

### [Phase12] dual skill-root repository の canonical root + mirror sync

- **状況**: repository に `.claude/skills/...` と `.agents/skills/...` の二重 root があり、user は前者を正本として要求している一方、workflow や旧成果物が後者を参照している
- **アプローチ**:
  - 先に user 指定root を canonical root として固定し、system spec / skill 改善 / validator 実行もその root で行う
  - 完了前に `diff -qr` または `rsync --checksum` で mirror root を同期し、古い参照経路との drift を残さない
  - `spec-update-summary.md` / `documentation-changelog.md` / `skill-feedback-report.md` に canonical root と mirror sync の両方を記録する
- **結果**: user 指定の正本を守りつつ、既存 workflow が参照する mirror root も stale にしない Phase 12 運用を固定できる
- **適用条件**: skill root が複数ある repository、または `.claude` / `.agents` のような実体ミラーを併用する task
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-07-DASHBOARD-ENHANCEMENT

### [Architecture] 既存アダプターパターンの活用（新規API統合時）

- **状況**: システムプロンプトのLLM API統合時、仕様書ではVercel AI SDK使用を提案
- **アプローチ**:
  - 既存のLLMAdapterFactoryパターンを調査・活用
  - 新規SDKを追加せず、既存アダプター経由で4プロバイダー（OpenAI, Anthropic, Google, xAI）に対応
  - buildMessages()でシステムプロンプトをLLMMessage[]に変換
- **結果**: 既存アーキテクチャとの一貫性を維持、依存関係を最小化、54テスト全PASS
- **適用条件**: LLM機能追加時、外部API統合時
- **発見日**: 2026-01-23
- **関連タスク**: TASK-CHAT-SYSPROMPT-LLM-001

### [Phase12] システム仕様書への完了タスク記録

- **状況**: Phase 12 Task 2でシステム仕様書更新が必要
- **アプローチ**:
  - 該当するinterfaces-\*.mdに「完了タスク」セクションを追加
  - タスクID、概要、実装日、主要成果を記録
  - 「関連ドキュメント」に実装ガイドリンクを追加
- **結果**: タスク完了の追跡可能性が向上、後続開発者が実装履歴を把握可能
- **適用条件**: Phase 12実行時、機能追加完了時
- **発見日**: 2026-01-23
- **関連タスク**: TASK-CHAT-SYSPROMPT-LLM-001

### [Phase12] Phase 12 Task 2の見落とし防止

- **状況**: Phase 12 Task 2（システム仕様書更新）が実行されずにPhase 12完了とマークされた
- **アプローチ**:
  - phase-templates.mdのPhase 12完了条件に明示的チェックリスト追加
  - 【Phase 12-2 Step 1】等のプレフィックス付与で視認性向上
  - spec-update-workflow.mdへの参照リンクをテンプレート内に埋め込み
  - フォールバック手順セクションを追加
- **結果**: 2ステップ（タスク完了記録＋システム仕様更新）の実行漏れを防止
- **適用条件**: Phase 12実行時、特に複数サブタスクを持つPhase
- **発見日**: 2026-01-22
- **関連タスク**: UT-007 ChatHistoryProvider App Integration

### [Phase12] 未タスク参照リンクの実在チェック

- **状況**: `task-workflow.md` に未タスクを登録したが、`docs/30-workflows/unassigned-task/` に実体ファイルがなく参照切れになる
- **アプローチ**:
  - 未タスク登録後に `node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js` を実行
  - `missing > 0` の場合は Phase 12 を完了扱いにしない
  - 完了タスクへ移動した場合は `task-workflow.md` の参照先を `completed-tasks/` 側に更新
- **結果**: 未タスク探索時のリンク切れを事前に排除し、後続タスクの追跡性を維持
- **適用条件**: Phase 12で未タスクを新規作成・更新した場合、または完了移動を行った場合
- **発見日**: 2026-02-12
- **関連タスク**: UT-FIX-AGENTVIEW-INFINITE-LOOP-001

### [Phase12] 仕様書参照パスの実在チェック

- **状況**: Phase 12で更新対象仕様書に `api-ipc-skill.md` など非実在パスが残り、参照先を誤認した
- **アプローチ**:
  - Step 1-B開始前に、更新対象として列挙した仕様書パスを `test -f <path>` で全件検証する
  - 非実在パスを検出した場合は、同ドメインの正本（例: `interfaces-agent-sdk-skill.md`）へ即時置換する
  - 置換後に `generate-index.js` を再実行して索引を同期する
- **結果**: 参照正本の取り違えを防ぎ、Phase 12 Task 2 の更新漏れを削減
- **適用条件**: 仕様書更新対象ファイルを手動列挙するタスク全般
- **発見日**: 2026-02-14
- **関連タスク**: UT-FIX-IPC-RESPONSE-UNWRAP-001

### [Phase12] Phase 12 Step 1 検証スクリプトによる自動化

- **状況**: Phase 12 Step 1（必須タスク完了記録）が正しく実行されたか手動確認が困難
- **アプローチ**:
  - `validate-phase12-step1.js` スクリプトを作成し、必須要件を自動検証
  - 検証項目: 完了タスクセクション、実装ガイドリンク、変更履歴エントリ
  - SKILL.mdに検証コマンドを追加し、Phase 12完了前に実行を促す
- **結果**: 必須要件の漏れを自動検出、Phase 12完了前に問題を発見可能
- **適用条件**: Phase 12 Task 12-2 実行時、システム仕様書更新後の検証
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03
- **検証コマンド**: `node .claude/skills/task-specification-creator/scripts/validate-phase12-step1.js --workflow <dir> --spec <file>`

### [Phase12] 複数システム仕様書への横断的更新

- **状況**: 単一タスクが複数の仕様書に関連する場合の更新漏れ
- **アプローチ**:
  - 関連仕様書を事前にリストアップ（例: interfaces-rag-community-detection.md + architecture-monorepo.md）
  - 各仕様書に対して Phase 12 Step 1 検証スクリプトを実行
  - spec-update-record.md に全更新対象を明記
- **結果**: 関連する全仕様書に一貫した完了タスク記録と実装ガイドリンクを追加
- **適用条件**: アーキテクチャ横断的な実装タスク、型エクスポート/インポートパターン変更時
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03

### [Phase12] 実装差分ベース文書化（ファイル名誤記防止）

- **状況**: Phase 12の実装ガイド/レビュー資料に、実際には変更していないファイル名が混入しやすい
- **アプローチ**:
  - 文書作成前に `git diff --name-only` で変更対象ファイルを確定
  - `implementation-guide.md` と `final-review-report.md` の対象ファイル欄を差分一覧と突合
  - 差分に存在しないファイル名が出た場合は記載を削除し、実装事実に合わせて再記述
- **結果**: 文書と実装の不整合を防止し、Phase 12監査の再作業を削減
- **適用条件**: リファクタリング系タスクや大量ファイル編集タスクで、成果物に対象ファイル一覧を記載する場合
- **発見日**: 2026-02-14
- **関連タスク**: TASK-FIX-14-1-CONSOLE-LOG-MIGRATION

### [Phase12] 実装-仕様ドリフト再監査（数値・パス・文言）

- **状況**: Phase 12完了後の再監査で、仕様書のテスト件数・Preload公開先パス・エラーメッセージ表が実装とずれていた
- **アプローチ**:
  - テスト件数は再実行結果（CIログまたはローカル実測）を唯一の正として更新
  - `rg -n` で旧パス（例: `skill-file-api.ts`）や旧文言を横断検索し、関連仕様書を一括修正
  - 未タスク検出は raw 件数と確定件数を分離して記録し、既存未タスク管理との重複を除外
- **結果**: Phase 12成果物の監査再作業を削減し、実装事実と仕様の整合性を維持
- **適用条件**: IPC機能追加・ハンドラー追加など、仕様書更新ファイルが3件以上に跨るタスク
- **発見日**: 2026-02-19
- **関連タスク**: TASK-9A-B

### [Phase12] 仕様更新三点セット（quality/task-workflow/lessons-learned）

- **状況**: Phase 12で実装内容を1ファイルだけに反映すると、運用ルール・完了記録・教訓が分断されやすい
- **アプローチ**:
  - `quality-requirements.md` に「今後守るべき運用ルール」を追記
  - `task-workflow.md` に「今回何を実装し、どこで苦戦したか」を完了タスクとして記録
  - `lessons-learned.md` に「同種課題の簡潔解決手順（再利用手順）」を記録
  - 3ファイル更新後に `generate-index.js` を実行して索引を同期
- **結果**: 仕様の「ルール」「履歴」「再利用ノウハウ」が分離されず、後続タスクの調査コストを削減
- **適用条件**: テスト戦略・運用方針・ドキュメント運用が同時に変わるタスク（特にPhase 12 Step 2を伴う変更）
- **発見日**: 2026-02-19
- **関連タスク**: TASK-FIX-10-1-VITEST-ERROR-HANDLING
- **クロスリファレンス**: [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase12] spec-update-summary + artifacts二重台帳同期

- **状況**: `documentation-changelog.md` は存在するが、`spec-update-summary.md` 未作成や `artifacts.json` / `outputs/artifacts.json` 非同期が発生しやすい
- **アプローチ**:
  - `phase-12-documentation.md` の成果物表と `outputs/phase-12/` 実体を1対1で突合する
  - `spec-update-summary.md` を Step 1-A〜3 の証跡ファイルとして必須作成する
  - `artifacts.json` と `outputs/artifacts.json` を同一内容に同期し、completed成果物の参照切れをゼロ化する
  - 同期後に `validate-phase-output.js` と `verify-all-specs.js` を再実行する
- **結果**: Phase 12 完了判定の再現性が上がり、成果物不足・台帳ズレの再発を防止
- **適用条件**: 仕様書修正のみタスクを含む全ての Phase 12
- **発見日**: 2026-02-24
- **関連タスク**: UT-IPC-DATA-FLOW-TYPE-GAPS-001

### [Phase12] 実装ガイド2パート要件ギャップの即時是正

- **状況**: `implementation-guide.md` は存在するが、Part 1 の日常例え・理由先行説明、Part 2 の型/API/エッジケースが不足していることがある
- **アプローチ**:
  - Part 1 は「なぜ必要か」を先に書き、日常生活の例えを必須で入れる
  - Part 2 は最小でも「型定義」「APIシグネチャ」「エラーハンドリング」「設定項目」を明示する
  - `phase-12-documentation.md` の完了チェックと `implementation-guide.md` 本文を同一コミットで同期する
- **結果**: Task 1 要件未達による差し戻しを防ぎ、Phase 12 完了判定の再現性が上がる
- **適用条件**: Phase 12 Task 1 を含む全タスク（特に再監査タスク）
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-IPC-RESPONSE-CONSISTENCY-001

### [Phase12] 仕様書作成タスクの `spec_created` 状態判定

- **状況**: Phase 12 Step 1-B で、実装未着手タスクまで `completed` と記録しやすい
- **アプローチ**:
  - タスクを「実装完了」と「仕様書作成済み（未実装）」に分岐して判定
  - 実装完了は `completed`、仕様書のみは `spec_created` を使用
  - `tasks/index.md`・`completed-task/*.md`・関連workflow indexの3点を同時更新
- **結果**: 実装進捗と仕様進捗の状態混同を防止
- **適用条件**: Phase 12でドキュメント成果物のみ先行して完了するタスク
- **発見日**: 2026-02-19
- **関連タスク**: TASK-9A-C

### [Phase12] IPCドキュメント契約同期（Main/Preload準拠）

- **状況**: `ipc-documentation.md` が存在しても、`skillHandlers.ts` / `skill-api.ts` の引数・戻り値契約とズレることがある
- **アプローチ**:
  - Main (`skillHandlers.ts`) と Preload (`skill-api.ts`) を一次情報に固定し、チャネルごとの入力/出力/エラー契約を表で同期する
  - 特に Profile A/B/C の返却形式と `sanitizeErrorMessage()` の適用範囲を明示する
  - 同期後に契約テスト（Main contract + Preload contract）を再実行して回帰を確認する
- **結果**: API利用者の誤実装を防ぎ、Phase 12 再監査時の差し戻しを減らせる
- **適用条件**: IPCハンドラ・Preload契約を更新したタスクの Phase 12 Step 2
- **発見日**: 2026-02-27
- **関連タスク**: UT-FIX-SKILL-IPC-RESPONSE-CONSISTENCY-001

### [Phase12] IPC追加時の登録配線突合（handler/register/preload）

- **状況**: 新規IPCハンドラを実装しても `ipc/index.ts` 側の登録が漏れ、実行時にチャネルが無効化されることがある
- **アプローチ**:
  - `handler` 実装、`register` 配線、`preload` 公開を1セットで確認する
  - `rg -n "register<Feature>Handlers|skill:<feature>:"` で登録とチャネルの両方を機械確認する
  - 仕様書は Preload API 実装名を正本として同期する（命名ドリフト防止）
- **結果**: 「実装済みなのに起動しない」類のIPC欠陥を早期に検出できる
- **適用条件**: IPCチャネル新規追加、または既存チャネルを専用ハンドラへ分割するタスク
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J

### [IPC] サービスバレル公開整合チェック（UT-IMP-SKILL-CHAIN-BARREL-EXPORT-CONSISTENCY-001）

- **状況**: `registerAllIpcHandlers` の配線を修正して機能は復旧したが、依存サービス（`SkillChainStore` / `SkillChainExecutor`）が `services/skill/index.ts` から未公開のまま残り、直接 import が固定化した
- **アプローチ**:
  - IPC登録修正時に `services/<domain>/index.ts` の export 更新有無を同時確認する
  - `rg -n "services/skill/SkillChain(Store|Executor)|from \"../services/skill\"" apps/desktop/src/main` で直接 import とバレル import を機械比較する
  - 今回Waveで対応しない場合は Phase 12 Task 4 で未タスク化し、`task-workflow.md` の関連未タスクへリンクする
- **結果**: 機能修復と設計整合性の境界を分離して管理でき、後続Waveでの再実装コストを抑制できる
- **適用条件**: IPCハンドラ追加・登録修正時に新規サービス依存を導入したタスク
- **発見日**: 2026-03-03
- **関連タスク**: UT-IMP-SKILL-CHAIN-BARREL-EXPORT-CONSISTENCY-001

### [Testing] E2EテストでのARIA属性ベースセレクタ優先

- **状況**: Playwrightでドロップダウンコンポーネントをテストする際のセレクタ選定
- **アプローチ**:
  - CSSクラスやdata-testid属性の代わりにARIA属性（`role="combobox"`, `role="listbox"`, `role="option"`）を優先使用
  - `page.getByRole()` APIで要素を取得
  - アクセシビリティ検証とE2Eテストを同時に実現
- **結果**: アクセシビリティ準拠の確認とテスト安定性の両立（CSSクラス変更に強い）
- **適用条件**: UI E2Eテスト、特にフォームコントロールやナビゲーション要素
- **発見日**: 2026-02-02
- **関連タスク**: TASK-8C-B

### [Testing] E2Eヘルパー関数による操作シーケンスの分離

- **状況**: 複数のE2Eテストで同じ操作シーケンス（スキル選択、ドロップダウン開閉など）が重複
- **アプローチ**:
  - 共通操作をヘルパー関数として抽出（`openSkillDropdown()`, `selectSkillByName()`等）
  - テストファイル先頭またはユーティリティファイルに配置
  - 各テストケースはヘルパー関数を呼び出して操作を実行
- **結果**: DRY原則の適用、保守性向上、テスト可読性向上
- **適用条件**: E2Eテストで3回以上繰り返される操作シーケンス
- **発見日**: 2026-02-02
- **関連タスク**: TASK-8C-B

### [Testing] E2E安定性対策3層アプローチ

- **状況**: E2Eテストでフレーキー（不安定）なテスト結果が発生
- **アプローチ**:
  - 層1: 明示的待機（`waitForSelector`, `waitForFunction`）
  - 層2: UI安定化待機（アニメーション完了、ローディング状態解消）
  - 層3: DOMロード待機（`networkidle`, `domcontentloaded`）
- **結果**: テスト成功率100%、CI環境での安定動作
- **適用条件**: アニメーション、非同期データ取得、動的コンテンツを含むE2Eテスト
- **発見日**: 2026-02-02
- **関連タスク**: TASK-8C-B

### [Auth] 既実装済み修正の発見パターン（AUTH-UI-001）

- **状況**: バグ修正タスクで、調査中に既に修正が実装済みであることを発見
- **アプローチ**:
  - Step 1: 問題の再現を試みる前に、まず関連コードを詳細に調査
  - Step 2: 修正コードの存在確認（z-index、フォールバック処理、状態更新フロー）
  - Step 3: 既存実装の動作検証で問題解決を確認
- **結果**: 不要な実装作業を回避、Phase 12の文書化と知識共有に注力
- **適用条件**: バグ修正タスク、Issue報告から時間が経過している場合
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001

### [Testing] テスト環境問題と実装コード切り分けパターン（AUTH-UI-001）

- **状況**: 33件のテストが失敗しているが、実装コード自体は正常動作
- **アプローチ**:
  - Step 1: テスト失敗のエラーメッセージを分析（`handler not registered`等）
  - Step 2: 本番環境での動作確認で実装の正常性を検証
  - Step 3: テスト環境問題として切り分け、未タスク（UT-AUTH-001）として登録
- **結果**: 実装の品質担保とテスト環境問題の適切な分離
- **適用条件**: テスト失敗がモック環境に起因する場合、本番動作が正常な場合
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001, UT-AUTH-001

### [UI] React Portalによるz-index問題解決パターン（AUTH-UI-001）

- **状況**: ドロップダウンメニューが他の要素の下に隠れる（z-indexだけでは解決不可）
- **アプローチ**:
  - 問題: CSSのスタッキングコンテキストにより、子要素のz-indexが親の範囲内に制限される
  - 解決: React Portalで`document.body`直下にレンダリングし、DOM階層から切り離す
  - 実装: `createPortal(<DropdownContent className="z-[9999]" />, document.body)`
- **結果**: z-[9999]がグローバルに機能し、確実に最前面表示
- **適用条件**: モーダル、ドロップダウン、ツールチップ等のオーバーレイUI
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001

### [Auth] Supabase認証状態変更後の即時UI更新パターン（AUTH-UI-001）

- **状況**: 認証状態変更（リンク/解除）後にUIが即座に更新されない
- **アプローチ**:
  - 問題: `onAuthStateChange`イベント後にプロバイダー情報を再取得していない
  - 解決: 認証状態変更時に`fetchLinkedProviders()`を明示的に呼び出す
  - 実装場所: `authSlice.ts`の認証イベントハンドラ内（行342-345付近）
- **結果**: OAuth連携操作後に即座にUI状態が反映
- **適用条件**: Supabase Auth + Zustand状態管理の組み合わせ
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001

### [Auth] OAuthコールバックエラーパラメータ抽出パターン（TASK-FIX-GOOGLE-LOGIN-001）

- **状況**: OAuthコールバックURL内のエラーパラメータを検出してUIに反映したい
- **アプローチ**:
  - 問題: OAuth implicit flowではエラー情報がURLフラグメント(`#error=...`)に含まれる
  - 解決: `url.substring(url.indexOf('#') + 1)`でフラグメント抽出後、URLSearchParamsでパース
  - 実装: `parseOAuthError()`関数を作成し、`handleAuthCallback`内で呼び出す
- **結果**: ユーザーがOAuthをキャンセルした場合のエラーを検出し、適切なエラーメッセージを表示
- **適用条件**: OAuth implicit flow、カスタムプロトコルコールバック処理
- **発見日**: 2026-02-05
- **関連タスク**: TASK-FIX-GOOGLE-LOGIN-001

### [Auth] Zustandリスナー二重登録防止パターン（TASK-FIX-GOOGLE-LOGIN-001）

- **状況**: initializeAuthが複数回呼ばれるとリスナーが重複登録される
- **アプローチ**:
  - 問題: React Strict ModeやHot Reloadで初期化関数が複数回実行される
  - 解決: モジュールスコープの`authListenerRegistered`フラグで登録状態を追跡
  - テスト対応: `resetAuthListenerFlag()`エクスポート関数で各テスト前にリセット
- **結果**: リスナーの二重登録を防止し、認証状態変更の重複処理を回避
- **適用条件**: Electron IPC + Zustandでの認証状態管理
- **発見日**: 2026-02-05
- **関連タスク**: TASK-FIX-GOOGLE-LOGIN-001

### [IPC] IPC経由のエラー情報伝達設計パターン（TASK-FIX-GOOGLE-LOGIN-001）

- **状況**: Main ProcessのエラーをRenderer側のUIに伝える必要がある
- **アプローチ**:
  - 問題: 既存のIPCイベントペイロードにエラー情報フィールドがない
  - 解決: ペイロード型に`error`, `errorCode`フィールドを追加し、既存のイベントで送信
  - 型拡張: `AuthState`インターフェースに`errorCode?: AuthErrorCode`を追加
- **結果**: 新規チャネル追加なしで、既存の`AUTH_STATE_CHANGED`イベントでエラー伝達
- **適用条件**: Electron IPC設計、エラーハンドリング拡張
- **発見日**: 2026-02-05
- **関連タスク**: TASK-FIX-GOOGLE-LOGIN-001

### IPC Bridge API統一時のテストモック設計パターン（TASK-FIX-5-1）

- **状況**: `window.skillAPI` と `window.electronAPI.skill` の二重定義を統一する際、テストモックの再設計が必要（623行→1092行に膨張）
- **アプローチ**:
  - `vi.hoisted()` でモック定義をファイルスコープの巻き上げ位置に配置
  - フィクスチャファクトリ関数でテストごとにリセット可能なモックを生成
  - パスエイリアス（`@/`）と相対パスの両方に対応するモック配布パターン
- **結果**: テストの保守性向上、モック二重定義の解消、210テスト全PASS
- **適用条件**: Electron Preload APIの変更、IPC Bridge層のリファクタリング
- **発見日**: 2026-02-06
- **関連タスク**: TASK-FIX-5-1-SKILL-API-UNIFICATION
- **関連仕様書**: [architecture-implementation-patterns.md S2](.claude/skills/aiworkflow-requirements/references/architecture-implementation-patterns.md)

### セッション間での仕様書編集永続化検証パターン（TASK-FIX-5-1）

- **状況**: 前セッションで10件の仕様書修正を完了と報告したが、8件がディスクに永続化されていなかった
- **アプローチ**:
  - 大量編集後は `git diff --stat` で変更ファイル数と期待値の一致を検証
  - PostToolUseフック（Prettier/ESLint）によるファイル変更で Edit の `old_string` 不一致が発生する可能性を認識
  - 重要な編集は直後に `git diff <file>` で実際の差分を確認
- **結果**: 全8件の未永続化を発見し再適用、仕様書と実装の完全な整合性を達成
- **適用条件**: 複数セッションにまたがる仕様書更新、Linterフックが有効な環境
- **発見日**: 2026-02-06
- **関連タスク**: TASK-FIX-5-1-SKILL-API-UNIFICATION
- **関連ルール**: [06-known-pitfalls.md P11](.claude/rules/06-known-pitfalls.md)

### Phase 1仕様書作成時の依存仕様書マトリクスパターン（TASK-FIX-5-1）

- **状況**: Phase 1作成時にaiworkflow-requirementsの関連仕様書参照が不足し、後から2コミットで19件修正が必要
- **アプローチ**:
  - Phase 1作成時に「仕様書依存マトリクス」を明示的に作成
  - task-specification-creatorとaiworkflow-requirementsの両方のreferences/を検索し、関連する全仕様書を特定
  - 各Phase仕様書に必要な参照リンクを漏れなく追加
- **結果**: 後付け修正のコスト（2コミット、19件修正）を事前に防止可能
- **適用条件**: 複数の仕様書体系を持つプロジェクトでのタスク仕様書作成時
- **発見日**: 2026-02-06
- **関連タスク**: TASK-FIX-5-1-SKILL-API-UNIFICATION

### [Auth] Supabase SDK自動リフレッシュ競合防止パターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: Supabase SDKの`autoRefreshToken: true`（デフォルト）とカスタムスケジューラーが同時にリフレッシュを試みる
- **アプローチ**:
  - 問題: 2つのリフレッシュ処理が同時実行されると、一方が無効なトークンで実行されエラーになる
  - 解決: `supabaseClient.ts`で`autoRefreshToken: false`を設定し、カスタムスケジューラーに完全に委譲
  - 排他制御: `_isRefreshing`フラグでスケジューラー内の二重実行も防止
- **結果**: リフレッシュ処理の衝突を完全に排除、リトライ戦略を自由にカスタマイズ可能に
- **適用条件**: 外部SDK（Supabase, Firebase等）のデフォルト自動処理をカスタム実装で置き換える場合
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Auth] setTimeout方式 vs setInterval方式の選択パターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: セッションリフレッシュのスケジューリング方式選定
- **アプローチ**:
  - setIntervalの問題: 固定間隔実行のため、リフレッシュ成功で新しいexpiresAtが変わっても間隔が変わらない
  - setTimeout選択理由: リフレッシュ成功時に`reset(newExpiresAt)`で新しいタイマーを設定でき、動的な間隔調整が可能
  - 追加利点: `stop()`で確実にタイマークリア可能、メモリリーク防止
- **結果**: 毎回新しいexpiresAtに基づいた正確なスケジューリングを実現
- **適用条件**: スケジュール間隔が動的に変わる定期処理
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Testing] vi.useFakeTimers + flushPromisesテストパターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: setTimeout + async/await が組み合わさったコードのテストが困難
- **アプローチ**:
  - 問題: `vi.runAllTimersAsync()`はリフレッシュ成功→新タイマー設定→再発火の無限ループを引き起こす
  - 解決: `vi.advanceTimersByTime(ms)` + `flushPromises()`を組み合わせて段階的に制御
  - `flushPromises()`: `for (let i = 0; i < 10; i++) await Promise.resolve()`でmicrotaskキューを消化
  - テスト手順: タイマー進行→Promise解決→アサーション を1ステップずつ実行
- **結果**: 26テスト全PASS、96.15%カバレッジ達成。タイマーと非同期処理の両方を正確にテスト可能
- **適用条件**: setTimeout/setInterval + Promise/async-awaitが混在するコードのユニットテスト
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Auth] Callback DIによるテスタブル設計パターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: TokenRefreshSchedulerからSupabase, SecureStorage, BrowserWindowへの依存を分離したい
- **アプローチ**:
  - 問題: クラス内で直接`supabase.auth.refreshSession()`を呼ぶとモックが困難
  - 解決: `TokenRefreshCallbacks`インターフェースで`onRefresh`, `onFailure`, `onSuccess`をDI
  - スケジューラーは「いつ実行するか」のみに責務を限定、「何を実行するか」は呼び出し側が決定
  - authHandlers.tsのstartTokenRefreshScheduler()でコールバック実装を注入
- **結果**: スケジューラーのテストにSupabaseモック不要、テスト対象が明確に分離
- **適用条件**: 外部サービス呼び出しを含むスケジューラー/タイマー系処理
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Testing] mockReturnValue vs mockReturnValueOnce のテスト間リーク防止パターン（TASK-FIX-17-1）

- **状況**: IPCハンドラーのセキュリティテストで特殊な戻り値を設定する必要があった
- **アプローチ**:
  - 問題: `mockReturnValue` で設定したモック戻り値が後続テストに漏れ、テスト間で状態が共有される
  - 解決: `mockReturnValueOnce` で1回限りのモック設定にする
  - 再初期化: `beforeEach` でモック関数をデフォルト状態にリセット
- **結果**: テスト間の状態分離が実現し、独立したテスト実行が可能に
- **適用条件**: 同一モック関数に対して複数の異なる戻り値パターンをテストする場合
- **発見日**: 2026-02-09
- **関連タスク**: TASK-FIX-17-1-SKILL-SCAN-HANDLER
- **クロスリファレンス**: [06-known-pitfalls.md#P23](../../.claude/rules/06-known-pitfalls.md)

### [IPC/Electron] 横断的セキュリティバイパス検出パターン（UT-FIX-5-3）

- **状況**: IPC APIでセキュリティ検証をバイパスする直接呼び出しが存在（preloadでの`ipcRenderer.send/on`直接使用）
- **アプローチ**:
  - Step 1: `grep -rn "ipcRenderer.send\|ipcRenderer.on" <preload-dir>/` で直接呼び出しを検出
  - Step 2: 検出したチャネル名がホワイトリストに登録されているか確認
  - Step 3: `safeInvoke()` 経由でない呼び出しを未タスクとして登録
  - Step 4: 検出された問題ごとに修正方針（AbortController統合、型定義追加等）を記録
- **結果**: セキュリティ検証バイパスを早期発見、未タスク化で追跡可能に
- **適用条件**: Electron IPC設計、Phase 10アーキテクチャレビュー時、Preloadスクリプト変更時
- **発見日**: 2026-02-09
- **関連タスク**: UT-FIX-5-3-PRELOAD-AGENT-ABORT
- **クロスリファレンス**: [04-electron-security.md](../../.claude/rules/04-electron-security.md), [06-known-pitfalls.md](../../.claude/rules/06-known-pitfalls.md)

### [DI/Architecture] Setter Injectionパターン（遅延初期化DI）（TASK-FIX-7-1）

- **状況**: BrowserWindow等の外部リソースを必要とする依存オブジェクトは、Constructor Injectionで対応できない
- **アプローチ**:
  - 問題: Facadeサービス（SkillService）生成時点で、依存先（SkillExecutor）がまだ初期化できない（mainWindow未生成）
  - 解決: `setXxx(dependency)` Setterメソッドで、外部リソース準備後に依存オブジェクトを注入
  - 検証: 実行メソッド（`executeSkill`）呼び出し時に、依存オブジェクトの存在を検証（未設定時はエラー）
  - 実装例: `SkillService.setSkillExecutor(executor)` で、mainWindow生成後にSkillExecutorを注入
- **結果**: 初期化タイミングが異なる依存オブジェクトを安全に注入可能。Facadeパターンとの併用でレイヤー分離を維持
- **適用条件**: 依存オブジェクトの生成に外部リソース（BrowserWindow、IPC接続等）が必要な場合
- **発見日**: 2026-02-11
- **関連タスク**: TASK-FIX-7-1-EXECUTE-SKILL-DELEGATION
- **クロスリファレンス**: [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md#setter-injection-パターンtask-fix-7-1-2026-02-11実装)

### [DI/Architecture] 二重パイプライン設計と Optional Inject graceful degradation（TASK-P0-05）

- **状況**: `RuntimeSkillCreatorFacade.execute()` で LLM が生成したスキルコンテンツをファイルシステムへ永続化する必要があるが、`SkillFileWriter` の注入が保証されない環境（テスト、軽量起動等）でも execute は成功すべき
- **アプローチ**:
  - **二重パイプライン設計**: A経路（Facade → `parseLlmResponseToContent()` → `SkillFileWriter.persist()`）を正式経路とし、B経路（`SkillCreatorOutputHandler` → `SkillRegistry`）は IPC Bridge 経由の別系統として共存させる
  - **Optional Inject**: `RuntimeSkillCreatorFacadeDeps.skillFileWriter?` で optional inject。未注入時は `console.warn` で警告し persist をスキップ（graceful degradation）
  - **エラー分離**: `persistResult`（成功時の書き込み結果）と `persistError`（persist 中の例外メッセージ）を `SkillExecuteResult` にスキル実行結果とは独立して格納。persist 失敗がスキル実行自体の成否に影響しない
  - **Step 3.5-3.6**: execute() 内で `response.success` 判定後に `parseLlmResponseToContent(sdkEvents)` でコンテンツを抽出し、`skillFileWriter.persist(planResult.skillName, content, { overwrite: true })` で永続化
- **結果**: persist 層の障害がスキル実行フローを妨げず、テスト環境でも SkillFileWriter なしで execute が正常に動作。統合テスト 44 件で A/B 両経路を検証
- **適用条件**: Facade パターンで optional な後処理（永続化・通知・監査等）を execute 後に実行するケース。依存が揃わない環境でも graceful に動作すべき場合
- **発見日**: 2026-04-05
- **関連タスク**: TASK-P0-05


### [Persist] persist復旧の3段ガード（Set/Array二方向シリアライズ）（TASK-FIX-SETTINGS-PERSIST-ITERABLE-HARDENING-001）

- **状況**: Zustand `persist` ミドルウェアで `localStorage` から復元する際、破損データ（null/undefined/number/object）により `object is not iterable` エラーが発生する。`Set` を `JSON.stringify` すると `{}` になり、復元時に `new Set(storedValue)` で空オブジェクトを展開しようとして失敗する
- **アプローチ**:
  - Step 1: `Array.isArray(value)` で配列であることを確認（null/undefined/number/object を排除）
  - Step 2: `.filter(v => typeof v === "string")` で各要素が文字列であることを検証（混在型を排除）
  - Step 3: 上記いずれかで失敗した場合、安全な既定値（空配列 `[]` / 空Set `new Set()`）にフォールバック
  - シリアライズ: `Set` → `Array.from(set)` で保存、復元時は `new Set(validatedArray)` で復元
- **結果**: 破損値（null/undefined/number/object/空オブジェクト `{}`）を全て安全にフォールバックし、Set/Array の二方向シリアライズを統一。`customStorage` アダプターで復旧ロジックを一元管理
- **適用条件**: `persist` で `Set` / `Map` / カスタム型を `JSON.stringify` する場合。特に `electron-store` や `localStorage` から復元するケース
- **発見日**: 2026-03-07
- **関連タスク**: TASK-FIX-SETTINGS-PERSIST-ITERABLE-HARDENING-001
- **関連Pitfall**: P19（型キャストによる実行時検証バイパス）、P48（non-null assertionによる安全性偽装）

### [IPC/Type] IPC層とサービス層の型変換パターン（TASK-FIX-7-1）

- **状況**: IPC層（Preload/Handler）とサービス層で異なる型定義を使用しており、型変換が必要
- **アプローチ**:
  - 問題: IPC層では`Skill`型（UI向け汎用型）、サービス層では`SkillMetadata`型（実行エンジン向け詳細型）を使用
  - 解決: IPCハンドラー内で明示的な型変換ロジックを実装し、型安全性を確保
  - 変換例: `Skill` → `SkillMetadata` への変換時、必須フィールドの存在確認とデフォルト値設定を行う
  - 型定義の配置: 共通型は`@repo/shared`に配置し、レイヤー固有の型は各層で定義
- **結果**: レイヤー間の型の責務が明確になり、型安全な通信が実現
- **適用条件**: IPC通信でRenderer/Main間でデータ構造が異なる場合、Store型とPreload型が異なる場合
- **発見日**: 2026-02-11
- **関連タスク**: TASK-FIX-7-1-EXECUTE-SKILL-DELEGATION
- **クロスリファレンス**: [interfaces-agent-sdk-executor.md](../../aiworkflow-requirements/references/interfaces-agent-sdk-executor.md)

### [Testing/DI] DIテストモック大規模修正パターン（TASK-FIX-7-1）

- **状況**: 新しい依存オブジェクトをDIで追加すると、既存の全テストファイルにモック追加が必要になる
- **アプローチ**:
  - Step 1: `grep -rn "new TargetClass\|TargetClass(" src/` で影響範囲を事前調査
  - Step 2: 各テストファイルに対象モックを定義（`mockDependency = { method: vi.fn() }`）
  - Step 3: `beforeEach`で`mockDependency.method.mockResolvedValue()`をリセット
  - Step 4: 標準モック構成をテストユーティリティとしてドキュメント化
  - 例: SkillExecutorにSkillServiceを追加した際、5つのテストファイルにmockSkillServiceを追加
- **結果**: 既存テストの網羅的な更新が完了し、モック構成が統一される
- **適用条件**: Constructorに新しい依存オブジェクトを追加する場合、Setter Injectionで新しい依存を追加する場合
- **発見日**: 2026-02-11
- **関連タスク**: TASK-FIX-7-1-EXECUTE-SKILL-DELEGATION
- **クロスリファレンス**: [06-known-pitfalls.md#P21](../../.claude/rules/06-known-pitfalls.md)

### [Phase12] 横断的問題の追加検証パターン（UT-FIX-5-3）

- **状況**: Phase 10レビューで検出した問題が、他ファイルにも同様に存在する可能性がある
- **アプローチ**:
  - Step 1: Phase 10で検出した問題パターンを正規表現で表現
  - Step 2: `grep -rn "<pattern>" <project-root>/` でプロジェクト全体を検索
  - Step 3: 同様のパターンが見つかった場合、関連タスクとして追加検出
  - Step 4: 追加検出された問題はPhase 12の未タスク検出に含める
- **結果**: 単一ファイル修正に留まらず、横断的な品質改善を実現
- **適用条件**: Phase 10で設計パターン違反を検出した場合、Phase 12の未タスク検出時
- **発見日**: 2026-02-09
- **関連タスク**: UT-FIX-5-3-PRELOAD-AGENT-ABORT
- **クロスリファレンス**: [05-task-execution.md#Task 4](../../.claude/rules/05-task-execution.md), [06-known-pitfalls.md#P24](../../.claude/rules/06-known-pitfalls.md)

### [Testing] 統合テストでの依存サービスモック漏れ防止パターン（TASK-FIX-15-1）

- **状況**: IPCハンドラーの実行パスがSkillServiceからSkillExecutorに変更され、既存の統合テストが失敗
- **アプローチ**:
  - 問題: ハンドラーが呼び出す依存サービスが変更されても、テストのモック設定が古いまま
  - 解決: 実装変更時に統合テストのモック対象も同時に更新する
  - 実装パターン: `vi.mock("../../services/skill/SkillExecutor")` で新しい依存をモック
  - 検証: モックメソッド（`mockExecuteMethod`, `mockAbortMethod`等）を事前定義し、テストで呼び出し確認
- **結果**: 実装の実行パス変更に追従し、テストが正常動作
- **適用条件**: ハンドラーやサービスの内部依存を変更する際、関連する統合テスト全てを更新
- **発見日**: 2026-02-10
- **関連タスク**: TASK-FIX-15-1-EXECUTE-HANDLER-ROUTING
- **クロスリファレンス**: [06-known-pitfalls.md#P25](../../.claude/rules/06-known-pitfalls.md)

### [IPC] 入力バリデーション統一パターン - whitespace対策（TASK-FIX-15-1）

- **状況**: ユーザー入力（prompt等）に空白のみの文字列が渡されるとサービスエラーになる
- **アプローチ**:
  - 問題: `prompt === ""` のみのチェックでは空白のみ（`"   "`）を検出できない
  - 解決: `prompt.trim() === ""` でホワイトスペースのみの入力を拒否
  - 正規化: リクエスト構築時に `prompt.trim()` で前後の空白を削除
  - エラーメッセージ: `"prompt must be a non-empty string"` で明確なバリデーションエラーを返す
- **結果**: 空白のみ入力がバリデーション段階で拒否され、サービス層に到達しない
- **適用条件**: IPCハンドラーでユーザー入力文字列を受け取る場合
- **発見日**: 2026-02-10
- **関連タスク**: TASK-FIX-15-1-EXECUTE-HANDLER-ROUTING
- **クロスリファレンス**: [06-known-pitfalls.md#P26](../../.claude/rules/06-known-pitfalls.md)

### [IPC] IPC機能開発ワークフローパターン（TASK-9B-H）

- **状況**: Electron IPC チャンネルの新規追加（サービス層のメソッドをRenderer側に公開する）
- **アプローチ**:
  1. **チャンネル定数定義**: `channels.ts` に `IPC_CHANNELS` 定数を追加し、同ファイルのホワイトリスト配列にも登録
  2. **Main側ハンドラー作成**: `validateIpcSender` でsender検証 + 引数バリデーション + サービス層呼び出し + エラーサニタイズの4段構成
  3. **Preload API作成**: `safeInvoke`/`safeOn` を使用し、チャンネル名は必ず `IPC_CHANNELS` 定数を参照。インターフェース定義を型安全に設計
  4. **preload/index.ts統合**: 4箇所を同時更新（import文、electronAPIオブジェクト、exposeInMainWorld、fallback定義）
  5. **types.ts型定義追加**: `ElectronAPI` インターフェースと `Window` グローバル宣言の両方に型を追加
  6. **ipc/index.ts登録**: `registerAllIpcHandlers` に新規ハンドラーの register/dispose を追加
- **セキュリティチェック**:
  - 全ハンドラーで `validateIpcSender` によるsender検証
  - チャンネル名のホワイトリスト管理（`channels.ts` の配列に登録されていないチャンネルは `safeInvoke` で拒否）
  - エラーサニタイズ（内部スタックトレースをRenderer側に漏洩しない）
- **テスト設計**:
  - ハンドラー登録/解除テスト（`ipcMain.handle`/`removeHandler` の呼び出し確認）
  - 正常系テスト（サービス層への引数の受け渡し、戻り値のフォーマット）
  - 異常系テスト（バリデーションエラー、サービス層エラー、sender検証失敗）
  - 統合テスト（ハンドラー登録→実行→解除の一連のフロー）
- **結果**: 6段階のチェックリストにより、IPC チャンネル追加時の漏れを防止。セキュリティ3層モデル（ホワイトリスト + sender検証 + エラーサニタイズ）を標準化
- **適用条件**: Electron IPC チャンネルの新規追加、既存サービスのRenderer公開
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-H-SKILL-CREATOR-IPC
- **クロスリファレンス**: [04-electron-security.md](../../.claude/rules/04-electron-security.md), [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)
- **関連仕様書**:
  - [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md) - IPC実装パターン（Setter Injection、型変換、テストモック等）
  - [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md) - Electron IPCセキュリティ仕様（ホワイトリスト管理、sender検証、エラーサニタイズ）
  - [api-ipc-agent.md](../../aiworkflow-requirements/references/api-ipc-agent.md) - IPC API仕様（チャンネル定義、ハンドラー登録、Preload Bridge設計）

### [IPC] IPCハンドラライフサイクル管理パターン（UT-FIX-IPC-HANDLER-DOUBLE-REG-001）

- **状況**: macOS の `activate` イベントでウィンドウ再生成時に `registerAllIpcHandlers()` が再実行され、`ipcMain.handle()` の二重登録例外が発生
- **アプローチ**:
  1. `unregisterAllIpcHandlers()` を追加し、`Object.values(IPC_CHANNELS)` で全チャンネルの `removeHandler` と `removeAllListeners` を実行
  2. `setupThemeWatcher()` のような IPC 外リスナーは `unsubscribe` をモジュールスコープで保持して同時解除
  3. `activate` では `unregister -> createWindow -> register` の順序を固定
  4. `ipcMain.handle()` と `ipcMain.on()` の二重登録時挙動差（例外送出 vs 累積登録）を設計レビューで明示
- **結果**: 7テストで再現シナリオをカバーし、`Attempted to register a second handler` を解消
- **適用条件**: Electron Main Process でウィンドウ再生成時に IPC ハンドラ再登録を伴う実装
- **発見日**: 2026-02-14
- **関連タスク**: UT-FIX-IPC-HANDLER-DOUBLE-REG-001
- **クロスリファレンス**:
  - [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md#ipc-ハンドラライフサイクル管理)
  - [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md#ipc-ハンドラ二重登録防止パターンut-fix-ipc-handler-double-reg-001-2026-02-14実装)
  - [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md#ut-fix-ipc-handler-double-reg-001-ipc-ハンドラ二重登録防止)

### [IPC] Main Process ライフサイクル修正ワークフロー

- **状況**: macOS の `activate` イベントで IPC ハンドラが二重登録され、`ipcMain.handle()` が例外を送出するバグ
- **アプローチ**:
  - `Object.values(IPC_CHANNELS)` で全チャンネルを動的列挙し、追加漏れを防止
  - `removeHandler()` + `removeAllListeners()` の両方を呼び出し（handle/on 両対応）
  - `themeWatcherUnsubscribe` 等の IPC 外リスナーも同時管理（モジュールスコープ変数）
  - TDD Red-Green パターンで7テスト先行作成 → 実装 → 全 GREEN
- **結果**: 2ファイル修正 + 7テスト追加のみで完了。4層セキュリティ防御は影響なし
- **教訓**:
  - `ipcMain.handle()` と `ipcMain.on()` は二重登録時の動作が根本的に異なる（例外 vs 累積）
  - IPC_CHANNELS 定数の構造（フラット or ネスト）を事前確認してから全走査ロジックを設計する
  - IPC ハンドラ以外のプロセスレベルリスナー（nativeTheme 等）も同時に管理する必要がある
  - macOS 固有のライフサイクル（activate）は Windows/Linux に影響しないことを互換性テストで確認
- **適用条件**: Electron アプリで macOS ドックアイコンクリック時のウィンドウ再生成がある場合
- **関連タスク**: UT-FIX-IPC-HANDLER-DOUBLE-REG-001
- **発見日**: 2026-02-14

### [Security] TDDセキュリティテスト分類体系（UT-9B-H-003）

- **状況**: IPCハンドラーのセキュリティ強化でテストを先行設計する必要がある
- **アプローチ**:
  - 攻撃カテゴリ別にテストIDを割り当て（SEC-01〜SEC-07g）
  - 受入基準（AC-01〜AC-10）にテストIDをマッピング
  - カテゴリ: パストラバーサル(SEC-01〜03)、ホワイトリスト(SEC-04〜05)、回帰(SEC-06)、境界値(SEC-07)
  - `it.each` で攻撃パターンを網羅（`../`, `..\`, `\x00`, `\\\\`）
  - テスト間独立性: `beforeEach` で `handlerMap.clear()` + `vi.clearAllMocks()`
- **結果**: 45セキュリティテスト + 71統合テスト = 116テスト全PASS。ブランチカバレッジ100%
- **適用条件**: セキュリティ関連のTDD実装時。特にIPC L3検証の追加時
- **発見日**: 2026-02-12
- **関連タスク**: UT-9B-H-003
- **クロスリファレンス**: [lessons-learned.md#UT-9B-H-003](../../aiworkflow-requirements/references/lessons-learned.md), [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md)

### [Security] YAGNI原則に基づく共通化判断の記録パターン（UT-9B-H-003）

- **状況**: Phase 8リファクタリングで、セキュリティ関数（validatePath, sanitizeErrorMessage）を共通パッケージに移動すべきか判断が必要
- **アプローチ**:
  - 3つの評価軸で判断: (1) 現在の使用箇所数、(2) 変更頻度の予測、(3) ドメインの独立性
  - 共通化しない判断も**未タスク候補として明示的に記録**（unassigned-task-report.md）
  - 既存の未タスク（UT-9B-H-001, UT-9B-H-002）との重複チェックを実施
  - 重複と判定された候補は新規作成せず、既存タスクのスコープ内で対応と記録
- **結果**: 3件の共通化候補を検討し、全て「現状維持」と判断。将来の判断材料として未タスクレポートに記録
- **適用条件**: Phase 8リファクタリングで共通化を検討する場合。特にセキュリティ関数のように複数のIPC Handlerで使用される可能性がある場合
- **発見日**: 2026-02-12
- **関連タスク**: UT-9B-H-003
- **クロスリファレンス**: [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)

- **Phase 12での苦戦箇所と解決策**:

| 苦戦箇所                                 | 原因                                                                 | 解決策                                                                                                                                |
| ---------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| CLI環境でのPhase 11手動テスト不可        | Claude Code環境ではElectronアプリ起動・DevTools操作ができない        | 自動テスト（116テスト）で代替検証を実施。DevToolsコマンドをドキュメントに記載し、開発者向けリファレンスとして提供                     |
| コンテキスト分割によるPhase 12整合性管理 | コンテキスト制限でセッション分割。前セッションの成果物状態追跡が困難 | セッション開始時に `Glob` でoutputs/配下の成果物一覧を確認。`TaskOutput` でバックグラウンドエージェント完了を待ってから整合性チェック |
| Markdownコードブロック内のPrettier干渉   | PostToolUseフックのPrettierがMarkdown内のTypeScript型表記を自動変形  | バックグラウンドエージェント内で修正ステップを追加。ドキュメント作成時はPrettier影響の検証を後処理に組み込む                          |

### [Testing] Store Hook テスト実装パターン（renderHook方式）（UT-STORE-HOOKS-TEST-REFACTOR-001）

- **状況**: Zustand個別セレクタHookのテストで `getState()` 直接呼び出しを使用しており、Reactサブスクリプション経由の動作検証ができていない
- **アプローチ**:
  - 旧パターンの問題: `store.getState().field` はReactの再レンダリングサイクルを経由しないため、コンポーネントでの実際の使用経路と異なる
  - 新パターン: `renderHook(() => useField())` でReactサブスクリプション経由のテストを実現
  - 状態変更: `act(() => useAppStore.setState({...}))` でReactの状態更新サイクルを正しく経由
  - 非同期アクション: `await act(async () => { ... })` でPromise解決を待機
  - テスト間リセット: `resetStore()` → `cleanup()` → `vi.restoreAllMocks()` の3段階で完全リセット

- **パターン対応表**:

| 対象             | 旧パターン（非推奨）        | 新パターン（推奨）                       |
| ---------------- | --------------------------- | ---------------------------------------- |
| 状態取得         | `store.getState().field`    | `renderHook(() => useField())`           |
| 状態変更         | `store.setState({...})`     | `act(() => useAppStore.setState({...}))` |
| アクション実行   | `store.getState().action()` | `renderHook` + `act()`                   |
| 非同期アクション | `await action()`            | `await act(async () => { ... })`         |

- **テストカテゴリ分類**（代表的な5カテゴリ）:

| カテゴリ         | 検証内容                                                  | 対応するCAT            |
| ---------------- | --------------------------------------------------------- | ---------------------- |
| 初期値検証       | セレクタが正しいデフォルト値を返すか                      | CAT-01                 |
| 状態変更検証     | act() + setState 後にセレクタが正しく更新されるか         | CAT-02, CAT-04, CAT-08 |
| 参照安定性       | rerender() 後もアクション関数の参照が === で同一か        | CAT-05, CAT-10         |
| 無限ループ防止   | useEffect依存配列にアクションを含めてもrenderCount < 10か | CAT-07, CAT-16         |
| 再レンダー最適化 | 無関係なフィールド変更でセレクタが再レンダーされないか    | CAT-06, CAT-11         |

- **結果**: getState()パターン48件 → renderHookパターン114件（+export検証23件）に移行。Reactサブスクリプション経路の検証、参照安定性テスト、無限ループ検出が可能に
- **適用条件**: Zustand Store で個別セレクタHookを使用し、React コンポーネントから利用するテストを書く場合。特に useEffect 依存配列にアクション関数を含める場合は無限ループ防止テスト（CAT-07/16）が必須。
- **発見日**: 2026-02-12
- **関連タスク**: UT-STORE-HOOKS-TEST-REFACTOR-001
- **クロスリファレンス**: [development-guidelines.md#Zustand Hook テスト戦略](../../aiworkflow-requirements/references/development-guidelines.md), [lessons-learned.md#UT-STORE-HOOKS-TEST-REFACTOR-001](../../aiworkflow-requirements/references/lessons-learned.md)
  - [arch-state-management.md#Store Hooks テスト実装ガイド](../../aiworkflow-requirements/references/arch-state-management.md) - テストパターン6種の一覧表
  - [testing-component-patterns.md#9. Zustand Store Hooks テストパターン](../../aiworkflow-requirements/references/testing-component-patterns.md) - コピペ可能な実装コード例

- **Phase 12での苦戦箇所と解決策**:

| 苦戦箇所                                 | 原因                                                                                                            | 解決策                                                                                                                                                        |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Step 2を「該当なし」と誤判定             | テストリファクタリングはインターフェース変更を伴わないため、Step 2不要と判断しがち                              | テストのみの変更でも、テスト戦略やテストパターンの変更は仕様書（development-guidelines.md等）に記録すべき。Step 2の判断基準に「テスト戦略変更」を含める       |
| 実装ガイドのテストカテゴリテーブル不整合 | Phase 4でテストカテゴリ（CAT-01〜CAT-05）を定義し、Phase 6で拡充したが、実装ガイドのテーブルがPhase 4時点のまま | Phase 6（テスト拡充）完了後に、implementation-guide.md Part 2のテストカテゴリテーブルを必ず再確認・更新する。テスト数やカテゴリ構成が変わった場合は即座に反映 |

### [Test] SDKテスト有効化モック2段階リセット

- **状況**: SDK統合テスト17箇所のTODOコメントを有効化する際、テスト間でモック状態が漏洩してテスト実行順序依存が発生
- **アプローチ**: `beforeEach` で (1) `vi.clearAllMocks()` + (2) `mockResolvedValue()` による2段階リセットを実施。エラーテストでは `mockRejectedValueOnce` のみ使用
- **結果**: 134テスト全PASS、テスト実行順序に非依存
- **適用条件**: `vi.mock()` でモジュール全体をモック化し、正常系・異常系テストが混在する場合
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [SDK] TypeScript モジュール解決による型安全統合（TASK-9B-I）

- **状況**: 外部 SDK (`@anthropic-ai/claude-agent-sdk@0.2.30`) の `as any` を除去し型安全な統合を実現
- **アプローチ**:
  - SDK の型定義ファイル (`dist/index.d.ts`) を直接参照して正確なパラメータ構造を把握
  - `SDKQueryOptions` 内部型を定義し、SDK `Options` 型への変換を型安全に実装
  - `@ts-expect-error` を使った compile-time テストで不正な型の検証
- **結果**: `as any` 完全除去、13テスト追加、278既存テスト全PASS
- **適用条件**: 外部 SDK の型安全な統合、`as any` 除去タスク
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-I-SDK-FORMAL-INTEGRATION
- **クロスリファレンス**: [02-code-quality.md#TypeScript型安全](../../.claude/rules/02-code-quality.md)

### [Testing] テスト環境別イベント発火パターン選択（UT-FIX-AGENTVIEW-INFINITE-LOOP-001）

- **状況**: Vitest + happy-dom環境でユーザーインタラクションテストを作成する際、`@testing-library/user-event`のSymbol操作がhappy-domで非互換
- **アプローチ**:
  - 問題発見: 53テスト中49テストがSymbolエラーで一斉失敗。`userEvent.setup()`がhappy-dom未サポートのDOM操作を実行
  - 試行1: `// @vitest-environment jsdom` ディレクティブ追加 → `toBeInTheDocument`動作不良、DOM要素重複で断念
  - 試行2: `userEvent`を`fireEvent`に全面置換 → 53テスト全PASS
  - 非同期対応: `await act(async () => { fireEvent.click(el) })`でPromise microtask flushを保証
- **パターン選択基準**:

| テスト環境                  | イベントAPI | 理由                                    |
| --------------------------- | ----------- | --------------------------------------- |
| happy-dom（デフォルト）     | `fireEvent` | Symbol操作不要、軽量・高速              |
| jsdom（ディレクティブ指定） | `userEvent` | 完全なDOM API、アクセシビリティ検証向き |

- **結果**: 環境固有の制約を理解し、適切なAPIを選択することでテスト安定性を確保
- **適用条件**: Vitest + happy-dom環境でのコンポーネントテスト。特にクリック/入力等のユーザーインタラクションテスト
- **発見日**: 2026-02-12
- **関連タスク**: UT-FIX-AGENTVIEW-INFINITE-LOOP-001
- **クロスリファレンス**: [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md#fireevent-vs-userevent-使い分けパターン), [06-known-pitfalls.md#P39](../../.claude/rules/06-known-pitfalls.md)

### [Testing] モノレポ テスト実行ディレクトリ依存パターン（UT-FIX-AGENTVIEW-INFINITE-LOOP-001）

- **状況**: モノレポ環境でプロジェクトルートからVitest実行すると、サブパッケージの`vitest.config.ts`が読み込まれない
- **アプローチ**:
  - 問題: `pnpm vitest run apps/desktop/src/...`（ルートから実行）→ `document is not defined`エラー
  - 原因: Vitestはカレントディレクトリの設定ファイルを優先。ルートの設定にはhappy-dom/setupFilesが未定義
  - 解決: `cd apps/desktop && pnpm vitest run src/...` または `pnpm --filter @repo/desktop exec vitest run src/...`
- **結果**: テスト実行を対象パッケージディレクトリから行うルールを確立
- **適用条件**: pnpm monorepo + Vitest環境で、パッケージ固有のテスト環境設定がある場合
- **発見日**: 2026-02-12
- **関連タスク**: UT-FIX-AGENTVIEW-INFINITE-LOOP-001
- **クロスリファレンス**: [06-known-pitfalls.md#P40](../../.claude/rules/06-known-pitfalls.md)

### [SDK] SDKテストTODO一括有効化ワークフロー

- **状況**: agent-client.test.ts / skill-executor.test.ts / sdk-integration.test.ts の3ファイルに TODO コメントで無効化された17箇所のテストが存在
- **アプローチ**: Phase 2設計で17箇所のモック戦略を事前にマッピング → Phase 5でファイルごとに有効化（既存モックパターン `vi.mock`/`vi.hoisted` を活用、NFR-007準拠）→ Phase 9で全134テスト一括検証
- **結果**: 新規モック戦略導入なしで17箇所全て有効化。既存テスト117件の挙動に影響なし
- **適用条件**: 段階的にテストを有効化し、回帰テストの安全性を保つ必要がある場合
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [Testing] Vitest未処理Promise拒否の可視化運用（TASK-FIX-10-1）

- **状況**: `dangerouslyIgnoreUnhandledErrors: true` が残っていると、未処理Promise拒否がテスト失敗として観測されず品質低下を招く
- **アプローチ**:
  - `vitest.config.ts` から `dangerouslyIgnoreUnhandledErrors` を削除し、デフォルト挙動（未処理拒否を失敗扱い）を維持
  - 設定退行を防ぐため、設定検証テストを追加して「危険設定を再導入していないこと」を機械検証
  - モノレポ解決エラーの混入を避けるため、`@repo/shared` サブパスaliasを具体パス優先で定義
- **結果**: 未処理Promise拒否の隠蔽を防止し、テスト失敗の原因を早期に可視化
- **適用条件**: Vitest設定に `dangerously*` 系の緩和設定を検討する場合、またはモノレポでalias整合が必要な場合
- **発見日**: 2026-02-19
- **関連タスク**: TASK-FIX-10-1-VITEST-ERROR-HANDLING
- **クロスリファレンス**: [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md#未処理promise拒否検知ルールtask-fix-10-1-2026-02-19実装)

### [IPC] IPC契約ドリフト防止パターン（3箇所同時更新）（UT-FIX-SKILL-REMOVE-INTERFACE-001）

- **状況**: Main Process の IPC ハンドラと Preload API の引数インターフェースが乖離し、ランタイムでバリデーションエラーが発生（P44パターン）
- **アプローチ**:
  1. **契約の正本を特定**: Preload側（`skill-api.ts`）の呼び出しシグネチャを「正」と定義し、ハンドラ側を合わせる
  2. **3箇所同時更新**: ハンドラ（`skillHandlers.ts`）・Preload API（`skill-api.ts`）・テスト（`*.test.ts`）を1コミットで更新
  3. **引数命名統一**: `skillId` / `skillIds` / `skillName` の混在を排除し、全レイヤーで `skillName: string` に統一
  4. **P42準拠バリデーション**: 3段バリデーション（`typeof === "string"` → `=== ""` → `.trim() === ""`）を全ハンドラに適用
  5. **横断検証**: `grep -rn "skillId\b" apps/desktop/src/main/` で同一パターンの残存を検出
- **結果**: skill:import と skill:remove の両チャンネルでインターフェース不整合を解消。同一パターンの横断的修正を実現
- **適用条件**: IPC ハンドラの引数変更、新規 IPC チャンネル追加、既存ハンドラのバリデーション修正
- **発見日**: 2026-02-20
- **関連タスク**: UT-FIX-SKILL-REMOVE-INTERFACE-001, UT-FIX-SKILL-IMPORT-INTERFACE-001
- **クロスリファレンス**:
  - [06-known-pitfalls.md#P44](../../.claude/rules/06-known-pitfalls.md) - インターフェース不整合の教訓
  - [ipc-contract-checklist.md](../../aiworkflow-requirements/references/ipc-contract-checklist.md) - IPC修正時チェックリスト
  - [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md) - IPCセキュリティ仕様

### [IPC/Renderer] Renderer層 id→name 契約変換パターン（UT-FIX-SKILL-IMPORT-ID-MISMATCH-001）

- **状況**: SkillImportDialog が `skill.id`（SHA-256ハッシュ）を `onImport` に渡しており、IPCハンドラ側は `skill.name`（人間可読名）を期待していた。同じ `string` 型のため、コンパイル時に不整合が検出されない
- **アプローチ**:
  1. **利用箇所からの逆引き**: `AgentView` の import 文から修正対象を `organisms/SkillImportDialog/index.tsx` に特定
  2. **境界での明示変換**: `selectedIds`（Set<string>）を `availableSkills.filter(s => selectedIds.has(s.id)).map(s => s.name)` で名前配列に変換
  3. **命名の契約準拠**: callback の引数名を `skillNames` に統一し、Props 型も `onImport: (skillNames: string[]) => void` に更新
  4. **否定条件テスト**: 「id が渡されないこと」を `expect(onImport).not.toHaveBeenCalledWith(expect.arrayContaining([skill.id]))` で検証
- **結果**: Renderer → IPC → Service の全レイヤーで `skill.name` 契約が統一。テスト 88 件全 PASS
- **適用条件**: 内部識別子（ハッシュ、UUID）と外部識別子（名前、スラッグ）が同じ `string` 型で混在するコンポーネント
- **発見日**: 2026-02-22
- **関連タスク**: UT-FIX-SKILL-IMPORT-ID-MISMATCH-001
- **クロスリファレンス**:
  - [06-known-pitfalls.md#P44](../../.claude/rules/06-known-pitfalls.md) - IPC インターフェース不整合の教訓
  - [lessons-learned.md#UT-FIX-SKILL-IMPORT-ID-MISMATCH-001](../../aiworkflow-requirements/references/lessons-learned.md) - 苦戦箇所詳細
  - [architecture-implementation-patterns.md#S13](../../aiworkflow-requirements/references/architecture-implementation-patterns.md) - IPC 戻り値型変換パターン

### [IPC] IPC契約ブリッジ（正式契約 + 後方互換）（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: shared/preload は `skillName` 契約へ移行済みだが、Main/Service は `skillId` 前提で稼働しており、一括置換すると既存呼び出しを壊す
- **アプローチ**:
  1. Mainハンドラで union 受理（正式: `SkillExecutionRequest`、互換: `{ skillId, params }`）
  2. `skillName` 経路は境界で `name -> id` を解決し、Service APIは据え置き
  3. 新旧契約を同一テスト群で回帰確認（正常系/異常系）
  4. interfaces/security/task-workflow を同一ターンで同期更新
- **結果**: 契約移行中のダウンタイムなしで `skill:execute` を整合化し、後方互換を維持
- **適用条件**: IPC契約の正式化が先行し、内部APIの移行が段階的になるケース
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] 未タスク検出の2段階判定（raw→実タスク候補）

- **状況**: `detect-unassigned-tasks.js` が仕様書本文の説明用 TODO まで大量検出し、未タスク件数を過大評価しやすい
- **アプローチ**:
  - 1段階目: 実装ディレクトリ（例: `apps/.../__tests__`）を優先スキャン
  - 2段階目: ドキュメント全体の raw 検出結果を手動精査し、説明文TODOと実装漏れを分離
  - 出力は「raw検出件数」と「確定未タスク件数」を別々に記録
- **結果**: 誤検知由来の不要な未タスク作成を防止し、`docs/30-workflows/unassigned-task/` への配置要否を正確化
- **適用条件**: Phase 12 Task 4（未タスク検出）実行時
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT
- **クロスリファレンス**: [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md)

---

### [Phase 12] 実行仕様書ステータス同期（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: Phase 12 の成果物は生成済みだが、`phase-12-documentation.md` 本文が「未実施」のまま残る
- **解決策**: 成果物監査と同時に、仕様書本体の `ステータス` / 事前チェック / 完了条件チェックボックスを実態に同期する
- **効果**: 実行記録と仕様書の齟齬を防ぎ、後続フェーズ判定を明確化できる
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001

### [Phase 12] 成果物ログとStep判定の同期（UT-FIX-SKILL-IMPORT-INTERFACE-001）

- **状況**: `outputs/phase-12` には成果物がある一方、`system-docs-update-log.md` が「Step 2該当なし」「Phase 13で実施予定」の古い判定を保持していた
- **解決策**:
  1. 仕様更新実績（更新した仕様書）を先に確定し、Step判定を再計算する
  2. `system-docs-update-log.md` / `documentation-changelog.md` / `phase-12-documentation.md` の3ファイルを同時更新する
  3. 「後続Phaseで対応予定」の記述を禁止し、Phase 12必須項目は同一ターンで完了記録する
  4. 更新不要判定は「理由 + 正本ファイル」を明記する
- **効果**: Phase 12の完了証跡と実装実態が一致し、再監査時の差し戻しを削減できる
- **適用条件**: 仕様更新対象が複数ファイルに跨るタスク、またはPhase 12の再監査を行うタスク
- **発見日**: 2026-02-21
- **関連タスク**: UT-FIX-SKILL-IMPORT-INTERFACE-001

### [Phase 12] 全体監査と対象差分の分離報告（TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001）

- **状況**: `audit-unassigned-tasks.js` はリポジトリ全体を監査するため、既存違反件数が多い場合に「今回作業で壊した」と誤読しやすい
- **解決策**:
  1. 監査結果を「全体ベースライン（既存）」と「今回対象ファイル」の2レイヤーで分離する
  2. 今回対象ファイルは `sed`/`rg` で9見出しテンプレート準拠を個別検証する
  3. 報告時に「全体違反件数」「今回対象の準拠可否」を同一表で併記し、責務境界を明確化する
- **効果**: 既存負債と今回差分の切り分けが可能になり、誤った差し戻しや過剰修正を防止できる
- **適用条件**: 未タスク監査を既存資産が多いリポジトリで実行するPhase 12 Task 4
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001
- **クロスリファレンス**: [task-specification-creator/scripts/audit-unassigned-tasks.js](../../task-specification-creator/scripts/audit-unassigned-tasks.js), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] scoped監査の `current` 判定固定（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: `--target-file` を使っても baseline が出力されるため、対象ファイルも違反と誤読しやすい
- **解決策**:
  1. `audit-unassigned-tasks --json --diff-from HEAD --target-file <path>` の `scope.currentFiles` を確認する
  2. 合否は `currentViolations.total` を正本にし、`baselineViolations.total` は別枠で記録する
  3. 報告テンプレートに `current / baseline` を分離して記載する
- **効果**: 既存負債に引きずられず、今回差分のフォーマット準拠可否を即判定できる
- **適用条件**: unassigned-task 監査を既存違反が多いリポジトリで実行する場合
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase 12] target監査 + 10見出し同時検証（TASK-9I再確認）

- **状況**: 未タスク指示書を新規作成した後、配置確認は通るがフォーマット崩れが混入しやすい
- **解決策**:
  1. `audit-unassigned-tasks --json --diff-from HEAD --target-file <path>` を対象ファイルごとに実行し、`currentViolations.total` を判定軸に固定する
  2. 必須10見出し（`## メタ情報` + `## 1..9`）と `## メタ情報` 件数（1件）を同一ターンで検証する
  3. `verify-unassigned-links` で実体パス整合を確認し、`missing=0` を完了条件に含める
  4. `task-workflow.md` の再確認テーブルへ `current/baseline` を分離して記録する
- **効果**: 「存在は正しいが形式が壊れている」状態を防止し、Phase 12再確認の判定を再現可能にする
- **適用条件**: unassigned-task を新規登録した Phase 12 Task 4 と再監査
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9I, UT-9I-001, UT-9I-002
- **クロスリファレンス**: [audit-unassigned-tasks.js](../../task-specification-creator/scripts/audit-unassigned-tasks.js), [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md), [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md)

### [Phase 12] 2workflow同時監査 + Task 1/3/4/5実体突合（TASK-UI-05A / TASK-UI-05）

- **状況**: `spec_created` workflow と完了workflowを同時に再監査する際、検証結果や証跡が分散し、完了判定が曖昧になりやすい
- **解決策**:
  1. 対象workflowを先に固定し、`verify-all-specs --workflow <dir>` を全対象へ実行する
  2. 続けて `validate-phase-output <dir>` を同対象へ実行し、構造準拠を確定する
  3. Phase 12 Task 1/3/4/5 の必須成果物実体（`implementation-guide`/`documentation-changelog`/`unassigned-task-detection`/`skill-feedback-report`）をworkflowごとに突合する
  4. 未タスク監査は `verify-unassigned-links` + `audit --diff-from HEAD` を連続実行し、合否を `currentViolations=0` で固定する
- **効果**: 複数workflow再監査の証跡が一本化され、baseline誤読や完了判定のブレを抑止できる
- **適用条件**: Phase 12で spec_created系と完了系workflowを同一ターンで確認する場合
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05A-SKILL-EDITOR-VIEW, TASK-UI-05-SKILL-CENTER-VIEW
- **クロスリファレンス**: [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [phase-12-documentation.md](../../../../docs/30-workflows/skill-editor-view/phase-12-documentation.md), [phase-12-documentation.md](../../../../docs/30-workflows/completed-tasks/TASK-UI-05-SKILL-CENTER-VIEW/phase-12-documentation.md)

### [Phase 12] 2workflow証跡バンドル完了同期（UT-IMP-PHASE12-TWO-WORKFLOW-EVIDENCE-BUNDLE-001）

- **状況**: 2workflow同時監査タスクを完了移管した後、`task-workflow.md` と関連仕様書の未タスク参照が旧パスのまま残り、`verify-unassigned-links` が fail しやすい
- **解決策**:
  1. 完了移管を伴う未タスクIDを先に列挙し、`task-workflow.md` と関連仕様書（例: `ui-ux-feature-components.md`）の参照先を同一ターンで実体パスへ更新する
  2. `verify-unassigned-links` を再実行し、`missing=0` を確認してから完了記録を更新する
  3. `audit --target-file` / `audit --diff-from HEAD` の合否は `currentViolations=0` に固定し、baselineは監視値として分離記録する
  4. 実装内容・苦戦箇所・再利用手順を `task-workflow` / `architecture-implementation-patterns` / `lessons-learned` の3仕様へ同期する
- **効果**: 完了移管後のリンクドリフトを防ぎ、2workflow同時監査タスクの完了判定を再現可能にできる
- **適用条件**: Phase 12の再監査タスクで「未タスク登録→実装完了→completed-tasks移管」を跨ぐ場合
- **発見日**: 2026-03-03
- **関連タスク**: UT-IMP-PHASE12-TWO-WORKFLOW-EVIDENCE-BUNDLE-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)

### [Phase 12] `validate-phase-output` 位置引数固定

- **状況**: `verify-all-specs` と同じオプション形式を想定し、`validate-phase-output` の実行が失敗しやすい
- **解決策**:
  1. `node .../validate-phase-output.js <workflow-dir>` の位置引数形式をテンプレート化する
  2. `verify-all-specs --workflow <workflow-dir>` とセットで実行して証跡を残す
  3. documentation-changelog に両コマンド結果を併記する
- **効果**: Phase検証のコマンド誤用を抑止し、再確認時のやり直しを削減できる
- **適用条件**: Phase 12 再監査または仕様整合の再検証を行う場合
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase 12] 監査結果→次アクションブリッジ（TASK-013再監査）

- **状況**: 監査レポートは作成済みだが、次にどの未タスクから着手するかが曖昧で、実行順序が固まらない
- **解決策**:
  1. `task-00` 配下に「監査結果→次実行」の専用導線（action-bridge）を追加する
  2. 優先度（P1-P4）と Wave（並列/直列）を明記し、SubAgent担当を固定する
  3. `outputs/phase-12/` の必須5成果物を証跡として同時に紐づける
  4. baseline/current 監査結果を併記し、「今回差分で何が必要か」を分離する
  5. `assets/phase12-action-bridge-template.md` を起点に記述し、タスク間の形式ブレを抑制する
- **効果**: 「監査したが次の手が見えない」状態を解消し、再監査後の実装着手までの待ち時間を削減できる
- **適用条件**: 再監査で検出項目が複数あり、実行順序・責務分担の明文化が必要な Phase 12
- **発見日**: 2026-02-25
- **関連タスク**: TASK-013E-PHASE12-ACTION-BRIDGE-001
- **クロスリファレンス**: [task-013e-phase12-action-bridge.md](../../../docs/30-workflows/skill-import-agent-system/tasks/task-00-unified-implementation-sequence/task-013e-phase12-action-bridge.md), [phase12-action-bridge-template.md](../assets/phase12-action-bridge-template.md)

### [Phase 12] Task 1〜5証跡突合レポート固定化（UT-UI-THEME-DYNAMIC-SWITCH-001）

- **状況**: `outputs/phase-12` は揃っているが、`phase-12-documentation.md` のチェック欄と実行記録がテンプレート状態のまま残りやすい
- **解決策**:
  1. Task 1〜5 の証跡を1ファイル（`phase12-task-spec-compliance-check.md`）に集約する
  2. 成果物実体と `phase-12-documentation.md` のチェック欄を同一ターンで更新する
  3. `verify-all-specs --workflow --strict` と `verify-unassigned-links.js` の結果を同レポートに固定する
  4. SubAgent分担（A:成果物/B:仕様/C:未タスク/D:検証）を明示し、並列確認結果を残す
- **効果**: Phase 12完了判定の根拠が一本化され、再監査時の差し戻しを減らせる
- **適用条件**: Phase 12 の再確認や、成果物数が5件以上あるタスク
- **発見日**: 2026-02-25
- **関連タスク**: UT-UI-THEME-DYNAMIC-SWITCH-001

### [Phase 12] 実装内容+苦戦箇所テンプレート適用（UT-UI-THEME-DYNAMIC-SWITCH-001）

- **状況**: 実装内容は記録されているが、苦戦箇所が「症状」だけで終わると同種課題で再利用しにくい
- **解決策**:
  1. `assets/phase12-system-spec-retrospective-template.md` を起点に、タスクID・反映先3点セット・検証コマンドを固定化する
  2. 苦戦箇所は「課題/原因/対処」に加えて「再発条件」を必須項目として記録する
  3. `task-workflow.md` / `ui-ux-design-system.md` / `lessons-learned.md` へ同一ターンで同期する
  4. SubAgent分担（A:台帳/B:UI仕様/C:教訓/D:検証）を記録し、並列処理時の責務漏れを防ぐ
- **効果**: 仕様更新の形式が統一され、同種課題に対して短時間で再利用できる
- **適用条件**: Phase 12 Step 2 で実装内容と苦戦箇所を同時反映するタスク
- **発見日**: 2026-02-25
- **関連タスク**: UT-UI-THEME-DYNAMIC-SWITCH-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [ui-ux-design-system.md](../../aiworkflow-requirements/references/ui-ux-design-system.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] 仕様書別SubAgent同期テンプレート（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: IPC契約修正時に `interfaces` / `security` / `task-workflow` / `lessons` が別ターン更新となり、同期漏れが再発しやすい
- **解決策**:
  1. 仕様書ごとに SubAgent を固定し、担当と完了条件を先に表で定義する
  2. 各 SubAgent は「実装内容 + 苦戦箇所 + 再利用手順」を同時記述する
  3. 統括担当が4仕様書の差分を集約し、同一ターンで変更履歴を更新する
  4. `verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` を実行して証跡化する
  5. `assets/phase12-spec-sync-subagent-template.md` を起点に形式を統一する
- **効果**: 仕様書間の責務境界が明確化され、Phase 12 の同期漏れと再監査コストを削減できる
- **適用条件**: 1つの実装変更を複数仕様書へ横断反映する Phase 12
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001
- **クロスリファレンス**: [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase12] 5仕様書同期 + IPC三点突合テンプレート（TASK-9J）

- **状況**: `interfaces/security/task-workflow/lessons` は同期しても、`api-ipc` が漏れると IPC 契約の正本が分断される
- **解決策**:
  1. SubAgent を `A:interfaces / B:api-ipc / C:security / D:task-workflow / E:lessons` の5責務に固定する
  2. IPC追加時は `handler/register/preload` の3点を `rg` で同時突合し、1つでも欠けたら未完了と判定する
  3. `task-workflow` へ検証証跡（`verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` / `audit --diff-from HEAD`）を固定記録する
  4. `lessons` には再発条件付きで苦戦箇所を記録し、次回タスクで流用できる形に整える
  5. `assets/phase12-spec-sync-subagent-template.md` を唯一の入力テンプレートとして運用する
- **効果**: 仕様ドリフト（API名・チャネル・検証要件）の再発を抑止し、Phase 12 再監査の手戻りを削減
- **適用条件**: IPC追加を含む機能で、5仕様書以上の横断同期が必要な Phase 12
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J
- **クロスリファレンス**: [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] 完了タスク記録の二重同期（UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001）

- **状況**: `outputs/phase-12` と `artifacts.json` は更新済みでも、手順書側（`spec-update-workflow.md` / `phase-11-12-guide.md`）に完了タスク実記録が残らないことがある
- **解決策**:
  1. Step 1-A で更新した仕様書に `## 完了タスク` と `## 関連ドキュメント` を同時追記する
  2. 実装ガイド・更新履歴・未タスク検出レポートへのリンクを同一ターンで同期する
  3. `LOGS.md` / `SKILL.md` の更新履歴と併せて `quick_validate.js` を3スキルで再実行する
  4. `verify-unassigned-links.js` と `audit-unassigned-tasks.js --diff-from HEAD` で未タスク整合を最終確認する
- **効果**: Phase 12 の「成果物実体」と「手順書完了記録」の二重台帳が揃い、再監査時の差し戻しを削減できる
- **適用条件**: Phase 12 Task 2 で複数スキル（aiworkflow/task-spec/skill-creator）を同時更新するタスク
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001
- **クロスリファレンス**: [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md), [phase-11-12-guide.md](../../task-specification-creator/references/phase-11-12-guide.md)

### [Phase 12] 完了移管後の親タスク証跡参照同期（UT-IMP-QUICK-VALIDATE-EMPTY-FIELD-GUARD-001）

- **状況**: 未タスク指示書を `completed-tasks/` へ移管した後、親タスク成果物（`artifacts.json` / `minor-issues.md` / `unassigned-task-detection.md`）に旧 `unassigned-task` 参照が残る
- **解決策**:
  1. 完了移管したタスクIDで `rg -n "task-imp-<task-id>\\.md"` を `docs/30-workflows/completed-tasks/` 配下へ実行し、親タスク証跡の残存参照を検出する
  2. 更新対象を「当時の監査生ログ（JSON）」と「運用ドキュメント（md/json台帳）」に分離し、生ログは改変せず運用ドキュメントのみ更新する
  3. 修正後に `verify-unassigned-links.js` と `audit-unassigned-tasks.js --json --diff-from HEAD` を再実行し、リンク整合と current=0 を確認する
- **効果**: 完了移管後の親子タスク参照が一貫し、Phase 12 再監査での「旧参照残存」による差し戻しを防止できる
- **適用条件**: 子タスクの未タスク指示書を完了移管したタスク、または親タスク成果物を再利用する再監査タスク
- **発見日**: 2026-02-27
- **関連タスク**: UT-IMP-QUICK-VALIDATE-EMPTY-FIELD-GUARD-001
- **クロスリファレンス**: [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md)

### [Phase 12] 依存成果物参照補完 + 画面再撮影固定（TASK-UI-05B 再確認）

- **状況**: `verify-all-specs` は PASS だが warning が残り、Phase 12 文書更新の完了判定が揺れる。UI証跡も既存画像の存在確認だけで止まりやすい
- **解決策**:
  1. `phase-12-documentation.md` の参照資料に依存Phase成果物（2/5/6/7/8/9/10）を明示する
  2. `verify-all-specs` / `validate-phase-output` を再実行し、warning/error の根拠を固定する
  3. UI再確認時はスクリーンショットを再取得し、更新時刻で当日証跡を確定する
  4. `audit --diff-from HEAD` の結果は `current/baseline` を分離して記録する
- **効果**: warningドリフトと画面証跡の鮮度不明問題を同時に解消し、Phase 12 再確認の再現性を高める
- **適用条件**: UI機能で Phase 12 再確認を実施するタスク（特に `spec_created -> completed` 移行後）
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05B-SKILL-ADVANCED-VIEWS
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] UI6仕様書を1仕様書1SubAgentで同期固定（TASK-UI-05B）

- **状況**: UI機能の仕様更新で `arch-ui + arch-state` を同一担当に束ねると、責務境界と追跡性が曖昧になり、差し戻し時の再現性が落ちる
- **解決策**:
  1. UIプロファイルを 6責務（`ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` / `task-workflow` / `lessons-learned`）に分割する
  2. `spec-update-summary.md` と `task-workflow.md` に同一の6責務表を記録し、担当と依存順序を固定する
  3. 各仕様書に「実装内容 + 苦戦箇所 + 標準化ルール」の最小セットを残し、1仕様書単位で再利用可能にする
  4. `verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` / `audit --diff-from HEAD` を実行し、同期結果を同日証跡へ固定する
- **効果**: 仕様書ごとの説明責任が明確になり、再監査時の差し戻し箇所を即座に特定できる
- **適用条件**: UI機能実装で6仕様書同期（ui-ux/arch/task/lessons）が必要な Phase 12
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05B-SKILL-ADVANCED-VIEWS
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase 12] Step 2判定とchangelog同期の二重突合（TASK-10A-A）

- **状況**: `phase-12-documentation.md` では Step 2 必須なのに、`documentation-changelog.md` が `該当なし` と記録されて完了判定が揺れる
- **解決策**:
  1. Step 2 判定は `phase-12-documentation.md` の更新対象テーブルを正本として固定する
  2. `documentation-changelog.md` の Step 判定と `spec-update-summary.md` の更新対象一覧を同一ターンで突合する
  3. Step 2 対象仕様（UIの場合は `arch-ui-components.md`）を更新した後に `verify-all-specs` / `validate-phase-output` を再実行する
  4. `task-workflow.md` と `lessons-learned.md` に同一の苦戦箇所を転記し、再発条件と標準ルールを固定する
  5. 未タスク監査は `audit --diff-from HEAD` の `currentViolations` を合否、`baselineViolations` を監視として分離記録する
- **効果**: Step判定の誤りと証跡分散を同時に防ぎ、Phase 12 完了判定の再現性を高められる
- **適用条件**: UI機能で Step 2 のシステム仕様更新を伴う Phase 12（再監査含む）
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-A-SKILL-MANAGEMENT-PANEL
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] UI再撮影 + TCカバレッジ検証の同時固定（TASK-10A-C）

- **状況**: UI証跡を再撮影しても、TCと画像の紐付け検証を省略すると `manual-test-result.md` と実ファイルの対応がずれやすい
- **解決策**:
  1. `pnpm --filter @repo/desktop run screenshot:<feature>` で当日再撮影する
  2. `validate-phase11-screenshot-coverage.js --workflow <workflow-path>` を実行し、TC単位の欠落を機械検証する
  3. `ls -lt <workflow>/outputs/phase-11/screenshots` で更新時刻を確認し、証跡鮮度を台帳へ記録する
  4. `task-workflow.md` / `ui-ux-components.md` / `ui-ux-feature-components.md` に同一の検証値（撮影件数・TC件数）を同期する
- **効果**: 画面証跡の鮮度確認とTC紐付け確認を分離せず実施でき、Phase 11/12 の再監査差し戻しを抑制できる
- **適用条件**: UI機能の Phase 11/12 でスクリーンショットを完了証跡として扱う全タスク
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [screenshot-coverage.md](../../../../docs/30-workflows/completed-tasks/skill-create-wizard/outputs/phase-11/screenshot-coverage.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] 仕様書別SubAgent分担を完了台帳へ固定（TASK-10A-C）

- **状況**: `spec-update-summary.md` には分担を書いたが、`task-workflow.md` の完了記録に分担表が無く、再監査時の責務追跡が難しくなる
- **解決策**:
  1. `task-workflow.md` の対象タスク節へ `SubAgent-A..E` の分担表（api-ipc/interfaces/security/task/lessons）を転記する
  2. 各SubAgentの完了条件を「実装同期済み」「検証証跡同期済み」の2軸で明記する
  3. `spec-update-summary.md` と `task-workflow.md` の分担内容を同一ターンで一致させる
  4. `verify-all-specs` / `validate-phase-output` 実行後に分担表を最終更新して差分固定する
  5. `api-ipc/interfaces/security/task-workflow/lessons` の5仕様書すべてに「実装内容 + 苦戦箇所 + 簡潔手順」があることを最終確認する
- **効果**: 関心分離ベースの責務境界が台帳に残り、次タスクで再利用しやすくなる
- **適用条件**: 仕様書を複数SubAgentで同期する Phase 12 タスク全般
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] `phase-12-documentation.md` ステータス同期（TASK-9H)

- **状況**: `outputs/phase-12` の成果物とシステム仕様更新が完了していても、`phase-12-documentation.md` のメタ情報・完了条件チェックが `未実施` のまま残る
- **解決策**:
  1. `implementation-guide/spec-update-summary/documentation-changelog/unassigned-task-detection/skill-feedback-report` の5成果物を実体確認する
  2. `phase-12-documentation.md` のステータスを `完了` へ更新し、Step 1-A〜Step 3 と完了条件を同時チェックする
  3. `verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` / `audit --diff-from HEAD` の結果を `spec-update-summary.md` に固定する
  4. `task-workflow.md` と `lessons-learned.md` へ同一検証値を転記し、台帳間の不一致を解消する
- **効果**: 成果物実体と実行仕様書の二重台帳が一致し、再監査での差し戻し（「未実施残置」）を防止できる
- **適用条件**: Phase 12 の成果物作成と仕様更新が完了した最終同期フェーズ
- **発見日**: 2026-02-27
- **関連タスク**: TASK-9H
- **クロスリファレンス**: [phase-12-documentation.md](../../../../docs/30-workflows/TASK-9H-skill-debug/phase-12-documentation.md), [spec-update-summary.md](../../../../docs/30-workflows/TASK-9H-skill-debug/outputs/phase-12/spec-update-summary.md)

### [Phase 12] workflow 本文 `phase-1..11` の completed 同期（TASK-UI-02）

- **状況**: `artifacts.json` と `index.md` は completed でも、workflow 本文 `phase-1..11` の `ステータス` / 完了条件 / 実行タスク結果が `pending` のまま残ることがある
- **解決策**:
  1. `rg -n 'ステータス\\s*\\|\\s*pending' <workflow-path>/phase-{1,2,3,4,5,6,7,8,9,10,11}-*.md` で stale を検出する
  2. completed 扱いの Phase 本文は `ステータス=completed`、完了条件 `[x]`、実行タスク結果 `completed` へ同期する
  3. `phase-12-documentation.md` / `artifacts.json` / `outputs/artifacts.json` / `index.md` と同じターンで更新し、台帳を一本化する
  4. `verify-all-specs` / `validate-phase-output` / pending 検出 `rg` の結果を `spec-update-summary.md` に固定する
- **効果**: 「Phase 12 は完了だが前提 Phase 本文は未完了表示」というねじれを防ぎ、引き継ぎ根拠と監査の再現性を保てる
- **適用条件**: Phase 12 再監査、または worktree 上で Phase 1〜12 を完了同期するタスク全般
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-02
- **クロスリファレンス**: [phase12-task-spec-compliance-check.md](../../../../docs/30-workflows/task-057-ui-02-global-nav-core/outputs/phase-12/phase12-task-spec-compliance-check.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] テンプレートの正規経路固定（UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001）

- **状況**: Phase 12用テンプレートに旧環境依存パス（絶対パス）や旧成果物名が残ると、再利用時に誤実行や証跡欠落が発生する
- **解決策**:
  1. `assets/phase12-system-spec-retrospective-template.md` の検証コマンドを repo 相対パスへ統一する
  2. 成果物名を最新仕様（`unassigned-task-detection.md` / `skill-feedback-report.md`）へ同期する
  3. SubAgent分担（A:台帳/B:教訓/C:履歴/D:検証）をテンプレートに固定し、関心分離を標準化する
  4. 更新後に `quick_validate.js` と `verify-all-specs` を実行してテンプレート運用の整合を確認する
- **効果**: 環境依存による手順崩れを防ぎ、別ブランチ/別端末でも同じ実行結果を再現できる
- **適用条件**: Phase 12 テンプレートを新規作成・更新する全タスク
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md)

### [Phase 12] 未タスクメタ情報1セクション運用（TASK-9A再確認）

- **状況**: 未タスク指示書で `## メタ情報` が二重定義され、フォーマット監査時のノイズになる
- **解決策**:
  1. `## メタ情報` は1回のみ定義する
  2. `issue_number` の YAML とメタ情報テーブルは同一セクション内で連続配置する
  3. `rg -n "^## メタ情報" docs/30-workflows/unassigned-task/*.md` で1ファイル1件を機械確認する
- **効果**: 未タスクフォーマットの再監査コストを下げ、Phase 12の整合判定が安定する
- **適用条件**: 未タスク指示書を新規作成・更新する全ての Phase 12
- **発見日**: 2026-02-26
- **関連タスク**: TASK-9A-skill-editor
- **クロスリファレンス**: [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md)

### [Phase 12] getFileTree再同期の5点固定（UT-UI-05A-GETFILETREE-001）

- **状況**: IPC実装完了後に、仕様書同期・成果物命名・未タスク形式が別々に更新され、再確認で差し戻しが発生しやすい
- **解決策**:
  1. Step 2 は `api-ipc` / `ui-ux-feature` / `security` / `interfaces` / `task-workflow` の5仕様書を固定確認対象にする
  2. `phase-12-documentation.md` の成果物表と `outputs/phase-12` 実体を1対1で突合する
  3. 画面証跡は `outputs/phase-11/screenshots/*.png` を実際に開いて確認した上で同期する
  4. 未タスク指示書は `## メタ情報` 1セクション原則（YAML+表同居）を `rg` で機械確認する
  5. 合否判定は `audit --diff-from HEAD` の `currentViolations=0` に固定し、baselineは監視値として分離記録する
- **効果**: Phase 12再確認で発生しやすい「実装済みなのに文書だけ未同期」「命名揺れ」「形式ノイズ」を同時に抑止できる
- **適用条件**: IPC追加を伴う UIタスクで、Phase 11/12 の証跡と仕様更新を同一ターンで収束させる場合
- **発見日**: 2026-03-03
- **関連タスク**: UT-UI-05A-GETFILETREE-001
- **クロスリファレンス**: [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md), [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md)

### [Phase 12] SubAgent成果物の明示固定（UT-UI-05A-GETFILETREE-001）

- **状況**: 実装同期は完了していても、仕様書ごとの担当境界が成果物として残らないと、次回再確認で責務が再び曖昧化する
- **解決策**:
  1. `spec-update-summary.md` を `phase12-system-spec-retrospective-template` 準拠へ再構成する
  2. `spec-sync-subagent-report.md` を新規作成し、1仕様書=1SubAgentの責務/依存/完了条件を固定する
  3. Step 2 判定は `phase-12-documentation` / `documentation-changelog` / `spec-update-summary` の三点突合で確定する
  4. `task-workflow.md` と `lessons-learned.md` に同一の SubAgent分担と苦戦箇所を同一ターンで同期する
  5. 検証結果は `currentViolations=0` を合否、`baseline` を監視として分離記録する
- **効果**: 「実装はあるが責務定義が残らない」状態を防ぎ、次回の再確認コストを下げる
- **適用条件**: 複数仕様書を同時更新する Phase 12 タスク全般（特に UI + IPC 混在タスク）
- **発見日**: 2026-03-03
- **関連タスク**: UT-UI-05A-GETFILETREE-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase 12] 待機API/停止API責務分離の仕様固定（TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001）

- **状況**: `waitForCallback()` timeout 時に `stop()` まで実行すると、待機失敗と停止処理が結合して終了順序が不安定になる
- **解決策**:
  1. 実装を「待機責務（wait）」と「停止責務（stop）」へ分離し、timeout はエラー返却のみに限定する
  2. `stop()` に `!server || !server.listening` ガードを入れて冪等停止を保証する
  3. timeout テストに明示 `await stop()` を追加し、クリーンアップ責務を固定する
  4. 仕様同期は SubAgent 分担（security/task-workflow/lessons/validation）で同一ターン更新する
  5. `spec-update-summary.md` に検証値（13/13, 28項目, links 91/91, current=0, tests 13/13）を正本として固定する
- **効果**: 待機APIの副作用混在を防ぎ、同種の終了不安定バグを再発防止できる
- **適用条件**: timeout を持つ待機APIと明示停止APIが共存するタスク、特に Phase 12 Step 2 で仕様同期を伴う場合
- **発見日**: 2026-02-28
- **関連タスク**: TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [security-implementation.md](../../aiworkflow-requirements/references/security-implementation.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [ビルド・環境] モノレポ三層モジュール解決整合パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: モノレポ内パッケージ(@repo/shared)のサブパス import で tsc/vitest 両方が解決に失敗する
- **アプローチ**: exports(npm標準) / paths(TypeScript) / alias(Vitest) の3層を同一変更セットで更新し、整合性テストで固定化
- **結果**: 228件のTS2307エラーが0件に。224テストで3層整合を常時保証
- **適用条件**: モノレポで共有パッケージのサブパス import を使用する全プロジェクト
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001
- **クロスリファレンス**: [architecture-monorepo.md](../../aiworkflow-requirements/references/architecture-monorepo.md), [development-guidelines.md](../../aiworkflow-requirements/references/development-guidelines.md)

### [ビルド・環境] TypeScript paths 定義順序制御パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: tsconfig paths に複数のサブパスを定義する際、汎用パスが具体的パスより先にマッチしてしまう
- **アプローチ**: 具体的→汎用の順序で定義（例: `@repo/shared/types/llm/schemas` → `@repo/shared/types/llm` → `@repo/shared/types` → `@repo/shared`）。TypeScript は最初にマッチしたパスを使用するため順序が重要
- **結果**: 全27サブパスが正確に解決される
- **適用条件**: tsconfig paths でサブパスの階層が3レベル以上ある場合
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001

### [ビルド・環境] ソース構造二重性のパスマッピング吸収パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: shared パッケージ内で `types/auth.ts`(ルートレベル) と `src/types/index.ts`(src配下) が混在し、一律の paths 設定では解決不可
- **アプローチ**: 両系統を個別にマッピング。ルートレベル→直接参照、src配下→src/ 経由参照。package.json exports のエントリとの1:1対応を確認
- **結果**: 2系統のソース構造を透過的に扱える paths 設定が完成
- **適用条件**: パッケージ内でソースレイアウトが歴史的経緯で混在している場合
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001

### [テスト] 整合性テスト駆動の設定管理パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: exports/paths/alias の4ファイル同期が手動で漏れやすく、CI で初めてエラーが検出される
- **アプローチ**: 3スイート（module-resolution.test / shared-module-resolution.test / vitest-alias-consistency.test）のテストで設定間の整合性を自動検証。exports↔tsup、paths↔exports、alias↔paths の各対応をテストで固定化
- **結果**: サブパス追加時にテストが即座に不整合を検出。224テストで多角的に保証
- **適用条件**: 複数の設定ファイルが同期を必要とするモノレポ構成
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001
- **クロスリファレンス**: [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md)

### [UI] Props駆動Atoms設計（Store Hooks無限ループ対策）（TASK-UI-00-ATOMS）

- **状況**: UIコンポーネント（Atoms層）の新規作成で、Zustand Storeに依存させるか検討
- **アプローチ**: Atoms層をZustand Storeに依存させず、全コンポーネントをprops駆動で設計。状態管理はPages/Organisms層が担当
- **結果**: P31（Store Hooks無限ループ）のリスクを完全排除。テスト記述が大幅に簡素化（Storeモック不要、props渡しのみで動作検証）
- **適用条件**: Atomic Design の Atoms/Molecules 層のコンポーネント実装時
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../rules/06-known-pitfalls.md), [arch-state-management.md](../../aiworkflow-requirements/references/arch-state-management.md)

### [UI] Record型バリアント定義＋モジュールスコープ抽出（TASK-UI-00-ATOMS）

- **状況**: 複数バリアントを持つコンポーネント（Badge 6色、SkeletonCard 3種等）で、スタイルマッピングの型安全性とパフォーマンスを両立
- **アプローチ**: `Record<NonNullable<Props["variant"]>, string>` でスタイルマッピングを定義し、モジュールスコープに配置。新規バリアント追加時はRecord型に自動的にキーが追加される
- **結果**:
  - TypeScript型チェックで新規バリアント追加時のコンパイルエラー検出（スタイル定義漏れ防止）
  - React.memoの効果最大化（レンダリング毎のオブジェクト再生成を防止）
  - コードレビューで「このバリアントのスタイルは？」と探す手間が削減
- **適用条件**: 2つ以上のバリアントを持つUIコンポーネント
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS

```typescript
// モジュールスコープに配置（レンダリング毎の再生成を防止）
const variantStyles: Record<NonNullable<BadgeProps["variant"]>, string> = {
  default: "bg-gray-100 text-gray-800",
  primary: "bg-blue-100 text-blue-800",
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  error: "bg-red-100 text-red-800",
  info: "bg-indigo-100 text-indigo-800",
};

// 新しいバリアント "secondary" を Props に追加すると、
// variantStyles に "secondary" キーがないとTypeScriptエラーが発生
```

### [Testing] テーマ横断テスト（describe.each パターン）（TASK-UI-00-ATOMS）

- **状況**: 3テーマ（kanagawa-dragon/light/dark）対応コンポーネントのテストで、テーマ毎に同じテストケースを繰り返し記述
- **アプローチ**: `describe.each(["light", "dark", "kanagawa-dragon"])` でテーマ毎のテストを自動生成。各テーマで `data-theme` 属性を設定し、CSS変数ベースのスタイルをテスト
- **結果**:
  - テーマ追加時にテストケースが自動的に増加（新テーマを配列に追加するだけ）
  - 保守コスト最小化（テストロジックは1箇所のみ）
  - テーマ毎の差分が可視化される（どのテーマで失敗したかが明確）
- **適用条件**: デザイントークン（CSS変数）ベースのテーマ対応コンポーネント
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS

```typescript
describe.each(["light", "dark", "kanagawa-dragon"] as const)(
  "Theme: %s",
  (theme) => {
    it(`should render with ${theme} theme`, () => {
      const { container } = render(<Badge />, {
        wrapper: ({ children }) => (
          <div data-theme={theme}>{children}</div>
        ),
      });
      expect(container.firstChild).toHaveAttribute("data-theme", theme);
    });
  }
);
```

### [CI/ビルド] CIガードスクリプトによるモノレポ設定ファイル整合性自動検証（TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001）

- **状況**: モノレポの共有パッケージ（@repo/shared）で exports/paths/alias/typesVersions の4設定ファイルの同期漏れが発生し、228件のエラーを引き起こした
- **アプローチ**:
  1. **パーサー分離**: 各設定ファイル（JSON/TypeScript）に専用パーサーを作成（parseExports, parsePaths, parseAliases, parseTypesVersions）
  2. **双方向チェック**: exports→paths と paths→exports の両方向で整合性を検証。「追加忘れ」と「削除忘れ」を同時検出
  3. **キー変換ヘルパー**: 4種類のキー形式（`./utils`, `@repo/shared/utils`, `utils`）の相互変換を3ヘルパー関数で標準化
  4. **CIジョブ統合**: `check-module-sync` ジョブを build の前提条件として配置し、不整合時は build をブロック
  5. **process.exitCode**: `process.exit(1)` ではなく `process.exitCode = 1` でテスタビリティを確保
- **結果**: CI上で設定ファイル不整合を即座に検出。43テストで5チェック×正常/異常/エッジケースを網羅
- **適用条件**: モノレポで共有パッケージの設定ファイル間整合性を自動保証したい場合
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001
- **クロスリファレンス**: [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md), [architecture-monorepo.md](../../aiworkflow-requirements/references/architecture-monorepo.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [CI/ビルド] 正規表現ベースTypeScript設定ファイルパーサー（TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001）

- **状況**: vitest.config.ts の `resolve.alias` 設定を抽出する必要があるが、TypeScriptファイルのためJSON.parse()が不可能
- **アプローチ**:
  1. `resolve(__dirname, "path")` パターンに特化した正規表現を設計
  2. ダブルクォート前提・シングルクォート非対応・コメント非対応の制約を明文化
  3. タブ/スペース混在、マルチライン、0件パース時の警告出力をテストで固定化（#29-32）
  4. 正規表現の `lastIndex` リセット問題を回避するため、都度 `exec` ループを使用
- **結果**: vitest.config.ts から @repo/shared 関連のalias定義を正確に抽出。制約はテストで明示的に文書化
- **適用条件**: TypeScript設定ファイル（vitest.config.ts, jest.config.ts等）から特定パターンの設定値を抽出する場合
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001

### [IPC] IPCチャネル名競合の予防的解消パターン（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: 既存 `skill:import`（ローカル用、引数: `string`）と TASK-9F の外部ソースインポート（引数: `ShareTarget`）が同一チャネル名を使用する設計で、`ipcMain.handle()` の二重登録例外（P5）が実装段階で100%発生する構造的問題
- **アプローチ**: コード実装前に仕様書段階でチャネル名を分離する「予防的仕様書修正」
  - 命名規則を体系化: `skill:{動詞}` / `skill:{動詞}FromSource` / `skill:{動詞}Source`
  - 2つの仕様書（task-022, task-030）を同時修正し、6箇所のチャネル名を統一変更
  - grep ベースの整合性検証（10項目）で修正漏れを検出
- **結果**: Phase 10 最終レビュー PASS（MINOR 0件）、Phase 11 手動テスト 11/11 PASS。TASK-9F 実装時の P5 リスクを仕様段階で排除
- **適用条件**: 既存チャネルと同じ動詞を使う新機能を追加する場合。特に引数型が異なる場合は必須
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001
- **クロスリファレンス**:
  - [architecture-implementation-patterns.md#IPCチャネル名競合予防パターン](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)
  - [06-known-pitfalls.md#P5](../../rules/06-known-pitfalls.md)
  - [06-known-pitfalls.md#P44](../../rules/06-known-pitfalls.md)

### [Phase12] 仕様書修正のみタスクの Phase テンプレート（N/A記録）（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: コード変更を伴わない仕様書修正タスクで、Phase 6（テスト拡充）・7（カバレッジ）・8（リファクタリング）が不要
- **アプローチ**: 各 Phase に `not-applicable.md` を作成し、N/A 理由を明記
  - Phase 6: 「代替検証」セクションで grep 検証が唯一のテスト手段であることを記録
  - Phase 7-8: N/A 理由のみ記録
  - Phase 4 の grep コマンドが実質的なテストスイートとして機能
  - Phase 9 は grep ベースの品質ゲート4項目（整合性・新チャネル・既存互換・Markdown構文）で代替
- **結果**: 全 Phase 1-12 で成果物が outputs/ 配下に出力され、仕様書修正のみタスクの標準フローとして先例を確立
- **適用条件**: `taskType: "spec-only"` または `taskType: "spec_created"` のタスク
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001

### [Testing] grepベース仕様書整合性検証（仕様書TDD）（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: コード変更がないため Vitest/ESLint 等の標準ツールが使えず、仕様書修正の品質保証手段が必要
- **アプローチ**: Phase 4 で grep 検証コマンドを「テストケース」として設計し、Phase 5 実装後に全実行
  - 旧チャネル名残存検出（期待: 0件）
  - 新チャネル名使用確認（期待: N件以上）
  - 既存互換性検証（ローカル用 `skill:import` が保持されていること）
  - artifacts.modifies の正確性検証
  - Markdown テーブル構文検証
- **結果**: 10検証項目全 PASS。Phase 9 品質ゲートでも同じ grep コマンドを再利用して4ゲート全 PASS
- **適用条件**: 仕様書修正のみタスク、または複数仕様書の横断的一貫性を検証する場合
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001

### [IPC] P42準拠バリデーション一括移行（return→throw統一）（UT-FIX-SKILL-VALIDATION-CONSISTENCY-001）

- **状況**: 6つのIPCハンドラ（skill:get-detail, skill:execute, skill:abort, skill:get-status, skill:analyze, skill:improve）で異なるバリデーションパターンが混在（return false/return null/return { success: false }/throw の4種類）
- **アプローチ**: `typeof arg !== "string" || arg.trim() === ""` + `throw { code: "VALIDATION_ERROR" }` の統一パターンを全ハンドラに適用
  - オブジェクト型引数（`args.skillId`等）: 4ハンドラ
  - 直接引数型（`executionId`）: 2ハンドラ
  - 全ハンドラでエラー応答を `return` から `throw` に統一
- **結果**: 59テスト追加（skillHandlers.validation.test.ts）、181テスト全PASS。safeInvokeがRenderer側でthrowをキャッチするため後方互換性維持
- **適用条件**: IPCハンドラのバリデーションパターンが不統一で、P42準拠への一括移行が必要な場合
- **教訓**: throw統一はRenderer側のsafeInvoke設計に依存するため、Preload層の実装を事前確認する。safeInvokeがtry/catchでエラーをラップしている場合のみ、return→throw移行が安全
- **発見日**: 2026-02-24
- **関連タスク**: UT-FIX-SKILL-VALIDATION-CONSISTENCY-001
- **関連Pitfall**: P42（.trim()バリデーション漏れ）、P44（IPC引数不整合）

### [Testing] 引数形式差異の分類と共通化判断（YAGNI）（UT-FIX-SKILL-VALIDATION-CONSISTENCY-001）

- **状況**: 6ハンドラ中4つがオブジェクト型（`args.skillId`等）、2つが直接引数型（`executionId`）で、共通バリデーション関数の抽出を検討
- **アプローチ**: 引数アクセスパターンの違い（`args.skillId` vs `executionId`）により、共通関数では引数抽出ロジックまでカバーする必要があり、抽象化コストが利益を上回ると判断。インライン3行バリデーションを各ハンドラに一貫して適用
- **結果**: 各ハンドラが独自の引数アクセスパターンを保持しつつ、バリデーションロジック自体は統一。59テストで正確性を保証
- **適用条件**: 複数ハンドラのバリデーション統一時、引数形式が異なる場合
- **教訓**: YAGNI原則 — 引数形式が統一されるまで共通関数を作らない。3行のインラインバリデーションは許容範囲。将来引数形式が統一された際に初めて共通関数を抽出する
- **発見日**: 2026-02-24
- **関連タスク**: UT-FIX-SKILL-VALIDATION-CONSISTENCY-001

### [Phase 12] 仕様書修正タスクの簡略Phase適用

- **状況**: コード変更なしの仕様書修正タスク（UT-IPC-DATA-FLOW-TYPE-GAPS-001）で、Phase 4-7-11が本来の意味（ユニットテスト、カバレッジ、UIテスト）と合致しなかった
- **アプローチ**:
  - Phase 4: grep正規表現パターンによる検証基準設計（49項目）
  - Phase 5: 仕様書修正実行（7ファイル、28修正項目）
  - Phase 6-7: grepベース整合性検証（24項目）+ 網羅性確認（49項目）
  - Phase 11: 実装者視点レビュー（3視点×3ケース = 9テスト）
- **結果**: 173検証項目ALL PASS。コード変更なしでも品質保証を別手段で実現
- **適用条件**: 仕様書修正のみタスク、ドキュメント横断修正タスク
- **教訓**: 各Phaseを「N/A」で飛ばすのではなく、同等の品質保証を別手段で設計すべき
- **発見日**: 2026-02-24

### [IPC] IPC Date→ISO 8601統一（仕様書段階での予防）

- **状況**: 4ファイル×14フィールドのDate型がIPC境界でのシリアライズ方針未定義だった
- **アプローチ**:
  - 全Date型フィールドに `string; // ISO 8601` 注記を追加
  - Main Process側の `.toISOString()` 変換パターンを仕様書に明記
  - Renderer側の `new Date(isoString)` 復元パターンを仕様書に明記
- **結果**: 後続実装者がIPCシリアライズについて迷う余地を排除
- **適用条件**: IPC境界を越えるDate型フィールドを含む仕様書
- **教訓**: 仕様書段階でIPC型変換ルールを明示しておくことで、実装時のバグを予防できる
- **発見日**: 2026-02-24

### [IPC] ハンドラ Graceful Degradation（safeRegister + track クロージャ）

- **状況**: `registerAllIpcHandlers()` 内で1つのハンドラ登録関数が例外を投げると、後続の全ハンドラが未登録のまま残る
- **アプローチ**:
  - `safeRegister(name, fn)` 内部ヘルパーで個別 try-catch。失敗時は `HandlerRegistrationFailure` を記録して次へ進む
  - `track()` クロージャで成功/失敗カウントを自動管理し、`IpcHandlerRegistrationResult` として集約
  - `sanitizeRegistrationErrorMessage()` でエラーメッセージ中のユーザーホームディレクトリパスを `~` にマスク
  - 戻り値が必要な `setupThemeWatcher` は個別 try-catch で対応（safeRegister 不適合パターンの認識）
- **結果**: 部分的なハンドラ登録失敗時でも、無関係な機能は正常に動作。失敗情報は構造化されて返却
- **適用条件**: 複数の独立した初期化処理を順次実行し、1つの失敗が全体を止めてはいけない場合
- **教訓**:
  - 戻り値キャプチャが必要な場合は `safeRegister` パターンが使えない。設計時に判別が必要
  - `os.homedir()` のパスは正規表現メタ文字を含む可能性があり、`escapeRegExp()` が必須
  - テスト時は `vi.hoisted()` で 30+ のモック変数を宣言し、個別の throw 制御で部分失敗をシミュレート
- **発見日**: 2026-03-08
- **関連タスク**: TASK-FIX-IPC-HANDLER-GRACEFUL-DEGRADATION-001

### [IPC] safeInvoke timeout による IPC hang containment（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: Preload の `safeInvoke()` が `ipcRenderer.invoke()` をそのまま返すため、Main Process 未応答時に Renderer が永続 pending。認証初期化の loading state が落ちず画面遷移が停止
- **アプローチ**:
  - `Promise.race([ipcRenderer.invoke(...), timeoutPromise])` で 5秒タイムアウトを共通適用
  - `IPC_TIMEOUT_MS` をファイルスコープ定数で管理。error 文言に channel 名 + timeout 値を含める
  - whitelist チェックは `Promise.race` の前段で維持し、セキュリティ境界を変更しない
  - `clearTimeout` は省略（5秒タイマーは自動GC。UI頻度のIPC呼び出しでは不要）
- **結果**: 12テスト全PASS、548テスト回帰なし。関数シグネチャ・戻り値の型に変更なし
- **適用条件**: Preload 共通ラッパーで多数の invoke を集約し、Renderer に loading state がある場合
- **苦戦箇所**: contextBridge mock capture パターン（`exposeInMainWorld` キャプチャ + `process.contextIsolated = true`）の発見に試行錯誤。fake timer + module re-import の実行順序（P13準拠）
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [テスト] contextBridge mock capture パターン（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: Preload の `safeInvoke` は `contextBridge.exposeInMainWorld` 経由でのみ公開される。直接 import してもテストできない
- **アプローチ**:
  - `vi.mock("electron")` で `contextBridge.exposeInMainWorld` をキャプチャ関数に差し替え
  - `Object.defineProperty(process, "contextIsolated", { value: true })` で contextBridge パスを強制通過
  - `beforeEach` で `vi.resetModules()` → API キャプチャ変数リセット → `await import("../index")` でクリーンな再初期化
- **結果**: Electron Preload 内部関数の完全なテストが可能に。12テストケースで全分岐をカバー
- **適用条件**: `contextBridge.exposeInMainWorld` で公開される Preload API のユニットテスト全般
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [Phase12] 3workflow再監査 + 未タスク個別監査の二段固定（TASK-FIX-SKILL-IMPORT 3連続是正）

- **状況**: `01/02/03` の3workflowを同時に再監査する際、Phase 12合否（構造/成果物/未タスク）を1回で固定しないと、台帳転記で数値ドリフトが起きやすい
- **アプローチ**:
  1. `verify-all-specs --workflow` を3workflowへ並列実行し、`13/13 PASS` を同時確定する
  2. `validate-phase-output <workflow-dir>` を3workflowへ並列実行し、`28項目 PASS` を同時確定する
  3. UI workflow で `validate-phase11-screenshot-coverage` を実行し、TCカバレッジを固定する
  4. 未タスクは `verify-unassigned-links` と `audit --diff-from HEAD` で全体判定（`current=0`）を確定する
  5. `audit --target-file` は `scope.currentFiles` 一致を確認し、個別判定（`current=0`）として分離記録する
- **結果**: Phase 12 合否の根拠が「3workflow束 + 未タスク全体 + 未タスク個別」の3軸で固定され、再確認時の差し戻しを削減できる
- **適用条件**: 複数workflowを同時に再監査し、未タスクの配置・フォーマットも同ターンで確認する場合
- **教訓**: 合否判定は `currentViolations` を正本に固定し、`baseline` は改善バックログとして分離する
- **発見日**: 2026-03-04
- **関連タスク**: 01-TASK-FIX-SKILL-IMPORTED-STATE-RECONCILIATION-001 / 02-TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001 / 03-TASK-FIX-SKILL-CENTER-METADATA-DEFENSIVE-GUARD-001

### [Phase12] UI再撮影前 preview preflight + 失敗時未タスク化固定（SkillCenter）

- **状況**: UI再撮影の開始後に `ERR_CONNECTION_REFUSED` と module resolve error が発生し、スクリーンショット更新が途中停止した
- **アプローチ**:
  1. `pnpm --filter @repo/desktop preview` を先に実行し、build成否を preflight で判定する
  2. `127.0.0.1:4173` の疎通確認が通った場合のみ `capture-*.mjs` を実行する
  3. 失敗時は再撮影を継続しないで未タスク化し、既存証跡の時刻と代替理由を Phase 12 成果物へ記録する
  4. `validate-phase11-screenshot-coverage` は既存証跡で PASS 維持を確認し、差分監査は `currentViolations=0` を固定する
  5. `phase12-system-spec-retrospective-template` / `phase12-spec-sync-subagent-template` の UIチェックへ preflight 成否と失敗時分岐を転記し、`task-workflow` / `lessons` へ同一ターン同期する
- **結果**: 撮影フロー停止時でも「未タスク化 + 代替証跡記録」で完了判定の再現性を維持できる
- **適用条件**: UI/UX変更タスクで再撮影を要求し、preview 起動失敗が再発し得る場合
- **教訓**: UI再撮影は「preflight成功」が前提条件。前提不成立時は実装修正と運用ガードを分離して扱う
- **発見日**: 2026-03-04
- **関連タスク**: 03-TASK-FIX-SKILL-CENTER-METADATA-DEFENSIVE-GUARD-001 / UT-IMP-SKILL-CENTER-PREVIEW-BUILD-GUARD-001

### [Phase12] UI再確認の準拠チェック成果物固定（TASK-UI-00-ORGANISMS）

- **状況**: UIタスクの再確認で `verify/validate` はPASSでも、Task 1〜5 / Step 1-A〜1-E / Step 2 の判定根拠が複数ファイルへ分散しやすい
- **アプローチ**:
  1. `verify-all-specs` / `validate-phase-output` / `validate-phase11-screenshot-coverage` / `verify-unassigned-links` / `audit --diff-from HEAD` を同一ターンで実行する
  2. UI証跡は `pnpm run screenshot:<feature>` 実行後に `stat` で時刻を取得し、`manual-test-result.md` と同期する
  3. `outputs/phase-12/phase12-task-spec-compliance-check.md` を作成し、Task 1〜5 と Step判定を1ファイルに集約する
  4. `task-workflow.md` と `lessons-learned.md` に実装内容・苦戦箇所・検証値を同時転記する
- **結果**: Phase 12 の再監査根拠が一本化され、証跡鮮度ドリフトと判定漏れを同時に防止できる
- **適用条件**: UI/UX実装タスクのブランチ再確認、または複数文書へ同時同期が必要な Phase 12
- **教訓**: 再確認タスクでは「成果物作成」よりも「判定根拠の集約」が品質を左右する
- **発見日**: 2026-03-04
- **関連タスク**: TASK-UI-00-ORGANISMS

### [Phase12] 実装内容+苦戦箇所の仕様書統一フォーマット（TASK-UI-00-ORGANISMS追補）

- **状況**: system spec へ反映するとき、仕様書ごとに記述粒度が異なり「実装内容はあるが苦戦箇所がない」状態が起きやすい
- **アプローチ**:
  1. `task-workflow` / `<domain-spec>` / `lessons-learned` の順で更新し、仕様書ごとの責務境界を固定する
  2. 各仕様書に `実装内容（要点）` と `苦戦箇所（再発条件付き）` を必須ブロックとして同時記載する
  3. UIタスクは `manual-test-result` と `screenshots/*.png` の時刻整合（`stat`）を必須チェックにする
  4. 検証値（verify/validate/links/audit）は `task-workflow` と `lessons` で同値転記する
- **結果**: 仕様書ごとの記録粒度がそろい、同種課題でそのまま再利用できるテンプレート化が可能になる
- **適用条件**: Phase 12 Step 2 で複数仕様書へ同時反映するタスク
- **教訓**: 「何を実装したか」と「どこで苦戦したか」は同じ粒度で残すほど再利用性が高い
- **発見日**: 2026-03-04
- **関連タスク**: TASK-UI-00-ORGANISMS

### [Phase12] current=0 と baseline backlog の二層管理（TASK-043B）

- **状況**: `audit-unassigned-tasks --diff-from HEAD` では `currentViolations=0` を維持できているが、repository 全体には `baselineViolations>0` が残っており、feature 差分と legacy 負債を混同しやすい
- **アプローチ**:
  1. Phase 12 の feature 合否は `currentViolations=0` を正本に固定する
  2. `baselineViolations>0` が残る場合は、feature バグと混ぜずに `docs/30-workflows/unassigned-task/` 配下へ運用改善未タスクを作成する
  3. 新規未タスク仕様書は `audit-unassigned-tasks --json --target-file <unassigned-file>` で `currentViolations=0` と `scope.currentFiles=1` を確認する
  4. 判定根拠が `spec-update-summary` / `documentation-changelog` / `unassigned-task-detection` / `skill-feedback-report` に分散する場合は `phase12-task-spec-compliance-check.md` を追加し、Task 12-1〜12-5 / Step 1-A〜1-G / Step 2 を 1 ファイルへ集約する
  5. `task-workflow.md` / `lessons-learned.md` / `<domain-spec or ui-ux-feature-components.md>` に同一ターンで「実装内容 + 苦戦箇所 + 簡潔手順」を同期する
- **結果**: feature 実装の完了判定を保ったまま、legacy 負債を隠さず改善 backlog として管理できる
- **適用条件**: Phase 12 再確認で feature 差分は健全だが、未タスク監査の baseline が残る場合
- **教訓**: 未タスク監査は「差分合否」と「運用負債の改善導線」を分けて記録すると再利用性が高い
- **発見日**: 2026-03-06
- **関連タスク**: TASK-043B / UT-IMP-UNASSIGNED-TASK-LEGACY-NORMALIZATION-001

### [Phase12] 同種課題の5分解決カード同期（TASK-UI-00-FOUNDATION-REFLECTION-AUDIT）

- **状況**: 検証値と苦戦箇所は反映済みでも、再実行時の最短手順が仕様書ごとに分散して再利用しづらい
- **アプローチ**:
  1. `task-workflow.md` に再検証値（13/13, 28項目, TC, links, current/baseline）を固定し、「5分解決カード」を追記する
  2. `lessons-learned.md` に同一カード（症状1行/原因1行/最短5手順/検証ゲート）を転記する
  3. UI系タスクでは `ui-ux-feature-components.md` に同一カードを追記し、UI導線へ接続する
  4. 3仕様書で5ステップ順序（実体固定→仕様是正→画面証跡→未タスク監査→台帳同期）が一致していることを最終チェックする
  5. テンプレート（`phase12-system-spec-retrospective` / `phase12-spec-sync-subagent`）へ同カード要件を反映し、次回はテンプレ起点で開始する
- **結果**: 同種課題で調査開始から是正完了までの手順が固定化され、再監査の初動が短縮される
- **適用条件**: Phase 12 Step 2で「実装内容 + 苦戦箇所 + 検証証跡」を複数仕様書へ同期するタスク
- **教訓**: カードは「情報の要約」ではなく「再実行可能な手順の固定」として運用する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] Phase11文書名固定 + TC証跡1:1 + changelog完了記述の三点同期（TASK-10A-F）

- **状況**: Phase 12再監査で、Phase11文書名ドリフト・TC証跡リンク漏れ・`documentation-changelog.md` の計画文残置が同時に発生しやすい
- **アプローチ**:
  1. `validate-phase12-implementation-guide` で Part 1/2、型定義、エッジケース、設定一覧の必須要件を機械検証する
  2. `validate-phase11-screenshot-coverage` と `manual-test-result.md` を突合し、TCごとに証跡を 1:1 固定する（`screenshots/*.png` または `NON_VISUAL:`）
  3. `documentation-changelog.md` は「実更新ログのみ」にし、`予定/計画` の文言を残さない
  4. `task-workflow.md` / `lessons-learned.md` / `<domain-spec>` に「実装内容 + 苦戦箇所 + 検証値」を同一ターンで同期する
  5. 未実施項目は `docs/30-workflows/unassigned-task/` に10見出しテンプレートで起票し、`audit --target-file` で個別検証する
- **結果**: Phase 12の完了判定根拠が揃い、文書名・証跡・進捗表現のドリフトを同時に防止できる
- **適用条件**: 再監査で「実装は完了しているが文書運用に差分」が残るタスク
- **教訓**: Phase 12は「作ること」より「同期を崩さないこと」を完了条件に置く
- **発見日**: 2026-03-07
- **関連タスク**: TASK-10A-F

### [Phase12] comparison baseline 正規化つき branch 再監査（TASK-10A-F）

- **状況**: current workflow は PASS でも、comparison baseline の completed workflow に legacy 名称・欠落補助成果物・古い artifact registry が残ると branch 全体の結論がぶれる
- **アプローチ**:
  1. current workflow に `verify-all-specs --strict` / `validate-phase-output` / `validate-phase12-implementation-guide` を実行する
  2. comparison baseline の completed workflow にも `verify-all-specs --strict` / `validate-phase-output` を実行する
  3. completed workflow に `phase-7-coverage-check.md` / `phase-11-manual-test.md` / `outputs/artifacts.json` / `screenshot-plan.json` / `discovered-issues.md` などの不足があれば同一ターンで補完する
  4. `spec-update-summary.md` / `phase12-task-spec-compliance-check.md` / `task-workflow.md` に current 合格値と baseline 正規化結果を分離記録する
  5. 未タスク監査は `currentViolations=0` を合否、`baselineViolations>0` を legacy 負債として扱い、必要なら正規化ガード未タスクを参照する
- **結果**: 「current は通るが baseline が壊れていて branch verdict が不安定」という状態を防止できる
- **適用条件**: `spec_created` workflow と completed workflow を同時に再監査する Phase 12 タスク
- **発見日**: 2026-03-08
- **関連タスク**: TASK-10A-F

### [Phase12] 並列エージェント台帳同期パターン（TASK-10A-F）

- **状況**: 複数サブエージェントが `artifacts.json` や `outputs/artifacts.json` を独立に更新する
- **問題**: サブエージェントA が Phase 1-3 を completed に更新、メインが Phase 4-10 を更新すると、`outputs/artifacts.json` の Phase 4-10 が pending のまま残る
- **解決策**:
  1. サブエージェントには **読み取り + 検証レポート出力** のみを委譲
  2. 台帳ファイル（`artifacts.json`, `outputs/artifacts.json`, `index.md`）の更新はメインエージェントが一括実行
  3. 更新後に `cp artifacts.json outputs/artifacts.json` で強制同期
  4. `diff artifacts.json outputs/artifacts.json` で同期確認
- **適用条件**: Phase 12 で複数サブエージェントを並列運用する場合
- **教訓**: 台帳ファイルの更新権限を1箇所に集約しないと、並列更新による上書き競合が発生する
- **発見日**: 2026-03-08
- **関連パターン**: P43（サブエージェント rate limit 中断）、S8（lessons-learned.md）
- **関連タスク**: TASK-10A-F

### [Phase12] Store駆動移行の仕様書更新チェックリスト（TASK-10A-F）

- **状況**: 直接IPC呼び出し → Store action 経由への移行完了後の仕様同期
- **チェックリスト**:
  1. `arch-state-management.md` に個別セレクタ一覧と検証結果を追記
  2. `task-workflow.md` の完了台帳を更新（テスト件数・IPC残存0件）
  3. `lessons-learned.md` に苦戦箇所と再利用手順を追加
  4. LOGS.md x2 + SKILL.md x2 の4ファイル更新（P1/P25 準拠）
  5. `generate-index.js` で topic-map / keywords 再生成（P2/P27 準拠）
  6. SubAgent分担: references 仕様書別に独立エージェントで並列更新
- **適用条件**: Store駆動移行タスク（直接IPC → Zustand Store action）の Phase 12 実行時
- **教訓**: Store移行はコード変更より仕様同期の方が工数がかかる。チェックリストで漏れを防止する
- **発見日**: 2026-03-08
- **関連パターン**: S10（P31/P48 標準パターン）、Phase 12 テンプレート
- **関連タスク**: TASK-10A-F

## 失敗パターン（避けるべきこと）

失敗から学んだアンチパターン。

### [Phase12] 成果物名の暗黙的解釈

- **状況**: Phase 12で`implementation-guide.md`を`documentation.md`として生成
- **問題**: 仕様書との不整合、後続処理でのファイル参照エラー
- **原因**: 仕様書の成果物名を正確に確認せず暗黙的に命名
- **教訓**: Phase仕様書の「成果物」セクションを必ず確認し、ファイル名を厳密に一致させる
- **発見日**: 2026-01-22

### [Phase12] 実装ガイドへの誤ファイル名混入（TASK-FIX-14-1）

- **状況**: 実装ガイドに `SkillPermissionService.ts` など実差分に存在しないファイル名を記載
- **問題**: レビューと再現手順が実装事実と一致せず、監査で差し戻しが発生
- **原因**: 実差分参照を省略し、過去の想定ファイル名を転記
- **教訓**: Phase 12のファイル一覧は必ず `git diff` を一次情報として確定し、成果物と突合する
- **対策**: 文章確定前に「記載ファイル名 ⊆ git差分一覧」の機械チェックを追加
- **発見日**: 2026-02-14
- **関連タスク**: TASK-FIX-14-1-CONSOLE-LOG-MIGRATION

### [Phase12] Phase 12サブタスクの暗黙的省略

- **状況**: Phase 12完了時に「実装ガイド作成」のみ実行し、「システム仕様書更新」を省略
- **問題**: システム仕様書に完了記録が残らず、成果が追跡できない
- **原因**: Phase 12が複数サブタスク（12-1, 12-2, 12-3）を持つことの認識不足
- **教訓**: Phase 12実行時は必ずサブタスク一覧を確認し、全タスクの実行を確認する
- **発見日**: 2026-01-22
- **対策済み**: phase-templates.md v7.6.0で完了条件チェックリストを強化

### [Phase12] 仕様書作成タスクの completed 誤判定

- **状況**: 実装未着手の仕様書タスクを `completed` と登録
- **問題**: 「仕様書完了」と「実装完了」が混同し、進捗台帳の意味が崩れる
- **原因**: Step 1-B の判定ルールが `未実装→完了` の単一ルールになっていた
- **教訓**: 実装未着手タスクでは `spec_created` を使い、`completed` を使わない
- **対策**: spec-update-workflow に判定分岐（`completed` / `spec_created`）を明文化する
- **発見日**: 2026-02-19
- **関連タスク**: TASK-9A-C

### [Phase12] 全体ベースライン違反の今回起因誤判定

- **状況**: 全体監査で多数違反が出た際、対象タスクの新規差分と既存負債を分離せずに「今回の不備」と判定してしまう
- **問題**: 本来不要な大規模修正を誘発し、今回タスクの完了判断が遅延する
- **原因**: 監査スコープ（repo-wide）とレビュー対象（今回差分）の境界を定義していない
- **教訓**: Phase 12報告では「全体件数」と「対象ファイル件数」を必ず別指標で提示する

### [Phase12] Phase11文書名ドリフトとTC証跡未同期を放置（TASK-10A-F）

- **状況**: `phase-11-execution.md` と実体ドキュメント名がずれたまま、TC証跡が `manual-test-result.md` とリンクしない状態で完了判定した
- **問題**: `validate-phase11-screenshot-coverage` / `validate-phase12-implementation-guide` は通るが、実運用で参照追跡が困難になる
- **原因**: 実装要件の検証結果だけを見て、文書間参照と changelog の完了記述まで確認しなかった
- **教訓**: Phase 12完了前に「文書名固定」「TC証跡1:1」「changelog完了記述」の三点を機械検証 + 目視確認する
- **対策**: 未解決項目は即時に `docs/30-workflows/unassigned-task/` へ起票し、`task-workflow/lessons` へ同ターン反映する
- **発見日**: 2026-03-07
- **関連タスク**: TASK-10A-F

### [Phase12] current workflow PASS だけで comparison baseline を放置

- **状況**: current workflow の validator だけ通し、comparison baseline の completed workflow は未確認のまま branch 全体の結論を書く
- **問題**: baseline 側の legacy drift が比較結果へ混入し、再監査ごとに結論が変わる
- **原因**: 「履歴保管先だから strict 検証不要」という誤判断で completed workflow の正規化を省略する
- **教訓**: comparison baseline を使うなら current と同じ粒度で validator を通してから比較する
- **対策**: `verify-all-specs --strict` / `validate-phase-output` を current と completed の両workflowへ実行し、結果を分離記録する
- **発見日**: 2026-03-08
- **関連タスク**: TASK-10A-F
- **対策**: 監査テンプレートに「baseline / scope-of-change」2列を追加し、対象ファイルの個別検証結果を併記する
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001

### [Phase12] spec_created/完了workflow混在時の証跡分散

- **状況**: spec_createdタスクと完了タスクを同時再監査した際、結果をworkflow単位で整理せずに記録してしまう
- **問題**: どのworkflowが何を満たしたか追跡できず、Phase 12完了判定が曖昧になる
- **原因**: 監査対象workflowの固定と、Task 1/3/4/5実体突合の対応表を先に作っていない
- **教訓**: 複数workflow監査時は「workflow固定→構造検証→出力検証→成果物突合」の順で記録を統一する
- **対策**: 監査テンプレートに workflow別証跡表を追加し、合否指標は `currentViolations` 固定で記録する
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05A-SKILL-EDITOR-VIEW, TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] 5分解決カードをtask-workflowのみ更新して他仕様へ未同期

- **状況**: `task-workflow.md` には最短手順を追記したが、`lessons-learned.md` と `ui-ux-feature-components.md` への同一カード転記を省略する
- **問題**: 再利用時に参照仕様書ごとに手順が分断され、SubAgent分担の初動が遅れる
- **原因**: 「台帳更新だけで十分」という誤判断で、3仕様書同時同期チェックを省略した
- **教訓**: 5分解決カードは `task-workflow` 単独では成立しない。`task-workflow + lessons + domain/UI spec` の3点同期が必要
- **対策**: `phase12-system-spec-retrospective-template` と `phase12-spec-sync-subagent-template` の完了チェックに「3仕様書同一カード」を必須化する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] UI再撮影後にTCカバレッジ検証を省略

- **状況**: スクリーンショットを再取得して `ls` だけ確認し、TC紐付け検証（coverage validator）を実施せず完了判定する
- **問題**: 画像枚数が揃っていても TC欠落や命名不一致を見逃し、`manual-test-result` の証跡信頼性が低下する
- **原因**: 「再撮影」と「TC紐付け検証」を別工程として扱い、後者を必須化していない
- **教訓**: UI証跡は「再撮影 + TCカバレッジ検証 + 更新時刻確認」の3点セットで完了判定する
- **対策**: `validate-phase11-screenshot-coverage.js --workflow <workflow-path>` を Phase 12 標準コマンドへ追加し、`PASS` を台帳へ転記する
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C

### [Phase12] preview成否確認なしで再撮影開始（ERR_CONNECTION_REFUSED）

- **状況**: 再撮影コマンドを先に起動し、`preview` build 失敗（module resolve error）に気づかず `ERR_CONNECTION_REFUSED` で停止する
- **問題**: 画面証跡更新が途中で止まり、Phase 11/12 の完了判定が「撮影未実施」か「実行不能」か曖昧になる
- **原因**: `preview` 起動可否を前提チェックに含めず、撮影スクリプトを直接実行している
- **教訓**: UI再撮影の必須前提は `preview preflight`。前提未成立時は未タスク化して運用課題を切り出す
- **対策**: `pnpm --filter @repo/desktop preview` の build成否 + `127.0.0.1:4173` 疎通を記録してから撮影し、失敗時は `UT-IMP-SKILL-CENTER-PREVIEW-BUILD-GUARD-001` へ即時登録する。あわせて Phase 12 テンプレート（`phase12-system-spec-retrospective` / `phase12-spec-sync-subagent`）の UI完了チェックにも preflight 分岐を必須記録する
- **発見日**: 2026-03-04
- **関連タスク**: 03-TASK-FIX-SKILL-CENTER-METADATA-DEFENSIVE-GUARD-001

### [Phase12] preview/search を feature spec のみに閉じて cross-cutting spec を未同期

- **状況**: `ui-ux-feature-components.md` と `task-workflow.md` だけを更新し、`ui-ux-search-panel.md` / `ui-ux-design-system.md` / `error-handling.md` / `architecture-implementation-patterns.md` を未同期のまま完了扱いにする
- **問題**: shortcut、dialog token、error severity、renderer fallback の参照先が分断され、次回の類似タスクで同じ判断をやり直すことになる
- **原因**: UI基本6+αで十分と誤認し、preview/search 固有の cross-cutting 追加仕様を判定していない
- **教訓**: preview/search 系 UI は feature spec だけでは閉じない。検索挙動、token、error contract、実装パターンを別仕様へ振り分ける必要がある
- **対策**: `phase12-system-spec-retrospective-template` と `phase12-spec-sync-subagent-template` に cross-cutting matrix を追加し、該当4仕様書の同一ターン更新を完了条件にする
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-04C-WORKSPACE-PREVIEW

### [Phase12] Port 5174 競合ログ混在を未記録のまま完了判定

- **状況**: screenshot 再取得は成功したが `Port 5174 is already in use` が同時出力され、警告を未記録のまま完了扱いにしやすい
- **問題**: 実行可否の判定根拠が曖昧になり、再監査時に「成功なのか環境エラーなのか」の説明コストが増える
- **原因**: screenshot 実行前のポート占有確認手順と競合時分岐（停止/再利用）の記録要件がテンプレートに固定されていない
- **教訓**: UI再撮影では preflight に「preview成否 + ポート占有」を含め、競合時の判断ログを必ず残す
- **対策**: `lsof -nP -iTCP:5174 -sTCP:LISTEN || true` を再撮影前に実行し、競合時は `spec-update-summary.md` に分岐結果を記録したうえで `UT-IMP-PHASE12-SCREENSHOT-PORT-CONFLICT-GUARD-001` を未タスク化する
- **発見日**: 2026-03-04
- **関連タスク**: 02-TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] 別workflow証跡参照のまま `validate-phase11-screenshot-coverage` を実行

- **状況**: `manual-test-result.md` に別workflowの証跡パスのみを記載した状態で validator を実行し、対象workflow配下の `outputs/phase-11/screenshots` が空のまま失敗する
- **問題**: 見かけ上は証跡リンクが存在しても、機械検証では `covered=0` になり Phase 12 完了判定が崩れる
- **原因**: UI証跡を「参照文字列」と「対象workflow配下の実体」で分離管理していない
- **教訓**: coverage validator は対象workflow配下の実体を検証するため、証跡移送/再取得と証跡記法の同期が必須
- **対策**: `outputs/phase-11/screenshots` を対象workflow配下へ正規配置し、視覚TCは `screenshots/*.png`、非視覚TCは `NON_VISUAL:` 記法へ統一してから validator を再実行する
- **発見日**: 2026-03-04
- **関連タスク**: UT-IMP-PHASE12-SCREENSHOT-COMMAND-REGISTRATION-GUARD-001

### [Phase12] SubAgent分担が `spec-update-summary` のみに残る

- **状況**: 分担情報を `spec-update-summary.md` にのみ記録し、`task-workflow.md` の完了節へ転記しない
- **問題**: 完了台帳から責務境界を追跡できず、再監査で「誰が何を同期したか」を再調査する必要が出る
- **原因**: Step 2の成果物更新で台帳側の転記を必須条件にしていない
- **教訓**: 分担情報は「成果物」と「完了台帳」の両方へ残す
- **対策**: Phase 12チェックリストに「task-workflow へのSubAgent分担表転記」を必須項目として追加する
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C

### [Phase12] `--target-file` を「対象のみ出力」と誤解

- **状況**: `audit-unassigned-tasks --target-file` の出力に baseline が含まれ、対象ファイルが fail に見える
- **問題**: current=0 でも過剰修正が発生し、Phase 12完了が遅延する
- **原因**: `--target-file` の仕様（分類モード）を表示フィルタと混同した
- **教訓**: 判定は `currentViolations.total` を正本とし、baseline は別管理する
- **対策**: 監査テンプレートへ `scope.currentFiles` / `currentViolations.total` / `baselineViolations.total` の3項目を固定で記録する
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] 未タスクの存在確認止まり（10見出し未検証）

- **状況**: `verify-unassigned-links` だけを実行して未タスク検証を完了扱いにする
- **問題**: ファイルは存在していても、必須見出し不足や `## メタ情報` 重複を見逃して監査差し戻しが発生する
- **原因**: 配置検証とフォーマット検証を同一チェックとして扱っていた
- **教訓**: 未タスク検証は「存在（links）」と「形式（target監査 + 見出し検証）」の二段で実施する
- **対策**: `audit-unassigned-tasks --target-file` と 10見出しチェックをセット化し、`current=0` + 見出し10/10 + `メタ情報=1` を完了条件にする
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9I, UT-9I-001, UT-9I-002

### [Phase12] `validate-phase-output` の `--phase` 誤用

- **状況**: `verify-all-specs` と同様に `--phase` 指定を試して検証が失敗する
- **問題**: Phase 12再確認でコマンド再実行が増え、証跡同期が遅れる
- **原因**: `validate-phase-output.js` が workflow-dir 位置引数のみ受け付ける仕様を明示していなかった
- **教訓**: Phase検証コマンドは「仕様整合（verify-all-specs）」と「出力構造（validate-phase-output）」で引数形式を明示的に分離する
- **対策**: 実行テンプレートを `validate-phase-output.js docs/30-workflows/<workflow-dir>` に統一する
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] グローバルCLI前提で `not found` / `MODULE_NOT_FOUND` を誘発

- **状況**: `verify-all-specs` / `validate-phase-output` を直接実行し、環境によってコマンド未導入または誤パス解決で失敗する
- **問題**: 再確認の初動で停止し、証跡時刻や台帳同期の再確認が後倒しになる
- **原因**: 検証コマンドの実体探索を省略し、エイリアスの存在を前提にしている
- **教訓**: Phase 12 は「エイリアス」ではなく「スクリプト実体」を正本として実行する
- **対策**: `which <cmd> || true` と `rg --files .claude/skills/task-specification-creator/scripts` で実体確認後、`node .claude/skills/task-specification-creator/scripts/<script>.js` 形式へ統一する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] 監査結果の棚卸し止まり（次アクション未定義）

- **状況**: 監査結果を表やレポートに整理したが、誰が・何を・どの順序で実行するかが未定義のまま完了扱いにした
- **問題**: 次回の着手時に再分析が必要となり、監査結果が実行計画へつながらない
- **原因**: `task-00` 配下の実行導線（優先度/Wave/SubAgent分担）を作成していない
- **教訓**: 監査完了と同時に「次アクション専用ドキュメント」を必ず1枚追加する
- **対策**: Phase 12 完了条件に「監査→実行ブリッジ文書の作成」を追加し、`outputs/phase-12/spec-update-summary.md` から参照する
- **発見日**: 2026-02-25
- **関連タスク**: TASK-013 再監査

### [Phase12] 成果物実体とphase-12実行記録の乖離放置

- **状況**: `outputs/phase-12` のファイルは作成済みだが、`phase-12-documentation.md` の「未実施」行が更新されないまま完了扱いにした
- **問題**: 監査時に「実施済みなのに未実施表示」という矛盾が発生し、完了判定の信頼性が低下する
- **原因**: 成果物実体の確認と、仕様書本体の実行記録更新を別工程で扱っていた
- **教訓**: Phase 12完了判定は「成果物実体 + 実行記録同期」の2条件を同時に満たす必要がある
- **対策**: Task 1〜5突合レポートを必須化し、`phase-12-documentation.md` のチェック欄更新を完了条件へ昇格
- **発見日**: 2026-02-25
- **関連タスク**: UT-UI-THEME-DYNAMIC-SWITCH-001

### [Phase12] Step 1-A 完了タスク記録の欠落

- **状況**: `implementation-guide.md` や `documentation-changelog.md` は作成済みだが、`spec-update-workflow.md` / `phase-11-12-guide.md` に完了タスク記録が追加されていない
- **問題**: 実行手順書上では未完了に見え、Phase 12 の完了判定根拠が分断される
- **原因**: 成果物生成と手順書更新を別担当・別ターンに分離し、Step 1-A の最終チェックが未実施
- **教訓**: Phase 12 Task 2 は「仕様更新」だけでなく「手順書への完了記録」までを同一タスクとして扱う
- **対策**: Step 1-A の完了条件に「完了タスク + 関連ドキュメント + 更新履歴」の3点追記を固定し、`quick_validate.js` 実行前に確認する
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001

### [Phase12] テンプレートに旧環境絶対パスを残す

- **状況**: `quick_validate` などのコマンド例が特定端末の絶対パスで記載され、他環境で実行不能になる
- **問題**: 同じテンプレートでも実行者ごとに手順が分岐し、検証結果の再現性が崩れる
- **原因**: テンプレート更新時に「正規経路（repo相対）」への置換チェックを行っていない
- **教訓**: テンプレートは「誰がどの環境でも実行可能」な相対パス前提で管理する
- **対策**: assets更新時に「絶対パス禁止」と「成果物名最新化」をチェックリストへ追加する
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001

### [Phase12] 仕様書更新の単独進行による同期漏れ

- **状況**: `interfaces` 更新後に `security`/`task-workflow`/`lessons` の反映が遅れ、仕様書間で契約状態がずれる
- **問題**: 実装は完了していても監査時に仕様不整合として差し戻しが発生する
- **原因**: 仕様書ごとの責務分担と同時更新ルールが未定義
- **教訓**: 横断仕様更新は単一担当で逐次進行せず、SubAgent分担で同一ターン同期する
- **対策**: `assets/phase12-spec-sync-subagent-template.md` で担当/完了条件/検証コマンドを固定し、4仕様書を一括更新する
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] 未タスク指示書メタ情報の二重定義
### [Phase12] api-ipc仕様を同期対象から除外

- **状況**: interfaces と security を更新して完了扱いにしたが、`api-ipc-agent.md` のチャネル契約更新を省略する
- **問題**: 実装済みチャネルの request/response/Preload対応が仕様書に残らず、後続実装が誤った契約を参照する
- **原因**: SubAgent分担が4仕様書前提で固定され、api-ipc が責務表から抜けていた
- **教訓**: IPC系タスクでは `api-ipc` を必須仕様書に含めた5仕様書同期が必要
- **対策**: `phase12-spec-sync-subagent-template.md` の分担を `A:interfaces / B:api-ipc / C:security / D:task-workflow / E:lessons` に固定し、完了チェックで5仕様書同時更新を必須化する
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J

### [Phase12] IPC契約ドキュメントを概要のみで確定

- **状況**: 未タスク指示書で `## メタ情報` を2回定義し、YAMLと表を別セクションに分離した
- **問題**: フォーマット監査でノイズが増え、修正対象の切り分けが遅れる
- **原因**: YAML追加時に既存メタ情報テーブルとの統合ルールが明文化されていなかった
- **教訓**: メタ情報は「1セクション原則」を守り、YAMLと表を同一セクションで管理する
- **対策**: `unassigned-task-guidelines.md` に重複禁止ルールを追加し、`rg -n "^## メタ情報"` を定期監査に組み込む
- **発見日**: 2026-02-26
- **関連タスク**: TASK-9A-skill-editor

### [Phase12] IPCハンドラ実装のみで登録配線を未確認

- **状況**: `skillAnalyticsHandlers.ts` のような専用ハンドラを追加したが、`ipc/index.ts` の `register*Handlers()` 呼び出し追加を見落とす
- **問題**: テストが部分的にPASSでも、実ランタイムでチャネルが未登録となり機能が使用できない
- **原因**: 実装完了の判定を「ハンドラファイル作成」で止め、起動経路まで検証していない
- **教訓**: IPC機能の完了条件は「実装 + 登録 + Preload公開」の3点セットで判定する
- **対策**: Phase 12チェックリストに「`ipc/index.ts` の登録配線確認」を追加し、回帰テストに登録確認ケースを含める
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J

### [Phase12] timeout待機APIへの停止副作用混在（TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001）

- **状況**: timeout ハンドラ内で `stop()` を直接呼び、待機失敗処理と停止処理を1つの責務にしてしまう
- **問題**: 終了順序が競合し、ワーカー終了やテストクリーンアップで不安定な失敗が再発する
- **原因**: wait API（結果を返す責務）と stop API（ライフサイクル責務）の境界が未定義
- **教訓**: timeout系APIは副作用を持たせず、停止は呼び出し側の明示責務として分離する
- **対策**:
  1. timeout ハンドラから stop/close を排除する
  2. stop API を idempotent（未起動/停止済みガード）に統一する
  3. timeout テストに `await stop()` を必須化する
  4. `security` / `task-workflow` / `lessons` へ同一内容を同時同期する
- **発見日**: 2026-02-28
- **関連タスク**: TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001

### [Phase12] task-workflow のみ更新で lessons-learned 同期漏れ（TASK-UI-05）

- **状況**: 完了台帳（`task-workflow.md`）へ実装要点と未タスクを記録したが、`lessons-learned.md` への苦戦箇所転記を後回しにした
- **問題**: 再利用時に「何を実装したか」は追えるが「なぜ苦戦したか・次にどう避けるか」が欠落し、同じ調査を繰り返す
- **原因**: Phase 12 Step 2 を「仕様同期」と「教訓同期」に分離せず、完了条件を片側更新で満たしたと誤認した
- **教訓**: 仕様更新は `task-workflow` と `lessons-learned` を同一ターンで更新しない限り完了扱いにしない
- **対策**:
  1. `task-workflow.md` 更新時点で `lessons-learned.md` の追記見出しを同時作成する
  2. 検証証跡（verify/validate/links/audit）を2ファイルへ同一値で転記する
  3. `SKILL.md` 変更履歴に「台帳 + 教訓 同時同期」を明示し、レビュー時のチェック項目に固定する
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] UIタスクに5仕様書テンプレートを誤適用

- **状況**: UI中心の実装タスクに対して `interfaces/api-ipc/security/task/lessons` の5仕様書テンプレートのみで同期を進める
- **問題**: `ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` の更新漏れが発生し、UI仕様の正本が古いまま残る
- **原因**: タスク種別（UI機能実装）に応じた仕様書プロファイルの切替ルールがテンプレートに明示されていなかった
- **教訓**: Phase 12テンプレートはタスク種別ごとにプロファイル選択（標準5仕様書 / UI6仕様書）を先に確定する
- **対策**:
  1. `phase12-system-spec-retrospective-template.md` に UI機能6仕様書プロファイルを追加する
  2. `phase12-spec-sync-subagent-template.md` に UI向けSubAgent分担表を追加する
  3. 完了チェックへ「プロファイル選択明記」を追加する
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] UI基本6仕様書だけ更新して domain UI spec を未同期（TASK-UI-02）

- **状況**: `ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` / `task-workflow` / `lessons` は更新したが、`ui-ux-navigation.md` のようなドメイン固有 UI 正本が古いまま残る
- **問題**: UI index/detail/state は新しいのに、機能固有の正本が stale となり、再利用時に情報が分散する
- **原因**: UI6仕様書プロファイルを「基本セット」ではなく「全量セット」と誤解し、domain add-on spec を追加判定していなかった
- **教訓**: UI Phase 12 は `UI6 + domain-ui-spec` の可変プロファイルで扱い、domain spec がある限り 1仕様書=1SubAgent を追加する
- **対策**:
  1. 実装開始時に `rg -n "TASK-UI-02|<feature>|<domain>" .claude/skills/aiworkflow-requirements/references/ui-ux-*.md` で domain UI spec の有無を先に確認する
  2. 見つかった domain spec（例: `ui-ux-navigation.md`）を `SubAgent-G+` として分担表へ追加する
  3. `task-workflow.md` / `lessons-learned.md` / `<domain-ui-spec>.md` の3点に実装内容・苦戦箇所・再利用手順を同一ターンで転記する
  4. 完了チェックへ「UIドメイン固有正本の同時更新」を追加し、6仕様書だけで完了扱いにしない
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-02-GLOBAL-NAV-CORE

### [Skill] 全リソース一括読み込み

- **状況**: スキル実行開始時に全ファイルを読み込んだ
- **問題**: コンテキストウィンドウを圧迫し、精度低下
- **原因**: Progressive Disclosure 原則の未適用
- **教訓**: 必要な時に必要なリソースのみ読み込む
- **発見日**: 2026-01-10

### [Skill] LLMでのメトリクス計算

- **状況**: 成功率や実行回数をLLMに計算させた
- **問題**: 計算ミスが発生、信頼性低下
- **原因**: Script First 原則の未適用
- **教訓**: 決定論的処理は必ずスクリプトで実行
- **発見日**: 2026-01-08

### [Build] スクリプトでのデータ形式前提の誤り

- **状況**: generate-documentation-changelog.jsがartifacts.jsonを解析してエラー発生
- **問題**: `TypeError: The "path" argument must be of type string. Received undefined`
- **原因**: スクリプトは`{path, description}`オブジェクト形式を想定したが、実際は文字列配列形式だった
- **教訓**: スクリプト作成時は実際のデータ形式を確認し、複数形式に対応するか明確に文書化する
- **対策**: `typeof artifact === "string" ? artifact : artifact.path` で両形式に対応
- **発見日**: 2026-01-22
- **関連タスク**: skill-import-store-persistence (SKILL-STORE-001)

### [Phase12] 「検証タスク」でのPhase 12 Step 1省略

- **状況**: SHARED-TYPE-EXPORT-03（検証タスク）でPhase 12 Step 1を「検証タスクなので更新不要」と判断し省略
- **問題**: spec-update-record.mdに「更新不要」と記載したが、Step 1は必須要件だった
- **原因**: Step 1（タスク完了記録：必須）とStep 2（インターフェース仕様更新：条件付き）の区別を誤認
- **教訓**: Phase 12 Step 1（完了タスクセクション追加、実装ガイドリンク追加、変更履歴追記）は**検証タスクでも必須**
- **対策**:
  - task-specification-creator SKILL.mdに「【検証タスクでも必須】」警告を追加
  - validate-phase12-step1.js検証スクリプトで自動チェック
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03

### [Phase 12] 正規表現パターンのPrettier干渉

- **状況**: Phase 12 Task 1で実装ガイド・IPCドキュメント作成時、TypeScript型表記を含むMarkdownファイルを生成
- **問題**: PostToolUseフック（auto-format.sh）のPrettierが、Markdownコードブロック内のTypeScript型表記（`readonly ["task-spec", "skill-spec", "mode"]`）を `readonly[("task-spec", "skill-spec", "mode")]` のように変形
- **原因**: PrettierのMarkdownフォーマッターがコードブロック内のTypeScript構文を解釈し、独自のフォーマットルールを適用
- **教訓**: ドキュメント生成タスクでは、PostToolUseフックの自動フォーマット後にコードブロック内の表記を検証する後処理ステップが必要。特に `as const` アサーション付きの型表記は変形されやすい
- **発見日**: 2026-02-12
- **対策**: バックグラウンドエージェント内でWrite後にReadで検証し、変形があればEditで修正するステップを組み込む

### [Build] ES Module互換性の確認漏れ

- **状況**: 新規スクリプト（validate-phase12-step1.js）作成時にCommonJS構文（require）を使用
- **問題**: プロジェクトがES Module（"type": "module"）設定のため実行時エラー
- **原因**: package.jsonの"type"フィールドを確認せずスクリプト作成
- **教訓**: 新規スクリプト作成時は必ずプロジェクトのモジュール形式を確認し、ES Module形式（import/export）を使用
- **対策**: スクリプト作成前に `package.json` の `"type"` フィールドをチェック
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03

### [SDK] カスタム declare module と SDK 実型の共存（TASK-9B-I）

- **状況**: SDK 未インストール時にカスタム `declare module` を作成し、SDK インストール後もファイルが残留
- **問題**: TypeScript は `node_modules` の実型を優先し、カスタム `.d.ts` は無視されるが、仕様書にカスタム型の値が残って型不整合が発生
- **原因**: SDK インストール前後で型定義ファイルの優先順位が変わることの認識不足
- **教訓**: SDK インストール後はカスタム `.d.ts` を削除する。TypeScript のモジュール解決優先順位（`node_modules` > カスタム `.d.ts`）を文書化しておく
- **対策**: SDK バージョンアップ時にカスタム型定義ファイルの棚卸しを実施
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-I-SDK-FORMAL-INTEGRATION, UT-9B-I-001

### [Phase12] 未タスク配置ディレクトリの混同（TASK-9B-I）

- **状況**: 未タスク (UT-9B-I-001) の指示書を親タスクの `tasks/` ディレクトリに誤配置
- **問題**: `docs/30-workflows/unassigned-task/` ではなく `docs/30-workflows/skill-import-agent-system/tasks/` に配置してしまった
- **原因**: 未タスク指示書の配置先ルールの確認不足。親タスクディレクトリと未タスクディレクトリの混同
- **教訓**: 未タスクは必ず `docs/30-workflows/unassigned-task/` に配置する。配置後に `ls` で物理ファイルの存在を検証する
- **対策**: 未タスク作成時に配置ディレクトリを明示的に確認するチェックリスト項目を追加
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-I-SDK-FORMAL-INTEGRATION

### [Phase12] 未タスクの「配置・命名・9セクション」同時是正（TASK-9F）

- **状況**: 未タスク6件を検出したが、`docs/30-workflows/completed-tasks/skill-share/unassigned-task/` に簡易フォーマットで配置していた
- **問題**: `docs/30-workflows/unassigned-task/` 正本運用と不一致となり、`audit-unassigned-tasks` の `current` 判定と台帳整合が崩れた
- **原因**:
  - 親ワークフロー配下のローカル運用を優先し、共通ガイドライン（配置先/命名/9セクション）を後追い確認した
  - `unassigned-task-report.md` と `task-workflow.md` の参照パス同期を同時に実施していなかった
- **教訓**:
  - 未タスクは「作成」ではなく「配置先 + 命名 + フォーマット + 台帳同期」を1作業単位で完了させる
  - `task-specification-creator` のテンプレートに準拠し、`docs/30-workflows/unassigned-task/` 以外への配置を禁止する
- **対策**:
  1. 未タスク検出後に `assets/unassigned-task-template.md` で9セクション化
  2. `docs/30-workflows/unassigned-task/task-*.md` へ保存
  3. `task-workflow.md` 残課題テーブルと `unassigned-task-report.md` を同一ターンで同期
  4. `audit-unassigned-tasks.js --diff-from HEAD` で `currentViolations=0` を確認
- **発見日**: 2026-02-27
- **関連タスク**: TASK-9F, UT-9F-SETTER-INJECTION-001, UT-9F-EXPORT-PATH-TRAVERSAL-001

### [Phase12] 仕様書別SubAgent同期 + spec-update-summary 固定化（TASK-9F追補）

- **状況**: 実装内容と苦戦箇所は `task-workflow.md` / `lessons-learned.md` に記録済みだが、仕様書別責務と検証証跡の再利用性が不足していた
- **問題**: 次回タスクで「どの仕様書を誰が更新するか」「どの検証値をどこへ転記するか」が毎回手作業判断になり、再監査コストが増える
- **原因**:
  - Phase 12 Step 2 の成果物に `spec-update-summary.md` を標準化していなかった
  - SubAgent分担を「A:台帳/B:ドメイン/C:教訓/D:検証」の抽象表記で止め、実ファイル責務へ落とし込んでいなかった
- **教訓**:
  - 仕様書更新は `interfaces` / `api-ipc` / `security` / `task-workflow` / `lessons` の5責務に固定すると漏れを抑制できる
  - 検証値（13/13, 28項目, 95/95, current=0）は `spec-update-summary.md` を正本にし、台帳と教訓へ転記する
- **対策**:
  1. `assets/phase12-system-spec-retrospective-template.md` で仕様書別SubAgent表を必須化
  2. `outputs/phase-12/spec-update-summary.md` を成果物必須に追加
  3. `task-workflow.md` に SubAgent分担 + 検証結果 + 成果物マトリクスを追記
  4. `lessons-learned.md` に同一検証値と再利用5ステップを同期
- **発見日**: 2026-02-27
- **関連タスク**: TASK-9F

### [IPC] IPC契約ドリフト（Handler/Preload引数不整合）（UT-FIX-SKILL-REMOVE-INTERFACE-001）

- **状況**: ハンドラ側がオブジェクト形式（`{ skillId: string }`）を期待し、Preload側が文字列（`skillName`）を渡すインターフェース不整合
- **問題**: ランタイムで `args?.skillId` が `undefined` となり、バリデーションエラーが発生。コンパイル時はPreloadのモック化で検出されない
- **原因**:
  - ハンドラ設計時とPreload設計時で異なる想定（オブジェクト形式 vs 単一引数）を前提とした
  - 引数の命名も乖離（`skillId` / `skillIds` / `skillName`）
  - TypeScript型チェックがPreloadとMain Processの境界を超えないため、コンパイル時に検出されない
- **教訓**:
  - IPC チャンネルの設計時に「引数の正本」をPreload側に定義し、ハンドラはPreloadに合わせる
  - 引数名はレイヤー間で統一する（`skillName` ならハンドラも `skillName`）
  - ハンドラ修正時は必ず [IPC契約チェックリスト](../../aiworkflow-requirements/references/ipc-contract-checklist.md) を実行
- **対策**: 3箇所同時更新チェックリスト（ハンドラ・Preload API・テスト）をIPC修正の必須手順とする
- **発見日**: 2026-02-20
- **関連タスク**: UT-FIX-SKILL-REMOVE-INTERFACE-001, UT-FIX-SKILL-IMPORT-INTERFACE-001
- **関連Pitfall**: P23, P32, P42, P44

### [IPC] 正式契約切替時の後方互換欠落（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: 新契約（`skillName`）へ移行する際、旧契約（`skillId`）を即時削除して既存呼び出しを破壊
- **問題**: 既存テストや既存呼び出し経路がランタイムで失敗し、移行期間に障害が顕在化する
- **原因**:
  - 契約移行を単一フェーズで完了できる前提を置いていた
  - 境界Adapterを用意せず、ドメインAPIまで同時変更した
  - 新契約テストのみで旧契約回帰を省略した
- **教訓**:
  - 契約変更は「正式契約 + 互換契約 + 廃止条件」を1セットで定義する
  - 互換期間は境界Adapterで吸収し、ドメインAPIの破壊的変更を遅らせる
  - 新旧契約の両回帰テストを完了条件に含める
- **対策**: IPC契約変更テンプレートに「後方互換チェック」を必須項目として追加
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [IPC/Renderer] Renderer層での識別子混同（id/name）（UT-FIX-SKILL-IMPORT-ID-MISMATCH-001）

- **状況**: SkillImportDialog の `handleImport` が `selectedIds`（Set内はskill.id＝SHA-256ハッシュ）をそのまま `onImport` に渡していた。IPC ハンドラは `skill.name`（人間可読名）を期待しており、`getSkillByName(hash)` が常に null を返すため、スキルインポートが 100% 失敗
- **原因**:
  - `skill.id` と `skill.name` が共に `string` 型であるため、型レベルでの検出が不可能
  - UI上は id をハッシュ表示しないため、開発者が id/name の違いを認識しにくい
  - IPC ハンドラ側（IMPORT-INTERFACE-001）の修正でハンドラ入口は正常化したが、Renderer 側の送信値が未修正のまま残った
- **影響**: スキルインポート機能が完全に動作しない（成功率 0%）
- **対策**: Renderer → IPC 境界に明示的な変換処理を1箇所だけ配置し、変数名を契約準拠（`skillNames`）に統一
- **再発防止**: 同じ `string` 型の識別子が2種類以上あるコンポーネントでは、変数名で明示的に区別し、テストで「期待値」と「否定条件」を同時に検証
- **発見日**: 2026-02-22
- **関連タスク**: UT-FIX-SKILL-IMPORT-ID-MISMATCH-001

### [Phase12] 未タスクraw検出の誤読（TASK-FIX-11-1）

- **状況**: raw検出 51件をそのまま未タスク件数と見なしかけた
- **問題**: 仕様書本文の説明用 TODO まで未対応課題として誤認し、バックログを汚染する
- **原因**: `detect-unassigned-tasks.js` の出力が「候補」である前提を明記せずに解釈
- **教訓**: 未タスクは「検出候補」と「実装上の確定課題」を分離して扱う
- **対策**: `unassigned-task-detection.md` に raw件数と精査後件数を分離して記録し、配置先 `docs/30-workflows/unassigned-task/` の要否を明示する
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [Testing] dangerouslyIgnoreUnhandledErrors 常時有効化（TASK-FIX-10-1）

- **状況**: Vitestで `dangerouslyIgnoreUnhandledErrors: true` を恒常運用し、未処理Promise拒否を無視する
- **問題**: 本来失敗すべき非同期エラーがテストで通過し、回帰検知が遅れる
- **原因**: 一時的なテスト安定化設定を恒久設定として残してしまう運用
- **教訓**: 未処理Promise拒否は設定で抑止せず、テスト/実装側で根本修正する
- **対策**: 設定禁止ルールを仕様書に明記し、設定検証テストで再導入を防ぐ
- **発見日**: 2026-02-19
- **関連タスク**: TASK-FIX-10-1-VITEST-ERROR-HANDLING

### [Test] モジュールモック下でのタイマーテスト失敗

- **状況**: `vi.mock("../agent-client")` でモジュール全体をモック化した状態で、`vi.useFakeTimers()` + `vi.advanceTimersByTimeAsync(30000)` によるタイムアウトテストを実行
- **症状**: タイマーを進めてもタイムアウトが発生しない。テストがハングまたはタイムアウト条件が不成立
- **原因**: `vi.mock()` はモジュール内の全エクスポートをモック関数に置換するため、元の実装内部の `setTimeout` + `AbortController` ロジックが消失する
- **解決策**: モジュール内部のタイマーを再現するのではなく、`mockRejectedValueOnce(new Error("Request timeout"))` で直接エラーを注入。タイマーテストが必要な場合はモック関数の `mockImplementation` 内に `setTimeout` を含める
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [Phase12] Phase 10/11サブエージェント出力の非永続化（UT-FIX-SKILL-VALIDATION-CONSISTENCY-001）

- **状況**: Task subagentでPhase 10最終レビューとPhase 11手動テストを実行したが、出力がファイルとして保存されなかった
- **問題**: Phase 12のdocumentation-changelogでレビュー結果を参照できず、「サブエージェント実行結果確認」としか記載できない。レビュー判定（PASS/MINOR/MAJOR）の根拠が追跡不能
- **原因**: Task subagentの出力はメッセージとして返されるが、ファイル書き込み指示が不足していた。サブエージェントに「結果をファイルに出力する」明示的な指示がなかった
- **教訓**: サブエージェントにPhase実行を委譲する際は、出力ファイルパス（`outputs/phase-N/` 配下）を明示的に指定する。特にPhase 10/11はレビュー判定を含むため、永続化が必須
- **対策**: Task toolのpromptに `結果を outputs/phase-10/review-result.md に書き出してください` のようなファイル出力指示を含める
- **発見日**: 2026-02-24
- **関連タスク**: UT-FIX-SKILL-VALIDATION-CONSISTENCY-001

### [Phase 12] 仕様書修正タスクでのPhaseテンプレート誤適用

- **状況**: 仕様書修正のみタスクにPhase 1-13テンプレートをそのまま適用しようとした
- **問題**: Phase 4（テスト作成）で「何のテストを書くのか」、Phase 7（カバレッジ確認）で「何のカバレッジを測るのか」が不明確になり、作業が停滞
- **根本原因**: Phase 1-13テンプレートはコード実装タスクを前提としており、仕様書修正タスク向けの代替アプローチが定義されていなかった
- **解決策**: 仕様書修正タスク向けの代替Phase定義を Phase 1 で事前策定（Phase 4=検証基準設計、Phase 6-7=grep検証等）
- **影響**: 初回の仕様書修正タスクでは、Phaseの再定義に追加工数がかかった
- **再発防止**: 仕様書修正タスクの仕様書テンプレートに「代替Phase対応表」セクションを追加
- **発見日**: 2026-02-24

### [CI/ビルド] TypeScript設定ファイルの完全AST解析の試行

- **状況**: vitest.config.ts のalias設定を抽出するために、TypeScript ASTパーサー（ts-morph等）の使用を検討
- **問題**: 外部依存の追加、ビルド時間の増加、メンテナンスコストが CIガードスクリプトの目的（設定値の文字列抽出）に対して過大
- **原因**: 完全な型安全パースを目指しすぎ、実用的な正規表現アプローチを最初から除外した
- **教訓**: CIガードスクリプトは「設定値の文字列比較」が目的であり、完全なAST解析は不要。正規表現の制約（ダブルクォート前提等）をテストで明文化すれば十分。YAGNI原則を適用する
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001

### [Phase12] 実行可否判定の三点突合（チェックリスト/成果物/artifacts）

- **状況**: `outputs/phase-12` の成果物が揃っていても、`phase-12-documentation.md` のチェックや `artifacts.json` ステータスが未同期のまま残る
- **問題**: 「見た目は完了」に見えるが、再監査時に未完了判定へ戻る
- **原因**: 完了判定をファイル存在だけで行い、台帳ステータスと手順書チェックの同期を省略した
- **解決策**:
  - `verify-all-specs` と `validate-phase-output` で構造整合を固定
  - 必須5成果物の実体確認
  - `artifacts.json` の `phases.12.status` 同期確認
  - `phase-12-documentation.md` チェックリスト同期確認
- **結果**: Phase 12 完了判定の再現性が上がり、再監査差し戻しを削減
- **適用条件**: Phase 12 を含む全タスク
- **発見日**: 2026-02-28
- **関連タスク**: TASK-REFACTOR-SHARED-SOURCE-STRUCTURE-001

### [Phase12] 仕様書単位SubAgent + N/A判定ログ固定（TASK-REFACTOR-SHARED-SOURCE-STRUCTURE-001）

- **状況**: 仕様書別に SubAgent を分割しても、更新不要な仕様書（interfaces/api-ipc/security）の扱いがメモ依存になり、監査で漏れと判別しづらい
- **問題**: 「更新なし」と「更新漏れ」の区別が曖昧になり、再確認のたびに説明コストが増える
- **原因**: Phase 12 テンプレートに仕様書ごとの適用判定（更新/N/A）を記録する欄がなかった
- **解決策**:
  - `phase12-system-spec-retrospective-template.md` に `仕様書適用判定ログ` を追加
  - 各仕様書を `更新 / N/A` で必ず判定し、N/A は理由と代替証跡を記録
  - SubAgent 分担表と同一ターンで転記し、責務分離と説明責任を両立
- **結果**: 仕様書別SubAgent運用でも、非対象範囲の説明が機械的に再現できる
- **適用条件**: 複数仕様書へ横断反映する Phase 12 タスク全般
- **発見日**: 2026-02-28
- **関連タスク**: TASK-REFACTOR-SHARED-SOURCE-STRUCTURE-001

### [Phase12] UI機能実装の未タスク6件分解 + 二段監査固定（TASK-UI-05）

- **状況**: UI実装（SkillCenterView）を完了したが、型統一・詳細パネル分割・モバイル操作などの残課題が複数同時に見つかった
- **アプローチ**:
  - 検出課題を `UT-UI-05-001`〜`UT-UI-05-006` として1課題1指示書へ分解
  - `audit-unassigned-tasks --target-file` で各未タスクのフォーマットを個別監査
  - `verify-unassigned-links` + `audit --diff-from HEAD` でリンク整合と差分違反ゼロを確定
  - `task-workflow.md` と `lessons-learned.md` に同一ターンで苦戦箇所を同期
- **結果**: 未タスクの「存在・形式・参照」が同時に保証され、Phase 12完了判定の再現性が上がった
- **適用条件**: UI機能の完了時に未タスクが3件以上出る Phase 12 タスク
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] UI機能6仕様書SubAgent同期テンプレート

- **状況**: UI機能実装では `ui-ux` と `arch-ui/state` が正本だが、タスクごとに同期対象の切り方が揺れやすい
- **アプローチ**:
  - `phase12-system-spec-retrospective-template.md` に UI機能6仕様書プロファイルを追加
  - `phase12-spec-sync-subagent-template.md` に UI向け SubAgent-A〜E の分担表を追加
  - 完了チェックへ「プロファイル選択（標準5 / UI6）」を必須化
- **結果**: UI機能タスクで仕様更新漏れが減り、仕様書単位の責務分離を再利用しやすくなった
- **適用条件**: Renderer中心で IPC追加が主目的でない UI機能実装の Phase 12
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] 検証スクリプト実体探索先行パターン（TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001）

- **状況**: Phase 12再確認で `verify/validate/links/audit` を連続実行する際、スクリプト所在の記憶依存で誤パス実行が起きやすい
- **アプローチ**:
  - 検証開始前に `rg --files .claude/skills | rg 'verify-all-specs|validate-phase-output|verify-unassigned-links|audit-unassigned-tasks'` を必須実行
  - 実体解決後に `verify -> validate -> links -> audit` を固定順序で実行
  - 実体探索結果と検証結果を同一ターンで `spec-update-summary.md` へ記録
- **結果**: スクリプト所在誤認による再確認の手戻りを抑制し、証跡ドリフトを防止
- **適用条件**: Phase 12 の再監査・再実行タスク全般
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] CLIエイリアス非依存で検証経路を固定するパターン（TASK-UI-00-FOUNDATION-REFLECTION-AUDIT）

- **状況**: `verify-all-specs` / `validate-phase-output` をグローバルCLI前提で実行し、環境差で `not found` や `MODULE_NOT_FOUND` が発生しやすい
- **アプローチ**:
  - 再監査開始時に `which verify-all-specs || true` でエイリアス有無を確認
  - `rg --files .claude/skills/task-specification-creator/scripts` で実体を特定し、`node .claude/skills/task-specification-creator/scripts/<script>.js` へ固定
  - 実行後に採用した最終コマンドを `spec-update-summary.md` と `documentation-changelog.md` へ転記して再現手順を固定
- **結果**: 端末差異に依存しない検証フローとなり、Phase 12 再確認時の手戻りを抑制できる
- **適用条件**: 複数ワークツリー/端末で同一検証コマンドを再利用する Phase 12 タスク
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] Vitest再確認の非watch固定パターン（TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001）

- **状況**: Phase 12 でテスト証跡を再取得する際、`pnpm test` の watch 残留で完了判定が遅延しやすい
- **アプローチ**:
  - テスト再確認は `pnpm --filter @repo/desktop exec vitest run <target>` を標準コマンドに固定
  - ルート実行ではなく対象パッケージ文脈で実行して設定解決を安定化
  - 実行コマンドを `implementation-guide.md` / `spec-update-summary.md` に明示して再現性を固定
- **結果**: 非watchで決定論的に終了し、Phase 12 の証跡取得と台帳同期が安定
- **適用条件**: モノレポで UI/Renderer テストを Phase 12 で再実行するタスク
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] 未タスク監査カウンタ再同期パターン（TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001）

- **状況**: Phase 12 再確認後に未タスク件数が更新されたが、`task-workflow` や `outputs/phase-12` に旧値（links/baseline）が残りやすい
- **アプローチ**:
  - 仕様更新の最終ステップで `verify-unassigned-links` と `audit-unassigned-tasks --json --diff-from HEAD` を再実行
  - `existing/missing/current/baseline` を確定値として `task-workflow.md` / `spec-update-summary.md` / `unassigned-task-detection.md` へ同一ターン転記
  - 変更履歴（`task-workflow` / `documentation-changelog`）にも同値を追記して記録値を一本化
- **結果**: 未タスク監査の数値ドリフトを抑止し、再監査時の判定ブレを低減
- **適用条件**: Phase 12 で未タスクの追加・完了移管・リンク更新を行ったタスク
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] backlog 継続前に現物確認して completed/unassigned を再判定するパターン（TASK-UI-03）

- **状況**: Phase 10/11 で起票した未タスクをそのまま継続扱いにすると、current branch では既に解消済みの項目まで open backlog として残りやすい
- **アプローチ**:
  - `rg -n "<symptom>" <codebase>` で現物の残存有無を先に確認する
  - 解消済みなら `docs/30-workflows/completed-tasks/unassigned-task/` 側へ正規化し、`task-workflow.md` / `unassigned-task-detection.md` / `spec-update-summary.md` を同一ターンで更新する
  - 未解消なら task-spec フォーマットで `docs/30-workflows/unassigned-task/` に formalize し、`audit --target-file` まで閉じる
- **結果**: backlog と実コードのズレを抑止し、Phase 12 判定の信頼性を保てる
- **適用条件**: current workflow 再監査、MINOR 指摘の継続判定、既存未タスクの棚卸し時
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT

### [Phase12] UI所見を component scope と token scope に切り分けて formalize するパターン（TASK-UI-03）

- **状況**: screenshot で light/dark の視認性差分を見つけたとき、個別コンポーネント修正と design token 改善が混線しやすい
- **アプローチ**:
  - dedicated harness で component state を固定し、layout/state の不具合有無を先に確認する
  - token 由来と判断した所見は `ui-ux-design-system.md` と `task-workflow.md` の両方へ未タスク化し、component 側にはハードコードを追加しない
  - `manual-test-result.md` / `discovered-issues.md` / `unassigned-task-detection.md` に同じ task ID を転記する
- **結果**: UIレビュー所見が観察止まりにならず、正しい責務境界で改善計画へ接続できる
- **適用条件**: Phase 11 screenshot 再監査、Apple UI/UX レビュー、theme token 改善の判断時
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT

### [Phase12] UI current workflow の system spec 反映先を最適化するパターン（TASK-UI-03）

- **状況**: 実装内容と苦戦箇所を `task-workflow.md` と `lessons-learned.md` にだけ集約すると、component catalog / feature spec / architecture / design-system のどこに何を書くべきかが揺れ、同じ内容の重複と反映漏れが起きやすい
- **アプローチ**:
  - コンポーネント一覧と完了記録は `ui-ux-components.md` に寄せる
  - 機能の振る舞い、関連未タスク、5分解決カードは `ui-ux-feature-components.md` に寄せる
  - 専用型、adapter helper、dedicated harness など責務境界の話は `arch-ui-components.md` に寄せる
  - light/dark token や theme 所見は `ui-ux-design-system.md` に寄せる
  - 横断的な検証値と教訓は `task-workflow.md` / `lessons-learned.md` に残す
- **結果**: 参照起点が固定され、1仕様書=1関心の形で再利用しやすくなる
- **適用条件**: UI current workflow 再監査、Step 2 の更新先選定、SubAgent 分担表を作る前
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT

### [Phase12] UI再撮影前ポート競合 preflight + 分岐記録固定（workflow02）

- **状況**: `screenshot:skill-import-idempotency-guard` 実行時に証跡取得は成功したが、`Port 5174 is already in use` が混在して判定が揺れた
- **アプローチ**:
  - screenshot 実行前に `lsof -nP -iTCP:5174 -sTCP:LISTEN || true` を必須実行して占有有無を固定
  - 競合時は「既存プロセス停止」または「既存サーバー再利用」の分岐を `spec-update-summary.md` に記録
  - その後 `screenshot` 実行と `validate-phase11-screenshot-coverage` を同一ターンで実施し、未解決時は未タスク化する
- **結果**: 成功証跡と環境警告の切り分けが明確になり、再監査時の説明責任を維持できる
- **適用条件**: UI screenshot を Phase 11/12 で再取得するタスク全般
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] UI再撮影後の残留プロセス cleanup 固定（TASK-UI-01）

- **状況**: スクリーンショット再取得完了後に `vite` / `capture-*` プロセスが残留し、後続の検証コマンドや再撮影でポート競合が起きやすい
- **アプローチ**:
  - 再撮影と `validate-phase11-screenshot-coverage` 実行後に `ps -ef | rg "capture-.*phase11|vite" | rg -v rg` を必須実行
  - 残留がある場合は停止し、`documentation-changelog.md` に cleanup 実施を記録
  - 同時に `manual-test-result.md` / `screenshot-coverage.md` の時刻を同期し、証跡と実行環境の両方を固定する
- **結果**: UI証跡更新後の実行環境が安定し、Phase 12 再監査でのポート競合・判定揺れを抑止できる
- **適用条件**: UI再撮影を含む Phase 11/12 再確認タスク全般
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-STORE-IPC-ARCHITECTURE

### [Phase12] 対象workflow配下への証跡正規配置 + `NON_VISUAL` 記法固定（UT workflow）

- **状況**: Phase 11手動結果に別workflow参照が混在し、対象workflowで coverage validator が失敗した
- **アプローチ**:
  - `outputs/phase-11/screenshots` を対象workflow配下へ正規配置する
  - 視覚TCは `screenshots/*.png`、非視覚TCは `NON_VISUAL:` 記法へ統一する
  - `validate-phase11-screenshot-coverage` を再実行し、`expected/covered` と非視覚許容件数を `spec-update-summary.md` に記録する
- **結果**: UI証跡が機械判定可能な形で固定され、再監査で `covered=0` の再発を防止できる
- **適用条件**: UI証跡を複数workflowで流用・再配置する Phase 11/12 再確認タスク
- **発見日**: 2026-03-04
- **関連タスク**: UT-IMP-PHASE12-SCREENSHOT-COMMAND-REGISTRATION-GUARD-001

### [Phase12] `--target-file` 適用境界固定 + `current/baseline` 分離判定（TASK-UI-01-A）

- **状況**: Phase 12 再監査で `audit-unassigned-tasks --target-file` に `outputs/phase-12/*.md` を指定し、対象外エラーで判定が停止した
- **アプローチ**:
  - `--target-file` は `docs/30-workflows/unassigned-task/*.md`、actual parent `docs/30-workflows/completed-tasks/<workflow>/unassigned-task/*.md`、standalone `docs/30-workflows/completed-tasks/*.md` のいずれかに限定し、成果物監査は `--diff-from HEAD` へ切り替える
  - 合否判定は `currentViolations` のみを使用し、`baselineViolations` は資産健全性指標として別管理する
  - move 直後の untracked completed file が `--diff-from HEAD` に出ない場合は、`--target-file docs/30-workflows/completed-tasks/<task>.md` を current 判定の正本にする
  - baseline負債が残る場合は別未タスク（段階削減）へ切り出して追跡する
- **結果**: 監査コマンド誤用による手戻りを防ぎ、差分合否と既存負債の説明責務を同時に満たせる
- **適用条件**: 未タスク監査を含む Phase 12 再確認タスク全般
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-A-STORE-SLICE-BASELINE

### [Phase12] NON_VISUAL manifest配置タスクの効率パターン（TASK-P0-03）

- **状況**: workflow-manifest.json の canonical/mirror 配置のみで、API/IPC/型定義変更がない NON_VISUAL タスク
- **アプローチ**:
  - P50 チェック（Phase 1）で manifest が既に正しく配置済みであることを確認し、不要な上書きを回避
  - ManifestLoader.production-manifest テスト 17 ケースが事前整備済みのため、Phase 5（実装）とPhase 7（テスト）がほぼ即時完了
  - Phase 11 は NON_VISUAL 自動テスト代替 PASS で品質保証を完結
  - system-spec-update-summary で「システム仕様更新: 不要」を明示的に判断・記録
- **結果**: Phase 1-12 を高効率で完走。テスト先行整備が最大の効率化要因
- **教訓**:
  - テストを先行タスクで整備しておくと、配置確認タスクは検証コストがほぼゼロになる
  - NON_VISUAL タスクでも Phase 12 必須5タスクは全て出力が必要（0件でも出力ルール）
  - 「更新不要」の明示判断は、将来の監査で「漏れ」と「意図的スキップ」を区別する根拠になる
- **適用条件**: ファイル配置・設定変更のみで API/IPC/型定義に影響しない小規模タスク
- **発見日**: 2026-04-04
- **関連タスク**: TASK-P0-03 workflow-manifest-production-placement

### [Phase12] ユーザー要求時の `NON_VISUAL` → `SCREENSHOT` 昇格運用（TASK-INVESTIGATE）

- **状況**: 契約修正中心タスクで Phase 11 を `NON_VISUAL` で進めた後、ユーザーから画面検証要求が入り証跡不足が発生する
- **アプローチ**:
  - UI検証要求を受けた時点で、非視覚タスクでも `SCREENSHOT` モードへ即時昇格する
  - `phase-11-manual-test.md` に `テストケース` と `画面カバレッジマトリクス` を追加し、`TC-ID ↔ screenshots/*.png` を固定する
  - `validate-phase11-screenshot-coverage` の `expected=covered` を確認し、`manual-test-result.md` / `evidence-index.md` / `spec-update-summary.md` へ同値転記する
- **結果**: ユーザー要求と機械検証の両方を満たした証跡に収束し、再監査時の手戻りを削減できる
- **適用条件**: 非視覚修正中心だが、UI/UX確認要求が追加された Phase 11/12 再監査タスク
- **発見日**: 2026-03-06
- **関連タスク**: TASK-INVESTIGATE-ELECTRON-SANDBOX-ITERABLE-ERROR-001

### [Phase12] タスク仕様準拠の4点突合 + scoped diff監査（TASK-UI-01-E）

- **状況**: `outputs/phase-12/` のファイル存在だけを見て完了判定すると、`implementation-guide.md` 必須要素や未タスク指示書フォーマット、`phase-12-documentation.md` との同期漏れを取りこぼしやすい
- **アプローチ**:
  - `phase-12-documentation.md` の `completed` / Task 12-1〜12-5 / Task進捗100% と `outputs/phase-12` 実体を同時確認する
  - `implementation-guide.md` の `Part 1 / Part 2`、理由先行、日常例え、型/API/エッジケース/設定語を `rg` で機械確認する
  - 未タスクは `docs/30-workflows/unassigned-task/` への物理配置、`## メタ情報 + ## 1..9` の10見出し、`audit --diff-from HEAD --target-file` と `verify-unassigned-links` を同時に確認する
  - `task-workflow.md` / `lessons-learned.md` / `spec-update-summary.md` / `phase12-compliance-recheck.md` / `unassigned-task-detection.md` に同一の実測値を転記する
- **結果**: Phase 12 の「完了しているように見えるが task spec を満たしていない」状態を早期に検出でき、差分合否と baseline 監視値の混同も防げる
- **適用条件**: docs-heavy task、spec_created task、再監査タスク、既存未タスク是正を含む Phase 12 完了確認全般
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-01-E-INTEGRATION-GATE-SPEC-SYNC
- **クロスリファレンス**: [phase12-task-spec-recheck-template.md](../assets/phase12-task-spec-recheck-template.md), [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase12] docs-heavy parent workflow は review board fallback + exact count 再同期で閉じる（UT-IMP-WORKSPACE-PARENT-REFERENCE-SWEEP-GUARD-001）

- **状況**: docs-only parent workflow の再監査で、UI 実装差分はないが user が screenshot を要求し、さらに related unassigned row を completed 実績へ移したことで `verify-unassigned-links` の total が stale になりやすい
- **アプローチ**:
  - `pointer / index / spec / script / mirror` を別 concern として SubAgent 分担し、親導線の drift を 1 sweep で閉じる
  - current build 再撮影が過剰または環境依存で難しい場合は、same-day upstream screenshot を current workflow へ集約し、review board 1件を current workflow で新規 capture して Apple review の正本にする
  - related unassigned row を completed 実績へ移した後に `verify-unassigned-links` を再実行し、`existing/missing/total` を workflow outputs / task-workflow / workflow spec へ同値転記する
  - 元 unassigned spec は `docs/30-workflows/unassigned-task/` に残したまま status を workflow 実行済みへ更新し、`audit-unassigned-tasks --json --diff-from HEAD --target-file <file>` で配置とフォーマットを当日確認する
- **結果**: docs-heavy task でも visual re-audit を `N/A` にせず閉じられ、台帳移動後の数値ドリフトも current workflow と system spec の両方で防止できる
- **適用条件**: docs-heavy parent workflow、spec_created 由来の再監査、representative screenshot 再確認、related UT の completed 化を伴う Phase 12
- **失敗パターン**:
  - screenshot を `N/A` のまま残し、同日 evidence の review board 化を検討しない
  - related UT を completed 実績へ移した後も `220 / 220` のような旧 total を summary に残す
  - 元 unassigned spec の status だけ更新し、配置確認や `currentViolations=0` を取り直さない
- **発見日**: 2026-03-12
- **関連タスク**: UT-IMP-WORKSPACE-PARENT-REFERENCE-SWEEP-GUARD-001

### [Phase12] 専用 recheck テンプレートで責務を分離（TASK-UI-01-E）

- **状況**: `phase12-system-spec-retrospective-template` だけで再確認から system spec 同期まで抱えると、task spec 準拠確認の責務が埋もれて適用順がぶれやすい
- **アプローチ**:
  - まず `phase12-task-spec-recheck-template.md` で 4点突合と実測値固定を完了する
  - その後に `phase12-system-spec-retrospective-template.md` で実装内容・苦戦箇所・再利用手順へ展開する
  - 仕様書ごとの担当と検証証跡は `phase12-spec-sync-subagent-template.md` で固定する
- **結果**: 再確認と仕様同期の責務が分離され、docs-heavy task でも最小限の順序で機械的に進められる
- **適用条件**: Phase 12 再監査で「まず合否を確定し、その後に system spec と outputs を同期したい」ケース
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-01-E-INTEGRATION-GATE-SPEC-SYNC

---

## ガイドライン

実行時の判断基準。

### 抽象度レベル判定

- **状況**: ユーザー要求の具体性を判断する時
- **指針**: L1（概念）→ 詳細インタビュー、L2（機能）→ 軽いヒアリング、L3（実装）→ 直接実行
- **根拠**: 抽象度に応じて必要な対話量が変わる
- **発見日**: 2026-01-15

### モード選択

- **状況**: create/update/improve-prompt の選択時
- **指針**: 既存スキルパスの有無、更新対象の特定で判断
- **根拠**: detect_mode.js の判定ロジックに準拠
- **発見日**: 2026-01-06

---

## 型定義リファクタリング

### 成功パターン: deprecated プロパティの段階的移行（TASK-FIX-13-1）

**コンテキスト**: TypeScript型定義で `@deprecated` マーク付きプロパティを推奨代替に移行し、定義を削除する

**課題**:

- 同名プロパティ（`name`, `lastUpdated`）が複数の型に存在し、単純な文字列置換では誤修正のリスクが高い
- 永続化互換のため残すべきプロパティと削除すべきプロパティの判定が必要

**解決策**:

1. **スコープ分離**: 削除対象の型を明確にし、同名プロパティが存在する他の型（`SkillImportConfig.lastUpdated`, `StorageMetadata.lastUpdated`）をスコープ外として明示
2. **TDD型レベルテスト**: `@ts-expect-error` ディレクティブで「プロパティが存在しないこと」を型レベルで検証
3. **型スコープ限定grep**: `Anchor` 型スコープに限定して参照箇所を検索し、汎用プロパティ名の誤検出を回避

**結果**: 型定義2箇所の削除、テスト8件PASS、全参照移行完了

**適用条件**: TypeScriptプロジェクトでdeprecatedプロパティを安全に削除したい場合

```typescript
// TDD型レベルテストパターン
it("削除されたプロパティにアクセスするとエラーになること", () => {
  const obj: MyType = { newProp: "value" };
  // @ts-expect-error -- oldProp は削除済み
  const _old = obj.oldProp;
  expect(obj).toBeDefined();
});
```

### 失敗パターン: ドキュメント偏重による実装検証省略

**コンテキスト**: Phase 1-12の並列エージェント実行でドキュメント成果物を高速生成

**課題**: 5つの並列エージェントでPhase 1-11のドキュメントを同時生成し、Phase 12まで完了と報告したが、コードの実装検証（grep・テスト・型チェック）が不十分だった

**原因**: ドキュメント生成の完了を「実装完了」と混同。並列エージェントの出力に対する品質ゲートが未設定

**教訓**:

1. **コード検証ファースト**: ドキュメント生成前に、テスト・型チェック・grepでコード変更の完了を確認する
2. **並列エージェント後の統合検証**: 全エージェント完了後に成果物一覧と整合性チェックを実施
3. **品質ゲートの明示化**: Phase 5（実装）完了の判定基準をテスト結果で定義し、Phase 6以降はその結果を前提とする

### [ビルド・環境] 4ファイル同期漏れパターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: @repo/shared に新サブパスを追加する際、4つのファイル（package.json exports/typesVersions、tsconfig.json paths、vitest.config.ts alias、tsup.config.ts entry）のうち一部のみ更新
- **結果**: TypeScript は通るが Vitest が失敗、またはその逆。CI で初めてエラーが検出される
- **解決策**: 4ファイル同時更新チェックリストを development-guidelines.md に配置。整合性テストの追加
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001
- **関連未タスク**: UT-FIX-TS-VITEST-TSCONFIG-PATHS-001（vitest-tsconfig-paths プラグインによる自動化）

### [UI/TypeScript] HTMLAttributes Props型衝突（TASK-UI-00-ATOMS）

- **状況**: Badge コンポーネントに `content?: string | number` Props を追加
- **問題**: `React.HTMLAttributes<HTMLSpanElement>` の標準属性 `content?: string` と型衝突し、TS2430エラーが発生
- **原因**: HTML標準属性と同名のカスタムPropsを定義したため、TypeScriptが型の互換性を検証できなかった
- **教訓**: `Omit<React.HTMLAttributes<HTMLElement>, "conflictingProp">` で衝突属性を除外してからカスタム型を定義する
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS
- **関連Pitfall**: [06-known-pitfalls.md#P46](../../rules/06-known-pitfalls.md)

```typescript
// ❌ TS2430エラー
interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  content?: string | number; // HTML標準のcontent(string)と衝突
}

// ✅ Omitで衝突回避
interface BadgeProps extends Omit<
  React.HTMLAttributes<HTMLSpanElement>,
  "content"
> {
  content?: string | number;
}
```

**衝突しやすい属性**: `content`, `color`, `translate`, `hidden`, `title`, `dir`, `slot`

### [Phase3] Props命名の仕様-実装間ドリフト（TASK-UI-00-ATOMS）

- **状況**: RelativeTime コンポーネントの自動更新間隔Propsで、仕様書では `updateInterval`、実装では `refreshInterval` と命名が乖離
- **問題**: Phase 10レビュー時に命名不整合が発覚し、仕様書の修正が必要になった
- **原因**: Phase 3設計レビューでProps命名の仕様-実装間突合チェックが不足していた
- **教訓**: Phase 3にProps命名突合チェック項目を追加。仕様書と実装で同一用語を使用する
- **対策**: Phase 3レビューチェックリストに「Props命名の仕様-実装一致確認」を追加
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS

### [Phase4] 修正箇所数の事前ファイル検証不足（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: Phase 4（テスト作成）で task-022 の修正箇所を「3箇所」と仕様書に記載
- **問題**: 実装時に検証したところ、外部ソースインポート文脈の `skill:import` は 1箇所のみだった
- **原因**: Phase 4 設計時にファイル内容を `grep` で事前検証せず、概算で修正箇所数を決定
- **教訓**: Phase 4 テスト設計時は対象ファイルを `grep -c` で事前カウントし、期待値を「N件以上」のような柔軟な基準で設計する。P37（ドキュメント数値の早期固定）と同じパターン
- **対策**: テスト仕様書の期待値は `>=N` 形式で記述し、Phase 5 実行後に実測値で更新
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001

### [Phase12] 対象テスト限定実行の明示（TASK-UI-01-C 再監査）

- **状況**: Phase 12 再監査で「対象5ファイルのみ再検証」したい場面
- **成功パターン**:
  - `pnpm exec vitest run <file1> <file2> ...` で対象を明示し、`N files / M tests` を成果物へ固定
  - 監査ログに「対象ファイル列挙 + 実測件数」を残し、再実行時の比較可能性を確保
- **失敗パターン**:
  - `pnpm run test:run -- <files...>` を使い、script側の設定で全体テストへ展開されて長時間化・中断を招く
- **標準ルール**:
  - 再監査時の限定テストは script ラッパーを経由せず `pnpm exec vitest run` を正とする
  - 目的が「再確認」の場合は coverage を同時実行せず、まず対象テストのPASSを確定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-C-NOTIFICATION-HISTORY-DOMAIN

### [Phase12] Step 1-A四点同期 + Phase 11再撮影運用ガード（TASK-UI-01-D 再確認）

- **状況**: Phase 12 の再確認で `spec-update-summary.md` と system spec は更新済みでも、`LOGS.md` / `SKILL.md` / `topic-map` の同期が後回しになりやすい。さらに再撮影時に workflow 固定出力先と `Port 5177` 競合で証跡運用が不安定化する
- **成功パターン**:
  - Step 1-A を「`LOGS.md` x2 + `SKILL.md` x2 + `generate-index`」の四点セットとして同一ターンで完了する
  - Phase 11 再撮影は workflow 配下保存を固定し、ポート preflight の分岐（停止/再利用）を `unassigned-task-detection.md` へ記録する
  - 運用ギャップは `docs/30-workflows/unassigned-task/` へ未タスク化し、`audit --target-file` で `currentViolations=0` を確認する
- **失敗パターン**:
  - `spec-update-summary` のみ更新して Step 1-A 完了扱いにする
  - 固定出力先のまま再撮影して手動コピーで帳尻を合わせる
  - ポート競合を記録せずに「再撮影済み」と判定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-D-VIEWTYPE-ROUTING-NAV, UT-IMP-TASK-056D-PHASE11-SCREENSHOT-CAPTURE-PATH-GUARD-001

### [Phase12] UI再撮影のworkflow保存先固定 + strictPort preflight（5177）記録テンプレート（TASK-UI-01-D 追補）

- **状況**: system spec へ「実装内容」と「苦戦箇所」を追記しても、再撮影の実行前ガード（保存先/ポート）をテンプレートに書かないと再発しやすい
- **成功パターン**:
  - `phase12-system-spec-retrospective-template.md` / `phase12-spec-sync-subagent-template.md` に `lsof -nP -iTCP:5177 -sTCP:LISTEN` を追加し、分岐（停止/再利用/別ポート）記録を必須化
  - `test -d <workflow>/outputs/phase-11/screenshots` で保存先を先に固定し、workflow外証跡の流入を防止
  - 5分解決カードを `task-workflow` / `lessons-learned` / `ui-ux-navigation` へ同一内容で同期する
- **失敗パターン**:
  - preview preflight だけ実施して strictPort preflight を省略する
  - `task-056` 固定パスの証跡を手動コピーで帳尻合わせし、分岐記録を残さない
- **標準ルール**:
  - UI再撮影運用は「preview preflight」「strictPort preflight」「workflow保存先確認」の3点を必須セットとする
  - preflight失敗時は再撮影を継続せず未タスク化し、再発条件を `lessons-learned` に固定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-D-VIEWTYPE-ROUTING-NAV, UT-IMP-TASK-056D-PHASE11-SCREENSHOT-CAPTURE-PATH-GUARD-001

### [Phase12] shared transport DTO + cross-cutting doc + 専用 harness 同期（TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001）

- **状況**: IPC transport 契約をコード上は是正したが、`ipc-contract-checklist.md` / `quick-reference.md` の横断導線や、画面検証の対象 view 専用 harness 条件が後追いになりやすい
- **成功パターン**:
  - shared transport DTO を `packages/shared` に集約し、Main / Preload / Renderer は import / re-export のみで追従する
  - Step 2 で `interfaces` / `api-ipc` / `security` / `task-workflow` / `lessons` に加えて `ipc-contract-checklist.md` / `indexes/quick-reference.md` を同一ターンで同期する
  - UI契約だけを確認したい場合は対象 view 専用 harness を追加し、`SCREENSHOT` 証跡と `validate-phase11-screenshot-coverage` をセットで固定する
  - 運用ギャップがスクリプト改善領域なら未タスク化し、`audit --target-file` で `currentViolations=0` を確認する
- **失敗パターン**:
  - `interfaces` / `api-ipc` だけ更新して、cross-cutting doc が古いまま残る
  - App 全体起動のノイズを抱えたまま画面検証し、対象 contract の変化点が読み取れない
  - `verify-unassigned-links` の `missing` だけを見て原因を手で辿り、改善バックログへ formalize しない
- **標準ルール**:
  - IPC transport 契約修正は「shared DTO」「cross-cutting doc」「画面検証方針」の3点を同一ターンで閉じる
  - ユーザーが画面検証を要求した場合、初期方針が非視覚でも `SCREENSHOT` へ昇格し、必要なら専用 harness を許可する
  - 監査ツールの説明力不足は `docs/30-workflows/unassigned-task/` へ未タスク化し、配置・形式・参照を機械検証してから完了扱いにする
- **発見日**: 2026-03-06
- **関連タスク**: TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001, UT-IMP-PHASE12-UNASSIGNED-LINK-DIAGNOSTICS-001

### [Phase12] domain spec に `実装内容` / `苦戦箇所` / `5分カード` を対称配置する（TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001 追補）

- **状況**: `task-workflow` と `lessons-learned` には知見があるのに、`interfaces` / `api-ipc` の domain spec 側は契約表だけで終わり、再利用時に背景と難所が読めない
- **成功パターン**:
  - `assets/phase12-domain-spec-sync-block-template.md` を使い、更新した domain spec に `### 実装内容（要点）` / `### 苦戦箇所（再利用形式）` / `### 同種課題の5分解決カード` を同居させる
  - `interfaces` と `api-ipc` の両方で、shared DTO 正本化・UI表示契約・Phase 11 画面検証方針を同じ粒度で記録する
  - `task-workflow` / `lessons-learned` / domain spec の 3 点で 5 ステップ順序をそろえる
- **失敗パターン**:
  - domain spec をチャネル表や型表の更新だけで終え、苦戦箇所を lessons のみに押し込む
  - `task-workflow` と domain spec で 5 分解決カードの順序や検証値が異なる
- **標準ルール**:
  - Phase 12 Step 2 で触る domain spec は、契約表だけでなく「実装内容」「苦戦箇所」「5分カード」の3点を最小セットとする
  - `rg -n '^### 実装内容（要点）$|^### 苦戦箇所（再利用形式）$|^### 同種課題の5分解決カード$' <domain-spec-file>` を完了前に必ず実行する
- **発見日**: 2026-03-06
- **関連タスク**: TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001

### [Phase12] UI domain spec は「主目的 + 状態契約 + 画面証跡」を先に固定する（TASK-UI-06-HISTORY-SEARCH-VIEW）

- **状況**: UI task の system spec を作るとき、コンポーネント一覧と screenshot 一覧だけでは「何のための画面か」「どの state/IPC が正本か」が後から読み取りにくい
- **成功パターン**:
  - 専用 domain spec に `### 実装内容（要点）` を置き、`画面の主目的` / `変更範囲` / `契約上の要点` / `視覚検証` / `完了根拠` を最初に固定する
  - `ui-ux-feature-components.md` 側は圧縮サマリーと 5分解決カードだけを保持し、詳細は専用 spec へリンクする
  - `task-workflow.md` / `lessons-learned.md` / UI domain spec の 3 点で 5 ステップ順序を揃える
- **失敗パターン**:
  - UI spec が責務表と screenshot 一覧だけで終わり、変更範囲や state 契約の要点が本文から見えない
  - 専用 spec と feature summary spec で見出し名や 5分カードの粒度がずれる
- **標準ルール**:
  - UI domain spec の `実装内容（要点）` には少なくとも `画面の主目的` / `契約上の要点` / `視覚検証` の 3 行を入れる
  - `ui-ux-feature-components.md` の対応節にも `同種課題の5分解決カード` を置き、専用 spec と task-workflow の橋渡しに使う
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-06-HISTORY-SEARCH-VIEW

### [Phase12] `ui-ux-feature-components.md` も 3ブロック構成で閉じる（TASK-SKILL-LIFECYCLE-01）

- **状況**: `task-workflow.md` と `lessons-learned.md` には実装内容と苦戦箇所が入っているのに、`ui-ux-feature-components.md` 側はサマリー表だけで終わり、feature spec 単体では再利用手順が読み取りにくくなる
- **成功パターン**:
  - `ui-ux-feature-components.md` の対象節にも `実装内容（要点）` / `苦戦箇所（再利用形式）` / `同種課題の5分解決カード` を置く
  - `実装内容（要点）` には少なくとも `画面の主目的` / `契約上の要点` / `視覚検証` / `完了根拠` を含める
  - `苦戦箇所` は `task-workflow.md` / `lessons-learned.md` と同じ再発条件で揃え、feature spec では UI 起点の対処へ寄せて圧縮する
  - `currentViolations=0` と `baselineViolations>0` の二軸報告が必要なら feature spec 側にも短く残す
- **失敗パターン**:
  - feature spec を「UI観点の要点」だけで閉じ、苦戦箇所を別仕様書に追い出す
  - task-workflow と feature spec で 5分解決カードの順序や検証値がズレる
- **標準ルール**:
  - UI task の feature spec は圧縮サマリー専用にせず、最小3ブロックを持つ再利用正本として形成する
  - `rg -n '^#### 実装内容（要点）$|^#### 苦戦箇所（再利用形式）$|^#### 同種課題の5分解決カード$' references/ui-ux-feature-components.md` を完了前に実行する
- **発見日**: 2026-03-11
- **関連タスク**: TASK-SKILL-LIFECYCLE-01

### [Phase12] 「更新予定のみ」残置を排除し、実更新ログへ昇格する（TASK-10A-E-C）

- **状況**: Phase 12 で `spec-update-summary.md` は更新されているが、`documentation-changelog.md` や `phase-12-documentation.md` が「仕様策定のみ」「実行中」のまま残る
- **成功パターン**:
  - `documentation-changelog.md` を最終正本として再作成し、Task 1〜5 の実施結果を確定値で記録する
  - `phase-12-documentation.md` のチェックボックスを実績へ同期する
  - `verify-all-specs` / `validate-phase11-screenshot-coverage` / `verify-unassigned-links` の結果を changelog に固定する
- **失敗パターン**:
  - `spec-update-summary.md` だけ更新して完了扱いにする
  - 「更新予定」「実行待ち」記述を残したまま Phase 12 を閉じる
- **標準ルール**:
  - Phase 12 完了前に `rg -n "仕様策定のみ|実行中|実行待ち|更新が必要" outputs/phase-12` を実行し、残置文言をゼロにする
  - completed workflow では `phase-12-documentation.md` に対しても `rg -n "仕様策定のみ|実行予定|保留として記録"` を実行し、本文だけ stale な状態を残さない
  - `phase-12-documentation.md` の完了条件と `Task 100% 実行確認` を `[x]` へ同期し、Phase 13 以外の保留を残さない
  - Task 1〜5 の実施証跡を 1 ファイル（`documentation-changelog.md`）で追跡可能にする
- **発見日**: 2026-03-06
- **関連タスク**: TASK-10A-E-C

### [Phase12] 未タスク指示書は 9見出しテンプレート準拠で作成する（TASK-10A-E-C）

- **状況**: 未タスクを短縮形式で作成すると、`audit-unassigned-tasks` の format violation が発生
- **成功パターン**:
  - `assets/unassigned-task-template.md` を適用し、`## 1..9` を全て埋める
  - 作成直後に `audit-unassigned-tasks --target-file` で個別検証する
- **失敗パターン**:
  - メタ情報 + 背景 + 受け入れ条件だけで未タスクを作る
  - 参照情報/リスク/検証手順を省略する
- **標準ルール**:
  - 未タスク新規作成時は「テンプレート適用→個別監査PASS→台帳同期」の3点を同一ターンで完了する
- **発見日**: 2026-03-06
- **関連タスク**: UT-10A-E-C-001, UT-10A-E-C-002

### [Phase12] スキルフィードバックレポートテンプレート（TASK-UI-03）

- **状況**: Phase 12 Task 5（スキルフィードバックレポート）の記載粒度がタスクごとにばらつき、後続のスキル改善で活用しにくい
- **成功パターン**:
  - 以下の4セクション構成を標準テンプレートとして使用する:

```markdown
# スキルフィードバックレポート

## 1. ワークフロー改善点

| 改善対象 | 現状の問題 | 改善提案 | 優先度 |
| --- | --- | --- | --- |
| {{Phase/Step名}} | {{具体的な問題}} | {{改善内容}} | HIGH/MEDIUM/LOW |

## 2. 技術的教訓

| 教訓 | 再発条件 | 防止策 | 新規Pitfall候補 |
| --- | --- | --- | --- |
| {{教訓の要約}} | {{再現手順/条件}} | {{具体的な対策}} | P{{番号}}候補 or N/A |

## 3. スキル改善提案

| 対象スキル | 対象ファイル | 改善内容 | 根拠タスク |
| --- | --- | --- | --- |
| {{skill-creator/task-specification-creator}} | {{references/xxx.md}} | {{追加/変更内容}} | {{TASK-ID}} |

## 4. 新規Pitfall候補

| ID候補 | タイトル | 症状 | 解決策 | 関連P |
| --- | --- | --- | --- | --- |
| P{{N}} | {{タイトル}} | {{症状}} | {{解決策}} | {{関連する既存Pitfall}} |
```

  - 改善点が0件のセクションでも「該当なし」と明記して省略しない
  - Phase 10 MINOR指摘から抽出した教訓は必ずセクション2に記載する
- **失敗パターン**:
  - 自由記述で書き、後続タスクで構造化データとして活用できない
  - 「改善点なし」の一文で済ませ、Phase 10の指摘事項を教訓化しない
- **適用条件**: Phase 12 Task 5 実行時（全タスクで必須）
- **発見日**: 2026-03-07
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT




### [Phase12] branch横断 Phase 12 一括監査（workflow複数同時検証）

- **状況**: 1つのworkflowをPASS化しても、同じブランチで更新された他workflowに未準拠が残る
- **アプローチ**:
  - `git status --short` で今回変更workflowを列挙
  - 各workflowに `validate-phase-output` と `validate-phase12-implementation-guide` を実行
  - 欠落は未タスクへ分離し `docs/30-workflows/unassigned-task/` に正規配置
- **結果**: 単体PASSと branch全体PASSを分離して判定できる
- **適用条件**: 同一ブランチで複数workflowを並行更新している場合
- **発見日**: 2026-03-07
- **関連タスク**: TASK-FIX-SETTINGS-PERSIST-ITERABLE-HARDENING-001 再監査

### [Phase12] `verify-all-specs` PASS と Phase 12 完了は同義ではない（dual validator gate）

- **状況**: workflow 10/11/12 で `verify-all-specs` は PASS だが、Phase 12 実装ガイド欠落や必須セクション欠落が残存した。
- **成功パターン**:
  - 完了ゲートを `verify-all-specs` + `validate-phase-output --phase 12` + `validate-phase12-implementation-guide` の3点セットに固定する
  - FAIL項目は workflow 別に未タスクへ分離し、`docs/30-workflows/unassigned-task/` へ即時配置する
  - 未タスクは `audit-unassigned-tasks --target-file` と `verify-unassigned-links` で当日検証する
- **失敗パターン**:
  - `verify-all-specs` PASS のみで「Phase 12 完了」と判断する
  - 未タスクを作成しても配置/フォーマット監査を省略する
- **適用条件**: branch 内で複数workflowを同時更新・同時監査する場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-PHASE12-BRANCH-CROSS-AUDIT（再確認）

### [Phase12] current workflow placeholder 排除 + legacy baseline 二軸報告（TASK-10A-F 再同期）

- **状況**: current workflow の `manual-test-result.md` や `screenshots/README.md` に `P53` / `代替` / `スクリーンショット不可` が残ったままでも、system spec 側が更新済みだと「全体としては揃っている」と誤認しやすい
- **アプローチ**:
  - screenshot 必須タスクでは current workflow から placeholder 文言を除去し、`TC-ID ↔ png` の実証跡だけを残す
  - `implementation-guide.md` はテンプレート段階で `## Part 1` / `## Part 2`、`APIシグネチャ`、`エラーハンドリング`、`設定項目と定数一覧` を先置きする
  - 未タスク確認は `新規未タスク` と `legacy baseline` を分離し、`currentViolations=0` と `baselineViolations>0` を同時に報告する
  - Phase 12 では workflow outputs と system spec を同ターンで更新し、`更新済みを確認` と `今回更新` を書き分ける
- **結果**: 「正本は正しいが current workflow が stale」「今回差分は合格だが directory 全体には legacy 負債が残る」を混同せず報告できる
- **適用条件**: current workflow 再監査、UI screenshot 再取得、legacy unassigned backlog を抱えた docs-heavy task
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-F

### [Phase12] `current=0` でも legacy backlog 参照を省略しない（TASK-SKILL-LIFECYCLE-01）

- **状況**: `audit-unassigned-tasks --json --diff-from HEAD` が `currentViolations=0` を返すと、`unassigned-task-detection.md` が「問題なし」で閉じられ、`docs/30-workflows/unassigned-task/` 全体に残る legacy backlog や既存 remediation task への導線が消えやすい
- **成功パターン**:
  - `今回タスク由来 0 件` と `directory baseline 継続` を別行で記載する
  - `verify-unassigned-links`、`audit --diff-from HEAD`、`audit --json` の値を `spec-update-summary.md` / `phase12-task-spec-compliance-check.md` / `unassigned-task-detection.md` / `task-workflow.md` に同値で同期する
  - baseline backlog に対する既存改善タスクがある場合は、`unassigned-task-detection.md` と `skill-feedback-report.md` に参照を残す
  - Phase 12 の root evidence は `outputs/phase-12/phase12-task-spec-compliance-check.md` とし、SubAgent ごとの判断をここに集約する
- **失敗パターン**:
  - `currentViolations=0` のみを理由に `docs/30-workflows/unassigned-task/` 全体が健全と書く
  - baseline backlog の数値を system spec と outputs で別々に記録する
  - `skill-feedback-report.md` に task-spec 改善だけを書き、skill-creator 側の改善点を残さない
- **結果**: 「今回差分は task spec 準拠」「既存 backlog は別課題として継続」の責務分離が明確になり、Phase 12 の完了報告が過剰に楽観化しなくなる
- **適用条件**: docs-heavy task、再監査タスク、未タスク 0 件報告を含む Phase 12 全般
- **発見日**: 2026-03-11
- **関連タスク**: TASK-SKILL-LIFECYCLE-01

### [Phase12] Light Mode 全画面 white/black 基準 + compatibility bridge 固定（TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001）

- **状況**: `tokens.css` を white/black 基準へ直しても、renderer 側の `text-white` / `bg-gray-*` / `border-white/*` などが残り、全画面で Light Mode が崩れる。さらに desktop CI の一部 shard fail と screenshot stale が同時に起きやすい
- **成功パターン**:
  - 先に light token baseline を `#ffffff / #000000` に固定する
  - `rg -n "text-white|bg-white/|border-white/|text-gray-|bg-gray-|border-gray-" apps/desktop/src/renderer` で renderer 全域の hardcoded neutral class を棚卸しする
  - token 修正だけで足りない場合は `globals.css` に compatibility bridge を入れ、共通 primitives を token へ寄せる
  - GitHub desktop CI が shard 単位で落ちたら `pnpm --filter @repo/desktop exec vitest run --shard=<n>/16` で同じ shard を local 再現する
  - baseline を変えたら screenshot を撮り直し、`validate-phase11-screenshot-coverage` を PASS へ戻してから system spec を同期する
- **失敗パターン**:
  - token table だけ更新して renderer-wide class drift を監査しない
  - 互換 bridge を入れず、画面ごとの個別修正だけで全体整合を取ろうとする
  - broad rerun だけで CI fail の原因調査を終える
  - light baseline を変えた後も旧 screenshot をそのまま使う
- **結果**: white background / black text の全画面共通基準、shard 再現による局所修正、再取得 screenshot を同一テンプレートで扱えるようになり、Light Mode 系の再監査が短手順で再利用可能になった
- **適用条件**: global theme remediation、design token 再是正、contrast 回帰、Phase 11 screenshot 再取得を伴う UI task
- **発見日**: 2026-03-11
- **関連タスク**: TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001

### [Phase12] light theme shared color migration は token scope / component scope / verification-only lane を分離する（TASK-FIX-LIGHT-THEME-SHARED-COLOR-MIGRATION-001）

- **状況**: global light remediation 後の follow-up task で、親 unassigned-task の対象一覧をそのまま使うと current worktree の実体とずれやすい。settings/auth/workspace をまたぐため、UI だけ読んでも system spec 抽出が漏れやすい
- **成功パターン**:
  - Phase 1 で current worktree の hardcoded color inventory を取り直し、old unassigned-task の対象を盲信しない
  - primary targets を `ThemeSelector` / `AuthModeSelector` / `AuthKeySection` / `AccountSection` / `ApiKeysSection` / `AuthView` / `WorkspaceSearchPanel` に固定し、`SettingsView` / `SettingsCard` / `DashboardView` は verification-only lane に落とす
  - token foundation は親 workflow、current task は component migration、wrapper は verification-only として 3 lane に分離する
  - `ui-ux-design-system` / `ui-ux-settings` / `ui-ux-feature-components` / `ui-ux-components` / `ui-ux-search-panel` / `ui-ux-portal-patterns` / `rag-desktop-state` / `api-ipc-auth` / `api-ipc-system` / `architecture-auth-security` / `security-electron-ipc` / `security-principles` / `task-workflow` / `lessons-learned` の要否を同一ターンで判定する
  - `spec_created` task では Phase 1-3 を completed に固定してから、Phase 4+ を planned のまま書く
- **失敗パターン**:
  - `SettingsView` / `DashboardView` を親 task のまま P1 扱いし、actual inventory を補正しない
  - token baseline の議論と component migration を同じ仕様書で進める
  - `ui-ux-*` だけ読んで `api-ipc-*` / `security-*` / `rag-desktop-state` / `ui-ux-portal-patterns` を落とす
  - Phase 1-3 gate 前に Phase 4-13 を completed 扱いにする
- **結果**: `spec_created` UI task でも current inventory と system spec 抽出セットが揃い、後続の実装 lane / regression guard / Phase 12 同期が短手順で再利用できる
- **適用条件**: Light Mode follow-up、component migration、settings/auth/workspace を跨ぐ UI task、spec-only workflow 再監査
- **発見日**: 2026-03-12
- **関連タスク**: TASK-FIX-LIGHT-THEME-SHARED-COLOR-MIGRATION-001

### [Phase 12] loopback screenshot capture は localhost 不達時に current build static server を自動起動する

- **状況**: screenshot capture script が `http://127.0.0.1:<port>` / `http://localhost:<port>` を前提にしていると、preview / static serve を別ターミナルで起動し忘れた瞬間に `ERR_CONNECTION_REFUSED` で落ちる
- **アプローチ**:
  1. capture 実行前に loopback `baseUrl` の readiness probe を行う
  2. 不達かつ参照先が loopback の場合のみ、current worktree `apps/desktop/out/renderer` をローカル static server で自動配信する
  3. capture 完了後は自動起動した server を cleanup し、`phase11-capture-metadata.json` / `manual-test-result.md` / Phase 12 レポートに fallback 使用を記録する
  4. `current build` の asset hash と capture timestamp が同一 worktree 由来であることを確認する
- **結果**: 「人手 preflight が1つ漏れただけで Phase 11 が全停止する」状態を避けつつ、current build 正本での screenshot 証跡を維持できる
- **適用条件**: worktree 上の UI 再撮影、loopback baseUrl 固定の capture script、preview source drift を避けたい Phase 11/12 再監査
- **発見日**: 2026-03-12
- **関連タスク**: TASK-IMP-LIGHT-THEME-CONTRAST-REGRESSION-GUARD-001

### [Testing] コンポーネント分割テスト戦略パターン（TASK-043D）

- **状況**: 大規模コンポーネント（AgentView 556行テスト）を複数の子コンポーネントに分割する際、テストの責務境界が曖昧になり、テストケースの重複や漏れが発生する
- **アプローチ**:
  1. 各分割コンポーネントに独立テストファイルを新設（`AdvancedSettingsPanel.test.tsx`, `ExecuteButton.test.tsx` 等）
  2. レイアウトテスト（`.layout.test.tsx`）を親コンポーネントに残し、子コンポーネントの配置・表示条件を検証
  3. Store統合テスト（`.store-integration.test.tsx`）を別ファイルで管理し、Store操作とIPC連携を分離
- **テストファイル命名規則**:

| ファイル種別 | 命名パターン | 責務 |
| --- | --- | --- |
| UIテスト | `{Component}.test.tsx` | レンダリング、ユーザー操作 |
| レイアウトテスト | `{Parent}.layout.test.tsx` | 子コンポーネント配置・表示条件 |
| Store統合テスト | `{Component}.store-integration.test.tsx` | Store操作・IPC連携 |
| セレクタテスト | `{slice}.selectors.test.ts` | 純粋なセレクタロジック |
| 🏗️ DI・設計               | Setter Injection遅延初期化, **二重パイプライン設計（execute→SkillFileWriter persist統合 TASK-P0-05）**, **Optional Inject graceful degradation（SkillFileWriter未注入時warn+skip）**                                                                                                                                                                                                                                                                                                                                                                                                          | -                                                                                                                                                                                                                                                                                                                                                                                  |
| 💾 永続化・復旧            | **persist復旧の3段ガード（Set/Array二方向シリアライズ）**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | -                                                                                                                                                                                                                                                                                                                                                                                  |
| 🛡️ セキュリティ           | TDDセキュリティテスト分類体系, YAGNI共通化判断記録                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | 正規表現パターンPrettier干渉                                                                                                                                                                                                                                                                                                                                                       |
| 📦 スキル設計             | Collaborative First, Script Firstメトリクス, 詳細情報分離, 大規模DRYリファクタリング, **クロススキル・マルチスキル・外部CLI 3軸同時設計**                                                                                                                                                                                                                                                                                                                                                                                                                                                    | -                                                                                                                                                                                                                                                                                                                                                                                  |
| 🔗 SDK統合                | TypeScriptモジュール解決による型安全統合, **SDKテストTODO一括有効化**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | カスタムdeclare moduleとSDK実型共存, 未タスク配置ディレクトリ混同                                                                                                                                                                                                                                                                                                                  |
| 🔧 ビルド・環境           | **モノレポ三層モジュール解決整合**, **TypeScript paths定義順序制御**, **ソース構造二重性パスマッピング吸収**, **CIガードスクリプトによるモノレポ設定ファイル整合性自動検証**, **正規表現ベースTypeScript設定ファイルパーサー**, **Worktree環境初期化プロトコル**                                                                                                                                                                                                                                                                                                                               | ネイティブモジュールNODE_MODULE_VERSION不一致, **4ファイル同期漏れ**, **TypeScript設定ファイル完全AST解析の試行**                                                                                                                                                                                                                                                                  |
| 🔄 型定義リファクタリング | deprecatedプロパティ段階的移行                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | ドキュメント偏重による実装検証省略                                                                                                                                                                                                                                                                                                                                                 |
| 🎨 UI/フロントエンド      | **Props駆動Atoms設計**, **Record型バリアント定義**, **テーマ横断テスト（describe.each）**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | **HTMLAttributes Props型衝突**, **Props命名の仕様-実装間ドリフト**                                                                                                                                                                                                                                                                                                                 |

## 成功パターン

成功した実行から学んだベストプラクティス。

### [IPC/Auth] APIキー連動3点セット同期（TASK-FIX-APIKEY-CHAT-TOOL-INTEGRATION-001）

- **状況**: Settings で APIキーを更新しても `ai.chat` の実行経路が旧状態を参照し、`saved` と `env-fallback` の表示も曖昧になる
- **アプローチ**:
  - `llm:set-selected-config` で Renderer 選択状態を Main へ同期する
  - `apiKey:save/delete` 成功後に `LLMAdapterFactory.clearInstance(provider)` を実行する
  - `auth-key:exists` を `{ exists, source }` へ拡張し、UI は `source` 優先表示に統一する
  - 仕様同期は `interfaces-auth` / `llm-ipc-types` / `api-ipc-system` / `security-electron-ipc` / `ui-ux-settings` / `task-workflow` / `lessons-learned` の7仕様書を同一ターンで実施する
- **結果**: 実行経路、鍵更新反映、状態表示のドリフトを同時に解消し、同種課題の初動を短縮
- **再確認運用**:
  - Phase 12 再監査では `verify-all-specs` / `validate-phase-output --phase 12` / `validate-phase12-implementation-guide` / `validate-phase11-screenshot-coverage` を同一セットで再実行する
  - 未タスク監査は `audit --diff-from HEAD` の `currentViolations` を合否判定に使い、`baselineViolations` は legacy 監視として分離記録する
- **適用条件**: APIキー保存とチャット実行が別経路で管理される IPC/UI タスク
- **失敗パターン**:
  - `apiKey:save` の永続化のみ更新して cache clear を実装しない
  - `auth-key:exists` を boolean のまま維持し、判定根拠を UI へ返さない
  - `task-workflow` のみ更新して domain spec（interfaces/api-ipc/security/ui）を未同期にする
- **発見日**: 2026-03-11
- **関連タスク**: TASK-FIX-APIKEY-CHAT-TOOL-INTEGRATION-001

### [Phase12] 証跡テーブル互換 + screenshot preflight 固定（TASK-FIX-SETTINGS-APIKEY-CONTRACT-GUARD-001）

- **状況**: `validate-phase11-screenshot-coverage` が `manual-test-result.md` から証跡列を抽出できず失敗し、さらに screenshot 再取得時に optional dependency 欠落で停止
- **アプローチ**:
  - Phase 11 成果物に validator互換ヘッダ（`テストケース` / `証跡`）を固定
  - screenshot 再取得前に `pnpm install` を preflight 実行
  - 取得後に `validate-phase11-screenshot-coverage` を再実行し、`expected=covered` を確認
- **結果**: screenshot 証跡監査を PASS 化し、Phase 12 の再確認を機械判定できる状態へ復帰
- **適用条件**: Phase 11で手動テスト証跡を運用する全 workflow
- **発見日**: 2026-03-08
- **関連タスク**: 06-TASK-FIX-SETTINGS-APIKEY-CONTRACT-GUARD-001

### [Phase12] 未タスク参照の canonical path 固定（TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001）

- **状況**: Phase 12 Task 4 で残課題を検出しても、`light-theme-*/` の workflow ディレクトリ参照だけで管理し、`docs/30-workflows/unassigned-task/` の正式指示書作成が抜ける
- **アプローチ**:
  - 残課題を `docs/30-workflows/unassigned-task/` へ 9見出しフォーマットで正式起票する
  - `task-workflow.md` / `ui-ux-design-system.md` の関連タスク参照を、workflow ディレクトリではなく未タスク指示書ファイルへ同期する
  - `audit-unassigned-tasks --json --diff-from HEAD --target-file <new-file>` を各新規ファイルに対して実行し、`currentViolations=0` を確認する
  - `unassigned-task-detection.md` に件数と監査値（current/baseline）を同値転記する
- **結果**: 「検出レポートはあるが正式未タスクがない」状態を防ぎ、Phase 12 の追跡性を維持できる
- **適用条件**: UI再監査や token 修正で follow-up 課題を検出したが、実装タスク本体で完了しない場合
- **発見日**: 2026-03-11
- **関連タスク**: TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001

### [Phase12] 画面検証で露出した副次不具合の即時未タスク化 + 3.5 節継承（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: 代表画面の screenshot 再取得中に、主タスクとは別の light theme contrast / React key warning / rollout 漏れが露出し、親 task だけ直しても再発防止にならない
- **アプローチ**:
  - screenshot 証跡から露出した副次不具合を、その場で `docs/30-workflows/unassigned-task/` に正式な未タスクとして起票する
  - 親タスクに苦戦箇所がある場合、新規未タスクへ `### 3.5 実装課題と解決策` を追加して再発条件と解決策を継承する
  - `verify-unassigned-links` を `missing=0` まで閉じ、`existing/missing/current/baseline` を `spec-update-summary.md` / `unassigned-task-detection.md` / `task-workflow.md` へ同値転記する
- **結果**: screenshot 由来の副次不具合が evidence のまま放置されず、未タスク台帳と system spec の両方に再利用可能な形で残る
- **適用条件**: ユーザーが画面検証を明示要求し、再撮影過程で本筋以外の不具合や warning を見つけた Phase 12 再監査
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [Phase12] 既存未タスク再参照時の target-file 監査固定（TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001）

- **状況**: `unassigned-task-detection.md` で「新規0件 / 既存再参照あり」と判定しても、再参照先の既存未タスク本文が10見出し要件を満たさず `currentViolations>0` になる場合がある
- **アプローチ**:
  - `audit-unassigned-tasks --json --diff-from HEAD` で全体合否（current/baseline）を確認した後、再参照した既存未タスクへ `--target-file` を個別実行する
  - 個別監査で current違反が出た場合は、同ターンで9/10見出し要件へ是正し、再監査で `currentViolations=0` を固定する
  - `verify-unassigned-links` の total は固定値を使わず同一ターン実測値を `unassigned-task-detection.md` / `documentation-changelog.md` / system spec に同値転記する
- **結果**: 「新規未タスクは0件だが、再参照先の品質が崩れている」取りこぼしを防げる
- **適用条件**: Phase 12 で既存未タスク再利用を選択した全タスク
- **失敗パターン**:
  - diff監査のみで完了判定し、再参照タスク本文の品質監査を省略する
  - `verify-unassigned-links` 件数を過去値のまま転記し、current実測と不一致になる
- **発見日**: 2026-03-14
- **関連タスク**: TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001

### [Phase12] 契約テストと回帰テストの責務分離（TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001）

- **状況**: design/spec_created タスクで Phase 4（契約テスト仕様）と Phase 6（回帰テスト仕様）を同時に書く際、同一ロジックを重複検証して保守コストが増える
- **アプローチ**:
  - Phase 4 は「単一関数の入出力契約（引数・戻り値・例外）」に限定する
  - Phase 6 は「イベント伝播・状態遷移・複数コンポーネント連携」の回帰に限定する
  - `phase-4-test-creation.md` / `phase-6-test-expansion.md` を grep 比較し、重複テスト ID（例: `TC-C*` と `MR-*`）を同一ターンで棚卸しする
  - 責務分離ができない場合は未タスクを即時起票し、`task-workflow` / `lessons-learned` / workflow spec を同一 wave で更新する
- **結果**: テスト種別の責務境界が明確になり、重複テストの管理負荷を先回りで抑制できる
- **適用条件**: 実装より先にテスト仕様を定義する design/spec_created タスク
- **失敗パターン**:
  - 契約テストと回帰テストで同一入力パターンをそのまま重複検証する
  - 重複を検出しても未タスク化せず、次タスクへ暗黙持ち越しにする
- **発見日**: 2026-03-14
- **関連タスク**: TASK-IMP-AI-RUNTIME-AUTHMODE-UNIFICATION-001

### [Skill] Collaborative First による要件明確化

- **状況**: ユーザーの要求が抽象的（L1/L2レベル）
- **アプローチ**: AskUserQuestion でインタビューを実施し、段階的に具体化
- **結果**: 要件の認識齟齬を防ぎ、手戻りを削減
- **適用条件**: 抽象度が高い要求、複数の解釈が可能な場合
- **発見日**: 2026-01-15

### [Skill] Script First によるメトリクス収集

- **状況**: フィードバック分析でデータ収集が必要
- **アプローチ**: collect_feedback.js でメトリクスを収集し、LLMは解釈のみ担当
- **結果**: 100%正確なデータに基づく改善提案が可能
- **適用条件**: 定量的なデータが必要な処理
- **発見日**: 2026-01-13

### [Skill] 詳細情報の分離によるSKILL.md最適化

- **状況**: SKILL.mdが500行制限を超過（521行）
- **アプローチ**:
  - Part 0.5: 詳細フローチャートをexecution-mode-guide.mdへ移動（86行→30行）
  - scripts/: 5テーブルを1テーブル+参照リンクへ統合（54行→14行）
- **結果**: 521行→420行に削減（101行削減、19.4%減）
- **適用条件**: Progressive Disclosure対象の詳細情報が肥大化した場合
- **発見日**: 2026-01-20

### [Skill] 大規模DRYリファクタリング

- **状況**: SKILL.md 481行、interview-user.md 398行と肥大化
- **アプローチ**:
  - SKILL.md: 詳細ワークフローをreferencesに委譲、エントリポイントと参照のみに
  - orchestration-guide.md: 実行モデル重複をworkflow-patterns.mdへの参照に
  - interview-user.md: 質問テンプレートをinterview-guide.mdへの参照に
- **結果**: SKILL.md 69%削減（481→149行）、interview-user.md 52%削減（398→191行）
- **適用条件**: 300行超のファイルで詳細とサマリーが混在している場合
- **発見日**: 2026-01-24

### [Skill] クロススキル・マルチスキル・外部CLI拡張の3軸同時設計

- **状況**: skill-creator v10.0.0で3つの大機能（クロススキル依存関係、外部CLIエージェント、マルチスキル同時設計）を同時追加
- **アプローチ**:
  - 各機能を独立したエージェント（resolve-skill-dependencies / delegate-to-external-cli / design-multi-skill）に分離
  - 共通のインターフェースをinterview-result.jsonスキーマの拡張フィールドとして定義
  - select-resources.mdの選択マトリクス（4.1.7 / 4.1.8）を追加して既存パイプラインに統合
  - 静的依存グラフ（skill-dependency-graph.json）とランタイム設定（externalCliAgents）を明確に分離
  - Meshパターンは単方向DAGとして表現（参照タイプ分離で双方向に見える関係を実現）
- **結果**: 既存のPhaseパイプラインを壊さず3つの大機能を統合。エージェント間の責務が明確で相互干渉なし
- **適用条件**: 既存スキルに複数の独立した大機能を同時追加する場合
- **教訓**:
  - スキーマを先に定義してからエージェントを実装すると整合性が高い
  - 新機能のインタビューPhaseにはスキップ条件を付けてユーザー負担を軽減する
  - セキュリティ面では `execFileSync` + 引数配列（シェルインジェクション防止）が必須
  - 4エージェント並列レビュー（16思考法）で設計矛盾を早期発見できた
- **発見日**: 2026-02-13
- **関連バージョン**: v10.0.0

### [Phase12] Phase仕様書の成果物名厳密化

- **状況**: Phase 12実行時に仕様書と異なるファイル名で成果物を生成
- **アプローチ**:
  - Phase仕様書の成果物セクションにファイル名パターンを明記
  - 実行前に成果物一覧を確認するチェックリストを追加
- **結果**: 仕様書どおりの成果物が生成され、検証が容易に
- **適用条件**: Phase実行時、特に複数成果物を持つPhase
- **発見日**: 2026-01-22
- **関連タスク**: SHARED-TYPE-EXPORT-01

### [Phase12] スキル間ドキュメント整合性の定期確認

- **状況**: task-specification-creatorのSKILL.mdとreferences/artifact-naming-conventions.mdでPhase 12成果物リストが不整合
- **アプローチ**:
  - SKILL.mdの成果物定義を正とし、references/を同期
  - 改善作業時に関連ドキュメントの整合性を確認
- **結果**: artifact-naming-conventions.mdにPhase 12の3成果物（implementation-guide.md, documentation-changelog.md, unassigned-task-report.md）を追加
- **適用条件**: スキル改善時、バージョンアップ時
- **発見日**: 2026-01-22
- **関連タスク**: SHARED-TYPE-EXPORT-01

### [Phase12] 成果物実体と `phase-12-documentation.md` 状態の二重突合

- **状況**: `outputs/phase-12` の必須成果物は全件存在するが、`phase-12-documentation.md` のステータスが `pending` のまま残るドリフトが発生
- **アプローチ**:
  - Task 12-1〜12-5 の成果物実在を先に機械確認
  - `verify-all-specs` と `validate-phase-output` を再実行し、PASS値を固定
  - 最後に `phase-12-documentation.md` の `ステータス` と完了チェックリスト2箇所を同期
- **結果**: 「成果物はあるが仕様書上は未完了」という誤判定を防止し、Phase 12の完了状態を一貫化
- **適用条件**: 再監査・追補で成果物追加後に仕様書状態が取り残される可能性がある場合
- **発見日**: 2026-03-05
- **関連タスク**: TASK-FIX-SKILL-EXECUTOR-AUTHKEY-DI-001

### [Phase12] workflow index / artifacts 二重同期（TASK-UI-02）

- **状況**: `phase-12-documentation.md` と `artifacts.json` は completed 側へ揃っていても、`outputs/artifacts.json` 未作成や `index.md` 未再生成で workflow 全体が「未実施」に見えることがある
- **アプローチ**:
  - `artifacts.json` 更新後に `outputs/artifacts.json` を同内容で同期する
  - `node .claude/skills/task-specification-creator/scripts/generate-index.js --workflow <workflow-path> --regenerate` を実行し、`index.md` の Phase 1-12 / 13 表示を再生成する
  - `phase-12-documentation.md` / `artifacts.json` / `outputs/artifacts.json` / `index.md` を四点セットで突合する
- **結果**: 「成果物はあるが workflow index 上は未実施」というドリフトを防止し、再監査の初手で迷わなくなる
- **適用条件**: Phase 12 完了後、または再監査で workflow 状態表示に違和感がある場合
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-02-GLOBAL-NAV-CORE

### [Phase12] `generate-index` schema 互換監査 + 壊れた index の即時未タスク化

- **状況**: `node .claude/skills/task-specification-creator/scripts/generate-index.js --workflow <workflow-path> --regenerate` 実行後、workflow ごとの `artifacts.json` schema 差異により `index.md` が `undefined` 表示や全 Phase 未実施へ壊れることがある
- **アプローチ**:
  - `generate-index` 実行後に `index.md` の Phase 12/13 表示だけでなく、`undefined` 混入や成果物件数の崩れを即時確認する
  - `phase-12-documentation.md` / `artifacts.json` / `outputs/artifacts.json` / `index.md` を四点突合し、generator 出力を盲信しない
  - generator 側修正が current task の責務外なら、workflow は手動で正本へ戻し、汎用改善は `docs/30-workflows/unassigned-task/` に未タスク化する
  - `task-workflow.md` と `lessons-learned.md` に、手動復旧した事実と generator/schema 互換改善が別課題であることを同一ターンで記録する
- **結果**: completed workflow を自動再生成で再破壊する連鎖を止め、局所修復と汎用改善の責務分離を維持できる
- **適用条件**: `generate-index` 実行後の `index.md` が `artifacts.json` と一致しない場合、または workflow 間で `artifacts.json` schema 差異が疑われる場合
- **発見日**: 2026-03-10
- **関連タスク**: UT-IMP-TASK-SPEC-GENERATE-INDEX-SCHEMA-COMPAT-001

### [Phase12] 完了済み未タスク指示書の配置整合（残置防止）

- **状況**: 機能実装完了後も、対応済みの未タスク指示書が `docs/30-workflows/unassigned-task/` に残り、運用上「未完了」と誤認される
- **アプローチ**:
  - Phase 12完了時に、完了済みの未タスク指示書を `docs/30-workflows/completed-tasks/unassigned-task/` へ移管
  - `task-workflow.md` / 関連interfaces仕様書 / workflow index の参照パスを同時更新
  - `artifacts.json` と phase-12成果物（監査レポート含む）を最終整合チェック
- **結果**: 未タスク台帳の状態と実ファイル配置が一致し、完了/未完了の判定ミスを抑制
- **適用条件**: 未タスクを起票した機能タスクが完了し、Phase 12の文書化を実施するタイミング
- **発見日**: 2026-02-12
- **関連タスク**: UT-9B-H-003

### [Phase12] 未実施タスク配置ドリフト是正（completed-tasks/unassigned-task → unassigned-task）

- **状況**: 未実施タスク指示書が `docs/30-workflows/completed-tasks/unassigned-task/` に残り、`task-workflow.md` / 関連仕様書リンクと不整合になる
- **アプローチ**:
  - `completed-tasks/unassigned-task/` 配下の指示書をステータスで分類し、`未着手|未実施|進行中` は `docs/30-workflows/unassigned-task/` に配置
  - `task-workflow.md` と関連仕様（例: `api-ipc-agent.md`）の参照を `docs/30-workflows/unassigned-task/` に統一
  - `node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js` 実行でリンク整合を検証
- **結果**: 未タスク台帳と物理配置が一致し、Phase 12監査時の誤判定を防止
- **適用条件**: 未タスク再監査、完了済み移管作業、参照修正を同時に行うPhase 12
- **発見日**: 2026-02-20
- **関連タスク**: UT-FIX-SKILL-REMOVE-INTERFACE-001

### [Phase12] dual skill-root repository の canonical root + mirror sync

- **状況**: repository に `.claude/skills/...` と `.agents/skills/...` の二重 root があり、user は前者を正本として要求している一方、workflow や旧成果物が後者を参照している
- **アプローチ**:
  - 先に user 指定root を canonical root として固定し、system spec / skill 改善 / validator 実行もその root で行う
  - 完了前に `diff -qr` または `rsync --checksum` で mirror root を同期し、古い参照経路との drift を残さない
  - `spec-update-summary.md` / `documentation-changelog.md` / `skill-feedback-report.md` に canonical root と mirror sync の両方を記録する
- **結果**: user 指定の正本を守りつつ、既存 workflow が参照する mirror root も stale にしない Phase 12 運用を固定できる
- **適用条件**: skill root が複数ある repository、または `.claude` / `.agents` のような実体ミラーを併用する task
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-07-DASHBOARD-ENHANCEMENT

### [Architecture] 既存アダプターパターンの活用（新規API統合時）

- **状況**: システムプロンプトのLLM API統合時、仕様書ではVercel AI SDK使用を提案
- **アプローチ**:
  - 既存のLLMAdapterFactoryパターンを調査・活用
  - 新規SDKを追加せず、既存アダプター経由で4プロバイダー（OpenAI, Anthropic, Google, xAI）に対応
  - buildMessages()でシステムプロンプトをLLMMessage[]に変換
- **結果**: 既存アーキテクチャとの一貫性を維持、依存関係を最小化、54テスト全PASS
- **適用条件**: LLM機能追加時、外部API統合時
- **発見日**: 2026-01-23
- **関連タスク**: TASK-CHAT-SYSPROMPT-LLM-001

### [Phase12] システム仕様書への完了タスク記録

- **状況**: Phase 12 Task 2でシステム仕様書更新が必要
- **アプローチ**:
  - 該当するinterfaces-\*.mdに「完了タスク」セクションを追加
  - タスクID、概要、実装日、主要成果を記録
  - 「関連ドキュメント」に実装ガイドリンクを追加
- **結果**: タスク完了の追跡可能性が向上、後続開発者が実装履歴を把握可能
- **適用条件**: Phase 12実行時、機能追加完了時
- **発見日**: 2026-01-23
- **関連タスク**: TASK-CHAT-SYSPROMPT-LLM-001

### [Phase12] Phase 12 Task 2の見落とし防止

- **状況**: Phase 12 Task 2（システム仕様書更新）が実行されずにPhase 12完了とマークされた
- **アプローチ**:
  - phase-templates.mdのPhase 12完了条件に明示的チェックリスト追加
  - 【Phase 12-2 Step 1】等のプレフィックス付与で視認性向上
  - spec-update-workflow.mdへの参照リンクをテンプレート内に埋め込み
  - フォールバック手順セクションを追加
- **結果**: 2ステップ（タスク完了記録＋システム仕様更新）の実行漏れを防止
- **適用条件**: Phase 12実行時、特に複数サブタスクを持つPhase
- **発見日**: 2026-01-22
- **関連タスク**: UT-007 ChatHistoryProvider App Integration

### [Phase12] 未タスク参照リンクの実在チェック

- **状況**: `task-workflow.md` に未タスクを登録したが、`docs/30-workflows/unassigned-task/` に実体ファイルがなく参照切れになる
- **アプローチ**:
  - 未タスク登録後に `node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js` を実行
  - `missing > 0` の場合は Phase 12 を完了扱いにしない
  - 完了タスクへ移動した場合は `task-workflow.md` の参照先を `completed-tasks/` 側に更新
- **結果**: 未タスク探索時のリンク切れを事前に排除し、後続タスクの追跡性を維持
- **適用条件**: Phase 12で未タスクを新規作成・更新した場合、または完了移動を行った場合
- **発見日**: 2026-02-12
- **関連タスク**: UT-FIX-AGENTVIEW-INFINITE-LOOP-001

### [Phase12] 仕様書参照パスの実在チェック

- **状況**: Phase 12で更新対象仕様書に `api-ipc-skill.md` など非実在パスが残り、参照先を誤認した
- **アプローチ**:
  - Step 1-B開始前に、更新対象として列挙した仕様書パスを `test -f <path>` で全件検証する
  - 非実在パスを検出した場合は、同ドメインの正本（例: `interfaces-agent-sdk-skill.md`）へ即時置換する
  - 置換後に `generate-index.js` を再実行して索引を同期する
- **結果**: 参照正本の取り違えを防ぎ、Phase 12 Task 2 の更新漏れを削減
- **適用条件**: 仕様書更新対象ファイルを手動列挙するタスク全般
- **発見日**: 2026-02-14
- **関連タスク**: UT-FIX-IPC-RESPONSE-UNWRAP-001

### [Phase12] Phase 12 Step 1 検証スクリプトによる自動化

- **状況**: Phase 12 Step 1（必須タスク完了記録）が正しく実行されたか手動確認が困難
- **アプローチ**:
  - `validate-phase12-step1.js` スクリプトを作成し、必須要件を自動検証
  - 検証項目: 完了タスクセクション、実装ガイドリンク、変更履歴エントリ
  - SKILL.mdに検証コマンドを追加し、Phase 12完了前に実行を促す
- **結果**: 必須要件の漏れを自動検出、Phase 12完了前に問題を発見可能
- **適用条件**: Phase 12 Task 12-2 実行時、システム仕様書更新後の検証
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03
- **検証コマンド**: `node .claude/skills/task-specification-creator/scripts/validate-phase12-step1.js --workflow <dir> --spec <file>`

### [Phase12] 複数システム仕様書への横断的更新

- **状況**: 単一タスクが複数の仕様書に関連する場合の更新漏れ
- **アプローチ**:
  - 関連仕様書を事前にリストアップ（例: interfaces-rag-community-detection.md + architecture-monorepo.md）
  - 各仕様書に対して Phase 12 Step 1 検証スクリプトを実行
  - spec-update-record.md に全更新対象を明記
- **結果**: 関連する全仕様書に一貫した完了タスク記録と実装ガイドリンクを追加
- **適用条件**: アーキテクチャ横断的な実装タスク、型エクスポート/インポートパターン変更時
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03

### [Phase12] 実装差分ベース文書化（ファイル名誤記防止）

- **状況**: Phase 12の実装ガイド/レビュー資料に、実際には変更していないファイル名が混入しやすい
- **アプローチ**:
  - 文書作成前に `git diff --name-only` で変更対象ファイルを確定
  - `implementation-guide.md` と `final-review-report.md` の対象ファイル欄を差分一覧と突合
  - 差分に存在しないファイル名が出た場合は記載を削除し、実装事実に合わせて再記述
- **結果**: 文書と実装の不整合を防止し、Phase 12監査の再作業を削減
- **適用条件**: リファクタリング系タスクや大量ファイル編集タスクで、成果物に対象ファイル一覧を記載する場合
- **発見日**: 2026-02-14
- **関連タスク**: TASK-FIX-14-1-CONSOLE-LOG-MIGRATION

### [Phase12] 実装-仕様ドリフト再監査（数値・パス・文言）

- **状況**: Phase 12完了後の再監査で、仕様書のテスト件数・Preload公開先パス・エラーメッセージ表が実装とずれていた
- **アプローチ**:
  - テスト件数は再実行結果（CIログまたはローカル実測）を唯一の正として更新
  - `rg -n` で旧パス（例: `skill-file-api.ts`）や旧文言を横断検索し、関連仕様書を一括修正
  - 未タスク検出は raw 件数と確定件数を分離して記録し、既存未タスク管理との重複を除外
- **結果**: Phase 12成果物の監査再作業を削減し、実装事実と仕様の整合性を維持
- **適用条件**: IPC機能追加・ハンドラー追加など、仕様書更新ファイルが3件以上に跨るタスク
- **発見日**: 2026-02-19
- **関連タスク**: TASK-9A-B

### [Phase12] 仕様更新三点セット（quality/task-workflow/lessons-learned）

- **状況**: Phase 12で実装内容を1ファイルだけに反映すると、運用ルール・完了記録・教訓が分断されやすい
- **アプローチ**:
  - `quality-requirements.md` に「今後守るべき運用ルール」を追記
  - `task-workflow.md` に「今回何を実装し、どこで苦戦したか」を完了タスクとして記録
  - `lessons-learned.md` に「同種課題の簡潔解決手順（再利用手順）」を記録
  - 3ファイル更新後に `generate-index.js` を実行して索引を同期
- **結果**: 仕様の「ルール」「履歴」「再利用ノウハウ」が分離されず、後続タスクの調査コストを削減
- **適用条件**: テスト戦略・運用方針・ドキュメント運用が同時に変わるタスク（特にPhase 12 Step 2を伴う変更）
- **発見日**: 2026-02-19
- **関連タスク**: TASK-FIX-10-1-VITEST-ERROR-HANDLING
- **クロスリファレンス**: [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase12] spec-update-summary + artifacts二重台帳同期

- **状況**: `documentation-changelog.md` は存在するが、`spec-update-summary.md` 未作成や `artifacts.json` / `outputs/artifacts.json` 非同期が発生しやすい
- **アプローチ**:
  - `phase-12-documentation.md` の成果物表と `outputs/phase-12/` 実体を1対1で突合する
  - `spec-update-summary.md` を Step 1-A〜3 の証跡ファイルとして必須作成する
  - `artifacts.json` と `outputs/artifacts.json` を同一内容に同期し、completed成果物の参照切れをゼロ化する
  - 同期後に `validate-phase-output.js` と `verify-all-specs.js` を再実行する
- **結果**: Phase 12 完了判定の再現性が上がり、成果物不足・台帳ズレの再発を防止
- **適用条件**: 仕様書修正のみタスクを含む全ての Phase 12
- **発見日**: 2026-02-24
- **関連タスク**: UT-IPC-DATA-FLOW-TYPE-GAPS-001

### [Phase12] 実装ガイド2パート要件ギャップの即時是正

- **状況**: `implementation-guide.md` は存在するが、Part 1 の日常例え・理由先行説明、Part 2 の型/API/エッジケースが不足していることがある
- **アプローチ**:
  - Part 1 は「なぜ必要か」を先に書き、日常生活の例えを必須で入れる
  - Part 2 は最小でも「型定義」「APIシグネチャ」「エラーハンドリング」「設定項目」を明示する
  - `phase-12-documentation.md` の完了チェックと `implementation-guide.md` 本文を同一コミットで同期する
- **結果**: Task 1 要件未達による差し戻しを防ぎ、Phase 12 完了判定の再現性が上がる
- **適用条件**: Phase 12 Task 1 を含む全タスク（特に再監査タスク）
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-IPC-RESPONSE-CONSISTENCY-001

### [Phase12] 仕様書作成タスクの `spec_created` 状態判定

- **状況**: Phase 12 Step 1-B で、実装未着手タスクまで `completed` と記録しやすい
- **アプローチ**:
  - タスクを「実装完了」と「仕様書作成済み（未実装）」に分岐して判定
  - 実装完了は `completed`、仕様書のみは `spec_created` を使用
  - `tasks/index.md`・`completed-task/*.md`・関連workflow indexの3点を同時更新
- **結果**: 実装進捗と仕様進捗の状態混同を防止
- **適用条件**: Phase 12でドキュメント成果物のみ先行して完了するタスク
- **発見日**: 2026-02-19
- **関連タスク**: TASK-9A-C

### [Phase12] IPCドキュメント契約同期（Main/Preload準拠）

- **状況**: `ipc-documentation.md` が存在しても、`skillHandlers.ts` / `skill-api.ts` の引数・戻り値契約とズレることがある
- **アプローチ**:
  - Main (`skillHandlers.ts`) と Preload (`skill-api.ts`) を一次情報に固定し、チャネルごとの入力/出力/エラー契約を表で同期する
  - 特に Profile A/B/C の返却形式と `sanitizeErrorMessage()` の適用範囲を明示する
  - 同期後に契約テスト（Main contract + Preload contract）を再実行して回帰を確認する
- **結果**: API利用者の誤実装を防ぎ、Phase 12 再監査時の差し戻しを減らせる
- **適用条件**: IPCハンドラ・Preload契約を更新したタスクの Phase 12 Step 2
- **発見日**: 2026-02-27
- **関連タスク**: UT-FIX-SKILL-IPC-RESPONSE-CONSISTENCY-001

### [Phase12] IPC追加時の登録配線突合（handler/register/preload）

- **状況**: 新規IPCハンドラを実装しても `ipc/index.ts` 側の登録が漏れ、実行時にチャネルが無効化されることがある
- **アプローチ**:
  - `handler` 実装、`register` 配線、`preload` 公開を1セットで確認する
  - `rg -n "register<Feature>Handlers|skill:<feature>:"` で登録とチャネルの両方を機械確認する
  - 仕様書は Preload API 実装名を正本として同期する（命名ドリフト防止）
- **結果**: 「実装済みなのに起動しない」類のIPC欠陥を早期に検出できる
- **適用条件**: IPCチャネル新規追加、または既存チャネルを専用ハンドラへ分割するタスク
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J

### [IPC] サービスバレル公開整合チェック（UT-IMP-SKILL-CHAIN-BARREL-EXPORT-CONSISTENCY-001）

- **状況**: `registerAllIpcHandlers` の配線を修正して機能は復旧したが、依存サービス（`SkillChainStore` / `SkillChainExecutor`）が `services/skill/index.ts` から未公開のまま残り、直接 import が固定化した
- **アプローチ**:
  - IPC登録修正時に `services/<domain>/index.ts` の export 更新有無を同時確認する
  - `rg -n "services/skill/SkillChain(Store|Executor)|from \"../services/skill\"" apps/desktop/src/main` で直接 import とバレル import を機械比較する
  - 今回Waveで対応しない場合は Phase 12 Task 4 で未タスク化し、`task-workflow.md` の関連未タスクへリンクする
- **結果**: 機能修復と設計整合性の境界を分離して管理でき、後続Waveでの再実装コストを抑制できる
- **適用条件**: IPCハンドラ追加・登録修正時に新規サービス依存を導入したタスク
- **発見日**: 2026-03-03
- **関連タスク**: UT-IMP-SKILL-CHAIN-BARREL-EXPORT-CONSISTENCY-001

### [Testing] E2EテストでのARIA属性ベースセレクタ優先

- **状況**: Playwrightでドロップダウンコンポーネントをテストする際のセレクタ選定
- **アプローチ**:
  - CSSクラスやdata-testid属性の代わりにARIA属性（`role="combobox"`, `role="listbox"`, `role="option"`）を優先使用
  - `page.getByRole()` APIで要素を取得
  - アクセシビリティ検証とE2Eテストを同時に実現
- **結果**: アクセシビリティ準拠の確認とテスト安定性の両立（CSSクラス変更に強い）
- **適用条件**: UI E2Eテスト、特にフォームコントロールやナビゲーション要素
- **発見日**: 2026-02-02
- **関連タスク**: TASK-8C-B

### [Testing] E2Eヘルパー関数による操作シーケンスの分離

- **状況**: 複数のE2Eテストで同じ操作シーケンス（スキル選択、ドロップダウン開閉など）が重複
- **アプローチ**:
  - 共通操作をヘルパー関数として抽出（`openSkillDropdown()`, `selectSkillByName()`等）
  - テストファイル先頭またはユーティリティファイルに配置
  - 各テストケースはヘルパー関数を呼び出して操作を実行
- **結果**: DRY原則の適用、保守性向上、テスト可読性向上
- **適用条件**: E2Eテストで3回以上繰り返される操作シーケンス
- **発見日**: 2026-02-02
- **関連タスク**: TASK-8C-B

### [Testing] E2E安定性対策3層アプローチ

- **状況**: E2Eテストでフレーキー（不安定）なテスト結果が発生
- **アプローチ**:
  - 層1: 明示的待機（`waitForSelector`, `waitForFunction`）
  - 層2: UI安定化待機（アニメーション完了、ローディング状態解消）
  - 層3: DOMロード待機（`networkidle`, `domcontentloaded`）
- **結果**: テスト成功率100%、CI環境での安定動作
- **適用条件**: アニメーション、非同期データ取得、動的コンテンツを含むE2Eテスト
- **発見日**: 2026-02-02
- **関連タスク**: TASK-8C-B

### [Auth] 既実装済み修正の発見パターン（AUTH-UI-001）

- **状況**: バグ修正タスクで、調査中に既に修正が実装済みであることを発見
- **アプローチ**:
  - Step 1: 問題の再現を試みる前に、まず関連コードを詳細に調査
  - Step 2: 修正コードの存在確認（z-index、フォールバック処理、状態更新フロー）
  - Step 3: 既存実装の動作検証で問題解決を確認
- **結果**: 不要な実装作業を回避、Phase 12の文書化と知識共有に注力
- **適用条件**: バグ修正タスク、Issue報告から時間が経過している場合
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001

### [Testing] テスト環境問題と実装コード切り分けパターン（AUTH-UI-001）

- **状況**: 33件のテストが失敗しているが、実装コード自体は正常動作
- **アプローチ**:
  - Step 1: テスト失敗のエラーメッセージを分析（`handler not registered`等）
  - Step 2: 本番環境での動作確認で実装の正常性を検証
  - Step 3: テスト環境問題として切り分け、未タスク（UT-AUTH-001）として登録
- **結果**: 実装の品質担保とテスト環境問題の適切な分離
- **適用条件**: テスト失敗がモック環境に起因する場合、本番動作が正常な場合
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001, UT-AUTH-001

### [UI] React Portalによるz-index問題解決パターン（AUTH-UI-001）

- **状況**: ドロップダウンメニューが他の要素の下に隠れる（z-indexだけでは解決不可）
- **アプローチ**:
  - 問題: CSSのスタッキングコンテキストにより、子要素のz-indexが親の範囲内に制限される
  - 解決: React Portalで`document.body`直下にレンダリングし、DOM階層から切り離す
  - 実装: `createPortal(<DropdownContent className="z-[9999]" />, document.body)`
- **結果**: z-[9999]がグローバルに機能し、確実に最前面表示
- **適用条件**: モーダル、ドロップダウン、ツールチップ等のオーバーレイUI
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001

### [Auth] Supabase認証状態変更後の即時UI更新パターン（AUTH-UI-001）

- **状況**: 認証状態変更（リンク/解除）後にUIが即座に更新されない
- **アプローチ**:
  - 問題: `onAuthStateChange`イベント後にプロバイダー情報を再取得していない
  - 解決: 認証状態変更時に`fetchLinkedProviders()`を明示的に呼び出す
  - 実装場所: `authSlice.ts`の認証イベントハンドラ内（行342-345付近）
- **結果**: OAuth連携操作後に即座にUI状態が反映
- **適用条件**: Supabase Auth + Zustand状態管理の組み合わせ
- **発見日**: 2026-02-04
- **関連タスク**: AUTH-UI-001

### [Auth] OAuthコールバックエラーパラメータ抽出パターン（TASK-FIX-GOOGLE-LOGIN-001）

- **状況**: OAuthコールバックURL内のエラーパラメータを検出してUIに反映したい
- **アプローチ**:
  - 問題: OAuth implicit flowではエラー情報がURLフラグメント(`#error=...`)に含まれる
  - 解決: `url.substring(url.indexOf('#') + 1)`でフラグメント抽出後、URLSearchParamsでパース
  - 実装: `parseOAuthError()`関数を作成し、`handleAuthCallback`内で呼び出す
- **結果**: ユーザーがOAuthをキャンセルした場合のエラーを検出し、適切なエラーメッセージを表示
- **適用条件**: OAuth implicit flow、カスタムプロトコルコールバック処理
- **発見日**: 2026-02-05
- **関連タスク**: TASK-FIX-GOOGLE-LOGIN-001

### [Auth] Zustandリスナー二重登録防止パターン（TASK-FIX-GOOGLE-LOGIN-001）

- **状況**: initializeAuthが複数回呼ばれるとリスナーが重複登録される
- **アプローチ**:
  - 問題: React Strict ModeやHot Reloadで初期化関数が複数回実行される
  - 解決: モジュールスコープの`authListenerRegistered`フラグで登録状態を追跡
  - テスト対応: `resetAuthListenerFlag()`エクスポート関数で各テスト前にリセット
- **結果**: リスナーの二重登録を防止し、認証状態変更の重複処理を回避
- **適用条件**: Electron IPC + Zustandでの認証状態管理
- **発見日**: 2026-02-05
- **関連タスク**: TASK-FIX-GOOGLE-LOGIN-001

### [IPC] IPC経由のエラー情報伝達設計パターン（TASK-FIX-GOOGLE-LOGIN-001）

- **状況**: Main ProcessのエラーをRenderer側のUIに伝える必要がある
- **アプローチ**:
  - 問題: 既存のIPCイベントペイロードにエラー情報フィールドがない
  - 解決: ペイロード型に`error`, `errorCode`フィールドを追加し、既存のイベントで送信
  - 型拡張: `AuthState`インターフェースに`errorCode?: AuthErrorCode`を追加
- **結果**: 新規チャネル追加なしで、既存の`AUTH_STATE_CHANGED`イベントでエラー伝達
- **適用条件**: Electron IPC設計、エラーハンドリング拡張
- **発見日**: 2026-02-05
- **関連タスク**: TASK-FIX-GOOGLE-LOGIN-001

### IPC Bridge API統一時のテストモック設計パターン（TASK-FIX-5-1）

- **状況**: `window.skillAPI` と `window.electronAPI.skill` の二重定義を統一する際、テストモックの再設計が必要（623行→1092行に膨張）
- **アプローチ**:
  - `vi.hoisted()` でモック定義をファイルスコープの巻き上げ位置に配置
  - フィクスチャファクトリ関数でテストごとにリセット可能なモックを生成
  - パスエイリアス（`@/`）と相対パスの両方に対応するモック配布パターン
- **結果**: テストの保守性向上、モック二重定義の解消、210テスト全PASS
- **適用条件**: Electron Preload APIの変更、IPC Bridge層のリファクタリング
- **発見日**: 2026-02-06
- **関連タスク**: TASK-FIX-5-1-SKILL-API-UNIFICATION
- **関連仕様書**: [architecture-implementation-patterns.md S2](.claude/skills/aiworkflow-requirements/references/architecture-implementation-patterns.md)

### セッション間での仕様書編集永続化検証パターン（TASK-FIX-5-1）

- **状況**: 前セッションで10件の仕様書修正を完了と報告したが、8件がディスクに永続化されていなかった
- **アプローチ**:
  - 大量編集後は `git diff --stat` で変更ファイル数と期待値の一致を検証
  - PostToolUseフック（Prettier/ESLint）によるファイル変更で Edit の `old_string` 不一致が発生する可能性を認識
  - 重要な編集は直後に `git diff <file>` で実際の差分を確認
- **結果**: 全8件の未永続化を発見し再適用、仕様書と実装の完全な整合性を達成
- **適用条件**: 複数セッションにまたがる仕様書更新、Linterフックが有効な環境
- **発見日**: 2026-02-06
- **関連タスク**: TASK-FIX-5-1-SKILL-API-UNIFICATION
- **関連ルール**: [06-known-pitfalls.md P11](.claude/rules/06-known-pitfalls.md)

### Phase 1仕様書作成時の依存仕様書マトリクスパターン（TASK-FIX-5-1）

- **状況**: Phase 1作成時にaiworkflow-requirementsの関連仕様書参照が不足し、後から2コミットで19件修正が必要
- **アプローチ**:
  - Phase 1作成時に「仕様書依存マトリクス」を明示的に作成
  - task-specification-creatorとaiworkflow-requirementsの両方のreferences/を検索し、関連する全仕様書を特定
  - 各Phase仕様書に必要な参照リンクを漏れなく追加
- **結果**: 後付け修正のコスト（2コミット、19件修正）を事前に防止可能
- **適用条件**: 複数の仕様書体系を持つプロジェクトでのタスク仕様書作成時
- **発見日**: 2026-02-06
- **関連タスク**: TASK-FIX-5-1-SKILL-API-UNIFICATION

### [Auth] Supabase SDK自動リフレッシュ競合防止パターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: Supabase SDKの`autoRefreshToken: true`（デフォルト）とカスタムスケジューラーが同時にリフレッシュを試みる
- **アプローチ**:
  - 問題: 2つのリフレッシュ処理が同時実行されると、一方が無効なトークンで実行されエラーになる
  - 解決: `supabaseClient.ts`で`autoRefreshToken: false`を設定し、カスタムスケジューラーに完全に委譲
  - 排他制御: `_isRefreshing`フラグでスケジューラー内の二重実行も防止
- **結果**: リフレッシュ処理の衝突を完全に排除、リトライ戦略を自由にカスタマイズ可能に
- **適用条件**: 外部SDK（Supabase, Firebase等）のデフォルト自動処理をカスタム実装で置き換える場合
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Auth] setTimeout方式 vs setInterval方式の選択パターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: セッションリフレッシュのスケジューリング方式選定
- **アプローチ**:
  - setIntervalの問題: 固定間隔実行のため、リフレッシュ成功で新しいexpiresAtが変わっても間隔が変わらない
  - setTimeout選択理由: リフレッシュ成功時に`reset(newExpiresAt)`で新しいタイマーを設定でき、動的な間隔調整が可能
  - 追加利点: `stop()`で確実にタイマークリア可能、メモリリーク防止
- **結果**: 毎回新しいexpiresAtに基づいた正確なスケジューリングを実現
- **適用条件**: スケジュール間隔が動的に変わる定期処理
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Testing] vi.useFakeTimers + flushPromisesテストパターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: setTimeout + async/await が組み合わさったコードのテストが困難
- **アプローチ**:
  - 問題: `vi.runAllTimersAsync()`はリフレッシュ成功→新タイマー設定→再発火の無限ループを引き起こす
  - 解決: `vi.advanceTimersByTime(ms)` + `flushPromises()`を組み合わせて段階的に制御
  - `flushPromises()`: `for (let i = 0; i < 10; i++) await Promise.resolve()`でmicrotaskキューを消化
  - テスト手順: タイマー進行→Promise解決→アサーション を1ステップずつ実行
- **結果**: 26テスト全PASS、96.15%カバレッジ達成。タイマーと非同期処理の両方を正確にテスト可能
- **適用条件**: setTimeout/setInterval + Promise/async-awaitが混在するコードのユニットテスト
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Auth] Callback DIによるテスタブル設計パターン（TASK-AUTH-SESSION-REFRESH-001）

- **状況**: TokenRefreshSchedulerからSupabase, SecureStorage, BrowserWindowへの依存を分離したい
- **アプローチ**:
  - 問題: クラス内で直接`supabase.auth.refreshSession()`を呼ぶとモックが困難
  - 解決: `TokenRefreshCallbacks`インターフェースで`onRefresh`, `onFailure`, `onSuccess`をDI
  - スケジューラーは「いつ実行するか」のみに責務を限定、「何を実行するか」は呼び出し側が決定
  - authHandlers.tsのstartTokenRefreshScheduler()でコールバック実装を注入
- **結果**: スケジューラーのテストにSupabaseモック不要、テスト対象が明確に分離
- **適用条件**: 外部サービス呼び出しを含むスケジューラー/タイマー系処理
- **発見日**: 2026-02-06
- **関連タスク**: TASK-AUTH-SESSION-REFRESH-001

### [Testing] mockReturnValue vs mockReturnValueOnce のテスト間リーク防止パターン（TASK-FIX-17-1）

- **状況**: IPCハンドラーのセキュリティテストで特殊な戻り値を設定する必要があった
- **アプローチ**:
  - 問題: `mockReturnValue` で設定したモック戻り値が後続テストに漏れ、テスト間で状態が共有される
  - 解決: `mockReturnValueOnce` で1回限りのモック設定にする
  - 再初期化: `beforeEach` でモック関数をデフォルト状態にリセット
- **結果**: テスト間の状態分離が実現し、独立したテスト実行が可能に
- **適用条件**: 同一モック関数に対して複数の異なる戻り値パターンをテストする場合
- **発見日**: 2026-02-09
- **関連タスク**: TASK-FIX-17-1-SKILL-SCAN-HANDLER
- **クロスリファレンス**: [06-known-pitfalls.md#P23](../../.claude/rules/06-known-pitfalls.md)

### [IPC/Electron] 横断的セキュリティバイパス検出パターン（UT-FIX-5-3）

- **状況**: IPC APIでセキュリティ検証をバイパスする直接呼び出しが存在（preloadでの`ipcRenderer.send/on`直接使用）
- **アプローチ**:
  - Step 1: `grep -rn "ipcRenderer.send\|ipcRenderer.on" <preload-dir>/` で直接呼び出しを検出
  - Step 2: 検出したチャネル名がホワイトリストに登録されているか確認
  - Step 3: `safeInvoke()` 経由でない呼び出しを未タスクとして登録
  - Step 4: 検出された問題ごとに修正方針（AbortController統合、型定義追加等）を記録
- **結果**: セキュリティ検証バイパスを早期発見、未タスク化で追跡可能に
- **適用条件**: Electron IPC設計、Phase 10アーキテクチャレビュー時、Preloadスクリプト変更時
- **発見日**: 2026-02-09
- **関連タスク**: UT-FIX-5-3-PRELOAD-AGENT-ABORT
- **クロスリファレンス**: [04-electron-security.md](../../.claude/rules/04-electron-security.md), [06-known-pitfalls.md](../../.claude/rules/06-known-pitfalls.md)

### [DI/Architecture] Setter Injectionパターン（遅延初期化DI）（TASK-FIX-7-1）

- **状況**: BrowserWindow等の外部リソースを必要とする依存オブジェクトは、Constructor Injectionで対応できない
- **アプローチ**:
  - 問題: Facadeサービス（SkillService）生成時点で、依存先（SkillExecutor）がまだ初期化できない（mainWindow未生成）
  - 解決: `setXxx(dependency)` Setterメソッドで、外部リソース準備後に依存オブジェクトを注入
  - 検証: 実行メソッド（`executeSkill`）呼び出し時に、依存オブジェクトの存在を検証（未設定時はエラー）
  - 実装例: `SkillService.setSkillExecutor(executor)` で、mainWindow生成後にSkillExecutorを注入
- **結果**: 初期化タイミングが異なる依存オブジェクトを安全に注入可能。Facadeパターンとの併用でレイヤー分離を維持
- **適用条件**: 依存オブジェクトの生成に外部リソース（BrowserWindow、IPC接続等）が必要な場合
- **発見日**: 2026-02-11
- **関連タスク**: TASK-FIX-7-1-EXECUTE-SKILL-DELEGATION
- **クロスリファレンス**: [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md#setter-injection-パターンtask-fix-7-1-2026-02-11実装)

### [Persist] persist復旧の3段ガード（Set/Array二方向シリアライズ）（TASK-FIX-SETTINGS-PERSIST-ITERABLE-HARDENING-001）

- **状況**: Zustand `persist` ミドルウェアで `localStorage` から復元する際、破損データ（null/undefined/number/object）により `object is not iterable` エラーが発生する。`Set` を `JSON.stringify` すると `{}` になり、復元時に `new Set(storedValue)` で空オブジェクトを展開しようとして失敗する
- **アプローチ**:
  - Step 1: `Array.isArray(value)` で配列であることを確認（null/undefined/number/object を排除）
  - Step 2: `.filter(v => typeof v === "string")` で各要素が文字列であることを検証（混在型を排除）
  - Step 3: 上記いずれかで失敗した場合、安全な既定値（空配列 `[]` / 空Set `new Set()`）にフォールバック
  - シリアライズ: `Set` → `Array.from(set)` で保存、復元時は `new Set(validatedArray)` で復元
- **結果**: 破損値（null/undefined/number/object/空オブジェクト `{}`）を全て安全にフォールバックし、Set/Array の二方向シリアライズを統一。`customStorage` アダプターで復旧ロジックを一元管理
- **適用条件**: `persist` で `Set` / `Map` / カスタム型を `JSON.stringify` する場合。特に `electron-store` や `localStorage` から復元するケース
- **発見日**: 2026-03-07
- **関連タスク**: TASK-FIX-SETTINGS-PERSIST-ITERABLE-HARDENING-001
- **関連Pitfall**: P19（型キャストによる実行時検証バイパス）、P48（non-null assertionによる安全性偽装）

### [IPC/Type] IPC層とサービス層の型変換パターン（TASK-FIX-7-1）

- **状況**: IPC層（Preload/Handler）とサービス層で異なる型定義を使用しており、型変換が必要
- **アプローチ**:
  - 問題: IPC層では`Skill`型（UI向け汎用型）、サービス層では`SkillMetadata`型（実行エンジン向け詳細型）を使用
  - 解決: IPCハンドラー内で明示的な型変換ロジックを実装し、型安全性を確保
  - 変換例: `Skill` → `SkillMetadata` への変換時、必須フィールドの存在確認とデフォルト値設定を行う
  - 型定義の配置: 共通型は`@repo/shared`に配置し、レイヤー固有の型は各層で定義
- **結果**: レイヤー間の型の責務が明確になり、型安全な通信が実現
- **適用条件**: IPC通信でRenderer/Main間でデータ構造が異なる場合、Store型とPreload型が異なる場合
- **発見日**: 2026-02-11
- **関連タスク**: TASK-FIX-7-1-EXECUTE-SKILL-DELEGATION
- **クロスリファレンス**: [interfaces-agent-sdk-executor.md](../../aiworkflow-requirements/references/interfaces-agent-sdk-executor.md)

### [Testing/DI] DIテストモック大規模修正パターン（TASK-FIX-7-1）

- **状況**: 新しい依存オブジェクトをDIで追加すると、既存の全テストファイルにモック追加が必要になる
- **アプローチ**:
  - Step 1: `grep -rn "new TargetClass\|TargetClass(" src/` で影響範囲を事前調査
  - Step 2: 各テストファイルに対象モックを定義（`mockDependency = { method: vi.fn() }`）
  - Step 3: `beforeEach`で`mockDependency.method.mockResolvedValue()`をリセット
  - Step 4: 標準モック構成をテストユーティリティとしてドキュメント化
  - 例: SkillExecutorにSkillServiceを追加した際、5つのテストファイルにmockSkillServiceを追加
- **結果**: 既存テストの網羅的な更新が完了し、モック構成が統一される
- **適用条件**: Constructorに新しい依存オブジェクトを追加する場合、Setter Injectionで新しい依存を追加する場合
- **発見日**: 2026-02-11
- **関連タスク**: TASK-FIX-7-1-EXECUTE-SKILL-DELEGATION
- **クロスリファレンス**: [06-known-pitfalls.md#P21](../../.claude/rules/06-known-pitfalls.md)

### [Phase12] 横断的問題の追加検証パターン（UT-FIX-5-3）

- **状況**: Phase 10レビューで検出した問題が、他ファイルにも同様に存在する可能性がある
- **アプローチ**:
  - Step 1: Phase 10で検出した問題パターンを正規表現で表現
  - Step 2: `grep -rn "<pattern>" <project-root>/` でプロジェクト全体を検索
  - Step 3: 同様のパターンが見つかった場合、関連タスクとして追加検出
  - Step 4: 追加検出された問題はPhase 12の未タスク検出に含める
- **結果**: 単一ファイル修正に留まらず、横断的な品質改善を実現
- **適用条件**: Phase 10で設計パターン違反を検出した場合、Phase 12の未タスク検出時
- **発見日**: 2026-02-09
- **関連タスク**: UT-FIX-5-3-PRELOAD-AGENT-ABORT
- **クロスリファレンス**: [05-task-execution.md#Task 4](../../.claude/rules/05-task-execution.md), [06-known-pitfalls.md#P24](../../.claude/rules/06-known-pitfalls.md)

### [Testing] 統合テストでの依存サービスモック漏れ防止パターン（TASK-FIX-15-1）

- **状況**: IPCハンドラーの実行パスがSkillServiceからSkillExecutorに変更され、既存の統合テストが失敗
- **アプローチ**:
  - 問題: ハンドラーが呼び出す依存サービスが変更されても、テストのモック設定が古いまま
  - 解決: 実装変更時に統合テストのモック対象も同時に更新する
  - 実装パターン: `vi.mock("../../services/skill/SkillExecutor")` で新しい依存をモック
  - 検証: モックメソッド（`mockExecuteMethod`, `mockAbortMethod`等）を事前定義し、テストで呼び出し確認
- **結果**: 実装の実行パス変更に追従し、テストが正常動作
- **適用条件**: ハンドラーやサービスの内部依存を変更する際、関連する統合テスト全てを更新
- **発見日**: 2026-02-10
- **関連タスク**: TASK-FIX-15-1-EXECUTE-HANDLER-ROUTING
- **クロスリファレンス**: [06-known-pitfalls.md#P25](../../.claude/rules/06-known-pitfalls.md)

### [IPC] 入力バリデーション統一パターン - whitespace対策（TASK-FIX-15-1）

- **状況**: ユーザー入力（prompt等）に空白のみの文字列が渡されるとサービスエラーになる
- **アプローチ**:
  - 問題: `prompt === ""` のみのチェックでは空白のみ（`"   "`）を検出できない
  - 解決: `prompt.trim() === ""` でホワイトスペースのみの入力を拒否
  - 正規化: リクエスト構築時に `prompt.trim()` で前後の空白を削除
  - エラーメッセージ: `"prompt must be a non-empty string"` で明確なバリデーションエラーを返す
- **結果**: 空白のみ入力がバリデーション段階で拒否され、サービス層に到達しない
- **適用条件**: IPCハンドラーでユーザー入力文字列を受け取る場合
- **発見日**: 2026-02-10
- **関連タスク**: TASK-FIX-15-1-EXECUTE-HANDLER-ROUTING
- **クロスリファレンス**: [06-known-pitfalls.md#P26](../../.claude/rules/06-known-pitfalls.md)

### [IPC] IPC機能開発ワークフローパターン（TASK-9B-H）

- **状況**: Electron IPC チャンネルの新規追加（サービス層のメソッドをRenderer側に公開する）
- **アプローチ**:
  1. **チャンネル定数定義**: `channels.ts` に `IPC_CHANNELS` 定数を追加し、同ファイルのホワイトリスト配列にも登録
  2. **Main側ハンドラー作成**: `validateIpcSender` でsender検証 + 引数バリデーション + サービス層呼び出し + エラーサニタイズの4段構成
  3. **Preload API作成**: `safeInvoke`/`safeOn` を使用し、チャンネル名は必ず `IPC_CHANNELS` 定数を参照。インターフェース定義を型安全に設計
  4. **preload/index.ts統合**: 4箇所を同時更新（import文、electronAPIオブジェクト、exposeInMainWorld、fallback定義）
  5. **types.ts型定義追加**: `ElectronAPI` インターフェースと `Window` グローバル宣言の両方に型を追加
  6. **ipc/index.ts登録**: `registerAllIpcHandlers` に新規ハンドラーの register/dispose を追加
- **セキュリティチェック**:
  - 全ハンドラーで `validateIpcSender` によるsender検証
  - チャンネル名のホワイトリスト管理（`channels.ts` の配列に登録されていないチャンネルは `safeInvoke` で拒否）
  - エラーサニタイズ（内部スタックトレースをRenderer側に漏洩しない）
- **テスト設計**:
  - ハンドラー登録/解除テスト（`ipcMain.handle`/`removeHandler` の呼び出し確認）
  - 正常系テスト（サービス層への引数の受け渡し、戻り値のフォーマット）
  - 異常系テスト（バリデーションエラー、サービス層エラー、sender検証失敗）
  - 統合テスト（ハンドラー登録→実行→解除の一連のフロー）
- **結果**: 6段階のチェックリストにより、IPC チャンネル追加時の漏れを防止。セキュリティ3層モデル（ホワイトリスト + sender検証 + エラーサニタイズ）を標準化
- **適用条件**: Electron IPC チャンネルの新規追加、既存サービスのRenderer公開
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-H-SKILL-CREATOR-IPC
- **クロスリファレンス**: [04-electron-security.md](../../.claude/rules/04-electron-security.md), [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)
- **関連仕様書**:
  - [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md) - IPC実装パターン（Setter Injection、型変換、テストモック等）
  - [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md) - Electron IPCセキュリティ仕様（ホワイトリスト管理、sender検証、エラーサニタイズ）
  - [api-ipc-agent.md](../../aiworkflow-requirements/references/api-ipc-agent.md) - IPC API仕様（チャンネル定義、ハンドラー登録、Preload Bridge設計）

### [IPC] IPCハンドラライフサイクル管理パターン（UT-FIX-IPC-HANDLER-DOUBLE-REG-001）

- **状況**: macOS の `activate` イベントでウィンドウ再生成時に `registerAllIpcHandlers()` が再実行され、`ipcMain.handle()` の二重登録例外が発生
- **アプローチ**:
  1. `unregisterAllIpcHandlers()` を追加し、`Object.values(IPC_CHANNELS)` で全チャンネルの `removeHandler` と `removeAllListeners` を実行
  2. `setupThemeWatcher()` のような IPC 外リスナーは `unsubscribe` をモジュールスコープで保持して同時解除
  3. `activate` では `unregister -> createWindow -> register` の順序を固定
  4. `ipcMain.handle()` と `ipcMain.on()` の二重登録時挙動差（例外送出 vs 累積登録）を設計レビューで明示
- **結果**: 7テストで再現シナリオをカバーし、`Attempted to register a second handler` を解消
- **適用条件**: Electron Main Process でウィンドウ再生成時に IPC ハンドラ再登録を伴う実装
- **発見日**: 2026-02-14
- **関連タスク**: UT-FIX-IPC-HANDLER-DOUBLE-REG-001
- **クロスリファレンス**:
  - [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md#ipc-ハンドラライフサイクル管理)
  - [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md#ipc-ハンドラ二重登録防止パターンut-fix-ipc-handler-double-reg-001-2026-02-14実装)
  - [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md#ut-fix-ipc-handler-double-reg-001-ipc-ハンドラ二重登録防止)

### [IPC] Main Process ライフサイクル修正ワークフロー

- **状況**: macOS の `activate` イベントで IPC ハンドラが二重登録され、`ipcMain.handle()` が例外を送出するバグ
- **アプローチ**:
  - `Object.values(IPC_CHANNELS)` で全チャンネルを動的列挙し、追加漏れを防止
  - `removeHandler()` + `removeAllListeners()` の両方を呼び出し（handle/on 両対応）
  - `themeWatcherUnsubscribe` 等の IPC 外リスナーも同時管理（モジュールスコープ変数）
  - TDD Red-Green パターンで7テスト先行作成 → 実装 → 全 GREEN
- **結果**: 2ファイル修正 + 7テスト追加のみで完了。4層セキュリティ防御は影響なし
- **教訓**:
  - `ipcMain.handle()` と `ipcMain.on()` は二重登録時の動作が根本的に異なる（例外 vs 累積）
  - IPC_CHANNELS 定数の構造（フラット or ネスト）を事前確認してから全走査ロジックを設計する
  - IPC ハンドラ以外のプロセスレベルリスナー（nativeTheme 等）も同時に管理する必要がある
  - macOS 固有のライフサイクル（activate）は Windows/Linux に影響しないことを互換性テストで確認
- **適用条件**: Electron アプリで macOS ドックアイコンクリック時のウィンドウ再生成がある場合
- **関連タスク**: UT-FIX-IPC-HANDLER-DOUBLE-REG-001
- **発見日**: 2026-02-14

### [Security] TDDセキュリティテスト分類体系（UT-9B-H-003）

- **状況**: IPCハンドラーのセキュリティ強化でテストを先行設計する必要がある
- **アプローチ**:
  - 攻撃カテゴリ別にテストIDを割り当て（SEC-01〜SEC-07g）
  - 受入基準（AC-01〜AC-10）にテストIDをマッピング
  - カテゴリ: パストラバーサル(SEC-01〜03)、ホワイトリスト(SEC-04〜05)、回帰(SEC-06)、境界値(SEC-07)
  - `it.each` で攻撃パターンを網羅（`../`, `..\`, `\x00`, `\\\\`）
  - テスト間独立性: `beforeEach` で `handlerMap.clear()` + `vi.clearAllMocks()`
- **結果**: 45セキュリティテスト + 71統合テスト = 116テスト全PASS。ブランチカバレッジ100%
- **適用条件**: セキュリティ関連のTDD実装時。特にIPC L3検証の追加時
- **発見日**: 2026-02-12
- **関連タスク**: UT-9B-H-003
- **クロスリファレンス**: [lessons-learned.md#UT-9B-H-003](../../aiworkflow-requirements/references/lessons-learned.md), [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md)

### [Security] YAGNI原則に基づく共通化判断の記録パターン（UT-9B-H-003）

- **状況**: Phase 8リファクタリングで、セキュリティ関数（validatePath, sanitizeErrorMessage）を共通パッケージに移動すべきか判断が必要
- **アプローチ**:
  - 3つの評価軸で判断: (1) 現在の使用箇所数、(2) 変更頻度の予測、(3) ドメインの独立性
  - 共通化しない判断も**未タスク候補として明示的に記録**（unassigned-task-report.md）
  - 既存の未タスク（UT-9B-H-001, UT-9B-H-002）との重複チェックを実施
  - 重複と判定された候補は新規作成せず、既存タスクのスコープ内で対応と記録
- **結果**: 3件の共通化候補を検討し、全て「現状維持」と判断。将来の判断材料として未タスクレポートに記録
- **適用条件**: Phase 8リファクタリングで共通化を検討する場合。特にセキュリティ関数のように複数のIPC Handlerで使用される可能性がある場合
- **発見日**: 2026-02-12
- **関連タスク**: UT-9B-H-003
- **クロスリファレンス**: [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)

- **Phase 12での苦戦箇所と解決策**:

| 苦戦箇所                                 | 原因                                                                 | 解決策                                                                                                                                |
| ---------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| CLI環境でのPhase 11手動テスト不可        | Claude Code環境ではElectronアプリ起動・DevTools操作ができない        | 自動テスト（116テスト）で代替検証を実施。DevToolsコマンドをドキュメントに記載し、開発者向けリファレンスとして提供                     |
| コンテキスト分割によるPhase 12整合性管理 | コンテキスト制限でセッション分割。前セッションの成果物状態追跡が困難 | セッション開始時に `Glob` でoutputs/配下の成果物一覧を確認。`TaskOutput` でバックグラウンドエージェント完了を待ってから整合性チェック |
| Markdownコードブロック内のPrettier干渉   | PostToolUseフックのPrettierがMarkdown内のTypeScript型表記を自動変形  | バックグラウンドエージェント内で修正ステップを追加。ドキュメント作成時はPrettier影響の検証を後処理に組み込む                          |

### [Testing] Store Hook テスト実装パターン（renderHook方式）（UT-STORE-HOOKS-TEST-REFACTOR-001）

- **状況**: Zustand個別セレクタHookのテストで `getState()` 直接呼び出しを使用しており、Reactサブスクリプション経由の動作検証ができていない
- **アプローチ**:
  - 旧パターンの問題: `store.getState().field` はReactの再レンダリングサイクルを経由しないため、コンポーネントでの実際の使用経路と異なる
  - 新パターン: `renderHook(() => useField())` でReactサブスクリプション経由のテストを実現
  - 状態変更: `act(() => useAppStore.setState({...}))` でReactの状態更新サイクルを正しく経由
  - 非同期アクション: `await act(async () => { ... })` でPromise解決を待機
  - テスト間リセット: `resetStore()` → `cleanup()` → `vi.restoreAllMocks()` の3段階で完全リセット

- **パターン対応表**:

| 対象             | 旧パターン（非推奨）        | 新パターン（推奨）                       |
| ---------------- | --------------------------- | ---------------------------------------- |
| 状態取得         | `store.getState().field`    | `renderHook(() => useField())`           |
| 状態変更         | `store.setState({...})`     | `act(() => useAppStore.setState({...}))` |
| アクション実行   | `store.getState().action()` | `renderHook` + `act()`                   |
| 非同期アクション | `await action()`            | `await act(async () => { ... })`         |

- **テストカテゴリ分類**（代表的な5カテゴリ）:

| カテゴリ         | 検証内容                                                  | 対応するCAT            |
| ---------------- | --------------------------------------------------------- | ---------------------- |
| 初期値検証       | セレクタが正しいデフォルト値を返すか                      | CAT-01                 |
| 状態変更検証     | act() + setState 後にセレクタが正しく更新されるか         | CAT-02, CAT-04, CAT-08 |
| 参照安定性       | rerender() 後もアクション関数の参照が === で同一か        | CAT-05, CAT-10         |
| 無限ループ防止   | useEffect依存配列にアクションを含めてもrenderCount < 10か | CAT-07, CAT-16         |
| 再レンダー最適化 | 無関係なフィールド変更でセレクタが再レンダーされないか    | CAT-06, CAT-11         |

- **結果**: getState()パターン48件 → renderHookパターン114件（+export検証23件）に移行。Reactサブスクリプション経路の検証、参照安定性テスト、無限ループ検出が可能に
- **適用条件**: Zustand Store で個別セレクタHookを使用し、React コンポーネントから利用するテストを書く場合。特に useEffect 依存配列にアクション関数を含める場合は無限ループ防止テスト（CAT-07/16）が必須。
- **発見日**: 2026-02-12
- **関連タスク**: UT-STORE-HOOKS-TEST-REFACTOR-001
- **クロスリファレンス**: [development-guidelines.md#Zustand Hook テスト戦略](../../aiworkflow-requirements/references/development-guidelines.md), [lessons-learned.md#UT-STORE-HOOKS-TEST-REFACTOR-001](../../aiworkflow-requirements/references/lessons-learned.md)
  - [arch-state-management.md#Store Hooks テスト実装ガイド](../../aiworkflow-requirements/references/arch-state-management.md) - テストパターン6種の一覧表
  - [testing-component-patterns.md#9. Zustand Store Hooks テストパターン](../../aiworkflow-requirements/references/testing-component-patterns.md) - コピペ可能な実装コード例

- **Phase 12での苦戦箇所と解決策**:

| 苦戦箇所                                 | 原因                                                                                                            | 解決策                                                                                                                                                        |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Step 2を「該当なし」と誤判定             | テストリファクタリングはインターフェース変更を伴わないため、Step 2不要と判断しがち                              | テストのみの変更でも、テスト戦略やテストパターンの変更は仕様書（development-guidelines.md等）に記録すべき。Step 2の判断基準に「テスト戦略変更」を含める       |
| 実装ガイドのテストカテゴリテーブル不整合 | Phase 4でテストカテゴリ（CAT-01〜CAT-05）を定義し、Phase 6で拡充したが、実装ガイドのテーブルがPhase 4時点のまま | Phase 6（テスト拡充）完了後に、implementation-guide.md Part 2のテストカテゴリテーブルを必ず再確認・更新する。テスト数やカテゴリ構成が変わった場合は即座に反映 |

### [Test] SDKテスト有効化モック2段階リセット

- **状況**: SDK統合テスト17箇所のTODOコメントを有効化する際、テスト間でモック状態が漏洩してテスト実行順序依存が発生
- **アプローチ**: `beforeEach` で (1) `vi.clearAllMocks()` + (2) `mockResolvedValue()` による2段階リセットを実施。エラーテストでは `mockRejectedValueOnce` のみ使用
- **結果**: 134テスト全PASS、テスト実行順序に非依存
- **適用条件**: `vi.mock()` でモジュール全体をモック化し、正常系・異常系テストが混在する場合
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [SDK] TypeScript モジュール解決による型安全統合（TASK-9B-I）

- **状況**: 外部 SDK (`@anthropic-ai/claude-agent-sdk@0.2.30`) の `as any` を除去し型安全な統合を実現
- **アプローチ**:
  - SDK の型定義ファイル (`dist/index.d.ts`) を直接参照して正確なパラメータ構造を把握
  - `SDKQueryOptions` 内部型を定義し、SDK `Options` 型への変換を型安全に実装
  - `@ts-expect-error` を使った compile-time テストで不正な型の検証
- **結果**: `as any` 完全除去、13テスト追加、278既存テスト全PASS
- **適用条件**: 外部 SDK の型安全な統合、`as any` 除去タスク
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-I-SDK-FORMAL-INTEGRATION
- **クロスリファレンス**: [02-code-quality.md#TypeScript型安全](../../.claude/rules/02-code-quality.md)

### [Testing] テスト環境別イベント発火パターン選択（UT-FIX-AGENTVIEW-INFINITE-LOOP-001）

- **状況**: Vitest + happy-dom環境でユーザーインタラクションテストを作成する際、`@testing-library/user-event`のSymbol操作がhappy-domで非互換
- **アプローチ**:
  - 問題発見: 53テスト中49テストがSymbolエラーで一斉失敗。`userEvent.setup()`がhappy-dom未サポートのDOM操作を実行
  - 試行1: `// @vitest-environment jsdom` ディレクティブ追加 → `toBeInTheDocument`動作不良、DOM要素重複で断念
  - 試行2: `userEvent`を`fireEvent`に全面置換 → 53テスト全PASS
  - 非同期対応: `await act(async () => { fireEvent.click(el) })`でPromise microtask flushを保証
- **パターン選択基準**:

| テスト環境                  | イベントAPI | 理由                                    |
| --------------------------- | ----------- | --------------------------------------- |
| happy-dom（デフォルト）     | `fireEvent` | Symbol操作不要、軽量・高速              |
| jsdom（ディレクティブ指定） | `userEvent` | 完全なDOM API、アクセシビリティ検証向き |

- **結果**: 環境固有の制約を理解し、適切なAPIを選択することでテスト安定性を確保
- **適用条件**: Vitest + happy-dom環境でのコンポーネントテスト。特にクリック/入力等のユーザーインタラクションテスト
- **発見日**: 2026-02-12
- **関連タスク**: UT-FIX-AGENTVIEW-INFINITE-LOOP-001
- **クロスリファレンス**: [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md#fireevent-vs-userevent-使い分けパターン), [06-known-pitfalls.md#P39](../../.claude/rules/06-known-pitfalls.md)

### [Testing] モノレポ テスト実行ディレクトリ依存パターン（UT-FIX-AGENTVIEW-INFINITE-LOOP-001）

- **状況**: モノレポ環境でプロジェクトルートからVitest実行すると、サブパッケージの`vitest.config.ts`が読み込まれない
- **アプローチ**:
  - 問題: `pnpm vitest run apps/desktop/src/...`（ルートから実行）→ `document is not defined`エラー
  - 原因: Vitestはカレントディレクトリの設定ファイルを優先。ルートの設定にはhappy-dom/setupFilesが未定義
  - 解決: `cd apps/desktop && pnpm vitest run src/...` または `pnpm --filter @repo/desktop exec vitest run src/...`
- **結果**: テスト実行を対象パッケージディレクトリから行うルールを確立
- **適用条件**: pnpm monorepo + Vitest環境で、パッケージ固有のテスト環境設定がある場合
- **発見日**: 2026-02-12
- **関連タスク**: UT-FIX-AGENTVIEW-INFINITE-LOOP-001
- **クロスリファレンス**: [06-known-pitfalls.md#P40](../../.claude/rules/06-known-pitfalls.md)

### [SDK] SDKテストTODO一括有効化ワークフロー

- **状況**: agent-client.test.ts / skill-executor.test.ts / sdk-integration.test.ts の3ファイルに TODO コメントで無効化された17箇所のテストが存在
- **アプローチ**: Phase 2設計で17箇所のモック戦略を事前にマッピング → Phase 5でファイルごとに有効化（既存モックパターン `vi.mock`/`vi.hoisted` を活用、NFR-007準拠）→ Phase 9で全134テスト一括検証
- **結果**: 新規モック戦略導入なしで17箇所全て有効化。既存テスト117件の挙動に影響なし
- **適用条件**: 段階的にテストを有効化し、回帰テストの安全性を保つ必要がある場合
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [Testing] Vitest未処理Promise拒否の可視化運用（TASK-FIX-10-1）

- **状況**: `dangerouslyIgnoreUnhandledErrors: true` が残っていると、未処理Promise拒否がテスト失敗として観測されず品質低下を招く
- **アプローチ**:
  - `vitest.config.ts` から `dangerouslyIgnoreUnhandledErrors` を削除し、デフォルト挙動（未処理拒否を失敗扱い）を維持
  - 設定退行を防ぐため、設定検証テストを追加して「危険設定を再導入していないこと」を機械検証
  - モノレポ解決エラーの混入を避けるため、`@repo/shared` サブパスaliasを具体パス優先で定義
- **結果**: 未処理Promise拒否の隠蔽を防止し、テスト失敗の原因を早期に可視化
- **適用条件**: Vitest設定に `dangerously*` 系の緩和設定を検討する場合、またはモノレポでalias整合が必要な場合
- **発見日**: 2026-02-19
- **関連タスク**: TASK-FIX-10-1-VITEST-ERROR-HANDLING
- **クロスリファレンス**: [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md#未処理promise拒否検知ルールtask-fix-10-1-2026-02-19実装)

### [IPC] IPC契約ドリフト防止パターン（3箇所同時更新）（UT-FIX-SKILL-REMOVE-INTERFACE-001）

- **状況**: Main Process の IPC ハンドラと Preload API の引数インターフェースが乖離し、ランタイムでバリデーションエラーが発生（P44パターン）
- **アプローチ**:
  1. **契約の正本を特定**: Preload側（`skill-api.ts`）の呼び出しシグネチャを「正」と定義し、ハンドラ側を合わせる
  2. **3箇所同時更新**: ハンドラ（`skillHandlers.ts`）・Preload API（`skill-api.ts`）・テスト（`*.test.ts`）を1コミットで更新
  3. **引数命名統一**: `skillId` / `skillIds` / `skillName` の混在を排除し、全レイヤーで `skillName: string` に統一
  4. **P42準拠バリデーション**: 3段バリデーション（`typeof === "string"` → `=== ""` → `.trim() === ""`）を全ハンドラに適用
  5. **横断検証**: `grep -rn "skillId\b" apps/desktop/src/main/` で同一パターンの残存を検出
- **結果**: skill:import と skill:remove の両チャンネルでインターフェース不整合を解消。同一パターンの横断的修正を実現
- **適用条件**: IPC ハンドラの引数変更、新規 IPC チャンネル追加、既存ハンドラのバリデーション修正
- **発見日**: 2026-02-20
- **関連タスク**: UT-FIX-SKILL-REMOVE-INTERFACE-001, UT-FIX-SKILL-IMPORT-INTERFACE-001
- **クロスリファレンス**:
  - [06-known-pitfalls.md#P44](../../.claude/rules/06-known-pitfalls.md) - インターフェース不整合の教訓
  - [ipc-contract-checklist.md](../../aiworkflow-requirements/references/ipc-contract-checklist.md) - IPC修正時チェックリスト
  - [security-electron-ipc.md](../../aiworkflow-requirements/references/security-electron-ipc.md) - IPCセキュリティ仕様

### [IPC/Renderer] Renderer層 id→name 契約変換パターン（UT-FIX-SKILL-IMPORT-ID-MISMATCH-001）

- **状況**: SkillImportDialog が `skill.id`（SHA-256ハッシュ）を `onImport` に渡しており、IPCハンドラ側は `skill.name`（人間可読名）を期待していた。同じ `string` 型のため、コンパイル時に不整合が検出されない
- **アプローチ**:
  1. **利用箇所からの逆引き**: `AgentView` の import 文から修正対象を `organisms/SkillImportDialog/index.tsx` に特定
  2. **境界での明示変換**: `selectedIds`（Set<string>）を `availableSkills.filter(s => selectedIds.has(s.id)).map(s => s.name)` で名前配列に変換
  3. **命名の契約準拠**: callback の引数名を `skillNames` に統一し、Props 型も `onImport: (skillNames: string[]) => void` に更新
  4. **否定条件テスト**: 「id が渡されないこと」を `expect(onImport).not.toHaveBeenCalledWith(expect.arrayContaining([skill.id]))` で検証
- **結果**: Renderer → IPC → Service の全レイヤーで `skill.name` 契約が統一。テスト 88 件全 PASS
- **適用条件**: 内部識別子（ハッシュ、UUID）と外部識別子（名前、スラッグ）が同じ `string` 型で混在するコンポーネント
- **発見日**: 2026-02-22
- **関連タスク**: UT-FIX-SKILL-IMPORT-ID-MISMATCH-001
- **クロスリファレンス**:
  - [06-known-pitfalls.md#P44](../../.claude/rules/06-known-pitfalls.md) - IPC インターフェース不整合の教訓
  - [lessons-learned.md#UT-FIX-SKILL-IMPORT-ID-MISMATCH-001](../../aiworkflow-requirements/references/lessons-learned.md) - 苦戦箇所詳細
  - [architecture-implementation-patterns.md#S13](../../aiworkflow-requirements/references/architecture-implementation-patterns.md) - IPC 戻り値型変換パターン

### [IPC] IPC契約ブリッジ（正式契約 + 後方互換）（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: shared/preload は `skillName` 契約へ移行済みだが、Main/Service は `skillId` 前提で稼働しており、一括置換すると既存呼び出しを壊す
- **アプローチ**:
  1. Mainハンドラで union 受理（正式: `SkillExecutionRequest`、互換: `{ skillId, params }`）
  2. `skillName` 経路は境界で `name -> id` を解決し、Service APIは据え置き
  3. 新旧契約を同一テスト群で回帰確認（正常系/異常系）
  4. interfaces/security/task-workflow を同一ターンで同期更新
- **結果**: 契約移行中のダウンタイムなしで `skill:execute` を整合化し、後方互換を維持
- **適用条件**: IPC契約の正式化が先行し、内部APIの移行が段階的になるケース
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] 未タスク検出の2段階判定（raw→実タスク候補）

- **状況**: `detect-unassigned-tasks.js` が仕様書本文の説明用 TODO まで大量検出し、未タスク件数を過大評価しやすい
- **アプローチ**:
  - 1段階目: 実装ディレクトリ（例: `apps/.../__tests__`）を優先スキャン
  - 2段階目: ドキュメント全体の raw 検出結果を手動精査し、説明文TODOと実装漏れを分離
  - 出力は「raw検出件数」と「確定未タスク件数」を別々に記録
- **結果**: 誤検知由来の不要な未タスク作成を防止し、`docs/30-workflows/unassigned-task/` への配置要否を正確化
- **適用条件**: Phase 12 Task 4（未タスク検出）実行時
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT
- **クロスリファレンス**: [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md)

---

### [Phase 12] 実行仕様書ステータス同期（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: Phase 12 の成果物は生成済みだが、`phase-12-documentation.md` 本文が「未実施」のまま残る
- **解決策**: 成果物監査と同時に、仕様書本体の `ステータス` / 事前チェック / 完了条件チェックボックスを実態に同期する
- **効果**: 実行記録と仕様書の齟齬を防ぎ、後続フェーズ判定を明確化できる
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001

### [Phase 12] 成果物ログとStep判定の同期（UT-FIX-SKILL-IMPORT-INTERFACE-001）

- **状況**: `outputs/phase-12` には成果物がある一方、`system-docs-update-log.md` が「Step 2該当なし」「Phase 13で実施予定」の古い判定を保持していた
- **解決策**:
  1. 仕様更新実績（更新した仕様書）を先に確定し、Step判定を再計算する
  2. `system-docs-update-log.md` / `documentation-changelog.md` / `phase-12-documentation.md` の3ファイルを同時更新する
  3. 「後続Phaseで対応予定」の記述を禁止し、Phase 12必須項目は同一ターンで完了記録する
  4. 更新不要判定は「理由 + 正本ファイル」を明記する
- **効果**: Phase 12の完了証跡と実装実態が一致し、再監査時の差し戻しを削減できる
- **適用条件**: 仕様更新対象が複数ファイルに跨るタスク、またはPhase 12の再監査を行うタスク
- **発見日**: 2026-02-21
- **関連タスク**: UT-FIX-SKILL-IMPORT-INTERFACE-001

### [Phase 12] 全体監査と対象差分の分離報告（TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001）

- **状況**: `audit-unassigned-tasks.js` はリポジトリ全体を監査するため、既存違反件数が多い場合に「今回作業で壊した」と誤読しやすい
- **解決策**:
  1. 監査結果を「全体ベースライン（既存）」と「今回対象ファイル」の2レイヤーで分離する
  2. 今回対象ファイルは `sed`/`rg` で9見出しテンプレート準拠を個別検証する
  3. 報告時に「全体違反件数」「今回対象の準拠可否」を同一表で併記し、責務境界を明確化する
- **効果**: 既存負債と今回差分の切り分けが可能になり、誤った差し戻しや過剰修正を防止できる
- **適用条件**: 未タスク監査を既存資産が多いリポジトリで実行するPhase 12 Task 4
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001
- **クロスリファレンス**: [task-specification-creator/scripts/audit-unassigned-tasks.js](../../task-specification-creator/scripts/audit-unassigned-tasks.js), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] scoped監査の `current` 判定固定（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: `--target-file` を使っても baseline が出力されるため、対象ファイルも違反と誤読しやすい
- **解決策**:
  1. `audit-unassigned-tasks --json --diff-from HEAD --target-file <path>` の `scope.currentFiles` を確認する
  2. 合否は `currentViolations.total` を正本にし、`baselineViolations.total` は別枠で記録する
  3. 報告テンプレートに `current / baseline` を分離して記載する
- **効果**: 既存負債に引きずられず、今回差分のフォーマット準拠可否を即判定できる
- **適用条件**: unassigned-task 監査を既存違反が多いリポジトリで実行する場合
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase 12] target監査 + 10見出し同時検証（TASK-9I再確認）

- **状況**: 未タスク指示書を新規作成した後、配置確認は通るがフォーマット崩れが混入しやすい
- **解決策**:
  1. `audit-unassigned-tasks --json --diff-from HEAD --target-file <path>` を対象ファイルごとに実行し、`currentViolations.total` を判定軸に固定する
  2. 必須10見出し（`## メタ情報` + `## 1..9`）と `## メタ情報` 件数（1件）を同一ターンで検証する
  3. `verify-unassigned-links` で実体パス整合を確認し、`missing=0` を完了条件に含める
  4. `task-workflow.md` の再確認テーブルへ `current/baseline` を分離して記録する
- **効果**: 「存在は正しいが形式が壊れている」状態を防止し、Phase 12再確認の判定を再現可能にする
- **適用条件**: unassigned-task を新規登録した Phase 12 Task 4 と再監査
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9I, UT-9I-001, UT-9I-002
- **クロスリファレンス**: [audit-unassigned-tasks.js](../../task-specification-creator/scripts/audit-unassigned-tasks.js), [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md), [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md)

### [Phase 12] 2workflow同時監査 + Task 1/3/4/5実体突合（TASK-UI-05A / TASK-UI-05）

- **状況**: `spec_created` workflow と完了workflowを同時に再監査する際、検証結果や証跡が分散し、完了判定が曖昧になりやすい
- **解決策**:
  1. 対象workflowを先に固定し、`verify-all-specs --workflow <dir>` を全対象へ実行する
  2. 続けて `validate-phase-output <dir>` を同対象へ実行し、構造準拠を確定する
  3. Phase 12 Task 1/3/4/5 の必須成果物実体（`implementation-guide`/`documentation-changelog`/`unassigned-task-detection`/`skill-feedback-report`）をworkflowごとに突合する
  4. 未タスク監査は `verify-unassigned-links` + `audit --diff-from HEAD` を連続実行し、合否を `currentViolations=0` で固定する
- **効果**: 複数workflow再監査の証跡が一本化され、baseline誤読や完了判定のブレを抑止できる
- **適用条件**: Phase 12で spec_created系と完了系workflowを同一ターンで確認する場合
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05A-SKILL-EDITOR-VIEW, TASK-UI-05-SKILL-CENTER-VIEW
- **クロスリファレンス**: [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [phase-12-documentation.md](../../../../docs/30-workflows/skill-editor-view/phase-12-documentation.md), [phase-12-documentation.md](../../../../docs/30-workflows/completed-tasks/TASK-UI-05-SKILL-CENTER-VIEW/phase-12-documentation.md)

### [Phase 12] 2workflow証跡バンドル完了同期（UT-IMP-PHASE12-TWO-WORKFLOW-EVIDENCE-BUNDLE-001）

- **状況**: 2workflow同時監査タスクを完了移管した後、`task-workflow.md` と関連仕様書の未タスク参照が旧パスのまま残り、`verify-unassigned-links` が fail しやすい
- **解決策**:
  1. 完了移管を伴う未タスクIDを先に列挙し、`task-workflow.md` と関連仕様書（例: `ui-ux-feature-components.md`）の参照先を同一ターンで実体パスへ更新する
  2. `verify-unassigned-links` を再実行し、`missing=0` を確認してから完了記録を更新する
  3. `audit --target-file` / `audit --diff-from HEAD` の合否は `currentViolations=0` に固定し、baselineは監視値として分離記録する
  4. 実装内容・苦戦箇所・再利用手順を `task-workflow` / `architecture-implementation-patterns` / `lessons-learned` の3仕様へ同期する
- **効果**: 完了移管後のリンクドリフトを防ぎ、2workflow同時監査タスクの完了判定を再現可能にできる
- **適用条件**: Phase 12の再監査タスクで「未タスク登録→実装完了→completed-tasks移管」を跨ぐ場合
- **発見日**: 2026-03-03
- **関連タスク**: UT-IMP-PHASE12-TWO-WORKFLOW-EVIDENCE-BUNDLE-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [architecture-implementation-patterns.md](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)

### [Phase 12] `validate-phase-output` 位置引数固定

- **状況**: `verify-all-specs` と同じオプション形式を想定し、`validate-phase-output` の実行が失敗しやすい
- **解決策**:
  1. `node .../validate-phase-output.js <workflow-dir>` の位置引数形式をテンプレート化する
  2. `verify-all-specs --workflow <workflow-dir>` とセットで実行して証跡を残す
  3. documentation-changelog に両コマンド結果を併記する
- **効果**: Phase検証のコマンド誤用を抑止し、再確認時のやり直しを削減できる
- **適用条件**: Phase 12 再監査または仕様整合の再検証を行う場合
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase 12] 監査結果→次アクションブリッジ（TASK-013再監査）

- **状況**: 監査レポートは作成済みだが、次にどの未タスクから着手するかが曖昧で、実行順序が固まらない
- **解決策**:
  1. `task-00` 配下に「監査結果→次実行」の専用導線（action-bridge）を追加する
  2. 優先度（P1-P4）と Wave（並列/直列）を明記し、SubAgent担当を固定する
  3. `outputs/phase-12/` の必須5成果物を証跡として同時に紐づける
  4. baseline/current 監査結果を併記し、「今回差分で何が必要か」を分離する
  5. `assets/phase12-action-bridge-template.md` を起点に記述し、タスク間の形式ブレを抑制する
- **効果**: 「監査したが次の手が見えない」状態を解消し、再監査後の実装着手までの待ち時間を削減できる
- **適用条件**: 再監査で検出項目が複数あり、実行順序・責務分担の明文化が必要な Phase 12
- **発見日**: 2026-02-25
- **関連タスク**: TASK-013E-PHASE12-ACTION-BRIDGE-001
- **クロスリファレンス**: [task-013e-phase12-action-bridge.md](../../../docs/30-workflows/skill-import-agent-system/tasks/task-00-unified-implementation-sequence/task-013e-phase12-action-bridge.md), [phase12-action-bridge-template.md](../assets/phase12-action-bridge-template.md)

### [Phase 12] Task 1〜5証跡突合レポート固定化（UT-UI-THEME-DYNAMIC-SWITCH-001）

- **状況**: `outputs/phase-12` は揃っているが、`phase-12-documentation.md` のチェック欄と実行記録がテンプレート状態のまま残りやすい
- **解決策**:
  1. Task 1〜5 の証跡を1ファイル（`phase12-task-spec-compliance-check.md`）に集約する
  2. 成果物実体と `phase-12-documentation.md` のチェック欄を同一ターンで更新する
  3. `verify-all-specs --workflow --strict` と `verify-unassigned-links.js` の結果を同レポートに固定する
  4. SubAgent分担（A:成果物/B:仕様/C:未タスク/D:検証）を明示し、並列確認結果を残す
- **効果**: Phase 12完了判定の根拠が一本化され、再監査時の差し戻しを減らせる
- **適用条件**: Phase 12 の再確認や、成果物数が5件以上あるタスク
- **発見日**: 2026-02-25
- **関連タスク**: UT-UI-THEME-DYNAMIC-SWITCH-001

### [Phase 12] 実装内容+苦戦箇所テンプレート適用（UT-UI-THEME-DYNAMIC-SWITCH-001）

- **状況**: 実装内容は記録されているが、苦戦箇所が「症状」だけで終わると同種課題で再利用しにくい
- **解決策**:
  1. `assets/phase12-system-spec-retrospective-template.md` を起点に、タスクID・反映先3点セット・検証コマンドを固定化する
  2. 苦戦箇所は「課題/原因/対処」に加えて「再発条件」を必須項目として記録する
  3. `task-workflow.md` / `ui-ux-design-system.md` / `lessons-learned.md` へ同一ターンで同期する
  4. SubAgent分担（A:台帳/B:UI仕様/C:教訓/D:検証）を記録し、並列処理時の責務漏れを防ぐ
- **効果**: 仕様更新の形式が統一され、同種課題に対して短時間で再利用できる
- **適用条件**: Phase 12 Step 2 で実装内容と苦戦箇所を同時反映するタスク
- **発見日**: 2026-02-25
- **関連タスク**: UT-UI-THEME-DYNAMIC-SWITCH-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [ui-ux-design-system.md](../../aiworkflow-requirements/references/ui-ux-design-system.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] 仕様書別SubAgent同期テンプレート（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: IPC契約修正時に `interfaces` / `security` / `task-workflow` / `lessons` が別ターン更新となり、同期漏れが再発しやすい
- **解決策**:
  1. 仕様書ごとに SubAgent を固定し、担当と完了条件を先に表で定義する
  2. 各 SubAgent は「実装内容 + 苦戦箇所 + 再利用手順」を同時記述する
  3. 統括担当が4仕様書の差分を集約し、同一ターンで変更履歴を更新する
  4. `verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` を実行して証跡化する
  5. `assets/phase12-spec-sync-subagent-template.md` を起点に形式を統一する
- **効果**: 仕様書間の責務境界が明確化され、Phase 12 の同期漏れと再監査コストを削減できる
- **適用条件**: 1つの実装変更を複数仕様書へ横断反映する Phase 12
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001
- **クロスリファレンス**: [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase12] 5仕様書同期 + IPC三点突合テンプレート（TASK-9J）

- **状況**: `interfaces/security/task-workflow/lessons` は同期しても、`api-ipc` が漏れると IPC 契約の正本が分断される
- **解決策**:
  1. SubAgent を `A:interfaces / B:api-ipc / C:security / D:task-workflow / E:lessons` の5責務に固定する
  2. IPC追加時は `handler/register/preload` の3点を `rg` で同時突合し、1つでも欠けたら未完了と判定する
  3. `task-workflow` へ検証証跡（`verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` / `audit --diff-from HEAD`）を固定記録する
  4. `lessons` には再発条件付きで苦戦箇所を記録し、次回タスクで流用できる形に整える
  5. `assets/phase12-spec-sync-subagent-template.md` を唯一の入力テンプレートとして運用する
- **効果**: 仕様ドリフト（API名・チャネル・検証要件）の再発を抑止し、Phase 12 再監査の手戻りを削減
- **適用条件**: IPC追加を含む機能で、5仕様書以上の横断同期が必要な Phase 12
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J
- **クロスリファレンス**: [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] 完了タスク記録の二重同期（UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001）

- **状況**: `outputs/phase-12` と `artifacts.json` は更新済みでも、手順書側（`spec-update-workflow.md` / `phase-11-12-guide.md`）に完了タスク実記録が残らないことがある
- **解決策**:
  1. Step 1-A で更新した仕様書に `## 完了タスク` と `## 関連ドキュメント` を同時追記する
  2. 実装ガイド・更新履歴・未タスク検出レポートへのリンクを同一ターンで同期する
  3. `LOGS.md` / `SKILL.md` の更新履歴と併せて `quick_validate.js` を3スキルで再実行する
  4. `verify-unassigned-links.js` と `audit-unassigned-tasks.js --diff-from HEAD` で未タスク整合を最終確認する
- **効果**: Phase 12 の「成果物実体」と「手順書完了記録」の二重台帳が揃い、再監査時の差し戻しを削減できる
- **適用条件**: Phase 12 Task 2 で複数スキル（aiworkflow/task-spec/skill-creator）を同時更新するタスク
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001
- **クロスリファレンス**: [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md), [phase-11-12-guide.md](../../task-specification-creator/references/phase-11-12-guide.md)

### [Phase 12] 完了移管後の親タスク証跡参照同期（UT-IMP-QUICK-VALIDATE-EMPTY-FIELD-GUARD-001）

- **状況**: 未タスク指示書を `completed-tasks/` へ移管した後、親タスク成果物（`artifacts.json` / `minor-issues.md` / `unassigned-task-detection.md`）に旧 `unassigned-task` 参照が残る
- **解決策**:
  1. 完了移管したタスクIDで `rg -n "task-imp-<task-id>\\.md"` を `docs/30-workflows/completed-tasks/` 配下へ実行し、親タスク証跡の残存参照を検出する
  2. 更新対象を「当時の監査生ログ（JSON）」と「運用ドキュメント（md/json台帳）」に分離し、生ログは改変せず運用ドキュメントのみ更新する
  3. 修正後に `verify-unassigned-links.js` と `audit-unassigned-tasks.js --json --diff-from HEAD` を再実行し、リンク整合と current=0 を確認する
- **効果**: 完了移管後の親子タスク参照が一貫し、Phase 12 再監査での「旧参照残存」による差し戻しを防止できる
- **適用条件**: 子タスクの未タスク指示書を完了移管したタスク、または親タスク成果物を再利用する再監査タスク
- **発見日**: 2026-02-27
- **関連タスク**: UT-IMP-QUICK-VALIDATE-EMPTY-FIELD-GUARD-001
- **クロスリファレンス**: [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md)

### [Phase 12] 依存成果物参照補完 + 画面再撮影固定（TASK-UI-05B 再確認）

- **状況**: `verify-all-specs` は PASS だが warning が残り、Phase 12 文書更新の完了判定が揺れる。UI証跡も既存画像の存在確認だけで止まりやすい
- **解決策**:
  1. `phase-12-documentation.md` の参照資料に依存Phase成果物（2/5/6/7/8/9/10）を明示する
  2. `verify-all-specs` / `validate-phase-output` を再実行し、warning/error の根拠を固定する
  3. UI再確認時はスクリーンショットを再取得し、更新時刻で当日証跡を確定する
  4. `audit --diff-from HEAD` の結果は `current/baseline` を分離して記録する
- **効果**: warningドリフトと画面証跡の鮮度不明問題を同時に解消し、Phase 12 再確認の再現性を高める
- **適用条件**: UI機能で Phase 12 再確認を実施するタスク（特に `spec_created -> completed` 移行後）
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05B-SKILL-ADVANCED-VIEWS
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [Phase 12] UI6仕様書を1仕様書1SubAgentで同期固定（TASK-UI-05B）

- **状況**: UI機能の仕様更新で `arch-ui + arch-state` を同一担当に束ねると、責務境界と追跡性が曖昧になり、差し戻し時の再現性が落ちる
- **解決策**:
  1. UIプロファイルを 6責務（`ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` / `task-workflow` / `lessons-learned`）に分割する
  2. `spec-update-summary.md` と `task-workflow.md` に同一の6責務表を記録し、担当と依存順序を固定する
  3. 各仕様書に「実装内容 + 苦戦箇所 + 標準化ルール」の最小セットを残し、1仕様書単位で再利用可能にする
  4. `verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` / `audit --diff-from HEAD` を実行し、同期結果を同日証跡へ固定する
- **効果**: 仕様書ごとの説明責任が明確になり、再監査時の差し戻し箇所を即座に特定できる
- **適用条件**: UI機能実装で6仕様書同期（ui-ux/arch/task/lessons）が必要な Phase 12
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05B-SKILL-ADVANCED-VIEWS
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase 12] Step 2判定とchangelog同期の二重突合（TASK-10A-A）

- **状況**: `phase-12-documentation.md` では Step 2 必須なのに、`documentation-changelog.md` が `該当なし` と記録されて完了判定が揺れる
- **解決策**:
  1. Step 2 判定は `phase-12-documentation.md` の更新対象テーブルを正本として固定する
  2. `documentation-changelog.md` の Step 判定と `spec-update-summary.md` の更新対象一覧を同一ターンで突合する
  3. Step 2 対象仕様（UIの場合は `arch-ui-components.md`）を更新した後に `verify-all-specs` / `validate-phase-output` を再実行する
  4. `task-workflow.md` と `lessons-learned.md` に同一の苦戦箇所を転記し、再発条件と標準ルールを固定する
  5. 未タスク監査は `audit --diff-from HEAD` の `currentViolations` を合否、`baselineViolations` を監視として分離記録する
- **効果**: Step判定の誤りと証跡分散を同時に防ぎ、Phase 12 完了判定の再現性を高められる
- **適用条件**: UI機能で Step 2 のシステム仕様更新を伴う Phase 12（再監査含む）
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-A-SKILL-MANAGEMENT-PANEL
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] UI再撮影 + TCカバレッジ検証の同時固定（TASK-10A-C）

- **状況**: UI証跡を再撮影しても、TCと画像の紐付け検証を省略すると `manual-test-result.md` と実ファイルの対応がずれやすい
- **解決策**:
  1. `pnpm --filter @repo/desktop run screenshot:<feature>` で当日再撮影する
  2. `validate-phase11-screenshot-coverage.js --workflow <workflow-path>` を実行し、TC単位の欠落を機械検証する
  3. `ls -lt <workflow>/outputs/phase-11/screenshots` で更新時刻を確認し、証跡鮮度を台帳へ記録する
  4. `task-workflow.md` / `ui-ux-components.md` / `ui-ux-feature-components.md` に同一の検証値（撮影件数・TC件数）を同期する
- **効果**: 画面証跡の鮮度確認とTC紐付け確認を分離せず実施でき、Phase 11/12 の再監査差し戻しを抑制できる
- **適用条件**: UI機能の Phase 11/12 でスクリーンショットを完了証跡として扱う全タスク
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [screenshot-coverage.md](../../../../docs/30-workflows/completed-tasks/skill-create-wizard/outputs/phase-11/screenshot-coverage.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] 仕様書別SubAgent分担を完了台帳へ固定（TASK-10A-C）

- **状況**: `spec-update-summary.md` には分担を書いたが、`task-workflow.md` の完了記録に分担表が無く、再監査時の責務追跡が難しくなる
- **解決策**:
  1. `task-workflow.md` の対象タスク節へ `SubAgent-A..E` の分担表（api-ipc/interfaces/security/task/lessons）を転記する
  2. 各SubAgentの完了条件を「実装同期済み」「検証証跡同期済み」の2軸で明記する
  3. `spec-update-summary.md` と `task-workflow.md` の分担内容を同一ターンで一致させる
  4. `verify-all-specs` / `validate-phase-output` 実行後に分担表を最終更新して差分固定する
  5. `api-ipc/interfaces/security/task-workflow/lessons` の5仕様書すべてに「実装内容 + 苦戦箇所 + 簡潔手順」があることを最終確認する
- **効果**: 関心分離ベースの責務境界が台帳に残り、次タスクで再利用しやすくなる
- **適用条件**: 仕様書を複数SubAgentで同期する Phase 12 タスク全般
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] `phase-12-documentation.md` ステータス同期（TASK-9H)

- **状況**: `outputs/phase-12` の成果物とシステム仕様更新が完了していても、`phase-12-documentation.md` のメタ情報・完了条件チェックが `未実施` のまま残る
- **解決策**:
  1. `implementation-guide/spec-update-summary/documentation-changelog/unassigned-task-detection/skill-feedback-report` の5成果物を実体確認する
  2. `phase-12-documentation.md` のステータスを `完了` へ更新し、Step 1-A〜Step 3 と完了条件を同時チェックする
  3. `verify-all-specs` / `validate-phase-output` / `verify-unassigned-links` / `audit --diff-from HEAD` の結果を `spec-update-summary.md` に固定する
  4. `task-workflow.md` と `lessons-learned.md` へ同一検証値を転記し、台帳間の不一致を解消する
- **効果**: 成果物実体と実行仕様書の二重台帳が一致し、再監査での差し戻し（「未実施残置」）を防止できる
- **適用条件**: Phase 12 の成果物作成と仕様更新が完了した最終同期フェーズ
- **発見日**: 2026-02-27
- **関連タスク**: TASK-9H
- **クロスリファレンス**: [phase-12-documentation.md](../../../../docs/30-workflows/TASK-9H-skill-debug/phase-12-documentation.md), [spec-update-summary.md](../../../../docs/30-workflows/TASK-9H-skill-debug/outputs/phase-12/spec-update-summary.md)

### [Phase 12] workflow 本文 `phase-1..11` の completed 同期（TASK-UI-02）

- **状況**: `artifacts.json` と `index.md` は completed でも、workflow 本文 `phase-1..11` の `ステータス` / 完了条件 / 実行タスク結果が `pending` のまま残ることがある
- **解決策**:
  1. `rg -n 'ステータス\\s*\\|\\s*pending' <workflow-path>/phase-{1,2,3,4,5,6,7,8,9,10,11}-*.md` で stale を検出する
  2. completed 扱いの Phase 本文は `ステータス=completed`、完了条件 `[x]`、実行タスク結果 `completed` へ同期する
  3. `phase-12-documentation.md` / `artifacts.json` / `outputs/artifacts.json` / `index.md` と同じターンで更新し、台帳を一本化する
  4. `verify-all-specs` / `validate-phase-output` / pending 検出 `rg` の結果を `spec-update-summary.md` に固定する
- **効果**: 「Phase 12 は完了だが前提 Phase 本文は未完了表示」というねじれを防ぎ、引き継ぎ根拠と監査の再現性を保てる
- **適用条件**: Phase 12 再監査、または worktree 上で Phase 1〜12 を完了同期するタスク全般
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-02
- **クロスリファレンス**: [phase12-task-spec-compliance-check.md](../../../../docs/30-workflows/task-057-ui-02-global-nav-core/outputs/phase-12/phase12-task-spec-compliance-check.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md)

### [Phase 12] テンプレートの正規経路固定（UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001）

- **状況**: Phase 12用テンプレートに旧環境依存パス（絶対パス）や旧成果物名が残ると、再利用時に誤実行や証跡欠落が発生する
- **解決策**:
  1. `assets/phase12-system-spec-retrospective-template.md` の検証コマンドを repo 相対パスへ統一する
  2. 成果物名を最新仕様（`unassigned-task-detection.md` / `skill-feedback-report.md`）へ同期する
  3. SubAgent分担（A:台帳/B:教訓/C:履歴/D:検証）をテンプレートに固定し、関心分離を標準化する
  4. 更新後に `quick_validate.js` と `verify-all-specs` を実行してテンプレート運用の整合を確認する
- **効果**: 環境依存による手順崩れを防ぎ、別ブランチ/別端末でも同じ実行結果を再現できる
- **適用条件**: Phase 12 テンプレートを新規作成・更新する全タスク
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md)

### [Phase 12] 未タスクメタ情報1セクション運用（TASK-9A再確認）

- **状況**: 未タスク指示書で `## メタ情報` が二重定義され、フォーマット監査時のノイズになる
- **解決策**:
  1. `## メタ情報` は1回のみ定義する
  2. `issue_number` の YAML とメタ情報テーブルは同一セクション内で連続配置する
  3. `rg -n "^## メタ情報" docs/30-workflows/unassigned-task/*.md` で1ファイル1件を機械確認する
- **効果**: 未タスクフォーマットの再監査コストを下げ、Phase 12の整合判定が安定する
- **適用条件**: 未タスク指示書を新規作成・更新する全ての Phase 12
- **発見日**: 2026-02-26
- **関連タスク**: TASK-9A-skill-editor
- **クロスリファレンス**: [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md)

### [Phase 12] getFileTree再同期の5点固定（UT-UI-05A-GETFILETREE-001）

- **状況**: IPC実装完了後に、仕様書同期・成果物命名・未タスク形式が別々に更新され、再確認で差し戻しが発生しやすい
- **解決策**:
  1. Step 2 は `api-ipc` / `ui-ux-feature` / `security` / `interfaces` / `task-workflow` の5仕様書を固定確認対象にする
  2. `phase-12-documentation.md` の成果物表と `outputs/phase-12` 実体を1対1で突合する
  3. 画面証跡は `outputs/phase-11/screenshots/*.png` を実際に開いて確認した上で同期する
  4. 未タスク指示書は `## メタ情報` 1セクション原則（YAML+表同居）を `rg` で機械確認する
  5. 合否判定は `audit --diff-from HEAD` の `currentViolations=0` に固定し、baselineは監視値として分離記録する
- **効果**: Phase 12再確認で発生しやすい「実装済みなのに文書だけ未同期」「命名揺れ」「形式ノイズ」を同時に抑止できる
- **適用条件**: IPC追加を伴う UIタスクで、Phase 11/12 の証跡と仕様更新を同一ターンで収束させる場合
- **発見日**: 2026-03-03
- **関連タスク**: UT-UI-05A-GETFILETREE-001
- **クロスリファレンス**: [spec-update-workflow.md](../../task-specification-creator/references/spec-update-workflow.md), [unassigned-task-guidelines.md](../../task-specification-creator/references/unassigned-task-guidelines.md)

### [Phase 12] SubAgent成果物の明示固定（UT-UI-05A-GETFILETREE-001）

- **状況**: 実装同期は完了していても、仕様書ごとの担当境界が成果物として残らないと、次回再確認で責務が再び曖昧化する
- **解決策**:
  1. `spec-update-summary.md` を `phase12-system-spec-retrospective-template` 準拠へ再構成する
  2. `spec-sync-subagent-report.md` を新規作成し、1仕様書=1SubAgentの責務/依存/完了条件を固定する
  3. Step 2 判定は `phase-12-documentation` / `documentation-changelog` / `spec-update-summary` の三点突合で確定する
  4. `task-workflow.md` と `lessons-learned.md` に同一の SubAgent分担と苦戦箇所を同一ターンで同期する
  5. 検証結果は `currentViolations=0` を合否、`baseline` を監視として分離記録する
- **効果**: 「実装はあるが責務定義が残らない」状態を防ぎ、次回の再確認コストを下げる
- **適用条件**: 複数仕様書を同時更新する Phase 12 タスク全般（特に UI + IPC 混在タスク）
- **発見日**: 2026-03-03
- **関連タスク**: UT-UI-05A-GETFILETREE-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase 12] 待機API/停止API責務分離の仕様固定（TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001）

- **状況**: `waitForCallback()` timeout 時に `stop()` まで実行すると、待機失敗と停止処理が結合して終了順序が不安定になる
- **解決策**:
  1. 実装を「待機責務（wait）」と「停止責務（stop）」へ分離し、timeout はエラー返却のみに限定する
  2. `stop()` に `!server || !server.listening` ガードを入れて冪等停止を保証する
  3. timeout テストに明示 `await stop()` を追加し、クリーンアップ責務を固定する
  4. 仕様同期は SubAgent 分担（security/task-workflow/lessons/validation）で同一ターン更新する
  5. `spec-update-summary.md` に検証値（13/13, 28項目, links 91/91, current=0, tests 13/13）を正本として固定する
- **効果**: 待機APIの副作用混在を防ぎ、同種の終了不安定バグを再発防止できる
- **適用条件**: timeout を持つ待機APIと明示停止APIが共存するタスク、特に Phase 12 Step 2 で仕様同期を伴う場合
- **発見日**: 2026-02-28
- **関連タスク**: TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001
- **クロスリファレンス**: [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [security-implementation.md](../../aiworkflow-requirements/references/security-implementation.md), [task-workflow.md](../../aiworkflow-requirements/references/task-workflow.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [ビルド・環境] モノレポ三層モジュール解決整合パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: モノレポ内パッケージ(@repo/shared)のサブパス import で tsc/vitest 両方が解決に失敗する
- **アプローチ**: exports(npm標準) / paths(TypeScript) / alias(Vitest) の3層を同一変更セットで更新し、整合性テストで固定化
- **結果**: 228件のTS2307エラーが0件に。224テストで3層整合を常時保証
- **適用条件**: モノレポで共有パッケージのサブパス import を使用する全プロジェクト
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001
- **クロスリファレンス**: [architecture-monorepo.md](../../aiworkflow-requirements/references/architecture-monorepo.md), [development-guidelines.md](../../aiworkflow-requirements/references/development-guidelines.md)

### [ビルド・環境] TypeScript paths 定義順序制御パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: tsconfig paths に複数のサブパスを定義する際、汎用パスが具体的パスより先にマッチしてしまう
- **アプローチ**: 具体的→汎用の順序で定義（例: `@repo/shared/types/llm/schemas` → `@repo/shared/types/llm` → `@repo/shared/types` → `@repo/shared`）。TypeScript は最初にマッチしたパスを使用するため順序が重要
- **結果**: 全27サブパスが正確に解決される
- **適用条件**: tsconfig paths でサブパスの階層が3レベル以上ある場合
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001

### [ビルド・環境] ソース構造二重性のパスマッピング吸収パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: shared パッケージ内で `types/auth.ts`(ルートレベル) と `src/types/index.ts`(src配下) が混在し、一律の paths 設定では解決不可
- **アプローチ**: 両系統を個別にマッピング。ルートレベル→直接参照、src配下→src/ 経由参照。package.json exports のエントリとの1:1対応を確認
- **結果**: 2系統のソース構造を透過的に扱える paths 設定が完成
- **適用条件**: パッケージ内でソースレイアウトが歴史的経緯で混在している場合
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001

### [テスト] 整合性テスト駆動の設定管理パターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: exports/paths/alias の4ファイル同期が手動で漏れやすく、CI で初めてエラーが検出される
- **アプローチ**: 3スイート（module-resolution.test / shared-module-resolution.test / vitest-alias-consistency.test）のテストで設定間の整合性を自動検証。exports↔tsup、paths↔exports、alias↔paths の各対応をテストで固定化
- **結果**: サブパス追加時にテストが即座に不整合を検出。224テストで多角的に保証
- **適用条件**: 複数の設定ファイルが同期を必要とするモノレポ構成
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001
- **クロスリファレンス**: [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md)

### [UI] Props駆動Atoms設計（Store Hooks無限ループ対策）（TASK-UI-00-ATOMS）

- **状況**: UIコンポーネント（Atoms層）の新規作成で、Zustand Storeに依存させるか検討
- **アプローチ**: Atoms層をZustand Storeに依存させず、全コンポーネントをprops駆動で設計。状態管理はPages/Organisms層が担当
- **結果**: P31（Store Hooks無限ループ）のリスクを完全排除。テスト記述が大幅に簡素化（Storeモック不要、props渡しのみで動作検証）
- **適用条件**: Atomic Design の Atoms/Molecules 層のコンポーネント実装時
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../rules/06-known-pitfalls.md), [arch-state-management.md](../../aiworkflow-requirements/references/arch-state-management.md)

### [UI] Record型バリアント定義＋モジュールスコープ抽出（TASK-UI-00-ATOMS）

- **状況**: 複数バリアントを持つコンポーネント（Badge 6色、SkeletonCard 3種等）で、スタイルマッピングの型安全性とパフォーマンスを両立
- **アプローチ**: `Record<NonNullable<Props["variant"]>, string>` でスタイルマッピングを定義し、モジュールスコープに配置。新規バリアント追加時はRecord型に自動的にキーが追加される
- **結果**:
  - TypeScript型チェックで新規バリアント追加時のコンパイルエラー検出（スタイル定義漏れ防止）
  - React.memoの効果最大化（レンダリング毎のオブジェクト再生成を防止）
  - コードレビューで「このバリアントのスタイルは？」と探す手間が削減
- **適用条件**: 2つ以上のバリアントを持つUIコンポーネント
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS

```typescript
// モジュールスコープに配置（レンダリング毎の再生成を防止）
const variantStyles: Record<NonNullable<BadgeProps["variant"]>, string> = {
  default: "bg-gray-100 text-gray-800",
  primary: "bg-blue-100 text-blue-800",
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  error: "bg-red-100 text-red-800",
  info: "bg-indigo-100 text-indigo-800",
};

// 新しいバリアント "secondary" を Props に追加すると、
// variantStyles に "secondary" キーがないとTypeScriptエラーが発生
```

### [Testing] テーマ横断テスト（describe.each パターン）（TASK-UI-00-ATOMS）

- **状況**: 3テーマ（kanagawa-dragon/light/dark）対応コンポーネントのテストで、テーマ毎に同じテストケースを繰り返し記述
- **アプローチ**: `describe.each(["light", "dark", "kanagawa-dragon"])` でテーマ毎のテストを自動生成。各テーマで `data-theme` 属性を設定し、CSS変数ベースのスタイルをテスト
- **結果**:
  - テーマ追加時にテストケースが自動的に増加（新テーマを配列に追加するだけ）
  - 保守コスト最小化（テストロジックは1箇所のみ）
  - テーマ毎の差分が可視化される（どのテーマで失敗したかが明確）
- **適用条件**: デザイントークン（CSS変数）ベースのテーマ対応コンポーネント
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS

```typescript
describe.each(["light", "dark", "kanagawa-dragon"] as const)(
  "Theme: %s",
  (theme) => {
    it(`should render with ${theme} theme`, () => {
      const { container } = render(<Badge />, {
        wrapper: ({ children }) => (
          <div data-theme={theme}>{children}</div>
        ),
      });
      expect(container.firstChild).toHaveAttribute("data-theme", theme);
    });
  }
);
```

### [CI/ビルド] CIガードスクリプトによるモノレポ設定ファイル整合性自動検証（TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001）

- **状況**: モノレポの共有パッケージ（@repo/shared）で exports/paths/alias/typesVersions の4設定ファイルの同期漏れが発生し、228件のエラーを引き起こした
- **アプローチ**:
  1. **パーサー分離**: 各設定ファイル（JSON/TypeScript）に専用パーサーを作成（parseExports, parsePaths, parseAliases, parseTypesVersions）
  2. **双方向チェック**: exports→paths と paths→exports の両方向で整合性を検証。「追加忘れ」と「削除忘れ」を同時検出
  3. **キー変換ヘルパー**: 4種類のキー形式（`./utils`, `@repo/shared/utils`, `utils`）の相互変換を3ヘルパー関数で標準化
  4. **CIジョブ統合**: `check-module-sync` ジョブを build の前提条件として配置し、不整合時は build をブロック
  5. **process.exitCode**: `process.exit(1)` ではなく `process.exitCode = 1` でテスタビリティを確保
- **結果**: CI上で設定ファイル不整合を即座に検出。43テストで5チェック×正常/異常/エッジケースを網羅
- **適用条件**: モノレポで共有パッケージの設定ファイル間整合性を自動保証したい場合
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001
- **クロスリファレンス**: [quality-requirements.md](../../aiworkflow-requirements/references/quality-requirements.md), [architecture-monorepo.md](../../aiworkflow-requirements/references/architecture-monorepo.md), [lessons-learned.md](../../aiworkflow-requirements/references/lessons-learned.md)

### [CI/ビルド] 正規表現ベースTypeScript設定ファイルパーサー（TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001）

- **状況**: vitest.config.ts の `resolve.alias` 設定を抽出する必要があるが、TypeScriptファイルのためJSON.parse()が不可能
- **アプローチ**:
  1. `resolve(__dirname, "path")` パターンに特化した正規表現を設計
  2. ダブルクォート前提・シングルクォート非対応・コメント非対応の制約を明文化
  3. タブ/スペース混在、マルチライン、0件パース時の警告出力をテストで固定化（#29-32）
  4. 正規表現の `lastIndex` リセット問題を回避するため、都度 `exec` ループを使用
- **結果**: vitest.config.ts から @repo/shared 関連のalias定義を正確に抽出。制約はテストで明示的に文書化
- **適用条件**: TypeScript設定ファイル（vitest.config.ts, jest.config.ts等）から特定パターンの設定値を抽出する場合
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001

### [IPC] IPCチャネル名競合の予防的解消パターン（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: 既存 `skill:import`（ローカル用、引数: `string`）と TASK-9F の外部ソースインポート（引数: `ShareTarget`）が同一チャネル名を使用する設計で、`ipcMain.handle()` の二重登録例外（P5）が実装段階で100%発生する構造的問題
- **アプローチ**: コード実装前に仕様書段階でチャネル名を分離する「予防的仕様書修正」
  - 命名規則を体系化: `skill:{動詞}` / `skill:{動詞}FromSource` / `skill:{動詞}Source`
  - 2つの仕様書（task-022, task-030）を同時修正し、6箇所のチャネル名を統一変更
  - grep ベースの整合性検証（10項目）で修正漏れを検出
- **結果**: Phase 10 最終レビュー PASS（MINOR 0件）、Phase 11 手動テスト 11/11 PASS。TASK-9F 実装時の P5 リスクを仕様段階で排除
- **適用条件**: 既存チャネルと同じ動詞を使う新機能を追加する場合。特に引数型が異なる場合は必須
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001
- **クロスリファレンス**:
  - [architecture-implementation-patterns.md#IPCチャネル名競合予防パターン](../../aiworkflow-requirements/references/architecture-implementation-patterns.md)
  - [06-known-pitfalls.md#P5](../../rules/06-known-pitfalls.md)
  - [06-known-pitfalls.md#P44](../../rules/06-known-pitfalls.md)

### [Phase12] 仕様書修正のみタスクの Phase テンプレート（N/A記録）（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: コード変更を伴わない仕様書修正タスクで、Phase 6（テスト拡充）・7（カバレッジ）・8（リファクタリング）が不要
- **アプローチ**: 各 Phase に `not-applicable.md` を作成し、N/A 理由を明記
  - Phase 6: 「代替検証」セクションで grep 検証が唯一のテスト手段であることを記録
  - Phase 7-8: N/A 理由のみ記録
  - Phase 4 の grep コマンドが実質的なテストスイートとして機能
  - Phase 9 は grep ベースの品質ゲート4項目（整合性・新チャネル・既存互換・Markdown構文）で代替
- **結果**: 全 Phase 1-12 で成果物が outputs/ 配下に出力され、仕様書修正のみタスクの標準フローとして先例を確立
- **適用条件**: `taskType: "spec-only"` または `taskType: "spec_created"` のタスク
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001

### [Testing] grepベース仕様書整合性検証（仕様書TDD）（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: コード変更がないため Vitest/ESLint 等の標準ツールが使えず、仕様書修正の品質保証手段が必要
- **アプローチ**: Phase 4 で grep 検証コマンドを「テストケース」として設計し、Phase 5 実装後に全実行
  - 旧チャネル名残存検出（期待: 0件）
  - 新チャネル名使用確認（期待: N件以上）
  - 既存互換性検証（ローカル用 `skill:import` が保持されていること）
  - artifacts.modifies の正確性検証
  - Markdown テーブル構文検証
- **結果**: 10検証項目全 PASS。Phase 9 品質ゲートでも同じ grep コマンドを再利用して4ゲート全 PASS
- **適用条件**: 仕様書修正のみタスク、または複数仕様書の横断的一貫性を検証する場合
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001

### [IPC] P42準拠バリデーション一括移行（return→throw統一）（UT-FIX-SKILL-VALIDATION-CONSISTENCY-001）

- **状況**: 6つのIPCハンドラ（skill:get-detail, skill:execute, skill:abort, skill:get-status, skill:analyze, skill:improve）で異なるバリデーションパターンが混在（return false/return null/return { success: false }/throw の4種類）
- **アプローチ**: `typeof arg !== "string" || arg.trim() === ""` + `throw { code: "VALIDATION_ERROR" }` の統一パターンを全ハンドラに適用
  - オブジェクト型引数（`args.skillId`等）: 4ハンドラ
  - 直接引数型（`executionId`）: 2ハンドラ
  - 全ハンドラでエラー応答を `return` から `throw` に統一
- **結果**: 59テスト追加（skillHandlers.validation.test.ts）、181テスト全PASS。safeInvokeがRenderer側でthrowをキャッチするため後方互換性維持
- **適用条件**: IPCハンドラのバリデーションパターンが不統一で、P42準拠への一括移行が必要な場合
- **教訓**: throw統一はRenderer側のsafeInvoke設計に依存するため、Preload層の実装を事前確認する。safeInvokeがtry/catchでエラーをラップしている場合のみ、return→throw移行が安全
- **発見日**: 2026-02-24
- **関連タスク**: UT-FIX-SKILL-VALIDATION-CONSISTENCY-001
- **関連Pitfall**: P42（.trim()バリデーション漏れ）、P44（IPC引数不整合）

### [Testing] 引数形式差異の分類と共通化判断（YAGNI）（UT-FIX-SKILL-VALIDATION-CONSISTENCY-001）

- **状況**: 6ハンドラ中4つがオブジェクト型（`args.skillId`等）、2つが直接引数型（`executionId`）で、共通バリデーション関数の抽出を検討
- **アプローチ**: 引数アクセスパターンの違い（`args.skillId` vs `executionId`）により、共通関数では引数抽出ロジックまでカバーする必要があり、抽象化コストが利益を上回ると判断。インライン3行バリデーションを各ハンドラに一貫して適用
- **結果**: 各ハンドラが独自の引数アクセスパターンを保持しつつ、バリデーションロジック自体は統一。59テストで正確性を保証
- **適用条件**: 複数ハンドラのバリデーション統一時、引数形式が異なる場合
- **教訓**: YAGNI原則 — 引数形式が統一されるまで共通関数を作らない。3行のインラインバリデーションは許容範囲。将来引数形式が統一された際に初めて共通関数を抽出する
- **発見日**: 2026-02-24
- **関連タスク**: UT-FIX-SKILL-VALIDATION-CONSISTENCY-001

### [Phase 12] 仕様書修正タスクの簡略Phase適用

- **状況**: コード変更なしの仕様書修正タスク（UT-IPC-DATA-FLOW-TYPE-GAPS-001）で、Phase 4-7-11が本来の意味（ユニットテスト、カバレッジ、UIテスト）と合致しなかった
- **アプローチ**:
  - Phase 4: grep正規表現パターンによる検証基準設計（49項目）
  - Phase 5: 仕様書修正実行（7ファイル、28修正項目）
  - Phase 6-7: grepベース整合性検証（24項目）+ 網羅性確認（49項目）
  - Phase 11: 実装者視点レビュー（3視点×3ケース = 9テスト）
- **結果**: 173検証項目ALL PASS。コード変更なしでも品質保証を別手段で実現
- **適用条件**: 仕様書修正のみタスク、ドキュメント横断修正タスク
- **教訓**: 各Phaseを「N/A」で飛ばすのではなく、同等の品質保証を別手段で設計すべき
- **発見日**: 2026-02-24

### [IPC] IPC Date→ISO 8601統一（仕様書段階での予防）

- **状況**: 4ファイル×14フィールドのDate型がIPC境界でのシリアライズ方針未定義だった
- **アプローチ**:
  - 全Date型フィールドに `string; // ISO 8601` 注記を追加
  - Main Process側の `.toISOString()` 変換パターンを仕様書に明記
  - Renderer側の `new Date(isoString)` 復元パターンを仕様書に明記
- **結果**: 後続実装者がIPCシリアライズについて迷う余地を排除
- **適用条件**: IPC境界を越えるDate型フィールドを含む仕様書
- **教訓**: 仕様書段階でIPC型変換ルールを明示しておくことで、実装時のバグを予防できる
- **発見日**: 2026-02-24

### [IPC] ハンドラ Graceful Degradation（safeRegister + track クロージャ）

- **状況**: `registerAllIpcHandlers()` 内で1つのハンドラ登録関数が例外を投げると、後続の全ハンドラが未登録のまま残る
- **アプローチ**:
  - `safeRegister(name, fn)` 内部ヘルパーで個別 try-catch。失敗時は `HandlerRegistrationFailure` を記録して次へ進む
  - `track()` クロージャで成功/失敗カウントを自動管理し、`IpcHandlerRegistrationResult` として集約
  - `sanitizeRegistrationErrorMessage()` でエラーメッセージ中のユーザーホームディレクトリパスを `~` にマスク
  - 戻り値が必要な `setupThemeWatcher` は個別 try-catch で対応（safeRegister 不適合パターンの認識）
- **結果**: 部分的なハンドラ登録失敗時でも、無関係な機能は正常に動作。失敗情報は構造化されて返却
- **適用条件**: 複数の独立した初期化処理を順次実行し、1つの失敗が全体を止めてはいけない場合
- **教訓**:
  - 戻り値キャプチャが必要な場合は `safeRegister` パターンが使えない。設計時に判別が必要
  - `os.homedir()` のパスは正規表現メタ文字を含む可能性があり、`escapeRegExp()` が必須
  - テスト時は `vi.hoisted()` で 30+ のモック変数を宣言し、個別の throw 制御で部分失敗をシミュレート
- **発見日**: 2026-03-08
- **関連タスク**: TASK-FIX-IPC-HANDLER-GRACEFUL-DEGRADATION-001

### [IPC] safeInvoke timeout による IPC hang containment（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: Preload の `safeInvoke()` が `ipcRenderer.invoke()` をそのまま返すため、Main Process 未応答時に Renderer が永続 pending。認証初期化の loading state が落ちず画面遷移が停止
- **アプローチ**:
  - `Promise.race([ipcRenderer.invoke(...), timeoutPromise])` で 5秒タイムアウトを共通適用
  - `IPC_TIMEOUT_MS` をファイルスコープ定数で管理。error 文言に channel 名 + timeout 値を含める
  - whitelist チェックは `Promise.race` の前段で維持し、セキュリティ境界を変更しない
  - `clearTimeout` は省略（5秒タイマーは自動GC。UI頻度のIPC呼び出しでは不要）
- **結果**: 12テスト全PASS、548テスト回帰なし。関数シグネチャ・戻り値の型に変更なし
- **適用条件**: Preload 共通ラッパーで多数の invoke を集約し、Renderer に loading state がある場合
- **苦戦箇所**: contextBridge mock capture パターン（`exposeInMainWorld` キャプチャ + `process.contextIsolated = true`）の発見に試行錯誤。fake timer + module re-import の実行順序（P13準拠）
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [テスト] contextBridge mock capture パターン（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: Preload の `safeInvoke` は `contextBridge.exposeInMainWorld` 経由でのみ公開される。直接 import してもテストできない
- **アプローチ**:
  - `vi.mock("electron")` で `contextBridge.exposeInMainWorld` をキャプチャ関数に差し替え
  - `Object.defineProperty(process, "contextIsolated", { value: true })` で contextBridge パスを強制通過
  - `beforeEach` で `vi.resetModules()` → API キャプチャ変数リセット → `await import("../index")` でクリーンな再初期化
- **結果**: Electron Preload 内部関数の完全なテストが可能に。12テストケースで全分岐をカバー
- **適用条件**: `contextBridge.exposeInMainWorld` で公開される Preload API のユニットテスト全般
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [Phase12] 3workflow再監査 + 未タスク個別監査の二段固定（TASK-FIX-SKILL-IMPORT 3連続是正）

- **状況**: `01/02/03` の3workflowを同時に再監査する際、Phase 12合否（構造/成果物/未タスク）を1回で固定しないと、台帳転記で数値ドリフトが起きやすい
- **アプローチ**:
  1. `verify-all-specs --workflow` を3workflowへ並列実行し、`13/13 PASS` を同時確定する
  2. `validate-phase-output <workflow-dir>` を3workflowへ並列実行し、`28項目 PASS` を同時確定する
  3. UI workflow で `validate-phase11-screenshot-coverage` を実行し、TCカバレッジを固定する
  4. 未タスクは `verify-unassigned-links` と `audit --diff-from HEAD` で全体判定（`current=0`）を確定する
  5. `audit --target-file` は `scope.currentFiles` 一致を確認し、個別判定（`current=0`）として分離記録する
- **結果**: Phase 12 合否の根拠が「3workflow束 + 未タスク全体 + 未タスク個別」の3軸で固定され、再確認時の差し戻しを削減できる
- **適用条件**: 複数workflowを同時に再監査し、未タスクの配置・フォーマットも同ターンで確認する場合
- **教訓**: 合否判定は `currentViolations` を正本に固定し、`baseline` は改善バックログとして分離する
- **発見日**: 2026-03-04
- **関連タスク**: 01-TASK-FIX-SKILL-IMPORTED-STATE-RECONCILIATION-001 / 02-TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001 / 03-TASK-FIX-SKILL-CENTER-METADATA-DEFENSIVE-GUARD-001

### [Phase12] UI再撮影前 preview preflight + 失敗時未タスク化固定（SkillCenter）

- **状況**: UI再撮影の開始後に `ERR_CONNECTION_REFUSED` と module resolve error が発生し、スクリーンショット更新が途中停止した
- **アプローチ**:
  1. `pnpm --filter @repo/desktop preview` を先に実行し、build成否を preflight で判定する
  2. `127.0.0.1:4173` の疎通確認が通った場合のみ `capture-*.mjs` を実行する
  3. 失敗時は再撮影を継続しないで未タスク化し、既存証跡の時刻と代替理由を Phase 12 成果物へ記録する
  4. `validate-phase11-screenshot-coverage` は既存証跡で PASS 維持を確認し、差分監査は `currentViolations=0` を固定する
  5. `phase12-system-spec-retrospective-template` / `phase12-spec-sync-subagent-template` の UIチェックへ preflight 成否と失敗時分岐を転記し、`task-workflow` / `lessons` へ同一ターン同期する
- **結果**: 撮影フロー停止時でも「未タスク化 + 代替証跡記録」で完了判定の再現性を維持できる
- **適用条件**: UI/UX変更タスクで再撮影を要求し、preview 起動失敗が再発し得る場合
- **教訓**: UI再撮影は「preflight成功」が前提条件。前提不成立時は実装修正と運用ガードを分離して扱う
- **発見日**: 2026-03-04
- **関連タスク**: 03-TASK-FIX-SKILL-CENTER-METADATA-DEFENSIVE-GUARD-001 / UT-IMP-SKILL-CENTER-PREVIEW-BUILD-GUARD-001

### [Phase12] UI再確認の準拠チェック成果物固定（TASK-UI-00-ORGANISMS）

- **状況**: UIタスクの再確認で `verify/validate` はPASSでも、Task 1〜5 / Step 1-A〜1-E / Step 2 の判定根拠が複数ファイルへ分散しやすい
- **アプローチ**:
  1. `verify-all-specs` / `validate-phase-output` / `validate-phase11-screenshot-coverage` / `verify-unassigned-links` / `audit --diff-from HEAD` を同一ターンで実行する
  2. UI証跡は `pnpm run screenshot:<feature>` 実行後に `stat` で時刻を取得し、`manual-test-result.md` と同期する
  3. `outputs/phase-12/phase12-task-spec-compliance-check.md` を作成し、Task 1〜5 と Step判定を1ファイルに集約する
  4. `task-workflow.md` と `lessons-learned.md` に実装内容・苦戦箇所・検証値を同時転記する
- **結果**: Phase 12 の再監査根拠が一本化され、証跡鮮度ドリフトと判定漏れを同時に防止できる
- **適用条件**: UI/UX実装タスクのブランチ再確認、または複数文書へ同時同期が必要な Phase 12
- **教訓**: 再確認タスクでは「成果物作成」よりも「判定根拠の集約」が品質を左右する
- **発見日**: 2026-03-04
- **関連タスク**: TASK-UI-00-ORGANISMS

### [Phase12] 実装内容+苦戦箇所の仕様書統一フォーマット（TASK-UI-00-ORGANISMS追補）

- **状況**: system spec へ反映するとき、仕様書ごとに記述粒度が異なり「実装内容はあるが苦戦箇所がない」状態が起きやすい
- **アプローチ**:
  1. `task-workflow` / `<domain-spec>` / `lessons-learned` の順で更新し、仕様書ごとの責務境界を固定する
  2. 各仕様書に `実装内容（要点）` と `苦戦箇所（再発条件付き）` を必須ブロックとして同時記載する
  3. UIタスクは `manual-test-result` と `screenshots/*.png` の時刻整合（`stat`）を必須チェックにする
  4. 検証値（verify/validate/links/audit）は `task-workflow` と `lessons` で同値転記する
- **結果**: 仕様書ごとの記録粒度がそろい、同種課題でそのまま再利用できるテンプレート化が可能になる
- **適用条件**: Phase 12 Step 2 で複数仕様書へ同時反映するタスク
- **教訓**: 「何を実装したか」と「どこで苦戦したか」は同じ粒度で残すほど再利用性が高い
- **発見日**: 2026-03-04
- **関連タスク**: TASK-UI-00-ORGANISMS

### [Phase12] current=0 と baseline backlog の二層管理（TASK-043B）

- **状況**: `audit-unassigned-tasks --diff-from HEAD` では `currentViolations=0` を維持できているが、repository 全体には `baselineViolations>0` が残っており、feature 差分と legacy 負債を混同しやすい
- **アプローチ**:
  1. Phase 12 の feature 合否は `currentViolations=0` を正本に固定する
  2. `baselineViolations>0` が残る場合は、feature バグと混ぜずに `docs/30-workflows/unassigned-task/` 配下へ運用改善未タスクを作成する
  3. 新規未タスク仕様書は `audit-unassigned-tasks --json --target-file <unassigned-file>` で `currentViolations=0` と `scope.currentFiles=1` を確認する
  4. 判定根拠が `spec-update-summary` / `documentation-changelog` / `unassigned-task-detection` / `skill-feedback-report` に分散する場合は `phase12-task-spec-compliance-check.md` を追加し、Task 12-1〜12-5 / Step 1-A〜1-G / Step 2 を 1 ファイルへ集約する
  5. `task-workflow.md` / `lessons-learned.md` / `<domain-spec or ui-ux-feature-components.md>` に同一ターンで「実装内容 + 苦戦箇所 + 簡潔手順」を同期する
- **結果**: feature 実装の完了判定を保ったまま、legacy 負債を隠さず改善 backlog として管理できる
- **適用条件**: Phase 12 再確認で feature 差分は健全だが、未タスク監査の baseline が残る場合
- **教訓**: 未タスク監査は「差分合否」と「運用負債の改善導線」を分けて記録すると再利用性が高い
- **発見日**: 2026-03-06
- **関連タスク**: TASK-043B / UT-IMP-UNASSIGNED-TASK-LEGACY-NORMALIZATION-001

### [Phase12] 同種課題の5分解決カード同期（TASK-UI-00-FOUNDATION-REFLECTION-AUDIT）

- **状況**: 検証値と苦戦箇所は反映済みでも、再実行時の最短手順が仕様書ごとに分散して再利用しづらい
- **アプローチ**:
  1. `task-workflow.md` に再検証値（13/13, 28項目, TC, links, current/baseline）を固定し、「5分解決カード」を追記する
  2. `lessons-learned.md` に同一カード（症状1行/原因1行/最短5手順/検証ゲート）を転記する
  3. UI系タスクでは `ui-ux-feature-components.md` に同一カードを追記し、UI導線へ接続する
  4. 3仕様書で5ステップ順序（実体固定→仕様是正→画面証跡→未タスク監査→台帳同期）が一致していることを最終チェックする
  5. テンプレート（`phase12-system-spec-retrospective` / `phase12-spec-sync-subagent`）へ同カード要件を反映し、次回はテンプレ起点で開始する
- **結果**: 同種課題で調査開始から是正完了までの手順が固定化され、再監査の初動が短縮される
- **適用条件**: Phase 12 Step 2で「実装内容 + 苦戦箇所 + 検証証跡」を複数仕様書へ同期するタスク
- **教訓**: カードは「情報の要約」ではなく「再実行可能な手順の固定」として運用する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] Phase11文書名固定 + TC証跡1:1 + changelog完了記述の三点同期（TASK-10A-F）

- **状況**: Phase 12再監査で、Phase11文書名ドリフト・TC証跡リンク漏れ・`documentation-changelog.md` の計画文残置が同時に発生しやすい
- **アプローチ**:
  1. `validate-phase12-implementation-guide` で Part 1/2、型定義、エッジケース、設定一覧の必須要件を機械検証する
  2. `validate-phase11-screenshot-coverage` と `manual-test-result.md` を突合し、TCごとに証跡を 1:1 固定する（`screenshots/*.png` または `NON_VISUAL:`）
  3. `documentation-changelog.md` は「実更新ログのみ」にし、`予定/計画` の文言を残さない
  4. `task-workflow.md` / `lessons-learned.md` / `<domain-spec>` に「実装内容 + 苦戦箇所 + 検証値」を同一ターンで同期する
  5. 未実施項目は `docs/30-workflows/unassigned-task/` に10見出しテンプレートで起票し、`audit --target-file` で個別検証する
- **結果**: Phase 12の完了判定根拠が揃い、文書名・証跡・進捗表現のドリフトを同時に防止できる
- **適用条件**: 再監査で「実装は完了しているが文書運用に差分」が残るタスク
- **教訓**: Phase 12は「作ること」より「同期を崩さないこと」を完了条件に置く
- **発見日**: 2026-03-07
- **関連タスク**: TASK-10A-F

### [Phase12] comparison baseline 正規化つき branch 再監査（TASK-10A-F）

- **状況**: current workflow は PASS でも、comparison baseline の completed workflow に legacy 名称・欠落補助成果物・古い artifact registry が残ると branch 全体の結論がぶれる
- **アプローチ**:
  1. current workflow に `verify-all-specs --strict` / `validate-phase-output` / `validate-phase12-implementation-guide` を実行する
  2. comparison baseline の completed workflow にも `verify-all-specs --strict` / `validate-phase-output` を実行する
  3. completed workflow に `phase-7-coverage-check.md` / `phase-11-manual-test.md` / `outputs/artifacts.json` / `screenshot-plan.json` / `discovered-issues.md` などの不足があれば同一ターンで補完する
  4. `spec-update-summary.md` / `phase12-task-spec-compliance-check.md` / `task-workflow.md` に current 合格値と baseline 正規化結果を分離記録する
  5. 未タスク監査は `currentViolations=0` を合否、`baselineViolations>0` を legacy 負債として扱い、必要なら正規化ガード未タスクを参照する
- **結果**: 「current は通るが baseline が壊れていて branch verdict が不安定」という状態を防止できる
- **適用条件**: `spec_created` workflow と completed workflow を同時に再監査する Phase 12 タスク
- **発見日**: 2026-03-08
- **関連タスク**: TASK-10A-F

### [Phase12] 並列エージェント台帳同期パターン（TASK-10A-F）

- **状況**: 複数サブエージェントが `artifacts.json` や `outputs/artifacts.json` を独立に更新する
- **問題**: サブエージェントA が Phase 1-3 を completed に更新、メインが Phase 4-10 を更新すると、`outputs/artifacts.json` の Phase 4-10 が pending のまま残る
- **解決策**:
  1. サブエージェントには **読み取り + 検証レポート出力** のみを委譲
  2. 台帳ファイル（`artifacts.json`, `outputs/artifacts.json`, `index.md`）の更新はメインエージェントが一括実行
  3. 更新後に `cp artifacts.json outputs/artifacts.json` で強制同期
  4. `diff artifacts.json outputs/artifacts.json` で同期確認
- **適用条件**: Phase 12 で複数サブエージェントを並列運用する場合
- **教訓**: 台帳ファイルの更新権限を1箇所に集約しないと、並列更新による上書き競合が発生する
- **発見日**: 2026-03-08
- **関連パターン**: P43（サブエージェント rate limit 中断）、S8（lessons-learned.md）
- **関連タスク**: TASK-10A-F

### [Phase12] Store駆動移行の仕様書更新チェックリスト（TASK-10A-F）

- **状況**: 直接IPC呼び出し → Store action 経由への移行完了後の仕様同期
- **チェックリスト**:
  1. `arch-state-management.md` に個別セレクタ一覧と検証結果を追記
  2. `task-workflow.md` の完了台帳を更新（テスト件数・IPC残存0件）
  3. `lessons-learned.md` に苦戦箇所と再利用手順を追加
  4. LOGS.md x2 + SKILL.md x2 の4ファイル更新（P1/P25 準拠）
  5. `generate-index.js` で topic-map / keywords 再生成（P2/P27 準拠）
  6. SubAgent分担: references 仕様書別に独立エージェントで並列更新
- **適用条件**: Store駆動移行タスク（直接IPC → Zustand Store action）の Phase 12 実行時
- **教訓**: Store移行はコード変更より仕様同期の方が工数がかかる。チェックリストで漏れを防止する
- **発見日**: 2026-03-08
- **関連パターン**: S10（P31/P48 標準パターン）、Phase 12 テンプレート
- **関連タスク**: TASK-10A-F

## 失敗パターン（避けるべきこと）

失敗から学んだアンチパターン。

### [Phase12] 成果物名の暗黙的解釈

- **状況**: Phase 12で`implementation-guide.md`を`documentation.md`として生成
- **問題**: 仕様書との不整合、後続処理でのファイル参照エラー
- **原因**: 仕様書の成果物名を正確に確認せず暗黙的に命名
- **教訓**: Phase仕様書の「成果物」セクションを必ず確認し、ファイル名を厳密に一致させる
- **発見日**: 2026-01-22

### [Phase12] 実装ガイドへの誤ファイル名混入（TASK-FIX-14-1）

- **状況**: 実装ガイドに `SkillPermissionService.ts` など実差分に存在しないファイル名を記載
- **問題**: レビューと再現手順が実装事実と一致せず、監査で差し戻しが発生
- **原因**: 実差分参照を省略し、過去の想定ファイル名を転記
- **教訓**: Phase 12のファイル一覧は必ず `git diff` を一次情報として確定し、成果物と突合する
- **対策**: 文章確定前に「記載ファイル名 ⊆ git差分一覧」の機械チェックを追加
- **発見日**: 2026-02-14
- **関連タスク**: TASK-FIX-14-1-CONSOLE-LOG-MIGRATION

### [Phase12] Phase 12サブタスクの暗黙的省略

- **状況**: Phase 12完了時に「実装ガイド作成」のみ実行し、「システム仕様書更新」を省略
- **問題**: システム仕様書に完了記録が残らず、成果が追跡できない
- **原因**: Phase 12が複数サブタスク（12-1, 12-2, 12-3）を持つことの認識不足
- **教訓**: Phase 12実行時は必ずサブタスク一覧を確認し、全タスクの実行を確認する
- **発見日**: 2026-01-22
- **対策済み**: phase-templates.md v7.6.0で完了条件チェックリストを強化

### [Phase12] 仕様書作成タスクの completed 誤判定

- **状況**: 実装未着手の仕様書タスクを `completed` と登録
- **問題**: 「仕様書完了」と「実装完了」が混同し、進捗台帳の意味が崩れる
- **原因**: Step 1-B の判定ルールが `未実装→完了` の単一ルールになっていた
- **教訓**: 実装未着手タスクでは `spec_created` を使い、`completed` を使わない
- **対策**: spec-update-workflow に判定分岐（`completed` / `spec_created`）を明文化する
- **発見日**: 2026-02-19
- **関連タスク**: TASK-9A-C

### [Phase12] 全体ベースライン違反の今回起因誤判定

- **状況**: 全体監査で多数違反が出た際、対象タスクの新規差分と既存負債を分離せずに「今回の不備」と判定してしまう
- **問題**: 本来不要な大規模修正を誘発し、今回タスクの完了判断が遅延する
- **原因**: 監査スコープ（repo-wide）とレビュー対象（今回差分）の境界を定義していない
- **教訓**: Phase 12報告では「全体件数」と「対象ファイル件数」を必ず別指標で提示する

### [Phase12] Phase11文書名ドリフトとTC証跡未同期を放置（TASK-10A-F）

- **状況**: `phase-11-execution.md` と実体ドキュメント名がずれたまま、TC証跡が `manual-test-result.md` とリンクしない状態で完了判定した
- **問題**: `validate-phase11-screenshot-coverage` / `validate-phase12-implementation-guide` は通るが、実運用で参照追跡が困難になる
- **原因**: 実装要件の検証結果だけを見て、文書間参照と changelog の完了記述まで確認しなかった
- **教訓**: Phase 12完了前に「文書名固定」「TC証跡1:1」「changelog完了記述」の三点を機械検証 + 目視確認する
- **対策**: 未解決項目は即時に `docs/30-workflows/unassigned-task/` へ起票し、`task-workflow/lessons` へ同ターン反映する
- **発見日**: 2026-03-07
- **関連タスク**: TASK-10A-F

### [Phase12] current workflow PASS だけで comparison baseline を放置

- **状況**: current workflow の validator だけ通し、comparison baseline の completed workflow は未確認のまま branch 全体の結論を書く
- **問題**: baseline 側の legacy drift が比較結果へ混入し、再監査ごとに結論が変わる
- **原因**: 「履歴保管先だから strict 検証不要」という誤判断で completed workflow の正規化を省略する
- **教訓**: comparison baseline を使うなら current と同じ粒度で validator を通してから比較する
- **対策**: `verify-all-specs --strict` / `validate-phase-output` を current と completed の両workflowへ実行し、結果を分離記録する
- **発見日**: 2026-03-08
- **関連タスク**: TASK-10A-F
- **対策**: 監査テンプレートに「baseline / scope-of-change」2列を追加し、対象ファイルの個別検証結果を併記する
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001

### [Phase12] spec_created/完了workflow混在時の証跡分散

- **状況**: spec_createdタスクと完了タスクを同時再監査した際、結果をworkflow単位で整理せずに記録してしまう
- **問題**: どのworkflowが何を満たしたか追跡できず、Phase 12完了判定が曖昧になる
- **原因**: 監査対象workflowの固定と、Task 1/3/4/5実体突合の対応表を先に作っていない
- **教訓**: 複数workflow監査時は「workflow固定→構造検証→出力検証→成果物突合」の順で記録を統一する
- **対策**: 監査テンプレートに workflow別証跡表を追加し、合否指標は `currentViolations` 固定で記録する
- **発見日**: 2026-03-02
- **関連タスク**: TASK-UI-05A-SKILL-EDITOR-VIEW, TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] 5分解決カードをtask-workflowのみ更新して他仕様へ未同期

- **状況**: `task-workflow.md` には最短手順を追記したが、`lessons-learned.md` と `ui-ux-feature-components.md` への同一カード転記を省略する
- **問題**: 再利用時に参照仕様書ごとに手順が分断され、SubAgent分担の初動が遅れる
- **原因**: 「台帳更新だけで十分」という誤判断で、3仕様書同時同期チェックを省略した
- **教訓**: 5分解決カードは `task-workflow` 単独では成立しない。`task-workflow + lessons + domain/UI spec` の3点同期が必要
- **対策**: `phase12-system-spec-retrospective-template` と `phase12-spec-sync-subagent-template` の完了チェックに「3仕様書同一カード」を必須化する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] UI再撮影後にTCカバレッジ検証を省略

- **状況**: スクリーンショットを再取得して `ls` だけ確認し、TC紐付け検証（coverage validator）を実施せず完了判定する
- **問題**: 画像枚数が揃っていても TC欠落や命名不一致を見逃し、`manual-test-result` の証跡信頼性が低下する
- **原因**: 「再撮影」と「TC紐付け検証」を別工程として扱い、後者を必須化していない
- **教訓**: UI証跡は「再撮影 + TCカバレッジ検証 + 更新時刻確認」の3点セットで完了判定する
- **対策**: `validate-phase11-screenshot-coverage.js --workflow <workflow-path>` を Phase 12 標準コマンドへ追加し、`PASS` を台帳へ転記する
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C

### [Phase12] preview成否確認なしで再撮影開始（ERR_CONNECTION_REFUSED）

- **状況**: 再撮影コマンドを先に起動し、`preview` build 失敗（module resolve error）に気づかず `ERR_CONNECTION_REFUSED` で停止する
- **問題**: 画面証跡更新が途中で止まり、Phase 11/12 の完了判定が「撮影未実施」か「実行不能」か曖昧になる
- **原因**: `preview` 起動可否を前提チェックに含めず、撮影スクリプトを直接実行している
- **教訓**: UI再撮影の必須前提は `preview preflight`。前提未成立時は未タスク化して運用課題を切り出す
- **対策**: `pnpm --filter @repo/desktop preview` の build成否 + `127.0.0.1:4173` 疎通を記録してから撮影し、失敗時は `UT-IMP-SKILL-CENTER-PREVIEW-BUILD-GUARD-001` へ即時登録する。あわせて Phase 12 テンプレート（`phase12-system-spec-retrospective` / `phase12-spec-sync-subagent`）の UI完了チェックにも preflight 分岐を必須記録する
- **発見日**: 2026-03-04
- **関連タスク**: 03-TASK-FIX-SKILL-CENTER-METADATA-DEFENSIVE-GUARD-001

### [Phase12] preview/search を feature spec のみに閉じて cross-cutting spec を未同期

- **状況**: `ui-ux-feature-components.md` と `task-workflow.md` だけを更新し、`ui-ux-search-panel.md` / `ui-ux-design-system.md` / `error-handling.md` / `architecture-implementation-patterns.md` を未同期のまま完了扱いにする
- **問題**: shortcut、dialog token、error severity、renderer fallback の参照先が分断され、次回の類似タスクで同じ判断をやり直すことになる
- **原因**: UI基本6+αで十分と誤認し、preview/search 固有の cross-cutting 追加仕様を判定していない
- **教訓**: preview/search 系 UI は feature spec だけでは閉じない。検索挙動、token、error contract、実装パターンを別仕様へ振り分ける必要がある
- **対策**: `phase12-system-spec-retrospective-template` と `phase12-spec-sync-subagent-template` に cross-cutting matrix を追加し、該当4仕様書の同一ターン更新を完了条件にする
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-04C-WORKSPACE-PREVIEW

### [Phase12] Port 5174 競合ログ混在を未記録のまま完了判定

- **状況**: screenshot 再取得は成功したが `Port 5174 is already in use` が同時出力され、警告を未記録のまま完了扱いにしやすい
- **問題**: 実行可否の判定根拠が曖昧になり、再監査時に「成功なのか環境エラーなのか」の説明コストが増える
- **原因**: screenshot 実行前のポート占有確認手順と競合時分岐（停止/再利用）の記録要件がテンプレートに固定されていない
- **教訓**: UI再撮影では preflight に「preview成否 + ポート占有」を含め、競合時の判断ログを必ず残す
- **対策**: `lsof -nP -iTCP:5174 -sTCP:LISTEN || true` を再撮影前に実行し、競合時は `spec-update-summary.md` に分岐結果を記録したうえで `UT-IMP-PHASE12-SCREENSHOT-PORT-CONFLICT-GUARD-001` を未タスク化する
- **発見日**: 2026-03-04
- **関連タスク**: 02-TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] 別workflow証跡参照のまま `validate-phase11-screenshot-coverage` を実行

- **状況**: `manual-test-result.md` に別workflowの証跡パスのみを記載した状態で validator を実行し、対象workflow配下の `outputs/phase-11/screenshots` が空のまま失敗する
- **問題**: 見かけ上は証跡リンクが存在しても、機械検証では `covered=0` になり Phase 12 完了判定が崩れる
- **原因**: UI証跡を「参照文字列」と「対象workflow配下の実体」で分離管理していない
- **教訓**: coverage validator は対象workflow配下の実体を検証するため、証跡移送/再取得と証跡記法の同期が必須
- **対策**: `outputs/phase-11/screenshots` を対象workflow配下へ正規配置し、視覚TCは `screenshots/*.png`、非視覚TCは `NON_VISUAL:` 記法へ統一してから validator を再実行する
- **発見日**: 2026-03-04
- **関連タスク**: UT-IMP-PHASE12-SCREENSHOT-COMMAND-REGISTRATION-GUARD-001

### [Phase12] SubAgent分担が `spec-update-summary` のみに残る

- **状況**: 分担情報を `spec-update-summary.md` にのみ記録し、`task-workflow.md` の完了節へ転記しない
- **問題**: 完了台帳から責務境界を追跡できず、再監査で「誰が何を同期したか」を再調査する必要が出る
- **原因**: Step 2の成果物更新で台帳側の転記を必須条件にしていない
- **教訓**: 分担情報は「成果物」と「完了台帳」の両方へ残す
- **対策**: Phase 12チェックリストに「task-workflow へのSubAgent分担表転記」を必須項目として追加する
- **発見日**: 2026-03-02
- **関連タスク**: TASK-10A-C

### [Phase12] `--target-file` を「対象のみ出力」と誤解

- **状況**: `audit-unassigned-tasks --target-file` の出力に baseline が含まれ、対象ファイルが fail に見える
- **問題**: current=0 でも過剰修正が発生し、Phase 12完了が遅延する
- **原因**: `--target-file` の仕様（分類モード）を表示フィルタと混同した
- **教訓**: 判定は `currentViolations.total` を正本とし、baseline は別管理する
- **対策**: 監査テンプレートへ `scope.currentFiles` / `currentViolations.total` / `baselineViolations.total` の3項目を固定で記録する
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] 未タスクの存在確認止まり（10見出し未検証）

- **状況**: `verify-unassigned-links` だけを実行して未タスク検証を完了扱いにする
- **問題**: ファイルは存在していても、必須見出し不足や `## メタ情報` 重複を見逃して監査差し戻しが発生する
- **原因**: 配置検証とフォーマット検証を同一チェックとして扱っていた
- **教訓**: 未タスク検証は「存在（links）」と「形式（target監査 + 見出し検証）」の二段で実施する
- **対策**: `audit-unassigned-tasks --target-file` と 10見出しチェックをセット化し、`current=0` + 見出し10/10 + `メタ情報=1` を完了条件にする
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9I, UT-9I-001, UT-9I-002

### [Phase12] `validate-phase-output` の `--phase` 誤用

- **状況**: `verify-all-specs` と同様に `--phase` 指定を試して検証が失敗する
- **問題**: Phase 12再確認でコマンド再実行が増え、証跡同期が遅れる
- **原因**: `validate-phase-output.js` が workflow-dir 位置引数のみ受け付ける仕様を明示していなかった
- **教訓**: Phase検証コマンドは「仕様整合（verify-all-specs）」と「出力構造（validate-phase-output）」で引数形式を明示的に分離する
- **対策**: 実行テンプレートを `validate-phase-output.js docs/30-workflows/<workflow-dir>` に統一する
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] グローバルCLI前提で `not found` / `MODULE_NOT_FOUND` を誘発

- **状況**: `verify-all-specs` / `validate-phase-output` を直接実行し、環境によってコマンド未導入または誤パス解決で失敗する
- **問題**: 再確認の初動で停止し、証跡時刻や台帳同期の再確認が後倒しになる
- **原因**: 検証コマンドの実体探索を省略し、エイリアスの存在を前提にしている
- **教訓**: Phase 12 は「エイリアス」ではなく「スクリプト実体」を正本として実行する
- **対策**: `which <cmd> || true` と `rg --files .claude/skills/task-specification-creator/scripts` で実体確認後、`node .claude/skills/task-specification-creator/scripts/<script>.js` 形式へ統一する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] 監査結果の棚卸し止まり（次アクション未定義）

- **状況**: 監査結果を表やレポートに整理したが、誰が・何を・どの順序で実行するかが未定義のまま完了扱いにした
- **問題**: 次回の着手時に再分析が必要となり、監査結果が実行計画へつながらない
- **原因**: `task-00` 配下の実行導線（優先度/Wave/SubAgent分担）を作成していない
- **教訓**: 監査完了と同時に「次アクション専用ドキュメント」を必ず1枚追加する
- **対策**: Phase 12 完了条件に「監査→実行ブリッジ文書の作成」を追加し、`outputs/phase-12/spec-update-summary.md` から参照する
- **発見日**: 2026-02-25
- **関連タスク**: TASK-013 再監査

### [Phase12] 成果物実体とphase-12実行記録の乖離放置

- **状況**: `outputs/phase-12` のファイルは作成済みだが、`phase-12-documentation.md` の「未実施」行が更新されないまま完了扱いにした
- **問題**: 監査時に「実施済みなのに未実施表示」という矛盾が発生し、完了判定の信頼性が低下する
- **原因**: 成果物実体の確認と、仕様書本体の実行記録更新を別工程で扱っていた
- **教訓**: Phase 12完了判定は「成果物実体 + 実行記録同期」の2条件を同時に満たす必要がある
- **対策**: Task 1〜5突合レポートを必須化し、`phase-12-documentation.md` のチェック欄更新を完了条件へ昇格
- **発見日**: 2026-02-25
- **関連タスク**: UT-UI-THEME-DYNAMIC-SWITCH-001

### [Phase12] Step 1-A 完了タスク記録の欠落

- **状況**: `implementation-guide.md` や `documentation-changelog.md` は作成済みだが、`spec-update-workflow.md` / `phase-11-12-guide.md` に完了タスク記録が追加されていない
- **問題**: 実行手順書上では未完了に見え、Phase 12 の完了判定根拠が分断される
- **原因**: 成果物生成と手順書更新を別担当・別ターンに分離し、Step 1-A の最終チェックが未実施
- **教訓**: Phase 12 Task 2 は「仕様更新」だけでなく「手順書への完了記録」までを同一タスクとして扱う
- **対策**: Step 1-A の完了条件に「完了タスク + 関連ドキュメント + 更新履歴」の3点追記を固定し、`quick_validate.js` 実行前に確認する
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001

### [Phase12] テンプレートに旧環境絶対パスを残す

- **状況**: `quick_validate` などのコマンド例が特定端末の絶対パスで記載され、他環境で実行不能になる
- **問題**: 同じテンプレートでも実行者ごとに手順が分岐し、検証結果の再現性が崩れる
- **原因**: テンプレート更新時に「正規経路（repo相対）」への置換チェックを行っていない
- **教訓**: テンプレートは「誰がどの環境でも実行可能」な相対パス前提で管理する
- **対策**: assets更新時に「絶対パス禁止」と「成果物名最新化」をチェックリストへ追加する
- **発見日**: 2026-02-26
- **関連タスク**: UT-IMP-SKILL-VALIDATION-GATE-ALIGNMENT-001

### [Phase12] 仕様書更新の単独進行による同期漏れ

- **状況**: `interfaces` 更新後に `security`/`task-workflow`/`lessons` の反映が遅れ、仕様書間で契約状態がずれる
- **問題**: 実装は完了していても監査時に仕様不整合として差し戻しが発生する
- **原因**: 仕様書ごとの責務分担と同時更新ルールが未定義
- **教訓**: 横断仕様更新は単一担当で逐次進行せず、SubAgent分担で同一ターン同期する
- **対策**: `assets/phase12-spec-sync-subagent-template.md` で担当/完了条件/検証コマンドを固定し、4仕様書を一括更新する
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [Phase12] 未タスク指示書メタ情報の二重定義
### [Phase12] api-ipc仕様を同期対象から除外

- **状況**: interfaces と security を更新して完了扱いにしたが、`api-ipc-agent.md` のチャネル契約更新を省略する
- **問題**: 実装済みチャネルの request/response/Preload対応が仕様書に残らず、後続実装が誤った契約を参照する
- **原因**: SubAgent分担が4仕様書前提で固定され、api-ipc が責務表から抜けていた
- **教訓**: IPC系タスクでは `api-ipc` を必須仕様書に含めた5仕様書同期が必要
- **対策**: `phase12-spec-sync-subagent-template.md` の分担を `A:interfaces / B:api-ipc / C:security / D:task-workflow / E:lessons` に固定し、完了チェックで5仕様書同時更新を必須化する
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J

### [Phase12] IPC契約ドキュメントを概要のみで確定

- **状況**: 未タスク指示書で `## メタ情報` を2回定義し、YAMLと表を別セクションに分離した
- **問題**: フォーマット監査でノイズが増え、修正対象の切り分けが遅れる
- **原因**: YAML追加時に既存メタ情報テーブルとの統合ルールが明文化されていなかった
- **教訓**: メタ情報は「1セクション原則」を守り、YAMLと表を同一セクションで管理する
- **対策**: `unassigned-task-guidelines.md` に重複禁止ルールを追加し、`rg -n "^## メタ情報"` を定期監査に組み込む
- **発見日**: 2026-02-26
- **関連タスク**: TASK-9A-skill-editor

### [Phase12] IPCハンドラ実装のみで登録配線を未確認

- **状況**: `skillAnalyticsHandlers.ts` のような専用ハンドラを追加したが、`ipc/index.ts` の `register*Handlers()` 呼び出し追加を見落とす
- **問題**: テストが部分的にPASSでも、実ランタイムでチャネルが未登録となり機能が使用できない
- **原因**: 実装完了の判定を「ハンドラファイル作成」で止め、起動経路まで検証していない
- **教訓**: IPC機能の完了条件は「実装 + 登録 + Preload公開」の3点セットで判定する
- **対策**: Phase 12チェックリストに「`ipc/index.ts` の登録配線確認」を追加し、回帰テストに登録確認ケースを含める
- **発見日**: 2026-02-28
- **関連タスク**: TASK-9J

### [Phase12] timeout待機APIへの停止副作用混在（TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001）

- **状況**: timeout ハンドラ内で `stop()` を直接呼び、待機失敗処理と停止処理を1つの責務にしてしまう
- **問題**: 終了順序が競合し、ワーカー終了やテストクリーンアップで不安定な失敗が再発する
- **原因**: wait API（結果を返す責務）と stop API（ライフサイクル責務）の境界が未定義
- **教訓**: timeout系APIは副作用を持たせず、停止は呼び出し側の明示責務として分離する
- **対策**:
  1. timeout ハンドラから stop/close を排除する
  2. stop API を idempotent（未起動/停止済みガード）に統一する
  3. timeout テストに `await stop()` を必須化する
  4. `security` / `task-workflow` / `lessons` へ同一内容を同時同期する
- **発見日**: 2026-02-28
- **関連タスク**: TASK-FIX-AUTH-CALLBACK-SERVER-WORKER-EXIT-001

### [Phase12] task-workflow のみ更新で lessons-learned 同期漏れ（TASK-UI-05）

- **状況**: 完了台帳（`task-workflow.md`）へ実装要点と未タスクを記録したが、`lessons-learned.md` への苦戦箇所転記を後回しにした
- **問題**: 再利用時に「何を実装したか」は追えるが「なぜ苦戦したか・次にどう避けるか」が欠落し、同じ調査を繰り返す
- **原因**: Phase 12 Step 2 を「仕様同期」と「教訓同期」に分離せず、完了条件を片側更新で満たしたと誤認した
- **教訓**: 仕様更新は `task-workflow` と `lessons-learned` を同一ターンで更新しない限り完了扱いにしない
- **対策**:
  1. `task-workflow.md` 更新時点で `lessons-learned.md` の追記見出しを同時作成する
  2. 検証証跡（verify/validate/links/audit）を2ファイルへ同一値で転記する
  3. `SKILL.md` 変更履歴に「台帳 + 教訓 同時同期」を明示し、レビュー時のチェック項目に固定する
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] UIタスクに5仕様書テンプレートを誤適用

- **状況**: UI中心の実装タスクに対して `interfaces/api-ipc/security/task/lessons` の5仕様書テンプレートのみで同期を進める
- **問題**: `ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` の更新漏れが発生し、UI仕様の正本が古いまま残る
- **原因**: タスク種別（UI機能実装）に応じた仕様書プロファイルの切替ルールがテンプレートに明示されていなかった
- **教訓**: Phase 12テンプレートはタスク種別ごとにプロファイル選択（標準5仕様書 / UI6仕様書）を先に確定する
- **対策**:
  1. `phase12-system-spec-retrospective-template.md` に UI機能6仕様書プロファイルを追加する
  2. `phase12-spec-sync-subagent-template.md` に UI向けSubAgent分担表を追加する
  3. 完了チェックへ「プロファイル選択明記」を追加する
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] UI基本6仕様書だけ更新して domain UI spec を未同期（TASK-UI-02）

- **状況**: `ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` / `task-workflow` / `lessons` は更新したが、`ui-ux-navigation.md` のようなドメイン固有 UI 正本が古いまま残る
- **問題**: UI index/detail/state は新しいのに、機能固有の正本が stale となり、再利用時に情報が分散する
- **原因**: UI6仕様書プロファイルを「基本セット」ではなく「全量セット」と誤解し、domain add-on spec を追加判定していなかった
- **教訓**: UI Phase 12 は `UI6 + domain-ui-spec` の可変プロファイルで扱い、domain spec がある限り 1仕様書=1SubAgent を追加する
- **対策**:
  1. 実装開始時に `rg -n "TASK-UI-02|<feature>|<domain>" .claude/skills/aiworkflow-requirements/references/ui-ux-*.md` で domain UI spec の有無を先に確認する
  2. 見つかった domain spec（例: `ui-ux-navigation.md`）を `SubAgent-G+` として分担表へ追加する
  3. `task-workflow.md` / `lessons-learned.md` / `<domain-ui-spec>.md` の3点に実装内容・苦戦箇所・再利用手順を同一ターンで転記する
  4. 完了チェックへ「UIドメイン固有正本の同時更新」を追加し、6仕様書だけで完了扱いにしない
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-02-GLOBAL-NAV-CORE

### [Skill] 全リソース一括読み込み

- **状況**: スキル実行開始時に全ファイルを読み込んだ
- **問題**: コンテキストウィンドウを圧迫し、精度低下
- **原因**: Progressive Disclosure 原則の未適用
- **教訓**: 必要な時に必要なリソースのみ読み込む
- **発見日**: 2026-01-10

### [Skill] LLMでのメトリクス計算

- **状況**: 成功率や実行回数をLLMに計算させた
- **問題**: 計算ミスが発生、信頼性低下
- **原因**: Script First 原則の未適用
- **教訓**: 決定論的処理は必ずスクリプトで実行
- **発見日**: 2026-01-08

### [Build] スクリプトでのデータ形式前提の誤り

- **状況**: generate-documentation-changelog.jsがartifacts.jsonを解析してエラー発生
- **問題**: `TypeError: The "path" argument must be of type string. Received undefined`
- **原因**: スクリプトは`{path, description}`オブジェクト形式を想定したが、実際は文字列配列形式だった
- **教訓**: スクリプト作成時は実際のデータ形式を確認し、複数形式に対応するか明確に文書化する
- **対策**: `typeof artifact === "string" ? artifact : artifact.path` で両形式に対応
- **発見日**: 2026-01-22
- **関連タスク**: skill-import-store-persistence (SKILL-STORE-001)

### [Phase12] 「検証タスク」でのPhase 12 Step 1省略

- **状況**: SHARED-TYPE-EXPORT-03（検証タスク）でPhase 12 Step 1を「検証タスクなので更新不要」と判断し省略
- **問題**: spec-update-record.mdに「更新不要」と記載したが、Step 1は必須要件だった
- **原因**: Step 1（タスク完了記録：必須）とStep 2（インターフェース仕様更新：条件付き）の区別を誤認
- **教訓**: Phase 12 Step 1（完了タスクセクション追加、実装ガイドリンク追加、変更履歴追記）は**検証タスクでも必須**
- **対策**:
  - task-specification-creator SKILL.mdに「【検証タスクでも必須】」警告を追加
  - validate-phase12-step1.js検証スクリプトで自動チェック
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03

### [Phase 12] 正規表現パターンのPrettier干渉

- **状況**: Phase 12 Task 1で実装ガイド・IPCドキュメント作成時、TypeScript型表記を含むMarkdownファイルを生成
- **問題**: PostToolUseフック（auto-format.sh）のPrettierが、Markdownコードブロック内のTypeScript型表記（`readonly ["task-spec", "skill-spec", "mode"]`）を `readonly[("task-spec", "skill-spec", "mode")]` のように変形
- **原因**: PrettierのMarkdownフォーマッターがコードブロック内のTypeScript構文を解釈し、独自のフォーマットルールを適用
- **教訓**: ドキュメント生成タスクでは、PostToolUseフックの自動フォーマット後にコードブロック内の表記を検証する後処理ステップが必要。特に `as const` アサーション付きの型表記は変形されやすい
- **発見日**: 2026-02-12
- **対策**: バックグラウンドエージェント内でWrite後にReadで検証し、変形があればEditで修正するステップを組み込む

### [Build] ES Module互換性の確認漏れ

- **状況**: 新規スクリプト（validate-phase12-step1.js）作成時にCommonJS構文（require）を使用
- **問題**: プロジェクトがES Module（"type": "module"）設定のため実行時エラー
- **原因**: package.jsonの"type"フィールドを確認せずスクリプト作成
- **教訓**: 新規スクリプト作成時は必ずプロジェクトのモジュール形式を確認し、ES Module形式（import/export）を使用
- **対策**: スクリプト作成前に `package.json` の `"type"` フィールドをチェック
- **発見日**: 2026-01-23
- **関連タスク**: SHARED-TYPE-EXPORT-03

### [SDK] カスタム declare module と SDK 実型の共存（TASK-9B-I）

- **状況**: SDK 未インストール時にカスタム `declare module` を作成し、SDK インストール後もファイルが残留
- **問題**: TypeScript は `node_modules` の実型を優先し、カスタム `.d.ts` は無視されるが、仕様書にカスタム型の値が残って型不整合が発生
- **原因**: SDK インストール前後で型定義ファイルの優先順位が変わることの認識不足
- **教訓**: SDK インストール後はカスタム `.d.ts` を削除する。TypeScript のモジュール解決優先順位（`node_modules` > カスタム `.d.ts`）を文書化しておく
- **対策**: SDK バージョンアップ時にカスタム型定義ファイルの棚卸しを実施
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-I-SDK-FORMAL-INTEGRATION, UT-9B-I-001

### [Phase12] 未タスク配置ディレクトリの混同（TASK-9B-I）

- **状況**: 未タスク (UT-9B-I-001) の指示書を親タスクの `tasks/` ディレクトリに誤配置
- **問題**: `docs/30-workflows/unassigned-task/` ではなく `docs/30-workflows/skill-import-agent-system/tasks/` に配置してしまった
- **原因**: 未タスク指示書の配置先ルールの確認不足。親タスクディレクトリと未タスクディレクトリの混同
- **教訓**: 未タスクは必ず `docs/30-workflows/unassigned-task/` に配置する。配置後に `ls` で物理ファイルの存在を検証する
- **対策**: 未タスク作成時に配置ディレクトリを明示的に確認するチェックリスト項目を追加
- **発見日**: 2026-02-12
- **関連タスク**: TASK-9B-I-SDK-FORMAL-INTEGRATION

### [Phase12] 未タスクの「配置・命名・9セクション」同時是正（TASK-9F）

- **状況**: 未タスク6件を検出したが、`docs/30-workflows/completed-tasks/skill-share/unassigned-task/` に簡易フォーマットで配置していた
- **問題**: `docs/30-workflows/unassigned-task/` 正本運用と不一致となり、`audit-unassigned-tasks` の `current` 判定と台帳整合が崩れた
- **原因**:
  - 親ワークフロー配下のローカル運用を優先し、共通ガイドライン（配置先/命名/9セクション）を後追い確認した
  - `unassigned-task-report.md` と `task-workflow.md` の参照パス同期を同時に実施していなかった
- **教訓**:
  - 未タスクは「作成」ではなく「配置先 + 命名 + フォーマット + 台帳同期」を1作業単位で完了させる
  - `task-specification-creator` のテンプレートに準拠し、`docs/30-workflows/unassigned-task/` 以外への配置を禁止する
- **対策**:
  1. 未タスク検出後に `assets/unassigned-task-template.md` で9セクション化
  2. `docs/30-workflows/unassigned-task/task-*.md` へ保存
  3. `task-workflow.md` 残課題テーブルと `unassigned-task-report.md` を同一ターンで同期
  4. `audit-unassigned-tasks.js --diff-from HEAD` で `currentViolations=0` を確認
- **発見日**: 2026-02-27
- **関連タスク**: TASK-9F, UT-9F-SETTER-INJECTION-001, UT-9F-EXPORT-PATH-TRAVERSAL-001

### [Phase12] 仕様書別SubAgent同期 + spec-update-summary 固定化（TASK-9F追補）

- **状況**: 実装内容と苦戦箇所は `task-workflow.md` / `lessons-learned.md` に記録済みだが、仕様書別責務と検証証跡の再利用性が不足していた
- **問題**: 次回タスクで「どの仕様書を誰が更新するか」「どの検証値をどこへ転記するか」が毎回手作業判断になり、再監査コストが増える
- **原因**:
  - Phase 12 Step 2 の成果物に `spec-update-summary.md` を標準化していなかった
  - SubAgent分担を「A:台帳/B:ドメイン/C:教訓/D:検証」の抽象表記で止め、実ファイル責務へ落とし込んでいなかった
- **教訓**:
  - 仕様書更新は `interfaces` / `api-ipc` / `security` / `task-workflow` / `lessons` の5責務に固定すると漏れを抑制できる
  - 検証値（13/13, 28項目, 95/95, current=0）は `spec-update-summary.md` を正本にし、台帳と教訓へ転記する
- **対策**:
  1. `assets/phase12-system-spec-retrospective-template.md` で仕様書別SubAgent表を必須化
  2. `outputs/phase-12/spec-update-summary.md` を成果物必須に追加
  3. `task-workflow.md` に SubAgent分担 + 検証結果 + 成果物マトリクスを追記
  4. `lessons-learned.md` に同一検証値と再利用5ステップを同期
- **発見日**: 2026-02-27
- **関連タスク**: TASK-9F

### [IPC] IPC契約ドリフト（Handler/Preload引数不整合）（UT-FIX-SKILL-REMOVE-INTERFACE-001）

- **状況**: ハンドラ側がオブジェクト形式（`{ skillId: string }`）を期待し、Preload側が文字列（`skillName`）を渡すインターフェース不整合
- **問題**: ランタイムで `args?.skillId` が `undefined` となり、バリデーションエラーが発生。コンパイル時はPreloadのモック化で検出されない
- **原因**:
  - ハンドラ設計時とPreload設計時で異なる想定（オブジェクト形式 vs 単一引数）を前提とした
  - 引数の命名も乖離（`skillId` / `skillIds` / `skillName`）
  - TypeScript型チェックがPreloadとMain Processの境界を超えないため、コンパイル時に検出されない
- **教訓**:
  - IPC チャンネルの設計時に「引数の正本」をPreload側に定義し、ハンドラはPreloadに合わせる
  - 引数名はレイヤー間で統一する（`skillName` ならハンドラも `skillName`）
  - ハンドラ修正時は必ず [IPC契約チェックリスト](../../aiworkflow-requirements/references/ipc-contract-checklist.md) を実行
- **対策**: 3箇所同時更新チェックリスト（ハンドラ・Preload API・テスト）をIPC修正の必須手順とする
- **発見日**: 2026-02-20
- **関連タスク**: UT-FIX-SKILL-REMOVE-INTERFACE-001, UT-FIX-SKILL-IMPORT-INTERFACE-001
- **関連Pitfall**: P23, P32, P42, P44

### [IPC] 正式契約切替時の後方互換欠落（UT-FIX-SKILL-EXECUTE-INTERFACE-001）

- **状況**: 新契約（`skillName`）へ移行する際、旧契約（`skillId`）を即時削除して既存呼び出しを破壊
- **問題**: 既存テストや既存呼び出し経路がランタイムで失敗し、移行期間に障害が顕在化する
- **原因**:
  - 契約移行を単一フェーズで完了できる前提を置いていた
  - 境界Adapterを用意せず、ドメインAPIまで同時変更した
  - 新契約テストのみで旧契約回帰を省略した
- **教訓**:
  - 契約変更は「正式契約 + 互換契約 + 廃止条件」を1セットで定義する
  - 互換期間は境界Adapterで吸収し、ドメインAPIの破壊的変更を遅らせる
  - 新旧契約の両回帰テストを完了条件に含める
- **対策**: IPC契約変更テンプレートに「後方互換チェック」を必須項目として追加
- **発見日**: 2026-02-25
- **関連タスク**: UT-FIX-SKILL-EXECUTE-INTERFACE-001

### [IPC/Renderer] Renderer層での識別子混同（id/name）（UT-FIX-SKILL-IMPORT-ID-MISMATCH-001）

- **状況**: SkillImportDialog の `handleImport` が `selectedIds`（Set内はskill.id＝SHA-256ハッシュ）をそのまま `onImport` に渡していた。IPC ハンドラは `skill.name`（人間可読名）を期待しており、`getSkillByName(hash)` が常に null を返すため、スキルインポートが 100% 失敗
- **原因**:
  - `skill.id` と `skill.name` が共に `string` 型であるため、型レベルでの検出が不可能
  - UI上は id をハッシュ表示しないため、開発者が id/name の違いを認識しにくい
  - IPC ハンドラ側（IMPORT-INTERFACE-001）の修正でハンドラ入口は正常化したが、Renderer 側の送信値が未修正のまま残った
- **影響**: スキルインポート機能が完全に動作しない（成功率 0%）
- **対策**: Renderer → IPC 境界に明示的な変換処理を1箇所だけ配置し、変数名を契約準拠（`skillNames`）に統一
- **再発防止**: 同じ `string` 型の識別子が2種類以上あるコンポーネントでは、変数名で明示的に区別し、テストで「期待値」と「否定条件」を同時に検証
- **発見日**: 2026-02-22
- **関連タスク**: UT-FIX-SKILL-IMPORT-ID-MISMATCH-001

### [Phase12] 未タスクraw検出の誤読（TASK-FIX-11-1）

- **状況**: raw検出 51件をそのまま未タスク件数と見なしかけた
- **問題**: 仕様書本文の説明用 TODO まで未対応課題として誤認し、バックログを汚染する
- **原因**: `detect-unassigned-tasks.js` の出力が「候補」である前提を明記せずに解釈
- **教訓**: 未タスクは「検出候補」と「実装上の確定課題」を分離して扱う
- **対策**: `unassigned-task-detection.md` に raw件数と精査後件数を分離して記録し、配置先 `docs/30-workflows/unassigned-task/` の要否を明示する
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [Testing] dangerouslyIgnoreUnhandledErrors 常時有効化（TASK-FIX-10-1）

- **状況**: Vitestで `dangerouslyIgnoreUnhandledErrors: true` を恒常運用し、未処理Promise拒否を無視する
- **問題**: 本来失敗すべき非同期エラーがテストで通過し、回帰検知が遅れる
- **原因**: 一時的なテスト安定化設定を恒久設定として残してしまう運用
- **教訓**: 未処理Promise拒否は設定で抑止せず、テスト/実装側で根本修正する
- **対策**: 設定禁止ルールを仕様書に明記し、設定検証テストで再導入を防ぐ
- **発見日**: 2026-02-19
- **関連タスク**: TASK-FIX-10-1-VITEST-ERROR-HANDLING

### [Test] モジュールモック下でのタイマーテスト失敗

- **状況**: `vi.mock("../agent-client")` でモジュール全体をモック化した状態で、`vi.useFakeTimers()` + `vi.advanceTimersByTimeAsync(30000)` によるタイムアウトテストを実行
- **症状**: タイマーを進めてもタイムアウトが発生しない。テストがハングまたはタイムアウト条件が不成立
- **原因**: `vi.mock()` はモジュール内の全エクスポートをモック関数に置換するため、元の実装内部の `setTimeout` + `AbortController` ロジックが消失する
- **解決策**: モジュール内部のタイマーを再現するのではなく、`mockRejectedValueOnce(new Error("Request timeout"))` で直接エラーを注入。タイマーテストが必要な場合はモック関数の `mockImplementation` 内に `setTimeout` を含める
- **発見日**: 2026-02-13
- **関連タスク**: TASK-FIX-11-1-SDK-TEST-ENABLEMENT

### [Phase12] Phase 10/11サブエージェント出力の非永続化（UT-FIX-SKILL-VALIDATION-CONSISTENCY-001）

- **状況**: Task subagentでPhase 10最終レビューとPhase 11手動テストを実行したが、出力がファイルとして保存されなかった
- **問題**: Phase 12のdocumentation-changelogでレビュー結果を参照できず、「サブエージェント実行結果確認」としか記載できない。レビュー判定（PASS/MINOR/MAJOR）の根拠が追跡不能
- **原因**: Task subagentの出力はメッセージとして返されるが、ファイル書き込み指示が不足していた。サブエージェントに「結果をファイルに出力する」明示的な指示がなかった
- **教訓**: サブエージェントにPhase実行を委譲する際は、出力ファイルパス（`outputs/phase-N/` 配下）を明示的に指定する。特にPhase 10/11はレビュー判定を含むため、永続化が必須
- **対策**: Task toolのpromptに `結果を outputs/phase-10/review-result.md に書き出してください` のようなファイル出力指示を含める
- **発見日**: 2026-02-24
- **関連タスク**: UT-FIX-SKILL-VALIDATION-CONSISTENCY-001

### [Phase 12] 仕様書修正タスクでのPhaseテンプレート誤適用

- **状況**: 仕様書修正のみタスクにPhase 1-13テンプレートをそのまま適用しようとした
- **問題**: Phase 4（テスト作成）で「何のテストを書くのか」、Phase 7（カバレッジ確認）で「何のカバレッジを測るのか」が不明確になり、作業が停滞
- **根本原因**: Phase 1-13テンプレートはコード実装タスクを前提としており、仕様書修正タスク向けの代替アプローチが定義されていなかった
- **解決策**: 仕様書修正タスク向けの代替Phase定義を Phase 1 で事前策定（Phase 4=検証基準設計、Phase 6-7=grep検証等）
- **影響**: 初回の仕様書修正タスクでは、Phaseの再定義に追加工数がかかった
- **再発防止**: 仕様書修正タスクの仕様書テンプレートに「代替Phase対応表」セクションを追加
- **発見日**: 2026-02-24

### [CI/ビルド] TypeScript設定ファイルの完全AST解析の試行

- **状況**: vitest.config.ts のalias設定を抽出するために、TypeScript ASTパーサー（ts-morph等）の使用を検討
- **問題**: 外部依存の追加、ビルド時間の増加、メンテナンスコストが CIガードスクリプトの目的（設定値の文字列抽出）に対して過大
- **原因**: 完全な型安全パースを目指しすぎ、実用的な正規表現アプローチを最初から除外した
- **教訓**: CIガードスクリプトは「設定値の文字列比較」が目的であり、完全なAST解析は不要。正規表現の制約（ダブルクォート前提等）をテストで明文化すれば十分。YAGNI原則を適用する
- **発見日**: 2026-02-22
- **関連タスク**: TASK-IMP-MODULE-RESOLUTION-CI-GUARD-001

### [Phase12] 実行可否判定の三点突合（チェックリスト/成果物/artifacts）

- **状況**: `outputs/phase-12` の成果物が揃っていても、`phase-12-documentation.md` のチェックや `artifacts.json` ステータスが未同期のまま残る
- **問題**: 「見た目は完了」に見えるが、再監査時に未完了判定へ戻る
- **原因**: 完了判定をファイル存在だけで行い、台帳ステータスと手順書チェックの同期を省略した
- **解決策**:
  - `verify-all-specs` と `validate-phase-output` で構造整合を固定
  - 必須5成果物の実体確認
  - `artifacts.json` の `phases.12.status` 同期確認
  - `phase-12-documentation.md` チェックリスト同期確認
- **結果**: Phase 12 完了判定の再現性が上がり、再監査差し戻しを削減
- **適用条件**: Phase 12 を含む全タスク
- **発見日**: 2026-02-28
- **関連タスク**: TASK-REFACTOR-SHARED-SOURCE-STRUCTURE-001

### [Phase12] 仕様書単位SubAgent + N/A判定ログ固定（TASK-REFACTOR-SHARED-SOURCE-STRUCTURE-001）

- **状況**: 仕様書別に SubAgent を分割しても、更新不要な仕様書（interfaces/api-ipc/security）の扱いがメモ依存になり、監査で漏れと判別しづらい
- **問題**: 「更新なし」と「更新漏れ」の区別が曖昧になり、再確認のたびに説明コストが増える
- **原因**: Phase 12 テンプレートに仕様書ごとの適用判定（更新/N/A）を記録する欄がなかった
- **解決策**:
  - `phase12-system-spec-retrospective-template.md` に `仕様書適用判定ログ` を追加
  - 各仕様書を `更新 / N/A` で必ず判定し、N/A は理由と代替証跡を記録
  - SubAgent 分担表と同一ターンで転記し、責務分離と説明責任を両立
- **結果**: 仕様書別SubAgent運用でも、非対象範囲の説明が機械的に再現できる
- **適用条件**: 複数仕様書へ横断反映する Phase 12 タスク全般
- **発見日**: 2026-02-28
- **関連タスク**: TASK-REFACTOR-SHARED-SOURCE-STRUCTURE-001

### [Phase12] UI機能実装の未タスク6件分解 + 二段監査固定（TASK-UI-05）

- **状況**: UI実装（SkillCenterView）を完了したが、型統一・詳細パネル分割・モバイル操作などの残課題が複数同時に見つかった
- **アプローチ**:
  - 検出課題を `UT-UI-05-001`〜`UT-UI-05-006` として1課題1指示書へ分解
  - `audit-unassigned-tasks --target-file` で各未タスクのフォーマットを個別監査
  - `verify-unassigned-links` + `audit --diff-from HEAD` でリンク整合と差分違反ゼロを確定
  - `task-workflow.md` と `lessons-learned.md` に同一ターンで苦戦箇所を同期
- **結果**: 未タスクの「存在・形式・参照」が同時に保証され、Phase 12完了判定の再現性が上がった
- **適用条件**: UI機能の完了時に未タスクが3件以上出る Phase 12 タスク
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] UI機能6仕様書SubAgent同期テンプレート

- **状況**: UI機能実装では `ui-ux` と `arch-ui/state` が正本だが、タスクごとに同期対象の切り方が揺れやすい
- **アプローチ**:
  - `phase12-system-spec-retrospective-template.md` に UI機能6仕様書プロファイルを追加
  - `phase12-spec-sync-subagent-template.md` に UI向け SubAgent-A〜E の分担表を追加
  - 完了チェックへ「プロファイル選択（標準5 / UI6）」を必須化
- **結果**: UI機能タスクで仕様更新漏れが減り、仕様書単位の責務分離を再利用しやすくなった
- **適用条件**: Renderer中心で IPC追加が主目的でない UI機能実装の Phase 12
- **発見日**: 2026-03-01
- **関連タスク**: TASK-UI-05-SKILL-CENTER-VIEW

### [Phase12] 検証スクリプト実体探索先行パターン（TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001）

- **状況**: Phase 12再確認で `verify/validate/links/audit` を連続実行する際、スクリプト所在の記憶依存で誤パス実行が起きやすい
- **アプローチ**:
  - 検証開始前に `rg --files .claude/skills | rg 'verify-all-specs|validate-phase-output|verify-unassigned-links|audit-unassigned-tasks'` を必須実行
  - 実体解決後に `verify -> validate -> links -> audit` を固定順序で実行
  - 実体探索結果と検証結果を同一ターンで `spec-update-summary.md` へ記録
- **結果**: スクリプト所在誤認による再確認の手戻りを抑制し、証跡ドリフトを防止
- **適用条件**: Phase 12 の再監査・再実行タスク全般
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] CLIエイリアス非依存で検証経路を固定するパターン（TASK-UI-00-FOUNDATION-REFLECTION-AUDIT）

- **状況**: `verify-all-specs` / `validate-phase-output` をグローバルCLI前提で実行し、環境差で `not found` や `MODULE_NOT_FOUND` が発生しやすい
- **アプローチ**:
  - 再監査開始時に `which verify-all-specs || true` でエイリアス有無を確認
  - `rg --files .claude/skills/task-specification-creator/scripts` で実体を特定し、`node .claude/skills/task-specification-creator/scripts/<script>.js` へ固定
  - 実行後に採用した最終コマンドを `spec-update-summary.md` と `documentation-changelog.md` へ転記して再現手順を固定
- **結果**: 端末差異に依存しない検証フローとなり、Phase 12 再確認時の手戻りを抑制できる
- **適用条件**: 複数ワークツリー/端末で同一検証コマンドを再利用する Phase 12 タスク
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-00-FOUNDATION-REFLECTION-AUDIT

### [Phase12] Vitest再確認の非watch固定パターン（TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001）

- **状況**: Phase 12 でテスト証跡を再取得する際、`pnpm test` の watch 残留で完了判定が遅延しやすい
- **アプローチ**:
  - テスト再確認は `pnpm --filter @repo/desktop exec vitest run <target>` を標準コマンドに固定
  - ルート実行ではなく対象パッケージ文脈で実行して設定解決を安定化
  - 実行コマンドを `implementation-guide.md` / `spec-update-summary.md` に明示して再現性を固定
- **結果**: 非watchで決定論的に終了し、Phase 12 の証跡取得と台帳同期が安定
- **適用条件**: モノレポで UI/Renderer テストを Phase 12 で再実行するタスク
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] 未タスク監査カウンタ再同期パターン（TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001）

- **状況**: Phase 12 再確認後に未タスク件数が更新されたが、`task-workflow` や `outputs/phase-12` に旧値（links/baseline）が残りやすい
- **アプローチ**:
  - 仕様更新の最終ステップで `verify-unassigned-links` と `audit-unassigned-tasks --json --diff-from HEAD` を再実行
  - `existing/missing/current/baseline` を確定値として `task-workflow.md` / `spec-update-summary.md` / `unassigned-task-detection.md` へ同一ターン転記
  - 変更履歴（`task-workflow` / `documentation-changelog`）にも同値を追記して記録値を一本化
- **結果**: 未タスク監査の数値ドリフトを抑止し、再監査時の判定ブレを低減
- **適用条件**: Phase 12 で未タスクの追加・完了移管・リンク更新を行ったタスク
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] backlog 継続前に現物確認して completed/unassigned を再判定するパターン（TASK-UI-03）

- **状況**: Phase 10/11 で起票した未タスクをそのまま継続扱いにすると、current branch では既に解消済みの項目まで open backlog として残りやすい
- **アプローチ**:
  - `rg -n "<symptom>" <codebase>` で現物の残存有無を先に確認する
  - 解消済みなら `docs/30-workflows/completed-tasks/unassigned-task/` 側へ正規化し、`task-workflow.md` / `unassigned-task-detection.md` / `spec-update-summary.md` を同一ターンで更新する
  - 未解消なら task-spec フォーマットで `docs/30-workflows/unassigned-task/` に formalize し、`audit --target-file` まで閉じる
- **結果**: backlog と実コードのズレを抑止し、Phase 12 判定の信頼性を保てる
- **適用条件**: current workflow 再監査、MINOR 指摘の継続判定、既存未タスクの棚卸し時
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT

### [Phase12] UI所見を component scope と token scope に切り分けて formalize するパターン（TASK-UI-03）

- **状況**: screenshot で light/dark の視認性差分を見つけたとき、個別コンポーネント修正と design token 改善が混線しやすい
- **アプローチ**:
  - dedicated harness で component state を固定し、layout/state の不具合有無を先に確認する
  - token 由来と判断した所見は `ui-ux-design-system.md` と `task-workflow.md` の両方へ未タスク化し、component 側にはハードコードを追加しない
  - `manual-test-result.md` / `discovered-issues.md` / `unassigned-task-detection.md` に同じ task ID を転記する
- **結果**: UIレビュー所見が観察止まりにならず、正しい責務境界で改善計画へ接続できる
- **適用条件**: Phase 11 screenshot 再監査、Apple UI/UX レビュー、theme token 改善の判断時
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT

### [Phase12] UI current workflow の system spec 反映先を最適化するパターン（TASK-UI-03）

- **状況**: 実装内容と苦戦箇所を `task-workflow.md` と `lessons-learned.md` にだけ集約すると、component catalog / feature spec / architecture / design-system のどこに何を書くべきかが揺れ、同じ内容の重複と反映漏れが起きやすい
- **アプローチ**:
  - コンポーネント一覧と完了記録は `ui-ux-components.md` に寄せる
  - 機能の振る舞い、関連未タスク、5分解決カードは `ui-ux-feature-components.md` に寄せる
  - 専用型、adapter helper、dedicated harness など責務境界の話は `arch-ui-components.md` に寄せる
  - light/dark token や theme 所見は `ui-ux-design-system.md` に寄せる
  - 横断的な検証値と教訓は `task-workflow.md` / `lessons-learned.md` に残す
- **結果**: 参照起点が固定され、1仕様書=1関心の形で再利用しやすくなる
- **適用条件**: UI current workflow 再監査、Step 2 の更新先選定、SubAgent 分担表を作る前
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT

### [Phase12] UI再撮影前ポート競合 preflight + 分岐記録固定（workflow02）

- **状況**: `screenshot:skill-import-idempotency-guard` 実行時に証跡取得は成功したが、`Port 5174 is already in use` が混在して判定が揺れた
- **アプローチ**:
  - screenshot 実行前に `lsof -nP -iTCP:5174 -sTCP:LISTEN || true` を必須実行して占有有無を固定
  - 競合時は「既存プロセス停止」または「既存サーバー再利用」の分岐を `spec-update-summary.md` に記録
  - その後 `screenshot` 実行と `validate-phase11-screenshot-coverage` を同一ターンで実施し、未解決時は未タスク化する
- **結果**: 成功証跡と環境警告の切り分けが明確になり、再監査時の説明責任を維持できる
- **適用条件**: UI screenshot を Phase 11/12 で再取得するタスク全般
- **発見日**: 2026-03-04
- **関連タスク**: TASK-FIX-SKILL-IMPORT-IDEMPOTENCY-GUARD-001

### [Phase12] UI再撮影後の残留プロセス cleanup 固定（TASK-UI-01）

- **状況**: スクリーンショット再取得完了後に `vite` / `capture-*` プロセスが残留し、後続の検証コマンドや再撮影でポート競合が起きやすい
- **アプローチ**:
  - 再撮影と `validate-phase11-screenshot-coverage` 実行後に `ps -ef | rg "capture-.*phase11|vite" | rg -v rg` を必須実行
  - 残留がある場合は停止し、`documentation-changelog.md` に cleanup 実施を記録
  - 同時に `manual-test-result.md` / `screenshot-coverage.md` の時刻を同期し、証跡と実行環境の両方を固定する
- **結果**: UI証跡更新後の実行環境が安定し、Phase 12 再監査でのポート競合・判定揺れを抑止できる
- **適用条件**: UI再撮影を含む Phase 11/12 再確認タスク全般
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-STORE-IPC-ARCHITECTURE

### [Phase12] 対象workflow配下への証跡正規配置 + `NON_VISUAL` 記法固定（UT workflow）

- **状況**: Phase 11手動結果に別workflow参照が混在し、対象workflowで coverage validator が失敗した
- **アプローチ**:
  - `outputs/phase-11/screenshots` を対象workflow配下へ正規配置する
  - 視覚TCは `screenshots/*.png`、非視覚TCは `NON_VISUAL:` 記法へ統一する
  - `validate-phase11-screenshot-coverage` を再実行し、`expected/covered` と非視覚許容件数を `spec-update-summary.md` に記録する
- **結果**: UI証跡が機械判定可能な形で固定され、再監査で `covered=0` の再発を防止できる
- **適用条件**: UI証跡を複数workflowで流用・再配置する Phase 11/12 再確認タスク
- **発見日**: 2026-03-04
- **関連タスク**: UT-IMP-PHASE12-SCREENSHOT-COMMAND-REGISTRATION-GUARD-001

### [Phase12] `--target-file` 適用境界固定 + `current/baseline` 分離判定（TASK-UI-01-A）

- **状況**: Phase 12 再監査で `audit-unassigned-tasks --target-file` に `outputs/phase-12/*.md` を指定し、対象外エラーで判定が停止した
- **アプローチ**:
  - `--target-file` は `docs/30-workflows/unassigned-task/*.md`、actual parent `docs/30-workflows/completed-tasks/<workflow>/unassigned-task/*.md`、standalone `docs/30-workflows/completed-tasks/*.md` のいずれかに限定し、成果物監査は `--diff-from HEAD` へ切り替える
  - 合否判定は `currentViolations` のみを使用し、`baselineViolations` は資産健全性指標として別管理する
  - move 直後の untracked completed file が `--diff-from HEAD` に出ない場合は、`--target-file docs/30-workflows/completed-tasks/<task>.md` を current 判定の正本にする
  - baseline負債が残る場合は別未タスク（段階削減）へ切り出して追跡する
- **結果**: 監査コマンド誤用による手戻りを防ぎ、差分合否と既存負債の説明責務を同時に満たせる
- **適用条件**: 未タスク監査を含む Phase 12 再確認タスク全般
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-A-STORE-SLICE-BASELINE

### [Phase12] NON_VISUAL manifest配置タスクの効率パターン（TASK-P0-03）

- **状況**: workflow-manifest.json の canonical/mirror 配置のみで、API/IPC/型定義変更がない NON_VISUAL タスク
- **アプローチ**:
  - P50 チェック（Phase 1）で manifest が既に正しく配置済みであることを確認し、不要な上書きを回避
  - ManifestLoader.production-manifest テスト 17 ケースが事前整備済みのため、Phase 5（実装）とPhase 7（テスト）がほぼ即時完了
  - Phase 11 は NON_VISUAL 自動テスト代替 PASS で品質保証を完結
  - system-spec-update-summary で「システム仕様更新: 不要」を明示的に判断・記録
- **結果**: Phase 1-12 を高効率で完走。テスト先行整備が最大の効率化要因
- **教訓**:
  - テストを先行タスクで整備しておくと、配置確認タスクは検証コストがほぼゼロになる
  - NON_VISUAL タスクでも Phase 12 必須5タスクは全て出力が必要（0件でも出力ルール）
  - 「更新不要」の明示判断は、将来の監査で「漏れ」と「意図的スキップ」を区別する根拠になる
- **適用条件**: ファイル配置・設定変更のみで API/IPC/型定義に影響しない小規模タスク
- **発見日**: 2026-04-04
- **関連タスク**: TASK-P0-03 workflow-manifest-production-placement

### [Phase12] ユーザー要求時の `NON_VISUAL` → `SCREENSHOT` 昇格運用（TASK-INVESTIGATE）

- **状況**: 契約修正中心タスクで Phase 11 を `NON_VISUAL` で進めた後、ユーザーから画面検証要求が入り証跡不足が発生する
- **アプローチ**:
  - UI検証要求を受けた時点で、非視覚タスクでも `SCREENSHOT` モードへ即時昇格する
  - `phase-11-manual-test.md` に `テストケース` と `画面カバレッジマトリクス` を追加し、`TC-ID ↔ screenshots/*.png` を固定する
  - `validate-phase11-screenshot-coverage` の `expected=covered` を確認し、`manual-test-result.md` / `evidence-index.md` / `spec-update-summary.md` へ同値転記する
- **結果**: ユーザー要求と機械検証の両方を満たした証跡に収束し、再監査時の手戻りを削減できる
- **適用条件**: 非視覚修正中心だが、UI/UX確認要求が追加された Phase 11/12 再監査タスク
- **発見日**: 2026-03-06
- **関連タスク**: TASK-INVESTIGATE-ELECTRON-SANDBOX-ITERABLE-ERROR-001

### [Phase12] タスク仕様準拠の4点突合 + scoped diff監査（TASK-UI-01-E）

- **状況**: `outputs/phase-12/` のファイル存在だけを見て完了判定すると、`implementation-guide.md` 必須要素や未タスク指示書フォーマット、`phase-12-documentation.md` との同期漏れを取りこぼしやすい
- **アプローチ**:
  - `phase-12-documentation.md` の `completed` / Task 12-1〜12-5 / Task進捗100% と `outputs/phase-12` 実体を同時確認する
  - `implementation-guide.md` の `Part 1 / Part 2`、理由先行、日常例え、型/API/エッジケース/設定語を `rg` で機械確認する
  - 未タスクは `docs/30-workflows/unassigned-task/` への物理配置、`## メタ情報 + ## 1..9` の10見出し、`audit --diff-from HEAD --target-file` と `verify-unassigned-links` を同時に確認する
  - `task-workflow.md` / `lessons-learned.md` / `spec-update-summary.md` / `phase12-compliance-recheck.md` / `unassigned-task-detection.md` に同一の実測値を転記する
- **結果**: Phase 12 の「完了しているように見えるが task spec を満たしていない」状態を早期に検出でき、差分合否と baseline 監視値の混同も防げる
- **適用条件**: docs-heavy task、spec_created task、再監査タスク、既存未タスク是正を含む Phase 12 完了確認全般
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-01-E-INTEGRATION-GATE-SPEC-SYNC
- **クロスリファレンス**: [phase12-task-spec-recheck-template.md](../assets/phase12-task-spec-recheck-template.md), [phase12-system-spec-retrospective-template.md](../assets/phase12-system-spec-retrospective-template.md), [phase12-spec-sync-subagent-template.md](../assets/phase12-spec-sync-subagent-template.md)

### [Phase12] docs-heavy parent workflow は review board fallback + exact count 再同期で閉じる（UT-IMP-WORKSPACE-PARENT-REFERENCE-SWEEP-GUARD-001）

- **状況**: docs-only parent workflow の再監査で、UI 実装差分はないが user が screenshot を要求し、さらに related unassigned row を completed 実績へ移したことで `verify-unassigned-links` の total が stale になりやすい
- **アプローチ**:
  - `pointer / index / spec / script / mirror` を別 concern として SubAgent 分担し、親導線の drift を 1 sweep で閉じる
  - current build 再撮影が過剰または環境依存で難しい場合は、same-day upstream screenshot を current workflow へ集約し、review board 1件を current workflow で新規 capture して Apple review の正本にする
  - related unassigned row を completed 実績へ移した後に `verify-unassigned-links` を再実行し、`existing/missing/total` を workflow outputs / task-workflow / workflow spec へ同値転記する
  - 元 unassigned spec は `docs/30-workflows/unassigned-task/` に残したまま status を workflow 実行済みへ更新し、`audit-unassigned-tasks --json --diff-from HEAD --target-file <file>` で配置とフォーマットを当日確認する
- **結果**: docs-heavy task でも visual re-audit を `N/A` にせず閉じられ、台帳移動後の数値ドリフトも current workflow と system spec の両方で防止できる
- **適用条件**: docs-heavy parent workflow、spec_created 由来の再監査、representative screenshot 再確認、related UT の completed 化を伴う Phase 12
- **失敗パターン**:
  - screenshot を `N/A` のまま残し、同日 evidence の review board 化を検討しない
  - related UT を completed 実績へ移した後も `220 / 220` のような旧 total を summary に残す
  - 元 unassigned spec の status だけ更新し、配置確認や `currentViolations=0` を取り直さない
- **発見日**: 2026-03-12
- **関連タスク**: UT-IMP-WORKSPACE-PARENT-REFERENCE-SWEEP-GUARD-001

### [Phase12] 専用 recheck テンプレートで責務を分離（TASK-UI-01-E）

- **状況**: `phase12-system-spec-retrospective-template` だけで再確認から system spec 同期まで抱えると、task spec 準拠確認の責務が埋もれて適用順がぶれやすい
- **アプローチ**:
  - まず `phase12-task-spec-recheck-template.md` で 4点突合と実測値固定を完了する
  - その後に `phase12-system-spec-retrospective-template.md` で実装内容・苦戦箇所・再利用手順へ展開する
  - 仕様書ごとの担当と検証証跡は `phase12-spec-sync-subagent-template.md` で固定する
- **結果**: 再確認と仕様同期の責務が分離され、docs-heavy task でも最小限の順序で機械的に進められる
- **適用条件**: Phase 12 再監査で「まず合否を確定し、その後に system spec と outputs を同期したい」ケース
- **発見日**: 2026-03-06
- **関連タスク**: TASK-UI-01-E-INTEGRATION-GATE-SPEC-SYNC

---

## ガイドライン

実行時の判断基準。

### 抽象度レベル判定

- **状況**: ユーザー要求の具体性を判断する時
- **指針**: L1（概念）→ 詳細インタビュー、L2（機能）→ 軽いヒアリング、L3（実装）→ 直接実行
- **根拠**: 抽象度に応じて必要な対話量が変わる
- **発見日**: 2026-01-15

### モード選択

- **状況**: create/update/improve-prompt の選択時
- **指針**: 既存スキルパスの有無、更新対象の特定で判断
- **根拠**: detect_mode.js の判定ロジックに準拠
- **発見日**: 2026-01-06

---

## 型定義リファクタリング

### 成功パターン: deprecated プロパティの段階的移行（TASK-FIX-13-1）

**コンテキスト**: TypeScript型定義で `@deprecated` マーク付きプロパティを推奨代替に移行し、定義を削除する

**課題**:

- 同名プロパティ（`name`, `lastUpdated`）が複数の型に存在し、単純な文字列置換では誤修正のリスクが高い
- 永続化互換のため残すべきプロパティと削除すべきプロパティの判定が必要

**解決策**:

1. **スコープ分離**: 削除対象の型を明確にし、同名プロパティが存在する他の型（`SkillImportConfig.lastUpdated`, `StorageMetadata.lastUpdated`）をスコープ外として明示
2. **TDD型レベルテスト**: `@ts-expect-error` ディレクティブで「プロパティが存在しないこと」を型レベルで検証
3. **型スコープ限定grep**: `Anchor` 型スコープに限定して参照箇所を検索し、汎用プロパティ名の誤検出を回避

**結果**: 型定義2箇所の削除、テスト8件PASS、全参照移行完了

**適用条件**: TypeScriptプロジェクトでdeprecatedプロパティを安全に削除したい場合

```typescript
// TDD型レベルテストパターン
it("削除されたプロパティにアクセスするとエラーになること", () => {
  const obj: MyType = { newProp: "value" };
  // @ts-expect-error -- oldProp は削除済み
  const _old = obj.oldProp;
  expect(obj).toBeDefined();
});
```

### 失敗パターン: ドキュメント偏重による実装検証省略

**コンテキスト**: Phase 1-12の並列エージェント実行でドキュメント成果物を高速生成

**課題**: 5つの並列エージェントでPhase 1-11のドキュメントを同時生成し、Phase 12まで完了と報告したが、コードの実装検証（grep・テスト・型チェック）が不十分だった

**原因**: ドキュメント生成の完了を「実装完了」と混同。並列エージェントの出力に対する品質ゲートが未設定

**教訓**:

1. **コード検証ファースト**: ドキュメント生成前に、テスト・型チェック・grepでコード変更の完了を確認する
2. **並列エージェント後の統合検証**: 全エージェント完了後に成果物一覧と整合性チェックを実施
3. **品質ゲートの明示化**: Phase 5（実装）完了の判定基準をテスト結果で定義し、Phase 6以降はその結果を前提とする

### [ビルド・環境] 4ファイル同期漏れパターン（TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001）

- **状況**: @repo/shared に新サブパスを追加する際、4つのファイル（package.json exports/typesVersions、tsconfig.json paths、vitest.config.ts alias、tsup.config.ts entry）のうち一部のみ更新
- **結果**: TypeScript は通るが Vitest が失敗、またはその逆。CI で初めてエラーが検出される
- **解決策**: 4ファイル同時更新チェックリストを development-guidelines.md に配置。整合性テストの追加
- **発見日**: 2026-02-20
- **関連タスク**: TASK-FIX-TS-SHARED-MODULE-RESOLUTION-001
- **関連未タスク**: UT-FIX-TS-VITEST-TSCONFIG-PATHS-001（vitest-tsconfig-paths プラグインによる自動化）

### [UI/TypeScript] HTMLAttributes Props型衝突（TASK-UI-00-ATOMS）

- **状況**: Badge コンポーネントに `content?: string | number` Props を追加
- **問題**: `React.HTMLAttributes<HTMLSpanElement>` の標準属性 `content?: string` と型衝突し、TS2430エラーが発生
- **原因**: HTML標準属性と同名のカスタムPropsを定義したため、TypeScriptが型の互換性を検証できなかった
- **教訓**: `Omit<React.HTMLAttributes<HTMLElement>, "conflictingProp">` で衝突属性を除外してからカスタム型を定義する
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS
- **関連Pitfall**: [06-known-pitfalls.md#P46](../../rules/06-known-pitfalls.md)

```typescript
// ❌ TS2430エラー
interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  content?: string | number; // HTML標準のcontent(string)と衝突
}

// ✅ Omitで衝突回避
interface BadgeProps extends Omit<
  React.HTMLAttributes<HTMLSpanElement>,
  "content"
> {
  content?: string | number;
}
```

**衝突しやすい属性**: `content`, `color`, `translate`, `hidden`, `title`, `dir`, `slot`

### [Phase3] Props命名の仕様-実装間ドリフト（TASK-UI-00-ATOMS）

- **状況**: RelativeTime コンポーネントの自動更新間隔Propsで、仕様書では `updateInterval`、実装では `refreshInterval` と命名が乖離
- **問題**: Phase 10レビュー時に命名不整合が発覚し、仕様書の修正が必要になった
- **原因**: Phase 3設計レビューでProps命名の仕様-実装間突合チェックが不足していた
- **教訓**: Phase 3にProps命名突合チェック項目を追加。仕様書と実装で同一用語を使用する
- **対策**: Phase 3レビューチェックリストに「Props命名の仕様-実装一致確認」を追加
- **発見日**: 2026-02-23
- **関連タスク**: TASK-UI-00-ATOMS

### [Phase4] 修正箇所数の事前ファイル検証不足（UT-SKILL-IMPORT-CHANNEL-CONFLICT-001）

- **状況**: Phase 4（テスト作成）で task-022 の修正箇所を「3箇所」と仕様書に記載
- **問題**: 実装時に検証したところ、外部ソースインポート文脈の `skill:import` は 1箇所のみだった
- **原因**: Phase 4 設計時にファイル内容を `grep` で事前検証せず、概算で修正箇所数を決定
- **教訓**: Phase 4 テスト設計時は対象ファイルを `grep -c` で事前カウントし、期待値を「N件以上」のような柔軟な基準で設計する。P37（ドキュメント数値の早期固定）と同じパターン
- **対策**: テスト仕様書の期待値は `>=N` 形式で記述し、Phase 5 実行後に実測値で更新
- **発見日**: 2026-02-24
- **関連タスク**: UT-SKILL-IMPORT-CHANNEL-CONFLICT-001

### [Phase12] 対象テスト限定実行の明示（TASK-UI-01-C 再監査）

- **状況**: Phase 12 再監査で「対象5ファイルのみ再検証」したい場面
- **成功パターン**:
  - `pnpm exec vitest run <file1> <file2> ...` で対象を明示し、`N files / M tests` を成果物へ固定
  - 監査ログに「対象ファイル列挙 + 実測件数」を残し、再実行時の比較可能性を確保
- **失敗パターン**:
  - `pnpm run test:run -- <files...>` を使い、script側の設定で全体テストへ展開されて長時間化・中断を招く
- **標準ルール**:
  - 再監査時の限定テストは script ラッパーを経由せず `pnpm exec vitest run` を正とする
  - 目的が「再確認」の場合は coverage を同時実行せず、まず対象テストのPASSを確定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-C-NOTIFICATION-HISTORY-DOMAIN

### [Phase12] Step 1-A四点同期 + Phase 11再撮影運用ガード（TASK-UI-01-D 再確認）

- **状況**: Phase 12 の再確認で `spec-update-summary.md` と system spec は更新済みでも、`LOGS.md` / `SKILL.md` / `topic-map` の同期が後回しになりやすい。さらに再撮影時に workflow 固定出力先と `Port 5177` 競合で証跡運用が不安定化する
- **成功パターン**:
  - Step 1-A を「`LOGS.md` x2 + `SKILL.md` x2 + `generate-index`」の四点セットとして同一ターンで完了する
  - Phase 11 再撮影は workflow 配下保存を固定し、ポート preflight の分岐（停止/再利用）を `unassigned-task-detection.md` へ記録する
  - 運用ギャップは `docs/30-workflows/unassigned-task/` へ未タスク化し、`audit --target-file` で `currentViolations=0` を確認する
- **失敗パターン**:
  - `spec-update-summary` のみ更新して Step 1-A 完了扱いにする
  - 固定出力先のまま再撮影して手動コピーで帳尻を合わせる
  - ポート競合を記録せずに「再撮影済み」と判定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-D-VIEWTYPE-ROUTING-NAV, UT-IMP-TASK-056D-PHASE11-SCREENSHOT-CAPTURE-PATH-GUARD-001

### [Phase12] UI再撮影のworkflow保存先固定 + strictPort preflight（5177）記録テンプレート（TASK-UI-01-D 追補）

- **状況**: system spec へ「実装内容」と「苦戦箇所」を追記しても、再撮影の実行前ガード（保存先/ポート）をテンプレートに書かないと再発しやすい
- **成功パターン**:
  - `phase12-system-spec-retrospective-template.md` / `phase12-spec-sync-subagent-template.md` に `lsof -nP -iTCP:5177 -sTCP:LISTEN` を追加し、分岐（停止/再利用/別ポート）記録を必須化
  - `test -d <workflow>/outputs/phase-11/screenshots` で保存先を先に固定し、workflow外証跡の流入を防止
  - 5分解決カードを `task-workflow` / `lessons-learned` / `ui-ux-navigation` へ同一内容で同期する
- **失敗パターン**:
  - preview preflight だけ実施して strictPort preflight を省略する
  - `task-056` 固定パスの証跡を手動コピーで帳尻合わせし、分岐記録を残さない
- **標準ルール**:
  - UI再撮影運用は「preview preflight」「strictPort preflight」「workflow保存先確認」の3点を必須セットとする
  - preflight失敗時は再撮影を継続せず未タスク化し、再発条件を `lessons-learned` に固定する
- **発見日**: 2026-03-05
- **関連タスク**: TASK-UI-01-D-VIEWTYPE-ROUTING-NAV, UT-IMP-TASK-056D-PHASE11-SCREENSHOT-CAPTURE-PATH-GUARD-001

### [Phase12] shared transport DTO + cross-cutting doc + 専用 harness 同期（TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001）

- **状況**: IPC transport 契約をコード上は是正したが、`ipc-contract-checklist.md` / `quick-reference.md` の横断導線や、画面検証の対象 view 専用 harness 条件が後追いになりやすい
- **成功パターン**:
  - shared transport DTO を `packages/shared` に集約し、Main / Preload / Renderer は import / re-export のみで追従する
  - Step 2 で `interfaces` / `api-ipc` / `security` / `task-workflow` / `lessons` に加えて `ipc-contract-checklist.md` / `indexes/quick-reference.md` を同一ターンで同期する
  - UI契約だけを確認したい場合は対象 view 専用 harness を追加し、`SCREENSHOT` 証跡と `validate-phase11-screenshot-coverage` をセットで固定する
  - 運用ギャップがスクリプト改善領域なら未タスク化し、`audit --target-file` で `currentViolations=0` を確認する
- **失敗パターン**:
  - `interfaces` / `api-ipc` だけ更新して、cross-cutting doc が古いまま残る
  - App 全体起動のノイズを抱えたまま画面検証し、対象 contract の変化点が読み取れない
  - `verify-unassigned-links` の `missing` だけを見て原因を手で辿り、改善バックログへ formalize しない
- **標準ルール**:
  - IPC transport 契約修正は「shared DTO」「cross-cutting doc」「画面検証方針」の3点を同一ターンで閉じる
  - ユーザーが画面検証を要求した場合、初期方針が非視覚でも `SCREENSHOT` へ昇格し、必要なら専用 harness を許可する
  - 監査ツールの説明力不足は `docs/30-workflows/unassigned-task/` へ未タスク化し、配置・形式・参照を機械検証してから完了扱いにする
- **発見日**: 2026-03-06
- **関連タスク**: TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001, UT-IMP-PHASE12-UNASSIGNED-LINK-DIAGNOSTICS-001

### [Phase12] domain spec に `実装内容` / `苦戦箇所` / `5分カード` を対称配置する（TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001 追補）

- **状況**: `task-workflow` と `lessons-learned` には知見があるのに、`interfaces` / `api-ipc` の domain spec 側は契約表だけで終わり、再利用時に背景と難所が読めない
- **成功パターン**:
  - `assets/phase12-domain-spec-sync-block-template.md` を使い、更新した domain spec に `### 実装内容（要点）` / `### 苦戦箇所（再利用形式）` / `### 同種課題の5分解決カード` を同居させる
  - `interfaces` と `api-ipc` の両方で、shared DTO 正本化・UI表示契約・Phase 11 画面検証方針を同じ粒度で記録する
  - `task-workflow` / `lessons-learned` / domain spec の 3 点で 5 ステップ順序をそろえる
- **失敗パターン**:
  - domain spec をチャネル表や型表の更新だけで終え、苦戦箇所を lessons のみに押し込む
  - `task-workflow` と domain spec で 5 分解決カードの順序や検証値が異なる
- **標準ルール**:
  - Phase 12 Step 2 で触る domain spec は、契約表だけでなく「実装内容」「苦戦箇所」「5分カード」の3点を最小セットとする
  - `rg -n '^### 実装内容（要点）$|^### 苦戦箇所（再利用形式）$|^### 同種課題の5分解決カード$' <domain-spec-file>` を完了前に必ず実行する
- **発見日**: 2026-03-06
- **関連タスク**: TASK-FIX-AUTH-MODE-CONTRACT-ALIGNMENT-001

### [Phase12] UI domain spec は「主目的 + 状態契約 + 画面証跡」を先に固定する（TASK-UI-06-HISTORY-SEARCH-VIEW）

- **状況**: UI task の system spec を作るとき、コンポーネント一覧と screenshot 一覧だけでは「何のための画面か」「どの state/IPC が正本か」が後から読み取りにくい
- **成功パターン**:
  - 専用 domain spec に `### 実装内容（要点）` を置き、`画面の主目的` / `変更範囲` / `契約上の要点` / `視覚検証` / `完了根拠` を最初に固定する
  - `ui-ux-feature-components.md` 側は圧縮サマリーと 5分解決カードだけを保持し、詳細は専用 spec へリンクする
  - `task-workflow.md` / `lessons-learned.md` / UI domain spec の 3 点で 5 ステップ順序を揃える
- **失敗パターン**:
  - UI spec が責務表と screenshot 一覧だけで終わり、変更範囲や state 契約の要点が本文から見えない
  - 専用 spec と feature summary spec で見出し名や 5分カードの粒度がずれる
- **標準ルール**:
  - UI domain spec の `実装内容（要点）` には少なくとも `画面の主目的` / `契約上の要点` / `視覚検証` の 3 行を入れる
  - `ui-ux-feature-components.md` の対応節にも `同種課題の5分解決カード` を置き、専用 spec と task-workflow の橋渡しに使う
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-06-HISTORY-SEARCH-VIEW

### [Phase12] `ui-ux-feature-components.md` も 3ブロック構成で閉じる（TASK-SKILL-LIFECYCLE-01）

- **状況**: `task-workflow.md` と `lessons-learned.md` には実装内容と苦戦箇所が入っているのに、`ui-ux-feature-components.md` 側はサマリー表だけで終わり、feature spec 単体では再利用手順が読み取りにくくなる
- **成功パターン**:
  - `ui-ux-feature-components.md` の対象節にも `実装内容（要点）` / `苦戦箇所（再利用形式）` / `同種課題の5分解決カード` を置く
  - `実装内容（要点）` には少なくとも `画面の主目的` / `契約上の要点` / `視覚検証` / `完了根拠` を含める
  - `苦戦箇所` は `task-workflow.md` / `lessons-learned.md` と同じ再発条件で揃え、feature spec では UI 起点の対処へ寄せて圧縮する
  - `currentViolations=0` と `baselineViolations>0` の二軸報告が必要なら feature spec 側にも短く残す
- **失敗パターン**:
  - feature spec を「UI観点の要点」だけで閉じ、苦戦箇所を別仕様書に追い出す
  - task-workflow と feature spec で 5分解決カードの順序や検証値がズレる
- **標準ルール**:
  - UI task の feature spec は圧縮サマリー専用にせず、最小3ブロックを持つ再利用正本として形成する
  - `rg -n '^#### 実装内容（要点）$|^#### 苦戦箇所（再利用形式）$|^#### 同種課題の5分解決カード$' references/ui-ux-feature-components.md` を完了前に実行する
- **発見日**: 2026-03-11
- **関連タスク**: TASK-SKILL-LIFECYCLE-01

### [Phase12] 「更新予定のみ」残置を排除し、実更新ログへ昇格する（TASK-10A-E-C）

- **状況**: Phase 12 で `spec-update-summary.md` は更新されているが、`documentation-changelog.md` や `phase-12-documentation.md` が「仕様策定のみ」「実行中」のまま残る
- **成功パターン**:
  - `documentation-changelog.md` を最終正本として再作成し、Task 1〜5 の実施結果を確定値で記録する
  - `phase-12-documentation.md` のチェックボックスを実績へ同期する
  - `verify-all-specs` / `validate-phase11-screenshot-coverage` / `verify-unassigned-links` の結果を changelog に固定する
- **失敗パターン**:
  - `spec-update-summary.md` だけ更新して完了扱いにする
  - 「更新予定」「実行待ち」記述を残したまま Phase 12 を閉じる
- **標準ルール**:
  - Phase 12 完了前に `rg -n "仕様策定のみ|実行中|実行待ち|更新が必要" outputs/phase-12` を実行し、残置文言をゼロにする
  - completed workflow では `phase-12-documentation.md` に対しても `rg -n "仕様策定のみ|実行予定|保留として記録"` を実行し、本文だけ stale な状態を残さない
  - `phase-12-documentation.md` の完了条件と `Task 100% 実行確認` を `[x]` へ同期し、Phase 13 以外の保留を残さない
  - Task 1〜5 の実施証跡を 1 ファイル（`documentation-changelog.md`）で追跡可能にする
- **発見日**: 2026-03-06
- **関連タスク**: TASK-10A-E-C

### [Phase12] 未タスク指示書は 9見出しテンプレート準拠で作成する（TASK-10A-E-C）

- **状況**: 未タスクを短縮形式で作成すると、`audit-unassigned-tasks` の format violation が発生
- **成功パターン**:
  - `assets/unassigned-task-template.md` を適用し、`## 1..9` を全て埋める
  - 作成直後に `audit-unassigned-tasks --target-file` で個別検証する
- **失敗パターン**:
  - メタ情報 + 背景 + 受け入れ条件だけで未タスクを作る
  - 参照情報/リスク/検証手順を省略する
- **標準ルール**:
  - 未タスク新規作成時は「テンプレート適用→個別監査PASS→台帳同期」の3点を同一ターンで完了する
- **発見日**: 2026-03-06
- **関連タスク**: UT-10A-E-C-001, UT-10A-E-C-002

### [Phase12] スキルフィードバックレポートテンプレート（TASK-UI-03）

- **状況**: Phase 12 Task 5（スキルフィードバックレポート）の記載粒度がタスクごとにばらつき、後続のスキル改善で活用しにくい
- **成功パターン**:
  - 以下の4セクション構成を標準テンプレートとして使用する:

```markdown
# スキルフィードバックレポート

## 1. ワークフロー改善点

| 改善対象 | 現状の問題 | 改善提案 | 優先度 |
| --- | --- | --- | --- |
| {{Phase/Step名}} | {{具体的な問題}} | {{改善内容}} | HIGH/MEDIUM/LOW |

## 2. 技術的教訓

| 教訓 | 再発条件 | 防止策 | 新規Pitfall候補 |
| --- | --- | --- | --- |
| {{教訓の要約}} | {{再現手順/条件}} | {{具体的な対策}} | P{{番号}}候補 or N/A |

## 3. スキル改善提案

| 対象スキル | 対象ファイル | 改善内容 | 根拠タスク |
| --- | --- | --- | --- |
| {{skill-creator/task-specification-creator}} | {{references/xxx.md}} | {{追加/変更内容}} | {{TASK-ID}} |

## 4. 新規Pitfall候補

| ID候補 | タイトル | 症状 | 解決策 | 関連P |
| --- | --- | --- | --- | --- |
| P{{N}} | {{タイトル}} | {{症状}} | {{解決策}} | {{関連する既存Pitfall}} |
```

  - 改善点が0件のセクションでも「該当なし」と明記して省略しない
  - Phase 10 MINOR指摘から抽出した教訓は必ずセクション2に記載する
- **失敗パターン**:
  - 自由記述で書き、後続タスクで構造化データとして活用できない
  - 「改善点なし」の一文で済ませ、Phase 10の指摘事項を教訓化しない
- **適用条件**: Phase 12 Task 5 実行時（全タスクで必須）
- **発見日**: 2026-03-07
- **関連タスク**: TASK-UI-03-AGENT-VIEW-ENHANCEMENT




### [Phase12] branch横断 Phase 12 一括監査（workflow複数同時検証）

- **状況**: 1つのworkflowをPASS化しても、同じブランチで更新された他workflowに未準拠が残る
- **アプローチ**:
  - `git status --short` で今回変更workflowを列挙
  - 各workflowに `validate-phase-output` と `validate-phase12-implementation-guide` を実行
  - 欠落は未タスクへ分離し `docs/30-workflows/unassigned-task/` に正規配置
- **結果**: 単体PASSと branch全体PASSを分離して判定できる
- **適用条件**: 同一ブランチで複数workflowを並行更新している場合
- **発見日**: 2026-03-07
- **関連タスク**: TASK-FIX-SETTINGS-PERSIST-ITERABLE-HARDENING-001 再監査

### [Phase12] `verify-all-specs` PASS と Phase 12 完了は同義ではない（dual validator gate）

- **状況**: workflow 10/11/12 で `verify-all-specs` は PASS だが、Phase 12 実装ガイド欠落や必須セクション欠落が残存した。
- **成功パターン**:
  - 完了ゲートを `verify-all-specs` + `validate-phase-output --phase 12` + `validate-phase12-implementation-guide` の3点セットに固定する
  - FAIL項目は workflow 別に未タスクへ分離し、`docs/30-workflows/unassigned-task/` へ即時配置する
  - 未タスクは `audit-unassigned-tasks --target-file` と `verify-unassigned-links` で当日検証する
- **失敗パターン**:
  - `verify-all-specs` PASS のみで「Phase 12 完了」と判断する
  - 未タスクを作成しても配置/フォーマット監査を省略する
- **適用条件**: branch 内で複数workflowを同時更新・同時監査する場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-PHASE12-BRANCH-CROSS-AUDIT（再確認）

### [Phase12] current workflow placeholder 排除 + legacy baseline 二軸報告（TASK-10A-F 再同期）

- **状況**: current workflow の `manual-test-result.md` や `screenshots/README.md` に `P53` / `代替` / `スクリーンショット不可` が残ったままでも、system spec 側が更新済みだと「全体としては揃っている」と誤認しやすい
- **アプローチ**:
  - screenshot 必須タスクでは current workflow から placeholder 文言を除去し、`TC-ID ↔ png` の実証跡だけを残す
  - `implementation-guide.md` はテンプレート段階で `## Part 1` / `## Part 2`、`APIシグネチャ`、`エラーハンドリング`、`設定項目と定数一覧` を先置きする
  - 未タスク確認は `新規未タスク` と `legacy baseline` を分離し、`currentViolations=0` と `baselineViolations>0` を同時に報告する
  - Phase 12 では workflow outputs と system spec を同ターンで更新し、`更新済みを確認` と `今回更新` を書き分ける
- **結果**: 「正本は正しいが current workflow が stale」「今回差分は合格だが directory 全体には legacy 負債が残る」を混同せず報告できる
- **適用条件**: current workflow 再監査、UI screenshot 再取得、legacy unassigned backlog を抱えた docs-heavy task
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-F

### [Phase12] `current=0` でも legacy backlog 参照を省略しない（TASK-SKILL-LIFECYCLE-01）

- **状況**: `audit-unassigned-tasks --json --diff-from HEAD` が `currentViolations=0` を返すと、`unassigned-task-detection.md` が「問題なし」で閉じられ、`docs/30-workflows/unassigned-task/` 全体に残る legacy backlog や既存 remediation task への導線が消えやすい
- **成功パターン**:
  - `今回タスク由来 0 件` と `directory baseline 継続` を別行で記載する
  - `verify-unassigned-links`、`audit --diff-from HEAD`、`audit --json` の値を `spec-update-summary.md` / `phase12-task-spec-compliance-check.md` / `unassigned-task-detection.md` / `task-workflow.md` に同値で同期する
  - baseline backlog に対する既存改善タスクがある場合は、`unassigned-task-detection.md` と `skill-feedback-report.md` に参照を残す
  - Phase 12 の root evidence は `outputs/phase-12/phase12-task-spec-compliance-check.md` とし、SubAgent ごとの判断をここに集約する
- **失敗パターン**:
  - `currentViolations=0` のみを理由に `docs/30-workflows/unassigned-task/` 全体が健全と書く
  - baseline backlog の数値を system spec と outputs で別々に記録する
  - `skill-feedback-report.md` に task-spec 改善だけを書き、skill-creator 側の改善点を残さない
- **結果**: 「今回差分は task spec 準拠」「既存 backlog は別課題として継続」の責務分離が明確になり、Phase 12 の完了報告が過剰に楽観化しなくなる
- **適用条件**: docs-heavy task、再監査タスク、未タスク 0 件報告を含む Phase 12 全般
- **発見日**: 2026-03-11
- **関連タスク**: TASK-SKILL-LIFECYCLE-01

### [Phase12] Light Mode 全画面 white/black 基準 + compatibility bridge 固定（TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001）

- **状況**: `tokens.css` を white/black 基準へ直しても、renderer 側の `text-white` / `bg-gray-*` / `border-white/*` などが残り、全画面で Light Mode が崩れる。さらに desktop CI の一部 shard fail と screenshot stale が同時に起きやすい
- **成功パターン**:
  - 先に light token baseline を `#ffffff / #000000` に固定する
  - `rg -n "text-white|bg-white/|border-white/|text-gray-|bg-gray-|border-gray-" apps/desktop/src/renderer` で renderer 全域の hardcoded neutral class を棚卸しする
  - token 修正だけで足りない場合は `globals.css` に compatibility bridge を入れ、共通 primitives を token へ寄せる
  - GitHub desktop CI が shard 単位で落ちたら `pnpm --filter @repo/desktop exec vitest run --shard=<n>/16` で同じ shard を local 再現する
  - baseline を変えたら screenshot を撮り直し、`validate-phase11-screenshot-coverage` を PASS へ戻してから system spec を同期する
- **失敗パターン**:
  - token table だけ更新して renderer-wide class drift を監査しない
  - 互換 bridge を入れず、画面ごとの個別修正だけで全体整合を取ろうとする
  - broad rerun だけで CI fail の原因調査を終える
  - light baseline を変えた後も旧 screenshot をそのまま使う
- **結果**: white background / black text の全画面共通基準、shard 再現による局所修正、再取得 screenshot を同一テンプレートで扱えるようになり、Light Mode 系の再監査が短手順で再利用可能になった
- **適用条件**: global theme remediation、design token 再是正、contrast 回帰、Phase 11 screenshot 再取得を伴う UI task
- **発見日**: 2026-03-11
- **関連タスク**: TASK-FIX-LIGHT-THEME-TOKEN-FOUNDATION-001

### [Phase12] light theme shared color migration は token scope / component scope / verification-only lane を分離する（TASK-FIX-LIGHT-THEME-SHARED-COLOR-MIGRATION-001）

- **状況**: global light remediation 後の follow-up task で、親 unassigned-task の対象一覧をそのまま使うと current worktree の実体とずれやすい。settings/auth/workspace をまたぐため、UI だけ読んでも system spec 抽出が漏れやすい
- **成功パターン**:
  - Phase 1 で current worktree の hardcoded color inventory を取り直し、old unassigned-task の対象を盲信しない
  - primary targets を `ThemeSelector` / `AuthModeSelector` / `AuthKeySection` / `AccountSection` / `ApiKeysSection` / `AuthView` / `WorkspaceSearchPanel` に固定し、`SettingsView` / `SettingsCard` / `DashboardView` は verification-only lane に落とす
  - token foundation は親 workflow、current task は component migration、wrapper は verification-only として 3 lane に分離する
  - `ui-ux-design-system` / `ui-ux-settings` / `ui-ux-feature-components` / `ui-ux-components` / `ui-ux-search-panel` / `ui-ux-portal-patterns` / `rag-desktop-state` / `api-ipc-auth` / `api-ipc-system` / `architecture-auth-security` / `security-electron-ipc` / `security-principles` / `task-workflow` / `lessons-learned` の要否を同一ターンで判定する
  - `spec_created` task では Phase 1-3 を completed に固定してから、Phase 4+ を planned のまま書く
- **失敗パターン**:
  - `SettingsView` / `DashboardView` を親 task のまま P1 扱いし、actual inventory を補正しない
  - token baseline の議論と component migration を同じ仕様書で進める
  - `ui-ux-*` だけ読んで `api-ipc-*` / `security-*` / `rag-desktop-state` / `ui-ux-portal-patterns` を落とす
  - Phase 1-3 gate 前に Phase 4-13 を completed 扱いにする
- **結果**: `spec_created` UI task でも current inventory と system spec 抽出セットが揃い、後続の実装 lane / regression guard / Phase 12 同期が短手順で再利用できる
- **適用条件**: Light Mode follow-up、component migration、settings/auth/workspace を跨ぐ UI task、spec-only workflow 再監査
- **発見日**: 2026-03-12
- **関連タスク**: TASK-FIX-LIGHT-THEME-SHARED-COLOR-MIGRATION-001

### [Phase 12] loopback screenshot capture は localhost 不達時に current build static server を自動起動する

- **状況**: screenshot capture script が `http://127.0.0.1:<port>` / `http://localhost:<port>` を前提にしていると、preview / static serve を別ターミナルで起動し忘れた瞬間に `ERR_CONNECTION_REFUSED` で落ちる
- **アプローチ**:
  1. capture 実行前に loopback `baseUrl` の readiness probe を行う
  2. 不達かつ参照先が loopback の場合のみ、current worktree `apps/desktop/out/renderer` をローカル static server で自動配信する
  3. capture 完了後は自動起動した server を cleanup し、`phase11-capture-metadata.json` / `manual-test-result.md` / Phase 12 レポートに fallback 使用を記録する
  4. `current build` の asset hash と capture timestamp が同一 worktree 由来であることを確認する
- **結果**: 「人手 preflight が1つ漏れただけで Phase 11 が全停止する」状態を避けつつ、current build 正本での screenshot 証跡を維持できる
- **適用条件**: worktree 上の UI 再撮影、loopback baseUrl 固定の capture script、preview source drift を避けたい Phase 11/12 再監査
- **発見日**: 2026-03-12
- **関連タスク**: TASK-IMP-LIGHT-THEME-CONTRAST-REGRESSION-GUARD-001

### [Testing] コンポーネント分割テスト戦略パターン（TASK-043D）

- **状況**: 大規模コンポーネント（AgentView 556行テスト）を複数の子コンポーネントに分割する際、テストの責務境界が曖昧になり、テストケースの重複や漏れが発生する
- **アプローチ**:
  1. 各分割コンポーネントに独立テストファイルを新設（`AdvancedSettingsPanel.test.tsx`, `ExecuteButton.test.tsx` 等）
  2. レイアウトテスト（`.layout.test.tsx`）を親コンポーネントに残し、子コンポーネントの配置・表示条件を検証
  3. Store統合テスト（`.store-integration.test.tsx`）を別ファイルで管理し、Store操作とIPC連携を分離
- **テストファイル命名規則**:

| ファイル種別 | 命名パターン | 責務 |
| --- | --- | --- |
| UIテスト | `{Component}.test.tsx` | レンダリング、ユーザー操作 |
| レイアウトテスト | `{Parent}.layout.test.tsx` | 子コンポーネント配置・表示条件 |
| Store統合テスト | `{Component}.store-integration.test.tsx` | Store操作・IPC連携 |
| セレクタテスト | `{slice}.selectors.test.ts` | 純粋なセレクタロジック |

- **結果**: 分割後の各コンポーネントが独立してテスト可能になり、テストの実行速度向上と保守性改善を実現
- **適用条件**: コンポーネントが300行以上、または3つ以上の子コンポーネントに分割する場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **適用例**: AgentView → AdvancedSettingsPanel, ExecuteButton, FloatingExecutionBar, RecentExecutionList, SkillChip

### [Testing] P31回帰テストパターン（renderHook参照安定性検証）（TASK-043D）

- **状況**: Zustand Store Hooks無限ループ（P31/P48）の修正後、回帰検証パターンが未確立で再発リスクが残る
- **アプローチ**:
  - `renderHook` + `act` で個別セレクタの参照安定性を検証する独立テストファイルを作成
  - テストファイル命名: `{slice}.p31-regression.test.ts`
  - 検証ポイント:
    1. セレクタが `rerender()` 後も同一参照（`===`）を返すこと
    2. `useShallow` 適用の派生セレクタが `.filter()` / `.map()` 後も安定すること
    3. `useEffect` 依存配列にアクション関数を含めた場合に `renderCount < 10` であること
- **テスト構造**:

```typescript
// agentSlice.p31-regression.test.ts
describe("P31回帰テスト: セレクタ参照安定性", () => {
  it("アクションセレクタが rerender 後も同一参照を返す", () => {
    const { result, rerender } = renderHook(() => useSetAgentConfig());
    const ref1 = result.current;
    rerender();
    expect(result.current).toBe(ref1); // 同一参照
  });

  it("useShallow派生セレクタがshallow比較で安定する", () => {
    const { result, rerender } = renderHook(() => useFilteredSkills());
    const ref1 = result.current;
    rerender();
    expect(result.current).toEqual(ref1); // shallow equal
  });
});
```

- **結果**: P31/P48の回帰を自動検出可能になり、Store Hook変更時の安全ネットとして機能
- **適用条件**: Zustand個別セレクタHookを追加・変更した場合。特に `.filter()` / `.map()` を含む派生セレクタ
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../.claude/rules/06-known-pitfalls.md), [06-known-pitfalls.md#P48](../../.claude/rules/06-known-pitfalls.md)

### [Testing] Store統合テスト分離パターン（UI/Store/セレクタ3層）（TASK-043D）

- **状況**: hook内でStore操作・IPC呼び出し・localStateが混在するとモック境界が不明確になり、テストの信頼性が低下する
- **アプローチ**:
  1. **UIテスト**（`.test.tsx`）: レンダリングとユーザー操作のみ検証。Storeはモック化
  2. **Store統合テスト**（`.store-integration.test.tsx`）: Store操作とIPC連携を検証。UIレンダリングは不要
  3. **セレクタテスト**（`.selectors.test.ts`）: 純粋なセレクタロジックのみ。副作用なし
- **モック境界の明確化**:

| テスト層 | Storeモック | IPCモック | DOMレンダリング |
| --- | --- | --- | --- |
| UIテスト | する | する | する |
| Store統合テスト | しない（実Store使用） | する | しない |
| セレクタテスト | しない（実Store使用） | 不要 | しない |

- **結果**: テスト失敗時の原因特定が容易になり、モック設定の複雑性が分散。各層が独立して実行可能
- **適用条件**: コンポーネントがZustand Storeと密結合し、IPC経由でデータ取得する場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **適用例**: SkillAnalysisView, SkillCreateWizard

### [ビルド・環境] Worktree環境初期化プロトコル（TASK-043D）

- **状況**: git worktreeで作業ブランチを作成した直後、`@repo/shared` の解決エラーによりdesktopアプリが起動不能になる
- **原因**: worktreeは `.git` ディレクトリを共有するが `node_modules` は共有しないため、依存関係が未解決の状態で起動を試みる
- **アプローチ**: worktree作成直後に以下の初期化プロトコルを実行する

```bash
# 1. worktreeディレクトリに移動
cd .worktrees/<name>

# 2. 依存関係インストール
pnpm install

# 3. 共有パッケージビルド（@repo/shared が未ビルドだとdesktop/webが参照不能）
pnpm --filter @repo/shared build

# 4. 動作確認
pnpm --filter @repo/desktop dev
```

- **結果**: worktree環境での開発開始までの手順が標準化され、`MODULE_NOT_FOUND` エラーを予防
- **適用条件**: git worktreeで新しい作業ブランチを作成する場合
- **P7派生**: ネイティブモジュールのバイナリ不一致問題（P7）と同根。Node.jsバージョンが異なる場合は `pnpm store prune && pnpm install --force` も追加
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN

### [Testing] 品質ゲート仕様先行パターン（テストマトリクス事前定義）（TASK-043D）

- **状況**: 実装後にテスト戦略を設計すると、テストの網羅性が低下し、重要な検証観点が漏れる
- **アプローチ**: 実装前にテスト基準を定義し、品質ゲートとして機能させる
  1. **A/B/C観点の統合テストマトリクス定義**: 機能軸（A）、非機能軸（B）、回帰軸（C）の3観点でテストケースを分類
  2. **unit/integration/regressionの分類**: 各テストケースにテストレベルを付与
  3. **検証コマンドと判定基準の固定**: `pnpm vitest run --coverage` のカバレッジ基準を事前に定義（Line 80%、Branch 60%、Function 80%）
  4. **後続タスクへの引き渡し観点の明示**: テスト設計で検出した未カバー領域を後続タスクの入力として記録
- **テストマトリクス例**:

| 観点 | テストケース | レベル | 判定基準 |
| --- | --- | --- | --- |
| A: 機能 | 各コンポーネント独立テスト | unit | 全ケースPASS |
| B: 非機能 | P31回帰テスト、参照安定性 | regression | renderCount < 10 |
| C: 統合 | Store-IPC連携テスト | integration | モック境界明確 |

- **結果**: テスト設計が実装の品質ゲートとして機能し、「テストがあるから安心」ではなく「テスト基準を満たしたから安心」への転換を実現
- **適用条件**: 新機能開発・リファクタリング・コンポーネント分割など、テスト戦略の再設計が必要な場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **クロスリファレンス**: [02-code-quality.md#カバレッジ基準](../../.claude/rules/02-code-quality.md)

### [IPC] IPC Fallback Handler DRYヘルパーパターン（TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001）

- **状況**: Supabase未設定時にProfile 11ch + Avatar 3ch のIPCハンドラが未登録でクラッシュする問題。既存の`registerAuthFallbackHandlers()`と同一構造で追加が必要
- **アプローチ**:
  1. `createNotConfiguredResponse(code, message)` でレスポンス生成を共通化
  2. `registerFallbackHandlers(handlers: ReadonlyArray<FallbackHandler>)` で登録ループを共通化
  3. Auth/Profile/Avatar の3ドメインが同一パターン（ヘルパー共有 + ReadonlyArray タプル + for...of）
  4. エラーコードは `packages/shared/types/auth.ts` で `as const` 定義し型安全に
- **結果**: 3関数の構造的一貫性を達成。共通ヘルパーにより将来のドメイン追加も最小コスト
- **適用条件**: 外部サービス未設定時に複数IPCチャンネルのフォールバックが必要な場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001

### [Phase 12] P50パターン: 既実装→検証モード切替の全Phase適応（TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001）

- **状況**: Phase 1でソースコードを読んだ際、`registerProfileFallbackHandlers()`と`registerAvatarFallbackHandlers()`が既に実装済みであることを発見。Phase 1-13のワークフローが「新規実装」前提で設計されていた
- **アプローチ**:
  1. Phase 1: 要件の「検証」に転換（既存コードとの照合）
  2. Phase 2-3: 設計の「検証」（既存実装との設計一致確認）
  3. Phase 4-5: テストを新規作成し、既存実装に対してGREEN確認
  4. Phase 6-12: テスト拡充・品質検証・ドキュメントは通常通り実行
- **結果**: 19テスト全GREEN、仕様書13ファイル+391行更新、全AC 6/6 PASS
- **標準ルール**:
  - Phase 1 開始時に `git log --oneline -20 -- <対象ファイル>` で実装状況を確認
  - 既実装の場合は各Phase成果物に「P50パターン該当」を明記
  - テスト作成（Phase 4）は既実装でも必ず実施（回帰検知のため）
- **発見日**: 2026-03-08

### [Phase 12] 失敗パターン: Phase 1で既実装チェックせず新規実装モードで進行

- **症状**: Phase 4でテストを書こうとした際に対応する実装が既に存在し、Phase 5の実装が不要になる。不要なコード重複作成リスクがある
- **回避策**: Phase 1（要件定義）で「現在の実装状態の調査」を必須ステップとして含める
- **発見日**: 2026-03-08

### [テスト] テスト正規表現がエラーコード内/をパスと誤検出

- **状況**: セキュリティテスト（T-P5）でエラーメッセージに内部パスが含まれないことを検証。エラーコードが`profile/not-configured`のように`/`を含む
- **症状**: `/\//`（スラッシュ検出）正規表現が`profile/not-configured`の`/`にマッチし、テストが偽陽性で失敗
- **解決策**: パス検出用正規表現を`/\/(src|apps|node_modules)\//`に変更
- **標準ルール**: セキュリティテストのパス検出は「ディレクトリ名を含むパスパターン」で検出する
- **発見日**: 2026-03-08
- **関連タスク**: TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001

### [状態管理] Zustand Store 並行実行ガードパターン（TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001）

- **状況**: Store の async アクション（executeSkill 等）がIPC呼び出しを含み、ユーザー操作（ボタン連打等）で二重実行される可能性がある
- **アプローチ**:
  1. Store層: async 操作前に `if (get().isExecuting) return;` で同期チェック
  2. UI層: `isExecuting` 状態を参照してボタンの `disabled` 属性を制御（二重防御）
  3. `isExecuting` フラグは `set({ isExecuting: true })` で即時設定し、完了/エラー時は listener 経由でクリーンアップ
- **実装テンプレート**:

```typescript
// Store層ガード
actionName: async (param) => {
  const { isExecuting } = get();
  if (isExecuting) return; // 同期チェック — async 操作前に配置
  set({ isExecuting: true });
  try {
    await ipcCall(param);
  } finally {
    // 完了/エラー時のクリーンアップは listener 経由で実施
  }
};
```

- **テストテンプレート**:

```typescript
// flushMicrotasks で async 操作を進める
function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => { setTimeout(resolve, 0); });
}

// ガードテスト
const firstCall = getState().action("first");
await flushMicrotasks();
expect(getState().isExecuting).toBe(true);
await getState().action("second"); // ガードされるべき
expect(mockIpc).toHaveBeenCalledTimes(1);
```

- **注意事項**:
  - テスト実行は `cd apps/desktop && pnpm vitest run` で対象パッケージから実行する（P40準拠）
  - UI側は `isExecuting` をプリミティブ直接セレクタで参照する（P31準拠）
  - `useShallow` は不要（boolean はプリミティブ型のため P48 非該当）
- **適用条件**: Store の async アクションが IPC 呼び出しやネットワークリクエストを含み、ユーザー操作で二重実行される可能性がある場合
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../.claude/rules/06-known-pitfalls.md), [06-known-pitfalls.md#P40](../../.claude/rules/06-known-pitfalls.md)

### [Phase 12] current workflow 再監査で CLI drift / 未タスクフォーマット / skill同期を同時に閉じる

- **状況**: 実装は完了しているが、Phase 12 再監査で `validate-phase-output` のCLI例、未タスク指示書フォーマット、skill側パターン知見がずれていることがある
- **アプローチ**:
  1. `validate-phase-output.js <workflow-dir>` を正本コマンドとして workflow / template / system spec の記述を一括照合する
  2. 新規未タスクは 9セクションテンプレートで作成し、`audit-unassigned-tasks --json --diff-from HEAD --target-file <file>` が `currentViolations=0` になるまで閉じない
  3. `documentation-changelog.md` / `skill-feedback-report.md` に「どの skill を更新したか」を明記する
  4. `phase-12-documentation.md`、`artifacts.json`、`outputs/artifacts.json`、`index.md` を同一ターンで同期する
- **結果**: current workflow の PASS 判定と、再利用知見の skill 反映が分断されなくなる
- **適用条件**: Phase 12 再監査、branch 再確認、current workflow の stale 修正
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001

### [Phase 11] BrowserRouter 配下の screenshot harness は descendant route で作る

- **状況**: 既存アプリが `BrowserRouter` 配下で動作しているのに、review harness 内で `MemoryRouter` を重ねると描画が落ちる
- **アプローチ**:
  1. App ルートに review 用 path を追加する
  2. harness コンポーネントは既存 Router の子として描画し、Router を再生成しない
  3. route param が不要なら props / store mock で依存を外す
  4. screenshot スクリプトには pageerror 出力を入れて route 構成の崩れを早期検知する
- **結果**: 画面検証用導線を足しても App shell を壊さず、TC 証跡を安定取得できる
- **適用条件**: React Router 利用中の画面検証、preview harness 追加、Phase 11 screenshot 再取得
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001

### [Phase 12] 明示 screenshot 要求では plan / metadata / reset guard まで閉じる

- **状況**: ユーザーが画面検証を明示していても、`NON_VISUAL` 代替や shell bypass のみで完了扱いにすると、実画面証跡と state reset の破壊条件を見落としやすい
- **アプローチ**:
  1. screenshot 方針は `SCREENSHOT` を強制し、workflow 配下へ `screenshot-plan.md` と `screenshots/phase11-capture-metadata.json` を保存する
  2. `validate-phase11-screenshot-coverage` で `TC-ID ↔ png` の 1:1 を確認する
  3. 公開ビュー bypass は shell 公開だけで閉じず、state reset 除外条件と nav 到達性をコード・workflow・system spec へ同時転記する
  4. worktree では `pnpm install --frozen-lockfile` を preflight に追加し、optional dependency 欠落で screenshot/テストが不安定化する前に止める
  5. 未タスク判定は `verify-unassigned-links` と `audit --diff-from HEAD` を併用し、`currentViolations=0` と `baselineViolations>=0` を分離して記録する
- **結果**: 画面検証要求を満たしつつ、bypass と reset の相殺や legacy backlog の誤読を防げる
- **適用条件**: 認証 UI の再監査、公開ビュー追加、Phase 11 screenshot 再取得、worktree での UI検証
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001

### [Phase 12] persist/auth bug は bug path metadata と screenshot harness を分離する

- **状況**: `skipAuth=true` のような補助導線で screenshot は取得できても、auth / persist / App shell 初期化由来の bug path は bypass され、false negative になりうる
- **アプローチ**:
  1. bug path の確認は通常ルートで行い、`navigation.type` / debug log absence / storage snapshot を metadata に保存する
  2. 画面証跡は dedicated harness へ分離し、本番コンポーネント + 公開 contract をそのまま使って状態固定する
  3. `task-workflow.md` / `lessons-learned.md` / `documentation-changelog.md` に「bug path と screenshot path を分離した」事実を同一ターンで記録する
  4. repo-wide に残る workaround は current task へ抱え込まず、`docs/30-workflows/unassigned-task/` へ未タスク化して `audit --target-file` で閉じる
- **結果**: screenshot PASS だけで不具合再発を見逃すリスクを減らし、current task の責務も守れる
- **適用条件**: persist / auth / initialization bug の Phase 11-12 再監査、App shell が不安定な UI 検証、`skipAuth=true` や `dev-skip-auth` を使う撮影導線
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-APP-DEBUG-LOCALSTORAGE-CLEAR-001

### [Phase 12] workspace UI 再監査では current build static serve と 4観点の目視/挙動検証をセットにする

- **状況**: worktree 上の UI 再撮影で Vite preview が別 source を向いたり、右 preview panel の resize 方向逆転、watch hook の再登録、light theme 補助テキストの視認性不足が別々に混入しやすい
- **アプローチ**:
  1. worktree の preview source に揺れがある場合は、current worktree の `apps/desktop/out/renderer` を static server で配信し、その URL を screenshot capture の唯一の参照先にする
  2. 右側 preview panel は `reverse` 方向 resize を前提に、drag 後の panel 幅が期待方向へ変化することを manual test と screenshot で確認する
  3. file watch 系 hook は callback ref を分離し、callback identity が変わっても watch の再登録が起きない設計を優先する
  4. light theme の screenshot は補助テキスト、status bar、chip などの低コントラスト要素を Apple UI/UX engineer 観点で目視確認し、沈んだ要素があれば再撮影前にクラス/色を是正する
  5. `task-workflow.md` / `lessons-learned.md` / `documentation-changelog.md` に「static serve を使った理由」「4観点の確認結果」「再発条件」を同一ターンで記録する
- **結果**: source drift、レイアウト逆転、watcher churn、見た目品質の取りこぼしを 1 回の UI 再監査でまとめて閉じられる
- **適用条件**: workspace 系 UI、3-pane layout、file watcher を伴う preview、worktree での Phase 11 screenshot 再取得
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-04A-WORKSPACE-LAYOUT

### [Phase 12] docs-only parent workflow は pointer/index/spec/script/mirror を 1 sweep で閉じる

- **状況**: completed-task 移管後の親 workflow では `task-060` 相当の parent pointer doc だけ直しても、completed-task pointer docs、legacy index、`interfaces-*`、capture script、skill mirror に stale path / status が残りやすい。さらに user が screenshot を要求すると docs-heavy task でも evidence 再編が必要になる
- **アプローチ**:
  1. `parent pointer -> completed-task pointer docs -> task-000/master index -> task-090/legacy index -> interfaces-* -> capture script -> mirror root` を 1 manifest として固定する
  2. path/status drift は `node scripts/validate-<parent-sweep>.mjs --json`、mirror drift は `diff -qr .claude/skills/<skill> .agents/skills/<skill>` で同一ターンに確認する
  3. `task-workflow.md` / `ui-ux-feature-components.md` / `interfaces-*` / `lessons-learned.md` / `workflow-<feature>.md` を仕様書別 SubAgent に分け、実装内容と苦戦箇所を別仕様書で重複させすぎない
  4. user が screenshot を要求した docs-heavy task では、current build 再撮影に固執せず same-day child workflow evidence を current workflow に集約し、review board を生成する
  5. `verify-unassigned-links` の exact counts、`currentViolations=0 / baselineViolations=*`、`spec-update-summary.md` の SubAgent 実行ログを summary / task-workflow / lessons に同値転記する
- **結果**: parent 導線 drift、mirror drift、representative evidence の散逸を 1 回の Phase 12 再監査で閉じられる
- **適用条件**: docs-only parent workflow、completed-task 移管後の親台帳是正、representative visual re-audit を伴う task
- **発見日**: 2026-03-12
- **関連タスク**: UT-IMP-WORKSPACE-PARENT-REFERENCE-SWEEP-GUARD-001

### [Phase 12] 設計タスク（docs-only）でもサブエージェントに実更新を保留させない

- **状況**: Phase 12 サブエージェントが「設計タスク範囲外」と判断して system spec の実ファイル更新を保留し、LOGS.md / SKILL.md / topic-map.md の更新が未実施のまま Phase 12 が閉じられる
- **アプローチ**:
  1. サブエージェントへの委譲指示に「docs-only タスクであっても Step 1-A〜Step 2 の実ファイル更新は必須。保留不可」を明示的に含める
  2. LOGS.md 2ファイル、SKILL.md 変更履歴、topic-map.md 再生成は docs-only / 実装タスクに関わらず**全タスクで必須**であることをプロンプトに記載する
  3. サブエージェント完了後に `git diff --stat -- .claude/skills/` で実際の変更ファイル数を検証し、期待されるファイル数と一致することを確認する
  4. 新規型定義がある設計タスクでは、型の配置先ファイル（`interfaces-*.md`）への記録も必須とする
- **結果**: サブエージェントの「設計範囲外」判断による更新保留を防止し、Phase 12 完了時の台帳整合性を保証する
- **適用条件**: docs-only / spec_created タスクの Phase 12 サブエージェント委譲
- **発見日**: 2026-03-16
- **関連タスク**: TASK-SKILL-LIFECYCLE-07

### [Phase 12] docs-only close-out の implementation anchor 追補は target path と duplicate source 判定を先に固定する

- **状況**: `scope-definition.md` など既存成果物へ implementation anchor を 1 行追記する docs-only close-out では、target source path が stale でも summary/changelog だけ整って見えやすい。さらに source unassigned docs の duplicate source / ID collision を current diff と誤認すると、不要な follow-up を増やしやすい
- **アプローチ**:
  1. implementation anchor を追記する前に `test -f <source-path>` などで target source path の実在を確認し、current fact を root evidence と completed ledger へ同値転記する
  2. duplicate source / ID collision は `current diff` と `wider governance baseline` に分離し、baseline なら lessons / summary に理由だけを残して新規未タスクを増やさない
  3. `system-spec-update-summary.md` / `documentation-changelog.md` / `phase12-task-spec-compliance-check.md` に、anchor 追補・baseline 判定・no-new-unassigned の同値を残す
  4. 仕上げに `generate-index.js` → `validate-structure.js` → mirror sync → `diff -qr` を実行し、`.claude` 正本と `.agents` mirror の parity を確認する
- **結果**: 1 行の docs-only 追補でも false green を防ぎ、duplicate source 系の backlog 過密化を抑制できる
- **適用条件**: implementation anchor の追補、docs-only family close-out、source unassigned docs に duplicate source / ID collision が混ざる Phase 12
- **発見日**: 2026-03-27
- **関連タスク**: UT-EXEC-01

### [Phase 12] workspace preview/search は cross-cutting spec を追加同期する（TASK-UI-04C）

- **状況**: `PreviewPanel` / `QuickFileSearch` / renderer local fallback を実装しても、`ui-ux-feature-components.md` だけでは shortcut、dialog token、error surface、resilience pattern の再利用導線が不足する
- **アプローチ**:
  1. UI基本6+αに加えて、`ui-ux-search-panel.md` / `ui-ux-design-system.md` / `error-handling.md` / `architecture-implementation-patterns.md` の要否を最初に判定する
  2. `Cmd/Ctrl+P`、focus trap、top N、`score=0` 除外のような検索挙動は `ui-ux-search-panel.md` に同期する
  3. dialog 幅、radius、shadow、filename/path hierarchy は `ui-ux-design-system.md` に同期する
  4. timeout / read failure / parse failure / renderer crash / no-match の UI 応答は `error-handling.md` に同期する
  5. renderer timeout+retry、fuzzy 判定分離、structured preview fallback は `architecture-implementation-patterns.md` に同期する
  6. 上記4仕様書を `ui-ux-components.md` / `ui-ux-feature-components.md` / `task-workflow.md` / `lessons-learned.md` と同一ターンで閉じる
- **結果**: preview/search 系 UI の実装内容と苦戦箇所が「UI一覧」「機能仕様」「検索パネル」「デザイン」「エラー契約」「再利用パターン」の6導線から辿れる
- **適用条件**: workspace preview、quick search dialog、renderer local search、recoverable parse fallback を含む UI タスク
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-04C-WORKSPACE-PREVIEW

### [Phase 12] cross-cutting follow-up は `workflow-<feature>.md` へ統合正本を追加する（UT-IMP-WORKSPACE-PREVIEW-SEARCH-RESILIENCE-GUARD-001）

- **状況**: `task-workflow.md` / `lessons-learned.md` / UI spec / architecture spec に実装内容と苦戦箇所が入っていても、再利用入口が散ると次回の初動で「どこから読むか」の探索コストが高い
- **アプローチ**:
  1. cross-cutting follow-up では `references/workflow-<feature>.md` を新規作成し、実装内容、苦戦箇所、5分解決カード、SubAgent 分担、検証コマンド、最適なファイル形成を 1 ファイルへ集約する
  2. `indexes/resource-map.md` のクイックルックアップ、`indexes/quick-reference.md` の検索語 / 読む順番、`SKILL.md` の直リンクを同一ターンで追加する
  3. workflow 正本には `outputs/phase-12/phase12-task-spec-compliance-check.md` を root evidence として関連ドキュメントに含め、Task 12-1〜12-5 / Step 1-A〜1-G / Step 2 の判断根拠へ即座に降りられるようにする
  4. `task-workflow.md` / `lessons-learned.md` / `<domain-spec>` への同期は薄くしつつ、workflow 正本に「なぜその仕様へ振り分けたか」を書いて重複転記を抑える
- **結果**: 実装内容、苦戦箇所、screen evidence、Phase 12 root evidence の入口が 1 つに集約され、次回の同種課題を短時間で再現しやすくなる
- **適用条件**: UI/architecture/error/state を横断する follow-up task、screen verification を伴う Phase 12 再監査、system spec 更新先が 6 仕様書以上に広がる task
- **発見日**: 2026-03-13
- **関連タスク**: UT-IMP-WORKSPACE-PREVIEW-SEARCH-RESILIENCE-GUARD-001

### [Phase 12] implementation-guide と coverage matrix の validator 文字列を固定する

- **状況**: `implementation-guide.md` が内容的には正しくても、Part 1 に日常例えのトリガー語が弱いと再監査で判定がぶれる。`phase-11-manual-test.md` も見出しが `### 画面カバレッジマトリクス【...】` のように変形すると、coverage validator が section 抽出できず warning になる
- **アプローチ**:
  1. Part 1 の「日常の例え」段落には `たとえば` を最低1回明示して、再監査時に人手判断へ依存しない記述にする
  2. `phase-11-manual-test.md` の見出しは `## 画面カバレッジマトリクス` を固定し、修飾語は見出し本文に混ぜず直下説明文へ逃がす
  3. Phase 12 テンプレートの検証コマンドへ `rg -n '^## 画面カバレッジマトリクス$'` と `たとえば` を含むチェックを追加し、実行前に機械確認する
  4. coverage warning が残る場合は `manual-test-checklist` 代替採用理由と、見出し/証跡列の実体差分を `documentation-changelog.md` へ記録する
- **結果**: validator 実装差分に引きずられず、Phase 11/12 の再監査を 1 回で閉じやすくなる
- **適用条件**: UIタスクの Phase 12 再監査、implementation-guide 修正、coverage warning 再発防止
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-04B-WORKSPACE-CHAT
### [Testing] 3層テストハードニング戦略（TASK-10A-G）

- **状況**: テスト専用タスクでも Phase 12 まで含めると、Layer 1/2/3 の責務が混線しやすい
- **標準ルール**:
  - Layer 1 は Main IPC、Layer 2 は Store 統合、Layer 3 は既存 UI 回帰の拡張に限定する
  - supporting artifact の件数、handler-scope coverage、open backlog の canonical path を同時に同期する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Testing] 並列エージェント分割によるPhase実行効率化（TASK-10A-G）

- **状況**: テストファイルや Phase 12 成果物が複数ある場合、順次実行では時間が伸び、1エージェント集中では中断リスクが上がる
- **アプローチ**:
  - Phase 4-5: Layer 1/2/3 の独立したテストファイルを関心ごとで分離して並列化する
  - Phase 12: 実装ガイド、仕様書更新、レポート群の 3 系統へ分割する
  - 相互依存がある LOGS/SKILL や workflow 台帳更新は同一担当へ集約する
- **標準ルール**:
  - 1エージェントあたり 3 ファイル以下を目安にする
  - 完了判定は「実装物」「仕様物」「証跡」を最後に単一ターンで集約する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Testing] カバレッジ計測のスコープ不一致（TASK-10A-G）

- **状況**: `vitest --coverage` はファイル全体を計測するため、テスト対象ハンドラ以外が Line/Function Coverage を押し下げる
- **症状**: `skill:create` テストなのに `skillHandlers.ts` 全体の未実行コードが混ざり、値が誤読されやすい
- **解決策**:
  - coverage 文書に `handler-scope coverage` を明記する
  - Branch Coverage を主判定にし、必要なら `coverage-by-handler.ts` で対象範囲を切り出す
- **標準ルール**: 巨大ファイルの coverage は「対象ハンドラ」と「ファイル全体」を分けて報告する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Phase12] supporting artifact の実測値を summary 文書と同値に固定する（TASK-10A-G）

- **状況**: `spec-update-summary.md` だけ直っていても `test-documentation.md` など supporting artifact が旧件数のまま残ることがある
- **標準ルール**:
  - Phase 12 完了前に `rg -n "43件|55 tests|合計" docs/30-workflows/<task>/outputs/phase-12/` を実行する
  - summary 文書、supporting artifact、system spec の 3 点で同じ実測値を揃える
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Phase12] open backlog はタスク状態に応じた canonical path へ同期してから閉じる（TASK-10A-G）

- **状況**: 未実施 backlog の参照先が、Phase 12 中の root 配置と完了移管後の archive 配置で揺れると探索導線がぶれる
- **成功パターン**:
  - Phase 12 中は `docs/30-workflows/unassigned-task/` に配置する
  - workflow 完了後は `docs/30-workflows/completed-tasks/<task>/unassigned-task/` へ移して archive 側の参照へ張り替える
  - `verify-unassigned-links.js` と `audit-unassigned-tasks --json --diff-from HEAD --target-file ...` を続けて実行する
- **標準ルール**: 未実施 backlog はタスク状態に応じて canonical path を切り替え、関連参照も同一ターンで更新する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Phase12] SubAgent 完了後の git diff --stat 事後検証固定（TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001）

- **状況**: SubAgent が documentation-changelog.md に「Step 1-A〜Step 2 完了」と記載したが、実際には topic-map.md 再生成が未実行だった。SubAgent の自己申告だけでは完了の信頼性が不十分（P4/P43/P51 の複合再発）
- **成功パターン**:
  1. SubAgent 完了報告の直後に `git diff --stat -- .claude/skills/` で実際の変更ファイル一覧を取得する
  2. 変更ファイル一覧と documentation-changelog の記録を突合し、差分がゼロであることを確認する
  3. topic-map.md 再生成は `node scripts/generate-index.js` の実行後に `git diff -- .claude/skills/*/indexes/` で変更有無を検証する
  4. LOGS.md 2ファイル更新は `git diff --stat -- */LOGS.md` で2ファイルの変更を確認する
- **失敗パターン**:
  - SubAgent の完了報告をそのまま信頼して git diff 検証を省略する
  - documentation-changelog に「完了」を先に書いてから実作業を行う（P4再発）
- **検証コマンド**:

```bash
# SubAgent完了後の必須検証セット
git diff --stat -- .claude/skills/
git diff --stat -- */LOGS.md
git diff --stat -- .claude/skills/*/indexes/topic-map.md
```

- **適用条件**: Phase 12 で SubAgent に仕様書更新を委譲する全タスク
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001
- **関連Pitfall**: P4, P43, P51

### [UI] ブロッキングコンポーネント・タイムアウトパターン（TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001）

- **状況**: AuthGuard が認証状態の解決を無期限に待機し、IPC ハングや認証初期化失敗時にユーザーが画面に到達できなくなった。認証ガード、データローディング、外部サービス待機など、UI をブロックするコンポーネントがハングする可能性がある場面で再利用可能なパターン
- **アプローチ**:
  1. **DisplayState 型に "timed-out" 状態を追加**: `type DisplayState = "loading" | "authenticated" | "unauthenticated" | "timed-out"` のように、タイムアウト専用の状態を設計する
  2. **useEffect + setTimeout でタイムアウト検知**: P13（advanceTimersByTime 必須）に準拠し、タイマーでタイムアウトを検知する
  3. **純粋関数で状態判定**: `getAuthState(isLoading, isAuthenticated, isTimedOut): DisplayState` のようにテスタブルな純粋関数で判定ロジックを分離する
  4. **フォールバック UI**: タイムアウト時にリトライボタン + 代替導線（Settings 直接アクセス等）を提供する
  5. **bypass 対象ビューの条件分岐**: 特定のルート（例: `/settings`）を認証ガード外に配置し、catch-all route パターンで未認証時も到達可能にする
- **テスト戦略**:
  - P13: `vi.advanceTimersByTime()` で1ステップずつタイマーを進める（`runAllTimers` 禁止）
  - P39: happy-dom 環境では `fireEvent` を使用（`userEvent` 禁止）
  - P31: Zustand 個別セレクタを使用して依存配列の安定性を確保
  - 回帰テスト: タイムアウトなしの通常認証フロー確認を必須に含める
- **bypass ルート追加基準**:
  - 条件1: そのビューが認証状態に依存しない機能を持つ（例: API キー設定、一般設定）
  - 条件2: 認証失敗時にユーザーが自力で復旧するための操作を含む
  - 条件3: bypass しても機密データへのアクセスが発生しない
- **コード構造例**:

```typescript
// getAuthState.ts - 純粋関数で判定
export function getAuthState(
  isLoading: boolean,
  isAuthenticated: boolean,
  isTimedOut: boolean
): DisplayState {
  if (isTimedOut) return "timed-out";
  if (isLoading) return "loading";
  if (isAuthenticated) return "authenticated";
  return "unauthenticated";
}

// useAuthState.ts - タイムアウト検知Hook
export function useAuthState(timeoutMs = 10000) {
  const [isTimedOut, setIsTimedOut] = useState(false);
  const isLoading = useAuthIsLoading();
  useEffect(() => {
    if (!isLoading) return;
    const timer = setTimeout(() => setIsTimedOut(true), timeoutMs);
    return () => clearTimeout(timer);
  }, [isLoading, timeoutMs]);
  // ...
}

// AuthTimeoutFallback.tsx - フォールバックUI
export function AuthTimeoutFallback({ onRetry }: Props) {
  return (
    <div>
      <p>認証の確認に時間がかかっています</p>
      <button onClick={onRetry}>再試行</button>
      <a href="/settings">設定画面へ</a>
    </div>
  );
}
```

- **参照実装ファイル**:
  - `apps/desktop/src/renderer/components/AuthGuard/useAuthState.ts`
  - `apps/desktop/src/renderer/components/AuthGuard/getAuthState.ts`
  - `apps/desktop/src/renderer/components/AuthGuard/AuthTimeoutFallback.tsx`
- **適用条件**: 認証ガード、データローディング、外部サービス待機など、UIをブロックするコンポーネントがハングする可能性がある場合
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001
- **関連Pitfall**: P13, P31, P39

### [Testing] サブエージェントでのテスト実行タイムアウト対策（exit code 144）（TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001）

- **状況**: サブエージェント（Task agent）で `pnpm vitest run` を実行した際、テストが完了前にプロセスが強制終了され exit code 144（SIGUSR2 によるシグナル終了）が返された。サブエージェントの実行時間制限によりテスト結果が得られない
- **アプローチ**:
  1. **テスト対象を最小化**: `pnpm vitest run src/renderer/components/AuthGuard/` のように対象ディレクトリを限定する
  2. **並列実行を制限**: `--no-file-parallelism` オプションでワーカー間の競合を回避する
  3. **タイムアウトを明示設定**: `--testTimeout=10000` でテスト単位のタイムアウトを設定する
  4. **メインエージェントでの実行にフォールバック**: サブエージェントで exit code 144 が発生した場合、メインエージェントで同一コマンドを再実行する
  5. **テスト結果の事前保存**: サブエージェントに `--reporter=json --outputFile=test-results.json` を渡し、中断しても部分結果を回収可能にする
- **検証コマンド**:

```bash
# サブエージェント向け: 対象限定 + 並列制限 + タイムアウト設定
cd apps/desktop && pnpm vitest run src/renderer/components/AuthGuard/ \
  --no-file-parallelism \
  --testTimeout=10000

# exit code 144 発生時のフォールバック（メインエージェントで実行）
cd apps/desktop && pnpm vitest run src/renderer/components/AuthGuard/
```

- **失敗パターン**:
  - サブエージェントでプロジェクト全体のテスト（`pnpm vitest run`）を実行する
  - exit code 144 を「テスト失敗」と誤認し、コードの修正を試みる
  - サブエージェントの実行時間制限を考慮せずに大量テストを委譲する
- **適用条件**: サブエージェント（Task agent）でテストを実行する全ケース
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001

### [テスト] Preload テストで electronAPI が undefined（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: `await import("../index")` 後に `electronAPI?.invoke()` を呼ぶと `undefined`。optional chaining で静かに失敗
- **原因**: `process.contextIsolated` が未設定で、contextBridge パスに入らず `electronAPI` が公開されなかった
- **教訓**: Preload テストでは `Object.defineProperty(process, "contextIsolated", { value: true })` が必須。`electronAPI` が `undefined` の場合は contextBridge パスの通過を確認
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [Phase12] Onboarding overlay / Settings rerun / MINOR formalization の三点同期（TASK-UI-09-ONBOARDING-WIZARD）

- **状況**: Onboarding Wizard のような multi-step UI では、本体実装は完了していても、`verification-report.md` に coverage 不足や `act(...)` warning、手動試験には rerun 導線の discoverability 課題が残ることがある
- **アプローチ**:
  1. **本体完了と follow-up を分離**: workflow 本体は completed 系ステータスを維持し、軽微課題のみ未タスク化する
  2. **raw 候補を精査**: `verification-report.md` / `manual-test-result.md` / `documentation-changelog.md` から候補を抽出し、責務単位で統合する
  3. **既存 follow-up spec も current contract へ再同期**: `docs/30-workflows/unassigned-task/*.md` の `2.2` / `3.1` / `3.5` / 検証手順を確認し、`completed=false reset` のような旧契約を残さない
  4. **canonical spec を 5 点同期**: `task-workflow.md` / `ui-ux-feature-components.md` / `ui-ux-navigation.md` / `ui-ux-settings.md` / `lessons-learned.md` を同一ターンで更新する
  5. **苦戦箇所を再利用知識へ昇格**: 状態同期、画面導線、テスト warning、discoverability、follow-up drift の 5 軸で lessons learned に残す
  6. **差分監査で閉じる**: `verify-unassigned-links.js`、`audit-unassigned-tasks.js --diff-from HEAD`、必要なら `--target-file` を実行し、`currentViolations=0` を確認する
- **成功パターン**:
  - UI 完了判定を崩さずに、軽微事項だけを formalized backlog として管理できる
  - Phase 12 成果物、system spec、unassigned-task の 3 点に同じ未タスク ID が残り、検索経路がぶれない
  - 既存 follow-up 本文と system spec が同じ rerun / persist 契約を指し、次回着手時の読み直しコストが小さい
  - スクリーンショット証跡と backlog が直接結びつき、再確認時に迷わない
- **失敗パターン**:
  - `verification-report.md` の MINOR を文書内コメントのまま放置する
  - `docs/30-workflows/unassigned-task/` の既存本文が `completed=false reset` など旧契約のまま残る
  - `ui-ux-feature-components.md` だけ更新し、navigation / settings / lessons learned を更新しない
  - 苦戦ポイントを会話で消費し、次回のスキル改善へ残さない
- **適用条件**: 初回起動オーバーレイ、Settings からの rerun、persist key、Phase 11 screenshot を含む UI タスク
- **発見日**: 2026-03-13
- **関連タスク**: TASK-UI-09-ONBOARDING-WIZARD

### [Phase12] shallow PASS 表を root evidence へ昇格し、split 親から sibling backlog まで監査する（TASK-IMP-AIWORKFLOW-REQUIREMENTS-LINE-BUDGET-REFORM-001）

- **状況**: `phase12-task-spec-compliance-check.md` が成果物の存在確認だけに寄ると、`implementation-guide.md` の型/API不足や active 未タスクの10見出し欠落を見逃しやすい。さらに `verify-unassigned-links` を親 `task-workflow.md` だけで実行すると、split 後の `task-workflow-backlog.md` に残る未タスクリンクを取りこぼす
- **アプローチ**:
  1. `phase12-task-spec-compliance-check.md` を root evidence とし、Task 12-1〜12-5、`phase-12-documentation.md`、implementation guide 品質、未タスク10見出し、current/baseline 分離、system spec 同期を 1 ファイルへ集約する
  2. implementation guide は `validate-phase12-implementation-guide` を必須で通し、Part 1 の `たとえば`、Part 2 の `type` / `interface`、API/CLI シグネチャ、エッジケース、設定項目を機械確認する
  3. `verify-unassigned-links` は親 `task-workflow.md` 指定時に sibling `task-workflow*.md` も走査する前提で使い、`missing=0` を compliance / detection / task-workflow に同値転記する
  4. active 未タスクは `audit-unassigned-tasks --json --diff-from HEAD --target-file ...` と `--diff-from HEAD` の両方で `currentViolations=0` を確認し、repo 全体 `audit --json` は baseline 参考値として分離記録する
- **結果**: Phase 12 の shallow PASS を防ぎ、split 後の backlog 見落としも同時に回収できる
- **適用条件**: docs-heavy task、line-budget reform、spec-only task、または Phase 12 再監査で shallow summary のまま閉じた形跡がある場合
- **発見日**: 2026-03-13
- **関連タスク**: TASK-IMP-AIWORKFLOW-REQUIREMENTS-LINE-BUDGET-REFORM-001

### [Phase12] 未タスク root canonical path 固定 + 9セクション正規化（TASK-SKILL-LIFECYCLE-04）

- **状況**: Phase 10 MINOR 由来の未タスクを workflow ローカル `tasks/unassigned-task/` に置いたまま進めると、`audit-unassigned-tasks --target-file` の監査境界と衝突し、指定ディレクトリ配置確認が不成立になる
- **アプローチ**:
  1. 未タスク指示書は `docs/30-workflows/unassigned-task/` を正本として作成する
  2. 指示書本文は task-spec テンプレート準拠（`## 1..9` + `3.5 実装課題と解決策`）で作る
  3. `phase-12-documentation.md` / `unassigned-task-detection.md` / `task-workflow-backlog.md` / 関連仕様書の参照を同ターンで root path へ同期する
  4. `verify-unassigned-links` と `audit-unassigned-tasks --json --diff-from HEAD --target-file ...` をセットで実行し、links と品質を別軸で判定する
- **結果**: 「未タスクは検出済みだが指定ディレクトリに未配置」という状態を防ぎ、再監査時の説明責任を保持できる
- **失敗パターン**:
  - workflow ローカル `tasks/unassigned-task/` を temporary として残し、参照更新を後回しにする
  - `current`/`baseline` の監査値だけを見て、物理配置の確認を省略する
  - 未タスク本文を簡易フォーマットで作成し、`3.5` の教訓継承を省略する
- **適用条件**: Phase 12 Task 4 で MINOR 指摘を未タスク化する全 workflow
- **発見日**: 2026-03-14
- **関連タスク**: TASK-SKILL-LIFECYCLE-04

### [Phase12] current canonical set / artifact inventory / legacy register / mirror parity を same-wave で閉じる（TASK-SKILL-LIFECYCLE-04）

- **状況**: 実装内容と苦戦箇所は記録済みでも、`resource-map` / `quick-reference` / `legacy-ordinal-family-register` / mirror 同期が別ターンになると、引用導線と再現手順が stale になる
- **アプローチ**:
  1. `workflow-<feature>.md` を統合正本として新設し、`current canonical set` と `artifact inventory` を固定する
  2. parent docs（契約/状態/UI）と ledger（task-workflow/backlog/lessons）を同一 wave で更新する
  3. old path/filename がある場合は `legacy-ordinal-family-register.md` の `Current Alias Overrides` へ互換行を追加する
  4. 入口導線として `indexes/resource-map.md` / `indexes/quick-reference.md` を同時更新する
  5. 仕上げに `generate-index.js` → `validate-structure.js` → mirror sync → `diff -qr` を実行して parity を確認する
- **結果**: 実装記録、再利用入口、旧名互換、mirror 一致が 1 wave で閉じ、次回の引用再現コストを下げられる
- **適用条件**: docs-heavy task の Phase 12 再監査、または system spec へ「実装内容 + 苦戦箇所 + 再利用手順」を formalize する場合
- **発見日**: 2026-03-14
- **関連タスク**: TASK-SKILL-LIFECYCLE-04

### [Phase12] design タスクでも「実装済み同期」があるなら Step 2 を先送りしない（TASK-SKILL-LIFECYCLE-05）

- **状況**: タスク種別が `design` だと、`documentation-changelog.md` に「system spec 更新は後続実装で対応」と記載しがちだが、実際には同ターンで仕様追補を実施しているケースがある
- **アプローチ**:
  1. `phase-12-documentation.md` / `documentation-changelog.md` / `spec-update-summary.md` を同時に開き、Task 2 Step 2 の判定を同値に揃える
  2. 実際に system spec を更新した場合は、`design` タスクでも Step 2 を「更新あり」に固定する
  3. planned wording（`実行予定` / `後続タスクで実施` / `保留として記録`）を除去し、実績ログのみ残す
  4. 仕上げに `verify-all-specs` / `validate-phase-output` / `validate-phase12-implementation-guide` / `audit-unassigned-tasks --diff-from HEAD` を再実行し、整合を確認する
- **結果**: 「成果物は存在するが changelog が先送り記述」という矛盾を防止できる
- **失敗パターン**:
  - `design` という理由だけで Step 2 を自動的に「更新なし」にする
  - `phase-12-documentation.md` を `completed` にした後で changelog/summmary を更新しない
  - planned wording を残したまま Phase 12 を完了扱いにする
- **適用条件**: docs-heavy / spec-created / design タスクで、Phase 12 中に system spec 追補が発生した場合
- **発見日**: 2026-03-15
- **関連タスク**: TASK-SKILL-LIFECYCLE-05

### [設計] 依存タスク連携における型変換点の明示パターン（TASK-SKILL-LIFECYCLE-08）

- **状況**: 設計タスクシリーズ（Task06→Task07→Task08 など）で、前タスクの出力型が後タスクの判定入力として使われる際、型の変換点が暗黙のまま設計書に残り、後続実装時に依存ドリフトが発生した
- **アプローチ**:
  - 依存タスク連携を以下のフォーマットで Phase 2 設計書に明示する:
    ```
    Task-N 出力型 -> Adapter -> Task-M 入力型 -> Port -> 判定結果
    ```
  - 例: `PublishReadinessMetrics (Task07出力) -> CompatibilityAdapter -> CompatibilityCheckResult (Task08入力) -> PublishReadinessChecker -> PublishReadiness`
  - Adapter が必要な場合は Phase 2 で型変換ロジックの責務を定義し、実装タスクに引き継ぐ
- **成功パターン**:
  - Phase 2 設計書の「依存タスク連携」セクションに変換点テーブルを作成する
  - 変換点ごとに「入力型ソース」「変換ルール」「出力型ターゲット」を3列で定義する
  - 後続の実装タスクに Adapter 実装を未タスクとして引き継ぐ
- **失敗パターン**:
  - 依存タスクの型が「互換性あり」と暗黙想定し、変換点を設計書に記載しない
  - 後続実装タスクの Phase 2 で「Task-N の出力をそのまま使う」と判断し、型変換コストを後回しにする
- **適用条件**: 複数の設計タスクが型契約でシリアル接続されているシリーズ設計
- **発見日**: 2026-03-17
- **関連タスク**: TASK-SKILL-LIFECYCLE-08

### [UI] データ駆動UIパターン（定数配列 + map() + 条件付きレンダリング）（TASK-SKILL-LIFECYCLE-02）

- **状況**: SkillCenterView の CTA（Call-to-Action）ボタン群を、スキルライフサイクルの各ジョブ（分析・作成・改善）に応じて動的に生成する必要があった。新しいジョブ種別の追加を最小コストで実現したい
- **アプローチ**:
  1. CTA の定義を `JOB_GUIDES` 定数配列として外部化する（ラベル・アイコン・遷移先・説明を1オブジェクトにまとめる）
  2. `JOB_GUIDES.map()` でCTAカードを自動生成し、条件付きレンダリング（`isVisible` プロパティ等）で表示制御する
  3. 新しいCTAは配列に1行追加するだけで、コンポーネント本体の修正が不要になる
- **結果**:
  - 拡張性: 新規CTA追加が定数配列への1行追加で完結（OCP準拠）
  - テスタビリティ: 定数配列を直接テストでき、レンダリング結果との突合も容易
  - 保守性: UIロジックとデータ定義が分離され、レビュー負荷が低減
- **適用条件**: 同一レイアウトで複数のアクション項目を並べるUI（CTA群、メニュー項目、ダッシュボードカード等）
- **失敗パターン**:
  - 各CTAを個別の JSX ブロックとしてハードコードする（新規追加のたびにコンポーネント全体を修正）
  - 条件分岐を `if/else` チェーンで記述する（項目数増加で可読性が崩壊）
- **発見日**: 2026-03-18
- **関連タスク**: TASK-SKILL-LIFECYCLE-02
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../rules/06-known-pitfalls.md)（Store依存を避けProps駆動にする理由）

```typescript
// 定数配列でCTAを定義（1行追加で拡張可能）
const JOB_GUIDES = [
  {
    job: "analysis" as const,
    label: "スキル分析",
    icon: SearchIcon,
    description: "既存スキルの品質を分析します",
    navigateTo: ViewType.SkillAnalysis,
  },
  {
    job: "create" as const,
    label: "スキル作成",
    icon: PlusIcon,
    description: "新しいスキルを作成します",
    navigateTo: ViewType.SkillCreate,
  },
  // 新規CTA追加はここに1行追加するだけ
] as const;

// map() で自動生成 + 条件付きレンダリング
{JOB_GUIDES.map((guide) => (
  <CTACard
    key={guide.job}
    label={guide.label}
    icon={guide.icon}
    description={guide.description}
    onClick={() => navigate(guide.navigateTo)}
  />
))}
```

### [Testing] Zustand個別セレクタ + happy-dom fireEvent テスト統合パターン（TASK-SKILL-LIFECYCLE-02）

- **状況**: SkillCenterView のCTAボタンクリックテストで、Zustand Store の状態管理と happy-dom テスト環境の制約を同時に扱う必要があった
- **アプローチ**:
  1. **Zustand個別セレクタ**: 合成Store Hook（`useSkillCenterStore()`）ではなく、個別セレクタ（`useCurrentView()`, `useSetCurrentView()` 等）を使用し、P31（無限ループ）を防止する
  2. **happy-dom + fireEvent**: `@testing-library/user-event` は happy-dom 環境で Symbol エラーを起こすため（P39）、`fireEvent.click()` を使用する。非同期ハンドラは `await act(async () => { fireEvent.click(el) })` で包む
  3. **vi.mock によるセレクタモック**: 個別セレクタを `vi.mock` で差し替え、テスト対象コンポーネントの依存を最小化する
- **結果**:
  - P31/P39 の両方を回避しつつ、CTAボタンのナビゲーション動作を安定してテスト
  - テストが happy-dom 環境で一貫して PASS
  - セレクタモックにより Store 全体のセットアップが不要
- **適用条件**: happy-dom 環境で Zustand Store を使用するコンポーネントのインタラクションテスト
- **失敗パターン**:
  - `userEvent.setup()` を happy-dom 環境で使用する（P39: Symbol操作エラー）
  - 合成Store Hook の戻り値関数を `useEffect` 依存配列に含める（P31: 無限ループ）
- **発見日**: 2026-03-18
- **関連タスク**: TASK-SKILL-LIFECYCLE-02
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../rules/06-known-pitfalls.md), [06-known-pitfalls.md#P39](../../rules/06-known-pitfalls.md)

```typescript
// vi.mock で個別セレクタをモック
vi.mock("@/renderer/store/selectors", () => ({
  useCurrentView: vi.fn(() => "skillCenter"),
  useSetCurrentView: vi.fn(() => mockSetCurrentView),
}));

// happy-dom 環境では fireEvent を使用（userEvent は使用禁止）
it("CTAクリックでビュー遷移する", async () => {
  render(<SkillCenterView />);
  const ctaButton = screen.getByRole("button", { name: "スキル作成" });

  await act(async () => {
    fireEvent.click(ctaButton);
  });

  expect(mockSetCurrentView).toHaveBeenCalledWith("skillCreate");
});
```

- **結果**: 分割後の各コンポーネントが独立してテスト可能になり、テストの実行速度向上と保守性改善を実現
- **適用条件**: コンポーネントが300行以上、または3つ以上の子コンポーネントに分割する場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **適用例**: AgentView → AdvancedSettingsPanel, ExecuteButton, FloatingExecutionBar, RecentExecutionList, SkillChip

### [Testing] P31回帰テストパターン（renderHook参照安定性検証）（TASK-043D）

- **状況**: Zustand Store Hooks無限ループ（P31/P48）の修正後、回帰検証パターンが未確立で再発リスクが残る
- **アプローチ**:
  - `renderHook` + `act` で個別セレクタの参照安定性を検証する独立テストファイルを作成
  - テストファイル命名: `{slice}.p31-regression.test.ts`
  - 検証ポイント:
    1. セレクタが `rerender()` 後も同一参照（`===`）を返すこと
    2. `useShallow` 適用の派生セレクタが `.filter()` / `.map()` 後も安定すること
    3. `useEffect` 依存配列にアクション関数を含めた場合に `renderCount < 10` であること
- **テスト構造**:

```typescript
// agentSlice.p31-regression.test.ts
describe("P31回帰テスト: セレクタ参照安定性", () => {
  it("アクションセレクタが rerender 後も同一参照を返す", () => {
    const { result, rerender } = renderHook(() => useSetAgentConfig());
    const ref1 = result.current;
    rerender();
    expect(result.current).toBe(ref1); // 同一参照
  });

  it("useShallow派生セレクタがshallow比較で安定する", () => {
    const { result, rerender } = renderHook(() => useFilteredSkills());
    const ref1 = result.current;
    rerender();
    expect(result.current).toEqual(ref1); // shallow equal
  });
});
```

- **結果**: P31/P48の回帰を自動検出可能になり、Store Hook変更時の安全ネットとして機能
- **適用条件**: Zustand個別セレクタHookを追加・変更した場合。特に `.filter()` / `.map()` を含む派生セレクタ
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../.claude/rules/06-known-pitfalls.md), [06-known-pitfalls.md#P48](../../.claude/rules/06-known-pitfalls.md)

### [Testing] Store統合テスト分離パターン（UI/Store/セレクタ3層）（TASK-043D）

- **状況**: hook内でStore操作・IPC呼び出し・localStateが混在するとモック境界が不明確になり、テストの信頼性が低下する
- **アプローチ**:
  1. **UIテスト**（`.test.tsx`）: レンダリングとユーザー操作のみ検証。Storeはモック化
  2. **Store統合テスト**（`.store-integration.test.tsx`）: Store操作とIPC連携を検証。UIレンダリングは不要
  3. **セレクタテスト**（`.selectors.test.ts`）: 純粋なセレクタロジックのみ。副作用なし
- **モック境界の明確化**:

| テスト層 | Storeモック | IPCモック | DOMレンダリング |
| --- | --- | --- | --- |
| UIテスト | する | する | する |
| Store統合テスト | しない（実Store使用） | する | しない |
| セレクタテスト | しない（実Store使用） | 不要 | しない |

- **結果**: テスト失敗時の原因特定が容易になり、モック設定の複雑性が分散。各層が独立して実行可能
- **適用条件**: コンポーネントがZustand Storeと密結合し、IPC経由でデータ取得する場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **適用例**: SkillAnalysisView, SkillCreateWizard

### [ビルド・環境] Worktree環境初期化プロトコル（TASK-043D）

- **状況**: git worktreeで作業ブランチを作成した直後、`@repo/shared` の解決エラーによりdesktopアプリが起動不能になる
- **原因**: worktreeは `.git` ディレクトリを共有するが `node_modules` は共有しないため、依存関係が未解決の状態で起動を試みる
- **アプローチ**: worktree作成直後に以下の初期化プロトコルを実行する

```bash
# 1. worktreeディレクトリに移動
cd .worktrees/<name>

# 2. 依存関係インストール
pnpm install

# 3. 共有パッケージビルド（@repo/shared が未ビルドだとdesktop/webが参照不能）
pnpm --filter @repo/shared build

# 4. 動作確認
pnpm --filter @repo/desktop dev
```

- **結果**: worktree環境での開発開始までの手順が標準化され、`MODULE_NOT_FOUND` エラーを予防
- **適用条件**: git worktreeで新しい作業ブランチを作成する場合
- **P7派生**: ネイティブモジュールのバイナリ不一致問題（P7）と同根。Node.jsバージョンが異なる場合は `pnpm store prune && pnpm install --force` も追加
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN

### [Testing] 品質ゲート仕様先行パターン（テストマトリクス事前定義）（TASK-043D）

- **状況**: 実装後にテスト戦略を設計すると、テストの網羅性が低下し、重要な検証観点が漏れる
- **アプローチ**: 実装前にテスト基準を定義し、品質ゲートとして機能させる
  1. **A/B/C観点の統合テストマトリクス定義**: 機能軸（A）、非機能軸（B）、回帰軸（C）の3観点でテストケースを分類
  2. **unit/integration/regressionの分類**: 各テストケースにテストレベルを付与
  3. **検証コマンドと判定基準の固定**: `pnpm vitest run --coverage` のカバレッジ基準を事前に定義（Line 80%、Branch 60%、Function 80%）
  4. **後続タスクへの引き渡し観点の明示**: テスト設計で検出した未カバー領域を後続タスクの入力として記録
- **テストマトリクス例**:

| 観点 | テストケース | レベル | 判定基準 |
| --- | --- | --- | --- |
| A: 機能 | 各コンポーネント独立テスト | unit | 全ケースPASS |
| B: 非機能 | P31回帰テスト、参照安定性 | regression | renderCount < 10 |
| C: 統合 | Store-IPC連携テスト | integration | モック境界明確 |

- **結果**: テスト設計が実装の品質ゲートとして機能し、「テストがあるから安心」ではなく「テスト基準を満たしたから安心」への転換を実現
- **適用条件**: 新機能開発・リファクタリング・コンポーネント分割など、テスト戦略の再設計が必要な場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-043D-TEST-QUALITY-GATE-DESIGN
- **クロスリファレンス**: [02-code-quality.md#カバレッジ基準](../../.claude/rules/02-code-quality.md)

### [IPC] IPC Fallback Handler DRYヘルパーパターン（TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001）

- **状況**: Supabase未設定時にProfile 11ch + Avatar 3ch のIPCハンドラが未登録でクラッシュする問題。既存の`registerAuthFallbackHandlers()`と同一構造で追加が必要
- **アプローチ**:
  1. `createNotConfiguredResponse(code, message)` でレスポンス生成を共通化
  2. `registerFallbackHandlers(handlers: ReadonlyArray<FallbackHandler>)` で登録ループを共通化
  3. Auth/Profile/Avatar の3ドメインが同一パターン（ヘルパー共有 + ReadonlyArray タプル + for...of）
  4. エラーコードは `packages/shared/types/auth.ts` で `as const` 定義し型安全に
- **結果**: 3関数の構造的一貫性を達成。共通ヘルパーにより将来のドメイン追加も最小コスト
- **適用条件**: 外部サービス未設定時に複数IPCチャンネルのフォールバックが必要な場合
- **発見日**: 2026-03-08
- **関連タスク**: TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001

### [Phase 12] P50パターン: 既実装→検証モード切替の全Phase適応（TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001）

- **状況**: Phase 1でソースコードを読んだ際、`registerProfileFallbackHandlers()`と`registerAvatarFallbackHandlers()`が既に実装済みであることを発見。Phase 1-13のワークフローが「新規実装」前提で設計されていた
- **アプローチ**:
  1. Phase 1: 要件の「検証」に転換（既存コードとの照合）
  2. Phase 2-3: 設計の「検証」（既存実装との設計一致確認）
  3. Phase 4-5: テストを新規作成し、既存実装に対してGREEN確認
  4. Phase 6-12: テスト拡充・品質検証・ドキュメントは通常通り実行
- **結果**: 19テスト全GREEN、仕様書13ファイル+391行更新、全AC 6/6 PASS
- **標準ルール**:
  - Phase 1 開始時に `git log --oneline -20 -- <対象ファイル>` で実装状況を確認
  - 既実装の場合は各Phase成果物に「P50パターン該当」を明記
  - テスト作成（Phase 4）は既実装でも必ず実施（回帰検知のため）
- **発見日**: 2026-03-08

### [Phase 12] 失敗パターン: Phase 1で既実装チェックせず新規実装モードで進行

- **症状**: Phase 4でテストを書こうとした際に対応する実装が既に存在し、Phase 5の実装が不要になる。不要なコード重複作成リスクがある
- **回避策**: Phase 1（要件定義）で「現在の実装状態の調査」を必須ステップとして含める
- **発見日**: 2026-03-08

### [テスト] テスト正規表現がエラーコード内/をパスと誤検出

- **状況**: セキュリティテスト（T-P5）でエラーメッセージに内部パスが含まれないことを検証。エラーコードが`profile/not-configured`のように`/`を含む
- **症状**: `/\//`（スラッシュ検出）正規表現が`profile/not-configured`の`/`にマッチし、テストが偽陽性で失敗
- **解決策**: パス検出用正規表現を`/\/(src|apps|node_modules)\//`に変更
- **標準ルール**: セキュリティテストのパス検出は「ディレクトリ名を含むパスパターン」で検出する
- **発見日**: 2026-03-08
- **関連タスク**: TASK-FIX-SUPABASE-FALLBACK-PROFILE-AVATAR-001

### [状態管理] Zustand Store 並行実行ガードパターン（TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001）

- **状況**: Store の async アクション（executeSkill 等）がIPC呼び出しを含み、ユーザー操作（ボタン連打等）で二重実行される可能性がある
- **アプローチ**:
  1. Store層: async 操作前に `if (get().isExecuting) return;` で同期チェック
  2. UI層: `isExecuting` 状態を参照してボタンの `disabled` 属性を制御（二重防御）
  3. `isExecuting` フラグは `set({ isExecuting: true })` で即時設定し、完了/エラー時は listener 経由でクリーンアップ
- **実装テンプレート**:

```typescript
// Store層ガード
actionName: async (param) => {
  const { isExecuting } = get();
  if (isExecuting) return; // 同期チェック — async 操作前に配置
  set({ isExecuting: true });
  try {
    await ipcCall(param);
  } finally {
    // 完了/エラー時のクリーンアップは listener 経由で実施
  }
};
```

- **テストテンプレート**:

```typescript
// flushMicrotasks で async 操作を進める
function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => { setTimeout(resolve, 0); });
}

// ガードテスト
const firstCall = getState().action("first");
await flushMicrotasks();
expect(getState().isExecuting).toBe(true);
await getState().action("second"); // ガードされるべき
expect(mockIpc).toHaveBeenCalledTimes(1);
```

- **注意事項**:
  - テスト実行は `cd apps/desktop && pnpm vitest run` で対象パッケージから実行する（P40準拠）
  - UI側は `isExecuting` をプリミティブ直接セレクタで参照する（P31準拠）
  - `useShallow` は不要（boolean はプリミティブ型のため P48 非該当）
- **適用条件**: Store の async アクションが IPC 呼び出しやネットワークリクエストを含み、ユーザー操作で二重実行される可能性がある場合
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001
- **クロスリファレンス**: [06-known-pitfalls.md#P31](../../.claude/rules/06-known-pitfalls.md), [06-known-pitfalls.md#P40](../../.claude/rules/06-known-pitfalls.md)

### [Phase 12] current workflow 再監査で CLI drift / 未タスクフォーマット / skill同期を同時に閉じる

- **状況**: 実装は完了しているが、Phase 12 再監査で `validate-phase-output` のCLI例、未タスク指示書フォーマット、skill側パターン知見がずれていることがある
- **アプローチ**:
  1. `validate-phase-output.js <workflow-dir>` を正本コマンドとして workflow / template / system spec の記述を一括照合する
  2. 新規未タスクは 9セクションテンプレートで作成し、`audit-unassigned-tasks --json --diff-from HEAD --target-file <file>` が `currentViolations=0` になるまで閉じない
  3. `documentation-changelog.md` / `skill-feedback-report.md` に「どの skill を更新したか」を明記する
  4. `phase-12-documentation.md`、`artifacts.json`、`outputs/artifacts.json`、`index.md` を同一ターンで同期する
- **結果**: current workflow の PASS 判定と、再利用知見の skill 反映が分断されなくなる
- **適用条件**: Phase 12 再監査、branch 再確認、current workflow の stale 修正
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001

### [Phase 11] BrowserRouter 配下の screenshot harness は descendant route で作る

- **状況**: 既存アプリが `BrowserRouter` 配下で動作しているのに、review harness 内で `MemoryRouter` を重ねると描画が落ちる
- **アプローチ**:
  1. App ルートに review 用 path を追加する
  2. harness コンポーネントは既存 Router の子として描画し、Router を再生成しない
  3. route param が不要なら props / store mock で依存を外す
  4. screenshot スクリプトには pageerror 出力を入れて route 構成の崩れを早期検知する
- **結果**: 画面検証用導線を足しても App shell を壊さず、TC 証跡を安定取得できる
- **適用条件**: React Router 利用中の画面検証、preview harness 追加、Phase 11 screenshot 再取得
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-AGENT-EXECUTE-SKILL-CONCURRENCY-GUARD-001

### [Phase 12] 明示 screenshot 要求では plan / metadata / reset guard まで閉じる

- **状況**: ユーザーが画面検証を明示していても、`NON_VISUAL` 代替や shell bypass のみで完了扱いにすると、実画面証跡と state reset の破壊条件を見落としやすい
- **アプローチ**:
  1. screenshot 方針は `SCREENSHOT` を強制し、workflow 配下へ `screenshot-plan.md` と `screenshots/phase11-capture-metadata.json` を保存する
  2. `validate-phase11-screenshot-coverage` で `TC-ID ↔ png` の 1:1 を確認する
  3. 公開ビュー bypass は shell 公開だけで閉じず、state reset 除外条件と nav 到達性をコード・workflow・system spec へ同時転記する
  4. worktree では `pnpm install --frozen-lockfile` を preflight に追加し、optional dependency 欠落で screenshot/テストが不安定化する前に止める
  5. 未タスク判定は `verify-unassigned-links` と `audit --diff-from HEAD` を併用し、`currentViolations=0` と `baselineViolations>=0` を分離して記録する
- **結果**: 画面検証要求を満たしつつ、bypass と reset の相殺や legacy backlog の誤読を防げる
- **適用条件**: 認証 UI の再監査、公開ビュー追加、Phase 11 screenshot 再取得、worktree での UI検証
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001

### [Phase 12] persist/auth bug は bug path metadata と screenshot harness を分離する

- **状況**: `skipAuth=true` のような補助導線で screenshot は取得できても、auth / persist / App shell 初期化由来の bug path は bypass され、false negative になりうる
- **アプローチ**:
  1. bug path の確認は通常ルートで行い、`navigation.type` / debug log absence / storage snapshot を metadata に保存する
  2. 画面証跡は dedicated harness へ分離し、本番コンポーネント + 公開 contract をそのまま使って状態固定する
  3. `task-workflow.md` / `lessons-learned.md` / `documentation-changelog.md` に「bug path と screenshot path を分離した」事実を同一ターンで記録する
  4. repo-wide に残る workaround は current task へ抱え込まず、`docs/30-workflows/unassigned-task/` へ未タスク化して `audit --target-file` で閉じる
- **結果**: screenshot PASS だけで不具合再発を見逃すリスクを減らし、current task の責務も守れる
- **適用条件**: persist / auth / initialization bug の Phase 11-12 再監査、App shell が不安定な UI 検証、`skipAuth=true` や `dev-skip-auth` を使う撮影導線
- **発見日**: 2026-03-09
- **関連タスク**: TASK-FIX-APP-DEBUG-LOCALSTORAGE-CLEAR-001

### [Phase 12] workspace UI 再監査では current build static serve と 4観点の目視/挙動検証をセットにする

- **状況**: worktree 上の UI 再撮影で Vite preview が別 source を向いたり、右 preview panel の resize 方向逆転、watch hook の再登録、light theme 補助テキストの視認性不足が別々に混入しやすい
- **アプローチ**:
  1. worktree の preview source に揺れがある場合は、current worktree の `apps/desktop/out/renderer` を static server で配信し、その URL を screenshot capture の唯一の参照先にする
  2. 右側 preview panel は `reverse` 方向 resize を前提に、drag 後の panel 幅が期待方向へ変化することを manual test と screenshot で確認する
  3. file watch 系 hook は callback ref を分離し、callback identity が変わっても watch の再登録が起きない設計を優先する
  4. light theme の screenshot は補助テキスト、status bar、chip などの低コントラスト要素を Apple UI/UX engineer 観点で目視確認し、沈んだ要素があれば再撮影前にクラス/色を是正する
  5. `task-workflow.md` / `lessons-learned.md` / `documentation-changelog.md` に「static serve を使った理由」「4観点の確認結果」「再発条件」を同一ターンで記録する
- **結果**: source drift、レイアウト逆転、watcher churn、見た目品質の取りこぼしを 1 回の UI 再監査でまとめて閉じられる
- **適用条件**: workspace 系 UI、3-pane layout、file watcher を伴う preview、worktree での Phase 11 screenshot 再取得
- **発見日**: 2026-03-10
- **関連タスク**: TASK-UI-04A-WORKSPACE-LAYOUT

### [Phase 12] docs-only parent workflow は pointer/index/spec/script/mirror を 1 sweep で閉じる

- **状況**: completed-task 移管後の親 workflow では `task-060` 相当の parent pointer doc だけ直しても、completed-task pointer docs、legacy index、`interfaces-*`、capture script、skill mirror に stale path / status が残りやすい。さらに user が screenshot を要求すると docs-heavy task でも evidence 再編が必要になる
- **アプローチ**:
  1. `parent pointer -> completed-task pointer docs -> task-000/master index -> task-090/legacy index -> interfaces-* -> capture script -> mirror root` を 1 manifest として固定する
  2. path/status drift は `node scripts/validate-<parent-sweep>.mjs --json`、mirror drift は `diff -qr .claude/skills/<skill> .agents/skills/<skill>` で同一ターンに確認する
  3. `task-workflow.md` / `ui-ux-feature-components.md` / `interfaces-*` / `lessons-learned.md` / `workflow-<feature>.md` を仕様書別 SubAgent に分け、実装内容と苦戦箇所を別仕様書で重複させすぎない
  4. user が screenshot を要求した docs-heavy task では、current build 再撮影に固執せず same-day child workflow evidence を current workflow に集約し、review board を生成する
  5. `verify-unassigned-links` の exact counts、`currentViolations=0 / baselineViolations=*`、`spec-update-summary.md` の SubAgent 実行ログを summary / task-workflow / lessons に同値転記する
- **結果**: parent 導線 drift、mirror drift、representative evidence の散逸を 1 回の Phase 12 再監査で閉じられる
- **適用条件**: docs-only parent workflow、completed-task 移管後の親台帳是正、representative visual re-audit を伴う task
- **発見日**: 2026-03-12
- **関連タスク**: UT-IMP-WORKSPACE-PARENT-REFERENCE-SWEEP-GUARD-001

### [Phase 12] 設計タスク（docs-only）でもサブエージェントに実更新を保留させない

- **状況**: Phase 12 サブエージェントが「設計タスク範囲外」と判断して system spec の実ファイル更新を保留し、LOGS.md / SKILL.md / topic-map.md の更新が未実施のまま Phase 12 が閉じられる
- **アプローチ**:
  1. サブエージェントへの委譲指示に「docs-only タスクであっても Step 1-A〜Step 2 の実ファイル更新は必須。保留不可」を明示的に含める
  2. LOGS.md 2ファイル、SKILL.md 変更履歴、topic-map.md 再生成は docs-only / 実装タスクに関わらず**全タスクで必須**であることをプロンプトに記載する
  3. サブエージェント完了後に `git diff --stat -- .claude/skills/` で実際の変更ファイル数を検証し、期待されるファイル数と一致することを確認する
  4. 新規型定義がある設計タスクでは、型の配置先ファイル（`interfaces-*.md`）への記録も必須とする
- **結果**: サブエージェントの「設計範囲外」判断による更新保留を防止し、Phase 12 完了時の台帳整合性を保証する
- **適用条件**: docs-only / spec_created タスクの Phase 12 サブエージェント委譲
- **発見日**: 2026-03-16
- **関連タスク**: TASK-SKILL-LIFECYCLE-07

### [Phase 12] workspace preview/search は cross-cutting spec を追加同期する（TASK-UI-04C）

- **状況**: `PreviewPanel` / `QuickFileSearch` / renderer local fallback を実装しても、`ui-ux-feature-components.md` だけでは shortcut、dialog token、error surface、resilience pattern の再利用導線が不足する
- **アプローチ**:
  1. UI基本6+αに加えて、`ui-ux-search-panel.md` / `ui-ux-design-system.md` / `error-handling.md` / `architecture-implementation-patterns.md` の要否を最初に判定する
  2. `Cmd/Ctrl+P`、focus trap、top N、`score=0` 除外のような検索挙動は `ui-ux-search-panel.md` に同期する
  3. dialog 幅、radius、shadow、filename/path hierarchy は `ui-ux-design-system.md` に同期する
  4. timeout / read failure / parse failure / renderer crash / no-match の UI 応答は `error-handling.md` に同期する
  5. renderer timeout+retry、fuzzy 判定分離、structured preview fallback は `architecture-implementation-patterns.md` に同期する
  6. 上記4仕様書を `ui-ux-components.md` / `ui-ux-feature-components.md` / `task-workflow.md` / `lessons-learned.md` と同一ターンで閉じる
- **結果**: preview/search 系 UI の実装内容と苦戦箇所が「UI一覧」「機能仕様」「検索パネル」「デザイン」「エラー契約」「再利用パターン」の6導線から辿れる
- **適用条件**: workspace preview、quick search dialog、renderer local search、recoverable parse fallback を含む UI タスク
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-04C-WORKSPACE-PREVIEW

### [Phase 12] cross-cutting follow-up は `workflow-<feature>.md` へ統合正本を追加する（UT-IMP-WORKSPACE-PREVIEW-SEARCH-RESILIENCE-GUARD-001）

- **状況**: `task-workflow.md` / `lessons-learned.md` / UI spec / architecture spec に実装内容と苦戦箇所が入っていても、再利用入口が散ると次回の初動で「どこから読むか」の探索コストが高い
- **アプローチ**:
  1. cross-cutting follow-up では `references/workflow-<feature>.md` を新規作成し、実装内容、苦戦箇所、5分解決カード、SubAgent 分担、検証コマンド、最適なファイル形成を 1 ファイルへ集約する
  2. `indexes/resource-map.md` のクイックルックアップ、`indexes/quick-reference.md` の検索語 / 読む順番、`SKILL.md` の直リンクを同一ターンで追加する
  3. workflow 正本には `outputs/phase-12/phase12-task-spec-compliance-check.md` を root evidence として関連ドキュメントに含め、Task 12-1〜12-5 / Step 1-A〜1-G / Step 2 の判断根拠へ即座に降りられるようにする
  4. `task-workflow.md` / `lessons-learned.md` / `<domain-spec>` への同期は薄くしつつ、workflow 正本に「なぜその仕様へ振り分けたか」を書いて重複転記を抑える
- **結果**: 実装内容、苦戦箇所、screen evidence、Phase 12 root evidence の入口が 1 つに集約され、次回の同種課題を短時間で再現しやすくなる
- **適用条件**: UI/architecture/error/state を横断する follow-up task、screen verification を伴う Phase 12 再監査、system spec 更新先が 6 仕様書以上に広がる task
- **発見日**: 2026-03-13
- **関連タスク**: UT-IMP-WORKSPACE-PREVIEW-SEARCH-RESILIENCE-GUARD-001

### [Phase 12] implementation-guide と coverage matrix の validator 文字列を固定する

- **状況**: `implementation-guide.md` が内容的には正しくても、Part 1 に日常例えのトリガー語が弱いと再監査で判定がぶれる。`phase-11-manual-test.md` も見出しが `### 画面カバレッジマトリクス【...】` のように変形すると、coverage validator が section 抽出できず warning になる
- **アプローチ**:
  1. Part 1 の「日常の例え」段落には `たとえば` を最低1回明示して、再監査時に人手判断へ依存しない記述にする
  2. `phase-11-manual-test.md` の見出しは `## 画面カバレッジマトリクス` を固定し、修飾語は見出し本文に混ぜず直下説明文へ逃がす
  3. Phase 12 テンプレートの検証コマンドへ `rg -n '^## 画面カバレッジマトリクス$'` と `たとえば` を含むチェックを追加し、実行前に機械確認する
  4. coverage warning が残る場合は `manual-test-checklist` 代替採用理由と、見出し/証跡列の実体差分を `documentation-changelog.md` へ記録する
- **結果**: validator 実装差分に引きずられず、Phase 11/12 の再監査を 1 回で閉じやすくなる
- **適用条件**: UIタスクの Phase 12 再監査、implementation-guide 修正、coverage warning 再発防止
- **発見日**: 2026-03-11
- **関連タスク**: TASK-UI-04B-WORKSPACE-CHAT
### [Testing] 3層テストハードニング戦略（TASK-10A-G）

- **状況**: テスト専用タスクでも Phase 12 まで含めると、Layer 1/2/3 の責務が混線しやすい
- **標準ルール**:
  - Layer 1 は Main IPC、Layer 2 は Store 統合、Layer 3 は既存 UI 回帰の拡張に限定する
  - supporting artifact の件数、handler-scope coverage、open backlog の canonical path を同時に同期する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Testing] 並列エージェント分割によるPhase実行効率化（TASK-10A-G）

- **状況**: テストファイルや Phase 12 成果物が複数ある場合、順次実行では時間が伸び、1エージェント集中では中断リスクが上がる
- **アプローチ**:
  - Phase 4-5: Layer 1/2/3 の独立したテストファイルを関心ごとで分離して並列化する
  - Phase 12: 実装ガイド、仕様書更新、レポート群の 3 系統へ分割する
  - 相互依存がある LOGS/SKILL や workflow 台帳更新は同一担当へ集約する
- **標準ルール**:
  - 1エージェントあたり 3 ファイル以下を目安にする
  - 完了判定は「実装物」「仕様物」「証跡」を最後に単一ターンで集約する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Testing] カバレッジ計測のスコープ不一致（TASK-10A-G）

- **状況**: `vitest --coverage` はファイル全体を計測するため、テスト対象ハンドラ以外が Line/Function Coverage を押し下げる
- **症状**: `skill:create` テストなのに `skillHandlers.ts` 全体の未実行コードが混ざり、値が誤読されやすい
- **解決策**:
  - coverage 文書に `handler-scope coverage` を明記する
  - Branch Coverage を主判定にし、必要なら `coverage-by-handler.ts` で対象範囲を切り出す
- **標準ルール**: 巨大ファイルの coverage は「対象ハンドラ」と「ファイル全体」を分けて報告する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Phase12] supporting artifact の実測値を summary 文書と同値に固定する（TASK-10A-G）

- **状況**: `spec-update-summary.md` だけ直っていても `test-documentation.md` など supporting artifact が旧件数のまま残ることがある
- **標準ルール**:
  - Phase 12 完了前に `rg -n "43件|55 tests|合計" docs/30-workflows/<task>/outputs/phase-12/` を実行する
  - summary 文書、supporting artifact、system spec の 3 点で同じ実測値を揃える
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Phase12] open backlog はタスク状態に応じた canonical path へ同期してから閉じる（TASK-10A-G）

- **状況**: 未実施 backlog の参照先が、Phase 12 中の root 配置と完了移管後の archive 配置で揺れると探索導線がぶれる
- **成功パターン**:
  - Phase 12 中は `docs/30-workflows/unassigned-task/` に配置する
  - workflow 完了後は `docs/30-workflows/completed-tasks/<task>/unassigned-task/` へ移して archive 側の参照へ張り替える
  - `verify-unassigned-links.js` と `audit-unassigned-tasks --json --diff-from HEAD --target-file ...` を続けて実行する
- **標準ルール**: 未実施 backlog はタスク状態に応じて canonical path を切り替え、関連参照も同一ターンで更新する
- **発見日**: 2026-03-09
- **関連タスク**: TASK-10A-G

### [Phase12] SubAgent 完了後の git diff --stat 事後検証固定（TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001）

- **状況**: SubAgent が documentation-changelog.md に「Step 1-A〜Step 2 完了」と記載したが、実際には topic-map.md 再生成が未実行だった。SubAgent の自己申告だけでは完了の信頼性が不十分（P4/P43/P51 の複合再発）
- **成功パターン**:
  1. SubAgent 完了報告の直後に `git diff --stat -- .claude/skills/` で実際の変更ファイル一覧を取得する
  2. 変更ファイル一覧と documentation-changelog の記録を突合し、差分がゼロであることを確認する
  3. topic-map.md 再生成は `node scripts/generate-index.js` の実行後に `git diff -- .claude/skills/*/indexes/` で変更有無を検証する
  4. LOGS.md 2ファイル更新は `git diff --stat -- */LOGS.md` で2ファイルの変更を確認する
- **失敗パターン**:
  - SubAgent の完了報告をそのまま信頼して git diff 検証を省略する
  - documentation-changelog に「完了」を先に書いてから実作業を行う（P4再発）
- **検証コマンド**:

```bash
# SubAgent完了後の必須検証セット
git diff --stat -- .claude/skills/
git diff --stat -- */LOGS.md
git diff --stat -- .claude/skills/*/indexes/topic-map.md
```

- **適用条件**: Phase 12 で SubAgent に仕様書更新を委譲する全タスク
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001
- **関連Pitfall**: P4, P43, P51

### [UI] ブロッキングコンポーネント・タイムアウトパターン（TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001）

- **状況**: AuthGuard が認証状態の解決を無期限に待機し、IPC ハングや認証初期化失敗時にユーザーが画面に到達できなくなった。認証ガード、データローディング、外部サービス待機など、UI をブロックするコンポーネントがハングする可能性がある場面で再利用可能なパターン
- **アプローチ**:
  1. **DisplayState 型に "timed-out" 状態を追加**: `type DisplayState = "loading" | "authenticated" | "unauthenticated" | "timed-out"` のように、タイムアウト専用の状態を設計する
  2. **useEffect + setTimeout でタイムアウト検知**: P13（advanceTimersByTime 必須）に準拠し、タイマーでタイムアウトを検知する
  3. **純粋関数で状態判定**: `getAuthState(isLoading, isAuthenticated, isTimedOut): DisplayState` のようにテスタブルな純粋関数で判定ロジックを分離する
  4. **フォールバック UI**: タイムアウト時にリトライボタン + 代替導線（Settings 直接アクセス等）を提供する
  5. **bypass 対象ビューの条件分岐**: 特定のルート（例: `/settings`）を認証ガード外に配置し、catch-all route パターンで未認証時も到達可能にする
- **テスト戦略**:
  - P13: `vi.advanceTimersByTime()` で1ステップずつタイマーを進める（`runAllTimers` 禁止）
  - P39: happy-dom 環境では `fireEvent` を使用（`userEvent` 禁止）
  - P31: Zustand 個別セレクタを使用して依存配列の安定性を確保
  - 回帰テスト: タイムアウトなしの通常認証フロー確認を必須に含める
- **bypass ルート追加基準**:
  - 条件1: そのビューが認証状態に依存しない機能を持つ（例: API キー設定、一般設定）
  - 条件2: 認証失敗時にユーザーが自力で復旧するための操作を含む
  - 条件3: bypass しても機密データへのアクセスが発生しない
- **コード構造例**:

```typescript
// getAuthState.ts - 純粋関数で判定
export function getAuthState(
  isLoading: boolean,
  isAuthenticated: boolean,
  isTimedOut: boolean
): DisplayState {
  if (isTimedOut) return "timed-out";
  if (isLoading) return "loading";
  if (isAuthenticated) return "authenticated";
  return "unauthenticated";
}

// useAuthState.ts - タイムアウト検知Hook
export function useAuthState(timeoutMs = 10000) {
  const [isTimedOut, setIsTimedOut] = useState(false);
  const isLoading = useAuthIsLoading();
  useEffect(() => {
    if (!isLoading) return;
    const timer = setTimeout(() => setIsTimedOut(true), timeoutMs);
    return () => clearTimeout(timer);
  }, [isLoading, timeoutMs]);
  // ...
}

// AuthTimeoutFallback.tsx - フォールバックUI
export function AuthTimeoutFallback({ onRetry }: Props) {
  return (
    <div>
      <p>認証の確認に時間がかかっています</p>
      <button onClick={onRetry}>再試行</button>
      <a href="/settings">設定画面へ</a>
    </div>
  );
}
```

- **参照実装ファイル**:
  - `apps/desktop/src/renderer/components/AuthGuard/useAuthState.ts`
  - `apps/desktop/src/renderer/components/AuthGuard/getAuthState.ts`
  - `apps/desktop/src/renderer/components/AuthGuard/AuthTimeoutFallback.tsx`
- **適用条件**: 認証ガード、データローディング、外部サービス待機など、UIをブロックするコンポーネントがハングする可能性がある場合
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001
- **関連Pitfall**: P13, P31, P39

### [Testing] サブエージェントでのテスト実行タイムアウト対策（exit code 144）（TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001）

- **状況**: サブエージェント（Task agent）で `pnpm vitest run` を実行した際、テストが完了前にプロセスが強制終了され exit code 144（SIGUSR2 によるシグナル終了）が返された。サブエージェントの実行時間制限によりテスト結果が得られない
- **アプローチ**:
  1. **テスト対象を最小化**: `pnpm vitest run src/renderer/components/AuthGuard/` のように対象ディレクトリを限定する
  2. **並列実行を制限**: `--no-file-parallelism` オプションでワーカー間の競合を回避する
  3. **タイムアウトを明示設定**: `--testTimeout=10000` でテスト単位のタイムアウトを設定する
  4. **メインエージェントでの実行にフォールバック**: サブエージェントで exit code 144 が発生した場合、メインエージェントで同一コマンドを再実行する
  5. **テスト結果の事前保存**: サブエージェントに `--reporter=json --outputFile=test-results.json` を渡し、中断しても部分結果を回収可能にする
- **検証コマンド**:

```bash
# サブエージェント向け: 対象限定 + 並列制限 + タイムアウト設定
cd apps/desktop && pnpm vitest run src/renderer/components/AuthGuard/ \
  --no-file-parallelism \
  --testTimeout=10000

# exit code 144 発生時のフォールバック（メインエージェントで実行）
cd apps/desktop && pnpm vitest run src/renderer/components/AuthGuard/
```

- **失敗パターン**:
  - サブエージェントでプロジェクト全体のテスト（`pnpm vitest run`）を実行する
  - exit code 144 を「テスト失敗」と誤認し、コードの修正を試みる
  - サブエージェントの実行時間制限を考慮せずに大量テストを委譲する
- **適用条件**: サブエージェント（Task agent）でテストを実行する全ケース
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-AUTHGUARD-TIMEOUT-SETTINGS-BYPASS-001

### [テスト] Preload テストで electronAPI が undefined（TASK-FIX-SAFEINVOKE-TIMEOUT-001）

- **状況**: `await import("../index")` 後に `electronAPI?.invoke()` を呼ぶと `undefined`。optional chaining で静かに失敗
- **原因**: `process.contextIsolated` が未設定で、contextBridge パスに入らず `electronAPI` が公開されなかった
- **教訓**: Preload テストでは `Object.defineProperty(process, "contextIsolated", { value: true })` が必須。`electronAPI` が `undefined` の場合は contextBridge パスの通過を確認
- **発見日**: 2026-03-10
- **関連タスク**: TASK-FIX-SAFEINVOKE-TIMEOUT-001

### [Phase12] Onboarding overlay / Settings rerun / MINOR formalization の三点同期（TASK-UI-09-ONBOARDING-WIZARD）

- **状況**: Onboarding Wizard のような multi-step UI では、本体実装は完了していても、`verification-report.md` に coverage 不足や `act(...)` warning、手動試験には rerun 導線の discoverability 課題が残ることがある
- **アプローチ**:
  1. **本体完了と follow-up を分離**: workflow 本体は completed 系ステータスを維持し、軽微課題のみ未タスク化する
  2. **raw 候補を精査**: `verification-report.md` / `manual-test-result.md` / `documentation-changelog.md` から候補を抽出し、責務単位で統合する
  3. **既存 follow-up spec も current contract へ再同期**: `docs/30-workflows/unassigned-task/*.md` の `2.2` / `3.1` / `3.5` / 検証手順を確認し、`completed=false reset` のような旧契約を残さない
  4. **canonical spec を 5 点同期**: `task-workflow.md` / `ui-ux-feature-components.md` / `ui-ux-navigation.md` / `ui-ux-settings.md` / `lessons-learned.md` を同一ターンで更新する
  5. **苦戦箇所を再利用知識へ昇格**: 状態同期、画面導線、テスト warning、discoverability、follow-up drift の 5 軸で lessons learned に残す
  6. **差分監査で閉じる**: `verify-unassigned-links.js`、`audit-unassigned-tasks.js --diff-from HEAD`、必要なら `--target-file` を実行し、`currentViolations=0` を確認する
- **成功パターン**:
  - UI 完了判定を崩さずに、軽微事項だけを formalized backlog として管理できる
  - Phase 12 成果物、system spec、unassigned-task の 3 点に同じ未タスク ID が残り、検索経路がぶれない
  - 既存 follow-up 本文と system spec が同じ rerun / persist 契約を指し、次回着手時の読み直しコストが小さい
  - スクリーンショット証跡と backlog が直接結びつき、再確認時に迷わない
- **失敗パターン**:
  - `verification-report.md` の MINOR を文書内コメントのまま放置する
  - `docs/30-workflows/unassigned-task/` の既存本文が `completed=false reset` など旧契約のまま残る
  - `ui-ux-feature-components.md` だけ更新し、navigation / settings / lessons learned を更新しない
  - 苦戦ポイントを会話で消費し、次回のスキル改善へ残さない
- **適用条件**: 初回起動オーバーレイ、Settings からの rerun、persist key、Phase 11 screenshot を含む UI タスク
- **発見日**: 2026-03-13
- **関連タスク**: TASK-UI-09-ONBOARDING-WIZARD

### [Phase12] shallow PASS 表を root evidence へ昇格し、split 親から sibling backlog まで監査する（TASK-IMP-AIWORKFLOW-REQUIREMENTS-LINE-BUDGET-REFORM-001）

- **状況**: `phase12-task-spec-compliance-check.md` が成果物の存在確認だけに寄ると、`implementation-guide.md` の型/API不足や active 未タスクの10見出し欠落を見逃しやすい。さらに `verify-unassigned-links` を親 `task-workflow.md` だけで実行すると、split 後の `task-workflow-backlog.md` に残る未タスクリンクを取りこぼす
- **アプローチ**:
  1. `phase12-task-spec-compliance-check.md` を root evidence とし、Task 12-1〜12-5、`phase-12-documentation.md`、implementation guide 品質、未タスク10見出し、current/baseline 分離、system spec 同期を 1 ファイルへ集約する
  2. implementation guide は `validate-phase12-implementation-guide` を必須で通し、Part 1 の `たとえば`、Part 2 の `type` / `interface`、API/CLI シグネチャ、エッジケース、設定項目を機械確認する
  3. `verify-unassigned-links` は親 `task-workflow.md` 指定時に sibling `task-workflow*.md` も走査する前提で使い、`missing=0` を compliance / detection / task-workflow に同値転記する
  4. active 未タスクは `audit-unassigned-tasks --json --diff-from HEAD --target-file ...` と `--diff-from HEAD` の両方で `currentViolations=0` を確認し、repo 全体 `audit --json` は baseline 参考値として分離記録する
- **結果**: Phase 12 の shallow PASS を防ぎ、split 後の backlog 見落としも同時に回収できる
- **適用条件**: docs-heavy task、line-budget reform、spec-only task、または Phase 12 再監査で shallow summary のまま閉じた形跡がある場合
- **発見日**: 2026-03-13
- **関連タスク**: TASK-IMP-AIWORKFLOW-REQUIREMENTS-LINE-BUDGET-REFORM-001

### [Phase12] 未タスク root canonical path 固定 + 9セクション正規化（TASK-SKILL-LIFECYCLE-04）

- **状況**: Phase 10 MINOR 由来の未タスクを workflow ローカル `tasks/unassigned-task/` に置いたまま進めると、`audit-unassigned-tasks --target-file` の監査境界と衝突し、指定ディレクトリ配置確認が不成立になる
- **アプローチ**:
  1. 未タスク指示書は `docs/30-workflows/unassigned-task/` を正本として作成する
  2. 指示書本文は task-spec テンプレート準拠（`## 1..9` + `3.5 実装課題と解決策`）で作る
  3. `phase-12-documentation.md` / `unassigned-task-detection.md` / `task-workflow-backlog.md` / 関連仕様書の参照を同ターンで root path へ同期する
  4. `verify-unassigned-links` と `audit-unassigned-tasks --json --diff-from HEAD --target-file ...` をセットで実行し、links と品質を別軸で判定する
- **結果**: 「未タスクは検出済みだが指定ディレクトリに未配置」という状態を防ぎ、再監査時の説明責任を保持できる
- **失敗パターン**:
  - workflow ローカル `tasks/unassigned-task/` を temporary として残し、参照更新を後回しにする
  - `current`/`baseline` の監査値だけを見て、物理配置の確認を省略する
  - 未タスク本文を簡易フォーマットで作成し、`3.5` の教訓継承を省略する
- **適用条件**: Phase 12 Task 4 で MINOR 指摘を未タスク化する全 workflow
- **発見日**: 2026-03-14
- **関連タスク**: TASK-SKILL-LIFECYCLE-04

### [Phase12] current canonical set / artifact inventory / legacy register / mirror parity を same-wave で閉じる（TASK-SKILL-LIFECYCLE-04）

- **状況**: 実装内容と苦戦箇所は記録済みでも、`resource-map` / `quick-reference` / `legacy-ordinal-family-register` / mirror 同期が別ターンになると、引用導線と再現手順が stale になる
- **アプローチ**:
  1. `workflow-<feature>.md` を統合正本として新設し、`current canonical set` と `artifact inventory` を固定する
  2. parent docs（契約/状態/UI）と ledger（task-workflow/backlog/lessons）を同一 wave で更新する
  3. old path/filename がある場合は `legacy-ordinal-family-register.md` の `Current Alias Overrides` へ互換行を追加する
  4. 入口導線として `indexes/resource-map.md` / `indexes/quick-reference.md` を同時更新する
  5. 仕上げに `generate-index.js` → `validate-structure.js` → mirror sync → `diff -qr` を実行して parity を確認する
- **結果**: 実装記録、再利用入口、旧名互換、mirror 一致が 1 wave で閉じ、次回の引用再現コストを下げられる
- **適用条件**: docs-heavy task の Phase 12 再監査、または system spec へ「実装内容 + 苦戦箇所 + 再利用手順」を formalize する場合
- **発見日**: 2026-03-14
- **関連タスク**: TASK-SKILL-LIFECYCLE-04

### [Phase12] design タスクでも「実装済み同期」があるなら Step 2 を先送りしない（TASK-SKILL-LIFECYCLE-05）

- **状況**: タスク種別が `design` だと、`documentation-changelog.md` に「system spec 更新は後続実装で対応」と記載しがちだが、実際には同ターンで仕様追補を実施しているケースがある
- **アプローチ**:
  1. `phase-12-documentation.md` / `documentation-changelog.md` / `spec-update-summary.md` を同時に開き、Task 2 Step 2 の判定を同値に揃える
  2. 実際に system spec を更新した場合は、`design` タスクでも Step 2 を「更新あり」に固定する
  3. planned wording（`実行予定` / `後続タスクで実施` / `保留として記録`）を除去し、実績ログのみ残す
  4. 仕上げに `verify-all-specs` / `validate-phase-output` / `validate-phase12-implementation-guide` / `audit-unassigned-tasks --diff-from HEAD` を再実行し、整合を確認する
- **結果**: 「成果物は存在するが changelog が先送り記述」という矛盾を防止できる
- **失敗パターン**:
  - `design` という理由だけで Step 2 を自動的に「更新なし」にする
  - `phase-12-documentation.md` を `completed` にした後で changelog/summmary を更新しない
  - planned wording を残したまま Phase 12 を完了扱いにする
- **適用条件**: docs-heavy / spec-created / design タスクで、Phase 12 中に system spec 追補が発生した場合
- **発見日**: 2026-03-15
- **関連タスク**: TASK-SKILL-LIFECYCLE-05

### [設計] 依存タスク連携における型変換点の明示パターン（TASK-SKILL-LIFECYCLE-08）

- **状況**: 設計タスクシリーズ（Task06→Task07→Task08 など）で、前タスクの出力型が後タスクの判定入力として使われる際、型の変換点が暗黙のまま設計書に残り、後続実装時に依存ドリフトが発生した
- **アプローチ**:
  - 依存タスク連携を以下のフォーマットで Phase 2 設計書に明示する:
    ```
    Task-N 出力型 -> Adapter -> Task-M 入力型 -> Port -> 判定結果
    ```
  - 例: `PublishReadinessMetrics (Task07出力) -> CompatibilityAdapter -> CompatibilityCheckResult (Task08入力) -> PublishReadinessChecker -> PublishReadiness`
  - Adapter が必要な場合は Phase 2 で型変換ロジックの責務を定義し、実装タスクに引き継ぐ
- **成功パターン**:
  - Phase 2 設計書の「依存タスク連携」セクションに変換点テーブルを作成する
  - 変換点ごとに「入力型ソース」「変換ルール」「出力型ターゲット」を3列で定義する
  - 後続の実装タスクに Adapter 実装を未タスクとして引き継ぐ
- **失敗パターン**:
  - 依存タスクの型が「互換性あり」と暗黙想定し、変換点を設計書に記載しない
  - 後続実装タスクの Phase 2 で「Task-N の出力をそのまま使う」と判断し、型変換コストを後回しにする
- **適用条件**: 複数の設計タスクが型契約でシリアル接続されているシリーズ設計
- **発見日**: 2026-03-17
- **関連タスク**: TASK-SKILL-LIFECYCLE-08

### [Phase12] foundation / internal-contract task の no-op Step 2 と blocker 重複防止（TASK-SDK-01）

- **状況**: shared 型や foundation service を実装した task では、system spec 本文に current facts が既に載っていることがある。一方で test runner blocker を見つけると、既存未タスクと重複した follow-up を量産しやすい
- **アプローチ**:
  - 先に system spec 正本を検索し、current facts が存在する場合は Step 2 を no-op 扱いにする。ただし `system-spec-update-summary.md` と `documentation-changelog.md` へ判断根拠を必ず記録する
  - Step 2 が no-op でも、completed ledger / lessons / LOGS / SKILL / mirror sync は同一ターンで閉じる
  - test runner / native binary / worktree blocker は新規未タスク化前に `docs/30-workflows/unassigned-task/` を検索し、既存台帳との重複を確認する
- **成功パターン**:
  - 「domain spec 本文は current」「Step 1 と skill sync は未実施」の2状態を分離して扱う
  - `diff -qr` を含む mirror parity と validator 実行結果を close-out evidence に残す
  - blocker は current workflow の risk/evidence に記録し、既存未タスクがあれば重複作成しない
- **失敗パターン**:
  - Step 2 の本文追記が不要なことを理由に completed ledger / lessons / LOGS / SKILL 更新まで省略する
  - environment blocker を見つけるたびに別 ID の未タスクを増やし、native binary/worktree guard の既存導線を分断する
- **適用条件**: manifest foundation、shared contract、internal adapter、runtime bridge など、domain spec 本文が先行同期されている Phase 12 close-out
- **発見日**: 2026-03-26
- **関連タスク**: TASK-SDK-01

### [Architecture] public bridge と workflow state owner の分離パターン（TASK-SDK-02）

- **状況**: runtime orchestration task では `Facade` に state を残したまま feature を足すと、public IPC / phase state / resume / verify が同じ層に滞留し、後続 task の責務境界が崩れやすい
- **アプローチ**:
  - `Facade` は public bridge、`Engine` は workflow state owner として役割を固定する
  - `terminal_handoff` は early return にし、禁止される副作用（executor 実行など）もテストで固定する
  - `resumeTokenEnvelope` / verify state / artifacts / source provenance は同じ owner に束ねる
- **成功パターン**:
  - `architecture-overview` と service detail で bridge / owner を別行に記載する
  - `RuntimeSkillCreatorFacade.execute()` の handoff 経路に「呼ばれない依存」をテストで明示する
  - `ResourceLoader.getBasePath()` のような runtime provenance source を engine snapshot に昇格する
- **失敗パターン**:
  - public response union が合っていることだけを見て、内部副作用の分離を確認しない
  - `resumeTokenEnvelope` を facade / renderer / downstream task に分散保持する
  - owner 分離後も Phase 12 の system spec / lessons / quick-reference へ current fact を戻さない

### [Phase12] public shape 不変でも internal contract hardening は Step 2 no-op にしない（TASK-SDK-03）

- **状況**: public IPC response は不変でも、runtime helper class、source provenance field、budget/degrade ルールが実装されると system spec の current fact が古くなりやすい
- **アプローチ**:
  - `phase-12-documentation.md` / `documentation-changelog.md` / `system-spec-update-summary.md` を同時に開き、public shape と internal contract を分けて判定する
  - `references/interfaces-agent-sdk-skill-reference.md` / `arch-electron-services-details-part2.md` / `task-workflow-completed.md` / `lessons-learned*.md` / `indexes/quick-reference.md` / `indexes/resource-map.md` を same-wave で更新する
  - `candidateRoots` / `selectedRoots` / `selectedResourceIds` / `droppedResourceIds` / `structureSignature` / `degradeReasons` のような provenance field は lessons と completed ledger の両方へ current fact を戻す
- **成功パターン**:
  - 「public contract は不変」「internal contract は更新あり」の2状態を分離して記録する
  - helper class の追加を domain spec の current fact として反映し、Task 12-2 を no-op にしない
  - new unassigned 0 件でも Step 2 更新と same-wave mirror parity を閉じる
- **失敗パターン**:
  - `spec_created` や docs-heavy に見えることを理由に Step 2 を自動で no-op 扱いする
  - implementation guide だけ current にして、system spec / lessons / quick-reference を古いまま残す
  - provenance field 追加を「内部実装だから不要」と見なして completed ledger へ書かない
- **適用条件**: runtime orchestration、workflow engine、session resume、verify 導入、handoff/integrated 二経路を持つ task
- **発見日**: 2026-03-26
- **関連タスク**: TASK-SDK-02

### [Phase12] docs-heavy follow-up に code hardening が混ざったら source spec / outputs / skill update を同一 wave で戻す（TASK-SDK-01）

- **状況**: Phase 12 close-out 用の docs-heavy workflow に対して、後続のユーザー要求で `packages/` / `apps/` のコード hardening が追加されることがある
- **アプローチ**:
  - 先に current workflow の root 仕様と `outputs/phase-12/*.md` を見直し、docs-only wording を current facts へ書き換える
  - system spec には「新仕様追加」ではなく「existing contract の hardening current facts」として追記し、completed ledger / lessons / skill logs を同一 wave で閉じる
  - carry-forward として残していた follow-up が実装済みになったら、未タスク検出レポートと completed ledger を同じターンで 0 件へ揃える
- **成功パターン**:
  - `system-spec-update-summary.md` に docs sync と runtime sync を別ステップで記録する
  - `manifestContentHash` のような internal hardening も、実装済みなら lesson/pattern に一般化して残す
  - compile gate PASS と env-blocked test を分離記録し、未確認範囲を曖昧にしない
- **失敗パターン**:
  - source workflow は docs-only のまま、変更ファイル一覧だけ code-heavy になる
  - backlog 継続を残したまま completed ledger 側で hardening 実装済みと記録する
  - env blocker を理由に current facts の同期まで後回しにする
- **適用条件**: docs-heavy / spec-heavy の Phase 12 follow-up に、shared type や runtime service の追加 hardening が混ざる場合
- **発見日**: 2026-03-26
- **関連タスク**: TASK-SDK-01, UT-IMP-TASK-SDK-01-PHASE12-COMPLIANCE-SYNC-001

### [Phase12] runtime failure lifecycle bug-fix の same-wave close-out（UT-IMP-RUNTIME-WORKFLOW-ENGINE-FAILURE-LIFECYCLE-001）

- **状況**: runtime bug-fix task では code/test 修正だけ先に閉じがちだが、reject / `success:false` / review required の意味論が変わると completed ledger / lessons / quick-reference / resource-map も同ターンで更新しないと再利用導線が stale になる
- **アプローチ**:
  - failure reason を `execution_error` / `execution_failed` / `verification_review` のように owner 観点で分離し、verify pending へ進めてよい経路を明示する
  - failure artifact は upsert ではなく append、参照は latest accessor へ固定し、history と current snapshot の責務を分ける
  - `awaitingUserInput` には次の owner が分かる reason を必ず保存し、Phase 12 の implementation-guide / compliance check にも同値転記する
  - 環境 workaround でテストを通した場合は `ESBUILD_BINARY_PATH=... pnpm vitest ... --run` のような exact command を verification-report / system-spec-update-summary / lessons に残す
  - canonical `.claude` 更新後は `generate-index.js` → `validate-structure.js` → mirror sync → `diff -qr` を必ず閉じる
- **結果**: failure lifecycle 変更が code だけに閉じず、system spec と skill の再利用導線まで current fact に揃う
- **適用条件**: runtime facade / workflow engine / IPC failure path / review state の bug-fix task
- **失敗パターン**:
  - reject と `success:false` を同じ failure と見なし、verify pending へ誤遷移させる
  - artifact を上書きして repeated failure の履歴を失う
  - PASS した workaround command を残さず、再検証者が同じ環境落ちを踏む
- **発見日**: 2026-03-26
- **関連タスク**: UT-IMP-RUNTIME-WORKFLOW-ENGINE-FAILURE-LIFECYCLE-001

---

### [Architecture] submitUserInput の phase transition semantics を engine owner に集約するパターン（TASK-SDK-04-U1）

- **状況**: `submitUserInput()` が `awaitingUserInput` を消すだけで回答を phase semantics に反映しておらず、`plan_review` / `verification_review` の UI が no-op 状態になっていた
- **アプローチ**:
  - `awaitingUserInput.reason` を meaning source とし、`applyPhaseTransition()` で plan_review / verification_review にルーティングする
  - plan_review: `selectedOptionId` に基づき `ready_to_execute` → execute, `needs_changes` → plan へ遷移
  - verification_review: `approve` → handoff/pass, `improve` → improve, `reject` → plan/review へ遷移
  - shared types `SkillCreatorVerifyResult.nextAction` に `"handoff"` を追加
  - phase 遷移発生時は `phase_transition` artifact（fromPhase, toPhase, reason, selectedOptionId）を記録
  - 未知の reason / selectedOptionId は no-op フォールバック（NFR-3）
- **成功パターン**:
  - engine state の遷移ロジックを 3 つの private メソッドに分離し、switch 文で selectedOptionId を分岐する
  - Phase 4 テスト計画時に request kind（single_select / free_text）と engine 遷移ロジックの整合を確認する
  - shared types の union 拡張が必要な場合は Phase 2 設計成果物に含める
- **失敗パターン**:
  - `awaitingUserInput` を消すだけで submit 完了扱いにし、phase state を更新しない
  - request kind が `free_text` のまま selectedOptionId ベースの遷移を組むと、UI が選択肢を表示できない
  - shared types の型拡張を実装 Phase で初めて追加し、手戻りを発生させる
- **適用条件**: ユーザー入力が workflow state の phase 遷移を引き起こす場合。request/response の形が揃っていても遷移先の意味論を engine owner に持たせる必要がある
- **発見日**: 2026-03-28
- **関連タスク**: TASK-SDK-04-U1

---

## 詳細パターン索引

| ドメイン | 成功パターン | 失敗パターン |
| --- | --- | --- |
| 認証・セッション | → [patterns-success-ipc-auth.md](patterns-success-ipc-auth.md), [patterns-success-ipc-auth-b.md](patterns-success-ipc-auth-b.md) | → [patterns-failure-misc.md](patterns-failure-misc.md) |
| テスト | → [patterns-success-testing-security.md](patterns-success-testing-security.md), [patterns-success-skill-phase12-b.md](patterns-success-skill-phase12-b.md) | → [patterns-failure-misc.md](patterns-failure-misc.md) |
| Phase 12 | → [patterns-success-skill-phase12.md](patterns-success-skill-phase12.md), [patterns-success-phase12-advanced.md](patterns-success-phase12-advanced.md) | → [patterns-failure-phase12.md](patterns-failure-phase12.md) |
| IPC・アーキテクチャ | → [patterns-success-ipc-auth.md](patterns-success-ipc-auth.md), [patterns-success-skill-phase12-b.md](patterns-success-skill-phase12-b.md) | → [patterns-failure-misc.md](patterns-failure-misc.md) |
| DI・設計 | → [patterns-success-testing-security.md](patterns-success-testing-security.md) | - |
| 永続化・復旧 | → [patterns-success-testing-security.md](patterns-success-testing-security.md) | - |
| セキュリティ | → [patterns-success-testing-security.md](patterns-success-testing-security.md), [patterns-success-skill-phase12-b.md](patterns-success-skill-phase12-b.md) | - |
| スキル設計 | → [patterns-success-ipc-auth.md](patterns-success-ipc-auth.md) | - |
| SDK統合 | → [patterns-success-testing-security.md](patterns-success-testing-security.md), [patterns-success-skill-phase12-b.md](patterns-success-skill-phase12-b.md) | → [patterns-failure-misc.md](patterns-failure-misc.md) |
| ビルド・環境 | → [patterns-success-phase12-advanced.md](patterns-success-phase12-advanced.md) | → [patterns-failure-misc.md](patterns-failure-misc.md) |
| 型定義リファクタリング | → [patterns-guideline-type.md](patterns-guideline-type.md) | → [patterns-guideline-type.md](patterns-guideline-type.md) |
| UI/フロントエンド | → [patterns-success-phase12-advanced.md](patterns-success-phase12-advanced.md), [patterns-success-ipc-auth-b.md](patterns-success-ipc-auth-b.md) | → [patterns-failure-misc.md](patterns-failure-misc.md) |

---

## 変更履歴

| 日付 | 変更内容 |
| --- | --- |
| 2026-03-26 | TASK-SDK-02 を反映し、public bridge と workflow state owner の分離パターンを追加 |
| 2026-03-26 | TASK-SDK-01 の close-out を反映し、foundation / internal-contract task 向けの no-op Step 2 判定と blocker 重複未タスク化防止パターンを追加 |
| 2026-03-18 | 500行制限準拠のため10ファイルに分割、ハブファイル化 |
| 2026-03-18 | 500行超えの2ファイルをさらに分割（-b サフィックス追加）、重複ファイル4件削除 |
