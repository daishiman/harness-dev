# Task仕様書：リソース選択

> **読み込み条件**: interview-result.json生成後、Phase 1開始前
> **相対パス**: `agents/select-resources.md`
> **Phase**: Pre-1（リソース選択）

## 1. メタ情報

| 項目     | 内容                           |
| -------- | ------------------------------ |
| 名前     | Resource Selector              |
| 専門領域 | 最適リソース選択・依存関係解決 |

---

## 2. プロフィール

### 2.1 背景

interview-result.jsonの内容から、スキル作成に必要な全リソース（agents, scripts, schemas, assets, references）を選択する。
全リソースから最適なものを漏れなく選定し、resource-selection.jsonとして出力する。

### 2.2 目的

ユーザー要件に基づき、以下を決定する：

1. 使用するエージェント（ワークフロー構成）
2. 使用するスクリプト（処理実行）
3. 使用するスキーマ（検証）
4. 使用するアセット（テンプレート）
5. 参照するリファレンス（設計指針）

### 2.3 責務

| 責務         | 成果物                  |
| ------------ | ----------------------- |
| リソース選択 | resource-selection.json |
| 依存関係解決 | 順序付きリソースリスト  |

---

## 3. 知識ベース

### 3.1 参考文献

| ドキュメント                       | 適用方法                      |
| ---------------------------------- | ----------------------------- |
| references/resource-map.md         | 全リソースの読み込み条件参照  |
| references/script-types-catalog.md | スクリプトタイプ→アセット対応 |
| references/workflow-patterns.md    | ワークフロー→エージェント対応 |

---

## 4. 実行仕様

### 4.1 選択マトリクス

#### 4.1.1 抽象度レベル → エージェント

| 抽象度 | 追加エージェント                            |
| ------ | ------------------------------------------- |
| L1     | extract-purpose, define-boundary (詳細分析) |
| L2     | extract-purpose (簡易分析)                  |
| L3     | 分析スキップ可能                            |

#### 4.1.2 機能タイプ → スクリプト・アセット

| 機能カテゴリ   | スクリプトタイプ                | 対応アセット                        |
| -------------- | ------------------------------- | ----------------------------------- |
| 外部API連携    | api-client, webhook             | type-api-client.md, type-webhook.md |
| データ処理     | parser, transformer, aggregator | type-parser.md, type-transformer.md, type-aggregator.md |
| ファイル操作   | file-processor                  | type-file-processor.md              |
| Git操作        | git-ops                         | type-git-ops.md                     |
| テスト         | test-runner                     | type-test-runner.md                 |
| 通知           | notification                    | type-notification.md                |
| DB操作         | database                        | type-database.md                    |
| キャッシュ     | cache                           | type-cache.md                       |
| AI連携         | ai-tool                         | type-ai-tool.md                     |
| MCP            | mcp-bridge                      | type-mcp-bridge.md                  |
| シェル         | shell                           | type-shell.md                       |
| デプロイ       | deployer                        | type-deployer.md                    |
| Docker         | docker                          | type-docker.md                      |
| クラウド       | cloud                           | type-cloud.md                       |
| 監視           | monitor                         | type-monitor.md                     |
| ビルド         | builder                         | type-builder.md                     |
| Lint           | linter                          | type-linter.md                      |
| Format         | formatter                       | type-formatter.md                   |
| スクレイピング | scraper                         | type-scraper.md                     |
| キュー         | queue                           | type-queue.md                       |
| 汎用           | universal                       | type-universal.md                   |

#### 4.1.3 外部連携 → エージェント・リファレンス

| 条件                 | 追加エージェント          | 追加リファレンス            |
| -------------------- | ------------------------- | --------------------------- |
| integrations[]あり   | recommend-integrations.md | goal-to-api-mapping.md      |
| REST API             | -                         | api-integration-patterns.md |
| 認証が必要           | -                         | api-docs-standards.md       |
| 公式ドキュメント必要 | -                         | official-docs-registry.md   |

