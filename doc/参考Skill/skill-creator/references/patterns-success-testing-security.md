# 成功パターン: Testing/Security/IPC契約

> 親ファイル: [patterns.md](patterns.md)

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

