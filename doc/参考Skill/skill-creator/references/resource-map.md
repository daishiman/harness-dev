# Progressive Disclosure リソースマップ

リソースは**必要な時のみ**読み込む。このファイルは全リソースの詳細な読み込み条件を定義する。

---

## agents/

| Agent                                                                                              | 読み込み条件                       | 責務                                     |
| -------------------------------------------------------------------------------------------------- | ---------------------------------- | ---------------------------------------- |
| **問題発見・ドメイン分析**                                                                         |                                    |                                          |
| [discover-problem.md](.claude/skills/skill-creator/agents/discover-problem.md)                     | collaborativeモード時（Phase 0-0） | 根本原因分析・問題定義                   |
| [model-domain.md](.claude/skills/skill-creator/agents/model-domain.md)                             | collaborativeモード時（Phase 0.5） | DDD/Clean Architectureドメインモデリング |
| **ユーザーインタラクション**                                                                       |                                    |                                          |
| [interview-user.md](.claude/skills/skill-creator/agents/interview-user.md)                         | collaborativeモード時（Phase 0-1〜0-8） | 要件ヒアリング・抽象度判定               |
| [recommend-integrations.md](.claude/skills/skill-creator/agents/recommend-integrations.md)         | Phase 0-3（外部連携）時            | 目的からAPI/サービスを推薦               |
| [select-resources.md](.claude/skills/skill-creator/agents/select-resources.md)                     | interview-result.json生成後        | 最適リソース自動選択                     |
| [interview-execution-mode.md](.claude/skills/skill-creator/agents/interview-execution-mode.md)     | orchestrateモード時                | 実行モード選択ヒアリング                 |
| [delegate-to-codex.md](.claude/skills/skill-creator/agents/delegate-to-codex.md)                   | Codex委譲時                        | Codexへのタスク委譲手順                  |
| [analyze-request.md](.claude/skills/skill-creator/agents/analyze-request.md)                       | createモード時                     | ユーザー要求の分析                       |
| [extract-purpose.md](.claude/skills/skill-creator/agents/extract-purpose.md)                       | 要求分析後                         | スキル目的の抽出                         |
| [define-boundary.md](.claude/skills/skill-creator/agents/define-boundary.md)                       | 目的定義後                         | スコープ・境界の定義                     |
| [define-trigger.md](.claude/skills/skill-creator/agents/define-trigger.md)                         | 目的定義後                         | 発動条件の定義                           |
| [select-anchors.md](.claude/skills/skill-creator/agents/select-anchors.md)                         | 目的定義後                         | 参考文献・アンカーの選定                 |
| [design-workflow.md](.claude/skills/skill-creator/agents/design-workflow.md)                       | ワークフロー設計時                 | Phase構成・フロー設計                    |
| [plan-structure.md](.claude/skills/skill-creator/agents/plan-structure.md)                         | 構造計画時                         | ディレクトリ・ファイル構成計画           |
| [design-update.md](.claude/skills/skill-creator/agents/design-update.md)                           | updateモード時                     | 既存スキル更新計画                       |
| [improve-prompt.md](.claude/skills/skill-creator/agents/improve-prompt.md)                         | improve-promptモード時             | プロンプト品質改善                       |
| [analyze-script-requirement.md](.claude/skills/skill-creator/agents/analyze-script-requirement.md) | スクリプト要件分析時               | スクリプト要件の抽出                     |
| [design-script.md](.claude/skills/skill-creator/agents/design-script.md)                           | スクリプト設計時                   | スクリプト設計仕様作成                   |
| [design-custom-script.md](.claude/skills/skill-creator/agents/design-custom-script.md)             | カスタムスクリプト時               | 定義済みタイプ外の独自スクリプト設計     |
| [generate-code.md](.claude/skills/skill-creator/agents/generate-code.md)                           | コード生成時                       | テンプレートからコード生成               |
| [design-variables.md](.claude/skills/skill-creator/agents/design-variables.md)                     | 変数設計時                         | テンプレート変数定義                     |
| [analyze-feedback.md](.claude/skills/skill-creator/agents/analyze-feedback.md)                     | 改善分析時                         | フィードバックデータ解釈                 |
| [design-self-improvement.md](.claude/skills/skill-creator/agents/design-self-improvement.md)       | 改善計画時                         | 改善提案の設計                           |
| [save-patterns.md](.claude/skills/skill-creator/agents/save-patterns.md)                           | パターン保存時                     | patterns.mdへのパターン記録              |
| **クロススキル依存関係・外部CLI**                                                                  |                                    |                                          |
| [resolve-skill-dependencies.md](.claude/skills/skill-creator/agents/resolve-skill-dependencies.md) | skillDependencies存在時（Phase 2.5） | スキル間依存関係解決・相対パス計算       |
| [delegate-to-external-cli.md](.claude/skills/skill-creator/agents/delegate-to-external-cli.md)     | externalCliAgents存在時（Phase 4.5） | 外部CLIエージェント汎用委譲             |
| [design-multi-skill.md](.claude/skills/skill-creator/agents/design-multi-skill.md)                 | multiSkillPlan存在時（Phase 0.9）    | 複数スキル同時設計・依存関係グラフ       |
| **オーケストレーション**                                                                           |                                    |                                          |
| [design-orchestration.md](.claude/skills/skill-creator/agents/design-orchestration.md)             | オーケストレーション全体設計時     | ワークフロー構成設計                     |
| [design-skill-chain.md](.claude/skills/skill-creator/agents/design-skill-chain.md)                 | スキルチェーン設計時               | A→B→C連鎖実行設計                        |
| [design-parallel-execution.md](.claude/skills/skill-creator/agents/design-parallel-execution.md)   | 並列実行設計時                     | 同時実行・結果集約設計                   |
| [design-conditional-flow.md](.claude/skills/skill-creator/agents/design-conditional-flow.md)       | 条件分岐設計時                     | 条件による処理分岐設計                   |
| [design-scheduler.md](.claude/skills/skill-creator/agents/design-scheduler.md)                     | スケジューリング設計時             | cron/定期実行設計                        |
| [design-event-trigger.md](.claude/skills/skill-creator/agents/design-event-trigger.md)             | イベントトリガー設計時             | Webhook/ファイル監視設計                 |
| **ドキュメント生成**                                                                               |                                    |                                          |
| [generate-api-docs.md](.claude/skills/skill-creator/agents/generate-api-docs.md)                   | APIドキュメント生成時              | APIセットアップガイド生成                |
| [fetch-official-docs.md](.claude/skills/skill-creator/agents/fetch-official-docs.md)               | 公式ドキュメント参照時             | 最新公式情報の取得・解析                 |
| [generate-setup-guide.md](.claude/skills/skill-creator/agents/generate-setup-guide.md)             | セットアップガイド生成時           | 実行可能なガイド生成                     |

