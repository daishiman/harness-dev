---
name: assign-plugin-plan-evaluator
description: 生成済み plan を4条件と決定論ゲートで評価したいとき、context:fork で独立評価結果 plan-findings.json を取得したいときに使う。
disable-model-invocation: false
user-invocable: false
context: fork
argument-hint: "[--plan-dir <path>] [--output <findings_path>]"
arguments: [plan_dir, output]
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(python3 *)
  - Task
kind: assign
version: 0.2.0
effect: local-artifact
owner: team-platform
contract:
  intent: 生成済み plan を親 context の解釈バイアスから切り離して独立評価し plan-findings.json を返すため、4条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) + 決定論ゲートの採点専用 evaluator を提供する。
  interface:
    inputs: [plan_dir, output]
    outputs: [plan-findings.json]
  invariant:
    - 必ず context:fork で起動し、親 (architect / orchestrator) の解釈バイアスを引き継がないこと
    - 評価対象 plan を書き換えず findings の出力のみ行うこと (write=findings only、Goodhart 防止)
    - 4条件 verdict を全付与し、空 findings を残さない (PASS でも info を 1 件以上) こと
    - plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) の exit code を一次根拠とし、自然言語で PASS 判定しないこと
    - high severity が 1 件でもあれば全体を FAIL とすること
since: 2026-06-30
script_refs:
  - ../run-plugin-dev-plan/scripts/verify-index-topsort.py
  - ../run-plugin-dev-plan/scripts/detect-unassigned.py
  - ../run-plugin-dev-plan/scripts/check-spec-frontmatter.py
  - ../run-plugin-dev-plan/scripts/check-spec-gates.py
  - ../run-plugin-dev-plan/scripts/check-spec-matrix-coverage.py
  - ../run-plugin-dev-plan/scripts/check-surface-inventory.py
  - ../run-plugin-dev-plan/scripts/check-build-handoff.py
  - ../run-plugin-dev-plan/scripts/check-requirements-coverage.py
  - ../run-plugin-dev-plan/scripts/check-runtime-portability.py
  - scripts/evaluate-plan.py
rubric_refs:
  - ref-skill-design-rubric              # L0: 共通設計 rubric (harness-creator 正本, 固定)
  - references/plan-rubric.json           # L2: 本 evaluator 固有 (4条件 plan 判定)
reference_refs:
  - references/resource-map.yaml
  - references/four-condition-criteria.md
source: plugins/plugin-dev-planner/skills/run-plugin-dev-plan/prompts/R4-verify-traceability.md
source-tier: internal
last-audited: 2026-06-30
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-evaluate.md
schema_refs:
  - schemas/plan-findings.schema.json
responsibilities:
  - id: R1
    name: evaluate
    prompt_required: true
agent_refs:
  - ../../agents/plugin-dev-plan-evaluator.md
pair: run-plugin-dev-plan
role_suffix: evaluator
---

# assign-plugin-plan-evaluator

> 生成 plan を **4条件 + 決定論ゲート** で評価し `plan-findings.json` を返す independent evaluator。`context:fork` で起動して Sycophancy (親への迎合) を防ぐ。生成者 (`run-plugin-dev-plan` の architect) と評価者を分離し、proposer ≠ approver を構造で保証する。

## Purpose & Output Contract

**入力**: plan_dir (評価対象 plan ディレクトリ = `index.md` + 13 phase files (`phase-01-*.md` … `phase-13-*.md`) + `component-inventory.json` 機械SSOT + `handoff-run-plugin-dev-plan.json`) / output (省略時 `<PLAN_DIR>/plan-findings.json`)
**出力**: `<PLAN_DIR>/plan-findings.json` (`schemas/plan-findings.schema.json` 準拠)
**完了条件**: 4条件 verdict 全付与 + findings[] に severity 配列 + plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) の gate_results。

## 4条件 評価軸 (R4 の独立 skill 昇格)

| Gate | 観点 | 一次根拠 (決定論ゲート) |
|---|---|---|
| **C1 矛盾なし** | component_kind / handoff / manifest / harness の契約が衝突しない | 意味判定 (script では捕捉不能、契約間突合) |
| **C2 漏れなし** | 5 種 component_kind × N 実体 + plugin-level surface を必要性ベースで全確認 (同一 kind 複数実体可・各 component が ≥1 phase の entities_covered に出現)・単一 skill 退化なし | `detect-unassigned` / `check-spec-frontmatter` / `check-spec-gates` / `check-surface-inventory` / `check-requirements-coverage` exit0 |
| **C3 整合性あり** | 用語 / frontmatter / plugin_meta / quality_gates が同一語彙・マトリクス全行被覆 (行数正本=harness-creator-spec-reflection.md) | `check-spec-matrix-coverage --self-test` / PLAN exit0 |
| **C4 依存関係整合** | index が P01..P13 を phase_number 昇順で全列挙・inventory component DAG 非循環・orphan 0 | `verify-index-topsort` / `detect-unassigned` / `check-build-handoff` / `check-runtime-portability` exit0 |

