# フィードバックループ（§7）

> 18-skills.md §7 の要約
> **相対パス**: `references/feedback-loop.md`
> **原典**: `docs/00-requirements/18-skills.md` §7

---

## 7.1 目的

スキルが使用されるたびにフィードバックを収集し、継続的に改善する仕組みを提供する。

---

## 7.2 実装方式

**採用方式**: エージェント責務方式（明示的な記録フェーズ）

| 特性           | 説明                                                 |
| -------------- | ---------------------------------------------------- |
| 確実性         | 最も高い（ワークフローに組み込むため記録漏れがない） |
| 不確実性排除   | スクリプトで確実に実行                               |
| メンテナンス性 | 高い（エージェントテンプレートで標準化）             |

---

## 7.3 標準ログスクリプト: log_usage.js

**ファイル**: `scripts/log_usage.js`

### 責務

| 処理           | 説明                                                 |
| -------------- | ---------------------------------------------------- |
| 実行記録の追記 | 使用履歴をログファイルに記録                         |
| メトリクス更新 | 使用回数・成功率を更新                               |
| レベル評価     | 現在のメトリクスがレベルアップ条件を満たすかチェック |

### 引数

| 引数       | 必須 | 説明                       |
| ---------- | ---- | -------------------------- |
| `--result` | 必須 | `success` または `failure` |
| `--phase`  | 任意 | 実行したフェーズ名         |
| `--agent`  | 任意 | 実行したエージェント名     |
| `--notes`  | 任意 | 追加のフィードバックメモ   |

### 使用形式

```bash
node scripts/log_usage.js \
  --result {{success|failure}} \
  --phase "{{phase-name}}" \
  --agent "{{agent-name}}"
```

### 使用例

**成功時**:

```bash
node scripts/log_usage.js \
  --result success \
  --phase "Phase 4" \
  --agent "skill-creator"
```

**失敗時（ノート付き）**:

```bash
node scripts/log_usage.js \
  --result failure \
  --phase "Phase 3" \
  --notes "検証エラー: name フィールドが不正"
```

---

## 7.4 更新されるファイル

### LOGS.md

実行記録が追記される：

```markdown
## [2025-12-31T10:00:00.000Z]

- **Agent**: skill-creator
- **Phase**: Phase 4
- **Result**: ✓ 成功
- **Notes**: なし

---
```

### EVALS.json

メトリクスが更新される：

```json
{
  "skill_name": "skill-creator",
  "current_level": 1,
  "metrics": {
    "total_usage_count": 10,
    "success_count": 8,
    "failure_count": 2,
    "last_evaluated": "2025-12-31T10:00:00.000Z"
  }
}
```

---

## 7.5 レベルアップ条件

スキルは使用実績に基づいて自動的にレベルアップする：

| レベル | 名称         | 最小使用回数 | 最小成功率 |
| ------ | ------------ | ------------ | ---------- |
| 1      | Beginner     | 0            | 0%         |
| 2      | Intermediate | 5            | 60%        |
| 3      | Advanced     | 15           | 75%        |
| 4      | Expert       | 30           | 85%        |

**レベルアップ時の動作**:

| 順序 | 処理                                                 |
| ---- | ---------------------------------------------------- |
| 1    | EVALS.json の `current_level` を更新                 |
| 2    | コンソールにレベルアップ通知を表示                   |
| 3    | SKILL.md の `level` フィールドを更新（存在する場合） |
| 4    | CHANGELOG.md に自動エントリを追加（存在する場合）    |

---

## 7.6 ベストプラクティス

### すべきこと

| プラクティス                              | 理由                       |
| ----------------------------------------- | -------------------------- |
| ワークフローの最終フェーズで必ず記録      | 記録漏れを防ぐ             |
| 失敗時は `--notes` で具体的な原因を記録   | 改善のためのデータを蓄積   |
| 定期的に LOGS.md を確認し、パターンを分析 | 継続的改善のサイクルを維持 |

### 避けるべきこと

