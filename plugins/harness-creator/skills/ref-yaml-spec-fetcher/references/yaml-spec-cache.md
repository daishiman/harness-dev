# YAML Spec Cache

last_fetched: 2026-07-06T03:50:22Z
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
.
​
Bundled skills
Claude Code includes a set of bundled skills that are available in every session unless disabled with the
disableBundledSkills
setting, including
/code-review
,
/batch
,
/debug
,
/loop
, and
/claude-api
. Unlike most built-in commands, which execute fixed logic directly, bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools. You invoke them the same way as any other skill, by typing
/
followed by the skill name.
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
All three skills require Claude Code v2.1.145 or later.
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
When skills share the same name across levels, enterprise overrides personal, and personal overrides project. A skill at any of these levels also overrides a bundled skill with the same name. For example, a
code-review
skill in your project’s
.claude/skills/
replaces the bundled
/code-review
. Plugin skills use a
plugin-name:skill-name
namespace, so they cannot conflict with other levels. If you have files in
.claude/commands/
, those work the same way, but if a skill and a command share the same name, the skill takes precedence.
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
Claude Code watches skill directories for file changes. Adding, editing, or removing a skill under
~/.claude/skills/
, the project
.claude/skills/
, or a
.claude/skills/
inside an
--add-dir
directory takes effect within the current session without restarting. Creating a top-level skills directory that did not exist when the session started requires restarting Claude Code so the new directory can be watched.
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
Automatic discovery from parent and nested directories
Project skills load from
.claude/skills/
in your starting directory and in every parent directory up to the repository root, so starting Claude in a subdirectory still picks up skills defined at the root. When you work with files in subdirectories below your starting directory, Claude Code also discovers skills from nested
.claude/skills/
directories on demand. For example, if you’re editing a file in
packages/frontend/
, Claude Code also looks for skills in
packages/frontend/.claude/skills/
. This supports monorepo setups where packages have their own skills.
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
still work and support the same
frontmatter
. Skills are recommended since they support additional features like supporting files.
​
Skills from additional directories
The
--add-dir
flag and
/add-dir
command
grant file access
rather than configuration discovery, but skills are an exception:
.claude/skills/
within an added directory is loaded automatically. This exception applies only to
--add-dir
and
/add-dir
. The
permissions.additionalDirectories
setting in
settings.json
grants file access only and does not load skills. See
Live change detection
for how edits are picked up during a session.
Other
.claude/
configuration such as commands and output styles is not loaded from additional directories. See the
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
to prevent Claude from triggering it automatically.
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
Your
SKILL.md
can contain anything, but thinking through how you want the skill invoked (by you, by Claude, or both) and where you want it to run (inline or in a subagent) helps guide what to include. For complex skills, you can also
add supporting files
to keep the main skill focused.
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
Field
Required
Description
name
No
Display name shown in skill listings. Defaults to the directory name. See
How a skill gets its command name
for how this differs from the name you type to invoke the skill.
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
.
As of v2.1.196, also prevents the skill from running when a
scheduled task
fires with the skill as its prompt. Default:
false
.
user-invocable
No
Set to
false
to hide from the
/
menu. Use for background knowledge users shouldn’t invoke directly. Default:
true
.
allowed-tools
No
Tools Claude can use without asking permission when this skill is active. Accepts a space- or comma-separated string, or a YAML list.
disallowed-tools
No
Tools removed from Claude’s available pool while this skill is active. Use for autonomous skills that should never call certain tools, such as
AskUserQuestion
for a background loop. Accepts a space- or comma-separated string, or a YAML list. The restriction clears when you send your next message.
model
No
Model to use when this skill is active. The override applies for the rest of the current turn and is not saved to settings; the session model resumes on your next prompt. Accepts the same values as
/model
, or
inherit
to keep the active model. A value excluded by your organization’s
availableModels
allowlist is not used and the session keeps its current model.
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
to run in a forked subagent context.
agent
No
Which subagent type to use when
context: fork
is set.
hooks
No
Hooks scoped to this skill’s lifecycle. See
Hooks in skills and agents
for configuration format.
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
runs inline shell commands via PowerShell on Windows. Requires
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
.
​
How a skill gets its command name
The command you type to invoke a skill comes from where the skill file lives. The frontmatter
name
field sets the display label shown in skill listings and, except for a plugin-root
SKILL.md
, does not change what you type after
/
.
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
Directory name, namespaced by plugin
my-plugin/skills/review/SKILL.md
→
/my-plugin:review
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
The plugin-root case is the one place where
name
does set the command name, because there is no skill directory to take it from. If
name
is not set in the frontmatter, the plugin’s directory name is used instead.
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
The
${CLAUDE_PROJECT_DIR}
substitution requires Claude Code v2.1.196 or later. It applies to both the skill body and the
allowed-tools
frontmatter, so a permission rule like
Bash(${CLAUDE_PROJECT_DIR}/scripts/lint.sh *)
resolves to the same path the skill body uses.
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
still expands to the argument value.
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
This example creates a deploy skill that only you can trigger. The
disable-model-invocation: true
field prevents Claude from running it automatically:
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
content enters the conversation as a single message and stays there for the rest of the session. Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps.
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
field grants permission for the listed tools while the skill is active, so Claude can use them without prompting you for approval. It does not restrict which tools are available: every tool remains callable, and your
permission settings
still govern tools that are not listed.
For skills checked into a project’s
.claude/skills/
directory,
allowed-tools
takes effect after you accept the workspace trust dialog for that folder, the same as permission rules in
.claude/settings.json
. Review project skills before trusting a repository, since a skill can grant itself broad tool access.
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
in the skill’s frontmatter. The restriction clears when you send your next message. To block tools across all skills and prompts, add deny rules in your
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
You can also stack several skills at the start of one message.
As of v2.1.199, typing
/code-review /fix-issue 123
loads both skills and passes the trailing text
123
as
$ARGUMENTS
to each of them. In earlier versions, only the first skill loaded and received
/fix-issue 123
as literal argument text.
Claude Code expands the first skill plus up to five more stacked after it. Expansion stops at the first token that isn’t an inline user-invocable skill, so a skill that runs as a
forked subagent
or one whose arguments may themselves start with a slash command, such as
/loop
, also ends the run there; that token and everything after it become the argument text for every expanded skill.
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
syntax runs shell commands before the skill content is sent to Claude. The command output replaces the placeholder, so Claude receives actual data, not the command itself.
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
When this skill runs:
Each
!`<command>`
executes immediately (before Claude sees anything)
The output replaces the placeholder in the skill content
Claude receives the fully-rendered prompt with actual PR data
This is preprocessing, not something Claude executes. Claude only sees the final result.
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
To request deeper reasoning when a skill runs, include
ultrathink
anywhere in the skill content. See
Use ultrathink for one-off deep reasoning
.
​
Run skills in a subagent
Add
context: fork
to your frontmatter when you want a skill to run in isolation. The skill content becomes the prompt that drives the subagent. It won’t have access to your conversation history.
context: fork
only makes sense for skills with explicit instructions. If your skill contains guidelines like “use these API conventions” without a task, the subagent receives the guidelines but no actionable prompt, and returns without meaningful output.
Skills and
subagents
work together in two directions:
Approach
System prompt
Task
Also loads
Skill with
context: fork
From agent type
SKILL.md content
CLAUDE.md, except when the agent is Explore or Plan
Subagent with
skills
field
Subagent’s markdown body
Claude’s delegation message
Preloaded skills + CLAUDE.md
With
context: fork
, you write the task in your skill and pick an agent type to execute it. The built-in Explore and Plan agents
skip CLAUDE.md and git status
to keep their context small, so a forked skill using
agent: Explore
sees only the SKILL.md content and the agent’s own system prompt. For the inverse, where you define a custom subagent that uses skills as reference material, see
Subagents
.
​
Example: Research skill using Explore agent
This skill runs research in a forked Explore agent. The skill content becomes the task, and the agent provides read-only tools optimized for codebase exploration:
---
name
:
deep-research
description
:
Research a topic thoroughly
context
:
fork
agent
:
Explore
---
Research $ARGUMENTS thoroughly
:
1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Summarize findings with specific file references
When this skill runs:
A new isolated context is created
The subagent receives the skill content as its prompt (“Research $ARGUMENTS thoroughly…”)
The
agent
field determines the execution environment (model, tools, and permissions)
Results are summarized and returned to your main conversation
The
agent
field specifies which subagent configuration to use. Options include built-in agents (
Explore
,
Plan
,
general-purpose
) or any custom subagent from
.claude/agents/
. If omitted, uses
general-purpose
.
​
Restrict Claude’s skill access
By default, Claude can invoke any skill that doesn’t have
disable-model-invocation: true
set. Skills that define
allowed-tools
grant Claude access to those tools without per-use approval when the skill is active. Your
permission settings
still govern baseline approval behavior for all other tools. A few built-in commands are also available through the Skill tool, including
/init
,
/review
, and
/security-review
. Other built-in commands such as
/compact
are not.
Three ways to control which skills Claude can invoke:
Disable all skills
by denying the Skill tool in
/permissions
:
# Add to deny rules:
Skill
Allow or deny specific skills
using
permission rules
:
# Allow only specific skills
Skill(commit)
Skill(review-pr *)
# Deny specific skills
Skill(deploy *)
Permission syntax:
Skill(name)
for exact match,
Skill(name *)
for prefix match with any arguments.
Hide individual skills
by adding
disable-model-invocation: true
to their frontmatter. This removes the skill from Claude’s context entirely.
The
user-invocable
field only controls menu visibility, not Skill tool access. Use
disable-model-invocation: true
to block programmatic invocation.
​
Override skill visibility from settings
The
skillOverrides
setting controls skill visibility from your
settings
instead of the skill’s own frontmatter. Use it for skills whose SKILL.md you don’t want to edit, such as ones checked into a shared project repo or provided by an MCP server. The
/skills
menu writes it for you: highlight a skill and press
Space
to cycle states, then
Enter
to save to
.claude/settings.local.json
.
Each key is a skill name and each value is one of four states:
Value
Listed to Claude
In
/
menu
"on"
Name and description
Yes
"name-only"
Name only
Yes
"user-invocable-only"
Hidden
Yes
"off"
Hidden
Hidden
As of v2.1.199,
"off"
also hides the skill from the command lists advertised to
Remote Control
clients and to
Agent SDK
callers, not only the terminal
/
menu. Invoking a hidden skill by its full name still returns the
skillOverrides
error instead of running it.
A skill that is absent from
skillOverrides
is treated as
"on"
. The example below collapses one skill to its name and turns another off entirely:
{
"skillOverrides"
: {
"legacy-context"
:
"name-only"
,
"deploy"
:
"off"
}
}
Plugin skills are not affected by
skillOverrides
. Manage those through
/plugin
instead.
​
Evaluate and iterate on a skill
Seeing a skill trigger tells you Claude found it, not that it did what you intended. To know a skill is working, measure two things separately: whether Claude invokes it on the prompts it should, and whether the output matches what you expect when it does.
The check for both is a baseline comparison. Collect a few realistic prompts, run each one in a fresh session with the skill available and again with it
disabled
, and compare the results. A fresh session matters because leftover context from authoring the skill will mask gaps in the written instructions.
​
Run evals with skill-creator
The
skill-creator
plugin
automates the comparison loop inside Claude Code. Install it from the official marketplace:
/plugin install skill-creator@claude-plugins-official
If Claude Code reports that the plugin is not found in any marketplace, your marketplace is either missing or outdated. Run
/plugin marketplace update claude-plugins-official
to refresh it, or
/plugin marketplace add anthropics/claude-plugins-official
if you haven’t added it before. Then retry the install.
After installing, run
/reload-plugins
to make the plugin’s skills available in the current session. Then ask Claude to evaluate an existing skill, for example
evaluate my summarize-changes skill with skill-creator
. The plugin walks you through writing test cases and runs the loop:
Test cases
: stores prompts, input files, and expected behavior in
evals/evals.json
inside the skill directory
Isolated runs
: spawns a
subagent
per test case so each run starts with a clean context, and records token count and duration
Grading
: checks each assertion against the output and writes pass or fail with evidence to
grading.json
Benchmark
: aggregates pass rate, time, and tokens for with-skill versus without-skill into
benchmark.json
so you can compare the pass-rate improvement against the token and time overhead
Version comparison
: runs a blind A/B between two versions of the skill so you can confirm an edit is an improvement before committing it
Description tuning
: generates should-trigger and should-not-trigger prompts, measures the hit rate, and proposes description edits when the skill activates on the wrong requests
Review viewer
: opens an HTML report where you inspect each output and record qualitative feedback that the next iteration reads
For the eval file format and the full iteration workflow, see
Evaluating skill output quality
on agentskills.io. For background on the benchmark and comparison modes, see the
skill-creator announcement
.
​
Share skills
Skills can be distributed at different scopes depending on your audience:
Project skills
: Commit
.claude/skills/
to version control
Plugins
: Create a
skills/
directory in your
plugin
Managed
: Deploy organization-wide through
managed settings
​
Generate visual output
Skills can bundle and run scripts in any language, giving Claude capabilities beyond what’s possible in a single prompt. One powerful pattern is generating visual output: interactive HTML files that open in your browser for exploring data, debugging, or creating reports.
This example creates a codebase explorer: an interactive tree view where you can expand and collapse directories, see file sizes at a glance, and identify file types by color.
Create the Skill directory:
mkdir
-p
~/.claude/skills/codebase-visualizer/scripts
Save this to
~/.claude/skills/codebase-visualizer/SKILL.md
. The description tells Claude when to activate this Skill, and the instructions tell Claude to run the bundled script. The script path uses
${CLAUDE_SKILL_DIR}
so it resolves correctly whether the skill is installed at the personal, project, or plugin level:
---
name
:
codebase-visualizer
description
:
Generate an interactive collapsible tree visualization of your codebase. Use when exploring a new repo, understanding project structure, or identifying large files.
allowed-tools
:
Bash(python3 *)
---
# Codebase Visualizer
Generate an interactive HTML tree view that shows your project's file structure with collapsible directories.
## Usage
Run the visualization script from your project root
:
```
bash
python3 ${CLAUDE_SKILL_DIR}/scripts/visualize.py .
```
This creates `codebase-map.html` in the current directory and opens it in your default browser.
## What the visualization shows
-
*
*Collapsible
directories**
:
Click folders to expand/collapse
-
*
*File
sizes**
:
Displayed next to each file
-
*
*Colors**:
Different colors for different file types
-
*
*Directory
totals**
:
Shows aggregate size of each folder
Save this to
~/.claude/skills/codebase-visualizer/scripts/visualize.py
. This script scans a directory tree and generates a self-contained HTML file with:
A
summary sidebar
showing file count, directory count, total size, and number of file types
A
bar chart
breaking down the codebase by file type (top 8 by size)
A
collapsible tree
where you can expand and collapse directories, with color-coded file type indicators
The script requires Python 3 but uses only built-in libraries, so there are no packages to install:
#!/usr/bin/env python3
"""Generate an interactive collapsible tree visualization of a codebase."""
import
json
import
sys
import
webbrowser
from
html
import
escape
from
pathlib
import
Path
from
collections
import
Counter
IGNORE
=
{
'.git'
,
'node_modules'
,
'__pycache__'
,
'.venv'
,
'venv'
,
'dist'
,
'build'
}
def
scan
(
path
: Path,
stats
:
dict
) ->
dict
:
result
=
{
"name"
: path.name,
"children"
: [],
"size"
:
0
}
try
:
for
item
in
sorted
(path.iterdir()):
if
item.name
in
IGNORE
or
item.name.startswith(
'.'
):
continue
if
item.is_file():
size
=
item.stat().st_size
ext
=
item.suffix.lower()
or
'(no ext)'
result[
"children"
].append({
"name"
: item.name,
"size"
: size,
"ext"
: ext})
result[
"size"
]
+=
size
stats[
"files"
]
+=
1
stats[
"extensions"
][ext]
+=
1
stats[
"ext_sizes"
][ext]
+=
size
elif
item.is_dir():
stats[
"dirs"
]
+=
1
child
=
scan(item, stats)
if
child[
"children"
]:
result[
"children"
].append(child)
result[
"size"
]
+=
child[
"size"
]
except
PermissionError
:
pass
return
result
def
generate_html
(
data
:
dict
,
stats
:
dict
,
output
: Path) ->
None
:
ext_sizes
=
stats[
"ext_sizes"
]
total_size
=
sum
(ext_sizes.values())
or
1
sorted_exts
=
sorted
(ext_sizes.items(),
key
=
lambda
x
:
-
x[
1
])[:
8
]
colors
=
{
'.js'
:
'#f7df1e'
,
'.ts'
:
'#3178c6'
,
'.py'
:
'#3776ab'
,
'.go'
:
'#00add8'
,
'.rs'
:
'#dea584'
,
'.rb'
:
'#cc342d'
,
'.css'
:
'#264de4'
,
'.html'
:
'#e34c26'
,
'.json'
:
'#6b7280'
,
'.md'
:
'#083fa1'
,
'.yaml'
:
'#cb171e'
,
'.yml'
:
'#cb171e'
,
'.mdx'
:
'#083fa1'
,
'.tsx'
:
'#3178c6'
,
'.jsx'
:
'#61dafb'
,
'.sh'
:
'#4eaa25'
,
}
lang_bars
=
""
.join(
f
'<div class="bar-row"><span class="bar-label">
{
ext
}
</span>'
f
'<div class="bar" style="width:
{
(size
/
total_size)
*
100
}
%;background:
{
colors.get(ext,
"#6b7280"
)
}
"></div>'
f
'<span class="bar-pct">
{
(size
/
total_size)
*
100
:.1f}
%</span></div>'
for
ext, size
in
sorted_exts
)
def
fmt
(
b
):
if
b
<
1024
:
return
f
"
{
b
}
B"
if
b
<
1048576
:
return
f
"
{
b
/
1024
:.1f}
KB"
return
f
"
{
b
/
1048576
:.1f}
MB"
html
=
f
'''<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>Codebase Explorer</title>
<style>
body
{{
font: 14px/1.5 system-ui, sans-serif; margin: 0; background: #1a1a2e; color: #eee;
}}
.container
{{
display: flex; height: 100vh;
}}
.sidebar
{{
width: 280px; background: #252542; padding: 20px; border-right: 1px solid #3d3d5c; overflow-y: auto; flex-shrink: 0;
}}
.main
{{
flex: 1; padding: 20px; overflow-y: auto;
}}
h1
{{
margin: 0 0 10px 0; font-size: 18px;
}}
h2
{{
margin: 20px 0 10px 0; font-size: 14px; color: #888; text-transform: uppercase;
}}
.stat
{{
display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #3d3d5c;
}}
.stat-value
{{
font-weight: bold;
}}
.bar-row
{{
display: flex; align-items: center; margin: 6px 0;
}}
.bar-label
{{
width: 55px; font-size: 12px; color: #aaa;
}}
.bar
{{
height: 18px; border-radius: 3px;
}}
.bar-pct
{{
margin-left: 8px; font-size: 12px; color: #666;
}}
.tree
{{
list-style: none; padding-left: 20px;
}}
details
{{
cursor: pointer;
}}
summary
{{
padding: 4px 8px; border-radius: 4px;
}}
summary:hover
{{
background: #2d2d44;
}}
.folder
{{
color: #ffd700;
}}
.file
{{
display: flex; align-items: center; padding: 4px 8px; border-radius: 4px;
}}
.file:hover
{{
background: #2d2d44;
}}
.size
{{
color: #888; margin-left: auto; font-size: 12px;
}}
.dot
{{
width: 8px; height: 8px; border-radius: 50%; margin-right: 8px;
}}
</style>
</head><body>
<div class="container">
<div class="sidebar">
<h1>📊 Summary</h1>
<div class="stat"><span>Files</span><span class="stat-value">
{
stats[
"files"
]
:,}
</span></div>
<div class="stat"><span>Directories</span><span class="stat-value">
{
stats[
"dirs"
]
:,}
</span></div>
<div class="stat"><span>Total size</span><span class="stat-value">
{
fmt(data[
"size"
])
}
</span></div>
<div class="stat"><span>File types</span><span class="stat-value">
{
len
(stats[
"extensions"
])
}
</span></div>
<h2>By file type</h2>
{
lang_bars
}
</div>
<div class="main">
<h1>📁
{
escape(data[
"name"
])
}
</h1>
<ul class="tree" id="root"></ul>
</div>
</div>
<script>
const data =
{
json.dumps(data)
}
;
const colors =
{
json.dumps(colors)
}
;
function fmt(b)
{{
if (b < 1024) return b + ' B'; if (b < 1048576) return (b/1024).toFixed(1) + ' KB'; return (b/1048576).toFixed(1) + ' MB';
}}
function esc(s)
{{
return s.replace(/[&<>"']/g, c => (
{{
"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}}
[c]));
}}
function render(node, parent)
{{
if (node.children)
{{
const det = document.createElement('details');
det.open = parent === document.getElementById('root');
det.innerHTML = `<summary><span class="folder">📁 $
{{
esc(node.name)
}}
</span><span class="size">$
{{
fmt(node.size)
}}
</span></summary>`;
const ul = document.createElement('ul'); ul.className = 'tree';
node.children.sort((a,b) => (b.children?1:0)-(a.children?1:0) || a.name.localeCompare(b.name));
node.children.forEach(c => render(c, ul));
det.appendChild(ul);
const li = document.createElement('li'); li.appendChild(det); parent.appendChild(li);
}}
else
{{
const li = document.createElement('li'); li.className = 'file';
li.innerHTML = `<span class="dot" style="background:$
{{
colors[node.ext]||'#6b7280'
}}
"></span>$
{{
esc(node.name)
}}
<span class="size">$
{{
fmt(node.size)
}}
</span>`;
parent.appendChild(li);
}}
}}
data.children.forEach(c => render(c, document.getElementById('root')));
</script>
</body></html>'''
output.write_text(html)
if
__name__
==
'__main__'
:
target
=
Path(sys.argv[
1
]
if
len
(sys.argv)
>
1
else
'.'
).resolve()
stats
=
{
"files"
:
0
,
"dirs"
:
0
,
"extensions"
: Counter(),
"ext_sizes"
: Counter()}
data
=
scan(target, stats)
out
=
Path(
'codebase-map.html'
)
generate_html(data, stats, out)
print
(
f
'Generated
{
out.absolute()
}
'
)
webbrowser.open(
f
'file://
{
out.absolute()
}
'
)
See all 133 lines
To test, open Claude Code in any project and ask “Visualize this codebase.” Claude runs the script, generates
codebase-map.html
, and opens it in your browser.
This pattern works for any visual output: dependency graphs, test coverage reports, API documentation, or database schema visualizations. The bundled script does the work while Claude handles orchestration.
​
Troubleshooting
​
Skill not triggering
If Claude doesn’t use your skill when expected:
Check the description includes keywords users would naturally say
Verify the skill appears in
What skills are available?
Try rephrasing your request to match the description more closely
Invoke it directly with
/skill-name
if the skill is user-invocable
If the frontmatter YAML is malformed, Claude Code loads the skill body with empty metadata, so
/skill-name
still works but Claude has no
description
to match against. Run with
--debug
to see the parse error.
​
Skill triggers too often
If Claude uses your skill when you don’t want it:
Make the description more specific
Add
disable-model-invocation: true
if you only want manual invocation
​
Skill descriptions are cut short
Skill descriptions are loaded into context so Claude knows what’s available. All skill names are always included, but if you have many skills, descriptions are shortened to fit the character budget, which can strip the keywords Claude needs to match your request. The budget scales at 1% of the model’s context window. When it overflows, descriptions for the skills you invoke least are dropped first, so the skills you actually use keep their full text. Run
/doctor
to see how many skill descriptions are being shortened or dropped and which skills are affected.
As of v2.1.196, the Skills row in
/context
reports the size of the listing after the budget is applied, so it matches what the model receives. Earlier versions counted the full text of every description, so the row could show a value several times larger than the budget
/doctor
reports.
To raise the budget, set the
skillListingBudgetFraction
setting (e.g.
0.02
= 2%) or the
SLASH_COMMAND_TOOL_CHAR_BUDGET
environment variable to a fixed character count. To free budget for other skills, set low-priority entries to
"name-only"
in
skillOverrides
so they list without a description. You can also trim the
description
and
when_to_use
text at the source: put the key use case first, since each entry’s combined text is capped at 1,536 characters regardless of budget. The cap is configurable with
skillListingMaxDescChars
.
​
Related resources
Debug your configuration
: diagnose why a skill isn’t appearing or triggering
Evaluating skill output quality
: the eval file format and iteration workflow on agentskills.io
Skill authoring best practices
: writing guidance that applies across Claude products
Subagents
: delegate tasks to specialized agents
Plugins
: package and distribute skills with other extensions
Hooks
: automate workflows around tool events
Memory
: manage CLAUDE.md files for persistent context
Commands
: reference for built-in commands and bundled skills
Permissions
: control tool and skill access
Claude Tag skills
: project skills committed to a repo also load when that repo is used in a Claude Tag channel
Was this page helpful?
Yes
No
Reference
Discover and install prebuilt plugins
⌘
I
Assistant
Responses are generated using AI and may contain mistakes.

