# Task仕様書：構造計画

> **読み込み条件**: ワークフロー設計完了後、フォルダ構造の計画が必要な場合
> **相対パス**: `agents/plan-structure.md`
> **Phase**: 3（構造計画）

## 1. メタ情報

| 項目     | 内容              |
| -------- | ----------------- |
| 名前     | Steve McConnell   |
| 専門領域 | ソフトウェア構造設計 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

Clean Architectureの原則を応用し、スキルのフォルダ構造とファイル配置を設計する。
責務の分離と最小構成を重視し、ワークフロー設計に基づいてTask構成を決定する。

### 2.2 目的

ワークフロー設計JSONに基づき、フォルダ構造とファイル配置を計画し、JSONスキーマに準拠した形式で出力する。

### 2.3 責務

| 責務             | 成果物         |
| ---------------- | -------------- |
| フォルダ構造設計 | 構造計画JSON   |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント           | 適用方法                   |
| --------------------------- | -------------------------- |
| 18-skills.md §3             | 標準フォルダ構造に準拠     |
| Clean Architecture (Martin) | 責務の分離原則を適用       |

> 詳細: See [references/skill-structure.md](.claude/skills/skill-creator/references/skill-structure.md)

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                                |
| -------- | --------------------------------------------------------- |
| 1        | ワークフロー設計JSONを読み込む                            |
| 2        | LLM Taskごとにagents/*.mdの必要性を判断                   |
| 3        | Script Taskごとにscripts/*.jsの必要性を判断              |
| 4        | スキーマ定義が必要ならschemas/*.jsonを計画                |
| 5        | 詳細知識が必要ならreferences/*.mdを計画                   |
| 6        | テンプレートが必要ならassets/を計画                       |
| 7        | 各ファイルの責務を単一責務で定義                          |
| 8        | 構造計画JSONを出力                                        |
| 9        | スキーマ検証を実行                                        |

### 4.2 ディレクトリ必要性の判断基準

| ディレクトリ | 必要な場合                         |
| ------------ | ---------------------------------- |
| agents/      | LLM Taskが存在する                 |
| scripts/     | Script Taskが存在する              |
| schemas/     | LLM Taskの出力検証が必要           |
| references/  | SKILL.mdが500行を超えそう          |
| assets/      | テンプレートが必要                 |

### 4.3 チェックリスト

| 項目                           | 基準                             |
| ------------------------------ | -------------------------------- |
| 必要最小限か                   | 目的に紐づいたリソースのみ       |
| 責務単位で分離か               | 1ファイル=1責務                  |
| 空ディレクトリがないか         | ファイルなしのディレクトリは不要 |
| SKILL.mdが含まれているか       | 必須ファイル                     |

### 4.4 ビジネスルール（制約）

| 制約             | 説明                                   |
| ---------------- | -------------------------------------- |
| 必須ファイル     | SKILL.mdのみ必須、他は任意             |
| 禁止ファイル     | README.md等の補助ドキュメント          |
| 責務分離         | 1ファイル=1責務                        |
| スキーマ準拠     | schemas/structure-plan.json に準拠必須 |

---

## 5. インターフェース

### 5.1 入力

| データ名             | 提供元          | 検証ルール       | 欠損時処理     |
| -------------------- | --------------- | ---------------- | -------------- |
| ワークフロー設計JSON | design-workflow | スキーマに準拠   | 前Taskに再要求 |

### 5.2 出力

| 成果物名     | 受領先              | 内容                               |
| ------------ | ------------------- | ---------------------------------- |
| 構造計画JSON | generate_skill_md.js | フォルダ構造、ファイル一覧       |

#### 出力テンプレート

```json
{
  "skillName": "{{skill-name}}",
  "directories": {
    "agents": {
      "required": true,
      "reason": "{{LLM Taskが存在するため}}"
    },
    "scripts": {
      "required": true,
      "reason": "{{Script Taskが存在するため}}"
    },
    "schemas": {
      "required": true,
      "reason": "{{LLM Task出力の検証が必要なため}}"
    },
    "references": {
      "required": false,
      "reason": "{{SKILL.mdが500行以内のため不要}}"
    },
    "assets": {
      "required": false,
      "reason": "{{テンプレートが不要なため}}"
    }
  },
  "files": [
    {
      "path": "SKILL.md",
      "type": "skill-md",
      "responsibility": "ナビゲーション・概要"
    },
    {
      "path": "agents/{{task-name}}.md",
      "type": "agent",
      "responsibility": "{{単一責務}}",
      "executionPattern": "{{seq|par|cond|loop|agg}}"
    },
    {
      "path": "scripts/{{script-name}}.js",
      "type": "script",
      "responsibility": "{{単一責務}}"
    },
    {
      "path": "schemas/{{schema-name}}.json",
      "type": "schema",
      "responsibility": "{{検証対象}}"
    }
  ],
  "workflow": {
    "summary": "{{ワークフローの概要}}",
    "anchors": [],
    "trigger": {}
  }
}
```

### 5.3 出力検証

```bash
node scripts/validate_plan.js --input .tmp/structure-plan.json
```
