# Phase 12 システム仕様更新・苦戦箇所テンプレート

> **用途**: Phase 12 Step 2 で「今回の実装内容」と「苦戦箇所」を aiworkflow-requirements へ再利用可能な形で反映する。
> **推奨出力先**: `docs/30-workflows/<TASK-ID>/outputs/phase-12/system-spec-update-summary.md`
> **cross-cutting follow-up の追加テンプレート**: `references/workflow-<feature>.md` を新規作成する場合は `skill-creator/assets/phase12-integrated-workflow-spec-template.md` を併用する。
> **関連仕様書（推奨5点セット）**:
> - `references/<interface-spec>.md`（型/API契約）
> - `references/<api-ipc-spec>.md`（IPC契約）
> - `references/<security-spec>.md`（セキュリティ仕様）
> - `references/task-workflow.md`（完了台帳）
> - `references/lessons-learned.md`（再発防止知見）
>  
> **UI機能実装時（TASK-UI-05型）の推奨6+α点セット**:
> - `references/ui-ux-components.md`（主要UI一覧・完了タスク）
> - `references/ui-ux-feature-components.md`（機能仕様・関連未タスク・苦戦箇所）
> - `references/arch-ui-components.md`（UI構造・責務境界）
> - `references/arch-state-management.md`（状態管理パターン）
> - `references/task-workflow.md`（完了台帳）
> - `references/lessons-learned.md`（再発防止知見）
> - `references/<ui-domain-spec>.md`（必要時。例: `ui-ux-navigation.md` のようなドメイン固有 UI 正本）
> - `references/ui-ux-design-system.md`（token / theme / contrast 所見がある場合）
> - `references/ui-ux-search-panel.md`（shortcut / focus trap / ranking / no-match 契約がある場合）
> - `references/error-handling.md`（recoverable / fatal error surface を追加した場合）
> - `references/architecture-implementation-patterns.md`（renderer local timeout+retry / parse fallback を標準化した場合）

> **Phase 12 実績ベース更新ルール**:
> - 完了記録は `verify` / `validate` / `diff` / `audit` / `screenshot` の当日実測値だけを書く
> - `実施予定` / `後続で追記` / `N/A` を完了文言に残さない
> - user が画面検証を要求したら、docs-heavy / backend-heavy でも `SCREENSHOT + NON_VISUAL` へ昇格する
> - 苦戦箇所は `症状 / 再発条件 / 解決策 / 標準ルール` の4点で再利用カード化する
> - `workflow-<feature>.md` を使う wave では `current canonical set` / `artifact inventory` / `legacy-ordinal-family-register.md` / `topic-map` を同一ターンで更新する
> - `generate-index.js` → `validate-structure.js` → mirror sync → `diff -qr` を完了判定へ含める
> - 500行超過が出たら semantic filename で family split し、split 後の current canonical set を書き換える
> - targeted suite PASS と wider suite blocker は分離記録し、wider blocker は既存未タスクとの重複確認後にのみ formalize する
> - Skill/template changes are not complete until the owning `.claude/skills/<skill>` file is updated and mirror parity is recorded when `.agents/skills/<skill>` exists.

> **統合 workflow 正本を追加する条件**:
> - 更新先が 4仕様書以上に分散する
> - `task-workflow.md` / `lessons-learned.md` / domain spec だけでは全体像を再利用しにくい
> - preview/search、guard、pointer sweep、theme remediation のように UI/状態/検証/運用が横断する

---

## 1. メタ情報

| 項目 | 値 |
| --- | --- |
| タスクID | `<TASK-ID>` |
| 実施日 | `YYYY-MM-DD` |
| ステータス | `completed` / `spec_created` |
| 監査対象workflow | `<workflow-a>`（必須） / `<workflow-b>`（必要時） |
| SubAgent分担 | `A:interfaces / B:api-ipc / C:security / D:task-workflow / E:lessons` または `A:ui-ux-components / B:ui-ux-feature-components / C:arch-ui-components / D:arch-state-management / E:task-workflow / F:lessons / G+:<ui-domain-spec>` |

---

## 2. 実装内容サマリー

| 観点 | 内容 |
| --- | --- |
| 何を実装したか | `<実装の要点を1-2行>` |
| 変更範囲 | `<Main / Preload / Renderer / Store など>` |
| なぜ必要か | `<背景と狙い>` |
| 完了判定 | `<Phase 12要件と一致する根拠>` |

### 2.3 実績ベース更新・画面昇格・苦戦再利用ルール

| 観点 | 書き方 |
| --- | --- |
| 実績値 | `verify` / `validate` / `diff` / `audit` / `screenshot` の実測値だけを書く |
| planned wording 禁止 | `実施予定` / `後続タスク` / `N/A` を完了文言に残さない |
| 画面昇格 | user が画面検証を要求したら docs-heavy / backend-heavy でも `SCREENSHOT + NON_VISUAL` を採用する |
| 苦戦箇所 | `症状 / 再発条件 / 解決策 / 標準ルール` で再利用カード化し、`task-workflow` と `lessons-learned` へ同値転記する |
| canonical navigation | `current canonical set` / `artifact inventory` / `legacy register` / `topic-map` を same-wave で更新する |
| line budget | `validate-structure.js` 後に 500 行超過を semantic split し、親 doc と index を追従更新する |
| stale fact cleanup | 古いテスト件数 / coverage / out-of-scope 注記 / 日付 / follow-up 件数を `outputs/phase-12` と未タスク指示書で同一値へそろえる |
| `spec_created` close-out | workflow root が `completed-tasks/` 配下でも status は `spec_created` を維持し、Part 2 は `current contract + target delta` で書く |
| internal hardening 判定 | public response が不変でも、runtime helper class / owner boundary / source provenance / budget degrade ルールが増えたら Step 2 を `更新あり` と判定する。例: dryRun/apply 副作用境界、DB migration 実体差分、bulk back-fill budget/resume、retryable HTTP mapping |
| screenshot/compliance hardening | placeholder-only PNG で完了扱いにせず、`TC-ID ↔ png ↔ coverage ↔ metadata ↔ fallback reason` と implementation guide Part 2 の必須項目を実測値で閉じる |
| dark-mode screenshot stability | `playwright.config.ts` の `use.colorScheme` と spec の `test.use({ colorScheme })` を両方固定し、片側だけの設定で baseline drift を残さない |

