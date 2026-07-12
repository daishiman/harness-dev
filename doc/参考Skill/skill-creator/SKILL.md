---
name: skill-creator
description: |
  スキルを作成・更新・プロンプト改善するためのメタスキル。
  **最初のアクションは必ず AskUserQuestion**（インタビュー深度確認）。
  **collaborative**モードでユーザーと対話しながら共創し、抽象的なアイデアから具体的な実装まで柔軟に対応する。
  **orchestrate**モードでタスクの実行エンジン（Claude Code / Codex / 連携）を選択。

  Anchors（主要3件・全7件は references/anchors.md 参照）:
  • Continuous Delivery (Jez Humble) / 適用: 自動化パイプライン / 目的: 決定論的実行
  • The Lean Startup (Eric Ries) / 適用: Build-Measure-Learn / 目的: 反復改善
  • Domain-Driven Design (Eric Evans) / 適用: 戦略的設計・ユビキタス言語・Bounded Context / 目的: ドメイン構造の明確化

  Trigger:
  新規スキルの作成、既存スキルの更新、プロンプト改善を行う場合に使用。
  スキル作成, スキル更新, プロンプト改善, skill creation, skill update, improve prompt,
  Codexに任せて, assign codex, 実行モード選択, IPC Bridge統一, safeInvoke/safeOn,
  Preload API標準化, contextBridge, Electron IPC pattern
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
  - AskUserQuestion
---

# Skill Creator

スキルを作成・更新・プロンプト改善するためのメタスキル。

## 変更履歴

| Version | Date | Changes |
| --- | --- | --- |
| v2026.05.11-task15-e2e-mock-testid-drift | 2026-05-11 | task-15 admin dashboard and members 実装サイクル feedback を反映。`references/patterns-pitfall-testing-ui.md` に (1) **e2e mock の二重実装は state drift を生む** (standalone mock を single source of truth とし HTTP control endpoint で一本化、Server Component `fetch()` は `page.route()` で捕捉できない事実を明記)、(2) **page-object と実装 testid の drift 防止** (`data-testid` 命名は機能 prefix + kebab、page-object と実装の同 commit 配備、`scripts/verify-testid-parity.mjs` CI gate) の 2 entry を追加。 |
| v2026.05.01-phase12-skill-feedback-sync | 2026-05-01 | Phase 12 `skill-feedback-report.md` の改善提案を既存 skill reference へ最小反映する運用を追加。ADR / topology drift task では重複候補検索、base case 別差分マトリクス、doc-only grep、NON_VISUAL evidence を優先して反映する。 |

> Anchors の詳細（全 7 件）は [references/anchors.md](references/anchors.md) を参照（description には主要 3 件のみ記載）。

## 必須：最初の実行ステップ

**このスキルを呼ばれたら、最初のアクションは必ず `AskUserQuestion` である。**

1. インタビュー深度を確認する（quick / standard / detailed）
2. 深度が確定したら `agents/discover-problem.md` を読み込み Phase 0-0 を開始する
3. `problem-definition.json` が存在しない場合は AskUserQuestion で問題定義を収集する

ユーザーの回答なしに生成を開始してはならない。create / update / improve-prompt モードも、最初に深度確認の質問を行ってから着手する。

**例外（読み取り監査のみ）**: 既存スキルの作成・更新・改善生成を行わず、ユーザーが対象範囲を具体指定し、かつ SubAgent などへ read-only audit を依頼するだけの場合は AskUserQuestion を省略してよい。監査結果を受けて実ファイルを編集する段階では、ユーザー指定済みの範囲に限定し、create / update / improve-prompt の対話フローを開始した扱いにしない。

## 設計原則

| 原則                    | 説明                                       |
| ----------------------- | ------------------------------------------ |
| **Problem First**       | 機能の前に本質的な問題を特定する           |
| **Collaborative First** | ユーザーとの対話を通じて要件を明確化       |
| Domain-Driven Design    | ドメイン構造を明確化し高精度な設計を導く   |
| Clean Architecture      | 層分離と依存関係ルールで変更に強い構造     |
| Script First            | 決定論的処理はスクリプトで実行（100%精度） |
| Progressive Disclosure  | 必要な時に必要なリソースのみ読み込み       |
| `.claude` Canonical     | Skill updates target `.claude/skills/...`; `.agents/skills/...` is mirror/runtime compatibility and must be diff-validated when present |

## クイックスタート