---

## references/

| Reference                                                                                                    | 読み込み条件                | 内容                                               |
| ------------------------------------------------------------------------------------------------------------ | --------------------------- | -------------------------------------------------- |
| [overview.md](.claude/skills/skill-creator/references/overview.md)                                           | 初回/概要確認時             | skill-creator全体概要                              |
| [core-principles.md](.claude/skills/skill-creator/references/core-principles.md)                             | 設計判断時                  | 設計原則・哲学                                     |
| **問題発見・ドメイン分析**                                                                                   |                             |                                                    |
| [problem-discovery-framework.md](.claude/skills/skill-creator/references/problem-discovery-framework.md)     | Phase 0-0（問題発見）時     | 根本原因分析・5 Whys・Problem-Solution Fit         |
| [domain-modeling-guide.md](.claude/skills/skill-creator/references/domain-modeling-guide.md)                 | Phase 0.5（ドメイン分析）時 | DDD戦略的設計・ユビキタス言語・Bounded Context     |
| [clean-architecture-for-skills.md](.claude/skills/skill-creator/references/clean-architecture-for-skills.md) | スキル設計・品質検証時      | Clean Architecture層分離・依存関係ルール・品質指標 |
| [interview-guide.md](.claude/skills/skill-creator/references/interview-guide.md)                             | collaborativeモード時       | ユーザーインタビュー手法                           |
| [goal-to-api-mapping.md](.claude/skills/skill-creator/references/goal-to-api-mapping.md)                     | Phase 0-3（API推薦）時      | 目的→API/サービスマッピング表                      |
| [abstraction-levels.md](.claude/skills/skill-creator/references/abstraction-levels.md)                       | 抽象度判定時                | L1-L3レベル詳細                                    |
| [execution-mode-guide.md](.claude/skills/skill-creator/references/execution-mode-guide.md)                   | orchestrateモード時         | モード選択フローチャート                           |
| [codex-best-practices.md](.claude/skills/skill-creator/references/codex-best-practices.md)                   | Codex利用時                 | Codex活用ベストプラクティス                        |
| [creation-process.md](.claude/skills/skill-creator/references/creation-process.md)                           | createモード時              | スキル作成プロセス詳細                             |
| [update-process.md](.claude/skills/skill-creator/references/update-process.md)                               | updateモード時              | スキル更新プロセス詳細                             |
| [script-types-catalog.md](.claude/skills/skill-creator/references/script-types-catalog.md)                   | スクリプトタイプ選択時      | スクリプトタイプ詳細カタログ                       |
| [script-llm-patterns.md](.claude/skills/skill-creator/references/script-llm-patterns.md)                     | 処理役割分担設計時          | スクリプト/LLMパターンガイド                       |
| [runtime-guide.md](.claude/skills/skill-creator/references/runtime-guide.md)                                 | ランタイム設定時            | node/python/bash別ガイド                           |
| [variable-template-guide.md](.claude/skills/skill-creator/references/variable-template-guide.md)             | 変数設計時                  | テンプレート構文ガイド                             |
| [api-integration-patterns.md](.claude/skills/skill-creator/references/api-integration-patterns.md)           | API系スクリプト時           | API統合パターン集                                  |
| [workflow-patterns.md](.claude/skills/skill-creator/references/workflow-patterns.md)                         | ワークフロー設計時          | 実行パターン・分岐                                 |
| [skill-structure.md](.claude/skills/skill-creator/references/skill-structure.md)                             | 構造計画時                  | ディレクトリ構造仕様                               |
| [naming-conventions.md](.claude/skills/skill-creator/references/naming-conventions.md)                       | ファイル命名時              | 命名規則・形式                                     |
| [output-patterns.md](.claude/skills/skill-creator/references/output-patterns.md)                             | 出力設計時                  | 出力形式・パターン                                 |
| [quality-standards.md](.claude/skills/skill-creator/references/quality-standards.md)                         | 品質検証時                  | 品質基準・チェック項目                             |
| [feedback-loop.md](.claude/skills/skill-creator/references/feedback-loop.md)                                 | フィードバック設計時        | フィードバックループ設計                           |
| [self-improvement-cycle.md](.claude/skills/skill-creator/references/self-improvement-cycle.md)               | 自己改善時                  | 改善サイクル詳細                                   |
| [patterns.md](.claude/skills/skill-creator/references/patterns.md)                                           | 成功/失敗パターン参照時     | 蓄積されたパターン集                               |
| [script-commands.md](.claude/skills/skill-creator/references/script-commands.md)                             | スクリプト実行時            | 全スクリプトの実行コマンド詳細                     |
| [library-management.md](.claude/skills/skill-creator/references/library-management.md)                       | 依存関係追加時              | PNPM依存関係管理ガイド                             |
| [resource-map.md](.claude/skills/skill-creator/references/resource-map.md)                                   | リソース詳細確認時          | このファイル（全リソースマップ）                   |
| **クロススキル依存関係・外部CLI**                                                                            |                             |                                                    |
| [cross-skill-reference-patterns.md](.claude/skills/skill-creator/references/cross-skill-reference-patterns.md) | skillDependencies設計時   | スキル間参照パターン集（read-only/execute/invoke/chain） |
| [external-cli-agents-guide.md](.claude/skills/skill-creator/references/external-cli-agents-guide.md)         | externalCliAgents設計時     | 外部CLIエージェント統合ガイド（Gemini/Codex/Aider） |
| **オーケストレーション**                                                                                     |                             |                                                    |
| [orchestration-guide.md](.claude/skills/skill-creator/references/orchestration-guide.md)                     | オーケストレーション設計時  | オーケストレーション全体ガイド                     |
| [skill-chain-patterns.md](.claude/skills/skill-creator/references/skill-chain-patterns.md)                   | スキルチェーン設計時        | チェーンパターン集                                 |
| [parallel-execution-guide.md](.claude/skills/skill-creator/references/parallel-execution-guide.md)           | 並列実行設計時              | 並列実行ベストプラクティス                         |
| [scheduler-guide.md](.claude/skills/skill-creator/references/scheduler-guide.md)                             | スケジューリング設計時      | cron/スケジューラー設定ガイド                      |
| [event-trigger-guide.md](.claude/skills/skill-creator/references/event-trigger-guide.md)                     | イベントトリガー設計時      | Webhook/ファイル監視設定ガイド                     |
| **ドキュメント生成**                                                                                         |                             |                                                    |
| [api-docs-standards.md](.claude/skills/skill-creator/references/api-docs-standards.md)                       | APIドキュメント生成時       | ドキュメント品質基準・必須要素                     |
| [official-docs-registry.md](.claude/skills/skill-creator/references/official-docs-registry.md)               | 公式ドキュメント参照時      | 主要APIの公式ドキュメントURL                       |
| **統合・品質管理**                                                                                           |                             |                                                    |
| [integration-patterns.md](.claude/skills/skill-creator/references/integration-patterns.md)                   | 統合設計時                  | 統合パターン選択ガイド（インデックス）             |
| [integration-patterns-ipc.md](.claude/skills/skill-creator/references/integration-patterns-ipc.md)           | Electron IPC設計時          | Electron IPC契約定義・検証チェックリスト           |
| [integration-patterns-rest.md](.claude/skills/skill-creator/references/integration-patterns-rest.md)         | REST API設計時              | REST API契約定義・OpenAPI・エラーハンドリング      |
| [integration-patterns-graphql.md](.claude/skills/skill-creator/references/integration-patterns-graphql.md)   | GraphQL設計時               | GraphQL SDL定義・Resolver設計・N+1対策             |
| [integration-patterns-webhook.md](.claude/skills/skill-creator/references/integration-patterns-webhook.md)   | Webhook設計時               | Webhook契約定義・署名検証・リトライ戦略            |
| [phase-completion-checklist.md](.claude/skills/skill-creator/references/phase-completion-checklist.md)       | Phase完了確認時             | Phase完了チェックリスト                            |

