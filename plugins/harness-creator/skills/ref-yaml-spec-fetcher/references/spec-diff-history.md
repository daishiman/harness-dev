# Spec Diff History

このファイルは `.github/workflows/update-yaml-spec.yml` が週次自動更新する。最新が上。
## 2026-08-10T01:27:37Z

実仕様ページに変更を検知。

```diff
--- 
+++ 
@@ -47,7 +47,9 @@
 subagent execution
 , and
 dynamic context injection
-.
+. See
+Using skill frontmatter outside Claude Code
+for which frontmatter fields are part of the standard and which are Claude Code extensions.
 ​
 Bundled skills
 Claude Code includes a set of bundled skills, such as
@@ -65,8 +67,7 @@
 . Bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. Most built-in commands instead execute fixed logic directly.
 You invoke a bundled skill the same way as any other skill, by typing
 /
-followed by the skill name. Claude invokes some bundled skills automatically when relevant; others,
-including
+followed by the skill name. Claude invokes some bundled skills automatically when relevant; others, including
 /verify
 and
 /code-review
@@ -323,7 +324,7 @@
 for more details.
 Files in
 .claude/commands/
-still work and support the same
+support the same
 frontmatter
 . Skills are recommended since they support additional features like supporting files.
 ​
@@ -443,11 +444,6 @@
 1. Run the test suite
 2. Build the application
 3. Push to the deployment target
-Your
-SKILL.md
-can contain anything, but thinking through how you want the skill invoked (by you, by Claude, or both) and where you want it to run (inline or in a subagent) helps guide what to include. For complex skills, you can also
-add supporting files
-to keep the main skill focused.
 Keep the body itself concise. Once a skill loads, its content
 stays in context across turns
 , so every line is a recurring token cost. State what to do rather than narrating how or why, and apply the same conciseness test you would for
@@ -540,8 +536,7 @@
 /name
 . Also prevents the skill from being
 preloaded into subagents
-.
-As of v2.1.196, also prevents the skill from running when a
+. As of v2.1.196, also prevents the skill from running when a
 scheduled task
 fires with the skill as its prompt. Default:
 false
@@ -575,7 +570,13 @@
 inherit
 to keep the active model. A value excluded by your organization’s
 availableModels
-allowlist is not used and the session keeps its current model.
+allowlist is not used and the session keeps its current model. With
+context: fork
+, the value sets the
+forked subagent’s model
+instead, and an excluded value follows the
+same rules as a subagent model override
+.
 effort
 No
 Effort level
@@ -612,8 +613,7 @@
 running it in the background
 . Default:
 true
-.
-Requires Claude Code v2.1.218 or later.
+. Requires Claude Code v2.1.218 or later.
 hooks
 No
 Hooks scoped to this skill’s lifecycle. See
@@ -641,6 +641,67 @@
... (3690 more lines)
```

## 2026-08-03T02:33:54Z

実仕様ページに変更を検知。

