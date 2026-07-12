# 失敗パターン: Phase12

> 親ファイル: [patterns.md](patterns.md)

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

