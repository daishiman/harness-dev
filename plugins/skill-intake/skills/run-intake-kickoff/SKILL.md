---
name: run-intake-kickoff
description: intake セッション起動直後にパターン・深度・痛点 3 軸を確定したいとき、run-skill-intake から phase 1 として呼ばれて kickoff.json を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.1.0
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成された output/<hint>/kickoff.json が schemas/output.schema.json 準拠かつ scripts/validate-kickoff-json.py exit 0 で、pattern/depth/skill_name_hint/pain_ranking の4項目と qa_log[] を充足する
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: skill_name_hint が pain 動詞+目的語から kebab-case で決定論的生成され、社名・個人名等の固有名詞を含まず、同一 qa_log なら sha256 一致する
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 本スキルが「セッション起動・3軸(pattern/depth/pain)確定・kickoff.json emit」に責務を絞り、5軸シート充足・深掘り(Phase5)・可視化・mode判定へ逸脱せず、AskUserQuestion を完全直列で発行する設計になっている
      verify_by: elegant-review
---

# run-intake-kickoff

## Purpose & Output Contract

intake セッションの最初の phase。ユーザー初期発話から **3 軸 (pattern A-E / depth / pain ranking)** を AskUserQuestion で 1 問ずつ確定し、後続 phase の共通基盤となる `kickoff.json` を生成する。本スキルは「セッション起動・3 軸確定・kickoff.json emit」に責務を絞り、5 軸シート充足 (`run-intake-interview`)、深掘り (Phase 5)、可視化 (`run-intake-visualize`)、mode 判定 (`run-intake-next-action`) は行わない。

**入力**: 初期発話 (自由記述、orchestrator から渡される)
**出力**: `output/<hint>/kickoff.json` (`schemas/output.schema.json` 準拠)
**完了条件**: `pattern` / `depth` / `skill_name_hint` / `pain_ranking` 4 項目が揃い、`scripts/validate-kickoff-json.py` exit 0。

### 出力 JSON 形式

```json
{
  "pattern": "A|B|C|D|E",
  "depth": "quick|standard|detailed",
  "skill_name_hint": "<kebab-case>",
  "pain_ranking": [{"task": "...", "frequency_per_week": 3, "minutes_per_run": 30}],
  "initial_utterance": "...",
  "timestamp": "ISO8601",
  "qa_log": [{"question": "...", "answer": "..."}]
}
```

## Key Rules

1. **3 軸のみ確定**: pattern / depth / pain ranking。仮説検証 (assumption-challenger)、6 軸プロファイル (user-profiler)、5 軸シート (`run-intake-interview`) には踏み込まない。
2. **AskUserQuestion は 1 問ずつ**: Q1 (pattern) → Q2 (depth) → Q3-N (pain) を順次。並列・束ね質問禁止。
3. **語彙は beginner 既定**: 初対面のため平易語を使用 (`vocabulary_tier` 確定は後続 phase の責務)。
4. **口語→技術用語の整形は許可**: 「定型作業」→「ルーチンタスク」など軽整形は可。本旨改変・要約は禁止 (生回答を `qa_log[]` に保存)。
5. **skill_name_hint に固有名詞を直書きしない**: 社名・個人名は variable_abstraction (Layer 1.2)。
6. **pattern E (不明) 許容**: 確定不能時は E で進め、Phase 8 Gate A 時点で再判定する。

## ゴールシーク実行

### ゴール (Goal)

初期発話を起点に `output/<hint>/kickoff.json` が `schemas/output.schema.json` 準拠で生成され、`scripts/validate-kickoff-json.py` exit 0、4 項目 (`pattern` / `depth` / `skill_name_hint` / `pain_ranking`) すべて充足、`qa_log[]` に Q&A 時系列を保存した状態。

### 目的・背景 (Why)

