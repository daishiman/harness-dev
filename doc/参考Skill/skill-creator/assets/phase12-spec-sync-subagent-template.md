# Phase 12 仕様書別SubAgent同期テンプレート

> **cross-cutting follow-up の追加テンプレート**: `references/workflow-<feature>.md` を新規作成する場合は `skill-creator/assets/phase12-integrated-workflow-spec-template.md` を併用し、実装内容 / 苦戦箇所 / 5分解決カード / root evidence を 1 ファイルへ集約する。

## 1. 対象タスク

| 項目 | 記入内容 |
| --- | --- |
| タスクID | `<TASK-ID>` |
| 実装対象 | `<実装ファイル/機能>` |
| 監査対象workflow | `<workflow-a>`（必須） / `<workflow-b>`（必要時） |
| 反映対象仕様書 | `interfaces / api-ipc / security / task-workflow / lessons / (+ domain-ui-spec if needed)` |
| 実行日 | `<YYYY-MM-DD>` |

> `workflow-<feature>.md` を追加した場合は、`indexes/resource-map.md` / `indexes/quick-reference.md` / 対象 skill の `SKILL.md` まで同一ターンで直リンクを戻す。

## 2. SubAgent分担（仕様書単位）

| SubAgent | 担当仕様書 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-A | `references/interfaces-*.md` | 型定義・Preload API契約同期 | 実装型と仕様型の差分ゼロ |
| SubAgent-B | `references/api-ipc-*.md` | IPCチャネル契約（request/response/validation）同期 | チャネル表・実装状況表が実装一致 |
| SubAgent-C | `references/security-*.md` | sender/P42/許可値/エラー境界の同期 | セキュリティ要件の欠落ゼロ |
| SubAgent-D | `references/task-workflow.md` | 完了記録・成果物・検証証跡・苦戦箇所同期 | 実装内容 + 証跡 + 苦戦箇所が同一ターンで記録済み |
| SubAgent-E | `references/lessons-learned.md` | 苦戦箇所の再利用可能化 | 再発条件付きで簡潔解決手順が記録済み |

### 2.0.1 スキル更新 close-out プロファイル

スキル自体を更新する Phase 12 close-out では、read-only 監査を並列化し、編集は skill owner ごとに直列統合する。

| Lane | 担当範囲 | 完了条件 |
| --- | --- | --- |
| Skill-Audit | `.claude/skills/<skill>/SKILL.md` / references / assets | skill feedback を主担当 skill / 補助 skill / 正本仕様導線に分類し、反映先と見送り理由が明示済み |
| Mirror-Audit | `.claude/skills/<skill>` / `.agents/skills/<skill>` | canonical と mirror の `diff -qr` が差分なし、または symlink 等の N/A 理由が compliance check に記録済み |
| Phase12-Audit | workflow `outputs/phase-12/*` / artifacts | canonical 7 ファイル、artifacts parity、planned wording、runtime pending 境界が実測値で確認済み |
| Legacy-Audit | `legacy-ordinal-family-register.md` / artifact inventory / task-workflow / resource-map | 旧 filename / 旧 root citation が current semantic filename へ引ける、または archived/stale-current 分類が同期済み |

主担当 skill にルールを厚く書き、補助 skill にはテンプレートと導線だけを置く。苦戦箇所は `症状 / 根本原因 / 5分解決手順 / 検証ゲート / 同期先` の5項目で記録し、cleanup / restore / fix 系の未タスクでも通常の未タスク必須セクションを省略しない。`quick_validate`、Phase 12 validator、mirror `diff -qr` の実測値を compliance check に集約する。
### 2.1 UI機能実装プロファイル（TASK-UI-05型）

| SubAgent | 担当仕様書 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-A | `references/ui-ux-components.md` | 主要UI一覧・完了タスク・導線同期 + 実装内容と苦戦箇所サマリー追加 | UI正本へ反映済み |
| SubAgent-B | `references/ui-ux-feature-components.md` | 機能仕様・未タスク・苦戦箇所同期 | 機能仕様と再利用手順が記録済み |
| SubAgent-C | `references/arch-ui-components.md` | 構造責務境界の同期 | レイヤー境界が整合 |
| SubAgent-D | `references/arch-state-management.md` | 状態管理責務の同期 | 状態境界が整合 |
| SubAgent-E | `references/task-workflow.md` | 完了台帳・検証証跡・残課題同期 | 実装 + 証跡 + 未タスクが同一ターン記録済み |
| SubAgent-F | `references/lessons-learned.md` | 再発条件付き教訓の同期 | 苦戦箇所と簡潔手順が再利用可能 |

#### 2.1.1 UIドメイン追加仕様（必要時）

