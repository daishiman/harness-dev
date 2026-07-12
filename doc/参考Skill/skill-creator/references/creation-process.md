# 新規作成プロセス（§6.1-6.7）

> 18-skills.md §6 新規作成部分の要約
> **相対パス**: `references/creation-process.md`
> **原典**: `docs/00-requirements/18-skills.md` §6.1-6.7

---

## Collaborative モード（推奨）

SKILL.md で推奨されるモード。ユーザーと対話しながら段階的にスキルを共創する。

```
Phase 0-0: 問題発見 → problem-definition.json
      ↓
Phase 0.5: ドメインモデリング → domain-model.json
      ↓
Phase 0-1〜0-8: インタビュー → interview-result.json
      ↓
[分岐] multiSkillPlan がある場合:
  Phase 0.9: マルチスキル設計 (design-multi-skill) → multi-skill-graph.json
  → 各サブスキルに対して以下を繰り返し:
      ↓
リソース選択: select-resources.md → resource-selection.json
      ↓
Phase 1: 要求分析 → Phase 2: 設計
      ↓
[条件] skillDependencies がある場合:
  Phase 2.5: 依存関係解決 (resolve-skill-dependencies) → skill-dependency-graph.json
      ↓
Phase 3: 構造計画 → Phase 4: 生成
      ↓
[条件] externalCliAgents がある場合:
  Phase 4.5: 外部CLIエージェント委譲 (delegate-to-external-cli) → external-cli-result.json
      ↓
Phase 5: レビュー → Phase 6: 検証
```

---

## Create モード（手動）

手動でStep 1-6を順に実行するモード。

```
1. 具体例でスキルを理解する
       ↓
2. 再利用可能なスキルコンテンツを計画する
       ↓
3. スキルを初期化する（init_skill.js）
       ↓
4. スキルを編集する（リソース実装 + SKILL.md 作成）
       ↓
5. スキルを検証する（quick_validate.js）
       ↓
6. 実際の使用に基づいてイテレーション
```

---

## Step 1: 具体例でスキルを理解する

**確認すべき質問**:

| 質問                                                   | 目的                     |
| ------------------------------------------------------ | ------------------------ |
| このスキルはどのような機能をサポートすべきか？         | 機能範囲の明確化         |
| このスキルがどのように使用されるか、例を挙げられるか？ | 具体的なユースケース特定 |
| このスキルをトリガーするためにユーザーは何と言うか？   | 発動条件の定義           |
| 参照すべき書籍や知識体系は何か？                       | 知識圧縮アンカーの選定   |

**完了条件**: スキルがサポートすべき機能の明確な理解が得られた時点

---

## Step 2: 再利用可能なスキルコンテンツを計画する

具体例を効果的なスキルに変換するため、各例を分析：

1. 例をゼロから実行する方法を検討
2. 繰り返し実行時に役立つスクリプト、参照資料、素材を特定
3. 参照すべき書籍を特定（コンテキスト圧縮）
4. Task分割（agents/）を必須分析対象にする

### 分析パターン

| パターン             | 問題                         | 解決策                                       |
| -------------------- | ---------------------------- | -------------------------------------------- |
| コード重複           | 同じコードを毎回書き直す     | `scripts/{{script-name}}.js` にスクリプト化 |
| ボイラープレート重複 | 同じテンプレートを毎回作成   | `assets/{{template-name}}/` に素材化         |
| 知識再発見           | 同じ情報を毎回調査           | `references/{{reference-name}}.md` に参照化  |
| 原則適用             | 同じ判断基準を毎回思い出す   | `references` に書籍参照として知識体系を圧縮  |
| 思考ログ肥大         | 探索・試行錯誤がメインに残る | agents/ に Task化して隔離                    |
| フェーズ混線         | リサーチと生成が同窓で混ざる | Taskをフェーズ単位で分ける                   |
| 知識ベタ書き         | SKILL/agents が肥大          | references へ外部化                          |
| 制約違反             | 文字数/形式/品質が崩れる     | scripts/ に検証スクリプトを用意              |

---

## Step 3: スキルを初期化する

新規スキルを作成する場合、常に `init_skill.js` を実行：

```bash
node scripts/init_skill.js <skill-name> --path .claude/skills --resources agents,references
```

**注記**: `--resources` は構造設計書で選定したリソースに合わせる。

---

## Step 4: スキルを編集する

### 再利用可能コンテンツから開始

| 順序 | 対象          | 内容                         |
| ---- | ------------- | ---------------------------- |
| 1    | `scripts/`    | 繰り返しコードをスクリプト化 |
| 2    | `references/` | 知識を外部化                 |
| 3    | `assets/`     | テンプレートを配置           |

### SKILL.md を更新

**Frontmatter テンプレ**:

```yaml
---
name: { { skill-name } }
description: |
  {{スキルの機能説明（2〜3行）}}

  Anchors:
  • {{ドキュメント/ルール/スキーマ/書籍名など}} / 適用: {{適用範囲}} / 目的: {{目的}}

  Trigger:
  Use when {{発動条件}}.
  {{word1}}, ..., {{wordN}}
allowed-tools:
  - { { tool1 } }
---
```

---

## Step 5: スキルを検証する

```bash
node scripts/quick_validate.js .claude/skills/<skill-name>
```

---

## Step 6: イテレーション

| ステップ | 内容                                                  |
| -------- | ----------------------------------------------------- |
| 1        | 実際のタスクでスキルを使用                            |
| 2        | 苦戦や非効率に気づく                                  |
| 3        | SKILL.md またはバンドルリソースをどう更新すべきか特定 |
| 4        | 変更を実装して再テスト                                |
| 5        | `scripts/log_usage.js` でフィードバックを記録        |

---

## 関連リソース

- **更新プロセス**: See [update-process.md](update-process.md)
- **フィードバック**: See [feedback-loop.md](feedback-loop.md)
