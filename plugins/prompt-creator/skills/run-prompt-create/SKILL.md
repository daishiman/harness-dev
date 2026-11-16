---
name: run-prompt-create
description: 新規プロンプト作成・既存プロンプト更新を端から端まで実行するとき、Gate/eval-log 連鎖で再現性高くプロンプトを生成するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--topic <text>] [--mode create|update]"
arguments: [topic, mode]
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
  - Agent
kind: run
version: 2.1.0
effect: local-artifact
goal_seek:
  engine: inline
  fork: inline
owner: team-platform
contract:
  intent: 7 層プロンプトの実物を最小guard後に先に提示し、利用者が診断を選んだときだけ fork evaluator 1 つで C1-C4 を診断し、release を明示したときだけ governance を起動する orchestrator を提供する。
  interface:
    inputs: [topic, mode]
    outputs: [seven-layer-prompt.md, prompt-build-trace.json, "eval-log/docs/*.json (findings)", "handoff-*.json", completion-report]
  invariant:
    - 実prompt生成前の追加対話は行わず依頼からbriefを最尤導出し、artifact提示後にだけ現状で試すか診断するかを聞くこと
    - 委譲先 worker の成果物前ユーザー対話は skip し、仮定をbrief/traceへ残してartifact提示後のchoiceに委譲すること
    - brief 推定・生成・診断は独立 Skill へ委譲し、本スキルは制御と handoff の記録だけを担うこと (手順の機械正本は workflow-manifest.json、散文はゴール+完了条件のみ宣言)
    - evaluator (design-evaluate) と governance reviewer (governance で R3 を読む subagent) は必ず context:fork で起動すること (Sycophancy 防止)
    - 各 phase の handoff を manifest phases[].handoff の path へ schemas/handoff.schema.json 準拠で永続化すること (数値の gate_id を持つのは p0-lint の Gate 2 だけ)
    - Layer 依存方向 L7→L1 を逸脱した生成物は、diagnose 選択後の design-evaluate で C2 FAIL とし、利用者が選んだ改善の深さの対象なら build へ差し戻すこと
since: 2026-05-22
script_refs:
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
      text: workflow-manifest.json phases[id=p0-lint] の 9 コマンド (ユニークスクリプト 8 本、validate-prompt は prompt/trace の 2 phase 実行) が全て exit 0 で通り、未解決 TODO や未展開プレースホルダ {{...}} の残存を検出した場合は Step 2 へ自律差し戻すことを lint で機械検証できる。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: workflow-manifest.json の各 phase が eval-log/handoff-*.json の保存先を 1 つずつ持ち、数値の Gate を持つのは p0-lint (Gate 2。commands の exit code で判定) だけで、各 phase の handoff の見本が schemas/handoff.schema.json に通ることを test で機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: orchestrator が制御と handoff の記録のみを担い brief 推定・生成・診断を独立 Skill へ委譲する責務分割と、evaluator や governance reviewer を必ず fork コンテキスト(context=fork)で起動する Sycophancy 防止と、Layer 依存方向 L7→L1 違反を design-evaluate の C2 で差し戻す仕組みが、ユーザ目的(再現性高い 7 層プロンプト生成)に対し過不足ないこと。
      verify_by: elegant-review
artifact_delivery: artifact-delivery-v1
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/diagnoseを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはdiagnoseが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-prompt-create

> 7 層プロンプトの実物を usable-first で構築する orchestrator。parse/open・secret・破損のP0 guard後に現物を先に提示し、C1-C4 の設計評価は利用者が診断を選んだときだけ fork evaluator 1 つで行う。governance は release を明示したときだけ起動する。

## Purpose & Output Contract

ユーザー要望 → 最尤 `prompt-brief.json` → 7 層プロンプト生成 → P0最小guard → 実artifact提示 → 利用者選択。`accept-as-is` はevaluator 0 / improver 0。`diagnose` を選んだときだけ設計評価 (C1-C4) を 1 回行う。governance は release の別の明示 event でだけ実行する。

