# Phase完了チェックリスト（skill-creator用）

> **相対パス**: `references/phase-completion-checklist.md`
> **用途**: skill-creator の各Phase完了条件の共通テンプレート

---

## 概要

skill-creator のスキル作成ワークフロー（Phase 0-0 〜 Phase 6）実行時に使用する完了条件チェックリスト。
各Phaseの必須成果物、検証方法、後続Phaseへの引き継ぎ条件を定義。

---

## Phase共通完了条件

すべてのPhaseに共通する完了条件。

### 必須チェック項目

- [ ] 本Phase内の全ステップを実行完了
- [ ] 出力JSONがスキーマに準拠している（該当する場合）
- [ ] 後続Phaseへの入力データが `.tmp/` に配置されている

### 検証コマンド（共通）

```bash
# スキーマ検証
node scripts/validate_all.js --input .tmp/<output>.json --schema schemas/<schema>.json

# 個別スキーマ検証
node scripts/validate_schema.js --input .tmp/<output>.json --schema schemas/<schema>.json
```

---

## Phase別チェックリスト

<details>
<summary><strong>Phase 0-0: 問題発見</strong></summary>

### 担当エージェント
`agents/discover-problem.md`

### 目的
ユーザーの根本課題を特定し、スキルで解決すべき問題を定義する。

### 完了条件

- [ ] 問題定義JSONが生成されている
- [ ] 根本原因が特定されている
- [ ] スキルで解決可能な範囲が明確化されている

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| 問題定義 | `.tmp/problem-definition.json` | `schemas/problem-definition.json` |

</details>

<details>
<summary><strong>Phase 0.5: ドメインモデリング</strong></summary>

### 担当エージェント
`agents/model-domain.md`

### 目的
DDD/Clean Architectureに基づき、スキルのドメインモデルを構築する。

### 完了条件

- [ ] ドメインモデルJSONが生成されている
- [ ] ユビキタス言語が定義されている
- [ ] Bounded Contextが明確化されている

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| ドメインモデル | `.tmp/domain-model.json` | `schemas/domain-model.json` |

</details>

<details>
<summary><strong>Phase 0-1〜0-8: インタビュー</strong></summary>

### 担当エージェント
`agents/interview-user.md`

### 目的
ユーザーとの対話を通じて、スキルの要件・機能・制約を収集する。

### 完了条件

- [ ] interview-result.json が生成されている
- [ ] interviewDepth に応じた必須フィールドが埋まっている
- [ ] goal, features, structure が定義されている
- [ ] インタビュー結果がスキーマに準拠している

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| インタビュー結果 | `.tmp/interview-result.json` | `schemas/interview-result.json` |

### interviewDepth別の完了基準

| 深度 | 必須Phase | 質問数目安 |
| --- | --- | --- |
| quick | 0-1, 0-2 | 3-4問 |
| standard | 0-1〜0-5 | 5-8問 |
| detailed | 0-1〜0-8 | 10-15問 |

</details>

<details>
<summary><strong>Phase 0.9: マルチスキル設計（条件付き）</strong></summary>

### 担当エージェント
`agents/design-multi-skill.md`

### 発動条件
`interview-result.json` に `multiSkillPlan` が存在する場合

### 目的
複数スキルの同時作成における依存関係グラフを設計する。

### 完了条件

- [ ] multi-skill-graph.json が生成されている
- [ ] 依存関係グラフがDAGとして有効
- [ ] トポロジカルソート順が決定されている
- [ ] 各サブスキル用の interview-result.json が分割されている
- [ ] failureRecovery 設定が定義されている

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| マルチスキルグラフ | `.tmp/multi-skill-graph.json` | `schemas/multi-skill-graph.json` |
| 個別インタビュー結果 | `.tmp/{skill-name}-interview-result.json` | `schemas/interview-result.json` |

</details>

<details>
<summary><strong>リソース選択（Phase間）</strong></summary>

### 担当エージェント
`agents/select-resources.md`

### 目的
interview-result.json に基づき、Phase 1以降で使用するリソースを選定する。

### 完了条件

- [ ] resource-selection.json が生成されている
- [ ] 選定理由が記録されている
- [ ] 不要なリソースが除外されている

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| リソース選定結果 | `.tmp/resource-selection.json` | `schemas/resource-selection.json` |

</details>

<details>
<summary><strong>Phase 1: 要求分析</strong></summary>

### 担当エージェント
`agents/analyze-request.md`

### 目的
インタビュー結果を構造化された要求分析に変換する。

### 完了条件

- [ ] 要求分析が完了している
- [ ] 機能要件が整理されている
- [ ] 後続Phase（設計）への入力が準備されている

### 必須成果物

| 成果物 | パス |
| --- | --- |
| 要求分析結果 | `.tmp/request-analysis.json` |

</details>

<details>
<summary><strong>Phase 2: 設計</strong></summary>

### 担当エージェント（順次実行）
1. `agents/extract-purpose.md` — 目的抽出
2. `agents/define-boundary.md` — 境界定義
3. `agents/design-workflow.md` — ワークフロー設計
4. サブタスクエージェント（条件付き）:
   - `agents/design-scheduler.md`
   - `agents/design-conditional-flow.md`
   - `agents/design-event-trigger.md`
   - `agents/design-orchestration.md`
   - `agents/design-custom-script.md`

### 目的
スキルの目的・境界・ワークフローを設計する。

### 完了条件