3 軸が曖昧なまま後続 phase に進むと、interview の質問数が爆発し、profile / 5 軸シート / 可視化が手戻りする。固定手順では初期発話の粒度・ユーザーの語彙差・痛点列挙数に脆く、未充足軸を都度埋めるゴールシークが必要。本スキルは制御フェーズの第一歩として「最小 3 軸の合意」を機械検証可能な形で固定する。

### 完了チェックリスト (Checklist)

- [ ] 初期発話を改変・要約せず受領し、整形後文も本旨保持
- [ ] Q1 で `pattern` ∈ {A, B, C, D, E} を 1 つ選択 (E 許容、`references/pattern-catalog.md` 提示後)
- [ ] Q2 で `depth` ∈ {quick, standard, detailed} を確定 (`references/depth-criteria.md` 提示後)
- [ ] Q3-N で `pain_ranking[]` を 1〜3 件、各要素に `task` / `frequency_per_week` / `minutes_per_run` を充足 (`references/pain-ranking-template.md` 準拠)
- [ ] `skill_name_hint` を pain 動詞 + 目的語から kebab-case で決定論的に生成 (固有名詞混入なし、同 qa_log なら sha256 一致)
- [ ] AskUserQuestion を並列発行していない (完全直列)
- [ ] `output/<hint>/kickoff.json` が `schemas/output.schema.json` 準拠
- [ ] `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/run-intake-kickoff/scripts/validate-kickoff-json.py output/<hint>/kickoff.json` exit 0
- [ ] `qa_log[]` に質問・回答ペアが時系列で保存され、ユーザー回答は生のまま
- [ ] 本スキルの責務外 (5 軸シート充足・深掘り・mode 判定) に踏み込んでいない

### ゴールシークループ

固定手順ではなく、上記チェックリストを唯一の停止条件とする。未充足軸を特定 → 次に出すべき AskUserQuestion (3 択 + 自由入力) を立案 → 回答取得 → `qa_log[]` 追記 → checklist 自己評価、を反復する (上限は `prompts/R1-main.md` Layer 4 反復回数)。`workflow-manifest.json` の phase 順 P1-pattern → P2-depth → P3-pain → P4-emit に従い、各 phase の `fatal_exit_codes` 検出時は即停止して未充足項目を stderr に列挙する。

## Gotchas

1. **責務逸脱禁止**: 「真の課題は?」などの深掘りは Phase 5 (assumption-challenger)、5 軸シートは `run-intake-interview` の責務。本 phase で踏み込むと同意ループを誘発する。
2. **AskUserQuestion 3 連発禁止**: 必ず 1 問ずつ。並列質問は認知負荷が高く回答品質が落ちる。
3. **pattern E は逃げではない**: 確定不能時の正当な選択肢として扱い、Phase 8 Gate A で再判定する設計に従う。
4. **skill_name_hint 固有名詞**: 社名・個人名を直書きすると後続成果物全体に漏洩する。variable_abstraction で抽象化。
5. **validate-kickoff-json.py 自動修正禁止**: FAIL 時は不足項目をユーザー提示し、LLM 判断で勝手に埋めない。

## Additional Resources

- `workflow-manifest.json` — P1-P4 phase 定義・dependsOn・entryHook/exitHook・fatal_exit_codes
- `prompts/R1-main.md` — R1-pattern-depth-pain-confirm 7 層プロンプト (Layer 1-7)
- `schemas/output.schema.json` — kickoff.json 正本スキーマ
- `references/pattern-catalog.md` — pattern A-E の選択肢と判定基準
- `references/depth-criteria.md` — quick / standard / detailed の判断基準
- `references/pain-ranking-template.md` — 痛点構造化フォーマット
- `references/resource-map.yaml` — machine-readable リソース一覧
- `scripts/validate-kickoff-json.py` — 出力 JSON の schema validate
- 後続 phase: `run-intake-interview` (5 軸シート), `run-intake-visualize`, `run-intake-next-action`, `run-intake-finalize`
