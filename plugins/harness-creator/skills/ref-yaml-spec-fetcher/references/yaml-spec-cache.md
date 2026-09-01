# YAML Spec Cache

last_fetched: 2026-08-31T03:32:27Z
fetcher: scripts/build-yaml-spec-cache.py

## Source (skills): https://docs.claude.com/en/docs/claude-code/skills

Extend Claude with skills - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Skills extend what Claude can do. Create a
SKILL.md
file with instructions, and Claude adds it to its toolkit. Claude uses skills when relevant, or you can invoke one directly with
/skill-name
.
Create a skill when you keep pasting the same instructions, checklist, or multi-step procedure into chat, or when a section of CLAUDE.md has grown into a procedure rather than a fact. Unlike CLAUDE.md content, a skill’s body loads only when it’s used, so long reference material costs almost nothing until you need it.
For built-in commands like
/help
and
/compact
, and bundled skills like
/debug
and
/code-review
, see the
commands reference
.
Custom commands have been merged into skills.
A file at
.claude/commands/deploy.md
and a skill at
.claude/skills/deploy/SKILL.md
both create
/deploy
and work the same way. Your existing
.claude/commands/
files keep working. Skills add optional features: a directory for supporting files, frontmatter to
control whether you or Claude invokes them
, and the ability for Claude to load them automatically when relevant.
Claude Code skills follow the
Agent Skills
open standard, which works across multiple AI tools. Claude Code extends the standard with additional features like
invocation control
,
subagent execution
, and
dynamic context injection
. See
Using skill frontmatter outside Claude Code
for which frontmatter fields are part of the standard and which are Claude Code extensions.
​
Bundled skills
Claude Code includes a set of bundled skills, such as
/doctor
,
/code-review
,
/batch
,
/debug
,
/loop
, and
/claude-api
. Bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. Most built-in commands instead execute fixed logic directly.
You invoke a bundled skill the same way as any other skill, by typing
/
followed by the skill name. Claude invokes some bundled skills automatically when relevant; others, including
/verify
, run only when you invoke them, which keeps you in control of when these longer-running checks spend time and tokens.
Most bundled skills are available in every session. A few depend on a specific feature:
/workflow-authoring
, for example, is available only when
dynamic workflows
are enabled.
To turn bundled skills off, use the
disableBundledSkills
setting, which disables every bundled skill except
/doctor
.
The
/doctor
setup checkup stays typable when
disableBundledSkills
is on, in Claude Code v2.1.205 and later. To hide it, set the
DISABLE_DOCTOR_COMMAND
environment variable or a
skillOverrides
entry of
"doctor": "off"
. Before v2.1.205,
/doctor
was a built-in command rather than a bundled skill.
Bundled skills are listed alongside built-in commands in the
commands reference
, marked
Skill
in the Purpose column.
​
Run and verify your app
Three bundled skills work together to launch your app and confirm changes against the running app instead of just tests:
Skill
Purpose
/run
Launch and drive your app to see a change working
/verify
Build and run your app to confirm a code change does what it should, without falling back to tests or type checks
/run-skill-generator
Teach
/run
and
/verify
how to build and launch your project
/run
and
/verify
work without setup. They infer the launch from your project type (CLI, server, TUI, browser-driven) and from what’s in your README,
package.json
, or
Makefile
. That inference gets unreliable for projects that need anything beyond a standard launch: a database, an env file, a graphical session, a multi-step build.
/run-skill-generator
records the recipe instead. It gets your app running from a clean environment, captures what worked (the install commands, the env vars, the launch script), and commits it as a per-project skill at
.claude/skills/run-<name>/
. After that,
/run
,
/verify
, and any other agent in the repo follow the recorded recipe instead of rediscovering it. Run
/run-skill-generator
once per project, and again if the build or launch process changes.
/verify
can also record its own recipe. When it has to build and drive your app without a recorded recipe, it writes what worked to
.claude/skills/verify/SKILL.md
at the repo root, or in the touched package directory in a monorepo, so later runs and other agents follow the same steps. At the repo root, the recorded skill replaces the bundled
/verify
. This requires Claude Code v2.1.200 or later.
Claude edits the recorded file only when it steered a run wrong, such as a command that failed or a missing step, so you can commit the file without per-session diffs. Before v2.1.205, the bundled skill told Claude to fold in anything a run learned, which caused frequent merge conflicts.
​
Getting started
​
Create your first skill
This example creates a skill that summarizes the uncommitted changes in your git repository and flags anything risky. It pulls the live diff into the prompt before Claude reads it, so the response is grounded in your actual working tree rather than what Claude can guess from open files. Claude loads the skill automatically when you ask about your changes, or you can invoke it directly with
/summarize-changes
.
1
Create the skill directory
Create a directory for the skill in your personal skills folder. Personal skills are available across all your projects.
mkdir
-p
~/.claude/skills/summarize-changes
2
Write SKILL.md
Every skill needs a
SKILL.md
file with two parts: YAML frontmatter between
---
markers that tells Claude when to use the skill, and markdown content with the instructions Claude follows when the skill runs. The directory name becomes the command you type, and the
description
helps Claude decide when to load the skill automatically.
Save this to
~/.claude/skills/summarize-changes/SKILL.md
:
---
description
:
Summarizes uncommitted changes and flags anything risky. Use when the user asks what changed, wants a commit message, or asks to review their diff.
---
## Current changes
!`git
diff HEAD`
## Instructions
Summarize the changes above in two or three bullet points, then list any risks you notice such as missing error handling, hardcoded values, or tests that need updating. If the diff is empty, say there are no uncommitted changes.
The
!`git diff HEAD`
line uses
dynamic context injection
: Claude Code runs the command and replaces the line with its output before Claude sees the skill content, so the instructions arrive with the current diff already inlined.
3
Test the skill
Open a git project, make a small edit to any file, and start Claude Code by running
claude
. You can test the skill two ways.
Let Claude invoke it automatically
by asking something that matches the description:
What did I change?
Or invoke it directly
with the skill name:
/summarize-changes
Either way, Claude should respond with a short summary of your edit and a list of risks.
​
Where skills live
Where you store a skill determines who can use it:
Location
Path
Applies to
Enterprise
See
managed settings
All users in your organization
Personal
~/.claude/skills/<skill-name>/SKILL.md
All your projects
Project
.claude/skills/<skill-name>/SKILL.md
This project only
Plugin
<plugin>/skills/<skill-name>/SKILL.md
Where plugin is enabled
When skills share the same name, Claude Code resolves the conflict by source:
Across levels, enterprise overrides personal, and personal overrides project.
For example, with a
deploy
skill in both
~/.claude/skills/
and your project’s
.claude/skills/
,
/deploy
runs the personal one.
A skill at any of these levels also overrides a bundled skill with the same name, but not the bundled skill’s aliases.
For example, a
code-review
skill in your project’s
.claude/skills/
replaces the bundled
/code-review
, and typing the bundled alias
/review
never runs your skill.
Plugin skills use a
plugin-name:skill-name
namespace, so they can’t conflict with other levels.
For example,
my-plugin/skills/deploy/SKILL.md
becomes
/my-plugin:deploy
and loads alongside a
deploy
skill in your project’s
.claude/skills/
.
If you have files in
.claude/commands/
, those work the same way, but if a skill and a command share the same name, the skill takes precedence.
For example, with both
.claude/commands/deploy.md
and
.claude/skills/deploy/SKILL.md
,
/deploy
runs the skill.
A skill or command from any of these sources overrides a skill
synced from your claude.ai account
with the same name.
For example, with a
deploy
skill enabled on claude.ai and another in your project’s
.claude/skills/
,
/deploy
runs the project one.
Skills also load from nested
.claude/skills/
directories below your working directory. When Claude reads or edits a file in a subdirectory, skills from that subdirectory’s
.claude/skills/
become available. This lets a monorepo package provide its own skills that apply when working on that package, even if the session started at the repo root.
If a nested skill shares a name with another skill, both stay available. For example, with a
deploy
skill at the project root and another in
apps/web/.claude/skills/
:
The nested one appears under a directory-qualified name,
apps/web:deploy
.
Its description says which directory it applies to.
Claude picks the variant that matches the files it is working on.
Typing
/deploy
runs the project-root skill. Type the qualified name
/apps/web:deploy
to run the nested variant explicitly.
When you or Claude invoke the unqualified name, the project-root skill loads, and Claude Code appends a list of the directory-qualified variants to its content with an instruction to also invoke any variant whose directory holds the files Claude is working on. A nested skill therefore still applies to work in its directory when only the unqualified name is invoked.
The folder name
synced
is reserved in the enterprise, personal, and project skills locations, in any capitalization. Claude Code
downloads the skills you enable on claude.ai
into
~/.claude/skills/synced/
when
CLAUDE_CODE_SYNC_SKILLS
is set in non-interactive mode, and skips a skill you author at that name.
A
<skill-name>
entry in the enterprise, personal, or project locations can be a symlink to a directory elsewhere on disk. Claude Code follows the symlink and reads
SKILL.md
from the target directory, and if the same target is reachable from more than one location, Claude Code loads the skill once. Plugin skills handle symlinks differently; see
Share files within a marketplace with symlinks
.
Add a
.claude-plugin/plugin.json
to a skill folder and it loads as a
plugin
named
<name>@skills-dir
, so it can bundle agents, hooks, and MCP servers. In a project’s
.claude/skills/
, this requires accepting the workspace trust dialog first.
​
Live change detection
Claude Code watches skill directories for file changes. When you add, edit, or remove a skill under
~/.claude/skills/
, the project
.claude/skills/
, or a
.claude/skills/
inside an
--add-dir
directory, Claude Code picks up the change within the current session, without a restart. If you create a top-level skills directory that didn’t exist when the session started, restart Claude Code so it can watch the new directory.
Live change detection covers
SKILL.md
text only. For a skill folder that is also a
plugin
, changes to
hooks/
,
.mcp.json
,
agents/
, and
output-styles/
need
/reload-plugins
to take effect.
​
Discovery from parent and nested directories
Project skills load from
.claude/skills/
in the directory where you start Claude Code and in every parent directory up to the repository root. Starting Claude in a subdirectory still picks up skills defined at the root. To load skills from a directory outside that path at startup, pass it with
--add-dir
. Claude Code reads
.claude/skills/
inside each added directory alongside the project skills. When you
move the session with
/cd
on v2.1.246 or later, Claude Code adds the new directory’s project skills.
Skills in nested
.claude/skills/
directories below your starting directory aren’t loaded at startup. They load the first time Claude reads or edits a file inside that subdirectory, and stay available for the rest of the session. For example, after Claude edits a file under
packages/frontend/
, skills in
packages/frontend/.claude/skills/
become available. Until then, those skills don’t appear in autocomplete and can’t be invoked by name.
Files in
.claude/commands/
support the same
frontmatter
, except
name
and
paths
, which Claude Code ignores in a command file. You invoke a command file by its file name. Skills are recommended since they support additional features like
supporting files
.
​
Skills from additional directories
The
--add-dir
flag and
/add-dir
command
grant file access
rather than configuration discovery, but skills and commands are an exception: Claude Code loads
.claude/skills/
and
.claude/commands/
from each added directory automatically. This exception applies to
--add-dir
,
/add-dir
, and directories the Agent SDK adds through
additionalDirectories
in TypeScript or
add_dirs
in Python, which the SDK passes to Claude Code as
--add-dir
.
The
permissions.additionalDirectories
setting in
settings.json
grants file access only and doesn’t load skills, commands, or subagents, even though the TypeScript option has the same name. See
Live change detection
for how skill edits are picked up during a session.
Claude Code loads skills, commands, and subagents from an added directory only when the
project
setting source
is enabled, which is the default. If you pass
--setting-sources
on the CLI, or set
settingSources
or
setting_sources
explicitly in the SDK, include
project
in the list. In
--safe-mode
, Claude Code loads none of the three. A
strictPluginOnlyCustomization
managed policy and
bare mode
treat the three differently:
Skills
in
.claude/skills/
: a policy that locks skills turns them off. Bare mode still loads them.
Commands
in
.claude/commands/
: the same skills lock turns them off. Bare mode skips them.
Subagents
in
.claude/agents/
: the policy’s
agents
entry turns them off, not its
skills
entry. Bare mode skips every
.claude/agents/
folder, including the project’s own.
Claude Code never watches
.claude/agents/
or
.claude/commands/
in an added directory, so after you add or edit a subagent or command file there, restart the session to load the change. In bare mode, Claude Code doesn’t watch skill directories at all.
Apart from the
enabledPlugins
and
extraKnownMarketplaces
keys in an added directory’s
.claude/settings.json
and
.claude/settings.local.json
, Claude Code doesn’t load other
.claude/
configuration, such as output styles, from additional directories. See the
exceptions table
for the complete list of what is and isn’t loaded, and the recommended ways to share configuration across projects.
CLAUDE.md files from
--add-dir
directories are not loaded by default. To load them, set
CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1
. See
Load from additional directories
.
​
Skills in Cowork and cloud sessions
Cowork
sessions and
cloud sessions
, including
routines
, don’t read
~/.claude/skills/
on your machine. Both interactive and scheduled Cowork sessions load the skills enabled for your claude.ai account, synced at session start; manage them from
Customize
in the Desktop app sidebar or from the skills settings on claude.ai. Cloud sessions additionally load project skills committed to the cloned repository’s
.claude/skills/
.
If a skill exists only in
~/.claude/skills/
on your machine, Claude Code reports that the skill was not found when a
routine
invokes it, because each routine run starts as a fresh remote session. To make a personal skill available in these sessions:
For Cowork and cloud sessions, enable the skill for your claude.ai account.
For cloud sessions, you can instead commit the skill to the repository’s
.claude/skills/
, or ship it in a plugin declared in the repository’s
.claude/settings.json
. Repo-declared plugins
install at session start
; plugins enabled only in your user settings don’t transfer.
Desktop scheduled tasks
are different: they run locally on your machine and load skills from the same locations as any other local session.
​
Skills synced from claude.ai
This section applies to you if you enabled skills for your claude.ai account. In Cowork and cloud sessions, Claude Code loads those skills without any setup on your machine. In any other session on your machine, Claude Code loads them only after you turn syncing on with
CLAUDE_CODE_SYNC_SKILLS
in a non-interactive run, as
Where synced skills load
describes.
Claude Code downloads a synced skill from your account rather than reading a file you wrote on the machine where the session runs, so it applies rules to synced skills that don’t apply to the skills you store in the
skills locations
.
​
Where synced skills load
In a Cowork or cloud session, Claude Code loads the skills enabled for your claude.ai account, and
Skills in Cowork and cloud sessions
says how to choose which skills those sessions get.
In any other session on your machine, Claude Code loads them only after you download them once in a non-interactive run:
1
Enable the skills for your claude.ai account
Enable each skill you want for your claude.ai account, as
Skills in Cowork and cloud sessions
describes. Claude Code downloads only the skills you enabled, and it needs your claude.ai sign-in to download them.
2
Run Claude Code in non-interactive mode with syncing turned on
Claude Code downloads synced skills only when you run it in
non-interactive mode
with the
-p
flag and set
CLAUDE_CODE_SYNC_SKILLS
to
1
. The prompt you pass doesn’t affect the download.
CLAUDE_CODE_SYNC_SKILLS
=
1
claude
-p
"List the skills you have available"
Claude Code downloads the skills into
~/.claude/skills/synced/
, answers the prompt, and exits like any other non-interactive run. The downloaded skills stay on disk after it exits, so you don’t need to keep the run open. Claude Code downloads skills only during a run with
CLAUDE_CODE_SYNC_SKILLS
set, so after you enable or change a skill on claude.ai, run the command again. To change how long the run waits for the sync before it answers the prompt, set
CLAUDE_CODE_SYNC_SKILLS_WAIT_TIMEOUT_MS
.
3
Confirm the skills load in a local session
Start an interactive session, without
CLAUDE_CODE_SYNC_SKILLS
set, and run
/skills
. The menu lists the downloaded skills under
claude.ai sync
. Every local session you start afterwards with the same claude.ai sign-in loads them from
~/.claude/skills/synced/
too.
​
When a synced skill name matches another command
Claude Code skips a synced skill whose name matches any other command, and that other command runs. The other command can be a built-in command, a
bundled skill
, a skill at any
local level
, a plugin skill, a file in
.claude/commands/
, or an
MCP prompt
. Claude Code also reserves the names of its own built-in commands and bundled skills even when they’re unavailable in your session, for example after you turn bundled skills off, so it skips a synced skill with one of those names too.
Claude Code labels synced skills so you can tell where they came from. The
/skills
menu and
/context
group synced skills under
claude.ai sync
, and the
/
command menu marks them as coming from claude.ai.
When it compares names, Claude Code ignores case, spacing, and invisible characters, and treats compatibility forms such as fullwidth letters and dash variants as their plain equivalents, so a synced
Commit
can’t load beside a local
commit
. A name that differs only by a look-alike letter from another alphabet counts as a different name, and the
claude.ai sync
label is how you tell the two apart.
​
How Claude Code handles the frontmatter of a synced skill
Claude Code applies two rules to a synced skill’s frontmatter:
Claude Code honors the frontmatter in every kind of session, so an
allowed-tools
grant goes through the normal
permission flow
.
Claude Code sanitizes the display text the skill supplies, such as its description. It removes control characters, and in text that reaches Claude, such as the description, it also escapes angle brackets so the text can’t imitate Claude Code’s internal formatting.
​
How Claude Code handles the body of a synced skill
What Claude Code does with a synced skill’s body depends on where the session runs:
In a cloud session, the body keeps the behavior a local skill has, because the session runs in an isolated container.
In a Cowork session on your desktop, the body keeps the behavior a local skill has, except that Claude Code replaces every
!
command line with the
disableSkillShellExecution
placeholder
, as it does for every skill you supply there.
In any other session on your machine, Claude Code doesn’t run
!
commands
, doesn’t attach the files that
@
references name the way it does for a local skill, and doesn’t substitute the
${CLAUDE_PROJECT_DIR}
and
${CLAUDE_SESSION_ID}
placeholders, so the
@
references and both placeholders reach Claude as literal text. A
!
command line reaches Claude as literal text too, or as that placeholder when
disableSkillShellExecution
is on.
​
Remove a skill
How you remove a skill depends on where it came from:
Personal or project skill
: delete the skill’s directory,
~/.claude/skills/<skill-name>/
or
.claude/skills/<skill-name>/
. Claude Code
drops it from
/skills
in the current session
; content Claude Code already loaded from it follows the
skill content lifecycle
.
Enterprise skill
: an administrator deletes the skill’s directory from
.claude/skills/
inside the
managed settings directory
, for example
/etc/claude-code/.claude/skills/<skill-name>/
on Linux.
Plugin skill
: disable or uninstall the plugin that provides it, from the
/plugin
menu or with
/plugin uninstall <plugin-name>@<marketplace-name>
. Claude Code unloads the plugin’s skills after you run
/reload-plugins
or restart; see
Apply plugin changes without restarting
.
Skill synced from claude.ai
: turn the skill off for your claude.ai account, in the same place you
enabled it
. Claude Code removes it from
~/.claude/skills/synced/
the next time it
syncs your skills
. If you delete the directory by hand instead, the next sync downloads it again while the skill stays enabled on claude.ai.
Bundled skill
: set
disableBundledSkills
to
true
to turn off every bundled skill except
/doctor
, or set one skill to
"off"
in
skillOverrides
to hide it.
To keep a personal or project skill but stop Claude from invoking it on its own, set
disable-model-invocation: true
in its frontmatter, or
"user-invocable-only"
in
skillOverrides
when you don’t want to edit the file.
​
Configure skills
Skills are configured through YAML frontmatter at the top of
SKILL.md
and the markdown content that follows.
​
Types of skill content
Skill files can contain any instructions, but thinking about how you want to invoke them helps guide what to include:
Reference content
adds knowledge Claude applies to your current work. Conventions, patterns, style guides, domain knowledge. This content runs inline so Claude can use it alongside your conversation context.
---
name
:
api-conventions
description
:
API design patterns for this codebase
---
When writing API endpoints
:
-
Use RESTful naming conventions
-
Return consistent error formats
-
Include request validation
Task content
gives Claude step-by-step instructions for a specific action, like deployments, commits, or code generation. These are often actions you want to invoke directly with
/skill-name
rather than letting Claude decide when to run them. Add
disable-model-invocation: true
to prevent Claude from triggering it automatically. The example below adds
context: fork
, which runs the skill in its own subagent context; see
Run skills in a subagent
.
---
name
:
deploy
description
:
Deploy the application to production
context
:
fork
disable-model-invocation
:
true
---
Deploy the application
:
1. Run the test suite
2. Build the application
3. Push to the deployment target
Keep the body itself concise. Once a skill loads, its content
stays in context across turns
, so every line is a recurring token cost. State what to do rather than narrating how or why, and apply the same conciseness test you would for
CLAUDE.md content
.
​
Frontmatter reference
Beyond the markdown content, you can configure skill behavior using YAML frontmatter fields between
---
markers at the top of your
SKILL.md
file:
---
name
:
my-skill
description
:
What this skill does
disable-model-invocation
:
true
allowed-tools
:
Read Grep
---
Your skill instructions here...
All fields are optional. Only
description
is recommended so Claude knows when to use the skill.
Claude Code reads the frontmatter only when the opening
---
is the file’s first line. Otherwise it treats the whole file,
---
markers included, as skill content.
Boolean fields accept
yes
,
no
,
on
,
off
,
1
, and
0
in any letter case, in addition to
true
and
false
. Before v2.1.218, Claude Code recognized only
true
and
false
.
Field
Required
Description
name
No
Display name shown in skill listings. Defaults to the directory name. See
How a skill gets its command name
for how the field interacts with the name you type to invoke the skill.
description
Recommended
What the skill does and when to use it. Claude uses this to decide when to apply the skill. If omitted, uses the first paragraph of markdown content. Put the key use case first: the combined
description
and
when_to_use
text is truncated at 1,536 characters in the skill listing to reduce context usage.
when_to_use
No
Additional context for when Claude should invoke the skill, such as trigger phrases or example requests. Appended to
description
in the skill listing and counts toward the 1,536-character cap.
argument-hint
No
Hint shown during autocomplete to indicate expected arguments. Example:
[issue-number]
or
[filename] [format]
.
arguments
No
Named positional arguments for
$name
substitution
in the skill content. Accepts a space-separated string or a YAML list. Names map to argument positions in order.
disable-model-invocation
No
Set to
true
to prevent Claude from automatically loading this skill. Use for workflows you want to trigger manually with
/name
. Also prevents the skill from being
preloaded into subagents
. As of v2.1.196, also prevents the skill from running when a
scheduled task
fires with the skill as its prompt. Default:
false
.
user-invocable
No
Set to
false
when only Claude should invoke the skill: Claude Code hides it from the
/
menu and doesn’t run it when you type
/name
. Use for background knowledge users shouldn’t invoke directly. Default:
true
.
allowed-tools
No
Tools Claude can use without asking permission during the turn that invokes this skill. The grant clears when you send your next message. Accepts a space- or comma-separated string, or a YAML list. See
Pre-approve tools for a skill
.
disallowed-tools
No
Tools removed from Claude’s available pool while this skill is active. Use for autonomous skills that should never call certain tools, such as
AskUserQuestion
for a background loop. Accepts a space- or comma-separated string, or a YAML list. The restriction clears when you send your next message. Like deny rules, the field can’t remove
EndConversation
while any other tool remains.
model
No
Model to use when this skill is active. The override applies for the rest of the current turn and is not saved to settings; the session model resumes on your next prompt. Accepts the same values as
/model
, or
inherit
to keep the active model. A value excluded by your organization’s
availableModels
allowlist is not used and the session keeps its current model. With
context: fork
, the value sets the
forked subagent’s model
instead, and an excluded value follows the
same rules as a subagent model override
.
effort
No
Effort level
when this skill is active. Overrides the session effort level. Default: inherits from session. Options:
low
,
medium
,
high
,
xhigh
,
max
; available levels depend on the model.
context
No
Set to
fork
to run in a forked subagent context. See
Run skills in a subagent
.
agent
No
Which subagent type to use when
context: fork
is set.
background
No
Only applies with
context: fork
. Set to
false
to wait for the forked subagent’s result in the turn that invoked the skill, instead of
running it in the background
. Default:
true
. Requires Claude Code v2.1.218 or later.
hooks
No
Hooks that Claude Code registers when the skill is invoked and keeps running for the rest of the session. See
Hooks in skills and agents
for the configuration format and the
once
option.
paths
No
Glob patterns that limit when this skill is activated. Accepts a comma-separated string or a YAML list. When set, Claude loads the skill automatically only when working with files matching the patterns. Uses the same format as
path-specific rules
.
shell
No
Shell to use for
!`command`
and
```!
blocks in this skill. Accepts
bash
(default) or
powershell
. Setting
powershell
runs inline shell commands via PowerShell when the
PowerShell tool
is enabled: it’s on by default on Windows without Git Bash, on by default with Git Bash for claude.ai and Console accounts, and needs
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
in Amazon Bedrock, Google Cloud’s Agent Platform, and Microsoft Foundry sessions and on macOS, Linux, and WSL. Set it to
0
to turn the tool off.
metadata
No
Free-form YAML map for your own key-value data, such as entitlement or catalog fields, read by your own tooling from
SKILL.md
. Claude Code doesn’t act on its contents, and drops a value that isn’t a map. Don’t reuse frontmatter field names such as
paths
as keys.
license
No
License covering the skill. Part of the
Agent Skills
spec; see
Using skill frontmatter outside Claude Code
. Claude Code accepts the field but doesn’t act on it.
compatibility
No
Environment requirements for the skill, such as intended products or system prerequisites, as defined by the
Agent Skills
spec; see
Using skill frontmatter outside Claude Code
. Accepts a string of up to 500 characters. Claude Code accepts the field but doesn’t act on it.
​
Using skill frontmatter outside Claude Code
Claude Code accepts every field in the table above. Outside Claude Code, you can use only the fields in the
Agent Skills
spec:
Distribution path
Frontmatter fields you can use
Claude Code skills at
any level
, including
plugin
skills
Every field in the table above
claude.ai skill uploads, the Skills API, and packaging with
package_skill.py
from
anthropics/skills
name
,
description
,
license
,
compatibility
,
metadata
,
allowed-tools
When you enable a personal skill for
Cowork and cloud sessions
, including routines, you upload it to claude.ai, so the same rules apply.
If you include any field the spec doesn’t allow, packaging or upload fails with a hard error instead of ignoring the field:
Unexpected key(s) in SKILL.md frontmatter: argument-hint. Allowed properties are: allowed-tools, compatibility, description, license, metadata, name
Restricting frontmatter to the spec’s six fields avoids the unexpected-key error above. The
Agent Skills spec
and the
Skills API requirements
define everything else those paths validate. Claude Code-only body features, such as
dynamic context injection
, don’t function in claude.ai chat or through the API. Claude Code accepts all six fields, so frontmatter that follows the spec loads in Claude Code without changes.
​
How a skill gets its command name
The command you type to invoke a skill comes from where the skill file lives and, for plugin skills, also from the frontmatter
name
field. In a personal or project skill,
name
sets only the display label shown in skill listings, and the command still comes from the directory name. In a plugin skill,
name
sets the last segment of the command and the plugin prefix stays in place.
The table below shows where the command name comes from for each layout:
Skill location
Command name source
Example
Skill directory under
~/.claude/skills/
or
.claude/skills/
Directory name
.claude/skills/deploy-staging/SKILL.md
→
/deploy-staging
Nested
.claude/skills/
directory, when the name clashes with another skill
Subdirectory path relative to the working directory, then the skill directory name
apps/web/.claude/skills/deploy/SKILL.md
→
/apps/web:deploy
File under
.claude/commands/
File name without extension
.claude/commands/deploy.md
→
/deploy
Plugin
skills/
subdirectory
Frontmatter
name
or the directory name, namespaced by plugin
my-plugin/skills/review/SKILL.md
→
/my-plugin:review
, or
/my-plugin:fancy
with
name: fancy
Plugin root
SKILL.md
Frontmatter
name
, with the plugin directory name as a fallback
my-plugin/SKILL.md
with
name: review
→
/my-plugin:review
. See
Path behavior rules
In a plugin skill, the frontmatter
name
replaces the directory name in the last segment of the command, so
my-plugin/skills/review/SKILL.md
with
name: fancy
becomes
/my-plugin:fancy
. The bare
/fancy
also invokes the skill unless another command already uses that name. If the
name
you write already starts with the plugin’s own prefix, Claude Code doesn’t add the prefix again on v2.1.246 or later. For example,
name: my-plugin:fancy
still becomes
/my-plugin:fancy
. From v2.1.216 through v2.1.245, Claude Code doubled the prefix when the
name
already carried it.
In
non-interactive sessions
, Claude Code doesn’t reserve the names
help
and
feedback
for their terminal-only built-in commands, so a plugin skill with one of those names keeps its bare command there. Claude Code still reserves the name of every other terminal-only built-in, such as
/login
, even though the command can’t run in those sessions. In those sessions Claude Code also skips a synced skill named
help
or
feedback
, because it
skips a synced skill
whose name matches any built-in command whether or not that command can run. From v2.1.216 through v2.1.220,
help
and
feedback
were reserved too, so a plugin skill with one of those names was invocable only by its namespaced command in non-interactive sessions.
For a plugin-root
SKILL.md
, there is no skill directory to take the name from, so
name
supplies the whole final segment. Without a
name
field, Claude Code falls back to the plugin’s directory name.
​
Available string substitutions
Skills support string substitution for dynamic values in the skill content:
Variable
Description
$ARGUMENTS
All arguments passed when invoking the skill. When no placeholder receives an argument, Claude Code appends them as
ARGUMENTS: <value>
. See
Pass arguments to skills
.
$ARGUMENTS[N]
Access a specific argument by 0-based index, such as
$ARGUMENTS[0]
for the first argument.
$N
Shorthand for
$ARGUMENTS[N]
, such as
$0
for the first argument or
$1
for the second.
$name
Named argument declared in the
arguments
frontmatter list. Names map to positions in order, so with
arguments: [issue, branch]
the placeholder
$issue
expands to the first argument and
$branch
to the second.
${CLAUDE_SESSION_ID}
The current session ID. Useful for logging, creating session-specific files, or correlating skill output with sessions.
${CLAUDE_EFFORT}
The current effort level:
low
,
medium
,
high
,
xhigh
, or
max
. Ultracode is not a distinct level and reports as
xhigh
. Use this to adapt skill instructions to the active effort setting.
${CLAUDE_SKILL_DIR}
The directory containing the skill’s
SKILL.md
file. For plugin skills, this is the skill’s subdirectory within the plugin, not the plugin root. Use this in bash injection commands to reference scripts or files bundled with the skill, regardless of the current working directory.
${CLAUDE_PROJECT_DIR}
The project root directory. This is the same path
hooks
and MCP servers receive as
CLAUDE_PROJECT_DIR
. Use this to reference project-local scripts or files, such as
${CLAUDE_PROJECT_DIR}/.claude/hooks/helper.sh
, independent of where the skill is installed.
${CLAUDE_PLUGIN_ROOT}
The plugin’s installation directory. Substituted only in plugin skills. Use this to reference scripts or files bundled anywhere in the plugin, including resources shared between the plugin’s skills. See
plugin environment variables
.
${CLAUDE_PLUGIN_DATA}
The plugin’s
persistent data directory
, which survives plugin updates. Substituted only in plugin skills. Use this to reference installed dependencies, generated files, or caches that must outlive an update.
Claude Code substitutes
${CLAUDE_SKILL_DIR}
and
${CLAUDE_PROJECT_DIR}
in two places: the skill’s markdown content, and Bash rules in the
allowed-tools
frontmatter. In a plugin skill, Claude Code substitutes
${CLAUDE_PLUGIN_ROOT}
and
${CLAUDE_PLUGIN_DATA}
in the same two places. Using the same variable in both places lets a skill run a bundled script without a permission prompt. The following skill shows the pattern:
---
name
:
render-chart
description
:
Render a chart from a CSV file
allowed-tools
:
Bash(${CLAUDE_SKILL_DIR}/scripts/render.sh *)
---
Run `${CLAUDE_SKILL_DIR}/scripts/render.sh <csv-file>` to render the chart.
If this skill is installed at
~/.claude/skills/render-chart/
, both occurrences of
${CLAUDE_SKILL_DIR}
expand to that directory. The
allowed-tools
rule then matches the exact command the skill body tells Claude to run, so the script runs without prompting.
The
${CLAUDE_PROJECT_DIR}
substitution requires Claude Code v2.1.196 or later.
Indexed arguments use shell-style quoting, so wrap multi-word values in quotes to pass them as a single argument. For example,
/my-skill "hello world" second
makes
$0
expand to
hello world
and
$1
to
second
. The
$ARGUMENTS
placeholder always expands to the full argument string as typed.
An indexed placeholder with no corresponding argument, such as
$2
when only one argument was passed, stays in the content unchanged. A named placeholder from the
arguments
frontmatter with no matching argument expands to an empty string.
If you pass an argument value that itself contains text such as
$1
or
$ARGUMENTS
, Claude Code inserts it as literal text and doesn’t expand it. For example, if a skill’s body contains
Summarize $0
and you run
/summarize "$ARGUMENTS from yesterday"
, Claude receives
Summarize $ARGUMENTS from yesterday
. Claude Code still replaces
${CLAUDE_*}
variables such as
${CLAUDE_SKILL_DIR}
after it inserts the arguments.
To include a literal
$
before a digit,
ARGUMENTS
, or a declared argument name, such as
$1.00
in prose, escape it with a backslash:
\$1.00
. A backslash before any other
$
is left unchanged. Only a single backslash directly before the token escapes it. A doubled backslash such as
\\$1
leaves both backslashes in place, and
$1
still expands to the argument value. The backslash escape covers only these argument placeholders. A backslash doesn’t prevent substitution of a
${CLAUDE_*}
variable where the variable applies.
Example using substitutions:
---
name
:
session-logger
description
:
Log activity for this session
---
Log the following to logs/${CLAUDE_SESSION_ID}.log
:
$ARGUMENTS
​
Add supporting files
Skills can include multiple files in their directory. This keeps
SKILL.md
focused on the essentials while letting Claude access detailed reference material only when needed. Large reference docs, API specifications, or example collections don’t need to load into context every time the skill runs.
my-skill/
├── SKILL.md (required - overview and navigation)
├── reference.md (detailed API docs - loaded when needed)
├── examples.md (usage examples - loaded when needed)
└── scripts/
└── helper.py (utility script - executed, not loaded)
Reference supporting files from
SKILL.md
so Claude knows what each file contains and when to load it:
## Additional resources
-
For complete API details, see [
reference.md
](
reference.md
)
-
For usage examples, see [
examples.md
](
examples.md
)
Keep
SKILL.md
under 500 lines. Move detailed reference material to separate files.
​
Control who invokes a skill
By default, both you and Claude can invoke any skill. You can type
/skill-name
to invoke it directly, and Claude can load it automatically when relevant to your conversation. Two frontmatter fields let you restrict this:
disable-model-invocation: true
: Only you can invoke the skill. Use this for workflows with side effects or that you want to control timing, like
/commit
,
/deploy
, or
/send-slack-message
. You don’t want Claude deciding to deploy because your code looks ready.
user-invocable: false
: Only Claude can invoke the skill. Use this for background knowledge that isn’t actionable as a command. A
legacy-system-context
skill explains how an old system works. Claude should know this when relevant, but
/legacy-system-context
isn’t a meaningful action for users to take.
This example creates a deploy skill that only you can trigger. If you set
disable-model-invocation: true
, Claude can’t run the skill automatically:
---
name
:
deploy
description
:
Deploy the application to production
disable-model-invocation
:
true
---
Deploy $ARGUMENTS to production
:
1. Run the test suite
2. Build the application
3. Push to the deployment target
4. Verify the deployment succeeded
If Claude tries anyway, Claude Code blocks the call and instructs it not to reproduce the deploy steps another way, so expect Claude to suggest running
/deploy
yourself.
Here’s how the two fields affect invocation and context loading:
Frontmatter
You can invoke
Claude can invoke
When loaded into context
(default)
Yes
Yes
Description always in context, full skill loads when invoked
disable-model-invocation: true
Yes
No
Description not in context, full skill loads when you invoke
user-invocable: false
No
Yes
Description always in context, full skill loads when invoked
In a regular session, skill descriptions are loaded into context so Claude knows what’s available, but full skill content only loads when invoked.
Subagents with preloaded skills
work differently: the full skill content is injected at startup.
​
Skill content lifecycle
When you or Claude invoke a skill, the rendered
SKILL.md
content enters the conversation as a single message and stays there across later turns. This persistence applies to the skill’s instructions, not its permissions: an
allowed-tools
grant clears when you send your next message. Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps.
When Claude re-invokes a skill whose rendered content is identical to the copy already in context, Claude Code adds a short note that the skill is already loaded rather than a second copy of the content. When the rendered content differs, because the arguments changed or a
dynamic context
command produced new output, Claude Code appends the full content again.
Auto-compaction
carries invoked skills forward within a token budget. When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens. Claude Code fills this budget starting from the most recently invoked skill, so older skills can be dropped entirely after compaction if you have invoked many in one session.
If a skill seems to stop influencing behavior after the first response, the content is usually still present and the model is choosing other tools or approaches. Strengthen the skill’s
description
and instructions so the model keeps preferring it, or use
hooks
to enforce behavior deterministically. If the skill is large or you invoked several others after it, re-invoke it after compaction to restore the full content.
​
Pre-approve tools for a skill
The
allowed-tools
field grants permission for the listed tools during the turn that invokes the skill, so Claude can use them without prompting you for approval. The grant clears when you send your next message, even though the skill content
stays in context
; invoking the skill again re-applies it for that turn. It does not restrict which tools are available: every tool remains callable, and your
permission settings
still govern tools that are not listed. To pre-approve tools for the whole session rather than a single turn, add allow rules to those permission settings instead.
Workspace trust doesn’t gate this field. Claude Code applies a project skill’s
allowed-tools
whenever you or Claude invoke the skill, including in a
-p
run in a folder you’ve never trusted. A skill can grant itself broad tool access, so review the
allowed-tools
of skills checked into a repository before you run Claude Code there.
This skill lets Claude run git commands without per-use approval whenever you invoke it:
---
name
:
commit
description
:
Stage and commit the current changes
disable-model-invocation
:
true
allowed-tools
:
Bash(git add *) Bash(git commit *) Bash(git status *)
---
To remove tools from Claude’s available pool while a skill is active, list them in
disallowed-tools
in the skill’s frontmatter. The restriction clears when you send your next message. Like deny rules, the field can’t remove
EndConversation
while any other tool remains. To block tools across all skills and prompts, add deny rules in your
permission settings
.
​
Pass arguments to skills
Both you and Claude can pass arguments when invoking a skill. Arguments are available via the
$ARGUMENTS
placeholder.
This skill fixes a GitHub issue by number. The
$ARGUMENTS
placeholder gets replaced with whatever follows the skill name:
---
name
:
fix-issue
description
:
Fix a GitHub issue
disable-model-invocation
:
true
---
Fix GitHub issue $ARGUMENTS following our coding standards.
1. Read the issue description
2. Understand the requirements
3. Implement the fix
4. Write tests
5. Create a commit
When you run
/fix-issue 123
, Claude receives “Fix GitHub issue 123 following our coding standards…”
If you invoke a skill with arguments but no placeholder in the skill’s content receives one, Claude Code appends
ARGUMENTS: <your input>
to the end of the skill content so Claude still sees what you typed. A placeholder is
$ARGUMENTS
, an indexed form such as
$1
, or a named argument. An indexed placeholder with no argument at its position stays as literal text and doesn’t count as receiving one. A named placeholder counts even when its position has no argument, because it expands to an empty string.
You can also stack several skills at the start of one message. Typing
/write-tests /fix-issue 123
loads both skills and passes the trailing text
123
as
$ARGUMENTS
to each of them. Before v2.1.199, only the first skill loaded and received
/fix-issue 123
as literal argument text.
Claude Code expands the first skill plus up to five more stacked after it. Expansion stops at the first token that isn’t an inline user-invocable skill, so a skill that runs as a
forked subagent
, such as
/code-review
, or one whose arguments may themselves start with a slash command, such as
/loop
, also ends the run there. That token and everything after it become the argument text for every expanded skill.
/code-review
runs as a forked subagent from v2.1.218; on earlier versions it ran inline and stacked.
To access individual arguments by position, use
$ARGUMENTS[N]
or the shorter
$N
:
---
name
:
migrate-component
description
:
Migrate a component from one language to another
---
Migrate the $ARGUMENTS[0] component from $ARGUMENTS[1] to $ARGUMENTS[2].
Preserve all existing behavior and tests.
Running
/migrate-component SearchBar JavaScript TypeScript
replaces
$ARGUMENTS[0]
with
SearchBar
,
$ARGUMENTS[1]
with
JavaScript
, and
$ARGUMENTS[2]
with
TypeScript
. The same skill using the
$N
shorthand:
---
name
:
migrate-component
description
:
Migrate a component from one language to another
---
Migrate the $0 component from $1 to $2.
Preserve all existing behavior and tests.
​
Advanced patterns
​
Inject dynamic context
The
!`<command>`
syntax runs shell commands before the skill content is sent to Claude. The command output replaces the placeholder, so Claude receives actual data, not the command itself. Claude Code doesn’t run these commands on your machine when the skill is
synced from your claude.ai account
.
This skill summarizes a pull request by fetching live PR data with the GitHub CLI. The
!`gh pr diff`
and other commands run first, and their output gets inserted into the prompt:
---
name
:
pr-summary
description
:
Summarize changes in a pull request
context
:
fork
agent
:
Explore
allowed-tools
:
Bash(gh *)
---
## Pull request context
-
PR diff
:
!`gh
pr diff`
-
PR comments
:
!`gh
pr view --comments`
-
Changed files
:
!`gh
pr diff --name-only`
## Your task
Summarize this pull request...
Substitution runs once over the original file. Command output is inserted as plain text and is not re-scanned for further
!`<command>`
placeholders, so a command cannot emit a placeholder for a later pass to expand.
The inline form is only recognized when
!
appears at the start of a line or immediately after whitespace. If
!
follows another character, as in
KEY=!`cmd`
, the placeholder is left as literal text and the command does not run.
For multi-line commands, use a fenced code block opened with
```!
instead of the inline form:
## Environment
```!
node --version
git status --short
```
To disable this behavior for skills and custom commands from user, project, plugin, or
additional-directory
sources, set
"disableSkillShellExecution": true
in
settings
. Each command is replaced with
[shell command execution disabled by policy]
instead of being run. Bundled and managed skills are not affected. This setting is most useful in
managed settings
, where users cannot override it.
Claude Code never runs these commands on your machine when they appear in skills
synced from your claude.ai account
, regardless of this setting.
How Claude Code handles the body of a synced skill
says what Claude receives in place of the command in each kind of session.
To request deeper reasoning when

## Source (settings): https://docs.claude.com/en/docs/claude-code/settings

Claude Code settings - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
This page covers Claude Code running on your machine: the terminal, the
VS Code
and
JetBrains
extensions, and the
desktop app
, which all read the same settings files. A cloud session on
Claude Code on the web
runs on a different machine and reads only some of them; see
Settings in cloud sessions
.
Settings are the JSON keys that change how Claude Code behaves: which model it starts with, what it can run without asking, which files it can’t read, how it looks in your terminal, and what your organization enforces.
Claude Code reads settings from JSON settings files such as
~/.claude/settings.json
. It looks for them in a few locations, and
the file it reads a setting from decides who the setting applies to
.
Use this page to pick the settings file that reaches the people you want a setting to apply to, change a setting and confirm it applied, and see which value Claude Code uses when the same key is set in more than one file.
The
settings reference
lists every key you can set, with the file you set it in, its type, and its default.
Configure permissions
covers what Claude Code can run without asking and how to write
allow
,
ask
, and
deny
rules.
​
Settings files and who they affect
Claude Code reads settings from four files, and an organization can also deliver managed settings from the claude.ai console. Each source has a scope: the set of people and projects a setting saved in it applies to, whether that’s just you, everyone in a project, or everyone in your organization.
Scope
File
Who it affects
Use it for
User
~/.claude/settings.json
You, in every project on this machine
Personal preferences: theme, editor mode, default model, your own permission rules
Shared project
.claude/settings.json
Everyone working in the folder that contains it. In a git repository, commit it so teammates get it
Team permissions, hooks, plugins, and the environment variables the project needs
Project local
.claude/settings.local.json
You, in this one project only. Claude Code keeps it out of git when it creates the file; if you create it by hand, add it to
.gitignore
yourself
Personal overrides for one project, and testing before you share
Managed
managed-settings.json
and other
managed sources
Everyone your organization deploys it to; nothing you set overrides it, apart from a few
security-sensitive exceptions
Security policy and compliance requirements
In the File column,
~/.claude
is the
.claude
folder in your home directory, and a bare
.claude
is the
.claude
folder inside your project.
​
Compare the scope of each settings file
Suppose you have three projects on your machine,
website/
,
api/
, and
acme-app/
, a teammate has their own clone of
acme-app/
, and you start a
cloud session
on
acme-app/
.
The graphic below shows which of those folders a setting applies in when you start Claude Code from them. Click a settings file to see the folders it reaches.
~/.claude/settings.json
: every project on your machine, and nothing on your teammate’s or in the cloud session
acme-app/.claude/settings.json
: your
acme-app/
. It reaches your teammate’s clone and the cloud session only if you commit the file to version control; until you do, it’s a file on your disk like any other and nobody else has it
acme-app/.claude/settings.local.json
: your
acme-app/
only. Claude Code adds it to your global git excludes the first time it writes the file, so it stays out of your commits; if you create the file by hand,
add it to
.gitignore
yourself
Managed settings
, whether a
managed-settings.json
file, an MDM policy, or
server-managed settings
from the claude.ai console: every project on every machine your organization deploys it to, or that you sign in to with your organization account. Only server-managed settings reach the cloud session
​
Find or create your settings files
Installing Claude Code doesn’t create any settings file. If your machine or project already has one, it came from one of these sources:
Managed
: your organization deploys it. You don’t create or edit it.
Shared project
: a project that already uses Claude Code may have one committed. If not, create it at
.claude/settings.json
in the project folder.
User
and
Project local
: create them yourself, or let Claude Code create them. It writes
~/.claude/settings.json
the first time you change an option in the
/config
menu that it stores in user settings, such as the theme, and
.claude/settings.local.json
the first time you give a standing approval on a permission prompt, such as “Yes, and don’t ask again” for a Bash command. A few
/config
options, including
Show tips
, save to
.claude/settings.local.json
instead of the user file.
On Windows,
~/.claude
means
%USERPROFILE%\.claude
. To keep the home-directory files somewhere else, set
CLAUDE_CONFIG_DIR
; Claude Code then stores your settings, session history, and plugins there instead.
Claude Code also keeps a fifth file,
~/.claude.json
, that it writes for itself; you don’t need to edit it. It holds your sign-in session,
MCP server
configurations, per-project state such as trust decisions, and the
global config keys
that
/config
writes for you.
​
Share settings with your team
Commit
.claude/settings.json
so everyone who clones the repository gets the same permissions, hooks, telemetry, and plugins. Each teammate can still override it for themselves in their own
.claude/settings.local.json
, so personal exceptions don’t need a commit. For a complete team file, see
a team’s shared settings
.
Some of what you commit waits until each teammate
trusts the folder
, and a few keys never take effect from a repository file;
Troubleshoot a setting that doesn’t apply
covers both.
​
Keep personal settings out of a repository
To change a setting for yourself in one project without changing it for your teammates, save it in
.claude/settings.local.json
inside the project. Claude Code applies that file over the committed
.claude/settings.json
, so if your team’s file sets
"model": "claude-sonnet-5"
and you want Opus, put
"model": "claude-opus-4-8"
in your local file and only your sessions change.
Three things to know about the local file:
Claude Code writes it too.
When Claude asks permission to run a Bash command and you choose “Yes, and don’t ask again”, Claude Code saves that
permission approval
here as an
allow
rule.
You don’t need to gitignore it yourself, unless you created it by hand.
The first time Claude Code writes the file in a git repository that doesn’t already ignore it, it adds
**/.claude/settings.local.json
to your global git excludes file, so the file stays out of your commits in every repository. That file is
core.excludesFile
when your global git config sets it to an absolute or
~
-prefixed path; otherwise it’s
$XDG_CONFIG_HOME/git/ignore
, or
~/.config/git/ignore
when
XDG_CONFIG_HOME
is unset. If you created the file by hand and Claude Code hasn’t written to it yet, add it to
.gitignore
yourself.
Its allow rules don’t wait for trust while the file stays untracked.
Because the file is yours and not the repository’s, Claude Code applies its
allow
rules without the
workspace trust
step it requires for the committed file. If the file is tracked by git, the trust step applies to it too; see
When your local settings file needs trust
.
​
Where Claude Code keeps the local file in a git repository
When Claude asks permission to run a Bash command and you choose “Yes, and don’t ask again”, Claude Code saves that approval as an
allow
rule in
.claude/settings.local.json
. If you start Claude Code in a subdirectory of a git repository, it reads and writes that file at the repository root and applies the approval across the whole repository. In a
worktree
, it uses the file at the main checkout’s root.
Two rules qualify the root location:
When the file stays with
.claude/settings.json
instead
: outside a git repository, when the repository root is your home directory, on Windows, or when the repository root or its
.git
or
.claude
entry isn’t owned by your user.
Paths in the file don’t anchor at the repository root
: a permission rule that starts with
/
or a relative sandbox path
anchors at the session’s primary working directory
instead.
Before v2.1.211, Claude Code kept the file in the starting directory. It still reads a file an earlier version left there alongside the root file; where both set the same key, the root’s value applies, and permission rules from both files apply. The Agent SDK’s
resolveSettings()
helper always reads the file from the starting directory.
Claude Code reads the shared
.claude/settings.json
from the session’s
primary working directory
, so to use a file committed at the repository root, start Claude Code there. After you
move the session with
/cd
, Claude Code reads both project files from the new directory instead, placing the local file by the same rules. Reading them from the directory you moved to requires Claude Code v2.1.246 or later.
​
Check what your organization enforces
If your organization manages Claude Code, some settings are decided for you and nothing you put in your own files changes them. To see which, run
/status
: the
Setting sources
line names the managed source that applies to you. Managed settings apply wherever Claude Code runs on this machine;
What a developer can change
covers local admin rights and tools other than Claude Code.
Managed settings reach you through the
delivery mechanisms
on the managed settings page, most commonly:
Server-managed settings
, which Claude Code fetches from the claude.ai admin console or a self-hosted
Claude apps gateway
MDM or OS-level policies, and
managed-settings.json
files in a system directory
An embedding host such as Claude Desktop, through the SDK
managedSettings
option; see
Control policy from an embedding host
In a
Cowork
session that runs on your machine in the Claude Desktop app, Claude Code doesn’t fetch server-managed settings from the claude.ai admin console, and it reads policy deployed to your device unless your organization’s Claude Desktop configuration sets
requireCoworkFullVmSandbox
.
Where and when a policy applies
covers Cowork and cloud sessions.
If you’re the administrator,
Set up Claude Code for your organization
walks through choosing what to enforce, and
Deploy managed settings
covers delivery and how to confirm a policy is in force.
​
Change a setting
You can change a setting from the
/config
menu, by editing a settings file, or for one session from the command line.
Claude Code’s system prompt isn’t published. To give Claude standing instructions, use
CLAUDE.md
files
or the
--append-system-prompt
flag.
​
Use the /config menu
Run
/config
inside Claude Code and open the
Config
tab. It lists a short set of personal options such as theme, editor mode, and verbose output, not every settings key. Select an option to change it; Claude Code saves it for you:
Most options
:
~/.claude/settings.json
A few options, such as Show tips
:
.claude/settings.local.json
The
global config options
:
~/.claude.json
To set one option without the menu, pass
key=value
, such as
/config verbose=true
.
/config
is part of the terminal interface. The
VS Code
chat panel and the
desktop app
don’t open it; change settings there by editing a settings file or through those apps’ own settings.
​
Edit a settings file
Open the settings file for the scope you want in your editor and add or change a key. Settings files are strict JSON: a
//
comment or a trailing comma is a syntax error, and Claude Code reports the file as a
Settings Error
at the next start. For example, to let Claude Code run your lint and test commands without asking and stop it reading
.env
files, add this to
~/.claude/settings.json
:
~/.claude/settings.json
{
"$schema"
:
"https://json.schemastore.org/claude-code-settings.json"
,
"permissions"
: {
"allow"
: [
"Bash(npm run lint)"
,
"Bash(npm run test *)"
],
"deny"
: [
"Read(./.env)"
,
"Read(./.env.*)"
]
}
}
Each entry under
permissions
is a rule that names a tool and what it may do;
Configure permissions
explains the syntax. The
$schema
line points to the
published JSON schema
for Claude Code settings, which gives you autocomplete and inline validation in VS Code, Cursor, and any other editor that supports JSON schema. The schema can lag behind the newest CLI releases, so a validation warning on a recently documented key doesn’t mean your configuration is invalid.
After you save, run
/status
inside Claude Code to confirm the file loaded;
Confirm what loaded
says what the
Setting sources
line shows and how a broken file is reported.
For a complete personal file, team file, and organization file, each shown with a comment on every key it sets, see the
example settings files
.
​
Change a setting for one session
To try a value without saving it, set it when you start Claude Code. The value applies to that session and your settings files stay as they were. You have three ways to do it:
--settings
: pass a key as JSON, inline or as a path to a file. Claude Code applies it above your user, project, and local files and below managed settings. It can set any key your user settings file can set; it can’t set
Managed
or
Global config
keys.
A flag for that key
: some keys have their own flag, such as
--model
for
model
and
--effort
for
effortLevel
.
An environment variable
: export the key’s paired variable before you run
claude
, such as
ANTHROPIC_MODEL
for
model
.
Each key’s entry on the
settings reference
lists its per-session overrides and which one takes precedence, so check the entry for the key you want to change.
Commands you run inside a session mostly save your choice:
/config
writes to your settings files, and
/model
and
/effort
save the value as your default for new sessions. Pressing
s
in the
/model
picker switches the model without saving it, and some
/effort
levels, such as
max
and
ultracode
, apply to the current session only; see
Adjust effort level
.
For example, to start one session on Opus without changing your default:
claude
--settings
'{"model": "claude-opus-4-8"}'
​
When edits take effect
Claude Code watches your settings files and reloads them when they change, so it applies most edits to the running session without a restart, including edits to
permissions
,
hooks
, and credential helpers such as
apiKeyHelper
. The reload covers user, project, local, and managed settings, and Claude Code runs the
ConfigChange
hook
for each settings-file change it detects, not for managed settings that arrive from MDM or the claude.ai console. Managed settings that arrive through MDM or from the claude.ai console reach a running session on a schedule rather than on save; the
delivery table
gives it per source.
Claude Code reads some keys only once, at session start, so an edit to one of them doesn’t reach the running session. Admin-side keys that also wait for a restart, such as
requiredMinimumVersion
, are listed under
where and when a policy applies
. The ones you’re most likely to edit mid-session:
model
: use
/model
to switch mid-session. Each model has its own prompt cache, so the first request after a switch re-reads the whole conversation uncached; see
Switching models
effortLevel
: use
/effort
to change it mid-session
outputStyle
: part of the system prompt, so Claude Code applies the edit after
/clear
or a restart
​
Confirm what loaded
Run
/status
inside Claude Code to see which settings sources are active. The
Status
tab includes a
Setting sources
line that lists each settings file Claude Code loaded for the current session, such as
User settings
or
Project local settings
. When
managed settings
are in effect, the managed settings entry shows in parentheses how they reached your machine.
The line confirms which files Claude Code read; it doesn’t show which file supplied each key. To list entries Claude Code rejected, run
claude doctor
; for a model that project or managed settings set, the startup header names the file that set it.
/status
and
/config
open the same dialog on different tabs, and the
Config
tab isn’t a view of your
settings.json
contents.
​
Fix a broken settings file
If you mistype JSON or set a key to a value Claude Code doesn’t accept, Claude Code tells you at the start of an interactive session. What it shows depends on how much of the file is affected:
Settings Error
: a user, project, or local file has invalid JSON or a value the schema rejects. At the start of an interactive session Claude Code shows a dialog that lets you fix the file with Claude’s help, exit, or continue without the broken settings.
Settings Warning
: only individual entries fail, such as a malformed permission rule or an unknown hook event name. Claude Code skips those values and keeps the rest of the file in effect.
Managed settings
: Claude Code keeps enforcing the rest of the file.
Invalid entries in managed settings
says what it drops and which keys fall back to a stricter value until you fix them.
Configuration error
:
~/.claude.json
can’t be parsed. Claude Code copies the broken file to
~/.claude/backups/.claude.json.corrupted.<timestamp>
and asks whether to exit and fix it by hand or reset to the default configuration; a
-p
run prints the error and exits. To recover your previous state, copy back one of the five most recent
.claude.json.backup.<timestamp>
files in
~/.claude/backups/
, which Claude Code saves before it writes the file.
After you continue, run
/status
to see the affected files and
claude doctor
for the details of each error.
A
-p
run shows no dialog: Claude Code skips the broken file or values and continues with the rest, so after a
-p
run that ignores a setting, run
claude doctor
to see what it dropped.
​
Settings precedence
When the same key appears in more than one place, Claude Code uses the value from the highest level that sets it. The stack below shows the levels, highest on top; a key at a higher level overrides the same key anywhere below it.
In order, highest precedence first:
Managed settings
: settings your organization deploys, by a
managed-settings.json
file, an MDM policy, or
server-managed settings
from the claude.ai console. Nothing you set overrides them: a key you pass with
--settings
doesn’t override the same managed key, and a flag such as
--model
picks only from the models your organization allows. A managed
model
sets the model each session starts with, and you can still switch with
/model
; the lock is
availableModels
, which constrains
/model
,
--model
, and the
model
key in your own files. When your organization delivers more than one managed source, the rules for
precedence within the managed tier
say what Claude Code reads from each.
Command line arguments
: flags you pass when you start
claude
from a terminal, for one session; see
Change a setting for one session
. Claude Code merges JSON you pass with
--settings <file-or-json>
with your settings files by the same rules as the other levels: it takes a key you set here over the same key in local, project, or user settings, and keeps the lower-level value for a key you omit.
Project local settings
(
.claude/settings.local.json
): your personal settings for this project.
Shared project settings
(
.claude/settings.json
): settings your team checks into source control.
User settings
(
~/.claude/settings.json
): your personal settings for every project.
Environment variables aren’t a level in this stack. When a behavior has both a shell variable and a settings key, which one applies is decided per pair, not by level:
ANTHROPIC_MODEL
exported in your shell applies over the
model
key from any file, while
ANTHROPIC_DEFAULT_MODEL
applies only when no file sets
model
. The
environment variables reference
says which keys have a pair and which one Claude Code reads first. An
env
block inside a settings file is an ordinary key and follows the levels above.
For a few security-sensitive keys, Claude Code honors a stricter value from a lower level over a managed value;
Exceptions to managed settings precedence
lists them.
​
Lists merge instead of overriding
When you set the same list key, such as
permissions.allow
, in more than one file, Claude Code combines the lists instead of picking one, so each file can add entries without removing another file’s. Three keys that hold model lists follow their own rules:
fallbackModel
is an ordered chain where position carries meaning, so Claude Code takes the whole value from the highest-precedence file that defines it.
modelPicker
holds one ordered list of rows plus a replace flag, so Claude Code never merges rows from two sources. It takes the whole value from the highest of managed settings,
--settings
, and user settings that defines it, and ignores the key in project and local settings. Requires Claude Code v2.1.242 or later.
availableModels
: when the managed settings Claude Code applies define it, Claude Code applies that list as-is and ignores entries you add in user, project, or local settings, unless an app that embeds Claude Code supplies its own model list; see
Exceptions to managed settings precedence
. Across managed sources the list never merges either;
how Claude Code combines managed sources
says which source’s list applies. Across non-managed scopes Claude Code merges the arrays as usual.
​
Precedence examples
While Claude works, Claude Code shows a one-line tip under the spinner, such as “Use /config to change your default permission mode (including Plan Mode)”. Suppose you want those tips off, so you set
spinnerTipsEnabled
to
false
in
~/.claude/settings.json
. Each scenario below is something that can turn them back on, and what you can do about it.
​
Team settings override personal settings
Your team’s
.claude/settings.json
sets it to
true
. Claude Code uses the project value because shared project sits above user, so you see tips in that project and nowhere else.
You can get your value back: add
"spinnerTipsEnabled": false
to
.claude/settings.local.json
in that project. Project local sits above shared project, so your sessions there stop showing tips and your teammates’ sessions don’t change.
​
Organization settings override everything
Your organization’s managed settings set it to
true
. Nothing you put in user, project, or local settings turns tips off, and neither does
--settings
. Managed is the top level.
You can’t get your value back. Run
/status
to see which managed source applies, and ask your administrator if the policy should change.
​
The command line overrides your files for one session
You started the session with
claude --settings '{"spinnerTipsEnabled": true}'
. Command line sits above every file except managed, so that session shows tips even though your files say
false
.
You get your value back on the next session;
--settings
lasts one session and doesn’t write to any file.
​
A flag or environment variable sets the same thing
Some keys have a command line flag or an environment variable that overrides the settings value regardless of which file set it:
ANTHROPIC_MODEL
overrides the
model
setting, and
--model
overrides both for a session.
Whether you can get your value back depends on the key: unset the variable or drop the flag, and check the key’s entry on the
settings reference
and the variable’s row on the
environment variables reference
for which one Claude Code uses.
​
Troubleshoot a setting that doesn’t apply
When you set a key and Claude Code doesn’t behave as if you had, start with
/status
to see which files it loaded, then find your symptom below.
Debug your configuration
covers the wider checks, including a clean-configuration test.
​
A value you set is ignored
Something else is setting the same key, or the file didn’t load:
A higher level sets it.
Another settings file, a
--settings
flag, or a managed source sets the key above yours; the
stack
says which. A flag or environment variable can also override the key on its own, decided key by key; the key’s entry on the
settings reference
says which one Claude Code uses, and the
env
entry
covers a managed
env
value versus a shell export.
A security key keeps its strict value.
For a few keys Claude Code honors the restrictive value from any file, so a project
true
for
disableClaudeAiConnectors
stays on; see
Exceptions to managed settings precedence
.
The file is broken.
Invalid JSON or a rejected value makes Claude Code skip the file or the entry; see
Fix a broken settings file
.
​
A managed change hasn’t reached you
Managed sources reach a running session on the schedule in the
delivery table
, so restart the session first. If
/status
then names a different source than the one your administrator changed, a higher-priority source applies;
How Claude Code combines managed sources
gives the order.
​
A committed key doesn’t reach teammates
Two things keep a key in
.claude/settings.json
from applying for everyone who clones it:
Claude Code ignores the key in a repository file.
Look for
User, local, or managed
,
User or managed
,
Managed
, or
Global config
in the Scope column of the
All settings
index; those keys never apply from the shared file, apart from
autoContinueAtUsageLimit
, which a repository file can still switch off: while the file sets the key and no user,
--settings
, or managed value does, Claude Code reads the setting as off.
Global config
keys apply only from
~/.claude.json
.
The key waits for trust.
permissions.allow
rules,
permissions.additionalDirectories
,
extraKnownMarketplaces
, and most
env
values apply only after each teammate
trusts the folder
. Until then they still see prompts and don’t get plugins from a marketplace the file declares.
deny
and
ask
rules apply right away.
​
Permission rules combine differently than you expected
You chose “Yes, and don’t ask again” on a permission prompt but still get prompted for the same tool.
That choice saved an
allow
rule to your local file, and an
allow
rule there doesn’t outrank an
ask
rule from a project or managed file;
how permission rules combine
explains the order. In the VS Code extension the approval card lets you pick the destination file, including the project’s shared file, which changes the rule for everyone; in the CLI, Claude Code writes only to your local file.
Your organization’s allow rules still apply alongside yours.
That’s expected: Claude Code merges
permissions.allow
across scopes, unless your organization sets
allowManagedPermissionRulesOnly
.
​
Exceptions to managed settings precedence
For a few security-sensitive keys, Claude Code honors a restrictive value from a scope that otherwise couldn’t override managed settings. Find the key in this table to see which value it honors and from where.
Key
Value Claude Code honors
Notes
disableClaudeAiConnectors
true
from any scope
Honored even when a managed source sets
false
enableArtifact
false
from any scope, and
disableArtifact: true
from any scope
Honored even when a managed source sets
true
; nothing turns the
Artifact tool
back on. Requires Claude Code v2.1.242 or later
isolatePeerMachines
true
from any scope
Honored even when a managed source sets
false
remoteControlAtStartup
false
from
.claude/settings.json
or
.claude/settings.local.json
Honored even when a managed source sets
true
; a project or local
true
is ignored
crossSessionInbound
A stricter value from
.claude/settings.json
or
.claude/settings.local.json
, on the
accept
<
hold
<
refuse
ladder
Honored over managed,
--settings
, and user values; a project or local value that isn’t stricter is ignored
useAutoModeDuringPlan
false
from any managed source,
--settings
,
~/.claude/settings.json
, or
.claude/settings.local.json
Honored even when the winning managed source sets
true
; a
false
in
.claude/settings.json
is ignored
syncClaudeAiSkills
false
from any managed source,
--settings
,
~/.claude/settings.json
, or
.claude/settings.local.json
Honored even when the winning managed source sets
true
; a
false
in
.claude/settings.json
is ignored
An app that runs Claude Code inside itself and sets
CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST
is also an exception. Claude Code takes that app’s model configuration over the
model
,
fallbackModel
, and
modelOverrides
keys from every managed source, and over the model-selection variables in a managed
env
block, such as
ANTHROPIC_MODEL
and the
ANTHROPIC_DEFAULT_*_MODEL
family. Claude Code keeps a managed
availableModels
allowlist in force unless the app supplies its own.
​
Settings in cloud sessions
A cloud session, on
Claude Code on the web
or from
claude --cloud
, runs in a
cloud environment
on a fresh clone of your repository, not on your machine. That changes which settings reach it:
Shared project settings
(
.claude/settings.json
): read, because the file is part of the clone. Commit a setting there to apply it in cloud sessions.
User and project local settings
(
~/.claude/settings.json
and
.claude/settings.local.json
): not read. Both stay on your machine, and the local file isn’t in the clone.
Managed settings
: only
server-managed settings
reach a cloud session; a
managed-settings.json
file or MDM profile on your device doesn’t. A
self-hosted environment
also reads the managed settings file in its runner image.
How Claude Code combines managed sources
says when that file applies.
/config
: on the web, opens the Claude Code section of your claude.ai settings instead of changing a value. To change a setting for a cloud session, set an
environment variable
on the environment or commit the key to the repository’s
.claude/settings.json
.
What carries over from your setup
lists the rest:
CLAUDE.md
, skills, MCP servers, plugins, and credentials.
​
What’s next
Settings reference
: every key, with where you set it and an example
Example settings files
: a personal file, a team file, and an organization’s managed file
Configure permissions
: allow, ask, and deny rules, and what Claude Code runs without asking
Environment variables
: the variables Claude Code reads and the
env
block
Debug your configuration
: when a setting doesn’t apply
Claude directory reference
: every file Claude Code reads, including subagents, MCP servers, plugins, and
CLAUDE.md
Was this page helpful?
Yes
No
Assistant
Responses are generated using AI and may contain mistakes.

## Source (subagents): https://docs.claude.com/en/docs/claude-code/sub-agents

Create custom subagents - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Subagents are specialized AI assistants that handle specific types of tasks. Use one when a side task would flood your main conversation with search results, logs, or file contents you won’t reference again: the subagent does that work in its own context and returns only the summary. Define a custom subagent when you keep spawning the same kind of worker with the same instructions.
Each subagent runs in its own context window with a custom system prompt, specific tool access, and independent permissions. When Claude encounters a task that matches a subagent’s description, it delegates to that subagent, which works independently and returns results. To see the context savings in practice, the
context window visualization
walks through a session where a subagent handles research in its own separate window.
Subagents work within a single session. To run many independent sessions in parallel and monitor them from one place, see
background agents
. For separate sessions that pass messages to each other, see
cross-session messaging
. For a coordinated team of sessions Claude spawns and supervises, see
agent teams
.
Subagents help you:
Preserve context
by keeping exploration and implementation out of your main conversation
Enforce constraints
by limiting which tools a subagent can use
Reuse configurations
across projects with user-level subagents
Specialize behavior
with focused system prompts for specific domains
Control costs
by routing tasks to faster, cheaper models like Haiku
Claude uses each subagent’s description to decide when to delegate tasks. When you create a subagent, write a clear description so Claude knows when to use it.
Those descriptions take up context, so keep them short. When the combined descriptions of your subagents, except the built-in ones, exceed 15,000 tokens, Claude Code shows a
warning at startup with the total token count
. Trim the
description
fields of your subagents, and move detail into each subagent’s system prompt, which only loads when that subagent runs.
​
Built-in subagents
Claude Code includes built-in subagents that Claude automatically uses when appropriate. Each inherits the parent conversation’s permissions; most run with a restricted tool set.
Explore and Plan skip your CLAUDE.md files and the parent session’s git status to keep research fast and inexpensive. Every other built-in and
custom subagent
loads both. For the full breakdown of what reaches a subagent, see
what loads at startup
.
Explore
Plan
General-purpose
Other
A fast, read-only agent optimized for searching and analyzing codebases.
Model
: inherits from the main conversation, capped at Opus on the Claude API, so Explore never runs on a more expensive model than the one you already chose for the session
Tools
: read-only tools; Write and Edit are denied
Purpose
: file discovery, code search, codebase exploration
As of v2.1.198, Explore inherits the main conversation’s model instead of always running on Haiku. On the Claude API, the inherited model is capped at Opus: a main conversation on a higher tier runs Explore on Opus, and a main conversation on Sonnet or Haiku runs Explore on that same model. On any other provider, such as
Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, or Claude Platform on AWS
, Explore inherits the main conversation’s model directly.
A
user or project subagent
named
Explore
overrides the built-in and keeps its own
model
field, so define one with
model: haiku
to keep exploration on a lower-cost model.
Claude delegates to Explore when it needs to search or understand a codebase without making changes. This keeps exploration results out of your main conversation context.
When invoking Explore, Claude specifies a thoroughness level:
quick
for targeted lookups,
medium
for balanced exploration, or
very thorough
for comprehensive analysis.
A research agent used during
plan mode
to gather context before presenting a plan.
Model
: inherits from the main conversation
Tools
: read-only tools; Write and Edit are denied
Purpose
: codebase research for planning
When you’re in plan mode and Claude needs to understand your codebase, it delegates research to the Plan subagent so that exploration output stays in a separate context window while the main conversation remains read-only.
A capable agent for complex, multi-step tasks that require both exploration and action.
Model
: inherits from the main conversation
Tools
: every tool
available to subagents
Purpose
: complex research, multi-step operations, code modifications
Claude delegates to general-purpose when the task requires both exploration and modification, complex reasoning to interpret results, or multiple dependent steps.
Claude Code includes additional helper agents for specific tasks. These are typically invoked automatically, so you don’t need to use them directly.
Agent
Model
When Claude uses it
claude
Inherits
When a task doesn’t fit a more specialized agent. A catch-all with every tool
available to subagents
. Also the default agent for a dispatched
background session
;
which permission mode it starts in
depends on how the session was started
statusline-setup
Sonnet
When you run
/statusline
to configure your status line
claude-code-guide
Haiku
When you ask questions about Claude Code features
Built-in subagents are registered by default in interactive sessions. To restrict them:
To block a specific built-in type, add it to
permissions.deny
as shown in
Disable specific subagents
.
To prevent Claude from delegating to any subagent, deny the
Agent
tool itself with
permissions.deny
.
To remove only the built-in
Explore
and
Plan
subagents, set
CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1
. Claude reads and explores files directly instead of delegating to them. Requires Claude Code v2.1.198 or later.
In
non-interactive mode
and the
Agent SDK
, set
CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1
to remove all built-in types and supply only your own.
An Agent tool call that omits
subagent_type
fails with
subagent_type is required
when the session has no
general-purpose
subagent to fall back on.
Beyond these built-in subagents, you can create your own with custom prompts, tool restrictions, permission modes, hooks, and skills. The following sections show how to get started and customize subagents.
​
Quickstart: create your first subagent
Subagents are Markdown files with YAML frontmatter. To create one, ask Claude to write it for you, or
write the file yourself
.
As of v2.1.198, the
/agents
command no longer opens the interactive creation wizard; running it prints a reminder to ask Claude or edit
.claude/agents/
directly. Subagent files, frontmatter fields, and the
.claude/agents/
and
~/.claude/agents/
locations are unchanged; only the terminal wizard is removed.
This walkthrough creates a user-level subagent that reviews code and suggests improvements.
1
Ask Claude to create the subagent
In Claude Code, describe the subagent you want and where to save it:
Create a personal code-improver subagent in ~/.claude/agents/ that scans
files and suggests improvements for readability, performance, and best
practices. It should explain each issue, show the current code, and
provide an improved version. Make it read-only and have it use Sonnet.
Claude writes the file with a
name
, a
description
, a
tools
list, a
model
, and a system prompt.
2
Review the file
Open
~/.claude/agents/code-improver.md
and confirm the frontmatter matches what you asked for. The result looks like this:
---
name
:
code-improver
description
:
Scans files and suggests improvements for readability, performance, and best practices. Use after writing or modifying code.
tools
:
Read, Grep, Glob
model
:
sonnet
---
You are a code improvement specialist. For each issue you find, explain
the problem, show the current code, and provide an improved version.
Because the file lives in
~/.claude/agents/
, the subagent is available in every project on your machine. To scope it to one project instead, move it to that project’s
.claude/agents/
directory.
Choose the subagent scope
compares the two.
3
Try it out
Ask Claude to delegate to the new subagent:
Use the code-improver agent to suggest improvements in this project
Claude delegates to your new subagent, which scans the codebase and returns improvement suggestions. In the transcript, the delegation appears as a tool call row showing the subagent’s name followed by a short task description, such as
code-improver(Suggest code improvements)
.
If Claude can’t find the new subagent, restart Claude Code and try again. This happens only when
~/.claude/agents/
didn’t exist before the session started, because a running session doesn’t detect a newly created
agents
directory.
You now have a subagent you can use in any project on your machine to analyze codebases and suggest improvements.
You can also write subagent files by hand, define them via CLI flags, or distribute them through plugins. The following sections cover all configuration options.
On Claude Code v2.1.197 and earlier,
/agents
opens an interactive wizard with a
Running
tab that lists live subagents and a
Library
tab for creating, editing, and deleting them.
​
Configure subagents
A subagent’s file location determines who it’s available to, and its frontmatter determines what it can do. This section covers where subagent files live and every field they support.
​
Choose the subagent scope
Store subagent files in different locations depending on scope. When multiple subagents share the same name, Claude Code uses the one from the higher-priority location.
Location
Scope
Priority
How to create
Managed settings
Organization-wide
1 (highest)
Deployed via
managed settings
--agents
CLI flag
Current session
2
Pass JSON when launching Claude Code
.claude/agents/
Current project
3
Ask Claude, or create the file manually
~/.claude/agents/
All your projects
4
Ask Claude, or create the file manually
Plugin’s
agents/
directory
Where plugin is enabled
5 (lowest)
Installed with
plugins
Project subagents
(
.claude/agents/
) are ideal for subagents specific to a codebase. Check them into version control so your team can use and improve them collaboratively.
Project subagents are discovered by walking up from the current working directory, so every
.claude/agents/
between there and the repository root is scanned. As of v2.1.178, when more than one of these nested directories defines the same
name
, Claude Code uses the definition closest to the working directory.
When you add a directory with
--add-dir
or
/add-dir
, Claude Code also loads its
.claude/agents/
folder, alongside your project subagents. See
Additional directories
for which other configuration types load from
--add-dir
. To share subagents across projects without
--add-dir
, use
~/.claude/agents/
or a
plugin
.
User subagents
(
~/.claude/agents/
) are personal subagents available in all your projects.
Claude Code scans
.claude/agents/
and
~/.claude/agents/
recursively, so you can organize definitions into subfolders such as
agents/review/
or
agents/research/
. The subdirectory path doesn’t affect how a subagent is identified or invoked, because identity comes only from the
name
frontmatter field.
Keep
name
values unique across the whole tree: if two files under the same
.claude/agents/
directory, including its subfolders, declare the same name, Claude Code loads only one of them, chosen by filesystem read order rather than a documented precedence. Across nested project directories, the definition closest to the working directory wins, as described above. The
/doctor
setup checkup reports files in the same directory that share a name and proposes renaming or removing all but one. Before v2.1.205,
/doctor
opened a diagnostics screen that listed duplicates and showed which definition was active.
Plugin
agents/
directories are also scanned recursively. Unlike project and user scopes, a subfolder inside a plugin’s
agents/
directory becomes part of the
scoped identifier
: a file at
agents/review/security.md
in plugin
my-plugin
registers as
my-plugin:review:security
.
CLI-defined subagents
are passed as JSON when launching Claude Code. They exist only for that session and aren’t saved to disk, making them useful for quick testing or automation scripts. You can define multiple subagents in a single
--agents
call:
macOS, Linux, WSL
Windows PowerShell
claude
--agents
'{
"code-reviewer": {
"description": "Expert code reviewer. Use proactively after code changes.",
"prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
"tools": ["Read", "Grep", "Glob", "Bash"],
"model": "sonnet"
},
"debugger": {
"description": "Debugging specialist for errors and test failures.",
"prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
}
}'
claude
--
agents
@'
{
"code-reviewer": {
"description": "Expert code reviewer. Use proactively after code changes.",
"prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
"tools": ["Read", "Grep", "Glob", "Bash"],
"model": "sonnet"
},
"debugger": {
"description": "Debugging specialist for errors and test failures.",
"prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
}
}
'@
The
--agents
flag accepts JSON with a
prompt
field plus these
frontmatter
fields:
description
,
tools
,
disallowedTools
,
model
,
permissionMode
,
mcpServers
,
hooks
,
maxTurns
,
skills
,
initialPrompt
,
memory
,
effort
,
background
, and
isolation
. Use
prompt
for the system prompt, equivalent to the markdown body in file-based subagents. Each top-level key in the JSON is the agent’s name. Don’t start a name with
-
.
For what Claude Code does with a value it can’t load, and the flags and environment variable that skip that check, see
Invalid --agents configuration
.
Managed subagents
are deployed by organization administrators. Place markdown files in
.claude/agents/
inside the
managed settings directory
, using the same frontmatter format as project and user subagents. Managed definitions take precedence over project and user subagents with the same name.
Plugin subagents
come from
plugins
you’ve installed. They load automatically alongside your custom subagents and appear in the @-mention typeahead under their scoped name. See the
plugin components reference
for details on creating plugin subagents.
For security reasons, plugin subagents don’t support the
hooks
,
mcpServers
, or
permissionMode
frontmatter fields. These fields are ignored when loading agents from a plugin. If you need them, copy the agent file into
.claude/agents/
or
~/.claude/agents/
. You can also add rules to
permissions.allow
in
settings.json
or
settings.local.json
, but these rules apply to the entire session, not only the plugin subagent.
Subagent definitions from any of these scopes are also available to
agent teams
: when spawning a teammate, you can reference a subagent type, and Claude Code applies parts of that definition to the teammate. See
agent teams
for which parts apply in each display mode.
​
Write subagent files
Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown:
Claude Code watches
~/.claude/agents/
and
.claude/agents/
. When you add or edit a subagent file on disk, or ask Claude to write one for you, Claude Code detects the change within a few seconds and the next delegation uses the updated definition, with no restart needed.
Three cases still need a restart:
The watcher covers only directories that existed when the session started, so after creating a scope’s first agent file in a new
agents
directory, restart to load it.
Claude Code doesn’t watch
.claude/agents/
inside directories added with
--add-dir
or
/add-dir
, so after adding or editing a subagent there, restart to load the change.
Sessions started with
--disable-slash-commands
don’t watch these directories at all.
.claude/agents/code-reviewer.md
---
name
:
code-reviewer
description
:
Reviews code for quality and best practices
tools
:
Read, Glob, Grep
model
:
sonnet
---
You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
The frontmatter defines the subagent’s metadata and configuration. The body becomes the system prompt that guides the subagent’s behavior. Subagents receive only this system prompt plus basic environment details like the working directory, not the full Claude Code system prompt.
In
non-interactive mode
, pass
--append-subagent-system-prompt
to append your text to the end of every subagent’s system prompt, nested subagents included, apart from a
forked subagent
, which reuses the conversation’s own prompt. Requires Claude Code v2.1.205 or later.
A subagent starts in the main conversation’s current working directory. Within a subagent,
cd
commands don’t persist between Bash or PowerShell tool calls and don’t affect the main conversation’s working directory. To give the subagent an isolated copy of the repository instead, set
isolation: worktree
.
A subagent with
isolation: worktree
runs its Bash and PowerShell commands inside its worktree. A command whose working directory resolves to your main checkout instead, for example because the worktree directory was removed while the subagent was running, fails with an error. Before v2.1.203, such a command could run in the main checkout.
This working-directory check covers the whole repository containing the directory you launched Claude Code from. When your session runs in a linked
worktree
of its own, the check also covers the main checkout that worktree is linked from. Before v2.1.210, the check covered only the launch directory itself. A command whose working directory resolved elsewhere in the same repository, such as the repository root when you launched Claude Code from a monorepo subdirectory, ran there instead of failing.
For Bash commands, Claude Code also checks the command itself in two ways:
It blocks a command that redirects git into the main checkout.
It refuses a command whose shape it can’t verify stays inside the worktree. This refusal applies even to a command that runs no git.
The redirect vectors and the shape rules are listed under
How Claude Code enforces isolation
. PowerShell commands get only the working-directory check.
Monitor
commands go through the same working-directory and command-content checks as Bash commands.
When the main conversation itself runs isolated in a worktree, Claude Code applies the same checks to the session and to every subagent it spawns, including subagents without
isolation: worktree
; see
How Claude Code enforces isolation
.
​
Supported frontmatter fields
The following fields can be used in the YAML frontmatter. Only
name
and
description
are required.
Field
Required
Description
name
Yes
Unique identifier using lowercase letters and hyphens.
Hooks
receive this value as
agent_type
. The filename doesn’t have to match. Names can’t contain
:
, which is reserved for
plugin-scoped identifiers
such as
my-plugin:reviewer
. Claude Code doesn’t load a file whose name contains one and logs an error to the debug log. Before v2.1.218, such names were accepted
description
Yes
When Claude should delegate to this subagent
tools
No
Tools
the subagent can use. Inherits every tool available to subagents if omitted. If no entry in the list resolves to a tool, the subagent usually
fails to launch
with an error naming the entries. To preload Skills into context, use the
skills
field rather than listing
Skill
here
disallowedTools
No
Tools to deny, removed from inherited or specified list
model
No
Model
to use:
sonnet
,
opus
,
haiku
,
fable
, a full model ID (for example,
claude-opus-5
), or
inherit
. Defaults to
inherit
permissionMode
No
Permission mode
:
default
,
acceptEdits
,
auto
,
dontAsk
,
bypassPermissions
,
plan
, or
manual
as an alias for
default
. The
manual
alias requires Claude Code v2.1.200 or later. Ignored for
plugin subagents
maxTurns
No
Maximum number of agentic turns before the subagent stops. When the subagent reaches the limit, Claude Code returns its output marked as partial, and Claude can
resume it
to continue. The partial marking requires Claude Code v2.1.246 or later
skills
No
Skills
to preload into the subagent’s context at startup. The full skill content is injected, not only the description. Subagents can still invoke unlisted project, user, and plugin skills through the Skill tool
mcpServers
No
MCP servers
available to this subagent. Each entry is either a server name referencing an already-configured server (e.g.,
"slack"
) or an inline definition with the server name as key and a full
MCP server config
as value. Ignored for
plugin subagents
hooks
No
Lifecycle hooks
scoped to this subagent. Ignored for
plugin subagents
memory
No
Persistent memory scope
:
user
,
project
, or
local
. Enables cross-session learning
background
No
Set to
true
to keep this subagent in the background even when Claude asks to run it in the foreground. Where
fork mode
is on, Claude Code already runs the subagents Claude spawns
in the background
effort
No
Effort level when this subagent is active. Overrides the session effort level. Default: inherits from session. Options:
low
,
medium
,
high
,
xhigh
,
max
; available levels depend on the model
isolation
No
Set to
worktree
to run the subagent in a temporary
git worktree
, giving it an isolated copy of the repository branched by default from your
default branch
rather than the parent session’s
HEAD
. The worktree is automatically cleaned up if the subagent makes no changes
color
No
Display color for the subagent in the task list and transcript. Accepts
red
,
blue
,
green
,
yellow
,
purple
,
orange
,
pink
, or
cyan
initialPrompt
No
Auto-submitted as the first user turn when this agent runs as the main session agent (via
--agent
or the
agent
setting).
Commands
and
skills
are processed. Prepended to any user-provided prompt
experimental
No
Map of experimental options. Set its
cacheTtl
key to
5m
or
1h
to choose the
prompt cache lifetime
for this subagent’s requests. Claude Code ignores any other value, ignores
1h
while your Claude subscription is using usage credits, and reads the field only from subagent files. Requires Claude Code v2.1.248 or later
Write
cacheTtl
inside the
experimental
map, not at the top level of the frontmatter.
---
name
:
repo-auditor
description
:
Audits a large repository and reports what it finds
experimental
:
cacheTtl
:
1h
---
​
Subagent files Claude Code skips
Claude Code skips a file in a project, user, or managed
agents
directory, or in one under a directory you add with
--add-dir
, without reporting it in the session, when the frontmatter has any of these problems:
No
name
: Claude Code treats the file as documentation kept beside your agents.
An opening
---
that isn’t the file’s first line
: Claude Code reads the file as having no frontmatter and treats it as documentation.
A
name
that starts with
-
or contains
:
: Claude Code skips the file and writes an error to the debug log. See the
name
row in the table above.
A
name
but no
description
: Claude Code skips the file and writes the reason to the debug log.
YAML that doesn’t parse
: Claude Code reads no fields from the file, skips it, and writes the parse error to the debug log.
To see the debug log, run Claude Code with
--debug
.
A
plugin subagent
whose frontmatter has no
name
or doesn’t parse still loads, under its filename.
Check an
agents
directory before a session
To find files in an
agents
directory whose frontmatter doesn’t parse, run
claude plugin validate
against the directory, for example
.claude/agents
or
~/.claude/agents
. Claude Code checks only
the directory you name
, and doesn’t flag a file whose frontmatter parses but has no
name
. Requires Claude Code v2.1.233 or later.
​
Choose a model
The
model
field controls which
AI model
the subagent uses:
Model alias
: use one of the available aliases:
sonnet
,
opus
,
haiku
, or
fable
Full model ID
: use a full model ID such as
claude-opus-5
or
claude-sonnet-5
. Accepts the same values as the
--model
flag
inherit
: use the same model as the main conversation
Omitted
: defaults to
inherit
and uses the same model as the main conversation
When Claude invokes a subagent, it can also pass a
model
parameter for that specific invocation. Claude Code resolves the subagent’s model in this order:
The
CLAUDE_CODE_SUBAGENT_MODEL
environment variable, when set to a model alias or model ID
The per-invocation
model
parameter
The subagent definition’s
model
frontmatter
The main conversation’s model
As of v2.1.196, setting
CLAUDE_CODE_SUBAGENT_MODEL
to
inherit
is the same as leaving it unset: resolution continues with the per-invocation
model
parameter, then the frontmatter. In earlier versions,
inherit
forced subagents onto the main conversation’s model and ignored both of those sources.
Claude Code checks the environment variable, per-invocation parameter, and frontmatter values against your organization’s
availableModels
allowlist. For a blocked value, it substitutes another model:
When the blocked value is a family alias such as
opus
, Claude Code runs the subagent on the newest version of that family the allowlist permits, following the same
substitution rules and provider scope
as
/model
. Before v2.1.222, Claude Code ran the subagent on the inherited model for a blocked family alias as well.
For any other blocked value, on providers where that substitution doesn’t operate, or when the allowlist permits no version of the family, Claude Code runs the subagent on the inherited model instead.
In interactive sessions, Claude Code shows a warning naming the requested model and the model the subagent runs on, for either substitution.
A per-invocation
model
parameter also applies when the subagent is
resumed or sent a follow-up message
, so the subagent stays on that model. Before v2.1.211, resuming dropped the per-invocation value and the subagent reverted to its definition’s
model
field or, without one, the main conversation’s model.
As of v2.1.198, subagents also inherit the main conversation’s
extended thinking
configuration: if thinking is on in your session, it’s on for the subagent, and if it’s off, it stays off. There is no per-subagent thinking setting. Before v2.1.198, subagents ran with extended thinking disabled regardless of the main conversation’s setting.
​
Control subagent capabilities
You can control what subagents can do through tool access, permission modes, and conditional rules.
​
Available tools
Subagents inherit the
built-in tools
and MCP tools available in the main conversation, narrowed by two filters: the first removes a short list of tools from every subagent, and the second reduces the built-in tool set for subagents that run in the
background
, which is the default.
Forks
skip both filters and receive the main conversation’s exact tool pool. The first filter removes these tools, even when listed in the
tools
field:
Agent
, when the subagent is at the
depth limit
; in a
fork
the tool stays listed but returns an error instead of spawning
AskUserQuestion
EndConversation
, which can end only the main conversation; see
EndConversation tool behavior
EnterPlanMode
ExitPlanMode
, unless the subagent’s
permissionMode
is
plan
ScheduleWakeup
TaskOutput
WaitForMcpServers
Workflow
The second filter applies to subagents running in the background. Apart from
Agent
and
ExitPlanMode
, which follow the first filter’s conditions wherever the subagent runs, a background subagent keeps every MCP tool but only these built-in tools:
Read
,
Grep
,
Glob
,
Bash
,
PowerShell
,
Edit
,
Write
,
NotebookEdit
,
WebFetch
,
WebSearch
,
TodoWrite
,
Skill
,
ToolSearch
,
EnterWorktree
,
ExitWorktree
,
Monitor
,
TaskStop
,
SendMessage
, and
Artifact
. Claude Code removes every other built-in tool from a background subagent, whether inherited or listed in the
tools
field, so the same definition can resolve to different tools in the foreground and the background. The removal reports no error unless it leaves the
tools
list
resolving to nothing
.
ListAgents
follows these filters like any built-in tool: a foreground subagent inherits it in sessions where cross-session messaging is enabled, and a background subagent doesn’t keep it.
Teammates in
agent teams
additionally keep the task tools and cron tools:
TaskCreate
,
TaskGet
,
TaskList
,
TaskUpdate
,
CronCreate
,
CronDelete
, and
CronList
.
In a
session without the Task tools
, Claude Code doesn’t provide the task tools to subagents either, even when the subagent runs a different model. An in-process teammate follows your session the same way, while a teammate in its own
split pane
runs as a separate Claude Code process, so its own model decides.
To restrict tools, use the
tools
field as an allowlist or the
disallowedTools
field as a denylist. This example uses
tools
to allow only Read, Grep, Glob, and Bash. The subagent can’t edit files, write files, or use any MCP tools:
---
name
:
safe-researcher
description
:
Research agent with restricted capabilities
tools
:
Read, Grep, Glob, Bash
---
This example uses
disallowedTools
to inherit the subagent’s tool pool except Write and Edit. The subagent keeps Bash, MCP tools, and the rest of its pool:
---
name
:
no-writes
description
:
Inherits the available tools except file writes
disallowedTools
:
Write, Edit
---
If both are set,
disallowedTools
is applied first, then
tools
is resolved against the remaining pool. A tool listed in both is removed.
When nothing in the
tools
list resolves to a tool, for example because every entry is misspelled or names a tool that isn’t available to subagents, Claude Code usually refuses to launch the subagent and the Agent tool returns an error naming the unresolved entries; see
Agent would be spawned with zero tools
for the message and how to fix each entry. Before v2.1.208, that subagent launched with no tools and could return an empty or confusing result.
Both fields accept MCP server-level patterns in addition to exact tool names:
mcp__<server>
or
mcp__<server>__*
grants or removes every tool from the named server. In
disallowedTools
,
mcp__*
also removes every MCP tool from any server. This example removes every tool from the
github
MCP server while keeping tools from other servers and the built-in tools in its pool:
---
name
:
local-only
description
:
Inherits every tool except those from the github MCP server
disallowedTools
:
mcp__github
---
​
Restrict which subagents can be spawned
When an agent runs as the main thread with
claude --agent
, it can spawn subagents using the Agent tool. To restrict which subagent types it can spawn, use
Agent(agent_type)
syntax in the
tools
field.
In version 2.1.63, the Task tool was renamed to Agent. Existing
Task(...)
references in settings and agent definitions still work as aliases.
---
name
:
coordinator
description
:
Coordinates work across specialized agents
tools
:
Agent(worker, researcher), Read, Bash
---
This is an allowlist: only the
worker
and
researcher
subagents can be spawned. If the agent tries to spawn any other type, the request fails and the agent sees only the allowed types in its prompt. To block specific agents while allowing all others, use
permissions.deny
instead.
To allow spawning any subagent without restrictions, use
Agent
without parentheses:
tools
:
Agent, Read, Bash
If you omit
Agent
from the
tools
list entirely, the agent can’t spawn any subagents with the Agent tool.
The
Agent(agent_type)
allowlist syntax applies only to an agent running as the main thread with
claude --agent
. In a subagent definition, listing
Agent
in
tools
lets that subagent spawn subagents of its own while the
depth limit
allows it, but any type list inside the parentheses is ignored.
​
Scope MCP servers to a subagent
Use the
mcpServers
field to give a subagent access to
MCP
servers that aren’t available in the main conversation. Inline servers defined here are connected when the subagent starts, subject to the
trust rule for the agent file’s folder
, and disconnected when it finishes. String references share the parent session’s connection.
The
mcpServers
field applies in both contexts where an agent file can run:
As a subagent, spawned through the Agent tool or an @-mention
As the main session, launched with
--agent
or the
agent
setting
When the agent is the main session, inline server definitions connect at startup alongside servers from
.mcp.json
and settings files, under the same
trust rule for the agent file’s folder
. In
/mcp
, a remote (HTTP or SSE) server you’ve used before can show the
cached
status
instead; Claude Code connects it when Claude first calls one of its tools.
Each entry in the list is either an inline server definition or a string referencing an MCP server already configured in your session:
---
name
:
browser-tester
description
:
Tests features in a real browser using Playwright
mcpServers
:
# Inline definition: scoped to this subagent only
-
playwright
:
type
:
stdio
command
:
npx
args
: [
"-y"
,
"@playwright/mcp@latest"
]
# Reference by name: reuses an already-configured server
-
github
---
Use the Playwright tools to navigate, screenshot, and interact with pages.
Inline definitions use the same schema as
.mcp.json
server entries, keyed by the server name, and support the
stdio
,
http
,
sse
, and
ws
types.
To keep an MCP server out of the main conversation entirely and avoid its tool descriptions consuming context there, define it inline here rather than in
.mcp.json
. The subagent gets the tools; the parent conversation doesn’t.
Claude Code loads an inline server from an agent file in your project’s
.claude/agents/
directory, or in an
--add-dir
directory’s
.claude/agents/
, only after you
trust the folder the agent file came from
. Before v2.1.238, Claude Code loaded these servers without checking trust.
Trust that doesn’t count
: a parent folder’s trust, and the automatic trust a
-p
or SDK session gets for
hooks in settings files
Until then
: Claude Code skips every inline server in that agent file and writes the exact
projects["<path>"].hasTrustDialogAccepted
key for
~/.claude.json
to the debug log
--add-dir
directories
: a directory outside your trusted workspace’s repository needs its own trust entry, since its
.claude/agents/
files don’t inherit your workspace’s trust
Claude Code loads two kinds of server without checking trust for the folder the agent file came from:
A name that references a server you already configured
An inline server in an agent file from
~/.claude/agents/
, in one you pass with
--agents
or the SDK
agents
option, or in one that managed settings supplies
As of v2.1.153, the MCP restrictions that apply to the main session also cover servers declared in subagent frontmatter:
--strict-mcp-config
and
--bare
Enterprise managed MCP configuration
allowedMcpServers
and
deniedMcpServers
policies
When one of these blocks a server, Claude Code skips it and shows a warning naming the blocked servers.
Managed-settings restrictions apply to every subagent regardless of how it is defined.
--strict-mcp-config
doesn’t filter servers you pass inline via
--agents
or the SDK
agents
option, since those are explicit caller input.
​
Permission modes
Set
permissionMode
to choose the permission mode a subagent runs in. Use the modes’ config values, so Manual mode is
default
. If you leave it unset, the subagent inherits the main conversation’s mode, which starts as
auto mode
on Pro, Max, and Team plans unless your settings or your organization change it. Setting it overrides that mode, except in the cases described below.
Mode
Behavior
default
Manual mode: prompts for permission
acceptEdits
Auto-accept file edits and common filesystem commands for paths in the working directory or
additionalDirectories
auto
Auto mode
: a background classifier reviews commands and protected-directory writes
dontAsk
Auto-deny permission prompts. Explicitly allowed tools still work;
AskUserQuestion
, MCP tools marked
requiresUserInteraction
, and connector tools
your organization set to
ask
in sessions where that setting reaches Claude Code are denied even if you’ve allowed them
bypassPermissions
Skip permission prompts
plan
Plan mode (read-only exploration)
Use
bypassPermissions
with caution. It skips permission prompts, allowing the subagent to execute operations without approval, including writes to
.git
,
.config/git
,
.claude
,
.vscode
,
.idea
,
.husky
,
.cargo
,
.devcontainer
,
.yarn
, and
.mvn
.
Even in this mode, the
actions no mode auto-approves
still apply. See
permission modes
for details.
If the parent uses
bypassPermissions
or
acceptEdits
, this takes precedence and can’t be overridden. If the parent uses
auto mode
, the subagent inherits auto mode and any
permissionMode
in its frontmatter is ignored: the classifier evaluates the subagent’s tool calls with the same block and allow rules as the parent session.
If bypass mode is disabled by
permissions.disableBypassPermissionsMode
, Claude Code ignores
permissionMode: bypassPermissions
in the frontmatter and the subagent runs with the parent session’s mode. Before v2.1.223, Claude Code applied the frontmatter mode even with bypass disabled.
​
Preload skills into subagents
Use the
skills
field to inject skill content into a subagent’s context at startup. This gives the subagent domain knowledge without requiring it to discover and load skills during execution.
---
name
:
api-developer
description
:
Implement API endpoints following team conventions
skills
:
-
api-conventions
-
error-handling-patterns
---
Implement API endpoints. Follow the conventions and patterns from the preloaded skills.
The full content of each listed skill is injected into the subagent’s context at startup. This field controls which skills are preloaded, not which skills the subagent can access: without it, the subagent can still discover and invoke project, user, and plugin skills through the Skill tool during execution. To prevent a subagent from invoking skills entirely, omit
Skill
from the
tools
list or add it to
disallowedTools
.
You can’t preload skills that set
disable-model-invocation: true
, since preloading draws from the same set of skills Claude can invoke. This includes the bundled
/verify
skill: only you can run it, so it can’t be preloaded either.
If a listed skill is missing or disabled, for example by your organization’s policy, Claude Code skips it and logs a warning to the debug log.
This is the inverse of
running a skill in a subagent
. With
skills
in a subagent, the subagent controls the system prompt and loads skill content. With
context: fork
in a skill, the skill content is injected into the agent you specify. Both use the same underlying system.
​
Enable persistent memory
The
memory
field gives the subagent a persistent directory that survives across conversations. The subagent uses this directory to build up knowledge over time, such as codebase patterns, debugging insights, and architectural decisions.
---
name
:
code-reviewer
description
:
Reviews code for quality and best practices
memory
:
user
---
You are a code reviewer. As you review code, update your agent memory with
patterns, conventions, and recurring issues you discover.
Choose a scope based on how broadly the memory should apply:
Scope
Location
Use when
user
~/.claude/agent-memory/<name-of-agent>/
the subagent should remember learnings across all projects
project
.claude/agent-memory/<name-of-agent>/
the subagent’s knowledge is project-specific and shareable via version control
local
.claude/agent-memory-local/<name-of-agent>/
the subagent’s knowledge is project-specific but shouldn’t be checked into version control
Subagent memory is part of
auto memory
: if you turn auto memory off, with the
autoMemoryEnabled
setting or
CLAUDE_CODE_DISABLE_AUTO_MEMORY
, the
memory
field has no effect and the subagent launches without the memory instructions or the memory tool access described below.
When memory is enabled:
The subagent’s system prompt includes instructions for reading and writing to the memory directory.
The subagent’s system prompt also includes the first 200 lines or 25KB of
MEMORY.md
in the memory directory, whichever comes first, with instructions to curate
MEMORY.md
if it exceeds that limit.
Read, Write, and Edit tools are automatically enabled so the subagent can manage its memory files.
Persistent memory tips
project
is the recommended default scope. It makes subagent knowledge shareable via version control.
Ask the subagent to consult its memory before starting work: “Review this PR, and check your memory for patterns you’ve seen before.”
Ask the subagent to update its memory after completing a task: “Now that you’re done, save what you learned to your memory.” Over time, this builds a knowledge base that makes the subagent more effective.
Include memory instructions directly in the subagent’s markdown file so it proactively maintains its own knowledge base:
Update your agent memory as you discover codepaths, patterns, library
locations, and key architectural decisions. This builds up institutional
knowledge across conversations. Write concise notes about what you found
and where.
​
Conditional rules with hooks
For more dynamic control over tool usage, use
PreToolUse
hooks to validate operations before they execute. This is useful when you need to allow some operations of a tool while blocking others.
This example creates a subagent that only allows read-only database queries. The
PreToolUse
hook runs the script specified in
command
before each Bash command executes:
---
name
:
db-reader
description
:
Execute read-only database queries
tools
:
Bash
hooks
:
PreToolUse
:
-
matcher
:
"Bash"
hooks
:
-
type
:
command
command
:
"./scripts/validate-readonly-query.sh"
---
Claude Code
passes hook input as JSON
via stdin to hook commands. The validation script reads this JSON, extracts the Bash command, and
exits with code 2
to block write operations:
#!/bin/bash
# ./scripts/validate-readonly-query.sh
INPUT
=
$(
cat
)
COMMAND
=
$(
echo
"
$INPUT
"
|
jq
-r
'.tool_input.command // empty'
)
# Block SQL write operations (case-insensitive)
if
echo
"
$COMMAND
"
|
grep
-iE
'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b'
>
/dev/null
;
then
echo
"Blocked: Only SELECT queries are allowed"
>&2
exit
2
fi
exit
0
On macOS and Linux, make the script executable, or the hook fails instead of blocking anything:
chmod
+x
./scripts/validate-readonly-query.sh
To test the rule, ask the subagent to run an
UPDATE
statement: the script exits with code 2, Claude Code blocks the command, and the subagent sees the
Blocked: Only SELECT queries are allowed
message.
See
Hook input
for the complete input schema and
exit codes
for how exit codes affect behavior. On Windows, write hook scripts in PowerShell and add
shell: powershell
to the hook entry as shown in
running hooks in PowerShell
.
​
Disable specific subagents
You can prevent Claude from using specific subagents by adding them to the
deny
array in your
settings
. Use the format
Agent(subagent-name)
where
subagent-name
matches the subagent’s name field.
{
"permissions"
: {
"deny"
: [
"Agent(Explore)"
,
"Agent(my-custom-agent)"
]
}
}
This works for both built-in and custom subagents. You can also use the
--disallowedTools
CLI flag:
claude
--disallowedTools
"Agent(Explore)"
See
Permissions documentation
for more details on permission rules.
​
Define hooks for subagents
Subagents can define
hooks
that run during the subagent’s lifecycle. There are two ways to configure hooks:
In the subagent’s frontmatter
: define hooks that run only while that subagent is active
In
settings.json
: define session-wide hooks that also fire inside subagents. Tool events such as
PreToolUse
and
PostToolUse
fire for the subagent’s tool calls the same way they do in the main conversation, and
SubagentStart
and
SubagentStop
fire when a subagent starts or finishes
Hooks from
settings files, managed policy settings, and plugins
all apply inside subagents, so a
PreToolUse
hook in
settings.json
also runs before every tool a subagent uses.
​
Hooks in subagent frontmatter
Define hooks directly in the subagent’s markdown file. These hooks only run while that specific subagent is active and are cleaned up when it finishes.
Frontmatter hooks fire when the agent is spawned as a subagent through the Agent tool or an @-mention, and when the agent runs as the main session via
--agent
or the
agent
setting. In the main-session case they run alongside any hooks defined in
settings.json
.
To let a project-level subagent’s frontmatter hooks run, accept the
workspace trust dialog
for the folder that contains the agent file. Hooks from user-level subagents in
~/.claude/agents/
and from definitions you pass with
--agents
run without this step. If you added a folder with
--add-dir
from outside your trusted workspace’s repository, trust that folder separately: its
.claude/agents/
hooks don’t inherit the workspace’s grant.
Until you trust the folder, the subagent still runs, but Claude Code skips its frontmatter hooks and logs an error to the debug log explaining how to trust the folder. This is a stricter rule than the one for hooks in settings files: trusting a parent folder isn’t enough, and a
-p
session doesn’t count as trusted.
What runs before you trust a folder
compares the two. Before v2.1.218, frontmatter hooks could run from folders you hadn’t trusted, including in non-interactive sessions.
All
hook events
are supported. The most common events for subagents are:
Event
Matcher input
When it fires
PreToolUse
Tool name
Before the subagent uses a tool
PostToolUse
Tool name
After the subagent uses a tool
Stop
(none)
When the subagent finishes (converted to
SubagentStop
at runtime)
This example validates Bash commands with the
PreToolUse
hook and runs a linter after file edits with
PostToolUse
:
---
name
:
code-reviewer
description
:
Review code changes with automatic linting
hooks
:
PreToolUse
:
-
matcher
:
"Bash"
hooks
:
-
type
:
command
command
:
"./scripts/validate-command.sh $TOOL_INPUT"
PostToolUse
:
-
matcher
:
"Edit|Write"
hooks
:
-
type
:
command
command
:
"./scripts/run-linter.sh"
---
When the agent is invoked as a subagent,
Stop
hooks in frontmatter are automatically converted to
SubagentStop
events.
​
Project-level hooks for subagent events
Configure hooks in
settings.json
that respond to subagent lifecycle events in the main session.
Event
Matcher input
When it fires
SubagentStart
Agent type name
When a subagent begins execution
SubagentStop
Agent type name
When a subagent completes
Both events support matchers to target specific agent types by name. The matcher value is the agent’s frontmatter
name
for project-level and user-level subagents, or the plugin-scoped identifier such as
my-plugin:db-agent
for
plugin subagents
. A scoped name contains a colon, so it is evaluated as an
unanchored regular expression
; anchor it with
^
and
$
, as in
^my-plugin:db-agent$
, to match only that agent.
This example runs a setup script only when the
db-agent
subagent starts, and a cleanup script when any subagent stops:
{
"hooks"
: {
"SubagentStart"
: [
{
"matcher"
:
"db-agent"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"./scripts/setup-db-connection.sh"
}
]
}
],
"SubagentStop"
: [
{
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"./scripts/cleanup-db-connection.sh"
}
]
}
]
}
}
A hyphenated matcher like
db-agent
matches exactly on Claude Code v2.1.195 or later. On earlier versions it is evaluated as an unanchored regular expression and also fires for any agent type that contains it, such as
prod-db-agent
; anchor it as
^db-agent$
on those versions.
See
Hooks
for the complete hook configuration format.
​
Work with subagents
​
Understand automatic delegation
Claude automatically delegates tasks based on the task description in your request, the
description
field in subagent configurations, and current context. To encourage proactive delegation, include phrases like “use proactively” in your subagent’s description field.
​
Invoke subagents explicitly
When automatic delegation isn’t enough, you can request a subagent yourself. Three patterns escalate from a one-off suggestion to a session-wide default:
Natural language
: name the subagent in your prompt; Claude decides whether to delegate
@-mention
: guarantees the subagent runs for one task
Session-wide
: the whole session uses that subagent’s system prompt, tool restrictions, and model via the
--agent
flag or the
agent
setting
For natural language, there’s no special syntax. Name the subagent and Claude typically delegates:
Use the test-runner subagent to fix failing tests
Have the code-reviewer subagent look at my recent changes
@-mention the subagent.
Type
@
and pick the subagent from the typeahead, the same way you @-mention files. This ensures that specific subagent runs rather than leaving the choice to Claude:
@"code-reviewer (agent)" look at the auth changes
Your full message still goes to Claude, which writes the subagent’s task prompt based on what you asked. The @-mention controls which subagent Claude invokes, not what prompt it receives.
Subagents provided by an enabled
plugin
appear in the typeahead under their scoped name, such as
my-plugin:code-reviewer
or
my-plugin:review:security
when the plugin
organizes agents into subfolders
. Named background subagents currently running in the session also appear in the typeahead, showing their status next to the name.
You can also type the mention manually without using the picker:
@agent-<name>
for local subagents, or
@agent-
followed by the scoped name for plugin subagents, for example
@agent-my-plugin:code-reviewer
. While you type this form the typeahead shows file matches rat

## Source (hooks): https://docs.claude.com/en/docs/claude-code/hooks

Hooks reference - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
For a quickstart guide with examples, see
Automate actions with hooks
.
Hooks are user-defined shell commands, HTTP endpoints, MCP tool calls, LLM prompts, or subagents that execute automatically at specific points in Claude Code’s lifecycle. Claude Code fires the same hook events wherever it runs: sessions in the terminal, IDE extensions, the
Desktop app
, and
Claude Code on the web
. Use this reference to look up event schemas, configuration options, JSON input/output formats, and advanced features like async hooks, HTTP hooks, and MCP tool hooks.
​
Hook lifecycle
Claude Code runs hooks at specific points during a session. When an event fires and a matcher matches, Claude Code passes JSON context about the event to your hook handler. For command hooks, input arrives on stdin. For HTTP hooks, it arrives as the POST request body. Your handler can then inspect the input, take action, and optionally return a decision.
Events fall into three cadences:
once per session:
SessionStart
and
SessionEnd
once per turn:
UserPromptSubmit
,
Stop
, and
StopFailure
on every tool call inside the agentic loop:
PreToolUse
and
PostToolUse
, except
EndConversation
calls, which skip both
The table below summarizes when each event fires. The
Hook events
section documents the full input schema and decision control options for each one.
Event
When it fires
SessionStart
When a session begins or resumes
Setup
When you start Claude Code with
--init-only
, or with
--init
or
--maintenance
in
-p
mode. For one-time preparation in CI or scripts
UserPromptSubmit
When you submit a prompt, before Claude processes it
UserPromptExpansion
When a user-typed command expands into a prompt, before it reaches Claude. Can block the expansion
PreToolUse
Before a tool call executes. Can block it
PermissionRequest
When a tool call needs a permission decision
PermissionDenied
When auto mode denies a tool call, including denials without a classifier verdict. Use JSON
hookSpecificOutput.retry: true
to tell the model it may retry the denied tool call. Claude Code ignores
retry
when the classifier produced no verdict
PostToolUse
After a tool call succeeds
PostToolUseFailure
After a tool call fails
PostToolBatch
After a full batch of parallel tool calls resolves, before the next model call
Notification
When Claude Code sends a notification
MessageDisplay
While assistant message text is displayed
SubagentStart
When a subagent is spawned
SubagentStop
When a subagent finishes
TaskCreated
When a task is being created via
TaskCreate
TaskCompleted
When a task is being marked as completed
Stop
When Claude finishes responding
StopFailure
When the turn ends due to an API error
TeammateIdle
When an
agent team
teammate is about to go idle
InstructionsLoaded
When a CLAUDE.md or
.claude/rules/*.md
file is loaded into context. Fires at session start and when files are lazily loaded during a session
ConfigChange
When a configuration file changes during a session
CwdChanged
When the working directory changes, for example when Claude executes a
cd
command. Useful for reactive environment management with tools like direnv
DirectoryAdded
When a working directory is added mid-session via
/add-dir
or the SDK
register_repo_root
control request
FileChanged
When a watched file changes on disk. The
matcher
field specifies which filenames to watch
WorktreeCreate
When a worktree is being created via
--worktree
,
isolation: "worktree"
, or for a background session. Replaces default git behavior
WorktreeRemove
When a worktree is being removed at session exit, when a subagent finishes, or when you delete a background session
PreCompact
Before context compaction
PostCompact
After context compaction completes
PreModelSwitch
Before Claude Code applies a model switch that you or a client requested. Can block the switch
PostModelSwitch
After the session’s model changes, including changes Claude Code makes on its own, such as restoring the model when you resume a session
Elicitation
When an MCP server requests user input during a tool call
ElicitationResult
After a user responds to an MCP elicitation, before the response is sent back to the server
SessionEnd
When a session terminates
​
How a hook resolves
To see how the event, the matcher, and the handler fit together, consider this
PreToolUse
hook that blocks destructive shell commands.
macOS/Linux
Windows (PowerShell)
The
matcher
narrows to Bash tool calls and the
if
condition narrows further to Bash subcommands matching
rm *
, so
block-rm.sh
only spawns when both filters match:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"Bash"
,
"hooks"
: [
{
"type"
:
"command"
,
"if"
:
"Bash(rm *)"
,
"command"
:
"${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh"
,
"args"
: []
}
]
}
]
}
}
The script reads the JSON input from stdin, extracts the command, and returns a
permissionDecision
of
"deny"
if it contains
rm -rf
. Save it to
.claude/hooks/block-rm.sh
in your project and make it executable with
chmod +x .claude/hooks/block-rm.sh
so Claude Code can run it:
#!/bin/bash
# .claude/hooks/block-rm.sh
COMMAND
=
$(
jq
-r
'.tool_input.command'
)
if
echo
"
$COMMAND
"
|
grep
-q
'rm -rf'
;
then
jq
-n
'{
hookSpecificOutput: {
hookEventName: "PreToolUse",
permissionDecision: "deny",
permissionDecisionReason: "Destructive command blocked by hook"
}
}'
else
exit
0
# no decision; normal permission flow applies
fi
This script, like the other Bash examples on this page that parse JSON input, uses
jq
, so install
jq
and make sure it is on your
PATH
before trying them.
The matcher
Bash|PowerShell
covers the
PowerShell tool
as well as Bash. A single
if
rule matches only one tool’s calls, so each tool gets its own handler: the first narrows to Bash subcommands matching
rm *
, the second to PowerShell commands matching
Remove-Item *
. Both run the same script through
powershell.exe
:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"Bash|PowerShell"
,
"hooks"
: [
{
"type"
:
"command"
,
"if"
:
"Bash(rm *)"
,
"command"
:
"powershell.exe"
,
"args"
: [
"-NoProfile"
,
"-ExecutionPolicy"
,
"Bypass"
,
"-File"
,
"${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.ps1"
]
},
{
"type"
:
"command"
,
"if"
:
"PowerShell(Remove-Item *)"
,
"command"
:
"powershell.exe"
,
"args"
: [
"-NoProfile"
,
"-ExecutionPolicy"
,
"Bypass"
,
"-File"
,
"${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.ps1"
]
}
]
}
]
}
}
The
-NoProfile
flag skips loading your PowerShell profile so the hook starts fast, and
-ExecutionPolicy Bypass
lets PowerShell run the local script file.
The script reads the JSON input from stdin, extracts the command, and returns a
permissionDecision
of
"deny"
if it contains
rm -rf
or
Remove-Item
followed by
-Recurse
. Save it to
.claude/hooks/block-rm.ps1
in your project:
# .claude/hooks/block-rm.ps1
$callInput
=
[
Console
]::
In
.ReadToEnd()
|
ConvertFrom-Json
$command
=
$callInput
.tool_input.command
if
(
$command
-match
'rm -rf|Remove-Item.*-Recurse'
) {
@
{
hookSpecificOutput
=
@
{
hookEventName
=
"PreToolUse"
permissionDecision
=
"deny"
permissionDecisionReason
=
"Destructive command blocked by hook"
}
}
|
ConvertTo-Json
}
else
{
exit
0
# no decision; normal permission flow applies
}
Now suppose Claude Code decides to run
Bash "rm -rf /tmp/build"
against the macOS/Linux config. Here’s what happens:
1
Event fires
The
PreToolUse
event fires. Claude Code sends the tool input as JSON on stdin to the hook:
{
"tool_name"
:
"Bash"
,
"tool_input"
: {
"command"
:
"rm -rf /tmp/build"
},
...
}
2
Matcher checks
The matcher
"Bash"
matches the tool name, so this hook group activates. If you omit the matcher or use
"*"
, the group activates on every occurrence of the event.
3
If condition checks
The
if
condition
"Bash(rm *)"
matches because
rm -rf /tmp/build
is a subcommand matching
rm *
, so this handler spawns. If the command had been
npm test
, the
if
check would fail and
block-rm.sh
would never run, avoiding the process spawn overhead. The
if
field is optional; without it, every handler in the matched group runs.
4
Hook handler runs
The script inspects the full command and finds
rm -rf
, so it prints a decision to stdout:
{
"hookSpecificOutput"
: {
"hookEventName"
:
"PreToolUse"
,
"permissionDecision"
:
"deny"
,
"permissionDecisionReason"
:
"Destructive command blocked by hook"
}
}
If the command had been a safer
rm
variant like
rm file.txt
, the script would hit
exit 0
instead. Exit code 0 with no output means the hook has no decision to report, so the tool call continues through the normal
permission flow
. The hook can deny the call, but staying silent doesn’t approve it.
5
Claude Code acts on the result
Claude Code reads the JSON decision, blocks the tool call, and shows Claude the reason.
The
Configuration
section below documents the full schema, and each
hook event
section documents what input your command receives and what output it can return.
​
Configuration
Hooks are defined in JSON settings files. The configuration has three levels of nesting:
Choose a
hook event
to respond to, like
PreToolUse
or
Stop
Add a
matcher group
to filter when it fires, like “only for the Bash tool”
Define one or more
hook handlers
to run when matched
See
How a hook resolves
above for a complete walkthrough with an annotated example.
This page uses specific terms for each level:
hook event
for the lifecycle point,
matcher group
for the filter, and
hook handler
for the shell command, HTTP endpoint, MCP tool, prompt, or agent that runs. “Hook” on its own refers to the general feature.
​
Hook locations
Where you define a hook determines its scope:
Location
Scope
Shareable
~/.claude/settings.json
All your projects
No, local to your machine
.claude/settings.json
Single project
Yes, can be committed to the repo
.claude/settings.local.json
Single project
No, gitignored when Claude Code saves a setting to it
Managed policy settings
Organization-wide
Yes, admin-controlled
Plugin
hooks/hooks.json
When plugin is enabled
Yes, bundled with the plugin
Skill
frontmatter
The rest of the session once the skill is invoked. See
Hooks in skills and agents
Yes, defined in the skill file
Subagent
frontmatter
While that subagent is running
Yes, defined in the subagent file
Cloud sessions on
Claude Code on the web
don’t read your local
~/.claude/settings.json
; hooks there come from the repo and from your organization’s server-managed settings. In a
self-hosted environment
, Claude Code also runs the hooks the operator seeded from the runner host’s
~/.claude/
, and it runs the hooks in the runner image’s managed settings file when that file is among the
managed sources Claude Code applies
, which by default means only when neither server-managed settings nor an MDM-delivered Claude Code policy supplies the managed tier. See
what carries over from your setup
for which files reach a cloud session.
For details on settings file resolution, see
settings
.
Hooks from settings files, managed policy settings, and plugins also run inside
subagents
. When a subagent calls a tool, tool events such as
PreToolUse
and
PostToolUse
fire the same configured hooks as in the main conversation, and the input carries the
agent_id
and
agent_type
common input fields
that identify the subagent.
Enterprise administrators can use
allowManagedHooksOnly
to restrict which hooks run:
Your user, project, local, and plugin hooks are blocked. Hooks from plugins force-enabled in managed settings
enabledPlugins
are exempt
Claude Code also narrows your
statusLine
,
fileSuggestion
, and
subagentStatusLine
settings to managed settings
Claude Code also disables plugins with a
command
source
, including plugins force-enabled in managed settings
enabledPlugins
, unless
disableCommandPluginSources
is explicitly set to
false
.
command
sources require Claude Code v2.1.229 or later
Claude Code also blocks marketplace
headersHelper
commands
unless
disableCommandPluginSources
is explicitly set to
false
, except for a marketplace that managed settings themselves declare
See
what runs under
allowManagedHooksOnly
.
Hook entries merge across settings levels rather than replacing each other: user, project, and local settings add their own hooks without removing managed ones, and the
disableAllHooks
setting can’t disable managed hooks from outside managed settings.
The
HTTP hook allowlists
apply to hooks from every source, including managed policy settings:
allowedHttpHookUrls
: when defined at any settings level, Claude Code runs an HTTP hook handler only if its URL matches the merged allowlist
httpHookAllowedEnvVars
: when defined, Claude Code interpolates only the environment variables on that list into hook headers
​
Matcher patterns
The
matcher
field filters when hooks fire. How a matcher is evaluated depends on the characters it contains:
Matcher value
Evaluated as
Example
"*"
,
""
, or omitted
Match all
fires on every occurrence of the event
Only letters, digits,
_
,
-
, spaces,
,
, and
|
Exact string, or list of exact strings separated by
|
or
,
with optional surrounding whitespace
Bash
matches only the Bash tool;
Edit|Write
and
Edit, Write
each match either tool exactly;
code-reviewer
matches only that agent type
Contains any other character
JavaScript regular expression, unanchored
^Notebook
matches any tool whose name starts with
Notebook
;
mcp__memory__.*
matches every tool from the
memory
server
A matcher on the regular-expression path is tested with JavaScript’s
RegExp.prototype.test
, which succeeds on a match anywhere in the value.
Edit.*
matches both
Edit
and
NotebookEdit
; wrap the pattern in
^
and
$
, as in
^Edit$
, when you need a whole-string match.
Comma separators and the surrounding whitespace tolerance require Claude Code v2.1.191 or later.
Hyphens in the exact-match set require Claude Code v2.1.195 or later. On earlier versions a hyphenated name like
code-reviewer
is evaluated as an unanchored regular expression, so it also fires for
senior-code-reviewer
; anchor it as
^code-reviewer$
on those versions to match only that name.
FileChanged
and
StopFailure
use a narrower exact-match set of letters, digits,
_
, and
|
only. A hyphen, space, or comma in a matcher for those two events keeps it on the regular-expression path, and only
|
separates alternatives. Every other event with matcher support in the table that follows accepts
|
or
,
.
The
FileChanged
event doesn’t follow these rules when building its watch list. See
FileChanged
.
Each event type matches on a different field:
Event
What the matcher filters
Example matcher values
PreToolUse
,
PostToolUse
,
PostToolUseFailure
,
PermissionRequest
,
PermissionDenied
tool name
Bash
,
Edit|Write
,
mcp__.*
SessionStart
how the session started
startup
,
resume
,
clear
,
compact
,
fork
Setup
which CLI flag triggered setup
init
,
maintenance
SessionEnd
why the session ended
clear
,
resume
,
logout
,
prompt_input_exit
,
other
Notification
notification type
permission_prompt
,
idle_prompt
,
auth_success
,
elicitation_dialog
,
elicitation_url_dialog
,
elicitation_complete
,
elicitation_response
,
agent_needs_input
,
agent_completed
,
quota_auto_resume_fired
,
quota_auto_resume_stale
,
quota_auto_resume_disabled
SubagentStart
agent type
general-purpose
,
Explore
,
Plan
, custom agent names, or plugin-scoped names like
^my-plugin:reviewer$
PreCompact
,
PostCompact
what triggered compaction
manual
,
auto
PreModelSwitch
,
PostModelSwitch
canonical name of the model the session switches to, as described under
PreModelSwitch
claude-opus-5
,
claude-opus-4-6|claude-opus-5
,
.*opus.*
SubagentStop
agent type
same values as
SubagentStart
ConfigChange
configuration source
user_settings
,
project_settings
,
local_settings
,
policy_settings
,
skills
CwdChanged
no matcher support
always fires on every directory change
DirectoryAdded
how the directory was added
slash_command
,
register_repo_root
FileChanged
literal filenames to watch (see
FileChanged
)
.envrc|.env
StopFailure
error type
rate_limit
,
overloaded
,
authentication_failed
,
oauth_org_not_allowed
,
billing_error
,
invalid_request
,
model_not_found
,
server_error
,
max_output_tokens
,
unknown
InstructionsLoaded
load reason
session_start
,
nested_traversal
,
path_glob_match
,
include
,
compact
UserPromptExpansion
command name
your skill or command names
Elicitation
MCP server name
your configured MCP server names
ElicitationResult
MCP server name
same values as
Elicitation
UserPromptSubmit
,
PostToolBatch
,
Stop
,
TeammateIdle
,
TaskCreated
,
TaskCompleted
,
WorktreeCreate
,
WorktreeRemove
,
MessageDisplay
no matcher support
always fires on every occurrence
For most events, Claude Code evaluates the matcher against a field from the
JSON input
it sends to your hook on stdin. For tool events, that field is
tool_name
. For
PreModelSwitch
and
PostModelSwitch
, Claude Code evaluates the matcher against the canonical name it derives from
to_model
, as described under
PreModelSwitch
. Each
hook event
section lists the full set of matcher values and the input schema for that event.
This example runs a linting script only when Claude writes or edits a file:
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Edit|Write"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"/path/to/lint-check.sh"
}
]
}
]
}
}
If you add a
matcher
field to an event without matcher support, it is silently ignored.
For tool events, you can filter more narrowly by setting the
if
field
on individual hook handlers.
if
uses
permission rule syntax
to match against the tool name and arguments together, so
"Bash(git *)"
runs when any subcommand of the Bash input matches
git *
and
"Edit(*.ts)"
runs only for TypeScript files.
​
Match MCP tools
MCP
server tools appear as regular tools in tool events (
PreToolUse
,
PostToolUse
,
PostToolUseFailure
,
PermissionRequest
,
PermissionDenied
), so you can match them the same way you match any other tool name.
MCP tools follow the naming pattern
mcp__<server>__<tool>
, for example:
mcp__memory__create_entities
: Memory server’s create entities tool
mcp__filesystem__read_file
: Filesystem server’s read file tool
mcp__github__search_repositories
: GitHub server’s search tool
To match every tool from a server, append
.*
to the server prefix. The
.*
is required: a matcher like
mcp__memory
or
mcp__brave-search
contains only exact-match characters, so it is compared as an exact string and matches no tool.
mcp__memory__.*
matches all tools from the
memory
server
mcp__brave-search__.*
matches all tools from a server whose name contains a hyphen
mcp__.*__write.*
matches any tool whose name starts with
write
from any server
Hyphens in the exact-match set require Claude Code v2.1.195 or later. On earlier versions a bare hyphenated prefix like
mcp__brave-search
is evaluated as an unanchored regular expression and matches every tool from that server. The
mcp__brave-search__.*
form works on every version.
Tools from a
plugin-bundled MCP server
use a scoped server segment that includes the plugin name:
mcp__plugin_<plugin-name>_<server-name>__<tool>
. A matcher written against the bare server key never fires for these tools. For a plugin named
my-plugin
that bundles a server under the key
db
, a
query
tool appears as
mcp__plugin_my-plugin_db__query
, so the matcher for every tool from that server is
mcp__plugin_my-plugin_db__.*
. Use the same scoped tool name in a handler’s
if
field
. See
Plugin-provided MCP servers
for how the scoped name is built.
This example logs all memory server operations and validates write operations from any MCP server:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"mcp__memory__.*"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"echo 'Memory operation initiated' >> ~/mcp-operations.log"
}
]
},
{
"matcher"
:
"mcp__.*__write.*"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"/home/user/scripts/validate-mcp-write.py"
}
]
}
]
}
}
​
Hook handler fields
Each object in the inner
hooks
array is a hook handler: the shell command, HTTP endpoint, MCP tool, LLM prompt, or agent that runs when the matcher matches. There are five types:
Command hooks
(
type: "command"
): run a shell command. Your script receives the event’s
JSON input
on stdin and communicates results back through exit codes and stdout.
HTTP hooks
(
type: "http"
): send the event’s JSON input as an HTTP POST request to a URL. The endpoint communicates results back through the response body using the same
JSON output format
as command hooks.
MCP tool hooks
(
type: "mcp_tool"
): call a tool on an already-connected
MCP server
. The tool’s text output is treated like command-hook stdout.
Prompt hooks
(
type: "prompt"
): send a prompt to a Claude model for single-turn evaluation. The model returns its decision as JSON. See
Prompt-based hooks
.
Agent hooks
(
type: "agent"
): spawn a subagent that can use tools like Read, Grep, and Glob to verify conditions before returning a decision. Agent hooks are experimental and may change. See
Agent-based hooks
.
All matching hooks run in parallel. If you define the same handler in more than one settings file, it runs once. A plugin’s or skill’s copy of the same handler stays separate.
Handlers run in the current directory with Claude Code’s environment. If the current directory no longer exists, for example a worktree or temp directory that another shell deleted mid-session, Claude Code runs command hooks from the first of these that still exists: the directory the session started in, the project root, your home directory, or the system temp directory. Claude Code records a warning naming the fallback directory in the
debug log
.
The
$CLAUDE_CODE_REMOTE
environment variable is
"true"
in remote web environments and not set in the local CLI. Claude Code v2.1.199 and later sets
$CLAUDE_CODE_BRIDGE_SESSION_ID
to the
Remote Control
session ID while the local session has an active Remote Control connection.
​
Common fields
These fields apply to all hook types:
Field
Required
Description
type
yes
"command"
,
"http"
,
"mcp_tool"
,
"prompt"
, or
"agent"
if
no
Permission rule syntax to filter when this hook runs, such as
"Bash(git *)"
or
"Edit(*.ts)"
. The hook command only runs if the tool call matches the pattern. See the
Bash matching table
below for how Bash patterns evaluate against subcommands,
$()
, and backticks. Only evaluated on tool events:
PreToolUse
,
PostToolUse
,
PostToolUseFailure
,
PermissionRequest
, and
PermissionDenied
. On other events, a hook with
if
set never runs. Uses the same syntax as
permission rules
timeout
no
Seconds before canceling. Claude Code doesn’t enforce it on a command hook you run with
async: true
. Defaults: 600 for
command
,
http
, and
mcp_tool
; 30 for
prompt
; 60 for
agent
. Claude Code lowers the
command
,
http
, and
mcp_tool
default to 30 on
UserPromptSubmit
,
PreModelSwitch
, and
PostModelSwitch
, and to 10 on
MessageDisplay
.
SessionEnd
hooks share a 1.5-second budget; if your settings set a longer per-hook
timeout
, Claude Code raises the budget to match, up to 60 seconds
statusMessage
no
Custom spinner message displayed while the hook runs
once
no
If
true
, Claude Code removes the hook after its first successful run. A run that fails, blocks with exit code 2, or times out leaves the hook in place, so it runs again on the next matching event. Only honored for hooks declared in
skill frontmatter
; ignored in settings files and agent frontmatter
The
if
field holds exactly one permission rule. There is no
&&
,
||
, or list syntax for combining rules; to apply multiple conditions, define a separate hook handler for each.
In an
if
condition for a file tool, a single-segment directory pattern like
"Edit(src/**)"
matches only the
src
directory in the working directory and the files under it. To match a directory named
src
at any depth, write
"Edit(**/src/**)"
. Before v2.1.214,
"Edit(src/**)"
matched a directory named
src
at any depth under the working directory.
For Bash patterns, whether your hook command runs depends on the shape of the pattern and the Bash command Claude is invoking. Leading
VAR=value
assignments are stripped before matching.
if
pattern
Bash command
Hook runs?
Why
Bash(git *)
FOO=bar git push
yes
leading assignments are stripped;
git push
matches
Bash(git *)
npm test && git push
yes
each subcommand is checked;
git push
matches
Bash(rm *)
echo $(rm -rf /)
yes
commands inside
$()
and backticks are checked;
rm -rf /
matches
Bash(rm *)
echo $(date)
no
no subcommand matches
rm *
Bash(cat *)
echo before $(date) after
no
a substitution can sit at any argument position, so the full command and
date
are both checked; neither matches
cat *
Bash(git *)
$TOOL git push
yes
Claude Code can’t tell what the command name expands to, so it runs the hook
Bash(git push *)
echo $(date)
yes
patterns that specify more than the command name run the hook anyway on
$()
, backticks, or
$VAR
When Claude Code can’t determine which commands the Bash input runs, it runs your hook regardless of the pattern. Because the
if
filter is best-effort, use the
permission system
rather than a hook to enforce a hard allow or deny.
​
Command hook fields
In addition to the
common fields
, command hooks accept these fields:
Field
Required
Description
command
yes
Shell command to execute. With
args
, the executable to spawn directly. See
Exec form and shell form
args
no
Argument list. When present,
command
is resolved as an executable and spawned directly with
args
as the argument vector, with no shell involved. See
Exec form and shell form
async
no
If
true
, runs in the background without blocking. See
Run hooks in the background
asyncRewake
no
If
true
, runs in the background and wakes Claude on exit code 2. The hook’s stderr, or stdout if stderr is empty, is shown to Claude as a system reminder so it can react to a long-running background failure
shell
no
Shell to use for this hook. Accepts
"bash"
or
"powershell"
. Defaults to
"bash"
, or to
"powershell"
on Windows when Git Bash isn’t installed. Setting
"powershell"
runs the command via PowerShell on Windows. Does not require
CLAUDE_CODE_USE_POWERSHELL_TOOL
since hooks spawn PowerShell directly. Ignored when
args
is set
Exec form and shell form
A command hook runs as exec form when
args
is set, and shell form when
args
is omitted. Set
args
whenever the hook references a
path placeholder
, since each element is passed as one argument with no quoting. Omit
args
when you need shell features like pipes or
&&
, or when neither concern applies.
Exec form
runs when
args
is present. Claude Code resolves
command
as an executable on
PATH
and spawns it directly with
args
as the argument vector. There is no shell, so each
args
element is one argument exactly as written, and path placeholders like
${CLAUDE_PLUGIN_ROOT}
are substituted into
command
and into each
args
element as plain strings. Special characters such as apostrophes,
$
, and backticks pass through verbatim because there is no shell to interpret them. No shell tokenization happens on any platform.
Shell form
runs when
args
is absent. The
command
string is passed to a shell:
sh -c
on macOS and Linux, Git Bash on Windows, or PowerShell when Git Bash isn’t installed. Set the
shell
field to choose explicitly. The shell tokenizes the string, expands variables, and interprets pipes,
&&
, redirects, and globs.
On Windows, exec form requires
command
to resolve to a real executable such as a
.exe
. The
.cmd
and
.bat
shims that npm, npx, eslint, and other tools install in
node_modules/.bin
are not executables and can’t be spawned without a shell. To run them in exec form, invoke the underlying script with
node
directly, for example
"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/node_modules/eslint/bin/eslint.js"]
. The
node
plus script-path pattern works on every platform because
node.exe
is a real binary. To run a
.cmd
or
.bat
shim by name, use shell form.
This example runs a Node script bundled with a plugin. Exec form passes the resolved script path as one argument with no quoting:
{
"type"
:
"command"
,
"command"
:
"node"
,
"args"
: [
"${CLAUDE_PLUGIN_ROOT}/scripts/format.js"
,
"--fix"
]
}
The equivalent shell form needs quoting to handle paths with spaces or special characters:
{
"type"
:
"command"
,
"command"
:
"node
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/format.js --fix"
}
Both forms support the same
path placeholders
, and both export them as the environment variables
CLAUDE_PROJECT_DIR
,
CLAUDE_PLUGIN_ROOT
, and
CLAUDE_PLUGIN_DATA
on the spawned process, so a script can read
process.env.CLAUDE_PLUGIN_ROOT
regardless of how it was launched.
Plugin hooks additionally substitute
${user_config.*}
values, in exec form only: the value is substituted into
command
and into each
args
element as a plain string, so no shell re-parses it.
A shell-form plugin hook whose
command
references
${user_config.*}
fails with an
error
instead of running. To use an option value from a shell-form hook, read the
$CLAUDE_PLUGIN_OPTION_<KEY>
environment variable, such as
$CLAUDE_PLUGIN_OPTION_WEBHOOK_URL
for a
webhook_url
option, or set
args
to switch the hook to exec form. Before v2.1.207, shell-form plugin hook commands also substituted
${user_config.*}
.
In exec form,
command
is the executable name or path only. If
command
is a bare name with no path separator and contains whitespace alongside
args
, Claude Code logs a warning because the spawn will fail: there is no executable named
node script.js
. Move the extra tokens into
args
. Absolute paths with spaces, such as
C:\Program Files\nodejs\node.exe
, are a single valid executable and don’t trigger the warning.
​
HTTP hook fields
In addition to the
common fields
, HTTP hooks accept these fields:
Field
Required
Description
url
yes
URL to send the POST request to
headers
no
Additional HTTP headers as key-value pairs. Values support environment variable interpolation using
$VAR_NAME
or
${VAR_NAME}
syntax. Only variables listed in
allowedEnvVars
are resolved
allowedEnvVars
no
List of environment variable names that may be interpolated into header values. References to unlisted variables are replaced with empty strings. Required for any env var interpolation to work
Claude Code sends the hook’s
JSON input
as the POST request body with
Content-Type: application/json
. The response body uses the same
JSON output format
as command hooks.
Error handling differs from command hooks; see
HTTP response handling
.
This example sends
PreToolUse
events to a local validation service, authenticating with a token from the
MY_TOKEN
environment variable:
{
"hooks"
: {
"PreToolUse"
: [
{
"matcher"
:
"Bash"
,
"hooks"
: [
{
"type"
:
"http"
,
"url"
:
"http://localhost:8080/hooks/pre-tool-use"
,
"timeout"
:
30
,
"headers"
: {
"Authorization"
:
"Bearer $MY_TOKEN"
},
"allowedEnvVars"
: [
"MY_TOKEN"
]
}
]
}
]
}
}
​
MCP tool hook fields
In addition to the
common fields
, MCP tool hooks accept these fields:
Field
Required
Description
server
yes
Name of a configured MCP server. For a
plugin-bundled server
, this is the scoped name
plugin:<plugin-name>:<server-name>
, such as
plugin:my-plugin:db
, not the bare server key. The server must already be connected; the hook never triggers an OAuth or connection flow
tool
yes
Name of the tool to call on that server
input
no
Arguments passed to the tool. String values support
${path}
substitution from the hook’s
JSON input
, such as
"${tool_input.file_path}"
Claude Code reads the tool’s text content the same way it reads command-hook stdout, following the
parsing rule under exit code 0
. If the named server is not connected, or the tool returns
isError: true
, the hook produces a non-blocking error and execution continues.
MCP tool hooks are available on every hook event once Claude Code has connected to your MCP servers.
SessionStart
and
Setup
typically fire before servers finish connecting, so hooks on those events should expect the “not connected” error on first run.
This example calls the
security_scan
tool on the
my_server
MCP server after each
Write
or
Edit
, passing the edited file’s path:
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"mcp_tool"
,
"server"
:
"my_server"
,
"tool"
:
"security_scan"
,
"input"
: {
"file_path"
:
"${tool_input.file_path}"
}
}
]
}
]
}
}
​
Prompt and agent hook fields
In addition to the
common fields
, prompt and agent hooks accept these fields:
Field
Required
Description
prompt
yes
Prompt text to send to the model. Use
$ARGUMENTS
as a placeholder for the hook input JSON. Escape with a backslash to include literal text:
\$1.00
renders as
$1.00
model
no
Model to use for evaluation. Defaults to a fast model
​
Reference scripts by path
Use these placeholders to reference hook scripts relative to the project or plugin root, regardless of the working directory when the hook runs:
${CLAUDE_PROJECT_DIR}
: the project root where the session started. Claude Code also sets this variable in the environment of
stdio MCP servers
and plugin LSP servers.
${CLAUDE_PLUGIN_ROOT}
: the plugin’s installation directory, for scripts bundled with a
plugin
. Changes on each plugin update.
${CLAUDE_PLUGIN_DATA}
: the plugin’s
persistent data directory
, for dependencies and state that should survive plugin updates.
Worktrees are different.
If Claude enters a
worktree
during the session, Claude Code keeps
${CLAUDE_PROJECT_DIR}
where it was and passes the worktree path to your hooks a different way:
${CLAUDE_PROJECT_DIR}
stays put
: it still points at the project root where the session started, so a command such as
${CLAUDE_PROJECT_DIR}/.claude/hooks/check-style.sh
still runs the script in the main checkout.
cwd
follows Claude
: the
cwd
field in the hook’s
input JSON
is the worktree root after Claude enters a worktree, and the new directory after Claude runs
cd
. Read it when a hook needs to know which directory Claude is working in.
Prefer
exec form
for any hook that references a path placeholder. In shell form, wrap each placeholder in double quotes.
Project scripts
Plugin scripts
This example uses
${CLAUDE_PROJECT_DIR}
to run a style checker from the project’s
.claude/hooks/
directory after any
Write
or
Edit
tool call:
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"${CLAUDE_PROJECT_DIR}/.claude/hooks/check-style.sh"
,
"args"
: []
}
]
}
]
}
}
Define plugin hooks in
hooks/hooks.json
with an optional top-level
description
field. When a plugin is enabled, its hooks merge with your user and project hooks.
This example runs a formatting script bundled with the plugin:
{
"description"
:
"Automatic code formatting"
,
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"${CLAUDE_PLUGIN_ROOT}/scripts/format.sh"
,
"args"
: [],
"timeout"
:
30
}
]
}
]
}
}
See the
plugin components reference
for details on creating plugin hooks.
​
Hooks in skills and agents
In addition to settings files and plugins, hooks can be defined directly in
skills
and
subagents
using frontmatter, in the same configuration format as settings-based hooks. How long Claude Code keeps them registered depends on the component:
Subagent hooks
: Claude Code runs them only while that subagent is running and removes them when it finishes. Claude Code converts a
Stop
hook here to
SubagentStop
, the event it fires when a subagent completes.
Skill hooks
: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session, on turns after the skill’s own turn as well. To have Claude Code remove a hook after its first successful run instead, set
once: true
on it.
All hook events are supported.
This skill defines a
PreToolUse
hook that runs a security validation script before each
Bash
command:
---
name
:
secure-operations
description
:
Perform operations with security checks
hooks
:
PreToolUse
:
-
matcher
:
"Bash"
hooks
:
-
type
:
command
command
:
"./scripts/security-check.sh"
---
Subagents use the same format in their YAML frontmatter.
Frontmatter hooks in a project skill follow the same
workspace trust rule as hooks in settings files
. Claude Code registers them when you or Claude invoke the skill, including in a
-p
run in a folder you haven’t trusted.
Frontmatter hooks in a project subagent run only after you accept the
workspace trust dialog
for the folder the agent file came from. A
-p
session doesn’t count as accepting it.
What runs before you trust a folder
compares this with the settings-file rule, and the subagents page lists
which scopes are exempt
. Before v2.1.218, these hooks could run from folders you hadn’t trusted.
​
The
/hooks
menu
Type
/hooks
in Claude Code to open a read-only browser for your configured hooks. The menu shows every hook event with a count of configured hooks, lets you drill into matchers, and shows the full details of each hook handler. Use it to verify configuration, check which settings file a hook came from, or inspect a hook’s command, prompt, or URL.
The menu displays all five hook types:
command
,
prompt
,
agent
,
http
, and
mcp_tool
. Each hook is labeled with a
[type]
prefix and a source indicating where it was defined:
User Settings
: from
~/.claude/settings.json
Project Settings
: from
.claude/settings.json
Local Settings
: from
.claude/settings.local.json
Plugin Hooks
: from a plugin’s
hooks/hooks.json
Session Hooks
: registered in memory for the current session
Selecting a hook opens a detail view showing its event, matcher, type, source file, and the full command, prompt, or URL. The menu is read-only: to add, modify, or remove hooks, edit the settings JSON directly or ask Claude to make the change.
​
Disable or remove hooks
To remove a hook, delete its entry from the settings JSON file.
To temporarily disable all hooks without removing them, set
"disableAllHooks": true
in your settings file. Claude Code reads the value left after
settings precedence
applies, so a
"disableAllHooks": false
in a project’s
.claude/settings.json
overrides a
true
in your user settings. To turn hooks off for one run whatever the project’s settings say, pass
--settings '{"disableAllHooks": true}'
, which takes precedence over project and local settings. There is no way to disable an individual hook while keeping it in the configuration.
The
disableAllHooks
setting respects the managed settings hierarchy. If an administrator has configured hooks through managed policy settings,
disableAllHooks
set in user, project, or local settings can’t disable those managed hooks. Only
disableAllHooks
set at the managed settings level can disable managed hooks. For the full reach of each level, see
disableAllHooks
.
Direct edits to hooks in settings files are normally picked up automatically by the file watcher.
​
Hook input and output
Command hooks receive JSON data via stdin and communicate results through exit codes, stdout, and stderr. HTTP hooks receive the same JSON as the POST request body and communicate results through the HTTP response body. This section covers fields and behavior common to all events. Each event’s section under
Hook events
includes its specific input schema and decision control options.
On macOS and Linux, command hooks run in their own session without a controlling terminal. The hook process and any child processes can’t open
/dev/tty
or send escape sequences directly to the Claude Code interface. Windows has no
/dev/tty
.
To surface a message to the user on any platform, return
systemMessage
in JSON output. Some events discard it or deliver it elsewhere, and each
event’s section
says so. To trigger a desktop notification, set a window title, or ring the bell, return
terminalSequence
instead.
​
Common input fields
Hook events receive these fields as JSON, in addition to event-specific fields documented in each
hook event
section. For command hooks, this JSON arrives via stdin. For HTTP hooks, it arrives as the POST request body.
Field
Description
session_id
Current session identifier
prompt_id
UUID identifying the user prompt currently being processed. Matches the
prompt.id
attribute on OpenTelemetry events
, so you can correlate hook output with telemetry for a single prompt. Absent until the first user input. Requires Claude Code v2.1.196 or later
transcript_path
Path to conversation JSON. The transcript file is written asynchronously and may lag the in-memory conversation, so it may not yet include the current turn’s most recent messages when a hook fires. Hooks that need the final assistant text of the current turn should use
last_assistant_message
on
Stop
and
SubagentStop
instead of reading the transcript
cwd
Current working directory when the hook is invoked
permission_mode
Current
permission mode
:
"default"
,
"plan"
,
"acceptEdits"
,
"auto"
,
"dontAsk"
, or
"bypassPermissions"
. The mode labeled
Manual
arrives as
"default"
, never as
"manual"
, so scripts that match
"default"
keep working. Not all events receive this field. Check the JSON example in each
hook event
section
effort
Object with a
level
field holding the
effort level
in effect when the hook runs:
"low"
,
"medium"
,
"high"
,
"xhigh"
, or
"max"
. If you set a level the active model doesn’t support,
level
reports the level Claude Code ran instead;
Adjust effort level
says how it picks that level. Ultracode is not a distinct level and reports as
"xhigh"
. The object matches the
status line
effort
field. Present for events that fire within a tool-use context, such as
PreToolUse
,
PostToolUse
,
Stop
, and
SubagentStop
, when the current model supports the effort parameter. The level is also available to hook commands and the Bash tool as the
$CLAUDE_EFFORT
environment variable.
hook_event_name
Name of the event that fired
When running with
--agent
or inside a subagent, two additional fields are included:
Field
Description
agent_id
Unique identifier for the subagent. Present only when the hook fires inside a subagent call. Use this to distinguish subagent hook calls from main-thread calls.
agent_type
Agent name (for example,
"Explore"
or
"security-reviewer"
). Present when the session uses
--agent
or the hook fires inside a subagent. For subagents, the subagent’s type takes precedence over the session’s
--agent
value. See
SubagentStart
for the values custom and plugin subagents report and how to write a matcher against a plugin-scoped name.
Only
SessionStart
hooks can receive a
model
field, and Claude Code doesn’t always include it.
PreModelSwitch
and
PostModelSwitch
hooks receive
from_model
and
to_model
instead, so use a PostModelSwitch hook to follow the model as it changes during a session.
There is no
$CLAUDE_MODEL
environment variable. The hook can read
$ANTHROPIC_MODEL
if you set it in your shell, but that value doesn’t change when you switch models with
/model
during a session.
A hook process inherits the parent environment, apart from the
OTEL_*
exporter variables that Claude Code
removes from every subprocess it spawns
, including hooks.
For example, a
PreToolUse
hook for a Bash command receives this on stdin:
{
"session_id"
:
"abc123"
,
"prompt_id"
:
"550e8400-e29b-41d4-a716-446655440000"
,
"transcript_path"
:
"/home/user/.claude/projects/.../transcript.jsonl"
,
"cwd"
:
"/home/user/my-project"
,
"permission_mode"
:
"default"
,
"hook_event_name"
:
"PreToolUse"
,
"tool_name"
:
"Bash"
,
"tool_input"
: {
"command"
:
"npm test"
,
"description"
:
"Run test suite"
,
"timeout"
:
120000
,
"run_in_background"
:
false
},
"tool_use_id"
:
"toolu_01ABC123..."
}
The
tool_name
,
tool_input
, and
tool_use_id
fields are event-specific. Each
hook event
section documents the additional fields for that event.
​
Exit code output
The exit code from your hook command tells Claude Code whether the action should proceed, be blocked, or be ignored. The exit code doesn’t act alone. Claude Code reads
JSON output fields
from stdout on every exit code, not just 0, and for events that use the standard decision model, a parsed object that passes schema validation takes effect alongside the code. Exit 2’s block is the one outcome JSON can’t override.
Two tables own the per-event exceptions:
Exit code 2 behavior per event
says what exit codes do for each event, and
Decision control
says which decision fields each event honors. Universal fields such as
systemMessage
work across most events and are listed in the
JSON output
table.
​
Exit code 0
Exit 0 means success, and is the intended exit code when you print JSON for structured control.
For most events, Claude Code writes stdout to the debug log and doesn’t show it in the transcript. The exceptions are
UserPromptSubmit
,
UserPromptExpansion
,
SessionStart
, and
PostModelSwitch
, where Claude Code adds plain-text stdout as context that Claude can see and act on.
Whether Claude Code reads your stdout as
JSON output
or as plain text depends on how it starts and ends, ignoring surrounding whitespace:
Starts with
{
and ends with
}
: Claude Code parses it as JSON. When the output is two or more lines that each parse as JSON on their own, and no line is a
JSON output
object that sets a field, Claude Code treats the whole output as plain text. When one of those lines does set a field, the whole output is a parse failure, described below.
Starts with
{
but doesn’t end with
}
: Claude Code treats it as plain text.
Starts with anything else
: Claude Code treats it as plain text, a JSON array or a quoted JSON string included.
For events that use the standard decision model, exit 0 with a parsed object that fails schema validation is a non-blocking error: the action proceeds, and the transcript shows a
<hook name> hook error
notice with the validation message. The same happens on any exit code other than 2, while
exit 2 still blocks
.
For events that use the standard decision model, when Claude Code tries to parse your stdout as JSON and can’t, it reports a non-blocking error on every exit code other than 2. The transcript shows a
<hook name> hook error
notice with the parse message. On the events that add plain-text stdout as context, Claude Code doesn’t add the text. Before v2.1.248, Claude Code treated that stdout as plain text.
Stderr from a hook that exits 0 goes to the debug log only, never the transcript, and Claude never sees it. To read it yourself, enable
debug logging
. To surface a warning to Claude from a
PostToolUse
or
PostToolUseFailure
hook, exit 2 instead so
Claude sees the stderr
even though the tool already ran.
​
Exit code 2
Exit 2 means a blocking error. On
events that can block
, exit 2 blocks whether or not you print JSON: even a JSON
permissionDecision
of
"allow"
can’t override it. Claude Code still reads any valid
JSON output
on stdout. On
Elicitation
and
ElicitationResult
, an exit-2 hook’s
hookSpecificOutput
is ignored.
The blocking message is the reason from your JSON’s blocking decision when it makes one, and your stderr text otherwise. What the block does varies by event:
PreToolUse
blocks the tool call,
UserPromptSubmit
rejects the prompt, and so on.
Exit code 2 behavior per event
lists the effect for every event, and each event’s section says where the message goes.
A hook that exits 2 while printing JSON that fails
JSON output
schema validation still blocks: Claude Code uses stderr as the blocking reason and records the validation failure in the debug log. Before v2.1.214, Claude Code treated that combination as a non-blocking error and the action proceeded.
This script blocks
rm
commands by exiting 2 and leaves every other command to the normal permission flow:
#!/bin/bash
# Reads JSON input from stdin, checks the command
input
=
$(
cat
)
command
=
$(
jq
-r
'.tool_input.command'
<<<
"
$input
"
)
if
[[
"
$command
"
==
rm
*
]];
then
echo
"Blocked: rm commands are not allowed"
>&2
exit
2
# Blocking error: tool call is prevented
fi
exit
0
# No decision: the normal permission flow applies
​
Other exit codes
Any other exit code doesn’t block on its own for most hook events. What happens depends on your stdout:
With a parsed object that passes schema validation, for events that use the standard decision model, Claude Code ignores the exit code and the JSON alone decides the outcome:
Each field the event supports is honored, including
permissionDecision
,
additionalContext
,
updatedInput
, and
systemMessage
, and the hook isn’t reported as an error.
Decision control
lists the decision fields per event; universal fields like
systemMessage
follow the
JSON output
table.
With a parsed object that fails schema validation, for events that use the standard decision model, it’s the same non-blocking error as
on exit 0
: the action proceeds, and the
<hook name> hook error
notice carries the validation message.
With stdout that Claude Code
tries to parse as JSON
and can’t, Claude Code reports the same non-blocking error as on exit 0 for events that use the standard decision model. The action proceeds, and the notice carries the parse message.
With stdout that Claude Code
treats as plain text
, or with empty stdout, it’s a non-blocking error for most hook events: the action proceeds, and the transcript shows a
<hook name> hook error
notice followed by the first line of stderr, prefixed with
Failed with non-blocking status code:
. To capture the full stderr, enable
debug logging
.
Events outside the standard decision model keep their own rows in the
per-event table
:
WorktreeCreate
fails creation on any nonzero exit no matter what your JSON says, and events that discard hook output entirely, like
StopFailure
, ignore your JSON on every exit code, apart from side-effect fields like
terminalSequence
, which still fire.
A hook that can’t start lands in the same non-blocking bucket. When the script path doesn’t exist or isn’t executable, the shell exits with a code like 127 and you see the same notice with the interpreter’s message, for example
Failed with non-blocking status code: /bin/sh: /path/to/hook.sh: No such file or directory
. For most hook events, the action proceeds. When you set

## Source (permissions): https://docs.claude.com/en/docs/claude-code/permissions

Configure permissions - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Claude Code supports fine-grained permissions so that you can specify exactly what the agent is allowed to do and what it can’t. You can check permission settings into version control to share them with every developer in your organization, and each developer can customize their own.
​
Permission system
Claude Code uses a tiered permission system to balance power and safety. The table shows, for each tool type, whether Manual mode asks before the action runs. The other
permission modes
change which of these ask you; in auto mode a classifier reviews actions instead of you, and
how the classifier evaluates actions
lists which ones it sees.
Tool type
Example
Approval required
”Yes, and don’t ask again” behavior
Read-only
File reads, Grep
No, within the
working directory and additional directories
N/A
Bash commands
Shell execution
Yes, except a built-in set of
read-only commands
Permanently per repository and command
File modification
Edit/write files
Yes
Until session end
Web fetch
WebFetch
Yes, except a built-in set of
preapproved documentation domains
Permanently per repository and domain
Web search
WebSearch
Yes
Permanently per repository
When you choose “Yes, and don’t ask again” and the approval saves permanently, such as for a Bash command or a WebFetch domain, Claude Code saves the rule to
.claude/settings.local.json
at the root of the git repository, resolved through
worktrees
to the main checkout. The rule applies to future sessions anywhere in that repository, including sessions started in subdirectories and in worktrees. A file-modification approval isn’t saved to the file: as the table shows, it lasts until the session ends. In some cases, such as outside a git repository or on Windows, Claude Code doesn’t use the repository root;
Where Claude Code looks for each file
lists those cases and where it saves the rule instead.
Before v2.1.211, Claude Code always saved the rule in the starting directory, so an approval granted in a worktree or subdirectory didn’t apply to the rest of the repository. Rules that earlier versions saved in a subdirectory or worktree still apply to sessions started there.
Sometimes a permission prompt offers only a one-time approval, with no “don’t ask again” option and no option to allow the action for the rest of the session. Claude Code offers those options only when the prompt can show you everything they would allow, so a rule you save from a prompt covers only what its option named.
When the directory you started Claude Code in is what makes the option’s label too long, Claude Code shortens it in the label, replacing your home directory with
~
and then the end of the path with
…
, and keeps the option. You still save the same rule. Claude Code leaves the options out in three cases:
Command or edit:
too large to show in full.
Commands or paths the rule would cover:
the label can’t fit them all.
Starting directory too long, not shortened:
it contains characters Claude Code can’t display safely, or even its start doesn’t fit.
Approve the action once, or add the rule yourself in
/permissions
.
On a Bash or PowerShell permission prompt, press
Ctrl+E
to show an explanation of the command: what it does, why Claude is running it, and what could go wrong, labeled
Low risk
,
Med risk
, or
High risk
. Claude Code sends the command and Claude’s own description of the call to the model to generate the explanation only when you press
Ctrl+E
, not on every prompt. Showing the explanation doesn’t run the command; press
Ctrl+E
again to hide it.
To turn the shortcut off, set
permissionExplainerEnabled
to
false
in
~/.claude.json
.
​
Add a comment when you answer a permission prompt
You can attach a note to Claude when you approve or deny a single action. On most permission prompts, including Bash, PowerShell, file, and MCP tool prompts, move to
Yes
or
No
and press
Tab
to open a comment field on that option. WebFetch and browser prompts don’t offer the field. The options that allow the action for the rest of the session or save a rule don’t take one either.
With the field open, type the comment and then press one of these keys:
Enter
: submits your answer with the comment attached. If you leave the field empty, Claude Code submits the answer without a comment.
Tab
: closes the field without answering. Claude Code keeps the text you typed and still sends it if you answer with that option.
Shift+Tab
: on a file prompt, such as an Edit or Write prompt, closes the field the same as
Tab
. Before v2.1.235, pressing
Shift+Tab
inside the field instead selected the option that allows the action for the rest of the session, so Claude Code approved the action for the rest of the session and discarded the comment.
Claude Code delivers the comment differently depending on how you answered:
Yes
: Claude Code runs the action, then sends your comment to Claude after the result.
No
: Claude Code sends your comment to Claude as the reason for the denial, and Claude continues working. If you select
No
without a comment on a prompt from the main conversation, Claude Code stops the turn.
​
Manage permissions
You can view and manage Claude Code’s tool permissions with
/permissions
. The dialog lists all permission rules and the
settings.json
file each rule comes from. You can open the dialog while Claude is working: when you add or remove a rule, Claude Code applies the change starting with Claude’s next tool call in the same turn. Before v2.1.234, Claude Code queued the command until the turn finished.
Allow
rules let Claude Code use the specified tool without manual approval.
Ask
rules prompt for confirmation whenever Claude Code tries to use the specified tool.
Deny
rules prevent Claude Code from using the specified tool.
Rules are evaluated in order: deny, then ask, then allow. The first match in that order determines the outcome, and rule specificity doesn’t change the order.
A broad deny rule like
Bash(aws *)
blocks every matching call, including calls that also match a narrower allow rule like
Bash(aws s3 ls)
, so a deny rule can’t carry allowlist exceptions. The same precedence applies between ask and allow: a matching ask rule prompts even when a more specific allow rule also matches the same call.
Deny rules behave differently depending on whether they name a tool or scope a pattern within one. A bare tool name like
Bash
removes the tool from Claude’s context entirely, so Claude never sees it. Bare-name removal applies to every tool except
EndConversation
: a deny rule can’t remove it while any other tool remains, and an ask rule never prompts for it. A scoped rule like
Bash(rm *)
leaves the tool available and blocks matching calls when Claude attempts them.
Permission rules are enforced by Claude Code, not by the model. Instructions in your prompt or
CLAUDE.md
shape what Claude tries to do, but they don’t change what Claude Code allows. To grant or revoke access, use
/permissions
, the rules described here, a
permission mode
, or a
PreToolUse hook
.
When
auto mode
is available to your session, the dialog also includes the
auto mode classifier rules
. Select the
Auto mode
tab to view them.
​
Permission modes
Claude Code supports several permission modes that control how it approves tool calls. See
Permission modes
for when to use each one. To change the mode sessions start in, set
defaultMode
in your
settings files
.
Which mode a session starts in
covers the built-in default for each plan and what the VS Code extension reads.
Mode
Description
default
Prompts for permission on first use of each tool. Labeled Manual in the CLI, the VS Code and JetBrains extensions, and the desktop app, and Claude Code accepts
manual
as an alias. The label and alias require Claude Code v2.1.200 or later. The desktop app’s label doesn’t depend on your CLI version
acceptEdits
Automatically accepts file edits and common filesystem commands such as
mkdir
,
touch
,
mv
, and
cp
for paths in the working directory or
additionalDirectories
plan
Claude reads files and runs read-only shell commands to explore but doesn’t edit your source files; with
auto mode
available, classifier-approved commands also run. Labeled Plan in the CLI and the VS Code extension
auto
Auto-approves tool calls with background safety checks that verify actions align with your request
dontAsk
Auto-denies tools unless pre-approved via
/permissions
or
permissions.allow
rules.
AskUserQuestion
, MCP tools marked
requiresUserInteraction
, and connector tools
your organization set to
ask
in sessions where that setting reaches Claude Code are denied even if you’ve allowed them
bypassPermissions
Skips permission prompts, except for the
actions no mode auto-approves
bypassPermissions
mode skips permission prompts, including for writes to
protected paths
such as
.git
and
.claude
. The
cross-session messaging safeguards
still apply. Only use this mode in isolated environments like containers or VMs where Claude Code can’t cause damage.
To prevent
bypassPermissions
or
auto
mode from being used, set
permissions.disableBypassPermissionsMode
or
permissions.disableAutoMode
to
"disable"
in any
settings file
. These are most useful in
managed settings
where they can’t be overridden.
​
Permission rule syntax
Permission rules follow the format
Tool
or
Tool(specifier)
.
​
Match all uses of a tool
To match all uses of a tool, use only the tool name without parentheses:
Rule
Effect
Bash
Matches all Bash commands
WebFetch
Matches all web fetch requests
Read
Matches all file reads
Bash(*)
is equivalent to
Bash
and matches all Bash commands. As a deny rule, both forms remove the tool from Claude’s context.
​
Use specifiers for fine-grained control
Add a specifier in parentheses to match specific tool uses:
Rule
Effect
Bash(npm run build)
Matches the exact command
npm run build
Read(./.env)
Matches reading the
.env
file in the current directory
WebFetch(domain:example.com)
Matches fetch requests to example.com
​
Match by input parameter
Deny and ask rules can match a top-level input parameter on any built-in tool with
Tool(param:value)
.
To match a parameter on an MCP tool, pass a deny rule with
--disallowedTools
. When Claude Code loads a settings file, it skips any
mcp__
rule that has parentheses. Claude Code lists the skipped rule in the invalid-settings dialog when an interactive session starts, and in
claude doctor
output.
A parameter rule matches when Claude calls the tool with that parameter set to that exact value. An allow rule for one parameter value wouldn’t establish that the call is safe overall, so allow rules continue to use each tool’s own specifier syntax. This works for any scalar parameter the tool accepts:
Rule
Matches
Agent(model:opus)
Agent calls that request the Opus model tier
Agent(isolation:worktree)
Agent calls that request a git worktree
Bash(run_in_background:true)
Bash calls that run in the background
Parameter matching follows these rules:
The parameter name must be a direct field of the tool’s input, such as
model
on the Agent tool. Fields nested inside an object or array are not matchable
Each rule names one parameter. To gate on both
model
and
isolation
, write two rules,
Agent(model:opus)
and
Agent(isolation:worktree)
, rather than combining them in one rule
The value supports
*
as a wildcard that matches any sequence of characters, so
Agent(isolation:*)
matches any explicit isolation value. Without
*
the match is exact
A parameter the model omits is never matched, so
Agent(model:*)
doesn’t match a call that leaves
model
unset
The value is compared against the literal input Claude sends, before any normalization.
Agent(model:opus)
matches the alias
opus
but not a full model ID. Run with
--verbose
to see the exact parameter names and values in each tool call
Whitespace around the colon is ignored
You can’t match a tool’s primary content field this way:
command
for Bash and PowerShell,
file_path
for Read, Edit, and Write,
path
for Grep and Glob,
notebook_path
for NotebookEdit, and
url
for WebFetch. A rule like
Bash(command:rm *)
would be bypassable by a compound command, so Claude Code ignores it and emits a startup warning. Use
Bash(rm *)
,
Read(./path)
, or
WebFetch(domain:host)
instead.
​
Wildcard patterns
A
*
in a Bash rule matches any text, including spaces, so one rule covers a family of commands. A rule with no
*
matches one exact command.
Put the
*
after the subcommand. In
git log --oneline main
,
git
is the program and
log
is the subcommand, the word that determines what the program does. Claude Code matches everything before the first
*
as written, so those words are what limit the rule:
Bash(git log *)
allows only
git log
commands, and
Bash(git *)
allows every git command. Claude Code
warns at startup
about an allow rule with a
*
before the subcommand, such as
Bash(git * main)
.
Write the command you want Claude to run without asking, and replace the parts that vary with
*
. With this configuration, Claude Code runs npm scripts and git commits without asking and refuses git push:
{
"permissions"
: {
"allow"
: [
"Bash(npm run *)"
,
"Bash(git commit *)"
],
"deny"
: [
"Bash(git push *)"
]
}
}
A
*
can go anywhere in the rule: at the start, in the middle, or at the end. Each row shows a rule, commands it matches, and nearby commands it doesn’t match:
You write
Matches
Doesn’t match
Bash(npm run build)
npm run build
npm run build --watch
Bash(npm run *)
npm run build
,
npm run test --watch
,
npm run
npm install
Bash(git log * main)
git log --oneline main
,
git log -5 main
,
git log --output=<file> main
git log main
,
git push origin main
Bash(git * main)
git merge main
,
git push origin main
,
git -c core.fsmonitor=<script> diff main
git log
Bash(* --version)
node --version
,
bash -c 'echo hi' --version
node -v
Bash(ls *)
ls -la
,
ls
lsof
Bash(ls*)
ls -la
,
lsof
Bash(* --help *)
npm --help x
npm --help
Three matching rules produce those rows:
The
*
stands in for whatever text is in its place.
In
Bash(git * main)
, it stands in for the subcommand, so Claude Code matches every git subcommand and every option before it. That includes
-c
, which makes git run a program you name. In
Bash(* --version)
, the
*
stands in for the program, so any program matches.
A
*
at the end, with a space before it, also matches the bare command.
Bash(ls *)
matches
ls
, and
Bash(git log *)
matches
git log
. That holds only when the trailing
*
is the rule’s only wildcard:
Bash(* --help *)
matches
npm --help x
but not
npm --help
.
The space before a trailing
*
is part of the rule.
Bash(ls *)
requires a space after
ls
, so
lsof
doesn’t match.
Bash(ls*)
has no space, so it matches
lsof
too.
The
:*
suffix is an equivalent way to write a trailing wildcard, so
Bash(ls:*)
matches the same commands as
Bash(ls *)
.
The permission dialog writes the space-separated form when you select “Yes, and don’t ask again” for a command prefix. The
:*
form is only recognized at the end of a pattern. In a pattern like
Bash(git:* push)
, the colon is treated as a literal character and won’t match git commands.
​
Tool name wildcards
Deny and ask rules also accept glob patterns in the tool-name position. The pattern must match the full tool name:
"*"
matches every tool, and
"mcp__*"
matches every MCP tool across all servers. A tool matched by a bare-name glob deny rule is removed from Claude’s context, the same as a bare tool name, including the
EndConversation
exception: a glob deny can’t remove it while any other tool remains, and a glob ask never prompts for it. This configuration denies every MCP tool:
{
"permissions"
: {
"deny"
: [
"mcp__*"
]
}
}
Allow rules accept tool-name globs only after a literal
mcp__<server>__
prefix. The server segment must be glob-free so the rule names a specific server you configured.
mcp__puppeteer__*
matches every tool from the
puppeteer
server, and
mcp__github__get_*
matches its
get_
tools. An unanchored allow glob such as
"*"
,
"B*"
, or
"mcp__*"
is skipped with a warning and doesn’t auto-approve anything.
A deny or ask rule whose tool name matches no known tool produces a startup warning to catch typos. Tool names containing
_
or
*
are exempt from the check.
The label shown for a tool in the transcript and permission dialog can differ from its canonical name. For example, the tool labeled
Stop Task
in the transcript has the canonical name
TaskStop
. Permission rules and
hook matchers
match the canonical name only, so a rule written as
Stop Task
doesn’t match. For deny and ask rules, the startup warning above catches the mismatch. Use the canonical names listed in the
tools reference
.
​
Tool-specific permission rules
​
Bash
Bash rules match the whole command text, with
*
standing in for any text.
Wildcard patterns
shows which commands each rule shape matches and where to put the
*
. The rest of this section covers how Claude Code matches compound commands, wrappers, read-only commands, and redirections.
​
Compound commands
Claude Code is aware of shell operators, so a rule like
Bash(safe-cmd *)
won’t give it permission to run the command
safe-cmd && other-cmd
. The recognized command separators are
&&
,
||
,
;
,
|
,
|&
,
&
, and newlines. A rule must match each subcommand independently.
When
&&
or
||
has nothing after it, such as in
npm test &&
, Claude Code treats the command as unparseable and doesn’t split it into subcommands for allow-rule matching, so a rule such as
Bash(npm *)
doesn’t approve it.
When you approve a compound command with “Yes, and don’t ask again”, Claude Code saves a separate rule for each subcommand that requires approval, rather than a single rule for the full compound string. For example, approving
git status && npm test
saves a rule for
npm test
, so future
npm test
invocations are recognized regardless of what precedes the
&&
. Subcommands like
cd
into a subdirectory generate their own Read rule for that path. Up to 5 rules may be saved for a single compound command.
​
Wrappers
Before matching Bash rules, Claude Code strips a fixed set of wrappers, so a rule like
Bash(npm test *)
also matches
timeout 30 npm test
. The stripped wrappers are
timeout
,
time
,
nice
,
nohup
, and
stdbuf
, plus the shell builtins
command
and
builtin
, and zsh’s
noglob
. Each runs its argument as the actual command. Two related forms aren’t stripped: the query form
command -v
, which looks up a command rather than running one, and zsh’s
nocorrect
.
Claude Code also strips a leading assignment of certain known-safe environment variables, so
Bash(npm test *)
matches
NODE_ENV=test npm test
. An allow rule won’t match past an assignment of any other variable. A deny or ask rule matches past any leading assignment, so
Bash(rm *)
in deny still matches
FOO=bar rm -rf tmp/
.
Bare
xargs
is also stripped, so
Bash(grep *)
matches
xargs grep pattern
. Stripping applies only when
xargs
has no flags: an invocation like
xargs -n1 grep pattern
is matched as an
xargs
command, so rules written for the inner command do not cover it.
This wrapper list is built in and is not configurable. Development environment runners such as
direnv exec
,
devbox run
,
mise exec
,
npx
, and
docker exec
are not in the list. Because these tools execute their arguments as a command, a rule like
Bash(devbox run *)
matches whatever comes after
run
, including
devbox run rm -rf .
. To approve work inside an environment runner, write a specific rule that includes both the runner and the inner command, such as
Bash(devbox run npm test)
. Add one rule per inner command you want to allow.
Exec wrappers such as
watch
,
setsid
,
ionice
, and
flock
can’t be auto-approved by a prefix rule like
Bash(watch *)
, so in Manual mode they always prompt. The same applies to
find
with
-exec
or
-delete
: a
Bash(find *)
rule doesn’t cover these forms. To approve a specific invocation, write an exact-match rule for the full command string.
​
Read-only commands
Claude Code recognizes a built-in set of Bash commands as read-only and runs them without a permission prompt in every mode. These include
ls
,
cat
,
echo
,
pwd
,
head
,
tail
,
grep
,
find
,
wc
,
which
,
diff
,
stat
,
du
,
cd
, and read-only forms of
git
. The set is not configurable; to require a prompt for one of these commands, add an
ask
or
deny
rule for it.
A redirect such as
ls > out.txt
adds a check on the target. See
Redirections
.
Unquoted glob patterns are permitted for commands whose every flag is read-only, so
ls *.ts
and
wc -l src/*.py
run without a prompt.
In Manual mode, commands from this set still prompt in these cases:
Unquoted globs for commands with write-capable flags
: commands with write-capable or exec-capable flags, such as
find
,
sort
,
sed
, and
git
, prompt when an unquoted glob is present, because the glob could expand to a flag like
-delete
.
docker
pointed at another daemon
: read-only forms of
docker
prompt when the command carries a flag that selects a different daemon, such as
-H
,
--context
, or Podman’s
--url
and
--connection
.
file
with path-opening flags
:
file
prompts when it passes
-m
/
--magic-file
or
-f
/
--files-from
, because those flags make
file
open the paths named in the flag’s value.
Network paths on Windows
: a command whose arguments include a network (UNC) path, such as
\\server\share\file
, prompts because accessing a network path can send your Windows credentials to the host it names. The same check applies to
PowerShell tool
commands.
Commands the analysis can’t parse
: when Claude Code can’t fully parse a command, it asks for approval instead of treating the command as read-only. Commands longer than 10,000 characters always prompt because they exceed what the analysis parses.
A
cd
into a path inside your working directory or an
additional directory
is also read-only, and a compound command like
cd packages/api && ls
runs without a prompt when each part qualifies on its own. Two combinations prompt even when each part is read-only:
cd
with
git
: prompts when the
cd
changes into a different directory, since running
git
in a new directory can execute that directory’s hooks. A
cd
whose target resolves to the current working directory is a no-op and doesn’t trigger the prompt.
cd
with an output redirect
: prompts when Claude Code can’t determine which directory the redirect target resolves against after the
cd
runs. A command whose only redirect target is
/dev/null
, such as
cd app; grep -r pattern . 2>/dev/null
, doesn’t prompt, because
/dev/null
doesn’t depend on the working directory.
Bash permission patterns that try to constrain command arguments are fragile. For example,
Bash(curl http://github.com/ *)
intends to restrict curl to GitHub URLs, but won’t match variations like:
Options before URL:
curl -X GET http://github.com/...
Different protocol:
curl https://github.com/...
Redirects:
curl -L http://short.example.com/xyz
, which redirects to GitHub
Variables:
URL=http://github.com && curl $URL
Extra spaces:
curl  http://github.com
For more reliable URL filtering, consider:
Restrict Bash network tools
: use deny rules to block
curl
,
wget
, and similar commands, then use the WebFetch tool with
WebFetch(domain:github.com)
permission for allowed domains
Use PreToolUse hooks
: implement a hook that validates URLs in Bash commands and blocks disallowed domains
Add CLAUDE.md guidance
: describe your allowed curl patterns in
CLAUDE.md
. This shapes what Claude tries but doesn’t enforce a boundary, so pair it with one of the options above
Note that using WebFetch alone doesn’t prevent network access. If Bash is allowed, Claude can still use
curl
,
wget
, or other tools to reach any URL.
​
Redirections
Claude Code checks the target of an output redirection, such as
>
,
>>
, or
2>
, as a file write. The check covers your
Edit
allow and deny rules,
protected paths
, and the
working directories
. A rule such as
Bash(git commit *)
allows the command, not the target. A
/dev/null
target isn’t checked. A target that starts with
~
or contains a glob character needs approval.
​
PowerShell
PowerShell permission rules use the same shape as Bash rules. Wildcards with
*
match at any position, the
:*
suffix is equivalent to a trailing
*
, and a bare
PowerShell
or
PowerShell(*)
matches every command. This configuration allows
Get-ChildItem
and
git commit
commands while blocking
Remove-Item
:
{
"permissions"
: {
"allow"
: [
"PowerShell(Get-ChildItem *)"
,
"PowerShell(git commit *)"
],
"deny"
: [
"PowerShell(Remove-Item *)"
]
}
}
Common aliases are canonicalized before matching. A rule written for the cmdlet name also matches its aliases, so
PowerShell(Get-ChildItem *)
matches
gci
,
ls
, and
dir
as well. Matching is case-insensitive.
Claude Code parses the PowerShell AST and checks each command in a compound command independently. Pipeline operators
|
, statement separators
;
, and on PowerShell 7+ the chain operators
&&
and
||
split a compound command into subcommands. A rule must match every subcommand for the compound command to be allowed.
​
Read and Edit
To block Claude’s file tools from reading a file or directory, add a
Read
deny rule for its path, such as
Read(./.env)
or
Read(./secrets/**)
;
Exclude sensitive files
has a paste-ready example.
Edit
rules apply to all built-in tools that edit files. Claude makes a best-effort attempt to apply
Read
rules to all built-in tools that read files like Grep and Glob, to
@file
mentions in your prompts, and to the selection and open-file context that a connected
IDE
shares with Claude.
A
Read
deny rule also blocks the
Edit and Write tools
on the same path, including creating a new file there. NotebookEdit isn’t covered, so add an
Edit
deny rule for paths no tool may change. The check requires Claude Code v2.1.208 or later on edits, and v2.1.228 or later on writes.
Claude Code checks file permissions against
Edit(path)
and
Read(path)
rules only. If you write a path rule for
Write
,
NotebookEdit
,
Glob
, or the legacy
MultiEdit
tool instead, Claude Code accepts the rule but never consults it, and
warns at startup
, except for a
Glob
rule passed in
--allowedTools
. Use
Edit(docs/**)
in place of
Write(docs/**)
,
NotebookEdit(docs/**)
, or
MultiEdit(docs/**)
, and
Read(docs/**)
in place of
Glob(docs/**)
. Claude Code doesn’t warn about a tool-name rule with no path, such as a deny rule for
Write
; it matches that rule at the tool level everywhere. Requires Claude Code v2.1.210 or later.
Read and Edit deny rules apply to Claude’s built-in file tools and to file commands Claude Code recognizes in Bash, such as
cat
,
head
,
tail
, and
sed
. They don’t apply to arbitrary subprocesses that read or write files indirectly, like a Python or Node script that opens files itself. For OS-level enforcement that blocks all processes from accessing a path,
enable the sandbox
.
Read and Edit rules both use
gitignore
pattern syntax with four distinct pattern types; for single-segment directory patterns, the matching depth also depends on the rule type, described later in this section:
Pattern
Meaning
Example
Matches
//path
Absolute path from filesystem root
Read(//Users/alice/secrets/**)
/Users/alice/secrets/**
~/path
Path from home directory
Read(~/Documents/*.pdf)
/Users/alice/Documents/*.pdf
/path
Path relative to the settings source
Edit(/src/**/*.ts)
<primary working directory>/src/**/*.ts
in project settings
path
or
./path
Path relative to current directory
Read(*.env)
<cwd>/*.env
A pattern like
/Users/alice/file
isn’t an absolute path. The single leading slash anchors at the settings source, not the filesystem root. Use
//Users/alice/file
for absolute paths.
A
/path
pattern anchors at a directory associated with the settings source that defines it, so the same rule matches different locations depending on where you put it:
Rule defined in
/path
resolves to
Project settings at
.claude/settings.json
<primary working directory>/path
Local settings at
.claude/settings.local.json
<primary working directory>/path
User settings at
~/.claude/settings.json
~/.claude/path
A file passed with
--settings <file>
<directory of file>/path
CLI flags or session rules
<primary working directory>/path
A rule you add through
/permissions
follows the row for the settings file you save it to.
Local settings rules anchor at the session’s
primary working directory
, not at the repository root where Claude Code
stores the file
in v2.1.211 and later. In a session started at the repository root, the two directories are the same; in a
worktree
session, a shared rule such as
Edit(/src/**)
matches that worktree’s own
src/
directory.
A deny rule such as
Read(/secrets/**)
in user settings blocks
~/.claude/secrets/**
, not a
secrets
directory in your project. To write a rule in user settings that applies inside every project, use a
//
absolute path or a
~/
home-relative path instead.
On Windows, paths are normalized to POSIX form before matching.
C:\Users\alice
becomes
/c/Users/alice
, so use
//c/**/.env
to match
.env
files anywhere on that drive. To match across all drives, use
//**/.env
.
Examples:
Edit(/docs/**)
: edits in
<primary working directory>/docs/
, not
/docs/
or
<primary working directory>/.claude/docs/
Read(~/.zshrc)
: reads your home directory’s
.zshrc
Edit(//tmp/scratch.txt)
: edits the absolute path
/tmp/scratch.txt
Read(src/**)
: as an allow rule, reads from
<current-directory>/src/
only; as a deny or ask rule, matches a
src
directory at any depth under the current directory
A rule only matches files under its anchor; within that bound, matching depth depends on the pattern shape and, for single-segment directory patterns, the rule type, described below. Bare filenames follow gitignore semantics and match at any depth, so
Read(.env)
and
Read(**/.env)
are equivalent:
Deny rule
Blocks
Does not block
Read(.env)
or
Read(**/.env)
any
.env
at or under the current directory
.env
in a parent directory or another project
Read(//**/.env)
any
.env
anywhere on the filesystem
nothing; the rule is anchored at the filesystem root
A relative pattern with a single directory segment, such as
src/**
, matches at different depths depending on the rule type:
Allow rules
:
Edit(src/**)
matches only
<cwd>/src
and the files under it. To allow a directory name at any depth, write
Edit(**/src/**)
.
Deny and ask rules
:
Read(secrets/**)
matches a directory named
secrets
at any depth under the current directory, so the rule also applies to nested copies.
Every other pattern shape matches at the same depth in every rule type:
Edit(/src/**)
and
Edit(src/components/**)
match only at their anchored location, while
Edit(**/src/**)
matches at any depth.
The following example shows each pattern shape against a project with a top-level
src/
directory and a nested copy under
vendor/
:
<current-directory>/
├── src/
│   └── app.ts
└── vendor/
└── pkg/
└── src/
└── lib.js
Rule
Matches
src/app.ts
Matches
vendor/pkg/src/lib.js
Edit(src/**)
as an allow rule
Yes
No
Edit(src/**)
as a deny or ask rule
Yes
Yes
Edit(/src/**)
in any rule type
Yes
No
Edit(**/src/**)
in any rule type
Yes
Yes
In gitignore patterns,
*
matches within a single path segment and can appear at any position in the pattern, while
**
matches across directories.
When you approve a file path with “Yes, and don’t ask again”, Claude Code escapes gitignore pattern characters in that path, such as
[
,
]
, and
*
, so the generated rule matches only the literal path you approved. Rules you write yourself aren’t escaped. Before v2.1.202, Claude Code saved the path unescaped, so a generated rule for a directory named
[2024-06] Reports
could fail to match its own path or match unintended sibling directories.
When Claude accesses a symlink, permission rules check two paths: the symlink itself and the file it resolves to. Allow and deny rules treat that pair differently: allow rules fall back to prompting you, while deny rules block outright.
Allow rules
: apply only when both the symlink path and its target match. A symlink inside an allowed directory that points outside it still prompts you.
Deny rules
: apply when either the symlink path or its target matches. A symlink that points to a denied file is itself denied.
For example, with
Read(./project/**)
allowed and
Read(~/.ssh/**)
denied, a symlink at
./project/key
pointing to
~/.ssh/id_rsa
is blocked: the target fails the allow rule and matches the deny rule.
When a tool opens an approved file, Claude Code
confirms the path still resolves to the location the permission check approved
.
Grep and Glob search the directory the
path
argument resolves to. Claude Code applies
Read
deny rules to that directory.
​
WebFetch
WebFetch rules use a
domain:
prefix and match against the hostname of the requested URL. Matching is case-insensitive, supports
*
wildcards, and strips a trailing
.
from both the rule and the hostname so
example.com.
and
example.com
are treated the same.
WebFetch(domain:example.com)
matches requests to
example.com
WebFetch(domain:*.example.com)
matches any subdomain at any depth, such as
api.example.com
or
a.b.example.com
, but not
example.com
itself
WebFetch(domain:*)
matches every domain. It isn’t the same as a bare
WebFetch
rule; see
Allow or deny every fetch
In any position other than a leading
*.
or a bare
*
, the wildcard matches only the text between two dots.
WebFetch(domain:example.*)
matches
example.org
, where
*
becomes
org
, but not
example.evil.com
, where
*
would have to become
evil.com
and cross a dot. This keeps a trailing wildcard from matching domains an attacker could register.
Wildcards in
WebFetch
rules require Claude Code v2.1.172 or later to match fetches.
​
Allow or deny every fetch
A bare
WebFetch
rule is the tool name with no
domain:
part, such as
"deny": ["WebFetch"]
. Both it and
WebFetch(domain:*)
cover every URL, but Claude Code applies them differently, and only the
domain:
form also adds its domain to the sandbox’s
allowed or denied domain list
. That section lists the wildcard forms the sandbox honors and the version that added bare
*
.
Each row shows what a rule does in the
allow
list and in the
deny
list:
Rule
In
allow
In
deny
WebFetch
Claude fetches without prompting you. Doesn’t change which hosts sandboxed commands can reach.
Claude Code removes the
WebFetch
tool, so Claude can’t fetch at all. Doesn’t change which hosts sandboxed commands can reach.
WebFetch(domain:*)
Claude fetches without prompting you, and sandboxed commands can reach any host.
Claude Code keeps the tool and refuses each fetch, and sandboxed commands can’t reach any host.
To let Claude fetch freely while keeping the sandbox allowlist as it is, use the bare form. This
settings.json
does that:
{
"permissions"
: {
"allow"
: [
"WebFetch"
]
}
}
When you ask Claude to fetch a page, it fetches without a prompt. When you ask it to run a
sandboxed
curl
against a host outside the sandbox allowlist, Claude Code still prompts you for that host, or in
auto mode
sends the request to the classifier, because the bare rule didn’t add the host to the allowlist.
​
MCP
MCP rules use the server name as configured in Claude Code, optionally followed by the name of a tool from that server.
mcp__puppeteer
matches any tool provided by the
puppeteer
server
mcp__puppeteer__*
uses wildcard syntax and also matches all tools from the
puppeteer
server
mcp__puppeteer__puppeteer_navigate
matches the
puppeteer_navigate
tool provided by the
puppeteer
server
If your organization has set a
claude.ai connector
tool to
ask
and that setting reaches Claude Code in your session, allow rules for that tool don’t take effect: Claude Code prompts on every call, even in
auto
and
bypassPermissions
modes. In
dontAsk
mode, which never prompts, Claude Code denies the call instead. Tools from connectors Claude Code fetches itself appear as
mcp__claude_ai_<server>__<tool>
.
In a
Cowork
session in the Claude Desktop app, Claude runs shell commands through Cowork’s
mcp__workspace__bash
tool rather than the built-in
Bash
tool, and Cowork likewise provides
mcp__workspace__web_fetch
for web fetches. Claude Code also applies deny rules that name the whole
Bash
or
WebFetch
tool to these Cowork tools, so a managed
Bash
deny rule stops Claude from running shell commands in Cowork. When Claude Code blocks such a call, the message names the Cowork tool:
Permission to use mcp__workspace__bash has been denied.
Allow rules don’t carry over: Claude Code never applies a
Bash
allow rule to
mcp__workspace__bash
.
​
Agent (subagents)
Use
Agent(AgentName)
rules to control which
subagents
Claude can use:
Agent(Explore)
matches the Explore subagent
Agent(Plan)
matches the Plan subagent
Agent(my-custom-agent)
matches a custom subagent named
my-custom-agent
Add these rules to the
deny
array in your settings or use the
--disallowedTools
CLI flag to disable specific agents. To disable the Explore agent:
{
"permissions"
: {
"deny"
: [
"Agent(Explore)"
]
}
}
​
Cd
Cd
rules control which directories the
/cd
command
can move the session to.
Cd
is not a model-invocable tool: Claude can’t call it, and the rules apply only when you run
/cd
yourself.
A bare
Cd
deny rule disables
/cd
entirely. A
Cd(<path-pattern>)
deny rule blocks matching targets. Deny rules check every spelling of the target, including each symlink hop it resolves through, so a rule written for one path also blocks targets that resolve to it.
Adding any
Cd
allow rule switches
/cd
to allowlist mode: the resolved target directory must match one of your allow rules, or
/cd
refuses. With no
Cd
rules configured,
/cd
keeps its default behavior and prompts you to trust an unfamiliar directory.
Path patterns share the
//
,
~/
, and
/
anchors from
Read and Edit rules
, but matching is anchored to the whole directory path rather than gitignore-style.
*
matches exactly one path segment and
**
matches across segments. A trailing
/**
also matches its named root.
Rule
Matches
Does not match
Cd(~/code/*)
~/code/app
~/code/app/src
,
~/code
Cd(~/code/**)
~/code
and any directory under it
directories outside
~/code
Cd(**/node_modules)
any
node_modules
directory at any depth
node_modules/pkg
​
Extend permissions with hooks
Claude Code hooks
let you register custom shell commands that evaluate permissions at runtime. When Claude Code makes a tool call, PreToolUse hooks run before the permission prompt, for every tool except
EndConversation
. The hook output can deny the tool call, force a prompt, or skip the prompt to let the call proceed.
Hook decisions don’t bypass permission rules. Claude Code evaluates deny and ask rules regardless of what a PreToolUse hook returns: a matching deny rule blocks the call, and a matching ask rule still prompts even when the hook returned
"allow"
or
"ask"
. This preserves the deny-first precedence described in
Manage permissions
, including deny rules set in managed settings.
MCP tools marked
requiresUserInteraction
also still prompt when a hook returns
"allow"
, as do connector tools
your organization set to
ask
in sessions where that setting reaches Claude Code.
A blocking hook also takes precedence over allow rules. A hook that exits with code 2 stops the tool call before permission rules are evaluated, so the block applies even when an allow rule would otherwise let the call proceed. To run all Bash commands without prompts except for a few you want blocked, add
"Bash"
to your allow list and register a PreToolUse hook that rejects those specific commands. See
Block edits to protected files
for a hook script you can adapt.
​
Working directories
By default, Claude has access to files in the directory where you launched it. That directory is the session’s primary working directory until you
move the session with
/cd
. You can extend this access:
During startup
: use
--add-dir <path>
CLI argument
During session
: use
/add-dir
command
Persistent configuration
: add to
additionalDirectories
in
settings files
Files in additional directories follow the same permission rules as the original working directory: they become readable without prompts, and file editing permissions follow the current permission mode.
In background sessions on macOS, the session host requests access to protected folders such as
~/Desktop
,
~/Documents
, and
~/Downloads
separately from your terminal when Claude needs to read or write files there; if reads there fail with
Operation not permitted
, see
how to grant folder access to background sessions
.
​
Move the session to another directory
To move the session to a different primary working directory, rather than
adding a directory
alongside the current one, run
/cd <path>
. Claude Code keeps the conversation, loads the new directory’s
CLAUDE.md
, and prompts you to
trust the workspace
if you haven’t worked in it before. Afterward, Claude Code
finds the moved session
when you run
--resume
from the new directory. The
/cd
command requires Claude Code v2.1.169 or later.
As soon as you move, Claude Code applies the new directory’s project configuration:
Its project settings, including their permission rules and
hooks
Its
.mcp.json
servers
, subject to the same
server approval
as at startup, and the
local-scope
MCP servers you registered in it
The
plugins
its settings enable, its
skills
, and its
subagents
Its
env
values, applied on top of the environment variables from the previous directory’s settings, which stay in effect
Claude Code also disconnects the previous directory’s project and
local-scope
MCP servers, and the servers of
plugins
that are no longer enabled after the move. It takes
additional directories
from the new directory’s settings instead of the previous one’s, and keeps the directories you added with
--add-dir
or
/add-dir
. Hooks the move activates still receive
${CLAUDE_PROJECT_DIR}
set to the project root where the session started.
When the new directory isn’t trusted yet, Claude Code lists in the trust prompt the allow rules, additional directories, hooks, and helper commands the directory’s settings would activate, so you can review them before you accept. If you decline, the session stays where it is. Before v2.1.246,
/cd
didn’t apply the new directory’s settings, hooks, MCP servers, or skills until you resumed the session, and its trust prompt didn’t list what the directory’s settings would activate.
Restrict or disable
/cd
targets with
Cd
permission rules
.
​
Additional directories grant file access, not configuration
Adding a directory extends where Claude can read and edit files. It doesn’t make that directory a full configuration root: most
.claude/
configuration is not discovered from additional directories, though a few types are loaded as exceptions.
These exceptions apply only to directories added with the
--add-dir
flag or the
/add-dir
command, including directories the Agent SDK adds through the flag. Directories listed in
permissions.additionalDirectories
in a settings file grant file access only and don’t load any of the configuration below.
The Agent SDK’s
additionalDirectories
option in TypeScript and
add_dirs
option in Python receive the exceptions too, even though the TypeScript option shares its name with the settings key. The SDK passes each entry to Claude Code as
--add-dir
, so those directories behave like flag-added directories. Skills, commands, and subagents from any flag-added directory load through the
project
setting source
, so they don’t load when you exclude that source with
--setting-sources
on the CLI or
settingSources
in the SDK, and
bare mode
skips the commands and subagents among them.
The following configuration types are loaded from
--add-dir
directories:
Configuration
Loaded from
--add-dir
Skills
in
.claude/skills/
Yes, with live reload
Command files
in
.claude/commands/
Yes, without live reload. When the added directory and your project both define a command with the same name, Claude Code runs your project’s command
Subagents
in
.claude/agents/
Yes, without live reload
Settings
in
.claude/settings.json
and
.claude/settings.local.json
enabledPlugins
and
extraKnownMarketplaces
keys only
CLAUDE.md
files,
.claude/rules/
, and
CLAUDE.local.md
Only when
CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1
is set.
CLAUDE.local.md
additionally requires the
local
setting source, which is enabled by default
Claude Code discovers output styles from the current working directory and its parents, your user directory at
~/.claude/
, and managed settings. Hooks and other
.claude/settings.json
keys load from the current working directory’s
.claude/
folder with no parent-directory fallback, alongside your user
~/.claude/settings.json
and managed settings.
.claude/settings.local.json
loads from the git repository root instead, even when you start Claude Code in a subdirectory, except in the cases where Claude Code
doesn’t use the repository root
, such as on Windows; before v2.1.211, it too loaded only from the current working directory.
Agent SDK
sessions load it from the working directory in all versions.
To share that configuration across projects, use one of these approaches:
User-level configuration
: place files in
~/.claude/agents/
,
~/.claude/output-styles/
, or
~/.claude/settings.json
to make them available in every project
Plugins
: package and distribute configuration as a
plugin
that teams can install
Launch from the config directory
: run Claude Code from the directory containing the
.claude/
configuration you want
​
How permissions interact with sandboxing
Permissions and
sandboxing
are complementary security layers:
Permissions
control which tools Claude Code can use and which files or domains it can access. They apply to Bash, Read, Edit, WebFetch, MCP, and every other tool, except that a deny or ask rule can’t block
EndConversation
while any other tool remains.
Sandboxing
provides OS-level enforcement that restricts the Bash tool’s filesystem and network access. It applies only to Bash commands and their child processes.
Use both for defense-in-depth:
Permission deny rules block Claude from even attempting to access restricted resources
Sandbox restrictions prevent Bash commands from reaching resources outside defined boundaries, even if a prompt injection bypasses Claude’s decision-making
Filesystem restrictions in the sandbox combine the
sandbox.filesystem
settings with Read and Edit deny rules; both are merged into the final sandbox boundary
Network restrictions combine
WebFetch(domain:...)
permission rules with the sandbox’s
allowedDomains
and
deniedDomains
lists
When you enable sandboxing and leave
autoAllowBashIfSandboxed
at its default of
true
, sandboxed Bash commands run without prompting even if your permissions include a bare
Bash
ask rule, or the
equivalent
Bash(*)
form
: the sandbox boundary substitutes for that whole-tool prompt.
In
plan mode
, Claude Code skips this substitution. Without an ask rule, the built-in read-only commands still run without prompting, and any other shell command goes through the regular permission flow while you are still planning; see
plan mode
for how Claude Code gates commands there. With a bare
Bash
ask rule, every Bash command prompts, including sandboxed read-only commands, the same as outside sandboxing. Before v2.1.212, the substitution applied in plan mode as well.
These checks still apply:
Content-scoped ask rules like
Bash(git push *)
still force a prompt
Explicit deny rules still apply
rm
or
rmdir
commands that target a
critical path
still go through the regular permission flow
Commands that won’t run sandboxed, such as excluded commands, respect the bare
Bash
ask rule as usual. See
sandbox modes
to change this behavior.
​
Managed settings
For organizations that need centralized control, administrators deploy managed settings that user and project settings can’t override, apart from a few
security-sensitive keys
.
Deploy managed settings
covers the delivery mechanisms, precedence within the managed tier, and the
keys only managed settings can set
, such as
allowManagedPermissionRulesOnly
, which limits permission rules to the managed source.
disableBypassPermissionsMode
is typically placed in managed settings to enforce organizational policy, but it works from any scope. A user can set it in their own settings to lock themselves out of bypass mode.
​
Settings precedence
Permission rules follow the same
settings precedence
as all other Claude Code settings, with managed settings highest: no other level, including command line arguments, can override a managed permission rule.
If a tool is denied at any level, no other level can allow it. For example, a managed settings deny can’t be overridden by
--allowedTools
, and
--disallowedTools
can add restrictions beyond what managed settings define.
The same holds across settings scopes: if user settings allow a permission and project settings deny it, the deny rule blocks it. The reverse is also true: a user-level deny blocks a project-level allow, because deny rules from any scope are evaluated before allow rules.
Embedding hosts can supply additional managed policy via the SDK
managedSettings
option, including permission allow rules unless the admin sets the
allowManaged*Only
locks;
Deliver policy to Claude Desktop sessions
covers when embedder policy applies at all.
​
Project allow rules and workspace trust
permissions.allow
rules and
permissions.additionalDirectories
entries in a project’s
.claude/settings.json
grant capability, so Claude Code applies them only after you accept the
workspace trust dialog
for that folder. The dialog lists the rules and directories the folder would grant so you can review them first.
deny
and
ask
rules aren’t affected, since they only restrict.
Claude Code keys and stores the trust you accept according to where you start it:
In a repository, Claude Code keys the trust on the git repository root, so the trust covers the whole repository apart from any git repository nested inside it, such as a submodule. In a
worktree
, it uses the main checkout

## Source (agent-teams): https://docs.claude.com/en/docs/claude-code/agent-teams

Orchestrate teams of Claude Code sessions - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Agent teams are experimental and disabled by default. Enable them by setting
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
in your
settings.json
or environment. Without that variable, no team is set up at session start, no team directories are written, and Claude does not spawn or propose teammates. Agent teams have
known limitations
around session resumption, task coordination, and shutdown behavior.
Agent teams let you coordinate multiple Claude Code instances working together. One session acts as the team lead, coordinating work, assigning tasks, and synthesizing results. Teammates work independently, each in its own context window, and communicate directly with each other. You can also talk to any teammate directly without going through the lead.
Before you set up a team, check whether a lighter option does the job.
Subagents
work within a single session, and with
cross-session messaging
Claude can pass findings between the sessions you run yourself.
This page describes agent teams as of v2.1.178. With
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
set, spawning a teammate no longer needs a setup step, and cleanup happens automatically when the session exits. Before v2.1.178, you asked Claude to create and name a team first, and Claude used the
TeamCreate
and
TeamDelete
tools to set it up and remove it. Both tools no longer exist. The
team_name
input on the Agent tool is accepted but ignored, and the
team_name
field in
TaskCreated
,
TaskCompleted
, and
TeammateIdle
hook payloads
carries the session-derived name and is deprecated.
​
When to use agent teams
Agent teams are most effective for tasks where parallel exploration adds real value. See
use case examples
for full scenarios. The strongest use cases are:
Research and review
: multiple teammates can investigate different aspects of a problem simultaneously, then share and challenge each other’s findings
New modules or features
: teammates can each own a separate piece without stepping on each other
Debugging with competing hypotheses
: teammates test different theories in parallel and converge on the answer faster
Cross-layer coordination
: changes that span frontend, backend, and tests, each owned by a different teammate
Agent teams add coordination overhead and use significantly more tokens than a single session. They work best when teammates can operate independently. For sequential tasks, same-file edits, or work with many dependencies, a single session or
subagents
are more effective.
​
Compare with subagents
Both agent teams and
subagents
let you parallelize work, but they operate differently. For separate sessions that pass messages to each other without a team, see
cross-session messaging
.
Subagents report results back to the main agent. In agent teams, teammates share a task list, claim work, and communicate directly with each other.
Subagents
Agent teams
Context
Own context window; results return to the caller
Own context window; fully independent
Communication
Return a result to the caller. Subagents that Claude named when it spawned them can also
message each other
Teammates message each other directly
Coordination
Main agent manages all work
Self-coordination through messages, plus a shared task list for
agents that have the Task tools
Best for
Focused tasks where only the result matters
Complex work requiring discussion and collaboration
Token cost
Lower: results summarized back to main context
Higher: each teammate is a separate Claude instance
Use subagents when you need quick, focused workers that report back. Use agent teams when teammates need to share findings, challenge each other, and coordinate on their own.
​
Enable agent teams
Agent teams are disabled by default. Enable them by setting the
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
environment variable to
1
, either in your shell environment or through
settings.json
:
settings.json
{
"env"
: {
"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
:
"1"
}
}
Enabling agent teams also changes ordinary delegation. Claude may
name a subagent
on its own, and while agent teams are enabled, a subagent that Claude names launches as a teammate, so teams can form even when you didn’t ask for one. For more, see
How Claude starts agent teams
; to turn the behavior off, see
Claude spawns teammates instead of subagents
.
Spawning teammates also requires an interactive session. In
non-interactive mode
with the
-p
flag, including Agent SDK sessions, Claude doesn’t spawn teammates, and a subagent that Claude names runs as an ordinary
subagent
even with agent teams enabled.
​
Start your first agent team
After enabling agent teams, describe the task and the teammates you want in natural language. Claude spawns them and coordinates work based on your prompt.
This example works well because the three roles are independent and can explore the problem without waiting on each other:
I'm designing a CLI tool that helps developers track TODO comments across
their codebase. Spawn three teammates to explore this from different angles:
one on UX, one on technical architecture, one playing devil's advocate.
From there, Claude populates a
shared task list
in a
session that has the Task tools
, spawns teammates for each perspective, has them explore the problem, and synthesizes findings when finished.
Claude may sometimes use
subagents
instead of creating a team. Subagents appear in the same agent panel as teammates, so the panel alone doesn’t confirm a team formed. If Claude spawned subagents instead, ask again and explicitly request an agent team.
The lead’s terminal lists teammates in the agent panel below the prompt input. From the panel:
Up and down arrows
: select a teammate
Enter
: open the selected teammate’s transcript and message it directly
Escape
: clear the selection. While you’re viewing a teammate’s transcript, Escape interrupts that teammate’s current turn
As of v2.1.199, an idle teammate’s row stays in the panel while any teammate or subagent is still working, so you can select it to review its transcript or send it more work. Once every agent in the panel is idle, idle rows hide after 30 seconds and reappear on the teammate’s next turn; the teammate stays running and addressable while hidden. In v2.1.181 through v2.1.198, an idle row hid 30 seconds after its own turn ended, even while other teammates were still working; idle rows are not hidden on versions before v2.1.181.
When more than three teammates are idle at once, the rows beyond the first three collapse into a single row that counts the collapsed teammates, such as
2 idle agents
when five are idle. Select it and press Enter to expand the collapsed rows, or press Esc to collapse them again. Working teammates, failed teammates, and the teammate you’re viewing always keep their own rows.
If you want each teammate in its own split pane, see
Choose a display mode
.
​
Control your agent team
Tell the lead what you want in natural language. It handles team coordination, task assignment, and delegation based on your instructions.
​
Choose a display mode
Agent teams support two display modes:
In-process
: all teammates run inside your main terminal. Use the up and down arrow keys in the agent panel to select a teammate, then press Enter to view it and type to message it directly. Works in any terminal, no extra setup required.
Split panes
: each teammate gets its own pane. You can see everyone’s output at once and click into a pane to interact directly. Requires tmux, or iTerm2.
tmux
has known limitations on certain operating systems and traditionally works best on macOS. Using
tmux -CC
in iTerm2 is the suggested entrypoint into
tmux
.
The default is
"in-process"
. Before v2.1.179 the default was
"auto"
, so upgraded sessions that previously opened split panes now stay in one terminal unless you set the mode explicitly. Set
"auto"
to enable split panes when you’re already running inside a tmux session, or when your terminal is iTerm2 with the
it2
CLI installed, falling back to in-process otherwise. The
"tmux"
setting enables split-pane mode and auto-detects whether to use tmux or iTerm2 based on your terminal.
As of v2.1.186, set
"iterm2"
to use iTerm2 native split panes explicitly. This mode requires the
it2
CLI
and shows an error with the install command if
it2
is missing. The setup prompt that offers to install
it2
or switch to tmux appears under
"auto"
or
"tmux"
when your terminal is iTerm2 and tmux is available as a fallback.
To override the default, set
teammateMode
in
~/.claude/settings.json
:
{
"teammateMode"
:
"auto"
}
To set the mode for a single session, pass it as a flag:
claude
--teammate-mode
auto
The
--teammate-mode
flag is experimental and doesn’t appear in
claude --help
.
Split-pane mode requires either
tmux
or iTerm2 with the
it2
CLI
. To install manually:
tmux
: install through your system’s package manager. See the
tmux wiki
for platform-specific instructions.
iTerm2
: install the
it2
CLI
, then enable the Python API in
iTerm2 → Settings → General → Magic → Enable Python API
.
​
Specify teammates and models
Claude decides the number of teammates to spawn based on your task, or you can specify exactly what you want:
Spawn 4 teammates to refactor these modules in parallel. Use Sonnet for
each teammate.
Claude Code picks each teammate’s model from the first of these that applies:
CLAUDE_CODE_SUBAGENT_MODEL
, when it’s set to anything other than
inherit
.
The model your spawn prompt names for that teammate.
For an in-process teammate spawned from a
subagent definition
, the definition’s
model
.
The lead’s current model.
teammateDefaultModel
was removed in v2.1.234; Claude Code ignores a leftover value. Name the model in your prompt or set
CLAUDE_CODE_SUBAGENT_MODEL
instead.
Claude Code checks the model your prompt requests for a teammate, or the one
CLAUDE_CODE_SUBAGENT_MODEL
supplies, against your organization’s
availableModels
allowlist. When the allowlist blocks a value, Claude Code substitutes another model:
Family alias such as
opus
: On the Anthropic API and Claude Platform on AWS, Claude Code runs the teammate on the newest version of that family the allowlist permits. On providers with provider-specific model IDs, where the
substitution doesn’t operate
, a blocked alias falls back like any other blocked value per the next bullet
Any other blocked value, including a family alias on providers where the substitution doesn’t operate or whose family has no permitted version
: Claude Code runs the teammate on the lead’s model
Teammates inherit the lead’s
effort level
. In split-pane mode this applies from v2.1.186; earlier versions did not pass the lead’s session effort to split-pane teammates.
​
Have teammates plan before implementing
For complex or risky tasks, you can have teammates plan before implementing. A teammate that Claude spawns while the lead is in
plan mode
works in read-only plan mode until its plan is ready. Switch the lead into plan mode first, then ask for the teammate:
Spawn an architect teammate to refactor the authentication module.
When a teammate finishes planning, it sends a plan approval request to the lead. Claude Code approves the plan in the lead’s session as soon as the request arrives, without the lead reviewing it. The teammate’s edits and commands still go through the permission prompts described in
Permissions
. Once approved, the teammate exits plan mode and begins implementation.
​
Talk to teammates directly
Each teammate is a full, independent Claude Code session. You can message any teammate directly to give additional instructions, ask follow-up questions, or redirect their approach.
In-process mode
: use the up and down arrow keys in the agent panel to select a teammate, then press Enter to view its session and type to send it a message. Press
x
on a selected teammate to stop it. Press Ctrl+T to toggle the task list.
Split-pane mode
: click into a teammate’s pane to interact with their session directly. Each teammate has a full view of their own terminal.
While you’re viewing an in-process teammate, plain text and
skills
go to that teammate, but built-in commands still run in the lead’s session.
A teammate’s model and fast mode are fixed when it spawns, so
/model
and
/fast
only change the lead’s settings. As of v2.1.199, typing either command while viewing a teammate shows a notice that the change applies to the lead; earlier versions applied it to the lead with no indication.
/effort
still applies to the viewed teammate’s later turns, because teammates follow the lead’s
effort level
.
​
Assign and claim tasks
The shared task list coordinates work across the team. The lead creates tasks and teammates work through them. Tasks have three states: pending, in progress, and completed. Tasks can also depend on other tasks: a pending task with unresolved dependencies cannot be claimed until those dependencies are completed.
Agents
without the Task tools
coordinate through messages instead of the shared task list.
The lead can assign tasks explicitly, or teammates can self-claim:
Lead assigns
: tell the lead which task to give to which teammate
Self-claim
: after finishing a task, a teammate picks up the next unassigned, unblocked task on its own
Task claiming uses file locking to prevent race conditions when multiple teammates try to claim the same task simultaneously.
​
Shut down teammates
To gracefully end a teammate’s session, refer to it by name. For example, with a teammate named researcher:
Ask the researcher teammate to shut down
The lead sends a shutdown request. The teammate can approve, exiting gracefully, or reject with an explanation.
The team’s shared directories are cleaned up automatically when the session ends, so there’s no separate cleanup step. See
Architecture
for which directories are removed and which persist for resumed sessions.
​
Enforce quality gates with hooks
Use
hooks
to enforce rules when teammates finish work or tasks are created or completed:
TeammateIdle
: runs when a teammate is about to go idle. Exit with code 2 to send feedback and keep the teammate working.
TaskCreated
: runs when a task is being created. Exit with code 2 to prevent creation and send feedback.
TaskCompleted
: runs when a task is being marked complete. Exit with code 2 to prevent completion and send feedback.
​
How agent teams work
This section covers the architecture and mechanics behind agent teams. If you want to start using them, see
Control your agent team
above.
​
How Claude starts agent teams
To start a team, ask Claude for teammates. Claude launches a teammate when it calls the
Agent tool
with a
name
while agent teams are enabled, and Claude Code doesn’t ask you to confirm. Claude also names ordinary subagents on its own so it can message them later, and while agent teams are enabled, a named subagent launches as a teammate, so teams can form even when you didn’t ask for one.
If you want subagents instead,
turn agent teams off
.
​
Architecture
An agent team consists of:
Component
Role
Team lead
The main Claude Code session that spawns teammates and coordinates work
Teammates
Separate Claude Code instances that each work on assigned tasks
Task list
Shared list of work items that teammates claim and complete
Mailbox
Messaging system for communication between agents
Each agent’s mailbox is a JSON file at
~/.claude/teams/{team-name}/inboxes/{agent-name}.json
. Claude Code validates every entry when it reads a mailbox file. Entries that don’t match the message format are reported as errors and removed from the file; the valid messages are still delivered. Before v2.1.207, a single malformed mailbox entry caused a repeated error every second and blocked delivery for that mailbox until you deleted the file manually.
Claude Code reports a message as sent only when the write to the recipient’s mailbox file succeeds, whether the message is plain text or a structured protocol message such as a plan approval or shutdown request. When the write fails, for example because the disk is full or the mailbox directory isn’t writable, the sending agent receives an error and nothing is sent. See
Failed to write to a teammate’s inbox
for the error messages and recovery steps.
Claude Code manages task dependencies automatically: when a teammate completes a task that other tasks depend on, it unblocks the dependent tasks without any action from you.
Teams and tasks are stored locally under a session-derived name. The name is
session-
followed by the first eight characters of the session ID:
Team config
:
~/.claude/teams/{team-name}/config.json
Task list
:
~/.claude/tasks/{team-name}/
Claude Code generates both of these automatically at session startup and updates them as teammates join, go idle, or leave. The team config directory is removed when the session ends. The task list directory persists locally and is never uploaded, so resumed sessions keep their tasks. Retention is governed by the same
cleanupPeriodDays
you already control for session transcripts, following the
retention sweep rules
.
The team config holds runtime state such as session IDs and tmux pane IDs, so don’t edit it by hand or pre-author it: your changes are overwritten on the next state update.
To define reusable teammate roles, use
subagent definitions
instead.
The team config contains a
members
array with each member’s name and agent ID. The lead’s entry always carries the agent type
team-lead
. A teammate’s entry carries whatever agent type the lead named when spawning it, whether a
built-in type
or a
subagent definition
, and omits the field when the lead named none. Teammates can read this file to discover other team members.
There is no project-level equivalent of the team config. A file like
.claude/teams/teams.json
in your project directory is not recognized as configuration; Claude treats it as an ordinary file.
​
Use subagent definitions for teammates
When spawning a teammate, you can reference a
subagent
type from any
subagent scope
: project, user, plugin, or CLI-defined. This lets you define a role once, such as a security-reviewer or test-runner, and reuse it both as a delegated subagent and as an agent team teammate.
To use a subagent definition, name it when you ask Claude to spawn the teammate:
Spawn a teammate using the security-reviewer agent type to audit the auth module.
Claude Code reads the subagent definition you named and applies these parts of it to the teammate. Where a part depends on the teammate’s
display mode
, the entry says so:
tools
: Claude Code limits the teammate to the tools in the definition’s
tools
list. For an in-process teammate, Claude Code adds
SendMessage
to that list, and in a
session that has the Task tools
it adds
TaskCreate
,
TaskGet
,
TaskList
, and
TaskUpdate
too.
model
: for an in-process teammate, Claude Code uses the definition’s
model
when neither
CLAUDE_CODE_SUBAGENT_MODEL
nor your spawn prompt names a model. A split-pane teammate doesn’t use the definition’s
model
. See
how Claude Code picks a teammate’s model
.
Body
: for an in-process teammate, Claude Code appends the definition’s body to its default system prompt as additional instructions. For a split-pane teammate, Claude Code uses the body in place of its default system prompt.
skills
: Claude Code doesn’t apply the definition’s
skills
to a teammate in either display mode. The teammate loads skills from your project and user settings.
mcpServers
: for a split-pane teammate, Claude Code applies the definition’s
mcpServers
under the
rules for that field
, which cover a session started with
--agent
as well. An in-process teammate ignores the field and loads MCP servers from your project and user settings.
​
Permissions
Teammates start with the lead’s permission settings. If the lead runs with
--dangerously-skip-permissions
, all teammates do too. After spawning, you can change individual teammate modes, but you can’t set per-teammate modes at spawn time.
Teammate permission prompts appear in the lead session, so approve them there yourself.
Plan approval
is the designed exception: the lead session grants teammate plan approvals without a separate prompt to you.
​
Messages between agents
When one agent sends another a message over
SendMessage
, Claude Code tells the receiving agent the message came from another Claude session, not from you. A teammate can’t approve a permission prompt or supply consent on your behalf, and a teammate that was denied an action can’t relay it to another teammate to bypass the check. The same rules apply to a message that arrives from
one of your other Claude Code sessions
, outside the team entirely.
In
auto mode
, the classifier applies two checks to messages between agents:
It treats an approval claim relayed from another agent as untrusted input rather than confirmation from you.
It reviews each message before Claude Code delivers it, whether a plain message or a structured protocol message such as a shutdown request or plan approval response. A message it blocks never reaches the recipient.
​
Context and communication
Each teammate has its own context window. When spawned, a teammate loads the same project context as a regular session: CLAUDE.md, MCP servers, and skills. It also receives the spawn prompt from the lead. The lead’s conversation history does not carry over.
How teammates share information:
Automatic message delivery
: when teammates send messages, they’re delivered automatically to recipients. The lead doesn’t need to poll for updates.
Idle notifications
: when a teammate finishes and stops, it automatically notifies the lead and includes its final answer in the notification. A teammate whose turn ends on an API error notifies the lead that it failed and includes the error text.
Shared task list
:
agents that have the Task tools
can see task status and claim available work.
Teammate messaging
: send a message to one specific teammate by name. To reach everyone, send one message per recipient.
The lead assigns every teammate a name when it spawns them, and any teammate can message any other by that name. To get predictable names you can reference in later prompts, tell the lead what to call each teammate in your spawn instruction.
​
Token usage
Agent teams use significantly more tokens than a single session. Each teammate has its own context window, and token usage scales with the number of active teammates. For research, review, and new feature work, the extra tokens are usually worthwhile. For routine tasks, a single session is more cost-effective. See
agent team token costs
for usage guidance.
An in-process teammate’s requests fall outside the main conversation’s
cache TTL bucket
, so its cache holds for five minutes by default, including on a Claude subscription. To keep it for an hour, set
subagentPromptCacheTtl
to
1h
. The API bills 1-hour cache writes at a higher rate.
​
Use case examples
These examples show how agent teams handle tasks where parallel exploration adds value.
​
Run a parallel code review
A single reviewer tends to gravitate toward one type of issue at a time. Splitting review criteria into independent domains means security, performance, and test coverage all get thorough attention simultaneously. The prompt assigns each teammate a distinct lens so they don’t overlap:
Spawn three teammates to review PR #142:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
Each reviewer works from the same PR but applies a different filter. The lead synthesizes findings across all three after they finish.
​
Investigate with competing hypotheses
When the root cause is unclear, a single agent tends to find one plausible explanation and stop looking. The prompt fights this by making teammates explicitly adversarial: each one’s job is not only to investigate its own theory but to challenge the others’.
Users report the app exits after one message instead of staying connected.
Spawn 5 agent teammates to investigate different hypotheses. Have them talk to
each other to try to disprove each other's theories, like a scientific
debate. Update the findings doc with whatever consensus emerges.
The debate structure is the key mechanism here. Sequential investigation suffers from anchoring: once one theory is explored, subsequent investigation is biased toward it.
With multiple independent investigators actively trying to disprove each other, the theory that survives is much more likely to be the actual root cause.
​
Best practices
​
Give teammates enough context
Teammates load project context automatically, including CLAUDE.md, MCP servers, and skills, but they don’t inherit the lead’s conversation history. See
Context and communication
for details. Include task-specific details in the spawn prompt:
Spawn a security reviewer teammate with the prompt: "Review the authentication module
at src/auth/ for security vulnerabilities. Focus on token handling, session
management, and input validation. The app uses JWT tokens stored in
httpOnly cookies. Report any issues with severity ratings."
​
Choose an appropriate team size
There’s no hard limit on the number of teammates, but practical constraints apply:
Token costs scale linearly
: each teammate has its own context window and consumes tokens independently. See
agent team token costs
for details.
Coordination overhead increases
: more teammates means more communication, task coordination, and potential for conflicts
Diminishing returns
: beyond a certain point, additional teammates don’t speed up work proportionally
Start with 3-5 teammates for most workflows. This balances parallel work with manageable coordination. If you have 15 independent tasks, 3 teammates is a good starting point.
Scale up only when the work benefits from having teammates work simultaneously. Three focused teammates often outperform five scattered ones.
​
Size tasks appropriately
Too small
: coordination overhead exceeds the benefit
Too large
: teammates work too long without check-ins, increasing risk of wasted effort
Just right
: self-contained units that produce a clear deliverable, such as a function, a test file, or a review
The lead breaks work into tasks and assigns them to teammates automatically. If it isn’t creating enough tasks, ask it to split the work into smaller pieces. Having 5-6 tasks per teammate keeps everyone productive and lets the lead reassign work if someone gets stuck.
​
Wait for teammates to finish
Sometimes the lead starts implementing tasks itself instead of waiting for teammates. If you notice this:
Wait for your teammates to complete their tasks before proceeding
​
Start with research and review
If you’re new to agent teams, start with tasks that have clear boundaries and don’t require writing code: reviewing a PR, researching a library, or investigating a bug. These tasks show the value of parallel exploration without the coordination challenges that come with parallel implementation.
​
Avoid file conflicts
Two teammates editing the same file leads to overwrites. Break the work so each teammate owns a different set of files.
​
Monitor and steer
Check in on teammates’ progress, redirect approaches that aren’t working, and synthesize findings as they come in. Letting a team run unattended for too long increases the risk of wasted effort.
​
Troubleshooting
​
Teammates not appearing
If teammates aren’t appearing after you ask Claude to spawn them:
In in-process mode, teammates appear in the agent panel below the prompt input. Use the up and down arrow keys to select one, then press Enter to view it.
A teammate row that disappeared after sitting idle has been hidden, not stopped. Idle rows hide 30 seconds after the whole panel goes idle and reappear on the teammate’s next turn. When more than three teammates are idle, their surplus rows collapse into a single
N idle agents
row that Enter expands. Send the teammate a message by name to bring a hidden row back.
Check that the task you gave Claude was complex enough to warrant a team. Claude decides whether to spawn teammates based on the task.
If you explicitly requested split panes, ensure tmux is installed and available in your PATH:
which
tmux
For iTerm2, verify the
it2
CLI is installed and the Python API is enabled in iTerm2 preferences.
​
Claude spawns teammates instead of subagents
While agent teams are enabled, a subagent that Claude names in the lead’s session launches as a teammate. Claude
can name subagents on its own
, so this can happen during delegation you never framed as team work.
To make named subagents launch as subagents again, turn agent teams off by setting
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
to
0
:
settings.json
{
"env"
: {
"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
:
"0"
}
}
You don’t need to start a new session: Claude Code reapplies settings-file
env
values to the running session when you save, and rereads the variable each time Claude spawns a subagent, so the next subagent Claude names launches as a subagent.
Setting the variable to
0
in your user
settings.json
overrides a shell export. Other settings sources can still enable agent teams:
Higher-precedence settings files
: project settings, local settings, and a
--settings
payload apply after user settings, so an
env
entry that sets the variable to
1
in any of them wins. See
Settings precedence
.
Managed settings
:
managed settings
apply after every other source. If your organization enables agent teams there, ask your administrator to change the managed value.
After the change, Claude may still name subagents, and the name keeps working as a
SendMessage
address
. Claude receives each subagent’s result when it completes.
​
Too many permission prompts
Teammate permission requests bubble up to the lead, which can create friction. Pre-approve common operations in your
permission settings
before spawning teammates to reduce interruptions.
​
Agents stopping early
Teammates may stop after encountering errors instead of recovering. Check their output by selecting the teammate in the agent panel and pressing Enter in in-process mode, or by clicking the pane in split mode, then either:
Give them additional instructions directly
Spawn a replacement teammate to continue the work
A message from the lead or another teammate wakes an in-process teammate that is waiting to retry a failed API request, so it retries immediately instead of waiting for the full retry delay.
The lead can stop early too, deciding the team is finished before all tasks are actually complete. If that happens, tell it to keep going.
​
Orphaned tmux sessions
If a tmux session persists after the Claude Code session ends, it may not have been fully cleaned up. List sessions and end the one created by the team:
tmux
ls
tmux
kill-session
-t
<
session-nam
e
>
​
Limitations
Agent teams are experimental. Current limitations to be aware of:
No session resumption with in-process teammates
:
/resume
and
/rewind
do not restore in-process teammates. After resuming a session, the lead may attempt to message teammates that no longer exist. If this happens, tell the lead to spawn new teammates.
Task status can lag
: teammates sometimes fail to mark tasks as completed, which blocks dependent tasks. If a task appears stuck, check whether the work is actually done and update the task status manually or tell the lead to nudge the teammate.
Shutdown can be slow
: teammates finish their current request or tool call before shutting down, which can take time.
One team per session
: a session has exactly one team, scoped to that session. You can’t create additional named teams or share a team across sessions.
No nested teams
: teammates cannot spawn their own teammates. Only the lead can manage the team.
No background subagents from in-process teammates
: an in-process teammate’s own subagents run in the foreground, because a teammate’s background work can’t outlive the lead’s process. Claude Code returns an error when a teammate spawns a subagent whose definition sets
background: true
. A teammate’s
run_in_background: true
request also fails, either with an error or by running silently in the foreground, as described in
how Claude Code picks foreground or background
. Subagents launched from the main conversation follow the
background default
.
Lead is fixed
: the main session is the lead for its lifetime. You can’t promote a teammate to lead or transfer leadership.
Permissions set at spawn
: all teammates start with the lead’s permission mode. You can change individual teammate modes after spawning, but you can’t set per-teammate modes at spawn time.
Split panes require tmux or iTerm2
: the default in-process mode works in any terminal. Split-pane mode isn’t supported in VS Code’s integrated terminal, Windows Terminal, or Ghostty.
​
Next steps
Explore related approaches for parallel work and delegation:
Lightweight delegation
:
subagents
spawn helper agents for research or verification within your session, better for tasks that don’t need inter-agent coordination
Messaging between your own sessions
:
cross-session messaging
lets Claude pass findings between the sessions you run yourself
Manual parallel sessions
:
Git worktrees
let you run multiple Claude Code sessions yourself without automated team coordination
Was this page helpful?
Yes
No
Assistant
Responses are generated using AI and may contain mistakes.

## Source (commands): https://docs.claude.com/en/docs/claude-code/commands

Commands - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Commands control Claude Code from inside a session. They provide a quick way to switch models, manage permissions, clear context, run a workflow, and more.
Type
/
to see the commands available to you, or type
/
followed by letters to filter.
How the command menu matches what you type
covers highlighting, typos, and the few commands Claude Code hides from the menu until you type their full name.
A command is only recognized at the start of your message. Text that follows the command name becomes its arguments. As of v2.1.199,
skills
are the exception: a skill invocation followed by more skills, such as
/skill-a /skill-b do XYZ
, loads every skill named at the start and passes the trailing text to each as arguments. Up to six skills can be chained.
If you send a command while Claude is responding, Claude Code queues it and runs it after the current turn finishes. Claude Code runs some commands immediately without interrupting the response, such as
/status
,
/tasks
, and
/usage
. In
fullscreen rendering
, Claude Code also opens dialog commands such as
/theme
and
/help
immediately. Before v2.1.234, Claude Code queued those dialogs until the turn finished.
​
Commands across a typical workflow
Most commands are useful at a specific point in a session, from setting up a project to shipping a change.
First session in a repo.
Run
/init
to generate a starter
CLAUDE.md
, then
/memory
to refine it. Use
/mcp
to set up any servers the project needs, ask Claude to create any
subagents
you want, and run
/permissions
to set your approval rules.
During a task.
/plan
switches into plan mode before a large change.
/model
and
/effort
adjust which model you’re using and how much reasoning it applies. When the conversation gets long,
/context
shows what’s filling the window and
/compact
summarizes it to free space. Use
/btw
for a side question that shouldn’t add to the conversation history.
Run work in parallel.
Claude delegates side tasks to
subagents
, and
/tasks
lists the current session’s background work, including subagents that have finished.
/background
detaches the whole session to keep running as a
background agent
and frees your terminal. For a large change that spans the codebase,
/batch
decomposes it into independent units and runs each in its own
worktree
. See
Run agents in parallel
for how these approaches relate.
Before you ship.
/diff
shows what changed.
/code-review
checks the current diff for correctness bugs and cleanups and can apply the findings with
--fix
; pass a PR number, such as
/code-review high 1234
, to review a pull request instead.
/review
is an alias.
/code-review ultra
runs a multi-agent review in the cloud.
/security-review
checks the diff for security vulnerabilities.
Between sessions.
/clear
starts fresh on a new task while keeping project memory.
/resume
returns to an earlier conversation,
/branch
branches the current one to try a different direction, and
/fork
copies it into a new
background session
.
/teleport
pulls a web session into this terminal, and
/remote-control
lets you continue this local session from another device.
When something is wrong.
/rewind
rolls code and conversation back to a checkpoint, or summarizes part of the conversation.
/doctor
runs a setup checkup that diagnoses installation and configuration issues and can fix them,
/debug
diagnoses runtime issues, and
/feedback
reports a bug with session context attached.
​
All commands
The table below lists all the commands included in Claude Code. Most are built-in commands whose behavior is coded into the CLI. Two kinds of entries are marked:
Skill
: a bundled skill. It works like skills you write yourself: a prompt handed to Claude.
/verify
runs only when you invoke it. Before v2.1.215, Claude could also run
/verify
on its own.
Workflow
: a bundled
dynamic workflow
that fans work out across many subagents and runs in the background.
/deep-research
runs only when you invoke it. Before v2.1.218, Claude could also start it on its own.
To add your own commands, see
skills
.
In the table below,
<arg>
indicates a required argument and
[arg]
indicates an optional one.
Not every command appears for every user. Availability depends on your platform, plan, and environment. For example,
/desktop
only shows on macOS and x64 Windows when signed in with a Claude subscription, and
/upgrade
doesn’t show on Enterprise plans.
Command
Purpose
/add-dir <path>
Add a working directory for file access during the current session. Type a partial path to see matching directory suggestions; press
Tab
to accept one. Most
.claude/
configuration is
not discovered
from the added directory. A successful add runs your
DirectoryAdded
hooks
. When you run it while Claude is responding, Claude Code asks you to confirm the directory right away, and once you confirm, Claude’s next tool call in the same turn can access it. Before v2.1.234, Claude Code queued the command until the turn finished
/advisor [model|off]
Enable or disable the
advisor tool
, which consults a second model for guidance at key moments during a task. Accepts
fable
,
opus
,
sonnet
, or a full model ID.
fable
requires
Fable 5 access
. Without an argument, opens a picker
/agents
As of v2.1.198, running
/agents
prints a reminder to ask Claude to create or manage
subagents
, or to edit
.claude/agents/
or
~/.claude/agents/
directly. On v2.1.197 and earlier, opens an interactive interface for creating and managing subagent configurations
/artifacts
List the
artifacts
you own or that are shared with you, then attach one to the session, open it in your browser, or copy its link. Available where
artifacts
are. Requires Claude Code v2.1.208 or later; attaching with
Enter
requires v2.1.216
/auto-mode-setup
Draft
autoMode.environment
entries
from your project and recent sessions, then review the draft and save it to your user settings. Requires a Pro, Max, or Team plan and Claude Code v2.1.228 or later. On native Windows, requires v2.1.233 or later
/autocompact [auto|<tokens>]
Set the auto-compact window: how full the context window gets before Claude Code compacts automatically. Pass a size such as
500k
, or
auto
to return to the window tuned for your model. Claude Code saves the value to user settings and applies it to the current session. See
Set the auto-compact window
for accepted values and what overrides it. Without an argument, opens a dialog that shows the current window. Requires Claude Code v2.1.221 or later
/autofix-pr [prompt]
Spawn a
Claude Code on the web
session that watches the current branch’s PR and pushes fixes when CI fails or reviewers leave comments. Detects the open PR from your checked-out branch with
gh pr view
; to watch a different PR, check out its branch first. By default the cloud session is told to fix every CI failure and review comment; pass a prompt to give it different instructions, for example
/autofix-pr only fix lint and type errors
. Requires the
gh
CLI and access to
Claude Code on the web
/background [prompt]
Detach the current session to run as a
background agent
and free this terminal. Pass a prompt to send one more instruction before detaching. Monitor the session with
claude agents
. To copy the conversation into a new background session while this one keeps running, use
/fork
. Alias:
/bg
/batch <instruction>
Skill
.
Orchestrate large-scale changes across a codebase in parallel. Researches the codebase, decomposes the work into 5 to 30 independent units, and presents a plan. Once approved, spawns one
background subagent
per unit in an isolated
git worktree
. Each subagent implements its unit, runs tests, and opens a pull request. Requires a git repository. Example:
/batch migrate src/ from JavaScript to TypeScript
/branch [name]
Create a branch of the current conversation at this point, so you can try a different direction without losing the conversation as it stands. Switches you into the branch and preserves the original, which you can return to with
/resume
. To run a copy as a separate
background session
instead of switching into it, use
/fork
; to hand a side task to a
subagent
that reports back into this conversation, use
/subtask
/btw [question]
Ask a
side question
about the current session without adding to the conversation. If you run
/btw
without a question, Claude Code shows your most recent side question so you can browse earlier answers; if you haven’t asked one yet, Claude Code prints a usage line. Before v2.1.212,
/btw
required a question
/bug [report]
Report a bug or share your conversation. You choose how much session history to include and confirm on a consent screen before anything is sent. When you’re signed in to Anthropic on a first-party connection, the report goes to Anthropic; on a third-party provider, or without Anthropic credentials, Claude Code writes the report to a
local archive under
~/.claude/feedback-bundles/
that you forward yourself. In the
VS Code extension
,
/bug
opens the extension’s own feedback dialog instead; requires Claude Code v2.1.229 or later. When you run it while Claude is responding, Claude Code opens the dialog immediately. Before v2.1.232, Claude Code queued the command until the turn finished. Alias:
/share
. Before v2.1.212,
/bug
and
/share
were aliases of
/feedback
/cd <path>
Move this session to a new working directory, keeping the conversation. Type a partial path to see matching directory suggestions; press
Tab
to accept one. The suggestions require Claude Code v2.1.206 or later. For what Claude Code applies from the new directory as soon as you move, and how
/cd
differs from
/add-dir
, see
Move the session to another directory
. Requires Claude Code v2.1.169 or later
/chrome
Configure
Claude in Chrome
settings
/claude-api [migrate|upgrade|managed-agents-onboard|prompt-audit|cost-optimize]
Skill
.
Load
Claude API
and
Managed Agents
reference material for your project’s language. Also activates automatically when your code imports
anthropic
or
@anthropic-ai/sdk
. Run
migrate
to update existing Claude API code to a newer model. Run
upgrade
to move your project’s Anthropic SDK dependency across a major version, currently the Python
anthropic
package from 0.x to 1.x. Run
managed-agents-onboard
for a walkthrough that creates a new Managed Agent. Run
prompt-audit
to flag instructions written for older models in your prompts, skills, and tool descriptions and propose fixes as a diff. Run
cost-optimize
to profile where your project’s Claude API spend goes and propose savings from options such as prompt caching, trimming unneeded input and output tokens, batch processing, effort, and model choice, one change at a time. The
prompt-audit
subcommand requires Claude Code v2.1.221 or later,
upgrade
requires v2.1.236 or later, and
cost-optimize
requires v2.1.247 or later
/clear [name]
Start a new conversation with empty context. Pass a name to label the previous conversation in the
/resume
picker. To free up context while continuing the same conversation, use
/compact
instead. Resume the previous conversation with
/resume
, or, in the same Claude Code process, restore it from
the rewind menu’s previous-session entry
. The rewind entry requires Claude Code v2.1.191 or later. Aliases:
/reset
,
/new
/code-review [low|medium|high|xhigh|max|ultra] [--fix] [--comment] [pr#|branch|path]
Skill
.
Review the current diff, or a PR number, branch, or path you pass, for correctness bugs and cleanup opportunities. Pass
--fix
to apply findings,
--comment
to post them as inline GitHub PR comments, or
ultra
to run a deep
cloud review
. With
ultra
on a
github.com
PR target,
--post
preselects
posting the finished findings to the PR
in the launch dialog. See
Review a diff locally
for the effort levels, targeting, and how it relates to
/simplify
. Alias:
/review
/color [color|default]
Set the prompt bar color for the current session. Available colors:
red
,
blue
,
green
,
yellow
,
purple
,
orange
,
pink
,
cyan
. Use
default
to reset, or run with no argument to pick a random color. When
Remote Control
is connected, the color syncs to claude.ai/code. Also available in non-interactive mode (
-p
); requires Claude Code v2.1.205 or later
/compact [instructions]
Free up context by summarizing the conversation so far. Optionally pass focus instructions for the summary. See
how compaction handles rules, skills, and memory files
/config [key=value ...]
Open the
Settings
interface to adjust theme, model,
output style
, and other preferences. From v2.1.181, pass one or more
key=value
pairs to set a setting directly without opening the interface, for example
/config thinking=false
. From v2.1.182, named shorthand keys are also accepted, such as
/config theme=dark
or
/config model=sonnet
. The
key=value
form also works in non-interactive mode (
-p
) and from the Claude mobile app via
Remote Control
. The
key=value
form can’t turn on a setting that needs your confirmation in the panel, such as
autoContinueAtUsageLimit
, though it can turn one off. Run
/config --help
to list the keys it accepts. Alias:
/settings
/context [all]
Visualize current context usage as a colored grid. Shows optimization suggestions for context-heavy tools, memory bloat, and capacity warnings. When the conversation exceeds the context window, the output includes a
warning
showing how far over the limit you are and which command frees space. In
fullscreen mode
,
/context
collapses the per-item breakdown to keep the grid visible. Pass
all
to expand it
/copy [N]
Copy the last assistant response to clipboard. Pass a number
N
to copy the Nth-latest response:
/copy 2
copies the second-to-last. When code blocks are present, shows an interactive picker to select individual blocks or the full response. Press
w
in the picker to write the selection to a file instead of the clipboard, which is useful over SSH
/cost
Alias for
/usage
/dataviz [request]
Skill
.
Design guidance for charts, graphs, and dashboards. Claude picks the chart form for the data, assigns color by role, validates the palette for colorblind safety and contrast with a bundled script, and applies mark, interaction, and accessibility rules. Uses a brand-neutral placeholder palette that you replace with your own. Requires Claude Code v2.1.198 or later
/debug [description]
Skill
.
Enable debug logging for the current session and troubleshoot issues by reading the session debug log. Debug logging is off by default unless you started with
claude --debug
, so running
/debug
mid-session starts capturing logs from that point forward. Optionally describe the issue to focus the analysis
/deep-research <question>
Workflow
.
Fan out web searches on a question, fetch and cross-check sources, and synthesize a cited report
/design-login
Authorize design-system access for
/design-sync
with your claude.ai account
/design-sync [hint]
Skill
.
Convert your repo’s React design system and upload it to
Claude Design
, so designs it produces use your real components. Optionally name the design system, for example
/design-sync Acme DS
. A first-time sync verifies every component and can take a few hours on a large repo. Available on the Anthropic API; on Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, and Claude Platform on AWS the underlying tool can’t reach claude.ai, so the command is unavailable
/desktop
Continue the current session in the Claude Code Desktop app. Requires macOS or x64 Windows and a Claude subscription. Alias:
/app
/diff
Open an interactive diff viewer showing uncommitted changes and per-turn diffs. Use left/right arrows to switch between the current git diff and individual Claude turns, and up/down to browse files. Press Enter to open the selected file’s diff, scroll it with up/down or PageUp/PageDown, and press Esc to return to the file list. Claude Code computes these diffs from raw git blob content, so diff drivers and
textconv
filters configured in
.gitattributes
or git config don’t apply. Before v2.1.222, workspace-configured drivers and filters could rewrite the viewer’s output. The open viewer also refreshes automatically when the repository’s git state changes outside the session, such as a branch switch or commit in another terminal; the auto-refresh requires Claude Code v2.1.198 or later
/doctor
Skill
.
Run a setup checkup that diagnoses issues and can fix them. Checks installation health, including duplicate or leftover installs,
PATH
problems, and unparseable settings files. Finds unused skills, MCP servers, and plugins versus their context cost, flags slow
hooks
, and checks for a newer version on your
release channel
. Deduplicates local
CLAUDE.md
files against checked-in ones, trims checked-in
CLAUDE.md
files by cutting content Claude could derive from the codebase, and migrates the always-loaded guidance that remains into
skills
and nested
CLAUDE.md
files that load on demand. Also offers to make
auto mode
your default and to
pre-approve
frequently denied read-only commands. Reports findings first and asks for confirmation before changing anything. From the terminal,
claude doctor
prints read-only installation diagnostics without starting a session. Alias:
/checkup
. The
CLAUDE.md
trim check requires Claude Code v2.1.206 or later. Before v2.1.205,
/doctor
opened a read-only diagnostics screen and pressing
f
sent the report to Claude
/effort [level|auto|status]
Set the
effort level
:
low
to
xhigh
,
max
,
ultracode
, or
auto
;
status
prints it.
max
and
ultracode
are session-only; the
ultracode
key persists. Run it while Claude is responding and, once you confirm the
cache warning
, if Claude Code shows one, Claude Code applies the new level to the next request in that turn. Before v2.1.242, Claude Code decided from a feature flag it fetched from Anthropic whether to run the command mid-turn or queue it until the turn finished, and always queued it in a session that doesn’t
fetch feature flags
, such as on a
third-party provider
. Works in
-p
outside the
effort hold
/exit
Exit the CLI. In an attached
background session
, this detaches and the session keeps running. Alias:
/quit
/export [filename]
Export the current conversation as plain text. With a filename, writes directly to that file. Without, opens a dialog to copy to clipboard or save to a file
/fast [on|off]
Toggle
fast mode
on or off. Run it while Claude is responding and Claude Code toggles fast mode without waiting for the turn to end, though the running turn finishes at its original speed. Before v2.1.242, Claude Code decided from a feature flag it fetched from Anthropic whether to run the command mid-turn or queue it until the turn finished, and always queued it in a session that doesn’t
fetch feature flags
. Availability in non-interactive mode with
-p
is limited; see
Toggle fast mode
. Requires Claude Code v2.1.205 or later
/feedback [report]
Send product feedback about Claude Code. Opens the same dialog as
/bug
, with the same consent step, sending rules, and mid-turn behavior. In sessions with
Claude-drafted feedback
,
/feedback
with no argument opens the drafts queue instead, where you review, edit, send, or discard the drafts Claude queued; the queue includes an option to write a new report in the dialog. With an argument, and for
/bug
always, the dialog opens directly
/fewer-permission-prompts
Skill
.
Scan your transcripts for common read-only Bash and MCP tool calls, then add a prioritized allowlist to project
.claude/settings.json
to reduce permission prompts
/focus
Toggle the focus view, which shows only your last prompt, a one-line tool-call summary with edit diffstats, and the final response. The tool-call summary also counts the subagents launched in the turn and collapses completed background-task notifications into a single count. The selection persists across sessions; set
viewMode
in settings to override it. Only available in
fullscreen rendering
. The
VS Code extension
offers its own Focus view as a command-menu toggle, stored as an extension setting, independent of
viewMode
/fork [prompt]
Copy the current conversation
into a new background session and keep working here. Pass a prompt and the copy starts working on it immediately; without one it waits in agent view for its first prompt. Except when the copy
edits in place
, Claude Code instructs it to create a worktree of its own before making code changes; the isolation instruction requires Claude Code v2.1.221 or later. To hand a side task to a subagent whose result comes back into this conversation, use
/subtask
; to switch into a copy yourself, use
/branch
. Requires Claude Code v2.1.212 or later; on v2.1.161 through v2.1.211, and whenever
agent view is turned off
,
/fork
starts a
forked subagent
instead
/goal [condition|clear]
Set a
goal
: Claude keeps working across turns until the condition is met or the goal
clears for another reason
. With no argument, shows the current or most recently achieved goal.
clear
,
stop
,
off
,
reset
,
none
, or
cancel
removes an active goal early
/heapdump
Write a JavaScript heap snapshot and a memory breakdown to
~/Desktop
, or your home directory on Linux without a Desktop folder, for diagnosing high memory usage. Attach only the
-diagnostics.json
file when reporting a memory issue; the
.heapsnapshot
contains your full conversation and credentials, so don’t share it.
Hidden from the command menu
; type it in full. See
what to do with the output
/help
Show help and available commands
/hooks
View
hook
configurations for tool events
/ide
Manage IDE integrations and show status
/import [codex|gemini] [--dry-run] [--yes]
Bring configuration from other coding agents on your machine, currently OpenAI Codex and Google Gemini CLI, into Claude Code, including instruction files, MCP servers, commands, subagents, and skills. In
non-interactive mode
with
-p
,
/import
lists what it found and gives you the command that confirms the import. Add
--dry-run
to preview without writing anything, or
--yes
to skip the interactive picker. Not available on Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, or Claude Platform on AWS. Also unavailable when you turn off
feature-flag fetching
. Requires Claude Code v2.1.213 or later
/init
Initialize project with a
CLAUDE.md
guide. Set
CLAUDE_CODE_NEW_INIT=1
for an interactive flow that also walks through skills, hooks, and personal memory files. If
/init
finds configuration from a coding agent that
/import
supports, it offers to carry it over with
/import
/insights
Generate an HTML report analyzing your recent sessions on this machine: which projects you work in, how you use Claude Code, where things go wrong, and features to try. Not available in
cloud sessions
. See
Analyze your usage patterns
for the report location, retention, and cost
/install-github-app
Install the Claude GitHub App for a repository, with an optional step to set up
GitHub Actions
workflows and secrets. Walks you through selecting a repo and configuring the integration
/install-slack-app
Install the Claude Slack app. Opens a browser to complete the OAuth flow
/keybindings
Open your
keyboard shortcuts
file
/list-agents
List the subagents,
agent team
teammates, and other Claude Code sessions Claude can message, with the name to use for each. See
cross-session messaging
. Also available as
/peers
. Requires Claude Code v2.1.224 or later; earlier versions report
Unknown command: /list-agents
. Teammate rows and the first line showing this session’s own name require v2.1.239 or later. Available only in sessions where
cross-session messaging is enabled
/login
Sign in to your Anthropic account
/logout
Sign out from your Anthropic account
/loop [interval] [prompt]
Skill
.
Run a prompt repeatedly while the session stays open. Omit the interval and Claude
self-paces between iterations
. Omit the prompt and Claude runs the
built-in maintenance prompt
or your
loop.md
. Example:
/loop 5m check if the deploy finished
. See
Run prompts on a schedule
. Alias:
/proactive
/mcp [reconnect <server>|enable|disable [<server>|all]]
Manage MCP server connections and OAuth authentication. Run with no argument to open the interactive list, pass
reconnect <server>
to reconnect one disconnected server, or pass
enable
/
disable
with a server name or
all
to change connection state without opening the dialog. Also available in non-interactive mode (
-p
), where running it with no argument prints a text summary of server status instead of opening the list; requires Claude Code v2.1.205 or later
/memory
Edit
CLAUDE.md
files, enable or disable
auto memory
, and view auto memory entries
/mobile
Show QR code to download the Claude mobile app. Aliases:
/ios
,
/android
/model [model]
Switch the AI model and save it as your default for new sessions. For models that support it, use left/right arrows to
adjust effort level
. With no argument, opens a picker; press
s
on a row to switch for the current session only. See
when Claude Code asks you to confirm the switch
. Once you confirm the switch, if Claude Code asks, Claude Code applies the change without waiting for the current response to finish. Before v2.1.242, Claude Code decided from a feature flag it fetched from Anthropic whether to run the command mid-turn or queue it until the turn finished, and always queued it in a session that doesn’t
fetch feature flags
, such as on a
third-party provider
. Also available in non-interactive mode (
-p
) with a model argument instead of the picker, where it applies to the current session only and isn’t saved as your default; requires Claude Code v2.1.205 or later
/passes
Share a free week of Claude Code with friends. Only visible if your account is eligible
/permissions
Manage allow, ask, and deny rules for tool permissions. Opens an interactive dialog where you can view rules by scope, add or remove rules, manage working directories, and review
recent auto mode denials
. You can also view and edit
auto mode classifier rules
from the dialog’s
Auto mode
tab. When you run it while Claude is responding, Claude Code opens the dialog immediately and applies your changes starting with Claude’s next tool call in the same turn. Before v2.1.234, Claude Code queued the command until the turn finished. Alias:
/allowed-tools
/plan [description]
Enter plan mode directly from the prompt. Pass an optional description to enter plan mode and immediately start with that task, for example
/plan fix the auth bug
/plugin [subcommand]
Manage Claude Code
plugins
. Run with no argument to open the plugin menu, or pass a subcommand such as
list
,
install
,
enable
, or
disable
to act directly. Claude Code can activate a plugin during the install; the
install summary
tells you whether it did or whether to run
/reload-plugins
/powerup
Discover Claude Code features through quick interactive lessons with animated demos
/pr-comments [PR]
Removed in v2.1.91. Ask Claude directly to view pull request comments instead. On earlier versions, fetches and displays comments from a GitHub pull request; automatically detects the PR for the current branch, or pass a PR URL or number. Requires the
gh
CLI
/privacy-settings
View and update your privacy settings. Only available for Pro and Max plan subscribers
/radio
Open Claude FM lo-fi radio in your browser. Prints the stream URL when no browser is available
/rate-limit-options
Show ways to keep working when a claude.ai usage limit blocks a request: wait and
continue automatically when the limit resets
, add
usage credits
, or upgrade your plan. Claude Code can also open this menu on its own when you hit a limit at your own terminal. See
Turn automatic continue off
. Requires a claude.ai subscription. Doesn’t appear in the command menu; type it in full. The wait-and-continue rows require Claude Code v2.1.234 or later
/recap
Generate a one-line summary of the current session on demand. See
Session recap
for the automatic recap that appears after you’ve been away
/release-notes
View the changelog in an interactive version picker. Select a specific version to see its release notes, or choose to show all versions. The notes appear in your transcript without entering the conversation Claude sees
/reload-plugins [--force]
Reload all active
plugins
to apply pending changes without restarting. Reports counts for each reloaded component and flags any load errors. When the reload would change which MCP tools are loaded and invalidate the prompt cache, the command warns and skips unless you pass
--force
/reload-skills
Re-scan
skill
and command directories so skills added or changed on disk during the session become available without restarting. Reports how many skills are available and how many were added or removed
/remote-control
Make this session available for
Remote Control
from claude.ai. Running it while signed out prints that Remote Control requires a claude.ai subscription and tells you how to sign in; before v2.1.206 it reported
Unknown command: /remote-control
. Alias:
/rc
/remote-env
Choose the default environment for
cloud agents
/rename [name]
Rename the current session and show the name on the prompt bar. Without a name, auto-generates one from conversation history. Also available in non-interactive mode (
-p
); requires Claude Code v2.1.205 or later. From every rename surface, including claude.ai and the desktop app, Claude Code replaces control and invisible characters in the new name with spaces and caps the name at 200 characters. If the name is empty once invisible characters are removed, Claude Code rejects it and shows
That name is empty once invisible characters are removed. Usage: /rename <name>
. The character replacement and length cap require Claude Code v2.1.221 or later. If another live session on this machine already uses a name you pass, Claude Code applies
a variant of it
instead
/resume [session]
Resume a conversation by ID or name, or open the session picker.
Background sessions
appear in the picker marked with
bg
; one that is still running can’t be resumed here, so attach to it from
claude agents
or stop it there first. Alias:
/continue
/review [low|medium|high|xhigh|max|ultra] [--fix] [--comment] [pr#|branch|path]
Alias of
/code-review
: reviews the current diff, or a PR number, branch, or path you pass, such as
/review 1234
, and takes the same effort levels and flags. With no level given, the review reuses the last
low
through
max
level you typed; see
Review a diff locally
for the exact rules. For a deep cloud review, use
/code-review ultra
. Before v2.1.223,
/review
was a separate command that ran a single-pass, read-only review of a GitHub pull request by number, listing open PRs to pick from when run with no argument; from v2.1.186 through v2.1.201, it ran the same multi-agent engine as
/code-review medium
/rewind
Rewind the conversation and/or code to a previous point, or summarize from a selected message. See
checkpointing
. Aliases:
/checkpoint
,
/undo
/run
Skill
.
Launch and drive your project’s app to see a change working, not only passing tests. See
Run and verify your app
/run-skill-generator
Skill
.
Teach
/run
and
/verify
how to build, launch, and drive your project’s app from a clean environment by writing a per-project
skill
/sandbox
Toggle
sandbox mode
. Available on supported platforms only
/schedule [description]
Create, update, list, or run
routines
, which execute in the cloud. Claude walks you through the setup conversationally. You can also ask about a
routine’s recent runs
. Alias:
/routines
/scroll-speed
Adjust mouse wheel
scroll speed
interactively, with a ruler you can scroll while the dialog is open to preview the change. Available in
fullscreen rendering
only and not in the JetBrains IDE terminal
/security-review
Analyze the changes on your current branch for security vulnerabilities. Reviews the diff between your branch and origin’s default branch, identifying risks like injection, auth issues, and data exposure. Needs an
origin
remote; if the review fails with an
ambiguous argument
error, see the
error reference
/setup-bedrock
Configure
Amazon Bedrock
authentication, region, and model pins through an interactive wizard.
Hidden from the command menu
until
CLAUDE_CODE_USE_BEDROCK=1
is set; type it in full. First-time Amazon Bedrock users can also access this wizard from the login screen
/setup-vertex
Configure
Google Cloud’s Agent Platform
authentication, project, region, and model pins through an interactive wizard.
Hidden from the command menu
until
CLAUDE_CODE_USE_VERTEX=1
is set; type it in full. First-time Google Cloud’s Agent Platform users can also access this wizard from the login screen
/simplify [target]
Skill
.
Review the changed code for cleanup opportunities and apply the fixes. Four review
agents
run in parallel, covering reuse of existing helpers, simplification, efficiency, and whether the change is at the right level of abstraction. The review doesn’t look for correctness bugs. Use
/code-review
to find bugs. Pass a path or PR reference to review a specific target
/skills
List available
skills
. Type to filter the list by name, description, or source. Press
t
to sort by token count,
Space
or
Enter
to
cycle a skill’s visibility to Claude and the
/
menu
, and
Esc
to save and close. You can’t cycle plugin skills, skills whose frontmatter sets
disable-model-invocation: true
, or skills with a
skillOverrides
entry in managed settings or the
--settings
flag
/stats
Alias for
/usage
. Opens on the Stats tab
/status
Open the Settings interface on the Status tab, showing version, model, account, and connectivity. A
Session kind
row reads
background job · attached
or
background job · unattended
in a
background session
, depending on whether a terminal is attached, and
interactive
in any other session. Before v2.1.221,
/status
didn’t show this row. Works while Claude is responding
/statusline
Configure Claude Code’s
status line
. Describe what you want, or run without arguments to auto-configure from your shell prompt
/stickers
Order Claude Code stickers
/stop
Stop the current
background session
. Only available while attached to a background session; the transcript and any worktree are kept. To detach without stopping, use
/exit
or press
←
/subtask <task>
Spawn a
forked subagent
: a background subagent that inherits the full conversation and works on the task while you keep working. Its result returns to this conversation when it finishes. To copy the conversation into a separate background session instead, use
/fork
. Requires Claude Code v2.1.212 or later; on v2.1.161 through v2.1.211 this command is
/fork
. When
agent view is turned off
,
/subtask
isn’t available and
/fork
keeps the forked-subagent behavior
/tasks
View and manage background work in the current session, including subagents that have finished. Also available as
/bashes
/team-onboarding
Generate a team onboarding guide from your Claude Code usage history. Claude analyzes your sessions, commands, and MCP server usage from the past 30 days and produces a markdown guide a teammate can paste as a first message to get set up quickly. For claude.ai subscribers on Pro, Max, Team, and Enterprise plans, also returns a share link teammates can open directly in Claude Code
/teleport
Pull a
Claude Code on the web
session into this terminal. Opens a picker, then fetches the branch and conversation. Also available as
/tp
. Requires a claude.ai subscription
/terminal-setup
Install a Shift+Enter keybinding for newlines
in VS Code, Cursor, Devin Desktop, Alacritty, or Zed. In Apple Terminal,
enable Option+Enter for newlines and turn off the audible bell
instead. In iTerm2,
turn on clipboard access so that
/copy
works
/theme
Change the color theme. Includes an
auto
option that matches your terminal’s light or dark background, light and dark variants, colorblind-accessible (daltonized) themes, ANSI themes that use your terminal’s color palette, and any
custom themes
from
~/.claude/themes/
or plugins. Select
New custom theme…
to create one
/tui [default|fullscreen]
Set the terminal UI renderer and relaunch into it with your conversation intact.
fullscreen
enables the
flicker-free alt-screen renderer
. With no argument, prints the active renderer
/ultraplan <prompt>
Removed. Use
plan mode
instead. Previously sent a planning task to a
Claude Code on the web
session for review in your browser
/ultrareview [PR or branch]
Run a deep, multi-agent code review in a cloud sandbox with
ultrareview
. Pass a PR reference to review that pull request, or a branch name to change the comparison base. The preferred invocation is now
/code-review ultra
, and
/ultrareview
remains as an alias. Includes 3 free runs on Pro and Max, then requires
usage credits
/upgrade
Open the upgrade page in your browser to switch to a higher plan tier. When the browser fails to open, the command shows a sign-in prompt without printing the URL
/usage
Show session cost, plan usage limits, and activity stats. On a Pro, Max, Team, or Enterprise plan, includes a
breakdown of what counts against your plan limits
.
/cost
and
/stats
are aliases
/usage-credits
Configure usage credits, or request them from your admin, when you hit a limit. Opens your
usage-credits billing settings
in the browser, except that Team and Enterprise members without billing access instead send a usage-credits request to their admin from the CLI, after confirming in a dialog that the request notifies their admins. When no browser can open the billing page, for example over SSH, the command prints the URL to visit instead; this requires Claude Code v2.1.205 or later, and earlier versions showed nothing in that case. Previously
/extra-usage
/verify
Skill
.
Confirm a code change does what it should by building your project’s app, running it, and observing the result, rather than relying on tests or type checks. See
Run and verify your app
/vim
Removed in v2.1.92. To toggle between Vim and Normal editing modes, use
/config
→ Editor mode
/voice [hold|tap|off]
Toggle
voice dictation
, or enable it in a specific mode. Requires a Claude.ai account
/web-setup
Connect your GitHub account to
Claude Code on the web
using your local
gh
CLI credentials
/workflow-authoring
Skill
.
Load the reference for writing
dynamic workflow
scripts: the script API, resume behavior, quality patterns, and worked examples. Claude normally loads it on its own before writing a script; run it yourself before
editing a saved script by hand
. Available when dynamic workflows are enabled, and requires Claude Code v2.1.248 or later
/workflows
Open the
workflow
progress view to watch, pause, resume, or save running and completed workflows
​
How the command menu matches what you type
Claude Code filters the
/
menu as you type. Each bullet below covers one thing you might notice while filtering:
Highlighting
: Claude Code highlights the top suggestion only when the letters after the
/
match a command’s name or alias, from the start of the name or from a word within it, ignoring the
:
,
_
, and
-
separators. Typing
/adddir
highlights
/add-dir
, and typing
/new
highlights
/clear
through its alias. Press
Enter
to run the highlighted suggestion. These highlighting rules require Claude Code v2.1.236 or later.
After a typo
: Claude Code highlights nothing. The close matches stay listed, and you can pick one with
Tab
or the arrow keys, but
Enter
submits your text as typed and reports
Unknown command
.
Commands that aren’t available to you
: Claude Code leaves them out of the menu. When nothing matches, Claude Code shows
No commands match "/name"
. Most unavailable commands return
Unknown command
when you submit them; a few, such as
/schedule
on a Console API key
, answer with their own availability message instead. Some commands also answer with a message of their own when your organization’s policy disables them.
Hidden commands
: Claude Code keeps a few available commands, such as
/heapdump
, out of the menu by design. A partial name never brings a hidden command into the menu: if the partial matches nothing visible, Claude Code shows the same no-match message. Claude Code lists the command only once you’ve typed its full name, and submitting the full name runs it.
​
MCP prompts
MCP servers can expose prompts that appear as commands. See
MCP prompts
for details.
​
See also
Skills
: create your own commands
Interactive mode
: keyboard shortcuts, Vim mode, and command history
CLI reference
: launch-time flags
Was this page helpful?
Yes
No
Assistant
Responses are generated using AI and may contain mistakes.

## Source (plugins): https://docs.claude.com/en/docs/claude-code/plugins

Create plugins - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Plugins let you extend Claude Code with custom functionality that can be shared across projects and teams. This guide covers creating your own plugins with skills, agents, hooks, and MCP servers.
Looking to install existing plugins? See
Discover and install plugins
. For complete technical specifications, see
Plugins reference
.
​
When to use plugins vs standalone configuration
Claude Code supports two ways to add custom skills, agents, and hooks:
Approach
Skill names
Best for
Standalone
(
.claude/
directory)
/hello
Personal workflows, project-specific customizations, quick experiments
Plugins
(self-contained directories with skills, agents, hooks, or a
.claude-plugin/plugin.json
manifest)
/plugin-name:hello
Sharing with teammates, distributing to community, versioned releases, reusable across projects
Start with standalone configuration in
.claude/
for quick iteration, then
convert to a plugin
when you’re ready to share.
​
Quickstart
This quickstart walks you through creating a plugin with a custom skill. You’ll create a manifest (the configuration file that defines your plugin), add a skill, and test it locally using the
--plugin-dir
flag.
​
Prerequisites
Claude Code
installed and authenticated
​
Create your first plugin
1
Create the plugin directory
Every plugin lives in its own directory containing your skills, agents, or hooks, optionally alongside a
.claude-plugin/plugin.json
manifest. The location doesn’t matter for this quickstart because you’ll point Claude Code at the directory with
--plugin-dir
in the test step. Create it anywhere convenient, such as a scratch folder or a projects directory:
mkdir
my-first-plugin
The remaining steps run from the parent directory and reference paths like
my-first-plugin/...
relative to it.
2
Create the plugin manifest
The manifest file at
.claude-plugin/plugin.json
defines your plugin’s identity: its name, description, and version. Claude Code uses this metadata to display your plugin in the plugin manager.
Create the
.claude-plugin
directory inside your plugin folder:
mkdir
my-first-plugin/.claude-plugin
Then create
my-first-plugin/.claude-plugin/plugin.json
with this content:
my-first-plugin/.claude-plugin/plugin.json
{
"name"
:
"my-first-plugin"
,
"description"
:
"A greeting plugin to learn the basics"
,
"version"
:
"1.0.0"
,
"author"
: {
"name"
:
"Your Name"
}
}
Field
Purpose
name
Unique identifier and skill namespace. Skills are prefixed with this (e.g.,
/my-first-plugin:hello
).
description
Shown in the plugin manager when browsing or installing plugins.
version
Optional. If set, users only receive updates when you bump this field, except for a
command
source
; see
version management
. If omitted, the version comes from the next source in
version management
.
author
Optional. Helpful for attribution.
For additional fields like
homepage
,
repository
, and
license
, see the
full manifest schema
.
3
Add a skill
Skills live in the
skills/
directory. Each skill is a folder containing a
SKILL.md
file. The folder name becomes the skill name, prefixed with the plugin’s namespace (
hello/
in a plugin named
my-first-plugin
creates
/my-first-plugin:hello
).
Create a skill directory in your plugin folder:
mkdir
-p
my-first-plugin/skills/hello
Then create
my-first-plugin/skills/hello/SKILL.md
with this content:
my-first-plugin/skills/hello/SKILL.md
---
description
:
Greet the user with a friendly message
disable-model-invocation
:
true
---
Greet the user warmly and ask how you can help them today.
4
Test your plugin
Run Claude Code with the
--plugin-dir
flag to load your plugin:
claude
--plugin-dir
./my-first-plugin
Once Claude Code starts, try your new skill:
/my-first-plugin:hello
You’ll see Claude respond with a greeting. Run
/help
and open the
Custom commands
tab to see your skill listed under the plugin namespace.
Why namespacing?
Plugin skills are always namespaced (like
/my-first-plugin:hello
) to prevent conflicts when multiple plugins have skills with the same name.
To change the namespace prefix, update the
name
field in
plugin.json
.
5
Add skill arguments
Make your skill dynamic by accepting user input. The
$ARGUMENTS
placeholder captures any text the user provides after the skill name.
Update your
SKILL.md
file:
my-first-plugin/skills/hello/SKILL.md
---
description
:
Greet the user with a personalized message
---
# Hello Skill
Greet the user named "$ARGUMENTS" warmly and ask how you can help them today. Make the greeting personal and encouraging.
Run
/reload-plugins
to pick up the changes. Then try the skill with your name:
/my-first-plugin:hello
Alex
Claude will greet you by name. For more on passing arguments to skills, see
Skills
.
The
--plugin-dir
flag is useful for development and testing. When you’re ready to share your plugin with others, see
Create and distribute a plugin marketplace
.
​
Develop a plugin in your skills directory
Instead of passing
--plugin-dir
on every launch, you can keep a plugin in your skills directory and have Claude Code load it automatically.
claude plugin init
scaffolds one:
claude
plugin
init
my-tool
This creates
~/.claude/skills/my-tool/
with a
.claude-plugin/plugin.json
manifest and a starter
SKILL.md
. On the next session it loads as
my-tool@skills-dir
with no marketplace or install step.
For the auto-load rules, personal vs. project scope, the workspace-trust requirement, and how to update or remove one, see
Skills-directory plugins
.
​
Plugin structure overview
You’ve created a plugin with a skill, but plugins can include much more: custom agents, hooks, MCP servers, LSP servers, and background monitors.
Common mistake
: Don’t put
commands/
,
agents/
,
skills/
, or
hooks/
inside the
.claude-plugin/
directory. Only
plugin.json
goes inside
.claude-plugin/
. All other directories must be at the plugin root level.
The plugin root is the individual plugin’s own directory: the one you pass to
--plugin-dir
or that contains
.claude-plugin/plugin.json
. It is never
~/.claude/
. For example, Claude Code doesn’t read a
.mcp.json
placed at
~/.claude/.mcp.json
.
Directory
Location
Purpose
.claude-plugin/
Plugin root
Contains
plugin.json
manifest (optional if components use default locations)
skills/
Plugin root
Skills as
<name>/SKILL.md
directories
commands/
Plugin root
Skills as flat Markdown files. Use
skills/
for new plugins
agents/
Plugin root
Custom agent definitions
hooks/
Plugin root
Event handlers in
hooks.json
.mcp.json
Plugin root
MCP server configurations
.lsp.json
Plugin root
LSP server configurations for code intelligence
monitors/
Plugin root
Background monitor configurations in
monitors.json
bin/
Plugin root
Executables added to the Bash tool’s
PATH
while the plugin is enabled. You can’t include this directory in a plugin you
distribute through claude.ai organization settings
settings.json
Plugin root
Default
settings
applied when the plugin is enabled
A plugin that ships exactly one skill can place
SKILL.md
directly at the plugin root instead of creating a
skills/
directory. Claude Code loads it as a single skill and uses the frontmatter
name
field for the invocation name. Use the
skills/
layout for plugins that may grow to more than one skill.
​
Develop more complex plugins
Once you’re comfortable with basic plugins, you can create more sophisticated extensions.
​
Add Skills to your plugin
Plugins can include
Agent Skills
to extend Claude’s capabilities. Skills are model-invoked: Claude automatically uses them based on the task context.
Add a
skills/
directory at your plugin root with Skill folders containing
SKILL.md
files:
my-plugin/
├── .claude-plugin/
│   └── plugin.json
└── skills/
└── code-review/
└── SKILL.md
Each
SKILL.md
contains YAML frontmatter and instructions. Include a
description
so Claude knows when to use the skill:
---
description
:
Reviews code for best practices and potential issues. Use when reviewing code, checking PRs, or analyzing code quality.
---
When reviewing code, check for
:
1. Code organization and structure
2. Error handling
3. Security concerns
4. Test coverage
After you install the plugin, check the install summary: if it reports
Run /reload-plugins to activate.
, run that command to load the Skills. For complete Skill authoring guidance including progressive disclosure and tool restrictions, see
Agent Skills
.
​
Add LSP servers to your plugin
For common languages like TypeScript, Python, and Rust, install the pre-built LSP plugins from the official marketplace. Create custom LSP plugins only when you need support for languages not already covered.
LSP (Language Server Protocol) plugins give Claude real-time code intelligence. If you need to support a language that doesn’t have an official LSP plugin, you can create your own by adding an
.lsp.json
file to your plugin:
.lsp.json
{
"go"
: {
"command"
:
"gopls"
,
"args"
: [
"serve"
],
"extensionToLanguage"
: {
".go"
:
"go"
}
}
}
Users installing your plugin must have the language server binary installed on their machine.
To confirm the server starts, launch Claude Code with the plugin enabled and check the
/plugin
Errors tab: a language server that fails to start appears there, for example with
Executable not found in $PATH
when the binary isn’t installed. An entry with an invalid configuration is skipped instead; run
claude --debug
to see why.
For complete LSP configuration options, see
LSP servers
.
​
Add background monitors to your plugin
Background monitors let your plugin watch logs, files, or external status in the background and notify Claude as events arrive. Claude Code starts each monitor automatically when the plugin is active, so you don’t need to instruct Claude to start the watch.
Add a
monitors/monitors.json
file at the plugin root with an array of monitor entries:
monitors/monitors.json
[
{
"name"
:
"error-log"
,
"command"
:
"tail -F ./logs/error.log"
,
"description"
:
"Application error log"
}
]
Each stdout line from
command
is delivered to Claude as a notification during the session. For the full schema, including the
when
trigger and variable substitution, see
Monitors
.
​
Ship default settings with your plugin
Plugins can include a
settings.json
file at the plugin root to apply default configuration when the plugin is enabled. Currently, only the
agent
and
subagentStatusLine
keys are supported.
Setting
agent
activates one of the plugin’s
custom agents
as the main thread, applying its system prompt, tool restrictions, and model. This lets a plugin change how Claude Code behaves by default when enabled.
settings.json
{
"agent"
:
"security-reviewer"
}
This example activates the
security-reviewer
agent defined in the plugin’s
agents/
directory. Settings from
settings.json
take priority over
settings
declared in
plugin.json
. Unknown keys are silently ignored.
​
Organize complex plugins
For plugins with many components, organize your directory structure by functionality. For complete directory layouts and organization patterns, see
Plugin directory structure
.
​
Test your plugins locally
Use the
--plugin-dir
flag to test plugins during development. This loads your plugin directly without requiring installation.
claude
--plugin-dir
./my-plugin
The flag also accepts a
.zip
archive of the plugin directory.
claude
--plugin-dir
./my-plugin.zip
When a
--plugin-dir
plugin has the same name as an installed marketplace plugin, the local copy takes precedence for that session. This lets you test changes to a plugin you already have installed without uninstalling it first. The exception is plugins that managed settings force-enable or force-disable:
--plugin-dir
cannot override those.
As you make changes to your plugin, run
/reload-plugins
to pick up the updates without restarting. This reloads plugins, skills, agents, hooks, plugin MCP servers, and plugin LSP servers. Test your plugin components:
Try your skills with
/plugin-name:skill-name
Check that agents appear in
/context
under Custom Agents, or @-mention one by its scoped name
Trigger the event each hook matches, such as asking Claude to edit a file for a
PostToolUse
hook, and confirm its effect. Claude Code records which hooks matched, their exit codes, and their output in the
debug log
You can load multiple plugins at once by specifying the flag multiple times:
claude
--plugin-dir
./plugin-one
--plugin-dir
./plugin-two
To test a plugin together with a plugin it depends on, see
Test a plugin and its dependency locally
.
To test a plugin that is already packaged as a
.zip
archive and hosted at a URL, such as a CI build artifact, use
--plugin-url
instead. Claude Code fetches the archive at startup and loads it for that session only. If Claude Code can’t fetch the archive, or the archive is invalid, it starts without the plugin and records a plugin load error that you can review in the
/plugin
manager’s
Errors
tab. The same
trust considerations
apply as for any plugin source: only point this flag at archives you control or trust.
To load multiple plugins, repeat the flag for each URL:
claude
--plugin-url
https://example.com/my-plugin.zip
--plugin-url
https://example.com/other.zip
Or pass space-separated URLs as one quoted argument:
claude
--plugin-url
"https://example.com/my-plugin.zip https://example.com/other.zip"
​
Debug plugin issues
If your plugin isn’t working as expected:
Check the structure
: Ensure your directories are at the plugin root, not inside
.claude-plugin/
Test components individually
: Check each skill, agent, and hook separately
Use validation and debugging tools
: See
Debugging and development tools
for CLI commands and troubleshooting techniques
​
Share your plugins
When your plugin is ready to share:
Add documentation
: Include a
README.md
with installation and usage instructions
Choose a versioning strategy
: Decide whether to set an explicit
version
or rely on the fallback described in
version management
.
Create or use a marketplace
: Distribute through
plugin marketplaces
for installation
Test with others
: Have team members test the plugin before wider distribution
Once your plugin is in a marketplace, others can install it using the instructions in
Discover and install plugins
. To keep a plugin internal to your team, host the marketplace in a
private repository
.
​
Submit your plugin to the community marketplace
Anthropic maintains two public marketplaces for Claude Code plugins:
claude-plugins-official
: a curated set of plugins maintained by Anthropic. Claude Code registers it automatically the first time you start Claude Code interactively. If you run Claude Code non-interactively before that first interactive launch, or a
marketplace policy
blocked an earlier attempt, register it yourself with
claude plugin marketplace add anthropics/claude-plugins-official
.
claude-community
: the public community marketplace where third-party submissions land after review. Users add it with
/plugin marketplace add anthropics/claude-plugins-community
and install from it as
@claude-community
.
To submit your plugin for community-marketplace review, use one of the in-app forms:
claude.ai
:
claude.ai/admin-settings/directory/submissions/plugins/new
Console
:
platform.claude.com/plugins/submit
The claude.ai form requires a Team or Enterprise organization and directory management access; organization Owners have this access by default. Individual authors who aren’t part of a Team or Enterprise organization can use the Console form instead.
Run
claude plugin validate ./your-plugin
locally before you submit, replacing
./your-plugin
with the path to your plugin directory. The review pipeline runs the same check on every submission, along with automated safety screening. When validation passes, Claude Code prints
✔ Validation passed
, or
✔ Validation passed with warnings
if there are warnings. Warnings don’t fail validation; add
--strict
to treat them as errors.
Approved plugins are pinned to a specific commit SHA in the
anthropics/claude-plugins-community
catalog, and CI bumps the pin automatically as you push new commits to your repository. The public catalog syncs nightly from the review pipeline, so there can be a delay between approval and your plugin appearing in
marketplace.json
. To check whether your plugin is installable yet, search for its name in the
community catalog
.
The official marketplace,
claude-plugins-official
, is curated separately. Anthropic decides which plugins to include at its discretion. There is no application process, and the submission form does not add plugins to the official marketplace.
If Anthropic lists your plugin in the official marketplace, your CLI can prompt Claude Code users to install it. See
Recommend your plugin from your CLI
.
​
Convert existing configurations to plugins
If you already have skills or hooks in your
.claude/
directory, you can convert them into a plugin for easier sharing and distribution.
​
Migration steps
1
Create the plugin structure
Create a new plugin directory in your project root, alongside the existing
.claude/
folder, so the relative
cp
paths in the next step resolve:
mkdir
-p
my-plugin/.claude-plugin
Create the manifest file at
my-plugin/.claude-plugin/plugin.json
:
my-plugin/.claude-plugin/plugin.json
{
"name"
:
"my-plugin"
,
"description"
:
"Migrated from standalone configuration"
,
"version"
:
"1.0.0"
}
2
Copy your existing files
Copy each configuration directory you have to the plugin root. You might not have all three: if a directory doesn’t exist,
cp
prints
No such file or directory
and copies nothing, so skip that command or ignore the error.
cp
-r
.claude/commands
my-plugin/
cp
-r
.claude/agents
my-plugin/
cp
-r
.claude/skills
my-plugin/
Your plugin now contains copies of the directories you had under
.claude/
. Run
ls my-plugin
to confirm: you should see each directory you copied.
3
Migrate hooks
If you have hooks in your settings, create a hooks directory:
mkdir
my-plugin/hooks
Create
my-plugin/hooks/hooks.json
with your hooks configuration. Copy the
hooks
object from your
.claude/settings.json
or
settings.local.json
, since the format is the same. The command receives hook input as JSON on stdin, so use
jq
to extract the file path:
my-plugin/hooks/hooks.json
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [{
"type"
:
"command"
,
"command"
:
"jq -r '.tool_input.file_path' | xargs npm run lint:fix"
}]
}
]
}
}
4
Test your migrated plugin
Load your plugin to verify everything works:
claude
--plugin-dir
./my-plugin
Test each component: run your commands, check that agents appear in
/context
, and trigger the event each hook matches to confirm its effect. Claude Code records which hooks matched and how they exited in the
debug log
.
​
What changes when migrating
Standalone (
.claude/
)
Plugin
Only available in one project
Can be shared via marketplaces
Files in
.claude/commands/
Files in
plugin-name/commands/
Hooks in
settings.json
Hooks in
hooks/hooks.json
Must manually copy to share
Install with
/plugin install
After migrating, remove the original files from
.claude/
to avoid duplicates. Project and user
.claude/agents/
definitions override same-named plugin agents, so the plugin version only takes effect once the originals are removed. Plugin skills are namespaced as
/plugin-name:skill-name
, so the original
/skill-name
and the plugin copy both remain available rather than one overriding the other.
​
Next steps
Now that you understand Claude Code’s plugin system, here are suggested paths for different goals:
​
For plugin users
Discover and install plugins
: browse marketplaces and install plugins
Configure team marketplaces
: set up repository-level plugins for your team
​
For plugin developers
Create and distribute a marketplace
: package and share your plugins
Plugins reference
: complete technical specifications
Dive deeper into specific plugin components:
Skills
: skill development details
Subagents
: agent configuration and capabilities
Hooks
: event handling and automation
MCP
: external tool integration
Was this page helpful?
Yes
No
Assistant
Responses are generated using AI and may contain mistakes.

## Source (plugins-reference): https://docs.claude.com/en/docs/claude-code/plugins-reference

Plugins reference - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Looking to install plugins? See
Discover and install plugins
. For creating plugins, see
Plugins
. For distributing plugins, see
Plugin marketplaces
.
A
plugin
is a self-contained directory of components that extends Claude Code with custom functionality. Plugin components include skills, agents, hooks, MCP servers, LSP servers, and monitors.
​
Plugin components reference
​
Skills
Plugins add skills to Claude Code, creating
/name
shortcuts that you or Claude can invoke.
Location
:
skills/
or
commands/
directory in plugin root, or a single
SKILL.md
file at the plugin root
File format
: Skills are directories with
SKILL.md
; commands are simple markdown files
Skill structure
:
skills/
├── pdf-processor/
│   ├── SKILL.md
│   ├── reference.md (optional)
│   └── scripts/ (optional)
└── code-reviewer/
└── SKILL.md
Skills and commands are automatically discovered when the plugin is installed.
If a plugin has no
skills/
directory and no
skills
manifest field, a
SKILL.md
at the plugin root is loaded as a single skill. Set the frontmatter
name
field to control the skill’s invocation name. Without it, Claude Code falls back to the install directory name, which for marketplace-installed plugins is a version string that changes on every update. For plugins that ship more than one skill, use the
skills/
directory layout shown above.
In plugin skills and commands, Boolean frontmatter fields such as
disable-model-invocation
accept
yes
,
no
,
on
,
off
,
1
, and
0
in any letter case, in addition to
true
and
false
. Before v2.1.218, Claude Code recognized only
true
and
false
.
For complete details, see
Skills
.
​
Agents
Plugins can provide specialized subagents for specific tasks that Claude can invoke automatically when appropriate.
Location
:
agents/
directory in plugin root
File format
: Markdown files describing agent capabilities
Agent structure
:
---
name
:
agent-name
description
:
What this agent specializes in and when Claude should invoke it
model
:
sonnet
effort
:
medium
maxTurns
:
20
disallowedTools
:
Write, Edit
---
Detailed system prompt for the agent describing its role, expertise, and behavior.
Plugin agents support
name
,
description
,
model
,
effort
,
maxTurns
,
tools
,
disallowedTools
,
skills
,
memory
,
background
, and
isolation
frontmatter fields. The only valid
isolation
value is
"worktree"
. For security reasons,
hooks
,
mcpServers
, and
permissionMode
are not supported for plugin-shipped agents.
Claude Code loads a plugin agent even when its frontmatter has no
name
or doesn’t parse:
No
name
: Claude Code names the agent after the file, so
agents/reviewer.md
in a plugin named
my-plugin
loads as
my-plugin:reviewer
Frontmatter that doesn’t parse: Claude Code names the agent after the file, uses
Agent from my-plugin plugin
as its description, and ignores every field in the file
By contrast, Claude Code skips a project, user, or managed agent file whose frontmatter has no
name
or doesn’t parse.
To find files in a plugin’s default
agents/
directory whose frontmatter doesn’t parse, run
claude plugin validate
. The path you pass depends on whether the plugin has a manifest, and both examples use
./my-plugin
as the plugin directory:
A plugin with a manifest:
claude plugin validate ./my-plugin
A plugin without a manifest:
claude plugin validate ./my-plugin/agents
. Requires Claude Code v2.1.233 or later.
Agents appear in the
@-mention typeahead
under their scoped name, such as
my-plugin:code-reviewer
, once the plugin is enabled.
For complete details, see
Subagents
.
​
Hooks
Plugins can provide event handlers that respond to Claude Code events automatically.
Location
:
hooks/hooks.json
in plugin root, or inline in plugin.json
Format
: JSON configuration with event matchers and actions
Hook configuration
:
{
"hooks"
: {
"PostToolUse"
: [
{
"matcher"
:
"Write|Edit"
,
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/format-code.sh"
}
]
}
]
}
}
Plugin hooks respond to the same lifecycle events as
user-defined hooks
:
Event
When it fires
SessionStart
When a session begins or resumes
Setup
When you start Claude Code with
--init-only
, or with
--init
or
--maintenance
in
-p
mode. For one-time preparation in CI or scripts
UserPromptSubmit
When you submit a prompt, before Claude processes it
UserPromptExpansion
When a user-typed command expands into a prompt, before it reaches Claude. Can block the expansion
PreToolUse
Before a tool call executes. Can block it
PermissionRequest
When a tool call needs a permission decision
PermissionDenied
When auto mode denies a tool call, including denials without a classifier verdict. Use JSON
hookSpecificOutput.retry: true
to tell the model it may retry the denied tool call. Claude Code ignores
retry
when the classifier produced no verdict
PostToolUse
After a tool call succeeds
PostToolUseFailure
After a tool call fails
PostToolBatch
After a full batch of parallel tool calls resolves, before the next model call
Notification
When Claude Code sends a notification
MessageDisplay
While assistant message text is displayed
SubagentStart
When a subagent is spawned
SubagentStop
When a subagent finishes
TaskCreated
When a task is being created via
TaskCreate
TaskCompleted
When a task is being marked as completed
Stop
When Claude finishes responding
StopFailure
When the turn ends due to an API error
TeammateIdle
When an
agent team
teammate is about to go idle
InstructionsLoaded
When a CLAUDE.md or
.claude/rules/*.md
file is loaded into context. Fires at session start and when files are lazily loaded during a session
ConfigChange
When a configuration file changes during a session
CwdChanged
When the working directory changes, for example when Claude executes a
cd
command. Useful for reactive environment management with tools like direnv
DirectoryAdded
When a working directory is added mid-session via
/add-dir
or the SDK
register_repo_root
control request
FileChanged
When a watched file changes on disk. The
matcher
field specifies which filenames to watch
WorktreeCreate
When a worktree is being created via
--worktree
,
isolation: "worktree"
, or for a background session. Replaces default git behavior
WorktreeRemove
When a worktree is being removed at session exit, when a subagent finishes, or when you delete a background session
PreCompact
Before context compaction
PostCompact
After context compaction completes
PreModelSwitch
Before Claude Code applies a model switch that you or a client requested. Can block the switch
PostModelSwitch
After the session’s model changes, including changes Claude Code makes on its own, such as restoring the model when you resume a session
Elicitation
When an MCP server requests user input during a tool call
ElicitationResult
After a user responds to an MCP elicitation, before the response is sent back to the server
SessionEnd
When a session terminates
Hook types
:
command
: execute shell commands or scripts
http
: send the event JSON as a POST request to a URL
mcp_tool
: call a tool on a configured
MCP server
prompt
: evaluate a prompt with an LLM (uses
$ARGUMENTS
placeholder for context)
agent
: run an agentic verifier with tools for complex verification tasks
Hooks that target the plugin’s own
bundled MCP server
must use its scoped names. Tool matchers and
if
fields take the scoped tool name
mcp__plugin_<plugin-name>_<server-name>__<tool>
, and an
mcp_tool
hook’s
server
field takes
plugin:<plugin-name>:<server-name>
. A matcher written against the bare server key never fires. See
Match MCP tools
and
Plugin-provided MCP servers
.
​
MCP servers
Plugins can bundle Model Context Protocol (MCP) servers to connect Claude Code with external tools and services.
Location
:
.mcp.json
in plugin root, or inline in plugin.json
Format
: Standard MCP server configuration
MCP server configuration
:
{
"mcpServers"
: {
"plugin-database"
: {
"command"
:
"${CLAUDE_PLUGIN_ROOT}/servers/db-server"
,
"args"
: [
"--config"
,
"${CLAUDE_PLUGIN_ROOT}/config.json"
],
"env"
: {
"DB_PATH"
:
"${CLAUDE_PLUGIN_ROOT}/data"
}
},
"plugin-api-client"
: {
"command"
:
"npx"
,
"args"
: [
"@company/mcp-server"
,
"--plugin-mode"
]
}
}
}
Integration behavior
:
Plugin MCP servers start automatically when the plugin is enabled
Servers appear as standard MCP tools in Claude’s toolkit
Plugin servers can be configured independently of user MCP servers
If you run
/reload-plugins
mid-session, Claude Code keeps the live connections of servers whose configuration is unchanged
​
LSP servers
Looking to use LSP plugins? Install them from the official marketplace: search for “lsp” in the
/plugin
Discover tab. This section documents how to create LSP plugins for languages not covered by the official marketplace.
Plugins can provide
Language Server Protocol
(LSP) servers to give Claude
real-time code intelligence
while working on your codebase.
Location
:
.lsp.json
in plugin root, or inline in
plugin.json
Format
: JSON configuration mapping language server names to their configurations
.lsp.json
file format
:
{
"go"
: {
"command"
:
"gopls"
,
"args"
: [
"serve"
],
"extensionToLanguage"
: {
".go"
:
"go"
}
}
}
Inline in
plugin.json
:
{
"name"
:
"my-plugin"
,
"lspServers"
: {
"go"
: {
"command"
:
"gopls"
,
"args"
: [
"serve"
],
"extensionToLanguage"
: {
".go"
:
"go"
}
}
}
}
Required fields:
Field
Description
command
The LSP binary to execute (must be in PATH)
extensionToLanguage
Maps file extensions to language identifiers
Optional fields:
Field
Description
args
Command-line arguments for the LSP server
transport
Communication transport:
stdio
(default) or
socket
. Claude Code accepts
socket
but runs every server over stdio, so the stdout protocol rules apply to all servers
env
Environment variables to set when starting the server
initializationOptions
Options passed to the server during initialization
settings
Settings passed via
workspace/didChangeConfiguration
workspaceFolder
Workspace folder path for the server
startupTimeout
Max time to wait for server startup (milliseconds)
shutdownTimeout
Max time to wait for graceful shutdown (milliseconds). When the timeout elapses, Claude Code terminates the server process. When unset, no timeout applies
restartOnCrash
Whether to restart the server after it crashes. Defaults to
true
. Set to
false
to leave a crashed server stopped instead of restarting it
maxRestarts
Maximum number of restart attempts before giving up
diagnostics
Whether to push diagnostics into Claude’s context after edits (default
true
). Set to
false
to keep code navigation but suppress automatic diagnostic injection.
restartOnCrash
and
shutdownTimeout
require Claude Code v2.1.205 or later. Before v2.1.205, the config schema accepted both options but setting either one caused Claude Code to skip that LSP server entirely at startup, with the reason visible only in
claude --debug
output.
Multiple servers for the same extension
: when more than one enabled LSP server declares the same file extension in
extensionToLanguage
, whether the servers come from one plugin or from different plugins, the first server registered handles files with that extension and the others never start. The
/plugin
interface shows a warning naming the plugin whose server is active.
Servers that fail to initialize
: Claude Code skips a server whose configuration is invalid, for example one missing
command
or
extensionToLanguage
, and the other configured servers still start. Run
claude --debug
to see why a server was skipped.
A skipped server doesn’t claim its file extensions, so another valid server that declares the same extension, from the same or a different plugin, still handles those files.
Send log output to stderr, not stdout
: Claude Code reads a server’s stdout as protocol messages only, and accepts message headers up to 64 KiB and a message body up to 32 MiB. Claude Code disconnects a server that exceeds either limit or writes non-protocol output to stdout, and counts the disconnect as a crash for
restartOnCrash
and
maxRestarts
. When you run with
--debug
, Claude Code writes an error naming the cause to the debug log.
You must install the language server binary separately.
LSP plugins configure how Claude Code connects to a language server, but they don’t include the server itself. If you see
Executable not found in $PATH
in the
/plugin
Errors tab, install the required binary for your language.
Available LSP plugins:
Plugin
Language server
Install command
pyright-lsp
Pyright (Python)
pip install pyright
or
npm install -g pyright
typescript-lsp
TypeScript Language Server
npm install -g typescript-language-server typescript
rust-analyzer-lsp
rust-analyzer
See rust-analyzer installation
Install the language server first, then install the plugin from the marketplace.
​
Monitors
Plugins can declare background monitors that Claude Code starts automatically when the plugin is active. Each monitor runs a shell command for the lifetime of the session and delivers every stdout line to Claude as a notification, so Claude can react to log entries, status changes, or polled events without being asked to start the watch itself.
Plugin monitors use the same mechanism as the
Monitor tool
and share its availability constraints. They run only in interactive CLI sessions, run unsandboxed at the same trust level as
hooks
, and are skipped on hosts where the Monitor tool is unavailable.
Location
:
monitors/monitors.json
in the plugin root, or inline in
plugin.json
Format
: JSON array of monitor entries
The following
monitors/monitors.json
watches a deployment status endpoint and a local error log:
[
{
"name"
:
"deploy-status"
,
"command"
:
"
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/poll-deploy.sh"
,
"description"
:
"Deployment status changes"
},
{
"name"
:
"error-log"
,
"command"
:
"tail -F ./logs/error.log"
,
"description"
:
"Application error log"
,
"when"
:
"on-skill-invoke:debug"
}
]
To declare monitors inline, set
experimental.monitors
in
plugin.json
to the same array. To load from a non-default path, set
experimental.monitors
to a relative path string such as
"./config/monitors.json"
. Monitors are an
experimental component
.
Required fields:
Field
Description
name
Identifier unique within the plugin. Prevents duplicate processes when the plugin reloads or a skill is invoked again
command
Shell command run as a persistent background process in the session working directory
description
Short summary of what is being watched. Shown in the task panel and in notification summaries
Optional fields:
Field
Description
when
Controls when the monitor starts.
"always"
starts it at session start and on plugin reload, and is the default.
"on-skill-invoke:<skill-name>"
starts it the first time the named skill in this plugin is dispatched
The
command
value supports the
path substitutions
${CLAUDE_PLUGIN_ROOT}
,
${CLAUDE_PLUGIN_DATA}
, and
${CLAUDE_PROJECT_DIR}
, plus any
${ENV_VAR}
from the environment. Prefix the command with
cd "${CLAUDE_PLUGIN_ROOT}" &&
if the script needs to run from the plugin’s own directory.
A monitor
command
can’t reference
${user_config.*}
values. The command runs through a shell, so Claude Code rejects the monitor with an
error
instead of substituting the value. Monitor processes don’t receive
CLAUDE_PLUGIN_OPTION_<KEY>
environment variables, so have the monitor script read the value from a config file it owns.
If you disable a plugin mid-session, Claude Code doesn’t stop monitors that are already running; they stop when the session ends.
​
Themes
Plugins can ship color themes that appear in
/theme
alongside the built-in presets and the user’s local themes. A theme is a JSON file in
themes/
with a
base
preset and a sparse
overrides
map of color tokens. Themes are an
experimental component
.
{
"name"
:
"Dracula"
,
"base"
:
"dark"
,
"overrides"
: {
"claude"
:
"#bd93f9"
,
"error"
:
"#ff5555"
,
"success"
:
"#50fa7b"
}
}
When a user selects a plugin theme, Claude Code saves
custom:<plugin-name>:<slug>
in their config. Plugin themes are read-only: when a user presses
Ctrl+E
on one in
/theme
, Claude Code copies it into
~/.claude/themes/
so they can edit the copy.
​
Plugin installation scopes
When you install a plugin, you choose a
scope
that determines where the plugin is available and who else can use it:
Scope
Settings file
Use case
user
~/.claude/settings.json
Personal plugins available across all projects (default)
project
.claude/settings.json
Team plugins shared via version control
local
.claude/settings.local.json
Project-specific plugins, gitignored when Claude Code saves a setting to it
managed
Managed settings
Managed plugins (read-only, update only)
Plugins use the same scope system as other Claude Code configurations. For installation instructions and scope flags, see
Install plugins
. For a complete explanation of scopes, see
Configuration scopes
.
​
Skills-directory plugins
Any folder under a skills directory that contains a
.claude-plugin/plugin.json
manifest is loaded as a plugin named
<name>@skills-dir
on the next session, with no marketplace and no install step. Scaffold one with
plugin init
. Unlike a copied marketplace install, the plugin is discovered in place rather than copied into the plugin cache.
A skills directory tree supports three distinct things:
What you have
What it is
<skills-dir>/foo/SKILL.md
with no manifest
A plain
skill
named
foo
<skills-dir>/foo/.claude-plugin/plugin.json
A plugin
foo@skills-dir
, which can bundle its own skills, agents, hooks, and more
<plugin>/skills/bar/SKILL.md
A skill
bar
packaged inside a plugin
​
Choose where the plugin loads from
Skills directory
Scope
Loads
~/.claude/skills/
personal
In every project, since the location is yours alone
<cwd>/.claude/skills/
project
Only after you accept the workspace
trust dialog
for that folder
A project-scope plugin is checked into the repository and reaches every collaborator who clones it. Because that content comes from the repository rather than from you, it loads only after the same trust gate that governs project allow rules in
.claude/settings.json
, so trusting a parent folder or running with
-p
isn’t enough, and components that run code are restricted further:
MCP servers it declares go through the
same per-server approval
as a project
.mcp.json
LSP servers start only after you trust the workspace
Background monitors
do not load
Personal-scope plugins have none of these restrictions.
Project-scope
@skills-dir
plugins load only from the
.claude/skills/
of the session’s
primary working directory
. They don’t
walk up to the repository root
the way plain skills and commands do, so launching from a subdirectory misses a plugin that lives at the repo root. Launch from the repository root, or
move the session there with
/cd
on v2.1.246 or later.
​
Edit, reload, and disable a skills-directory plugin
Changes you make to a skill’s
SKILL.md
take effect immediately in the current session. Changes to the plugin’s other components, such as
hooks/
,
.mcp.json
,
agents/
, and
output-styles/
, do not. Run
/reload-plugins
or restart Claude Code to pick those up. See
Live change detection
.
To stop loading a skills-directory plugin, delete its folder or disable it by name. There is no
uninstall
step because nothing was installed from a marketplace.
claude
plugin
disable
my-tool@skills-dir
​
Plugins synced from claude.ai
In
Cowork
and
cloud sessions
, Claude Code downloads the plugins enabled for your claude.ai account into
~/.claude/plugins/synced/
in the session’s own environment and loads each one as
<name>@synced
, with no marketplace and no install record. Claude Code doesn’t load them in sessions you start in your own terminal. Inside that Cowork or cloud environment,
claude plugin list
shows the downloaded copies under a
Synced from claude.ai
heading. Before v2.1.239, Claude Code loaded these plugins as
<name>@inline
, the identity that
--plugin-dir
plugins use.
Manage a synced plugin by the
<name>@synced
ID that
claude plugin list
prints:
Turn one off
: in the synced session, run
claude plugin disable <name>@synced
, or ask Claude to run it. Claude Code saves the choice as
"<name>@synced": false
in that environment’s user-level
enabledPlugins
. To turn the plugin back on, run
claude plugin enable <name>@synced
in the same session. To keep a plugin out of every synced session,
turn it off for your claude.ai account
. To keep it out of one project’s synced sessions in every environment, set
"<name>@synced": false
under
enabledPlugins
in that project’s committed
.claude/settings.json
.
Manage the plugin itself on claude.ai
:
claude plugin install
,
update
, and
uninstall
don’t apply to a synced plugin. To remove one, turn the plugin off for your claude.ai account; the next synced session starts without it.
When an enabled plugin from any other source, such as a marketplace install, a
skills-directory plugin
, or a
--plugin-dir
plugin, matches a synced plugin’s name, Claude Code loads that plugin and reports the synced copy as not loaded. To use the claude.ai copy instead, disable your own copy. Before v2.1.239, Claude Code loaded the synced copy instead of a same-named marketplace install.
​
Plugin manifest schema
The
.claude-plugin/plugin.json
file defines your plugin’s metadata and configuration.
The manifest is optional. If omitted, Claude Code auto-discovers components in
default locations
and derives the plugin name from the directory name. Use a manifest when you need to provide metadata or custom component paths.
​
Complete schema
{
"name"
:
"plugin-name"
,
"displayName"
:
"Plugin Name"
,
"version"
:
"1.2.0"
,
"description"
:
"Brief plugin description"
,
"author"
: {
"name"
:
"Author Name"
,
"email"
:
"author@example.com"
,
"url"
:
"https://github.com/author"
},
"homepage"
:
"https://docs.example.com/plugin"
,
"repository"
:
"https://github.com/author/plugin"
,
"license"
:
"MIT"
,
"keywords"
: [
"keyword1"
,
"keyword2"
],
"metadata"
: {
"catalogId"
:
"cat-123"
,
"tier"
:
"pro"
},
"skills"
:
"./custom/skills/"
,
"commands"
: [
"./custom/commands/special.md"
],
"agents"
: [
"./custom/agents/reviewer.md"
],
"hooks"
:
"./config/hooks.json"
,
"mcpServers"
:
"./mcp-config.json"
,
"outputStyles"
:
"./styles/"
,
"lspServers"
:
"./.lsp.json"
,
"experimental"
: {
"themes"
:
"./themes/"
,
"monitors"
:
"./monitors.json"
},
"dependencies"
: [
"helper-lib"
,
{
"name"
:
"secrets-vault"
,
"version"
:
"~2.1.0"
}
]
}
​
Required fields
If you include a manifest,
name
is the only required field.
Field
Type
Description
Example
name
string
Unique identifier in kebab-case, with no spaces, control characters, or bidirectional-formatting characters. When a
marketplace entry
lists the plugin under a different name, the marketplace entry name is what
enabledPlugins
keys and
/plugin
use
"deployment-tools"
This name is used for namespacing components. For example, in the UI, the
agent
agent-creator
for the plugin with name
plugin-dev
will appear as
plugin-dev:agent-creator
.
​
Unrecognized fields
Claude Code ignores top-level fields it does not recognize. You can keep
metadata from another ecosystem in
plugin.json
and the plugin still loads.
This makes it practical to maintain one manifest that doubles as a VS Code or
Cursor extension manifest, an npm
package.json
, or an MCPB/DXT bundle
manifest.
claude plugin validate
reports unrecognized fields as warnings, not errors.
If a field is one or two characters off from a recognized one, the warning
suggests the likely intended name. A plugin with only unrecognized-field
warnings still passes validation and loads at runtime.
How Claude Code handles a recognized field whose value has the wrong type depends on the field:
Most fields
: the plugin fails to load. For example, a
keywords
value that is a string instead of an array is a load error, and
claude plugin validate
reports it as one.
experimental
and
metadata
: Claude Code ignores a non-object value, and
claude plugin validate
reports a warning.
Pass
--strict
to treat warnings as errors. Use it in CI to catch a misspelled
field name or a field left over from another tool’s manifest before publishing,
even though the plugin would load at runtime.
claude
plugin
validate
./my-plugin
--strict
​
Metadata fields
Field
Type
Description
Example
$schema
string
JSON Schema URL for editor autocomplete and validation. Claude Code ignores this field at load time.
"https://json.schemastore.org/claude-code-plugin-manifest.json"
displayName
string
Human-readable name shown in the
/plugin
picker and other UI surfaces. Falls back to
name
when omitted. Unlike
name
, may contain spaces and any casing. Not used for namespacing or lookup.
"Deployment Tools"
version
string
Optional. Semantic version. Setting this pins the plugin to that version string, so users only receive updates when you bump it, except for a
command
source
; see
Version management
. If also set in the marketplace entry,
plugin.json
wins. If omitted, the version comes from the next source in
Version management
.
"2.1.0"
description
string
Brief explanation of plugin purpose
"Deployment automation tools"
author
object
Author information
{"name": "Dev Team", "email": "dev@company.com"}
homepage
string
Documentation URL
"https://docs.example.com"
repository
string
Source code URL
"https://github.com/user/plugin"
license
string
License identifier
"MIT"
,
"Apache-2.0"
keywords
array
Discovery tags
["deployment", "ci-cd"]
metadata
object
Free-form object for your own data, such as entitlement or catalog fields. Claude Code doesn’t read it, so the values never affect plugin behavior. Claude Code ignores a non-object value, and
claude plugin validate
reports it as a warning. Before v2.1.222, Claude Code treated the key as an
unrecognized field
.
{"catalogId": "cat-123"}
defaultEnabled
boolean
Whether the plugin starts in an enabled state when the user has not set one. Defaults to
true
. See
Default enablement
.
false
​
Default enablement
Set
defaultEnabled: false
in
plugin.json
to ship a plugin that installs disabled. The user turns it on with
claude plugin enable <plugin>
or the
/plugin
interface. Use this for plugins that add cost or scope a user should opt into, such as one that connects to an external service.
defaultEnabled
is the fallback when nothing else has decided the plugin’s state. Two things take precedence over it:
The user’s setting
: an entry for the plugin in
enabledPlugins
at any settings scope. Once written, it persists across plugin updates and reinstalls, so changing
defaultEnabled
in a later release does not flip an existing user.
A dependency requirement
: when a plugin is required by another one that is active, Claude Code writes
true
for it at install or enable time. That gives it an explicit setting, so its own default no longer applies. See
Enable or disable a plugin with dependencies
.
The same field can appear in a plugin’s marketplace entry, where it takes precedence over the value in
plugin.json
. See
Optional plugin fields
.
​
Component path fields
Field
Type
Description
Example
skills
string|array
Custom skill directories containing
<name>/SKILL.md
. Adds to the default
skills/
scan. See
Path behavior rules
for the marketplace-root exception
"./custom/skills/"
commands
string|array
Custom flat
.md
skill files or directories (replaces default
commands/
)
"./custom/cmd.md"
or
["./cmd1.md"]
agents
string|array
Custom agent files (replaces default
agents/
)
"./custom/agents/reviewer.md"
workflows
string|array
Custom
workflow
script files or directories (replaces default
workflows/
)
"./custom/workflows/"
hooks
string|array|object
Hook config paths or inline config
"./my-extra-hooks.json"
mcpServers
string|array|object
MCP config paths or inline config
"./my-extra-mcp-config.json"
outputStyles
string|array
Custom output style files/directories (replaces default
output-styles/
)
"./styles/"
lspServers
string|array|object
Language Server Protocol
configs for code intelligence (go to definition, find references, etc.)
"./.lsp.json"
experimental.themes
string|array
Color theme files/directories (replaces default
themes/
). See
Themes
"./themes/"
experimental.monitors
string|array
Background
Monitor
configurations that start automatically when the plugin is active. See
Monitors
"./monitors.json"
userConfig
object
User-configurable values prompted at enable time. See
User configuration
See below
channels
array
Channel declarations for message injection (Telegram, Slack, Discord style). See
Channels
See below
dependencies
array
Other plugins this plugin requires, optionally with semver version constraints. See
Constrain plugin dependency versions
[{ "name": "secrets-vault", "version": "~2.1.0" }]
​
Experimental components
Components under the
experimental
key,
themes
and
monitors
, have a manifest schema that may change between releases while they stabilize. Where you declare them is a separate migration: the top level still works,
claude plugin validate
warns, and a future release will require
experimental.*
.
​
User configuration
The
userConfig
field declares values that Claude Code prompts the user for when the plugin is enabled. Use this instead of requiring users to hand-edit
settings.json
.
{
"userConfig"
: {
"api_endpoint"
: {
"type"
:
"string"
,
"title"
:
"API endpoint"
,
"description"
:
"Your team's API endpoint"
},
"api_token"
: {
"type"
:
"string"
,
"title"
:
"API token"
,
"description"
:
"API authentication token"
,
"sensitive"
:
true
}
}
}
Keys must be valid identifiers. Each option supports these fields:
Field
Required
Description
type
Yes
One of
string
,
number
,
boolean
,
directory
, or
file
title
Yes
Label shown in the configuration dialog
description
Yes
Help text shown beneath the field
sensitive
No
If
true
, masks input and stores the value in secure storage instead of
settings.json
required
No
If
true
, validation fails when the field is empty
default
No
Value used when the user provides nothing
multiple
No
For
string
type, allow an array of strings
min
/
max
No
Bounds for
number
type
Each value is available for substitution as
${user_config.KEY}
in MCP and LSP server configs and hook commands. Non-sensitive values can also be substituted in skill and agent content. All values are exported to hook processes as
CLAUDE_PLUGIN_OPTION_<KEY>
environment variables, where
<KEY>
is the option key uppercased.
Fields that run in a shell reject
${user_config.*}
: substituting a configured value into a shell command would let the shell run whatever that value contains, so the component fails with an
error
instead. Each rejected field has an alternative way to pass the value:
Rejected field
How to pass the value
Shell-form hook commands
Use
exec form
with
args
, or read
CLAUDE_PLUGIN_OPTION_<KEY>
from the hook’s environment
Monitor
commands
Read the value from a config file in the script
MCP
headersHelper
Read the value from a config file in the script
Before v2.1.207, these fields substituted
${user_config.KEY}
values; update plugins that relied on this.
Non-sensitive values are stored under the
pluginConfigs
key in your user
settings.json
as
pluginConfigs[<plugin-id>].options
.
Sensitive values go to the macOS Keychain, or to
~/.claude/.credentials.json
on platforms where no supported keychain is available. Keychain storage is shared with OAuth tokens and has an approximately 2 KB total limit, so keep sensitive values small.
Claude Code reads all
pluginConfigs
values from only three settings sources:
User settings
:
~/.claude/settings.json
, the file the enable-time prompt writes to
--settings
: the CLI flag or SDK inline settings
Managed settings
:
organization-controlled policy
When more than one source sets the same key, managed settings take precedence, then
--settings
, then user settings. The only source you can remove from this list is user settings: pass
--setting-sources
without
user
and Claude Code skips them. Managed settings and
--settings
stay whatever you pass. The SDK’s
settingSources
option sets the same list.
Entries in a project’s
.claude/settings.json
or
.claude/settings.local.json
are ignored. Both files live in the workspace, so a cloned repository could supply values there, and those values would flow into plugin hook commands, MCP server configs, LSP commands, and monitor commands. Before v2.1.207, these entries were read. The restriction is specific to
pluginConfigs
:
enabledPlugins
still honors project and local settings.
​
Channels
The
channels
field lets a plugin declare one or more message channels that inject content into the conversation. Each channel binds to an MCP server that the plugin provides.
{
"channels"
: [
{
"server"
:
"telegram"
,
"userConfig"
: {
"bot_token"
: {
"type"
:
"string"
,
"title"
:
"Bot token"
,
"description"
:
"Telegram bot token"
,
"sensitive"
:
true
},
"owner_id"
: {
"type"
:
"string"
,
"title"
:
"Owner ID"
,
"description"
:
"Your Telegram user ID"
}
}
}
]
}
The
server
field is required and must match a key in the plugin’s
mcpServers
. The optional per-channel
userConfig
uses the same schema as the top-level field, letting the plugin prompt for bot tokens or owner IDs when the plugin is enabled.
​
Path behavior rules
Whether a custom path replaces or extends the plugin’s default directory depends on the field:
Replaces the default
:
commands
,
agents
,
workflows
,
outputStyles
,
experimental.themes
,
experimental.monitors
. For example, when the manifest specifies
commands
, the default
commands/
directory is not scanned. To keep the default and add more, list it explicitly:
"commands": ["./commands/", "./extras/"]
Adds to the default
:
skills
. The default
skills/
directory is always scanned, and directories listed in
skills
are loaded alongside it. Exception: for a
marketplace entry whose
source
resolves to the marketplace root
, declaring specific subdirectories replaces the default
skills/
scan
Own merge rules
:
hooks
,
MCP servers
, and
LSP servers
. See each section for how multiple sources combine
When a plugin has both a default folder and the matching manifest key, Claude Code warns about the ignored folder in
claude plugin list
and the
/plugin
detail view. The plugin still loads using the manifest paths. Claude Code doesn’t warn when the manifest key points into the default folder, for example
"commands": ["./commands/deploy.md"]
, because that path names the folder explicitly.
For all path fields:
All paths must be relative to the plugin root and start with
./
, except that the
skills
field also accepts
"."
Both
"."
and
"./"
denote the plugin root itself
Before v2.1.221,
"."
failed manifest validation and the plugin didn’t load, so use
"./"
to support earlier versions
Components from custom paths use the same naming and namespacing rules
Multiple paths can be specified as arrays
A skill path can point to a directory that contains a
SKILL.md
directly, for example
"skills": ["."]
for the plugin root
Claude Code takes the skill’s invocation name from the frontmatter
name
field in
SKILL.md
, so the name stays stable whatever the install directory is named
If
name
isn’t set in the frontmatter, Claude Code falls back to the directory basename
A plugin that has a
SKILL.md
at its root, no
skills/
subdirectory, and no
skills
manifest field is automatically loaded as a single-skill plugin. You do not need to set
"skills": ["./"]
in
plugin.json
for this layout.
Path examples
:
{
"commands"
: [
"./specialized/deploy.md"
,
"./utilities/batch-process.md"
],
"agents"
: [
"./custom-agents/reviewer.md"
,
"./custom-agents/tester.md"
]
}
​
Environment variables
Claude Code provides three variables for referencing paths:
Variable
Resolves to
Use it for
${CLAUDE_PLUGIN_ROOT}
Absolute path to the plugin’s installation directory
Scripts, binaries, and config files bundled with the plugin
${CLAUDE_PLUGIN_DATA}
Persistent directory
that survives plugin updates, created on first reference
Installed dependencies such as
node_modules
or Python virtual environments, generated code, and caches
${CLAUDE_PROJECT_DIR}
The project root
Project-local scripts and config files
All three are exported as environment variables to hook processes and to MCP and LSP server subprocesses. Which fields substitute them inline depends on the plugin component:
Plugin component
Fields where placeholders resolve
Skill and agent content
Anywhere the placeholder appears
Hook and monitor commands
Anywhere the placeholder appears
MCP
stdio
servers
command
,
args
,
env
MCP
http
,
sse
,
ws
servers
url
,
headers
,
headersHelper
LSP servers
command
,
args
,
env
,
workspaceFolder
In hook commands, use
exec form
with
args
so each path is passed as one argument with no quoting. In shell-form hooks and monitor commands, wrap the variables in double quotes, as in
"${CLAUDE_PROJECT_DIR}/scripts/server.sh"
. This shell-form hook runs a script bundled with a plugin:
{
"hooks"
: {
"PostToolUse"
: [
{
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"
\"
${CLAUDE_PLUGIN_ROOT}
\"
/scripts/process.sh"
}
]
}
]
}
}
${CLAUDE_PLUGIN_ROOT}
changes when the plugin updates. The previous version’s directory remains on disk for a grace period after an update, but treat it as ephemeral and don’t write state there. See
plugin caching
for cleanup semantics.
When a plugin updates mid-session, hook commands, monitors, MCP servers, and LSP servers keep using the previous version’s path. Run
/reload-plugins
to switch hooks, MCP servers, and LSP servers to the new path; monitors require a session restart. For a plugin with a
command
source, Claude Code
can reload the plugin itself
.
MCP servers can also call the
roots/list
request to read the session’s working directories at runtime. See
what
roots/list
returns and when Claude Code notifies the server of changes
.
​
Persistent data directory
The
${CLAUDE_PLUGIN_DATA}
directory resolves to
~/.claude/plugins/data/{id}/
, where
{id}
is the plugin identifier with characters outside
a-z
,
A-Z
,
0-9
,
_
, and
-
replaced by
-
. For a plugin installed as
formatter@my-marketplace
, the directory is
~/.claude/plugins/data/formatter-my-marketplace/
.
A common use is installing language dependencies once and reusing them across sessions and plugin updates. Use it for Python dependencies, dependencies locked with Yarn or pnpm, and packages whose lifecycle scripts must run. For a marketplace-installed plugin, you may not need it at all: Claude Code installs eligible
Node.js package dependencies
automatically when it caches the plugin.
Because the data directory outlives any single plugin version, a check for directory existence alone cannot detect when an update changes the plugin’s dependency manifest. The recommended pattern compares the bundled manifest against a copy in the data directory and reinstalls when they differ.
This
SessionStart
hook installs
node_modules
on the first run and again whenever a plugin update includes a changed
package.json
:
{
"hooks"
: {
"SessionStart"
: [
{
"hooks"
: [
{
"type"
:
"command"
,
"command"
:
"diff -q
\"
${CLAUDE_PLUGIN_ROOT}/package.json
\"
\"
${CLAUDE_PLUGIN_DATA}/package.json
\"
>/dev/null 2>&1 || (cd
\"
${CLAUDE_PLUGIN_DATA}
\"
&& cp
\"
${CLAUDE_PLUGIN_ROOT}/package.json
\"
. && npm install) || rm -f
\"
${CLAUDE_PLUGIN_DATA}/package.json
\"
"
}
]
}
]
}
}
The
diff
exits nonzero when the stored copy is missing or differs from the bundled one, covering both first run and dependency-changing updates. If
npm install
fails, the trailing
rm
removes the copied manifest so the next session retries.
Scripts bundled in
${CLAUDE_PLUGIN_ROOT}
can then run against the persisted
node_modules
:
{
"mcpServers"
: {
"routines"
: {
"command"
:
"node"
,
"args"
: [
"${CLAUDE_PLUGIN_ROOT}/server.js"
],
"env"
: {
"NODE_PATH"
:
"${CLAUDE_PLUGIN_DATA}/node_modules"
}
}
}
}
The data directory is deleted automatically when you uninstall the plugin from the last scope where it is installed. The
/plugin
interface shows the directory size and prompts before deleting. The CLI deletes by default; pass
--keep-data
to preserve it.
​
Plugin caching and file resolution
Plugins are specified in one of two ways:
Through
claude --plugin-dir
or
claude --plugin-url
, for the duration of a session.
Through a marketplace, installed for future sessions.
For security and verification purposes, Claude Code copies
marketplace
plugins to the user’s local
plugin cache
(
~/.claude/plugins/cache
) rather than using them in place, except for
command
sources in link mode
, which Claude Code uses in place through links in the cache entry.
For copied plugins, each installed version is a separate directory in the cache, grouped by marketplace and plugin and named for the resolved version, with its own copy of the plugin’s files and
Node.js package dependencies
. A dependency resolved from a
release tag
gets a directory name with a commit-SHA suffix.
When you update or uninstall a plugin, Claude Code marks the previous version directory as orphaned and removes it in a background sweep roughly 14 days later. The grace period lets concurrent Claude Code sessions that already loaded the old version keep running without errors. Claude Code runs the sweep only while at least one plugin is installed; after you uninstall your last plugin, orphaned directories stay on disk until you install a plugin again.
Claude Code removes a plugin or marketplace folder from the cache only when it no longer contains any directory or symlink. If you symlink a development checkout into the cache as a plugin’s version entry, Claude Code never marks the link as orphaned and never removes it or the folders that hold it. Claude Code also never writes its version-tracking files inside the linked checkout.
Claude’s Glob and Grep tools skip orphaned version directories during searches, so file results don’t include outdated plugin code.
​
Node.js package dependencies
When Claude Code copies a plugin into the cache, it also installs the plugin’s Node.js package dependencies there, so the plugin’s hooks and MCP servers can load them. This section covers the npm and Bun packages a plugin declares in its own
package.json
. For plugins that depend on other plugins, see
plugin dependency versions
.
Claude Code runs the install inside the copied version directory each time it creates one: when you install a plugin, when Claude Code updates a plugin to a new version, and at session start when an enabled plugin isn’t cached yet, such as on a new machine. The install runs only when the plugin’s root directory contains both a
package.json
and a supported lockfile:
Lockfile
Command
bun.lock
or
bun.lockb
bun install --frozen-lockfile --ignore-scripts
npm-shrinkwrap.json
or
package-lock.json
npm ci --ignore-scripts
If a plugin contains more than one of these lockfiles, Claude Code uses the first match, checking in order:
bun.lock
,
bun.lockb
,
npm-shrinkwrap.json
,
package-lock.json
. Claude Code skips
yarn.lock
and
pnpm-lock.yaml
because Yarn and pnpm support resolution-time configuration hooks that bypass
--ignore-scripts
.
Ship an npm lockfile for the widest reach. Claude Code runs the matched lockfile’s package manager from the user’s PATH and doesn’t fall back to the other lockfile if it’s missing. For a plugin distributed through an npm source, use
npm-shrinkwrap.json
; npm excludes
package-lock.json
from published packages.
Claude Code constrains this dependency install so that no code from the plugin or its packages executes during it, and bounds how long it can run:
Frozen resolution:
Bun and npm install exactly what the lockfile pins, and fail rather than re-resolve versions when
package.json
and the lockfile disagree.
No lifecycle scripts:
--ignore-scripts
keeps
preinstall
,
install
, and
postinstall
scripts from running, so dependencies that build native modules in those scripts download but don’t compile during this install.
60-second timeout:
Claude Code stops an install that runs longer and treats it as failed.
Fetching an npm-source plugin itself runs
npm install
with lifecycle scripts enabled, before this dependency install runs.
A failed or skipped install never blocks the plugin. When the install fails, or Claude Code skips a yarn or pnpm lockfile, it records the reason as a warning in
debug output
. A plugin with a
package.json
and no lockfile is skipped without a log entry. A timed-out install can leave a partial
node_modules
tree in the cached copy.
You can’t turn the automatic install off; no setting or environment variable disables it. In restricted networks, see the
network access requirements
for the hosts to allow.
For dependencies the automatic install can’t provide, such as packages that need their lifecycle scripts to build, Python dependencies, or a plugin locked with Yarn or pnpm, install them from a hook into the
persistent data directory
.
​
Path traversal limitations
Claude Code doesn’t let a plugin reference files outside its own directory. It rejects a component path that resolves outside the plugin root, such as
../shared-utils
, whether the path is declared in
plugin.json
or in a
marketplace entry
. Claude Code reports a
path escapes plugin directory
error and loads the plugin without that component.
Claude Code also doesn’t copy files outside the plugin directory into the cache when it installs the plugin, so when a script inside a copied plugin reads a path above the plugin root, it doesn’t find those files either.
​
Share files within a marketplace with symlinks
If your plugin needs to share files with other parts of the same marketplace, you can create symbolic links inside your plugin directory. How a symlink is handled when the plugin is copied into the cache depends on where its target resolves:
Within the plugin’s own directory:
the symlink is preserved as a relative symlink in the cache, so it keeps resolving to the copied target at runtime.
Elsewhere within the same marketplace:
the symlink is dereferenced. The target’s content is copied into the cache in its place. This lets a meta-plugin’s
skills/
directory link to skills defined by other plugins in the marketplace.
Outside the marketplace:
the symlink is skipped for security. This prevents plugins from pulling arbitrary host files such as system paths into the cache.
For plugins installed with
--plugin-dir
, from a local path, or from a
command
source
in copy mode, only symlinks that resolve within the plugin’s own directory are preserved. All others are skipped.
The following command creates a link from inside a marketplace plugin to a shared skill defined by a sibling plugin. On Windows, use
mklink /D
from an elevated Command Prompt or enable Developer Mode:
ln
-s
../../shared-plugin/skills/foo
./skills/foo
​
Plugin directory structure
​
Standard plugin layout
A complete plugin follows this structure:
enterprise-plugin/
├── .claude-plugin/           # Metadata directory (optional)
│   └── plugin.json             # plugin manifest
├── skills/                   # Skills
│   ├── code-reviewer/
│   │   └── SKILL.md
│   └── pdf-processor/
│       ├── SKILL.md
│       └── scripts/
├── commands/                 # Skills as flat .md files
│   ├── status.md
│   └── logs.md
├── agents/                   # Subagent definitions
│   ├── security-reviewer.md
│   ├── performance-tester.md
│   └── compliance-checker.md
├── workflows/                # Workflow scripts
│   └── release-audit.js
├── output-styles/            # Output style definitions
│   └── terse.md
├── themes/                   # Color theme definitions
│   └── dracula.json
├── monitors/                 # Background monitor configurations
│   └── monitors.json
├── hooks/                    # Hook configurations
│   ├── hooks.json           # Main hook config
│   └── security-hooks.json  # Additional hooks
├── bin/                      # Plugin executables added to PATH
│   └── my-tool               # Invokable as bare command in Bash tool
├── settings.json            # Default settings for the plugin
├── .mcp.json                # MCP server definitions
├── .lsp.json                # LSP server configurations
├── scripts/                 # Hook and utility scripts
│   ├── security-scan.sh
│   ├── format-code.py
│   └── deploy.js
├── LICENSE                  # License file
└── CHANGELOG.md             # Version history
The
.claude-plugin/
directory contains the
plugin.json
file. All other directories (commands/, agents/, skills/, workflows/, output-styles/, themes/, monitors/, hooks/) must be at the plugin root, not inside
.claude-plugin/
.
A
CLAUDE.md
file at the plugin root is not loaded as project context. Plugins contribute context through skills, agents, and hooks rather than CLAUDE.md. To ship instructions that load into Claude’s context, put them in a
skill
.
​
File locations reference
Component
Default Location
Purpose
Manifest
.claude-plugin/plugin.json
Plugin metadata and configuration (optional)
Skills
skills/
Skills with
<name>/SKILL.md
structure
Commands
commands/
Skills as flat Markdown files. Use
skills/
for new plugins
Agents
agents/
Subagent Markdown files
Workflows
workflows/
Workflow
script files
Output styles
output-styles/
Output style definitions
Themes
themes/
Color theme definitions
Hooks
hooks/hooks.json
Hook configuration
MCP servers
.mcp.json
MCP server definitions
LSP servers
.lsp.json
Language server configurations
Monitors
monitors/monitors.json
Background monitor configurations
Executables
bin/
Executables added to the Bash tool’s
PATH
and invokable as bare commands while the plugin is enabled. You can’t include this directory in a plugin you
distribute through claude.ai organization settings
Settings
settings.json
Default configuration applied when the plugin is enabled. Only the
agent
and
subagentStatusLine
keys are supported
​
CLI commands reference
Claude Code provides CLI commands for non-interactive plugin management, useful for scripting and automation.
​
plugin init
Scaffold a new plugin at
~/.claude/skills/<name>/
. On the next Clau

## Source (output-styles): https://docs.claude.com/en/docs/claude-code/output-styles

Output styles - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Output styles change how Claude responds, not what Claude knows. They modify the system prompt to set role, tone, and output format. Use one when you keep re-prompting for the same voice or format every turn, or when you want Claude to act as something other than a software engineer.
A custom output style adds your instructions to the system prompt and lets you choose whether to keep Claude Code’s built-in software engineering instructions. Keep them when you’re changing how Claude communicates but still coding, like always answering with a diagram. Leave them out when Claude isn’t doing software engineering at all, like a writing assistant or data analyst.
For instructions about your project, conventions, or codebase, use
CLAUDE.md
instead.
​
Built-in output styles
Claude Code’s
Default
output style is the existing system prompt, designed to help you complete software engineering tasks efficiently.
There are four additional built-in output styles:
Proactive
: Claude executes immediately, makes reasonable assumptions instead of pausing for routine decisions, and prefers action over planning. This is stronger autonomous-execution guidance than
auto mode
applies, and it works without changing your permission mode, so your permission mode still decides what runs without asking you.
Concise
: Claude leads with the result, skips preamble and narration, and keeps responses short by default, while doing the engineering work as thoroughly as in the Default style. When you ask for an explanation or more detail, Claude answers in full. Claude always keeps the complete content of error reports, security warnings, and confirmations for destructive actions. Requires Claude Code v2.1.237 or later.
Explanatory
: Provides educational “Insights” in between helping you complete software engineering tasks. Helps you understand implementation choices and codebase patterns.
Learning
: Collaborative, learn-by-doing mode where Claude will not only share “Insights” while coding, but also ask you to contribute small, strategic pieces of code yourself. Claude Code will add
TODO(human)
markers in your code for you to implement.
​
Change your output style
Pick a style in one of these ways:
Terminal
: run
/config
and select
Output style
to pick a style from a menu. Claude Code saves your selection to
.claude/settings.local.json
at the
local project level
.
Desktop app
: set the
outputStyle
field in a settings file, for example
.claude/settings.local.json
, the file the terminal menu writes. When you run
/config
there, Claude Code
opens
Settings > Claude Code
rather than a menu.
The standalone
/output-style
command was deprecated in v2.1.73 and removed in v2.1.91. Use
/config
or edit the
outputStyle
setting directly.
To set a style without the menu, edit the
outputStyle
field directly in a settings file:
{
"outputStyle"
:
"Explanatory"
}
Output style is part of the system prompt, which Claude Code reads once at session start. Changes take effect after
/clear
or a new session. See
How Claude Code uses prompt caching
for what an output style change does to the cache.
​
Create a custom output style
A custom output style is a Markdown file: frontmatter for metadata, then the instructions to add to the system prompt.
1
Create a Markdown file
Save it at one of three levels. The file name becomes the style name unless you set
name
in the frontmatter.
User:
~/.claude/output-styles
Project:
.claude/output-styles
Managed policy:
.claude/output-styles
inside the
managed settings directory
Project output styles load from every
.claude/output-styles/
between the working directory and the repository root. When more than one of these nested directories defines a style with the same name, Claude Code uses the one closest to the working directory.
2
Add frontmatter and instructions
Decide whether to keep Claude Code’s software engineering instructions. Set
keep-coding-instructions: true
if you’re changing how Claude communicates but still want it coding the same way. Leave it out if Claude won’t be doing software engineering.
This example leads every explanation with a diagram while keeping Claude’s coding behavior:
---
name
:
Diagrams first
description
:
Lead every explanation with a diagram
keep-coding-instructions
:
true
---
When explaining code, architecture, or data flow, start with a Mermaid diagram showing the structure, then explain in prose.
## Diagram conventions
Use
`flowchart TD`
for control flow and
`sequenceDiagram`
for request paths. Keep diagrams under 15 nodes.
3
Switch to your style
Run
/config
in the terminal and select your style under
Output style
, or set
outputStyle
in a settings file to the style’s name. It takes effect after
/clear
or the next time you start a session.
Plugins
can also ship output styles in an
output-styles/
directory.
​
Frontmatter
Output style files support these frontmatter fields:
Frontmatter
Purpose
Default
name
Name of the output style, if not the file name
Inherits from file name
description
Description of the output style, shown in the
/config
picker
None
keep-coding-instructions
Keep Claude Code’s built-in software engineering instructions
false
force-for-plugin
Plugin output styles only: apply this style automatically whenever the plugin is enabled, without requiring users to select it. Overrides the user’s
outputStyle
setting. If multiple enabled plugins set this, Claude Code uses the first one loaded.
false
​
How output styles work
Output styles directly modify Claude Code’s system prompt.
Claude Code adds the output style’s custom instructions to the system prompt.
When you
select a style other than Default
, Claude Code also reminds Claude of the style during the conversation.
Custom output styles leave out Claude Code’s built-in software engineering instructions, such as how to scope changes, write comments, and verify work, unless
keep-coding-instructions
is set to
true
.
Output styles apply to the main conversation only: a
subagent runs its own system prompt
, so styles don’t change how subagents respond. A
fork
is the exception, because it inherits the parent’s full system prompt.
Token usage depends on the style. Adding instructions to the system prompt increases input tokens, though prompt caching reduces this cost after the first request in a session. The built-in Explanatory and Learning styles produce longer responses than Default by design, which increases output tokens, and the Concise style does the opposite by instructing Claude to keep responses short by default. For custom styles, output token usage depends on what your instructions tell Claude to produce.
​
Comparisons to related features
Several features customize how Claude Code behaves. Output styles modify the system prompt directly and apply to every response. The others add instructions without changing the default system prompt, or scope them to a specific task.
Feature
How it works
Use it when
Output styles
Modifies the system prompt
You want a different role, tone, or default response format every turn
CLAUDE.md
Adds a user message after the system prompt
Claude should always know your project conventions and codebase context
--append-system-prompt
Appends to the system prompt without removing anything
You want a one-off addition for a single invocation
Agents
Runs a subagent with its own system prompt, model, and tools
You want a separately scoped helper for a focused task
Skills
Loads task-specific instructions when invoked or relevant
You have a reusable workflow
​
Related resources
Settings
: where the
outputStyle
field lives and how settings precedence works
Permission modes
: how the Proactive style compares to auto mode
Plugins
: package and distribute output styles alongside skills, hooks, and agents
Debug your configuration
: diagnose why an output style isn’t taking effect
Was this page helpful?
Yes
No
Assistant
Responses are generated using AI and may contain mistakes.

## Source (tools-reference): https://docs.claude.com/en/docs/claude-code/tools-reference

Tools reference - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Claude Code has access to a set of built-in tools that help it understand and modify your codebase. The tool names are the exact strings you use in
permission rules
,
subagent tool lists
, and
hook matchers
.
To control which tools Claude can use and when it asks first, configure
permission rules
in your settings,
hooks
, or a
subagent’s tool list
. See
Configure tools with permission rules and hooks
for each place that accepts a tool name.
To add custom tools, connect an
MCP server
. To extend Claude with reusable prompt-based workflows, write a
skill
, which runs through the existing
Skill
tool rather than adding a new tool entry.
On Pro, Max, and Team plans, Claude Code starts sessions in
auto mode
, where a classifier decides most of these prompts instead of you. The
Permission required
column shows whether the tool prompts in
Manual mode
for paths inside the working directory. File-access tools marked No, including
Read
,
Grep
, and
Glob
, still prompt for paths outside the
working directory and additional directories
.
Bash
is marked Yes but runs a built-in set of
read-only commands
without prompting.
Tool
Description
Permission required
Agent
Spawns a
subagent
with its own context window to handle a task. With
agent teams
enabled, a call that carries a
name
can launch a
teammate
instead. See
Agent tool behavior
No
Artifact
Publishes an HTML or Markdown file as an
artifact
: a private, interactive page on claude.ai. You can share it with a public link, or inside your organization on Team and Enterprise plans, where public sharing requires an Owner to
enable it
. Requires a Pro, Max, Team, or Enterprise plan and
/login
authentication; see
Availability
Yes
AskUserQuestion
Asks multiple-choice questions to gather requirements or clarify ambiguity. Questions stay open until you answer them by default. See
AskUserQuestion tool behavior
No
Bash
Executes shell commands in your environment. See
Bash tool behavior
Yes
CronCreate
Schedules a recurring or one-shot prompt within the current session. Tasks are session-scoped and restored on
--resume
or
--continue
if unexpired. See
scheduled tasks
No
CronDelete
Cancels a scheduled task by ID
No
CronList
Lists all scheduled tasks in the session
No
Edit
Makes targeted edits to specific files. See
Edit tool behavior
Yes
EndConversation
Ends the session, in rare cases of sustained abusive input or when you ask Claude to demonstrate the tool. Requires Claude Code v2.1.213 or later. See
EndConversation tool behavior
No
EnterPlanMode
Switches to plan mode to design an approach before coding
No
EnterWorktree
Creates an isolated
git worktree
and switches into it. Pass a
path
to switch into an existing worktree instead of creating a new one. On first entry the target may be a worktree of the current repository or, in a multi-repo workspace, of a repository nested inside it. Before v2.1.203, a nested repository’s worktree was rejected. A
path
outside
.claude/worktrees/
prompts for your approval before entering, since it moves the session’s working directory and write access to that location. New-worktree creation and paths under
.claude/worktrees/
don’t prompt. Before v2.1.206, Claude entered paths outside
.claude/worktrees/
without a prompt. From within a worktree session, or from a subagent with a pinned working directory such as
isolation: worktree
, only the
path
form is available and the target must be under
.claude/worktrees/
of the session’s repository
Yes
ExitPlanMode
Presents a plan for approval and exits plan mode
Yes
ExitWorktree
Exits a worktree session and returns to the original directory. Not available to subagents that already run in their own working directory, such as with
isolation: worktree
No
Glob
Finds files based on pattern matching. See
Glob tool behavior
No
Grep
Searches for patterns in file contents. See
Grep tool behavior
No
ListAgents
Lists the agents Claude can message with
SendMessage
: subagents in the session,
agent team
teammates, your other local Claude Code sessions, and, while this session is connected to
Remote Control
, your
Claude Code on the web
sessions and your Remote Control sessions on other machines. Backs the
/list-agents
command. See
cross-session messaging
. Requires Claude Code v2.1.224 or later, and appears only in sessions where
cross-session messaging is enabled
. Teammate rows and the first line showing this session’s own name require v2.1.239 or later
No
ListMcpResourcesTool
Lists resources exposed by connected
MCP servers
No
LSP
Code intelligence via language servers: jump to definitions, find references, report type errors and warnings. See
LSP tool behavior
No
Monitor
Runs a command in the background and feeds each output line back to Claude, so it can react to log entries, file changes, or polled status mid-conversation. Can also open a WebSocket and treat each incoming message as an event. See
Monitor tool
Yes
NotebookEdit
Modifies Jupyter notebook cells. See
NotebookEdit tool behavior
Yes
PowerShell
Executes PowerShell commands natively. See
PowerShell tool
for availability
Yes
PushNotification
Sends a desktop notification, and a phone push when
Remote Control
is connected, so a long-running task or
scheduled task
can reach you when you step away. Push delivery runs through Anthropic-hosted infrastructure, which is not accessible from Amazon Bedrock, Claude Platform on AWS, Google Cloud’s Agent Platform, or Microsoft Foundry
No
Read
Reads the contents of files. See
Read tool behavior
No
ReadMcpResourceTool
Reads a specific MCP resource by URI
No
RemoteTrigger
Creates, updates, runs, and lists
Routines
on claude.ai. Backs the
/schedule
command. The
RemoteTrigger
input reference
documents every action and the organization policies that remove the tool. Routines live on claude.ai and require a Pro, Max, Team, or Enterprise plan, so this tool is not accessible from Amazon Bedrock, Claude Platform on AWS, Google Cloud’s Agent Platform, or Microsoft Foundry. Also unavailable when you turn off
feature-flag fetching
No
ReportFindings
Reports code-review findings as a structured list, with a file, summary, and failure scenario per finding, so Claude Code can render them instead of printing them as text. Claude calls it when active code-review instructions tell it to. Requires Claude Code v2.1.196 or later. As of v2.1.199, a finding can also carry an optional
category
slug, such as
correctness
or
test-coverage
, shown next to the file location in the rendered list
No
ScheduleWakeup
Reschedules the next iteration of a
self-paced
/loop
. Claude calls this at the end of each iteration to pick when the next one runs, between one minute and one hour out; you don’t call it directly. To end the loop instead, Claude calls it with
stop: true
, which cancels the pending wakeup. The
stop
field requires Claude Code v2.1.202 or later. The pending wakeup appears in
session_crons
in
Stop hook input
No
SendFeedback
Drafts a feedback report about Claude Code, covering a product problem or Claude’s own behavior in the session, and queues it on your machine for you to review. Claude Code sends nothing until you choose to send the draft. See
SendFeedback tool behavior
. Requires Claude Code v2.1.238 or later
No
SendMessage
Sends a message to another agent: an
agent team
teammate, a
subagent it resumes
by agent ID or name, or one of your other Claude Code sessions, on this machine or beyond it. Messaging other sessions requires Claude Code v2.1.224 or later.
Cross-session messaging
covers which sessions Claude can reach,
what a message looks like when it arrives
, and
how Claude gets a notice when another session goes idle
. Claude can include an optional
summary
input, typically 5-10 words, that Claude Code shows as a one-line preview. When Claude omits it on a
plain-text message
, Claude Code uses the first line of the message as the summary. Claude Code truncates a summary longer than 200 characters with an ellipsis
No
SendUserFile
Sends files from the session to you with an optional caption, so a generated report, diagram, screenshot, or built artifact reaches your device instead of only being mentioned in the transcript. As of v2.1.196, the optional
display
input controls presentation:
render
opens the file inline in the client,
attach
shows a download card only, and when unset the client decides by file type. Available when a
Remote Control
client is connected or the session runs in a managed cloud environment such as
Claude Code on the web
. Delivery runs through Anthropic-hosted infrastructure, so the tool is not available on Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry
No
ShareOnboardingGuide
Uploads
ONBOARDING.md
and returns a share link teammates can open in Claude Code. Called from
/team-onboarding
after the guide is written. Available to claude.ai subscribers on Pro, Max, Team, and Enterprise plans
Yes
Skill
Executes a
skill
within the main conversation
Yes
TaskCreate
Creates a new task in the task list. Claude Code leaves it out on the models listed under
Task tool availability
unless you opt in
No
TaskGet
Retrieves full details for a specific task. Claude Code leaves it out on the models listed under
Task tool availability
unless you opt in
No
TaskList
Lists all tasks with their current status. Claude Code leaves it out on the models listed under
Task tool availability
unless you opt in
No
TaskOutput
Retrieves output from a background task. Deprecated in favor of
Read
on the task’s output file path. When no task matches the ID, the error lists the running background agents by ID and description. Before v2.1.203, the error named only the missing ID
No
TaskStop
Stops a running background task by ID. It also accepts an
agent-team teammate
or a named background agent by agent ID or name. Before v2.1.198, it accepted only a background task ID. When no task matches the ID, the error lists the running background agents by ID and description, including agents that another agent spawned. Before v2.1.203, the error listed running teammates and named agents but not background agents another agent spawned, so those couldn’t be identified or stopped from the main conversation
No
TaskUpdate
Updates task status, dependencies, details, or deletes tasks. Claude Code leaves it out on the models listed under
Task tool availability
unless you opt in
No
TodoWrite
Manages the session task checklist. Disabled by default in favor of
TaskCreate
,
TaskGet
,
TaskList
, and
TaskUpdate
. Set
CLAUDE_CODE_ENABLE_TASKS=0
to re-enable it in
sessions that have the task-tracking tools
No
ToolSearch
Searches for and loads deferred tools when
tool search
is enabled
No
WaitForMcpServers
Waits for one or more
MCP servers
that are still connecting in the background, so a request can use their tools without restarting the session. Claude calls it when a needed server isn’t connected yet. Only appears when
tool search
is disabled, since
ToolSearch
handles the wait when it’s enabled
No
WebFetch
Fetches content from a specified URL. See
WebFetch tool behavior
Yes
WebSearch
Performs web searches. See
WebSearch tool behavior
Yes
Workflow
Runs a
dynamic workflow
: a script that orchestrates many subagents in the background and returns one consolidated result
Yes
Write
Creates or overwrites files. See
Write tool behavior
Yes
​
Configure tools with permission rules and hooks
For the most part, Claude decides when to use these tools and you don’t need to name them yourself when interacting with Claude. You reference tool names directly when defining permissions and other configuration:
in
permissions.allow
and
permissions.deny
in settings, and the
/permissions
interface
in the
--allowedTools
and
--disallowedTools
CLI flags
in the Agent SDK’s
allowedTools
and
disallowedTools
options
in a
subagent’s
tools
or
disallowedTools
frontmatter
in a
skill’s
allowed-tools
frontmatter
in a hook’s
if
condition
All of these accept the same rule format,
ToolName(specifier)
. The specifier depends on the tool, and several tools share a format:
Rule format
Applies to
Details
Bash(npm run *)
Bash, Monitor
Command pattern matching
PowerShell(Get-ChildItem *)
PowerShell
Command pattern matching
Read(~/secrets/**)
Read, Grep, Glob, LSP
Path pattern matching
Edit(/src/**)
Edit, Write, NotebookEdit
Path pattern matching
Skill(deploy *)
Skill
Skill name matching
Agent(Explore)
Agent
Subagent type matching
WebFetch(domain:example.com)
WebFetch
Domain matching
WebSearch
WebSearch
No specifier; allow or deny the tool as a whole
Tools not listed here, such as
ExitPlanMode
or
ShareOnboardingGuide
, accept only the bare tool name with no specifier.
An
Edit(...)
allow rule also grants read access to the same path, so you don’t need a matching
Read(...)
rule. A
Read(...)
deny rule also blocks the Edit and Write tools on the same path, including creating a new file there, because both tools change content Claude has to be able to read back. The
Read
deny check requires Claude Code v2.1.208 or later on edits, and v2.1.228 or later on writes.
Hook
matcher
fields use bare tool names, not the parenthesized rule format. See
matcher patterns
for the matching rules. For the field names each tool passes to
tool_input
in hooks, see the
PreToolUse input reference
.
​
Agent tool behavior
The Agent tool spawns a subagent in a separate context window. The subagent works through its task autonomously, then returns a single text result to the parent conversation. The parent doesn’t see the subagent’s intermediate tool calls or outputs, only that final result. With
agent teams
enabled, a call that carries a
name
can launch a
teammate
instead, which reports back through team messages rather than by returning a result.
To cap how many turns a subagent runs, set
maxTurns
in the
subagent definition
. When the subagent reaches the limit, Claude Code marks the returned result as partial output, and Claude can
resume the subagent
to continue.
The same Agent tool also launches
forked subagents
wherever
fork mode
is on. A fork inherits the full parent conversation instead of starting fresh, runs in the background apart from the
cases that stay in the foreground
, and still surfaces permission prompts in your terminal. The rest of this section describes non-fork subagents.
Which tools a non-fork subagent can use depends on the
tools
and
disallowedTools
fields in the
subagent definition
:
Neither field set
: the subagent inherits every
tool available to subagents
.
tools
only
: the subagent gets only the listed tools.
disallowedTools
only
: the subagent gets every parent tool except the listed ones.
Both set
:
disallowedTools
takes precedence. A tool listed in both is removed.
In every case, the resolved set is limited to the
tools available to subagents
: a tool that isn’t available to subagents is never granted, even when listed in
tools
.
If every entry in a subagent’s
tools
list fails to match a usable tool, the Agent tool usually returns an error naming the entries instead of launching the subagent; see
Agent would be spawned with zero tools
for the message and how to fix each entry.
Launching the subagent doesn’t itself prompt for permission. Claude Code checks the subagent’s own tool calls against your permission rules as it runs.
Where you see a subagent’s permission prompts depends on whether it runs in the foreground or the background. Claude Code runs subagents in the background by default, apart from the
cases that run in the foreground
.
Foreground subagents
show the same permission prompts you would see in the main conversation, at the moment each tool call happens.
Background subagents
surface permission prompts in your main session as of v2.1.186. The prompt names which subagent is asking, and pressing Esc denies that one tool call without stopping the subagent. Before v2.1.186, background subagents auto-denied any tool call that would otherwise prompt and continued without that tool.
To
limit what a subagent can reach
in the first place, narrow its
tools
field, for example by leaving Bash off the list, or set deny rules in your settings.
​
AskUserQuestion tool behavior
Claude uses
AskUserQuestion
to ask you multiple-choice questions when it needs a decision or a clarification. Answer by picking an option, or type your own text through the
Other
row or the notes field.
When you answer by typing your own text, Claude Code relays the answer with neutral wording so Claude follows what you wrote, including a request to wait or explain first.
​
Question auto-continue timeout
Questions stay open until you answer them. If you want a question you leave unanswered to eventually close and let Claude continue without you, set the
askUserQuestionTimeout
setting to
60s
,
5m
, or
10m
, either in your user
settings.json
or from the
Question auto-continue timeout
row in
/config
.
After a question sits that long with no input, the dialog closes on its own: it submits any options you’d already selected and tells Claude you may be away from your keyboard, so Claude proceeds on its own judgment and can re-ask later. You see a countdown for the last 20 seconds. Press any key to restart the timer; on terminals that report focus, switching to the window restarts it too.
The timeout applies only to
AskUserQuestion
’s multiple-choice questions; permission prompts, including plan approval, never auto-resolve on idle.
​
Bash tool behavior
The Bash tool runs each command in a separate process.
​
What persists between commands
When Claude runs
cd
in the main session, the new working directory carries over to later Bash commands as long as it stays inside the project directory or an
additional working directory
you added with
--add-dir
,
/add-dir
, or
additionalDirectories
in settings. Subagent sessions never carry over working directory changes.
If
cd
lands outside those directories, Claude Code resets to the project directory and appends
Shell cwd was reset to <dir>
to the tool result.
To disable this carry-over so every Bash command starts in the project directory, set
CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1
.
Environment variables don’t persist. An
export
in one command won’t be available in the next.
Aliases and shell functions defined in your shell startup file are available. At session start, Claude Code sources
~/.zshrc
,
~/.bashrc
, or
~/.profile
depending on your shell, captures the resulting aliases, functions, and shell options, and applies them to every Bash command.
Activate your virtualenv or conda environment before launching Claude Code. To make environment variables persist across Bash commands, set
CLAUDE_ENV_FILE
to a shell script before launching Claude Code, or use a
SessionStart hook
to populate it dynamically.
​
Timeout and output limits
Each command runs under a timeout, and Claude manages it: when it wants longer than the default for a command, it passes the
timeout
parameter with that call — you never set a per-command timeout. Two
environment variables
bound what Claude gets:
BASH_DEFAULT_TIMEOUT_MS
— the default when Claude passes no timeout; two minutes out of the box
BASH_MAX_TIMEOUT_MS
— with the default, sets the ceiling that caps whatever Claude requests: the effective ceiling is the larger of the two, ten minutes out of the box
​
Output limits
Claude Code streams a command’s output to a working file as the command runs; a command whose output passes 5 GB is killed. When the command finishes, Claude Code reads the output back from that file, up to the read-back window described below. How much of the output reaches Claude inline depends on whether Claude Code treats the result as a failure:
Result
What Claude gets
Valid
Inline up to roughly 30,000 characters; past that, the path of a file saved to the session directory, truncated past 64 MiB, plus a short preview from the start, and Claude reads or searches the file when it needs the rest
Failure
Inline up to roughly 10,000 characters; past that, a head-and-tail excerpt of that size cut from the read-back window, with no file path
A command that exits 1 counts as a valid result for the Bash tool only when Claude Code recognizes exit code 1 as a benign outcome for that command:
grep
,
rg
,
egrep
,
fgrep
,
find
,
diff
,
test
, and
[
, plus
git diff
and
git grep
. Every other command that exits 1 counts as a failure, even when exit 1 is a benign informational outcome: no matches for
pgrep
and
jq -e
, files that differ for
cmp
.
BASH_MAX_OUTPUT_LENGTH
sets how many characters of output Claude Code reads back from the working file into a command’s result: 30,000 by default, up to a hard ceiling of 150,000. Raise it when your commands routinely overflow that window, such as a verbose build or a full test-suite log. Raising it enlarges the read-back window, and the window a failing command’s excerpt is cut from. It does not raise the inline ceilings above: a valid result over roughly 30,000 characters arrives as a file path plus preview regardless of this variable.
​
Background commands
For long-running processes such as dev servers or watch builds, Claude can set
run_in_background: true
to start the command as a background task and continue working while it runs. List and stop background tasks with
/tasks
. When a
subagent running in the foreground
started the command, Claude Code ends it when that subagent gives its final response. Commands started by the main conversation or by a background subagent keep running. In non-interactive mode with the
-p
flag,
background tasks end shortly after the run’s final result
.
When a command reaches its timeout without finishing, Claude Code moves it to the background instead of stopping it. Claude keeps working while the command continues. Claude Code applies the same lifetime rules to a moved command as to any other background command, so it still ends a foreground subagent’s command at that subagent’s final response. Setting
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
disables auto-backgrounding along with the rest of the background task functionality.
Claude Code never auto-backgrounds three kinds of command. It stops them at the timeout instead:
A command that starts with
sleep
.
A command that runs
git
anywhere in it.
A compound command Claude Code can’t fully parse into simple commands. Claude Code treats a parameter expansion such as
${VAR}
as unparseable, so it stops a command that ends in
; exit "${PIPESTATUS[0]}"
at the timeout even when the rest of that command parses.
The result of a command moved to the background states what happened:
When the timeout triggers the move, the result reports it explicitly:
Command did not complete within its 120s timeout and was moved to the background
, with the seconds matching the timeout that applied, followed by the task ID and the path of the file the output is being written to.
A
cd
,
pushd
,
popd
, or
chdir
inside a command that is moved to the background never carries over: the result states
Session cwd remains <dir>; directory changes made by the backgrounded command do not apply to subsequent commands.
, so Claude doesn’t act on a directory change that didn’t happen.
​
Memory limit on Linux and WSL
On Linux and WSL, set
CLAUDE_CODE_TOOL_MEMORY_LIMIT
to a size such as
4G
to cap the memory that Bash, PowerShell, and
Monitor
tool commands can use, so one runaway build can’t take the memory the rest of the session needs. Requires Claude Code v2.1.233 or later. Before v2.1.246, Monitor tool commands ran outside the cap.
Write the size as a number of bytes or with a
K
,
M
,
G
, or
T
suffix. Set
0
,
off
,
false
,
no
, or
none
to turn the cap off. Claude Code ignores any other value it can’t read as a size, such as
4e9
.
Claude Code counts all of a session’s Bash, PowerShell, and Monitor commands against the one cap, not each command on its own.
Claude Code applies the cap with a memory cgroup. When it can’t set the cgroup up, commands run without a cap, and the debug log from
claude --debug
says why.
After the first process Claude Code starts has turned the cap on, or has turned it off because of an off value or a failed cgroup setup, Claude Code holds that result until you relaunch. To apply a changed or removed value, or a fixed setup, launch
claude
again.
When commands can’t stay under the cap, the kernel kills a command, and nothing in its result names the cap.
Claude Code can also count other kinds of processes it starts against the same limit. Set
CLAUDE_CODE_TOOL_MEMORY_CGROUP_EXCLUDE
to a comma-separated list of the kinds to exempt from the cap; Claude Code applies the cap to every kind not on your list. Set it to
none
to cap every kind, or to
all-new
to cap only Bash, PowerShell, and Monitor tool commands. Requires Claude Code v2.1.246 or later. The kinds you can name:
mcp
: local
MCP servers
lsp
:
language servers
hooks
:
hook
commands
plugin
: commands that
plugins
run
helper
: Claude Code’s own helper commands, such as
git
agent
: child Claude Code processes, such as
agent teammates
Whatever you list, these rules apply:
Unknown names
: Claude Code ignores names it doesn’t recognize
Bash, PowerShell, and Monitor
: Claude Code keeps Bash, PowerShell, and Monitor tool commands under the cap whatever you list
Variable unset
: Claude Code takes the set of other capped kinds from configuration Anthropic delivers from the server, and that set can change over time, so set the variable when you need a set that doesn’t change
Permission-gating hooks
: even with every kind capped, Claude Code excludes from the cap a hook that can block or change the outcome of an action, and any MCP server that such a hook calls, so the kernel killing a permission-gating hook can’t allow the action it was blocking
​
Edit tool behavior
The Edit tool performs exact string replacement. It takes an
old_string
and a
new_string
and replaces the first with the second. It doesn’t use regex or fuzzy matching.
Three checks must pass for an edit to apply. Before any of them, a path matched by a
Read
deny rule
is refused, including creating a new file there. The refusal requires Claude Code v2.1.208 or later.
Read-before-edit
: Claude reads the file in the current conversation before editing it, and a read cut short with a
PARTIAL view
notice
doesn’t count. Claude Opus 4.6, Claude Haiku 4.5, and older models always require the read. Newer models can edit an unread file when reading it wouldn’t need a permission prompt and the Read tool is available.
Match
:
old_string
must appear in the file exactly as written. A single character of whitespace or indentation difference is enough to miss.
Uniqueness
:
old_string
must appear exactly once. When it appears more than once, Claude either supplies a longer string with enough surrounding context to pin down one occurrence, or sets
replace_all: true
to replace them all.
A file that changed on disk after Claude last read it can still be edited when
old_string
matches the current content exactly and unambiguously and Claude Code can read the file without prompting. Matching against the file’s current content keeps this safe, and the result notes that the file carries other changes so Claude re-reads it before edits that depend on surrounding content. In any other case, such as a stale
old_string
or one that matches more than once without
replace_all
, Claude reads the file again before editing. The relaxed handling of unread and changed files requires Claude Code v2.1.208 or later; before that, Claude Code refused any edit to a file it hadn’t read in the conversation or that changed on disk after the read.
Viewing a file with Bash also satisfies the read-before-edit requirement when the command is
cat
,
nl
,
bat
,
batcat
,
head
,
tail
,
sed -n 'X,Yp'
,
grep
,
egrep
,
fgrep
, or
rg
on a single file with no pipes or redirects. Piped output and other Bash commands don’t count toward the read-before-edit check.
This affects edit eligibility only, not permissions.
Read and Edit deny rules
also apply to file commands Claude Code recognizes in Bash, such as
cat
,
head
,
tail
,
sed
, and
grep
, but not to arbitrary subprocesses that read or write files indirectly, like a Python or Node script that opens files itself. The set of commands recognized for deny rules is not the same as the read-before-edit list above: for example,
egrep
and
fgrep
count for read-before-edit but are not checked against Read deny rules. For OS-level enforcement that covers every process,
enable the sandbox
.
​
EndConversation tool behavior
The EndConversation tool ends the current session. Claude uses it only in two situations:
as a last resort against sustained abusive input, after attempts to redirect the conversation have failed and after a clear warning in an earlier message
when you explicitly ask to see the tool demonstrated and confirm that you want the session to end
General frustration, profanity, or a task going badly don’t qualify, and neither do requests for harmful content, which Claude declines instead of ending the session. Claude Code follows the same approach as claude.ai, which can
end a rare subset of chats
.
After Claude ends an interactive session, the session locks. New prompts and most commands return
Claude ended this conversation. Start a new session (or /clear) to continue.
, and only
/clear
,
/resume
,
/help
,
/exit
, and
/feedback
still run. Claude Code records the end in the session’s transcript, so resuming an ended session restores the lock; the session’s history isn’t deleted.
Resuming an ended session in
non-interactive mode
with the
-p
flag errors and exits with code 1, so a script doesn’t read the ended run as a success.
The tool never prompts for permission, and
PreToolUse hooks
don’t run for it. While any other tool remains, you can’t block it either:
deny and ask rules
naming
EndConversation
have no effect, and neither
--disallowedTools
nor a
--tools
list can remove it. The exemption is deliberate: the tool does nothing except end the conversation, never reading or modifying files or data, and a safeguard of this kind holds only if the session it applies to can’t turn it off. When your deny rules remove every other tool and also match
EndConversation
, as
"*"
does, Claude Code removes it too rather than leaving it as the only tool, unless an allow rule names
EndConversation
explicitly. A deny list that removes every other tool without matching
EndConversation
leaves it in place.
Subagents
never get the tool. Background tasks that share the main conversation’s tool list see it, but calling it there ends nothing.
The tool appears only when all of the following hold:
Version
: Claude Code v2.1.213 or later.
Model
: the session’s model is Claude Opus 4.8, Claude Sonnet 5, Claude Fable 5, or a later version of one of those families.
Surface
: an interactive terminal session, including a
claude
session in an IDE’s integrated terminal, which is how the
JetBrains plugin
runs it. Other surfaces don’t include the tool, such as:
non-interactive
-p
runs
sessions through the
Agent SDK
TypeScript and Python packages
the
VS Code extension
panel, which bundles its own CLI
GitHub Actions
Claude Code on the web
Startup mode
: not a
--bare
session. Bare mode loads only shell and file tools, so the tool is never registered there.
Provider
: not available on
Amazon Bedrock
,
Claude Platform on AWS
,
Google Cloud’s Agent Platform
, or
Microsoft Foundry
, or on sessions signed in through a
cloud gateway
.
​
Glob tool behavior
The Glob tool finds files by name pattern. It supports standard glob syntax including
**
for recursive directory matching:
**/*.js
matches all
.js
files at any depth
src/**/*.ts
matches all
.ts
files under
src/
*.{json,yaml}
matches
.json
and
.yaml
files in the current directory
Results are sorted by modification time and capped at 100 files. If the cap is hit, Claude sees a truncation flag in the result and can narrow the pattern.
Glob doesn’t respect
.gitignore
by default, so it finds gitignored files alongside tracked ones. This differs from
Grep
, which skips gitignored files. To make Glob respect
.gitignore
, set
CLAUDE_CODE_GLOB_NO_IGNORE=false
before launching Claude Code.
A
pattern
or
path
value that contains a null byte returns an error asking Claude to remove it.
​
Grep tool behavior
The Grep tool searches file contents for patterns. Where
Glob
finds files by name, Grep finds lines inside them.
Grep is built on
ripgrep
and uses ripgrep’s regex syntax, not POSIX grep. Patterns that include regex metacharacters need escaping. For example, finding
interface{}
in Go code takes the pattern
interface\{\}
.
A pattern, glob, or file type that ripgrep rejects returns an error that includes ripgrep’s diagnostic, so Claude can correct the input and search again. Before v2.1.208, Claude Code reported a rejected input as
No files found
instead of an error, even when the searched-for text existed in the target files.
Three output modes control what comes back:
files_with_matches
: file paths only, no line content. This is the default.
content
: matching lines with file and line number. When the tool’s
offset
parameter points past the last match for a pattern that has matches, Grep returns
No entries at this offset
, so Claude widens or resets the offset instead of concluding the pattern doesn’t match.
count
: match count per file, followed by a total across all matching files. The total covers every match even when the tool’s
head_limit
or
offset
parameters truncate the listed per-file entries. Before v2.1.208, the total only summed the listed entries.
Claude can scope results by file with the
glob
parameter, such as
**/*.tsx
, or by language with the
type
parameter, such as
py
or
rust
. By default, patterns match within a single line. Claude can set
multiline: true
to match across line boundaries.
Grep respects
.gitignore
, so gitignored files are skipped. To search a gitignored file, Claude passes its path directly.
​
LSP tool behavior
The LSP tool gives Claude code intelligence from a running language server. After each file edit, it automatically reports type errors and warnings so Claude can fix issues without a separate build step. Claude can also call it directly to navigate code:
Jump to a symbol’s definition
Find all references to a symbol
Get type information at a position
List symbols in a file
Search for a symbol by name across the workspace
Find implementations of an interface
Trace call hierarchies
Claude Code keeps the tool inactive until you install a
code intelligence plugin
for your language. In
cloud sessions
, Claude Code doesn’t start plugin language servers, so the LSP tool stays inactive there. Claude Code takes the language server’s configuration from the plugin, and you install the server binary yourself.
Claude Code returns an error result for each LSP call on a file whose language server it can’t start.
​
Monitor tool
The Monitor tool lets Claude watch something in the background and react when it changes, without pausing the conversation. Ask Claude to:
Tail a log file and flag errors as they appear
Poll a PR or CI job and report when its status changes
Watch a directory for file changes
Track output from any long-running script you point it at
Connect to a WebSocket feed and report each message as it arrives
For most watches, Claude writes a small script, runs it in the background, and receives each output line as it arrives. For a server that already pushes events, Claude can open a
WebSocket
instead of running a script.
You keep working in the same session and Claude interjects when an event arrives. Stop a monitor by asking Claude to cancel it or by ending the session.
When Monitor runs a command, it uses the same
permission rules as Bash
, so
allow
and
deny
patterns you have set for Bash apply here too. While
auto mode
is active, Claude Code sets aside allow rules that name
Monitor
itself, along with the other
broad allow rules it drops
, so the classifier reviews Monitor commands the same way it reviews Bash commands.
The
WebSocket source
has its own approval prompt, which the classifier also decides in auto mode.
The tool is not available on Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry. It is also not available when
DISABLE_TELEMETRY
or
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
is set.
Plugins can declare monitors that start automatically when the plugin is active, instead of asking Claude to start them. See
plugin monitors
.
​
WebSocket source
The WebSocket source requires Claude Code v2.1.195 or later.
When a server already pushes events over a WebSocket, Claude can connect to it directly instead of writing a polling script. Each kind of socket activity either becomes an event or ends the watch:
Text messages
: each one becomes one event, even when the message spans multiple lines.
Binary messages
: not passed through. Claude receives a placeholder line such as
[binary frame, 512 bytes]
instead.
Messages larger than 1 MiB
: the watch ends, so subscribe to a filtered feed where one exists.
Socket close
: the watch ends and Claude receives the close code.
A WebSocket watch takes a
ws
input in place of
command
, and a single Monitor call can’t combine the two. The
ws
input has two fields:
Field
Required
Description
url
Yes
The endpoint to connect to. Must be a
ws://
or
wss://
URL with no embedded credentials or whitespace, using ASCII characters only
protocols
No
WebSocket subprotocol names to offer during the handshake. Each entry must be a valid subprotocol token, and the list can’t contain duplicates
The
timeout_ms
and
persistent
inputs behave the same as they do for a command: the watch ends at the deadline unless
persistent
is set, and
TaskStop
cancels it early.
Opening a WebSocket prompts for approval; in
auto mode
the classifier decides instead. The prompt doesn’t offer an option to skip future prompts for the same host.
Claude Code denies URLs that point at a private, link-local, or cloud-metadata address, including hostnames that resolve to one. It also denies hosts in
sandbox.network.deniedDomains
, and when
allowManagedDomainsOnly
is set in managed settings, any host outside the managed allowlist.
​
NotebookEdit tool behavior
NotebookEdit modifies a Jupyter notebook one cell at a time, targeting cells by their
cell_id
. It doesn’t perform string replacement across the notebook the way
Edit
does on plain files.
Three edit modes control what happens to the target cell:
replace
: overwrite the cell’s source. This is the default.
insert
: add a new cell after the target. With no
cell_id
, the new cell goes at the start of the notebook. Requires
cell_type
set to
code
or
markdown
.
delete
: remove the target cell.
Permission rules use the
Edit(...)
path format. A rule like
Edit(notebooks/**)
covers NotebookEdit calls on files in that directory.
​
PowerShell tool
The PowerShell tool lets Claude run PowerShell commands natively. On Windows, this means commands run in PowerShell instead of routing through Git Bash. How the tool becomes available depends on your platform:
Windows without Git Bash
: the tool is enabled automatically.
Windows with Git Bash installed
: the tool is on by default for claude.ai and Console accounts; set
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
to enable it in Amazon Bedrock, Google Cloud’s Agent Platform, and Microsoft Foundry sessions, or
0
to turn it off.
Linux, macOS, and WSL
: the tool is opt-in.
Your
PreToolUse hooks
receive the tool’s command string in
tool_input.command
, with the same fields as the Bash tool.
Match
Bash|PowerShell
in hooks that inspect shell commands; the
PowerShell hook input section
explains why matching
Bash
alone is not enough.
​
Enable the PowerShell tool
Set
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
in your environment or in
settings.json
:
{
"env"
: {
"CLAUDE_CODE_USE_POWERSHELL_TOOL"
:
"1"
}
}
On Windows, set the variable to
0
to turn the tool off. On Linux, macOS, and WSL, the tool requires PowerShell 7 or later: install
pwsh
and ensure it is on your
PATH
.
On Windows, Claude Code auto-detects
pwsh.exe
for PowerShell 7+ with a fallback to
powershell.exe
for PowerShell 5.1. When the tool is enabled, Claude treats PowerShell as the primary shell. The Bash tool remains available for POSIX scripts when Git Bash is installed.
Claude Code spawns PowerShell with
-ExecutionPolicy Bypass
at process scope only, so
.ps1
scripts and module imports work on default Windows installs without changing the machine’s policy. Process-scope bypass doesn’t override Group Policy
MachinePolicy
or
UserPolicy
, so enterprise policies still apply. To respect the machine’s effective execution policy instead, set
CLAUDE_CODE_POWERSHELL_RESPECT_EXECUTION_POLICY=1
.
​
Shell selection in settings, hooks, and skills
Three additional settings control where PowerShell is used:
"defaultShell": "powershell"
in
settings.json
: routes interactive
!
commands through PowerShell. Requires the PowerShell tool to be enabled.
"shell": "powershell"
on individual
command hooks
: runs that hook in PowerShell. Hooks spawn PowerShell directly, so this works regardless of
CLAUDE_CODE_USE_POWERSHELL_TOOL
.
shell: powershell
in
skill frontmatter
: runs
!`command`
blocks in PowerShell. Requires the PowerShell tool to be enabled.
The same main-session working-directory reset behavior described under the Bash tool section applies to PowerShell commands, including the
CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR
environment variable.
As of v2.1.196, exit code 1 from
grep
,
rg
,
egrep
,
fgrep
,
findstr
, and
git grep
means no matches. Exit code 1 from
git diff
means differences exist. Neither result is reported to Claude as a command failure. For
robocopy
, exit codes 0 through 7 are informational results, such as files copied or extra files detected. Exit codes of 8 or higher count as failures.
​
Windows encoding and exit codes
On Windows, the following PowerShell encoding and exit-code behaviors require Claude Code v2.1.214 or later:
Redirection with
>
and
>>
writes UTF-8 files on PowerShell 5.1
Claude Code encodes text piped to a native command’s standard input as UTF-8
Claude Code captures error output without ANSI escape sequences
A command whose child process waits on standard input receives end-of-file instead of hanging
Exit code 1 from
where.exe
means no match, and from
fc.exe
and
diff.exe
it means the files differ, so when the command produces output, Claude Code treats that exit code as a valid negative answer rather than a command error. Claude Code still reports a silenced form, such as
where.exe /Q
or a redirect to
$null
, as a failure on exit code 1
Before v2.1.214,
>
on PowerShell 5.1 wrote UTF-16LE files, non-ASCII piped input arrived as
?
, and Python scripts could crash with a
UnicodeEncodeError
when printing non-ASCII characters.
​
Preview limitations
The PowerShell tool has the following known limitations during the preview:
PowerShell profiles are not loaded
On Windows, sandboxing is not supported
​
Read tool behavior
The Read tool takes a file path and returns the contents with line numbers. Claude is instructed to always pass absolute paths.
By default, Read returns the file from the start. When a whole-file read exceeds the token limit, Read returns the first page with a
PARTIAL view
notice that tells Claude how much of the file it received and how to read more with
offset
and
limit
. A read that passes an explicit
offset
or
limit
and still exceeds the token limit returns an error.
A read with an explicit
limit
stops as soon as the selected lines exceed what the token limit could ever fit and returns an error without loading the rest of the range. The error tells Claude to use a smaller
limit
, or to search for specific content with
Grep
instead when a single line is that large. Before v2.1.208, Claude Code loaded the whole range into memory before rejecting it, so reading a file with an extremely long single line could run it out of memory.
Reading an empty file returns a notice that the file exists but its contents are empty, and an
offset
past the last line returns a notice giving the file’s line count. Before v2.1.208, reading an empty file returned the past-the-end notice instead.
Read handles several file types beyond plain text:
Images
: PNG, JPG, and other image formats are returned as visual content that Claude can see, not as raw bytes. Claude Code resizes and recompresses large images to fit the model’s image size limits before sending them, so Claude may see a downscaled version of a large screenshot. As of v2.1.196, an image that is still larger than 500KB after that resize is re-encoded as a JPEG at reduced quality with its pixel dimensions unchanged. If Claude misses fine pixel-level detail in a large image, ask it to crop the region of interest first, for example with ImageMagick via Bash.
PDFs
: Claude reads short
.pdf
files whole. For PDFs longer than 10 pages, it reads in ranges with a
pages
parameter, such as
"1-5"
, up to 20 pages at a time.
Jupyter notebooks
:
.ipynb
files return all cells with their outputs, including code, markdown, and visualizations. Claude Code refuses to read a notebook file over 100 MB; the error tells Claude how to read a portion of the notebook instead, such as a slice of cells, with a shell command.
Read only reads files, not directories. Claude lists directory contents with a shell command such as
ls
.
​
SendFeedback tool behavior
Claude-drafted feedback is a feedback report about Claude Code that Claude writes for you. It requires Claude Code v2.1.238 or later. Claude Code saves each draft on your machine under
~/.claude/feedback/drafts/
, and nothing reaches Anthropic until you send it. Claude drafts one with the SendFeedback tool when:
A tool or command keeps failing
It can’t help with something you asked for
You point out a mistake it made, or it notices one
You ask it to file feedback
​
What you see when Claude drafts
After Claude queues a draft, you see a card above your prompt with the draft’s title. Press
1
to review the draft, press
2
twice to send it as written, or press
0
to dismiss it. A dismissed draft stays in your queue. After you dismiss a card, Claude Code asks whether to turn Claude-drafted feedback off. It stops asking once you’ve declined twice.
By default, you see at most three cards in a session; Anthropic can adjust that limit from the server without a release. After the limit, and whenever you set
feedbackDrafts
to
quiet
, you see only a count of queued drafts in the prompt footer.
​
Review and edit a draft
Run
/feedback
with no argument to open your queue. It lists every queued draft from all your sessions, including drafts whose cards you dismissed or never saw. Select a draft to open it for review, where you can:
Edit the title, area, and details
Set
Send transcript
to
yes
or
no
. When the transcript from the session where Claude queued the draft is still available, it starts at
yes
, which sends that conversation to Anthropic;
no
sends the report only
Send the draft, discard it, or leave it in the queue for later
To write a report yourself instead, press
w
for the standard feedback dialog.
/feedback
with text after it, and
/bug
, open that dialog directly.
​
Send a draft
When you send a draft, Claude Code submits it the same way as a
/feedback
report, with the same
retention
, and deletes the draft from your machine. When you send from the card, it shows
✓ Sent
; when you send from the queue, it closes with a receipt ID.
The report carries:
Your title, area, and details
Environment info, such as your Claude Code version, operating system, and model
The IDs of recent API requests
The conversation transcript, when you left
Send transcript
at
yes
in the review screen. Sending from the card never includes the transcript
Claude Code keeps your working directory in the local draft so it can find the transcript, and doesn’t send the directory.
In
organizations with zero data retention
, Claude Code leaves the tool out, as it does for
/feedback
. If a session in such an organization still offers the tool, drafts stay on your machine, and sending fails with
Feedback collection is not available for organizations with custom data retention policies.
​
Discard or keep a draft
When you discard a draft, Claude Code deletes it from your machine. A draft you leave in the queue expires after 30 days, or after
cleanupPeriodDays
when that’s shorter. The queue holds 10 drafts across all your sessions, and when Claude queues an eleventh, Claude Code deletes the oldest. When you run
/exit
with drafts from the session still in the queue, Claude Code asks whether to review them or discard them before exiting.
​
Turn Claude-drafted feedback off
Set
Claude-drafted feedback
to
off
in
/config
, which writes the
feedbackDrafts
setting, or set
CLAUDE_CODE_SEND_FEEDBACK=0
for one session. With either, Claude can’t queue drafts. To keep drafting on without cards, set
feedbackDrafts
to
quiet
instead. Administrators can set
feedbackDrafts
in
managed settings
, which takes precedence over your own setting.
​
Sessions without Claude-drafted feedback
Claude Code includes the tool in interactive terminal sessions on your own machine that use the Claude API rather than a cloud provider. It leaves the tool out of:
Non-interactive
-p
runs and
Agent SDK
sessions, which have no screen to review the queue on
Cloud sessions such as
Claude Code on the web
, which can’t write to the queue on your machine
Sessions on
Amazon Bedrock
,
Claude Platform on AWS
,
Google Cloud’s Agent Platform
, or
Microsoft Foundry
Sessions where you set
CLAUDE_CODE_SEND_FEEDBACK=0
or
DISABLE_FEEDBACK_COMMAND=1
, set
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
to any non-empty value, or turned off
feature-flag fetching
Organizations that have turned off product feedback, and
organizations with zero data retention
​
Task tool availability
In Claude Code v2.1.233 and later, the following tools aren’t avai

## Source (changelog): https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md

# Changelog

## 2.1.251

- Added `PreModelSwitch` and `PostModelSwitch` hook events (block, confirm, or annotate a model switch); `SessionStart` resume hooks now receive session staleness and the estimated re-cache cost
- Added live streaming of a foreground subagent's tool calls and results to Remote Control clients (background subagents, the default, still show status only)
- Added a Spend limit bar to `/usage` and a `rate_limits.spend_limit` status line field for developers behind a Claude apps gateway with spend limits
- Added a per-session prompt-cache line to `/cost` (hit ratio, misses, tokens re-cached, warm/cold) and a matching `prompt_cache` object for status line scripts
- Added `attach`, `logs`, `stop`, `respawn`, and `rm` to `claude --help`; the `--resume` message for a running background session now names the exact `claude attach
` command
- Fixed file tools (Read, Write, Edit) following a symlink swapped inside the working directory after the permission check, which could read or write outside the approved location
- Fixed plugin commands declared in a marketplace entry being able to point outside the plugin directory; such paths are now rejected with a path-traversal error
- Fixed project settings being able to enable detailed beta tracing or raw API body logging, and a lower-scope beta tracing endpoint bypassing an OTLP collector pinned by managed settings or a host app
- Fixed the Workflow tool reading (and quoting in errors) a `scriptPath` outside what the session may read before the permission check ran
- Fixed Grep and Glob not applying `Read(...)` deny rules to files reached through a symlinked search path
- Fixed conversations getting stuck on "text content blocks must be non-empty" errors after a turn where the model produced only thinking
- Fixed the first launch on a fresh install starting in default mode instead of auto mode for accounts whose startup default is auto mode
- Fixed Opus 5 requests failing with "effort … is not supported when thinking is disabled" when effort was xhigh/max and thinking was turned off; effort is now sent as `high` in that case
- Fixed replying to a message Claude Desktop delivered from another session: `SendMessage` to that session id now delivers through Claude Desktop instead of failing with "not reachable"
- Fixed TUI lag with many parallel subagents: per-second progress ticks now replace their predecessor instead of piling up in the transcript
- Fixed agent teams: a teammate's final answer not reaching the team lead — it now arrives in the idle notification instead of a content-free "available" notice
- Fixed background subagents being unable to reply to a message from an unnamed sibling or parent agent (`from` was the agent type, which is not an address)
- Fixed managed-settings `disableAutoMode` arriving mid-session not moving an already-running auto-mode session back to default mode
- Fixed a "switch to Opus 1M for 5x more context" tip that appeared even when the current Opus model already has a 1M context window
- Fixed Claude apps gateway sessions treating a stored Anthropic profile (e.g. a Console sign-in) as active: listing it in `/status` and retrying gateway 401s with it, though requests never use it
- Fixed cloud sessions telling Claude the model had changed when the host was only setting the session's initial model
- Fixed Remote Control reporting a failure when an organization's policy disables it; it now shows a single quiet notice instead
- Fixed `/mcp reconnect` on Remote Control showing a generic withheld-detail error instead of the real remedy when a server was disabled in another session
- Fixed `--input-format stream-json`: client-injected assistant tool calls sent without a message id were merged into the first one and their results lost, including when resuming older sessions
- Fixed session transcripts being silently overwritten when a directory change relocated a session onto an existing same-ID transcript
- Fixed background sessions and their subagents being unable to edit files inside a git worktree they created with `git worktree add`
- Fixed background sessions occasionally starting without any plugin skills (and staying that way) when another Claude Code process was refreshing the plugin marketplace at the same moment
- Fixed selecting text in an opened background session inside tmux over SSH: it now copies to the tmux buffer like a foreground session instead of falling back to OSC 52
- Fixed SDK and cloud sessions hanging indefinitely when an SDK MCP server's handshake acknowledgment was lost; the wait now times out after 70 seconds and marks only that server failed
- Fixed self-hosted runner leaving a stuck session's Bash tool processes running after the session was force-stopped
- Fixed `/usage-credits` for Team and Enterprise members whose admin set the org's usage-credit limit to $0: it now offers to ask the admin instead of saying a cap was reached
- Fixed `--worktree --tmux` with a merge-request number on a gitlab.com origin trying a doomed GitHub-style fetch first instead of fetching the GitLab ref directly
- Fixed Ctrl+G failing with "Emacs quit unexpectedly" in background sessions for editors that open `/dev/tty`, such as `emacs -nw` and `micro`
- Fixed an `additionalDirectories` entry containing a null byte crashing startup, or breaking `/add-dir` and later settings updates when it came from an SDK host, IDE, or hook; it is now skipped
- Fixed the MCP server menu's copy shortcut: it now says how the sign-in URL was copied instead of always claiming success
- Fixed italic text (such as the session recap line) rendering as highlighted blocks in GNU screen and in tmux sessions using a `screen` terminal type
- Fixed `claude mcp add --header` and `claude mcp add-json` help text naming the wrong transports
- Fixed `claude ultrareview` and `/ultrareview` waiting the full 30 minutes when the cloud session fails to start; they now stop early and report the reason
- Fixed Bash permission checks auto-approving commands that assign an arithmetic expression to an integer shell variable (e.g. `OPTIND=1/0`, `RANDOM=2+2`); these now prompt for approval
- Fixed backgrounded sessions (`←`, `/background`, `--bg`) losing a Vertex/Bedrock gateway (`ANTHROPIC_*_BASE_URL` + `CLAUDE_CODE_SKIP_*_AUTH`) exported in the shell, so every request failed
- Fixed `claude --bg --model fable` on Max plans stopping to ask for usage credits while the interactive session on the same account still had Fable allowance
- Fixed the one-time "make auto mode your default" offer appearing in unattended sessions (e.g. agent-team teammate panes), where a stray keypress could accept it unread
- Fixed the managed-settings approval prompt re-appearing after signing in again to the same Claude apps gateway when the settings are unchanged
- Fixed disabled `/bug` and `/share` reporting that `/feedback` was disabled; tips, `/help`, and refusal messages no longer suggest `/feedback` when an org policy or env var turns it off
- Fixed cloud session creation advising GitHub setup after a transient GitHub connection failure — the message now says to retry instead
- Improved CPU usage during turns in interactive sessions by cutting redundant UI re-renders
- Improved install size: the native binary is about 5 MB smaller
- Improved cloud sessions: when the session's network proxy drops a connection during a Bash command, the tool result now names the host and reason instead of only "connection reset"
- Improved `/schedule` to explain that MCP servers configured in Claude Code can't be attached to cloud routines, instead of a bare "No MCP connectors" message
- Improved framing of messages from your own subagents: Claude is told the sender is a worker inside this session, not an unrelated Claude session
- Improved the prompt placeholder to read "Message @name…" while viewing a background subagent or fork transcript opened from the subagent panel or `/tasks`
- Improved sanitization of MCP server names in error messages, menus, and command results
- Improved Amazon Bedrock session start under `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` (e.g. Claude Desktop): a session given a Bedrock model ID or ARN no longer waits for inference-profile discovery
- Improved the managed settings approval dialog to list only the settings that changed since you last approved them
- Improved retry when the model's tool call is malformed: the broken output is now dropped from the retry context, including on Bedrock, Vertex, and Foundry
- Changed `/radio` to be available on Bedrock, Vertex AI, Foundry, and Claude Platform on AWS, and when telemetry is disabled
- Changed Claude in Chrome so browser actions always go through Claude Code's permission checks, including in sessions with telemetry disabled, which previously used the Chrome extension's own prompts
- Changed `CLAUDE_CODE_SUBAGENT_MODEL` to set the default subagent model rather than override everything: an agent definition's `model:` and an explicit per-spawn model now take precedence over it
- Changed the default commit trailer to `Co-Authored-By: Claude Code` when the active model isn't a recognized Claude model (e.g. third-party models behind a custom `ANTHROPIC_BASE_URL`)
- Changed the default model for seat-based Enterprise subscriptions to Opus 5, matching other premium plans
- Changed `/effort` to save your default effort level per model, so each model keeps its own setting when you switch
- Changed analytics to no longer turn off before sign-in solely because managed settings force gateway login (or cannot be read); they stay off once signed in to the gateway or via `DISABLE_TELEMETRY`
- Changed the footer PR badge on Bedrock, Vertex, and Foundry, and when telemetry is off, to call the GitHub API directly (via `gh auth token`, `GH_TOKEN`, or `GITHUB_TOKEN`) instead of `gh pr view`
- Changed how Bash command output files are created and read back when commands run in the sandbox, so a sandboxed command cannot redirect or replace them
- Changed plugin/LSP install suggestions and the auto-mode default offer to wait until you've sent or cleared what you're typing, so the Enter that sends your prompt can't answer them
- Changed server-managed settings that terminate sandbox TLS, route sandbox traffic through your own proxy, inject credentials, or weaken sandbox isolation to require approval before they apply
- Changed `ANTHROPIC_CUSTOM_HEADERS` from managed or project settings to require approval when it sets a credential, org/tenant, routing, or API-behavior header (e.g. `Authorization`, `Host`)
- Changed project-level `.claude/settings.json` `env` to no longer set `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_TMPDIR`, or `TMPDIR`/`TMP`/`TEMP`; set them in your shell, user, or managed settings instead
- Removed syntax highlighting for six rarely used languages (1c, gml, isbl, mathematica, maxima, sqf); the binary is 2.5 MB smaller
- [VSCode] Fixed the sign-in screen's "Bedrock, Foundry, or Vertex" button opening the docs at the top of the page instead of the third-party provider setup section
- [VSCode] Changed the Remote Control banner to a footer pill (shown while Remote Control is on or has failed) that opens the session on claude.ai/code; turn it on or off with `/remote-control`

## 2.1.250

- Bug fixes and reliability improvements

## 2.1.248

- Added `--restricted` (or `CLAUDE_CODE_RESTRICTED=1`): removes the built-in tools that run commands or code and `WebFetch` (unless named in `--tools`), keeps file tools inside the working directory, refuses `bypassPermissions`, and ignores user, project and local settings files
- Added `experimental.cacheTtl` (`"5m"` or `"1h"`) to agent frontmatter: a per-agent prompt cache TTL used when no subagent TTL setting is configured
- Added `claude self-hosted-runner --client-label
` (or `SELF_HOSTED_RUNNER_CLIENT_LABEL`) to override the label the runner registers with (default: hostname)
- Added server-managed settings diagnostics: a startup warning when the settings fail to load, and a `/doctor` and `/status` line explaining a load failure or why they weren't fetched (Bedrock/Vertex/third-party provider, custom `ANTHROPIC_BASE_URL`)
- Added a warning in `/web-setup` when the GitHub CLI token lacks the `workflow` scope, since pushes to very large repositories can be rejected without it
- Added `/usage-credits` for Enterprise organizations billed through AWS Marketplace, self-serve Enterprise, and Enterprise trials, so members can request a higher usage limit from their admin
- Added cross-session messaging (`SendMessage` / `ListAgents`) between sessions on the same machine on Bedrock, Vertex, and Foundry, and when telemetry is disabled
- Fixed a prompt-cache miss (and lost extended-thinking context) roughly once an hour in long sessions, caused by tool definitions being re-rendered after an OAuth token refresh
- Fixed the `ScheduleWakeup` tool definition changing between a session and its `--resume` when the account had entered usage overage, causing a full prompt-cache miss on the resumed session's first turn
- Fixed Claude Desktop and Cowork sessions disappearing after 30 days: the transcript cleanup now keeps desktop-written sessions while they are in the app (unless org policy manages retention); the new `desktopSessionCleanupPeriodDays` setting caps the exemption
- Fixed being sent to the login screen when another Claude Code process held the token refresh lock while the session token had expired; the request now fails with a retryable error instead
- Windows: Fixed the `claude agents` list not responding to the keyboard after detaching from a session, or when launched in a terminal tab left in win32-input-mode
- Fixed the recommended Console sign-in in `/login` failing with an OAuth error before showing a sign-in URL on machines where it can't be used (for example when `ANTHROPIC_API_KEY` or an API key helper is set); it now falls back to the API-key sign-in
- Fixed model names in `/model` and fast-mode switch notices to render as code, so suffixes like `[1m]` display literally instead of as a link
- Fixed `claude agents` skipping the workspace trust prompt when the `CI` environment variable is set
- Fixed `claude agents` crashing on launch when the PR-status cache held a malformed entry
- Fixed agent view resurrecting a weeks-old background session after the machine was off: such a session now shows as stopped at its real end, and opening it asks before resuming its saved conversation
- Fixed agent view sometimes opening an older conversation, and dropping the typed prompt, when starting a new session
- Fixed `claude agents`: opening a stopped session that you already resumed in another terminal no longer starts a second process on that conversation; the row now says it is open in a terminal
- Fixed `claude agents` and `claude rm` refusing to delete a session ("has commits that are not pushed anywhere") when its worktree branch was already merged into your checked-out default branch (e.g. local `main`) but not yet pushed
- Fixed background sessions waiting silently when a `PermissionRequest` or `PreToolUse` hook prints an invalid answer: the `claude agents` row now names the hook and the schema error
- Fixed hooks silently treating a stdout `{…}` object that isn't valid JSON as plain text; it's now reported as a hook error with the parse message
- Fixed `/mcp` listing a project `.mcp.json` entry that declares the claude.ai connector type under the trusted "claude.ai" heading; it now appears under its real scope
- Fixed MCP servers whose `headersHelper` supplies the `Authorization` header falling into OAuth discovery on a 401 instead of re-running the helper and retrying the call as documented
- Fixed `/login` to a Claude apps gateway hanging when the managed-settings security approval dialog was required
- Fixed gateway model discovery (`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY`) never running when `apiKeyHelper` is the only credential
- Fixed `claude logs` leaving mouse tracking, bracketed paste and the alternate screen switched on in the terminal it was run from
- Fixed the trust dialog's list of repo permission rules showing a garbled character when a long rule was cut off in the middle of an emoji
- Fixed the permission mode indicator staying hidden behind the "Press Ctrl-C again to exit" hint when you press shift+tab right after ctrl+c
- Fixed `/ultrareview` and locally seeded cloud sessions uploading uncommitted edits to `prod.env`-style and `*.tfvars` files, or to editor swap, temp, and backup copies of credential files (e.g. `key.pem.tmp`, `id_rsa.swo`); they now stay on your machine
- Fixed Remote Control sessions occasionally never showing a permission prompt or the latest messages on the connected device after the CLI silently reconnected
- Fixed cloud sessions occasionally failing at startup when the container's session credentials were not yet readable
- Fixed `claude remote-control` rejecting its own flags (e.g. `--spawn`, `--name`) when a global flag or a wrapper-injected option precedes the subcommand
- Fixed startup warnings (e.g. "N MCP servers need authentication") rendering one column right of the rest of the transcript
- Fixed a backgrounded worktree session losing its checkout: the background session now holds the worktree's lock while it runs, so cleanup and `git worktree remove` leave it alone
- Fixed @-mentions of other sessions not matching names typed with non-Latin characters (for example Korean entered through an IME)
- Fixed an invalid `crossSessionInbound` value being silently ignored: it now warns and holds cross-session messages (user settings) or refuses them (managed settings) until fixed
- Fixed rate-limit, usage, and fast-mode messages telling you to run `/usage-credits` when that command isn't available for your organization (e.g. hidden with `DISABLE_EXTRA_USAGE_COMMAND`)
- [VSCode] Fixed a chat tab getting stuck on "No conversation found" when its session was never saved; it now starts a new conversation instead
- Improved the Workflow tool's prompt footprint: its description is now about 1k tokens instead of 5.7k, with the script-writing reference moved into a bundled `workflow-authoring` skill
- Improved the prompt-footer PR badge to check GitHub less often while the pull request is unchanged; a push or a `gh pr` command still refreshes it right away
- Improved managed settings: client-side timeout, MCP startup-mode, and stream-watchdog env vars no longer trigger the settings-approval prompt
- Improved `/ultrareview
` to check before launch that the GitHub account connected to your Claude account can access the repository, and to explain how to fix it, instead of failing after the cloud session starts
- Improved cross-session messaging: falls back to a private per-user `/tmp` directory when the default one can't be used, and the notice and `/status` name the directory to fix
- Changed shift+enter in the agent view dispatch input to insert a newline (matching the prompt); ctrl+enter now dispatches and attaches
- Changed `/loop`: self-paced dynamic mode and the no-prompt autonomous default are now always available, including on Bedrock/Vertex/Foundry
- Changed Anthropic telemetry export failures to log at debug level as `[Anthropic telemetry]` instead of `[3P telemetry] OTEL diag error`, so they are not mistaken for your OTel collector failing
- Changed cross-session messaging in Linux user namespaces: root-equivalent trust for unmapped owners is limited to canonical system directories
- Changed `SendMessage` from a subagent to another session: the result now notes that any reply is delivered to the parent session's conversation, not to the subagent

## 2.1.247

- Added the `SendFeedback` tool: when something goes wrong in a session, Claude can draft a feedback report for you to review and send from `/feedback` (turn off with the `feedbackDrafts` setting)
- Added `{id, text, cooldownSessions, priority}` entries, `tipsFile`, and `label` to `spinnerTipsOverride`, so organizations can rotate their own tips alongside the built-in ones
- Added a tip on Bash permission prompts pointing to auto mode, with a one-keystroke "Yes, and switch to auto mode" option
- Added `/claude-api cost-optimize` to profile an existing project's Claude API spend and work through cost levers (caching, token hygiene, batch, effort, model choice) one measured change at a time
- Updated the `/claude-api` skill with Admin API coverage (organization members, invites, workspaces, API keys, rate limit reports, workload identity federation, CMEK)
- Fixed fast arrow-key + Enter sequences acting on the row above the one you navigated to in history search, `/config`, `/mcp`, `/skills`, background tasks, and `/model`
- Fixed sub-agents dying on a first-call model 404: they now use the session's fallback model chain, and the error returned to the parent includes the error type, status, request id, and model
- Fixed a hook or background agent that printed megabytes of error output being able to overflow the conversation and wedge the session on "Prompt is too long"
- Fixed Ctrl keyboard shortcuts not firing under non-Latin (e.g. Cyrillic) keyboard layouts in kitty-protocol terminals
- Fixed text like `
<
35;150;7M` being inserted into the prompt when a mouse report arrived split across reads right after the escape prefix
- Fixed the Bash sandbox's after-command cleanup deleting a dotfile-managed `~/.claude/settings.json` symlink (nix/home-manager, stow) when it is repointed outside the sandbox's writable area
- Fixed `/terminal-setup` overwriting your entire Zed `keymap.json` instead of merging in its keybinding
- Fixed `/rename` silently confirming when the session registry could not be updated; it now says other sessions may still show the old name
- Fixed `/compact` and "Summarize from here" in sessions started with `--agent` summarizing under the default system prompt instead of the conversation's own
- Fixed a background session showing "opening…" forever in `claude agents` after its terminal host process died; the row now fails within seconds with the reason, and Enter restarts it
- Fixed unbounded memory growth when a hook's or background task's output file could not be written; the file now notes where output was lost
- Fixed `/install-github-app` over SSH: the copy shortcut now says how the sign-in URL was copied instead of always claiming success, and the URL appears immediately when no browser can open
- Fixed shell commands carried over from the foreground logging an internal error or showing a misleading `[exited with code -1]` line when they finish in background sessions
- Fixed a version-less marketplace plugin's live cache directory being deleted and recreated on a second-scope install, which could disrupt a running session using it
- Fixed Remote Control sessions started with `/remote-control` not reporting the working-tree diff to connected clients
- Fixed self-hosted runner sessions reporting `running` before Claude Code had started, which could trigger a premature "Claude is waiting for your input" notification from the Claude desktop app
- Fixed first-run setup exiting with "Unable to connect to Anthropic services" when managed settings configure Claude apps gateway sign-in and Anthropic endpoints are unreachable
- Fixed cloud sessions (Claude Code on the web, desktop and mobile apps) sometimes showing the previous permission mode when you switch modes right after sending a message
- Fixed cloud sessions going silent when the session's container restarts between turns while a background agent, shell, or monitor is still running — the resumed session now reports the lost work
- Improved plugin marketplace hardening: names containing control or invisible characters are rejected, and marketplace-supplied text in `/plugin` and `claude plugin` output is escape-safe
- Improved Bedrock, Vertex, and Foundry sessions (and any with telemetry disabled): Claude is now told when a configured MCP server failed to connect, instead of concluding its tools don't exist
- Changed Sonnet 5's default auto-compact window to its full 1M context, so sessions on the 1M window now auto-compact at about 967K tokens instead of about 934K
- Changed cross-session peer messages to collapse by default to a one-line `Message from @
:
` preview; Ctrl+O expands the full body
- Changed terminal hyperlinks in rendered markdown: link targets that point at a network or automounter path, contain a control character, or lead with an invisible character now render as plain text
- Changed the prompt-footer PR badge to skip its GitHub re-check on terminal refocus when the last check is under a minute old
- Changed analytics to stay off from startup, not only after login, when managed settings force gateway login or a custom OAuth deployment is configured
- Changed Claude apps gateway sign-in requests to identify Claude Code (a `surface=claude_code` device-authorization parameter and a `claude-code/
` User-Agent)
- Changed organization sign-in enforcement to exit at start when the administrator's managed settings cannot be read, even if host-supplied or per-user Windows registry settings exist

## 2.1.246

- Added a startup warning for Bash allow rules with a wildcard before the subcommand (e.g. `Bash(git * main)`), since they also match options inserted before the subcommand
- Added an Auto mode tab to `/permissions` for viewing and editing auto mode classifier rules
- Added the turn's completion time to the end-of-turn duration line, e.g. `✻ Sautéed for 23s · done 6:05 PM`
- Fixed fullscreen mode showing a blank transcript after resizing the terminal and jumping to the bottom until the next keypress
- Fixed a severe transcript slowdown when a diff contained a very long single line (e.g. a base64 string); such lines now render truncated with a marker
- Fixed erratic fullscreen scrolling when positioned at an earlier message, including jump-to-bottom getting stuck mid-transcript
- Fixed background sessions failing to open after 45 seconds when Claude Code's starting directory had been deleted, the machine had slept, or the host is slow to start processes
- Fixed background sessions failing to open with "Couldn't start the background service … EACCES" when another Claude Code process was re-installing the npm package at that moment
- Fixed markdown rendering being disabled for a whole message when its first 500 characters contained no markdown, and for `+`/`N)` lists and setext headings
- Fixed MCP tool calls interrupted by an incoming message in headless/remote sessions being reported to the model as "completed with no output" instead of an explicit interrupted error
- Fixed MCP tool arguments being sent as JSON strings when the parameter's schema is empty (`{}`), instead of their real type
- Fixed a command interrupted mid-run showing as "Ran 1 shell command" with no sign it was cut
- Fixed pressing ← or running `/background` during a dynamic workflow restarting its finished subagents; it now asks first and says how many subagents would restart
- Fixed opening a just-started session in `claude agents` while its worker was still booting (common on Windows) stopping it with "was stopped while the respawn was in flight"
- Fixed `claude agents` listing a backgrounded named session twice; backgrounding the same conversation again now numbers the new row (e.g. `my-session (2)`)
- Fixed the background retention sweep removing git worktrees under `.claude/worktrees/` that you created yourself when an old background-session record pointed at them
- Fixed auto mode tool calls being denied as "temporarily unavailable" on very large sessions by scaling the safety-check deadline with prompt size
- Fixed the plugin cache creating duplicate SHA-named directories for the same plugin
- Fixed plugin skills whose frontmatter `name` already includes the `
:` prefix showing it doubled in the slash menu (e.g. `/plugin:plugin:skill`)
- Fixed `claude plugin update` failing for an installed plugin given its bare name (only the fully-qualified name worked)
- Fixed plugin installation failing when `plugin.json` was saved with a UTF-8 byte-order mark (BOM)
- Fixed `/reload-plugins` reporting 0 skills for plugins that define skills under `skills/*/SKILL.md`
- Fixed hook error messages showing a literal `${CLAUDE_PLUGIN_ROOT}` instead of the resolved plugin path
- Fixed `/rename` replacing the theme's prompt border color (including a custom theme's `promptBorder`) with the default cyan; the border now keeps your theme's color unless you pick one with `/color`
- Fixed custom theme diff colors (`diffAdded`/`diffRemoved` and their dimmed variants) being ignored in diffs and the `/theme` preview
- Fixed a `keybindings.json` binding with an unknown action name silently deadening that key; it is now skipped so the default binding keeps working, and a warning is logged under `--debug`
- Fixed `/stats` activity heatmap showing each day's activity one cell off (Sunday's count under Monday) in timezones east of UTC
- Fixed `/fork` from an already-forked or backgrounded session starting the new session with an empty conversation
- Fixed prompts beginning with `/--` (e.g. Lean doc comments) being rejected as an unknown slash command instead of being sent to Claude
- Fixed the `@` file picker staying open after the typed text stopped matching a real path
- Fixed the status line's cost and duration resetting to zero after navigating to the agents view and back
- Fixed fullscreen mode moving keyboard focus onto the control under the pointer when you clicked the terminal window only to bring it back into focus
- Fixed path completion failing when the completion token or working directory contained a null byte
- Windows/macOS: Fixed headless sessions not cleaning up stale entries in `~/.claude/sessions` left by sessions that exited uncleanly
- Fixed the UI stopping with a render error on the first tool call when a third-party Anthropic-compatible endpoint (`ANTHROPIC_BASE_URL`) streams a `tool_use` block without an `id`
- Fixed the Write tool reporting "Out of memory" or freezing for a long time after overwriting a very large existing file, even though the file had been written
- Fixed `claude plugin install
` exiting silently (or hanging in a terminal) instead of reporting an error when `~/.claude/plugins/known_marketplaces.json` is empty or corrupted
- Fixed resumed sessions failing every turn with a 400 when the saved history contains tool blocks the Anthropic API does not accept (typically written by a third-party API proxy)
- Fixed `curl -fsSL https://claude.ai/install.sh | bash` failing with "Raw mode is not supported" for some Team/Enterprise users with server-managed settings
- Fixed sessions that ended in plan mode resuming outside plan mode in the VS Code extension, and in `claude -p --continue`/`--resume` with a permission prompt tool, when no permission mode was set
- Fixed the `Notification` hook not firing while the sandbox "Network request outside of sandbox" permission prompt is waiting
- Fixed Bash permission checks to always require approval for malformed commands with a dangling `&&` or `||` operator
- Fixed `--strict-mcp-config` sessions prompting to approve `.mcp.json` servers they would never load, which left background sessions waiting at startup
- Fixed telemetry and metrics requests to Anthropic carrying the API key configured for a third-party gateway (`ANTHROPIC_BASE_URL`); a credential is now only sent to its own host
- Fixed a visible API error on the first prompt after idle when `apiKeyHelper` returns short-lived JWTs: an expired cached token is now refreshed before sending, and 401/403 auth errors retry quietly
- Fixed memory growing with session length in the fullscreen and Ctrl+O transcript views: each rendered message row no longer retains a full copy of the transcript-wide tool lookups
- Fixed `/ultrareview` runs and cloud sessions launched at the same time from one repository (e.g. from several worktrees) sometimes starting with another launch's uncommitted changes
- Fixed the task progress count (e.g. `3/5`) shown for background cloud sessions such as `/autofix-pr` occasionally missing a task
- Fixed Remote Control sessions keeping their placeholder name in claude.ai and the Claude app until the second prompt; the auto-generated title now appears after the first prompt
- Fixed MCP tools marked `requiresUserInteraction` still offering "Yes, and don't ask again" in their permission prompt; the option wrote an allow rule the tool then ignored
- Fixed the self-hosted runner ending its live sessions or exiting when a work-poll response is malformed (e.g. an intercepting proxy's HTML page); it now retries the poll
- Improved `/cd`: the new directory's project settings, hooks, `.mcp.json` servers (behind the usual approval prompt), skills, and agents now take effect right after the move instead of on `--resume`
- Improved Bash tool latency on bash shells by replaying snapshot functions without a base64 subshell per function
- Improved subagent results: a subagent that stops at its `maxTurns` limit now returns its output marked as partial, with a hint to continue it via `SendMessage`, instead of appearing finished
- Improved non-interactive sessions (`-p`, SDK, cloud sessions) to automatically continue a response cut off mid-stream by a server error, connection loss, or stall instead of ending with an error
- Improved attribution of usage telemetry to your organization for workload identity federation sessions, events sent while `apiKeyHelper` runs at startup, and after a login token expired while idle
- Changed `/code-review` so Claude can also start it on its own on Bedrock, Vertex AI, and Foundry, through the Claude apps gateway, and when telemetry or non-essential traffic is disabled
- `/goal`: Changed idle sessions to start at most three check-ins on long-running background work per goal; your next message allows three more
- Changed `claude install` and `claude update` to defer a pending managed-settings consent prompt to the next interactive session instead of prompting mid-command
- Changed OpenTelemetry plugin events for plugins synced from claude.ai: `plugin_id_hash` now reflects the plugin's real marketplace, and `enabled_via` is `admin-install` for admin-installed plugins
- Fixed the command sandbox's filesystem configuration not respecting `--setting-sources`

## 2.1.245

- Fixed a crash on startup on Linux distributions that ship glibc 2.44 (for example Arch Linux, CachyOS and Fedora Rawhide)

## 2.1.243

- Added a Loops breakdown to `/usage`: per-loop run count, total tokens, tokens per run, and last run, so runaway or chatty `/loop` tasks are easy to spot
- Added `modelPicker` setting: curate the `/model` picker with an ordered, labeled list of models (any id spelling, including Vertex/Bedrock ids), appended to or replacing the built-in lineup
- Added `promptCacheTtl` and `subagentPromptCacheTtl` settings so API-key and cloud-provider users can keep a 1-hour prompt cache on the main conversation while subagents stay at 5 minutes
- Added `modelPricing` managed setting so an organization's contracted per-model rates and discount multiplier are used for `/cost`, the status line, and telemetry cost figures instead of list price
- Added a keyless sign-in under `/login` → Anthropic Console: "Sign in with your Console account" (recommended) alongside creating an API key, so organizations that don't allow API keys can sign in
- Added a `Skipped sources` line to `/status` that lists managed settings sources (for example `managed-settings.json`) present but not applied because a higher-precedence managed source is active
- Added a `managed` marker in `/mcp` and `/plugins` on claude.ai connectors whose authentication is managed by your organization
- Added a tip pointing claude.ai users who haven't connected GitHub for Claude Code on the web to `/web-setup`
- Added a `/status` line showing whether GitHub is connected for Claude Code on the web (Pro/Max), pointing to `/web-setup` when it isn't
- Added the model (and effort level) each subagent ran on to `/tasks` and the agent detail dialogs
- Fixed remote MCP servers in non-interactive (`-p`) and SDK sessions never recovering after a dropped connection; they now reconnect automatically or report as failed
- Fixed MCP server sign-in started from the desktop app failing with "Invalid redirect URI" on servers that support client ID metadata documents (for example Linear)
- Fixed auto mode staying unavailable at startup when a temporary server-side disable was cached and later flag fetches failed
- Fixed auto mode tool calls being denied as "temporarily unavailable" after about a minute of waiting when the API was briefly overloaded and asked the client to retry
- Fixed the `/model` picker silently ignoring an Ultracode selection; picking Ultracode now applies it to the current session
- Fixed `/resume` only listing the 50 most recent sessions; the picker now loads more as you scroll
- Fixed cloud sessions resuming after a mid-turn restart with a pending hook or background-task notification re-sent as the prompt instead of the normal continuation message
- Fixed cross-session messaging silently turning off inside user namespaces and rootless containers after the 2.1.232 socket-directory hardening
- Fixed text that hangs outside its container (for example the sign-in URL in `/login`) losing its leading columns when another part of the screen repaints
- Fixed `spellcheck` not underlining a misspelled word typed directly after an emoji
- Fixed background subagents not waking when their last background Bash task completes
- Fixed sessions going silent for 10+ minutes when the Anthropic API never starts a response: the request now times out after ~3 minutes, retries once, then shows `API Error: No response from API`
- Fixed auth, model-availability, and other client-generated error messages rendering like model output instead of as error lines
- Fixed workload identity federation in CI: processes in one job share the exchanged token instead of re-exchanging the single-use token; a rejected exchange fails fast with the server's message
- Fixed server-managed `companyAnnouncements` not showing at startup in a session that began with signing in (for example the first launch after `/logout`)
- Fixed hook `if` conditions like `Bash(cat *)` firing on unrelated Bash commands when the command contained `$()` or backtick command substitution followed by more arguments
- Fixed plugin dependencies declared with a `marketplace` field never resolving when both plugins are loaded together via `--plugin-dir`
- Fixed `/reload-plugins` keeping the LSP tool after the last LSP plugin is disabled; it now also warns before an LSP plugin change that would re-read the conversation
- Fixed `--agents` silently ignoring invalid JSON or invalid agent definitions; it now exits with a clear error, like `--mcp-config`
- Fixed `/status` showing "Found invalid entries in: ." with no filename when `~/.claude.json` has an invalid MCP server entry
- Fixed `/clear` removing the `/rename` session name from the prompt bar even though the name was kept for the new session
- Fixed Ctrl+R history search and up-arrow history breaking when `~/.claude/history.jsonl` contains a malformed entry
- Fixed Ctrl+[ not leaving vim INSERT mode in terminals that encode modified keys (modifyOtherKeys / kitty protocol)
- Fixed the local IDE connection being routed through `HTTPS_PROXY` (and sometimes failing) when `localhost` was listed in `NO_PROXY` but not lowercase `no_proxy`; both casings are now honored
- Fixed sandbox network-violation details being dropped from the Bash tool result when the blocked command still exited 0 (for example `curl` printing the proxy's 403 page)
- Fixed the status line `rate_limits` fields and `/usage` still showing a rate-limit window's pre-reset usage percentage after the window reset while the session was idle
- Fixed `claude --teleport
` exiting on uncommitted changes instead of offering to stash them and continue, as the session picker already does
- Fixed `/web-setup` repeatedly asking you to log in when an older GitHub CLI (without `gh auth token`) was already authenticated
- Fixed Claude in Chrome losing its connection to Claude Code after an auto-update cleaned up the version it was set up with; the native host now launches via the stable `claude` launcher
- [VSCode] Fixed sessions started before feature flags were first fetched (for example right after install) opening in the default permission mode instead of auto mode or your configured default mode
- [VSCode] Fixed Focus view sections you expanded collapsing on their own during subagent tool activity
- Improved startup time: sandbox and MCP bring-up no longer block the first frame, bare launches skip subcommand registration, and workflow discovery, settings, and trust-store work is cheaper
- Improved native install and auto-update download size: the binary is now zstd-compressed (about 75 MB instead of 340 MB on Linux x64)
- Improved attribution of usage telemetry to your organization for sessions that authenticate with `ANTHROPIC_AUTH_TOKEN` directly against the Anthropic API, so its data-handling settings apply
- Improved native binary size: about 2 MB smaller by storing the bundled skill and prompt text more compactly
- Improved memory usage of native builds: code is now loaded on demand instead of keeping the whole bundle resident (roughly 40–70 MB less memory per session)
- Improved peak memory usage in long-running sessions (the runtime now garbage-collects sooner as the heap grows)
- Improved `/login` over SSH: the sign-in URL appears immediately, pressing `c` reports how the URL was copied instead of always claiming success, and a hint explains how to select text in fullscreen
- Improved the error when effort `xhigh`/`max` is used with thinking turned off: it now names the level, the setting that disabled thinking, and `/effort high` as the fix
- Improved `/loop`: consecutive wake-ups where Claude has nothing to do now fold into a single line in the terminal instead of printing each one
- Changed the sandboxed Bash tool prompt to no longer list allowed network hosts, so Claude attempts requests (and you can approve new hosts) instead of assuming unlisted hosts are blocked
- Updated the `/model` picker and the bundled `claude-api` skill to show Sonnet 5's $2/$10 per Mtok pricing as its standard list price rather than a limited-time promo
- Changed computer use on macOS so clicking the desktop, Dock, or a Finder window requires granting Finder via the access dialog, like any other app
- Changed `/model`, `/fast`, and `/effort` to also run immediately instead of queueing until the turn ends on Bedrock, Vertex, and Foundry and when telemetry is disabled
- Fixed `claude remote-control` exiting and stranding attached Remote Control sessions when the server drops its environment mid-session; it now recovers
- Fixed Remote Control sessions served by `claude remote-control` sometimes getting stuck after it was stopped and restarted, for Team and Enterprise members without an admin or owner role
- Changed the cross-session messaging inbox socket to close connections that send no complete line within 30 seconds; scripts posting to it should connect once their data is ready
- Improved the notice when resuming a conversation whose Remote Control is held by another terminal: it now says sessions on other machines can't be seen from, or reach, this one
- [VSCode] Improved history trimming in long sessions: older tool-activity rows are dropped first so your messages and Claude's replies stay visible
- [VSCode] Improved attribution of the extension's own usage telemetry to your organization when you are signed in with a Claude account, so its data-handling settings apply

## 2.1.241

- Bug fixes and reliability improvements

## 2.1.240

- Bug fixes and reliability improvements

## 2.1.239

- Cost estimates (`/cost`, status line, `--max-budget-usd`) now include the 1.1× US-only-inference premium for data-residency workspaces
- Added the one-time fullscreen renderer offer on Bedrock, Vertex, Foundry and other previously excluded setups; new installs there now start in fullscreen
- Added `/claude-api upgrade` to migrate Python projects from `anthropic` 0.x to 1.x, and updated the skill's Python reference for 1.x (timeouts use `anthropic.Timeout`, not `httpx.Timeout`)
- Cloud sessions: plugins synced from claude.ai now show as `name@synced`, work with `claude plugin enable/disable
@synced`, and never override a same-named plugin you installed
- Alpine/musl builds: native image paste, clipboard, and audio-capture add-ons now load (musl-built binaries instead of glibc ones refused by the runtime)
- The usage-limit message shown when your monthly spend limit is already used up now also says when your session or weekly limit resets
- Fixed Bedrock streaming behind proxies that strip the response Content-Type header, which silently doubled billed API calls by re-running every turn non-streaming
- Fixed Claude Code hanging at startup behind an HTTPS proxy when using Bedrock with an SSO profile and `awsAuthRefresh` — the credential pre-check now honors `HTTPS_PROXY`
- Fixed a raw crash dump when starting Claude Code from a directory that no longer exists; it now prints a clear message
- Fixed Edit and Write calls pausing for about 5 seconds in JetBrains IDE terminals when the Claude Code plugin is connected
- Fixed a race where pressing Esc with a prompt queued could let the next turn finish early, leaving the session idle while Claude was still working and letting a later resubmit repeat actions
- Fixed WebFetch retaining expired page content in memory for the whole session instead of the intended 15 minutes
- Fixed cloud sessions (Claude Code on the web, desktop and mobile apps) resuming out of plan mode after an idle worker restart
- Fixed MCP elicitation forms taller than the terminal being clipped in fullscreen mode: the form now fits the window, with hidden fields reachable by scrolling and Accept/Decline always visible
- Fixed remote MCP servers staying failed after a transient 5xx on a mid-session reconnect in cloud sessions or via SDK `setMcpServers()`
- Fixed custom session titles disappearing from `/resume` after more than ~64 KB of conversation was written following the rename
- Fixed `claude -c`/resume picking up sessions from a different directory whose path differed only by characters like `_`, `-`, or `.`
- Fixed `/resume` and the agents view showing a session as recently changed (and reordering it) when only its file was touched or it was merely reopened
- Fixed `/resume` in all-projects mode telling you to `cd` into a deleted directory (e.g. a removed worktree); such sessions now resume in the current directory
- Fixed the `dark-ansi` theme rendering expanded tool results in fullscreen mode with text the same color as the background
- Fixed the fullscreen renderer prompt reappearing on every launch when it could never be answered; it now stops after being shown on three launches
- Fixed `.worktreeinclude` patterns starting with `**/` silently matching nothing when the target lived in a gitignored directory
- Fixed agents, skills, and commands whose `.md` file starts with a UTF-8 BOM being silently ignored
- Fixed `/insights` echoing literal `
` tags in its response on some models
- Fixed marketplace `metadata.pluginRoot` having no effect: bare plugin source names now resolve under it as the docs describe
- Fixed mouse movement in browser-based terminals inserting text like `"35;150;7M"` into the prompt when a mouse report arrived split across writes
- Fixed custom theme overrides for the effort/ultracode status badge colors being ignored
- Fixed OpenTelemetry trace fragmentation: tool executions deferred by a `PreToolUse` hook now resume in the original turn's trace instead of starting a new trace
- Fixed vim mode in the agent view: Escape now switches to NORMAL mode and keeps your text instead of clearing the prompt
- Fixed the `selection:copy` keybinding silently dropping a text selection that had been extended with Shift+Arrow keys
- Fixed the `/voice` startup tip still appearing after voice dictation was enabled via the `voice.enabled` setting
- Fixed shell-mode (`!`) Tab completion dropping the `./` from a `./script` path, which left a command the shell couldn't run
- Fixed fullscreen mode answering a permission prompt or pressing a button when you clicked the terminal window only to bring it back into focus
- Fixed slash-command panels (e.g. `/config`, `/model`) in fullscreen mode covering the latest messages; the conversation now stays pinned above the panel
- Fixed the `/workflows` detail dialog overflowing the terminal and losing its header off-screen when opened while Claude is still responding
- Fixed the Linux sandbox making a nonexistent `.git/config.worktree` unreadable, which broke every sandboxed git command in repos with `extensions.worktreeConfig` set
- Fixed hooks failing with "posix_spawn ENOENT" after the session's working directory was deleted; they now run from the project root or home directory instead
- Fixed `claudeMdExcludes` not excluding a symlinked `.claude/rules` file when the pattern names the rules directory or the symlink rather than its target
- Fixed runaway session-title syncing to Remote Control when two Claude Code processes shared one background job's state (2.1.232 regression); title updates are now deduplicated and rate-limited
- Fixed sessions whose title starts with `/` being unaddressable by `SendMessage` and shown as "(untitled)" in `ListAgents`
- Fixed Ctrl+W, Ctrl+U, Ctrl+K, Option+Backspace, Option+D and vim `df`/`dt` leaving a broken `[Pasted text #N]` placeholder when the cursor was inside it
- Fixed masked (password-style) inputs such as the login code field letting their text be pasted back with Ctrl+Y elsewhere or saved to prom