**入力**: `topic` (任意), `mode` ∈ {create, update}
**出力**:
- `plugins/<plugin>/skills/<skill>/prompts/<R-id>-<slug>.md` (skill-local-v1)
- `eval-log/prompt-build-trace.json` (`schemas/build-trace.schema.json` 準拠)
- `eval-log/docs/<NN>-<timestamp>.json` (`schemas/findings.schema.json` 準拠)
- `eval-log/handoff-*.json` (`schemas/handoff.schema.json` 準拠。保存先は manifest `phases[].handoff` の path。8 phase 分あり、accept-as-is なら elicit・build・p0-lint・提示・診断選択・report の 6 件)
- 完了レポート (日本語、パラメーター名のみ英語)

**初回handoff完了条件**: 実promptとbuild traceが存在し、P0最小guard pass、成果物path/試し方/推定した仮定 (brief の open_questions) が提示済み。semantic/governance PASSはhandoff前提ではない。

### 起動モード

- **対象**: 本スキルが作るのは、skill が持つ責務 (target_skill の responsibilities[].id) の prompt だけ。skill に紐付かない standalone の prompt は対象外。
- **引数なし**: 依頼文と会話から topic・target_skill・responsibility_id・mode を最尤推定し、`run-prompt-elicit --batch` に渡す (AskUserQuestion も interview agent も使わない)。推定した仮定は brief の open_questions に残す。topic の手がかりが無いとき、または target_skill を特定できない standalone の依頼のときは brief を作らずに止め (exit 2)、`--topic <text>` 付きの起動例と、standalone の 2 段の経路 (`run-prompt-elicit` を単独で起動して brief と出力先 output_path を決める → `run-prompt-creator-7layer --skill-brief <brief> --output <output_path>`) を示す。
- **responsibility_id**: target_skill の responsibilities[].id の中からだけ推定する。依頼が名指しした R-id がそこに無ければ brief を作らずに止め (exit 2)、実在する R-id を示す。
- **`--mode`**: 指定があれば従う。無ければ target_skill の `prompts/<R-id>-*.md` があれば update、無ければ create と推定し、open_questions に残す。update は既存 prompt の path を build で `run-prompt-creator-7layer --output` に渡し、7layer が既存を分解して冪等に更新する。`--mode update` で既存が無い、または `--mode create` で既存があるときは止める (exit 2)。
- 評価を省く専用の起動モードは持たない。評価するかどうかは、現物を見た利用者が diagnostic-choice で選ぶ (`accept-as-is` なら evaluator 0)。

## Key Rules

1. **usable-first**: briefは依頼から最尤導出し、成果物前の追加質問は行わない。`artifact_created → minimal_guard_passed → artifact_presented → user_choice_recorded → semantic_evaluator_started` の順を守る。
2. **選択後のみ評価**: C1-C4 の設計評価は診断選択後に design-evaluate (fork evaluator) 1 つだけ、governance は利用者が自分から release を求めたとき (handoff の release_event) だけ。改善の深さは指摘を見せたあとに 1 回だけ聞く。release/exhaustiveを自動昇格しない。
3. **子スキルへの委譲**: brief 推定・生成・診断は独立 Skill を Skill tool で起動 (`workflow-manifest.json` の `delegateSkill`)。`delegateSkill` が null の phase は manifest の commands と R2 で進め、governance だけは manifest の `subagent` に R3 を読ませて進める。本スキルは制御と handoff の記録のみ。
4. **context:fork**: evaluator (design-evaluate) と governance reviewer (governance で `prompts/R3-governance-decide.md` を読む subagent) は必ず context:fork で起動 (Sycophancy 防止)。governance reviewer は Agent tool を `subagent_type=general-purpose` で起動し (会話を引き継ぐ fork 型は使わない)、R3 と入力の path だけを渡す。main context は R3 を読まず、governance の handoff (approver=solo_operator_auto・governance_decision) を書かない。
5. **handoff 保存**: 各 phase の終わりに manifest `phases[].handoff` の path へ `schemas/handoff.schema.json` 準拠で残す。数値の gate_id を持つのは p0-lint の Gate 2 だけで、ほかの phase は null。
6. **resource-map 先読み**: `references/resource-map.yaml` を最初に読み、必要ファイルのみ open。
7. **日本語成果物**: 本文・レビュー・完了レポートを日本語に保つ (パラメーター名・JSON キー・CLI 引数は英語)。
8. **Markdown 既定**: 新規 prompt は `prompts/<R-id>-<slug>.md` で `../run-prompt-creator-7layer/references/seven-layer-markdown-template.md` 写経 (YAML は legacy のみ許容、新規禁止)。
9. **Layer 依存方向不変**: L7 → L6 → ... → L1。逆方向参照は C2 FAIL。
10. **質ベース判定**: 数量カウント (3 つ以上等) を排し「実行可能か」「検証可能か」で判定。doc/prompt-creator/ 由来の核心原則。
11. **要素原子性**: 1 フィールド=1 概念、1 値=1 短文 (50 字目安)。長文は分解。
12. **目的+背景併記**: 全ルール/制約に「目的」と「背景」を必ず併記する記述スタイル。

