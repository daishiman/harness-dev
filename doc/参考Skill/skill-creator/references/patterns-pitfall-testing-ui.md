# 新規Pitfall候補: Testing/UI/状態管理

> 親ファイル: [patterns.md](patterns.md)

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

### [UI] 会話型インタビューUIの非同期状態管理パターン（TASK-P0-06）

- **状況**: ConversationalInterview コンポーネントで、APIキー存在確認の非同期性、Plan切り替え時の状態リセット、undo時のsecret値復元、multi_select型の互換性維持が同時に求められ、useEffect依存関係とセキュリティ要件の両立が困難だった
- **アプローチ**:
  1. **cancelledフラグによる競合状態対策**: `window.electronAPI?.authKey?.exists()` の非同期呼び出しで、useEffect cleanup時に `cancelled = true` を設定し、stale結果の反映を防止する
  2. **activePlanIdRefによるPlan切り替えリセット**: `useRef` で前回の `planId` を保持し、変更検知時に `interview.reset()` / `resetInputValues()` / `setResolvedApiKeyStatus("unknown")` を実行。useEffect依存配列の循環参照を回避する
  3. **undo時のsecret値セキュリティ（NFR-07準拠）**: `kind === "secret"` の回答をundo復元する際、元の値ではなく空文字で復元する。セキュリティ上、secret値はメモリ内に不必要に保持しない
  4. **multi_select型の相互フォールバック**: `selectedOptionIds ?? answer.selectedValues` と `selectedValues ?? answer.selectedOptionIds` の双方向フォールバックで、RT-05 canonical化との並行実装期間の互換性を維持する
  5. **Preload API型定義は shared パッケージから import**: `ExternalApiConnectionConfig` 等の型は `packages/shared` に配置し、Preload独自型は最小限に抑える
- **テスト戦略**:
  - APIキー存在確認のモック: `window.electronAPI.authKey.exists` を vi.fn() で差し替え
  - undo→rerender複合テスト: `restoredPendingRequest?.requestId !== pendingRequest.requestId` チェックの検証
  - multi_selectチェックボックス複数選択: `fireEvent.click` でトグル操作を再現
- **参照実装ファイル**:
  - `apps/desktop/src/renderer/components/skill/ConversationalInterview.tsx`
  - `apps/desktop/src/renderer/components/skill/hooks/useInterviewState.ts`
  - `apps/desktop/src/preload/skill-creator-session-api.ts`
- **適用条件**: 非同期状態取得を伴うUI、Plan/セッション切り替え、undo付きフォーム、複数型バージョンの互換性維持が必要なコンポーネント
- **発見日**: 2026-04-05
- **関連タスク**: TASK-P0-06

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

### [Testing/E2E] e2e mock の二重実装は state drift を生む（task-15 admin dashboard）

- **状況**: Playwright fixture 内 `page.route()` で組んだ mock と、SSR fetch 用 standalone mock server の両方を保持すると、片方の状態だけ更新されて assertion が一貫しない drift が発生する。Next.js Server Component の `fetch()` は `page.route()` を捕捉しないため、UI 経由で state を変えても server-side fetch は古い fixture-internal mock を踏まないが、別 spec が standalone 側を更新すると同じ画面でも結果が割れる
- **アプローチ**:
  1. Single source of truth は **standalone HTTP mock server**（`apps/web/playwright/fixtures/standalone-mock-server.ts` 等）に固定する
  2. Playwright test から状態を切り替えたい場合は HTTP control endpoint（例: `POST /__mock/state`）を一本生やし、test はそれだけを叩く。`page.route()` は使わない
  3. fixture-internal mock を残す合理的理由（page-object 単体検証など）がある場合は、必ず standalone mock と **同じ JSON fixture file** を読み込み、update 経路を control endpoint 経由に強制する
  4. CI gate として `grep -rn 'page.route(' apps/*/playwright/tests/` の hit 件数を Phase 11 evidence に残し、新規追加時はレビュー必須にする
- **結果**: SSR fetch / CSR fetch / test assertion の 3 経路が同じ state を見るため、screenshot と spec assertion の drift が消える
- **適用条件**: Next.js App Router / Server Component を含む E2E、Playwright + standalone mock の組み合わせ、admin dashboard のように UI から state 変更を行うフロー
- **発見日**: 2026-05-10
- **関連タスク**: task-15 admin dashboard and members

### [Testing/E2E] page-object と実装 testid の drift 防止（task-15 admin dashboard）

- **状況**: page-object に新しい locator を追加しても、実装側 `data-testid` が同 cycle で配備されていないと spec が `Locator timeout` で fail する。逆に実装側 testid を rename しても page-object が追従せず壊れる drift も起きる
- **アプローチ**:
  1. page-object 追加 / 変更時は `grep -rn 'data-testid="<id>"' apps/web/src` を必ず実行し、実装側存在を確認する。Phase 11 evidence (`testid-cross-check.txt`) に grep 結果を残す
  2. `data-testid` 命名は **機能 prefix + kebab-case** に統一する（例: `admin-kpi-card-total` / `admin-members-row-action-edit`）。snake_case / camelCase / 接尾辞バラつきを禁止する
  3. page-object と実装の同 commit 配備を Phase 5 ランブックで強制する。「実装は別タスク」分離は禁止
  4. CI gate として page-object の locator 文字列と実装 `data-testid` を cross-grep する script (`scripts/verify-testid-parity.mjs`) を整備し、`dev` PR で required check 化する
- **結果**: locator timeout / silent skip 系 fail が消え、page-object refactor も実装側更新と同期する
- **適用条件**: page-object pattern を採用する Playwright E2E、admin dashboard / KPI / table 等 testid を多用する UI
- **発見日**: 2026-05-10
- **関連タスク**: task-15 admin dashboard and members
