---
# Workflow Skeleton (kind: workflow)
#
# CapabilityManifest schema: definitions/kindWorkflow
# manifest 駆動の複数 phase オーケストレーション。
# 構造は run-elegant-review の manifest を踏襲する。
#
# - phases[]: 1 以上。id / agents[] / parallel / gate を宣言
# - max_iterations: 改善ループの上限 (default 3)
# - 各 phase の gate を機械判定可能な条件にすること
#
# TODO: build-skill が以下プレースホルダを置換する
#   {{CAPABILITY_NAME}}  workflow 名 (kebab-case, 例: run-elegant-review)
#   {{OWNER}}            governance 担当
#   {{MAX_ITERATIONS}}   改善ループ上限 (1..N)
---
name: {{CAPABILITY_NAME}}
description: {{WORKFLOW_TRIGGERS}}
kind: workflow
version: 0.1.0
owner: {{OWNER}}
since: {{DATE}}
max_iterations: {{MAX_ITERATIONS}}
phases:
  - id: phase-1-intake
    agents:
      - {{INTAKE_AGENT}}
    parallel: false
    gate: brief.json schema validation pass
  - id: phase-2-diverge
    agents:
      # TODO: 並列分析 agent を列挙
      - {{ANALYST_AGENT_1}}
      - {{ANALYST_AGENT_2}}
      - {{ANALYST_AGENT_3}}
    parallel: true
    gate: findings[] 全件が severity フィールドを持つ
  - id: phase-3-converge
    agents:
      - {{EXECUTOR_AGENT}}
    parallel: false
    gate: C1-C4 ゲート全 PASS かつ changed_paths[] 非空
  - id: phase-4-verify
    agents:
      - {{EVALUATOR_AGENT}}
    parallel: false
    gate: evaluator JSON passed=true
contract:
  intent: {{WORKFLOW_INTENT}}
  interface:
    input: {{WORKFLOW_INPUT_SCHEMA}}
    output: {{WORKFLOW_OUTPUT_SCHEMA}}
    handoff_format: .claude/handoff/{{CAPABILITY_NAME}}-<session>.json
  invariant:
    - 各 phase の gate を機械判定する (自然言語の「完了」を信用しない)
    - phase 3 evaluator は必ず context=fork で起動 (sycophancy 防止)
    - max_iterations 到達で governance escalation
rubric_refs:
  - ref-skill-design-rubric
responsibility_refs: []
---

# {{CAPABILITY_NAME}}

## Orchestration Flow

```
phase-1-intake
   │ gate: brief.json schema OK
   ▼
phase-2-diverge (parallel)
   ├─ {{ANALYST_AGENT_1}}
   ├─ {{ANALYST_AGENT_2}}
   └─ {{ANALYST_AGENT_3}}
   │ gate: findings[].severity 完備
   ▼
phase-3-converge
   └─ {{EXECUTOR_AGENT}}
   │ gate: C1-C4 PASS + changed_paths != []
   ▼
phase-4-verify
   └─ {{EVALUATOR_AGENT}} (context=fork)
   │ gate: passed=true
   ▼
[converged] or [iterate <= max_iterations] or [escalate]
```

## Phase 詳細

### phase-1-intake
- 役割: 要求を構造化 brief に変換
- 入力: user prompt
- 出力: `{{BRIEF_PATH}}`
- Gate: schema validation pass

### phase-2-diverge
- 役割: 多角的に findings を並列収集
- 起動: 並列 (`parallel: true`)
- 出力: 各 agent が `paradigm_findings[]` を返す
- Gate: severity 完備 + 重複除去後 N 件以上

### phase-3-converge
- 役割: findings を統合し最小パッチ集合を適用
- Gate: C1-C4 全 PASS、changed_paths[] 非空

### phase-4-verify
- 役割: 適用結果を fork 評価
- isolation: fork (必須)
- Gate: evaluator JSON `passed=true`

## 改善ループ
- gate FAIL かつ iteration < {{MAX_ITERATIONS}} → phase-2 へ戻す (findings を context 注入)
- iteration == {{MAX_ITERATIONS}} → governance escalation (`run-skill-rubric-governance`)

## Handoff
- 形式: `.claude/handoff/{{CAPABILITY_NAME}}-<session>.json`
- PreCompact 後は PostCompact で handoff 再読込

## Convergence Policy
`references/convergence-policy.json` の Δneg/Δpos 閾値で収束判定する。