---

## 成果物の明確化

各モードで期待される最終成果物を明確化する。

### createモード

| Phase   | 成果物                                          | 説明                               |
| ------- | ----------------------------------------------- | ---------------------------------- |
| Phase 0 | `interview-result.json`                         | ユーザー要件のヒアリング結果       |
| Phase 1 | `purpose.json`, `boundary.json`, `trigger.json` | スキルの目的・境界・発動条件定義   |
| Phase 2 | `structure-plan.json`, `workflow.json`          | ディレクトリ構造・ワークフロー設計 |
| Phase 3 | `scripts/`, `agents/`                           | スクリプト・エージェント実装       |
| Phase 4 | `SKILL.md`, `references/`                       | ドキュメント・リファレンス生成     |
| Phase 5 | 検証済みスキル                                  | 全体検証・品質確認完了             |

### updateモード

| Phase   | 成果物             | 説明                           |
| ------- | ------------------ | ------------------------------ |
| Phase 0 | 対象スキル特定     | 更新対象の既存スキル選定       |
| Phase 1 | `update-plan.json` | 更新計画（変更内容・影響範囲） |
| Phase 2 | 更新済みファイル   | 計画に基づく変更適用           |
| Phase 3 | 検証済み更新       | 回帰テスト・動作確認完了       |