> ここでの「完了」は、代表スクリーンショットと実測証跡が current workflow に保存されていることを含む。
> 旧 path / 旧 filename が残る場合は、`legacy-ordinal-family-register.md` で current semantic filename へ引き直せる状態を必須とする。

### 2.4 targeted / wider suite / backlog dedup

| 観点 | 記録内容 |
| --- | --- |
| targeted tests | 今回変更箇所を直接守る test file と pass 件数 |
| wider suite | 範囲外 blocker がある場合は file / error / current owner task を明記 |
| duplicate backlog check | `docs/30-workflows/unassigned-task/` と `docs/30-workflows/completed-tasks/unassigned-task/` への検索結果 |
| formalize decision | `新規未タスク化` / `既存 tracker 再利用` / `対応不要` のいずれかを明記 |
| screenshot evidence | `TC-ID`、review board/actual png、`screenshot-coverage.md`、metadata JSON、fallback reason、source evidence を current workflow に揃えたか |

---

## 3. 仕様書別SubAgent分担（必須）

| SubAgent | 担当仕様書 | 主担当作業 | 依存関係 |
| --- | --- | --- | --- |
| A | `references/<interface-spec>.md` | 型/API契約の同期 | 実装差分確定後 |
| B | `references/<api-ipc-spec>.md` | IPCチャネル契約（request/response/validation）同期 | A完了後 |
| C | `references/<security-spec>.md` | sender/P42/入力検証/エラーサニタイズ同期 | B完了後 |
| D | `references/task-workflow.md` | 完了台帳・検証証跡・残課題同期 | A/B/C完了後 |
| E | `references/lessons-learned.md` | 苦戦箇所と再利用手順の教訓化 | D完了後 |

### 3.1 UI機能実装向けSubAgent分担（TASK-UI-05型）

| SubAgent | 担当仕様書 | 主担当作業 | 依存関係 |
| --- | --- | --- | --- |
| A | `references/ui-ux-components.md` | 主要UI一覧・完了タスク・関連導線の同期 | 実装差分確定後 |
| B | `references/ui-ux-feature-components.md` | 機能仕様・関連未タスク・苦戦箇所の同期 | A完了後 |
| C | `references/arch-ui-components.md` | UI構造と責務境界の同期 | A/B完了後 |
| D | `references/arch-state-management.md` | 状態管理設計とP31対策の同期 | C完了後 |
| E | `references/task-workflow.md` | 完了台帳・検証証跡・未タスクの同期 | A/B/C/D完了後 |
| F | `references/lessons-learned.md` | 再発条件付き教訓と簡潔手順の同期 | E完了後 |

#### 3.1.1 UIドメイン追加仕様（必要時）

| SubAgent | 担当仕様書 | 主担当作業 | 依存関係 |
| --- | --- | --- | --- |
| G+ | `references/<ui-domain-spec>.md` / `references/ui-ux-search-panel.md` / `references/ui-ux-design-system.md` / `references/error-handling.md` / `references/architecture-implementation-patterns.md` | ドメイン固有 UI 正本または preview/search cross-cutting 正本へ実装内容・苦戦箇所・再利用手順を同期 | A/B/C/D完了後、E/Fと同一ターン |

再確認タスクでは次の分担に置き換えてよい:
- `A: task-workflow`
- `B: lessons-learned`
- `C: unassigned-task (配置/見出し/監査)`
- `D: 検証（verify/validate/links/audit）`

### 3.2 2workflow同時監査プロファイル（spec_created + completed）

| workflow | 種別 | 必須検証 | 記録先 |
| --- | --- | --- | --- |
| `<workflow-a>` | `spec_created` / `completed` | `verify-all-specs` + `validate-phase-output` + Task 1/3/4/5 実体突合 | `task-workflow.md` 再確認テーブル |
| `<workflow-b>` | `spec_created` / `completed` | `verify-all-specs` + `validate-phase-output` + Task 1/3/4/5 実体突合 | `task-workflow.md` 再確認テーブル |

> `<workflow-b>` が不要な場合は1workflowのみで運用し、理由を「備考」に明記する。

### 3.2.1 docs-only parent workflow sweep プロファイル

| SubAgent | 担当仕様書 / 成果物 | 主担当作業 | 依存関係 |
| --- | --- | --- | --- |
| P1 | `task-060` 相当の parent pointer doc / completed-task pointer docs / `task-000` / `task-090` | parent-child root、legacy status、pointer inventory を completed 正本へそろえる | 実装差分確定後 |
| P2 | `references/task-workflow.md` / `references/ui-ux-feature-components.md` / `references/interfaces-*.md` | completed root、representative evidence path、5分解決カードを同期 | P1 完了後 |
| P3 | `references/workflow-<feature>.md` / `references/lessons-learned.md` | docs-only parent workflow の統合正本、苦戦箇所、標準ルールを同期 | P2 完了後 |
| P4 | `scripts/validate-<parent-sweep>.mjs` / `diff -qr .claude/skills/<skill> .agents/skills/<skill>` | path / status / mirror drift guard を機械検証 | P1-P3 完了後 |
| P5 | `outputs/phase-11/*` / `outputs/phase-12/system-spec-update-summary.md` / `skill-creator` templates | representative visual re-audit board と SubAgent 実行ログ、再利用テンプレート化を同一ターンで残す | P2-P4 と同一ターン |

