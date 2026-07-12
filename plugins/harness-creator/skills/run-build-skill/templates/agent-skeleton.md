---
# Agent Skeleton (kind: agent)
#
# CapabilityManifest schema: definitions/kindAgent
# 用途: SubAgent 定義 (plugins/*/agents/*.md) の雛形。
# 親 orchestrator から Task tool 経由で fan-out 起動される単位。
#
# TODO: build-skill が以下プレースホルダを置換する
#   {{CAPABILITY_NAME}}  agent 名 (kebab-case)
#   {{OWNER}}            governance 担当
#   {{PHASE}}            親 workflow 内の phase id
#   {{MODEL}}            sonnet|opus|haiku|inherit
#   {{ISOLATION}}        fork|worktree|inherit  (評価系は必ず fork)
#   {{FAN_OUT}}          single|parallel|sequential
#   {{TOOLS_JSON}}       ["Read", "Write", ...]
#   {{PURPOSE}}          一行で存在意義
#   {{TRIGGERS}}         発動条件
#   {{OUTPUT_CONTRACT}}  返却スキーマ
---
name: {{CAPABILITY_NAME}}
description: {{TRIGGERS}}
kind: agent
version: 0.1.0
owner: {{OWNER}}
since: {{DATE}}
tools: {{TOOLS_JSON}}
model: {{MODEL}}
isolation: {{ISOLATION}}
phase: {{PHASE}}
fan-out: {{FAN_OUT}}
contract:
  intent: {{PURPOSE}}
  interface:
    input: {{INPUT_SCHEMA_REF}}
    output: {{OUTPUT_SCHEMA_REF}}
  invariant:
    - 親 orchestrator の context を fork した時点の値のみ参照する
    - 出力は Output Contract で宣言した JSON 形のみを返す
    - 評価系 agent は generator の思考過程を読まない (sycophancy 防止)
rubric_refs: []
responsibility_refs: []
---

# {{CAPABILITY_NAME}}

## Purpose
{{PURPOSE}}

## Triggers
- {{TRIGGER_1}}
- {{TRIGGER_2}}

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・チェックリスト」を読み、未達項目を埋める手順をその場で生成して実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。

### ゴール (Goal)
{{GOAL}}

### 完了チェックリスト (Checklist)
- [ ] 入力 (`interface.input`) を検証した
- [ ] {{CHECKLIST_CORE}}
- [ ] 出力 (`interface.output`) が JSON 契約を満たす

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成 → 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら orchestrator に差し戻す。

## Output Contract
```json
{{OUTPUT_EXAMPLE_JSON}}
```

## Self-Evaluation
`plugins/harness-creator/references/quality-rubric.md` の 5 次元で自己採点する。

| 次元 | 本 agent での重点 |
|---|---|
| 完全性 | {{COMPLETENESS_FOCUS}} |
| 一貫性 | {{CONSISTENCY_FOCUS}} |
| 深度 | {{DEPTH_FOCUS}} |
| 検証可能性 | {{VERIFIABILITY_FOCUS}} |
| 簡潔性 | {{CONCISENESS_FOCUS}} |

未達なら自己修正を 1 回試行し、それでも未達なら orchestrator に差し戻す。

## Handoff
{{HANDOFF_TARGET}} に `{{HANDOFF_FIELDS}}` を返す。
