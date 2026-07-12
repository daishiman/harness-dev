# 20. プロンプト集 / CLAUDE.md から Skill 群への移行

## 目的

肥大化した prompt、`CLAUDE.md`、docs を、Skill / Hook / CLI / MCP へ分解する。

## Step 1. 棚卸し

既存文書を次に分類する。

| 内容 | 移行先 |
|---|---|
| 全タスクで必須の短い規約 | `CLAUDE.md` |
| domain-specific reference | `ref-*` |
| 手順化された workflow | `run-*` |
| 既存 workflow の preset | `wrap-*` |
| internal worker | `assign-*` |
| 外部 LLM 委譲 | `delegate-*` |
| 決定論的検査 | Hook / CI / CLI |
| 人間向け記録 | docs |
| 外部プロトコル/接続面 | MCP / plugin / app connector |

## Step 2. `CLAUDE.md` を薄くする

残す:

- repo identity
- always-on constraints
- high-level navigation

移す:

- 長い手順
- domain reference
- examples
- API details
- repeated checklist

## Step 3. 最初の `ref-*` を作る

読み物をそのまま docs に置くだけでなく、Claude に自動想起させたい知識は `ref-*` にする。

## Step 4. workflow を `run-*` にする

3 step 以上の繰り返し作業は `run-*` にする。副作用が強ければ `disable-model-invocation: true`。

## Step 5. 決定論へ昇格する

Gotchas（落とし穴） が増えたら、次へ移す。

```text
Gotchas（落とし穴） -> frontmatter lint -> Hook -> CI -> CLI / lint plugin
```

## Step 6. 評価器を追加する

成果物品質が重要な workflow には `assign-*-evaluator` を追加する。

## Step 7. 依存関係を lint する

検査対象:

- `wrap-*` に `base:` がある。
- `assign-*-evaluator` に `pair:` がある。
- `pair:` の相手が存在する。
- `ref-*` が到達不能設定になっていない。
- dangerous `run-*` に `disable-model-invocation: true` がある。dangerous は `danger: true` または `effect: external-mutation` を持つものとする。