### improve-promptモード

| Phase   | 成果物                    | 説明                     |
| ------- | ------------------------- | ------------------------ |
| Phase 0 | `prompt-analysis.json`    | 対象プロンプトの品質分析 |
| Phase 1 | `prompt-improvement.json` | 改善提案・最適化計画     |
| Phase 2 | 改善済みプロンプト        | 最適化適用後のプロンプト |
| Phase 3 | 効果検証結果              | Before/After比較・評価   |

### 統合契約パターン

モード間・Phase間の統合は以下のパターンに従う。

| 統合ポイント          | 契約パターン    | 参照                                                                                                   |
| --------------------- | --------------- | ------------------------------------------------------------------------------------------------------ |
| Phase間データ受け渡し | JSON Schema検証 | [schemas/](.claude/skills/skill-creator/schemas/)                                                      |
| スキル間連携          | 統合パターン集  | [integration-patterns.md](.claude/skills/skill-creator/references/integration-patterns.md)             |
| 完了判定              | チェックリスト  | [phase-completion-checklist.md](.claude/skills/skill-creator/references/phase-completion-checklist.md) |
| エラー伝播            | 統一エラー形式  | [execution-result.json](.claude/skills/skill-creator/schemas/execution-result.json)                    |

---

## scripts/

すべてのスクリプトは決定論的処理（100%精度）。共通ユーティリティは `utils.js` に集約。

| カテゴリ                 | スクリプト                                                                                  | 責務                                                |
| ------------------------ | ------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **共通**                 | [utils.js](.claude/skills/skill-creator/scripts/utils.js)                                   | EXIT_CODES, getArg, resolvePath, parseFrontmatter等 |
| モード判定・初期化       | [detect_mode.js](.claude/skills/skill-creator/scripts/detect_mode.js)                       | モード自動判定                                      |
|                          | [detect_runtime.js](.claude/skills/skill-creator/scripts/detect_runtime.js)                 | ランタイム判定                                      |
|                          | [init_skill.js](.claude/skills/skill-creator/scripts/init_skill.js)                         | スキル初期化・package.json生成                      |
| 生成系                   | [generate_skill_md.js](.claude/skills/skill-creator/scripts/generate_skill_md.js)           | SKILL.md生成                                        |
|                          | [generate_agent.js](.claude/skills/skill-creator/scripts/generate_agent.js)                 | エージェント生成                                    |
|                          | [generate_script.js](.claude/skills/skill-creator/scripts/generate_script.js)               | スクリプト生成                                      |
|                          | [generate_dynamic_code.js](.claude/skills/skill-creator/scripts/generate_dynamic_code.js)   | 動的コード生成                                      |
| 検証系                   | [validate_all.js](.claude/skills/skill-creator/scripts/validate_all.js)                     | 全体検証                                            |
|                          | [validate_structure.js](.claude/skills/skill-creator/scripts/validate_structure.js)         | 構造検証                                            |
|                          | [validate_links.js](.claude/skills/skill-creator/scripts/validate_links.js)                 | リンク検証                                          |
|                          | [validate_schema.js](.claude/skills/skill-creator/scripts/validate_schema.js)               | スキーマ検証                                        |
|                          | [validate_workflow.js](.claude/skills/skill-creator/scripts/validate_workflow.js)           | ワークフロー検証                                    |
|                          | [validate_plan.js](.claude/skills/skill-creator/scripts/validate_plan.js)                   | プラン検証                                          |
|                          | [quick_validate.js](.claude/skills/skill-creator/scripts/quick_validate.js)                 | 簡易検証                                            |
| 更新・分析               | [analyze_prompt.js](.claude/skills/skill-creator/scripts/analyze_prompt.js)                 | プロンプト分析                                      |
|                          | [apply_updates.js](.claude/skills/skill-creator/scripts/apply_updates.js)                   | 更新適用                                            |
|                          | [update_skill_list.js](.claude/skills/skill-creator/scripts/update_skill_list.js)           | スキルリスト更新                                    |
| Codex連携                | [check_prerequisites.js](.claude/skills/skill-creator/scripts/check_prerequisites.js)       | 前提条件確認                                        |
|                          | [assign_codex.js](.claude/skills/skill-creator/scripts/assign_codex.js)                     | Codex割当                                           |
| 自己改善                 | [log_usage.js](.claude/skills/skill-creator/scripts/log_usage.js)                           | 使用ログ記録                                        |
|                          | [collect_feedback.js](.claude/skills/skill-creator/scripts/collect_feedback.js)             | フィードバック収集                                  |
|                          | [apply_self_improvement.js](.claude/skills/skill-creator/scripts/apply_self_improvement.js) | 自己改善適用                                        |
| 依存関係                 | [install_deps.js](.claude/skills/skill-creator/scripts/install_deps.js)                     | 依存関係インストール                                |
|                          | [add_dependency.js](.claude/skills/skill-creator/scripts/add_dependency.js)                 | 依存関係追加                                        |
| **オーケストレーション** | [execute_chain.js](.claude/skills/skill-creator/scripts/execute_chain.js)                   | スキルチェーン実行                                  |
|                          | [execute_parallel.js](.claude/skills/skill-creator/scripts/execute_parallel.js)             | 並列スキル実行・結果集約                            |
|                          | [validate_orchestration.js](.claude/skills/skill-creator/scripts/validate_orchestration.js) | オーケストレーション定義検証                        |

