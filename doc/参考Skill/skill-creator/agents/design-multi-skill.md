# Task仕様書：マルチスキル設計（Phase 0.9）

> **読み込み条件**: multiSkillPlan が interview-result.json に存在する場合
> **相対パス**: `agents/design-multi-skill.md`
> **Phase**: 0.9（インタビュー後、リソース選択の前）

## 1. メタ情報

| 項目     | 内容                                 |
| -------- | ------------------------------------ |
| 名前     | Multi-Skill Architect                |
| 専門領域 | 複数スキル同時設計・依存関係グラフ構築 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

大規模なスキルエコシステムを構築する際に、複数のスキルを同時に設計・作成する。
各スキル間の依存関係、共有リソース、公開インターフェースを統合的に管理する。

### 2.2 目的

interview-result.json の `multiSkillPlan` に基づき、以下を実現する：

1. 各スキルの役割分担と境界の明確化（Bounded Context）
2. 依存関係グラフの構築と作成順序の決定
3. 共有リソースの配置戦略
4. 各スキルの interview-result.json サブセットを生成
5. 順序に従い各スキルの作成を制御

### 2.3 責務

| 責務                   | 成果物                          |
| ---------------------- | ------------------------------- |
| 境界定義               | 各スキルの Bounded Context      |
| 依存関係グラフ         | multi-skill-graph.json          |
| 作成順序決定           | トポロジカルソート順            |
| 個別スキル仕様生成     | 各スキルの interview-result.json |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                                | 適用方法                          |
| ------------------------------------------------ | --------------------------------- |
| Domain-Driven Design (Eric Evans)                | Bounded Context・Context Map      |
| Clean Architecture (Robert C. Martin)            | 依存関係の方向制御                |
| references/cross-skill-reference-patterns.md      | スキル間参照パターン              |
| references/skill-chain-patterns.md               | スキルチェーンパターン            |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                                      | 担当            |
| -------- | --------------------------------------------------------------- | --------------- |
| 1        | multiSkillPlan.skills を読み込む                                | LLM             |
| 2        | 各スキルの役割から Bounded Context を定義                       | LLM             |
| 3        | dependencyGraph を解析し DAG を構築                             | LLM             |
| 4        | 循環依存を検出（あればエラー）                                  | LLM             |
| 5        | トポロジカルソートで作成順序を決定                              | LLM             |
| 6        | 共有リソースの配置を決定（オーナーシップ割り当て）              | LLM             |
| 7        | 各スキルの個別 interview-result.json を生成                     | LLM             |

> **skillDependencies自動生成**: multiSkillPlan.dependencyGraph から各スキルの
> skillDependencies.dependsOn / dependedBy を自動算出する。
> 例: dependencyGraph が `{"skill-a": ["skill-b"]}` の場合:
> - skill-a の dependsOn に `{"skillName": "skill-b", ...}` を追加
> - skill-b の dependedBy に `{"skillName": "skill-a", ...}` を追加

| 8        | ユーザーに全体設計を提示して確認                                | AskUserQuestion |
| 9        | 承認後、作成順序に従って各スキルの作成を開始                    | LLM             |
| 10       | 各スキルに対して Phase 1-6 を順次実行                           | LLM (Task)      |
| 11       | 各スキル完了後に依存関係の接続を検証                            | Script          |
| 12       | 全スキル完了後に統合テストを実施                                | Script          |

### 4.2 マルチスキル設計パターン

#### Hub-and-Spoke（ハブ＆スポーク）

```
        [spoke-a]
            ↑
[spoke-b] ← [hub] → [spoke-c]
            ↓
        [spoke-d]
```

中心スキル（hub）が共通機能を提供し、周辺スキル（spoke）が特化機能を実装。

| 役割  | 特徴                           | 例                               |
| ----- | ------------------------------ | -------------------------------- |
| Hub   | 共通ユーティリティ・型定義     | shared-utils, core-types         |
| Spoke | 特化機能・独立して動作可能     | api-connector, report-generator  |

#### Pipeline（パイプライン）

```
[skill-a] → [skill-b] → [skill-c] → [skill-d]
```

各スキルの出力が次のスキルの入力になる。

#### Mesh（メッシュ）

```
[skill-a] → [skill-b]
    ↑    ↗        ↓
[skill-c] ← [skill-d]
```

多数のスキルが密に接続するパターン。**全ての辺は単方向**であり、DAGを維持する。
双方向の参照が必要な場合は、インターフェース層を分離する：

| 参照方向      | 方法                                                    |
| ------------- | ------------------------------------------------------- |
| A → B（直接） | A が B の script/schema を `execute-script` で参照      |
| B → A（逆方向）| B が A の reference を `read-only` で参照（実行依存なし）|

> **注意**: 双方向に見える関係も、参照タイプを分離することでDAGとして表現できる。
> 「A が B のスクリプトを実行する」と「B が A のリファレンスを読む」は異なる依存レベルであり、
> 循環依存には該当しない。ただし、同一参照タイプでの双方向依存は禁止。

### 4.3 共有リソース配置戦略

| 戦略             | 説明                                         | 適用場面                 |
| ---------------- | -------------------------------------------- | ------------------------ |
| Owner Pattern    | 1つのスキルがリソースを所有し、他が参照する  | 型定義、共通スキーマ     |
| Shared Skill     | 共有専用スキルを作成                         | 共通ユーティリティが多い |
| Copy Pattern     | 各スキルにコピーを配置                       | 独立性を重視する場合     |

