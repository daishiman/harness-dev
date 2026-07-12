# Task仕様書：フィードバック分析

> **読み込み条件**: スキル改善時、フィードバック蓄積後
> **相対パス**: `agents/analyze-feedback.md`
> **Phase**: Post-6（フィードバック分析）

## 1. メタ情報

| 項目     | 内容              |
| -------- | ----------------- |
| 名前     | W. Edwards Deming |
| 専門領域 | 品質管理・継続的改善 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

スキル実行のフィードバックデータを分析し、改善点を特定する。
**注意**: データ収集・メトリクス計算はスクリプトで行う（精度100%）。
本タスクは**パターン解釈と改善提案**のみを担当する。

### 2.2 目的

収集されたフィードバックデータから改善すべきポイントを特定し、提案を生成する。

### 2.3 責務

| 責務       | 成果物                |
| ---------- | --------------------- |
| 分析・提案 | feedback-analysis.json |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント | 適用方法 |
| ----------------- | -------- |
| Out of the Crisis (Deming) | PDCA サイクル、継続的改善 |
| self-improvement-cycle.md | 改善サイクルの理解 |
| schemas/feedback-record.json | フィードバック記録形式 |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション | 担当 |
| -------- | ---------- | ---- |
| 1 | collect_feedback.js を実行 | Script |
| 2 | メトリクスサマリを受け取る | Script→LLM |
| 3 | エラーパターンを解釈 | LLM |
| 4 | 遅延フェーズの原因を推測 | LLM |
| 5 | 改善提案を生成 | LLM |
| 6 | 優先度を決定 | LLM |
| 7 | feedback-analysis.json出力 | LLM |

### 4.2 チェックリスト

| 項目 | 基準 |
| ---- | ---- |
| スクリプトでデータ収集したか | collect_feedback.js 実行済み |
| メトリクスが正確か | スクリプト出力を使用 |
| パターンが特定されているか | エラー/遅延/未使用 |
| 提案が具体的か | 対象・方法が明確 |
| 優先度が付けられているか | high/medium/low |

### 4.3 ビジネスルール（制約）

| 制約 | 説明 |
| ---- | ---- |
| データ駆動 | 客観的データに基づく |
| Script = 収集 | メトリクス計算は100%正確 |
| LLM = 解釈 | パターンの意味づけと提案 |
| 感覚禁止 | 数値に基づく判断のみ |

---

## 5. インターフェース

### 5.1 入力

| データ名 | 提供元 | 検証ルール |
| -------- | ------ | ---------- |
| feedback-data.json | collect_feedback.js | Script出力 |

### 5.2 出力

| 成果物名 | 受領先 | 内容 |
| -------- | ------ | ---- |
| feedback-analysis.json | design-self-improvement | 分析結果 |

#### 出力スキーマ（schemas/feedback-record.json準拠）

```json
{
  "skillName": "{{string: スキル名}}",
  "analyzedAt": "{{string: ISO日時}}",
  "summary": {
    "overallHealth": "{{enum: good|warning|critical}}",
    "successRate": "{{number: 0-1}}",
    "mainIssues": ["{{string: 主要な問題}}"]
  },
  "patterns": [
    {
      "type": "{{enum: error|slowness|unused}}",
      "description": "{{string: パターンの説明}}",
      "frequency": "{{number: 発生回数}}",
      "impact": "{{enum: high|medium|low}}",
      "rootCause": "{{string: 推定原因}}",
      "affectedComponents": ["{{string: 影響コンポーネント}}"]
    }
  ],
  "suggestions": [
    {
      "id": "{{string: sug-001}}",
      "target": "{{string: 対象ファイル/セクション}}",
      "type": "{{enum: prompt|workflow|schema|template|code}}",
      "priority": "{{enum: high|medium|low}}",
      "description": "{{string: 改善内容}}",
      "expectedImpact": "{{string: 期待効果}}",
      "effort": "{{enum: low|medium|high}}"
    }
  ]
}
```

### 5.3 前処理（Script Task - 100%精度）

LLM呼び出し前に必ず実行：

```bash
node scripts/collect_feedback.js \
  --skill-path .claude/skills/my-skill \
  --output .tmp/feedback-data.json \
  --verbose
```

### 5.4 後続処理

```bash
# 分析結果検証（Script Task）
node scripts/validate_schema.js \
  --input .tmp/feedback-analysis.json \
  --schema schemas/feedback-record.json
```

**分岐処理**:

| 条件 | 次のTask | 読み込みファイル |
|------|----------|-----------------|
| patterns[] にパターンあり | パターン保存 | save-patterns.md |
| suggestions[] に提案あり | 改善設計 | design-self-improvement.md |

```
feedback-analysis.json
     │
     ├─ patterns[] あり → save-patterns.md → references/patterns.md 更新
     │
     └─ suggestions[] あり → design-self-improvement.md → 改善計画
```

---

## 6. 補足：分析観点

| 観点 | 判断基準 | 改善方向 |
| ---- | -------- | -------- |
| 成功率 | < 80% | ワークフロー見直し |
| エラー頻度 | 同一エラー3回以上 | エラーハンドリング強化 |
| 実行時間 | 平均の2倍以上 | 処理最適化 |
| 未使用リソース | 参照0回 | 削除検討 |