## Source (settings): https://docs.claude.com/en/docs/claude-code/settings

Claude Code settings - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Claude Code offers a variety of settings to configure its behavior to meet your needs. You can configure Claude Code by running the
/config
command, which opens a tabbed Settings interface where you can view status information and modify configuration options.
From v2.1.181, you can change a single option without opening the interface by passing
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
You, in this repository only
No (gitignored when Claude Code creates it)
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
(highest): can’t be overridden by anything
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
, the project value applies. Permission rules behave differently because they merge across scopes rather than override. See
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
for settings that are not checked in, useful for personal preferences and experimentation. When Claude Code creates
.claude/settings.local.json
, it configures git to ignore the file. If you create the file yourself, add it to your gitignore manually.
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
Following the systemd convention,
managed-settings.json
is merged first as the base, then all
*.json
files in the drop-in directory are sorted alphabetically and merged on top. Later files override earlier ones for scalar values, arrays are concatenated and de-duplicated, and objects are deep-merged. Hidden files starting with
.
are ignored.
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
Managed settings parse tolerantly. When a managed configuration contains an entry that fails schema validation, Claude Code strips that entry, records a warning, and enforces every remaining valid policy. A single typo cannot disable the rest of your organization’s policy.
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
allowManagedMcpServersOnly
Treated as
true
.
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
An individual invalid entry in
files
or
envVars
is stripped with a warning and the valid subset is enforced. A wholly invalid
credentials
value is dropped with a warning while the rest of
sandbox
still applies. Applies in v2.1.191 and later.
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
. Accepts a model alias such as
"opus"
,
"sonnet"
, or
"fable"
(
v2.1.170+), or a full model ID. Written automatically when you run
/advisor
. Unset to disable the advisor. Requires Claude Code v2.1.98 or later
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
. Requires Claude Code v2.1.119 or later
true
allowAllClaudeAiMcps
(Managed settings only) Load claude.ai connectors alongside a deployed
managed-mcp.json
, which otherwise takes exclusive control and suppresses them. See
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
(Managed settings only) Only managed hooks, SDK hooks, and hooks from plugins force-enabled in managed settings
enabledPlugins
are loaded. User, project, and all other plugin hooks are blocked. See
Hook configuration
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
autoMemoryDirectory
Custom directory for
auto memory
storage. Accepts an absolute path or a
~/
-prefixed path. From project or local settings, this is honored only after you accept the workspace trust dialog, since a cloned repository can supply this file
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
. Not read from shared project settings
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
Render screen-reader friendly output: flat text without decorative borders or animations. Screen-reader mode always uses the classic renderer, so the
tui
setting has no effect while it is active. The
CLAUDE_AX_SCREEN_READER
environment variable and the
--ax-screen-reader
flag take precedence. Requires Claude Code v2.1.181 or later
true
blockedMarketplaces
(Managed settings only) Blocklist of marketplace sources. Enforced on marketplace add and on plugin install, update, refresh, and auto-update, so a marketplace added before the policy was set cannot be used to fetch plugins. Blocked sources are checked before downloading, so they never touch the filesystem. See
Managed marketplace restrictions
[{ "source": "github", "repo": "untrusted/plugins" }]
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
. Session files older than this period are deleted at startup. Setting to
0
is rejected with a validation error. Also controls the age cutoff for automatic removal of
orphaned subagent worktrees
at startup. To disable transcript writes entirely, set the
CLAUDE_CODE_SKIP_PROMPT_HISTORY
environment variable, or in non-interactive mode (
-p
) use the
--no-session-persistence
flag or the
persistSession: false
SDK option.
20
companyAnnouncements
Announcement to display to users at startup. If multiple announcements are provided, they will be cycled through at random.
["Welcome to Acme Corp! Review our code guidelines at docs.acme.com"]
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
commands through PowerShell on Windows. Requires
CLAUDE_CODE_USE_POWERSHELL_TOOL=1
. See
PowerShell tool
"powershell"
deniedMcpServers
When set in managed-settings.json, denylist of MCP servers that are explicitly blocked. Applies to all scopes including managed servers. Denylist takes precedence over allowlist. See
Managed MCP configuration
[{ "serverName": "filesystem" }]
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
and any custom
status line
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
cycle and rejects
--permission-mode auto
at startup. Most useful in
managed settings
where users cannot override it
"disable"
disableBundledSkills
Set to
true
to disable the
skills
and workflows that ship with Claude Code: bundled skills and workflows are removed entirely, while built-in slash commands like
/init
stay typable but are hidden from the model. Skills from plugins,
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
disableDeepLinkRegistration
Set to
"disable"
to prevent Claude Code from registering the
claude-cli://
protocol handler with the operating system on startup.
Deep links
let external tools open a Claude Code session with a pre-filled prompt. Useful in environments where protocol handler registration is restricted or managed separately
"disable"
disabledMcpjsonServers
List of specific MCP servers from
.mcp.json
files to reject
["filesystem"]
disableRemoteControl
Disable
Remote Control
: blocks
claude remote-control
, the
--remote-control
flag, auto-start, and the in-session toggle. Typically placed in
managed settings
for per-device MDM enforcement, but works from any scope. Requires Claude Code v2.1.128 or later
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
enableAllProjectMcpServers
Automatically approve all MCP servers defined in project
.mcp.json
files.
As of v2.1.196,
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
files to approve.
As of v2.1.196,
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
Environment variables applied to every session and to subprocesses Claude Code spawns from it.
As of v2.1.143,
NO_COLOR
and
FORCE_COLOR
set here are passed to subprocesses but do not change Claude Code’s own interface colors. Set those in your shell before launching
claude
to change interface colors.
As of v2.1.195, identity variables that Claude Code’s hosting environments set, for example
CLAUDE_CODE_REMOTE
and
CLAUDE_CODE_ACCOUNT_UUID
, are ignored when set here
{"FOO": "bar"}
fallbackModel
Fallback model(s) to try in order when the primary model is overloaded or unavailable. Claude Code switches to the next available model in the chain for the rest of the turn and shows a notice.
"default"
expands to the default model. Chains are capped at three models; extra entries are ignored. Unlike most array settings, this key does not merge across settings files: the highest-precedence file that defines it supplies the entire chain. The
--fallback-model
flag overrides this for one session. See
Fallback model chains
["claude-sonnet-5", "claude-haiku-4-5"]
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
to restrict login to Claude.ai accounts,
console
to restrict login to Claude Console accounts, or
gateway
to restrict login to a cloud gateway; see
Claude apps gateway
. When set to any value in managed settings, sessions authenticated by
ANTHROPIC_API_KEY
,
ANTHROPIC_AUTH_TOKEN
, or
apiKeyHelper
are blocked at startup, since an environment credential cannot satisfy the required login method. Third-party provider sessions such as Amazon Bedrock, Google Cloud’s Agent Platform, and Microsoft Foundry are not blocked: they authenticate against your cloud provider rather than Anthropic
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
Require login to belong to a specific Anthropic organization. Accepts a single UUID string, which also pre-selects that organization during login, or an array of UUIDs where any listed organization is accepted without pre-selection. When set in managed settings, login fails if the authenticated account does not belong to a listed organization, and sessions authenticated by
ANTHROPIC_API_KEY
,
ANTHROPIC_AUTH_TOKEN
, or
apiKeyHelper
are blocked at startup since organization membership cannot be verified for them. Third-party provider sessions such as Amazon Bedrock, Google Cloud’s Agent Platform, and Microsoft Foundry are not blocked: use your cloud IAM to restrict which cloud accounts can be used. An empty array fails closed and blocks login with a misconfiguration message
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
. Requires Claude Code v2.1.119 or later
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
and auto-generated session titles.
As of v2.1.176, when not set, session titles match the language of your conversation
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
. Controls whether managed settings supplied programmatically by an embedding host process, such as the Agent SDK or an IDE extension, apply when an admin-deployed managed tier is also present.
"first-wins"
: the parent-supplied settings are dropped and only the admin tier applies.
"merge"
: the parent-supplied settings apply under the admin tier, filtered so they can tighten policy but not loosen it. Has no effect when no admin tier is deployed. Requires Claude Code v2.1.133 or later
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
. Requires Claude Code v2.1.136 or later
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
remoteControlAtStartup
Connect
Remote Control
automatically when each interactive session starts, instead of waiting for
/remote-control
. Set to
true
to always auto-connect,
false
to never auto-connect, or leave unset to follow your organization’s default. Appears in
/config
as
Enable Remote Control for all sessions
. See
Enable Remote Control for all sessions
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
. Show turn duration messages after responses, e.g. “Cooked for 1m 6s”. Appears in
/config
as
Show turn duration
false
skillListingBudgetFraction
Default
:
0.01
(1%). Fraction of the model’s context window reserved for the
skill listing
Claude sees each turn. When the listing exceeds the budget, descriptions for the least-used skills are collapsed to bare names so Claude can still invoke them but won’t see why. Raise to keep more descriptions visible at the cost of more context per turn.
/doctor
shows the current truncation count and which skills are affected. Requires Claude Code v2.1.105 or later
0.02
skillListingMaxDescChars
Default
:
1536
. Per-skill character cap on the combined
description
and
when_to_use
text in the
skill listing
Claude sees each turn. Text longer than this is truncated. Raise to keep long descriptions intact at the cost of more context per turn; lower to fit more skills under
skillListingBudgetFraction
. Requires Claude Code v2.1.105 or later
2048
skillOverrides
Per-skill visibility overrides keyed by skill name. Value is
"on"
,
"name-only"
,
"user-invocable-only"
, or
"off"
. Lets you hide or collapse a skill without editing its SKILL.md. Does not apply to plugin skills, which are managed through
/plugin
. The
/skills
menu writes these to
.claude/settings.local.json
. See
Override skill visibility from settings
. Requires Claude Code v2.1.129 or later
{"legacy-context": "name-only", "deploy": "off"}
skipWebFetchPreflight
Skip the
WebFetch domain safety check
that sends each requested hostname to
api.anthropic.com
before fetching. Set to
true
in environments that block traffic to Anthropic, such as Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry deployments with restrictive egress. When skipped, WebFetch attempts any URL without consulting the blocklist
true
spinnerTipsEnabled
Default
:
true
. Show tips in the spinner while Claude is working. Set to
false
to disable tips
false
spinnerTipsOverride
Override spinner tips with custom strings.
tips
: array of tip strings.
excludeDefault
: if
true
, only show custom tips; if
false
or absent, custom tips are merged with built-in tips
{ "excludeDefault": true, "tips": ["Use our internal tool X"] }
spinnerVerbs
Customize the action verbs shown while a turn is in progress. Set
mode
to
"replace"
to use only your verbs, or
"append"
to add them to the defaults
{"mode": "append", "verbs": ["Pondering", "Crafting"]}
sshConfigs
SSH connections to show in the
Desktop
environment dropdown. Each entry requires
id
,
name
, and
sshHost
;
sshPort
,
sshIdentityFile
, and
startDirectory
are optional. When set in managed settings, connections are read-only for users. Read from managed and user settings only
[{"id": "dev-vm", "name": "Dev VM", "sshHost": "user@dev.example.com"}]
statusLine
Configure a custom status line to display context. The object’s optional
padding
,
refreshInterval
, and
hideVimModeIndicator
fields control spacing, periodic re-runs, and whether the built-in vim mode indicator below the prompt is hidden. See
statusLine
documentation
{"type": "command", "command": "~/.claude/statusline.sh"}
strictKnownMarketplaces
(Managed settings only) Allowlist of plugin marketplace sources. Undefined = no restrictions, empty array = lockdown. Enforced on marketplace add and on plugin install, update, refresh, and auto-update, so a marketplace added before the policy was set cannot be used to fetch plugins. See
Managed marketplace restrictions
[{ "source": "github", "repo": "acme-corp/plugins" }]
strictPluginOnlyCustomization
(Managed settings only) Block skills, agents, hooks, and MCP servers from user and project sources, so they can only come from plugins or managed settings.
true
locks all four surfaces; an array locks only the named ones. See
strictPluginOnlyCustomization
["skills", "hooks"]
syntaxHighlightingDisabled
Disable syntax highlighting in diffs, code blocks, and file previews
true
teammateMode
Default
:
in-process
. How
agent team
teammates display:
in-process
,
auto
(split panes when running inside tmux, or inside iTerm2 with
it2
on your
PATH
; in-process otherwise),
tmux
(split panes using tmux or iTerm2, detected from your terminal), or
iterm2
(iTerm2 native split panes via the
it2
CLI, added in v2.1.186). The default changed from
auto
in v2.1.179.
--teammate-mode
overrides this for one session. See
choose a display mode
"auto"
terminalProgressBarEnabled
Default
:
true
. Show the terminal progress bar in supported terminals: ConEmu, Ghostty 1.2.0+, and iTerm2 3.6.6+. Appears in
/config
as
Terminal progress bar
false
theme
Default
:
"dark"
. Color theme for the interface:
"auto"
,
"dark"
,
"light"
,
"dark-daltonized"
,
"light-daltonized"
,
"dark-ansi"
,
"light-ansi"
, or a custom theme reference such as
"custom:<slug>"
or
"custom:<plugin-name>:<slug>"
. See
Create a custom theme
. Appears in
/config
as
Theme
"dark"
tui
Terminal UI renderer. Use
"fullscreen"
for the flicker-free
alt-screen renderer
with virtualized scrollback. Use
"default"
for the classic main-screen renderer. Set via
/tui
. You can also set the
CLAUDE_CODE_NO_FLICKER
environment variable. Background sessions opened from
agent view
always use the fullscreen renderer regardless of this setting
"fullscreen"
ultracode
Turn on
ultracode
for the session. Session-only and not read from
settings.json
. Set through
/effort ultracode
,
--settings
, or an Agent SDK control request
true
useAutoModeDuringPlan
Default
:
true
. Whether plan mode uses auto mode semantics when auto mode is available. Not read from shared project settings. Appears in
/config
as “Use auto mode during plan”
false
verbose
Default
:
false
. Show full tool output instead of truncated summaries. Appears in
/config
as
Verbose output
. The
--verbose
flag overrides this for one session
true
viewMode
Default transcript view mode on startup:
"default"
,
"verbose"
, or
"focus"
. Overrides the sticky
/focus
selection when set. The
--verbose
flag overrides this for one session
"verbose"
voice
Voice dictation
settings:
enabled
turns dictation on,
mode
selects
"hold"
or
"tap"
, and
autoSubmit
sends the prompt on key release in hold mode. Written automatically when you run
/voice
. Requires a Claude.ai account
{ "enabled": true, "mode": "tap" }
voiceEnabled
Legacy alias for
voice.enabled
. Prefer the
voice
object
true
wheelScrollAccelerationEnabled
Default
:
true
. In
fullscreen rendering
, accelerate mouse-wheel scroll speed during fast scrolls. Set to
false
for a constant scroll rate per wheel notch. Requires Claude Code v2.1.174 or later
false
workflowKeywordTriggerEnabled
Default
:
true
. Whether the keyword
ultracode
in a prompt triggers a
dynamic workflow
. Set to
false
to type the word without triggering one. The
ultracode
effort setting,
/workflows
, and saved workflow commands are unaffected. Appears in
/config
as
Ultracode keyword trigger
. Added in v2.1.157; before v2.1.160 the trigger keyword was
workflow
false
wslInheritsWindowsSettings
(Windows managed settings only) When
true
, Claude Code on WSL reads managed settings from the Windows policy chain in addition to
/etc/claude-code
, with Windows sources taking priority. Only honored when set in the HKLM registry key or
C:\Program Files\ClaudeCode\managed-settings.json
, both of which require Windows admin to write. For HKCU policy to also apply on WSL, the flag must additionally be set in HKCU itself. Has no effect on native Windows
true
​
Global config settings
These settings are stored in
~/.claude.json
rather than
settings.json
. Adding them to
settings.json
will trigger a schema validation error.
Versions before v2.1.119 also store a number of
/config
preference keys here instead of in
settings.json
, including
theme
,
verbose
,
editorMode
,
autoCompactEnabled
, and
preferredNotifChannel
.
Key
Description
Example
autoConnectIde
Default
:
false
. Automatically connect to a running IDE when Claude Code starts from an external terminal. Appears in
/config
as
Auto-connect to IDE (external terminal)
when running outside a VS Code or JetBrains terminal. The
CLAUDE_CODE_AUTO_CONNECT_IDE
environment variable overrides this when set
true
autoInstallIdeExtension
Default
:
true
. Automatically install the Claude Code IDE extension when running from a VS Code terminal. Appears in
/config
as
Auto-install IDE extension
when running inside a VS Code or JetBrains terminal. You can also set the
CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL
environment variable to
1
false
externalEditorContext
Default
:
false
. Prepend Claude’s previous response as
#
-commented context when you open the external editor with
Ctrl+G
. Appears in
/config
as
Show last response in external editor
true
teammateDefaultModel
Default model for
agent team
teammates when the spawn prompt doesn’t specify one. Set to a model alias such as
"sonnet"
, or
null
to inherit the lead’s current
/model
selection. Appears in
/config
as
Default teammate model
"sonnet"
​
Worktree settings
Configure how
--worktree
creates and manages git worktrees.
Key
Description
Example
worktree.baseRef
Which ref new worktrees branch from.
"fresh"
(default) branches from
origin/<default-branch>
for a clean tree matching the remote.
"head"
branches from your current local
HEAD
, so unpushed commits and feature-branch state are present in the worktree. Applies to
--worktree
, the
EnterWorktree
tool, and subagent isolation
"head"
worktree.symlinkDirectories
Directories to symlink from the main repository into each worktree to avoid duplicating large directories on disk. No directories are symlinked by default
["node_modules", ".cache"]
worktree.sparsePaths
Directories to check out in each worktree via git sparse-checkout. Only the listed directories plus root-level files are written to disk, which is faster in large monorepos
["packages/my-app", "shared/utils"]
worktree.bgIsolation
Isolation mode for
background sessions
.
"worktree"
(default) blocks
Edit
/
Write
in the main checkout until
EnterWorktree
is called.
"none"
lets background jobs edit the working copy directly. Requires Claude Code v2.1.143 or later
"none"
To copy gitignored files like
.env
into new worktrees, use a
.worktreeinclude
file
in your project root instead of a setting.


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
. For sessions that communicate with each other, see
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
Claude Code includes several built-in subagents such as Explore, Plan, and general-purpose. You can also create custom subagents to handle specific tasks.
​
Built-in subagents
Claude Code includes built-in subagents that Claude automatically uses when appropriate. Each inherits the parent conversation’s permissions with additional tool restrictions.
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
: all tools
Purpose
: complex research, multi-step operations, code modifications
Claude delegates to general-purpose when the task requires both exploration and modification, complex reasoning to interpret results, or multiple dependent steps.
Claude Code includes additional helper agents for specific tasks. These are typically invoked automatically, so you don’t need to use them directly.
Agent
Model
When Claude uses it
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
Claude delegates to your new subagent, which scans the codebase and returns improvement suggestions.
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
between there and the repository root is scanned.
As of v2.1.178, when more than one of these nested directories defines the same
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
values unique across the whole tree: if two files within one scope declare the same name, Claude Code loads only one of them.
As of v2.1.196, running
/doctor
reports same-scope duplicate agent names and shows which definition is active.
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
flag accepts JSON with the same
frontmatter
fields as file-based subagents:
description
,
prompt
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
,
isolation
, and
color
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
you’ve installed. They load alongside your custom subagents and appear in the @-mention typeahead under their scoped name. See the
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
A subagent starts in the main conversation’s current working directory. Within a subagent,
cd
commands don’t persist between Bash or PowerShell tool calls and don’t affect the main conversation’s working directory. To give the subagent an isolated copy of the repository instead, set
isolation: worktree
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
. The filename doesn’t have to match
description
Yes
When Claude should delegate to this subagent
tools
No
Tools
the subagent can use. Inherits all tools if omitted. To preload Skills into context, use the
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
claude-opus-4-8
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
to always run this subagent as a
background task
, even when Claude needs its result right away. When unset, Claude chooses, and
as of v2.1.198 it runs subagents in the background by default
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
claude-opus-4-8
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
allowlist. It skips a value that resolves to an excluded model and runs the subagent on the inherited model instead.
As of v2.1.198, subagents also inherit the main conversation’s
extended thinking
configuration: if thinking is on in your session, it’s on for the subagent, and if it’s off, it stays off. There is no per-subagent thinking setting. Before v2.1.198, subagents ran with extended thinking disabled regardless of the main conversation’s setting.
​
Control subagent capabilities
You can control what subagents can do through tool access, permission modes, and conditional rules.
​
Available tools
Subagents inherit the
internal tools
and MCP tools available in the main conversation by default. The following tools depend on the main conversation’s UI or session state and aren’t available to subagents, even when listed in the
tools
field:
AskUserQuestion
EnterPlanMode
ExitPlanMode
, unless the subagent’s
permissionMode
is
plan
ScheduleWakeup
WaitForMcpServers
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
to inherit every tool from the main conversation except Write and Edit. The subagent keeps Bash, MCP tools, and everything else:
---
name
:
no-writes
description
:
Inherits every tool except file writes
disallowedTools
:
Write, Edit
---
If both are set,
disallowedTools
is applied first, then
tools
is resolved against the remaining pool. A tool listed in both is removed.
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
MCP server while keeping tools from other servers and every built-in tool:
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
If
Agent
is omitted from the
tools
list entirely, the agent can’t spawn any subagents.
The
Agent(agent_type)
allowlist syntax applies only to an agent running as the main thread with
claude --agent
. In a subagent definition, listing
Agent
in
tools
lets that subagent
spawn nested subagents
, but any type list inside the parentheses is ignored.
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
and settings files.
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
The
permissionMode
field controls how the subagent handles permission prompts. Subagents inherit the permission context from the main conversation and can override the mode, except when the parent mode takes precedence as described below.
Mode
Behavior
default
Standard permission checking with prompts
acceptEdits
Auto-accept file edits and common filesystem commands for paths in the working directory or
additionalDirectories
auto
Auto mode
: a background classifier reviews commands and protected-directory writes
dontAsk
Auto-deny permission prompts (explicitly allowed tools still work)
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
. Explicit
ask
rules
and root and home directory removals such as
rm -rf /
still prompt. See
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
, since preloading draws from the same set of skills Claude can invoke. If a listed skill is missing or disabled, Claude Code skips it and logs a warning to the debug log.
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
: define hooks that run in the main session when subagents start or stop
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
.
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
This works with built-in and custom subagents, and the choice persists when you resume the session.
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
run concurrently while you continue working.
As of v2.1.186, when a background subagent reaches a tool call that needs permission, the prompt surfaces in your main session and names the subagent that is asking. Approve to let the subagent continue, or press Esc to deny that one tool call without stopping the subagent. Before v2.1.186, background subagents auto-denied any tool call that would have prompted.
As of v2.1.198, subagents run in the background by default. Claude runs a subagent in the foreground when it needs the result before continuing. The default changes where a subagent runs, not what it’s allowed to do: background subagents still surface every permission prompt in your main session. Before v2.1.198, Claude chose between foreground and background based on the task.
You can also steer this yourself:
Ask Claude to run a task in the background or in the foreground
Press
Ctrl+B
to background a running task
To disable all background task functionality, set the
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS
environment variable to
1
. See
Environment variables
.
When
CLAUDE_CODE_FORK_SUBAGENT
is set to
1
, every subagent spawn runs in the background and the frontmatter
background
field has no effect, because fork mode removes the
run_in_background
parameter from the
Agent
tool.
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS
takes precedence over fork mode and keeps subagent spawns in the foreground.
​
API errors in subagents
As of v2.1.199, a subagent whose run ends on an API error, such as a usage limit or a repeated server error, reports that failure back to Claude instead of returning the error text as if it were the subagent’s findings. What Claude receives depends on where the subagent ran:
Foreground
: if a rate limit, overload, or server error cuts off a subagent that already produced text output, the Agent tool returns that partial output with a note that the subagent was cut off and didn’t finish its task.
A subagent that produced nothing, or whose only output was tool calls, fails with
Agent terminated early due to an API error
, followed by the error detail. In v2.1.199, a rate limit, overload, or server error that cut off the tool-calls-only shape returned an empty partial result containing only the cut-off note instead.
Background
: the subagent is marked failed, and the message Claude receives when it ends names the API error and includes the subagent’s last output, so partial work isn’t lost.
Once the underlying API error clears, ask Claude to retry the task or
resume the subagent
.
​
Common patterns
​
Isolate high-volume operations
One of the most effective uses for subagents is isolating operations that produce large amounts of output. Running tests, fetching documentation, or processing log files can consume significant context. By delegating these to a subagent, the verbose output stays in the subagent’s context while only the relevant summary returns to your main conversation.
Use a subagent to run the test suite and report only the failing tests with their error messages
​
Run parallel research
For independent investigations, spawn multiple subagents to work simultaneously:
Research the authentication, database, and API modules in parallel using separate subagents
Each subagent explores its area independently, then Claude synthesizes the findings. This works best when the research paths don’t depend on each other.
When subagents complete, their results return to your main conversation. Running many subagents that each return detailed results can consume significant context.
For tasks that need sustained parallelism or exceed your context window,
agent teams
give each worker its own independent context.
​
Chain subagents
For multi-step workflows, ask Claude to use subagents in sequence. Each subagent completes its task and returns results to Claude, which then passes relevant context to the next subagent.
Use the code-reviewer subagent to find performance issues, then use the optimizer subagent to fix them
​
Choose between subagents and main conversation
Use the
main conversation
when:
The task needs frequent back-and-forth or iterative refinement
Multiple phases share significant context, such as planning, implementation, and testing
You’re making a quick, targeted change
Latency matters. Subagents start fresh and may need time to gather context
Use
subagents
when:
The task produces verbose output you don’t need in your main context
You want to enforce specific tool restrictions or permissions
The work is self-contained and can return a summary
Consider
Skills
instead when you want reusable prompts or workflows that run in the main conversation context rather than isolated subagent context.
For a quick question about something already in your conversation, use
/btw
instead of a subagent. It sees your full context but has no tool access, and the answer is discarded rather than added to history.
​
Spawn nested subagents
As of Claude Code v2.1.172, a subagent can spawn its own subagents. Use this when a delegated task itself splits into parallel subtasks, such as a reviewer subagent that dispatches a verifier per finding, so the intermediate output never reaches your main conversation. Only the top-level subagent’s summary returns to you.
A nested subagent is configured the same way as a top-level one and resolves from the same
scopes
.
The subagent panel below the prompt input shows the full tree: each row displays a
(+N)
count of descendants, and
as of v2.1.193, opening a row shows that subagent’s siblings and direct children with a path back to
main
.
Depth is counted as the number of subagent levels below the main conversation, regardless of whether each level runs in the
foreground or background
. A subagent at depth five doesn’t receive the Agent tool and can’t spawn further. The limit is fixed and not configurable.
As of Claude Code v2.1.187, a background subagent’s depth is fixed when it is first spawned, and
resuming
it later doesn’t change that depth. For example, if your main conversation spawns subagent A, and A spawns a background subagent B at depth two, B is still at depth two when you resume it directly from the main conversation. Resuming a subagent from a shallower context doesn’t let it spawn additional levels that the depth limit already prevented.
To prevent a specific subagent from spawning others, omit
Agent
from its
tools
list or add it to
disallowedTools
.
A
fork
still can’t spawn another fork. It can spawn other subagent types, and those count toward the depth limit.
​
Manage subagent context
​
What loads at startup
Each subagent starts with a fresh, isolated context window. It doesn’t see your conversation history, the skills you’ve already invoked, or the files Claude has already read. Claude composes a delegation message that summarizes the task, and the subagent works from there. The exception is a
fork
, which inherits the parent conversation instead of starting fresh.
A non-fork subagent’s initial context contains:
System prompt
: the agent’s own prompt plus environment details that Claude Code appends, not the full Claude Code system prompt. Custom subagents define theirs in the
markdown body
or
prompt
field. Built-in agents have predefined prompts.
Task message
: the delegation prompt Claude writes when it hands off the work.
CLAUDE.md and memory
: every level of the
memory hierarchy
the main conversation loads, including
~/.claude/CLAUDE.md
, project rules,
CLAUDE.local.md
, and managed policy files. The built-in Explore and Plan agents skip this.
Git status
: a snapshot taken at the start of the parent session. Absent when the working directory isn’t a Git repository or when
includeGitInstructions
is
false
. Explore and Plan skip it regardless.
Preloaded skills
: full content of any skill named in the agent’s
skills
field
. Built-in agents don’t preload skills.
Explore and Plan are the only subagents that omit CLAUDE.md and git status. There is no frontmatter field or per-agent setting to change which agents skip them.
The main conversation reads Explore and Plan results with full CLAUDE.md context, so most rules don’t need to reach the subagent itself. If a rule must, such as “ignore the
vendor/
directory,” restate it in the prompt you give Claude when delegating.
​
Resume subagents
Each subagent invocation creates a new instance with fresh context. To continue an existing subagent’s work instead of starting over, ask Claude to resume it.
Resumed subagents retain their full conversation history, including all previous tool calls, results, and reasoning. The subagent picks up exactly where it stopped rather than starting fresh.
When a subagent completes, Claude receives its agent ID. The built-in Explore and Plan agents are one-shot and return no agent ID, so they can’t be resumed; use
general-purpose
or a custom subagent when you need to continue the work.
Claude uses the
SendMessage
tool with the agent’s ID or name as the
to
field to resume it.
SendMessage
doesn’t require
agent teams
to be enabled; only structured team-protocol messages such as
shutdown_request
and
plan_approval_response
do.
To resume a subagent, ask Claude to continue the previous work:
Use the code-reviewer subagent to review the authentication module
[Agent completes]
Continue that code review and now analyze the authorization logic
[Claude resumes the subagent with full context from previous conversation]
If a stopped subagent receives a
SendMessage
, it auto-resumes in the background without requiring a new
Agent
invocation.
As of v2.1.199,
SendMessage
checks that a name still refers to the same agent it reached earlier in the conversation. If a newer agent has taken the name, such as a re-spawned background agent that reused it, Claude Code refuses the send rather than delivering it to the wrong agent, and the error reports which agent the name now reaches so Claude can retarget. To reach the earlier agent while it’s still running, Claude addresses it by the agent ID from its spawn result. The check is scoped to the current conversation and resets on
/clear
.
As of v2.1.198, a subagent treats messages from the agent that launched it as normal task direction, including mid-task course corrections, and acts on them within its own permission settings. Two limits still hold regardless of who sent the message: no message from any agent counts as your approval for a pending permission prompt, and no agent message can change a subagent’s permission settings,
CLAUDE.md
, or configuration. Only the permission system or your own messages can grant approval.
You can also ask Claude for the agent ID if you want to reference it explicitly, or find IDs in the transcript files at
~/.claude/projects/{project}/{sessionId}/subagents/
. Each transcript is stored as
agent-{agentId}.jsonl
.
Subagent transcripts persist independently of the main conversation:
Main conversation compaction
: when the main conversation compacts, subagent transcripts are unaffected. They’re stored in separate files.
Session persistence
: subagent transcripts persist within their session. You can
resume a subagent
after restarting Claude Code by resuming the same session.
Automatic cleanup
: transcripts are cleaned up based on the
cleanupPeriodDays
setting, which defaults to 30 days.
​
Auto-compaction
Subagents support automatic compaction using the same logic as the main conversation. Compaction triggers under the same conditions, and
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE
applies to subagents as well. See
environment variables
for when the override takes effect.
Compaction events are logged in subagent transcript files:
{
"type"
:
"system"
,
"subtype"
:
"compact_boundary"
,
"compactMetadata"
: {
"trigger"
:
"auto"
,
"preTokens"
:
167189
}
}
The
preTokens
value shows how many tokens were used before compaction occurred.
​

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
Hooks are user-defined shell commands, HTTP endpoints, or LLM prompts that execute automatically at specific points in Claude Code’s lifecycle. Use this reference to look up event schemas, configuration options, JSON input/output formats, and advanced features like async hooks, HTTP hooks, and MCP tool hooks. If you’re setting up hooks for the first time, start with the
guide
instead.
​
Hook lifecycle
Hooks fire at specific points during a Claude Code session. When an event fires and a matcher matches, Claude Code passes JSON context about the event to your hook handler. For command hooks, input arrives on stdin. For HTTP hooks, it arrives as the POST request body. Your handler can then inspect the input, take action, and optionally return a decision.
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
When a permission dialog appears
PermissionDenied
When a tool call is denied by the auto mode classifier. Return
{retry: true}
to tell the model it may retry the denied tool call
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
When the turn ends due to an API error. Output and exit code are ignored
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
FileChanged
When a watched file changes on disk. The
matcher
field specifies which filenames to watch
WorktreeCreate
When a worktree is being created via
--worktree
or
isolation: "worktree"
. Replaces default git behavior
WorktreeRemove
When a worktree is being removed, either at session exit or when a subagent finishes
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
hook that blocks destructive shell commands. The
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
:
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
Now suppose Claude Code decides to run
Bash "rm -rf /tmp/build"
. Here’s what happens:
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
No, gitignored when Claude Code creates it
Managed policy settings
Organization-wide
Yes, admin-controlled
Plugin
hooks/hooks.json
When plugin is enabled
Yes, bundled with the plugin
Skill
or
agent
frontmatter
While the component is active
Yes, defined in the component file
For details on settings file resolution, see
settings
.
Enterprise administrators can use
allowManagedHooksOnly
to block user, project, and plugin hooks. Hooks from plugins force-enabled in managed settings
enabledPlugins
are exempt, so administrators can distribute vetted hooks through an organization marketplace. See
Hook configuration
.
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
, and
CwdChanged
don’t support matchers and always fire on every occurrence. If you add a
matcher
field to these events, it is silently ignored.
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
): send a prompt to a Claude model for single-turn evaluation. The model returns a yes/no decision as JSON. See
Prompt-based hooks
.
Agent hooks
(
type: "agent"
): spawn a subagent that can use tools like Read, Grep, and Glob to verify conditions before returning a decision. Agent hooks are experimental and may change. See
Agent-based hooks
.
All matching hooks run in parallel, and identical handlers are deduplicated automatically. Command hooks are deduplicated by command string and
args
, and HTTP hooks are deduplicated by URL.
Handlers run in the current directory with Claude Code’s environment. The
$CLAUDE_CODE_REMOTE
environment variable is set to
"true"
in remote web environments and not set in the local CLI.
As of v2.1.199,
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
lowers it to 10
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
regardless of how it was launched. Plugin hooks additionally substitute
${user_config.*}
values; see
User configuration
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
Error handling differs from command hooks: non-2xx responses, connection failures, and timeouts all produce non-blocking errors that allow execution to continue. To block a tool call or deny a permission, return a 2xx response with a JSON body containing
decision: "block"
or a
hookSpecificOutput
with
permissionDecision: "deny"
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
Name of a configured MCP server. The server must already be connected; the hook never triggers an OAuth or connection flow
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
The tool’s text content is treated like command-hook stdout: if it parses as valid
JSON output
it is processed as a decision, otherwise it is shown as plain text. If the named server is not connected, or the tool returns
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
for any hook that references a path placeholder. Exec form passes each
args
element as one argument with no shell tokenization, so paths with spaces or special characters need no quoting. In shell form, wrap each placeholder in double quotes.
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
using frontmatter. These hooks are scoped to the component’s lifecycle and only run when that component is active.
All hook events are supported. For subagents,
Stop
hooks are automatically converted to
SubagentStop
since that is the event that fires when a subagent completes.
Hooks use the same configuration format as settings-based hooks but are scoped to the component’s lifetime and cleaned up when it finishes.
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
Agents use the same format in their YAML frontmatter.
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
User
: from
~/.claude/settings.json
Project
: from
.claude/settings.json
Local
: from
.claude/settings.local.json
Plugin
: from a plugin’s
hooks/hooks.json
Session
: registered in memory for the current session
Built-in
: registered internally by Claude Code
Selecting a hook opens a detail view showing its event, matcher, type, source file, and the full command, prompt, or URL. The menu is read-only: to add, modify, or remove hooks, edit the settings JSON directly or ask Claude to make the change.
​
Disable or remove hooks
To remove a hook, delete its entry from the settings JSON file.
To temporarily disable all hooks without removing them, set
"disableAllHooks": true
in your settings file. There is no way to disable an individual hook while keeping it in the configuration.
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
On macOS and Linux, command hooks run in their own session without a controlling terminal as of v2.1.139. The hook process and any child processes can’t open
/dev/tty
or send escape sequences directly to the Claude Code interface. Windows has no
/dev/tty
. To surface a message to the user on any platform, return
systemMessage
in JSON output. To trigger a desktop notification, set a window title, or ring the bell, return
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
, so you can correlate hook output with telemetry for a single prompt. Absent until the first user input.
Requires Claude Code v2.1.196 or later
transcript_path
Path to conversation JSON
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
value. For
custom subagents
, this is the
name
field from the agent’s frontmatter, not the filename. For subagents shipped by a
plugin
, this is the plugin-scoped identifier such as
my-plugin:reviewer
, not the bare frontmatter name. See
SubagentStart
for how to write a matcher against a plugin-scoped name.
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
during a session.
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
}
}
The
tool_name
and
tool_input
fields are event-specific. Each
hook event
section documents the additional fields for that event.
​
Exit code output
The exit code from your hook command tells Claude Code whether the action should proceed, be blocked, or be ignored.
Exit 0
means success. Claude Code parses stdout for
JSON output fields
. JSON output is only processed on exit 0. For most events, stdout is written to the debug log but not shown in the transcript. The exceptions are
UserPromptSubmit
,
UserPromptExpansion
, and
SessionStart
, where stdout is added as context that Claude can see and act on.
Exit 2
means a blocking error. Claude Code ignores stdout and any JSON in it. Instead, stderr text is fed back to Claude as an error message. The effect depends on the event:
PreToolUse
blocks the tool call,
UserPromptSubmit
rejects the prompt, and so on. See
exit code 2 behavior
for the full list.
Any other exit code
is a non-blocking error for most hook events. The transcript shows a
<hook name> hook error
notice followed by the first line of stderr, so you can identify the cause without
--debug
. Execution continues and the full stderr is written to the debug log.
For example, a hook command script that blocks dangerous Bash commands:
#!/bin/bash
# Reads JSON input from stdin, checks the command
command
=
$(
jq
-r
'.tool_input.command'
<
/dev/stdin
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
For most hook events, only exit code 2 blocks the action. Claude Code treats exit code 1 as a non-blocking error and proceeds with the action, even though 1 is the conventional Unix failure code. If your hook is meant to enforce a policy, use
exit 2
. The exception is
WorktreeCreate
, where any non-zero exit code aborts worktree creation.
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
Yes
Denies the permission
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
Output and exit code are ignored
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
to tell the model it may retry
Notification
No
Shows stderr to user only
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
As of Claude Code v2.1.199,
SessionStart
,
Setup
, and
SubagentStart
show exit code 2 stderr in the transcript. Earlier versions wrote it to the debug log only.
​
HTTP response handling
HTTP hooks use HTTP status codes and response bodies instead of exit codes and stdout:
2xx with an empty body
: success, equivalent to exit code 0 with no output
2xx with a plain text body
: success, the text is added as context
2xx with a JSON body
: success, parsed using the same
JSON output
schema as command hooks
Non-2xx status
: non-blocking error, execution continues
Connection failure or timeout
: non-blocking error, execution continues
Unlike command hooks, HTTP hooks can’t signal a blocking error through status codes alone. To block a tool call or deny a permission, return a 2xx response with a JSON body containing the appropriate decision fields.
​
JSON output
Exit codes only let you block or stay silent, but JSON output gives you finer-grained control. Instead of exiting with code 2 to block, exit 0 and print a JSON object to stdout. Claude Code reads specific fields from that JSON to control behavior, including
decision control
for blocking, allowing, or escalating to the user.
You must choose one approach per hook, not both: either use exit codes alone for signaling, or exit 0 and print JSON for structured control. Claude Code only processes JSON on exit 0. If you exit 2, any JSON is ignored.
Your hook’s stdout must contain only the JSON object. If your shell profile prints text on startup, it can interfere with JSON parsing. See
JSON validation failed
in the troubleshooting guide.
Hook output strings, including
additionalContext
,
systemMessage
, and plain stdout, are capped at 10,000 characters. Output that exceeds this limit is saved to a file and replaced with a preview and file path, the same way large tool results are handled.
The JSON object supports three kinds of fields:
Universal fields
like
continue
work across all events. These are listed in the table below.
Top-level
decision
and
reason
are used by some events to block or provide feedback.
hookSpecificOutput
is a nested object for events that need richer control. It requires a
hookEventName
field set to the event name.
Field
Default
Description
continue
true
If
false
, Claude stops processing entirely after the hook runs. Takes precedence over any event-specific decision fields
stopReason
none
Message shown to the user when
continue
is
false
. Not shown to Claude
suppressOutput
false
If
true
, hides the hook’s stdout from the transcript. Stdout still appears in the debug log
systemMessage
none
Warning message shown to the user
terminalSequence
none
A terminal escape sequence for Claude Code to emit on your behalf, such as a desktop notification, window title, or bell. Restricted to OSC
0
/
1
/
2
/
9
/
99
/
777
and BEL. If the value contains anything outside the allowlist, the field is ignored. Use this instead of writing to
/dev/tty
, which is unavailable to hooks
To stop Claude entirely regardless of event type:
{
"continue"
:
false
,
"stopReason"
:
"Build failed, fix errors before continuing"
}
​
Emit terminal notifications
The
terminalSequence
field requires Claude Code v2.1.141 or later.
Hooks run without a controlling terminal, so writing escape sequences directly to
/dev/tty
fails. Instead, return the escape sequence in the
terminalSequence
field and Claude Code emits it for you through its own terminal write path. This is race-free, works inside tmux and GNU screen, and works on Windows where there is no
/dev/tty
.
The field accepts a string of one or more allowlisted escape sequences:
OSC
0
,
1
,
2
: window and icon titles
OSC
9
: iTerm2, ConEmu, Windows Terminal, and WezTerm notifications, including
9;4
taskbar progress
OSC
99
: Kitty notifications
OSC
777
: urxvt, Ghostty, and Warp notifications
Bare BEL
Sequences may be terminated with BEL or with ST. Anything outside the allowlist, including CSI cursor and color sequences, OSC palette sequences, OSC 8 hyperlinks, OSC 52 clipboard writes, and OSC 1337, is rejected and the field is ignored.
The example below fires a desktop notification from a
Notification
hook. The escape sequence is built with
printf
octal escapes so the control bytes never appear on the shell command line, and
jq -n --arg
builds the JSON output so quotes, backslashes, and newlines in the notification message are escaped correctly:
#!/bin/bash
# Notification hook: ping the desktop when Claude Code needs attention.
input
=
$(
cat
)
title
=
"Claude Code"
body
=
$(
jq
-r
'.message // "Needs your attention"'
<<<
"
$input
"
)
seq
=
$(
printf
'\033]777;notify;%s;%s\007'
"
$title
"
"
$body
"
)
jq
-nc
--arg
seq
"
$seq
"
'{terminalSequence: $seq}'
The
{ "terminalSequence": "..." }
shape is the same from any shell or language. On Windows, build the escape string in PowerShell or a script and emit the same JSON object.
terminalSequence
is the supported replacement for hooks that previously wrote escape sequences directly to
/dev/tty
. The allowlist is restricted to sequences that can’t move the cursor or alter colors, so a hook can never corrupt an on-screen prompt.
​
Add context for Claude
The
additionalContext
field passes a string from your hook into Claude’s context window. Claude Code wraps the string in a system reminder and inserts it into the conversation at the point where the hook fired. Claude reads the reminder on the next model request, but it doesn’t appear as a chat message in the interface.
Return
additionalContext
inside
hookSpecificOutput
alongside the event name:
{
"hookSpecificOutput"
: {
"hookEventName"
:
"PostToolUse"
,
"additionalContext"
:
"This file is generated. Edit src/schema.ts and run `bun generate` instead."
}
}
Where the reminder appears depends on the event:
SessionStart
,
Setup
, and
SubagentStart
: at the start of the conversation, before the first prompt
UserPromptSubmit
and
UserPromptExpansion
: alongside the submitted prompt
PreToolUse
,
PostToolUse
,
PostToolUseFailure
, and
PostToolBatch
: next to the tool result
Stop
and
SubagentStop
: at the end of the turn. The conversation continues so Claude can act on the feedback. See
Stop decision control
When several hooks return
additionalContext
for the same event, Claude receives all of the values. If a value exceeds 10,000 characters, Claude Code writes the full text to a file in the session directory and passes Claude the file path with a short preview instead.
Use
additionalContext
for information Claude should know about the current state of your environment or the operation that just ran:
Environment state
: the current branch, deployment target, or active feature flags
Conditional project rules
: which test command applies to the file just edited, which directories are read-only in this worktree
External data
: open issues assigned to you, recent CI results, content fetched from an internal service
For instructions that never change, prefer
CLAUDE.md
. It loads without running a script and is the standard place for static project conventions.
Write the text as factual statements rather than imperative system instructions. Phrasing such as “The deployment target is production” or “This repo uses
bun test
” reads as project information. Text framed as out-of-band system commands can trigger Claude’s prompt-injection defenses, which causes Claude to surface the text to you instead of treating it as context.
Once injected, the text is saved in the session transcript. For mid-session events like
PostToolUse
or
UserPromptSubmit
, resuming with
--continue
or
--resume
replays the saved text rather than re-running the hook for past turns, so values like timestamps or commit SHAs become stale on resume.
SessionStart
hooks run again on resume with
source
set to
"resume"
, so they can refresh their context.
​
Decision control
Not every event supports blocking or controlling behavior through JSON. The events that do each use a different set of fields to express that decision. Use this table as a quick reference before writing a hook:
Events
Decision pattern
Key fields
UserPromptSubmit, UserPromptExpansion, PostToolUse, PostToolUseFailure, PostToolBatch, Stop, SubagentStop, ConfigChange, PreCompact
Top-level
decision
decision: "block"
,
reason
. Stop and SubagentStop also accept
hookSpecificOutput.additionalContext
for
non-error feedback that continues the conversation
TeammateIdle, TaskCreated, TaskCompleted
Exit code or
continue: false
Exit code 2 blocks the action with stderr feedback. JSON
{"continue": false, "stopReason": "..."}
also stops the teammate entirely, matching
Stop
hook behavior
PreToolUse
hookSpecificOutput
permissionDecision
(allow/deny/ask/defer),
permissionDecisionReason
PermissionRequest
hookSpecificOutput
decision.behavior
(allow/deny)
PermissionDenied
hookSpecificOutput
retry: true
tells the model it may retry the denied tool call
WorktreeCreate
path return
Command hook prints path on stdout; HTTP hook returns
hookSpecificOutput.worktreePath
. Hook failure or missing path fails creation
Elicitation
hookSpecificOutput
action
(accept/decline/cancel),
content
(form field values for accept)
ElicitationResult
hookSpecificOutput
action
(accept/decline/cancel),
content
(form field values override)
MessageDisplay
hookSpecificOutput
displayContent
replaces the displayed text on screen. Display-only: the transcript and what Claude sees keep the original
SessionStart, Setup, SubagentStart
Context only
hookSpecificOutput.additionalContext
adds context for Claude. SessionStart also accepts
initialUserMessage
,
watchPaths
,
sessionTitle
, and
reloadSkills
. No blocking or decision control
WorktreeRemove, Notification, SessionEnd, PostCompact, InstructionsLoaded, StopFailure, CwdChanged, FileChanged
None
No decision control. Used for side effects like logging or cleanup
A few events can also rewrite content rather than only allow or block it:
PreToolUse
:
updatedInput
directly under
hookSpecificOutput
replaces a tool’s arguments before it runs. See
PreToolUse decision control
PermissionRequest
:
updatedInput
inside the
decision
object. See
PermissionRequest decision control
PostToolUse
:
updatedToolOutput
replaces the tool’s result. See
PostToolUse decision control
UserPromptSubmit
: can’t replace the prompt; it only injects
additionalContext
alongside it
For redaction or transformation use cases, intercept at
PreToolUse
for outbound tool inputs and
PostToolUse
for inbound tool results.
Here are examples of each pattern in action:
Top-level decision
PreToolUse
PermissionRequest
Used by
UserPromptSubmit
,
UserPromptExpansion
,
PostToolUse
,
PostToolUseFailure
,
PostToolBatch
,
Stop
,
SubagentStop
,
ConfigChange
, and
PreCompact
. The only value is
"block"
. To allow the action to proceed, omit
decision
from your JSON, or exit 0 without any JSON at all:
{
"decision"
:
"block"
,
"reason"
:
"Test suite must pass before proceeding"
}
Uses
hookSpecificOutput
for richer control: allow, deny, or escalate to the user. You can also modify tool input before it runs or inject additional context for Claude. See
PreToolUse decision control
for the full set of options.
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
"Database writes are not allowed"
}
}
Uses
hookSpecificOutput
to allow or deny a permission request on behalf of the user. When allowing, you can also modify the tool’s input or apply permission rules so the user isn’t prompted again. See
PermissionRequest decision control
for the full set of options.
{
"hookSpecificOutput"
: {
"hookEventName"
:
"PermissionRequest"
,
"decision"
: {
"behavior"
:
"allow"
,
"updatedInput"
: {
"command"
:
"npm run lint"
}
}
}
}
For extended examples including Bash command validation, prompt filtering, and auto-approval scripts, see
What you can automate
in the guide and the
Bash command validator reference implementation
.
​
Hook events
Each event corresponds to a point in Claude Code’s lifecycle where hooks can run. The sections below are ordered to match the lifecycle: from session setup through the agentic loop to session end. Each section describes when the event fires, what matchers it supports, t

