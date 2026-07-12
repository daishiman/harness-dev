---
name: run-prompt-create
description: 新規プロンプト作成・既存プロンプト更新を端から端まで実行するとき、Gate/eval-log 連鎖で再現性高くプロンプトを生成するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--topic <text>] [--mode create|update] [--fast]"
arguments: [topic, mode, fast]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3 *)
  - Bash(git *)
  - AskUserQuestion
  - Skill
kind: run
version: 2.1.0
effect: local-artifact
owner: team-platform
contract:
  intent: 7 層プロンプトを要望から成果物まで品質保証付きで送り出すため、elicit→build→evaluate→governance をゲート制御で連鎖させる orchestrator を提供する。
  interface:
    inputs: [topic, mode, fast]
    outputs: [seven-layer-prompt.md, prompt-build-trace.json, findings.json, "handoff-*.json", completion-report]
  invariant:
    - Gate 1 (brief 確認) のみユーザー対話を行い、Gate 2-4 は workflow-manifest.json の auto_approve_conditions を機械評価すること
    - 委譲先 worker のユーザー対話は brief 供給時 skip し、導出確認は brief 内容と Gate 1 承認に委譲すること (user_question_budget=1)
    - 各フェーズは独立 Skill へ委譲し、本スキルは制御のみを担うこと (手順の機械正本は workflow-manifest.json、散文はゴール+完了条件のみ宣言)
    - evaluator / governance reviewer は必ず context:fork で起動すること (Sycophancy 防止)
    - 各ゲート通過時に handoff-<step>.json を schemas/handoff.schema.json 準拠で永続化すること
    - Layer 依存方向 L7→L1 を逸脱した生成物は Gate で差し戻すこと
since: 2026-05-22
script_refs:
  - scripts/evaluate-create-gates.py
  - ../run-prompt-creator-7layer/scripts/verify-completeness.py
  - ../run-prompt-creator-7layer/scripts/validate-prompt.py
reference_refs:
  - references/resource-map.yaml
  - references/governance-params.json
source: plugins/prompt-creator/skills/run-prompt-create/
source-tier: internal
last-audited: 2026-05-22
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-gate-review.md
  - prompts/R3-governance-decide.md
schema_refs:
  - schemas/prompt-brief.schema.json
  - schemas/build-trace.schema.json
  - schemas/findings.schema.json
  - schemas/handoff.schema.json
manifest: workflow-manifest.json
responsibilities:
  - id: R1
    name: elicit
    prompt_required: true
  - id: R2
    name: gate-review
    prompt_required: true
  - id: R3
    name: governance-decide
    prompt_required: true
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: workflow-manifest.json phases[id=p0-lint] の 9 コマンド (ユニークスクリプト 8 本、validate-prompt は prompt/trace の 2 phase 実行) が全て exit 0 で通り、未解決 TODO や未展開プレースホルダ {{...}} や英語仮文の残存(パラメーター名を除く)を検出した場合は Step 2 へ自律差し戻すことを lint で機械検証できる。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 各ゲート通過時に eval-log/handoff-<step>.json が schemas/handoff.schema.json 準拠で永続化され、Gate 2-4 が workflow-manifest.json の auto_approve_conditions を機械評価した証跡を伴うことを script で機械検証できる。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: orchestrator が制御のみを担い各フェーズを独立 Skill へ委譲する責務分割と、evaluator や governance reviewer を必ず fork コンテキスト(context=fork)で起動する Sycophancy 防止と、Layer 依存方向 L7→L1 不変の差し戻しが、ユーザ目的(再現性高い 7 層プロンプト生成)に対し過不足ないこと。
      verify_by: elegant-review
---

# run-prompt-create

> 端から端まで 7 層プロンプトを構築する **orchestrator skill**。Gate 1 のみユーザー確認を行い、以降は manifest 条件に基づく自動ゲートと eval-log 永続化で再現性を担保する。

## Purpose & Output Contract

ユーザー要望 → `prompt-brief.json` → 7 層プロンプト生成 → P0 lint → 設計評価 → パラダイム評価 → governance 承認 を**ゲートあり自動連鎖**で実行する orchestrator。各 Step/Gate の機械可読定義は `workflow-manifest.json`、責務別プロンプトは `prompts/*.md`、データ契約は `schemas/*.schema.json`。

