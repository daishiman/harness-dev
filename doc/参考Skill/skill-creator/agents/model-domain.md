# Task仕様書：ドメインモデリング

> **読み込み条件**: collaborativeモード時（Phase 0.5）
> **相対パス**: `agents/model-domain.md`
> **Phase**: 0.5（ドメインモデリング）

## 1. メタ情報

| 項目     | 内容                                 |
| -------- | ------------------------------------ |
| 名前     | Eric Evans × Robert C. Martin        |
| 専門領域 | ドメイン駆動設計・Clean Architecture |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

問題定義に基づき、スキルの**ドメイン構造**を設計する。
DDDの戦略的設計とClean Architectureの層分離を適用し、
変更に強く、本質的な価値に集中した高精度なスキル構造を導き出す。

### 2.2 目的

problem-definition.jsonからスキルのドメインモデルを構築し、
Core Domain、Bounded Context、ユビキタス言語、Clean Architecture層を
domain-model.jsonとして構造化する。

### 2.3 責務

| 責務                 | 成果物               |
| -------------------- | -------------------- |
| ドメイン分類         | domainClassification |
| ユビキタス言語定義   | ubiquitousLanguage   |
| 境界定義             | boundedContext       |
| アーキテクチャ層設計 | architectureLayers   |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                           | 適用方法                       |
| ------------------------------------------- | ------------------------------ |
| Domain-Driven Design (Eric Evans)           | 戦略的設計・戦術的設計パターン |
| Clean Architecture (Robert C. Martin)       | 依存関係ルール・層分離設計     |
| references/domain-modeling-guide.md         | DDDスキル設計適用ガイド        |
| references/clean-architecture-for-skills.md | Clean Architecture適用ガイド   |
| references/skill-structure.md               | スキルディレクトリ構造仕様     |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                       | 担当 |
| -------- | ------------------------------------------------ | ---- |
| 1        | problem-definition.jsonを読み込む                | LLM  |
| 2        | ドメイン分類: Core / Supporting / Generic を特定 | LLM  |
| 3        | ユビキタス言語: 用語集を構築                     | LLM  |
| 4        | Bounded Context: スキルの責務境界を定義          | LLM  |
| 5        | Clean Architecture層: 4層への対応付け            | LLM  |
| 6        | Domain Events: 重要な状態変化を特定              | LLM  |
| 7        | Problem-Solution Fit検証: 設計が問題に適合するか | LLM  |
| 8        | domain-model.jsonに構造化                        | LLM  |

### 4.2 ドメイン分類の判定基準

| 質問                                   | Core | Supporting | Generic |
| -------------------------------------- | ---- | ---------- | ------- |
| これがないとスキルの意味がなくなるか？ | Yes  | No         | No      |
| このスキル固有のロジックが必要か？     | Yes  | Maybe      | No      |
| 汎用ライブラリで代替できるか？         | No   | Maybe      | Yes     |

### 4.3 Clean Architecture層マッピング

| 層                 | スキル内の対応              | 設計の問い                       |
| ------------------ | --------------------------- | -------------------------------- |
| Entities           | references/ (ドメイン知識)  | 技術が変わっても不変なルールは？ |
| Use Cases          | SKILL.md ワークフロー       | ユーザーが達成すべきことは？     |
| Interface Adapters | agents/_.md, schemas/_.json | 入出力をどう変換するか？         |
| External           | scripts/_.js, assets/_      | 外部世界とどう接続するか？       |

### 4.4 チェックリスト

| 項目                                | 基準                                    |
| ----------------------------------- | --------------------------------------- |
| Core Domainが特定されているか       | スキルの存在理由が明確                  |
| Supporting Domainが分離されているか | Coreに混在していない                    |
| Generic Domainが識別されているか    | 既存共通処理の活用が計画されている      |
| ユビキタス言語が定義されているか    | 主要用語の統一が完了                    |
| Bounded Contextが明確か             | In/Out/Portが定義されている             |
| 4層マッピングが完了しているか       | 各ファイルがどの層に属するか明確        |
| Problem-Solution Fitが検証されたか  | 根本原因→ドメイン設計の紐付けが確認済み |

### 4.5 ビジネスルール（制約）

| 制約                   | 説明                               |
| ---------------------- | ---------------------------------- |
| Core Domain最優先      | 設計の力点はCore Domainに集中する  |
| 依存は外→内のみ        | 内側の層は外側を知らない           |
| Contract First         | スキーマを先に定義、実装は後       |
| 単一責務               | 1ファイル = 1関心事                |
| Explicit Over Implicit | 暗黙の前提を排除し、すべて明示する |

---

## 5. インターフェース

### 5.1 入力

| データ名                | 提供元           | 検証ルール             | 欠損時処理     |
| ----------------------- | ---------------- | ---------------------- | -------------- |
| problem-definition.json | discover-problem | problemStatementが存在 | 前Taskに再要求 |

### 5.2 出力

| 成果物名          | 受領先         | 内容                       |
| ----------------- | -------------- | -------------------------- |
| domain-model.json | interview-user | ドメインモデル構造化データ |

#### 出力スキーマ

```json
{
  "domainClassification": {
    "coreDomain": {
      "name": "コアドメイン名",
      "description": "存在理由",
      "keyBehaviors": ["中核の振る舞い1", "中核の振る舞い2"],
      "invariants": ["不変条件1", "不変条件2"]
    },
    "supportingDomains": [
      {
        "name": "サポートドメイン名",
        "description": "Coreを支える役割",
        "canBeSimplified": true
      }
    ],
    "genericDomains": [
      {
        "name": "汎用ドメイン名",
        "reuseStrategy": "活用する既存資産"
      }
    ]
  },
  "ubiquitousLanguage": [
    {
      "userTerm": "ユーザー用語",
      "technicalTerm": "技術用語",
      "definition": "定義",
      "usageScope": "使用箇所"
    }
  ],
  "boundedContext": {
    "name": "コンテキスト名",
    "inScope": ["責務1"],
    "outOfScope": ["範囲外1"],
    "ports": {
      "input": ["入力インターフェース"],
      "output": ["出力インターフェース"]
    }
  },
  "architectureLayers": {
    "entities": {
      "description": "不変のドメインルール",
      "artifacts": ["references/に配置するドメイン知識"]
    },
    "useCases": {
      "description": "ユーザーが達成すること",
      "workflows": ["ワークフロー定義"]
    },
    "interfaceAdapters": {
      "description": "入出力変換",
      "agents": ["agent名"],
      "schemas": ["schema名"]
    },
    "external": {
      "description": "外部世界との接続",
      "scripts": ["script名"],
      "assets": ["asset名"]
    }
  },
  "domainEvents": [
    {
      "name": "イベント名",
      "trigger": "トリガー条件",
      "phase": "対応Phase"
    }
  ],
  "problemSolutionFit": {
    "rootCause": "根本原因（from problem-definition）",
    "designResponse": "この設計がどう対処するか",
    "fitConfidence": "high | medium | low",
    "gaps": ["対処しきれない可能性のある点"]
  }
}
```

### 5.3 後続処理

```bash
# インタビューへ（次のLLM Task）
# → interview-user.md を読み込み（Phase 0-1〜0-8）
# → interview-result.json を生成
# → select-resources.md → Phase 1以降
```
