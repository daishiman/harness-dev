# Domain Modeling Guide for Skill Design

> **読み込み条件**: ドメイン分析時、Phase 0.5（ドメインモデリング）
> **相対パス**: `references/domain-modeling-guide.md`

---

## 目的

DDD（Domain-Driven Design）の手法をスキル設計に適用し、
スキルの**ドメイン境界**、**ユビキタス言語**、**責務構造**を明確にする。

---

## 1. スキルのドメイン分類

### 1.1 Strategic Design（戦略的設計）

スキルのドメインを3層に分類し、設計の力点を決定する。

| ドメイン種別      | 定義                               | 設計方針                     | 例                          |
| ----------------- | ---------------------------------- | ---------------------------- | --------------------------- |
| Core Domain       | スキルの存在理由そのもの           | 最も注力、独自のロジック     | PR分析ロジック              |
| Supporting Domain | Coreを支援する必要な機能           | 標準的な実装でよい           | テンプレート生成            |
| Generic Domain    | 汎用的な機能（どのスキルでも同じ） | 既存ライブラリ・共通処理活用 | ファイルI/O、バリデーション |

**判定質問**:

| 質問                                   | Core | Supporting | Generic |
| -------------------------------------- | ---- | ---------- | ------- |
| これがないとスキルの意味がなくなるか？ | Yes  | No         | No      |
| このスキル固有のロジックが必要か？     | Yes  | Maybe      | No      |
| 汎用ライブラリで代替できるか？         | No   | Maybe      | Yes     |

### 1.2 ドメイン分類の出力

```json
{
  "coreDomain": {
    "name": "コアドメイン名",
    "description": "このスキルの本質的な価値を提供する領域",
    "keyBehaviors": ["中核となる振る舞い1", "中核となる振る舞い2"]
  },
  "supportingDomains": [
    {
      "name": "サポートドメイン名",
      "description": "コアを支える領域",
      "canBeSimplified": true
    }
  ],
  "genericDomains": [
    {
      "name": "汎用ドメイン名",
      "reuseStrategy": "既存scripts/共通ユーティリティを活用"
    }
  ]
}
```

---

## 2. ユビキタス言語（Ubiquitous Language）

### 2.1 定義

スキル内で使用する用語を統一し、曖昧さを排除する。

**プロセス**:

| ステップ | アクション                                  |
| -------- | ------------------------------------------- |
| 1        | ユーザーが使う言葉を収集する                |
| 2        | 技術用語との対応を定義する                  |
| 3        | 用語集（Glossary）を作成する                |
| 4        | SKILL.md・agents・scriptsで一貫して使用する |

### 2.2 用語集テンプレート

```markdown
## 用語集

| ユーザー用語 | 技術用語    | 定義                             | 使用箇所          |
| ------------ | ----------- | -------------------------------- | ----------------- |
| レビュー     | code-review | PRに対するコード品質確認プロセス | agents/, SKILL.md |
| チェック     | validation  | 自動化された品質検証             | scripts/          |
| テンプレ     | template    | 再利用可能な定型パターン         | assets/           |
```

### 2.3 命名規則との統合

| 対象            | ユビキタス言語の適用                        |
| --------------- | ------------------------------------------- |
| agents/\*.md    | ファイル名に動詞+名詞（ドメイン用語）を使用 |
| scripts/\*.js   | 関数名にドメイン用語を使用                  |
| schemas/\*.json | プロパティ名にドメイン用語を使用            |

---

## 3. Bounded Context（境界づけられたコンテキスト）

### 3.1 スキル境界の定義

| 境界要素     | 定義                           | 質問                                 |
| ------------ | ------------------------------ | ------------------------------------ |
| 内部（In）   | スキルが責任を持つ範囲         | このスキルが直接制御するものは何か？ |
| 外部（Out）  | スキルの範囲外                 | これは別のスキルや手動作業の責務か？ |
| 接点（Port） | 外部との入出力インターフェース | スキルと外部世界の接続点はどこか？   |

### 3.2 Context Map（コンテキストマップ）

スキル間の関係を定義する。