#### 4.1.4 構成タイプ → 基本アセット

| 構成     | アセット                                                     |
| -------- | ------------------------------------------------------------ |
| simple   | skill-template.md                                            |
| standard | skill-template.md, agent-template.md                         |
| full     | skill-template.md, agent-template.md, agent-task-template.md |
| custom   | 上記 + カスタム設計                                          |

#### 4.1.4.1 LLM System Prompt生成 → 追加アセット

| 条件                              | 追加アセット                  |
| --------------------------------- | ----------------------------- |
| スキルがLLM System Promptを生成する | system-prompt-template.md     |
| スキルがLLM System Promptを生成しない | -（追加なし）               |

> `system-prompt-template.md` は、スキルがLLMを外部呼び出し（System Prompt経由）する場合にのみ選択する。
> skill-creator内部のTask仕様書には `agent-template.md` を使用する。

#### 4.1.5 スクリプト有無 → スキーマ・スクリプト

| 条件          | 追加スキーマ                                                  | 追加スクリプト                        |
| ------------- | ------------------------------------------------------------- | ------------------------------------- |
| scripts[]あり | script-definition.json, script-type.json, runtime-config.json | generate_script.js, detect_runtime.js |
| scripts[]なし | -                                                             | -                                     |

#### 4.1.6 オーケストレーション → リソース

| 条件         | 追加エージェント             | 追加スキーマ            | 追加アセット           |
| ------------ | ---------------------------- | ----------------------- | ---------------------- |
| チェーン     | design-skill-chain.md        | skill-chain.json        | chain-template.yaml    |
| 並列         | design-parallel-execution.md | parallel-execution.json | parallel-template.yaml |
| 条件分岐     | design-conditional-flow.md   | conditional-flow.json   | -                      |
| スケジュール | design-scheduler.md          | schedule.json           | scheduler-cron.sh      |
| イベント     | design-event-trigger.md      | event-trigger.json      | trigger-watcher.js     |

#### 4.1.7 クロススキル依存関係 → リソース

| 条件                        | 追加エージェント                | 追加スキーマ               | 追加リファレンス                     | 実行Phase |
| --------------------------- | ------------------------------- | -------------------------- | ------------------------------------ | --------- |
| skillDependencies.dependsOn有 | resolve-skill-dependencies.md | skill-dependency-graph.json | cross-skill-reference-patterns.md   | Phase 2.5（Phase 2の後、Phase 3の前） |
| skillDependencies.dependedBy有 | resolve-skill-dependencies.md | skill-dependency-graph.json | cross-skill-reference-patterns.md  | Phase 2.5（Phase 2の後、Phase 3の前） |
| multiSkillPlan有            | design-multi-skill.md（Phase 0.9で実行済み・記録用） | multi-skill-graph.json | cross-skill-reference-patterns.md   | Phase 0.9（インタビュー後、リソース選択の前） |

#### 4.1.8 外部CLIエージェント → リソース

| 条件                        | 追加エージェント                | 追加スキーマ               | 追加リファレンス                  | 実行Phase |
| --------------------------- | ------------------------------- | -------------------------- | --------------------------------- | --------- |
| externalCliAgents[]有       | delegate-to-external-cli.md     | external-cli-result.json   | external-cli-agents-guide.md      | Phase 4.5（スキル生成後、Phase 5の前） |
| agentName=codex             | delegate-to-codex.md（後方互換）| external-cli-result.json   | codex-best-practices.md           | Phase 4.5（スキル生成後、Phase 5の前） |

#### 4.1.9 ドキュメント → リソース

| 条件                      | 追加エージェント        | 追加スキーマ           | 追加アセット            | 追加リファレンス          |
| ------------------------- | ----------------------- | ---------------------- | ----------------------- | ------------------------- |
| needsApiGuide=true        | generate-api-docs.md    | api-documentation.json | setup-guide-template.md | api-docs-standards.md     |
| needsEnvGuide=true        | generate-setup-guide.md | setup-guide.json       | setup-guide-template.md | -                         |
| apiServices[]にサービス有 | fetch-official-docs.md  | -                      | -                       | official-docs-registry.md |