## Source (permissions): https://docs.claude.com/en/docs/claude-code/permissions

Configure permissions - Claude Code Docs
Documentation Index
Fetch the complete documentation index at:
/docs/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Claude Code supports fine-grained permissions so that you can specify exactly what the agent is allowed to do and what it can’t. Permission settings can be checked into version control and distributed to all developers in your organization, as well as customized by individual developers.
​
Permission system
Claude Code uses a tiered permission system to balance power and safety:
Tool type
Example
Approval required
”Yes, don’t ask again” behavior
Read-only
File reads, Grep
No
N/A
Bash commands
Shell execution
Yes
Permanently per project directory and command
File modification
Edit/write files
Yes
Until session end
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
removes the tool from Claude’s context entirely, so Claude never sees it. A scoped rule like
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
for when to use each one. Set the
defaultMode
in your
settings files
:
Mode
Description
default
Standard behavior: prompts for permission on first use of each tool.
Labeled Manual in the CLI and the VS Code and JetBrains extensions, and Claude Code accepts
manual
as an alias. The label and alias require Claude Code v2.1.200 or later
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
Plan Mode: Claude reads files and runs read-only shell commands to explore but doesn’t edit your source files
auto
Auto-approves tool calls with background safety checks that verify actions align with your request. Currently a research preview
dontAsk
Auto-denies tools unless pre-approved via
/permissions
or
permissions.allow
rules
bypassPermissions
Skips permission prompts, except those forced by explicit
ask
rules. Root and home directory removals such as
rm -rf /
also still prompt as a circuit breaker
bypassPermissions
mode skips permission prompts, including for writes to
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
. Explicit
ask
rules still force a prompt, and removals targeting the filesystem root or home directory, such as
rm -rf /
and
rm -rf ~
, still prompt as a circuit breaker against model error. Only use this mode in isolated environments like containers or VMs where Claude Code can’t cause damage.
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
Fields that a tool already matches with its own canonicalizing rules are not matchable this way:
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
. Wildcards can appear at any position in the command. This configuration allows npm and git commit commands while blocking git push:
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
The space before
*
matters:
Bash(ls *)
matches
ls -la
but not
lsof
, while
Bash(ls*)
matches both. The
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
matches every MCP tool across all servers. A tool matched by a bare-name glob deny rule is removed from Claude’s context, the same as a bare tool name. This configuration denies every MCP tool:
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
Process wrappers
Before matching Bash rules, Claude Code strips a fixed set of process wrappers so a rule like
Bash(npm test *)
also matches
timeout 30 npm test
. The recognized wrappers are
timeout
,
time
,
nice
,
nohup
, and
stdbuf
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
always prompt and can’t be auto-approved by a prefix rule like
Bash(watch *)
. The same applies to
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
run without a prompt. Commands with write-capable or exec-capable flags, such as
find
,
sort
,
sed
, and
git
, still prompt when an unquoted glob is present because the glob could expand to a flag like
-delete
.
A
cd
into a path inside your working directory or an
additional directory
is also read-only. A compound command like
cd packages/api && ls
runs without a prompt when each part qualifies on its own. Combining
cd
with
git
in one compound command always prompts, regardless of the target directory.
Bash permission patterns that try to constrain command arguments are fragile. For example,
Bash(curl http://github.com/ *)
intends to restrict curl to GitHub URLs, but won’t match variations like:
Options before URL:
curl -X GET http://github.com/...
Different protocol:
curl https://github.com/...
Redirects:
curl -L http://bit.ly/xyz
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
Read and Edit rules both follow the
gitignore
specification with four distinct pattern types:
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
pattern anchors at the directory associated with the settings file that defines it, so the same rule matches different locations depending on where you put it:
Rule defined in
/path
resolves to
Project or local settings, such as
.claude/settings.json
<project root>/path
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
: reads from
<current-directory>/src/
A rule only matches files under its anchor, so the anchor determines how far a deny rule reaches. Bare filenames follow gitignore semantics and match at any depth, so
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
In gitignore patterns,
*
matches within a single path segment and can appear at any position in the pattern, while
**
matches across directories. To allow all file access, use only the tool name without parentheses:
Read
,
Edit
, or
Write
.
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
provide a way to register custom shell commands to perform permission evaluation at runtime. When Claude Code makes a tool call, PreToolUse hooks run before the permission prompt. The hook output can deny the tool call, force a prompt, or skip the prompt to let the call proceed.
Hook decisions don’t bypass permission rules. Deny and ask rules are evaluated regardless of what a PreToolUse hook returns, so a matching deny rule blocks the call and a matching ask rule still prompts even when the hook returned
"allow"
or
"ask"
. This preserves the deny-first precedence described in
Manage permissions
, including deny rules set in managed settings.
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
Commands and output styles are discovered from the current working directory and its parents, your user directory at
~/.claude/
, and managed settings. Hooks and other
settings.json
keys load from the current working directory’s
.claude/
folder with no parent-directory fallback, alongside your user
~/.claude/settings.json
and managed settings. To share that configuration across projects, use one of these approaches:
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
control which tools Claude Code can use and which files or domains it can access. They apply to all tools, including Bash, Read, Edit, WebFetch, and MCP.
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
When sandboxing is enabled with
autoAllowBashIfSandboxed: true
, which is the default, sandboxed Bash commands run without prompting even if your permissions include a bare
Bash
ask rule, or the
equivalent
Bash(*)
form
: the sandbox boundary substitutes for that whole-tool prompt. These checks still apply:
Content-scoped ask rules like
Bash(git push *)
still force a prompt
Explicit deny rules still apply
rm
or
rmdir
commands that target
/
, your home directory, or other critical system paths still trigger a prompt
Commands that won’t run sandboxed, such as excluded commands, respect the bare
Bash
ask rule as usual. See
sandbox modes
to change this behavior.
​
Managed settings
For organizations that need centralized control over Claude Code configuration, administrators can deploy managed settings that can’t be overridden by user or project settings. These policy settings follow the same format as regular settings files and can be delivered through MDM/OS-level policies, managed settings files,
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
, claude.ai connectors load alongside a deployed
managed-mcp.json
instead of being suppressed by its exclusive control. See
Managed MCP configuration
allowedChannelPlugins
Allowlist of channel plugins that may push messages. Replaces the default Anthropic allowlist when set. Requires
channelsEnabled: true
. See
Restrict which channel plugins can run
allowManagedHooksOnly
When
true
, only managed hooks, SDK hooks, and hooks from plugins force-enabled in managed settings
enabledPlugins
are loaded. User, project, and all other plugin hooks are blocked
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
as all other Claude Code settings:
Managed settings
: can’t be overridden by any other level, including command line arguments
Command line arguments
: temporary session overrides
Local project settings
(
.claude/settings.local.json
)
Shared project settings
(
.claude/settings.json
)
User settings
(
~/.claude/settings.json
)
If a tool is denied at any level, no other level can allow it. For example, a managed settings deny can’t be overridden by
--allowedTools
, and
--disallowedTools
can add restrictions beyond what managed settings define.
The same holds across settings scopes: if user settings allow a permission and project settings deny it, the deny rule blocks it. The reverse is also true: a user-level deny blocks a project-level allow, because deny rules from any scope are evaluated before allow rules.
Embedding hosts can supply additional managed policy via the SDK
managedSettings
option when
parentSettingsBehavior
is set to
"merge"
; embedder values can tighten policy but not loosen it.
​
Project allow rules and workspace trust
permissions.allow
rules and
permissions.additionalDirectories
entries in a project’s
.claude/settings.json
grant capability, so Claude Code applies them only after you accept the
workspace trust dialog
for that workspace. Until then, Claude Code reads the rules but doesn’t apply them. The trust dialog lists the allow rules and additional directories the folder would grant so you can review them before accepting.
deny
and
ask
rules aren’t affected, since they only restrict.
Claude Code saves trust per workspace, keyed on the git repository root or, outside a repository, the directory you started Claude Code from. When you start in your home directory, trust is held for the current session only and isn’t written to disk; see the
additional safeguards
note. Trusting a parent directory doesn’t apply a nested project’s allow rules.
.claude/settings.local.json
is your own file, so the workspace trust check usually doesn’t apply to it. When a repository could have supplied the file, such as when it is committed to git or
.claude
is a symlink, its allow rules and additional directories go through the trust check like project settings.
Allow rules and additional directories in
.claude/settings.local.json
also apply without workspace trust in two cases:
The directory you started Claude Code from isn’t inside a git repository.
The session runs in your own configuration home: your home directory or any directory whose
.claude
subdirectory you’ve set as
CLAUDE_CONFIG_DIR
.
In both cases the file is one you created rather than one a repository could have supplied, and a repository-committed
.claude/settings.local.json
still requires workspace trust. Versions 2.1.196 through 2.1.199 treated the file as repository-supplied in those workspaces, ignored its allow rules, and printed a
this workspace has not been trusted
warning to stderr. The two exceptions above match v2.1.195 and earlier and were restored in v2.1.200.
Also as of v2.1.200, a workspace whose allow rules or additional directories still aren’t applied, but that never showed the trust dialog because a parent directory was already trusted, shows the dialog the next time you start Claude Code there interactively. The dialog offers two choices:
Yes, I trust this folder
: saves trust for that workspace and applies the rules in the same session.
No, continue without these permissions
: keeps working with those rules ignored. The dialog appears again in the next session.
In
non-interactive mode
with
-p
, no dialog appears and the rules stay ignored.
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
Settings
Sandbox environments
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
Agent teams are experimental and disabled by default. Enable them by adding
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
to your
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
let you parallelize work, but they operate differently. Choose based on whether your workers need to communicate with each other:
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
Shared task list with self-coordination
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
​
Start your first agent team
After enabling agent teams, describe the task and the teammates you want in natural language. Claude spawns them and coordinates work based on your prompt.
This example works well because the three roles are independent and can explore the problem without waiting on each other:
I'm designing a CLI tool that helps developers track TODO comments across
their codebase. Spawn three teammates to explore this from different angles:
one on UX, one on technical architecture, one playing devil's advocate.
From there, Claude populates a
shared task list
, spawns teammates for each perspective, has them explore the problem, and synthesizes findings when finished.
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
only change the lead’s settings.
As of v2.1.199, typing either command while viewing a teammate shows a notice that the change applies to the lead; earlier versions applied it to the lead with no indication.
/effort
still applies to the viewed teammate’s later turns, because teammates follow the lead’s
effort level
.
​
Assign and claim tasks
The shared task list coordinates work across the team. The lead creates tasks and teammates work through them. Tasks have three states: pending, in progress, and completed. Tasks can also depend on other tasks: a pending task with unresolved dependencies cannot be claimed until those dependencies are completed.
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
An agent team forms when the first teammate is spawned, with the main session acting as the lead. There are two ways teammates get spawned:
You request teammates
: give Claude a task that benefits from parallel work and explicitly ask for teammates. Claude spawns them based on your instructions.
Claude proposes teammates
: if Claude determines your task would benefit from parallel work, it may suggest spawning teammates. You confirm before it proceeds.
In both cases, you stay in control. Claude won’t spawn teammates without your approval.
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
See
Choose a display mode
for display configuration options. Teammate messages arrive at the lead automatically.
The system manages task dependencies automatically. When a teammate completes a task that other tasks depend on, blocked tasks unblock without manual intervention.
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
you already control for session transcripts.
The team config holds runtime state such as session IDs and tmux pane IDs, so don’t edit it by hand or pre-author it: your changes are overwritten on the next state update.
To define reusable teammate roles, use
subagent definitions
instead.
The team config contains a
members
array with each teammate’s name, agent ID, and agent type. Teammates can read this file to discover other team members.
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
, and the definition’s body is appended to the teammate’s system prompt as additional instructions rather than replacing it. Team coordination tools such as
SendMessage
and the task management tools are always available to a teammate even when
tools
restricts other tools.
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
When one agent sends another a message over
SendMessage
, the receiving agent is told it came from another Claude session, not from you. A teammate cannot approve a permission prompt or supply consent on your behalf, and a teammate that was denied an action cannot relay it to another teammate to bypass the check. In
auto mode
, the classifier treats an approval claim relayed from another agent as untrusted input rather than confirmation from you. Teammate permission prompts bubble up to the lead session, so approve them there yourself.
​
Context and communication
Each teammate has its own context window. When spawned, a teammate loads the same project context as a regular session: CLAUDE.md, MCP servers, and skills. It also receives the spawn prompt from the lead. The lead’s conversation history does not carry over.
How teammates share information:
Automatic message delivery
: when teammates send messages, they’re delivered automatically to recipients. The lead doesn’t need to poll for updates.
Idle notifications
: when a teammate finishes and stops, it automatically notifies the lead.
As of v2.1.198, a teammate whose turn ends on an API error notifies the lead that it failed and includes the error text, instead of appearing to finish normally.
Shared task list
: all agents can see task status and claim available work.
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
Start with 3-5 teammates for most workflows. This balances parallel work with manageable coordination. The examples in this guide use 3-5 teammates because that range works well across different task types.
Having 5-6
tasks
per teammate keeps everyone productive without excessive context switching. If you have 15 independent tasks, 3 teammates is a good starting point.
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
Too many permission prompts
Teammate permission requests bubble up to the lead, which can create friction. Pre-approve common operations in your
permission settings
before spawning teammates to reduce interruptions.
​
Teammates stopping on errors
Teammates may stop after encountering errors instead of recovering. Check their output by selecting the teammate in the agent panel and pressing Enter in in-process mode, or by clicking the pane in split mode, then either:
Give them additional instructions directly
Spawn a replacement teammate to continue the work
As of v2.1.198, a message from the lead or another teammate wakes an in-process teammate that is waiting to retry a failed API request, so it retries immediately instead of waiting for the full retry delay.
​
Lead shuts down before work is done
The lead may decide the team is finished before all tasks are actually complete. If this happens, tell it to keep going. You can also tell the lead to wait for teammates to finish before proceeding if it starts doing work instead of delegating.
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
CLAUDE.md
works normally
: teammates read
CLAUDE.md
files from their working directory. Use this to provide project-specific guidance to all teammates.
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
Agent view
Dynamic workflows
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
to see every command available to you, or type
/
followed by letters to filter.
A command is only recognized at the start of your message. Text that follows the command name becomes its arguments.
As of v2.1.199,
skills
are the exception: a skill invocation followed by more skills, such as
/skill-a /skill-b do XYZ
, loads every skill named at the start and passes the trailing text to each as arguments. Up to six skills can be chained.
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
for a quick aside that shouldn’t add to the conversation history.
Run work in parallel.
Claude delegates side tasks to
subagents
, and
/tasks
lists what’s running in the background of the current session.
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
shows what changed,
/code-review
checks the diff for correctness bugs and cleanups and can apply the findings with
--fix
,
/review
runs the same read-only review on a GitHub pull request, and
/security-review
gives a deeper read-only pass.
/code-review ultra
runs a multi-agent review in the cloud.
Between sessions.
/clear
starts fresh on a new task while keeping project memory.
/resume
and
/branch
let you return to or fork an earlier conversation.
/teleport
pulls a web session into this terminal, and
/remote-control
lets you continue this local session from another device.
When something is wrong.
/rewind
rolls code and conversation back to a checkpoint, or summarizes part of the conversation.
/doctor
and
/debug
diagnose install and runtime issues, and
/feedback
reports a bug with session context attached.
​
All commands
The table below lists all the commands included in Claude Code. Most are built-in commands whose behavior is coded into the CLI. Two kinds of entries are marked:
Skill
: a bundled skill. It works like skills you write yourself: a prompt handed to Claude, which Claude can also invoke automatically when relevant.
Workflow
: a bundled
dynamic workflow
that fans work out across many subagents and runs in the background.
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
only shows on macOS and Windows when signed in with a Claude subscription, and
/upgrade
only shows on Pro and Max plans.
Command
Purpose
/add-dir <path>
Add a working directory for file access during the current session. Most
.claude/
configuration is
not discovered
from the added directory. You can later resume the session from the added directory with
--continue
or
--resume
/advisor [model|off]
Enable or disable the
advisor tool
, which consults a second model for guidance at key moments during a task. Accepts
opus
,
sonnet
,
fable
(
v2.1.170+), or a full model ID. Without an argument, opens a picker. Requires Claude Code v2.1.98 or later
/agents
As of v2.1.198, running
/agents
prints a reminder to ask Claude to create or manage
subagents
, or to edit
.claude/agents/
or
~/.claude/agents/
directly.
On v2.1.197 and earlier, opens an interactive interface for creating and managing subagent configurations
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
. To hand a side task to a background subagent instead of switching into a copy yourself, use
/fork
/btw <question>
Ask a quick
side question
without adding to the conversation
/cd <path>
Move this session to a new working directory. The conversation’s prompt cache is preserved: the new directory’s
CLAUDE.md
is appended as a message instead of rebuilding the system prompt. The session is relocated to the new directory’s project storage, so
--resume
and
--continue
find it from there. Prompts you to trust the directory if you haven’t worked in it before. To grant access to an extra directory without moving the session, use
/add-dir
. Restrict or disable
/cd
targets with
Cd
permission rules
. Requires Claude Code v2.1.169 or later; earlier versions report
Unknown command: /cd
/chrome
Configure
Claude in Chrome
settings
/claude-api [migrate|managed-agents-onboard]
Skill
.
Load Claude API reference material for your project’s language (Python, TypeScript, Java, Go, Ruby, C#, PHP, or cURL) and Managed Agents reference. Covers tool use, streaming, batches, structured outputs, and common pitfalls. Also activates automatically when your code imports
anthropic
or
@anthropic-ai/sdk
. Run
/claude-api migrate
to upgrade existing Claude API code to a newer model: Claude asks which files to scan and which model to target, then updates model IDs, thinking configuration, and other parameters that changed between versions. Run
/claude-api managed-agents-onboard
for an interactive walkthrough that creates a new Managed Agent from scratch
/clear [name]
Start a new conversation with empty context. The previous conversation stays available in
/resume
. Pass a name to label the previous conversation in the
/resume
picker. To free up context while continuing the same conversation, use
/compact
instead. Aliases:
/reset
,
/new
/code-review [low|medium|high|xhigh|max|ultra] [--fix] [--comment] [target]
Skill
.
Review the current diff for correctness bugs and for reuse, simplification, and efficiency cleanups. Pass
--fix
to apply findings to your working tree,
--comment
to post them as inline GitHub PR comments, or
ultra
to run a deep
cloud review
.
From v2.1.154,
/simplify
runs a separate cleanup-only review that applies fixes without hunting for bugs. See
Review a diff locally
for effort levels and targeting
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
is connected, the color syncs to claude.ai/code
/compact [instructions]
Free up context by summarizing the conversation so far. Optionally pass focus instructions for the summary. See
how compaction handles rules, skills, and memory files
/config [key=value ...]
Open the
Settings
interface to adjust theme, model,
output style
, and other preferences.
From v2.1.181, pass one or more
key=value
pairs to set a setting directly without opening the interface, for example
/config thinking=false
.
From v2.1.182, named shorthand keys are also accepted, such as
/config theme=dark
or
/config model=sonnet
. The
key=value
form also works in non-interactive mode (
-p
) and from
Remote Control
. Run
/config --help
to list every settable key with its options. Alias:
/settings
/context [all]
Visualize current context usage as a colored grid. Shows optimization suggestions for context-heavy tools, memory bloat, and capacity warnings. In
fullscreen mode
the per-item breakdown is collapsed to keep the grid visible. Pass
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
Design guidance for charts, graphs, and dashboards. Claude picks the chart form for the data, assigns color by role, validates the palette for colorblind safety and contrast with a bundled script, and applies mark, interaction, and accessibility rules. Uses a brand-neutral placeholder palette that you replace with your own.
Requires Claude Code v2.1.198 or later
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
. A first-time sync verifies every component and can take a few hours on a large repo. Available on the Anthropic API; on Amazon Bedrock, Google Cloud’s Agent Platform, and Microsoft Foundry the underlying tool can’t reach claude.ai, so the command is unavailable
/desktop
Continue the current session in the Claude Code Desktop app. Requires macOS or Windows and a Claude subscription. Alias:
/app
/diff
Open an interactive diff viewer showing uncommitted changes and per-turn diffs. Use left/right arrows to switch between the current git diff and individual Claude turns, and up/down to browse files.
As of v2.1.198, the open viewer also refreshes automatically when the repository’s git state changes outside the session, such as a branch switch or commit in another terminal
/doctor
Diagnose and verify your Claude Code installation and settings. Results show with status icons. Press
f
to have Claude fix any reported issues
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
ultracode
is a Claude Code setting that combines
xhigh
reasoning with automatic
workflow
orchestration.
auto
resets to the model default. Without an argument, opens an interactive slider; use left and right arrows to pick a level and
Enter
to apply. Takes effect immediately without waiting for the current response to finish
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
on or off
/feedback [report]
Submit feedback, report a bug, or share your conversation. Aliases:
/bug
,
/share
/fewer-permission-prompts
Skill
.
Scan your transcripts for common read-only Bash and MCP tool calls, then add a prioritized allowlist to project
.claude/settings.json
to reduce permission prompts
/focus
Toggle the focus view, which shows only your last prompt, a one-line tool-call summary with edit diffstats, and the final response.
As of v2.1.198, the tool-call summary also counts the subagents launched in the turn and collapses completed background-task notifications into a single count. The selection persists across sessions; set
viewMode
in settings to override it. Only available in
fullscreen rendering
/fork <directive>
Spawn a
forked subagent
: a background subagent that inherits the full conversation and works on the directive while you keep going. Its result returns to your conversation when it finishes. To switch into a copy of the conversation yourself, use
/branch
. Before v2.1.161,
/fork
is an alias for
/branch
/goal [condition|clear]
Set a
goal
: Claude keeps working across turns until the condition is met. With no argument, shows the current or most recently achieved goal.
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
, or your home directory on Linux without a Desktop folder, for diagnosing high memory usage. See
troubleshooting
/help
Show help and available commands
/hooks
View
hook
configurations for tool events
/ide
Manage IDE integrations and show status
/init
Initialize project with a
CLAUDE.md
guide. Set
CLAUDE_CODE_NEW_INIT=1
for an interactive flow that also walks through skills, hooks, and personal memory files
/insights
Generate a report analyzing your Claude Code sessions, including project areas, interaction patterns, and friction points
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
/login
Sign in to your Anthropic account
/logout
Sign out from your Anthropic account
/loop [interval] [prompt]
Skill
.
Run a prompt repeatedly while the session stays open. Omit the interval and Claude self-paces between iterations. Omit the prompt and,
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
to change connection state without opening the dialog
/memory
Edit
CLAUDE.md
memory files, enable or disable
auto-memory
, and view auto-memory entries
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
on a row to switch for the current session only. The picker asks for confirmation when the conversation has prior output, since the next response re-reads the full history without cached context. Once confirmed, the change applies without waiting for the current response to finish
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
to act directly
/powerup
Discover Claude Code features through quick interactive lessons with animated demos
/pr-comments [PR]
Removed in v2.1.91. Ask Claude directly to view pull request comments instead. On earlier versions, fetches and displays comments from a GitHub pull request; automatically detects the PR for the current branch, or pass a PR URL or number. Requires the
gh
CLI
/privacy-settings
View and update your privacy settings. Only available for Pro and Max plan subscribers
/radio
Open Claude FM lo-fi radio in your browser. Prints the stream URL when no browser is available. Not available on Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry
/recap
Generate a one-line summary of the current session on demand. See
Session recap
for the automatic recap that appears after you’ve been away
/release-notes
View the changelog in an interactive version picker. Select a specific version to see its release notes, or choose to show all versions
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
remote control
from claude.ai. Alias:
/rc
/remote-env
Choose the default environment for
cloud agents
/rename [name]
Rename the current session and show the name on the prompt bar. Without a name, auto-generates one from conversation history
/resume [session]
Resume a conversation by ID or name, or open the session picker. As of v2.1.144,
background sessions
appear in the picker marked with
bg
. Alias:
/continue
/review [PR]
Review a GitHub pull request by number, using the same review engine as
/code-review
. With no arguments, lists open PRs to pick from. For a cloud-based review, see
/code-review ultra
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
.
Requires Claude Code v2.1.145 or later
/run-skill-generator
Skill
.
Teach
/run
and
/verify
how to build, launch, and drive your project’s app from a clean environment by writing a per-project
skill
.
Requires Claude Code v2.1.145 or later
/sandbox
Toggle
sandbox mode
. Available on supported platforms only
/schedule [description]
Create, update, list, or run
routines
, which execute on Anthropic-managed cloud infrastructure. Claude walks you through the setup conversationally. Alias:
/routines
/scroll-speed
Adjust mouse wheel
scroll speed
interactively, with a ruler you can scroll while the dialog is open to preview the change. Available in
fullscreen rendering
only and not in the JetBrains IDE terminal
/security-review
Analyze pending changes on the current branch for security vulnerabilities. Reviews the git diff and identifies risks like injection, auth issues, and data exposure
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
.
As of v2.1.121, type to filter the list by name. Press
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
Open the Settings interface on the Status tab, showing version, model, account, and connectivity. Works while Claude is responding
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
/tasks
View and manage everything running in the background. Also available as
/bashes
/team-onboarding
Generate a team onboarding guide from your Claude Code usage history. Claude analyzes your sessions, commands, and MCP server usage from the past 30 days and produces a markdown guide a teammate can paste as a first message to get set up quickly. For claude.ai subscribers on Pro, Max, Team, and Enterprise plans, also returns a share link teammates can open directly in Claude Code
/teleport
Pull a
Claude Code on the web
session into this terminal: opens a picker, then fetches the branch and conversation. Also available as
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
Draft a plan in an
ultraplan
session, review it in your browser, then execute remotely or send it back to your terminal
/ultrareview [PR]
Run a deep, multi-agent code review in a cloud sandbox with
ultrareview
. The preferred invocation is now
/code-review ultra
, and
/ultrareview
remains as an alias. Includes 3 free runs on Pro and Max, then requires
usage credits
/upgrade
Open the upgrade page to switch to a higher plan tier
/usage
Show session cost, plan usage limits, and activity stats. On a Pro, Max, Team, or Enterprise plan, includes a breakdown of usage by skill, subagent, plugin, and MCP server. See the
cost tracking guide
for details.
/cost
and
/stats
are aliases
/usage-credits
Configure usage credits to keep working when you hit a limit. Previously
/extra-usage
/verify
Skill
.
Confirm a code change does what it should by building your project’s app, running it, and observing the result, rather than relying on tests or type checks. See
Run and verify your app
.
Requires Claude Code v2.1.145 or later
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
CLI reference
Environment variables
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
Use standalone configuration when
:
You’re customizing Claude Code for a single project
The configuration is personal and doesn’t need to be shared
You’re experimenting with skills or hooks before packaging them
You want short skill names like
/hello
or
/deploy
Use plugins when
:
You want to share functionality with your team or community
You need the same skills/agents across multiple projects
You want version control and easy updates for your extensions
You’re distributing through a marketplace
You’re okay with namespaced skills like
/my-plugin:hello
(namespacing prevents conflicts between plugins)
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
If you don’t see the
/plugin
command, update Claude Code to the latest version. See
Troubleshooting
for upgrade instructions.
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
Optional. If set, users only receive updates when you bump this field. If omitted and your plugin is distributed via git, the commit SHA is used and every commit counts as a new version. See
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
to see your skill listed under the plugin namespace.
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
to pick up the changes, then try the skill with your name:
/my-first-plugin:hello
Alex
Claude will greet you by name. For more on passing arguments to skills, see
Skills
.
You’ve successfully created and tested a plugin with these key components:
Plugin manifest
(
.claude-plugin/plugin.json
): describes your plugin’s metadata
Skills directory
(
skills/
): contains your custom skills
Skill arguments
(
$ARGUMENTS
): captures user input for dynamic behavior
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
Next steps
: Ready to add more features? Jump to
Develop more complex plugins
to add agents, hooks, MCP servers, and LSP servers. For complete technical specifications of all plugin components, see
Plugins reference
.
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
After installing the plugin, run
/reload-plugins
to load the Skills. For complete Skill authoring guidance including progressive disclosure and tool restrictions, see
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
archive of the plugin directory, which requires Claude Code v2.1.128 or later.
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
Verify hooks work as expected
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
instead. Claude Code fetches the archive at startup and loads it for that session only. If the fetch fails or the archive is invalid, Claude Code reports a plugin load error and starts without it. The same
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
or rely on the git commit SHA. See
version management
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
: a curated set of plugins maintained by Anthropic. Registered automatically the first time you start Claude Code interactively. A non-interactive script that runs before that first launch must add it explicitly with
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
claude plugin validate
locally before you submit. The review pipeline runs the same check on every submission, along with automated safety screening.
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
For complete technical specifications, debugging techniques, and distribution strategies, see
Plugins reference
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
Copy your existing configurations to the plugin directory:
# Copy commands
cp
-r
.claude/commands
my-plugin/
# Copy agents (if any)
cp
-r
.claude/agents
my-plugin/
# Copy skills (if any)
cp
-r
.claude/skills
my-plugin/
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
, and verify hooks trigger correctly.
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
definitions override same-named plugin agents, so the plugin version only takes effect once the originals are removed.
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
Discover and install prebuilt plugins
Share session output as artifacts
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
This reference provides complete technical specifications for the Claude Code plugin system, including component schemas, CLI commands, and development tools.
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
Integration behavior
:
Skills and commands are automatically discovered when the plugin is installed
Claude can invoke them automatically based on task context
Skills can include supporting files alongside SKILL.md
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
Integration points
:
Agents appear in the
@-mention typeahead
under their scoped name, such as
my-plugin:code-reviewer
, once the plugin is enabled
Claude can invoke agents automatically based on task context
Agents can be invoked manually by users
Plugin agents work alongside built-in Claude agents
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
When a permission dialog appears
PermissionDenied
When a tool call is denied by the auto mode classifier. Return
{retry: true}
to tell the model it may retry the denied tool call
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
When the turn ends due to an API error. Output and exit code are ignored
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
FileChanged
When a watched file changes on disk. The
matcher
field specifies which filenames to watch
WorktreeCreate
When a worktree is being created via
--worktree
or
isolation: "worktree"
. Replaces default git behavior
WorktreeRemove
When a worktree is being removed, either at session exit or when a subagent finishes
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
],
"cwd"
:
"${CLAUDE_PLUGIN_ROOT}"
}
}
}
Integration behavior
:
Plugin MCP servers start automatically when the plugin is enabled
Servers appear as standard MCP tools in Claude’s toolkit
Server capabilities integrate seamlessly with Claude’s existing tools
Plugin servers can be configured independently of user MCP servers
​
LSP servers
Looking to use LSP plugins? Install them from the official marketplace: search for “lsp” in the
/plugin
Discover tab. This section documents how to create LSP plugins for languages not covered by the official marketplace.
Plugins can provide
Language Server Protocol
(LSP) servers to give Claude real-time code intelligence while working on your codebase.
LSP integration provides:
Instant diagnostics
: Claude sees errors and warnings immediately after each edit
Code navigation
: go to definition, find references, and hover information
Language awareness
: type information and documentation for code symbols
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
maxRestarts
Maximum number of restart attempts before giving up
diagnostics
Whether to push diagnostics into Claude’s context after edits (default
true
). Set to
false
to keep code navigation but suppress automatic diagnostic injection.
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
Plugin monitors require Claude Code v2.1.105 or later.
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
/scripts/poll-deploy.sh ${user_config.api_endpoint}"
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
value supports the same
variable substitutions
as MCP and LSP server configs:
${CLAUDE_PLUGIN_ROOT}
,
${CLAUDE_PLUGIN_DATA}
,
${CLAUDE_PROJECT_DIR}
,
${user_config.*}
, and any
${ENV_VAR}
from the environment. Prefix the command with
cd "${CLAUDE_PLUGIN_ROOT}" &&
if the script needs to run from the plugin’s own directory.
Disabling a plugin mid-session does not stop monitors that are already running. They stop when the session ends.
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
Selecting a plugin theme persists
custom:<plugin-name>:<slug>
in the user’s config. Plugin themes are read-only; pressing
Ctrl+E
on one in
/theme
copies it into
~/.claude/themes/
so the user can edit the copy.
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
Project-specific plugins, gitignored
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
. Unlike a marketplace install, the plugin is discovered in place rather than copied into the plugin cache.
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
A project-scope plugin is checked into the repository and reaches every collaborator who clones it. Because that content comes from the repository rather than from you, it loads only after the same trust gate that governs
.claude/settings.json
, and components that run code are restricted further:
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
of the directory where you start Claude Code. They do not
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
file defines your plugin’s metadata and configuration. This section documents all supported fields and options.
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
Fields with the wrong type still fail. For example, a
keywords
value that is
a string instead of an array is a load error, and
claude plugin validate
reports it as one.
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
Optional. Semantic version. Setting this pins the plugin to that version string, so users only receive updates when you bump it. If omitted, Claude Code falls back to the git commit SHA, so every commit is treated as a new version. If also set in the marketplace entry,
plugin.json
wins. See
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
in MCP and LSP server configs, hook commands, and monitor commands. Non-sensitive values can also be substituted in skill and agent content. All values are exported to plugin subprocesses as
CLAUDE_PLUGIN_OPTION_<KEY>
environment variables.
Non-sensitive values are stored in
settings.json
under
pluginConfigs[<plugin-id>].options
. Sensitive values go to the system keychain (or
~/.claude/.credentials.json
where the keychain is unavailable). Keychain storage is shared with OAuth tokens and has an approximately 2 KB total limit, so keep sensitive values small.
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
When a plugin has both a default folder and the matching manifest key, Claude Code v2.1.140 and later flags the ignored folder in
/doctor
,
claude plugin list
, and the
/plugin
detail view. The plugin still loads using the manifest paths. No warning is shown when the manifest key points into the default folder, for example
"commands": ["./commands/deploy.md"]
, because the folder is addressed explicitly in that case.
For all path fields:
All paths must be relative to the plugin root and start with
./
Components from custom paths use the same naming and namespacing rules
Multiple paths can be specified as arrays
When a skill path points to a directory that contains a
SKILL.md
directly, for example
"skills": ["./"]
pointing to the plugin root, the frontmatter
name
field in
SKILL.md
determines the skill’s invocation name. This gives a stable name regardless of the install directory. If
name
is not set in the frontmatter, the directory basename is used as a fallback.
A plugin that has a
SKILL.md
at its root, no
skills/
subdirectory, and no
skills
manifest field is automatically loaded as a single-skill plugin in Claude Code v2.1.142 and later. You do not need to set
"skills": ["./"]
in
plugin.json
for this layout. The skill’s invocation name follows the same rule as above: the frontmatter
name
field, or the directory basename as a fallback.
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
Claude Code provides three variables for referencing paths. All are substituted inline anywhere they appear in skill content, agent content, hook commands, monitor commands, and MCP or LSP server configs. All are also exported as environment variables to hook processes and MCP or LSP server subprocesses.
${CLAUDE_PLUGIN_ROOT}
: the absolute path to your plugin’s installation directory. Use this to reference scripts, binaries, and config files bundled with the plugin. In hook commands, use
exec form
with
args
so the path is passed as one argument with no quoting. In shell-form hooks and monitor commands, wrap it in double quotes, as in
"${CLAUDE_PLUGIN_ROOT}"
. This path changes when the plugin updates. The previous version’s directory remains on disk for about seven days after an update before cleanup, but treat it as ephemeral and do not write state here.
When a plugin updates mid-session, hook commands, monitors, MCP servers, and LSP servers keep using the previous version’s path. Run
/reload-plugins
to switch hooks, MCP servers, and LSP servers to the new path; monitors require a session restart.
${CLAUDE_PLUGIN_DATA}
: a persistent directory for plugin state that survives updates. Use this for installed dependencies such as
node_modules
or Python virtual environments, generated code, caches, and any other files that should persist across plugin versions. The directory is created automatically the first time this variable is referenced.
${CLAUDE_PROJECT_DIR}
: the project root. This is the same directory hooks receive in their
CLAUDE_PROJECT_DIR
variable. Use this to reference project-local scripts or config files. Wrap in quotes to handle paths with spaces, for example
"${CLAUDE_PROJECT_DIR}/scripts/server.sh"
. MCP servers can also call the MCP
roots/list
request, which returns the directory Claude Code was launched from.
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
A common use is installing language dependencies once and reusing them across sessions and plugin updates. Because the data directory outlives any single plugin version, a check for directory existence alone cannot detect when an update changes the plugin’s dependency manifest. The recommended pattern compares the bundled manifest against a copy in the data directory and reinstalls when they differ.
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
) rather than using them in-place. Understanding this behavior is important when developing plugins that reference external files.
Each installed version is a separate directory in the cache. When you update or uninstall a plugin, the previous version directory is marked as orphaned and removed automatically 7 days later. The grace period lets concurrent Claude Code sessions that already loaded the old version keep running without errors.
Claude’s Glob and Grep tools skip orphaned version directories during searches, so file results don’t include outdated plugin code.
​
Path traversal limitations
Installed plugins cannot reference files outside their directory. Paths that traverse outside the plugin root (such as
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
or from a local path, only symlinks that resolve within the plugin’s own directory are preserved. All others are skipped.
The following command creates a link from inside a marketplace plugin to a shared skill defined by a sibling plugin. On Windows, use
mklink /D
from an elevated Command Prompt or enable Developer Mode:
ln
-s
../../shared-plugin/skills/foo
./skills/foo
This provides flexibility while maintaining the security benefits of the caching system.
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
file. All other directories (commands/, agents/, skills/, output-styles/, themes/, monitors/, hooks/) must be at the plugin root, not inside
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
keys are currently supported
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
# Install to local scope (gitignored)
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
Also remove auto-installed dependencies that no other plugin requires. See
plugin prune
-y, --yes
Skip the
--prune
confirmation prompt. Required when stdin or stdout is not a TTY
-h, --help
Display help for command
Aliases:
remove
,
rm
By default, uninstalling from the last remaining scope also deletes the plugin’s
${CLAUDE_PLUGIN_DATA}
directory. Use
--keep-data
to preserve it, for example when reinstalling after testing a new version.
​
plugin prune
Remove auto-installed plugin dependencies that are no longer required by any installed plugin. Dependencies that Claude Code pulled in to satisfy another plugin’s
dependencies
field are removed; plugins you installed directly are never touched.
claude
plugin
prune
[options]
Options:
Option
Description
Default
-s, --scope <scope>
Prune at scope:
user
,
project
, or
local
user
--dry-run
List what would be removed without removing anything
-y, --yes
Skip the confirmation prompt. Required when stdin or stdout is not a TTY
-h, --help
Display help for command
Aliases:
autoremove
The command lists orphaned dependencies and asks for confirmation before removing them. To remove a plugin and clean up its dependencies in one step, run
claude plugin uninstall <plugin> --prune
.
claude plugin prune
requires Claude Code v2.1.121 or later.
​
plugin enable
Enable a disabled plugin. If the plugin declares
dependencies
, Claude Code enables them transitively at the same scope, and the command fails when a dependency is not installed.
claude
plugin
enable
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
Scope to enable:
user
,
project
, or
local
user
-h, --help
Display help for command
​
plugin disable
Disable a plugin without uninstalling it. Fails when another enabled plugin
depends on
the target. The error message includes a chained command that disables every dependent first.
claude
plugin
disable
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
Scope to disable:
user
,
project
, or
local
user
-h, --help
Display help for command
​
plugin update
Update a plugin to the latest version.
claude
plugin
update
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
Scope to update:
user
,
project
,
local
, or
managed
user
-h, --help
Display help for command
​
plugin list
List installed plugins with their version, source marketplace, and enable status.
claude
plugin
list
[options]
Options:
Option
Description
Default
--json
Output as JSON
--available
Include available plugins from marketplaces. Requires
--json
-h, --help
Display help for command
Within an interactive session,
/plugin list
prints the same listing inline. The interactive form accepts
--enabled
or
--disabled
to show only plugins in that state, and
ls
as a shorthand for
list
.
​
plugin details
Show a plugin’s component inventory and projected token cost. The output lists all components the plugin contributes, grouped as Skills, Agents, Hooks, MCP servers, and LSP servers, along with an estimate of how many tokens it adds to each session. The Skills group includes both
skills/
and
commands/
entries.
claude
plugin
details
<
nam
e
>
Arguments:
<name>
: Plugin name or
plugin-name@marketplace-name
Options:
Option
Description
Default
-h, --help
Display help for command
The output shows two cost figures for each component:
Always-on:
tokens added to every session by the plugin’s listing text, such as skill descriptions, agent descriptions, and command names, regardless of whether any component fires.
On-invoke:
tokens a component costs when it fires. Shown per component, not as a plugin total, because a typical session invokes only a subset of components.
This example shows what the output looks like for a plugin with two skills:
dependency-guard 1.2.0
Dependency analysis for Claude Code sessions
Source: dependency-guard@example-marketplace
Component inventory
Skills (2)  scan-dependencies, review-changes
Agents (0)
Hooks (1)  (harness-only — no model context cost)
MCP servers (0)
LSP servers (0)
Projected token cost
Always-on:   ~180 tok   added to every session
Per-component (rounded)
component            always-on  on-invoke
scan-dependencies        ~100      ~2400
review-changes            ~80      ~1800
On-invoke cost is paid each time a skill or agent fires.
Token counts are estimates and may differ from actual usage.
The always-on total is computed via the
count_tokens
API for your active model. Per-component numbers are proportionally scaled from that total. If the API is unreachable, the command falls back to a character-based estimate.
​
plugin tag
Create a release git tag for the plugin in the current directory. Run from inside the plugin’s folder. See
Tag plugin releases
.
claude
plugin
tag
[options]
Options:
Option
Description
Default
--push
Push the tag to the remote after creating it
--dry-run
Print what would be tagged without creating the tag
-f, --force
Create the tag even if the working tree is dirty or the tag already exists
-h, --help
Display help for command
​
Debugging and development tools
​
Debugging commands
Use
claude --debug
to see plugin loading details:
This shows:
Which plugins are being loaded
Any errors in plugin manifests
Skill, agent, and hook registration
MCP server initialization
​
Common issues
Issue
Cause
Solution
Plugin not loading
Invalid
plugin.json
Run
claude plugin validate
or
/plugin validate
to check
plugin.json
, skill/agent/command frontmatter, and
hooks/hooks.json
for syntax and schema errors
Skills not appearing
Wrong directory structure
Ensure
skills/
or
commands/
is at the plugin root, not inside
.claude-plugin/
Hooks not firing
Script not executable
Run
chmod +x script.sh
MCP server fails
Missing
${CLAUDE_PLUGIN_ROOT}
Use variable for all plugin paths
Path errors
Absolute paths used
All paths must be relative and start with
./
LSP
Executable not found in $PATH
Language server not installed
Install the binary (e.g.,
npm install -g typescript-language-server typescript
)
​
Example error messages
Manifest validation errors
:
Invalid JSON syntax: Unexpected token } in JSON at position 142
: check for missing commas, extra commas, or unquoted strings
Plugin has an invalid manifest file at .claude-plugin/plugin.json. Validation errors: name: Required
: a required field is missing
Plugin has a corrupt manifest file at .claude-plugin/plugin.json. JSON parse error: ...
: JSON syntax error
Plugin loading errors
:
Warning: No commands found in plugin my-plugin custom directory: ./cmds. Expected .md files or SKILL.md in subdirectories.
: command path exists but contains no valid command files
Plugin directory not found at path: ./plugins/my-plugin. Check that the marketplace entry has the correct path.
: the
source
path in marketplace.json points to a non-existent directory
Plugin my-plugin has conflicting manifests: both plugin.json and marketplace entry specify components.
: remove duplicate component definitions or remove
strict: false
in marketplace entry
​
Hook troubleshooting
Hook script not executing
:
Check the script is executable:
chmod +x ./scripts/your-script.sh
Verify the shebang line: First line should be
#!/bin/bash
or
#!/usr/bin/env bash
Check the path uses
${CLAUDE_PLUGIN_ROOT}
:
"command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/your-script.sh"
Test the script manually:
./scripts/your-script.sh
Hook not triggering on expected events
:
Verify the event name is correct (case-sensitive):
PostToolUse
, not
postToolUse
Check the matcher pattern matches your tools:
"matcher": "Write|Edit"
for file operations
Confirm the hook type is valid:
command
,
http
,
mcp_tool
,
prompt
, or
agent
​
MCP server troubleshooting
Server not starting
:
Check the command exists and is executable
Verify all paths use
${CLAUDE_PLUGIN_ROOT}
variable
Check the MCP server logs:
claude --debug
shows initialization errors
Test the server manually outside of Claude Code
Server tools not appearing
:
Ensure the server is properly configured in
.mcp.json
or
plugin.json
Verify the server implements the MCP protocol correctly
Check for connection timeouts in debug output
​
Directory structure mistakes
Symptoms
: Plugin loads but components (skills, agents, hooks) are missing.
Correct structure
: Components must be at the plugin root, not inside
.claude-plugin/
. Only
plugin.json
belongs in
.claude-plugin/
.
my-plugin/
├── .claude-plugin/
│   └── plugin.json      ← Only manifest here
├── commands/            ← At root level
├── agents/              ← At root level
└── hooks/               ← At root level
If your components are inside
.claude-plugin/
, move them to the plugin root.
Debug checklist
:
Run
claude --debug
and look for “loading plugin” messages
Check that each component directory is listed in the debug output
Verify file permissions allow reading the plugin files
​
Distribution and versioning reference
​
Version management
Claude Code uses the plugin’s version as the cache key that determines whether an update is available. When you run
/plugin update
or auto-update fires, Claude Code computes the current version and skips the update if it matches what’s already installed.
The version is resolved from the first of these that is set:
The
version
field in the plugin’s
plugin.json
The
version
field in the plugin’s marketplace entry in
marketplace.json
The git commit SHA of the plugin’s source, for
github
,
url
,
git-subdir
, and relative-path sources in

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
applies, and it works without changing your permission mode, so you still see permission prompts before tools run.
Explanatory
: Provides educational “Insights” in between helping you complete software engineering tasks. Helps you understand implementation choices and codebase patterns.
Learning
: Collaborative, learn-by-doing mode where Claude will not only share “Insights” while coding, but also ask you to contribute small, strategic pieces of code yourself. Claude Code will add
TODO(human)
markers in your code for you to implement.
​
Change your output style
Run
/config
and select
Output style
to pick a style from a menu. Your selection is saved to
.claude/settings.local.json
at the
local project level
.
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
between the working directory and the repository root.
As of v2.1.178, when more than one of these nested directories defines a style with the same name, Claude Code uses the one closest to the working directory.
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
and select your style under
Output style
. It takes effect after
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
All output styles have their own custom instructions added to the end of the system prompt.
All output styles trigger reminders for Claude to adhere to the output style instructions during the conversation.
Custom output styles leave out Claude Code’s built-in software engineering instructions, such as how to scope changes, write comments, and verify work, unless
keep-coding-instructions
is set to
true
.
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
Escalate hard decisions with the advisor tool
Terminal configuration
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
. To disable a tool entirely, add its name to the
deny
array in your
permission settings
.
To add custom tools, connect an
MCP server
. To extend Claude with reusable prompt-based workflows, write a
skill
, which runs through the existing
Skill
tool rather than adding a new tool entry.
Tool
Description
Permission required
Agent
Spawns a
subagent
with its own context window to handle a task. See
Agent tool behavior
No
Artifact
Publishes an HTML or Markdown file as an
artifact
: a private, interactive page on claude.ai. On Team and Enterprise plans, you can share it inside your organization.
Requires a Pro, Max, Team, or Enterprise plan and
/login
authentication; see
Availability
Yes
AskUserQuestion
Asks multiple-choice questions to gather requirements or clarify ambiguity.
Questions stay open until you answer them: there’s no idle timeout by default. To have an idle dialog auto-continue instead, set the
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
. Once the chosen idle time passes with no input, the dialog closes on its own: it submits any options you’d already selected and tells Claude you may be away from your keyboard, so Claude proceeds on its own judgment and can re-ask later. A countdown appears for the last 20 seconds. Any keypress restarts the timer, and so does a focused window on terminals that report focus. The timeout applies only to
AskUserQuestion
’s multiple-choice questions; permission prompts, including plan approval, never auto-resolve on idle. In v2.1.198 and v2.1.199, the dialog auto-continued after 60 seconds of idle by default, and
CLAUDE_AFK_TIMEOUT_MS
was the only way to change that
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
EnterPlanMode
Switches to plan mode to design an approach before coding
No
EnterWorktree
Creates an isolated
git worktree
and switches into it. Pass a
path
to switch into an existing worktree of the current repository instead of creating a new one. From within a worktree session, or from a subagent with a pinned working directory such as
isolation: worktree
, only the
path
form is available and the target must be under
.claude/worktrees/
No
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
can reach you when you step away.
Push delivery runs through Anthropic-hosted infrastructure, which is not accessible from Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry
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
command.
Routines live on claude.ai and require a Pro, Max, Team, or Enterprise plan, so this tool is not accessible from Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry
No
ReportFindings
Reports code-review findings as a structured list, with a file, summary, and failure scenario per finding, so Claude Code can render them instead of printing them as text. Claude calls it when active code-review instructions tell it to.
Requires Claude Code v2.1.196 or later.
As of v2.1.199, a finding can also carry an optional
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
. Claude calls this at the end of each iteration to pick when the next one runs, between one minute and one hour out; you don’t call it directly. The pending wakeup appears in
session_crons
in
Stop hook input
.
Not available on Amazon Bedrock, Google Cloud’s Agent Platform, or Microsoft Foundry, where a
/loop
prompt with no interval runs on a fixed schedule instead
No
SendMessage
Sends a message to an
agent team
teammate, or
resumes a subagent
by its agent ID or name. Stopped subagents auto-resume in the background. Structured team-protocol messages require agent teams. A receiver never treats a message from another agent as your consent or approval.
As of v2.1.198, a subagent treats a message from the agent that launched it as normal task direction rather than as a peer request.
As of v2.1.199, a send to a name that now resolves to a different agent than it did earlier in the conversation is refused instead of delivered; see
Resume subagents
No
SendUserFile
Sends files from the session to you with an optional caption, so a generated report, diagram, screenshot, or built artifact reaches your device instead of only being mentioned in the transcript.
As of v2.1.196, the optional
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
Creates a new task in the task list
No
TaskGet
Retrieves full details for a specific task
No
TaskList
Lists all tasks with their current status
No
TaskOutput
(Deprecated) Retrieves output from a background task. Prefer
Read
on the task’s output file path
No
TaskStop
Stops a running background task by ID.
As of v2.1.198, also accepts an
agent-team teammate
or a named background agent by agent ID or name
No
TaskUpdate
Updates task status, dependencies, details, or deletes tasks
No
TodoWrite
Manages the session task checklist. Disabled by default as of v2.1.142 in favor of
TaskCreate
,
TaskGet
,
TaskList
, and
TaskUpdate
. Set
CLAUDE_CODE_ENABLE_TASKS=0
to re-enable
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
rule.
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
The Agent tool spawns a subagent in a separate context window. The subagent works through its task autonomously, then returns a single text result to the parent conversation. The parent doesn’t see the subagent’s intermediate tool calls or outputs, only that final result.
To cap how many turns a subagent runs, set
maxTurns
in the
subagent definition
.
The same Agent tool also launches
forked subagents
when fork mode is enabled. A fork inherits the full parent conversation instead of starting fresh, always runs in the background, and still surfaces permission prompts in your terminal. The rest of this section describes named subagents.
Which tools a named subagent can use depends on the
tools
and
disallowedTools
fields in the
subagent definition
:
Neither field set
: the subagent inherits every tool available to the parent.
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
Launching the subagent doesn’t itself prompt for permission. Claude Code checks the subagent’s own tool calls against your permission rules as it runs.
As of v2.1.198, subagents run in the background by default; Claude runs one in the foreground when it needs the result before continuing.
Foreground subagents
show the same permission prompts you would see in the main conversation, at the moment each tool call happens.
Background subagents
surface permission prompts in your main session as of v2.1.186. The prompt names which subagent is asking, and pressing Esc denies that one tool call without stopping the subagent. Before v2.1.186, background subagents auto-denied any tool call that would otherwise prompt and continued without that tool.
To limit what a subagent can reach in the first place, narrow its
tools
field, leave Bash off the list, or set deny rules in your settings, as described in
Control subagent capabilities
. For more on choosing between foreground and background, see
Run subagents in foreground or background
.
​
Bash tool behavior
The Bash tool runs each command in a separate process with the following persistence behavior:
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
Two limits bound each command:
Timeout
: two minutes by default. Claude can request up to 10 minutes per command with the
timeout
parameter. Override the default and ceiling with
BASH_DEFAULT_TIMEOUT_MS
and
BASH_MAX_TIMEOUT_MS
.
Output length
: 30,000 characters by default. When a command produces more than that, Claude Code saves the full output to a file in the session directory and gives Claude the file path plus a short preview from the start. Claude reads or searches that file when it needs the rest. Raise the limit with
BASH_MAX_OUTPUT_LENGTH
, up to a hard ceiling of 150,000 characters.
For long-running processes such as dev servers or watch builds, Claude can set
run_in_background: true
to start the command as a background task and continue working while it runs. List and stop background tasks with
/tasks
.
​
Edit tool behavior
The Edit tool performs exact string replacement. It takes an
old_string
and a
new_string
and replaces the first with the second. It doesn’t use regex or fuzzy matching.
Three checks must pass for an edit to apply:
Read-before-edit
: Claude must have read the file in the current conversation, and the file must not have changed on disk since that read. This check runs first, before any string matching.
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
Viewing a file with Bash also satisfies the read-before-edit requirement when the command is
cat
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
, or
fgrep
on a single file with no pipes or redirects. Piped output and other Bash commands don’t count, and Claude must use Read before editing in those cases.
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
Three output modes control what comes back:
files_with_matches
: file paths only, no line content. This is the default.
content
: matching lines with file and line number.
count
: match count per file.
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
The Monitor tool requires Claude Code v2.1.98 or later.
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
has its own approval prompt.
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
Opening a WebSocket prompts for approval, and the prompt doesn’t offer an option to skip future prompts for the same host.
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
As of v2.1.196, the PowerShell tool matches the Bash tool’s handling of search and diff exit codes. Exit code 1 from
grep
,
egrep
,
fgrep
, and
git grep
means no matches, and exit code 1 from
git diff
means differences exist, so these results aren’t reported to Claude as command failures.
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
Read handles several file types beyond plain text:
Images
: PNG, JPG, and other image formats are returned as visual content that Claude can see, not as raw bytes. Claude Code resizes and recompresses large images to fit the model’s image size limits before sending them, so Claude may see a downscaled version of a large screenshot.
As of v2.1.196, an image that is still larger than 500KB after that resize is re-encoded as a JPEG at reduced quality with its pixel dimensions unchanged. If Claude misses fine pixel-level detail in a large image, ask it to crop the region of interest first, for example with ImageMagick via Bash.
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
files return all cells with their outputs, including code, markdown, and visualizations.
Read only reads files, not directories. Claude uses
ls
via the Bash tool to list directory contents.
​
WebFetch tool behavior
WebFetch takes a URL and a prompt describing what to extract. It fetches the page, converts the response to Markdown when the server returns HTML, and runs the prompt against the content using a small, fast model. For most fetches, Claude receives that model’s answer, not the raw page. The conversion step is not configurable.
This makes WebFetch lossy by design. The extraction prompt determines what reaches Claude, so a result that says a page doesn’t mention something may only mean the prompt didn’t ask about it. Ask Claude to fetch again with a more specific prompt, or use
curl
via Bash for the unprocessed page.
A few behaviors shape the response Claude receives:
HTTP URLs are automatically upgraded to HTTPS.
Large pages are truncated to a fixed character limit before processing.
Responses are cached for 15 minutes, so repeated fetches of the same URL return quickly.
When a URL redirects to a different host, WebFetch returns a text result that names the original URL and the redirect target instead of following it. Claude then fetches the new URL with a second WebFetch call.
In the default and
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
The search backend is not configurable. To search with a different provider, add an
MCP server
that exposes a search tool.
WebSearch permission rules take no specifier. A bare
WebSearch
entry in
allow
or
deny
is the only form.
WebSearch is available on the Claude API,
Claude Platform on AWS
, and Microsoft Foundry. On Google Cloud’s Agent Platform it works with Claude 4 and later models, including Opus, Sonnet, and Haiku. Amazon Bedrock doesn’t expose the server-side web search tool.
​
Write tool behavior
The Write tool creates a new file or overwrites an existing one with the full content provided. It doesn’t append or merge.
If the target path already exists, Claude must have read that file at least once in the current conversation before overwriting it. A Write to an unread existing file fails with an error. This constraint doesn’t apply to new files.
Viewing the file with Bash also satisfies this requirement under the same rules described in
Edit tool behavior
.
For partial changes to an existing file, Claude uses Edit instead of Write.
​
Check which tools are available
Your exact tool set depends on your provider, platform, and settings. To check what’s loaded in a running session, ask Claude directly:
What tools do you have access to?
Claude gives a conversational summary. For exact MCP tool names, run
/mcp
.
The
advisor tool
is a
server tool
that the API runs, rather than a tool that Claude Code implements. It has no name you can reference in permission rules or hook matchers.
​
See also
MCP servers
: add custom tools by connecting external servers
Permissions
: permission system, rule syntax, and tool-specific patterns
Subagents
: configure tool access for subagents
Hooks
: run custom commands before or after tool execution
Was this page helpful?
Yes
No
Environment variables
Interactive mode
⌘
I
Assistant
Responses are generated using AI and may contain mistakes.

