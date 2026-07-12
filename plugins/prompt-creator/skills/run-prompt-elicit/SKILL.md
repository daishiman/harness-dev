---
name: run-prompt-elicit
description: プロンプト要望を対話でヒアリングして prompt-brief.json を生成するとき、target_skill と responsibility_id の確定または skill 非紐付け (standalone) の汎用プロンプト要望を構造化するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--topic <text>] [--target-skill <skill_name>] [--responsibility-id <R-id>] [--batch]"
arguments: [topic, target_skill, responsibility_id, batch]
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - AskUserQuestion
  - Task
kind: run
version: 2.2.0
effect: local-artifact
owner: team-platform
contract:
  intent: プロンプト要望を対話で構造化し、後続 build/evaluate が依拠できる prompt-brief.json を確定するため、ヒアリング責務 (単独起動・委譲呼出共通の正本) を提供する。
  interface:
    inputs: [topic, target_skill, responsibility_id, batch]
    outputs: [prompt-brief.json, hearing-result.json]
  invariant:
    - 質問は 1 セッション 3-5 問 + 評価優先度に絞ること
    - AI の推定・解釈は導出確認 (ユーザー承認) を経るまで confirm 扱いしないこと
    - target_skill 指定時は responsibility_id が target_skill の responsibilities[].id と 1:1 で対応すること。standalone (target_skill なし) では出力先 (brief.output_path) をユーザー指定で確定すること
    - goals (達成ゴール=成果状態文) と checklist (完了チェックリスト=YES/NO 判定文) を hearing-result と brief に必ず搭載すること (固定手順は収集しない)
    - evaluation_priorities は schemas/hearing-result.schema.json の enum (SSOT) に従い最大 2 とし、enum 外回答は open_questions へ fail-visible に記録すること
    - batch モードでは AskUserQuestion を使用しないこと
since: 2026-05-22
script_refs: []
reference_refs:
  - references/resource-map.yaml
  - references/elicit-question-bank.md
source: doc/prompt-creator/agents/interview-user.md
source-tier: internal
last-audited: 2026-07-02
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-interview.md
schema_refs:
  - ../run-prompt-create/schemas/prompt-brief.schema.json
  - schemas/hearing-result.schema.json
responsibilities:
  - id: R1
    name: interview
    prompt_required: true
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成された prompt-brief.json が prompt-brief.schema.json に妥当で goals/checklist が非空で搭載され、target_skill 指定時は responsibility_id が target_skill の SKILL.md responsibilities[].id に実在する1:1対応として機械検証できる(不在時は open_questions に記録され confirm 化されない。standalone 時は output_path のユーザー指定確定で代替)。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: batch モード指定時は topic と target_skill と responsibility_id が全て与えられ AskUserQuestion を一切起動せず非対話で brief を確定する一方、欠落時は fail する(対話前提と非対話前提の取り違えが起きない)。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: AI の推定値を導出確認(ユーザー承認)なしに事実として埋めない・質問は1セッション3-5問+評価優先度に集約するというヒアリング中核原則が SKILL.md と prompts/R1-interview.md SSOT と interview-user agent アダプタまで一貫し、迷いなく後続 build が依拠できる brief を生むユーザー目的を最適反映している。
      verify_by: elegant-review
---

# run-prompt-elicit

> ユーザー要望から `prompt-brief.json` を構築するヒアリング skill。`prompt-creator-interview-user` agent を context:fork で起動する。**単独起動**と **run-prompt-create (Step 1) / run-prompt-creator-7layer (Phase 1) からの委譲呼出**の両対応で、ヒアリング経路の正本を本 skill に一本化する。

## Purpose & Output Contract

**入力**: topic (任意) / target_skill (任意。未指定 = standalone モード) / responsibility_id (任意) / batch flag
**出力**:
- `eval-log/prompt-brief.json` (`../run-prompt-create/schemas/prompt-brief.schema.json` 準拠)
- `eval-log/hearing-result.json` (`schemas/hearing-result.schema.json` 準拠、中間生データ。goals / checklist / evaluation_priorities を必須搭載)

**完了条件**: 下記「完了チェックリスト」全充足 (schema validation PASS + 呼出モード別整合)。

## Key Rules

1. **AskUserQuestion 集約**: 質問は 1 セッション 3-5 問 + 評価優先度に絞る (doc/prompt-creator/ 由来の核心原則)。
2. **導出確認**: AI の推定・解釈は必ずユーザーに透明化して承認を得る。推測を事実として埋めない。
3. **質ベース判定**: 「この回答で次に何をすべきか迷わないか?」で十分性を判断。数量カウント禁止。
4. **R-id 1:1 (skill 紐付け時)**: responsibility_id は target_skill の responsibilities[].id と必ず一致。不在なら open_questions に記録。
5. **standalone モード (skill 非紐付け)**: target_skill 未指定の汎用プロンプト要望を公認。R-id 突合は skip し、出力先 (brief.output_path) をユーザー指定で確定する。brief の埋め方 (機械正本 = brief schema の if/then/else):
   - `target_skill` / `responsibility_id`: **キーごと省く** (R-id は skill 紐付け専用。混入は schema FAIL)
   - `output_path`: **必須**。生成物出力先をユーザー指定 (導出確認済み) の値で格納する (規約パス自動解決に依存しない)
   - `owner_agent_or_skill`: 実行主体の識別子。該当 agent / skill が無ければ `standalone` と記載する
   - 共通必須 (prompt_name / layers_required / trigger_conditions / goals / checklist / output_contract / boundary / output_language): 両モード同一に埋める (IN1 criteria の standalone 代替条項 = output_path 確定と 1:1)