## End-to-End Flow (概観図。正本は workflow-manifest.json)

```
[Step 1 infer] 依頼から prompt-brief.json を最尤導出 (run-prompt-elicit --batch)─▶
[Step 2 build]  run-prompt-creator-7layer ─→ prompt-build-trace.json
[Step 3a p0-lint] Gate 2 (commands の exit code) ─▶ [3b 提示/handoff] ─▶ [3c 利用者choice]
  ├─ accept-as-is → evaluator=0 / improver=0 で report (3d)
  └─ diagnose → design-evaluate (fork evaluator 1 つで C1-C4)
        └─ 指摘を提示 → 改善の深さを 1 回だけ聞く
             ├─ findings-only → report
             └─ light / standard / detailed → 選んだ finding を build へ (最大 1 / 2 / 3 周)
        └─ release_event があるときだけ governance (Agent tool で起動した R3) → report
```

ユーザー対話は artifact 提示後の診断選択と、diagnose のときに指摘を見せたあとの改善の深さの選択だけ (各 1 回)。accept-as-isはそのまま試用し、semantic/governanceをhandoffの依存先にしない。

## Phase 別ゴールと完了条件 (宣言核)

**手順の機械正本は `workflow-manifest.json`** (phases[].dependsOn / entryHook / exitHook / resourceIds / commands / max_retry / fatal_exit_codes / handoff)。本節は各 phase の到達状態と受入条件のみを宣言し、遷移・実行の細部は実行時に manifest とゴールから導出する (手続き列挙の二重管理をしない)。責務別の停止条件は `prompts/R1-elicit.md` / `prompts/R2-gate-review.md` / `prompts/R3-governance-decide.md` の「5.3 完了チェックリスト」(l5-contract v2.0.0)。

| phase (step/gate) | ゴール (到達状態) | 完了条件 (受入基準) |
|---|---|---|
| elicit (1/-) | goals・checklistを含む schema 準拠 brief が依頼から最尤導出され保存済み | 成果物前の追加質問0、仮定は brief の open_questions に明記。topic の手がかりが無い・standalone・名指しの R-id が target_skill に無い・mode と既存 prompt の有無が食い違う依頼なら brief を作らず exit 2 (起動モード) |
| build (2/-) | 7 層プロンプトと `eval-log/prompt-build-trace.json` (build-trace.schema.json 準拠・Layer coverage 全 PASS/N/A/skip 理由付き) が生成済み | trace schema 検証 exit 0 (Gate 2 前提) |
| p0-lint (3a/G2) | manifest `phases[id=p0-lint].commands` (9 コマンド、ユニークスクリプト 8 本) が全 exit 0 の状態 | 全 exit 0 (Gate 2 は exit code だけで判定)。fail / `TODO` / 未展開 `{{...}}` は findings 付きで build へ差し戻し (最大 3 周)。英語の仮文は機械検出せず、diagnose 後の design-evaluate の C4 で意味判定する |
| artifact-present-handoff (3b/-) | 実promptのpathと試し方と、推定で決めた仮定 (brief の open_questions の要約) が提示済み | semantic/governance非依存でhandoff完了 |
| diagnostic-choice (3c/-) | 提示後の choice が handoff の user_choice にある | accept-as-isはevaluator/improver 0 |
| design-evaluate (4/-) | diagnose 選択時だけ fork evaluator が C1-C4 を 1 回診断し、指摘を見せたあとで利用者が選んだ改善の深さが handoff の improvement_depth にある | choice前の起動は順序違反。深さは 1 回だけ聞き、選んだ深さの finding だけを build へ戻す (findings-only 0 / light 1 / standard 2 / detailed 3 周。選んだ finding が解消したら上限前に止める)。周回番号は handoff の improvement_round (初回 0)、再診断では深さを聞き直さず approver=system_auto |
| governance (5/-) | 利用者が自分から release を求めた (handoff の release_event がある) 場合だけ、Agent tool で起動した governance reviewer (R3) が auto_approve_conditions を evidence で判定し、その handoff を自分で書いている | auto release/exhaustive 0・追加質問 0。条件を満たさなければ required_fixes を付けて blocked で report へ。利用者が直すよう求めたときだけ required_fixes を build へ戻して governance まで 1 周する (manifest `governance.on_blocked`)。blocked を approved に書き換えない |
| report (3d/-) | usable artifact提示レポートが保存済み | design-evaluate/governanceの結果を必須としない |