> user が screenshot を要求した docs-heavy task では、P5 を `N/A` にせず current workflow への representative screenshot 集約可否を最初に判定し、`SCREENSHOT + NON_VISUAL` で閉じる。

### 3.3 仕様書別SubAgent実行ログ（必須）

| SubAgent | 担当仕様書 | 実装内容の反映先 | 苦戦箇所の反映先 | 検証証跡 |
| --- | --- | --- | --- | --- |
| `<SubAgent-A>` | `<spec-a>` | `<実装内容を反映したセクション/見出し>` | `<苦戦箇所を反映したセクション/見出し>` | `<verify/validate/links/audit/UI証跡のいずれか>` |
| `<SubAgent-B>` | `<spec-b>` | `<実装内容を反映したセクション/見出し>` | `<苦戦箇所を反映したセクション/見出し>` | `<verify/validate/links/audit/UI証跡のいずれか>` |
| `<SubAgent-C>` | `<spec-c>` | `<実装内容を反映したセクション/見出し>` | `<苦戦箇所を反映したセクション/見出し>` | `<verify/validate/links/audit/UI証跡のいずれか>` |

> 各行は「実装内容」と「苦戦箇所」の両列を必須とし、片側のみ更新を禁止する。

---

## 4. 仕様反映先（テンプレート準拠）

| 仕様書 | 反映内容 | 証跡 |
| --- | --- | --- |
| `task-workflow.md` | 完了タスク・成果物・苦戦箇所・簡潔手順を記録 | `<該当セクション>` |
| `<domain-spec>.md` | 実装仕様・契約差分・苦戦箇所・関連タスクを記録 | `<該当セクション>` |
| `lessons-learned.md` | 再発条件付きの苦戦箇所と再利用手順を記録 | `<該当セクション>` |

### 4.1 標準5仕様書の転記チェック（TASK-10A-C型）

| 仕様書 | 必須記載 | 担当SubAgent |
| --- | --- | --- |
| `interfaces-agent-sdk-skill.md` | 実装した型/API契約、苦戦箇所、同種課題の簡潔解決手順 | A |
| `api-ipc-agent.md` | request/response/validation、苦戦箇所、同種課題の簡潔解決手順 | B |
| `security-electron-ipc.md` | sender/P42/構造/サニタイズ、苦戦箇所、同種課題の簡潔解決手順 | C |
| `task-workflow.md` | 完了記録、検証証跡、SubAgent分担、苦戦箇所 | D |
| `lessons-learned.md` | 再発条件付きの苦戦箇所、同種課題の簡潔解決手順 | E |

> 上記5仕様書は同一ターンで更新し、`task-workflow.md` の対象タスク節に SubAgent 分担表を転記する。

UI機能実装の場合は次を推奨:
- `ui-ux-components.md`（実装内容・完了タスク・未タスク導線）
- `ui-ux-feature-components.md`（機能仕様・苦戦箇所）
- `arch-ui-components.md` / `arch-state-management.md`（設計整合）
- `ui-ux-design-system.md`（token / contrast / theme 改善がある場合）
- `ui-ux-search-panel.md`（shortcut / focus trap / ranking / no-match 契約がある場合）
- `error-handling.md`（timeout / parse / transport error の UI 応答を整理した場合）
- `architecture-implementation-patterns.md`（renderer local resilience を標準化した場合）
- `task-workflow.md` / `lessons-learned.md`（台帳・教訓）
- `ui-ux-navigation.md` などのドメイン固有 UI 正本（存在する場合）

### 4.2 UI current workflow 反映先マトリクス（最適ファイル形成）

| 情報の種類 | 最適な反映先 | 反映理由 |
| --- | --- | --- |
| 追加コンポーネント一覧、完了タスク、実装内容と苦戦箇所サマリー | `ui-ux-components.md` | UI カタログとして一覧性が高く、一覧だけ読んでも再利用ポイントを把握できる |
| 画面の振る舞い、関連未タスク、5分解決カード | `ui-ux-feature-components.md` | 機能単位で再利用しやすい |
| 専用型、adapter helper、harness、責務境界 | `arch-ui-components.md` | 構造上の判断理由を残せる |
| selector / store / reset 条件 | `arch-state-management.md` | 状態責務の正本に集約できる |
| token / contrast / theme 所見 | `ui-ux-design-system.md` | component 修正と token 改善を分離できる |
| shortcut / focus trap / ranking / no-match | `ui-ux-search-panel.md` | quick search / search dialog の挙動を検索仕様へ再利用可能な形で集約できる |
| renderer timeout / retry / parse fallback | `architecture-implementation-patterns.md` | UI実装で閉じた resilience pattern を他画面へ転用できる |
| retryable / fatal / recoverable error surface | `error-handling.md` | parse/read/timeout の UI 応答を共通の error contract に寄せられる |
| 実装全体像、SubAgent 編成、苦戦箇所、5分解決カード | `references/workflow-<feature>.md` | preview/search のような cross-cutting UI guard を 1 入口で再利用できる |
| 検証値、残課題、完了記録 | `task-workflow.md` | 台帳として追跡できる |
| 苦戦箇所、再発条件、標準手順 | `lessons-learned.md` | 次回の短時間解決に直結する |

> 迷った場合は「複数仕様書に同じ段落を貼る」のではなく、最初にこのマトリクスで責務を決めてから SubAgent 分担へ落とす。

### 4.2.1 Light theme shared color migration（`spec_created`）反映先マトリクス

