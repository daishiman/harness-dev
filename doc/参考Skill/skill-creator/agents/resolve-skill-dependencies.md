# Task仕様書：クロススキル依存関係解決（Phase 2.5）

> **読み込み条件**: skillDependencies が interview-result.json に存在する場合
> **相対パス**: `agents/resolve-skill-dependencies.md`
> **Phase**: 2.5（Phase 2（設計）の後、Phase 3（構造計画）の前）

## 1. メタ情報

| 項目     | 内容                             |
| -------- | -------------------------------- |
| 名前     | Dependency Resolver              |
| 専門領域 | スキル間依存関係・インターフェース設計 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

**単一スキル**の依存関係（呼び出し・被呼び出し）を解決し、相対パスによる参照構造を設計する。
既存スキルのSKILL.mdを読み込み、公開インターフェースを特定し、新規スキルとの接続点を定義する。

> **責務境界**: 本エージェントは「1つの新規スキル」から「既存スキル群」への依存解決を担当する。
> 複数スキルを同時に新規作成する場合の全体グラフ設計は `design-multi-skill.md` が担当する。
> design-multi-skill.mdが全体設計を行った後、個々のスキルの依存解決で本エージェントが呼ばれる。

### 2.2 目的

> **責務境界**: 本エージェントは**単一スキル**の外部依存関係を解決する。複数スキルの同時作成・相互依存関係は `design-multi-skill.md` が担当する。呼び出しコンテキスト: (1) 単一スキル作成時: select-resources後に直接呼び出し (2) マルチスキル作成時: design-multi-skill.md から各サブスキルに対して呼び出し

interview-result.json の `skillDependencies` に基づき、以下を実現する：

1. 依存先スキルの存在確認と公開インターフェース特定
2. 相対パスによる参照パス計算
3. 被依存スキルへの公開インターフェース設計
4. 依存関係グラフ（DAG）の構築と循環依存検出
5. マルチスキル作成時の作成順序決定

### 2.3 責務

| 責務                   | 成果物                        |
| ---------------------- | ----------------------------- |
| 依存関係解決           | skill-dependency-graph.json   |
| 相対パス計算           | 各依存への相対パスマッピング  |
| 循環依存検出           | エラー報告（循環があれば）    |
| 作成順序決定           | トポロジカルソート順          |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント                                 | 適用方法                           |
| ------------------------------------------------- | ---------------------------------- |
| Clean Architecture (Robert C. Martin)             | 依存関係の方向制御                 |
| references/cross-skill-reference-patterns.md       | クロススキル参照パターン集         |
| references/skill-structure.md                      | スキルディレクトリ構造仕様         |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                                     | 担当   |
| -------- | -------------------------------------------------------------- | ------ |
| 1        | interview-result.json の skillDependencies を読み込む          | LLM    |
| 2        | dependsOn の各スキルの SKILL.md を Read ツールで読み込む       | LLM    |
| 3        | 各スキルの公開インターフェース（scripts, agents, schemas）を特定 | LLM    |
| 4        | 新規スキルから各依存先への相対パスを計算                       | LLM    |
| 5        | dependedBy の各スキルに対する公開インターフェースを設計         | LLM    |
| 6        | 依存関係グラフ（DAG）を構築しJSONとして出力                    | LLM    |
| 7        | `validate_all.js` でグラフの循環依存検出・DAG検証を実行        | Script |
| 7.5      | required=true の依存先が `.claude/skills/` に存在しない場合、エラー報告 | LLM |
| 7.7      | sharedResources[] の検証 - 各リソースパスの存在確認、オーナースキルの存在確認、consumers の妥当性チェックを行い、検証結果を出力の sharedResources に反映する | LLM |
| 8        | 検証エラーがあれば修正、なければ続行                            | LLM    |
| 9        | skill-dependency-graph.json を最終出力                         | LLM    |

> **Script First原則**: DAG検証・循環依存検出・トポロジカルソートは決定論的処理のため、
> LLMではなく `validate_all.js` のグラフ検証機能で実行する。
> LLMはグラフの構築と結果の解釈を担当する。

> **required=true 依存先の存在検証（ステップ7.5）**: required=true の依存先スキルが
> `.claude/skills/` に存在しない場合、エラーとして報告し、ユーザーにオプションを提示する：
> 1. 依存先を先に作成する
> 2. required を false に変更する
> 3. 作成を中止する

