# SKILL.md テンプレート

> 18-skills.md §3.2 準拠
> このテンプレートを使用して新規スキルの SKILL.md を作成する
> **相対パス**: `assets/skill-template.md`

---

## クイックリファレンス

| 要素        | 制約                                                 |
| ----------- | ---------------------------------------------------- |
| name        | ハイフンケース、最大64文字、ディレクトリ一致         |
| description | 最大1024文字、角括弧禁止、Markdown禁止               |
| Anchors     | 目標達成に必要十分な個数、`•` で開始（`-` `*` 禁止） |
| Trigger     | 日本語で記述（発動条件を明確に）                     |
| SKILL.md    | 500行以内                                            |

---

## Frontmatter テンプレート（§3.2.1-3.2.3）

```yaml
---
name: { { ハイフンケースのスキル名（例: database-migration） } }
description: |
  {{スキルの機能説明（2〜3行で簡潔に記述）}}

  Anchors:
  • {{アンカー1: 書籍名/ドキュメント名}} / 適用: {{適用範囲}} / 目的: {{目的}}
  • {{アンカー2: 書籍名/ドキュメント名}} / 適用: {{適用範囲}} / 目的: {{目的}}
  • {{目標達成に必要十分な個数を記述}}

  Trigger:
  {{発動条件を日本語で記述（短く、具体的な語彙を含める）}}。
  {{キーワード1}}, {{キーワード2}}, {{キーワードN}}
allowed-tools:
  - { { tool1 } }
  - { { toolN } }
---
```

---

## 本文テンプレート（§3.2.4）

```markdown
# {{スキル名（Frontmatter の name と一致）}}

## 概要

{{スキルの目的と提供する価値を1-2文で説明}}

---

## ワークフロー

{{以下から適切なパターンを選択して使用}}

### パターン A: シーケンシャル（依存関係あり）
```

task-a → task-b → task-c → task-d

```

### Task 1: {{task-a}}
{{前提なし}}

### Task 2: {{task-b}}
**依存**: task-a の出力を使用

---

### パターン B: 並列実行（独立したタスク）

```

      ┌→ task-b ─┐

start → ┼→ task-c ─┼→ aggregate
└→ task-d ─┘

```

### 並列実行グループ

以下のTaskを**並列で実行**する：

| Task   | 責務         | 独立性           |
| ------ | ------------ | ---------------- |
| task-b | {{責務B}}    | 他と依存関係なし |
| task-c | {{責務C}}    | 他と依存関係なし |
| task-d | {{責務D}}    | 他と依存関係なし |

**実行指示**: `Task tool` で複数エージェントを同時起動

### aggregate（結果集約）
**依存**: task-b, task-c, task-d すべての完了を待機

---

### パターン C: 条件分岐

```

analyze → ◇ 判断ポイント
│
├─ 条件A → workflow-a
├─ 条件B → workflow-b
└─ default → workflow-default

```

### Task 1: analyze（状況分析）

入力を分析し、以下の判断基準で分岐を決定する：

| 条件      | 判断基準      | 次のワークフロー |
| --------- | ------------- | ---------------- |
| {{条件A}} | {{判断基準A}} | workflow-a       |
| {{条件B}} | {{判断基準B}} | workflow-b       |
| それ以外  | デフォルト    | workflow-default |

---

### パターン D: ループ処理（For-Each）

```

collect-items → ↺ process-each-item → aggregate-results

```

### Task 1: collect-items（収集）
**出力**: `items[]` - 処理対象の配列

### Task 2: process-each-item（反復処理）

`items[]` の各要素に対して以下を実行：

| ステップ | アクション                  |
| -------- | --------------------------- |
| 1        | 要素を取得                  |
| 2        | {{処理内容}}を実行          |
| 3        | 結果を `results[]` に追加   |

**ループ継続条件**: `items[]` の全要素を処理するまで
**最大反復回数**: {{N回}}（無限ループ防止）

---

### パターン E: Phase ベース（大規模タスク）

```

Phase 1: {{分析}} → Phase 2: {{設計}} → Phase 3: {{実装}} → Phase 4: {{検証}}