| 情報の種類 | 最適な反映先 | 反映理由 |
| --- | --- | --- |
| actual target inventory、verification-only lane | `ui-ux-design-system.md` / `ui-ux-settings.md` | token/component 境界と Settings domain inventory を一緒に固定できる |
| Auth / WorkspaceSearch / dialog / panel state | `ui-ux-feature-components.md` / `ui-ux-search-panel.md` / `ui-ux-portal-patterns.md` / `rag-desktop-state.md` | search/portal/state の cross-cutting 条件を落としにくい |
| auth/api/security boundary | `api-ipc-auth.md` / `api-ipc-system.md` / `architecture-auth-security.md` / `security-electron-ipc.md` / `security-principles.md` | public auth shell と settings/search surface の安全境界を明示できる |
| `spec_created` 台帳、Phase 1-3 gate、苦戦箇所 | `task-workflow.md` / `lessons-learned.md` | Phase 1-3 completed / Phase 4+ planned の運用と 5分解決カードを固定できる |

> `SettingsView` / `SettingsCard` / `DashboardView` のような wrapper shell は、current inventory で主因でない限り verification-only lane へ分離する。

### 4.2.2 docs-only parent workflow 反映先マトリクス

| 情報の種類 | 最適な反映先 | 反映理由 |
| --- | --- | --- |
| parent pointer / completed-task pointer docs / legacy index の正規化 | parent workflow doc / `task-workflow.md` | 親導線と完了台帳を同時に閉じられる |
| Workspace lineage の representative visual review | `ui-ux-feature-components.md` | surface 単位で same-day evidence を辿りやすい |
| completed root / evidence path | `interfaces-*.md` | path drift を契約面から再利用できる |
| docs-only parent workflow の統合ルール | `references/workflow-<feature>.md` | pointer / index / spec / script / mirror を 1 入口で再現できる |
| 苦戦箇所、再発条件、5分解決カード | `lessons-learned.md` | 次回の調査時間を最短化できる |
| 再利用テンプレート、SubAgent プロファイル | `skill-creator` patterns / templates | 同種 task の初動をテンプレートで短縮できる |

### 4.2.3 Onboarding overlay / Settings rerun 反映先マトリクス

| 情報の種類 | 最適な反映先 | 反映理由 |
| --- | --- | --- |
| 実装全体像、SubAgent 分担、follow-up resweep の統合入口 | `references/workflow-onboarding-wizard-alignment.md` | overlay / rerun / persist / screenshot / backlog resweep を 1 入口で再現できる |
| 追加コンポーネント一覧、完了タスク、実装サマリー | `ui-ux-components.md` | UI カタログとして一覧性が高い |
| overlay flow、画面証跡、関連未タスク、5分解決カード | `ui-ux-feature-components.md` | 機能単位で再利用しやすい |
| overlay 表示条件、`system` preview readability | `ui-ux-navigation.md` | visual contract と表示条件の正本 |
| rerun button、force-open callback、Settings 責務 | `ui-ux-settings.md` | rerun 導線の責務境界を固定できる |
| persist key、dismiss / forcedOpen / completion ownership | `arch-state-management.md` | state 境界を保存責務込みで整理できる |
| 完了記録、検証値、既存 follow-up 配置確認 | `task-workflow.md` | 台帳と検証結果を同時追跡できる |
| 苦戦箇所、再発条件、5分解決カード | `lessons-learned.md` | 次回の短時間解決に直結する |
| 既存 follow-up 指示書本文 | `docs/30-workflows/unassigned-task/*.md` | 実際の実行仕様を current contract に保てる |

> Onboarding 系 Phase 12 では「新規未タスク 0 件」でも、既存 follow-up 本文の `2.2` / `3.1` / `3.5` / 検証手順を current contract へ再同期する。

### 4.3 APIキー連動 + チャット経路整合マトリクス（TASK-FIX-APIKEY-CHAT-TOOL-INTEGRATION-001型）

| 情報の種類 | 最適な反映先 | 反映理由 |
| --- | --- | --- |
| `AuthKeyExistsResponse.source` 契約 | `interfaces-auth.md` | 判定根拠（saved/env-fallback/not-set）の型正本 |
| `AIChatRequest(providerId/modelId)` と同期 request | `llm-ipc-types.md` | request/response 境界の型正本 |
| `AI_CHAT` 解決順、`llm:set-selected-config`、cache clear | `api-ipc-system.md` | 実行経路とチャネル契約の正本 |
| AI/チャット IPC 一覧 | `api-endpoints.md` | 探索導線の正本 |
| 判定根拠の非機密化（キー実値非公開） | `security-electron-ipc.md` | セキュリティ境界の正本 |
| AuthKeySection 表示条件と `source` 優先表示 | `ui-ux-settings.md` | 画面表示契約の正本 |
| 完了台帳・検証証跡・苦戦箇所 | `task-workflow.md` | 実施記録の正本 |
| 再発条件付き教訓と短手順 | `lessons-learned.md` | 同種課題の再利用起点 |

> APIキー連動系は `interfaces / llm / api-ipc / security / ui-ux-settings / task / lessons` の7仕様書を同一ターンで同期する。

---

## 5. 苦戦箇所（再利用可能形式）

| 苦戦箇所 | 再発条件 | 解決策 | 今後の標準ルール |
| --- | --- | --- | --- |
| `<課題1>` | `<再発しやすい条件>` | `<今回の対処>` | `<次回の標準運用>` |
| `<課題2>` | `<再発しやすい条件>` | `<今回の対処>` | `<次回の標準運用>` |
| `<課題3>` | `<再発しやすい条件>` | `<今回の対処>` | `<次回の標準運用>` |

---

## 6. 同種課題の5分解決カード（必須）

### 6.1 カード本体（コピペ用）

| 項目 | 記入内容 |
| --- | --- |
| 対象課題 | `<TASK-ID>` |
| 症状（1行） | `<今回の再発症状を1行で記述>` |
| 根本原因（1行） | `<再発条件を含む原因>` |
| 最短手順 | `1) 実体固定 2) 仕様是正 3) 画面証跡 4) 未タスク監査 5) 台帳同期` |
| 検証ゲート | `<13/13, 28項目, links, current=0 など>` |
| 同期先3点 | `<task-workflow / lessons-learned / domain-spec or ui-ux-feature>` |

