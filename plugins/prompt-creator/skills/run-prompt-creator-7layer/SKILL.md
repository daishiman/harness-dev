---
name: run-prompt-creator-7layer
description: 7 層構造プロンプトを生成・更新するとき、owner_agent 向けに Prompt Templates/Self-Evaluation を充填するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--responsibility-id <R-id>] [--output <path>] [--target-agent <path>] [--skill-brief <path>] [--format yaml|md|json|xml] [--inject-sections <list>]"
arguments: [responsibility_id, output, target_agent, skill_brief, format, inject_sections]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3 *)
  - AskUserQuestion
kind: run
version: 2.1.0
effect: local-artifact
owner: team-platform
contract:
  intent: ユーザー要求またはヒアリング結果から、エンドユーザー向け成果物としての 7 層構造プロンプトを生成するため、Layer 単位生成 worker を提供する。
  interface:
    inputs: [responsibility_id, output, target_agent, skill_brief, format, inject_sections]
    outputs: [seven-layer-prompt.md, prompt-build-trace.json, prompt-creator-trace.json]
  invariant:
    - 7 層構造 (L1→L7) を厳守し、一括生成せず Layer 単位生成→merge とすること
    - Layer 5 は固定手順を持たず、ゴール定義+完了チェックリスト+実行方式 (l5-contract v2.0.0) で宣言すること
    - Layer 依存方向は L7→L1 の単方向のみとすること
    - 既存改善は冪等更新 (分解→類似は上書き統合・無ければ新規) で同一意図要素を重複させないこと
    - ゴールシーク反復は SubAgent / チームで分離 context で実行し、親へは最終差分のみ返し、各周回末に中間成果物アンカーを intermediate.jsonl へ追記すること
    - SKILL.md / SubAgent 各 300 行以下を保つこと
    - brief / hearing-result 供給時 (orchestrator / run-build-skill 呼出) は Phase 1-3 の全ユーザー対話を skip し、導出確認は brief.user_confirmed に委譲すること
    - C1-C4 設計評価を worker 完了条件に内蔵すること (呼出元が同等ゲートを機械証跡で保証する場合のみ免除)
    - 生成物の注入セクション名 (Prompt Templates / Self-Evaluation) は呼出元非依存の不変契約とすること
since: 2026-05-20
script_refs:
  - scripts/merge-layers.py
  - scripts/validate-prompt.py
  - scripts/convert-format.py
  - scripts/verify-completeness.py
  - scripts/generate-sheet.py
  - scripts/validate-sheet.py
  - scripts/scaffold-prompt.py
  - scripts/log-usage.py
reference_refs:
  - references/resource-map.yaml
  - references/seven-layer-format.md
  - references/quality-criteria.md
  - references/workflow-guide.md
  - references/writing-style-principles.md
  - references/prompt-sheet-template.md
  - references/idempotent-update-policy.md
# context-budget (CD-005): 章一括ロード禁止 / max-reference-chapters: 3
source: doc/prompt-creator/
source-tier: internal
last-audited: 2026-05-24
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
  - schemas/hearing-result.schema.json
responsibilities:
  - id: R1
    name: main
    prompt_required: true
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: Layer 5 がゴール定義+完了チェックリスト+実行方式 (l5-contract v2.0.0) で宣言され、「推論手順/思考プロセス/手順/Steps」見出し配下の連番手順列挙 (固定手順) を含まないこと、かつ 7 層 (または --layers で宣言した brief.layers_required サブセット。宣言外は N/A skip) が網羅されていることを verify-completeness.py が検出し FAIL なら停止できる。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 生成物の 7 層マーカー実在・Layer 本文の未展開 placeholder ({{...}}) 残存なし・TODO(human) 以外の TODO 残存なしを validate-prompt.py (--phase prompt) が機械検証し FAIL なら停止できる。要素原子性 (1 値 50 文字目安)・同一意図重複の排除・生成物スキーマ妥当性は機械検証対象外で、quality-criteria.md §8 と idempotent-update-policy.md に基づく Phase 4-B/4-C の LLM レビューで担保する。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 生成された 7 層プロンプトがエンドユーザー要求の本質目的を過不足なく満たし、L7→L1 単方向依存・冪等更新(分解→類似は上書き統合)・ゴールシーク反復のセッション分離(親へ最終差分のみ)という設計原則がスキルの目的に対し整合していること。
      verify_by: elegant-review
