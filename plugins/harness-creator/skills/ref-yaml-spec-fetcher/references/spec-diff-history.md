# Spec Diff History

このファイルは `.github/workflows/update-yaml-spec.yml` が週次自動更新する。最新が上。
## 2026-07-06T03:50:24Z

実仕様ページに変更を検知。

```diff
--- 
+++ 
@@ -1,24 +1,15094 @@
+# YAML Spec Cache
+
+fetcher: scripts/build-yaml-spec-cache.py
+
+## Source (skills): https://docs.claude.com/en/docs/claude-code/skills
+
+Extend Claude with skills - Claude Code Docs
+Documentation Index
+Fetch the complete documentation index at:
+/docs/llms.txt
+Use this file to discover all available pages before exploring further.
+Skip to main content
+Skills extend what Claude can do. Create a
+SKILL.md
+file with instructions, and Claude adds it to its toolkit. Claude uses skills when relevant, or you can invoke one directly with
+/skill-name
+.
+Create a skill when you keep pasting the same instructions, checklist, or multi-step procedure into chat, or when a section of CLAUDE.md has grown into a procedure rather than a fact. Unlike CLAUDE.md content, a skill’s body loads only when it’s used, so long reference material costs almost nothing until you need it.
+For built-in commands like
+/help
+and
+/compact
+, and bundled skills like
+/debug
+and
+/code-review
+, see the
+commands reference
+.
+Custom commands have been merged into skills.
+A file at
+.claude/commands/deploy.md
+and a skill at
+.claude/skills/deploy/SKILL.md
+both create
+/deploy
+and work the same way. Your existing
+.claude/commands/
+files keep working. Skills add optional features: a directory for supporting files, frontmatter to
+control whether you or Claude invokes them
+, and the ability for Claude to load them automatically when relevant.
+Claude Code skills follow the
+Agent Skills
+open standard, which works across multiple AI tools. Claude Code extends the standard with additional features like
+invocation control
+,
+subagent execution
+, and
+dynamic context injection
+.
+​
+Bundled skills
+Claude Code includes a set of bundled skills that are available in every session unless disabled with the
+disableBundledSkills
+setting, including
+/code-review
+,
+/batch
+,
+/debug
+,
+/loop
+, and
+/claude-api
+. Unlike most built-in commands, which execute fixed logic directly, bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. You invoke them the same way as any other skill, by typing
+/
+followed by the skill name.
+Bundled skills are listed alongside built-in commands in the
+commands reference
+, marked
+Skill
+in the Purpose column.
+​
+Run and verify your app
+Three bundled skills work together to launch your app and confirm changes against the running app instead of just tests:
+Skill
+Purpose
... (15032 more lines)
```