### 4.2 相対パス計算ルール

| 条件                                | 相対パス例                                      |
| ----------------------------------- | ----------------------------------------------- |
| 同階層のスキル間                    | `../../other-skill/scripts/foo.js`              |
| スキル→エージェント参照             | `../../other-skill/agents/some-agent.md`        |
| スキル→リファレンス参照             | `../../other-skill/references/guide.md`         |
| スキル→スキーマ参照                 | `../../other-skill/schemas/result.json`         |

**基本ルール**: `.claude/skills/` を基点として、各スキルは `skill-name/` ディレクトリ配下にある。
スキルA (`skills/skill-a/`) からスキルB (`skills/skill-b/`) への参照は `../../skill-b/...` となる。

### 4.3 参照タイプ別の実行方法

| referenceType   | 実行方法                                              | Claude Code実装                          |
| --------------- | ----------------------------------------------------- | ---------------------------------------- |
| `read-only`     | Read ツールで参照先を読み込むのみ                     | `Read(path)` でファイル内容を取得        |
| `execute-script`| 参照先スクリプトを Bash ツールで実行                  | `Bash("node ../../other/scripts/x.js")` |
| `invoke-agent`  | 参照先エージェントを Task ツールで読み込み実行        | `Read` → エージェント指示に従い実行      |
| `chain-step`    | スキルチェーンのステップとして組み込み                | orchestration定義に参照パスを埋め込み    |

### 4.4 チェックリスト

| 項目                                 | 基準                                    |
| ------------------------------------ | --------------------------------------- |
| 依存先スキルが存在するか             | SKILL.md が読める                       |
| 参照先ファイルが存在するか           | 相対パス先にファイルがある              |
| 循環依存がないか                     | DAGが有効（トポロジカルソート可能）     |
| 公開インターフェースが明確か         | exposedPaths が具体的                   |
| 相対パスが正しいか                   | パス解決テストをパス                    |

### 4.5 ビジネスルール（制約）

| 制約               | 説明                                                     |
| ------------------ | -------------------------------------------------------- |
| 循環依存禁止       | A→B→C→A のような循環は許可しない                        |
| 公開範囲最小化     | 必要なファイルのみ公開する（全ファイル公開禁止）         |
| バージョン互換     | 依存先スキルのバージョンとの互換性を確認                 |
| オプショナル依存   | required=false の依存は、スキル不在時でも動作する設計    |

---

## 5. インターフェース

### 5.1 入力

| データ名              | 提供元            | 検証ルール                    | 欠損時処理           |
| --------------------- | ----------------- | ----------------------------- | -------------------- |
| interview-result.json | interview-user.md | skillDependencies が存在      | この Agent をスキップ |

### 5.2 出力

| 成果物名                    | 受領先           | 内容                             |
| --------------------------- | ---------------- | -------------------------------- |
| skill-dependency-graph.json | Phase 3以降      | 依存関係グラフと相対パスマッピング |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/skill-dependency-graph.json",
  "skillName": "新規スキル名",
  "dependencies": [
    {
      "skillName": "参照先スキル名",
      "skillPath": ".claude/skills/referenced-skill",
      "relativePath": "../../referenced-skill",
      "referenceType": "execute-script",
      "interfaces": [
        {
          "type": "script",
          "path": "scripts/some_script.js",
          "fullRelativePath": "../../referenced-skill/scripts/some_script.js",
          "description": "スクリプトの説明"
        }
      ],
      "required": true,
      "verified": true
    }
  ],
  "exposedInterfaces": [
    {
      "path": "scripts/public_api.js",
      "type": "script",
      "consumers": ["calling-skill"],
      "description": "公開APIの説明"
    }
  ],
  "sharedResources": [],
  "graphValidation": {
    "isDAG": true,
    "hasCycles": false,
    "topologicalOrder": ["skill-a", "skill-b", "skill-c"]
  }
}
```

### 5.3 後続処理

```bash
# Phase 3（構造計画）で skill-dependency-graph.json を参照
# 依存先スキルのインターフェースに基づいてスキル構造を設計
# SKILL.md 生成時に依存関係セクションを自動追加
```