---

# run-prompt-creator-7layer

> doc/prompt-creator/ を harness-creator 仕様準拠で plugins/prompt-creator/ へ移植した正本。SKILL.md/SubAgent 各 300 行以下、Progressive Disclosure 厳守。

## Purpose & Output Contract

ユーザー要求またはヒアリング結果から、**成果物としての 7 層構造プロンプト** を生成する。
7 層: L1 基本定義 / L2 ドメイン定義 / L3 インフラストラクチャ / L4 共通ポリシー / L5 エージェント定義 / L6 オーケストレーション / L7 ユーザーインタラクション。
Layer 5 はゴールシーク型 (達成ゴール+完了チェックリスト+実行方式)。固定手順は書かず、手順はエージェントが実行時に自律生成する。

本スキルの責務は **エンドユーザー向け成果物プロンプトの生成** に純化する。SubAgent .md の Prompt Templates / Self-Evaluation への注入は、owner_agent 指定時のみ行う付随機能 (legacy) であり、本スキルの主目的ではない。

**入力**: `--responsibility-id <R-id>` (skill-local-v1 既定で必須、`brief.responsibilities[].id` と 1:1) / `--output <path>` (省略時は規約パス自動解決) / `--target-agent` (任意、owner_agent がある場合のみ注入) / `--skill-brief` / `--format` (md 既定、yaml は内部正規形または legacy 互換) / `--inject-sections` (既定: "Prompt Templates,Self-Evaluation")

**出力 (path_convention で切替)**:
- `skill-local-v1` (既定): `plugins/<plugin>/skills/<skill>/prompts/<R-id>-<slug>.md` — `references/prompt-placement-convention.md` (harness-creator 側) 準拠、`validate-build-trace.py` が正規表現と sha256 で機械検証
- `agents-legacy` (`--responsibility-id` 省略時のみ): `plugins/<plugin>/agents/prompts/<role>.yaml` — 後方互換、brief.responsibilities[] が空の ref/wrap/delegate 用
- 対象 SubAgent .md への自動注入 (Edit、owner_agent がある場合のみ)
- `eval-log/prompt-build-trace.json` (`run-prompt-create/schemas/build-trace.schema.json` 互換)
- `eval-log/prompt-creator-trace.json` (worker-local trace。必須フィールド: `path_convention`, `responsibility_id`, `layer_artifact_path`, `sha256`)

**完了条件**: `verify-completeness.py` PASS + `validate-prompt.py` PASS + `lint-agent-prompt-section.py` PASS + **C1-C4 設計評価 PASS** (worker 内蔵ゲート: `assign-prompt-design-evaluator` を fork し findings 出力のみ受領。呼出元が同等ゲートを機械証跡 (design-findings JSON) で保証する場合のみ免除)。run-build-skill Step 7.5 直呼びでも同一の設計保証が成立する (経路非依存)。

## Key Rules

1. **Script First**: 決定論的処理は python3 スクリプト。LLM は意味判断のみ。
2. **1 Layer = 1 出力**: 一括生成禁止、Layer 単位生成→merge。
3. **質ベース判定**: 「実行可能か/検証可能か」。数量カウント禁止。
4. **Progressive Disclosure**: `references/` は Phase 直前で必要分のみ読込。
5. **目的+背景併記**: 全ルール/制約に併記 (`writing-style-principles.md`)。
6. **300 行制約**: SKILL.md / SubAgent 各 300 行以下。
7. **ループ整合性**: run-build-skill 呼出時は `lint-agent-prompt-section.py` 通過必須。FAIL 時最大 3 回自律修正→未達なら orchestrator 差戻。
8. **責務境界**: 担当は Prompt Templates / Self-Evaluation の 2 セクションのみ。9 セクション骨格は run-build-skill 責務。
9. **Markdown 既定**: prompt 出力は **Markdown 形式 (`.md`) を既定**とする。論理構造の正本は `references/seven-layer-format.md`。内部正規形は YAML (scaffold/merge/verify の前提) とし、最終成果物は `convert-format.py` で Markdown へ変換する。`references/seven-layer-markdown-template.md` は提示形式の補助テンプレ。
10. **ゴールシーク**: Layer 5 に固定手順 (思考プロセスのステップ列挙) を書かない。達成ゴール+完了チェックリストを宣言し、手順は実行時にエージェントが自律生成する。`verify-completeness.py` が固定手順を検出したら FAIL。
11. **冪等更新 (重複回避・上書き優先)**: 既存プロンプトを改善するときは闇雲に追加せず、先に既存を原子要素へ分解・分析し、類似要素があれば上書き統合・無ければ新規追加する。同一意図の要素が 2 つ以上残ったら FAIL。正本 `references/idempotent-update-policy.md`。
12. **セッション分離**: ゴールシーク反復は SubAgent / エージェントチームで分離 context で実行する。中間探索情報を親 context に流さず、親へは最終差分と完了判定のみ返す (現セッション汚染防止)。

