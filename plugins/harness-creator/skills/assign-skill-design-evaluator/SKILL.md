---
name: assign-skill-design-evaluator
description: 生成済みSKILL.mdを評価したいとき、rubric準拠を確認したいときに使う。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Grep, Bash(python3 *)]
pair: run-build-skill
kind: assign
prefix: assign
effect: conversation-output
role_suffix: evaluator
owner: team-platform
since: 2026-05-17
version: 0.1.0
rubric_refs:
  - ref-skill-design-rubric              # L0: 共通 (固定)
  # L1: ドメイン rubric は CLI --rubric-refs で append される (rubric-registry.json 経由)
  - references/rubric.json               # L2: 本 evaluator 固有 override
reference_refs:
  - references/evaluator-contract.md
script_refs:
  - scripts/render-findings-score.py
  - ../../../skill-governance-automation/scripts/compose-rubrics.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-evaluate.md
schema_refs:
  - schemas/evaluator-output.schema.json
---

# assign-skill-design-evaluator

> ※ creator-kit Phase 0 移行中は `plugins/harness-creator/skills/` が正本、`.claude/skills/` への配置は派生。本SKILL.mdは両配置で動作するよう self-relative パスを使用。

## Purpose & Output Contract

生成済みSkillをrubricで採点し、構造化JSONを返す評価専用Skill。
forkコンテキストで動き、生成本体（run-build-skill）と context を共有しない。

**入力**: `target` = SKILL.md のパス もしくは スキルディレクトリ
**出力（STDOUT、JSON 1オブジェクト）**:
```json
{
  "rubric_id": "skill-design",
  "rubric_version": "1.0.0",
  "rubric_hash": "<sha256:rubric.json>",
  "composition_hash": "<sha256:merged-rubrics>",
  "rubric_refs": ["<L0 rubric>", "<local override>"],
  "target": "<path>",
  "score": 87,
  "threshold": 80,
  "passed": true,
  "machine_checks": [],
  "findings": [
    {"id":"FM-003","severity":"medium","message":"trigger count=4 > 3","loc":"frontmatter.description"}
  ],
  "required_fixes": [],
  "pending_human": []
}
```

**禁則**: 生成・修正を行わない。Write/Edit toolは持たない。`pair: run-build-skill` が修正担当。

## Key Rules

1. **Goodhart対策**: 採点者は被採点物を改変しない（09章）。
2. **rubric_refs 注入 (append-only)**: runner/orchestrator が L1 ドメイン rubric を CLI `--rubric-refs` で **append** する（順序: L0 → L1 → L2）。evaluator 自身は frontmatter `rubric_refs` を書き換えない（設計書29 §10 アンチパターン）。合成は `plugins/skill-governance-automation/scripts/compose-rubrics.py` に委譲し、`deep-merge / strict / override / layered`、conflict policy、schema検証、循環検出、composition hash を同一実装で扱う。未指定時は L0 + L2 のみで合成する（L1 スキップ）。
3. **TODO(human)残置**: 合成 rubric の check に TODO(human) マーカーが残る rule は採点せず `pending_human` に別建てする（score に反映しない）。
4. **severity weights固定**: high -20 / medium -10 / low -3、初期 100。負値は 0 にクランプ。
5. **rubric_hash必須**: 出力JSONに rubric.json の sha256 を載せる（再現性、27章）。

## ゴールシーク実行

evaluator は一度の採点で完結する read-only 工程。**ループは回さず**、採点の網羅性を完了チェックリストで担保する（正本 `run-build-skill/references/goal-seek-paradigm.md` 「評価系 (assign-*-evaluator) の扱い」）。

### ゴール (Goal)

全 rubric 項目を採点し、各 findings にエビデンス（loc）と severity を付与し、最終 score を算出した JSON 1 オブジェクトが STDOUT に出力され、eval-log へ append 済みになっている。

### 目的・背景 (Why)

生成本体（`run-build-skill`）と context を共有しない fork で被採点物を改変せず採点することで、Goodhart/Sycophancy を避け再現可能な品質ゲートを成立させる。

### 完了チェックリスト (Checklist)

- [ ] 全 rubric 項目（FM/BD/NM/PD/RG 系）を評価し終えている
- [ ] 各 finding に loc エビデンスと severity (high/medium/low) が付いている
- [ ] severity weight (high -20 / medium -10 / low -3、初期 100、負値は 0 クランプ) で score を算出済み
- [ ] 出力 JSON が `schemas/evaluator-output.schema.json` / `references/evaluator-contract.md` に準拠し rubric_hash を含む
- [ ] STDOUT の JSON を `write-eval-log.py` 経由で `eval-log/<plugin>/<date>-score.jsonl` へ append 済み