### 4.2 思考プロセス

| ステップ | アクション                                             | 担当 | 対応マトリクス |
| -------- | ------------------------------------------------------ | ---- | -------------- |
| 1        | interview-result.jsonを読み込む                        | LLM  | -              |
| 2        | 抽象度レベルから基本エージェントを選択                 | LLM  | 4.1.1          |
| 3        | 機能リストからスクリプトタイプ・アセットを選択         | LLM  | 4.1.2          |
| 4        | 外部連携からリファレンスを選択                         | LLM  | 4.1.3          |
| 5        | 構成タイプから基本アセットを選択                       | LLM  | 4.1.4          |
| 6        | スクリプト有無からスキーマ・スクリプトを追加           | LLM  | 4.1.5          |
| 7        | オーケストレーション要件からリソースを追加             | LLM  | 4.1.6          |
| 8        | skillDependencies/multiSkillPlanからリソースを追加     | LLM  | 4.1.7          |
| 9        | externalCliAgents[]からリソースを追加                  | LLM  | 4.1.8          |
| 10       | ドキュメント要件からリソースを追加                     | LLM  | 4.1.9          |
| 11       | 必須リソース（共通）を追加                             | LLM  | 4.4            |
| 12       | 依存関係を解決し順序付け                               | LLM  | -              |
| 13       | resource-selection.jsonを出力                          | LLM  | -              |

### 4.3 コンテキストフィールド（リソース選択には使用しない）

以下のフィールドはスキル生成時のコンテキスト情報として使用されるが、リソース選択には直接影響しない：

| フィールド         | 用途                                     |
| ------------------ | ---------------------------------------- |
| goal               | スキル目的（SKILL.md生成時に使用）       |
| domain             | 対象領域（ドキュメント生成時に使用）     |
| frequency          | 使用頻度（スケジューラー設定の参考）     |
| scale              | 使用規模（設計判断の参考）               |
| priorities         | 設計優先事項（コード生成スタイルに反映） |
| constraints        | 制約条件（検証・テスト時に参照）         |
| additionalNotes    | 補足情報（全Phase通じて参照）            |
| suggestedSkillName | スキル名（ディレクトリ生成時に使用）     |
| interviewTimestamp | 記録用（ログ出力に使用）                 |

### 4.4 必須リソース（常に選択）

| カテゴリ   | リソース                                                                       |
| ---------- | ------------------------------------------------------------------------------ |
| agents     | analyze-request.md                                                             |
| scripts    | init_skill.js, generate_skill_md.js, validate_all.js, log_usage.js, utils.js   |
| schemas    | workflow.json, structure-plan.json                                             |
| assets     | skill-template.md, logs-template.md, evals-template.json, patterns-template.md |
| references | core-principles.md, skill-structure.md, naming-conventions.md                  |

---

## 5. インターフェース

### 5.1 入力

| データ名              | 提供元            | 検証ルール                    |
| --------------------- | ----------------- | ----------------------------- |
| interview-result.json | interview-user.md | schemas/interview-result.json |

### 5.2 出力

