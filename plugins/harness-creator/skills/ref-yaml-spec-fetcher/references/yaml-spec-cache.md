# YAML Spec Cache

last_fetched: 2026-08-17T01:05:11Z
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
Bundled skills are available in every session. To turn them off, use the
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
All three skills require Claude Code v2.1.145 or later. Check your version with
claude --version
or the
/status
command.
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
inside each added directory alongside the project skills.
Skills in nested
.claude/skills/
directories below your starting directory aren’t loaded at startup. They load the first time Claude reads or edits a file inside that subdirectory, and stay available for the rest of the session. For example, after Claude edits a file under
packages/frontend/
, skills in
packages/frontend/.claude/skills/
become available. Until then, those skills don’t appear in autocomplete and can’t be invoked by name.
Each skill is a directory with
SKILL.md
as the entrypoint:
my-skill/
├── SKILL.md           # Main instructions (required)
├── template.md        # Template for Claude to fill in
├── examples/
│   └── sample.md      # Example output showing expected format
└── scripts/
└── validate.sh    # Script Claude can execute
The
SKILL.md
contains the main instructions and is required. Other files are optional and let you build more powerful skills: templates for Claude to fill in, example outputs showing the expected format, scripts Claude can execute, or detailed reference documentation. Reference these files from your
SKILL.md
so Claude knows what they contain and when to load them. See
Add supporting files
for more details.
Files in
.claude/commands/
support the same
frontmatter
, except
name
and
paths
, which Claude Code ignores in a command file. You invoke a command file by its file name. Skills are recommended since they support additional features like supporting files.
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
from each added directory automatically. This exception applies only to
--add-dir
and
/add-dir
. The
permissions.additionalDirectories
setting in
settings.json
grants file access only and doesn’t load skills or commands. See
Live change detection
for how skill edits are picked up during a session.
Other
.claude/
configuration such as output styles is not loaded from additional directories. See the
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
. Every local session you start afterwards loads them from
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
is enabled: it’s on by default on Windows without Git Bash, and
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
enables it elsewhere.
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
also invokes the skill unless another command already uses that name. Before v2.1.216, the frontmatter name replaced the whole command name, so the menu showed
/fancy
without the plugin prefix and
/my-plugin:fancy
didn’t autocomplete.
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
All arguments passed when invoking the skill. If
$ARGUMENTS
is not present in the content, arguments are appended as
ARGUMENTS: <value>
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
content enters the conversation as a single message and stays there for the rest of the session. This persistence applies to the skill’s instructions, not its permissions: an
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
If you invoke a skill with arguments but the skill doesn’t include
$ARGUMENTS
, Claude Code appends
ARGUMENTS: <your input>
to the end of the skill content so Claude still sees what you typed.
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
Migrate a component from one framework to another
---
Migrate the $ARGUMENTS[0] component from $ARGUMENTS[1] to $ARGUMENTS[2].
Preserve all existing behavior and tests.
Running
/migrate-component SearchBar React Vue
replaces
$ARGUMENTS[0]
with
SearchBar
,
$ARGUMENTS[1]
with
React
, and
$ARGUMENTS[2]
with
Vue
. The same skill using the
$N
shorthand:
---
name
:
migrate-component
description
:
Migrate a component from one framework to another
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
npm --version
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
To request deeper reasoning when a skill runs, include
ultrathink
anywhere in the skill content. See
Use ultrathink for one-off deep reasoning
.
​
How injected commands run
Claude Code picks the tool that runs a skill’s injected commands from the
shell
key in the skill’s frontmatter and your environment. Every combination runs the commands through the Bash tool or the PowerShell tool, except one that fails the invocation outright:
shell: powershell
, with the
PowerShell tool
enabled: the commands run through the PowerShell tool.
shell: bash
when bash isn’t available: the invocation fails before any command runs. This happens on Windows without Git Bash. Claude Code shows
Skill <name> requires bash (`shell: bash` in frontmatter) but Git Bash was not found
.
Any other combination: the commands run through the Bash tool when bash is available. When it isn’t, they run through the PowerShell tool.
Either tool runs the commands the same way it runs Claude’s own shell commands. They share the working directory, timeout, and output handling:
Working directory
: Claude Code runs each command in the session shell’s current working directory. That directory moves when Claude runs
cd
. Use
${CLAUDE_SKILL_DIR}
or
${CLAUDE_PROJECT_DIR}
in paths that must resolve the same way every time.
stderr
: with the default
bash
shell, Claude Code merges stderr into stdout. Anything the command writes to stderr appears in the injected text.
Timeout
: each command runs under the Bash tool’s default 2-minute
timeout
. When the Bash tool
moves a timed-out command to the background
, the skill still renders. The injected text reports the move and names the background task and the file collecting the command’s output. When the command is one the Bash tool never auto-backgrounds, Claude Code kills it at the timeout. That failure
aborts the invocation
.
Output size
: output past the Bash tool’s inline ceiling arrives as a file path plus a short preview, not truncated text.
Output limits
covers the ceiling and which variable adjusts which boundary.
The PowerShell tool applies the same timeout, backgrounding, and output-ceiling behavior to the commands it runs. See the
PowerShell tool
section for its specifics.
​
When an injected command fails
A failed command aborts the entire skill invocation, not just its own placeholder. Claude never sees the skill content for that invocation. The abort shows
Shell command failed for pattern "..."
. The error message includes the command’s output under
[stderr]
.
With the default
bash
shell, any non-zero exit code counts as a failure. One carveout applies: Claude Code treats exit code 1 from
search and comparison commands
as a normal result and injects their output. Exit codes of 2 or higher fail even for those commands.
Which commands get the carveout depends on the shell:
Default
bash
shell: the commands listed under
Output limits
shell: powershell
, when the PowerShell tool is enabled: a
different set
that includes
grep
and
git diff
but not
find
or
diff
With the default
bash
shell, append
|| true
to any other command you expect to exit non-zero. A check script that exits 1 when it finds problems is one example.
Injected commands never prompt for permission. When a command’s permission check returns anything other than allow, Claude Code aborts the invocation. This includes a rule that would normally ask you. The abort shows
Shell command permission check failed for pattern "..."
.
To keep an unmatched command from aborting here, pre-approve it with
allowed-tools
. A matching ask or deny rule still aborts the invocation regardless of
allo

## Source (settings): https://docs.claude.com/en/docs/claude-code/settings