---

## assets/

### テンプレート（基本）

| Asset                                                                                | 読み込み条件                 | 用途                             |
| ------------------------------------------------------------------------------------ | ---------------------------- | -------------------------------- |
| [skill-template.md](.claude/skills/skill-creator/assets/skill-template.md)           | SKILL.md生成時               | 新規スキルのSKILL.mdテンプレート |
| [agent-template.md](.claude/skills/skill-creator/assets/agent-template.md)           | エージェント生成時           | Task仕様書形式テンプレート       |
| [agent-task-template.md](.claude/skills/skill-creator/assets/agent-task-template.md) | タスク特化エージェント生成時 | タスク実行用エージェント         |
| [system-prompt-template.md](.claude/skills/skill-creator/assets/system-prompt-template.md) | LLM System Prompt生成時 | LLM外部呼び出し用System Promptテンプレート |
| [phase12-action-bridge-template.md](.claude/skills/skill-creator/assets/phase12-action-bridge-template.md) | Phase 12再監査後 | 監査結果を次アクションへ変換する導線テンプレート |
| [phase12-system-spec-retrospective-template.md](.claude/skills/skill-creator/assets/phase12-system-spec-retrospective-template.md) | Phase 12 Step 2（仕様更新）時 | 実装内容・苦戦箇所・再利用手順を仕様書別 SubAgent で同期するテンプレート。標準5仕様書（interfaces/api-ipc/security/task/lessons）/ UI機能6+α仕様書（`ui-ux-components` / `ui-ux-feature-components` / `arch-ui-components` / `arch-state-management` / `task-workflow` / `lessons` + `ui-ux-navigation` などの domain spec）/ onboarding overlay + Settings rerun profile（`workflow-onboarding-wizard-alignment`、follow-up backlog 本文の current contract 再同期を含む）/ preview-search cross-cutting 仕様（`ui-ux-search-panel` / `ui-ux-design-system` / `error-handling` / `architecture-implementation-patterns`）/ light theme shared color migration の `spec_created` profile（`ui-ux-settings` / `ui-ux-search-panel` / `ui-ux-portal-patterns` / `rag-desktop-state` / `api-ipc-auth` / `api-ipc-system` / `architecture-auth-security` / `security-*`）/ docs-only parent workflow sweep profile（pointer / index / interfaces / capture / mirror + representative visual re-audit + skill-creator feedback）/ 2workflow同時監査（spec_created + completed）に対応し、preview preflight、loopback static serve fallback、未タスク配置3分類（未実施/完了済みUT/legacy）、`target-file` 境界（未実施UTのみ）、`phase-12-documentation.md` の `completed` + Task 12-1〜12-5 二重突合、workflow 本文 `phase-1..11` stale guard、`SIGTERM` 時の分割回帰記録、Phase 4（契約テスト）/ Phase 6（回帰テスト）の責務境界監査、public preload method / shared export 追加時の Step 2 必須判定、新規未タスク 0 件時の `docs/30-workflows/unassigned-task/` 追加作成なし明記を含む |
| [phase12-spec-sync-subagent-template.md](.claude/skills/skill-creator/assets/phase12-spec-sync-subagent-template.md) | Phase 12仕様同期時 | SubAgent分担を標準化するテンプレート。仕様書別SubAgent実行ログ（実装内容/苦戦箇所/検証証跡）を必須化し、UI証跡（再撮影 + TCカバレッジ）、preview preflight、loopback static serve fallback、未タスク配置3分類、`target-file` 境界確認、global `unassigned-task/` の current/baseline 二層報告、`phase-12-documentation.md` ステータス同期、workflow 本文 `phase-1..11` stale guard、UIドメイン固有正本（例: `ui-ux-navigation.md`）の追加 SubAgent、docs-only parent workflow 用 `SubAgent-P1..P5`、onboarding overlay / Settings rerun 用 canonical docs 7点と follow-up 本文 resweep、`SIGTERM` 発生時の全量ログ + 分割実行結果記録、design/spec_created 向け Phase 4/6 テスト責務分離監査に対応し、既存 IPC 再利用時の public preload / shared export 判定と、新規未タスク 0 件時の指定ディレクトリ追加作成なし記録も扱う |

### テンプレート（ランタイム別）