**入力**: `topic` (任意), `mode` ∈ {create, update}, `--fast` (任意)
**出力**:
- `plugins/<plugin>/skills/<skill>/prompts/<R-id>-<slug>.md` (skill-local-v1)
- `eval-log/prompt-build-trace.json` (`schemas/build-trace.schema.json` 準拠)
- `eval-log/docs/<NN>-<timestamp>.json` (`schemas/findings.schema.json` 準拠)
- `eval-log/handoff-<step>.json` (`schemas/handoff.schema.json` 準拠) ×7
- 完了レポート (日本語、パラメーター名のみ英語)

**完了条件**: P0 lint pass + (`--fast` でない場合は evaluator JSON pass と elegant-review pass) + `workflow-manifest.json` の `auto_approve_conditions` 全充足または governance handoff 確定。

### 起動モード

- **引数なし**: Step 1 (run-prompt-elicit) が起動、対話で topic を確定。
- **`--fast`**: new_prompt でなく、diff_lines <= 30 のときのみ design-evaluate / elegant-review を skip。判定:
  ```bash
  python3 plugins/prompt-creator/skills/run-prompt-create/scripts/evaluate-create-gates.py \
    --prompt-name "$PROMPT_NAME" --brief eval-log/prompt-brief.json --fast
  ```

## Key Rules

1. **自動承認既定**: 初回 brief 確定 (Gate 1) のみユーザーに AskUserQuestion を発行。Gate 2-4 は `workflow-manifest.json` の `auto_approve_conditions` を機械評価し、全充足時は `solo_operator_auto` で自動承認。brief を供給して委譲する worker 側のユーザー対話 (導出確認・出力先指定等) は skip し、導出確認は brief 内容と Gate 1 承認に委譲する (user_question_budget=1)。
2. **条件不充足時のみ停止**: P0 lint fail / evaluator FAIL / Layer 依存違反 / 充足率 95% 未満などのいずれかで停止し findings 提示。
3. **子スキルへの委譲**: 各フェーズは独立 Skill を Skill tool で起動 (`workflow-manifest.json` の `delegateSkill`)。本スキルは制御のみ。
4. **context:fork**: evaluator/governance reviewer は必ず context:fork で起動 (Sycophancy 防止)。
5. **handoff 保存**: 各ゲート通過時に `eval-log/handoff-<step>.json` を `schemas/handoff.schema.json` 準拠で残す。
6. **resource-map 先読み**: `references/resource-map.yaml` を最初に読み、必要ファイルのみ open。
7. **日本語成果物**: 本文・レビュー・完了レポートを日本語に保つ (パラメーター名・JSON キー・CLI 引数は英語)。
8. **Markdown 既定**: 新規 prompt は `prompts/<R-id>-<slug>.md` で `../run-prompt-creator-7layer/references/seven-layer-markdown-template.md` 写経 (YAML は legacy のみ許容、新規禁止)。
9. **Layer 依存方向不変**: L7 → L6 → ... → L1。逆方向参照は C2 FAIL。
10. **質ベース判定**: 数量カウント (3 つ以上等) を排し「実行可能か」「検証可能か」で判定。doc/prompt-creator/ 由来の核心原則。
11. **要素原子性**: 1 フィールド=1 概念、1 値=1 短文 (50 字目安)。長文は分解。
12. **目的+背景併記**: 全ルール/制約に「目的」と「背景」を必ず併記する記述スタイル。

## End-to-End Flow (概観図。正本は workflow-manifest.json)

```
[Step 1 elicit] run-prompt-elicit ─→ prompt-brief.json ─[Gate 1 ★唯一の対話]─▶
[Step 2 build]  run-prompt-creator-7layer ─→ prompt-build-trace.json
[Step 3a p0-lint] (fail→Step 2、最大 3 周) ─[Gate 2 自動]─▶
[Step 3b design-evaluate] assign-prompt-design-evaluator (context:fork) ─→ findings
[Step 4 elegant-review] (条件: new or >30 行, context:fork) ─[Gate 3 自動]─▶
[Step 5 governance] (manifest 条件充足で solo_operator_auto) ─[Gate 4 自動]─▶
[Step 6 report]
```

★ ユーザー対話は Gate 1 のみ。Gate 2-4 は `workflow-manifest.json` の `auto_approve_conditions` を機械評価し、全充足で自動承認。1 条件でも不充足なら findings 提示 + 修正ループ。

## Phase 別ゴールと完了条件 (宣言核)

**手順の機械正本は `workflow-manifest.json`** (phases[].dependsOn / entryHook / exitHook / resourceIds / commands / max_retry / fatal_exit_codes / handoff)。本節は各 phase の到達状態と受入条件のみを宣言し、遷移・実行の細部は実行時に manifest とゴールから導出する (手続き列挙の二重管理をしない)。責務別の停止条件は `prompts/R1-elicit.md` / `prompts/R2-gate-review.md` / `prompts/R3-governance-decide.md` の「5.3 完了チェックリスト」(l5-contract v2.0.0)。