```diff
--- 
+++ 
@@ -136,6 +136,13 @@
 , and any other agent in the repo follow the recorded recipe instead of rediscovering it. Run
 /run-skill-generator
 once per project, and again if the build or launch process changes.
+/verify
+can also record its own recipe. When it has to build and drive your app without a recorded recipe, it writes what worked to
+.claude/skills/verify/SKILL.md
+at the repo root, or in the touched package directory in a monorepo, so later runs and other agents follow the same steps. At the repo root, the recorded skill replaces the bundled
+/verify
+. This requires Claude Code v2.1.200 or later.
+Claude edits the recorded file only when it steered a run wrong, such as a command that failed or a missing step, so you can commit the file without per-session diffs. Before v2.1.205, the bundled skill told Claude to fold in anything a run learned, which caused frequent merge conflicts.
 ​
 Getting started
 ​
@@ -257,7 +264,7 @@
 , this requires accepting the workspace trust dialog first.
 ​
 Live change detection
-Claude Code watches skill directories for file changes. Adding, editing, or removing a skill under
+Claude Code watches skill directories for file changes. When you add, edit, or remove a skill under
 ~/.claude/skills/
 , the project
 .claude/skills/
@@ -265,7 +272,7 @@
 .claude/skills/
 inside an
 --add-dir
-directory takes effect within the current session without restarting. Creating a top-level skills directory that did not exist when the session started requires restarting Claude Code so the new directory can be watched.
+directory, Claude Code picks up the change within the current session, without a restart. If you create a top-level skills directory that didn’t exist when the session started, restart Claude Code so it can watch the new directory.
 Live change detection covers
 SKILL.md
 text only. For a skill folder that is also a
@@ -282,16 +289,21 @@
 /reload-plugins
 to take effect.
 ​
-Automatic discovery from parent and nested directories
+Discovery from parent and nested directories
 Project skills load from
 .claude/skills/
-in your starting directory and in every parent directory up to the repository root, so starting Claude in a subdirectory still picks up skills defined at the root. When you work with files in subdirectories below your starting directory, Claude Code also discovers skills from nested
+in the directory where you start Claude Code and in every parent directory up to the repository root. Starting Claude in a subdirectory still picks up skills defined at the root. To load skills from a directory outside that path at startup, pass it with
+--add-dir
+. Claude Code reads
 .claude/skills/
-directories on demand. For example, if you’re editing a file in
+inside each added directory alongside the project skills.
+Skills in nested
+.claude/skills/
+directories below your starting directory aren’t loaded at startup. They load the first time Claude reads or edits a file inside that subdirectory, and stay available for the rest of the session. For example, after Claude edits a file under
 packages/frontend/
-, Claude Code also looks for skills in
+, skills in
 packages/frontend/.claude/skills/
-. This supports monorepo setups where packages have their own skills.
+become available. Until then, those skills don’t appear in autocomplete and can’t be invoked by name.
 Each skill is a directory with
 SKILL.md
 as the entrypoint:
@@ -1878,62 +1890,7 @@
 =
 f
 '''<!DOCTYPE html>
-<html><head>
-<meta charset="utf-8"><title>Codebase Explorer</title>
-<style>
-body
-{{
-font: 14px/1.5 system-ui, sans-serif; margin: 0; background: #1a1a2e; color: #eee;
-}}
-.container
-{{
-display: flex; height: 100vh;
-}}
-.sidebar
-{{
-width: 280px; background: #252542; padding: 20px; border-right: 1px solid #3d3d5c; overflow-y: auto; flex-shrink: 0;
-}}
... (1004 more lines)
```

## 2026-07-27T02:40:22Z

実仕様ページに変更を検知。

```diff
--- 
+++ 
@@ -50,9 +50,7 @@
 .
 ​
 Bundled skills
-Claude Code includes a set of bundled skills that are available in every session unless disabled with the
-disableBundledSkills
-setting, including
+Claude Code includes a set of bundled skills, such as
 /doctor
 ,
 /code-review
@@ -64,14 +62,29 @@
 /loop
 , and
 /claude-api
-. Unlike most built-in commands, which execute fixed logic directly, bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. You invoke them the same way as any other skill, by typing
+. Bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. Most built-in commands instead execute fixed logic directly.
+You invoke a bundled skill the same way as any other skill, by typing
 /
-followed by the skill name.
+followed by the skill name. Claude invokes some bundled skills automatically when relevant; others,
+including
+/verify
+and
+/code-review
+, run only when you invoke them, which keeps you in control of when these longer-running checks spend time and tokens. Before v2.1.215, Claude could also run
+/verify
+and
+/code-review
+on its own.
+Bundled skills are available in every session. To turn them off, use the
+disableBundledSkills
+setting, which disables every bundled skill except
+/doctor
+.
 The
 /doctor
-setup checkup is the one exception to
+setup checkup stays typable when
 disableBundledSkills
-in Claude Code v2.1.205 and later: it stays typable when the setting is on. To hide it, set the
+is on, in Claude Code v2.1.205 and later. To hide it, set the
 DISABLE_DOCTOR_COMMAND
 environment variable or a
 skillOverrides
@@ -453,6 +466,27 @@
 All fields are optional. Only
 description
 is recommended so Claude knows when to use the skill.
+Boolean fields accept
+yes
+,
+no
+,
+on
+,
+off
+,
+1
+, and
+0
+in any letter case, in addition to
+true
+and
+false
+. Before v2.1.218, Claude Code recognized only
+true
+and
+false
+.
 Field
 Required
 Description
@@ -460,7 +494,7 @@
 No
 Display name shown in skill listings. Defaults to the directory name. See
 How a skill gets its command name
-for how this differs from the name you type to invoke the skill.
... (2301 more lines)
```

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