> **C1-C4 ラベルの二層性 (語彙 disambiguate)**: 本 skill の C1-C4 は **inner の機械ゲート** (plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) による plan の構造検証)。`run-plugin-dev-plan` が昇格前に通す `run-elegant-review` の C1-C4 は **outer の設計レビュー** (30 思考法による elegance lint)。両者は同じ 4 概念 (矛盾なし/漏れなし/整合性あり/依存関係整合) を**別 loop-scope・別手法で二段検証する意図的な階層**であり、冗長ではない。同一ラベルが指すゲートは文脈で異なる (本 skill=inner / elegant-review=outer)。

## Key Rules

1. **context:fork 必須**: 親 (architect/orchestrator) から plan の解釈バイアスを引き継がない。
2. **決定論ゲート優先**: スクリプト検証可能な項目は必ず exit code で判定し、LLM は契約間の意味判定のみ。
3. **findings 必出**: severity ∈ {high, medium, low, info}、bucket は C1-C4 か rubric id (PLAN-001 等)。
4. **単一 skill 退化の検出**: sub-agent / slash-command / hook / script component を不要とした根拠が goal-spec constraints または index の受入確認に無ければ C2 を high で FAIL。plugin-level surface の不要理由は `plugin_level_surfaces.<surface>.omitted_reason` (正本キー一本) で見る。
5. **suggested_fix 明示**: high/medium には差し戻し方針を 1-2 文で明記し architect (R3) へ返す。
6. **空 findings 禁止**: PASS でも info severity で「確認した観点」を 1 件以上残す。
7. **plan を書き換えない**: read-only 評価 (Edit を持たない)。Bash は検証スクリプト実行のみ。

## Steps

正本責務は `prompts/R1-evaluate.md`。要約:

### Step 1: 決定論ゲート (script、一次根拠)
```bash
EVALUATOR_DIR=plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator
# 全 plan-scoped 決定論ゲート (G1-G10) を束ねて実行し plan-findings.json を出力
# (個別ゲート一覧の可読正本は run-plugin-dev-plan/references/io-contract.md §11 表)
python3 "$EVALUATOR_DIR/scripts/evaluate-plan.py" --plan-dir "$PLAN_DIR"
```

### Step 2: 4条件機械評価
`references/plan-rubric.json` を Read し、各 exit code を C1-C4 へ写像する。

### Step 3: 意味判定 (LLM、契約間突合のみ)
`scripts/evaluate-plan.py` は決定論ゲートと plugin-level surface 明示性だけを機械判定する。C1 の契約衝突や単一 skill 退化の意味判定は、本 assign skill の LLM 評価レイヤーで `plan-rubric.json` の `semantic_checks` を読んで追加 finding として扱う。

### Step 4: findings 出力
`schemas/plan-findings.schema.json` 準拠で `<PLAN_DIR>/plan-findings.json` を Write。verdict に 4 条件 PASS/FAIL、gate_results に plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) の exit code。

## Gotchas

1. C2 と C4 を混同しない (漏れ = surface 網羅性 vs 依存 = top-sort 健全性)。両者とも detect-unassigned が関与するが観点が違う。
2. 決定論ゲートが exit0 でも、単一 skill 退化の根拠欠落は LLM 意味判定で C2 FAIL にしうる。
3. high severity が 1 件でもあれば全体 FAIL。
4. Bash 背景権限で停止する場合は caller (run-plugin-dev-plan の親セッション) が exit code を渡す。
5. 本 skill は kind=assign のため feedback_contract.criteria は N/A (評価器自身は評価基準を携帯しない)。

## Additional Resources

- `references/plan-rubric.json` — 4条件機械判定ルール (C1-C4 × checks)
- `references/four-condition-criteria.md` — 人間向け詳細基準
- `schemas/plan-findings.schema.json` — 出力スキーマ
- `prompts/R1-evaluate.md` — R1 (evaluate) 責務正本
- 実行 fork 先 agent: `../../agents/plugin-dev-plan-evaluator.md`
- caller: `run-plugin-dev-plan` (R4 verify-traceability)
