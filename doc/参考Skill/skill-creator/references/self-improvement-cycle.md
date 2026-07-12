# 自己改善サイクル

> **読み込み条件**: フィードバック分析時、スキル改善時
> **相対パス**: `references/self-improvement-cycle.md`

---

## 概要

スキルが自己のパフォーマンスを分析し、継続的に改善するサイクルの実装方法。

---

## 1. 自己改善サイクル全体像

```
スキル実行
    │
    ▼
[実行結果記録] ← log_usage.js
    │
    ▼
[メトリクス更新] ← EVALS.json
    │
    ▼
[パターン分析] ← analyze-feedback (LLM)
    │
    ├─ patterns[] あり ─────────────┐
    │                               ▼
    │                    [パターン保存] ← save-patterns (LLM)
    │                               │
    │                               ▼
    │                    references/patterns.md 更新
    │
    ├─ suggestions[] あり
    ▼
[改善提案生成] ← design-self-improvement (LLM)
    │
    ▼
[改善適用] ← apply_self_improvement.js
    │
    ▼
[検証] ← validate_all.js
    │
    ▼
改善完了（ホットリロード）
```

---

## 2. 記録フェーズ

### 2.1 実行結果の記録

**スクリプト**: `scripts/log_usage.js`

```bash
# 成功時
node scripts/log_usage.js \
  --result success \
  --phase "Phase 4" \
  --duration 1234 \
  --notes "正常完了"

# 失敗時
node scripts/log_usage.js \
  --result failure \
  --phase "Phase 3" \
  --error "ValidationError" \
  --notes "スキーマ検証失敗"
```

### 2.2 記録される情報

| 項目 | 説明 | 例 |
|------|------|-----|
| timestamp | 実行日時 | 2026-01-13T12:00:00.000Z |
| result | 結果 | success/failure |
| phase | フェーズ | Phase 4 |
| duration | 実行時間 | 1234ms |
| errors | エラー情報 | ValidationError |
| notes | 補足メモ | 自由記述 |

### 2.3 LOGS.md形式

```markdown
## [2026-01-13T12:00:00.000Z]

- **Result**: ✓ 成功
- **Phase**: Phase 4
- **Duration**: 1234ms
- **Notes**: スキル生成完了

---
```

---

## 3. 分析フェーズ

### 3.1 メトリクス計算

**EVALS.json**:

```json
{
  "skillName": "skill-creator",
  "currentLevel": 2,
  "metrics": {
    "totalUsageCount": 25,
    "successCount": 22,
    "failureCount": 3,
    "successRate": 0.88,
    "averageDuration": 2345,
    "lastEvaluated": "2026-01-13T12:00:00.000Z"
  },
  "levelHistory": [
    { "level": 1, "achievedAt": "2026-01-01T00:00:00.000Z" },
    { "level": 2, "achievedAt": "2026-01-10T00:00:00.000Z" }
  ],
  "patterns": {
    "commonErrors": [
      { "type": "ValidationError", "count": 2, "lastOccurred": "..." }
    ],
    "slowPhases": [
      { "phase": "Phase 2", "avgDuration": 5000 }
    ]
  }
}
```

### 3.2 パターン検出

| パターン | 検出条件 | 改善アクション |
|----------|----------|----------------|
| 高頻度エラー | 同一エラー3回以上 | エラーハンドリング強化 |
| 遅いフェーズ | 平均の2倍以上 | 処理最適化 |
| 低成功率 | 80%未満 | ワークフロー見直し |
| 未使用リソース | 参照0回 | リソース削除検討 |

---

## 4. 改善提案フェーズ

### 4.1 改善対象

| 対象 | 改善内容 | 優先度判定 |
|------|----------|------------|
| SKILL.md | ワークフロー最適化 | 高: 成功率影響 |
| agents/ | プロンプト改善 | 中: 品質影響 |
| scripts/ | パフォーマンス改善 | 中: 速度影響 |
| schemas/ | 検証ルール調整 | 低: 安定性影響 |
| references/ | ドキュメント更新 | 低: 利便性影響 |

### 4.2 改善提案JSON形式

```json
{
  "skillName": "skill-creator",
  "analyzedAt": "2026-01-13T12:00:00.000Z",
  "suggestions": [
    {
      "id": "sug-001",
      "target": "agents/design-workflow.md",
      "type": "prompt",
      "priority": "high",
      "reason": "Phase 2でのエラー率が高い",
      "description": "タスク分類の判断基準を明確化",
      "change": {
        "section": "4.2 タスクタイプの判断基準",
        "action": "add",
        "content": "..."
      }
    },
    {
      "id": "sug-002",
      "target": "scripts/validate_schema.js",
      "type": "code",
      "priority": "medium",
      "reason": "検証エラーメッセージが不明確",
      "description": "詳細なエラーメッセージを追加"
    }
  ],
  "autoApplicable": ["sug-002"],
  "requiresReview": ["sug-001"]
}
```

---

## 5. 適用フェーズ

### 5.1 自動適用可能な改善

| 改善タイプ | 自動適用条件 | 例 |
|------------|--------------|-----|
| ドキュメント | 記述追加のみ | リファレンス更新 |
| エラーメッセージ | 文字列変更のみ | 詳細化 |
| デフォルト値 | 安全な変更 | タイムアウト調整 |
| ログ追加 | 副作用なし | デバッグ情報 |