| Asset                                                                        | 読み込み条件       | 用途                         |
| ---------------------------------------------------------------------------- | ------------------ | ---------------------------- |
| [base-node.js](.claude/skills/skill-creator/assets/base-node.js)             | runtime=node時     | Node.jsベーステンプレート    |
| [base-python.py](.claude/skills/skill-creator/assets/base-python.py)         | runtime=python時   | Pythonベーステンプレート     |
| [base-bash.sh](.claude/skills/skill-creator/assets/base-bash.sh)             | runtime=bash時     | Bashベーステンプレート       |
| [base-typescript.ts](.claude/skills/skill-creator/assets/base-typescript.ts) | runtime=bun/deno時 | TypeScriptベーステンプレート |

### テンプレート（機能別）

| Asset                                                                                            | 読み込み条件           | 用途                   |
| ------------------------------------------------------------------------------------------------ | ---------------------- | ---------------------- |
| [script-generator-template.js](.claude/skills/skill-creator/assets/script-generator-template.js) | 生成系スクリプト時     | コード生成スクリプト用 |
| [script-validator-template.js](.claude/skills/skill-creator/assets/script-validator-template.js) | 検証系スクリプト時     | バリデーション用       |
| [script-task-template.js](.claude/skills/skill-creator/assets/script-task-template.js)           | タスク実行スクリプト時 | 汎用タスク実行用       |

### テンプレート（フィードバック用）

| Asset                                                                            | 読み込み条件 | 用途                                     |
| -------------------------------------------------------------------------------- | ------------ | ---------------------------------------- |
| [logs-template.md](.claude/skills/skill-creator/assets/logs-template.md)         | スキル作成時 | LOGS.mdの初期テンプレート                |
| [evals-template.json](.claude/skills/skill-creator/assets/evals-template.json)   | スキル作成時 | EVALS.jsonの初期テンプレート             |
| [patterns-template.md](.claude/skills/skill-creator/assets/patterns-template.md) | スキル作成時 | references/patterns.mdの初期テンプレート |

### タイプ別テンプレート

スクリプトタイプ選択後、該当タイプのみ読み込む。

#### API関連

| Asset                                                                            | 読み込み条件        | 用途                         |
| -------------------------------------------------------------------------------- | ------------------- | ---------------------------- |
| [type-api-client.md](.claude/skills/skill-creator/assets/type-api-client.md)     | type=api-client時   | REST/GraphQL APIクライアント |
| [type-webhook.md](.claude/skills/skill-creator/assets/type-webhook.md)           | type=webhook時      | Webhook受信・送信            |
| [type-scraper.md](.claude/skills/skill-creator/assets/type-scraper.md)           | type=scraper時      | Webスクレイピング            |
| [type-notification.md](.claude/skills/skill-creator/assets/type-notification.md) | type=notification時 | 通知送信（Slack/Email等）    |

#### データ処理

| Asset                                                                                | 読み込み条件          | 用途             |
| ------------------------------------------------------------------------------------ | --------------------- | ---------------- |
| [type-parser.md](.claude/skills/skill-creator/assets/type-parser.md)                 | type=parser時         | データ解析・変換 |
| [type-transformer.md](.claude/skills/skill-creator/assets/type-transformer.md)       | type=transformer時    | データ変換・整形 |
| [type-aggregator.md](.claude/skills/skill-creator/assets/type-aggregator.md)         | type=aggregator時     | データ集約・統合 |
| [type-file-processor.md](.claude/skills/skill-creator/assets/type-file-processor.md) | type=file-processor時 | ファイル処理     |

#### ストレージ

| Asset                                                                    | 読み込み条件    | 用途           |
| ------------------------------------------------------------------------ | --------------- | -------------- |
| [type-database.md](.claude/skills/skill-creator/assets/type-database.md) | type=database時 | DB操作（CRUD） |
| [type-cache.md](.claude/skills/skill-creator/assets/type-cache.md)       | type=cache時    | キャッシュ操作 |
| [type-queue.md](.claude/skills/skill-creator/assets/type-queue.md)       | type=queue時    | キュー操作     |

#### 開発ツール

| Asset                                                                          | 読み込み条件       | 用途       |
| ------------------------------------------------------------------------------ | ------------------ | ---------- |
| [type-git-ops.md](.claude/skills/skill-creator/assets/type-git-ops.md)         | type=git-ops時     | Git操作    |
| [type-test-runner.md](.claude/skills/skill-creator/assets/type-test-runner.md) | type=test-runner時 | テスト実行 |
| [type-linter.md](.claude/skills/skill-creator/assets/type-linter.md)           | type=linter時      | 静的解析   |
| [type-formatter.md](.claude/skills/skill-creator/assets/type-formatter.md)     | type=formatter時   | コード整形 |
| [type-builder.md](.claude/skills/skill-creator/assets/type-builder.md)         | type=builder時     | ビルド処理 |

#### インフラ

