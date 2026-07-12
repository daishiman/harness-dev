---
name: run-skill-rubric-governance
description: rubric変更を提案するとき、rubric改正を施行するときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Bash(git *)]
kind: run
prefix: run
owner: team-platform
since: 2026-05-17
version: 0.1.0
effect: local-artifact
reference_refs:
  - ref-domain-rubric-template
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-govern.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: rubric.json 改正後に compute-rubric-hash.py で rubric_hash を再計算し check-rubric-sync.py が exit 0(RUBRIC_DRIFT なし)で assign 側派生と版ずれゼロを確認している
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: diff-rubric-impact.py の合否変動率が 30% 超のとき bump を major へ強制昇格し semver 規約(major厳格化 minor緩和 patch文言のみ)に整合した rubric_version へ更新している
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 提案者と承認者が同一でなく第三者レビュア tooling役を含む4ロール承認ボードが独立に発効を承認し proposer 非イコール approver を満たしている
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: 猶予期間(major14日 minor7日 patch即時)と旧ルール warning ダウングレードを governance log へ記録し発効後 git commit で log を closed に更新した到達状態が adequate である
      verify_by: elegant-review
---

# run-skill-rubric-governance

## Purpose & Output Contract

`ref-skill-design-rubric/references/rubric.json` の改正 Runbook（27章）。
提案 → 影響評価 → 猶予期間 → 発効 の4フェーズを1本のワークフローで管理。

**入力**: `templates/proposal.json` を埋めた改正提案ファイル
**出力**: rubric.json のPR、 governance log（`$SKILL_DIR/log/*.jsonl`）

## Key Rules

1. **直接編集禁止**: rubric.json は本Runbook経由でのみ更新。
2. **semver**: minor=緩和（しきい値↓、ルール削除）、major=厳格化（ルール追加、weight↑）、patch=文言のみ。
3. **猶予期間**: major は最低14日、minor は7日、patch は即時可。
4. **影響評価必須**: `scripts/diff-rubric-impact.py` で過去 eval-log の合否変動率を測る。
5. **承認ボード**: 提案者 / 第三者レビュア / 承認者 / tooling役 の4ロール（`references/governance-board.md`）。

## ゴールシーク実行

### ゴール (Goal)

提案された rubric 改正が「影響評価・猶予期間・rubric_hash 再計算・派生同期・版ずれ検証」を全通過し、`rubric.json` が正しい semver で発効され、governance log が closed として記録された状態。

### 目的・背景 (Why)

rubric は全 Skill 採点の SSOT であり、直接編集や手順抜けは採点基盤を破壊する。固定手順では提案種別（add/modify/remove）や bootstrap 有無に応じた分岐に脆いため、到達状態（発効＋検証通過＋log closed）をゴールとし、未達項目を都度埋める。

### 完了チェックリスト (Checklist)

- [ ] `resolve-skill-dirs.py` で SKILL_DIR が解決され `eval-log/skill-dirs.json` 出力済み
- [ ] `templates/proposal.json` が rule_id / change_type / bump / rationale / sunset_days を埋めた状態で存在
- [ ] 時系列違反率 (`lint-rubric-violation.py --log-dir eval-log --n 3 --threshold 0.20`) を評価し `trigger.json` 出力済み（eval-log 件数が `governance-params.json` の `bootstrap_mode.min_eval_log_records`（既定 20）未満なら exit 3=pending を許容、bootstrap 時は `solo_operator_mode: true` を log 記録し major bump は禁止）
- [ ] ルール別違反集計 (`$SKILL_DIR/scripts/lint-rubric-violation.py --rule $RULE_ID`) と差分影響評価 (`diff-rubric-impact.py`) を実施済み
- [ ] 合否変動率が 30% 超なら bump を major へ強制昇格している
- [ ] 猶予期間（major≥14日 / minor≥7日 / patch即時）を governance log（jsonl 1行）に記録し、旧ルールを warning（severity→low）へダウングレード済み
- [ ] `rubric.json` 編集後 `rubric_version` を semver で bump 済み
- [ ] `assign-skill-design-evaluator/references/rubric.json` を deep-merge 同期済み
- [ ] `compute-rubric-hash.py` で `rubric.normalized.json` と `rubric_hash` を再計算済み（27章§8.2）
- [ ] `check-rubric-sync.py` が exit 0（`RUBRIC_DRIFT:` でない）であることを確認済み
- [ ] `git commit` 実行し governance log を closed に更新済み
- [ ] 1 release 後に違反率が悪化した場合、安定版凍結条件（`freeze.consecutive_runs` × `violation_rate_ceiling`）を満たす版へ `rollback-to-stable.py` で巻き戻し可能な状態（PostToolUse Hook 連携、27章§9）

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップ（現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し）に従う。本スキル固有差分:

- 対象ファイル: `ref-skill-design-rubric/references/rubric.json`（直接編集禁止・本 Runbook 経由のみ）、`templates/proposal.json`、governance log（`$SKILL_DIR/log/*.jsonl`）
- 固定パス/閾値: 違反率閾値 0.20 / 連続 3 release、合否変動率 30% で major 昇格、bootstrap 最小件数 20、猶予 major14/minor7/patch0 日
- 検証は `## 検証` 系スクリプト（`lint-rubric-violation.py` / `diff-rubric-impact.py` / `check-rubric-sync.py`）へ寄せ、決定論的に `[x]` 判定する
- 規定周回を超えても未達なら残項目を承認ボード（`references/governance-board.md` の 4 ロール）へ差し戻す

### 局面カタログ (順序は都度判断)

- 出力先解決: `python3 plugins/harness-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py --skill-dir-name run-skill-rubric-governance > eval-log/skill-dirs.json`
- 影響評価コマンド群:
  ```bash
  python3 plugins/skill-governance-lint/scripts/lint-rubric-violation.py --log-dir eval-log --n 3 --threshold 0.20 --out eval-log/trigger.json
  python3 "$SKILL_DIR/scripts/lint-rubric-violation.py" --logs "$SKILL_DIR/log" --rule "$RULE_ID"
  python3 "$SKILL_DIR/scripts/diff-rubric-impact.py" --proposal proposal.json --logs "$SKILL_DIR/log"
  ```
- 発効: `compute-rubric-hash.py --rubric plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json` → `check-rubric-sync.py`（exit 0 確認）→ `git commit`
- 自動 rollback:
  ```bash
  python3 plugins/skill-governance-automation/scripts/rollback-to-stable.py \
    --rubric plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json \
    --versions-md eval-log/rubric-versions.md \
    --params references/governance-params.json --dry-run
  ```

## Gotchas

- **patchで内容変更は禁則**: 文言のみ。閾値や severity 変更は最低 minor。
- **assign 側 override をrebaseし忘れる事故**: deep-merge の most-specific-wins が壊れる（29章）。
- **eval-log がない**: 影響評価できないので `diff-rubric-impact.py` は exit 2 でフェイルセーフ。
- **緊急パッチ**: high severity の誤検出固定は patch 例外（log に `emergency: true`）。

## Additional Resources

- `templates/proposal.json` — 改正提案テンプレ
- `plugins/skill-governance-lint/scripts/lint-rubric-violation.py` — **時系列違反率検出（連続 N×閾値超 → trigger.json）正本（27章§3.2）**
- `$SKILL_DIR/scripts/lint-rubric-violation.py` — ルール別違反集計（単一 release/proposal 単位）
- `$SKILL_DIR/scripts/diff-rubric-impact.py` — 差分影響評価
- `plugins/skill-governance-automation/scripts/compute-rubric-hash.py` — rubric_hash 再計算（27章§8.2）
- `plugins/skill-governance-automation/scripts/notify-if-governance-trigger.py` — Stop Hook 用招集通知（27章§3.4）
- `plugins/skill-governance-automation/scripts/rollback-to-stable.py` — 安定版凍結条件を満たす版への自動 rollback（27章§9）
- `plugins/skill-governance-automation/scripts/doc-to-skill-adapter.py` — 設計書を Skill artifact 化して自己採点する起動装置（26章）
- `references/governance-board.md` — ボード構成
- `references/version-rules.md` — semver規約
- 27章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md`
- 26章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/26-meta-skill-dogfooding.md`
- 28章: `{{PROJECT_ROOT}}/doc/ClaudeCodeスキルの設計書/28-script-execution-model.md`
- `plugins/harness-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py` — SKILL_DIR 解決スクリプト
