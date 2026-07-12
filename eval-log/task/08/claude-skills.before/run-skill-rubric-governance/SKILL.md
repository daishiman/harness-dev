---
name: run-skill-rubric-governance
description: rubric変更を提案するとき、rubric改正を施行するときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Bash(git *)]
kind: run
owner: team-platform
since: 2026-05-17
effect: local-artifact
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# run-skill-rubric-governance

## Purpose & Output Contract

`ref-skill-design-rubric/rubric.json` の改正 Runbook（27章）。
提案 → 影響評価 → 猶予期間 → 発効 の4フェーズを1本のワークフローで管理。

**入力**: `templates/proposal.json` を埋めた改正提案ファイル
**出力**: rubric.json のPR、 governance log（`$SKILL_DIR/log/*.jsonl`）

## Key Rules

1. **直接編集禁止**: rubric.json は本Runbook経由でのみ更新。
2. **semver**: minor=緩和（しきい値↓、ルール削除）、major=厳格化（ルール追加、weight↑）、patch=文言のみ。
3. **猶予期間**: major は最低14日、minor は7日、patch は即時可。
4. **影響評価必須**: `scripts/diff-rubric-impact.py` で過去 eval-log の合否変動率を測る。
5. **承認ボード**: 提案者 / 第三者レビュア / 承認者 / tooling役 の4ロール（`references/governance-board.md`）。

## Steps

### Step 0: 出力先解決

```bash
# SKILL_DIR を確立する (governance log / scripts/ の親ディレクトリ)
source creator-kit/scripts/resolve-skill-dirs.sh
# SKILL_DIR が run-build-skill を指すため、本スキル用に上書き:
SKILL_DIR="${CLAUDE_SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  if [ -f "creator-kit/skills/run-skill-rubric-governance/scripts/lint-rubric-violation.py" ]; then
    SKILL_DIR="creator-kit/skills/run-skill-rubric-governance"
  elif [ -f ".claude/skills/run-skill-rubric-governance/scripts/lint-rubric-violation.py" ]; then
    SKILL_DIR=".claude/skills/run-skill-rubric-governance"
  fi
fi
```

### Step 1: 提案

`templates/proposal.json` をコピーして埋める:
- rule_id, change_type (add/modify/remove), bump (major/minor/patch), rationale, sunset_days

### Step 2: 影響評価

2つの違反集計スクリプトを使い分ける。

```bash
# 2a. 時系列違反率（連続 N release × 閾値超）を検出 → governance トリガー判定 (27章§3.2)
python3 creator-kit/scripts/lint-rubric-violation.py \
  --log-dir eval-log \
  --n 3 --threshold 0.20 \
  --out eval-log/trigger.json

# 2b. ルール別違反集計（単一 release / proposal 単位）
python3 "$SKILL_DIR/scripts/lint-rubric-violation.py" \
  --logs "$SKILL_DIR/log" \
  --rule "$RULE_ID"

# 2c. 差分影響評価
python3 "$SKILL_DIR/scripts/diff-rubric-impact.py" \
  --proposal proposal.json --logs "$SKILL_DIR/log"
```

**bootstrap フェーズ**: eval-log の合計件数が `governance-params.json.bootstrap_mode.min_eval_log_records`（既定 20）未満の場合、2a は exit 3 を返し governance ループは pending 扱い。**最初の 20 件を蓄積するため、まず通常の Skill 生成・採点を回すこと**。bootstrap 中は `solo_operator_mode: true` への一時切替を governance log に記録すれば minor/patch の自己承認を許容する（major bump は禁止）。

合否変動率が 30% 超なら major 強制昇格。

### Step 3: 猶予期間アナウンス

- governance log にエントリ追加（jsonl 1行）
- `aliases` 的に旧ルールを残し warning にダウングレード（severity→low）

### Step 4: 発効

- `ref-skill-design-rubric/rubric.json` を編集
- `rubric_version` を bump（semver）
- `assign-skill-design-evaluator/references/rubric.json` を同期（deep-merge upstream更新）
- **rubric_hash 再計算**: `python3 creator-kit/scripts/compute-rubric-hash.py --rubric creator-kit/skills/ref-skill-design-rubric/rubric.json` を実行し `rubric.normalized.json` と `rubric_hash` を更新（27章§8.2）
- **版ずれ検証**: `python3 creator-kit/scripts/check-rubric-sync.py` を実行し
  exit 0（OK）であることを必ず確認。`RUBRIC_DRIFT:` で落ちた場合は commit 前に
  派生 rubric を再同期すること。
- `git commit` し governance log を closed に

### Step 5: 不安定時の自動 rollback

`lint-rubric-violation.py` の `trigger.json` で 1 release 後に違反率が悪化した場合、
PostToolUse Hook 経由で `rollback-to-stable.py` を起動して安定版凍結条件
（`freeze.consecutive_runs` × `violation_rate_ceiling`）を満たす過去版へ巻き戻す（27章§9）。

```bash
python3 creator-kit/scripts/rollback-to-stable.py \
  --rubric creator-kit/skills/ref-skill-design-rubric/rubric.json \
  --versions-md eval-log/rubric-versions.md \
  --params references/governance-params.json \
  --dry-run
```

## Gotchas

- **patchで内容変更は禁則**: 文言のみ。閾値や severity 変更は最低 minor。
- **assign 側 override をrebaseし忘れる事故**: deep-merge の most-specific-wins が壊れる（29章）。
- **eval-log がない**: 影響評価できないので `diff-rubric-impact.py` は exit 2 でフェイルセーフ。
- **緊急パッチ**: high severity の誤検出固定は patch 例外（log に `emergency: true`）。

## Additional Resources

- `templates/proposal.json` — 改正提案テンプレ
- `creator-kit/scripts/lint-rubric-violation.py` — **時系列違反率検出（連続 N×閾値超 → trigger.json）正本（27章§3.2）**
- `$SKILL_DIR/scripts/lint-rubric-violation.py` — ルール別違反集計（単一 release/proposal 単位）
- `$SKILL_DIR/scripts/diff-rubric-impact.py` — 差分影響評価
- `creator-kit/scripts/compute-rubric-hash.py` — rubric_hash 再計算（27章§8.2）
- `creator-kit/scripts/notify-if-governance-trigger.py` — Stop Hook 用招集通知（27章§3.4）
- `creator-kit/scripts/rollback-to-stable.py` — 安定版凍結条件を満たす版への自動 rollback（27章§9）
- `creator-kit/scripts/doc-to-skill-adapter.py` — 設計書を Skill artifact 化して自己採点する起動装置（26章）
- `references/governance-board.md` — ボード構成
- `references/version-rules.md` — semver規約
- 27章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md`
- 26章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/26-meta-skill-dogfooding.md`
- 28章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/28-script-execution-model.md`
- `creator-kit/scripts/resolve-skill-dirs.sh` — SKILL_DIR 解決スクリプト