## Source (changelog): https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md

# Changelog

## 2.1.201

- Claude Sonnet 5 sessions no longer use the mid-conversation system role for harness reminders

## 2.1.200

- Changed `AskUserQuestion` dialogs to no longer auto-continue by default; opt into an idle timeout via `/config`
- Changed the "default" permission mode to "Manual" across the CLI, `--help`, VS Code, and JetBrains; `--permission-mode manual` and `"defaultMode": "manual"` are accepted alongside `default`
- Fixed a crash at startup when `disabledMcpServers` or `enabledMcpServers` in `.claude.json` is set to a non-array value
- Fixed background sessions silently stopping mid-turn after sleep/wake or when reopening a stalled session
- Fixed background sessions re-running a turn cancelled with Esc after a stall respawn
- Fixed background agents never starting again after a crash left a stale `daemon.lock` whose PID the OS reused
- Fixed background-agent daemon handover so a reinstalled older build can no longer take over the daemon; build recency is now judged by the version's embedded build timestamp
- Fixed background-agent roster issues: transient corruption permanently disabling orphan cleanup, older binaries not preserving fields written by newer versions, and socket auth tokens being stripped during daemon restarts
- Fixed subagents cut off by a rate limit before producing any text output returning an empty result instead of failing cleanly
- Fixed control bytes from background-agent output reaching the terminal in the agent view
- Fixed `claude agents --plugin-dir
` not showing the plugin's agents and skills in the agent view when the flag is placed after `agents`
- Fixed project-scoped plugins not loading correctly from git worktrees of the same repository
- Fixed `/mcp` server list not tracking focus for screen readers and magnifiers
- Fixed voice dictation showing a misleading "Voice connection failed" message when a recording captures no audio
- Fixed rendering flicker under tmux 3.4+ by enabling synchronized terminal output
- Improved screen-reader output: decorative glyphs are now hidden, transcript symbols read as short labels, and nested tables read as `Header: value.` lines
- Improved the install script to explain when installation is killed by the system running out of memory

