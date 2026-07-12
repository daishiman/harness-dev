# 成功パターン: Phase12上級・UI・ビルド

> 親ファイル: [patterns.md](patterns.md)

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

### [Phase12] P59 対策 — 並列 SubAgent 成果物統合検証（TASK-IMP-CHATPANEL-REAL-AI-CHAT-001）

- **状況**: Phase 12 を複数の SubAgent で分担した結果、documentation-changelog の未タスク件数と unassigned-task-detection の検出件数が乖離する
- **問題**: changelog 作成 SubAgent が他 SubAgent の成果物件数を確認せずに「完了」と記録し、件数不整合が Phase 12 終了後まで発見されない
- **解決策**:
  - documentation-changelog は全 SubAgent 完了後にメインエージェントが統合作成する
  - SubAgent に changelog 作成を委譲する場合は、完了後にメインエージェントが `unassigned-task-detection.md` の件数と照合する
  - 件数が不一致の場合は changelog を修正してから Phase 12 完了とする
- **照合コマンド**:
  ```bash
  # unassigned-task-detection の検出件数を取得
  grep -c "^| UT-" outputs/phase-12/unassigned-task-detection.md

  # documentation-changelog の Task 4 記載件数を確認
  grep "検出件数" outputs/phase-12/documentation-changelog.md
  ```
- **適用条件**: Phase 12 で複数 SubAgent を並列運用する場合
- **教訓**: 並列エージェント間の情報断絶により、changelog 件数と detection 件数が乖離する。メインエージェントが最終照合する責務を持つ
- **発見日**: 2026-03-18
- **関連パターン**: P59（並列エージェントによる documentation-changelog 件数不整合）、P43（サブエージェント rate limit 中断）
- **関連タスク**: TASK-IMP-CHATPANEL-REAL-AI-CHAT-001

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

### [Phase12] 実績ベース更新 + screenshot 昇格 + 苦戦カード再利用（UT-TASK06-007）

- **状況**: Phase 12 の再監査や docs-heavy/backend-heavy の更新で、完了記録が `実施予定` や `N/A` に寄り、画面検証の要求があっても `NON_VISUAL` のまま閉じやすい
- **アプローチ**:
  1. `verify` / `validate` / `diff` / `audit` / `validate-phase11-screenshot-coverage` の当日実測値のみを `spec-update-summary.md` / `documentation-changelog.md` / `task-workflow.md` に転記する
  2. ユーザーが画面検証を要求したら、docs-heavy/backend-heavy でも `SCREENSHOT + NON_VISUAL` に昇格し、代表スクリーンショットを current workflow へ集約する
  3. 苦戦箇所は `症状 / 再発条件 / 解決策 / 標準ルール` の4点で書き、`task-workflow.md` と `lessons-learned.md` と該当テンプレートへ同値転記する
- **結果**: 実績値と証跡の不足を同時に防ぎ、次回の同種課題を短い再利用カードで解決できる
- **適用条件**: Phase 12 再監査、docs-heavy/backend-heavy の仕様同期、ユーザーからの明示的な画面検証要求
- **発見日**: 2026-03-19
- **関連タスク**: UT-TASK06-007

### [Phase12] dark-mode visual baseline drift の theme lock / evidence lock / same-wave sync（UT-UIUX-VISUAL-BASELINE-DRIFT-001）

- **状況**: Playwright の browser default と spec-level default がズレると、`dark-mode` baseline drift が UI 差分ではなく実行環境差分として再発する
- **アプローチ**:
  1. `ui-ux-layer2` の Playwright project に `use.colorScheme: "dark"` を固定する
  2. `apps/desktop/e2e/ui-ux/layer2-visual.spec.ts` に `test.use({ colorScheme: "dark" })` を固定し、spec-level default も同値にする
  3. Phase 11 screenshot evidence を `TC-ID` ベースで保存し、`manual-test-result.md` と 1:1 対応させる
  4. `workflow-ui-ux-visual-baseline-drift.md` / `task-workflow-completed-ui-ux-visual-baseline-drift.md` / `lessons-learned-ui-ux-visual-baseline-drift.md` を同一 wave で同期する
  5. `resource-map.md` / `quick-reference.md` / `LOGS.md` へ lookup 導線を戻す
- **結果**: `ui-ux-layer2` は `10 passed`、`typecheck` は PASS、`eslint` は `0 errors / 6 warnings` で、current と baseline を分離したまま完了できた
- **適用条件**: dark-mode screenshot / visual regression / baseline drift の再撮影が必要な Phase 12 タスク
- **教訓**: browser theme は config だけでは足りず、spec-level evidence と docs/spec sync まで同一 wave で閉じる必要がある
- **発見日**: 2026-04-03
- **関連タスク**: UT-UIUX-VISUAL-BASELINE-DRIFT-001