### 6.2 最短5ステップ

1. `<変更範囲を標準5責務（interfaces/api-ipc/security/task/lessons）またはUI6+α責務（ui-ux-components/ui-ux-feature/arch-ui/arch-state/task/lessons + domain-ui-spec）へ分離する>`
2. `<実装 + 契約 + セキュリティを同一ターンで同期する>`
3. `<Light Mode 全画面是正では rg で renderer 全域の hardcoded neutral class を棚卸しし、token修正 / compatibility bridge / component migration の責務を先に分ける>`
4. `<未タスクがある場合は docs/30-workflows/unassigned-task/ に10見出し（## メタ情報 + ## 1..9）で作成し、workflow 直下 <workflow>/unassigned-task/ 参照のまま止めない。completed workflow 由来の継続 backlog は docs/30-workflows/completed-tasks/<workflow>/unassigned-task/ を正本にする>`
5. `<worktree では UI再撮影や検証前に pnpm install --frozen-lockfile を実行し、optional dependency 欠落を先に解消する>`
6. `<UIタスクは再撮影前に preview preflight（build成功 + 127.0.0.1:4173 疎通）を実施し、失敗時は未タスク化へ分離する>`
7. `<CI が desktop shard 単位で失敗している場合は pnpm --filter @repo/desktop exec vitest run --shard=<n>/16 で同じ shard を再現し、全量再実行だけで原因調査を済ませない>`
8. `<公開ビューを bypass した場合は shell 公開だけで閉じず、state reset 除外条件と nav 到達性も同一ターンで検証する>`
9. `<verify-unassigned-links / audit --diff-from HEAD / 必要時の audit --target-file で current/baseline を確定し、移動直後の untracked completed file は direct target-file を正本にする>`
10. `<phase-12-documentation.md / phase-1..11-*.md / artifacts.json / outputs/artifacts.json / index.md を同一ターンで同期し、generate-index.js --workflow ... --regenerate を実行する>`
11. `<generate-index.js 実行後は index.md の undefined 混入や全Phase未実施化を確認し、schema 互換問題なら workflow を手動復旧して未タスク化する>`
12. `<UIタスクでは validate-phase11-screenshot-coverage を追加し、全量 test:run が SIGTERM の場合は vitest 分割実行へフォールバックした記録を含めて、検証値と苦戦箇所を task-workflow と lessons に同時転記する>`
13. `<Light Mode / contrast 改修では screenshot を再取得し、token修正・compatibility bridge・component migration のどれで解消したかを system-spec-update-summary / task-workflow / lessons に同値転記する>`
14. `<persist/auth 初期化バグでは bug path を通常ルート metadata（navigation type / debug log absence / storage snapshot）で確認し、screenshot は dedicated harness に分離する。skipAuth=true を唯一経路にしない>`
15. `<worktree の preview source が揺れる UIタスクでは current worktree の out/renderer を static server で配信し、right preview panel reverse resize / watcher callback ref 分離 / light theme 補助テキスト contrast を同じ再監査セットで確認する>`

---

## 7. 検証コマンド

