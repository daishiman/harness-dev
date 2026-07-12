# combinators/ — Atomic Composer 差分パッチ

`_base.md` (骨格) に対して kind 固有・フラグ固有の差分を適用するための combinator 群。

## 設計原則

- 各 `.patch` は `_base.md` を対象とした **unified diff**（`patch -p1` 適用可能）。
- 1 つの combinator は **1 つの関心** のみ扱う（kind | flag | project）。
- すべての差分は **変数プレースホルダ** (`{{...}}`) で記述し、プロジェクト固有値・ハードコードを禁止する。
- 適用順序は `run-build-skill` Step 2 で固定:
  1. **kind-specific**（必ず 1 つ適用）: `with-run.patch` / `with-ref.patch` / `with-wrap.patch` / `with-assign-evaluator.patch` / `with-assign-generator.patch` / `with-delegate.patch`
  2. **optional flag**（0〜N 個）: `with-evaluator.patch` / `with-hooks.patch` / `with-subagent.patch` / `with-knowledge.patch`
  3. **project flag**（0〜N 個、Phase 1 で追加予定）: `with-cross-platform.patch` / `with-rubric.patch`
- 同一セクションを複数 combinator が触る場合は **順序保証** により後勝ち（flag combinator が kind-specific を上書き可）。

## なぜテンプレ展開ではなく combinator か

- 旧設計: 9 種テンプレ × N 個フラグ = **積空間**
- 新設計: 1 atom + 6 kind-combinator + N flag combinator = **和空間**
- kind に新フラグを追加するとき、旧設計では 9 ファイル全て更新が必要だったが、新設計では combinator を 1 つ追加するだけで全 kind に伝搬する。

## kind と combinator の対応 (F8 連携)

| kind | combinator | 補足 |
|---|---|---|
| `run` | `with-run.patch` | `## ゴールシーク実行` (Goal+Checklist+Loop) を注入 |
| `ref` | `with-ref.patch` | `## 参照内容` セクション、`disable-model-invocation: true` を frontmatter に注入 |
| `assign` + `role_suffix: generator` | `with-assign-generator.patch` | `## 生成契約` セクション、`pair:` 必須を注入 |
| `assign` + `role_suffix: evaluator` | `with-assign-evaluator.patch` | `## Evaluator Contract` + `context: fork` + `user-invocable: false` を注入 |
| `wrap` | `with-wrap.patch` | `## Wrapped CLI` セクション、`allowed-tools: Bash(...)` テンプレを注入 |
| `delegate` | `with-delegate.patch` | `## Delegation Target` セクション、外部実行系の宣言を注入 |
| `run` の亜種（agent-team / orchestrator / hook-integrated） | `with-run.patch` + optional flag を重ねる | 設計書24章 §「runの複合kind」参照 |

## flag combinator の役割

| flag | patch | 注入内容 |
|---|---|---|
| `with_evaluator_pair` | `with-evaluator.patch` | generator 側に `pair:` フィールド + Evaluator 連携セクション。**generator自身に `context: fork` を入れてはならない** |
| `with_hooks` | `with-hooks.patch` | `PreToolUse` / `PostToolUse` 配線 + security セクション |
| `with_subagent` | `with-subagent.patch` | `agent`, Subagent body 連携。`context: fork` は **subagent 用** combinator が扱う |
| `with_knowledge` | `with-knowledge.patch` | `## ナレッジループ` 節 + frontmatter `knowledge_loop` 記述子を注入。knowledge/ 雛形 (`../knowledge-skeleton/<pattern>/`) と Python スクリプト群 (search_knowledge / build_index / record_usage) を併せて展開。正本仕様は `ref-knowledge-loop`。全 kind に適用可能な横断 combinator |

## 移行戦略（Phase 0）

現状の `run.md` / `ref.md` / `wrap.md` / `assign-*.md` / `delegate.md` / `hook-integrated.md` / `agent-team.md` / `orchestrator.md` は **引き続き使用可能**（fallback）。
combinator は **新規スキル生成時の代替経路** として並行運用し、Phase 0 終了時に旧テンプレを deprecate する。

`run-build-skill` の Step 2 で `composer_mode` を選べる:

```bash
# 旧フロー (default)
COMPOSER_MODE="template"

# 新フロー (kind-specific combinator 6枚が揃ったため atomic を選択可能)
COMPOSER_MODE="atomic"
```

`atomic` 選択時、`_base.md` を読み、brief の `kind` / `role_suffix` / `with_evaluator_pair` / `with_hooks` / `with_subagent_hint` に応じて kind-specific combinator → flag combinator の順で適用する。

## ファイル一覧

### kind-specific（必須・1つ適用）
- `with-run.patch` — run 系ワークフロー骨格
- `with-ref.patch` — ref 系参照書骨格（`disable-model-invocation: true`）
- `with-assign-generator.patch` — assign 系 generator 骨格（`pair:` 必須）
- `with-assign-evaluator.patch` — assign 系 evaluator 骨格（`context: fork` + `user-invocable: false`）
- `with-wrap.patch` — wrap 系 CLI ラッパ骨格
- `with-delegate.patch` — delegate 系 外部実行委譲骨格

### optional flag（0〜N 個適用）
- `with-evaluator.patch` — generator に **pair: のみ** 注入（`context: fork` は注入しない）
- `with-hooks.patch` — Hook 配線 + security 強化
- `with-subagent.patch` — Subagent 連携
- `with-knowledge.patch` — ナレッジループ（蓄積/検索/§12フィードバック）注入。`../knowledge-skeleton/` 雛形と併用
