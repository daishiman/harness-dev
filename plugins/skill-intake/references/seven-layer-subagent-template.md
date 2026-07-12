# 7-layer SubAgent Template (skill-intake 専用)

本ファイルは skill-intake plugin の全 SubAgent (`plugins/skill-intake/agents/*.md`) が**写経して使う唯一の正規骨格**。`run-prompt-creator-7layer` の `seven-layer-markdown-template.md` を SubAgent (Claude Code Subagent file) の制約に適合させた版。

## 適合方針

- Claude Code SubAgent は frontmatter (`name` / `description` / `tools` / `model`) + 本文 Markdown 形式が必須。
- 7 層は本文側に配置。Layer 1〜4 はメタ情報、Layer 5〜7 は実行指示。
- 1 SubAgent = 1 責務 (R-id)。本文末尾に Self-Evaluation rubric を必須配置。
- 入出力は `schemas/<phase>.schema.json` で機械検証可能にする (additionalProperties:false)。

## 正規骨格

```markdown
---
name: <subagent-name>
description: <when_to_use 1 文。日本語、〜したいとき、〜したいときに使う。形式>
tools: <最小権限。例: Read, Write, AskUserQuestion>
model: sonnet
---

## メタ

| key | value |
|---|---|
| responsibility_id | R<n>-<slug> (1 agent = 1 R-id) |
| phase | <aggregator phase 番号 / 名前> |
| input_schema | <path/to/input.schema.json> |
| output_schema | <path/to/output.schema.json> |
| context_fork | true \| false (理由必須) |
| reproducible | true (同入力→同出力保証) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- <この SubAgent が絶対に守る原則。例: 抽象語を最終回答にしない>

### 1.2 倫理ガード
- <禁止事項 / PII 取扱 / secret 取扱>

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 単一責務
- 担当: <verb + object 形式で 1 文>
- 非担当: <他 SubAgent に委譲する責務を明示>

### 2.2 ドメインルール
- <ドメイン制約 / 不変条件 / 業界用語>

### 2.3 入力契約
| field | type | required | source | 説明 |
|---|---|---|---|---|
| <name> | <type> | yes/no | <前 phase / 静的 ref> | <意味> |

入力スキーマ: `<path/to/input.schema.json>` 準拠必須。

### 2.4 出力契約
- schema: `<path/to/output.schema.json>` (additionalProperties:false)
- 必須フィールド: <列挙>
- 完了条件: <機械検証可能な条件を列挙>

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| <id> | <path> | <タイミング> |

### 3.2 外部ツール / Script
- <CLI / Python script / MCP>

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- <exit code / fallback / halt 条件>

### 4.2 観測 / ロギング
- <`eval-log/skill-intake/<YYYY-MM-DD>.jsonl` に何を追記するか>

### 4.3 セキュリティ
- <Keychain 経由のみ / secret を本文出力禁止 / PII 取扱>

## Layer 5: エージェント層 (実行主体)

### 5.1 context_fork 要否
- <true: 理由 (Sycophancy 防止 / 独立判定) | false: 理由>

### 5.2 ゴール定義 (固定手順を持たない)
- 目的: <この出力が必要な理由>
- 背景: <目的の背景 (なぜ他の手段では駄目か)>
- 達成ゴール: <観測可能な完了状態 1 文 (schema validate PASS 等の機械判定を含める)>

### 5.3 実行方式
固定手順を持たない。`## Self-Evaluation` の完了チェックリスト未充足項目を特定→手順を都度立案→実行→自己評価を全項目充足まで反復する (上限: Layer 4 最大反復回数)。固定手順見出し (推論手順/思考プロセス) を置かない (l5-contract v2.0.0)。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `<aggregator skill / phase 番号>`
- 後続: `<次の SubAgent / phase>`
- handoff: `eval-log/handoff-<phase>.json` (`schemas/handoff.schema.json` 準拠)

### 6.2 並列性
- <並列可否 / 排他条件>

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- <Markdown / JSON / 図>
- AskUserQuestion 使用時は最大 3 択 + 自由入力で構成

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key / CLI 引数は英語のまま)

## 起動条件

- <orchestrator が本 SubAgent を起動する明示条件>

## やらないこと

- <他 phase / 他 SubAgent 担当の責務を列挙>

## Prompt Templates (任意, AskUserQuestion 等で使う場合)

> `{{var}}` 置換変数はこの節内のみ許容 (節外に書くと lint SE-no-todo が未展開プレースホルダとして error)。

### <Round N: 用途>
> 「<質問文>」
選択肢:
1. <選択肢 1>
2. <選択肢 2>
3. <選択肢 3>

## Self-Evaluation

> Layer 5 完了チェックリスト。全項目 YES でゴール到達=停止条件成立。固定手順は持たない。完了前に必ず 0/1 で自己採点し、1 つでも 0 なら出力前に修正。

- [ ] **完全性**: 出力 schema の required フィールドが全て埋まっている
- [ ] **再現性**: 同入力で同出力になる (LLM 判断の揺れ要素を排除)
- [ ] **責務遵守**: 「やらないこと」に該当する出力を含まない
- [ ] **言語遵守**: 本文日本語 / パラメーター名・schema key 英語
- [ ] **<phase 固有>**: <この SubAgent に特化した品質基準を 1 つ以上>

## Handoff

完了後の遷移先と渡すデータを明記:
- 成功時: `<次の SubAgent>` に `<file/path>` を渡す
- 失敗時: orchestrator に `halt_reason=<code>` で返す
```

## 命名・配置規則

- `plugins/skill-intake/agents/skill-intake-<role>.md` で配置。
- `responsibility_id` は `R<phase-番号>-<slug>` (例: `R5-purpose-excavate`)。
- 1 ファイル = 1 責務 = 1 agent。複数責務を 1 ファイルに詰めない。

## Self-Evaluation rubric の設計指針

本文末尾 `## Self-Evaluation` の **「phase 固有」項目** が SubAgent ごとの暗黙知を明示化する核。以下のパターンを参考に設計する:

| SubAgent カテゴリ | 推奨 phase 固有 rubric |
|---|---|
| 対話系 (interviewer / purpose-excavator / option-presenter) | 「同一の問いを言い換えで 2 回連続出していない」「抽象語 (効率化 / 最適化) を最終回答にしていない」 |
| 推定系 (user-profiler / next-action-advisor) | 「推定根拠が入力データから追跡可能」「推定信頼度を 0-1 で明示」 |
| 検証系 (assumption-challenger / notion-fidelity-guard) | 「対立仮説を最低 2 つ提示」「合格/不合格判定が機械検証可能」 |
| 生成系 (summarizer / handoff / visualizer / notion-publisher) | 「生成物が input schema を被覆」「冪等性 (再実行で差分なし)」 |
| 自己進化系 (self-updater) | 「追加質問の重複検出を行った」「snapshot を残した」 |

## Lint との接続

`scripts/lint_subagent_seven_layer.py` が本テンプレ準拠を機械検証する (rubric 正本: `references/rubric.json`)。
- frontmatter 4 キー必須
- 本文に `## Layer 1` 〜 `## Layer 7` 見出しが順序通り存在
- Layer 5 が宣言型 (`### 5.2 ゴール定義` + `### 5.3 実行方式`) で、固定手順見出し (推論手順/思考プロセス) を含まない (l5-contract v2.0.0)
- 本文末尾 `## Self-Evaluation` の checklist が 5 項目以上
- `{{var}}` 置換変数は `## Prompt Templates` 節内のみ許容
- `input_schema` / `output_schema` で参照される schema ファイルが存在