- [ ] purpose.json が生成されている
- [ ] boundary.json が生成されている
- [ ] workflow.json が生成されている
- [ ] 各サブタスク成果物が生成されている（該当する場合）
- [ ] 各出力がスキーマに準拠している

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| 目的定義 | `.tmp/purpose.json` | `schemas/purpose.json` |
| 境界定義 | `.tmp/boundary.json` | `schemas/boundary.json` |
| ワークフロー設計 | `.tmp/workflow.json` | `schemas/workflow.json` |

</details>

<details>
<summary><strong>Phase 2.5: 依存関係解決（条件付き）</strong></summary>

### 担当エージェント
`agents/resolve-skill-dependencies.md`

### 発動条件
`interview-result.json` に `skillDependencies` が存在する場合

### 目的
他スキルとの依存関係を解決し、相対パス参照を設計する。

### 完了条件

- [ ] skill-dependency-graph.json が生成されている
- [ ] 依存先スキルの存在が確認されている
- [ ] 相対パスが正しく計算されている
- [ ] 循環依存がないことが検証されている
- [ ] required=true の依存先が全て存在する

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| 依存関係グラフ | `.tmp/skill-dependency-graph.json` | `schemas/skill-dependency-graph.json` |

</details>

<details>
<summary><strong>Phase 3: 構造計画</strong></summary>

### 担当エージェント
`agents/plan-structure.md`

### 目的
フォルダ構造とファイル配置を計画する。

### 完了条件

- [ ] 構造計画JSONが生成されている
- [ ] ディレクトリ構造が定義されている
- [ ] ファイル配置が決定されている
- [ ] 構造がスキーマに準拠している

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| 構造計画 | `.tmp/structure.json` | `schemas/structure.json` |

</details>

<details>
<summary><strong>Phase 4: 生成</strong></summary>

### 担当エージェント
1. `agents/generate-code.md` — メインコード生成
2. `agents/generate-api-docs.md` — APIドキュメント生成（条件付き）
3. `agents/generate-setup-guide.md` — セットアップガイド生成（条件付き）

### 目的
構造計画に基づき、実際のスキルファイルを生成する。

### 完了条件

- [ ] SKILL.md が生成されている
- [ ] agents/ 配下のエージェントファイルが生成されている
- [ ] references/ 配下のリファレンスファイルが生成されている
- [ ] scripts/ 配下のスクリプトが生成されている（該当する場合）
- [ ] schemas/ 配下のスキーマが生成されている（該当する場合）
- [ ] assets/ 配下のテンプレートが生成されている（該当する場合）

### 検証コマンド

```bash
# スキル構造検証
node scripts/quick_validate.js .claude/skills/<skill-name>
```

</details>

<details>
<summary><strong>Phase 4.5: 外部CLIエージェント委譲（条件付き）</strong></summary>

### 担当エージェント
`agents/delegate-to-external-cli.md`

### 発動条件
`interview-result.json` に `externalCliAgents` が存在する場合

### 目的
Codex/Gemini等の外部CLIエージェントにタスクを委譲する。

### 完了条件

- [ ] external-cli-result.json が生成されている
- [ ] 外部エージェントの実行が完了している
- [ ] 結果が統合されている

### 必須成果物

| 成果物 | パス | スキーマ |
| --- | --- | --- |
| 外部CLI結果 | `.tmp/external-cli-result.json` | `schemas/external-cli-result.json` |

</details>

<details>
<summary><strong>Phase 5: レビュー</strong></summary>

### 担当スクリプト
- `scripts/quick_validate.js` — スキル構造検証（詳細モード）

### 目的
生成されたスキルの品質をレビューする。

### 完了条件

- [ ] SKILL.md の構造が正しい（Frontmatter, Anchors, Trigger）
- [ ] エージェント仕様書のフォーマットが統一されている
- [ ] スキーマ参照が正しい
- [ ] 相対パスが正しい
- [ ] Progressive Disclosure が適切に設計されている

### 検証コマンド

```bash
# スキル構造検証（詳細）
node scripts/quick_validate.js .claude/skills/<skill-name> --verbose
```

</details>

<details>
<summary><strong>Phase 6: 検証</strong></summary>

### 担当スクリプト
- `scripts/validate_all.js` — 全体検証（スキーマ・構造・リンク）
- `scripts/quick_validate.js` — 簡易構造検証
- `scripts/log_usage.js` — 使用ログ記録

### 目的
スキルの総合的な検証を行い、リリース可能な品質を確認する。

### 完了条件

- [ ] quick_validate.js が全項目PASSしている
- [ ] validate_all.js が全スキーマ検証PASSしている
- [ ] resource-map.md が最新のリソース構成を反映している
- [ ] SKILL.md の変更履歴が更新されている
- [ ] 実際の使用テスト（ドライラン）が実施されている
- [ ] 未タスク監査を実施する場合、`current`（合否）と`baseline`（既存負債）を分離記録している
- [ ] 画面証跡を扱う場合、各スクリーンショットに「状態名 + 検証目的」を記録している
- [ ] 仕様更新タスクでは、仕様書別SubAgent実行ログ（実装内容/苦戦箇所/検証証跡）を成果物に残している

### 検証コマンド

```bash
# 全体検証
node scripts/validate_all.js --skill .claude/skills/<skill-name>

# 構造検証
node scripts/quick_validate.js .claude/skills/<skill-name>

# （必要時）未タスク差分監査
node .agents/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD

# （必要時）未タスク全体監視
node .agents/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json
```

</details>

---

## 関連リソース

- **作成プロセス**: See [creation-process.md](creation-process.md)
- **品質基準**: See [quality-standards.md](quality-standards.md)
- **スキル構造**: See [skill-structure.md](skill-structure.md)
- **リソースマップ**: See [resource-map.md](resource-map.md)
