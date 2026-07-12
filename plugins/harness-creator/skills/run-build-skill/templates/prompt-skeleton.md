---
# Prompt Skeleton (kind: prompt)
#
# CapabilityManifest schema: definitions/kindPrompt
# prompt-creator プラグインの 7層構造に準拠 (run-prompt-creator-7layer)。
# 各 layer は index 1..7 で順序固定。ref は layer 詳細仕様への path/anchor。
#
# 7 Layer 構造:
#   1. Role / Persona            役割と立場
#   2. Context / Background      背景情報
#   3. Goal / Objective          目的の明示
#   4. Constraints / Rules       制約・禁則
#   5. Steps / Procedure         手順
#   6. Output Format             出力形式
#   7. Self-Evaluation           自己評価基準
#
# TODO: build-skill が以下プレースホルダを置換する
#   {{CAPABILITY_NAME}}  prompt 名 (kebab-case)
#   {{OWNER}}            governance 担当
#   {{SELF_EVAL_REF}}    Self-Evaluation rubric への参照
---
name: {{CAPABILITY_NAME}}
description: {{PROMPT_TRIGGERS}}
kind: prompt
version: 0.1.0
owner: {{OWNER}}
since: {{DATE}}
layers:
  - index: 1
    title: Role / Persona
    ref: "#layer-1-role"
  - index: 2
    title: Context / Background
    ref: "#layer-2-context"
  - index: 3
    title: Goal / Objective
    ref: "#layer-3-goal"
  - index: 4
    title: Constraints / Rules
    ref: "#layer-4-constraints"
  - index: 5
    title: Steps / Procedure
    ref: "#layer-5-steps"
  - index: 6
    title: Output Format
    ref: "#layer-6-output"
  - index: 7
    title: Self-Evaluation
    ref: "#layer-7-self-eval"
self_evaluation: {{SELF_EVAL_REF}}
contract:
  intent: {{PROMPT_INTENT}}
  interface:
    invocation: {{INVOCATION_PATTERN}}
    output_shape: {{OUTPUT_SHAPE}}
  invariant:
    - 7 layer 全てを欠落させない (index 1..7 連番)
    - Self-Evaluation を必ず最終 layer に置く
    - 各 layer は単一責務 (混在させない)
---

# {{CAPABILITY_NAME}}

## Layer 1: Role
<!-- TODO: agent/user の役割と立場を一文で定義 -->
{{ROLE_DEFINITION}}

## Layer 2: Context
<!-- TODO: タスクの背景・前提・周辺情報 -->
{{CONTEXT_BACKGROUND}}

## Layer 3: Goal
<!-- TODO: 達成すべきゴールを SMART で記述 -->
{{GOAL_STATEMENT}}

## Layer 4: Constraints
<!-- TODO: やってよいこと/やってはいけないこと/形式制約 -->
- {{CONSTRAINT_1}}
- {{CONSTRAINT_2}}

## Layer 5: Steps（ゴールシーク）
<!-- 固定手順を番号で羅列しない。ゴール+チェックリストを置き、手順は実行時に都度生成する。詳細: run-build-skill references/goal-seek-paradigm.md -->
- **ゴール**: {{GOAL}}
- **完了チェックリスト**:
  - [ ] {{CHECK_1}}
  - [ ] {{CHECK_2}}
- **ループ**: 未達項目を特定 → 手順を都度生成 → 実行 → チェックリスト再評価 → 全達成まで反復。

## Layer 6: Output
<!-- TODO: 出力形式 (JSON schema / markdown 構造 / 文字数等) -->
```
{{OUTPUT_TEMPLATE}}
```

## Layer 7: Self-Evaluation
`{{SELF_EVAL_REF}}` の rubric で自己採点する。

| 次元 | 重点 |
|---|---|
| 完全性 | {{COMPLETENESS_FOCUS}} |
| 一貫性 | {{CONSISTENCY_FOCUS}} |
| 深度 | {{DEPTH_FOCUS}} |
| 検証可能性 | {{VERIFIABILITY_FOCUS}} |
| 簡潔性 | {{CONCISENESS_FOCUS}} |

未達なら自己修正を 1 回試行する。