| SubAgent | 担当仕様書 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-G+ | `references/<ui-domain-spec>.md` / `references/ui-ux-search-panel.md` / `references/ui-ux-design-system.md` / `references/error-handling.md` / `references/architecture-implementation-patterns.md` | ドメイン固有 UI 正本または preview/search cross-cutting 正本の同期 | 実装内容 + 苦戦箇所 + 再利用手順が追記済み |

#### 2.1.2 Light Mode 全画面是正プロファイル（theme / contrast）

| SubAgent | 担当仕様書 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-L1 | `references/ui-ux-design-system.md` | white/black baseline、token 契約、compatibility bridge 方針を同期 | light mode 標準と token 名が実装一致 |
| SubAgent-L2 | `references/ui-ux-components.md` / `references/ui-ux-feature-components.md` | renderer-wide drift の対象画面、primitive migration、視覚証跡を同期 | 全画面共通の drift と代表 screenshot が記録済み |
| SubAgent-L3 | `references/task-workflow.md` | shard 再現、screenshot 再取得、継続 backlog を同期 | 実装内容 + 検証証跡 + 未タスクが同一ターン記録済み |
| SubAgent-L4 | `references/lessons-learned.md` | token修正 / bridge / component migration の責務分離と 5分解決カードを同期 | 再発条件付きの短手順が記録済み |

#### 2.1.3 Light theme shared color migration プロファイル（`spec_created` / component migration）

| SubAgent | 担当仕様書 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-M1 | `references/ui-ux-design-system.md` / `references/ui-ux-settings.md` | actual target inventory、token/component 境界、verification-only lane を同期 | current workflow と inventory correction が一致 |
| SubAgent-M2 | `references/ui-ux-feature-components.md` / `references/ui-ux-search-panel.md` / `references/ui-ux-portal-patterns.md` / `references/rag-desktop-state.md` | Auth / WorkspaceSearch / dialog / panel state の cross-cutting 条件を同期 | search/portal/state contract が仕様へ反映済み |
| SubAgent-M3 | `references/api-ipc-auth.md` / `references/api-ipc-system.md` / `references/architecture-auth-security.md` / `references/security-electron-ipc.md` / `references/security-principles.md` | auth/api/security boundary を同期 | public auth shell と settings/search の安全境界が記録済み |
| SubAgent-M4 | `references/task-workflow.md` | `spec_created` 台帳、Phase 1-3 gate、検証証跡を同期 | Phase 1-3 completed / Phase 4+ planned / status=`spec_created` が一致 |
| SubAgent-M5 | `references/lessons-learned.md` | inventory drift、scope 分離、cross-cutting spec 抽出漏れ、Phase gate を教訓化 | 5分解決カードが再利用可能形式で記録済み |

#### 2.1.4 docs-only parent workflow sweep プロファイル

| SubAgent | 担当仕様書 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-P1 | `task-060` 相当の parent pointer doc / completed-task pointer docs / `task-000` / `task-090` | parent-child root、legacy status、pointer inventory の正規化 | 親導線が completed 正本を指し、legacy status が一致 |
| SubAgent-P2 | `references/task-workflow.md` / `references/ui-ux-feature-components.md` / `references/interfaces-*.md` | completed root、representative evidence path、5分解決カードを同期 | task / feature / interface の root drift がゼロ |
| SubAgent-P3 | `references/workflow-<feature>.md` / `references/lessons-learned.md` | docs-only parent workflow の統合正本、苦戦箇所、標準ルールを同期 | 実装内容 + 苦戦箇所 + 再利用手順が記録済み |
| SubAgent-P4 | `scripts/validate-<parent-sweep>.mjs` / `diff -qr .claude/skills/<skill> .agents/skills/<skill>` | path / status / mirror drift guard を検証 | `path=0 / status=0 / mirror=0` かつ mirror 差分なし |
| SubAgent-P5 | `outputs/phase-11/*` / `outputs/phase-12/system-spec-update-summary.md` / `skill-creator` templates | representative visual re-audit board、SubAgent 実行ログ、再利用テンプレート化 | evidence board と template update が同一ターン記録済み |

### 2.2 再確認（2workflow同時監査）プロファイル