### 5.2 レビュー必須の改善

| 改善タイプ | レビュー理由 | 例 |
|------------|--------------|-----|
| ワークフロー変更 | 実行順序影響 | フェーズ追加 |
| プロンプト変更 | 出力品質影響 | 判断基準変更 |
| スキーマ変更 | 互換性影響 | 必須フィールド追加 |
| スクリプトロジック | 動作変更 | アルゴリズム変更 |

### 5.3 適用コマンド

```bash
# dry-run（変更確認のみ）
node scripts/apply_self_improvement.js \
  --suggestions .tmp/suggestions.json \
  --dry-run

# 自動適用可能なもののみ適用
node scripts/apply_self_improvement.js \
  --suggestions .tmp/suggestions.json \
  --auto-only

# 全て適用（レビュー済み前提）
node scripts/apply_self_improvement.js \
  --suggestions .tmp/suggestions.json \
  --all \
  --backup
```

---

## 6. スキル更新との統合

### 6.1 更新トリガー

| トリガー | 説明 | 自動実行 |
|----------|------|----------|
| 手動要求 | ユーザーからの更新要求 | × |
| 閾値到達 | エラー率閾値超過 | ○（提案のみ） |
| 定期評価 | 10回実行ごと | ○（分析のみ） |
| レベルアップ | レベル条件達成 | ○（メトリクス更新） |

### 6.2 更新ワークフロー統合

```
[update モード]
    │
    ├─ 手動更新要求
    │   └─ design-update → apply_updates
    │
    └─ 自己改善トリガー
        └─ analyze-feedback → design-self-improvement → apply_self_improvement
```

### 6.3 Phase 12 docs-heavy で優先抽出する改善候補

| 症状 | 追加すべき改善候補 | 優先対象 |
|------|--------------------|----------|
| `spec_created` なのに Phase 12 が計画記述で止まる | `.claude` 正本 / lessons / backlog / artifacts を同一ターンで実更新する guide 追加 | `references/update-process.md`, `SKILL.md` |
| screenshot fallback に metadata や failure reason が無い | harness / capture script / metadata / review board path を必須化 | `assets/phase12-system-spec-retrospective-template.md` |
| 未タスクを formalize したが配置先が揺れる | `docs/30-workflows/unassigned-task/` と completed backlog の配置判断を追記 | `references/update-process.md` |
| system spec 更新と skill 更新が別ターンに分離される | `A: system spec / B: screenshot / C: unassigned / D: skill mirror` の lane をテンプレート化 | `SKILL.md`, templates |

---

## 7. 実装例

### 7.1 collect_feedback.js

```javascript
#!/usr/bin/env node

import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = resolve(__dirname, "..");
const LOGS_PATH = resolve(SKILL_DIR, "LOGS.md");
const EVALS_PATH = resolve(SKILL_DIR, "EVALS.json");

function collectFeedback() {
  // LOGS.mdからエントリを解析
  const logs = parseLogs();

  // パターン分析
  const patterns = analyzePatterns(logs);

  // メトリクス更新
  const metrics = calculateMetrics(logs);

  // EVALS.json更新
  const evals = existsSync(EVALS_PATH)
    ? JSON.parse(readFileSync(EVALS_PATH, "utf-8"))
    : {};

  evals.metrics = metrics;
  evals.patterns = patterns;
  evals.lastAnalyzed = new Date().toISOString();

  writeFileSync(EVALS_PATH, JSON.stringify(evals, null, 2));

  return { metrics, patterns };
}

function parseLogs() {
  if (!existsSync(LOGS_PATH)) return [];
  // ログ解析ロジック
}

function analyzePatterns(logs) {
  // パターン検出ロジック
}

function calculateMetrics(logs) {
  // メトリクス計算ロジック
}
```

### 7.2 フィードバック分析エージェント呼び出し

```bash
# フィードバック収集
node scripts/collect_feedback.js --skill-path .claude/skills/my-skill

# LLM分析（analyze-feedback.md参照）
# → 改善提案JSON出力

# 改善適用
node scripts/apply_self_improvement.js \
  --suggestions .tmp/suggestions.json \
  --backup
```

---

## 8. ベストプラクティス

### すべきこと

| 推奨事項 | 理由 |
|----------|------|
| 毎回ログ記録 | データ駆動の改善 |
| 閾値の設定 | 適切なタイミングで改善 |
| バックアップ作成 | ロールバック可能 |
| 段階的適用 | リスク最小化 |

### 避けるべきこと

| アンチパターン | 問題 |
|----------------|------|
| ログ省略 | 分析データ不足 |
| 無検証適用 | 意図しない変更 |
| 過剰な自動適用 | 安定性低下 |

---

## 関連リソース

- **エージェント**: See [agents/analyze-feedback.md](.claude/skills/skill-creator/agents/analyze-feedback.md)
- **エージェント**: See [agents/design-self-improvement.md](.claude/skills/skill-creator/agents/design-self-improvement.md)
- **エージェント**: See [agents/save-patterns.md](.claude/skills/skill-creator/agents/save-patterns.md)
- **スクリプト**: See [scripts/collect_feedback.js](.claude/skills/skill-creator/scripts/collect_feedback.js)
- **スキーマ**: See [schemas/feedback-record.json](.claude/skills/skill-creator/schemas/feedback-record.json)
- **パターン集**: See [references/patterns.md](patterns.md)
