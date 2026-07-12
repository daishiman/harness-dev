# スクリプトコマンドリファレンス

> **読み込み条件**: スクリプト実行時
> **相対パス**: `references/script-commands.md`

---

## モード判定・初期化

| Script            | 用途               | 実行コマンド                                                |
| ----------------- | ------------------ | ----------------------------------------------------------- |
| detect_mode.js    | モード判定         | `node scripts/detect_mode.js --request "新規スキル"`        |
| detect_runtime.js | ランタイム判定     | `node scripts/detect_runtime.js --script-type api-client`   |
| init_skill.js     | ディレクトリ初期化 | `node scripts/init_skill.js my-skill --path .claude/skills` |

---

## Codex連携

| Script                 | 用途                  | 実行コマンド                                               |
| ---------------------- | --------------------- | ---------------------------------------------------------- |
| check_prerequisites.js | Codex事前条件チェック | `node scripts/check_prerequisites.js`                      |
| assign_codex.js        | Codexへのタスク委譲   | `node scripts/assign_codex.js --task .tmp/codex-task.json` |

---

## 生成

| Script                   | 用途                 | 実行コマンド                                                                    |
| ------------------------ | -------------------- | ------------------------------------------------------------------------------- |
| generate_skill_md.js     | SKILL.md生成         | `node scripts/generate_skill_md.js --config .tmp/skill-config.json`             |
| generate_agent.js        | agents/\*.md生成     | `node scripts/generate_agent.js --config .tmp/agent-config.json`                |
| generate_script.js       | scripts/\*.js生成    | `node scripts/generate_script.js --config .tmp/script-config.json`              |
| generate_dynamic_code.js | テンプレート変数展開 | `node scripts/generate_dynamic_code.js --template <path> --vars .tmp/vars.json` |

---

## 検証

| Script                | 用途             | 実行コマンド                                                                       |
| --------------------- | ---------------- | ---------------------------------------------------------------------------------- |
| validate_all.js       | 全体検証         | `node scripts/validate_all.js --skill-path .claude/skills/my-skill`                |
| validate_structure.js | 構造検証         | `node scripts/validate_structure.js --skill-path .claude/skills/my-skill`          |
| validate_links.js     | リンク検証       | `node scripts/validate_links.js --skill-path .claude/skills/my-skill`              |
| validate_schema.js    | スキーマ検証     | `node scripts/validate_schema.js --input .tmp/data.json --schema schemas/xxx.json` |
| validate_workflow.js  | ワークフロー検証 | `node scripts/validate_workflow.js --skill-path .claude/skills/my-skill`           |
| validate_plan.js      | 構造計画検証     | `node scripts/validate_plan.js --plan .tmp/structure-plan.json`                    |
| quick_validate.js     | 簡易検証         | `node scripts/quick_validate.js --skill-path .claude/skills/my-skill`              |

---

## プロンプト・更新

| Script               | 用途              | 実行コマンド                                                          |
| -------------------- | ----------------- | --------------------------------------------------------------------- |
| analyze_prompt.js    | プロンプト分析    | `node scripts/analyze_prompt.js --skill-path .claude/skills/my-skill` |
| apply_updates.js     | 更新適用          | `node scripts/apply_updates.js --plan .tmp/update-plan.json`          |
| update_skill_list.js | skill_list.md更新 | `node scripts/update_skill_list.js --skills-dir .claude/skills`       |

---

## フィードバック・改善

| Script                    | 用途               | 実行コマンド                                                                                             |
| ------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------- |
| log_usage.js              | 使用記録           | `node scripts/log_usage.js --result success --phase "Phase 4" --notes "完了"`                            |
| collect_feedback.js       | フィードバック収集 | `node scripts/collect_feedback.js --skill-path .claude/skills/my-skill --output .tmp/feedback-data.json` |
| apply_self_improvement.js | 改善適用           | `node scripts/apply_self_improvement.js --suggestions .tmp/suggestions.json --dry-run`                   |

---

## オーケストレーション

| Script                    | 用途                     | 実行コマンド                                                                                 |
| ------------------------- | ------------------------ | -------------------------------------------------------------------------------------------- |
| execute_chain.js          | スキルチェーン実行       | `node scripts/execute_chain.js --chain .tmp/chain-def.json --input '{"key":"value"}'`        |
| execute_parallel.js       | 並列スキル実行           | `node scripts/execute_parallel.js --config .tmp/parallel-def.json --input '{"key":"value"}'` |
| validate_orchestration.js | オーケストレーション検証 | `node scripts/validate_orchestration.js --config .tmp/orchestration.json`                    |

### 使用例

```bash
# スキルチェーン実行（dry-run）
node scripts/execute_chain.js --chain .tmp/chain.json --dry-run

# 並列実行（詳細ログ付き）
node scripts/execute_parallel.js --config .tmp/parallel.json -v

# オーケストレーション定義検証
node scripts/validate_orchestration.js --config .tmp/orchestration.json --verbose
```

---

## 依存関係管理

| Script            | 用途                 | 実行コマンド                                                                |
| ----------------- | -------------------- | --------------------------------------------------------------------------- |
| install_deps.js   | 依存関係インストール | `node scripts/install_deps.js --skill-path .claude/skills/my-skill`         |
| add_dependency.js | 依存関係追加         | `node scripts/add_dependency.js axios --skill-path .claude/skills/my-skill` |

### 使用例

```bash
# skill-creatorの依存関係をインストール
node .claude/skills/skill-creator/scripts/install_deps.js

# 他のスキルに依存関係を追加
node .claude/skills/skill-creator/scripts/add_dependency.js axios --skill-path .claude/skills/my-skill

# 開発依存関係として追加
node .claude/skills/skill-creator/scripts/add_dependency.js typescript --dev

# バージョン指定で追加
node .claude/skills/skill-creator/scripts/add_dependency.js lodash@4.17.21
```

---

## スキーマ検証コマンド

### コア定義

```bash
# エージェント定義
node scripts/validate_schema.js --input .tmp/agent.json --schema schemas/agent-definition.json

# モード判定結果
node scripts/validate_schema.js --input .tmp/mode.json --schema schemas/mode.json

# ワークフロー定義
node scripts/validate_schema.js --input .tmp/workflow.json --schema schemas/workflow.json

# 構造計画
node scripts/validate_schema.js --input .tmp/structure.json --schema schemas/structure-plan.json
```

### その他

```bash
# 汎用スキーマ検証
node scripts/validate_schema.js --input <input-file> --schema <schema-file>
```