## 2.1.199

- Stacked slash-skill invocations like `/skill-a /skill-b do XYZ` now load all leading skills (up to 5), not just the first
- Fixed SSL certificate errors (TLS-inspecting proxies, missing `NODE_EXTRA_CA_CERTS`, expired certs) burning retries before showing actionable guidance — they now fail immediately with the fix hint
- Fixed streaming responses being discarded when the API emits a mid-stream overloaded/server error after partial output — the partial is now kept with an incomplete-response notice
- Fixed subagents cut off by a rate limit or server error silently failing instead of returning their partial work to the parent
- Fixed subagents reporting API errors (e.g. usage limit reached) as successful results — the error is now reported to the parent agent
- Fixed the background-agent daemon on Linux killing itself and every running agent every ~50 seconds after an unclean shutdown left a corrupted worker record
- Fixed background agents failing to cold-start over SSH on macOS with "Could not switch to audit session" (regression in 2.1.196)
- Fixed `claude stop` being silently undone when it raced a background-agent respawn — the respawn now honors the stop
- Fixed background job progress indicators stalling for minutes while the job ran long commands
- Fixed background sessions on memory-starved machines showing a generic error — they now indicate low memory and suggest freeing resources
- Fixed remote sessions briefly flapping between Working and Idle in the agent view when a background agent completes
- Fixed idle subagents vanishing from the agent panel while other subagents were still working; surplus idle agents now collapse into an expandable summary row
- Fixed typing `/model` or `/fast` while viewing a subagent silently opening the lead's model picker — a notice now explains the command applies to the lead
- Fixed `SessionStart`, `Setup`, and `SubagentStart` hooks silently hiding stderr when exiting with code 2 — the error is now shown in the transcript
- Fixed `claude --dangerously-skip-permissions daemon
` being treated as a chat prompt instead of running the subcommand
- Fixed `SendMessage` silently misrouting when a re-spawned agent reuses a previous agent's name — the tool now detects the mismatch and asks the caller to retarget
- Fixed opening or resuming a session with no new messages needlessly growing the transcript file
- Fixed backgrounding a session with `←` or `/background` dropping its `/color` from the agent view row
- Fixed resetting a corrupted config file from the startup recovery dialog destroying it unrecoverably — it now backs up the file first
- Fixed Claude in Chrome repeatedly opening the reconnect page when sessions run from different builds or config directories
- Fixed plan mode not prompting for state-changing browser tool calls; read-only `browser_batch` calls are now correctly auto-allowed
- Transient server rate-limit errors (429s unrelated to your usage limit) are now retried automatically with backoff for subscribers instead of failing the turn
- `CLAUDE_CODE_RETRY_WATCHDOG` now raises the default retry count for non-capacity transient errors to 300 and lifts the cap of 15 on `CLAUDE_CODE_MAX_RETRIES`
- `claude agents` session rows now show pull-request links as bare `#N` without the redundant "PR" label

