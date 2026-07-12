---
name: assign-system-spec-completeness-evaluator
description: 生成された仕様書ドキュメントセットの完成度を独立 context で評価したいとき、上位概念trace・意思決定・マトリクス網羅性・設計知識反映・最新ドキュメント出典・prompt品質の 6 観点で合否判定したいときに使う。
disable-model-invocation: false
user-invocable: false
context: fork
argument-hint: "[--spec-dir <path>] [--output <report_path>]"
arguments: [spec_dir, output]
kind: assign
prefix: assign
role_suffix: evaluator
version: 0.1.0
effect: local-artifact
owner: team-platform
since: 2026-07-11
source: plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/references/scoring-rubric.json
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
allowed-tools:
  - Read
  - Bash
  - Task
responsibility_refs:
  - prompts/R1-score.md
  - prompts/R2-delegate.md
responsibilities:
  - id: R1
    name: score
    prompt_required: true
  - id: R2
    name: delegate
    prompt_required: true
rubric_refs:
  - references/scoring-rubric.json
reference_refs:
  - references/resource-map.yaml
  - references/aspect-criteria.md
script_refs:
  - scripts/aggregate-completeness.py
  - ../../scripts/validate-coverage-matrix.py
schema_refs:
  - schemas/completeness-findings.schema.json
agent_refs:
  - ../../agents/system-spec-matrix-auditor.md
  - ../../agents/system-spec-hearing-auditor.md
  - ../../agents/system-spec-doc-freshness-auditor.md
feedback_contract:
  skip_reason: "assign kind は loop criteria 対象外。合否基準は checklist の 6 評価観点 (foundation_trace/decision_guidance/prompt_quality=C05 自前評価 / matrix_coverage=C07 監査 + C06 ヒアリング品質 sub-input / design_knowledge_reflection=C05 自前評価 / doc_freshness=C08 監査) の evaluator ゲート、および validate-coverage-matrix.py の決定論ゲートで担保する。"
---

# assign-system-spec-completeness-evaluator

> 生成された仕様書ドキュメントセットを、上位概念trace / 意思決定根拠 / マトリクス網羅性 / deep knowledge目的適合 / 最新出典 / prompt品質の観点で評価し、観点別スコア + 総合判定 (PASS/FAIL) + 不足事項一覧を返す independent evaluator。`context:fork` で生成者と評価者を分離する。

## Purpose & Output Contract

**入力**: `system-spec/*.md` + index (C03 出力) / `spec-state.json` (C01) / `fetched-references.json` (C02)
**出力**: 評価レポート (`schemas/completeness-findings.schema.json` 準拠) — 観点別スコア + 総合判定 + 不足事項一覧
**完了条件**: 全観点 verdict 付与 + findings[] (info 以上を最低 1 件) + 総合判定が観点スコアからの fail-closed 再導出値と一致 + 総合 FAIL 時は不足事項一覧が非空。

各 skill 単独では見えない全体網羅性の欠落を、生成物から独立した context で評価し客観的合否を返す。

## 監査 sub-agent 対応 (全 6 観点中、sub-agent 関与が判定に効く 3 観点)

> 本 skill は全 6 観点 (上位概念trace / 意思決定 / マトリクス網羅性 / 設計知識反映 / 最新ドキュメント出典 / prompt品質) を採点する (schema/rubric/aggregate-completeness の正本)。うち foundation_trace / decision_guidance / prompt_quality は C05 R1-score の自前評価。以下は監査 sub-agent の関与が判定に効く 3 観点の対応表。

| 観点 (aspect id) | ラベル | 評価主体 (component) | 一次根拠 |
|---|---|---|---|
| `matrix_coverage` | マトリクス網羅性 | `system-spec-matrix-auditor` (C07) + sub-input `system-spec-hearing-auditor` (C06) | `validate-coverage-matrix.py --require-complete` の exit0 + 意味層。C06 の 4 軸 (聞き漏れ/誘導/早期停止/トレーサビリティ) を網羅性・トレースの補助根拠に併せる |
| `design_knowledge_reflection` | 設計知識反映 | C05 R1-score が自前評価 (**独立 auditor なし**) | 機械層=各章の設計知識ポインタ存在 (compile 注入) + 意味層=そのポインタ原則の確定セルへの具体適用 (存在確認だけで PASS にしない = Goodhart 防止) |
| `doc_freshness` | 最新ドキュメント出典 | `system-spec-doc-freshness-auditor` (C08) | 二層監査 (形式=`validate-source-citation.py` / 内容鮮度=公式再照合) |