Claude Code settings - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Claude Code offers a variety of settings to configure its behavior to meet your needs. You can configure Claude Code by running the
/config
command in an interactive session, which opens a tabbed Settings interface where you can view status information and modify configuration options. From v2.1.181, you can change a single option without opening the interface by passing
key=value
to
/config
, for example
/config verbose=true
.
​
Configuration scopes
Claude Code uses a scope system to determine where configurations apply and who they’re shared with. Understanding scopes helps you decide how to configure Claude Code for personal use, team collaboration, or enterprise deployment.
​
Available scopes
Scope
Location
Who it affects
Shared with team?
Managed
Server-managed settings, plist / registry, or system-level
managed-settings.json
All organization members for server-managed delivery; all users on the machine for plist, HKLM registry, and file delivery; the current user for HKCU registry delivery
Yes (deployed by IT)
User
~/.claude/
directory
You, across all projects
No
Project
.claude/
in repository
All collaborators on this repository
Yes (committed to git)
Local
.claude/settings.local.json
at the repository root
You, in this repository only
No (gitignored when Claude Code saves a setting to it)
​
When to use each scope
Managed scope
is for:
Security policies that must be enforced organization-wide
Compliance requirements that can’t be overridden
Standardized configurations deployed by IT/DevOps
User scope
is best for:
Personal preferences you want everywhere (themes, editor settings)
Tools and plugins you use across all projects
API keys and authentication (stored securely)
Project scope
is best for:
Team-shared settings (permissions, hooks, MCP servers)
Plugins the whole team should have
Standardizing tooling across collaborators
Local scope
is best for:
Personal overrides for a specific project
Testing configurations before sharing with the team
Machine-specific settings that won’t work for others
​
How scopes interact
When the same setting appears in multiple scopes, Claude Code applies them in priority order:
Managed
(highest): can’t be overridden by any other scope, apart from the
exceptions to managed settings precedence
Command line arguments
: temporary session overrides
Local
: overrides project and user settings
Project
: overrides user settings
User
(lowest): applies when nothing else specifies the setting
For example, if your user settings set
spinnerTipsEnabled
to
true
and project settings set it to
false
, the project value applies. Permission rules merge across scopes instead, and a few security-sensitive keys are exceptions. See
Settings precedence
.
​
What uses scopes
Scopes apply to many Claude Code features:
Feature
User location
Project location
Local location
Settings
~/.claude/settings.json
.claude/settings.json
.claude/settings.local.json
Subagents
~/.claude/agents/
.claude/agents/
None
MCP servers
~/.claude.json
.mcp.json
~/.claude.json
(per-project)
Plugins
~/.claude/settings.json
.claude/settings.json
.claude/settings.local.json
CLAUDE.md
~/.claude/CLAUDE.md
CLAUDE.md
or
.claude/CLAUDE.md
CLAUDE.local.md
On Windows, paths shown as
~/.claude
resolve to
%USERPROFILE%\.claude
.
​
Settings files
The
settings.json
file is the official mechanism for configuring Claude
Code through hierarchical settings:
User settings
are defined in
~/.claude/settings.json
and apply to all
projects.
Project settings
are saved in your project directory:
.claude/settings.json
for settings that are checked into source control and shared with your team
.claude/settings.local.json
for settings that are not checked in, useful for personal preferences and experimentation. When Claude Code saves a setting to this file in a repository that doesn’t already ignore it, Claude Code adds
**/.claude/settings.local.json
to your global git excludes file. That excludes file is
core.excludesFile
from your global git config when it’s set to an absolute or
~
-prefixed path, otherwise
$XDG_CONFIG_HOME/git/ignore
, or
~/.config/git/ignore
. If you create the file by hand or have Claude write it with the Write tool, add it to your gitignore yourself.
Claude Code reads and writes this file at the root of the git repository, resolved through
worktrees
to the main checkout, so one file covers sessions started in any subdirectory or worktree of the repository. The file stays in the directory you start Claude Code from in three cases: outside a git repository, when the repository root is your home directory, and in
Agent SDK
sessions.
Before v2.1.211, the file always lived in the starting directory. Claude Code still reads a
.claude/settings.local.json
that an earlier version left there. When both files set the same key, the repository root’s value wins, except that permission rules from both files stay in effect.
Claude Code also saves permanent “don’t ask again”
permission approvals
, such as Bash command approvals, to this file.
Because this file is yours rather than the repository’s, its permission
allow
rules take effect without the
workspace trust
step that
.claude/settings.json
allow rules require. If the repository supplies the file, for example by committing it, workspace trust still applies.
Managed settings
: For organizations that need centralized control, Claude Code supports multiple delivery mechanisms for managed settings. All use the same JSON format and cannot be overridden by user or project settings:
Server-managed settings
: delivered remotely at sign-in, either from Anthropic’s servers via the claude.ai admin console or from a self-hosted
Claude apps gateway
. See
server-managed settings
.
MDM/OS-level policies
: delivered through native device management on macOS and Windows:
macOS:
com.anthropic.claudecode
managed preferences domain. The plist’s top-level keys mirror
managed-settings.json
, with nested settings as dictionaries and arrays as plist arrays. Deploy via configuration profiles in Jamf, Iru (Kandji), or similar MDM tools.
Windows:
HKLM\SOFTWARE\Policies\ClaudeCode
registry key with a
Settings
value (REG_SZ or REG_EXPAND_SZ) containing JSON (deployed via Group Policy or Intune)
Windows (user-level):
HKCU\SOFTWARE\Policies\ClaudeCode
(lowest policy priority, only used when no admin-level source exists)
File-based
:
managed-settings.json
and
managed-mcp.json
deployed to system directories:
macOS:
/Library/Application Support/ClaudeCode/
Linux and WSL:
/etc/claude-code/
Windows:
C:\Program Files\ClaudeCode\
The legacy Windows path
C:\ProgramData\ClaudeCode\managed-settings.json
is no longer supported as of v2.1.75. Administrators who deployed settings to that location must migrate files to
C:\Program Files\ClaudeCode\managed-settings.json
.
File-based managed settings also support a drop-in directory at
managed-settings.d/
in the same system directory alongside
managed-settings.json
. This lets separate teams deploy independent policy fragments without coordinating edits to a single file.
Following the systemd convention, Claude Code merges
managed-settings.json
first as the base, then sorts all
*.json
files in the drop-in directory alphabetically and merges them on top. For scalar values, Claude Code lets later files override earlier ones; it concatenates and de-duplicates arrays and deep-merges objects. A later file’s
fallbackModel
chain replaces an earlier one instead of merging with it, and a later file’s
extraKnownMarketplaces
entry replaces an earlier file’s same-name entry whole. Claude Code ignores hidden files starting with
.
.
Use numeric prefixes to control merge order, for example
10-telemetry.json
and
20-security.json
.
See
managed settings
and
Managed MCP configuration
for details.
This
repository
includes starter deployment templates for Jamf, Iru (Kandji), Intune, and Group Policy. Use these as starting points and adjust them to fit your needs.
Managed deployments can also restrict
plugin marketplace additions
using
strictKnownMarketplaces
. For more information, see
Managed marketplace restrictions
.
Other configuration
is stored in
~/.claude.json
. This file contains your OAuth session,
MCP server
configurations for user and local scopes, per-project state (allowed tools, trust settings), and various caches. Project-scoped MCP servers are stored separately in
.mcp.json
.
Claude Code automatically creates timestamped backups of configuration files and retains the five most recent backups to prevent data loss.
The following example works in any of the settings file locations above. Where you save the file determines where it applies:
To apply it to all of your projects, save it as
~/.claude/settings.json
. This file lives in your home directory rather than in any project, so Claude Code reads it in every session regardless of which project you open.
To share it with collaborators on one project, save it as
.claude/settings.json
in that project. Claude Code reads this file from the directory the session runs in, so it applies only to that project, and checking it into source control gives every collaborator the same settings.
Example settings.json
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
,
"Read(~/.zshrc)"
],
"deny"
: [
"Bash(curl *)"
,
"Read(./.env)"
,
"Read(./.env.*)"
,
"Read(./secrets/**)"
]
},
"env"
: {
"CLAUDE_CODE_ENABLE_TELEMETRY"
:
"1"
,
"OTEL_METRICS_EXPORTER"
:
"otlp"
,
"OTEL_EXPORTER_OTLP_PROTOCOL"
:
"http/protobuf"
},
"companyAnnouncements"
: [
"Welcome to Acme Corp! Review our code guidelines at docs.acme.com"
,
"Reminder: Code reviews required for all PRs"
,
"New security policy in effect"
]
}
The
$schema
line in the example above points to the
official JSON schema
for Claude Code settings. Adding it to your
settings.json
enables autocomplete and inline validation in VS Code, Cursor, and any other editor that supports JSON schema validation.
The published schema is updated periodically and may not include settings added in the most recent CLI releases, so a validation warning on a recently documented field does not necessarily mean your configuration is invalid.
After you edit a settings file, run
/status
inside Claude Code to confirm it was loaded. The
Setting sources
line lists each settings source loaded for the current session; a source appears once it loads with at least one setting, so a file with broken JSON doesn’t appear even if it contains settings. See
Verify active settings
.
​
When edits take effect
Claude Code watches your settings files and reloads them when they change, so edits to most keys apply to the running session without a restart. This includes
permissions
,
hooks
, and credential helpers like
apiKeyHelper
. The reload covers user, project, local, and managed settings, and the
ConfigChange
hook
fires for each detected change.
A few keys are read once at session start and apply on the next restart instead:
model
: use
/model
to switch mid-session
outputStyle
: part of the system prompt, which is rebuilt on
/clear
or restart
​
Invalid entries in managed settings
Managed settings parse tolerantly. When a managed configuration contains an entry that fails schema validation, Claude Code strips that entry, records a warning, and enforces every remaining valid policy. A single typo cannot disable the rest of your organization’s policy. Run
/doctor
to list stripped entries with their source file and field.
This behavior is consistent across all three delivery mechanisms:
server-managed settings
, plist and registry policies deployed through MDM, and
managed-settings.json
files. Requires Claude Code v2.1.169 or later.
Security-enforcement fields are handled per field instead of being stripped wholesale when they are present but invalid:
Field
Behavior when present but invalid
allowedMcpServers
Enforced as an empty allowlist, so no MCP servers are admitted until the value is fixed. An individual invalid entry is stripped and the valid subset is enforced.
allowManagedHooksOnly
Treated as
true
, so the
hook restrictions
apply until the value is fixed and, unless
disableCommandPluginSources
is explicitly
false
, command-sourced plugins are disabled. Applies in v2.1.229 and later.
allowManagedMcpServersOnly
Treated as
true
.
disableCommandPluginSources
Treated as
true
, so command-sourced plugins stay disabled until the value is fixed. Applies in v2.1.229 and later.
availableModels
Enforced as an empty allowlist, so only the Default model is available until the value is fixed. An individual non-string entry is stripped and the valid subset is enforced. Applies in v2.1.175 and later.
enforceAvailableModels
Treated as
true
. Applies in v2.1.175 and later.
forceLoginOrgUUID
No organization is permitted to log in until the value is fixed.
deniedMcpServers
An individual invalid entry is stripped and the valid subset is enforced. A wholly invalid value is dropped with a warning, since denying every server would block servers the policy never named.
sandbox.credentials
An invalid entry in
files
or
envVars
that still has a valid
path
or
name
and a
mode
of
mask
or
deny
, such as one whose
extract
pattern has no capturing group, is degraded to
mode: "deny"
with a warning, so the credential stays blocked, not masked, until you fix the entry. A degraded
files
entry pins
filesystem.disabled
like an explicit
deny
entry, and the warning notes that its read block isn’t enforced if managed settings turn filesystem isolation off. An entry with an unknown
mode
or an invalid
path
or
name
is stripped. Each case warns; whether an entry is degraded or stripped, the remaining valid entries are still enforced, and a wholly invalid
credentials
value is dropped while the rest of
sandbox
still applies. Applies in v2.1.191 and later; before v2.1.221, every invalid entry was stripped.
requiredMinimumVersion
and
requiredMaximumVersion
fail open by design: an invalid value is stripped rather than enforced, so a bad policy push cannot prevent Claude Code from starting.
Validation errors surface in three places:
Interactive sessions show a dialog at startup listing the invalid entries.
Headless runs with
-p
print a summary to stderr.
claude doctor
lists each invalid entry with its source and field.
Validate policy changes by running
claude doctor
on a test machine before deploying them fleet-wide.
This tolerance applies only to managed settings. User, project, and local settings files remain strict: a file that fails validation is rejected as a whole and reported.
​
Available settings
settings.json
supports a number of options:
Key
Description
Example
advisorModel
Model for the server-side
advisor tool
. Accepts the model aliases
"fable"
,
"opus"
, and
"sonnet"
, or a full model ID.
"fable"
requires
Fable 5 access
. Written automatically when you run
/advisor
. Unset to disable the advisor.
"opus"
agent
Run the main thread as a named subagent, and set the default agent for sessions dispatched from
claude agents
. Applies that subagent’s system prompt, tool restrictions, and model. See
Invoke subagents explicitly
"code-reviewer"
agentPushNotifEnabled
Default
:
false
. When
Remote Control
is connected, allow Claude to send proactive push notifications to your phone, for example when a long task finishes. Appears in
/config
as
Push when Claude decides
. See
Mobile push notifications
true
allowAllClaudeAiMcps
(Managed settings only) Load the claude.ai connectors Claude Code fetches itself alongside a deployed
managed-mcp.json
, which otherwise takes exclusive control and suppresses them. Connectors delivered to cloud sessions stay suppressed. See
Managed MCP configuration
true
allowedChannelPlugins
(Managed settings only) Allowlist of channel plugins that may push messages. Replaces the default Anthropic allowlist when set. Undefined = fall back to the default, empty array = block all channel plugins. Requires
channelsEnabled: true
. See
Restrict which channel plugins can run
[{ "marketplace": "claude-plugins-official", "plugin": "telegram" }]
allowedHttpHookUrls
Allowlist of URL patterns that HTTP hooks may target. Supports
*
as a wildcard. When set, hooks with non-matching URLs are blocked. Undefined = no restrictions, empty array = block all HTTP hooks. Arrays merge across settings sources. See
Hook configuration
["https://hooks.example.com/*"]
allowedMcpServers
When set in managed-settings.json, allowlist of MCP servers users can configure. Undefined = no restrictions, empty array = lockdown. Applies to all scopes. Denylist takes precedence. See
Managed MCP configuration
[{ "serverName": "github" }]
allowManagedHooksOnly
(Managed settings only) Restrict which hooks run; see
Hook configuration
for the full effect list
true
allowManagedMcpServersOnly
(Managed settings only) Only
allowedMcpServers
from managed settings are respected.
deniedMcpServers
still merges from all sources. Users can still add MCP servers, but only the admin-defined allowlist applies. See
Managed MCP configuration
true
allowManagedPermissionRulesOnly
(Managed settings only) Prevent user and project settings from defining
allow
,
ask
, or
deny
permission rules. Only rules in managed settings apply. See
Managed-only settings
true
alwaysThinkingEnabled
Enable
extended thinking
by default for all sessions. Typically configured via the
/config
command rather than editing directly. To force thinking off regardless of this setting, set
MAX_THINKING_TOKENS=0
in
env
, which disables thinking on the Anthropic API except on Fable 5, which cannot have thinking turned off. On
third-party providers
this omits the
thinking
parameter instead, and adaptive-reasoning models may still think
true
apiKeyHelper
Custom command, run through the system shell (
/bin/sh
on macOS and Linux,
cmd
on Windows), to generate an auth value. This value will be sent as
X-Api-Key
and
Authorization: Bearer
headers for model requests. Set the refresh interval with
CLAUDE_CODE_API_KEY_HELPER_TTL_MS
/bin/generate_temp_api_key.sh
askUserQuestionTimeout
Default
:
"never"
. Idle time before an unanswered
AskUserQuestion
dialog auto-continues with whatever options you’d already selected. Accepts
"60s"
,
"5m"
,
"10m"
, or
"never"
. With the default, questions wait until you answer them. Appears in
/config
as
Question auto-continue timeout
, which writes this key to user settings. Not read from project or local settings. Requires Claude Code v2.1.200 or later
"5m"
attribution
Customize attribution for git commits and pull requests. See
Attribution settings
{"commit": "🤖 Generated with Claude Code", "pr": ""}
autoCompactEnabled
Default
:
true
. Automatically compact the conversation when context approaches the limit. Appears in
/config
as
Auto-compact
. To disable via environment variable, set
DISABLE_AUTO_COMPACT
in
env
false
autoCompactWindow
How full the context window gets before Claude Code
compacts automatically
, in tokens from
100000
to
1000000
. When unset, Claude Code uses a window tuned for your model. Set it with the
/autocompact
command, which writes this key to user settings; the
--autocompact
flag and the
CLAUDE_CODE_AUTO_COMPACT_WINDOW
environment variable can override it.
Set the auto-compact window
covers how they interact
500000
autoMemoryDirectory
Custom directory for
auto memory
storage. Accepts an absolute path or a
~/
-prefixed path. From project or local settings, Claude Code honors it under the same
workspace trust rule as hooks
, since a cloned repository can supply this file
"~/my-memory-dir"
autoMemoryEnabled
Default
:
true
. Enable
auto memory
. When
false
, Claude does not read from or write to the auto memory directory. You can also toggle this with
/memory
during a session. To disable via environment variable, set
CLAUDE_CODE_DISABLE_AUTO_MEMORY
in
env
false
autoMode
Customize what the
auto mode
classifier blocks and allows. Contains
environment
,
allow
,
soft_deny
, and
hard_deny
arrays of prose rules. Include the literal string
"$defaults"
in an array to inherit the built-in rules at that position. See
Configure auto mode
. Read from user settings, the
--settings
flag, and managed settings only. Ignored in project
.claude/settings.json
and local
.claude/settings.local.json
. Before v2.1.207,
.claude/settings.local.json
was also read
{"soft_deny": ["$defaults", "Never run terraform apply"]}
autoMode.classifyAllShell
Default
:
false
. When
true
, suspends every Bash and PowerShell allow rule while auto mode is active so all shell commands route through the classifier, not only rules that match arbitrary-code-execution patterns. See
Route all shell commands through the classifier
. Requires Claude Code v2.1.193 or later
true
autoScrollEnabled
Default
:
true
. In
fullscreen rendering
, follow new output to the bottom of the conversation. Appears in
/config
as
Auto-scroll
. Permission prompts still scroll into view when this is off
false
autoUpdatesChannel
Default
:
"latest"
. Release channel to follow for updates. Use
"stable"
for a version that is typically about one week old and skips versions with major regressions, or
"latest"
for the most recent release. To disable auto-updates entirely, set
DISABLE_AUTOUPDATER
in
env
"stable"
availableModels
Restrict which models users can select for the main session,
subagents
,
skills
, and the
advisor
. Does not affect the Default option unless
enforceAvailableModels
is also set. See
Restrict model selection
["sonnet", "haiku"]
awaySummaryEnabled
Show a one-line session recap when you return to the terminal after a few minutes away. Set to
false
or turn off Session recap in
/config
to disable. Same as
CLAUDE_CODE_ENABLE_AWAY_SUMMARY
true
awsAuthRefresh
Custom script that modifies the
.aws
directory (see
advanced credential configuration
)
aws sso login --profile myprofile
awsCredentialExport
Custom script that outputs JSON with AWS credentials (see
advanced credential configuration
)
/bin/generate_aws_grant.sh
axScreenReader
Render screen-reader friendly output: flat text without decorative borders or animations. Screen-reader mode uses the classic renderer, so the
tui
setting has no effect while it is active; attached
background sessions
still render fullscreen. The
CLAUDE_AX_SCREEN_READER
environment variable and the
--ax-screen-reader
flag take precedence. Requires Claude Code v2.1.181 or later
true
blockedMarketplaces
(Managed settings only) Blocklist of marketplace sources. Enforced on marketplace add and on plugin install, update, refresh, and auto-update, so a marketplace added before the policy was set cannot be used to fetch plugins. Blocked sources are checked before downloading, so they never touch the filesystem. A
github
entry may use the
owner-wildcard form
"owner/*"
to block every repository under that GitHub owner. Requires Claude Code v2.1.223 or later. See
Managed marketplace restrictions
[{ "source": "github", "repo": "untrusted/plugins" }]
browserExternalPageTools
(Managed settings only) Set to
"disabled"
to prevent Claude from using tools to read or act on external pages in the desktop app’s
Browser pane
. Users can still navigate to external sites themselves, and local dev server previews are unaffected
"disabled"
channelsEnabled
(Managed settings only) Allow
channels
for the organization. On claude.ai Team and Enterprise plans, channels are blocked when this is unset or
false
. For
Anthropic Console
accounts using API key authentication, channels are allowed by default unless your organization deploys managed settings, in which case this key must be set to
true
true
claudeMd
(Managed settings only) CLAUDE.md-style instructions injected as organization-managed memory. Only honored when set in managed or policy settings and ignored in user, project, and local settings. See
organization-wide CLAUDE.md
"Always run make lint before committing."
claudeMdExcludes
Glob patterns or absolute paths of
CLAUDE.md
files to skip when loading
memory
. Patterns match against absolute file paths. Only applies to user, project, and local memory; managed policy files cannot be excluded
["**/vendor/**/CLAUDE.md"]
cleanupPeriodDays
Default
:
30
days, minimum
1
. Claude Code deletes
session files and other application data
older than this period at startup, as long as it can safely determine the retention period. To disable transcript writes entirely, see
Plaintext storage
.
20
companyAnnouncements
Announcement to display to users at startup. If multiple announcements are provided, they will be cycled through at random.
["Welcome to Acme Corp! Review our code guidelines at docs.acme.com"]
crossSessionInbound
How this session treats inbound
cross-session messages
from your other Claude Code sessions:
"accept"
delivers them to Claude,
"hold"
shows a notice for each message without delivering it, and
"refuse"
drops them. When no value applies, Claude Code decides per message from the two sessions’ permission-mode classes; see
Control inbound messages
for the rules. Claude Code reads managed settings first, then the
--settings
flag, then user settings, and applies the first value found; a value in project or local settings applies only when it’s stricter, on the
accept
<
hold
<
refuse
ladder, than the value those trusted sources give. When none of the trusted sources sets a value, a project or local
hold
or
refuse
still applies, replacing the per-message default. Requires Claude Code v2.1.224 or later. In sessions with cross-session messaging, appears in
/config
as
Messages from your other sessions
, which writes this key to user settings. The row requires Claude Code v2.1.232 or later, and Claude Code hides it while the
--settings
flag or managed settings set the key
"hold"
defaultShell
Default
:
"bash"
, or
"powershell"
on Windows when Bash isn’t available. Default shell for input-box
!
commands. Accepts
"bash"
or
"powershell"
. Setting
"powershell"
routes interactive
!
commands through PowerShell when the
PowerShell tool
is enabled: it’s on by default on Windows without Git Bash, and
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
enables it elsewhere
"powershell"
deniedMcpServers
When set in managed-settings.json, denylist of MCP servers that are explicitly blocked. Applies to all scopes including managed servers. Denylist takes precedence over allowlist. See
Managed MCP configuration
[{ "serverName": "filesystem" }]
dialogExpiry
Default
:
"5m"
. Deadline for dialogs Claude Code
forwards to a remote client
, such as a Remote Control or SDK host, and for the approval dialog for a
held cross-session message
. When no answer arrives before the deadline, Claude Code cancels the dialog and continues with its no-action default. Permission prompts and
AskUserQuestion
questions use their own flows and aren’t governed by this deadline. Accepts
"60s"
,
"5m"
,
"10m"
, or
"never"
, which disables the deadline. The
CLAUDE_CODE_USER_DIALOG_TIMEOUT_MS
environment variable overrides this setting. Read from user, managed, and
--settings
sources only. Requires Claude Code v2.1.224 or later. Appears in
/config
as
Dialog expiry
, which writes this key to user settings. The row requires Claude Code v2.1.232 or later, and Claude Code hides it while the
--settings
flag or managed settings set the key
"10m"
disableAgentView
Set to
true
to turn off
background agents and agent view
:
claude agents
,
--bg
,
/background
, and the on-demand supervisor. Typically set in
managed settings
. Equivalent to setting
CLAUDE_CODE_DISABLE_AGENT_VIEW
to
1
true
disableAllHooks
Disable all
hooks
, any custom
status line
, and any custom
file suggestion
command
true
disableArtifact
Set to
true
to disable the
Artifact
tool, which publishes session output as a private web page on claude.ai. Equivalent to setting
CLAUDE_CODE_DISABLE_ARTIFACT
to
1
true
disableAutoMode
Set to
"disable"
to prevent
auto mode
from being activated. Removes
auto
from the
Shift+Tab
cycle, and any session that would otherwise
start in auto mode
, whether from
--permission-mode auto
, a settings file, or the built-in default, starts in
default
instead. Also accepted under
permissions
as
permissions.disableAutoMode
. Most useful in
managed settings
where users cannot override it
"disable"
disableBrowserExternalNavigation
(Managed settings only) Set to
true
to turn off external browsing in the desktop app’s
Browser pane
. Neither users nor Claude can navigate to external sites, and localhost dev server previews are unaffected. The value must be the JSON boolean
true
; the string
"true"
is ignored
true
disableBundledSkills
Set to
true
to disable the
skills
and workflows included with Claude Code: bundled skills and workflows are removed entirely, while built-in commands like
/init
stay typable but are hidden from the model.
/doctor
stays typable like the built-in commands; hide it with
DISABLE_DOCTOR_COMMAND
instead. Skills from plugins,
.claude/skills/
, and
.claude/commands/
are unaffected. Equivalent to setting
CLAUDE_CODE_DISABLE_BUNDLED_SKILLS
to
1
true
disableClaudeAiConnectors
Disable
claude.ai MCP connectors
so they are not auto-fetched or connected. Set in any settings scope.
true
in any source takes precedence, so a checked-in project
.claude/settings.json
can opt a repo out of cloud connectors, but a project-level
false
cannot override a user- or policy-level
true
. Servers passed explicitly via
--mcp-config
are unaffected. To deny individual connectors instead of all of them, use
deniedMcpServers
. Requires Claude Code v2.1.182 or later
true
disableCommandPluginSources
(Managed settings only) Control the
command
plugin source
, which installs a plugin by running a marketplace-declared command on the user’s machine. Set to
true
to block command-sourced plugins entirely. Claude Code never runs the command, doesn’t install or update those plugins, and stops loading the ones already installed. Set to
false
to allow them explicitly. When unset, Claude Code follows
allowManagedHooksOnly
, so an organization that restricts hook execution to managed settings gets command sources disabled too. Requires Claude Code v2.1.229 or later
true
disableDeepLinkRegistration
Set to
"disable"
to prevent Claude Code from registering the
claude-cli://
protocol handler with the operating system when you send the first prompt of an interactive session.
Deep links
let external tools open a Claude Code session with a pre-filled prompt. Useful in environments where protocol handler registration is restricted or managed separately
"disable"
disabledMcpjsonServers
List of specific MCP servers from
.mcp.json
files to reject
["filesystem"]
disableMobileSimulatorTools
(Managed settings only) Set to
true
to block Claude’s tools for the desktop app’s
iOS Simulator pane
. Users keep manual use of the pane; only Claude’s access is removed. The value must be the JSON boolean
true
; any other value is ignored, and a malformed value such as
"true"
or
1
logs a warning
true
disableRemoteControl
Disable
Remote Control
: blocks
claude remote-control
, the
--remote-control
flag, auto-start, and the in-session toggle. Typically placed in
managed settings
for per-device MDM enforcement, but works from any scope
true
disableSideloadFlags
(Managed settings only) Reject the
--plugin-dir
,
--plugin-url
,
--agents
, and
--mcp-config
CLI flags at startup, which users could otherwise pass to bypass
strictKnownMarketplaces
for a single run. Also rejects these flags from any surface that spawns the CLI with them internally, currently
Cowork
local sessions in the desktop app. A
--mcp-config
whose servers are all in-process
type: "sdk"
entries is still accepted, so the Agent SDK and VS Code extension keep working. Doesn’t block
claude mcp add
,
.mcp.json
, or SDK
setMcpServers()
; pair with
allowedMcpServers
for per-server MCP control. Requires Claude Code v2.1.193 or later
true
disableSkillShellExecution
Disable inline shell execution for
!`...`
and
```!
blocks in
skills
and custom commands from user, project, plugin, or additional-directory sources. Commands are replaced with
[shell command execution disabled by policy]
instead of being run. Bundled and managed skills are not affected. Most useful in
managed settings
where users cannot override it
true
disableWorkflows
Default
:
false
. Disable
dynamic workflows
and the bundled workflow commands. Equivalent to setting
CLAUDE_CODE_DISABLE_WORKFLOWS
to
1
true
editorMode
Default
:
"normal"
. Key binding mode for the input prompt:
"normal"
or
"vim"
. Appears in
/config
as
Editor mode
"vim"
effortLevel
Persist the
effort level
across sessions. Accepts
"low"
,
"medium"
,
"high"
, or
"xhigh"
. Written automatically when you run
/effort
with one of those values.
--effort
and
CLAUDE_CODE_EFFORT_LEVEL
override this for one session. See
Adjust effort level
for supported models
"xhigh"
emojiCompletionEnabled
Default
:
true
. Show emoji suggestions when you type
:
plus a shortcode in the prompt input, and replace a completed shortcode such as
:heart:
with its emoji. Set to
false
to disable both. See
Emoji shortcodes
. Requires Claude Code v2.1.217 or later
false
enableAllProjectMcpServers
Automatically approve all MCP servers defined in project
.mcp.json
files. As of v2.1.196,
claude mcp list
and
claude mcp get
honor this key in an untrusted folder only from
settings files that aren’t checked into the repository
true
enableArtifact
Enable or disable the
Artifact
tool for this user. When unset, the default follows the feature’s
availability
for your account. The
Artifacts
row in
/config
writes this key. A managed
disableArtifact
and your organization’s
admin setting
take precedence, and the key is ignored in project and local settings (
.claude/settings.json
,
.claude/settings.local.json
), which a repository could otherwise commit. Requires Claude Code v2.1.196 or later
true
enabledMcpjsonServers
List of specific MCP servers from
.mcp.json
files to approve. As of v2.1.196,
claude mcp list
and
claude mcp get
honor this key in an untrusted folder only from
settings files that aren’t checked into the repository
["memory", "github"]
enforceAvailableModels
Extend the
availableModels
allowlist to the Default model. When
true
in managed settings and
availableModels
is a non-empty array, the Default option falls back to the first allowlisted entry that is available, but only when the model Default would resolve to (the
organization default
when one applies, otherwise the account-type default) is not in the allowlist; an allowlisted default is kept as-is. Has no effect when
availableModels
is unset or empty. See
Enforce the allowlist for the Default model
. Requires Claude Code v2.1.175 or later
true
env
Environment variables applied to every session and to subprocesses Claude Code spawns from it. Set a variable to
""
to override a shell export with an empty string, which Claude Code treats as unset for provider selection. Subprocesses still inherit the empty value.
NO_COLOR
and
FORCE_COLOR
set here reach only subprocesses; to change Claude Code’s own interface colors, set them in your shell before launching
claude
. Claude Code ignores identity variables set here that its hosting environments own, such as
CLAUDE_CODE_REMOTE
and
CLAUDE_CODE_ACCOUNT_UUID
. It also ignores
CLAUDE_CODE_MESSAGING_SOCKET
and
CLAUDE_CODE_MESSAGING_TOKEN
, which it exports itself. Ignoring the socket variable requires Claude Code v2.1.224 or later, and ignoring the token requires v2.1.228 or later
{"FOO": "bar"}
fallbackModel
Fallback model(s) to try in order when the primary model is overloaded or unavailable. Claude Code switches to the next available model in the chain for the rest of the turn and shows a notice.
"default"
expands to the default model. Chains are capped at three models; extra entries are ignored. Unlike most array settings, this key does not merge across settings files: the highest-precedence file that defines it supplies the entire chain. The
--fallback-model
flag overrides this for one session. See
Fallback model chains
["claude-sonnet-5", "claude-haiku-4-5"]
fastMode
Turn
fast mode
on for sessions where it’s available. Toggling with
/fast
writes
true
here in user settings and removes the key when you turn fast mode off
true
fastModePerSessionOptIn
When
true
, fast mode does not persist across sessions. Each session starts with fast mode off, requiring users to enable it with
/fast
. The user’s fast mode preference is still saved. See
Require per-session opt-in
true
feedbackSurveyRate
Probability (0–1) that the
session quality survey
appears when eligible. Set to
0
to suppress entirely, or set
CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY
in
env
. Useful when using Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry where the default sample rate does not apply
0.05
fileCheckpointingEnabled
Default
:
true
. Snapshot files before each edit so
/rewind
can restore them. Appears in
/config
as
Rewind code (checkpoints)
. To disable via environment variable, set
CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING
in
env
false
fileSuggestion
Configure a custom script for
@
file autocomplete. See
File suggestion settings
{"type": "command", "command": "~/.claude/file-suggestion.sh"}
footerLinksRegexes
Render extra clickable badges in the footer when a regex matches turn output. Each entry has a
pattern
, a
url
template with
{name}
placeholders filled from named capture groups, and an optional
label
. Read from user,
--settings
flag, and managed settings only. See
Footer link badges
for URL constraints, scheme allowlist, and limits. Requires Claude Code v2.1.176 or later
[{"type": "regex", "pattern": "\\b(?<key>PROJ-\\d+)\\b", "url": "https://issues.example.com/browse/{key}", "label": "{key}"}]
forceLoginMethod
Use
claudeai
to restrict login to claude.ai accounts,
console
to restrict login to Claude Console accounts, or
gateway
to restrict login to a cloud gateway; see
Claude apps gateway
. On Claude Code v2.1.212 or later, every first-party login path applies the restriction, including the
VS Code extension
, the Agent SDK,
claude setup-token
, and
/install-github-app
; before v2.1.212, only terminal logins applied it. See
Restrict login to your organization
for how each login path, environment credentials, and third-party providers are handled
claudeai
forceLoginGatewayUrl
Pre-fills and locks the gateway URL on the
/login
Cloud gateway screen. Either this key or
forceLoginMethod: "gateway"
surfaces that screen; set both so the URL is filled in. Honored only at the managed policy tier; ignored in user and project settings. See
Claude apps gateway
"https://claude-gateway.example.com"
forceLoginOrgUUID
Require claude.ai account logins to belong to a specific Anthropic organization. Accepts a single UUID string, which also pre-selects that organization during a claude.ai or Claude Console login, or an array of UUIDs where any listed organization is accepted without pre-selection. An empty array fails closed and blocks login with a misconfiguration message. See
Restrict login to your organization
for how Claude Code treats Claude Console logins, the other login paths, and environment credentials
"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
or
["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"]
forceRemoteSettingsRefresh
(Managed settings only) Block CLI startup until remote managed settings are freshly fetched from the server. If the fetch fails, the CLI exits rather than continuing with cached or no settings. When not set, startup continues without waiting for remote settings. See
fail-closed enforcement
true
gcpAuthRefresh
Custom script that refreshes GCP Application Default Credentials when they expire or cannot be loaded. See
advanced credential configuration
gcloud auth application-default login
hooks
Configure custom commands to run at lifecycle events. See
hooks documentation
for format
See
hooks
httpHookAllowedEnvVars
Allowlist of environment variable names HTTP hooks may interpolate into headers. When set, each hook’s effective
allowedEnvVars
is the intersection with this list. Undefined = no restriction. Arrays merge across settings sources. See
Hook configuration
["MY_TOKEN", "HOOK_SECRET"]
includeGitInstructions
Default
:
true
. Include built-in commit and PR workflow instructions and the git status snapshot in Claude’s system prompt. Set to
false
to remove both, for example when using your own git workflow skills. The
CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS
environment variable takes precedence over this setting when set
false
inputNeededNotifEnabled
Default
:
false
. When
Remote Control
is connected, send a push notification to your phone when a permission prompt or question is waiting for your input. Appears in
/config
as
Push when actions required
. See
Mobile push notifications
true
isolatePeerMachines
Require your explicit approval before Claude’s
SendMessage
reaches one of your sessions beyond this machine; see
cross-session messaging
. The approval prompt appears even in
bypassPermissions
mode
. A
true
from any settings scope applies, so a checked-in project file can turn the requirement on but not off. The cross-machine
SendMessage
approval requires Claude Code v2.1.224 or later
true
language
Configure Claude’s preferred response language (e.g.,
"japanese"
,
"spanish"
,
"french"
). Claude will respond in this language by default. Also sets the language for
voice dictation
and auto-generated session titles. As of v2.1.176, when not set, session titles match the language of your conversation
"japanese"
minimumVersion
Floor that prevents background auto-updates and
claude update
from installing a version below this one. Switching from the
"latest"
channel to
"stable"
via
/config
prompts you to stay on the current version or allow the downgrade. Choosing to stay sets this value. Also useful in
managed settings
to pin an organization-wide minimum. For a hard floor that blocks startup entirely, see
requiredMinimumVersion
"2.1.100"
model
Override the default model to use for Claude Code.
--model
and
ANTHROPIC_MODEL
override this for one session
"claude-sonnet-5"
modelOverrides
Map Anthropic model IDs to provider-specific model IDs such as Amazon Bedrock inference profile ARNs. Each model picker entry uses its mapped value when calling the provider API. See
Override model IDs per version
{"claude-opus-4-6": "arn:aws:bedrock:..."}
otelHeadersHelper
Script to generate dynamic OpenTelemetry headers. Runs at startup and periodically. Set the refresh interval with
CLAUDE_CODE_OTEL_HEADERS_HELPER_DEBOUNCE_MS
. See
Dynamic headers
/bin/generate_otel_headers.sh
outputStyle
Configure an output style to adjust the system prompt. See
output styles documentation
"Explanatory"
parentSettingsBehavior
(Managed settings only)
Default
:
"first-wins"
. Controls whether Claude Code applies managed settings supplied by an embedding host process, such as the Agent SDK or an IDE extension, when an admin-deployed managed tier is also present. With
"first-wins"
, Claude Code drops the parent-supplied settings. With
"merge"
, Claude Code applies them under the admin tier through a restrictive-only filter. For the filter’s limits and how the managed sources interact, see
Parent settings from embedding hosts
and
Restrict parent settings
"merge"
permissions
See table below for structure of permissions.
plansDirectory
Default
:
~/.claude/plans
. Customize where plan files are stored. Path is relative to project root.
"./plans"
pluginSuggestionMarketplaces
(Managed settings only) Marketplace names whose plugins can appear as contextual install suggestions. No marketplace-declared suggestions surface without this allowlist; the built-in first-party frontend-design tip is unaffected. Suggestions come from each plugin’s
relevance
declaration in its marketplace entry. A name only takes effect when the marketplace is registered on the machine and its registered source is also declared in managed settings, either as the
extraKnownMarketplaces
entry for that name or as an entry of
strictKnownMarketplaces
. A marketplace registered from a different source under an allowlisted name is ignored. The official marketplace is exempt from the source requirement: allowlisting its name alone suffices, since that name can only register from the official Anthropic source.
["acme-corp-plugins"]
pluginTrustMessage
(Managed settings only) Custom message appended to the plugin trust warning shown before installation. Use this to add organization-specific context, for example to confirm that plugins from your internal marketplace are vetted.
"All plugins from our marketplace are approved by IT"
policyHelper
Admin-deployed executable that computes managed settings dynamically at startup. Only honored from MDM or a system
managed-settings.json
file. See
Compute managed settings with a policy helper
{"path": "/usr/local/bin/claude-policy"}
preferredNotifChannel
Default
:
"auto"
. Method for task-complete and permission-prompt notifications:
"auto"
,
"terminal_bell"
,
"iterm2"
,
"iterm2_with_bell"
,
"kitty"
,
"ghostty"
, or
"notifications_disabled"
.
"auto"
sends a desktop notification in iTerm2, Ghostty, and Kitty and does nothing in other terminals. Set
"terminal_bell"
to ring the bell character in any terminal. Appears in
/config
as
Notifications
. See
Get a terminal bell or notification
"terminal_bell"
prefersReducedMotion
Reduce or disable UI animations (spinners, shimmer, flash effects) for accessibility
true
processWrapper
Corporate launcher command placed in front of the
background processes Claude Code starts
. Honored from managed settings, a
--settings
file, and user settings only; the
CLAUDE_CODE_PROCESS_WRAPPER
environment variable takes precedence when both are set. See
Run Claude Code behind a corporate launcher
for the launcher contract. Requires Claude Code v2.1.210 or later
"/opt/corp/launcher --profile claude"
promptSuggestionEnabled
Default
:
true
. Show
prompt suggestions
, the grayed-out predictions that appear in your prompt input. Set to
false
or turn off
Prompt suggestions
in
/config
to disable.
CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION
takes precedence when both are set
false
prUrlTemplate
URL template for the PR badge shown in the footer and in tool-result summaries. Substitutes
{host}
,
{owner}
,
{repo}
,
{number}
, and
{url}
from the
gh
-reported PR URL. Use to point PR links at an internal code-review tool instead of
github.com
. Does not affect
#123
autolinks in Claude’s prose
"https://reviews.example.com/{owner}/{repo}/pull/{number}"
remote.defaultEnvironmentId
Default
cloud environment
for cloud sessions you create from the CLI, such as with
claude --cloud
. Written to user settings when you pick an environment with
/remote-env
. For Anthropic-hosted environment IDs (
env_...
), follows the standard settings precedence, so a value in a repo’s project settings overrides the user-level pick. A
self-hosted environment
ID (
ccpool_...
) is honored only from user settings, managed settings, and the
--settings
CLI flag; Claude Code ignores one in a repo’s project or local settings with a warning, so a checked-in file can’t steer sessions onto a self-hosted environment you didn’t choose
"env_0123abcd"
remoteControlAtStartup
Connect
Remote Control
automatically when each interactive session starts, instead of waiting for
/remote-control
. Set to
true
to turn auto-connect on,
false
to turn it off, or leave unset to follow your organization’s admin default if one is set, and otherwise Claude Code’s current default. Appears in
/config
as
Enable Remote Control for all sessions
. Claude Code ignores a
true
from project or local settings; for the full per-scope behavior, see
Enable Remote Control for all sessions
and the
exceptions to managed settings precedence
false
requiredMaximumVersion
Managed settings only. Maximum Claude Code version allowed to start. If the running version is newer, Claude Code exits at startup and instructs the user to install an approved version through the organization’s approved method;
claude install <version>
may also work. Background auto-updates and
claude update
skip versions above the ceiling, so an in-range installation stays in range.
claude update
,
claude install
, and
claude doctor
keep working above the ceiling so users can recover. Versions that predate this setting ignore it
"2.1.150"
requiredMinimumVersion
Managed settings only. Minimum Claude Code version required to start. If the running version is older, Claude Code exits at startup and instructs the user to update through the organization’s approved method.
claude update
,
claude install
, and
claude doctor
keep working below the floor so users can recover. Differs from
minimumVersion
, which prevents downgrades but never blocks startup. Versions that predate this setting ignore it
"2.1.150"
respectGitignore
Default
:
true
. Control whether the
@
file picker respects
.gitignore
patterns. When
true
, files matching
.gitignore
patterns are excluded from suggestions
false
respondToBashCommands
Default
:
true
. Whether Claude responds after an input-box
!
shell command runs. Set to
false
to add the command output to context without a response. See
Shell mode with
!
prefix
. Requires Claude Code v2.1.186 or later
false
showClearContextOnPlanAccept
Default
:
false
. Show the “clear context” option on the plan accept screen. Set to
true
to restore the option
true
showThinkingSummaries
Default
:
false
. Show
extended thinking
summaries in interactive sessions. When unset or
false
, thinking blocks are redacted by the API and shown as a collapsed stub. Redaction only changes what you see, not what the model generates: to reduce thinking spend,
lower the budget or disable thinking
instead. This setting has no effect in non-interactive mode (
-p
), the Agent SDK, or IDE extensions such as VS Code
true
showTurnDuration
Default
:
true
. Show turn duration mes

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
code-improver (Suggest code improvements)
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
Directories added with
--add-dir
are also scanned: a
.claude/agents/
folder inside an added directory loads alongside project subagents. See
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
for the system prompt, equivalent to the markdown body in file-based subagents.
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
: when spawning a teammate, you can reference a subagent type and the teammate uses its
tools
and
model
, with the definition’s body appended to the teammate’s system prompt as additional instructions. See
agent teams
for which frontmatter fields apply on that path.
​
Write subagent files
Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown:
Claude Code watches
~/.claude/agents/
and
.claude/agents/
. When you add or edit a subagent file on disk, or ask Claude to write one for you, Claude Code detects the change within a few seconds and the next delegation uses the updated definition, with no restart needed.
Two cases still need a restart:
The watcher covers only directories that existed when the session started, so after creating a scope’s first agent file in a new
agents
directory, restart to load it.
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
Maximum number of agentic turns before the subagent stops
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
servers that aren’t available in the main conversation. Inline servers defined here are connected when the subagent starts and disconnected when it finishes. String references share the parent session’s connection.
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
and settings files. In
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
, connector tools
your organization set to
ask
, and MCP tools marked
requiresUserInteraction
are denied even if you’ve allowed them
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
Even in this mode, some operations still prompt:
Explicit
ask
rules
Connector tools
your organization set to
ask
MCP tools marked
requiresUserInteraction
Root and home directory removals such as
rm -rf /
The
isolatePeerMachines
approval for messages beyond this machine
See
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
. While you type this form the typeahead shows file matches rather than agents. The agent mention still resolves when you submit.
Run the whole session as a subagent.
Pass
--agent <name>
to start a session where the main thread itself takes on that subagent’s system prompt, tool restrictions, and model:
claude
--agent
code-reviewer
The subagent’s system prompt replaces the default Claude Code system prompt entirely, the same way
--system-prompt
does.
CLAUDE.md
files and project memory still load through the normal message flow. The agent name appears as
@<name>
in the startup header so you can confirm it’s active.
This works with built-in and custom subagents, and the choice persists when you resume the session: Claude Code restores the agent’s system prompt, tool restrictions, and model along with the conversation. If the agent no longer exists when you resume, the session continues with the default tools and system prompt and shows a
warning naming the agent
.
For a plugin-provided subagent, you can pass only the agent name and Claude Code finds it:
claude
--agent
security-reviewer
If multiple plugins provide agents with the same name, pass the scoped name to disambiguate:
claude
--agent
my-plugin:security-reviewer
If the plugin places the agent in a subfolder of its
agents/
directory, include the subfolder in the scoped name, for example
claude --agent my-plugin:review:security
.
To make it the default for every session in a project, set
agent
in
.claude/settings.json
:
{
"agent"
:
"code-reviewer"
}
The CLI flag overrides the setting if both are present.
​
Run subagents in foreground or background
Subagents can run in the foreground or the background:
Foreground subagents
block the main conversation until complete. Permission prompts are passed through to you as they come up.
Background subagents
run concurrently while you continue working. As of v2.1.186, when a background subagent reaches a tool call that needs permission, the prompt surfaces in your main session and names the subagent that is asking. Approve to let the subagent continue, or press Esc to deny that one tool call without stopping the subagent. Before v2.1.186, background subagents auto-denied any tool call that would have prompted.
For each subagent Claude spawns, Claude Code picks the mode from the first of these cases that applies:
If you set
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS
to
1
, Claude Code runs the subagent in the foreground, in every kind of session and whether or not fork mode is on.
If an in-process
agent team
teammate spawned the subagent, Claude Code runs it in the foreground.
Where
fork mode
is on, as it is by default in an interactive session, Claude Code runs the subagent in the background, forks and non-fork subagents alike, and Claude can’t ask for the foreground.
Where fork mode is off, Claude runs the subagent in the background by default and in the foreground when it needs the result before continuing. Fork mode is off in
non-interactive mode
with
-p
and in the Agent SDK unless you turn it on. To keep a particular subagent in the background even when Claude wants the result, set its frontmatter
background
field to
true
.
Background subagents run with a
smaller built-in tool set
than foreground subagents, except for conversation forks, and they surface every permission prompt in your main session.
A background subagent’s results reach Claude as a completion notification in a later turn. Claude waits for that notification before reporting the subagent’s results, and if you ask about progress first, it reports that the subagent is still running. Before v2.1.211, Claude sometimes reported results for a background subagent that hadn’t finished.
You can also steer this yourself:
Where fork mode is off, ask Claude to run a task in the background or in the foreground
Press
Ctrl+B
to background a running task
Claude Code clears a background subagent’s row from the subagent panel below the prompt input in one of two ways, depending on how the 

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
Hooks are user-defined shell commands, HTTP endpoints, or LLM prompts that execute automatically at specific points in Claude Code’s lifecycle. Hooks run wherever Claude Code runs: sessions in the terminal, IDE extensions, the
Desktop app
, and
Claude Code on the web
all fire the same hook events. Use this reference to look up event schemas, configuration options, JSON input/output formats, and advanced features like async hooks, HTTP hooks, and MCP tool hooks.
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
Elicitation
When an MCP server requests user input during a tool call
ElicitationResult
After a user responds to an MCP elicitation, before the response is sent back to the server
SessionEnd
When a session terminates
​
How a hook resolves
To see how these pieces fit together, consider this
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
; hooks there come from the repo and from your organization’s server-managed settings. See
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
See
Hook configuration
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
bypass_permissions_disabled
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
The matcher runs against a field from the
JSON input
that Claude Code sends to your hook on stdin. For tool events, that field is
tool_name
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
Handlers run in the current directory with Claude Code’s environment. The
$CLAUDE_CODE_REMOTE
environment variable is set to
"true"
in remote web environments and not set in the local CLI. As of v2.1.199,
$CLAUDE_CODE_BRIDGE_SESSION_ID
is set to the
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
Seconds before canceling. Defaults: 600 for
command
,
http
, and
mcp_tool
; 30 for
prompt
; 60 for
agent
.
UserPromptSubmit
lowers the
command
,
http
, and
mcp_tool
default to 30, and
MessageDisplay
lowers it to 10.
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
, runs once per session then is removed. Only honored for hooks declared in
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
Bash(git push *)
echo $(date)
yes
patterns that specify more than the command name run the hook anyway on
$()
, backticks, or
$VAR
The filter also fails open, running your hook regardless of pattern, when the Bash command can’t be parsed. Because the
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
, runs in the background and wakes Claude on exit code 2. Implies
async
. The hook’s stderr, or stdout if stderr is empty, is shown to Claude as a system reminder so it can react to a long-running background failure
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
: the project root. Claude Code also sets this variable in the environment of
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
: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session, on turns after the skill’s own turn as well. To have Claude Code run a hook a single time instead, set
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
Built-in Hooks
: registered internally by Claude Code
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
set at the managed settings level can disable managed hooks.
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
field holding the active
effort level
for the turn:
"low"
,
"medium"
,
"high"
,
"xhigh"
, or
"max"
. If the requested model effort exceeds what the current model supports, this is the downgraded level the model actually used. Ultracode is not a distinct level and reports as
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
field, and it is not guaranteed to be present. There is no
$CLAUDE_MODEL
environment variable. A hook process inherits the parent environment, so it can read
$ANTHROPIC_MODEL
if you set it in your shell, but that value doesn’t change when you switch models with
/model
during a session. One set of variables is not inherited: Claude Code
removes
OTEL_*
exporter variables from every subprocess it spawns
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
Exit 0 means success, and is the intended exit code when you print JSON for structured control. For most events, stdout is written to the debug log but not shown in the transcript. The exceptions are
UserPromptSubmit
,
UserPromptExpansion
, and
SessionStart
, where Claude Code adds plain-text stdout as context that Claude can see and act on.
Whether Claude Code reads your stdout as
JSON output
or as plain text depends on its first character, ignoring leading whitespace:
Starts with
{
: Claude Code parses it as JSON. If it isn’t valid JSON, Claude Code treats it as plain text.
Starts with anything else
: Claude Code treats it as plain text, a JSON array or a quoted JSON string included.
For events that use the standard decision model, exit 0 with a parsed object that fails schema validation is a non-blocking error: the action proceeds, and the transcript shows a
<hook name> hook error
notice with the validation message. The same happens on any exit code other than 2, while
exit 2 still blocks
.
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
. For most hook events, the action proceeds. When you set up a policy hook, watch for this notice on its first run: a mistyped path in
settings.json
leaves the gate silently disabled.
For most hook events, exit code 2 is the only exit code that blocks through the code alone. Without valid JSON on stdout, Claude Code treats exit code 1 as a non-blocking error and proceeds with the action, even though 1 is the conventional Unix failure code. If your hook is meant to enforce a policy, use
exit 2
. The exception is
WorktreeCreate
, where any non-zero exit code aborts worktree creation.
​
Timeouts
A
command
,
http
, or
mcp_tool
hook that reaches its
timeout
is canceled: Claude Code discards the hook’s output, and the hook renders no decision. On
PreToolUse
, the two hook families differ:
A timed-out
command
,
http
, or
mcp_tool
hook doesn’t block the tool call. The call continues through the normal
permission flow
, so don’t count on a stalled hook to act as a gate.
An
Agent SDK callback hook
that exceeds its timeout
blocks the tool call
.
​
Exit code 2 behavior per event
Exit code 2 is the way a hook signals “stop, don’t do this.” The effect depends on the event, because some events represent actions that can be blocked (like a tool call that hasn’t happened yet) and others represent things that already happened or can’t be prevented.
Hook event
Can block?
What happens on exit 2
PreToolUse
Yes
Blocks the tool call
PermissionRequest
No
Exit code 2 isn’t honored for this event and the permission flow proceeds unchanged. Deny through the
decision
object
instead
UserPromptSubmit
Yes
Blocks prompt processing and erases the prompt
UserPromptExpansion
Yes
Blocks the expansion
Stop
Yes
Prevents Claude from stopping, continues the conversation
SubagentStop
Yes
Prevents the subagent from stopping
TeammateIdle
Yes
Prevents the teammate from going idle, so it continues working
TaskCreated
Yes
Rolls back the task creation
TaskCompleted
Yes
Prevents the task from being marked as completed
ConfigChange
Yes
Blocks the configuration change from taking effect (except
policy_settings
)
StopFailure
No
Output and exit code are ignored, except
terminalSequence
PostToolUse
No
Shows stderr to Claude; the tool already ran
PostToolUseFailure
No
Shows stderr to Claude; the tool already failed
PostToolBatch
Yes
Stops the agentic loop before the next model call
PermissionDenied
No
Exit code and stderr are ignored because the denial already occurred. Use JSON
hookSpecificOutput.retry: true
to tell the model it may retry; Claude Code ignores
retry: true
for
no-verdict denials
Notification
No
Exit code and stderr are ignored
SubagentStart
No
Shows stderr to user only
SessionStart
No
Shows stderr to user only
Setup
No
Shows stderr to user only
SessionEnd
No
Shows stderr to user only
CwdChanged
No
Shows stderr to user only
DirectoryAdded
No
Stderr goes to the debug log; the directory is already added
FileChanged
No
Shows stderr to user only
PreCompact
Yes
Blocks compaction
PostCompact
No
Shows stderr to user only
Elicitation
Yes
Denies the elicitation
ElicitationResult
Yes
Blocks the response (action becomes decline)
WorktreeCreate
Yes
Any non-zero exit code causes worktree creation to fail
WorktreeRemove
No
Failures are logged in debug mode only
InstructionsLoaded
No
Exit code is ignored
MessageDisplay
No
The original text is displayed
For
SessionStart
,
Setup
, and
SubagentStart
, the exit code 2 stderr renders in the transcript as a
<hook name> hook error
notice, the same way a
non-blocking error
does. Claude doesn’t see it, and the session or subagent proceeds. For
SubagentStart
, the notice appears in the subagent’s own transcript, not in the parent conversation.
​
HTTP response handling
HTTP hooks use HTTP status codes and response bodies instead of exit codes and stdout. The outcomes below apply to most events; an event with its own failure contract in the
per-event table
, such as
WorktreeCreate
, applies that contract to a failed HTTP hook too:
2xx with an empty body
: success, equivalent to exit code 0 with no output
2xx with a JSON object body
: parsed using the same
JSON output
schema as command hooks. A body that fails schema validation is a non

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
”Yes, don’t ask again” behavior
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
When you choose “Yes, don’t ask again” and the approval saves permanently, such as for a Bash command, Claude Code saves the rule to
.claude/settings.local.json
at the root of the git repository, resolved through
worktrees
to the main checkout. The rule applies to future sessions anywhere in that repository, including sessions started in subdirectories and in worktrees. A file-modification approval isn’t saved to the file: as the table shows, it lasts until the session ends. Outside a git repository, and when the repository root is your home directory, Claude Code saves the rule in the directory you started it from.
Before v2.1.211, Claude Code always saved the rule in the starting directory, so an approval granted in a worktree or subdirectory didn’t apply to the rest of the repository. Rules that earlier versions saved in a subdirectory or worktree still apply to sessions started there.
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
Manage permissions
You can view and manage Claude Code’s tool permissions with
/permissions
. This UI lists all permission rules and the
settings.json
file each rule comes from.
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
, connector tools
your organization set to
ask
, and MCP tools marked
requiresUserInteraction
are denied even if you’ve allowed them
bypassPermissions
Skips permission prompts, except those forced by explicit
ask
rules, connector tools
your organization set to
ask
, and MCP tools marked
requiresUserInteraction
. Root and home directory removals such as
rm -rf /
also still prompt as a circuit breaker, and the
cross-session messaging safeguards
still apply
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
A few prompts still fire in this mode. Explicit
ask
rules, connector tools
your organization set to
ask
, and MCP tools marked
requiresUserInteraction
still prompt. Removals targeting the filesystem root or home directory, such as
rm -rf /
and
rm -rf ~
, also prompt as a circuit breaker against model error, including when the command contains command substitution with
$(...)
or backticks, or process substitution with
<(...)
.
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
Deny and ask rules can match a top-level input parameter on any tool with
Tool(param:value)
. The rule matches when Claude calls the tool with that parameter set to that exact value. An allow rule for one parameter value wouldn’t establish that the call is safe overall, so allow rules continue to use each tool’s own specifier syntax. This works for any scalar parameter the tool accepts:
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
Bash rules support glob patterns with
*
. This configuration allows npm and git commit commands while blocking git push:
{
"permissions"
: {
"allow"
: [
"Bash(npm run *)"
,
"Bash(git commit *)"
,
"Bash(git * main)"
,
"Bash(* --version)"
,
"Bash(* --help *)"
],
"deny"
: [
"Bash(git push *)"
]
}
}
The
:*
suffix is an equivalent way to write a trailing wildcard, so
Bash(ls:*)
matches the same commands as
Bash(ls *)
.
The permission dialog writes the space-separated form when you select “Yes, don’t ask again” for a command prefix. The
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
Bash permission rules support wildcard matching with
*
. Wildcards can appear at any position in the command, including at the beginning, middle, or end:
Bash(npm run build)
matches the exact Bash command
npm run build
Bash(npm run test *)
matches Bash commands starting with
npm run test
Bash(npm *)
matches any command starting with
npm
Bash(* install)
matches any command ending with
install
Bash(git * main)
matches commands like
git checkout main
and
git log --oneline main
A single
*
matches any sequence of characters including spaces, so one wildcard can span multiple arguments.
Bash(git *)
matches
git log --oneline --all
, and
Bash(git * main)
matches
git push origin main
as well as
git merge main
.
When
*
appears at the end with a space before it (like
Bash(ls *)
), it enforces a word boundary, requiring the prefix to be followed by a space or end-of-string. For example,
Bash(ls *)
matches
ls -la
but not
lsof
. In contrast,
Bash(ls*)
without a space matches both
ls -la
and
lsof
because there’s no word boundary constraint.
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
When you approve a compound command with “Yes, don’t ask again”, Claude Code saves a separate rule for each subcommand that requires approval, rather than a single rule for the full compound string. For example, approving
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
<project root>/src/**/*.ts
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
<project root>/path
Local settings at
.claude/settings.local.json
<original cwd>/path
User settings at
~/.claude/settings.json
~/.claude/path
A file passed with
--settings <file>
<directory of file>/path
CLI flags,
/permissions
, or session rules
<original cwd>/path
Local settings rules anchor at the directory you started Claude Code from, not at the repository root where Claude Code
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
<project>/docs/
, not
/docs/
or
<project>/.claude/docs/
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
When you approve a file path with “Yes, don’t ask again”, Claude Code escapes gitignore pattern characters in that path, such as
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
matches every domain and is equivalent to a bare
WebFetch
rule
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
, allow rules for that tool don’t take effect: Claude Code prompts on every call, even in
auto
and
bypassPermissions
modes. In
dontAsk
mode, which never prompts, Claude Code denies the call instead. Connector tools appear as
mcp__claude_ai_<server>__<tool>
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
Connector tools
your organization set to
ask
and MCP tools marked
requiresUserInteraction
also still prompt when a hook returns
"allow"
.
A blocking hook also takes precedence over allow rules. A hook that exits with code 2 stops the tool call before permission rules are evaluated, so the block applies even when an allow rule would otherwise let the call proceed. To run all Bash commands without prompts except for a few you want blocked, add
"Bash"
to your allow list and register a PreToolUse hook that rejects those specific commands. See
Block edits to protected files
for a hook script you can adapt.
​
Working directories
By default, Claude has access to files in the directory where you launched it. You can extend this access:
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
To change the session’s primary working directory instead of adding another, use
/cd
. The
/cd
command requires Claude Code v2.1.169 or later. Unlike
/add-dir
, it relocates the session: the new directory’s
CLAUDE.md
is loaded and
--resume
finds the session from there.
​
Additional directories grant file access, not configuration
Adding a directory extends where Claude can read and edit files. It doesn’t make that directory a full configuration root: most
.claude/
configuration is not discovered from additional directories, though a few types are loaded as exceptions.
These exceptions apply only to directories added with the
--add-dir
flag or the
/add-dir
command. Directories listed in
permissions.additionalDirectories
in a settings file grant file access only and don’t load any of the configuration below.
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
Yes. When the added directory and your project both define a command with the same name, Claude Code runs your project’s command
Subagents
in
.claude/agents/
Yes
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
loads from the git repository root instead, even when you start Claude Code in a subdirectory; before v2.1.211, it too loaded only from the current working directory.
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
Network restrictions combine WebFetch permission rules with the sandbox’s
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
commands that target
/
, your home directory, or other critical system paths still go through the regular permission flow
Commands that won’t run sandboxed, such as excluded commands, respect the bare
Bash
ask rule as usual. See
sandbox modes
to change this behavior.
​
Managed settings
For organizations that need centralized control over Claude Code configuration, administrators can deploy managed settings that can’t be overridden by user or project settings, apart from a few
security-sensitive keys
. These policy settings follow the same format as regular settings files and can be delivered through MDM/OS-level policies, managed settings files,
server-managed settings
, or a self-hosted
Claude apps gateway
. See
settings files
for delivery mechanisms and file locations.
​
Managed-only settings
The following settings are only read from managed settings. Placing them in user or project settings files has no effect.
Setting
Description
allowAllClaudeAiMcps
When
true
, the claude.ai connectors Claude Code fetches itself load alongside a deployed
managed-mcp.json
instead of being suppressed by its exclusive control. Connectors delivered to cloud sessions stay suppressed. See
Managed MCP configuration
allowedChannelPlugins
Allowlist of channel plugins that may push messages. Replaces the default Anthropic allowlist when set. Requires
channelsEnabled: true
. See
Restrict which channel plugins can run
allowManagedHooksOnly
When
true
, restricts which hooks run; see
Hook configuration
for the full effect list
allowManagedMcpServersOnly
When
true
, only
allowedMcpServers
from managed settings are respected.
deniedMcpServers
still merges from all sources. See
Managed MCP configuration
allowManagedPermissionRulesOnly
When
true
, prevents user and project settings from defining
allow
,
ask
, or
deny
permission rules. Only rules in managed settings apply. Doesn’t affect the MCP server allowlist; for that, set
allowManagedMcpServersOnly
blockedMarketplaces
Blocklist of marketplace sources. Blocked sources are checked before downloading, so they never touch the filesystem. See
managed marketplace restrictions
channelsEnabled
Allow
channels
for the organization. See
enterprise controls
for the default on each plan
disableCommandPluginSources
When
true
, blocks
command
plugin sources
entirely, so the marketplace-declared command never runs. When unset, follows
allowManagedHooksOnly
. Requires Claude Code v2.1.229 or later
disableSideloadFlags
Reject the
--plugin-dir
,
--plugin-url
,
--agents
, and
--mcp-config
CLI flags at startup. Without this, users can bypass
strictKnownMarketplaces
for a single run by passing these flags. See
disableSideloadFlags
. Requires Claude Code v2.1.193 or later
forceRemoteSettingsRefresh
When
true
, blocks CLI startup until remote managed settings are freshly fetched and exits if the fetch fails. See
fail-closed enforcement
pluginTrustMessage
Custom message appended to the plugin trust warning shown before installation
sandbox.filesystem.allowManagedReadPathsOnly
When
true
, only
filesystem.allowRead
paths from managed settings are respected.
denyRead
still merges from all sources
sandbox.network.allowManagedDomainsOnly
When
true
, only
allowedDomains
and
WebFetch(domain:...)
allow rules from managed settings are respected. Non-allowed domains are blocked automatically without prompting the user. Denied domains still merge from all sources
strictKnownMarketplaces
Controls which plugin marketplace sources users can add and install plugins from. See
managed marketplace restrictions
strictPluginOnlyCustomization
Block skills, agents, hooks, and MCP servers from user and project sources, so they can only come from plugins or managed settings.
true
locks all four surfaces; an array such as
["skills", "hooks"]
locks only the named ones. See
strictPluginOnlyCustomization
wslInheritsWindowsSettings
When
true
in the Windows HKLM registry key or
C:\Program Files\ClaudeCode\managed-settings.json
, WSL reads managed settings from the Windows policy chain in addition to
/etc/claude-code
. See
Settings files
disableBypassPermissionsMode
is typically placed in managed settings to enforce organizational policy, but it works from any scope. A user can set it in their own settings to lock themselves out of bypass mode.
On Team and Enterprise plans, an Owner enables or disables
Remote Control
and
web sessions
organization-wide in
Claude Code admin settings
. Remote Control can additionally be disabled per device with the
disableRemoteControl
setting. Web sessions have no per-device managed settings key.
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
Claude Code saves trust per workspace, keyed on the git repository root or, outside a repository, the directory you started Claude Code from. When you start in your home directory, trust is held for the current session only and isn’t written to disk; see the
additional safeguards
note.
Claude Code shows the trust dialog in interactive sessions only. A
claude -p
run or an SDK session never shows it, and trusting a parent folder doesn’t count for these rules, so
What runs before you trust a folder
says which repository content Claude Code still uses in each of those two situations.
​
When your local settings file needs trust
.claude/settings.local.json
is normally your own file, so its allow rules and additional directories apply without the trust step. Claude Code treats the file as repository-supplied instead, and holds its rules until you trust the folder, when the file is tracked in git or
.claude
is a symlink.
Claude Code runs git to tell the two apart, and it runs git in a folder only after you accept a trust dialog for that folder or one of its parents, or in a
-p
or SDK session, which counts as accepted. Until then it holds the file’s rules like project settings, with one exception: in your own configuration home, meaning your home directory or any directory whose
.claude
subdirectory you’ve set as
CLAUDE_CONFIG_DIR
, the file applies right away without running git. Once the check has run, an untracked file, or one in a directory that isn’t inside a git repository, applies even though you haven’t trusted that exact folder.
Versions 2.1.196 through 2.1.199 held the file’s rules in your configuration home and outside git repositories too, and printed the
this workspace has not been trusted
warning there. Before v2.1.207, an untracked file applied before you accepted the dialog.
​
What runs before you trust a folder
Each row is one kind of content a repository can supply. The columns are the two situations in which you haven’t trusted the folder itself: you trusted only a parent folder, or you ran
claude -p
or the SDK there, which never shows the trust dialog.
What the repository supplies
You trusted only a parent folder
claude -p
or the SDK, folder never trusted
Hooks
in settings files, the
env
block and helper commands such as
apiKeyHelper
, and a project skill’s
hooks
and
allowed-tools
Used
Used. Workspace trust never gates a skill’s
allowed-tools
in any session
permissions.allow
rules and
additionalDirectories
in
.claude/settings.json
Not used until you accept the trust dialog, which appears again listing them
Not used. Claude Code prints a
this workspace has not been trusted
warning to stderr
Frontmatter hooks in a project
subagent
, a project
@skills-dir
plugin
, and
extraKnownMarketplaces
entries from the repository or an
--add-dir
directory
Not used, and no dialog is offered
Not used
Servers in
.mcp.json
, including ones the repository
approves in its own settings
, and any
headersHelper
they define, which runs when its server connects
Claude Code asks you before connecting them. The repository’s own approvals don’t count
Connected without asking, approved or not. The SDK loads them only when
settingSources
includes project settings.
claude mcp list
in the same folder still reports such a server as pending
For the rows that need this exact folder trusted and offer no dialog, trust it by hand: set
projects["<path>"].hasTrustDialogAccepted
to
true
in
~/.claude.json
, where
<path>
is the repository root, or the folder itself outside a repository. The debug log line for a skipped subagent hook and the stderr warning for skipped allow rules both print the exact key.
Before you run
claude -p
in a repository you didn’t write, decide what it may run on your machine:
Pass
--setting-sources user
, or set the SDK’s
settingSources
without project settings, so Claude Code reads neither the project’s settings files nor its
.mcp.json
Start with
--bare
so Claude Code reads no hooks, skills, plugins, or
.mcp.json
servers from the project. The project’s
env
block and helpers such as
awsAuthRefresh
in its settings files still apply, and Claude Code reads
apiKeyHelper
only from
--settings
Pass
--settings '{"disableAllHooks": true}'
to
turn hooks off
for that run. Setting it in your user settings alone isn’t enough, because the repository’s project settings take precedence over yours and can set it back to
false
Add a
disabledMcpjsonServers
entry to reject a
.mcp.json
server by name in every session type
​
Example configurations
This
repository
includes starter settings configurations for common deployment scenarios. Use these as starting points and adjust them to fit your needs.
​
See also
Settings
: complete configuration reference including the permission settings table
Configure auto mode
: tell the auto mode classifier which infrastructure your organization trusts
Sandboxing
: OS-level filesystem and network isolation for Bash commands
Authentication
: set up user access to Claude Code
Security
: security safeguards and best practices
Hooks
: automate workflows and extend permission evaluation
Was this page helpful?
Yes
No
⌘
I
Assistant
Responses are generated using AI and may contain mistakes.

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
Agent teams let you coordinate multiple Claude Code instances working together. One session acts as the team lead, coordinating work, assigning tasks, and synthesizing results. Teammates work independently, each in its own context window, and communicate directly with each other.
Unlike
subagents
, which run within a single session and can only report back to the main agent, you can also interact with individual teammates directly without going through the lead.
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
let you parallelize work, but they operate differently. Choose based on whether your workers need to communicate with each other. For separate sessions that pass messages to each other without a team, see
cross-session messaging
.
Subagents only report results back to the main agent and never talk to each other. In agent teams, teammates share a task list, claim work, and communicate directly with each other.
Subagents
Agent teams
Context
Own context window; results return to the caller
Own context window; fully independent
Communication
Report results back to the main agent only
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
: interrupt the selected teammate’s current turn
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
Teammates don’t inherit the lead’s
/model
selection by default. To change the model used when the prompt doesn’t specify one, set
Default teammate model
in
/config
. Pick
Default (leader’s model)
to have teammates follow the lead’s current model.
Claude Code checks each teammate’s model, whether requested in your prompt or set through
Default teammate model
, against your organization’s
availableModels
allowlist. When the allowlist blocks a value, Claude Code substitutes another model:
Family alias such as
opus
: On the Anthropic API and Claude Platform on AWS, Claude Code runs the teammate on the newest version of that family the allowlist permits. On providers with provider-specific model IDs, where the
substitution doesn’t operate
, a blocked alias falls back like any other blocked value per the next bullet
Any other blocked value, including a family alias on providers where the substitution doesn’t operate or whose family has no permitted version
: Claude Code uses the default teammate model. When the blocked value is the
Default teammate model
setting itself, Claude Code uses your provider’s default Opus model, or the lead’s model when the allowlist blocks that too
Teammates inherit the lead’s
effort level
. In split-pane mode this applies from v2.1.186; earlier versions did not pass the lead’s session effort to split-pane teammates.
​
Require plan approval for teammates
For complex or risky tasks, you can require teammates to plan before implementing. The teammate works in read-only plan mode until the lead approves their approach:
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.
When a teammate finishes planning, it sends a plan approval request to the lead. The lead reviews the plan and either approves it or rejects it with feedback. If rejected, the teammate stays in plan mode, revises based on the feedback, and resubmits. Once approved, the teammate exits plan mode and begins implementation.
The lead makes approval decisions autonomously. To influence the lead’s judgment, give it criteria in your prompt, such as “only approve plans that include test coverage” or “reject plans that modify the database schema.”
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
To use a subagent definition, mention it by name when asking Claude to spawn the teammate:
Spawn a teammate using the security-reviewer agent type to audit the auth module.
The teammate honors that definition’s
tools
allowlist and
model
, and the definition’s body is appended to the teammate’s system prompt as additional instructions rather than replacing it. For an in-process teammate, Claude Code adds
SendMessage
to that allowlist. In a
session that has the Task tools
, Claude Code adds
TaskCreate
,
TaskGet
,
TaskList
, and
TaskUpdate
to it too.
The
skills
and
mcpServers
frontmatter fields in a subagent definition are not applied when that definition runs as a teammate. Teammates load skills and MCP servers from your project and user settings, the same as a regular session.
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
: when a teammate finishes and stops, it automatically notifies the lead. The notification doesn’t carry the teammate’s output; a teammate shares results by messaging the lead or updating the shared task list. As of v2.1.198, a teammate whose turn ends on an API error notifies the lead that it failed and includes the error text, instead of appearing to finish normally.
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
Scale up only when the work genuinely benefits from having teammates work simultaneously. Three focused teammates often outperform five scattered ones.
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
, so this can happen during delegation you never framed as team work. Subagents and teammates report back differently:
Subagents
: Claude receives the subagent’s result when it completes.
Teammates
: the
idle notification
reports that the teammate stopped, without its output.
An orchestration flow that waits on subagent results can stall. To make named subagents launch as subagents again, turn agent teams off by setting
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
: an in-process teammate’s own subagents run in the foreground. Asking for a background one, whether with
run_in_background
or a subagent definition that sets
background: true
, returns an error, because a teammate’s background work can’t outlive the lead’s process. Subagents launched from the main conversation follow the
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
Manual parallel sessions
:
Git worktrees
let you run multiple Claude Code sessions yourself without automated team coordination
Compare approaches
: see the
subagent vs agent team
comparison for a side-by-side breakdown
Was this page helpful?
Yes
No
⌘
I
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
A command is only recognized at the start of your message. Text that follows the command name becomes its arguments. As of v2.1.199,
skills
are the exception: a skill invocation followed by more skills, such as
/skill-a /skill-b do XYZ
, loads every skill named at the start and passes the trailing text to each as arguments. Up to six skills can be chained.
If you send a command while Claude is responding, it queues and runs after the current turn finishes. Some commands, such as
/status
,
/tasks
, and
/usage
, run immediately without interrupting the response.
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
: a bundled skill. It works like skills you write yourself: a prompt handed to Claude, which Claude can also invoke automatically when relevant.
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
/batch migrate src/ from Solid to React
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
opens the extension’s own feedback dialog instead; requires Claude Code v2.1.229 or later. Alias:
/share
. Before v2.1.212,
/bug
and
/share
were aliases of
/feedback
/cd <path>
Move this session to a new working directory, keeping the conversation and its prompt cache. Type a partial path to see matching directory suggestions; press
Tab
to accept one. Claude Code prompts you to
trust the workspace
if you haven’t worked in it before, and
--resume
finds the moved session
afterward. To grant access to an extra directory without moving the session, use
/add-dir
. Restrict or disable
/cd
targets with
Cd
permission rules
. Requires Claude Code v2.1.169 or later
/chrome
Configure
Claude in Chrome
settings
/claude-api [migrate|managed-agents-onboard|prompt-audit]
Skill
.
Load
Claude API
and Managed Agents reference material for your project’s language. Also activates automatically when your code imports
anthropic
or
@anthropic-ai/sdk
. Run
migrate
to upgrade existing Claude API code to a newer model,
managed-agents-onboard
for a walkthrough that creates a new Managed Agent, or
prompt-audit
to flag instructions written for older models in your prompts, skills, and tool descriptions and propose fixes as a diff. The
prompt-audit
subcommand requires Claude Code v2.1.221 or later
/clear [name]
Start a new conversation with empty context. Pass a name to label the previous conversation in the
/resume
picker. To free up context while continuing the same conversation, use
/compact
instead. Resume the previous conversation with
/resume
, or, in the same Claude Code process, restore it from
the rewind menu’s previous-session entry
. Aliases:
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
. Run
/config --help
to list every settable key with its options. Alias:
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
/effort [level|auto]
Set the model
effort level
. Accepts
low
,
medium
,
high
,
xhigh
,
max
, or
ultracode
; available levels depend on the model, and
max
and
ultracode
are session-only.
auto
resets to the model default. Without an argument, opens an interactive slider. Takes effect immediately without waiting for the current response to finish. Also available in non-interactive mode (
-p
) with a level argument, where it applies to the current session only; requires Claude Code v2.1.205 or later. While the
model-default effort hold
is in force, a non-interactive
/effort
reports
Not applied
, so pass
--effort
at launch instead
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
on or off. Availability in non-interactive mode with
-p
is limited; see
Toggle fast mode
. Requires Claude Code v2.1.205 or later
/feedback [report]
Send product feedback about Claude Code. Opens the same dialog as
/bug
with the same consent step and sending rules
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
: Claude keeps working across turns until the condition is met or judged impossible. With no argument, shows the current or most recently achieved goal.
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
contains your full conversation and credentials, so don’t share it. Doesn’t appear in the command menu; type it in full. See
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
List the subagents and other Claude Code sessions Claude can message, with the name to use for each;
agent team
teammates aren’t listed, since Claude reaches them through the team’s roster. See
cross-session messaging
. Also available as
/peers
. Requires Claude Code v2.1.224 or later; earlier versions report
Unknown command: /list-agents
. Available only in sessions where
cross-session messaging is enabled
/login
Sign in to your Anthropic account
/logout
Sign out from your Anthropic account
/loop [interval] [prompt]
Skill
.
Run a prompt repeatedly while the session stays open. Omit the interval and,
where available
, Claude self-paces between iterations. Omit the prompt and,
where available
, Claude runs an autonomous maintenance check or the prompt in
.claude/loop.md
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
on a row to switch for the current session only. The picker asks for confirmation when the conversation has prior output, since the next response re-reads the full history without cached context. Once confirmed, the change applies without waiting for the current response to finish. Also available in non-interactive mode (
-p
) with a model argument instead of the picker, where it applies to the current session only and isn’t saved as your default; requires Claude Code v2.1.205 or later
/passes
Share a free week of Claude Code with friends. Only visible if your account is eligible
/permissions
Manage allow, ask, and deny rules for tool permissions. Opens an interactive dialog where you can view rules by scope, add or remove rules, manage working directories, and review
recent auto mode denials
. Alias:
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
Open Claude FM lo-fi radio in your browser. Prints the stream URL when no browser is available. Not available on Amazon Bedrock, Google Cloud’s Agent Platform, Microsoft Foundry, or Claude Platform on AWS
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
and command directories so skills added or changed on disk during the session become available without restarting. Reports how many skills are available and how many were added or removed. Added in v2.1.152
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
. Requires Claude Code v2.1.145 or later
/run-skill-generator
Skill
.
Teach
/run
and
/verify
how to build, launch, and drive your project’s app from a clean environment by writing a per-project
skill
. Requires Claude Code v2.1.145 or later
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
authentication, region, and model pins through an interactive wizard. Only visible when
CLAUDE_CODE_USE_BEDROCK=1
is set. First-time Amazon Bedrock users can also access this wizard from the login screen
/setup-vertex
Configure
Google Cloud’s Agent Platform
authentication, project, region, and model pins through an interactive wizard. Only visible when
CLAUDE_CODE_USE_VERTEX=1
is set. First-time Google Cloud’s Agent Platform users can also access this wizard from the login screen
/simplify [target]
Skill
.
Review the changed code for cleanup opportunities and apply the fixes. Four review
agents
run in parallel, covering reuse of existing helpers, simplification, efficiency, and whether the change is at the right level of abstraction. From v2.1.154, the review doesn’t look for correctness bugs. Use
/code-review
to find bugs. On earlier versions,
/simplify
is equivalent to
/code-review --fix
. Pass a path or PR reference to review a specific target
/skills
List available
skills
. Type to filter the list by name. Press
t
to sort by token count. Press
Space
to
cycle a skill’s visibility to Claude and the
/
menu
, then
Enter
to save
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
Configure terminal keybindings for Shift+Enter and other shortcuts. Only visible in terminals that need it, like VS Code, Cursor, Devin Desktop, Alacritty, or Zed
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
Show session cost, plan usage limits, and activity stats. On a Pro, Max, Team, or Enterprise plan, includes a breakdown of usage by skill, subagent, plugin, and MCP server. See the
cost tracking guide
for details.
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
. Requires Claude Code v2.1.145 or later
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
CLI credentials.
/schedule
prompts for this automatically if GitHub isn’t connected
/workflows
Open the
workflow
progress view to watch, pause, resume, or save running and completed workflows
​
MCP prompts
MCP servers can expose prompts that appear as commands. These use the format
/mcp__<server>__<prompt>
and are dynamically discovered from connected servers. See
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
⌘
I
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
to pick up the changes. The skills count in the summary covers only
commands/
directories, so it can report
0 skills
even though the skill you just edited reloaded. Then try the skill with your name:
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
while the plugin is enabled
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
⌘
I
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
of the directory where you start Claude Code. They don’t
walk up to the repository root
the way plain skills and commands do, so launching from a subdirectory misses a plugin that lives at the repo root. Launch from the repository root, or run
/reload-plugins
after changing directories.
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
Unique identifier (kebab-case, no spaces). When a
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
, may contain spaces and any casing. Not used for namespacing or lookup. Requires Claude Code v2.1.143 or later.
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
. Requires Claude Code v2.1.154 or later.
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
interface. Use this for plugins that add cost or scope a user should opt into, such as one that connects to an external service. This requires Claude Code v2.1.154 or later. Earlier versions ignore the field and enable the plugin on install.
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
, then user settings. The
--setting-sources
flag narrows the list further.
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
Copied plugins cannot reference files outside their directory. Paths that traverse outside the plugin root (such as
../shared-utils
) will not work after installation because those external files are not copied to the cache.
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
. Files here are invokable as bare commands in any Bash tool call while the plugin is enabled
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
. On the next Claude Code session it loads automatically as
<name>@skills-dir
and appears in
/plugin
and
claude plugin list
with no install step.
See
Skills-directory plugins
for scope and trust requirements.
claude
plugin
init
<
nam
e
>
[options]
Arguments:
<name>
: Plugin name. Becomes the skill namespace and the directory name under
~/.claude/skills/
, so it cannot contain spaces or path separators.
Options:
Option
Description
Default
--description <text>
Manifest description
--author <name>
Author name
git config user.name
--author-email <email>
Author email
git config user.email
--with <components...>
Also scaffold component folders. Valid values:
skills
,
agents
,
hooks
,
mcp
,
lsp
,
output-style
,
channel
-f, --force
Overwrite an existing
.claude-plugin/
at the target
-h, --help
Display help for command
Aliases:
new
Each
--with
value adds a starter file for that component, ready to edit:
Component
What it scaffolds
skills
An extra namespaced
<name>:example
skill alongside the default one
agents
An
agents/
subagent definition
hooks
A
hooks/hooks.json
with a sample event handler
mcp
A
.mcp.json
with HTTP and stdio server examples
lsp
A
.lsp.json
language-server example
output-style
An
output-styles/<name>.md
that applies automatically while the plugin is enabled
channel
An MCP-based
channel
: a stdio server (
server.ts
), its
.mcp.json
, and a
package.json
The scaffolded plugin uses the
@skills-dir
source rather than a marketplace. Admins can block this source with
strictKnownMarketplaces
or by adding
{"source": "skills-dir"}
to
blockedMarketplaces
in
managed settings
. When blocked,
plugin init
fails before writing.
Examples:
# Scaffold a minimal plugin
claude
plugin
init
my-helper
# Scaffold with skill and hook folders
claude
plugin
init
my-helper
--with
skills
hooks
# Overwrite an existing scaffold
claude
plugin
init
my-helper
--force
​
plugin install
Install a plugin from available marketplaces.
claude
plugin
install
<
plugi
n
>
[options]
Arguments:
<plugin>
: Plugin name or
plugin-name@marketplace-name
for a specific marketplace
Options:
Option
Description
Default
-s, --scope <scope>
Installation scope:
user
,
project
, or
local
user
--config <key=value>
Set a
userConfig
option declared in the plugin’s manifest. Repeat the flag to set multiple options
-y, --yes
Accept the command that a plugin with a
command
source
runs, without the confirmation prompt. Claude Code still prints the command first. Required when stdin or stdout isn’t a TTY. Has no effect inside a Claude Code session, so run the command from your own terminal
-h, --help
Display help for command
Scope determines which settings file the installed plugin is added to. For example,
--scope project
writes to
enabledPlugins
in .claude/settings.json, making the plugin available to everyone who clones the project repository.
Examples:
# Install to user scope (default)
claude
plugin
install
formatter@my-marketplace
# Install to project scope (shared with team)
claude
plugin
install
formatter@my-marketplace
--scope
project
# Install to local scope (not shared with team)
claude
plugin
install
formatter@my-marketplace
--scope
local
​
plugin uninstall
Remove an installed plugin.
claude
plugin
uninstall
<
plugi
n
>
[options]
Arguments:
<plugin>
: Plugin name or
plugin-name@marketplace-name
Options:
Option
Description
Default
-s, --scope <scope>
Uninstall from scope:
user
,
project
, or
local
user
--keep-data
Preserve the plugin’s
persistent data directory
--prune
Also remove auto-ins

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
There are three additional built-in output styles:
Proactive
: Claude executes immediately, makes reasonable assumptions instead of pausing for routine decisions, and prefers action over planning. This is stronger autonomous-execution guidance than
auto mode
applies, and it works without changing your permission mode, so your permission mode still decides what runs without asking you.
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
Claude Code adds each output style’s custom instructions to the end of the system prompt.
All output styles trigger reminders for Claude to adhere to the output style instructions during the conversation.
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
Token usage depends on the style. Adding instructions to the system prompt increases input tokens, though prompt caching reduces this cost after the first request in a session. The built-in Explanatory and Learning styles produce longer responses than Default by design, which increases output tokens. For custom styles, output token usage depends on what your instructions tell Claude to produce.
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
⌘
I
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
, apart from
agent team
teammates, which Claude reaches through the team’s roster: subagents in the session, your other local Claude Code sessions, and, while this session is connected to
Remote Control
, your
Claude Code on the web
sessions and your Remote Control sessions on other machines. Backs the
/list-agents
command. See
cross-session messaging
. Requires Claude Code v2.1.224 or later, and appears only in sessions where
cross-session messaging is enabled
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
. Not available on Amazon Bedrock, Claude Platform on AWS, Google Cloud’s Agent Platform, or Microsoft Foundry, where a
/loop
prompt with no interval runs on a fixed schedule instead. The same happens when you turn off
feature-flag fetching
No
SendMessage
Sends a message to another agent: an
agent team
teammate, a
subagent it resumes
by agent ID or name, or one of your other Claude Code sessions, on this machine or beyond it. Messaging other sessions requires Claude Code v2.1.224 or later;
cross-session messaging
covers which sessions Claude can reach and each case’s requirements. A receiver never treats a message from another agent as your consent or approval. Claude can include an optional
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
.
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
Where a subagent’s permission prompts appear depends on whether it runs in the foreground or the background. Claude Code runs subagents in the background by default. For the cases where one runs in the foreground, see
Run subagents in foreground or background
.
Foreground subagents
show the same permission prompts you would see in the main conversation, at the moment each tool call happens.
Background subagents
surface permission prompts in your main session as of v2.1.186. The prompt names which subagent is asking, and pressing Esc denies that one tool call without stopping the subagent. Before v2.1.186, background subagents auto-denied any tool call that would otherwise prompt and continued without that tool.
To limit what a subagent can reach in the first place, narrow its
tools
field, leave Bash off the list, or set deny rules in your settings, as described in
Control subagent capabilities
.
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
A compound command Claude Code can’t fully parse into simple commands.
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
to cap the memory that Bash and PowerShell tool commands can use, so one runaway build can’t take the memory the rest of the session needs. Requires Claude Code v2.1.233 or later.
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
Claude Code counts all of a session’s Bash and PowerShell commands against the one cap, not each command on its own.
Claude Code applies the cap with a memory cgroup. When it can’t set the cgroup up, commands run without a cap, and the debug log from
claude --debug
says why.
After a Bash or PowerShell tool command has turned the cap on, or has turned it off because of an off value or a failed cgroup setup, Claude Code holds that result until you relaunch. To apply a changed or removed value, or a fixed setup, launch
claude
again.
When commands can’t stay under the cap, the kernel kills a command, and nothing in its result names the cap.
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
The tool is inactive until you install a
code intelligence plugin
for your language. The plugin bundles the language server configuration, and you install the server binary separately.
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
patterns you have set for Bash apply here too. The
WebSocket source
has its own approval prompt, which the classifier decides in
auto mode
.
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
: the tool is rolling out progressively.
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
to opt out of the rollout. On Linux, macOS, and WSL, the tool requires PowerShell 7 or later: install
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
Task tool availability
In Claude Code v2.1.233 and later, the following tools aren’t available on Opus 4.8, Sonnet 5, Fable 5, Mythos 5, or later versions of those families unless you opt in:
TodoWrite
,
TaskCreate
,
TaskGet
,
TaskUpdate
, and
TaskList
. Those models keep track of multi-step work without a written checklist, and the tools’ definitions and reminders take up context, so Claude Code leaves them out. Without them, Claude adds nothing to the
task list
while it works. On any other model, such as Opus 4.7, Claude Code provides the four Task tools by default and
TodoWrite
only when you set
CLAUDE_CODE_ENABLE_TASKS=0
.
If you’d like to use these tools on one of the listed models anyway, do one of the following:
Export
CLAUDE_CODE_ENABLE_TODO_TOOLS=1
before you start Claude Code, for example
CLAUDE_CODE_ENABLE_TODO_TOOLS=1 claude
. Claude Code then provides the same tools on every model and every provider
Name one of the tools in
--allowedTools
, for example
claude --allowedTools TaskCreate
List the tools in
--tools
, which restricts the session’s built-in tools to the ones it names. Include the tools you want alongside the other built-in tools you use
In the Agent SDK, the
allowedTools
and
tools
options
work the same way as the two flags
In
background sessions
and in
Claude Code on the web
, Claude Code provides the same tools on every model, listed or not.
Claude Code gives a subagent the tools only when your session has them, even when the subagent runs a different model. An in-process
agent team
teammate follows your session the same way, while a teammate in its own
split pane
runs as a separate Claude Code process, so its own model decides. Without the Task tools, an agent coordinates with its team through messages instead of the
shared task list
.
​
WebFetch tool behavior
WebFetch takes a URL and a prompt describing what to extract. It fetches the page, converts the response to Markdown when the server returns HTML, and runs the prompt against the content using a small, fast model. For most fetches, Claude receives that model’s answer, not the raw page. The conversion step is not configurable.
This makes WebFetch lossy by design. The extraction prompt determines what reaches Claude, so a result that says a page doesn’t mention something may only mean the prompt didn’t ask about it. Ask Claude to fetch again with a more specific prompt, or use
curl
via Bash for the unprocessed page.
A few behaviors shape the response Claude receives:
HTTP URLs are automatically upgraded to HTTPS.
Large pages are truncated to a fixed character limit before processing.
WebFetch caches each response for 15 minutes by default, so repeated fetches of the same URL return quickly. On Claude Code v2.1.233 or later, set
CLAUDE_CODE_WEBFETCH_CACHE_TTL_MS
to change how long WebFetch keeps each response.
When a URL redirects to a different host, WebFetch returns a text result that names the original URL and the redirect target instead of following it. Claude then fetches the new URL with a second WebFetch call.
When the extraction step hits an overloaded API, Claude Code retries it with backoff; a fetch that still fails returns an error result. Before v2.1.212, the API error text could reach Claude as if it were the extracted page content.
In the
default
and
acceptEdits
permission modes, WebFetch prompts the first time it reaches a new domain, except for a built-in set of preapproved documentation domains that fetch without a prompt. To allow another domain in advance without a prompt, add a permission rule like
WebFetch(domain:example.com)
. The
auto
and
bypassPermissions
permission modes
skip the prompt entirely.
An explicit
WebFetch(domain:...)
rule in
deny
,
ask
, or
allow
takes precedence over the preapproved set, so you can block a preapproved domain or require a prompt for it.
WebFetch sets a
User-Agent
header beginning with
Claude-User
, and an
Accept
header that prefers Markdown over HTML so servers that support content negotiation can return Markdown directly.
You configure
sandbox
network rules separately, so a domain you want a sandboxed process to reach still needs an explicit sandbox permission rule.
​
WebSearch tool behavior
WebSearch runs a query against Anthropic’s
web search
backend and returns result titles and URLs. It doesn’t fetch the result pages. To read a page Claude finds in search results, it follows up with
WebFetch
.
The tool may issue up to eight backend searches per call, refining the search internally before returning results. Claude can scope results with
allowed_domains
to include only certain hosts, or
blocked_domains
to exclude them. The two lists can’t be combined in a single call.
When the search request hits an overloaded API, Claude Code retries it with backoff; a call that still fails returns an error result. Before v2.1.212, the API error text could reach Claude as if it were search results.
WebSearch permission rules take no specifier. A bare
WebSearch
entry in
allow
or
deny
is the only form.
The search backend is not configurable. To search with a different provider, add an
MCP server
that exposes a search tool.
WebSearch is available on the Claude API and
Claude Platform on AWS
. On Microsoft Foundry it requires a
deployment hosted on Anthropic
: deployments hosted on Azure don’t support server-side tools, so the WebSearch call fails. On Google Cloud’s Agent Platform it works with Claude 4 and later models, including Opus, Sonnet, and Haiku. Amazon Bedrock doesn’t expose the server-side web search tool.
​
Session search limit
A session can make at most 200 WebSearch calls, counted across the main conversation and every
subagent
it spawns, so searches made by parallel research fan-outs count against the same limit. The limit requires Claude Code v2.1.212 or later. When Claude reaches the limit, further calls return a notice telling Claude to continue with the information it already gathered, rather than an error that would invite a retry. You don’t see the notice: a capped call appears in the conversation as a search that did nothing, and if Claude genuinely needs more searches, the notice tells it to ask you to raise the limit.
Set the
CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION
environment variable to change the cap; it accepts a positive whole number, so the cap can be raised but not turned off. Running
/clear
resets the count. If work that can still spawn
subagents
survives the clear, such as a running workflow, the count carries over instead.
​
Write tool behavior
The Write tool creates a new file or overwrites an existing one with the full content provided. It doesn’t append or merge.
Whether Claude must read an existing file in the current conversation before overwriting it depends on the model and the file:
Claude Opus 4.6, Claude Haiku 4.5, and older models always require the read, so a Write to an unread existing file fails with an error.
Newer models can overwrite a file they never read this session under the sam

## Source (changelog): https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md

# Changelog

## 2.1.233

- Added GitLab merge request URL support to the `--worktree` flag and the `claude agents` view (where MRs display as `!N`)
- Added an opt-in `forward_user_identity` apps gateway setting on Anthropic upstreams that sends the signed-in user's identity as headers, so a proxy behind the gateway can attribute spend per user
- Added opt-in memory cgroup support for Bash tool commands on Linux (`CLAUDE_CODE_TOOL_MEMORY_LIMIT`) so a runaway build can't stall the session
- Added `CLAUDE_CODE_WEBFETCH_CACHE_TTL_MS` environment variable to configure the WebFetch session URL cache TTL (default unchanged: 15 minutes)
- Fixed cloud sessions occasionally being marked as lost when the environment shut down while Claude was waiting on a permission prompt
- Fixed MCP v2 connections endlessly reopening the subscriptions/listen stream against servers that terminate long-held streams on a fixed timeout (e.g. serverless hosts)
- Fixed Notification hooks not firing for permission prompts when running under Claude Desktop or VS Code
- Fixed idle sessions on Linux sometimes keeping one CPU core at 100% when sandboxing is enabled
- Fixed bundled skill aliases like `/checkup` and `/review` reporting "Unknown command" in `-p` mode or with plugins/MCP loaded when a user or project skill shadows the bundled skill
- Fixed skill/command argument substitution to prevent argument values from being re-expanded as template markers
- Fixed Windows paths spelled with the NT `\??\` device prefix bypassing UNC path validation, closing an NTLM credential-leak vector
- Improved `claude self-hosted-runner` session start time: the session branch is now created without rewriting the working tree, and two server round trips no longer block the agent's launch
- Improved apps gateway error forwarding: 400/413 errors from Vertex, Foundry, and Claude Platform on AWS upstreams now carry the upstream's own message; fixes a bug with auto-compact on apps gateway
- Improved `claude plugin validate` to check a bare `.claude/skills` directory, reporting SKILL.md files whose frontmatter fails to parse
- Improved screen reader mode: the `/effort` selector renders as a numbered list with a typed-number prompt, and hint and dialog text is no longer clipped
- Improved print mode diagnostics: a `[claude-code:unrecognized_model]` line is written to stderr when a request goes out for a model ID Claude Code doesn't recognize; map it with `modelOverrides` to silence
- Changed the GitHub app setup tip to no longer appear in repositories whose origin remote is on gitlab.com or bitbucket.org; the enterprise marketplace tip now covers non-GitHub internal git hosts
- Todo/task-tracking tools (TaskCreate/Get/Update/List, TodoWrite) are no longer available on Opus 4.8, Sonnet 5, Fable 5, Mythos 5, and newer models; set `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` to bring them back
- Windows: fixed auto mode repeatedly stopping for manual approval on ordinary `cd
&&
> file` Bash commands (a 2.1.232 regression)
- Reverted the 2.1.232 Bash permission changes for Cygwin-style symlinks on Windows and for input redirections (`
<
file`); a narrower version will return in a later release

## 2.1.232

- Subagent forking is now on by default: a `subagent_type: "fork"` subagent inherits the full conversation and prompt cache, and non-teammate agent spawns in interactive sessions now run in the background by default
- Type `@` in the prompt to mention another Claude session by name; Claude then uses `SendMessage` to reach that session directly
- `SendMessage` now delivers to a bare name that exactly matches one live session, instead of asking to confirm with a ref first
- Interactive sessions on one machine now keep unique names: starting or renaming a session to a name another live session already uses gives it a `name-word-word` variant and tells you
- Added `/config` rows for "Dialog expiry" and "Messages from your other sessions" (cross-session inbound accept/hold/refuse)
- Added secret redaction for GitLab token families (`glrt-`, `gloas-`, `glptt-`, `glagent-`, `glimt-`, `glsoat-`, `glcbt-`, `glft-`, `glffct-`) and full redaction of routable `glpat-`/`gldt-` tokens; the `glab` CLI config store gets the same sandbox and credential-path protection as `gh`
- Added GitLab support to plugin marketplaces: bare `gitlab.com` repo URLs (including nested subgroups) now clone like `github.com` URLs, and clone auth-failure hints name your actual git host
- Settings: `additionalMarketplaces` and `allowedMarketplaces` are now accepted as friendlier aliases for `extraKnownMarketplaces` and `strictKnownMarketplaces`
- Enterprise policy: a url-typed `blockedMarketplaces` entry for a bare repo URL keeps blocking that URL when the CLI classifies it as a git clone
- Gateway: the `desktop:` overlay now accepts every released Desktop setting (was 11 hand-listed keys), validated at boot against Desktop's own schema; unknown or invalid keys fail boot
- Gateway: empty `managed.policies[].match.groups`/`admin.admin_groups` entries and malformed `email_domain` values (empty, or containing `@`, whitespace, or commas) now fail at boot instead of silently matching no one or granting admin access
- Fable 5 is offered as an advisor in `/advisor` again for organizations with Fable access, with usage-credits consent set up through `/model fable`
- Fixed a PowerShell permission bypass where variable-writing parameters could silently overwrite `$PSDefaultParameterValues` and redirect later commands' file access
- Fixed a Windows permission bypass where Git Bash followed Cygwin-style symlinks that path validation saw as regular files; writes through them now require permission approval
- Fixed nested git repositories inheriting trust from a parent directory; each repository now requires its own trust confirmation
- Fixed MCP connections hanging for the full 30-second connect timeout when a server fails to answer or sends a malformed reply to the protocol-version probe
- Fixed Remote Control sessions hosted by a bridge inside a cloud session inheriting that session's transcript or credentials
- Fixed Remote Control sessions started from Claude Desktop or an IDE appearing as a new claude.ai session each time the local session was resumed; they now reattach to the existing one
- Fixed Remote Control sessions appearing unreachable to newly attached clients while idle
- Fixed Remote Control bridge sessions not restoring conversation history when the session worker restarts
- Remote Control: resuming a conversation whose session was deleted from claude.ai or the app now starts a replacement instead of failing with a message about your login (regressed in v2.1.227)
- Fixed Cloud gateway `/login` exiting silently or leaving an unresponsive terminal after "Press Enter to continue" when managed settings failed to load; the reason is now shown
- Fixed voice mode on native builds getting stuck on "listening…" when the voice service rejected the connection; the rejection is now shown immediately
- Fixed mTLS client certificate rotation requiring a restart; Claude Code now reloads the rotated cert and key automatically on connection errors
- Fixed malformed AWS or Vertex region values being used to build request URLs; they now fall back to the default region
- Fixed stream idle timeout errors failing the request instead of recovering on Bedrock, Vertex, and gateway deployments
- Fixed content-sized overlays containing truncated text rendering one column too wide, and start-truncated text collapsing to an ellipsis
- Fixed a stray garbled character where a long shell-command or agent-description preview was cut off mid-emoji
- Fixed a startup race that could silently unregister a plugin marketplace due to concurrent writes to `known_marketplaces.json`
- Fixed `/update` and `/tui` refusing to restart while work that survives the relaunch was running
- Fixed usage-limit guidance suggesting unavailable slash commands in SDK and remote sessions
- Fixed the consent message for interactive `--advisor fable` launches, which told you to run `/model fable` in an interactive session that had just exited
- Improved fullscreen streaming: long sessions stay responsive because the whole conversation is no longer re-normalized on every update
- Improved the managed settings approval dialog: shows endpoint URLs, uses clearer wording for telemetry-only changes, skips routine OpenTelemetry options, and requires approval for server-managed sandbox binary overrides (`sandbox.bwrapPath`, `sandbox.socatPath`, `sandbox.ripgrep`)
- `/feedback` and `/bug` now open immediately when invoked while Claude is responding, instead of waiting for the turn to finish
- `/plugin install plugin@marketplace` now refreshes the marketplace first, so newly published plugins install without a manual marketplace update
- `/code-review` at high, xhigh, and max effort now runs in a background agent like the other levels
- Pasted and clipboard images are read without blocking the event loop
- Remote Control now keeps reconnecting for about 30 minutes after a network blip and no longer drops after a few blips spread across an hour
- Remote Control: resuming a conversation no longer silently takes Remote Control away from another Claude Code on the same machine that still has it; run `/remote-control` there to move it
- Updated agent panel: completed subagents hide immediately with a `/tasks` footer hint, and the "↓ N more" overflow indicator moved left for visibility
- Remote Control: the terminal now says whether a session was taken over by another device, ended from another app, or deleted, and stops suggesting a reconnect that would undo it
- Bash input redirections (`
<
file`) are now permission-checked like their argument spellings on all platforms
- Shortened the message shown when resuming a completed background agent
- Cowork sessions no longer inline external @-imports from user-scope memory files
- Hardened the auto-generated cross-session messaging socket directory on shared `/tmp`: a pre-planted symlink or another user's directory is now refused instead of used
- Hardened the Linux filesystem sandbox against a protected-path bypass
- Changed `sandbox.ripgrep` to be honored only from user, managed, and `--settings` settings; project settings can no longer override the sandbox's ripgrep binary
- Removed the startup tip suggesting you create custom subagents, and the matching nudge in the `/powerup` tour

## 2.1.231

- Fixed MCP OAuth sign-in failing with a redirect URI mismatch for servers that use a pre-registered OAuth client, such as Slack

## 2.1.229

- Documented `claude remote-control --continue` for resuming the most recent Remote Control session
- Added server-supplied Claude Code hook support for self-hosted runner sessions, matching managed-environment behavior
- Added SSE keepalive pings to gateway streaming responses during long thinking pauses, preventing idle-timeout disconnects on Vertex and Bedrock upstreams
- Added plugin marketplace `command` sources: a local command (e.g. an IDE) prints the plugin directory, which is re-resolved each session and applied without a restart; `mode: "link"` uses it in place
- `ListAgents` now marks disconnected Remote Control sessions as `offline` and labels your cloud sessions as `cloud`
- Fixed long responses partly disappearing while streaming and being printed twice in the terminal
- Fixed a crash to the error screen (including on `--resume` of the affected session) when a tool call had a non-string `glob`, `file_path`, or `command` value
- Fixed a RangeError crash when a progress bar or markdown table rendered in a very narrow terminal window (could also crash `claude --continue`/`--resume` at startup)
- Fixed a crash on Windows when a tool call or message referenced a file by an extended-length (`\\?\`) or UNC path
- Fixed auto mode failing on every tool call for users who disable the attribution header via `CLAUDE_CODE_ATTRIBUTION_HEADER` (direct Anthropic API connections)
- Fixed `/model` rejecting Sonnet/Opus 1M for claude.ai subscribers using a custom `ANTHROPIC_BASE_URL` gateway
- Fixed MCP OAuth with strict authorization servers by using `127.0.0.1` instead of `localhost` in the redirect URI
- Fixed Remote Control clients showing a stuck working spinner after a slash command typed in the laptop terminal
- Fixed the Claude Code Review workflow generated by `/install-github-app` completing without posting its review on the pull request
- Fixed multi-second UI stalls after editing a file with thousands of IDE diagnostics while the IDE extension is connected
- Fixed one-shot `claude plugin` commands leaving a stray liveness file that could prevent cleanup of outdated plugin versions
- Fixed dynamic workflows inside CPU-limited containers using the host machine's core count instead of the container's CPU limit
- Fixed a file-watcher handle leak after atomic file replacements, and an uncaught error on Windows when the scheduled-tasks watcher failed on a network or virtual filesystem
- Fixed SDK and `--input-format stream-json` sessions getting a 400 API error when a whitespace-only message was submitted
- Fixed conversations whose messages alone exceed the API's 32 MB request limit retrying compaction when no images or documents can be stripped; they now fail once with a clear message
- Fixed OpenTelemetry export from Claude Desktop sessions being rejected by the Desktop-managed gateway when that gateway is also the telemetry endpoint
- Fixed self-hosted runner and other remote sessions exiting at startup when `managed-mcp.json` is deployed and the server delivers MCP servers; those servers are now skipped with a warning
- Fixed self-hosted runner repository preparation hanging on a Git Credential Manager prompt; git now fails fast when credentials are missing
- Improved workflow fan-outs to stagger same-prefix sibling agents so subsequent agents read the cached prompt prefix instead of re-paying it (`CLAUDE_CODE_WORKFLOW_PREFIX_STAGGER_MS=0` disables)
- Improved "prompt is too long" errors to explain why automatic compaction could not recover instead of only suggesting `/compact`
- Improved sandbox: IPv6 literals in network domain lists are now bracketed (`[::1]:443`), and ambiguous spellings are enforced fail-closed and flagged by `/doctor`
- Updated `/login` to repeat the `CLAUDE_CODE_OAUTH_TOKEN` override warning after a successful login
- Changed `/commit-push-pr` so git/gh commands with dangerous flags (`--force`, `--amend`, `--no-verify`, etc.) are no longer auto-approved
- Changed self-hosted runner Windows startup to require an explicit `--base-dir`; there is no default checkout directory on Windows
- [VSCode] "Report a problem" and `/bug` now open the built-in feedback dialog instead of a retired survey link
- [VSCode] Made the `/btw` side-question panel resizable by dragging its boundary, in both side-docked and stacked layouts
- [VSCode] Added session groups in the sidebar — right-click to create, rename, or delete; Cmd/Ctrl- or Shift-click to move several sessions at once

## 2.1.228

- Fixed interactive sessions that could stop redrawing entirely, while the process kept running, after a rare internal layout error
- Fixed `git` / Git Bash not being found on Windows when Claude Code is launched from a parent folder of the git installation
- Fixed `/tui` reverting the session to an earlier model when `/model` had been changed since the last response
- Fixed cross-session messaging sometimes starting without an inbox in the first session after install or upgrade
- Fixed Remote Control `/resume` while connected leaking the resumed conversation's title or history into the connected session
- Fixed `claude self-hosted-runner` sessions failing on every fresh runner when the `checkout` hook fails for a repository the session doesn't push to; that repository is now skipped with a warning
- Fixed self-hosted runners ending sessions in the gap between a background task finishing and the follow-up turn starting
- Fixed session cleanup deleting contents inside a project's memory folder
- Fixed background plugin-cache cleanup deleting a plugin's cache when its only version is a symlinked development checkout
- Fixed a settings-merge issue where a marketplace entry redefined in a higher-precedence settings tier could inherit another tier's custom headers; marketplace entries now merge as whole entries
- Fixed the deferred-tools reminder occasionally being sent to the model twice after a skill invocation
- Hardened skills synced from claude.ai: they no longer shadow local commands or MCP prompts, their descriptions are sanitized and labeled, and on your machine their bodies don't run `!` commands or expand `@` files
- Improved cross-session messages: the sender and body now display inline instead of a collapsed line, and messages to Remote Control sessions on other machines show your Remote Control session name as the sender
- Improved Vertex AI credential handling: expired or missing Google Cloud credentials now fail within seconds instead of retrying for minutes
- Improved compaction progress: the retry countdown and stall hint now appear during compaction instead of only a progress bar
- Updated terminal title busy-spinner glyphs to reduce tab-bar jitter on some terminals
- Changed the Write tool so newer models can overwrite an existing file they haven't read this session, matching the Edit tool's rules; older models still require the read first
- Removed the outdated note about auto mode sessions costing slightly more from the first-use notice for Pro, Max, and Team plans

## 2.1.227

- Fixed feature flags being evaluated without the user's subscription tier when a session started with an expired login token, which could wrongly prompt Max plan users to enable usage credits for Fable
- Fixed every Bash command failing under `claude-code-action` with `allowed_non_write_users` on GitHub-hosted runners
- Fixed `/tui` bringing back a conversation that had been rewound to before its first message
- Improved slash-command menu: blue now marks only the selected row, matched characters are bolded instead of recolored, and emoji or accented names keep their glyphs
- Improved performance: fewer event-loop stalls on file-not-found suggestions and at-mention size checks

## 2.1.226

- Bug fixes and reliability improvements

## 2.1.225

- Added gateway spend-limit support to Claude Code's usage warning; the limit-reached message now names the cap, its reset time, and the operator's message (requires the gateway on 2.1.225)
- Added a workspace trust prompt to `claude agents` for untrusted directories, matching the behavior of `claude`
- Fixed a transient 401 replacing a long-lived `CLAUDE_CODE_OAUTH_TOKEN` with a stored login's short-lived token, breaking headless sessions until restart
- Fixed MCP OAuth servers on macOS intermittently failing with a burst of 401 errors, as if never authenticated, after a keychain read timed out
- Fixed auto mode counting a safety-filter refusal of its own permission check toward the consecutive-block limit; the action is still denied, but the model is now told to move on rather than retry
- Fixed cross-session messages staying parked without a notice or expiry in headless sessions and during startup
- Fixed conversation history breaking on Remote Control session resume after very large conversations were compacted
- Fixed hovering over a session in another project in the agents list changing the directory the next agent starts in
- Fixed `claude self-hosted-runner` registering and then failing every session when `--base-dir` cannot be created or written; it now exits at startup with a clear error
- Fixed Claude Code on the web sessions being misreported as stuck, re-sending a growing event backlog on every reconnect
- Improved Remote Control: photos attached from the Claude app are now shown to Claude directly instead of being read from disk with a separate tool call
- [VSCode] Fixed Focus view folding away the latest to-do list, a pending question's context, and settled answers; thinking-only folds show "Thought for Ns" and re-collapse when their turn completes
- SendMessage can now start a conversation with your Remote Control sessions on other machines by name (`ListAgents` shows them as `name [ref]`), instead of only replying after they message you first
- SendMessage: a Remote Control recipient you already confirmed is never swapped for a same-named session on this machine when its own list couldn't be checked

## 2.1.224

- Added self-hosted environments: `claude self-hosted-runner` turns your own machines or containers into a place Claude Code web, mobile, and desktop sessions can run, on Team and Enterprise plans
- Added `archive` plugin source: install plugins from a zip over HTTPS without git or npm, with optional SHA-256 pinning
- Added a cancel-and-confirm step when removing an unavailable paste changes a command's text
- Added `ANTHROPIC_BEDROCK_REGION_PREFIX` env var for Bedrock to prefer a specific cross-region inference profile over the `AWS_REGION`-derived one
- Added `crossSessionInbound` and `dialogExpiry` settings: cross-session messages sent to a session running with bypassed permissions are held for your approval, and messages to other sessions auto-deliver
- Added sandbox credential-masking options: `extract` and `onExtractNoMatch` for structured env values, `decode: "jwt"` with `maskClaims` for JWT-aware masking, and `awsPairs`/`sigv4` for AWS SigV4 re-signing; these need `network.tlsTerminate` and are honored only from user, managed, or `--settings` settings
- Added cross-session `SendMessage`: Claude Code sessions can now message each other, on any of your machines, with `ListAgents` to discover them (macOS and Linux)
- Fixed long (>200 char) project paths resolving to another project's session directory under a shared sanitized prefix; session list, rename, fork, delete and `/resume` no longer cross projects
- Fixed `SendMessage` reporting "Message sent" when the write to a teammate's inbox had actually failed; failed deliveries are now reported as errors
- Fixed sandbox filesystem deny entries written with a trailing slash (e.g. `denyRead: "~/.aws/"`) being silently bypassable on Linux and macOS
- Fixed sandbox violation details never appearing in Bash tool results; Claude now sees which file or network access was denied and why
- Fixed MCP tools that connect mid-turn being deferred for tool search without their names announced to the model
- Fixed plugin install records being silently corrupted when the same plugin is installed in multiple projects
- Fixed recalled or restored paste content occasionally attaching wrong data or silently losing text when the paste had aged out or placeholder numbers collided
- Fixed copy-on-select on Wayland sometimes not reaching the clipboard; the two selection writes no longer race
- Fixed the feedback survey's transcript share silently failing on long sessions; a failed share now shows an error instead of a success message
- Fixed Remote Control auto-start intermittently failing with "Remote credentials fetch failed" on a cold start with a stale login token
- Fixed Remote Control and SDK clients showing a blank "(no content)" message after `/clear` and other output-less commands
- Fixed a Remote Control session recreated after its server session expired uploading prior local conversation history into the new session
- Improved fullscreen mode to keep the full pre-compaction history in scrollback across repeated compactions, instead of only the most recent interval
- Improved Remote Control: attached web and mobile clients now see compaction progress and the post-compaction boundary instead of a silent pause; `/clear` resets now propagate to attached clients
- Improved Remote Control: connection failures now show a persistent failure indicator with details and a reconnect shortcut, instead of only an 8-second toast
- Removed the 200-subagent-per-session spawn cap; long-running sessions no longer refuse new agents (concurrency and depth limits still apply)
- Changed managed settings: the approval prompt no longer re-appears after re-login or org switching when the organization's settings are unchanged
- Changed the feedback-survey transcript share: with your consent it now also uploads the last request's model settings — the system prompt (which includes your `CLAUDE.md` instructions), tool definitions, and model parameters. Secrets are redacted as before, and these fields are dropped first if the share is too large
- Changed the Bash tool description to always note that command output is displayed to the model, not reliably to the user
- Changed recalled paste placeholder numbers to renumber when accepted into the input
- Changed Remote Control to archive the stale server session instead of leaving a dead one listed when a fresh session is minted after compaction or `/resume`
- [VSCode] Fixed the extension showing Remote Control as connected after the connection failed
- Fixed a session resume silently reconnecting Remote Control after the user turned it off (`--resume`, SDK hosts, and the VS Code extension)
- [VSCode] Fixed sessions not honoring `remoteControlAtStartup` when explicitly enabled

## 2.1.223

- Added owner wildcard entries (`"owner/*"`) to the `strictKnownMarketplaces` and `blockedMarketplaces` managed settings for allowing or blocking all marketplace repos under a GitHub org
- Added a warning when workflow agents, forked skills, slash commands, or resumed background agents' requested subagent model is restricted and the parent model runs instead
- Added a `/teleport` hint in cloud sessions showing how to continue locally with `claude --teleport
`
- Fixed a Bash permission bypass where a crafted command could hide parts of itself from permission checks
- Fixed permission prompts so commands padded with tabs or invisible Unicode can no longer hide part of the command from the approval dialog
- Fixed workflow scripts being able to use dynamic `import()` to run code outside the workflow sandbox
- Fixed a permission gap where an agent definition's `bypassPermissions` mode ignored the org bypass-permissions disable policy
- Fixed resuming a session after a mid-session `/cd` coming back empty
- Fixed gateway model discovery hiding Claude models registered under provider-prefixed IDs such as `vertex_ai/claude-*` or `bedrock/anthropic.claude-*`
- Fixed `modelOverrides` keys that aren't Anthropic model IDs being treated as the session's canonical model ID; unknown keys are now ignored as documented
- Fixed managed settings: server-delivered settings no longer disable the env block of a machine-local `managed-settings.json` or MDM profile; admin env now merges per key
- Fixed sandboxed commands failing to start on Linux when `sandbox.filesystem.denyWrite` covers the working directory
- Fixed forked background agents getting stuck "already resuming" for the rest of the session when rebuilding the fork's parent prompt failed during resume
- Fixed a resumed session failing every turn, or leaving the interactive app on an unresponsive error screen, when its history held a malformed diagnostics attachment
- Fixed a rare hang when parsing unusual `git push` output
- Changed `CLAUDE_CODE_DISABLE_1M_CONTEXT` to hold every Claude model with a native 1M window to 200K via auto-compaction, not just a fixed list; a startup warning now appears when auto-compaction isn't holding the session to 200K
- Changed auto-compact to keep sessions on unrecognized model IDs within the assumed context window instead of letting them grow past it; set `CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1` to restore the previous behavior
- Changed `/review` to be an alias of `/code-review`, which reviews the current diff or a PR (`/code-review
`); use `/code-review ultra` for a deep cloud review
- Changed `/code-review` with no effort level to reuse the level you typed last; type a level like `/code-review high` to change it

## 2.1.222

- Fixed worktree-isolated sessions and their subagents being able to run destructive git commands against the main checkout; isolation now applies to file edits and Bash in every session type
- Fixed PreToolUse auto-allow hooks bypassing tool restrictions in background agent tasks (summaries, compaction, renames)
- Fixed `/usage-credits` on Team and Enterprise showing "you've already sent a usage credit request" for members whose earlier request was dismissed, blocking them from sending a new one
- Fixed the startup connectivity check hanging and then failing behind an HTTPS proxy; it now uses the same proxy-aware transport as API requests and times out with a clear message
- Fixed "Connection closed mid-response" errors being reported on responses that had actually completed
- Fixed `/usage` overattributing usage to MCP servers: a server's share now reflects only the requests that actually consumed its tool results, instead of every turn after any call to it
- Fixed sessions not linking to pull requests created after the branch was pushed, including through the GitHub REST API
- Fixed org-restricted `model: opus`-style subagent and teammate family aliases dropping to the parent model instead of stepping down to the newest org-allowed model in the family
- Fixed stream idle timeout firing on custom `ANTHROPIC_BASE_URL` gateways despite server keep-alive pings arriving on the wire
- Fixed claude.ai connectors being falsely marked as needing authorization when the session token is invalid — they now show a `/login` hint instead
- Fixed tool errors not being displayed for tools no longer available locally, for example after an MCP server is removed
- Fixed `SendMessage` rejecting a long summary — it now truncates instead, so sends no longer fail on a character limit
- Fixed the spinner's effort label in a subagent's transcript view showing the session's effort level instead of the subagent's own `effort:` setting
- Fixed rare crashes when a file watcher hit a filesystem error or during file-watcher teardown
- Fixed screen readers re-reading the whole input line on every backspace in `--ax-screen-reader` mode — end-of-line deletions now echo just the deleted characters
- Fixed host model-selection keys not taking precedence over a stale on-disk `managed-settings.json` when `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` is set
- Improved auto mode safety: messages sent to other agent sessions via `SendMessage` are now evaluated by the permission classifier before dispatch
- Improved the refusal when Claude tries to invoke a skill with `disable-model-invocation`: Claude is now told to ask you to run the skill instead of replicating its workflow
- Improved the `/diff` view, the Remote Control workspace diff, and file-edit diffs in Claude Code on the web sessions to use raw git blob content, ignoring workspace-configured diff drivers and textconv
- Changed Remote Control auto-start so repo-local settings (`.claude/settings.json` or `.claude/settings.local.json`) can no longer turn it on (they can still turn it off); enable it at user scope via `/config`
- Removed ultraplan feature

## 2.1.221

- [VSCode] Added Focus view: a chat-menu toggle that hides tool activity behind an expandable per-turn summary with a live running-tool indicator, toggled with `Ctrl+Alt+F` or the "Claude Code: Toggle Focus view" command
- Added `mode: "mask"` for sandbox credential files on Linux and WSL — sandboxed commands read a sentinel copy (the whole file, or just the spans captured by an `extract` regex) while the sandbox proxy substitutes the real value on egress; on macOS file masking falls back to `deny`
- Added warnings to `claude plugin validate` when a marketplace or plugin name would be rejected by Claude Desktop's managed marketplace sync
- Added a `prompt-audit` subcommand to the `claude-api` skill for auditing prompts and tool descriptions for patterns written for older models
- Fixed a Bash tool permission-check bypass where zsh could execute hidden commands in `[[ ]]` regex conditionals; affected commands now prompt for permission
- Fixed PowerShell permission checks mishandling paths containing quote characters on Windows; such paths now prompt for approval
- Fixed the thinking toggle having no effect for the rest of a session that started with thinking off; disabling an MCP server mid-connect no longer silently reverts
- Fixed MCP servers from `--mcp-config` not being connected before the first turn in print mode (`-p`), which made the model emit tool calls as literal text
- Fixed @-mentioned files being silently dropped when pressing Esc to retract a prompt and resubmitting it
- Fixed a crash when preparing API requests for SDK MCP tools named after built-in object properties such as `constructor`
- Fixed WebSearch failing with a 400 error at effort `xhigh`/`max` when thinking is disabled
- Fixed sandboxed large uploads failing with TLS errors through the sandbox proxy
- Fixed Team and Enterprise spend-limit message incorrectly blaming the org's monthly limit instead of your individual spend limit
- Fixed Bedrock authentication with AWS SSO named profiles failing in desktop-managed sessions on Windows machines that set a stray `HOME` environment variable
- Fixed `CLAUDE_CODE_RESUME_INTERRUPTED_TURN=0` not disabling interrupted-turn auto-resume; falsy values are now honored
- Fixed a rare wake-from-sleep race where two Claude Code processes could both refresh the same MCP connector or WIF OAuth token at once, forcing re-authentication
- Fixed renaming a session from Claude Code Desktop or claude.ai not updating the CLI's session name; session names from every rename surface are now sanitized
- Fixed plugin- and org-delivered skills named after terminal-only built-ins (e.g. `/help`, `/feedback`) being un-invocable in non-interactive sessions
- Fixed the "Plugins changed" notification lingering after plugins were reloaded instead of clearing
- Fixed Vim mode: the yank register now survives dialogs, history search, and the transcript view instead of being silently emptied
- Fixed Vim mode: undoing back to an empty prompt now arms the "press ← again" confirm before returning to the agent view
- Improved tool search on Google Vertex AI: re-enabled for Claude 4.5-generation and newer models
- Improved auto mode: permission checks for parallel tool calls are now cache-efficient, and switching modes while a check is pending reliably prompts instead of applying the stale result
- Reduced prompt-cache costs for auto-mode permission checks by reusing the cached conversation prefix across decisions
- Improved Stats panel to count cache tokens in its token totals, with a breakdown by input, output, cache read, and cache write
- Improved `/ultrareview` error messages when a repo shares no history with its base: a checkout with no branches is now refused up front with advice to create one, and refusal hints no longer suggest `git fetch --unshallow` on clones that are already complete
- Improved Windows startup: process creation times are now read via a native kernel32 call instead of spawning PowerShell, so endpoint security tools that gate `powershell.exe` no longer prompt
- Changed background sessions to commit and push to preserve work, open a draft PR only when the task calls for one, follow your CLAUDE.md git instructions, and always end by reporting where the work lives
- Changed `/plugin install` to refresh a stale marketplace catalog and retry before reporting a plugin not found
- Changed plugins installed from `/plugin` to activate immediately when safe, instead of always requiring `/reload-plugins`
- Changed plugins to accept `"."` as a `skills` path, and the root-level `SKILL.md` validation error now suggests using the plugin root
- Changed `/status` to show the session kind: `interactive`, or a background job that is `attached` or `unattended`
- Changed emoji autocomplete to accept common alternate shortcodes like `:thumbsup:`, `:thumbsdown:`, and `:love:`
- Changed sessions forked with `/fork` to create a new worktree of their own instead of working in the original session's checkout
- Changed Claude in Chrome to close the browser tabs it opens once it no longer needs them
- Changed fast mode to report on the stream when usage credits run out mid-session, instead of failing silently
- Changed Monitor: a watch that exits without producing any output now says so instead of reporting "stream ended"
- Changed the Gateway `model` field validation: non-string values are rejected with a 400 instead of being forwarded
- Removed the repeated "Permission mode changed while the auto-mode classifier call was queued" notice from approval prompts

## 2.1.220

- Bug fixes and reliability improvements

## 2.1.219

- Added Claude Opus 5 (`claude-opus-5`), now the default Opus model — 1M context, fast mode at $10/$50 per Mtok
- Added `sandbox.network.strictAllowlist` setting to deny non-allowlisted hosts for sandboxed commands without prompting
- Added `DirectoryAdded` hook that fires after `/add-dir` or the SDK `register_repo_root` control request registers a new working directory mid-session
- Added `mcp_server_errors` to the headless stream-json init event, listing `--mcp-config` entries skipped by config validation; terminal runs print a startup warning
- Added the `workflowSizeGuideline` settings key so the advisory Dynamic workflow size guideline can be set from any settings file; the `/config` row is hidden while one does
- Added nested subagent forwarding in stream-json: subagents spawned at depth-2+ now appear when `--forward-subagent-text` is set, keyed by their spawning Agent `tool_use` id
- Fixed `claude -p` text output dropping the answer already produced when a turn dies on a mid-stream API error
- Added HTTP status and error text to `claude mcp list` and `/mcp` when a server fails to connect, and a warning for MCP config values with hidden leading or trailing whitespace
- Fixed the Fable model row showing "Requires usage credits" for plans that include it, when a stale cache had baked the label in
- Fixed the `/model` picker showing the merged Opus row as plain "Opus" instead of "Opus (1M context)"
- Fixed copy-on-select inside GNU screen printing base64 into the terminal instead of copying the selection
- Fixed Remote Control clients keeping a stale fast-mode status after a model switch, reconnect, or failed org check
- Fixed `CLAUDE_CODE_GIT_BASH_PATH` on Windows exiting or being used as bash when the path isn't a bash/sh binary; it's now ignored with a warning
- Fixed Vim mode: pressing ← on an empty prompt now returns to the agent view from NORMAL mode, not just INSERT
- Fixed screen-reader mode rewriting the entire input line on every keystroke instead of echoing only the typed character
- Improved the "Remote Control is only available via api.anthropic.com" error to name the specific setting that caused it
- Improved `claude --teleport` to show which repo your current checkout points at when it doesn't match the session's repo
- Changed dynamic workflows to default to a medium size guideline (aim for fewer than 15 agents); pick another size or unrestricted with Dynamic workflow size in `/config`
- Changed managed MCP allowlist/denylist `${VAR}` entries to resolve from the startup environment and managed-settings env instead of settings-file env
- Changed the `/model` picker to highlight only the newest model's name, so the highlight marks the new release rather than an arbitrary subset of the list
- Added the current default workflow size to the running-workflow status line, with a pointer to `/config` for changing it
- Removed Opus 4.7 from fast mode; `/fast` now applies to Opus 5 and Opus 4.8
- Updated the claude-api skill to default to Claude Opus 5, with a migration path from Opus 4.8
- Subagents can now spawn nested subagents up to depth 3 by default (was 1); set CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1 to disable nesting

## 2.1.218

- Changed `/code-review` to run as a background subagent, so review work no longer fills your conversation and keeps stacked slash commands as its review target
- Added screen-reader announcements of deleted text for word and line deletions (`Option+Delete`, `Ctrl+W`, `Cmd+Backspace`, `Ctrl+U`, `Ctrl+K`) in `--ax-screen-reader` mode
- Fixed Windows paths with `\u`-prefixed segments (like `C:\Users\unicorn`) being corrupted into CJK characters in tool inputs, which made those files inaccessible
- Fixed the left arrow key discarding the conversation with no undo: presses right after editing now ask to confirm, and Esc in the agent view returns to the conversation it backgrounded
- Fixed multi-line paste collapsing into one line with `j` in place of newlines in terminals that encode pasted newlines as Ctrl+J
- Fixed `/context` reporting stale pre-compact token usage after compacting from the message picker
- Fixed `/ultrareview` failing on descriptive arguments like "review my auth changes" — they now run a review of your current branch with the text applied as a note to the findings
- Fixed `/code-review ultra` silently running a local review in non-interactive sessions — it now launches the cloud review
- Fixed gateway spend metering to price Bedrock application-inference-profile ARNs and other config-mapped upstream model IDs at the configured model's rates
- Fixed mojibake when a long IDE selection was truncated mid-emoji, and a case where a tool executor error could be silently dropped
- Fixed an engine teardown race that could start and abandon a phantom turn, and made input pushed after close consistently rejected
- Fixed spurious "[Request interrupted by user]" messages after interrupted tool calls, and an unpaired `tool_use` block left in the transcript when a tool aborted mid-response
- Fixed VoiceOver reading "new line" instead of echoing the typed space at the end of the input in `--ax-screen-reader` mode
- Fixed plugin and settings panels not moving the terminal cursor to the focused row, so screen readers and magnifiers can follow arrow-key navigation
- Fixed crashes (maximum call stack exceeded) when a deeply nested watched directory tree was deleted or moved, and when rendering deeply nested UI trees
- Fixed pull request events occasionally being lost when a session exited immediately after creating or linking a PR
- Fixed the Bedrock setup wizard failing profile verification for assume-role profiles in partitioned AWS regions and on proxy-only networks
- Fixed rare negative or incorrect turn duration measurements after a system clock adjustment by timing turns with a monotonic clock
- Fixed the "N MCP servers need authentication" startup notice over-counting claude.ai connectors that aren't connected in claude.ai
- Fixed prompt history entries being dropped or duplicated when history writes raced or failed
- Fixed a retry loop that re-sent identical doomed requests after a context-overflow error with a large thinking budget; `Ctrl+B` backgrounding now applies the same background-shell caps as other paths
- Fixed agent frontmatter hooks running from untrusted folders: hooks now require the agent file's own folder to have accepted workspace trust
- Fixed fork-session lineage being lost after compaction in headless and SDK sessions
- Fixed a resumed session failing every turn, or crashing on resume, when its history held a malformed delta attachment
- Improved `/ultrareview` error feedback so Claude can correct an invalid argument instead of retrying it unchanged
- Improved auto mode: the dangerous-rm, background-`&`, and suspicious-Windows-path checks no longer open permission dialogs; the auto-mode classifier adjudicates them instead
- Improved sandbox command restrictions for IDE interactions
- Improved trust dialogs to name the repository root the grant covers
- Changed `/deep-research` to start only when invoked manually; Claude no longer launches it on its own
- Changed plan mode with auto to no longer prompt for Bash commands the static analyzer can't prove read-only; the auto-mode classifier judges them instead
- Added an announcement when fast mode changes as a result of switching models via `/config model=
` or Remote Control
- Changed server-managed settings so benign feature and cost toggles no longer trigger the settings-approval prompt
- Changed agent markdown files to reject agent names containing `:`, which is reserved for plugin namespacing
- Changed skills with `context: fork` to run in the background by default; opt out per skill with `background: false`
- Added `yes`/`no`/`on`/`off`/`1`/`0` (case-insensitive) as accepted values for skill and plugin frontmatter booleans, alongside `true`/`false`
- Fixed remote sessions continuing to send heartbeats after their worker was replaced, which left long-lived desktop and IDE processes retrying a rejected request every few seconds forever

## 2.1.217

- Added emoji shortcode autocomplete in the prompt input: type `:heart:` to insert ❤️, or `:hea` for suggestions — disable with the `emojiCompletionEnabled` setting
- Added warnings when transcript writes are failing (e.g. disk full) or when session saving is off due to an inherited environment variable, instead of losing transcripts silently
- Fixed a memory leak where truncated MCP tool outputs kept the full untruncated result in memory for the rest of the session
- Fixed Windows auto-update failures that could leave `claude.exe` missing; failed updates now restore the preserved executable automatically
- Fixed background session isolation not canonicalizing symlinked working directories, which could let sessions escape their workspace folder
- Fixed auto-compact never triggering for Claude Opus 4.8 on Bedrock and `/compact` failing once over the limit
- Fixed corporate mTLS, TLS-verify, OAuth scope, and proxy settings being ignored in Claude Desktop sessions
- Fixed screen reader mode's startup announcement being cut off by the first prompt render, and the thinking status row re-rendering every few seconds to update elapsed time and token counts
- Fixed managed settings that set `OTEL_EXPORTER_OTLP_ENDPOINT` not governing all signals — lower-scope signal-specific overrides no longer redirect telemetry away from the managed endpoint
- Fixed `--resume`/`--continue` and `/resume` failing with a TypeError when a transcript has a malformed attachment entry
- Fixed Remote Control sessions not showing a pending permission prompt or dialog to viewers that connected after it appeared
- Fixed background shells sometimes becoming impossible to stop after a session is sent to the background (`/background` or `←`) or when the session exits on a heavily loaded machine, most visible on Windows
- Fixed a `CLAUDE.md` or `SKILL.md` paths frontmatter value with many brace groups OOM-killing or stalling the CLI at startup — brace expansion is now budget-bounded
- Fixed the transcript preview sitting flush against the input area when attaching to a starting background session; it now leaves the same one-line gap as the live layout, so the transcript no longer shifts when the session takes over
- Improved footer PR badge links to be clickable hyperlinks even when terminal support can't be detected (e.g. over ssh/tmux); set `FORCE_HYPERLINK=0` to opt out
- Changed the login-expiry warning to appear 3 days before expiry instead of 5
- Capped the frontend-design plugin suggestion tip at 3 lifetime impressions instead of repeating indefinitely
- Added a cap on concurrently-running subagents (default 20, override with `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`) so one message can't fan out unbounded background agents
- Changed subagents to no longer spawn nested subagents by default; set `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` to allow deeper nesting
- Fixed `--max-budget-usd` not stopping background subagents: once the cap is reached, new spawns are denied and running background agents are halted

## 2.1.216

- Added `sandbox.filesystem.disabled` setting to skip filesystem isolation while keeping network egress control
- Fixed a slowdown in long sessions where message normalization cost grew quadratically with the number of turns, causing multi-second stalls and slow resumes
- Fixed auto mode denying commands with "HTTP 401" classifier errors after the OAuth token expired or rotated mid-session
- Fixed AskUserQuestion telling Claude to continue even when your answer asked it to wait or explain first — free-text answers now get neutral wording
- Fixed Claude Code on the web re-asking the same question and dropping your answer after the session sat idle for a few minutes
- Fixed @-mentions silently attaching nothing after file-modifying hooks, vim dot-repeat of `c`-operators and paste, statusline running twice on resume, and resume-picker hangs on failure
- Fixed resumed background agent sessions reverting to the default agent: the agent's prompt and tool restrictions are now restored
- Fixed worktree-isolated subagents redirecting git into the shared checkout via `git -C`, `--git-dir`, or `GIT_DIR`/`GIT_WORK_TREE`
- Fixed worktree sessions landing in another project's leftover worktree when the working directory did not match the selected project
- Fixed background sessions whose worktree has no git repository being undeletable
- Fixed `claude daemon stop --any` potentially terminating an unrelated process via a stale legacy daemon lockfile
- Fixed Esc-Esc at an idle prompt not opening the rewind picker in long-running sessions with background tasks
- Fixed Bash command permission checking for compound statements with redirects inside `&&` lists or negations
- Fixed pressing Ctrl+X twice in the agent list failing to delete a session, and deleted sessions reappearing when their background worker had died
- Fixed background subagents getting cancelled when a high-priority message arrives during their startup window
- Fixed mouse and focus garbage in the terminal while a GUI editor from `/memory`, `/plan`, `/keybindings`, or
