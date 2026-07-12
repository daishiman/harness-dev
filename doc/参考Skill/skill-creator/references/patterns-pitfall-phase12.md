# 新規Pitfall候補: Phase12

> 親ファイル: [patterns.md](patterns.md)

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