| モード            | 用途                             | 開始方法                                        |
| ----------------- | -------------------------------- | ----------------------------------------------- |
| **collaborative** | ユーザー対話型スキル共創（推奨） | AskUserQuestionでインタビュー開始               |
| **orchestrate**   | 実行エンジン選択                 | AskUserQuestionでヒアリング開始                 |
| create            | 要件が明確な場合の新規作成       | `scripts/detect_mode.js --request "..."`        |
| update            | 既存スキル更新                   | `scripts/detect_mode.js --skill-path <path>`    |
| improve-prompt    | プロンプト改善                   | `scripts/analyze_prompt.js --skill-path <path>` |

## ワークフロー概要（Collaborative）

```
Phase 0-0: 問題発見 → problem-definition.json
Phase 0.5: ドメインモデリング → domain-model.json
Phase 0-1〜0-8: インタビュー → interview-result.json
[分岐] multiSkillPlan: Phase 0.9 design-multi-skill → multi-skill-graph.json
リソース選択: select-resources.md → resource-selection.json
Phase 1: 要求分析 → Phase 2: 設計
[条件] skillDependencies: Phase 2.5 resolve-skill-dependencies → skill-dependency-graph.json
Phase 3: 構造計画 → Phase 4: 生成
[条件] externalCliAgents: Phase 4.5 delegate-to-external-cli → external-cli-result.json
Phase 5: レビュー (quick-validate) → Phase 6: 検証 (validate-all)
```

Runtime ワークフロー（IPC 駆動: plan → review → execute → verify → improve → reverify → handoff）の状態遷移・IPC チャネル一覧・submitUserInput セマンティクス・verify→improve 閉ループ・SDK 正規化・Session Persistence などの詳細は **[references/runtime-workflow.md](references/runtime-workflow.md)** を参照。

設計タスク（Phase 1-3 中心）向けの並列 SubAgent 戦略・Phase 12 再監査ショートカット・P43 対策・ベストプラクティスは **[references/orchestration-design-tasks.md](references/orchestration-design-tasks.md)** を参照。

## リソース一覧

