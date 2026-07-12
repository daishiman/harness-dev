---
name: agent-template
description: run-build-skill が SubAgent ファイルを量産するための正本テンプレート。9 セクション固定で Prompt Templates と Self-Evaluation を必須化する。
type: reference
version: 1.0.0
---

# SubAgent 9 セクション正本テンプレート

`plugins/<plugin>/agents/<role>.md` を量産する際の骨格。

## なぜこの 9 セクションか

| # | セクション | 役割 | lint 必須 |
|---|---|---|---|
| 1 | Frontmatter | name / description / tools / model / context-fork | ✅ |
| 2 | Purpose | 役割定義 (Layer 1 相当: 不変定義) | ✅ |
| 3 | Inputs | 前提・参照 reference (Layer 2 相当: ドメイン定義) | ✅ |
| 4 | Outputs | 成果物パス + JSON 雛形 (Layer 6 相当: 出力契約) | ✅ |
| 5 | ゴールシーク実行 (旧 Steps) | 固定手順ではなく Goal+Checklist+Loop で都度手順生成 (Layer 5/6 相当) | ✅ |
| 6 | Constraints | 制約・禁止事項 (Layer 4 相当: ガードレール) | ✅ |
| 7 | **Prompt Templates** | ユーザーに投げる実発話例 (Layer 7 相当) | ✅ **NEW** |
| 8 | **Self-Evaluation** | quality-rubric.md の 5 次元採点 | ✅ **NEW** |
| 9 | Handoff | 次 agent と引き継ぎデータ | ✅ |

7 と 8 が legacy `doc/skill-intake-interviewer/agents/` には有り、現状 `plugins/skill-intake/agents/` には欠落していた領域。本テンプレで再導入する。

## 完全な骨格テンプレ

```markdown
---
name: <plugin-prefix>-<role>
description: <一行で何をする agent か。"~ するエージェント。" で終わる。>
tools: <最小権限。例: Read, Write, AskUserQuestion>
model: <sonnet|haiku>  # 対話系=sonnet / 決定論系=haiku
---

## Purpose

<役割 2-3 文。Layer 1 相当の不変定義。>

## Inputs

- <参照する output/<hint>/*.json>
- <参照する references/*.md (Progressive Disclosure)>

## Outputs

- `output/<hint>/<name>.json` (構造化結果)
- `output/<hint>/<name>.md` (人間向けサマリ, 任意)

出力 JSON 雛形:

```json
{
  "<field>": "<value>",
  "next_agent": "<successor-agent-name>"
}
```

## ゴールシーク実行
<!-- 固定手順を書かない。Goal+Checklist を宣言し、手順は実行時に都度生成する。詳細: run-build-skill references/goal-seek-paradigm.md -->

### ゴール (Goal)
<この agent が達成すべき最終状態を 1 文・観測可能な形で>

### 完了チェックリスト (Checklist)
- [ ] 入力 (`Inputs`) を検証した
- [ ] <検証可能な達成条件>
- [ ] 出力 (`Outputs`) が JSON 契約を満たす

### ゴールシークループ
未達 `[ ]` を特定 → 手順を都度生成 → 実行 → チェックリスト再評価 `[x]` → 全達成まで反復。規定周回で未達なら Handoff せず orchestrator に差し戻す。

## Constraints

- <禁止事項。"~ しない" 形式>
- <ガードレール>

## Prompt Templates

各ラウンドでユーザーに投げる実発話例。`vocabulary_tier` (beginner/intermediate/expert) に応じて差し替える。

`brief.responsibilities[]` が複数定義されている場合、**responsibility ごとに 1 つ以上の `### Round` ブロック** を生成し、直前に `<!-- responsibility: <id> -->` HTML コメント anchor を必須で挿入する。lint Tier 2 (`--strict-coverage --brief`) が brief の responsibility.id 集合と SubAgent.md の anchor 集合を照合する。

<!-- responsibility: R1 -->
### Round 1: <局面名 / responsibility=R1>

> 「<実発話例。語彙 tier=beginner 想定>」

選択肢 (任意):
1. <option 1>
2. <option 2>
3. <option 3>

<!-- responsibility: R2 -->
### Round N: <局面名 / responsibility=R2>

> 「<実発話例>」

## Self-Evaluation

`plugins/harness-creator/references/quality-rubric.md` の 5 次元で自己採点する。

| 次元 | 本 agent での重点 |
|---|---|
| 完全性 | <この agent で重点的に見る合格条件> |
| 一貫性 | <矛盾を排除する観点> |
| 深度 | <深掘り十分性> |
| 検証可能性 | <スクリプト/客観条件で判定可能か> |
| 簡潔性 | <冗長排除> |

未達なら自己修正を 1 回試行し、それでも未達なら Handoff せず orchestrator に差し戻す。

## Handoff