### 採点フロー（局面カタログ・順序は都度判断）

- **rubric ロード**: self-relative で scripts/references を解決し、`render-findings-score.py` を L0→L1→L2 の順で合成して呼ぶ。

  ```bash
  SKILL_DIR="${CLAUDE_SKILL_DIR:-}"
  if [ -z "$SKILL_DIR" ]; then
    if [ -f "plugins/harness-creator/skills/assign-skill-design-evaluator/scripts/render-findings-score.py" ]; then
      SKILL_DIR="plugins/harness-creator/skills/assign-skill-design-evaluator"
    elif [ -f ".claude/skills/assign-skill-design-evaluator/scripts/render-findings-score.py" ]; then
      SKILL_DIR=".claude/skills/assign-skill-design-evaluator"
    else
      SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
    fi
  fi
  UPSTREAM="${SKILL_DESIGN_RUBRIC:-plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json}"
  # L1: DOMAIN_RUBRIC_REFS は run-build-skill が brief.domain から rubric-registry.json 経由で空白区切りで渡す。未設定なら L0 + L2 のみ。
  L1_REFS="${DOMAIN_RUBRIC_REFS:-}"
  python3 "$SKILL_DIR/scripts/render-findings-score.py" \
    --rubric-refs "$UPSTREAM" $L1_REFS "$SKILL_DIR/references/rubric.json" \
    --target "$TARGET" --emit-hash
  ```

  合成順序は **L0 → L1 → L2** (末尾が最 specific)。`deep-merge` + `most-specific-wins` で末尾優先。別ドメイン追加時も本体は変えず `rubric-registry.json` に L1 登録するだけ（設計書29 §7.1）。
- **静的検査**: Read / Grep / lint-* で findings 収集 — FM-001..005 (`validate-frontmatter.py`)、BD-001..004 (Output contract / Gotchas / 行数 / BD-004=TODO(human))、NM-001..003 (`lint-skill-name.py`, `lint-skill-tree.py`)、PD-001 (本文100行超なら references/ 必須)、RG-001 (rubric_hash 埋め込み)。
- **スコア計算**: `render-findings-score.py` に findings を渡し severity weight で減点。
- **JSON 出力**: `references/evaluator-contract.md` のスキーマ通り STDOUT 1 行で出す。threshold 未達は `passed=false`。run-build-skill が `findings[*].message` を元に再生成する。
- **eval-log 永続化 (必須・F1 規約)**: STDOUT の JSON を `write-eval-log.py` 経由で `eval-log/<plugin>/<date>-score.jsonl` (= `write-eval-log.py` の `resolve_log_path`) へ append。自己進化ループ（設計書23章）の入力ストックを確保する唯一の書き込み経路。集計 `aggregate-evals.py` (SessionEnd) はこの score.jsonl を読み取り source とする。

  ```bash
  python3 "$SKILL_DIR/scripts/render-findings-score.py" ... \
    | tee /dev/tty \
    | python3 plugins/skill-governance-automation/scripts/write-eval-log.py
  ```

  `write-eval-log.py` は schema 検証・`recorded_at`/`schema_version` 自動付与を行う。書き込み失敗 (exit != 0) なら本 Skill 全体を非ゼロ exit で終え上位 runbook に報告する。**直接 `echo >> jsonl` 追記は禁止**（スキーマ事故防止）。

## Gotchas

- **rubric.json内のTODO(human)はscoreに反映しない**: `pending_human` 配列に別建て。
- **forkでも /tmp は永続しない**: 中間ファイルは `--target` 内に置かない。STDOUT返却のみ。
- **stdlibのみ**: PyYAML不可。`scripts/render-findings-score.py` は標準ライブラリ `json` で `rubric.json` を読む。
- **rubric_refs の most-specific-wins**: 本Skill側で override したルールが優先（29章）。

## Additional Resources

- `references/rubric.json` — L2 delta-only override（evaluator 固有 rule のみ。正本 rule 集合は upstream L0）
- `references/evaluator-contract.md` — 出力JSONスキーマ・禁則
- `scripts/render-findings-score.py` — findings→score計算
- upstream: `plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json`
