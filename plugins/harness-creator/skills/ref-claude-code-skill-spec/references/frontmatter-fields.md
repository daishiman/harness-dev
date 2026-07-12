# frontmatter フィールド詳細

設計書 03章の圧縮版。すべて YAML 1.2、タブ禁止、true/false 小文字。

## 公式仕様とローカル規約

Claude Code 公式仕様では frontmatter field の多くは optional で、`description` が推奨中心である。harness の出荷基準では再現性と lint のため `name` / `description` を必須扱いにする。

## harness 必須

| field | 型 | 内容 |
|---|---|---|
| `name` | string | kebab-case、ディレクトリ名と一致（第7条） |
| `description` | string | 発動条件 exactly 2 trigger |

## invocation 制御

| field | 既定 | 用途 |
|---|---|---|
| `disable-model-invocation` | false | true: モデルから自動発動しない（ref系） |
| `user-invocable` | true | false: ユーザー直接呼出不可（assign系） |

## 引数（run系）

| field | 例 |
|---|---|
| `argument-hint` | `"[skill-name] [kind?]"` |
| `arguments` | `[skill_name, kind]` |

## 権限

| field | 例 |
|---|---|
| `allowed-tools` | `[Read, Write, Bash(python3 *), Skill(assign-x *)]` |

glob 制限可。`Bash(*)` は危険。

## 実行コンテキスト

| field | 値 |
|---|---|
| `context` | `inline` (既定) / `fork` |
| `agent` | subagent 種別（`general-purpose` 等） |

## メタ

| field | 用途 |
|---|---|
| `kind` | run/ref/assign/wrap/delegate |
| `pair` | 対Skill名（generator↔evaluator） |
| `owner` | 所有者（team-skills 等） |
| `since` | YYYY-MM-DD |
| `aliases` | 改名時の旧名（第15条） |

## 多重継承 (29章)

| field | 用途 |
|---|---|
| `rubric_refs` | upstream rubric の参照リスト |
| `reference_refs` | 参照Skill リスト |
| `script_refs` | 共通scriptへの参照 |
| `merge_strategy` | `deep-merge` / `strict` / `override` / `layered` |
| `conflict_policy` | `most-specific-wins` / `error` / `warn-and-merge` |

## アンチパターン

- `disable-model-invocation: true` + `user-invocable: true` は意味矛盾しないが、その場合はSlash command経由でのみ呼ばれる珍しい構成
- `allowed-tools: [Bash(*)]` は実質ノーガード
- trigger は exactly 2。1個や3個以上は lint で落とす