> `system-spec/*.md` を読まない C06 (hearing-auditor) を設計知識反映へ束縛するのは虚偽対応のため撤去した。C06 はヒアリング品質を担い matrix_coverage の sub-input へ再配置し、設計知識反映は C05 が system-spec/*.md と resource-map から自前評価する。監査 sub-agent (C07/C08 と matrix sub-input の C06) は Task tool でそれぞれ独立 context (fork) に起動する (R2-delegate)。監査ロジックは各 agent の SSOT prompt に委ね、本 skill は結果を集約するだけで書き換えない。

## 評価レポート形状 (schema)

```
{
  "evaluator": {"name": "assign-system-spec-completeness-evaluator", "version": "0.1.0", "context": "fork"},
  "verdict": "PASS" | "FAIL",
  "aspects": {
    "foundation_trace":             {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...},
    "decision_guidance":            {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...},
    "matrix_coverage":              {"verdict": "PASS|FAIL|INDETERMINATE", "auditor": "system-spec-matrix-auditor", "component": "C07", "summary": "...", "evidence": [...]},
    "design_knowledge_reflection":  {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...},
    "doc_freshness":                {"verdict": "...", "auditor": "system-spec-doc-freshness-auditor", "component": "C08", "summary": "...", ...},
    "prompt_quality":               {"verdict": "...", "auditor": "assign-system-spec-completeness-evaluator", "component": "C05", "summary": "...", ...}
  },
  "gate_results": [ {"id": "G-matrix", "name": "validate-coverage-matrix", "exit_code": 0, ...} ],
  "findings": [ {"severity": "high|medium|low|info", "bucket": "...", "observation": "...", "suggested_fix": "..."} ],
  "gaps": [ "不足事項1", ... ]
}
```

## 総合判定 (fail-closed 集約)

- 全観点PASS **かつ** high severity finding 0 件のときだけ総合 PASS。
- 1 観点でも FAIL/INDETERMINATE、または high finding が 1 件でもあれば総合 FAIL。
- 全観点を過不足なく評価していなければ総合 FAIL (監査観点の取りこぼしを PASS にしない)。
- 総合判定は `scripts/aggregate-completeness.py` の `aggregate_verdict` で再導出でき、レポートの `verdict` と一致すること (総合判定が観点スコアに接地しているかの整合検査 = Goodhart 防止)。

## Key Rules

1. **context:fork 必須**: 生成側 (elicit/doc-fetch/compile) の「網羅できた」自己肯定バイアスを断つ。
2. **proposer ≠ approver**: 評価者は仕様書を書き換えない (read-only)。修正は elicit/doc-fetch/compile への差し戻し (Goodhart 防止)。
3. **決定論ゲート優先**: マトリクス網羅性は `validate-coverage-matrix.py` の exit code を一次根拠にし、自然言語で PASS 判定しない。
4. **空 findings 禁止**: PASS 時も info severity で「確認した観点」を 1 件以上残す。
5. **総合 FAIL は差し戻し材料付き**: gaps (不足事項一覧) を非空にし、どの skill (elicit/doc-fetch/compile) または監査再実行へ戻すかを記す。

## Steps

正本責務は `prompts/R1-score.md` (スコアリング) と `prompts/R2-delegate.md` (監査 fork 集約)。要約:

### Step 1: 観点別監査を独立 context で集約 (R2-delegate)
Task tool で監査 sub-agent (`system-spec-matrix-auditor` (C07) / `system-spec-hearing-auditor` (C06) / `system-spec-doc-freshness-auditor` (C08)) をそれぞれ fork する。C07 は matrix_coverage、C08 は doc_freshness の一次根拠。C06 はヒアリング品質を監査し matrix_coverage の sub-input として併せる。design_knowledge_reflection は独立 auditor を立てず Step 3 で C05 自身が評価する。

### Step 2: マトリクス網羅性の決定論ゲート
```bash
PLUGIN_ROOT=plugins/system-spec-harness
python3 "$PLUGIN_ROOT/scripts/validate-coverage-matrix.py" --matrix <spec-state.json> --require-complete
```
exit0 をマトリクス網羅性観点の一次根拠にする (`scripts/aggregate-completeness.py --matrix ...` でも回収可)。

### Step 3: 設計知識反映の自前評価 (独立 auditor なし)
C05 R1-score が `system-spec/*.md` 各章を直接読み、`ref-system-design-knowledge/references/resource-map.yaml` 由来の設計知識ポインタの (1) 存在 (機械層) と (2) その原則が確定セル要件へ具体適用されているか (意味層) を評価する。**存在確認だけで PASS にしない** (compile が機械注入するポインタを自己循環で肯定しない = Goodhart 防止)。汎用ポインタ (resource-map 索引) のみで具体適用が無い章は medium 以上で拾う。C06 のヒアリング品質監査は本観点でなく matrix_coverage の sub-input として使う。

### Step 4: レポート出力と整合検査
`schemas/completeness-findings.schema.json` 準拠で評価レポートを出力。`scripts/aggregate-completeness.py --report <report.json>` で形状 + 総合判定整合 (fail-closed 再導出との一致) を検証する。

## Gotchas

1. 観点↔評価主体を取り違えない (マトリクス=C07 + C06 ヒアリング品質 sub-input / 設計知識=C05 自前評価・独立 auditor なし / 出典鮮度=C08)。C06 は system-spec/*.md を読まないため設計知識反映へ束縛しない。
2. 決定論ゲート exit0 でも、意味層 (対象外理由の具体性 / 非公式 host / 設計知識反映の形骸化) で FAIL にしうる。
3. high severity が 1 件でもあれば総合 FAIL。
4. INDETERMINATE は fail-closed で FAIL に寄せ、仕様書修正でなく監査再実行/入力補完へ差し戻す。
5. 本 skill は kind=assign のため feedback_contract.criteria は N/A (評価器自身は評価基準を携帯せず、checklist 観点 + evaluator ゲートで担保。frontmatter の skip_reason 参照)。

## Additional Resources

- `references/scoring-rubric.json` — 全 6 観点機械判定ルールと fail-closed 集約ポリシー
- `references/aspect-criteria.md` — 観点別意味判定の詳細基準 + 観点↔監査 agent 対応
- `schemas/completeness-findings.schema.json` — 評価レポート出力スキーマ
- `scripts/aggregate-completeness.py` — レポート形状検証 + 総合 fail-closed 集約 (決定論)
- `prompts/R1-score.md` / `prompts/R2-delegate.md` — R1 (スコアリング) / R2 (監査 fork 集約) 責務正本
- fork 先 agent: `../../agents/system-spec-{matrix,hearing,doc-freshness}-auditor.md`