| カテゴリ | 詳細参照 |
| -------- | -------- |
| agents/ | [references/resource-map.md#agents](references/resource-map.md) |
| references/ | [references/resource-map.md#references](references/resource-map.md) |
| scripts/ | [references/resource-map.md#scripts](references/resource-map.md) |
| assets/ | [references/resource-map.md#assets](references/resource-map.md) |
| schemas/ | [references/resource-map.md#schemas](references/resource-map.md) |

主要 entrypoint references（SKILL.md 200 行制約のため本体に含めず references/ に退避）:

| ファイル | 役割 |
| -------- | ---- |
| [references/anchors.md](references/anchors.md) | 全 7 件の設計アンカー（description には主要 3 件のみ） |
| [references/runtime-workflow.md](references/runtime-workflow.md) | Runtime ワークフロー状態遷移・IPC チャネル・submitUserInput・verify→improve ループ・SDK 正規化・Session Persistence |
| [references/orchestration-design-tasks.md](references/orchestration-design-tasks.md) | 設計タスク向けオーケストレーション・並列 SubAgent 戦略・Phase 12 再監査・P43 対策・ベストプラクティス |
| [references/fixture-conventions.md](references/fixture-conventions.md) | テストフィクスチャ `.fixture` 拡張子規約・loadFixture ヘルパー仕様（Codex / Claude Code skill discovery 排除のため） |
| [references/resource-map.md](references/resource-map.md) | agents / references / scripts / assets / schemas の全リソースカタログ |

## 主要エントリポイント（agents）

| 用途 | リソース |
| ---- | -------- |
| 問題発見 | agents/discover-problem.md |
| ドメインモデリング | agents/model-domain.md |
| インタビュー | agents/interview-user.md |
| リソース選択 | agents/select-resources.md |
| 要求分析 | agents/analyze-request.md |
| スクリプト生成 | agents/design-script.md |
| オーケストレーション | agents/design-orchestration.md |
| クロススキル依存関係解決 | agents/resolve-skill-dependencies.md |
| 外部CLIエージェント委譲 | agents/delegate-to-external-cli.md |
| マルチスキル同時設計 | agents/design-multi-skill.md |
| フィードバック記録 | scripts/log_usage.js |
| Phase 12 再監査同期 | assets/phase12-system-spec-retrospective-template.md |

## 機能別ガイド（references/）

| 機能 | 参照先 |
| ---- | ------ |
| 問題発見フレームワーク | references/problem-discovery-framework.md |
| ドメインモデリング | references/domain-modeling-guide.md |
| Clean Architecture | references/clean-architecture-for-skills.md |
| プロンプト生成ポリシー | references/prompt-generation-policy.md |
| スクリプト/LLM分担 | references/script-llm-patterns.md |
| クロススキル参照パターン | references/cross-skill-reference-patterns.md |
| skill-ledger 規約 | references/skill-ledger-conventions.md |
| 外部CLIエージェント統合 | references/external-cli-agents-guide.md |
| スクリプト生成 | references/script-types-catalog.md |
| ワークフローパターン | references/workflow-patterns.md |
| オーケストレーション | references/orchestration-guide.md |
| 実行モード選択 | references/execution-mode-guide.md |
| ドキュメント生成 | references/api-docs-standards.md |
| Phase 12 spec-to-skill sync | references/update-process.md, assets/phase12-task-spec-recheck-template.md, assets/phase12-system-spec-retrospective-template.md |
| Phase 12 再監査 | references/update-process.md, references/output-patterns.md, references/patterns-success-*.md, references/patterns-failure-*.md, references/patterns-pitfall-*.md |
| 自己改善サイクル | references/self-improvement-cycle.md |
| ライブラリ管理 | references/library-management.md |

その他カテゴリ別（基礎設計 / ヒアリング / 統合 / 実行運用）の追加リファレンスは [references/resource-map.md](references/resource-map.md) を参照。

### 追加リファレンス（網羅インデックス）

- 基礎設計: [references/abstraction-levels.md](references/abstraction-levels.md), [references/core-principles.md](references/core-principles.md), [references/creation-process.md](references/creation-process.md), [references/skill-structure.md](references/skill-structure.md), [references/naming-conventions.md](references/naming-conventions.md), [references/quality-standards.md](references/quality-standards.md), [references/overview.md](references/overview.md), [references/phase-completion-checklist.md](references/phase-completion-checklist.md)
- ヒアリング・設計補助: [references/interview-guide.md](references/interview-guide.md), [references/goal-to-api-mapping.md](references/goal-to-api-mapping.md), [references/variable-template-guide.md](references/variable-template-guide.md), [references/event-trigger-guide.md](references/event-trigger-guide.md), [references/feedback-loop.md](references/feedback-loop.md)
- 実装・統合: [references/api-integration-patterns.md](references/api-integration-patterns.md), [references/integration-patterns.md](references/integration-patterns.md), [references/integration-patterns-rest.md](references/integration-patterns-rest.md), [references/integration-patterns-graphql.md](references/integration-patterns-graphql.md), [references/integration-patterns-webhook.md](references/integration-patterns-webhook.md), [references/integration-patterns-ipc.md](references/integration-patterns-ipc.md), [references/runtime-guide.md](references/runtime-guide.md), [references/script-commands.md](references/script-commands.md), [references/official-docs-registry.md](references/official-docs-registry.md)
- 実行・運用: [references/parallel-execution-guide.md](references/parallel-execution-guide.md), [references/scheduler-guide.md](references/scheduler-guide.md), [references/skill-chain-patterns.md](references/skill-chain-patterns.md), [references/codex-best-practices.md](references/codex-best-practices.md)
- パターン集: [references/patterns.md](references/patterns.md), [references/patterns-guideline-type.md](references/patterns-guideline-type.md), [references/patterns-success-ipc-auth.md](references/patterns-success-ipc-auth.md), [references/patterns-success-ipc-auth-b.md](references/patterns-success-ipc-auth-b.md), [references/patterns-success-skill-phase12.md](references/patterns-success-skill-phase12.md), [references/patterns-success-skill-phase12-b.md](references/patterns-success-skill-phase12-b.md), [references/patterns-success-phase12-advanced.md](references/patterns-success-phase12-advanced.md), [references/patterns-success-testing-security.md](references/patterns-success-testing-security.md), [references/patterns-failure-misc.md](references/patterns-failure-misc.md), [references/patterns-failure-phase12.md](references/patterns-failure-phase12.md), [references/patterns-pitfall-phase12.md](references/patterns-pitfall-phase12.md), [references/patterns-pitfall-testing-ui.md](references/patterns-pitfall-testing-ui.md)

## フィードバック（必須）

実行後は必ず記録：

```bash
node scripts/log_usage.js --result success --phase "Phase 4"
node scripts/log_usage.js --result failure --phase "Phase 3" --error "ValidationError"
```