## 2.1.198

- Subagents now run in the background by default, so Claude keeps working while they run and is notified when they finish (previously a gradual rollout)
- Claude in Chrome is now generally available
- Added background agent notifications in `claude agents` — sessions that need input or finish now fire the `Notification` hook (`agent_needs_input` / `agent_completed`)
- Added `/dataviz` skill for chart and dashboard design guidance with a runnable color-palette validator
- Gateway: added Claude Platform on AWS (anthropicAws) as an upstream provider; model-not-found responses now advance the failover chain
- Background agents launched from `claude agents` now commit, push, and open a draft PR when they finish code work in a worktree, instead of stopping to ask
- The built-in Explore agent now inherits the main session's model (capped at opus) instead of running on haiku
- Subagents and context compaction now inherit the session's extended thinking configuration, improving output quality on delegated tasks
- Fixed brief network drops mid-response aborting the turn — transient errors like ECONNRESET now retry with backoff instead of failing
- Fixed excessive background classifier requests when sandboxed processes repeatedly accessed the same network host
- Fixed background tasks in web, desktop, and VS Code task panels getting stuck on "Running" after they finish or after resuming a session
- Fixed agent teams: a teammate that dies on an API error now reports "failed" to the lead, and messaging a stuck teammate wakes it to retry immediately
- Fixed the `/diff` panel not refreshing when you switch branches or commit outside the session
- Fixed markdown tables overflowing and wrapping their right border when rendered in fullscreen mode
- Fixed Claude Platform on AWS and Mantle sessions dead-ending with "Please run /login" when the STS token expires — `awsAuthRefresh` now runs automatically
- Fixed "no route to host" for local-network hosts in macOS background agent sessions by declaring Local Network entitlements
- Fixed `/desktop` failing with "Cannot determine working directory" after entering and exiting a worktree
- Fixed background agents repeatedly showing "Reconnecting…" every ~52 seconds on macOS while the agents view was open
- Fixed pressing `←` inside `claude attach
` exiting to the shell instead of opening the agent view
- Fixed `claude --bg` silently creating an unattachable session when combined with `--print`/`-p`; the conflicting flags are now rejected up front
- Fixed the workflow progress view dropping the earliest agents from the list while the phase counter stayed correct in SDK and desktop-app sessions
- Fixed `.claude/rules/` conditional rules not loading when the target file is reached via a symlinked path
- Fixed Cmd+click not opening URLs in fullscreen mode in Warp on macOS
- Fixed double-click word selection in fullscreen mode to select the entire URL including the scheme
- Fixed plan mode not auto-allowing read-only tool calls when a session starts in plan mode
- Fixed `/branch` deriving its default fork name from the compaction summary instead of the first real prompt
- Improved focus mode: subagents launched in a turn now appear in its activity summary, and completed background notifications fold into a single count
- Improved syntax highlighting accuracy in code blocks, diffs, and file previews by upgrading to highlight.js 11
- Keyboard shortcut hints now show opt/cmd instead of alt/super when connected from a Mac over SSH
- Improved API retry UX: the error reason is now shown after the second attempt, and a status page link replaces the spinner tip when the API is overloaded
- `/login` now opens the sign-in dialog from the `claude agents` view instead of saying it isn't available
- Subagents now treat messages from the agent that launched them as normal task direction; an agent's message is still never treated as the user's approval
- Removed the `/agents` wizard; ask Claude to create or manage subagents, or edit `.claude/agents/` directly