## End-to-End Flow

```
Phase 1 ヒアリング委譲 (run-prompt-elicit)   [delegate] hearing-result/brief 供給時 skip
   ↓
Phase 2 Prompt 作成シート生成+導出確認       [script→LLM] brief.user_confirmed で skip
   ↓
Phase 3 フォーマット選択 (yaml/md/json/xml)  [LLM] brief 供給時/ループ時 skip (md 既定)
   ↓
Phase 4-A Layer 単位生成 (L1→L7)             [script→LLM] generate-prompt
   ↓
Phase 4-B 4 パス品質レビュー                 [script→LLM] review-prompt
   ↓
Phase 4-C 自律改善 (最大 3 回+Anchor 記録)   [LLM]
   ↓
Phase 4-D フォーマット変換+注入             [script + Write/Edit]
   ↓
Phase 5 戻り検証+設計ゲート (C1-C4)          [script + evaluator fork]
```

詳細 (各 Phase のゴール+完了条件+判断基準): `references/workflow-guide.md`

## Steps (局面カタログ)

本節は各局面の**ゴール+完了条件+判断基準のみ**を宣言する。実行順・依存関係・fatal exit code の機械正本は `workflow-manifest.json` (phases[].dependsOn)。手順はゴールシークループ (5.4 実行方式相当) で都度立案し、固定ステップ列挙を持たない。

| Phase | ゴール (到達状態) | 完了条件 (機械判定) | 判断基準 / skip 条件 |
|---|---|---|---|
| 1 ヒアリング | 検証済み hearing-result が存在する | `validate-prompt.py --phase hearing` exit 0 | hearing-result / brief 供給時は skip。無ければ **run-prompt-elicit へ委譲** (interview-user agent を直接呼ばない: 収集正本の二重経路を作らないため) |
| 2 シート生成+導出確認 | goals/checklist を含む内部正規形材料が確定 | `generate-sheet.py` + `validate-sheet.py` exit 0 | brief.user_confirmed=true なら導出確認 skip。単独起動時のみユーザー承認を取る |
| 3 フォーマット選択 | 出力 format が一意確定 | format ∈ {md,yaml,json,xml} (md 既定) | brief 供給時 / ループ呼出時は md 既定で skip。単独起動時のみ AskUserQuestion。YAML は内部正規形または legacy 互換に限定 |
| 4-A Layer 単位生成 | 7 層 (または brief.layers_required サブセット) の Layer 別 artifact が揃う | 各 layer artifact 実在 + `merge-layers.py` exit 0 | 1 Layer = 1 出力 (一括生成禁止)。`prompt-creator-generate-prompt` fork。Layer 役割・依存方向の正本: `references/seven-layer-format.md` |
| 4-B 4 パスレビュー | Pass 0 (動的基準生成)〜Pass 4 の findings が確定 | 全 Pass PASS または修正指示付き findings | `prompt-creator-review-prompt` fork。基準: `references/quality-criteria.md` |
| 4-C 自律改善 | 完了チェックリスト全充足 or 上限到達 | `verify-completeness.py` (+`--layers` サブセット時) + `validate-prompt.py --phase prompt` exit 0 | 最大 3 回。冪等更新 (`idempotent-update-policy.md`)。各周回末に Anchor 追記 (下記契約) |
| 4-D 変換+注入 | 最終成果物出力 + (owner_agent 時) 注入完了 | `convert-format.py` exit 0、注入 diff が inject-sections 内 | 注入セクション名は不変契約 (下記) |
| 5 戻り検証+設計ゲート | 全機械ゲート+C1-C4 設計ゲート PASS | `lint-agent-prompt-section.py` exit 0 + C1-C4 findings PASS + `log-usage.py` 記録 | FAIL は Phase 4-A 再起動 (最大 3 周)。設計ゲート免除は呼出元の機械証跡がある場合のみ |

