# 成功パターン: IPC/Testing/SDK/Security

> 親ファイル: [patterns.md](patterns.md)
> 続き: [patterns-success-skill-phase12.md](patterns-success-skill-phase12.md) の後半

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