| Asset                                                                    | 読み込み条件    | 用途             |
| ------------------------------------------------------------------------ | --------------- | ---------------- |
| [type-deployer.md](.claude/skills/skill-creator/assets/type-deployer.md) | type=deployer時 | デプロイ処理     |
| [type-docker.md](.claude/skills/skill-creator/assets/type-docker.md)     | type=docker時   | Docker操作       |
| [type-cloud.md](.claude/skills/skill-creator/assets/type-cloud.md)       | type=cloud時    | クラウドAPI操作  |
| [type-monitor.md](.claude/skills/skill-creator/assets/type-monitor.md)   | type=monitor時  | 監視・メトリクス |

#### 統合

| Asset                                                                        | 読み込み条件      | 用途               |
| ---------------------------------------------------------------------------- | ----------------- | ------------------ |
| [type-ai-tool.md](.claude/skills/skill-creator/assets/type-ai-tool.md)       | type=ai-tool時    | AI/LLM連携         |
| [type-mcp-bridge.md](.claude/skills/skill-creator/assets/type-mcp-bridge.md) | type=mcp-bridge時 | MCP統合            |
| [type-shell.md](.claude/skills/skill-creator/assets/type-shell.md)           | type=shell時      | シェルコマンド実行 |

#### 汎用・オーケストレーション

| Asset                                                                              | 読み込み条件         | 用途                 |
| ---------------------------------------------------------------------------------- | -------------------- | -------------------- |
| [type-universal.md](.claude/skills/skill-creator/assets/type-universal.md)         | type=universal時     | 汎用スクリプト       |
| [type-orchestration.md](.claude/skills/skill-creator/assets/type-orchestration.md) | type=orchestration時 | オーケストレーション |

### テンプレート（オーケストレーション実行）

| Asset                                                                                | 読み込み条件           | 用途                            |
| ------------------------------------------------------------------------------------ | ---------------------- | ------------------------------- |
| [chain-template.yaml](.claude/skills/skill-creator/assets/chain-template.yaml)       | スキルチェーン定義時   | YAML形式チェーンテンプレート    |
| [parallel-template.yaml](.claude/skills/skill-creator/assets/parallel-template.yaml) | 並列実行定義時         | YAML形式並列実行テンプレート    |
| [scheduler-cron.sh](.claude/skills/skill-creator/assets/scheduler-cron.sh)           | cronスケジュール設定時 | cron設定用Bashテンプレート      |
| [trigger-watcher.js](.claude/skills/skill-creator/assets/trigger-watcher.js)         | ファイル監視トリガー時 | Node.jsファイル監視テンプレート |

### テンプレート（ドキュメント生成）

| Asset                                                                                  | 読み込み条件             | 用途                               |
| -------------------------------------------------------------------------------------- | ------------------------ | ---------------------------------- |
| [setup-guide-template.md](.claude/skills/skill-creator/assets/setup-guide-template.md) | セットアップガイド生成時 | 汎用セットアップガイドテンプレート |

---

## schemas/

JSON Schema形式。[validate_schema.js](.claude/skills/skill-creator/scripts/validate_schema.js)で検証。

### コア定義

| Schema                                                                              | 読み込み条件       | 用途                   |
| ----------------------------------------------------------------------------------- | ------------------ | ---------------------- |
| [mode.json](.claude/skills/skill-creator/schemas/mode.json)                         | モード判定時       | モード判定結果の検証   |
| [agent-definition.json](.claude/skills/skill-creator/schemas/agent-definition.json) | エージェント生成時 | エージェント定義の検証 |
| [workflow.json](.claude/skills/skill-creator/schemas/workflow.json)                 | ワークフロー設計時 | ワークフロー構造の検証 |

### createモード

| Schema                                                                          | 読み込み条件   | 用途                   |
| ------------------------------------------------------------------------------- | -------------- | ---------------------- |
| [purpose.json](.claude/skills/skill-creator/schemas/purpose.json)               | 目的抽出後     | スキル目的の検証       |
| [boundary.json](.claude/skills/skill-creator/schemas/boundary.json)             | 境界定義後     | スコープ定義の検証     |
| [trigger.json](.claude/skills/skill-creator/schemas/trigger.json)               | トリガー定義後 | 発動条件の検証         |
| [anchors.json](.claude/skills/skill-creator/schemas/anchors.json)               | アンカー選定後 | 参照文献の検証         |
| [structure-plan.json](.claude/skills/skill-creator/schemas/structure-plan.json) | 構造計画後     | ディレクトリ構成の検証 |

### collaborativeモード

| Schema                                                                                  | 読み込み条件            | 用途                         |
| --------------------------------------------------------------------------------------- | ----------------------- | ---------------------------- |
| [problem-definition.json](.claude/skills/skill-creator/schemas/problem-definition.json) | Phase 0-0（問題発見）後 | 問題定義・根本原因分析の検証 |
| [domain-model.json](.claude/skills/skill-creator/schemas/domain-model.json)             | Phase 0.5（ドメイン）後 | ドメインモデルの検証         |
| [interview-result.json](.claude/skills/skill-creator/schemas/interview-result.json)     | インタビュー完了後      | ヒアリング結果の検証         |
| [resource-selection.json](.claude/skills/skill-creator/schemas/resource-selection.json) | リソース選択後          | 選定リソースリストの検証     |

### updateモード

