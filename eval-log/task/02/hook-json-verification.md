# Hook JSON Verification

Date: 2026-05-19

## Checked Files

- `.claude/settings.json`
- `.claude/settings.creator-kit-hooks.json.example`
- `.claude/settings.meta-harness-hooks.json.example`
- `creator-kit/config/claude-settings-hooks.json.example`
- `creator-kit/config/meta-harness-hooks.json.example`
- `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md`
- `doc/task/02-settings-merge-specification.md`
- `doc/task/04-settings-merge-cli-specification.md`

## Result

- JSON parse: PASS
- Hook shape (`hooks` object -> event arrays -> matcher groups -> command handlers): PASS
- Official hook event key compatibility: PASS after correction

## Findings

1. `.claude/settings.json` used `FileChanged.matcher = "SKILL\\.md$"`. Current Claude Code docs describe `FileChanged` matchers as literal filenames, not the normal regex matcher flow. Fixed to `SKILL.md`.
2. 34a previously proposed `_generated_section_start` / `_generated_section_end` inside the `hooks` object. Current Claude Code docs define `hooks` object keys as hook events, so marker keys under `hooks` are unsafe. Fixed the specification to keep real hooks in official event-key form and put generation ownership in top-level `_build_claude_settings.managed_hooks`.

## Reference

- Claude Code Hooks reference: https://code.claude.com/docs/en/hooks