| SubAgent | 担当範囲 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-A | `<workflow-a>` | `verify-all-specs` + `validate-phase-output` + Task 1/3/4/5 実体突合 | workflow-a の検証が全て PASS |
| SubAgent-B | `<workflow-b>` | `verify-all-specs` + `validate-phase-output` + Task 1/3/4/5 実体突合 | workflow-b の検証が全て PASS（不要時はN/A理由記録） |
| SubAgent-C | `docs/30-workflows/unassigned-task/` / `docs/30-workflows/completed-tasks/<workflow>/unassigned-task/` / `docs/30-workflows/completed-tasks/` / `docs/30-workflows/completed-tasks/unassigned-task/` | `verify-unassigned-links` + `audit --diff-from HEAD` + 10見出し確認 + 配置先判定 | `missing=0` かつ `currentViolations=0`。active workflow 由来の未実施は1つ目、completed workflow 由来の継続 backlog は2つ目、完了済み standalone UT は3つ目、4つ目は legacy。`target-file` 監査は実際の正本 unassigned dir に合わせる |
| SubAgent-D | `references/task-workflow.md` | 2workflow証跡、苦戦箇所、簡潔解決手順の同期 | 監査結果が再利用可能形式で記録済み |
| SubAgent-E | `references/lessons-learned.md` | 再発条件付き教訓と標準ルールの同期 | 教訓が task-workflow と整合 |

### 2.3 Step 2 判定同期プロファイル（仕様更新タスク必須）

| SubAgent | 担当範囲 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-S2-A | `phase-12-documentation.md` | Step 2 更新対象（`arch/api/interfaces/security`）の要否判定を確定 | 更新対象に応じて Step 2 を `完了` / `該当なし` で説明可能 |
| SubAgent-S2-B | `outputs/phase-12/documentation-changelog.md` | Step 判定（1-A〜2）と理由を同期 | Step 2 判定が実装実体と一致 |
| SubAgent-S2-C | `outputs/phase-12/system-spec-update-summary.md` | Step 2 更新仕様書の一覧化と反映内容同期 | changelog の Step 2 判定と更新対象一覧が一致 |

### 2.4 仕様書別SubAgent実行ログ（必須）

| SubAgent | 担当仕様書 | 実装内容の反映先 | 苦戦箇所の反映先 | 検証証跡 |
| --- | --- | --- | --- | --- |
| SubAgent-A | `<spec-a>` | `<実装内容を反映した見出し>` | `<苦戦箇所を反映した見出し>` | `<verify/validate/links/audit/UI証跡>` |
| SubAgent-B | `<spec-b>` | `<実装内容を反映した見出し>` | `<苦戦箇所を反映した見出し>` | `<verify/validate/links/audit/UI証跡>` |
| SubAgent-C | `<spec-c>` | `<実装内容を反映した見出し>` | `<苦戦箇所を反映した見出し>` | `<verify/validate/links/audit/UI証跡>` |

> 全SubAgentで「実装内容」「苦戦箇所」の両方を埋めること。空欄は未完了扱い。

### 2.5 APIキー連動 + チャット経路整合プロファイル（TASK-FIX-APIKEY-CHAT-TOOL-INTEGRATION-001型）

| SubAgent | 担当仕様書 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-A | `references/interfaces-auth.md` | `AuthKeyExistsResponse.source` 契約同期 | saved/env-fallback/not-set の型・説明が一致 |
| SubAgent-B | `references/llm-ipc-types.md` | `AIChatRequest` と `LLMSetSelectedConfigRequest` 同期 | provider/model 契約が実装一致 |
| SubAgent-C | `references/api-ipc-system.md` / `references/api-endpoints.md` | `AI_CHAT` 解決順、`llm:set-selected-config`、cache clear 反映 | channel 表と実装状況が一致 |
| SubAgent-D | `references/security-electron-ipc.md` / `references/ui-ux-settings.md` | 非機密判定契約と表示契約を同期 | キー実値非公開 + `source` 優先表示が一致 |
| SubAgent-E | `references/task-workflow.md` | 完了台帳、検証証跡、苦戦箇所同期 | 実装内容 + 苦戦箇所 + 検証値が同時記録 |
| SubAgent-F | `references/lessons-learned.md` | 再発条件付き教訓と短手順同期 | 3苦戦箇所と解決カードが再利用可能 |

> このプロファイルでは `interfaces / llm / api-ipc / security / ui-ux-settings / task-workflow / lessons` を同一ターンで更新する。

### 2.6 実績ベース更新・画面昇格・苦戦再利用プロファイル

| SubAgent | 担当範囲 | 主担当作業 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-SR1 | `outputs/phase-12/system-spec-update-summary.md` / `outputs/phase-12/documentation-changelog.md` | `verify` / `validate` / `diff` / `audit` の実測値を同期し、planned wording を除去する | 完了文言が実測値のみで説明可能 |
| SubAgent-SR2 | `outputs/phase-11/*` / `outputs/phase-12/*` | user が画面検証を要求したら docs-heavy / backend-heavy でも screenshot へ昇格し、代表証跡を残す | `SCREENSHOT + NON_VISUAL` で current workflow に閉じる |
| SubAgent-SR3 | `references/task-workflow.md` / `references/lessons-learned.md` | 苦戦箇所を `症状 / 再発条件 / 解決策 / 標準ルール` へ分解して再利用カード化する | 次回の短時間解決に流用可能 |