| コマンド | 目的 | 期待結果 |
| --- | --- | --- |
| `rg --files .claude/skills \| rg 'verify-all-specs\|validate-phase-output\|verify-unassigned-links\|audit-unassigned-tasks'` | 監査スクリプト実体の事前解決 | 実体パスが確認できる |
| `node .claude/skills/task-specification-creator/scripts/verify-all-specs.js --workflow <workflow-path> --strict` | ワークフロー仕様準拠確認 | `PASS` |
| `node .claude/skills/task-specification-creator/scripts/validate-phase-output.js <workflow-path>` | Phase出力構造確認 | `PASS` |
| `rg -n '^\\| ステータス \\| completed' <workflow-path>/phase-12-documentation.md && rg -n '^- \\[x\\] Task 12-[1-5]' <workflow-path>/phase-12-documentation.md` | `phase-12-documentation.md` のメタ情報/Task 12-1〜12-5 完了同期を確認 | `ステータス=completed` と Task 12-1〜12-5 が `[x]` で一致する |
| `diff -u <workflow-path>/artifacts.json <workflow-path>/outputs/artifacts.json` | artifacts 二重台帳の同期確認 | 差分なし |
| `node .claude/skills/task-specification-creator/scripts/generate-index.js --workflow <workflow-path> --regenerate` | workflow index 再生成 | `index.md` が再生成される |
| `rg -n 'undefined' <workflow-path>/index.md` | `generate-index` 後の壊れた index 早期検知 | 想定外の `undefined` が 0 件 |
| `rg -n '^\\| 12 \\| .* \\| .*完了' <workflow-path>/index.md && rg -n '^\\| 13 \\| .* \\| .*未実施' <workflow-path>/index.md` | workflow index 状態確認 | Phase 12=完了、Phase 13=未実施 |
| `rg -n 'ステータス\\s*\\|\\s*pending' <workflow-path>/phase-{1,2,3,4,5,6,7,8,9,10,11}-*.md` | workflow 本文 stale 確認 | 0件 |
| `rg -n "契約テスト|回帰テスト|TC-C|MR-" <workflow-path>/phase-4-test-creation.md <workflow-path>/phase-6-test-expansion.md` | Phase 4/6 のテスト責務境界と重複候補の監査 | 契約テスト（関数入出力）と回帰テスト（伝播経路）が分離され、重複候補が説明できる |
| `node .claude/skills/task-specification-creator/scripts/verify-all-specs.js --workflow <workflow-a> --json && node .claude/skills/task-specification-creator/scripts/verify-all-specs.js --workflow <workflow-b> --json` | 2workflow同時監査（構造） | 2件とも `PASS` |
| `node .claude/skills/task-specification-creator/scripts/validate-phase-output.js <workflow-a> && node .claude/skills/task-specification-creator/scripts/validate-phase-output.js <workflow-b>` | 2workflow同時監査（出力） | 2件とも `PASS` |
| `pnpm install --frozen-lockfile` | worktree / UI再撮影前の依存解決 preflight | 依存欠落が解消される |
| `rg -n "text-white\|bg-white/\|border-white/\|text-gray-\|bg-gray-\|border-gray-" apps/desktop/src/renderer` | Light Mode 全画面 drift の hardcoded neutral class 監査 | 修正対象が列挙される |
| `node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js` | 未タスクリンク整合確認 | `missing: 0` |
| `node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --target-file <unassigned-file>` | root `unassigned-task/` の対象未タスク監査 | `currentViolations: 0` |
| `node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --completed-unassigned-dir docs/30-workflows/completed-tasks/<workflow>/unassigned-task --target-file docs/30-workflows/completed-tasks/<workflow>/unassigned-task/<task>.md` | completed workflow 配下 backlog の current 監査 | `currentViolations: 0` |
| `node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --target-file docs/30-workflows/completed-tasks/<task>.md` | standalone completed task spec の current 監査 | `currentViolations: 0` |
| `node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD` | 今回差分の未タスク監査 | `currentViolations: 0` |
| `node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD \| jq '{currentViolations: .currentViolations.total, baselineViolations: .baselineViolations.total}'` | 未タスク監査カウンタ（current/baseline）を転記用に固定 | current/baseline の確定値が取得できる |
| `node scripts/validate-<parent-sweep>.mjs --json` | docs-only parent workflow の path / status drift 監査 | `path-drift=0 / status-drift=0 / mirror-drift=0` |
| `diff -qr .claude/skills/<canonical-skill> .agents/skills/<mirror-skill>` | dual root repository の mirror drift 監査 | 差分なし |
| `node apps/desktop/scripts/capture-<docs-heavy-review-board>.mjs` | representative visual re-audit board の生成 | current workflow 配下へ PNG と metadata が出力される |
| `rg -n "<UT-ID>|<task-id>" docs/30-workflows/unassigned-task docs/30-workflows/completed-tasks docs/30-workflows/completed-tasks/unassigned-task` | 未タスクの配置先判定（未完了/完了移管） | active workflow 由来は `unassigned-task`、completed workflow 由来は `completed-tasks/<workflow>/unassigned-task`、standalone completed UT は `completed-tasks/*.md`、legacy standalone は `completed-tasks/unassigned-task` |
| `rg -n '^## メタ情報$|^## [1-9]\\. ' <unassigned-file>` | 10見出しの機械確認 | `## メタ情報` が1件、`## 1..9` が9件 |
| `rg -n '## Part 1|## Part 2|なぜ|必要|例え|たとえば|interface|type|API|エッジケース|設定' <workflow-path>/outputs/phase-12/implementation-guide.md` | 実装ガイド Task 1 必須要素の簡易確認 | Part 1/Part 2 + 理由先行 + 日常例え（`たとえば` 含む）+ 型/API/エッジケース/設定語が検出される |
| `test -f <workflow-path>/outputs/phase-11/screenshot-plan.md && test -f <workflow-path>/outputs/phase-11/screenshots/phase11-capture-metadata.json` | screenshot 要求時の補助証跡実在確認 | 2ファイルとも存在する |
| `pnpm --filter @repo/desktop preview` | UI再撮影前の preview preflight（build成否確認） | `ready in ...` または build成功ログが確認できる |
| `python3 -m http.server 4173 --directory apps/desktop/out/renderer` | worktree で preview source が揺れる場合の current build static serve | current worktree build を `127.0.0.1:4173` で配信できる |
| `curl -I http://127.0.0.1:4173` | UI再撮影前のローカル疎通確認 | `HTTP/1.1 200` 系応答 |
| `pnpm --filter @repo/desktop run screenshot:<feature>` | UI画面証跡の当日再撮影（UIタスクのみ） | 対象TCのスクリーンショットが再生成される |
| `pnpm --filter @repo/desktop test:run` | 回帰の全量実行（ベースライン確認） | `PASS` または `SIGTERM` 失敗ログが記録される |
| `pnpm --filter @repo/desktop exec vitest run <target-test-file>` | UI/Store/Main の再確認テストを非watchで実行 | プロセスが単発終了し証跡を固定できる |
| `pnpm --filter @repo/desktop exec vitest run --shard=<n>/16` | GitHub desktop CI と同じ shard を local 再現 | shard 単位の PASS/FAIL が確定できる |
| `node .claude/skills/task-specification-creator/scripts/validate-phase11-screenshot-coverage.js --workflow <workflow-path>` | TC単位の証跡紐付け検証（UIタスクのみ） | `PASS`（expected TC = covered TC） |
| `pnpm --filter @repo/desktop exec vitest run <target-test-file-1> <target-test-file-2>` | 全量実行が `SIGTERM` の場合の分割フォールバック | 対象回帰の合否が確定できる |
| `rg -o 'TC-[A-Za-z0-9-]*[0-9][A-Za-z0-9-]*' <workflow-path>/phase-11-manual-test.md <workflow-path>/outputs/phase-11/manual-test-checklist.md \| sort -u` | TC命名互換（`TC-XX` / `TC-UI-*`）の事前確認 | 対象TCが抽出される |
| `ls -la <workflow-path>/outputs/phase-11/screenshots` | UI画面証跡の存在確認（UIタスクのみ） | スクリーンショットが列挙される |
| `rg -n '^## 画面カバレッジマトリクス$' <workflow-path>/phase-11-manual-test.md` | coverage validator 互換見出し確認（UIタスクのみ） | `## 画面カバレッジマトリクス` が1件以上検出される |
| `rg -n -e '^## 統合テスト連携$' -e '^## 成果物$' -e '^## 実行手順$' -e '^## 完了条件$' <workflow-path>/phase-11-manual-test.md` | Phase 11 必須節（統合テスト連携/成果物or実行手順/完了条件）確認 | 必須見出しが3種そろう |
| `ls -lt <workflow-path>/outputs/phase-11/screenshots` | UI再撮影証跡の鮮度確認（UIタスクのみ） | 最上位ファイルの更新時刻が当日である |
| `ps -ef \| rg "capture-.*phase11\|vite" \| rg -v rg || true` | UI再撮影後の残留プロセス確認（UIタスクのみ） | 不要プロセスが残留していない、または停止方針が記録済み |
| `node .claude/skills/skill-creator/scripts/quick_validate.js <skill-dir>` | スキル構造検証 | `error: 0` |