```

### Phase 1: {{フェーズ1の名前}}

**目的**: {{このフェーズで達成すること}}

**アクション**:
1. {{具体的なアクション1}}
2. {{具体的なアクション2}}

**Task**: `agents/{{task-1}}.md` を参照
**完了条件**: {{このPhaseの完了基準}}

---

### パターン F: 組み合わせ（Phase + 並列 + 条件分岐）

```

Phase 1: 収集
collect-sources
↓
Phase 2: 処理（並列）
┌→ process-source-1 ─┐
┼→ process-source-2 ─┼→ ◇ validation
└→ process-source-3 ─┘ ├─ pass → Phase 3
└─ fail → retry (↺)
Phase 3: 出力
generate-output

```

{{複数パターンの組み合わせは references/workflow-patterns.md を参照}}

---

## Task仕様（ナビゲーション）

| Task       | 責務           | 実行パターン | 入力     | 出力     |
| ---------- | -------------- | ------------ | -------- | -------- |
| {{task-1}} | {{単一責務}}   | {{パターン}} | {{入力}} | {{出力}} |
| {{task-N}} | {{単一責務}}   | {{パターン}} | {{入力}} | {{出力}} |

**実行パターン凡例**:
- `seq`: シーケンシャル（前のTaskに依存）
- `par`: 並列実行（他と独立）
- `cond`: 条件分岐の起点
- `loop`: ループ処理の本体
- `agg`: 集約処理（並列/ループの終点）

**詳細仕様**: 各Taskの詳細は `agents/` ディレクトリを参照
**注記**: Taskは必要な分だけ定義する。不要なら agents/ は作成しない。
**注記**: Task名は目的に合わせて設計し、固定名の流用は避ける。
**注記**: Taskは責務単位で分離し、1 Task = 1 責務を基本とする。
**ワークフロー詳細**: See [references/workflow-patterns.md](references/workflow-patterns.md)

---

## ベストプラクティス

### すべきこと

| 推奨事項      | 理由                 |
| ------------- | -------------------- |
| {{推奨事項1}} | {{なぜそうすべきか}} |
| {{推奨事項N}} | {{理由}}             |

### 避けるべきこと

| 禁止事項      | 問題点               |
| ------------- | -------------------- |
| {{禁止事項1}} | {{なぜ避けるべきか}} |
| {{禁止事項N}} | {{問題点}}           |

---

## リソース参照

**注記**: scripts/references/assets は必要なセクションだけ残し、不要なら削除する。
**注記**: scripts/references/assets は責務単位で分割し、1ファイル=1責務を基本とする。
**注記**: 制約/品質条件がある場合は検証スクリプトを追加する。

### scripts/（決定論的処理）

| スクリプト                 | 機能         |
| -------------------------- | ------------ |
| `scripts/{{script-1}}.js` | {{実行スクリプトの機能}} |
| `scripts/{{validator-1}}.js` | {{検証スクリプトの機能}} |
| `scripts/{{script-N}}.js` | {{機能説明}} |

### references/（詳細知識）

| リソース        | パス                                                 | 読込条件     |
| --------------- | ---------------------------------------------------- | ------------ |
| {{リソース1名}} | [references/{{file-1}}.md](references/{{file-1}}.md) | {{読込条件}} |
| {{リソースN名}} | [references/{{file-N}}.md](references/{{file-N}}.md) | {{読込条件}} |

### assets/（テンプレート・素材）

| アセット             | 用途     |
| -------------------- | -------- |
| `assets/{{asset-1}}` | {{用途}} |
| `assets/{{asset-N}}` | {{用途}} |

**テンプレート例**:
- `assets/script-task-template.js`
- `assets/script-validator-template.js`
```

---

## Progressive Disclosure 原則（§3.2.4）

| レベル  | 内容                           | 配置場所         |
| ------- | ------------------------------ | ---------------- |
| Level 1 | 概要・ワークフロー・ベストプラ | SKILL.md 本文    |
| Level 2 | Task仕様・思考プロセス         | agents/\*.md     |
| Level 3 | 詳細知識・参照資料             | references/\*.md |

