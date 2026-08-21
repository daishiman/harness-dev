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
  intent: 7 層プロンプトの実物を最小guard後に先に提示し、利用者選択時だけevaluate→governanceをpost-choiceで連鎖させる orchestrator を提供する。
  interface:
    inputs: [topic, mode, fast]
    outputs: [seven-layer-prompt.md, prompt-build-trace.json, findings.json, "handoff-*.json", completion-report]
  invariant:
    - 実prompt生成前の追加対話は行わず依頼からbriefを最尤導出し、artifact提示後にだけ診断深度を聞くこと
    - 委譲先 worker の成果物前ユーザー対話は skip し、仮定をbrief/traceへ残してartifact提示後のchoiceに委譲すること
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
  activation_state: semantic_evaluator_started
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
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-prompt-create

> 7 層プロンプトの実物を usable-first で構築する orchestrator。parse/open・secret・破損のP0 guard後に現物を先に提示し、design/elegant/governanceは利用者が選んだ後だけ起動する。

## Purpose & Output Contract

ユーザー要望 → 最尤 `prompt-brief.json` → 7 層プロンプト生成 → P0最小guard → 実artifact提示 → 利用者選択。`accept-as-is` はevaluator 0 / improver 0。その他の選択時のみ設計評価→パラダイム評価、明示release時のみgovernanceを実行する。

**入力**: `topic` (任意), `mode` ∈ {create, update}, `--fast` (任意)
**出力**:
- `plugins/<plugin>/skills/<skill>/prompts/<R-id>-<slug>.md` (skill-local-v1)
- `eval-log/prompt-build-trace.json` (`schemas/build-trace.schema.json` 準拠)
- `eval-log/docs/<NN>-<timestamp>.json` (`schemas/findings.schema.json` 準拠)
- `eval-log/handoff-<step>.json` (`schemas/handoff.schema.json` 準拠) ×7
- 完了レポート (日本語、パラメーター名のみ英語)

**初回handoff完了条件**: 実promptとbuild traceが存在し、P0最小guard pass、成果物path/試し方が提示済み。semantic/governance PASSはhandoff前提ではない。

### 起動モード

- **引数なし**: Step 1 (run-prompt-elicit) が起動、対話で topic を確定。
- **`--fast`**: new_prompt でなく、diff_lines <= 30 のときのみ design-evaluate / elegant-review を skip。判定:
  ```bash
  python3 plugins/prompt-creator/skills/run-prompt-create/scripts/evaluate-create-gates.py \
    --prompt-name "$PROMPT_NAME" --brief eval-log/prompt-brief.json --fast
  ```

## Key Rules

1. **usable-first**: briefは依頼から最尤導出し、成果物前の追加質問は行わない。`artifact_created → minimal_guard_passed → artifact_presented → user_choice_recorded → semantic_evaluator_started` の順を守る。
2. **選択後のみ重いゲート**: design/elegantは診断選択後、governanceはrelease選択後のみ。release/exhaustiveを自動昇格しない。
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
[Step 1 infer] 依頼から prompt-brief.json を最尤導出─▶
[Step 2 build]  run-prompt-creator-7layer ─→ prompt-build-trace.json
[Step 3a p0-lint] 最小guard ─▶ [artifact 提示/handoff] ─▶ [利用者choice]
  ├─ accept-as-is → evaluator=0 / improver=0 で完了
  └─ 診断選択 → design-evaluate → elegant-review
                         └─ release明示時だけ governance
```

ユーザー対話はartifact提示後の診断深度選択だけ。accept-as-isはそのまま試用し、semantic/governanceをhandoffの依存先にしない。

## Phase 別ゴールと完了条件 (宣言核)

**手順の機械正本は `workflow-manifest.json`** (phases[].dependsOn / entryHook / exitHook / resourceIds / commands / max_retry / fatal_exit_codes / handoff)。本節は各 phase の到達状態と受入条件のみを宣言し、遷移・実行の細部は実行時に manifest とゴールから導出する (手続き列挙の二重管理をしない)。責務別の停止条件は `prompts/R1-elicit.md` / `prompts/R2-gate-review.md` / `prompts/R3-governance-decide.md` の「5.3 完了チェックリスト」(l5-contract v2.0.0)。

| phase (step/gate) | ゴール (到達状態) | 完了条件 (受入基準) |
|---|---|---|
| elicit (1/-) | goals・checklistを含む schema 準拠 brief が依頼から最尤導出され保存済み | 成果物前の追加質問0、仮定はtraceに明記 |
| build (2/-) | 7 層プロンプトと `eval-log/prompt-build-trace.json` (build-trace.schema.json 準拠・Layer coverage 全 PASS/N/A/skip 理由付き) が生成済み | trace schema 検証 exit 0 (Gate 2 前提) |
| p0-lint (3a/G2) | manifest `phases[id=p0-lint].commands` (9 コマンド、ユニークスクリプト 8 本) が全 exit 0 の状態 | 全 exit 0。fail / `TODO` / 未展開 `{{...}}` / 英語仮文残存 (パラメーター名除く) は findings 付きで build へ差し戻し (最大 3 周) |
| artifact-present-handoff (3b/delivery) | 実promptのpathと試し方が提示済み | semantic/governance非依存でhandoff完了 |
| diagnostic-choice (3c/user) | 提示後のchoice receiptがある | accept-as-isはevaluator/improver 0 |
| design-evaluate (4/-) | 選択時のみfork evaluatorが C1-C4 を診断 | choice前の起動は順序違反 |
| elegant-review (4/G3) | (new_prompt or diff>30 行のみ。判定 `scripts/evaluate-create-gates.py`) C1-C4 全 PASS | FAIL 残存時のみ停止し修正ループへ |
| governance (6/-) | releaseが明示選択された場合のみ承認証跡がある | auto release/exhaustive 0 |
| report (3d/-) | usable artifact提示レポートが保存済み | design/elegant/governanceの結果を必須としない |

### 完了レポート形式 (phase=report の出力契約)
```markdown
# Prompt Creation Report: <prompt_name>
- mode: create|update
- responsibility_id: R<n>
- target_skill: <skill_name>
- delivery_events: [artifact_created, minimal_guard_passed, artifact_presented]
- user_choice: accept-as-is|light|standard|detailed
- release_event / exhaustive_event: user_choiceとは別の明示event (自動昇格なし)
- p0_lint: PASS
- evaluator_result: PASS (or not-run: accept-as-is)
- elegant_review: PASS (or not-run: accept-as-is)
- governance: approved (or not-run: release not selected)
- output_path: <path>
- residual_findings: [<未収束 finding 一覧 / 空配列なら全解消>]
- follow_up_actions: [<利用者choiceで認可された次アクション>]
```

## Gotchas

1. **delivery順序 skip 禁止**: artifact created/minimal guard/presented/user choice/evaluator startの順序証跡なしにpost-choice phaseへ進めない。
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