> 完了条件は「実装したか」ではなく「実測証跡が同期されたか」で判定する。

## 3. 各仕様書の必須記載

| 仕様書 | 必須記載 |
| --- | --- |
| interfaces | 実装内容、契約差分、後方互換方針、型公開面（package index） |
| api-ipc | チャネル一覧、引数/戻り値、実装状況、Preload対応メソッド |
| security | 検証要件、責務分離、許可値リスト、サニタイズ方針 |
| task-workflow | 完了記録、成果物、苦戦箇所、検証証跡、未タスク監査結果 |
| lessons-learned | 苦戦箇所、再発条件、原因、解決策、簡潔手順 |

UI機能実装時の必須記載（追加）:
- `ui-ux-components`: 完了タスク、関連未タスク、実装導線
- `ui-ux-feature-components`: 機能仕様、苦戦箇所、簡潔解決手順
- `arch-ui-components` / `arch-state-management`: UI構造・状態責務境界
- `ui-ux-design-system`: token / contrast / theme 起因の改善余地と未タスク導線
- `ui-ux-search-panel`: shortcut / focus trap / ranking / no-match 契約
- `error-handling`: timeout / read failure / parse failure / renderer crash / no-match の UI 応答
- `architecture-implementation-patterns`: renderer local timeout+retry / fuzzy 判定分離 / structured fallback
- `ui-ux-navigation` などのドメイン固有 UI 正本: その機能に固有な契約・苦戦箇所・再利用手順

### 3.1 UI current workflow 反映先マトリクス

| 関心ごと | 最適な担当仕様書 | SubAgent |
| --- | --- | --- |
| コンポーネント一覧、完了タスク、実装内容と苦戦箇所サマリー | `ui-ux-components.md` | A |
| 機能の振る舞い、関連未タスク、5分解決カード | `ui-ux-feature-components.md` | B |
| 専用型、adapter、harness、責務境界 | `arch-ui-components.md` | C |
| selector / reset / store 契約 | `arch-state-management.md` | D |
| token / theme / contrast 所見 | `ui-ux-design-system.md` | G+ |
| shortcut / focus trap / ranking / no-match | `ui-ux-search-panel.md` | G+ |
| renderer timeout / retry / parse fallback | `architecture-implementation-patterns.md` | G+ |
| retryable / fatal / recoverable error surface | `error-handling.md` | G+ |
| 検証値、残課題、完了記録 | `task-workflow.md` | E |
| 苦戦箇所、再発条件、標準手順 | `lessons-learned.md` | F |

### 3.2 docs-only parent workflow 反映先マトリクス

| 関心ごと | 最適な担当仕様書 | SubAgent |
| --- | --- | --- |
| parent pointer / completed-task pointer docs / legacy index | parent workflow doc / `task-workflow.md` | P1 |
| representative visual review と Workspace lineage surface | `ui-ux-feature-components.md` | P2 |
| completed root / evidence path | `interfaces-*.md` | P2 |
| 統合正本、苦戦箇所、5分解決カード | `workflow-<feature>.md` / `lessons-learned.md` | P3 |
| path / status / mirror drift guard | validator script / `diff -qr` | P4 |
| evidence board / SubAgent実行ログ / テンプレート改善 | `outputs/phase-12/system-spec-update-summary.md` / `skill-creator` templates | P5 |

### 3.1 同種課題の5分解決カード同期ルール

- `task-workflow.md` / `lessons-learned.md` / `<domain-spec or ui-ux-feature-components.md>` の3仕様書に同一カードを記録する
- カードは「症状1行」「根本原因1行」「最短5ステップ」「検証ゲート」「同期先3点」を必須項目とする
- 5ステップは `実体固定→仕様是正→画面証跡→未タスク監査→台帳同期` の順序を固定し、並び替えを禁止する

## 4. IPC追加時の契約突合（必須）

| 観点 | 確認方法 | 完了条件 |
| --- | --- | --- |
| handler 実装 | `rg -n "skill:.*" apps/desktop/src/main/ipc` | 追加チャネルのハンドラが存在 |
| register 配線 | `rg -n "register.*Handlers" apps/desktop/src/main/ipc/index.ts` | 新規ハンドラが `registerAllIpcHandlers` に登録済み |
| preload 公開 | `rg -n "safeInvoke|safeInvokeUnwrap" apps/desktop/src/preload/skill-api.ts` | 全チャネルに対応する API が公開済み |
| service 公開境界 | `rg -n "services/<domain>/|export .* from \"./\"|SkillChain(Store|Executor)" apps/desktop/src/main` | 依存サービスのバレル公開（または未タスク移管）が記録されている |
| 回帰テスト運用 | `pnpm --filter @repo/desktop test:run`（失敗時は `vitest run <target>` 分割） | `SIGTERM` 時も分割実行で対象回帰の合否が確定できる |
| 仕様同期 | interfaces/api-ipc/security の3仕様書を同時更新 | 実装名・契約・検証要件のドリフトゼロ |