6. **goals / checklist 必須収集**: 達成ゴール (成果状態文) と完了チェックリスト (YES/NO 判定文) を hearing-result → brief へ必ず載せる (Layer 5 宣言型材料。固定手順は収集しない)。
7. **評価優先度 SSOT**: `schemas/hearing-result.schema.json` の enum 5 値・最大 2 が正本。enum 外回答は open_questions へ fail-visible。
8. **batch モード**: `--batch` 指定時は AskUserQuestion 不使用。topic / target_skill / responsibility_id 全指定必須。
9. **言語**: 出力本文は日本語、パラメーター名と JSON キーは英語のまま。

## ゴールシーク実行

> 本 Skill は固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。下記「局面カタログ」は順序固定の手順ではなく、未達項目に応じてループが選ぶ局面メニュー。正本: harness-creator `run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

後続 build/evaluate が迷いなく依拠できる `eval-log/prompt-brief.json` と `eval-log/hearing-result.json` が、最小質問数 (3-5 問 + 評価優先度) と導出確認済みの状態で確定している。

### 目的・背景 (Why)

網羅ヒアリングはユーザー負担を増やし、AI の無断推定は brief の信頼を毀損する。ゴールと停止条件を固定し、質問設計・補完・突合の手順は要望と文脈から都度導出することで、単独起動・委譲呼出のどちらでも同一品質の brief を確定できる。

### 完了チェックリスト (ゴール到達の停止条件)

- [ ] hearing-result.json が `schemas/hearing-result.schema.json` validation を通過している (goals / checklist / evaluation_priorities 必須搭載)
- [ ] prompt-brief.json が `../run-prompt-create/schemas/prompt-brief.schema.json` validation を通過している
- [ ] goals が成果状態文・checklist が第三者 YES/NO 判定文で非空である
- [ ] evaluation_priorities が schema enum 内の値のみ・最大 2 で、enum 外回答は open_questions に記録されている
- [ ] skill 紐付け時は responsibility_id が target_skill の responsibilities[].id に実在し、standalone 時は brief.output_path がユーザー指定で確定している
- [ ] AI 推定値 (`ai_derived: true`) が全て導出確認済み (`user_confirmed: true`) で、未確認推定の confirm 化が 0 件である
- [ ] 既知項目 (既存 brief) への再質問が 0 件で、発行質問が 3-5 問 + 評価優先度 1 セットに収まっている
- [ ] batch モード時は AskUserQuestion 0 回で、必須引数欠落時は fail している

### ゴールシークループ

正本 goal-seek-paradigm.md の 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し) に従う。反復上限は `feedback_contract.max_iterations` (3)。超過時は残項目を open_questions に記録し呼出元 (ユーザー / orchestrator) へ差し戻す。

## 局面カタログ (順序は都度判断)

- **既存 brief 差分確認**: `eval-log/prompt-brief.json` が存在すれば既知項目を抽出し、差分のみをヒアリング対象化する。
- **target_skill 突合**: `plugins/*/skills/<target_skill>/SKILL.md` から `responsibilities[]` を抽出し boundary / layers_required を推定 (導出確認必須)。standalone では skip。
- **対話ヒアリング**: `Task(subagent_type=prompt-creator-interview-user)` で fork 起動。質問設計は `references/elicit-question-bank.md` (schema enum 従属) に従う。
- **brief 構築**: hearing-result を brief へ正規化する (goals / checklist / evaluation_priorities を脱落させない)。standalone は Key Rule 5 の brief 契約に従い output_path をユーザー指定値で埋め、target_skill / responsibility_id をキーごと省く。
- **検証**: 完了チェックリストを schema validation と responsibilities[] 突合で再評価し、未達項目の局面へ戻る。

## Gotchas

1. 既存 brief がある場合は差分のみ。既知項目を再質問しない。
2. responsibility_id 不在で target_skill 側の更新が必要なら open_questions に保持。
3. AI 推定値は導出確認 (ユーザー承認) を経ずに confirm 扱いしない。補完は AI 最尤仮説 + 仮定記録で行い、人間差し戻しマーカーは生成しない。
4. doc/prompt-creator/ の writing-style-principles に従い「目的+背景」併記。
5. 委譲呼出 (run-prompt-create / 7layer) 時は呼出元の対話予算に従い、brief 供給済み項目の再ヒアリングをしない。

## Additional Resources

- `references/elicit-question-bank.md` — 質問テンプレ集 (evaluation_priorities は schema enum 従属)
- `schemas/hearing-result.schema.json` — 中間スキーマ = evaluation_priorities enum / goals / checklist の SSOT
- `../run-prompt-create/schemas/prompt-brief.schema.json` — brief 出力スキーマ
- caller: `run-prompt-create` (Step 1) / `run-prompt-creator-7layer` (Phase 1 委譲)
- delegate agent: `prompt-creator-interview-user`