## 2.1.197

- Introducing Claude Sonnet 5: now the default model in Claude Code, with a native 1M-token context window and promotional pricing of $2/$10 per Mtok through August 31. Update to version 2.1.197 for access. https://www.anthropic.com/news/claude-sonnet-5

## 2.1.196

- Added support for organization default models — admins set it in the org console; it shows as "Org default" (or "Role default") in `/model` when you haven't picked one yourself
- Added readable default names for sessions at start, making them easier to identify and message
- Added clickable file attachments in chat — Cmd/Ctrl-click reveals the file in Finder/Explorer
- Security: `claude mcp list`/`get` no longer spawn `.mcp.json` servers that a repo self-approved via a committed `.claude/settings.json`; untrusted workspaces show `⏸ Pending approval`
- Fixed waking a background job permanently deleting its conversation and re-running the original prompt when the transcript probe misread a real transcript; the file is now set aside, never deleted
- Fixed the rate-limit warning flickering off and rate-limit telemetry being over-counted when multiple parallel requests were in flight at the moment a usage limit was hit
- Fixed duplicate recap lines after a background session's turn: a schema-rejected StructuredOutput attempt no longer renders alongside its retry
- Fixed PowerShell `git diff`/`git grep`, `egrep`/`fgrep`, and quoted search patterns containing `|` being reported as failures when they exit 1, matching Bash behavior
- Fixed multiple `claude agents` side panel issues: keyboard focus getting stuck when opening an agent, background jobs losing their subagent types on every open, and sessions showing incorrect status while actively running
- Fixed `claude agents --dangerously-skip-permissions` silently falling back to auto mode instead of showing the bypass disclaimer and applying bypass mode to spawned agents
- Fixed mid-turn crash recovery for Remote sessions — sessions interrupted by a server restart now auto-resume on the next worker
- Fixed sessions moved with `/cd` reappearing in the old directory's resume list after a non-graceful exit when the old path contained special characters
- Fixed `claude plugin validate` skipping local plugins whose source is "." and stopping after the first error class
- Fixed Esc Esc at an idle prompt not opening the rewind menu (regression); use Ctrl+C or Ctrl+X Ctrl+K to stop background agents
- Fixed MCP OAuth requesting the authorization server's full `scopes_supported` catalog when no scope is specified, causing `invalid_scope` failures on GitLab self-hosted and other enterprise IdPs
- Fixed `/context` showing 0 tokens for all tool groups on Bedrock
- Fixed `/deep-research` misreporting verifier failures as "all claims refuted" instead of `unverified`
- Fixed plugin dependency version pins not being honored when the marketplace was added as a local folder path backed by a git repo
- Fixed `claude agents` session status: completed rows no longer flip between "Done" and "Needs your input", stalled agents are now labeled "Needs attention", and results that mention a PR show a clickable link
- Fixed voice dictation swallowing spaces and spuriously starting a recording during very fast typing when voice mode is enabled
- Improved background session reliability: long-running commands and workflows now survive the session's process being stopped, restarted, or updated — including on Windows, where background shells are handed off instead of being killed
- Improved background agents: workers killed by a daemon restart are now automatically resumed from where they left off the next time the agents view opens
- Improved `/code-review` workflow: merged five cleanup finders into one, cutting token usage by roughly 25%
- Reduced per-frame rendering work in the terminal UI by skipping no-op subtree walks during streaming
- The streaming idle watchdog is now on by default for all providers — it aborts and retries when a response stream produces no events for 5 minutes. Set `CLAUDE_ENABLE_STREAM_WATCHDOG=0` to disable.
- Remote Control is now disabled when `ANTHROPIC_BASE_URL` points at a non-Anthropic host, matching the existing behavior under `CLAUDE_CODE_USE_BEDROCK`/`_VERTEX`/`_FOUNDRY`
- Changed opening the agents view from a foreground session to require a single `←` press instead of two, matching the behavior in background sessions

## 2.1.195

- Added `CLAUDE_CODE_DISABLE_MOUSE_CLICKS` to disable mouse click/drag/hover in fullscreen mode while keeping wheel scroll
- Fixed hook matchers with hyphenated identifiers (e.g. `code-reviewer`, `mcp__brave-search`) accidentally substring-matching — they now exact-match. Use `mcp__brave-search__.*` to match all tools from a hyphenated MCP server.
- Fixed voice dictation on macOS capturing silence in long-running sessions after the default input device changes
- Fixed voice dictation auto-submit never firing for languages written without spaces (Japanese, Chinese, Thai)
- Fixed external plugins enabled only by project `.claude/settings.json` not requiring explicit install consent on every loader path
- Fixed `/plugin` Enable/Disable not working when a plugin's `plugin.json` `name` differs from its marketplace entry name
- Fixed background jobs disappearing from `claude agents` or losing data when written by a newer Claude Code version
- Fixed reopening a crashed background task showing a blank screen for up to 5 seconds instead of its restart
- Fixed background agent daemons running unreachable when the control socket fails to start, blocking restarts
- Improved voice mode on Linux: now distinguishes "no microphone" from "SoX not installed" when SoX is present but no audio capture device exists
- Improved `claude agents` completed list to fill available vertical space; on short terminals the header compacts so live sessions stay visible
- Improved Remote session startup with a provisioning checklist while the container starts

## 2.1.193

- Added `autoMode.classifyAllShell` setting to route all Bash/PowerShell commands through the auto-mode classifier instead of only arbitrary-code-execution patterns
- Added auto-mode denial reasons to the transcript, the denial toast, and `/permissions` recent denials
- Added `claude_code.assistant_response` OpenTelemetry log event containing the model's response text. Redacted unless `OTEL_LOG_ASSISTANT_RESPONSES=1`; when that var is unset it follows `OTEL_LOG_USER_PROMPTS`, so deployments that already log prompt content will start receiving response content on upgrade — set `OTEL_LOG_ASSISTANT_RESPONSES=0` to keep prompts-only.
- Added live file path autocomplete to bash mode (`!`)
- Added a startup notice when MCP servers need authentication, pointing at `/mcp`
- Added automatic memory-pressure reaping for idle background shell commands (disable with `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`)
- Fixed `/model` and other client-data-gated UI showing stale/empty state immediately after `/login`
- Fixed backgrounding (←←) spuriously cancelling with "N background tasks would be abandoned" when all running tasks carry over to the new session
- Fixed pinned background agents being re-prompted to "Continue from where you left off" after every auto-update
- Fixed backgrounding the main turn spawning a phantom "general-purpose (resumed)" subagent that re-ran the main conversation
- Fixed agent panel hiding sibling agents when viewing a subagent
- Improved background agents: the launch result no longer instructs Claude to "end your response" — it keeps working on other tasks while the agent runs
- Improved MCP `headersHelper` auth: the helper now re-runs and reconnects automatically when a tool call returns 401/403
- Improved plugin auto-rename: marketplace `renames` maps are now followed automatically, updating your settings to the new name
- Improved `/add-dir` message when the directory is already a working directory

## 2.1.191

- Added `/rewind` support for resuming a conversation from before `/clear` was run
- Fixed scroll position jumping to the bottom while reading earlier output during a streaming response
- Fixed background agents resurrecting after being stopped — stopping an agent from the tasks panel is now permanent
- Fixed `/voice` showing a generic "not available" message when disabled by an organization's policy — it now explains the restriction
- Fixed `/login` URL opening truncated in Windows Terminal when it wraps across lines
- Fixed Cmd+click on links in fullscreen mode for Ghostty over ssh/tmux
- Fixed `claude agents` sending builtin slash commands like `/usage` to background sessions as prompt text instead of showing a hint
- Fixed `claude agents` job rows showing full filesystem paths for pasted images instead of the `[Image #N]` placeholder
- Fixed hooks with comma-separated matchers (e.g. `"Bash,PowerShell"`) silently never firing
- Fixed `/permissions` Recently-denied tab: approving a denial now persists on close instead of being silently discarded
- Fixed the agent panel jumping by one row when scrolling the roster past the overflow cap
- Fixed the welcome splash art overflowing the default 80×24 macOS Terminal window
- Fixed managed settings: `forceRemoteSettingsRefresh` now takes effect when set via MDM or file policy, and the fetch sends `Cache-Control: no-cache` to prevent proxies from serving stale responses
- Improved sandbox network permission dialog: hosts you allow with "Yes" are now remembered for the rest of the session instead of re-prompting on every connection
- Improved MCP server reliability: capability discovery (`tools/list`, `prompts/list`, `resources/list`) now retries transient network errors with short backoff
- Improved MCP OAuth: discovery and token requests now retry once after transient network errors, and headless environments skip the browser popup and go straight to the paste-the-URL prompt
- Improved MCP error messages: HTTP 404 errors now show the URL and point to your MCP config
- Improved vim mode prompt-history search (NORMAL `/`) to hint how to reach slash commands
- Reduced CPU usage during streaming responses by ~37% by coalescing text updates to 100ms
- Reduced long-session memory growth from terminal output cache

## 2.1.190

- Bug fixes and reliability improvements

## 2.1.187

- Added `sandbox.credentials` setting to block sandboxed commands from reading credential files and secret environment variables
- Added org-configured model restrictions to the model picker, `--model`, `/model`, and `ANTHROPIC_MODEL`, with a "restricted by your organization's settings" message when a restricted model is selected
- Added mouse click support to select menus (permission prompts, `/model`, `/config`, etc.) in fullscreen mode
- Fixed `--resume` failing with "No conversation found" when the original `-p` run produced no model turns
- Fixed `--json-schema` and workflow `agent({schema})` structured output: the model can no longer re-call `StructuredOutput` indefinitely after a successful call, and follow-up turns now reliably return structured output
- Fixed remote MCP tool calls that hang with no response for 5 minutes — they now abort with an error instead of blocking indefinitely (override with `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`)
- Fixed Claude Code Remote sessions taking ~2.7s longer to start after the agent proxy CA system-trust install was added
- Fixed pasted Korean/CJK text turning into mojibake in terminals that deliver paste as per-byte extended-key events
- Fixed `/update` over Remote Control hanging when a startup trust dialog would have shown
- Fixed background jobs in the agents view getting stuck in "working" indefinitely when the agent ended a turn without producing structured output
- Fixed channel connections dropping after navigating to the agents view and back, and after `/bg`, `/tui`, or `/update`
- Fixed agent stop notifications not correctly attributing who stopped the agent, and improved wording ("finished"/"stopped" instead of "came to rest")
- Fixed subagent depth tracking: resumed subagents now restore their original spawn depth, and forked subagents now count toward the depth cap
- Fixed leaked agent worktree registrations: locked `.git/worktrees/` entries from killed agents are now cleaned up automatically
- Fixed Cmd+click not opening URLs in fullscreen mode in Ghostty on macOS
- Fixed `claude --help` not listing the `--bg`/`--background` flag
- Fixed Esc, Ctrl-C, and Ctrl-D not working while `/share` is uploading
- Improved `/install-github-app`: GitHub Actions workflow setup is now optional — you can install just the GitHub App and skip the workflow/secret steps
- Improved `/btw` with ←/→ arrow navigation to step through earlier answers
- Improved `/plugin` to surface plugins you haven't used recently so you can clean them up
- [VSCode] Fixed extension becoming unresponsive when resuming a large session

## 2.1.186

- Added `claude mcp login
` and `claude mcp logout
` to authenticate MCP servers from the CLI without opening the interactive `/mcp` menu, with `--no-browser` stdin redirect support for completing over SSH
- Added status filtering (press `f`) to the `/workflows` agent detail view
- Added a "Skills" section to the `/plugin` Installed tab
- Added `teammateMode: "iterm2"` setting with a warning when auto mode cannot find the `it2` CLI
- Added "Claude Platform on AWS - refresh credentials" option to `/login` when `awsAuthRefresh` is configured
- `!` bash commands now trigger Claude to respond to the output automatically; set `"respondToBashCommands": false` in settings.json to keep the previous context-only behavior
- Fixed streaming requests failing with "Content block not found" or JSON parse errors after the machine wakes from sleep
- Fixed subagent transcript scroll position bleeding into the main transcript on exit
- Fixed background task previews flashing raw tool names before the agent's plan loaded
- Fixed Chrome tab-group isolation not applying when the in-product permissions gate is off for concurrent CLI sessions
- Fixed background session recaps being duplicated; the agent's own end-of-turn summary now shows as the recap line
- Fixed opening a background session from `claude agents` leaving the previous screen painted behind it
- Fixed `Agent(type)` deny rules and `Agent(x,y)` allowed-types restrictions not being enforced for named subagent spawns
- Fixed Esc and Ctrl+C not responding while background agents are still running after the main turn ends
- Fixed misaligned option numbers in permission prompts when the option text overflows
- Fixed pressing `x` on a finished subagent in the agent panel not dismissing it
- Fixed a misleading "MCP server disconnected" notice for intentionally retired tools when resuming older sessions
- Fixed `/plugin` Installed showing a "more above" indicator when already scrolled to the top
- Fixed `~~strikethrough~~` showing literal tildes in assistant messages instead of rendering as strikethrough
- Fixed `--tools` allowing feature-gated tools to slip through before flags loaded on a cold first launch
- Fixed background job status in `claude agents` showing a stale "needs input" message after replying
- Fixed a dark-theme flash when opening a background session from `claude agents` on a light terminal
- Fixed mouse-selected text staying highlighted after deleting it in `claude agents`
- Fixed session cost not showing for usage-based Enterprise and Team subscribers
- Fixed agent teams: teammates spawned via tmux/pane backends now inherit the leader's `--effort` level
- Fixed Workflow `agent({schema})` subagents looping forever on repeated schema validation failures instead of aborting after 5 attempts
- Improved `claude mcp get` and `claude mcp remove` to suggest the closest configured server name on a typo and truncate long server lists
- Improved memory: the agent is now reminded to compact its `MEMORY.md` index when nearing the size limit
- Improved skill frontmatter: `display-name`, `default-enabled`, `fallback`, and `metadata.*` keys now accept kebab-case, snake_case, and camelCase
- Improved malformed `SKILL.md` YAML frontmatter handling: loads the skill body with empty metadata instead of failing silently
- Changed `CLAUDE_CODE_MAX_RETRIES` to cap at 15; for unattended sessions, use `CLAUDE_CODE_RETRY_WATCHDOG` instead
- Changed background subagents to surface permission prompts in the main session instead of auto-denying; the dialog shows which agent is asking, and Esc denies just that tool
- Changed `/review
` to use the same review engine as `/code-review medium`