### 完了レポート形式 (phase=report の出力契約)
```markdown
# Prompt Creation Report: <prompt_name>
- mode: create|update
- responsibility_id: R<n>
- target_skill: <skill_name>
- delivery_events: [artifact_created, minimal_guard_passed, artifact_presented]
- user_choice: accept-as-is|diagnose
- assumptions: [<brief の open_questions の要約 / 空配列なら仮定なし>]
- release_event: <利用者の発言の引用> (or none。user_choiceとは別の明示event で、自動昇格なし)
- exhaustive: not-supported (成果物全体を見直すときは run-elegant-review を明示的に呼ぶ)
- p0_lint: PASS (Gate 2)
- evaluator_result: PASS|FAIL (or not-run: accept-as-is)
- improvement_depth: findings-only|light|standard|detailed (or not-run: 診断しなかったとき)
- governance: approved|blocked (or not-run: release not requested / not-run: release requested after accept-as-is)
- governance_required_fixes: [<blocked のときの required_fixes / 空配列なら該当なし>]
- resume_command: <accept-as-is のあとで release を求められたときの再実行コマンド> (or none)
- output_path: <path>
- residual_findings: [<未収束 finding 一覧 / 空配列なら全解消>]
- follow_up_actions: [<利用者choiceで認可された次アクション>]
```

## Gotchas

1. **delivery順序 skip 禁止**: artifact created/minimal guard/presented/user choice/evaluator startの順序証跡なしにpost-choice phaseへ進めない。
2. **同一 context 評価禁止**: evaluator (design-evaluate) と governance reviewer (R3) は必ず context:fork。governance reviewer を会話を引き継ぐ fork 型で起動したり、main context が R3 を読んで判定したりしない (manifest `governance.subagent`)。
3. **lint 失敗を手で直さない**: Gate 2 が通らなければ、本スキルは自分で直さず findings を付けて build へ戻す (最大 3 周)。3 周で通らなければ止め、失敗した command と根本原因を利用者に示す。
4. **mode=update 時の改名**: update は既存 prompt の path のまま更新する (起動モード)。prompt 名変更は `run-skill-rename` 相当を経由 (本スキル対象外)。
5. **context 予算**: SKILL.md / 各 prompt 300 行以下、`references/` は Phase 直前で必要分のみ読込。
6. **manifest 二重管理禁止**: 手書き追加後も `lint-manifest-contents.py` を必ず通す。
7. **評価の二重化禁止**: C1-C4 は design-evaluate の findings を正本とし、同じ成果物を elegant-review などで自動的に評価し直さない。成果物全体を 30 思考法で見直したいときは、利用者が `run-elegant-review` (harness-creator) または `/skill-improve` を明示的に呼ぶ。

## Additional Resources

`references/resource-map.yaml` を最初に読む。主要参照:

- `workflow-manifest.json` — Step/Gate/Phase の機械可読定義
- `schemas/prompt-brief.schema.json` — Step 1→2 渡し正本スキーマ
- `schemas/handoff.schema.json` — 各 phase の handoff 共通形式
- `schemas/findings.schema.json` — design-evaluate (assign-prompt-design-evaluator) の出力形式 (C1-C4)
- `schemas/build-trace.schema.json` — Step 2 emit する Layer 別 coverage 形式
- `prompts/R1-elicit.md` / `prompts/R2-gate-review.md` / `prompts/R3-governance-decide.md` — R1/R2/R3 責務別プロンプト
- 子スキル: `run-prompt-elicit` (`--batch`), `run-prompt-creator-7layer`, `assign-prompt-design-evaluator`。governance は委譲先を持たず、Agent tool の `subagent_type=general-purpose` で起動した subagent が `prompts/R3-governance-decide.md` を読んで判定する。利用者が明示的に呼ぶ: `run-elegant-review` (harness-creator)