| phase (step/gate) | ゴール (到達状態) | 完了条件 (受入基準) |
|---|---|---|
| elicit (1/G1) | goals (成果状態)・checklist (item+judgement) を含む schema 準拠 brief が `eval-log/prompt-brief.json` に保存済み | R1 5.3 全充足 + Gate 1 ユーザー承認 (唯一の対話。否認は最大 3 周) |
| build (2/-) | 7 層プロンプトと `eval-log/prompt-build-trace.json` (build-trace.schema.json 準拠・Layer coverage 全 PASS/N/A/skip 理由付き) が生成済み | trace schema 検証 exit 0 (Gate 2 前提) |
| p0-lint (3a/G2) | manifest `phases[id=p0-lint].commands` (9 コマンド、ユニークスクリプト 8 本) が全 exit 0 の状態 | 全 exit 0。fail / `TODO` / 未展開 `{{...}}` / 英語仮文残存 (パラメーター名除く) は findings 付きで build へ差し戻し (最大 3 周) |
| design-evaluate (3b/-) | fork した evaluator の findings (`eval-log/docs/<NN>-<timestamp>.json`, findings.schema.json 準拠) に C1-C4 FAIL がない | FAIL は build へ自律差し戻し (最大 3 周)。未収束は governance へ昇格し solo_operator_auto 失効を判定 |
| elegant-review (4/G3) | (new_prompt or diff>30 行のみ。判定 `scripts/evaluate-create-gates.py`) C1-C4 全 PASS | FAIL 残存時のみ停止し修正ループへ |
| governance (5/G4) | preconditions (環境前提) 成立かつ `auto_approve_conditions` 全充足が各 evidence で機械評価済み → solo_operator_auto。不成立は `run-skill-rubric-governance` の手動承認確定 | manifest `governance.auto_approve_conditions` の evidence 全 PASS または手動承認 handoff (R3 5.3 全充足) |
| report (6/-) | 下記形式の完了レポートが提示され `handoff-prompt_done.json` 保存済み | レポート必須項目が全て埋まっている |

### 完了レポート形式 (phase=report の出力契約)
```markdown
# Prompt Creation Report: <prompt_name>
- mode: create|update
- responsibility_id: R<n>
- target_skill: <skill_name>
- gates_passed: [1,2,3,4]
- p0_lint: PASS
- evaluator_result: PASS
- elegant_review: PASS (or N/A)
- governance: solo_auto_approved (or manual)
- output_path: <path>
- residual_findings: [<未収束 finding 一覧 / 空配列なら全解消>]
- follow_up_actions: [<AI が自動選定した次アクション>]
```

## Gotchas

1. **Gate 条件 skip 禁止**: Gate 1 は明示確認必須。Gate 2-4 は manifest 条件の評価証跡なしに進めない。
2. **同一 context 評価禁止**: evaluator/governance reviewer は必ず context:fork。
3. **lint 失敗時の自動修正禁止**: 根本原因をユーザー提示。
4. **mode=update 時の改名**: prompt 名変更は `run-skill-rename` 相当を経由 (本スキル対象外)。
5. **context 予算**: SKILL.md / 各 prompt 300 行以下、`references/` は Phase 直前で必要分のみ読込。
6. **manifest 二重管理禁止**: 手書き追加後も `lint-manifest-contents.py` を必ず通す。

## Additional Resources

`references/resource-map.yaml` を最初に読む。主要参照:

- `workflow-manifest.json` — Step/Gate/Phase の機械可読定義
- `schemas/prompt-brief.schema.json` — Step 1→2 渡し正本スキーマ
- `schemas/handoff.schema.json` — Gate 通過時 handoff 共通形式
- `schemas/findings.schema.json` — evaluator/elegant-review 出力形式 (C1-C4)
- `schemas/build-trace.schema.json` — Step 2 emit する Layer 別 coverage 形式
- `prompts/R1-elicit.md` / `prompts/R2-gate-review.md` / `prompts/R3-governance-decide.md` — R1/R2/R3 責務別プロンプト
- 子スキル: `run-prompt-elicit`, `run-prompt-creator-7layer`, `assign-prompt-design-evaluator`, `run-elegant-review` (harness-creator), `run-skill-rubric-governance` (harness-creator)
