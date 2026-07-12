# 成功パターン: Skill/Phase12同期

> 親ファイル: [patterns.md](patterns.md)

### [Phase12] docs-only runbook task の feedback promotion パターン（09b）

- **状況**: cron / release / incident response の docs-only runbook task で、runtime 操作を実行せずに Phase 12 を閉じる
- **アプローチ**:
  - runtime 操作は PASS と扱わず、current facts / expected command / link checklist を代替 evidence にする
  - 大きい deployment 親ファイルへ詳細を足さず、artifact inventory と lessons child に苦戦箇所を分離する
  - unassigned candidate は既存 task を先に検索し、formalized / delegated / existing related / candidate に分類する
- **結果**: `09b` の cron current facts、release runbook、incident response、skill feedback が同一 wave で追跡可能になった
- **適用条件**: docs-only / `spec_created` / `NON_VISUAL` の運用 runbook close-out
- **発見日**: 2026-05-01
- **関連タスク**: 09b-parallel-cron-triggers-monitoring-and-release-runbook

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


> 続き: [patterns-success-skill-phase12-b.md](patterns-success-skill-phase12-b.md)