## 5. 検証コマンド

```bash
rg --files .claude/skills | rg 'verify-all-specs|validate-phase-output|verify-unassigned-links|audit-unassigned-tasks'
rg -n "register.*Handlers|skill:analytics|safeInvokeUnwrap" apps/desktop/src/main/ipc apps/desktop/src/preload/skill-api.ts
rg -n "services/skill/SkillChain(Store|Executor)|export .*SkillChain(Store|Executor)" apps/desktop/src/main
node .claude/skills/task-specification-creator/scripts/verify-all-specs.js --workflow <workflow-dir> --json
node .claude/skills/task-specification-creator/scripts/validate-phase-output.js <workflow-dir>
node .claude/skills/task-specification-creator/scripts/verify-all-specs.js --workflow <workflow-a> --json
node .claude/skills/task-specification-creator/scripts/verify-all-specs.js --workflow <workflow-b> --json
node .claude/skills/task-specification-creator/scripts/validate-phase-output.js <workflow-a>
node .claude/skills/task-specification-creator/scripts/validate-phase-output.js <workflow-b>
rg -n '^\\| ステータス \\| completed' <workflow-path>/phase-12-documentation.md
rg -n '^- \\[x\\] Task 12-[1-5]' <workflow-path>/phase-12-documentation.md
rg -n '## Part 1|## Part 2|なぜ|必要|例え|たとえば|interface|type|API|エッジケース|設定' <workflow-path>/outputs/phase-12/implementation-guide.md
diff -u <workflow-path>/artifacts.json <workflow-path>/outputs/artifacts.json
node .claude/skills/task-specification-creator/scripts/generate-index.js --workflow <workflow-path> --regenerate
rg -n 'undefined' <workflow-path>/index.md
rg -n '^\\| 12 \\| .* \\| .*完了' <workflow-path>/index.md
rg -n 'ステータス\\s*\\|\\s*pending' <workflow-path>/phase-{1,2,3,4,5,6,7,8,9,10,11}-*.md
rg -n "契約テスト|回帰テスト|TC-C|MR-" <workflow-path>/phase-4-test-creation.md <workflow-path>/phase-6-test-expansion.md
rg -n '^\\| 2\\s+\\|' <workflow-path>/outputs/phase-12/documentation-changelog.md
rg -n "text-white|bg-white/|border-white/|text-gray-|bg-gray-|border-gray-" apps/desktop/src/renderer
node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD --unassigned-dir <unassigned-dir> --target-file <unassigned-file>
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --completed-unassigned-dir docs/30-workflows/completed-tasks/<workflow>/unassigned-task --target-file docs/30-workflows/completed-tasks/<workflow>/unassigned-task/<task>.md
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --target-file docs/30-workflows/completed-tasks/<task>.md
node scripts/validate-<parent-sweep>.mjs --json
diff -qr .claude/skills/<canonical-skill> .agents/skills/<mirror-skill>
rg -n "<UT-ID>|<task-id>" docs/30-workflows/unassigned-task docs/30-workflows/completed-tasks docs/30-workflows/completed-tasks/unassigned-task
node apps/desktop/scripts/capture-<docs-heavy-review-board>.mjs
pnpm --filter @repo/desktop preview
python3 -m http.server 4173 --directory apps/desktop/out/renderer
curl -I http://127.0.0.1:4173
pnpm --filter @repo/desktop test:run
pnpm --filter @repo/desktop exec vitest run --shard=<n>/16
pnpm --filter @repo/desktop exec vitest run <target-test-file-1> <target-test-file-2>
rg -o 'TC-[A-Za-z0-9-]*[0-9][A-Za-z0-9-]*' <workflow-path>/phase-11-manual-test.md <workflow-path>/outputs/phase-11/manual-test-checklist.md | sort -u
node .claude/skills/task-specification-creator/scripts/validate-phase11-screenshot-coverage.js --workflow <workflow-path>
ls -la <workflow-path>/outputs/phase-11/screenshots
rg -n '^## 画面カバレッジマトリクス$' <workflow-path>/phase-11-manual-test.md
rg -n "screenshots/.*\\.png|NON_VISUAL:" <workflow-path>/outputs/phase-11/manual-test-result.md
ps -ef | rg "capture-.*phase11|vite" | rg -v rg || true
```

## 6. 完了チェック

