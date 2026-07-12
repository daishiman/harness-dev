# 失敗パターン: Skill/Build/SDK/IPC/Testing

> 親ファイル: [patterns.md](patterns.md)

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

### [IPC/SDK] 並行フロー管理での pending Promise 競合（TASK-SDK-SC-03）

- **状況**: SDK Session 内で「ユーザーへの質問待機」と「外部API設定要求待機」の2つの非同期フローが存在し、同時に pending 状態になりうる
- **問題**: 両方の resolve コールバックが同時に存在すると、一方の応答が他方の Promise を解決してしまい、型不整合やデータ混在が発生する
- **原因**:
  - `pendingQuestionResolve` と `pendingExternalApiResolve` が独立したフィールドとして管理されており、相互排他の保証がなかった
  - IPC イベントの到着順序が非決定的で、テスト時は成功するがランタイムで競合する
- **教訓**:
  - 複数の pending Promise を持つクラスでは、相互排他を明示的に保証する（一方がアクティブなら他方を null 化）
  - abort / cleanup 時に全 pending を一括で reject / null 化する
  - テストでは「両方が同時にアクティブになるケース」を必ず検証する
- **対策**: `pendingQuestionResolve` セット時に `pendingExternalApiResolve` が null であることを assert し、逆も同様にする
- **発見日**: 2026-04-03
- **関連タスク**: TASK-SDK-SC-03

### [IPC/SDK] 秘匿化境界の曖昧さ（TASK-SDK-SC-03）

- **状況**: 外部API設定に含まれる認証情報（API キー、Bearer トークン）をSDKプロンプトに注入する際、sanitize 処理の適用箇所が不明確になった
- **問題**: HTTP呼び出し時に必要な生の credential と、SDKに渡す sanitize 済み設定の使い分けが曖昧で、一方を修正すると他方で認証エラーになる
- **原因**:
  - `ExternalApiConnectionConfig` という単一の型をHTTP呼び出しとSDKコンテキストの両方で使用しており、どちらの文脈の値かが型レベルで区別できなかった
- **教訓**:
  - 秘匿化は「SDKに渡す直前の1箇所」に集約する（`sanitizeExternalApiConfigForPrompt()`）
  - HTTP Adapter は生の設定を受け取り、SDKには sanitize 済みの設定のみを渡す
  - 同じ型でも「生」と「sanitize済み」は変数名で明示的に区別する
- **発見日**: 2026-04-03
- **関連タスク**: TASK-SDK-SC-03

---