## 2.1.185

- The stream-stall hint now reads "Waiting for API response · will retry in …" instead of "No response from API · Retrying in …", and triggers after 20s of silence instead of 10s

## 2.1.183

- Improved auto mode safety: destructive git commands (`git reset --hard`, `git checkout -- .`, `git clean -fd`, `git stash drop`) are now blocked when you didn't ask to discard local work, `git commit --amend` is blocked when the commit wasn't made by the agent this session, and `terraform destroy`/`pulumi destroy`/`cdk destroy` are blocked unless you asked for the specific stack
- Added a warning when the requested model is deprecated or automatically updated to a newer model, shown on stderr in print mode (`-p`) and now also covering models set in agent frontmatter
- Added `attribution.sessionUrl` setting to omit the claude.ai session link from commits and PRs in web and Remote Control sessions
- Added `/config --help` to list all available shorthand keys for `/config key=value`
- Changed `/config` toggle behavior: Enter and Space both change the selected setting, and Esc now saves and closes instead of reverting
- Removed the startup "setup issues" line under the logo — run `/doctor` to see configuration issues or use `--debug`
- Fixed `thinking.disabled.display: Extra inputs are not permitted` 400 errors on subagent spawns and session-title generation for affected configurations
- Fixed WebSearch returning empty results in subagents
- Fixed the terminal cursor being stranded above the prompt after navigating history in vim mode with the native cursor enabled
- Fixed fullscreen TUI corruption (statusline mid-screen, duplicated spinner rows, merged text) in Windows Terminal under heavy nested-subagent load
- Fixed turns silently completing with no visible output when the model returned only a thinking block; Claude now re-prompts once
- Fixed user-level skills appearing multiple times in slash-command autocomplete when multiple plugins are enabled
- Fixed MCP servers requiring authentication exposing auth-stub tools to the model in headless/SDK mode
- Fixed tmux teammate panes failing to launch when the shell has slow rc-file initialization, and keystrokes typed during agent spawn leaking into the new tmux pane instead of the leader prompt
- Fixed background tasks started by a teammate being killed when the teammate finishes a turn
- Fixed scheduled task and webhook trigger deliveries being treated as keyboard input; they now classify as task notifications and can no longer approve a pending action or set the session title in auto mode
- Fixed focus mode showing "Ran N PostToolUse hooks" timing lines under each response

## 2.1.181

- Added `/config key=value` syntax to set any setting from the prompt (e.g. `/config thinking=false`) — works in interactive, `-p`, and Remote Control
- Added `sandbox.allowAppleEvents` opt-in setting that lets sandboxed commands send Apple Events on macOS
- Added `CLAUDE_CLIENT_PRESENCE_FILE` environment variable: point it at a marker file to suppress mobile push notifications while you're at the machine
- Upgraded the bundled Bun runtime to 1.4
- Improved streaming of long paragraphs: text now appears line-by-line instead of waiting for the first line break
- Improved auto-retry: API connection drops mid-thinking now automatically retry instead of showing "Connection closed while thinking"
- Improved the subagent panel: idle subagents auto-hide after 30s, the list caps at 5 rows with scroll hints, and keyboard hints now show in the footer
- Improved the MCP OAuth browser page to match Claude Code's visual style and auto-close on success
- Changed fullscreen mode URL opening to require Cmd+click (macOS) / Ctrl+click, matching native terminal behavior
- Changed the `Improved N memories` line to no longer list individual files outside verbose mode
- Fixed prompt caching not reading on custom `ANTHROPIC_BASE_URL` and on Foundry due to a per-request attestation token changing every turn
- Fixed Write/Edit producing 0-byte or truncated files on network drives and cloud-synced folders
- Fixed `open`, `osascript`, and browser-based auth flows failing with error -600 on macOS by adding the Apple Events entitlement
- Fixed a startup regression (~120ms per launch in fresh environments, introduced in 2.1.169): the first prompt no longer waits for the managed-settings fetch when no MCP servers are configured
- Fixed startup blocking with a blank terminal for up to 15 seconds when the account settings fetch is slow on a degraded network
- Fixed startup crash (`TypeError: Cannot read properties of null`) when `.claude.json` contains corrupted null project entries
- Fixed macOS TUI freezing at session start (Ctrl+C unresponsive) when Spotlight is busy reindexing
- Fixed long-running idle sessions losing their history when another Claude Code process ran the 30-day transcript cleanup
- Fixed foreground subagents spawning unbounded nested chains; they now respect the same 5-level depth limit as background subagents
- Fixed `/recap` and conversation forks using the previous model immediately after a model switch
- Fixed subagent "Thinking" duration showing the parent agent's elapsed time instead of the subagent's own
- Fixed subagents blocked on a nested agent showing a ticking elapsed time instead of "waiting" in the agent panel
- Fixed the API retry indicator ("Retrying in 0s · attempt N/10") staying on screen after the retry succeeded
- Fixed AWS `awsCredentialExport` credentials with a short remaining lifetime causing credential refreshes every minute, and now accepts the JSON shape from `aws configure export-credentials`
- Fixed `claude mcp get`/`list` showing `✓ Connected` when tools/list fails; they now show `! Connected · tools fetch failed` with the error detail
- Fixed `/remote-control` leaving a stale "connecting…" line; it now confirms in the transcript once connected
- Fixed ExitWorktree refusing to remove a clean worktree with "Could not verify worktree state" when bare `git` cannot be resolved on Windows
- Fixed settings changes (such as `/effort` or `/model`) failing with ENOENT when `~/.claude/settings.json` is a relative symlink under a symlinked `~/.claude`
- Fixed IDE selection line numbers in context reminders being off by one (IntelliJ and VS Code)
- Fixed Ctrl+C in fullscreen after a native terminal selection (modifier+drag) overwriting the clipboard with the app's prior selection
- Fixed Ctrl+V showing "No image found in clipboard" instead of pasting when the clipboard contains text
- Fixed agent creation failing with "EEXIST: file already exists" when the agents directory already exists (Windows/OneDrive)
- Fixed AskUserQuestion preview content being cut off at the dialog edge instead of word-wrapping
- Fixed AskUserQuestion multi-select questions silently dropping a typed "Other" free-text answer when submitting
- Fixed `/stats` "Most active day" and daily token chart dates showing one day early in UTC-negative timezones
- Fixed `/copy` and copy-on-select on Linux not detecting a clipboard utility installed after Claude Code started
- Fixed tab-indented code rendering with incorrect indentation in the Write (create-file) preview
- Fixed user prompts queued mid-turn not showing a full-width background highlight in the transcript
- Fixed the activity spinner's pulse dwelling on the wrong glyph size in Ghostty

## 2.1.179

- Fixed mid-stream connection drops: partial responses are now preserved instead of showing a raw error, and the spinner no longer gets stuck at "running tool"
- Fixed mouse-wheel scrolling in WSL2 under Windows Terminal and VS Code (regression in 2.1.172)
- Fixed a sandbox `denyRead`/`allowRead` glob over a large directory tree making the Bash tool description enormous and the session unusable on Linux
- Fixed the feedback survey capturing a single-digit reply as a session rating immediately after a turn completes
- Fixed the welcome screen stacking multiple promotional banners — at most one promo now shows per session
- Fixed Ctrl+O not showing the subagent's transcript when viewing a subagent
- Fixed clicking the prompt input not returning focus from the subagent/footer panel
- Fixed remote session background tasks appearing stuck as "still running" between turns
- Improved plugin loading performance in remote sessions

## 2.1.178

- Agent teams: removed the `TeamCreate` and `TeamDelete` tools. With `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` set, every session now has one implicit team — spawn teammates directly with the Agent tool's `name` parameter, no setup step needed. The `team_name` parameter on the Agent tool is still accepted but ignored.
- Added `Tool(param:value)` syntax for permission rules to match a tool's input parameters (with `*` wildcard), e.g. `Agent(model:opus)` to block Opus subagents
- Skills in nested `.claude/skills` directories now load when working on files there; on a name clash, the nested skill appears as `
:
` so both stay available
- Nested `.claude/` directories: the agent, workflow, and output-style closest to the working directory now wins when names collide; project-scope workflow saves now target the closest existing `.claude/workflows/`
- Improved auto mode: subagent spawns are now evaluated by the classifier before launch, closing a gap where a subagent could request a blocked action without review
- Improved `/doctor` with consistent flat tree layout across all sections, clearer section status icons, and highlighted command names
- Improved the skill listing truncation warning to show how many skill descriptions are affected
- Changed the workflow prompt keyword to use a purple shimmer highlight and trigger only on explicit phrases like "run a workflow" or "workflow:", not on any mention of the word
- Improved Remote Control error messages: connection failures now show a persistent red "/rc failed" indicator in the footer, and the "not yet enabled" error now explains whether it's a gate, a check failure, stale entitlement, or org policy
- `/bug` now requires a description before submitting, and no longer uses model-refusal text as the GitHub issue title
- Fixed a crash (out-of-memory) when the CLI inherits a stale websocket/OAuth file-descriptor environment variable from a parent process
- Fixed Claude in Chrome silently failing to connect when the OAuth token belongs to a different account than the Claude Code login
- Fixed nested `.claude/skills` skills with directory-qualified names being blocked by permission prompts in non-interactive runs
- Fixed several subagent issues: viewing a subagent's transcript now shows tool results and live progress, messages sent while it finishes its turn are no longer dropped, and backgrounding a running subagent (ctrl+b) no longer restarts it from scratch
- Fixed `claude agents` workers failing with `401 Invalid bearer token` when the daemon was started from a shell with a custom API gateway via `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`
- Fixed compaction not honoring `--fallback-model`: compaction now falls back to the configured fallback model chain on overload or model-availability errors
- Fixed model requests continuing to fail with auth errors after credentials were refreshed outside the session, due to a stale cached request configuration
- Fixed background sessions created with `/bg` or `←←` after a turn finished showing "Working" forever in the agents list
- Fixed Linux sandbox failing to start when `.claude/skills` or `.claude/hooks` is a symlink
- Fixed `CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1` preventing fresh marketplace installs from cloning
- Fixed MCP server-level specs (`mcp__server`, `mcp__server__*`, `mcp__*`) in subagent `disallowedTools` being silently ignored
- Fixed vim mode undo: `u` now steps through NORMAL/VISUAL-mode commands one at a time instead of merging commands in quick succession into a single undo step
- Fixed statusline links with custom URI schemes (e.g. `vscode://`) not opening when clicked in `claude agents`
- [VSCode] Fixed pressing Esc to dismiss a CJK IME candidate window canceling the running Claude task

## 2.1.176

- Session titles are now generated in the language of your conversation (set the `language` setting to pin a specific language)
- Added `footerLinksRegexes` setting for regex-matched link badges in the footer row, configurable via user or managed settings
- Improved Bedrock credential caching: credentials from `awsCredentialExport` are now cached until their `Expiration` instead of a fixed 1 hour
- Fixed `availableModels` enforcement: alias model picks can no longer be redirected to a blocked model via `ANTHROPIC_DEFAULT_*_MODEL` environment variables, and `/fast` now refuses to toggle when it would switch to a model outside the allowlist
- Fixed auto mode failing on Fable 5 for organizations without Opus 4.8 enabled — the classifier now falls back to the best available Opus model
- Fixed hook `if` conditions for Read/Edit/Write tool paths: documented patterns like `Edit(src/**)`, `Read(~/.ssh/**)`, and `Read(.env)` now match correctly
- Fixed Linux sandbox failing to start when `.claude/settings.json` is a symlink with an absolute target
- Fixed `/copy` and mouse-selection copy not reaching the system clipboard inside tmux over SSH, and tmux paste buffer not loading on versions older than 3.2
- Fixed Remote Control connecting from web/mobile silently switching the session's model
- Fixed Remote Control disconnect notifications showing a bare numeric code instead of a human-readable reason, and connection failures adding a duplicate line to the conversation transcript
- Fixed Remote Control sessions not disconnecting when you sign in to a different account
- Fixed `/cd` and worktree moves leaving the session reporting the previous directory's git branch
- Fixed `claude agents`: pressing back in one window no longer detaches other windows attached to the same session
- Fixed backgrounded sessions showing "Working" forever when `/bg` mid-turn had nothing left to continue
- Fixed background agent search by PR URL: PRs opened during scheduled wakeups or while a job was blocked now appear in `claude agents` search
- Fixed the agents view input showing no text cursor on Windows
- Fixed `claude --bg -cn
` not seeding the session name
- Fixed background sessions to neutralize Windows network paths in persisted state before respawn
- Fixed background-session respawn rejecting malformed resume IDs from corrupted state files
- Fixed the Windows background-service daemon not starting when `~/.claude/daemon` has the ReadOnly attribute set
- Fixed cloud sessions failing with "Could not resolve authentication method" when idle for too long before being claimed
- Background sessions now show clearer guidance when a window left open across an auto-update can't submit a reply, and `claude daemon status` explains version-skew behavior

## 2.1.175

- Added `enforceAvailableModels` managed setting — when enabled, the `availableModels` allowlist also constrains the Default model (a Default that would resolve to a disallowed model now falls back to the first allowed model), and user or project settings can no longer widen a managed `availableModels` list

## 2.1.174

- Added `wheelScrollAccelerationEnabled` setting to disable mouse-wheel scroll acceleration in fullscreen mode
- Fixed the `/model` picker hiding the model family that Default resolves to — Opus now appears as its own row on Max/Team Premium/Enterprise plans, Sonnet on Pro/Team plans, and Opus on pay-as-you-go API accounts
- Fixed `/model` picker showing a hardcoded Sonnet version label when `ANTHROPIC_DEFAULT_SONNET_MODEL` pins a different Sonnet
- Fixed the "Fable 5 is now consuming usage credits" banner incorrectly showing for enterprise accounts with usage-based billing
- Fixed Bedrock GovCloud regions (`us-gov-*`) deriving the wrong inference profile prefix (`global` instead of `us-gov`), causing 400 errors on derived model IDs
- Fixed background sessions inheriting another session's `ANTHROPIC_*` provider env (gateway URL, custom headers, `/model` aliases) from the shell that started the background daemon
- Fixed a 1-2 second pause when exiting Claude Code shortly after a shell command was interrupted or killed on macOS and Linux
- Fixed git commit co-author attribution showing an incorrect model name for some models
- Fixed the `/advisor` dialog pre-selecting a saved advisor model that is blocked by the `availableModels` allowlist
- Fixed skill hot-reload re-sending the entire skill listing when a single skill changed; only changed skills are now re-announced
- Fixed Workflow tool `agent()` subagents missing per-agent attribution headers
- [VSCode] Added usage attribution to the Account & usage dialog (`/usage`) showing cache misses, long context, subagents, and per-skill/agent/plugin/MCP breakdowns over the last 24h or 7d
- Fixed pre-warmed background workers failing with "Could not resolve authentication method" when claimed after sitting idle

## 2.1.173

- Fixed Fable 5 model names with a `[1m]` suffix not being normalized — Fable 5 includes 1M context by default, so the suffix is now stripped automatically
- Fixed a spurious "sandbox dependencies missing" startup warning on Windows when sandbox was enabled in settings

## 2.1.172

- Sub-agents can now spawn their own sub-agents (up to 5 levels deep)
- Amazon Bedrock now reads the AWS region from `~/.aws` config files when `AWS_REGION` isn't set, matching AWS SDK precedence; `/status` shows where the region came from
- Added a search bar when browsing a marketplace's plugins in `/plugin`
- Added `model` attribute to the `claude_code.lines_of_code.count` OTEL metric
- Fixed sessions using 1M context without usage credits getting permanently stuck — the session now automatically compacts back under the standard context limit
- Fixed a repeating "an image in the conversation could not be processed and was removed" error when the conversation contained multiple images
- Fixed the agents view keeping a session under Working with a busy spinner for up to 30 seconds after the worker replied
- Fixed background agents potentially reading another directory's project settings (`.mcp.json` approvals, trust) when dispatched onto a pre-warmed worker
- Fixed background-session attach failing with EAUTH for sessions started on an older version after the daemon auto-updated
- Fixed a background sub-agent staying stuck as "active" in the agent panel after a nested agent it spawned was stopped
- Fixed `/model` suggestions in the `claude agents` dispatch input rendering with a misleading slash prefix and showing models disabled for your org
- Fixed `availableModels` restrictions not being applied to subagent model overrides, the agent dispatch model picker, and the advisor model
- Fixed `availableModels` allowlists hiding the `/model` picker's Opus and Sonnet 1M rows when entries use version-specific IDs like `claude-opus-4-8`
- Fixed the `/model` picker on Bedrock offering models the provider doesn't serve — selecting one silently switched the session model and lit the selection marker on multiple rows
- Fixed model IDs getting a doubled 1M-context suffix (e.g. `[1M][1m]`) when `ANTHROPIC_DEFAULT_OPUS_MODEL` already includes one
- Fixed `opusplan` model setting not shipping with 1M context in plan mode for entitled users; the `opusplan[1m]` workaround now also correctly switches to Opus in plan mode
- Fixed `WebFetch(domain:*.example.com)` wildcard domain rules never matching subdomains in allow, deny, and ask position, and file permission rules with mid-pattern wildcards (e.g. `Read(secrets-*/config.json)`) being rejected at startup
- Fixed up-arrow prompt history showing the main agent's prompts while a subagent's chat tab is open
- Fixed memory recall not finding mounted team memory stores (`CLAUDE_MEMORY_STORES`) in remote sessions
- Fixed workflow validation rejecting scripts whose prompt strings or comments merely mention `Date.now()`/`Math.random()`
- Disable mouse tracking on Windows consoles that don't fully support it
- Fixed the `/plugin` marketplace list losing its cursor after backing out of a long plugin list, and Esc from the plugin browser returning to the wrong tab
- Improved performance in long conversations by removing redundant message normalization and avoiding full message-history transforms when streaming tool-use state is unchanged
- Reduced idle CPU usage: `/goal` status chip no longer re-renders the terminal at 5 Hz while idle, and fewer UI re-renders while subagents run in parallel
- Improved Claude in Chrome tool loading: browser tools now load in a single batched call instead of one per tool
- Improved the non-interactive Usage Policy refusal message to suggest starting a new session or changing your model
- `/code-review` now keeps the `ultra` option visible when you're not signed in to claude.ai, with an explanation that the cloud review requires a claude.ai account
- Shortened the Remote Control footer indicator to "/rc active" and hid it on narrow terminals
- Stopped promoting `/loop` in remote sessions, where pending loops don't keep the container alive
- [VSCode] Fixed PowerShell tool calls rendering as raw JSON instead of a proper command display and permission dialog, and stripped ANSI escape codes from displayed shell output

## 2.1.170

- Introducing Claude Fable 5: a Mythos-class model that we’ve made safe for general use. Fable’s capabilities exceed those of any model we’ve ever made generally available. Update to version 2.1.170 for access. https://www.anthropic.com/news/claude-fable-5-mythos-5
- Fixed sessions not saving transcripts (and not appearing in --resume) when launched from the VS Code integrated terminal or any shell that inherited Claude Code environment variables.

## 2.1.169

- Self-hosted runner: added a `post-session` lifecycle hook that runs after the session ends and before the workspace is deleted, so you can snapshot uncommitted work or export logs; also made the child-process SIGTERM→SIGKILL window configurable (default unchanged at 5s)
- Added `--safe-mode` flag (and `CLAUDE_CODE_SAFE_MODE`) to start Claude Code with all customizations (CLAUDE.md, plugins, skills, hooks, MCP servers) disabled for troubleshooting
- Added `/cd` command to move a session to a new working directory without breaking the prompt cache mid-session
- Added a `disableBundledSkills` setting and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS` environment variable to hide bundled skills, workflows, and built-in slash commands from the model
- Fixed Up/Down arrows jumping to command history past the wrapped rows of a long input line — they now move through each visual row first, and history recall enters at the near edge
- Fixed enterprise managed MCP policies (`allowedMcpServers`/`deniedMcpServers`) not being enforced on reconnect, IDE-typed configs, `--mcp-config` servers during the first session after install, or before remote settings loaded; also fixed slow cold starts for orgs without remote settings
- Fixed a ~30-50ms UI stall at the start of each turn for macOS users logged in with claude.ai credentials
- Fixed `claude -p` being slow or appearing to hang on Windows while waiting for the slash-command/skill scan (regression in 2.1.161)
- Fixed Remote Control getting stuck on "reconnecting" after resuming a session when an OAuth token refresh happened at the same time
- Fixed Git Credential Manager's "Connect to GitHub" popup appearing on Windows at startup when background git commands ran without cached credentials
- Fixed footer hints (e.g. "esc to interrupt") not showing for users with a custom statusline
- Fixed stale permission and dialog prompts reappearing every time you reattac
