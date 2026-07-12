# Task仕様書：自己改善設計

> **読み込み条件**: フィードバック分析完了後、改善適用前
> **相対パス**: `agents/design-self-improvement.md`

## 1. メタ情報

| 項目     | 内容                    |
| -------- | ----------------------- |
| 名前     | Taiichi Ohno            |
| 専門領域 | 継続的改善・カイゼン    |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

フィードバック分析結果に基づき、具体的な改善計画を設計する。
**注意**: 実際の改善適用はスクリプトで行う（精度100%）。
本タスクは**改善内容の設計**のみを担当する。

### 2.2 目的

分析で特定された改善点を、適用可能な具体的な変更計画に落とし込む。

### 2.3 責務

| 責務       | 成果物                    |
| ---------- | ------------------------- |
| 改善計画設計 | improvement-plan.json |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント | 適用方法 |
| ----------------- | -------- |
| Toyota Production System (Ohno) | ムダの排除、継続的改善 |
| self-improvement-cycle.md | 改善サイクル全体像 |
| update-process.md | 更新プロセス |
| quality-standards.md | 品質基準 |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション | 担当 |
| -------- | ---------- | ---- |
| 1 | feedback-analysis.json を読み込む | LLM |
| 2 | 各提案を具体的な変更に変換 | LLM |
| 3 | 変更対象ファイルを特定 | LLM |
| 4 | 変更内容（diff形式）を生成 | LLM |
| 5 | 自動適用可否を判定 | LLM |
| 6 | リスクレベルを評価 | LLM |
| 7 | improvement-plan.json出力 | LLM |
| 8 | スキーマ検証 | Script |

### 4.2 チェックリスト

| 項目 | 基準 |
| ---- | ---- |
| 変更対象が特定されているか | ファイルパス・行範囲が明確 |
| 変更内容が具体的か | before/afterが定義済み |
| 自動適用可否が判定されているか | autoApplicableフラグ |
| リスクレベルが設定されているか | low/medium/high |
| ロールバック方法が明記されているか | 復元手順が存在 |
| 実行順序が定義されているか | executionOrder配列 |

### 4.3 ビジネスルール（制約）

| 制約 | 説明 |
| ---- | ---- |
| LLM = 設計のみ | 計画立案と判断 |
| Script = 適用 | 100%正確な変更実行 |
| 段階適用 | 低リスクから順に |
| 検証ゲート | 各変更後に検証 |
| バックアップ必須 | 変更前に自動保存 |

---

## 5. インターフェース

### 5.1 入力

| データ名 | 提供元 | 検証ルール |
| -------- | ------ | ---------- |
| feedback-analysis.json | analyze-feedback | スキーマ準拠 |

### 5.2 出力

| 成果物名 | 受領先 | 内容 |
| -------- | ------ | ---- |
| improvement-plan.json | apply_self_improvement.js | 改善計画 |

#### 出力スキーマ（schemas/update-plan.json準拠）

```json
{
  "skillName": "{{string: スキル名}}",
  "planCreatedAt": "{{string: ISO日時}}",
  "basedOn": "{{string: feedback-analysis.jsonのパス}}",
  "changes": [
    {
      "id": "{{string: chg-001}}",
      "suggestionId": "{{string: sug-001}}",
      "target": {
        "file": "{{string: 対象ファイルパス}}",
        "section": "{{string: セクション名（任意）}}",
        "lineRange": { "start": "{{number}}", "end": "{{number}}" }
      },
      "type": "{{enum: add|modify|delete}}",
      "content": {
        "before": "{{string: 変更前の内容}}",
        "after": "{{string: 変更後の内容}}"
      },
      "autoApplicable": "{{boolean}}",
      "riskLevel": "{{enum: low|medium|high}}",
      "reason": "{{string: 変更理由}}",
      "rollbackPlan": "{{string: ロールバック方法}}"
    }
  ],
  "executionOrder": ["{{string: chg-001}}", "{{string: chg-002}}"],
  "preConditions": ["{{string: 前提条件}}"],
  "postValidation": ["{{string: 検証コマンド}}"],
  "summary": {
    "totalChanges": "{{number: 変更数}}",
    "autoApplicable": "{{number: 自動適用可能数}}",
    "requiresReview": "{{number: レビュー必要数}}",
    "estimatedImpact": "{{string: 影響の概要}}"
  }
}
```

### 5.3 後続処理（Script Task - 100%精度）

```bash
# 計画検証
node scripts/validate_schema.js \
  --input .tmp/improvement-plan.json \
  --schema schemas/update-plan.json

# dry-run
node scripts/apply_self_improvement.js \
  --plan .tmp/improvement-plan.json \
  --dry-run

# 自動適用可能なもののみ適用
node scripts/apply_self_improvement.js \
  --plan .tmp/improvement-plan.json \
  --auto-only \
  --backup

# 全体検証
node scripts/validate_all.js .claude/skills/my-skill
```

---

## 6. 補足：LLM vs Script の役割分担

| 処理 | 担当 | 理由 |
| ---- | ---- | ---- |
| 改善内容の設計 | LLM | 創造的判断 |
| 変更差分の生成 | LLM | 文脈理解 |
| 自動適用可否判定 | LLM | リスク評価 |
| バックアップ作成 | Script | ファイル操作 |
| 変更適用 | Script | 正確な書き換え |
| 検証実行 | Script | 機械的チェック |

---

## 7. 補足：自動適用可否の判定基準

| 変更タイプ | 自動適用 | 理由 |
| ---------- | -------- | ---- |
| ドキュメント追記 | ○ | 副作用なし |
| エラーメッセージ改善 | ○ | 動作変更なし |
| デフォルト値調整 | △ | 影響範囲確認必要 |
| ワークフロー変更 | × | 動作に影響 |
| プロンプト変更 | × | 出力品質に影響 |
| スキーマ変更 | × | 互換性に影響 |

---

## 8. 補足：リスクレベル定義

| レベル | 条件 | 対応 |
| ------ | ---- | ---- |
| low | 副作用なし、ロールバック容易 | 自動適用可 |
| medium | 限定的影響、テスト必要 | レビュー推奨 |
| high | 動作変更、互換性影響 | レビュー必須 |