---

## 8. Phase 12 成果物チェック

- [ ] `implementation-guide.md`
- [ ] `system-spec-update-summary.md`（旧名 `system-spec-update-summary.md` は legacy alias としてのみ扱う）
- [ ] `documentation-changelog.md`
- [ ] `unassigned-task-detection.md`（標準）
- [ ] 旧名 `unassigned-task-report.md` を新規作成していない（互換用途のみ・非推奨）
- [ ] `phase12-task-spec-compliance-check.md`（任意だが推奨）
- [ ] `phase-12-documentation.md` が `ステータス=completed` で、Task 12-1〜12-5 のチェックが `[x]` になっている
- [ ] `artifacts.json` と `outputs/artifacts.json` が同一内容で同期されている
- [ ] `generate-index.js --workflow <workflow-path> --regenerate` 実行後の `index.md` が `artifacts.json` と同じ Phase 状態を表示している
- [ ] `generate-index.js` 実行後の `index.md` に `undefined` 混入や全Phase未実施化がない。発生時は workflow を手動復旧し、generator/schema 互換改善を未タスク化している
- [ ] completed 扱いの `phase-1..11` 本文仕様書に `ステータス=pending` が残っていない
- [ ] 未タスク指示書の見出しフォーマット（`## メタ情報` + `## 1..9`）確認
- [ ] 関連未タスク参照が workflow 直下 `.../<workflow>/unassigned-task/` で止まっていない（未実施は `docs/30-workflows/unassigned-task/` 正本、完了済みは `docs/30-workflows/completed-tasks/.../unassigned-task/`）
- [ ] `audit --target-file` の `currentViolations: 0` を確認し、対象の正本配置（root / completed parent / standalone completed）と一致している
- [ ] `verify-unassigned-links` / `audit --diff-from HEAD` の確定値（existing/missing/current/baseline）を `task-workflow.md` と `outputs/phase-12`（`system-spec-update-summary.md`/`unassigned-task-detection.md`）へ同値転記する
- [ ] 未タスクの配置先判定（未完了=`docs/30-workflows/unassigned-task/`、completed workflow 由来の継続 backlog=`docs/30-workflows/completed-tasks/<workflow>/unassigned-task/`、standalone completed UT=`docs/30-workflows/completed-tasks/*.md`、legacy standalone=`docs/30-workflows/completed-tasks/unassigned-task/`）を証跡化している
- [ ] Light Mode / contrast 是正では `token修正` / `compatibility bridge` / `component migration` のどれで閉じたかを仕様書へ明記している
- [ ] GitHub desktop CI が shard 単位で失敗した場合、`pnpm --filter @repo/desktop exec vitest run --shard=<n>/16` の結果を記録している
- [ ] screenshot 検証で副次不具合や warning が露出した場合、その場で `docs/30-workflows/unassigned-task/` に正式な未タスクを追加している
- [ ] 親タスクに苦戦箇所がある場合、新規未タスクへ `### 3.5 実装課題と解決策` を追加し、再発条件と解決策を継承している
- [ ] Light Mode / contrast 改修で screenshot を再取得した場合、coverage validator の PASS を再取得後の証跡として記録している
- [ ] 2workflow同時監査時は両workflowの `verify-all-specs` / `validate-phase-output` 証跡を記録
- [ ] docs-only parent workflow では `SubAgent-P1..P5` または同等の責務分離を使い、pointer / index / spec / script / mirror / evidence board を同一ターンで閉じている
- [ ] docs-only parent workflow では `task-workflow.md` / `ui-ux-feature-components.md` / `interfaces-*` / `workflow-<feature>.md` / `lessons-learned.md` / `skill-creator` templates の担当境界が `system-spec-update-summary.md` に記録されている
- [ ] user が screenshot を要求した docs-heavy task では、representative visual re-audit board か `N/A` 理由のどちらかを `system-spec-update-summary.md` と `documentation-changelog.md` に記録している
- [ ] `task-workflow.md` の対象タスク節へ「仕様書別SubAgent分担」表を転記する
- [ ] 仕様書別SubAgent実行ログ（実装内容/苦戦箇所/検証証跡）を `system-spec-update-summary.md` に記録する
- [ ] `task-workflow.md` / `lessons-learned.md` / `<domain-spec or ui-ux-feature-components.md>` の3点へ同一内容の「5分解決カード」を記録する
- [ ] design/spec_created タスクでは Phase 4（契約テスト）/ Phase 6（回帰テスト）の責務境界を記録し、重複候補は未タスク化している
- [ ] Light theme shared color migration の `spec_created` task では actual target inventory と verification-only lane を明記している
- [ ] Light theme shared color migration では `ui-ux-settings` / `ui-ux-search-panel` / `ui-ux-portal-patterns` / `rag-desktop-state` / `api-ipc-auth` / `api-ipc-system` / `architecture-auth-security` / `security-electron-ipc` / `security-principles` の要否判定を記録している
- [ ] Light theme shared color migration の `spec_created` task では Phase 1-3 completed / Phase 4+ planned / workflow status=`spec_created` が同期している
- [ ] UIタスクでは `ui-ux-components.md` にも「実装内容と苦戦箇所サマリー」を残し、一覧specから再利用ポイントを辿れるようにする
- [ ] UIドメイン固有正本（例: `ui-ux-navigation.md`）が存在する場合、基本6仕様書に加えて同一ターンで更新している
- [ ] preview/search 系 UI タスクでは `ui-ux-search-panel.md` / `ui-ux-design-system.md` / `error-handling.md` / `architecture-implementation-patterns.md` の cross-cutting 4仕様書について要否判定を記録し、該当時は同一ターンで更新している
- [ ] preview/search や guard 系 UI task で更新先が 4仕様書以上に分散する場合、`references/workflow-<feature>.md` を追加し、`resource-map.md` / `quick-reference.md` / 対象 skill の `SKILL.md` まで直リンクを張っている
- [ ] 公開ビュー bypass を実装した場合、shell 公開だけでなく state reset 除外条件と nav 到達性も同一ターンで記録している
- [ ] UIタスクでは `phase-11-manual-test.md` に必須節（`統合テスト連携` / `成果物 or 実行手順` / `完了条件`）が存在する
- [ ] `implementation-guide.md` の Part 1 に日常例えを示す `たとえば` が明示されている
- [ ] UIタスクでは `phase-11-manual-test.md` に `## 画面カバレッジマトリクス` 見出しが存在する
- [ ] UIタスクでは worktree preflight として `pnpm install --frozen-lockfile` の要否を確認し、実行した場合は記録している
- [ ] UIタスクでは再撮影前に preview preflight（build成功 + `127.0.0.1:4173` 疎通）を記録している
- [ ] worktree の preview source が揺れる UIタスクでは current worktree の `apps/desktop/out/renderer` を static server で配信した記録がある
- [ ] UIタスクでは `validate-phase11-screenshot-coverage.js --workflow <workflow-path>` が `PASS` である
- [ ] UIタスクでは再撮影したスクリーンショット証跡（`outputs/phase-11/screenshots`）を記録し、更新時刻が当日である
- [ ] workspace/preview UI では right preview panel の reverse resize を manual test または screenshot で確認している
- [ ] file watch を含む UI では callback ref 分離などにより watch 再登録が抑止される設計/実装を記録している
- [ ] light theme screenshot では補助テキスト・status bar・chip の contrast を目視確認し、必要な是正を記録している
- [ ] ユーザーが画面検証を要求した場合、初期方針が `NON_VISUAL` でも `SCREENSHOT` へ昇格し、`TC-ID ↔ png` を再同期している
- [ ] persist/auth 初期化バグでは bug path の metadata 証跡と screenshot harness 証跡を分離し、`skipAuth=true` を唯一経路にしていない
- [ ] ユーザーが画面検証を要求した場合、`screenshot-plan.md` と `screenshots/phase11-capture-metadata.json` を workflow 配下へ保存している
- [ ] UIタスクで preflight が失敗した場合は、再撮影を継続せず未タスク化し、代替証跡の理由を記録している
- [ ] UIタスクでは `manual-test-result.md` / `screenshot-coverage.md` の時刻記録が実ファイル `stat` と整合する
- [ ] dark-mode screenshot task では `playwright.config.ts` と visual spec の `colorScheme` が一致し、`TC-ID ↔ png ↔ manual-test-result` を 1:1 で管理している
- [ ] UIタスクでは再撮影後に残留プロセス（`vite` / `capture-*`）を確認し、必要なら停止している

