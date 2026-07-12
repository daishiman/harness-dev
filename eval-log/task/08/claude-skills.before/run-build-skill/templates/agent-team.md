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
#   TaskCompleted: scripts/hook-verify-evaluator-json.py (artifact 欠落 block)
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

## Steps

### Step 1: Task 生成（並列）
```python
# 3 teammate を同一メッセージで起動 (parallel)
Task(subagent_type="{{role1_subagent}}", file_ownership=[{{role1_files}}], ...)
Task(subagent_type="{{role2_subagent}}", file_ownership=[{{role2_files}}], ...)
Task(subagent_type="{{role3_subagent}}", file_ownership=[{{role3_files}}], ...)
```
**Gate**: TaskCreated hook が exit 0 を返すこと（ownership 衝突なし）。

### Step 2: 完了待機 + artifact 検証
- 各 teammate の output_file を読む
- TaskCompleted hook が evaluator JSON 契約を検証

### Step 3: 統合フェーズ（直列）
- evaluator (`context: fork`) が全 artifact を読んで採点
- score >= threshold で完了、未達なら teammate 単位で改善ループ

## Gotchas
- **same-file edit 衝突**: Agent Team の最大の罠。file_ownership 宣言と TaskCreated hook 両方が必要
- **並列起動のし忘れ**: 独立 task を直列で起動すると context が肥大化する
- **evaluator を並列に混ぜない**: evaluator は **必ず最後**、かつ fork で起動

## Additional Resources
- 設計書 10章 §6 — Agent Team で同一 file 編集を避ける
- 設計書 09章 — Sycophancy対策（fork評価）
- `.claude/logs/task-ownership.json` — hook の state
