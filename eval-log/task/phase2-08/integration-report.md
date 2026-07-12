# Phase 2 統合検証レポート

生成: 2026-05-20T20:19:58.523518+09:00

## Summary

- plugins: skill-creator, skill-governance-adapters, skill-governance-automation, skill-governance-config, skill-governance-hooks, skill-governance-lint, skill-governance-migration, skill-governance-secrets
- symlinks plan 件数: 26 (全 noop)
- symlinks conflicts: 0
- settings conflicts: 0
- invariants_checked: ['INV-1', 'INV-2', 'INV-3', 'INV-4', 'INV-5', 'INV-6', 'INV-7', 'INV-8', 'INV-9', 'INV-10', 'INV-11', 'INV-12']
- union match: PASS (skills + agents + commands)
- dangling symlink: 0
- creator-kit symlink refs: 0
- user section hash: unchanged
- revert dry-run: PASS
- claude plugin validate: PASS for all plugins (author warning only)

## Notes

- Initial dangling check found two .claude/config links pointing at removed creator-kit/config files; they were relinked to plugins/skill-governance-config/config and rechecked as zero.
- The current claude CLI expects plugin paths for local validation, so validation was executed as `claude plugin validate plugins/<name>`.
- Precondition `git status -s clean` was not met before this task; unrelated existing worktree changes were left intact.

## Claude validate exit codes

- skill-creator=0
- skill-governance-adapters=0
- skill-governance-automation=0
- skill-governance-config=0
- skill-governance-hooks=0
- skill-governance-lint=0
- skill-governance-migration=0
- skill-governance-secrets=0