---

## 9. 最適なファイル形成（Phase 12 Step 2）

### 9.1 記述順序（固定）

1. `task-workflow.md`（完了台帳・検証証跡・苦戦箇所）
2. `<domain-spec>.md`（実装仕様と契約差分）
3. `lessons-learned.md`（再発条件付き教訓）

> UI機能実装では `ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` を 2 と 3 の間に追加する。

### 9.2 各仕様書の必須ブロック（コピペ用）

```markdown
### 実装内容（要点）
- 変更範囲:
- 実装した要点:
- 完了根拠:

### 苦戦箇所（再利用形式）
| 苦戦箇所 | 再発条件 | 対処 | 標準ルール |
| --- | --- | --- | --- |
|  |  |  |  |

### 同種課題の5分解決カード（最短手順）
1.
2.
3.
4.
5.
```

### 9.3 ファイル形成チェック

- [ ] 仕様書ごとに `実装内容` と `苦戦箇所` の両方が存在する
- [ ] `task-workflow.md` と `lessons-learned.md` の検証値（verify/validate/links/audit）が一致する
- [ ] 3仕様書（`task-workflow.md` / `lessons-learned.md` / `<domain-spec or ui-ux-feature-components.md>`）で5分解決カードの5ステップ順序が一致する
- [ ] UIタスクでは `manual-test-result.md` の時刻と `screenshots/*.png` の `stat` が一致する
- [ ] `currentViolations` を合否、`baselineViolations` を監視値として分離記録している
- [ ] UIタスクで coverage が warning になった場合、`manual-test-checklist` 代替や `画面カバレッジマトリクス` 未記載などの理由を成果物へ明記している
- [ ] テスト再確認時に `pnpm test` を使わず、`pnpm --filter @repo/desktop exec vitest run ...` で非watch実行している
- [ ] `apps/desktop` 全量 `test:run` が `SIGTERM` の場合、失敗ログと分割実行結果の両方を記録している
- [ ] テンプレート本文の重複行（同一手順番号重複、同一検証コマンド重複）がないことを確認している

## 苦戦した箇所

- 何が難しかったか
- どの判断を誤ると再発するか
- 次回 5 分で確認すべき順序は何か

## 未タスク formalize 確認

- unassigned-task-detection に ID が残っているか
- 対応する unassigned-task 実ファイルがあるか
- 関連仕様と backlog に導線があるか
