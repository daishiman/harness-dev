# Spec Diff History

このファイルは `.github/workflows/update-yaml-spec.yml` が週次自動更新する。最新が上。
## 2026-07-20T02:43:21Z

実仕様ページに変更を検知。

```diff
--- 
+++ 
@@ -100,7 +100,11 @@
 and
 /verify
 how to build and launch your project
-All three skills require Claude Code v2.1.145 or later.
+All three skills require Claude Code v2.1.145 or later. Check your version with
+claude --version
+or the
+/status
+command.
 /run
 and
 /verify
@@ -331,6 +335,35 @@
 Load from additional directories
 .
 ​
+Skills in Cowork and cloud sessions
+Cowork
+sessions and
+cloud sessions
+, including
+routines
+, don’t read
+~/.claude/skills/
+on your machine. Both interactive and scheduled Cowork sessions load the skills enabled for your claude.ai account, synced at session start; manage them from
+Customize
+in the Desktop app sidebar or from the skills settings on claude.ai. Cloud sessions additionally load project skills committed to the cloned repository’s
+.claude/skills/
+.
+If a skill exists only in
+~/.claude/skills/
+on your machine, Claude Code reports that the skill was not found when a
+routine
+invokes it, because each routine run starts as a fresh remote session. To make a personal skill available in these sessions:
+For Cowork and cloud sessions, enable the skill for your claude.ai account.
+For cloud sessions, you can instead commit the skill to the repository’s
+.claude/skills/
+, or ship it in a plugin declared in the repository’s
+.claude/settings.json
+. Repo-declared plugins
+install at session start
+; plugins enabled only in your user settings don’t transfer.
+Desktop scheduled tasks
+are different: they run locally on your machine and load skills from the same locations as any other local session.
+​
 Configure skills
 Skills are configured through YAML frontmatter at the top of
 SKILL.md
@@ -361,7 +394,11 @@
 /skill-name
 rather than letting Claude decide when to run them. Add
 disable-model-invocation: true
-to prevent Claude from triggering it automatically.
+to prevent Claude from triggering it automatically. The example below adds
+context: fork
+, which runs the skill in its own subagent context; see
+Run skills in a subagent
+.
 ---
 name
 :
@@ -474,7 +511,9 @@
 .
 allowed-tools
 No
-Tools Claude can use without asking permission when this skill is active. Accepts a space- or comma-separated string, or a YAML list.
+Tools Claude can use without asking permission during the turn that invokes this skill. The grant clears when you send your next message. Accepts a space- or comma-separated string, or a YAML list. See
+Pre-approve tools for a skill
+.
 disallowed-tools
 No
 Tools removed from Claude’s available pool while this skill is active. Use for autonomous skills that should never call certain tools, such as
@@ -507,7 +546,9 @@
 No
 Set to
 fork
-to run in a forked subagent context.
... (3206 more lines)
```

## 2026-07-13T02:32:50Z

実仕様ページに変更を検知。

```diff
--- 
+++ 
@@ -53,6 +53,8 @@
 Claude Code includes a set of bundled skills that are available in every session unless disabled with the
 disableBundledSkills
 setting, including
+/doctor
+,
 /code-review
 ,
 /batch
@@ -65,6 +67,19 @@
 . Unlike most built-in commands, which execute fixed logic directly, bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. You invoke them the same way as any other skill, by typing
 /
 followed by the skill name.
+The
+/doctor
+setup checkup is the one exception to
+disableBundledSkills
+in Claude Code v2.1.205 and later: it stays typable when the setting is on. To hide it, set the
+DISABLE_DOCTOR_COMMAND
+environment variable or a
+skillOverrides
+entry of
+"doctor": "off"
+. Before v2.1.205,
+/doctor
+was a built-in command rather than a bundled skill.
 Bundled skills are listed alongside built-in commands in the
 commands reference
 , marked
@@ -206,6 +221,7 @@
 runs the project-root skill. Type the qualified name
 /apps/web:deploy
 to run the nested variant explicitly.
+When you or Claude invoke the unqualified name, the project-root skill loads, and Claude Code appends a list of the directory-qualified variants to its content with an instruction to also invoke any variant whose directory holds the files Claude is working on. A nested skill therefore still applies to work in its directory when only the unqualified name is invoked. Requires Claude Code v2.1.203 or later.
 A
 <skill-name>
 entry in the enterprise, personal, or project locations can be a symlink to a directory elsewhere on disk. Claude Code follows the symlink and reads
@@ -782,6 +798,9 @@
 When you or Claude invoke a skill, the rendered
 SKILL.md
 content enters the conversation as a single message and stays there for the rest of the session. Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps.
+When Claude re-invokes a skill whose rendered content is identical to the copy already in context, Claude Code adds a short note that the skill is already loaded rather than a second copy of the content. When the rendered content differs, because the arguments changed or a
+dynamic context
+command produced new output, Claude Code appends the full content again. Before v2.1.202, every re-invocation appended another full copy of the skill’s instructions.
 Auto-compaction
 carries invoked skills forward within a token budget. When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens. Claude Code fills this budget starting from the most recently invoked skill, so older skills can be dropped entirely after compaction if you have invoked many in one session.
 If a skill seems to stop influencing behavior after the first response, the content is usually still present and the model is choosing other tools or approaches. Strengthen the skill’s
@@ -1957,14 +1976,15 @@
 if you only want manual invocation
 ​
 Skill descriptions are cut short
-Skill descriptions are loaded into context so Claude knows what’s available. All skill names are always included, but if you have many skills, descriptions are shortened to fit the character budget, which can strip the keywords Claude needs to match your request. The budget scales at 1% of the model’s context window. When it overflows, descriptions for the skills you invoke least are dropped first, so the skills you actually use keep their full text. Run
+Claude Code loads a listing of skill names and descriptions into context so Claude knows what’s available. The listing always contains every skill name, but if you have many skills, Claude Code shortens descriptions to fit the listing’s character budget, which can strip the keywords Claude needs to match your request. The budget scales at 1% of the model’s context window. When the listing overflows, Claude Code drops descriptions starting with the skills you invoke least, so the skills you use most keep their full text.
+Run
 /doctor
-to see how many skill descriptions are being shortened or dropped and which skills are affected.
-As of v2.1.196, the Skills row in
+for an estimate of the listing’s context cost and its biggest contributors. When the listing exceeds its budget, Claude Code also writes a warning to the debug log, visible with
+--debug
+.
+The Skills row in
 /context
-reports the size of the listing after the budget is applied, so it matches what the model receives. Earlier versions counted the full text of every description, so the row could show a value several times larger than the budget
-/doctor
-reports.
+reports the size of the listing after the budget is applied, so it matches what the model receives. Before v2.1.196, the row counted the full text of every description and could show a value several times larger than the configured budget.
 To raise the budget, set the
 skillListingBudgetFraction
 setting (e.g.
@@ -2003,16 +2023,7 @@
 Permissions
 : control tool and skill access
 Claude Tag skills
-: project skills committed to a repo also load when that repo is used in a Claude Tag channel
-Was this page helpful?
-Yes
-No
-Reference
... (1239 more lines)
```

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