- [ ] skill feedback promotion がある場合、promotion target / no-op reason / evidence path が `skill-feedback-report.md` と更新先 reference/asset で一致している
- [ ] `.agents/skills/<skill>` mirror が存在する場合、sync 後の `diff -qr` 結果を記録している
- [ ] プロファイル選択（標準5仕様書 / UI機能6仕様書）が明記されている
- [ ] 5仕様書（interfaces/api-ipc/security/task-workflow/lessons）が同一ターンで更新されている
- [ ] UI機能の場合、`ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` / `task-workflow` / `lessons-learned` を 1仕様書=1SubAgent で同一ターン更新している
- [ ] UI機能の場合、`ui-ux-components.md` にも `実装内容と苦戦箇所サマリー` を追加している
- [ ] UIドメイン固有正本（例: `ui-ux-navigation.md`）がある場合、SubAgent-G+ を追加して同一ターン更新している
- [ ] preview/search 系 UI タスクでは `ui-ux-search-panel.md` / `ui-ux-design-system.md` / `error-handling.md` / `architecture-implementation-patterns.md` の要否を判定し、該当分を SubAgent-G+ で同一ターン更新している
- [ ] `handler/register/preload` 三点突合が完了している
- [ ] IPC登録修正タスクでは `service 公開境界`（`services/*/index.ts` export）を確認し、未対応時は未タスク移管を記録している
- [ ] 変更履歴が各仕様書で更新されている
- [ ] 検証コマンド結果が `task-workflow.md` に記録されている
- [ ] design/spec_created タスクでは Phase 4（契約テスト）/ Phase 6（回帰テスト）の責務境界を記録し、重複候補を未タスク化している
- [ ] `audit-unassigned-tasks --diff-from HEAD` の `currentViolations=0` を確認し、移動直後の untracked completed file は `audit --target-file` で補完している
- [ ] Light Mode / contrast 系 UI task では `SubAgent-L1..L4` または同等の責務分離を使い、design-system / components / task-workflow / lessons を同一ターンで同期している
- [ ] Light Mode / contrast 系 UI task では `rg -n "text-white|bg-white/|border-white/|text-gray-|bg-gray-|border-gray-" apps/desktop/src/renderer` の監査結果を残している
- [ ] Light theme shared color migration の `spec_created` task では `SubAgent-M1..M5` または同等の責務分離を使い、inventory correction / verification-only lane / auth-search-security cross-cutting spec を同一ターンで同期している
- [ ] Light theme shared color migration の `spec_created` task では actual target inventory と verification-only wrappers が別行で記録されている
- [ ] Light theme shared color migration の `spec_created` task では Phase 1-3 completed / Phase 4+ planned / workflow status=`spec_created` が台帳と artifacts で一致している
- [ ] GitHub desktop CI が shard 単位で失敗した場合、`pnpm --filter @repo/desktop exec vitest run --shard=<n>/16` の結果を `task-workflow.md` に転記している
- [ ] 未タスクの配置先判定（active workflow 由来の未実施=`docs/30-workflows/unassigned-task/`、completed workflow 由来の継続 backlog=`docs/30-workflows/completed-tasks/<workflow>/unassigned-task/`、完了済み standalone UT=`docs/30-workflows/completed-tasks/`、legacy=`docs/30-workflows/completed-tasks/unassigned-task/`）を記録している
- [ ] `audit --target-file` の対象が、実際の正本配置（active / completed parent / standalone completed）と一致していることを確認している
- [ ] 関連未タスク参照の正本が実際の配置先と一致している（active workflow は root、completed workflow は parent workflow 配下）
- [ ] screenshot 検証で露出した副次不具合や warning を `docs/30-workflows/unassigned-task/` へ正式起票している
- [ ] 親タスクの苦戦箇所がある場合、新規未タスクに `### 3.5 実装課題と解決策` を追加して継承している
- [ ] 苦戦箇所と簡潔解決手順が `lessons-learned.md` に反映されている
- [ ] `task-workflow.md` / `lessons-learned.md` / `<domain-spec or ui-ux-feature-components.md>` の3点に同一の「5分解決カード」が同期されている
- [ ] 仕様書別SubAgent実行ログで、全担当の「実装内容 + 苦戦箇所 + 検証証跡」が記録されている
- [ ] 2workflow同時監査時は `workflow-a` / `workflow-b` の検証結果が両方記録されている
- [ ] docs-only parent workflow では `SubAgent-P1..P5` または同等の責務分離を使い、pointer / index / spec / script / mirror / evidence board を同一ターンで閉じている
- [ ] docs-only parent workflow では `task-workflow.md` / `ui-ux-feature-components.md` / `interfaces-*` / `workflow-<feature>.md` / `lessons-learned.md` / `skill-creator` templates の担当境界が `system-spec-update-summary.md` に記録されている
- [ ] user が screenshot を要求した docs-heavy task では、representative visual re-audit board か `N/A` 理由のどちらかを `system-spec-update-summary.md` と `documentation-changelog.md` に記録している
- [ ] UIタスクでは preview preflight（`pnpm --filter @repo/desktop preview` + `curl -I http://127.0.0.1:4173`）を再撮影前に記録している
- [ ] worktree の preview source が揺れる UIタスクでは current worktree の `apps/desktop/out/renderer` を static serve して capture 元を固定している
- [ ] UIタスクでは TC命名互換（`TC-XX` / `TC-UI-*`）を事前確認し、coverage実行前に抽出結果を記録している
- [ ] UIタスクでは `validate-phase11-screenshot-coverage.js --workflow <workflow-path>` の `PASS` を記録している
- [ ] Light Mode / contrast 改修で screenshot を再取得した場合、coverage validator の PASS を再取得後の証跡として記録している
- [ ] UIタスクではスクリーンショット証跡（`outputs/phase-11/screenshots`）を台帳に記録している
- [ ] UIタスクでは視覚TCの証跡列を `screenshots/*.png` 記法で記録している
- [ ] workspace/preview UI では right preview panel の reverse resize を証跡化している
- [ ] file watcher を含む UI では callback ref 分離など、watch 再登録を抑止する実装/設計を仕様へ転記している
- [ ] light theme screenshot では補助テキスト・status bar・chip の contrast を目視確認し、是正結果を記録している
- [ ] ユーザーが画面検証を要求した場合、初期方針が `NON_VISUAL` でも `SCREENSHOT` へ昇格し、`TC-ID ↔ png` を再同期している
- [ ] persist/auth 初期化バグでは bug path の metadata 証跡と screenshot harness 証跡を分離し、`skipAuth=true` を唯一経路にしていない
- [ ] UIタスクでは非視覚TCを `NON_VISUAL:` 記法で記録し、許容理由を明記している
- [ ] UIタスクでは再撮影後に残留プロセス（`vite` / `capture-*`）を確認し、必要なら停止している
- [ ] UIタスクで preflight 失敗時は再撮影を中断し、未タスク化と代替証跡理由を記録している
- [ ] UIタスクで coverage が warning になった場合、`manual-test-checklist` 代替や `画面カバレッジマトリクス` 未記載などの理由を成果物へ明記している
- [ ] `apps/desktop test:run` が `SIGTERM` の場合、失敗ログと `vitest run` 分割実行結果を同時に記録している
- [ ] `phase-12-documentation.md` が `ステータス=completed` で、Task 12-1〜12-5 が `[x]` で同期されている
- [ ] `artifacts.json` と `outputs/artifacts.json` が同一内容で同期されている
- [ ] `generate-index.js --workflow <workflow-path> --regenerate` 後の `index.md` が Phase 状態を正しく表示している
- [ ] `generate-index.js` 後に `index.md` が `undefined` 混入や全Phase未実施化を起こしていない。発生時は手動復旧し、generator/schema 互換問題を未タスク化している
- [ ] completed 扱いの `phase-1..11` 本文仕様書に `pending` が残っていない
- [ ] `phase-12-documentation.md` の更新対象表と `documentation-changelog.md` の Step 2 判定が一致している
- [ ] `system-spec-update-summary.md` の更新対象一覧が Step 2 判定と一致している
- [ ] `audit --diff-from HEAD` の結果は `currentViolations` を合否、`baselineViolations` を監視として分離記録している
- [ ] `implementation-guide.md` の Part 1 に日常例えを示す `たとえば` が明示されている
- [ ] UIタスクでは `phase-11-manual-test.md` に `## 画面カバレッジマトリクス` 見出しが存在する
- [ ] 利用テンプレート（retrospective/subagent）の重複行（同一手順番号・同一コマンド）が解消されている