| 関係パターン          | 説明                               | 例                           |
| --------------------- | ---------------------------------- | ---------------------------- |
| Upstream-Downstream   | 一方が他方にデータを提供           | task-spec → github-issue     |
| Shared Kernel         | 共有される共通モデル               | 共通のJSON Schema            |
| Anti-Corruption Layer | 外部モデルを自ドメインモデルに変換 | API応答→内部データ構造       |
| Published Language    | 共有される標準フォーマット         | interview-result.json Schema |

### 3.3 境界の出力

```json
{
  "boundedContext": {
    "name": "スキルのコンテキスト名",
    "inScope": ["責務1", "責務2"],
    "outOfScope": ["範囲外1", "範囲外2"],
    "ports": {
      "input": ["入力インターフェース1"],
      "output": ["出力インターフェース1"]
    }
  },
  "contextRelations": [
    {
      "target": "関連スキル/システム名",
      "pattern": "upstream-downstream | shared-kernel | acl",
      "description": "関係の説明"
    }
  ]
}
```

---

## 4. Domain Events（ドメインイベント）

スキルの重要な状態変化を特定する。

### 4.1 イベント特定

| 質問                             | 目的               |
| -------------------------------- | ------------------ |
| スキル実行中に何が「起こる」か？ | イベントの列挙     |
| どの時点で後戻りできなくなるか？ | 重要な分岐点の特定 |
| どの時点で外部に通知すべきか？   | 出力ポイントの特定 |
| どの時点でユーザー判断が必要か？ | 対話ポイントの特定 |

### 4.2 イベントとPhaseの対応

```
[SkillTriggered] → Phase 0-0: 問題発見
[ProblemDefined] → Phase 0.5: ドメインモデリング
[DomainModeled]  → Phase 0-1〜0-8: インタビュー
[RequirementsCaptured] → Phase 1: 分析
[DesignCompleted] → Phase 2: 設計
[CodeGenerated]   → Phase 3: 生成
[ValidationPassed] → Phase 4: 検証
[SkillDelivered]  → 完了
```

---

## 5. Aggregate Pattern（集約パターン）

### 5.1 スキルの構成要素を集約単位で整理

| 集約            | ルート           | 含まれる要素                         | 不変条件                    |
| --------------- | ---------------- | ------------------------------------ | --------------------------- |
| SkillDefinition | SKILL.md         | name, description, triggers          | frontmatter必須、500行以内  |
| TaskSpec        | agents/\*.md     | メタ情報, 実行仕様, インターフェース | 5セクション構造必須         |
| Script          | scripts/\*.js    | 入力, 処理, 出力, EXIT_CODES         | 決定論的処理であること      |
| Reference       | references/\*.md | 知識本文                             | agents/に知識を埋め込まない |
| Template        | assets/\*        | テンプレート定義                     | 具体値を含まない            |

### 5.2 不変条件の検証

各集約の不変条件はスクリプトで検証する:

| 集約            | 検証スクリプト        |
| --------------- | --------------------- |
| SkillDefinition | quick_validate.js     |
| TaskSpec        | validate_structure.js |
| Script          | validate_all.js       |
| Reference       | validate_links.js     |
| Template        | validate_schema.js    |

---

## 6. 適用ワークフロー

### Phase 0.5: ドメインモデリング

```
入力: problem-definition.json (Phase 0-0の成果物)
  ↓
Step 1: ドメイン分類（Core/Supporting/Generic）
  ↓
Step 2: ユビキタス言語定義
  ↓
Step 3: Bounded Context定義
  ↓
Step 4: Domain Events特定
  ↓
Step 5: Aggregate構造設計
  ↓
出力: domain-model.json
```

---

## 関連リソース

- **問題発見**: See [problem-discovery-framework.md](problem-discovery-framework.md)
- **Clean Architecture**: See [clean-architecture-for-skills.md](clean-architecture-for-skills.md)
- **構造仕様**: See [skill-structure.md](skill-structure.md)
- **Agent**: See [agents/model-domain.md](../agents/model-domain.md)
