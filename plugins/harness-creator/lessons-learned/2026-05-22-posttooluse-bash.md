---
date: 2026-05-22
trigger_event: PostToolUse
tool: Bash
severity: high
capability: shell
---

## observation

validator FAIL: rule X

## hypothesis

(自動記録: 失敗パターンを検出。根本原因は要 human triage)

## proposed_action

- 当該 capability に対する rubric 強化 / validator 追加を検討
- 再現条件を別 issue に起票
