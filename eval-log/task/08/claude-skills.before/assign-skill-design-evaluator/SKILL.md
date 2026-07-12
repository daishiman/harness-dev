---
name: assign-skill-design-evaluator
description: 生成済みSKILL.mdを評価したいとき、rubric準拠を確認したいときに使う。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Grep, Bash(python3 *)]
pair: run-build-skill
kind: assign
effect: conversation-output
role_suffix: evaluator
owner: team-platform
since: 2026-05-17
rubric_refs:
  - ref-skill-design-rubric              # L0: 共通 (固定)
  # L1: ドメイン rubric は CLI --rubric-refs で append される (rubric-registry.json 経由)
  - references/rubric.json               # L2: 本 evaluator 固有 override
reference_refs:
  - references/evaluator-contract.md
script_refs:
  - scripts/render-findings-score.py
  - ../../scripts/compose-rubrics.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# assign-skill-design-evaluator

> ※ creator-kit Phase 0 移行中は `creator-kit/skills/` が正本、`.claude/skills/` への配置は派生。本SKILL.mdは両配置で動作するよう self-relative パスを使用。

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
2. **rubric_refs 注入 (append-only)**: runner/orchestrator が L1 ドメイン rubric を CLI `--rubric-refs` で **append** する（順序: L0 → L1 → L2）。evaluator 自身は frontmatter `rubric_refs` を書き換えない（設計書29 §10 アンチパターン）。合成は `creator-kit/scripts/compose-rubrics.py` に委譲し、`deep-merge / strict / override / layered`、conflict policy、schema検証、循環検出、composition hash を同一実装で扱う。未指定時は L0 + L2 のみで合成する（L1 スキップ）。
3. **TODO(human)残置**: BD-004 は人間判断待ち。検出時は finding severity=low で `pending_human` を立てる。
4. **severity weights固定**: high -20 / medium -10 / low -3、初期 100。負値は 0 にクランプ。
5. **rubric_hash必須**: 出力JSONに rubric.json の sha256 を載せる（再現性、27章）。

## Steps

### Step 1: rubric ロード

```bash
# self-relative: SKILL.md と同階層の scripts/ / references/ を解決。
# CLAUDE_SKILL_DIR が未設定なら creator-kit / .claude 両配置を fallback で探索。
SKILL_DIR="${CLAUDE_SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  if [ -f "creator-kit/skills/assign-skill-design-evaluator/scripts/render-findings-score.py" ]; then
    SKILL_DIR="creator-kit/skills/assign-skill-design-evaluator"
  elif [ -f ".claude/skills/assign-skill-design-evaluator/scripts/render-findings-score.py" ]; then
    SKILL_DIR=".claude/skills/assign-skill-design-evaluator"
  else
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
  fi
fi
UPSTREAM="${SKILL_DESIGN_RUBRIC:-creator-kit/skills/ref-skill-design-rubric/rubric.json}"
# L1: DOMAIN_RUBRIC_REFS は run-build-skill が brief.domain から rubric-registry.json 経由で解決し、空白区切りで渡す。
# 未設定なら L0 + L2 のみで合成される (L1 スキップ)。
L1_REFS="${DOMAIN_RUBRIC_REFS:-}"
python3 "$SKILL_DIR/scripts/render-findings-score.py" \
  --rubric-refs "$UPSTREAM" $L1_REFS "$SKILL_DIR/references/rubric.json" \
  --target "$TARGET" --emit-hash
```

合成順序は **L0 → L1 → L2** (リスト末尾が最 specific)。`merge_strategy: deep-merge` + `conflict_policy: most-specific-wins` により末尾が優先される。別ドメインを追加する場合も evaluator 本体は変えず、`creator-kit/config/rubric-registry.json` に L1 を登録するだけで済む（設計書29 §7.1）。

### Step 2: 静的検査の実行

各ルールについて Read / Grep / lint-* スクリプト で findings を集める:

- FM-001..005: frontmatter検査（`validate-frontmatter.py`）
- BD-001..004: 本文検査（Output contract / Gotchas / 行数 / BD-004=TODO(human)）
- NM-001..003: 命名/構造（`lint-skill-name.py`, `lint-skill-tree.py`）
- PD-001: Progressive Disclosure（本文100行超なら references/ 必須）
- RG-001: rubric_hash の埋め込み

### Step 3: スコア計算

`render-findings-score.py` に findings リストを渡し、severity weight で減点。

### Step 4: JSON出力

`references/evaluator-contract.md` のスキーマ通りに STDOUT 1行で出す。
threshold 未達なら `passed=false`。run-build-skill が `findings[*].message` を元に再生成する。

### Step 5: eval-log への永続化（必須・F1 規約）

評価完了後、STDOUTのJSONを `creator-kit/scripts/write-eval-log.py` 経由で
`eval-log/skill-build-trace.jsonl` へ append する。自己進化ループ（設計書23章）の
**入力ストック** を確保するための唯一の書き込み経路。

```bash
# STDOUT を直接パイプ
python3 "$SKILL_DIR/scripts/render-findings-score.py" ... \
  | tee /dev/tty \
  | python3 creator-kit/scripts/write-eval-log.py
```

`write-eval-log.py` は schema 検証・`recorded_at`/`schema_version` 自動付与を行う。
書き込み失敗（exit != 0）の場合は本Skill全体を非ゼロ exit で終え、上位 runbook に
報告する。**直接 `echo >> jsonl` 追記は禁止**（スキーマ事故防止）。

## Gotchas

- **rubric.json内のTODO(human)はscoreに反映しない**: `pending_human` 配列に別建て。
- **forkでも /tmp は永続しない**: 中間ファイルは `--target` 内に置かない。STDOUT返却のみ。
- **stdlibのみ**: PyYAML不可。`scripts/render-findings-score.py` は標準ライブラリ `json` で `rubric.json` を読む。
- **rubric_refs の most-specific-wins**: 本Skill側で override したルールが優先（29章）。

## Additional Resources

- `references/rubric.json` — 機械可読rubric（BD-004 に TODO(human)あり）
- `references/evaluator-contract.md` — 出力JSONスキーマ・禁則
- `scripts/render-findings-score.py` — findings→score計算
- upstream: `ref-skill-design-rubric/rubric.json`