| アンチパターン               | 問題                           |
| ---------------------------- | ------------------------------ |
| フィードバック記録をスキップ | データが蓄積されない           |
| 成功/失敗の判断を曖昧にする  | メトリクスの信頼性が低下       |
| 記録なしでスキルを改善する   | データ駆動の改善が維持できない |

---

## 7.7 Phase 12 からのフィードバック反映プロセス

Phase 12 で作成したスキルフィードバックレポートを、スキル改善に確実に反映するサイクル。

### 反映フロー

```
Phase 12 Task 5               Phase 2 テンプレート改善
  (フィードバックレポート作成)        (次タスクの設計品質向上)
        │                              ▲
        ▼                              │
  lessons-learned.md  ──────→  patterns.md / phase-templates.md
        │                              ▲
        ▼                              │
  06-known-pitfalls.md ────────────────┘
  (新規Pitfall登録)
```

### 反映ステップ

| Step | 内容 | 入力 | 出力 |
| --- | --- | --- | --- |
| 1 | フィードバックレポートのセクション2（技術的教訓）を精査 | `skill-feedback-report.md` | Pitfall候補リスト |
| 2 | 新規Pitfall候補を `06-known-pitfalls.md` へ登録 | Pitfall候補リスト | `P{{N}}` エントリ |
| 3 | セクション3（スキル改善提案）を対象スキルの `patterns.md` / `phase-templates.md` へ反映 | 改善提案リスト | 更新済みテンプレート |
| 4 | セクション1（ワークフロー改善点）を `phase-11-12-guide.md` や `spec-update-workflow.md` へ反映 | 改善点リスト | 更新済みガイド |
| 5 | 反映結果を `LOGS.md`（2ファイル）と `SKILL.md`（2ファイル）へ記録 | 更新結果 | 変更履歴エントリ |

### TASK-UI-03 での適用例

| Step | 入力 | 出力 | 結果 |
| --- | --- | --- | --- |
| 1 | Phase 10 MINOR 4件（a11y属性不足） | a11y テスト早期検出の教訓 | Phase 4 テンプレート改善候補 |
| 2 | a11y 属性不足が Phase 10 まで検出されなかった | 既存Pitfall P47 の拡張候補 | N/A（独立Pitfall化せず Phase 4 で対応） |
| 3 | Phase 4 に WCAG テストケース推奨を追加 | `phase-templates.md` 更新 | UIタスクで a11y テストが標準化 |
| 4 | フィードバックレポートテンプレートの標準化 | `patterns.md` 更新 | Task 5 の記載粒度が統一 |
| 5 | LOGS.md / SKILL.md 更新 | 変更履歴 | トレーサビリティ確保 |

### タイミング

| トリガー | 実行者 | 頻度 |
| --- | --- | --- |
| Phase 12 Task 5 完了直後 | タスク実行者（同一セッション推奨） | 毎タスク |
| スキル改善セッション開始時 | skill-creator update モード | 蓄積した知見の一括反映 |

### lessons-learned inbound link 規約（task-24 適用）

task 完了時に当該 skill の `references/lessons-learned-<task-id>.md` を生成し、同一 wave 内で 3 indexes へ登録する。indexes drift は CI gate `verify-indexes-up-to-date` で検出される。

1. `references/lessons-learned-<task-id>.md` を新規作成（frontmatter: `task_id`, `status`, `scope`, `created`）
2. `indexes/resource-map.md` に `references/lessons-learned-<task-id>.md` の項目を追加
3. `indexes/quick-reference.md` に L-<TASK>-NNN アンカーから本文への逆引きを追加
4. `indexes/topic-map.md` の関連 topic 下に inbound link を追加
5. workflow artifact-inventory（`references/workflow-<task>-artifact-inventory.md`）にも cross-link を残す

---

## 関連リソース

- **作成プロセス**: See [creation-process.md](creation-process.md) / [update-process.md](update-process.md)
- **品質基準**: See [quality-standards.md](quality-standards.md) - §8
- **フィードバックテンプレート**: See [patterns.md](patterns.md) - スキルフィードバックレポートテンプレート（TASK-UI-03）
