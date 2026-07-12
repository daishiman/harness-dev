---
name: assign-prompt-design-evaluator
description: 生成済みプロンプトを C1-C4 と 4 パスで評価したいとき、context:fork で独立評価結果 findings.json を取得したいときに使う。
disable-model-invocation: false
user-invocable: false
context: fork
argument-hint: "[--prompt-path <path>] [--brief <path>] [--output <findings_path>]"
arguments: [prompt_path, brief, output]
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(python3 *)
  - Task
kind: assign
version: 2.1.0
effect: local-artifact
owner: team-platform
contract:
  intent: 生成済みプロンプトを親 context のバイアスから切り離して独立評価し、findings.json を返すため、C1-C4 + 4 パスの採点専用 evaluator を提供する。
  interface:
    inputs: [prompt_path, brief, output]
    outputs: [findings.json]
  invariant:
    - 必ず context:fork で起動し、親 context の解釈バイアスを引き継がないこと
    - 評価対象を書き換えず findings の出力のみ行うこと (write=findings only、Goodhart 防止)
    - C1-C4 verdict を全付与し、空 findings を残さない (PASS でも info を 1 件以上) こと
    - high severity が 1 件でもあれば全体を FAIL とすること
since: 2026-05-22
script_refs:
  - ../run-prompt-creator-7layer/scripts/verify-completeness.py
  - ../run-prompt-creator-7layer/scripts/validate-prompt.py
rubric_refs:
  - ref-skill-design-rubric              # L0: 共通設計 rubric (harness-creator 正本, 固定)
  - references/prompt-rubric.json         # L2: 本 evaluator 固有 (C1-C4 prompt 判定)
reference_refs:
  - references/resource-map.yaml
  - references/c1-c4-criteria.md
source: ../run-prompt-creator-7layer/references/quality-criteria.md
source-tier: internal
last-audited: 2026-05-22
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-evaluate.md
schema_refs:
  - ../run-prompt-create/schemas/findings.schema.json
responsibilities:
  - id: R1
    name: evaluate
    prompt_required: true
pair: run-prompt-creator-7layer
role_suffix: evaluator
---

# assign-prompt-design-evaluator

> 生成プロンプトを **C1-C4 + 4 パス** で評価し `findings.json` を返す independent evaluator。`context:fork` で起動して Sycophancy を防ぐ。

## Purpose & Output Contract

**入力**: prompt_path (評価対象 .md/.yaml) / brief (eval-log/prompt-brief.json) / output (省略時 `eval-log/docs/<NN>-<timestamp>.json`)
**出力**: `eval-log/docs/<NN>-<timestamp>.json` (`../run-prompt-create/schemas/findings.schema.json` 準拠)

**完了条件**: C1-C4 verdict 全付与 + findings[] に高/中/低の severity 配列。

## C1-C4 評価軸

| Gate | 観点 | 合格条件 |
|---|---|---|
| **C1** | Layer 整合 | L1-L7 が seven-layer-format.md と整合、Layer 番号と役割の対応が崩れていない |
| **C2** | 依存方向 | L7→L1 の単方向参照のみ。Layer N が Layer N-1 以外を参照していない |
| **C3** | 再現性 | reproducible=true。再現性根拠 (output_schema / script_refs / 検証可能な完了チェックリスト) が揃い、5.2 ゴール定義が成果状態で固定手順列挙を含まない (l5-contract v2.0.0) |
| **C4** | Self-Evaluation 充足 | L5.3 完了チェックリスト (停止条件) が非空で、全項目が第三者に YES/NO 判定可能 (数量レンジは l5-contract v2.0.0 で廃止) |

## 4 パスレビュー (Pass 0-4)

`../run-prompt-creator-7layer/references/quality-criteria.md` §7 由来:
- **Pass 0** 動的評価基準生成: `evaluation_priorities` から重み付けし以下 Pass を調整
- **Pass 1** 網羅性: 必須フィールド漏れがないか
- **Pass 2** 整合性: Layer 間/メタ/responsibility_id が矛盾しないか
- **Pass 3** 深度: 意味的に十分か (抽象的な空文句に終わっていないか)
- **Pass 4** 実用性: そのまま実行/注入できるか (placeholder 残存ゼロ)

## Key Rules

1. **context:fork 必須**: 親 context から評価対象の解釈バイアスを引き継がない。
2. **客観判定優先**: スクリプト検証可能な項目は必ずスクリプトで判定し、LLM は意味判定のみ。
3. **findings 必出**: severity ∈ {high, medium, low, info}、bucket は C1-C4 か rubric id (PR-001 等)。
4. **suggested_fix 明示**: high/medium には修正方針を 1-2 文で明記。
5. **空 findings 禁止**: PASS でも info severity で「確認した観点」を 1 件以上残す。
6. **mass_production_risk**: 同型 prompt 量産でリスクが高い設計欠陥は high を付ける。

## ゴール駆動評価 (固定手順なし)

> 正本責務は `prompts/R1-evaluate.md` Layer 5 (l5-contract v2.0.0)。単発評価 (read-only、runtime loop なし。goal-seek-paradigm 適用マトリクス: `assign-*` はループ非対象) で、検査の実施内容と順序は下記局面カタログから都度導出する。

**ゴール**: C1-C4 verdict + 4 パス結果が `findings.schema.json` 準拠 JSON として保存され、呼出元が `global_thresholds` で auto-approve 可否を機械判定できる状態。

**完了条件** (停止条件の正本 = `prompts/R1-evaluate.md` 5.3): verdicts 全付与 / scripted checks の実行証跡 / findings 非空 (PASS 時も info) / high・medium への suggested_fix / schema 検証通過 / 評価対象への書換 0 件。

**局面カタログ** (順序は都度判断):
- **客観検証 (script)**: `verify-completeness.py --input ${PROMPT_PATH}` / `validate-prompt.py --input ${PROMPT_PATH} --phase prompt` を実行し exit code を証跡化。
- **C1-C4 機械評価**: `references/prompt-rubric.json` の scripted checks (regex_match / regex_absent) を prompt_path の Layer 構造と突合。
- **意味判定 (LLM)**: non-scripted checks と Pass 0-4 (`references/c1-c4-criteria.md` / quality-criteria.md §7 準拠) を評価し findings に集約。
- **findings 出力**: `schemas/findings.schema.json` 準拠で Write。verdicts に C1-C4 PASS/FAIL/N/A、findings に severity-bucket-observations。

## Gotchas

1. C1 と C2 を混同しない (Layer 整合 vs 依存方向)。
2. Pass 3 深度判定は「具体例があるか」「checklist が客観条件か」が基準。
3. evaluation_priorities が空なら Pass 0 で標準重み (1.0) を全 Pass に付与。
4. high severity が 1 件でもあれば全体は FAIL。

## Additional Resources

- `references/prompt-rubric.json` — C1-C4 機械判定ルール
- `references/c1-c4-criteria.md` — 人間向け詳細基準
- `../run-prompt-create/schemas/findings.schema.json` — 出力スキーマ
- caller: `run-prompt-create` (Step 3b)