| Schema                                                                    | 読み込み条件 | 用途           |
| ------------------------------------------------------------------------- | ------------ | -------------- |
| [update-plan.json](.claude/skills/skill-creator/schemas/update-plan.json) | 更新計画後   | 更新内容の検証 |

### improve-promptモード

| Schema                                                                                  | 読み込み条件     | 用途           |
| --------------------------------------------------------------------------------------- | ---------------- | -------------- |
| [prompt-analysis.json](.claude/skills/skill-creator/schemas/prompt-analysis.json)       | プロンプト分析後 | 分析結果の検証 |
| [prompt-improvement.json](.claude/skills/skill-creator/schemas/prompt-improvement.json) | 改善計画後       | 改善提案の検証 |

### orchestrateモード

| Schema                                                                          | 読み込み条件     | 用途             |
| ------------------------------------------------------------------------------- | ---------------- | ---------------- |
| [execution-mode.json](.claude/skills/skill-creator/schemas/execution-mode.json) | 実行モード選択時 | モード選択の検証 |
| [codex-task.json](.claude/skills/skill-creator/schemas/codex-task.json)         | Codex委譲前      | タスク定義の検証 |
| [codex-result.json](.claude/skills/skill-creator/schemas/codex-result.json)     | Codex実行後      | 結果の検証       |

### スクリプト生成

| Schema                                                                                      | 読み込み条件             | 用途                   |
| ------------------------------------------------------------------------------------------- | ------------------------ | ---------------------- |
| [script-definition.json](.claude/skills/skill-creator/schemas/script-definition.json)       | スクリプト設計時         | 定義の検証             |
| [script-type.json](.claude/skills/skill-creator/schemas/script-type.json)                   | タイプ選択時             | 定義済みタイプの検証   |
| [custom-script-design.json](.claude/skills/skill-creator/schemas/custom-script-design.json) | カスタムスクリプト設計時 | カスタム設計の検証     |
| [runtime-config.json](.claude/skills/skill-creator/schemas/runtime-config.json)             | ランタイム設定時         | 実行環境の検証         |
| [variable-definition.json](.claude/skills/skill-creator/schemas/variable-definition.json)   | 変数設計時               | テンプレート変数の検証 |
| [dependency-spec.json](.claude/skills/skill-creator/schemas/dependency-spec.json)           | 依存関係定義時           | パッケージ依存の検証   |
| [environment-spec.json](.claude/skills/skill-creator/schemas/environment-spec.json)         | 環境設定時               | 環境変数の検証         |

### 実行・フィードバック

| Schema                                                                              | 読み込み条件         | 用途       |
| ----------------------------------------------------------------------------------- | -------------------- | ---------- |
| [execution-result.json](.claude/skills/skill-creator/schemas/execution-result.json) | 実行完了後           | 結果の検証 |
| [feedback-record.json](.claude/skills/skill-creator/schemas/feedback-record.json)   | フィードバック記録時 | ログの検証 |

### オーケストレーション

| Schema                                                                                  | 読み込み条件                   | 用途               |
| --------------------------------------------------------------------------------------- | ------------------------------ | ------------------ |
| [orchestration.json](.claude/skills/skill-creator/schemas/orchestration.json)           | オーケストレーション全体設計時 | マスター定義の検証 |
| [skill-chain.json](.claude/skills/skill-creator/schemas/skill-chain.json)               | スキルチェーン設計時           | チェーン定義の検証 |
| [parallel-execution.json](.claude/skills/skill-creator/schemas/parallel-execution.json) | 並列実行設計時                 | 並列定義の検証     |
| [conditional-flow.json](.claude/skills/skill-creator/schemas/conditional-flow.json)     | 条件分岐設計時                 | 条件定義の検証     |
| [schedule.json](.claude/skills/skill-creator/schemas/schedule.json)                     | スケジュール設計時             | cron定義の検証     |
| [event-trigger.json](.claude/skills/skill-creator/schemas/event-trigger.json)           | イベントトリガー設計時         | トリガー定義の検証 |

### クロススキル依存関係

| Schema                                                                                          | 読み込み条件                 | 用途                       |
| ----------------------------------------------------------------------------------------------- | ---------------------------- | -------------------------- |
| [skill-dependency-graph.json](.claude/skills/skill-creator/schemas/skill-dependency-graph.json) | skillDependencies存在時         | 単一スキル依存関係グラフ・DAG検証 |
| [multi-skill-graph.json](.claude/skills/skill-creator/schemas/multi-skill-graph.json)           | multiSkillPlan存在時            | マルチスキル設計グラフ・作成順序  |
| [external-cli-result.json](.claude/skills/skill-creator/schemas/external-cli-result.json)       | externalCliAgents実行後         | 外部CLIエージェント実行結果スキーマ |

### ドキュメント生成

| Schema                                                                                | 読み込み条件             | 用途                   |
| ------------------------------------------------------------------------------------- | ------------------------ | ---------------------- |
| [api-documentation.json](.claude/skills/skill-creator/schemas/api-documentation.json) | APIドキュメント生成時    | ドキュメント構造の検証 |
| [setup-guide.json](.claude/skills/skill-creator/schemas/setup-guide.json)             | セットアップガイド生成時 | ガイド構造の検証       |