### 4.4 チェックリスト

| 項目                                       | 基準                                |
| ------------------------------------------ | ----------------------------------- |
| 各スキルの境界が明確か                     | 責務の重複がない                    |
| 依存関係グラフに循環がないか               | DAGとして有効                       |
| 共有リソースのオーナーが決まっているか     | 各リソースに1つのオーナー           |
| 作成順序が依存関係を満たすか               | 依存先が先に作成される              |
| 各スキルが単独でも動作するか（可能な場合） | オプショナル依存の適切な処理        |

### 4.5 ビジネスルール（制約）

| 制約               | 説明                                             |
| ------------------ | ------------------------------------------------ |
| 循環依存禁止       | 直接・間接の循環を許可しない                     |
| 最大スキル数       | 一度に作成するスキルは10個まで                   |
| 段階的作成         | 依存先スキルの検証完了後に次のスキルを作成       |
| 個別検証           | 各スキルは validate_all.js で個別に検証           |
| 順序の正本         | `topologicalOrder` が作成順序の正本。`skills[].creationOrder` は参照用の派生値 |

### 4.6 失敗リカバリ戦略

スキル作成中に失敗が発生した場合の対応:

| 戦略 | 説明 | 適用場面 |
| --- | --- | --- |
| stop-on-failure | 即座に停止し、ユーザーに判断を委ねる | デフォルト。依存先の失敗時 |
| skip-and-continue | 失敗したスキルをスキップし、依存元も自動スキップ | 独立性の高いスキル群 |
| retry-then-skip | リトライ後にスキップ | 外部要因による一時的失敗 |

#### リカバリフロー

1. 失敗発生 → multi-skill-graph.json の `failureRecovery` を更新
2. 依存元スキルへの影響を自動判定（DAGを逆走査）
3. ユーザーに状況報告と選択肢を提示
4. 選択に応じて継続 or 中止
5. 完了済みスキルは `completedSkills` に記録（再実行時にスキップ）

> **creationOrder と dependencyGraph の関係**:
> `interview-result.json` の `multiSkillPlan.skills[].creationOrder` はユーザーの暫定値であり、
> 本エージェントが `dependencyGraph` からトポロジカルソートを実行して `topologicalOrder` を算出する。
> 矛盾がある場合は `topologicalOrder` が常に優先される。
> `skills[].creationOrder` は `topologicalOrder` から自動算出し、ユーザーの暫定値は上書きする。

---

## 5. インターフェース

### 5.1 入力

| データ名              | 提供元            | 検証ルール                   | 欠損時処理           |
| --------------------- | ----------------- | ---------------------------- | -------------------- |
| interview-result.json | interview-user.md | multiSkillPlan が存在        | この Agent をスキップ |

### 5.2 出力

| 成果物名                              | 受領先              | 内容                                    |
| ------------------------------------- | ------------------- | --------------------------------------- |
| multi-skill-graph.json                | 各サブスキルのPhase 1以降 | マルチスキル依存関係グラフ              |
| {skill-name}-interview-result.json    | 各スキルのPhase 0   | 個別スキルのインタビュー結果            |

#### multi-skill-graph.json スキーマ

```json
{
  "projectName": "プロジェクト名",
  "pattern": "hub-and-spoke | pipeline | mesh",
  "skills": [
    {
      "name": "skill-a",
      "role": "スキルの役割",
      "boundedContext": "Bounded Context名",
      "creationOrder": 1,
      "dependencies": ["skill-b"],
      "exposedInterfaces": [
        { "type": "script", "path": "scripts/public.js" }
      ],
      "status": "pending"
    }
  ],
  "sharedResources": [
    {
      "resourcePath": "schemas/shared-types.json",
      "owner": "skill-a",
      "consumers": ["skill-b", "skill-c"]
    }
  ],
  "dependencyGraph": {
    "skill-b": [],
    "skill-a": ["skill-b"],
    "skill-c": ["skill-a", "skill-b"]
  },
  "topologicalOrder": ["skill-b", "skill-a", "skill-c"],
  "validation": {
    "isDAG": true,
    "totalSkills": 3,
    "totalDependencies": 3
  },
  "failureRecovery": {
    "strategy": "stop-on-failure",
    "maxRetries": 1,
    "completedSkills": [],
    "failedSkills": []
  }
}
```

### 5.3 後続処理

各スキルの作成は以下のフローで実行する:

1. topologicalOrder[0] のスキルから開始
2. 各スキルに対して:
   a. 個別の interview-result.json を `.tmp/{skill-name}-interview-result.json` に配置
   b. select-resources.md → resource-selection.json を生成
   c. Phase 1 (analyze-request) → Phase 2 (design) を順次実行
   c2. skillDependencies がある場合: Phase 2.5 (resolve-skill-dependencies) を実行
   d. Phase 3 (plan-structure) → Phase 4 (generate) を順次実行
   d2. externalCliAgents がある場合: Phase 4.5 (delegate-to-external-cli) を実行
   e. Phase 5 (review) → Phase 6 (validate) を順次実行
   f. 検証成功後、multi-skill-graph.json の status を "completed" に更新
3. 全スキル完了後:
   a. 共有リソースの参照パスを検証
   b. 公開インターフェースの整合性を確認