<次 agent 名> へ <引き渡しデータ> を渡す。
```

## prompt-creator 連携 (kind 別ルール / 双方向責務契約)

run-build-skill Step 7.5 は `brief.prompt_creator_policy` の resolved 値で起動条件を判定する。bool 単独フラグではなく **kind 別ルール化** された policy を参照する。

### kind 別 resolved policy (auto 時の既定)

| brief.kind | resolved_policy | 備考 |
|---|---|---|
| `run` | **required** | responsibilities[] に prompt_required=true が 1 件以上必須 (schema allOf で強制) |
| `assign` | **required** | generator/evaluator 双方の責務 prompt が必要 |
| `ref` | optional | 静的参照中心。明示指定で skip も可 |
| `wrap` | optional | 外部 CLI ラップ中心。L5/L6 のみ生成のケースあり |
| `delegate` | skip | 外部 LLM 委譲は本 skill 側で prompt 生成しない |

`brief.prompt_creator_policy` で上記 default を上書き可能。required にした場合 lint Tier 2 が trace.prompt_generation_model と突合する。

### 双方向責務契約

- **harness-creator 側責務** (本テンプレ): 9 セクション骨格生成、responsibility anchor (`<!-- responsibility: <id> -->`) 配置、brief.responsibilities[] の id 集合を SubAgent.md に転写。
- **prompt-creator 側責務** (`plugins/prompt-creator/skills/run-prompt-creator-7layer/SKILL.md` Key Rule 8): Prompt Templates / Self-Evaluation の 2 セクション内、各 responsibility anchor 配下の本文を 7 層プロンプトで充填。anchor は触らない。
- **正本の向き (逆転禁止)**: 7 層本文の SSOT 正本は `prompts/<R-id>.md` 側。`agents/*.md` を 7 層本文の正本にし `prompts/<R-id>.md` を `moved_to` リダイレクトで空殻化する逆転 (旧「SSOT 統合方針 A」型) は禁止。`prompt-placement-convention.md#正本の向き-canonical-direction-と禁止アンチパターン` を正本とし、canonical な `scripts/lint-prompt-placement.py`(run-build-skill 配下)が `PROMPT-REDIRECT-INVERSION` として機械検出する。

### 起動と戻り検証

```
brief.responsibilities[].prompt_required=true が 1 件でもあれば
  → Skill(run-prompt-creator-7layer, target_agent=<agent.md>, brief=<brief.json>, --responsibility-id <R-id>)
  → 出力先: plugins/<plugin>/skills/<skill>/prompts/<R-id>.yaml (prompt-placement-convention.md 準拠)
  → lint-agent-prompt-section.py --strict-coverage --brief <brief.json> <agent.md>
  → trace.prompt_generation_model.per_responsibility[*].lint_status=PASS なら完了
  → FAIL なら最大 3 回再起動、超過時は brief.responsibilities[] 再設計のため run-skill-elicit に escalate
```

### Prompt 成果物の格納先 (再現性規約)

責務単位の 7 層 YAML は **skill 配下の `prompts/` ディレクトリに格納** する。SKILL.md 本文には転記しない (300 行制約 + DRY)。

| 観点 | 規約 |
|---|---|
| 配置パス | `plugins/<plugin>/skills/<skill>/prompts/<R-id>.yaml` |
| ファイル名 | brief.responsibilities[].id (R1, R2, ...) と 1:1 |
| ディレクトリ階層 | 1 階層 (ネスト禁止) |
| SKILL.md 参照 | `## Additional Resources` 節に案内 1 行のみ可 |

詳細は `references/prompt-placement-convention.md` を参照。`plugins/prompt-creator/skills/run-prompt-creator-7layer/SKILL.md` および `references/build-steps.md#h25-prompt-creator-ループ詳細` も併読。

## lint 規則 (Tier 1 形式 / Tier 2 責務 coverage)

`plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py` で以下を二段で必須化:

### Tier 1: 形式検査 (常時実行)

1. `## Prompt Templates` 見出しが存在する
2. `## Self-Evaluation` 見出しが存在する
3. Prompt Templates 配下に少なくとも 1 つの `>` 引用 (実発話) または `### Round` 見出しがある (純自動 agent でユーザー対話が無い場合は本文に `(対話なし: 自動実行 agent)` を明記すれば skip 許可)
4. Self-Evaluation 配下に 5 次元 (完全性/一貫性/深度/検証可能性/簡潔性) のいずれか 1 つ以上が言及されている

### Tier 2: 責務 coverage 検査 (`--strict-coverage --brief <skill-brief.json>` 指定時)

5. brief.responsibilities[] の id 集合と SubAgent.md の `<!-- responsibility: <id> -->` anchor 集合が一致する (missing/extra ともに violation)
6. 各 anchor 直後に `### Round` 見出しまたは `>` 引用が 1 件以上存在する
7. brief.responsibilities[].prompt_required=true である responsibility に対して、対応する anchor 配下の本文が placeholder (`<...>`, `TODO`, 空) でない
8. brief.kind ∈ {run, assign} のとき Tier 2 は必須 (`required` policy)、ref/wrap は optional、delegate は skip

Tier 2 違反は CI hook (PostToolUse) で fail-close。Tier 1 のみは後方互換のため既存 SubAgent もしばらくは通過可能とする。

## 命名規則 (再掲)

- agent 名: `<plugin-prefix>-<role>` (例: `skill-intake-interviewer`)
- description は `~ する <名詞>。` で終わる
- nested directory 禁止 (lint-skill-tree 第 13 条準拠)