## 7. 最適なファイル形成（仕様書別）

### 7.1 仕様書単位の出力粒度

| 仕様書 | 最小構成（必須） |
| --- | --- |
| `task-workflow.md` | 実装内容、苦戦箇所、検証証跡、5分解決カード |
| `lessons-learned.md` | 苦戦箇所（再発条件付き）、5分解決カードテンプレート |
| `<domain-spec>.md` | 実装差分、契約/責務境界、再利用ルール、5分解決カード導線 |

### 7.2 記録整合チェック

- [ ] SubAgentごとに「実装内容 + 苦戦箇所 + 検証証跡」を同一行で記録している
- [ ] 仕様書間で検証値（13/13, 28項目, current=0 など）の値が一致している
- [ ] 3仕様書（`task-workflow.md` / `lessons-learned.md` / `<domain-spec or ui-ux-feature-components.md>`）で5分解決カードの5ステップ順序が一致している
- [ ] UIタスクでは画面証跡の時刻が仕様書間で一致している

## 8. 追補プロファイル: Onboarding Wizard / Settings rerun

### 8.1 適用条件

- 初回表示オーバーレイ
- multi-step onboarding
- Settings からの rerun 導線
- persist key による再表示抑制

### 8.2 最低限更新する canonical docs

1. `/.claude/skills/aiworkflow-requirements/references/task-workflow.md`
2. `/.claude/skills/aiworkflow-requirements/references/ui-ux-feature-components.md`
3. `/.claude/skills/aiworkflow-requirements/references/ui-ux-navigation.md`
4. `/.claude/skills/aiworkflow-requirements/references/ui-ux-settings.md`
5. `/.claude/skills/aiworkflow-requirements/references/arch-state-management.md`
6. `/.claude/skills/aiworkflow-requirements/references/lessons-learned.md`
7. `/.claude/skills/aiworkflow-requirements/references/workflow-onboarding-wizard-alignment.md`

