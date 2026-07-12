---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Task]
kind: run
owner: {{owner}}
since: {{date}}
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal") }}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly") }}
role_suffix: orchestrator
# === Agent Team 統合スキル ===
# 設計書10章§6: Agent Team は same-file edits に弱い。
# 各 teammate task に file_ownership を frontmatter で宣言し、
# TaskCreated hook (scripts/hook-check-file-ownership.py) で衝突を block する。
#
# 必須 hook (settings.json):
#   TaskCreated:   scripts/hook-check-file-ownership.py  (ownership 衝突 block)
#   TaskCompleted: scripts/hook-verify-task-artifact.py  (teammate artifact 欠落 block)
#   SubagentStop:  scripts/hook-verify-evaluator-json.py (evaluator JSON 契約 block)
---

# {{name}}

## Purpose & Output Contract
{{output_contract}}

## Team Composition

| Role | Subagent | 主担当 file ownership | 並列度 |
|---|---|---|---|
| {{role1_name}} | {{role1_subagent}} | {{role1_files}} | 並列可 |
| {{role2_name}} | {{role2_subagent}} | {{role2_files}} | 並列可 |
| {{role3_name}} | {{role3_subagent}} | {{role3_files}} | 並列可 |
| evaluator | {{evaluator_subagent}} | (read-only) | 直列・最後 |

### Boundary
- 各 teammate は **自身の file_ownership 内のみ** 編集可
- 共有 file への書き込みは evaluator 経由でのみ許可
- 並列 task は same-message で起動（context efficiency）

## Key Rules
- task frontmatter に必ず `file_ownership: [path1, path2]` を宣言する
- `Task` tool 呼び出し時は file_ownership を JSON で渡す（TaskCreated hook が検査）
- 別 teammate の領域に踏み込む変更は手前で **task を分割** する

## ゴールシーク実行
> 固定手順は書かない。Gate を完了チェックリストとし、局面の選択と手順は AI が都度判断する。詳細は run-build-skill `references/goal-seek-paradigm.md`。

### ゴール (Goal)
全 teammate の artifact が揃い、evaluator の score >= threshold を満たした状態。

### 完了チェックリスト (Checklist)
- [ ] TaskCreated hook が exit 0（file ownership 衝突なし）
- [ ] 各 teammate の output_file が生成され、TaskCompleted hook の artifact 契約を通過
- [ ] evaluator JSON が SubagentStop hook の JSON 契約を通過
- [ ] evaluator (`context: fork`) の score >= threshold

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 局面（下カタログ）を選び手順を都度生成 → 3. 実行 → 4. チェックリスト再評価 → 全 `[x]` まで反復。未達は teammate 単位で改善ループ。

### 局面カタログ（順序は都度判断）
- **並列起動**: 独立 teammate は**同一メッセージ**で起動（context efficiency）。
  ```python
  Task(subagent_type="{{role1_subagent}}", file_ownership=[{{role1_files}}], ...)
  Task(subagent_type="{{role2_subagent}}", file_ownership=[{{role2_files}}], ...)
  Task(subagent_type="{{role3_subagent}}", file_ownership=[{{role3_files}}], ...)
  ```
- **artifact 検証**: 各 teammate の output_file を読み、TaskCompleted hook で成果物存在を検証。
- **統合（直列・最後）**: evaluator を `context: fork` で起動し全 artifact を採点。

## Gotchas
- **same-file edit 衝突**: Agent Team の最大の罠。file_ownership 宣言と TaskCreated hook 両方が必要
- **並列起動のし忘れ**: 独立 task を直列で起動すると context が肥大化する
- **evaluator を並列に混ぜない**: evaluator は **必ず最後**、かつ fork で起動

## Additional Resources
- 設計書 10章 §6 — Agent Team で同一 file 編集を避ける
- 設計書 09章 — Sycophancy対策（fork評価）
- `.claude/logs/task-ownership.json` — hook の state