| 成果物名                | 受領先      | 内容                     |
| ----------------------- | ----------- | ------------------------ |
| resource-selection.json | Phase 1以降 | 選択されたリソースリスト |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/resource-selection.json",
  "createdAt": "2026-01-24T00:00:00Z",
  "basedOn": "interview-result.json",
  "agents": [
    {
      "path": "agents/analyze-request.md",
      "phase": "Phase 1",
      "reason": "要求分析に必須"
    }
  ],
  "scripts": [
    {
      "path": "scripts/init_skill.js",
      "phase": "Phase 4",
      "reason": "スキル初期化に必須"
    }
  ],
  "schemas": [
    {
      "path": "schemas/workflow.json",
      "phase": "Phase 2",
      "reason": "ワークフロー検証"
    }
  ],
  "assets": [
    {
      "path": "assets/skill-template.md",
      "phase": "Phase 4",
      "reason": "SKILL.md生成"
    },
    {
      "path": "assets/type-api-client.md",
      "phase": "Phase 2",
      "reason": "API連携スクリプト設計"
    }
  ],
  "references": [
    {
      "path": "references/core-principles.md",
      "phase": "全Phase",
      "reason": "設計原則参照"
    }
  ],
  "summary": {
    "totalResources": 25,
    "byCategory": {
      "agents": 5,
      "scripts": 8,
      "schemas": 4,
      "assets": 5,
      "references": 3
    }
  }
}
```

### 5.3 後続処理

```bash
# Phase 1へ（analyze-request.md を読み込み）
# resource-selection.jsonに基づき、各Phaseで必要なリソースのみを読み込む
```

---

## 6. 使用例

### 入力例: interview-result.json

```json
{
  "abstractionLevel": "L2",
  "goal": "GitHub PRを自動作成",
  "features": [
    { "name": "API連携", "priority": "must" },
    { "name": "テンプレート生成", "priority": "should" }
  ],
  "integrations": [{ "service": "GitHub API", "authType": "token" }],
  "scripts": [
    { "type": "api-client", "runtime": "node" },
    { "type": "git-ops", "runtime": "node" }
  ],
  "structure": "standard"
}
```

### 出力例: resource-selection.json

```json
{
  "agents": [
    {
      "path": "agents/analyze-request.md",
      "phase": "Phase 1",
      "reason": "要求分析"
    },
    {
      "path": "agents/extract-purpose.md",
      "phase": "Phase 1",
      "reason": "L2のため簡易分析"
    },
    {
      "path": "agents/design-script.md",
      "phase": "Phase 2",
      "reason": "スクリプト設計"
    }
  ],
  "scripts": [
    { "path": "scripts/init_skill.js", "phase": "Phase 4", "reason": "初期化" },
    {
      "path": "scripts/generate_skill_md.js",
      "phase": "Phase 4",
      "reason": "SKILL.md生成"
    },
    {
      "path": "scripts/generate_script.js",
      "phase": "Phase 4",
      "reason": "スクリプト生成"
    },
    {
      "path": "scripts/detect_runtime.js",
      "phase": "Phase 2",
      "reason": "ランタイム判定"
    }
  ],
  "schemas": [
    {
      "path": "schemas/script-definition.json",
      "phase": "Phase 2",
      "reason": "スクリプト定義検証"
    },
    {
      "path": "schemas/runtime-config.json",
      "phase": "Phase 2",
      "reason": "ランタイム検証"
    }
  ],
  "assets": [
    {
      "path": "assets/skill-template.md",
      "phase": "Phase 4",
      "reason": "SKILL.md生成"
    },
    {
      "path": "assets/agent-template.md",
      "phase": "Phase 4",
      "reason": "エージェント生成"
    },
    {
      "path": "assets/type-api-client.md",
      "phase": "Phase 2",
      "reason": "API連携設計"
    },
    {
      "path": "assets/type-git-ops.md",
      "phase": "Phase 2",
      "reason": "Git操作設計"
    },
    {
      "path": "assets/base-node.js",
      "phase": "Phase 4",
      "reason": "Node.jsテンプレート"
    }
  ],
  "references": [
    {
      "path": "references/api-integration-patterns.md",
      "phase": "Phase 2",
      "reason": "API統合パターン"
    },
    {
      "path": "references/official-docs-registry.md",
      "phase": "Phase 2",
      "reason": "GitHub API公式ドキュメント"
    }
  ],
  "summary": {
    "totalResources": 16,
    "byCategory": {
      "agents": 3,
      "scripts": 4,
      "schemas": 2,
      "assets": 5,
      "references": 2
    }
  }
}
```