**原則**: SKILL.md は軽量に保ち、詳細は references/ に外部化

---

## 相対パス記述規則（§10.1）

| 参照対象   | 相対パス形式                       |
| ---------- | ---------------------------------- |
| Task仕様書 | `agents/{{task-name}}.md`          |
| スクリプト | `scripts/{{script-name}}.js`      |
| 参照資料   | `references/{{reference-name}}.md` |
| アセット   | `assets/{{asset-name}}`            |

**禁止形式**（§10.2）:

| 形式                 | 問題点         |
| -------------------- | -------------- |
| スキル名のみ         | パスが不明確   |
| 絶対パス             | 環境依存       |
| `../` を含む相対パス | 曖昧さが生じる |

---

## フィードバック機構

### 更新対象ファイル

| ファイル | 用途 | 更新タイミング |
|----------|------|----------------|
| LOGS/ | 実行ログ fragment ディレクトリ（1 entry = 1 file、`pnpm skill:logs:append` 経由） | 毎回実行後 |
| changelog/ | SKILL 機能差分 fragment ディレクトリ（旧 `SKILL-changelog.md` は `changelog/_legacy.md` に退避） | SKILL 仕様変更時 |
| lessons-learned/ | 苦戦箇所・知見 fragment ディレクトリ（旧 `references/lessons-learned-*.md` は `lessons-learned/_legacy-*.md` に退避） | 苦戦箇所発生時 |
| EVALS.json | メトリクス | 毎回実行後 |
| references/patterns.md | 成功/失敗パターン | パターン発見時 |

### ログ記録（毎回実行後）

```bash
# 成功時
node scripts/log_usage.js --result success --phase "{{phase}}" --notes "{{概要}}"

# 失敗時
node scripts/log_usage.js --result failure --phase "{{phase}}" --notes "{{エラー原因}}"
```

### パターン保存（改善発見時）

成功/失敗パターンを発見したら `references/patterns.md` に追記：

```markdown
## 成功パターン

### {{パターン名}}
- **状況**: {{どんな状況で}}
- **アプローチ**: {{何をしたか}}
- **結果**: {{なぜうまくいったか}}
- **適用条件**: {{いつ使うべきか}}

## 失敗パターン（避けるべきこと）

### {{パターン名}}
- **状況**: {{どんな状況で}}
- **問題**: {{何が起きたか}}
- **原因**: {{なぜ失敗したか}}
- **教訓**: {{何を学んだか}}
```

### フィードバックサイクル

```
スキル実行 → LOGS fragment 追記（`pnpm skill:logs:append` 経由）→ EVALS.json更新（集約参照は `pnpm skill:logs:render --skill <name>`）
     ↓
パターン発見 → references/patterns.md更新
     ↓
次回実行時に活用
```

---

## チェックリスト（§8.1）

作成完了後、以下を確認：

| 項目                                                        | 確認 |
| ----------------------------------------------------------- | ---- |
| `name` がハイフンケース（最大64文字）でディレクトリ一致     | [ ]  |
| `description` が1024文字以内                                | [ ]  |
| `Anchors` が目標達成に必要十分な個数、`•` で開始            | [ ]  |
| `Trigger` が日本語で記述                                    | [ ]  |
| `description` にMarkdown記法がない                          | [ ]  |
| SKILL.md が500行以内                                        | [ ]  |
| `references/` のファイルがすべてリンク済み                  | [ ]  |
| `agents/*.md` が5セクション構造                             | [ ]  |
| 禁止ファイル（README.md等）がない                           | [ ]  |
| スクリプトが冪等性・エラー出力・引数検証を実装              | [ ]  |
| agents/scripts/references/assets が責務単位で分離されている | [ ]  |

---

## 関連リソース

- **構造仕様**: See [references/skill-structure.md](references/skill-structure.md)
- **品質基準**: See [references/quality-standards.md](references/quality-standards.md)
- **命名規則**: See [references/naming-conventions.md](references/naming-conventions.md)