### Phase 4-C アンカー契約 (goal-seek-paradigm 準拠)

各周回末に `eval-log/prompt-creator-intermediate.jsonl` へ 1 行 append する: `original_goal` (全周回不変) / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal`。schema 正本は harness-creator `run-build-skill/schemas/goal-seek-loop.schema.json` の `intermediate_artifacts[]` (本 skill で再宣言しない)。次周回の手順立案は直前行の `merged_directive_for_next` + `original_goal` を必須入力とする。`drift_signal` が stagnant/widening/oscillating で 2 周連続なら orchestrator へ差し戻す。

### worker 内蔵ゲート (経路非依存の品質保証)

C1-C4 設計評価は worker の完了条件に内蔵する: `assign-prompt-design-evaluator` を fork (read-only・findings 出力のみ) して PASS を得る。呼出元 (例: run-prompt-create Step 3b) が同等ゲートを機械証跡 (design-findings JSON パス) で保証する場合のみ免除。これにより run-build-skill Step 7.5 直呼び・orchestrator 経由・手動起動のどの経路でも同一の設計保証が成立する。

### 呼出元非依存の不変契約

- 注入セクション名 `Prompt Templates` / `Self-Evaluation` はどの呼出元でも不変 (`lint-agent-prompt-section.py` の検証契約と 1:1)。
- brief 供給時は Phase 1-3 の全ユーザー対話を skip し、導出確認は brief の `user_confirmed` に委譲する (orchestrator の user_question_budget=1 違反を防ぐ)。

## Gotchas

1. 7 層一括生成禁止 (Layer 単位→merge)。
2. 「3 つ以上」型禁止→質ベース判定。
3. 長文フィールド禁止 (要素原子性、1 値 50 文字目安)。
4. 外部依存不持込 → YAML は python3 標準ライブラリのみで手書きシリアライズ。
5. doc/prompt-creator/ は deprecated、正本は plugins/。
6. 自律修正 3 回上限、超過時 orchestrator 差戻。
7. 9 セクション骨格生成禁止 (run-build-skill 責務)。
8. Layer 5 固定手順禁止 (「推論手順/思考プロセス/手順/Steps」見出し配下の連番列挙、l5-contract v2.0.0)。ゴール定義+完了チェックリスト+実行方式で宣言。
9. ヒアリングで固定手順を収集しない (goals/checklist を収集、steps は廃止)。
10. 既存改善時の重複追加禁止 (分析せず追加で肥大化させない)。類似は上書き統合。
11. ゴールシークを現セッション直書きで回さない (SubAgent/チームで分離、中間情報を親に漏らさない)。
12. Phase 1 で interview-user agent を直接呼ばない (ヒアリング経路は run-prompt-elicit へ一本化。二重経路は収集正本のドリフト源)。
13. Anchor 未記録のまま Phase 4-C を反復しない (intermediate.jsonl 追記は各周回末の必須ステップ)。

## Additional Resources

- `references/seven-layer-format.md` — 7 層 YAML 正本テンプレ (Phase 4-A 直前読込)
- `references/workflow-guide.md` — Phase 1-4 詳細
- `references/quality-criteria.md` — 4 パス評価基準 + §8 冪等更新基準
- `references/idempotent-update-policy.md` — 既存改善時の重複回避・上書き優先・セッション分離 (Phase 4-B/4-C 直前読込)
- `references/writing-style-principles.md` — 記述スタイル
- `references/prompt-sheet-template.md` — シート項目
- `schemas/hearing-result.schema.json` — legacy sheet/scaffold 入力スキーマ (raw hearing の正本は run-prompt-elicit 側)
- 子 agent: `plugins/prompt-creator/agents/prompt-creator-{generate-prompt,review-prompt}.md` (ヒアリングは run-prompt-elicit へ委譲)
- caller: `plugins/harness-creator/skills/run-build-skill` (Step 7.5)
- 戻り検証: `plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py`
- 設計ゲート: `plugins/prompt-creator/skills/assign-prompt-design-evaluator` (C1-C4、fork・findings 出力のみ)
- Anchor schema 正本: `plugins/harness-creator/skills/run-build-skill/schemas/goal-seek-loop.schema.json` (`intermediate_artifacts[]`)
