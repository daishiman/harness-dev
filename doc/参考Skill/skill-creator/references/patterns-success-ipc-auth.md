# 成功パターン: IPC/Auth/Phase12基盤

> 親ファイル: [patterns.md](patterns.md)

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

> 続き: [patterns-success-ipc-auth-b.md](patterns-success-ipc-auth-b.md)
