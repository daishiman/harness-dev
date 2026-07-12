# クロススキル参照パターン集

> **読み込み条件**: skillDependencies がある場合、または既存スキルとの連携設計時
> **相対パス**: `references/cross-skill-reference-patterns.md`

---

## 概要

スキル間で参照・呼び出しを行うためのパターン集。
Claude Code の Read/Bash/Task ツールを活用し、スキル間の連携を実現する。

---

## 参照タイプ一覧

| タイプ           | 方向       | 実行方法                    | ユースケース                     |
| ---------------- | ---------- | --------------------------- | -------------------------------- |
| `read-only`      | 一方向     | Read ツールでファイル読込   | 設計パターン参照、スキーマ共有   |
| `execute-script` | 一方向     | Bash ツールでスクリプト実行 | データ変換、検証処理             |
| `invoke-agent`   | 一方向     | Read → 指示に従い実行       | 分析・設計の委譲                 |
| `chain-step`     | 双方向     | オーケストレーション内       | パイプライン、ワークフロー       |

---

## パターン1: read-only（読み取り専用参照）

### 概要
他スキルのリファレンスやスキーマを読み込んで参考にする。最も軽量な連携。

### 実装方法

SKILL.md に参照先を記述:
```markdown
## 依存スキル

| スキル名    | 参照目的        | 参照パス                                        |
| ----------- | --------------- | ----------------------------------------------- |
| prompt-creator | プロンプト設計参照 | `../prompt-creator/references/7-layer.md` |
```

実行時の動作:
```
Read("../prompt-creator/references/7-layer.md")
→ 内容を参考にして設計に反映
```

### 適用場面
- 設計パターンの参照
- 型定義・スキーマの参照
- ベストプラクティスの参照

---

## パターン2: execute-script（スクリプト実行）

### 概要
他スキルが提供するスクリプトを直接実行する。決定論的処理の再利用。

### 実装方法

スキルの scripts/ に公開用スクリプトを配置:
```
.claude/skills/data-processor/
├── scripts/
│   ├── transform.js          # 内部用
│   └── public_transform.js   # 公開用（他スキルから呼び出し可能）
```

呼び出し側:
```bash
# 相対パスで実行
node ../../data-processor/scripts/public_transform.js \
  --input ./data/input.json \
  --output ./data/output.json
```

### 公開スクリプトの規約

```javascript
// public_transform.js
// @public - 他スキルから呼び出し可能
// @input: --input <path> 入力JSONファイルパス
// @output: --output <path> 出力JSONファイルパス
// @exit-codes: 0=成功, 1=入力エラー, 2=変換エラー

import { getArg, EXIT_CODES } from '../scripts/utils.js';
// ... 実装
```

### 適用場面
- データ変換処理の共有
- 検証ロジックの再利用
- 決定論的な計算処理

---

## パターン3: invoke-agent（エージェント呼び出し）

### 概要
他スキルのエージェント定義を読み込み、その指示に従って処理を実行する。

### 実装方法

呼び出し側が Read でエージェント定義を読み込む:
```
Read("../analysis-skill/agents/analyze-data.md")
→ エージェント定義に記載された思考プロセスとチェックリストに従って実行
```

### 規約
- エージェントは自己完結型で、前提条件が明確であること
- 入出力インターフェースが定義されていること
- 呼び出し側は必要な入力を準備してから読み込むこと

### 適用場面
- 専門的な分析・設計の委譲
- 品質チェックの実行
- ドキュメント生成の委譲

---

## パターン4: chain-step（チェーンステップ）

### 概要
オーケストレーション定義内でスキルをステップとして組み込む。

### 実装方法

```yaml
# orchestration.yaml
steps:
  - id: collect
    skill: data-collector
    skill_path: "../data-collector"
    script: "scripts/collect.js"
    args:
      source: "{{trigger.source}}"

  - id: transform
    skill: data-transformer
    skill_path: "../data-transformer"
    script: "scripts/transform.js"
    input_mapping:
      data: "{{collect.output}}"

  - id: report
    skill: report-generator
    skill_path: "../report-generator"
    script: "scripts/generate.js"
    input_mapping:
      data: "{{transform.output}}"
```

### 適用場面
- 複数スキルを連携させたパイプライン
- ETL（Extract-Transform-Load）処理
- マルチステップワークフロー

---

## 依存関係の方向ルール

### 許可される依存

```
[leaf-skill] → [core-skill]     # 末端→コア（OK）
[feature-skill] → [util-skill]  # 機能→ユーティリティ（OK）
[skill-a] → [shared-types]      # 独立スキル→共有型（OK）
```

### 禁止される依存

```
[skill-a] → [skill-b] → [skill-a]  # 循環依存（NG）
[core-skill] → [leaf-skill]         # コア→末端（NG: 依存方向逆転）
```

### 依存方向の原則（Clean Architecture）

```
外側（具体） → 内側（抽象）

具体スキル → 共通スキーマ → 共通インターフェース
```

---

## SKILL.md への依存関係記述テンプレート

```markdown
## 依存関係

### このスキルが参照するスキル（dependsOn）

| スキル名         | 参照タイプ      | 参照パス                              | 必須 |
| ---------------- | --------------- | ------------------------------------- | ---- |
| shared-schemas   | read-only       | `../shared-schemas/schemas/*.json` | Yes  |
| data-transformer | execute-script  | `../data-transformer/scripts/transform.js` | No |

### このスキルを参照するスキル（dependedBy）

| スキル名         | 公開インターフェース | 公開パス                        |
| ---------------- | -------------------- | ------------------------------- |
| report-generator | script               | `scripts/public_analyze.js`     |
| dashboard-skill  | schema               | `schemas/analysis-result.json`  |
```

---

## 相対パス計算早見表

すべてのスキルは `.claude/skills/<skill-name>/` に配置される前提。
repo に `.agents/skills/` が存在しても、それは mirror または runtime 補助であり、**仕様更新の正本は `.claude/skills/`** とする。

| From (呼び出し元)         | To (呼び出し先)                        | 相対パス                                  |
| ------------------------- | -------------------------------------- | ----------------------------------------- |
| `skills/skill-a/SKILL.md`| `skills/skill-b/SKILL.md`             | `../skill-b/SKILL.md`                     |
| `skills/skill-a/scripts/` | `skills/skill-b/scripts/foo.js`       | `../../skill-b/scripts/foo.js`            |
| `skills/skill-a/agents/`  | `skills/skill-b/agents/analyze.md`    | `../../skill-b/agents/analyze.md`         |
| `skills/skill-a/schemas/` | `skills/skill-b/schemas/result.json`  | `../../skill-b/schemas/result.json`       |

### canonical root / mirror ルール

| 項目 | ルール |
| --- | --- |
| canonical root | system spec / skill spec の更新先は `.claude/skills/...` を正本とする |
| mirror root | `.agents/skills/...` は参照互換や runtime 用 mirror として扱い、正本更新の代替にしない |
| workflow 記述 | `phase-12-documentation.md` / `spec-update-summary.md` / outputs に `.agents/skills/.../references/` を正本として書かない |
| 監査方法 | `rg -n "\\.agents/skills/.+references" docs/30-workflows/<workflow>` で mirror 側参照残存を確認する |

---

## 変更履歴

| Version | Date       | Changes           |
| ------- | ---------- | ----------------- |
| 1.1.0   | 2026-02-13 | SKILL.mdレベルからの相対パス計算エラー修正（`../../` → `../`）。テーブル・コード例・テンプレート計8箇所 |
| 1.0.0   | 2026-02-13 | 初版作成          |