### 8.3 関心ごとの分離

- 画面導線担当:
  - overlay 表示条件
  - step 遷移
  - 完了後の戻り先
  - screenshot 証跡の照合
- 設定導線担当:
  - rerun button 文言
  - persist key と local state の責務分離
  - dashboard への handoff
  - discoverability 課題の backlog 化要否
- 品質/未タスク担当:
  - verification report の MINOR 抽出
  - `docs/30-workflows/unassigned-task/` への formalize
  - 既存 follow-up 指示書の `2.2` / `3.1` / `3.5` / 検証手順が current contract を向いているか確認
  - `verify-unassigned-links.js`
  - `audit-unassigned-tasks.js --diff-from HEAD`
  - 必要時 `audit-unassigned-tasks.js --diff-from HEAD --target-file <follow-up-file>`

### 8.4 完了条件

- Phase 12 側に implementation-guide / system-spec-update-summary / documentation-changelog / unassigned-task-detection / skill-feedback-report が揃っている
- canonical docs 側に実装内容と苦戦箇所が同一用語で残っている
- UI 本体完了と follow-up backlog が責務分離されている
- 既存 follow-up backlog を流用した場合、`docs/30-workflows/unassigned-task/` の本文も current contract へ再同期されている
- `workflow-onboarding-wizard-alignment.md` が作成または更新され、統合入口が残っている

## 9. 追補プロファイル: UI visual baseline drift / dark-mode screenshot

### 9.1 適用条件

- dark-mode / light-mode の visual regression
- browser defaults と spec defaults の不一致が疑われる場合
- `TC-ID ↔ png ↔ manual-test-result` の 1:1 対応が必要な場合
- completed ledger と lessons を同一 wave で sync したい場合

### 9.2 最低限更新する canonical docs

1. `/.claude/skills/aiworkflow-requirements/references/workflow-ui-ux-visual-baseline-drift.md`
2. `/.claude/skills/aiworkflow-requirements/references/task-workflow-completed-ui-ux-visual-baseline-drift.md`
3. `/.claude/skills/aiworkflow-requirements/references/lessons-learned-ui-ux-visual-baseline-drift.md`
4. `/.claude/skills/aiworkflow-requirements/references/task-workflow.md`
5. `/.claude/skills/aiworkflow-requirements/references/lessons-learned.md`
6. `/.claude/skills/aiworkflow-requirements/indexes/resource-map.md`
7. `/.claude/skills/aiworkflow-requirements/indexes/quick-reference.md`
8. `/.claude/skills/skill-creator/assets/phase12-system-spec-retrospective-template.md`
9. `/.claude/skills/skill-creator/references/patterns-success-phase12-advanced.md`
10. `/.claude/skills/skill-creator/SKILL.md`

### 9.3 関心ごとの分離

- browser theme 担当:
  - `playwright.config.ts` の `colorScheme` 固定
  - spec-level `test.use({ colorScheme })` 固定
  - browser defaults の差分切り分け
- screenshot evidence 担当:
  - `TC-ID` ベースの screenshot 命名
  - `manual-test-result.md` / `manual-test-checklist.md` / `screenshot-plan.json` の同値同期
  - `outputs/phase-11/screenshots/` の保存確認
- docs/spec sync 担当:
  - workflow / completed ledger / lessons / lookup の同一 wave 更新
  - current と baseline の分離記録
  - mirror diff zero の確認

### 9.4 完了条件

- `playwright.config.ts` と visual spec の両方で `colorScheme` が固定されている
- Phase 11 screenshot evidence が `TC-ID ↔ png ↔ manual-test-result` で揃っている
- `task-workflow` / `lessons-learned` / lookup docs が同一 wave で更新されている
- mirror diff と検証スクリプトが PASS している
